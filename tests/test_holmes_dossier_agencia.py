"""Cartão de identidade + linha do tempo do dossiê. Sem rede."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes.dossier import Dossier  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import ConnectorResult, Confidence, Finding, FindingKind  # noqa: E402


def _dossie(alvo, findings):
    d = Dossier(entity=detect(alvo))
    d.add_results([ConnectorResult("t", "T", True, findings)])
    d.consolidate()
    return d


def test_cartao_reune_o_melhor_de_cada_tipo():
    d = _dossie("Ada Lovelace", [
        Finding(FindingKind.NAME, "Ada Lovelace", "t", confidence=Confidence.CONFIRMED),
        Finding(FindingKind.EMAIL, "ada@x.com", "t"),
        Finding(FindingKind.PHONE, "+5511999998888", "t"),
        Finding(FindingKind.IMAGE, "https://x.com/foto.jpg", "t"),
        Finding(FindingKind.ACCOUNT, "GitHub: @ada", "t"),
        Finding(FindingKind.ACCOUNT, "Keybase: ada", "t"),
    ])
    card = d.identity_card()
    assert card["nome"] == "Ada Lovelace"
    assert card["foto"] == "https://x.com/foto.jpg"
    assert "ada@x.com" in card["emails"]
    assert card["total_contas"] == 2


def test_cartao_marca_bandeiras_de_risco():
    d = _dossie("Fulano", [
        Finding(FindingKind.NOTE, "Consta como pessoa POLITICAMENTE EXPOSTA (deputado)", "t"),
        Finding(FindingKind.BREACH, "LinkedIn", "t"),
        Finding(FindingKind.LEGAL, "SANÇÃO no CEIS", "t"),
    ])
    flags = " ".join(d.identity_card()["flags"]).lower()
    assert "politicamente exposta" in flags
    assert "vazamento" in flags
    assert "sanção" in flags or "sancao" in flags


def test_timeline_ordena_por_data_e_pega_iso_e_br():
    d = _dossie("alvo@x.com", [
        Finding(FindingKind.BREACH, "Adobe", "t", detail="Vazamento em 2013-10-04 — e-mails"),
        Finding(FindingKind.NOTE, "Registrado em: 2001-03-15", "t"),
        Finding(FindingKind.COMPANY, "Empresa X", "t", detail="Sócio, entrada em 20/07/2019"),
    ])
    tl = d.timeline()
    datas = [e["data"] for e in tl]
    assert datas == sorted(datas)
    assert "2001-03-15" in datas
    assert "2013-10-04" in datas
    assert "2019-07-20" in datas  # 20/07/2019 normalizado para ISO


def test_timeline_ignora_resultado_de_busca():
    d = _dossie("Fulano", [
        Finding(FindingKind.WEB_RESULT, "Notícia de 2020-01-01", "t",
                detail="publicado em 2020-01-01"),
    ])
    assert d.timeline() == []


def test_timeline_deduplica():
    d = _dossie("Fulano", [
        Finding(FindingKind.BREACH, "Adobe", "t", detail="2013-10-04"),
        Finding(FindingKind.BREACH, "Adobe", "s", detail="2013-10-04"),
    ])
    assert len(d.timeline()) == 1
