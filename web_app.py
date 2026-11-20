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

import tema

tema.aplicar()

from pathlib import Path

_ASSETS = Path(__file__).parent / "assets"
st.logo(str(_ASSETS / "logo.png"), icon_image=str(_ASSETS / "icone.png"), size="large")


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

    sync_llm_keys_from_session()
    try:
        from Core.Support.Robin.engine import tool_status as _ts
        _prov = _ts().get("providers") or {}
    except Exception:
        _prov = {}
    st.html(
        '<div class="mh-side-foot">'
        f'<span class="mh-dot {"on" if _prov.get("openai") else ""}"></span>OpenAI &nbsp; '
        f'<span class="mh-dot {"on" if _prov.get("anthropic") else ""}"></span>Claude'
        '<br>Uso profissional, com finalidade legítima (LGPD).</div>'
    )


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
