# Implementation Plan: MCP server de dados e conhecimento

**Branch**: `003-mcp-dados-conhecimento` | **Spec**: [spec.md](spec.md)

## Summary

Substituir o mock do 000 pelo servidor real: FastMCP em streamable HTTP em
`/mcp`, 9 ferramentas (um módulo cada) sobre portas injetadas, fábrica única
de dependências e testes offline. Enquanto o 001 não está em `main`, os
cálculos vêm de um adaptador de golden atrás da porta `FinancialComputations`.

## Technical Context

- **Linguagem:** Python 3.12, `uv`. **Dependências:** as já presentes (`mcp` 1.x,
  `pydantic`, `uvicorn`). Nenhuma dependência nova.
- **Testes:** `pytest` + `pytest-asyncio`, cliente MCP do SDK em memória
  (`create_connected_server_and_client_session`) e por HTTP
  (`streamable_http_client`). `@pytest.mark.bq` fora do `make test`.
- **Restrições:** sem rede e sem GCP no `make test`; logs só via `logging_json`.

## Constitution Check

| Princípio | Como o ciclo atende |
|---|---|
| II/V (sem SQL, sem segredo, entrada validada) | `Entrada*` antes de tudo; mensagem cita só campos; varredura de saídas |
| III (escopo por cliente) | repositório sempre com `id_usuario`; controle nunca recebe golden do âncora |
| IV (corte temporal) | cortes intermediários servem o golden anterior, nunca meses depois do corte |
| VIII (nomes) | contrato em pt-BR intocado; código interno novo em inglês, consistente por módulo |
| X (contratos) | nenhum arquivo de contrato alterado |

Sem violação. Sem `proposta-constituicao.md`.

## Arquitetura (ports & adapters)

```text
server.py ── build_dependencies() ──► ToolDependencies(repository, searcher, computations)
    │                                        ▲             ▲            ▲
    │                        RepositorioFinanceiro  BuscadorContexto  FinancialComputations
    │                        (interfaces.py, 000)   (interfaces.py)   (ferramentas/ports.py)
    ▼
ferramentas/__init__.register_all(server, deps)
    └─ <ferramenta>.register(server, runner)  → runner.run(nome, argumentos, compute)
                                                  1. Entrada* (ENTRADA_INVALIDA | PRAZO_IMPLAUSIVEL)
                                                  2. usuario_existe (USUARIO_INEXISTENTE)
                                                  3. compute(deps, entrada) → Computation
                                                  4. Resposta[Dados] + Fonte(TABELAS_FERRAMENTA)
                                                  5. DomainError → código; BackendUnavailable/Exception → INDISPONIVEL
                                                  6. log ferramenta_chamada
```

### Estrutura

```text
mcp_server/bussola_mcp/
├── server.py                    # create_server, build_dependencies, main (CLI igual ao mock),
│                                # criar_servidor (alias da API do mock do 000)
└── ferramentas/
    ├── __init__.py              # TOOL_MODULES, register_all
    ├── ports.py                 # Computation, DomainError, BackendUnavailable,
    │                            # FinancialComputations, ToolDependencies
    ├── base.py                  # ToolRunner (validação, envelope, erros, log)
    ├── computations.py          # build_computations(): ÚNICO ponto de troca pós-001
    ├── golden_adapter.py        # GoldenFixtureComputations (provisório, D-03..D-06)
    ├── fixture_backends.py      # FixtureRepository, FixtureSearcher (fakes + INDISPONIVEL)
    ├── perfil_financeiro.py … referencia_coorte.py   # 9 módulos: NAME, compute, register
mcp_server/tests/ferramentas/   # sem __init__.py: nomes de arquivo únicos no projeto
    ├── apoio_ferramentas.py        # sessão em memória, chamar(), espiões e dublês das portas
    ├── test_schema_ferramentas.py  # list_tools ↔ §5 (cliente MCP em memória)
    ├── test_contrato_golden.py     # golden × corte, §7, truncamento, entrada não canônica
    ├── test_erros_ferramentas.py   # 5 códigos × ferramentas aplicáveis, precedência
    ├── test_escopo_ferramentas.py  # id de controle, espião do repositório e do buscador
    ├── test_busca_conhecimento.py  # tema, k, lista vazia, fonte.url, corpus oficial
    ├── test_seguranca_saidas.py    # varredura SELECT / batalha-time-07 / googleapis / Bearer
    ├── test_logs_ferramentas.py    # campos de §9, nunca pergunta, textos ou ids
    ├── test_runner_ferramentas.py  # ToolRunner e is_implausible_term (unitário)
    ├── test_golden_adapter.py      # GoldenFixtureComputations (unitário)
    ├── test_fabrica_dependencias.py # fakes, modo real com módulos injetados, fallback, CLI
    ├── test_http_servidor.py       # subprocess em streamable HTTP; equivalente a make mcp
    ├── test_simulacao_coerencia.py # importorskip de dominio/simulacao (001)
    └── test_bq_ferramentas.py      # @pytest.mark.bq, importorskip de repositorio_bq (001)
```

