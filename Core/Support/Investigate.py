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


_STOP = {"da", "de", "do", "dos", "das", "e", "the", "of"}


def name_tokens(query: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-zÀ-ÿ0-9]+", query or "") if t.lower() not in _STOP and len(t) > 2]


def looks_like_same_person(text: str, query: str) -> bool:
    tokens = name_tokens(query)
    blob = (text or "").lower()
    if not tokens:
        return False
    if len(tokens) == 1:
        return tokens[0] in blob
    hits = sum(1 for t in tokens if t in blob)
    return hits >= min(3, len(tokens))


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
            if not looks_like_same_person(f"{title} {desc}", query):
                continue
            out["hits"].append({"title": title, "desc": desc, "url": url, "lang": lang})
            out["ok"] = True
        if out["hits"]:
            break
    return out


def _github_users(query: str, kind: str = "username") -> dict:
    q = (query or "").strip().lstrip("@")
    if kind == "person" and " " in q:
        search = f"{q} in:fullname"
    else:
        search = q.split()[0]
    data = _get_json(f"https://api.github.com/search/users?q={quote_plus(search)}&per_page=8")
    items = (data or {}).get("items") if isinstance(data, dict) else None
    users = []
    for item in items or []:
        login = item.get("login") or ""
        url = item.get("html_url") or ""
        detail = _get_json(f"https://api.github.com/users/{quote(login)}") if login else None
        display = (detail or {}).get("name") or login
        hay = f"{login} {display} {url}"
        if kind == "person" and not looks_like_same_person(hay, q):
            continue
        users.append({"login": login, "name": display, "url": url, "type": item.get("type")})
    return {"ok": bool(users), "users": users[:5]}


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


def _search_angles(query: str, kind: str) -> list[tuple[str, str]]:
    quoted = f'"{query.strip()}"'
    rules = (
        "Você É o investigador. A chave OpenAI já está buscando a web. "
        "NÃO diga ao usuário para procurar no Google, LinkedIn, Twitter ou Facebook. "
        "NÃO invente perfis. Homônimos (só o primeiro nome) devem ser descartados. "
        "Para cada achado: URL, o que a página mostra, e confiança alta/média/baixa. "
        "Se a plataforma não aparecer, escreva 'não encontrado nesta busca'. Português.\n\n"
        f"Alvo EXATO: {query}\nTipo: {kind}\n"
    )
    if kind == "email":
        return [
            ("email", rules + f"Busque menções públicas deste email: {query}. Gravatar, GitHub, pastes, páginas pessoais."),
        ]
    if kind == "username":
        return [
            ("handle", rules + f"Busque o handle {quoted} em GitHub, GitLab, redes e sites pessoais."),
        ]
    if kind == "domain":
        return [
            ("dominio", rules + f"Busque o domínio {quoted}: empresa, WHOIS público, notícias, redes sociais oficiais."),
        ]
    return [
        ("identidade", rules + f"Busque {quoted} (Brasil). Quem é, cidade, empresa, notícias, currículo público."),
        ("linkedin", rules + f"Busque o perfil LinkedIn público de {quoted}. Se não houver, diga não encontrado."),
        ("codigo-midia", rules + f"Busque {quoted} no GitHub/GitLab e em notícias/imprensa. Só perfis do nome completo."),
    ]


def _web_prompt(query: str, kind: str, packs: dict) -> str:
    return _search_angles(query, kind)[0][1] + f"\nEvidências locais:\n{_evidence_blob(kind, packs)}"


def _run_web_angles(query: str, kind: str, model: str) -> list[dict]:
    notes = []
    angles = _search_angles(query, kind)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {
            pool.submit(llm_bridge.openai_web_search, prompt, model): label
            for label, prompt in angles
        }
        done, pending = wait(futs, timeout=110)
        for fut in done:
            label = futs[fut]
            try:
                notes.append({"angle": label, **(fut.result() or {})})
            except Exception as exc:
                notes.append({"angle": label, "ok": False, "error": str(exc)[:200], "text": "", "citations": []})
        for fut in pending:
            notes.append({"angle": futs[fut], "ok": False, "error": "timeout", "text": "", "citations": []})
    return notes


