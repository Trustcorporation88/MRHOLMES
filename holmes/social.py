"""
Fontes gratuitas de conta por username — todas HTTP puro, sem chave, sem binário.

Complementam o WhatsMyName e o GitHub (que já existem em connectors/auto.py)
com APIs públicas que devolvem JSON estruturado e, de quebra, entregam nome
real, cripto e provas de outras contas do mesmo dono.

- Keybase: a mais rica. Prova, assinada pelo próprio dono, de que aquele
  username também controla tal Twitter/GitHub/Reddit/site — e ainda lista
  endereços de cripto. Confirmação forte de identidade.
- GitLab: perfil público via API v4, com nome real.
- Hacker News: conta e "sobre mim" via API da Algolia.
- Reddit: conta, carma e data de criação via about.json.

Nenhuma destas grava conteúdo de página; só o dado estruturado do perfil.
"""

from __future__ import annotations

from typing import Iterable

from . import net
from .entity import Entity, EntityType
from .findings import Confidence, Finding, FindingKind

# Prova do Keybase → como o dossiê deve nomear a conta.
_KEYBASE_PROOFS = {
    "twitter": "X/Twitter", "github": "GitHub", "reddit": "Reddit",
    "hackernews": "Hacker News", "mastodon": "Mastodon", "generic_web_site": "Site",
    "dns": "Domínio", "facebook": "Facebook",
}


def _handle(entity: Entity) -> str:
    return (entity.get("handle") or entity.get("username_guess") or entity.value or "").strip()


def keybase_findings(entity: Entity) -> Iterable[Finding]:
    """
    Keybase amarra o username a outras contas com prova criptográfica e ainda
    entrega cripto do dono. É o achado de identidade mais forte que existe grátis.
    """
    handle = _handle(entity)
    if not handle:
        return []
    try:
        data = net.get_json(
            "https://keybase.io/_/api/1.0/user/lookup.json",
            params={
                "usernames": handle,
                "fields": "basics,profile,proofs_summary,cryptocurrency_addresses",
            },
            timeout=15, ttl=12 * 3600,
        ) or {}
    except Exception:
        return []

    them = data.get("them") or []
    user = them[0] if them else None
    if not user:
        return []

    url = f"https://keybase.io/{handle}"
    out: list[Finding] = [Finding(
        kind=FindingKind.ACCOUNT, value=f"Keybase: {handle}",
        source="keybase", source_label="Keybase", url=url,
        confidence=Confidence.CONFIRMED,
        detail="Conta Keybase existe — as contas ligadas abaixo têm prova assinada pelo dono.",
    )]

    profile = (user.get("profile") or {})
    nome = (profile.get("full_name") or "").strip()
    if nome:
        out.append(Finding(
            kind=FindingKind.NAME, value=nome, source="keybase",
            source_label="Keybase", url=url, confidence=Confidence.LIKELY,
            detail="Nome declarado no perfil Keybase",
        ))
    local = (profile.get("location") or "").strip()
    if local:
        out.append(Finding(
            kind=FindingKind.ADDRESS, value=local, source="keybase",
            source_label="Keybase", url=url, confidence=Confidence.POSSIBLE,
            detail="Localização declarada no Keybase",
        ))

    proofs = ((user.get("proofs_summary") or {}).get("all")) or []
    for proof in proofs:
        tipo = proof.get("proof_type") or ""
        nome_serv = _KEYBASE_PROOFS.get(tipo, tipo.title() or "Conta")
        nomeval = proof.get("nametag") or proof.get("service_url") or ""
        if not nomeval:
            continue
        out.append(Finding(
            kind=FindingKind.ACCOUNT, value=f"{nome_serv}: {nomeval}",
            source="keybase", source_label="Keybase (prova ligada)",
            url=proof.get("service_url") or proof.get("proof_url"),
            confidence=Confidence.CONFIRMED,
            detail=f"O dono do Keybase @{handle} provou controlar esta conta {nome_serv}.",
        ))

    cryptos = user.get("cryptocurrency_addresses") or {}
    for moeda, enderecos in cryptos.items():
        sigla = {"bitcoin": "BTC", "zcash": "ZEC"}.get(moeda, moeda.upper())
        for item in enderecos or []:
            addr = item.get("address") if isinstance(item, dict) else str(item)
            if addr:
                out.append(Finding(
                    kind=FindingKind.CRYPTO, value=f"{sigla}: {addr}",
                    source="keybase", source_label="Keybase", url=url,
                    confidence=Confidence.CONFIRMED,
                    detail=f"Endereço {sigla} publicado no Keybase por @{handle}.",
                ))
    return out


