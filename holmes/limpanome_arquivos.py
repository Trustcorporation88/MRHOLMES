"""
Leitura do relatório do birô enviado como arquivo (PDF ou print).

Serasa, SPC, Boa Vista e CENPROT entregam PDF ou tela para print, não texto.
Aqui o arquivo vai direto para um modelo que lê PDF e imagem de forma nativa
(Anthropic primeiro, OpenAI como alternativa) e volta a lista de registros.
O usuário revisa tudo na tabela depois: a IA só poupa a digitação.
"""

from __future__ import annotations

import base64
import json
import os
import re

import requests

from . import limpanome as ln

LIMITE_BYTES = 20 * 1024 * 1024      # 20 MB por arquivo
TIPOS = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}

_INSTRUCAO = (
    "Leia este relatório de negativação (Serasa, SPC, Boa Vista, Quod ou consulta de protesto em "
    "cartório) e devolva os registros de dívida no formato pedido. Ignore score, ofertas de acordo, "
    "propaganda e consultas ao CPF: só dívidas negativadas ou protestadas."
)


def tipo_do_arquivo(nome: str) -> str | None:
    ext = (nome or "").rsplit(".", 1)[-1].lower()
    return TIPOS.get(ext)


def _chave(nome: str) -> str:
    return (os.environ.get(nome) or "").strip().strip('"').strip("'")


def disponivel() -> bool:
    return bool(_chave("ANTHROPIC_API_KEY") or _chave("OPENAI_API_KEY"))


# O primeiro modelo que a conta aceitar. O Watson, na mesma conta, confere
# claude-sonnet-5 na inicialização; o 4.5 fica como reserva.
_MODELOS_ANTHROPIC = ("claude-sonnet-5", "claude-sonnet-4-5")


def _modelos_anthropic() -> list[str]:
    preferido = _chave("HOLMES_VISAO_MODELO")
    return list(dict.fromkeys([m for m in (preferido, *_MODELOS_ANTHROPIC) if m]))


def _anthropic(mime: str, dados: bytes) -> str | None:
    chave = _chave("ANTHROPIC_API_KEY")
    if not chave:
        return None
    for modelo in _modelos_anthropic():
        saida, tentar_outro = _anthropic_modelo(chave, modelo, mime, dados)
        if saida or not tentar_outro:
            return saida
    return None


def _anthropic_modelo(chave: str, modelo: str, mime: str, dados: bytes) -> tuple[str | None, bool]:
    """(texto, vale tentar outro modelo). Modelo inexistente (404) ou recusado
    (400 citando o modelo) passa para o próximo; outros erros param."""
    bloco_tipo = "document" if mime == "application/pdf" else "image"
    conteudo = [
        {"type": bloco_tipo, "source": {"type": "base64", "media_type": mime,
                                        "data": base64.b64encode(dados).decode("ascii")}},
        {"type": "text", "text": _INSTRUCAO},
    ]
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": modelo, "max_tokens": 4096,
              "system": ln._SISTEMA_EXTRACAO, "messages": [{"role": "user", "content": conteudo}]},
        timeout=120,
    )
    if resp.status_code >= 400:
        try:
            erro = str(resp.json())
        except Exception:
            erro = ""
        return None, resp.status_code == 404 or (resp.status_code == 400 and "model" in erro)
    blocos = resp.json().get("content") or []
    return "".join(b.get("text", "") for b in blocos if b.get("type") == "text").strip() or None, False


def _openai(nome: str, mime: str, dados: bytes) -> str | None:
    chave = _chave("OPENAI_API_KEY")
    if not chave:
        return None
    url_dados = f"data:{mime};base64," + base64.b64encode(dados).decode("ascii")
    if mime == "application/pdf":
        anexo = {"type": "file", "file": {"filename": nome or "relatorio.pdf", "file_data": url_dados}}
    else:
        anexo = {"type": "image_url", "image_url": {"url": url_dados}}
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"},
        json={"model": os.environ.get("HOLMES_VISAO_MODELO_OPENAI", "gpt-4o-mini"), "temperature": 0,
              "messages": [{"role": "system", "content": ln._SISTEMA_EXTRACAO},
                           {"role": "user", "content": [anexo, {"type": "text", "text": _INSTRUCAO}]}]},
        timeout=120,
    )
    if resp.status_code >= 400:
        return None
    try:
        return resp.json()["choices"][0]["message"]["content"].strip() or None
    except (KeyError, IndexError, TypeError):
        return None


def registros_do_json(saida: str | None, biro_padrao: str | None = None) -> list[ln.Registro]:
    """Converte a resposta do modelo em registros. Tolera texto em volta do JSON."""
    if not saida:
        return []
    m = re.search(r"\[.*\]", saida, re.S)
    if not m:
        return []
    try:
        itens = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    regs: list[ln.Registro] = []
    for it in itens if isinstance(itens, list) else []:
        if not isinstance(it, dict) or not str(it.get("credor") or "").strip():
            continue
        try:
            valor = float(str(it.get("valor") or 0).replace("R$", "").strip() or 0)
        except ValueError:
            valor = 0.0
        biro = it.get("biro") if it.get("biro") in ln.BIROS else (biro_padrao or "Serasa")
        regs.append(ln.Registro(
            credor=str(it["credor"]).strip()[:80], valor=valor,
            vencimento=ln._data_iso(it.get("vencimento")), inclusao=ln._data_iso(it.get("inclusao")),
            biro=biro, cnpj_credor=str(it.get("cnpj_credor") or "")[:20],
        ))
    return regs


def extrair_de_arquivo(nome: str, dados: bytes, biro_padrao: str | None = None) -> tuple[list[ln.Registro], str]:
    """(registros, mensagem). Nunca levanta exceção: o erro vira mensagem para a tela."""
    mime = tipo_do_arquivo(nome)
    if not mime:
        return [], f"{nome}: formato não aceito. Envie PDF, PNG, JPG ou WEBP."
    if not dados:
        return [], f"{nome}: arquivo vazio."
    if len(dados) > LIMITE_BYTES:
        return [], f"{nome}: arquivo maior que 20 MB."
    if not disponivel():
        return [], "Configure ANTHROPIC_API_KEY ou OPENAI_API_KEY para ler arquivos."
    saida = None
    try:
        saida = _anthropic(mime, dados)
    except requests.RequestException:
        saida = None
    if not saida:
        try:
            saida = _openai(nome, mime, dados)
        except requests.RequestException:
            saida = None
    if not saida:
        return [], f"{nome}: a IA não respondeu. Tente de novo ou cole o texto."
    regs = registros_do_json(saida, biro_padrao)
    if not regs:
        return [], f"{nome}: nenhuma dívida encontrada no arquivo."
    return regs, f"{nome}: {len(regs)} registro(s) lido(s)."
