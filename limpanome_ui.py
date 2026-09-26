"""
Página «Limpar Nome»: do relatório do birô até a baixa do registro.

Cinco abas na ordem em que o trabalho acontece: registros, estratégia,
documentos, protocolos e plano. O caso fica salvo (disco + Supabase) e pode
ser reaberto depois.
"""

from __future__ import annotations

import csv
import html as _html
import io
from datetime import date, datetime

import streamlit as st

from holmes import limpanome as ln

_COR_PILHA = {"errado": "#e8488a", "vencido": "#5b5bf0", "verdadeira": "#d98e00", "duvida": "#8a90a8"}
_COR_STATUS = {"Baixado": "#10b27c", "Recusado": "#e8488a"}


# ── Estado ─────────────────────────────────────────────────────────────────

def _caso() -> ln.Caso:
    if "ln_caso" not in st.session_state:
        st.session_state["ln_caso"] = ln.Caso()
    return st.session_state["ln_caso"]


def _salvar() -> None:
    caso = _caso()
    if caso.registros or caso.protocolos or caso.nome:
        ln.salvar(caso)


def _abrir(caso_id: str) -> None:
    c = ln.carregar(caso_id)
    if c:
        st.session_state["ln_caso"] = c


def _novo() -> None:
    st.session_state["ln_caso"] = ln.Caso()


def _investigar_credor(nome: str) -> None:
    """Manda o credor para a caixa única: quem é essa empresa, CNPJ, sócios, processos."""
    from osint_premium import queue_navigation

    st.session_state["holmes_target"] = nome
    queue_navigation(st.session_state, "Investigar")


# ── Cabeçalho do caso ──────────────────────────────────────────────────────

def _painel_caso() -> None:
    caso = _caso()
    with st.expander("👤 Dados do caso e casos salvos", expanded=not caso.registros):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            nome = st.text_input("Nome completo", value=caso.nome, key="ln_nome",
                                 placeholder="Como está no documento")
        with c2:
            cpf_raw = st.text_input("CPF", value="", key="ln_cpf", placeholder="000.000.000-00",
                                    help="Fica salvo só mascarado (000.***.***-00). O número completo nunca vai para o disco.")
        with c3:
            st.write("")
            if st.button("Salvar dados", key="ln_salvar_dados", use_container_width=True):
                caso.nome = nome.strip()
                if cpf_raw.strip():
                    from holmes.entity import format_cpf, mascarar, valid_cpf

                    if valid_cpf(cpf_raw):
                        caso.cpf_mascarado = mascarar(format_cpf(cpf_raw))
                    else:
                        st.error("CPF inválido: confira os dígitos.")
                _salvar()
                st.success("Salvo.")

        salvos = ln.listar_casos()
        if salvos:
            st.markdown('<div class="mh-hint-label">Casos salvos</div>', unsafe_allow_html=True)
            cols = st.columns(min(4, len(salvos)) or 1)
            for i, c in enumerate(salvos[:8]):
                rotulo = f"{c['nome'] or c['cpf'] or c['id']} · {c['registros']} reg."
                cols[i % len(cols)].button(rotulo, key=f"ln_abrir_{c['id']}", use_container_width=True,
                                           on_click=_abrir, args=(c["id"],))
        st.button("➕ Novo caso", key="ln_novo", on_click=_novo)

    s = ln.resumo(caso)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Registros", s["registros"])
    m2.metric("Contestável", ln.moeda(s["valor_contestavel"]))
    m3.metric("Protocolos abertos", s["protocolos"] - s["baixados"])
    m4.metric("Baixados", s["baixados"])


# ── Aba 1: registros ───────────────────────────────────────────────────────

