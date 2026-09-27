from datetime import date
from unittest import mock

from holmes import cnpj_trust

DADOS = {
    "provedor": "CNPJá", "cnpj": "11.222.333/0001-81", "razao_social": "ACME LTDA", "fantasia": "Acme",
    "situacao": "ATIVA", "abertura": "2015-03-02", "porte": "ME", "mei": False, "simples": True,
    "capital_social": 50000.0, "natureza": "Sociedade Limitada", "atividade": "Comércio varejista",
    "endereco": "Rua A, 10, São Paulo/SP", "telefones": ["(11) 99999-0000"], "emails": ["x@acme.com"],
    "socios": [{"nome": "FULANO DE TAL", "qualificacao": "Sócio-Administrador", "desde": "2015-03-02",
                "faixa_etaria": "41 a 50", "documento": "***123456**", "tipo": "NATURAL"}],
    "inscricoes": [{"uf": "SP", "numero": "123", "ativa": True, "situacao": "Habilitada", "tipo": "IE Normal"}],
}


def test_secoes_trazem_socios_simples_e_inscricoes():
    secoes = dict(cnpj_trust.secoes_relatorio(DADOS))
    assert "Optante do Simples Nacional: sim" in secoes["Porte e tributação"]
    assert "Capital social: R$ 50.000,00" in secoes["Porte e tributação"]
    socios = secoes["Quadro de sócios (1)"]
    assert socios[0].startswith("FULANO DE TAL (Sócio-Administrador, desde 2015-03-02")
    assert secoes["Inscrições estaduais (1)"] == ["IE 123 (SP): ativa, Habilitada, IE Normal"]


def test_secoes_sem_dados_nao_quebram():
    secoes = dict(cnpj_trust.secoes_relatorio({"cnpj": "11.222.333/0001-81", "simples": None}))
    assert secoes["Quadro de sócios (0)"] == ["Nenhum sócio informado pela fonte."]
    assert "Optante do Simples Nacional: não informado" in secoes["Porte e tributação"]


def test_markdown_tem_cabecalho_e_fonte():
    md = cnpj_trust.relatorio_markdown(DADOS, hoje=date(2026, 9, 27))
    assert md.startswith("# CNPJ completo: ACME LTDA")
    assert "consultado em 27/09/2026" in md
    assert "- IE 123 (SP): ativa, Habilitada, IE Normal" in md


def test_relatorio_cai_para_markdown_sem_reportlab():
    with mock.patch.object(cnpj_trust, "consultar", return_value=DADOS), \
         mock.patch.object(cnpj_trust, "relatorio_pdf", side_effect=ImportError):
        conteudo, ext, mime = cnpj_trust.relatorio("11222333000181")
    assert ext == "md" and mime == "text/markdown"
    assert b"FULANO DE TAL" in conteudo


def test_relatorio_none_quando_consulta_falha():
    with mock.patch.object(cnpj_trust, "consultar", return_value=None):
        assert cnpj_trust.relatorio("11222333000181") is None
