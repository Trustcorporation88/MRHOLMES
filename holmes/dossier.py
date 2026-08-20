"""
Consolidação do dossiê.

Recebe centenas de findings de dezenas de fontes e produz UMA resposta:
o que se sabe sobre o alvo, com que confiança e provado por qual link.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from .entity import Entity, EntityType
from .findings import ConnectorResult, CorroboratedFact, Finding, FindingKind

# Datas para a linha do tempo — ISO (2024-08-24) e BR (24/08/2024).
_DATA_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATA_BR = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")

# Findings que não entram na linha do tempo: a data no snippet de busca ou no
# deeplink é ruído, não evento do alvo.
_SEM_TIMELINE = {FindingKind.WEB_RESULT, FindingKind.LINK, FindingKind.IMAGE}


def _extrair_data(*textos: str) -> str | None:
    """Primeira data plausível (1900–2100) encontrada, normalizada em ISO."""
    for texto in textos:
        if not texto:
            continue
        m = _DATA_ISO.search(texto)
        if m:
            ano, mes, dia = m.groups()
            if 1900 <= int(ano) <= 2100:
                return f"{ano}-{mes}-{dia}"
        m = _DATA_BR.search(texto)
        if m:
            dia, mes, ano = m.groups()
            if 1900 <= int(ano) <= 2100:
                return f"{ano}-{mes}-{dia}"
    return None


# Ordem de apresentação: identidade primeiro, ruído por último.
SECTION_ORDER = [
    (FindingKind.NAME, "Nomes"),
    (FindingKind.ACCOUNT, "Contas e perfis"),
    (FindingKind.EMAIL, "E-mails"),
    (FindingKind.PHONE, "Telefones"),
    (FindingKind.COMPANY, "Empresas"),
    (FindingKind.ADDRESS, "Localização"),
    (FindingKind.DOCUMENT, "Documentos"),
    (FindingKind.CRYPTO, "Endereços de cripto"),
    (FindingKind.BREACH, "Vazamentos"),
    (FindingKind.DOMAIN, "Domínios"),
    (FindingKind.IMAGE, "Imagens"),
    (FindingKind.LEGAL, "Jurídico"),
    (FindingKind.WEB_RESULT, "Resultados na web"),
    (FindingKind.NOTE, "Observações técnicas"),
    (FindingKind.LINK, "Fontes para abrir"),
]


def _normalize_value(kind: FindingKind, value: str) -> str:
    """Mesmo fato escrito de formas diferentes tem que colidir na deduplicação."""
    v = (value or "").strip()
    if kind is FindingKind.EMAIL:
        return v.lower()
    if kind is FindingKind.PHONE:
        digits = re.sub(r"\D", "", v)
        return f"+{digits}" if digits else v
    if kind is FindingKind.NAME:
        return re.sub(r"\s+", " ", v).title()
    if kind in (FindingKind.DOMAIN, FindingKind.ACCOUNT):
        return v.lower()
    return v


@dataclass
class Dossier:
    entity: Entity
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    results: list[ConnectorResult] = field(default_factory=list)
    pivots_run: list[dict] = field(default_factory=list)
    facts: dict[str, list[CorroboratedFact]] = field(default_factory=dict)
    summary: str = ""
    next_steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # ── construção ──────────────────────────────────────────────────────────

    def add_results(self, results: Iterable[ConnectorResult]) -> None:
        self.results.extend(results)

    def all_findings(self) -> list[Finding]:
        out: list[Finding] = []
        for r in self.results:
            out.extend(r.findings)
        return out

    def consolidate(self) -> None:
        """Funde findings iguais e agrupa por seção."""
        buckets: dict[tuple[str, str], CorroboratedFact] = {}
        for f in self.all_findings():
            if not f.value:
                continue
            norm = _normalize_value(f.kind, f.value)
            key = (f.kind.value, norm.lower())
            fact = buckets.get(key)
            if not fact:
                fact = CorroboratedFact(kind=f.kind, value=norm)
                buckets[key] = fact
            fact.findings.append(f)

        grouped: dict[str, list[CorroboratedFact]] = {}
        for fact in buckets.values():
            grouped.setdefault(fact.kind.value, []).append(fact)
        for kind, items in grouped.items():
            items.sort(key=lambda x: (-x.score, x.value.lower()))
        self.facts = grouped

    # ── leitura ─────────────────────────────────────────────────────────────

    def section(self, kind: FindingKind) -> list[CorroboratedFact]:
        return self.facts.get(kind.value, [])

    def sections(self) -> list[tuple[str, list[CorroboratedFact]]]:
        out = []
        for kind, label in SECTION_ORDER:
            items = self.section(kind)
            if items:
                out.append((label, items))
        return out

    def high_confidence(self, minimum: float = 0.55) -> list[CorroboratedFact]:
        out = [
            f
            for kind, _ in SECTION_ORDER
            for f in self.section(kind)
            if f.score >= minimum and kind not in (FindingKind.LINK, FindingKind.WEB_RESULT)
        ]
        return sorted(out, key=lambda f: -f.score)

    # ── dossiê estilo agência ─────────────────────────────────────────────────

    def identity_card(self) -> dict:
        """
        Cartão de identidade: o melhor de cada tipo, para bater o olho e saber
        quem é o alvo sem ler o dossiê inteiro. É o topo do relatório.
        """
        def melhores(kind: FindingKind, n: int = 3) -> list[str]:
            return [f.value for f in self.section(kind)[:n]]

        def melhor(kind: FindingKind) -> str:
            itens = self.section(kind)
            return itens[0].value if itens else ""

        foto = ""
        for f in self.section(FindingKind.IMAGE):
            if f.value.startswith("http"):
                foto = f.value
                break

        # Bandeiras que mudam a leitura do caso, em ordem de gravidade.
        flags: list[str] = []
        if any("POLITICAMENTE EXPOSTA" in n.value.upper() for n in self.section(FindingKind.NOTE)):
            flags.append("Pessoa politicamente exposta (PEP)")
        vaz = self.section(FindingKind.BREACH)
        if vaz:
            flags.append(f"{len(vaz)} vazamento(s)")
        sancoes = [j for j in self.section(FindingKind.LEGAL) if "SANÇÃO" in j.value.upper()]
        if sancoes:
            flags.append(f"{len(sancoes)} sanção(ões) oficial(is)")

        nome = melhor(FindingKind.NAME)
        if not nome and self.entity.type is EntityType.NAME:
            nome = self.entity.value

        contas = self.section(FindingKind.ACCOUNT)
        return {
            "alvo": self.entity.value,
            "tipo": self.entity.label,
            "nome": nome,
            "foto": foto,
            "emails": melhores(FindingKind.EMAIL, 4),
            "telefones": melhores(FindingKind.PHONE, 4),
            "localizacao": melhor(FindingKind.ADDRESS),
            "empresas": melhores(FindingKind.COMPANY, 3),
            "documentos": melhores(FindingKind.DOCUMENT, 3),
            "contas": [c.value for c in contas[:8]],
            "total_contas": len(contas),
            "flags": flags,
        }

    def timeline(self) -> list[dict]:
        """
        Linha do tempo: todo achado com data vira um evento, em ordem
        cronológica. Vazamento, registro de domínio, entrada em sociedade,
        infecção por malware — tudo que tem quando.
        """
        vistos: set[tuple] = set()
        eventos: list[dict] = []
        for f in self.all_findings():
            if f.kind in _SEM_TIMELINE:
                continue
            try:
                raw_blob = json.dumps(f.raw, ensure_ascii=False)
            except Exception:
                raw_blob = ""
            data = _extrair_data(f.value, f.detail, raw_blob)
            if not data:
                continue
            texto = f.value if len(f.value) <= 90 else f.value[:90] + "…"
            chave = (data, f.kind.value, texto.lower())
            if chave in vistos:
                continue
            vistos.add(chave)
            eventos.append({
                "data": data,
                "texto": texto,
                "tipo": f.kind.value,
                "fonte": f.source_label or f.source,
                "url": f.url or "",
            })
        eventos.sort(key=lambda e: e["data"])
        return eventos[:40]

    @property
    def stats(self) -> dict:
        ok = [r for r in self.results if r.ok and not r.skipped_reason]
        failed = [r for r in self.results if not r.ok and not r.skipped_reason]
        skipped = [r for r in self.results if r.skipped_reason]
        total_facts = sum(len(v) for v in self.facts.values())
        return {
            "fontes_consultadas": len(ok),
            "fontes_com_erro": len(failed),
            "fontes_puladas": len(skipped),
            "achados_brutos": len(self.all_findings()),
            "fatos_consolidados": total_facts,
            "pivos": len(self.pivots_run),
            "tempo_total_ms": sum(r.elapsed_ms for r in self.results),
        }

    @property
    def failures(self) -> list[ConnectorResult]:
        return [r for r in self.results if not r.ok]

    # ── exportação ──────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "alvo": self.entity.to_dict(),
            "iniciado_em": self.started_at,
            "resumo": self.summary,
            "proximos_passos": self.next_steps,
            "avisos": self.warnings,
            "estatisticas": self.stats,
            "pivos": self.pivots_run,
            "fatos": {k: [f.to_dict() for f in v] for k, v in self.facts.items()},
            "execucao": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_markdown(self) -> str:
        L: list[str] = []
        L.append(f"# Dossiê — {self.entity.value}")
        L.append("")
        L.append(f"**Tipo de alvo:** {self.entity.label}  ")
        L.append(f"**Gerado em:** {self.started_at}  ")
        s = self.stats
        L.append(
            f"**Cobertura:** {s['fontes_consultadas']} fontes consultadas · "
            f"{s['fatos_consolidados']} fatos · {s['pivos']} pivôs"
        )
        L.append("")

        if self.summary:
            L.append("## Leitura do caso")
            L.append("")
            L.append(self.summary)
            L.append("")

        destaque = self.high_confidence()
        if destaque:
            L.append("## O que está bem sustentado")
            L.append("")
            for fact in destaque[:20]:
                fontes = ", ".join(fact.sources[:4])
                L.append(f"- **{fact.value}** — confiança {fact.label} ({fontes})")
            L.append("")

        for label, items in self.sections():
            L.append(f"## {label}")
            L.append("")
            for fact in items[:60]:
                linha = f"- **{fact.value}**"
                if fact.detail:
                    linha += f" — {fact.detail}"
                linha += f"  \n  confiança {fact.label} · fontes: {', '.join(fact.sources[:5])}"
                if fact.urls:
                    linha += f"  \n  {fact.urls[0]}"
                L.append(linha)
            L.append("")

        if self.pivots_run:
            L.append("## Cadeia de pivôs")
            L.append("")
            for p in self.pivots_run:
                L.append(f"- `{p.get('alvo')}` ({p.get('tipo')}) — {p.get('motivo')}")
            L.append("")

        if self.next_steps:
            L.append("## Próximos passos")
            L.append("")
            for step in self.next_steps:
                L.append(f"- {step}")
            L.append("")

        if self.failures:
            L.append("## Fontes que não responderam")
            L.append("")
            for r in self.failures:
                motivo = r.skipped_reason or r.error or "erro desconhecido"
                L.append(f"- {r.connector_label}: {motivo}")
            L.append("")

        L.append("---")
        L.append("")
        L.append(
            "Documento gerado pelo Mr.Holmes a partir de fontes públicas. "
            "Uso educacional e em alvos autorizados. Confirme cada fato na fonte "
            "antes de qualquer decisão."
        )
        return "\n".join(L)

    def to_html(self) -> str:
        """HTML autocontido — serve para arquivar o caso e para imprimir em PDF."""
        def esc(t: str) -> str:
            return (
                str(t).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;")
            )

        s = self.stats
        parts: list[str] = [
            "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>",
            f"<title>Dossiê — {esc(self.entity.value)}</title>",
            """<style>
            :root{--ink:#0b1220;--mut:#5b6779;--line:#e2e8f0;--acc:#0f62fe;--bg:#f8fafc}
            *{box-sizing:border-box}
            body{font-family:ui-sans-serif,-apple-system,'Segoe UI',Roboto,sans-serif;
                 margin:0;background:var(--bg);color:var(--ink);line-height:1.55}
            .wrap{max-width:960px;margin:0 auto;padding:48px 32px}
            header{border-bottom:3px solid var(--ink);padding-bottom:20px;margin-bottom:32px}
            .eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;
                     color:var(--mut);font-weight:700}
            h1{font-size:34px;margin:8px 0 6px;letter-spacing:-.02em}
            .meta{color:var(--mut);font-size:14px}
            .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
                   gap:12px;margin:24px 0 8px}
            .card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px}
            .card b{display:block;font-size:24px}
            .card span{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em}
            h2{font-size:19px;margin:36px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
            .fact{background:#fff;border:1px solid var(--line);border-left:4px solid var(--line);
                  border-radius:8px;padding:12px 14px;margin-bottom:8px}
            .fact.alta{border-left-color:#0f9d58}.fact.media{border-left-color:#f4b400}
            .fact.baixa{border-left-color:#db4437}.fact.indicio{border-left-color:#9aa5b1}
            .val{font-weight:650}
            .det{color:var(--mut);font-size:14px;margin-top:3px}
            .src{font-size:12px;color:var(--mut);margin-top:6px}
            .badge{display:inline-block;font-size:10px;font-weight:700;text-transform:uppercase;
                   letter-spacing:.06em;padding:2px 7px;border-radius:99px;background:#eef2f7;
                   color:var(--mut);margin-right:6px}
            a{color:var(--acc);text-decoration:none;word-break:break-all}
            a:hover{text-decoration:underline}
            .summary{background:#fff;border:1px solid var(--line);border-radius:10px;
                     padding:18px 20px;white-space:pre-wrap}
            footer{margin-top:48px;padding-top:16px;border-top:1px solid var(--line);
                   color:var(--mut);font-size:12px}
            @media print{body{background:#fff}.wrap{padding:0}}
            </style></head><body><div class='wrap'>""",
            "<header><div class='eyebrow'>Dossiê de investigação · Mr.Holmes</div>",
            f"<h1>{esc(self.entity.value)}</h1>",
            f"<div class='meta'>{esc(self.entity.label)} · gerado em {esc(self.started_at)}</div>",
            "</header>",
            "<div class='cards'>",
            f"<div class='card'><b>{s['fontes_consultadas']}</b><span>fontes</span></div>",
            f"<div class='card'><b>{s['fatos_consolidados']}</b><span>fatos</span></div>",
            f"<div class='card'><b>{s['pivos']}</b><span>pivôs</span></div>",
            f"<div class='card'><b>{s['achados_brutos']}</b><span>achados brutos</span></div>",
            "</div>",
        ]

        if self.summary:
            parts.append("<h2>Leitura do caso</h2>")
            parts.append(f"<div class='summary'>{esc(self.summary)}</div>")

        for label, items in self.sections():
            parts.append(f"<h2>{esc(label)}</h2>")
            for fact in items[:80]:
                url = fact.urls[0] if fact.urls else ""
                link = f"<div class='src'><a href='{esc(url)}' target='_blank' rel='noopener noreferrer'>{esc(url)}</a></div>" if url else ""
                parts.append(
                    f"<div class='fact {fact.label}'>"
                    f"<span class='badge'>{esc(fact.label)}</span>"
                    f"<span class='val'>{esc(fact.value)}</span>"
                    + (f"<div class='det'>{esc(fact.detail)}</div>" if fact.detail else "")
                    + f"<div class='src'>fontes: {esc(', '.join(fact.sources[:6]))}</div>"
                    + link
                    + "</div>"
                )

        if self.pivots_run:
            parts.append("<h2>Cadeia de pivôs</h2>")
            for p in self.pivots_run:
                parts.append(
                    f"<div class='fact'><span class='val'>{esc(p.get('alvo'))}</span>"
                    f"<div class='det'>{esc(p.get('motivo'))}</div></div>"
                )

        if self.next_steps:
            parts.append("<h2>Próximos passos</h2><ul>")
            for step in self.next_steps:
                parts.append(f"<li>{esc(step)}</li>")
            parts.append("</ul>")

        parts.append(
            "<footer>Gerado pelo Mr.Holmes a partir de fontes públicas. "
            "Uso educacional, em alvos autorizados. Cada fato deve ser conferido "
            "na fonte original antes de embasar qualquer decisão.</footer>"
        )
        parts.append("</div></body></html>")
        return "".join(parts)
