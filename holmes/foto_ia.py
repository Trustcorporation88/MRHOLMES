"""
Leitura do CENÁRIO de uma foto por IA de visão.

O EXIF (`photo.py`) diz onde a foto foi tirada quando o aparelho gravou o GPS.
Rede social apaga isso, e aí sobra o que está dentro da imagem: fundo,
construções, vegetação, tipo de rua, sinalização, veículos, letreiros e placas.
É a mesma técnica de quem geolocaliza foto em OSINT: pista por pista, com a
confiança de cada uma, e um local provável que é estimativa e não prova.

Regras que o modelo recebe, e que os testes conferem:
  * nunca identifica pessoas pelo rosto nem diz quem alguém é;
  * só afirma o que está visível;
  * confiança honesta: sem base, "nenhuma", nunca um palpite com cara de certeza;
  * transcreve todo texto legível (letreiro, endereço, telefone, placa de veículo).

Custa uma chamada ao modelo (alguns centavos): só roda quando o usuário pede.
"""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Any
from urllib.parse import quote_plus

import requests

from . import photo  # noqa: F401 — registra o leitor de HEIC no Pillow
from .limpanome_arquivos import _chave, _modelos_anthropic

LIMITE_BYTES = 20 * 1024 * 1024
LADO_MAXIMO = 1568          # acima disso o modelo reduz sozinho; mandar menor poupa tempo e custo

SISTEMA = (
    "Você ajuda numa investigação com fontes abertas (OSINT) a ler o CENÁRIO de uma foto: fundo, "
    "construções, vegetação, relevo, vias, sinalização, veículos, textos e iluminação. "
    "Responda SOMENTE com um objeto JSON, sem nenhum texto fora dele.\n"
    "Regras:\n"
    "1. Nunca identifique pessoas pelo rosto nem diga quem alguém é. Pessoas só entram como contagem e "
    "contexto genérico (ex.: 'duas pessoas de camiseta, ao fundo').\n"
    "2. Só afirme o que está visível. Cada pista traz o que foi observado, o que isso indica e a confiança.\n"
    "3. Para o local, preencha país, região, cidade e ponto somente se houver base; sem base, confiança "
    "'nenhuma' e campos nulos. Nunca invente nome de rua ou número.\n"
    "4. Transcreva literalmente todo texto legível (letreiros, placas de veículo, endereços, telefones) e "
    "marque o que estiver ilegível ou parcial.\n"
    "5. Em 'limites' diga o que impede uma conclusão melhor (foto escura, sem ponto de referência, recorte "
    "pequeno, edição aparente)."
)

INSTRUCAO = """Analise o cenário desta foto e devolva exatamente este JSON (português do Brasil):
{
  "resumo": "duas ou três frases sobre o que a foto mostra",
  "ambiente": "interno | externo | misto",
  "pistas": [
    {"tipo": "arquitetura | vegetação | sinalização | veículo | texto | relevo | clima e luz | ponto de referência | outro",
     "observado": "o que se vê",
     "indica": "o que isso sugere sobre o lugar, a época ou o contexto",
     "confianca": "alta | media | baixa"}
  ],
  "textos_visiveis": ["texto literal, com [parcial] ou [ilegível] quando for o caso"],
  "local_provavel": {
    "pais": null, "regiao": null, "cidade": null, "ponto": null,
    "confianca": "alta | media | baixa | nenhuma",
    "motivo": "as pistas que sustentam a estimativa"
  },
  "como_confirmar": ["passos concretos: o que procurar no Street View, no mapa ou na busca reversa"],
  "limites": ["o que atrapalha a análise"]
}"""

_PLACA = re.compile(r"\b[A-Z]{3}[- ]?\d[A-Z0-9]\d{2}\b")
CONFIANCAS = ("alta", "media", "baixa", "nenhuma")


class ErroIA(Exception):
    """Falha do provedor com causa que o usuário precisa ver (chave recusada, sem crédito)."""


def _checar(resp, provedor: str) -> None:
    if resp.status_code in (401, 403):
        raise ErroIA(f"A chave da {provedor} foi recusada (HTTP {resp.status_code}). "
                     f"Atualize a variável de ambiente no Railway.")
    if resp.status_code == 429:
        raise ErroIA(f"A {provedor} limitou as consultas (HTTP 429). Tente em instantes.")


def disponivel() -> bool:
    return bool(_chave("ANTHROPIC_API_KEY") or _chave("OPENAI_API_KEY"))


def preparar_imagem(dados: bytes) -> bytes:
    """JPEG de no máximo 1568 px no lado maior, com a rotação já aplicada.

    Converte HEIC, TIFF e WEBP para algo que todo modelo aceita e tira o EXIF
    (que já foi lido à parte, e não precisa ir para o provedor de IA)."""
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(dados))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    saida = io.BytesIO()
    img.save(saida, "JPEG", quality=85, optimize=True)
    return saida.getvalue()


