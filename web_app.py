"""Mr.Holmes Web — OSINT Investigation Console"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from external_services_ui import display_external_services, display_services_for_page
from osint_premium import apply_pending_navigation
from osint_premium_ui import display_osint_premium
from robin_workspace import sync_llm_keys_from_session
from holmes_ui import display_investigar, display_historico, display_monitoramento

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
import streamlit.components.v1 as _components

_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Sora:wght@600;700;800&display=swap');
:root {
  --ink: #eef3f9;
  --ink-soft: #98a6b8;
  --paper: #0b0f15;
  --panel: #161d27;
  --panel-2: #121822;
  --sidebar: #0a0e14;
  --sidebar-text: #c8d2df;
  --accent: #5fd6bd;
  --accent-hover: #7fe6d0;
  --accent-warm: #ffa87c;
  --line: #26313f;
  --line-soft: #1b232e;
  --ok: #5fd6bd;
  --shadow: 0 12px 32px rgba(0, 0, 0, 0.38);
  --radius: 12px;
  --mono: 'IBM Plex Mono', ui-monospace, monospace;
  --sans: 'IBM Plex Sans', system-ui, sans-serif;
  --display: 'Sora', 'IBM Plex Sans', system-ui, sans-serif;
}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background:
    radial-gradient(1200px 620px at 88% -8%, rgba(95, 214, 189, 0.10), transparent 55%),
    radial-gradient(900px 520px at -5% 105%, rgba(255, 168, 124, 0.06), transparent 52%),
    var(--paper) !important;
  color: var(--ink) !important;
  font-family: var(--sans) !important;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
.main, [data-testid="stMain"] {
  background: transparent !important;
}
[data-testid="stMain"] .block-container {
  padding-top: 1.35rem !important;
  padding-bottom: 2.5rem !important;
  max-width: 1100px !important;
}
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stToolbar"] { color: var(--ink-soft) !important; }
[data-testid="stSidebar"], [data-testid="stSidebarContent"],
section[data-testid="stSidebar"] > div {
  background: var(--sidebar) !important;
  border-right: 1px solid #1e2936 !important;
}
[data-testid="stSidebar"] * { color: var(--sidebar-text) !important; font-family: var(--sans) !important; }
[data-testid="stSidebar"] .stRadio label {
  padding: 0.4rem 0.6rem !important;
  border-radius: 6px !important;
  margin-bottom: 2px !important;
  font-size: 0.9rem !important;
}
[data-testid="stSidebar"] .stRadio label:hover { background: #1a2330 !important; }
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + div,
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
  background: rgba(111, 212, 190, 0.12) !important;
  border: 1px solid rgba(111, 212, 190, 0.35) !important;
}
.mh-nav-group {
  font-family: var(--mono); font-size: 0.65rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: #6fd4be !important;
  margin: 0.85rem 0 0.35rem 0; opacity: 0.95;
}
.mh-panel {
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  padding: 1rem 1.1rem; margin-bottom: 0.9rem;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.22);
}
.mh-panel h3 {
  margin: 0 0 0.35rem 0 !important; font-size: 0.95rem !important;
  color: var(--ink) !important; font-weight: 650 !important;
}
.mh-panel p, .mh-panel .mh-muted {
  margin: 0; color: var(--ink-soft); font-size: 0.84rem; line-height: 1.4;
}
.mh-quick-links a {
  display: inline-block; margin: 0.2rem 0.35rem 0.2rem 0;
  padding: 0.35rem 0.65rem; border-radius: 999px;
  border: 1px solid var(--line); background: var(--panel-2);
  font-family: var(--mono); font-size: 0.72rem; color: var(--accent) !important;
  text-decoration: none; font-weight: 600;
}
.mh-quick-links a:hover { border-color: rgba(111,212,190,.45); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  color: #f1f5f9 !important;
}
.mh-brand { padding: 0.25rem 0 1.25rem 0; border-bottom: 1px solid #243041; margin-bottom: 1rem; }
.mh-brand .mark {
  font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--accent) !important; margin-bottom: 0.35rem;
}
.mh-brand .name {
  font-family: var(--display); font-size: 1.45rem; font-weight: 800; color: #f8fafc !important;
  letter-spacing: -0.03em; line-height: 1.15;
  background: linear-gradient(92deg, #f8fafc 30%, var(--accent));
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.mh-brand .tag { font-size: 0.78rem; color: #8b9aab !important; margin-top: 0.35rem; }
.mh-brand-row { display: flex; align-items: center; gap: 0.6rem; margin-top: 0.15rem; }
.mh-brand-badge {
  width: 2.15rem; height: 2.15rem; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 1.1rem;
  background: linear-gradient(150deg, rgba(95, 214, 189, 0.22), rgba(95, 214, 189, 0.05));
  border: 1px solid rgba(95, 214, 189, 0.35);
  box-shadow: 0 0 22px rgba(95, 214, 189, 0.16);
}
.mh-page { margin-bottom: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid var(--line); }
.mh-page .eyebrow {
  font-family: var(--mono); font-size: 0.72rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.35rem;
}
.mh-page h1 {
  font-family: var(--display) !important;
  font-size: 1.85rem !important; font-weight: 800 !important; color: var(--ink) !important;
  letter-spacing: -0.035em; margin: 0 !important; padding: 0 !important; line-height: 1.2 !important;
}
.mh-page .desc { margin-top: 0.4rem; color: var(--ink-soft); font-size: 0.95rem; max-width: 40rem; }
h1, h2, h3 { font-family: var(--display) !important; color: var(--ink) !important; letter-spacing: -0.02em; }
h2 { font-size: 1.15rem !important; font-weight: 700 !important; margin-top: 1.25rem !important; }
p, label, .stMarkdown, [data-testid="stMarkdownContainer"],
[data-testid="stWidgetLabel"] { color: var(--ink) !important; font-family: var(--sans) !important; }
/* Expander/chevron icons are Material ligatures (_arrow_right). Do not put font-family on `span`. */
[data-testid="stIconMaterial"],
[data-testid="stExpanderToggleIcon"],
[data-testid="stExpander"] summary > span:first-child,
span[class*="material-symbols"],
span[class*="material-icons"] {
  font-family: "Material Symbols Rounded", "Material Symbols Outlined",
    "Material Icons", sans-serif !important;
  font-feature-settings: "liga" !important;
  -webkit-font-feature-settings: "liga" !important;
  font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
  letter-spacing: normal !important;
  line-height: 1 !important;
  overflow: hidden;
}
[data-testid="stExpander"] [data-testid="stIconMaterial"] {
  color: var(--ink-soft) !important;
}
.stButton > button {
  background: linear-gradient(180deg, var(--accent-hover), var(--accent)) !important;
  color: #06231d !important; border: none !important;
  border-radius: 8px !important; font-family: var(--sans) !important; font-weight: 650 !important;
  padding: 0.55rem 1.05rem !important;
  box-shadow: 0 6px 16px rgba(95, 214, 189, 0.16) !important;
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease !important;
}
.stButton > button:hover {
  filter: brightness(1.04) !important; transform: translateY(-1px) !important;
  box-shadow: 0 9px 22px rgba(95, 214, 189, 0.26) !important; color: #06231d !important;
}
.stButton > button:active { transform: translateY(0) !important; }
/* link_button (cards externos) */
[data-testid="stLinkButton"] > a,
.stLinkButton > a {
  background: var(--accent) !important; color: #0d1218 !important;
  border: none !important; border-radius: 8px !important;
  font-weight: 700 !important; text-decoration: none !important;
  box-shadow: none !important;
}
[data-testid="stLinkButton"] > a:hover,
.stLinkButton > a:hover { background: var(--accent-hover) !important; color: #0d1218 !important; }
/* cards nativos com borda */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--panel-2) !important;
  border-color: var(--line) !important;
  border-radius: 12px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
  border-color: rgba(111, 212, 190, 0.4) !important;
}
/* abas mais legíveis */
button[data-baseweb="tab"] { padding: 0.55rem 0.85rem !important; }
input, textarea, .stTextInput input, .stTextArea textarea,
.stSelectbox > div > div, [data-baseweb="select"] > div,
[data-baseweb="base-input"] {
  background: var(--panel-2) !important; color: var(--ink) !important;
  border-color: var(--line) !important; border-radius: 6px !important;
}
.stTextInput input, .stTextArea textarea { font-family: var(--mono) !important; font-size: 0.9rem !important; }
/* anel de foco no campo ativo — dá acabamento e mostra onde você está digitando */
.stTextInput input:focus, .stTextArea textarea:focus,
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(95, 214, 189, 0.18) !important;
}
.stMetric, [data-testid="stMetric"] {
  background: linear-gradient(165deg, #1a222d 0%, var(--panel) 60%) !important;
  border: 1px solid var(--line) !important;
  border-radius: 10px !important; padding: 0.85rem 1rem !important;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.20) !important;
}
[data-testid="stMetricLabel"] {
  font-family: var(--mono) !important; font-size: 0.68rem !important;
  letter-spacing: 0.08em !important; text-transform: uppercase !important; color: var(--ink-soft) !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--mono) !important; font-size: 1.15rem !important;
  color: var(--ink) !important; font-weight: 500 !important;
}
button[data-baseweb="tab"] { font-family: var(--sans) !important; font-weight: 600 !important; color: var(--ink-soft) !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--accent) !important; }
div[data-baseweb="tab-list"] { border-bottom-color: var(--line) !important; gap: 0.25rem !important; }
div[data-baseweb="tab-highlight"] { background: var(--accent) !important; height: 3px !important; border-radius: 3px !important; }
.stCheckbox label, .stRadio label { color: var(--ink) !important; }
.stSlider [data-baseweb="slider"] div[role="slider"] { background: var(--accent) !important; }
.stAlert { background: var(--panel) !important; }
.mh-chip {
  display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.35rem 0.7rem;
  border-radius: 999px; font-family: var(--mono); font-size: 0.72rem;
  border: 1px solid var(--line); background: var(--panel); margin: 0.2rem 0.25rem 0.2rem 0;
  color: var(--ink-soft);
}
.mh-chip.on { border-color: rgba(111, 212, 190, 0.45); background: rgba(111, 212, 190, 0.12); color: var(--ok); }
.mh-chip.off { color: var(--ink-soft); }
/* Nav OSINT: botões-chip (sobrescreve o estilo global de botão) */
div:has(.mh-osint-nav-mark) [data-testid="stHorizontalBlock"] {
  gap: 0.4rem !important; flex-wrap: wrap !important; row-gap: 0.45rem !important;
}
div:has(.mh-osint-nav-mark) .stButton > button {
  border-radius: 999px !important;
  font-family: var(--mono) !important;
  font-size: 0.74rem !important;
  font-weight: 500 !important;
  padding: 0.4rem 0.85rem !important;
  border: 1px solid var(--line) !important;
  background: var(--panel) !important;
  color: var(--ink-soft) !important;
  box-shadow: none !important;
  min-height: 2.1rem !important;
}
div:has(.mh-osint-nav-mark) .stButton > button:hover {
  border-color: rgba(111, 212, 190, 0.45) !important;
  color: var(--ink) !important;
  background: #243140 !important;
}
div:has(.mh-osint-nav-mark) .stButton > button[kind="primary"],
div:has(.mh-osint-nav-mark) .stButton > button[data-testid="baseButton-primary"] {
  border-color: rgba(111, 212, 190, 0.55) !important;
  background: rgba(111, 212, 190, 0.16) !important;
  color: var(--ok) !important;
}
.mh-osint-panel {
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  padding: 1.1rem 1.2rem; margin: 0.75rem 0 1rem 0;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);
}
.mh-osint-panel h3 {
  margin: 0 0 0.35rem 0 !important; font-size: 1.1rem !important;
  color: var(--ink) !important; font-weight: 600 !important;
}
.mh-osint-panel .mh-osint-desc {
  margin: 0 0 0.85rem 0 !important; font-size: 0.86rem !important;
  color: var(--ink-soft) !important; line-height: 1.45;
}
.mh-tool {
  border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.05rem 0.95rem;
  background: linear-gradient(165deg, #1e2834 0%, var(--panel) 55%);
  margin: 0; min-height: 152px; display: flex; flex-direction: column;
  transition: border-color 0.18s ease, transform 0.18s ease, background 0.18s ease;
}
.mh-tool:hover {
  border-color: rgba(111, 212, 190, 0.42);
  transform: translateY(-2px);
  background: linear-gradient(165deg, #243140 0%, var(--panel) 55%);
}
.mh-tool-top {
  display: flex; align-items: baseline; gap: 0.55rem; margin-bottom: 0.4rem;
}
.mh-tool-num {
  font-family: var(--mono); font-size: 0.65rem; letter-spacing: 0.08em;
  color: var(--accent-warm); font-weight: 500; flex-shrink: 0; min-width: 1.4rem;
}
.mh-tool h4 {
  margin: 0 !important; font-size: 0.98rem !important; color: var(--ink) !important;
  font-weight: 600 !important; letter-spacing: -0.02em; line-height: 1.25 !important;
}
.mh-tool p {
  margin: 0 0 0.85rem 0 !important; font-size: 0.8rem !important;
  color: var(--ink-soft) !important; line-height: 1.45; flex: 1;
}
.mh-tool-foot {
  display: flex; align-items: center; justify-content: space-between;
  gap: 0.5rem; flex-wrap: wrap; margin-top: auto;
  padding-top: 0.55rem; border-top: 1px solid rgba(51, 67, 85, 0.7);
}
.mh-tool a {
  font-family: var(--mono); font-size: 0.72rem; color: var(--accent) !important;
  text-decoration: none; font-weight: 600; letter-spacing: 0.02em;
}
.mh-tool a:hover { color: var(--accent-hover) !important; }
.mh-tool-hint {
  font-family: var(--mono); font-size: 0.65rem; color: var(--ink-soft);
  letter-spacing: 0.02em;
}
.mh-tools-hero {
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  padding: 1.15rem 1.25rem; margin-bottom: 1rem;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
}
.mh-tools-hero .mh-dork-kicker {
  font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.35rem;
}
.mh-tools-hero h2 {
  margin: 0 !important; font-size: 1.45rem !important; font-weight: 700 !important;
  letter-spacing: -0.03em; color: var(--ink) !important; font-family: var(--mono) !important;
}
.mh-tools-hero p {
  margin: 0.5rem 0 0 0 !important; color: var(--ink-soft) !important;
  font-size: 0.9rem !important; max-width: 48rem; line-height: 1.45;
}
.mh-tools-stats {
  display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.9rem 0 0 0;
}
.mh-tools-stat {
  font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.04em;
  padding: 0.28rem 0.55rem; border-radius: 999px;
  border: 1px solid var(--line); background: var(--panel-2); color: var(--ink-soft);
}
.mh-tools-stat strong { color: var(--accent); font-weight: 600; }
.mh-tools-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 0.75rem; margin: 0.35rem 0 1.35rem 0;
}
.mh-tools-section {
  margin: 1.35rem 0 0.55rem 0; display: flex; align-items: baseline;
  justify-content: space-between; gap: 0.75rem; flex-wrap: wrap;
}
.mh-tools-section h3 {
  margin: 0 !important; font-family: var(--mono) !important;
  font-size: 0.72rem !important; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--accent) !important; font-weight: 600 !important;
}
.mh-tools-section span {
  font-family: var(--mono); font-size: 0.7rem; color: var(--ink-soft);
}
.mh-tools-empty {
  border: 1px dashed var(--line); border-radius: 10px; padding: 1.25rem;
  text-align: center; color: var(--ink-soft); font-family: var(--mono);
  font-size: 0.8rem; margin: 0.75rem 0 1.25rem 0; background: var(--panel-2);
}
.mh-urlscan {
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  padding: 1rem 1.15rem; margin: 1.5rem 0 0.5rem 0;
}
.mh-urlscan h3 {
  margin: 0 0 0.25rem 0 !important; font-size: 1rem !important;
  color: var(--ink) !important; font-weight: 650 !important;
}
.mh-urlscan p {
  margin: 0 0 0.85rem 0 !important; font-size: 0.82rem !important;
  color: var(--ink-soft) !important; line-height: 1.4;
}
.mh-premium-hero {
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  padding: 1.2rem 1.3rem; margin-bottom: 1.1rem;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
  position: relative; overflow: hidden;
}
.mh-premium-hero::before {
  content: ""; position: absolute; inset: 0;
  background:
    radial-gradient(ellipse at 88% 8%, rgba(111, 212, 190, 0.16), transparent 46%),
    radial-gradient(ellipse at 8% 92%, rgba(255, 155, 106, 0.10), transparent 42%);
  pointer-events: none;
}
.mh-premium-hero > * { position: relative; }
.mh-premium-hero .mh-dork-kicker {
  font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.35rem;
}
.mh-premium-hero h2 {
  margin: 0 !important; font-size: 1.45rem !important; font-weight: 700 !important;
  letter-spacing: -0.03em; color: var(--ink) !important; font-family: var(--mono) !important;
}
.mh-premium-hero p {
  margin: 0.5rem 0 0 0 !important; color: var(--ink-soft) !important;
  font-size: 0.9rem !important; max-width: 48rem; line-height: 1.45;
}
.mh-learn-hero {
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  padding: 1.2rem 1.3rem; margin-bottom: 1.1rem;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
  position: relative; overflow: hidden;
}
.mh-learn-hero::before {
  content: ""; position: absolute; inset: 0;
  background:
    radial-gradient(ellipse at 90% 10%, rgba(111, 212, 190, 0.12), transparent 45%),
    radial-gradient(ellipse at 5% 90%, rgba(255, 155, 106, 0.08), transparent 40%);
  pointer-events: none;
}
.mh-learn-hero > * { position: relative; }
.mh-learn-hero .mh-dork-kicker {
  font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.35rem;
}
.mh-learn-hero h2 {
  margin: 0 !important; font-size: 1.45rem !important; font-weight: 700 !important;
  letter-spacing: -0.03em; color: var(--ink) !important; font-family: var(--mono) !important;
}
.mh-learn-hero p {
  margin: 0.5rem 0 0 0 !important; color: var(--ink-soft) !important;
  font-size: 0.9rem !important; max-width: 48rem; line-height: 1.45;
}
.mh-learn-grid {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.7rem; margin: 0.25rem 0 1rem 0;
}
@media (max-width: 820px) {
  .mh-learn-grid { grid-template-columns: 1fr; }
}
a.mh-learn-card {
  display: grid; grid-template-columns: auto auto 1fr; grid-template-rows: auto auto;
  column-gap: 0.75rem; row-gap: 0.2rem; align-items: center;
  border: 1px solid var(--line); border-radius: 12px;
  background: linear-gradient(165deg, #1e2834 0%, var(--panel) 60%);
  padding: 0.85rem 1rem; text-decoration: none !important;
  transition: border-color 0.18s ease, transform 0.18s ease, background 0.18s ease;
  min-height: 78px;
}
a.mh-learn-card:hover {
  border-color: rgba(111, 212, 190, 0.45);
  transform: translateY(-2px);
  background: linear-gradient(165deg, #243140 0%, var(--panel) 60%);
}
.mh-learn-num {
  grid-row: 1 / span 2; align-self: center;
  font-family: var(--mono); font-size: 0.68rem; font-weight: 600;
  letter-spacing: 0.04em; color: var(--ink);
  background: #0f3d32; border: 1px solid rgba(111, 212, 190, 0.35);
  border-radius: 6px; min-width: 1.85rem; height: 1.85rem;
  display: inline-flex; align-items: center; justify-content: center;
}
.mh-learn-icon {
  grid-row: 1 / span 2; width: 2.35rem; height: 2.35rem; border-radius: 999px;
  display: inline-flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 0.68rem; font-weight: 700;
  color: #0d1218; background: var(--c, var(--accent)); letter-spacing: -0.02em;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--c, var(--accent)) 22%, transparent);
}
.mh-learn-url {
  grid-column: 3; font-family: var(--mono); font-size: 0.88rem; font-weight: 600;
  color: var(--accent) !important; letter-spacing: -0.01em; line-height: 1.25;
}
.mh-learn-desc {
  grid-column: 3; font-size: 0.78rem; color: var(--ink-soft) !important;
  line-height: 1.4; margin: 0;
}
.mh-dork-workspace {
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  padding: 1.15rem 1.25rem; margin-bottom: 1rem;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
}
.mh-dork-hero .mh-dork-kicker {
  font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.35rem;
}
.mh-dork-hero h2 {
  margin: 0 !important; font-size: 1.55rem !important; font-weight: 700 !important;
  letter-spacing: -0.03em; color: var(--ink) !important; font-family: var(--mono) !important;
}
.mh-dork-hero p {
  margin: 0.5rem 0 0 0 !important; color: var(--ink-soft) !important;
  font-size: 0.9rem !important; max-width: 46rem; line-height: 1.45;
}
.mh-dork-summary {
  font-family: var(--mono); font-size: 0.78rem; color: var(--ink-soft);
  padding: 0.55rem 0.75rem; border: 1px dashed var(--line); border-radius: 8px;
  margin: 0.75rem 0 1rem 0; background: var(--panel-2);
}
.mh-dork-side {
  border: 1px solid var(--line); border-radius: 10px; background: var(--panel);
  padding: 0.85rem 0.95rem; margin-bottom: 0.75rem;
}
.mh-dork-side h4 {
  margin: 0 0 0.35rem 0 !important; font-family: var(--mono) !important;
  font-size: 0.68rem !important; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--accent) !important; font-weight: 600 !important;
}
.mh-dork-side p {
  margin: 0 0 0.55rem 0 !important; font-size: 0.75rem !important;
  color: var(--ink-soft) !important; line-height: 1.35;
}
/* Scroll nos painéis de filtro (containers com height do Streamlit) */
[data-testid="stVerticalBlockBorderWrapper"]:has(.mh-scroll-mark) {
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
  background: var(--panel) !important;
  padding: 0.35rem 0.55rem 0.55rem !important;
  margin-bottom: 0.65rem !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(.mh-scroll-mark) > div {
  scrollbar-width: auto;
  scrollbar-color: #c5ced9 #1e2936;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(.mh-scroll-mark) > div::-webkit-scrollbar {
  width: 10px;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(.mh-scroll-mark) > div::-webkit-scrollbar-track {
  background: #1e2936;
  border-radius: 8px;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(.mh-scroll-mark) > div::-webkit-scrollbar-thumb {
  background: #8b9aab;
  border-radius: 8px;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(.mh-scroll-mark) > div::-webkit-scrollbar-thumb:hover {
  background: #c5ced9;
}
.mh-dork-card {
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  padding: 1.1rem 1.2rem; margin-bottom: 0.95rem;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.25);
}
.mh-dork-card h3 {
  margin: 0 0 0.35rem 0 !important; font-size: 1.12rem !important;
  color: var(--ink) !important; font-weight: 700 !important; letter-spacing: -0.02em;
}
.mh-dork-card .mh-dork-desc {
  margin: 0 0 0.65rem 0 !important; font-size: 0.86rem !important;
  color: var(--ink-soft) !important; line-height: 1.45;
}
.mh-dork-card .mh-dork-tags { margin-bottom: 0.75rem; }
.mh-dork-tag {
  display: inline-block; font-family: var(--mono); font-size: 0.65rem;
  letter-spacing: 0.04em; text-transform: uppercase; padding: 0.2rem 0.5rem;
  border-radius: 999px; border: 1px solid rgba(111, 212, 190, 0.35);
  background: rgba(111, 212, 190, 0.12); color: var(--accent);
  margin: 0 0.3rem 0.3rem 0;
}
.mh-dork-query {
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem 0.65rem;
  padding: 0.65rem 0.7rem; margin-top: 0.45rem;
  border: 1px solid var(--line); border-radius: 8px; background: var(--panel-2);
}
.mh-dork-engine {
  font-family: var(--mono); font-size: 0.68rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.06em; color: var(--accent-warm);
  min-width: 5rem;
}
.mh-dork-code {
  flex: 1 1 240px; font-family: var(--mono); font-size: 0.78rem;
  color: var(--ink); background: transparent; border: none;
  border-radius: 0; padding: 0; word-break: break-all; line-height: 1.4;
}
.mh-dork-actions { display: flex; gap: 0.55rem; align-items: center; flex-wrap: wrap; }
.mh-dork-actions a {
  font-family: var(--mono); font-size: 0.72rem; color: var(--accent) !important;
  text-decoration: none; font-weight: 600;
}
.mh-cat-label {
  font-family: var(--mono); font-size: 0.72rem; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--accent); margin: 1.25rem 0 0.55rem 0;
}
.stCodeBlock, pre, code,
[data-testid="stCode"] {
  font-family: var(--mono) !important;
  background: var(--panel-2) !important;
  color: var(--ink) !important;
}
img { border-radius: 8px; border: 1px solid var(--line); }
.mh-foot {
  margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--line);
  font-family: var(--mono); font-size: 0.72rem; color: #7a8796; letter-spacing: 0.04em;
}
div[data-testid="stAlert"] { border-radius: 8px !important; background: var(--panel) !important; }
hr { border-color: var(--line) !important; }
a { color: var(--accent) !important; }

/* ── Menu lateral: vira NAVEGAÇÃO, não formulário ──────────────────────────── */
[data-testid="stSidebar"] .stRadio [role="radiogroup"] { gap: 3px !important; }
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label {
  width: 100% !important; margin: 0 !important;
  padding: 0.5rem 0.7rem !important; border-radius: 9px !important;
  border: 1px solid transparent !important;
  transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease !important;
}
/* esconde a bolinha do radio — vira item de menu */
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label > div:first-child {
  display: none !important;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label:hover {
  background: #131b25 !important;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label:has(input:checked) {
  background: rgba(95, 214, 189, 0.12) !important;
  border-color: rgba(95, 214, 189, 0.32) !important;
  box-shadow: inset 3px 0 0 var(--accent) !important;
}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] > label:has(input:checked) p {
  color: #eafff8 !important; font-weight: 600 !important;
}

/* ── Hero de comando (tela Investigar) ─────────────────────────────────────── */
.mh-hero {
  position: relative; overflow: hidden;
  border: 1px solid var(--line); border-radius: 16px;
  background: linear-gradient(150deg, #18212d 0%, #0e141c 72%);
  padding: 1.7rem 1.9rem; margin-bottom: 1.15rem;
  box-shadow: var(--shadow);
}
.mh-hero::after {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(640px 220px at 92% -25%, rgba(95, 214, 189, 0.20), transparent 60%);
}
.mh-hero > * { position: relative; }
.mh-hero-eyebrow {
  font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.2em;
  text-transform: uppercase; color: var(--accent);
}
.mh-hero-title {
  font-family: var(--display); font-size: 2.15rem !important; font-weight: 800;
  letter-spacing: -0.04em; margin: 0.4rem 0 0 !important; color: var(--ink); line-height: 1.05;
}
.mh-hero-sub {
  color: var(--ink-soft); font-size: 0.96rem; line-height: 1.55;
  margin: 0.6rem 0 0 !important; max-width: 47rem;
}
.mh-hero-stats { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 1.1rem; }
.mh-hero-stats span {
  font-family: var(--mono); font-size: 0.72rem; color: var(--ink-soft);
  border: 1px solid var(--line); background: rgba(0, 0, 0, 0.22);
  padding: 0.32rem 0.65rem; border-radius: 999px;
}
.mh-hero-stats strong { color: var(--accent); font-weight: 600; }
.mh-hero-badge { color: var(--accent-warm) !important; border-color: rgba(255, 168, 124, 0.3) !important; }

/* Caixa de busca principal: maior e com mais presença */
.stTextInput input { min-height: 2.9rem !important; }
"""

