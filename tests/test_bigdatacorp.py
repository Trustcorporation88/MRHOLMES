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


# ── localizador: telefone, e-mail ou nome → quem é ──────────────────────────

def _basico(nome, cpf, **extra):
    return {"BasicData": {"Name": nome, "TaxIdNumber": cpf, "BirthDate": "1980-05-02T00:00:00Z",
                          "Age": 46, "MotherName": "MARIA DE TAL", "TaxIdStatus": "REGULAR", **extra}}


def test_telefone_devolve_o_dono_com_cpf_e_contatos():
    pessoa = {**PESSOA, **_basico("FULANO DE TAL", "52998224725")}
    fs = bdc.localizar_findings([pessoa], [], "telefone")
    doc = next(f for f in fs if f.kind is FindingKind.DOCUMENT and f.value == "529.982.247-25")
    assert "FULANO DE TAL" in doc.detail and "mãe MARIA DE TAL" in doc.detail
    assert doc.raw["candidato"] and doc.raw["documento"] == "52998224725"
    dono = next(f for f in fs if f.kind is FindingKind.NAME and f.value == "FULANO DE TAL")
    assert "Cadastro ligado a este telefone" in dono.detail
    # os outros contatos e o endereço do dono entram junto, com o nome dele
    assert "fulano@exemplo.com" in _valores(fs, FindingKind.EMAIL)
    endereco = next(f for f in fs if f.kind is FindingKind.ADDRESS)
    assert endereco.detail.endswith("de FULANO DE TAL")
    # a mãe aparece, mas não como confirmada (não vira pivô)
    mae = next(f for f in fs if f.value == "MARIA DE TAL")
    assert mae.confidence.value == "provavel"


def test_nome_com_homonimos_separa_por_cpf_e_nao_detalha():
    a = _basico("JOSE DA SILVA", "52998224725", NumberOfFullNameNamesakes=1200)
    b = _basico("JOSE DA SILVA", "11144477735", NumberOfFullNameNamesakes=1200)
    fs = bdc.localizar_findings([a, b], [], "nome", detalhar=False)
    assert _valores(fs, FindingKind.DOCUMENT) == ["529.982.247-25", "111.444.777-35"]
    assert _valores(fs, FindingKind.NAME) == []  # o valor repetiria o próprio alvo
    assert "1200 pessoas têm este nome exato no Brasil" in _valores(fs, FindingKind.NOTE)
    assert len(_valores(fs, FindingKind.NOTE)) == 1


def test_empresa_achada_pelo_telefone_vira_pivo_de_cnpj():
    empresa = {"BasicData": {"OfficialName": "ACME LTDA", "TradeName": "Acme", "TaxIdNumber": "11222333000181",
                             "TaxIdStatus": "ATIVA", "HeadquarterState": "SP"}}
    fs = bdc.localizar_findings([], [empresa], "telefone")
    razao = next(f for f in fs if f.kind is FindingKind.COMPANY)
    assert razao.value == "ACME LTDA" and "CNPJ 11.222.333/0001-81" in razao.detail
    cnpj = next(f for f in fs if f.kind is FindingKind.DOCUMENT)
    assert cnpj.value == "11.222.333/0001-81" and cnpj.confidence.value == "confirmada"


def test_chaves_da_consulta_por_tipo_de_alvo():
    assert bdc._chave_e_dado(detect("(11) 98765-4321")) == (
        ["phone{11987654321}", "phone{1187654321}"], "telefone")
    assert bdc._chave_e_dado(detect("Fulano@Exemplo.com")) == (["email{fulano@exemplo.com}"], "e-mail")
    assert bdc._chave_e_dado(detect("Fulano de Tal"))[1] == "nome"
    assert bdc._chave_e_dado(detect("529.982.247-25")) == ([], "")


def test_localizar_consulta_pessoas_e_empresas_e_tenta_sem_o_nono_digito():
    chamadas = []

    def falso(tipo, q, datasets, limite):
        chamadas.append((tipo, q, limite))
        if q == "phone{1187654321}" and tipo == "pessoas":
            return [_basico("FULANO DE TAL", "52998224725")]
        return []

    with mock.patch.object(bdc, "_consultar_chave", side_effect=falso):
        fs = list(bdc.localizar(detect("11 98765-4321")))
    assert [c[:2] for c in chamadas] == [
        ("pessoas", "phone{11987654321}"), ("empresas", "phone{11987654321}"),
        ("pessoas", "phone{1187654321}"), ("empresas", "phone{1187654321}")]
    assert all(c[2] == bdc.LIMITE_CONTATO for c in chamadas)
    assert "FULANO DE TAL" in _valores(fs, FindingKind.NAME)


