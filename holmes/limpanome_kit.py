"""
Kit do Juizado e do Procon: um documento com tudo o que o atendente pede.

O conteúdo é montado em seções (testável, sem dependência) e depois vira PDF
com reportlab ou Markdown. Serve para imprimir, anexar no Procon ou levar ao
Juizado Especial Cível.
"""

from __future__ import annotations

import io
from datetime import date

from . import limpanome as ln


def _linha_do_tempo(caso: ln.Caso, r: ln.Registro, hoje: date) -> list[tuple[date, str]]:
    a = ln.analisar(r, hoje, caso)
    eventos: list[tuple[date, str]] = []
    if r.venc():
        eventos.append((r.venc(), f"Vencimento informado da dívida ({r.valor_fmt()})"))
    if ln._data(r.inclusao):
        eventos.append((ln._data(r.inclusao), f"Inclusão no {r.biro}"))
    if ln._data(r.data_pagamento):
        eventos.append((ln._data(r.data_pagamento), "Pagamento da dívida"))
    if a.limite_5_anos:
        eventos.append((a.limite_5_anos, "Fim do prazo máximo de 5 anos para a negativação (CDC art. 43 §1)"))
    for p in caso.protocolos:
        if p.registro_id != r.id:
            continue
        num = f", protocolo {p.numero}" if p.numero else ""
        if ln._data(p.data):
            eventos.append((ln._data(p.data), f"Pedido via {ln.CANAIS.get(p.canal, p.canal)}{num}"))
        est = ln.situacao_protocolo(p, hoje)
        if p.aceito is not None and ln._data(p.data_resposta):
            eventos.append((ln._data(p.data_resposta),
                            f"Resposta da empresa: {'aceitou' if p.aceito else 'recusou'}"))
        elif est["atrasado"] and p.aceito is None:
            eventos.append((est["limite_resposta"], "Prazo de resposta vencido sem resposta da empresa"))
        if est["limite_exclusao"] and est["atrasado"]:
            eventos.append((est["limite_exclusao"], "Prazo de exclusão vencido com o registro mantido"))
        if ln._data(p.data_baixa):
            eventos.append((ln._data(p.data_baixa), "Registro baixado"))
    return sorted(eventos, key=lambda e: e[0])


def _provas(r: ln.Registro, a: ln.Analise, tem_protocolo: bool, pj: bool = False) -> list[str]:
    provas = ([
        "Contrato social (ou certificado do MEI) e documento do representante legal",
        "Cartão CNPJ e comprovante do porte (ME, EPP ou MEI), se for ao Juizado",
    ] if pj else [
        "Documento de identidade e CPF",
        "Comprovante de residência",
    ]) + [
        f"Print ou relatório do {r.biro} mostrando o registro, com data da consulta",
    ]
    if r.situacao == "ja_paguei":
        provas.append("Comprovante de pagamento (recibo, extrato ou boleto pago)")
    if r.situacao == "nao_reconheco":
        provas.append("Boletim de ocorrência, se houver suspeita de fraude com o CPF")
    if r.situacao == "valor_errado":
        provas.append("Documento que mostre o valor correto (contrato, fatura ou acordo)")
    if r.biro == ln.PROTESTO:
        provas.append("Certidão ou consulta de protesto (CENPROT) com cartório e título")
        if r.situacao in ("ja_paguei", "minha_no_prazo"):
            provas.append("Pedido de carta de anuência enviado ao credor e a resposta, se houver")
    if tem_protocolo:
        provas.append("Protocolos e respostas da empresa (prints do consumidor.gov.br, e-mails, cartas)")
    if r.notificado == "nao":
        provas.append("Declaração de que não recebeu aviso prévio (quem inscreveu deve provar o envio)")
    return provas


