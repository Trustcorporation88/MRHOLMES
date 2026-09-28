from unittest import mock

from holmes import monitor

REGISTRO = {"dossie": {"fatos": {
    "empresa": [{"value": "ACME LTDA", "detail": "Sócio desde 2015", "sources": ["CNPJ Trust"],
                 "urls": ["https://cnpj.trustcorp.com.br/x"], "confidence": "confirmado"}],
    "juridico": [{"value": "Processo 123", "detail": "", "sources": ["JusBrasil"], "urls": [], "confidence": ""}],
}}}

ALERTA = {"alvo": "Fulano", "tipo": "novidade", "dossie_id": "abc",
          "detalhe": {"Empresas": {"novos": ["ACME LTDA"], "sumidos": ["VELHA ME"]},
                      "Jurídico": {"novos": ["Processo 123", "Processo 456"], "sumidos": []}}}


def test_detalhes_trazem_fonte_detalhe_e_link():
    with mock.patch.object(monitor.history, "load", return_value=REGISTRO) as load:
        secoes = monitor.detalhes_alerta(ALERTA)
    load.assert_called_once_with("abc")
    assert [s["secao"] for s in secoes] == ["Jurídico", "Empresas"]  # mais novidades primeiro
    empresa = secoes[1]["novos"][0]
    assert empresa["detalhe"] == "Sócio desde 2015"
    assert empresa["fontes"] == ["CNPJ Trust"]
    assert empresa["links"] == ["https://cnpj.trustcorp.com.br/x"]
    assert secoes[1]["sumidos"] == ["VELHA ME"]
    # valor que não está no dossiê aparece mesmo assim, só sem fonte
    assert secoes[0]["novos"][1] == {"valor": "Processo 456", "detalhe": "", "fontes": [], "links": [],
                                     "confianca": ""}


def test_alerta_antigo_usa_ultimo_dossie_da_vigilancia():
    antigo = {k: v for k, v in ALERTA.items() if k != "dossie_id"}
    with mock.patch.object(monitor, "watchlist", return_value=[{"alvo": "FULANO", "ultimo_id": "xyz"}]), \
         mock.patch.object(monitor.history, "load", return_value=REGISTRO) as load:
        secoes = monitor.detalhes_alerta(antigo)
    load.assert_called_once_with("xyz")
    assert secoes[1]["novos"][0]["fontes"] == ["CNPJ Trust"]


def test_sem_dossie_ainda_lista_os_valores():
    with mock.patch.object(monitor.history, "load", return_value=None):
        secoes = monitor.detalhes_alerta(ALERTA)
    assert [n["valor"] for n in secoes[0]["novos"]] == ["Processo 123", "Processo 456"]


def test_alerta_sem_detalhe():
    assert monitor.detalhes_alerta({"alvo": "x", "tipo": "erro", "texto": "falhou"}) == []


def test_run_once_grava_dossie_id_no_alerta(monkeypatch):
    monkeypatch.setattr(monitor, "watchlist", lambda: [{"alvo": "Fulano", "ultimo_id": "velho"}])
    monkeypatch.setattr(monitor, "_update_target", lambda cfg: None)
    monkeypatch.setattr(monitor, "enabled_store", lambda: True)
    monkeypatch.setattr(monitor.history, "save", lambda d: "novo")
    monkeypatch.setattr(monitor.history, "diff", lambda a, b: {"tem_novidade": True,
                        "mudancas": {"Nomes": {"novos": ["X"], "sumidos": []}}})
    gravados = []
    monkeypatch.setattr(monitor, "_push_alert", gravados.append)
    with mock.patch("holmes.notify.notify_alerts"):
        monitor.run_once(investigate_fn=lambda alvo: object())
    assert gravados[0]["dossie_id"] == "novo"
