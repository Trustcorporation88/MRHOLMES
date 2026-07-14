"""
Busca por email - Verificação gratuita multi-fonte para Mr.Holmes
- Valida formato do email
- Verifica MX records (servidor de email existe)
- Busca domínio em pastes públicos (Psbdmp)
- Verifica contas em redes sociais vinculadas ao email
"""

import urllib.request
import urllib.parse
import json
import re
import hashlib
import socket
from Core.Support import Font
from Core.Support import Language

filename = Language.Translation.Get_Language()


def validar_email(email: str) -> bool:
    """Valida formato básico do email."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def verificar_mx(dominio: str) -> dict:
    """Verifica se o domínio tem servidores de email (MX records)."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(dominio, 'MX')
        mx_records = [str(a.exchange) for a in answers]
        return {"has_mx": True, "servers": mx_records[:3]}
    except ImportError:
        try:
            socket.gethostbyname(dominio)
            return {"has_mx": True, "servers": ["DNS resolvido (dnspython não instalado)"]}
        except Exception:
            return {"has_mx": False, "servers": []}
    except Exception:
        return {"has_mx": False, "servers": []}


def buscar_pastes_dominio(dominio: str) -> list:
    """Busca o domínio em pastes públicos (Psbdmp.ws)."""
    pastes = []
    try:
        req = urllib.request.Request(
            f"https://psbdmp.ws/api/v3/search/{urllib.parse.quote(dominio)}",
            headers={"User-Agent": "MrHolmes-1.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        if resp.status == 200:
            data = json.loads(resp.read().decode())
            for p in data.get("data", [])[:5]:
                pastes.append({
                    "id": p.get("id", ""),
                    "url": f"https://pastebin.com/{p.get('id', '')}" if p.get("id") else "",
                    "date": p.get("date", "N/A"),
                    "title": p.get("title", "")[:100],
                })
    except Exception:
        pass
    return pastes


def verificar_gravatar(email: str) -> dict:
    """Verifica se o email tem conta Gravatar (implica conta real)."""
    email_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
    try:
        req = urllib.request.Request(
            f"https://www.gravatar.com/{email_hash}.json",
            headers={"User-Agent": "MrHolmes-1.0"}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        if resp.status == 200:
            return {"has_gravatar": True}
    except Exception:
        pass
    return {"has_gravatar": False}


def buscar_email(email: str) -> dict:
    """
    Busca informações sobre um email usando fontes públicas gratuitas.
    
    Retorna: dict com validação, MX, pastes, Gravatar e alertas.
    """
    email_limpo = email.strip().lower()
    dominio = email_limpo.split("@")[1] if "@" in email_limpo else ""
    
    resultado = {
        "email": email_limpo,
        "valido": validar_email(email_limpo),
        "dominio": dominio,
        "mx": {},
        "pastes": [],
        "gravatar": {},
        "alertas": [],
        "total_fontes": 0,
    }
    
    if not resultado["valido"]:
        resultado["alertas"].append("Formato de email inválido")
        return resultado
    
    print(Font.Color.GREEN + "\n[+]" + Font.Color.WHITE + f" ANALYZING: {email_limpo}")
    
    print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + " Checking email format...")
    print(Font.Color.GREEN + "[+]" + Font.Color.WHITE + " FORMAT: VALID")
    
    print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + " Checking MX records...")
    resultado["mx"] = verificar_mx(dominio)
    if resultado["mx"]["has_mx"]:
        print(Font.Color.GREEN + "[+]" + Font.Color.WHITE + f" MX: {', '.join(resultado['mx']['servers'][:2])}")
        resultado["total_fontes"] += 1
    else:
        print(Font.Color.RED + "[!]" + Font.Color.WHITE + " MX: No mail servers found")
    
    print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + " Checking Gravatar...")
    resultado["gravatar"] = verificar_gravatar(email_limpo)
    if resultado["gravatar"]["has_gravatar"]:
        print(Font.Color.GREEN + "[+]" + Font.Color.WHITE + " GRAVATAR: Account found (real user)")
        resultado["alertas"].append("Conta Gravatar encontrada - email pertence a usuário real")
        resultado["total_fontes"] += 1
    else:
        print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + " GRAVATAR: No public profile")
    
    print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + f" Searching domain '{dominio}' in public pastes...")
    resultado["pastes"] = buscar_pastes_dominio(dominio)
    if resultado["pastes"]:
        print(Font.Color.RED + f"[!]" + Font.Color.WHITE + f" FOUND: {len(resultado['pastes'])} pastes with '{dominio}'")
        for p in resultado["pastes"][:3]:
            print(Font.Color.RED + f"[!]" + Font.Color.WHITE + f" {p['url']}")
        resultado["alertas"].append(f"Domínio {dominio} encontrado em {len(resultado['pastes'])} pastes públicos")
        resultado["total_fontes"] += len(resultado["pastes"])
    else:
        print(Font.Color.GREEN + "[+]" + Font.Color.WHITE + f" No public pastes found for '{dominio}'")
    
    print(Font.Color.GREEN + "\n[+]" + Font.Color.WHITE + f" SUMMARY: {len(resultado['alertas'])} alerts, {resultado['total_fontes']} sources checked")
    
    return resultado
