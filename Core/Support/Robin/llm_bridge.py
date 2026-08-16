"""Cliente LLM enxuto (OpenAI-compatível, Anthropic, Gemini, Ollama)."""

from __future__ import annotations

import json
import os
from typing import Optional
from urllib.parse import urljoin

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


_LAST_ERROR: Optional[str] = None


def last_error() -> Optional[str]:
    return _LAST_ERROR


def apply_keys(openai: Optional[str] = None, anthropic: Optional[str] = None) -> None:
    """Aplica chaves da sessão/.env sem gravar no disco."""
    if openai and str(openai).strip() and not str(openai).startswith("your_"):
        os.environ["OPENAI_API_KEY"] = str(openai).strip()
    if anthropic and str(anthropic).strip() and not str(anthropic).startswith("your_"):
        os.environ["ANTHROPIC_API_KEY"] = str(anthropic).strip()
        os.environ.setdefault("CLAUDE_API_KEY", str(anthropic).strip())


def _clean(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if name == "ANTHROPIC_API_KEY" and not value:
        value = os.getenv("CLAUDE_API_KEY", default)
    if value is None:
        return None
    value = str(value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    if not value or value.startswith("your_"):
        return None
    return value


def _is_set(value: Optional[str]) -> bool:
    return bool(value and str(value).strip() and "your_" not in str(value))


def fetch_ollama_models(base: Optional[str] = None) -> list[str]:
    url = (base or _clean("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/") + "/"
    try:
        resp = requests.get(urljoin(url, "api/tags"), timeout=3)
        resp.raise_for_status()
        names = []
        for item in resp.json().get("models", []):
            name = item.get("name") or item.get("model")
            if name:
                names.append(name)
        return names
    except (requests.RequestException, ValueError):
        return []


def list_models() -> list[dict]:
    models = []
    if _is_set(_clean("OPENAI_API_KEY")):
        models.append({"id": "gpt-4o-mini", "label": "[openai] gpt-4o-mini", "provider": "openai"})
        models.append({"id": "gpt-4o", "label": "[openai] gpt-4o", "provider": "openai"})
        models.append({"id": "gpt-4.1", "label": "[openai] gpt-4.1", "provider": "openai"})
    if _is_set(_clean("ANTHROPIC_API_KEY")):
        models.append({"id": "claude-sonnet-4-5", "label": "[anthropic] claude-sonnet-4-5", "provider": "anthropic"})
        models.append({"id": "claude-haiku-4-5", "label": "[anthropic] claude-haiku-4-5", "provider": "anthropic"})
    if _is_set(_clean("GOOGLE_API_KEY")):
        models.append({"id": "gemini-2.5-flash", "label": "[google] gemini-2.5-flash", "provider": "google"})
    if _is_set(_clean("OPENROUTER_API_KEY")):
        models.append({"id": "openrouter/auto", "label": "[openrouter] auto", "provider": "openrouter"})
    custom_url = _clean("CUSTOM_API_BASE_URL")
    custom_model = _clean("CUSTOM_API_MODEL")
    if custom_url and custom_model:
        models.append({"id": f"custom:{custom_model}", "label": f"[custom] {custom_model}", "provider": "custom"})
    for name in fetch_ollama_models():
        models.append({"id": f"ollama:{name}", "label": f"[ollama] {name}", "provider": "ollama"})
    return models


def _openai_chat(base_url: str, api_key: str, model: str, system: str, user: str, history=None) -> str:
    messages = [{"role": "system", "content": system}]
    for turn in history or []:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": turn.get("content", "")})
    messages.append({"role": "user", "content": user})
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    resp = requests.post(
        f"{url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0},
        timeout=90,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {resp.text[:240]}")
    resp.raise_for_status()
    data = resp.json()
    return (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()


def _anthropic_chat(model: str, system: str, user: str, history=None) -> str:
    messages = []
    for turn in history or []:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": turn.get("content", "")})
    messages.append({"role": "user", "content": user})
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": _clean("ANTHROPIC_API_KEY"),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={"model": model, "max_tokens": 2048, "system": system, "messages": messages},
        timeout=90,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Anthropic HTTP {resp.status_code}: {resp.text[:240]}")
    resp.raise_for_status()
    blocks = resp.json().get("content") or []
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


def _gemini_chat(model: str, system: str, user: str, history=None) -> str:
    key = _clean("GOOGLE_API_KEY")
    contents = []
    for turn in history or []:
        role = "model" if turn.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": turn.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": user}]})
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": key},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
        },
        timeout=90,
    )
    resp.raise_for_status()
    cands = resp.json().get("candidates") or []
    parts = (((cands[0] if cands else {}).get("content") or {}).get("parts") or [])
    return "".join(p.get("text", "") for p in parts).strip()


