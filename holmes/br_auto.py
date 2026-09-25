"""
Conectores automáticos brasileiros — os que consultam de verdade.

Todos usam fonte oficial e aberta. A única que exige chave é o Portal da
Transparência (cadastro gratuito por e-mail), e ela vale muito: é a base
oficial de PEP, empresa sancionada e servidor público federal.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from . import net
from .entity import Entity, EntityType, only_digits
from .findings import Confidence, Finding, FindingKind

PORTAL_BASE = "https://api.portaldatransparencia.gov.br/api-de-dados"


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _mesma_pessoa(alvo: str, achado: str) -> bool:
    """
    Casamento conservador de nome: exige primeiro e último sobrenome iguais.
    Sem isso, "João Silva" casa com meio Brasil e o dossiê vira lixo.
    """
    a = [t for t in re.split(r"\W+", _sem_acento(alvo)) if len(t) > 1]
    b = [t for t in re.split(r"\W+", _sem_acento(achado)) if len(t) > 1]
    if len(a) < 2 or len(b) < 2:
        return False
    return a[0] == b[0] and a[-1] == b[-1]


# ── Congresso Nacional: detecção de pessoa politicamente exposta ────────────

def congresso_findings(entity: Entity) -> Iterable[Finding]:
    """
    Deputado federal ou senador com o nome do alvo. Achar aqui muda o caso
    inteiro: passa a existir declaração de bens, votação e despesa de gabinete
    tudo público.
    """
    nome = entity.value
    if len(nome.split()) < 2:
        return []
    out: list[Finding] = []

    # Câmara dos Deputados — dados abertos.
    try:
        data = net.get_json(
            "https://dadosabertos.camara.leg.br/api/v2/deputados",
            params={"nome": nome, "itens": 20, "ordem": "ASC", "ordenarPor": "nome"},
            timeout=15, ttl=7 * 24 * 3600,
        ) or {}
        for dep in data.get("dados") or []:
            dep_nome = dep.get("nome") or ""
            if not _mesma_pessoa(nome, dep_nome):
                continue
            perfil = f"https://www.camara.leg.br/deputados/{dep.get('id')}"
            out.append(Finding(
                kind=FindingKind.NOTE,
                value=f"PESSOA POLITICAMENTE EXPOSTA — Deputado(a) Federal {dep_nome}",
                source="camara", source_label="Câmara dos Deputados (dados abertos)",
                url=perfil, confidence=Confidence.CONFIRMED,
                detail=f"{dep.get('siglaPartido')}/{dep.get('siglaUf')}. "
                       f"E-mail funcional e despesas de gabinete são públicos.",
                raw=dep,
            ))
            if dep.get("email"):
                out.append(Finding(
                    kind=FindingKind.EMAIL, value=str(dep["email"]).lower(),
                    source="camara", source_label="Câmara dos Deputados",
                    url=perfil, confidence=Confidence.CONFIRMED,
                    detail="E-mail funcional do gabinete",
                ))
            if dep.get("urlFoto"):
                out.append(Finding(
                    kind=FindingKind.IMAGE, value=dep["urlFoto"],
                    source="camara", source_label="Câmara dos Deputados",
                    url=dep["urlFoto"], confidence=Confidence.CONFIRMED,
                    detail="Foto oficial",
                ))
    except Exception:
        pass

    # Senado Federal — dados abertos.
    try:
        data = net.get_json(
            "https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json",
            timeout=20, ttl=7 * 24 * 3600,
        ) or {}
        lista = (
            ((data.get("ListaParlamentarEmExercicio") or {}).get("Parlamentares") or {})
            .get("Parlamentar") or []
        )
        for sen in lista:
            ident = sen.get("IdentificacaoParlamentar") or {}
            sen_nome = ident.get("NomeCompletoParlamentar") or ident.get("NomeParlamentar") or ""
            if not _mesma_pessoa(nome, sen_nome):
                continue
            out.append(Finding(
                kind=FindingKind.NOTE,
                value=f"PESSOA POLITICAMENTE EXPOSTA — Senador(a) {sen_nome}",
                source="senado", source_label="Senado Federal (dados abertos)",
                url=ident.get("UrlPaginaParlamentar"), confidence=Confidence.CONFIRMED,
                detail=f"{ident.get('SiglaPartidoParlamentar')}/{ident.get('UfParlamentar')}",
                raw=ident,
            ))
            if ident.get("EmailParlamentar"):
                out.append(Finding(
                    kind=FindingKind.EMAIL, value=str(ident["EmailParlamentar"]).lower(),
                    source="senado", source_label="Senado Federal",
                    confidence=Confidence.CONFIRMED, detail="E-mail funcional do gabinete",
                ))
    except Exception:
        pass

    return out


# ── Portal da Transparência (chave gratuita por e-mail) ─────────────────────

class _PortalErros(list):
    """Falhas de uma rodada de consultas ao Portal, para não virar «nada encontrado»."""

    chamadas = 0

    def conferir(self) -> None:
        # Se TODAS as consultas falharam, o Portal não respondeu: isso tem que
        # aparecer em «fontes que não responderam», não como dossiê vazio.
        if self.chamadas and len(self) >= self.chamadas:
            raise RuntimeError(f"Portal da Transparência não respondeu: {self[0]}")


def _portal_get(caminho: str, params: dict, erros: _PortalErros | None = None):
    chave = net.get_key("portal_transparencia")
    if not chave:
        return None
    if erros is not None:
        erros.chamadas += 1
    try:
        return net.get_json(
            f"{PORTAL_BASE}/{caminho}",
            params=params,
            headers={"chave-api-dados": chave, "Accept": "application/json"},
            timeout=25, ttl=24 * 3600,
        )
    except Exception as exc:  # noqa: BLE001
        if erros is not None:
            erros.append(f"{caminho}: {exc}")
        return None


def _lista(resposta) -> list:
    """O Portal devolve lista na maioria dos recursos e objeto em alguns."""
    if isinstance(resposta, list):
        return resposta
    if isinstance(resposta, dict) and resposta:
        return [resposta]
    return []


# Flags do recurso pessoa-fisica/pessoa-juridica → frase para o dossiê.
_VINCULOS_PF = {
    "servidor": "servidor público federal",
    "servidorInativo": "servidor federal inativo",
    "pensionistaOuRepresentanteLegal": "pensionista (ou representante legal)",
    "beneficiarioBolsaFamilia": "beneficiário do Bolsa Família",
    "beneficiarioNovoBolsaFamilia": "beneficiário do Novo Bolsa Família",
    "beneficiarioAuxilioEmergencial": "beneficiário do Auxílio Emergencial",
    "beneficiarioAuxilioBrasil": "beneficiário do Auxílio Brasil",
    "beneficiarioBpc": "beneficiário do BPC",
    "beneficiarioPeti": "beneficiário do PETI",
    "beneficiarioSafra": "beneficiário do Garantia-Safra",
    "beneficiarioSeguroDefeso": "beneficiário do Seguro-Defeso",
    "favorecidoDespesas": "favorecido em despesa federal (recebeu pagamento da União)",
    "favorecidoTransferencias": "favorecido em transferência federal",
    "favorecidoRecursos": "favorecido em recursos federais",
    "possuiContratacao": "possui contrato com o governo federal",
    "participanteLicitacao": "participou de licitação federal",
    "emitiuNFe": "emitiu NF-e para órgão federal",
    "sancionadoCEIS": "sancionado no CEIS",
    "sancionadoCNEP": "sancionado no CNEP",
    "sancionadoCEAF": "expulso da administração federal (CEAF)",
    "sancionadoCEPIM": "impedido no CEPIM (entidade sem fins lucrativos)",
    "permissionario": "permissionário",
    "portadorCPGF": "portador de cartão corporativo do governo",
    "favorecidoCPGF": "favorecido por cartão corporativo",
    "convenios": "possui convênio federal",
}


def _brl(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".translate(str.maketrans(",.", ".,"))


def _vinculos(registro: dict) -> list[str]:
    return [frase for campo, frase in _VINCULOS_PF.items() if registro.get(campo) is True]


def portal_nome_findings(entity: Entity) -> Iterable[Finding]:
    """Sanção, servidor federal e PEP pelo nome — base oficial da CGU."""
    nome = entity.value
    out: list[Finding] = []
    erros = _PortalErros()

    # PEP — pessoa exposta politicamente. Muda o nível de diligência do caso.
    for registro in _lista(_portal_get("peps", {"nome": nome, "pagina": 1}, erros))[:10]:
        pessoa = (registro.get("pessoa") or {})
        achado = pessoa.get("nome") or registro.get("nome") or ""
        if achado and not _mesma_pessoa(nome, achado):
            continue
        funcao = registro.get("descricaoFuncao") or "função n/d"
        orgao = registro.get("nomeOrgao") or registro.get("orgaoLotacaoPep") or "órgão n/d"
        out.append(Finding(
            kind=FindingKind.NOTE,
            value=f"PESSOA POLITICAMENTE EXPOSTA (lista oficial): {achado or nome}",
            source="portal_pep", source_label="Portal da Transparência — PEP",
            url="https://portaldatransparencia.gov.br/pessoa-exposta-politicamente",
            confidence=Confidence.CONFIRMED,
            detail=f"{funcao} — {orgao}. Exercício de "
                   f"{registro.get('dataInicioExercicio') or '?'} a "
                   f"{registro.get('dataFimExercicio') or 'atual'}.",
            raw=registro,
        ))

    # Empresa/pessoa inidônea ou suspensa (CEIS).
    for registro in _lista(_portal_get("ceis", {"nomeSancionado": nome, "pagina": 1}, erros))[:10]:
        pessoa = (registro.get("pessoa") or {})
        sancao = (registro.get("sancao") or {})
        nome_sancionado = pessoa.get("nome") or ""
        out.append(Finding(
            kind=FindingKind.LEGAL,
            value=f"SANÇÃO (CEIS): {nome_sancionado}",
            source="portal_ceis", source_label="Portal da Transparência — CEIS",
            url="https://portaldatransparencia.gov.br/sancoes/ceis",
            confidence=Confidence.CONFIRMED,
            detail=f"{sancao.get('tipoSancao', {}).get('descricaoResumida') or 'sanção'} — "
                   f"órgão: {(registro.get('orgaoSancionador') or {}).get('nome') or 'n/d'}. "
                   f"Vigência: {sancao.get('dataInicioSancao') or '?'} a "
                   f"{sancao.get('dataFimSancao') or '?'}",
            raw=registro,
        ))

    # Empresa punida por corrupção (CNEP — Lei Anticorrupção).
    for registro in _lista(_portal_get("cnep", {"nomeSancionado": nome, "pagina": 1}, erros))[:10]:
        out.append(Finding(
            kind=FindingKind.LEGAL,
            value=f"SANÇÃO (CNEP): {(registro.get('pessoa') or {}).get('nome') or nome}",
            source="portal_cnep", source_label="Portal da Transparência — CNEP",
            url="https://portaldatransparencia.gov.br/sancoes/cnep",
            confidence=Confidence.CONFIRMED,
            detail="Punição com base na Lei Anticorrupção (12.846/2013).",
            raw=registro,
        ))

    # Servidor público federal.
    for registro in _lista(_portal_get("servidores", {"nome": nome, "pagina": 1}, erros))[:10]:
        servidor = (registro.get("servidor") or registro)
        pessoa = (servidor.get("pessoa") or {})
        achado = pessoa.get("nome") or registro.get("nome") or ""
        if achado and not _mesma_pessoa(nome, achado):
            continue
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"Servidor público federal: {achado or nome}",
            source="portal_servidores", source_label="Portal da Transparência — Servidores",
            url="https://portaldatransparencia.gov.br/servidores",
            confidence=Confidence.CONFIRMED,
            detail="Cargo e remuneração são públicos no portal.",
            raw=registro,
        ))

    erros.conferir()
    return out


def portal_cpf_findings(entity: Entity) -> Iterable[Finding]:
    """
    CPF contra a base da CGU. O recurso pessoa-fisica é o único caminho
    oficial e gratuito de CPF → nome completo, e ainda diz em quais cadastros
    federais a pessoa aparece (servidor, benefício, contrato, sanção).
    """
    cpf = only_digits(entity.value)
    out: list[Finding] = []
    erros = _PortalErros()

    for pessoa in _lista(_portal_get("pessoa-fisica", {"cpf": cpf}, erros))[:1]:
        nome = (pessoa.get("nome") or "").strip()
        if nome:
            out.append(Finding(
                kind=FindingKind.NAME, value=nome,
                source="portal_pf", source_label="Portal da Transparência — Pessoa física",
                url=f"https://portaldatransparencia.gov.br/busca?termo={cpf}",
                confidence=Confidence.CONFIRMED,
                detail="Nome vinculado ao CPF na base oficial da CGU.",
                raw=pessoa,
            ))
        vinc = _vinculos(pessoa)
        if vinc:
            out.append(Finding(
                kind=FindingKind.NOTE,
                value="Vínculos federais: " + "; ".join(vinc),
                source="portal_pf", source_label="Portal da Transparência — Pessoa física",
                url=f"https://portaldatransparencia.gov.br/busca?termo={cpf}",
                confidence=Confidence.CONFIRMED,
                detail="Cadastros federais em que o CPF aparece. Cada um tem detalhe "
                       "(valor, órgão, período) na página do Portal.",
            ))
        if pessoa.get("nis"):
            out.append(Finding(
                kind=FindingKind.DOCUMENT, value=f"NIS {pessoa['nis']}",
                source="portal_pf", source_label="Portal da Transparência — Pessoa física",
                confidence=Confidence.CONFIRMED, detail="NIS/PIS vinculado ao CPF.",
            ))

    for registro in _lista(_portal_get("peps", {"cpf": cpf, "pagina": 1}, erros))[:5]:
        pessoa = (registro.get("pessoa") or {})
        out.append(Finding(
            kind=FindingKind.NOTE,
            value=f"PESSOA POLITICAMENTE EXPOSTA: {pessoa.get('nome') or registro.get('nome') or 'titular do CPF'}",
            source="portal_pep", source_label="Portal da Transparência — PEP",
            url="https://portaldatransparencia.gov.br/pessoa-exposta-politicamente",
            confidence=Confidence.CONFIRMED,
            detail=f"{registro.get('descricaoFuncao') or 'função n/d'} — "
                   f"{registro.get('nomeOrgao') or 'órgão n/d'}",
            raw=registro,
        ))
        nome_pep = pessoa.get("nome") or registro.get("nome")
        if nome_pep:
            out.append(Finding(
                kind=FindingKind.NAME, value=nome_pep,
                source="portal_pep", source_label="Portal da Transparência — PEP",
                confidence=Confidence.CONFIRMED, detail="Nome vinculado ao CPF na base oficial",
            ))

    for registro in _lista(_portal_get("servidores", {"cpf": cpf, "pagina": 1}, erros))[:5]:
        servidor = registro.get("servidor") or registro
        cargo = (registro.get("fichasCargoEfetivo") or [{}])
        cargo = cargo[0] if isinstance(cargo, list) and cargo else {}
        out.append(Finding(
            kind=FindingKind.NOTE, value="Servidor público federal",
            source="portal_servidores", source_label="Portal da Transparência — Servidores",
            url="https://portaldatransparencia.gov.br/servidores",
            confidence=Confidence.CONFIRMED,
            detail=", ".join(p for p in [
                cargo.get("cargo") or "", cargo.get("orgaoLotacao") or "",
                (servidor.get("situacao") or "") if isinstance(servidor, dict) else "",
            ] if p) or "Cargo e remuneração são públicos no portal.",
            raw=registro,
        ))

    for recurso, param, rotulo, texto in (
        ("ceis", "codigoSancionado", "CEIS", "Impedido de contratar com a administração pública."),
        ("cnep", "codigoSancionado", "CNEP", "Punição com base na Lei Anticorrupção (12.846/2013)."),
        ("ceaf", "cpfSancionado", "CEAF", "Expulso da administração pública federal."),
    ):
        for registro in _lista(_portal_get(recurso, {param: cpf, "pagina": 1}, erros))[:5]:
            sancao = registro.get("sancao") or {}
            out.append(Finding(
                kind=FindingKind.LEGAL, value=f"CPF consta no {rotulo} (sancionado)",
                source=f"portal_{recurso}", source_label=f"Portal da Transparência — {rotulo}",
                url=f"https://portaldatransparencia.gov.br/sancoes/{recurso}",
                confidence=Confidence.CONFIRMED,
                detail=f"{texto} Vigência: {sancao.get('dataInicioSancao') or registro.get('dataPublicacao') or '?'}"
                       f" a {sancao.get('dataFimSancao') or '?'}",
                raw=registro,
            ))

    erros.conferir()
    return out


def portal_cnpj_findings(entity: Entity) -> Iterable[Finding]:
    """Vínculos, sanções, contratos e acordos de leniência de um CNPJ."""
    digits = only_digits(entity.value)
    out: list[Finding] = []
    erros = _PortalErros()

    for pj in _lista(_portal_get("pessoa-juridica", {"cnpj": digits}, erros))[:1]:
        vinc = _vinculos(pj)
        if vinc:
            out.append(Finding(
                kind=FindingKind.NOTE, value="Vínculos federais: " + "; ".join(vinc),
                source="portal_pj", source_label="Portal da Transparência — Pessoa jurídica",
                url=f"https://portaldatransparencia.gov.br/busca?termo={digits}",
                confidence=Confidence.CONFIRMED,
                detail="Cadastros federais em que o CNPJ aparece.",
                raw=pj,
            ))

    for recurso, param, rotulo, texto in (
        ("ceis", "codigoSancionado", "CEIS", "Inidônea/suspensa: impedida de contratar com a administração pública."),
        ("cnep", "codigoSancionado", "CNEP", "Punida com base na Lei Anticorrupção (12.846/2013)."),
        ("cepim", "cnpjSancionado", "CEPIM", "Entidade sem fins lucrativos impedida de receber transferências."),
        ("acordos-leniencia", "cnpjSancionado", "Acordo de leniência", "Firmou acordo de leniência com a CGU."),
    ):
        for registro in _lista(_portal_get(recurso, {param: digits, "pagina": 1}, erros))[:10]:
            sancao = registro.get("sancao") or {}
            out.append(Finding(
                kind=FindingKind.LEGAL, value=f"Empresa consta no {rotulo}",
                source=f"portal_{recurso.replace('-', '_')}",
                source_label=f"Portal da Transparência — {rotulo}",
                url="https://portaldatransparencia.gov.br/sancoes",
                confidence=Confidence.CONFIRMED,
                detail=f"{texto} Vigência: {sancao.get('dataInicioSancao') or registro.get('dataInicioAcordo') or '?'}"
                       f" a {sancao.get('dataFimSancao') or registro.get('dataFimAcordo') or '?'}",
                raw=registro,
            ))

    contratos = _lista(_portal_get("contratos/cpf-cnpj", {"cpfCnpj": digits, "pagina": 1}, erros))
    if contratos:
        total = 0.0
        for c in contratos:
            try:
                total += float(c.get("valorInicialCompra") or c.get("valorFinalCompra") or 0)
            except (TypeError, ValueError):
                pass
        orgaos = sorted({
            ((c.get("unidadeGestora") or {}).get("orgaoVinculado") or {}).get("nome")
            or ((c.get("unidadeGestora") or {}).get("nome")) or ""
            for c in contratos
        } - {""})
        out.append(Finding(
            kind=FindingKind.NOTE,
            value=f"{len(contratos)}+ contrato(s) com o governo federal"
                  + (f", {_brl(total)} na 1ª página" if total else ""),
            source="portal_contratos", source_label="Portal da Transparência — Contratos",
            url=f"https://portaldatransparencia.gov.br/busca?termo={digits}",
            confidence=Confidence.CONFIRMED,
            detail=("Órgãos: " + "; ".join(orgaos[:6])) if orgaos else "Contratos federais do CNPJ.",
        ))

    erros.conferir()
    return out


# ── registro.br: domínios .br têm titular público ───────────────────────────

def registrobr_findings(entity: Entity) -> Iterable[Finding]:
    root = entity.get("root") or entity.value
    if not root.endswith(".br"):
        return []
    try:
        data = net.get_json(
            f"https://brasilapi.com.br/api/registrobr/v1/{root}", timeout=15, ttl=24 * 3600,
        ) or {}
    except Exception:
        return []
    if not data or data.get("status") in (0, None):
        return []

    out: list[Finding] = []
    situacao = data.get("status") or "?"
    out.append(Finding(
        kind=FindingKind.NOTE, value=f"Domínio .br — situação: {situacao}",
        source="registrobr", source_label="Registro.br (via BrasilAPI)",
        url=f"https://registro.br/tecnologia/ferramentas/whois/?search={root}",
        confidence=Confidence.CONFIRMED,
        detail=f"Criado em {data.get('created') or 'n/d'}, expira em {data.get('expires-at') or 'n/d'}.",
        raw=data,
    ))
    if data.get("owner"):
        out.append(Finding(
            kind=FindingKind.COMPANY, value=str(data["owner"]),
            source="registrobr", source_label="Registro.br",
            confidence=Confidence.CONFIRMED, detail="Titular declarado do domínio .br",
        ))
    doc = data.get("ownerid") or data.get("owner-id")
    if doc:
        limpo = only_digits(str(doc))
        tipo = "CNPJ" if len(limpo) == 14 else "CPF" if len(limpo) == 11 else "documento"
        out.append(Finding(
            kind=FindingKind.DOCUMENT, value=str(doc),
            source="registrobr", source_label="Registro.br",
            confidence=Confidence.CONFIRMED,
            detail=f"{tipo} do titular do domínio — pivô direto para a Receita.",
        ))
    for host in data.get("hosts") or []:
        out.append(Finding(
            kind=FindingKind.NOTE, value=f"NS: {host}",
            source="registrobr", source_label="Registro.br",
            confidence=Confidence.CONFIRMED, detail="Servidor de nomes declarado",
        ))
    return out


# ── Querido Diário: diários oficiais municipais ─────────────────────────────

def _diario_busca(querystring: str) -> dict:
    return net.get_json(
        "https://api.queridodiario.ok.org.br/gazettes",
        params={
            "querystring": querystring,
            "size": 10,
            "excerpt_size": 400,
            "number_of_excerpts": 1,
            "sort_by": "descending_date",
        },
        timeout=25, ttl=24 * 3600,
    ) or {}


def querido_diario_findings(entity: Entity) -> Iterable[Finding]:
    """
    Busca o alvo em diários oficiais de mais de 3.000 municípios. É onde
    aparecem nomeação, licitação vencida, contrato com prefeitura, multa e
    processo administrativo — coisa que raramente está indexada no Google.

    Para CPF, procura também a forma mascarada da LGPD (***.456.789-**), que
    é como a maioria dos diários publica hoje. Achado só pelo miolo pode ser
    outra pessoa, e sai com confiança menor.
    """
    termo = entity.value
    if len(termo) < 5:
        return []

    consultas: list[tuple[str, Confidence, str]] = []
    if entity.type is EntityType.CPF:
        consultas.append((f'"{termo}" | "{entity.get("digits", "")}"', Confidence.CONFIRMED, ""))
        if entity.get("miolo"):
            consultas.append((f'"{entity.get("miolo")}"', Confidence.POSSIBLE,
                              "CPF mascarado (só o miolo bate): confira o nome no trecho. "))
    elif entity.type is EntityType.CNPJ:
        consultas.append((f'"{termo}" | "{entity.get("digits", "")}"', Confidence.CONFIRMED, ""))
    else:
        consultas.append((f'"{termo}"', Confidence.CONFIRMED, ""))

    out: list[Finding] = []
    vistos: set[str] = set()
    falhas = 0
    for querystring, confianca, aviso in consultas:
        try:
            data = _diario_busca(querystring)
        except Exception:  # noqa: BLE001
            falhas += 1
            continue
        gazetas = [g for g in (data.get("gazettes") or []) if g.get("url") not in vistos]
        if not gazetas:
            continue
        total = data.get("total_gazettes") or len(gazetas)
        out.append(Finding(
            kind=FindingKind.NOTE,
            value=f"{total} menção(ões) em diários oficiais municipais"
                  + (" (CPF mascarado)" if confianca is Confidence.POSSIBLE else ""),
            source="querido_diario", source_label="Querido Diário (Open Knowledge Brasil)",
            url=f"https://queridodiario.ok.org.br/pesquisa?term={termo.replace(' ', '+')}",
            confidence=confianca,
            detail=aviso + "Diários municipais raramente aparecem no Google — é onde saem "
                   "nomeação, contrato com prefeitura, licitação e sanção administrativa.",
        ))
        for g in gazetas[:8]:
            vistos.add(g.get("url"))
            municipio = g.get("territory_name") or "município n/d"
            uf = g.get("state_code") or ""
            data_pub = g.get("date") or ""
            trecho = " ".join((g.get("excerpts") or [""])[0].split())[:280]
            out.append(Finding(
                kind=FindingKind.LEGAL,
                value=f"Diário Oficial de {municipio}/{uf} — {data_pub}",
                source="querido_diario", source_label="Querido Diário",
                url=g.get("url"), confidence=confianca,
                detail=aviso + (trecho or "Menção ao termo no diário oficial do município."),
                raw={"territory_id": g.get("territory_id"), "date": data_pub},
            ))
            out.append(Finding(
                kind=FindingKind.ADDRESS, value=f"{municipio}/{uf}",
                source="querido_diario", source_label="Querido Diário",
                url=g.get("url"), confidence=Confidence.POSSIBLE,
                detail=f"Município onde o alvo é citado em diário oficial ({data_pub}).",
            ))
    if falhas and falhas == len(consultas):
        raise RuntimeError("API do Querido Diário não respondeu")
    return out


# ── IBGE: contexto geográfico ───────────────────────────────────────────────

def ibge_por_cep(cep: str) -> dict | None:
    from .br import cep_lookup

    dados = cep_lookup(cep)
    if not dados:
        return None
    return dados
