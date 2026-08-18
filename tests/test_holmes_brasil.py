"""
Camada Brasil: número CNJ, deeplinks por tipo e casamento de nome.

Nenhum teste toca a rede — as funções que dependem de API são testadas pela
parte determinística (decodificação, filtro de homônimo, geração de link).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes.br import TRIBUNAL_CONSULTA, br_deeplinks, ddd_info, tribunal_link  # noqa: E402
from holmes.br_auto import _mesma_pessoa, _sem_acento  # noqa: E402
from holmes.cnj import format_cnj, parse, validate_dv  # noqa: E402
from holmes.connectors import connectors_for, ensure_registered  # noqa: E402
from holmes.entity import EntityType, detect  # noqa: E402

ensure_registered()

# Número real, com DV válido (TJSP).
NUM_VALIDO = "0000133-39.2025.8.26.0334"


# ── número CNJ ──────────────────────────────────────────────────────────────

def test_detecta_numero_de_processo():
    e = detect(NUM_VALIDO)
    assert e.type is EntityType.PROCESSO
    assert e.get("tribunal") == "TJSP"


def test_detecta_processo_sem_pontuacao():
    e = detect("00001333920258260334")
    assert e.type is EntityType.PROCESSO
    assert e.value == NUM_VALIDO


def test_decodifica_segmento_e_tribunal():
    casos = {
        "0000133-39.2025.8.26.0334": ("TJSP", "Justiça Estadual"),
        "0001234-56.2020.5.02.0001": ("TRT2", "Justiça do Trabalho"),
        "0001234-56.2021.4.03.6100": ("TRF3", "Justiça Federal"),
        "0001234-56.2021.8.19.0001": ("TJRJ", "Justiça Estadual"),
        "0001234-56.2021.8.13.0024": ("TJMG", "Justiça Estadual"),
    }
    for numero, (sigla, segmento) in casos.items():
        info = parse(numero)
        assert info is not None, numero
        assert info["sigla"] == sigla
        assert info["segmento"] == segmento


def test_digito_verificador_pega_numero_inventado():
    assert validate_dv(NUM_VALIDO)
    # Mesmo número com o DV trocado tem que ser rejeitado.
    assert not validate_dv("0000133-00.2025.8.26.0334")


def test_dv_invalido_vira_aviso_no_alvo():
    e = detect("0000133-00.2025.8.26.0334")
    assert e.type is EntityType.PROCESSO
    assert any("verificador" in n for n in e.notes)


def test_numero_com_tamanho_errado_nao_e_processo():
    assert detect("123456789").type is not EntityType.PROCESSO
    assert parse("123") is None


def test_formata_numero_cnj():
    assert format_cnj("00001333920258260334") == NUM_VALIDO


def test_processo_tem_conector_automatico():
    autos = [c for c in connectors_for(detect(NUM_VALIDO)) if c.mode.value == "auto"]
    assert any(c.id == "datajud" for c in autos)


# ── link do tribunal certo ──────────────────────────────────────────────────

def test_link_do_tribunal_sai_do_proprio_numero():
    url, _obs = tribunal_link("TJSP", "00001333920258260334")
    assert "esaj.tjsp.jus.br" in url
    assert "00001333920258260334" in url


def test_trt_e_trf_resolvem_para_o_pje_certo():
    url_trt, _ = tribunal_link("TRT15", "00000000000000000000")
    assert "trt15" in url_trt
    url_trf, _ = tribunal_link("TRF5", "00000000000000000000")
    assert "trf5" in url_trf


def test_tribunal_desconhecido_nao_quebra():
    assert tribunal_link(None, "123") is None


def test_deeplink_de_processo_inclui_o_tribunal():
    links = br_deeplinks(detect(NUM_VALIDO))
    rotulos = [r for r, _u, _d in links]
    assert any("TJSP" in r for r in rotulos)
    # Todo link de processo tem que carregar o número.
    assert all("0000133" in u or "00001333920258260334" in u for _r, u, _d in links)


def test_todo_template_de_tribunal_tem_placeholder():
    for sigla, modelo in TRIBUNAL_CONSULTA.items():
        assert "{num}" in modelo, sigla


# ── deeplinks brasileiros ───────────────────────────────────────────────────

def test_nome_recebe_fontes_brasileiras_essenciais():
    rotulos = " ".join(r for r, _u, _d in br_deeplinks(detect("Jose da Silva")))
    for esperado in ("Escavador", "JusBrasil", "Lattes", "Querido Diário",
                     "TJSP", "Reclame Aqui", "CADE", "INPI"):
        assert esperado in rotulos, esperado


def test_cnpj_recebe_sintegra_e_reputacao():
    rotulos = " ".join(r for r, _u, _d in br_deeplinks(detect("00.000.000/0001-91")))
    for esperado in ("Consulta Sócio", "Sintegra", "Reclame Aqui", "Querido Diário"):
        assert esperado in rotulos, esperado


def test_deeplinks_br_levam_o_alvo_na_url():
    # Descarta os que são formulário puro (captcha/SPA) — esses são links fixos.
    fixos = ("receita.fazenda.gov.br", "sintegra.fazenda", "fazenda.pr.gov.br",
             "cade.gov.br", "inpi.gov.br", "in.gov.br", "cvm.gov.br",
             "divulgacandcontas")
    for entidade in ("Jose da Silva", "00.000.000/0001-91"):
        ent = detect(entidade)
        # O alvo pode ir na URL só com dígitos ou formatado (é assim que o
        # CNPJ aparece escrito num diário oficial) — as duas formas valem.
        formas = {
            (ent.get("digits") or "")[:6],
            ent.value.split()[0][:6].replace("/", "%2F"),
        }
        formas = {f.lower() for f in formas if len(f) >= 4}
        for rotulo, url, _d in br_deeplinks(ent):
            if any(f in url for f in fixos):
                continue
            assert any(f in url.lower() for f in formas), f"{rotulo}: {url}"


def test_telefone_br_tem_ddd_mapeado():
    assert "São Paulo" in (ddd_info("11") or "")
    assert "Curitiba" in (ddd_info("41") or "")
    assert ddd_info("00") is None


# ── casamento de nome (anti-homônimo) ───────────────────────────────────────

def test_casamento_de_nome_exige_primeiro_e_ultimo():
    assert _mesma_pessoa("Benedita da Silva", "Benedita Souza da Silva")
    assert _mesma_pessoa("JOSE ALMEIDA", "josé almeida")
    # Sobrenome diferente não é a mesma pessoa.
    assert not _mesma_pessoa("Jose Almeida", "Jose Pereira")
    # Nome solto não casa com ninguém — evita enxurrada de falso positivo.
    assert not _mesma_pessoa("Jose", "Jose Almeida")


def test_remove_acento_para_comparar():
    assert _sem_acento("JOSÉ ANTÔNIO") == "jose antonio"


# ── registro ────────────────────────────────────────────────────────────────

def test_conectores_brasileiros_registrados():
    ids = {c.id for c in connectors_for(detect("Jose da Silva"))}
    assert {"congresso", "querido_diario", "portal_nome"} <= ids

    ids_cnpj = {c.id for c in connectors_for(detect("00.000.000/0001-91"))}
    assert {"receita_cnpj", "querido_diario", "portal_cnpj"} <= ids_cnpj

    ids_dom = {c.id for c in connectors_for(detect("empresa.com.br"))}
    assert "registrobr" in ids_dom


def test_portal_da_transparencia_e_pulado_sem_chave():
    import os as _os

    if _os.environ.get("PORTAL_TRANSPARENCIA_KEY"):
        return  # ambiente com chave: o teste não se aplica
    conn = [c for c in connectors_for(detect("Jose da Silva")) if c.id == "portal_nome"][0]
    res = conn.execute(detect("Jose da Silva"))
    assert res.status == "pulado"
    assert "chave" in (res.skipped_reason or "")
