"""
Análise por IA.

A LLM aqui não escreve texto bonito: ela faz o trabalho que um analista faria
ao receber a pilha de evidências — separar o alvo do homônimo, apontar
contradição, dizer o que está fraco e sugerir o próximo movimento.

Regra dura no prompt: só afirmar o que está na evidência. Investigação com
alucinação é pior que investigação nenhuma.
"""

from __future__ import annotations

import json
import re
from typing import Any

_SYSTEM = """Você é um analista OSINT sênior revisando as evidências brutas de uma investigação.

REGRAS INEGOCIÁVEIS:
1. Só afirme o que está literalmente nas evidências fornecidas. Nunca infira dado que não está lá.
2. Se a evidência é fraca, diga que é fraca. Nunca transforme indício em conclusão.
3. Homônimo é o erro nº 1 em OSINT: se os achados parecem se referir a pessoas
   diferentes, aponte isso explicitamente e explique o que os separa.
4. Contradição entre fontes é informação valiosa — reporte, não esconda.
5. Não invente URL, nome, data ou número. Nenhum.
6. Escreva em português do Brasil, direto, sem enrolação e sem jargão desnecessário.

Responda SOMENTE com um objeto JSON válido, sem cercas de código, no formato:
{
  "resumo": "3 a 6 frases: quem/o que é o alvo segundo as evidências, o que foi confirmado, o que é dúvida.",
  "identidade_provavel": "a leitura mais sustentada, ou 'indeterminada' se as evidências não fecham",
  "conflitos": ["cada sinal de que há mais de uma pessoa/entidade misturada, ou contradição entre fontes"],
  "pontos_fracos": ["fatos que parecem fortes mas se apoiam em fonte única ou frágil"],
  "proximos_passos": ["ações concretas e específicas para este alvo, não conselho genérico"]
}"""


def _evidence_blob(dossier, char_budget: int = 14000) -> str:
    """Serializa o dossiê priorizando o que é decisivo, dentro do orçamento de contexto."""
    from .findings import FindingKind

    ent = dossier.entity
    L: list[str] = [
        f"ALVO: {ent.value}",
        f"TIPO: {ent.label}",
        "",
    ]

    prioridade = [
        FindingKind.NAME, FindingKind.ACCOUNT, FindingKind.EMAIL,
        FindingKind.PHONE, FindingKind.COMPANY, FindingKind.ADDRESS,
        FindingKind.BREACH, FindingKind.DOMAIN, FindingKind.WEB_RESULT,
        FindingKind.NOTE,
    ]
    for kind in prioridade:
        items = dossier.section(kind)
        if not items:
            continue
        L.append(f"## {kind.value.upper()}")
        for fact in items[:25]:
            linha = f"- {fact.value} [confiança {fact.label}; fontes: {', '.join(fact.sources[:4])}]"
            if fact.detail:
                linha += f" — {fact.detail[:200]}"
            L.append(linha)
        L.append("")
        if sum(len(x) for x in L) > char_budget:
            L.append("(evidências truncadas por limite de contexto)")
            break

    if dossier.pivots_run:
        L.append("## PIVÔS EXECUTADOS")
        for p in dossier.pivots_run[:15]:
            L.append(f"- {p.get('alvo')} ({p.get('tipo')}): {p.get('motivo')}")

    falhas = dossier.failures
    if falhas:
        L.append("")
        L.append(f"## FONTES QUE NÃO RESPONDERAM ({len(falhas)})")
        L.append(", ".join(r.connector_label for r in falhas[:20]))

    return "\n".join(L)[:char_budget]


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    match = re.search(r"\{.*\}", cleaned, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


def available() -> bool:
    try:
        from Core.Support.Robin.llm_bridge import provider_status

        status = provider_status() or {}
        return bool(status.get("openai") or status.get("anthropic") or status.get("google"))
    except Exception:
        from . import net

        return net.has_key("openai") or net.has_key("anthropic")


def analyze(dossier, model: str | None = None) -> dict[str, Any] | None:
    """Devolve o dicionário de análise, ou None se não houver LLM configurada."""
    if not available():
        return None
    try:
        from Core.Support.Robin.llm_bridge import chat, list_models
    except Exception:
        return None

    if not model:
        models = list_models() or []
        model = (models[0] or {}).get("id") if models else None
    if not model:
        return None

    raw = chat(model, _SYSTEM, _evidence_blob(dossier))
    data = _extract_json(raw or "")
    if not data:
        return None

    avisos: list[str] = []
    for conflito in data.get("conflitos") or []:
        avisos.append(f"Possível conflito de identidade: {conflito}")
    for fraco in data.get("pontos_fracos") or []:
        avisos.append(f"Evidência frágil: {fraco}")

    resumo = data.get("resumo") or ""
    identidade = data.get("identidade_provavel")
    if identidade and identidade.lower() not in {"indeterminada", "indeterminado"}:
        resumo = f"{resumo}\n\nLeitura mais sustentada: {identidade}"

    return {
        "resumo": resumo.strip(),
        "proximos_passos": data.get("proximos_passos") or [],
        "avisos": avisos,
        "bruto": data,
    }


def answer_question(dossier, question: str, model: str | None = None) -> str:
    """Pergunta e resposta em cima do dossiê já levantado, sem reinvestigar."""
    try:
        from Core.Support.Robin.llm_bridge import chat, list_models
    except Exception:
        return "IA indisponível neste ambiente."

    if not model:
        models = list_models() or []
        model = (models[0] or {}).get("id") if models else None
    if not model:
        return "Configure uma chave de LLM (OpenAI ou Anthropic) para usar o chat do dossiê."

    system = (
        "Você é um analista OSINT respondendo perguntas sobre um dossiê já levantado. "
        "Responda APENAS com base nas evidências abaixo. Se a resposta não estiver nelas, "
        "diga exatamente o que falta investigar para obtê-la. Nunca invente. "
        "Português do Brasil, direto ao ponto."
    )
    user = f"{_evidence_blob(dossier)}\n\n---\nPERGUNTA: {question}"
    return chat(model, system, user) or "Sem resposta do modelo."
