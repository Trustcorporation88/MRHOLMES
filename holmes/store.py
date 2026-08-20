"""
Armazenamento — Supabase (Postgres) com reserva em arquivo.

Se `SUPABASE_URL` e `SUPABASE_KEY` estiverem configurados, os dados (histórico,
watchlist, alertas) vão para o Postgres do Supabase via REST (PostgREST) — não
somem em deploy. Sem essas variáveis, cai automaticamente no armazenamento em
arquivo local. Nenhuma dependência nova: usa a camada HTTP do próprio motor.

O código chama sempre o Supabase primeiro; se ele falhar por qualquer motivo,
o arquivo garante que nada quebra.
"""

from __future__ import annotations

import os
from typing import Any


def _cfg() -> tuple[str, str] | None:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_KEY")
           or os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    if url and key:
        return url, key
    return None


def enabled() -> bool:
    return _cfg() is not None


def _headers(key: str, extra: dict | None = None) -> dict:
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _rest(table: str) -> str | None:
    cfg = _cfg()
    if not cfg:
        return None
    url, _ = cfg
    return f"{url}/rest/v1/{table}"


def insert(table: str, row: dict) -> bool:
    """Insere uma linha. Devolve True se gravou no Supabase."""
    cfg = _cfg()
    endpoint = _rest(table)
    if not cfg or not endpoint:
        return False
    _, key = cfg
    try:
        from . import net

        net._SESSION.post(
            endpoint, json=row,
            headers=_headers(key, {"Prefer": "return=minimal"}),
            timeout=15,
        ).raise_for_status()
        return True
    except Exception:
        return False


def upsert(table: str, row: dict, on_conflict: str) -> bool:
    cfg = _cfg()
    endpoint = _rest(table)
    if not cfg or not endpoint:
        return False
    _, key = cfg
    try:
        from . import net

        net._SESSION.post(
            f"{endpoint}?on_conflict={on_conflict}", json=row,
            headers=_headers(key, {"Prefer": "resolution=merge-duplicates,return=minimal"}),
            timeout=15,
        ).raise_for_status()
        return True
    except Exception:
        return False


def select(table: str, params: dict | None = None) -> list[dict] | None:
    """SELECT via PostgREST. None = Supabase indisponível (caia no arquivo)."""
    cfg = _cfg()
    endpoint = _rest(table)
    if not cfg or not endpoint:
        return None
    _, key = cfg
    try:
        from . import net

        resp = net._SESSION.get(endpoint, params=params or {}, headers=_headers(key), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception:
        return None


def delete(table: str, params: dict) -> bool:
    cfg = _cfg()
    endpoint = _rest(table)
    if not cfg or not endpoint:
        return False
    _, key = cfg
    try:
        from . import net

        net._SESSION.delete(endpoint, params=params, headers=_headers(key), timeout=15).raise_for_status()
        return True
    except Exception:
        return False


# SQL das tabelas — usado no setup do Supabase (documentado e aplicado via MCP).
SCHEMA_SQL = """
create table if not exists holmes_dossies (
    id text primary key,
    alvo text not null,
    tipo text,
    tipo_label text,
    quando timestamptz default now(),
    stats jsonb,
    resumo text,
    dossie jsonb
);
create index if not exists holmes_dossies_alvo_idx on holmes_dossies (lower(alvo));
create index if not exists holmes_dossies_quando_idx on holmes_dossies (quando desc);

create table if not exists holmes_watchlist (
    alvo text primary key,
    adicionado_em bigint,
    ultimo_id text,
    ultima_verificacao bigint
);

create table if not exists holmes_alertas (
    id bigint generated always as identity primary key,
    alvo text not null,
    quando bigint,
    tipo text,
    texto text,
    detalhe jsonb,
    lido boolean default false
);
create index if not exists holmes_alertas_quando_idx on holmes_alertas (quando desc);
"""
