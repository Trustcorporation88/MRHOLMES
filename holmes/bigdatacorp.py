"""
BigDataCorp: dados completos de CPF e CNPJ (a mesma API do bot do Telegram
"Consulta processos" no n8n).

Cada consulta custa crédito, então o Holmes separa em três pacotes, iguais
aos botões do bot:

  principais  identificação, contatos, endereços, ocupação, vínculos e sócios.
              Roda sozinho quando o alvo investigado é um CPF ou CNPJ (nunca
              nos pivôs, para não multiplicar o custo).
  processos   lista de processos judiciais. Só sob demanda, por botão.
  completa    parentes, veículos, KYC, débitos com o governo, distribuição de
              processos e mais. Só sob demanda, por botão.

Configuração (Railway do Mr.Holmes):
  BIGDATACORP_ACCESS_TOKEN   o AccessToken da plataforma
  BIGDATACORP_TOKEN_ID       o TokenId
"""

from __future__ import annotations

from typing import Iterable

import requests

from . import net
from .entity import Entity, EntityType, format_cnpj, format_cpf, only_digits
from .findings import Confidence, ConnectorResult, Finding, FindingKind

BASE_URL = "https://plataforma.bigdatacorp.com.br"
FONTE = "bigdatacorp"
ROTULO = "BigDataCorp"
CACHE_TTL = 24 * 3600  # a mesma consulta no mesmo dia não é cobrada de novo

PACOTES = {
    "principais": {
        "pessoas": "basic_data,phones_extended,emails_extended,addresses_extended,occupation_data,"
                   "financial_risk,kyc,business_relationships",
        "empresas": "basic_data,dynamic_qsa_data",
    },
    "processos": {"pessoas": "processes", "empresas": "processes"},
    "completa": {
        "pessoas": "lawsuits_distribution_data,financial_data,related_people,vehicles,"
                   "indebtedness_question,security_data,passages,financial_interests,"
                   "unified_modeling_data_x1_5",
        "empresas": "lawsuits_distribution_data,owners_lawsuits_distribution_data,government_debtors,"
                    "licenses_and_authorizations,owners_kyc,owners_influence,history_basic_data,"
                    "company_group_owners,company_group_legal_representative,"
                    "circles_first_level_owners,unified_modeling_data_x1_5",
    },
}
NOMES_PACOTE = {"principais": "dados principais", "processos": "processos", "completa": "pesquisa completa"}

PAPEIS = {"OWNERSHIP": "Sócio/Proprietário", "LEGAL REPRESENTATIVE": "Representante legal",
          "PARTNER": "Sócio em comum", "EMPLOYEE": "Funcionário", "QSA": "Quadro societário"}
PARENTESCO = {"MOTHER": "Mãe", "FATHER": "Pai", "SON": "Filho(a)", "DAUGHTER": "Filha",
              "BROTHER": "Irmão", "SISTER": "Irmã", "SPOUSE": "Cônjuge", "PARTNER": "Sócio em comum",
              "NEIGHBOR": "Vizinho(a)", "COWORKER": "Colega de trabalho",
              "HOUSEHOLD": "Mesma residência", "RELATIVE": "Parente"}


def configurado() -> bool:
    return net.has_key("bigdatacorp_token") and net.has_key("bigdatacorp_tokenid")


def _tipo(doc: str) -> str | None:
    d = only_digits(doc)
    return "pessoas" if len(d) == 11 else "empresas" if len(d) == 14 else None


