# Mr.Holmes

Painel de consultas e investigação. Você digita um dado (nome, CPF, CNPJ,
telefone, e-mail, @usuário, placa, domínio, número de processo ou link) e
recebe um dossiê com a fonte e o nível de confiança de cada fato.

Em produção: https://mrholmes.trustcorp.com.br (Railway, deploy automático a
cada push na `master`).

## Páginas

| Página | O que faz |
|---|---|
| **Investigar** | Caixa única. Detecta o tipo do dado, roda as consultas automáticas em paralelo, segue os achados (pivô) e monta o dossiê |
| **Diretório de fontes** | Árvore de fontes por categoria. Diz o que cada uma entrega e quanto custa, e abre já pesquisada no dado digitado |
| **Limpar Nome** | Do relatório do birô até a baixa: classifica a dívida, escreve o pedido e acompanha prazos |
| **Monitoramento** | Reinvestiga alvos e avisa por e-mail quando surge algo novo |
| **Dark web (Robin)** | Busca na rede Tor com relatório por IA |
| **Histórico** | Dossiês salvos, para reabrir ou comparar |

## O que cada tipo de dado devolve

| Você digita | Sai no dossiê |
|---|---|
| **Telefone** | Pessoas e empresas com o número no cadastro (nome, CPF ou CNPJ, nascimento, mãe), outros telefones, e-mails, endereços e empresas do dono. Mais DDD, operadora de origem e páginas que citam o número |
| **E-mail** | Dono do e-mail (mesma ficha do telefone), contas em que o e-mail está cadastrado, vazamentos e Gravatar |
| **Nome** | Candidatos com CPF, nascimento e nome da mãe para separar homônimos. Com um só candidato, a ficha completa. Mais sócio de quais empresas, PEP, sanções, diários oficiais e JusBrasil |
| **CPF** | Ficha completa da BigDataCorp, vínculos federais, sanções e empresas. Processos e pesquisa completa (parentes, veículos, débitos) por botão |
| **CNPJ** | Receita com quadro societário, CNPJ Trust, sanções, contratos federais e diários. Cada sócio vira alvo |
| **Processo** | Tribunal, classe, assunto e movimentação oficial (DataJud) |
| **@usuário** | Perfis em centenas de sites, GitHub, LinkedIn e Instagram |
| **Domínio / IP** | Titular (.br com CPF ou CNPJ), subdomínios, e-mails e geolocalização |

Quem resolve telefone, e-mail e nome é o **localizador da BigDataCorp**
(`holmes/bigdatacorp.py`, função `localizar`). Ele usa as chaves `phone{}`,
`email{}` e `name{}` da mesma API já contratada. A cobrança é por pessoa ou
empresa devolvida, com teto de 3 por telefone ou e-mail e 5 por nome.

## Rodar local

```bash
pip install -r requirements.txt
cp .env.example .env        # preencha as chaves
streamlit run web_app.py
```

## Chaves (Railway → Variables)

| Chave | Para quê |
|---|---|
| `BIGDATACORP_ACCESS_TOKEN` + `BIGDATACORP_TOKEN_ID` | Ficha de CPF e CNPJ e o localizador por telefone, e-mail e nome |
| `SERPER_API_KEY` | Busca no Google a partir do servidor |
| `PORTAL_TRANSPARENCIA_KEY` | Vínculos federais, PEP e sanções (gratuita) |
| `BRIGHTDATA_API_KEY` + `HOLMES_UNLOCKER=1` / `HOLMES_BRD_DATASETS=1` | Leitura do JusBrasil e perfis de LinkedIn e Instagram |
| `CNPJ_TRUST_KEY` | Consulta completa de CNPJ |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Leitura do caso, desambiguação e chat com o dossiê |
| `RESEND_API_KEY`, `ALERT_EMAIL` | Alertas do monitoramento |

As demais opções estão comentadas em `.env.example`. Detalhes do motor em
`MOTOR.md`.

## Verificação

```bash
python -m pytest                          # testes do motor, sem rede
python scripts/verificar_diretorio.py     # testa ao vivo cada fonte do diretório
```

O verificador sai com erro se algum link do diretório cair ou se um
repositório for arquivado. Vale rodar uma vez por mês.

## Uso responsável

A ferramenta consulta dados pessoais. Use com finalidade legítima e base legal
(LGPD): investigação patrimonial, instrução de processo, prevenção à fraude,
diligência prévia. Saldo bancário, declaração de renda, restrição de veículo e
titular de chave Pix não são consulta aberta: saem por ordem judicial
(SISBAJUD, INFOJUD, RENAJUD).

## Créditos

- Nome e ponto de partida: [Mr.Holmes](https://github.com/Lucksi/Mr.Holmes), de Lucksi (GPL-3.0). O CLI e a interface PHP originais foram removidos em novembro de 2026; ficou só o painel web.
- Dark web: [Robin](https://github.com/apurvsinghgautam/robin), de Apurv Singh Gautam (MIT).
- Usuário em sites: lista [WhatsMyName](https://github.com/WebBreacher/WhatsMyName) (CC BY-SA 4.0).
