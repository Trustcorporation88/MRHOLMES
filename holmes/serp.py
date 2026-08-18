"""
Busca de superfície.

Este é o módulo que faltava. Sem ele o Holmes nunca ia superar "digitar o
nome no Google", porque simplesmente não havia busca clearnet estruturada.

Provedores em ordem de qualidade: Serper (índice do Google) → Brave →
Google CSE → DuckDuckGo HTML (sem chave, degradado). O primeiro que tiver
chave configurada é usado; o DDG é a rede de segurança.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote_plus, urlparse

from . import net
from .entity import Entity, EntityType

# Domínios cujo resultado é quase sempre ruído numa investigação de pessoa.
_NOISE_HOSTS = {
    "pinterest.com", "quora.com", "answers.com", "wikihow.com",
    "amazon.com", "amazon.com.br", "mercadolivre.com.br", "aliexpress.com",
    "shopee.com.br", "olx.com.br", "ebay.com",
}

# Host → plataforma, para transformar resultado de busca em "conta encontrada".
_PLATFORM_HOSTS = {
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "linkedin.com": "LinkedIn",
    "twitter.com": "X/Twitter",
    "x.com": "X/Twitter",
    "github.com": "GitHub",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "threads.net": "Threads",
    "t.me": "Telegram",
    "reddit.com": "Reddit",
    "medium.com": "Medium",
    "twitch.tv": "Twitch",
    "behance.net": "Behance",
    "dribbble.com": "Dribbble",
    "gitlab.com": "GitLab",
    "about.me": "About.me",
    "lattes.cnpq.br": "Lattes",
    "jusbrasil.com.br": "JusBrasil",
    "escavador.com": "Escavador",
}


@dataclass
class SerpHit:
    title: str
    url: str
    snippet: str = ""
    position: int = 0
    engine: str = ""
    query: str = ""

    @property
    def host(self) -> str:
        try:
            return (urlparse(self.url).netloc or "").lower().replace("www.", "")
        except Exception:
            return ""

    @property
    def platform(self) -> str | None:
        host = self.host
        for known, name in _PLATFORM_HOSTS.items():
            if host == known or host.endswith("." + known):
                return name
        return None

    @property
    def is_noise(self) -> bool:
        return self.host in _NOISE_HOSTS


# ── provedores ──────────────────────────────────────────────────────────────

def _serper(query: str, limit: int) -> list[SerpHit]:
    key = net.get_key("serper")
    data = net.post_json(
        "https://google.serper.dev/search",
        payload={"q": query, "num": min(limit, 20), "gl": "br", "hl": "pt-br"},
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
        timeout=15,
    ) or {}
    hits: list[SerpHit] = []
    for i, item in enumerate(data.get("organic") or []):
        hits.append(
            SerpHit(
                title=item.get("title") or "",
                url=item.get("link") or "",
                snippet=item.get("snippet") or "",
                position=item.get("position") or i + 1,
                engine="serper",
                query=query,
            )
        )
    # O knowledge graph costuma trazer o nome canônico da pessoa/empresa.
    kg = data.get("knowledgeGraph") or {}
    if kg.get("title"):
        hits.append(
            SerpHit(
                title=kg.get("title"),
                url=kg.get("website") or kg.get("descriptionLink") or "",
                snippet=kg.get("description") or "",
                position=0,
                engine="serper:kg",
                query=query,
            )
        )
    return hits


def _brave(query: str, limit: int) -> list[SerpHit]:
    key = net.get_key("brave")
    data = net.get_json(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": min(limit, 20), "country": "br"},
        headers={"X-Subscription-Token": key, "Accept": "application/json"},
        timeout=15,
    ) or {}
    results = ((data.get("web") or {}).get("results")) or []
    return [
        SerpHit(
            title=r.get("title") or "",
            url=r.get("url") or "",
            snippet=re.sub(r"<[^>]+>", "", r.get("description") or ""),
            position=i + 1,
            engine="brave",
            query=query,
        )
        for i, r in enumerate(results)
    ]


def _google_cse(query: str, limit: int) -> list[SerpHit]:
    data = net.get_json(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": net.get_key("google_cse"),
            "cx": net.get_key("google_cse_cx"),
            "q": query,
            "num": min(limit, 10),
            "gl": "br",
            "hl": "pt-BR",
        },
        timeout=15,
    ) or {}
    return [
        SerpHit(
            title=r.get("title") or "",
            url=r.get("link") or "",
            snippet=r.get("snippet") or "",
            position=i + 1,
            engine="google_cse",
            query=query,
        )
        for i, r in enumerate(data.get("items") or [])
    ]


def _clean_href(href: str) -> str:
    """Desembrulha redirecionador (DDG usa /l/?uddg=…)."""
    from urllib.parse import parse_qs, unquote

    if not href:
        return ""
    if "uddg=" in href:
        qs = parse_qs(urlparse(href).query)
        return unquote((qs.get("uddg") or [href])[0])
    if href.startswith("//"):
        return "https:" + href
    return href


def _keyless(query: str, limit: int) -> list[SerpHit]:
    """
    Sem chave. Aviso honesto: motores públicos bloqueiam IP de datacenter,
    então em servidor (Railway) isso costuma voltar vazio. É rede de segurança,
    não substituto de uma SERP API.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    def _parse(html: str, selectors: list[tuple[str, str, str]], engine: str) -> list[SerpHit]:
        soup = BeautifulSoup(html, "html.parser")
        hits: list[SerpHit] = []
        for item_sel, link_sel, snip_sel in selectors:
            nodes = soup.select(item_sel)
            if not nodes:
                continue
            for i, node in enumerate(nodes[:limit]):
                link = node.select_one(link_sel) if link_sel else node
                if not link or not link.get("href"):
                    continue
                snip = node.select_one(snip_sel) if snip_sel else None
                hits.append(SerpHit(
                    title=link.get_text(" ", strip=True),
                    url=_clean_href(link.get("href")),
                    snippet=snip.get_text(" ", strip=True) if snip else "",
                    position=i + 1, engine=engine, query=query,
                ))
            if hits:
                return hits
        return hits

    session = net.build_session(retries=1)

    # 1. DuckDuckGo lite (POST) — o mais tolerante dos três.
    try:
        resp = session.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query, "kl": "br-pt"}, timeout=15,
        )
        if resp.ok:
            hits = _parse(
                resp.text,
                [("table tr", "a.result-link", ".result-snippet"),
                 ("div.result", "a.result-link", ".result-snippet")],
                "ddg-lite",
            )
            if hits:
                return hits
    except Exception:
        pass

    # 2. DuckDuckGo HTML.
    try:
        html = net.get_text(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "kl": "br-pt"}, timeout=15, ttl=3600,
        )
        if html:
            hits = _parse(
                html,
                [(".result__body", "a.result__a", ".result__snippet")],
                "duckduckgo",
            )
            if hits:
                return hits
    except Exception:
        pass

    # 3. Mojeek — índice próprio, costuma aceitar scraping educado.
    try:
        html = net.get_text(
            "https://www.mojeek.com/search",
            params={"q": query}, timeout=15, ttl=3600,
        )
        if html:
            hits = _parse(
                html,
                [("ul.results-standard li", "a.title", "p.s"),
                 ("li.result", "h2 a", "p.s")],
                "mojeek",
            )
            if hits:
                return hits
    except Exception:
        pass

    return []


