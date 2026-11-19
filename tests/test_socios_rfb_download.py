"""Índice de sócios: leitura da pasta compartilhada da Receita. Sem rede."""

from unittest import mock

from holmes import socios_rfb as s

WEBDAV = """<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2026-10/</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/2026-11/</d:href></d:response>
<d:response><d:href>/public.php/webdav/Dados/Cadastros/CNPJ/cnpj.tar.gz</d:href></d:response>
</d:multistatus>"""


def test_listagem_webdav_e_pagina_de_indice():
    assert s.nomes_da_listagem(WEBDAV) == ["CNPJ", "2026-10", "2026-11", "cnpj.tar.gz"]
    html = '<a href="2026-09/">2026-09/</a> <a href="Socios0.zip">Socios0.zip</a> <a href="?C=N;O=D">x</a>'
    assert s.nomes_da_listagem(html) == ["2026-09", "Socios0.zip"]


def test_padrao_usa_a_pasta_compartilhada_com_o_codigo_como_usuario():
    assert s.BASE_URL.endswith("/public.php/webdav/Dados/Cadastros/CNPJ/")
    assert s._webdav() and s._auth() == (s.TOKEN, "")


def test_mes_pela_metade_e_pulado():
    completo = ["2026-10"] + s.ARQUIVOS + ["Empresas0.zip"]
    pela_metade = ["2026-11"] + s.ARQUIVOS[:4]

    def falso(pasta=""):
        return {"": ["CNPJ", "2026-10", "2026-11", "cnpj.tar.gz"],
                "2026-11/": pela_metade, "2026-10/": completo}[pasta]

    with mock.patch.object(s, "_listar", side_effect=falso), \
         mock.patch.dict("os.environ", {"HOLMES_RFB_CNPJ_MES": ""}):
        assert s.mes_mais_recente() == "2026-10"


def test_mes_fixado_por_variavel_nao_consulta_a_receita():
    with mock.patch.object(s, "_listar", side_effect=AssertionError("não devia listar")), \
         mock.patch.dict("os.environ", {"HOLMES_RFB_CNPJ_MES": "2026-08"}):
        assert s.mes_mais_recente() == "2026-08"
