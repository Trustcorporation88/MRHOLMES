# Motor de investigação (`holmes/`)

Uma caixa. Você digita **nome, e-mail, telefone, @usuário, CPF, CNPJ, domínio,
link de perfil, número de processo judicial ou URL (inclusive `.onion`)**.
O motor detecta o tipo, consulta todas as fontes que se
aplicam em paralelo, investiga sozinho o que encontrou e devolve **um dossiê**
com fonte e nível de confiança em cada fato.

```python
from holmes import investigate

dossie = investigate("fulano de tal")
print(dossie.to_markdown())
```

Na interface: menu **🔎 INVESTIGAR — caixa única** (primeira opção).

---

## O que mudou, e por quê

| Antes | Agora |
|---|---|
| 13 páginas por tipo de dado; você escolhia o menu | Uma caixa; o tipo é detectado sozinho |
| 89 serviços abrindo a **home** — você redigitava o alvo | 88 deeplinks que abrem **já pesquisados** no alvo |
| Cada módulo imprimia seu resultado e morria ali | Pivô automático: e-mail → username → perfil → nome → telefone |
| Nenhuma busca clearnet estruturada | Bateria de 10–15 dorks por alvo, com resultado classificado |
| Sem fontes brasileiras | 44 fontes BR: Receita com quadro societário, DataJud/CNJ, PEP no Congresso, Querido Diário, sanções da CGU, Escavador, JusBrasil, Lattes |
| Resultados soltos, sem conferência | Dossiê consolidado, deduplicado, com score por corroboração |
| Ferramenta que falha, falha calada | Toda falha aparece em «fontes que não responderam», com o motivo |

---

## Como funciona

```
alvo digitado
   │
   ├─ entity.py ......... detecta o tipo e gera as variantes
   │                      (E.164, local-part, raiz do domínio, CPF limpo…)
   │
   ├─ connectors/ ....... todas as fontes aplicáveis, em paralelo
   │     auto ........... executa e traz o dado (25 fontes)
   │     deeplink ....... monta a URL já pesquisada (88 fontes)
   │     manual ......... exige login/captcha — declarado, não fingido (14)
   │
   ├─ pivot.py .......... cada achado vira o próximo alvo
   │
   ├─ dossier.py ........ funde, deduplica e pontua por corroboração
   │
   └─ llm.py ............ desambigua homônimo, aponta contradição e próximos passos
```

### Confiança

Um fato ganha score por **corroboração independente**: duas fontes fracas
concordando valem mais que uma fonte forte sozinha — que é como um
investigador raciocina.

| Rótulo | Score | Significado |
|---|---|---|
| `alta` | ≥ 0.85 | confirmado pela fonte, ou 2+ fontes independentes |
| `media` | ≥ 0.55 | indício forte |
| `baixa` | ≥ 0.30 | pode ser homônimo |
| `indicio` | < 0.30 | link gerado, ninguém verificou ainda |

### Pivô

Profundidade 2 é o padrão (o alvo + um salto). Exemplos reais de cadeia:

- `fulano@empresa.com.br` → local-part vira `fulano` → WhatsMyName acha 12 perfis
  → GitHub entrega o nome real → o nome vira alvo de busca e de Escavador.
- `CNPJ` → Receita entrega os sócios → cada sócio vira alvo de nome → Congresso
  e Querido Diário rodam em cima de cada um.
- `@handle` → GitHub expõe e-mail de commit → o e-mail vira alvo e abre novas contas.

Cada pivô registra **por que foi criado**, e a cadeia aparece no dossiê.

---

## Chaves

Só uma é realmente decisiva:

| Chave | Sem ela | Com ela |
|---|---|---|
| **`SERPER_API_KEY`** | A busca de superfície **não funciona no servidor** — Google, DDG e Mojeek bloqueiam IP de datacenter | 10–15 dorks por alvo, resultado classificado em conta/e-mail/telefone |
| `OPENAI_API_KEY` | Resumo determinístico | Análise, desambiguação de homônimo e chat com o dossiê |
| `HIBP_API_KEY` | Vazamento fica só como link | Lista os vazamentos do e-mail |
| `HUNTER_API_KEY` | — | E-mails e padrão de e-mail de um domínio |
| `NUMVERIFY_API_KEY` | — | Operadora atual e tipo de linha |
| `PORTAL_TRANSPARENCIA_KEY` | PEP fica só via Câmara/Senado | PEP oficial, CEIS, CNEP e servidor federal (grátis) |

