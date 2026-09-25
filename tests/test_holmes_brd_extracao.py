"""JusBrasil pelo Unlocker, coletores de LinkedIn/Instagram, índice de sócios e rendimento das fontes."""

from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import pytest

from holmes import jusbrasil, net, social_brd, socios_rfb, source_yield
from holmes.connectors import get_connector
from holmes.entity import detect
from holmes.findings import Confidence, FindingKind

FIX = Path(__file__).parent / "fixtures"


# ── JusBrasil (amostras reais capturadas pela Bright Data) ──────────────────

def test_cards_da_busca_por_nome():
    cards = jusbrasil.parse_cards((FIX / "jusbrasil_busca_nome.md").read_text())
    pessoa = next(c for c in cards if c.tipo == "pessoa")
    assert pessoa.nome == "Sergio Fernando Moro" and pessoa.idade == "50 a 54 anos"
    empresa = next(c for c in cards if c.tipo == "empresa")
    assert empresa.cnpj == "47.518.403/0001-90" and empresa.uf == "Paraná"


def test_diarios_da_busca_por_nome():
    total, itens = jusbrasil.parse_diarios((FIX / "jusbrasil_busca_nome.md").read_text())
    assert total == "mais de 10.000"
    assert itens[0]["data"] == "28/08/2025"
    assert itens[0]["orgao"] == "Tribunal Superior Eleitoral"
    assert itens[1]["trecho"].startswith("REPRESENTADO")


def test_pagina_da_pessoa_lista_empresas_com_cargo():
    dados = jusbrasil.parse_pessoa((FIX / "jusbrasil_pessoa.md").read_text())
    assert dados["cpf_parcial"] == "***.***.629-**"
    assert dados["estados"].startswith("Paraná")
    cnpjs = {e.cnpj: e.relacao for e in dados["empresas"]}
    assert cnpjs["38.193.419/0001-80"] == "Sócio-Administrador"
    assert "39.157.336/0001-06" in cnpjs


def test_nome_findings_segue_para_a_pagina_da_pessoa(monkeypatch):
    paginas = {
        "busca": (FIX / "jusbrasil_busca_nome.md").read_text(),
        "/cpf-": (FIX / "jusbrasil_pessoa.md").read_text(),
    }
    chamadas = []

    def fake_fetch(url, **kw):
        chamadas.append(url)
        assert kw.get("data_format") == "markdown"
        return paginas["/cpf-"] if "/cpf-" in url else paginas["busca"]

    monkeypatch.setattr(net, "unlocked_fetch", fake_fetch)
    achados = list(jusbrasil.findings(detect("Sergio Fernando Moro")))
    assert len(chamadas) == 2  # busca + página da única pessoa com o nome exato
    empresas = [f for f in achados if f.kind is FindingKind.COMPANY]
    socio = next(f for f in empresas if "38.193.419/0001-80" in f.detail)
    assert socio.confidence is Confidence.LIKELY and "Sócio-Administrador" in socio.detail
    assert any(f.kind is FindingKind.LEGAL for f in achados)


def test_cnpj_findings_traz_relacionadas_e_contato(monkeypatch):
    monkeypatch.setattr(net, "unlocked_fetch",
                        lambda url, **kw: (FIX / "jusbrasil_empresa.md").read_text())
    achados = list(jusbrasil.findings(detect("33.000.167/0001-01")))
    assert any(f.kind is FindingKind.EMAIL and f.value == "cc-rfisc@petrobras.com.br" for f in achados)
    rel = [f for f in achados if f.kind is FindingKind.COMPANY]
    assert len(rel) == 2 and "Sociedade Consorciada" in rel[0].detail


class _Resp:
    def __init__(self, status=200, text="", headers=None, payload=None):
        self.status_code, self.text, self.headers, self._payload = status, text, headers or {}, payload

    def json(self):
        return self._payload


