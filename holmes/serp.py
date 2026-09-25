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


def _brightdata(query: str, limit: int) -> list[SerpHit]:
    """Google pela SERP API da Bright Data: mesmo índice do Serper, sem bloqueio de IP."""
    from urllib.parse import quote_plus

    data = net.brd_serp_json(
        f"https://www.google.com/search?q={quote_plus(query)}"
        f"&num={min(max(limit, 10), 20)}&gl=br&hl=pt-BR",
        timeout=45,
    ) or {}
    hits: list[SerpHit] = []
    for i, item in enumerate(data.get("organic") or []):
        hits.append(
            SerpHit(
                title=item.get("title") or "",
                url=item.get("link") or item.get("url") or "",
                snippet=item.get("description") or item.get("snippet") or "",
                position=item.get("rank") or item.get("global_rank") or i + 1,
                engine="brightdata",
                query=query,
            )
        )
    kg = data.get("knowledge") or {}
    if kg.get("name") or kg.get("title"):
        hits.append(
            SerpHit(
                title=kg.get("name") or kg.get("title"),
                url=kg.get("website") or kg.get("link") or "",
                snippet=kg.get("description") or "",
                position=0,
                engine="brightdata:kg",
                query=query,
            )
        )
    return hits[:limit] if limit else hits


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
    ("brightdata", "brightdata", _brightdata),
    ("brave", "brave", _brave),
    ("google_cse", "google_cse", _google_cse),
)


def _provider_ready(name: str, key: str) -> bool:
    if name == "brightdata":
        # A chave da Bright Data serve também ao Unlocker; a busca só liga
        # quando a zona SERP foi declarada.
        return net.brd_serp_enabled()
    return net.has_key(key)


def active_provider() -> str:
    for name, key, _ in _PROVIDERS:
        if _provider_ready(name, key):
            if name == "google_cse" and not net.has_key("google_cse_cx"):
                continue
            return name
    return "duckduckgo"


def provider_label() -> str:
    return {
        "serper": "Serper (índice Google)",
        "brightdata": "Bright Data SERP (índice Google)",
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
                       "bloquearam o servidor. Configure SERPER_API_KEY (serper.dev), "
                       "ou BRIGHTDATA_API_KEY com HOLMES_BRD_SERP_ZONE, para que a investigação encontre o que o Google encontra."}


def search(query: str, limit: int = 10) -> list[SerpHit]:
    """Uma busca. Cai para o próximo provedor se o preferido falhar."""
    if not query or not query.strip():
        return []
    chain = [p for p in _PROVIDERS if _provider_ready(p[0], p[1])]
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
    with ThreadPoolExecutor(max_workers=min(10, len(unique_queries))) as pool:
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
    "cnpj.biz", "econodata.com.br",
)


