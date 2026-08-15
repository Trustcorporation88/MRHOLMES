"""
Orquestra a investigação Robin dentro do Holmes.

Prompts de relatório adaptados de Robin (MIT) © Apurv Singh Gautam.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import llm_bridge
from .llm_bridge import last_error
from .scrape import scrape_multiple
from .search import ensure_tor, get_search_results, tor_proxy_up

INVESTIGATIONS_DIR = Path("investigations")

PRESET_LABELS = {
    "threat_intel": "Dark Web Threat Intel",
    "ransomware_malware": "Ransomware / Malware",
    "personal_identity": "Identidade / PII",
    "corporate_espionage": "Vazamento corporativo",
}

# Prompts do Robin (MIT) — seções Markdown do relatório.
_PRESET_PROMPTS = {
    "threat_intel": """
You are an Cybercrime Threat Intelligence Expert tasked with generating context-based technical investigative insights from dark web osint search engine results.

Rules:
0. STRICT GROUNDING: Only report artifacts, IOCs, and claims explicitly present in the provided INPUT data. Do not infer, extrapolate, or fabricate anything absent from the input — if evidence isn't there, omit it rather than speculate.
1. Analyze the Darkweb OSINT data provided using links and their raw text.
2. Output the Source Links referenced for the analysis.
3. Provide a detailed, contextual, evidence-based technical analysis of the data.
4. Provide intelligence artifacts along with their context visible in the data.
5. The artifacts can include indicators like name, email, phone, cryptocurrency addresses, domains, darkweb markets, forum names, threat actor information, malware names, TTPs, etc.
6. Generate 3-5 key insights based on the data.
7. Each insight should be specific, actionable, context-based, and data-driven.
8. Include suggested next steps and queries for investigating more on the topic.
9. Be objective and analytical in your assessment.
10. Ignore not safe for work texts from the analysis

Output Format — respond in Markdown. Render EVERY section below as its own `## Heading`. Use bullet points (`-`) for all lists. Do NOT use numbered lists.

## Input Query
{query}

## Source Links Referenced for Analysis
- every source link used for the analysis

## Investigation Artifacts
- each technical artifact with its context

## Key Insights
- each insight as its own bullet

## Next Steps
- each next investigative step

INPUT:
""",
    "ransomware_malware": """
You are a Malware and Ransomware Intelligence Expert tasked with analyzing dark web data for malware-related threats.
STRICT GROUNDING: Only report artifacts present in the INPUT. Respond in Markdown with headings ## Input Query, ## Source Links Referenced for Analysis, ## Malware / Ransomware Indicators, ## Threat Actor Profile, ## Key Insights, ## Next Steps. Use bullets only.
Query: {query}
INPUT:
""",
    "personal_identity": """
You are a Personal Threat Intelligence Expert tasked with analyzing dark web data for identity and personal information exposure.
STRICT GROUNDING: Only report artifacts present in the INPUT. Handle personal data with discretion. Respond in Markdown with ## Input Query, ## Source Links Referenced for Analysis, ## Exposed PII Artifacts, ## Breach / Marketplace Sources Identified, ## Exposure Risk Assessment, ## Key Insights, ## Next Steps. Use bullets only.
Query: {query}
INPUT:
""",
    "corporate_espionage": """