_components.html(
    f"""<script>
    (function() {{
      const doc = window.parent.document;
      let s = doc.getElementById('mh-theme');
      if (!s) {{
        s = doc.createElement('style');
        s.id = 'mh-theme';
        doc.head.appendChild(s);
      }}
      s.textContent = {_CSS!r};
    }})();
    </script>""",
    height=0,
    width=0,
)


def page_header(eyebrow: str, title: str, desc: str = ""):
    desc_html = f'<div class="desc">{desc}</div>' if desc else ""
    st.html(
        f'<div class="mh-page"><div class="eyebrow">{eyebrow}</div>'
        f'<h1>{title}</h1>{desc_html}</div>'
    )


def ensure_dork_tokens():
    from Core.Support.DorkWorkbench import empty_tokens
    if "dork_tokens" not in st.session_state:
        st.session_state.dork_tokens = empty_tokens()
    return st.session_state.dork_tokens


def send_to_dorks(**kwargs):
    tokens = ensure_dork_tokens()
    for key, val in kwargs.items():
        if val:
            tokens[key] = str(val).strip()
            st.session_state[f"dork_tok_{key}"] = tokens[key]
    st.session_state.dork_tokens = tokens
    st.session_state.dork_navigate_hint = True
    st.success("Tokens enviados ao Dorks Workbench — abra o menu **Dorks** na sidebar.")


