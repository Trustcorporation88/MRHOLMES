"""Wikipédia / Wikidata. net.get_json mockado por URL — sem rede."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import net, wiki  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import FindingKind  # noqa: E402


def _fake_completo(url, params=None, timeout=12, ttl=0, headers=None):
    if "opensearch" in (params or {}).get("action", ""):
        return ["Ada Lovelace", ["Ada Lovelace"], [""], ["https://pt.wikipedia.org/wiki/Ada_Lovelace"]]
    if "rest_v1/page/summary" in url:
        return {
            "title": "Ada Lovelace", "type": "standard",
            "extract": "Matemática e escritora britânica, pioneira da computação.",
            "thumbnail": {"source": "https://x.com/ada.jpg"},
            "content_urls": {"desktop": {"page": "https://pt.wikipedia.org/wiki/Ada_Lovelace"}},
        }
    action = (params or {}).get("action", "")
    if action == "wbsearchentities":
        return {"search": [{"id": "Q7259"}]}
    if action == "wbgetentities" and (params or {}).get("props") == "claims|labels":
        return {"entities": {"Q7259": {"claims": {
            "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+1815-12-10T00:00:00Z"}}}}],
            "P106": [{"mainsnak": {"datavalue": {"value": {"id": "Q170790"}}}}],
            "P39": [{"mainsnak": {"datavalue": {"value": {"id": "Q1234"}}}}],
        }}}}
    if action == "wbgetentities" and (params or {}).get("props") == "labels":
        return {"entities": {
            "Q170790": {"labels": {"pt": {"value": "matemática"}}},
            "Q1234": {"labels": {"pt": {"value": "deputada"}}},
        }}
    return {}


def test_wiki_findings_bio_foto_nascimento_e_ocupacao(monkeypatch):
    monkeypatch.setattr(net, "get_json", _fake_completo)
    out = list(wiki.wiki_findings(detect("Ada Lovelace")))
    kinds = {f.kind for f in out}
    assert FindingKind.NOTE in kinds
    assert FindingKind.IMAGE in kinds
    assert any("Wikipédia: Ada Lovelace" in f.value for f in out)
    assert any(f.value == "https://x.com/ada.jpg" for f in out)
    assert any("1815-12-10" in f.value for f in out)
    assert any("matemática" in f.value for f in out)


def test_cargo_publico_gera_gatilho_pep(monkeypatch):
    monkeypatch.setattr(net, "get_json", _fake_completo)
    out = list(wiki.wiki_findings(detect("Ada Lovelace")))
    assert any("POLITICAMENTE EXPOSTA" in f.value.upper() and "deputada" in f.value
                for f in out)


def test_sem_pagina_encontrada_devolve_vazio(monkeypatch):
    def fake(url, params=None, timeout=12, ttl=0, headers=None):
        if (params or {}).get("action") == "opensearch":
            return ["x", [], [], []]
        if (params or {}).get("action") == "wbsearchentities":
            return {"search": []}
        return {}
    monkeypatch.setattr(net, "get_json", fake)
    assert list(wiki.wiki_findings(detect("Ninguém Conhecido"))) == []


def test_desambiguacao_e_ignorada(monkeypatch):
    def fake(url, params=None, timeout=12, ttl=0, headers=None):
        if (params or {}).get("action") == "opensearch":
            return ["x", ["Termo Ambíguo"], [], []]
        if "rest_v1/page/summary" in url:
            return {"type": "disambiguation"}
        if (params or {}).get("action") == "wbsearchentities":
            return {"search": []}
        return {}
    monkeypatch.setattr(net, "get_json", fake)
    assert list(wiki.wiki_findings(detect("Termo Ambíguo"))) == []


def test_ignora_tipo_de_alvo_nao_suportado(monkeypatch):
    monkeypatch.setattr(net, "get_json", _fake_completo)
    assert list(wiki.wiki_findings(detect("alvo@x.com"))) == []


def test_resolve_labels_sem_qids_nao_chama_rede():
    assert wiki._resolve_labels([]) == {}