def _aba_registros() -> None:
    caso = _caso()

    with st.expander("📋 Colar o relatório do birô (Serasa, SPC, Boa Vista, Quod)", expanded=not caso.registros):
        st.caption("Abra o app ou site do birô, copie a lista de dívidas e cole aqui. "
                   "Puxe nos três: um registro pode estar só num deles.")
        texto = st.text_area("Texto copiado", key="ln_texto", height=160, label_visibility="collapsed",
                             placeholder="BANCO EXEMPLO S.A.\nValor: R$ 1.250,90\nVencimento: 10/03/2020\n\nLOJA EXEMPLO\nR$ 89,00\n01/02/2023")
        c1, c2 = st.columns(2)
        if c1.button("Extrair registros", key="ln_extrair", use_container_width=True, type="primary"):
            novos = ln.importar_texto(texto)
            if novos:
                caso.registros += novos
                _salvar()
                st.success(f"{len(novos)} registro(s) extraído(s). Revise a tabela abaixo.")
                st.rerun()
            else:
                st.warning("Não encontrei valores em R$ no texto. Confira o que foi colado ou adicione na mão.")
        if ln.ia_disponivel():
            if c2.button("✨ Extrair com IA", key="ln_extrair_ia", use_container_width=True,
                         help="Usa o modelo configurado para ler o texto. Serve para formatos que a extração simples não pega."):
                with st.spinner("Lendo o relatório…"):
                    novos = ln.extrair_com_ia(texto)
                if novos:
                    caso.registros += novos
                    _salvar()
                    st.success(f"{len(novos)} registro(s) extraído(s) pela IA. Revise a tabela abaixo.")
                    st.rerun()
                else:
                    st.warning("A IA não devolveu registros. Tente a extração simples ou adicione na mão.")
        else:
            c2.caption("Extração com IA: configure OPENAI_API_KEY ou ANTHROPIC_API_KEY.")

    with st.expander("➕ Adicionar registro na mão"):
        with st.form("ln_form_registro", border=False):
            a, b, c = st.columns([2, 1, 1])
            credor = a.text_input("Credor (empresa que registrou)")
            valor = b.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f")
            biro = c.selectbox("Birô", ln.BIROS)
            d, e, f = st.columns(3)
            venc = d.date_input("Data de vencimento", value=None, format="DD/MM/YYYY",
                                help="A data em que a dívida venceu, não a data em que apareceu no birô. É daí que contam os 5 anos.")
            incl = e.date_input("Data de inclusão no birô", value=None, format="DD/MM/YYYY")
            situacao = f.selectbox("Situação", list(ln.SITUACOES), format_func=ln.SITUACOES.get)
            g, h, i = st.columns(3)
            notificado = g.radio("Foi avisado por escrito antes da inclusão?", list(ln.NOTIFICADO),
                                 format_func=ln.NOTIFICADO.get, horizontal=True)
            comprovante = h.checkbox("Tenho comprovante de pagamento")
            pago_em = i.date_input("Pago em", value=None, format="DD/MM/YYYY")
            obs = st.text_input("Observação (ex.: valor que você reconhece, número do contrato)")
            if st.form_submit_button("Adicionar", type="primary"):
                if not credor.strip():
                    st.error("Informe o credor.")
                else:
                    caso.registros.append(ln.Registro(
                        credor=credor.strip(), valor=float(valor), biro=biro, situacao=situacao,
                        vencimento=venc.isoformat() if venc else None,
                        inclusao=incl.isoformat() if incl else None,
                        notificado=notificado, comprovante=comprovante,
                        data_pagamento=pago_em.isoformat() if pago_em else None, observacao=obs.strip(),
                    ))
                    _salvar()
                    st.rerun()

    if not caso.registros:
        st.info("Nenhum registro ainda. Cole o relatório do birô ou adicione na mão.", icon="🧹")
        return

    st.markdown('<div class="mh-section">Seus registros</div>', unsafe_allow_html=True)
    st.caption("Edite direto na tabela. A data de vencimento e a situação são o que decide a estratégia.")
    _tabela_registros()


