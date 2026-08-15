"""UI Streamlit do hub OSINT Premium."""

from __future__ import annotations

import html as _html

import streamlit as st

from osint_premium import (
    FEATURED,
    NATIVE_SUITES,
    PLAYBOOKS,
    premium_stats,
    search_catalog,
    search_featured,
    search_native,
)
from external_services import get_all_categories


def go_to_page(page_id: str, osint_tool: str | None = None) -> None:
    if osint_tool:
        st.session_state.osint_adv_tool = osint_tool
    st.session_state.nav_page = page_id
    st.rerun()


def _kind_chip(kind: str) -> str:
    return {
        "lookup": "Lookup",
        "analise": "Análise",
        "catalogo": "Catálogo",
        "native": "Nativo",
        "external": "Oficial",
        "note": "Nota",
    }.get(kind, kind)


def display_osint_premium() -> None:
    stats = premium_stats()
    st.html(
        f"""
        <div class="mh-premium-hero">
          <div class="mh-dork-kicker">OSINT Premium</div>
          <h2>Um espaço, todos os serviços</h2>
          <p>
            Hub educacional do Mr.Holmes: módulos nativos, catálogo já curado e
            destaques oficiais (incluindo <strong>Robin</strong>).
            Ferramentas de terceiros abrem no site/repo original — este console
            não copia código nem sobe Tor.
          </p>
          <div class="mh-tools-stats">
            <span class="mh-tools-stat"><strong>{stats['playbooks']}</strong> playbooks</span>
            <span class="mh-tools-stat"><strong>{stats['native']}</strong> suites nativas</span>
            <span class="mh-tools-stat"><strong>{stats['featured']}</strong> destaques</span>
            <span class="mh-tools-stat"><strong>{stats['catalog']}</strong> fontes no catálogo</span>
          </div>
        </div>
        """
    )

    tab_play, tab_native, tab_feat, tab_cat = st.tabs(
        [
            "1 · Playbooks",
            f"2 · Suites nativas ({stats['native']})",
            f"3 · Destaques ({stats['featured']})",
            f"4 · Catálogo ({stats['catalog']})",
        ]
    )

    with tab_play:
        _render_playbooks()
    with tab_native:
        _render_native()
    with tab_feat:
        _render_featured()
    with tab_cat:
        _render_catalog()

    st.caption(
        "Educacional · alvos autorizados · sem phishing/RAT/DDoS · "
        "Robin e demais projetos oficiais permanecem nos repositórios originais."
    )


def _render_playbooks() -> None:
    st.markdown(
        "Receitas de investigação. Cada passo abre o módulo Holmes ou o link oficial."
    )
    labels = [f"{p['icon']} {p['title']}" for p in PLAYBOOKS]
    pick = st.radio("Playbook", labels, horizontal=True, key="premium_playbook")
    book = PLAYBOOKS[labels.index(pick)]

    st.html(
        f'<div class="mh-osint-panel"><h3>{_html.escape(book["icon"])} '
        f'{_html.escape(book["title"])}</h3>'
        f'<p class="mh-osint-desc">{_html.escape(book["goal"])}</p></div>'
    )

    for i, step in enumerate(book["steps"], 1):
        kind = step.get("kind", "note")
        cols = st.columns([6, 2])
        with cols[0]:
            st.markdown(f"**{i}. {step['label']}**")
            st.caption(f"{_kind_chip(kind)} · {step.get('detail', '')}")
        with cols[1]:
            if kind == "native":
                if st.button(
                    "Abrir módulo",
                    key=f"pb_{book['id']}_{i}",
                    use_container_width=True,
                ):
                    go_to_page(step["page"], step.get("osint_tool"))
            elif kind == "external" and step.get("url"):
                st.link_button(
                    "Abrir oficial →",
                    step["url"],
                    use_container_width=True,
                )
            else:
                st.caption("Siga a nota")


