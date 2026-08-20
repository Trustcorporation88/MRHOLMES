"""Armazenamento Supabase com reserva em arquivo. Sem rede — HTTP é mockado."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import history, monitor, store  # noqa: E402
from holmes.dossier import Dossier  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import ConnectorResult, Finding, FindingKind  # noqa: E402


def test_desabilitado_sem_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    assert store.enabled() is False


def test_habilitado_com_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "chave")
    assert store.enabled() is True


def test_select_none_quando_desabilitado(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert store.select("holmes_dossies") is None
    assert store.insert("holmes_dossies", {"a": 1}) is False


def _dossie(alvo="Fulano de Tal"):
    d = Dossier(entity=detect(alvo))
    d.add_results([ConnectorResult("t", "T", True, [Finding(FindingKind.EMAIL, "x@y.com", "t")])])
    d.consolidate()
    return d


def test_history_usa_supabase_quando_ligado(monkeypatch):
    # Simula Supabase ligado; captura o insert e devolve pela list.
    gravados: list[dict] = []
    monkeypatch.setattr(store, "enabled", lambda: True)
    monkeypatch.setattr(store, "insert", lambda tabela, row: gravados.append(row) or True)

    def fake_select(tabela, params=None):
        return [{"id": r["id"], "alvo": r["alvo"], "tipo_label": r.get("tipo_label"),
                 "quando": r["quando"], "stats": r["stats"], "resumo": r["resumo"]}
                for r in gravados]

    monkeypatch.setattr(store, "select", fake_select)
    # Isola o arquivo para não interferir.
    monkeypatch.setattr(history, "HISTORY_DIR", pathlib.Path(tempfile.mkdtemp()))

    rid = history.save(_dossie("Alvo Supabase"))
    assert rid
    assert gravados and gravados[0]["alvo"] == "Alvo Supabase"
    entradas = history.list_entries()
    assert any(e["alvo"] == "Alvo Supabase" for e in entradas)


def test_monitor_watchlist_via_supabase(monkeypatch):
    estado: list[dict] = []
    monkeypatch.setattr(store, "enabled", lambda: True)
    monkeypatch.setattr(store, "select",
                        lambda t, params=None: list(estado) if "watchlist" in t else [])
    monkeypatch.setattr(store, "upsert",
                        lambda t, row, on_conflict: estado.append(row) or True)
    monkeypatch.setattr(store, "delete",
                        lambda t, params: estado.clear() or True)

    assert monitor.add_target("Alvo Vigiado")
    assert any(t["alvo"] == "Alvo Vigiado" for t in monitor.watchlist())
    # duplicado não entra
    assert not monitor.add_target("Alvo Vigiado")
    monitor.remove_target("Alvo Vigiado")
    assert monitor.watchlist() == []


def test_schema_sql_tem_as_tres_tabelas():
    for tabela in ("holmes_dossies", "holmes_watchlist", "holmes_alertas"):
        assert tabela in store.SCHEMA_SQL
