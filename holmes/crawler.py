"""
Rastreamento de site (clearnet e .onion).

Complemento do motor: quando você JÁ TEM a URL, isto expande a página em uma
árvore e extrai os artefatos de cada nó — e-mail, telefone, endereço de
cripto, perfil social e domínio externo.

Escrito a partir da avaliação do TorBot (OWASP), corrigindo o que estava
quebrado ou faltando lá:

| TorBot                                    | Aqui                              |
|-------------------------------------------|-----------------------------------|
| `parse_links()` sem `base_url` no crawl   | `urljoin` sempre — link relativo  |
|   → perdia todo link relativo             |   é resolvido                     |
| sem conjunto de visitados                 | visitados global, sem revisitar   |
| sequencial                                | paralelo, com teto de workers     |
| sem rate limit                            | intervalo mínimo por host         |
| classificador treinado em site comercial  | nenhum rótulo inventado           |
| telefone só de `href="tel:"`              | `tel:` + corpo do texto validado  |
| guardava o HTML                           | só o artefato extraído            |

O corpo das páginas NUNCA é gravado — em investigação de dark web isso é
proteção, não detalhe: evita materializar no servidor conteúdo cuja simples
posse é crime.
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

from .entity import Entity
from .findings import Confidence, Finding, FindingKind

# ── configuração de execução (a UI liga/desliga) ────────────────────────────

_ENABLED = False
_SETTINGS = {
    "depth": 1,             # 0 = só a página informada
    "max_pages": 15,
    "workers": 6,
    "delay_por_host": 0.3,  # segundos entre requisições ao mesmo host
    "same_site": True,
    "timeout": 20,
    "max_bytes": 600_000,   # não baixa arquivo grande
}


def set_enabled(value: bool) -> None:
    global _ENABLED
    _ENABLED = bool(value)


def is_enabled() -> bool:
    return _ENABLED


def configure(**kwargs) -> None:
    for k, v in kwargs.items():
        if k in _SETTINGS and v is not None:
            _SETTINGS[k] = v


def settings() -> dict:
    return dict(_SETTINGS)


# ── extração de artefatos ───────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I)
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,3}\)|\d{2,3})[\s.-]?\d{4,5}[\s.-]?\d{4}")

# Endereço de cripto é o artefato mais valioso num mercado .onion: é o que
# amarra vendedor, pagamento e, muitas vezes, identidade via exchange.
_CRYPTO_RES = {
    "BTC": re.compile(r"\b(?:bc1[a-z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"),
    "ETH": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "XMR": re.compile(r"\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b"),
}

_SOCIAL_HOSTS = {
    "instagram.com": "Instagram", "facebook.com": "Facebook", "x.com": "X/Twitter",
    "twitter.com": "X/Twitter", "linkedin.com": "LinkedIn", "github.com": "GitHub",
    "t.me": "Telegram", "youtube.com": "YouTube", "tiktok.com": "TikTok",
    "wa.me": "WhatsApp", "discord.gg": "Discord", "reddit.com": "Reddit",
}

_EMAIL_GENERICO = {
    "info", "contato", "contact", "suporte", "support", "admin", "webmaster",
    "noreply", "no-reply", "privacy", "privacidade", "sac", "vendas", "abuse",
}


def _extrair_emails(texto: str) -> set[str]:
    achados = set()
    for m in _EMAIL_RE.findall(texto or ""):
        mail = m.lower().strip(".")
        # Filtra falso positivo comum: nome de arquivo e sentinela de exemplo.
        if mail.endswith((".png", ".jpg", ".gif", ".webp", ".svg", ".css", ".js")):
            continue
        if mail.split("@")[-1] in {"example.com", "email.com", "domain.com", "sentry.io"}:
            continue
        achados.add(mail)
    return achados


def _extrair_telefones(texto: str, region: str = "BR") -> set[str]:
    """Valida com libphonenumber quando disponível — sem isso vira lixo numérico."""
    brutos = set(_PHONE_RE.findall(texto or ""))
    if not brutos:
        return set()
    try:
        import phonenumbers as pn
    except ImportError:
        # Sem validador: só aceita o que tem cara de número completo.
        return {b.strip() for b in brutos if 10 <= len(re.sub(r"\D", "", b)) <= 15}

    validos = set()
    for bruto in brutos:
        digits = re.sub(r"\D", "", bruto)
        if not (10 <= len(digits) <= 15):
            continue
        for tentativa in (bruto, f"+{digits}"):
            try:
                num = pn.parse(tentativa, region)
                if pn.is_valid_number(num):
                    validos.add(pn.format_number(num, pn.PhoneNumberFormat.E164))
                    break
            except Exception:
                continue
    return validos


def _extrair_cripto(texto: str) -> set[tuple[str, str]]:
    out = set()
    for moeda, rx in _CRYPTO_RES.items():
        for endereco in rx.findall(texto or ""):
            out.add((moeda, endereco))
    return out


def _normalizar_url(url: str) -> str:
    """Sem fragmento e sem barra final — para o conjunto de visitados funcionar."""
    try:
        p = urlparse(url)
        caminho = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme.lower(), p.netloc.lower(), caminho, "", p.query, ""))
    except Exception:
        return url


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def extrair_links(html: str, base_url: str) -> list[str]:
    """
    Resolve link relativo contra a página atual — este é exatamente o passo
    que o TorBot tem implementado e não usa no crawl (chama `parse_links()`
    sem `base_url`), perdendo todo link relativo do site.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html or "", "html.parser")
    saida: list[str] = []
    for tag in soup.find_all("a"):
        href = tag.get("href")
        if not href or not isinstance(href, str):
            continue
        href = href.strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        resolvido = urljoin(base_url, href)
        if resolvido.startswith(("http://", "https://")):
            saida.append(_normalizar_url(resolvido))
    return list(dict.fromkeys(saida))


