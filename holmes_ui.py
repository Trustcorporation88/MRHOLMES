"""
Página «Investigar» — a caixa única do Mr.Holmes.

Você digita nome, e-mail, telefone, @usuário, CPF/CNPJ, domínio ou link de
perfil. O console detecta o tipo, consulta tudo que se aplica, encadeia os
pivôs e monta o dossiê. Sem escolher menu, sem redigitar o alvo.
"""

from __future__ import annotations

import streamlit as st

from holmes import InvestigationConfig, investigate
from holmes.connectors import ensure_registered, registry_stats
from holmes.entity import detect
from holmes.findings import FindingKind

_BADGE_COLOR = {
    "alta": "#0f9d58",
    "media": "#f4b400",
    "baixa": "#db4437",
    "indicio": "#9aa5b1",
}

_ICON = {
    "Nomes": "🪪", "Contas e perfis": "👤", "E-mails": "✉️", "Telefones": "📱",
    "Empresas": "🏢", "Endereços de cripto": "₿", "Localização": "📍", "Documentos": "📄", "Vazamentos": "🩸",
    "Domínios": "🌐", "Imagens": "🖼️", "Jurídico": "⚖️",
    "Resultados na web": "🔎", "Observações técnicas": "🔧", "Fontes para abrir": "🔗",
}


def _key_sidebar() -> None:
    """Chaves coladas aqui valem só nesta sessão — não vão para disco nem para o git."""
    from holmes import net

    with st.expander("🔑 Chaves de API (opcional — vale só nesta sessão)", expanded=False):
        st.caption(
            "O jeito recomendado é definir as variáveis no Railway. "
            "Colar aqui serve para testar rápido."
        )
        col1, col2 = st.columns(2)
        with col1:
            serper = st.text_input(
                "SERPER_API_KEY", type="password", key="k_serper",
                help="serper.dev — 2.500 buscas grátis. É a chave que mais muda o resultado.",
            )
            hibp = st.text_input("HIBP_API_KEY", type="password", key="k_hibp",
                                 help="Have I Been Pwned — vazamentos por e-mail")
            hunter = st.text_input("HUNTER_API_KEY", type="password", key="k_hunter")
        with col2:
            brave = st.text_input("BRAVE_API_KEY", type="password", key="k_brave")
            numverify = st.text_input("NUMVERIFY_API_KEY", type="password", key="k_numverify")
            openai = st.text_input("OPENAI_API_KEY", type="password", key="k_openai",
                                   help="Habilita a análise e o chat do dossiê")

        for name, val in (
            ("serper", serper), ("brave", brave), ("hibp", hibp),
            ("hunter", hunter), ("numverify", numverify), ("openai", openai),
        ):
            if val:
                net.set_runtime_key(name, val)
                if name == "openai":
                    import os

                    os.environ["OPENAI_API_KEY"] = val