def _tabela_registros() -> None:
    import pandas as pd

    caso = _caso()
    linhas = []
    for r in caso.registros:
        linhas.append({
            "id": r.id, "Credor": r.credor, "Valor": r.valor, "Vencimento": ln._data(r.vencimento),
            "Inclusão": ln._data(r.inclusao), "Birô": r.biro, "Situação": r.situacao,
            "Avisado antes?": r.notificado, "Comprovante": r.comprovante,
            "Pago em": ln._data(r.data_pagamento), "Observação": r.observacao,
        })
    df = pd.DataFrame(linhas)
    editado = st.data_editor(
        df, key="ln_editor", hide_index=True, use_container_width=True, num_rows="dynamic",
        column_config={
            "id": None,
            "Valor": st.column_config.NumberColumn(format="R$ %.2f", min_value=0.0),
            "Vencimento": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Inclusão": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Pago em": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Birô": st.column_config.SelectboxColumn(options=list(ln.BIROS), required=True),
            "Situação": st.column_config.SelectboxColumn(options=list(ln.SITUACOES), required=True),
            "Avisado antes?": st.column_config.SelectboxColumn(options=list(ln.NOTIFICADO), required=True),
            "Comprovante": st.column_config.CheckboxColumn(),
        },
    )
    if st.button("💾 Salvar tabela", key="ln_salvar_tabela", type="primary"):
        novos: list[ln.Registro] = []
        for _, row in editado.iterrows():
            credor = str(row.get("Credor") or "").strip()
            if not credor:
                continue
            antigo = caso.registro(str(row.get("id") or "")) if row.get("id") else None
            reg = ln.Registro(
                credor=credor, valor=float(row.get("Valor") or 0),
                vencimento=_iso(row.get("Vencimento")), inclusao=_iso(row.get("Inclusão")),
                biro=row.get("Birô") or "Serasa", situacao=row.get("Situação") or "nao_sei",
                notificado=row.get("Avisado antes?") or "nao_sei", comprovante=bool(row.get("Comprovante")),
                data_pagamento=_iso(row.get("Pago em")), observacao=str(row.get("Observação") or ""),
                cnpj_credor=antigo.cnpj_credor if antigo else "",
                id=antigo.id if antigo else ln.Registro(credor=credor).id,
            )
            novos.append(reg)
        caso.registros = novos
        _salvar()
        st.success("Tabela salva.")
        st.rerun()


def _iso(v) -> str | None:
    if v is None or (isinstance(v, float) and v != v):
        return None
    if isinstance(v, (date, datetime)):
        return v.date().isoformat() if isinstance(v, datetime) else v.isoformat()
    try:
        return date.fromisoformat(str(v)[:10]).isoformat()
    except ValueError:
        return None


# ── Aba 2: estratégia ──────────────────────────────────────────────────────