# ── limitador de taxa por host ──────────────────────────────────────────────

class _RateLimiter:
    """Intervalo mínimo entre requisições ao mesmo host. Educado e discreto."""

    def __init__(self, delay: float) -> None:
        self._delay = delay
        self._ultimo: dict[str, float] = {}
        self._lock = threading.Lock()

    def espera(self, host: str) -> None:
        with self._lock:
            agora = time.time()
            anterior = self._ultimo.get(host, 0.0)
            faltando = self._delay - (agora - anterior)
            self._ultimo[host] = agora + max(0.0, faltando)
        if faltando > 0:
            time.sleep(faltando)


# ── página e resultado ──────────────────────────────────────────────────────

@dataclass
class Pagina:
    url: str
    status: int | None
    titulo: str = ""
    profundidade: int = 0
    emails: set[str] = field(default_factory=set)
    telefones: set[str] = field(default_factory=set)
    cripto: set[tuple[str, str]] = field(default_factory=set)
    sociais: list[tuple[str, str]] = field(default_factory=list)
    externos: set[str] = field(default_factory=set)
    erro: str | None = None
    # Nenhum campo guarda o HTML: o corpo é descartado após a extração.


@dataclass
class Resultado:
    inicio: str
    paginas: list[Pagina] = field(default_factory=list)
    visitadas: int = 0
    via_tor: bool = False
    aviso: str | None = None


def _sessao(is_onion: bool):
    from . import net

    s = net.build_session(retries=1)
    if is_onion:
        # Tor local — mesmo SOCKS que o Robin e o start_web.sh já usam.
        s.proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050",
        }
    return s


def tor_disponivel(host: str = "127.0.0.1", port: int = 9050, timeout: float = 2.0) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _buscar(sessao, url: str, timeout: int, max_bytes: int) -> tuple[int | None, str, str | None]:
    """(status, html, erro). Só baixa HTML e só até o teto de bytes."""
    try:
        resp = sessao.get(url, timeout=timeout, stream=True, allow_redirects=True)
    except Exception as exc:
        return None, "", f"{type(exc).__name__}: {str(exc)[:120]}"

    tipo = (resp.headers.get("Content-Type") or "").lower()
    if "html" not in tipo and "text" not in tipo:
        resp.close()
        return resp.status_code, "", f"tipo não textual ({tipo.split(';')[0] or 'desconhecido'})"

    pedacos: list[bytes] = []
    total = 0
    try:
        for pedaco in resp.iter_content(8192):
            pedacos.append(pedaco)
            total += len(pedaco)
            if total >= max_bytes:
                break
    except Exception as exc:
        return resp.status_code, "", f"leitura interrompida: {exc}"
    finally:
        resp.close()

    encoding = resp.encoding or "utf-8"
    return resp.status_code, b"".join(pedacos).decode(encoding, errors="replace"), None


