"""
Limpa Nome, serviços complementares: leitura de PDF ou print, kit do
Juizado e lembretes de prazo por e-mail. Nada aqui toca a rede.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import limpanome as ln  # noqa: E402
from holmes import limpanome_arquivos as lna  # noqa: E402
from holmes import limpanome_kit as kit  # noqa: E402

HOJE = date(2026, 9, 27)
JSON_IA = ('Aqui estão os registros:\n[{"credor": "BANCO ABC S.A.", "valor": 1250.9, '
           '"vencimento": "2020-03-10", "inclusao": null, "biro": "Serasa", "cnpj_credor": ""}, '
           '{"credor": "LOJA", "valor": "R$ 89", "vencimento": "10/02/2023", "biro": "Inventado"}, '
           '{"credor": "", "valor": 1}]')


class _Resp:
    def __init__(self, status, dados):
        self.status_code = status
        self._dados = dados

    def json(self):
        return self._dados


# ── leitura de arquivo ──────────────────────────────────────────────────────

def test_registros_do_json_tolera_texto_e_campos_ruins():
    regs = lna.registros_do_json(JSON_IA)
    assert [r.credor for r in regs] == ["BANCO ABC S.A.", "LOJA"]
    assert regs[0].valor == 1250.9 and regs[0].vencimento == "2020-03-10"
    assert regs[1].valor == 89.0 and regs[1].vencimento is None   # data fora do padrão ISO fica vazia
    assert regs[1].biro == "Serasa"                                # birô inventado cai no padrão
    assert lna.registros_do_json("sem json") == []
    assert lna.registros_do_json(None) == []
    assert lna.registros_do_json('[{"credor": "X"}]', ln.PROTESTO)[0].biro == ln.PROTESTO


def test_formatos_e_limites(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert lna.extrair_de_arquivo("a.docx", b"1")[0] == []
    assert "vazio" in lna.extrair_de_arquivo("a.pdf", b"")[1]
    assert "20 MB" in lna.extrair_de_arquivo("a.pdf", b"0" * (lna.LIMITE_BYTES + 1))[1]
    assert lna.tipo_do_arquivo("Relatorio.PDF") == "application/pdf"
    assert lna.tipo_do_arquivo("print.jpeg") == "image/jpeg"


def test_sem_chave_avisa(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    regs, msg = lna.extrair_de_arquivo("a.pdf", b"%PDF")
    assert regs == [] and "ANTHROPIC_API_KEY" in msg


def test_pdf_vai_como_documento_para_a_anthropic(monkeypatch):
    enviados = []

    def _post(url, headers=None, json=None, timeout=None):
        enviados.append((url, json))
        return _Resp(200, {"content": [{"type": "text", "text": JSON_IA}]})

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(lna.requests, "post", _post)
    regs, msg = lna.extrair_de_arquivo("serasa.pdf", b"%PDF-1.4")
    assert len(regs) == 2 and "2 registro" in msg
    url, corpo = enviados[0]
    assert "anthropic.com" in url
    bloco = corpo["messages"][0]["content"][0]
    assert bloco["type"] == "document" and bloco["source"]["media_type"] == "application/pdf"


def test_modelo_inexistente_passa_para_o_proximo(monkeypatch):
    modelos = []

    def _post(url, headers=None, json=None, timeout=None):
        modelos.append(json["model"])
        if json["model"] == "claude-sonnet-5":
            return _Resp(404, {"error": {"type": "not_found_error", "message": "model: claude-sonnet-5"}})
        return _Resp(200, {"content": [{"type": "text", "text": JSON_IA}]})

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.delenv("HOLMES_VISAO_MODELO", raising=False)
    monkeypatch.setattr(lna.requests, "post", _post)
    regs, _ = lna.extrair_de_arquivo("a.pdf", b"%PDF")
    assert len(regs) == 2 and modelos == ["claude-sonnet-5", "claude-sonnet-4-5"]
    # modelo escolhido por variável vem primeiro
    monkeypatch.setenv("HOLMES_VISAO_MODELO", "claude-opus-5")
    assert lna._modelos_anthropic()[0] == "claude-opus-5"


def test_print_cai_para_openai_se_anthropic_falhar(monkeypatch):
    chamadas = []

    def _post(url, headers=None, json=None, timeout=None):
        chamadas.append(url)
        if "anthropic" in url:
            return _Resp(500, {})
        anexo = json["messages"][1]["content"][0]
        assert anexo["type"] == "image_url" and anexo["image_url"]["url"].startswith("data:image/png;base64,")
        return _Resp(200, {"choices": [{"message": {"content": JSON_IA}}]})

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    monkeypatch.setattr(lna.requests, "post", _post)
    regs, _ = lna.extrair_de_arquivo("print.png", b"\x89PNG")
    assert len(regs) == 2 and len(chamadas) == 2


# ── kit do Juizado ──────────────────────────────────────────────────────────

def _caso_com_protocolo():
    r = ln.Registro(credor="Banco X", valor=1234.5, vencimento="2020-03-10", inclusao="2020-06-01",
                    situacao="nao_reconheco", notificado="nao")
    caso = ln.Caso(nome="Fulano de Tal", cpf_mascarado="529.***.***-25", registros=[r])
    caso.protocolos.append(ln.Protocolo(registro_id=r.id, canal="consumidor.gov.br", data="2026-08-01",
                                        numero="2026-123", aceito=False, data_resposta="2026-08-08",
                                        resposta="Dívida legítima."))
    return caso, r


def test_kit_tem_todas_as_secoes_e_a_linha_do_tempo_em_ordem():
    caso, r = _caso_com_protocolo()
    secoes = dict(kit.secoes_do_kit(caso, r, HOJE))
    assert list(secoes) == ["Identificação", "Linha do tempo", "O que já foi tentado",
                            "Fundamentos (Registro errado)", "Pedidos", "Provas para juntar", "Atenção",
                            "Onde levar"]
    tempo = secoes["Linha do tempo"]
    assert tempo[0].startswith("10/03/2020") and "Vencimento" in tempo[0]
    assert any("11/03/2025" in t and "5 anos" in t for t in tempo)
    assert any("recusou" in t for t in tempo)
    assert "protocolo 2026-123" in secoes["O que já foi tentado"][0]
    assert any("Boletim de ocorrência" in p for p in secoes["Provas para juntar"])
    assert any("aviso prévio" in p for p in secoes["Provas para juntar"])
    assert "529.***.***-25" in secoes["Identificação"][1]


def test_kit_sem_protocolo_orienta_a_tentar_antes():
    r = ln.Registro(credor="Loja", valor=10, vencimento="2025-01-01", situacao="ja_paguei")
    secoes = dict(kit.secoes_do_kit(ln.Caso(registros=[r]), r, HOJE))
    assert "Nenhum pedido registrado" in secoes["O que já foi tentado"][0]
    assert any("Comprovante de pagamento" in p for p in secoes["Provas para juntar"])


def test_kit_de_protesto_pede_cancelamento():
    r = ln.Registro(credor="Fornecedor", valor=10, biro=ln.PROTESTO, situacao="ja_paguei")
    secoes = dict(kit.secoes_do_kit(ln.Caso(registros=[r]), r, HOJE))
    assert "Cancelamento do protesto" in secoes["Pedidos"][0]
    assert any("CENPROT" in p for p in secoes["Provas para juntar"])


def test_kit_markdown_e_pdf():
    caso, r = _caso_com_protocolo()
    md = kit.kit_markdown(caso, r, HOJE)
    assert md.startswith("# Kit do Juizado e do Procon: Banco X")
    assert "## Linha do tempo" in md and "score" not in md.lower()
    if kit.disponivel_pdf():
        assert kit.kit_pdf(caso, r, HOJE).startswith(b"%PDF")


# ── lembretes ───────────────────────────────────────────────────────────────

def test_lembrete_sai_uma_vez_por_estado(monkeypatch):
    monkeypatch.setattr(ln, "CASOS_DIR", pathlib.Path(tempfile.mkdtemp()))
    from holmes import store

    monkeypatch.setattr(store, "enabled", lambda: False)
    r = ln.Registro(credor="Banco X", valor=100, vencimento="2025-01-01")
    caso = ln.Caso(nome="Fulano", email="fulano@exemplo.com", registros=[r])
    caso.protocolos.append(ln.Protocolo(registro_id=r.id, canal="consumidor.gov.br", data="2026-09-01",
                                        numero="777"))
    caixa = []

    def _enviar(assunto, corpo, destino):
        caixa.append((assunto, corpo, destino))
        return True

    assert ln.enviar_lembretes(HOJE, [caso], _enviar) == 1
    assunto, corpo, destino = caixa[0]
    assert "Banco X" in assunto and destino == "fulano@exemplo.com"
    assert "protocolo 777" in corpo and "Procon" in corpo
    assert caso.protocolos[0].avisos_enviados == ["Sem resposta no prazo"]
    # segunda rodada: nada novo
    assert ln.enviar_lembretes(HOJE, [caso], _enviar) == 0
    # a empresa aceitou e não excluiu: novo estado, novo aviso
    caso.protocolos[0].aceito = True
    caso.protocolos[0].data_resposta = "2026-09-10"
    assert ln.enviar_lembretes(HOJE, [caso], _enviar) == 1
    assert "exclusão atrasada" in caixa[-1][1]
    # e o aviso ficou salvo no disco
    assert ln.carregar(caso.id).protocolos[0].avisos_enviados == ["Sem resposta no prazo",
                                                                    "Aceito, exclusão atrasada"]


def test_lembrete_nao_marca_se_o_envio_falhar(monkeypatch):
    monkeypatch.setattr(ln, "CASOS_DIR", pathlib.Path(tempfile.mkdtemp()))
    r = ln.Registro(credor="X", valor=1)
    caso = ln.Caso(registros=[r])
    caso.protocolos.append(ln.Protocolo(registro_id=r.id, canal="biro", data="2026-09-01"))
    assert ln.enviar_lembretes(HOJE, [caso], lambda *a: False) == 0
    assert caso.protocolos[0].avisos_enviados == []


def test_sem_smtp_nao_envia(monkeypatch):
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    assert ln.enviar_lembretes(HOJE, []) == 0


def test_carregar_todos_usa_o_supabase_quando_ligado(monkeypatch):
    from holmes import store

    caso = ln.Caso(nome="Remoto", registros=[ln.Registro(credor="A", valor=1)])
    from dataclasses import asdict

    monkeypatch.setattr(store, "enabled", lambda: True)
    monkeypatch.setattr(store, "select", lambda t, p=None: [{"dados": asdict(caso)}])
    todos = ln.carregar_todos()
    assert [c.nome for c in todos] == ["Remoto"]


def test_notify_send_aceita_destino(monkeypatch):
    from holmes import notify

    enviados = []

    class _SMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, **k):
            pass

        def login(self, *a):
            pass

        def send_message(self, msg):
            enviados.append(msg["To"])

    for k, v in {"SMTP_HOST": "h", "SMTP_USER": "u@x.com", "SMTP_PASSWORD": "p", "ALERT_EMAIL": "a@x.com"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(notify.smtplib, "SMTP", _SMTP)
    assert notify.send("s", "c", "cliente@x.com") and notify.send("s", "c")
    assert enviados == ["cliente@x.com", "a@x.com"]
