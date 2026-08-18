"""
Orquestrador.

Uma chamada: `investigate("fulano de tal")`. Ele detecta o alvo, dispara
todas as fontes aplicáveis em paralelo, encadeia os pivôs e devolve o dossiê.

Princípio: fonte que falha não derruba a investigação — vira linha na seção
"fontes que não responderam".
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

from . import pivot as pivot_mod
from .connectors import Mode, connectors_for, ensure_registered
from .dossier import Dossier
from .entity import Entity, EntityType, detect
from .findings import ConnectorResult

ProgressFn = Callable[[str, float], None]


@dataclass
class InvestigationConfig:
    depth: int = 2                  # 1 = só o alvo; 2 = +1 salto; 3 = +2 saltos
    max_workers: int = 10
    include_deeplinks: bool = True
    include_manual: bool = True
    max_pivots_per_hop: int = 4
    use_llm: bool = True
    global_timeout: int = 300       # teto total, para a UI nunca travar


def _run_batch(
    entity: Entity,
    modes: set[Mode],
    config: InvestigationConfig,
    progress: ProgressFn | None,
    progress_base: float,
    progress_span: float,
) -> list[ConnectorResult]:
    """Dispara todos os conectores aplicáveis a um alvo, em paralelo."""
    conns = connectors_for(entity, modes)
    if not conns:
        return []

    results: list[ConnectorResult] = []
    done = 0
    total = len(conns)

    with ThreadPoolExecutor(max_workers=min(config.max_workers, max(1, total))) as pool:
        futures = {pool.submit(c.execute, entity): c for c in conns}
        for fut in as_completed(futures):
            conn = futures[fut]
            try:
                results.append(fut.result())
            except Exception as exc:  # noqa: BLE001 — blindagem final
                results.append(ConnectorResult(
                    connector_id=conn.id, connector_label=conn.label,
                    ok=False, error=f"falha inesperada: {exc}",
                ))
            done += 1
            if progress:
                progress(
                    f"{entity.value} · {conn.label} ({done}/{total})",
                    progress_base + progress_span * (done / total),
                )
    return results


def investigate(
    raw_target: str,
    config: InvestigationConfig | None = None,
    progress: ProgressFn | None = None,
) -> Dossier:
    """Ponto de entrada único do motor."""
    ensure_registered()
    cfg = config or InvestigationConfig()
    started = time.time()

    entity = detect(raw_target)
    dossier = Dossier(entity=entity)

    if entity.type is EntityType.UNKNOWN or not entity.value:
        dossier.warnings.append("Alvo vazio ou não reconhecido.")
        dossier.consolidate()
        return dossier

    for note in entity.notes:
        dossier.warnings.append(note)

    modes = {Mode.AUTO}
    if cfg.include_deeplinks:
        modes.add(Mode.DEEPLINK)
    if cfg.include_manual:
        modes.add(Mode.MANUAL)

    # ── salto 0: o alvo informado ───────────────────────────────────────────
    if progress:
        progress(f"Detectado: {entity.label} — {entity.value}", 0.02)

    results = _run_batch(entity, modes, cfg, progress, 0.02, 0.48)
    dossier.add_results(results)

    seen: set[str] = {f"{entity.type.value}:{entity.value.lower()}"}

    # ── saltos seguintes: pivôs ─────────────────────────────────────────────
    hop = 1
    pending = pivot_mod.dedupe_and_rank(
        pivot_mod.from_entity(entity)
        + pivot_mod.from_findings([f for r in results for f in r.findings], hop, entity),
        seen,
        limit=cfg.max_pivots_per_hop,
    )

    while hop < cfg.depth and pending:
        if time.time() - started > cfg.global_timeout:
            dossier.warnings.append(
                f"Tempo limite de {cfg.global_timeout}s atingido — pivôs restantes não foram executados."
            )
            break

        span = 0.4 / max(1, cfg.depth - 1)
        base = 0.5 + span * (hop - 1)
        new_findings = []

        for idx, piv in enumerate(pending):
            if time.time() - started > cfg.global_timeout:
                break
            seen.add(piv.key)
            dossier.pivots_run.append({
                "alvo": piv.entity.value,
                "tipo": piv.entity.label,
                "motivo": piv.reason,
                "origem": piv.origin,
                "salto": hop,
            })
            if progress:
                progress(f"Pivô {hop}.{idx + 1}: {piv.entity.value}", base + span * (idx / max(1, len(pending))))

            # No pivô, só fontes automáticas: deeplink de alvo derivado vira ruído.
            piv_results = _run_batch(
                piv.entity, {Mode.AUTO}, cfg, None, base, span / max(1, len(pending))
            )
            dossier.add_results(piv_results)
            new_findings.extend(f for r in piv_results for f in r.findings)

        hop += 1
        pending = pivot_mod.dedupe_and_rank(
            pivot_mod.from_findings(new_findings, hop, entity), seen, limit=cfg.max_pivots_per_hop
        )

    # ── consolidação ────────────────────────────────────────────────────────
    if progress:
        progress("Consolidando dossiê…", 0.92)
    dossier.consolidate()

    if cfg.use_llm:
        if progress:
            progress("Analisando com IA…", 0.96)
        try:
            from .llm import analyze

            analysis = analyze(dossier)
            if analysis:
                dossier.summary = analysis.get("resumo") or ""
                dossier.next_steps = analysis.get("proximos_passos") or []
                dossier.warnings.extend(analysis.get("avisos") or [])
        except Exception as exc:  # noqa: BLE001
            dossier.warnings.append(f"Análise por IA indisponível: {exc}")

    if not dossier.summary:
        dossier.summary = _fallback_summary(dossier)
    if not dossier.next_steps:
        dossier.next_steps = _fallback_next_steps(dossier)

    if progress:
        progress("Pronto.", 1.0)
    return dossier


def _fallback_summary(dossier: Dossier) -> str:
    """Resumo determinístico — o dossiê nunca sai sem leitura, mesmo sem LLM."""
    from .findings import FindingKind

    s = dossier.stats
    ent = dossier.entity
    linhas = [
        f"Alvo: {ent.value} ({ent.label}). "
        f"{s['fontes_consultadas']} fontes responderam e produziram "
        f"{s['fatos_consolidados']} fatos consolidados a partir de "
        f"{s['achados_brutos']} achados brutos."
    ]

    contas = dossier.section(FindingKind.ACCOUNT)
    if contas:
        fortes = [c for c in contas if c.score >= 0.55]
        linhas.append(
            f"Foram localizadas {len(contas)} contas/perfis, sendo {len(fortes)} com "
            "confirmação direta da plataforma."
        )
    emails = dossier.section(FindingKind.EMAIL)
    if emails:
        linhas.append(f"E-mails associados: {', '.join(e.value for e in emails[:5])}.")
    fones = dossier.section(FindingKind.PHONE)
    if fones:
        linhas.append(f"Telefones associados: {', '.join(f.value for f in fones[:5])}.")
    nomes = dossier.section(FindingKind.NAME)
    if nomes and ent.type is not EntityType.NAME:
        linhas.append(f"Nomes vinculados: {', '.join(n.value for n in nomes[:4])}.")
    vaz = dossier.section(FindingKind.BREACH)
    if vaz:
        linhas.append(
            f"O alvo aparece em {len(vaz)} vazamento(s) conhecido(s): "
            f"{', '.join(v.value for v in vaz[:6])}."
        )

    # Camada Brasil: o que muda o nível de diligência do caso vem primeiro.
    notas = dossier.section(FindingKind.NOTE)
    pep = [n for n in notas if "POLITICAMENTE EXPOSTA" in n.value.upper()]
    if pep:
        linhas.append(
            "ATENÇÃO: o alvo consta como pessoa politicamente exposta — "
            + "; ".join(p.value for p in pep[:2])
            + ". Isso eleva o nível de diligência exigido."
        )

    juridico = dossier.section(FindingKind.LEGAL)
    if juridico:
        sancoes = [j for j in juridico if "SANÇÃO" in j.value.upper()]
        diarios = [j for j in juridico if "Diário Oficial" in j.value]
        processos = [j for j in juridico if j not in sancoes and j not in diarios]
        partes = []
        if sancoes:
            partes.append(f"{len(sancoes)} sanção(ões) em base oficial")
        if processos:
            partes.append(f"{len(processos)} registro(s) processual(is)")
        if diarios:
            partes.append(f"{len(diarios)} menção(ões) em diário oficial municipal")
        if partes:
            linhas.append("No âmbito jurídico e administrativo: " + ", ".join(partes) + ".")

    empresas = dossier.section(FindingKind.COMPANY)
    if empresas and ent.type is not EntityType.CNPJ:
        linhas.append(f"Vínculo empresarial: {', '.join(e.value for e in empresas[:4])}.")
    if dossier.pivots_run:
        linhas.append(
            f"O motor executou {len(dossier.pivots_run)} pivô(s) automático(s) a partir dos achados."
        )
    return " ".join(linhas)


def _fallback_next_steps(dossier: Dossier) -> list[str]:
    from .findings import FindingKind

    passos: list[str] = []
    ent = dossier.entity

    if dossier.section(FindingKind.IMAGE):
        passos.append("Rodar busca reversa das fotos encontradas no Yandex Imagens e no Google Lens.")
    if dossier.section(FindingKind.EMAIL) and ent.type is not EntityType.EMAIL:
        passos.append("Reinvestigar cada e-mail encontrado como alvo principal para abrir novas contas.")
    if dossier.section(FindingKind.COMPANY):
        passos.append("Consultar o CNPJ das empresas citadas para obter o quadro societário completo.")
    if not dossier.section(FindingKind.ACCOUNT):
        passos.append(
            "Nenhuma conta confirmada: tentar variações do handle (com ponto, underline, número) "
            "e o nome sem acento."
        )
    fracos = [f for f in dossier.high_confidence(0.0) if f.score < 0.4]
    if fracos:
        passos.append(
            f"Confirmar manualmente os {len(fracos)} fatos de baixa confiança antes de usá-los — "
            "há risco de homônimo."
        )
    passos.append("Abrir os links da seção «Fontes para abrir» — eles já vão pesquisados no alvo.")
    return passos
