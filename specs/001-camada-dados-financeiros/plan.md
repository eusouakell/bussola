# Plano 001: camada de dados financeiros determinística

- **Spec:** [spec.md](./spec.md). **Tarefas:** [tasks.md](./tasks.md).
- **Marcos:** [marcos.md](./marcos.md).
- **Rastreabilidade:** [traceability.md](./traceability.md).

## Contexto técnico

- **Stack:** Python 3.12 com `uv`, Pydantic v2 (modelos de `bussola_mcp.contratos`),
  `google-cloud-bigquery` e pytest (`asyncio` auto, marcador `bq`). O ruff usa
  linha de 100 e as regras E, F, I, UP e B.
- **BigQuery:** projeto `batalha-time-07-lkbv`, `us-central1`.
  - A origem `hackathon_dados.extrato_sintetico` é somente leitura.
  - O destino é `bussola_dados`. Só este ciclo escreve nele.
- **Arquitetura (ports & adapters):**
  - **Port:** `RepositorioFinanceiro` (contrato, `dominio/interfaces.py`).
  - **Adapters:** `RepositorioBigQuery` (este ciclo) e `RepositorioFake` (000).
  - **Domínio puro:** `metricas.py` e `simulacao.py`. Não fazem I/O, só recebem o
    repositório ou as linhas.
  - As ferramentas do 003 ficam por cima e só validam, chamam e montam o envelope.
- **Nomes:**
  - O contrato fixa os nomes do §4. As funções de `metricas.py` têm os nomes das
    ferramentas do §5.
  - O que o contrato não nomeia está em inglês (`MetricResult`, `MetricError`,
    `income_band`, `rank_opportunities` etc.).
  - Os campos espelham os `dados` do contrato. Os textos ao cliente estão em pt-BR.

## Estrutura

```text
data/sql/*.sql                       # 8 etapas (7 tabelas + users), TRUNCATE+INSERT
data/scripts/build_dados.py          # build, validação pós-build e --fixtures
mcp_server/bussola_mcp/dominio/
  simulacao.py                       # funções puras de contratos §4 + auxiliares
  metricas.py                        # uma função por ferramenta de dados (§5)
  repositorio_bq.py                  # RepositorioBigQuery (query | memoria)
mcp_server/tests/dados/              # unitários, integração offline e @pytest.mark.bq
```

## Decisões

