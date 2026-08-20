"""
Página «Investigar» — a caixa única do Mr.Holmes.

Você digita nome, e-mail, telefone, @usuário, CPF/CNPJ, domínio ou link de
perfil. O console detecta o tipo, consulta tudo que se aplica, encadeia os
pivôs e monta o dossiê. Sem escolher menu, sem redigitar o alvo.
"""

from __future__ import annotations

import json

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
    import html as _html

    color = _BADGE_COLOR.get(fact.label, "#9aa5b1")
    url = fact.urls[0] if fact.urls else ""
    # Escapa tudo: valor/detalhe podem conter HTML (ex.: fragmento vazado de
    # raspagem). Sem isso, uma tag solta quebra o layout do card.
    valor = _html.escape(fact.value or "")
    detalhe = _html.escape(fact.detail or "")
    fontes = _html.escape(", ".join(fact.sources[:6]))
    url_attr = _html.escape(url, quote=True)
    url_txt = _html.escape(url)

    link_html = (
        f"<div style='margin-top:6px'><a href='{url_attr}' target='_blank' "
        f"rel='noopener noreferrer' style='font-size:12px;word-break:break-all'>{url_txt}</a></div>"
        if url else ""
    )
    detail_html = (
        f"<div style='color:#64748b;font-size:13.5px;margin-top:3px'>{detalhe}</div>"
        if detalhe else ""
    )
    # HTML numa linha só: linha indentada vira "bloco de código" no Streamlit
    # e faz a tag final aparecer como texto (o bug do </div>).
    bloco = (
        f'<div style="background:rgba(255,255,255,.03);border:1px solid rgba(148,163,184,.18);'
        f'border-left:4px solid {color};border-radius:8px;padding:11px 13px;margin-bottom:7px">'
        f'<span style="display:inline-block;font-size:9.5px;font-weight:800;text-transform:uppercase;'
        f'letter-spacing:.08em;padding:2px 7px;border-radius:99px;background:{color}22;'
        f'color:{color};margin-right:8px">{_html.escape(fact.label)}</span>'
        f'<span style="font-weight:600">{valor}</span>'
        f'{detail_html}'
        f'<div style="color:#94a3b8;font-size:11.5px;margin-top:5px">fontes: {fontes}</div>'
        f'{link_html}'
        f'</div>'
    )
    st.markdown(bloco, unsafe_allow_html=True)


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


def _render_identity_card(dossier) -> None:
    """Cartão de identidade estilo agência: quem é o alvo numa olhada só."""
    import html as _html

    card = dossier.identity_card()

    def _linha(rotulo: str, valor: str) -> str:
        if not valor:
            return ""
        return (
            f"<div style='margin:2px 0'><span style='color:#94a3b8;font-size:12px;"
            f"text-transform:uppercase;letter-spacing:.06em'>{rotulo}</span><br>"
            f"<span style='font-size:14.5px'>{_html.escape(valor)}</span></div>"
        )

    esquerda = ""
    if card["foto"]:
        esquerda = (
            f"<img src='{_html.escape(card['foto'], quote=True)}' "
            f"style='width:92px;height:92px;border-radius:12px;object-fit:cover;"
            f"border:1px solid rgba(148,163,184,.3)'>"
        )
    else:
        inicial = (card["nome"] or card["alvo"] or "?")[:1].upper()
        esquerda = (
            f"<div style='width:92px;height:92px;border-radius:12px;background:rgba(15,98,254,.15);"
            f"display:flex;align-items:center;justify-content:center;font-size:40px;"
            f"font-weight:800;color:#3b82f6'>{_html.escape(inicial)}</div>"
        )

    flags_html = ""
    if card["flags"]:
        pills = "".join(
            f"<span style='display:inline-block;background:#db443722;color:#f87171;"
            f"font-size:11px;font-weight:700;padding:3px 9px;border-radius:99px;"
            f"margin:2px 4px 2px 0'>⚠ {_html.escape(x)}</span>"
            for x in card["flags"]
        )
        flags_html = f"<div style='margin-top:8px'>{pills}</div>"

    corpo = "".join([
        _linha("Nome", card["nome"]),
        _linha("E-mails", " · ".join(card["emails"])),
        _linha("Telefones", " · ".join(card["telefones"])),
        _linha("Localização", card["localizacao"]),
        _linha("Empresas", " · ".join(card["empresas"])),
        _linha("Documentos", " · ".join(card["documentos"])),
        _linha("Contas", f"{card['total_contas']} encontrada(s): "
               + ", ".join(c.split(':')[0] for c in card["contas"]) if card["contas"] else ""),
    ])

    bloco = (
        f"<div style='background:linear-gradient(135deg,rgba(15,98,254,.08),rgba(15,98,254,.01));"
        f"border:1px solid rgba(148,163,184,.22);border-radius:14px;padding:16px 18px;margin-bottom:14px'>"
        f"<div style='display:flex;gap:16px;align-items:flex-start'>"
        f"<div>{esquerda}</div>"
        f"<div style='flex:1'>"
        f"<div style='font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#94a3b8;font-weight:700'>"
        f"Cartão de identidade · {_html.escape(card['tipo'])}</div>"
        f"<div style='font-size:21px;font-weight:800;margin:2px 0 8px'>{_html.escape(card['nome'] or card['alvo'])}</div>"
        f"{corpo}{flags_html}"
        f"</div></div></div>"
    )
    st.markdown(bloco, unsafe_allow_html=True)


