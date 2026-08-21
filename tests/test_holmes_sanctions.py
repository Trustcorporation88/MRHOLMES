"""Sanções e PEP internacionais — índice local primeiro, API paga como reserva. Sem rede."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import net, opensanctions_bulk as bulk, sanctions  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import Confidence, FindingKind  # noqa: E402


def test_sem_indice_e_sem_chave_nao_busca(monkeypatch):
    monkeypatch.setattr(bulk, "disponivel", lambda: False)
    monkeypatch.setattr(net, "get_key", lambda name: None)
    assert sanctions.buscar("Fulano") == []
    assert list(sanctions.opensanctions_findings(detect("Fulano de Tal"))) == []


def _com_chave(monkeypatch):
    monkeypatch.setattr(bulk, "disponivel", lambda: False)  # força caminho da API
    monkeypatch.setattr(net, "get_key", lambda name: "chave-teste" if name == "opensanctions" else None)


# ── caminho da API (reserva, só quando não há índice local) ─────────────────

def test_sancao_via_api_vira_legal_confirmada(monkeypatch):
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


def test_pep_via_api_vira_note_com_gatilho_do_dossie(monkeypatch):
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


# ── índice local tem prioridade sobre a API ──────────────────────────────────

def test_indice_local_e_preferido_sobre_api(monkeypatch):
    monkeypatch.setattr(bulk, "disponivel", lambda: True)
    monkeypatch.setattr(bulk, "search", lambda nome, limit=5: [{
        "id": "Q1", "nome": "Fulano Sancionado", "sancoes": "EU sanctions",
        "datasets": "eu_fsf", "nivel_match": "exato", "eh_sancao": True, "eh_pep": False,
    }])

    def _api_boom(*a, **k):
        raise AssertionError("não deveria chamar a API quando o índice local existe")

    monkeypatch.setattr(net, "get_json", _api_boom)
    out = list(sanctions.opensanctions_findings(detect("Fulano Sancionado")))
    assert len(out) == 1
    assert out[0].source == "opensanctions_local"
    assert out[0].confidence is Confidence.CONFIRMED


def test_indice_local_match_parcial_vira_likely_com_aviso(monkeypatch):
    monkeypatch.setattr(bulk, "disponivel", lambda: True)
    monkeypatch.setattr(bulk, "search", lambda nome, limit=5: [{
        "id": "Q2", "nome": "Joao Silva Pereira", "sancoes": "",
        "datasets": "br_pep_source", "nivel_match": "parcial", "eh_sancao": False, "eh_pep": True,
    }])
    out = list(sanctions.opensanctions_findings(detect("Joao Pereira")))
    assert out[0].kind is FindingKind.NOTE
    assert out[0].confidence is Confidence.LIKELY
    assert "confirme antes de usar" in out[0].detail


def test_indice_local_sem_resultado_devolve_vazio(monkeypatch):
    monkeypatch.setattr(bulk, "disponivel", lambda: True)
    monkeypatch.setattr(bulk, "search", lambda nome, limit=5: [])
    assert list(sanctions.opensanctions_findings(detect("Ninguém Conhecido"))) == []
