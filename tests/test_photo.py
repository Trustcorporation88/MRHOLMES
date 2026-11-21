"""Análise de foto: metadados embutidos. Sem rede."""

import io

import pytest
from PIL import Image

from holmes import photo


def _foto(exif: Image.Exif | None = None, formato: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    kw = {"exif": exif} if exif is not None else {}
    Image.new("RGB", (64, 48), (90, 120, 160)).save(buf, formato, **kw)
    return buf.getvalue()


def _exif_completo(software: str = "") -> Image.Exif:
    ex = Image.Exif()
    ex[0x010F], ex[0x0110] = "Apple", "iPhone 14 Pro"
    ex[0x0132] = "2026:11:03 09:00:00"                       # gravada depois
    if software:
        ex[0x0131] = software
    sub = ex.get_ifd(0x8769)
    sub[0x9003] = "2026:11:02 18:41:07"                      # tirada
    sub[0x9011] = "-03:00"
    sub[0xA434] = "iPhone 14 Pro back camera 6.86mm f/1.78"
    sub[0xA431] = "F2LXXXXXXXXX"
    g = ex.get_ifd(0x8825)
    g[1], g[2], g[3], g[4] = "S", (22.0, 57.0, 6.0), "W", (43.0, 12.0, 38.0)
    g[5], g[6] = 0, 710.5
    g[17] = 182.4
    g[29], g[7] = "2026:11:02", (21.0, 41.0, 5.0)
    return ex


def test_le_data_original_lente_serie_e_gps_completo():
    info = photo.analisar_bytes(_foto(_exif_completo()))
    assert info["tem_exif"] and info["camera"] == "Apple iPhone 14 Pro"
    assert info["datas"][0] == "Tirada em: 2026:11:02 18:41:07 (fuso -03:00)"
    assert "Arquivo gravado em: 2026:11:03 09:00:00" in info["datas"]
    assert info["lente"].startswith("iPhone 14 Pro back camera") and info["serie"] == "F2LXXXXXXXXX"
    gps = info["gps"]
    assert (gps["lat"], gps["lon"]) == (-22.951667, -43.210556)
    assert gps["altitude"] == 710.5 and gps["direcao"] == 182.4 and gps["utc"] == "2026-11-02 21:41:05 UTC"
    assert gps["maps"].endswith("-22.951667,-43.210556")


def test_alerta_de_regravacao_e_de_programa_de_edicao():
    assert "regravado" in photo.analisar_bytes(_foto(_exif_completo()))["alerta"]
    editada = photo.analisar_bytes(_foto(_exif_completo("Adobe Photoshop 25.0")))
    assert "programa de edição" in editada["alerta"]


def test_foto_sem_exif_explica_o_motivo():
    info = photo.analisar_bytes(_foto())
    assert not info["tem_exif"] and "rede social" in info["aviso"] and info["gps"] is None


def test_arquivo_que_nao_e_imagem_nao_levanta_erro():
    assert "não é uma imagem" in photo.analisar_bytes(b"isto nao e uma foto")["aviso"]


def test_resumo_na_tela_traz_cada_campo():
    texto = "\n".join(photo.resumo_texto(photo.analisar_bytes(_foto(_exif_completo()))))
    for trecho in ("Câmera/aparelho: Apple iPhone 14 Pro", "Lente:", "Número de série do corpo", "Tirada em:",
                   "GPS: -22.951667, -43.210556", "altitude 710.5 m", "câmera apontada a 182.4°"):
        assert trecho in texto, trecho


def test_foto_heic_do_iphone_e_aberta():
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 90, 40)).save(buf, "HEIF", exif=_exif_completo())
    info = photo.analisar_bytes(buf.getvalue())
    assert info["tem_exif"] and info["gps"] and info["datas"][0].startswith("Tirada em:")
