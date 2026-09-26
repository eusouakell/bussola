# Tasks: Fundação e contratos

**Input**: `specs/000-fundacao-contratos/` (plan.md, spec.md, research.md,
data-model.md, contracts/)

**Tests**: obrigatórios (constituição IX). O modo de execução é multiagente:
os blocos marcados `[A:<trilha>]` rodam em paralelo por subagentes, na mesma
worktree e com arquivos disjuntos, depois da Phase 2.

## Format: `[ID] [P?] [Story] Descrição`

- `[P]`: pode rodar em paralelo (arquivos diferentes, sem dependência
  pendente).
- `[A:mcp|agente|dados|deploy]`: subagente responsável.
- `[CRED]`: depende de credenciais GCP do integrante. Fica pendente até
  existir ADC.

## Phase 1: Setup

- [x] T000 Spec Kit 0.8.17 inicializado (`.specify/`, `.claude/skills/speckit-*`) e constituição v1.0.0 com os princípios de 000 §3.1 (FR-001, AC-01). Feito antes do plano
- [x] T001 Acrescentar `.adk/`, `*.db` e `.uv-cache/` ao `.gitignore`, preservando o conteúdo (FR-003)
- [x] T002 Escrever `CLAUDE.md` com comandos, modo fake, contratos, propriedade, proibições e fluxo de PR (FR-002, AC-01)
- [x] T003 [P] Criar `mcp_server/pyproject.toml` + `.python-version` + `uv.lock`: `mcp>=1.24,<2`, pydantic, google-cloud-bigquery, numpy, uvicorn; dev: pytest, pytest-asyncio, ruff (FR-005)
- [x] T004 [P] Criar `agent/pyproject.toml` + `.python-version` + `uv.lock`: `google-adk[mcp]`, `mcp>=1.24,<2`, google-genai, google-auth, pydantic; dev: pytest, pytest-asyncio, ruff (FR-005)
- [x] T005 Criar `Makefile` com `test lint mcp agent fixtures test-bq` e carga opcional de `.env` (FR-004)

## Phase 2: Foundational (bloqueia os subagentes)

- [x] T006 [P] DDL `contracts/bigquery/bussola_dados.sql`, `bussola_rag.sql`, `bussola_app.sql` idêntico a contratos §3 (FR-006)
- [x] T007 [P] `contracts/env.example` com as variáveis de §7, sem segredos (FR-007)
- [x] T008 `mcp_server/bussola_mcp/contratos.py`: linhas §3, entradas com validação, `dados` §5, envelopes, `CodigoErro`, `RegrasCenario`, `FERRAMENTAS` (FR-008)
- [x] T009 `mcp_server/bussola_mcp/__init__.py` e `agent/bussola_agent/__init__.py` (pacotes vazios)

**Checkpoint**: `uv sync` nos dois projetos e `contratos.py` importável. A
partir daqui, os subagentes podem começar.

## Phase 3: US1: ciclo isolado sobre contratos e fakes (P1) 🎯 MVP