def _ollama_chat(model: str, system: str, user: str, history=None) -> str:
    base = (_clean("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
    messages = [{"role": "system", "content": system}]
    for turn in history or []:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": turn.get("content", "")})
    messages.append({"role": "user", "content": user})
    resp = requests.post(
        f"{base}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return ((resp.json().get("message") or {}).get("content") or "").strip()


def chat(model_id: Optional[str], system: str, user: str, history=None) -> str:
    """Chama o provedor do modelo. Sem modelo/chave → string vazia."""
    global _LAST_ERROR
    _LAST_ERROR = None
    if not model_id:
        return ""
    mid = model_id.strip()
    try:
        if mid.startswith("ollama:"):
            return _ollama_chat(mid.split(":", 1)[1], system, user, history)
        if mid.startswith("custom:"):
            return _openai_chat(
                _clean("CUSTOM_API_BASE_URL") or "",
                _clean("CUSTOM_API_KEY") or "sk-custom",
                mid.split(":", 1)[1],
                system,
                user,
                history,
            )
        if mid.startswith("openrouter/"):
            return _openai_chat(
                _clean("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
                _clean("OPENROUTER_API_KEY") or "",
                "openrouter/auto",
                system,
                user,
                history,
            )
        if mid.startswith("claude"):
            return _anthropic_chat(mid, system, user, history)
        if mid.startswith("gemini"):
            return _gemini_chat(mid, system, user, history)
        if mid.startswith("gpt-"):
            return _openai_chat("https://api.openai.com/v1", _clean("OPENAI_API_KEY") or "", mid, system, user, history)
    except Exception as exc:
        _LAST_ERROR = str(exc)[:400]
        return ""
    return ""


def openai_web_search(
    prompt: str,
    model: str = "gpt-4o",
    *,
    search_context_size: str = "high",
    country: str = "BR",
    force: bool = True,
) -> dict:
    """Responses API + web_search. A chave faz a busca; o usuário não precisa clicar em Google."""
    global _LAST_ERROR
    _LAST_ERROR = None
    key = _clean("OPENAI_API_KEY")
    if not _is_set(key):
        return {"ok": False, "error": "OPENAI_API_KEY ausente", "text": "", "citations": []}

    tool: dict = {"type": "web_search"}
    if country:
        tool["user_location"] = {"type": "approximate", "country": country}
    if search_context_size:
        tool["search_context_size"] = search_context_size

    payload = {
        "model": model or "gpt-4o",
        "tools": [tool],
        "input": prompt,
    }
    if force:
        payload["tool_choice"] = {"type": "web_search"}

    def _post(body: dict):
        resp = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=body,
            timeout=120,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {resp.text[:320]}")
        return resp.json()

    try:
        try:
            data = _post(payload)
        except RuntimeError:
            payload.pop("tool_choice", None)
            if isinstance(payload.get("tools"), list) and payload["tools"]:
                payload["tools"][0].pop("search_context_size", None)
                payload["tools"][0].pop("user_location", None)
            data = _post(payload)
    except Exception as exc:
        _LAST_ERROR = str(exc)[:400]
        return {"ok": False, "error": str(exc)[:320], "text": "", "citations": []}

    text = (data.get("output_text") or "").strip()
    citations = []
    for item in data.get("output") or []:
        if item.get("type") != "message":
            continue
        for block in item.get("content") or []:
            piece = (block.get("text") or "").strip()
            if piece and not text:
                text = piece
            elif piece and piece not in text:
                text = (text + "\n\n" + piece).strip()
            for ann in block.get("annotations") or []:
                url = ann.get("url") or ""
                if url:
                    citations.append({"title": ann.get("title") or url, "url": url})
    seen = set()
    uniq = []
    for c in citations:
        if c["url"] not in seen:
            seen.add(c["url"])
            uniq.append(c)
    return {"ok": bool(text), "text": text, "citations": uniq, "error": None if text else "Resposta vazia"}


def provider_status() -> dict:
    return {
        "openai": _is_set(_clean("OPENAI_API_KEY")),
        "anthropic": _is_set(_clean("ANTHROPIC_API_KEY")),
        "google": _is_set(_clean("GOOGLE_API_KEY")),
        "openrouter": _is_set(_clean("OPENROUTER_API_KEY")),
        "ollama": bool(fetch_ollama_models()),
        "custom": bool(_clean("CUSTOM_API_BASE_URL") and _clean("CUSTOM_API_MODEL")),
    }