def consultar(doc: str, pacote: str = "principais") -> dict:
    """Result[0] da BigDataCorp para o documento, já com a chave '_falhas'
    (datasets que não voltaram). Levanta erro se nada voltou."""
    digitos = only_digits(doc)
    tipo = _tipo(digitos)
    if not tipo or pacote not in PACOTES:
        raise ValueError("documento ou pacote inválido")
    if not configurado():
        raise RuntimeError("BIGDATACORP_ACCESS_TOKEN e BIGDATACORP_TOKEN_ID não configurados")
    resp = net.post_json(
        f"{BASE_URL}/{tipo}",
        payload={"Datasets": PACOTES[pacote][tipo], "q": f"doc{{{digitos}}}", "Limit": 20},
        headers={"AccessToken": net.get_key("bigdatacorp_token") or "",
                 "TokenId": net.get_key("bigdatacorp_tokenid") or "",
                 "Content-Type": "application/json", "Accept": "application/json"},
        timeout=120 if pacote == "completa" else 60, ttl=CACHE_TTL,
    ) or {}
    bruto = resp.get("Result")
    r = (bruto[0] if isinstance(bruto, list) and bruto else bruto) or {}
    falhas = []
    for nome, info in (resp.get("Status") or {}).items():
        info = info[0] if isinstance(info, list) and info else info
        if isinstance(info, dict) and info.get("Code") not in (0, None):
            falhas.append(f"{nome}: {info.get('Message') or info.get('Code')}")
    if not r:
        raise RuntimeError("; ".join(falhas) or "a BigDataCorp não devolveu dados")
    r = dict(r)
    r["_falhas"] = falhas
    return r


# ── utilitários ──────────────────────────────────────────────────────────────

def _data(d) -> str:
    s = str(d or "")
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        ano = int(s[:4]) if s[:4].isdigit() else 0
        if 1 < ano < 9999:
            return f"{s[8:10]}/{s[5:7]}/{s[:4]}"
    return ""


def _ativo(item: dict) -> bool:
    if isinstance(item.get("IsCurrentlyActive"), bool):
        return item["IsCurrentlyActive"]
    fim = str(item.get("RelationshipEndDate") or item.get("EndDate") or "")
    return not fim or fim.startswith("9999")


def _fmt_doc(numero, tipo=None) -> str:
    d = only_digits(str(numero or ""))
    if tipo == "CPF" or len(d) == 11:
        return format_cpf(d)
    if tipo == "CNPJ" or len(d) == 14:
        return format_cnpj(d)
    return str(numero or "")


def _moeda(v) -> str:
    try:
        return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(v or "")


def _lista(bloco, campo: str) -> list:
    v = (bloco or {}).get(campo) if isinstance(bloco, dict) else None
    return v if isinstance(v, list) else []


def _juntar(*partes) -> str:
    return ". ".join(p for p in partes if p)


# ── resposta → achados ───────────────────────────────────────────────────────