`criar_servidor(dir_fixtures, *, host, port)` continua exportado como alias
de `create_server` para quem usava a API do mock (ciclos em paralelo).
`test_mock_servidor.py` e `test_mock_http.py` (000) saem; a cobertura está
acima (D-07).

### Fábrica de dependências (`server.build_dependencies`)

1. `--fixtures DIR` ou `BUSSOLA_FAKES` ∈ {`TRUE`, `1`} → `FixtureRepository`,
   `FixtureSearcher`, `build_computations(repository, fixtures_dir)`.
2. Senão: `bussola_mcp.dominio.repositorio_bq.RepositorioBigQuery(modo=BQ_MODO_LEITURA)`
   (padrão `query`) e `bussola_mcp.rag.criar_buscador(RAG_BACKEND)` (padrão
   `lexico`), importados sob demanda. `ModuleNotFoundError` **desse** módulo
   cai no fake correspondente com log `evento=dependencia_ausente`. Outro erro
   propaga (falha no startup, visível no Cloud Run).

### Mapa porta → contratos §4 (métricas e simulação do 001)

| Método de `FinancialComputations` | Função esperada do 001 |
|---|---|
| `perfil_financeiro`, `capacidade_poupanca`, `oportunidades_corte`, `dividas_e_parcelas`, `resumo_mes`, `referencia_coorte` | `metricas.<mesmo nome>` sobre as linhas do repositório |
| `simular_objetivo` (prazo) | `simulacao.aporte_para_prazo` |
| `simular_objetivo` (aporte) | `simulacao.prazo_para_meta` (prazo > 360 → `DomainError(PRAZO_IMPLAUSIVEL)`) |
| `comparar_cenarios` | `simulacao.gerar_cenarios` |

## Troca após o merge do 001 (um arquivo)

Arquivo: `mcp_server/bussola_mcp/ferramentas/computations.py`.

1. Criar a classe `DomainComputations(repository)` no mesmo arquivo, que
   implementa `FinancialComputations` chamando `metricas.*` e `simulacao.*`
   (tabela acima) e converte as exceções de domínio do 001 em `DomainError`
   (`DADOS_INSUFICIENTES`, `PRAZO_IMPLAUSIVEL`).
2. Em `build_computations(repository, fixtures_dir)`, devolver
   `DomainComputations(repository)` no lugar de `GoldenFixtureComputations(...)`.

Nada muda em `server.py`, nos módulos de ferramenta nem nos testes:

- os testes que passam pela fábrica comparam com os golden **oficiais**
  (`test_contrato_golden.py`, `test_http_servidor.py`), que o 001 precisa
  reproduzir, ou só conferem regras válidas para qualquer adaptador (escopo,
  varredura, schema, busca);
- os testes das regras próprias do adaptador provisório (D-04 a D-06: corte
  intermediário, entrada não canônica, controle sem golden, corte < 202506)
  usam `apoio_ferramentas.deps_golden()`, que injeta `GoldenFixtureComputations`
  explicitamente, e seguem verdes;
- `test_simulacao_coerencia.py` e `test_bq_ferramentas.py` passam a rodar
  (hoje são `importorskip`).

Opcional, num PR seguinte: apagar `golden_adapter.py`, `deps_golden`,
`test_golden_adapter.py` e os testes marcados "Decisão D-04/D-05/D-06".

## Após o merge do 002

Nenhuma mudança de código. Com `BUSSOLA_FAKES` desligado, a fábrica passa a
importar `bussola_mcp.rag.criar_buscador(RAG_BACKEND)` e o aviso
`dependencia_ausente` some. `test_fabrica_dependencias.py` já cobre esse caminho com um
módulo `bussola_mcp.rag` injetado.

## Riscos e decisões

- **R-01:** assinatura real de `RepositorioBigQuery` pode diferir (`modo=`
  nomeado). Mitigação: a chamada fica isolada em `_real_repository()`.
- **R-02:** `referencia_coorte` não tem coluna de mês; o corte não se aplica.
  `fonte.periodo` = primeiro mês do cliente → corte. Registrado para o 001.
  No adaptador de golden não há golden dessa ferramenta: ele só consulta as
  linhas de `repository.referencia_coorte(faixa)` com a `faixa_renda` de
  `usuarios.json` (busca sem acento e sem caixa pela `macro`, sem cálculo).
- **R-03:** o 000 publicou 8 ferramentas; o agente lista 8
  (`FERRAMENTAS_MCP`). O servidor expõe 9; o filtro do agente decide quais usa.
