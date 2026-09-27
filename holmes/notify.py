"""
Notificação por e-mail.

Quando o monitoramento acha novidade num alvo, ou um prazo do Limpa Nome
vence, manda um e-mail. Dois caminhos, nesta ordem:

1. Resend (API HTTP, recomendado): só uma chave, melhor entrega.
     RESEND_API_KEY  chave re_... do painel do Resend
     RESEND_FROM     remetente, ex.: "Mr.Holmes <alertas@trustcorp.com.br>"
                     (o domínio precisa estar verificado no Resend; sem isso,
                     o Resend só aceita onboarding@resend.dev e só entrega
                     para o e-mail dono da conta)
2. SMTP (biblioteca padrão), ex.: Gmail com senha de app.
     SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

Em ambos:
  ALERT_EMAIL    destino padrão dos alertas (se vazio, usa SMTP_USER)
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

RESEND_URL = "https://api.resend.com/emails"


def _env(nome: str) -> str:
    return (os.environ.get(nome) or "").strip().strip('"').strip("'")


def resend_configurado() -> bool:
    return bool(_env("RESEND_API_KEY"))


def smtp_configurado() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER")
                and os.environ.get("SMTP_PASSWORD"))


def configured() -> bool:
    return resend_configurado() or smtp_configurado()


def provedor() -> str:
    """Nome do canal que vai ser usado, para mostrar na tela."""
    if resend_configurado():
        return "Resend"
    if smtp_configurado():
        return "SMTP"
    return ""


def _destino() -> str:
    return (os.environ.get("ALERT_EMAIL") or os.environ.get("SMTP_USER") or "").strip()


def _send_resend(assunto: str, corpo: str, destino: str) -> bool:
    import requests

    remetente = _env("RESEND_FROM") or "Mr.Holmes <onboarding@resend.dev>"
    try:
        resp = requests.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {_env('RESEND_API_KEY')}", "Content-Type": "application/json"},
            json={"from": remetente, "to": [destino], "subject": assunto, "text": corpo},
            timeout=20,
        )
        return 200 <= resp.status_code < 300
    except Exception:
        return False


def send(assunto: str, corpo: str, destino: str | None = None) -> bool:
    """Envia um e-mail simples. Devolve True se saiu; nunca levanta exceção.
    Sem `destino`, vai para ALERT_EMAIL (ou o próprio SMTP_USER).
    Resend primeiro; se falhar e houver SMTP, tenta o SMTP."""
    if not configured():
        return False
    alvo = (destino or "").strip() or _destino()
    if resend_configurado() and alvo:
        if _send_resend(assunto, corpo, alvo):
            return True
        if not smtp_configurado():
            return False
    if not smtp_configurado():
        return False
    host = os.environ["SMTP_HOST"].strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"].strip()
    pwd = os.environ["SMTP_PASSWORD"]
    destino = (destino or "").strip() or _destino()
    if not destino:
        return False

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = user
    msg["To"] = destino
    msg.set_content(corpo)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as s:
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, pwd)
                s.send_message(msg)
        return True
    except Exception:
        return False


def notify_alerts(alertas: list[dict]) -> bool:
    """Monta e envia um resumo dos alertas de novidade de uma rodada."""
    novidades = [a for a in alertas if a.get("tipo") == "novidade"]
    if not novidades or not configured():
        return False

    linhas = ["O monitoramento do Mr.Holmes encontrou novidades:\n"]
    for a in novidades:
        linhas.append(f"• {a.get('alvo')}: {a.get('texto')}")
        for secao, m in (a.get("detalhe") or {}).items():
            for v in (m.get("novos") or [])[:8]:
                linhas.append(f"    - novo em {secao}: {v}")
    linhas.append("\nAbra a aba Monitoramento no Mr.Holmes para ver o dossiê completo.")

    assunto = (f"[Mr.Holmes] {len(novidades)} alvo(s) com novidade"
               if len(novidades) > 1 else
               f"[Mr.Holmes] novidade em {novidades[0].get('alvo')}")
    return send(assunto, "\n".join(linhas))
