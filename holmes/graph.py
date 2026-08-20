"""
Grafo de conexões do dossiê.

Transforma a lista de fatos num mapa: o alvo no centro, e cada achado
(perfil, e-mail, telefone, empresa, sócio, domínio…) como um nó ligado a ele.
Sócio de empresa liga na empresa, não no alvo — é isso que faz a rede
"pessoa → empresa → sócio" aparecer em vez de uma lista chapada.

Renderiza HTML autocontido com vis-network (CDN). Sem dependência nova no
servidor: é só um bloco HTML embutido na página.
"""

from __future__ import annotations

import html
import json

from .dossier import Dossier
from .findings import FindingKind

# Cor e forma por tipo de nó — leitura rápida do mapa.
_ESTILO = {
    "alvo":     {"color": "#0f62fe", "shape": "star",     "size": 30},
    "nome":     {"color": "#8b5cf6", "shape": "dot",      "size": 20},
    "conta":    {"color": "#0ea5e9", "shape": "dot",      "size": 16},
    "email":    {"color": "#10b981", "shape": "diamond",  "size": 16},
    "telefone": {"color": "#f59e0b", "shape": "triangle", "size": 16},
    "empresa":  {"color": "#ef4444", "shape": "square",   "size": 22},
    "endereco": {"color": "#14b8a6", "shape": "dot",      "size": 14},
    "dominio":  {"color": "#64748b", "shape": "dot",      "size": 14},
    "vazamento":{"color": "#dc2626", "shape": "triangleDown", "size": 16},
    "cripto":   {"color": "#eab308", "shape": "hexagon",  "size": 16},
    "documento":{"color": "#a855f7", "shape": "square",   "size": 16},
    "juridico": {"color": "#b91c1c", "shape": "square",   "size": 16},
}

# Tipos que viram nó no grafo (o resto — nota, link, resultado web — é ruído visual).
_TIPOS_NO = {
    FindingKind.NAME, FindingKind.ACCOUNT, FindingKind.EMAIL, FindingKind.PHONE,
    FindingKind.COMPANY, FindingKind.ADDRESS, FindingKind.DOMAIN,
    FindingKind.BREACH, FindingKind.CRYPTO, FindingKind.DOCUMENT, FindingKind.LEGAL,
}


def build(dossier: Dossier, min_score: float = 0.3, max_nos: int = 80) -> dict:
    """Monta {nodes, edges} a partir dos fatos consolidados do dossiê."""
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = set()

    alvo_id = "alvo"
    nodes.append({
        "id": alvo_id,
        "label": html.escape(_quebra(dossier.entity.value, 22)),
        "title": html.escape(f"ALVO: {dossier.entity.value}"),
        **_ESTILO["alvo"],
        "font": {"color": "#e2e8f0", "size": 18, "strokeWidth": 4, "strokeColor": "#0b1220"},
    })

    # Empresas viram âncora: sócio se liga à empresa, e a empresa ao alvo.
    empresa_ids: list[str] = []

    for kind in (FindingKind.COMPANY, FindingKind.NAME, FindingKind.ACCOUNT,
                 FindingKind.EMAIL, FindingKind.PHONE, FindingKind.ADDRESS,
                 FindingKind.DOMAIN, FindingKind.BREACH, FindingKind.CRYPTO,
                 FindingKind.DOCUMENT, FindingKind.LEGAL):
        if kind not in _TIPOS_NO:
            continue
        for fato in dossier.section(kind):
            if fato.score < min_score:
                continue
            if len(nodes) >= max_nos:
                break
            nid = f"{kind.value}:{fato.value.lower()}"
            if nid in seen:
                continue
            seen.add(nid)
            estilo = _ESTILO.get(kind.value, {"color": "#94a3b8", "shape": "dot", "size": 14})
            nodes.append({
                "id": nid,
                "label": html.escape(_quebra(fato.value, 24)),
                "title": html.escape(_tooltip(fato)),
                **estilo,
                "font": {"color": "#cbd5e1", "size": 12},
            })

            # A quem este nó se liga.
            destino = alvo_id
            if kind is FindingKind.COMPANY:
                empresa_ids.append(nid)
            elif kind is FindingKind.NAME and empresa_ids and _e_socio(fato):
                # Sócio: liga à empresa mais recente (quadro societário).
                destino = empresa_ids[-1]

            edges.append({
                "from": destino, "to": nid,
                "color": {"color": "rgba(148,163,184,.35)"},
                "width": 1 + 2 * fato.score,
            })

    return {"nodes": nodes, "edges": edges}


def _e_socio(fato) -> bool:
    d = (fato.detail or "").lower()
    return "sócio" in d or "socio" in d or "quadro societário" in d


def _quebra(texto: str, largura: int) -> str:
    """Quebra o rótulo em linhas para não virar um nó gigante."""
    t = (texto or "").strip()
    if len(t) <= largura:
        return t
    palavras = t.split()
    linhas, atual = [], ""
    for p in palavras:
        if len(atual) + len(p) + 1 > largura:
            linhas.append(atual)
            atual = p
        else:
            atual = f"{atual} {p}".strip()
    if atual:
        linhas.append(atual)
    return "\n".join(linhas[:3])


def _tooltip(fato) -> str:
    partes = [fato.value, f"confiança: {fato.label}", f"fontes: {', '.join(fato.sources[:4])}"]
    if fato.detail:
        partes.append(fato.detail[:140])
    return " | ".join(partes)


def to_html(dossier: Dossier, altura: int = 560) -> str:
    """HTML autocontido com o grafo interativo (arrastar, zoom, clicar)."""
    dados = build(dossier)
    dados_json = json.dumps(dados, ensure_ascii=False)
    alvo = html.escape(dossier.entity.value)

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  body{{margin:0;background:#0b1220;font-family:ui-sans-serif,-apple-system,'Segoe UI',Roboto,sans-serif}}
  #rede{{width:100%;height:{altura}px}}
  .legenda{{position:absolute;top:8px;left:8px;background:rgba(11,18,32,.85);
    border:1px solid rgba(148,163,184,.25);border-radius:8px;padding:8px 10px;
    font-size:11px;color:#94a3b8;line-height:1.7;z-index:5}}
  .legenda b{{color:#e2e8f0}}
  .dica{{position:absolute;bottom:8px;right:12px;font-size:11px;color:#64748b;z-index:5}}
</style></head><body>
<div class="legenda">
  <b>{alvo}</b><br>
  ⭐ alvo · 🟣 nome · 🔵 conta · 🟢 e-mail<br>
  🟠 telefone · 🟥 empresa · 🔴 vazamento
</div>
<div id="rede"></div>
<div class="dica">arraste os nós · role para dar zoom · clique para focar</div>
<script>
  const dados = {dados_json};
  const nodes = new vis.DataSet(dados.nodes);
  const edges = new vis.DataSet(dados.edges);
  const container = document.getElementById('rede');
  new vis.Network(container, {{nodes, edges}}, {{
    physics: {{stabilization: true, barnesHut: {{gravitationalConstant: -8000, springLength: 130}}}},
    interaction: {{hover: true, tooltipDelay: 120, navigationButtons: false}},
    nodes: {{borderWidth: 0, shadow: false}},
    edges: {{smooth: {{type: 'continuous'}}}}
  }});
</script></body></html>"""


def stats(dossier: Dossier) -> dict:
    d = build(dossier)
    return {"nos": len(d["nodes"]), "conexoes": len(d["edges"])}