You are a Corporate Intelligence Expert tasked with analyzing dark web data for corporate data leaks and espionage activity.
STRICT GROUNDING: Only report artifacts present in the INPUT. Respond in Markdown with ## Input Query, ## Source Links Referenced for Analysis, ## Leaked Corporate Artifacts, ## Threat Actor / Broker Activity, ## Business Impact Assessment, ## Key Insights, ## Next Steps. Use bullets only.
Query: {query}
INPUT:
""",
}


def tool_status() -> dict:
    models = llm_bridge.list_models()
    return {
        "tor": ensure_tor(wait_seconds=8),
        "llm": bool(models),
        "models": models,
        "providers": llm_bridge.provider_status(),
    }


def _refine_query(llm_id: str | None, query: str) -> str:
    system = (
        "You are a Cybercrime Threat Intelligence Expert. Refine the user query "
        "for dark-web search engines. No logical operators. 5 words or less. "
        "Output just the refined query."
    )
    refined = llm_bridge.chat(llm_id, system, query)
    cleaned = re.sub(r"\s+", " ", (refined or "").strip())
    if not cleaned:
        words = re.findall(r"[A-Za-z0-9_.-]{2,}", query)
        cleaned = " ".join(words[:5]) or query.strip()
    return cleaned[:80]


def _filter_results(llm_id: str | None, query: str, results: list[dict], limit: int) -> list[dict]:
    if not results:
        return []
    if not llm_id or len(results) <= limit:
        return results[:limit]
    listing = "\n".join(
        f"{i}. {re.sub(r'(?<=\.onion).*', '', item.get('link', ''))} - {item.get('title', '')[:80]}"
        for i, item in enumerate(results, 1)
    )
    system = (
        "You are a Cybercrime Threat Intelligence Expert. Select the most relevant "
        f"results for the query. Output ONLY up to {limit} indices as a comma-separated list.\n"
        f"Search Query: {query}\nSearch Results:"
    )
    raw = llm_bridge.chat(llm_id, system, listing)
    indices = []
    seen = set()
    for match in re.findall(r"\d+", raw or ""):
        idx = int(match)
        if 1 <= idx <= len(results) and idx not in seen:
            seen.add(idx)
            indices.append(idx)
        if len(indices) >= limit:
            break
    if not indices:
        return results[:limit]
    return [results[i - 1] for i in indices]


def _fallback_summary(query: str, sources: list[dict], scraped: dict) -> str:
    lines = [
        f"## Input Query\n{query}",
        "",
        "## Source Links Referenced for Analysis",
    ]
    if sources:
        lines.extend(f"- [{item.get('title', 'Untitled')}]({item.get('link', '')})" for item in sources)
    else:
        lines.append("- Nenhum resultado nesta rodada")
    lines += ["", "## Investigation Artifacts"]
    if scraped:
        for url, text in list(scraped.items())[:12]:
            snippet = re.sub(r"\s+", " ", text)[:220]
            lines.append(f"- `{url}` — {snippet}")
    else:
        lines.append("- Sem texto raspado (Tor ausente ou páginas indisponíveis)")
    lines += [
        "",
        "## Key Insights",
        "- Relatório heurístico: nenhum LLM configurado ou a chamada falhou.",
        "- Revise as fontes acima antes de tratar qualquer artefato como confirmado.",
        "",
        "## Next Steps",
        "- Configure OPENAI_API_KEY / Ollama para o briefing completo do Robin.",
        "- Suba Tor (porta 9050) para scrape de páginas .onion.",
    ]
    return "\n".join(lines)


def _generate_summary(llm_id: str | None, query: str, scraped: dict, preset: str, extra: str) -> str:
    prompt = _PRESET_PROMPTS.get(preset, _PRESET_PROMPTS["threat_intel"]).replace("{query}", query)
    if extra.strip():
        prompt = prompt.rstrip() + f"\n\nAdditionally focus on: {extra.strip()}\n"
    content = "\n\n".join(f"{url}\n{text}" for url, text in (scraped or {}).items()) or "(no scraped text)"
    text = llm_bridge.chat(llm_id, prompt, content)
    return text.strip() if text and text.strip() else ""


def run_investigation(
    query: str,
    *,
    model: str | None = None,
    preset: str = "threat_intel",
    custom_instructions: str = "",
    threads: int = 4,
    max_results: int = 50,
    max_scrape: int = 10,
) -> dict:
    query = (query or "").strip()
    if not query:
        return {"ok": False, "error": "Informe uma query."}

    refined = _refine_query(model, query)
    search = get_search_results(refined, max_workers=threads)
    raw_results = (search.get("results") or [])[: max(1, int(max_results))]
    filtered = _filter_results(model, refined, raw_results, max(1, int(max_scrape)))
    scraped = scrape_multiple(filtered, max_workers=threads) if filtered else {}
    summary = _generate_summary(model, query, scraped, preset, custom_instructions)
    if not summary:
        summary = _fallback_summary(query, filtered, scraped)

    record = {
        "ok": True,
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "refined_query": refined,
        "model": model or "heuristic",
        "preset": PRESET_LABELS.get(preset, preset),
        "preset_key": preset,
        "sources": filtered,
        "scraped": scraped,
        "summary": summary,
        "results_count": len(raw_results),
        "via_tor": search.get("via_tor"),
        "via_clearnet": search.get("via_clearnet"),
        "engines": search.get("engines"),
        "llm_error": last_error(),
    }
    record["filename"] = save_investigation(record)
    return record


def save_investigation(data: dict) -> str:
    INVESTIGATIONS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"investigation_{stamp}.json"
    payload = {
        "timestamp": data.get("timestamp"),
        "query": data.get("query"),
        "refined_query": data.get("refined_query"),
        "model": data.get("model"),
        "preset": data.get("preset"),
        "preset_key": data.get("preset_key"),
        "sources": data.get("sources") or [],
        "summary": data.get("summary") or "",
        "via_tor": data.get("via_tor"),
        "via_clearnet": data.get("via_clearnet"),
    }
    (INVESTIGATIONS_DIR / fname).write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return fname


def load_investigations() -> list[dict]:
    if not INVESTIGATIONS_DIR.exists():
        return []
    items = []
    for path in sorted(INVESTIGATIONS_DIR.glob("investigation_*.json"), reverse=True):
        try:
            data = json.loads(path.read_text())
            data["_filename"] = path.name
            items.append(data)
        except Exception:
            continue
    return items


def build_followup_context(inv: dict, char_budget: int = 12000) -> str:
    parts = [
        f"ORIGINAL QUERY: {inv.get('query', '')}",
        f"REFINED QUERY: {inv.get('refined_query') or inv.get('refined', '')}",
    ]
    sources = inv.get("sources") or []
    if sources:
        parts.append(
            "SOURCES:\n"
            + "\n".join(f"- {s.get('title', 'Untitled')} ({s.get('link', '')})" for s in sources)
        )
    if inv.get("summary"):
        parts.append("INVESTIGATION SUMMARY:\n" + str(inv["summary"]))
    scraped = inv.get("scraped")
    if scraped:
        raw = scraped if isinstance(scraped, str) else "\n\n".join(str(x) for x in scraped.values())
        if len(raw) > char_budget:
            raw = raw[:char_budget] + "\n\n[...truncated...]"
        parts.append("RAW SCRAPED CONTENT:\n" + raw)
    return "\n\n".join(parts)


def answer_followup(model: str | None, question: str, inv: dict, history=None) -> str:
    system = (
        "You are a Cybercrime Threat Intelligence Expert answering follow-up "
        "questions about a completed dark-web OSINT investigation.\n"
        "STRICT GROUNDING: Answer ONLY from the INVESTIGATION CONTEXT. "
        "If the answer is not there, say so. Be concise.\n"
        f"INVESTIGATION CONTEXT:\n{build_followup_context(inv)}"
    )
    text = llm_bridge.chat(model, system, question, history=history)
    if text:
        return text
    return "Sem LLM configurado — releia o relatório em Findings. Não invento artefatos."


def suggest_pivots(model: str | None, query: str, scraped: dict, max_pivots: int = 5) -> list[str]:
    raw = scraped if isinstance(scraped, str) else "\n\n".join(str(x) for x in (scraped or {}).values())
    system = (
        "Propose concise follow-up SEARCH QUERIES (5 words or fewer, no AND/OR) "
        f"grounded in the investigation data. Output ONLY a JSON array of 1 to {max_pivots} strings."
    )
    text = llm_bridge.chat(model, system, f"QUERY: {query}\nDATA:\n{raw[:8000]}")
    if not text:
        return []
    blob = text.strip()
    if blob.startswith("```"):
        blob = re.sub(r"^```[a-zA-Z]*\n?", "", blob).rstrip("`").strip()
    match = re.search(r"\[.*\]", blob, re.DOTALL)
    if not match:
        return []
    try:
        pivots = json.loads(match.group(0))
    except Exception:
        return []
    if not isinstance(pivots, list):
        return []
    return [p.strip() for p in pivots if isinstance(p, str) and p.strip()][:max_pivots]
