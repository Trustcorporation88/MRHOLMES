"""O tema precisa chegar ao navegador: sem "<" no CSS e com as classes usadas."""

import re
from pathlib import Path

import tema

RAIZ = Path(__file__).resolve().parent.parent


def test_css_nao_tem_nada_com_cara_de_tag():
    # O sanitizador do st.html descarta o estilo inteiro se achar "<".
    assert tema.css_valido()
    assert not tema.css_valido("a{} /* um <p> no comentario */")


def test_web_app_aplica_o_tema_e_nao_carrega_css_proprio():
    src = (RAIZ / "web_app.py").read_text(encoding="utf-8")
    assert "tema.aplicar()" in src
    assert "<style>" not in src


def test_fonte_dos_icones_do_streamlit_esta_preservada():
    assert "Material Symbols Rounded" in tema.CSS


def test_toda_classe_usada_na_interface_existe_no_tema():
    usadas = set()
    for nome in ("web_app.py", "holmes_ui.py", "diretorio_ui.py", "limpanome_ui.py"):
        texto = (RAIZ / nome).read_text(encoding="utf-8")
        for bloco in re.findall(r"class=[\'\"]([^\'\"{}]+)[\'\"]", texto):
            usadas.update(c for c in bloco.split() if c.startswith("mh-"))
    faltando = sorted(c for c in usadas if f".{c}" not in tema.CSS)
    assert not faltando, faltando


def test_logotipo_e_icone_existem_com_fundo_transparente():
    from PIL import Image

    for nome in ("logo.png", "icone.png"):
        arquivo = RAIZ / "assets" / nome
        assert arquivo.exists(), nome
        img = Image.open(arquivo)
        assert img.mode == "RGBA", nome
        # as bordas transparentes evitam a moldura escura em volta do logotipo
        assert img.getpixel((1, 1))[3] == 0 and img.getpixel((img.size[0] - 2, img.size[1] // 2))[3] == 0, nome
        assert img.getpixel((img.size[0] // 2, img.size[1] // 2))[3] > 0, nome


def test_fontes_do_tema_estao_no_config():
    config = (RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'font = "Inter:' in config and 'headingFont = "Sora:' in config
    assert 'codeFont = "JetBrains Mono:' in config
