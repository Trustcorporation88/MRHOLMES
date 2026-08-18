"""
Mr.Holmes — motor de investigação unificado.

Uso mínimo:

    from holmes import investigate
    dossie = investigate("fulano de tal")
    print(dossie.to_markdown())

Uma caixa de entrada, detecção automática do tipo de alvo, todas as fontes
aplicáveis em paralelo, pivô automático e um dossiê consolidado com fonte e
confiança em cada fato.
"""

from __future__ import annotations

from .dossier import Dossier
from .entity import Entity, EntityType, detect, detect_all
from .findings import Confidence, Finding, FindingKind
from .orchestrator import InvestigationConfig, investigate

__all__ = [
    "investigate",
    "InvestigationConfig",
    "Dossier",
    "Entity",
    "EntityType",
    "detect",
    "detect_all",
    "Finding",
    "FindingKind",
    "Confidence",
]

__version__ = "1.0.0"
