"""Exportador de Relatório PDF para Mr.Holmes"""

import os
from datetime import datetime

def gerar_relatorio_pdf(
    numero: str,
    internacional: str,
    local: str,
    pais: str,
    area: str,
    operadora: str,
    ddd_info: dict,
    sites_encontrados: list,
    pasta_saida: str,
) -> str:
    """Gera um PDF simples com os dados da busca."""
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        return _gerar_pdf_texto(numero, internacional, local, pais, area, operadora, ddd_info, sites_encontrados, pasta_saida)
    
    os.makedirs(pasta_saida, exist_ok=True)
    caminho = os.path.join(pasta_saida, f"{numero}_report.pdf")
    
    doc = SimpleDocTemplate(caminho, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=2*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    
    titulo = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#1a1a2e'), spaceAfter=12, alignment=1)
    subtitulo = ParagraphStyle('Subtitulo', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#059669'), spaceAfter=8)
    normal = ParagraphStyle('Normal', parent=styles['BodyText'], fontSize=10, leading=14)
    
    content = []
    content.append(Paragraph("Mr.Holmes - Relatorio de Busca", titulo))
    content.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal))
    content.append(Spacer(1, 1*cm))
    
    dados = [
        ["Numero", numero],
        ["Formato Internacional", internacional],
        ["Pais", pais],
        ["Area / Estado", area],
        ["Operadora", operadora or "N/A"],
        ["DDD / Cidade", f"{local[:2]} - {ddd_info.get('city', 'N/A')}" if len(local) >= 2 else "N/A"],
        ["Latitude", str(ddd_info.get('lat', 'N/A'))],
        ["Longitude", str(ddd_info.get('lon', 'N/A'))],
    ]
    
    table = Table(dados, colWidths=[5*cm, 11*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f2f5')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1a1a2e')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))
    content.append(table)
    content.append(Spacer(1, 1*cm))
    
    if sites_encontrados:
        content.append(Paragraph("Sites Encontrados", subtitulo))
        for site in sites_encontrados:
            content.append(Paragraph(f"- {site}", normal))
    else:
        content.append(Paragraph("Nenhum site encontrado com este numero.", normal))
    
    content.append(Spacer(1, 1*cm))
    content.append(Paragraph("Mr.Holmes OSINT Tool - Para fins educacionais", ParagraphStyle('Footer', parent=normal, fontSize=8, textColor=colors.grey)))
    
    doc.build(content)
    return caminho

def _gerar_pdf_texto(numero, internacional, local, pais, area, operadora, ddd_info, sites_encontrados, pasta_saida):
    """Fallback: gera um arquivo texto formatado (sem reportlab)."""
    os.makedirs(pasta_saida, exist_ok=True)
    caminho = os.path.join(pasta_saida, f"{numero}_report.txt")
    
    linhas = [
        "=" * 60,
        "  Mr.Holmes - Relatorio de Busca",
        "=" * 60,
        f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        f"Numero: {numero}",
        f"Internacional: {internacional}",
        f"Pais: {pais}",
        f"Area: {area}",
        f"Operadora: {operadora or 'N/A'}",
        f"Coordenadas: {ddd_info.get('lat', 'N/A')}, {ddd_info.get('lon', 'N/A')}",
        "",
    ]
    
    if sites_encontrados:
        linhas.append("Sites Encontrados:")
        for s in sites_encontrados:
            linhas.append(f"  - {s}")
    
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    
    return caminho