def _render_native() -> None:
    q = st.text_input(
        "Filtrar suites",
        key="premium_native_q",
        placeholder="telefone, dorks, grafo…",
    )
    items = search_native(q)
    if not items:
        st.info("Nenhuma suite com esse filtro.")
        return

    row = st.columns(3)
    for i, suite in enumerate(items):
        with row[i % 3]:
            with st.container(border=True):
                st.markdown(f"{suite['icon']} **{suite['title']}**")
                st.caption(_kind_chip(suite["kind"]))
                st.markdown(suite["blurb"])
                if st.button(
                    "Ir para o módulo",
                    key=f"nat_{suite['id']}",
                    use_container_width=True,
                ):
                    go_to_page(suite["page"], suite.get("osint_tool"))
        if (i % 3) == 2 and i < len(items) - 1:
            row = st.columns(3)


def _render_featured() -> None:
    st.markdown(
        "Projetos oficiais que **complementam** o Holmes. "
        "O Robin não é embutido: o entregável dele (relatório + JSON + chat) "
        "fica no container/repo original."
    )
    q = st.text_input(
        "Filtrar destaques",
        key="premium_feat_q",
        placeholder="robin, leaks, grafo…",
    )
    items = search_featured(q) if q else list(FEATURED)

    for item in items:
        with st.container(border=True):
            h1, h2 = st.columns([4, 1])
            with h1:
                st.markdown(f"{item['icon']} **{item['name']}** · {item['tier']}")
                st.caption(item["tagline"])
            with h2:
                st.caption(item.get("license", ""))

            st.markdown("**O que entrega**")
            for line in item.get("delivers") or []:
                st.markdown(f"- {line}")
            st.caption(f"Complemento: {item.get('complements', '—')}")
            st.caption(f"Requisitos: {item.get('requires', '—')}")
            if item.get("author"):
                st.caption(f"Autor / origem: {item['author']}")

            b1, b2, b3 = st.columns(3)
            with b1:
                st.link_button("Repositório / site →", item["url"], use_container_width=True)
            with b2:
                docs = item.get("docs") or item["url"]
                st.link_button("Documentação →", docs, use_container_width=True)
            with b3:
                if item.get("native_page"):
                    if st.button(
                        "Módulo Holmes",
                        key=f"feat_go_{item['id']}",
                        use_container_width=True,
                    ):
                        go_to_page(item["native_page"], item.get("osint_tool"))
                else:
                    st.caption("Roda fora do Holmes")


def _render_catalog() -> None:
    cats = get_all_categories()
    cat_keys = ["todas"] + list(cats.keys())
    cat_labels = {
        "todas": "Todas as categorias",
        **{k: f"{v.get('icon', '')} {v.get('label', k)}" for k, v in cats.items()},
    }

    c1, c2 = st.columns([2.2, 1])
    with c1:
        q = st.text_input(
            "Buscar no catálogo",
            key="premium_cat_q",
            placeholder="sherlock, hibp, crt.sh…",
        )
    with c2:
        cat_pick = st.selectbox(
            "Categoria",
            cat_keys,
            format_func=lambda k: cat_labels.get(k, k),
            key="premium_cat_key",
        )

    want = None if cat_pick == "todas" else cat_pick
    items = search_catalog(q, want)
    st.caption(f"{len(items)} fontes visíveis")

    if not items:
        st.info("Nenhum item com esse filtro.")
        return

    row = st.columns(3)
    for i, svc in enumerate(items):
        with row[i % 3]:
            with st.container(border=True):
                icon = svc.get("icon") or "🔗"
                st.markdown(f"{icon} **{svc.get('name', 'Serviço')}**")
                st.caption(svc.get("category_label", ""))
                if svc.get("description"):
                    st.markdown(svc["description"])
                if svc.get("use_for"):
                    st.caption(f"Uso: {svc['use_for']}")
                url = (svc.get("url") or "").strip()
                if url:
                    st.link_button(
                        "Abrir →",
                        url,
                        use_container_width=True,
                        key=f"prem_cat_{svc.get('id', i)}_{i}",
                    )
        if (i % 3) == 2 and i < len(items) - 1:
            row = st.columns(3)
