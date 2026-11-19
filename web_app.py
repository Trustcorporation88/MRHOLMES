"""Mr.Holmes: painel de consultas e investigação."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from nav import apply_pending_navigation, queue_navigation
from diretorio_ui import display_diretorio
from robin_workspace import display_robin_workspace, sync_llm_keys_from_session
from holmes_ui import display_investigar, display_historico, display_monitoramento
from limpanome_ui import display_limpar_nome

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

st.set_page_config(
    page_title="Mr.Holmes",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ────────────────────────────────────────────────────────────
# Injeta CSS no documento pai (markdown do Streamlit novo remove <style> e mostra texto)

_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
/* Tema claro e leve: fundo papel, cartões brancos, cor só onde tem ação. */
:root {
  --ink: #1d2239;
  --ink-soft: #5d6480;
  --ink-faint: #8a90a8;
  --paper: #f6f7fb;
  --panel: #ffffff;
  --panel-2: #f2f4fa;
  --sidebar: #ffffff;
  --sidebar-text: #3a4060;
  --accent: #5b5bf0;
  --accent-hover: #4845d8;
  --accent-soft: #ededff;
  --accent-warm: #f2703f;
  --warm-soft: #fff0e8;
  --sun: #f5b400;
  --sun-soft: #fff7d9;
  --mint: #10b27c;
  --mint-soft: #e3f8ef;
  --pink: #e8488a;
  --pink-soft: #fde9f2;
  --sky: #1f9bdc;
  --sky-soft: #e4f4fd;
  --line: #e3e6ef;
  --line-soft: #eef0f6;
  --ok: #10b27c;
  --shadow: 0 1px 2px rgba(29, 34, 57, 0.05), 0 2px 8px rgba(29, 34, 57, 0.04);
  --shadow-hover: 0 4px 14px rgba(91, 91, 240, 0.12);
  --radius: 14px;
  --mono: 'JetBrains Mono', ui-monospace, monospace;
  --sans: 'Plus Jakarta Sans', system-ui, sans-serif;
  --display: 'Plus Jakarta Sans', system-ui, sans-serif;
}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background: var(--paper) !important;
  color: var(--ink) !important;
  font-family: var(--sans) !important;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
.main, [data-testid="stMain"] { background: transparent !important; }
[data-testid="stMain"] .block-container {
  padding-top: 1.1rem !important;
  padding-bottom: 2.5rem !important;
  max-width: 1120px !important;
}
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stToolbar"] { color: var(--ink-soft) !important; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"], [data-testid="stSidebarContent"],
section[data-testid="stSidebar"] > div {
  background: var(--sidebar) !important;
  border-right: 1px solid var(--line) !important;
}
[data-testid="stSidebar"] * { color: var(--sidebar-text) !important; font-family: var(--sans) !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  color: var(--ink) !important;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color: var(--ink-faint) !important; font-size: 0.74rem !important; }
.mh-nav-group {
  font-family: var(--sans); font-size: 0.68rem; letter-spacing: 0.1em; font-weight: 700;
  text-transform: uppercase; color: var(--ink-faint) !important;
  margin: 0.6rem 0 0.3rem 0.2rem;
}
.mh-brand { padding: 0.1rem 0 0.9rem 0; border-bottom: 1px solid var(--line); margin-bottom: 0.6rem; }
.mh-brand .mark {
  font-size: 0.66rem; letter-spacing: 0.12em; font-weight: 700;
  text-transform: uppercase; color: var(--accent) !important; margin-bottom: 0.3rem;
}
.mh-brand-row { display: flex; align-items: center; gap: 0.6rem; }
.mh-brand-badge {
  width: 2.2rem; height: 2.2rem; border-radius: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 1.1rem;
  background: linear-gradient(135deg, #ffd66b, #ff9f6b);
}
.mh-brand .name {
  font-family: var(--display); font-size: 1.35rem; font-weight: 800;
  color: var(--ink) !important; letter-spacing: -0.03em; line-height: 1.1;
}
.mh-brand .tag { font-size: 0.76rem; color: var(--ink-faint) !important; margin-top: 0.3rem; }

/* itens do menu: lista compacta, item ativo em pílula colorida */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.08rem !important; }
[data-testid="stSidebar"] .stButton { margin: 0 !important; }
[data-testid="stSidebar"] .stButton > button {
  width: 100% !important; border-radius: 10px !important;
  background: transparent !important; color: var(--sidebar-text) !important;
  border: none !important;
  font-family: var(--sans) !important; font-weight: 500 !important; font-size: 0.88rem !important;
  padding: 0.42rem 0.65rem !important; line-height: 1.2 !important;
  box-shadow: none !important; transform: none !important; min-height: 0 !important;
  display: flex !important; justify-content: flex-start !important;
}
[data-testid="stSidebar"] .stButton > button > div { width: 100% !important; justify-content: flex-start !important; }
[data-testid="stSidebar"] .stButton > button p { text-align: left !important; width: 100% !important; }
[data-testid="stSidebar"] .stButton > button:hover {
  background: var(--panel-2) !important; color: var(--ink) !important;
  box-shadow: none !important; transform: none !important; filter: none !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"],
[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] {
  background: var(--accent-soft) !important; font-weight: 700 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] p,
[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] p { color: var(--accent) !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] { border: none !important; background: transparent !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] details { border: none !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
  padding: 0.35rem 0.4rem !important; border-radius: 10px !important;
  font-size: 0.68rem !important; letter-spacing: 0.1em !important; text-transform: uppercase !important;
  color: var(--ink-faint) !important; font-weight: 700 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover { background: var(--panel-2) !important; }
/* o texto do grupo vem num <p> próprio do Streamlit: estiliza ele também */
[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
[data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p {
  font-size: 0.68rem !important; letter-spacing: 0.1em !important; text-transform: uppercase !important;
  color: var(--ink-faint) !important; font-weight: 700 !important; line-height: 1.2 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
  font-size: 1rem !important; color: var(--ink-faint) !important;
}
/* rótulo "Principal" sem a margem negativa do markdown, que o cortava */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:has(.mh-nav-group),
[data-testid="stSidebar"] [data-testid="stHtml"]:has(.mh-nav-group) { margin-bottom: 0.2rem !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] { padding: 0.1rem 0 0 0 !important; }
[data-testid="stSidebar"] hr { margin: 0.8rem 0 !important; }
/* restos do menu antigo por rádio (mantidos caso alguma tela ainda use) */
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label {
  width: 100% !important; margin: 0 !important; padding: 0.45rem 0.65rem !important;
  border-radius: 10px !important; border: none !important;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label > input + div,
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label > div:has(> input) { display: none !important; }
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label:hover { background: var(--panel-2) !important; }
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label:has(input:checked) { background: var(--accent-soft) !important; }

/* ── Tipografia ──────────────────────────────────────────────────────────── */
h1, h2, h3, h4 { font-family: var(--display) !important; color: var(--ink) !important; letter-spacing: -0.02em; }
h2 { font-size: 1.15rem !important; font-weight: 800 !important; margin-top: 1.1rem !important; }
p, label, .stMarkdown, [data-testid="stMarkdownContainer"],
[data-testid="stWidgetLabel"] { color: var(--ink) !important; font-family: var(--sans) !important; }
[data-testid="stCaptionContainer"] p { color: var(--ink-soft) !important; }
a { color: var(--accent) !important; }
hr { border-color: var(--line) !important; }
/* Ícones do Streamlit são ligaduras Material: não trocar a fonte deles. */
[data-testid="stIconMaterial"],
[data-testid="stExpanderToggleIcon"],
[data-testid="stExpander"] summary > span:first-child,
span[class*="material-symbols"],
span[class*="material-icons"] {
  font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons", sans-serif !important;
  font-feature-settings: "liga" !important;
  -webkit-font-feature-settings: "liga" !important;
  font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
  letter-spacing: normal !important; line-height: 1 !important; overflow: hidden;
}
[data-testid="stExpander"] [data-testid="stIconMaterial"] { color: var(--ink-faint) !important; }

.mh-page {
  display: flex; align-items: center; gap: 0.9rem;
  border: 1px solid var(--line); border-radius: 16px; margin-bottom: 1rem;
  padding: 0.85rem 1.1rem; background: linear-gradient(120deg, #f1f0ff 0%, #fff4ec 100%);
}
.mh-page-icon {
  width: 2.8rem; height: 2.8rem; border-radius: 12px; flex-shrink: 0; font-size: 1.35rem;
  display: flex; align-items: center; justify-content: center;
  background: var(--panel); border: 1px solid var(--line);
}
.mh-page-body { min-width: 0; }
.mh-page .eyebrow {
  font-size: 0.66rem; letter-spacing: 0.1em; font-weight: 700;
  text-transform: uppercase; color: var(--accent);
}
.mh-page h1 {
  font-family: var(--display) !important; font-size: 1.35rem !important; font-weight: 800 !important;
  color: var(--ink) !important; letter-spacing: -0.03em; margin: 0.05rem 0 0 !important; padding: 0 !important;
  line-height: 1.2 !important;
}
.mh-page .desc { margin-top: 0.2rem; color: var(--ink-soft); font-size: 0.88rem; max-width: 46rem; }

/* ── Botões ──────────────────────────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  background: var(--panel) !important; color: var(--ink) !important;
  border: 1px solid var(--line) !important; border-radius: 10px !important;
  font-family: var(--sans) !important; font-weight: 600 !important;
  padding: 0.5rem 1rem !important; box-shadow: none !important;
  transition: background 0.12s ease, border-color 0.12s ease, transform 0.12s ease !important;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  border-color: var(--accent) !important; color: var(--accent) !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"],
.stButton > button[data-testid="stBaseButton-primary"],
.stFormSubmitButton > button[kind="primaryFormSubmit"] {
  background: var(--accent) !important; color: #ffffff !important; border-color: var(--accent) !important;
}
.stButton > button[kind="primary"] p,
.stButton > button[data-testid="stBaseButton-primary"] p { color: #ffffff !important; }
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {
  background: var(--accent-hover) !important; color: #ffffff !important; transform: translateY(-1px) !important;
}
.stButton > button:active { transform: translateY(0) !important; }
[data-testid="stLinkButton"] > a, .stLinkButton > a {
  background: var(--panel) !important; color: var(--accent) !important;
  border: 1px solid var(--line) !important; border-radius: 10px !important;
  font-weight: 600 !important; text-decoration: none !important; box-shadow: none !important;
}
[data-testid="stLinkButton"] > a:hover, .stLinkButton > a:hover {
  border-color: var(--accent) !important; background: var(--accent-soft) !important;
}

/* ── Campos, abas, métricas, alertas ────────────────────────────────────── */
input, textarea, .stTextInput input, .stTextArea textarea,
.stSelectbox > div > div, [data-baseweb="select"] > div, [data-baseweb="base-input"] {
  background: var(--panel) !important; color: var(--ink) !important;
  border-color: var(--line) !important; border-radius: 10px !important;
}
.stTextInput input, .stTextArea textarea { font-family: var(--sans) !important; font-size: 0.95rem !important; }
.stTextInput input { min-height: 2.8rem !important; }
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color: var(--ink-faint) !important; }
.stTextInput input:focus, .stTextArea textarea:focus,
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(91, 91, 240, 0.15) !important;
}
button[data-baseweb="tab"] {
  padding: 0.5rem 0.85rem !important; font-family: var(--sans) !important;
  font-weight: 600 !important; color: var(--ink-soft) !important;
}
button[data-baseweb="tab"][aria-selected="true"] { color: var(--accent) !important; }
div[data-baseweb="tab-list"] { border-bottom-color: var(--line) !important; gap: 0.25rem !important; }
div[data-baseweb="tab-highlight"] { background: var(--accent) !important; height: 3px !important; border-radius: 3px !important; }
.stMetric, [data-testid="stMetric"] {
  background: var(--panel) !important; border: 1px solid var(--line) !important;
  border-radius: 12px !important; padding: 0.75rem 0.95rem !important; box-shadow: var(--shadow) !important;
}
[data-testid="stMetricLabel"] p {
  font-size: 0.7rem !important; font-weight: 700 !important; letter-spacing: 0.06em !important;
  text-transform: uppercase !important; color: var(--ink-faint) !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--display) !important; font-size: 1.3rem !important;
  color: var(--ink) !important; font-weight: 800 !important;
}
.stCheckbox label, .stRadio label { color: var(--ink) !important; }
div[data-testid="stAlert"] { border-radius: 12px !important; }
[data-testid="stExpander"] details {
  background: var(--panel) !important; border: 1px solid var(--line) !important; border-radius: 12px !important;
}
[data-testid="stExpander"] summary { font-weight: 600 !important; }
[data-testid="stExpander"] summary:hover { color: var(--accent) !important; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px !important; }
.stCodeBlock, pre, code, [data-testid="stCode"] { font-family: var(--mono) !important; }
img { border-radius: 10px; }

/* ── Blocos reutilizados pelas páginas ──────────────────────────────────── */
.mh-panel, .mh-osint-panel, .mh-urlscan, .mh-dork-workspace, .mh-dork-card, .mh-dork-side {
  border: 1px solid var(--line); border-radius: var(--radius); background: var(--panel);
  padding: 1rem 1.1rem; margin-bottom: 0.9rem; box-shadow: var(--shadow);
}
.mh-panel h3, .mh-osint-panel h3, .mh-urlscan h3, .mh-dork-card h3 {
  margin: 0 0 0.3rem 0 !important; font-size: 1rem !important; color: var(--ink) !important; font-weight: 700 !important;
}
.mh-panel p, .mh-panel .mh-muted, .mh-osint-panel .mh-osint-desc, .mh-urlscan p,
.mh-dork-card .mh-dork-desc, .mh-dork-side p {
  margin: 0 0 0.6rem 0 !important; color: var(--ink-soft) !important; font-size: 0.86rem !important; line-height: 1.45;
}
.mh-panel p:last-child { margin-bottom: 0 !important; }
.mh-dork-side h4 {
  margin: 0 0 0.35rem 0 !important; font-size: 0.7rem !important; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--accent) !important; font-weight: 700 !important;
}
.mh-quick-links a {
  display: inline-block; margin: 0.2rem 0.35rem 0.2rem 0; padding: 0.35rem 0.75rem;
  border-radius: 999px; border: 1px solid var(--line); background: var(--panel);
  font-size: 0.8rem; color: var(--accent) !important; text-decoration: none; font-weight: 600;
}
.mh-quick-links a:hover { border-color: var(--accent); background: var(--accent-soft); }
.mh-chip {
  display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.3rem 0.7rem;
  border-radius: 999px; font-size: 0.76rem; font-weight: 600;
  border: 1px solid var(--line); background: var(--panel); margin: 0.2rem 0.25rem 0.2rem 0; color: var(--ink-soft);
}
.mh-chip.on { border-color: transparent; background: var(--mint-soft); color: var(--mint); }
.mh-chip.off { color: var(--ink-faint); }

/* nav em chips (OSINT Avançado) */
div:has(.mh-osint-nav-mark) [data-testid="stHorizontalBlock"] { gap: 0.4rem !important; flex-wrap: wrap !important; row-gap: 0.45rem !important; }
div:has(.mh-osint-nav-mark) .stButton > button {
  border-radius: 999px !important; font-size: 0.8rem !important; font-weight: 600 !important;
  padding: 0.35rem 0.85rem !important; min-height: 2.1rem !important;
}
div:has(.mh-osint-nav-mark) .stButton > button[kind="primary"],
div:has(.mh-osint-nav-mark) .stButton > button[data-testid="stBaseButton-primary"] {
  background: var(--accent-soft) !important; border-color: transparent !important;
}
div:has(.mh-osint-nav-mark) .stButton > button[kind="primary"] p,
div:has(.mh-osint-nav-mark) .stButton > button[data-testid="stBaseButton-primary"] p { color: var(--accent) !important; }

/* heróis das páginas: faixa clara e compacta, sem sombra pesada */
.mh-tools-hero, .mh-premium-hero, .mh-learn-hero, .mh-dork-hero {
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--panel); box-shadow: var(--shadow);
  padding: 1.05rem 1.2rem; margin-bottom: 1rem;
}
.mh-dork-kicker {
  display: inline-block; font-size: 0.68rem; letter-spacing: 0.1em; font-weight: 700;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.3rem;
}
.mh-tools-hero h2, .mh-premium-hero h2, .mh-learn-hero h2, .mh-dork-hero h2 {
  margin: 0 !important; font-size: 1.35rem !important; font-weight: 800 !important;
  letter-spacing: -0.03em; color: var(--ink) !important; font-family: var(--display) !important;
}
.mh-tools-hero p, .mh-premium-hero p, .mh-learn-hero p, .mh-dork-hero p {
  margin: 0.4rem 0 0 0 !important; color: var(--ink-soft) !important;
  font-size: 0.9rem !important; max-width: 48rem; line-height: 1.45;
}
.mh-tools-stats { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.8rem 0 0 0; }
.mh-tools-stat {
  font-size: 0.74rem; font-weight: 600; padding: 0.25rem 0.6rem; border-radius: 999px;
  background: var(--accent-soft); color: var(--ink-soft);
}
.mh-tools-stat strong { color: var(--accent); font-weight: 800; }

.mh-tools-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 0.7rem; margin: 0.35rem 0 1.25rem 0; }
.mh-tool {
  border: 1px solid var(--line); border-radius: 12px; padding: 0.9rem 1rem 0.85rem;
  background: var(--panel); min-height: 140px; display: flex; flex-direction: column;
  transition: border-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
.mh-tool:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.mh-tool-top { display: flex; align-items: baseline; gap: 0.5rem; margin-bottom: 0.35rem; }
.mh-tool-num { font-family: var(--mono); font-size: 0.66rem; color: var(--accent-warm); font-weight: 600; min-width: 1.4rem; }
.mh-tool h4 { margin: 0 !important; font-size: 0.96rem !important; font-weight: 700 !important; line-height: 1.25 !important; }
.mh-tool p { margin: 0 0 0.75rem 0 !important; font-size: 0.8rem !important; color: var(--ink-soft) !important; line-height: 1.45; flex: 1; }
.mh-tool-foot {
  display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap;
  margin-top: auto; padding-top: 0.5rem; border-top: 1px solid var(--line-soft);
}
.mh-tool a { font-size: 0.78rem; color: var(--accent) !important; text-decoration: none; font-weight: 700; }
.mh-tool-hint { font-size: 0.7rem; color: var(--ink-faint); }
.mh-tools-section { margin: 1.2rem 0 0.5rem 0; display: flex; align-items: baseline; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap; }
.mh-tools-section h3 {
  margin: 0 !important; font-size: 0.74rem !important; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--accent) !important; font-weight: 800 !important;
}
.mh-tools-section span { font-size: 0.74rem; color: var(--ink-faint); }
.mh-tools-empty {
  border: 1px dashed var(--line); border-radius: 12px; padding: 1.2rem; text-align: center;
  color: var(--ink-soft); font-size: 0.85rem; margin: 0.75rem 0 1.25rem 0; background: var(--panel);
}

.mh-learn-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.65rem; margin: 0.25rem 0 1rem 0; }
@media (max-width: 820px) { .mh-learn-grid { grid-template-columns: 1fr; } }
a.mh-learn-card {
  display: grid; grid-template-columns: auto auto 1fr; grid-template-rows: auto auto;
  column-gap: 0.75rem; row-gap: 0.15rem; align-items: center;
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  padding: 0.8rem 0.95rem; text-decoration: none !important; min-height: 72px;
  transition: border-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
a.mh-learn-card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.mh-learn-num {
  grid-row: 1 / span 2; font-family: var(--mono); font-size: 0.7rem; font-weight: 600; color: var(--accent);
  background: var(--accent-soft); border-radius: 8px; min-width: 1.85rem; height: 1.85rem;
  display: inline-flex; align-items: center; justify-content: center;
}
.mh-learn-icon {
  grid-row: 1 / span 2; width: 2.3rem; height: 2.3rem; border-radius: 999px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 0.7rem; font-weight: 800; color: #ffffff; background: var(--c, var(--accent));
}
.mh-learn-url { grid-column: 3; font-size: 0.9rem; font-weight: 700; color: var(--ink) !important; line-height: 1.25; }
.mh-learn-desc { grid-column: 3; font-size: 0.78rem; color: var(--ink-soft) !important; line-height: 1.4; margin: 0; }

.mh-dork-summary {
  font-family: var(--mono); font-size: 0.78rem; color: var(--ink-soft); padding: 0.55rem 0.75rem;
  border: 1px dashed var(--line); border-radius: 10px; margin: 0.75rem 0 1rem 0; background: var(--panel);
}
.mh-dork-card .mh-dork-tags { margin-bottom: 0.7rem; }
.mh-dork-tag {
  display: inline-block; font-size: 0.66rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  padding: 0.18rem 0.5rem; border-radius: 999px; background: var(--accent-soft); color: var(--accent);
  margin: 0 0.3rem 0.3rem 0;
}
.mh-dork-query {
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem 0.65rem;
  padding: 0.6rem 0.7rem; margin-top: 0.45rem; border-radius: 10px; background: var(--panel-2);
}
.mh-dork-engine { font-size: 0.68rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.06em; color: var(--accent-warm); min-width: 5rem; }
.mh-dork-code { flex: 1 1 240px; font-family: var(--mono); font-size: 0.78rem; color: var(--ink); word-break: break-all; line-height: 1.4; }
.mh-dork-actions { display: flex; gap: 0.55rem; align-items: center; flex-wrap: wrap; }
.mh-dork-actions a { font-size: 0.76rem; color: var(--accent) !important; text-decoration: none; font-weight: 700; }
.mh-cat-label { font-size: 0.72rem; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent); margin: 1.2rem 0 0.5rem 0; }
[data-testid="stVerticalBlockBorderWrapper"]:has(.mh-scroll-mark) {
  border: 1px solid var(--line) !important; border-radius: 12px !important; background: var(--panel) !important;
  padding: 0.35rem 0.55rem 0.55rem !important; margin-bottom: 0.65rem !important;
}
.mh-foot { margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--line); font-size: 0.75rem; color: var(--ink-faint); }

/* ── Investigar: barra de comando ───────────────────────────────────────── */
.mh-hero {
  border-radius: 18px; padding: 1.15rem 1.35rem 1rem; margin-bottom: 0.85rem;
  background: linear-gradient(120deg, #5b5bf0 0%, #8b5cf6 55%, #f2703f 130%);
  color: #ffffff;
}
.mh-hero-top { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.mh-hero-eyebrow { font-size: 0.68rem; letter-spacing: 0.12em; font-weight: 700; text-transform: uppercase; color: rgba(255,255,255,0.8); }
.mh-hero-title {
  font-family: var(--display); font-size: 1.55rem !important; font-weight: 800;
  letter-spacing: -0.035em; margin: 0.15rem 0 0 !important; padding: 0 !important; color: #ffffff !important; line-height: 1.15;
}
.mh-hero-sub { color: rgba(255,255,255,0.9) !important; font-size: 0.9rem; line-height: 1.5; margin: 0.35rem 0 0 !important; max-width: 46rem; }
.mh-hero-stats { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.75rem; }
.mh-hero-stats span {
  font-size: 0.74rem; font-weight: 600; color: #ffffff; background: rgba(255,255,255,0.18);
  padding: 0.25rem 0.65rem; border-radius: 999px;
}
.mh-hero-stats strong { font-weight: 800; }
.mh-hero-badge { background: rgba(255,255,255,0.28) !important; }
/* chips de exemplo e buscas recentes abaixo da caixa */
.mh-hint-label { font-size: 0.72rem; font-weight: 700; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 0.08em; margin: 0.35rem 0 0.2rem; }
[class*="st-key-mh_chips"] [data-testid="stHorizontalBlock"] { gap: 0.4rem !important; flex-wrap: wrap !important; }
[class*="st-key-mh_chips"] [data-testid="stColumn"] { width: auto !important; flex: 0 0 auto !important; min-width: 0 !important; }
[class*="st-key-mh_chips"] .stButton > button {
  border-radius: 999px !important; padding: 0.22rem 0.8rem !important; min-height: 0 !important;
}
[class*="st-key-mh_chips"] .stButton > button p { font-size: 0.8rem !important; }

/* atalhos do painel inicial: cartões clicáveis */
[class*="st-key-mh_tiles"] .stButton > button {
  justify-content: flex-start !important; padding: 0.8rem 0.95rem !important; border-radius: 12px !important;
  box-shadow: var(--shadow) !important;
}
[class*="st-key-mh_tiles"] .stButton > button:hover { transform: translateY(-2px) !important; box-shadow: var(--shadow-hover) !important; }
[class*="st-key-mh_tiles"] .stButton > button p { font-weight: 700 !important; }
.stFormSubmitButton > button[kind="primaryFormSubmit"] p,
.stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"] p { color: #ffffff !important; }
.stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"] {
  background: var(--accent) !important; color: #ffffff !important; border-color: var(--accent) !important;
}
.stFormSubmitButton > button[kind="primaryFormSubmit"]:hover,
.stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"]:hover { background: var(--accent-hover) !important; }
[data-testid="stForm"] { padding: 0 !important; border: none !important; }

/* títulos de seção dentro das páginas (painel, atalhos) */
.mh-section {
  font-family: var(--display); font-size: 1.05rem; font-weight: 800; letter-spacing: -0.02em;
  color: var(--ink); margin: 1.1rem 0 0.5rem;
}

/* ── Dossiê ─────────────────────────────────────────────────────────────── */
.mh-fact {
  background: var(--panel); border: 1px solid var(--line); border-left: 4px solid var(--c, var(--ink-faint));
  border-radius: 10px; padding: 0.65rem 0.8rem; margin-bottom: 0.45rem;
}
.mh-fact-tag {
  display: inline-block; font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em;
  padding: 0.12rem 0.45rem; border-radius: 999px; margin-right: 0.5rem;
  color: var(--c, var(--ink-faint)); background: color-mix(in srgb, var(--c, #8a90a8) 14%, transparent);
}
.mh-fact-val { font-weight: 700; color: var(--ink); }
.mh-fact-detail { color: var(--ink-soft); font-size: 0.86rem; margin-top: 0.2rem; }
.mh-fact-src { color: var(--ink-faint); font-size: 0.74rem; margin-top: 0.3rem; }
.mh-fact-link { margin-top: 0.3rem; font-size: 0.76rem; word-break: break-all; }
.mh-idcard {
  display: flex; gap: 1rem; align-items: flex-start;
  background: var(--panel); border: 1px solid var(--line); border-radius: 16px;
  padding: 1rem 1.1rem; margin-bottom: 0.9rem; box-shadow: var(--shadow);
}
.mh-idcard-photo { width: 84px; height: 84px; border-radius: 14px; object-fit: cover; border: 1px solid var(--line); }
.mh-idcard-initial {
  width: 84px; height: 84px; border-radius: 14px; display: flex; align-items: center; justify-content: center;
  font-size: 2.3rem; font-weight: 800; color: #ffffff; background: linear-gradient(135deg, #5b5bf0, #f2703f);
}
.mh-idcard-body { flex: 1; min-width: 0; }
.mh-idcard-kicker { font-size: 0.66rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); font-weight: 800; }
.mh-idcard-name { font-size: 1.35rem; font-weight: 800; letter-spacing: -0.02em; margin: 0.1rem 0 0.5rem; color: var(--ink); }
.mh-idcard-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.35rem 1rem; }
.mh-idcard-row span { display: block; font-size: 0.66rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-faint); }
.mh-idcard-row div { font-size: 0.9rem; color: var(--ink); overflow-wrap: anywhere; }
.mh-flag {
  display: inline-block; background: var(--pink-soft); color: #c2185b; font-size: 0.72rem; font-weight: 700;
  padding: 0.18rem 0.6rem; border-radius: 999px; margin: 0.5rem 0.3rem 0 0;
}
.mh-tl-row { display: flex; gap: 0.7rem; padding: 0.4rem 0; border-bottom: 1px solid var(--line-soft); }
.mh-tl-date { min-width: 92px; font-weight: 800; color: var(--accent); font-size: 0.82rem; }
.mh-tl-src { color: var(--ink-faint); font-size: 0.74rem; }
.mh-soft { color: var(--ink-soft); font-size: 0.85rem; }
"""

