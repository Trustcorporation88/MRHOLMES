"""
Busca reversa de imagem.

Quando o motor acha uma foto do alvo (avatar do GitHub, Gravatar, foto oficial),
esta camada gera automaticamente os links de busca reversa — para achar a mesma
foto (logo, o mesmo rosto) em outros lugares da web.

São deeplinks: cada um abre o buscador JÁ com a URL da foto carregada.
Rosto é o que mais amarra identidade em investigação, então isto costuma ser
o pulo do gato de um nome para os perfis reais.
"""

from __future__ import annotations

from urllib.parse import quote

from .findings import Confidence, Finding, FindingKind


def reverse_image_links(image_url: str) -> list[tuple[str, str, str]]:
    """(rótulo, url, descrição) — buscadores que aceitam a foto pela URL."""
    u = quote(image_url, safe="")
    return [
        ("Yandex Imagens", f"https://yandex.com/images/search?rpt=imageview&url={u}",
         "Melhor motor para rosto — acha a mesma pessoa em outros sites"),
        ("Google Lens", f"https://lens.google.com/uploadbyurl?url={u}",
         "Busca reversa do Google pela imagem"),
        ("Bing Visual", f"https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{u}",
         "Busca visual da Microsoft"),
        ("TinEye", f"https://tineye.com/search?url={u}",
         "Rastreia onde a imagem já foi publicada e desde quando"),
    ]


def face_findings(image_urls: list[str], max_images: int = 3) -> list[Finding]:
    """
    Para cada foto encontrada, adiciona os links de busca reversa como achados
    do tipo LINK — aparecem em «Fontes para abrir», prontos para clicar.
    """
    out: list[Finding] = []
    vistos: set[str] = set()
    for img in image_urls:
        if not img or img in vistos:
            continue
        vistos.add(img)
        if len(vistos) > max_images:
            break
        for rotulo, url, desc in reverse_image_links(img):
            out.append(Finding(
                kind=FindingKind.LINK,
                value=f"Busca reversa — {rotulo}",
                source="facesearch", source_label="Busca reversa de foto",
                url=url, confidence=Confidence.UNVERIFIED,
                detail=f"{desc}. Foto: {img[:60]}…",
                raw={"image": img, "engine": rotulo},
            ))
    return out