def _aba_estrategia() -> None:
    caso = _caso()
    if not caso.registros:
        st.info("Adicione registros na aba 1 para ver a estratégia.", icon="🧭")
        return

    s = ln.resumo(caso)
    for aviso in ln.avisos_do_caso(caso):
        st.warning(aviso, icon="⚖️")
    chips = "".join(
        f'<span class="mh-chip" style="border-color:{_COR_PILHA[k]};color:{_COR_PILHA[k]}">'
        f'{ln.PILHAS[k]}: <strong>{n}</strong></span>'
        for k, n in s["por_pilha"].items() if n
    )
    st.markdown(f'<div style="margin:.2rem 0 .8rem">{chips}</div>', unsafe_allow_html=True)
    st.markdown('<div class="mh-section">Ordem de ataque</div>', unsafe_allow_html=True)
    st.caption("Comece pela pilha mais fácil, não pela mais irritante: o caso rápido te dá o protocolo "
               "funcionando e ensina o caminho. Deixe por último o que você não reconhece.")

    for n, (r, a) in enumerate(ln.ordem_de_ataque(caso), start=1):
        cor = _COR_PILHA[a.pilha]
        prazo = ""
        if a.limite_5_anos:
            if a.dias_para_vencer_prazo is not None and a.dias_para_vencer_prazo < 0:
                prazo = f"Teto de 5 anos venceu em <strong>{ln.data_br(a.limite_5_anos)}</strong>"
            else:
                prazo = f"Sai sozinho em {ln.data_br(a.limite_5_anos)} ({a.dias_para_vencer_prazo} dias)"
        principal = a.argumento_principal
        arg_html = ""
        if principal:
            arg_html = (f"<div class='mh-fact-detail'><strong>{_html.escape(principal.titulo)}</strong> "
                        f"<span class='mh-tl-src'>· {_html.escape(principal.base)}</span><br>"
                        f"{_html.escape(principal.texto)}</div>")
        outros = [x for x in a.argumentos if x is not principal]
        if outros:
            arg_html += "<div class='mh-fact-src'>Também: " + "; ".join(
                f"{_html.escape(x.titulo)} ({_html.escape(x.base)})" for x in outros) + "</div>"
        alerta_html = f"<div class='mh-fact-detail' style='color:#c2185b'>⚠ {_html.escape(a.alerta)}</div>" if a.alerta else ""
        st.markdown(
            f"<div class='mh-fact' style='--c:{cor}'>"
            f"<span class='mh-fact-tag'>{n}º · {_html.escape(a.pilha_label)}</span>"
            f"<span class='mh-fact-val'>{_html.escape(r.credor)}</span> "
            f"<span class='mh-soft'>{r.valor_fmt()} · {_html.escape(r.biro)}</span>"
            f"<div class='mh-fact-src'>{prazo}</div>{arg_html}"
            f"<div class='mh-fact-detail'>➡️ {_html.escape(a.proximo_passo)} "
            f"<span class='mh-tl-src'>· canal: {ln.CANAIS[a.canal]}</span></div>{alerta_html}"
            f"</div>", unsafe_allow_html=True,
        )
        c1, c2, _ = st.columns([1, 1, 3])
        c1.button("📄 Gerar documentos", key=f"ln_doc_{r.id}", use_container_width=True,
                  on_click=lambda rid=r.id: st.session_state.update(ln_doc_registro=rid, ln_aba="docs"))
        c2.button("🔎 Quem é esse credor?", key=f"ln_inv_{r.id}", use_container_width=True,
                  on_click=_investigar_credor, args=(r.credor,),
                  help="Abre a caixa única com o nome da empresa: CNPJ, sócios, processos e reclamações.")


# ── Aba 3: documentos ──────────────────────────────────────────────────────

def _aba_documentos() -> None:
    caso = _caso()
    if not caso.registros:
        st.info("Adicione registros na aba 1 para gerar documentos.", icon="📄")
        return

    ids = [r.id for r in caso.registros]
    padrao = st.session_state.get("ln_doc_registro")
    idx = ids.index(padrao) if padrao in ids else 0
    r = st.selectbox("Registro", caso.registros, index=idx, key="ln_doc_sel",
                     format_func=lambda x: f"{x.credor} · {x.valor_fmt()} · {x.biro}")
    a = ln.analisar(r)

    st.caption(f"Estratégia: **{a.pilha_label}** · canal sugerido: **{ln.CANAIS[a.canal]}**. "
               "Os textos citam só lei brasileira e não prometem score. Revise antes de enviar.")

    tipos = a.documentos
    abas = st.tabs([ln.DOCUMENTOS[t] for t in tipos])
    for aba, tipo in zip(abas, tipos):
        with aba:
            if tipo == "roteiro_negociacao":
                _negociacao(r)
                continue
            chave = f"ln_texto_{r.id}_{tipo}"
            if chave not in st.session_state:
                st.session_state[chave] = ln.gerar_documento(tipo, caso, r)
            texto = st.text_area("Texto", key=chave, height=320, label_visibility="collapsed")
            c1, c2, c3, c4 = st.columns(4)
            c1.download_button("⬇️ Baixar .txt", texto, file_name=f"{tipo}_{r.id}.txt",
                               mime="text/plain", use_container_width=True, key=f"ln_dl_{chave}")
            if c2.button("↺ Regenerar", key=f"ln_regen_{chave}", use_container_width=True):
                st.session_state[chave] = ln.gerar_documento(tipo, caso, r)
                st.rerun()
            if ln.ia_disponivel():
                instrucao = c4.text_input("Instrução para a IA", key=f"ln_instr_{chave}",
                                          placeholder="ex.: mais curto, tom mais firme",
                                          label_visibility="collapsed")
                if c3.button("✨ Refinar com IA", key=f"ln_ia_{chave}", use_container_width=True):
                    with st.spinner("Reescrevendo…"):
                        novo = ln.refinar_com_ia(texto, instrucao)
                    if novo:
                        st.session_state[chave] = novo
                        st.rerun()
                    else:
                        st.warning("A IA não respondeu. O texto original continua válido.")
            else:
                c3.caption("Refinar com IA: configure uma chave de LLM.")
            if tipo == "consumidor_gov":
                st.markdown(
                    "**Onde colar:** [consumidor.gov.br](https://www.consumidor.gov.br/) → Registrar reclamação → "
                    "procure a empresa pelo CNPJ ou nome. A empresa tem 10 dias para responder. "
                    "Guarde o número do protocolo e registre na aba 4.")
            with st.expander("Registrar protocolo deste documento"):
                _form_protocolo(r, canal_padrao=a.canal, chave=f"{r.id}_{tipo}")


