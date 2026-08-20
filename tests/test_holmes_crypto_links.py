"""Exploradores de blockchain para endereços de cripto. Sem rede."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import crypto_links  # noqa: E402
from holmes.findings import CorroboratedFact, Finding, FindingKind  # noqa: E402


def test_btc_gera_explorador_e_denuncia():
    ls = crypto_links.links_for("BTC", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
    rotulos = {r for r, _u, _d in ls}
    assert "Mempool.space" in rotulos
    assert any("abuse" in u.lower() or "chainabuse" in u.lower() for _r, u, _d in ls)
    # o endereço vai em todas as URLs de explorador
    assert all("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in u or "xmrchain" in u.lower()
               for _r, u, _d in ls)


def test_eth_usa_etherscan():
    ls = crypto_links.links_for("ETH", "0x52908400098527886E0F7030069857D2E4169EE7")
    assert any("etherscan.io/address/0x" in u for _r, u, _d in ls)


def test_moeda_desconhecida_vazia():
    assert crypto_links.links_for("DOGE", "x") == []


def test_crypto_findings_de_fatos():
    facts = [
        CorroboratedFact(kind=FindingKind.CRYPTO, value="BTC: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                         findings=[Finding(FindingKind.CRYPTO, "BTC: x", "crawler")]),
        CorroboratedFact(kind=FindingKind.CRYPTO, value="ETH: 0xabc0000000000000000000000000000000000000",
                         findings=[Finding(FindingKind.CRYPTO, "ETH: x", "crawler")]),
    ]
    out = crypto_links.crypto_findings(facts)
    assert out and all(f.kind is FindingKind.LINK for f in out)
    assert any("Mempool" in f.value for f in out)
    assert any("Etherscan" in f.value for f in out)
    assert all(f.url for f in out)


def test_crypto_findings_ignora_valor_sem_endereco():
    facts = [CorroboratedFact(kind=FindingKind.CRYPTO, value="BTC:", findings=[])]
    assert crypto_links.crypto_findings(facts) == []
