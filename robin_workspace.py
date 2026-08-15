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
from Core.Support.Robin.llm_bridge import apply_keys, provider_status


def sync_llm_keys_from_session() -> None:
    try:
        apply_keys(
            openai=st.secrets.get("OPENAI_API_KEY"),
            anthropic=st.secrets.get("ANTHROPIC_API_KEY") or st.secrets.get("CLAUDE_API_KEY"),
        )
    except Exception:
        pass
    apply_keys(
        openai=st.session_state.get("llm_openai_key"),
        anthropic=st.session_state.get("llm_anthropic_key"),
    )


def _key_inputs() -> None:
    c1, c2 = st.columns(2)
    with c1:
        st.text_input(
            "OpenAI API key",
            type="password",
            key="llm_openai_key",
            placeholder="sk-… só se quiser trocar nesta sessão",
            help="gpt-4o / gpt-4.1. Não vai para o git.",
        )
    with c2:
        st.text_input(
            "Claude / Anthropic API key",
            type="password",
            key="llm_anthropic_key",
            placeholder="sk-ant-… só se quiser trocar nesta sessão",
            help="Claude Sonnet/Haiku. Não vai para o git.",
        )


def render_llm_key_fields() -> None:
    """Se as Variables já estão no processo, não renderiza nenhum campo de API."""
    sync_llm_keys_from_session()
    status = provider_status()
    oa, cl = bool(status.get("openai")), bool(status.get("anthropic"))
    if oa and cl:
        st.caption("OpenAI e Claude: Variables do Railway ativas. Sem campos de chave nesta tela.")
        return
    if not oa and not cl:
        st.warning(
            "Nenhuma chave no processo. Cole abaixo ou confira o nome exato "
            "no Railway: `OPENAI_API_KEY` e `ANTHROPIC_API_KEY`, depois Redeploy."
        )
        _key_inputs()
    else:
        missing = "Claude" if oa else "OpenAI"
        st.info(f"{missing} ainda não está no processo. Cole só essa chave ou ajuste a Variable.")
        _key_inputs()
    sync_llm_keys_from_session()


def _status_chips() -> dict:
    status = tool_status()
    prov = status.get("providers") or {}
    tor = "on" if status["tor"] else "off"
    oa = "on" if prov.get("openai") else "off"
    cl = "on" if prov.get("anthropic") else "off"
    st.html(
        f"""
        <div style="margin:0 0 0.85rem 0">
          <span class="mh-chip {oa}">{"●" if prov.get("openai") else "○"} OpenAI</span>
          <span class="mh-chip {cl}">{"●" if prov.get("anthropic") else "○"} Claude</span>
          <span class="mh-chip {tor}">{"●" if status["tor"] else "○"} Tor :9050 (opcional)</span>
        </div>
        """
    )
    if not status["tor"]:
        st.caption(
            "Tor ainda não subiu neste container. Depois do deploy com o pacote `tor`, "
            "o chip fica ● e a busca usa motores .onion. Enquanto isso, Ahmia (clearnet)."
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


def _robin_options(status: dict) -> tuple:
    models = status.get("models") or []
    model_ids = [m["id"] for m in models]
    labels = {m["id"]: m["label"] for m in models}
    saved = load_investigations()
    model = None
    preset = next(iter(PRESET_LABELS), "threat_intel")
    extra = ""
    threads, max_results, max_scrape = 4, 40, 8


    with st.expander("Modelo, domínio e limites", expanded=False):
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
    return model, preset, extra or "", threads, max_results, max_scrape


def display_robin_workspace() -> None:
    pending = st.session_state.pop("robin_pivot_query", None)
    if pending:
        st.session_state.robin_query = pending

    with st.form("robin_form", clear_on_submit=False):
        query = st.text_input(
            "Nome, username ou query",
            placeholder="Ex.: joaosilva   ·   alvo autorizado",
            key="robin_query",
            help="Pessoa, handle, e-mail, domínio ou frase. O relatório aparece nesta tela.",
        )
        run = st.form_submit_button("Investigar", type="primary", use_container_width=True)

    st.caption("Digite o alvo acima e clique em Investigar. Uso educacional · alvo autorizado.")

    sync_llm_keys_from_session()
    render_llm_key_fields()
    status = _status_chips()
    model, preset, extra, threads, max_results, max_scrape = _robin_options(status)

    if (run and (query or "").strip()) or pending:
        active_query = (pending or query or "").strip()
        with st.spinner("Rodando pipeline Robin (busca → filtro → scrape → relatório)…"):
            result = run_investigation(
                active_query,
                model=model,
                preset=preset,
                custom_instructions=extra,
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
            if result.get("llm_error"):
                st.warning(f"LLM: {result['llm_error']}")

    inv = st.session_state.get("robin_active")
    if inv:
        _render_report(inv)
        _render_chat(inv, model)
