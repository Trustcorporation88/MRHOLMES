"""Placa de veículo BR: detecção, deeplinks e dorks. Sem rede."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import serp  # noqa: E402
from holmes.br import br_deeplinks  # noqa: E402
from holmes.connectors import Mode, connectors_for, ensure_registered  # noqa: E402
from holmes.entity import EntityType, detect  # noqa: E402


def test_mercosul_e_detectada():
    e = detect("ABC1D23")
    assert e.type is EntityType.PLACA
    assert e.value == "ABC1D23"
    assert e.get("formato") == "Mercosul"


def test_mercosul_minuscula_tambem():
    assert detect("abc1d23").type is EntityType.PLACA


def test_antiga_maiuscula_e_placa():
    e = detect("ABC1234")
    assert e.type is EntityType.PLACA
    assert e.value == "ABC1234"


def test_antiga_com_hifen_e_placa():
    assert detect("ABC-1234").type is EntityType.PLACA
    assert detect("ABC-1234").value == "ABC1234"


def test_antiga_minuscula_sem_separador_vira_username():
    # "abc1234" é ambíguo com handle — não pode ser placa, senão quebra username.
    assert detect("abc1234").type is EntityType.USERNAME


def test_deeplinks_levam_a_placa_na_url():
    e = detect("ABC1D23")
    rotulos = {r for r, _u, _d in br_deeplinks(e)}
    assert "KePlaca" in rotulos
    assert all("ABC1D23" in u for _r, u, _d in br_deeplinks(e))


def test_serp_gera_dork_da_placa():
    e = detect("ABC1D23")
    qs = serp.build_queries(e)
    assert any("ABC1D23" in q for q in qs)


def test_catalogo_registra_conector_de_placa():
    ensure_registered()
    e = detect("ABC1D23")
    conns = connectors_for(e, {Mode.DEEPLINK})
    assert conns, "placa deveria ter deeplinks registrados"