def _crawler_controls(alvo: str) -> None:
    """
    Rastreamento é opt-in: é a única fonte que faz muitas requisições ao alvo.
    Só aparece quando o alvo é um endereço web, porque é o único caso em que
    faz sentido.
    """
    from holmes import crawler
    from holmes.entity import EntityType

    tipo = detect(alvo).type if alvo.strip() else None
    aplicavel = tipo in (EntityType.URL, EntityType.DOMAIN)

    with st.expander("🕸️ Rastrear o site (opcional)", expanded=False):
        if not aplicavel:
            st.caption(
                "Disponível quando o alvo é um endereço web (domínio ou URL). "
                "Digite algo como `site.com.br` ou `https://site.com.br/pagina`."
            )
            crawler.set_enabled(False)
            return

        ligado = st.checkbox(
            "Percorrer o site e extrair contatos", value=False, key="crawl_on",
            help="Visita as páginas do site e extrai e-mail, telefone, endereço "
                 "de cripto e perfis sociais. O conteúdo das páginas não é armazenado.",
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            depth = st.slider("Profundidade", 0, 3, 1, key="crawl_depth",
                              help="0 = só a página informada")
        with c2:
            max_pages = st.slider("Máx. de páginas", 5, 120, 25, step=5, key="crawl_max")
        with c3:
            same_site = st.checkbox("Só o mesmo site", value=True, key="crawl_same",
                                    help="Desmarcar faz o rastreamento sair do domínio.")

        crawler.set_enabled(ligado)
        crawler.configure(depth=depth, max_pages=max_pages, same_site=same_site)

        entidade = detect(alvo)
        if entidade.get("is_onion"):
            if crawler.tor_disponivel():
                st.success("Endereço .onion e Tor disponível — o acesso será via Tor.", icon="🧅")
            else:
                st.error(
                    "Endereço .onion, mas o Tor não está escutando em 127.0.0.1:9050. "
                    "O rastreamento será pulado.",
                    icon="🧅",
                )
            st.caption(
                "Em dark web, rastrear domínio arbitrário faz o servidor baixar o "
                "conteúdo daquelas páginas. Aqui nada do corpo é gravado — só "
                "e-mail, telefone, cripto e perfis. Use em alvo escolhido, "
                "não em varredura ampla."
            )


def _render_fact(fact) -> None:
    color = _BADGE_COLOR.get(fact.label, "#9aa5b1")
    url = fact.urls[0] if fact.urls else ""
    link_html = (
        f"<div style='margin-top:6px'><a href='{url}' target='_blank' "
        f"rel='noopener noreferrer' style='font-size:12px;word-break:break-all'>{url}</a></div>"
        if url else ""
    )
    detail_html = (
        f"<div style='color:#64748b;font-size:13.5px;margin-top:3px'>{fact.detail}</div>"
        if fact.detail else ""
    )
    st.markdown(
        f"""<div style="background:rgba(255,255,255,.03);border:1px solid rgba(148,163,184,.18);
             border-left:4px solid {color};border-radius:8px;padding:11px 13px;margin-bottom:7px">
          <span style="display:inline-block;font-size:9.5px;font-weight:800;text-transform:uppercase;
                letter-spacing:.08em;padding:2px 7px;border-radius:99px;background:{color}22;
                color:{color};margin-right:8px">{fact.label}</span>
          <span style="font-weight:600">{fact.value}</span>
          {detail_html}
          <div style="color:#94a3b8;font-size:11.5px;margin-top:5px">
            fontes: {', '.join(fact.sources[:6])}
          </div>
          {link_html}
        </div>""",
        unsafe_allow_html=True,
    )


def _render_links(facts) -> None:
    """Os deeplinks em grade — cada um já abre pesquisado no alvo."""
    cols = st.columns(3)
    for i, fact in enumerate(facts):
        with cols[i % 3]:
            url = fact.urls[0] if fact.urls else ""
            if url:
                st.link_button(fact.value, url, use_container_width=True)
                if fact.detail:
                    st.caption(fact.detail[:90])


def _render_dossier(dossier) -> None:
    s = dossier.stats

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fontes consultadas", s["fontes_consultadas"])
    c2.metric("Fatos consolidados", s["fatos_consolidados"])
    c3.metric("Pivôs automáticos", s["pivos"])
    c4.metric("Tempo", f"{s['tempo_total_ms'] / 1000:.1f}s")

    if dossier.summary:
        st.markdown("### Leitura do caso")
        st.info(dossier.summary)

    for aviso in dossier.warnings[:6]:
        st.warning(aviso, icon="⚠️")

    destaque = dossier.high_confidence(0.55)
    if destaque:
        with st.expander(f"⭐ O que está bem sustentado ({len(destaque)})", expanded=True):
            for fact in destaque[:25]:
                _render_fact(fact)

    sections = dossier.sections()
    link_section = [(l, i) for l, i in sections if l == "Fontes para abrir"]
    other = [(l, i) for l, i in sections if l != "Fontes para abrir"]

    for label, items in other:
        icon = _ICON.get(label, "•")
        with st.expander(f"{icon} {label} ({len(items)})", expanded=label in
                         ("Nomes", "Contas e perfis", "E-mails", "Telefones", "Vazamentos")):
            for fact in items[:80]:
                _render_fact(fact)

    for label, items in link_section:
        with st.expander(f"🔗 {label} ({len(items)}) — todos já abrem pesquisados no alvo", expanded=False):
            _render_links(items)

    if dossier.pivots_run:
        with st.expander(f"🧭 Cadeia de pivôs ({len(dossier.pivots_run)})"):
            for p in dossier.pivots_run:
                st.markdown(
                    f"**`{p.get('alvo')}`** — {p.get('tipo')}  \n"
                    f"<span style='color:#94a3b8;font-size:13px'>{p.get('motivo')} "
                    f"(salto {p.get('salto')}, origem: {p.get('origem')})</span>",
                    unsafe_allow_html=True,
                )

    if dossier.next_steps:
        with st.expander("➡️ Próximos passos", expanded=True):
            for step in dossier.next_steps:
                st.markdown(f"- {step}")

    if dossier.failures:
        with st.expander(f"⚙️ Fontes que não responderam ({len(dossier.failures)})"):
            st.caption("Transparência: nenhuma fonte falha em silêncio.")
            for r in dossier.failures:
                motivo = r.skipped_reason or r.error or "erro desconhecido"
                st.markdown(f"- **{r.connector_label}** — {motivo}")


def _render_export(dossier) -> None:
    st.markdown("### Exportar")
    alvo = "".join(c if c.isalnum() else "_" for c in dossier.entity.value)[:40]
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "📄 HTML", dossier.to_html(), file_name=f"dossie_{alvo}.html",
            mime="text/html", use_container_width=True,
        )
    with c2:
        st.download_button(
            "📝 Markdown", dossier.to_markdown(), file_name=f"dossie_{alvo}.md",
            mime="text/markdown", use_container_width=True,
        )
    with c3:
        st.download_button(
            "🧾 JSON", dossier.to_json(), file_name=f"dossie_{alvo}.json",
            mime="application/json", use_container_width=True,
        )
    st.caption("O HTML abre no navegador e imprime em PDF com Ctrl+P.")


