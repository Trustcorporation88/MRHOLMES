"""Mr.Holmes Web — OSINT Investigation Console"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

st.set_page_config(
    page_title="Mr.Holmes",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ────────────────────────────────────────────────────────────
# Injeta CSS no documento pai (markdown do Streamlit novo remove <style> e mostra texto)
import streamlit.components.v1 as _components

_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root {
  --ink: #0f1419;
  --ink-soft: #3d4a5c;
  --paper: #f3f4f6;
  --panel: #ffffff;
  --sidebar: #12181f;
  --sidebar-text: #c5ced9;
  --accent: #0d9488;
  --accent-hover: #0f766e;
  --line: #d1d5db;
  --ok: #047857;
  --mono: 'IBM Plex Mono', ui-monospace, monospace;
  --sans: 'IBM Plex Sans', system-ui, sans-serif;
}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background: var(--paper) !important;
  color: var(--ink) !important;
  font-family: var(--sans) !important;
}
.main, [data-testid="stMain"] { background: var(--paper) !important; }
[data-testid="stMain"] .block-container {
  padding-top: 1.75rem !important;
  padding-bottom: 3rem !important;
  max-width: 1120px !important;
}
[data-testid="stSidebar"], [data-testid="stSidebarContent"],
section[data-testid="stSidebar"] > div {
  background: var(--sidebar) !important;
  border-right: 1px solid #1e2936 !important;
}
[data-testid="stSidebar"] * { color: var(--sidebar-text) !important; font-family: var(--sans) !important; }
[data-testid="stSidebar"] .stRadio label {
  padding: 0.45rem 0.65rem !important;
  border-radius: 6px !important;
  margin-bottom: 2px !important;
}
[data-testid="stSidebar"] .stRadio label:hover { background: #1a2330 !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  color: #f1f5f9 !important;
}
.mh-brand { padding: 0.25rem 0 1.25rem 0; border-bottom: 1px solid #243041; margin-bottom: 1rem; }
.mh-brand .mark {
  font-family: var(--mono); font-size: 0.7rem; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--accent) !important; margin-bottom: 0.35rem;
}
.mh-brand .name {
  font-size: 1.35rem; font-weight: 700; color: #f8fafc !important;
  letter-spacing: -0.02em; line-height: 1.2;
}
.mh-brand .tag { font-size: 0.78rem; color: #8b9aab !important; margin-top: 0.25rem; }
.mh-page { margin-bottom: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid var(--line); }
.mh-page .eyebrow {
  font-family: var(--mono); font-size: 0.72rem; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 0.35rem;
}
.mh-page h1 {
  font-size: 1.75rem !important; font-weight: 700 !important; color: var(--ink) !important;
  letter-spacing: -0.03em; margin: 0 !important; padding: 0 !important; line-height: 1.25 !important;
}
.mh-page .desc { margin-top: 0.4rem; color: var(--ink-soft); font-size: 0.95rem; max-width: 40rem; }
h1, h2, h3 { font-family: var(--sans) !important; color: var(--ink) !important; }
h2 { font-size: 1.15rem !important; font-weight: 600 !important; margin-top: 1.25rem !important; }
p, label, span, .stMarkdown, [data-testid="stMarkdownContainer"],
[data-testid="stWidgetLabel"] { color: var(--ink) !important; font-family: var(--sans) !important; }
.stButton > button {
  background: var(--accent) !important; color: #fff !important; border: none !important;
  border-radius: 6px !important; font-family: var(--sans) !important; font-weight: 600 !important;
  padding: 0.5rem 1rem !important; box-shadow: none !important;
}
.stButton > button:hover { background: var(--accent-hover) !important; color: #fff !important; }
input, textarea, .stTextInput input, .stTextArea textarea,
.stSelectbox > div > div, [data-baseweb="select"] > div {
  background: var(--panel) !important; color: var(--ink) !important;
  border-color: var(--line) !important; border-radius: 6px !important;
}
.stTextInput input, .stTextArea textarea { font-family: var(--mono) !important; font-size: 0.9rem !important; }
.stMetric, [data-testid="stMetric"] {
  background: var(--panel) !important; border: 1px solid var(--line) !important;
  border-radius: 8px !important; padding: 0.85rem 1rem !important;
}
[data-testid="stMetricLabel"] {
  font-family: var(--mono) !important; font-size: 0.68rem !important;
  letter-spacing: 0.08em !important; text-transform: uppercase !important; color: var(--ink-soft) !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--mono) !important; font-size: 1.15rem !important;
  color: var(--ink) !important; font-weight: 500 !important;
}
button[data-baseweb="tab"] { font-family: var(--sans) !important; font-weight: 500 !important; color: var(--ink-soft) !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--accent) !important; }
.mh-chip {
  display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.35rem 0.7rem;
  border-radius: 999px; font-family: var(--mono); font-size: 0.72rem;
  border: 1px solid var(--line); background: var(--panel); margin: 0.2rem 0.25rem 0.2rem 0;
}
.mh-chip.on { border-color: #99f6e4; background: #f0fdfa; color: var(--ok); }
.mh-chip.off { color: var(--ink-soft); }
.mh-tool {
  border: 1px solid var(--line); border-radius: 8px; padding: 1rem 1.1rem;
  background: var(--panel); margin-bottom: 0.5rem;
}
.mh-tool h4 { margin: 0 0 0.35rem 0 !important; font-size: 0.95rem !important; color: var(--ink) !important; font-weight: 600 !important; }
.mh-tool p { margin: 0 0 0.75rem 0 !important; font-size: 0.82rem !important; color: var(--ink-soft) !important; line-height: 1.45; }
.mh-tool a { font-family: var(--mono); font-size: 0.75rem; color: var(--accent) !important; text-decoration: none; font-weight: 500; }
.stCodeBlock, pre, code { font-family: var(--mono) !important; }
img { border-radius: 8px; border: 1px solid var(--line); }
.mh-foot {
  margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--line);
  font-family: var(--mono); font-size: 0.72rem; color: #6b7280; letter-spacing: 0.04em;
}
div[data-testid="stAlert"] { border-radius: 8px !important; }
hr { border-color: var(--line) !important; }
"""