# Mantido como alias — algum código antigo pode chamar pelo nome do motor.
_duckduckgo = _keyless


_PROVIDERS = (
    ("serper", "serper", _serper),
    ("brave", "brave", _brave),
    ("google_cse", "google_cse", _google_cse),
)


def active_provider() -> str:
    for name, key, _ in _PROVIDERS:
        if net.has_key(key):
            if name == "google_cse" and not net.has_key("google_cse_cx"):
                continue
            return name
    return "duckduckgo"


def provider_label() -> str:
    return {
        "serper": "Serper (índice Google)",
        "brave": "Brave Search",
        "google_cse": "Google CSE",
        "duckduckgo": "sem chave — motores públicos (instável em servidor)",
    }[active_provider()]


def search_health() -> dict:
    """Diagnóstico honesto para a UI: a busca de superfície está funcionando?"""
    provider = active_provider()
    if provider != "duckduckgo":
        return {"ok": True, "provider": provider, "label": provider_label(),
                "message": f"Busca ativa via {provider_label()}."}
    probe = search("teste mr holmes", limit=3)
    if probe:
        return {"ok": True, "provider": provider, "label": provider_label(),
                "message": "Motores públicos responderam, mas o resultado é limitado. "
                           "Configure SERPER_API_KEY para cobertura real."}
    return {"ok": False, "provider": provider, "label": provider_label(),
            "message": "A busca de superfície está SEM chave e os motores públicos "
                       "bloquearam o servidor. Configure SERPER_API_KEY (serper.dev) "
                       "para que a investigação encontre o que o Google encontra."}