# ── Navigation (lista única, rótulos claros — sem menus aninhados) ────────────
# page_id interno permanece estável para o resto do app
NAV_OPTIONS = [
    "Investigar",
    "Monitoramento",
    "OSINT Premium",
    "Telefone",
    "Email",
    "Domínio",
    "Dorks",
    "OSINT Avançado",
    "Leaks",
    "Rede",
    "Gráfico",
    "Ferramentas",
    "Serviços Externos",
    "Aprenda",
    "Histórico",
    "Sobre",
]
NAV_LABEL = {
    "Investigar": "🔎 INVESTIGAR — caixa única",
    "Monitoramento": "🔔 Monitoramento",
    "OSINT Premium": "★ OSINT Premium",
    "Telefone": "1 · Telefone",
    "Email": "2 · Email",
    "Domínio": "3 · Domínio",
    "Dorks": "4 · Dorks Google",
    "OSINT Avançado": "5 · Username / Social",
    "Leaks": "6 · Leaks",
    "Rede": "7 · Rede / IP",
    "Gráfico": "8 · Grafo",
    "Ferramentas": "9 · Catálogo (GitHub)",
    "Serviços Externos": "10 · Links web",
    "Aprenda": "11 · Aprenda",
    "Histórico": "12 · Histórico",
    "Sobre": "13 · Sobre",
}


def _nav_label(page_id: str) -> str:
    return NAV_LABEL.get(page_id, page_id)


with st.sidebar:
    st.html(
        """
        <div class="mh-brand">
          <div class="mark">OSINT Console</div>
          <div class="mh-brand-row">
            <div class="mh-brand-badge">🔎</div>
            <div class="name">Mr.Holmes</div>
          </div>
          <div class="tag">OSINT Premium · hub unificado</div>
        </div>
        """
    )
    st.caption("Comece por **Investigar** · os itens 1–13 são o modo manual/avançado")
    apply_pending_navigation(st.session_state, NAV_OPTIONS, default="Investigar")
    page = st.radio(
        "Menu",
        NAV_OPTIONS,
        format_func=_nav_label,
        key="nav_page",
        label_visibility="collapsed",
    )
    st.markdown("---")
    sync_llm_keys_from_session()
    _prov = None
    try:
        from Core.Support.Robin.engine import tool_status as _ts
        _prov = _ts().get("providers") or {}
    except Exception:
        _prov = {}
    st.caption(
        "LLM · "
        f"OpenAI {'●' if _prov.get('openai') else '○'} · "
        f"Claude {'●' if _prov.get('anthropic') else '○'} · "
        "cole a chave OpenAI na aba Investigar"
    )
    st.caption("Educacional · alvos autorizados")


# ── Investigar (caixa única — motor holmes/) ─────────────────────────────────
if page == "Investigar":
    display_investigar()


# ── Monitoramento ────────────────────────────────────────────────────────────
elif page == "Monitoramento":
    page_header("Vigilância", "Monitoramento",
                "Reinvestiga alvos e avisa quando surge algo novo.")
    display_monitoramento()


# ── OSINT Premium ────────────────────────────────────────────────────────────
elif page == "OSINT Premium":
    page_header(
        "Hub",
        "OSINT Premium",
        "Digite o nome na aba Investigar. A OpenAI busca na web e o Holmes consulta as fontes locais. "
        "Educacional · alvos autorizados.",
    )
    display_osint_premium()


# ── Telefone ─────────────────────────────────────────────────────────────────
elif page == "Telefone":
    from external_services import get_category as _get_ext_cat
    _phone_n = len((_get_ext_cat("telefone") or {}).get("services") or [])
    page_header(
        "Lookup",
        "Telefone",
        "Passo 1: analisar o número localmente. Passo 2: abrir fontes externas (Web/GitHub).",
    )

    tab_analise, tab_fontes = st.tabs(
        ["1 · Analisar número", f"2 · Fontes externas ({_phone_n})"]
    )

    with tab_analise:
        st.markdown(
            '<div class="mh-panel"><h3>Consulta local</h3>'
            '<p class="mh-muted">libphonenumber + DDD BR. Não consulta bases pagas automaticamente.</p></div>',
            unsafe_allow_html=True,
        )
        c_in, c_btn = st.columns([3, 1])
        with c_in:
            phone = st.text_input(
                "Número (código do país + DDD)",
                placeholder="5511999999999",
                label_visibility="collapsed",
                key="phone_input_main",
            )
        with c_btn:
            st.write("")
            run_phone = st.button("Investigar", type="primary", use_container_width=True)

        if run_phone and phone:
            with st.spinner("Analisando número…"):
                try:
                    from Core.Support.Phone.Numbers import get_geo_from_ddd
                    from Core.Support.History import save_search
                    import phonenumbers as pn
                    from phonenumbers import carrier, geocoder, timezone

                    digits = "".join(c for c in phone.strip() if c.isdigit())
                    parsed = pn.parse("+" + digits, "BR")
                    pais = geocoder.country_name_for_number(parsed, "pt") or geocoder.country_name_for_number(parsed, "en") or "N/A"
                    area = geocoder.description_for_number(parsed, "pt") or geocoder.description_for_number(parsed, "en") or "N/A"
                    operadora = carrier.name_for_number(parsed, "pt") or carrier.name_for_number(parsed, "en") or "N/A"

                    c1, c2, c3 = st.columns(3)
                    c1.metric("País", pais)
                    c1.metric("Área", area)
                    c2.metric("Operadora", operadora or "—")
                    c2.metric("Região", pn.region_code_for_country_code(parsed.country_code))
                    c3.metric("Internacional", pn.format_number(parsed, pn.PhoneNumberFormat.INTERNATIONAL))
                    tz = timezone.time_zones_for_number(parsed)
                    c3.metric("Fuso", tz[0] if tz else "—")

                    e164 = pn.format_number(parsed, pn.PhoneNumberFormat.E164)
                    cc = str(parsed.country_code)
                    local = e164[1:]
                    if local.startswith(cc):
                        local = local[len(cc):]
                    ddd = local[:2]
                    geo = get_geo_from_ddd(ddd)

                    if geo:
                        st.success(f"DDD {ddd} → {geo['city']}/{geo['state']}")
                        st.map(data={"lat": [geo["lat"]], "lon": [geo["lon"]]}, zoom=10)

                    st.markdown("##### Atalhos rápidos")
                    ql = (
                        f'<div class="mh-quick-links">'
                        f'<a href="https://free-lookup.net/{digits}" target="_blank">Free-Lookup</a>'
                        f'<a href="https://whosenumber.info/{digits}" target="_blank">WhoseNumber</a>'
                        f'<a href="https://spamcalls.net/en/number/{digits}" target="_blank">SpamCalls</a>'
                        f'<a href="https://www.google.com/search?q=%22{digits}%22" target="_blank">Google</a>'
                        f'<a href="https://yandex.com/search/?text=%22{digits}%22" target="_blank">Yandex</a>'
                        f'<a href="https://wa.me/{digits}" target="_blank">WhatsApp</a>'
                        f'<a href="https://www.truecaller.com/search/br/{digits}" target="_blank">Truecaller</a>'
                        f'<a href="https://phonebook.cz/" target="_blank">Phonebook.cz</a>'
                        f"</div>"
                    )
                    st.markdown(ql, unsafe_allow_html=True)
                    st.caption("HTTP/acesso ao site não confirma que o número está cadastrado.")

                    sites_found = 8
                    save_search("phone", digits, country=pais, area=area, carrier=operadora, sites_found=sites_found)
                    st.session_state["last_phone"] = digits
                except Exception as e:
                    st.error(str(e))

        if st.session_state.get("last_phone"):
            st.caption(f"Último número: `{st.session_state['last_phone']}`")
            if st.button("Enviar para Dorks Workbench", key="phone_to_dorks"):
                send_to_dorks(PHONE=st.session_state["last_phone"])

    with tab_fontes:
        st.markdown("### Portfólio de telefone")
        st.caption(
            "GitHub (PhoneInfoga, Ignorant…) e sites (Sync.me, Truecaller…). "
            "Truecaller não tem API de busca reversa OSINT — o Holmes não raspa o site; o atalho abre a página oficial."
        )
        display_services_for_page("telefone", heading="Tools & serviços de número")


