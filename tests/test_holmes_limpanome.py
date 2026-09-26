"""
Limpar Nome: feriados, dias úteis, classificação, documentos, prazos,
importação de texto e persistência. Nada aqui toca a rede nem o LLM.
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import limpanome as ln  # noqa: E402

HOJE = date(2026, 9, 26)


# ── dias úteis ──────────────────────────────────────────────────────────────

def test_pascoa_e_feriados_moveis():
    assert ln.pascoa(2026) == date(2026, 4, 5)
    assert ln.pascoa(2024) == date(2024, 3, 31)
    f = ln.feriados_nacionais(2026)
    assert f[date(2026, 2, 17)] == "Carnaval"
    assert f[date(2026, 4, 3)] == "Sexta-feira Santa"
    assert f[date(2026, 6, 4)] == "Corpus Christi"
    assert f[date(2026, 11, 20)] == "Consciência Negra"


def test_somar_dias_uteis_pula_fim_de_semana_e_feriado():
    # 25/09/2026 é sexta. 10 dias úteis depois, sem feriado no meio, é 09/10.
    assert ln.somar_dias_uteis(date(2026, 9, 25), 10) == date(2026, 10, 9)
    # 09/10/2026 é sexta; 12/10 é feriado, então 1 dia útil depois é 13/10.
    assert ln.somar_dias_uteis(date(2026, 10, 9), 1) == date(2026, 10, 13)
    assert ln.dias_uteis_entre(date(2026, 9, 25), date(2026, 10, 9)) == 10
    assert ln.dias_uteis_entre(date(2026, 10, 9), date(2026, 9, 25)) == -10


# ── classificação ───────────────────────────────────────────────────────────

def test_mais_de_5_anos_do_vencimento_vai_para_baixa_por_prazo():
    r = ln.Registro(credor="Banco X", valor=1000, vencimento="2020-03-10", situacao="nao_sei")
    a = ln.analisar(r, HOJE)
    assert a.pilha == "vencido"
    assert a.limite_5_anos == date(2025, 3, 11)   # dia seguinte ao vencimento + 5 anos
    assert a.dias_para_vencer_prazo < 0
    assert a.argumento_principal.base.startswith("CDC art. 43 §1")
    assert "pedido_baixa_prazo" in a.documentos


def test_prazo_conta_do_vencimento_nao_da_inclusao():
    r = ln.Registro(credor="X", valor=1, vencimento="2022-01-15", inclusao="2019-01-01", situacao="minha_no_prazo")
    a = ln.analisar(r, HOJE)
    assert a.pilha == "verdadeira"
    assert a.limite_5_anos == date(2027, 1, 16)
    assert a.dias_para_vencer_prazo > 0


def test_dividas_verdadeira_vencida_vira_vencido_mesmo_sendo_minha():
    r = ln.Registro(credor="X", valor=1, vencimento="2021-01-15", situacao="minha_no_prazo")
    assert ln.analisar(r, HOJE).pilha == "vencido"


def test_vencimento_29_de_fevereiro():
    r = ln.Registro(credor="X", valor=1, vencimento="2024-02-29")
    assert ln.analisar(r, HOJE).limite_5_anos == date(2029, 3, 1)


def test_ja_paguei_com_comprovante_e_o_caso_mais_facil():
    r = ln.Registro(credor="Loja", valor=200, vencimento="2025-01-01", situacao="ja_paguei", comprovante=True)
    a = ln.analisar(r, HOJE)
    assert a.pilha == "errado" and a.prioridade == 1
    assert "Súmula 548" in a.argumento_principal.base
    assert not a.alerta


def test_ja_paguei_sem_comprovante_alerta():
    r = ln.Registro(credor="Loja", valor=200, vencimento="2025-01-01", situacao="ja_paguei")
    assert "comprovante" in ln.analisar(r, HOJE).alerta


def test_nao_reconheco_exige_documento_de_origem():
    r = ln.Registro(credor="Tele", valor=99, vencimento="2024-06-01", situacao="nao_reconheco")
    a = ln.analisar(r, HOJE)
    assert a.pilha == "errado"
    assert "contestacao_nao_reconheco" in a.documentos
    assert "6º, VIII" in a.argumento_principal.base


def test_sem_notificacao_previa_soma_argumento():
    r = ln.Registro(credor="X", valor=1, vencimento="2024-01-01", situacao="minha_no_prazo", notificado="nao")
    a = ln.analisar(r, HOJE)
    assert any("Súmulas 359" in x.base for x in a.argumentos)
    assert "contestacao_sem_notificacao" in a.documentos


def test_sem_data_de_vencimento_pede_documento_antes():
    r = ln.Registro(credor="X", valor=1, situacao="nao_sei")
    a = ln.analisar(r, HOJE)
    assert a.pilha == "duvida"
    assert a.documentos == ["pedido_documento_origem"]
    assert "vencimento" in a.alerta


def test_ordem_de_ataque_facil_primeiro():
    caso = ln.Caso(registros=[
        ln.Registro(credor="Não reconheço", valor=1, vencimento="2024-01-01", situacao="nao_reconheco"),
        ln.Registro(credor="Vencido", valor=1, vencimento="2019-01-01", situacao="nao_sei"),
        ln.Registro(credor="Pago", valor=1, vencimento="2025-01-01", situacao="ja_paguei", comprovante=True),
        ln.Registro(credor="Minha", valor=1, vencimento="2025-01-01", situacao="minha_no_prazo"),
    ])
    assert [r.credor for r, _ in ln.ordem_de_ataque(caso, HOJE)] == ["Pago", "Vencido", "Não reconheço", "Minha"]


def test_resumo_soma_so_o_contestavel():
    caso = ln.Caso(registros=[
        ln.Registro(credor="A", valor=100, vencimento="2019-01-01"),
        ln.Registro(credor="B", valor=50, vencimento="2025-01-01", situacao="minha_no_prazo"),
    ])
    s = ln.resumo(caso, HOJE)
    assert s["valor_total"] == 150 and s["valor_contestavel"] == 100
    assert s["por_pilha"]["vencido"] == 1 and s["por_pilha"]["verdadeira"] == 1


# ── documentos ──────────────────────────────────────────────────────────────

def _caso_um(reg: ln.Registro) -> ln.Caso:
    return ln.Caso(nome="Fulano de Tal", cpf_mascarado="529.***.***-25", registros=[reg])


def test_documentos_citam_so_lei_brasileira_e_nao_prometem_score():
    regs = [
        ln.Registro(credor="A", valor=10, vencimento="2019-01-01", situacao="nao_sei"),
        ln.Registro(credor="B", valor=10, vencimento="2025-01-01", situacao="ja_paguei", comprovante=True,
                    data_pagamento="2025-06-01"),
        ln.Registro(credor="C", valor=10, vencimento="2025-01-01", situacao="nao_reconheco"),
        ln.Registro(credor="D", valor=10, vencimento="2025-01-01", situacao="valor_errado", observacao="devo 5"),
        ln.Registro(credor="E", valor=10, vencimento="2025-01-01", situacao="minha_no_prazo", notificado="nao"),
        ln.Registro(credor="F", valor=10, situacao="nao_sei"),
    ]
    for r in regs:
        caso = _caso_um(r)
        for tipo in ln.analisar(r, HOJE).documentos:
            txt = ln.gerar_documento(tipo, caso, r, HOJE)
            assert "Fair Credit" not in txt and "FCRA" not in txt
            assert "score" not in txt.lower()
            assert r.credor in txt
            assert "R$ 10,00" in txt


def test_pedido_de_baixa_cita_a_data_limite():
    r = ln.Registro(credor="Banco X", valor=1234.5, vencimento="2020-03-10", situacao="nao_sei")
    txt = ln.gerar_documento("pedido_baixa_prazo", _caso_um(r), r, HOJE)
    assert "11/03/2025" in txt and "art. 43, §1" in txt and "Súmula 323" in txt


def test_texto_consumidor_gov_cabe_em_15_linhas():
    r = ln.Registro(credor="Loja Y", valor=300, vencimento="2024-01-05", situacao="ja_paguei", comprovante=True)
    txt = ln.gerar_documento("consumidor_gov", _caso_um(r), r, HOJE)
    assert len(txt.splitlines()) <= 15
    assert txt.startswith("Meu nome consta negativado")
    assert "Pedido:" in txt


def test_cenarios_de_negociacao_calculam_o_total():
    c = ln.cenarios_negociacao(1000, desconto_vista=0.5, parcelas_curto=6, parcelas_longo=24, juros_mes=0.02)
    assert c[0]["total"] == 500
    assert c[1]["total"] > 1000 and c[2]["total"] > c[1]["total"]
    assert abs(c[1]["parcela"] * 6 - c[1]["total"]) < 0.01
    sem_juros = ln.cenarios_negociacao(600, juros_mes=0)
    assert sem_juros[1]["parcela"] == 100


def test_documento_desconhecido_falha_alto():
    r = ln.Registro(credor="A", valor=1)
    try:
        ln.gerar_documento("inexistente", _caso_um(r), r, HOJE)
        assert False
    except ValueError:
        pass


# ── protocolos ──────────────────────────────────────────────────────────────

def test_protocolo_aguardando_e_atrasado():
    p = ln.Protocolo(registro_id="x", canal="consumidor.gov.br", data="2026-09-25")
    e = ln.situacao_protocolo(p, date(2026, 9, 30))
    # 10 dias corridos, como diz o consumidor.gov.br
    assert e["status"] == "Aguardando resposta" and e["limite_resposta"] == date(2026, 10, 5)
    e = ln.situacao_protocolo(p, date(2026, 10, 6))
    assert e["status"] == "Sem resposta no prazo" and e["atrasado"]
    assert "Procon" in e["acao"]


def test_protocolo_aceito_conta_5_dias_uteis_para_excluir():
    p = ln.Protocolo(registro_id="x", canal="consumidor.gov.br", data="2026-09-25",
                     aceito=True, data_resposta="2026-10-09")
    e = ln.situacao_protocolo(p, date(2026, 10, 14))
    # 09/10 sexta; 12/10 feriado; 5 dias úteis: 13,14,15,16,19 -> 19/10
    assert e["limite_exclusao"] == date(2026, 10, 19)
    assert e["status"] == "Aceito, aguardando exclusão"
    e = ln.situacao_protocolo(p, date(2026, 10, 20))
    assert e["atrasado"] and "dano moral" in e["acao"]


def test_protocolo_baixado_e_recusado():
    p = ln.Protocolo(registro_id="x", canal="biro", data="2026-09-01", data_baixa="2026-09-10")
    assert ln.situacao_protocolo(p, HOJE)["status"] == "Baixado"
    p = ln.Protocolo(registro_id="x", canal="biro", data="2026-09-01", aceito=False)
    acao = ln.situacao_protocolo(p, HOJE)["acao"]
    assert "Juizado" in acao and "3 anos" in acao


def test_avisos_do_caso_sumula_385_e_biro_unico():
    caso = ln.Caso(registros=[
        ln.Registro(credor="A", valor=1, vencimento="2019-01-01"),
        ln.Registro(credor="B", valor=1, vencimento="2025-01-01", situacao="minha_no_prazo"),
    ])
    avisos = ln.avisos_do_caso(caso, HOJE)
    assert any("Súmula 385" in a for a in avisos)
    assert any("outros birôs" in a for a in avisos)
    so_contestavel = ln.Caso(registros=[ln.Registro(credor="A", valor=1, vencimento="2019-01-01", biro="SPC Brasil"),
                                        ln.Registro(credor="C", valor=1, vencimento="2019-01-01", biro="Serasa")])
    assert not any("Súmula 385" in a for a in ln.avisos_do_caso(so_contestavel, HOJE))
    assert not any("outros birôs" in a for a in ln.avisos_do_caso(so_contestavel, HOJE))


# ── importação ──────────────────────────────────────────────────────────────

def test_importa_blocos_com_rotulos():
    regs = ln.importar_texto(
        "Serasa\nBANCO ABC S.A.\nContrato 123\nValor: R$ 1.250,90\nVencimento: 10/03/2020\n"
        "Inclusão: 15/05/2020\n\nLOJAS XYZ\nR$ 89,00\n01/02/2023")
    assert [(r.credor, r.valor, r.vencimento, r.inclusao) for r in regs] == [
        ("BANCO ABC S.A.", 1250.9, "2020-03-10", "2020-05-15"),
        ("LOJAS XYZ", 89.0, "2023-02-01", None),
    ]
    assert all(r.biro == "Serasa" for r in regs)


def test_importa_uma_linha_por_registro():
    regs = ln.importar_texto("SPC Brasil\nFINANCEIRA W | R$ 2.000,00 | 05/06/2019\nTELECOM Z | R$ 150,00 | 20/08/2022")
    assert [(r.credor, r.valor, r.vencimento, r.biro) for r in regs] == [
        ("FINANCEIRA W", 2000.0, "2019-06-05", "SPC Brasil"),
        ("TELECOM Z", 150.0, "2022-08-20", "SPC Brasil"),
    ]


def test_importa_texto_sem_valor_devolve_vazio():
    assert ln.importar_texto("nada aqui\nsó texto") == []
    assert ln.importar_texto("") == []


# ── persistência ────────────────────────────────────────────────────────────

def test_salva_e_recarrega_em_disco(monkeypatch):
    from holmes import store

    monkeypatch.setattr(ln, "CASOS_DIR", pathlib.Path(tempfile.mkdtemp()))
    monkeypatch.setattr(store, "enabled", lambda: False)
    caso = ln.Caso(nome="Fulano", cpf_mascarado="529.***.***-25", registros=[
        ln.Registro(credor="A", valor=10, vencimento="2020-01-01")])
    caso.protocolos.append(ln.Protocolo(registro_id=caso.registros[0].id, canal="biro", data="2026-09-01"))
    cid = ln.salvar(caso)
    lido = ln.carregar(cid)
    assert lido and lido.nome == "Fulano" and lido.registros[0].credor == "A"
    assert lido.protocolos[0].registro_id == caso.registros[0].id
    lista = ln.listar_casos()
    assert lista[0]["id"] == cid and lista[0]["registros"] == 1
    assert ln.carregar("nao-existe") is None


def test_salvar_manda_para_o_supabase_quando_ligado(monkeypatch):
    from holmes import store

    monkeypatch.setattr(ln, "CASOS_DIR", pathlib.Path(tempfile.mkdtemp()))
    gravados = []
    monkeypatch.setattr(store, "enabled", lambda: True)
    monkeypatch.setattr(store, "upsert", lambda t, row, oc: gravados.append((t, row, oc)) or True)
    ln.salvar(ln.Caso(nome="X"))
    assert gravados and gravados[0][0] == "holmes_limpanome" and gravados[0][2] == "id"
    assert "holmes_limpanome" in store.SCHEMA_SQL


# ── utilidades ──────────────────────────────────────────────────────────────

def test_moeda_e_data_em_portugues():
    assert ln.moeda(1234.5) == "R$ 1.234,50"
    assert ln.moeda(0) == "R$ 0,00"
    assert ln.data_br(date(2026, 9, 26)) == "26/09/2026"
    assert ln.data_br(None) == ""


# ── passagem para o Watson ─────────────────────────────────────────────────

def test_texto_para_watson_leva_fatos_prazos_e_protocolos():
    r = ln.Registro(credor="Banco X", valor=1234.5, vencimento="2020-03-10", situacao="nao_reconheco",
                    notificado="nao", cnpj_credor="11.222.333/0001-81")
    outra = ln.Registro(credor="Loja Y", valor=50, vencimento="2025-01-01", situacao="minha_no_prazo")
    caso = ln.Caso(nome="Fulano", cpf_mascarado="529.***.***-25", registros=[r, outra])
    caso.protocolos.append(ln.Protocolo(registro_id=r.id, canal="consumidor.gov.br", data="2026-09-01",
                                        numero="123", aceito=False, resposta="Dívida legítima."))
    txt = ln.texto_para_watson(caso, r, HOJE)
    for trecho in ("Banco X", "R$ 1.234,50", "11/03/2025", "já venceu", "Não reconheço",
                   "protocolo 123", "Recusado", "Dívida legítima.", "Súmula 385", "Juizado Especial Cível",
                   "1 são dívidas verdadeiras"):
        assert trecho in txt, trecho
    assert "529" not in txt           # CPF, nem mascarado, vai para o outro site


def test_link_watson_codifica_o_caso_no_fragmento():
    import base64
    import json as _json

    r = ln.Registro(credor="Banco Ção", valor=10, vencimento="2020-01-01")
    url = ln.link_watson(ln.Caso(registros=[r]), r, HOJE)
    assert url.startswith("https://watson.trustcorp.com.br/#caso=")
    b64 = url.split("#caso=", 1)[1]
    assert "=" not in b64 and "+" not in b64 and "/" not in b64
    dados = _json.loads(base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)).decode("utf-8"))
    assert dados["agente"] == "consumidor" and "Banco Ção" in dados["titulo"]
    assert dados["texto"] == ln.texto_para_watson(ln.Caso(registros=[r]), r, HOJE)
    assert len(dados["texto"]) <= 20000
