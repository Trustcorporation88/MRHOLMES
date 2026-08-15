"""
OSINT Premium — hub + ferramentas embutidas no Mr.Holmes.

Robin roda in-process (MIT © Apurv Singh Gautam). Suites nativas
abrem o módulo Holmes. Serviços comerciais continuam no site oficial.
"""

from __future__ import annotations

from typing import Iterable

from external_services import get_all_categories, get_all_services_flat

# page_id precisa coincidir com NAV_OPTIONS em web_app.py
NATIVE_SUITES = [
    {
        "id": "robin",
        "page": "OSINT Premium",
        "icon": "🕵️",
        "title": "Robin",
        "blurb": "Briefing dark web no console: busca, filtro, scrape e relatório.",
        "kind": "tool",
        "premium_view": "robin",
    },
    {
        "id": "telefone",
        "page": "Telefone",
        "icon": "📱",
        "title": "Telefone",
        "blurb": "libphonenumber, DDD BR e fontes de caller-ID.",
        "kind": "lookup",
    },
    {
        "id": "email",
        "page": "Email",
        "icon": "✉️",
        "title": "Email",
        "blurb": "Formato, MX, Gravatar e menções em pastes.",
        "kind": "lookup",
    },
    {
        "id": "dominio",
        "page": "Domínio",
        "icon": "🌐",
        "title": "Domínio",
        "blurb": "IP, GeoIP, DNS, headers e atalhos ViewDNS.",
        "kind": "lookup",
    },
    {
        "id": "dorks",
        "page": "Dorks",
        "icon": "🔎",
        "title": "Dorks Google",
        "blurb": "Workbench com tokens e catálogo curado.",
        "kind": "lookup",
    },
    {
        "id": "username",
        "page": "OSINT Avançado",
        "icon": "👤",
        "title": "Username / Social",
        "blurb": "Holehe, Maigret, theHarvester, subdomínios, httpx.",
        "kind": "analise",
        "osint_tool": "maigret",
    },
    {
        "id": "leaks",
        "page": "Leaks",
        "icon": "🔓",
        "title": "Leaks",
        "blurb": "HIBP, pastes e atalho para dashboards externos.",
        "kind": "analise",
    },
    {
        "id": "rede",
        "page": "Rede",
        "icon": "🛰️",
        "title": "Rede / IP",
        "blurb": "Ping, portas, reverso e hospedagem.",
        "kind": "analise",
    },
    {
        "id": "grafo",
        "page": "Gráfico",
        "icon": "🕸️",
        "title": "Grafo",
        "blurb": "Link analysis entre entidades da investigação.",
        "kind": "analise",
    },
    {
        "id": "catalogo_gh",
        "page": "Ferramentas",
        "icon": "🧰",
        "title": "Catálogo GitHub",
        "blurb": "Tools CLI/recon com link oficial — sem install automático.",
        "kind": "catalogo",
    },
    {
        "id": "catalogo_web",
        "page": "Serviços Externos",
        "icon": "🔗",
        "title": "Links web",
        "blurb": "Fontes por categoria (Web + GitHub).",
        "kind": "catalogo",
    },
    {
        "id": "aprenda",
        "page": "Aprenda",
        "icon": "📚",
        "title": "Aprenda",
        "blurb": "Referências de estudo e produtividade.",
        "kind": "catalogo",
    },
]

