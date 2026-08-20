"""Notificação por e-mail do monitoramento. SMTP é mockado — sem rede."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import notify  # noqa: E402


def test_desligado_sem_env(monkeypatch):
    for v in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(v, raising=False)
    assert notify.configured() is False
    assert notify.send("x", "y") is False


def _config(monkeypatch, porta="587"):
    monkeypatch.setenv("SMTP_HOST", "smtp.x.com")
    monkeypatch.setenv("SMTP_PORT", porta)
    monkeypatch.setenv("SMTP_USER", "a@x.com")
    monkeypatch.setenv("SMTP_PASSWORD", "senha-de-app")
    monkeypatch.setenv("ALERT_EMAIL", "dest@x.com")


class _FakeSMTP:
    ultima = {}

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def starttls(self, **k):
        _FakeSMTP.ultima["tls"] = True

    def login(self, u, p):
        _FakeSMTP.ultima["user"] = u

    def send_message(self, m):
        _FakeSMTP.ultima["msg"] = (m["Subject"], m["To"], m.get_content())


def test_envia_com_starttls(monkeypatch):
    _config(monkeypatch)
    import smtplib
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    assert notify.send("Assunto", "Corpo") is True
    assert _FakeSMTP.ultima["msg"][1] == "dest@x.com"
    assert _FakeSMTP.ultima.get("tls") is True


def test_alert_email_cai_no_user_se_vazio(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.x.com")
    monkeypatch.setenv("SMTP_USER", "a@x.com")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.delenv("ALERT_EMAIL", raising=False)
    assert notify._destino() == "a@x.com"


def test_notify_alerts_resume_novidades(monkeypatch):
    _config(monkeypatch)
    import smtplib
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    alertas = [{
        "alvo": "Fulano", "tipo": "novidade", "texto": "Novidade: 1 em Telefones",
        "detalhe": {"Telefones": {"novos": ["+5511999998888"], "sumidos": []}},
    }]
    assert notify.notify_alerts(alertas) is True
    assunto, _para, corpo = _FakeSMTP.ultima["msg"]
    assert "Fulano" in assunto
    assert "+5511999998888" in corpo


def test_notify_ignora_erros_e_sem_novidade(monkeypatch):
    _config(monkeypatch)
    # Só alerta de erro → não manda e-mail.
    assert notify.notify_alerts([{"alvo": "X", "tipo": "erro", "texto": "falhou"}]) is False


def test_falha_smtp_nao_quebra(monkeypatch):
    _config(monkeypatch)
    import smtplib

    def _boom(*a, **k):
        raise OSError("sem conexão")

    monkeypatch.setattr(smtplib, "SMTP", _boom)
    assert notify.send("x", "y") is False  # engole o erro