def build_queries(entity: Entity, deep: bool = True) -> list[str]:
    """
    A bateria que substitui você digitar 15 buscas na mão.
    Cada string aqui é uma consulta que um investigador faria.
    """
    t, v = entity.type, entity.value
    q: list[str] = []

    if t is EntityType.NAME and is_company_name(v):
        # Razão social: o que interessa é CNPJ, sócios e processos, não rede social.
        quoted = entity.get("quoted", f'"{v}"')
        q += [
            quoted,
            f"{quoted} CNPJ",
            f"{quoted} (sócio OR sócios OR QSA)",
        ]
        q += [f"{quoted} site:{s}" for s in ("cnpj.biz", "econodata.com.br", "jusbrasil.com.br")]
        if deep:
            q += [f"{quoted} site:{s}" for s in ("jusbrasil.com.br", "escavador.com")]

    elif t is EntityType.NAME:
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

    elif t is EntityType.CPF:
        digits = entity.get("digits", "")
        miolo = entity.get("miolo", "")
        q += [entity.get("quoted", f'"{v}"'), f'"{digits}"']
        # Diário oficial, edital e Portal publicam o CPF mascarado pela LGPD
        # (***.456.789-**). Sem essa consulta o CPF quase nunca é achado.
        if miolo:
            q.append(f'"{miolo}" CPF')
        # CPF só aparece em registro público: processo, diário oficial,
        # edital, licitação, lista de aprovados. É onde vale procurar.
        q += [
            f'"{v}" site:jusbrasil.com.br',
            f'"{v}" site:escavador.com',
            f'"{v}" site:jus.br',
            f'"{v}" (diário oficial OR DOU OR DOE OR portaria OR edital)',
            f'"{v}" (licitação OR contrato OR pregão OR empenho)',
            f'"{v}" (filetype:pdf OR filetype:xlsx OR filetype:csv)',
            f'"{v}" site:gov.br',
            f'"{digits}" (processo OR autos OR executado OR requerido)',
        ]
        if miolo and deep:
            q.append(f'"{miolo}" (edital OR nomeação OR portaria OR contrato OR processo)')

    elif t is EntityType.CNPJ:
        digits = entity.get("digits", "")
        q += [entity.get("quoted", f'"{v}"'), f'"{digits}"']
        q += [f'"{v}" site:{s}' for s in ("cnpj.biz", "econodata.com.br", "jusbrasil.com.br")]
        if deep:
            q += [
                f'"{v}" (licitação OR contrato OR pregão OR homologação)',
                f'"{v}" (filetype:pdf OR filetype:xlsx)',
                f'"{v}" (reclamação OR golpe OR fraude OR processo)',
            ]

    elif t is EntityType.PLACA:
        q += [
            f'"{v}"',
            f'placa "{v}"',
            f'"{v}" (venda OR anuncio OR anúncio OR leilao OR leilão OR multa)',
        ]

    elif t is EntityType.IP:
        q += [f'"{v}"', f'"{v}" (abuse OR blacklist OR malware)']

    elif t is EntityType.URL:
        root = entity.get("root") or ""
        q.append(f'"{v}"')
        if root and not entity.get("is_onion"):
            q += [
                f"site:{root}",
                f'"{root}" (contato OR email OR telefone)',
                f"site:{root} (filetype:pdf OR filetype:xlsx)",
            ]
            if deep:
                q += [f"site:*.{root} -www", f'"@{root}" -site:{root}']
        elif root:
            # .onion não é indexado por buscador comum: procura pela menção.
            q += [f'"{root}"', f'"{root}" (mirror OR vendor OR review)']

    elif t is EntityType.PROFILE_URL:
        handle = entity.get("handle")
        q.append(f'"{v}"')
        if handle:
            q += [f'"{handle}"'] + [f'"{handle}" site:{s}' for s in _SOCIAL_SITES[:5]]

    return [x for x in dict.fromkeys(q) if x.strip()]


# Número de processo no padrão CNJ, com pontuação (sem ela dá falso positivo).
_CNJ_RE = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
_CNPJ_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
_EMPRESA_SUFIXO = re.compile(r"\b(ltda|eireli|s/a|s\.a\.?)(?=\W|$)", re.I)
# Onde o texto costuma separar partes: "A x B", "A - Processo", "A | Escavador".
_SEPARADORES = re.compile(r"\s+(?:x|vs\.?|versus)\s+|[|:•·;,()\[\]]|\s[-–—]\s")
_PALAVRAS_RUIDO = {"processo", "processos", "autos", "ação", "acao", "réu", "reu", "autor",
                   "requerente", "requerido", "executado", "exequente", "contra", "de", "do", "da",
                   "cnpj", "empresa", "razão", "razao", "social", "nome"}


def is_company_name(texto: str) -> bool:
    """Razão social brasileira: termina (ou quase) em LTDA, EIRELI, S/A ou S.A."""
    return bool(_EMPRESA_SUFIXO.search(texto or ""))


def _host_juridico(hit: SerpHit) -> bool:
    host, path = hit.host, (urlparse(hit.url).path or "").lower()
    if host.endswith("jus.br"):
        return True
    if host.endswith("jusbrasil.com.br") or host.endswith("escavador.com"):
        # Perfil de pessoa nesses sites é conta; processo, diário e
        # jurisprudência são registro jurídico.
        return any(k in path for k in ("processo", "diario", "jurisprudencia", "/doc/"))
    return False


