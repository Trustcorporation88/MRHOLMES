"""
Camada HTTP e de chaves.

Um único lugar que sabe: onde estão as chaves, como fazer uma requisição
educada (timeout, retry, user-agent) e como cachear em disco. Conector
nenhum chama `requests` direto.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CACHE_DIR = Path(os.environ.get("HOLMES_CACHE_DIR", ".holmes_cache"))
DEFAULT_TTL = int(os.environ.get("HOLMES_CACHE_TTL", "86400"))  # 24h
DEFAULT_TIMEOUT = 12

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

# Nome canônico → variações aceitas no ambiente / na sidebar.
_KEY_ALIASES = {
    "serper": ("SERPER_API_KEY", "SERPER_KEY"),
    "brave": ("BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY"),
    "google_cse": ("GOOGLE_CSE_KEY", "GOOGLE_API_KEY"),
    "google_cse_cx": ("GOOGLE_CSE_CX", "GOOGLE_CX"),
    "hibp": ("HIBP_API_KEY",),
    "hunter": ("HUNTER_API_KEY",),
    "numverify": ("NUMVERIFY_API_KEY",),
    "shodan": ("SHODAN_API_KEY",),
    "ipinfo": ("IPINFO_TOKEN", "IPINFO_API_KEY"),
    "osintleak": ("OSINTLEAK_API_KEY",),
    "portal_transparencia": ("PORTAL_TRANSPARENCIA_KEY", "PORTAL_TRANSPARENCIA_API_KEY"),
    "opensanctions": ("OPENSANCTIONS_API_KEY",),
    "leakcheck": ("LEAKCHECK_API_KEY",),
    "dehashed_user": ("DEHASHED_USER", "DEHASHED_EMAIL"),
    "dehashed_key": ("DEHASHED_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
    "brightdata": ("BRIGHTDATA_API_KEY", "BRIGHT_DATA_API_KEY", "BRD_API_KEY"),
    "github": ("HOLMES_GITHUB_TOKEN",),
}

# Chaves coladas na UI nesta sessão (não persistem em disco).
_RUNTIME_KEYS: dict[str, str] = {}


def set_runtime_key(name: str, value: str | None) -> None:
    """A sidebar cola a chave aqui; vale só para o processo em execução."""
    if value and value.strip():
        _RUNTIME_KEYS[name] = value.strip()
    else:
        _RUNTIME_KEYS.pop(name, None)


def get_key(name: str) -> str | None:
    if name in _RUNTIME_KEYS:
        return _RUNTIME_KEYS[name]
    for env_name in _KEY_ALIASES.get(name, (name.upper(),)):
        val = os.environ.get(env_name, "").strip()
        if val:
            return val
    return None


def has_key(name: str) -> bool:
    return bool(get_key(name))


def key_status() -> dict[str, bool]:
    """Usado pela UI para mostrar a bolinha acesa/apagada de cada provedor."""
    return {name: has_key(name) for name in _KEY_ALIASES}


# ── cache em disco ──────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{digest}.json"


def cache_get(key: str, ttl: int = DEFAULT_TTL) -> Any | None:
    if ttl <= 0:
        return None
    path = _cache_path(key)
    try:
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > ttl:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def cache_set(key: str, value: Any) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(key).write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass  # cache é otimização, nunca motivo de falha


def cache_clear() -> int:
    removed = 0
    try:
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
            removed += 1
    except Exception:
        pass
    return removed


# ── sessão HTTP ─────────────────────────────────────────────────────────────

def build_session(retries: int = 2) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )
    return session


_SESSION = build_session()


def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    ttl: int = DEFAULT_TTL,
) -> Any | None:
    ck = f"GET:{url}:{json.dumps(params or {}, sort_keys=True)}"
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached
    resp = _SESSION.get(url, params=params, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        raise requests.HTTPError(f"HTTP {resp.status_code} em {url}", response=resp)
    data = resp.json()
    cache_set(ck, data)
    return data


def post_json(
    url: str,
    *,
    payload: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    ttl: int = DEFAULT_TTL,
) -> Any | None:
    ck = f"POST:{url}:{json.dumps(payload or {}, sort_keys=True)}"
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached
    resp = _SESSION.post(url, json=payload, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        raise requests.HTTPError(f"HTTP {resp.status_code} em {url}", response=resp)
    data = resp.json()
    cache_set(ck, data)
    return data


def get_text(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    ttl: int = DEFAULT_TTL,
) -> str | None:
    ck = f"TXT:{url}:{json.dumps(params or {}, sort_keys=True)}"
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached
    resp = _SESSION.get(url, params=params, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        return None
    cache_set(ck, resp.text)
    return resp.text


def head_status(url: str, timeout: int = 8) -> int | None:
    """Existe esse perfil? Alguns sites respondem 404 no HEAD e 200 no GET."""
    try:
        resp = _SESSION.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code in (403, 405):
            resp = _SESSION.get(url, timeout=timeout, allow_redirects=True, stream=True)
        return resp.status_code
    except Exception:
        return None


# ── GitHub: token opcional ──────────────────────────────────────────────────
#
# Sem token a API do GitHub dá 60 requisições/hora por IP; com token, 5.000.
# É o maior ganho gratuito do motor, e por isso vale um helper próprio.
#
# Cuidado deliberado com o nome da variável: `GITHUB_TOKEN` e `GH_TOKEN` são
# usadas por CI, por agentes e por proxies corporativos para guardar *outros*
# tokens. Mandar um desses para api.github.com vaza credencial de terceiro e
# ainda quebra o conector com 401. Então a variável canônica é
# HOLMES_GITHUB_TOKEN, e as genéricas só são aceitas se o valor tiver mesmo
# cara de token do GitHub.

_GITHUB_TOKEN_PREFIXES = ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_")


def github_token() -> str | None:
    explicit = get_key("github")
    if explicit:
        return explicit
    for env_name in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(env_name, "").strip()
        if val.startswith(_GITHUB_TOKEN_PREFIXES):
            return val
    return None


# Vira True no primeiro 401: token vencido, revogado ou digitado errado.
# A partir daí o processo segue sem token (60/h) em vez de falhar toda
# consulta ao GitHub até alguém notar e redeployar.
_github_token_rejected = False


def github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = github_token()
    if token and not _github_token_rejected:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_auth_state() -> str:
    """Para a UI e para o log: `sem_token`, `ativo` ou `recusado`."""
    if not github_token():
        return "sem_token"
    return "recusado" if _github_token_rejected else "ativo"


def github_get_json(url: str, *, timeout: int = DEFAULT_TIMEOUT, ttl: int = DEFAULT_TTL) -> Any | None:
    """
    GET na API do GitHub com o token, se houver. Se o GitHub recusar o token
    (401), repete a mesma chamada sem ele e desliga o token para o resto do
    processo. Um token vencido derruba a cota de 5.000/h para 60/h, mas não
    derruba o conector.
    """
    global _github_token_rejected
    try:
        return get_json(url, headers=github_headers(), timeout=timeout, ttl=ttl)
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status != 401 or _github_token_rejected or not github_token():
            raise
        _github_token_rejected = True
        print(
            "[holmes] GitHub recusou HOLMES_GITHUB_TOKEN (401: vencido, revogado "
            "ou inválido). Seguindo sem token, limite de 60 req/h. "
            "Gere um novo em github.com/settings/tokens.",
            file=sys.stderr,
            flush=True,
        )
        return get_json(url, headers=github_headers(), timeout=timeout, ttl=ttl)


# ── Bright Data Web Unlocker ────────────────────────────────────────────────
#
# Rota paga, desligada por padrão. Só entra em ação quando o alvo bloqueia de
# verdade (403/429/captcha) — nunca como caminho principal, porque cada
# requisição custa dinheiro e a esmagadora maioria das fontes do motor
# responde bem direto.
#
# Ligar:
#   export BRIGHTDATA_API_KEY=...     # a chave, nunca no código
#   export HOLMES_UNLOCKER=1          # o interruptor
#   export HOLMES_UNLOCKER_ZONE=...   # opcional (padrão: cli_unlocker)
#   export HOLMES_UNLOCKER_BUDGET=200 # teto de chamadas por processo

UNLOCKER_ENDPOINT = "https://api.brightdata.com/request"
UNLOCKER_ZONE = os.environ.get("HOLMES_UNLOCKER_ZONE", "cli_unlocker")
UNLOCKER_BUDGET = int(os.environ.get("HOLMES_UNLOCKER_BUDGET", "200"))
UNLOCKER_TIMEOUT = int(os.environ.get("HOLMES_UNLOCKER_TIMEOUT", "60"))

# Contadores do processo. O teto existe porque o crédito é finito e um laço
# mal fechado num motor que roda 90 sites em paralelo queima saldo rápido.
_unlocker_stats = {"usadas": 0, "sucesso": 0, "falha": 0, "bloqueadas_por_teto": 0}


def unlocker_enabled() -> bool:
    """Só é verdade com chave presente E interruptor ligado. Na dúvida, não gasta."""
    if os.environ.get("HOLMES_UNLOCKER", "").strip().lower() not in ("1", "true", "sim", "on"):
        return False
    return has_key("brightdata")


def unlocker_budget_left() -> int:
    return max(0, UNLOCKER_BUDGET - _unlocker_stats["usadas"])


def unlocker_stats() -> dict:
    """Usado pela UI e pelos relatórios: quanto desta investigação foi pago."""
    return dict(_unlocker_stats, teto=UNLOCKER_BUDGET, restante=unlocker_budget_left())


def unlocker_reset_stats() -> None:
    for k in ("usadas", "sucesso", "falha", "bloqueadas_por_teto"):
        _unlocker_stats[k] = 0


class UnlockerError(RuntimeError):
    """O Unlocker respondeu, mas não entregou a página (bloqueio, KYC, cota)."""


# Respostas que chegam com HTTP 200 mas não são a página pedida. Sem isto o
# extrator lê "Acesso Bloqueado" como se fosse um resultado vazio.
_UNLOCKER_BLOQUEIOS = (
    ("Residential Failed", "a Bright Data exige verificação KYC da conta para este site"),
    ("bad_endpoint", "a Bright Data exige verificação KYC da conta para este site"),
    ("Acesso Bloqueado", "o site bloqueia acesso por proxy"),
    ("atingiu o limite de consultas", "o site limitou as consultas"),
)


def unlocked_fetch(
    url: str,
    *,
    timeout: int | None = None,
    ttl: int = DEFAULT_TTL,
    country: str | None = None,
    data_format: str | None = None,
) -> str:
    """
    Busca a página pelo Web Unlocker. `data_format="markdown"` pede a página já
    convertida, que é o formato que os extratores do motor leem.

    Levanta `UnlockerError` quando não há página (desligado, teto, bloqueio),
    para o conector aparecer em «fontes que não responderam» com o motivo.
    """
    if not unlocker_enabled():
        raise UnlockerError("Web Unlocker desligado (BRIGHTDATA_API_KEY e HOLMES_UNLOCKER=1)")

    ck = f"UNLOCK:{url}:{country or ''}:{data_format or ''}"
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached

    if unlocker_budget_left() <= 0:
        _unlocker_stats["bloqueadas_por_teto"] += 1
        raise UnlockerError(f"teto de {UNLOCKER_BUDGET} chamadas do Unlocker atingido neste processo")

    payload: dict[str, Any] = {"zone": UNLOCKER_ZONE, "url": url, "format": "raw"}
    if country:
        payload["country"] = country
    if data_format:
        payload["data_format"] = data_format

    _unlocker_stats["usadas"] += 1
    try:
        resp = _SESSION.post(
            UNLOCKER_ENDPOINT,
            json=payload,
            headers={
                "Authorization": f"Bearer {get_key('brightdata')}",
                "Content-Type": "application/json",
            },
            timeout=timeout or UNLOCKER_TIMEOUT,
        )
    except Exception as exc:
        _unlocker_stats["falha"] += 1
        raise UnlockerError(f"Unlocker não respondeu: {exc}") from exc

    corpo = resp.text or ""
    if resp.status_code >= 400:
        _unlocker_stats["falha"] += 1
        motivo = resp.headers.get("x-brd-error") or corpo[:160]
        for marca, texto in _UNLOCKER_BLOQUEIOS:
            if marca in motivo:
                motivo = texto
                break
        raise UnlockerError(f"Unlocker HTTP {resp.status_code}: {motivo}")
    cabeca = corpo[:600]
    for marca, texto in _UNLOCKER_BLOQUEIOS:
        if marca in cabeca:
            _unlocker_stats["falha"] += 1
            raise UnlockerError(texto)

    _unlocker_stats["sucesso"] += 1
    cache_set(ck, corpo)
    return corpo


def unlocked_get_text(
    url: str,
    *,
    timeout: int | None = None,
    ttl: int = DEFAULT_TTL,
    country: str | None = None,
) -> str | None:
    """Versão tolerante: devolve o HTML ou None. Usada pelo WhatsMyName."""
    try:
        return unlocked_fetch(url, timeout=timeout, ttl=ttl, country=country)
    except UnlockerError:
        return None


# ── Bright Data SERP API ────────────────────────────────────────────────────
#
# A busca de superfície é o que mais pesa na qualidade do dossiê de nome, CPF
# e CNPJ, e é justamente o que Google, DDG e Mojeek bloqueiam em IP de
# datacenter. A SERP API da Bright Data devolve o resultado do Google já em
# JSON, pelo mesmo endpoint e pela mesma chave do Web Unlocker; só muda a zona.
#
# Ligar (a zona precisa existir no painel, do tipo "SERP API"):
#   export BRIGHTDATA_API_KEY=...
#   export HOLMES_BRD_SERP_ZONE=serp_api1   # nome da zona no painel
#   export HOLMES_BRD_SERP_BUDGET=500       # teto de buscas por processo

BRD_SERP_ZONE = os.environ.get("HOLMES_BRD_SERP_ZONE", "").strip()
BRD_SERP_BUDGET = int(os.environ.get("HOLMES_BRD_SERP_BUDGET", "500"))

_brd_serp_stats = {"usadas": 0, "sucesso": 0, "falha": 0, "bloqueadas_por_teto": 0}


def brd_serp_enabled() -> bool:
    return bool(BRD_SERP_ZONE) and has_key("brightdata")


def brd_serp_stats() -> dict:
    return dict(_brd_serp_stats, teto=BRD_SERP_BUDGET,
                restante=max(0, BRD_SERP_BUDGET - _brd_serp_stats["usadas"]))


def brd_serp_json(
    google_url: str,
    *,
    timeout: int | None = None,
    ttl: int = DEFAULT_TTL,
) -> dict | None:
    """
    Manda uma URL de busca do Google pela zona SERP e devolve o JSON parseado
    (`brd_json=1`). Cacheia como o resto da camada: repetir a mesma busca
    dentro do TTL não gasta crédito. Falha de rede ou de cota levanta erro,
    para o conector aparecer em «fontes que não responderam».
    """
    if not brd_serp_enabled():
        return None
    sep = "&" if "?" in google_url else "?"
    url = google_url if "brd_json=" in google_url else f"{google_url}{sep}brd_json=1"

    ck = f"BRDSERP:{url}"
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached

    if _brd_serp_stats["usadas"] >= BRD_SERP_BUDGET:
        _brd_serp_stats["bloqueadas_por_teto"] += 1
        raise RuntimeError(f"teto de {BRD_SERP_BUDGET} buscas Bright Data atingido neste processo")

    _brd_serp_stats["usadas"] += 1
    try:
        resp = _SESSION.post(
            UNLOCKER_ENDPOINT,
            json={"zone": BRD_SERP_ZONE, "url": url, "format": "raw"},
            headers={
                "Authorization": f"Bearer {get_key('brightdata')}",
                "Content-Type": "application/json",
            },
            timeout=timeout or UNLOCKER_TIMEOUT,
        )
    except Exception:
        _brd_serp_stats["falha"] += 1
        raise
    if resp.status_code >= 400:
        _brd_serp_stats["falha"] += 1
        raise requests.HTTPError(f"Bright Data SERP HTTP {resp.status_code}", response=resp)
    try:
        data = resp.json()
    except ValueError:
        _brd_serp_stats["falha"] += 1
        raise RuntimeError("Bright Data SERP devolveu HTML em vez de JSON (zona sem brd_json?)")
    _brd_serp_stats["sucesso"] += 1
    cache_set(ck, data)
    return data


# ── Bright Data Web Scraper API (coletores prontos) ─────────────────────────
#
# LinkedIn e Instagram exigem login para mostrar perfil. Os coletores prontos
# da Bright Data devolvem o perfil já estruturado (nome, cargo, empresa,
# seguidores, bio) a partir da URL. É cobrado por registro, então fica atrás
# de um interruptor próprio e de um teto por processo.
#
#   export HOLMES_BRD_DATASETS=1
#   export HOLMES_BRD_DATASETS_BUDGET=40

DATASETS_ENDPOINT = "https://api.brightdata.com/datasets/v3"
DATASETS_BUDGET = int(os.environ.get("HOLMES_BRD_DATASETS_BUDGET", "40"))
DATASETS_WAIT = int(os.environ.get("HOLMES_BRD_DATASETS_WAIT", "75"))

# IDs públicos dos coletores (os mesmos que o painel mostra em Web Scrapers).
DATASET_IDS = {
    "linkedin_person": os.environ.get("HOLMES_BRD_DS_LINKEDIN", "gd_l1viktl72bvl7bjuj0"),
    "linkedin_company": os.environ.get("HOLMES_BRD_DS_LINKEDIN_CO", "gd_l1vikfnt1wgvvqz95w"),
    "instagram_profile": os.environ.get("HOLMES_BRD_DS_INSTAGRAM", "gd_l1vikfch901nx3by4"),
}

_datasets_stats = {"usadas": 0, "sucesso": 0, "falha": 0, "bloqueadas_por_teto": 0}


def datasets_enabled() -> bool:
    if os.environ.get("HOLMES_BRD_DATASETS", "").strip().lower() not in ("1", "true", "sim", "on"):
        return False
    return has_key("brightdata")


def datasets_stats() -> dict:
    return dict(_datasets_stats, teto=DATASETS_BUDGET,
                restante=max(0, DATASETS_BUDGET - _datasets_stats["usadas"]))


def brd_dataset_scrape(dataset: str, url: str, *, ttl: int = 7 * 86400) -> dict | None:
    """
    Um registro de um coletor pronto. Tenta o modo síncrono (/scrape); se a
    coleta passar do tempo dele, acompanha o snapshot até DATASETS_WAIT
    segundos. Devolve o primeiro registro, ou None se o perfil não existe.
    """
    if not datasets_enabled():
        raise RuntimeError("coletores Bright Data desligados (HOLMES_BRD_DATASETS=1)")
    dataset_id = DATASET_IDS.get(dataset, dataset)

    ck = f"BRDDS:{dataset_id}:{url}"
    cached = cache_get(ck, ttl)
    if cached is not None:
        return cached or None

    if _datasets_stats["usadas"] >= DATASETS_BUDGET:
        _datasets_stats["bloqueadas_por_teto"] += 1
        raise RuntimeError(f"teto de {DATASETS_BUDGET} coletas Bright Data atingido neste processo")

    headers = {
        "Authorization": f"Bearer {get_key('brightdata')}",
        "Content-Type": "application/json",
    }
    _datasets_stats["usadas"] += 1
    try:
        resp = _SESSION.post(
            f"{DATASETS_ENDPOINT}/scrape",
            params={"dataset_id": dataset_id, "format": "json", "include_errors": "true"},
            json={"input": [{"url": url}]},
            headers=headers,
            timeout=DATASETS_WAIT,
        )
        if resp.status_code == 202:
            snapshot = (resp.json() or {}).get("snapshot_id")
            if not snapshot:
                raise RuntimeError("coleta aceita sem snapshot_id")
            data = _dataset_wait(snapshot, headers)
        elif resp.status_code >= 400:
            raise requests.HTTPError(
                f"Bright Data coletor HTTP {resp.status_code}: {resp.text[:160]}", response=resp)
        else:
            data = _json_or_lines(resp.text)
    except Exception:
        _datasets_stats["falha"] += 1
        raise

    registros = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    registro = next((r for r in registros if isinstance(r, dict) and not r.get("error")), None)
    if registro is None and registros and isinstance(registros[0], dict) and registros[0].get("error"):
        erro = str(registros[0].get("error"))
        # Perfil inexistente é resposta, não falha: cacheia o vazio.
        if "not found" in erro.lower() or "dead_page" in erro.lower() or "404" in erro:
            _datasets_stats["sucesso"] += 1
            cache_set(ck, {})
            return None
        _datasets_stats["falha"] += 1
        raise RuntimeError(f"coletor devolveu erro: {erro[:160]}")
    _datasets_stats["sucesso"] += 1
    cache_set(ck, registro or {})
    return registro


def _json_or_lines(texto: str):
    texto = (texto or "").strip()
    if not texto:
        return []
    try:
        return json.loads(texto)
    except ValueError:
        # Alguns coletores respondem NDJSON (um registro por linha).
        return [json.loads(linha) for linha in texto.splitlines() if linha.strip()]


def _dataset_wait(snapshot: str, headers: dict):
    limite = time.time() + DATASETS_WAIT
    while time.time() < limite:
        prog = _SESSION.get(f"{DATASETS_ENDPOINT}/progress/{snapshot}", headers=headers, timeout=20)
        status = (prog.json() or {}).get("status") if prog.status_code < 400 else None
        if status == "ready":
            snap = _SESSION.get(f"{DATASETS_ENDPOINT}/snapshot/{snapshot}",
                                params={"format": "json"}, headers=headers, timeout=30)
            if snap.status_code >= 400:
                raise requests.HTTPError(f"snapshot HTTP {snap.status_code}", response=snap)
            return _json_or_lines(snap.text)
        if status == "failed":
            raise RuntimeError("coleta falhou no lado da Bright Data")
        time.sleep(3)
    raise TimeoutError(f"coleta não ficou pronta em {DATASETS_WAIT}s (snapshot {snapshot})")
