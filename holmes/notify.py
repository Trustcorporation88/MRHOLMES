"""
Notificação por e-mail.

Quando o monitoramento acha novidade num alvo, manda um e-mail para você.
Usa SMTP puro (biblioteca padrão) — funciona com Gmail (senha de app),
Outlook, ou qualquer servidor SMTP. Sem serviço pago, sem dependência nova.

Configuração por variáveis de ambiente (no Railway):
  SMTP_HOST      ex.: smtp.gmail.com
  SMTP_PORT      ex.: 587
  SMTP_USER      seu e-mail de envio
  SMTP_PASSWORD  senha de app (NÃO a senha normal da conta)
  ALERT_EMAIL    para onde mandar o alerta (se vazio, usa SMTP_USER)
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER")
                and os.environ.get("SMTP_PASSWORD"))


def _destino() -> str:
    return (os.environ.get("ALERT_EMAIL") or os.environ.get("SMTP_USER") or "").strip()


def send(assunto: str, corpo: str) -> bool:
    """Envia um e-mail simples. Devolve True se saiu; nunca levanta exceção."""
    if not configured():
        return False
    host = os.environ["SMTP_HOST"].strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"].strip()
    pwd = os.environ["SMTP_PASSWORD"]
    destino = _destino()
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
