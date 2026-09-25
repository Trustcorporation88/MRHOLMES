"""CPF/CNPJ mais fortes: CPF mascarado, Portal completo e Bright Data como busca."""

from __future__ import annotations

import pytest

from holmes import br_auto, net, serp
from holmes.connectors import Mode, all_connectors
from holmes.entity import detect
from holmes.findings import Confidence, FindingKind

CPF = "529.982.247-25"  # CPF válido de exemplo, sem titular real


def test_cpf_ganha_forma_mascarada_da_lgpd():
    ent = detect(CPF)
    assert ent.get("masked") == "***.982.247-**"
    assert ent.get("miolo") == "982.247"


def test_dorks_de_cpf_procuram_o_miolo_mascarado():
    queries = serp.build_queries(detect(CPF), deep=True)
    assert any('"982.247"' in q for q in queries)
    assert len(queries) <= 12  # cabe no max_queries do conector serp


def test_portal_cpf_traz_nome_e_vinculos(monkeypatch):
    monkeypatch.setattr(net, "get_key", lambda name: "k" if name == "portal_transparencia" else None)

    def fake_get_json(url, **kw):
        if url.endswith("/pessoa-fisica"):
            return {"nome": "FULANO DE TAL", "nis": "12345678901",
                    "servidor": True, "beneficiarioBolsaFamilia": True, "sancionadoCEIS": False}
        return []

    monkeypatch.setattr(net, "get_json", fake_get_json)
    achados = list(br_auto.portal_cpf_findings(detect(CPF)))
    nomes = [f for f in achados if f.kind is FindingKind.NAME]
    assert nomes and nomes[0].value == "FULANO DE TAL"
    assert nomes[0].confidence is Confidence.CONFIRMED
    vinculos = next(f for f in achados if f.value.startswith("Vínculos federais"))
    assert "servidor público federal" in vinculos.value
    assert "CEIS" not in vinculos.value


def test_portal_fora_do_ar_nao_vira_dossie_vazio(monkeypatch):
    monkeypatch.setattr(net, "get_key", lambda name: "k" if name == "portal_transparencia" else None)

    def boom(url, **kw):
        raise net.requests.HTTPError("HTTP 503")

    monkeypatch.setattr(net, "get_json", boom)
    with pytest.raises(RuntimeError, match="Portal da Transparência não respondeu"):
        list(br_auto.portal_cpf_findings(detect(CPF)))


def test_portal_cnpj_lista_contratos(monkeypatch):
    monkeypatch.setattr(net, "get_key", lambda name: "k" if name == "portal_transparencia" else None)

    def fake_get_json(url, **kw):
        if url.endswith("/contratos/cpf-cnpj"):
            return [{"valorInicialCompra": 1500.5,
                     "unidadeGestora": {"orgaoVinculado": {"nome": "Ministério X"}}}]
        return []

    monkeypatch.setattr(net, "get_json", fake_get_json)
    achados = list(br_auto.portal_cnpj_findings(detect("00.000.000/0001-91")))
    contrato = next(f for f in achados if "contrato" in f.value)
    assert "R$ 1.500,50" in contrato.value
    assert "Ministério X" in contrato.detail


def test_querido_diario_cpf_busca_forma_mascarada_com_confianca_menor(monkeypatch):
    chamadas = []

    def fake_busca(querystring):
        chamadas.append(querystring)
        if querystring == '"982.247"':
            return {"total_gazettes": 1, "gazettes": [
                {"url": "https://x/1.pdf", "territory_name": "Campinas", "state_code": "SP",
                 "date": "2025-01-02", "excerpts": ["FULANO CPF ***.982.247-**"]}]}
        return {"gazettes": []}

    monkeypatch.setattr(br_auto, "_diario_busca", fake_busca)
    achados = list(br_auto.querido_diario_findings(detect(CPF)))
    assert len(chamadas) == 2
    legais = [f for f in achados if f.kind is FindingKind.LEGAL]
    assert legais and legais[0].confidence is Confidence.POSSIBLE


def test_bright_data_vira_provedor_de_busca(monkeypatch):
    monkeypatch.setattr(net, "BRD_SERP_ZONE", "serp_api1")
    monkeypatch.setattr(net, "get_key", lambda name: "tok" if name == "brightdata" else None)
    monkeypatch.setattr(net, "has_key", lambda name: name == "brightdata")
    assert serp.active_provider() == "brightdata"

    monkeypatch.setattr(net, "brd_serp_json", lambda url, **kw: {
        "organic": [{"link": "https://exemplo.gov.br/edital.pdf", "title": "Edital",
                     "description": "CPF ***.982.247-**", "rank": 1}]})
    hits = serp.search('"982.247" CPF')
    assert hits and hits[0].engine == "brightdata"
    assert hits[0].url == "https://exemplo.gov.br/edital.pdf"


def test_bright_data_sem_zona_nao_liga_busca_paga(monkeypatch):
    monkeypatch.setattr(net, "BRD_SERP_ZONE", "")
    monkeypatch.setattr(net, "has_key", lambda name: name == "brightdata")
    assert not net.brd_serp_enabled()
    assert serp.active_provider() == "duckduckgo"


def test_catalogo_nao_tem_mais_link_que_so_abre_a_home():
    for c in all_connectors():
        assert c.mode is not Mode.MANUAL, c.id
