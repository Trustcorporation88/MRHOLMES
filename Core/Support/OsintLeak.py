"""Official OSINT Leak API client (no dashboard scrape).

Docs: https://docs.osintleak.com/api/search
Requires OSINTLEAK_API_KEY from the user's paid plan (Railway Variables).
Default: stealerlogs=false. Passwords and similar secrets are stripped
before anything reaches the UI.
"""

from __future__ import annotations

import os
import re
from typing import Optional

import requests

SEARCH_URL = "https://osintleak.com/api/v1/search_api/"
DOCS_URL = "https://docs.osintleak.com/api/search"
DASH_URL = "https://app.osintleak.com/dashboard/search"
ALLOWED_TYPES = (
    "email",
    "username",
    "phone",
    "name",
    "url",
    "ip",
    "domain",
)
_TYPE_ALIAS = {"domain": "url"}
_SECRET_KEY = re.compile(
    r"(pass|pwd|secret|token|cookie|hash|cc_number|cvv|ssn|autofill_value|logname)",
    re.I,
)
_SAFE_KEYS = (
    "email",
    "username",
    "name",
    "first_name",
    "last_name",
    "phone",
    "url",
    "ip",
    "domain",
    "date",
    "created",
    "source",
    "leak",
    "database",
    "country",
    "title",
    "site",
    "type",
)
_UA = {"User-Agent": "MrHolmes-OSINT/1.0 (educational; authorized targets)"}


def configured(extra: str | None = None) -> bool:
    return bool(_key(extra))


def _key(extra: str | None = None) -> str:
    for value in (
        extra,
        os.environ.get("OSINTLEAK_API_KEY"),
        os.environ.get("OSINT_LEAK_API_KEY"),
    ):
        if value and str(value).strip() and "your_api_key" not in str(value).lower():
            return str(value).strip()
    return ""


def apply_session_key(value: str | None) -> None:
    cleaned = (value or "").strip()
    if cleaned:
        os.environ["OSINTLEAK_API_KEY"] = cleaned


def redact_record(item) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    out = {}
    for key, value in item.items():
        name = str(key)
        if _SECRET_KEY.search(name):
            continue
        if isinstance(value, (dict, list)):
            continue
        text = str(value).strip()
        if not text or text.lower() in ("none", "null"):
            continue
        if _SECRET_KEY.search(text) and name.lower() not in _SAFE_KEYS:
            continue
        if name.lower() in _SAFE_KEYS or len(out) < 8:
            out[name] = text[:160]
    return out or None


def search(
    query: str,
    kind: str = "username",
    page_size: int = 10,
    api_key: str | None = None,
) -> dict:
    q = (query or "").strip()
    mapped = _TYPE_ALIAS.get((kind or "").strip().lower(), (kind or "").strip().lower())
    if not q:
        return {"ok": False, "error": "Consulta vazia", "hits": [], "count": 0}
    if mapped not in ALLOWED_TYPES and mapped != "url":
        return {
            "ok": False,
            "error": f"Tipo não suportado no Holmes: {kind}",
            "hits": [],
            "count": 0,
        }
    key = _key(api_key)
    if not key:
        return {
            "ok": False,
            "error": "OSINTLEAK_API_KEY ausente. Cole no Railway (Variables) e faça Redeploy.",
            "hits": [],
            "count": 0,
            "needs_key": True,
            "dash": DASH_URL,
        }

    params = {
        "api_key": key,
        "query": q,
        "type": mapped,
        "stealerlogs": "false",
        "dbleaks": "true",
        "dbleaks2": "true",
        "search_option": "quick",
        "page": 1,
        "page_size": max(1, min(int(page_size), 20)),
        "meta": "false",
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, headers=_UA, timeout=40)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "hits": [], "count": 0}

    try:
        payload = resp.json()
    except Exception:
        payload = {}

    if resp.status_code == 403:
        msg = (payload.get("message") if isinstance(payload, dict) else None) or "Acesso negado (quota, IP whitelist ou assinatura)."
        return {"ok": False, "error": str(msg)[:220], "hits": [], "count": 0, "status_code": 403}
    if resp.status_code >= 400:
        msg = (payload.get("message") if isinstance(payload, dict) else None) or f"HTTP {resp.status_code}"
        return {"ok": False, "error": str(msg)[:220], "hits": [], "count": 0, "status_code": resp.status_code}

    if not isinstance(payload, dict) or payload.get("status") == "error":
        msg = (payload.get("message") if isinstance(payload, dict) else None) or "Resposta inválida da API"
        return {"ok": False, "error": str(msg)[:220], "hits": [], "count": 0}

    raw = payload.get("results") or []
    hits = []
    if isinstance(raw, list):
        for item in raw:
            clean = redact_record(item)
            if clean:
                hits.append(clean)

    return {
        "ok": True,
        "query": q,
        "kind": mapped,
        "hits": hits[:20],
        "count": int(payload.get("count") or len(hits) or 0),
        "censored": bool(payload.get("censored")),
        "stealerlogs": False,
        "source": "OSINT Leak API",
        "docs": DOCS_URL,
    }
