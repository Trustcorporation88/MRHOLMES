"""
Busca reversa de foto, histórico de dossiês e tribunais estaduais por nome.
Nenhum teste toca a rede.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import facesearch, history  # noqa: E402
from holmes.br import br_deeplinks  # noqa: E402
from holmes.dossier import Dossier  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import ConnectorResult, Confidence, Finding, FindingKind  # noqa: E402


# ── busca reversa de foto ────────────────────────────────────────────────────

def test_reverse_links_carregam_a_foto():
    ls = facesearch.reverse_image_links("https://site.com/foto.jpg")
    motores = {r[0] for r in ls}
    assert {"Yandex Imagens", "Google Lens", "TinEye"} <= motores
    # A URL da foto vai codificada dentro de cada link.
    assert all("foto.jpg" in u or "foto%2Ejpg" in u or "foto" in u for _r, u, _d in ls)


def test_face_findings_deduplica_e_limita():
    ff = facesearch.face_findings(
        ["https://a.com/1.jpg", "https://a.com/1.jpg", "https://a.com/2.jpg"]
    )
    # 2 fotos distintas × 4 motores = 8.
    assert len(ff) == 8
    assert all(f.kind is FindingKind.LINK for f in ff)


def test_face_findings_respeita_teto():
    muitas = [f"https://a.com/{i}.jpg" for i in range(10)]
    ff = facesearch.face_findings(muitas, max_images=2)
    assert len(ff) == 8  # 2 × 4


# ── tribunais estaduais por nome ─────────────────────────────────────────────

def test_nome_gera_varios_tribunais_estaduais():
    rotulos = [r for r, _u, _d in br_deeplinks(detect("Maria Souza"))]
    tribunais = [r for r in rotulos if "processos por parte" in r]
    assert len(tribunais) >= 6
    assert any("TJSP" in r for r in tribunais)
    assert any("TJBA" in r for r in tribunais)


def test_tribunal_estadual_leva_o_nome_na_url():
    for rotulo, url, _d in br_deeplinks(detect("Maria Souza")):
        if "processos por parte" in rotulo:
            assert "NMPARTE" in url
            assert "Maria" in url


def test_tjms_usa_cpopg5():
    for rotulo, url, _d in br_deeplinks(detect("Maria Souza")):
        if rotulo.startswith("TJMS"):
            assert "cpopg5" in url


# ── histórico ────────────────────────────────────────────────────────────────

def _hist_temp(monkeypatch):
    d = pathlib.Path(tempfile.mkdtemp()) / "hist"
    monkeypatch.setattr(history, "HISTORY_DIR", d)
    return d


def _dossie(alvo: str, findings: list[Finding]) -> Dossier:
    d = Dossier(entity=detect(alvo))
    d.add_results([ConnectorResult("t", "T", True, findings)])
    d.consolidate()
    return d


def test_salva_e_lista(monkeypatch):
    _hist_temp(monkeypatch)
    d = _dossie("Fulano de Tal", [Finding(FindingKind.EMAIL, "x@y.com", "t")])
    rid = history.save(d)
    assert rid
    entradas = history.list_entries()
    assert len(entradas) == 1
    assert entradas[0]["alvo"] == "Fulano de Tal"


def test_dois_saves_no_mesmo_segundo_nao_colidem(monkeypatch):
    _hist_temp(monkeypatch)
    a = history.save(_dossie("Alvo X", [Finding(FindingKind.EMAIL, "a@x.com", "t")]))
    b = history.save(_dossie("Alvo X", [Finding(FindingKind.EMAIL, "b@x.com", "t")]))
    assert a != b
    assert len(history.list_entries()) == 2


def test_filtro_por_alvo(monkeypatch):
    _hist_temp(monkeypatch)
    history.save(_dossie("Joao Silva", [Finding(FindingKind.NAME, "Joao Silva", "t")]))
    history.save(_dossie("Maria Souza", [Finding(FindingKind.NAME, "Maria Souza", "t")]))
    assert len(history.list_entries("maria")) == 1
    assert len(history.list_entries()) == 2


def test_diff_mostra_novidade(monkeypatch):
    _hist_temp(monkeypatch)
    velho = history.save(_dossie("Alvo", [
        Finding(FindingKind.EMAIL, "x@y.com", "t", confidence=Confidence.CONFIRMED),
    ]))
    novo = history.save(_dossie("Alvo", [
        Finding(FindingKind.EMAIL, "x@y.com", "t"),
        Finding(FindingKind.PHONE, "+5511999998888", "t"),
        Finding(FindingKind.ACCOUNT, "Instagram: @alvo", "t", url="https://instagram.com/alvo"),
    ]))
    d = history.diff(velho, novo)
    assert d["tem_novidade"]
    assert "+5511999998888" in d["mudancas"]["Telefones"]["novos"]


def test_diff_sem_mudanca(monkeypatch):
    _hist_temp(monkeypatch)
    f = [Finding(FindingKind.EMAIL, "x@y.com", "t")]
    a = history.save(_dossie("Alvo", f))
    b = history.save(_dossie("Alvo", [Finding(FindingKind.EMAIL, "x@y.com", "t")]))
    d = history.diff(a, b)
    assert d["mudancas"] == {}


def test_prune_respeita_teto(monkeypatch):
    _hist_temp(monkeypatch)
    monkeypatch.setattr(history, "MAX_ITEMS", 3)
    for i in range(6):
        history.save(_dossie(f"Alvo {i}", [Finding(FindingKind.NAME, f"Alvo {i}", "t")]))
    assert len(history.list_entries()) <= 3


# ── Hudson Rock (infostealer) ────────────────────────────────────────────────

def test_hudsonrock_extrai_stealers(monkeypatch):
    from holmes import net
    from holmes.connectors.auto import _hudsonrock

    fake = {
        "stealers": [
            {"stealer_family": "Lumma", "date_compromised": "2024-08-24T00:00:00Z",
             "computer_name": "pc1", "operating_system": "Windows 11", "ip": "1.2.*.*"},
            {"stealer_family": "Vidar", "date_compromised": "2022-01-10T00:00:00Z"},
        ],
        "total_user_services": 90, "total_corporate_services": 2,
    }
    monkeypatch.setattr(net, "get_json", lambda *a, **k: fake)
    out = list(_hudsonrock(detect("alvo@x.com")))
    assert out and out[0].kind is FindingKind.BREACH
    assert "3 máquina" not in out[0].value  # são 2
    assert any("Lumma" in f.value for f in out)


def test_hudsonrock_sem_infeccao_nao_gera_nada(monkeypatch):
    from holmes import net
    from holmes.connectors.auto import _hudsonrock

    monkeypatch.setattr(net, "get_json", lambda *a, **k: {"stealers": []})
    assert list(_hudsonrock(detect("limpo@x.com"))) == []


def test_hudsonrock_ignora_tipo_errado():
    from holmes.connectors.auto import _hudsonrock

    assert list(_hudsonrock(detect("+5511999998888"))) == []
