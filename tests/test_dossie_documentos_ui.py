"""Streamlit não roda nos testes: confere a montagem da tela pelo código-fonte."""

from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "holmes_ui.py").read_text(encoding="utf-8")


def _corpo(nome: str) -> str:
    ini = SRC.index(f"def {nome}(")
    fim = SRC.find("\ndef ", ini + 1)
    return SRC[ini:fim if fim != -1 else len(SRC)]


def test_bloco_de_documentos_fica_no_topo_do_dossie():
    dossie = _corpo("_render_dossier")
    assert "_render_documento(dossier)" in dossie
    assert dossie.index("_render_documento(dossier)") < dossie.index("Leitura do caso")


def test_bloco_junta_cnpj_e_bigdatacorp():
    bloco = _corpo("_render_documento")
    assert "botoes_cnpj(dossier.entity.value" in bloco
    assert "_render_bigdatacorp(dossier)" in bloco
    assert "cnpj_trust.configurado()" in bloco and "bigdatacorp.configurado()" in bloco


def test_botoes_do_cnpj_saem_do_exportar():
    assert "botoes_cnpj" not in _corpo("_render_export")
