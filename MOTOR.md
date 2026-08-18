# Motor de investigação (`holmes/`)

Uma caixa. Você digita **nome, e-mail, telefone, @usuário, CPF, CNPJ, domínio
ou link de perfil**. O motor detecta o tipo, consulta todas as fontes que se
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
| 89 serviços abrindo a **home** — você redigitava o alvo | 67 deeplinks que abrem **já pesquisados** no alvo |
| Cada módulo imprimia seu resultado e morria ali | Pivô automático: e-mail → username → perfil → nome → telefone |
| Nenhuma busca clearnet estruturada | Bateria de 10–15 dorks por alvo, com resultado classificado |
| Sem fontes brasileiras | Receita/CNPJ com quadro societário, DDD, Escavador, JusBrasil, Lattes, TSE, Transparência |
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
   │     auto ........... executa e traz o dado (16 fontes)
   │     deeplink ....... monta a URL já pesquisada (67 fontes)
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
- `CNPJ` → Receita entrega 8 sócios → cada sócio vira alvo de nome.
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

Configure no Railway em **Variables**, ou cole na própria página (vale só na sessão).

---

## Fontes automáticas (executam de verdade)

| Alvo | Fontes |
|---|---|
| E-mail | MX/provedor/descartável, Gravatar, Holehe¹, HIBP², busca+dorks |
| Username | WhatsMyName (~90 sites, HTTP puro), GitHub API, Maigret¹, busca+dorks |
| Telefone | libphonenumber, numeração BR (DDD, tipo de linha, WhatsApp), NumVerify², busca+dorks |
| Domínio | RDAP/WHOIS, crt.sh (todos os subdomínios), Hunter², busca+dorks |
| CNPJ | Receita Federal via BrasilAPI/ReceitaWS — razão social, endereço, contatos, **quadro societário** |
| IP | ip-api (geo, ISP, rDNS, detecção de VPN/datacenter) |
| Nome | busca+dorks, e os pivôs para username |

¹ só se o binário existir no ambiente — detectado e informado na tela
² requer chave

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
python -m pytest tests/ -q     # 90 testes
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
