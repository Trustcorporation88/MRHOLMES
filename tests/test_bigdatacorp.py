from unittest import mock

from holmes import bigdatacorp as bdc
from holmes.entity import detect
from holmes.findings import FindingKind

PESSOA = {
    "BasicData": {"Name": "FULANO DE TAL", "BirthDate": "1980-05-02T00:00:00Z", "Age": 46,
                  "TaxIdStatus": "REGULAR", "MotherName": "MARIA DE TAL", "FatherName": ""},
    "ExtendedPhones": {"Phones": [{"AreaCode": "11", "Number": "999990000", "Type": "MOBILE"}]},
    "ExtendedEmails": {"Emails": [{"EmailAddress": "Fulano@Exemplo.com", "Type": "PERSONAL"}]},
    "ExtendedAddresses": {"Addresses": [{"Typology": "RUA", "AddressMain": "DAS FLORES", "Number": "10",
                                         "Neighborhood": "CENTRO", "City": "SAO PAULO", "State": "SP",
                                         "ZipCode": "01001000", "Type": "HOME"}]},
    "BusinessRelationships": {"BusinessRelationships": [
        {"RelatedEntityName": "ACME LTDA", "RelatedEntityTaxIdNumber": "11222333000181",
         "RelatedEntityTaxIdType": "CNPJ", "RelationshipType": "OWNERSHIP",
         "RelationshipStartDate": "2015-03-02T00:00:00Z", "RelationshipEndDate": "9999-12-31T00:00:00Z"},
        {"RelatedEntityName": "FULANO DE TAL", "RelatedEntityTaxIdNumber": "52998224725"},
    ]},
    "KycData": {"IsCurrentlyPEP": False, "IsCurrentlySanctioned": False},
    "_falhas": [],
}


def _valores(fs, kind):
    return [f.value for f in fs if f.kind is kind]


def test_pessoa_vira_achados():
    fs = bdc.para_findings(PESSOA, "529.982.247-25")
    assert "FULANO DE TAL" in _valores(fs, FindingKind.NAME)
    assert "MARIA DE TAL" in _valores(fs, FindingKind.NAME)
    assert _valores(fs, FindingKind.PHONE) == ["(11) 999990000"]
    assert _valores(fs, FindingKind.EMAIL) == ["fulano@exemplo.com"]
    assert _valores(fs, FindingKind.ADDRESS) == ["RUA DAS FLORES, 10, CENTRO, SAO PAULO/SP, CEP 01001-000"]
    empresa = next(f for f in fs if f.kind is FindingKind.COMPANY)
    assert empresa.value == "ACME LTDA" and "Sócio/Proprietário" in empresa.detail and "atual" in empresa.detail
    assert "11.222.333/0001-81" in _valores(fs, FindingKind.DOCUMENT)
    # a própria pessoa não aparece como vínculo dela mesma
    assert "529.982.247-25" not in _valores(fs, FindingKind.DOCUMENT)
    assert "Sem apontamentos de PEP ou sanções" in _valores(fs, FindingKind.NOTE)
    assert all(f.source == "bigdatacorp" for f in fs)


def test_empresa_com_socios_no_qsa():
    r = {"DynamicQSAData": {
        "BasicData": {"OfficialName": "ACME LTDA", "TradeName": "Acme", "TaxIdStatus": "ATIVA",
                      "TaxRegimes": {"Simples": True}, "AdditionalOutputData": {"Capital": "50000"}},
        "Relationships": {"CurrentRelationships": [
            {"RelatedEntityName": "FULANO DE TAL", "RelatedEntityTaxIdNumber": "52998224725",
             "RelatedEntityTaxIdType": "CPF", "RelationshipName": "Sócio-Administrador",
             "RelationshipStartDate": "2015-03-02T00:00:00Z"}],
            "HistoricalRelationships": [
            {"RelatedEntityName": "BELTRANO", "RelationshipType": "OWNERSHIP",
             "RelationshipEndDate": "2018-01-01T00:00:00Z"}]}}}
    fs = bdc.para_findings(r, "11222333000181")
    razao = next(f for f in fs if f.value == "ACME LTDA")
    assert "optante do Simples" in razao.detail and "R$ 50.000,00" in razao.detail
    socio = next(f for f in fs if f.value == "FULANO DE TAL")
    assert socio.kind is FindingKind.NAME and "Sócio-Administrador" in socio.detail
    assert "529.982.247-25" in _valores(fs, FindingKind.DOCUMENT)
    antigo = next(f for f in fs if f.value == "BELTRANO")
    assert "encerrado" in antigo.detail and "até 01/01/2018" in antigo.detail