def _negociacao(r: ln.Registro) -> None:
    st.caption("Dívida verdadeira não se apaga, se negocia. Números para decidir, não promessa.")
    c1, c2, c3 = st.columns(3)
    desconto = c1.slider("Desconto à vista", 0, 95, 50, step=5, key=f"ln_desc_{r.id}", format="%d%%")
    juros = c2.slider("Juros ao mês no parcelamento", 0.0, 8.0, 2.0, step=0.5, key=f"ln_juros_{r.id}", format="%.1f%%")
    longo = c3.slider("Parcelas no cenário longo", 12, 48, 24, step=6, key=f"ln_longo_{r.id}")
    for c in ln.cenarios_negociacao(r.valor, desconto / 100, 6, int(longo), juros / 100):
        st.markdown(
            f"<div class='mh-fact' style='--c:#d98e00'><span class='mh-fact-tag'>{c['parcelas']}x</span>"
            f"<span class='mh-fact-val'>{_html.escape(c['cenario'])}</span> "
            f"<span class='mh-soft'>{ln.moeda(c['parcela'])} por parcela · total {ln.moeda(c['total'])}</span>"
            f"<div class='mh-fact-detail'>{_html.escape(c['quando'])}</div></div>", unsafe_allow_html=True)
    texto = ln.roteiro_negociacao(r)
    st.text_area("Roteiro", value=texto, height=260, key=f"ln_rot_{r.id}", label_visibility="collapsed")
    st.download_button("⬇️ Baixar roteiro", texto, file_name=f"negociacao_{r.id}.txt", key=f"ln_dl_rot_{r.id}")
    st.markdown("**Canais oficiais para negociar:** [Serasa Limpa Nome](https://www.serasa.com.br/limpa-nome-online/) · "
                "[SPC Brasil](https://www.spcbrasil.org.br/) · [Boa Vista](https://www.boavistaservicos.com.br/) · "
                "[Desenrola / Portal do credor]. Gere o boleto só no site ou app oficial.")


def _form_protocolo(r: ln.Registro, canal_padrao: str = "consumidor.gov.br", chave: str = "") -> None:
    caso = _caso()
    with st.form(f"ln_prot_{chave or r.id}", border=False):
        c1, c2, c3 = st.columns(3)
        canal = c1.selectbox("Canal", list(ln.CANAIS), index=list(ln.CANAIS).index(canal_padrao),
                             format_func=ln.CANAIS.get)
        data = c2.date_input("Data do protocolo", value=date.today(), format="DD/MM/YYYY")
        numero = c3.text_input("Número do protocolo")
        if st.form_submit_button("Registrar protocolo", type="primary"):
            caso.protocolos.append(ln.Protocolo(registro_id=r.id, canal=canal, data=data.isoformat(),
                                                numero=numero.strip()))
            _salvar()
            st.success("Protocolo registrado. Acompanhe na aba 4.")


