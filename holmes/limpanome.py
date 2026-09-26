"""
Limpar Nome: o motor do serviço de contestação de negativação.

Não é uma página de texto com prompts para copiar. É um fluxo que faz o
trabalho: classifica cada registro pela regra certa, calcula os prazos em
dias úteis, escreve os documentos citando só lei brasileira e acompanha os
protocolos até a baixa.

Base legal usada (e só ela):
  CDC art. 43 §1   teto de 5 anos para informação negativa
  CDC art. 43 §2   comunicação prévia por escrito antes da abertura do cadastro
  CDC art. 43 §3   correção de dado inexato em 5 dias úteis
  CDC art. 43 §5   prescrita a cobrança, a informação não pode ser fornecida
  Súmula 323 STJ   os 5 anos valem mesmo que a ação de cobrança prescreva antes
  Súmula 359 STJ   cabe ao órgão mantenedor notificar o devedor antes de inscrever
  Súmula 385 STJ   anotação legítima anterior afasta indenização por nova inscrição
  Súmula 404 STJ   a notificação prévia dispensa aviso de recebimento
  Súmula 548 STJ   pago o débito, o credor tem 5 dias úteis para pedir a baixa
  Tema 1.315 STJ   notificação eletrônica vale se provados envio e entrega (2026)
  REsp 1.316.117   os 5 anos correm do dia seguinte ao vencimento, não da inscrição
  CC art. 206 §3 V indenização por negativação indevida prescreve em 3 anos
  Lei 12.414/2011  Cadastro Positivo (histórico de pagamento a favor do consumidor)

Protesto em cartório é outro regime (Lei 9.492/1997):
  art. 26          cancelamento com o título ou a carta de anuência do credor
  Tema 725 STJ     protesto legítimo: após pagar, cabe ao DEVEDOR pedir o cancelamento
  O registro no cartório não cai sozinho com o tempo: precisa ser cancelado.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

# ── Dias úteis e feriados nacionais ────────────────────────────────────────

_FERIADOS_FIXOS = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Consciência Negra",   # nacional desde a Lei 14.759/2023
    (12, 25): "Natal",
}


def pascoa(ano: int) -> date:
    """Domingo de Páscoa pelo algoritmo de Meeus/Jones/Butcher."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def feriados_nacionais(ano: int) -> dict[date, str]:
    """Feriados nacionais do ano. Ponto facultativo (Carnaval, Corpus Christi)
    entra porque o consumidor.gov.br e os birôs não contam esses dias."""
    out = {date(ano, m, d): nome for (m, d), nome in _FERIADOS_FIXOS.items()}
    p = pascoa(ano)
    out[p - timedelta(days=48)] = "Carnaval"
    out[p - timedelta(days=47)] = "Carnaval"
    out[p - timedelta(days=2)] = "Sexta-feira Santa"
    out[p + timedelta(days=60)] = "Corpus Christi"
    return out


def e_dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in feriados_nacionais(d.year)


def somar_dias_uteis(inicio: date, n: int) -> date:
    """Data que cai n dias úteis depois de `inicio` (o próprio início não conta)."""
    d = inicio
    restantes = n
    while restantes > 0:
        d += timedelta(days=1)
        if e_dia_util(d):
            restantes -= 1
    return d


def dias_uteis_entre(a: date, b: date) -> int:
    """Dias úteis de a (exclusivo) até b (inclusivo). Negativo se b < a."""
    if b < a:
        return -dias_uteis_entre(b, a)
    d, n = a, 0
    while d < b:
        d += timedelta(days=1)
        if e_dia_util(d):
            n += 1
    return n


# ── Modelo de dados ────────────────────────────────────────────────────────

SITUACOES = {
    "nao_reconheco": "Não reconheço esta dívida",
    "ja_paguei": "Já paguei",
    "valor_errado": "O valor está errado",
    "minha_no_prazo": "É minha e ainda vale",
    "nao_sei": "Não sei / preciso confirmar",
}
PROTESTO = "Cartório de protesto"
BIROS = ("Serasa", "SPC Brasil", "Boa Vista", "Quod", PROTESTO, "Outro")
NOTIFICADO = {"sim": "Sim", "nao": "Não", "nao_sei": "Não sei"}

PILHAS = {
    "errado": "Registro errado",
    "vencido": "Mais de 5 anos do vencimento",
    "verdadeira": "Dívida verdadeira e no prazo",
    "duvida": "Precisa confirmar a data",
}
# Ordem sugerida de ataque: a pilha mais fácil primeiro, para ter o protocolo
# funcionando e aprender o caminho antes do caso difícil.
PRIORIDADE = {"ja_paguei": 1, "vencido": 2, "valor_errado": 3, "nao_reconheco": 4,
              "verdadeira": 5, "duvida": 6}


@dataclass
class Registro:
    credor: str
    valor: float = 0.0
    vencimento: str | None = None      # ISO AAAA-MM-DD
    inclusao: str | None = None        # data em que apareceu no birô
    biro: str = "Serasa"
    situacao: str = "nao_sei"
    notificado: str = "nao_sei"        # avisado por escrito antes da inscrição?
    comprovante: bool = False          # tem comprovante de pagamento?
    data_pagamento: str | None = None
    cnpj_credor: str = ""
    observacao: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def venc(self) -> date | None:
        return _data(self.vencimento)

    def valor_fmt(self) -> str:
        return moeda(self.valor)


@dataclass
class Protocolo:
    registro_id: str
    canal: str                         # consumidor.gov.br | biro | credor | procon
    data: str                          # ISO
    numero: str = ""
    resposta: str = ""
    data_resposta: str | None = None
    aceito: bool | None = None
    data_baixa: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class Caso:
    nome: str = ""
    cpf_mascarado: str = ""
    registros: list[Registro] = field(default_factory=list)
    protocolos: list[Protocolo] = field(default_factory=list)
    criado: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    atualizado: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    def registro(self, rid: str) -> Registro | None:
        return next((r for r in self.registros if r.id == rid), None)


# ── Análise de cada registro ───────────────────────────────────────────────

@dataclass
class Argumento:
    titulo: str
    base: str
    texto: str
    forca: int                          # 3 forte, 2 médio, 1 apoio


