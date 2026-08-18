"""
Contrato único de conector.

Todo serviço — API, raspagem, binário local ou link — obedece à mesma
interface. É isso que permite o orquestrador tratar 100 fontes diferentes
como uma lista só.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable

from ..entity import Entity, EntityType
from ..findings import ConnectorResult, Finding


class Mode(str, Enum):
    AUTO = "auto"          # executa e traz dado para dentro do dossiê
    DEEPLINK = "deeplink"  # gera a URL já pesquisada (sem API pública)
    MANUAL = "manual"      # exige login/captcha; listado com instrução


@dataclass
class Connector:
    """Uma fonte. `run` só é chamado quando `mode` é AUTO."""

    id: str
    label: str
    mode: Mode
    accepts: tuple[EntityType, ...]
    category: str = "geral"
    description: str = ""
    homepage: str = ""
    requires_key: str | None = None       # nome da chave em holmes.net
    requires_binary: str | None = None    # binário externo (holehe, maigret…)
    timeout: int = 25
    cost: str = "gratis"                  # gratis | chave | pago
    run: Callable[[Entity], Iterable[Finding]] | None = None
    deeplink: Callable[[Entity], str | None] | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def handles(self, entity: Entity) -> bool:
        return entity.type in self.accepts

    def availability(self) -> tuple[bool, str | None]:
        """(disponível, motivo de indisponibilidade). Falha explícita, nunca silenciosa."""
        from .. import net

        if self.requires_key and not net.has_key(self.requires_key):
            return False, f"chave {self.requires_key} não configurada"
        if self.requires_binary:
            from ..runtime import binary_available

            if not binary_available(self.requires_binary):
                return False, f"{self.requires_binary} não instalado neste ambiente"
        return True, None

    def execute(self, entity: Entity) -> ConnectorResult:
        """Nunca levanta exceção: o erro vira resultado, e o dossiê segue."""
        started = time.time()

        def _done(**kw) -> ConnectorResult:
            return ConnectorResult(
                connector_id=self.id,
                connector_label=self.label,
                elapsed_ms=int((time.time() - started) * 1000),
                **kw,
            )

        if not self.handles(entity):
            return _done(ok=False, skipped_reason=f"não aceita alvo do tipo {entity.type.value}")

        available, why = self.availability()
        if not available:
            return _done(ok=False, skipped_reason=why)

        if self.mode in (Mode.DEEPLINK, Mode.MANUAL):
            url = None
            try:
                url = self.deeplink(entity) if self.deeplink else None
            except Exception as exc:  # noqa: BLE001
                return _done(ok=False, error=f"falha ao montar link: {exc}")
            if not url:
                return _done(ok=False, skipped_reason="sem link aplicável a este alvo")
            from ..findings import Confidence, FindingKind

            note = "abre já pesquisado" if self.mode is Mode.DEEPLINK else "exige login/captcha"
            return _done(
                ok=True,
                findings=[
                    Finding(
                        kind=FindingKind.LINK,
                        value=self.label,
                        source=self.id,
                        source_label=self.label,
                        url=url,
                        confidence=Confidence.UNVERIFIED,
                        detail=f"{self.description} ({note})".strip(),
                        raw={"category": self.category, "mode": self.mode.value},
                    )
                ],
            )

        if not self.run:
            return _done(ok=False, skipped_reason="conector sem implementação")

        try:
            findings = list(self.run(entity) or [])
        except Exception as exc:  # noqa: BLE001
            return _done(ok=False, error=f"{type(exc).__name__}: {exc}")
        return _done(ok=True, findings=findings)


# ── registro global ─────────────────────────────────────────────────────────

_REGISTRY: dict[str, Connector] = {}


def register(connector: Connector) -> Connector:
    _REGISTRY[connector.id] = connector
    return connector


def all_connectors() -> list[Connector]:
    return list(_REGISTRY.values())


def get_connector(cid: str) -> Connector | None:
    return _REGISTRY.get(cid)


def connectors_for(entity: Entity, modes: Iterable[Mode] | None = None) -> list[Connector]:
    wanted = set(modes) if modes else set(Mode)
    return [c for c in _REGISTRY.values() if c.handles(entity) and c.mode in wanted]


def registry_stats() -> dict:
    stats: dict = {"total": len(_REGISTRY), "por_modo": {}, "por_categoria": {}, "prontos": 0}
    for c in _REGISTRY.values():
        stats["por_modo"][c.mode.value] = stats["por_modo"].get(c.mode.value, 0) + 1
        stats["por_categoria"][c.category] = stats["por_categoria"].get(c.category, 0) + 1
        if c.availability()[0]:
            stats["prontos"] += 1
    return stats