def gitlab_findings(entity: Entity) -> Iterable[Finding]:
    """Perfil público do GitLab pela API v4 — nome real e link do perfil."""
    handle = _handle(entity)
    if not handle:
        return []
    try:
        data = net.get_json(
            "https://gitlab.com/api/v4/users",
            params={"username": handle}, timeout=12, ttl=12 * 3600,
        ) or []
    except Exception:
        return []
    if not isinstance(data, list) or not data:
        return []

    u = data[0]
    url = u.get("web_url") or f"https://gitlab.com/{handle}"
    out: list[Finding] = [Finding(
        kind=FindingKind.ACCOUNT, value=f"GitLab: @{u.get('username') or handle}",
        source="gitlab", source_label="GitLab API", url=url,
        confidence=Confidence.CONFIRMED,
        detail="Conta GitLab pública confirmada pela API.",
    )]
    if u.get("name"):
        out.append(Finding(
            kind=FindingKind.NAME, value=str(u["name"]), source="gitlab",
            source_label="GitLab API", url=url, confidence=Confidence.LIKELY,
            detail="Nome declarado no perfil GitLab",
        ))
    return out


def hackernews_findings(entity: Entity) -> Iterable[Finding]:
    """Conta e 'sobre mim' no Hacker News, via API pública da Algolia."""
    handle = _handle(entity)
    if not handle:
        return []
    try:
        data = net.get_json(
            f"https://hn.algolia.com/api/v1/users/{handle}",
            timeout=12, ttl=12 * 3600,
        ) or {}
    except Exception:
        return []
    if not data or not data.get("username"):
        return []

    url = f"https://news.ycombinator.com/user?id={handle}"
    out: list[Finding] = [Finding(
        kind=FindingKind.ACCOUNT, value=f"Hacker News: {data['username']}",
        source="hackernews", source_label="Hacker News", url=url,
        confidence=Confidence.CONFIRMED,
        detail=f"Karma {data.get('karma', 0)}. Conta HN confirmada.",
    )]
    about = (data.get("about") or "").strip()
    if about:
        import re

        for mail in set(re.findall(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", about.lower())):
            out.append(Finding(
                kind=FindingKind.EMAIL, value=mail, source="hackernews",
                source_label="Hacker News (bio)", url=url,
                confidence=Confidence.POSSIBLE, detail="E-mail no 'sobre mim' do HN",
            ))
    return out


def reddit_findings(entity: Entity) -> Iterable[Finding]:
    """Conta do Reddit: carma e data de criação via about.json."""
    handle = _handle(entity)
    if not handle:
        return []
    try:
        data = net.get_json(
            f"https://www.reddit.com/user/{handle}/about.json",
            headers={"User-Agent": "MrHolmes-OSINT/1.0"},
            timeout=12, ttl=6 * 3600,
        ) or {}
    except Exception:
        return []
    d = (data.get("data") or {})
    if not d.get("name"):
        return []

    import datetime as _dt

    criado = ""
    if d.get("created_utc"):
        try:
            criado = _dt.datetime.fromtimestamp(
                d["created_utc"], _dt.timezone.utc
            ).strftime("%Y-%m-%d")
        except Exception:
            criado = ""
    url = f"https://www.reddit.com/user/{d['name']}"
    karma = (d.get("total_karma") or (d.get("link_karma", 0) + d.get("comment_karma", 0)))
    return [Finding(
        kind=FindingKind.ACCOUNT, value=f"Reddit: u/{d['name']}",
        source="reddit", source_label="Reddit", url=url,
        confidence=Confidence.CONFIRMED,
        detail=f"Carma {karma}" + (f", conta criada em {criado}." if criado else "."),
        raw={"created": criado},
    )]