_components.html(
    f"""<script>
    (function() {{
      const doc = window.parent.document;
      let s = doc.getElementById('mh-theme');
      if (!s) {{
        s = doc.createElement('style');
        s.id = 'mh-theme';
        doc.head.appendChild(s);
      }}
      s.textContent = {_CSS!r};
    }})();
    </script>""",
    height=0,
    width=0,
)


def page_header(eyebrow: str, title: str, desc: str = ""):
    desc_html = f'<div class="desc">{desc}</div>' if desc else ""
    st.html(
        f'<div class="mh-page"><div class="eyebrow">{eyebrow}</div>'
        f'<h1>{title}</h1>{desc_html}</div>'
    )


# ── Navigation ───────────────────────────────────────────────────────────────
PAGES = [
    "Telefone",
    "Email",
    "Domínio",
    "OSINT Avançado",
    "Rede",
    "Gráfico",
    "Ferramentas",
    "Histórico",
    "Sobre",
]

with st.sidebar:
    st.html(
        """
        <div class="mh-brand">
          <div class="mark">OSINT Console</div>
          <div class="name">Mr.Holmes</div>
          <div class="tag">Investigação · fontes abertas</div>
        </div>
        """
    )
    page = st.radio("Navegação", PAGES, label_visibility="collapsed")
    st.markdown("---")
    st.caption("Uso educacional e autorizado.")


