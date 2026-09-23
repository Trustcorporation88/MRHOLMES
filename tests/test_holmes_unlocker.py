"""
Rota paga (Bright Data Web Unlocker) e classificação bloqueio × ausência.

Nenhum teste aqui toca a rede: o ponto é justamente garantir que a decisão de
gastar dinheiro e a decisão de afirmar "não existe perfil" sejam tomadas por
lógica local e verificável.
"""

from __future__ import annotations

import pytest

from Core.Support import WhatsMyName as wmn
from holmes import net


class FakeResp:
    def __init__(self, status: int, text: str = "", headers: dict | None = None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}


@pytest.fixture(autouse=True)
def _ambiente_limpo(monkeypatch):
    for var in (
        "HOLMES_UNLOCKER", "BRIGHTDATA_API_KEY", "BRIGHT_DATA_API_KEY",
        "BRD_API_KEY", "HOLMES_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)
    net._RUNTIME_KEYS.clear()
    net.unlocker_reset_stats()
    monkeypatch.setattr(net, "_github_token_rejected", False)
    yield
    net.unlocker_reset_stats()


# ── o interruptor ───────────────────────────────────────────────────────────

def test_unlocker_desligado_por_padrao():
    assert net.unlocker_enabled() is False


def test_chave_sozinha_nao_liga_a_rota_paga(monkeypatch):
    """Ter a chave no ambiente não pode, sozinha, começar a gastar."""
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "chave-de-teste")
    assert net.unlocker_enabled() is False


def test_interruptor_sozinho_tambem_nao_liga(monkeypatch):
    monkeypatch.setenv("HOLMES_UNLOCKER", "1")
    assert net.unlocker_enabled() is False


def test_chave_mais_interruptor_liga(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "chave-de-teste")
    monkeypatch.setenv("HOLMES_UNLOCKER", "1")
    assert net.unlocker_enabled() is True


def test_desligado_nao_faz_requisicao(monkeypatch):
    def _explode(*a, **k):
        raise AssertionError("requisição paga disparada com o unlocker desligado")

    monkeypatch.setattr(net._SESSION, "post", _explode)
    assert net.unlocked_get_text("https://exemplo.test/x") is None


def test_teto_de_orcamento_corta_o_gasto(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "k")
    monkeypatch.setenv("HOLMES_UNLOCKER", "1")
    monkeypatch.setattr(net, "UNLOCKER_BUDGET", 2)
    monkeypatch.setattr(net, "DEFAULT_TTL", 0)
    chamadas = {"n": 0}

    def _post(*a, **k):
        chamadas["n"] += 1
        return FakeResp(200, "<html>ok</html>")

    monkeypatch.setattr(net._SESSION, "post", _post)
    for i in range(5):
        net.unlocked_get_text(f"https://exemplo.test/{i}", ttl=0)

    assert chamadas["n"] == 2, "o teto não segurou o gasto"
    assert net.unlocker_stats()["bloqueadas_por_teto"] == 3


# ── token do GitHub: não vazar credencial de terceiro ───────────────────────

def test_github_token_ignora_valor_que_nao_e_do_github(monkeypatch):
    """GITHUB_TOKEN costuma guardar token de CI/proxy. Mandar para o GitHub
    vaza credencial alheia e ainda quebra o conector com 401."""
    monkeypatch.setenv("GITHUB_TOKEN", "proxy-abcdef123456")
    assert net.github_token() is None
    assert "Authorization" not in net.github_headers()


