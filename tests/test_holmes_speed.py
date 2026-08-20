"""Pivôs em paralelo (ganho de velocidade). Sem rede — _run_batch é mockado."""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import orchestrator  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import ConnectorResult, Finding, FindingKind  # noqa: E402
from holmes.orchestrator import InvestigationConfig, _run_batches_parallel  # noqa: E402

_SLEEP = 0.5


def _fake_batch(entity, modes, config, progress, base, span):
    time.sleep(_SLEEP)
    return [ConnectorResult(
        connector_id="fake", connector_label="Fake", ok=True,
        findings=[Finding(FindingKind.NOTE, entity.value, "fake")],
    )]


def test_pivos_rodam_em_paralelo(monkeypatch):
    monkeypatch.setattr(orchestrator, "_run_batch", _fake_batch)
    entities = [detect("a@x.com"), detect("b@x.com"), detect("c@x.com")]
    cfg = InvestigationConfig()

    inicio = time.time()
    results = _run_batches_parallel(entities, cfg, time.time() + 30)
    gasto = time.time() - inicio

    # Sequencial levaria 3×0.5=1.5s; em paralelo fica perto de um único sleep.
    assert gasto < 1.1, f"pivôs não paralelizaram (gastou {gasto:.2f}s)"
    valores = {f.value for r in results for f in r.findings}
    assert valores == {"a@x.com", "b@x.com", "c@x.com"}


def test_lista_vazia_nao_quebra(monkeypatch):
    monkeypatch.setattr(orchestrator, "_run_batch", _fake_batch)
    assert _run_batches_parallel([], InvestigationConfig(), time.time() + 5) == []


def test_serp_connector_timeout_reduzido():
    from holmes.connectors import ensure_registered, get_connector

    ensure_registered()
    assert get_connector("serp").timeout <= 45
