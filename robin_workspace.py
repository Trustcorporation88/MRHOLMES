"""Console Robin embutido — a ferramenta roda aqui, não num link."""

from __future__ import annotations

import base64
from datetime import datetime

import streamlit as st

from Core.Support.Robin.engine import (
    PRESET_LABELS,
    answer_followup,
    load_investigations,
    run_investigation,
    suggest_pivots,
    tool_status,
)


def _status_chips() -> dict:
    status = tool_status()
    tor = "on" if status["tor"] else "off"
    llm = "on" if status["llm"] else "off"
    st.html(
        f"""
        <div style="margin:0 0 0.85rem 0">
          <span class="mh-chip {tor}">{"●" if status["tor"] else "○"} Tor :9050</span>
          <span class="mh-chip {llm}">{"●" if status["llm"] else "○"} LLM</span>
        </div>
        """
    )
    if not status["tor"]:
        st.info(
            "Tor não está na porta 9050. A busca ainda roda pela Ahmia (clearnet). "
            "Scrape de páginas .onion fica limitado até o proxy subir (`apt install tor` / `brew install tor`)."
        )
    if not status["llm"]:
        st.info(
            "Nenhum LLM configurado. A ferramenta busca e lista fontes; o briefing completo "
            "aparece quando você define OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "OPENROUTER_API_KEY ou sobe o Ollama."
        )
    return status


def _render_report(inv: dict) -> None:
    sources = inv.get("sources") or []
    with st.expander("📋 Notes", expanded=False):
        st.markdown(f"**Query:** `{inv.get('query', '')}`")
        st.markdown(f"**Refinada:** `{inv.get('refined_query') or inv.get('refined', '')}`")
        st.markdown(
            f"**Modelo:** `{inv.get('model', '—')}` · **Domínio:** {inv.get('preset') or inv.get('preset_key', '')}"
        )
        flags = []
        if inv.get("via_tor"):
            flags.append("Tor")
        if inv.get("via_clearnet"):
            flags.append("Ahmia clearnet")
        st.caption(
            f"Fontes: {len(sources)} · Resultados brutos: {inv.get('results_count', len(sources))} · "
            + (" · ".join(flags) or "sem canal anotado")
        )
    with st.expander(f"🔗 Sources ({len(sources)})", expanded=False):
        if not sources:
            st.caption("Nenhuma fonte nesta rodada.")
        for i, item in enumerate(sources, 1):
            title = item.get("title") or "Untitled"
            link = item.get("link") or ""
            st.markdown(f"{i}. [{title}]({link})" if link else f"{i}. {title}")

    st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
    summary = inv.get("summary") or ""
    st.markdown(summary or "_Sem relatório._")
    if summary:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        b64 = base64.b64encode(summary.encode()).decode()
        st.markdown(
            f'<a href="data:text/markdown;base64,{b64}" download="summary_{now}.md">📥 Download do relatório</a>',
            unsafe_allow_html=True,
        )


def _render_chat(inv: dict, model: str | None) -> None:
    st.divider()
    st.subheader(":red[💬 Follow-up]", anchor=None, divider="gray")
    pivots = st.session_state.get("robin_pivots") or []
    if pivots:
        st.caption("Pivôs sugeridos — clicar inicia outra investigação:")
        cols = st.columns(len(pivots))
        for i, (col, pq) in enumerate(zip(cols, pivots)):
            if col.button(f"🔎 {pq}", key=f"robin_pivot_{i}", use_container_width=True):
                st.session_state.robin_pivot_query = pq
                st.rerun()

    for turn in st.session_state.get("robin_chat") or []:
        with st.chat_message(turn.get("role", "assistant")):
            st.markdown(turn.get("content", ""))

    if st.session_state.get("robin_chat"):
        if st.button("Limpar chat", key="robin_clear_chat"):
            st.session_state.robin_chat = []
            st.rerun()

    followup = st.chat_input("Pergunte sobre esta investigação")
    if followup:
        history = st.session_state.setdefault("robin_chat", [])
        answer = answer_followup(model or inv.get("model"), followup, inv, history=history)
        history.append({"role": "user", "content": followup})
        history.append({"role": "assistant", "content": answer})
        st.rerun()


