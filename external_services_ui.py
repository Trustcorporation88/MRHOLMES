"""
UI Streamlit — serviços externos por categoria.
Usa componentes nativos (sem HTML aninhado) para não quebrar no Streamlit.
"""

import streamlit as st

from external_services import get_all_categories, get_services_for_page


def _source_label(src: str) -> str:
    s = (src or "").strip().lower()
    if s == "github":
        return "GitHub"
    if s == "web":
        return "Web"
    if s == "custom":
        return "Link"
    return src.upper() if src else ""


def _render_service_cards(services: list[dict], cols: int = 3):
    """Grid nativo — nunca vaza HTML cru na tela."""
    if not services:
        st.info("Nenhum serviço nesta categoria.")
        return

    row = st.columns(cols)
    for i, svc in enumerate(services):
        with row[i % cols]:
            icon = svc.get("icon") or "🔗"
            name = svc.get("name") or "Serviço"
            desc = svc.get("description") or ""
            use_for = svc.get("use_for") or ""
            url = (svc.get("url") or "").strip()
            badge = _source_label(svc.get("source") or "")

            with st.container(border=True):
                title = f"{icon} **{name}**"
                if badge:
                    title += f" · `{badge}`"
                st.markdown(title)
                if desc:
                    st.caption(desc)
                if use_for:
                    st.markdown(f"📌 {use_for}")
                if url:
                    st.link_button("Abrir →", url, use_container_width=True)
                else:
                    st.caption("Sem URL")
        if (i % cols) == (cols - 1) and i < len(services) - 1:
            row = st.columns(cols)


def _render_category_block(cat_key: str, cat: dict):
    services = cat.get("services") or []
    label = cat.get("label", cat_key)
    icon = cat.get("icon", "🔗")
    desc = cat.get("description", "")

    st.subheader(f"{icon} {label}")
    meta = st.columns([4, 1])
    with meta[0]:
        if desc:
            st.caption(desc)
    with meta[1]:
        st.metric("Itens", len(services), label_visibility="collapsed")
    _render_service_cards(services, cols=3)


def display_external_services(title: bool = True):
    """Catálogo com abas por categoria."""
    if title:
        st.markdown("### Serviços externos")
        st.caption("Escolha a categoria na aba. Cada link fica só no bloco certo.")

    cats = get_all_categories()
    if not cats:
        st.warning("Catálogo vazio.")
        return

    labels = [f"{c.get('icon', '🔗')} {c.get('label', k)}" for k, c in cats.items()]
    keys = list(cats.keys())
    tabs = st.tabs(labels)
    for tab, key in zip(tabs, keys):
        with tab:
            _render_category_block(key, cats[key])


def display_services_for_page(page_key: str, heading: str | None = None):
    """Só serviços da página atual."""
    blocks = get_services_for_page(page_key)
    if not blocks:
        return

    title = heading or "Fontes externas"
    st.markdown(f"#### {title}")
    st.caption("Links da categoria — abrem em nova aba. Uso educacional · alvos autorizados.")

    if len(blocks) == 1:
        _render_category_block(blocks[0][0], blocks[0][1])
    else:
        tabs = st.tabs(
            [f"{b[1].get('icon', '')} {b[1].get('label', b[0])}" for b in blocks]
        )
        for tab, (_k, cat) in zip(tabs, blocks):
            with tab:
                _render_category_block(_k, cat)


def display_services_grid():
    display_external_services(title=True)
