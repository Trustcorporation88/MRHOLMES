"""
LinkedIn e Instagram pelos coletores prontos da Bright Data.

As duas redes escondem o perfil de quem não está logado, e é por isso que o
motor só conseguia devolver o link. Os coletores da Bright Data (Web Scraper
API) devolvem o perfil estruturado a partir da URL: nome, cargo, empresa
atual, experiência, cidade, bio, seguidores e contato comercial.

Rotas de entrada:
* link de perfil colado na caixa (linkedin.com/in/…, linkedin.com/company/…,
  instagram.com/…);
* username: testa instagram.com/<handle>;
* nome: acha a URL do LinkedIn pela busca de superfície (1 consulta) e só
  coleta se o título do resultado bater com o nome.

Cada coleta é cobrada por registro. Tudo fica atrás de HOLMES_BRD_DATASETS=1,
com teto por processo e cache de 7 dias.
"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

from . import net
from .br_auto import _mesma_pessoa
from .entity import Entity, EntityType
from .findings import Confidence, Finding, FindingKind

LI_LABEL = "LinkedIn (coletor Bright Data)"
IG_LABEL = "Instagram (coletor Bright Data)"
_HANDLE_IG_RE = re.compile(r"^[a-z0-9._]{1,30}$")


def _host(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def _linkedin_tipo(url: str) -> str | None:
    if "linkedin.com" not in _host(url):
        return None
    path = urlparse(url).path.lower()
    if path.startswith("/in/"):
        return "linkedin_person"
    if path.startswith("/company/"):
        return "linkedin_company"
    return None


def _txt(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, dict):
        return str(valor.get("name") or valor.get("title") or "")
    return str(valor).strip()


# ── LinkedIn ────────────────────────────────────────────────────────────────

def _linkedin_pessoa(reg: dict, url: str, conf: Confidence) -> list[Finding]:
    out: list[Finding] = []
    nome = _txt(reg.get("name")) or " ".join(
        p for p in (_txt(reg.get("first_name")), _txt(reg.get("last_name"))) if p)
    perfil = reg.get("url") or reg.get("input_url") or url

    out.append(Finding(
        kind=FindingKind.ACCOUNT, value=perfil, source="brd_linkedin", source_label=LI_LABEL,
        url=perfil, confidence=conf,
        detail=" · ".join(p for p in [
            nome, _txt(reg.get("position")),
            f"{reg.get('followers')} seguidores" if reg.get("followers") else "",
            f"{reg.get('connections')} conexões" if reg.get("connections") else "",
        ] if p),
        raw={"platform": "linkedin"},
    ))
    if nome:
        out.append(Finding(kind=FindingKind.NAME, value=nome, source="brd_linkedin",
                           source_label=LI_LABEL, url=perfil, confidence=conf,
                           detail="Nome exibido no perfil do LinkedIn"))
    cidade = _txt(reg.get("city")) or _txt(reg.get("location"))
    if cidade:
        out.append(Finding(kind=FindingKind.ADDRESS, value=cidade, source="brd_linkedin",
                           source_label=LI_LABEL, url=perfil, confidence=Confidence.POSSIBLE,
                           detail="Cidade declarada no LinkedIn"))
    atual = reg.get("current_company") or {}
    atual_nome = _txt(atual) or _txt(reg.get("current_company_name"))
    if atual_nome:
        out.append(Finding(kind=FindingKind.COMPANY, value=atual_nome, source="brd_linkedin",
                           source_label=LI_LABEL, url=(atual.get("link") if isinstance(atual, dict) else None) or perfil,
                           confidence=conf, detail="Empresa atual no LinkedIn"))
    for exp in (reg.get("experience") or [])[:6]:
        if not isinstance(exp, dict):
            continue
        empresa = _txt(exp.get("company")) or _txt(exp.get("company_name"))
        if not empresa or empresa == atual_nome:
            continue
        periodo = " a ".join(p for p in (_txt(exp.get("start_date")), _txt(exp.get("end_date"))) if p)
        out.append(Finding(kind=FindingKind.COMPANY, value=empresa, source="brd_linkedin",
                           source_label=LI_LABEL, url=perfil, confidence=Confidence.POSSIBLE,
                           detail=", ".join(p for p in ["Experiência", _txt(exp.get("title")), periodo] if p)))
    formacao = [
        ", ".join(p for p in (_txt(e.get("title")), _txt(e.get("degree")),
                             _txt(e.get("start_year")), _txt(e.get("end_year"))) if p)
        for e in (reg.get("education") or [])[:4] if isinstance(e, dict)
    ]
    formacao = [f for f in formacao if f]
    if formacao:
        out.append(Finding(kind=FindingKind.NOTE, value="Formação: " + "; ".join(formacao),
                           source="brd_linkedin", source_label=LI_LABEL, url=perfil,
                           confidence=conf))
    sobre = _txt(reg.get("about"))
    if sobre:
        out.append(Finding(kind=FindingKind.NOTE, value="Sobre (LinkedIn)", source="brd_linkedin",
                           source_label=LI_LABEL, url=perfil, confidence=conf, detail=sobre[:500]))
    foto = _txt(reg.get("avatar")) or _txt(reg.get("image"))
    if foto.startswith("http"):
        out.append(Finding(kind=FindingKind.IMAGE, value=foto, source="brd_linkedin",
                           source_label=LI_LABEL, url=perfil, confidence=conf,
                           detail="Foto do perfil no LinkedIn"))
    return out


def _linkedin_empresa(reg: dict, url: str) -> list[Finding]:
    perfil = reg.get("url") or url
    nome = _txt(reg.get("name"))
    out = [Finding(
        kind=FindingKind.ACCOUNT, value=perfil, source="brd_linkedin", source_label=LI_LABEL,
        url=perfil, confidence=Confidence.CONFIRMED,
        detail=" · ".join(p for p in [
            nome, _txt(reg.get("industries")),
            f"{reg.get('employees_in_linkedin')} funcionários no LinkedIn" if reg.get("employees_in_linkedin") else "",
            _txt(reg.get("company_size")),
        ] if p),
        raw={"platform": "linkedin"},
    )]
    if nome:
        out.append(Finding(kind=FindingKind.COMPANY, value=nome, source="brd_linkedin",
                           source_label=LI_LABEL, url=perfil, confidence=Confidence.CONFIRMED,
                           detail=_txt(reg.get("headquarters"))))
    site = _txt(reg.get("website"))
    if site:
        dominio = _host(site if "://" in site else f"https://{site}").replace("www.", "")
        if dominio:
            out.append(Finding(kind=FindingKind.DOMAIN, value=dominio, source="brd_linkedin",
                               source_label=LI_LABEL, url=perfil, confidence=Confidence.CONFIRMED,
                               detail="Site declarado na página da empresa"))
    for pessoa in (reg.get("employees") or [])[:8]:
        if isinstance(pessoa, dict) and _txt(pessoa.get("title")):
            out.append(Finding(kind=FindingKind.NOTE,
                               value=f"Funcionário no LinkedIn: {_txt(pessoa.get('title'))}",
                               source="brd_linkedin", source_label=LI_LABEL,
                               url=pessoa.get("link") or perfil, confidence=Confidence.POSSIBLE,
                               detail=_txt(pessoa.get("subtitle"))))
    return out


def _url_linkedin_por_nome(nome: str) -> str | None:
    """Uma busca `"nome" site:linkedin.com/in`; só aceita título com o mesmo nome."""
    from . import serp

    for hit in serp.search(f'"{nome}" site:linkedin.com/in', limit=5):
        if _linkedin_tipo(hit.url) != "linkedin_person":
            continue
        titulo = re.split(r"\s[-–|]\s", hit.title or "")[0]
        if _mesma_pessoa(nome, titulo):
            return hit.url.split("?")[0]
    return None


def linkedin_findings(entity: Entity) -> Iterable[Finding]:
    if entity.type is EntityType.PROFILE_URL:
        url = entity.value
        tipo = _linkedin_tipo(url)
        if not tipo:
            return []
        conf = Confidence.CONFIRMED
    elif entity.type is EntityType.NAME:
        url = _url_linkedin_por_nome(entity.value)
        if not url:
            return []
        tipo, conf = "linkedin_person", Confidence.LIKELY
    else:
        return []

    reg = net.brd_dataset_scrape(tipo, url)
    if not reg:
        return []
    if tipo == "linkedin_company":
        return _linkedin_empresa(reg, url)
    achados = _linkedin_pessoa(reg, url, conf)
    if entity.type is EntityType.NAME:
        nome_perfil = next((f.value for f in achados if f.kind is FindingKind.NAME), "")
        if nome_perfil and not _mesma_pessoa(entity.value, nome_perfil):
            return []  # o resultado de busca enganou: perfil é de outra pessoa
    return achados


# ── Instagram ───────────────────────────────────────────────────────────────

def instagram_findings(entity: Entity) -> Iterable[Finding]:
    if entity.type is EntityType.PROFILE_URL:
        if "instagram.com" not in _host(entity.value):
            return []
        handle = entity.get("handle") or ""
    elif entity.type is EntityType.USERNAME:
        handle = (entity.get("handle") or entity.value).lstrip("@").lower()
    else:
        return []
    if not _HANDLE_IG_RE.match(handle or ""):
        return []
    url = f"https://www.instagram.com/{handle}/"

    reg = net.brd_dataset_scrape("instagram_profile", url)
    if not reg:
        return []

    perfil = reg.get("profile_url") or reg.get("url") or url
    nome = _txt(reg.get("full_name")) or _txt(reg.get("profile_name"))
    seguidores = reg.get("followers")
    out: list[Finding] = [Finding(
        kind=FindingKind.ACCOUNT, value=perfil, source="brd_instagram", source_label=IG_LABEL,
        url=perfil, confidence=Confidence.CONFIRMED,
        detail=" · ".join(p for p in [
            nome,
            f"{seguidores} seguidores" if seguidores is not None else "",
            f"{reg.get('posts_count')} posts" if reg.get("posts_count") is not None else "",
            "verificado" if reg.get("is_verified") else "",
            "privado" if reg.get("is_private") else "",
            _txt(reg.get("business_category_name")) or _txt(reg.get("category_name")),
        ] if p),
        raw={"platform": "instagram"},
    )]
    if nome:
        # Nome de exibição no Instagram é texto livre: pode ser apelido.
        out.append(Finding(kind=FindingKind.NAME, value=nome, source="brd_instagram",
                           source_label=IG_LABEL, url=perfil, confidence=Confidence.LIKELY,
                           detail="Nome de exibição no Instagram"))
    bio = _txt(reg.get("biography"))
    if bio:
        out.append(Finding(kind=FindingKind.NOTE, value="Bio do Instagram", source="brd_instagram",
                           source_label=IG_LABEL, url=perfil, confidence=Confidence.CONFIRMED,
                           detail=bio[:500]))
    for campo in ("business_email", "email_address", "public_email"):
        email = _txt(reg.get(campo))
        if "@" in email:
            out.append(Finding(kind=FindingKind.EMAIL, value=email.lower(), source="brd_instagram",
                               source_label=IG_LABEL, url=perfil, confidence=Confidence.CONFIRMED,
                               detail="E-mail comercial exposto no perfil"))
            break
    for campo in ("business_phone_number", "phone_number", "public_phone_number"):
        tel = _txt(reg.get(campo))
        if len(re.sub(r"\D", "", tel)) >= 10:
            out.append(Finding(kind=FindingKind.PHONE, value=tel, source="brd_instagram",
                               source_label=IG_LABEL, url=perfil, confidence=Confidence.CONFIRMED,
                               detail="Telefone comercial exposto no perfil"))
            break
    externo = reg.get("external_url")
    if isinstance(externo, list):
        externo = externo[0] if externo else ""
    externo = _txt(externo)
    if externo.startswith("http"):
        out.append(Finding(kind=FindingKind.NOTE, value=f"Link na bio: {externo}",
                           source="brd_instagram", source_label=IG_LABEL, url=externo,
                           confidence=Confidence.CONFIRMED))
    foto = _txt(reg.get("profile_image_link")) or _txt(reg.get("profile_pic_url"))
    if foto.startswith("http"):
        out.append(Finding(kind=FindingKind.IMAGE, value=foto, source="brd_instagram",
                           source_label=IG_LABEL, url=perfil, confidence=Confidence.CONFIRMED,
                           detail="Foto do perfil no Instagram"))
    return out
