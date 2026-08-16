"""
UI Streamlit — serviços externos por categoria.
Componentes nativos + filtro Web/GitHub + cards limpos.
"""

import streamlit as st

from external_services import get_all_categories, get_services_for_page


def _source_label(src: str) -> str:
    s = (src or "").strip().lower()
    if s == "github":
        return "GitHub"
    if s in ("web", "custom"):
        return "Web"
    return (src or "").upper()


def _filter_services(services: list[dict], kind: str) -> list[dict]:
    if kind == "Todos":
        return list(services)
    want = "github" if kind == "GitHub" else "web"
    out = []
    for s in services:
        src = (s.get("source") or "").lower()
        if want == "github" and src == "github":
            out.append(s)
        elif want == "web" and src != "github":
            out.append(s)
    return out


def _render_service_cards(services: list[dict], cols: int = 3, key_prefix: str = "svc"):
    if not services:
        st.info("Nenhum item com esse filtro.")
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
            sid = svc.get("id") or f"{i}"

            with st.container(border=True):
                st.markdown(f"{icon} **{name}**")
                if badge:
                    st.caption(badge)
                if desc:
                    st.markdown(desc)
                if use_for:
                    st.caption(f"Uso: {use_for}")
                native_page = svc.get("native_page")
                if native_page:
                    from osint_premium_ui import go_to_page

                    if st.button(
                        "Usar no Holmes",
                        use_container_width=True,
                        key=f"{key_prefix}_native_{sid}_{i}",
                    ):
                        go_to_page(native_page, svc.get("osint_tool"))
                if url:
                    st.link_button(
                        "Site oficial →" if native_page else "Abrir →",
                        url,
                        use_container_width=True,
                        key=f"{key_prefix}_{sid}_{i}",
                    )
        if (i % cols) == (cols - 1) and i < len(services) - 1:
            row = st.columns(cols)


def _kind_filter(key: str) -> str:
    return st.radio(
        "Tipo",
        ["Todos", "Web", "GitHub"],
        horizontal=True,
        key=key,
        label_visibility="collapsed",
    )


def _render_category_block(cat_key: str, cat: dict, show_title: bool = True):
    services = cat.get("services") or []
    label = cat.get("label", cat_key)
    icon = cat.get("icon", "🔗")
    desc = cat.get("description", "")

    if show_title:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"### {icon} {label}")
            if desc:
                st.caption(desc)
        with c2:
            st.metric("Itens", len(services))

    kind = _kind_filter(f"kind_{cat_key}")
    filtered = _filter_services(services, kind)
    st.caption(f"Mostrando **{len(filtered)}** de {len(services)}")
    _render_service_cards(filtered, cols=3, key_prefix=f"cat_{cat_key}")


def display_external_services(title: bool = True):
    if title:
        st.markdown("### Links externos por categoria")
        st.caption("Uma aba = uma finalidade. Filtre Web ou GitHub dentro da aba.")

    cats = get_all_categories()
    if not cats:
        st.warning("Catálogo vazio.")
        return

    labels = [f"{c.get('icon', '🔗')} {c.get('label', k)}" for k, c in cats.items()]
    keys = list(cats.keys())
    tabs = st.tabs(labels)
    for tab, key in zip(tabs, keys):
        with tab:
            _render_category_block(key, cats[key], show_title=False)
            st.caption(cats[key].get("description", ""))


def display_services_for_page(page_key: str, heading: str | None = None):
    blocks = get_services_for_page(page_key)
    if not blocks:
        return

    title = heading or "Fontes externas"
    st.markdown(f"#### {title}")
    st.caption("Atalhos externos — abrem em nova aba. Educacional · alvos autorizados.")

    if len(blocks) == 1:
        _render_category_block(blocks[0][0], blocks[0][1], show_title=True)
    else:
        tabs = st.tabs(
            [f"{b[1].get('icon', '')} {b[1].get('label', b[0])}" for b in blocks]
        )
        for tab, (k, cat) in zip(tabs, blocks):
            with tab:
                _render_category_block(k, cat, show_title=False)
                if cat.get("description"):
                    st.caption(cat["description"])


def display_services_grid():
    display_external_services(title=True)
