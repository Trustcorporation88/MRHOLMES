"""
Wikipédia e Wikidata — biografia, foto oficial, nascimento e cargos.

Só faz achado quando o alvo já é publicamente conhecido (político,
empresário, artista, atleta…), mas quando bate é o enriquecimento mais
barato que existe: zero chave, resposta estruturada, e alimenta a linha
do tempo do dossiê sozinho (data de nascimento, posse em cargo).
"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import quote

from . import net
from .entity import Entity, EntityType
from .findings import Confidence, Finding, FindingKind

# Cargo/ocupação que, se achado no Wikidata, eleva o alvo a PEP mesmo sem
# constar nas bases oficiais brasileiras (ex.: político de outro país).
# Radicais (sem sufixo de gênero) — "deputad" casa com deputado e deputada.
_OCUPACAO_PEP_RADICAIS = (
    "polític", "politic", "deputad", "senador", "senadora", "prefeit",
    "governador", "governadora", "ministr", "president", "vereador",
    "vereadora", "ju[ií]z", "magistrad", "embaixador", "embaixadora",
    "procurador", "procuradora", "promotor", "promotora",
)
_OCUPACAO_PEP_RE = re.compile("|".join(_OCUPACAO_PEP_RADICAIS), re.IGNORECASE)

_DATA_WIKIDATA_RE = re.compile(r"[+-](\d{4})-(\d{2})-(\d{2})")


def _titulo_para_url(titulo: str) -> str:
    return quote(titulo.replace(" ", "_"))


def _wikipedia_summary(nome: str) -> dict | None:
    """Título mais próximo do nome + resumo da página, via API pública."""
    try:
        busca = net.get_json(
            "https://pt.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": nome, "limit": 1,
                    "namespace": 0, "format": "json"},
            timeout=12, ttl=24 * 3600,
        )
    except Exception:
        return None
    titulos = busca[1] if isinstance(busca, list) and len(busca) > 1 else []
    if not titulos:
        return None
    titulo = titulos[0]
    try:
        resumo = net.get_json(
            f"https://pt.wikipedia.org/api/rest_v1/page/summary/{_titulo_para_url(titulo)}",
            timeout=12, ttl=24 * 3600,
        )
    except Exception:
        return None
    if not resumo or resumo.get("type") == "disambiguation":
        return None
    return resumo


def _wikidata_entity(nome: str) -> dict | None:
    """Item do Wikidata mais próximo do nome, com claims (nascimento, cargo…)."""
    try:
        busca = net.get_json(
            "https://www.wikidata.org/w/api.php",
            params={"action": "wbsearchentities", "search": nome, "language": "pt",
                    "format": "json", "limit": 1, "type": "item"},
            timeout=12, ttl=24 * 3600,
        ) or {}
    except Exception:
        return None
    hits = busca.get("search") or []
    if not hits or not hits[0].get("id"):
        return None
    qid = hits[0]["id"]
    try:
        ent = net.get_json(
            "https://www.wikidata.org/w/api.php",
            params={"action": "wbgetentities", "ids": qid, "props": "claims|labels",
                    "languages": "pt", "format": "json"},
            timeout=15, ttl=24 * 3600,
        ) or {}
    except Exception:
        return None
    return (ent.get("entities") or {}).get(qid)


def _resolve_labels(qids: list[str]) -> dict[str, str]:
    """QID -> rótulo em português, numa chamada só para todos os códigos."""
    if not qids:
        return {}
    try:
        data = net.get_json(
            "https://www.wikidata.org/w/api.php",
            params={"action": "wbgetentities", "ids": "|".join(qids[:20]),
                    "props": "labels", "languages": "pt", "format": "json"},
            timeout=12, ttl=24 * 3600,
        ) or {}
    except Exception:
        return {}
    out: dict[str, str] = {}
    for qid, ent in (data.get("entities") or {}).items():
        rotulo = ((ent.get("labels") or {}).get("pt") or {}).get("value")
        if rotulo:
            out[qid] = rotulo
    return out


def _claim_date(entidade: dict, prop: str) -> str | None:
    for c in (entidade.get("claims") or {}).get(prop) or []:
        try:
            bruto = c["mainsnak"]["datavalue"]["value"]["time"]
        except Exception:
            continue
        m = _DATA_WIKIDATA_RE.match(bruto)
        if m:
            return "-".join(m.groups())
    return None


def _claim_qids(entidade: dict, prop: str, limit: int = 4) -> list[str]:
    out = []
    for c in ((entidade.get("claims") or {}).get(prop) or [])[:limit]:
        try:
            out.append(c["mainsnak"]["datavalue"]["value"]["id"])
        except Exception:
            continue
    return out


def wiki_findings(entity: Entity) -> Iterable[Finding]:
    if entity.type is not EntityType.NAME:
        return []

    nome = entity.value
    out: list[Finding] = []

    resumo = _wikipedia_summary(nome)
    if resumo:
        pagina = resumo.get("title") or nome
        url = ((resumo.get("content_urls") or {}).get("desktop") or {}).get("page") or (
            f"https://pt.wikipedia.org/wiki/{_titulo_para_url(pagina)}"
        )
        extrato = (resumo.get("extract") or "").strip()
        if extrato:
            out.append(Finding(
                kind=FindingKind.NOTE, value=f"Wikipédia: {pagina}",
                source="wikipedia", source_label="Wikipédia",
                url=url, confidence=Confidence.LIKELY, detail=extrato[:500],
            ))
        thumb = (resumo.get("thumbnail") or {}).get("source")
        if thumb:
            out.append(Finding(
                kind=FindingKind.IMAGE, value=thumb, source="wikipedia",
                source_label="Wikipédia", url=thumb, confidence=Confidence.LIKELY,
                detail=f"Foto na página da Wikipédia de {pagina}",
            ))

    entidade = _wikidata_entity(nome)
    if entidade:
        nascimento = _claim_date(entidade, "P569")
        if nascimento:
            out.append(Finding(
                kind=FindingKind.NOTE, value=f"Data de nascimento: {nascimento}",
                source="wikidata", source_label="Wikidata", confidence=Confidence.LIKELY,
                detail=f"Segundo o Wikidata, nascido(a) em {nascimento}.",
            ))

        ocup_qids = _claim_qids(entidade, "P106")   # ocupação
        cargo_qids = _claim_qids(entidade, "P39")   # cargo ocupado
        rotulos = _resolve_labels(list(dict.fromkeys(ocup_qids + cargo_qids)))
        ocupacoes = [rotulos[q] for q in ocup_qids if q in rotulos]
        cargos = [rotulos[q] for q in cargo_qids if q in rotulos]

        if ocupacoes:
            out.append(Finding(
                kind=FindingKind.NOTE, value=f"Ocupação (Wikidata): {', '.join(ocupacoes)}",
                source="wikidata", source_label="Wikidata", confidence=Confidence.LIKELY,
            ))
        if cargos:
            eh_pep = any(_OCUPACAO_PEP_RE.search(c) for c in cargos) or any(
                _OCUPACAO_PEP_RE.search(o) for o in ocupacoes
            )
            if eh_pep:
                texto = (
                    "Consta como PESSOA POLITICAMENTE EXPOSTA (cargo público — Wikidata): "
                    + ", ".join(cargos)
                )
            else:
                texto = f"Cargo(s) (Wikidata): {', '.join(cargos)}"
            out.append(Finding(
                kind=FindingKind.NOTE, value=texto, source="wikidata",
                source_label="Wikidata", confidence=Confidence.LIKELY,
            ))
    return out