def test_unlocker_reconhece_bloqueio_devolvido_com_http_200(monkeypatch):
    monkeypatch.setenv("HOLMES_UNLOCKER", "1")
    monkeypatch.setattr(net, "has_key", lambda n: n == "brightdata")
    monkeypatch.setattr(net, "get_key", lambda n: "tok")
    monkeypatch.setattr(net, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr(net._SESSION, "post", lambda *a, **k: _Resp(
        text="Residential Failed (bad_endpoint): Requested site is not available"))
    with pytest.raises(net.UnlockerError, match="KYC"):
        net.unlocked_fetch("https://www.escavador.com/busca?q=x", data_format="markdown")


def test_conectores_pagos_ficam_pulados_sem_interruptor(monkeypatch):
    monkeypatch.delenv("HOLMES_UNLOCKER", raising=False)
    monkeypatch.delenv("HOLMES_BRD_DATASETS", raising=False)
    for cid in ("jusbrasil", "brd_linkedin", "brd_instagram"):
        ok, motivo = get_connector(cid).availability()
        assert not ok and "desligado" in motivo


# ── coletores LinkedIn / Instagram ──────────────────────────────────────────

LINKEDIN = {
    "name": "Fulana de Tal", "city": "Curitiba, Paraná", "position": "Diretora Financeira",
    "current_company": {"name": "Empresa X", "link": "https://www.linkedin.com/company/x"},
    "experience": [{"title": "Analista", "company": "Banco Y", "start_date": "2015", "end_date": "2019"}],
    "education": [{"title": "UFPR", "degree": "Economia"}],
    "avatar": "https://media.licdn.com/foto.jpg", "followers": 900,
}


def test_linkedin_por_link_traz_cargo_empresa_e_formacao(monkeypatch):
    monkeypatch.setattr(net, "brd_dataset_scrape", lambda ds, url: LINKEDIN)
    achados = list(social_brd.linkedin_findings(detect("https://www.linkedin.com/in/fulana-tal/")))
    tipos = {f.kind for f in achados}
    assert {FindingKind.ACCOUNT, FindingKind.NAME, FindingKind.COMPANY, FindingKind.IMAGE} <= tipos
    assert any(f.value == "Banco Y" for f in achados)


def test_linkedin_por_nome_descarta_perfil_de_outra_pessoa(monkeypatch):
    from holmes import serp

    monkeypatch.setattr(serp, "search", lambda q, limit=5: [serp.SerpHit(
        title="Fulana de Tal - Diretora | LinkedIn", url="https://br.linkedin.com/in/fulana-tal",
        snippet="", position=1, engine="brightdata", query=q)])
    monkeypatch.setattr(net, "brd_dataset_scrape", lambda ds, url: dict(LINKEDIN, name="Beltrano Souza"))
    assert list(social_brd.linkedin_findings(detect("Fulana de Tal"))) == []


def test_instagram_por_username_traz_bio_e_contato(monkeypatch):
    urls = []

    def fake(ds, url):
        urls.append((ds, url))
        return {"full_name": "Loja Z", "followers": 1200, "biography": "Moda feminina",
                "business_email": "Contato@LojaZ.com", "business_phone_number": "+55 11 99999-0000",
                "external_url": ["https://lojaz.com.br"], "is_verified": False}

    monkeypatch.setattr(net, "brd_dataset_scrape", fake)
    achados = list(social_brd.instagram_findings(detect("@lojaz")))
    assert urls == [("instagram_profile", "https://www.instagram.com/lojaz/")]
    assert any(f.kind is FindingKind.EMAIL and f.value == "contato@lojaz.com" for f in achados)
    assert any(f.kind is FindingKind.PHONE for f in achados)


def test_coletor_acompanha_snapshot_quando_a_coleta_demora(monkeypatch):
    monkeypatch.setenv("HOLMES_BRD_DATASETS", "1")
    monkeypatch.setattr(net, "has_key", lambda n: n == "brightdata")
    monkeypatch.setattr(net, "get_key", lambda n: "tok")
    monkeypatch.setattr(net, "cache_get", lambda *a, **k: None)
    monkeypatch.setattr(net, "cache_set", lambda *a, **k: None)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(net._SESSION, "post", lambda *a, **k: _Resp(202, payload={"snapshot_id": "s_1"}))
    estados = iter(["running", "ready"])

    def fake_get(url, **kw):
        if "/progress/" in url:
            return _Resp(payload={"status": next(estados)})
        return _Resp(text='[{"name": "Fulana"}]')

    monkeypatch.setattr(net._SESSION, "get", fake_get)
    assert net.brd_dataset_scrape("linkedin_person", "https://www.linkedin.com/in/x") == {"name": "Fulana"}


# ── índice de sócios da Receita ─────────────────────────────────────────────

def _zip_socios(path: Path, linhas: list[str]) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("K3241.K03200Y0.D60913.SOCIOCSV", "\n".join(linhas).encode("latin-1"))
    path.write_bytes(buf.getvalue())
    return path


LINHAS = [
    '"11222333";"2";"JOSÉ DA SILVA";"***982247**";"49";"20150301";"";"***000000**";"";"00";"5"',
    '"44555666";"2";"JOSE DA SILVA";"***982247**";"22";"20180710";"";"***000000**";"";"00";"5"',
    '"44555666";"2";"MARIA SOUZA";"***111222**";"22";"20180710";"";"***000000**";"";"00";"4"',
    '"77888999";"2";"JOSE DA SILVA";"***555666**";"49";"20200101";"";"***000000**";"";"00";"7"',
]


@pytest.fixture
def indice(tmp_path, monkeypatch):
    pasta = tmp_path / "2026-09"
    pasta.mkdir()
    _zip_socios(pasta / "Socios0.zip", LINHAS)
    db = tmp_path / "socios.sqlite"
    monkeypatch.setattr(socios_rfb, "DB_PATH", db)
    assert socios_rfb.build_from_dir(pasta) == 4
    monkeypatch.setattr(socios_rfb, "_razoes", lambda cnpjs: {c: f"EMPRESA {c[:2]}" for c in cnpjs})
    return db


def test_cnpj_da_matriz_a_partir_do_basico():
    assert socios_rfb.cnpj_matriz("33000167") == "33.000.167/0001-01"


def test_indice_status_e_consulta_por_nome(indice):
    st = socios_rfb.status()
    assert st["baixado"] and st["total_socios"] == 4 and st["mes_referencia"] == "2026-09"
    # Acento e caixa não importam; dois CPFs mascarados = duas pessoas.
    linhas = socios_rfb.por_nome("José da Silva")
    assert {l["doc"] for l in linhas} == {"***982247**", "***555666**"}
    achados = list(socios_rfb.findings(detect("José da Silva")))
    assert "2 pessoas diferentes" in achados[0].value
    assert all(f.confidence is Confidence.POSSIBLE for f in achados if f.kind is FindingKind.COMPANY)


def test_indice_cnpj_acha_as_outras_empresas_do_socio(indice):
    achados = list(socios_rfb.findings(detect(socios_rfb.cnpj_matriz("11222333"))))
    empresas = [f for f in achados if f.kind is FindingKind.COMPANY]
    assert len(empresas) == 1
    assert empresas[0].raw["cnpj_basico"] == "44555666"
    assert empresas[0].confidence is Confidence.CONFIRMED


def test_indice_cpf_com_nome_do_portal_confirma(indice, monkeypatch):
    monkeypatch.setattr(socios_rfb, "_nome_do_cpf", lambda cpf: "Jose da Silva")
    achados = list(socios_rfb.findings(detect("529.982.247-25")))
    assert len(achados) == 2
    assert all(f.confidence is Confidence.CONFIRMED for f in achados)


def test_indice_cpf_sem_nome_so_lista_candidatos(indice, monkeypatch):
    monkeypatch.setattr(socios_rfb, "_nome_do_cpf", lambda cpf: "")
    achados = list(socios_rfb.findings(detect("529.982.247-25")))
    assert len(achados) == 1 and achados[0].confidence is Confidence.POSSIBLE


# ── rendimento das fontes ───────────────────────────────────────────────────

def _execucao(cid, status="ok", valores=(), erro=None):
    return {"connector_id": cid, "connector_label": cid, "status": status, "ok": status == "ok",
            "error": erro, "elapsed_ms": 100,
            "findings": [{"kind": k, "value": v} for k, v in valores]}


def test_rendimento_da_veredito_por_fonte(tmp_path, monkeypatch):
    monkeypatch.setattr(source_yield, "DATA_DIR", tmp_path)
    monkeypatch.setattr(source_yield, "DB_PATH", tmp_path / "y.sqlite")
    for i in range(3):
        source_yield._gravar(f"inv{i}", time.time(), "cpf", [
            _execucao("boa", valores=[("nome", "Fulano"), ("empresa", f"E{i}")]),
            _execucao("eco", valores=[("nome", "Fulano")]),        # só repete a boa
            _execucao("vazia", valores=[("link", "abre home")]),    # link não é fato
            _execucao("quebra", status="erro", erro="HTTP 503"),
            _execucao("boa", valores=[("empresa", "Pivo")]),        # a mesma fonte no pivô soma
        ])
    rel = {r["fonte"]: r for r in source_yield.report(min_execucoes=3)}
    assert rel["vazia"]["veredito"] == "cortar"
    assert rel["quebra"]["veredito"] == "quebrada" and rel["quebra"]["ultimo_erro"] == "HTTP 503"
    assert rel["boa"]["veredito"] == "manter"
    assert rel["boa"]["execucoes"] == 3 and rel["boa"]["exclusivos"] == 6
    assert rel["eco"]["exclusivos"] == 0 and rel["eco"]["veredito"] == "manter"


def test_rendimento_com_poucas_execucoes_nao_julga(tmp_path, monkeypatch):
    monkeypatch.setattr(source_yield, "DATA_DIR", tmp_path)
    monkeypatch.setattr(source_yield, "DB_PATH", tmp_path / "y.sqlite")
    source_yield._gravar("x", time.time(), "nome", [_execucao("vazia")])
    assert source_yield.report(min_execucoes=5)[0]["veredito"] == "poucos dados"
