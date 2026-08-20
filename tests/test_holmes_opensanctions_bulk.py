"""Índice local gratuito de sanções/PEP (SQLite a partir do CSV oficial). Sem rede."""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import opensanctions_bulk as bulk  # noqa: E402

_CAMPOS = [
    "id", "schema", "name", "aliases", "birth_date", "countries", "addresses",
    "identifiers", "sanctions", "phones", "emails", "program_ids", "dataset",
]

_LINHAS = [
    {"id": "Q1", "schema": "Person", "name": "Vladimir Putin",
     "aliases": "Vladimir Vladimirovich Putin", "birth_date": "1952-10-07",
     "countries": "ru", "addresses": "", "identifiers": "",
     "sanctions": "EU sanctions 2022", "phones": "", "emails": "",
     "program_ids": "EU-RU-1", "dataset": "eu_fsf;ru_pep"},
    {"id": "Q2", "schema": "Person", "name": "Joao Silva Pereira",
     "aliases": "J. Silva Pereira", "birth_date": "", "countries": "br",
     "addresses": "", "identifiers": "", "sanctions": "", "phones": "",
     "emails": "", "program_ids": "", "dataset": "br_pep_source"},
]


def _csv_temp(dir_: Path) -> Path:
    caminho = dir_ / "targets.simple.csv"
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_CAMPOS)
        w.writeheader()
        w.writerows(_LINHAS)
    return caminho


def _db_temp(monkeypatch) -> Path:
    d = Path(tempfile.mkdtemp())
    db = d / "os.sqlite"
    monkeypatch.setattr(bulk, "DB_PATH", db)
    return db


def test_nao_disponivel_antes_de_construir(monkeypatch):
    _db_temp(monkeypatch)
    assert bulk.disponivel() is False
    assert bulk.search("Vladimir Putin") == []
    assert bulk.status()["baixado"] is False


def test_build_from_csv_e_status(monkeypatch):
    db = _db_temp(monkeypatch)
    tmp = Path(tempfile.mkdtemp())
    csv_path = _csv_temp(tmp)

    total = bulk.build_from_csv_file(csv_path, db)
    assert total == 2
    assert bulk.disponivel() is True

    s = bulk.status()
    assert s["baixado"] is True
    assert s["total_entidades"] == 2
    assert s["atualizado_em"]


def test_busca_exata_marca_sancao_e_pep(monkeypatch):
    db = _db_temp(monkeypatch)
    tmp = Path(tempfile.mkdtemp())
    bulk.build_from_csv_file(_csv_temp(tmp), db)

    r = bulk.search("Vladimir Putin")
    assert len(r) == 1
    item = r[0]
    assert item["nivel_match"] == "exato"
    assert item["eh_sancao"] is True
    assert item["eh_pep"] is True


def test_busca_por_alias(monkeypatch):
    db = _db_temp(monkeypatch)
    tmp = Path(tempfile.mkdtemp())
    bulk.build_from_csv_file(_csv_temp(tmp), db)

    r = bulk.search("Vladimir Vladimirovich Putin")
    assert r and r[0]["id"] == "Q1"


def test_busca_parcial_por_primeiro_e_ultimo_token(monkeypatch):
    db = _db_temp(monkeypatch)
    tmp = Path(tempfile.mkdtemp())
    bulk.build_from_csv_file(_csv_temp(tmp), db)

    r = bulk.search("Joao Pereira")
    assert r and r[0]["nivel_match"] == "parcial"
    assert r[0]["eh_sancao"] is False
    assert r[0]["eh_pep"] is True  # dataset "br_pep_source" contém "pep"


def test_busca_homonimo_sem_sobrenome_batendo_fica_vazia(monkeypatch):
    db = _db_temp(monkeypatch)
    tmp = Path(tempfile.mkdtemp())
    bulk.build_from_csv_file(_csv_temp(tmp), db)

    # "Joao Nascimento" bate o primeiro token mas não o último — não é a
    # mesma pessoa que "Joao Silva Pereira".
    assert bulk.search("Joao Nascimento") == []


def test_busca_alvo_desconhecido_vazia(monkeypatch):
    db = _db_temp(monkeypatch)
    tmp = Path(tempfile.mkdtemp())
    bulk.build_from_csv_file(_csv_temp(tmp), db)
    assert bulk.search("Fulano de Tal Nunca Existiu") == []


def test_busca_nome_de_uma_palavra_e_ignorada(monkeypatch):
    db = _db_temp(monkeypatch)
    tmp = Path(tempfile.mkdtemp())
    bulk.build_from_csv_file(_csv_temp(tmp), db)
    assert bulk.search("Putin") == []