# ── Telefone ─────────────────────────────────────────────────────────────────
if page == "Telefone":
    page_header("Lookup", "Telefone", "Operadora, geolocalização por DDD e links de consulta pública.")
    phone = st.text_input("Número (código do país + DDD)", placeholder="5511999999999")
    if st.button("Investigar", type="primary") and phone:
        with st.spinner("Analisando número…"):
            try:
                from Core.Support.Phone.Numbers import get_geo_from_ddd
                from Core.Support.History import save_search
                import phonenumbers as pn
                from phonenumbers import carrier, geocoder, timezone

                digits = "".join(c for c in phone.strip() if c.isdigit())
                parsed = pn.parse("+" + digits, "BR")
                pais = geocoder.country_name_for_number(parsed, "pt") or geocoder.country_name_for_number(parsed, "en") or "N/A"
                area = geocoder.description_for_number(parsed, "pt") or geocoder.description_for_number(parsed, "en") or "N/A"
                operadora = carrier.name_for_number(parsed, "pt") or carrier.name_for_number(parsed, "en") or "N/A"

                c1, c2, c3 = st.columns(3)
                c1.metric("País", pais)
                c1.metric("Área", area)
                c2.metric("Operadora", operadora or "—")
                c2.metric("Região", pn.region_code_for_country_code(parsed.country_code))
                c3.metric("Internacional", pn.format_number(parsed, pn.PhoneNumberFormat.INTERNATIONAL))
                tz = timezone.time_zones_for_number(parsed)
                c3.metric("Fuso", tz[0] if tz else "—")

                e164 = pn.format_number(parsed, pn.PhoneNumberFormat.E164)
                cc = str(parsed.country_code)
                local = e164[1:]
                if local.startswith(cc):
                    local = local[len(cc):]
                ddd = local[:2]
                geo = get_geo_from_ddd(ddd)

                if geo:
                    st.success(f"DDD {ddd} → {geo['city']}/{geo['state']}")
                    st.map(data={"lat": [geo["lat"]], "lon": [geo["lon"]]}, zoom=10)
                    st.caption(f"maps.google.com/maps/place/{geo['lat']},{geo['lon']}")

                st.subheader("Consultas públicas")
                st.caption("HTTP 200 indica página acessível — não confirma registro do número.")
                sites_found = []
                for site_name, url in [
                    ("free-lookup.net", f"https://free-lookup.net/{digits}"),
                    ("whosenumber.info", f"https://whosenumber.info/{digits}"),
                    ("spamcalls.net", f"https://spamcalls.net/en/number/{digits}"),
                ]:
                    try:
                        import urllib.request as _ur
                        req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                        resp = _ur.urlopen(req, timeout=8)
                        if resp.status == 200:
                            st.markdown(f"- [{site_name}]({url}) — acessível")
                            sites_found.append(site_name)
                    except Exception:
                        st.markdown(f"- {site_name} — indisponível")

                a, b, c = st.columns(3)
                a.markdown(f"[Google](https://www.google.com/search?q=%22{digits}%22)")
                b.markdown(f"[Yandex](https://yandex.com/search/?text=%22{digits}%22)")
                c.markdown(f"[WhatsApp](https://wa.me/{digits})")
                save_search("phone", digits, country=pais, area=area, carrier=operadora, sites_found=len(sites_found))
            except Exception as e:
                st.error(str(e))


# ── Email ────────────────────────────────────────────────────────────────────
elif page == "Email":
    page_header("Lookup", "Email", "Validação de formato, MX, Gravatar e menções em pastes públicos.")
    email = st.text_input("Endereço", placeholder="exemplo@dominio.com")
    if st.button("Investigar", type="primary") and email:
        with st.spinner("Analisando email…"):
            try:
                from Core.Support.EmailSearch import buscar_email
                from Core.Support.History import save_search
                r = buscar_email(email)
                c1, c2 = st.columns(2)
                c1.metric("Formato", "válido" if r["valido"] else "inválido")
                c1.metric("MX", "sim" if r.get("mx", {}).get("has_mx") else "não")
                c2.metric("Gravatar", "sim" if r.get("gravatar", {}).get("has_gravatar") else "não")
                c2.metric("Domínio", r.get("dominio", "—"))
                if r.get("pastes"):
                    st.warning(f"{len(r['pastes'])} menções em pastes públicos")
                    for p in r["pastes"][:5]:
                        st.markdown(f"- [{p['url']}]({p['url']}) — {p['title'][:80]}")
                for a in r.get("alertas", []):
                    st.info(a)
                save_search("email", email.strip().lower(), country=r.get("dominio", ""), sites_found=r.get("total_fontes", 0))
            except Exception as e:
                st.error(str(e))


