# Ciclo 001 — F1 Camada de dados financeiros determinística

> **Disparo:** `/spec-master docs/ciclos/001-camada-dados-financeiros.md`,
> no Claude Code, dentro da worktree `../bussola-001`, na branch
> `001-camada-dados-financeiros`.
>
> **Onda:** 1. **Prioridade:** P0. **Spec:**
> `specs/001-camada-dados-financeiros`. **Plano:** [README](./README.md).
>
> **Leitura obrigatória antes do Step 3:**
>
> - [contratos.md](./contratos.md) §0–§5 e §8.
> - Contexto mestre [§3, §8 e §10 F1](../contexto-spec-master.md).
> - [dados-tecnologia.md](../dados-tecnologia.md) §2 (as 8 perguntas).

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Uma única feature:** `id: camada-dados-financeiros`,
   `spec_directory: specs/001-camada-dados-financeiros`. Não gere outras
   features a partir do contexto mestre.
2. **Número fixo:** `SPECIFY_FEATURE_DIRECTORY=specs/001-camada-dados-financeiros`.
3. **Step 2:** Spec Kit já inicializado. Estratégia Git **Trunk-Based**: não
   crie branch nem instale a extensão git.
4. **Constituição congelada** (`contratos-v1`). No Step 4, **não aplique**
   nenhuma mudança; grave a proposta em
   `specs/001-camada-dados-financeiros/proposta-constituicao.md`.
5. **Escreva só nos caminhos da §4.** Se precisar mudar um contrato, pare,
   registre em `specs/001-*/questoes.md` e abra um PR `contracts:`
   separado.
6. **BigQuery:**
   - só este ciclo escreve em `bussola_dados`;
   - a origem `hackathon_dados` é **somente leitura**;
   - testes que gravam usam `bussola_app_dev`. Este ciclo não precisa
     gravar lá.
7. **Ao final:**
   - `make test` e `make lint` verdes;
   - rastreabilidade exportada para `specs/001-*/traceability.md`.
8. **Team Mode (opcional):** workstreams `sql` (3.1–3.2) ∥ `simulacao`
   (3.4–3.5), unidos pela interface `RepositorioFinanceiro`.

## 2. Propósito

Transformar o extrato sintético em **métricas confiáveis por usuário** e em
**funções de simulação testadas**. Todo número que o cliente verá sai
daqui; o LLM só redige.

## 3. Escopo e comportamento esperado

### 3.1 Tabelas `bussola_dados` (SQL em `data/sql/`)

Construídas a partir de `hackathon_dados.extrato_sintetico`, com as colunas
exatas de `contratos.md` §3.

| Tabela | Regra |
|---|---|
| `perfil_mensal` | `renda` = Σ entradas; `gasto` = Σ saídas; `sobra` = renda − gasto; `saldo_inicial`/`saldo_final` vêm de `saldo_apos` ordenado por `anomesdia` (saldo antes do primeiro e depois do último lançamento do mês); `saldo_minimo`/`saldo_maximo` do mês; `juros` = saídas de microcategorias de juros |
| `gastos_categoria` | Saídas (`tipo = 'S'`) agregadas por macro e micro |
| `entradas_categoria` | Entradas (`tipo = 'E'`) agregadas por macro e micro |
| `recorrentes` | `descr` normalizada (minúsculas, sem dígitos de parcela ou datas), presente em ≥ 3 meses distintos no ano. Uma linha por ocorrência mensal |
| `parcelas` | Lançamentos com `parcela_total > 1` |
| `categorias` | Seed versionado (`data/sql/seed_categorias.sql`) com todas as 98 micro. `discricionaria` = true para lazer, restaurantes/comer fora, delivery, assinaturas, compras/vestuário e viagens; `corte_max_pct` entre 0,2 e 0,5 conforme a categoria |
| `referencia_coorte` (P1) | Média e mediana mensal por `faixa_renda` × macro, agregando todos os usuários. Nunca dado individual |

### 3.2 Build

- **`data/scripts/build_dados.py`:**
  - executa os SQL em ordem, de forma idempotente
    (`CREATE OR REPLACE TABLE`);
  - opção `--dataset`, com padrão `bussola_dados`.