# Tema escuro opcional: só redefine as variáveis e as superfícies nativas que
# o tema claro do Streamlit (config.toml) pintaria de branco.
_CSS_DARK = r"""
:root {
  --ink: #eef0fa;
  --ink-soft: #a3a9c4;
  --ink-faint: #7a809c;
  --paper: #0f1220;
  --panel: #181c2e;
  --panel-2: #1f2438;
  --sidebar: #131627;
  --sidebar-text: #c9cde0;
  --accent: #8b8bff;
  --accent-hover: #a3a3ff;
  --accent-soft: rgba(139, 139, 255, 0.16);
  --warm-soft: rgba(242, 112, 63, 0.16);
  --sun-soft: rgba(245, 180, 0, 0.16);
  --mint-soft: rgba(16, 178, 124, 0.18);
  --pink-soft: rgba(232, 72, 138, 0.18);
  --sky-soft: rgba(31, 155, 220, 0.18);
  --line: #2c3150;
  --line-soft: #242940;
  --shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-hover: 0 4px 14px rgba(139, 139, 255, 0.18);
}
.mh-page { background: linear-gradient(120deg, #1d1f3d 0%, #2a1f24 100%) !important; }
.mh-flag { color: #ff8fbf !important; }
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"],
.stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"] { background: #5b5bf0 !important; border-color: #5b5bf0 !important; }
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] { background: var(--accent-soft) !important; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p { color: var(--ink) !important; }
.stCodeBlock pre, [data-testid="stCode"] pre, code { background: var(--panel-2) !important; color: var(--ink) !important; }
[data-baseweb="popover"] ul, [data-baseweb="popover"] li, [data-baseweb="menu"] { background: var(--panel) !important; color: var(--ink) !important; }
[data-baseweb="popover"] li:hover { background: var(--panel-2) !important; }
div[data-testid="stAlert"] p { color: var(--ink) !important; }
[data-testid="stSpinner"] p, [data-testid="stHeader"] * { color: var(--ink-soft) !important; }
[data-testid="stSidebarCollapseButton"] *, [data-testid="stSidebarCollapsedControl"] * { color: var(--ink-soft) !important; }
"""