def _processar(html: str, url: str, status: int | None, profundidade: int) -> Pagina:
    pagina = Pagina(url=url, status=status, profundidade=profundidade)
    if not html:
        return pagina

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        pagina.titulo = (soup.title.get_text(strip=True) if soup.title else "") or _host(url)
        texto = soup.get_text(" ", strip=True)
        # mailto: e tel: são declaração explícita de contato — valem mais.
        for tag in soup.find_all("a"):
            href = (tag.get("href") or "").strip()
            if href.lower().startswith("mailto:"):
                pagina.emails |= _extrair_emails(href[7:])
            elif href.lower().startswith("tel:"):
                pagina.telefones |= _extrair_telefones(href[4:])
    except ImportError:
        pagina.titulo = _host(url)
        texto = re.sub(r"<[^>]+>", " ", html)

    pagina.emails |= _extrair_emails(texto)
    pagina.telefones |= _extrair_telefones(texto)
    pagina.cripto |= _extrair_cripto(texto)

    origem = _host(url)
    for link in extrair_links(html, url):
        h = _host(link)
        if not h or h == origem:
            continue
        for conhecido, plataforma in _SOCIAL_HOSTS.items():
            if h == conhecido or h.endswith("." + conhecido):
                pagina.sociais.append((plataforma, link))
                break
        else:
            pagina.externos.add(h)
    return pagina


def rastrear(
    url_inicial: str,
    depth: int | None = None,
    max_pages: int | None = None,
    same_site: bool | None = None,
) -> Resultado:
    """Percorre em largura, com visitados, paralelismo e rate limit por host."""
    from concurrent.futures import ThreadPoolExecutor

    cfg = settings()
    depth = cfg["depth"] if depth is None else depth
    max_pages = cfg["max_pages"] if max_pages is None else max_pages
    same_site = cfg["same_site"] if same_site is None else same_site

    inicio = _normalizar_url(url_inicial)
    host_inicial = _host(inicio)
    is_onion = host_inicial.endswith(".onion")

    resultado = Resultado(inicio=inicio, via_tor=is_onion)
    if is_onion and not tor_disponivel():
        resultado.aviso = (
            "Endereço .onion mas o Tor não está escutando em 127.0.0.1:9050 — "
            "rastreamento não executado."
        )
        return resultado

    sessao = _sessao(is_onion)
    limitador = _RateLimiter(cfg["delay_por_host"])
    visitadas: set[str] = set()
    lock = threading.Lock()
    fila: deque[tuple[str, int]] = deque([(inicio, 0)])

    def _uma(url: str, nivel: int) -> tuple[Pagina, list[str]]:
        limitador.espera(_host(url))
        status, html, erro = _buscar(sessao, url, cfg["timeout"], cfg["max_bytes"])
        if erro and not html:
            p = Pagina(url=url, status=status, profundidade=nivel, erro=erro)
            p.titulo = _host(url)
            return p, []
        pagina = _processar(html, url, status, nivel)
        filhos = extrair_links(html, url) if nivel < depth else []
        del html  # o corpo morre aqui: nada de conteúdo é guardado
        return pagina, filhos

    with ThreadPoolExecutor(max_workers=max(1, cfg["workers"])) as pool:
        while fila and len(visitadas) < max_pages:
            # Um nível por vez: dá para paralelizar sem perder o controle.
            lote: list[tuple[str, int]] = []
            while fila and len(lote) < cfg["workers"] and len(visitadas) + len(lote) < max_pages:
                url, nivel = fila.popleft()
                chave = _normalizar_url(url)
                with lock:
                    if chave in visitadas:
                        continue
                    visitadas.add(chave)
                lote.append((chave, nivel))

            if not lote:
                break

            for pagina, filhos in pool.map(lambda a: _uma(*a), lote):
                resultado.paginas.append(pagina)
                for filho in filhos:
                    if len(visitadas) + len(fila) >= max_pages:
                        break
                    if same_site and _host(filho) != host_inicial:
                        continue
                    if _normalizar_url(filho) not in visitadas:
                        fila.append((filho, pagina.profundidade + 1))

    resultado.visitadas = len(resultado.paginas)
    return resultado


# ── conector ────────────────────────────────────────────────────────────────