- **Validações pós-build:**
  - `perfil_mensal` tem 1.000 usuários × 12 meses;
  - nenhuma linha com `anomes` fora de 202501–202512;
  - a soma de `gastos_categoria` bate com `perfil_mensal.gasto`;
  - a soma de `entradas_categoria` bate com `perfil_mensal.renda`.
- **Marco "tabelas v1" (desbloqueia o `make test-bq` do 003):** assim que `perfil_mensal`,
  `gastos_categoria`, `entradas_categoria`, `recorrentes`, `parcelas` e
  `categorias` estiverem publicadas e validadas:
  1. registrar o marco em `specs/001-*/marcos.md`;
  2. avisar o time.

  Isso deve acontecer **antes** de terminar a simulação.

### 3.3 Repositório (`mcp_server/bussola_mcp/dominio/repositorio_bq.py`)

- `RepositorioBigQuery(modo)` implementa `RepositorioFinanceiro`.
- **`modo="query"`:** jobs parametrizados (`@id_usuario`, `@ate_anomes`).
- **`modo="memoria"`:** Plano B, sem `bigquery.jobUser`. Carrega as tabelas
  via `list_rows` na inicialização e filtra em Python.
- Os dois modos devem devolver **resultados idênticos**.
- Todo `id_usuario` é validado por regex antes de qualquer consulta. **Nunca**
  montar SQL por concatenação.

### 3.4 Métricas (`dominio/metricas.py`)

- Uma função por ferramenta de §5, produzindo o campo `dados` exato de
  `perfil_financeiro`, `capacidade_poupanca`, `oportunidades_corte`,
  `dividas_e_parcelas`, `resumo_mes` e `referencia_coorte` (P1).
- Sempre consideram só os meses `≤ ate_anomes`.
- **Regras:**
  - `saldo.atual` = `saldo_final` de `ate_anomes`;
  - `meses_negativos` = meses com `sobra < 0`;
  - `oportunidades_corte`:
    - base: só categorias discricionárias;
    - `media_mensal` dos meses considerados;
    - `economia_potencial_mensal = media_mensal × corte_max_pct`;
    - `criterio` em texto fixo;
  - `comprometimento_renda_pct` = parcelas de `ate_anomes` ÷ renda média;
  - `meses_restantes` = `parcela_total − parcela_atual` na ocorrência mais
    recente.
- **Avisos determinísticos** (ex.: "Saldo ficou negativo em N meses") são
  devolvidos para o envelope.

### 3.5 Simulação (`dominio/simulacao.py`)

- Funções puras com as assinaturas de `contratos.md` §4:
  `prazo_para_meta`, `aporte_para_prazo`, `gerar_cenarios`,
  `impacto_cortes` e `impacto_dividas`.
- **`RegrasCenario`** com os padrões de §4:
  - 40%, 60% e 80% da sobra mediana;
  - cortes no cenário acelerado;
  - rendimento 0;
  - saldo inicial 0, a menos que `usar_saldo_atual`.
- `trade_offs` são gerados por regra, com frases fixas parametrizadas.
- Nenhum valor fixo de cenário (R$ 600 / R$ 900) no código.

### 3.6 Fixtures oficiais

- Regenerar `contracts/fixtures/` a partir das tabelas e funções reais,
  incluindo os golden das ferramentas e `resumo_mes__AAAAMM`.
- Entregar num PR **`contracts: fixtures v1 a partir de bussola_dados`**,
  separado do PR da feature ou como primeiro commit dela.
- Os consumidores (003, 004, 006) precisam ser avisados.

## 4. Propriedade (escreve só aqui)

- `data/sql/`
- `data/scripts/build_dados.py`
- `mcp_server/bussola_mcp/dominio/{repositorio_bq,metricas,simulacao}.py`
- `mcp_server/tests/dados/`
- `contracts/fixtures/` (só via PR `contracts:`)
- `specs/001-camada-dados-financeiros/`

## 5. Contratos

- **Consome:**
  - `contratos.py`, `interfaces.py` e `fakes.py`;
  - DDL `bussola_dados`;
  - env `BQ_DATASET_DADOS` e `BQ_MODO_LEITURA`.
- **Provê:**
  - tabelas `bussola_dados` preenchidas;
  - `RepositorioBigQuery`, `metricas.*` e `simulacao.*`;
  - fixtures v1.

