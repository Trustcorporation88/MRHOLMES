"""Detecção e normalização de alvo — a porta de entrada do motor."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes.entity import (  # noqa: E402
    EntityType,
    detect,
    detect_all,
    format_cnpj,
    valid_cnpj,
    valid_cpf,
)


def test_detecta_email():
    e = detect("Flavio.Melo+news@Gmail.com")
    assert e.type is EntityType.EMAIL
    assert e.value == "flavio.melo+news@gmail.com"
    # Gmail ignora ponto e sufixo: a forma canônica tem que colapsar as duas coisas.
    assert e.get("canonical") == "flaviomelo@gmail.com"
    assert e.get("username_guess") == "flaviomelo"


def test_detecta_telefone_br_sem_ddi():
    e = detect("(11) 98765-4321")
    assert e.type is EntityType.PHONE
    assert e.value == "+5511987654321"
    assert e.get("ddd") == "11"
    assert e.get("country") == "BR"
    assert "+5511987654321" in e.get("search_forms")


def test_telefone_fixo_nao_ganha_nono_digito():
    e = detect("1132145678")
    assert e.value == "+551132145678"
    assert e.get("local") == "32145678"


def test_ddd_invalido_nao_vira_telefone_br():
    # 00 não é DDD válido — não pode ganhar +55 automaticamente.
    e = detect("0012345678")
    assert e.get("country") != "BR" or not e.get("ddd")


def test_detecta_nome_e_gera_handles():
    e = detect("José da Silva Santos")
    assert e.type is EntityType.NAME
    assert e.get("ascii") == "jose da silva santos"
    # Partículas ("da") não entram na formação do handle.
    assert "josesantos" in e.get("username_guesses")


def test_detecta_username_e_perfil():
    assert detect("@fulano").type is EntityType.USERNAME
    assert detect("fulano123").type is EntityType.USERNAME

    p = detect("https://instagram.com/fulano_dev/")
    assert p.type is EntityType.PROFILE_URL
    assert p.get("handle") == "fulano_dev"
    assert p.get("platform") == "instagram"


def test_linkedin_pega_handle_no_segundo_segmento():
    p = detect("https://www.linkedin.com/in/joao-silva-123")
    assert p.type is EntityType.PROFILE_URL
    assert p.get("handle") == "joao-silva-123"


def test_dominio_com_br_tem_raiz_de_tres_rotulos():
    e = detect("https://blog.empresa.com.br")
    assert e.type is EntityType.DOMAIN
    assert e.get("root") == "empresa.com.br"

    # Com caminho o alvo é URL (o caminho importa para o rastreamento), mas a
    # raiz continua sendo extraída corretamente.
    u = detect("https://blog.empresa.com.br/post/1")
    assert u.type is EntityType.URL
    assert u.get("root") == "empresa.com.br"
    assert u.get("path") == "/post/1"


def test_cpf_e_cnpj_so_valem_com_digito_verificador():
    assert valid_cpf("111.444.777-35")
    assert not valid_cpf("111.111.111-11")
    assert valid_cnpj("00.000.000/0001-91")
    assert not valid_cnpj("11.111.111/1111-11")

    assert detect("111.444.777-35").type is EntityType.CPF
    assert detect("00000000000191").type is EntityType.CNPJ
    # Número inválido de 11 dígitos deve cair como telefone, não como CPF.
    assert detect("11111111111").type is not EntityType.CPF


def test_formata_cnpj():
    assert format_cnpj("00000000000191") == "00.000.000/0001-91"


def test_detecta_ip():
    assert detect("8.8.8.8").type is EntityType.IP
    assert detect("999.1.1.1").type is not EntityType.IP


def test_detect_all_extrai_de_bloco_de_texto():
    bloco = """
    Fulano de Tal — Diretor
    fulano@empresa.com.br | (11) 99876-5432
    https://linkedin.com/in/fulano
    """
    achados = detect_all(bloco)
    tipos = {e.type for e in achados}
    assert EntityType.EMAIL in tipos
    assert EntityType.PHONE in tipos
    assert EntityType.PROFILE_URL in tipos


def test_entrada_vazia_nao_quebra():
    assert detect("").type is EntityType.UNKNOWN
    assert detect("   ").type is EntityType.UNKNOWN


# ── detect_all: nome + documento colados na mesma linha ─────────────────────
# Reproduz o bug real: usuário colou "nome cpf 000..." como um alvo só de
# monitoramento, e o motor tratava a frase inteira como um "nome" literal.

def test_detect_all_separa_nome_e_cpf_sem_pontuacao():
    achados = detect_all("thiago augusto pinto gomes cpf 07268596642")
    por_tipo = {e.type: e.value for e in achados}
    assert por_tipo[EntityType.CPF] == "072.685.966-42"
    assert por_tipo[EntityType.NAME] == "thiago augusto pinto gomes"


def test_detect_all_preserva_particula_de_no_nome():
    # "de" é parte legítima do nome — não pode ser tratado como rótulo e sumir.
    achados = detect_all("Maria da Silva CPF 111.444.777-35")
    nomes = [e.value for e in achados if e.type is EntityType.NAME]
    assert nomes == ["Maria da Silva"]


def test_detect_all_reconhece_cnpj_antes_do_cpf():
    achados = detect_all("CNPJ 00.000.000/0001-91 da Empresa X Ltda")
    tipos = {e.type for e in achados}
    assert EntityType.CNPJ in tipos
    assert EntityType.CPF not in tipos  # não pode "quebrar" o CNPJ em CPF


def test_detect_all_com_email_telefone_e_nome_juntos():
    achados = detect_all("Fulano de Tal, e-mail fulano@x.com, telefone (11) 99999-8888")
    por_tipo = {e.type: e.value for e in achados}
    assert por_tipo[EntityType.EMAIL] == "fulano@x.com"
    assert por_tipo[EntityType.PHONE] == "+5511999998888"
    assert por_tipo[EntityType.NAME] == "Fulano de Tal"


def test_detect_all_string_unica_sem_rotulo_continua_funcionando():
    # Uso normal (sem nada para separar) não pode regredir.
    achados = detect_all("Maria Souza")
    assert len(achados) == 1
    assert achados[0].type is EntityType.NAME
    assert achados[0].value == "Maria Souza"