# Estado do tema: a chave do toggle vale na sessão; ?tema=escuro guarda a
# preferência na URL para sobreviver ao recarregar a página.
if "tema_escuro" not in st.session_state:
    st.session_state["tema_escuro"] = st.query_params.get("tema") == "escuro"
_TEMA_CSS = _CSS + (_CSS_DARK if st.session_state["tema_escuro"] else "")

# st.html com só <style> vai para o container de eventos: não ocupa espaço
# na página e, como não fica em iframe, o CSS vale para o app inteiro.
st.html("<style>" + _TEMA_CSS + "</style>")


def page_header(eyebrow: str, title: str, desc: str = ""):
    # Mesmo formato da faixa do Investigar, em versão suave: ícone da página,
    # rótulo, título e uma linha de descrição.
    icone = NAV_ICON.get(globals().get("page", ""), "🔎")
    desc_html = f'<div class="desc">{desc}</div>' if desc else ""
    st.html(
        f'<div class="mh-page"><div class="mh-page-icon">{icone}</div><div class="mh-page-body">'
        f'<div class="eyebrow">{eyebrow}</div><h1>{title}</h1>{desc_html}</div></div>'
    )


# ── Navegação ────────────────────────────────────────────────────────────────
NAV_OPTIONS = ["Investigar", "Diretório", "Limpar Nome", "Monitoramento", "Dark web", "Histórico"]
NAV_ICON = {
    "Investigar": "🔎", "Diretório": "🧭", "Limpar Nome": "🧹", "Monitoramento": "🔔",
    "Dark web": "🧅", "Histórico": "🕘",
}
NAV_SHORT = {
    "Investigar": "Investigar", "Diretório": "Diretório de fontes", "Limpar Nome": "Limpar Nome",
    "Monitoramento": "Monitoramento", "Dark web": "Dark web (Robin)", "Histórico": "Histórico",
}
NAV_GROUPS = [
    ("Consultas", ["Investigar", "Diretório"]),
    ("Serviços", ["Limpar Nome", "Monitoramento", "Dark web"]),
    ("Sistema", ["Histórico"]),
]


