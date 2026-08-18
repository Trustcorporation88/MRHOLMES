"""
Motor de pivô.

É o que separa "rodar 10 ferramentas" de "investigar". Um achado vira o
próximo alvo: e-mail → username → perfil → nome real → telefone → empresa.

Cada pivô carrega o motivo pelo qual foi criado, para o dossiê poder mostrar
a cadeia de raciocínio em vez de um monte de dado solto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .entity import Entity, EntityType, detect
from .findings import Finding, FindingKind

# Quantos alvos derivados aceitar por salto — trava contra explosão combinatória.
MAX_PIVOTS_PER_HOP = 6


@dataclass
class Pivot:
    entity: Entity
    reason: str
    origin: str           # id do conector que gerou
    hop: int = 1
    score: float = 0.5    # prioridade de execução

    @property
    def key(self) -> str:
        return f"{self.entity.type.value}:{self.entity.value.lower()}"


def _name_looks_real(value: str) -> bool:
    """Filtra 'Perfil', 'Home', 'Login' e outros lixos que vêm de título de página."""
    v = (value or "").strip()
    if len(v) < 5 or len(v) > 70:
        return False
    if not re.match(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.\- ]+$", v):
        return False
    tokens = [t for t in v.split() if len(t) > 1]
    if len(tokens) < 2:
        return False
    lixo = {"perfil", "profile", "home", "login", "sign", "user", "usuario",
            "página", "pagina", "page", "search", "busca", "resultado"}
    return not any(t.lower() in lixo for t in tokens)


def _from_email(entity: Entity) -> list[Pivot]:
    out: list[Pivot] = []
    handle = entity.get("username_guess")
    if handle and len(handle) >= 3:
        out.append(Pivot(
            entity=detect(handle), origin="pivot:email",
            reason=f"Local-part de {entity.value} testado como username",
            score=0.8,
        ))
    domain = entity.get("domain")
    if domain and domain not in {
        "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.com.br",
        "live.com", "icloud.com", "bol.com.br", "uol.com.br", "terra.com.br",
        "protonmail.com", "proton.me",
    }:
        out.append(Pivot(
            entity=detect(domain), origin="pivot:email",
            reason=f"Domínio corporativo de {entity.value} — identifica a organização",
            score=0.7,
        ))
    return out


def _from_username(entity: Entity) -> list[Pivot]:
    handle = entity.get("handle") or entity.value
    # Só chuta e-mail se o handle for específico o bastante para não gerar ruído.
    if len(handle) < 6:
        return []
    return [Pivot(
        entity=detect(f"{handle}@gmail.com"), origin="pivot:username",
        reason=f"Hipótese de e-mail a partir do handle @{handle} (verificar antes de usar)",
        score=0.3,
    )]


def _from_name(entity: Entity) -> list[Pivot]:
    out: list[Pivot] = []
    for guess in (entity.get("username_guesses") or [])[:3]:
        if len(guess) >= 5:
            out.append(Pivot(
                entity=detect(guess), origin="pivot:nome",
                reason=f"Handle provável formado a partir de «{entity.value}»",
                score=0.45,
            ))
    return out


def _from_cnpj(entity: Entity) -> list[Pivot]:
    return []  # os sócios chegam como finding NAME e são tratados abaixo


def from_entity(entity: Entity) -> list[Pivot]:
    """Pivôs derivados só da forma do alvo, antes de qualquer consulta."""
    fn = {
        EntityType.EMAIL: _from_email,
        EntityType.USERNAME: _from_username,
        EntityType.NAME: _from_name,
        EntityType.CNPJ: _from_cnpj,
    }.get(entity.type)
    return fn(entity) if fn else []


def from_findings(findings: list[Finding], hop: int) -> list[Pivot]:
    """
    Pivôs derivados do que as fontes acharam. Aqui está o ganho real: um
    e-mail confirmado no Gravatar ou um sócio na Receita viram alvo novo.
    """
    out: list[Pivot] = []

    for f in findings:
        if f.kind is FindingKind.EMAIL and "@" in f.value:
            out.append(Pivot(
                entity=detect(f.value), origin=f.source, hop=hop,
                reason=f"E-mail encontrado por {f.source_label}",
                score=0.7 if f.confidence.value == "confirmada" else 0.45,
            ))

        elif f.kind is FindingKind.NAME and _name_looks_real(f.value):
            out.append(Pivot(
                entity=detect(f.value), origin=f.source, hop=hop,
                reason=f.detail or f"Nome informado por {f.source_label}",
                score=0.65 if f.confidence.value == "confirmada" else 0.4,
            ))

        elif f.kind is FindingKind.PHONE:
            digits = re.sub(r"\D", "", f.value)
            if 10 <= len(digits) <= 15:
                out.append(Pivot(
                    entity=detect(f.value), origin=f.source, hop=hop,
                    reason=f"Telefone encontrado por {f.source_label}",
                    score=0.6,
                ))

        elif f.kind is FindingKind.ACCOUNT and f.url:
            # Perfil achado vira handle a ser testado nas outras plataformas.
            ent = detect(f.url)
            if ent.type is EntityType.PROFILE_URL and ent.get("handle"):
                handle_ent = detect(ent.get("handle"))
                if handle_ent.type is EntityType.USERNAME:
                    out.append(Pivot(
                        entity=handle_ent, origin=f.source, hop=hop,
                        reason=f"Handle @{ent.get('handle')} extraído de perfil em {ent.get('platform')}",
                        score=0.55,
                    ))

        elif f.kind is FindingKind.DOMAIN and hop <= 1:
            ent = detect(f.value)
            if ent.type is EntityType.DOMAIN:
                out.append(Pivot(
                    entity=ent, origin=f.source, hop=hop,
                    reason=f"Domínio associado, via {f.source_label}",
                    score=0.35,
                ))

    return out


def dedupe_and_rank(
    pivots: list[Pivot], already_seen: set[str], limit: int = MAX_PIVOTS_PER_HOP
) -> list[Pivot]:
    """Tira repetido, tira o que já foi investigado, e fica com os mais promissores."""
    best: dict[str, Pivot] = {}
    for p in pivots:
        if not p.entity.value or p.entity.type is EntityType.UNKNOWN:
            continue
        if p.key in already_seen:
            continue
        current = best.get(p.key)
        if not current or p.score > current.score:
            best[p.key] = p
    ranked = sorted(best.values(), key=lambda p: p.score, reverse=True)
    return ranked[:limit]
