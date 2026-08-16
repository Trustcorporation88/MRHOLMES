"""Campo único: nome → dossiê (OpenAI web_search + fontes públicas)."""

from __future__ import annotations

import streamlit as st

from Core.Support.Investigate import answer_followup, classify_target, run_name_investigation
from Core.Support.Robin.llm_bridge import list_models, provider_status
from robin_workspace import render_llm_key_fields, sync_llm_keys_from_session


def display_investigate_workspace() -> None:
    sync_llm_keys_from_session()
    st.markdown(
        "**Cole o alvo e clique em Investigar.** A chave OpenAI orquestra os módulos do Holmes "
        "(Maigret, Holehe, email, domínio) e completa com busca web. Você não precisa abrir os serviços."
    )

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
    ids = [m["id"] for m in list_models() if m.get("provider") == "openai"]
    if "gpt-4o" in ids:
        model = "gpt-4o"
    elif ids:
        model = ids[0]
    else:
        model = "gpt-4o"
    oa = "●" if status.get("openai") else "○"
    st.caption(f"OpenAI {oa} · `{model}` usa Maigret/Holehe/email do site + busca web · alvos autorizados")

    if run and (query or "").strip():
        kind = classify_target(query)
        with st.spinner("Rodando módulos Holmes e busca OpenAI…"):
            result = run_name_investigation(query, model=model)
        if not result.get("ok"):
            st.error(result.get("error") or "Falha na investigação.")
        else:
            st.session_state.investigate_active = result
            st.session_state.investigate_chat = []
            if result.get("web_ok"):
                st.success("Dossiê pronto — a API buscou e consolidou as fontes")
            else:
                st.warning(
                    "A busca web da OpenAI falhou. Mostrando só o que as APIs locais acharam. "
                    f"{result.get('web_error') or result.get('llm_error') or ''}"
                )

    inv = st.session_state.get("investigate_active")
    if not inv:
        st.caption("O relatório aparece nesta tela. Robin (.onion) fica na aba 5.")
        return

    st.markdown(inv.get("dossier") or "_Sem dossiê._")

    used = inv.get("tools_used") or []
    if used:
        st.caption("Módulos usados: " + " · ".join(used))

    cites = inv.get("citations") or []
    if cites:
        with st.expander(f"Fontes ({len(cites)})", expanded=False):
            for item in cites[:40]:
                title = item.get("title") or item.get("url")
                url = item.get("url") or ""
                st.markdown(f"- [{title}]({url})" if url else f"- {title}")

    packs = inv.get("packs") or {}
    profiles = []
    for key, pack in packs.items():
        if str(key).startswith("maigret"):
            profiles.extend((pack or {}).get("profiles") or [])
    if profiles:
        with st.expander(f"Maigret ({len(profiles)} perfis)", expanded=True):
            for p in profiles[:40]:
                st.markdown(f"- {p.get('site')}: {p.get('url')}")

    st.divider()
    st.caption("Pergunte sobre este dossiê")
    for turn in st.session_state.get("investigate_chat") or []:
        with st.chat_message(turn.get("role", "assistant")):
            st.markdown(turn.get("content", ""))
    follow = st.chat_input("Pergunte sobre o dossiê — a API busca de novo se precisar")
    if follow:
        history = st.session_state.setdefault("investigate_chat", [])
        answer = answer_followup(model, follow, inv, history=history)
        history.append({"role": "user", "content": follow})
        history.append({"role": "assistant", "content": answer})
        st.rerun()
