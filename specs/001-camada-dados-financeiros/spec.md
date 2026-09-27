# Spec 001: camada de dados financeiros determinística

- **Feature:** `camada-dados-financeiros` (ciclo 001, onda 1, P0).
- **Fonte:** [docs/ciclos/001-camada-dados-financeiros.md](../../docs/ciclos/001-camada-dados-financeiros.md),
  com [contratos.md](../../docs/ciclos/contratos.md) §3, §4, §5 e §8.
- **Branch:** `001-camada-dados-financeiros` (worktree `bussola-001`).
- **Plano:** [plan.md](./plan.md). **Tarefas:** [tasks.md](./tasks.md).

## Propósito

Transformar o extrato sintético (`hackathon_dados.extrato_sintetico`, só leitura) em
métricas confiáveis por cliente e em funções de simulação testadas. Todo número que o
cliente vê sai desta camada. O LLM só redige.

## Atores e consumidores

- **003 (ferramentas MCP):** chama `metricas.*` e `simulacao.*` e usa o
  `RepositorioBigQuery` no servidor real.
- **002 (RAG):** espera o marco "tabelas v1".
- **004 e 006:** consomem as fixtures v1 (`resumo_mes__AAAAMM` no 006).
- **Web (BFF):** lê `bussola_dados.users` (personas do login simulado).

## Requisitos funcionais

| ID | Requisito | Classificação |
|---|---|---|
| FR-001 | SQL versionado em `data/sql/` monta as 7 tabelas de `bussola_dados` do contratos §3 (mais `users`), com as colunas exatas da DDL | EXPLICIT |
| FR-002 | `perfil_mensal`: renda, gasto, sobra, saldos (inicial, final, mínimo e máximo) e juros por cliente e mês | EXPLICIT |
| FR-003 | `gastos_categoria` e `entradas_categoria` agregam saídas e entradas por macro e micro | EXPLICIT |
| FR-004 | `recorrentes`: `descr` normalizada presente em ≥ 3 meses distintos, com uma linha por ocorrência mensal | EXPLICIT (critério INFERRED) |
| FR-005 | `parcelas`: lançamentos com `parcela_total > 1` | EXPLICIT |
| FR-006 | `categorias`: seed versionado com as 98 micros. Discricionárias com `corte_max_pct` entre 0,2 e 0,5, e as demais com 0 | EXPLICIT (seleção INFERRED) |
| FR-007 | `referencia_coorte` (P1): média e mediana por faixa × macro, só grupos com ≥ 5 usuários | EXPLICIT |
| FR-008 | `build_dados.py`: execução idempotente, `--dataset` (padrão `bussola_dados`, restrito a `bussola_dados*`), validações pós-build e `--fixtures` | EXPLICIT |
| FR-009 | `RepositorioBigQuery(modo)` implementa `RepositorioFinanceiro`. `query` usa jobs parametrizados e `memoria` usa `list_rows` com filtro em Python. Os dois modos dão resultados idênticos | EXPLICIT |
| FR-010 | `id_usuario` é validado como UUID v4 e `ate_anomes` fica em 202501–202512, antes de qualquer consulta | EXPLICIT |
| FR-011 | `metricas.py` tem uma função por ferramenta de dados do §5 e produz o `dados` exato, com período e avisos determinísticos | EXPLICIT |
| FR-012 | As métricas só usam meses `≤ ate_anomes` (corte temporal) | EXPLICIT |
| FR-013 | `simulacao.py`: funções puras `prazo_para_meta`, `aporte_para_prazo`, `gerar_cenarios`, `impacto_cortes` e `impacto_dividas` (contratos §4) | EXPLICIT |
| FR-014 | `RegrasCenario`: 40/60/80% da sobra mediana, cortes no acelerado, rendimento 0 e saldo inicial 0. Nenhum valor fixo de cenário | EXPLICIT (percentuais UNRESOLVED, Q2) |
| FR-015 | `trade_offs` saem de regras com frases fixas parametrizadas | EXPLICIT |
| FR-016 | Fixtures v1 regeneradas a partir das tabelas e das funções reais, em commit `contracts:` separado | EXPLICIT |
| FR-017 | Marco "tabelas v1" registrado em `marcos.md` antes de terminar a simulação | EXPLICIT |
| FR-018 | `perguntas-ancora.md`: pergunta → função → valor, para 202506 e 202512 | EXPLICIT |
| FR-019 | Nenhum log com texto de lançamento, prompt, chave ou token. Nenhum SQL, projeto ou credencial na saída | EXPLICIT (constituição) |

## Critérios de aceite (ciclo §6)

- **AC-01:** as 7 perguntas numéricas do âncora (`dados-tecnologia.md` §2) têm resposta
  reproduzível para 202506 e 202512, em `perguntas-ancora.md`. As premissas de demo são
  INFERRED: R$ 60.000 em 24 meses, e "+R$ 300/mês" somado ao aporte do cenário
  equilibrado. A 8ª pergunta é respondida pelo catálogo curado (RAG do 002), sem taxas.
- **AC-02:** a simulação tem testes unitários com casos conhecidos e bordas:
  - sobra ≤ 0 → `viavel = false`, com motivo;
  - saldo inicial ≥ alvo → prazo 0;
  - prazo impossível → `viavel = false`.
- **AC-03:** as métricas do âncora em 202512 ficam dentro de 1% dos valores do
  contratos §8.
- **AC-04:** todas as consultas são parametrizadas, e `x' OR '1'='1` é rejeitado antes do
  BigQuery (teste).
- **AC-05:** com `ate_anomes = 202506`, nenhuma métrica usa dado posterior (um teste por
  métrica).
- **AC-06:** no `make test-bq`, `query` e `memoria` são idênticos para o âncora e o
  controle.
- **AC-07:** o marco "tabelas v1" está publicado e registrado, e as fixtures v1 foram
  entregues em commit `contracts:`.

## Cenários de teste (ciclo §7)

- **TS-01:** `perfil_mensal(âncora, 202512)` tem 12 linhas, com média de `sobra` ≈ 2.836
  (±1%).
- **TS-02:** `oportunidades_corte(âncora, top_n=3)` inclui restaurantes/comer fora
  (≈ 364/mês) e não inclui aluguel.
- **TS-03:** em `gerar_cenarios` com o âncora e alvo de 60.000, os aportes são
  conservador < equilibrado < acelerado, e o prazo do acelerado é o menor.
- **TS-04:** `prazo_para_meta(60000, 0)` dá `viavel = false`, sem divisão por zero.
- **TS-05:** as métricas do controle (`31e94f2f…`) nunca misturam linhas do âncora.

## Fora de escopo

- Ferramentas MCP e envelope (003).
- Corpus e embeddings (002).
- Recategorização de rótulos ruidosos (002, P2).
- Taxas de rendimento ou financiamento, que não existem na base e não se inventam.

## Premissas e questões

As premissas e questões ficam em [questoes.md](./questoes.md). As decisões técnicas
(D-01 a D-08) ficam em [plan.md](./plan.md#decisões).
