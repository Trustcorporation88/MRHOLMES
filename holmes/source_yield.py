"""
Quanto cada fonte traz de verdade.

Cortar fonte por impressão erra para os dois lados: some com a que acerta
pouco mas acerta o que ninguém mais acha, e mantém a que responde sempre mas
só repete o que outra já trouxe. Este módulo registra, a cada investigação,
o que cada conector entregou e mede três coisas:

* **fatos**: achados que não são link pronto (o link sozinho não prova nada);
* **exclusivos**: fatos que, no dossiê consolidado, só essa fonte trouxe;
* **falha**: quantas vezes deu erro ou estourou o tempo.

A partir disso o relatório dá um veredito por fonte: `manter`, `cortar`
(rodou bastante e nunca trouxe fato), `quebrada` (quase sempre falha) ou
`poucos dados` (ainda não rodou o suficiente para julgar).

    python -m holmes.source_yield              # relatório dos últimos 30 dias
    python -m holmes.source_yield --backfill   # mede também o histórico já salvo
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(os.environ.get("HOLMES_YIELD_DIR", os.environ.get("HOLMES_DATA_DIR", ".holmes_data")))
DB_PATH = DATA_DIR / "source_yield.sqlite"

MIN_EXECUCOES = int(os.environ.get("HOLMES_YIELD_MIN_RUNS", "15"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS execucoes (
    investigacao TEXT,
    quando REAL,
    alvo_tipo TEXT,
    connector_id TEXT,
    connector_label TEXT,
    status TEXT,            -- ok | erro | pulado
    erro TEXT,
    achados INTEGER,
    fatos INTEGER,
    exclusivos INTEGER,
    ms INTEGER,
    PRIMARY KEY (investigacao, connector_id, alvo_tipo)
);
CREATE INDEX IF NOT EXISTS idx_exec_quando ON execucoes(quando);
"""


def _con() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.executescript(_SCHEMA)
    return con


# ── medição de um dossiê ────────────────────────────────────────────────────

def _medir(execucao: list[dict]) -> list[dict]:
    """
    Recebe a lista `execucao` do dossiê serializado (to_dict), para servir
    tanto ao dossiê recém-montado quanto ao histórico gravado em JSON.
    """
    # Quem trouxe cada fato consolidado (pela chave tipo+valor).
    fontes_do_fato: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in execucao:
        for f in r.get("findings") or []:
            if f.get("kind") == "link":
                continue
            chave = (f.get("kind") or "", (f.get("value") or "").strip().lower())
            fontes_do_fato[chave].add(r.get("connector_id") or "")

    linhas = []
    for r in execucao:
        achados = r.get("findings") or []
        chaves = {
            (f.get("kind") or "", (f.get("value") or "").strip().lower())
            for f in achados if f.get("kind") != "link"
        }
        exclusivos = sum(1 for c in chaves if fontes_do_fato.get(c) == {r.get("connector_id")})
        linhas.append({
            "connector_id": r.get("connector_id") or "",
            "connector_label": r.get("connector_label") or "",
            "status": r.get("status") or ("ok" if r.get("ok") else "erro"),
            "erro": (r.get("error") or r.get("skipped_reason") or "")[:200],
            "achados": len(achados),
            "fatos": len(chaves),
            "exclusivos": exclusivos,
            "ms": int(r.get("elapsed_ms") or 0),
        })
    return linhas


def record(dossier, investigacao: str | None = None) -> int:
    """Chamado pelo orquestrador no fim de cada investigação. Nunca levanta."""
    try:
        d = dossier.to_dict()
        return _gravar(
            investigacao or f"{int(time.time() * 1000)}_{id(dossier)}",
            time.time(), (d.get("alvo") or {}).get("type") or dossier.entity.type.value,
            d.get("execucao") or [],
        )
    except Exception:  # noqa: BLE001 — medição nunca derruba investigação
        return 0


def _gravar(investigacao: str, quando: float, alvo_tipo: str, execucao: list) -> int:
    # Um conector pode rodar no alvo e em vários pivôs: soma por investigação.
    agregado: dict[str, dict] = {}
    for l in _medir(execucao):
        a = agregado.get(l["connector_id"])
        if a is None:
            agregado[l["connector_id"]] = dict(l, status_set={l["status"]})
            continue
        for k in ("achados", "fatos", "exclusivos", "ms"):
            a[k] += l[k]
        a["status_set"].add(l["status"])
        a["erro"] = a["erro"] or l["erro"]
    con = _con()
    try:
        for cid, a in agregado.items():
            s = a["status_set"]
            status = "ok" if "ok" in s else "erro" if "erro" in s else "pulado"
            con.execute(
                "INSERT OR REPLACE INTO execucoes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (investigacao, quando, alvo_tipo, cid, a["connector_label"], status,
                 a["erro"], a["achados"], a["fatos"], a["exclusivos"], a["ms"]),
            )
        con.commit()
    finally:
        con.close()
    return len(agregado)