def test_github_token_aceita_token_real(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_umTokenQueParecePlausivel1234567890")
    assert net.github_token().startswith("ghp_")
    assert net.github_headers()["Authorization"].startswith("Bearer ghp_")


def test_variavel_dedicada_tem_prioridade(monkeypatch):
    monkeypatch.setenv("HOLMES_GITHUB_TOKEN", "qualquer-coisa-explicita")
    assert net.github_token() == "qualquer-coisa-explicita"


# ── bloqueio não é ausência ─────────────────────────────────────────────────

SITE = {"name": "Exemplo", "uri_check": "https://exemplo.test/{account}",
        "e_code": 200, "m_code": 404, "e_string": "perfil"}


def test_403_e_bloqueio():
    assert wmn._looks_blocked(FakeResp(403), SITE) is True


def test_429_e_bloqueio():
    assert wmn._looks_blocked(FakeResp(429), SITE) is True


def test_codigo_esperado_pelo_dataset_nao_e_bloqueio():
    """Se o site legitimamente responde 403 para perfil existente, 403 é sinal,
    não barreira."""
    site = {**SITE, "e_code": 403}
    assert wmn._looks_blocked(FakeResp(403), site) is False


def test_m_code_do_dataset_nao_e_bloqueio():
    site = {**SITE, "m_code": 403}
    assert wmn._looks_blocked(FakeResp(403), site) is False


def test_404_normal_nao_e_bloqueio():
    assert wmn._looks_blocked(FakeResp(404), SITE) is False


def test_pagina_de_captcha_e_bloqueio():
    resp = FakeResp(200, "<html><title>Just a moment...</title></html>")
    assert wmn._looks_blocked(resp, SITE) is True


def test_probe_classifica_os_tres_casos(monkeypatch):
    casos = {
        "https://exemplo.test/achou": FakeResp(200, "tem perfil aqui"),
        "https://exemplo.test/naotem": FakeResp(404, "nada"),
        "https://exemplo.test/barrou": FakeResp(403, "no"),
    }
    monkeypatch.setattr(wmn.requests, "get", lambda url, **k: casos[url])

    assert wmn._probe(SITE, "achou", 5.0)["status"] == "hit"
    assert wmn._probe(SITE, "naotem", 5.0)["status"] == "miss"
    assert wmn._probe(SITE, "barrou", 5.0)["status"] == "blocked"


def test_erro_de_rede_vira_error_nao_miss(monkeypatch):
    def _boom(*a, **k):
        raise OSError("sem rota")

    monkeypatch.setattr(wmn.requests, "get", _boom)
    assert wmn._probe(SITE, "x", 5.0)["status"] == "error"


def test_check_username_separa_bloqueio_de_ausencia(monkeypatch):
    sites = [
        {**SITE, "name": "Responde", "uri_check": "https://ok.test/{account}"},
        {**SITE, "name": "Barra", "uri_check": "https://barra.test/{account}"},
    ]
    monkeypatch.setattr(wmn, "selectable_sites", lambda blob, max_sites=80: sites)
    respostas = {
        "https://ok.test/alvo": FakeResp(404, "nada"),
        "https://barra.test/alvo": FakeResp(403, "no"),
    }
    monkeypatch.setattr(wmn.requests, "get", lambda url, **k: respostas[url])

    res = wmn.check_username("alvo", data={"sites": sites}, workers=2)
    assert res["ok"] is True
    assert res["profiles"] == []
    assert res["blocked_count"] == 1
    # o denominador honesto: 1 site respondeu, não 2
    assert res["conclusive"] == 1


def test_conector_nao_afirma_ausencia_quando_houve_bloqueio(monkeypatch):
    """O achado só pode ser CONFIRMED se todo mundo respondeu."""
    from holmes.connectors import auto
    from holmes.entity import Entity, EntityType
    from holmes.findings import Confidence

    monkeypatch.setattr(
        auto, "_whatsmyname", auto._whatsmyname
    )  # mantém a função real
    import Core.Support.WhatsMyName as mod

    monkeypatch.setattr(
        mod, "check_username",
        lambda *a, **k: {
            "ok": True, "profiles": [], "checked": 10, "conclusive": 7,
            "blocked": [{"site": "Barra", "http": 403}], "blocked_count": 1,
        },
    )
    ent = Entity(type=EntityType.USERNAME, value="alvo", raw="alvo")
    achados = list(auto._whatsmyname(ent))
    nota = next(a for a in achados if "Nenhum perfil" in a.value)
    assert nota.confidence is not Confidence.CONFIRMED
    assert "bloquearam" in nota.value


# ── token do GitHub vencido não derruba o conector ──────────────────────────

class _GitHubFake:
    """Responde 401 a quem manda token e 200 a quem não manda."""

    def __init__(self):
        self.chamadas = []

    def get(self, url, params=None, headers=None, timeout=None):
        auth = (headers or {}).get("Authorization")
        self.chamadas.append(auth)
        if auth:
            return FakeResp(401, '{"message":"Bad credentials"}')
        r = FakeResp(200, '{"login":"alvo"}')
        r.json = lambda: {"login": "alvo"}
        return r


def test_token_recusado_cai_para_modo_sem_token(monkeypatch):
    monkeypatch.setenv("HOLMES_GITHUB_TOKEN", "ghp_vencido")
    monkeypatch.setattr(net, "DEFAULT_TTL", 0)
    fake = _GitHubFake()
    monkeypatch.setattr(net._SESSION, "get", fake.get)

    data = net.github_get_json("https://api.github.com/users/alvo", ttl=0)

    assert data == {"login": "alvo"}
    assert fake.chamadas == ["Bearer ghp_vencido", None]
    assert net.github_auth_state() == "recusado"


def test_depois_do_401_nao_insiste_no_token(monkeypatch):
    """Um 401 basta. Cada consulta seguinte vai direto sem token."""
    monkeypatch.setenv("HOLMES_GITHUB_TOKEN", "ghp_vencido")
    fake = _GitHubFake()
    monkeypatch.setattr(net._SESSION, "get", fake.get)

    net.github_get_json("https://api.github.com/users/a", ttl=0)
    net.github_get_json("https://api.github.com/users/b", ttl=0)

    assert fake.chamadas == ["Bearer ghp_vencido", None, None]


def test_sem_token_401_continua_sendo_erro(monkeypatch):
    """Sem token não há o que desligar. O 401 sobe como erro normal."""
    import requests

    monkeypatch.setattr(net._SESSION, "get", lambda *a, **k: FakeResp(401, "{}"))
    with pytest.raises(requests.HTTPError):
        net.github_get_json("https://api.github.com/users/x", ttl=0)
    assert net.github_auth_state() == "sem_token"


def test_token_valido_fica_ativo(monkeypatch):
    monkeypatch.setenv("HOLMES_GITHUB_TOKEN", "ghp_bom")

    def _ok(url, params=None, headers=None, timeout=None):
        r = FakeResp(200, "{}")
        r.json = lambda: {"login": "alvo"}
        return r

    monkeypatch.setattr(net._SESSION, "get", _ok)
    net.github_get_json("https://api.github.com/users/alvo", ttl=0)
    assert net.github_auth_state() == "ativo"
