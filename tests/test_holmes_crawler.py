"""
Rastreamento de site.

Nenhum teste acessa a rede: o `requests` do módulo é substituído por um site
falso em memória. Assim a suíte valida o comportamento do crawler (links
relativos, visitados, limites, extração) de forma determinística.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from holmes import crawler  # noqa: E402
from holmes.entity import EntityType, detect  # noqa: E402
from holmes.findings import FindingKind  # noqa: E402


# ── detecção de alvo ────────────────────────────────────────────────────────

def test_url_com_caminho_preserva_o_caminho():
    e = detect("https://site.com.br/vendor/joao?x=1")
    assert e.type is EntityType.URL
    assert e.get("path") == "/vendor/joao"
    assert e.get("root") == "site.com.br"
    # Domínio puro continua sendo domínio.
    assert detect("https://site.com.br").type is EntityType.DOMAIN


def test_onion_e_reconhecido():
    # Antes desta mudança, um .onion sem esquema virava "nome de pessoa".
    bare = detect("juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion")
    assert bare.type is EntityType.DOMAIN
    assert bare.get("is_onion") is True
    # .onion não tem TLS: a URL montada tem que ser http.
    assert bare.get("url").startswith("http://")

    com_caminho = detect("http://abc234567.onion/market/vendor")
    assert com_caminho.type is EntityType.URL
    assert com_caminho.get("is_onion") is True


# ── resolução de link relativo (o bug do TorBot) ────────────────────────────

def test_resolve_link_relativo():
    html = (
        '<a href="/interna">a</a>'
        '<a href="../acima">b</a>'
        '<a href="contato.html">c</a>'
        '<a href="https://externo.com/x">d</a>'
        '<a href="#ancora">e</a>'
        '<a href="mailto:x@y.com">f</a>'
        '<a href="javascript:void(0)">g</a>'
    )
    links = crawler.extrair_links(html, "https://site.com/dir/pagina")
    assert "https://site.com/interna" in links
    assert "https://site.com/acima" in links
    assert "https://site.com/dir/contato.html" in links
    assert "https://externo.com/x" in links
    # Âncora, mailto e javascript não são páginas.
    assert not any("#" in u or "mailto" in u or "javascript" in u for u in links)


def test_links_sao_deduplicados_e_normalizados():
    html = '<a href="/a">1</a><a href="/a/">2</a><a href="/a#topo">3</a>'
    assert len(crawler.extrair_links(html, "https://site.com/")) == 1


# ── extração de artefatos ───────────────────────────────────────────────────

def test_extrai_email_e_ignora_falso_positivo():
    achados = crawler._extrair_emails(
        "fale com joao.silva@empresa.com.br ou teste@example.com — logo.png@2x.png"
    )
    assert "joao.silva@empresa.com.br" in achados
    assert "teste@example.com" not in achados  # domínio de exemplo
    assert not any(a.endswith(".png") for a in achados)


def test_extrai_telefone_do_corpo_do_texto():
    # O TorBot só lê href="tel:"; aqui o número no texto também é pego.
    achados = crawler._extrair_telefones("Ligue (11) 98765-4321 ou 11 3214-5678 hoje")
    assert "+5511987654321" in achados


def test_telefone_invalido_e_descartado():
    assert crawler._extrair_telefones("00 0000-0000") == set()


def test_extrai_endereco_de_cripto():
    texto = (
        "BTC: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa "
        "ETH: 0x52908400098527886E0F7030069857D2E4169EE7"
    )
    achados = dict((m, e) for m, e in crawler._extrair_cripto(texto))
    assert achados.get("BTC") == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    assert achados.get("ETH", "").lower() == "0x52908400098527886e0f7030069857d2e4169ee7"


def test_normaliza_url_para_o_conjunto_de_visitados():
    n = crawler._normalizar_url
    assert n("https://Site.COM/a/") == n("https://site.com/a") == n("https://site.com/a#x")


# ── crawl com site falso ────────────────────────────────────────────────────

class _RespFalsa:
    def __init__(self, html: str, status: int = 200, tipo: str = "text/html"):
        self._html = html.encode("utf-8")
        self.status_code = status
        self.headers = {"Content-Type": tipo}
        self.encoding = "utf-8"

    def iter_content(self, n: int = 8192):
        for i in range(0, len(self._html), n):
            yield self._html[i:i + n]

    def close(self):
        pass


class _SessaoFalsa:
    """Site em memória. Conta acessos para provar que não há revisita."""

    def __init__(self, paginas: dict[str, str]):
        self.paginas = paginas
        self.acessos: list[str] = []
        self.proxies: dict = {}

    def get(self, url, **kwargs):
        self.acessos.append(url)
        chave = crawler._normalizar_url(url)
        for k, html in self.paginas.items():
            if crawler._normalizar_url(k) == chave:
                return _RespFalsa(html)
        return _RespFalsa("<html><body>404</body></html>", status=404)


@pytest.fixture
def site(monkeypatch):
    """Site com um ciclo A→B→A, para testar o conjunto de visitados."""
    paginas = {
        "https://alvo.com/": (
            "<html><head><title>Home do Alvo</title></head><body>"
            '<a href="/sobre">sobre</a><a href="/contato">contato</a>'
            '<a href="https://instagram.com/alvooficial">insta</a>'
            '<a href="https://parceiro.com/x">parceiro</a>'
            "</body></html>"
        ),
        "https://alvo.com/sobre": (
            "<html><head><title>Sobre</title></head><body>"
            '<a href="/">home</a><a href="/contato">contato</a>'
            "</body></html>"
        ),
        "https://alvo.com/contato": (
            "<html><head><title>Contato</title></head><body>"
            '<a href="mailto:diretoria@alvo.com">mail</a>'
            '<a href="tel:+5511987654321">tel</a>'
            "Fale com suporte@alvo.com. BTC 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
            '<a href="/">home</a>'
            "</body></html>"
        ),
    }
    sessao = _SessaoFalsa(paginas)
    monkeypatch.setattr(crawler, "_sessao", lambda is_onion: sessao)
    crawler.set_enabled(True)
    crawler.configure(depth=2, max_pages=20, workers=2, delay_por_host=0.0, same_site=True)
    yield sessao
    crawler.set_enabled(False)


def test_crawl_percorre_e_nao_revisita(site):
    res = crawler.rastrear("https://alvo.com/")
    urls = [crawler._normalizar_url(p.url) for p in res.paginas]
    assert len(urls) == len(set(urls)), "página visitada mais de uma vez"
    # As três páginas do site, apesar do ciclo A→B→A.
    assert len(res.paginas) == 3


def test_crawl_respeita_profundidade(site):
    crawler.configure(depth=0)
    res = crawler.rastrear("https://alvo.com/")
    assert len(res.paginas) == 1


def test_crawl_respeita_teto_de_paginas(site):
    crawler.configure(depth=3, max_pages=2)
    res = crawler.rastrear("https://alvo.com/")
    assert len(res.paginas) <= 2


def test_crawl_nao_sai_do_site_por_padrao(site):
    res = crawler.rastrear("https://alvo.com/")
    hosts = {crawler._host(p.url) for p in res.paginas}
    assert hosts == {"alvo.com"}
    # Mas registra o domínio externo como referência.
    externos = set()
    for p in res.paginas:
        externos |= p.externos
    assert "parceiro.com" in externos


def test_crawl_extrai_artefatos(site):
    res = crawler.rastrear("https://alvo.com/")
    emails, tels, cripto, sociais = set(), set(), set(), []
    for p in res.paginas:
        emails |= p.emails
        tels |= p.telefones
        cripto |= p.cripto
        sociais += p.sociais
    assert {"diretoria@alvo.com", "suporte@alvo.com"} <= emails
    assert "+5511987654321" in tels
    assert any(m == "BTC" for m, _ in cripto)
    assert any(plat == "Instagram" for plat, _ in sociais)


def test_crawl_nao_guarda_o_corpo_da_pagina(site):
    res = crawler.rastrear("https://alvo.com/")
    for p in res.paginas:
        campos = vars(p)
        assert "html" not in campos and "body" not in campos and "content" not in campos
        # Nenhum campo textual pode conter marcação da página.
        for valor in campos.values():
            if isinstance(valor, str):
                assert "<html" not in valor and "<a href" not in valor


def test_conector_gera_achados_do_dossie(site):
    achados = list(crawler.crawl_findings(detect("https://alvo.com/")))
    kinds = {f.kind for f in achados}
    assert FindingKind.EMAIL in kinds
    assert FindingKind.PHONE in kinds
    assert FindingKind.CRYPTO in kinds
    assert FindingKind.ACCOUNT in kinds
    assert FindingKind.NOTE in kinds
    # Todo achado aponta a página onde foi visto.
    assert all(f.url for f in achados if f.kind is FindingKind.EMAIL)


def test_email_institucional_pontua_menos_que_pessoal(site):
    achados = [f for f in crawler.crawl_findings(detect("https://alvo.com/"))
               if f.kind is FindingKind.EMAIL]
    por_valor = {f.value: f.confidence.value for f in achados}
    assert por_valor["suporte@alvo.com"] == "provavel"
    assert por_valor["diretoria@alvo.com"] == "confirmada"


# ── segurança / opt-in ──────────────────────────────────────────────────────

def test_conector_desligado_por_padrao():
    from holmes.connectors import connectors_for, ensure_registered

    ensure_registered()
    crawler.set_enabled(False)
    conn = [c for c in connectors_for(detect("https://alvo.com/x")) if c.id == "crawler"][0]
    res = conn.execute(detect("https://alvo.com/x"))
    assert res.status == "pulado"
    assert "desligado" in (res.skipped_reason or "")


def test_onion_sem_tor_avisa_e_nao_rastreia(monkeypatch):
    crawler.set_enabled(True)
    monkeypatch.setattr(crawler, "tor_disponivel", lambda **kw: False)
    res = crawler.rastrear("http://abc234567.onion/")
    assert res.paginas == []
    assert "Tor" in (res.aviso or "")
    crawler.set_enabled(False)


def test_limitador_de_taxa_espera_entre_acessos_ao_mesmo_host():
    import time

    lim = crawler._RateLimiter(0.25)
    inicio = time.time()
    lim.espera("host.com")
    lim.espera("host.com")
    assert time.time() - inicio >= 0.2