## 6. Critérios de aceite

- [ ] Para o âncora, as 7 perguntas numéricas de `dados-tecnologia.md` §2
      têm resposta reproduzível a partir das tabelas e funções. O resultado
      fica em `specs/001-*/perguntas-ancora.md`, com a pergunta → função →
      valor, para `ate_anomes = 202506` e `202512`.
  - As premissas de demo são INFERRED: entrada de R$ 60.000 em 24 meses; a
    pergunta "+R$ 300/mês" soma 300 ao aporte do cenário equilibrado.
  - A 8ª pergunta (produtos Itaú) não é numérica. Fica registrada como
    tratada genericamente pelo agente (Q3).
- [ ] Testes unitários de simulação com casos conhecidos e bordas:
  - sobra ≤ 0 → `viavel = false`, com motivo;
  - objetivo já atingido (saldo inicial ≥ alvo) → prazo 0;
  - prazo impossível → `viavel = false`.
- [ ] Métricas do âncora (`ate_anomes = 202512`) dentro de 1% dos valores
      de referência de `contratos.md` §8.
- [ ] Todas as consultas usam parâmetros. Um `id_usuario` com injeção (ex.:
      `x' OR '1'='1`) é rejeitado antes de chegar ao BigQuery (teste).
- [ ] O corte temporal funciona: com `ate_anomes = 202506`, nenhuma métrica
      usa dado posterior (teste por métrica).
- [ ] `make test-bq`: os modos `query` e `memoria` devolvem resultados
      idênticos para âncora e controle.
- [ ] Marco "tabelas v1" publicado e registrado. Fixtures v1 entregues via
      PR `contracts:`.

## 7. Cenários de teste

- `perfil_mensal(âncora, 202512)`: 12 linhas. A média de `sobra` fica
  ≈ 2.836 (±1%).
- `oportunidades_corte(âncora, top_n=3)` inclui restaurantes/comer fora
  (≈ 364/mês) e **não** inclui aluguel.
- `gerar_cenarios` com o âncora e alvo de 60.000:
  - o aporte do conservador é menor que o do equilibrado, que é menor que o
    do acelerado;
  - o prazo do acelerado é o menor.
- `prazo_para_meta(60000, 0)`: `viavel = false`, sem divisão por zero.
- Controle (`31e94f2f…`): as métricas nunca misturam linhas do âncora.

## 8. Dependências e gate de merge

- **Dependências duras:** 000 mergeado (contratos e fixtures provisórias).
- **Quem espera por este ciclo:**
  - o 002 aguarda o **marco tabelas v1**, não o merge;
  - o 003 troca os fakes pelo real após o merge;
  - o 006 usa `resumo_mes`.
- **Gate de merge:** critérios da §6 verdes. Este é o **2º na ordem de
  merge**.

## 9. Fora de escopo

- Ferramentas MCP e envelope (003).
- Corpus e embeddings (002).
- Recategorização de rótulos ruidosos (002, P2).
- Taxas de rendimento ou financiamento: não existem na base e não se
  inventam.

## 10. Questões em aberto

- **Q2 do mestre:** confirmar o âncora e os percentuais de cenário. Usar a
  proposta de §4 até decisão.
- A lista de microcategorias de juros e a seleção de discricionárias exigem
  revisão humana do seed.
- Premissa de valor da entrada para a demo (R$ 60.000) é INFERRED.

## 11. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| Tabelas derivadas e simulação com testes | Mestre §10 F1 | EXPLICIT |
| Colunas e tabelas finais (`entradas_categoria`, `parcelas`) | `contratos.md` §3 | EXPLICIT |
| 8 perguntas do âncora | `dados-tecnologia.md` §2; mestre §10 F1 | EXPLICIT |
| Modo `memoria` (Plano B, sem `jobUser`) | Mestre §16 | EXPLICIT |
| Critério de recorrência (≥ 3 meses) e faixas de `corte_max_pct` | Este ciclo | INFERRED |
| Entrada de R$ 60.000 em 24 meses na demo | Este ciclo | INFERRED |
| Percentuais finais dos cenários | Mestre §20, Q2 | UNRESOLVED |