def search(query: str, limit: int = 10) -> list[SerpHit]:
    """Uma busca. Cai para o próximo provedor se o preferido falhar."""
    if not query or not query.strip():
        return []
    chain = [p for p in _PROVIDERS if net.has_key(p[1])]
    if any(p[0] == "google_cse" for p in chain) and not net.has_key("google_cse_cx"):
        chain = [p for p in chain if p[0] != "google_cse"]

    for name, _, fn in chain:
        try:
            hits = fn(query, limit)
            if hits:
                return hits
        except Exception:
            continue
    try:
        return _keyless(query, limit)
    except Exception:
        return []


def search_many(queries: Iterable[str], limit_each: int = 8, max_queries: int = 12) -> list[SerpHit]:
    """
    Roda a bateria de dorks em paralelo e devolve tudo deduplicado por URL,
    preservando a melhor posição de cada resultado.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    unique_queries = list(dict.fromkeys(q for q in queries if q and q.strip()))[:max_queries]
    if not unique_queries:
        return []

    all_hits: list[SerpHit] = []
    with ThreadPoolExecutor(max_workers=min(6, len(unique_queries))) as pool:
        futures = {pool.submit(search, q, limit_each): q for q in unique_queries}
        for fut in as_completed(futures):
            try:
                all_hits.extend(fut.result() or [])
            except Exception:
                continue

    by_url: dict[str, SerpHit] = {}
    for hit in all_hits:
        if not hit.url or hit.is_noise:
            continue
        key = hit.url.rstrip("/").lower()
        existing = by_url.get(key)
        if not existing or (hit.position and hit.position < (existing.position or 99)):
            by_url[key] = hit
    return sorted(by_url.values(), key=lambda h: h.position or 99)


# ── geração de dorks por tipo de alvo ───────────────────────────────────────

_SOCIAL_SITES = (
    "linkedin.com", "instagram.com", "facebook.com", "x.com",
    "github.com", "tiktok.com", "youtube.com", "threads.net",
)

_BR_SITES = (
    "escavador.com", "jusbrasil.com.br", "lattes.cnpq.br",
    "consultasocio.com", "econodata.com.br",
)


def build_queries(entity: Entity, deep: bool = True) -> list[str]:
    """
    A bateria que substitui você digitar 15 buscas na mão.
    Cada string aqui é uma consulta que um investigador faria.
    """
    t, v = entity.type, entity.value
    q: list[str] = []

    if t is EntityType.NAME:
        quoted = entity.get("quoted", f'"{v}"')
        q.append(quoted)
        q += [f"{quoted} site:{s}" for s in _SOCIAL_SITES]
        q.append(f"{quoted} (email OR contato OR telefone)")
        q.append(f"{quoted} (curriculo OR currículo OR CV)")
        if deep:
            q += [f"{quoted} site:{s}" for s in _BR_SITES]
            q.append(f"{quoted} (processo OR ação OR intimação)")
            q.append(f"{quoted} (sócio OR empresa OR CNPJ)")
            q.append(f"{quoted} (filetype:pdf OR filetype:docx)")

    elif t is EntityType.EMAIL:
        quoted = f'"{v}"'
        q += [quoted, f"{quoted} -site:{entity.get('domain', '')}"]
        q.append(f'"{entity.get("local", "")}" "{entity.get("domain", "")}"')
        q += [f"{quoted} site:{s}" for s in ("github.com", "linkedin.com", "pastebin.com")]
        if deep:
            q.append(f"{quoted} (curriculo OR contato OR cadastro)")
            handle = entity.get("username_guess")
            if handle:
                q.append(f'"{handle}" (perfil OR profile OR @{handle})')

    elif t is EntityType.PHONE:
        forms = entity.get("search_forms") or [v]
        q += [f'"{f}"' for f in forms[:3]]
        if entity.get("ddd"):
            q.append(f'"{entity.get("national")}" (contato OR whatsapp OR telefone)')
        q += [f'"{forms[0]}" site:{s}' for s in ("facebook.com", "instagram.com", "olx.com.br")]
        if deep:
            q.append(f'"{forms[0]}" (denuncia OR golpe OR spam OR reclamacao)')
            q.append(f'"{forms[0]}" (empresa OR loja OR clinica OR escritorio)')

    elif t is EntityType.USERNAME:
        handle = entity.get("handle", v)
        q += [f'"{handle}"', f'"@{handle}"']
        q += [f'"{handle}" site:{s}' for s in _SOCIAL_SITES]
        if deep:
            q.append(f'"{handle}" (perfil OR profile OR bio)')
            q.append(f'intext:"{handle}" (email OR contato)')

    elif t is EntityType.DOMAIN:
        root = entity.get("root", v)
        q += [
            f"site:{root}",
            f"site:*.{root} -www",
            f'"{root}" (contato OR email OR telefone)',
            f"site:{root} (filetype:pdf OR filetype:xlsx OR filetype:docx)",
        ]
        if deep:
            q += [
                f"site:{root} (intitle:index.of OR inurl:admin OR inurl:login)",
                f'"{root}" site:linkedin.com/company',
                f'"@{root}" -site:{root}',
            ]

    elif t in (EntityType.CPF, EntityType.CNPJ):
        q += [entity.get("quoted", f'"{v}"'), f'"{entity.get("digits", "")}"']
        if t is EntityType.CNPJ:
            q += [f'"{v}" site:{s}' for s in ("consultasocio.com", "econodata.com.br", "jusbrasil.com.br")]

    elif t is EntityType.IP:
        q += [f'"{v}"', f'"{v}" (abuse OR blacklist OR malware)']

    elif t is EntityType.PROFILE_URL:
        handle = entity.get("handle")
        q.append(f'"{v}"')
        if handle:
            q += [f'"{handle}"'] + [f'"{handle}" site:{s}' for s in _SOCIAL_SITES[:5]]

    return [x for x in dict.fromkeys(q) if x.strip()]


def hits_to_findings(hits: Iterable[SerpHit], entity: Entity) -> list:
    """
    Converte resultado de busca em findings. Resultado em host de plataforma
    conhecida vira CONTA (com o handle extraído); o resto vira resultado web.
    """
    from .findings import Confidence, Finding, FindingKind

    findings: list[Finding] = []
    needle = (entity.get("ascii") or entity.value or "").lower()
    needle_tokens = [t for t in re.split(r"\W+", needle) if len(t) > 2]

    for hit in hits:
        if not hit.url:
            continue
        blob = f"{hit.title} {hit.snippet}".lower()
        # Se o alvo aparece no texto do resultado, o achado é mais forte.
        matched = sum(1 for t in needle_tokens if t in blob)
        strong = needle_tokens and matched >= max(1, len(needle_tokens) - 1)

        platform = hit.platform
        if platform:
            findings.append(
                Finding(
                    kind=FindingKind.ACCOUNT,
                    value=f"{platform}: {hit.title[:80]}",
                    source=f"serp:{hit.engine}",
                    source_label=f"Busca ({hit.engine})",
                    url=hit.url,
                    confidence=Confidence.LIKELY if strong else Confidence.POSSIBLE,
                    detail=hit.snippet[:300],
                    raw={"platform": platform, "query": hit.query, "position": hit.position},
                )
            )
        else:
            findings.append(
                Finding(
                    kind=FindingKind.WEB_RESULT,
                    value=hit.title[:140] or hit.url,
                    source=f"serp:{hit.engine}",
                    source_label=f"Busca ({hit.engine})",
                    url=hit.url,
                    confidence=Confidence.LIKELY if strong else Confidence.POSSIBLE,
                    detail=hit.snippet[:300],
                    raw={"host": hit.host, "query": hit.query, "position": hit.position},
                )
            )

        # Mineração de contato no snippet: e-mail/telefone aparecem muito em SERP.
        for mail in set(re.findall(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", blob)):
            findings.append(
                Finding(
                    kind=FindingKind.EMAIL,
                    value=mail,
                    source=f"serp:{hit.engine}",
                    source_label="Busca (snippet)",
                    url=hit.url,
                    confidence=Confidence.POSSIBLE,
                    detail=f"E-mail extraído do resultado: {hit.title[:60]}",
                )
            )
    return findings
