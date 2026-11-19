"""Diretório de fontes: estrutura, links e filtros. Sem rede."""

from holmes import diretorio as d


def test_toda_fonte_tem_o_minimo_e_valores_validos():
    nomes_por_categoria = set()
    for categoria, icone, fontes in d.DIRETORIO:
        assert categoria and icone and fontes
        for f in fontes:
            assert f.nome and f.entrega, f
            assert f.url.startswith("https://"), f.nome
            assert f.custo in ("gratis", "login", "pago"), f.nome
            assert f.acesso in ("auto", "busca", "form", "codigo", "api"), f.nome
            assert (categoria, f.nome) not in nomes_por_categoria, f"repetida: {f.nome}"
            nomes_por_categoria.add((categoria, f.nome))


def test_link_embute_o_dado_e_so_os_digitos_quando_pedido():
    whats = next(f for f in d.todas() if f.nome == "WhatsApp")
    assert whats.link("(11) 98765-4321") == "https://wa.me/5511987654321"
    escavador = next(f for f in d.todas() if f.nome == "Escavador")
    assert escavador.link("João da Silva") == "https://www.escavador.com/busca?q=Jo%C3%A3o+da+Silva"


def test_sem_dado_o_link_cai_na_raiz_do_site_sem_marcador():
    for f in d.todas():
        for dado in ("", "   ", "sem digitos"):
            link = f.link(dado)
            assert "{q}" not in link and "{d}" not in link, f.nome
    whats = next(f for f in d.todas() if f.nome == "WhatsApp")
    assert whats.link("") == "https://wa.me/"
    assert whats.link("nome sem número") == "https://wa.me/"


def test_fonte_sem_marcador_abre_sempre_a_propria_pagina():
    onr = next(f for f in d.todas() if f.nome.startswith("Registradores"))
    assert not onr.aceita_dado and onr.link("123") == onr.url


def test_filtro_por_texto_custo_e_fonte_que_aceita_dado():
    protesto = d.filtrar("protesto")
    assert [f.nome for _, _, fs in protesto for f in fs if "CENPROT" in f.nome]
    pagas = [f for _, _, fs in d.filtrar(custo="pago") for f in fs]
    assert pagas and all(f.custo == "pago" for f in pagas)
    com_dado = [f for _, _, fs in d.filtrar(so_com_dado=True) for f in fs]
    assert com_dado and all(f.aceita_dado for f in com_dado)
    assert d.filtrar("termo que não existe em lugar nenhum") == []


def test_resumo_bate_com_a_arvore():
    r = d.resumo()
    assert r["total"] == len(d.todas()) and r["categorias"] == len(d.DIRETORIO)
    assert 0 < r["automaticas"] < r["total"]


def test_telefone_tem_o_localizador_como_primeira_fonte():
    telefone = next(fs for nome, _, fs in d.DIRETORIO if nome == "Telefone")
    assert telefone[0].acesso == "auto" and "dono" in telefone[0].nome.lower()
