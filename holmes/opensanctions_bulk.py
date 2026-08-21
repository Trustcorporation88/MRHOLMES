"""
Índice local e gratuito de sanções/PEP internacionais — sem chave, sem custo.

A API paga do OpenSanctions (holmes.sanctions) cobra por consulta depois do
teste de 30 dias. Mas os dados em massa (o mesmo conteúdo, atualizado todo dia)
são de graça para uso não-comercial — só é preciso baixar e indexar localmente.

Este módulo baixa o arquivo `targets.simple.csv` (só as entidades sinalizadas:
sanção, PEP ou contexto criminal — a base inteira, sem sinalização, não vem
aqui) e monta um índice SQLite por nome, para consulta instantânea sem rede.

Uso:
    python -m holmes.opensanctions_bulk --update

No Railway, agende isto num Cron semanal (o arquivo de origem muda todo dia,
mas para OSINT pessoal atualizar 1x por semana já é sobra). O banco fica no
Volume persistente (mesma ideia do histórico) — sem Volume, ele é reconstruído
a cada deploy.

Licença: dados do OpenSanctions são gratuitos para uso NÃO-COMERCIAL
(CC BY-NC 4.0). Uso comercial exige licença paga deles — não é o caso do
Mr.Holmes pessoal, mas fica registrado aqui para quem reaproveitar o código.
"""

from __future__ import annotations

import csv
import io
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Iterable

from .entity import strip_accents

FONTE_URL = "https://data.opensanctions.org/datasets/latest/default/targets.simple.csv"

DATA_DIR = Path(os.environ.get("HOLMES_OPENSANCTIONS_DIR", os.environ.get("HOLMES_DATA_DIR", ".holmes_data")))
DB_PATH = DATA_DIR / "opensanctions.sqlite"

# Nome de dataset costuma trazer "_pep" ou "peps" quando é lista de PEP
# (ex.: "ru_pep", "am_pep", "peps_national"). Sem campo dedicado no CSV,
# isto é o melhor sinal disponível — sempre mostrando o dataset de origem
# para o investigador poder conferir.
_PEP_DATASET_RE = re.compile(r"pep", re.IGNORECASE)


# ── normalização e casamento de nome (mesmo espírito do anti-homônimo do br_auto) ──

def _normalizar(nome: str) -> str:
    limpo = strip_accents(nome or "").lower()
    limpo = re.sub(r"[^a-z0-9\s]", " ", limpo)
    return re.sub(r"\s+", " ", limpo).strip()


def _tokens(nome_normalizado: str) -> list[str]:
    return [t for t in nome_normalizado.split(" ") if len(t) > 1]


def _mesma_pessoa(alvo_tok: list[str], candidato_norm: str) -> str | None:
    """None se não bate; senão devolve o nível: 'exato' ou 'parcial'."""
    if not candidato_norm:
        return None
    if " ".join(alvo_tok) == candidato_norm:
        return "exato"
    cand_tok = _tokens(candidato_norm)
    if len(cand_tok) >= 2 and len(alvo_tok) >= 2:
        if cand_tok[0] == alvo_tok[0] and cand_tok[-1] == alvo_tok[-1]:
            return "parcial"
    return None


# ── status ──────────────────────────────────────────────────────────────────

def disponivel() -> bool:
    return DB_PATH.exists() and DB_PATH.stat().st_size > 0


def status() -> dict:
    if not disponivel():
        return {"baixado": False, "caminho": str(DB_PATH)}
    con = sqlite3.connect(str(DB_PATH))
    try:
        cur = con.cursor()
        cur.execute("SELECT chave, valor FROM meta")
        meta = dict(cur.fetchall())
    except Exception:
        meta = {}
    finally:
        con.close()
    tamanho_mb = DB_PATH.stat().st_size / (1024 * 1024)
    return {
        "baixado": True,
        "caminho": str(DB_PATH),
        "tamanho_mb": round(tamanho_mb, 1),
        "total_entidades": int(meta.get("total_entidades", 0) or 0),
        "atualizado_em": meta.get("atualizado_em", ""),
    }


