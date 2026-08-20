"""
Relatório PDF do dossiê.

Gera um PDF com cara de dossiê de agência — capa com o alvo e as métricas,
leitura do caso, o que está bem sustentado, e as seções com fonte e link.
Usa reportlab (já no requirements), sem binário externo.
"""

from __future__ import annotations

import io

from .dossier import Dossier
from .findings import FindingKind

_COR = {
    "alta": "#0f9d58", "media": "#f4b400", "baixa": "#db4437", "indicio": "#9aa5b1",
}


def generate(dossier: Dossier) -> bytes:
    """Devolve os bytes do PDF. Levanta ImportError se reportlab faltar."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    def esc(t: str) -> str:
        return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=16 * mm, rightMargin=16 * mm,
        title=f"Dossiê — {dossier.entity.value}",
    )
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=22, spaceAfter=2, textColor=colors.HexColor("#0b1220"))
    eyebrow = ParagraphStyle("eb", parent=ss["Normal"], fontSize=8, textColor=colors.HexColor("#64748b"))
    meta = ParagraphStyle("meta", parent=ss["Normal"], fontSize=9, textColor=colors.HexColor("#64748b"))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=4,
                        textColor=colors.HexColor("#0f172a"))
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=10, leading=14, alignment=TA_LEFT)
    small = ParagraphStyle("small", parent=ss["Normal"], fontSize=8, textColor=colors.HexColor("#64748b"), leading=11)

    el: list = []
    s = dossier.stats

    el.append(Paragraph("DOSSIÊ DE INVESTIGAÇÃO · MR.HOLMES", eyebrow))
    el.append(Paragraph(esc(dossier.entity.value), h1))
    el.append(Paragraph(f"{esc(dossier.entity.label)} · gerado em {esc(dossier.started_at)}", meta))
    el.append(Spacer(1, 6))
    el.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0b1220")))
    el.append(Spacer(1, 8))

    # Métricas em tabela.
    tab = Table([[
        f"{s['fontes_consultadas']}\nfontes", f"{s['fatos_consolidados']}\nfatos",
        f"{s['pivos']}\npivôs", f"{s['achados_brutos']}\nachados",
    ]], colWidths=[42 * mm] * 4)
    tab.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 11), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    el.append(tab)

    if dossier.summary:
        el.append(Paragraph("Leitura do caso", h2))
        for par in dossier.summary.split("\n"):
            if par.strip():
                el.append(Paragraph(esc(par), body))

    destaque = dossier.high_confidence(0.55)
    if destaque:
        el.append(Paragraph("O que está bem sustentado", h2))
        for fato in destaque[:20]:
            el.append(Paragraph(
                f"<b>{esc(fato.value)}</b> — <font color='{_COR.get(fato.label, '#64748b')}'>"
                f"{esc(fato.label)}</font> · {esc(', '.join(fato.sources[:4]))}", body))

    for label, items in dossier.sections():
        if label in ("Fontes para abrir", "Resultados na web"):
            continue
        el.append(Paragraph(f"{esc(label)} ({len(items)})", h2))
        for fato in items[:40]:
            linha = f"<b>{esc(fato.value)}</b>"
            if fato.detail:
                linha += f" — {esc(fato.detail[:180])}"
            el.append(Paragraph(linha, body))
            rodape = f"confiança {esc(fato.label)} · fontes: {esc(', '.join(fato.sources[:5]))}"
            if fato.urls:
                rodape += f" · {esc(fato.urls[0])}"
            el.append(Paragraph(rodape, small))
            el.append(Spacer(1, 3))

    if dossier.next_steps:
        el.append(Paragraph("Próximos passos", h2))
        for passo in dossier.next_steps:
            el.append(Paragraph(f"• {esc(passo)}", body))

    el.append(Spacer(1, 12))
    el.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    el.append(Paragraph(
        "Gerado pelo Mr.Holmes a partir de fontes públicas. Uso educacional, em "
        "alvos autorizados. Confirme cada fato na fonte antes de qualquer decisão.", small))

    doc.build(el)
    return buf.getvalue()


def available() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False
