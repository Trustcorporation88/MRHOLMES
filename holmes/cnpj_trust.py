"""
CNPJ Trust (cnpj.trustcorp.com.br): consulta completa de CNPJ.

O site é uma camada sobre dois provedores pagos, CNPJá e SintegraWS, com
cache de 24h e acesso por chave. Aqui o Holmes chama a API dele servidor a
servidor e traz o que a consulta gratuita da Receita não traz: sócios com
cargo e data de entrada, Simples Nacional e MEI confirmados, inscrições
estaduais, capital social e o comprovante oficial em PDF.

Configuração (Railway do Mr.Holmes):
  CNPJ_TRUST_KEY   a chave de acesso do site (CLIENT_KEY dele)
  CNPJ_TRUST_URL   opcional; padrão https://cnpj.trustcorp.com.br
"""

from __future__ import annotations

import os
from typing import Iterable

import requests

from . import net
from .entity import Entity, format_cnpj, only_digits
from .findings import Confidence, Finding, FindingKind

PADRAO_URL = "https://cnpj.trustcorp.com.br"
PORTE_CNPJA = {"ME": "ME", "EPP": "EPP", "DEMAIS": "DEMAIS"}


def base_url() -> str:
    return (os.environ.get("CNPJ_TRUST_URL") or PADRAO_URL).strip().rstrip("/")


def configurado() -> bool:
    return net.has_key("cnpj_trust")


def _get(caminho: str, params: dict, timeout: int = 30) -> dict | None:
    chave = net.get_key("cnpj_trust")
    if not chave:
        return None
    try:
        return net.get_json(f"{base_url()}{caminho}", params=params,
                            headers={"x-access-key": chave, "Accept": "application/json"},
                            timeout=timeout, ttl=24 * 3600)
    except (requests.RequestException, ValueError):
        return None


def consultar(cnpj: str) -> dict | None:
    """Dados normalizados do CNPJ. CNPJá primeiro (sócios, Simples, inscrições);
    se falhar, a consulta da Receita pelo SintegraWS."""
    digitos = only_digits(cnpj)
    if len(digitos) != 14:
        return None
    dados = _get("/api/cnpja/office", {"cnpj": digitos, "simples": "true", "registrations": "ALL"})
    if dados and (dados.get("company") or dados.get("taxId")):
        return normalizar_cnpja(dados)
    dados = _get("/api/sws/rf", {"cnpj": digitos})
    if dados and (dados.get("nome") or dados.get("razao_social")):
        return normalizar_receita(dados)
    return None


def _endereco_cnpja(a: dict) -> str:
    partes = [a.get("street"), a.get("number"), a.get("details"), a.get("district"),
              f"{a.get('city') or ''}/{a.get('state') or ''}".strip("/"), a.get("zip")]
    return ", ".join(str(p) for p in partes if p)


def normalizar_cnpja(d: dict) -> dict:
    empresa = d.get("company") or {}
    porte = ((empresa.get("size") or {}).get("acronym") or "").upper()
    simei = bool((empresa.get("simei") or {}).get("optant"))
    socios = []
    for m in empresa.get("members") or []:
        pessoa = m.get("person") or {}
        if not pessoa.get("name"):
            continue
        socios.append({
            "nome": pessoa["name"].strip(),
            "qualificacao": (m.get("role") or {}).get("text") or "",
            "desde": m.get("since") or "",
            "faixa_etaria": pessoa.get("age") or "",
            "documento": pessoa.get("taxId") or "",
            "tipo": pessoa.get("type") or "",
        })
    inscricoes = [{
        "uf": r.get("state") or "",
        "numero": r.get("number") or "",
        "ativa": bool(r.get("enabled")),
        "situacao": (r.get("status") or {}).get("text") or "",
        "tipo": (r.get("type") or {}).get("text") or "",
    } for r in d.get("registrations") or []]
    telefones = [f"({t.get('area')}) {t.get('number')}" for t in d.get("phones") or [] if t.get("number")]
    return {
        "provedor": "CNPJá",
        "cnpj": format_cnpj(d.get("taxId") or ""),
        "razao_social": empresa.get("name") or "",
        "fantasia": d.get("alias") or "",
        "situacao": ((d.get("status") or {}).get("text") or "").upper(),
        "abertura": d.get("founded") or "",
        "porte": "MEI" if simei else PORTE_CNPJA.get(porte, ""),
        "mei": simei,
        "simples": bool((empresa.get("simples") or {}).get("optant")),
        "capital_social": empresa.get("equity"),
        "natureza": (empresa.get("nature") or {}).get("text") or "",
        "atividade": (d.get("mainActivity") or {}).get("text") or "",
        "endereco": _endereco_cnpja(d.get("address") or {}),
        "telefones": telefones,
        "emails": [e.get("address") for e in d.get("emails") or [] if e.get("address")],
        "socios": socios,
        "inscricoes": inscricoes,
    }


