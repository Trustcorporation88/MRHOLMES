"""Visual do painel.

As cores de base (fundo, texto, destaque, raio, barra lateral) ficam em
`.streamlit/config.toml`, que é o tema nativo do Streamlit: os componentes
dele já nascem escuros e coerentes. Aqui fica só o que é nosso: marca, faixa
de busca, cartões de fato, linha do tempo, diretório.

Regra que não pode ser quebrada: este CSS não pode conter o caractere "<".
O `st.html` passa o bloco por um sanitizador de HTML e descarta o estilo
INTEIRO se achar algo com cara de tag, mesmo dentro de comentário. Foi assim
que o painel ficou dois meses sem tema. `aplicar()` e um teste conferem isso.
"""

from __future__ import annotations

import streamlit as st

CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg: #0a0e17;
  --surface: #111827;
  --surface-2: #172033;
  --surface-3: #1e2a42;
  --line: #243049;
  --line-strong: #33425f;
  --text: #e6eaf2;
  --muted: #8f9bb3;
  --faint: #64708a;
  --accent: #6c8cff;
  --accent-2: #22d3ee;
  --accent-soft: rgba(108, 140, 255, 0.14);
  --ok: #34d399;
  --warn: #fbbf24;
  --bad: #f87171;
  --radius: 14px;
  --mono: 'JetBrains Mono', ui-monospace, Consolas, monospace;
}

/* ── base ─────────────────────────────────────────────────────────────── */
html, body, .stApp, [data-testid="stSidebar"] { font-family: 'Inter', system-ui, sans-serif; }
.stApp { background:
  radial-gradient(1100px 520px at 78% -8%, rgba(108, 140, 255, 0.13), transparent 62%),
  radial-gradient(820px 460px at 4% 2%, rgba(34, 211, 238, 0.07), transparent 60%),
  var(--bg); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { max-width: 1180px; padding-top: 2.2rem; padding-bottom: 4rem; }
[data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded' !important; }
h1, h2, h3 { letter-spacing: -0.02em; }
h2 { font-size: 1.35rem !important; font-weight: 700 !important; }
h3 { font-size: 1.05rem !important; font-weight: 700 !important; }
a { color: var(--accent); }
code { font-family: var(--mono); }
hr { border-color: var(--line) !important; opacity: 1; margin: 1.4rem 0 !important; }

/* ── barra lateral ────────────────────────────────────────────────────── */
[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
[data-testid="stSidebarContent"] { padding-top: 0.4rem; }
.mh-brand { display: flex; align-items: center; gap: 12px; padding: 4px 4px 18px; }
.mh-brand-badge { width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center;
  font-size: 1.25rem; background: linear-gradient(135deg, var(--accent), var(--accent-2));
  box-shadow: 0 8px 22px rgba(108, 140, 255, 0.35); }
.mh-brand .name { font-weight: 800; font-size: 1.15rem; letter-spacing: -0.02em; color: var(--text); line-height: 1.1; }
.mh-brand .tag { font-size: 0.74rem; color: var(--muted); margin-top: 2px; }
.mh-nav-group { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--faint); margin: 14px 6px 2px; }
[data-testid="stSidebar"] .stButton > button { justify-content: flex-start; text-align: left; border: 1px solid transparent;
  background: transparent; color: var(--muted); font-weight: 500; padding: 0.5rem 0.75rem; border-radius: 10px;
  transition: background .12s, color .12s; }
[data-testid="stSidebar"] .stButton > button:hover { background: var(--surface-2); color: var(--text); border-color: transparent; }
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] {
  background: var(--accent-soft); color: var(--text); border-color: rgba(108, 140, 255, 0.35); font-weight: 600; }
[data-testid="stSidebar"] .stButton > button > div, [data-testid="stSidebar"] .stButton > button p {
  justify-content: flex-start; text-align: left; width: 100%; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.3rem; }
.st-key-mh_tipos .stButton > button p { white-space: pre-line; }
.mh-side-foot { font-size: 0.72rem; color: var(--faint); line-height: 1.5; padding: 4px 6px; }
.mh-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; background: var(--faint); }
.mh-dot.on { background: var(--ok); box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.16); }

