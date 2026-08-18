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

from .entity import Entity, EntityType, detect, strip_accents
from .findings import Confidence, Finding, FindingKind

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


def _tokens_alvo(entity: Entity | None) -> list[str]:
    """Radicais do alvo que servem para medir parentesco de um handle."""
    if entity is None:
        return []
    brutos: list[str] = []
    if entity.type is EntityType.NAME:
        brutos = list(entity.get("tokens") or [])
    elif entity.type is EntityType.EMAIL:
        brutos = [entity.get("username_guess") or "", entity.get("local") or ""]
    elif entity.type is EntityType.USERNAME:
        brutos = [entity.get("handle") or entity.value]
    elif entity.type is EntityType.DOMAIN:
        brutos = [(entity.get("root") or entity.value).split(".")[0]]
    else:
        brutos = [entity.value]

    saida: list[str] = []
    for t in brutos:
        t = re.sub(r"[^a-z0-9]", "", strip_accents(str(t)).lower())
        if len(t) >= 4:
            saida.append(t)
    return saida


def _parentesco(handle: str, entity: Entity | None) -> bool:
    """
    O handle tem alguma relação com o alvo?

    Sem esta trava, um resultado de busca que só MENCIONA o alvo faz o motor
    varrer 90 sites com o handle de outra entidade — foi exatamente o que
    aconteceu com `github.com/abjur` numa busca por "Benedita da Silva":
    144 perfis de uma associação sem nenhum vínculo com a pessoa.
    """
    alvo = _tokens_alvo(entity)
    if not alvo:
        return False
    h = re.sub(r"[^a-z0-9]", "", strip_accents(handle or "").lower())
    if len(h) < 3:
        return False
    for token in alvo:
        # Nome inteiro dentro do handle: "blogdabenedita" ⊃ "benedita".
        if token in h or h in token:
            return True
        # Abreviação plausível: "instadabene" contém "bene", prefixo de "benedita".
        if len(token) >= 6 and token[:4] in h:
            return True
    return False


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


def from_findings(
    findings: list[Finding], hop: int, target: Entity | None = None
) -> list[Pivot]:
    """
    Pivôs derivados do que as fontes acharam. Aqui está o ganho real: um
    e-mail confirmado no Gravatar ou um sócio na Receita viram alvo novo.

    A trava central: achado que veio de resultado de busca só vira alvo novo
    se tiver parentesco com o alvo original. Resultado de busca prova que uma
    página MENCIONA o alvo — não prova que aquele perfil é dele.
    """
    out: list[Pivot] = []

    for f in findings:
        confirmado = f.confidence is Confidence.CONFIRMED
        # "serp:serper", "serp:brave"… — associação por menção, não por vínculo.
        de_busca = f.source.startswith("serp")

        if f.kind is FindingKind.EMAIL and "@" in f.value:
            local = f.value.split("@")[0]
            if de_busca and not _parentesco(local, target):
                continue  # e-mail de contato da página, não do alvo
            out.append(Pivot(
                entity=detect(f.value), origin=f.source, hop=hop,
                reason=f"E-mail encontrado por {f.source_label}",
                score=0.7 if confirmado else 0.45,
            ))

        elif f.kind is FindingKind.NAME and _name_looks_real(f.value):
            # Nome só pivota se a fonte afirmou o vínculo (sócio na Receita,
            # perfil do próprio alvo). Nome tirado de página é homônimo em potencial.
            if not confirmado and not _parentesco(f.value.replace(" ", ""), target):
                continue
            out.append(Pivot(
                entity=detect(f.value), origin=f.source, hop=hop,
                reason=f.detail or f"Nome informado por {f.source_label}",
                score=0.65 if confirmado else 0.4,
            ))

        elif f.kind is FindingKind.PHONE:
            digits = re.sub(r"\D", "", f.value)
            if de_busca and not confirmado:
                continue  # telefone que aparece na página não é o do alvo
            if 10 <= len(digits) <= 15:
                out.append(Pivot(
                    entity=detect(f.value), origin=f.source, hop=hop,
                    reason=f"Telefone encontrado por {f.source_label}",
                    score=0.6,
                ))

        elif f.kind is FindingKind.ACCOUNT and f.url:
            # Perfil achado vira handle a ser testado nas outras plataformas —
            # mas só se o handle puxar para o alvo. É aqui que o motor derrapava.
            ent = detect(f.url)
            handle = ent.get("handle") if ent.type is EntityType.PROFILE_URL else None
            if not handle:
                continue
            if not confirmado and not _parentesco(handle, target):
                continue
            handle_ent = detect(handle)
            if handle_ent.type is EntityType.USERNAME:
                out.append(Pivot(
                    entity=handle_ent, origin=f.source, hop=hop,
                    reason=f"Handle @{handle} extraído de perfil em {ent.get('platform')}",
                    score=0.55 if confirmado else 0.45,
                ))

        elif f.kind is FindingKind.DOMAIN and hop <= 1:
            # Domínio só pivota quando a fonte o amarra ao alvo (MX do e-mail
            # dele, titular do .br). Domínio de resultado de busca é ruído.
            if de_busca or not confirmado:
                continue
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