# ── Email ────────────────────────────────────────────────────────────────────
elif page == "Email":
    page_header("Lookup", "Email", "Validação de formato, MX, Gravatar e menções em pastes públicos.")
    st.caption(
        "Paralelo gratuito (parcial) à busca de email em breaches do OSINT Leak: "
        "MX, Gravatar, Holehe (equivalente in-app ao Epieos para contas públicas) e pastes. "
        "Epieos não é raspado. Leaks pagos só entram se `OSINTLEAK_API_KEY` estiver no Railway."
    )
    email = st.text_input("Endereço", placeholder="exemplo@dominio.com")
    if st.button("Investigar", type="primary") and email:
        with st.spinner("Analisando email…"):
            try:
                from Core.Support.EmailSearch import buscar_email
                from Core.Support.History import save_search
                r = buscar_email(email)
                c1, c2 = st.columns(2)
                c1.metric("Formato", "válido" if r["valido"] else "inválido")
                c1.metric("MX", "sim" if r.get("mx", {}).get("has_mx") else "não")
                c2.metric("Gravatar", "sim" if r.get("gravatar", {}).get("has_gravatar") else "não")
                c2.metric("Domínio", r.get("dominio", "—"))
                if r.get("pastes"):
                    st.warning(f"{len(r['pastes'])} menções em pastes públicos")
                    for p in r["pastes"][:5]:
                        st.markdown(f"- [{p['url']}]({p['url']}) — {p['title'][:80]}")
                for a in r.get("alertas", []):
                    st.info(a)
                save_search("email", email.strip().lower(), country=r.get("dominio", ""), sites_found=r.get("total_fontes", 0))
                st.caption(
                    "Contas públicas: use **OSINT Avançado → Holehe** (não é necessário abrir o Epieos). "
                    "Breaches pagos: menu **Leaks** se `OSINTLEAK_API_KEY` estiver configurada."
                )
                st.session_state["last_email"] = email.strip().lower()
                st.session_state["last_email_domain"] = (r.get("dominio") or "").strip()
            except Exception as e:
                st.error(str(e))
    if st.session_state.get("last_email"):
        st.caption(f"Último email: `{st.session_state['last_email']}`")
        if st.button("Enviar para Dorks Workbench", key="email_to_dorks"):
            em = st.session_state["last_email"]
            dom = st.session_state.get("last_email_domain") or ""
            org = dom.split(".")[0] if dom else ""
            send_to_dorks(EMAIL=em, TARGET_DOMAIN=dom, ORG_NAME=org)
    display_services_for_page("email", heading="Fontes de email, pessoas e leaks")


# ── Domínio ──────────────────────────────────────────────────────────────────
elif page == "Domínio":
    page_header("Lookup", "Domínio", "Resolução IP, GeoIP, registros DNS, cabeçalhos HTTP e atalhos ViewDNS.")
    st.caption(
        "Paralelo gratuito aos tools WHOIS / IP Intelligence do OSINT Leak: "
        "GeoIP (ip-api) + links ViewDNS (WHOIS, histórico de IP, reverse IP)."
    )
    domain = st.text_input("Domínio", placeholder="exemplo.com")
    if st.button("Investigar", type="primary") and domain:
        with st.spinner("Investigando domínio…"):
            try:
                from Core.Support.DomainSearch import buscar_dominio
                from Core.Support.History import save_search
                r = buscar_dominio(domain)
                c1, c2, c3 = st.columns(3)
                c1.metric("IP", r.get("ip") or "—")
                c1.metric("HTTP", r.get("headers", {}).get("status", "—"))
                c2.metric("País", r.get("geo", {}).get("country", "—"))
                c2.metric("Cidade", r.get("geo", {}).get("city", "—"))
                c3.metric("ISP", r.get("geo", {}).get("isp", "—"))
                c3.metric("Server", r.get("headers", {}).get("server", "—"))
                if r.get("geo", {}).get("lat"):
                    st.map(data={"lat": [r["geo"]["lat"]], "lon": [r["geo"]["lon"]]}, zoom=8)
                st.subheader("DNS")
                for rtype, records in r.get("dns", {}).items():
                    if records:
                        st.markdown(f"`{rtype}`  {', '.join(records[:3])}")
                st.subheader("ViewDNS (WHOIS / IP)")
                cols = st.columns(5)
                for i, (name, link) in enumerate(r.get("viewdns_links", {}).items()):
                    cols[i % 5].markdown(f"[{name}]({link})")
                save_search(
                    "domain", r.get("dominio", domain),
                    country=r.get("geo", {}).get("country", ""),
                    area=r.get("geo", {}).get("city", ""),
                    carrier=r.get("geo", {}).get("isp", ""),
                )
                st.session_state["last_domain"] = (r.get("dominio") or domain).strip()
                st.session_state["last_domain_ip"] = (r.get("ip") or "").strip()
            except Exception as e:
                st.error(str(e))
    if st.session_state.get("last_domain"):
        st.caption(f"Último domínio: `{st.session_state['last_domain']}`")
        if st.button("Enviar para Dorks Workbench", key="domain_to_dorks"):
            dom = st.session_state["last_domain"]
            org = dom.split(".")[0] if dom else ""
            send_to_dorks(TARGET_DOMAIN=dom, ORG_NAME=org, IP=st.session_state.get("last_domain_ip", ""))
    display_services_for_page("dominio", heading="Fontes de domínio, DNS e recon")