def _render_timeline(dossier) -> None:
    """Linha do tempo: os achados com data, em ordem cronológica."""
    import html as _html

    eventos = dossier.timeline()
    if not eventos:
        return
    icone = {
        "vazamento": "🩸", "empresa": "🏢", "dominio": "🌐", "juridico": "⚖️",
        "conta": "👤", "nome": "🪪", "documento": "📄", "nota": "🔧",
    }
    with st.expander(f"🕰️ Linha do tempo ({len(eventos)} eventos com data)", expanded=False):
        linhas = []
        for ev in eventos:
            ic = icone.get(ev["tipo"], "•")
            texto = _html.escape(ev["texto"])
            fonte = _html.escape(ev["fonte"])
            link = (f" <a href='{_html.escape(ev['url'], quote=True)}' target='_blank' "
                    f"rel='noopener noreferrer' style='font-size:11px'>abrir</a>") if ev["url"] else ""
            linhas.append(
                f"<div style='display:flex;gap:10px;padding:6px 0;border-bottom:1px solid rgba(148,163,184,.12)'>"
                f"<div style='min-width:92px;font-weight:700;color:#3b82f6;font-size:13px'>{ev['data']}</div>"
                f"<div style='flex:1'>{ic} {texto}"
                f"<span style='color:#94a3b8;font-size:11.5px'> — {fonte}{link}</span></div></div>"
            )
        st.markdown("".join(linhas), unsafe_allow_html=True)


def _render_dossier(dossier) -> None:
    s = dossier.stats

    _render_identity_card(dossier)

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

    _render_timeline(dossier)

    # Grafo de conexões — o mapa "pessoa → empresa → sócio".
    try:
        from holmes import graph as _graph
        import streamlit.components.v1 as _components

        g = _graph.stats(dossier)
        if g["nos"] > 1:
            with st.expander(f"🕸️ Grafo de conexões ({g['nos']} nós, {g['conexoes']} ligações)",
                             expanded=False):
                _components.html(_graph.to_html(dossier), height=580, scrolling=False)
    except Exception:
        pass

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
        with st.expander("➡️ Próximos passos", expanded=False):
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

    # PDF caprichado (reportlab).
    try:
        from holmes import report_pdf

        if report_pdf.available():
            st.download_button(
                "📕 Relatório PDF", report_pdf.generate(dossier),
                file_name=f"dossie_{alvo}.pdf", mime="application/pdf",
                use_container_width=True,
            )
    except Exception:
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


