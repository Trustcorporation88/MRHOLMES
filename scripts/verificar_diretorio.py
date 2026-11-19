"""
Confere se cada fonte do diretório está de pé.

    python scripts/verificar_diretorio.py            # tabela no terminal
    python scripts/verificar_diretorio.py --json     # para guardar ou comparar

Site: uma requisição ao endereço da fonte. 401, 403 e 429 contam como "vivo"
(o site existe e barra robô; no navegador abre). 404, 5xx e falha de DNS
reprovam. Repositório do GitHub: existe, não está arquivado e quando teve o
último commit (via `gh api`, se o gh estiver instalado).

Sai com código 1 se alguma fonte reprovar, para poder rodar em CI ou cron.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from holmes.diretorio import DIRETORIO  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
EXEMPLO = {"{q}": "teste", "{d}": "11999999999"}
VIVO_MAS_BARRA_ROBO = {401, 403, 405, 406, 429, 451, 464, 999}


def _url_de_teste(fonte) -> str:
    if fonte.exemplo:
        return fonte.link(fonte.exemplo)
    url = fonte.url
    for marca, valor in EXEMPLO.items():
        url = url.replace(marca, valor)
    return url


def _github(repo: str) -> tuple[bool, str]:
    if not shutil.which("gh"):
        return _site(f"https://github.com/{repo}")
    try:
        r = subprocess.run(["gh", "api", f"repos/{repo}", "--jq",
                            "[.archived, .stargazers_count, .pushed_at] | @tsv"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"gh falhou: {exc}"
    if r.returncode != 0:
        return False, (r.stderr or "não encontrado").strip().splitlines()[-1][:80]
    arquivado, estrelas, push = (r.stdout.strip().split("\t") + ["", "", ""])[:3]
    if arquivado == "true":
        return False, f"arquivado ({estrelas} estrelas)"
    return True, f"{estrelas} estrelas, último commit {push[:10]}"


def _site(url: str) -> tuple[bool, str]:
    erro = ""
    for tentativa in range(2):
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"},
                             timeout=25, allow_redirects=True, stream=True)
            r.close()
            if r.status_code < 400:
                return True, f"HTTP {r.status_code}"
            if r.status_code in VIVO_MAS_BARRA_ROBO:
                return True, f"HTTP {r.status_code} (barra robô; abre no navegador)"
            erro = f"HTTP {r.status_code}"
            if r.status_code < 500:
                break
        except requests.exceptions.SSLError:
            # Vários sites do governo usam cadeia de certificado que o Python
            # não reconhece. O navegador abre; aqui só interessa se está de pé.
            try:
                r = requests.get(url, headers={"User-Agent": UA}, timeout=25, verify=False, stream=True)
                r.close()
                if r.status_code < 400 or r.status_code in VIVO_MAS_BARRA_ROBO:
                    return True, f"HTTP {r.status_code} (certificado fora da cadeia padrão)"
                erro = f"HTTP {r.status_code}"
            except requests.exceptions.SSLError:
                # O servidor respondeu ao aperto de mão: está de pé, só usa
                # TLS antigo que o Python recusa e o navegador aceita.
                return True, "TLS antigo (abre no navegador)"
            except requests.RequestException as exc:
                erro = type(exc).__name__
        except requests.RequestException as exc:
            erro = type(exc).__name__
    return False, erro or "sem resposta"


def verificar(fonte) -> dict:
    url = _url_de_teste(fonte)
    if url.startswith("https://github.com/") and url.count("/") == 4:
        ok, nota = _github(url.split("github.com/")[1])
    else:
        ok, nota = _site(url)
    return {"nome": fonte.nome, "url": url, "ok": ok, "nota": nota}


def main() -> int:
    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
    itens = [(cat, f) for cat, _, fontes in DIRETORIO for f in fontes]
    with ThreadPoolExecutor(max_workers=12) as pool:
        resultados = list(pool.map(lambda par: {"categoria": par[0], **verificar(par[1])}, itens))
    reprovadas = [r for r in resultados if not r["ok"]]
    if "--json" in sys.argv:
        print(json.dumps(resultados, ensure_ascii=False, indent=1))
    else:
        for r in resultados:
            print(f"{'OK  ' if r['ok'] else 'FALHA'} {r['categoria'][:22]:22} {r['nome'][:42]:42} {r['nota']}")
        print(f"\n{len(resultados) - len(reprovadas)} de {len(resultados)} fontes de pé; "
              f"{len(reprovadas)} reprovada(s).")
    return 1 if reprovadas else 0


if __name__ == "__main__":
    sys.exit(main())
