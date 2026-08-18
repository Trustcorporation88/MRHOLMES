"""
Camada Brasil.

Fontes públicas oficiais e gratuitas que o Google não consulta por você:
BrasilAPI/ReceitaWS (CNPJ → quadro societário → novos alvos), DDD → região,
CEP, e os portais jurídicos/societários que só funcionam com dork montado.

Quadro societário é o pivô mais valioso que existe em investigação BR:
um CNPJ entrega nome completo, qualificação e faixa etária dos sócios.
"""

from __future__ import annotations

from typing import Iterable

from . import net
from .entity import Entity, EntityType, only_digits
from .findings import Confidence, Finding, FindingKind

# DDD → capital/região, para localizar o alvo sem depender de base paga.
DDD_REGIAO = {
    "11": "São Paulo/SP (capital e Grande SP)", "12": "Vale do Paraíba/SP",
    "13": "Baixada Santista/SP", "14": "Bauru/SP", "15": "Sorocaba/SP",
    "16": "Ribeirão Preto/SP", "17": "São José do Rio Preto/SP",
    "18": "Presidente Prudente/SP", "19": "Campinas/SP",
    "21": "Rio de Janeiro/RJ", "22": "Campos dos Goytacazes/RJ", "24": "Volta Redonda/RJ",
    "27": "Vitória/ES", "28": "Cachoeiro de Itapemirim/ES",
    "31": "Belo Horizonte/MG", "32": "Juiz de Fora/MG", "33": "Governador Valadares/MG",
    "34": "Uberlândia/MG", "35": "Poços de Caldas/MG", "37": "Divinópolis/MG",
    "38": "Montes Claros/MG",
    "41": "Curitiba/PR", "42": "Ponta Grossa/PR", "43": "Londrina/PR",
    "44": "Maringá/PR", "45": "Foz do Iguaçu/PR", "46": "Francisco Beltrão/PR",
    "47": "Joinville/SC", "48": "Florianópolis/SC", "49": "Chapecó/SC",
    "51": "Porto Alegre/RS", "53": "Pelotas/RS", "54": "Caxias do Sul/RS", "55": "Santa Maria/RS",
    "61": "Brasília/DF", "62": "Goiânia/GO", "63": "Palmas/TO", "64": "Rio Verde/GO",
    "65": "Cuiabá/MT", "66": "Rondonópolis/MT", "67": "Campo Grande/MS",
    "68": "Rio Branco/AC", "69": "Porto Velho/RO",
    "71": "Salvador/BA", "73": "Ilhéus/BA", "74": "Juazeiro/BA", "75": "Feira de Santana/BA",
    "77": "Barreiras/BA", "79": "Aracaju/SE",
    "81": "Recife/PE", "82": "Maceió/AL", "83": "João Pessoa/PB", "84": "Natal/RN",
    "85": "Fortaleza/CE", "86": "Teresina/PI", "87": "Petrolina/PE",
    "88": "Juazeiro do Norte/CE", "89": "Picos/PI",
    "91": "Belém/PA", "92": "Manaus/AM", "93": "Santarém/PA", "94": "Marabá/PA",
    "95": "Boa Vista/RR", "96": "Macapá/AP", "97": "Coari/AM",
    "98": "São Luís/MA", "99": "Imperatriz/MA",
}


def ddd_info(ddd: str) -> str | None:
    return DDD_REGIAO.get(str(ddd).zfill(2))


# ── CNPJ: o pivô mais rico da investigação brasileira ───────────────────────

def consulta_cnpj(cnpj: str) -> dict | None:
    """BrasilAPI primeiro (sem chave, sem limite agressivo); ReceitaWS como reserva."""
    digits = only_digits(cnpj)
    if len(digits) != 14:
        return None
    try:
        data = net.get_json(f"https://brasilapi.com.br/api/cnpj/v1/{digits}", timeout=15)
        if data and (data.get("razao_social") or data.get("nome")):
            data["_fonte"] = "BrasilAPI"
            return data
    except Exception:
        pass
    try:
        data = net.get_json(f"https://receitaws.com.br/v1/cnpj/{digits}", timeout=20)
        if data and data.get("status") != "ERROR":
            data["_fonte"] = "ReceitaWS"
            return data
    except Exception:
        pass
    return None


