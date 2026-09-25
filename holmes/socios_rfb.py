"""
Índice local do quadro societário de TODAS as empresas do Brasil.

A consulta de CNPJ entrega os sócios de uma empresa. A pergunta seguinte de
qualquer investigação é a inversa: em que outras empresas essa pessoa é
sócia? Nenhuma API gratuita responde isso. Mas a Receita publica todo mês os
dados abertos do CNPJ, e o arquivo de sócios tem nome, CPF mascarado
(***456789**), qualificação e data de entrada de cada sócio de cada empresa.

Este módulo baixa só os arquivos de sócios (Socios0.zip a Socios9.zip, cerca
de 26 milhões de linhas) e monta um SQLite indexado por nome, por CPF
mascarado e por CNPJ básico. Com ele o motor responde, sem rede:

* nome → empresas em que alguém com esse nome é sócio;
* CPF  → empresas em que o CPF (mascarado) aparece como sócio;
* CNPJ → outras empresas dos sócios desta (as «coligadas por sócio»).

Uso:
    python -m holmes.socios_rfb --update            # descobre o mês mais recente
    python -m holmes.socios_rfb --from-dir ./rfb    # usa zips/CSVs já baixados

O banco final tem de 3 a 4 GB. No Railway, aponte HOLMES_SOCIOS_DIR para o
Volume persistente e agende a atualização mensal num Cron.

Endereço da Receita (muda de tempos em tempos, por isso é configurável):
    HOLMES_RFB_CNPJ_BASE  padrão: https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/
    HOLMES_RFB_CNPJ_MES   opcional, ex.: 2026-09 (sem isso, pega o mais recente)
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sqlite3
import sys
import time
import zipfile
from pathlib import Path
from typing import Iterable, Iterator

from .entity import only_digits, strip_accents

BASE_URL = os.environ.get(
    "HOLMES_RFB_CNPJ_BASE",
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/",
).rstrip("/") + "/"
DATA_DIR = Path(os.environ.get("HOLMES_SOCIOS_DIR", os.environ.get("HOLMES_DATA_DIR", ".holmes_data")))
DB_PATH = DATA_DIR / "socios_rfb.sqlite"
ARQUIVOS = [f"Socios{i}.zip" for i in range(10)]

# Tabela oficial de qualificação de sócio (as que aparecem no arquivo).
QUALIFICACAO = {
    "05": "Administrador", "08": "Conselheiro de Administração", "10": "Diretor",
    "16": "Presidente", "17": "Procurador", "22": "Sócio", "28": "Sócio-Gerente",
    "29": "Sócio Incapaz", "30": "Sócio Menor", "31": "Sócio Ostensivo",
    "37": "Sócio PJ domiciliado no exterior", "38": "Sócio PF residente no exterior",
    "47": "Sócio PF residente no Brasil", "48": "Sócio PJ domiciliado no Brasil",
    "49": "Sócio-Administrador", "50": "Empresário", "54": "Fundador",
    "55": "Sócio Comanditado", "56": "Sócio Comanditário", "57": "Sócio de Indústria",
    "63": "Cotas em Tesouraria", "65": "Titular PF residente no Brasil",
    "66": "Titular PF residente no exterior", "67": "Titular PF incapaz",
    "70": "Administrador residente no exterior", "72": "Diretor residente no exterior",
    "73": "Presidente residente no exterior", "74": "Sócio-Administrador residente no exterior",
    "78": "Titular PJ domiciliada no Brasil", "79": "Titular PJ domiciliada no exterior",
}
FAIXA_ETARIA = {
    "1": "0 a 12 anos", "2": "13 a 20 anos", "3": "21 a 30 anos", "4": "31 a 40 anos",
    "5": "41 a 50 anos", "6": "51 a 60 anos", "7": "61 a 70 anos", "8": "71 a 80 anos",
    "9": "mais de 80 anos",
}


def normalizar(nome: str) -> str:
    limpo = strip_accents(nome or "").upper()
    limpo = re.sub(r"[^A-Z0-9 ]", " ", limpo)
    return re.sub(r"\s+", " ", limpo).strip()


def cpf_mascarado(cpf: str) -> str:
    """Formato do arquivo da Receita: ***456789** (miolo do CPF)."""
    d = only_digits(cpf)
    return f"***{d[3:9]}**" if len(d) == 11 else ""


def cnpj_matriz(basico: str) -> str:
    """CNPJ completo da matriz a partir dos 8 dígitos básicos."""
    base = only_digits(basico).zfill(8) + "0001"
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        soma = sum(int(n) * p for n, p in zip(base, pesos))
        resto = soma % 11
        base += "0" if resto < 2 else str(11 - resto)
    return f"{base[:2]}.{base[2:5]}.{base[5:8]}/{base[8:12]}-{base[12:]}"


# ── status ──────────────────────────────────────────────────────────────────

def disponivel() -> bool:
    return DB_PATH.exists() and DB_PATH.stat().st_size > 0


def status() -> dict:
    if not disponivel():
        return {"baixado": False, "caminho": str(DB_PATH)}
    con = sqlite3.connect(str(DB_PATH))
    try:
        meta = dict(con.execute("SELECT chave, valor FROM meta").fetchall())
    except Exception:
        meta = {}
    finally:
        con.close()
    return {
        "baixado": True,
        "caminho": str(DB_PATH),
        "tamanho_mb": round(DB_PATH.stat().st_size / (1024 * 1024), 1),
        "total_socios": int(meta.get("total_socios", 0) or 0),
        "mes_referencia": meta.get("mes_referencia", ""),
        "atualizado_em": meta.get("atualizado_em", ""),
    }


# ── construção ──────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE socios (
    cnpj_basico TEXT,
    tipo TEXT,            -- 1 PJ, 2 PF, 3 estrangeiro
    nome TEXT,
    nome_norm TEXT,
    doc TEXT,             -- CPF mascarado (***456789**) ou CNPJ do sócio PJ
    qualificacao TEXT,
    entrada TEXT,
    faixa TEXT
);
CREATE TABLE meta (chave TEXT PRIMARY KEY, valor TEXT);
"""
_INDICES = """
CREATE INDEX idx_socios_nome ON socios(nome_norm);
CREATE INDEX idx_socios_doc ON socios(doc);
CREATE INDEX idx_socios_basico ON socios(cnpj_basico);
"""