FEATURED = [
    {
        "id": "robin",
        "name": "Robin",
        "icon": "🕵️",
        "tier": "Destaque",
        "tagline": "Ferramenta embutida: query → busca → scrape → dossiê nesta tela.",
        "delivers": [
            "Query refinada pelo modelo (máx. 5 palavras)",
            "Motores .onion via Tor + Ahmia clearnet se o proxy cair",
            "Filtro de relevância e scrape de texto",
            "Relatório Markdown (artefatos, insights, próximos passos)",
            "JSON em investigations/ + chat de follow-up + pivôs",
        ],
        "complements": "Holmes cobre clear web. Robin cobre o briefing .onion no mesmo console.",
        "requires": "Opcional: Tor :9050 e chave de LLM / Ollama. Sem isso, busca Ahmia + relatório heurístico.",
        "license": "MIT",
        "author": "Apurv Singh Gautam",
        "url": "https://github.com/apurvsinghgautam/robin",
        "docs": "https://github.com/apurvsinghgautam/robin#readme",
        "source": "github",
        "in_app": True,
        "premium_view": "robin",
        "tags": ["darkweb", "llm", "relatorio", "tor"],
    },
    {
        "id": "spiderfoot",
        "name": "SpiderFoot",
        "icon": "🕷️",
        "tier": "Suite",
        "tagline": "Recon automatizado pesado — serviço separado.",
        "delivers": ["Módulos de fontes abertas", "UI local", "Varredura por alvo"],
        "complements": "Atalho já existe em Username / Social.",
        "requires": "Instalação local; não sobe junto com o Streamlit.",
        "license": "MIT",
        "author": "Steve Micallef",
        "url": "https://github.com/smicallef/spiderfoot",
        "docs": "https://www.spiderfoot.net/documentation/",
        "source": "github",
        "native_page": "OSINT Avançado",
        "osint_tool": "spiderfoot",
        "tags": ["recon", "automacao"],
    },
    {
        "id": "maltego",
        "name": "Maltego",
        "icon": "🧭",
        "tier": "Suite",
        "tagline": "Grafo profissional de relacionamentos.",
        "delivers": ["Transforms", "Link analysis", "Export de caso"],
        "complements": "O menu Grafo do Holmes é o rascunho local; Maltego é o desktop.",
        "requires": "Conta no produto oficial.",
        "license": "Proprietário (Community disponível)",
        "author": "Maltego Technologies",
        "url": "https://www.maltego.com/",
        "docs": "https://docs.maltego.com/",
        "source": "web",
        "native_page": "Gráfico",
        "tags": ["grafo", "pessoas", "dominio"],
    },
    {
        "id": "osintleak",
        "name": "OSINT Leak",
        "icon": "🧾",
        "tier": "Conta externa",
        "tagline": "Dashboard de breaches — sem import automático.",
        "delivers": ["Busca em dumps (conta)", "Similar search", "Monitoramento pago"],
        "complements": "Holmes não puxa stealer logs. Use o menu Leaks e cole a query.",
        "requires": "Conta no serviço. Planos pagos para volume.",
        "license": "Serviço comercial",
        "author": "OSINT Leak",
        "url": "https://app.osintleak.com/dashboard/search",
        "docs": "https://app.osintleak.com/",
        "source": "web",
        "native_page": "Leaks",
        "tags": ["leaks", "email", "breaches"],
    },
    {
        "id": "intelx",
        "name": "Intelligence X",
        "icon": "🗄️",
        "tier": "Fonte",
        "tagline": "Search engine de arquivos e leaks públicos.",
        "delivers": ["Seletores (email, domínio, CIDR)", "Histórico de pastes"],
        "complements": "Fecha o ciclo Email → Leaks sem sair do fluxo Premium.",
        "requires": "Conta para volume; busca limitada no free.",
        "license": "Serviço web",
        "author": "Intelligence X",
        "url": "https://intelx.io/",
        "docs": "https://intelx.io/",
        "source": "web",
        "native_page": "Leaks",
        "tags": ["leaks", "email", "dominio"],
    },
    {
        "id": "shodan",
        "name": "Shodan",
        "icon": "🛰️",
        "tier": "Fonte",
        "tagline": "Hosts e banners expostos na internet clara.",
        "delivers": ["IP / porta / produto", "Filtros de banner"],
        "complements": "Use depois do lookup de Domínio / Rede.",
        "requires": "Conta para API; UI web tem cota.",
        "license": "Serviço web",
        "author": "Shodan",
        "url": "https://www.shodan.io/",
        "docs": "https://help.shodan.io/",
        "source": "web",
        "native_page": "Domínio",
        "tags": ["infra", "ip", "banner"],
    },
]

