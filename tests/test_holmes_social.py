"""Fontes gratuitas de conta por username. net.get_json é mockado — sem rede."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import net, social  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import FindingKind  # noqa: E402


def test_keybase_extrai_contas_nome_e_cripto(monkeypatch):
    fake = {"them": [{
        "profile": {"full_name": "Ada Lovelace", "location": "Londres"},
        "proofs_summary": {"all": [
            {"proof_type": "twitter", "nametag": "adalove",
             "service_url": "https://twitter.com/adalove"},
            {"proof_type": "github", "nametag": "ada",
             "service_url": "https://github.com/ada"},
        ]},
        "cryptocurrency_addresses": {
            "bitcoin": [{"address": "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"}],
        },
    }]}
    monkeypatch.setattr(net, "get_json", lambda *a, **k: fake)
    out = list(social.keybase_findings(detect("adalove")))
    kinds = {f.kind for f in out}
    assert FindingKind.ACCOUNT in kinds
    assert any(f.kind is FindingKind.NAME and "Ada" in f.value for f in out)
    assert any(f.kind is FindingKind.CRYPTO and "BTC" in f.value for f in out)
    assert any("X/Twitter" in f.value for f in out)


def test_keybase_sem_usuario_nao_gera_nada(monkeypatch):
    monkeypatch.setattr(net, "get_json", lambda *a, **k: {"them": []})
    assert list(social.keybase_findings(detect("ninguem"))) == []


def test_gitlab_perfil_e_nome(monkeypatch):
    fake = [{"username": "torvalds", "name": "Linus", "web_url": "https://gitlab.com/torvalds"}]
    monkeypatch.setattr(net, "get_json", lambda *a, **k: fake)
    out = list(social.gitlab_findings(detect("torvalds")))
    assert any(f.kind is FindingKind.ACCOUNT and "GitLab" in f.value for f in out)
    assert any(f.kind is FindingKind.NAME and "Linus" in f.value for f in out)


def test_gitlab_lista_vazia(monkeypatch):
    monkeypatch.setattr(net, "get_json", lambda *a, **k: [])
    assert list(social.gitlab_findings(detect("naoexiste"))) == []


def test_hackernews_conta_e_email_da_bio(monkeypatch):
    fake = {"username": "pg", "karma": 155000, "about": "contato: pg@example.org"}
    monkeypatch.setattr(net, "get_json", lambda *a, **k: fake)
    out = list(social.hackernews_findings(detect("pg")))
    assert any(f.kind is FindingKind.ACCOUNT for f in out)
    assert any(f.kind is FindingKind.EMAIL and "pg@example.org" in f.value for f in out)


def test_reddit_conta_com_carma(monkeypatch):
    fake = {"data": {"name": "spez", "total_karma": 900000, "created_utc": 1118030400}}
    monkeypatch.setattr(net, "get_json", lambda *a, **k: fake)
    out = list(social.reddit_findings(detect("spez")))
    assert len(out) == 1
    assert out[0].kind is FindingKind.ACCOUNT
    assert "u/spez" in out[0].value


def test_reddit_sem_conta(monkeypatch):
    monkeypatch.setattr(net, "get_json", lambda *a, **k: {"data": {}})
    assert list(social.reddit_findings(detect("fantasma"))) == []


def test_conectores_registrados(monkeypatch):
    from holmes.connectors import Mode, connectors_for, ensure_registered

    ensure_registered()
    conns = {c.id for c in connectors_for(detect("qualquer"), {Mode.AUTO})}
    assert {"keybase", "gitlab", "hackernews", "reddit_api"} <= conns