# ── Domínio ──────────────────────────────────────────────────────────────────
elif page == "Domínio":
    page_header("Lookup", "Domínio", "Resolução IP, GeoIP, registros DNS, cabeçalhos HTTP e atalhos ViewDNS.")
    domain = st.text_input("Domínio", placeholder="exemplo.com")
    if st.button("Investigar", type="primary") and domain:
        with st.spinner("Investigando domínio…"):
            try:
                from Core.Support.DomainSearch import buscar_dominio
                from Core.Support.History import save_search
                r = buscar_dominio(domain)
                c1, c2, c3 = st.columns(3)
                c1.metric("IP", r.get("ip") or "—")
                c1.metric("HTTP", r.get("headers", {}).get("status", "—"))
                c2.metric("País", r.get("geo", {}).get("country", "—"))
                c2.metric("Cidade", r.get("geo", {}).get("city", "—"))
                c3.metric("ISP", r.get("geo", {}).get("isp", "—"))
                c3.metric("Server", r.get("headers", {}).get("server", "—"))
                if r.get("geo", {}).get("lat"):
                    st.map(data={"lat": [r["geo"]["lat"]], "lon": [r["geo"]["lon"]]}, zoom=8)
                st.subheader("DNS")
                for rtype, records in r.get("dns", {}).items():
                    if records:
                        st.markdown(f"`{rtype}`  {', '.join(records[:3])}")
                st.subheader("ViewDNS")
                cols = st.columns(5)
                for i, (name, link) in enumerate(r.get("viewdns_links", {}).items()):
                    cols[i % 5].markdown(f"[{name}]({link})")
                save_search(
                    "domain", r.get("dominio", domain),
                    country=r.get("geo", {}).get("country", ""),
                    area=r.get("geo", {}).get("city", ""),
                    carrier=r.get("geo", {}).get("isp", ""),
                )
            except Exception as e:
                st.error(str(e))


