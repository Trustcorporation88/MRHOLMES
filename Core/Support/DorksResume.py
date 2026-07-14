"""Resumo inteligente de Dorks - reduz o flood de links mostrando só os melhores"""

def resumir_dorks(full_output: str) -> str:
    """Filtra apenas os dorks mais relevantes do output completo."""
    lines = full_output.split("\n")
    resumo = []
    
    redes = []
    google_top = []
    yandex_top = []
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("[v]---") or line_stripped.startswith("REPORT"):
            continue
        
        if "instagram.com" in line_stripped and line_stripped not in redes:
            redes.append(line_stripped)
        elif "facebook.com" in line_stripped and line_stripped not in redes:
            redes.append(line_stripped)
        elif "linkedin.com" in line_stripped and line_stripped not in redes:
            redes.append(line_stripped)
        elif "twitter.com" in line_stripped and line_stripped not in redes:
            redes.append(line_stripped)
        elif "google.com/search" in line_stripped and "intext" in line_stripped and "filetype" not in line_stripped:
            if len(google_top) < 2:
                google_top.append(line_stripped)
        elif "yandex.com/search" in line_stripped and "mime" not in line_stripped and "site:" not in line_stripped:
            if len(yandex_top) < 2:
                yandex_top.append(line_stripped)
    
    resumo.append("=" * 60)
    resumo.append("  RESUMO DOS MELHORES DORKS")
    resumo.append("=" * 60)
    
    if google_top:
        resumo.append("\n[GOOGLE - Busca Geral]:")
        for g in google_top:
            resumo.append(f"  {g.replace('[v]| ', '').strip()}")
    
    if yandex_top:
        resumo.append("\n[YANDEX - Busca Geral]:")
        for y in yandex_top:
            resumo.append(f"  {y.replace('[v]| ', '').strip()}")
    
    if redes:
        resumo.append("\n[REDES SOCIAIS - Mais Relevantes]:")
        for r in redes:
            resumo.append(f"  {r.replace('[v]| ', '').strip()}")
    
    resumo.append(f"\n[+] Dorks completos salvos em: GUI/Reports/Phone/Dorks/")
    resumo.append("=" * 60)
    
    return "\n".join(resumo)
