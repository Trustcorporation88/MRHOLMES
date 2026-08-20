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
