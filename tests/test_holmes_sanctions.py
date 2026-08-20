"""Sanções e PEP internacionais via OpenSanctions. net.get_json mockado — sem rede."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import net, sanctions  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import Confidence, FindingKind  # noqa: E402


def test_sem_chave_nao_busca(monkeypatch):
    monkeypatch.setattr(net, "get_key", lambda name: None)
    assert sanctions.buscar("Fulano") == []
    assert list(sanctions.opensanctions_findings(detect("Fulano de Tal"))) == []


def _com_chave(monkeypatch):
    monkeypatch.setattr(net, "get_key", lambda name: "chave-teste" if name == "opensanctions" else None)


def test_sancao_vira_legal_confirmada(monkeypatch):
    _com_chave(monkeypatch)
    fake = {"results": [{
        "id": "abc123", "caption": "Fulano Sancionado", "score": 0.92,
        "properties": {"topics": ["sanction"]},
        "datasets": ["us_ofac_sdn"],
    }]}
    monkeypatch.setattr(net, "get_json", lambda *a, **k: fake)
    out = list(sanctions.opensanctions_findings(detect("Fulano Sancionado")))
    assert len(out) == 1
    assert out[0].kind is FindingKind.LEGAL
    assert "SANÇÃO internacional" in out[0].value
    assert "us_ofac_sdn" in out[0].detail


def test_pep_vira_note_com_gatilho_do_dossie(monkeypatch):
    _com_chave(monkeypatch)
    fake = {"results": [{
        "id": "xyz", "caption": "Alguém Importante", "score": 0.8,
        "properties": {"topics": ["role.pep"]},
        "datasets": ["ru_pep"],
    }]}
    monkeypatch.setattr(net, "get_json", lambda *a, **k: fake)
    out = list(sanctions.opensanctions_findings(detect("Alguém Importante")))
    assert out[0].kind is FindingKind.NOTE
    assert "POLITICAMENTE EXPOSTA" in out[0].value.upper()


def test_score_baixo_vira_possivel_e_score_muito_baixo_e_descartado(monkeypatch):
    _com_chave(monkeypatch)
    fake = {"results": [
        {"id": "a", "caption": "Homônimo Fraco", "score": 0.4,
         "properties": {"topics": ["crime"]}, "datasets": ["x"]},
        {"id": "b", "caption": "Ruído", "score": 0.1,
         "properties": {"topics": ["crime"]}, "datasets": ["x"]},
    ]}
    monkeypatch.setattr(net, "get_json", lambda *a, **k: fake)
    out = list(sanctions.opensanctions_findings(detect("Homônimo Fraco")))
    assert len(out) == 1  # o de score 0.1 foi descartado
    assert out[0].confidence is Confidence.POSSIBLE


def test_ignora_tipo_de_alvo_nao_suportado(monkeypatch):
    _com_chave(monkeypatch)
    assert list(sanctions.opensanctions_findings(detect("+5511999998888"))) == []