def display_historico() -> None:
    """Página de histórico: reabrir dossiês antigos e comparar dois do mesmo alvo."""
    from holmes import history

    st.markdown(
        "<div style='font-size:11px;letter-spacing:.16em;text-transform:uppercase;"
        "color:#94a3b8;font-weight:700'>Histórico do motor</div>"
        "<div style='font-size:22px;font-weight:700;margin:4px 0 2px'>Investigações salvas</div>"
        "<div style='color:#94a3b8;font-size:14px'>Cada investigação feita na aba "
        "Investigar fica guardada aqui. Compare duas do mesmo alvo para ver o que mudou.</div>",
        unsafe_allow_html=True,
    )

    busca = st.text_input("Filtrar por alvo", key="hist_q", placeholder="parte do nome, e-mail, telefone…")
    entradas = history.list_entries(busca)

    if not entradas:
        st.info("Nenhuma investigação salva ainda. Rode uma na aba **Investigar**.")
        return

    st.caption(f"{len(entradas)} investigação(ões) salva(s).")

    # ── comparar duas ─────────────────────────────────────────────────────────
    rotulo_por_id = {
        e["id"]: f"{e['alvo']} · {(e.get('quando') or '')[:16].replace('T', ' ')}"
        for e in entradas
    }
    with st.expander("🔀 Comparar duas investigações (o que mudou)"):
        st.caption("Escolha a mais antiga e a mais nova — de preferência do mesmo alvo.")
        ids = list(rotulo_por_id.keys())
        c1, c2 = st.columns(2)
        with c1:
            antigo = st.selectbox("Antiga", ids, format_func=lambda i: rotulo_por_id[i],
                                  index=min(1, len(ids) - 1), key="hist_old")
        with c2:
            novo = st.selectbox("Nova", ids, format_func=lambda i: rotulo_por_id[i],
                                index=0, key="hist_new")
        if st.button("Comparar", key="hist_diff") and antigo and novo:
            if antigo == novo:
                st.warning("Escolha duas investigações diferentes.")
            else:
                d = history.diff(antigo, novo)
                if not d or not d["mudancas"]:
                    st.success("Nada mudou entre as duas — mesmos fatos.")
                else:
                    if d["tem_novidade"]:
                        st.success("Há novidades desde a investigação anterior:")
                    for secao, m in d["mudancas"].items():
                        st.markdown(f"**{secao}**")
                        for v in m["novos"]:
                            st.markdown(f"- 🟢 novo: {v}")
                        for v in m["sumidos"]:
                            st.markdown(f"- ⚪ sumiu: {v}")

    st.markdown("---")

    # ── lista ─────────────────────────────────────────────────────────────────
    for e in entradas:
        s = e.get("stats") or {}
        quando = (e.get("quando") or "")[:16].replace("T", " ")
        with st.expander(f"🔎 {e['alvo']}  ·  {e.get('tipo_label')}  ·  {quando}"):
            st.caption(
                f"{s.get('fatos_consolidados', 0)} fatos · "
                f"{s.get('fontes_consultadas', 0)} fontes · "
                f"{s.get('pivos', 0)} pivôs"
            )
            if e.get("resumo"):
                st.write(e["resumo"][:600])
            registro = history.load(e["id"])
            if registro:
                st.download_button(
                    "🧾 Baixar JSON deste dossiê",
                    json.dumps(registro.get("dossie") or {}, ensure_ascii=False, indent=2),
                    file_name=f"dossie_{e['id']}.json", mime="application/json",
                    key=f"dl_{e['id']}",
                )


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

    # Duas ferramentas separadas em abas: buscar por um dado, ou analisar uma
    # foto. Antes tudo ficava empilhado abaixo da caixa e confundia.
    aba_busca, aba_foto = st.tabs(["🔎 Investigar", "📷 Analisar foto"])

    with aba_foto:
        _render_foto()

    with aba_busca:
        health = serp.search_health()
        if not health["ok"]:
            st.error(health["message"], icon="🔑")
        elif health["provider"] == "duckduckgo":
            st.warning(health["message"], icon="⚠️")

        col_in, col_btn = st.columns([4, 1])
        with col_in:
            alvo = st.text_input(
                "Alvo", key="holmes_target", label_visibility="collapsed",
                placeholder="Digite um nome, e-mail, telefone, @usuário, CPF/CNPJ, placa, domínio ou link…",
            )
        with col_btn:
            rodar = st.button("🔎 Investigar", type="primary", use_container_width=True)

        linha1, linha2 = st.columns([3, 2])
        with linha1:
            if alvo.strip():
                preview = detect(alvo)
                st.caption(f"Detectado: **{preview.label}** → `{preview.value}`")
        with linha2:
            modo_rapido = st.checkbox(
                "⚡ Modo rápido (só o alvo, bem mais veloz)", value=False, key="modo_rapido",
                help="Sem pivôs — ótimo para uma primeira olhada. Desmarque para a busca completa.",
            )

        with st.expander("⚙️ Ajustes da busca"):
            c1, c2, c3 = st.columns(3)
            with c1:
                depth = st.slider(
                    "Profundidade de pivô", 1, 3, 2,
                    help="1 = só o alvo. 2 = investiga o que achou. 3 = dois saltos (mais lento e mais ruído).",
                )
                max_pivots = st.slider("Pivôs por salto", 1, 8, 4)
            with c2:
                timeout = st.slider("Tempo máximo (s)", 60, 600, 300, step=30)
                usar_llm = st.checkbox("Analisar com IA", value=True)
            with c3:
                incluir_links = st.checkbox("Incluir deeplinks", value=True)
                incluir_manual = st.checkbox("Incluir fontes manuais", value=True)

        with st.expander("🔧 Avançado — rastrear site e chaves de API"):
            _crawler_controls(alvo)
            _key_sidebar()
            env = environment_report()
            indisponiveis = [k for k, v in env.items() if not v]
            if indisponiveis:
                st.caption("Não instalado neste ambiente: " + ", ".join(indisponiveis))

        if rodar and alvo.strip():
            cfg = InvestigationConfig(
                depth=1 if modo_rapido else depth,
                include_deeplinks=incluir_links, include_manual=incluir_manual,
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

            # Histórico do motor: salva o dossiê inteiro para comparar depois.
            try:
                from holmes import history

                history.save(dossier)
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


def _render_foto() -> None:
    """Análise de foto: EXIF (GPS, câmera, data) + busca reversa por rosto."""
    from holmes import photo

    st.caption(
        "Suba uma foto **original** (não baixada de rede social) para extrair "
        "GPS, câmera e data embutidos. Rede social apaga esses dados."
    )
    arquivo = st.file_uploader("Foto", type=["jpg", "jpeg", "png", "tiff", "webp"],
                               key="foto_up", label_visibility="collapsed")
    if not arquivo:
        return

    dados = arquivo.getvalue()
    st.image(dados, width=260)

    info = photo.analisar_bytes(dados)
    linhas = photo.resumo_texto(info)
    if linhas:
        st.markdown("**Metadados encontrados:**")
        for l in linhas:
            st.markdown(f"- {l}")
        if info.get("gps"):
            g = info["gps"]
            st.success(f"📍 Esta foto tem GPS: {g['lat']}, {g['lon']}", icon="📍")
            st.link_button("Abrir no Google Maps", g["maps"])
    if info.get("aviso"):
        st.info(info["aviso"])

    st.markdown("**Busca reversa (para achar o rosto em outros lugares):**")
    st.caption(
        "Estes buscadores acham a mesma foto na web, mas exigem que você "
        "**arraste o arquivo** na página deles (não aceitam upload automático)."
    )
    for rotulo, url, _desc in [
        ("Google Lens", "https://lens.google.com/"),
        ("Yandex Imagens", "https://yandex.com/images/"),
        ("TinEye", "https://tineye.com/"),
        ("PimEyes (rosto)", "https://pimeyes.com/en"),
    ]:
        st.markdown(f"- [{rotulo}]({url})")


def display_monitoramento() -> None:
    """Página de monitoramento: watchlist de alvos e alertas de novidade."""
    from holmes import monitor

    st.markdown(
        "<div style='font-size:11px;letter-spacing:.16em;text-transform:uppercase;"
        "color:#94a3b8;font-weight:700'>Monitoramento</div>"
        "<div style='font-size:22px;font-weight:700;margin:4px 0 2px'>Alvos vigiados</div>"
        "<div style='color:#94a3b8;font-size:14px'>O sistema reinvestiga cada alvo e "
        "avisa quando surge algo novo — perfil, telefone, vazamento, processo.</div>",
        unsafe_allow_html=True,
    )

    nao_lidos = monitor.unread_count()
    if nao_lidos:
        st.warning(f"🔔 {nao_lidos} alerta(s) de novidade não lido(s).", icon="🔔")

    # Status do aviso por e-mail.
    try:
        from holmes import notify

        if notify.configured():
            st.caption("📧 Aviso por e-mail ativo — novidades são enviadas para você.")
        else:
            st.caption(
                "📧 Aviso por e-mail desligado. Configure SMTP_HOST, SMTP_USER, "
                "SMTP_PASSWORD e ALERT_EMAIL no Railway para receber as novidades por e-mail."
            )
    except Exception:
        pass

    # ── alertas ───────────────────────────────────────────────────────────────
    alertas = monitor.alerts()
    if alertas:
        with st.expander(f"🔔 Alertas ({len(alertas)})", expanded=bool(nao_lidos)):
            if st.button("Marcar todos como lidos", key="mon_read"):
                monitor.marcar_lidos()
                st.rerun()
            for a in alertas[:50]:
                import datetime as _dt
                quando = _dt.datetime.fromtimestamp(a.get("quando", 0)).strftime("%d/%m %H:%M")
                icone = "🟢" if a.get("tipo") == "novidade" else "⚠️"
                marca = "" if a.get("lido") else " **(novo)**"
                st.markdown(f"{icone} `{quando}` — **{a.get('alvo')}**: {a.get('texto')}{marca}")

    st.markdown("---")

    # ── adicionar / rodar agora ───────────────────────────────────────────────
    c1, c2 = st.columns([3, 1])
    with c1:
        novo = st.text_input("Adicionar alvo à vigilância", key="mon_add",
                             placeholder="nome, e-mail, telefone, @usuário, CNPJ…")
    with c2:
        st.write("")
        if st.button("➕ Vigiar", use_container_width=True) and novo.strip():
            if monitor.add_target(novo):
                st.success(f"Vigiando «{novo}».")
                st.rerun()
            else:
                st.info("Já estava na lista (ou vazio).")

    lista = monitor.watchlist()
    if not lista:
        st.caption("Nenhum alvo vigiado ainda.")
        return

    st.markdown(f"**{len(lista)} alvo(s) vigiado(s):**")
    for t in lista:
        col1, col2 = st.columns([5, 1])
        import datetime as _dt
        ultima = t.get("ultima_verificacao")
        quando = _dt.datetime.fromtimestamp(ultima).strftime("%d/%m %H:%M") if ultima else "nunca"
        col1.markdown(f"🎯 **{t['alvo']}**  ·  última verificação: {quando}")
        if col2.button("Remover", key=f"rm_{t['alvo']}"):
            monitor.remove_target(t["alvo"])
            st.rerun()

    st.markdown("---")
    if st.button("▶️ Verificar todos agora", type="primary"):
        with st.spinner("Reinvestigando os alvos vigiados…"):
            novos = monitor.run_once()
        if novos:
            st.success(f"{len(novos)} novidade(s) encontrada(s)! Veja nos alertas acima.")
        else:
            st.info("Nenhuma novidade desde a última verificação.")
        st.rerun()

    st.caption(
        "Para o sistema verificar sozinho (sem você abrir a página), configure um "
        "Railway Cron rodando `python -m holmes.monitor` no intervalo que quiser."
    )
