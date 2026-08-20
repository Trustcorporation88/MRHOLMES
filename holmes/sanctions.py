"""
Sanções e pessoas politicamente expostas — cobertura internacional.

A camada Brasil (br_auto.py, Portal da Transparência) só enxerga listas
nacionais. Aqui é o mundo todo, via OpenSanctions: agrega OFAC (EUA), ONU,
União Europeia, INTERPOL red notices, e listas de PEP de dezenas de países
num índice só, com busca por nome.

Chave gratuita (com limite de uso) — cadastro em opensanctions.org/api.
Sem chave, o conector fica listado como pulado, igual a qualquer outra
fonte do motor que depende de chave.
"""

from __future__ import annotations

from typing import Iterable

from . import net
from .entity import Entity, EntityType
from .findings import Confidence, Finding, FindingKind

_TOPICO_LABEL = {
    "sanction": "sanção internacional",
    "sanction.linked": "ligado a pessoa/entidade sancionada",
    "role.pep": "Pessoa Politicamente Exposta (PEP)",
    "role.rca": "parente ou associado próximo de PEP",
    "role.judge": "autoridade judicial",
    "poi": "pessoa de interesse público",
    "crime": "associado a crime",
    "crime.fin": "crime financeiro",
    "crime.fraud": "fraude",
    "crime.terror": "terrorismo",
    "wanted": "procurado",
    "debarment": "impedido de contratar com o poder público (debarment)",
}

# Resultado com pontuação abaixo disto é ruído de busca textual — nem entra.
_SCORE_MINIMO = 0.3


def _topico_texto(topico: str) -> str:
    return _TOPICO_LABEL.get(topico, topico.replace(".", " ").replace("_", " "))


def buscar(termo: str, limit: int = 5) -> list[dict]:
    """Busca crua na API. Lista vazia sem chave ou sem termo — nunca lança."""
    key = net.get_key("opensanctions")
    if not key or not (termo or "").strip():
        return []
    try:
        data = net.get_json(
            "https://api.opensanctions.org/search/default",
            params={"q": termo, "limit": limit},
            headers={"Authorization": f"ApiKey {key}"},
            timeout=15, ttl=6 * 3600,
        ) or {}
    except Exception:
        return []
    return data.get("results") or []


def opensanctions_findings(entity: Entity) -> Iterable[Finding]:
    if entity.type not in (EntityType.NAME, EntityType.CNPJ):
        return []

    termo = entity.value
    resultados = buscar(termo)
    out: list[Finding] = []

    for r in resultados:
        score = r.get("score") or 0.0
        if score < _SCORE_MINIMO:
            continue

        nome = r.get("caption") or termo
        topicos = ((r.get("properties") or {}).get("topics")) or r.get("topics") or []
        datasets = r.get("datasets") or []
        rotulos = [_topico_texto(t) for t in topicos] or ["registro em base internacional"]
        entity_id = r.get("id") or ""
        url = f"https://www.opensanctions.org/entities/{entity_id}/" if entity_id else "https://www.opensanctions.org/"
        detalhe = (
            f"Correspondência {score:.0%} · fontes: {', '.join(datasets[:4]) or 'OpenSanctions'}"
        )

        # score alto e nome batendo exatamente = confirmado; abaixo disso,
        # pode ser homônimo — nunca mais que "provável".
        if score >= 0.75:
            confianca = Confidence.CONFIRMED
        elif score >= 0.5:
            confianca = Confidence.LIKELY
        else:
            confianca = Confidence.POSSIBLE

        eh_sancao = any(t.startswith("sanction") for t in topicos)
        eh_pep = any(t.startswith("role.pep") for t in topicos)

        if eh_sancao:
            out.append(Finding(
                kind=FindingKind.LEGAL,
                value=f"SANÇÃO internacional: {nome} — {', '.join(rotulos)}",
                source="opensanctions", source_label="OpenSanctions",
                url=url, confidence=confianca, detail=detalhe, raw=r,
            ))
        elif eh_pep:
            out.append(Finding(
                kind=FindingKind.NOTE,
                value=f"Consta como PESSOA POLITICAMENTE EXPOSTA (internacional): {nome}",
                source="opensanctions", source_label="OpenSanctions",
                url=url, confidence=confianca, detail=detalhe, raw=r,
            ))
        else:
            out.append(Finding(
                kind=FindingKind.LEGAL,
                value=f"{nome} — {', '.join(rotulos)}",
                source="opensanctions", source_label="OpenSanctions",
                url=url, confidence=confianca, detail=detalhe, raw=r,
            ))
    return out
