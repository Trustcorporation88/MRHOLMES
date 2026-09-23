#!/usr/bin/env python3
"""
Mede quais sites do WhatsMyName bloqueiam este servidor.

O número que decide se vale contratar Web Unlocker — e para quantos sites.
Não usa Bright Data e não gasta crédito: faz a requisição direta e conta
quem barrou.

    python3 scripts/measure_blocking.py --handle johnsmith
    python3 scripts/measure_blocking.py --handle johnsmith --json relatorio.json

Use um handle que EXISTA em muitas plataformas. Com um handle inexistente
todo mundo responde "não encontrado" e a medição de bloqueio fica pobre.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402

from Core.Support.WhatsMyName import (  # noqa: E402
    _probe,
    load_wmn_data,
    selectable_sites,
)

# Preço por requisição do Web Unlocker. Confirme no seu painel: a tarifa varia
# por plano e muda com o tempo.
PRECO_POR_MIL = 1.50


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--handle", required=True, help="username a testar (use um que exista)")
    ap.add_argument("--max-sites", type=int, default=90)
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--json", dest="json_out", help="grava o relatório bruto neste arquivo")
    ap.add_argument("--credito", type=float, default=57.0, help="crédito disponível em USD")
    args = ap.parse_args()

    print(f"Baixando a lista WhatsMyName...", file=sys.stderr)
    try:
        blob = load_wmn_data()
    except Exception as exc:
        print(f"\nFalhou ao baixar a lista: {exc}", file=sys.stderr)
        print(
            "Se o erro for de allowlist/403, este ambiente está com egress "
            "bloqueado — rode o script onde o app roda de verdade.",
            file=sys.stderr,
        )
        return 2

    sites = selectable_sites(blob, max_sites=args.max_sites)
    print(f"Sondando {len(sites)} sites com o handle @{args.handle}...\n", file=sys.stderr)

    resultados: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {
            pool.submit(_probe, site, args.handle, args.timeout, False): site
            for site in sites
        }
        for fut in as_completed(futs):
            try:
                resultados.append(fut.result())
            except Exception as exc:
                resultados.append({"site": "?", "status": "error", "detail": str(exc)[:80]})

    contagem = Counter(r.get("status", "?") for r in resultados)
    bloqueados = sorted(
        (r for r in resultados if r.get("status") == "blocked"),
        key=lambda r: str(r.get("site", "")),
    )

    total = len(resultados)
    print("=" * 62)
    print(f"RESULTADO — {total} sites sondados com @{args.handle}")
    print("=" * 62)
    for status in ("hit", "miss", "blocked", "error"):
        n = contagem.get(status, 0)
        rotulo = {
            "hit": "perfil encontrado",
            "miss": "respondeu, sem perfil",
            "blocked": "BLOQUEOU",
            "error": "erro de rede/timeout",
        }[status]
        pct = (100.0 * n / total) if total else 0.0
        print(f"  {rotulo:<26} {n:>4}  ({pct:4.1f}%)")

    # Guarda contra medição inválida: taxa alta de erro quase nunca é "os sites
    # caíram" — é o ambiente sem saída para a internet (allowlist, firewall,
    # DNS). Sem esse aviso o relatório parece legítimo e leva à decisão errada.
    n_err = contagem.get("error", 0)
    taxa_err = (100.0 * n_err / total) if total else 0.0
    medicao_valida = taxa_err <= 30.0
    if not medicao_valida:
        print()
        print("!" * 62)
        print(f"AVISO: {taxa_err:.0f}% das sondagens deram erro de rede.")
        print("Isso indica que ESTE AMBIENTE não tem saída para a internet")
        print("(allowlist de egress, firewall ou DNS) — não que os sites")
        print("bloquearam. Os números abaixo NÃO valem para decidir nada.")
        print("Rode o script onde a aplicação roda de verdade.")
        print("!" * 62)

    if bloqueados:
        print(f"\nOs {len(bloqueados)} que bloquearam (candidatos a Web Unlocker):")
        for r in bloqueados:
            print(f"  - {str(r.get('site'))[:38]:<38} HTTP {r.get('http', '?')}")

    n_block = len(bloqueados)
    if n_block and not medicao_valida:
        print("\nEstimativa de custo omitida: a medição acima não é confiável.")
    elif n_block:
        custo_inv = n_block * PRECO_POR_MIL / 1000.0
        print(f"\nCusto estimado a ${PRECO_POR_MIL:.2f}/mil requisições:")
        print(f"  {n_block} sites bloqueados  ->  ${custo_inv:.4f} por investigação")
        if custo_inv > 0:
            print(f"  Com ${args.credito:.2f} de crédito  ->  ~{int(args.credito / custo_inv):,} investigações")
        todos = total * PRECO_POR_MIL / 1000.0
        print(f"\n  (Se roteasse os {total} sites: ${todos:.4f}/investigação -> "
              f"~{int(args.credito / todos):,} investigações. "
              f"Rotear só os bloqueados rende {todos / custo_inv:.1f}x mais.)")
    else:
        print("\nNenhum site bloqueou. Web Unlocker não é necessário para o WhatsMyName aqui.")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                {
                    "handle": args.handle,
                    "total": total,
                    "contagem": dict(contagem),
                    "bloqueados": bloqueados,
                    "resultados": resultados,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nRelatório bruto: {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
