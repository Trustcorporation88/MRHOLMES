"""Network Tools - Mr.Holmes
Ping, Port Scan, Uptime Check, Reverse IP, My IP, WHOIS, Hosting Lookup
"""

import socket
import urllib.request
import json
import subprocess
import platform
import re
from datetime import datetime
from Core.Support import Font

COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
    443: "HTTPS", 587: "SMTP TLS", 993: "IMAPS", 995: "POP3S",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    8080: "HTTP-Alt", 8443: "HTTPS-Alt",
}


def ping_host(host: str, count: int = 4) -> dict:
    """Executa ping em um host."""
    host = re.sub(r'^https?://', '', host).split('/')[0]
    
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    
    try:
        result = subprocess.run(
            ['ping', param, str(count), host],
            capture_output=True, text=True, timeout=15
        )
        
        output = result.stdout
        
        times = re.findall(r'time[=<]\s*(\d+\.?\d*)\s*ms', output, re.IGNORECASE)
        lost_match = re.search(r'(\d+)% loss', output) or re.search(r'(\d+)% packet loss', output)
        
        return {
            "host": host,
            "success": result.returncode == 0,
            "avg_time": sum(float(t) for t in times) / len(times) if times else 0,
            "min_time": min(float(t) for t in times) if times else 0,
            "max_time": max(float(t) for t in times) if times else 0,
            "packet_loss": int(lost_match.group(1)) if lost_match else 100,
            "output": output[-500:],
        }
    except Exception as e:
        return {"host": host, "success": False, "error": str(e)[:100]}


def scan_ports(host: str, ports: list = None) -> list:
    """Escaneia portas comuns em um host."""
    if ports is None:
        ports = list(COMMON_PORTS.keys())
    
    host = re.sub(r'^https?://', '', host).split('/')[0]
    results = []
    
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                results.append({
                    "port": port,
                    "service": COMMON_PORTS.get(port, "Unknown"),
                    "open": True,
                })
        except Exception:
            pass
    
    return results


def check_uptime(url: str) -> dict:
    """Verifica se um site está online."""
    if not url.startswith('http'):
        url = 'https://' + url
    
    try:
        start = datetime.now()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        elapsed = (datetime.now() - start).total_seconds()
        
        return {
            "url": url,
            "online": True,
            "status_code": resp.status,
            "response_time": round(elapsed, 2),
            "server": resp.headers.get("Server", "N/A"),
        }
    except Exception as e:
        return {
            "url": url,
            "online": False,
            "error": str(e)[:100],
        }


def reverse_ip(ip: str) -> dict:
    """Busca domínios associados a um IP (reverse lookup)."""
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        return {"ip": ip, "hostname": hostname, "found": True}
    except Exception:
        return {"ip": ip, "hostname": None, "found": False}


def get_my_ip() -> dict:
    """Obtém o IP público atual."""
    services = [
        "https://api.ipify.org?format=json",
        "https://api.my-ip.io/ip.json",
        "https://ipapi.co/json/",
    ]
    
    for url in services:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MrHolmes-1.0"})
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read().decode())
            
            ip = data.get("ip") or data.get("ip_addr") or ""
            if ip:
                return {"ip": ip, "source": url.split("/")[2]}
        except Exception:
            continue
    
    return {"ip": "Could not determine", "source": "none"}


def lookup_hosting(domain: str) -> dict:
    """Identifica o provedor de hospedagem de um domínio."""
    domain = re.sub(r'^https?://', '', domain).split('/')[0]
    
    try:
        ip = socket.gethostbyname(domain)
        
        req = urllib.request.Request(
            f"http://ip-api.com/json/{ip}",
            headers={"User-Agent": "MrHolmes-1.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        geo = json.loads(resp.read().decode())
        
        return {
            "domain": domain,
            "ip": ip,
            "isp": geo.get("isp", "N/A"),
            "org": geo.get("org", "N/A"),
            "country": geo.get("country", "N/A"),
            "hosting_link": f"https://hostingchecker.com/results/{domain}",
            "whois_link": f"https://viewdns.info/whois/?domain={domain}",
        }
    except Exception as e:
        return {"domain": domain, "error": str(e)[:100]}
