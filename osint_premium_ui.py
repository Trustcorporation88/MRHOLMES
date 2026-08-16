"""UI Streamlit do hub OSINT Premium — Robin roda nesta página."""

from __future__ import annotations

import html as _html

import streamlit as st

from osint_premium import (
    FEATURED,
    NATIVE_SUITES,
    PLAYBOOKS,
    premium_stats,
    queue_navigation,
    search_catalog,
    search_featured,
    search_native,
)
from investigate_workspace import display_investigate_workspace
from osint_partners import ARSENAL_PICKS, FLOWSINT_ENRICHERS, FLOWSINT_SITE, FLOWSINT_URL, ARSENAL_URL
from external_services import get_all_categories
from robin_workspace import display_robin_workspace


def go_to_page(page_id: str, osint_tool: str | None = None, premium_view: str | None = None) -> None:
    queue_navigation(st.session_state, page_id, osint_tool, premium_view)
    st.rerun()


def open_robin() -> None:
    queue_navigation(st.session_state, "OSINT Premium", premium_view="robin")
    st.rerun()


def open_partners() -> None:
    queue_navigation(st.session_state, "OSINT Premium", premium_view="partners")
    st.rerun()


def _open_suite(suite: dict) -> None:
    view = suite.get("premium_view")
    if view == "robin" or suite.get("id") == "robin":
        open_robin()
    elif view:
        go_to_page("OSINT Premium", premium_view=view)
    else:
        go_to_page(suite["page"], suite.get("osint_tool"))


def _kind_chip(kind: str) -> str:
    return {
        "lookup": "Lookup",
        "analise": "Análise",
        "catalogo": "Catálogo",
        "tool": "Ferramenta",
        "native": "Nativo",
        "external": "Oficial",
        "note": "Nota",
    }.get(kind, kind)