def _linhas_csv(fluxo: io.TextIOBase) -> Iterator[tuple]:
    """Arquivo da Receita: sem cabeçalho, `;`, aspas, latin-1."""
    for row in csv.reader(fluxo, delimiter=";", quotechar='"'):
        if len(row) < 11:
            continue
        basico, tipo, nome, doc, qualif, entrada, _pais, _rep, _nome_rep, _qual_rep, faixa = row[:11]
        nome = nome.strip()
        if not nome:
            continue
        yield (basico.strip(), tipo.strip(), nome, normalizar(nome), doc.strip(),
               qualif.strip().zfill(2), entrada.strip(), faixa.strip())


def _linhas_de_arquivo(caminho: Path) -> Iterator[tuple]:
    if caminho.suffix.lower() == ".zip":
        with zipfile.ZipFile(caminho) as z:
            for membro in z.namelist():
                with z.open(membro) as bruto:
                    yield from _linhas_csv(io.TextIOWrapper(bruto, encoding="latin-1", newline=""))
    else:
        with open(caminho, encoding="latin-1", newline="") as f:
            yield from _linhas_csv(f)


def build_from_rows(linhas: Iterable[tuple], db_path: Path | None = None, mes: str = "") -> int:
    """Monta o banco num arquivo temporário e troca no fim: consulta nunca vê meio índice."""
    destino = db_path or DB_PATH
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(str(tmp))
    try:
        con.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + _SCHEMA)
        total, lote = 0, []
        for linha in linhas:
            lote.append(linha)
            if len(lote) >= 50_000:
                con.executemany("INSERT INTO socios VALUES (?,?,?,?,?,?,?,?)", lote)
                total += len(lote)
                lote.clear()
        if lote:
            con.executemany("INSERT INTO socios VALUES (?,?,?,?,?,?,?,?)", lote)
            total += len(lote)
        con.executescript(_INDICES)
        con.executemany("INSERT INTO meta VALUES (?, ?)", [
            ("total_socios", str(total)),
            ("mes_referencia", mes),
            ("atualizado_em", time.strftime("%Y-%m-%d %H:%M")),
        ])
        con.commit()
    finally:
        con.close()
    os.replace(tmp, destino)
    return total