def secoes_do_kit(caso: ln.Caso, r: ln.Registro, hoje: date | None = None) -> list[tuple[str, list[str]]]:
    """[(título da seção, [linhas])]. Base comum do PDF e do Markdown."""
    hoje = hoje or date.today()
    a = ln.analisar(r, hoje, caso)
    prots = [p for p in caso.protocolos if p.registro_id == r.id]

    identificacao = ([
        f"Empresa: {caso.razao_social or caso.nome or '[razão social]'}",
        f"CNPJ: {caso.cnpj or '[CNPJ]'}, porte {ln.PORTES.get(caso.porte, 'não informado')}"
        + (f", situação {caso.situacao_cadastral}" if caso.situacao_cadastral else ""),
    ] if caso.pj else [
        f"Consumidor: {caso.nome or '[nome completo]'}",
        f"CPF: {caso.cpf_mascarado or '[CPF]'} (informar o número completo no atendimento)",
    ]) + [
        f"Credor: {r.credor}" + (f", CNPJ {r.cnpj_credor}" if r.cnpj_credor else ""),
        f"Valor registrado: {r.valor_fmt()}",
        f"Onde consta: {r.biro}",
        f"Situação: {ln.SITUACOES.get(r.situacao, r.situacao)}",
    ]

    tempo = [f"{ln.data_br(d)}: {t}" for d, t in _linha_do_tempo(caso, r, hoje)] or \
        ["Sem datas informadas. Consiga a data de vencimento antes de ir ao atendimento."]

    tentativas = []
    for p in sorted(prots, key=lambda x: x.data):
        est = ln.situacao_protocolo(p, hoje)
        linha = f"{ln.data_br(ln._data(p.data))}, {ln.CANAIS.get(p.canal, p.canal)}"
        if p.numero:
            linha += f", protocolo {p.numero}"
        linha += f": {est['status']}."
        if p.resposta:
            linha += f" Resposta: {p.resposta[:500]}"
        tentativas.append(linha)
    if not tentativas:
        tentativas = ["Nenhum pedido registrado ainda. O Procon e o Juizado costumam perguntar se você "
                      "tentou resolver antes: registre ao menos um pedido ao credor ou no consumidor.gov.br."]

    argumentos = [f"{x.titulo} ({x.base}): {x.texto}" for x in a.argumentos] or \
        ["Nenhum argumento de contestação identificado para este registro."]

    pedidos = []
    if r.biro == ln.PROTESTO:
        pedidos.append("Cancelamento do protesto ou entrega da carta de anuência pelo credor")
    else:
        pedidos.append("Exclusão do registro negativo em todos os birôs")
    pedidos.append("Tutela de urgência para suspender a negativação enquanto o caso é julgado")
    pedidos.append("Indenização por dano moral"
                   + (" da pessoa jurídica (Súmula 227 do STJ)" if caso.pj else "")
                   + ", se não houver outra negativação legítima (Súmula 385 do STJ)")

    avisos = ln.avisos_do_caso(caso, hoje)
    if a.alerta:
        avisos.insert(0, a.alerta)

    onde = [f"{etapa}: {texto}" for etapa, texto in ln.escalada(caso)[1:]]
    onde.append("O pedido de indenização prescreve em 3 anos (Código Civil, art. 206 §3 V).")

    return [
        ("Identificação", identificacao),
        ("Linha do tempo", tempo),
        ("O que já foi tentado", tentativas),
        (f"Fundamentos ({a.pilha_label})", argumentos),
        ("Pedidos", pedidos),
        ("Provas para juntar", _provas(r, a, bool(prots), caso.pj)),
        ("Atenção", avisos or ["Sem alertas para este caso."]),
        ("Onde levar", onde),
    ]


def kit_markdown(caso: ln.Caso, r: ln.Registro, hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    partes = [f"# Kit do Juizado e do Procon: {r.credor}",
              f"_Gerado pelo Limpa Nome do Mr.Holmes em {ln.data_br(hoje)}._", ""]
    for titulo, linhas in secoes_do_kit(caso, r, hoje):
        partes.append(f"## {titulo}")
        partes += [f"- {l}" for l in linhas]
        partes.append("")
    partes.append("_Documento de apoio. Não substitui a orientação de advogado ou do atendimento do Juizado._")
    return "\n".join(partes)


def disponivel_pdf() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


def kit_pdf(caso: ln.Caso, r: ln.Registro, hoje: date | None = None) -> bytes:
    """Bytes do PDF. Levanta ImportError se reportlab faltar."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    hoje = hoje or date.today()

    def esc(t: str) -> str:
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm, title=f"Kit do Juizado: {r.credor}")
    ss = getSampleStyleSheet()
    eyebrow = ParagraphStyle("eb", parent=ss["Normal"], fontSize=8, textColor=colors.HexColor("#5b5bf0"))
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=20, alignment=0, spaceAfter=2,
                        textColor=colors.HexColor("#1d2239"))
    meta = ParagraphStyle("meta", parent=ss["Normal"], fontSize=9, textColor=colors.HexColor("#5d6480"))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4,
                        textColor=colors.HexColor("#1d2239"))
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=10, leading=14)
    small = ParagraphStyle("small", parent=ss["Normal"], fontSize=8, leading=11,
                           textColor=colors.HexColor("#8a90a8"))

    el: list = [
        Paragraph("KIT DO JUIZADO E DO PROCON · LIMPA NOME · MR.HOLMES", eyebrow),
        Paragraph(esc(r.credor), h1),
        Paragraph(f"{esc(r.valor_fmt())} · {esc(r.biro)} · gerado em {ln.data_br(hoje)}", meta),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#5b5bf0")),
    ]
    for titulo, linhas in secoes_do_kit(caso, r, hoje):
        el.append(Paragraph(esc(titulo), h2))
        el.append(ListFlowable([ListItem(Paragraph(esc(l), body), leftIndent=10) for l in linhas],
                               bulletType="bullet", start="•", leftIndent=12))
    el += [Spacer(1, 14), Paragraph("Documento de apoio. Não substitui a orientação de advogado ou do "
                                    "atendimento do Juizado. Confira datas e valores antes de protocolar.", small)]
    doc.build(el)
    return buf.getvalue()