| ID | Decisão | Motivo |
|---|---|---|
| D-01 | As tabelas são reconstruídas com `BEGIN; TRUNCATE; INSERT; COMMIT;` sobre o DDL do contrato. O ciclo §3.2 pedia `CREATE OR REPLACE` | `CREATE OR REPLACE TABLE ... AS SELECT` perde o modo `REQUIRED` das colunas do contrato. O resultado continua idempotente |
| D-02 | O domínio fala por valores (`MetricResult`) e exceções tipadas (`MetricError` → `CodigoErro`), sem depender de tipos do 003 | O 001 não pode depender de código fora da `main`. A adaptação para `Computation`/`DomainError` do 003 é direta (ver "Ligação") |
| D-03 | `saldo_final` é o saldo no fim do último dia com lançamento: o `saldo_apos` que nenhum lançamento do dia consome como saldo anterior. Empate: o valor que continua no dia seguinte e, depois, a ordem estável (`tipo, descr, vlr, saldo_apos`). `saldo_inicial` é o `saldo_final` do mês anterior. No 1º mês, é o saldo anterior do 1º lançamento não produzido no dia | A regra gulosa anterior dava continuidade entre meses em 76% dos casos, e esta dá 89%. Em relação à fixture do 000, mudam 7.132 `saldo_inicial` e 1.703 `saldo_final` na base toda. Do âncora, `saldo_final` não muda (202506 = 17.652,15; 202512 = 47.597,68), e `saldo_inicial` passa a 16.085,22 (202506) e 44.420,19 (202512). Nenhuma métrica usa `saldo_inicial` |
| D-04 | `juros` = Σ saídas cuja micro normalizada tem palavra iniciada por "juros" | A base não tem campo de juros. A lista de micros de juros aguarda revisão humana (ciclo §10) |
| D-05 | O `RepositorioBigQuery` reaplica em Python, nos dois modos, o critério de recorrência (≥ 3 meses distintos por `descr_norm`) só sobre as linhas `≤ ate_anomes`. A faixa de renda da coorte do cliente é `fmean(renda)` de `perfil_mensal ≤ ate_anomes` | A tabela marca a recorrência no ano todo, e sem o filtro o futuro vazaria para o corte (constituição IV). O `RepositorioFake` (000, congelado) não reaplica. Nenhuma métrica usa `recorrentes` |
| D-06 | O seed de `categorias` é INFERRED: 0,5 em assinaturas e delivery; 0,3 em restaurantes, lazer e compras; 0,2 em padaria, clubes, infantis e viagens. Tem 7 pares diferentes da regra provisória do 000 | A regra do 000 era por palavra-chave. O seed versionado é a fonte (ciclo §3.1). Isso muda os goldens de `oportunidades_corte` e `comparar_cenarios` |
| D-07 | As fixtures v1 saem de `build_dados.py --fixtures`: as linhas vêm do `RepositorioBigQuery` e os goldens de `metricas.*` sobre `RepositorioFake` dessas linhas | O mesmo código gera o golden e responde em produção, e o teste de consistência compara os dois |
| D-08 | `categorias()` fica em cache na instância (seed estático). As demais leituras não têm cache | Economiza um job por chamada de `oportunidades_corte` e `comparar_cenarios` |
| D-09 | As fixtures v1 mudam goldens que o `web/` copia (`web/fixtures/goldens.json`) e números fixos em `web/src/simulado/agente-simulado.test.ts` (acelerado de 202506: 1.681,15 → 18 meses passa a 1.660,85 → 19). O job `web` do CI quebra até o dono do `web/` (008) rodar `npm run fixtures` e atualizar esses testes (e `web/fixtures/roteiro-demo.json`, se usar os valores) | O 001 não pode editar `web/`. Os valores novos vêm do seed D-06 e são os que o 003 serve em produção |

## API pública para o 003 (estável)

Todas as funções são síncronas e deterministas, e todos os valores em BRL são `float`
com 2 casas (`contratos.brl`).

### `bussola_mcp.dominio.metricas`

```python
@dataclass(frozen=True)
class MetricResult:
    dados: BaseModel            # o modelo Dados* da ferramenta
    periodo: Periodo            # inicio = 1º mês considerado; fim = ate_anomes (resumo_mes: anomes, anomes)
    avisos: tuple[str, ...] = ()

class MetricError(Exception):            # .codigo: CodigoErro, .mensagem: str (pt-BR)
class InvalidInputError(MetricError, ValueError)   # ENTRADA_INVALIDA
class InsufficientDataError(MetricError)           # DADOS_INSUFICIENTES
class ImplausibleTermError(MetricError)            # PRAZO_IMPLAUSIVEL

def perfil_financeiro(repo, id_usuario, ate_anomes) -> MetricResult
def capacidade_poupanca(repo, id_usuario, ate_anomes) -> MetricResult
def oportunidades_corte(repo, id_usuario, ate_anomes, top_n=5) -> MetricResult
def dividas_e_parcelas(repo, id_usuario, ate_anomes) -> MetricResult
def simular_objetivo(repo, id_usuario, ate_anomes, valor_alvo,
                     prazo_meses=None, aporte_mensal=None, usar_saldo_atual=False) -> MetricResult
def comparar_cenarios(repo, id_usuario, ate_anomes, valor_alvo, prazo_meses,
                      regras: RegrasCenario | None = None) -> MetricResult
def resumo_mes(repo, id_usuario, ate_anomes, anomes) -> MetricResult
def referencia_coorte(repo, id_usuario, ate_anomes, categoria) -> MetricResult

def build_envelope(ferramenta: str, resultado: MetricResult) -> dict   # Resposta[...] em JSON
def income_band(renda_media: float) -> str                            # FaixaRenda (limites 3k/6k/10k/20k)
def normalize_label(texto: str) -> str                                # NFKD + casefold + espaços
```

