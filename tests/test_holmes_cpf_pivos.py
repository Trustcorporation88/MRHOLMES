"""
CPF: consultas em registro público, classificação jurídica e os pivôs que
saem do que foi citado junto do alvo (processo, CNPJ, empresa).

Nenhum teste toca a rede.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import pivot as pivot_mod  # noqa: E402
from holmes.entity import EntityType, detect  # noqa: E402
from holmes.findings import Confidence, Finding, FindingKind  # noqa: E402
from holmes.serp import (  # noqa: E402
    SerpHit,
    build_queries,
    extrair_cnpjs,
    extrair_empresas,
    extrair_processos,
    hits_to_findings,
    is_company_name,
)

CPF = "529.982.247-25"          # sintético, dígitos válidos
PROCESSO = "1001234-35.2025.8.26.0095"   # sintético, DV válido
CNPJ = "11.222.333/0001-81"     # sintético, DV válido


# ── consultas ───────────────────────────────────────────────────────────────

def test_cpf_procura_em_registro_publico():
    qs = build_queries(detect(CPF))
    assert any("site:jusbrasil.com.br" in q for q in qs)
    assert any("site:jus.br" in q for q in qs)
    assert any("diário oficial" in q for q in qs)
    assert any("licitação" in q for q in qs)
    assert len(qs) >= 8


def test_razao_social_busca_cnpj_e_nao_rede_social():
    qs = build_queries(detect("Acme Comercio de Oleos LTDA"))
    assert any("CNPJ" in q for q in qs)
    assert not any("linkedin.com" in q or "instagram.com" in q for q in qs)


def test_nome_de_pessoa_segue_com_as_consultas_de_sempre():
    assert not is_company_name("Fulano de Tal")
    assert any("site:linkedin.com" in q for q in build_queries(detect("Fulano de Tal")))


# ── extração ────────────────────────────────────────────────────────────────

def test_extrai_empresa_de_titulo_de_processo():
    assert extrair_empresas(
        "escavador: citroleo industria e comercio de oleos essenciais ltda x thiago ..."
    ) == ["Citroleo Industria E Comercio De Oleos Essenciais LTDA"]
    assert extrair_empresas("Processo contra ACME Comércio S/A - JusBrasil") == ["ACME Comércio S/A"]
    assert extrair_empresas("Uma notícia qualquer sem empresa") == []


def test_extrai_so_numero_de_processo_e_cnpj_validos():
    assert extrair_processos(f"autos {PROCESSO} e 1001234-36.2025.8.26.0095") == [PROCESSO]
    assert extrair_cnpjs(f"CNPJ {CNPJ} e 11.222.333/0001-80") == [CNPJ]


# ── classificação ───────────────────────────────────────────────────────────

def _hit(**kw):
    base = dict(title="", url="", snippet="", position=1, engine="serper")
    base.update(kw)
    return SerpHit(**base)


def test_processo_no_escavador_vira_juridico_e_nao_conta():
    hits = [_hit(
        title="acme comercio de oleos ltda x fulano",
        url="https://www.escavador.com/processos-judiciais/123-abc",
        snippet=f"... {CPF.replace('.', '').replace('-', '')} execução, autos {PROCESSO}, CNPJ {CNPJ}",
    )]
    achados = hits_to_findings(hits, detect(CPF))
    kinds = [f.kind for f in achados]
    assert FindingKind.ACCOUNT not in kinds
    assert FindingKind.LEGAL in kinds
    assert any(f.kind is FindingKind.LEGAL and (f.raw or {}).get("cnj") == PROCESSO for f in achados)
    assert any(f.kind is FindingKind.DOCUMENT and f.value == CNPJ for f in achados)
    assert any(f.kind is FindingKind.COMPANY and "Acme" in f.value for f in achados)


def test_perfil_de_pessoa_no_escavador_continua_conta():
    hits = [_hit(title="Fulano de Tal | Escavador",
                 url="https://www.escavador.com/sobre/123/fulano-de-tal", snippet="Fulano de Tal")]
    kinds = {f.kind for f in hits_to_findings(hits, detect("Fulano de Tal"))}
    assert FindingKind.ACCOUNT in kinds
    assert FindingKind.LEGAL not in kinds


def test_empresa_so_e_extraida_quando_o_alvo_aparece_no_resultado():
    hits = [_hit(title="acme comercio de oleos ltda x beltrano",
                 url="https://www.escavador.com/processos-judiciais/9",
                 snippet="nada do alvo aqui")]
    achados = hits_to_findings(hits, detect(CPF))
    assert not any(f.kind is FindingKind.COMPANY for f in achados)


# ── pivôs ───────────────────────────────────────────────────────────────────

def _f(kind, value, conf=Confidence.LIKELY, raw=None):
    return Finding(kind=kind, value=value, source="serp:serper", source_label="Busca",
                   confidence=conf, raw=raw or {})


def test_processo_citado_vira_pivo_para_o_datajud():
    pivos = pivot_mod.from_findings(
        [_f(FindingKind.LEGAL, f"Processo {PROCESSO}", raw={"cnj": PROCESSO})], 1, detect(CPF))
    assert [p.entity.type for p in pivos] == [EntityType.PROCESSO]


def test_cnpj_citado_vira_pivo_para_a_receita():
    pivos = pivot_mod.from_findings([_f(FindingKind.DOCUMENT, CNPJ)], 1, detect(CPF))
    assert [p.entity.type for p in pivos] == [EntityType.CNPJ]


def test_empresa_citada_vira_pivo_de_razao_social():
    pivos = pivot_mod.from_findings(
        [_f(FindingKind.COMPANY, "Acme Comercio de Oleos LTDA")], 1, detect(CPF))
    assert len(pivos) == 1 and pivos[0].entity.type is EntityType.NAME


def test_achado_fraco_nao_vira_pivo():
    fracos = [
        _f(FindingKind.COMPANY, "Acme Comercio de Oleos LTDA", Confidence.POSSIBLE),
        _f(FindingKind.DOCUMENT, CNPJ, Confidence.POSSIBLE),
        _f(FindingKind.LEGAL, "x", Confidence.POSSIBLE, raw={"cnj": PROCESSO}),
    ]
    assert pivot_mod.from_findings(fracos, 1, detect(CPF)) == []


def test_cpf_de_terceiro_citado_nao_vira_pivo():
    assert pivot_mod.from_findings([_f(FindingKind.DOCUMENT, "111.444.777-35")], 1, detect(CPF)) == []


# ── razão social resolve o CNPJ no mesmo salto ──────────────────────────────

def test_razao_social_consulta_a_receita_pelo_cnpj_mais_citado(monkeypatch):
    from holmes import br
    from holmes.connectors import _resolver_cnpj

    chamados = []

    def _fake(entity):
        chamados.append(entity.value)
        return [_f(FindingKind.NAME, "Sócio Exemplo", Confidence.CONFIRMED)]

    monkeypatch.setattr(br, "cnpj_findings", _fake)
    achados = [_f(FindingKind.DOCUMENT, CNPJ, raw={"tipo": "cnpj"}) for _ in range(2)]
    achados.append(_f(FindingKind.DOCUMENT, "11.444.777/0001-61", raw={"tipo": "cnpj"}))
    extra = _resolver_cnpj(achados)
    assert chamados == [CNPJ]
    assert extra and extra[0].value == "Sócio Exemplo"
