"""
Número de processo judicial (padrão CNJ) — decodificação e consulta.

O número unificado do CNJ não é opaco: ele diz o segmento da Justiça, o
tribunal, a unidade de origem e o ano. Dá para saber em que vara corre o
processo sem consultar nada. Depois disso, a API pública DataJud (CNJ)
entrega a movimentação completa, de graça.

Formato: NNNNNNN-DD.AAAA.J.TR.OOOO  (20 dígitos)
  NNNNNNN  sequencial por unidade/ano
  DD       dígito verificador (ISO 7064, módulo 97 base 10)
  AAAA     ano de ajuizamento
  J        segmento do Judiciário
  TR       tribunal dentro do segmento
  OOOO     unidade de origem (foro/vara)
"""

from __future__ import annotations

import re
from typing import Iterable

from . import net
from .findings import Confidence, Finding, FindingKind

# Chave pública de acesso ao DataJud, divulgada pelo próprio CNJ na
# documentação oficial da API. Não é segredo e não identifica o usuário.
DATAJUD_PUBLIC_KEY = (
    "APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
)
DATAJUD_BASE = "https://api-publica.datajud.cnj.jus.br"

SEGMENTOS = {
    "1": "Supremo Tribunal Federal",
    "2": "Conselho Nacional de Justiça",
    "3": "Superior Tribunal de Justiça",
    "4": "Justiça Federal",
    "5": "Justiça do Trabalho",
    "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União",
    "8": "Justiça Estadual",
    "9": "Justiça Militar Estadual",
}

# Código do tribunal (TR) dentro da Justiça Estadual e Eleitoral.
UF_POR_TR = {
    "01": "AC", "02": "AL", "03": "AP", "04": "AM", "05": "BA", "06": "CE",
    "07": "DF", "08": "ES", "09": "GO", "10": "MA", "11": "MT", "12": "MS",
    "13": "MG", "14": "PA", "15": "PB", "16": "PR", "17": "PE", "18": "PI",
    "19": "RJ", "20": "RN", "21": "RS", "22": "RO", "23": "RR", "24": "SC",
    "25": "SE", "26": "SP", "27": "TO",
}

_CNJ_RE = re.compile(
    r"^(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})$"
)


def only_digits(text: str) -> str:
    return "".join(c for c in (text or "") if c.isdigit())


def parse(raw: str) -> dict | None:
    """Decodifica o número. Devolve None se não for um número CNJ plausível."""
    text = (raw or "").strip()
    digits = only_digits(text)
    if len(digits) != 20:
        return None

    m = _CNJ_RE.match(digits)
    if not m:
        return None
    seq, dv, ano, j, tr, origem = m.groups()

    segmento = SEGMENTOS.get(j, "segmento desconhecido")
    tribunal, sigla = _tribunal(j, tr)

    try:
        ano_int = int(ano)
    except ValueError:
        return None
    if not (1970 <= ano_int <= 2100):
        return None

    return {
        "digits": digits,
        "formatado": f"{seq}-{dv}.{ano}.{j}.{tr}.{origem}",
        "sequencial": seq,
        "dv": dv,
        "ano": ano,
        "segmento_codigo": j,
        "segmento": segmento,
        "tribunal_codigo": tr,
        "tribunal": tribunal,
        "sigla": sigla,
        "origem": origem,
        "dv_valido": validate_dv(digits),
    }


def _tribunal(j: str, tr: str) -> tuple[str, str | None]:
    """(nome legível, sigla usada pelo DataJud)."""
    if j == "1":
        return "Supremo Tribunal Federal", "STF"
    if j == "3":
        return "Superior Tribunal de Justiça", "STJ"
    if j == "4":
        n = int(tr) if tr.isdigit() else 0
        if 1 <= n <= 6:
            return f"Tribunal Regional Federal da {n}ª Região", f"TRF{n}"
        return "Justiça Federal", None
    if j == "5":
        n = int(tr) if tr.isdigit() else 0
        if tr == "00":
            return "Tribunal Superior do Trabalho", "TST"
        if 1 <= n <= 24:
            return f"Tribunal Regional do Trabalho da {n}ª Região", f"TRT{n}"
        return "Justiça do Trabalho", None
    if j == "6":
        uf = UF_POR_TR.get(tr)
        if tr == "00":
            return "Tribunal Superior Eleitoral", "TSE"
        return (f"Tribunal Regional Eleitoral do {uf}" if uf else "Justiça Eleitoral",
                f"TRE{uf}" if uf else None)
    if j == "8":
        uf = UF_POR_TR.get(tr)
        return (f"Tribunal de Justiça do {uf}" if uf else "Justiça Estadual",
                f"TJ{uf}" if uf else None)
    if j == "9":
        uf = UF_POR_TR.get(tr)
        return (f"Tribunal de Justiça Militar do {uf}" if uf else "Justiça Militar Estadual",
                None)
    if j == "7":
        return "Superior Tribunal Militar", "STM"
    return "Tribunal não identificado", None


def validate_dv(raw: str) -> bool:
    """
    Dígito verificador pelo módulo 97 base 10 (ISO 7064), como manda a
    Resolução CNJ 65/2008. Pega número digitado errado antes de sair
    consultando tribunal à toa.
    """
    d = only_digits(raw)
    if len(d) != 20:
        return False
    seq, dv, resto = d[:7], d[7:9], d[9:]
    # A conta é feita com o DV movido para o fim e zerado.
    base = int(seq + resto + "00")
    return (98 - (base % 97)) == int(dv)


def format_cnj(raw: str) -> str:
    d = only_digits(raw)
    if len(d) != 20:
        return raw
    return f"{d[:7]}-{d[7:9]}.{d[9:13]}.{d[13]}.{d[14:16]}.{d[16:]}"


