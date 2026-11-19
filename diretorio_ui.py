"""Página Diretório: a árvore de fontes, com o dado já embutido em cada link."""

from __future__ import annotations

import html as _html

import streamlit as st

from holmes import diretorio

_CUSTO = {"gratis": ("grátis", "#10b27c"), "login": ("cadastro grátis", "#1f9bdc"), "pago": ("pago", "#f2703f")}
_ACESSO = {
    "auto": "já roda no Investigar",
    "busca": "abre pesquisado",
    "form": "preencher no site",
    "codigo": "código aberto",
    "api": "contratar e integrar",
}
_FILTRO_CUSTO = {"Todas": "", "Grátis": "gratis", "Cadastro grátis": "login", "Pagas": "pago"}


def _investigar(dado: str) -> None:
    from nav import queue_navigation

    st.session_state["holmes_target"] = dado
    st.session_state["holmes_autorun"] = True
    queue_navigation(st.session_state, "Investigar")


def _cartao(fonte: diretorio.Fonte, dado: str) -> str:
    rotulo, cor = _CUSTO.get(fonte.custo, (fonte.custo, "#8a90a8"))
    pronto = bool(dado) and fonte.aceita_dado and fonte.acesso != "auto"
    acesso = "abre já com o seu dado" if pronto else _ACESSO.get(fonte.acesso, fonte.acesso)
    url = _html.escape(fonte.link(dado), quote=True)
    return (
        f'<a class="mh-dir" href="{url}" target="_blank" rel="noopener noreferrer">'
        f'<span class="mh-dir-nome">{_html.escape(fonte.nome)}</span>'
        f'<span class="mh-dir-txt">{_html.escape(fonte.entrega)}</span>'
        f'<span class="mh-dir-tags"><span style="color:{cor}">● {rotulo}</span>'
        f'<span>{_html.escape(acesso)}</span></span></a>'
    )


_CSS = """
.mh-dir-grade { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
.mh-dir { display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; border-radius: 12px;
  border: 1px solid var(--line, #e3e6ef); background: var(--panel, #fff); text-decoration: none !important;
  transition: border-color .12s, box-shadow .12s; }
.mh-dir:hover { border-color: var(--accent, #5b5bf0); box-shadow: 0 4px 14px rgba(91, 91, 240, .12); }
.mh-dir-nome { font-weight: 700; color: var(--ink, #1d2239); font-size: .93rem; }
.mh-dir-txt { color: var(--ink-soft, #5d6480); font-size: .82rem; line-height: 1.35; }
.mh-dir-tags { display: flex; gap: 10px; flex-wrap: wrap; font-size: .72rem; color: var(--ink-faint, #8a90a8);
  margin-top: 2px; }
"""


def display_diretorio() -> None:
    st.html(f"<style>{_CSS}</style>")
    r = diretorio.resumo()

    c1, c2, c3 = st.columns([3, 2, 1.4])
    with c1:
        dado = st.text_input(
            "Dado a pesquisar", key="dir_dado",
            placeholder="Opcional: nome, CPF, CNPJ, telefone, e-mail, placa, domínio…",
            help="Com o dado preenchido, cada fonte que aceita o alvo na URL abre já pesquisada.",
        ).strip()
    with c2:
        busca = st.text_input("Filtrar fontes", key="dir_busca", placeholder="protesto, imóvel, placa, sócio…")
    with c3:
        custo = st.selectbox("Custo", list(_FILTRO_CUSTO), key="dir_custo")

    if dado:
        st.button(f"🔎 Rodar o dossiê automático de “{dado}”", type="primary",
                  on_click=_investigar, args=(dado,), key="dir_investigar")

    arvore = diretorio.filtrar(busca, _FILTRO_CUSTO[custo])
    mostradas = sum(len(f) for _, _, f in arvore)
    st.caption(
        f"{mostradas} de {r['total']} fontes em {r['categorias']} categorias. "
        f"{r['automaticas']} já rodam sozinhas no Investigar. "
        "Todas passaram pelo verificador de links."
    )
    if not arvore:
        st.info("Nenhuma fonte com esse filtro.")
        return

    abrir_tudo = bool(busca) or len(arvore) <= 3
    for nome, icone, fontes in arvore:
        with st.expander(f"{icone}  {nome}  ({len(fontes)})", expanded=abrir_tudo):
            st.html('<div class="mh-dir-grade">' + "".join(_cartao(f, dado) for f in fontes) + "</div>")

    st.info(diretorio.SO_ORDEM_JUDICIAL, icon="⚖️")
