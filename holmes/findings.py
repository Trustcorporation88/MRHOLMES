"""
Modelo de dados do motor de investigação.

Tudo que qualquer conector produz vira `Finding`. O dossiê é só uma coleção
de findings deduplicada, correlacionada e pontuada. Nenhum conector escreve
HTML, nenhum conector fala com a UI.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Confidence(str, Enum):
    """Confiança de um achado isolado, antes da corroboração."""

    CONFIRMED = "confirmada"   # a fonte respondeu afirmando o dado (ex.: Holehe positivo)
    LIKELY = "provavel"        # forte indício, mas sem confirmação direta
    POSSIBLE = "possivel"      # pode ser homônimo / coincidência
    UNVERIFIED = "nao_verificada"  # link gerado, ninguém checou ainda


_CONF_WEIGHT = {
    Confidence.CONFIRMED: 1.0,
    Confidence.LIKELY: 0.65,
    Confidence.POSSIBLE: 0.35,
    Confidence.UNVERIFIED: 0.15,
}


class FindingKind(str, Enum):
    """O que o achado é. Guia o agrupamento no dossiê e o motor de pivô."""

    ACCOUNT = "conta"           # perfil em plataforma
    EMAIL = "email"
    PHONE = "telefone"
    NAME = "nome"
    USERNAME = "username"
    DOMAIN = "dominio"
    IP = "ip"
    ADDRESS = "endereco"
    DOCUMENT = "documento"      # CPF / CNPJ
    COMPANY = "empresa"
    BREACH = "vazamento"
    IMAGE = "imagem"
    WEB_RESULT = "resultado_web"
    LEGAL = "juridico"
    LINK = "link"               # deeplink pronto para abrir manualmente
    NOTE = "nota"


@dataclass
class Finding:
    """Um fato observado, sempre amarrado à fonte que o produziu."""

    kind: FindingKind
    value: str
    source: str                       # id do conector (ex.: "holehe", "serper")
    source_label: str = ""            # nome legível (ex.: "Holehe")
    url: str | None = None            # onde a evidência pode ser conferida
    confidence: Confidence = Confidence.POSSIBLE
    detail: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    observed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def __post_init__(self) -> None:
        # Aceita string crua vinda de conector escrito às pressas.
        if isinstance(self.kind, str):
            self.kind = FindingKind(self.kind)
        if isinstance(self.confidence, str):
            self.confidence = Confidence(self.confidence)
        self.value = (self.value or "").strip()
        if not self.source_label:
            self.source_label = self.source

    @property
    def dedup_key(self) -> tuple[str, str]:
        """Dois findings com a mesma chave são o mesmo fato visto por fontes diferentes."""
        return (self.kind.value, self.value.strip().lower())

    @property
    def weight(self) -> float:
        return _CONF_WEIGHT.get(self.confidence, 0.2)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["confidence"] = self.confidence.value
        return d


@dataclass
class ConnectorResult:
    """Retorno de um conector — inclui o fracasso, que também é informação."""

    connector_id: str
    connector_label: str
    ok: bool
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None
    skipped_reason: str | None = None
    elapsed_ms: int = 0

    @property
    def status(self) -> str:
        if self.skipped_reason:
            return "pulado"
        return "ok" if self.ok else "erro"

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "connector_label": self.connector_label,
            "status": self.status,
            "ok": self.ok,
            "error": self.error,
            "skipped_reason": self.skipped_reason,
            "elapsed_ms": self.elapsed_ms,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class CorroboratedFact:
    """Um fato depois da fusão: mesmo valor, várias fontes, um score só."""

    kind: FindingKind
    value: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def sources(self) -> list[str]:
        seen: list[str] = []
        for f in self.findings:
            if f.source not in seen:
                seen.append(f.source)
        return seen

    @property
    def urls(self) -> list[str]:
        seen: list[str] = []
        for f in self.findings:
            if f.url and f.url not in seen:
                seen.append(f.url)
        return seen

    @property
    def best_confidence(self) -> Confidence:
        return max(
            (f.confidence for f in self.findings),
            key=lambda c: _CONF_WEIGHT.get(c, 0.0),
            default=Confidence.UNVERIFIED,
        )

    @property
    def score(self) -> float:
        """
        0..1. Corroboração independente é o que mais pesa: duas fontes fracas
        concordando valem mais que uma fonte forte sozinha, que é exatamente
        como um investigador raciocina.
        """
        if not self.findings:
            return 0.0
        best = max(f.weight for f in self.findings)
        extra_sources = max(0, len(self.sources) - 1)
        bonus = min(0.45, extra_sources * 0.18)
        return round(min(1.0, best + bonus), 3)

    @property
    def label(self) -> str:
        s = self.score
        if s >= 0.85:
            return "alta"
        if s >= 0.55:
            return "media"
        if s >= 0.3:
            return "baixa"
        return "indicio"

    @property
    def detail(self) -> str:
        for f in self.findings:
            if f.detail:
                return f.detail
        return ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "value": self.value,
            "score": self.score,
            "confidence": self.label,
            "sources": self.sources,
            "urls": self.urls,
            "detail": self.detail,
            "findings": [f.to_dict() for f in self.findings],
        }


def fact_id(kind: FindingKind, value: str) -> str:
    raw = f"{kind.value}:{value.strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