# ── construção do índice ─────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entidades (
    id TEXT PRIMARY KEY,
    nome TEXT,
    tipo TEXT,
    nascimento TEXT,
    paises TEXT,
    enderecos TEXT,
    identificadores TEXT,
    sancoes TEXT,
    telefones TEXT,
    emails TEXT,
    program_ids TEXT,
    datasets TEXT
);
CREATE TABLE IF NOT EXISTS nomes (
    nome_normalizado TEXT,
    entity_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_nomes_norm ON nomes(nome_normalizado);
CREATE INDEX IF NOT EXISTS idx_nomes_entity ON nomes(entity_id);
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);
"""


def build_from_rows(linhas: Iterable[dict], db_path: Path | None = None) -> int:
    """
    Monta o SQLite a partir de linhas já parseadas (dict por linha do CSV).
    Separado do download para ser testável sem rede.
    """
    caminho = db_path or DB_PATH
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".building")
    if tmp.exists():
        tmp.unlink()

    con = sqlite3.connect(str(tmp))
    con.executescript(_SCHEMA_SQL)
    con.execute("PRAGMA synchronous = OFF")
    con.execute("PRAGMA journal_mode = MEMORY")

    total = 0
    lote_ent: list[tuple] = []
    lote_nome: list[tuple] = []

    def _flush():
        if lote_ent:
            con.executemany(
                "INSERT OR REPLACE INTO entidades VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                lote_ent,
            )
            lote_ent.clear()
        if lote_nome:
            con.executemany("INSERT INTO nomes VALUES (?,?)", lote_nome)
            lote_nome.clear()

    for linha in linhas:
        eid = (linha.get("id") or "").strip()
        nome = (linha.get("name") or "").strip()
        if not eid or not nome:
            continue
        lote_ent.append((
            eid, nome, linha.get("schema") or "", linha.get("birth_date") or "",
            linha.get("countries") or "", linha.get("addresses") or "",
            linha.get("identifiers") or "", linha.get("sanctions") or "",
            linha.get("phones") or "", linha.get("emails") or "",
            linha.get("program_ids") or "", linha.get("dataset") or "",
        ))
        vistos_norm = set()
        for candidato in [nome] + (linha.get("aliases") or "").split(";"):
            candidato = candidato.strip()
            if not candidato:
                continue
            norm = _normalizar(candidato)
            if norm and norm not in vistos_norm:
                vistos_norm.add(norm)
                lote_nome.append((norm, eid))
        total += 1
        if len(lote_ent) >= 5000:
            _flush()

    _flush()
    con.execute("DELETE FROM meta")
    con.execute(
        "INSERT INTO meta VALUES ('total_entidades', ?), ('atualizado_em', ?), ('fonte_url', ?)",
        (str(total), time.strftime("%Y-%m-%dT%H:%M:%S"), FONTE_URL),
    )
    con.commit()
    con.close()

    tmp.replace(caminho)
    return total


def _linhas_do_csv(caminho_csv: Path) -> Iterable[dict]:
    with open(caminho_csv, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def build_from_csv_file(caminho_csv: Path, db_path: Path | None = None) -> int:
    """Constrói o índice a partir de um CSV já em disco (usado por update() e por testes)."""
    return build_from_rows(_linhas_do_csv(caminho_csv), db_path)


def update(progress=None) -> dict:
    """
    Baixa o CSV oficial (~400 MB) em streaming e reconstrói o índice local.
    `progress(fração_0_a_1)` é chamado durante o download, se fornecido.
    Não carrega o arquivo inteiro em memória em nenhum momento.
    """
    from . import net

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_csv = DATA_DIR / "_targets.simple.csv.tmp"

    sessao = net.build_session(retries=2)
    with sessao.get(FONTE_URL, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        total_bytes = int(resp.headers.get("content-length", 0) or 0)
        feito = 0
        with open(tmp_csv, "wb") as f:
            for pedaco in resp.iter_content(chunk_size=1024 * 1024):
                if not pedaco:
                    continue
                f.write(pedaco)
                feito += len(pedaco)
                if progress and total_bytes:
                    progress(min(1.0, feito / total_bytes))

    total = build_from_csv_file(tmp_csv)
    tmp_csv.unlink(missing_ok=True)
    return {"total_entidades": total, "caminho": str(DB_PATH)}


# ── busca ────────────────────────────────────────────────────────────────────

def search(nome: str, limit: int = 5) -> list[dict]:
    """
    Busca com o mesmo cuidado anti-homônimo do resto do motor: só entra
    quem bate nome completo OU primeiro+último token com algum nome/apelido
    conhecido da entidade.
    """
    if not disponivel():
        return []
    alvo_norm = _normalizar(nome)
    alvo_tok = _tokens(alvo_norm)
    if len(alvo_tok) < 2:
        return []

    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT DISTINCT entity_id FROM nomes WHERE nome_normalizado = ?",
            (alvo_norm,),
        )
        candidatos = [r["entity_id"] for r in cur.fetchall()]

        if len(candidatos) < limit * 3:
            padrao = f"%{alvo_tok[-1]}%"
            cur.execute(
                "SELECT DISTINCT entity_id FROM nomes WHERE nome_normalizado LIKE ? LIMIT 1000",
                (padrao,),
            )
            for r in cur.fetchall():
                if r["entity_id"] not in candidatos:
                    candidatos.append(r["entity_id"])

        resultados: list[dict] = []
        for eid in candidatos:
            cur.execute("SELECT nome_normalizado FROM nomes WHERE entity_id = ?", (eid,))
            niveis = [_mesma_pessoa(alvo_tok, r["nome_normalizado"]) for r in cur.fetchall()]
            if "exato" in niveis:
                nivel = "exato"
            elif "parcial" in niveis:
                nivel = "parcial"
            else:
                continue

            cur.execute("SELECT * FROM entidades WHERE id = ?", (eid,))
            row = cur.fetchone()
            if not row:
                continue
            item = dict(row)
            item["nivel_match"] = nivel
            item["eh_sancao"] = bool((item.get("sancoes") or "").strip())
            item["eh_pep"] = bool(_PEP_DATASET_RE.search(item.get("datasets") or ""))
            resultados.append(item)
            if len(resultados) >= limit:
                break
        return resultados
    finally:
        con.close()


# ── linha de comando (Railway Cron) ──────────────────────────────────────────

def main() -> int:
    def _progresso(frac: float) -> None:
        if int(frac * 100) % 10 == 0:
            print(f"[holmes.opensanctions_bulk] baixando… {frac:.0%}")

    print(f"[holmes.opensanctions_bulk] atualizando de {FONTE_URL} …")
    info = update(progress=_progresso)
    print(f"[holmes.opensanctions_bulk] pronto: {info['total_entidades']} entidades em {info['caminho']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
