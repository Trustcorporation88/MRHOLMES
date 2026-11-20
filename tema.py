"""Visual do painel, versão 2 (identidade do logotipo: ciano para violeta).

Três camadas, cada uma no lugar certo:
  .streamlit/config.toml  fontes (Inter no texto, Sora nos títulos, JetBrains
                          Mono nos códigos) e as cores de base. É o tema nativo
                          do Streamlit: componentes já nascem coerentes.
  assets/                 logotipo e ícone, entregues por `st.logo` e `st.image`.
  este arquivo            só o que é nosso: página inicial, grade de fatos do
                          dossiê, diretório.

Regra que não pode ser quebrada: este CSS não pode conter o caractere "<".
O `st.html` passa o bloco por um sanitizador e descarta o estilo INTEIRO se
achar algo com cara de tag, até dentro de comentário. Foi assim que o painel
ficou dois meses sem tema. `aplicar()` e um teste conferem isso.
"""

from __future__ import annotations

import streamlit as st

CSS = r"""
:root {
  --bg: #0f121b;
  --panel: #151a26;
  --panel-2: #1a2131;
  --panel-3: #222b40;
  --line: #262f44;
  --line-2: #34405c;
  --text: #e9edf6;
  --muted: #94a0b8;
  --faint: #66728c;
  --a1: #4fd1ff;
  --a2: #8b7bff;
  --grad: linear-gradient(120deg, #4fd1ff 0%, #8b7bff 100%);
  --ok: #3ddc97;
  --warn: #f5b942;
  --bad: #ff7b7b;
  --r: 14px;
  --mono: 'JetBrains Mono', ui-monospace, Consolas, monospace;
}

/* ── base ─────────────────────────────────────────────────────────────── */
.stApp { background:
  radial-gradient(900px 480px at 50% -6%, rgba(139, 123, 255, 0.16), transparent 66%),
  radial-gradient(700px 400px at 92% 8%, rgba(79, 209, 255, 0.07), transparent 62%),
  var(--bg); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { max-width: 1120px; padding-top: 1.6rem; padding-bottom: 4rem; }
[data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded' !important; }
h1, h2, h3 { letter-spacing: -0.025em; }
h2 { font-size: 1.4rem !important; font-weight: 700 !important; }
h3 { font-size: 1.05rem !important; font-weight: 700 !important; }
hr { border-color: var(--line) !important; opacity: 1; margin: 1.5rem 0 !important; }

/* ── barra lateral ────────────────────────────────────────────────────── */
[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
[data-testid="stSidebarHeader"] { padding: 1.3rem 1rem 0.4rem; }
[data-testid="stSidebarHeader"] { min-height: 5.6rem; }
[data-testid="stSidebarLogo"] { height: 5.2rem !important; max-height: 5.2rem !important; width: auto !important; }
.mh-nav-group { font-size: 0.66rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--faint); margin: 20px 8px 4px; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.25rem; }
[data-testid="stSidebar"] .stButton > button { justify-content: flex-start; border: 1px solid transparent;
  background: transparent; color: var(--muted); font-weight: 500; padding: 0.55rem 0.8rem; border-radius: 10px;
  transition: background .12s, color .12s; }
[data-testid="stSidebar"] .stButton > button > div, [data-testid="stSidebar"] .stButton > button p {
  justify-content: flex-start; text-align: left; width: 100%; }
[data-testid="stSidebar"] .stButton > button:hover { background: var(--panel-2); color: var(--text); border-color: transparent; }
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] {
  background: var(--panel-3); color: var(--text); font-weight: 600; border-color: var(--line-2); }
.mh-side-foot { font-size: 0.72rem; color: var(--faint); line-height: 1.55; padding: 4px 8px; margin-top: 22px; }
.mh-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; background: var(--faint); }
.mh-dot.on { background: var(--ok); box-shadow: 0 0 0 3px rgba(61, 220, 151, 0.16); }

/* ── cabeçalho das páginas internas ───────────────────────────────────── */
.mh-page { display: flex; align-items: center; gap: 16px; margin: 0 0 1.5rem; }
.mh-page-icon { width: 50px; height: 50px; border-radius: 14px; display: grid; place-items: center; font-size: 1.4rem;
  background: var(--panel-2); border: 1px solid var(--line); flex: none; }
.mh-page-body { min-width: 0; }
.mh-page .eyebrow { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--a1); }
.mh-page h1 { font-size: 1.65rem; font-weight: 700; margin: 2px 0 0; padding: 0; color: var(--text); }
.mh-page .desc { color: var(--muted); font-size: 0.92rem; margin-top: 3px; }

/* ── página inicial: logotipo, busca e tipos, tudo centralizado ───────── */
.st-key-mh_logo { align-items: center; }
.st-key-mh_logo [data-testid="stImage"] { display: flex; justify-content: center; }
.st-key-mh_logo [data-testid="stImage"] button { display: none; }
.st-key-mh_logo img { border-radius: 0 !important; }
.mh-land { text-align: center; margin: 0 auto 1.2rem; max-width: 640px; }
.mh-land-sub { color: var(--muted); font-size: 1.04rem; line-height: 1.55; margin: 4px 0 0; }
.mh-land-meta { display: flex; justify-content: center; flex-wrap: wrap; gap: 6px 18px; margin-top: 14px;
  font-size: 0.78rem; color: var(--faint); }
.mh-land-meta b { color: var(--muted); font-weight: 600; }

.st-key-mh_busca { max-width: 860px; margin: 0 auto; background: var(--panel); border: 1px solid var(--line-2);
  border-radius: 18px; padding: 8px 10px 0; box-shadow: 0 22px 60px rgba(0, 0, 0, 0.38), 0 0 0 1px rgba(139, 123, 255, 0.08); }
.st-key-mh_busca [data-testid="stForm"] { border: 0; padding: 0; }
.st-key-mh_busca input { font-size: 1.08rem !important; height: 54px; background: transparent !important; }
.st-key-mh_busca [data-baseweb="input"], .st-key-mh_busca [data-baseweb="base-input"] {
  background: transparent !important; border-color: transparent !important; }
.st-key-mh_busca .stFormSubmitButton > button { height: 54px; border-radius: 12px; font-weight: 700; border: 0;
  background: var(--grad); color: #0b0e17; letter-spacing: 0.01em; }
.st-key-mh_busca .stFormSubmitButton > button:hover { filter: brightness(1.08); }
.st-key-mh_busca .stFormSubmitButton > button p { color: #0b0e17; font-weight: 700; }

.st-key-holmes_tipo { max-width: 860px; margin: 16px auto 0; }
.st-key-holmes_tipo [role="radiogroup"] { justify-content: center; gap: 8px; }
.st-key-holmes_tipo button[role="radio"] { background: transparent; border: 1px solid var(--line-2); color: var(--muted);
  border-radius: 999px; font-weight: 500; padding: 0.28rem 0.8rem; min-height: 0; }
.st-key-holmes_tipo button[role="radio"] p { font-size: 0.82rem; }
.st-key-holmes_tipo button[role="radio"]:hover { border-color: var(--a1); color: var(--text); }
.st-key-holmes_tipo button[role="radio"][aria-checked="true"] { background: rgba(79, 209, 255, 0.13);
  border-color: var(--a1); color: var(--text); }

.st-key-mh_chips { max-width: 860px; margin: 8px auto 0; }
.st-key-mh_chips .stButton > button { border-radius: 999px; background: transparent; border: 1px solid var(--line);
  color: var(--muted); font-size: 0.78rem; padding: 0.15rem 0.75rem; min-height: 0; font-family: var(--mono); }
.st-key-mh_chips .stButton > button:hover { border-color: var(--a1); color: var(--text); }
.st-key-mh_tiles .stButton > button { height: 60px; border-radius: var(--r); background: var(--panel);
  border: 1px solid var(--line); color: var(--text); font-weight: 600; }
.st-key-mh_tiles .stButton > button:hover { border-color: var(--a1); background: var(--panel-2); }
.mh-hint-label { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.13em; text-transform: uppercase;
  color: var(--faint); margin: 12px 0 4px; text-align: center; }
.mh-section { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--faint); margin: 2rem 0 0.7rem; display: flex; align-items: center; gap: 12px; }
.mh-section::after { content: ""; flex: 1; height: 1px; background: var(--line); }
.mh-soft { color: var(--muted); font-size: 0.84rem; }

/* ── componentes nativos, só o acabamento ─────────────────────────────── */
[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r); padding: 14px 18px; }
[data-testid="stMetricLabel"] p { color: var(--muted); font-size: 0.76rem; }
[data-testid="stMetricValue"] { font-weight: 700; letter-spacing: -0.03em; }
[data-testid="stExpander"] details { background: var(--panel); border: 1px solid var(--line); border-radius: var(--r); overflow: hidden; }
[data-testid="stExpander"] summary { font-weight: 600; padding: 0.7rem 1rem; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--line) !important; border-radius: var(--r) !important; }
[data-testid="stAlert"] { border-radius: var(--r); border: 1px solid var(--line); }
.stButton > button, .stDownloadButton > button, .stLinkButton > a { border-radius: 10px; font-weight: 600; }
[data-testid="stProgress"] > div > div > div > div { background: var(--grad); }
.stTabs [data-baseweb="tab-list"] { gap: 2px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
.stTabs [data-baseweb="tab"] { font-weight: 600; padding: 9px 14px; color: var(--muted); }
.stTabs [aria-selected="true"] { color: var(--text); }
.stTabs [data-baseweb="tab-highlight"] { background: var(--grad); height: 3px; border-radius: 3px; }

/* ── dossiê ───────────────────────────────────────────────────────────── */
.mh-idcard { display: flex; gap: 20px; align-items: center; background:
  linear-gradient(130deg, rgba(79, 209, 255, 0.10), rgba(139, 123, 255, 0.12)), var(--panel);
  border: 1px solid var(--line-2); border-radius: 20px; padding: 20px 22px; margin: 6px 0 18px; }
.mh-idcard-photo, .mh-idcard-initial { width: 78px; height: 78px; border-radius: 20px; flex: none; object-fit: cover;
  border: 1px solid var(--line-2); }
.mh-idcard-initial { display: grid; place-items: center; font-size: 1.9rem; font-weight: 700; color: #0b0e17;
  background: var(--grad); }
.mh-idcard-body { min-width: 0; flex: 1; }
.mh-idcard-kicker { font-size: 0.66rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: var(--a1); }
.mh-idcard-name { font-size: 1.55rem; font-weight: 700; letter-spacing: -0.025em; color: var(--text); margin: 2px 0 9px;
  overflow-wrap: anywhere; font-family: 'Sora', 'Inter', sans-serif; }
.mh-idcard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 5px 22px; }
.mh-idcard-row { font-size: 0.86rem; color: var(--muted); overflow-wrap: anywhere; }
.mh-idcard-row b { color: var(--text); font-weight: 600; }
.mh-flag { display: inline-block; margin: 8px 8px 0 0; color: var(--bad); font-weight: 600; font-size: 0.84rem; }

.mh-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 10px; margin-top: 12px; }
.mh-fact { --c: var(--faint); background: var(--panel-2); border: 1px solid var(--line); border-radius: 12px;
  padding: 12px 14px 11px; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.mh-fact-top { display: flex; align-items: center; gap: 8px; }
.mh-fact-tag { font-size: 0.62rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: var(--c);
  border: 1px solid var(--c); border-radius: 999px; padding: 1px 8px; flex: none; }
.mh-fact-val { font-weight: 600; color: var(--text); font-size: 0.95rem; overflow-wrap: anywhere; line-height: 1.35; }
.mh-fact-detail { color: var(--muted); font-size: 0.82rem; overflow-wrap: anywhere; line-height: 1.45; }
.mh-fact-src { color: var(--faint); font-size: 0.7rem; font-family: var(--mono); margin-top: 2px; }
.mh-fact-link { font-size: 0.74rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mh-fact-link a { color: var(--a1); text-decoration: none; }
.mh-fact-link a:hover { text-decoration: underline; }

.mh-cand { display: flex; align-items: center; gap: 14px; background: var(--panel-2); border: 1px solid var(--line);
  border-radius: 12px; padding: 11px 14px; }
.mh-cand-ico { width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; font-size: 1.05rem;
  background: var(--panel-3); flex: none; }
.mh-cand-nome { font-weight: 700; color: var(--text); }
.mh-cand-doc { font-family: var(--mono); font-size: 0.8rem; color: var(--a1); margin-left: 10px; }
.mh-cand-det { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }

.mh-tl-row { display: flex; gap: 14px; padding: 9px 0; border-bottom: 1px dashed var(--line); font-size: 0.88rem; }
.mh-tl-date { font-family: var(--mono); color: var(--a1); min-width: 96px; font-size: 0.8rem; padding-top: 1px; }
.mh-tl-src { color: var(--faint); font-size: 0.72rem; }
.mh-chip { display: inline-block; border: 1px solid var(--line-2); border-radius: 999px; padding: 2px 10px;
  font-size: 0.76rem; font-weight: 600; margin: 0 6px 6px 0; }
.mh-chip.on { color: var(--ok); border-color: rgba(61, 220, 151, 0.4); }
.mh-chip.off { color: var(--faint); }
.mh-quick-links { display: flex; flex-wrap: wrap; gap: 8px; }
.legenda, .dica { color: var(--muted); font-size: 0.82rem; }

/* ── diretório de fontes ──────────────────────────────────────────────── */
.mh-dir-grade { display: grid; grid-template-columns: repeat(auto-fill, minmax(255px, 1fr)); gap: 10px; }
.mh-dir { display: flex; flex-direction: column; gap: 5px; padding: 13px 15px; border-radius: 12px;
  border: 1px solid var(--line); background: var(--panel-2); text-decoration: none !important;
  transition: transform .12s, border-color .12s, background .12s; }
.mh-dir:hover { transform: translateY(-2px); border-color: var(--a1); background: var(--panel-3); }
.mh-dir-nome { font-weight: 700; color: var(--text); font-size: 0.92rem; }
.mh-dir-txt { color: var(--muted); font-size: 0.8rem; line-height: 1.4; flex: 1; }
.mh-dir-tags { display: flex; gap: 10px; flex-wrap: wrap; font-size: 0.7rem; color: var(--faint); margin-top: 3px; }
.mh-dir-tags .gratis { color: var(--ok); }
.mh-dir-tags .login { color: var(--a1); }
.mh-dir-tags .pago { color: var(--warn); }
"""

# Cor do rótulo de confiança de cada fato (usada como --c nos cartões).
COR_CONFIANCA = {"alta": "#3ddc97", "media": "#f5b942", "baixa": "#ff7b7b", "indicio": "#66728c"}


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
