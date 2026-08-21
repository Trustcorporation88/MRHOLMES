"""Simples Nacional, MEI e situação especial na consulta de CNPJ. Sem rede."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import br  # noqa: E402
from holmes.dossier import Dossier  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import ConnectorResult  # noqa: E402


def _fake_brasilapi(**over):
    base = {
        "razao_social": "Empresa Teste LTDA", "nome_fantasia": "Teste",
        "descricao_situacao_cadastral": "ATIVA", "_fonte": "BrasilAPI",
    }
    base.update(over)
    return base


def test_simples_optante_com_data(monkeypatch):
    monkeypatch.setattr(br, "consulta_cnpj", lambda _: _fake_brasilapi(
        opcao_pelo_simples=True, data_opcao_pelo_simples="2020-01-01",
    ))
    out = list(br.cnpj_findings(detect("00.000.000/0001-91")))
    achado = next(f for f in out if "Optante pelo Simples" in f.value)
    assert "2020-01-01" in achado.detail


def test_simples_nao_optante(monkeypatch):
    monkeypatch.setattr(br, "consulta_cnpj", lambda _: _fake_brasilapi(opcao_pelo_simples=False))
    out = list(br.cnpj_findings(detect("00.000.000/0001-91")))
    achado = next(f for f in out if "Simples" in f.value)
    assert "NÃO optante" in achado.value


def test_simples_via_receitaws_aninhado(monkeypatch):
    monkeypatch.setattr(br, "consulta_cnpj", lambda _: _fake_brasilapi(
        _fonte="ReceitaWS", simples={"optante": True, "data_opcao": "2019-05-10"},
    ))
    out = list(br.cnpj_findings(detect("00.000.000/0001-91")))
    achado = next(f for f in out if "Optante pelo Simples" in f.value)
    assert "2019-05-10" in achado.detail


def test_mei_optante(monkeypatch):
    monkeypatch.setattr(br, "consulta_cnpj", lambda _: _fake_brasilapi(opcao_pelo_mei=True))
    out = list(br.cnpj_findings(detect("00.000.000/0001-91")))
    assert any("MEI" in f.value for f in out)


def test_sem_mei_nao_gera_finding(monkeypatch):
    monkeypatch.setattr(br, "consulta_cnpj", lambda _: _fake_brasilapi(opcao_pelo_mei=False))
    out = list(br.cnpj_findings(detect("00.000.000/0001-91")))
    assert not any("MEI" in f.value for f in out)


def test_situacao_especial_gera_finding_e_bandeira_no_cartao(monkeypatch):
    monkeypatch.setattr(br, "consulta_cnpj", lambda _: _fake_brasilapi(
        situacao_especial="RECUPERAÇÃO JUDICIAL", data_situacao_especial="2023-03-01",
    ))
    findings = list(br.cnpj_findings(detect("00.000.000/0001-91")))
    achado = next(f for f in findings if "SITUAÇÃO ESPECIAL" in f.value.upper())
    assert "RECUPERAÇÃO JUDICIAL" in achado.value
    assert "2023-03-01" in achado.detail

    d = Dossier(entity=detect("00.000.000/0001-91"))
    d.add_results([ConnectorResult("receita_cnpj", "Receita", True, findings)])
    d.consolidate()
    card = d.identity_card()
    assert any("Situação especial" in f for f in card["flags"])


def test_sem_situacao_especial_sem_bandeira(monkeypatch):
    monkeypatch.setattr(br, "consulta_cnpj", lambda _: _fake_brasilapi())
    findings = list(br.cnpj_findings(detect("00.000.000/0001-91")))
    assert not any("SITUAÇÃO ESPECIAL" in f.value.upper() for f in findings)


def test_sem_dados_nenhum_devolve_vazio(monkeypatch):
    monkeypatch.setattr(br, "consulta_cnpj", lambda _: None)
    assert list(br.cnpj_findings(detect("00.000.000/0001-91"))) == []
