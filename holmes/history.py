"""
Histórico de dossiês.

Cada investigação é salva em disco (JSON). Permite reabrir um dossiê antigo,
e — o mais útil — comparar duas investigações do mesmo alvo para ver
**o que mudou** entre elas: perfil novo, telefone novo, vazamento novo.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

HISTORY_DIR = Path(os.environ.get("HOLMES_HISTORY_DIR", ".holmes_history"))
MAX_ITEMS = 200


def _slug(texto: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in (texto or ""))[:50] or "alvo"


def save(dossier) -> str | None:
    """Salva o dossiê e devolve o id do registro (ou None se falhar)."""
    try:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        # Sufixo curto evita colisão de duas investigações no mesmo segundo.
        registro_id = f"{int(time.time())}_{uuid.uuid4().hex[:6]}_{_slug(dossier.entity.value)}"
        payload = {
            "id": registro_id,
            "alvo": dossier.entity.value,
            "tipo": dossier.entity.type.value,
            "tipo_label": dossier.entity.label,
            "quando": dossier.started_at,
            "stats": dossier.stats,
            "resumo": dossier.summary,
            "dossie": dossier.to_dict(),
        }
        (HISTORY_DIR / f"{registro_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        _prune()
        return registro_id
    except Exception:
        return None


def _prune() -> None:
    """Mantém no máximo MAX_ITEMS arquivos, apagando os mais antigos."""
    try:
        arquivos = sorted(HISTORY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
        for velho in arquivos[:-MAX_ITEMS]:
            velho.unlink()
    except Exception:
        pass


def list_entries(query: str = "", limit: int = 100) -> list[dict]:
    """Lista os registros salvos (mais recentes primeiro), só com metadados."""
    if not HISTORY_DIR.exists():
        return []
    q = (query or "").strip().lower()
    out: list[dict] = []
    for arq in sorted(HISTORY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except Exception:
            continue
        if q and q not in (d.get("alvo") or "").lower():
            continue
        out.append({
            "id": d.get("id"),
            "alvo": d.get("alvo"),
            "tipo_label": d.get("tipo_label"),
            "quando": d.get("quando"),
            "stats": d.get("stats") or {},
            "resumo": d.get("resumo") or "",
        })
        if len(out) >= limit:
            break
    return out


def load(registro_id: str) -> dict | None:
    try:
        return json.loads((HISTORY_DIR / f"{registro_id}.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def _fatos_por_secao(dossie: dict) -> dict[str, set[str]]:
    """Extrai {seção: {valores}} de um dossiê salvo, para comparar."""
    out: dict[str, set[str]] = {}
    for kind, fatos in (dossie.get("fatos") or {}).items():
        out[kind] = {f.get("value", "") for f in fatos if f.get("value")}
    return out


def diff(id_antigo: str, id_novo: str) -> dict | None:
    """
    Compara dois dossiês e devolve, por seção, o que É NOVO e o que SUMIU.
    É a razão de existir o histórico: 'o que mudou desde a última vez'.
    """
    velho = load(id_antigo)
    novo = load(id_novo)
    if not velho or not novo:
        return None

    fatos_velho = _fatos_por_secao(velho.get("dossie") or {})
    fatos_novo = _fatos_por_secao(novo.get("dossie") or {})

    from .findings import FindingKind

    rotulos = {
        "nome": "Nomes", "conta": "Contas e perfis", "email": "E-mails",
        "telefone": "Telefones", "empresa": "Empresas", "endereco": "Localização",
        "documento": "Documentos", "cripto": "Endereços de cripto",
        "vazamento": "Vazamentos", "dominio": "Domínios", "juridico": "Jurídico",
    }

    mudancas: dict[str, dict[str, list[str]]] = {}
    for kind in set(fatos_velho) | set(fatos_novo):
        if kind in ("link", "resultado_web", "nota", "imagem"):
            continue
        antes = fatos_velho.get(kind, set())
        depois = fatos_novo.get(kind, set())
        novos = sorted(depois - antes)
        sumidos = sorted(antes - depois)
        if novos or sumidos:
            mudancas[rotulos.get(kind, kind)] = {"novos": novos, "sumidos": sumidos}

    return {
        "alvo": novo.get("alvo"),
        "de": velho.get("quando"),
        "para": novo.get("quando"),
        "mudancas": mudancas,
        "tem_novidade": any(m["novos"] for m in mudancas.values()),
    }
