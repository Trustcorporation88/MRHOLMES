"""
Limpa Nome para empresa (CNPJ): porte e Juizado, canais sem consumidor.gov.br,
dano moral da pessoa jurídica, dívida ativa e CADIN, kit e Watson.
Nada aqui toca a rede.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import limpanome as ln  # noqa: E402
from holmes import limpanome_kit as kit  # noqa: E402

HOJE = date(2026, 9, 27)
CNPJ = "11.222.333/0001-81"


def _empresa(porte="ME", **kw):
    return ln.Caso(tipo="pj", cnpj=CNPJ, razao_social="ACME COMERCIO LTDA", porte=porte, **kw)


# ── porte e Receita ─────────────────────────────────────────────────────────

def test_porte_da_receita_nas_tres_fontes():
    assert ln.porte_da_receita({"porte": "MICRO EMPRESA"}) == "ME"
    assert ln.porte_da_receita({"porte": "EMPRESA DE PEQUENO PORTE"}) == "EPP"
    assert ln.porte_da_receita({"porte": "DEMAIS"}) == "DEMAIS"
    assert ln.porte_da_receita({"porte": "MICRO EMPRESA", "opcao_pelo_mei": True}) == "MEI"
    assert ln.porte_da_receita({"descricao_porte": "ME"}) == "ME"
    assert ln.porte_da_receita({}) == ""


def test_preencher_empresa_pela_receita():
    caso = ln.Caso()
    erro = ln.preencher_empresa(caso, "11222333000181", consulta=lambda c: {
        "razao_social": "ACME COMERCIO LTDA", "porte": "EMPRESA DE PEQUENO PORTE",
        "descricao_situacao_cadastral": "ATIVA"})
    assert erro is None
    assert caso.pj and caso.cnpj == CNPJ and caso.porte == "EPP" and caso.situacao_cadastral == "ATIVA"
    assert caso.nome == "ACME COMERCIO LTDA"
    assert "inválido" in ln.preencher_empresa(ln.Caso(), "11.222.333/0001-80")
    assert "Receita" in ln.preencher_empresa(ln.Caso(), CNPJ, consulta=lambda c: None)


def test_juizado_so_para_mei_me_epp():
    assert ln.Caso().pode_juizado
    for porte, pode in (("MEI", True), ("ME", True), ("EPP", True), ("DEMAIS", False), ("", False)):
        assert _empresa(porte).pode_juizado is pode, porte


# ── regras ──────────────────────────────────────────────────────────────────

def test_empresa_nao_usa_consumidor_gov_salvo_mei():
    r = ln.Registro(credor="Banco", valor=10, vencimento="2025-01-01", situacao="ja_paguei", comprovante=True)
    a = ln.analisar(r, HOJE, _empresa("ME"))
    assert a.canal == "credor" and "consumidor_gov" not in a.documentos
    a_mei = ln.analisar(r, HOJE, _empresa("MEI"))
    assert a_mei.canal == "consumidor.gov.br" and "consumidor_gov" in a_mei.documentos
    # pessoa física continua igual
    assert ln.analisar(r, HOJE).canal == "consumidor.gov.br"


def test_empresa_tem_dano_moral_e_onus_da_prova_sem_cdc():
    r = ln.Registro(credor="Fornecedor", valor=10, vencimento="2025-01-01", situacao="nao_reconheco")
    a = ln.analisar(r, HOJE, _empresa("EPP"))
    bases = [x.base for x in a.argumentos]
    assert any("Súmula 227" in b for b in bases)
    assert any("CPC art. 373" in b for b in bases)
    assert not any("6º, VIII" in b for b in bases)
    txt = ln.gerar_documento("contestacao_nao_reconheco", _empresa("EPP", registros=[r]), r, HOJE)
    assert "CPC art. 373" in txt and "6º, VIII" not in txt and "CNPJ" in txt


def test_empresa_grande_avisa_que_nao_cabe_no_juizado():
    r = ln.Registro(credor="X", valor=1, vencimento="2025-01-01", situacao="nao_reconheco")
    assert "Justiça comum" in ln.analisar(r, HOJE, _empresa("DEMAIS")).alerta


def test_prazo_de_5_anos_vale_para_empresa():
    r = ln.Registro(credor="X", valor=1, vencimento="2019-01-01")
    a = ln.analisar(r, HOJE, _empresa("ME"))
    assert a.pilha == "vencido" and a.canal == "biro" and a.documentos == ["pedido_baixa_prazo"]


def test_documento_de_empresa_tem_razao_social_e_cnpj():
    r = ln.Registro(credor="Banco", valor=1234.5, vencimento="2019-01-01")
    txt = ln.gerar_documento("pedido_baixa_prazo", _empresa("ME", registros=[r]), r, HOJE)
    assert txt.startswith(f"A empresa ACME COMERCIO LTDA, CNPJ {CNPJ}, por seu representante legal")


# ── dívida ativa ────────────────────────────────────────────────────────────

def test_divida_ativa_paga_pede_baixa_no_cadin():
    r = ln.Registro(credor="PGFN", valor=5000, biro=ln.DIVIDA_ATIVA, situacao="ja_paguei")
    a = ln.analisar(r, HOJE, _empresa())
    assert a.canal == "regularize" and a.limite_5_anos is None
    assert "10.522" in a.argumento_principal.base
    txt = ln.gerar_documento("pedido_baixa_cadin", _empresa(registros=[r]), r, HOJE)
    assert "5 dias úteis" in txt and "art. 2º, §5º" in txt


def test_divida_ativa_verdadeira_negocia_com_mais_parcelas_para_pequena():
    r = ln.Registro(credor="PGFN", valor=5000, biro=ln.DIVIDA_ATIVA, situacao="minha_no_prazo")
    a = ln.analisar(r, HOJE, _empresa("EPP"))
    assert a.pilha == "verdadeira" and a.documentos == ["roteiro_divida_ativa"]
    assert "133 parcelas" in a.argumento_principal.texto
    assert "133 parcelas" not in ln.analisar(r, HOJE, _empresa("DEMAIS")).argumento_principal.texto
    assert "Regularize" in ln.gerar_documento("roteiro_divida_ativa", _empresa("EPP"), r, HOJE)


def test_divida_ativa_com_erro_pede_revisao():
    r = ln.Registro(credor="Estado", valor=1, biro=ln.DIVIDA_ATIVA, situacao="valor_errado", observacao="já pago em parte")
    a = ln.analisar(r, HOJE, _empresa())
    assert a.documentos == ["pedido_revisao_divida_ativa"]
    assert "suspensão" in ln.gerar_documento("pedido_revisao_divida_ativa", _empresa(), r, HOJE)


# ── avisos, escalada, kit e Watson ──────────────────────────────────────────

def test_avisos_de_empresa():
    caso = _empresa("", situacao_cadastral="INAPTA",
                    registros=[ln.Registro(credor="A", valor=1, vencimento="2025-01-01")])
    avisos = " ".join(ln.avisos_do_caso(caso, HOJE))
    assert "INAPTA" in avisos and "porte" in avisos and "certidões" in avisos


def test_escalada_de_empresa():
    etapas = [e for e, _ in ln.escalada(_empresa("ME"))]
    assert "consumidor.gov.br" not in etapas and "Juizado Especial Cível" in etapas
    assert "consumidor.gov.br" in [e for e, _ in ln.escalada(_empresa("MEI"))]
    assert "Justiça comum" in [e for e, _ in ln.escalada(_empresa("DEMAIS"))]
    assert "consumidor.gov.br" in [e for e, _ in ln.escalada(ln.Caso())]


def test_kit_de_empresa():
    r = ln.Registro(credor="Banco", valor=10, vencimento="2025-01-01", situacao="nao_reconheco")
    caso = _empresa("DEMAIS", registros=[r])
    secoes = dict(kit.secoes_do_kit(caso, r, HOJE))
    assert secoes["Identificação"][0] == "Empresa: ACME COMERCIO LTDA"
    assert any("Contrato social" in p for p in secoes["Provas para juntar"])
    assert any("Súmula 227" in p for p in secoes["Pedidos"])
    assert any("Justiça comum" in o for o in secoes["Onde levar"])


def test_watson_recebe_empresa_com_agente_civel():
    r = ln.Registro(credor="Banco", valor=10, vencimento="2025-01-01", situacao="nao_reconheco")
    caso = _empresa("DEMAIS", registros=[r])
    txt = ln.texto_para_watson(caso, r, HOJE)
    assert "Sou a empresa ACME COMERCIO LTDA" in txt and "não posso usar o Juizado" in txt
    assert "Justiça comum" in txt and "Súmula 227" in txt
    b64 = ln.link_watson(caso, r, HOJE).split("#caso=", 1)[1]
    dados = json.loads(base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)).decode("utf-8"))
    assert dados["agente"] == "civel"
    mei = _empresa("MEI", registros=[r])
    b64 = ln.link_watson(mei, r, HOJE).split("#caso=", 1)[1]
    assert json.loads(base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)))["agente"] == "consumidor"


def test_caso_de_empresa_salva_e_recarrega(monkeypatch):
    import pathlib
    import tempfile

    from holmes import store

    monkeypatch.setattr(ln, "CASOS_DIR", pathlib.Path(tempfile.mkdtemp()))
    monkeypatch.setattr(store, "enabled", lambda: False)
    caso = _empresa("EPP", situacao_cadastral="ATIVA")
    lido = ln.carregar(ln.salvar(caso))
    assert (lido.tipo, lido.cnpj, lido.porte, lido.razao_social, lido.situacao_cadastral) == \
        ("pj", CNPJ, "EPP", "ACME COMERCIO LTDA", "ATIVA")
