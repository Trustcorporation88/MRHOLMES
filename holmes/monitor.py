"""
Monitoramento de alvos.

Uma lista de alvos vigiados. Rodar `run_once()` reinvestiga cada um, compara
com a última vez (via holmes.history) e registra um ALERTA quando aparece algo
novo — perfil, telefone, vazamento, processo.

O agendamento em si é externo: no Railway, um serviço Cron que executa
`python -m holmes.monitor` de tempos em tempos. Assim o site avisa você mesmo
sem ninguém estar com a página aberta.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import history

WATCH_DIR = Path(os.environ.get("HOLMES_WATCH_DIR", os.environ.get("HOLMES_HISTORY_DIR", ".holmes_history")))
WATCH_FILE = WATCH_DIR / "_watchlist.json"
ALERTS_FILE = WATCH_DIR / "_alerts.json"
MAX_ALERTS = 200


# ── watchlist ────────────────────────────────────────────────────────────────

def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(path: Path, data) -> None:
    try:
        WATCH_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def watchlist() -> list[dict]:
    from . import store

    if store.enabled():
        linhas = store.select("holmes_watchlist", {"select": "*", "order": "adicionado_em.desc"})
        if linhas is not None:
            return linhas
    return _load(WATCH_FILE, [])


def add_target(alvo: str) -> bool:
    """Adiciona um alvo à vigilância. Devolve False se já existia ou vazio."""
    from . import store

    alvo = (alvo or "").strip()
    if not alvo:
        return False
    if any(t.get("alvo", "").lower() == alvo.lower() for t in watchlist()):
        return False
    novo = {"alvo": alvo, "adicionado_em": int(time.time()), "ultimo_id": None}
    if store.enabled():
        store.upsert("holmes_watchlist", novo, on_conflict="alvo")
    else:
        lista = _load(WATCH_FILE, [])
        lista.append(novo)
        _save(WATCH_FILE, lista)
    return True


def remove_target(alvo: str) -> None:
    from . import store

    if store.enabled():
        store.delete("holmes_watchlist", {"alvo": f"eq.{alvo}"})
        return
    lista = [t for t in _load(WATCH_FILE, []) if t.get("alvo", "").lower() != (alvo or "").lower()]
    _save(WATCH_FILE, lista)


def _update_target(alvo_cfg: dict) -> None:
    """Persiste ultimo_id/ultima_verificacao de um alvo após reinvestigar."""
    from . import store

    if store.enabled():
        store.upsert("holmes_watchlist", alvo_cfg, on_conflict="alvo")


# ── alertas ──────────────────────────────────────────────────────────────────

def alerts(limit: int = 100) -> list[dict]:
    from . import store

    if store.enabled():
        linhas = store.select("holmes_alertas", {"select": "*", "order": "quando.desc",
                                                 "limit": str(limit)})
        if linhas is not None:
            return linhas
    return _load(ALERTS_FILE, [])[:limit]


def _push_alert(alerta: dict) -> None:
    from . import store

    if store.enabled():
        store.insert("holmes_alertas", alerta)
        return
    lista = _load(ALERTS_FILE, [])
    lista.insert(0, alerta)
    _save(ALERTS_FILE, lista[:MAX_ALERTS])


def marcar_lidos() -> None:
    from . import store

    if store.enabled():
        # PATCH lido=true em todos os não lidos.
        cfg = store._cfg()
        endpoint = store._rest("holmes_alertas")
        if cfg and endpoint:
            _, key = cfg
            try:
                net_mod = __import__("holmes.net", fromlist=["_SESSION"])
                net_mod._SESSION.patch(
                    f"{endpoint}?lido=eq.false", json={"lido": True},
                    headers=store._headers(key, {"Prefer": "return=minimal"}), timeout=15,
                ).raise_for_status()
            except Exception:
                pass
        return
    lista = _load(ALERTS_FILE, [])
    for a in lista:
        a["lido"] = True
    _save(ALERTS_FILE, lista)


def unread_count() -> int:
    return sum(1 for a in alerts(200) if not a.get("lido"))


# ── execução ─────────────────────────────────────────────────────────────────

def run_once(investigate_fn=None, config=None) -> list[dict]:
    """
    Reinvestiga cada alvo da watchlist, compara com a última vez e gera alerta
    de novidade. Devolve a lista de alertas criados nesta rodada.

    investigate_fn é injetável para teste; em produção usa holmes.investigate.
    """
    if investigate_fn is None:
        from .orchestrator import InvestigationConfig, investigate

        investigate_fn = investigate
        config = config or InvestigationConfig(use_llm=False, include_deeplinks=False,
                                               include_manual=False)

    novos: list[dict] = []
    lista = watchlist()
    for alvo_cfg in lista:
        alvo = alvo_cfg.get("alvo")
        if not alvo:
            continue
        anterior_id = alvo_cfg.get("ultimo_id")
        try:
            dossier = investigate_fn(alvo, config) if config else investigate_fn(alvo)
        except Exception as exc:  # noqa: BLE001
            _push_alert({"alvo": alvo, "quando": int(time.time()),
                         "tipo": "erro", "texto": f"Falha ao reinvestigar: {exc}", "lido": False})
            continue

        novo_id = history.save(dossier)
        alvo_cfg["ultimo_id"] = novo_id
        alvo_cfg["ultima_verificacao"] = int(time.time())
        _update_target(alvo_cfg)

        if anterior_id and novo_id:
            d = history.diff(anterior_id, novo_id)
            if d and d.get("tem_novidade"):
                resumo = _resumir_diff(d)
                alerta = {"alvo": alvo, "quando": int(time.time()), "tipo": "novidade",
                          "texto": resumo, "detalhe": d["mudancas"], "lido": False}
                _push_alert(alerta)
                novos.append(alerta)

    _save(WATCH_FILE, lista)
    return novos


def _resumir_diff(d: dict) -> str:
    partes = []
    for secao, m in d.get("mudancas", {}).items():
        if m.get("novos"):
            partes.append(f"{len(m['novos'])} em {secao}")
    return "Novidade: " + ", ".join(partes) if partes else "Mudança detectada"


def main() -> int:
    """Entrada de linha de comando — para o Railway Cron chamar."""
    resultados = run_once()
    print(f"[holmes.monitor] {len(watchlist())} alvo(s) verificado(s), "
          f"{len(resultados)} alerta(s) de novidade.")
    for a in resultados:
        print(f"  ! {a['alvo']}: {a['texto']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