# ── OSINT Avançado ───────────────────────────────────────────────────────────
elif page == "OSINT Avançado":
    page_header(
        "Suite",
        "OSINT Avançado",
        "Holehe, Maigret, theHarvester, subdomínios, dnstwist, httpx e SpiderFoot.",
    )
    from Core.Support.OsintTools import tool_status
    status = tool_status()
    chips = [
        ("holehe", "Holehe"), ("maigret", "Maigret"), ("theHarvester", "theHarvester"),
        ("dnstwist", "dnstwist"), ("subfinder", "Subfinder"), ("amass", "Amass"),
        ("httpx", "httpx"), ("sherlock", "Sherlock"),
    ]
    chip_html = "".join(
        f'<span class="mh-chip {"on" if status.get(k) else "off"}">'
        f'{"●" if status.get(k) else "○"} {label}</span>'
        for k, label in chips
    )
    st.html(chip_html)
    st.caption("● instalado · ○ fallback ou pendente")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Holehe", "Maigret", "theHarvester", "Subdomínios", "dnstwist", "httpx", "SpiderFoot"
    ])

    with tab1:
        st.markdown("Descobre em quais serviços um email possui conta.")
        email_h = st.text_input("Email", placeholder="usuario@dominio.com", key="holehe_email")
        if st.button("Executar Holehe", key="btn_holehe") and email_h:
            with st.spinner("Consultando serviços…"):
                from Core.Support.OsintTools import run_holehe
                from Core.Support.History import save_search
                r = run_holehe(email_h)
                if r.get("install"):
                    st.warning(r.get("error", ""))
                    st.code(r["install"])
                elif r.get("sites"):
                    st.success(f"{len(r['sites'])} indícios")
                    for s in r["sites"]:
                        st.write(f"- {s}")
                    save_search("holehe", email_h, sites_found=len(r["sites"]))
                else:
                    st.info("Nenhuma conta pública encontrada.")
                    if r.get("raw"):
                        with st.expander("Saída bruta"):
                            st.code(r["raw"])

    with tab2:
        st.markdown("Username em redes e plataformas (Maigret; Sherlock se disponível).")
        user_m = st.text_input("Username", placeholder="joaosilva", key="maigret_user")
        max_sites = st.slider("Limite de sites", 20, 100, 40, key="maigret_n")
        if st.button("Executar Maigret", key="btn_maigret") and user_m:
            with st.spinner("Buscando perfis…"):
                from Core.Support.OsintTools import run_maigret
                from Core.Support.History import save_search
                r = run_maigret(user_m, max_sites=max_sites)
                if r.get("install"):
                    st.warning(r.get("error", ""))
                    st.code(r["install"])
                elif r.get("profiles"):
                    st.success(f"{len(r['profiles'])} perfis · {r.get('tool')}")
                    for p in r["profiles"]:
                        st.markdown(f"- **{p.get('site', '')}** — [{p.get('url', '')}]({p.get('url', '')})")
                    save_search("username", user_m, sites_found=len(r["profiles"]))
                else:
                    st.info("Nenhum perfil encontrado.")
                    if r.get("raw"):
                        with st.expander("Saída bruta"):
                            st.code(r["raw"])

    with tab3:
        st.markdown("Emails e hosts associados a um domínio.")
        dom_h = st.text_input("Domínio", placeholder="exemplo.com", key="harvester_dom")
        if st.button("Executar theHarvester", key="btn_harvester") and dom_h:
            with st.spinner("Coletando…"):
                from Core.Support.OsintTools import run_theharvester
                from Core.Support.History import save_search
                r = run_theharvester(dom_h)
                if r.get("note"):
                    st.info(r["note"])
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader(f"Emails ({len(r.get('emails', []))})")
                    for e in r.get("emails", []) or ["—"]:
                        st.write(e if e != "—" else "Nenhum")
                with c2:
                    st.subheader(f"Hosts ({len(r.get('hosts', []))})")
                    for h in r.get("hosts", []) or ["—"]:
                        st.write(h if h != "—" else "Nenhum")
                save_search("harvester", r.get("domain", dom_h),
                            sites_found=len(r.get("emails", [])) + len(r.get("hosts", [])))
                st.caption(f"Fonte: {r.get('tool', '—')}")

    with tab4:
        st.markdown("Enumeração via Subfinder/Amass ou brute DNS local.")
        dom_s = st.text_input("Domínio", placeholder="exemplo.com", key="sub_dom")
        if st.button("Enumerar", key="btn_subs") and dom_s:
            with st.spinner("Enumerando…"):
                from Core.Support.OsintTools import run_subdomains
                from Core.Support.History import save_search
                r = run_subdomains(dom_s)
                if r.get("note"):
                    st.info(r["note"])
                st.success(f"{r.get('count', 0)} · {r.get('tool')}")
                for s in r.get("subdomains", []):
                    st.code(s, language=None)
                save_search("subdomains", r.get("domain", dom_s), sites_found=r.get("count", 0))

    with tab5:
        st.markdown("Variações de domínio (typosquatting).")
        dom_t = st.text_input("Domínio", placeholder="exemplo.com", key="twist_dom")
        if st.button("Gerar variações", key="btn_twist") and dom_t:
            with st.spinner("Gerando…"):
                from Core.Support.OsintTools import run_dnstwist
                from Core.Support.History import save_search
                r = run_dnstwist(dom_t)
                if r.get("note"):
                    st.info(r["note"])
                domains = r.get("domains", [])
                st.success(f"{len(domains)} · {r.get('tool')}")
                for d in domains[:80]:
                    st.markdown(f"`{d.get('domain')}` — {d.get('fuzzer', '')} — {d.get('dns_a', '')}")
                save_search("dnstwist", r.get("domain", dom_t), sites_found=len(domains))

    with tab6:
        st.markdown("Verifica quais hosts/URLs respondem HTTP.")
        targets = st.text_area("Alvos (um por linha)", placeholder="exemplo.com\napi.exemplo.com", key="httpx_targets", height=120)
        if st.button("Checar", key="btn_httpx"):
            lines = [l.strip() for l in targets.splitlines() if l.strip()]
            if lines:
                with st.spinner("Verificando…"):
                    from Core.Support.OsintTools import run_httpx
                    from Core.Support.History import save_search
                    r = run_httpx(lines)
                    if r.get("note"):
                        st.info(r["note"])
                    alive = r.get("alive", [])
                    st.success(f"{len(alive)} / {r.get('total', 0)} · {r.get('tool')}")
                    for a in alive:
                        st.write(f"- {a}")
                    if not alive:
                        st.warning("Nenhum host respondeu.")
                    save_search("httpx", lines[0], sites_found=len(alive))

    with tab7:
        from Core.Support.OsintTools import spiderfoot_info
        info = spiderfoot_info()
        st.markdown("Recon automatizado pesado — roda como serviço separado.")
        st.code(info["install"])
        st.markdown(f"[Documentação]({info['docs']}) · UI local: [{info['url']}]({info['url']})")
        alvo_sf = st.text_input("Alvo para copiar", key="sf_target")
        if alvo_sf:
            st.code(alvo_sf)


