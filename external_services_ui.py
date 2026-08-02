"""
UI Streamlit — serviços externos por categoria (layout limpo).
"""

import html as _html
import streamlit as st

from external_services import get_all_categories, get_services_for_page


def _service_card(service: dict) -> str:
    name = _html.escape(service.get("name", ""))
    desc = _html.escape(service.get("description", ""))
    use_for = _html.escape(service.get("use_for", ""))
    url = _html.escape(service.get("url", "#"), quote=True)
    icon = service.get("icon", "🔗")
    src = _html.escape((service.get("source") or "").upper())
    badge = f'<span class="mh-ext-badge">{src}</span>' if src else ""
    return f"""
    <div class="mh-ext-card">
      <div class="mh-ext-card-top">
        <div class="mh-ext-card-title">{icon} {name} {badge}</div>
        <div class="mh-ext-card-desc">{desc}</div>
        <div class="mh-ext-card-use">{use_for}</div>
      </div>
      <div class="mh-ext-card-actions">
        <a href="{url}" target="_blank" rel="noopener noreferrer">Abrir →</a>
      </div>
    </div>
    """


def _inject_styles():
    st.markdown(
        """
<style>
.mh-ext-wrap { margin: 0.5rem 0 1rem 0; }
.mh-ext-cat {
  border: 1px solid #334355; border-radius: 12px;
  background: #151c25; padding: 0.85rem 1rem 1rem; margin: 0 0 0.85rem 0;
}
.mh-ext-cat-head {
  display:flex; align-items:baseline; justify-content:space-between;
  gap:.5rem; flex-wrap:wrap; margin-bottom:.4rem;
}
.mh-ext-cat-head h3 {
  margin:0 !important; font-size:.98rem !important; color:#ecf1f7 !important; font-weight:700 !important;
}
.mh-ext-cat-head .mh-ext-count {
  font-family: ui-monospace, monospace; font-size:.68rem; color:#6fd4be;
  letter-spacing:.06em; text-transform:uppercase;
}
.mh-ext-cat-desc { margin:0 0 .7rem 0; color:#9aa7b7; font-size:.84rem; line-height:1.35; }
.mh-ext-grid {
  display:grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap:.65rem;
}
.mh-ext-card {
  border:1px solid #334355; border-radius:10px; background:#11161d;
  padding:.75rem .85rem; min-height:132px;
  display:flex; flex-direction:column; justify-content:space-between;
}
.mh-ext-card:hover { border-color: rgba(111,212,190,.45); }
.mh-ext-card-title { font-weight:700; color:#6fd4be; font-size:.92rem; margin-bottom:.3rem; line-height:1.3; }
.mh-ext-card-desc { color:#c5ced9; font-size:.8rem; line-height:1.35; margin-bottom:.3rem; }
.mh-ext-card-use { color:#7a8796; font-size:.72rem; line-height:1.3; }
.mh-ext-badge {
  display:inline-block; margin-left:.35rem; padding:.08rem .35rem; border-radius:999px;
  font-size:.58rem; letter-spacing:.04em; vertical-align:middle;
  border:1px solid #334355; color:#9aa7b7; font-weight:600;
}
.mh-ext-card-actions { margin-top:.55rem; padding-top:.45rem; border-top:1px solid #243041; }
.mh-ext-card-actions a {
  display:inline-block; background:#6fd4be; color:#0d1218 !important;
  text-decoration:none; font-weight:700; font-size:.78rem;
  padding:.38rem .7rem; border-radius:6px;
}
.mh-ext-card-actions a:hover { background:#4fc4ab; }
.mh-ext-inline {
  border:1px solid #334355; border-radius:10px; background:#151c25;
  padding:.7rem .9rem; margin:1rem 0 .5rem 0;
}
.mh-ext-inline h4 {
  margin:0 0 .2rem 0 !important; font-size:.72rem !important;
  letter-spacing:.1em; text-transform:uppercase; color:#6fd4be !important;
  font-family: ui-monospace, monospace !important;
}
.mh-ext-inline p { margin:0 !important; color:#9aa7b7 !important; font-size:.8rem !important; }
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
    <span class="mh-ext-count">{len(services)}</span>
  </div>
  <div class="mh-ext-cat-desc">{desc}</div>
  <div class="mh-ext-grid">{cards}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def display_external_services(title: bool = True):
    """Catálogo com abas por categoria — evita scroll confuso."""
    _inject_styles()
    if title:
        st.markdown(
            """
<div class="mh-page">
  <div class="eyebrow">CATÁLOGO</div>
  <h1>Serviços externos</h1>
  <div class="desc">Escolha uma categoria na aba. Cada serviço aparece só no bloco certo.</div>
</div>
            """,
            unsafe_allow_html=True,
        )

    cats = get_all_categories()
    labels = [f"{c.get('icon','🔗')} {c.get('label', k)}" for k, c in cats.items()]
    keys = list(cats.keys())
    tabs = st.tabs(labels)
    for tab, key in zip(tabs, keys):
        with tab:
            _render_category_block(key, cats[key])


def display_services_for_page(page_key: str, heading: str | None = None):
    """Só serviços da página atual, em grid compacto."""
    blocks = get_services_for_page(page_key)
    if not blocks:
        return

    _inject_styles()
    title = heading or "Fontes externas"
    st.markdown(
        f"""
<div class="mh-ext-inline">
  <h4>{_html.escape(title)}</h4>
  <p>Links da categoria correspondente — abra em nova aba.</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    # Uma página costuma ter 1 categoria; se tiver várias, abas internas
    if len(blocks) == 1:
        _render_category_block(blocks[0][0], blocks[0][1])
    else:
        tabs = st.tabs([f"{b[1].get('icon','')} {b[1].get('label', b[0])}" for b in blocks])
        for tab, (k, cat) in zip(tabs, blocks):
            with tab:
                _render_category_block(k, cat)


def display_services_grid():
    display_external_services(title=True)