@dataclass
class Analise:
    pilha: str
    prioridade: int
    limite_5_anos: date | None
    dias_para_vencer_prazo: int | None   # negativo = já passou
    argumentos: list[Argumento]
    canal: str
    documentos: list[str]
    proximo_passo: str
    alerta: str = ""

    @property
    def pilha_label(self) -> str:
        return PILHAS[self.pilha]

    @property
    def argumento_principal(self) -> Argumento | None:
        return max(self.argumentos, key=lambda a: a.forca) if self.argumentos else None


def _arg_5_anos(limite: date) -> Argumento:
    return Argumento(
        "Passou o teto de 5 anos",
        "CDC art. 43 §1 e Súmula 323 do STJ",
        f"O registro só pode ficar até 5 anos contados do vencimento da dívida. "
        f"Esse prazo terminou em {data_br(limite)}. Vale mesmo que a dívida exista.",
        3,
    )


def _arg_notificacao() -> Argumento:
    return Argumento(
        "Não houve aviso prévio",
        "CDC art. 43 §2, Súmulas 359 e 404 e Tema 1.315 do STJ",
        "Antes de inscrever o nome, o birô precisa comunicar o consumidor. O aviso pode ser "
        "por carta (sem AR) ou eletrônico, mas quem inscreveu tem de provar o envio e a entrega. "
        "Sem essa prova, a inscrição é irregular e deve ser cancelada.",
        2,
    )


def analisar(r: Registro, hoje: date | None = None) -> Analise:
    """Classifica o registro e monta a estratégia. Determinístico e sem LLM:
    a regra é a lei, não uma opinião do modelo."""
    hoje = hoje or date.today()
    if r.biro == PROTESTO:
        return _analisar_protesto(r, hoje)
    venc = r.venc()
    # REsp 1.316.117/SC: o prazo começa no dia seguinte ao vencimento.
    limite = somar_anos(venc + timedelta(days=1), 5) if venc else None
    dias = (limite - hoje).days if limite else None
    args: list[Argumento] = []
    alerta = ""

    passou_5_anos = dias is not None and dias < 0
    if passou_5_anos and limite:
        args.append(_arg_5_anos(limite))
    if r.notificado == "nao":
        args.append(_arg_notificacao())

    if r.situacao == "ja_paguei":
        pilha = "errado"
        args.insert(0, Argumento(
            "Dívida já paga e registro mantido",
            "CDC art. 43 §3 e Súmula 548 do STJ",
            "Depois do pagamento o credor tem 5 dias úteis para pedir a baixa. "
            "Manter o registro depois disso é a situação que mais gera condenação por dano moral.",
            3 if r.comprovante else 2,
        ))
        if not r.comprovante:
            alerta = "Sem comprovante o pedido enfraquece. Procure o extrato, o recibo ou o boleto pago antes de protocolar."
        canal = "consumidor.gov.br"
        docs = ["reclamacao_pos_pagamento", "consumidor_gov"]
        passo = "Anexe o comprovante e peça a baixa imediata. É o caso mais rápido."

    elif r.situacao == "nao_reconheco":
        pilha = "errado"
        args.insert(0, Argumento(
            "Dívida não reconhecida: cabe ao credor provar",
            "CDC art. 43 §3 e art. 6º, VIII (inversão do ônus da prova)",
            "Quem inscreve precisa mostrar o contrato ou o documento que originou a dívida. "
            "Sem prova, o registro cai. Se houve fraude com o seu CPF, cabe indenização.",
            3,
        ))
        canal = "consumidor.gov.br"
        docs = ["contestacao_nao_reconheco", "consumidor_gov"]
        passo = "Peça o documento de origem. Se a resposta vier sem contrato assinado, o registro é indevido."
        if not passou_5_anos:
            alerta = "Deixe este para depois dos casos fáceis: pode virar apuração de fraude e demora mais."

    elif r.situacao == "valor_errado":
        pilha = "errado"
        args.insert(0, Argumento(
            "Valor registrado diferente do devido",
            "CDC art. 43 §3",
            "Dado inexato tem de ser corrigido em 5 dias úteis. O registro com valor errado não pode ficar como está.",
            2,
        ))
        canal = "consumidor.gov.br"
        docs = ["contestacao_valor", "consumidor_gov"]
        passo = "Informe o valor que você reconhece e peça a correção ou a exclusão."

    elif passou_5_anos:
        pilha = "vencido"
        canal = "biro"
        docs = ["pedido_baixa_prazo", "consumidor_gov"]
        passo = ("Peça a baixa direto ao birô citando o art. 43 §1. É quase automático. "
                 "A dívida continua existindo, mas não pode ser cobrada na Justiça nem ficar negativada.")

    elif r.situacao == "minha_no_prazo":
        pilha = "verdadeira"
        canal = "credor"
        docs = ["roteiro_negociacao"]
        passo = "Aqui não tem contestação, tem negociação. Acordo pago tira o registro."
        if limite:
            passo += f" O registro sai sozinho em {data_br(limite)}."

    else:
        pilha = "duvida"
        canal = "biro"
        docs = ["pedido_documento_origem"]
        passo = "Antes de contestar, peça ao birô e ao credor o documento de origem com a data de vencimento."
        if venc is None:
            alerta = "Sem a data de vencimento não dá para saber se os 5 anos passaram. É o argumento mais forte, vale a pena descobrir."

    if r.situacao in ("minha_no_prazo", "nao_sei") and r.notificado == "nao":
        docs.append("contestacao_sem_notificacao")

    return Analise(
        pilha=pilha,
        prioridade=PRIORIDADE["vencido"] if pilha == "vencido" else PRIORIDADE.get(r.situacao, 6),
        limite_5_anos=limite,
        dias_para_vencer_prazo=dias,
        argumentos=args,
        canal=canal,
        documentos=list(dict.fromkeys(docs)),
        proximo_passo=passo,
        alerta=alerta,
    )


