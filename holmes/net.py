"""
Camada HTTP e de chaves.

Um único lugar que sabe: onde estão as chaves, como fazer uma requisição
educada (timeout, retry, user-agent) e como cachear em disco. Conector
nenhum chama `requests` direto.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CACHE_DIR = Path(os.environ.get("HOLMES_CACHE_DIR", ".holmes_cache"))
DEFAULT_TTL = int(os.environ.get("HOLMES_CACHE_TTL", "86400"))  # 24h
DEFAULT_TIMEOUT = 12

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

# Nome canônico → variações aceitas no ambiente / na sidebar.
_KEY_ALIASES = {
    "serper": ("SERPER_API_KEY", "SERPER_KEY"),
    "brave": ("BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY"),
    "google_cse": ("GOOGLE_CSE_KEY", "GOOGLE_API_KEY"),
    "google_cse_cx": ("GOOGLE_CSE_CX", "GOOGLE_CX"),
    "hibp": ("HIBP_API_KEY",),
    "hunter": ("HUNTER_API_KEY",),
    "numverify": ("NUMVERIFY_API_KEY",),
    "shodan": ("SHODAN_API_KEY",),
    "ipinfo": ("IPINFO_TOKEN", "IPINFO_API_KEY"),
    "osintleak": ("OSINTLEAK_API_KEY",),
    "portal_transparencia": ("PORTAL_TRANSPARENCIA_KEY", "PORTAL_TRANSPARENCIA_API_KEY"),
    "opensanctions": ("OPENSANCTIONS_API_KEY",),
    "leakcheck": ("LEAKCHECK_API_KEY",),
    "dehashed_user": ("DEHASHED_USER", "DEHASHED_EMAIL"),
    "dehashed_key": ("DEHASHED_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
    "brightdata": ("BRIGHTDATA_API_KEY", "BRIGHT_DATA_API_KEY", "BRD_API_KEY"),
    "github": ("HOLMES_GITHUB_TOKEN",),
}

# Chaves coladas na UI nesta sessão (não persistem em disco).
_RUNTIME_KEYS: dict[str, str] = {}


def set_runtime_key(name: str, value: str | None) -> None:
    """A sidebar cola a chave aqui; vale só para o processo em execução."""
    if value and value.strip():
        _RUNTIME_KEYS[name] = value.strip()
    else:
        _RUNTIME_KEYS.pop(name, None)


def get_key(name: str) -> str | None:
    if name in _RUNTIME_KEYS:
        return _RUNTIME_KEYS[name]
    for env_name in _KEY_ALIASES.get(name, (name.upper(),)):
        val = os.environ.get(env_name, "").strip()
        if val:
            return val
    return None


def has_key(name: str) -> bool:
    return bool(get_key(name))


def key_status() -> dict[str, bool]:
    """Usado pela UI para mostrar a bolinha acesa/apagada de cada provedor."""
    return {name: has_key(name) for name in _KEY_ALIASES}


# ── cache em disco ──────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{digest}.json"


def cache_get(key: str, ttl: int = DEFAULT_TTL) -> Any | None:
    if ttl <= 0:
        return None
    path = _cache_path(key)
    try:
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > ttl:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def cache_set(key: str, value: Any) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(key).write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass  # cache é otimização, nunca motivo de falha


def cache_clear() -> int:
    removed = 0
    try:
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
            removed += 1
    except Exception:
        pass
    return removed


# ── sessão HTTP ─────────────────────────────────────────────────────────────

def build_session(retries: int = 2) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )
    return session


_SESSION = build_session()


def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    ttl: int = DEFAULT_TTL,
) -> Any | None:
    ck = f"GET:{url}:{json.dumps(params or {}, sort_keys=True)}"
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached
    resp = _SESSION.get(url, params=params, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        raise requests.HTTPError(f"HTTP {resp.status_code} em {url}", response=resp)
    data = resp.json()
    cache_set(ck, data)
    return data


def post_json(
    url: str,
    *,
    payload: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    ttl: int = DEFAULT_TTL,
) -> Any | None:
    ck = f"POST:{url}:{json.dumps(payload or {}, sort_keys=True)}"
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached
    resp = _SESSION.post(url, json=payload, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        raise requests.HTTPError(f"HTTP {resp.status_code} em {url}", response=resp)
    data = resp.json()
    cache_set(ck, data)
    return data


def get_text(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    ttl: int = DEFAULT_TTL,
) -> str | None:
    ck = f"TXT:{url}:{json.dumps(params or {}, sort_keys=True)}"
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached
    resp = _SESSION.get(url, params=params, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        return None
    cache_set(ck, resp.text)
    return resp.text


def head_status(url: str, timeout: int = 8) -> int | None:
    """Existe esse perfil? Alguns sites respondem 404 no HEAD e 200 no GET."""
    try:
        resp = _SESSION.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code in (403, 405):
            resp = _SESSION.get(url, timeout=timeout, allow_redirects=True, stream=True)
        return resp.status_code
    except Exception:
        return None


# ── GitHub: token opcional ──────────────────────────────────────────────────
#
# Sem token a API do GitHub dá 60 requisições/hora por IP; com token, 5.000.
# É o maior ganho gratuito do motor, e por isso vale um helper próprio.
#
# Cuidado deliberado com o nome da variável: `GITHUB_TOKEN` e `GH_TOKEN` são
# usadas por CI, por agentes e por proxies corporativos para guardar *outros*
# tokens. Mandar um desses para api.github.com vaza credencial de terceiro e
# ainda quebra o conector com 401. Então a variável canônica é
# HOLMES_GITHUB_TOKEN, e as genéricas só são aceitas se o valor tiver mesmo
# cara de token do GitHub.

_GITHUB_TOKEN_PREFIXES = ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_")


def github_token() -> str | None:
    explicit = get_key("github")
    if explicit:
        return explicit
    for env_name in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(env_name, "").strip()
        if val.startswith(_GITHUB_TOKEN_PREFIXES):
            return val
    return None


# Vira True no primeiro 401: token vencido, revogado ou digitado errado.
# A partir daí o processo segue sem token (60/h) em vez de falhar toda
# consulta ao GitHub até alguém notar e redeployar.
_github_token_rejected = False


def github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = github_token()
    if token and not _github_token_rejected:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_auth_state() -> str:
    """Para a UI e para o log: `sem_token`, `ativo` ou `recusado`."""
    if not github_token():
        return "sem_token"
    return "recusado" if _github_token_rejected else "ativo"


def github_get_json(url: str, *, timeout: int = DEFAULT_TIMEOUT, ttl: int = DEFAULT_TTL) -> Any | None:
    """
    GET na API do GitHub com o token, se houver. Se o GitHub recusar o token
    (401), repete a mesma chamada sem ele e desliga o token para o resto do
    processo. Um token vencido derruba a cota de 5.000/h para 60/h, mas não
    derruba o conector.
    """
    global _github_token_rejected
    try:
        return get_json(url, headers=github_headers(), timeout=timeout, ttl=ttl)
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status != 401 or _github_token_rejected or not github_token():
            raise
        _github_token_rejected = True
        print(
            "[holmes] GitHub recusou HOLMES_GITHUB_TOKEN (401: vencido, revogado "
            "ou inválido). Seguindo sem token, limite de 60 req/h. "
            "Gere um novo em github.com/settings/tokens.",
            file=sys.stderr,
            flush=True,
        )
        return get_json(url, headers=github_headers(), timeout=timeout, ttl=ttl)


# ── Bright Data Web Unlocker ────────────────────────────────────────────────
#
# Rota paga, desligada por padrão. Só entra em ação quando o alvo bloqueia de
# verdade (403/429/captcha) — nunca como caminho principal, porque cada
# requisição custa dinheiro e a esmagadora maioria das fontes do motor
# responde bem direto.
#
# Ligar:
#   export BRIGHTDATA_API_KEY=...     # a chave, nunca no código
#   export HOLMES_UNLOCKER=1          # o interruptor
#   export HOLMES_UNLOCKER_ZONE=...   # opcional (padrão: cli_unlocker)
#   export HOLMES_UNLOCKER_BUDGET=200 # teto de chamadas por processo

UNLOCKER_ENDPOINT = "https://api.brightdata.com/request"
UNLOCKER_ZONE = os.environ.get("HOLMES_UNLOCKER_ZONE", "cli_unlocker")
UNLOCKER_BUDGET = int(os.environ.get("HOLMES_UNLOCKER_BUDGET", "200"))
UNLOCKER_TIMEOUT = int(os.environ.get("HOLMES_UNLOCKER_TIMEOUT", "60"))

# Contadores do processo. O teto existe porque o crédito é finito e um laço
# mal fechado num motor que roda 90 sites em paralelo queima saldo rápido.
_unlocker_stats = {"usadas": 0, "sucesso": 0, "falha": 0, "bloqueadas_por_teto": 0}


def unlocker_enabled() -> bool:
    """Só é verdade com chave presente E interruptor ligado. Na dúvida, não gasta."""
    if os.environ.get("HOLMES_UNLOCKER", "").strip().lower() not in ("1", "true", "sim", "on"):
        return False
    return has_key("brightdata")


def unlocker_budget_left() -> int:
    return max(0, UNLOCKER_BUDGET - _unlocker_stats["usadas"])


def unlocker_stats() -> dict:
    """Usado pela UI e pelos relatórios: quanto desta investigação foi pago."""
    return dict(_unlocker_stats, teto=UNLOCKER_BUDGET, restante=unlocker_budget_left())


def unlocker_reset_stats() -> None:
    for k in ("usadas", "sucesso", "falha", "bloqueadas_por_teto"):
        _unlocker_stats[k] = 0


def unlocked_get_text(
    url: str,
    *,
    timeout: int | None = None,
    ttl: int = DEFAULT_TTL,
    country: str | None = None,
) -> str | None:
    """
    Busca a página pelo Web Unlocker da Bright Data. Devolve o HTML ou None.

    Cacheia igual ao resto da camada: repetir o mesmo alvo dentro do TTL não
    custa uma segunda requisição paga.
    """
    if not unlocker_enabled():
        return None

    ck = f"UNLOCK:{url}:{country or ''}"
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached

    if unlocker_budget_left() <= 0:
        _unlocker_stats["bloqueadas_por_teto"] += 1
        return None

    payload: dict[str, Any] = {"zone": UNLOCKER_ZONE, "url": url, "format": "raw"}
    if country:
        payload["country"] = country

    _unlocker_stats["usadas"] += 1
    try:
        resp = _SESSION.post(
            UNLOCKER_ENDPOINT,
            json=payload,
            headers={
                "Authorization": f"Bearer {get_key('brightdata')}",
                "Content-Type": "application/json",
            },
            timeout=timeout or UNLOCKER_TIMEOUT,
        )
    except Exception:
        _unlocker_stats["falha"] += 1
        return None

    if resp.status_code >= 400:
        _unlocker_stats["falha"] += 1
        return None

    _unlocker_stats["sucesso"] += 1
    cache_set(ck, resp.text)
    return resp.text