def extrair_empresas(texto: str) -> list[str]:
    """Razões sociais citadas num texto livre (título ou trecho de resultado)."""
    achadas: list[str] = []
    for trecho in _SEPARADORES.split(texto or ""):
        m = _EMPRESA_SUFIXO.search(trecho)
        if not m:
            continue
        nome = trecho[: m.end()].strip(" .-")
        palavras = nome.split()
        while palavras and palavras[0].lower().strip(".") in _PALAVRAS_RUIDO:
            palavras.pop(0)
        if not 2 <= len(palavras) <= 14:
            continue
        nome = " ".join(palavras)
        if nome.islower() or nome.isupper():
            nome = nome.title().replace("Ltda", "LTDA").replace("Eireli", "EIRELI")
        if nome.lower() not in {a.lower() for a in achadas}:
            achadas.append(nome)
    return achadas


def extrair_processos(texto: str) -> list[str]:
    from .cnj import validate_dv

    return [n for n in dict.fromkeys(_CNJ_RE.findall(texto or "")) if validate_dv(n)]


def extrair_cnpjs(texto: str) -> list[str]:
    from .entity import valid_cnpj

    return [c for c in dict.fromkeys(_CNPJ_RE.findall(texto or "")) if valid_cnpj(c)]


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

        texto = f"{hit.title} {hit.snippet}"
        juridico = _host_juridico(hit) or bool(extrair_processos(texto))
        platform = None if juridico else hit.platform
        if juridico:
            findings.append(
                Finding(
                    kind=FindingKind.LEGAL,
                    value=hit.title[:140] or hit.url,
                    source=f"serp:{hit.engine}",
                    source_label=f"Busca ({hit.engine})",
                    url=hit.url,
                    confidence=Confidence.LIKELY if strong else Confidence.POSSIBLE,
                    detail=hit.snippet[:300],
                    raw={"host": hit.host, "query": hit.query, "position": hit.position},
                )
            )
        elif platform:
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

        # O que vem citado junto do alvo no mesmo resultado: processo, CNPJ e
        # empresa. Só quando o alvo aparece no texto, senão é ruído da página.
        if strong:
            conf = Confidence.LIKELY
            for numero in extrair_processos(f"{texto} {hit.url}"):
                findings.append(Finding(
                    kind=FindingKind.LEGAL, value=f"Processo {numero}",
                    source=f"serp:{hit.engine}", source_label="Busca (número de processo)",
                    url=hit.url, confidence=conf,
                    detail=f"Número CNJ citado junto do alvo em: {hit.title[:80]}",
                    raw={"cnj": numero},
                ))
            for cnpj in extrair_cnpjs(texto):
                findings.append(Finding(
                    kind=FindingKind.DOCUMENT, value=cnpj,
                    source=f"serp:{hit.engine}", source_label="Busca (CNPJ citado)",
                    url=hit.url, confidence=conf,
                    detail=f"CNPJ citado junto do alvo em: {hit.title[:80]}",
                    raw={"tipo": "cnpj"},
                ))
            alvo_e_empresa = is_company_name(entity.value)
            vistas = {entity.value.lower()} if alvo_e_empresa else set()
            # Título e trecho em separado: juntos, o fim de um gruda no começo do outro.
            for empresa in extrair_empresas(hit.title) + extrair_empresas(hit.snippet):
                if empresa.lower() in vistas:
                    continue
                vistas.add(empresa.lower())
                findings.append(Finding(
                    kind=FindingKind.COMPANY, value=empresa,
                    source=f"serp:{hit.engine}", source_label="Busca (empresa citada)",
                    url=hit.url, confidence=conf,
                    detail=f"Empresa citada junto do alvo em: {hit.title[:80]}",
                    raw={"citada_em": hit.url},
                ))

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