# ── Rede ─────────────────────────────────────────────────────────────────────
elif page == "Rede":
    page_header("Utilitários", "Rede", "Ping, portas, uptime, DNS reverso e provedor de hospedagem.")
    tool = st.selectbox("Operação", ["Ping", "Scan de portas", "Site online", "IP reverso", "Meu IP", "Hospedagem"])

    if tool == "Ping":
        host = st.text_input("Host", "google.com")
        if st.button("Executar ping"):
            from Core.Support.NetTools import ping_host
            r = ping_host(host)
            if r["success"]:
                st.success(f"{host} responde")
                a, b, c = st.columns(3)
                a.metric("Médio", f"{r['avg_time']:.1f} ms")
                b.metric("Mín", f"{r['min_time']:.1f} ms")
                c.metric("Máx", f"{r['max_time']:.1f} ms")
                st.code(r["output"][-400:])
            else:
                st.error(r.get("error", "Host inacessível"))

    elif tool == "Scan de portas":
        host = st.text_input("Host", "localhost")
        if st.button("Escanear"):
            from Core.Support.NetTools import scan_ports, COMMON_PORTS
            with st.spinner("Escaneando…"):
                results = scan_ports(host)
                if results:
                    st.success(f"{len(results)} portas abertas")
                    for r in results:
                        st.write(f"Porta **{r['port']}** · {r['service']}")
                else:
                    st.info("Nenhuma porta comum aberta.")
                st.caption("Verificadas: " + ", ".join(str(p) for p in COMMON_PORTS))

    elif tool == "Site online":
        url = st.text_input("URL", "https://google.com")
        if st.button("Verificar"):
            from Core.Support.NetTools import check_uptime
            r = check_uptime(url)
            if r["online"]:
                st.success(f"Online · HTTP {r['status_code']}")
                a, b = st.columns(2)
                a.metric("Latência", f"{r['response_time']}s")
                b.metric("Server", r.get("server", "—"))
            else:
                st.error(r.get("error", "Sem resposta"))

    elif tool == "IP reverso":
        ip = st.text_input("IP", "8.8.8.8")
        if st.button("Resolver"):
            from Core.Support.NetTools import reverse_ip
            r = reverse_ip(ip)
            if r["found"]:
                st.success(f"{ip} → {r['hostname']}")
            else:
                st.info("Sem PTR.")

    elif tool == "Meu IP":
        if st.button("Obter IP público"):
            from Core.Support.NetTools import get_my_ip
            r = get_my_ip()
            st.metric("IP público", r["ip"])
            st.caption(r["source"])

    elif tool == "Hospedagem":
        domain = st.text_input("Domínio", "google.com")
        if st.button("Identificar"):
            from Core.Support.NetTools import lookup_hosting
            r = lookup_hosting(domain)
            a, b, c = st.columns(3)
            a.metric("IP", r.get("ip", "—"))
            b.metric("ISP", r.get("isp", "—"))
            c.metric("País", r.get("country", "—"))
            st.write(f"ORG: {r.get('org', '—')}")
            st.markdown(f"[HostingChecker]({r.get('hosting_link', '#')}) · [WHOIS]({r.get('whois_link', '#')})")