# ── OSINT Avançado ───────────────────────────────────────────────────────────
elif page == "OSINT Avançado":
    page_header(
        "Suite",
        "OSINT Avançado",
        "Holehe, WhatsMyName, Maigret, theHarvester, subdomínios, dnstwist, httpx e SpiderFoot.",
    )
    from Core.Support.OsintTools import tool_status
    from Core.Support.History import save_search

    status = tool_status()
    OSINT_NAV = [
        ("holehe", "Holehe", "holehe"),
        ("whatsmyname", "WhatsMyName", None),
        ("maigret", "Maigret", "maigret"),
        ("theHarvester", "theHarvester", "theHarvester"),
        ("subdomains", "Subdomínios", None),
        ("dnstwist", "dnstwist", "dnstwist"),
        ("httpx", "httpx", "httpx"),
        ("spiderfoot", "SpiderFoot", "spiderfoot"),
    ]

    def _osint_ready(tool_id: str, status_key):
        if tool_id == "subdomains":
            return bool(status.get("subfinder") or status.get("amass"))
        if tool_id == "maigret":
            return bool(status.get("maigret") or status.get("sherlock"))
        if tool_id == "whatsmyname":
            return True
        return bool(status.get(status_key)) if status_key else False

    if "osint_adv_tool" not in st.session_state:
        st.session_state.osint_adv_tool = "holehe"

    st.html('<div class="mh-osint-nav-mark" aria-hidden="true"></div>')
    nav_cols = st.columns(len(OSINT_NAV))
    for i, (tid, label, sk) in enumerate(OSINT_NAV):
        mark = "●" if _osint_ready(tid, sk) else "○"
        active = st.session_state.osint_adv_tool == tid
        with nav_cols[i]:
            if st.button(
                f"{mark} {label}",
                key=f"osint_nav_{tid}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                st.session_state.osint_adv_tool = tid
                st.rerun()

    st.caption("Clique em um chip para abrir a ferramenta · ● instalado · ○ fallback ou pendente")

    # Status auxiliar (não são abas — só indicadores)
    aux = [
        ("subfinder", "Subfinder"),
        ("amass", "Amass"),
        ("sherlock", "Sherlock"),
    ]
    aux_html = "".join(
        f'<span class="mh-chip {"on" if status.get(k) else "off"}">'
        f'{"●" if status.get(k) else "○"} {label}</span>'
        for k, label in aux
    )
    st.html(f'<div style="margin:0.15rem 0 0.85rem 0">{aux_html}</div>')

    selected = st.session_state.osint_adv_tool
    selected_label = next(label for tid, label, _ in OSINT_NAV if tid == selected)

    if selected == "holehe":
        st.html(
            f'<div class="mh-osint-panel"><h3>{selected_label}</h3>'
            '<p class="mh-osint-desc">Descobre em quais serviços um email possui conta. '
            "Equivalente in-app ao Epieos (contas públicas). O Holmes não raspa epieos.com. "
            "Complemento à busca de email em leaks (OSINT Leak API, se houver chave).</p></div>"
        )
        email_h = st.text_input("Email", placeholder="usuario@dominio.com", key="holehe_email")
        if st.button("Executar Holehe", key="btn_holehe") and email_h:
            with st.spinner("Consultando serviços…"):
                from Core.Support.OsintTools import run_holehe
                r = run_holehe(email_h)
                if r.get("install"):
                    st.warning(r.get("error", ""))
                    st.code(r["install"])
                elif r.get("sites"):
                    st.success(f"{len(r['sites'])} indícios")
                    for s in r["sites"]:
                        st.write(f"- {s}")
                    save_search("holehe", email_h, sites_found=len(r["sites"]))
                else:
                    st.info("Nenhuma conta pública encontrada.")
                    if r.get("raw"):
                        with st.expander("Saída bruta"):
                            st.code(r["raw"])

    elif selected == "whatsmyname":
        st.html(
            f'<div class="mh-osint-panel"><h3>{selected_label}</h3>'
            '<p class="mh-osint-desc">Checagem nativa com a lista aberta '
            '<a href="https://github.com/WebBreacher/WhatsMyName">WebBreacher/WhatsMyName</a> '
            "(CC BY-SA 4.0). O Holmes consulta as URLs públicas — não abre whatsmyname.app "
            "e não usa APIs não oficiais.</p></div>"
        )
        user_w = st.text_input("Username", placeholder="joaosilva", key="wmn_user")
        max_w = st.slider("Limite de sites", 20, 120, 60, key="wmn_n")
        if st.button("Executar WhatsMyName", key="btn_wmn") and user_w:
            with st.spinner("Checando perfis públicos…"):
                from Core.Support.WhatsMyName import check_username
                r = check_username(user_w, max_sites=max_w)
                if r.get("profiles"):
                    st.success(f"{len(r['profiles'])} perfis · {r.get('checked', 0)} sites checados")
                    for p in r["profiles"]:
                        st.markdown(
                            f"- **{p.get('site', '')}** — [{p.get('url', '')}]({p.get('url', '')})"
                        )
                    save_search("username", user_w, sites_found=len(r["profiles"]))
                else:
                    st.info(r.get("error") or "Nenhum perfil encontrado nesta amostra de sites.")
                    st.caption("Sites com captcha/Cloudflare agressivo são pulados de propósito.")

    elif selected == "maigret":
        st.html(
            f'<div class="mh-osint-panel"><h3>{selected_label}</h3>'
            '<p class="mh-osint-desc">Username em redes e plataformas (Maigret; Sherlock se disponível). '
            "Lista diferente do chip WhatsMyName. Equivalente open-source ao UserHunter do OSINT Leak — sem cota paga.</p></div>"
        )
        user_m = st.text_input("Username", placeholder="joaosilva", key="maigret_user")
        max_sites = st.slider("Limite de sites", 20, 100, 40, key="maigret_n")
        if st.button("Executar Maigret", key="btn_maigret") and user_m:
            with st.spinner("Buscando perfis…"):
                from Core.Support.OsintTools import run_maigret
                r = run_maigret(user_m, max_sites=max_sites)
                if r.get("install"):
                    st.warning(r.get("error", ""))
                    st.code(r["install"])
                elif r.get("profiles"):
                    st.success(f"{len(r['profiles'])} perfis · {r.get('tool')}")
                    for p in r["profiles"]:
                        st.markdown(
                            f"- **{p.get('site', '')}** — [{p.get('url', '')}]({p.get('url', '')})"
                        )
                    save_search("username", user_m, sites_found=len(r["profiles"]))
                else:
                    st.info("Nenhum perfil encontrado.")
                    if r.get("raw"):
                        with st.expander("Saída bruta"):
                            st.code(r["raw"])

    elif selected == "theHarvester":
        st.html(
            f'<div class="mh-osint-panel"><h3>{selected_label}</h3>'
            '<p class="mh-osint-desc">Emails e hosts associados a um domínio.</p></div>'
        )
        dom_h = st.text_input("Domínio", placeholder="exemplo.com", key="harvester_dom")
        if st.button("Executar theHarvester", key="btn_harvester") and dom_h:
            with st.spinner("Coletando…"):
                from Core.Support.OsintTools import run_theharvester
                r = run_theharvester(dom_h)
                if r.get("note"):
                    st.info(r["note"])
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader(f"Emails ({len(r.get('emails', []))})")
                    for e in r.get("emails", []) or ["—"]:
                        st.write(e if e != "—" else "Nenhum")
                with c2:
                    st.subheader(f"Hosts ({len(r.get('hosts', []))})")
                    for h in r.get("hosts", []) or ["—"]:
                        st.write(h if h != "—" else "Nenhum")
                save_search(
                    "harvester",
                    r.get("domain", dom_h),
                    sites_found=len(r.get("emails", [])) + len(r.get("hosts", [])),
                )
                st.caption(f"Fonte: {r.get('tool', '—')}")

    elif selected == "subdomains":
        st.html(
            f'<div class="mh-osint-panel"><h3>{selected_label}</h3>'
            '<p class="mh-osint-desc">Enumeração via Subfinder/Amass ou brute DNS local.</p></div>'
        )
        dom_s = st.text_input("Domínio", placeholder="exemplo.com", key="sub_dom")
        if st.button("Enumerar", key="btn_subs") and dom_s:
            with st.spinner("Enumerando…"):
                from Core.Support.OsintTools import run_subdomains
                r = run_subdomains(dom_s)
                if r.get("note"):
                    st.info(r["note"])
                st.success(f"{r.get('count', 0)} · {r.get('tool')}")
                for s in r.get("subdomains", []):
                    st.code(s, language=None)
                save_search("subdomains", r.get("domain", dom_s), sites_found=r.get("count", 0))

    elif selected == "dnstwist":
        st.html(
            f'<div class="mh-osint-panel"><h3>{selected_label}</h3>'
            '<p class="mh-osint-desc">Variações de domínio (typosquatting).</p></div>'
        )
        dom_t = st.text_input("Domínio", placeholder="exemplo.com", key="twist_dom")
        if st.button("Gerar variações", key="btn_twist") and dom_t:
            with st.spinner("Gerando…"):
                from Core.Support.OsintTools import run_dnstwist
                r = run_dnstwist(dom_t)
                if r.get("note"):
                    st.info(r["note"])
                domains = r.get("domains", [])
                st.success(f"{len(domains)} · {r.get('tool')}")
                for d in domains[:80]:
                    st.markdown(
                        f"`{d.get('domain')}` — {d.get('fuzzer', '')} — {d.get('dns_a', '')}"
                    )
                save_search("dnstwist", r.get("domain", dom_t), sites_found=len(domains))

    elif selected == "httpx":
        st.html(
            f'<div class="mh-osint-panel"><h3>{selected_label}</h3>'
            '<p class="mh-osint-desc">Verifica quais hosts/URLs respondem HTTP.</p></div>'
        )
        targets = st.text_area(
            "Alvos (um por linha)",
            placeholder="exemplo.com\napi.exemplo.com",
            key="httpx_targets",
            height=120,
        )
        if st.button("Checar", key="btn_httpx"):
            lines = [l.strip() for l in targets.splitlines() if l.strip()]
            if lines:
                with st.spinner("Verificando…"):
                    from Core.Support.OsintTools import run_httpx
                    r = run_httpx(lines)
                    if r.get("note"):
                        st.info(r["note"])
                    alive = r.get("alive", [])
                    st.success(f"{len(alive)} / {r.get('total', 0)} · {r.get('tool')}")
                    for a in alive:
                        st.write(f"- {a}")
                    if not alive:
                        st.warning("Nenhum host respondeu.")
                    save_search("httpx", lines[0], sites_found=len(alive))

    elif selected == "spiderfoot":
        from Core.Support.OsintTools import spiderfoot_info
        info = spiderfoot_info()
        st.html(
            f'<div class="mh-osint-panel"><h3>{selected_label}</h3>'
            '<p class="mh-osint-desc">Recon automatizado pesado — roda como serviço separado.</p></div>'
        )
        st.code(info["install"])
        st.markdown(f"[Documentação]({info['docs']}) · UI local: [{info['url']}]({info['url']})")
        alvo_sf = st.text_input("Alvo para copiar", key="sf_target")
        if alvo_sf:
            st.code(alvo_sf)
    display_services_for_page("osint", heading="Fontes de pessoas, imagem e utilitários")


# ── Rede ─────────────────────────────────────────────────────────────────────
elif page == "Rede":
    page_header("Utilitários", "Rede", "Ping, portas, uptime, DNS reverso e provedor de hospedagem.")
    tool = st.selectbox("Operação", ["Ping", "Scan de portas", "Site online", "IP reverso", "Meu IP", "Hospedagem"])

    if tool == "Ping":
        host = st.text_input("Host", "google.com")
        if st.button("Executar ping"):
            from Core.Support.NetTools import ping_host
            r = ping_host(host)
            if r["success"]:
                st.success(f"{host} responde")
                a, b, c = st.columns(3)
                a.metric("Médio", f"{r['avg_time']:.1f} ms")
                b.metric("Mín", f"{r['min_time']:.1f} ms")
                c.metric("Máx", f"{r['max_time']:.1f} ms")
                st.code(r["output"][-400:])
            else:
                st.error(r.get("error", "Host inacessível"))

    elif tool == "Scan de portas":
        host = st.text_input("Host", "localhost")
        if st.button("Escanear"):
            from Core.Support.NetTools import scan_ports, COMMON_PORTS
            with st.spinner("Escaneando…"):
                results = scan_ports(host)
                if results:
                    st.success(f"{len(results)} portas abertas")
                    for r in results:
                        st.write(f"Porta **{r['port']}** · {r['service']}")
                else:
                    st.info("Nenhuma porta comum aberta.")
                st.caption("Verificadas: " + ", ".join(str(p) for p in COMMON_PORTS))

    elif tool == "Site online":
        url = st.text_input("URL", "https://google.com")
        if st.button("Verificar"):
            from Core.Support.NetTools import check_uptime
            r = check_uptime(url)
            if r["online"]:
                st.success(f"Online · HTTP {r['status_code']}")
                a, b = st.columns(2)
                a.metric("Latência", f"{r['response_time']}s")
                b.metric("Server", r.get("server", "—"))
            else:
                st.error(r.get("error", "Sem resposta"))

    elif tool == "IP reverso":
        ip = st.text_input("IP", "8.8.8.8")
        if st.button("Resolver"):
            from Core.Support.NetTools import reverse_ip
            r = reverse_ip(ip)
            if r["found"]:
                st.success(f"{ip} → {r['hostname']}")
            else:
                st.info("Sem PTR.")

    elif tool == "Meu IP":
        if st.button("Obter IP público"):
            from Core.Support.NetTools import get_my_ip
            r = get_my_ip()
            st.metric("IP público", r["ip"])
            st.caption(r["source"])

    elif tool == "Hospedagem":
        domain = st.text_input("Domínio", "google.com")
        if st.button("Identificar"):
            from Core.Support.NetTools import lookup_hosting
            r = lookup_hosting(domain)
            a, b, c = st.columns(3)
            a.metric("IP", r.get("ip", "—"))
            b.metric("ISP", r.get("isp", "—"))
            c.metric("País", r.get("country", "—"))
            st.write(f"ORG: {r.get('org', '—')}")
            st.markdown(f"[HostingChecker]({r.get('hosting_link', '#')}) · [WHOIS]({r.get('whois_link', '#')})")


# ── Gráfico ──────────────────────────────────────────────────────────────────
elif page == "Gráfico":
    page_header("Análise", "Gráfico de relacionamentos", "Monte entidades e conexões no estilo link analysis.")
    if "graph_nodes" not in st.session_state:
        st.session_state.graph_nodes = []

    col1, col2 = st.columns([2, 1], gap="large")
    with col2:
        st.subheader("Entidade")
        tipo_map = {"Telefone": "Phone", "Email": "Email", "Domínio": "Domain", "IP": "IP", "Pessoa": "Person"}
        entity_type_pt = st.selectbox("Tipo", list(tipo_map.keys()))
        entity_type = tipo_map[entity_type_pt]
        placeholders = {
            "Telefone": "5511999999999", "Email": "usuario@dominio.com",
            "Domínio": "exemplo.com", "IP": "8.8.8.8", "Pessoa": "Nome Sobrenome",
        }
        entity_value = st.text_input("Valor", placeholder=placeholders[entity_type_pt])
        entity_label = st.text_input("Rótulo (opcional)", "")
        if st.button("Adicionar", use_container_width=True) and entity_value:
            node = {
                "id": entity_value,
                "label": entity_label or entity_value,
                "type": entity_type,
                "color": {"Phone": "#2563eb", "Email": "#dc2626", "Domain": "#059669", "IP": "#d97706", "Person": "#7c3aed"}[entity_type],
            }
            if node not in st.session_state.graph_nodes:
                st.session_state.graph_nodes.append(node)
                st.rerun()

        if st.session_state.graph_nodes:
            st.subheader("Conexão")
            if len(st.session_state.graph_nodes) >= 2:
                labels = [n["label"] for n in st.session_state.graph_nodes]
                src = st.selectbox("De", labels)
                dst = st.selectbox("Para", labels, index=min(1, len(labels) - 1))
                edge_label = st.text_input("Relação", "relacionado a")
                if st.button("Ligar", use_container_width=True):
                    if "graph_edges" not in st.session_state:
                        st.session_state.graph_edges = []
                    st.session_state.graph_edges.append({"from": src, "to": dst, "label": edge_label})
                    st.rerun()
            if st.button("Limpar gráfico", use_container_width=True):
                st.session_state.graph_nodes = []
                st.session_state.graph_edges = []
                st.rerun()

    with col1:
        if st.session_state.graph_nodes:
            try:
                import networkx as nx
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                from io import BytesIO

                G = nx.Graph()
                colors_map = {"Phone": "#2563eb", "Email": "#dc2626", "Domain": "#059669", "IP": "#d97706", "Person": "#7c3aed"}
                for node in st.session_state.graph_nodes:
                    G.add_node(node["label"], color=colors_map.get(node["type"], "#64748b"))
                if "graph_edges" in st.session_state:
                    for edge in st.session_state.graph_edges:
                        if edge["from"] in G.nodes and edge["to"] in G.nodes:
                            G.add_edge(edge["from"], edge["to"], label=edge["label"])

                bg = "#f8fafc"
                fig, ax = plt.subplots(figsize=(10, 6), facecolor=bg)
                pos = nx.spring_layout(G, k=2.2, iterations=50, seed=42)
                node_colors = [G.nodes[n].get("color", "#64748b") for n in G.nodes]
                nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=1600,
                                       alpha=1.0, ax=ax, edgecolors="#0f172a", linewidths=1.5)
                nx.draw_networkx_edges(G, pos, edge_color="#64748b", width=2, alpha=0.85, ax=ax)
                for node, (x, y) in pos.items():
                    ax.text(x, y + 0.1, node, fontsize=10, ha="center", va="bottom",
                            fontweight="bold", color="#0f172a",
                            bbox=dict(facecolor="#ffffff", alpha=0.95, edgecolor="#cbd5e1", boxstyle="round,pad=0.35"))
                if G.edges:
                    edge_labels = nx.get_edge_attributes(G, "label")
                    if edge_labels:
                        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color="#475569", font_size=8, ax=ax)
                ax.set_facecolor(bg)
                ax.axis("off")
                fig.tight_layout(pad=0.5)
                buf = BytesIO()
                plt.savefig(buf, format="png", dpi=140, bbox_inches="tight", facecolor=bg)
                plt.close()
                buf.seek(0)
                st.image(buf, use_container_width=True)
                st.caption("Telefone · Email · Domínio · IP · Pessoa")
            except Exception as e:
                st.error(str(e))
        else:
            st.info("Adicione entidades no painel à direita.")


