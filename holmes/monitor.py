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
    return _load(WATCH_FILE, [])


def add_target(alvo: str) -> bool:
    """Adiciona um alvo à vigilância. Devolve False se já existia ou vazio."""
    alvo = (alvo or "").strip()
    if not alvo:
        return False
    lista = watchlist()
    if any(t.get("alvo", "").lower() == alvo.lower() for t in lista):
        return False
    lista.append({"alvo": alvo, "adicionado_em": int(time.time()), "ultimo_id": None})
    _save(WATCH_FILE, lista)
    return True


def remove_target(alvo: str) -> None:
    lista = [t for t in watchlist() if t.get("alvo", "").lower() != (alvo or "").lower()]
    _save(WATCH_FILE, lista)


# ── alertas ──────────────────────────────────────────────────────────────────

def alerts(limit: int = 100) -> list[dict]:
    return _load(ALERTS_FILE, [])[:limit]


def _push_alert(alerta: dict) -> None:
    lista = _load(ALERTS_FILE, [])
    lista.insert(0, alerta)
    _save(ALERTS_FILE, lista[:MAX_ALERTS])


def marcar_lidos() -> None:
    lista = _load(ALERTS_FILE, [])
    for a in lista:
        a["lido"] = True
    _save(ALERTS_FILE, lista)


def unread_count() -> int:
    return sum(1 for a in _load(ALERTS_FILE, []) if not a.get("lido"))


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
