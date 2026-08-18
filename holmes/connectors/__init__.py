"""
Registro de conectores.

Importar este pacote já deixa tudo registrado. `ensure_registered()` é
idempotente e pode ser chamado a cada rerun do Streamlit sem duplicar nada.
"""

from __future__ import annotations

from ..entity import Entity, EntityType
from .base import (  # noqa: F401
    Connector,
    Mode,
    all_connectors,
    connectors_for,
    get_connector,
    register,
    registry_stats,
)

_REGISTERED = False


def _serp_connector():
    """A busca de superfície entra no fluxo como mais um conector."""
    from .. import serp
    from ..findings import Finding

    def _run(entity: Entity):
        queries = serp.build_queries(entity, deep=True)
        hits = serp.search_many(queries, limit_each=8, max_queries=12)
        findings: list[Finding] = list(serp.hits_to_findings(hits, entity))
        if findings:
            from ..findings import Confidence, FindingKind

            findings.insert(0, Finding(
                kind=FindingKind.NOTE,
                value=f"{len(hits)} resultados em {len(queries)} consultas",
                source="serp", source_label=f"Busca — {serp.provider_label()}",
                confidence=Confidence.CONFIRMED,
                detail="Bateria de dorks executada automaticamente: "
                       + " · ".join(queries[:6]),
                raw={"queries": queries},
            ))
        return findings

    return Connector(
        id="serp", label="Busca de superfície + dorks", mode=Mode.AUTO,
        accepts=(
            EntityType.NAME, EntityType.EMAIL, EntityType.PHONE,
            EntityType.USERNAME, EntityType.DOMAIN, EntityType.CPF,
            EntityType.CNPJ, EntityType.IP, EntityType.PROFILE_URL,
        ),
        category="busca", timeout=90, run=_run,
        description="Roda a bateria de dorks e classifica cada resultado",
    )


def ensure_registered() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    from .auto import register_auto_connectors
    from .catalog import register_br_catalog, register_catalog

    register(_serp_connector())
    register_auto_connectors()
    register_catalog()
    register_br_catalog()
    _REGISTERED = True


ensure_registered()