# ── Dorks Workbench ──────────────────────────────────────────────────────────
elif page == "Dorks":
    import importlib
    import html as _html
    import Core.Support.DorkWorkbench as _dw
    _dw = importlib.reload(_dw)

    TOKEN_KEYS = _dw.TOKEN_KEYS
    TOKEN_LABELS_PT = getattr(
        _dw,
        "TOKEN_LABELS_PT",
        {
            "TARGET_DOMAIN": "Domínio alvo",
            "ORG_NAME": "Organização",
            "USERNAME": "Usuário",
            "EMAIL": "Email",
            "IP": "IP",
            "ASN": "ASN",
            "PHONE": "Telefone",
        },
    )
    empty_tokens = _dw.empty_tokens
    filter_techniques = _dw.filter_techniques
    humanize_goal = _dw.humanize_goal
    list_engines = _dw.list_engines
    list_goals = _dw.list_goals
    load_catalog = _dw.load_catalog
    localize_technique = getattr(
        _dw,
        "localize_technique",
        lambda tech: {
            "title": tech.get("title") or "",
            "description": tech.get("description") or "",
        },
    )
    resolve_queries = _dw.resolve_queries
    source_label = getattr(_dw, "source_label", lambda s: s or "")

    ensure_dork_tokens()
    for key in TOKEN_KEYS:
        sk = f"dork_tok_{key}"
        if sk not in st.session_state:
            st.session_state[sk] = st.session_state.dork_tokens.get(key, "")

    catalog = load_catalog()
    engines_all = list_engines(catalog)
    goals_all = list_goals(catalog)

    page_header(
        "Busca",
        "Dorks Google",
        "Monte consultas prontas, filtre por motor/objetivo e abra no buscador. "
        "Uso educacional · alvos autorizados.",
    )
    st.caption(f"{len(catalog)} técnicas · WebDorks + Site_lists Holmes")

    # 1) Busca + letra (simples)
    f1, f2, f3 = st.columns([3, 1, 1])
    with f1:
        dork_search = st.text_input(
            "Buscar",
            placeholder="ex.: pdf, login, subdomain…",
            key="dork_search",
            label_visibility="collapsed",
        )
    letters = sorted(
        {
            (localize_technique(t).get("title") or t.get("title") or "?")[0].upper()
            for t in catalog
            if t.get("title") or localize_technique(t).get("title")
        }
    )
    with f2:
        letter_pick = st.selectbox(
            "Letra",
            ["Todas"] + letters,
            key="dork_letter",
        )
    letter = None if letter_pick == "Todas" else letter_pick
    with f3:
        if st.button("Limpar filtros", key="dork_clear_filters", use_container_width=True):
            st.session_state.dork_search = ""
            st.session_state.dork_letter = "Todas"
            st.session_state.dork_eng_ms = []
            st.session_state.dork_goal_ms = []
            st.rerun()

    # 2) Filtros compactos (sem parede de checkbox)
    engine_sel = st.multiselect(
        "Motores (opcional)",
        engines_all,
        default=[],
        key="dork_eng_ms",
        placeholder="Todos os motores",
    )
    goal_labels = {humanize_goal(g): g for g in goals_all}
    goal_picked = st.multiselect(
        "Objetivos (opcional)",
        list(goal_labels.keys()),
        default=[],
        key="dork_goal_ms",
        placeholder="Todos os objetivos",
    )
    goal_sel = [goal_labels[x] for x in goal_picked]

    # 3) Tokens recolhidos (não poluem a tela)
    placeholders = {
        "TARGET_DOMAIN": "exemplo.com",
        "ORG_NAME": "acme",
        "USERNAME": "johndoe",
        "EMAIL": "user@empresa.com",
        "IP": "203.0.113.7",
        "ASN": "AS15169",
        "PHONE": "5511999999999",
    }
    with st.expander("Preencher alvos (domínio, email, IP…)", expanded=False):
        st.caption("Substitui os placeholders nas consultas abaixo.")
        tcols = st.columns(4)
        token_vals = {}
        for i, key in enumerate(TOKEN_KEYS):
            with tcols[i % 4]:
                token_vals[key] = st.text_input(
                    TOKEN_LABELS_PT.get(key, key),
                    placeholder=placeholders.get(key, ""),
                    key=f"dork_tok_{key}",
                )
        ctok1, ctok2 = st.columns(2)
        with ctok1:
            if st.button("Limpar alvos", key="dork_clear_tokens", use_container_width=True):
                st.session_state.dork_tokens = empty_tokens()
                for key in TOKEN_KEYS:
                    st.session_state[f"dork_tok_{key}"] = ""
                st.rerun()
        st.session_state.dork_tokens = {
            k: (token_vals.get(k) or "").strip() for k in TOKEN_KEYS
        }

    filtered = filter_techniques(
        catalog,
        search=dork_search,
        engines=engine_sel,
        goals=goal_sel,
        letter=letter,
    )
    qcount = sum(len(t.get("queries") or []) for t in filtered)
    st.markdown(
        f"**{len(filtered)}** técnicas · **{qcount}** consultas"
        + (f" · filtro: `{dork_search}`" if dork_search else "")
    )

    if not filtered:
        st.info("Nada encontrado. Limpe os filtros ou mude a busca.")
    else:
        _opts = [n for n in (10, 20, 40, 60, 100) if n <= max(10, len(filtered))]
        if not _opts:
            _opts = [len(filtered) or 10]
        max_show = st.select_slider(
            "Mostrar até",
            options=_opts,
            value=_opts[min(1, len(_opts) - 1)],
            key="dork_max_slider",
        )
        for tech in filtered[: int(max_show)]:
            tid = tech.get("id", "")
            loc = localize_technique(tech)
            tags = "".join(
                f'<span class="mh-dork-tag">{_html.escape(humanize_goal(g))}</span>'
                for g in (tech.get("goals") or [])
            )
            src = source_label(tech.get("source") or "")
            src_badge = (
                f'<span class="mh-dork-tag">{_html.escape(src)}</span>' if src else ""
            )
            rows = resolve_queries(tech, st.session_state.dork_tokens)
            query_html_parts = []
            for row in rows:
                qtxt = _html.escape(row["q"])
                eng = _html.escape(row["engine"])
                link = ""
                if row.get("url"):
                    href = _html.escape(row["url"])
                    label = "Portal" if row.get("portal_only") else "Abrir"
                    link = (
                        f'<a href="{href}" target="_blank" rel="noopener">{label} →</a>'
                    )
                query_html_parts.append(
                    f'<div class="mh-dork-query">'
                    f'<span class="mh-dork-engine">{eng}</span>'
                    f'<code class="mh-dork-code">{qtxt}</code>'
                    f'<div class="mh-dork-actions">{link}</div></div>'
                )
            st.html(
                f'<div class="mh-dork-card">'
                f"<h3>{_html.escape(loc['title'])}</h3>"
                f'<p class="mh-dork-desc">{_html.escape(loc["description"])}</p>'
                f'<div class="mh-dork-tags">{tags}{src_badge}</div>'
                f'{"".join(query_html_parts)}'
                f"</div>"
            )
            acols = st.columns(min(3, max(1, len(rows))))
            for qi, row in enumerate(rows):
                with acols[qi % len(acols)]:
                    if st.button(
                        f"Copiar · {row['engine']}",
                        key=f"copy_{tid}_{qi}",
                        use_container_width=True,
                    ):
                        st.session_state["dork_clipboard"] = row["q"]
                        st.code(row["q"], language=None)
                        st.toast("Consulta pronta para copiar.")


# ── Leaks (API oficial se houver chave; senão dashboard) ─────────────────────
elif page == "Leaks":
    from Core.Support.OsintLeak import apply_session_key, configured, search as ol_search

    page_header(
        "API / Externo",
        "OSINT Leak",
        "Busca oficial no Holmes quando `OSINTLEAK_API_KEY` está no Railway. "
        "Sem chave, só o atalho do dashboard — o Holmes não raspa o site.",
    )

    apply_session_key(st.session_state.get("ol_api_key"))
    has_key = configured()
    if has_key:
        st.success("API OSINT Leak ativa neste processo. A busca roda aqui; senhas são omitidas; stealer logs desligados.")
    else:
        st.info(
            "Sem `OSINTLEAK_API_KEY`. Cole a Variable no Railway (mesmo lugar de OPENAI_API_KEY), "
            "faça Redeploy, ou use o campo abaixo só nesta sessão. Sem isso o Holmes não consulta a base paga."
        )
        st.text_input(
            "OSINT Leak API key (sessão)",
            type="password",
            key="ol_api_key",
            placeholder="só se quiser testar nesta sessão — não vai para o git",
            help="Dashboard → Profile → API Settings. Opcional: whitelist do IP do Railway.",
        )
        apply_session_key(st.session_state.get("ol_api_key"))
        has_key = configured()

    tipo_ol = st.selectbox(
        "Tipo de busca",
        ["email", "username", "phone", "domain", "ip", "name"],
        help="domain vira type=url na API oficial. type=password não é oferecido.",
    )
    query_ol = st.text_input(
        "Consulta",
        placeholder={
            "email": "exemplo@dominio.com",
            "username": "joaosilva",
            "phone": "5511999999999",
            "domain": "exemplo.com",
            "ip": "8.8.8.8",
            "name": "Nome Sobrenome",
        }[tipo_ol],
        key="ol_query",
    )

    dash_url = "https://app.osintleak.com/dashboard/search"
    c1, c2, c3 = st.columns(3)
    with c1:
        run_ol = st.button("Buscar no Holmes", type="primary", use_container_width=True, disabled=not query_ol.strip())
    with c2:
        st.link_button("Abrir dashboard OSINT Leak", dash_url, use_container_width=True)
    with c3:
        st.link_button("PimEyes (imagem)", "https://pimeyes.com", use_container_width=True)

    if run_ol and query_ol.strip():
        if not configured():
            st.warning("Ainda sem chave. A busca oficial não roda — use o dashboard ou cole OSINTLEAK_API_KEY.")
        else:
            with st.spinner("Consultando a API oficial OSINT Leak…"):
                r = ol_search(query_ol.strip(), kind=tipo_ol)
            from Core.Support.History import save_search
            if r.get("ok"):
                hits = r.get("hits") or []
                st.success(f"{len(hits)} registros visíveis · total informado: {r.get('count', 0)} · senhas omitidas")
                if r.get("censored"):
                    st.caption("A API marcou a resposta como censored.")
                for hit in hits:
                    st.markdown("- " + " · ".join(f"**{k}:** {v}" for k, v in hit.items()))
                if not hits:
                    st.info("A API respondeu, mas não havia campos públicos para mostrar.")
                save_search("osintleak", query_ol.strip(), country=tipo_ol, sites_found=len(hits))
            else:
                st.error(r.get("error") or "Falha na API OSINT Leak.")
                st.caption("Confira quota, IP whitelist no painel deles, e o nome exato da Variable.")

    if query_ol.strip() and not configured():
        st.subheader("Copiar para o dashboard")
        st.code(f"tipo={tipo_ol}\nquery={query_ol.strip()}", language=None)

    st.subheader("O que o Holmes já faz sem a chave paga")
    st.markdown(
        """
| Precisa de… | No Holmes (nativo) | Terceiro |
|---|---|---|
| Username em redes | **OSINT Avançado → WhatsMyName** e Maigret | WhatsMyName.app / UserHunter |
| Email (contas públicas) | **Holehe** (≈ Epieos) | Epieos (pago; sem scrape) |
| Email / telefone em breaches | **Leaks** com `OSINTLEAK_API_KEY` | Dashboard OSINT Leak |
| Telefone (DDD BR) | **Telefone** | Truecaller (só link; sem API reversa) |
| Reverse image | Link PimEyes | AI Reverse Image (pago) |
| Monitoring contínuo | — | Platinum / Enterprise |
"""
    )
    display_services_for_page("leaks", heading="Fontes de leaks e breaches")