def display_osint_premium() -> None:
    stats = premium_stats()
    views = [
        ("partners", "0 · Investigar"),
        ("playbooks", "1 · Playbooks"),
        ("native", f"2 · Suites ({stats['native']})"),
        ("featured", f"3 · Destaques ({stats['featured']})"),
        ("catalog", f"4 · Catálogo ({stats['catalog']})"),
        ("robin", "5 · Robin (.onion)"),
    ]
    if st.session_state.get("premium_view") not in {v[0] for v in views}:
        st.session_state.premium_view = "partners"
    view = st.session_state.premium_view

    if view not in ("robin", "partners"):
        st.html(
            f"""
            <div class="mh-premium-hero">
              <div class="mh-dork-kicker">OSINT Premium</div>
              <h2>Investigar neste console</h2>
              <p>
                <strong>Flowsint</strong> é o grafo (Docker oficial).
                <strong>Arsenal</strong> é o índice OSINT (sem red team).
                <strong>Robin</strong> continua na aba 5 — só briefing .onion com LLM.
              </p>
              <div class="mh-tools-stats">
                <span class="mh-tools-stat"><strong>Flowsint</strong> fluxo</span>
                <span class="mh-tools-stat"><strong>{len(ARSENAL_PICKS)}</strong> arsenal OSINT</span>
                <span class="mh-tools-stat"><strong>{stats['playbooks']}</strong> playbooks</span>
                <span class="mh-tools-stat"><strong>{stats['catalog']}</strong> fontes</span>
              </div>
            </div>
            """
        )

    cols = st.columns(len(views))
    for i, (vid, label) in enumerate(views):
        active = view == vid
        with cols[i]:
            if st.button(
                label,
                key=f"premium_view_{vid}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                st.session_state.premium_view = vid
                st.rerun()

    if view == "partners":
        display_investigate_workspace()
        if not st.session_state.get("investigate_active"):
            with st.expander("Flowsint e Arsenal (atalhos)", expanded=False):
                _render_partners()
    elif view == "robin":
        display_robin_workspace()
    elif view == "playbooks":
        _render_playbooks()
    elif view == "native":
        _render_native()
    elif view == "featured":
        _render_featured()
    else:
        _render_catalog()

    st.caption(
        "Educacional · alvos autorizados · Flowsint Apache-2.0 © reconurge · "
        "Arsenal MIT © rawfilejson · Robin MIT © Apurv Singh Gautam · "
        "sem phishing/RAT/DDoS."
    )


def _render_step_row(prefix: str, i: int, step: dict) -> None:
    kind = step.get("kind", "note")
    cols = st.columns([6, 2])
    with cols[0]:
        st.markdown(f"**{i}. {step['label']}**")
        st.caption(f"{_kind_chip(kind)} · {step.get('detail', '')}")
    with cols[1]:
        if kind == "tool" or step.get("premium_view") == "robin":
            if st.button("Usar ferramenta", key=f"{prefix}_{i}", use_container_width=True):
                open_robin()
        elif kind == "native":
            if st.button("Abrir módulo", key=f"{prefix}_{i}", use_container_width=True):
                go_to_page(step["page"], step.get("osint_tool"))
        elif kind == "external" and step.get("url"):
            st.link_button("Abrir oficial →", step["url"], use_container_width=True)
        else:
            st.caption("Siga a nota")


def _render_partners() -> None:
    st.markdown(
        "Atalhos se o dossiê não bastar: o app **Flowsint** (Docker) e a fatia OSINT do Arsenal."
    )
    c1, c2, c3 = st.columns(3)
    c1.link_button("Flowsint no GitHub →", FLOWSINT_URL, use_container_width=True)
    c2.link_button("flowsint.io →", FLOWSINT_SITE, use_container_width=True)
    c3.link_button("Arsenal OSINT →", ARSENAL_URL, use_container_width=True)
    st.caption(
        "Arsenal tem 753 tools e scripts de red team. **Não** rode `install.sh` / `redteam.sh` "
        "a partir deste site. Só os atalhos OSINT da lista abaixo."
    )

    st.subheader("Fluxo Flowsint → Holmes")
    for i, step in enumerate(FLOWSINT_ENRICHERS, 1):
        _render_step_row("flw", i, step)

    st.subheader("Fatia OSINT do Arsenal")
    groups = {}
    for item in ARSENAL_PICKS:
        groups.setdefault(item.get("group") or "outros", []).append(item)
    labels = {
        "username": "Username / social",
        "email": "Email",
        "corp": "Empresa / registros",
        "geoint": "GEOINT",
        "index": "Índice",
    }
    for gid, items in groups.items():
        st.markdown(f"**{labels.get(gid, gid)}**")
        row = st.columns(3)
        for i, item in enumerate(items):
            with row[i % 3]:
                with st.container(border=True):
                    st.markdown(f"{item.get('icon', '🔗')} **{item['name']}**")
                    st.caption(item.get("description", ""))
                    st.link_button("Abrir oficial →", item["url"], use_container_width=True)
            if (i % 3) == 2 and i < len(items) - 1:
                row = st.columns(3)


def _render_playbooks() -> None:
    st.markdown("Receitas de investigação. Passos nativos e o Robin abrem a ferramenta, não um site.")
    labels = [f"{p['icon']} {p['title']}" for p in PLAYBOOKS]
    pick = st.radio("Playbook", labels, horizontal=True, key="premium_playbook")
    book = PLAYBOOKS[labels.index(pick)]

    st.html(
        f'<div class="mh-osint-panel"><h3>{_html.escape(book["icon"])} '
        f'{_html.escape(book["title"])}</h3>'
        f'<p class="mh-osint-desc">{_html.escape(book["goal"])}</p></div>'
    )

    for i, step in enumerate(book["steps"], 1):
        _render_step_row(f"pb_{book['id']}", i, step)


def _render_native() -> None:
    q = st.text_input("Filtrar suites", key="premium_native_q", placeholder="robin, telefone, dorks…")
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
                label = "Usar ferramenta" if suite.get("kind") == "tool" else "Ir para o módulo"
                if st.button(label, key=f"nat_{suite['id']}", use_container_width=True):
                    _open_suite(suite)
        if (i % 3) == 2 and i < len(items) - 1:
            row = st.columns(3)


def _render_featured() -> None:
    st.markdown(
        "Destaques. **Flowsint / Arsenal** abrem a aba Investigar. "
        "**Robin** abre o briefing .onion. O resto vai ao módulo Holmes ou ao site oficial."
    )
    q = st.text_input("Filtrar destaques", key="premium_feat_q", placeholder="robin, leaks, grafo…")
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

            if item.get("premium_view") == "robin" or item.get("in_app"):
                if st.button("Usar ferramenta agora", key=f"feat_run_{item['id']}", use_container_width=True):
                    open_robin()
            elif item.get("premium_view") == "partners":
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Abrir fluxo no Holmes", key=f"feat_run_{item['id']}", use_container_width=True):
                        open_partners()
                with b2:
                    if item.get("url"):
                        st.link_button("Repo oficial →", item["url"], use_container_width=True)
            else:
                b1, b2 = st.columns(2)
                with b1:
                    if item.get("native_page"):
                        if st.button(
                            "Abrir no Holmes",
                            key=f"feat_go_{item['id']}",
                            use_container_width=True,
                        ):
                            go_to_page(item["native_page"], item.get("osint_tool"))
                    elif item.get("url"):
                        st.link_button("Abrir serviço →", item["url"], use_container_width=True)
                with b2:
                    if item.get("url") and item.get("native_page"):
                        st.link_button("Site oficial →", item["url"], use_container_width=True)


def _render_catalog() -> None:
    cats = get_all_categories()
    cat_keys = ["todas"] + list(cats.keys())
    cat_labels = {
        "todas": "Todas as categorias",
        **{k: f"{v.get('icon', '')} {v.get('label', k)}" for k, v in cats.items()},
    }

    c1, c2 = st.columns([2.2, 1])
    with c1:
        q = st.text_input("Buscar no catálogo", key="premium_cat_q", placeholder="robin, sherlock, hibp…")
    with c2:
        cat_pick = st.selectbox(
            "Categoria",
            cat_keys,
            format_func=lambda k: cat_labels.get(k, k),
            key="premium_cat_key",
        )

    want = None if cat_pick == "todas" else cat_pick
    items = search_catalog(q, want)
    st.caption(f"{len(items)} fontes visíveis · Robin abre in-app; o resto é atalho oficial")

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
                if svc.get("id") == "robin":
                    if st.button("Usar ferramenta", key=f"prem_cat_robin_{i}", use_container_width=True):
                        open_robin()
                else:
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