def build_from_dir(pasta: Path, db_path: Path | None = None) -> int:
    arquivos = sorted(
        p for p in Path(pasta).iterdir()
        if "socio" in p.name.lower() and p.suffix.lower() in (".zip", ".csv", ".socicsv", "")
        and p.is_file()
    )
    if not arquivos:
        raise FileNotFoundError(f"nenhum arquivo de sócios (Socios*.zip) em {pasta}")

    def _todas():
        for arq in arquivos:
            yield from _linhas_de_arquivo(arq)

    return build_from_rows(_todas(), db_path, mes=Path(pasta).name)


def mes_mais_recente() -> str:
    fixo = os.environ.get("HOLMES_RFB_CNPJ_MES", "").strip()
    if fixo:
        return fixo
    from . import net

    html = net.get_text(BASE_URL, ttl=3600) or ""
    meses = sorted(set(re.findall(r'href="(\d{4}-\d{2})/?"', html)))
    if not meses:
        raise RuntimeError(
            f"não achei pastas de mês em {BASE_URL}. A Receita pode ter mudado o endereço: "
            "ajuste HOLMES_RFB_CNPJ_BASE ou baixe os Socios*.zip e use --from-dir."
        )
    return meses[-1]


def update(progress=None) -> dict:
    """Baixa os 10 zips de sócios do mês mais recente e reconstrói o índice."""
    from . import net

    mes = mes_mais_recente()
    pasta = DATA_DIR / f"_rfb_{mes}"
    pasta.mkdir(parents=True, exist_ok=True)
    sessao = net.build_session(retries=3)
    for i, nome in enumerate(ARQUIVOS):
        destino = pasta / nome
        if destino.exists() and destino.stat().st_size > 0:
            continue
        with sessao.get(f"{BASE_URL}{mes}/{nome}", stream=True, timeout=180) as resp:
            resp.raise_for_status()
            parcial = destino.with_suffix(".part")
            with open(parcial, "wb") as f:
                for pedaco in resp.iter_content(chunk_size=4 * 1024 * 1024):
                    f.write(pedaco)
            os.replace(parcial, destino)
        if progress:
            progress((i + 1) / len(ARQUIVOS) * 0.7)

    total = build_from_rows(
        (linha for arq in sorted(pasta.glob("Socios*.zip")) for linha in _linhas_de_arquivo(arq)),
        mes=mes,
    )
    for arq in pasta.glob("*"):
        arq.unlink(missing_ok=True)
    pasta.rmdir()
    if progress:
        progress(1.0)
    return {"total_socios": total, "mes_referencia": mes, "caminho": str(DB_PATH)}


# ── consulta ────────────────────────────────────────────────────────────────

def _con() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _rotulo(row: sqlite3.Row) -> dict:
    return {
        "cnpj_basico": row["cnpj_basico"],
        "cnpj": cnpj_matriz(row["cnpj_basico"]),
        "nome": row["nome"],
        "doc": row["doc"],
        "tipo": row["tipo"],
        "qualificacao": QUALIFICACAO.get(row["qualificacao"], f"qualificação {row['qualificacao']}"),
        "entrada": _data(row["entrada"]),
        "faixa": FAIXA_ETARIA.get(row["faixa"], ""),
    }


def _data(aaaammdd: str) -> str:
    d = only_digits(aaaammdd or "")
    return f"{d[6:8]}/{d[4:6]}/{d[:4]}" if len(d) == 8 else ""


def por_nome(nome: str, limit: int = 200) -> list[dict]:
    alvo = normalizar(nome)
    if len(alvo.split()) < 2:
        return []
    con = _con()
    try:
        rows = con.execute("SELECT * FROM socios WHERE nome_norm = ? LIMIT ?", (alvo, limit)).fetchall()
    finally:
        con.close()
    return [_rotulo(r) for r in rows]