- [x] T010 [P] [US1] [A:mcp] `mcp_server/tests/conftest.py`: `BUSSOLA_FAKES=TRUE`, guarda de rede só para loopback, fixture `fixtures_sinteticas(tmp_path)`
- [x] T011 [P] [US1] [A:mcp] Teste `mcp_server/tests/contrato/test_contratos.py`: validação das entradas (UUID, faixas, exatamente um de prazo/aporte, `pergunta` ≤ 500, `resumo_mes` com `anomes ≤ ate_anomes`)
- [x] T012 [P] [US1] [A:mcp] Teste `mcp_server/tests/contrato/test_ddl_modelos.py`: DDL `bussola_dados` e `bussola_rag` ↔ modelos (nome, tipo, nulidade) (AC-03, TS-01)
- [x] T013 [P] [US1] [A:mcp] `mcp_server/bussola_mcp/dominio/interfaces.py` (Protocols §4, `runtime_checkable`) (FR-009)
- [x] T014 [US1] [A:mcp] `mcp_server/bussola_mcp/dominio/fakes.py`: `RepositorioFake` e `BuscadorFake` sobre o diretório de fixtures, com escopo e tempo (FR-009, FR-010)
- [x] T015 [US1] [A:mcp] Teste `mcp_server/tests/contrato/test_fakes.py`: TS-05, `desde_anomes`, filtro do buscador (coorte, `anomes` nulo, ordenação), `isinstance` com os Protocols
- [x] T016 [P] [US1] [A:mcp] `mcp_server/bussola_mcp/logging_json.py` + teste `test_logging_json.py` (FR-011)
- [x] T017 [P] [US1] [A:agente] `agent/bussola_agent/logging_json.py` + teste (FR-011)
- [x] T018 [P] [US1] [A:agente] `agent/tests/conftest.py` (guarda de rede, `limpar()` dos registros)
- [x] T019 [US1] [A:agente] Teste `agent/tests/contrato/test_ddl_modelos.py`: DDL `bussola_app` ↔ modelos de `persistencia.py` (AC-03)

## Phase 4: US2: MCP mock (P1)

- [x] T020 [US2] [A:mcp] `mcp_server/bussola_mcp/server.py`: FastMCP com as 8 ferramentas, validação, regra §8, CLI `--host --port --fixtures`, logs (FR-017, FR-018)
- [x] T021 [US2] [A:mcp] Teste `mcp_server/tests/contrato/test_mock_servidor.py` (em memória): `list_tools` ↔ §5 (nomes, parâmetros, obrigatórios, padrões), TS-02, TS-03, AC-05, controle → `DADOS_INSUFICIENTES`, truncamento, `INDISPONIVEL` sem fixtures
- [x] T022 [US2] [A:mcp] Teste `mcp_server/tests/contrato/test_mock_http.py`: servidor em subprocess via streamable HTTP em `/mcp`, `list_tools` = 8
- [x] T023 [US2] [A:mcp] Teste `mcp_server/tests/contrato/test_fixtures_oficiais.py`: golden ↔ modelos, e os 9 valores de referência a 1% (AC-04). É pulado com motivo quando não há `usuarios.json`

## Phase 5: US3: extensão do agente (P1)

- [x] T024 [P] [US3] [A:agente] `agent/bussola_agent/estado.py` + teste (FR-012)
- [x] T025 [P] [US3] [A:agente] `agent/bussola_agent/callbacks.py` + teste `test_callbacks.py`: 4 fases, ordem crescente, curto-circuito, sync/async, fase inválida (TS-04, AC-08, FR-013)
- [x] T026 [P] [US3] [A:agente] `agent/bussola_agent/extensoes.py` + teste `test_extensoes.py`: pacotes ausentes (AC-09), ordem das instruções, nome duplicado, sensíveis (FR-014)
- [x] T027 [P] [US3] [A:agente] `agent/bussola_agent/persistencia.py` + teste `test_persistencia.py`: `isinstance(RegistroEmMemoria(), RegistroApp)`, round-trip, 12 `TipoEvento` (AC-10)
- [x] T028 [US3] [A:agente] `agent/bussola_agent/mcp_conexao.py` + teste `test_mcp_conexao.py`: `McpToolset` lista 8 ferramentas no mock em subprocess (AC-06), `chamar_ferramenta` força o escopo, `INDISPONIVEL` sem servidor, `header_provider` OIDC com `fetch_id_token` simulado
- [x] T029 [US3] [A:agente] `agent/bussola_agent/agent.py` (hello) + teste `test_agent_hello.py`: `root_agent` importável sem rede, callbacks instalados, `carregar_extensoes` chamada (FR-019)

## Phase 6: US4: fixtures (P2)

