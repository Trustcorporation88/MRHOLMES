"""Domain Search - Mr.Holmes
Multi-source domain investigation: WHOIS, DNS, IP, ViewDNS links
"""

import urllib.request
import urllib.parse
import json
import re
import socket
from datetime import datetime
from Core.Support import Font
from Core.Support import Language

filename = Language.Translation.Get_Language()

VIEWDNS_TOOLS = {
    "WHOIS": "https://viewdns.info/whois/?domain={}",
    "DNS Records": "https://viewdns.info/dnsrecord/?domain={}",
    "IP History": "https://viewdns.info/iphistory/?domain={}",
    "Reverse IP": "https://viewdns.info/reverseip/?host={}&t=1",
    "Port Scan": "https://viewdns.info/portscan/?host={}",
    "HTTP Headers": "https://viewdns.info/httpheaders/?domain={}",
    "Traceroute": "https://viewdns.info/traceroute/?host={}",
    "DNS Report": "https://viewdns.info/dnsreport/?domain={}",
    "Spam DB": "https://viewdns.info/spamdblookup/?domain={}",
    "Country": "https://viewdns.info/country/?domain={}",
}


def buscar_dominio(dominio: str) -> dict:
    """Busca informações completas sobre um domínio."""
    dominio = dominio.strip().lower()
    dominio = re.sub(r'^https?://', '', dominio)
    dominio = re.sub(r'/.*$', '', dominio)
    
    resultado = {
        "dominio": dominio,
        "ip": None,
        "geo": {},
        "whois": {},
        "dns": {},
        "viewdns_links": {},
        "headers": {},
    }
    
    print(Font.Color.GREEN + "\n[+]" + Font.Color.WHITE + f" DOMAIN SEARCH: {dominio}")
    
    # 1. Resolver IP
    print(Font.Color.YELLOW + "\n[v]" + Font.Color.WHITE + " Resolving IP...")
    try:
        ip = socket.gethostbyname(dominio)
        resultado["ip"] = ip
        print(Font.Color.GREEN + "[+]" + Font.Color.WHITE + f" IP: {ip}")
    except Exception:
        print(Font.Color.RED + "[!]" + Font.Color.WHITE + " Could not resolve IP")
    
    # 2. GeoIP via ip-api.com
    if resultado["ip"]:
        print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + " GeoIP lookup...")
        try:
            req = urllib.request.Request(
                f"http://ip-api.com/json/{resultado['ip']}",
                headers={"User-Agent": "MrHolmes-1.0"}
            )
            resp = urllib.request.urlopen(req, timeout=10)
            geo = json.loads(resp.read().decode())
            resultado["geo"] = geo
            print(Font.Color.GREEN + "[+]" + Font.Color.WHITE +
                  f" COUNTRY: {geo.get('country', 'N/A')} | CITY: {geo.get('city', 'N/A')}")
            print(Font.Color.GREEN + "[+]" + Font.Color.WHITE +
                  f" ISP: {geo.get('isp', 'N/A')} | ORG: {geo.get('org', 'N/A')}")
            print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE +
                  f" COORDS: {geo.get('lat', 0)}, {geo.get('lon', 0)}")
        except Exception:
            pass
    
    # 3. DNS Records via dnspython
    print(Font.Color.YELLOW + "\n[v]" + Font.Color.WHITE + " DNS Records...")
    try:
        import dns.resolver
        
        record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'SOA', 'CNAME']
        for rtype in record_types:
            try:
                answers = dns.resolver.resolve(dominio, rtype)
                records = [str(a) for a in answers][:3]
                resultado["dns"][rtype] = records
                if records:
                    print(Font.Color.GREEN + f"[+] {rtype}:" + Font.Color.WHITE +
                          f" {', '.join(records[:2])}")
            except Exception:
                resultado["dns"][rtype] = []
    except ImportError:
        print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + " dnspython not available")
    except Exception as e:
        print(Font.Color.RED + "[!]" + Font.Color.WHITE + f" DNS error: {str(e)[:60]}")
    
    # 4. HTTP Headers
    print(Font.Color.YELLOW + "\n[v]" + Font.Color.WHITE + " HTTP Headers...")
    try:
        req = urllib.request.Request(
            f"https://{dominio}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        headers = dict(resp.headers)
        resultado["headers"] = {
            "status": resp.status,
            "server": headers.get("Server", "N/A"),
            "content_type": headers.get("Content-Type", "N/A"),
            "x_powered_by": headers.get("X-Powered-By", "N/A"),
        }
        print(Font.Color.GREEN + "[+]" + Font.Color.WHITE +
              f" STATUS: {resp.status} | SERVER: {resultado['headers']['server']}")
    except Exception:
        print(Font.Color.RED + "[!]" + Font.Color.WHITE + " Could not connect")
    
    # 5. ViewDNS Links
    print(Font.Color.YELLOW + "\n[v]" + Font.Color.WHITE + " ViewDNS Tools:")
    for name, url_template in VIEWDNS_TOOLS.items():
        link = url_template.format(dominio)
        resultado["viewdns_links"][name] = link
        print(Font.Color.GREEN + f"[+] {name}:" + Font.Color.WHITE + f" {link}")
    
    print(Font.Color.GREEN + "\n[+]" + Font.Color.WHITE + f" DOMAIN SEARCH COMPLETE: {dominio}")
    
    return resultado


def salvar_relatorio_dominio(resultado: dict) -> str:
    """Salva o resultado em arquivo."""
    dominio = resultado["dominio"]
    pasta = f"GUI/Reports/Domain/{dominio}"
    import os
    os.makedirs(pasta, exist_ok=True)
    
    caminho = os.path.join(pasta, f"{dominio}_report.txt")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(f"Mr.Holmes Domain Report\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Domain: {dominio}\n")
        f.write(f"IP: {resultado.get('ip', 'N/A')}\n\n")
        
        f.write("GeoIP:\n")
        for k, v in resultado.get("geo", {}).items():
            f.write(f"  {k}: {v}\n")
        
        f.write("\nDNS Records:\n")
        for rtype, records in resultado.get("dns", {}).items():
            f.write(f"  {rtype}: {', '.join(records)}\n")
        
        f.write("\nHTTP Headers:\n")
        for k, v in resultado.get("headers", {}).items():
            f.write(f"  {k}: {v}\n")
        
        f.write("\nViewDNS Links:\n")
        for name, link in resultado.get("viewdns_links", {}).items():
            f.write(f"  {name}: {link}\n")
    
    return caminho