def crawl_findings(entity: Entity) -> Iterable[Finding]:
    """Transforma o rastreamento em achados do dossiê."""
    inicio = entity.get("url") or (
        entity.value if "://" in entity.value else f"https://{entity.value}"
    )
    res = rastrear(inicio)

    if res.aviso:
        return [Finding(
            kind=FindingKind.NOTE, value=res.aviso, source="crawler",
            source_label="Rastreamento", confidence=Confidence.CONFIRMED,
        )]
    if not res.paginas:
        return []

    ok = [p for p in res.paginas if p.status and 200 <= p.status < 400]
    out: list[Finding] = [Finding(
        kind=FindingKind.NOTE,
        value=f"{res.visitadas} páginas rastreadas ({len(ok)} responderam)",
        source="crawler", source_label="Rastreamento", url=res.inicio,
        confidence=Confidence.CONFIRMED,
        detail=("Via Tor. " if res.via_tor else "")
               + "Somente os artefatos foram extraídos — o conteúdo das páginas não é armazenado.",
        raw={"paginas": [{"url": p.url, "status": p.status, "titulo": p.titulo}
                         for p in res.paginas[:60]]},
    )]

    raiz = next((p for p in res.paginas if p.titulo and not p.erro), None)
    if raiz and raiz.titulo:
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"Título do site: {raiz.titulo}",
            source="crawler", source_label="Rastreamento", url=raiz.url,
            confidence=Confidence.CONFIRMED,
        ))

    emails: dict[str, str] = {}
    telefones: dict[str, str] = {}
    cripto: dict[tuple[str, str], str] = {}
    sociais: dict[str, tuple[str, str]] = {}
    externos: dict[str, str] = {}

    for p in res.paginas:
        for e in p.emails:
            emails.setdefault(e, p.url)
        for t in p.telefones:
            telefones.setdefault(t, p.url)
        for c in p.cripto:
            cripto.setdefault(c, p.url)
        for plataforma, link in p.sociais:
            sociais.setdefault(link, (plataforma, p.url))
        for h in p.externos:
            externos.setdefault(h, p.url)

    for mail, pagina_url in emails.items():
        local = mail.split("@")[0]
        generico = local in _EMAIL_GENERICO
        out.append(Finding(
            kind=FindingKind.EMAIL, value=mail, source="crawler",
            source_label="Rastreamento do site", url=pagina_url,
            confidence=Confidence.LIKELY if generico else Confidence.CONFIRMED,
            detail=("Endereço institucional publicado no site."
                    if generico else "E-mail publicado no site rastreado."),
        ))

    for tel, pagina_url in telefones.items():
        out.append(Finding(
            kind=FindingKind.PHONE, value=tel, source="crawler",
            source_label="Rastreamento do site", url=pagina_url,
            confidence=Confidence.CONFIRMED, detail="Telefone publicado no site rastreado.",
        ))

    for (moeda, endereco), pagina_url in cripto.items():
        out.append(Finding(
            kind=FindingKind.CRYPTO, value=f"{moeda}: {endereco}", source="crawler",
            source_label="Rastreamento do site", url=pagina_url,
            confidence=Confidence.CONFIRMED,
            detail=f"Endereço {moeda} publicado no site. Consultável em explorador "
                   "de blockchain para histórico de transações.",
            raw={"moeda": moeda, "endereco": endereco},
        ))

    for link, (plataforma, pagina_url) in sociais.items():
        out.append(Finding(
            kind=FindingKind.ACCOUNT, value=f"{plataforma}: {link}", source="crawler",
            source_label="Rastreamento do site", url=link,
            confidence=Confidence.CONFIRMED,
            detail=f"Perfil divulgado pelo próprio site (em {pagina_url}).",
        ))

    for host, pagina_url in list(externos.items())[:25]:
        out.append(Finding(
            kind=FindingKind.DOMAIN, value=host, source="crawler",
            source_label="Rastreamento do site", url=f"http://{host}",
            confidence=Confidence.LIKELY,
            detail=f"Domínio externo referenciado pelo site (em {pagina_url}).",
        ))

    falhas = [p for p in res.paginas if p.erro]
    if falhas:
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"{len(falhas)} página(s) não pudera(m) ser lidas",
            source="crawler", source_label="Rastreamento", confidence=Confidence.CONFIRMED,
            detail="; ".join(f"{_host(p.url)}: {p.erro}" for p in falhas[:4]),
        ))
    return out