def _analisar_protesto(r: Registro, hoje: date) -> Analise:
    """Protesto não segue o art. 43 do CDC nem os prazos dos birôs: o caminho
    é o cancelamento no cartório, e quem pede depende de o protesto ser devido."""
    arg_cancel = Argumento(
        "Cancelamento com carta de anuência",
        "Lei 9.492/1997, art. 26, e Tema 725 do STJ",
        "Pago o título, o cancelamento é pedido no cartório com a carta de anuência do credor. "
        "Em protesto legítimo, quem pede é o devedor; o credor tem de fornecer a carta.",
        3,
    )
    alerta = ""
    if r.situacao == "ja_paguei":
        pilha, prioridade = "errado", 1
        args = [arg_cancel]
        canal = "credor"
        docs = ["pedido_carta_anuencia"]
        passo = ("Peça a carta de anuência ao credor e leve ao cartório, ou cancele online pela CENPROT "
                 "(resolve.cenprot.org.br). Há emolumentos a pagar no cancelamento.")
        if not r.comprovante:
            alerta = "Separe o comprovante de pagamento: o credor vai pedir antes de emitir a carta."
    elif r.situacao in ("nao_reconheco", "valor_errado"):
        pilha, prioridade = "errado", 4
        args = [Argumento(
            "Protesto indevido",
            "Lei 9.492/1997 e CDC art. 6º, VIII",
            "Título que não é seu, já pago antes do protesto ou com valor errado torna o protesto indevido. "
            "Cabe ao credor dar a anuência sem custo para você; se recusar, o cancelamento é judicial, "
            "com pedido de dano moral.",
            3,
        )]
        canal = "credor"
        docs = ["contestacao_protesto", "pedido_carta_anuencia"]
        passo = ("Peça ao credor o título que originou o protesto e a carta de anuência. Sem resposta, "
                 "o caminho é o Juizado: cancelamento do protesto e dano moral.")
    elif r.situacao == "minha_no_prazo":
        pilha, prioridade = "verdadeira", 5
        args = [arg_cancel]
        canal = "credor"
        docs = ["roteiro_negociacao", "pedido_carta_anuencia"]
        passo = ("Negocie com o credor e exija, no acordo, a entrega da carta de anuência. "
                 "Depois de pagar, cancele no cartório ou pela CENPROT.")
    else:
        pilha, prioridade = "duvida", 6
        args = []
        canal = "credor"
        docs = ["pedido_documento_origem"]
        passo = ("Tire a certidão ou consulte o protesto na CENPROT (pesquisaprotesto.com.br) para ver "
                 "credor, valor e cartório antes de decidir.")
    alerta = alerta or "Protesto não cai sozinho em 5 anos como o registro do Serasa: no cartório ele só sai com cancelamento."
    return Analise(pilha=pilha, prioridade=prioridade, limite_5_anos=None, dias_para_vencer_prazo=None,
                   argumentos=args, canal=canal, documentos=docs, proximo_passo=passo, alerta=alerta)


def ordem_de_ataque(caso: Caso, hoje: date | None = None) -> list[tuple[Registro, Analise]]:
    """Registros na ordem em que devem ser atacados: fácil primeiro."""
    pares = [(r, analisar(r, hoje)) for r in caso.registros]
    return sorted(pares, key=lambda p: (p[1].prioridade, -p[0].valor))


def resumo(caso: Caso, hoje: date | None = None) -> dict:
    pares = ordem_de_ataque(caso, hoje)
    por_pilha: dict[str, int] = {k: 0 for k in PILHAS}
    total_contestavel = 0.0
    for r, a in pares:
        por_pilha[a.pilha] += 1
        if a.pilha in ("errado", "vencido"):
            total_contestavel += r.valor
    return {
        "registros": len(pares),
        "por_pilha": por_pilha,
        "valor_total": sum(r.valor for r, _ in pares),
        "valor_contestavel": total_contestavel,
        "protocolos": len(caso.protocolos),
        "baixados": sum(1 for p in caso.protocolos if p.data_baixa),
    }


def avisos_do_caso(caso: Caso, hoje: date | None = None) -> list[str]:
    """Alertas que dependem do conjunto, não de um registro só."""
    avisos: list[str] = []
    pares = ordem_de_ataque(caso, hoje)
    if any(a.pilha == "verdadeira" for _, a in pares) and any(a.pilha in ("errado", "vencido") for _, a in pares):
        avisos.append(
            "Você tem uma dívida verdadeira e no prazo junto com registros contestáveis. Pela Súmula 385 do STJ, "
            "enquanto houver uma negativação legítima, não cabe indenização por dano moral pelas indevidas. "
            "A exclusão continua valendo. Se quiser pleitear indenização, negocie a verdadeira primeiro.")
    if any(a.pilha == "duvida" for _, a in pares):
        avisos.append("Há registro sem data de vencimento. Sem ela não dá para usar o argumento dos 5 anos, "
                      "que é o mais forte. Peça o documento de origem antes de contestar.")
    biros = {r.biro for r, _ in pares}
    if pares and len(biros - {PROTESTO}) == 1:
        avisos.append(f"Todos os registros são do {next(iter(biros - {PROTESTO}))}. Consulte também os outros "
                      "birôs: um registro pode estar só num deles.")
    if pares and PROTESTO not in biros:
        avisos.append("Consulte também protesto em cartório (gratuito em pesquisaprotesto.com.br). Protesto "
                      "é um registro separado do Serasa e segue regras próprias.")
    return avisos


# ── Acompanhamento de prazos ───────────────────────────────────────────────

PRAZO_RESPOSTA_DIAS = 10           # consumidor.gov.br: dias corridos para a empresa responder
PRAZO_AVALIACAO_DIAS = 20          # depois da resposta, o consumidor avalia em até 20 dias
PRAZO_EXCLUSAO_DIAS_UTEIS = 5      # CDC art. 43 §3 / Súmula 548: dias úteis para a baixa

CANAIS = {
    "consumidor.gov.br": "consumidor.gov.br",
    "biro": "Direto no birô",
    "credor": "Direto com o credor",
    "procon": "Procon",
}