with st.sidebar:
    st.html(
        """
        <div class="mh-brand">
          <div class="mark">Painel de consultas</div>
          <div class="mh-brand-row">
            <div class="mh-brand-badge">🔎</div>
            <div class="name">Mr.Holmes</div>
          </div>
          <div class="tag">Um dado entra, o dossiê sai</div>
        </div>
        """
    )
    apply_pending_navigation(st.session_state, NAV_OPTIONS, default="Investigar")
    page = st.session_state.get("nav_page", "Investigar")

    for _grupo, _ids in NAV_GROUPS:
        st.html(f'<div class="mh-nav-group">{_grupo}</div>')
        for _pid in _ids:
            if st.button(
                f"{NAV_ICON.get(_pid, '•')}  {NAV_SHORT.get(_pid, _pid)}",
                key=f"nav_btn_{_pid}", use_container_width=True,
                type="primary" if page == _pid else "secondary",
            ):
                queue_navigation(st.session_state, _pid)
                st.rerun()

    st.markdown("---")
    sync_llm_keys_from_session()
    try:
        from Core.Support.Robin.engine import tool_status as _ts
        _prov = _ts().get("providers") or {}
    except Exception:
        _prov = {}
    st.caption(
        "IA · "
        f"OpenAI {'●' if _prov.get('openai') else '○'} · "
        f"Claude {'●' if _prov.get('anthropic') else '○'}"
    )

    def _salvar_tema() -> None:
        if st.session_state.get("tema_escuro"):
            st.query_params["tema"] = "escuro"
        elif "tema" in st.query_params:
            del st.query_params["tema"]

    st.toggle("🌙 Tema escuro", key="tema_escuro", on_change=_salvar_tema)
    st.caption("Uso profissional · finalidade legítima (LGPD)")