PLAYBOOKS = [
    {
        "id": "pessoa",
        "title": "Pessoa / username",
        "icon": "👤",
        "goal": "Montar footprint público de um handle ou nome — fontes abertas, alvo autorizado.",
        "steps": [
            {
                "label": "Username em redes (Maigret)",
                "detail": "Módulo nativo · Username / Social",
                "kind": "native",
                "page": "OSINT Avançado",
                "osint_tool": "maigret",
            },
            {
                "label": "Email → contas públicas (Holehe)",
                "detail": "Mesma suite, chip Holehe",
                "kind": "native",
                "page": "OSINT Avançado",
                "osint_tool": "holehe",
            },
            {
                "label": "Sherlock (repo oficial)",
                "detail": "Fallback CLI se Maigret não estiver instalado",
                "kind": "external",
                "url": "https://github.com/sherlock-project/sherlock",
            },
            {
                "label": "Grafo de entidades",
                "detail": "Ligar handle, email e sites encontrados",
                "kind": "native",
                "page": "Gráfico",
            },
        ],
    },
    {
        "id": "telefone",
        "title": "Telefone",
        "icon": "📱",
        "goal": "Validar o número localmente e só então abrir fontes de reputação / caller-ID.",
        "steps": [
            {
                "label": "Analisar número (DDD / tipo)",
                "detail": "Consulta local — não chama bases pagas",
                "kind": "native",
                "page": "Telefone",
            },
            {
                "label": "PhoneInfoga (oficial)",
                "detail": "Framework OSINT de números",
                "kind": "external",
                "url": "https://github.com/sundowndev/phoneinfoga",
            },
            {
                "label": "Dorks com token PHONE",
                "detail": "Prefill a partir do lookup",
                "kind": "native",
                "page": "Dorks",
            },
        ],
    },
    {
        "id": "email",
        "title": "Email e exposição",
        "icon": "✉️",
        "goal": "Validar o endereço, ver contas públicas e checar breaches lícitos.",
        "steps": [
            {
                "label": "Lookup de email",
                "detail": "MX, Gravatar, formato",
                "kind": "native",
                "page": "Email",
            },
            {
                "label": "Holehe",
                "detail": "Onde o email tem conta pública",
                "kind": "native",
                "page": "OSINT Avançado",
                "osint_tool": "holehe",
            },
            {
                "label": "Have I Been Pwned",
                "detail": "Breaches públicos por email",
                "kind": "external",
                "url": "https://haveibeenpwned.com/",
            },
            {
                "label": "Menu Leaks",
                "detail": "Pastes + atalho OSINT Leak (sem import automático)",
                "kind": "native",
                "page": "Leaks",
            },
        ],
    },
    {
        "id": "dominio",
        "title": "Domínio / infra",
        "icon": "🌐",
        "goal": "Mapear superfície pública: DNS, hosts vivos, certificados.",
        "steps": [
            {
                "label": "Lookup de domínio",
                "detail": "IP, DNS, headers",
                "kind": "native",
                "page": "Domínio",
            },
            {
                "label": "Subdomínios + httpx",
                "detail": "Suite Username / Social",
                "kind": "native",
                "page": "OSINT Avançado",
                "osint_tool": "subdomains",
            },
            {
                "label": "crt.sh / Shodan",
                "detail": "CT logs e banners — contas oficiais",
                "kind": "external",
                "url": "https://crt.sh/",
            },
            {
                "label": "Rede / IP",
                "detail": "Ping, reverso, hospedagem",
                "kind": "native",
                "page": "Rede",
            },
        ],
    },
    {
        "id": "darkweb",
        "title": "Briefing dark web (Robin)",
        "icon": "🕵️",
        "goal": "Rodar o Robin aqui no console e só então ligar artefatos no Grafo.",
        "steps": [
            {
                "label": "Fechar o caso na clear web",
                "detail": "Email, leaks públicos e domínio primeiro",
                "kind": "native",
                "page": "Leaks",
            },
            {
                "label": "Investigar com Robin",
                "detail": "Ferramenta embutida nesta página",
                "kind": "tool",
                "premium_view": "robin",
            },
            {
                "label": "Trazer artefatos validados para o Grafo",
                "detail": "Sem colar dumps crus",
                "kind": "native",
                "page": "Gráfico",
            },
        ],
    },
]


def _blob(parts: Iterable[str]) -> str:
    return " ".join(p for p in parts if p).lower()


def search_native(query: str = "", kind: str | None = None) -> list[dict]:
    q = (query or "").strip().lower()
    out = []
    for item in NATIVE_SUITES:
        if kind and item.get("kind") != kind:
            continue
        text = _blob([item["title"], item["blurb"], item["page"], item["id"]])
        if not q or q in text:
            out.append(item)
    return out


def search_featured(query: str = "") -> list[dict]:
    q = (query or "").strip().lower()
    out = []
    for item in FEATURED:
        text = _blob(
            [
                item["name"],
                item["tagline"],
                item.get("complements", ""),
                " ".join(item.get("tags") or []),
                " ".join(item.get("delivers") or []),
            ]
        )
        if not q or q in text:
            out.append(item)
    return out


def search_catalog(query: str = "", category: str | None = None) -> list[dict]:
    q = (query or "").strip().lower()
    want_cat = (category or "").strip().lower() or None
    out = []
    for item in get_all_services_flat():
        if want_cat and item.get("category_key") != want_cat:
            continue
        text = _blob(
            [
                item.get("name", ""),
                item.get("description", ""),
                item.get("use_for", ""),
                item.get("category_label", ""),
                item.get("id", ""),
            ]
        )
        if not q or q in text:
            out.append(item)
    return out


def premium_stats() -> dict:
    cats = get_all_categories()
    return {
        "native": len(NATIVE_SUITES),
        "featured": len(FEATURED),
        "playbooks": len(PLAYBOOKS),
        "catalog": len(get_all_services_flat()),
        "categories": len(cats),
    }