def backfill() -> int:
    """Mede os dossiês já salvos no histórico (arquivo e Supabase)."""
    from . import history

    total = 0
    for e in history.list_entries(limit=10_000):
        reg = history.load(e["id"]) if e.get("id") else None
        if not reg:
            continue
        dossie = reg.get("dossie") or {}
        quando = _ts(reg.get("quando") or dossie.get("iniciado_em"))
        total += bool(_gravar(e["id"], quando, reg.get("tipo") or "",
                              dossie.get("execucao") or []))
    return total


def _ts(iso: str | None) -> float:
    from datetime import datetime

    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except Exception:  # noqa: BLE001
        return time.time()


# ── relatório ───────────────────────────────────────────────────────────────

def report(dias: int = 30, min_execucoes: int = MIN_EXECUCOES) -> list[dict]:
    if not DB_PATH.exists():
        return []
    desde = time.time() - dias * 86400
    con = _con()
    try:
        rows = con.execute(
            """
            SELECT connector_id, MAX(connector_label),
                   COUNT(*),
                   SUM(status = 'ok'), SUM(status = 'erro'), SUM(status = 'pulado'),
                   SUM(CASE WHEN status = 'ok' AND fatos > 0 THEN 1 ELSE 0 END),
                   SUM(fatos), SUM(exclusivos),
                   AVG(CASE WHEN status != 'pulado' THEN ms END),
                   GROUP_CONCAT(DISTINCT alvo_tipo)
            FROM execucoes WHERE quando >= ? GROUP BY connector_id
            """,
            (desde,),
        ).fetchall()
        ultimo_erro = dict(con.execute(
            "SELECT connector_id, erro FROM execucoes WHERE status = 'erro' AND quando >= ? "
            "ORDER BY quando DESC", (desde,)).fetchall()[::-1])
    finally:
        con.close()

    out = []
    for (cid, label, total, ok, erro, pulado, com_fato, fatos, exclusivos, ms, tipos) in rows:
        rodou = (ok or 0) + (erro or 0)
        if rodou < min_execucoes:
            veredito = "poucos dados"
        elif (erro or 0) / rodou >= 0.8:
            veredito = "quebrada"
        elif not fatos:
            veredito = "cortar"
        else:
            veredito = "manter"
        out.append({
            "fonte": cid, "rotulo": label, "execucoes": total, "ok": ok or 0,
            "erro": erro or 0, "pulado": pulado or 0,
            "taxa_acerto": round((com_fato or 0) / (ok or 1), 2) if ok else 0.0,
            "fatos": fatos or 0, "exclusivos": exclusivos or 0,
            "ms_medio": int(ms or 0), "tipos": tipos or "",
            "ultimo_erro": ultimo_erro.get(cid, ""),
            "veredito": veredito,
        })
    ordem = {"cortar": 0, "quebrada": 1, "manter": 2, "poucos dados": 3}
    out.sort(key=lambda r: (ordem[r["veredito"]], -r["exclusivos"], r["fonte"]))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rendimento de cada fonte nas investigações reais")
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--min", type=int, default=MIN_EXECUCOES, help="execuções mínimas para julgar")
    ap.add_argument("--backfill", action="store_true", help="mede também o histórico já salvo")
    ap.add_argument("--json", help="grava o relatório neste arquivo")
    args = ap.parse_args(argv)

    if args.backfill:
        print(f"[source_yield] {backfill()} investigações do histórico medidas")
    linhas = report(args.dias, args.min)
    if args.json:
        Path(args.json).write_text(json.dumps(linhas, ensure_ascii=False, indent=2), encoding="utf-8")
    if not linhas:
        print("Sem medições ainda. Rode investigações ou use --backfill.")
        return 0
    print(f"{'veredito':<13}{'fonte':<28}{'exec':>5}{'ok':>5}{'erro':>5}{'acerto':>8}{'fatos':>7}{'exclus':>7}{'ms':>7}")
    for r in linhas:
        print(f"{r['veredito']:<13}{r['fonte'][:27]:<28}{r['execucoes']:>5}{r['ok']:>5}{r['erro']:>5}"
              f"{r['taxa_acerto']:>8.0%}{r['fatos']:>7}{r['exclusivos']:>7}{r['ms_medio']:>7}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
