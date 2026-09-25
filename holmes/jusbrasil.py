"""
JusBrasil pelo Web Unlocker: de link para fato.

Antes o motor só montava o link de busca do JusBrasil. Agora ele lê a página
(pela Bright Data, em markdown) e extrai o que interessa:

* busca por nome: pessoas com aquele nome (faixa etária), empresas ligadas ao
  nome e menções em diários oficiais;
* página da pessoa: as empresas em que ela é sócia ou administradora, com CNPJ
  e cargo, os estados onde aparece e os 3 dígitos do CPF que o site exibe;
* busca por CNPJ: empresas relacionadas (consorciada, sócia PJ, filial) e o
  contato declarado.

Custo: 1 requisição por CNPJ; até 3 por nome (busca + 2 páginas de pessoa).
O Escavador ficou de fora de propósito: a Bright Data só libera o Escavador
para conta com verificação KYC, e sem ela toda consulta falharia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import quote_plus

from . import net
from .br_auto import _sem_acento
from .entity import Entity, EntityType, only_digits
from .findings import Confidence, Finding, FindingKind

BASE = "https://www.jusbrasil.com.br"
MAX_PAGINAS_PESSOA = 2
SOURCE = "jusbrasil"
LABEL = "JusBrasil (Web Unlocker)"

_CARD_RE = re.compile(
    r"\[([^\[\]]*?)\]\((https?://www\.jusbrasil\.com\.br/nome/[^)\s]+)\)", re.DOTALL
)
_CNPJ_RE = re.compile(r"CNPJ\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s*•?\s*(.*)")
_IDADE_RE = re.compile(r"(\d{1,3}\s*a\s*\d{1,3}\s*anos|mais de \d+ anos)", re.IGNORECASE)
_RELACAO_RE = re.compile(r"^(.+?)\s+é\s+(.+)$")
_DIARIO_RE = re.compile(r"\[([^\[\]]+)\]\((https?://www\.jusbrasil\.com\.br/diarios/[^)\s]+)\)")
_DATA_POR_RE = re.compile(
    r"publicado em\s*(\d{2}/\d{2}/\d{4})\s*por\s*(?:\[([^\]]+)\]\([^)]*\)|([^\n]+))"
)
_TOTAL_RE = re.compile(r"(Mais de\s+)?([\d.]+)\s+resultados?", re.IGNORECASE)
_CPF_PARCIAL_RE = re.compile(r"CPF\s*([*\dXx.\-]{11,14})")


@dataclass
class Card:
    """Um cartão de pessoa ou empresa como o JusBrasil lista."""

    url: str
    tipo: str                       # "pessoa" | "empresa"
    nome: str
    linhas: list[str] = field(default_factory=list)
    cnpj: str = ""
    uf: str = ""
    idade: str = ""
    relacao: str = ""               # "Sócio-Administrador", "Sociedade Consorciada"…


def normalizar(md: str) -> str:
    """O markdown chega com colchetes escapados (`\\[`, `]\\(`) — tira o escape."""
    md = re.sub(r"\\([\[\]()*_#])", r"\1", md or "")
    return md.replace("\r", "")


def _limpar_linha(linha: str) -> str:
    linha = re.sub(r"^[\s#*>\-]+", "", linha)
    linha = linha.replace("**", "").strip()
    return linha


def parse_cards(md: str) -> list[Card]:
    cards: list[Card] = []
    for bloco, url in _CARD_RE.findall(normalizar(md)):
        linhas = [_limpar_linha(x) for x in bloco.splitlines()]
        linhas = [x for x in linhas if x and x.lower() != "verificar processos"]
        if not linhas:
            continue
        card = Card(url=url, tipo="empresa" if "/cnpj-" in url else "pessoa",
                    nome=linhas[0], linhas=linhas)
        for linha in linhas[1:]:
            m = _CNPJ_RE.search(linha)
            if m:
                card.cnpj, card.uf = m.group(1), m.group(2).strip(" •")
                continue
            m = _IDADE_RE.search(linha)
            if m and not card.idade:
                card.idade = m.group(1)
                resto = linha[m.end():].strip(" •")
                if resto:
                    card.uf = resto
                continue
            m = _RELACAO_RE.match(linha)
            if m and not card.relacao:
                card.relacao = m.group(2).strip()
        # Empresa com nome fantasia vem com a razão social na segunda linha.
        if card.tipo == "empresa" and len(linhas) > 1 and not _CNPJ_RE.search(linhas[1]):
            card.nome = f"{linhas[1]} ({linhas[0]})" if linhas[1] != linhas[0] else linhas[0]
        cards.append(card)
    return cards


def parse_diarios(md: str, limite: int = 5) -> tuple[str, list[dict]]:
    """(total anunciado, itens) da seção «Diários Oficiais» da busca."""
    texto = normalizar(md)
    inicio = texto.find("Diários Oficiais\n")
    if inicio < 0:
        return "", []
    trecho = texto[inicio:]
    fim = trecho.find("Mostrar mais Diários")
    if fim > 0:
        trecho = trecho[:fim]
    total = ""
    m = _TOTAL_RE.search(trecho[:200])
    if m:
        total = f"{'mais de ' if m.group(1) else ''}{m.group(2)}"

    itens: list[dict] = []
    links = list(_DIARIO_RE.finditer(trecho))
    for i, link in enumerate(links[:limite]):
        corpo = trecho[link.end(): links[i + 1].start() if i + 1 < len(links) else len(trecho)]
        meta = _DATA_POR_RE.search(corpo)
        excerto = corpo[meta.end():] if meta else corpo
        excerto = " ".join(excerto.split()).strip(" [")[:300]
        itens.append({
            "titulo": link.group(1).strip(),
            "url": link.group(2),
            "data": meta.group(1) if meta else "",
            "orgao": (meta.group(2) or meta.group(3) or "").strip() if meta else "",
            "trecho": excerto,
        })
    return total, itens


def parse_pessoa(md: str) -> dict:
    """Página /nome/<slug>/cpf-…: CPF parcial, estados e empresas."""
    texto = normalizar(md)
    out: dict = {"cpf_parcial": "", "idade": "", "estados": "", "empresas": []}
    m = _CPF_PARCIAL_RE.search(texto)
    if m:
        out["cpf_parcial"] = m.group(1)
    for linha in texto.splitlines()[:40]:
        linha = _limpar_linha(linha)
        m = _IDADE_RE.search(linha)
        if m:
            out["idade"] = m.group(1)
            out["estados"] = linha[m.end():].strip(" •")
            break
    out["empresas"] = [c for c in parse_cards(texto) if c.tipo == "empresa"]
    return out


def parse_empresa(md: str) -> dict:
    """Página de empresa (a busca por CNPJ cai nela): contato e relacionadas."""
    texto = normalizar(md)
    linhas = [_limpar_linha(x) for x in texto.splitlines()]
    linhas = [x for x in linhas if x]
    campos: dict[str, list[str]] = {}
    rotulos = {"Razão social", "Nome fantasia", "Situação cadastral", "Data de abertura",
               "Capital social", "Natureza jurídica", "Porte", "Contato", "Localização",
               "CNAE Principal"}
    atual = None
    for linha in linhas:
        if linha in rotulos:
            atual = linha
            campos[atual] = []
            continue
        if atual:
            if linha.startswith("CNAEs secundários") or linha.startswith("Os dados cadastrais"):
                atual = None
                continue
            if len(campos[atual]) < 3:
                campos[atual].append(linha)
    return {"campos": campos, "relacionadas": [c for c in parse_cards(texto) if c.tipo == "empresa"]}


# ── conectores ──────────────────────────────────────────────────────────────

def _nome_exato(alvo: str, achado: str) -> bool:
    a = [t for t in re.split(r"\W+", _sem_acento(alvo)) if t]
    b = [t for t in re.split(r"\W+", _sem_acento(achado)) if t]
    return bool(a) and a == b


def _buscar(termo: str) -> str:
    return net.unlocked_fetch(f"{BASE}/busca?q={quote_plus(termo)}",
                              data_format="markdown", ttl=3 * 86400)


def _empresa_finding(card: Card, confianca: Confidence, contexto: str) -> Finding:
    return Finding(
        kind=FindingKind.COMPANY, value=card.nome, source=SOURCE, source_label=LABEL,
        url=card.url, confidence=confianca,
        detail=", ".join(p for p in [
            f"CNPJ {card.cnpj}" if card.cnpj else "", card.uf,
            card.relacao, contexto,
        ] if p),
        raw={"cnpj": card.cnpj, "relacao": card.relacao},
    )


def nome_findings(entity: Entity) -> Iterable[Finding]:
    md = _buscar(entity.value)
    cards = parse_cards(md)
    out: list[Finding] = []

    pessoas = [c for c in cards if c.tipo == "pessoa" and _nome_exato(entity.value, c.nome)]
    if pessoas:
        idades = "; ".join(p.idade for p in pessoas if p.idade)
        out.append(Finding(
            kind=FindingKind.NOTE,
            value=f"JusBrasil: {len(pessoas)} pessoa(s) com este nome exato",
            source=SOURCE, source_label=LABEL,
            url=f"{BASE}/busca?q={quote_plus(entity.value)}",
            confidence=Confidence.CONFIRMED,
            detail=(f"Faixa etária: {idades}. " if idades else "")
                   + ("Mais de uma pessoa: as empresas abaixo podem ser de homônimos."
                      if len(pessoas) > 1 else "Uma só pessoa com o nome exato."),
        ))

    # Uma pessoa só com o nome exato: o que vier da página dela é provável.
    # Várias: pode ser qualquer uma, então fica como possível.
    conf_pessoa = Confidence.LIKELY if len(pessoas) == 1 else Confidence.POSSIBLE
    vistos: set[str] = set()
    for pessoa in pessoas[:MAX_PAGINAS_PESSOA]:
        try:
            dados = parse_pessoa(net.unlocked_fetch(pessoa.url, data_format="markdown", ttl=7 * 86400))
        except net.UnlockerError:
            continue
        if dados["estados"] or dados["cpf_parcial"]:
            out.append(Finding(
                kind=FindingKind.NOTE,
                value=f"JusBrasil: {pessoa.nome} ({dados['idade'] or pessoa.idade or 'idade n/d'})",
                source=SOURCE, source_label=LABEL, url=pessoa.url, confidence=conf_pessoa,
                detail=", ".join(p for p in [
                    f"aparece em: {dados['estados']}" if dados["estados"] else "",
                    f"CPF exibido: {dados['cpf_parcial']}" if dados["cpf_parcial"] else "",
                ] if p),
            ))
        for emp in dados["empresas"]:
            if emp.url in vistos:
                continue
            vistos.add(emp.url)
            out.append(_empresa_finding(emp, conf_pessoa, f"vínculo de {pessoa.nome}"))

    # Empresas que levam o nome (campanha eleitoral, firma individual…).
    for card in cards:
        if card.tipo == "empresa" and card.url not in vistos:
            vistos.add(card.url)
            out.append(_empresa_finding(card, Confidence.POSSIBLE, "empresa listada na busca pelo nome"))

    total, diarios = parse_diarios(md)
    if diarios:
        out.append(Finding(
            kind=FindingKind.NOTE,
            value=f"JusBrasil: {total or len(diarios)} menção(ões) em diários oficiais",
            source=SOURCE, source_label=LABEL,
            url=f"{BASE}/diarios/busca?q={quote_plus(entity.value)}",
            confidence=Confidence.CONFIRMED,
            detail="Diários de tribunais e órgãos federais, estaduais e municipais.",
        ))
        for d in diarios:
            out.append(Finding(
                kind=FindingKind.LEGAL,
                value=f"{d['titulo']}" + (f" ({d['data']})" if d["data"] else ""),
                source=SOURCE, source_label=LABEL, url=d["url"],
                confidence=Confidence.POSSIBLE,
                detail=(f"{d['orgao']}: " if d["orgao"] else "") + d["trecho"],
            ))
    return out


def cnpj_findings(entity: Entity) -> Iterable[Finding]:
    digits = only_digits(entity.value)
    md = _buscar(digits)
    dados = parse_empresa(md)
    out: list[Finding] = []
    url = f"{BASE}/busca?q={digits}"

    for contato in dados["campos"].get("Contato", []):
        if "@" in contato:
            out.append(Finding(kind=FindingKind.EMAIL, value=contato.lower(), source=SOURCE,
                               source_label=LABEL, url=url, confidence=Confidence.CONFIRMED,
                               detail="Contato declarado (espelho da Receita no JusBrasil)"))
        elif len(only_digits(contato)) >= 10:
            out.append(Finding(kind=FindingKind.PHONE, value=contato, source=SOURCE,
                               source_label=LABEL, url=url, confidence=Confidence.CONFIRMED,
                               detail="Contato declarado (espelho da Receita no JusBrasil)"))

    proprio = entity.value
    for card in dados["relacionadas"]:
        if card.cnpj == proprio:
            continue
        out.append(_empresa_finding(card, Confidence.CONFIRMED, "empresa relacionada"))
    if dados["relacionadas"]:
        out.insert(0, Finding(
            kind=FindingKind.NOTE,
            value=f"JusBrasil: {len(dados['relacionadas'])} empresa(s) relacionada(s)",
            source=SOURCE, source_label=LABEL, url=url, confidence=Confidence.CONFIRMED,
            detail="Consórcios, sócias pessoa jurídica e demais vínculos societários.",
        ))
    return out


def findings(entity: Entity) -> Iterable[Finding]:
    if entity.type is EntityType.CNPJ:
        return cnpj_findings(entity)
    if entity.type is EntityType.NAME:
        return nome_findings(entity)
    return []
