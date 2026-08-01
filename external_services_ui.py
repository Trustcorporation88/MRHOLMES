"""
UI Streamlit — serviços externos separados por categoria.
Cada bloco mostra só os serviços daquela categoria.
"""

import html as _html
import streamlit as st

from external_services import (
    get_all_categories,
    get_services_for_page,
)


def _service_card(service: dict) -> str:
    name = _html.escape(service.get("name", ""))
    desc = _html.escape(service.get("description", ""))
    use_for = _html.escape(service.get("use_for", ""))
    url = _html.escape(service.get("url", "#"), quote=True)
    icon = service.get("icon", "🔗")
    return f"""
    <div class="mh-ext-card">
      <div class="mh-ext-card-top">
        <div class="mh-ext-card-title">{icon} {name}</div>
        <div class="mh-ext-card-desc">{desc}</div>
        <div class="mh-ext-card-use"><strong>Usar para:</strong> {use_for}</div>
      </div>
      <div class="mh-ext-card-actions">
        <a href="{url}" target="_blank" rel="noopener noreferrer">Abrir serviço →</a>
      </div>
    </div>
    """


def _inject_styles():
    st.markdown(
        """
<style>
.mh-ext-wrap { margin: 0.75rem 0 1.25rem 0; }
.mh-ext-cat {
  border: 1px solid #334355;
  border-radius: 12px;
  background: linear-gradient(135deg, #1b232d 0%, #151c25 100%);
  padding: 1rem 1.1rem 1.15rem;
  margin: 0 0 1rem 0;
  box-shadow: 0 10px 24px rgba(0,0,0,.25);
}
.mh-ext-cat-head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: .75rem; flex-wrap: wrap; margin-bottom: .55rem;
  padding-bottom: .55rem; border-bottom: 1px solid #334355;
}
.mh-ext-cat-head h3 {
  margin: 0 !important; font-size: 1.05rem !important; color: #ecf1f7 !important;
  font-weight: 700 !important;
}
.mh-ext-cat-head .mh-ext-count {
  font-family: ui-monospace, monospace; font-size: .72rem;
  color: #6fd4be; letter-spacing: .06em; text-transform: uppercase;
}
.mh-ext-cat-desc {
  margin: 0 0 .85rem 0; color: #9aa7b7; font-size: .88rem; line-height: 1.4;
}
.mh-ext-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: .75rem;
}
.mh-ext-card {
  border: 1px solid #334355; border-radius: 10px; background: #11161d;
  padding: .9rem 1rem; min-height: 160px;
  display: flex; flex-direction: column; justify-content: space-between;
}
.mh-ext-card-title {
  font-weight: 700; color: #6fd4be; font-size: 1rem; margin-bottom: .35rem;
}
.mh-ext-card-desc { color: #c5ced9; font-size: .86rem; line-height: 1.4; margin-bottom: .45rem; }
.mh-ext-card-use { color: #8b9aab; font-size: .78rem; line-height: 1.35; }
.mh-ext-card-actions { margin-top: .75rem; padding-top: .55rem; border-top: 1px solid #243041; }
.mh-ext-card-actions a {
  display: inline-block; background: #6fd4be; color: #0d1218 !important;
  text-decoration: none; font-weight: 700; font-size: .82rem;
  padding: .45rem .85rem; border-radius: 6px;
}
.mh-ext-card-actions a:hover { background: #4fc4ab; }
.mh-ext-inline {
  border: 1px dashed #334355; border-radius: 10px; background: #151c25;
  padding: .85rem 1rem; margin: 1rem 0 0.25rem 0;
}
.mh-ext-inline h4 {
  margin: 0 0 .35rem 0 !important; font-size: .78rem !important;
  letter-spacing: .1em; text-transform: uppercase; color: #6fd4be !important;
  font-family: ui-monospace, monospace !important;
}
.mh-ext-inline p { margin: 0 0 .65rem 0 !important; color: #9aa7b7 !important; font-size: .84rem !important; }
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_category_block(cat_key: str, cat: dict):
    services = cat.get("services") or []
    label = _html.escape(cat.get("label", cat_key))
    icon = cat.get("icon", "🔗")
    desc = _html.escape(cat.get("description", ""))
    cards = "".join(_service_card(s) for s in services)
    st.markdown(
        f"""
<div class="mh-ext-cat" id="ext-cat-{_html.escape(cat_key)}">
  <div class="mh-ext-cat-head">
    <h3>{icon} {label}</h3>
    <span class="mh-ext-count">{len(services)} serviço{"s" if len(services) != 1 else ""}</span>
  </div>
  <div class="mh-ext-cat-desc">{desc}</div>
  <div class="mh-ext-grid">{cards}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def display_external_services(title: bool = True):
    """Catálogo completo: uma seção por categoria, sem misturar serviços."""
    _inject_styles()
    if title:
        st.markdown(
            """
<div class="mh-page">
  <div class="eyebrow">SERVIÇOS EXTERNOS</div>
  <h1>Catálogo por categoria</h1>
  <div class="desc">Cada bloco abaixo agrupa apenas os serviços daquela finalidade.</div>
</div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="mh-ext-wrap">', unsafe_allow_html=True)
    for cat_key, cat in get_all_categories().items():
        _render_category_block(cat_key, cat)
    st.markdown("</div>", unsafe_allow_html=True)


def display_services_for_page(page_key: str, heading: str | None = None):
    """
    Mostra só as categorias/serviços ligados à página atual.
    Ex.: page_key='telefone' → Sync.me | 'dominio' → Web-Check | 'leaks' → Dehashed
    """
    blocks = get_services_for_page(page_key)
    if not blocks:
        return

    _inject_styles()
    title = heading or "Serviços externos desta categoria"
    st.markdown(
        f"""
<div class="mh-ext-inline">
  <h4>🔗 {_html.escape(title)}</h4>
  <p>Links diretos só dos serviços correspondentes a esta área.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    for cat_key, cat in blocks:
        _render_category_block(cat_key, cat)


def display_services_grid():
    """Compat: redireciona para o catálogo categorizado."""
    display_external_services(title=True)