def _json_de(texto: str | None) -> dict | None:
    if not texto:
        return None
    limpo = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip(), flags=re.I)
    ini, fim = limpo.find("{"), limpo.rfind("}")
    if ini < 0 or fim <= ini:
        return None
    try:
        obj = json.loads(limpo[ini:fim + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def normalizar(bruto: dict) -> dict:
    """Garante o formato, mesmo que o modelo omita ou invente campos."""
    def lista(v) -> list:
        return v if isinstance(v, list) else []

    local = bruto.get("local_provavel") if isinstance(bruto.get("local_provavel"), dict) else {}
    conf = str(local.get("confianca") or "nenhuma").lower().replace("é", "e")
    pistas = []
    for p in lista(bruto.get("pistas")):
        if isinstance(p, dict) and (p.get("observado") or p.get("indica")):
            c = str(p.get("confianca") or "baixa").lower().replace("é", "e")
            pistas.append({"tipo": str(p.get("tipo") or "outro"), "observado": str(p.get("observado") or ""),
                           "indica": str(p.get("indica") or ""), "confianca": c if c in CONFIANCAS else "baixa"})
    return {
        "resumo": str(bruto.get("resumo") or "").strip(),
        "ambiente": str(bruto.get("ambiente") or "").strip(),
        "pistas": pistas,
        "textos_visiveis": [str(t) for t in lista(bruto.get("textos_visiveis")) if str(t).strip()],
        "local_provavel": {
            **{k: (str(local.get(k)).strip() if local.get(k) else None) for k in ("pais", "regiao", "cidade", "ponto")},
            "confianca": conf if conf in CONFIANCAS else "nenhuma",
            "motivo": str(local.get("motivo") or "").strip(),
        },
        "como_confirmar": [str(x) for x in lista(bruto.get("como_confirmar")) if str(x).strip()],
        "limites": [str(x) for x in lista(bruto.get("limites")) if str(x).strip()],
    }


def placas_no_texto(textos: list[str]) -> list[str]:
    """Placas de veículo (antiga ou Mercosul) entre os textos transcritos."""
    achadas: list[str] = []
    for t in textos:
        for m in _PLACA.findall(t.upper()):
            placa = m.replace("-", "").replace(" ", "")
            if placa not in achadas:
                achadas.append(placa)
    return achadas


def link_do_mapa(local: dict) -> str | None:
    """Busca no Google Maps pelo que o modelo estimou. Sem cidade ou ponto, não há o que buscar."""
    if not (local.get("cidade") or local.get("ponto")) or local.get("confianca") == "nenhuma":
        return None
    consulta = ", ".join(x for x in (local.get("ponto"), local.get("cidade"), local.get("regiao"),
                                     local.get("pais")) if x)
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(consulta)}"


def _anthropic(jpeg: bytes) -> str | None:
    chave = _chave("ANTHROPIC_API_KEY")
    if not chave:
        return None
    imagem = {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                          "data": base64.b64encode(jpeg).decode("ascii")}}
    for modelo in _modelos_anthropic():
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": modelo, "max_tokens": 3000, "system": SISTEMA,
                  "messages": [{"role": "user", "content": [imagem, {"type": "text", "text": INSTRUCAO}]}]},
            timeout=120,
        )
        if resp.status_code >= 400:
            try:
                erro = str(resp.json())
            except Exception:  # noqa: BLE001
                erro = ""
            _checar(resp, "Anthropic")
            # Modelo inexistente ou recusado: tenta o próximo. Qualquer outro erro encerra.
            if resp.status_code == 404 or (resp.status_code == 400 and "model" in erro):
                continue
            return None
        blocos = resp.json().get("content") or []
        return "".join(b.get("text", "") for b in blocos if b.get("type") == "text").strip() or None
    return None


def _openai(jpeg: bytes) -> str | None:
    chave = _chave("OPENAI_API_KEY")
    if not chave:
        return None
    url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
        json={"model": _chave("HOLMES_FOTO_MODELO_OPENAI") or "gpt-4o", "temperature": 0,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": SISTEMA},
                           {"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}},
                                                        {"type": "text", "text": INSTRUCAO}]}]},
        timeout=120,
    )
    if resp.status_code >= 400:
        _checar(resp, "OpenAI")
        return None
    try:
        return resp.json()["choices"][0]["message"]["content"].strip() or None
    except (KeyError, IndexError, TypeError):
        return None


def analisar_cenario(dados: bytes) -> tuple[dict | None, str]:
    """(análise normalizada, mensagem de erro). Nunca levanta exceção."""
    if len(dados) > LIMITE_BYTES:
        return None, f"A foto passa de {LIMITE_BYTES // (1024 * 1024)} MB."
    if not disponivel():
        return None, "Sem chave de IA: configure ANTHROPIC_API_KEY ou OPENAI_API_KEY."
    try:
        jpeg = preparar_imagem(dados)
    except Exception:  # noqa: BLE001
        return None, "Arquivo não é uma imagem legível."
    saida: Any = None
    problemas: list[str] = []
    for provedor in (_anthropic, _openai):
        try:
            saida = provedor(jpeg)
        except ErroIA as exc:
            problemas.append(str(exc))
            continue
        except requests.RequestException as exc:
            problemas.append(f"O provedor de IA não respondeu: {type(exc).__name__}.")
            continue
        if saida:
            break
    if not saida and problemas:
        return None, " ".join(problemas)
    bruto = _json_de(saida)
    if not bruto:
        return None, "A IA não devolveu uma análise legível. Tente de novo."
    return normalizar(bruto), ""