def _render_chat(dossier) -> None:
    from holmes import llm

    if not llm.available():
        st.caption("Configure uma chave OpenAI ou Anthropic para conversar com o dossiê.")
        return

    st.markdown("### Perguntar ao dossiê")
    st.caption("A IA responde só com base nas evidências levantadas — sem inventar.")
    pergunta = st.text_input(
        "Pergunta", placeholder="Ex.: qual o vínculo entre o alvo e a empresa encontrada?",
        key="dossier_q", label_visibility="collapsed",
    )
    if st.button("Perguntar", key="dossier_ask") and pergunta:
        with st.spinner("Analisando as evidências…"):
            st.markdown(llm.answer_question(dossier, pergunta))


def display_investigar() -> None:
    ensure_registered()
    from holmes import serp
    from holmes.runtime import environment_report

    stats = registry_stats()

    st.markdown(
        f"""<div style="background:linear-gradient(135deg,rgba(15,98,254,.10),rgba(15,98,254,.02));
             border:1px solid rgba(15,98,254,.25);border-radius:12px;padding:16px 18px;margin-bottom:16px">
          <div style="font-size:11px;letter-spacing:.16em;text-transform:uppercase;
               color:#94a3b8;font-weight:700">Motor de investigação</div>
          <div style="font-size:22px;font-weight:700;margin-top:4px">Uma caixa. Todas as fontes.</div>
          <div style="color:#94a3b8;font-size:14px;margin-top:6px">
            Nome, e-mail, telefone, @usuário, CPF, CNPJ, domínio ou link de perfil —
            o tipo é detectado sozinho. {stats['total']} fontes registradas
            ({stats['por_modo'].get('auto', 0)} automáticas,
            {stats['por_modo'].get('deeplink', 0)} abrindo já pesquisadas).
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    health = serp.search_health()
    if not health["ok"]:
        st.error(health["message"], icon="🔑")
    elif health["provider"] == "duckduckgo":
        st.warning(health["message"], icon="⚠️")

    col_in, col_btn = st.columns([4, 1])
    with col_in:
        alvo = st.text_input(
            "Alvo", key="holmes_target", label_visibility="collapsed",
            placeholder="Digite um nome, e-mail, telefone, @usuário, CPF/CNPJ, domínio ou link de perfil…",
        )
    with col_btn:
        rodar = st.button("🔎 Investigar", type="primary", use_container_width=True)

    if alvo.strip():
        preview = detect(alvo)
        st.caption(f"Detectado: **{preview.label}** → `{preview.value}`")

    with st.expander("⚙️ Ajustes da investigação"):
        c1, c2, c3 = st.columns(3)
        with c1:
            depth = st.slider(
                "Profundidade de pivô", 1, 3, 2,
                help="1 = só o alvo. 2 = investiga o que achou. 3 = dois saltos (mais lento e mais ruído).",
            )
            max_pivots = st.slider("Pivôs por salto", 1, 8, 4)
        with c2:
            incluir_links = st.checkbox("Incluir deeplinks", value=True)
            incluir_manual = st.checkbox("Incluir fontes manuais", value=True)
        with c3:
            usar_llm = st.checkbox("Analisar com IA", value=True)
            timeout = st.slider("Tempo máximo (s)", 60, 600, 300, step=30)

        env = environment_report()
        indisponiveis = [k for k, v in env.items() if not v]
        if indisponiveis:
            st.caption("Não instalado neste ambiente: " + ", ".join(indisponiveis))

        _crawler_controls(alvo)
        _key_sidebar()

    if rodar and alvo.strip():
        cfg = InvestigationConfig(
            depth=depth, include_deeplinks=incluir_links, include_manual=incluir_manual,
            max_pivots_per_hop=max_pivots, use_llm=usar_llm, global_timeout=timeout,
        )
        barra = st.progress(0.0)
        status = st.empty()

        def _progress(msg: str, pct: float) -> None:
            barra.progress(min(1.0, max(0.0, pct)))
            status.caption(msg)

        with st.spinner("Investigando…"):
            dossier = investigate(alvo, cfg, progress=_progress)

        barra.empty()
        status.empty()
        st.session_state["holmes_dossier"] = dossier

        try:
            from Core.Support.History import save_search

            save_search(
                search_type=dossier.entity.type.value,
                query=dossier.entity.value,
                results=f"{dossier.stats['fatos_consolidados']} fatos de "
                        f"{dossier.stats['fontes_consultadas']} fontes",
            )
        except Exception:
            pass

    dossier = st.session_state.get("holmes_dossier")
    if dossier:
        st.markdown("---")
        st.markdown(f"## Dossiê — {dossier.entity.value}")
        _render_dossier(dossier)
        st.markdown("---")
        _render_export(dossier)
        st.markdown("---")
        _render_chat(dossier)
    elif not rodar:
        st.caption(
            "Dica: se você tem um bloco de texto (assinatura de e-mail, print de cadastro), "
            "cole só o dado principal — o motor extrai o resto sozinho pelos pivôs."
        )
