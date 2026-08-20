"""
Exploradores de blockchain para endereços de cripto.

O motor extrai endereços BTC/ETH/XMR das páginas que rastreia, mas um endereço
sozinho não diz nada. O valor está em ver as transações e checar se o endereço
já foi denunciado por golpe. Este módulo transforma cada endereço encontrado
em links diretos:

- explorador da blockchain (transações, saldo, histórico);
- base de denúncia de golpe/abuso;
- lista de sanções da OFAC.

Fontes selecionadas do OSINT-Framework (lockfale), categoria Blockchain.
São deeplinks — abrem já no endereço.
"""

from __future__ import annotations

from urllib.parse import quote

from .findings import Confidence, Finding, FindingKind

# moeda → [(rótulo, template com {addr}, descrição)]
_EXPLORADORES = {
    "BTC": [
        ("Mempool.space", "https://mempool.space/address/{addr}",
         "Transações, saldo e histórico do endereço Bitcoin"),
        ("Blockchair", "https://blockchair.com/bitcoin/address/{addr}",
         "Explorador com análise e exportação"),
        ("Bitcoin Abuse", "https://www.bitcoinabuse.com/reports/{addr}",
         "Denúncias de golpe/extorsão ligadas ao endereço"),
        ("Chainabuse", "https://www.chainabuse.com/address/{addr}",
         "Denúncias de fraude (multi-blockchain)"),
    ],
    "ETH": [
        ("Etherscan", "https://etherscan.io/address/{addr}",
         "Transações, tokens e contratos do endereço Ethereum"),
        ("Blockchair", "https://blockchair.com/ethereum/address/{addr}",
         "Explorador alternativo"),
        ("Chainabuse", "https://www.chainabuse.com/address/{addr}",
         "Denúncias de fraude ligadas ao endereço"),
    ],
    "XMR": [
        # Monero é privado por desenho: não há consulta por endereço, só por tx.
        ("XMRChain", "https://xmrchain.net/",
         "Explorador Monero — Monero não permite busca por endereço (privacidade)"),
    ],
}


def links_for(moeda: str, endereco: str) -> list[tuple[str, str, str]]:
    """(rótulo, url, descrição) para uma moeda+endereço."""
    out: list[tuple[str, str, str]] = []
    for rotulo, template, desc in _EXPLORADORES.get(moeda.upper(), []):
        if "{addr}" in template:
            out.append((rotulo, template.format(addr=quote(endereco, safe="")), desc))
        else:
            out.append((rotulo, template, desc))
    return out


def crypto_findings(cripto_facts) -> list[Finding]:
    """
    Recebe os fatos do tipo CRYPTO já consolidados e devolve LINK findings
    (explorador + denúncia) para cada endereço. Aparecem em «Fontes para abrir».

    Cada fato de cripto tem value no formato "BTC: <endereço>".
    """
    out: list[Finding] = []
    for fato in cripto_facts:
        valor = getattr(fato, "value", "") or ""
        if ":" not in valor:
            continue
        moeda, _, endereco = valor.partition(":")
        moeda, endereco = moeda.strip().upper(), endereco.strip()
        if not endereco:
            continue
        for rotulo, url, desc in links_for(moeda, endereco):
            out.append(Finding(
                kind=FindingKind.LINK,
                value=f"{moeda} — {rotulo}",
                source="crypto_links", source_label="Explorador de blockchain",
                url=url, confidence=Confidence.UNVERIFIED,
                detail=f"{desc}. Endereço: {endereco[:20]}…",
                raw={"moeda": moeda, "endereco": endereco},
            ))
    return out