def _synthesize(query: str, kind: str, packs: dict, notes: list[dict], model: str) -> str:
    found = "\n\n".join(
        f"### Busca {n.get('angle')}\n{(n.get('text') or n.get('error') or '').strip()}"
        for n in notes
        if (n.get("text") or n.get("error"))
    )
    cites = []
    for n in notes:
        for c in n.get("citations") or []:
            cites.append(f"- {c.get('title')}: {c.get('url')}")
    user = (
        f"Alvo: {query} ({kind})\n\n"
        f"Notas das buscas (já feitas pela API, não pelo usuário):\n{found[:14000]}\n\n"
        f"Citações:\n" + "\n".join(cites[:40]) + "\n\n"
        f"Evidências locais filtradas:\n{_evidence_blob(kind, packs)}\n"
    )
    text = llm_bridge.chat(
        model,
        (
            "Você entrega o dossiê PRONTO. O usuário não vai sair clicando em buscadores. "
            "Português, Markdown:\n"
            "## Resumo\n## Identificadores confirmados\n"
            "## Presença pública (cada item com URL e o que foi visto)\n"
            "## Homônimos descartados\n## Lacunas (o que a busca NÃO achou)\n"
            "Proibido: 'procure no LinkedIn', 'considere buscar', 'próximos passos: pesquise em'. "
            "Se não achou LinkedIn, escreva 'LinkedIn: não encontrado nesta busca'. "
            "Descarte gente que só compartilha o primeiro nome. Não invente."
        ),
        user,
    )
    return (text or "").strip()


def run_name_investigation(query: str, model: str = "gpt-4o") -> dict:
    q = (query or "").strip()
    kind = classify_target(q)
    if kind == "empty":
        return {"ok": False, "error": "Informe um nome, username, email ou domínio."}

    packs: dict = {}
    jobs = {
        "wikipedia": lambda: _wikipedia(q),
    }
    if kind in ("username", "person"):
        jobs["github"] = lambda: _github_users(q, kind)
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

    notes = _run_web_angles(q, kind, model)
    dossier = _synthesize(q, kind, packs, notes, model)
    web_ok = any(n.get("ok") and n.get("text") for n in notes)
    if not dossier:
        dossier = "\n\n".join((n.get("text") or "") for n in notes if n.get("text")).strip()
    if not dossier:
        dossier = _fallback_dossier(q, kind, packs)

    citations = []
    for n in notes:
        citations.extend(n.get("citations") or [])
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
        "links": [],
        "web_ok": web_ok,
        "web_error": next((n.get("error") for n in notes if n.get("error") and not n.get("ok")), None),
        "llm_error": llm_bridge.last_error(),
        "model": model,
        "angles": [n.get("angle") for n in notes],
    }


def answer_followup(model: str | None, question: str, inv: dict, history=None) -> str:
    q = (question or "").strip()
    if not q:
        return ""
    mid = model or "gpt-4o"
    prompt = (
        "Continue a investigação OSINT. Você busca; o usuário não. "
        "Português. Sem 'vá procurar no Google'.\n"
        f"Alvo: {inv.get('query')}\n"
        f"Dossiê já entregue:\n{(inv.get('dossier') or '')[:5000]}\n\n"
        f"Pergunta: {q}"
    )
    web = llm_bridge.openai_web_search(prompt, model=mid)
    if web.get("text"):
        return web["text"]
    return llm_bridge.chat(
        mid,
        "Analista OSINT. Responda com o dossiê. Sem mandar o usuário pesquisar. Português.",
        prompt,
        history=history,
    ) or "Sem resposta do modelo. Confira OPENAI_API_KEY."


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
    lines.append("## Lacunas\nA busca local não achou mais fontes. A OpenAI web_search não respondeu nesta rodada.")
    return "\n".join(lines)