# ── Ferramentas ──────────────────────────────────────────────────────────────
elif page == "Ferramentas":
    import html as _html
    import urllib.request as _ur
    import json as _json

    page_header(
        "Catálogo",
        "Ferramentas (GitHub / CLI)",
        "Só OSINT e recon passivo — links oficiais. Sem instalação automática. "
        "Para sites web prontos, use o menu «Links web».",
    )

    # cat keys drive filter + section order
    CAT_META = [
        ("workbench", "Workbenches"),
        ("leaks", "Leaks"),
        ("frameworks", "Frameworks OSINT"),
        ("coleta", "Coleta & descoberta"),
        ("metadados", "Metadados"),
        ("social", "Redes sociais"),
        ("infra", "Infra / DNS"),
        ("telefone", "Telefone"),
        ("codigo", "Código"),
    ]
    CAT_LABEL = {k: v for k, v in CAT_META}

    tools_catalog = [
        {
            "num": "",
            "name": "Dorks Workbench",
            "desc": "Catálogo curado com tokens e filtros — interno ao Mr.Holmes.",
            "url": None,
            "hint": "menu Dorks",
            "cat": "workbench",
        },
        {
            "num": "",
            "name": "WebDorks",
            "desc": "Workbench original que inspirou o layout do menu Dorks.",
            "url": "https://webdorks.vercel.app/",
            "cat": "workbench",
        },
        {
            "num": "",
            "name": "Robin",
            "desc": "Briefing de dark web com LLM (repo oficial). Roda no Docker dele, não no Holmes.",
            "url": "https://github.com/apurvsinghgautam/robin",
            "hint": "OSINT Premium",
            "cat": "frameworks",
        },
        {
            "num": "",
            "name": "OSINT Leak",
            "desc": "Breaches via API oficial se OSINTLEAK_API_KEY existir; senão dashboard.",
            "url": "https://app.osintleak.com/dashboard/search",
            "cat": "leaks",
        },
        {
            "num": "",
            "name": "Maltego",
            "desc": "Grafo de relacionamentos (pessoas, domínios, infra).",
            "url": "https://www.maltego.com/",
            "cat": "frameworks",
        },
        {
            "num": "",
            "name": "Recon-ng",
            "desc": "Framework modular de recon web.",
            "url": "https://github.com/lanmaster53/recon-ng",
            "cat": "frameworks",
        },
        {
            "num": "",
            "name": "SpiderFoot",
            "desc": "Automação OSINT (módulos de fontes abertas).",
            "url": "https://github.com/smicallef/spiderfoot",
            "hint": "OSINT Avançado",
            "cat": "frameworks",
        },
        {
            "num": "",
            "name": "Amass",
            "desc": "Mapeamento de superfície / subdomínios (OWASP).",
            "url": "https://github.com/OWASP/Amass",
            "hint": "OSINT Avançado",
            "cat": "frameworks",
        },
        {
            "num": "",
            "name": "Flowsint",
            "desc": "Grafo OSINT + enrichers (Docker oficial Apache-2.0). No Holmes o fluxo abre os módulos nativos.",
            "url": "https://github.com/reconurge/flowsint",
            "hint": "OSINT Premium · Investigar",
            "cat": "frameworks",
        },
        {
            "num": "",
            "name": "Awesome OSINT Arsenal",
            "desc": "Índice 753+ tools. Neste site só a fatia OSINT — sem redteam.sh / phishing.",
            "url": "https://github.com/rawfilejson/awesome-osint-arsenal",
            "hint": "OSINT Premium · Investigar",
            "cat": "frameworks",
        },
        {
            "num": "",
            "name": "OSINT Framework",
            "desc": "Mapa indexado de fontes OSINT.",
            "url": "https://github.com/lockfale/OSINT-Framework",
            "cat": "frameworks",
        },
        {
            "num": "",
            "name": "theHarvester",
            "desc": "Coleta emails e subdomínios em fontes abertas.",
            "url": "https://github.com/laramies/theHarvester",
            "hint": "OSINT Avançado",
            "cat": "coleta",
        },
        {
            "num": "",
            "name": "Infoga",
            "desc": "OSINT focado em e-mails.",
            "url": "https://github.com/m4ll0k/Infoga",
            "cat": "coleta",
        },
        {
            "num": "",
            "name": "Subfinder",
            "desc": "Enum passiva de subdomínios (ProjectDiscovery).",
            "url": "https://github.com/projectdiscovery/subfinder",
            "hint": "OSINT Avançado",
            "cat": "coleta",
        },
        {
            "num": "",
            "name": "httpx",
            "desc": "Probe HTTP — status, título, tecnologias.",
            "url": "https://github.com/projectdiscovery/httpx",
            "hint": "OSINT Avançado",
            "cat": "coleta",
        },
        {
            "num": "",
            "name": "FOCA",
            "desc": "Metadados em documentos públicos.",
            "url": "https://github.com/ElevenPaths/FOCA",
            "cat": "metadados",
        },
        {
            "num": "",
            "name": "Metagoofil",
            "desc": "Extrai metadados a partir de buscas.",
            "url": "https://github.com/laramies/metagoofil",
            "cat": "metadados",
        },
        {
            "num": "",
            "name": "Sherlock",
            "desc": "Username em redes sociais.",
            "url": "https://github.com/sherlock-project/sherlock",
            "cat": "social",
        },
        {
            "num": "",
            "name": "SocialScan",
            "desc": "Checa username/email em plataformas.",
            "url": "https://github.com/iojw/socialscan",
            "cat": "social",
        },
        {
            "num": "",
            "name": "PimEyes",
            "desc": "Busca reversa de rostos (serviço web).",
            "url": "https://pimeyes.com",
            "cat": "social",
        },
        {
            "num": "",
            "name": "UrlScan.io",
            "desc": "Sandbox de URLs — painel no final desta página.",
            "url": "https://urlscan.io",
            "cat": "infra",
        },
        {
            "num": "",
            "name": "ViewDNS",
            "desc": "WHOIS, histórico de IP, DNS.",
            "url": "https://viewdns.info",
            "cat": "infra",
        },
        {
            "num": "",
            "name": "dnsx",
            "desc": "Toolkit DNS (ProjectDiscovery).",
            "url": "https://github.com/projectdiscovery/dnsx",
            "cat": "infra",
        },
        {
            "num": "",
            "name": "PhoneInfoga",
            "desc": "Framework OSINT de números (destaque telefone).",
            "url": "https://github.com/sundowndev/phoneinfoga",
            "hint": "menu Telefone",
            "cat": "telefone",
        },
        {
            "num": "",
            "name": "Ignorant",
            "desc": "Número → presença em redes (Instagram, Snap…).",
            "url": "https://github.com/megadose/ignorant",
            "hint": "menu Telefone",
            "cat": "telefone",
        },
        {
            "num": "",
            "name": "Grep.app",
            "desc": "Busca em código público.",
            "url": "https://grep.app",
            "cat": "codigo",
        },
        {
            "num": "",
            "name": "Gitleaks",
            "desc": "Secrets expostos em repositórios Git.",
            "url": "https://github.com/gitleaks/gitleaks",
            "cat": "codigo",
        },
        {
            "num": "",
            "name": "TruffleHog",
            "desc": "Caça API keys e credenciais em repos (hackingtool).",
            "url": "https://github.com/trufflesecurity/trufflehog",
            "cat": "codigo",
        },
        {
            "num": "",
            "name": "CyberChef",
            "desc": "Encode/decode e análise de dados (hackingtool online).",
            "url": "https://gchq.github.io/CyberChef/",
            "cat": "metadados",
        },
        {
            "num": "",
            "name": "Aperi'Solve",
            "desc": "Stego + metadados de imagem no browser (hackingtool).",
            "url": "https://www.aperisolve.com/",
            "cat": "metadados",
        },
        {
            "num": "",
            "name": "StegOnline",
            "desc": "Explorador LSB de imagens (hackingtool).",
            "url": "https://georgeom.net/StegOnline/upload",
            "cat": "metadados",
        },
        {
            "num": "",
            "name": "ExifTool",
            "desc": "Metadados EXIF/IPTC/XMP (hackingtool).",
            "url": "https://exiftool.org/",
            "cat": "metadados",
        },
        {
            "num": "",
            "name": "Shodan",
            "desc": "Busca de hosts e serviços expostos (hackingtool).",
            "url": "https://www.shodan.io/",
            "cat": "infra",
        },
        {
            "num": "",
            "name": "crt.sh",
            "desc": "Certificate Transparency — subdomínios via CT logs.",
            "url": "https://crt.sh/",
            "cat": "infra",
        },
        {
            "num": "",
            "name": "WiGLE",
            "desc": "Mapa OSINT de redes Wi‑Fi (hackingtool).",
            "url": "https://wigle.net/",
            "cat": "infra",
        },
        {
            "num": "",
            "name": "Have I Been Pwned",
            "desc": "Breaches públicos por email (hackingtool-adjacent).",
            "url": "https://haveibeenpwned.com/",
            "cat": "leaks",
        },
        {
            "num": "",
            "name": "hackingtool",
            "desc": "Catálogo fonte (215 tools) — só referência; não instala ofensivos aqui.",
            "url": "https://github.com/Z4nzu/hackingtool",
            "cat": "frameworks",
        },
        # Phone OSINT portfolio (GitHub + web)
        {
            "num": "",
            "name": "PhoneInfoga",
            "desc": "Framework OSINT de números (sundowndev) — scanners e dorks.",
            "url": "https://github.com/sundowndev/phoneinfoga",
            "cat": "coleta",
        },
        {
            "num": "",
            "name": "Ignorant",
            "desc": "Número em redes (Instagram/Snap…) — megadose.",
            "url": "https://github.com/megadose/ignorant",
            "cat": "social",
        },
        {
            "num": "",
            "name": "Phunter",
            "desc": "OSINT multiponto a partir de telefone (N0rz3).",
            "url": "https://github.com/N0rz3/Phunter",
            "cat": "coleta",
        },
        {
            "num": "",
            "name": "SearchPhone",
            "desc": "Multi-API phone OSINT + relatório (HackUnderway).",
            "url": "https://github.com/HackUnderway/SearchPhone",
            "cat": "coleta",
        },
        {
            "num": "",
            "name": "Moriarty Project",
            "desc": "Informações a partir do número informado.",
            "url": "https://github.com/AzizKpln/Moriarty-Project",
            "cat": "coleta",
        },
        {
            "num": "",
            "name": "Telephone-OSINT Toolbox",
            "desc": "Coleção curada de phone lookup tools.",
            "url": "https://github.com/The-Osint-Toolbox/Telephone-OSINT",
            "cat": "frameworks",
        },
        {
            "num": "",
            "name": "Sync.me",
            "desc": "Caller ID / agenda reversa (web).",
            "url": "https://sync.me/pt-br/",
            "cat": "social",
        },
        {
            "num": "",
            "name": "Truecaller",
            "desc": "Caller ID colaborativo (web/app).",
            "url": "https://www.truecaller.com/",
            "cat": "social",
        },
        {
            "num": "",
            "name": "Phonebook.cz",
            "desc": "Busca em dumps públicos indexados.",
            "url": "https://phonebook.cz/",
            "cat": "leaks",
        },
    ]

    recon_count = sum(1 for t in tools_catalog if t.get("num"))
    total_count = len(tools_catalog)

    st.html(
        f"""
        <div class="mh-tools-hero">
          <div class="mh-dork-kicker">Catálogo externo</div>
          <h2>Serviços OSINT</h2>
          <p>
            Links para ferramentas de recon, coleta e análise. Itens com selo interno
            também aparecem no menu <strong>OSINT Avançado</strong> ou <strong>Dorks</strong>.
            Uso educacional e em alvos autorizados.
          </p>
          <div class="mh-tools-stats">
            <span class="mh-tools-stat"><strong>{total_count}</strong> no diretório</span>
            <span class="mh-tools-stat"><strong>{recon_count}</strong> recon/OSINT</span>
            <span class="mh-tools-stat"><strong>{len(CAT_META)}</strong> categorias</span>
          </div>
        </div>
        """
    )

    f1, f2 = st.columns([2.2, 1])
    with f1:
        tool_q = st.text_input(
            "Buscar",
            "",
            key="tools_search",
            placeholder="Ex.: nmap, email, metadados…",
            label_visibility="collapsed",
        )
    with f2:
        cat_options = ["Todas"] + [label for _, label in CAT_META]
        tool_cat = st.selectbox(
            "Categoria",
            cat_options,
            key="tools_cat",
            label_visibility="collapsed",
        )

    q = (tool_q or "").strip().lower()
    selected_cat_key = None
    if tool_cat != "Todas":
        selected_cat_key = next(k for k, v in CAT_META if v == tool_cat)

    def _tool_match(t: dict) -> bool:
        if selected_cat_key and t["cat"] != selected_cat_key:
            return False
        if not q:
            return True
        blob = " ".join(
            [
                t.get("name", ""),
                t.get("desc", ""),
                t.get("hint", ""),
                CAT_LABEL.get(t["cat"], ""),
                t.get("num", ""),
            ]
        ).lower()
        return q in blob

    filtered = [t for t in tools_catalog if _tool_match(t)]
    st.caption(f"{len(filtered)} de {total_count} ferramentas visíveis")

    def _render_tool_card(t: dict) -> str:
        num = _html.escape(t["num"]) if t.get("num") else ""
        name = _html.escape(t["name"])
        desc = _html.escape(t["desc"])
        num_html = f'<span class="mh-tool-num">{num}</span>' if num else "<span></span>"
        if t.get("url"):
            href = _html.escape(t["url"])
            action = f'<a href="{href}" target="_blank" rel="noopener noreferrer">Abrir →</a>'
        else:
            action = '<span class="mh-tool-hint">interno</span>'
        hint = t.get("hint")
        hint_html = (
            f'<span class="mh-tool-hint">→ {_html.escape(hint)}</span>' if hint else ""
        )
        return (
            f'<div class="mh-tool">'
            f'<div class="mh-tool-top">{num_html}<h4>{name}</h4></div>'
            f"<p>{desc}</p>"
            f'<div class="mh-tool-foot">{action}{hint_html}</div>'
            f"</div>"
        )

    blocks = []
    for cat_key, cat_label in CAT_META:
        group = [t for t in filtered if t["cat"] == cat_key]
        if not group:
            continue
        cards = "".join(_render_tool_card(t) for t in group)
        blocks.append(
            f'<div class="mh-tools-section">'
            f"<h3>{_html.escape(cat_label)}</h3>"
            f"<span>{len(group)}</span>"
            f"</div>"
            f'<div class="mh-tools-grid">{cards}</div>'
        )

    if blocks:
        st.html("".join(blocks))
    else:
        st.html('<div class="mh-tools-empty">Nenhuma ferramenta corresponde aos filtros.</div>')

    st.html(
        """
        <div class="mh-urlscan">
          <h3>UrlScan.io · análise rápida</h3>
          <p>Envie uma URL para sandbox pública ou abra a busca no site.</p>
        </div>
        """
    )
    url_to_scan = st.text_input("URL para UrlScan", "https://exemplo.com", key="urlscan_input")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Enviar análise", key="urlscan_submit"):
            try:
                req = _ur.Request(
                    "https://urlscan.io/api/v1/scan/",
                    data=_json.dumps({"url": url_to_scan, "visibility": "public"}).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "API-Key": "",
                        "User-Agent": "MrHolmes-1.0",
                    },
                )
                resp = _ur.urlopen(req, timeout=15)
                data = _json.loads(resp.read().decode())
                uuid = data.get("uuid", "")
                if uuid:
                    st.success("Análise enviada")
                    st.markdown(
                        f"[Resultado](https://urlscan.io/result/{uuid}/) · "
                        f"[Screenshot](https://urlscan.io/screenshots/{uuid}.png)"
                    )
            except Exception:
                st.warning("API indisponível ou limite atingido.")
                st.markdown(f"[Abrir no UrlScan](https://urlscan.io/search/#{url_to_scan})")
    with c2:
        st.link_button("Buscar no UrlScan", f"https://urlscan.io/search/#{url_to_scan}", use_container_width=True)


