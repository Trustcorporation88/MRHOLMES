"""Streamlit não roda nos testes: confere o menu pelo código-fonte do web_app."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = (RAIZ / "web_app.py").read_text(encoding="utf-8")


def _grupos() -> dict[str, list[str]]:
    bloco = SRC[SRC.index("NAV_GROUPS = ["):]
    bloco = bloco[: bloco.index("\n]\n") + 3]
    return {nome: re.findall(r'"([^"]+)"', ids) for nome, ids in re.findall(r'\("([^"]+)", \[(.*?)\]\)', bloco, re.S)}


def _opcoes() -> list[str]:
    linha = SRC[SRC.index("NAV_OPTIONS = ["):]
    return re.findall(r'"([^"]+)"', linha[: linha.index("]")])


def test_menu_tem_so_as_seis_paginas_que_funcionam():
    assert _opcoes() == ["Investigar", "Diretório", "Limpar Nome", "Monitoramento", "Dark web", "Histórico"]
    assert _grupos()["Consultas"] == ["Investigar", "Diretório"]


def test_toda_pagina_do_menu_tem_ramo_e_esta_num_grupo():
    agrupadas = [p for ids in _grupos().values() for p in ids]
    assert sorted(agrupadas) == sorted(_opcoes())
    for pagina in _opcoes():
        assert f'page == "{pagina}"' in SRC, f"sem ramo para {pagina}"


def test_pagina_dark_web_abre_o_robin():
    ramo = SRC[SRC.index('elif page == "Dark web":'):]
    ramo = ramo[: ramo.index("\n# ──")]
    assert "display_robin_workspace()" in ramo


def test_nada_importa_o_que_foi_removido():
    removidos = ("osint_premium", "external_services", "osint_partners", "investigate_workspace",
                 "Core.Support.History", "Core.Support.DorkWorkbench", "Core.Support.OsintTools",
                 "MrHolmes")
    for arquivo in list(RAIZ.glob("*.py")) + list((RAIZ / "holmes").rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        for nome in removidos:
            assert f"import {nome}" not in texto and f"from {nome}" not in texto, (arquivo.name, nome)


def test_navegacao_enfileira_e_aplica():
    from nav import apply_pending_navigation, queue_navigation

    sessao: dict = {"nav_page": "Telefone"}  # página que não existe mais
    apply_pending_navigation(sessao, _opcoes())
    assert sessao["nav_page"] == "Investigar"
    queue_navigation(sessao, "Diretório")
    apply_pending_navigation(sessao, _opcoes())
    assert sessao["nav_page"] == "Diretório" and "_pending_nav" not in sessao
    queue_navigation(sessao, "Página inventada")
    apply_pending_navigation(sessao, _opcoes())
    assert sessao["nav_page"] == "Diretório"
