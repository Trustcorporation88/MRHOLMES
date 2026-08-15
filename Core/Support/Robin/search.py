"""
Busca em motores .onion (via Tor) + Ahmia clearnet.

Adaptado de Robin (MIT) © Apurv Singh Gautam
https://github.com/apurvsinghgautam/robin
"""

from __future__ import annotations

import os
import random
import re
import shutil
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import warnings

warnings.filterwarnings("ignore")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
]

SEARCH_ENGINES = [
    {"name": "Ahmia", "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}"},
    {"name": "OnionLand", "url": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}"},
    {"name": "Torgle", "url": "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}"},
    {"name": "Amnesia", "url": "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}"},
    {"name": "Tor66", "url": "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}"},
    {"name": "Find Tor", "url": "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}"},
    {"name": "Excavator", "url": "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}"},
    {"name": "OSS", "url": "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/oss/index.php?search={query}"},
]

AHMIA_CLEARNET = "https://ahmia.fi/search/?q={query}"
ONION_RE = re.compile(r"https?://[a-z0-9]+\.onion[^\s\"'<>]*", re.I)


def tor_proxy_up(host: str = "127.0.0.1", port: int = 9050, timeout: float = 2.0) -> bool:
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except OSError:
        return False


_TOR_START_ATTEMPTED = False


def ensure_tor(wait_seconds: float = 20.0) -> bool:
    """Sobe o daemon Tor local se o binário existir e a :9050 estiver fechada."""
    global _TOR_START_ATTEMPTED
    if tor_proxy_up():
        return True
    if _TOR_START_ATTEMPTED:
        return False
    _TOR_START_ATTEMPTED = True
    binary = shutil.which("tor")
    if not binary:
        return False
    data_dir = os.environ.get("TOR_DATA_DIR", "/tmp/tordata")
    os.makedirs(data_dir, exist_ok=True)
    try:
        subprocess.Popen(
            [
                binary,
                "--RunAsDaemon", "1",
                "--SocksPort", "127.0.0.1:9050",
                "--ControlPort", "127.0.0.1:9051",
                "--CookieAuthentication", "0",
                "--DataDirectory", data_dir,
                "--Log", "notice file /tmp/tor.log",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    deadline = time.time() + max(1.0, wait_seconds)
    while time.time() < deadline:
        if tor_proxy_up():
            return True
        time.sleep(0.5)
    return tor_proxy_up()


def get_tor_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=2, read=2, connect=2, backoff_factor=0.4, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.proxies = {
        "http": "socks5h://127.0.0.1:9050",
        "https": "socks5h://127.0.0.1:9050",
    }
    return session


def _direct_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=2, read=2, connect=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def extract_onion_results(html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    links = []
    seen = set()
    for a in soup.find_all("a"):
        href = str(a.get("href") or "")
        title = a.get_text(" ", strip=True)
        found = ONION_RE.findall(href)
        if not found:
            continue
        url = found[0].rstrip("/")
        if "search" in url.lower() or len(title) < 3:
            continue
        if url in seen:
            continue
        seen.add(url)
        links.append({"title": title[:180], "link": url})
    return links


def fetch_search_results(endpoint: str, query: str, use_tor: bool) -> list[dict]:
    url = endpoint.format(query=quote_plus(query))
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    session = get_tor_session() if use_tor else _direct_session()
    try:
        response = session.get(url, headers=headers, timeout=40)
        if response.status_code != 200:
            return []
        return extract_onion_results(response.text)
    except Exception:
        return []


def fetch_ahmia_clearnet(query: str) -> list[dict]:
    return fetch_search_results(AHMIA_CLEARNET, query, use_tor=False)


def _dedupe(results: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for res in results:
        link = (res.get("link") or "").rstrip("/")
        if not link or link in seen:
            continue
        seen.add(link)
        unique.append(res)
    return unique


def get_search_results(refined_query: str, max_workers: int = 5) -> dict:
    """Busca Tor (se o proxy estiver no ar) e sempre tenta Ahmia clearnet."""
    query = (refined_query or "").strip()
    if not query:
        return {"results": [], "via_tor": False, "via_clearnet": False, "engines": 0}

    via_tor = ensure_tor()
    collected: list[dict] = []
    engines = 0

    if via_tor:
        endpoints = [e["url"] for e in SEARCH_ENGINES]
        engines = len(endpoints)
        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 8))) as pool:
            futures = [pool.submit(fetch_search_results, ep, query, True) for ep in endpoints]
            for future in as_completed(futures):
                collected.extend(future.result() or [])

    clearnet = fetch_ahmia_clearnet(query)
    collected.extend(clearnet)

    return {
        "results": _dedupe(collected),
        "via_tor": via_tor,
        "via_clearnet": bool(clearnet),
        "engines": engines,
    }