def normalizar_receita(d: dict) -> dict:
    """Formato ReceitaWS, que é o que o SintegraWS devolve no plugin RF."""
    from .limpanome import porte_da_receita

    socios = [{
        "nome": (s.get("nome") or s.get("nome_socio") or "").strip(),
        "qualificacao": s.get("qual") or s.get("qualificacao_socio") or "",
        "desde": s.get("data_entrada_sociedade") or "",
        "faixa_etaria": s.get("faixa_etaria") or "",
        "documento": s.get("cnpj_cpf_do_socio") or "",
        "tipo": "",
    } for s in d.get("qsa") or [] if (s.get("nome") or s.get("nome_socio"))]
    partes = [d.get("logradouro"), d.get("numero"), d.get("complemento"), d.get("bairro"),
              f"{d.get('municipio') or ''}/{d.get('uf') or ''}".strip("/"), d.get("cep")]
    return {
        "provedor": "SintegraWS",
        "cnpj": format_cnpj(d.get("cnpj") or ""),
        "razao_social": d.get("nome") or d.get("razao_social") or "",
        "fantasia": d.get("fantasia") or d.get("nome_fantasia") or "",
        "situacao": str(d.get("situacao") or d.get("descricao_situacao_cadastral") or "").upper(),
        "abertura": d.get("abertura") or "",
        "porte": porte_da_receita(d),
        "mei": porte_da_receita(d) == "MEI",
        "simples": None,
        "capital_social": d.get("capital_social"),
        "natureza": d.get("natureza_juridica") or "",
        "atividade": ((d.get("atividade_principal") or [{}])[0] or {}).get("text") or "",
        "endereco": ", ".join(str(p) for p in partes if p),
        "telefones": [t.strip() for t in str(d.get("telefone") or "").split("/") if t.strip()],
        "emails": [d["email"]] if d.get("email") else [],
        "socios": socios,
        "inscricoes": [],
    }