def situacao_protocolo(p: Protocolo, hoje: date | None = None) -> dict:
    """Estado do protocolo e o que fazer agora, com os prazos em dias úteis."""
    hoje = hoje or date.today()
    inicio = _data(p.data) or hoje
    limite_resposta = inicio + timedelta(days=PRAZO_RESPOSTA_DIAS)
    out = {"limite_resposta": limite_resposta, "limite_exclusao": None,
           "status": "", "acao": "", "atrasado": False}

    if p.data_baixa:
        out["status"] = "Baixado"
        out["acao"] = "Guarde o print do birô sem o registro. Caso encerrado."
        return out

    if p.aceito is True:
        base = _data(p.data_resposta) or hoje
        limite_exc = somar_dias_uteis(base, PRAZO_EXCLUSAO_DIAS_UTEIS)
        out["limite_exclusao"] = limite_exc
        if hoje > limite_exc:
            out.update(status="Aceito, exclusão atrasada", atrasado=True,
                       acao=f"A empresa aceitou em {data_br(base)} e tinha até {data_br(limite_exc)} "
                            f"para excluir. Consulte o birô e, se ainda constar, registre nova reclamação "
                            f"citando o descumprimento: manter registro após aceite gera dano moral.")
        else:
            out.update(status="Aceito, aguardando exclusão",
                       acao=f"Consulte o birô em {data_br(limite_exc)}. Se o registro ainda constar, volte aqui.")
        return out

    if p.aceito is False:
        out.update(status="Recusado",
                   acao="Leia o motivo. Se a empresa não apresentou o documento de origem, escale ao Procon "
                        "ou ao Juizado Especial Cível (sem advogado até 20 salários mínimos). O pedido de "
                        "indenização prescreve em 3 anos (CC art. 206 §3 V).")
        return out

    if hoje > limite_resposta:
        out.update(status="Sem resposta no prazo", atrasado=True,
                   acao=f"O prazo de {PRAZO_RESPOSTA_DIAS} dias venceu em {data_br(limite_resposta)}. "
                        f"Avalie a reclamação como não resolvida (você tem {PRAZO_AVALIACAO_DIAS} dias para isso) "
                        f"e abra o Procon. Guarde o print: a falta de resposta fica no histórico público da empresa.")
    else:
        faltam = (limite_resposta - hoje).days
        out.update(status="Aguardando resposta",
                   acao=f"A empresa tem até {data_br(limite_resposta)} ({faltam} dia(s)). "
                        f"Depois da resposta, avalie em até {PRAZO_AVALIACAO_DIAS} dias.")
    return out


# ── Documentos ─────────────────────────────────────────────────────────────

DOCUMENTOS = {
    "reclamacao_pos_pagamento": "Reclamação: registro mantido após pagamento",
    "contestacao_nao_reconheco": "Contestação: dívida não reconhecida",
    "contestacao_valor": "Contestação: valor errado",
    "pedido_baixa_prazo": "Pedido de baixa: mais de 5 anos",
    "contestacao_sem_notificacao": "Contestação: inscrição sem aviso prévio",
    "pedido_documento_origem": "Pedido do documento de origem",
    "consumidor_gov": "Texto para o consumidor.gov.br",
    "roteiro_negociacao": "Roteiro de negociação",
    "pedido_carta_anuencia": "Pedido de carta de anuência (protesto)",
    "contestacao_protesto": "Contestação: protesto indevido",
}


def _cabecalho(caso: Caso, r: Registro) -> str:
    quem = caso.nome or "o consumidor abaixo identificado"
    return (f"Eu, {quem}, CPF {caso.cpf_mascarado or '[CPF]'}, venho tratar do registro "
            f"negativo lançado por {r.credor}, no valor de {r.valor_fmt()}"
            + (f", com vencimento informado em {data_br(r.venc())}" if r.venc() else "")
            + f", que consta no {r.biro}.")


def _fecho(pedido: str) -> str:
    return (f"{pedido}\n\nPeço resposta por escrito dentro do prazo legal e guardo este pedido "
            f"como prova para as providências cabíveis.")