# ── Aprenda com Mr Holmes ────────────────────────────────────────────────────
elif page == "Aprenda":
    import html as _html

    page_header(
        "Recursos",
        "Aprenda com Mr Holmes",
        "Diretório de serviços úteis para estudo, pesquisa e produtividade na web.",
    )

    learn_catalog = [
        {
            "num": "01",
            "host": "12ft.io",
            "url": "https://12ft.io",
            "desc": "Contorna paywalls em páginas de notícias e artigos.",
            "color": "#4C8DFF",
            "glyph": "12",
        },
        {
            "num": "02",
            "host": "libgen.is",
            "url": "https://libgen.is",
            "desc": "Milhões de livros e textos para consulta.",
            "color": "#3DDC97",
            "glyph": "LG",
        },
        {
            "num": "03",
            "host": "sci-hub.se",
            "url": "https://sci-hub.se",
            "desc": "Acesso a artigos científicos de pesquisa.",
            "color": "#A78BFA",
            "glyph": "SH",
        },
        {
            "num": "04",
            "host": "alternativeto.net",
            "url": "https://alternativeto.net",
            "desc": "Encontre alternativas grátis a qualquer app.",
            "color": "#FF9B6A",
            "glyph": "AT",
        },
        {
            "num": "05",
            "host": "justwatch.com",
            "url": "https://www.justwatch.com",
            "desc": "Descubra onde assistir filmes e séries em streaming.",
            "color": "#5B8DEF",
            "glyph": "JW",
        },
        {
            "num": "06",
            "host": "archive.org",
            "url": "https://archive.org",
            "desc": "Arquivo da web, livros, áudio e mídia histórica.",
            "color": "#6EA8FE",
            "glyph": "IA",
        },
        {
            "num": "07",
            "host": "gutenberg.org",
            "url": "https://www.gutenberg.org",
            "desc": "Mais de 70 mil clássicos em domínio público.",
            "color": "#E8C547",
            "glyph": "PG",
        },
        {
            "num": "08",
            "host": "pdfdrive.com",
            "url": "https://www.pdfdrive.com",
            "desc": "Busca de PDFs em diversos temas.",
            "color": "#F07178",
            "glyph": "PDF",
        },
        {
            "num": "09",
            "host": "openculture.com",
            "url": "https://www.openculture.com",
            "desc": "Cursos online grátis de grandes universidades.",
            "color": "#C084FC",
            "glyph": "OC",
        },
        {
            "num": "10",
            "host": "wolframalpha.com",
            "url": "https://www.wolframalpha.com",
            "desc": "Resolva problemas matemáticos e consultas de conhecimento.",
            "color": "#FF5A5F",
            "glyph": "Wα",
        },
        {
            "num": "11",
            "host": "photopea.com",
            "url": "https://www.photopea.com",
            "desc": "Editor de imagens no navegador (estilo Photoshop).",
            "color": "#34D399",
            "glyph": "P",
        },
        {
            "num": "12",
            "host": "squoosh.app",
            "url": "https://squoosh.app",
            "desc": "Comprima imagens sem perder qualidade perceptível.",
            "color": "#F472B6",
            "glyph": "Sq",
        },
        {
            "num": "13",
            "host": "remove.bg",
            "url": "https://www.remove.bg",
            "desc": "Remove fundos de imagens automaticamente.",
            "color": "#4ADE80",
            "glyph": "BG",
        },
        {
            "num": "14",
            "host": "cleanup.picture",
            "url": "https://cleanup.picture",
            "desc": "Apague objetos indesejados das suas fotos.",
            "color": "#A78BFA",
            "glyph": "CL",
        },
        {
            "num": "15",
            "host": "unscreen.com",
            "url": "https://www.unscreen.com",
            "desc": "Remove o fundo de vídeos automaticamente.",
            "color": "#2DD4BF",
            "glyph": "Un",
        },
        {
            "num": "16",
            "host": "carbon.now.sh",
            "url": "https://carbon.now.sh",
            "desc": "Transforme código em imagens profissionais.",
            "color": "#FB923C",
            "glyph": "</>",
        },
        {
            "num": "17",
            "host": "ray.so",
            "url": "https://ray.so",
            "desc": "Capturas bonitas de trechos de código.",
            "color": "#60A5FA",
            "glyph": "Ry",
        },
        {
            "num": "18",
            "host": "shots.so",
            "url": "https://shots.so",
            "desc": "Mockups de produto grátis e profissionais.",
            "color": "#F87171",
            "glyph": "Sh",
        },
        {
            "num": "19",
            "host": "smartmockups.com",
            "url": "https://smartmockups.com",
            "desc": "Mockups sem precisar de Photoshop.",
            "color": "#4ADE80",
            "glyph": "SM",
        },
        {
            "num": "20",
            "host": "haveibeenpwned.com",
            "url": "https://haveibeenpwned.com",
            "desc": "Verifique se seus dados apareceram em vazamentos.",
            "color": "#F87171",
            "glyph": "HB",
        },
    ]

    st.html(
        """
        <div class="mh-learn-hero">
          <div class="mh-dork-kicker">Aprenda com Mr Holmes</div>
          <h2>Desbloqueie o poder oculto da internet</h2>
          <p>
            Catálogo de 20 serviços externos para estudo, pesquisa e produtividade.
            Links oficiais — sem instalação automática. Use com responsabilidade e
            respeite direitos autorais e termos de cada site.
          </p>
        </div>
        """
    )

    cards = []
    for item in learn_catalog:
        href = _html.escape(item["url"])
        host = _html.escape(item["host"])
        desc = _html.escape(item["desc"])
        num = _html.escape(item["num"])
        color = _html.escape(item["color"])
        glyph = _html.escape(item["glyph"])
        cards.append(
            f'<a class="mh-learn-card" href="{href}" target="_blank" rel="noopener noreferrer">'
            f'<span class="mh-learn-num">{num}</span>'
            f'<span class="mh-learn-icon" style="--c:{color}">{glyph}</span>'
            f'<span class="mh-learn-url">{host}</span>'
            f'<span class="mh-learn-desc">{desc}</span>'
            f"</a>"
        )

    st.html(f'<div class="mh-learn-grid">{"".join(cards)}</div>')


# ── Histórico ────────────────────────────────────────────────────────────────
elif page == "Serviços Externos":
    from external_services import get_all_services_flat, get_all_categories
    _n = len(get_all_services_flat())
    _nc = len(get_all_categories())
    page_header(
        "Catálogo",
        "Links por categoria",
        f"{_n} fontes em {_nc} categorias (Web + GitHub). "
        "Use o filtro Todos / Web / GitHub dentro de cada aba. "
        "O menu «Catálogo (GitHub)» lista tools CLI com mais detalhe.",
    )
    display_external_services(title=False)
    st.caption("Só OSINT legítimo · sem phishing/RAT/DDoS · alvos autorizados.")


# ── Histórico ────────────────────────────────────────────────────────────────
elif page == "Histórico":
    page_header("Registro", "Histórico", "Dossiês do motor e consultas recentes.")
    display_historico()
    st.markdown("---")
    st.subheader("Consultas rápidas (páginas manuais)")
    try:
        from Core.Support.History import get_history, get_stats
        stats = get_stats()
        a, b, c = st.columns(3)
        a.metric("Total", stats["total"])
        b.metric("Hoje", stats["today"])
        c.metric("Tipos", len(stats.get("by_type", {})))
        st.subheader("Recentes")
        for h in get_history(limit=20):
            st.markdown(
                f"`{h.get('type', '—')}`  **{h['query']}**  ·  "
                f"{(h.get('searched_at') or '')[:19]}"
            )
    except Exception:
        st.info("Sem histórico ainda. Execute uma busca.")


# ── Sobre ────────────────────────────────────────────────────────────────────
elif page == "Sobre":
    page_header("Projeto", "Sobre", "Console OSINT para coleta em fontes abertas.")
    st.markdown("""
**Mr.Holmes** reúne lookups de telefone, email e domínio, utilitários de rede,
análise de relacionamentos e integrações com ferramentas OSINT conhecidas.

**Módulos**
- **OSINT Premium** — Robin embutido (busca + relatório) e atalhos para as suites nativas
- Telefone, email, domínio
- **Dorks Workbench** — catálogo curado (WebDorks MIT + listas Holmes), tokens, filtros, abrir busca
- Suite OSINT (Holehe, WhatsMyName, Maigret, theHarvester, dnstwist, httpx…)
- **Leaks** — API oficial OSINT Leak se `OSINTLEAK_API_KEY` estiver no Railway (senhas omitidas; sem stealer logs)
- **Ferramentas** — catálogo externo (Robin, Maltego, Amass, SpiderFoot, theHarvester, FOCA…)
- **Aprenda com Mr Holmes** — 20 serviços de estudo e produtividade web
- Rede, gráfico, histórico

**Mr.Holmes vs Robin**
- **Holmes:** clear web — pessoa, telefone, domínio, dorks, grafo.
- **Robin** (MIT © [Apurv Singh Gautam](https://github.com/apurvsinghgautam/robin)): agora **roda no menu OSINT Premium** — query, busca (Tor + Ahmia), scrape e dossiê.
- **Chaves:** cole OpenAI/Claude na sidebar **Chaves LLM**, ou use `.env` / variáveis Railway (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`). Sem chave a busca ainda roda.

**Mr.Holmes vs WebDorks**
- Layout e catálogo de técnicas inspirados em [WebDorks](https://webdorks.vercel.app/) (© root-Manas, MIT).
- **Diferenciais Holmes:** links diretos para engines, token `PHONE`, fusão com `Site_lists/`, prefill a partir de Telefone/Email/Domínio.

**Mr.Holmes vs OSINT Leak / Epieos / Truecaller / WhatsMyName**
- **WhatsMyName:** nativo no Holmes (lista WebBreacher). Não abre whatsmyname.app.
- **Epieos:** não há scrape. Contas de email no Holmes = **Holehe**. API Pro só se vocês tiverem chave oficial no futuro.
- **Truecaller:** a API oficial é Caller ID comercial / SDK, não busca reversa OSINT. O Holmes não raspa o site; o atalho permanece.
- **OSINT Leak:** com `OSINTLEAK_API_KEY` a busca oficial roda no menu Leaks e na caixa Investigar. Sem chave, só o dashboard. Stealer logs desligados; senhas não aparecem na tela.

**Aviso** — uso educacional e em alvos autorizados. Não raspe bases comerciais.
O autor não se responsabiliza por uso indevido.
""")

st.caption("Mr.Holmes — console OSINT · apenas uso educacional e alvos autorizados")
