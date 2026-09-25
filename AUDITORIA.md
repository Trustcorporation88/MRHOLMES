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

## 4. Propostas para as próximas etapas

Em ordem de retorno sobre o esforço:

1. **Extrair dado das páginas que hoje são só link, pelo Web Unlocker.**
   Escavador, JusBrasil, CNPJ.biz e Econodata abrem já pesquisados, mas o
   motor não lê o conteúdo. Com o Unlocker (mesma chave), dá para buscar a
   página, extrair partes, processos e sócios, e transformar link em fato.
   Custo estimado: 3 a 6 requisições por alvo.
2. **Empresas ligadas ao sócio.** Hoje o CNPJ entrega os sócios, mas não as
   outras empresas deles. O caminho gratuito é indexar localmente os dados
   abertos da Receita (arquivo de sócios, cerca de 25 milhões de linhas, mesmo
   modelo do índice do OpenSanctions que já existe). Isso também resolve
   "CPF de sócio → empresas", com o CPF mascarado que a Receita publica.
3. **Datasets da Bright Data para redes sociais.** Os coletores prontos de
   LinkedIn, Instagram e Facebook devolvem perfil estruturado a partir do
   nome ou do link. Resolve o ponto mais fraco depois de CPF: rede social
   que exige login.
4. **Tribunais por CPF e CNPJ.** O e-SAJ (TJSP, TJSC, TJMS, TJAL, TJAM, TJCE)
   aceita busca por documento da parte na URL, como já é feito para nome.
   Passar pelo Unlocker contorna o captcha eventual.
5. **Medir antes de cortar mais.** O próximo passo da limpeza é registrar,
   por conector, quantos fatos cada fonte trouxe nas investigações reais
   (o histórico em `holmes/store.py` já guarda os resultados). Fonte que
   passar 30 dias sem trazer nada sai do catálogo com base em número, não em
   impressão.
6. **Opção "Incluir fontes manuais" na interface.** Depois da limpeza não
   sobrou fonte manual, então a caixa pode sair de `holmes_ui.py`.

## 5. Limites desta auditoria

* O container onde a revisão foi feita não tem acesso à internet, então as
  fontes não foram testadas ao vivo. Os formatos de resposta seguem a
  documentação pública do Portal, da Bright Data e do Querido Diário, e o
  código tolera campo ausente. Vale rodar um CPF e um CNPJ conhecidos logo
  depois do deploy.
* Não encontrei o serviço do mrholmes.trustcorp.com.br entre os projetos do
  Railway acessíveis a esta sessão, então não conferi quais chaves estão
  configuradas em produção nem os logs de erro reais.