def datajud_alias(sigla: str | None) -> str | None:
    """Nome do índice no DataJud (ex.: TJSP → api_publica_tjsp)."""
    if not sigla:
        return None
    return f"api_publica_{sigla.lower()}"


def consultar_datajud(numero: str, sigla: str | None) -> list[dict]:
    """Consulta a API pública do CNJ. Sem chave própria: a chave é pública."""
    alias = datajud_alias(sigla)
    if not alias:
        return []
    digits = only_digits(numero)
    try:
        data = net.post_json(
            f"{DATAJUD_BASE}/{alias}/_search",
            payload={"query": {"match": {"numeroProcesso": digits}}, "size": 5},
            headers={"Authorization": DATAJUD_PUBLIC_KEY, "Content-Type": "application/json"},
            timeout=25,
            ttl=12 * 3600,
        ) or {}
    except Exception:
        return []
    return [h.get("_source") or {} for h in ((data.get("hits") or {}).get("hits") or [])]


def _data_br(valor: str) -> str:
    """DataJud devolve data como AAAAMMDDHHMMSS ou ISO."""
    v = (valor or "").strip()
    if len(v) >= 8 and v[:8].isdigit():
        return f"{v[6:8]}/{v[4:6]}/{v[:4]}"
    if len(v) >= 10 and v[4] == "-":
        return f"{v[8:10]}/{v[5:7]}/{v[:4]}"
    return v


def processo_findings(entity) -> Iterable[Finding]:
    """Conector: número de processo → decodificação + movimentação oficial."""
    info = entity.variants.get("cnj") or parse(entity.value)
    if not info:
        return []

    out: list[Finding] = []
    numero_fmt = info["formatado"]

    if not info["dv_valido"]:
        out.append(Finding(
            kind=FindingKind.NOTE, value="Dígito verificador NÃO confere",
            source="cnj", source_label="Padrão CNJ", confidence=Confidence.CONFIRMED,
            detail="O número foi digitado errado ou é inventado. Confira antes de seguir.",
        ))

    # Decodificação — não depende de rede nenhuma.
    out.append(Finding(
        kind=FindingKind.LEGAL, value=f"{info['segmento']} — {info['tribunal']}",
        source="cnj", source_label="Padrão CNJ (decodificação)",
        confidence=Confidence.CONFIRMED,
        detail=f"Processo {numero_fmt}, ajuizado em {info['ano']}, "
               f"unidade de origem {info['origem']}.",
        raw=info,
    ))

    # Movimentação oficial via API pública do CNJ.
    registros = consultar_datajud(info["digits"], info["sigla"])
    if not registros:
        out.append(Finding(
            kind=FindingKind.NOTE, value="Sem retorno no DataJud",
            source="datajud", source_label="DataJud (CNJ)", confidence=Confidence.LIKELY,
            detail="O processo pode estar em segredo de justiça, ser de tribunal não "
                   "coberto pela base, ou o número estar incorreto.",
        ))
        return out

    for reg in registros[:2]:
        classe = (reg.get("classe") or {}).get("nome") or "classe n/d"
        orgao = (reg.get("orgaoJulgador") or {}).get("nome") or "órgão n/d"
        grau = reg.get("grau") or ""
        sigilo = reg.get("nivelSigilo")
        url = f"https://www.cnj.jus.br/sistemas/datajud/"

        out.append(Finding(
            kind=FindingKind.LEGAL, value=f"{classe} — {orgao}",
            source="datajud", source_label="DataJud (CNJ)", url=url,
            confidence=Confidence.CONFIRMED,
            detail=f"Tribunal {reg.get('tribunal')}, grau {grau}, "
                   f"ajuizado em {_data_br(reg.get('dataAjuizamento') or '')}"
                   + (f", nível de sigilo {sigilo}" if sigilo else ""),
            raw=reg,
        ))

        for assunto in (reg.get("assuntos") or [])[:6]:
            nome = assunto.get("nome")
            if nome:
                out.append(Finding(
                    kind=FindingKind.LEGAL, value=f"Assunto: {nome}",
                    source="datajud", source_label="DataJud (CNJ)", url=url,
                    confidence=Confidence.CONFIRMED,
                    detail="Assunto classificado pela tabela unificada do CNJ.",
                ))

        movimentos = reg.get("movimentos") or []
        if movimentos:
            ordenados = sorted(
                movimentos, key=lambda m: m.get("dataHora") or "", reverse=True
            )
            ultimo = ordenados[0]
            out.append(Finding(
                kind=FindingKind.LEGAL,
                value=f"Última movimentação: {ultimo.get('nome')}",
                source="datajud", source_label="DataJud (CNJ)", url=url,
                confidence=Confidence.CONFIRMED,
                detail=f"Em {_data_br(ultimo.get('dataHora') or '')}. "
                       f"O processo tem {len(movimentos)} movimentações registradas.",
                raw={"movimentos": ordenados[:40]},
            ))
            marcos = [
                m.get("nome") for m in ordenados[:12]
                if m.get("nome") and any(
                    p in m["nome"].lower()
                    for p in ("senten", "julgad", "trânsit", "transit", "arquiv",
                              "acórdão", "acordao", "recurso", "extin", "procedente")
                )
            ]
            for marco in dict.fromkeys(marcos):
                out.append(Finding(
                    kind=FindingKind.LEGAL, value=f"Marco processual: {marco}",
                    source="datajud", source_label="DataJud (CNJ)", url=url,
                    confidence=Confidence.CONFIRMED,
                    detail="Movimentação relevante para o desfecho do processo.",
                ))
    return out