**Regras de uso:**

- **Validação:** cada função valida e normaliza `id_usuario` (UUID v4) e `ate_anomes`
  (202501–202512) antes de ler o repositório. Entradas fora das regras de `Entrada*`
  levantam `InvalidInputError`:
  - `top_n` fora de 1–10;
  - `valor_alvo ≤ 0`;
  - nenhum ou os dois entre `prazo_meses` e `aporte_mensal`;
  - `anomes > ate_anomes`.
- **Existência do cliente:** fica a cargo do runner do 003
  (`repository.usuario_existe`). Cliente sem meses até o corte levanta
  `InsufficientDataError`.
- **`simular_objetivo` no modo aporte:** prazo calculado acima de 360 meses levanta
  `ImplausibleTermError`.
- **`referencia_coorte`:** sem linha da faixa para a macro, levanta
  `InsufficientDataError("Sem referência da faixa de renda para esta categoria.")`.
- **Avisos:** são os mesmos dos goldens (ex.: "Saldo ficou negativo em 1 mês do
  período.").

### `bussola_mcp.dominio.simulacao`

```python
@dataclass(frozen=True) class ResultadoPrazo:  prazo_meses: int; viavel: bool; motivo: str | None
@dataclass(frozen=True) class ResultadoAporte: aporte_mensal: float; viavel: bool; motivo: str | None
@dataclass(frozen=True) class Capacidade:      sobra_mediana: float; meses_considerados: int
    # .viavel (sobra_mediana > 0), .motivo, Capacidade.from_profile(meses: Sequence[PerfilMes])
@dataclass(frozen=True) class ImpactoCortes:   economia_mensal: float; itens: tuple[CorteSugerido, ...];
                                               nao_encontradas: tuple[str, ...]; viavel: bool; motivo: str | None
@dataclass(frozen=True) class ImpactoDividas:  parcelas_ativas: tuple[ParcelaAtiva, ...]; total_mensal: float;
                                               comprometimento_renda_pct: float; viavel: bool; motivo: str | None

def prazo_para_meta(valor_alvo, aporte_mensal, saldo_inicial=0.0, rendimento_mensal=0.0) -> ResultadoPrazo
def aporte_para_prazo(valor_alvo, prazo_meses, saldo_inicial=0.0, rendimento_mensal=0.0) -> ResultadoAporte
def gerar_cenarios(capacidade, valor_alvo, prazo_meses, gastos, categorias,
                   regras: RegrasCenario | None = None) -> list[Cenario]
def impacto_cortes(gastos, cortes: dict[str, float], meses_considerados: int | None = None) -> ImpactoCortes
def impacto_dividas(parcelas, renda_media: float) -> ImpactoDividas
```

**Semântica:**

- **`prazo_para_meta`:**
  - `saldo_inicial ≥ valor_alvo` → prazo 0, viável;
  - aporte 0 sem rendimento → inviável, prazo 0, com motivo e sem divisão;
  - prazo acima de 360 → inviável, mas o prazo calculado volta (o chamador decide
    `PRAZO_IMPLAUSIVEL`).
- **`aporte_para_prazo`:** prazo < 1 ou > 360 → inviável. Sem rendimento, o aporte é
  `brl((alvo − saldo) / prazo)`.
- **Rendimento:** `rendimento_mensal > 0` usa juros compostos mensais. O padrão é 0, porque
  a base não tem taxas.
- **Entradas negativas ou não finitas** levantam `ValueError`.
- **`gerar_cenarios`:** percentuais de `RegrasCenario` sobre `max(sobra_mediana, 0)`. O
  acelerado soma os cortes das até 10 oportunidades discricionárias. `viavel` = prazo ≤
  `prazo_meses`. Os `trade_offs` são frases fixas. Não há nenhum valor fixo de cenário.
- **`impacto_cortes`:**
  - as chaves são nomes de micro ou, na falta de casamento, de macro, sem acento e sem
    diferença de caixa;
  - os valores são frações de 0 a 1;
  - por padrão, os meses são os `anomes` distintos de `gastos`.
- **`impacto_dividas`:** recebe as parcelas do mês de corte, na mesma ordem e com o mesmo
  comprometimento do golden.

**Auxiliares públicos** (inglês, sem I/O): `mean_brl`, `median_brl`, `months_to_reach`,
`format_months`, `format_brl_whole`, `format_percent`, `opportunity_criterion` e
`rank_opportunities(gastos, categorias, meses_considerados, limit=10)`.

### `bussola_mcp.dominio.repositorio_bq`

```python
READ_MODES = ("query", "memoria")
class RepositoryUnavailableError(RuntimeError)   # falha do BigQuery, com mensagem genérica
class RepositorioBigQuery:                       # implementa RepositorioFinanceiro
    def __init__(self, modo: str | None = None, *, client=None, dataset: str | None = None,
                 projeto: str | None = None) -> None
```

- **Padrões:**
  - `modo` = `BQ_MODO_LEITURA` ou `"query"`;
  - `dataset` = `BQ_DATASET_DADOS` ou `"bussola_dados"`, restrito a `bussola_dados*`;
  - `client` = `bigquery.Client(project=projeto or GOOGLE_CLOUD_PROJECT, location="us-central1")`.
- **Modo `query`:** jobs com `@id_usuario`, `@ate_anomes`, `@desde_anomes`, `@faixa_renda`
  e `@macro`. O único texto no SQL é o dataset validado.
- **Modo `memoria`:** `list_rows` de todas as tabelas no construtor, indexadas por cliente,
  com filtro em Python.
- **Validação antes do cliente:** `id_usuario` inválido, `ate_anomes`/`desde_anomes` fora
  da faixa ou `faixa_renda` fora de `FaixaRenda` levantam `ValueError` antes de qualquer
  chamada (inclusive em `usuario_existe`).
- **Mesma ordem nos dois modos:**
  - `perfil`: `anomes`;
  - `gastos` e `entradas`: `anomes, macro, micro`;
  - `recorrentes`: `anomes, descr_norm, macro, micro`, com o filtro D-05;
  - `parcelas`: `anomes, descr, parcela_atual, parcela_total, vlr`;
  - `categorias`: `macro, micro`;
  - `coorte`: ordem de `FaixaRenda`, depois `macro`.

## Ligação depois dos merges

- **003 (após o merge do 001):** `ferramentas/computations.py` ganha
  `DomainComputations(repository)`. Cada método chama `metricas.<ferramenta>` e converte
  o resultado e os erros:

  ```python
  try:
      r = metricas.perfil_financeiro(self.repository, id_usuario, ate_anomes)
  except MetricError as exc:
      raise DomainError(exc.codigo, exc.mensagem) from exc
  return Computation(dados=r.dados, periodo=r.periodo, avisos=r.avisos)
  ```

  - `RepositoryUnavailableError` e outras exceções já viram `INDISPONIVEL` no runner.
  - `server.py` já instancia `RepositorioBigQuery(modo=...)`.
  - `referencia_coorte` passa a usar `metricas.referencia_coorte`, com a faixa pelo
    perfil até o corte (D-05), sem `usuarios.json`.
- **006:** lê `resumo_mes__AAAAMM` das fixtures v1, sem código novo. Em produção, chama
  `metricas.resumo_mes` via a ferramenta do 003.
- **Web (D-09):** `web/fixtures/goldens.json` é cópia dos goldens. Depois do merge do 001, o
  dono do `web/` roda `npm run fixtures` e atualiza `agente-simulado.test.ts` (1.660,85 → 19
  meses no acelerado de 202506). Até lá, o job `web` do CI fica vermelho.
- **000/Makefile:** `make fixtures` ainda gera o conjunto provisório. As fixtures v1 saem
  de `make fixtures-v1` (acréscimo deste ciclo).

## Verificação

- `make lint` e `make test` são offline: fakes, cliente BigQuery falso e fixtures
  sintéticas.
- `make test-bq` roda `mcp_server/tests/dados/test_repositorio_bq_real.py`, só leitura:
  compara `query` com `memoria` para o âncora e o controle, e o âncora com o §8 a 1%.
