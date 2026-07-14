"""
Wrappers OSINT para Mr.Holmes
- Holehe, Maigret/Sherlock, theHarvester, Subfinder/Amass,
  SpiderFoot (link), dnstwist, httpx
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

PYTHON = sys.executable
SCRIPTS = Path(sys.executable).parent / "Scripts"
TIMEOUT_SHORT = 60
TIMEOUT_LONG = 180


def _which(cmd: str) -> Optional[str]:
    found = shutil.which(cmd)
    if found:
        return found
    # Windows: pip scripts often not on PATH
    for name in (f"{cmd}.exe", cmd):
        candidate = SCRIPTS / name
        if candidate.is_file():
            return str(candidate)
    return None


def _is_projectdiscovery_httpx(path: str) -> bool:
    """Evita confundir com o CLI do pacote Python 'httpx'."""
    r = _run([path, "-h"], timeout=8)
    blob = (r["stdout"] + r["stderr"]).lower()
    return "-silent" in blob or "projectdiscovery" in blob or "-status-code" in blob


def _run(cmd: list, timeout: int = TIMEOUT_LONG, cwd: str = None) -> dict:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "code": proc.returncode,
        }
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": f"Comando não encontrado: {cmd[0]}", "code": -1}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"Timeout após {timeout}s", "code": -2}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e)[:200], "code": -3}


def tool_status() -> dict:
    """Estado de instalação das ferramentas."""
    httpx_bin = _which("httpx")
    return {
        "holehe": bool(_which("holehe") or _module_ok("holehe")),
        "maigret": bool(_which("maigret") or _module_ok("maigret")),
        "sherlock": bool(_which("sherlock")),
        "theHarvester": bool(_which("theHarvester") or _which("theharvester") or _module_ok("theHarvester")),
        "subfinder": bool(_which("subfinder")),
        "amass": bool(_which("amass")),
        "dnstwist": bool(_which("dnstwist") or _module_ok("dnstwist")),
        "httpx": bool(httpx_bin and _is_projectdiscovery_httpx(httpx_bin)),
        "spiderfoot": bool(_which("spiderfoot") or _which("sf")),
    }


def _module_ok(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


# ── Holehe: email → sites com conta ──────────────────────────────────────────

def run_holehe(email: str) -> dict:
    email = email.strip().lower()
    if "@" not in email:
        return {"ok": False, "error": "Email inválido", "sites": []}

    cmd = None
    if _which("holehe"):
        cmd = ["holehe", email, "--only-used", "--no-color"]
    elif _module_ok("holehe"):
        cmd = [PYTHON, "-m", "holehe", email, "--only-used", "--no-color"]
    else:
        return {
            "ok": False,
            "error": "Holehe não instalado. Rode: pip install holehe",
            "sites": [],
            "install": "pip install holehe",
        }

    r = _run(cmd, timeout=TIMEOUT_LONG)
    sites = []
    for line in (r["stdout"] + "\n" + r["stderr"]).splitlines():
        line = line.strip()
        # holehe prints [+] site or similar
        if re.search(r"\[\+\]|found|used", line, re.I) and len(line) > 3:
            clean = re.sub(r"\x1b\[[0-9;]*m", "", line)
            sites.append(clean)
        elif line.startswith("[+]") or " : " in line and ("+" in line or "found" in line.lower()):
            sites.append(re.sub(r"\x1b\[[0-9;]*m", "", line))

    # Fallback parse: lines with domain-like names after [+]
    if not sites:
        for line in r["stdout"].splitlines():
            clean = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
            if clean.startswith("[+]"):
                sites.append(clean)

    return {
        "ok": True,
        "email": email,
        "sites": sites,
        "raw": r["stdout"][-3000:],
        "error": r["stderr"][:500] if not sites and r["stderr"] else "",
    }


# ── Maigret / Sherlock: username em redes ────────────────────────────────────

def run_maigret(username: str, max_sites: int = 50) -> dict:
    username = username.strip().lstrip("@")
    if not username:
        return {"ok": False, "error": "Username vazio", "profiles": []}

    if _which("maigret") or _module_ok("maigret"):
        out_dir = tempfile.mkdtemp(prefix="maigret_")
        cmd = (
            ["maigret", username, "--json", "simple", "-fo", out_dir, "--timeout", "10", "-n", str(max_sites)]
            if _which("maigret")
            else [PYTHON, "-m", "maigret", username, "--json", "simple", "-fo", out_dir, "--timeout", "10", "-n", str(max_sites)]
        )
        r = _run(cmd, timeout=TIMEOUT_LONG)
        profiles = []
        # Maigret writes JSON files in out_dir
        for p in Path(out_dir).glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for site, info in data.items():
                        if isinstance(info, dict) and (info.get("url") or info.get("url_user")):
                            profiles.append({
                                "site": site,
                                "url": info.get("url_user") or info.get("url") or "",
                            })
                        elif isinstance(info, str) and info.startswith("http"):
                            profiles.append({"site": site, "url": info})
            except Exception:
                continue
        # Also parse stdout for Found lines
        for line in r["stdout"].splitlines():
            if "[+]" in line or "Found" in line:
                m = re.search(r"https?://\S+", line)
                if m:
                    profiles.append({"site": line.split(":")[0].strip(" [+]"), "url": m.group(0)})

        # dedupe
        seen = set()
        uniq = []
        for p in profiles:
            u = p.get("url", "")
            if u and u not in seen:
                seen.add(u)
                uniq.append(p)

        return {"ok": True, "username": username, "profiles": uniq, "tool": "maigret", "raw": r["stdout"][-2000:]}

    if _which("sherlock"):
        r = _run(["sherlock", username, "--print-found", "--timeout", "10"], timeout=TIMEOUT_LONG)
        profiles = []
        for line in r["stdout"].splitlines():
            m = re.search(r"https?://\S+", line)
            if m:
                profiles.append({"site": line.split("[+]")[-1].split(":")[0].strip(), "url": m.group(0)})
        return {"ok": True, "username": username, "profiles": profiles, "tool": "sherlock", "raw": r["stdout"][-2000:]}

    return {
        "ok": False,
        "error": "Maigret/Sherlock não instalados. Rode: pip install maigret",
        "profiles": [],
        "install": "pip install maigret",
    }


# ── theHarvester: emails + hosts de um domínio ───────────────────────────────

def run_theharvester(domain: str, limit: int = 50) -> dict:
    domain = _clean_domain(domain)
    if not domain:
        return {"ok": False, "error": "Domínio inválido", "emails": [], "hosts": []}

    binary = _which("theHarvester") or _which("theharvester")
    if binary:
        cmd = [binary, "-d", domain, "-b", "bing,duckduckgo", "-l", str(limit)]
    elif _module_ok("theHarvester") or _module_ok("theHarvester.theHarvester"):
        cmd = [PYTHON, "-m", "theHarvester", "-d", domain, "-b", "bing", "-l", str(limit)]
    else:
        # Fallback leve: MX + DNS common
        return _harvester_fallback(domain)

    r = _run(cmd, timeout=TIMEOUT_LONG)
    text = r["stdout"] + "\n" + r["stderr"]
    emails = sorted(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)))
    hosts = sorted(set(re.findall(rf"[a-zA-Z0-9._-]+\.{re.escape(domain)}", text, re.I)))
    return {
        "ok": True,
        "domain": domain,
        "emails": emails[:limit],
        "hosts": hosts[:limit],
        "raw": r["stdout"][-2500:],
        "tool": "theHarvester",
    }


def _harvester_fallback(domain: str) -> dict:
    hosts = []
    emails = []
    try:
        import dns.resolver
        for rtype in ("MX", "NS", "TXT"):
            try:
                for a in dns.resolver.resolve(domain, rtype):
                    hosts.append(str(a).rstrip("."))
            except Exception:
                pass
    except Exception:
        pass
    for sub in ("www", "mail", "ftp", "api", "dev", "staging", "vpn", "portal"):
        try:
            socket.gethostbyname(f"{sub}.{domain}")
            hosts.append(f"{sub}.{domain}")
        except Exception:
            pass
    return {
        "ok": True,
        "domain": domain,
        "emails": emails,
        "hosts": sorted(set(hosts)),
        "tool": "fallback-dns",
        "note": "theHarvester não instalado — usado fallback DNS. pip install theHarvester",
    }


# ── Subfinder / Amass: subdomínios ───────────────────────────────────────────

COMMON_SUBS = [
    "www", "mail", "ftp", "webmail", "smtp", "pop", "ns1", "ns2", "dns",
    "api", "app", "dev", "test", "staging", "prod", "admin", "portal",
    "vpn", "cdn", "static", "img", "images", "blog", "shop", "store",
    "m", "mobile", "beta", "demo", "docs", "status", "git", "gitlab",
    "ci", "jenkins", "grafana", "monitor", "db", "mysql", "redis",
    "remote", "owa", "autodiscover", "cpanel", "whm", "panel",
]


def run_subdomains(domain: str) -> dict:
    domain = _clean_domain(domain)
    if not domain:
        return {"ok": False, "error": "Domínio inválido", "subdomains": []}

    found = []
    tool = "fallback"
    note = ""

    if _which("subfinder"):
        r = _run(["subfinder", "-d", domain, "-silent"], timeout=TIMEOUT_LONG)
        found = [l.strip() for l in r["stdout"].splitlines() if l.strip()]
        tool = "subfinder"
    elif _which("amass"):
        r = _run(["amass", "enum", "-passive", "-d", domain, "-timeout", "2"], timeout=TIMEOUT_LONG)
        found = [l.strip() for l in r["stdout"].splitlines() if l.strip() and domain in l]
        tool = "amass"
    else:
        for sub in COMMON_SUBS:
            host = f"{sub}.{domain}"
            try:
                ip = socket.gethostbyname(host)
                found.append(f"{host} ({ip})")
            except Exception:
                pass
        tool = "bruteforce-dns"
        note = "Subfinder/Amass não no PATH — usado brute DNS leve. Instale: https://github.com/projectdiscovery/subfinder"

    return {
        "ok": True,
        "domain": domain,
        "subdomains": sorted(set(found)),
        "tool": tool,
        "note": note,
        "count": len(set(found)),
    }


# ── dnstwist: typosquatting ──────────────────────────────────────────────────

def run_dnstwist(domain: str, registered_only: bool = True) -> dict:
    domain = _clean_domain(domain)
    if not domain:
        return {"ok": False, "error": "Domínio inválido", "domains": []}

    if _which("dnstwist"):
        cmd = ["dnstwist", "--format", "json", domain]
        if registered_only:
            cmd.insert(1, "--registered")
        r = _run(cmd, timeout=TIMEOUT_LONG)
        try:
            data = json.loads(r["stdout"] or "[]")
            domains = [
                {
                    "domain": d.get("domain", ""),
                    "fuzzer": d.get("fuzzer", ""),
                    "dns_a": ",".join(d.get("dns_a", [])[:2]) if isinstance(d.get("dns_a"), list) else str(d.get("dns_a", "")),
                }
                for d in data if isinstance(d, dict)
            ]
            return {"ok": True, "domain": domain, "domains": domains, "tool": "dnstwist"}
        except json.JSONDecodeError:
            lines = [l.strip() for l in r["stdout"].splitlines() if l.strip()]
            return {"ok": True, "domain": domain, "domains": [{"domain": l, "fuzzer": "", "dns_a": ""} for l in lines[:100]], "tool": "dnstwist"}

    if _module_ok("dnstwist"):
        # API usage varies; call CLI module
        cmd = [PYTHON, "-m", "dnstwist", "--format", "json"]
        if registered_only:
            cmd.append("--registered")
        cmd.append(domain)
        r = _run(cmd, timeout=TIMEOUT_LONG)
        try:
            data = json.loads(r["stdout"] or "[]")
            domains = [
                {"domain": d.get("domain", ""), "fuzzer": d.get("fuzzer", ""), "dns_a": str(d.get("dns_a", ""))}
                for d in data if isinstance(d, dict)
            ]
            return {"ok": True, "domain": domain, "domains": domains, "tool": "dnstwist"}
        except Exception:
            pass

    return _dnstwist_fallback(domain)


def _dnstwist_fallback(domain: str) -> dict:
    """Gera variações simples e testa resolução DNS."""
    if "." not in domain:
        return {"ok": False, "error": "Domínio inválido", "domains": []}
    name, tld = domain.rsplit(".", 1)
    candidates = set()
    # missing dot / hyphen
    if len(name) > 2:
        for i in range(1, len(name)):
            candidates.add(f"{name[:i]}-{name[i:]}.{tld}")
            candidates.add(f"{name[:i]}{name[i:]}.{tld}")  # same
        # char swap
        for i in range(len(name) - 1):
            swapped = list(name)
            swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
            candidates.add("".join(swapped) + "." + tld)
        # common TLD swaps
        for alt in ("com", "net", "org", "com.br", "net.br", "io", "co"):
            if alt != tld and not domain.endswith("." + alt):
                candidates.add(f"{name}.{alt}")
        # double char
        for i, c in enumerate(name):
            candidates.add(name[:i] + c + name[i:] + "." + tld)

    candidates.discard(domain)
    results = []
    for d in sorted(candidates)[:80]:
        try:
            ip = socket.gethostbyname(d)
            results.append({"domain": d, "fuzzer": "fallback", "dns_a": ip})
        except Exception:
            pass

    return {
        "ok": True,
        "domain": domain,
        "domains": results,
        "tool": "fallback-twist",
        "note": "dnstwist não instalado — variações básicas. pip install dnstwist",
    }


# ── httpx: hosts/URLs vivos ──────────────────────────────────────────────────

def run_httpx(targets: list) -> dict:
    """Checa quais URLs/hosts respondem HTTP."""
    cleaned = []
    for t in targets:
        t = t.strip()
        if not t:
            continue
        if not t.startswith("http"):
            t = "https://" + t
        cleaned.append(t)

    if not cleaned:
        return {"ok": False, "error": "Nenhum alvo", "alive": []}

    if _which("httpx") and _is_projectdiscovery_httpx(_which("httpx")):
        httpx_bin = _which("httpx")
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt", encoding="utf-8") as f:
            f.write("\n".join(cleaned))
            path = f.name
        try:
            r = _run(
                [httpx_bin, "-l", path, "-silent", "-status-code", "-title"],
                timeout=TIMEOUT_LONG,
            )
            alive = [l.strip() for l in r["stdout"].splitlines() if l.strip()]
            return {"ok": True, "alive": alive, "tool": "httpx", "total": len(cleaned)}
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    # Fallback Python (não usa o pacote httpx do PyPI como scanner OSINT)
    import urllib.request
    alive = []
    for url in cleaned[:50]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MrHolmes-1.0"}, method="GET")
            with urllib.request.urlopen(req, timeout=8) as resp:
                title = ""
                try:
                    body = resp.read(4096).decode("utf-8", errors="ignore")
                    m = re.search(r"<title>([^<]+)</title>", body, re.I)
                    title = m.group(1).strip() if m else ""
                except Exception:
                    pass
                alive.append(f"{url} [{resp.status}] {title}".strip())
        except Exception as e:
            # try http if https failed
            if url.startswith("https://"):
                try:
                    alt = "http://" + url[8:]
                    req = urllib.request.Request(alt, headers={"User-Agent": "MrHolmes-1.0"})
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        alive.append(f"{alt} [{resp.status}]")
                except Exception:
                    pass

    return {
        "ok": True,
        "alive": alive,
        "tool": "python-fallback",
        "total": len(cleaned),
        "note": "httpx (ProjectDiscovery) não no PATH — usado checker Python. https://github.com/projectdiscovery/httpx",
    }


# ── SpiderFoot ───────────────────────────────────────────────────────────────

def spiderfoot_info() -> dict:
    status = tool_status()["spiderfoot"]
    return {
        "installed": status,
        "url": "http://127.0.0.1:5001",
        "docs": "https://github.com/smicallef/spiderfoot",
        "install": "pip install spiderfoot  # ou clone o repo e rode sf.py -l 127.0.0.1:5001",
        "note": "SpiderFoot é pesado (UI própria). Use como serviço externo e cole o alvo no Mr.Holmes.",
    }


def _clean_domain(domain: str) -> str:
    domain = (domain or "").strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/")[0].split("?")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain
