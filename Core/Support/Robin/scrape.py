"""
Scrape de páginas encontradas. .onion só via Tor.

Adaptado de Robin (MIT) © Apurv Singh Gautam
https://github.com/apurvsinghgautam/robin
"""

from __future__ import annotations

import logging
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .search import USER_AGENTS, tor_proxy_up

import warnings

warnings.filterwarnings("ignore")

MAX_DOWNLOAD_BYTES = 1_000_000
MAX_EXTRACTED_TEXT_CHARS = 50_000
MAX_RETURN_CHARS = 2_000
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_thread_local = threading.local()
_logger = logging.getLogger(__name__)


def _normalize_url_data(url_data) -> tuple[str, str]:
    if not isinstance(url_data, dict):
        return "", "Untitled"
    url = str(url_data.get("link") or "").strip()
    title = str(url_data.get("title") or "Untitled").strip() or "Untitled"
    return url, title


def _build_session(use_tor: bool = False) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        read=2,
        connect=2,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=12, pool_maxsize=12)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if use_tor:
        session.proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050",
        }
    return session


def _get_session(use_tor: bool = False) -> requests.Session:
    key = "tor_session" if use_tor else "direct_session"
    if not hasattr(_thread_local, key):
        setattr(_thread_local, key, _build_session(use_tor=use_tor))
    return getattr(_thread_local, key)


def scrape_single(url_data) -> tuple[str, str]:
    url, title = _normalize_url_data(url_data)
    if not url:
        return "", title

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return url, title

    is_onion = (parsed.hostname or "").lower().endswith(".onion")
    if is_onion and not tor_proxy_up():
        return url, f"{title} — scrape .onion exige Tor (proxy 9050 ausente)"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }
    response = None
    try:
        session = _get_session(use_tor=is_onion)
        timeout = (10, 45) if is_onion else (5, 25)
        response = session.get(url, headers=headers, timeout=timeout, stream=True)
        if response.status_code != 200:
            return url, title
        content_type = (response.headers.get("Content-Type") or "").lower()
        if content_type and not any(t in content_type for t in ALLOWED_CONTENT_TYPES):
            return url, title
        chunks = []
        bytes_read = 0
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            bytes_read += len(chunk)
            if bytes_read > MAX_DOWNLOAD_BYTES:
                break
            chunks.append(chunk)
        html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style"]):
            script.extract()
        text = " ".join(soup.get_text(separator=" ").split())[:MAX_EXTRACTED_TEXT_CHARS]
        return url, f"{title} - {text}" if text else title
    except Exception as exc:
        _logger.debug("Failed to scrape url=%s: %s", url, exc)
        return url, title
    finally:
        if response is not None:
            response.close()


def scrape_multiple(urls_data, max_workers: int = 5) -> dict:
    results = {}
    max_workers = max(1, min(int(max_workers), 16))
    if not isinstance(urls_data, (list, tuple)):
        return results

    unique = []
    seen = set()
    for item in urls_data:
        url, title = _normalize_url_data(item)
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append({"link": url, "title": title})

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(scrape_single, item): item for item in unique}
        for future in as_completed(future_to_url):
            try:
                url, content = future.result()
                if not url:
                    continue
                if len(content) > MAX_RETURN_CHARS:
                    content = content[: MAX_RETURN_CHARS - 14] + "...(truncated)"
                results[url] = content
            except Exception as exc:
                _logger.debug("Worker failed: %s", exc)
    return results
