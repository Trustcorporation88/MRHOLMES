"""
Análise de foto.

Duas coisas, ambas úteis em investigação:

1. EXIF (offline, sem rede): metadados embutidos na foto — câmera/celular que
   tirou, data/hora, e principalmente COORDENADAS GPS quando existem. Uma foto
   com GPS entrega o local exato onde foi tirada. É o dado mais forte que uma
   imagem pode carregar, e some assim que ela passa por rede social — por isso
   só vale em foto original (enviada por e-mail, WhatsApp Documento, etc.).

2. Busca reversa: links de Yandex, Google Lens e TinEye para achar a mesma
   foto (rosto) em outros lugares — reaproveita holmes.facesearch.
"""

from __future__ import annotations

from typing import Any


def _rational(v: Any) -> float:
    try:
        return float(v[0]) / float(v[1]) if isinstance(v, tuple) else float(v)
    except Exception:
        return 0.0


def _dms_para_graus(dms, ref) -> float | None:
    """Converte grau/minuto/segundo do EXIF em decimal (com sinal por hemisfério)."""
    try:
        g = _rational(dms[0]) + _rational(dms[1]) / 60 + _rational(dms[2]) / 3600
        if ref in ("S", "W"):
            g = -g
        return round(g, 6)
    except Exception:
        return None


def analisar_bytes(data: bytes) -> dict:
    """
    Lê os metadados da imagem. Retorna dict com câmera, datas, GPS e dimensões.
    Nunca levanta exceção — foto sem EXIF apenas volta com campos vazios.
    """
    resultado: dict[str, Any] = {
        "tem_exif": False, "camera": None, "datas": [], "gps": None,
        "software": None, "dimensoes": None, "aviso": None,
    }
    try:
        import io

        from PIL import Image, ExifTags
    except ImportError:
        resultado["aviso"] = "Pillow não instalado — não foi possível ler EXIF."
        return resultado

    try:
        img = Image.open(io.BytesIO(data))
        resultado["dimensoes"] = f"{img.width}×{img.height}"
        exif = img.getexif()
    except Exception:
        resultado["aviso"] = "Arquivo não é uma imagem legível."
        return resultado

    if not exif:
        resultado["aviso"] = (
            "A foto não tem metadados EXIF. Provavelmente passou por rede social "
            "(que remove tudo) ou é um print/captura."
        )
        return resultado

    resultado["tem_exif"] = True
    tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}

    marca = str(tags.get("Make", "")).strip()
    modelo = str(tags.get("Model", "")).strip()
    if marca or modelo:
        resultado["camera"] = f"{marca} {modelo}".strip()
    if tags.get("Software"):
        resultado["software"] = str(tags["Software"]).strip()
    for campo in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
        if tags.get(campo):
            resultado["datas"].append(f"{campo}: {tags[campo]}")

    # GPS fica num sub-dicionário.
    try:
        gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:
        gps_ifd = None
    if gps_ifd:
        g = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
        lat = _dms_para_graus(g.get("GPSLatitude"), g.get("GPSLatitudeRef"))
        lon = _dms_para_graus(g.get("GPSLongitude"), g.get("GPSLongitudeRef"))
        if lat is not None and lon is not None:
            resultado["gps"] = {
                "lat": lat, "lon": lon,
                "maps": f"https://www.google.com/maps?q={lat},{lon}",
            }
    return resultado


def resumo_texto(info: dict) -> list[str]:
    """Transforma o dict de EXIF em linhas legíveis para a tela."""
    linhas: list[str] = []
    if info.get("camera"):
        linhas.append(f"📷 Câmera/aparelho: {info['camera']}")
    if info.get("software"):
        linhas.append(f"🛠️ Software: {info['software']}")
    for d in info.get("datas", []):
        linhas.append(f"🕒 {d}")
    if info.get("dimensoes"):
        linhas.append(f"📐 Dimensões: {info['dimensoes']}")
    if info.get("gps"):
        g = info["gps"]
        linhas.append(f"📍 GPS: {g['lat']}, {g['lon']} — {g['maps']}")
    return linhas
