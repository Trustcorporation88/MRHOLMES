"""Dork Workbench — catalog load, token replace, filters, engine URLs."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import quote_plus

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_CATALOG_PATH = os.path.join(_ROOT, "data", "dork_catalog.json")

TOKEN_KEYS = (
    "TARGET_DOMAIN",
    "ORG_NAME",
    "USERNAME",
    "EMAIL",
    "IP",
    "ASN",
    "PHONE",
)

ENGINE_URLS = {
    "Google": "https://www.google.com/search?q={q}",
    "Bing": "https://www.bing.com/search?q={q}",
    "Yandex": "https://yandex.com/search/?text={q}",
    "DuckDuckGo": "https://duckduckgo.com/?q={q}",
    "GitHub": "https://github.com/search?q={q}&type=code",
    "GitLab": "https://gitlab.com/search?search={q}",
    "Shodan": "https://www.shodan.io/search?query={q}",
}

ENGINE_PORTALS = {
    "Censys": "https://search.censys.io/",
    "FOFA": "https://fofa.info/",
    "SecurityTrails": "https://securitytrails.com/",
    "PublicWWW": "https://publicwww.com/",
}

GOAL_PT = {
    "recon": "reconhecimento",
    "admin-panels": "painéis admin",
    "secrets": "segredos",
    "misconfigurations": "má configuração",
    "cloud": "nuvem",
    "data-exposure": "exposição de dados",
    "api-security": "segurança de API",
    "attack-surface": "superfície de ataque",
    "osint": "osint",
    "identity": "identidade",
    "supply-chain": "cadeia de suprimento",
    "iot": "iot",
    "asset-discovery": "descoberta de ativos",
    "application-security": "segurança de aplicação",
    "source-exposure": "exposição de código",
    "communication": "comunicação",
    "mobile": "mobile",
    "github": "github",
    "ai-security": "segurança de IA",
    "platform-security": "segurança de plataforma",
}

SOURCE_PT = {
    "webdorks": "WebDorks",
    "holmes": "Holmes",
}

TOKEN_LABELS_PT = {
    "TARGET_DOMAIN": "Domínio alvo",
    "ORG_NAME": "Organização",
    "USERNAME": "Usuário",
    "EMAIL": "Email",
    "IP": "IP",
    "ASN": "ASN",
    "PHONE": "Telefone",
}

# Title + description overrides for static WebDorks entries (id → pt)
TITLE_PT = {
    "admin-panels": ("Descoberta de painéis admin", "Localize interfaces de administração expostas em ativos públicos."),
    "env-leaks": ("Vazamento de arquivos .env", "Encontre .env e configs com segredos expostos acidentalmente."),
    "open-buckets": ("Buckets abertos", "Caçe listagens e referências a buckets de nuvem públicos."),
    "api-keys": ("Exposição de chaves de API", "Superfície de tokens, credenciais e segredos de integração."),
    "js-endpoints": ("Mineração de endpoints em JS", "Descubra rotas e endpoints internos em bundles JavaScript."),
    "graphql": ("Superfície GraphQL", "Identifique endpoints GraphQL e indícios de introspecção."),
    "debug-artifacts": ("Arquivos de debug e backup", "Encontre backups, dumps e artefatos temporários em produção."),
    "documents": ("Documentos sensíveis", "Busque docs internos com credenciais ou estratégia."),
    "login-portals": ("Portais SSO e login", "Mapeie pontos de autenticação e identidade."),
    "repo-secrets": ("Espalhamento de segredos em repos", "Correlacione atividade e credenciais vazadas em hosts de código."),
    "ci-cd": ("Exposição de CI/CD", "Detecte pipelines e credenciais em workflows."),
    "exposed-cameras": ("Câmeras e IoT expostos", "Localize painéis IoT e feeds de câmera acessíveis."),
    "subdomain-indexing": ("Inventário de subdomínios indexados", "Extraia subdomínios e hosts esquecidos indexados."),
    "email-footprints": ("Pegadas de email", "Rastreie artefatos públicos ligados a emails e funcionários."),
    "vpn-rdp": ("Portais de acesso remoto", "Identifique VPN, RDP e consoles remotos na internet."),
    "k8s-exposure": ("Exposição Kubernetes", "Procure dashboards e configs Kubernetes públicos."),
    "db-admin-panels": ("Interfaces admin de banco", "Encontre phpMyAdmin, pgAdmin e similares."),
    "paste-monitoring": ("Monitoramento de pastes e leaks", "Busque pastes e dumps com palavras da organização."),
    "network-fingerprints": ("Impressões digitais de rede", "Faça pivô por IP e ASN para descobrir ativos."),
    "swagger-openapi": ("Endpoints Swagger e OpenAPI", "Encontre docs de API que revelam rotas e schemas."),
    "open-directories": ("Índices de diretório abertos", "Detecte listagens que vazam código, backups ou logs."),
    "email-footprints": ("Pegadas de email", "Rastreie artefatos públicos de email."),
    "jira-discovery": ("Descoberta de Jira", "Localize boards e tickets Jira indexados."),
    "confluence-leaks": ("Exposição Confluence", "Encontre espaços e docs internos Confluence."),
    "kibana-panels": ("Painéis Kibana e logs", "Identifique dashboards de observabilidade abertos."),
    "grafana-panels": ("Exposição Grafana", "Descubra instâncias Grafana sem autenticação."),
    "jenkins-admin": ("Painéis Jenkins CI", "Rastreie endpoints Jenkins e metadados de build."),
    "swagger-files": ("Arquivos OpenAPI", "Caçe especificações Swagger/OpenAPI brutas."),
    "postgres-backups": ("Artefatos de backup de banco", "Busque dumps SQL/MySQL/Postgres expostos."),
    "firebase-tokens": ("Exposição Firebase", "Localize credenciais e configs Firebase."),
    "sentry-debug": ("Vazamento de DSN Sentry", "Identifique DSNs e endpoints de monitoramento."),
    "twilio-keys": ("Credenciais Twilio", "Encontre SID e tokens Twilio vazados."),
    "slack-webhooks": ("Webhooks Slack", "Detecte URLs de webhook Slack no código."),
    "discord-bot-token": ("Token de bot Discord", "Identifique tokens Discord vazados."),
    "docker-secrets": ("Segredos em Docker Compose", "Encontre variáveis e secrets em arquivos de container."),
    "terraform-secrets": ("Segredos Terraform", "Mapeie vazamentos em state/tfvars."),
    "ansible-vault": ("Chaves Ansible Vault", "Descubra senhas vault e inventários."),
    "npm-auth": ("Token autenticação NPM", "Localize vazamentos em .npmrc."),
    "pypi-token": ("Token PyPI", "Detecte tokens de publicação Python."),
    "aws-iam-keys": ("Chaves IAM AWS", "Identifique pares de access/secret keys."),
    "azure-credentials": ("Credenciais Azure", "Caçe connection strings e storage keys."),
    "gcp-service-keys": ("Service accounts GCP", "Encontre JSON de contas de serviço."),
    "rabbitmq-panels": ("Management RabbitMQ", "Localize portais RabbitMQ na internet."),
    "elastic-panels": ("Endpoints Elasticsearch", "Encontre clusters e APIs Elastic expostos."),
    "mongodb-open": ("Superfície MongoDB aberta", "Mapeie MongoDB acessível na internet."),
    "redis-open": ("Superfície Redis aberta", "Detecte nós Redis expostos."),
    "vnc-rdp-ports": ("Serviços desktop remoto", "Inventário de RDP e VNC."),
    "splunk-panels": ("Dashboards Splunk", "Encontre interfaces Splunk acessíveis."),
    "wordpress-debug": ("Debug WordPress", "Encontre wp-config e debug.log."),
    "laravel-debug": ("Debug Laravel", "Localize páginas Whoops e APP_DEBUG."),
    "spring-actuator": ("Actuator Spring", "Descubra endpoints /actuator expostos."),
    "phpinfo-files": ("Exposição phpinfo", "Identifique páginas phpinfo."),
    "git-metadata": ("Metadados Git", "Encontre diretórios .git acessíveis."),
    "svn-metadata": ("Metadados SVN", "Detecte pastas .svn expostas."),
    "gitlab-instance-search": ("GitLab self-hosted", "Enumere instâncias GitLab próprias."),
    "dev-portals": ("Portais de desenvolvedor", "Mapeie hubs e docs de API."),
    "status-pages": ("Páginas de status", "Localize status pages e incidentes."),
    "okta-login-surfaces": ("Superfície Okta", "Identifique portais Okta de login."),
    "vpn-vendor-portals": ("VPN de fornecedores", "Descubra portais AnyConnect/Pulse/GlobalProtect."),
    "kibana-devtools": ("Dev Tools Kibana", "Busque consoles Kibana abertos."),
    "adminer-exposure": ("Interface Adminer", "Localize login Adminer público."),
    "prometheus-metrics": ("Métricas Prometheus", "Encontre /metrics abertos."),
    "swagger-ui-cdn": ("Swagger UI", "Rastreie exploradores Swagger hospedados."),
    "backup-config-files": ("Backups de config", "Caçe .bak/.old de configuração."),
    "oauth-clients": ("Segredos OAuth", "Identifique client_secret vazados."),
    "private-key-hunt": ("Caça a chaves privadas", "Busque PEM/PPK e material criptográfico."),
    "jwt-secret-hunt": ("Segredo JWT", "Encontre signing secrets JWT."),
    "stripe-secret-hunt": ("Chave secreta Stripe", "Localize sk_live_ e webhooks."),
    "sendgrid-key-hunt": ("API Key SendGrid", "Detecte tokens SendGrid."),
    "mailgun-key-hunt": ("Credenciais Mailgun", "Encontre API keys Mailgun."),
    "digitalocean-token-hunt": ("Token DigitalOcean", "Identifique tokens DO vazados."),
    "vercel-token-hunt": ("Token Vercel", "Descubra tokens de deploy Vercel."),
    "netlify-token-hunt": ("Token Netlify", "Encontre auth tokens Netlify."),
    "cloudflare-token-hunt": ("Credenciais Cloudflare", "Localize API tokens Cloudflare."),
    "zendesk-keys": ("Token Zendesk", "Detecte API tokens Zendesk."),
    "intercom-keys": ("Chave Intercom", "Caçe API keys Intercom."),
    "algolia-keys": ("Admin key Algolia", "Localize credenciais Algolia."),
    "github-pat-leaks": ("PAT GitHub vazado", "Busque padrões ghp_/github_pat_."),
    "github-actions-secrets": ("Secrets no GitHub Actions", "Caçe workflows que ecoam segredos."),
    "github-codeowners-surface": ("CODEOWNERS GitHub", "Mapeie ownership de código crítico."),
    "github-release-artifacts": ("Artefatos de release", "Inspecione releases com debug/secrets."),
    "github-container-registry": ("GHCR", "Rastreie metadados de containers."),
    "github-discussions-leaks": ("Leaks em discussions", "Encontre segredos em issues/PRs."),
    "github-gist-leaks": ("Leaks em Gists", "Descubra gists públicos com tokens."),
    "github-npmrc-leaks": ("NPMRC no GitHub", "Encontre _authToken em repos."),
    "github-dockerhub-creds": ("Credenciais Docker no GitHub", "Localize docker login em CI."),
    "github-cicd-misconfig": ("Má config CI GitHub", "Detecte padrões perigosos em workflows."),
    "mongo-uri-leaks": ("URI MongoDB", "Encontre connection strings com senha."),
    "postgres-uri-leaks": ("URI Postgres", "Descubra DSNs PostgreSQL com senha."),
    "ssh-config-leaks": ("Config SSH e histórico", "Encontre .ssh/config e bash_history."),
    "openai-api-key-exposure": ("Chave API OpenAI", "Identifique keys OpenAI em código e logs."),
    "llm-prompt-leaks": ("Vazamento de prompts LLM", "Encontre system prompts hardcoded."),
    "rag-index-exposure": ("Índices RAG expostos", "Detecte stores vetoriais públicos."),
    "langchain-secrets": ("Segredos LangChain", "Busque projects LangChain com keys."),
    "llamaindex-leaks": ("Keys LlamaIndex", "Localize vazamentos LlamaIndex."),
    "gradio-streamlit-admin": ("Admin Gradio/Streamlit", "Descubra demos AI e debug públicos."),
    "ollama-endpoints": ("Endpoints Ollama", "Encontre APIs Ollama expostas."),
    "vllm-endpoints": ("API vLLM", "Localize servidores vLLM públicos."),
    "mcp-server-exposure": ("Servidor MCP", "Busque configs Model Context Protocol."),
    "agent-memory-leaks": ("Memória de agentes", "Encontre dumps e logs de conversa."),
    "prompt-injection-test-surface": ("Superfície prompt injection", "Mapeie endpoints vulneráveis a injeção."),
    "embedding-key-exposure": ("Keys de embedding", "Rastreie tokens de serviços vetoriais."),
}

_PATTERNS_TITLE = [
    (re.compile(r"^(.+) Credential Exposure$", re.I), r"Exposição de credenciais · \1"),
    (re.compile(r"^(.+) Secret And Config Hunt$", re.I), r"Caça a segredos e config · \1"),
    (re.compile(r"^(.+) Secret Exposure$", re.I), r"Exposição de segredos · \1"),
    (re.compile(r"^(.+) Key Leakage$", re.I), r"Vazamento de chave · \1"),
    (re.compile(r"^(.+) Token Exposure$", re.I), r"Exposição de token · \1"),
    (re.compile(r"^(.+) Credential Leakage$", re.I), r"Vazamento de credenciais · \1"),
    (re.compile(r"^Holmes Classic — (.+)$", re.I), r"Holmes clássico — \1"),
]

_PATTERNS_DESC = [
    (re.compile(r"^Discover leaked (.+) credentials and integration secrets\.$", re.I),
     r"Descubra credenciais e segredos de integração \1 vazados."),
    (re.compile(r"^Inspect (.+) projects for prompt/config leaks and hardcoded keys\.$", re.I),
     r"Inspecione projetos \1 em busca de vazamentos de prompt/config e chaves."),
    (re.compile(r"^Find leaked (.+) secrets, tokens, and config artifacts\.$", re.I),
     r"Encontre segredos, tokens e artefatos de config \1 vazados."),
    (re.compile(r"^Phone-oriented (.+)$", re.I), r"Dorks de telefone · \1"),
    (re.compile(r"^Email (.+)$", re.I), r"Dorks de email · \1"),
    (re.compile(r"^Username (.+)$", re.I), r"Dorks de usuário · \1"),
    (re.compile(r"^Website (.+)$", re.I), r"Dorks de site · \1"),
    (re.compile(r"^General (.+)$", re.I), r"Dorks gerais · \1"),
    (re.compile(r"^Extra (.+)$", re.I), r"Extras · \1"),
]

# Site_lists → contextual token for {}
_HOLMES_SOURCES = [
    ("Site_lists/Dorks/Google_dorks.txt", "Google", "TARGET_DOMAIN", "holmes-general-google",
     "Holmes clássico — Google geral", "Dorks gerais Google das listas Site_lists do Mr.Holmes.",
     ["osint", "recon"]),
    ("Site_lists/Dorks/Yandex_dorks.txt", "Yandex", "TARGET_DOMAIN", "holmes-general-yandex",
     "Holmes clássico — Yandex geral", "Dorks gerais Yandex das listas Site_lists do Mr.Holmes.",
     ["osint", "recon"]),
    ("Site_lists/Phone/Google_dorks.txt", "Google", "PHONE", "holmes-phone-google",
     "Holmes clássico — Telefone Google", "Dorks de telefone no Google ({} → PHONE).",
     ["osint", "identity"]),
    ("Site_lists/Phone/Yandex_dorks.txt", "Yandex", "PHONE", "holmes-phone-yandex",
     "Holmes clássico — Telefone Yandex", "Dorks de telefone no Yandex ({} → PHONE).",
     ["osint", "identity"]),
    ("Site_lists/E-Mail/Google_dorks.txt", "Google", "EMAIL", "holmes-email-google",
     "Holmes clássico — Email Google", "Dorks de email no Google ({} → EMAIL).",
     ["osint", "identity"]),
    ("Site_lists/E-Mail/Yandex_dorks.txt", "Yandex", "EMAIL", "holmes-email-yandex",
     "Holmes clássico — Email Yandex", "Dorks de email no Yandex ({} → EMAIL).",
     ["osint", "identity"]),
    ("Site_lists/Username/Google_dorks.txt", "Google", "USERNAME", "holmes-user-google",
     "Holmes clássico — Usuário Google", "Dorks de username no Google ({} → USERNAME).",
     ["osint", "identity"]),
    ("Site_lists/Username/Yandex_dorks.txt", "Yandex", "USERNAME", "holmes-user-yandex",
     "Holmes clássico — Usuário Yandex", "Dorks de username no Yandex ({} → USERNAME).",
     ["osint", "identity"]),
    ("Site_lists/Websites/Google_dorks.txt", "Google", "TARGET_DOMAIN", "holmes-web-google",
     "Holmes clássico — Site Google", "Dorks de website no Google ({} → TARGET_DOMAIN).",
     ["osint", "asset-discovery"]),
    ("Site_lists/Websites/Yandex_dorks.txt", "Yandex", "TARGET_DOMAIN", "holmes-web-yandex",
     "Holmes clássico — Site Yandex", "Dorks de website no Yandex ({} → TARGET_DOMAIN).",
     ["osint", "asset-discovery"]),
    ("Site_lists/Dorks/Websites/Google_dorks.txt", "Google", "TARGET_DOMAIN", "holmes-dorks-web-google",
     "Holmes clássico — Dorks/Sites Google", "Dorks extras de website (Google).",
     ["osint", "recon"]),
    ("Site_lists/Dorks/Websites/Yandex_dorks.txt", "Yandex", "TARGET_DOMAIN", "holmes-dorks-web-yandex",
     "Holmes clássico — Dorks/Sites Yandex", "Dorks extras de website (Yandex).",
     ["osint", "recon"]),
    ("Site_lists/Dorks/Usernames/Google_dorks.txt", "Google", "USERNAME", "holmes-dorks-user-google",
     "Holmes clássico — Dorks/Usuários Google", "Dorks de username (pacote Dorks).",
     ["osint", "identity"]),
    ("Site_lists/Dorks/Usernames/Yandex_dorks.txt", "Yandex", "USERNAME", "holmes-dorks-user-yandex",
     "Holmes clássico — Dorks/Usuários Yandex", "Dorks de username (pacote Dorks).",
     ["osint", "identity"]),
    ("Site_lists/Dorks/Phone/Google_dorks.txt", "Google", "PHONE", "holmes-dorks-phone-google",
     "Holmes clássico — Dorks/Telefone Google", "Dorks de telefone (pacote Dorks).",
     ["osint", "identity"]),
    ("Site_lists/Dorks/Phone/Yandex_dorks.txt", "Yandex", "PHONE", "holmes-dorks-phone-yandex",
     "Holmes clássico — Dorks/Telefone Yandex", "Dorks de telefone (pacote Dorks).",
     ["osint", "identity"]),
]


def empty_tokens() -> dict[str, str]:
    return {k: "" for k in TOKEN_KEYS}


def apply_tokens(query: str, tokens: dict[str, str] | None) -> str:
    """Replace TOKEN placeholders; keep token name when value is empty."""
    out = query
    tokens = tokens or {}
    for key in TOKEN_KEYS:
        val = (tokens.get(key) or "").strip()
        if val:
            out = out.replace(key, val)
    return out


def build_search_url(engine: str, query: str, is_full_url: bool = False) -> str | None:
    """Return a clickable search URL, or portal homepage when direct search is unavailable."""
    if is_full_url and query.startswith("http"):
        return query
    encoded = quote_plus(query)
    tmpl = ENGINE_URLS.get(engine)
    if tmpl:
        return tmpl.format(q=encoded)
    return ENGINE_PORTALS.get(engine)


def humanize_goal(goal: str) -> str:
    return GOAL_PT.get(goal, goal.replace("-", " "))


def source_label(source: str) -> str:
    return SOURCE_PT.get(source or "", source or "")


def localize_technique(tech: dict[str, Any]) -> dict[str, str]:
    """Return Portuguese title/description for display (fallbacks to EN patterns)."""
    tid = tech.get("id") or ""
    title = tech.get("title") or ""
    desc = tech.get("description") or ""
    if tid in TITLE_PT:
        return {"title": TITLE_PT[tid][0], "description": TITLE_PT[tid][1]}
    for pat, repl in _PATTERNS_TITLE:
        m = pat.match(title)
        if m:
            title = pat.sub(repl, title)
            break
    for pat, repl in _PATTERNS_DESC:
        m = pat.match(desc)
        if m:
            desc = pat.sub(repl, desc)
            break
    # Section titles from Holmes Site_lists often remain EN in flush(); localize base words
    title = title.replace(" — General", " — Geral").replace(" — Image", " — Imagem")
    return {"title": title, "description": desc}


def list_engines(techniques: list[dict[str, Any]]) -> list[str]:
    engines: set[str] = set()
    for t in techniques:
        for q in t.get("queries") or []:
            engines.add(q.get("engine", ""))
    return sorted(e for e in engines if e)


def list_goals(techniques: list[dict[str, Any]]) -> list[str]:
    goals: set[str] = set()
    for t in techniques:
        for g in t.get("goals") or []:
            goals.add(g)
    return sorted(goals)


def filter_techniques(
    catalog: list[dict[str, Any]],
    search: str = "",
    engines: list[str] | None = None,
    goals: list[str] | None = None,
    letter: str | None = None,
) -> list[dict[str, Any]]:
    text = (search or "").strip().lower()
    engines = engines or []
    goals = goals or []
    letter = (letter or "").strip().upper() or None
    out: list[dict[str, Any]] = []
    for item in catalog:
        loc = localize_technique(item)
        title = loc.get("title") or item.get("title") or ""
        if letter and not title.upper().startswith(letter):
            continue
        item_engines = [q.get("engine", "") for q in item.get("queries") or []]
        item_goals = item.get("goals") or []
        if engines and not any(e in item_engines for e in engines):
            continue
        if goals and not any(g in item_goals for g in goals):
            continue
        if text:
            hay = " ".join(
                [
                    loc["title"],
                    loc["description"],
                    item.get("title") or "",
                    item.get("description") or "",
                    " ".join(humanize_goal(g) for g in item_goals),
                    " ".join(item_goals),
                    " ".join(f"{q.get('engine', '')} {q.get('q', '')}" for q in item.get("queries") or []),
                ]
            ).lower()
            if text not in hay:
                continue
        out.append(item)
    return out


def _parse_site_list_file(
    path: str,
    engine: str,
    token: str,
    tech_id: str,
    title: str,
    description: str,
    goals: list[str],
) -> list[dict[str, Any]]:
    """Parse Holmes | URL lines; group by [SECTION] into techniques."""
    if not os.path.isfile(path):
        return []
    techniques: list[dict[str, Any]] = []
    section = "GENERAL"
    queries: list[dict[str, Any]] = []

    def flush():
        nonlocal queries, section
        if not queries:
            return
        sid = f"{tech_id}-{re.sub(r'[^a-z0-9]+', '-', section.lower()).strip('-')}"
        techniques.append(
            {
                "id": sid,
                "title": f"{title} — {section.replace('-', ' ').title()}",
                "description": description,
                "goals": list(goals),
                "source": "holmes",
                "queries": queries,
            }
        )
        queries = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or set(line) <= {"-", "|", " "}:
                continue
            m = re.match(r"^\[([^\]]+)\]:?\s*$", line)
            if m:
                flush()
                section = m.group(1).replace("-DORKS", "").replace("_", "-")
                continue
            # "| https://..." or bare URL
            url = line.lstrip("|").strip()
            if not url.startswith("http"):
                continue
            # Replace {} with token name so apply_tokens works later
            url = url.replace("{}", token)
            queries.append({"engine": engine, "q": url, "is_full_url": True})
    flush()
    return techniques


def parse_site_lists(root: str | None = None) -> list[dict[str, Any]]:
    root = root or _ROOT
    all_tech: list[dict[str, Any]] = []
    for rel, engine, token, tid, title, desc, goals in _HOLMES_SOURCES:
        path = os.path.join(root, *rel.split("/"))
        all_tech.extend(_parse_site_list_file(path, engine, token, tid, title, desc, goals))
    return all_tech


def load_catalog(include_holmes: bool = True) -> list[dict[str, Any]]:
    """Load static WebDorks JSON and optionally merge Holmes Site_lists techniques."""
    techniques: list[dict[str, Any]] = []
    if os.path.isfile(_CATALOG_PATH):
        with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            techniques = data
        elif isinstance(data, dict):
            techniques = list(data.get("techniques") or data.get("webdorks") or [])
    if include_holmes:
        existing_ids = {t.get("id") for t in techniques}
        for t in parse_site_lists():
            if t.get("id") not in existing_ids:
                techniques.append(t)
    return techniques


def resolve_queries(
    technique: dict[str, Any],
    tokens: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Apply tokens and attach search URLs for each query in a technique."""
    rows = []
    for q in technique.get("queries") or []:
        raw = q.get("q") or ""
        is_full = bool(q.get("is_full_url"))
        text = apply_tokens(raw, tokens)
        url = build_search_url(q.get("engine", ""), text, is_full_url=is_full)
        rows.append(
            {
                "engine": q.get("engine", ""),
                "q": text,
                "url": url,
                "is_full_url": is_full,
                "portal_only": url is not None and q.get("engine") in ENGINE_PORTALS and not is_full,
            }
        )
    return rows