def test_processos_e_parentes():
    r = {"Lawsuits": {"TotalLawsuits": 2, "TotalLawsuitsAsAuthor": 0, "TotalLawsuitsAsDefendant": 2,
                      "Lawsuits": [{"Number": "0001234-56.2020.8.26.0100", "Type": "CIVEL", "CourtName": "TJSP",
                                    "State": "SP", "Status": "ATIVO", "NoticeDate": "2020-04-13T00:00:00Z"}]},
         "RelatedPeople": {"PersonalRelationships": [
             {"RelatedEntityName": "MARIA DE TAL", "RelatedEntityTaxIdNumber": "11144477735",
              "RelationshipType": "MOTHER"}]}}
    fs = bdc.para_findings(r, "52998224725", "completa")
    proc = next(f for f in fs if f.kind is FindingKind.LEGAL)
    assert proc.value == "Processo 0001234-56.2020.8.26.0100"
    assert "TJSP/SP" in proc.detail and "13/04/2020" in proc.detail  # sem erro de fuso
    assert "2 processo(s) judicial(is)" in _valores(fs, FindingKind.NOTE)
    mae = next(f for f in fs if f.value == "MARIA DE TAL")
    assert "Mãe" in mae.detail
    assert "(pesquisa completa)" in mae.source_label


def test_consultar_monta_a_chamada_e_le_falhas():
    resposta = {"Result": [{"BasicData": {"Name": "X"}}],
                "Status": {"basic_data": [{"Code": 0}], "kyc": [{"Code": -1200, "Message": "sem acesso"}]}}
    with mock.patch.object(bdc, "configurado", return_value=True), \
         mock.patch.object(bdc.net, "get_key", side_effect=lambda k: {"bigdatacorp_token": "tok",
                                                                      "bigdatacorp_tokenid": "tid"}[k]), \
         mock.patch.object(bdc.net, "post_json", return_value=resposta) as post:
        r = bdc.consultar("529.982.247-25", "principais")
    url = post.call_args.args[0]
    kw = post.call_args.kwargs
    assert url == "https://plataforma.bigdatacorp.com.br/pessoas"
    assert kw["payload"]["q"] == "doc{52998224725}"
    assert "business_relationships" in kw["payload"]["Datasets"]
    assert kw["headers"]["AccessToken"] == "tok" and kw["headers"]["TokenId"] == "tid"
    assert r["_falhas"] == ["kyc: sem acesso"]


def test_consultar_sem_resultado_levanta_com_o_motivo():
    with mock.patch.object(bdc, "configurado", return_value=True), \
         mock.patch.object(bdc.net, "get_key", return_value="x"), \
         mock.patch.object(bdc.net, "post_json",
                           return_value={"Result": [], "Status": {"login": [{"Code": -100, "Message": "token inválido"}]}}):
        try:
            bdc.consultar("11222333000181", "processos")
            assert False, "devia levantar"
        except RuntimeError as exc:
            assert "token inválido" in str(exc)


def test_buscar_nunca_levanta():
    with mock.patch.object(bdc, "consultar", side_effect=RuntimeError("fora do ar")):
        res = bdc.buscar(detect("11.222.333/0001-81"), "completa")
    assert not res.ok and res.error == "fora do ar" and res.connector_id == "bigdatacorp_completa"


def test_conector_so_roda_no_alvo_e_nao_nos_pivos():
    from holmes.connectors import ensure_registered
    from holmes.connectors.base import get_connector
    from holmes import orchestrator

    ensure_registered()
    c = get_connector("bigdatacorp")
    assert c.on_pivots is False and c.cost == "pago"
    ent = detect("529.982.247-25")
    with mock.patch.object(orchestrator, "connectors_for", return_value=[c]):
        assert orchestrator._run_batch(ent, set(), orchestrator.InvestigationConfig(), None, 0, 0, True) == []