def por_cpf(cpf: str, limit: int = 200) -> list[dict]:
    doc = cpf_mascarado(cpf)
    if not doc:
        return []
    con = _con()
    try:
        rows = con.execute("SELECT * FROM socios WHERE doc = ? LIMIT ?", (doc, limit)).fetchall()
    finally:
        con.close()
    return [_rotulo(r) for r in rows]


def socios_de(cnpj: str) -> list[dict]:
    basico = only_digits(cnpj)[:8]
    con = _con()
    try:
        rows = con.execute("SELECT * FROM socios WHERE cnpj_basico = ?", (basico,)).fetchall()
    finally:
        con.close()
    return [_rotulo(r) for r in rows]


def empresas_da_pessoa(nome: str, doc: str, excluir_basico: str = "", limit: int = 50) -> list[dict]:
    """Mesmo nome E mesmo CPF mascarado: é a mesma pessoa com altíssima chance."""
    con = _con()
    try:
        rows = con.execute(
            "SELECT * FROM socios WHERE nome_norm = ? AND doc = ? AND cnpj_basico != ? LIMIT ?",
            (normalizar(nome), doc, excluir_basico, limit),
        ).fetchall()
    finally:
        con.close()
    return [_rotulo(r) for r in rows]


# ── achados para o dossiê ───────────────────────────────────────────────────

MAX_EMPRESAS = 15


def _razoes(cnpjs: list[str]) -> dict[str, str]:
    """Razão social das matrizes, pela consulta de CNPJ já cacheada do motor."""
    from concurrent.futures import ThreadPoolExecutor

    from .br import consulta_cnpj

    def _uma(cnpj: str) -> tuple[str, str]:
        try:
            dados = consulta_cnpj(cnpj) or {}
        except Exception:  # noqa: BLE001
            dados = {}
        return cnpj, (dados.get("razao_social") or dados.get("nome") or "")

    unicos = list(dict.fromkeys(cnpjs))[:MAX_EMPRESAS]
    if not unicos:
        return {}
    with ThreadPoolExecutor(max_workers=min(6, len(unicos))) as pool:
        return dict(pool.map(_uma, unicos))


def _empresa(item: dict, razao: str, conf, contexto: str):
    from .findings import Finding, FindingKind

    return Finding(
        kind=FindingKind.COMPANY,
        value=razao or f"CNPJ {item['cnpj']}",
        source="socios_rfb", source_label="Sócios da Receita (índice local)",
        url=f"https://brasilapi.com.br/api/cnpj/v1/{only_digits(item['cnpj'])}",
        confidence=conf,
        detail=", ".join(p for p in [
            f"CNPJ {item['cnpj']}", item["qualificacao"],
            f"desde {item['entrada']}" if item["entrada"] else "", contexto,
        ] if p),
        raw=item,
    )