def display_robin_workspace() -> None:
    st.html(
        """
        <div class="mh-osint-panel">
          <h3>Robin — investigação no console</h3>
          <p class="mh-osint-desc">
            Pipeline educacional embutido (MIT © Apurv Singh Gautam):
            refina a query, busca motores .onion / Ahmia, filtra, raspa texto e
            monta o dossiê. Uso em alvos autorizados.
          </p>
        </div>
        """
    )
    status = _status_chips()
    models = status.get("models") or []
    model_ids = [m["id"] for m in models]
    labels = {m["id"]: m["label"] for m in models}

    saved = load_investigations()
    c_model, c_preset, c_hist = st.columns([1.4, 1.2, 1.4])
    with c_model:
        model = None
        if model_ids:
            model = st.selectbox(
                "Modelo",
                model_ids,
                format_func=lambda mid: labels.get(mid, mid),
                key="robin_model",
            )
        else:
            st.selectbox("Modelo", ["heurístico (sem API)"], disabled=True, key="robin_model_off")
    with c_preset:
        preset = st.selectbox(
            "Domínio",
            list(PRESET_LABELS.keys()),
            format_func=lambda k: PRESET_LABELS[k],
            key="robin_preset",
        )
    with c_hist:
        hist_labels = ["(investigação atual)"] + [
            f"{item.get('_filename', '')} — {(item.get('query') or '')[:32]}"
            for item in saved
        ]
        picked = st.selectbox("Passadas", hist_labels, key="robin_hist")
        if picked != "(investigação atual)" and st.button("Carregar", key="robin_load"):
            idx = hist_labels.index(picked) - 1
            loaded = dict(saved[idx])
            loaded.setdefault("refined_query", loaded.get("refined", ""))
            st.session_state.robin_active = loaded
            st.session_state.robin_chat = []
            st.session_state.robin_pivots = []
            st.rerun()

    extra = st.text_area(
        "Instruções extras (opcional)",
        key="robin_extra",
        height=70,
        placeholder="Ex.: priorizar wallets e nomes de fóruns citados no texto.",
    )
    t1, t2, t3 = st.columns(3)
    threads = t1.slider("Threads", 1, 8, 4, key="robin_threads")
    max_results = t2.slider("Máx. resultados", 10, 80, 40, key="robin_max_results")
    max_scrape = t3.slider("Máx. páginas", 3, 16, 8, key="robin_max_scrape")

    pending = st.session_state.pop("robin_pivot_query", None)
    if pending:
        st.session_state.robin_query = pending
    with st.form("robin_form", clear_on_submit=False):
        query = st.text_input(
            "Query",
            placeholder="Ex.: vazamento credenciais domínio autorizado",
            label_visibility="collapsed",
            key="robin_query",
        )
        run = st.form_submit_button("Investigar", use_container_width=True)

    if (run and (query or "").strip()) or pending:
        active_query = (pending or query or "").strip()
        with st.spinner("Rodando pipeline Robin (busca → filtro → scrape → relatório)…"):
            result = run_investigation(
                active_query,
                model=model,
                preset=preset,
                custom_instructions=extra or "",
                threads=threads,
                max_results=max_results,
                max_scrape=max_scrape,
            )
        if not result.get("ok"):
            st.error(result.get("error") or "Falha na investigação.")
        else:
            st.session_state.robin_active = result
            st.session_state.robin_chat = []
            try:
                st.session_state.robin_pivots = suggest_pivots(
                    model, active_query, result.get("scraped") or {},
                )
            except Exception:
                st.session_state.robin_pivots = []
            st.success(f"Concluído · salvo em `{result.get('filename')}`")

    inv = st.session_state.get("robin_active")
    if inv:
        _render_report(inv)
        _render_chat(inv, model)
    else:
        st.caption("Digite a query e clique em Investigar. O relatório aparece nesta mesma tela.")
