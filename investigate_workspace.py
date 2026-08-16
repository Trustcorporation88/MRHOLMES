"""Campo único: nome → dossiê (OpenAI web_search + fontes públicas)."""

from __future__ import annotations

import streamlit as st

from Core.Support.Investigate import answer_followup, classify_target, run_name_investigation
from Core.Support.Robin.llm_bridge import list_models, provider_status
from robin_workspace import render_llm_key_fields, sync_llm_keys_from_session


def display_investigate_workspace() -> None:
    sync_llm_keys_from_session()
    st.markdown("**Digite o alvo abaixo.** A OpenAI busca na web e o Holmes consulta Wikipedia, GitHub, email/MX e Maigret quando couber.")

    pending = st.session_state.pop("investigate_pending", None)
    if pending:
        st.session_state.investigate_q = pending

    with st.form("investigate_form", clear_on_submit=False):
        query = st.text_input(
            "Nome, username, email ou domínio",
            placeholder="Ex.: joaosilva   ·   Maria Silva   ·   alvo autorizado",
            key="investigate_q",
        )
        run = st.form_submit_button("Investigar", type="primary", use_container_width=True)

    render_llm_key_fields()
    status = provider_status()
    models = [m["id"] for m in list_models() if m.get("provider") == "openai"] or [
        m["id"] for m in list_models()
    ]
    model = models[0] if models else "gpt-4o-mini"
    oa = "●" if status.get("openai") else "○"
    st.caption(f"OpenAI {oa} · modelo `{model}` · alvos autorizados · fontes abertas")

    if run and (query or "").strip():
        kind = classify_target(query)
        with st.spinner(f"Investigando `{query.strip()}` ({kind})…"):
            result = run_name_investigation(query, model=model)
        if not result.get("ok"):
            st.error(result.get("error") or "Falha na investigação.")
        else:
            st.session_state.investigate_active = result
            st.session_state.investigate_chat = []
            if result.get("web_ok"):
                st.success("Dossiê pronto · OpenAI web_search + fontes locais")
            else:
                st.warning(
                    "OpenAI web_search não respondeu. Dossiê com fontes locais. "
                    f"{result.get('web_error') or result.get('llm_error') or ''}"
                )

    inv = st.session_state.get("investigate_active")
    if not inv:
        st.caption("O relatório aparece nesta tela. Robin (.onion) fica na aba 5.")
        return

    st.markdown(inv.get("dossier") or "_Sem dossiê._")

    links = inv.get("links") or []
    if links:
        st.markdown("**Abrir nos serviços oficiais**")
        cols = st.columns(min(4, len(links)))
        for i, item in enumerate(links[:8]):
            cols[i % len(cols)].link_button(item["name"], item["url"], use_container_width=True)

    cites = inv.get("citations") or []
    if cites:
        with st.expander(f"Fontes ({len(cites)})", expanded=False):
            for item in cites[:30]:
                title = item.get("title") or item.get("url")
                url = item.get("url") or ""
                st.markdown(f"- [{title}]({url})" if url else f"- {title}")

    packs = inv.get("packs") or {}
    profiles = (packs.get("maigret") or {}).get("profiles") or []
    if profiles:
        with st.expander(f"Maigret ({len(profiles)} perfis)", expanded=False):
            for p in profiles[:40]:
                st.markdown(f"- {p.get('site')}: {p.get('url')}")

    st.divider()
    st.caption("Pergunte sobre este dossiê")
    for turn in st.session_state.get("investigate_chat") or []:
        with st.chat_message(turn.get("role", "assistant")):
            st.markdown(turn.get("content", ""))
    follow = st.chat_input("Ex.: quais handles vale checar no Maigret?")
    if follow:
        history = st.session_state.setdefault("investigate_chat", [])
        answer = answer_followup(model, follow, inv, history=history)
        history.append({"role": "user", "content": follow})
        history.append({"role": "assistant", "content": answer})
        st.rerun()