def gerar_documento(tipo: str, caso: Caso, r: Registro, hoje: date | None = None) -> str:
    """Texto pronto, sem LLM: só lei brasileira, sem promessa de score."""
    hoje = hoje or date.today()
    a = analisar(r, hoje)
    cab = _cabecalho(caso, r)

    if tipo == "reclamacao_pos_pagamento":
        pago = f" em {data_br(_data(r.data_pagamento))}" if r.data_pagamento else ""
        comp = "Tenho o comprovante de pagamento e o anexo a este pedido." if r.comprovante \
            else "Solicito que a empresa confirme em seus sistemas a quitação."
        return (f"{cab}\n\nEssa dívida foi paga{pago}. {comp}\n\n"
                f"Pelo art. 43, §3, do Código de Defesa do Consumidor, e pela Súmula 548 do STJ, "
                f"quitado o débito, cabe ao credor providenciar a baixa do registro em até 5 dias úteis. "
                f"A manutenção do nome negativado após o pagamento é indevida e gera dano moral.\n\n"
                + _fecho("Peço a exclusão imediata do registro e a comunicação da baixa aos birôs."))

    if tipo == "contestacao_nao_reconheco":
        extra = ""
        if a.limite_5_anos and a.dias_para_vencer_prazo is not None and a.dias_para_vencer_prazo < 0:
            extra = (f"\n\nAlém disso, o vencimento informado já passou de 5 anos em {data_br(a.limite_5_anos)}, "
                     f"o que por si só impede a manutenção do registro (CDC art. 43, §1, e Súmula 323 do STJ).")
        return (f"{cab}\n\nNão reconheço essa dívida. Não celebrei contrato com a empresa nem autorizei "
                f"qualquer operação que a justifique.\n\n"
                f"Solicito que a empresa apresente o contrato assinado ou o documento que deu origem ao débito, "
                f"com a data de vencimento. Cabe a quem inscreve provar a existência da dívida "
                f"(CDC art. 6º, VIII, e art. 43, §3). Sem essa comprovação, o registro é indevido e deve ser "
                f"excluído. Se a origem for uso indevido do meu CPF, informo desde já que registrarei boletim "
                f"de ocorrência.{extra}\n\n"
                + _fecho("Peço a exclusão do registro ou, no mínimo, sua suspensão até a apresentação da prova."))

    if tipo == "contestacao_valor":
        return (f"{cab}\n\nO valor registrado não corresponde ao que devo. "
                f"{('Observação: ' + r.observacao) if r.observacao else 'Solicito o demonstrativo detalhado do cálculo.'}\n\n"
                f"Pelo art. 43, §3, do Código de Defesa do Consumidor, encontrada inexatidão nos dados, "
                f"o consumidor pode exigir a correção imediata, que deve ser feita em 5 dias úteis.\n\n"
                + _fecho("Peço a correção do valor ou a exclusão do registro até que o valor correto seja apurado."))

    if tipo == "pedido_baixa_prazo":
        lim = data_br(a.limite_5_anos) if a.limite_5_anos else "[DATA]"
        return (f"{cab}\n\nO vencimento informado é de {data_br(r.venc()) if r.venc() else '[DATA]'}. "
                f"O prazo máximo de 5 anos para manutenção de informação negativa terminou em {lim}.\n\n"
                f"Pelo art. 43, §1, do Código de Defesa do Consumidor, cadastros de consumidores não podem "
                f"conter informações negativas referentes a período superior a 5 anos. A Súmula 323 do STJ "
                f"confirma que esse limite vale independentemente da prescrição da cobrança. "
                f"A manutenção do registro além do prazo é irregular e gera dano moral.\n\n"
                + _fecho("Peço a exclusão imediata do registro por decurso do prazo legal."))

    if tipo == "contestacao_sem_notificacao":
        return (f"{cab}\n\nNão recebi qualquer comunicação por escrito antes da inclusão do meu nome no cadastro.\n\n"
                f"O art. 43, §2, do Código de Defesa do Consumidor exige que a abertura de cadastro seja "
                f"comunicada por escrito ao consumidor. A Súmula 359 do STJ atribui essa obrigação ao órgão "
                f"mantenedor do cadastro. Sem a comunicação prévia, a inscrição é irregular.\n\n"
                + _fecho("Peço o cancelamento da inscrição por ausência de notificação prévia, "
                         "e a comprovação do envio da comunicação, caso a empresa alegue tê-la feito."))

    if tipo == "pedido_documento_origem":
        return (f"{cab}\n\nPara avaliar esse registro, solicito, com base no art. 43, caput, do Código de "
                f"Defesa do Consumidor, que garante o acesso às informações existentes em cadastros sobre mim "
                f"e às respectivas fontes:\n\n"
                f"1. O documento ou contrato que deu origem à dívida.\n"
                f"2. A data de vencimento original da obrigação.\n"
                f"3. O comprovante da comunicação prévia enviada antes da inscrição.\n\n"
                + _fecho("Peço o envio dessas informações no prazo de 5 dias úteis."))

    if tipo == "consumidor_gov":
        # Formato do canal: primeira pessoa, objetivo, até 15 linhas, pedido claro no fim.
        principal = a.argumento_principal
        base = principal.base if principal else "CDC art. 43"
        motivo = {
            "ja_paguei": "a dívida já foi paga" + (", e tenho o comprovante" if r.comprovante else ""),
            "nao_reconheco": "não reconheço essa dívida e a empresa não apresentou o contrato",
            "valor_errado": "o valor registrado está errado",
            "minha_no_prazo": "o registro ultrapassou o prazo legal de 5 anos",
            "nao_sei": "o registro ultrapassou o prazo legal de 5 anos",
        }[r.situacao if not (a.pilha == "vencido") else "nao_sei"]
        return (f"Meu nome consta negativado no {r.biro} por registro de {r.credor}, valor {r.valor_fmt()}"
                + (f", vencimento {data_br(r.venc())}" if r.venc() else "") + ".\n"
                f"O problema: {motivo}.\n"
                f"Base legal: {base}.\n"
                f"Já tentei resolver diretamente e não obtive a baixa.\n"
                f"Pedido: exclusão do registro negativo e confirmação por escrito da baixa nos birôs.\n"
                f"Anexo os documentos que comprovam o relato.")

    if tipo == "pedido_carta_anuencia":
        pago = f" em {data_br(_data(r.data_pagamento))}" if r.data_pagamento else ""
        motivo = (f"O título foi pago{pago}." if r.situacao in ("ja_paguei", "minha_no_prazo")
                  else "O protesto é indevido, pelas razões que exponho em separado.")
        return (f"{cab}\n\n{motivo}\n\n"
                f"Pelo art. 26 da Lei 9.492/1997, o cancelamento do protesto é feito no cartório mediante a "
                f"carta de anuência do credor. Solicito a emissão dessa carta, com firma reconhecida ou "
                f"assinatura eletrônica válida, identificando o título, o valor e o cartório do protesto.\n\n"
                + _fecho("Peço o envio da carta de anuência no prazo de 5 dias úteis."))

    if tipo == "contestacao_protesto":
        return (f"{cab}\n\n"
                + ("Não reconheço esse título. Não contratei com a empresa nem autorizei a operação que o originou. "
                   if r.situacao == "nao_reconheco" else
                   f"O valor protestado não corresponde ao devido. {r.observacao}".strip() + " ")
                + "\n\nSolicito a apresentação do título ou do documento que deu origem ao protesto, com a data de "
                  "vencimento (CDC art. 6º, VIII). Sem essa comprovação, o protesto é indevido e cabe ao credor "
                  "fornecer, sem custo para mim, a carta de anuência para o cancelamento (Lei 9.492/1997, art. 26).\n\n"
                + _fecho("Peço a carta de anuência para o cancelamento do protesto ou a apresentação do título."))

    if tipo == "roteiro_negociacao":
        return roteiro_negociacao(r)

    raise ValueError(f"documento desconhecido: {tipo}")


def cenarios_negociacao(valor: float, desconto_vista: float = 0.5, parcelas_curto: int = 6,
                        parcelas_longo: int = 24, juros_mes: float = 0.02) -> list[dict]:
    """Três cenários com o total pago em cada um. Números para decidir, não promessa."""
    def total_parcelado(n: int) -> tuple[float, float]:
        if juros_mes <= 0:
            return valor, valor / n
        pmt = valor * juros_mes / (1 - (1 + juros_mes) ** -n)
        return pmt * n, pmt

    vista = valor * (1 - desconto_vista)
    t_curto, p_curto = total_parcelado(parcelas_curto)
    t_longo, p_longo = total_parcelado(parcelas_longo)
    return [
        {"cenario": "À vista com desconto", "parcelas": 1, "parcela": vista, "total": vista,
         "quando": "Proponha primeiro. Credor de dívida antiga costuma aceitar entre 50% e 90% de desconto."},
        {"cenario": "Parcelamento curto", "parcelas": parcelas_curto, "parcela": p_curto, "total": t_curto,
         "quando": "Se não der à vista. Menos juros, registro sai com o acordo formalizado."},
        {"cenario": "Parcelamento longo", "parcelas": parcelas_longo, "parcela": p_longo, "total": t_longo,
         "quando": "Só se a parcela curta não couber. Paga muito mais no total."},
    ]