Configure no Railway em **Variables**, ou cole na própria página (vale só na sessão).

---

## Fontes automáticas (executam de verdade)

| Alvo | Fontes |
|---|---|
| E-mail | MX/provedor/descartável, Gravatar, Holehe¹, HIBP², Hudson Rock (infostealer), busca+dorks |
| Username | WhatsMyName (~90 sites, HTTP puro), GitHub API, Maigret¹, Hudson Rock, busca+dorks |
| Telefone | libphonenumber, numeração BR (DDD, tipo de linha, WhatsApp), NumVerify², busca+dorks |
| Domínio | RDAP/WHOIS, crt.sh (todos os subdomínios), Hunter², busca+dorks |
| CNPJ | Receita Federal (razão social, endereço, contatos, **quadro societário**), Querido Diário, Portal da Transparência² |
| CPF | Portal da Transparência² — PEP e listas de sanção |
| Nome | busca+dorks, Câmara e Senado (detecção de PEP), Querido Diário, Portal da Transparência² |
| **Processo judicial** | **DataJud (CNJ)** — decodifica o número e traz a movimentação oficial |
| Domínio .br | Registro.br — titular e CPF/CNPJ do dono |
| URL / domínio | Rastreamento do site (opt-in) — e-mail, telefone, cripto, perfis |
| IP | ip-api (geo, ISP, rDNS, detecção de VPN/datacenter) |

¹ só se o binário existir no ambiente — detectado e informado na tela
² requer chave

---

## Camada Brasil

É onde o ganho sobre o Google é maior, e quase tudo é de graça.

### Número de processo é um tipo de alvo

Cole `0000133-39.2025.8.26.0334` na caixa. O motor:

1. **Decodifica o número** (offline, sem consultar nada): segmento da Justiça,
   tribunal, unidade de origem e ano. O padrão CNJ carrega tudo isso.
2. **Valida o dígito verificador** (ISO 7064, módulo 97). Número inventado ou
   digitado errado é pego antes de sair consultando tribunal à toa.
3. **Consulta o DataJud do CNJ** — API pública oficial, cobre TJ, TRF, TRT, STJ
   e TST. Devolve classe, assunto, órgão julgador e a **movimentação completa**,
   destacando marcos como sentença, trânsito em julgado e arquivamento.
4. **Abre a consulta do tribunal certo**, deduzida do próprio número — você não
   precisa saber onde o processo corre.

O DataJud não expõe nome das partes (é assim por desenho, por privacidade).
Para partes e advogados, os deeplinks do Escavador e do JusBrasil vão junto.

### Quadro societário como pivô

Um CNPJ na Receita devolve razão social, endereço, telefone, e-mail e **todos
os sócios** com qualificação e faixa etária. Cada sócio vira alvo novo
automaticamente. Num teste real, um único CNPJ produziu 46 achados.

### Pessoa politicamente exposta

O motor cruza o nome com **Câmara dos Deputados** e **Senado** (dados abertos,
sem chave) e, com a chave da CGU, com a **lista oficial de PEP** do Portal da
Transparência. Achar aqui muda o caso: passa a existir declaração de bens,
votação e despesa de gabinete, tudo público. O casamento de nome é conservador
— exige primeiro nome e último sobrenome iguais, para não encher o dossiê de
homônimo.

### Diários oficiais municipais

**Querido Diário** (Open Knowledge Brasil) cobre mais de 3.000 municípios, sem
chave. É onde saem nomeação, licitação vencida, contrato com prefeitura e
sanção administrativa — conteúdo que raramente está indexado no Google. Cada
menção traz município, data e link do PDF original.

### Sanções oficiais

Com `PORTAL_TRANSPARENCIA_KEY` (grátis, cadastro por e-mail), o motor consulta
**CEIS** (inidôneas e suspensas), **CNEP** (Lei Anticorrupção), **PEP** e
**servidores federais**, por nome, CPF ou CNPJ.

### Fontes com deeplink

Escavador, JusBrasil, Lattes, Consulta Sócio, Econodata, Reclame Aqui,
Querido Diário, **TJSP por nome de parte** (o maior tribunal do país aceita a
busca na URL), Portal da Transparência.