def _nome_do_cpf(cpf: str) -> str:
    """Nome oficial do CPF (Portal da Transparência), se houver chave. Cacheado."""
    try:
        from .br_auto import _lista, _portal_get

        pessoa = next(iter(_lista(_portal_get("pessoa-fisica", {"cpf": only_digits(cpf)}))), {})
        return (pessoa.get("nome") or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def findings(entity):
    from .entity import EntityType
    from .findings import Confidence, Finding, FindingKind

    out: list = []
    label = "Sócios da Receita (índice local)"

    if entity.type is EntityType.NAME:
        linhas = [r for r in por_nome(entity.value) if r["tipo"] == "2"]
        if not linhas:
            return []
        pessoas: dict[str, list[dict]] = {}
        for r in linhas:
            pessoas.setdefault(r["doc"], []).append(r)
        # Cada CPF mascarado diferente é, na prática, uma pessoa diferente.
        conf = Confidence.LIKELY if len(pessoas) == 1 else Confidence.POSSIBLE
        out.append(Finding(
            kind=FindingKind.NOTE,
            value=f"Sócio em {len({r['cnpj_basico'] for r in linhas})} empresa(s) na Receita"
                  + (f", {len(pessoas)} pessoas diferentes com este nome" if len(pessoas) > 1 else ""),
            source="socios_rfb", source_label=label, confidence=Confidence.CONFIRMED,
            detail="CPFs mascarados encontrados: " + ", ".join(sorted(pessoas)[:8]),
        ))
        razoes = _razoes([r["cnpj"] for r in linhas])
        for r in linhas[:MAX_EMPRESAS]:
            out.append(_empresa(r, razoes.get(r["cnpj"], ""), conf, f"sócio com CPF {r['doc']}"))
        return out

    if entity.type is EntityType.CPF:
        linhas = [r for r in por_cpf(entity.value) if r["tipo"] == "2"]
        if not linhas:
            return []
        nome = _nome_do_cpf(entity.value)
        if nome:
            alvo = normalizar(nome)
            batem = [r for r in linhas if normalizar(r["nome"]) == alvo]
            if not batem:
                return [Finding(
                    kind=FindingKind.NOTE, value="Não é sócio de empresa na Receita",
                    source="socios_rfb", source_label=label, confidence=Confidence.LIKELY,
                    detail=f"Nenhum sócio com o CPF mascarado e o nome {nome}.",
                )]
            razoes = _razoes([r["cnpj"] for r in batem])
            return [_empresa(r, razoes.get(r["cnpj"], ""), Confidence.CONFIRMED,
                             f"{nome}, mesmo CPF mascarado e mesmo nome") for r in batem[:MAX_EMPRESAS]]
        # Sem o nome, o miolo do CPF sozinho bate com várias pessoas.
        nomes = sorted({r["nome"] for r in linhas})
        return [Finding(
            kind=FindingKind.NOTE,
            value=f"{len(nomes)} sócio(s) na Receita com o CPF mascarado {cpf_mascarado(entity.value)}",
            source="socios_rfb", source_label=label, confidence=Confidence.POSSIBLE,
            detail="Candidatos (confirme com o nome do titular; a chave do Portal da "
                   "Transparência faz isso sozinha): " + "; ".join(nomes[:12]),
        )]

    if entity.type is EntityType.CNPJ:
        basico = only_digits(entity.value)[:8]
        coligadas: list[tuple[dict, dict]] = []
        for socio in socios_de(entity.value):
            if socio["tipo"] != "2" or not socio["doc"]:
                continue
            for outra in empresas_da_pessoa(socio["nome"], socio["doc"], excluir_basico=basico, limit=10):
                coligadas.append((socio, outra))
        if not coligadas:
            return []
        out.append(Finding(
            kind=FindingKind.NOTE,
            value=f"Sócios desta empresa aparecem em {len({o['cnpj_basico'] for _s, o in coligadas})} outra(s) empresa(s)",
            source="socios_rfb", source_label=label, confidence=Confidence.CONFIRMED,
            detail="Mesmo nome e mesmo CPF mascarado no quadro societário da Receita.",
        ))
        razoes = _razoes([o["cnpj"] for _s, o in coligadas])
        for socio, outra in coligadas[:MAX_EMPRESAS]:
            out.append(_empresa(outra, razoes.get(outra["cnpj"], ""), Confidence.CONFIRMED,
                                f"também tem {socio['nome']} no quadro"))
        return out
    return []


# ── linha de comando ────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Índice local de sócios da Receita Federal")
    ap.add_argument("--update", action="store_true", help="baixa o mês mais recente e indexa")
    ap.add_argument("--from-dir", help="indexa Socios*.zip (ou CSVs) já baixados nesta pasta")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    if args.from_dir:
        total = build_from_dir(Path(args.from_dir))
        print(f"[socios_rfb] {total} sócios indexados em {DB_PATH}")
    elif args.update:
        info = update(progress=lambda f: print(f"[socios_rfb] {f:.0%}", flush=True))
        print(f"[socios_rfb] {info['total_socios']} sócios ({info['mes_referencia']}) em {info['caminho']}")
    else:
        print(status())
    return 0


if __name__ == "__main__":
    sys.exit(main())
