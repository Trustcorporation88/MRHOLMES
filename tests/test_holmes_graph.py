"""Grafo de conexões do dossiê. Sem rede."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import graph  # noqa: E402
from holmes.dossier import Dossier  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import ConnectorResult, Confidence, Finding, FindingKind  # noqa: E402


def _dossie(findings):
    d = Dossier(entity=detect("Empresa Alvo"))
    d.add_results([ConnectorResult("r", "R", True, findings)])
    d.consolidate()
    return d


def test_alvo_sempre_presente_no_centro():
    d = _dossie([Finding(FindingKind.EMAIL, "x@y.com", "r")])
    g = graph.build(d)
    alvo = [n for n in g["nodes"] if n["id"] == "alvo"]
    assert len(alvo) == 1
    assert alvo[0]["shape"] == "star"


def test_socio_liga_na_empresa_nao_no_alvo():
    d = _dossie([
        Finding(FindingKind.COMPANY, "ACME LTDA", "receita_cnpj", confidence=Confidence.CONFIRMED),
        Finding(FindingKind.NAME, "Joao Silva", "receita_cnpj",
                confidence=Confidence.CONFIRMED, detail="Sócio de ACME LTDA"),
    ])
    g = graph.build(d)
    empresa = next(n["id"] for n in g["nodes"] if n["id"].startswith("empresa"))
    socio_edges = [e for e in g["edges"] if e["to"].startswith("nome")]
    assert socio_edges
    assert all(e["from"] == empresa for e in socio_edges)


def test_nome_sem_ser_socio_liga_no_alvo():
    d = _dossie([
        Finding(FindingKind.NAME, "Fulano Detectado", "github",
                confidence=Confidence.CONFIRMED, detail="Nome no perfil"),
    ])
    g = graph.build(d)
    edge = next(e for e in g["edges"] if e["to"].startswith("nome"))
    assert edge["from"] == "alvo"


def test_ruido_nao_vira_no():
    d = _dossie([
        Finding(FindingKind.NOTE, "observação técnica", "r"),
        Finding(FindingKind.LINK, "Escavador", "r", url="https://escavador.com"),
        Finding(FindingKind.WEB_RESULT, "resultado", "r", url="https://x.com"),
        Finding(FindingKind.EMAIL, "x@y.com", "r"),
    ])
    g = graph.build(d)
    # Só alvo + e-mail.
    tipos = {n["id"].split(":")[0] for n in g["nodes"]}
    assert "email" in tipos
    assert "nota" not in tipos and "link" not in tipos and "resultado_web" not in tipos


def test_respeita_score_minimo():
    d = _dossie([
        Finding(FindingKind.EMAIL, "forte@y.com", "a", confidence=Confidence.CONFIRMED),
        Finding(FindingKind.EMAIL, "fraco@y.com", "b", confidence=Confidence.UNVERIFIED),
    ])
    g = graph.build(d, min_score=0.5)
    labels = " ".join(n["label"] for n in g["nodes"])
    assert "forte@y.com" in labels
    assert "fraco@y.com" not in labels


def test_html_autocontido_e_seguro():
    d = _dossie([Finding(FindingKind.NOTE, "<script>alert(1)</script>", "r")])
    h = graph.to_html(d)
    assert h.startswith("<!DOCTYPE html>")
    assert "vis-network" in h
    # O valor do alvo é escapado no HTML (legenda).
    d2 = Dossier(entity=detect("<b>x</b>"))
    d2.consolidate()
    assert "<b>x</b>" not in graph.to_html(d2)


def test_teto_de_nos():
    muitos = [Finding(FindingKind.EMAIL, f"e{i}@y.com", "r", confidence=Confidence.CONFIRMED)
              for i in range(200)]
    g = graph.build(_dossie(muitos), max_nos=30)
    assert len(g["nodes"]) <= 30


def test_quebra_de_rotulo_longo():
    r = graph._quebra("um rotulo muito muito muito muito longo mesmo demais", 20)
    assert "\n" in r
    assert all(len(linha) <= 24 for linha in r.split("\n"))