def _socios(data: dict) -> list[dict]:
    """Normaliza o quadro societário — BrasilAPI e ReceitaWS usam formatos diferentes."""
    out: list[dict] = []
    for s in data.get("qsa") or []:
        nome = s.get("nome_socio") or s.get("nome") or ""
        if not nome:
            continue
        out.append(
            {
                "nome": nome.strip(),
                "qualificacao": s.get("qualificacao_socio") or s.get("qual") or "",
                "faixa_etaria": s.get("faixa_etaria") or "",
                "entrada": s.get("data_entrada_sociedade") or "",
                "cpf_mascarado": s.get("cnpj_cpf_do_socio") or s.get("cpf_representante_legal") or "",
            }
        )
    return out


def cnpj_findings(entity: Entity) -> Iterable[Finding]:
    data = consulta_cnpj(entity.value)
    if not data:
        return []

    fonte = data.get("_fonte", "Receita Federal")
    url = f"https://brasilapi.com.br/api/cnpj/v1/{only_digits(entity.value)}"
    out: list[Finding] = []

    razao = data.get("razao_social") or data.get("nome") or ""
    fantasia = data.get("nome_fantasia") or data.get("fantasia") or ""
    if razao:
        out.append(Finding(
            kind=FindingKind.COMPANY, value=razao, source="receita_cnpj",
            source_label=f"Receita Federal ({fonte})", url=url,
            confidence=Confidence.CONFIRMED,
            detail=f"Razão social. Situação: {data.get('descricao_situacao_cadastral') or data.get('situacao') or 'n/d'}",
            raw=data,
        ))
    if fantasia:
        out.append(Finding(
            kind=FindingKind.COMPANY, value=fantasia, source="receita_cnpj",
            source_label=f"Receita Federal ({fonte})", url=url,
            confidence=Confidence.CONFIRMED, detail="Nome fantasia",
        ))

    # Endereço, telefone e e-mail declarados são dado oficial — confiança alta.
    logradouro = data.get("logradouro") or ""
    if logradouro:
        endereco = " ".join(str(p) for p in [
            data.get("descricao_tipo_de_logradouro") or "", logradouro,
            data.get("numero") or "", data.get("complemento") or "",
            "-", data.get("bairro") or "", data.get("municipio") or "",
            data.get("uf") or "", f"CEP {data.get('cep') or ''}",
        ] if p).strip()
        out.append(Finding(
            kind=FindingKind.ADDRESS, value=endereco, source="receita_cnpj",
            source_label=f"Receita Federal ({fonte})", url=url,
            confidence=Confidence.CONFIRMED, detail="Endereço cadastral declarado",
        ))

    for tel_key in ("ddd_telefone_1", "ddd_telefone_2", "telefone"):
        tel = data.get(tel_key)
        if tel:
            out.append(Finding(
                kind=FindingKind.PHONE, value=str(tel).strip(), source="receita_cnpj",
                source_label=f"Receita Federal ({fonte})", url=url,
                confidence=Confidence.CONFIRMED, detail="Telefone declarado na Receita",
            ))

    email = data.get("email")
    if email:
        out.append(Finding(
            kind=FindingKind.EMAIL, value=str(email).strip().lower(), source="receita_cnpj",
            source_label=f"Receita Federal ({fonte})", url=url,
            confidence=Confidence.CONFIRMED, detail="E-mail declarado na Receita",
        ))

    # Sócios: cada nome é um alvo novo para o motor de pivô.
    for socio in _socios(data):
        detalhe = ", ".join(p for p in [
            socio["qualificacao"], socio["faixa_etaria"],
            f"entrada em {socio['entrada']}" if socio["entrada"] else "",
        ] if p)
        out.append(Finding(
            kind=FindingKind.NAME, value=socio["nome"], source="receita_cnpj",
            source_label=f"Quadro societário ({fonte})", url=url,
            confidence=Confidence.CONFIRMED,
            detail=f"Sócio de {razao or entity.value}. {detalhe}".strip(),
            raw=socio,
        ))

    cnae = data.get("cnae_fiscal_descricao") or (data.get("atividade_principal") or [{}])[0].get("text", "")
    if cnae:
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"Atividade principal: {cnae}",
            source="receita_cnpj", source_label=f"Receita Federal ({fonte})", url=url,
            confidence=Confidence.CONFIRMED,
        ))
    return out


def cep_lookup(cep: str) -> dict | None:
    digits = only_digits(cep)
    if len(digits) != 8:
        return None
    try:
        return net.get_json(f"https://brasilapi.com.br/api/cep/v2/{digits}", timeout=10)
    except Exception:
        return None


