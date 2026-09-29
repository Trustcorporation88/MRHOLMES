"""Streamlit não roda nos testes: confere o menu pelo código-fonte do web_app."""

import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "web_app.py").read_text(encoding="utf-8")


def _grupos() -> dict[str, list[str]]:
    bloco = SRC[SRC.index("NAV_GROUPS = ["):]
    bloco = bloco[: bloco.index("\n]\n") + 3]
    return {nome: re.findall(r'"([^"]+)"', ids) for nome, ids in re.findall(r'\("([^"]+)", \[(.*?)\]\)', bloco, re.S)}


def test_principal_tem_so_o_que_se_usa():
    assert _grupos()["Principal"] == ["Investigar", "Limpar Nome", "Monitoramento"]


def test_robin_virou_dark_web_em_ferramentas_manuais():
    grupos = _grupos()
    assert "Dark web" in grupos["Ferramentas manuais"]
    assert "OSINT Premium" not in {p for ids in grupos.values() for p in ids}


def test_toda_pagina_do_menu_tem_ramo_e_rotulo():
    opcoes = re.findall(r'"([^"]+)"', SRC[SRC.index("NAV_OPTIONS = ["): SRC.index("NAV_LABEL")])
    for pagina in {p for ids in _grupos().values() for p in ids}:
        assert pagina in opcoes, pagina
        assert f'page == "{pagina}"' in SRC, f"sem ramo para {pagina}"


def test_pagina_dark_web_abre_o_robin():
    ramo = SRC[SRC.index('elif page == "Dark web":'):]
    ramo = ramo[: ramo.index("\n# ──")]
    assert "display_robin_workspace()" in ramo
    assert "display_osint_premium" not in SRC
