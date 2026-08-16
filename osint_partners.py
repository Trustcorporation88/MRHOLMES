"""
Flowsint + Awesome OSINT Arsenal — o que entra no Holmes e o que não entra.

Flowsint (Apache-2.0, reconurge) é uma plataforma de grafo com enrichers.
Não cabe no Streamlit/Railway (precisa Docker + Neo4j + Postgres + Redis).
O Holmes replica o *fluxo* nos módulos nativos e aponta o produto oficial.

Awesome OSINT Arsenal (MIT, rawfilejson) lista 753 tools em 50 categorias,
incluindo red team, phishing e exploits. Neste console entra só a fatia
OSINT (username, email, domínio, leaks, GEOINT, corporativo). Sem
install.sh completo, sem redteam.sh, sem Mimikatz/Sliver/phishing.
"""

from __future__ import annotations

FLOWSINT_URL = "https://github.com/reconurge/flowsint"
FLOWSINT_SITE = "https://flowsint.io"
ARSENAL_URL = "https://github.com/rawfilejson/awesome-osint-arsenal"

# Palavras que nunca podem aparecer nas picks do Arsenal neste repo.
ARSENAL_BLOCKLIST = (
    "mimikatz",
    "sliver",
    "impacket",
    "phishing",
    "gophish",
    "nuclei",
    "metasploit",
    "hashcat",
    "hydra",
    "sqlmap",
    "exploit",
    "rat",
    "ddos",
    "bloodhound",
    "netexec",
)

# Enrichers do Flowsint → módulo Holmes (ou link oficial).
FLOWSINT_ENRICHERS = [
    {
        "id": "dns",
        "label": "DNS / WHOIS / IP",
        "detail": "Resolve domínio, registra e geolocaliza — equivalente aos enrichers Domain/IP.",
        "kind": "native",
        "page": "Domínio",
    },
    {
        "id": "subs",
        "label": "Subdomínios",
        "detail": "Enum passiva (subfinder/amass) como o enricher Subdomain Discovery.",
        "kind": "native",
        "page": "OSINT Avançado",
        "osint_tool": "subdomains",
    },
    {
        "id": "maigret",
        "label": "Username (Maigret)",
        "detail": "O mesmo enricher social do Flowsint, no chip nativo.",
        "kind": "native",
        "page": "OSINT Avançado",
        "osint_tool": "maigret",
    },
    {
        "id": "email",
        "label": "Email + Gravatar",
        "detail": "Lookup local; breaches lícitos no menu Leaks / HIBP.",
        "kind": "native",
        "page": "Email",
    },
    {
        "id": "phone",
        "label": "Telefone",
        "detail": "libphonenumber + fontes de caller-ID (não puxa dump).",
        "kind": "native",
        "page": "Telefone",
    },
    {
        "id": "leaks",
        "label": "Breaches públicos",
        "detail": "HIBP / IntelX — equivalente ao enricher Email to Breaches.",
        "kind": "native",
        "page": "Leaks",
    },
    {
        "id": "graph",
        "label": "Grafo de entidades",
        "detail": "Rascunho local. O grafo Neo4j completo é o Flowsint (Docker).",
        "kind": "native",
        "page": "Gráfico",
    },
    {
        "id": "flowsint_app",
        "label": "Abrir Flowsint (oficial)",
        "detail": "Docker local · Apache-2.0 · ethics.md no repo. Não roda dentro do Holmes.",
        "kind": "external",
        "url": FLOWSINT_URL,
    },
]

# Fatia OSINT do Arsenal que ainda não estava no catálogo Holmes.
ARSENAL_PICKS = [
    {
        "id": "blackbird",
        "name": "Blackbird",
        "url": "https://github.com/p1ngul1n0/blackbird",
        "icon": "🐦",
        "description": "Busca rápida de username em dezenas de sites.",
        "use_for": "Handle / username",
        "source": "github",
        "group": "username",
    },
    {
        "id": "social-analyzer",
        "name": "Social Analyzer",
        "url": "https://github.com/qeeqbox/social-analyzer",
        "icon": "📊",
        "description": "API/CLI de perfis públicos por username.",
        "use_for": "Username → perfil",
        "source": "github",
        "group": "username",
    },
    {
        "id": "nexfil",
        "name": "NExfil",
        "url": "https://github.com/thewhiteh4t/nexfil",
        "icon": "🔎",
        "description": "Localiza perfis a partir do handle.",
        "use_for": "Username",
        "source": "github",
        "group": "username",
    },
    {
        "id": "gitfive",
        "name": "GitFive",
        "url": "https://github.com/mxrch/GitFive",
        "icon": "🐙",
        "description": "OSINT de contas GitHub (emails, aliases, repos).",
        "use_for": "GitHub username",
        "source": "github",
        "group": "username",
    },
    {
        "id": "socid-extractor",
        "name": "socid-extractor",
        "url": "https://github.com/soxoj/socid-extractor",
        "icon": "🪪",
        "description": "Extrai IDs e metadados públicos de páginas sociais.",
        "use_for": "URL de perfil",
        "source": "github",
        "group": "username",
    },
    {
        "id": "h8mail",
        "name": "h8mail",
        "url": "https://github.com/khast3x/h8mail",
        "icon": "📬",
        "description": "Email OSINT contra bases públicas / HIBP (CLI local).",
        "use_for": "Email autorizado",
        "source": "github",
        "group": "email",
    },
    {
        "id": "ghunt",
        "name": "GHunt",
        "url": "https://github.com/mxrch/GHunt",
        "icon": "🟦",
        "description": "OSINT de contas Google a partir de email/GAIA (CLI).",
        "use_for": "Email Google",
        "source": "github",
        "group": "email",
    },
    {
        "id": "opencorporates",
        "name": "OpenCorporates",
        "url": "https://opencorporates.com/",
        "icon": "🏛️",
        "description": "Registro societário aberto (empresa → diretores/domínios).",
        "use_for": "Organização",
        "source": "web",
        "group": "corp",
    },
    {
        "id": "occrp-aleph",
        "name": "OCCRP Aleph",
        "url": "https://aleph.occrp.org/",
        "icon": "📁",
        "description": "Arquivo investigativo de pessoas, empresas e leaks jornalísticos.",
        "use_for": "Nome / empresa",
        "source": "web",
        "group": "corp",
    },
    {
        "id": "bellingcat-osm",
        "name": "Bellingcat OSM Search",
        "url": "https://osm-search.bellingcat.com/",
        "icon": "🗺️",
        "description": "GEOINT: busca em OpenStreetMap para geolocalizar fotos/vídeos.",
        "use_for": "Imagem / local",
        "source": "web",
        "group": "geoint",
    },
    {
        "id": "arsenal-index",
        "name": "Awesome OSINT Arsenal",
        "url": ARSENAL_URL,
        "icon": "📚",
        "description": "Índice 753+ tools. No Holmes só a fatia OSINT. Não rode o instalador ofensivo do repo.",
        "use_for": "Descobrir fontes oficiais",
        "source": "github",
        "group": "index",
    },
]


def arsenal_picks_are_clean() -> bool:
    blob = " ".join(
        f"{item.get('name', '')} {item.get('url', '')} {item.get('description', '')}"
        for item in ARSENAL_PICKS
    ).lower()
    tokens = set(blob.replace("/", " ").replace("-", " ").replace(".", " ").split())
    return not any(word in tokens for word in ARSENAL_BLOCKLIST)
