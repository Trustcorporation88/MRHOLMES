# Auditoria do motor de investigação (setembro de 2026)

Foco: por que CPF e CNPJ trazem pouco, o que fazer com a Bright Data e quais
serviços só ocupavam espaço no dossiê.

## 1. Diagnóstico

### CPF: praticamente nada rodava de verdade

Antes desta revisão, um CPF acionava só três coisas:

| Fonte | O que fazia | Problema |
|---|---|---|
| Portal da Transparência | PEP e CEIS pelo CPF | Exige chave. Não pedia o **nome do titular**, que o Portal entrega de graça |
| Busca de superfície | `"123.456.789-00"` e `"12345678900"` | Documento público quase nunca traz o CPF inteiro. A LGPD fez os diários publicarem `***.456.789-**`, e ninguém procurava essa forma |
| Links | Portal, Receita (captcha) e Escavador | A Receita exige data de nascimento e captcha. Escavador não indexa por CPF |

Resultado: sem chave do Portal e sem Serper, o dossiê de CPF saía com três
links e nenhum fato. Com chave, saía só "não é PEP, não está no CEIS".

### CNPJ: a base era boa, a volta era fraca

A Receita pela BrasilAPI já entregava razão social, endereço, contatos e sócios.
O que faltava:

* Só uma reserva (ReceitaWS, limitada a 3 consultas por minuto). Quando a
  BrasilAPI oscilava, o CNPJ inteiro sumia.
* Portal da Transparência consultava só o CEIS. Contratos federais, CNEP,
  CEPIM e acordos de leniência ficavam de fora.
* Querido Diário procurava só a forma com pontuação.
* Dorks mandavam para o Consulta Sócio, que saiu do ar.

### Falha calada

O Portal e o Querido Diário engoliam erro de rede e devolviam lista vazia. No
dossiê isso aparecia como "nada encontrado", quando na verdade a fonte não
tinha respondido. Não dava para saber se o alvo estava limpo ou se a fonte caiu.

### Bright Data subaproveitada

A chave só era usada no WhatsMyName, como reserva para site que bloqueia
(e só com `HOLMES_UNLOCKER=1`). A busca de superfície, que é o maior gargalo
do servidor (Google, DDG e Mojeek bloqueiam IP de datacenter), não usava a
Bright Data em lugar nenhum.

### Ruído no dossiê

27 entradas do catálogo eram links para a **página inicial** do serviço, sem o
alvo embutido (GetContact, CallApp, Eyecon, SpyDialer, Epieos, LeakCheck,
DNSDumpster, Namechk e outras), ou ferramentas que nem chegavam a ser
registradas (TinEye, CyberChef, WiGLE...). No dossiê, cada uma virava um
"achado" de confiança mínima que não dizia nada sobre o alvo. Nos links
brasileiros acontecia o mesmo com Sintegra, Cartão CNPJ, CADE, INPI, TSE, CVM
e Diário Oficial da União, todos formulário com captcha ou SPA.

## 2. O que foi feito nesta branch

| Mudança | Onde | Efeito |
|---|---|---|
| **Bright Data SERP como motor de busca** | `holmes/net.py`, `holmes/serp.py` | Com `BRIGHTDATA_API_KEY` e `HOLMES_BRD_SERP_ZONE`, os 10 a 15 dorks por alvo passam a rodar no Google de verdade. Entra depois do Serper e antes do Brave. Cache de 24h e teto por processo |
| **CPF → nome completo** | `holmes/br_auto.py` | Recurso `pessoa-fisica` do Portal: nome, NIS e todos os vínculos federais (servidor, Bolsa Família, BPC, contratos, cartão corporativo, sanções). O nome vira alvo novo e o pivô roda em cima dele |
| CPF: servidor, CNEP e CEAF | `holmes/br_auto.py` | Além de PEP e CEIS |
| **CPF mascarado** | `holmes/entity.py`, `holmes/serp.py`, `holmes/br_auto.py` | Dorks e Querido Diário procuram também o miolo `456.789`. Achado só pelo miolo sai como "possível", para conferir o nome no trecho |
| CNPJ: vínculos, CNEP, CEPIM, leniência e contratos | `holmes/br_auto.py` | Contratos com total em reais e órgãos contratantes |
| CNPJ: Minha Receita como reserva | `holmes/br.py` | Mesma base da BrasilAPI, sem o limite da ReceitaWS |
| Dorks de CNPJ | `holmes/serp.py` | Licitação, contrato, reclamação e documentos. Consulta Sócio trocado por CNPJ.biz |
| Falha visível | `holmes/br_auto.py` | Se todas as consultas do Portal ou do Querido Diário falham, a fonte aparece em "fontes que não responderam" |
| Limpeza | `holmes/connectors/catalog.py`, `holmes/br.py` | 27 entradas do catálogo e 13 links brasileiros removidos |