def roteiro_negociacao(r: Registro) -> str:
    cen = cenarios_negociacao(r.valor)
    linhas = [f"Roteiro de negociação: {r.credor}, {r.valor_fmt()}"
              + (f", vencimento {data_br(r.venc())}" if r.venc() else ""), ""]
    for c in cen:
        linhas.append(f"{c['cenario']}: {c['parcelas']}x de {moeda(c['parcela'])}, total {moeda(c['total'])}. {c['quando']}")
    linhas += [
        "",
        "Como conduzir:",
        "1. Peça a proposta por escrito antes de pagar qualquer valor.",
        "2. Exija que o acordo diga que o registro será baixado após o pagamento (ou da primeira parcela).",
        "3. Guarde o comprovante. Pela Súmula 548 do STJ, o credor tem 5 dias úteis para pedir a baixa.",
        "4. Seu limite antes de recusar: o total do cenário curto. Acima disso, espere o próximo feirão.",
        "5. Não pague por boleto enviado por mensagem: gere o boleto no site ou app oficial do credor ou do birô.",
    ]
    return "\n".join(linhas)


def plano_12_meses(registros_baixados: int = 0) -> list[dict]:
    """Reconstrução de histórico. O que move o score de verdade, sem prometer número."""
    return [
        {"mes": "1", "acao": "Confirme nos três birôs que os registros saíram e guarde os prints.",
         "porque": "A baixa em um birô não garante a baixa nos outros."},
        {"mes": "1", "acao": "Consulte o Cadastro Positivo (Lei 12.414/2011) no Serasa, SPC ou Boa Vista e mantenha-o ativo.",
         "porque": "É o que faz pagamento em dia contar a favor, não só atraso contar contra."},
        {"mes": "1 a 3", "acao": "Coloque as contas fixas (luz, água, telefone, internet) no seu CPF e pague no vencimento.",
         "porque": "Histórico de pagamento em dia é o fator de maior peso."},
        {"mes": "2 a 6", "acao": "Use no máximo 30% do limite do cartão, mesmo pagando a fatura integral.",
         "porque": "Limite quase todo usado pesa contra, ainda que não haja atraso."},
        {"mes": "2 a 12", "acao": "Não feche a conta bancária nem o cartão mais antigos.",
         "porque": "Tempo de relacionamento conta. Recomeçar do zero derruba o score."},
        {"mes": "3 a 12", "acao": "Evite pedir vários créditos em sequência.",
         "porque": "Muitas consultas em pouco tempo sinalizam risco."},
        {"mes": "6 e 12", "acao": "Refaça a consulta nos três birôs e revise este plano.",
         "porque": "Registro novo pode aparecer. O acompanhamento é parte do processo."},
    ]


SINAIS_DE_GOLPE = [
    ("Promete número de score", "\"Score 750+ garantido\" não existe. Ninguém controla o modelo dos birôs."),
    ("Promete apagar dívida verdadeira", "Não é possível e não é legal. Dívida verdadeira se negocia."),
    ("Cobra antes de entregar", "Os canais oficiais são gratuitos. consumidor.gov.br não cobra nada."),
    ("Pede senha do banco ou do gov.br", "Nenhum serviço legítimo precisa disso."),
    ("Manda boleto por WhatsApp", "Gere o boleto só no site ou app oficial do credor ou do birô."),
]

CHECKLIST = [
    "Puxei o relatório nos três birôs (Serasa, SPC e Boa Vista), não em um só",
    "Consultei protesto em cartório na CENPROT (pesquisaprotesto.com.br)",
    "Separei os registros em errado, vencido e verdadeiro",
    "Tenho a data de vencimento de cada dívida, não só a data do registro",
    "O texto cita só legislação brasileira, sem lei inventada",
    "Guardei protocolo, data e resposta de cada pedido",
]


# ── Passagem para o Holmes jurídico (Watson) ───────────────────────────────

WATSON_URL = os.environ.get("HOLMES_WATSON_URL", "https://watson.trustcorp.com.br/")
_LIMITE_WATSON = 18000   # o Watson aceita até 20.000 caracteres pelo fragmento


def texto_para_watson(caso: Caso, r: Registro, hoje: date | None = None) -> str:
    """
    Resumo do caso já organizado para o agente jurídico: fatos, prazos,
    argumentos com base legal, protocolos e o pedido. É o que ele precisaria
    perguntar, entregue de uma vez.
    """
    hoje = hoje or date.today()
    a = analisar(r, hoje)
    linhas = [
        "Caso enviado pelo Limpa Nome do Mr.Holmes. Sou o consumidor.",
        "",
        "FATOS",
        f"- Credor: {r.credor}" + (f" (CNPJ {r.cnpj_credor})" if r.cnpj_credor else ""),
        f"- Valor registrado: {r.valor_fmt()}",
        f"- Birô: {r.biro}",
        f"- Vencimento informado: {data_br(r.venc()) or 'não sei'}",
        f"- Inclusão no birô: {data_br(_data(r.inclusao)) or 'não sei'}",
        f"- Situação: {SITUACOES.get(r.situacao, r.situacao)}",
        f"- Aviso prévio por escrito antes da inclusão: {NOTIFICADO.get(r.notificado, r.notificado)}",
    ]
    if r.situacao == "ja_paguei":
        linhas.append(f"- Pagamento: {data_br(_data(r.data_pagamento)) or 'data não informada'}, "
                      f"comprovante: {'sim' if r.comprovante else 'não'}")
    if r.observacao:
        linhas.append(f"- Observação: {r.observacao}")
    if a.limite_5_anos:
        estado = "já venceu" if (a.dias_para_vencer_prazo or 0) < 0 else "ainda não venceu"
        linhas.append(f"- Teto de 5 anos (dia seguinte ao vencimento): {data_br(a.limite_5_anos)}, {estado}")

    linhas += ["", f"CLASSIFICAÇÃO: {a.pilha_label}"]
    if a.argumentos:
        linhas.append("ARGUMENTOS JÁ IDENTIFICADOS")
        linhas += [f"- {x.titulo} ({x.base})" for x in a.argumentos]

    prots = [p for p in caso.protocolos if p.registro_id == r.id]
    if prots:
        linhas += ["", "O QUE JÁ FOI TENTADO"]
        for p in sorted(prots, key=lambda x: x.data):
            est = situacao_protocolo(p, hoje)
            linha = f"- {CANAIS.get(p.canal, p.canal)} em {data_br(_data(p.data))}"
            if p.numero:
                linha += f", protocolo {p.numero}"
            linha += f": {est['status']}"
            if p.resposta:
                linha += f". Resposta da empresa: {p.resposta[:600]}"
            linhas.append(linha)

    outros = [x for x in caso.registros if x.id != r.id]
    if outros:
        legitimas = [x for x in outros if analisar(x, hoje).pilha == "verdadeira"]
        linhas += ["", f"OUTRAS NEGATIVAÇÕES NO MEU CPF: {len(outros)}"
                   + (f", das quais {len(legitimas)} são dívidas verdadeiras e no prazo" if legitimas else "")]
        linhas += [f"- {x.credor}, {x.valor_fmt()}, {x.biro}, {analisar(x, hoje).pilha_label}" for x in outros[:10]]

    linhas += [
        "",
        "O QUE PRECISO",
        "1. Red team antes de tudo: Súmula 385 (outras negativações), prova da notificação prévia, "
        "data de vencimento, e se a dívida é de fato indevida. Diga com franqueza se vale entrar com ação.",
        "2. Se valer: petição inicial para o Juizado Especial Cível com exclusão do registro, tutela de "
        "urgência para suspender a negativação e dano moral com valor fundamentado.",
        "3. Lista de provas que devo anexar.",
    ]
    return "\n".join(linhas)[:_LIMITE_WATSON]


