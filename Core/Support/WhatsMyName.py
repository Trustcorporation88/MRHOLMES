"""Username check using the public WhatsMyName site list (not whatsmyname.app).

Dataset: WebBreacher/WhatsMyName wmn-data.json, CC BY-SA 4.0.
Holmes hits the public profile URLs itself. It does not scrape the web UI
and does not call unofficial third-party WhatsMyName APIs.
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

WMN_DATA_URL = (
    "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
)
WMN_REPO = "https://github.com/WebBreacher/WhatsMyName"
_UA = {
    "User-Agent": "MrHolmes-OSINT/1.0 (educational; authorized targets; WhatsMyName dataset)"
}
_SKIP_CATS = {"xx NSFW xx", "archived"}
_SKIP_PROTECTION = {"captcha"}
_PREFERRED_CATS = (
    "social",
    "coding",
    "blog",
    "images",
    "video",
    "music",
    "tech",
    "news",
    "business",
    "hobby",
)
_CACHE_TTL = 7 * 24 * 3600
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_.-]{2,32}$")


def _cache_path() -> Path:
    return Path(tempfile.gettempdir()) / "mrholmes-wmn-data.json"


def load_wmn_data(force: bool = False) -> dict:
    path = _cache_path()
    if not force and path.is_file() and time.time() - path.stat().st_mtime < _CACHE_TTL:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    resp = requests.get(WMN_DATA_URL, headers=_UA, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    try:
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass
    return data


def selectable_sites(data: dict | None = None, max_sites: int = 80) -> list[dict]:
    blob = data or {}
    sites = blob.get("sites") if isinstance(blob, dict) else None
    if not isinstance(sites, list):
        return []
    preferred, rest = [], []
    for site in sites:
        if not isinstance(site, dict):
            continue
        if site.get("valid") is False:
            continue
        cat = (site.get("cat") or "").strip()
        if cat in _SKIP_CATS:
            continue
        protection = {str(p).lower() for p in (site.get("protection") or [])}
        if protection & _SKIP_PROTECTION:
            continue
        uri = site.get("uri_check") or ""
        if "{account}" not in uri:
            continue
        if cat in _PREFERRED_CATS:
            preferred.append(site)
        else:
            rest.append(site)
    return (preferred + rest)[: max(1, int(max_sites))]


def _profile_url(site: dict, username: str) -> str:
    encoded = quote(username, safe="._-")
    pretty = site.get("uri_pretty") or site.get("uri_check") or ""
    return pretty.replace("{account}", encoded)


def _is_hit_text(text: str, site: dict, status: int) -> bool:
    """Regra de acerto do dataset, separada da resposta para servir aos dois
    caminhos: requisição direta e HTML vindo do Unlocker."""
    e_code = int(site.get("e_code") or 200)
    m_code = site.get("m_code")
    e_string = site.get("e_string") or ""
    m_string = site.get("m_string") or ""
    if m_string and m_string in text:
        return False
    if m_code is not None and status == int(m_code) and status != e_code:
        return False
    if status != e_code:
        return False
    if e_string and e_string not in text:
        return False
    return True


def _is_hit(resp: requests.Response, site: dict) -> bool:
    return _is_hit_text(resp.text or "", site, resp.status_code)


# Códigos que significam "o site barrou a requisição", não "o perfil não
# existe". A distinção é o coração deste módulo: tratar bloqueio como ausência
# produz falso negativo — o pior erro possível numa ferramenta de OSINT, porque
# afirma com confiança que não há perfil quando na verdade ninguém olhou.
_BLOCK_CODES = {401, 403, 405, 429, 451, 503}
_BLOCK_MARKERS = (
    "just a moment",
    "attention required",
    "checking your browser",
    "enable javascript and cookies",
    "access denied",
    "captcha",
)


def _looks_blocked(resp: requests.Response, site: dict) -> bool:
    status = resp.status_code
    e_code = int(site.get("e_code") or 200)
    m_code = site.get("m_code")
    e_string = site.get("e_string") or ""
    text = resp.text or ""

    # Primeiro o corpo, e não o código: o desafio do Cloudflare costuma vir
    # com HTTP 200. Checar o status antes deixaria passar justamente o caso
    # mais comum de bloqueio. A ressalva do e_string evita falso positivo numa
    # página que por acaso contém a palavra e ainda assim traz o perfil.
    sample = text[:2000].lower()
    if any(marker in sample for marker in _BLOCK_MARKERS):
        if not e_string or e_string not in text:
            return True
    # `getattr` porque nem todo objeto-resposta (dublê de teste, mock de
    # terceiro) expõe headers, e um AttributeError aqui apagaria o achado.
    if (getattr(resp, "headers", None) or {}).get("cf-mitigated"):
        return True

    # Se o próprio dataset diz que esse código é resposta legítima do site,
    # então não é bloqueio — é o protocolo normal daquela plataforma.
    if status == e_code:
        return False
    if m_code is not None and status == int(m_code):
        return False
    return status in _BLOCK_CODES


def _probe(site: dict, username: str, timeout: float, use_unlocker: bool = False) -> dict:
    """
    Sonda um site. Nunca levanta exceção; devolve sempre um veredito explícito.

    status ∈ {hit, miss, blocked, error, unlocked_hit, inconclusive}
    """
    name = site.get("name") or site.get("uri_check") or "site"
    url = (site.get("uri_check") or "").replace("{account}", quote(username, safe="._-"))
    out = {"site": name, "url": _profile_url(site, username), "category": site.get("cat") or ""}
    headers = dict(_UA)
    extra = site.get("headers")
    if isinstance(extra, dict):
        headers.update({str(k): str(v) for k, v in extra.items()})

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
    except Exception as exc:
        return {**out, "status": "error", "detail": type(exc).__name__}

    if _looks_blocked(resp, site):
        if use_unlocker:
            return _probe_unlocked(site, username, out, resp.status_code)
        return {**out, "status": "blocked", "http": resp.status_code}

    if _is_hit(resp, site):
        return {**out, "status": "hit", "http": resp.status_code}
    return {**out, "status": "miss", "http": resp.status_code}


def _probe_unlocked(site: dict, username: str, out: dict, first_status: int) -> dict:
    """Segunda tentativa, paga, só para quem bloqueou na primeira."""
    try:
        from holmes import net
    except Exception:
        return {**out, "status": "blocked", "http": first_status}

    url = (site.get("uri_check") or "").replace("{account}", quote(username, safe="._-"))
    html = net.unlocked_get_text(url)
    if html is None:
        return {**out, "status": "blocked", "http": first_status, "detail": "unlocker indisponível"}

    # O Unlocker devolve o corpo, não o código de status original. Sem e_string
    # no dataset não dá para afirmar nada: melhor inconclusivo que falso.
    e_string = site.get("e_string") or ""
    if not e_string:
        return {**out, "status": "inconclusive", "detail": "sem e_string para validar"}
    if _is_hit_text(html, site, int(site.get("e_code") or 200)):
        return {**out, "status": "unlocked_hit", "http": first_status, "via": "unlocker"}
    return {**out, "status": "miss", "via": "unlocker"}


def check_username(
    username: str,
    max_sites: int = 80,
    timeout: float = 6.0,
    workers: int = 12,
    data: dict | None = None,
    use_unlocker: bool | None = None,
) -> dict:
    handle = (username or "").strip().lstrip("@")
    base = {
        "username": handle,
        "profiles": [],
        "checked": 0,
        "blocked": [],
        "source": "WhatsMyName dataset",
    }
    if not _HANDLE_RE.match(handle):
        return {**base, "ok": False, "error": "Username inválido"}

    if use_unlocker is None:
        try:
            from holmes import net

            use_unlocker = net.unlocker_enabled()
        except Exception:
            use_unlocker = False

    blob = data
    if blob is None:
        try:
            blob = load_wmn_data()
        except Exception as exc:
            return {
                **base,
                "ok": False,
                "error": f"Não deu para baixar a lista WhatsMyName: {exc}"[:220],
            }

    sites = selectable_sites(blob, max_sites=max_sites)
    found: list[dict] = []
    blocked: list[dict] = []
    inconclusive: list[dict] = []
    errors = 0

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futs = [pool.submit(_probe, site, handle, timeout, use_unlocker) for site in sites]
        for fut in as_completed(futs):
            try:
                res = fut.result()
            except Exception:
                errors += 1
                continue
            status = res.get("status")
            if status in ("hit", "unlocked_hit"):
                found.append(res)
            elif status == "blocked":
                blocked.append(res)
            elif status == "inconclusive":
                inconclusive.append(res)
            elif status == "error":
                errors += 1

    seen = set()
    uniq = []
    for item in found:
        url = item.get("url") or ""
        if url and url not in seen:
            seen.add(url)
            uniq.append(item)

    # `conclusive` é quantos sites realmente responderam. É esse o denominador
    # honesto de "nenhum perfil encontrado" — não o total da lista.
    conclusive = len(sites) - len(blocked) - len(inconclusive) - errors

    result = {
        "ok": True,
        "username": handle,
        "profiles": uniq,
        "checked": len(sites),
        "conclusive": max(0, conclusive),
        "blocked": blocked,
        "blocked_count": len(blocked),
        "inconclusive_count": len(inconclusive),
        "errors": errors,
        "error": "",
        "source": "WhatsMyName dataset",
        "license": "CC BY-SA 4.0",
        "upstream": WMN_REPO,
        "tool": "whatsmyname",
        "unlocker_used": bool(use_unlocker),
    }
    if use_unlocker:
        try:
            from holmes import net

            result["unlocker"] = net.unlocker_stats()
        except Exception:
            pass
    return result
