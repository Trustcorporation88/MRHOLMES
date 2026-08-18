"""
Descoberta de ferramentas externas.

O Railway não tem holehe/maigret/theHarvester instalados na maioria dos
builds. Em vez de estourar timeout em silêncio, a gente detecta uma vez,
cacheia e diz na tela o que está e o que não está disponível.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

TIMEOUT_SHORT = 45
TIMEOUT_LONG = 150

# binário → módulo Python equivalente (dá para rodar via -m)
_MODULE_FALLBACK = {
    "holehe": "holehe",
    "maigret": "maigret",
    "theHarvester": "theHarvester",
    "dnstwist": "dnstwist",
    "socialscan": "socialscan",
}


@lru_cache(maxsize=None)
def binary_available(name: str) -> bool:
    if shutil.which(name):
        return True
    scripts = Path(sys.executable).parent
    for candidate in (scripts / name, scripts / f"{name}.exe"):
        if candidate.exists():
            return True
    module = _MODULE_FALLBACK.get(name)
    if module and importlib.util.find_spec(module) is not None:
        return True
    return False


@lru_cache(maxsize=None)
def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def resolve_command(name: str, args: list[str]) -> list[str] | None:
    """Prefere o binário; cai para `python -m módulo`; devolve None se não há nada."""
    path = shutil.which(name)
    if path:
        return [path, *args]
    scripts = Path(sys.executable).parent
    for candidate in (scripts / name, scripts / f"{name}.exe"):
        if candidate.exists():
            return [str(candidate), *args]
    module = _MODULE_FALLBACK.get(name)
    if module and module_available(module):
        return [sys.executable, "-m", module, *args]
    return None


def run_command(cmd: list[str], timeout: int = TIMEOUT_LONG) -> dict:
    """Execução blindada: timeout e erro viram dados, não exceção."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": -1, "stdout": "", "stderr": f"timeout de {timeout}s"}
    except FileNotFoundError:
        return {"ok": False, "code": -1, "stdout": "", "stderr": "binário não encontrado"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "code": -1, "stdout": "", "stderr": str(exc)}


def environment_report() -> dict[str, bool]:
    """Mostrado na página Investigar para você saber o que está de pé."""
    return {
        "holehe": binary_available("holehe"),
        "maigret": binary_available("maigret"),
        "theHarvester": binary_available("theHarvester"),
        "dnstwist": binary_available("dnstwist"),
        "phonenumbers": module_available("phonenumbers"),
        "dns": module_available("dns"),
        "bs4": module_available("bs4"),
    }