def link_watson(caso: Caso, r: Registro, hoje: date | None = None) -> str:
    """URL do Watson com o caso no fragmento (#caso=...). O fragmento não vai ao
    servidor: o navegador preenche a caixa do chat e o apaga da barra."""
    import base64

    dados = {"v": 1, "agente": "consumidor", "titulo": f"Limpa Nome: {r.credor}"[:120],
             "texto": texto_para_watson(caso, r, hoje)}
    b64 = base64.urlsafe_b64encode(json.dumps(dados, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return WATSON_URL.split("#")[0] + "#caso=" + b64.rstrip("=")


# ── Importação de texto colado ─────────────────────────────────────────────

_RE_VALOR = re.compile(r"R\$\s?([\d.]+,\d{2})")
_RE_DATA = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_RE_BIRO = re.compile(r"\b(serasa|spc|boa\s*vista|quod|protesto|cart[oó]rio|tabelionato)\b", re.I)
_RE_ROTULO = re.compile(
    r"^(contrato|valor|vencimento|venc\.?|data|inclus[aã]o|situa[cç][aã]o|origem|natureza|"
    r"tipo|registrado|registro|d[ií]vida|d[ée]bito|cpf|cnpj|total|saldo)\b", re.I)
_BIRO_NOME = {"serasa": "Serasa", "spc": "SPC Brasil", "boavista": "Boa Vista", "quod": "Quod",
              "protesto": PROTESTO, "cartório": PROTESTO, "cartorio": PROTESTO, "tabelionato": PROTESTO}


def _iso(m: tuple[str, str, str]) -> str:
    return f"{m[2]}-{m[1]}-{m[0]}"


def _linha_de_nome(linha: str) -> bool:
    limpa = linha.strip(" :-•*|\t")
    if len(re.findall(r"[A-Za-zÀ-ú]", limpa)) < 3:
        return False
    if _RE_VALOR.search(limpa) or _RE_DATA.search(limpa) or _RE_ROTULO.match(limpa):
        return False
    if _RE_BIRO.fullmatch(limpa.strip()):
        return False
    return True


def _datas_do_bloco(linhas: list[str]) -> tuple[str | None, str | None]:
    """(vencimento, inclusão). Prefere as datas rotuladas; senão, ordem de aparição."""
    venc = incl = None
    soltas: list[str] = []
    for l in linhas:
        for m in _RE_DATA.findall(l):
            iso = _iso(m)
            if re.search(r"venc", l, re.I) and not venc:
                venc = iso
            elif re.search(r"inclus|registr|inser", l, re.I) and not incl:
                incl = iso
            else:
                soltas.append(iso)
    if not venc and soltas:
        venc = soltas.pop(0)
    if not incl and soltas:
        incl = soltas.pop(0)
    return venc, incl


def importar_texto(texto: str) -> list[Registro]:
    """
    Extrai registros de um texto colado do app do birô ou de um extrato.
    Cada valor em reais vira um registro; o credor é a linha de nome mais
    próxima acima dele (ou o texto antes do valor na mesma linha). O usuário
    revisa tudo na tabela depois, então errar aqui custa pouco.
    """
    regs: list[Registro] = []
    biro_global = _RE_BIRO.search(texto or "")
    for bloco in re.split(r"\n\s*\n", texto or ""):
        linhas = [l for l in bloco.splitlines() if l.strip()]
        idx_valores = [i for i, l in enumerate(linhas) if _RE_VALOR.search(l)]
        if not idx_valores:
            continue
        b = _RE_BIRO.search(bloco) or biro_global
        biro = _BIRO_NOME.get(re.sub(r"\s", "", b.group(1).lower()), "Serasa") if b else "Serasa"
        for n, i in enumerate(idx_valores):
            linha = linhas[i]
            valor = float(_RE_VALOR.search(linha).group(1).replace(".", "").replace(",", "."))
            antes = _RE_VALOR.split(linha)[0]
            credor = ""
            if _linha_de_nome(antes):
                credor = antes
            else:
                inicio = idx_valores[n - 1] + 1 if n else 0
                for l in reversed(linhas[inicio:i]):
                    if _linha_de_nome(l):
                        credor = l
                        break
            if not credor:
                continue
            credor = re.sub(r"(?i)^(credor|empresa|nome|origem)[:\s]+", "", credor.strip(" :-•*|\t"))[:80]
            fim = idx_valores[n + 1] if n + 1 < len(idx_valores) else len(linhas)
            venc, incl = _datas_do_bloco(linhas[i:fim] if len(idx_valores) > 1 else linhas)
            regs.append(Registro(credor=credor, valor=valor, vencimento=venc, inclusao=incl, biro=biro))
    return regs


# ── IA como redatora, com trava ────────────────────────────────────────────

_SISTEMA_IA = """Você é um redator especializado em direito do consumidor brasileiro.
Regras obrigatórias, sem exceção:
1. Cite apenas legislação brasileira. Use só estas bases: Código de Defesa do Consumidor (art. 6º VIII, art. 43 e parágrafos), Súmulas 323, 359, 385, 404 e 548 do STJ, Lei 12.414/2011 e, para protesto em cartório, Lei 9.492/1997 art. 26 e Tema 725 do STJ. Não invente número de lei, artigo, súmula ou julgado.
2. Nunca mencione leis estrangeiras (Fair Credit Reporting Act ou similares).
3. Nunca prometa nem mencione aumento de score, nem prazo para "limpar o nome".
4. Se faltar um dado para sustentar o pedido, diga qual falta em vez de completar sozinho.
5. Linguagem simples, primeira pessoa, sem ameaça, sem adjetivos. No máximo 15 linhas. Termine com um pedido objetivo.
6. Não altere valores, datas, nomes de empresas nem a base legal do texto original."""


def ia_disponivel() -> bool:
    try:
        from . import llm

        return llm.available()
    except Exception:
        return False


def _chat(system: str, user: str) -> str | None:
    try:
        from Core.Support.Robin.llm_bridge import chat, list_models

        modelos = list_models() or []
        if not modelos:
            return None
        saida = chat(modelos[0]["id"], system, user)
        return saida.strip() or None
    except Exception:
        return None


def refinar_com_ia(texto: str, instrucao: str = "") -> str | None:
    """Reescreve o documento mantendo fatos e base legal. None se a IA não responder."""
    pedido = ("Reescreva o texto abaixo deixando-o mais claro e direto, obedecendo às regras. "
              + (f"Instrução extra do usuário: {instrucao}. " if instrucao else "")
              + "Devolva só o texto final.\n\n" + texto)
    return _chat(_SISTEMA_IA, pedido)


_SISTEMA_EXTRACAO = """Você extrai registros de negativação de um texto colado de Serasa, SPC, Boa Vista, Quod ou de uma consulta de protesto em cartório (CENPROT).
Devolva SOMENTE um JSON, uma lista de objetos com as chaves:
credor (string), valor (número em reais, ponto decimal), vencimento (AAAA-MM-DD ou null),
inclusao (AAAA-MM-DD ou null), biro (Serasa | SPC Brasil | Boa Vista | Quod | Cartório de protesto | Outro), cnpj_credor (string ou "").
Em consulta de protesto, o credor é o "apresentante" ou "cedente" e a data de vencimento é a do título.
Não invente dados: campo desconhecido fica null ou "". Datas no texto estão em DD/MM/AAAA."""


def extrair_com_ia(texto: str) -> list[Registro] | None:
    saida = _chat(_SISTEMA_EXTRACAO, texto)
    if not saida:
        return None
    m = re.search(r"\[.*\]", saida, re.S)
    if not m:
        return None
    try:
        itens = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    regs = []
    for it in itens if isinstance(itens, list) else []:
        if not isinstance(it, dict) or not it.get("credor"):
            continue
        try:
            valor = float(it.get("valor") or 0)
        except (TypeError, ValueError):
            valor = 0.0
        regs.append(Registro(
            credor=str(it["credor"])[:80], valor=valor,
            vencimento=_data_iso(it.get("vencimento")), inclusao=_data_iso(it.get("inclusao")),
            biro=it.get("biro") if it.get("biro") in BIROS else "Serasa",
            cnpj_credor=str(it.get("cnpj_credor") or ""),
        ))
    return regs


def _data_iso(v) -> str | None:
    d = _data(v) if v else None
    return d.isoformat() if d else None


# ── Persistência ───────────────────────────────────────────────────────────

# Mesmo diretório do histórico e do monitor; o Supabase é a cópia durável.
CASOS_DIR = Path(os.environ.get("HOLMES_HISTORY_DIR", ".holmes_history")) / "limpanome"


def salvar(caso: Caso) -> str:
    caso.atualizado = datetime.now().isoformat(timespec="seconds")
    CASOS_DIR.mkdir(parents=True, exist_ok=True)
    (CASOS_DIR / f"{caso.id}.json").write_text(
        json.dumps(asdict(caso), ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        from . import store

        if store.enabled():
            store.upsert("holmes_limpanome", {
                "id": caso.id, "nome": caso.nome, "cpf_mascarado": caso.cpf_mascarado,
                "dados": asdict(caso), "atualizado": caso.atualizado,
            }, "id")
    except Exception:
        pass
    return caso.id


def carregar(caso_id: str) -> Caso | None:
    arq = CASOS_DIR / f"{caso_id}.json"
    dados = None
    if arq.exists():
        dados = json.loads(arq.read_text(encoding="utf-8"))
    else:
        try:
            from . import store

            if store.enabled():
                linhas = store.select("holmes_limpanome", {"id": f"eq.{caso_id}", "select": "dados"})
                if linhas:
                    dados = linhas[0]["dados"]
        except Exception:
            dados = None
    return _de_dict(dados) if dados else None


def listar_casos() -> list[dict]:
    out = []
    if CASOS_DIR.exists():
        for arq in sorted(CASOS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                d = json.loads(arq.read_text(encoding="utf-8"))
                out.append({"id": d["id"], "nome": d.get("nome", ""), "cpf": d.get("cpf_mascarado", ""),
                            "registros": len(d.get("registros", [])), "atualizado": d.get("atualizado", "")})
            except Exception:
                continue
    return out


def _de_dict(d: dict) -> Caso:
    regs = [Registro(**{k: v for k, v in r.items() if k in Registro.__dataclass_fields__})
            for r in d.get("registros", [])]
    prots = [Protocolo(**{k: v for k, v in p.items() if k in Protocolo.__dataclass_fields__})
             for p in d.get("protocolos", [])]
    return Caso(nome=d.get("nome", ""), cpf_mascarado=d.get("cpf_mascarado", ""),
                registros=regs, protocolos=prots, criado=d.get("criado", ""),
                atualizado=d.get("atualizado", ""), id=d.get("id") or uuid.uuid4().hex[:10])


# ── Utilidades ─────────────────────────────────────────────────────────────

def _data(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None


def somar_anos(d: date, anos: int) -> date:
    """Mesmo dia e mês, anos depois. 29/02 vira 28/02 em ano não bissexto."""
    try:
        return d.replace(year=d.year + anos)
    except ValueError:
        return d.replace(year=d.year + anos, day=28)


def data_br(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def moeda(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"