### Serviços excluídos

**Catálogo geral (27):** GetContact, CallApp, Eyecon, SpyDialer, WhoseNumber,
Phonebook.cz, Epieos, HIBP (link; a consulta automática continua), Hudson Rock
(link; a consulta automática continua), LeakCheck, OSINT Leak, PSBDMP (fora do
ar), CrackStation, DNSDumpster, Namechk, Mind Search, TinEye, Google Lens,
Jimpl, FotoForensics, Aperi'Solve, StegOnline, InVID, CyberChef, WiGLE,
Bellingcat OSM e OSINT Framework.

**Links brasileiros (13):** Consulta Sócio (nome e CNPJ, site encerrado),
TSE, CVM, INPI (nome e CNPJ), CADE (nome e CNPJ), Diário Oficial da União,
Cartão CNPJ, Sintegra SP, Sintegra MG, Cadastro ICMS PR e Situação cadastral
do CPF.

**Entraram no lugar:** CNPJ.biz (ficha com sócios), Google pelo CPF mascarado
e Querido Diário para CPF.

## 3. Como ligar em produção

No Railway, em **Variables**:

```
BRIGHTDATA_API_KEY=...            # a chave que você já tem
HOLMES_BRD_SERP_ZONE=serp_api1    # nome exato da zona SERP no painel da Bright Data
HOLMES_BRD_SERP_BUDGET=500        # teto de buscas por processo (opcional)
PORTAL_TRANSPARENCIA_KEY=...      # grátis, por e-mail, em portaldatransparencia.gov.br/api-de-dados
```

A zona SERP precisa existir no painel (Proxies & Scraping → Add → SERP API).
Sem `HOLMES_BRD_SERP_ZONE` nada é cobrado: a chave sozinha não liga a busca.

**A chave do Portal é a mudança de maior impacto para CPF.** Sem ela, CPF
continua sem nome do titular. É gratuita.

## 4. Segunda etapa (implementada)

As quatro propostas de maior retorno foram feitas.

### 4.1 Páginas lidas pelo Web Unlocker

Antes de escrever o extrator, testei ao vivo, pela Bright Data, cada site que
era só link:

| Site | Resultado real | Decisão |
|---|---|---|
| JusBrasil | Página entregue, com dados estruturados | **Extrator implementado** (`holmes/jusbrasil.py`) |
| Escavador | Bright Data recusa sem verificação KYC da conta | Fica como link. Se a conta passar pelo KYC, vale implementar |
| CNPJ.biz | "Acesso Bloqueado": o site barra qualquer proxy | Fica como link (funciona no navegador de quem clica) |
| Econodata | "Você atingiu o limite de consultas" | Fica como link |

O que o JusBrasil entrega agora, direto no dossiê:

* **nome**: quantas pessoas têm aquele nome exato e a faixa etária; da página
  da pessoa, **as empresas em que ela é sócia ou administradora, com CNPJ e
  cargo**, os estados onde aparece e os dígitos do CPF que o site exibe;
  menções em diários oficiais de tribunais;
* **CNPJ**: empresas relacionadas (consórcios, sócias pessoa jurídica) e o
  contato declarado.

Os extratores foram escritos e testados sobre páginas reais capturadas nesta
sessão (`tests/fixtures/`). Quando o Unlocker devolve bloqueio com HTTP 200
(KYC, proxy barrado, limite), o motor reconhece e mostra o motivo em "fontes
que não responderam", em vez de tratar como resultado vazio.

