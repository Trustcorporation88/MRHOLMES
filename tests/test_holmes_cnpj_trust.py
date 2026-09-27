"""
CNPJ Trust (cnpj.trustcorp.com.br): normalização das respostas do CNPJá e do
SintegraWS, conector da investigação e uso no Limpa Nome. Sem rede: as
respostas são simuladas.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import cnpj_trust as ct  # noqa: E402
from holmes import limpanome as ln  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import FindingKind  # noqa: E402

CNPJ = "11.222.333/0001-81"

CNPJA = {
    "taxId": "11222333000181", "alias": "ACME", "founded": "2015-03-02",
    "status": {"id": 2, "text": "Ativa"},
    "address": {"street": "Rua A", "number": "10", "district": "Centro", "city": "São Paulo",
                "state": "SP", "zip": "01000000"},
    "phones": [{"area": "11", "number": "40004000"}],
    "emails": [{"address": "CONTATO@ACME.COM.BR"}],
    "mainActivity": {"id": 4712100, "text": "Comércio varejista"},
    "company": {
        "name": "ACME COMERCIO LTDA", "equity": 50000.0,
        "nature": {"text": "Sociedade Empresária Limitada"},
        "size": {"acronym": "ME", "text": "Microempresa"},
        "simples": {"optant": True}, "simei": {"optant": False},
        "members": [
            {"since": "2015-03-02", "person": {"name": "Fulano de Tal", "type": "NATURAL",
                                               "age": "41-50", "taxId": "***123456**"},
             "role": {"text": "Sócio-Administrador"}},
            {"person": {"name": ""}},
        ],
    },
    "registrations": [{"state": "SP", "number": "123456789", "enabled": True,
                       "status": {"text": "Sem restrição"}, "type": {"text": "IE Normal"}}],
}

RECEITA = {"cnpj": "11.222.333/0001-81", "nome": "ACME COMERCIO LTDA", "fantasia": "ACME",
           "situacao": "ATIVA", "porte": "MICRO EMPRESA", "abertura": "02/03/2015",
           "qsa": [{"nome": "Fulano de Tal", "qual": "49-Sócio-Administrador"}],
           "logradouro": "Rua A", "numero": "10", "municipio": "São Paulo", "uf": "SP",
           "telefone": "(11) 4000-4000 / (11) 5000-5000", "email": "contato@acme.com.br"}


def _com_chave(monkeypatch, respostas):
    monkeypatch.setenv("CNPJ_TRUST_KEY", "chave-teste")
    chamadas = []

    def _get_json(url, params=None, headers=None, timeout=None, ttl=None):
        chamadas.append((url, params, headers))
        for caminho, resposta in respostas.items():
            if url.endswith(caminho):
                if isinstance(resposta, Exception):
                    raise resposta
                return resposta
        return None

    monkeypatch.setattr(ct.net, "get_json", _get_json)
    return chamadas


def test_normaliza_cnpja():
    d = ct.normalizar_cnpja(CNPJA)
    assert d["razao_social"] == "ACME COMERCIO LTDA" and d["cnpj"] == CNPJ
    assert d["porte"] == "ME" and d["simples"] is True and d["mei"] is False
    assert d["situacao"] == "ATIVA" and d["capital_social"] == 50000.0
    assert d["socios"] == [{"nome": "Fulano de Tal", "qualificacao": "Sócio-Administrador",
                            "desde": "2015-03-02", "faixa_etaria": "41-50",
                            "documento": "***123456**", "tipo": "NATURAL"}]
    assert d["inscricoes"][0]["numero"] == "123456789" and d["inscricoes"][0]["ativa"]
    assert d["telefones"] == ["(11) 40004000"] and "São Paulo/SP" in d["endereco"]


def test_simei_vira_porte_mei():
    dados = {**CNPJA, "company": {**CNPJA["company"], "simei": {"optant": True}}}
    assert ct.normalizar_cnpja(dados)["porte"] == "MEI"


def test_normaliza_receita_do_sintegra():
    d = ct.normalizar_receita(RECEITA)
    assert d["provedor"] == "SintegraWS" and d["porte"] == "ME"
    assert d["socios"][0]["nome"] == "Fulano de Tal"
    assert d["telefones"] == ["(11) 4000-4000", "(11) 5000-5000"]


def test_consulta_usa_a_chave_e_cai_para_o_sintegra(monkeypatch):
    chamadas = _com_chave(monkeypatch, {"/api/cnpja/office": None, "/api/sws/rf": RECEITA})
    d = ct.consultar(CNPJ)
    assert d["provedor"] == "SintegraWS"
    url, params, headers = chamadas[0]
    assert url == "https://cnpj.trustcorp.com.br/api/cnpja/office"
    assert params == {"cnpj": "11222333000181", "simples": "true", "registrations": "ALL"}
    assert headers["x-access-key"] == "chave-teste"


def test_sem_chave_nao_consulta(monkeypatch):
    monkeypatch.delenv("CNPJ_TRUST_KEY", raising=False)
    assert not ct.configurado() and ct.consultar(CNPJ) is None
    assert ct.comprovante_pdf(CNPJ) is None


def test_erro_de_rede_nao_derruba(monkeypatch):
    import requests

    _com_chave(monkeypatch, {"/api/cnpja/office": requests.ConnectionError("x"),
                             "/api/sws/rf": requests.Timeout("y")})
    assert ct.consultar(CNPJ) is None
    assert ct.consultar("123") is None


def test_findings_da_investigacao(monkeypatch):
    _com_chave(monkeypatch, {"/api/cnpja/office": CNPJA})
    achados = list(ct.findings(detect(CNPJ)))
    por_tipo = {}
    for f in achados:
        por_tipo.setdefault(f.kind, []).append(f)
    empresa = por_tipo[FindingKind.COMPANY][0]
    assert empresa.value == "ACME COMERCIO LTDA" and "porte ME" in empresa.detail and "Simples" in empresa.detail
    socio = por_tipo[FindingKind.NAME][0]
    assert socio.value == "Fulano de Tal" and "Sócio-Administrador" in socio.detail
    assert por_tipo[FindingKind.EMAIL][0].value == "contato@acme.com.br"
    assert any("IE 123456789" in f.value for f in por_tipo[FindingKind.DOCUMENT])


def test_socio_do_cnpj_trust_vira_pivo():
    from holmes import pivot as pivot_mod
    from holmes.findings import Confidence, Finding

    f = Finding(kind=FindingKind.NAME, value="Fulano de Tal", source="cnpj_trust",
                source_label="CNPJ Trust", confidence=Confidence.CONFIRMED, detail="Sócio de ACME")
    assert pivot_mod.from_findings([f], 1, detect(CNPJ))


def test_conector_registrado_e_pago():
    from holmes.connectors import ensure_registered
    from holmes.connectors.base import get_connector

    ensure_registered()
    c = get_connector("cnpj_trust")
    assert c.requires_key == "cnpj_trust" and c.cost == "pago"


def test_limpa_nome_usa_o_cnpj_trust_quando_configurado(monkeypatch):
    dados = {**CNPJA, "company": {**CNPJA["company"], "simei": {"optant": True}}}
    _com_chave(monkeypatch, {"/api/cnpja/office": dados})
    caso = ln.Caso()
    assert ln.preencher_empresa(caso, CNPJ) is None
    assert caso.porte == "MEI" and caso.razao_social == "ACME COMERCIO LTDA" and caso.situacao_cadastral == "ATIVA"


def test_comprovante_pdf(monkeypatch):
    class _R:
        status_code = 200
        content = b"%PDF-1.7 ..."

    monkeypatch.setenv("CNPJ_TRUST_KEY", "k")
    pedidos = []
    monkeypatch.setattr(ct.requests, "get", lambda url, params=None, headers=None, timeout=None:
                        pedidos.append((url, params, headers)) or _R())
    assert ct.comprovante_pdf(CNPJ).startswith(b"%PDF")
    assert pedidos[0][0].endswith("/api/comprovante-rf") and pedidos[0][2]["x-access-key"] == "k"
