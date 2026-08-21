"""
Conectores automáticos — os que realmente executam e trazem dado.

Regra de ouro deste arquivo: nada aqui pode depender de binário externo para
funcionar. Onde existe binário (holehe, maigret) ele é bônus; o caminho
principal é HTTP puro, porque é o que sobrevive no container do Railway.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable

from .. import br, net
from ..entity import Entity, EntityType
from ..findings import Confidence, Finding, FindingKind
from ..runtime import binary_available, module_available, resolve_command, run_command
from .base import Connector, Mode, register

# ── E-MAIL ──────────────────────────────────────────────────────────────────

_DISPOSABLE = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "yopmail.com", "throwawaymail.com", "temp-mail.org", "getnada.com",
    "sharklasers.com", "trashmail.com", "maildrop.cc", "dispostable.com",
}
_FREE_PROVIDERS = {
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.com.br",
    "live.com", "icloud.com", "bol.com.br", "uol.com.br", "terra.com.br",
    "protonmail.com", "proton.me", "zoho.com", "gmx.com",
}


def _email_infra(entity: Entity) -> Iterable[Finding]:
    """MX, provedor e descartável — diz se o e-mail sequer pode existir."""
    domain = entity.get("domain", "")
    if not domain:
        return []
    out: list[Finding] = []

    if domain in _DISPOSABLE:
        out.append(Finding(
            kind=FindingKind.NOTE, value="E-mail descartável (temporário)",
            source="email_infra", source_label="Análise de domínio",
            confidence=Confidence.CONFIRMED,
            detail=f"{domain} é serviço de e-mail temporário — forte indício de cadastro deliberadamente anônimo.",
        ))
    elif domain in _FREE_PROVIDERS:
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"Provedor gratuito: {domain}",
            source="email_infra", source_label="Análise de domínio",
            confidence=Confidence.CONFIRMED, detail="Conta pessoal em provedor público.",
        ))
    else:
        out.append(Finding(
            kind=FindingKind.DOMAIN, value=domain, source="email_infra",
            source_label="Análise de domínio", url=f"https://{domain}",
            confidence=Confidence.CONFIRMED,
            detail="Domínio próprio/corporativo — investigar o domínio revela a organização.",
        ))

    if module_available("dns"):
        try:
            import dns.resolver  # type: ignore

            resolver = dns.resolver.Resolver()
            resolver.lifetime = 6
            answers = resolver.resolve(domain, "MX")
            hosts = sorted(str(r.exchange).rstrip(".") for r in answers)
            if hosts:
                provider = "desconhecido"
                blob = " ".join(hosts).lower()
                for needle, name in (
                    ("google", "Google Workspace"), ("outlook", "Microsoft 365"),
                    ("protection.outlook", "Microsoft 365"), ("zoho", "Zoho"),
                    ("locaweb", "Locaweb"), ("uolhost", "UOL Host"),
                    ("titan", "Titan"), ("hostgator", "HostGator"),
                    ("secureserver", "GoDaddy"), ("yandex", "Yandex"),
                ):
                    if needle in blob:
                        provider = name
                        break
                out.append(Finding(
                    kind=FindingKind.NOTE, value=f"MX ativo ({provider})",
                    source="email_infra", source_label="DNS MX",
                    confidence=Confidence.CONFIRMED,
                    detail=f"Servidores: {', '.join(hosts[:3])}. O domínio recebe e-mail.",
                    raw={"mx": hosts},
                ))
        except Exception:
            out.append(Finding(
                kind=FindingKind.NOTE, value="Sem registro MX válido",
                source="email_infra", source_label="DNS MX", confidence=Confidence.LIKELY,
                detail="O domínio não aparenta receber e-mail — endereço provavelmente inválido ou inativo.",
            ))
    return out


def _gravatar(entity: Entity) -> Iterable[Finding]:
    """Gravatar entrega foto, nome e às vezes perfis vinculados. Confirmação forte."""
    canonical = (entity.get("canonical") or entity.value).strip().lower()
    digest = hashlib.md5(canonical.encode("utf-8")).hexdigest()
    profile_url = f"https://www.gravatar.com/{digest}"
    try:
        data = net.get_json(f"{profile_url}.json", timeout=10)
    except Exception:
        return []
    entries = (data or {}).get("entry") or []
    if not entries:
        return []

    prof = entries[0]
    out: list[Finding] = [Finding(
        kind=FindingKind.ACCOUNT, value=f"Gravatar: {prof.get('preferredUsername') or canonical}",
        source="gravatar", source_label="Gravatar", url=profile_url,
        confidence=Confidence.CONFIRMED,
        detail="Perfil Gravatar existe para este e-mail — confirma que o endereço é real e usado.",
    )]
    if prof.get("thumbnailUrl"):
        out.append(Finding(
            kind=FindingKind.IMAGE, value=prof["thumbnailUrl"], source="gravatar",
            source_label="Gravatar", url=prof["thumbnailUrl"], confidence=Confidence.CONFIRMED,
            detail="Foto de perfil vinculada ao e-mail",
        ))
    display = (prof.get("displayName") or "").strip()
    if display and "@" not in display:
        out.append(Finding(
            kind=FindingKind.NAME, value=display, source="gravatar",
            source_label="Gravatar", url=profile_url, confidence=Confidence.LIKELY,
            detail="Nome de exibição declarado no Gravatar",
        ))
    for acc in prof.get("accounts") or []:
        out.append(Finding(
            kind=FindingKind.ACCOUNT,
            value=f"{acc.get('shortname', 'perfil').title()}: {acc.get('username') or ''}".strip(": "),
            source="gravatar", source_label="Gravatar (contas vinculadas)",
            url=acc.get("url"), confidence=Confidence.CONFIRMED,
            detail="Conta declarada pelo próprio titular no Gravatar",
        ))
    for name in prof.get("urls") or []:
        if name.get("value"):
            out.append(Finding(
                kind=FindingKind.LINK, value=name.get("title") or name["value"],
                source="gravatar", source_label="Gravatar (links)", url=name["value"],
                confidence=Confidence.LIKELY, detail="Link declarado no perfil",
            ))
    return out


def _holehe(entity: Entity) -> Iterable[Finding]:
    """Em quais serviços existe conta com este e-mail. Só roda se o binário existir."""
    cmd = resolve_command("holehe", ["--only-used", "--no-color", "--no-clear", entity.value])
    if not cmd:
        return []
    res = run_command(cmd, timeout=90)
    out: list[Finding] = []
    for line in (res.get("stdout") or "").splitlines():
        line = line.strip()
        if not line.startswith("[+]"):
            continue
        service = line[3:].strip().split()[0] if len(line) > 3 else ""
        if not service:
            continue
        out.append(Finding(
            kind=FindingKind.ACCOUNT, value=f"{service} (conta existe)",
            source="holehe", source_label="Holehe", confidence=Confidence.CONFIRMED,
            detail="O serviço confirmou que existe cadastro com este e-mail.",
        ))
    return out


def _hudsonrock(entity: Entity) -> Iterable[Finding]:
    """
    Máquina infectada por infostealer com o e-mail/username do alvo — API
    gratuita da Hudson Rock, sem chave. É o vazamento mais grave: significa
    que TODAS as senhas salvas naquele computador vazaram, não só uma.
    """
    if entity.type is EntityType.EMAIL:
        campo, valor = "email", entity.value
    elif entity.type is EntityType.USERNAME:
        campo, valor = "username", entity.get("handle") or entity.value
    else:
        return []

    try:
        data = net.get_json(
            f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-{campo}",
            params={campo: valor}, timeout=20, ttl=12 * 3600,
        ) or {}
    except Exception:
        return []

    stealers = data.get("stealers") or []
    if not stealers:
        return []

    out: list[Finding] = [Finding(
        kind=FindingKind.BREACH,
        value=f"Infostealer: {len(stealers)} máquina(s) infectada(s)",
        source="hudsonrock", source_label="Hudson Rock",
        url="https://www.hudsonrock.com/free-tools",
        confidence=Confidence.CONFIRMED,
        detail=f"O {campo} aparece em computador infectado por malware. "
               f"{data.get('total_user_services', 0)} serviços pessoais e "
               f"{data.get('total_corporate_services', 0)} corporativos com credencial exposta.",
        raw={"total": len(stealers)},
    )]
    for s in stealers[:5]:
        familia = s.get("stealer_family") or "malware"
        quando = (s.get("date_compromised") or "")[:10]
        so = s.get("operating_system") or ""
        out.append(Finding(
            kind=FindingKind.BREACH,
            value=f"{familia} — {quando}",
            source="hudsonrock", source_label="Hudson Rock",
            url="https://www.hudsonrock.com/free-tools", confidence=Confidence.CONFIRMED,
            detail=f"Computador '{s.get('computer_name') or '?'}' ({so}) infectado. "
                   f"IP parcial: {s.get('ip') or 'n/d'}.",
            raw=s,
        ))
    return out


def _hibp(entity: Entity) -> Iterable[Finding]:
    """Em quais vazamentos o e-mail apareceu. Nome da brecha, não credencial."""
    key = net.get_key("hibp")
    try:
        data = net.get_json(
            f"https://haveibeenpwned.com/api/v3/breachedaccount/{entity.value}",
            params={"truncateResponse": "false"},
            headers={"hibp-api-key": key, "User-Agent": "MrHolmes-OSINT"},
            timeout=15, ttl=6 * 3600,
        )
    except Exception as exc:
        if "404" in str(exc):
            return [Finding(
                kind=FindingKind.NOTE, value="Nenhum vazamento conhecido (HIBP)",
                source="hibp", source_label="Have I Been Pwned",
                confidence=Confidence.CONFIRMED,
                detail="O e-mail não aparece nas brechas catalogadas pelo HIBP.",
            )]
        raise

    out: list[Finding] = []
    for breach in data or []:
        classes = ", ".join(breach.get("DataClasses") or [])
        out.append(Finding(
            kind=FindingKind.BREACH, value=breach.get("Name") or "?",
            source="hibp", source_label="Have I Been Pwned",
            url=f"https://haveibeenpwned.com/PwnedWebsites#{breach.get('Name')}",
            confidence=Confidence.CONFIRMED,
            detail=f"Vazamento em {breach.get('BreachDate')} — dados expostos: {classes}",
            raw={"date": breach.get("BreachDate"), "classes": breach.get("DataClasses")},
        ))
    return out


def _hunter_domain(entity: Entity) -> Iterable[Finding]:
    """Padrão de e-mail e endereços públicos de um domínio corporativo."""
    domain = entity.get("root") or entity.value
    data = net.get_json(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domain, "api_key": net.get_key("hunter"), "limit": 25},
        timeout=20,
    ) or {}
    payload = data.get("data") or {}
    out: list[Finding] = []
    if payload.get("pattern"):
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"Padrão de e-mail: {payload['pattern']}",
            source="hunter", source_label="Hunter.io", confidence=Confidence.LIKELY,
            detail="Permite deduzir o e-mail de qualquer pessoa da organização.",
        ))
    for item in payload.get("emails") or []:
        nome = " ".join(p for p in [item.get("first_name"), item.get("last_name")] if p)
        out.append(Finding(
            kind=FindingKind.EMAIL, value=item.get("value") or "",
            source="hunter", source_label="Hunter.io",
            confidence=Confidence.LIKELY if item.get("confidence", 0) > 70 else Confidence.POSSIBLE,
            detail=f"{nome} — {item.get('position') or 'cargo n/d'} (confiança Hunter {item.get('confidence')}%)",
        ))
        if nome:
            out.append(Finding(
                kind=FindingKind.NAME, value=nome, source="hunter",
                source_label="Hunter.io", confidence=Confidence.POSSIBLE,
                detail=f"Pessoa associada a {domain}",
            ))
    return out


# ── USERNAME ────────────────────────────────────────────────────────────────

def _whatsmyname(entity: Entity) -> Iterable[Finding]:
    """
    Motor principal de username: bate direto nas URLs públicas de perfil.
    HTTP puro, sem binário — funciona no Railway.
    """
    handle = entity.get("handle") or entity.get("username_guess") or entity.value
    if not handle:
        return []
    try:
        from Core.Support.WhatsMyName import check_username
    except Exception:
        return []

    result = check_username(handle, max_sites=90, timeout=6.0, workers=14)
    if not result.get("ok"):
        return []
    out: list[Finding] = []
    for prof in result.get("profiles") or []:
        site = prof.get("site") or prof.get("name") or "site"
        out.append(Finding(
            kind=FindingKind.ACCOUNT, value=f"{site}: @{handle}",
            source="whatsmyname", source_label="WhatsMyName",
            url=prof.get("url"), confidence=Confidence.CONFIRMED,
            detail=f"Perfil ativo respondeu para o handle @{handle}.",
            raw=prof,
        ))
    if not out:
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"Nenhum perfil em {result.get('checked', 0)} sites checados",
            source="whatsmyname", source_label="WhatsMyName", confidence=Confidence.CONFIRMED,
            detail=f"O handle @{handle} não retornou perfil ativo nos sites da lista.",
        ))
    return out


def _maigret(entity: Entity) -> Iterable[Finding]:
    """Bônus quando o binário existe: cobre sites que a lista WMN não tem."""
    handle = entity.get("handle") or entity.value
    import tempfile
    from pathlib import Path

    outdir = Path(tempfile.gettempdir()) / "holmes_maigret"
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = resolve_command(
        "maigret",
        [handle, "--json", "simple", "--folderoutput", str(outdir),
         "--timeout", "8", "--top-sites", "80", "--no-progressbar", "--no-color"],
    )
    if not cmd:
        return []
    run_command(cmd, timeout=180)

    out: list[Finding] = []
    for jf in sorted(outdir.glob(f"*{handle}*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]:
        try:
            data = json.loads(jf.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for site, info in (data or {}).items():
            if not isinstance(info, dict):
                continue
            status = (info.get("status") or {})
            if str(status.get("status") or "").lower() != "claimed":
                continue
            out.append(Finding(
                kind=FindingKind.ACCOUNT, value=f"{site}: @{handle}",
                source="maigret", source_label="Maigret",
                url=info.get("url_user"), confidence=Confidence.CONFIRMED,
                detail="Perfil reivindicado (claimed) segundo o Maigret.",
                raw={"ids": status.get("ids") or {}},
            ))
            # O Maigret extrai nome real, e-mail e cidade da página do perfil.
            for k, v in (status.get("ids") or {}).items():
                if k in {"fullname", "name"} and v:
                    out.append(Finding(
                        kind=FindingKind.NAME, value=str(v), source="maigret",
                        source_label=f"Maigret ({site})", url=info.get("url_user"),
                        confidence=Confidence.LIKELY, detail=f"Nome exibido no perfil {site}",
                    ))
                elif k == "email" and v:
                    out.append(Finding(
                        kind=FindingKind.EMAIL, value=str(v).lower(), source="maigret",
                        source_label=f"Maigret ({site})", url=info.get("url_user"),
                        confidence=Confidence.LIKELY, detail=f"E-mail exposto no perfil {site}",
                    ))
    return out


def _github_user(entity: Entity) -> Iterable[Finding]:
    """API pública do GitHub: nome real, empresa, local, e-mail e repositórios."""
    handle = entity.get("handle") or entity.value
    try:
        data = net.get_json(f"https://api.github.com/users/{handle}", timeout=12)
    except Exception:
        return []
    if not data or not data.get("login"):
        return []

    url = data.get("html_url")
    out: list[Finding] = [Finding(
        kind=FindingKind.ACCOUNT, value=f"GitHub: @{data['login']}",
        source="github", source_label="GitHub API", url=url,
        confidence=Confidence.CONFIRMED,
        detail=f"{data.get('public_repos', 0)} repositórios públicos, "
               f"{data.get('followers', 0)} seguidores, criado em {(data.get('created_at') or '')[:10]}.",
        raw=data,
    )]
    if data.get("name"):
        out.append(Finding(
            kind=FindingKind.NAME, value=data["name"], source="github",
            source_label="GitHub API", url=url, confidence=Confidence.LIKELY,
            detail="Nome declarado no perfil GitHub",
        ))
    if data.get("email"):
        out.append(Finding(
            kind=FindingKind.EMAIL, value=str(data["email"]).lower(), source="github",
            source_label="GitHub API", url=url, confidence=Confidence.CONFIRMED,
            detail="E-mail público no perfil",
        ))
    if data.get("company"):
        out.append(Finding(
            kind=FindingKind.COMPANY, value=str(data["company"]).lstrip("@"),
            source="github", source_label="GitHub API", url=url,
            confidence=Confidence.LIKELY, detail="Empresa declarada no perfil",
        ))
    if data.get("location"):
        out.append(Finding(
            kind=FindingKind.ADDRESS, value=str(data["location"]), source="github",
            source_label="GitHub API", url=url, confidence=Confidence.LIKELY,
            detail="Localização declarada no perfil",
        ))
    if data.get("blog"):
        blog = str(data["blog"])
        out.append(Finding(
            kind=FindingKind.LINK, value="Site pessoal", source="github",
            source_label="GitHub API",
            url=blog if blog.startswith("http") else f"https://{blog}",
            confidence=Confidence.CONFIRMED, detail="Link declarado no perfil GitHub",
        ))
    if data.get("avatar_url"):
        out.append(Finding(
            kind=FindingKind.IMAGE, value=data["avatar_url"], source="github",
            source_label="GitHub API", url=data["avatar_url"],
            confidence=Confidence.CONFIRMED, detail="Foto de perfil",
        ))

    # E-mail de commit é o vazamento clássico de identidade em conta GitHub.
    try:
        events = net.get_json(f"https://api.github.com/users/{handle}/events/public", timeout=12) or []
        emails: dict[str, str] = {}
        for ev in events[:60]:
            for commit in ((ev.get("payload") or {}).get("commits") or []):
                author = (commit.get("author") or {})
                mail = (author.get("email") or "").lower()
                if mail and "noreply" not in mail:
                    emails[mail] = author.get("name") or ""
        for mail, nome in list(emails.items())[:5]:
            out.append(Finding(
                kind=FindingKind.EMAIL, value=mail, source="github",
                source_label="GitHub (commits públicos)", url=url,
                confidence=Confidence.CONFIRMED,
                detail=f"E-mail usado em commit público{f' por {nome}' if nome else ''}.",
            ))
            if nome:
                out.append(Finding(
                    kind=FindingKind.NAME, value=nome, source="github",
                    source_label="GitHub (commits públicos)", url=url,
                    confidence=Confidence.LIKELY, detail="Nome configurado no git do autor",
                ))
    except Exception:
        pass
    return out


# ── TELEFONE ────────────────────────────────────────────────────────────────

def _phone_lib(entity: Entity) -> Iterable[Finding]:
    """libphonenumber: validade, operadora original, região e fuso."""
    if not module_available("phonenumbers"):
        return []
    import phonenumbers as pn
    from phonenumbers import carrier, geocoder, timezone

    try:
        parsed = pn.parse(entity.get("e164", entity.value), None)
    except Exception:
        return []

    out: list[Finding] = []
    if not pn.is_valid_number(parsed):
        out.append(Finding(
            kind=FindingKind.NOTE, value="Número inválido para o país detectado",
            source="libphonenumber", source_label="libphonenumber",
            confidence=Confidence.CONFIRMED,
            detail="A numeração não fecha com o plano nacional — confira os dígitos.",
        ))
        return out

    op = carrier.name_for_number(parsed, "pt") or carrier.name_for_number(parsed, "en")
    area = geocoder.description_for_number(parsed, "pt") or geocoder.description_for_number(parsed, "en")
    pais = geocoder.country_name_for_number(parsed, "pt") or geocoder.country_name_for_number(parsed, "en")
    tz = timezone.time_zones_for_number(parsed)

    if op:
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"Operadora de origem: {op}",
            source="libphonenumber", source_label="libphonenumber",
            confidence=Confidence.LIKELY,
            detail="Operadora da faixa numérica. Portabilidade pode ter mudado a atual.",
        ))
    if area or pais:
        out.append(Finding(
            kind=FindingKind.ADDRESS, value=", ".join(p for p in [area, pais] if p),
            source="libphonenumber", source_label="libphonenumber",
            confidence=Confidence.LIKELY, detail="Região da numeração",
        ))
    if tz:
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"Fuso horário: {', '.join(tz)}",
            source="libphonenumber", source_label="libphonenumber",
            confidence=Confidence.CONFIRMED, detail="Útil para inferir rotina e horário de contato.",
        ))
    return out


def _numverify(entity: Entity) -> Iterable[Finding]:
    data = net.get_json(
        "http://apilayer.net/api/validate",
        params={"access_key": net.get_key("numverify"),
                "number": entity.get("digits", ""), "format": 1},
        timeout=15,
    ) or {}
    if not data.get("valid"):
        return []
    return [Finding(
        kind=FindingKind.NOTE,
        value=f"NumVerify: {data.get('carrier') or 'operadora n/d'} · {data.get('line_type') or 'tipo n/d'}",
        source="numverify", source_label="NumVerify", confidence=Confidence.CONFIRMED,
        detail=f"Localização: {data.get('location')} — {data.get('country_name')}",
        raw=data,
    )]


# ── DOMÍNIO / IP ────────────────────────────────────────────────────────────

def _rdap_domain(entity: Entity) -> Iterable[Finding]:
    """RDAP é o WHOIS moderno, em JSON e sem rate-limit agressivo."""
    root = entity.get("root") or entity.value
    try:
        data = net.get_json(f"https://rdap.org/domain/{root}", timeout=15)
    except Exception:
        return []
    if not data:
        return []

    out: list[Finding] = []
    for ev in data.get("events") or []:
        action = ev.get("eventAction")
        if action in {"registration", "expiration", "last changed"}:
            rotulo = {"registration": "Registrado em", "expiration": "Expira em",
                      "last changed": "Última alteração"}[action]
            out.append(Finding(
                kind=FindingKind.NOTE, value=f"{rotulo}: {(ev.get('eventDate') or '')[:10]}",
                source="rdap", source_label="RDAP/WHOIS", confidence=Confidence.CONFIRMED,
                detail=f"Registro do domínio {root}",
            ))
    for ent in data.get("entities") or []:
        roles = ", ".join(ent.get("roles") or [])
        vcard = ent.get("vcardArray") or []
        if len(vcard) > 1:
            for item in vcard[1]:
                if not isinstance(item, list) or len(item) < 4:
                    continue
                field_name, value = item[0], item[3]
                if field_name == "fn" and value:
                    out.append(Finding(
                        kind=FindingKind.NAME, value=str(value), source="rdap",
                        source_label="RDAP/WHOIS", confidence=Confidence.LIKELY,
                        detail=f"Contato do domínio ({roles})",
                    ))
                elif field_name == "email" and value:
                    out.append(Finding(
                        kind=FindingKind.EMAIL, value=str(value).lower(), source="rdap",
                        source_label="RDAP/WHOIS", confidence=Confidence.CONFIRMED,
                        detail=f"E-mail de contato do domínio ({roles})",
                    ))
                elif field_name == "tel" and value:
                    out.append(Finding(
                        kind=FindingKind.PHONE, value=str(value), source="rdap",
                        source_label="RDAP/WHOIS", confidence=Confidence.CONFIRMED,
                        detail=f"Telefone de contato do domínio ({roles})",
                    ))
    for ns in data.get("nameservers") or []:
        if ns.get("ldhName"):
            out.append(Finding(
                kind=FindingKind.NOTE, value=f"NS: {ns['ldhName'].lower()}",
                source="rdap", source_label="RDAP/WHOIS", confidence=Confidence.CONFIRMED,
                detail="Servidor de nomes — indica a hospedagem.",
            ))
    return out


def _crtsh(entity: Entity) -> Iterable[Finding]:
    """
    Certificate Transparency: todo subdomínio que já teve certificado TLS.
    É a forma mais completa e gratuita de mapear a superfície de um domínio.
    """
    root = entity.get("root") or entity.value
    try:
        data = net.get_json(
            "https://crt.sh/", params={"q": f"%.{root}", "output": "json"},
            timeout=25, ttl=7 * 24 * 3600,
        )
    except Exception:
        return []
    subs: set[str] = set()
    for row in (data or [])[:800]:
        for name in str(row.get("name_value") or "").split("\n"):
            name = name.strip().lower().lstrip("*.")
            if name.endswith(root) and name != root:
                subs.add(name)
    if not subs:
        return []
    ordered = sorted(subs)
    out = [Finding(
        kind=FindingKind.NOTE, value=f"{len(ordered)} subdomínios em Certificate Transparency",
        source="crtsh", source_label="crt.sh",
        url=f"https://crt.sh/?q=%25.{root}", confidence=Confidence.CONFIRMED,
        detail="Histórico completo de certificados emitidos para o domínio.",
        raw={"subdomains": ordered},
    )]
    for sub in ordered[:40]:
        out.append(Finding(
            kind=FindingKind.DOMAIN, value=sub, source="crtsh",
            source_label="crt.sh", url=f"https://{sub}",
            confidence=Confidence.CONFIRMED, detail="Subdomínio com certificado emitido",
        ))
    return out


def _ip_info(entity: Entity) -> Iterable[Finding]:
    ip = entity.value
    try:
        data = net.get_json(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,regionName,city,isp,org,as,lat,lon,timezone,reverse,proxy,hosting",
                    "lang": "pt-BR"},
            timeout=12,
        )
    except Exception:
        return []
    if not data or data.get("status") != "success":
        return []
    out = [
        Finding(kind=FindingKind.ADDRESS,
                value=f"{data.get('city')}, {data.get('regionName')}, {data.get('country')}",
                source="ipapi", source_label="ip-api", confidence=Confidence.LIKELY,
                detail="Geolocalização aproximada do IP (nível de cidade, sujeito a erro).",
                raw=data),
        Finding(kind=FindingKind.NOTE, value=f"ISP: {data.get('isp')} · {data.get('as')}",
                source="ipapi", source_label="ip-api", confidence=Confidence.CONFIRMED,
                detail=f"Organização: {data.get('org') or 'n/d'}"),
    ]
    if data.get("proxy") or data.get("hosting"):
        out.append(Finding(
            kind=FindingKind.NOTE,
            value="IP de datacenter/VPN/proxy" if data.get("hosting") else "IP marcado como proxy",
            source="ipapi", source_label="ip-api", confidence=Confidence.LIKELY,
            detail="A geolocalização não corresponde à posição real da pessoa.",
        ))
    if data.get("reverse"):
        out.append(Finding(
            kind=FindingKind.DOMAIN, value=str(data["reverse"]), source="ipapi",
            source_label="ip-api (rDNS)", confidence=Confidence.CONFIRMED,
            detail="DNS reverso do IP",
        ))
    return out


# ── registro ────────────────────────────────────────────────────────────────

def register_auto_connectors() -> None:
    E, U, P, D, I = (
        EntityType.EMAIL, EntityType.USERNAME, EntityType.PHONE,
        EntityType.DOMAIN, EntityType.IP,
    )

    register(Connector(
        id="email_infra", label="Infraestrutura do e-mail", mode=Mode.AUTO,
        accepts=(E,), category="email", run=_email_infra,
        description="MX, provedor, descartável e domínio corporativo",
    ))
    register(Connector(
        id="gravatar", label="Gravatar", mode=Mode.AUTO, accepts=(E,),
        category="email", run=_gravatar,
        description="Foto, nome e contas vinculadas ao e-mail",
    ))
    register(Connector(
        id="holehe", label="Holehe", mode=Mode.AUTO, accepts=(E,), category="email",
        run=_holehe, requires_binary="holehe", timeout=100,
        description="Em quais serviços existe conta com este e-mail",
    ))
    register(Connector(
        id="hibp", label="Have I Been Pwned", mode=Mode.AUTO, accepts=(E,),
        category="leaks", run=_hibp, requires_key="hibp", cost="chave",
        description="Vazamentos em que o e-mail apareceu",
    ))
    register(Connector(
        id="hudsonrock_api", label="Hudson Rock (infostealer)", mode=Mode.AUTO,
        accepts=(E, U), category="leaks", run=_hudsonrock,
        description="Máquina infectada por malware com o e-mail/username (grátis)",
    ))
    register(Connector(
        id="hunter", label="Hunter.io", mode=Mode.AUTO, accepts=(D,),
        category="dominio", run=_hunter_domain, requires_key="hunter", cost="chave",
        description="Padrão de e-mail e contatos do domínio",
    ))

    register(Connector(
        id="whatsmyname", label="WhatsMyName", mode=Mode.AUTO,
        accepts=(U, EntityType.PROFILE_URL), category="username", run=_whatsmyname,
        timeout=90, description="Handle em ~90 plataformas (HTTP direto)",
    ))
    register(Connector(
        id="maigret", label="Maigret", mode=Mode.AUTO, accepts=(U,),
        category="username", run=_maigret, requires_binary="maigret", timeout=190,
        description="Varredura ampla de username com extração de perfil",
    ))
    register(Connector(
        id="github", label="GitHub", mode=Mode.AUTO,
        accepts=(U, EntityType.PROFILE_URL), category="username", run=_github_user,
        description="Perfil, e-mail de commit, empresa e localização",
    ))

    # ── Contas por username: fontes gratuitas de JSON (holmes.social) ────────
    from .. import social

    register(Connector(
        id="keybase", label="Keybase", mode=Mode.AUTO,
        accepts=(U, EntityType.PROFILE_URL), category="username",
        run=social.keybase_findings,
        description="Contas ligadas com prova, nome real e cripto do dono",
    ))
    register(Connector(
        id="gitlab", label="GitLab", mode=Mode.AUTO,
        accepts=(U, EntityType.PROFILE_URL), category="username",
        run=social.gitlab_findings,
        description="Perfil público e nome real via API do GitLab",
    ))
    register(Connector(
        id="hackernews", label="Hacker News", mode=Mode.AUTO,
        accepts=(U, EntityType.PROFILE_URL), category="username",
        run=social.hackernews_findings,
        description="Conta, karma e e-mail do 'sobre mim' no HN",
    ))
    register(Connector(
        id="reddit_api", label="Reddit", mode=Mode.AUTO,
        accepts=(U, EntityType.PROFILE_URL), category="username",
        run=social.reddit_findings,
        description="Conta, carma e data de criação do perfil Reddit",
    ))

    register(Connector(
        id="libphonenumber", label="libphonenumber", mode=Mode.AUTO, accepts=(P,),
        category="telefone", run=_phone_lib,
        description="Validade, operadora de origem, região e fuso",
    ))
    register(Connector(
        id="phone_br", label="Numeração BR", mode=Mode.AUTO, accepts=(P,),
        category="telefone", run=br.phone_br_findings,
        description="DDD, tipo de linha e link direto do WhatsApp",
    ))
    register(Connector(
        id="numverify", label="NumVerify", mode=Mode.AUTO, accepts=(P,),
        category="telefone", run=_numverify, requires_key="numverify", cost="chave",
        description="Operadora atual e tipo de linha",
    ))

    register(Connector(
        id="receita_cnpj", label="Receita Federal (CNPJ)", mode=Mode.AUTO,
        accepts=(EntityType.CNPJ,), category="brasil", run=br.cnpj_findings,
        description="Razão social, endereço, contatos e quadro societário",
    ))

    # ── Sanções/PEP no mundo todo + Wikipédia/Wikidata ──────────────────────
    from .. import sanctions, wiki

    # Disponível se o índice LOCAL gratuito foi baixado OU se há chave da API
    # paga como reserva — nunca falha em silêncio quando nenhum dos dois existe.
    class _OpenSanctionsConnector(Connector):
        def availability(self):
            from .. import opensanctions_bulk as bulk

            if bulk.disponivel() or net.has_key("opensanctions"):
                return True, None
            return False, (
                "índice local não baixado (rode: python -m holmes.opensanctions_bulk "
                "--update) e OPENSANCTIONS_API_KEY não configurada"
            )

    register(_OpenSanctionsConnector(
        id="opensanctions", label="OpenSanctions (sanções e PEP globais)",
        mode=Mode.AUTO, accepts=(EntityType.NAME, EntityType.CNPJ),
        category="juridico", run=sanctions.opensanctions_findings, timeout=15,
        description="OFAC, ONU, UE, INTERPOL e PEP de dezenas de países — via índice local grátis "
                     "(python -m holmes.opensanctions_bulk --update) ou chave paga como reserva",
    ))
    register(Connector(
        id="wikipedia", label="Wikipédia / Wikidata", mode=Mode.AUTO,
        accepts=(EntityType.NAME,), category="perfil", run=wiki.wiki_findings,
        timeout=25,
        description="Biografia, foto oficial, data de nascimento e cargos — grátis, sem chave",
    ))

    # ── Brasil: fontes oficiais e abertas ──────────────────────────────────
    from .. import br_auto
    from ..cnj import processo_findings

    register(Connector(
        id="datajud", label="DataJud (CNJ)", mode=Mode.AUTO,
        accepts=(EntityType.PROCESSO,), category="brasil", run=processo_findings,
        timeout=40,
        description="Decodifica o número e traz a movimentação oficial do processo",
    ))
    register(Connector(
        id="congresso", label="Câmara e Senado (PEP)", mode=Mode.AUTO,
        accepts=(EntityType.NAME,), category="brasil", run=br_auto.congresso_findings,
        timeout=35,
        description="Detecta se o alvo é deputado federal ou senador",
    ))
    register(Connector(
        id="querido_diario", label="Querido Diário", mode=Mode.AUTO,
        accepts=(EntityType.NAME, EntityType.CNPJ), category="brasil",
        run=br_auto.querido_diario_findings, timeout=40,
        description="Diários oficiais de 3.000+ municípios",
    ))
    register(Connector(
        id="registrobr", label="Registro.br", mode=Mode.AUTO,
        accepts=(D,), category="brasil", run=br_auto.registrobr_findings,
        description="Titular e documento de domínio .br",
    ))
    register(Connector(
        id="portal_nome", label="Portal da Transparência (nome)", mode=Mode.AUTO,
        accepts=(EntityType.NAME,), category="brasil", run=br_auto.portal_nome_findings,
        requires_key="portal_transparencia", cost="chave", timeout=45,
        description="PEP, sanção (CEIS/CNEP) e servidor público federal",
    ))
    register(Connector(
        id="portal_cpf", label="Portal da Transparência (CPF)", mode=Mode.AUTO,
        accepts=(EntityType.CPF,), category="brasil", run=br_auto.portal_cpf_findings,
        requires_key="portal_transparencia", cost="chave", timeout=35,
        description="Cruza o CPF com PEP e listas de sanção",
    ))
    register(Connector(
        id="portal_cnpj", label="Portal da Transparência (CNPJ)", mode=Mode.AUTO,
        accepts=(EntityType.CNPJ,), category="brasil", run=br_auto.portal_cnpj_findings,
        requires_key="portal_transparencia", cost="chave", timeout=35,
        description="Sanções federais da pessoa jurídica",
    ))
    register(Connector(
        id="rdap", label="RDAP / WHOIS", mode=Mode.AUTO, accepts=(D,),
        category="dominio", run=_rdap_domain,
        description="Titular, datas de registro e servidores de nomes",
    ))
    register(Connector(
        id="crtsh", label="crt.sh (Certificate Transparency)", mode=Mode.AUTO,
        accepts=(D,), category="dominio", run=_crtsh, timeout=35,
        description="Todos os subdomínios que já tiveram certificado",
    ))
    register(Connector(
        id="ipapi", label="ip-api", mode=Mode.AUTO, accepts=(I,),
        category="rede", run=_ip_info,
        description="Geolocalização, ISP, rDNS e detecção de VPN/datacenter",
    ))

    # ── Rastreamento de site (clearnet e .onion) ───────────────────────────
    # Opt-in: é a única fonte que gera muitas requisições ao alvo, então só
    # roda quando você liga nos ajustes. Fora disso aparece como "pulado".
    from .. import crawler

    class _CrawlConnector(Connector):
        def availability(self):
            if not crawler.is_enabled():
                return False, "rastreamento desligado (ative em «Ajustes da investigação»)"
            return super().availability()

    register(_CrawlConnector(
        id="crawler", label="Rastreamento do site", mode=Mode.AUTO,
        accepts=(EntityType.URL, D), category="rastreamento",
        run=crawler.crawl_findings, timeout=300,
        description="Percorre o site e extrai e-mail, telefone, cripto e perfis",
    ))

    # URL com caminho também merece as fontes de domínio e a busca.
    for cid in ("rdap", "crtsh", "registrobr", "hunter"):
        conn = _REGISTRY_GET(cid)
        if conn and EntityType.URL not in conn.accepts:
            conn.accepts = conn.accepts + (EntityType.URL,)


def _REGISTRY_GET(cid: str):
    from .base import get_connector

    return get_connector(cid)