Ligar: `HOLMES_UNLOCKER=1` (usa a mesma `BRIGHTDATA_API_KEY`; zona em
`HOLMES_UNLOCKER_ZONE`, padrão `cli_unlocker`).

### 4.2 Índice local dos sócios da Receita

`holmes/socios_rfb.py` baixa os arquivos de sócios dos dados abertos do CNPJ
(cerca de 26 milhões de linhas) e monta um SQLite local. Responde, sem rede:

* **nome** → empresas em que alguém com esse nome é sócio, separando
  homônimos pelo CPF mascarado;
* **CPF** → empresas em que o CPF aparece como sócio. Com a chave do Portal,
  o nome do titular confirma quais são dele; sem ela, lista os candidatos;
* **CNPJ** → as outras empresas dos sócios desta (mesmo nome e mesmo CPF
  mascarado).

```
python -m holmes.socios_rfb --update           # ou o botão em Investigar → Avançado
HOLMES_SOCIOS_DIR=/data                          # Volume do Railway (3 a 4 GB)
```

O endereço dos arquivos da Receita muda de tempos em tempos. O módulo
descobre o mês mais recente sozinho; se falhar, ajuste `HOLMES_RFB_CNPJ_BASE`
ou baixe os `Socios*.zip` e use `--from-dir`.

### 4.3 Coletores prontos de LinkedIn e Instagram

`holmes/social_brd.py`, pela Web Scraper API da Bright Data:

* **LinkedIn**: a partir do link do perfil, ou do nome (uma busca acha a URL
  e só coleta se o título bater com o nome; se o perfil coletado for de outra
  pessoa, é descartado). Traz cargo, empresa atual, experiência, formação,
  cidade e foto. Página de empresa traz setor, porte, site e funcionários;
* **Instagram**: a partir do @username ou do link. Traz bio, seguidores,
  categoria, link da bio, foto e, em conta comercial, e-mail e telefone.

Ligar: `HOLMES_BRD_DATASETS=1`, com teto em `HOLMES_BRD_DATASETS_BUDGET`
(padrão 40 por processo) e cache de 7 dias. Os IDs dos coletores podem ser
trocados por variável (`HOLMES_BRD_DS_LINKEDIN`, `HOLMES_BRD_DS_INSTAGRAM`).

### 4.4 Medição do rendimento de cada fonte

`holmes/source_yield.py` registra, no fim de toda investigação, o que cada
fonte trouxe: fatos (link não conta), **fatos exclusivos** (que nenhuma outra
fonte trouxe), falhas e tempo. O relatório dá o veredito:

| Veredito | Regra |
|---|---|
| `cortar` | rodou 15 vezes ou mais e nunca trouxe um fato |
| `quebrada` | falhou em 80% ou mais das vezes |
| `manter` | trouxe fato |
| `poucos dados` | rodou menos de 15 vezes |

```
python -m holmes.source_yield --backfill    # mede também o histórico já salvo
```

O mesmo relatório aparece em Investigar → Avançado, com o botão "Medir
histórico salvo". A caixa "Incluir fontes manuais" saiu da interface, porque
não sobrou nenhuma fonte manual.

## 5. Próximas etapas

1. Rodar o `--backfill` em produção e cortar o que sair como `cortar` ou
   `quebrada`.
2. Pedir o KYC na Bright Data e ligar o Escavador pelo mesmo caminho do
   JusBrasil.
3. Tribunais estaduais (e-SAJ) por CPF e CNPJ pelo Unlocker.

## 6. Limites desta auditoria

* O container onde o código roda nesta sessão não tem acesso à internet. As
  páginas do JusBrasil, Escavador, CNPJ.biz e Econodata foram testadas ao vivo
  pela Bright Data, mas o Portal, o Querido Diário, os coletores de LinkedIn e
  Instagram e o download da Receita não foram. Os formatos de resposta seguem a
  documentação pública do Portal, da Bright Data e do Querido Diário, e o
  código tolera campo ausente. Vale rodar um CPF e um CNPJ conhecidos logo
  depois do deploy.
* Não encontrei o serviço do mrholmes.trustcorp.com.br entre os projetos do
  Railway acessíveis a esta sessão, então não conferi quais chaves estão
  configuradas em produção nem os logs de erro reais.