# ── Gráfico ──────────────────────────────────────────────────────────────────
elif page == "Gráfico":
    page_header("Análise", "Gráfico de relacionamentos", "Monte entidades e conexões no estilo link analysis.")
    if "graph_nodes" not in st.session_state:
        st.session_state.graph_nodes = []

    col1, col2 = st.columns([2, 1], gap="large")
    with col2:
        st.subheader("Entidade")
        tipo_map = {"Telefone": "Phone", "Email": "Email", "Domínio": "Domain", "IP": "IP", "Pessoa": "Person"}
        entity_type_pt = st.selectbox("Tipo", list(tipo_map.keys()))
        entity_type = tipo_map[entity_type_pt]
        placeholders = {
            "Telefone": "5511999999999", "Email": "usuario@dominio.com",
            "Domínio": "exemplo.com", "IP": "8.8.8.8", "Pessoa": "Nome Sobrenome",
        }
        entity_value = st.text_input("Valor", placeholder=placeholders[entity_type_pt])
        entity_label = st.text_input("Rótulo (opcional)", "")
        if st.button("Adicionar", use_container_width=True) and entity_value:
            node = {
                "id": entity_value,
                "label": entity_label or entity_value,
                "type": entity_type,
                "color": {"Phone": "#2563eb", "Email": "#dc2626", "Domain": "#059669", "IP": "#d97706", "Person": "#7c3aed"}[entity_type],
            }
            if node not in st.session_state.graph_nodes:
                st.session_state.graph_nodes.append(node)
                st.rerun()

        if st.session_state.graph_nodes:
            st.subheader("Conexão")
            if len(st.session_state.graph_nodes) >= 2:
                labels = [n["label"] for n in st.session_state.graph_nodes]
                src = st.selectbox("De", labels)
                dst = st.selectbox("Para", labels, index=min(1, len(labels) - 1))
                edge_label = st.text_input("Relação", "relacionado a")
                if st.button("Ligar", use_container_width=True):
                    if "graph_edges" not in st.session_state:
                        st.session_state.graph_edges = []
                    st.session_state.graph_edges.append({"from": src, "to": dst, "label": edge_label})
                    st.rerun()
            if st.button("Limpar gráfico", use_container_width=True):
                st.session_state.graph_nodes = []
                st.session_state.graph_edges = []
                st.rerun()

    with col1:
        if st.session_state.graph_nodes:
            try:
                import networkx as nx
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                from io import BytesIO

                G = nx.Graph()
                colors_map = {"Phone": "#2563eb", "Email": "#dc2626", "Domain": "#059669", "IP": "#d97706", "Person": "#7c3aed"}
                for node in st.session_state.graph_nodes:
                    G.add_node(node["label"], color=colors_map.get(node["type"], "#64748b"))
                if "graph_edges" in st.session_state:
                    for edge in st.session_state.graph_edges:
                        if edge["from"] in G.nodes and edge["to"] in G.nodes:
                            G.add_edge(edge["from"], edge["to"], label=edge["label"])

                bg = "#f8fafc"
                fig, ax = plt.subplots(figsize=(10, 6), facecolor=bg)
                pos = nx.spring_layout(G, k=2.2, iterations=50, seed=42)
                node_colors = [G.nodes[n].get("color", "#64748b") for n in G.nodes]
                nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=1600,
                                       alpha=1.0, ax=ax, edgecolors="#0f172a", linewidths=1.5)
                nx.draw_networkx_edges(G, pos, edge_color="#64748b", width=2, alpha=0.85, ax=ax)
                for node, (x, y) in pos.items():
                    ax.text(x, y + 0.1, node, fontsize=10, ha="center", va="bottom",
                            fontweight="bold", color="#0f172a",
                            bbox=dict(facecolor="#ffffff", alpha=0.95, edgecolor="#cbd5e1", boxstyle="round,pad=0.35"))
                if G.edges:
                    edge_labels = nx.get_edge_attributes(G, "label")
                    if edge_labels:
                        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color="#475569", font_size=8, ax=ax)
                ax.set_facecolor(bg)
                ax.axis("off")
                fig.tight_layout(pad=0.5)
                buf = BytesIO()
                plt.savefig(buf, format="png", dpi=140, bbox_inches="tight", facecolor=bg)
                plt.close()
                buf.seek(0)
                st.image(buf, use_container_width=True)
                st.caption("Telefone · Email · Domínio · IP · Pessoa")
            except Exception as e:
                st.error(str(e))
        else:
            st.info("Adicione entidades no painel à direita.")