### Fontes que só funcionam no formulário

Declaradas como manuais, porque exigem captcha ou são SPA: Sintegra (SP, MG,
PR — não existe portal nacional), Receita (cartão CNPJ e situação de CPF),
CADE, INPI, CVM, Diário Oficial da União, TSE, e os PJe de TRT e TRF. O
console leva você à página certa e diz o que preencher, em vez de fingir que
consulta.

---

## Rastreamento de site (opt-in)

Quando você **já tem a URL**, o motor percorre o site e extrai os artefatos de
cada página: e-mail, telefone, **endereço de cripto**, perfil social divulgado
e domínio externo referenciado. Funciona em clearnet e em `.onion` (via Tor).

Ligue em **«Rastrear o site»** na página Investigar. É a única fonte que faz
muitas requisições ao alvo, então nunca roda sozinha — fora disso aparece como
«pulado» no dossiê.

Controles: profundidade (0–3), teto de páginas, e se pode sair do domínio.

### O que este módulo aprendeu com o TorBot

Avaliei o [TorBot](https://github.com/DedSecInside/TorBot) (OWASP, 4.6k ★) para
esta função. O código é limpo, mas encontrei problemas que tornavam a adoção
direta ruim — e cada um virou uma decisão de projeto aqui:

| TorBot | Aqui |
|---|---|
| `_build_tree` chama `parse_links()` **sem** `base_url` → perde **todo** link relativo (verificado: 3 de 4 links) | `urljoin` sempre; link relativo é resolvido |
| Sem conjunto de visitados | Visitados global e normalizado — sem revisita, sem laço |
| Sequencial | Paralelo, com teto de workers |
| Sem rate limit | Intervalo mínimo por host |
| Classificador ML treinado em site comercial (Booking, Expedia) aplicado a `.onion` | Nenhum rótulo inventado — o motor não chuta categoria |
| Telefone só de `href="tel:"` | `tel:` **e** corpo do texto, validado por libphonenumber |
| Guardava o HTML | Só o artefato extraído; o corpo é descartado |
| Puxa scikit-learn, scipy, numpy (~200 MB) | Nenhuma dependência nova |

**Endereço de cripto** (BTC, ETH, XMR) é extraído porque, em investigação de
mercado `.onion`, é o artefato que amarra vendedor, pagamento e — via exchange
— identidade.

**Por que o corpo da página não é gravado:** em dark web, rastrear domínio
arbitrário faria o servidor materializar conteúdo cuja simples posse é crime.
Aqui só os artefatos sobrevivem à extração.

---

## Deeplink: a mudança mais prática

Antes, `Sync.me` levava para `https://sync.me/pt-br/`. Agora leva para
`https://sync.me/search/?number=+5511987654321`. O mesmo vale para Truecaller,
SpamCalls, Escavador, JusBrasil, Lattes, Portal da Transparência, TSE,
Consulta Sócio, Intelligence X, VirusTotal, crt.sh, BuiltWith, Wayback e outros.

Serviço que exige login ou captcha é marcado como **manual** — aparece com a
instrução, mas o console não promete o que não entrega.

---

## Exportação

HTML (abre no navegador, imprime em PDF com Ctrl+P), Markdown e JSON.
O JSON traz a execução completa: cada conector, cada achado, cada erro.

---

## Ambiente

Nada essencial depende de binário externo. `holehe`, `maigret` e
`theHarvester` são bônus quando existem; o caminho principal é HTTP puro,
que é o que sobrevive no container do Railway. A página mostra o que está
instalado e o que não está.

## Testes

```bash
python -m pytest tests/ -q     # 140 testes
```

Cobrem detecção de alvo, geração de deeplink, pivô, deduplicação, score por
corroboração, escape de HTML e resiliência a conector que falha. Nenhum toca
a rede.

---

## Limite de uso

O motor agrega **fonte pública** e faz checagem de vazamento no padrão do
mercado ("este e-mail aparece na brecha X"). Não despeja credencial vazada e
não integra serviço que comercializa base de dado pessoal roubada.
Uso educacional, em alvos autorizados. Confirme cada fato na fonte antes de
embasar qualquer decisão.


---

## Grafo de conexões

O dossiê agora tem um **mapa visual**: o alvo no centro e cada achado como um
nó ligado a ele. Sócio de empresa liga na empresa, não no alvo — então a rede
`pessoa → empresa → sócio → outra empresa` aparece desenhada, não em lista.
Arraste os nós, dê zoom, clique para focar. Aparece na página Investigar, no
próprio dossiê.

## Hudson Rock (infostealer) — grátis, sem chave

Novo conector automático para e-mail e username: detecta se o alvo teve um
computador infectado por malware infostealer. É o vazamento mais grave — quando
positivo, TODAS as senhas salvas naquela máquina vazaram, não uma só. Traz a
família do malware, a data e o sistema da máquina infectada.

## Histórico que sobrevive a deploy (Railway Volume)

O histórico de dossiês fica em `HOLMES_HISTORY_DIR` (padrão `.holmes_history`,
que o Railway apaga a cada deploy). Para preservar entre deploys:

1. No Railway, crie um **Volume** montado em `/data`.
2. Adicione a variável `HOLMES_HISTORY_DIR=/data/history`.

O mesmo vale para o cache: `HOLMES_CACHE_DIR=/data/cache`.

## Relatório PDF

O dossiê exporta um **PDF com cara de documento de agência** (capa com métricas,
leitura do caso, o que está sustentado, seções com fonte e link). Botão
«📕 Relatório PDF» na área de exportar. Usa reportlab, sem binário externo.

## Análise de foto (EXIF + busca reversa)

Na página Investigar, «📷 Analisar uma foto»: suba uma foto **original** e o
sistema extrai, offline, os metadados EXIF — câmera/aparelho, data e
principalmente **coordenadas GPS** quando existem (foto com GPS entrega o local
exato). Rede social apaga o EXIF, então só vale em foto original. Junto vão os
links de busca reversa por rosto (Google Lens, Yandex, TinEye, PimEyes).

## Monitoramento

Página «🔔 Monitoramento»: uma lista de alvos vigiados. «Verificar todos agora»
reinvestiga cada um, compara com a última vez e gera **alerta de novidade**
(perfil, telefone, vazamento, processo novos). Para o sistema verificar sozinho,
sem ninguém na página, configure um **Railway Cron** rodando:

```
python -m holmes.monitor
```

no intervalo desejado. A watchlist e os alertas ficam em `HOLMES_WATCH_DIR`
(padrão: junto do histórico) — aponte para o Volume para sobreviver a deploy.

## Armazenamento no Supabase (Postgres)

Histórico, watchlist e alertas podem ir para um Postgres do Supabase — não
somem em deploy. Com `SUPABASE_URL` e `SUPABASE_KEY` configurados, o app usa o
Supabase via REST; sem eles, cai no arquivo local automaticamente. Sem
dependência nova (usa a camada HTTP do motor).

Tabelas (criadas uma vez no Supabase): `holmes_dossies`, `holmes_watchlist`,
`holmes_alertas`. O SQL fica em `holmes/store.py` (`SCHEMA_SQL`).

No Railway, adicione duas variáveis:

```
SUPABASE_URL=https://SEU-PROJETO.supabase.co
SUPABASE_KEY=<service_role key do projeto>
```

## Aviso por e-mail (monitoramento)

Quando o monitoramento acha novidade num alvo vigiado, envia um e-mail com o
resumo. Usa SMTP puro (sem serviço pago). Configure no Railway:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=senha-de-app        # NÃO a senha normal — gere uma "senha de app"
ALERT_EMAIL=para-onde-avisar@...  # opcional; sem isso usa o SMTP_USER
```

Com o Railway Cron rodando `python -m holmes.monitor`, o alerta chega sozinho
na sua caixa, sem ninguém abrir a página.

## Exploradores de cripto

Todo endereço de cripto (BTC/ETH/XMR) que o motor extrai vira link direto para
o explorador da blockchain (transações e saldo) e para base de denúncia de
golpe (Bitcoin Abuse, Chainabuse). Aparece em «Fontes para abrir». Fontes
selecionadas da categoria Blockchain do OSINT-Framework (lockfale) — só o que
aceita o endereço na URL; o resto do índice (1.168 links) é home/manual e foi
deixado de fora de propósito, para não repetir o catálogo morto.
