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

try:  # iPhone grava HEIC por padrão; sem isto o Pillow não abre o arquivo
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:  # noqa: BLE001 — opcional: sem o pacote, HEIC cai em "não é uma imagem legível"
    pass

# Programas de edição: foto que passou por eles pode ter data e GPS alterados.
EDITORES = ("photoshop", "lightroom", "gimp", "snapseed", "picsart", "canva", "affinity", "pixelmator", "facetune")


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
    # A data em que a foto foi TIRADA e a lente ficam no sub-bloco "Exif", não no principal.
    try:
        tags.update({ExifTags.TAGS.get(k, k): v for k, v in exif.get_ifd(ExifTags.IFD.Exif).items()})
    except Exception:  # noqa: BLE001
        pass

    def texto(chave: str) -> str:
        v = tags.get(chave)
        if isinstance(v, bytes):
            v = v.decode("utf-8", "ignore")
        return str(v).replace("\x00", "").strip() if v not in (None, "") else ""

    marca, modelo = texto("Make"), texto("Model")
    if marca or modelo:
        resultado["camera"] = f"{marca} {modelo}".strip() if modelo.startswith(marca) is False else modelo
    for chave, campo in (("LensModel", "lente"), ("BodySerialNumber", "serie"), ("CameraOwnerName", "dono"),
                         ("Artist", "autor"), ("Copyright", "copyright"), ("Software", "software")):
        if texto(chave):
            resultado[campo] = texto(chave)

    # Da mais confiável (hora do disparo) para a menos (última gravação do arquivo).
    for chave, rotulo in (("DateTimeOriginal", "Tirada em"), ("DateTimeDigitized", "Digitalizada em"),
                          ("DateTime", "Arquivo gravado em")):
        if texto(chave):
            fuso = f" (fuso {texto('OffsetTimeOriginal')})" if chave == "DateTimeOriginal" and texto("OffsetTimeOriginal") else ""
            resultado["datas"].append(f"{rotulo}: {texto(chave)}{fuso}")
    original, gravada = texto("DateTimeOriginal"), texto("DateTime")
    editor = next((e for e in EDITORES if e in (resultado.get("software") or "").lower()), None)
    if editor:
        resultado["alerta"] = (f"Passou por programa de edição ({resultado['software']}): data, local e "
                               "conteúdo podem ter sido alterados.")
    elif original and gravada and original != gravada:
        resultado["alerta"] = "A data de gravação difere da data em que a foto foi tirada: o arquivo foi regravado."

    # GPS fica num sub-dicionário.
    try:
        gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:  # noqa: BLE001
        gps_ifd = None
    if gps_ifd:
        g = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
        lat = _dms_para_graus(g.get("GPSLatitude"), g.get("GPSLatitudeRef"))
        lon = _dms_para_graus(g.get("GPSLongitude"), g.get("GPSLongitudeRef"))
        if lat is not None and lon is not None:
            gps = {"lat": lat, "lon": lon, "maps": f"https://www.google.com/maps?q={lat},{lon}"}
            if g.get("GPSAltitude") is not None:
                altura = _rational(g["GPSAltitude"])
                gps["altitude"] = round(-altura if g.get("GPSAltitudeRef") in (1, b"\x01") else altura, 1)
            if g.get("GPSImgDirection") is not None:
                gps["direcao"] = round(_rational(g["GPSImgDirection"]), 1)
            if g.get("GPSDateStamp") and g.get("GPSTimeStamp"):
                try:
                    h, m, seg = (int(_rational(x)) for x in g["GPSTimeStamp"])
                    gps["utc"] = f"{str(g['GPSDateStamp']).replace(':', '-')} {h:02d}:{m:02d}:{seg:02d} UTC"
                except Exception:  # noqa: BLE001
                    pass
            resultado["gps"] = gps
    return resultado


def resumo_texto(info: dict) -> list[str]:
    """Transforma o dict de EXIF em linhas legíveis para a tela."""
    linhas: list[str] = []
    if info.get("camera"):
        linhas.append(f"📷 Câmera/aparelho: {info['camera']}")
    if info.get("lente"):
        linhas.append(f"🔭 Lente: {info['lente']}")
    if info.get("serie"):
        linhas.append(f"🔢 Número de série do corpo: {info['serie']} (identifica o aparelho)")
    if info.get("dono"):
        linhas.append(f"👤 Dono cadastrado no aparelho: {info['dono']}")
    if info.get("autor"):
        linhas.append(f"✍️ Autor: {info['autor']}")
    if info.get("copyright"):
        linhas.append(f"©️ Direitos: {info['copyright']}")
    if info.get("software"):
        linhas.append(f"🛠️ Software: {info['software']}")
    for d in info.get("datas", []):
        linhas.append(f"🕒 {d}")
    if info.get("dimensoes"):
        linhas.append(f"📐 Dimensões: {info['dimensoes']}")
    if info.get("gps"):
        g = info["gps"]
        extra = [f"altitude {g['altitude']} m"] if "altitude" in g else []
        if "direcao" in g:
            extra.append(f"câmera apontada a {g['direcao']}°")
        if "utc" in g:
            extra.append(f"fixado em {g['utc']}")
        linhas.append(f"📍 GPS: {g['lat']}, {g['lon']}" + (f" ({', '.join(extra)})" if extra else "")
                      + f" — {g['maps']}")
    return linhas
