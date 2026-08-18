"""
Conectores, pivô, consolidação e resiliência.

Nenhum teste aqui toca a rede: conector é injetado no registro, para que a
suíte rode offline e no CI.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import pivot as pivot_mod  # noqa: E402
from holmes.connectors import Connector, Mode, ensure_registered, registry_stats  # noqa: E402
from holmes.connectors.base import connectors_for  # noqa: E402
from holmes.connectors.catalog import _fmt  # noqa: E402
from holmes.dossier import Dossier  # noqa: E402
from holmes.entity import EntityType, detect  # noqa: E402
from holmes.findings import Confidence, Finding, FindingKind  # noqa: E402
from holmes.serp import SerpHit, build_queries, hits_to_findings  # noqa: E402

ensure_registered()


# ── registro ────────────────────────────────────────────────────────────────

def test_registro_tem_cobertura_para_todo_tipo_principal():
    for alvo in ["Fulano de Tal", "a@b.com", "+5511999999999", "@handle",
                 "empresa.com.br", "8.8.8.8", "00.000.000/0001-91"]:
        conns = connectors_for(detect(alvo))
        assert conns, f"nenhum conector aceita {alvo}"


def test_todo_alvo_tem_pelo_menos_uma_fonte_automatica():
    for alvo in ["Fulano de Tal", "a@b.com", "+5511999999999", "@handle", "empresa.com.br"]:
        autos = [c for c in connectors_for(detect(alvo)) if c.mode is Mode.AUTO]
        assert autos, f"{alvo} não tem fonte automática"


def test_catalogo_migrado_tem_volume_esperado():
    stats = registry_stats()
    assert stats["total"] >= 90
    assert stats["por_modo"]["deeplink"] >= 50


# ── deeplinks: o coração da mudança ─────────────────────────────────────────

def test_deeplink_leva_o_alvo_e_nao_a_home():
    ent = detect("+5511987654321")
    url = _fmt("https://sync.me/search/?number={e164}", ent)
    assert url is not None
    assert "5511987654321" in url
    assert url != "https://sync.me/"


def test_deeplink_escapa_caracteres():
    ent = detect("José da Silva")
    url = _fmt("https://www.google.com/search?q=%22{value+}%22", ent)
    assert " " not in url
    assert "Jos" in url


def test_deeplink_nao_e_gerado_sem_a_variavel():
    # Nome não tem 'digits'; o template tem que se recusar a gerar link quebrado.
    assert _fmt("https://x.com/{digits}", detect("Fulano de Tal")) is None


def test_conector_deeplink_produz_finding_com_url():
    conn = [c for c in connectors_for(detect("+5511987654321")) if c.id == "syncme"][0]
    res = conn.execute(detect("+5511987654321"))
    assert res.ok
    assert res.findings[0].url and "5511987654321" in res.findings[0].url


# ── resiliência ─────────────────────────────────────────────────────────────

def test_conector_que_explode_nao_derruba_a_investigacao():
    def _boom(_entity):
        raise RuntimeError("fonte fora do ar")

    conn = Connector(
        id="teste_boom", label="Fonte quebrada", mode=Mode.AUTO,
        accepts=(EntityType.NAME,), run=_boom,
    )
    res = conn.execute(detect("Fulano de Tal"))
    assert res.ok is False
    assert "fonte fora do ar" in (res.error or "")
    assert res.status == "erro"


def test_conector_sem_chave_e_pulado_com_motivo_explicito():
    conn = Connector(
        id="teste_chave", label="Precisa de chave", mode=Mode.AUTO,
        accepts=(EntityType.NAME,), requires_key="chave_inexistente_xyz",
        run=lambda e: [],
    )
    res = conn.execute(detect("Fulano de Tal"))
    assert res.status == "pulado"
    assert "chave" in (res.skipped_reason or "")


def test_conector_ignora_alvo_de_tipo_errado():
    conn = Connector(
        id="teste_tipo", label="Só e-mail", mode=Mode.AUTO,
        accepts=(EntityType.EMAIL,), run=lambda e: [],
    )
    res = conn.execute(detect("Fulano de Tal"))
    assert res.status == "pulado"


# ── consolidação e confiança ────────────────────────────────────────────────

def _f(kind, value, source, conf=Confidence.POSSIBLE, url=None):
    return Finding(kind=kind, value=value, source=source, confidence=conf, url=url)


def test_corroboracao_entre_fontes_aumenta_a_confianca():
    d = Dossier(entity=detect("Fulano de Tal"))
    from holmes.findings import ConnectorResult

    d.add_results([ConnectorResult(
        connector_id="a", connector_label="A", ok=True,
        findings=[_f(FindingKind.EMAIL, "x@y.com", "a")],
    )])
    d.consolidate()
    sozinho = d.section(FindingKind.EMAIL)[0].score

    d2 = Dossier(entity=detect("Fulano de Tal"))
    d2.add_results([ConnectorResult(
        connector_id="a", connector_label="A", ok=True,
        findings=[
            _f(FindingKind.EMAIL, "x@y.com", "a"),
            _f(FindingKind.EMAIL, "X@Y.com", "b"),
            _f(FindingKind.EMAIL, "x@y.com ", "c"),
        ],
    )])
    d2.consolidate()
    fato = d2.section(FindingKind.EMAIL)[0]

    # Três fontes viram UM fato, com score maior que o da fonte isolada.
    assert len(d2.section(FindingKind.EMAIL)) == 1
    assert len(fato.sources) == 3
    assert fato.score > sozinho


def test_dedup_normaliza_telefone_escrito_de_formas_diferentes():
    from holmes.findings import ConnectorResult

    d = Dossier(entity=detect("Fulano de Tal"))
    d.add_results([ConnectorResult(
        connector_id="a", connector_label="A", ok=True,
        findings=[
            _f(FindingKind.PHONE, "+55 11 98765-4321", "a"),
            _f(FindingKind.PHONE, "5511987654321", "b"),
        ],
    )])
    d.consolidate()
    assert len(d.section(FindingKind.PHONE)) == 1


def test_confirmada_pontua_mais_que_indicio():
    from holmes.findings import ConnectorResult

    d = Dossier(entity=detect("Fulano de Tal"))
    d.add_results([ConnectorResult(
        connector_id="a", connector_label="A", ok=True,
        findings=[
            _f(FindingKind.NAME, "Certo", "a", Confidence.CONFIRMED),
            _f(FindingKind.NAME, "Duvidoso", "b", Confidence.UNVERIFIED),
        ],
    )])
    d.consolidate()
    nomes = {f.value: f.score for f in d.section(FindingKind.NAME)}
    assert nomes["Certo"] > nomes["Duvidoso"]


def test_dossie_exporta_nos_tres_formatos():
    from holmes.findings import ConnectorResult

    d = Dossier(entity=detect("Fulano de Tal"))
    d.add_results([ConnectorResult(
        connector_id="a", connector_label="A", ok=True,
        findings=[_f(FindingKind.EMAIL, "x@y.com", "a", url="https://y.com")],
    )])
    d.consolidate()
    assert "x@y.com" in d.to_markdown()
    assert "x@y.com" in d.to_html()
    assert "x@y.com" in d.to_json()
    assert d.to_html().startswith("<!DOCTYPE html>")


def test_html_escapa_injecao():
    from holmes.findings import ConnectorResult

    d = Dossier(entity=detect("Fulano de Tal"))
    d.add_results([ConnectorResult(
        connector_id="a", connector_label="A", ok=True,
        findings=[_f(FindingKind.NOTE, "<script>alert(1)</script>", "a")],
    )])
    d.consolidate()
    assert "<script>alert(1)</script>" not in d.to_html()
    assert "&lt;script&gt;" in d.to_html()


# ── pivô ────────────────────────────────────────────────────────────────────

def test_email_pivota_para_username_e_dominio_corporativo():
    pivos = pivot_mod.from_entity(detect("joao.silva@empresa.com.br"))
    tipos = {p.entity.type for p in pivos}
    assert EntityType.USERNAME in tipos
    assert EntityType.DOMAIN in tipos


def test_email_gratuito_nao_pivota_o_dominio():
    pivos = pivot_mod.from_entity(detect("joao.silva@gmail.com"))
    assert all(p.entity.value != "gmail.com" for p in pivos)


def test_findings_geram_pivo_com_motivo():
    achados = [_f(FindingKind.EMAIL, "novo@alvo.com", "gravatar", Confidence.CONFIRMED)]
    pivos = pivot_mod.from_findings(achados, hop=1)
    assert pivos
    assert pivos[0].entity.value == "novo@alvo.com"
    assert pivos[0].reason  # todo pivô explica por que existe


def test_pivo_descarta_nome_lixo():
    # Nome afirmado pela fonte (ex.: sócio na Receita) pivota; título de
    # página não.
    achados = [
        _f(FindingKind.NAME, "Login", "receita_cnpj", Confidence.CONFIRMED),
        _f(FindingKind.NAME, "Perfil do Usuario", "receita_cnpj", Confidence.CONFIRMED),
        _f(FindingKind.NAME, "Maria Aparecida Souza", "receita_cnpj", Confidence.CONFIRMED),
    ]
    valores = {p.entity.value for p in pivot_mod.from_findings(achados, hop=1)}
    assert "Maria Aparecida Souza" in valores
    assert "Login" not in valores
    assert "Perfil do Usuario" not in valores


# ── anti-deriva: o bug do "abjur" ───────────────────────────────────────────
# Numa busca por "Benedita da Silva", o motor achou github.com/abjur (uma
# associação de jurimetria que só MENCIONAVA a pessoa numa página), tratou o
# handle como sendo dela e varreu 90 sites — 144 perfis de outra entidade
# entraram no dossiê. Resultado de busca prova menção, não vínculo.

def test_perfil_de_busca_sem_parentesco_nao_pivota():
    alvo = detect("Benedita da Silva")
    achado = _f(FindingKind.ACCOUNT, "GitHub: abjur", "serp:serper",
                Confidence.LIKELY, url="https://github.com/abjur")
    assert pivot_mod.from_findings([achado], hop=1, target=alvo) == []


def test_perfil_de_busca_com_parentesco_pivota():
    alvo = detect("Benedita da Silva")
    achado = _f(FindingKind.ACCOUNT, "Instagram: blogdabenedita", "serp:serper",
                Confidence.LIKELY, url="https://instagram.com/blogdabenedita")
    pivos = pivot_mod.from_findings([achado], hop=1, target=alvo)
    assert [p.entity.value for p in pivos] == ["blogdabenedita"]


def test_perfil_confirmado_pela_plataforma_pivota_sempre():
    # WhatsMyName/GitHub confirmam o handle na origem: não precisa parentesco.
    alvo = detect("qualquercoisa")
    achado = _f(FindingKind.ACCOUNT, "GitHub: xyz", "github",
                Confidence.CONFIRMED, url="https://github.com/xyz")
    assert pivot_mod.from_findings([achado], hop=1, target=alvo)


def test_email_de_snippet_sem_parentesco_nao_pivota():
    alvo = detect("Benedita da Silva")
    # E-mail de contato do site que menciona o alvo — não é o e-mail dela.
    ruido = _f(FindingKind.EMAIL, "contato@abj.org.br", "serp:serper")
    assert pivot_mod.from_findings([ruido], hop=1, target=alvo) == []
    # Já um e-mail com o nome dela dentro, sim.
    bom = _f(FindingKind.EMAIL, "benedita.silva@camara.leg.br", "serp:serper")
    assert pivot_mod.from_findings([bom], hop=1, target=alvo)


def test_dominio_de_busca_nao_pivota():
    alvo = detect("Benedita da Silva")
    achado = _f(FindingKind.DOMAIN, "abj.org.br", "serp:serper", Confidence.LIKELY)
    assert pivot_mod.from_findings([achado], hop=1, target=alvo) == []
    # Domínio afirmado como do alvo (MX do e-mail dele) continua pivotando.
    ok = _f(FindingKind.DOMAIN, "empresa.com.br", "email_infra", Confidence.CONFIRMED)
    assert pivot_mod.from_findings([ok], hop=1, target=alvo)


def test_telefone_de_snippet_nao_pivota():
    alvo = detect("Benedita da Silva")
    achado = _f(FindingKind.PHONE, "+5511999998888", "serp:serper")
    assert pivot_mod.from_findings([achado], hop=1, target=alvo) == []


def test_parentesco_reconhece_abreviacao_e_rejeita_estranho():
    alvo = detect("Benedita da Silva")
    for relacionado in ("blogdabenedita", "instadabene", "beneditasilva", "silvabene"):
        assert pivot_mod._parentesco(relacionado, alvo), relacionado
    for estranho in ("abjur", "torvalds", "nubank", "xpto"):
        assert not pivot_mod._parentesco(estranho, alvo), estranho


def test_parentesco_sem_alvo_e_conservador():
    # Sem alvo de referência não há como medir parentesco: nega.
    assert not pivot_mod._parentesco("qualquer", None)


def test_pivo_nao_repete_alvo_ja_investigado():
    achados = [_f(FindingKind.EMAIL, "x@y.com", "a")]
    pivos = pivot_mod.from_findings(achados, hop=1)
    filtrados = pivot_mod.dedupe_and_rank(pivos, already_seen={"email:x@y.com"})
    assert filtrados == []


def test_pivo_respeita_o_limite_por_salto():
    achados = [_f(FindingKind.EMAIL, f"a{i}@y.com", "a") for i in range(20)]
    pivos = pivot_mod.dedupe_and_rank(pivot_mod.from_findings(achados, 1), set(), limit=3)
    assert len(pivos) == 3


# ── dorks e classificação de SERP ───────────────────────────────────────────

def test_dorks_sao_especificos_por_tipo():
    nome = build_queries(detect("Fulano de Tal"))
    assert any("site:linkedin.com" in q for q in nome)
    assert any('"Fulano de Tal"' in q for q in nome)

    dom = build_queries(detect("empresa.com.br"))
    assert any(q.startswith("site:") for q in dom)

    tel = build_queries(detect("+5511987654321"))
    assert any("5511987654321" in q for q in tel)


def test_resultado_em_plataforma_conhecida_vira_conta():
    hits = [
        SerpHit(title="Fulano de Tal | LinkedIn",
                url="https://www.linkedin.com/in/fulano", snippet="Diretor", position=1),
        SerpHit(title="Notícia qualquer", url="https://jornal.com.br/x",
                snippet="texto", position=2),
    ]
    kinds = {f.kind for f in hits_to_findings(hits, detect("Fulano de Tal"))}
    assert FindingKind.ACCOUNT in kinds
    assert FindingKind.WEB_RESULT in kinds


def test_email_no_snippet_e_extraido_como_finding():
    hits = [SerpHit(title="Contato", url="https://site.com",
                    snippet="fale com fulano@empresa.com.br", position=1)]
    achados = hits_to_findings(hits, detect("Fulano de Tal"))
    assert any(f.kind is FindingKind.EMAIL and f.value == "fulano@empresa.com.br"
               for f in achados)