# ── Ferramentas ──────────────────────────────────────────────────────────────
elif page == "Ferramentas":
    page_header("Externas", "Ferramentas", "Integrações e serviços úteis para investigação.")
    st.subheader("UrlScan.io")
    url_to_scan = st.text_input("URL", "https://exemplo.com")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Enviar análise"):
            try:
                import urllib.request as _ur, json as _json
                req = _ur.Request(
                    "https://urlscan.io/api/v1/scan/",
                    data=_json.dumps({"url": url_to_scan, "visibility": "public"}).encode(),
                    headers={"Content-Type": "application/json", "API-Key": "", "User-Agent": "MrHolmes-1.0"},
                )
                resp = _ur.urlopen(req, timeout=15)
                data = _json.loads(resp.read().decode())
                uuid = data.get("uuid", "")
                if uuid:
                    st.success("Análise enviada")
                    st.markdown(f"[Resultado](https://urlscan.io/result/{uuid}/) · [Screenshot](https://urlscan.io/screenshots/{uuid}.png)")
            except Exception:
                st.warning("API indisponível ou limite atingido.")
                st.markdown(f"[Abrir no UrlScan](https://urlscan.io/search/#{url_to_scan})")
    with c2:
        st.markdown(f"[Buscar no UrlScan](https://urlscan.io/search/#{url_to_scan})")

    st.subheader("Diretório")
    tools = [
        {"name": "Metricool", "desc": "Analytics e anúncios de redes sociais.", "url": "https://metricool.com"},
        {"name": "PimEyes", "desc": "Busca reversa de rostos.", "url": "https://pimeyes.com"},
        {"name": "UrlScan.io", "desc": "Sandbox de URLs suspeitas.", "url": "https://urlscan.io"},
        {"name": "Grep.app", "desc": "Busca em repositórios públicos.", "url": "https://grep.app"},
        {"name": "ViewDNS", "desc": "WHOIS, histórico de IP, DNS.", "url": "https://viewdns.info"},
        {"name": "HostingChecker", "desc": "Provedor e localização do host.", "url": "https://hostingchecker.com"},
    ]
    cols = st.columns(3)
    for i, tool in enumerate(tools):
        with cols[i % 3]:
            st.html(
                f'<div class="mh-tool"><h4>{tool["name"]}</h4><p>{tool["desc"]}</p>'
                f'<a href="{tool["url"]}" target="_blank">Abrir →</a></div>'
            )


# ── Histórico ────────────────────────────────────────────────────────────────
elif page == "Histórico":
    page_header("Registro", "Histórico", "Consultas recentes salvas localmente.")
    try:
        from Core.Support.History import get_history, get_stats
        stats = get_stats()
        a, b, c = st.columns(3)
        a.metric("Total", stats["total"])
        b.metric("Hoje", stats["today"])
        c.metric("Tipos", len(stats.get("by_type", {})))
        st.subheader("Recentes")
        for h in get_history(limit=20):
            st.markdown(
                f"`{h.get('type', '—')}`  **{h['query']}**  ·  "
                f"{(h.get('searched_at') or '')[:19]}"
            )
    except Exception:
        st.info("Sem histórico ainda. Execute uma busca.")


# ── Sobre ────────────────────────────────────────────────────────────────────
elif page == "Sobre":
    page_header("Projeto", "Sobre", "Console OSINT para coleta em fontes abertas.")
    st.markdown("""
**Mr.Holmes** reúne lookups de telefone, email e domínio, utilitários de rede,
análise de relacionamentos e integrações com ferramentas OSINT conhecidas.

**Módulos**
- Telefone, email, domínio
- Suite OSINT (Holehe, Maigret, theHarvester, dnstwist, httpx…)
- Rede, gráfico, histórico

**Aviso** — uso educacional e em alvos autorizados. O autor não se responsabiliza por uso indevido.
""")

st.html('<div class="mh-foot">MR.HOLMES · OSINT · USO EDUCACIONAL</div>')