def findings(entity: Entity) -> Iterable[Finding]:
    """Conector da investigação: o que o CNPJ Trust sabe do CNPJ."""
    d = consultar(entity.value)
    if not d:
        return []
    fonte, rotulo = "cnpj_trust", f"CNPJ Trust ({d['provedor']})"
    url = base_url()
    out: list[Finding] = []

    def add(kind, value, detail="", conf=Confidence.CONFIRMED, raw=None):
        if value:
            out.append(Finding(kind=kind, value=str(value), source=fonte, source_label=rotulo,
                               url=url, confidence=conf, detail=detail, raw=raw or {}))

    resumo = [f"Situação {d['situacao']}" if d["situacao"] else "",
              f"porte {d['porte']}" if d["porte"] else "",
              "optante do Simples" if d["simples"] else "",
              "MEI" if d["mei"] else "",
              f"aberta em {d['abertura']}" if d["abertura"] else "",
              f"capital R$ {d['capital_social']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
              if isinstance(d.get("capital_social"), (int, float)) else ""]
    add(FindingKind.COMPANY, d["razao_social"], ". ".join(p for p in resumo if p),
        raw={"porte": d["porte"], "mei": d["mei"], "simples": d["simples"], "natureza": d["natureza"]})
    if d["fantasia"] and d["fantasia"] != d["razao_social"]:
        add(FindingKind.COMPANY, d["fantasia"], "Nome fantasia")
    add(FindingKind.ADDRESS, d["endereco"], "Endereço cadastral")
    for t in d["telefones"]:
        add(FindingKind.PHONE, t, "Telefone cadastral da empresa")
    for e in d["emails"]:
        add(FindingKind.EMAIL, e.lower(), "E-mail cadastral da empresa")
    for s in d["socios"]:
        detalhe = ", ".join(p for p in (s["qualificacao"], f"desde {s['desde']}" if s["desde"] else "",
                                        f"faixa {s['faixa_etaria']}" if s["faixa_etaria"] else "") if p)
        add(FindingKind.NAME, s["nome"], f"Sócio de {d['razao_social']}. {detalhe}".strip(),
            raw={"socio": True, "qualificacao": s["qualificacao"]})
    for i in d["inscricoes"]:
        add(FindingKind.DOCUMENT, f"IE {i['numero']} ({i['uf']})",
            f"Inscrição estadual {'ativa' if i['ativa'] else 'inativa'}"
            + (f": {i['situacao']}" if i["situacao"] else ""),
            raw={"tipo": "ie", "uf": i["uf"]})
    if d["atividade"]:
        add(FindingKind.NOTE, d["atividade"], "Atividade principal")
    return out


def comprovante_pdf(cnpj: str) -> bytes | None:
    """Comprovante de inscrição e situação cadastral da Receita, em PDF (via CNPJá)."""
    chave = net.get_key("cnpj_trust")
    digitos = only_digits(cnpj)
    if not chave or len(digitos) != 14:
        return None
    try:
        r = requests.get(f"{base_url()}/api/comprovante-rf", params={"cnpj": digitos},
                         headers={"x-access-key": chave}, timeout=40)
    except requests.RequestException:
        return None
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        return None
    return r.content


def _moeda(v) -> str:
    if not isinstance(v, (int, float)):
        return ""
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _sim_nao(v) -> str:
    return "não informado" if v is None else ("sim" if v else "não")


def secoes_relatorio(d: dict) -> list[tuple[str, list[str]]]:
    """[(título, [linhas])] do relatório completo. Base do PDF e do Markdown."""
    cadastro = [linha for linha in (
        f"Razão social: {d.get('razao_social')}" if d.get("razao_social") else "",
        f"Nome fantasia: {d.get('fantasia')}" if d.get("fantasia") else "",
        f"CNPJ: {d.get('cnpj')}" if d.get("cnpj") else "",
        f"Situação cadastral: {d.get('situacao')}" if d.get("situacao") else "",
        f"Abertura: {d.get('abertura')}" if d.get("abertura") else "",
        f"Natureza jurídica: {d.get('natureza')}" if d.get("natureza") else "",
        f"Atividade principal: {d.get('atividade')}" if d.get("atividade") else "",
    ) if linha]
    tributario = [
        f"Porte: {d.get('porte') or 'não informado'}",
        f"Optante do Simples Nacional: {_sim_nao(d.get('simples'))}",
        f"MEI: {_sim_nao(d.get('mei'))}",
    ]
    if _moeda(d.get("capital_social")):
        tributario.append(f"Capital social: {_moeda(d.get('capital_social'))}")
    contato = ([f"Endereço: {d['endereco']}"] if d.get("endereco") else []) \
        + [f"Telefone: {t}" for t in d.get("telefones") or []] \
        + [f"E-mail: {e}" for e in d.get("emails") or []]
    socios = []
    for s in d.get("socios") or []:
        extra = ", ".join(p for p in (s.get("qualificacao"),
                                      f"desde {s['desde']}" if s.get("desde") else "",
                                      f"faixa etária {s['faixa_etaria']}" if s.get("faixa_etaria") else "",
                                      f"documento {s['documento']}" if s.get("documento") else "") if p)
        socios.append(f"{s['nome']}" + (f" ({extra})" if extra else ""))
    inscricoes = [f"IE {i['numero']} ({i['uf']}): {'ativa' if i.get('ativa') else 'inativa'}"
                  + (f", {i['situacao']}" if i.get("situacao") else "")
                  + (f", {i['tipo']}" if i.get("tipo") else "")
                  for i in d.get("inscricoes") or []]
    return [
        ("Cadastro", cadastro or ["Sem dados cadastrais."]),
        ("Porte e tributação", tributario),
        ("Contato", contato or ["Sem contato cadastral."]),
        (f"Quadro de sócios ({len(socios)})", socios or ["Nenhum sócio informado pela fonte."]),
        (f"Inscrições estaduais ({len(inscricoes)})", inscricoes or ["Nenhuma inscrição estadual encontrada."]),
    ]