def phone_br_findings(entity: Entity) -> Iterable[Finding]:
    """Enriquecimento local de telefone BR — não depende de nenhuma API paga."""
    if entity.type is not EntityType.PHONE or entity.get("country") != "BR":
        return []
    out: list[Finding] = []
    ddd = entity.get("ddd")
    regiao = ddd_info(ddd) if ddd else None
    if regiao:
        out.append(Finding(
            kind=FindingKind.ADDRESS, value=regiao, source="ddd_br",
            source_label="Tabela DDD (Anatel)", confidence=Confidence.LIKELY,
            detail=f"Região de origem do DDD {ddd}. O número pode ter sido portado para outra cidade.",
        ))
    local = entity.get("local") or ""
    if local:
        tipo = "Celular (nono dígito)" if len(local) == 9 and local.startswith("9") else "Fixo"
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"Tipo de linha: {tipo}", source="ddd_br",
            source_label="Numeração brasileira", confidence=Confidence.CONFIRMED,
        ))
    wa = entity.get("whatsapp")
    if wa:
        out.append(Finding(
            kind=FindingKind.LINK, value="WhatsApp — abrir conversa", source="whatsapp",
            source_label="WhatsApp", url=wa, confidence=Confidence.UNVERIFIED,
            detail="Se o número tem conta, a foto e o nome de exibição aparecem aqui.",
        ))
    return out


# ── deeplinks BR (o que o Google não monta sozinho) ─────────────────────────

def br_deeplinks(entity: Entity) -> list[tuple[str, str, str]]:
    """(rótulo, url, descrição) — cada um abre já pesquisado no alvo."""
    from urllib.parse import quote_plus

    t = entity.type
    links: list[tuple[str, str, str]] = []

    if t is EntityType.NAME:
        nome = quote_plus(entity.value)
        links += [
            ("Escavador", f"https://www.escavador.com/busca?q={nome}",
             "Processos, publicações e vínculos profissionais"),
            ("JusBrasil", f"https://www.jusbrasil.com.br/busca?q={nome}",
             "Diários oficiais e jurisprudência"),
            ("Lattes", f"https://buscatextual.cnpq.br/buscatextual/busca.do?metodo=apresentar&textoBusca={nome}",
             "Currículo acadêmico, orientadores e instituições"),
            ("Portal da Transparência", f"https://portaldatransparencia.gov.br/busca?termo={nome}",
             "Servidor público, benefício, sanção e contrato federal"),
            ("Consulta Sócio", f"https://www.consultasocio.com/busca?q={nome}",
             "Participação societária em empresas"),
            ("TSE — candidaturas", f"https://divulgacandcontas.tse.jus.br/divulga/#/candidato?nome={nome}",
             "Candidatura, bens declarados e prestação de contas"),
        ]
    elif t is EntityType.CNPJ:
        digits = only_digits(entity.value)
        links += [
            ("Consulta Sócio", f"https://www.consultasocio.com/q/sa/{digits}", "Quadro societário e coligadas"),
            ("Econodata", f"https://www.econodata.com.br/consulta-empresa/{digits}", "Porte, faturamento estimado e contatos"),
            ("JusBrasil", f"https://www.jusbrasil.com.br/busca?q={digits}", "Processos da pessoa jurídica"),
            ("Portal da Transparência", f"https://portaldatransparencia.gov.br/busca?termo={digits}", "Contratos e sanções federais"),
        ]
    elif t is EntityType.CPF:
        digits = only_digits(entity.value)
        links += [
            ("Portal da Transparência", f"https://portaldatransparencia.gov.br/busca?termo={digits}",
             "Vínculo com programa social, servidor ou sanção"),
            ("Situação cadastral (Receita)", "https://servicos.receita.fazenda.gov.br/servicos/cpf/consultasituacao/consultapublica.asp",
             "Consulta oficial — exige data de nascimento e captcha"),
        ]
    elif t is EntityType.PHONE and entity.get("country") == "BR":
        e164 = entity.get("e164", entity.value)
        digits = entity.get("digits", "")
        links += [
            ("Quem Perturba", f"https://www.quemperturba.com.br/numero/{digits}", "Reputação e denúncia de spam"),
            ("Telelistas", f"https://www.telelistas.net/busca?q={quote_plus(e164)}", "Listagem comercial"),
            ("Sync.me", f"https://sync.me/search/?number={quote_plus(e164)}", "Caller ID colaborativo"),
        ]
    return links