# ── Aba 4: protocolos ──────────────────────────────────────────────────────

def _aba_protocolos() -> None:
    caso = _caso()
    if caso.registros:
        with st.expander("➕ Registrar protocolo", expanded=not caso.protocolos):
            r = st.selectbox("Registro", caso.registros, key="ln_prot_sel",
                             format_func=lambda x: f"{x.credor} · {x.valor_fmt()}")
            _form_protocolo(r, chave="aba4")

    if not caso.protocolos:
        st.info("Nenhum protocolo ainda. Depois de enviar um documento, registre aqui a data e o número.", icon="🗂️")
        return

    atrasados = [p for p in caso.protocolos if ln.situacao_protocolo(p)["atrasado"]]
    if atrasados:
        st.warning(f"{len(atrasados)} protocolo(s) com prazo vencido. Veja a ação sugerida em cada um.", icon="⏰")

    for p in sorted(caso.protocolos, key=lambda x: x.data, reverse=True):
        r = caso.registro(p.registro_id)
        est = ln.situacao_protocolo(p)
        cor = _COR_STATUS.get(est["status"], "#e8488a" if est["atrasado"] else "#5b5bf0")
        credor = _html.escape(r.credor if r else "registro removido")
        num = f" · nº {_html.escape(p.numero)}" if p.numero else ""
        st.markdown(
            f"<div class='mh-fact' style='--c:{cor}'><span class='mh-fact-tag'>{_html.escape(est['status'])}</span>"
            f"<span class='mh-fact-val'>{credor}</span> <span class='mh-soft'>{ln.CANAIS.get(p.canal, p.canal)}"
            f" · {ln.data_br(ln._data(p.data))}{num}</span>"
            f"<div class='mh-fact-src'>Resposta até {ln.data_br(est['limite_resposta'])}"
            + (f" · exclusão até {ln.data_br(est['limite_exclusao'])}" if est["limite_exclusao"] else "")
            + f"</div><div class='mh-fact-detail'>➡️ {_html.escape(est['acao'])}</div>"
            + (f"<div class='mh-fact-src'>Resposta: {_html.escape(p.resposta[:300])}</div>" if p.resposta else "")
            + "</div>", unsafe_allow_html=True,
        )
        with st.expander("Atualizar este protocolo"):
            with st.form(f"ln_upd_{p.id}", border=False):
                c1, c2 = st.columns([1, 2])
                aceito = c1.radio("Resposta da empresa", ["aguardando", "aceitou", "recusou"],
                                  index={None: 0, True: 1, False: 2}[p.aceito], horizontal=True)
                resp_data = c1.date_input("Data da resposta", value=ln._data(p.data_resposta), format="DD/MM/YYYY")
                resposta = c2.text_area("O que a empresa respondeu", value=p.resposta, height=90)
                baixa = c1.date_input("Registro baixado em", value=ln._data(p.data_baixa), format="DD/MM/YYYY",
                                      help="Confira no birô e anote a data em que o registro sumiu.")
                s1, s2 = st.columns([1, 1])
                if s1.form_submit_button("Salvar", type="primary", use_container_width=True):
                    p.aceito = {"aguardando": None, "aceitou": True, "recusou": False}[aceito]
                    p.data_resposta = resp_data.isoformat() if resp_data else None
                    p.resposta = resposta.strip()
                    p.data_baixa = baixa.isoformat() if baixa else None
                    _salvar()
                    st.rerun()
                if s2.form_submit_button("Excluir protocolo", use_container_width=True):
                    caso.protocolos = [x for x in caso.protocolos if x.id != p.id]
                    _salvar()
                    st.rerun()

    st.download_button("⬇️ Exportar acompanhamento (CSV)", _csv_protocolos(caso),
                       file_name=f"limpanome_{caso.id}.csv", mime="text/csv", key="ln_csv")