def test_nome_unico_ja_traz_a_ficha_completa():
    with mock.patch.object(bdc, "_consultar_chave", return_value=[_basico("FULANO DE TAL", "52998224725")]), \
         mock.patch.object(bdc, "consultar", return_value=dict(PESSOA)) as completa:
        fs = list(bdc.localizar(detect("Fulano de Tal")))
    completa.assert_called_once_with("52998224725", "principais")
    assert "529.982.247-25" in _valores(fs, FindingKind.DOCUMENT)
    assert "fulano@exemplo.com" in _valores(fs, FindingKind.EMAIL)


def test_conector_do_localizador_aceita_telefone_email_e_nome():
    from holmes.connectors import ensure_registered
    from holmes.connectors.base import get_connector

    ensure_registered()
    c = get_connector("bigdatacorp_localizar")
    assert c and not c.on_pivots and c.cost == "pago"
    for alvo in ("11 98765-4321", "a@b.com", "Fulano de Tal"):
        assert c.handles(detect(alvo))
    assert not c.handles(detect("529.982.247-25"))


# ── placa ───────────────────────────────────────────────────────────────────

PLACA = {
    "TotalOwnersInLifetime": 2, "CurrentlyHasRestrictions": False, "PreviouslyHadRestrictions": True,
    "VehicleInfo": [{"Brand": "GM", "Model": "CLASSIC", "Version": "SPIRIT", "FabricationYear": "2005",
                     "ModelYear": "2006", "Type": "PASSAGEIRO", "Fuel": "GASOL/GNV", "CylinderCapacity": "1000",
                     "Chassi": "*****41594", "LicenseLastYear": "2020"}],
    "VehicleHistory": [
        {"Color": "PRATA", "Location": "SAO JOAO DE MERITI", "State": "RJ", "OwnerFirstName": "PA*LO"},
        {"Color": "Prata", "Location": "SAO JOAO DE MERITI", "State": "RJ", "OwnerFirstName": ""},
    ],
}


def test_placa_vira_veiculo_local_e_nome_parcial_sem_pivo():
    fs = bdc.placa_findings(PLACA, "ABC1D23")
    veiculo = next(f for f in fs if f.value.startswith("Veículo:"))
    assert veiculo.value == "Veículo: GM CLASSIC SPIRIT"
    assert "2005/2006" in veiculo.detail and "chassi *****41594" in veiculo.detail
    assert _valores(fs, FindingKind.ADDRESS) == ["SAO JOAO DE MERITI/RJ"]
    # o primeiro nome do dono é NOTE: um NAME viraria pivô e investigaria um nome pela metade
    assert "Primeiro nome do proprietário: PA*LO" in _valores(fs, FindingKind.NOTE)
    assert FindingKind.NAME not in {f.kind for f in fs}
    assert "2 proprietário(s) ao longo da vida do veículo" in _valores(fs, FindingKind.NOTE)
    assert "Veículo já teve restrição" in _valores(fs, FindingKind.LEGAL)


def test_placa_sem_registro_e_restricao_ativa():
    vazio = bdc.placa_findings({}, "ABC1D23")
    assert len(vazio) == 1 and "sem registro" in vazio[0].value
    ativa = bdc.placa_findings({**PLACA, "CurrentlyHasRestrictions": True}, "ABC1D23")
    assert "Veículo com restrição ativa" in _valores(ativa, FindingKind.LEGAL)


def test_consulta_de_placa_usa_o_dataset_license_plates():
    import pytest

    visto = {}

    def falso(url, payload=None, **kw):
        visto.update(url=url, payload=payload)
        return {"Result": [{"LicensePlateData": PLACA}], "Status": {"license_plates": [{"Code": 0}]}}

    with mock.patch.object(bdc, "configurado", return_value=True), \
         mock.patch.object(bdc.net, "get_key", return_value="x"), \
         mock.patch.object(bdc.net, "post_json", side_effect=falso):
        assert bdc.consultar_placa("abc-1d23")["TotalOwnersInLifetime"] == 2
    assert visto["url"].endswith("/veiculos")
    assert visto["payload"] == {"Datasets": "license_plates", "q": "licenseplate{ABC1D23}", "Limit": 1}
    with pytest.raises(ValueError):
        bdc.consultar_placa("123")
    erro = {"Result": [], "Status": {"license_plates": [{"Code": -109, "Message": "DATASET NOT AVAILABLE"}]}}
    with mock.patch.object(bdc, "configurado", return_value=True), \
         mock.patch.object(bdc.net, "get_key", return_value="x"), \
         mock.patch.object(bdc.net, "post_json", return_value=erro):
        with pytest.raises(RuntimeError, match="DATASET NOT AVAILABLE"):
            bdc.consultar_placa("ABC1D23")


def test_conector_de_placa_aceita_so_placa():
    from holmes.connectors import ensure_registered
    from holmes.connectors.base import get_connector

    ensure_registered()
    c = get_connector("bigdatacorp_placa")
    assert c and not c.on_pivots and c.cost == "pago"
    assert c.handles(detect("ABC1D23")) and not c.handles(detect("529.982.247-25"))