- [x] T030 [US4] [A:dados] `data/scripts/gerar_fixtures.py`: SQL de referência parametrizado, funções puras de referência para os golden P0, `resumo_mes` e trechos RAG, validação com `bussola_mcp.contratos`, `--saida` (FR-015, FR-016)
- [x] T031 [US4] [A:dados] Teste `mcp_server/tests/contrato/test_gerar_fixtures.py`: funções puras com linhas sintéticas (métricas, golden válidos, determinismo, sem rede)
- [ ] T032 [US4] [CRED] Rodar `make fixtures` e versionar `contracts/fixtures/` (AC-04)

## Phase 7: US5: plataforma (P2)

- [x] T033 [P] [US5] [A:dados] `data/scripts/aplicar_ddl.py` (idempotente, `--dry-run`, `bussola_app_dev`) + teste do parser (FR-020)
- [x] T034 [P] [US5] [A:deploy] `mcp_server/Dockerfile` + `mcp_server/Dockerfile.dockerignore`, `agent/Dockerfile` + `agent/Dockerfile.dockerignore` (FR-005)
- [x] T035 [P] [US5] [A:deploy] `deploy/build_push.sh`, `deploy/deploy.sh` (FR-022)
- [x] T036 [P] [US5] [A:deploy] `deploy/smoke_modelos.py` (FR-021)
- [x] T037 [P] [US5] [A:deploy] `deploy/iam_datasets.sh`, com simulação por padrão e confirmação digitada (FR-023)
- [ ] T038 [US5] [CRED] Aplicar o DDL duas vezes, rodar o smoke de modelos, build/push/deploy hello e registrar em `modelos.md` e `smoke.md` (AC-11, AC-12, AC-13)
- [ ] T039 [US5] [CRED] Smoke local do agente hello contra o mock e registro em `smoke.md` (AC-07)

## Phase 8: US6: governança e pedidos (P2)

- [x] T040 [P] [US6] `specs/000-fundacao-contratos/pedidos-owner.md`: 4 itens de mestre §16, com status e decisão Plano A/B (FR-024)
- [x] T041 [P] [US6] `specs/000-fundacao-contratos/questoes.md` + correções aditivas em `docs/ciclos/contratos.md` (FR-025)

## Phase 9: Polish e gates

- [x] T042 Integrar os subagentes: `make lint` e `make test` verdes, sem rede
- [x] T043 `modelos.md` e `smoke.md` com o status (pendente de credencial quando for o caso)
- [x] T044 Exportar a rastreabilidade para `specs/000-fundacao-contratos/traceability.md`
- [ ] T045 [HUMANO] Após o merge em `main`, um integrante cria e publica a tag `contratos-v1` (AC-15). Fora do PR

## Dependências

- Phase 1 → Phase 2 → {US1..US5 em paralelo por subagente} → Phase 9.
- US2 (T020) depende de T013/T014 (mesmo subagente, em sequência).
- US3 T028 depende do `server.py` (T020) para o teste AC-06. O subagente
  "agente" usa um servidor mínimo próprio só se o mock ainda não existir; a
  integração final roda com o mock real.
- T031 depende de T030. T032/T038/T039 dependem de credenciais.

## Execução paralela (multiagente)

| Subagente | Tarefas | Arquivos exclusivos |
|---|---|---|
| mcp | T010–T016, T020–T023 | `mcp_server/bussola_mcp/{dominio/*, logging_json.py, server.py}`, `mcp_server/tests/**` exceto `test_gerar_fixtures.py` e `test_aplicar_ddl.py` |
| agente | T017–T019, T024–T029 | `agent/bussola_agent/**` exceto `__init__.py`, `agent/tests/**` |
| dados | T030, T031, T033 | `data/scripts/**`, `mcp_server/tests/contrato/test_gerar_fixtures.py`, `mcp_server/tests/contrato/test_aplicar_ddl.py` |
| deploy | T034–T037 | `*/Dockerfile*`, `deploy/**` |
| principal | T001–T009, T040–T044 | o restante |