/* ── cabeçalho das páginas ────────────────────────────────────────────── */
.mh-page { display: flex; align-items: center; gap: 16px; margin: 0 0 1.4rem; }
.mh-page-icon { width: 52px; height: 52px; border-radius: 14px; display: grid; place-items: center; font-size: 1.5rem;
  background: var(--surface-2); border: 1px solid var(--line); flex: none; }
.mh-page-body { min-width: 0; }
.mh-chip.on { color: var(--ok); border-color: rgba(52, 211, 153, 0.4); }
.mh-chip.off { color: var(--faint); }
.mh-page .eyebrow, .mh-hero-eyebrow { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--accent-2); }
.mh-page h1 { font-size: 1.7rem; font-weight: 800; margin: 2px 0 0; padding: 0; color: var(--text); }
.mh-page .desc { color: var(--muted); font-size: 0.93rem; margin-top: 3px; }

/* ── faixa de busca (Investigar) ──────────────────────────────────────── */
.mh-hero { margin: 0.2rem 0 1.1rem; }
.mh-hero-title { font-size: 2.3rem; font-weight: 800; letter-spacing: -0.035em; line-height: 1.1; margin: 8px 0 8px;
  padding: 0; background: linear-gradient(92deg, #ffffff 0%, #b9c7ff 55%, #7fe3f5 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent; }
.mh-hero-sub { color: var(--muted); font-size: 1rem; margin: 0; max-width: 640px; }
.mh-hero-stats { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.mh-hero-stats span { font-size: 0.78rem; color: var(--muted); background: var(--surface); border: 1px solid var(--line);
  border-radius: 999px; padding: 4px 12px; }
.mh-hero-stats strong { color: var(--text); font-weight: 700; }
.mh-hero-stats .mh-hero-badge { color: var(--ok); border-color: rgba(52, 211, 153, 0.3); background: rgba(52, 211, 153, 0.08); }

/* escolha do tipo de consulta: uma fileira de cartões clicáveis */
.st-key-mh_tipos .stButton > button { height: 76px; width: 100%; border-radius: var(--radius); background: var(--surface);
  border: 1px solid var(--line); color: var(--muted); font-weight: 600; font-size: 0.8rem; line-height: 1.25;
  transition: transform .12s, border-color .12s, background .12s, color .12s; padding: 6px 4px; }
.st-key-mh_tipos .stButton > button p { font-size: 0.8rem; }
.st-key-mh_tipos .stButton > button:hover { transform: translateY(-2px); border-color: var(--accent); color: var(--text);
  background: var(--surface-2); }
.st-key-mh_tipos .stButton > button[kind="primary"],
.st-key-mh_tipos .stButton > button[data-testid="stBaseButton-primary"] { background: var(--accent-soft);
  border-color: var(--accent); color: var(--text); box-shadow: 0 0 0 3px rgba(108, 140, 255, 0.12); }

/* a caixa de busca */
.st-key-mh_busca { background: var(--surface); border: 1px solid var(--line-strong); border-radius: 18px;
  padding: 10px 12px 2px; box-shadow: 0 18px 50px rgba(0, 0, 0, 0.35); margin-top: 6px; }
.st-key-mh_busca [data-testid="stForm"] { border: 0; padding: 0; }
.st-key-mh_busca input { font-size: 1.05rem !important; height: 52px; background: transparent !important; }
.st-key-mh_busca [data-baseweb="input"], .st-key-mh_busca [data-baseweb="base-input"] { background: transparent !important;
  border-color: transparent !important; }
.st-key-mh_busca .stFormSubmitButton > button { height: 52px; border-radius: 12px; font-weight: 700; border: 0;
  background: linear-gradient(135deg, var(--accent), #4b6bf5); color: #fff; }
.st-key-mh_busca .stFormSubmitButton > button:hover { filter: brightness(1.1); }

/* buscas recentes e atalhos */
.st-key-mh_chips .stButton > button { border-radius: 999px; background: transparent; border: 1px solid var(--line);
  color: var(--muted); font-size: 0.8rem; padding: 0.2rem 0.8rem; min-height: 0; font-family: var(--mono); }
.st-key-mh_chips .stButton > button:hover { border-color: var(--accent); color: var(--text); }
.st-key-mh_tiles .stButton > button { height: 58px; border-radius: var(--radius); background: var(--surface);
  border: 1px solid var(--line); color: var(--text); font-weight: 600; }
.st-key-mh_tiles .stButton > button:hover { border-color: var(--accent); background: var(--surface-2); }
.mh-hint-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--faint); margin: 10px 0 4px; }
.mh-section { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.13em; text-transform: uppercase;
  color: var(--faint); margin: 1.6rem 0 0.6rem; display: flex; align-items: center; gap: 10px; }
.mh-section::after { content: ""; flex: 1; height: 1px; background: var(--line); }
.mh-soft { color: var(--muted); font-size: 0.84rem; }

/* ── componentes nativos, só o acabamento ─────────────────────────────── */
[data-testid="stMetric"] { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 14px 16px; }
[data-testid="stMetricLabel"] p { color: var(--muted); font-size: 0.78rem; }
[data-testid="stMetricValue"] { font-weight: 800; letter-spacing: -0.03em; }
[data-testid="stExpander"] details { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  overflow: hidden; }
[data-testid="stExpander"] summary { font-weight: 600; padding: 0.7rem 1rem; }
[data-testid="stExpander"] summary:hover { color: var(--accent); }
[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--line) !important; border-radius: var(--radius) !important; }
[data-testid="stAlert"] { border-radius: var(--radius); border: 1px solid var(--line); }
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { font-weight: 600; padding: 8px 14px; }
.stButton > button, .stDownloadButton > button, .stLinkButton > a { border-radius: 10px; font-weight: 600; }
[data-testid="stProgress"] > div > div > div > div { background: linear-gradient(90deg, var(--accent), var(--accent-2)); }

/* ── dossiê ───────────────────────────────────────────────────────────── */
.mh-idcard { display: flex; gap: 18px; align-items: center; background:
  linear-gradient(135deg, rgba(108, 140, 255, 0.16), rgba(34, 211, 238, 0.06)), var(--surface);
  border: 1px solid var(--line-strong); border-radius: 18px; padding: 18px 20px; margin: 4px 0 16px; }
.mh-idcard-photo, .mh-idcard-initial { width: 76px; height: 76px; border-radius: 18px; flex: none; object-fit: cover;
  border: 1px solid var(--line-strong); }
.mh-idcard-initial { display: grid; place-items: center; font-size: 1.9rem; font-weight: 800; color: #fff;
  background: linear-gradient(135deg, var(--accent), var(--accent-2)); }
.mh-idcard-body { min-width: 0; flex: 1; }
.mh-idcard-kicker { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: var(--accent-2); }
.mh-idcard-name { font-size: 1.5rem; font-weight: 800; letter-spacing: -0.02em; color: var(--text); margin: 2px 0 8px;
  overflow-wrap: anywhere; }
.mh-idcard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 4px 18px; }
.mh-idcard-row { font-size: 0.86rem; color: var(--muted); overflow-wrap: anywhere; }
.mh-idcard-row b, .mh-idcard-row strong { color: var(--text); font-weight: 600; }
.mh-flag { color: var(--bad); font-weight: 700; }

.mh-fact { --c: var(--faint); position: relative; background: var(--surface-2); border: 1px solid var(--line);
  border-left: 3px solid var(--c); border-radius: 12px; padding: 10px 14px; margin: 0 0 8px; }
.mh-fact-tag { display: inline-block; font-size: 0.64rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--c); border: 1px solid var(--c); border-radius: 999px; padding: 1px 8px; margin-right: 10px;
  vertical-align: 2px; opacity: 0.95; }
