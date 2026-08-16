"""Investigação prática: um alvo → fontes públicas + OpenAI web_search."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Optional
from urllib.parse import quote_plus, quote

import requests

from Core.Support.Robin import llm_bridge

_UA = {"User-Agent": "MrHolmes-OSINT/1.0 (educational; authorized targets)"}


def classify_target(raw: str) -> str:
    q = (raw or "").strip()
    if not q:
        return "empty"
    if re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", q):
        return "email"
    digits = re.sub(r"\D", "", q)
    if 10 <= len(digits) <= 15 and re.fullmatch(r"[\d+\s().-]+", q):
        return "phone"
    if " " not in q and re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,24}$", q):
        return "domain"
    if " " not in q and re.match(r"^@?[A-Za-z0-9_.-]{2,32}$", q):
        return "username"
    return "person"


def official_links(query: str, kind: str) -> list[dict]:
    q = quote_plus(query.strip())
    handle = quote_plus(query.strip().lstrip("@").split()[0])
    links = [
        {"name": "Google", "url": f"https://www.google.com/search?q={q}"},
        {"name": "DuckDuckGo", "url": f"https://duckduckgo.com/?q={q}"},
        {"name": "WhatsMyName", "url": f"https://whatsmyname.app/"},
        {"name": "OpenCorporates", "url": f"https://opencorporates.com/companies?q={q}"},
        {"name": "OCCRP Aleph", "url": f"https://aleph.occrp.org/search?q={q}"},
    ]
    if kind in ("username", "person"):
        links.insert(2, {"name": "Namechk", "url": "https://namechk.com/"})
        links.insert(2, {"name": "Epieos", "url": "https://epieos.com/"})
    if kind == "email":
        links.insert(0, {"name": "Have I Been Pwned", "url": f"https://haveibeenpwned.com/account/{quote(query.strip())}"})
        links.insert(1, {"name": "Epieos", "url": "https://epieos.com/"})
    if kind == "username":
        links.insert(0, {"name": "GitHub", "url": f"https://github.com/{handle}"})
    return links


def _get_json(url: str, timeout: int = 8) -> Optional[dict | list]:
    try:
        resp = requests.get(url, headers=_UA, timeout=timeout)
        if resp.status_code >= 400:
            return None
        return resp.json()
    except Exception:
        return None


def _wikipedia(query: str) -> dict:
    out = {"ok": False, "hits": []}
    for lang in ("pt", "en"):
        data = _get_json(
            "https://" + lang + ".wikipedia.org/w/api.php"
            f"?action=opensearch&search={quote_plus(query)}&limit=3&namespace=0&format=json"
        )
        if not isinstance(data, list) or len(data) < 4:
            continue
        titles, descs, urls = data[1], data[2], data[3]
        for title, desc, url in zip(titles, descs, urls):
            out["hits"].append({"title": title, "desc": desc, "url": url, "lang": lang})
            out["ok"] = True
        if out["hits"]:
            break
    return out


def _github_users(query: str) -> dict:
    token = query.strip().lstrip("@").split()[0]
    data = _get_json(f"https://api.github.com/search/users?q={quote_plus(token)}&per_page=5")
    items = (data or {}).get("items") if isinstance(data, dict) else None
    users = []
    for item in items or []:
        users.append(
            {
                "login": item.get("login"),
                "url": item.get("html_url"),
                "type": item.get("type"),
            }
        )
    return {"ok": bool(users), "users": users}


def _ddg(query: str) -> dict:
    data = _get_json(
        f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
    )
    if not isinstance(data, dict):
        return {"ok": False}
    related = []
    for item in (data.get("RelatedTopics") or [])[:6]:
        if isinstance(item, dict) and item.get("FirstURL"):
            related.append({"title": (item.get("Text") or "")[:160], "url": item["FirstURL"]})
    return {
        "ok": bool(data.get("Abstract") or related),
        "heading": data.get("Heading") or "",
        "abstract": data.get("Abstract") or "",
        "url": data.get("AbstractURL") or "",
        "related": related,
    }


def _email_pack(email: str) -> dict:
    try:
        from Core.Support.EmailSearch import buscar_email

        return {"ok": True, **buscar_email(email)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def _phone_pack(raw: str) -> dict:
    try:
        import phonenumbers as pn
        from phonenumbers import carrier, geocoder

        try:
            num = pn.parse(raw, None)
        except Exception:
            num = pn.parse(raw, "BR")
        return {
            "ok": pn.is_possible_number(num),
            "e164": pn.format_number(num, pn.PhoneNumberFormat.E164),
            "country": geocoder.description_for_number(num, "pt") or "",
            "carrier": carrier.name_for_number(num, "pt") or "",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:160]}


def _username_pack(username: str) -> dict:
    try:
        from Core.Support.OsintTools import run_maigret

        return run_maigret(username.lstrip("@"), max_sites=12)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "profiles": []}


def _evidence_blob(kind: str, packs: dict) -> str:
    return json.dumps({"kind": kind, **packs}, ensure_ascii=False, default=str)[:8000]


def _web_prompt(query: str, kind: str, packs: dict) -> str:
    return (
        "Investigação OSINT educacional de alvo autorizado. "
        "Busque apenas fontes abertas (perfis públicos, notícias, registros, GitHub, Wikipedia). "
        "Não invente dados. Não oriente hacking, phishing, acesso não autorizado ou compra de leaks.\n\n"
        f"Tipo detectado: {kind}\nAlvo: {query}\n\n"
        f"Evidências locais já coletadas (JSON):\n{_evidence_blob(kind, packs)}\n\n"
        "Responda em português, Markdown:\n"
        "## Resumo\n## Identificadores\n## Presença pública (URLs)\n"
        "## O que NÃO foi confirmado\n## Próximos passos lícitos\n"
    )


def run_name_investigation(query: str, model: str = "gpt-4o-mini") -> dict:
    q = (query or "").strip()
    kind = classify_target(q)
    if kind == "empty":
        return {"ok": False, "error": "Informe um nome, username, email ou domínio."}

    packs: dict = {}
    jobs = {
        "wikipedia": lambda: _wikipedia(q),
        "github": lambda: _github_users(q),
        "ddg": lambda: _ddg(q),
    }
    if kind == "email":
        jobs["email"] = lambda: _email_pack(q)
    elif kind == "phone":
        jobs["phone"] = lambda: _phone_pack(q)
    elif kind == "username":
        jobs["maigret"] = lambda: _username_pack(q)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(fn): name for name, fn in jobs.items()}
        done, pending = wait(futs, timeout=50)
        for fut in done:
            name = futs[fut]
            try:
                packs[name] = fut.result()
            except Exception as exc:
                packs[name] = {"ok": False, "error": str(exc)[:160]}
        for fut in pending:
            packs[futs[fut]] = {"ok": False, "error": "timeout"}

    web = llm_bridge.openai_web_search(_web_prompt(q, kind, packs), model=model)
    dossier = (web.get("text") or "").strip()
    if not dossier:
        dossier = llm_bridge.chat(
            model,
            "Analista OSINT. Só use as evidências. Português. Markdown. Sem conselhos ilegais.",
            _web_prompt(q, kind, packs),
        )
    if not dossier:
        dossier = _fallback_dossier(q, kind, packs)

    citations = list(web.get("citations") or [])
    for hit in (packs.get("wikipedia") or {}).get("hits") or []:
        citations.append({"title": hit.get("title") or "Wikipedia", "url": hit.get("url")})
    for user in (packs.get("github") or {}).get("users") or []:
        if user.get("url"):
            citations.append({"title": f"GitHub {user.get('login')}", "url": user["url"]})

    try:
        from Core.Support.History import save_search

        save_search("investigate", q, sites_found=len(citations))
    except Exception:
        pass

    return {
        "ok": True,
        "query": q,
        "kind": kind,
        "dossier": dossier,
        "packs": packs,
        "citations": citations,
        "links": official_links(q, kind),
        "web_ok": bool(web.get("ok")),
        "web_error": web.get("error"),
        "llm_error": llm_bridge.last_error(),
        "model": model,
    }


def answer_followup(model: str | None, question: str, inv: dict, history=None) -> str:
    q = (question or "").strip()
    if not q:
        return ""
    context = (
        f"Alvo: {inv.get('query')}\nTipo: {inv.get('kind')}\n\n"
        f"Dossiê:\n{(inv.get('dossier') or '')[:6000]}\n"
    )
    text = llm_bridge.chat(
        model or "gpt-4o-mini",
        "Analista OSINT. Responda só com base no dossiê. Sem conselhos ilegais. Português.",
        f"{context}\nPergunta: {q}",
        history=history,
    )
    return text or "Sem resposta do modelo. Confira OPENAI_API_KEY."


def _fallback_dossier(query: str, kind: str, packs: dict) -> str:
    lines = [
        f"## Resumo\nConsulta local para `{query}` ({kind}). Sem OpenAI web_search nesta rodada.",
        "## Presença pública",
    ]
    for hit in (packs.get("wikipedia") or {}).get("hits") or []:
        lines.append(f"- Wikipedia: [{hit.get('title')}]({hit.get('url')}) — {hit.get('desc') or ''}")
    for user in (packs.get("github") or {}).get("users") or []:
        lines.append(f"- GitHub: [{user.get('login')}]({user.get('url')})")
    for prof in (packs.get("maigret") or {}).get("profiles") or []:
        lines.append(f"- {prof.get('site')}: {prof.get('url')}")
    ddg = packs.get("ddg") or {}
    if ddg.get("abstract"):
        lines.append(f"- DuckDuckGo: {ddg['abstract'][:400]}")
    if len(lines) == 2:
        lines.append("- Nada confirmado nas APIs públicas desta rodada.")
    lines.append("## Próximos passos lícitos\nUse os atalhos oficiais abaixo (WhatsMyName, Epieos, HIBP).")
    return "\n".join(lines)
