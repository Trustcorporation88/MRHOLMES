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


def _is_hit(resp: requests.Response, site: dict) -> bool:
    text = resp.text or ""
    status = resp.status_code
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


def _probe(site: dict, username: str, timeout: float) -> Optional[dict]:
    url = (site.get("uri_check") or "").replace("{account}", quote(username, safe="._-"))
    headers = dict(_UA)
    extra = site.get("headers")
    if isinstance(extra, dict):
        headers.update({str(k): str(v) for k, v in extra.items()})
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
    except Exception:
        return None
    if not _is_hit(resp, site):
        return None
    return {
        "site": site.get("name") or url,
        "url": _profile_url(site, username),
        "category": site.get("cat") or "",
    }


def check_username(
    username: str,
    max_sites: int = 80,
    timeout: float = 6.0,
    workers: int = 12,
    data: dict | None = None,
) -> dict:
    handle = (username or "").strip().lstrip("@")
    if not _HANDLE_RE.match(handle):
        return {
            "ok": False,
            "error": "Username inválido",
            "username": handle,
            "profiles": [],
            "checked": 0,
            "source": "WhatsMyName dataset",
        }

    error = ""
    blob = data
    if blob is None:
        try:
            blob = load_wmn_data()
        except Exception as exc:
            return {
                "ok": False,
                "error": f"Não deu para baixar a lista WhatsMyName: {exc}"[:220],
                "username": handle,
                "profiles": [],
                "checked": 0,
                "source": "WhatsMyName dataset",
            }

    sites = selectable_sites(blob, max_sites=max_sites)
    found: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futs = [pool.submit(_probe, site, handle, timeout) for site in sites]
        for fut in as_completed(futs):
            try:
                hit = fut.result()
            except Exception:
                continue
            if hit:
                found.append(hit)

    seen = set()
    uniq = []
    for item in found:
        url = item.get("url") or ""
        if url and url not in seen:
            seen.add(url)
            uniq.append(item)

    return {
        "ok": True,
        "username": handle,
        "profiles": uniq,
        "checked": len(sites),
        "error": error,
        "source": "WhatsMyName dataset",
        "license": "CC BY-SA 4.0",
        "upstream": WMN_REPO,
        "tool": "whatsmyname",
    }