.mh-fact-val { font-weight: 600; color: var(--text); font-size: 0.97rem; overflow-wrap: anywhere; }
.mh-fact-detail { color: var(--muted); font-size: 0.85rem; margin-top: 4px; overflow-wrap: anywhere; }
.mh-fact-src { color: var(--faint); font-size: 0.72rem; margin-top: 5px; font-family: var(--mono); }
.mh-fact-link { font-size: 0.76rem; margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mh-fact-link a { color: var(--accent); text-decoration: none; }
.mh-fact-link a:hover { text-decoration: underline; }

.mh-cand { display: flex; align-items: center; gap: 14px; background: var(--surface-2); border: 1px solid var(--line);
  border-radius: 12px; padding: 10px 14px; margin-bottom: 8px; }
.mh-cand-ico { width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; font-size: 1.05rem;
  background: var(--accent-soft); flex: none; }
.mh-cand-nome { font-weight: 700; color: var(--text); }
.mh-cand-doc { font-family: var(--mono); font-size: 0.8rem; color: var(--accent-2); margin-left: 8px; }
.mh-cand-det { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }

.mh-tl-row { display: flex; gap: 14px; padding: 8px 0; border-bottom: 1px dashed var(--line); font-size: 0.88rem; }
.mh-tl-date { font-family: var(--mono); color: var(--accent-2); min-width: 96px; font-size: 0.8rem; padding-top: 1px; }
.mh-tl-src { color: var(--faint); font-size: 0.72rem; }
.mh-chip { display: inline-block; border: 1px solid var(--line-strong); border-radius: 999px; padding: 2px 10px;
  font-size: 0.76rem; font-weight: 600; margin: 0 6px 6px 0; }
.mh-quick-links { display: flex; flex-wrap: wrap; gap: 8px; }
.legenda, .dica { color: var(--muted); font-size: 0.82rem; }

/* ── diretório de fontes ──────────────────────────────────────────────── */
.mh-dir-grade { display: grid; grid-template-columns: repeat(auto-fill, minmax(255px, 1fr)); gap: 10px; }
.mh-dir { display: flex; flex-direction: column; gap: 5px; padding: 13px 15px; border-radius: 12px;
  border: 1px solid var(--line); background: var(--surface-2); text-decoration: none !important;
  transition: transform .12s, border-color .12s, background .12s; }
.mh-dir:hover { transform: translateY(-2px); border-color: var(--accent); background: var(--surface-3); }
.mh-dir-nome { font-weight: 700; color: var(--text); font-size: 0.92rem; }
.mh-dir-txt { color: var(--muted); font-size: 0.8rem; line-height: 1.4; flex: 1; }
.mh-dir-tags { display: flex; gap: 10px; flex-wrap: wrap; font-size: 0.7rem; color: var(--faint); margin-top: 3px; }
.mh-dir-tags .gratis { color: var(--ok); }
.mh-dir-tags .login { color: var(--accent-2); }
.mh-dir-tags .pago { color: var(--warn); }
"""

# Cor do rótulo de confiança de cada fato (usada como --c nos cartões).
COR_CONFIANCA = {"alta": "#34d399", "media": "#fbbf24", "baixa": "#f87171", "indicio": "#64708a"}


def css_valido(css: str = CSS) -> bool:
    """O sanitizador do `st.html` descarta o estilo inteiro se houver "<"."""
    return "<" not in css


def aplicar() -> None:
    """Injeta o tema. Chamar uma vez, logo depois do `set_page_config`."""
    if not css_valido():
        st.error('O CSS do tema contém "<" e seria descartado pelo navegador. Corrija tema.py.')
        return
    # Só o bloco de estilo: vai para o container de eventos, sem ocupar espaço.
    st.html("<style>" + CSS + "</style>")