def para_findings(r: dict, doc: str, pacote: str = "principais") -> list[Finding]:
    """Converte a resposta em achados do dossiê. Testável sem rede."""
    rotulo = f"{ROTULO} ({NOMES_PACOTE.get(pacote, pacote)})"
    out: list[Finding] = []
    proprio = only_digits(doc)

    def add(kind, value, detail="", conf=Confidence.CONFIRMED, raw=None):
        if value and str(value).strip():
            out.append(Finding(kind=kind, value=str(value).strip(), source=FONTE, source_label=rotulo,
                               url="", confidence=conf, detail=detail, raw=raw or {}))

    # identificação
    b = r.get("BasicData") or r.get("RegistrationData") or (r.get("DynamicQSAData") or {}).get("BasicData") or {}
    if b.get("OfficialName"):
        ativs = b.get("Activities") if isinstance(b.get("Activities"), list) else []
        principal = next((a for a in ativs if a.get("IsMain")), None)
        capital = (b.get("AdditionalOutputData") or {}).get("Capital")
        simples = (b.get("TaxRegimes") or {}).get("Simples")
        add(FindingKind.COMPANY, b["OfficialName"], _juntar(
            f"Situação {b['TaxIdStatus']}" if b.get("TaxIdStatus") else "",
            f"aberta em {_data(b.get('FoundedDate'))}" if _data(b.get("FoundedDate")) else "",
            f"regime {b['TaxRegime']}" if b.get("TaxRegime") else "",
            "optante do Simples" if simples is True else "",
            f"capital {_moeda(capital)}" if capital else "",
            f"atividade {principal.get('Activity')} (CNAE {principal.get('Code')})" if principal else ""),
            raw={"natureza": (b.get("LegalNature") or {}).get("Activity")})
        if b.get("TradeName") and b["TradeName"] != b["OfficialName"]:
            add(FindingKind.COMPANY, b["TradeName"], "Nome fantasia")
    elif b.get("Name"):
        idade = f" ({b['Age']} anos)" if b.get("Age") else ""
        add(FindingKind.NAME, b["Name"], _juntar(
            f"Titular do CPF, nascido em {_data(b.get('BirthDate'))}{idade}" if _data(b.get("BirthDate"))
            else "Titular do CPF",
            f"CPF {b['TaxIdStatus']}" if b.get("TaxIdStatus") else "",
            "⚠️ indicação de óbito" if b.get("HasObitIndication") else ""),
            raw={"titular": True})
        if b.get("MotherName"):
            add(FindingKind.NAME, b["MotherName"], "Mãe do titular", raw={"parentesco": "mae"})
        if b.get("FatherName"):
            add(FindingKind.NAME, b["FatherName"], "Pai do titular", raw={"parentesco": "pai"})
        apelido = (b.get("Aliases") or {}).get("CommonName")
        if apelido and apelido != b["Name"]:
            add(FindingKind.NAME, apelido, "Como é conhecido")

    # contatos e endereços (cadastro de birô: pode estar desatualizado)
    tipos_tel = {"MOBILE": "celular", "HOME": "residencial", "WORK": "comercial"}
    for p in _lista(r.get("ExtendedPhones"), "Phones")[:15]:
        if p.get("Number"):
            add(FindingKind.PHONE, f"({p.get('AreaCode') or ''}) {p['Number']}".strip(),
                _juntar("Telefone ligado ao documento", tipos_tel.get(p.get("Type"), "")),
                Confidence.LIKELY)
    tipos_mail = {"PERSONAL": "pessoal", "WORK": "profissional"}
    for e in _lista(r.get("ExtendedEmails"), "Emails")[:15]:
        if e.get("EmailAddress"):
            add(FindingKind.EMAIL, e["EmailAddress"].lower(),
                _juntar("E-mail ligado ao documento", tipos_mail.get(e.get("Type"), "")), Confidence.LIKELY)
    for e in _lista(r.get("ExtendedAddresses"), "Addresses")[:10]:
        rua = " ".join(x for x in (e.get("Typology"), e.get("AddressMain")) if x)
        cidade = f"{e.get('City') or ''}/{e.get('State') or ''}".strip("/")
        cep = str(e.get("ZipCode") or "")
        cep = f"CEP {cep[:5]}-{cep[5:]}" if len(cep) == 8 else ""
        texto = ", ".join(x for x in (rua, e.get("Number"), e.get("Complement"), e.get("Neighborhood"),
                                      cidade, cep) if x)
        add(FindingKind.ADDRESS, texto, _juntar(
            "Endereço ligado ao documento",
            {"HOME": "residencial", "WORK": "comercial"}.get(e.get("Type"), "")), Confidence.LIKELY)

    # ocupação
    for x in _lista(r.get("ProfessionData"), "Professions")[:10]:
        if x.get("CompanyName"):
            ativo = x.get("Status") == "ACTIVE"
            renda = x.get("IncomeRange") if x.get("IncomeRange") not in (None, "", "SEM INFORMACAO") else ""
            add(FindingKind.COMPANY, x["CompanyName"], _juntar(
                f"Ocupação: {x.get('Level') or 'vínculo'} ({'ativo' if ativo else 'encerrado'})",
                f"desde {_data(x.get('StartDate'))}" if _data(x.get("StartDate")) else "",
                f"renda {renda}" if renda else ""), raw={"ocupacao": True})

    # sócios (CNPJ) e vínculos empresariais (CPF)
    rel = (r.get("DynamicQSAData") or {}).get("Relationships") or {}
    socios = [(x, True) for x in _lista(rel, "CurrentRelationships")] + \
             [(x, False) for x in _lista(rel, "HistoricalRelationships")]
    vinculos = [(x, _ativo(x)) for x in _lista(r.get("BusinessRelationships"), "BusinessRelationships")]
    for x, atual in socios + vinculos:
        nome = x.get("RelatedEntityName")
        numero = only_digits(str(x.get("RelatedEntityTaxIdNumber") or ""))
        if not nome or (numero and numero == proprio):
            continue
        papel = x.get("RelationshipName") or PAPEIS.get(x.get("RelationshipType"), x.get("RelationshipType") or "")
        e_empresa = x.get("RelatedEntityTaxIdType") == "CNPJ" or len(numero) == 14
        detalhe = _juntar(
            papel, "atual" if atual else "encerrado",
            f"desde {_data(x.get('RelationshipStartDate'))}" if _data(x.get("RelationshipStartDate")) else "",
            f"até {_data(x.get('RelationshipEndDate'))}" if not atual and _data(x.get("RelationshipEndDate")) else "",
            f"documento {_fmt_doc(numero)}" if numero else "")
        add(FindingKind.COMPANY if e_empresa else FindingKind.NAME, nome, detalhe,
            raw={"socio": True, "qualificacao": papel, "atual": atual})
        if len(numero) in (11, 14):
            add(FindingKind.DOCUMENT, _fmt_doc(numero), f"{'CNPJ' if e_empresa else 'CPF'} de {nome}",
                raw={"de": nome})

    # KYC
    k = r.get("KycData") or {}
    if k:
        alertas = []
        if k.get("IsCurrentlyPEP"):
            alertas.append("Pessoa Politicamente Exposta (PEP) atual")
        elif _lista(k, "PEPHistory"):
            alertas.append("Já foi Pessoa Politicamente Exposta (PEP)")
        if k.get("IsCurrentlySanctioned"):
            alertas.append("Consta hoje em lista de sanções")
        elif k.get("WasPreviouslySanctioned"):
            alertas.append("Já constou em lista de sanções")
        for a in alertas:
            add(FindingKind.LEGAL, a, "KYC da BigDataCorp")
        if not alertas:
            add(FindingKind.NOTE, "Sem apontamentos de PEP ou sanções", "KYC da BigDataCorp")

    # risco financeiro
    f = r.get("FinancialRisk") or {}
    if f:
        partes = [
            f"score {f['FinancialRiskScore']}" + (f" (nível {f['FinancialRiskLevel']})" if f.get("FinancialRiskLevel") else "")
            if f.get("FinancialRiskScore") is not None else "",
            f"renda estimada {f['EstimatedIncomeRange']}" if f.get("EstimatedIncomeRange") else "",
            "em cobrança hoje" if f.get("IsCurrentlyOnCollection") else "",
            f"{f['Last365DaysCollectionOccurrences']} cobrança(s) em 12 meses"
            if f.get("Last365DaysCollectionOccurrences") else "",
        ]
        texto = ", ".join(p for p in partes if p)
        if texto:
            add(FindingKind.NOTE, f"Risco financeiro: {texto}", "BigDataCorp")
    if isinstance((r.get("IndebtednessQuestion") or {}).get("LikelyInDebt"), bool):
        add(FindingKind.NOTE, "Perfil com indícios de endividamento" if r["IndebtednessQuestion"]["LikelyInDebt"]
            else "Sem indícios de endividamento", "Probabilidade de negativação")

    # processos
    p = r.get("Processes") or r.get("Lawsuits") or {}
    if isinstance(p, dict) and p:
        total = p.get("TotalLawsuits") or 0
        add(FindingKind.NOTE, f"{total} processo(s) judicial(is)" if total else "Nenhum processo judicial",
            _juntar(f"{p.get('TotalLawsuitsAsAuthor') or 0} como autor, "
                    f"{p.get('TotalLawsuitsAsDefendant') or 0} como réu" if total else "",
                    f"mais recente em {_data(p.get('LastLawsuitDate'))}" if _data(p.get("LastLawsuitDate")) else ""))
        for x in _lista(p, "Lawsuits")[:60]:
            numero = x.get("Number")
            if numero:
                add(FindingKind.LEGAL, f"Processo {numero}", _juntar(
                    x.get("Type"), f"{x.get('CourtName') or ''}/{x.get('State') or ''}".strip("/"),
                    x.get("CourtType"), x.get("Status"),
                    f"distribuído em {_data(x.get('NoticeDate'))}" if _data(x.get("NoticeDate")) else ""))

    d = r.get("LawsuitsDistributionData") or {}
    for campo, titulo in (("TypeDistribution", "tipo"), ("CourtTypeDistribution", "área"),
                          ("StateDistribution", "estado")):
        v = d.get(campo)
        if isinstance(v, dict):
            itens = sorted(((kk, vv) for kk, vv in v.items() if vv), key=lambda t: -t[1])[:6]
            if itens:
                add(FindingKind.NOTE, f"Processos por {titulo}: " + ", ".join(f"{kk} ({vv})" for kk, vv in itens),
                    "Perfil dos processos")

    # parentes e pessoas relacionadas
    for x in _lista(r.get("RelatedPeople"), "PersonalRelationships")[:25]:
        nome = x.get("RelatedEntityName")
        if not nome:
            continue
        grau = PARENTESCO.get(x.get("RelationshipType"), x.get("RelationshipType") or "relacionado")
        numero = only_digits(str(x.get("RelatedEntityTaxIdNumber") or ""))
        add(FindingKind.NAME, nome, _juntar(f"Pessoa relacionada: {grau}",
                                            f"CPF {_fmt_doc(numero)}" if len(numero) == 11 else ""),
            Confidence.LIKELY, raw={"parentesco": grau})
        if len(numero) == 11:
            add(FindingKind.DOCUMENT, _fmt_doc(numero), f"CPF de {nome} ({grau})", Confidence.LIKELY)

    # veículos
    v = r.get("Vehicles")
    veiculos = v if isinstance(v, list) else _lista(v, "Vehicles")
    for x in veiculos[:10]:
        desc = " ".join(str(y) for y in (x.get("Brand"), x.get("Model"), x.get("ManufactureYear")) if y)
        if desc or x.get("LicensePlate"):
            add(FindingKind.NOTE, f"Veículo: {desc}" + (f", placa {x['LicensePlate']}" if x.get("LicensePlate") else ""),
                "BigDataCorp")

    # débitos com o governo (CNPJ)
    g = r.get("GovernmentDebtors") or {}
    if g:
        total = g.get("TotalDebts") or 0
        if not total:
            add(FindingKind.NOTE, "Nenhum débito com o governo", "Devedores do governo")
        else:
            add(FindingKind.LEGAL, f"{total} débito(s) com o governo",
                f"valor total {_moeda(g.get('TotalDebtValue'))}" if g.get("TotalDebtValue") else "")
            for x in _lista(g, "Debts")[:15]:
                origem = x.get("Origin") or x.get("Source") or "Débito"
                add(FindingKind.LEGAL, f"Débito: {origem}" + (f", {_moeda(x['Value'])}" if x.get("Value") else ""),
                    x.get("Situation") or "")

    o = r.get("OwnersLawsuitsDistributionData") or {}
    if o.get("TotalLawsuits"):
        add(FindingKind.NOTE, f"Sócios somam {o['TotalLawsuits']} processo(s)",
            _juntar(f"{o.get('TotalOwners')} sócio(s) analisado(s)" if o.get("TotalOwners") else "",
                    f"{o.get('TotalLawsuitsAsDefendant') or 0} como réu"))

    if r.get("_falhas"):
        add(FindingKind.NOTE, "Parte da consulta não voltou", "; ".join(r["_falhas"])[:500],
            Confidence.UNVERIFIED)
    return out


def buscar(entity_or_doc, pacote: str = "principais") -> ConnectorResult:
    """Uma consulta sob demanda (botões do dossiê). Nunca levanta."""
    doc = entity_or_doc.value if isinstance(entity_or_doc, Entity) else str(entity_or_doc)
    rotulo = f"{ROTULO} ({NOMES_PACOTE.get(pacote, pacote)})"
    try:
        r = consultar(doc, pacote)
        return ConnectorResult(connector_id=f"{FONTE}_{pacote}", connector_label=rotulo, ok=True,
                               findings=para_findings(r, doc, pacote))
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        return ConnectorResult(connector_id=f"{FONTE}_{pacote}", connector_label=rotulo, ok=False,
                               error=str(exc)[:300])


def findings(entity: Entity) -> Iterable[Finding]:
    """Conector automático: pacote 'principais' do alvo investigado."""
    if entity.type not in (EntityType.CPF, EntityType.CNPJ):
        return []
    return para_findings(consultar(entity.value, "principais"), entity.value, "principais")
