"""Troca de página pelo código (botões que levam de uma página a outra).

O Streamlit não deixa escrever `session_state.nav_page` depois que o menu já
foi desenhado na mesma execução. Então o botão só enfileira o destino e chama
`st.rerun()`; `apply_pending_navigation` consome a fila no começo da próxima
passada, antes de o menu existir.
"""

from __future__ import annotations

from typing import Iterable


def queue_navigation(session: dict, page_id: str) -> None:
    session["_pending_nav"] = page_id


def apply_pending_navigation(session: dict, nav_options: Iterable[str], default: str = "Investigar") -> None:
    options = set(nav_options)
    pending = session.pop("_pending_nav", None)
    if pending in options:
        session["nav_page"] = pending
    elif session.get("nav_page") not in options:
        session["nav_page"] = default