def _csv_protocolos(caso: ln.Caso) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["credor", "valor", "canal", "protocolo", "data", "prazo_resposta", "status",
                "resposta", "data_resposta", "prazo_exclusao", "data_baixa", "acao"])
    for p in caso.protocolos:
        r = caso.registro(p.registro_id)
        e = ln.situacao_protocolo(p)
        w.writerow([r.credor if r else "", f"{r.valor:.2f}".replace(".", ",") if r else "",
                    ln.CANAIS.get(p.canal, p.canal), p.numero, ln.data_br(ln._data(p.data)),
                    ln.data_br(e["limite_resposta"]), e["status"], p.resposta,
                    ln.data_br(ln._data(p.data_resposta)), ln.data_br(e["limite_exclusao"]),
                    ln.data_br(ln._data(p.data_baixa)), e["acao"]])
    return buf.getvalue()


# ── Aba 5: plano e guia ────────────────────────────────────────────────────

def _aba_plano() -> None:
    caso = _caso()
    s = ln.resumo(caso)

    st.markdown('<div class="mh-section">Os números que mandam</div>', unsafe_allow_html=True)
    n1, n2, n3, n4 = st.columns(4)
    n1.metric("5 anos", "teto da negativação", help="CDC art. 43 §1 e Súmula 323 do STJ, contados do vencimento")
    n2.metric("10 dias", "resposta no consumidor.gov.br", help="Depois da resposta, você tem 20 dias para avaliar")
    n3.metric("5 dias úteis", "para a baixa após aceite ou pagamento", help="CDC art. 43 §3 e Súmula 548 do STJ")
    n4.metric("0", "formas legais de apagar dívida verdadeira")

    st.markdown('<div class="mh-section">Escalada, quando o canal não resolve</div>', unsafe_allow_html=True)
    for i, (etapa, quando) in enumerate([
        ("Credor ou birô", "Primeiro pedido, por escrito, com o documento desta ferramenta. Guarde o protocolo."),
        ("consumidor.gov.br", "Sem baixa em 5 dias úteis, ou sem resposta. Público, gratuito, 10 dias úteis de prazo."),
        ("Procon", "Se o consumidor.gov.br não resolver ou a empresa não estiver cadastrada nele."),
        ("Juizado Especial Cível", "Registro indevido mantido: exclusão mais dano moral. Até 20 salários mínimos sem advogado."),
    ], start=1):
        st.markdown(f"<div class='mh-tl-row'><div class='mh-tl-date'>{i}ª rodada</div>"
                    f"<div><strong>{etapa}</strong> <span class='mh-tl-src'>· {quando}</span></div></div>",
                    unsafe_allow_html=True)

    st.markdown('<div class="mh-section">Plano de 12 meses, depois da baixa</div>', unsafe_allow_html=True)
    st.caption("Contestar e subir score são coisas diferentes. Isto é o que move o score de verdade.")
    for item in ln.plano_12_meses(s["baixados"]):
        st.markdown(f"<div class='mh-tl-row'><div class='mh-tl-date'>Mês {item['mes']}</div>"
                    f"<div>{_html.escape(item['acao'])} <span class='mh-tl-src'>· {_html.escape(item['porque'])}</span></div></div>",
                    unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="mh-section">Antes de protocolar</div>', unsafe_allow_html=True)
        for i, item in enumerate(ln.CHECKLIST):
            st.checkbox(item, key=f"ln_chk_{i}")
    with c2:
        st.markdown('<div class="mh-section">Sinais de golpe</div>', unsafe_allow_html=True)
        for titulo, texto in ln.SINAIS_DE_GOLPE:
            st.markdown(f"<div class='mh-fact' style='--c:#e8488a'><span class='mh-fact-tag'>golpe</span>"
                        f"<span class='mh-fact-val'>{_html.escape(titulo)}</span>"
                        f"<div class='mh-fact-detail'>{_html.escape(texto)}</div></div>", unsafe_allow_html=True)

    st.markdown('<div class="mh-section">Consulte o seu CPF de graça</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="mh-quick-links">'
        '<a href="https://www.serasa.com.br/" target="_blank">Serasa</a>'
        '<a href="https://www.spcbrasil.org.br/" target="_blank">SPC Brasil</a>'
        '<a href="https://www.boavistaservicos.com.br/" target="_blank">Boa Vista</a>'
        '<a href="https://www.quod.com.br/" target="_blank">Quod</a>'
        '<a href="https://www.bcb.gov.br/cidadaniafinanceira/registrato" target="_blank">Registrato (Banco Central)</a>'
        '<a href="https://www.consumidor.gov.br/" target="_blank">consumidor.gov.br</a>'
        '<a href="https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm" target="_blank">CDC (texto da lei)</a>'
        '</div>', unsafe_allow_html=True)
    st.caption("O Registrato mostra empréstimos, financiamentos e cheques sem fundo, não a negativação. "
               "Para a negativação, consulte os birôs.")

    st.markdown('<div class="mh-section">O que a lei diz, em uma linha cada</div>', unsafe_allow_html=True)
    for base, texto in [
        ("CDC art. 43 §1 + Súmula 323", "Registro negativo fica no máximo 5 anos, mesmo que a cobrança prescreva antes."),
        ("REsp 1.316.117 (STJ)", "Os 5 anos contam do dia seguinte ao vencimento da dívida, não da data em que ela apareceu no birô."),
        ("CDC art. 43 §2 + Súmulas 359 e 404 + Tema 1.315", "O birô tem de avisar antes de inscrever. Pode ser por carta sem AR ou por meio eletrônico, mas precisa provar envio e entrega."),
        ("CDC art. 43 §3 + Súmula 548", "Dado errado se corrige em 5 dias úteis. Pago o débito, o credor tem 5 dias úteis para pedir a baixa."),
        ("Súmula 385", "Quem tem outra negativação legítima não recebe indenização pela indevida. A exclusão continua valendo."),
        ("CC art. 206 §3 V", "O pedido de indenização por negativação indevida prescreve em 3 anos."),
        ("CC art. 882", "Dívida prescrita continua existindo: não pode ser cobrada na Justiça, mas quem paga não pode pedir de volta."),
        ("Lei 12.414/2011 + LC 166/2019", "O Cadastro Positivo abre sozinho. Consulta e cancelamento são gratuitos em qualquer birô (brasilnopositivo.com.br)."),
    ]:
        st.markdown(f"<div class='mh-tl-row'><div class='mh-tl-date' style='min-width:220px'>{_html.escape(base)}</div>"
                    f"<div>{_html.escape(texto)}</div></div>", unsafe_allow_html=True)
    st.caption("Confira os textos: [CDC no Planalto](https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm) · "
               "[Súmulas do STJ](https://scon.stj.jus.br/SCON/sumstj/) · "
               "[Lei 12.414](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12414.htm)")


# ── Página ─────────────────────────────────────────────────────────────────

def display_limpar_nome() -> None:
    _painel_caso()
    rotulos = ["1 · Registros", "2 · Estratégia", "3 · Documentos", "4 · Protocolos", "5 · Plano e guia"]
    abas = st.tabs(rotulos)
    with abas[0]:
        _aba_registros()
    with abas[1]:
        _aba_estrategia()
    with abas[2]:
        _aba_documentos()
    with abas[3]:
        _aba_protocolos()
    with abas[4]:
        _aba_plano()
    if st.session_state.get("ln_aba") == "docs":
        st.session_state["ln_aba"] = None
        st.info("Os documentos do registro escolhido estão na aba **3 · Documentos**.", icon="📄")
