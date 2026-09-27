# Tasks: MCP server de dados e conhecimento

**Input**: `specs/003-mcp-dados-conhecimento/` (spec.md, plan.md)

**Tests**: obrigatórios (constituição IX), unitários e de integração, todos
offline no `make test`. Os `@pytest.mark.bq` ficam fora.

## Format: `[ID] [P?] [Story] Descrição`

- `[P]`: pode rodar em paralelo (arquivos diferentes, sem dependência pendente).
- `[FORA]`: arquivo fora da propriedade do 003 (commit separado, sinalizado).

## Phase 1: Setup

- [x] T001 `spec.md` com as decisões D-01 a D-09 (9 ferramentas, `PRAZO_IMPLAUSIVEL`, porta de cálculo, corte, simulação canônica, escopo do controle, testes do mock, cliente de teste, nomes)
- [x] T002 `plan.md`: ports & adapters, fábrica de dependências, mapa porta → contratos §4, troca pós-001 e pós-002

## Phase 2: Foundational (portas e adaptadores)

- [x] T003 `ferramentas/ports.py`: `Computation`, `DomainError`, `BackendUnavailable`, `FinancialComputations`, `ToolDependencies` (FR-007)
- [x] T004 [P] `ferramentas/fixture_backends.py`: `FixtureRepository` e `FixtureSearcher` sobre os fakes, com `INDISPONIVEL` para fixture ausente ou inválida (FR-002, FR-005)
- [x] T005 [P] `ferramentas/golden_adapter.py`: `GoldenFixtureComputations` provisório (D-03 a D-06), sem lógica de métrica nem de simulação
- [x] T006 `ferramentas/computations.py`: `build_computations()`, ponto único de troca pós-001 (FR-011)
- [x] T007 `ferramentas/base.py`: `ToolRunner` (validação, precedência dos códigos, envelope com `fonte`, log `ferramenta_chamada`) e `is_implausible_term` (FR-005, FR-006, FR-009)
- [x] T008 [P] `ferramentas/registry.py`: `TOOL_ANNOTATIONS` read-only e idempotente (FR-003)

## Phase 3: User Story 1 - números do cliente com origem (P1)

- [x] T009 [US1] Módulos `perfil_financeiro`, `capacidade_poupanca`, `oportunidades_corte`, `dividas_e_parcelas`, `simular_objetivo`, `comparar_cenarios`, `resumo_mes`, `referencia_coorte` com assinaturas de §5 e descrições em pt-BR (FR-003, FR-004)
- [x] T010 [US1] `ferramentas/__init__.py`: `TOOL_MODULES` na ordem de `FERRAMENTAS` e `register_all` (FR-003)
- [x] T011 [US1] `server.py`: `create_server`, `build_dependencies` (fakes, real com import sob demanda e fallback `dependencia_ausente`), CLI `--host --port --fixtures`, `$PORT` (FR-001, FR-002)
- [x] T012 [US1] `server.criar_servidor`: alias da API do mock do 000 para os ciclos em paralelo

## Phase 4: User Story 2 - conhecimento geral (P1)

- [x] T013 [US2] Módulo `buscar_contexto_financeiro`: buscador só com `pergunta`, `k`, `tema`; `fonte.tabelas=[]`; avisos fixos (FR-008)

## Phase 5: Testes

- [x] T014 [P] `tests/ferramentas/apoio_ferramentas.py`: sessão MCP em memória, `chamar()`, espiões e dublês das portas, `deps_golden()`
- [x] T015 [P] `test_schema_ferramentas.py`: `list_tools` ↔ §5 (nomes, tipos, padrões, sem restrição de faixa, anotações) (FR-003, FR-004)
- [x] T016 [P] `test_contrato_golden.py`: golden × corte, `resumo_mes` dos 12 meses, §7, `top_n`, `dados` e `fonte` completos (FR-006, SC-002)
- [x] T017 [P] `test_erros_ferramentas.py`: 5 códigos × ferramentas aplicáveis, precedência, sem vazamento (FR-005, SC-003)
- [x] T018 [P] `test_escopo_ferramentas.py`: id de controle, espião do repositório e do buscador (FR-007, FR-008)
- [x] T019 [P] `test_busca_conhecimento.py`: tema, `k`, lista vazia, `fonte.url` de produto, corpus oficial (FR-008)
- [x] T020 [P] `test_seguranca_saidas.py`: varredura `SELECT` / `batalha-time-07` / `googleapis` / `Bearer` em saídas, schema e logs (FR-010, SC-004)
- [x] T021 [P] `test_logs_ferramentas.py`: campos de §9, nunca pergunta, textos ou ids (FR-009)
- [x] T022 [P] `test_runner_ferramentas.py` e `test_golden_adapter.py` (unitários)
- [x] T023 [P] `test_fabrica_dependencias.py`: fakes, modo real com módulos injetados, fallback, dependência interna ausente, CLI (FR-002, FR-011)
- [x] T024 [P] `test_http_servidor.py`: subprocess em streamable HTTP e equivalente a `make mcp` (FR-001)
- [x] T025 [P] `test_simulacao_coerencia.py`: §7 contra `simulacao.aporte_para_prazo` (pulado até o 001)
- [x] T026 [P] `test_bq_ferramentas.py`: `@pytest.mark.bq`, modos `query` e `memoria` (pulado até o 001) (FR-012)
- [x] T027 Testes das regras D-04 a D-06 fixados no adaptador (`deps_golden`), para a troca pós-001 não quebrar a suíte

## Phase 6: Integração e polimento

- [x] T028 [FORA] Remover `mcp_server/tests/contrato/test_mock_servidor.py` e `test_mock_http.py` (D-07); `agent/tests/contrato/test_mcp_conexao.py` espera 9 ferramentas (D-01)
- [x] T029 `make lint` e `make test` verdes (SC-001)
- [x] T030 `traceability.md`

## Pendentes fora deste ciclo

- [ ] T031 Publicar a revisão `c003` (`--no-traffic`): orquestrador
- [x] T032 Troca pós-001 em `ferramentas/computations.py` (`DomainComputations`) e `make test-bq` real: goldens v1 reproduzidos nos modos `query` e `memoria`