def relatorio_markdown(d: dict, hoje=None) -> str:
    from datetime import date

    hoje = hoje or date.today()
    partes = [f"# CNPJ completo: {d.get('razao_social') or d.get('cnpj')}",
              f"_Fonte: CNPJ Trust ({d.get('provedor')}), consultado em {hoje.strftime('%d/%m/%Y')}._", ""]
    for titulo, linhas in secoes_relatorio(d):
        partes.append(f"## {titulo}")
        partes += [f"- {l}" for l in linhas]
        partes.append("")
    return "\n".join(partes)


def relatorio_pdf(d: dict, hoje=None) -> bytes:
    """PDF do relatório completo. Levanta ImportError se reportlab faltar."""
    import io
    from datetime import date

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    hoje = hoje or date.today()

    def esc(t) -> str:
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm, title=f"CNPJ completo: {d.get('cnpj')}")
    ss = getSampleStyleSheet()
    eyebrow = ParagraphStyle("eb", parent=ss["Normal"], fontSize=8, textColor=colors.HexColor("#5b5bf0"))
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=18, alignment=0, spaceAfter=2,
                        textColor=colors.HexColor("#1d2239"))
    meta = ParagraphStyle("meta", parent=ss["Normal"], fontSize=9, textColor=colors.HexColor("#5d6480"))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4,
                        textColor=colors.HexColor("#1d2239"))
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=10, leading=14)
    el: list = [
        Paragraph("CNPJ COMPLETO · MR.HOLMES", eyebrow),
        Paragraph(esc(d.get("razao_social") or d.get("cnpj")), h1),
        Paragraph(f"{esc(d.get('cnpj'))} · fonte CNPJ Trust ({esc(d.get('provedor'))}) · "
                  f"consultado em {hoje.strftime('%d/%m/%Y')}", meta),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#5b5bf0")),
    ]
    for titulo, linhas in secoes_relatorio(d):
        el.append(Paragraph(esc(titulo), h2))
        el.append(ListFlowable([ListItem(Paragraph(esc(l), body), leftIndent=10) for l in linhas],
                               bulletType="bullet", start="•", leftIndent=12))
    doc.build(el)
    return buf.getvalue()


def relatorio(cnpj: str) -> tuple[bytes, str, str] | None:
    """(conteúdo, extensão, mime) do relatório completo: PDF se houver reportlab,
    senão Markdown. None se a consulta falhar."""
    d = consultar(cnpj)
    if not d:
        return None
    try:
        return relatorio_pdf(d), "pdf", "application/pdf"
    except ImportError:
        return relatorio_markdown(d).encode("utf-8"), "md", "text/markdown"