# ── Investigar ───────────────────────────────────────────────────────────────
if page == "Investigar":
    display_investigar()


# ── Diretório ────────────────────────────────────────────────────────────────
elif page == "Diretório":
    page_header("Fontes", "Diretório de fontes",
                "O que cada fonte entrega, quanto custa e o link já pesquisado no seu dado.")
    display_diretorio()


# ── Limpar Nome ──────────────────────────────────────────────────────────────
elif page == "Limpar Nome":
    page_header("Serviço", "Limpar Nome",
                "Do relatório do birô até a baixa: classifica, escreve o pedido certo e acompanha os prazos.")
    display_limpar_nome()


# ── Monitoramento ────────────────────────────────────────────────────────────
elif page == "Monitoramento":
    page_header("Vigilância", "Monitoramento",
                "Reinvestiga alvos e avisa quando surge algo novo.")
    display_monitoramento()


# ── Dark web (Robin) ─────────────────────────────────────────────────────────
elif page == "Dark web":
    page_header("Ferramenta", "Dark web (Robin)",
                "Busca na rede Tor e monta um relatório com IA.")
    display_robin_workspace()


# ── Histórico ────────────────────────────────────────────────────────────────
elif page == "Histórico":
    page_header("Registro", "Histórico", "Dossiês salvos, para reabrir ou comparar.")
    display_historico()
