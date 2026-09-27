# Resultados do eval do RAG (ciclo 002)

Gerado por `make eval-rag` (`eval/rag/rodar_eval.py --resultados`). Perguntas em
[`perguntas.yaml`](perguntas.yaml); acerto = algum trecho esperado no top-3,
sem filtro de tema. Meta: pelo menos 80% no backend `numpy`,
com o `lexico` como linha de base.

## Resumo

| Backend | Acertos top-3 | Conhecimento | Produto | Negativas vazias |
|---|---|---|---|---|
| `lexico` | 18/22 (82%) | 14/18 | 4/4 | 4/4 |
| `numpy` | 22/22 (100%) | 18/18 | 4/4 | 4/4 |

- Backend `numpy`: ok (gemini-embedding-001, dim 768).
- Parâmetros: `lexico` com `min_coverage=0.2` e `single_term_coverage=0.5`; `numpy` com `min_score=0.64`.
- Trechos de produto com marcador de taxa (`%`, `a.a.`, `a.m.`, `R$`): nenhum.

## Por pergunta

| Id | Tipo | Pergunta | `lexico` | `numpy` |
|---|---|---|---|---|
| p01 | conhecimento | O banco pode cobrar de juros no cartão mais do que o valor que eu devia? | ❌ | ✅ 1º |
| p02 | conhecimento | Por quanto tempo a dívida pode ficar no rotativo do cartão? | ✅ 1º | ✅ 1º |
| p03 | conhecimento | Paguei só o mínimo da fatura, o que acontece com o resto? | ✅ 1º | ✅ 1º |
| p04 | conhecimento | O que é o CET de um empréstimo e o que entra nele? | ✅ 1º | ✅ 1º |
| p05 | conhecimento | Existe um limite para os juros do cheque especial? | ✅ 1º | ✅ 1º |
| p06 | conhecimento | Consigo transferir meu empréstimo para outro banco que cobre menos juros? | ✅ 1º | ✅ 1º |
| p07 | conhecimento | Como vejo todas as dívidas que estão no meu nome no Banco Central? | ✅ 1º | ✅ 1º |
| p08 | conhecimento | O gerente disse que só libera o empréstimo se eu fizer um seguro. Ele pode fazer isso? | ✅ 1º | ✅ 1º |
| p09 | conhecimento | Quais serviços da conta corrente o banco não pode cobrar? | ✅ 1º | ✅ 1º |
| p10 | conhecimento | Qual a diferença entre consignado e empréstimo pessoal? | ✅ 1º | ✅ 1º |
| p11 | conhecimento | Não consigo pagar as dívidas e está faltando dinheiro até para o básico. O que a lei prevê? | ❌ | ✅ 1º |
| p12 | conhecimento | Quanto eu deveria ter guardado para emergências? | ✅ 1º | ✅ 1º |
| p13 | conhecimento | Tenho cartão atrasado, cheque especial e um empréstimo. Qual pago primeiro? | ✅ 1º | ✅ 1º |
| p14 | conhecimento | Como organizo minhas contas do mês para sobrar dinheiro? | ✅ 2º | ✅ 1º |
| p15 | conhecimento | Qual parte do salário é seguro comprometer com prestações? | ❌ | ✅ 1º |
| p16 | conhecimento | Se eu adiantar as parcelas do financiamento, os juros diminuem? | ❌ | ✅ 1º |
| p17 | conhecimento | Como saber qual de duas propostas de crédito sai mais barata? | ✅ 1º | ✅ 1º |
| p18 | conhecimento | Onde reclamo se o banco não resolver meu problema? | ✅ 1º | ✅ 1º |
| p19 | produto | Onde guardo o dinheiro da entrada? | ✅ 1º | ✅ 1º |
| p20 | produto | Quero comprar um carro sem pegar financiamento. Que alternativa existe? | ✅ 1º | ✅ 1º |
| p21 | produto | Tem alguma ferramenta para acompanhar meus gastos por categoria e receber alertas? | ✅ 1º | ✅ 1º |
| p22 | produto | Quero reorganizar minhas dívidas com o banco em um acordo só. Existe um produto para isso? | ✅ 1º | ✅ 1º |

## Negativas (fora do domínio)

| Id | Pergunta | `lexico` | `numpy` |
|---|---|---|---|
| n01 | previsão do tempo | vazio | vazio |
| n02 | Qual a previsão do tempo para amanhã? | vazio | vazio |
| n03 | Quem ganhou o jogo de futebol ontem à noite? | vazio | vazio |
| n04 | Me passa uma receita de bolo de cenoura com cobertura de chocolate. | vazio | vazio |

## Calibração do limiar do `numpy` (cosseno, sem limiar)

- Menor score do 1º acerto entre as positivas: 0.6860.
- Maior score entre as negativas: 0.5995.
- Limiar adotado (`DEFAULT_MIN_SCORE`): 0.64, perto do ponto médio
  entre os dois grupos, para deixar folga dos dois lados.

| Id | Score do 1º acerto |
|---|---|
| p01 | 0.7104 |
| p02 | 0.7539 |
| p03 | 0.7339 |
| p04 | 0.8067 |
| p05 | 0.8018 |
| p06 | 0.7018 |
| p07 | 0.7772 |
| p08 | 0.7525 |
| p09 | 0.7744 |
| p10 | 0.7198 |
| p11 | 0.7365 |
| p12 | 0.7694 |
| p13 | 0.7773 |
| p14 | 0.7579 |
| p15 | 0.7688 |
| p16 | 0.7786 |
| p17 | 0.7718 |
| p18 | 0.7985 |
| p19 | 0.6860 |
| p20 | 0.7022 |
| p21 | 0.7544 |
| p22 | 0.7420 |

| Negativa | Maior score |
|---|---|
| n01 | 0.5995 |
| n02 | 0.5657 |
| n03 | 0.5260 |
| n04 | 0.5469 |
