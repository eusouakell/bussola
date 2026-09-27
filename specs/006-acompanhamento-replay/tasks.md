# Tasks: Acompanhamento com replay temporal

**Input**: [spec.md](spec.md) e [plan.md](plan.md).

**Tests**: obrigatórios (AC-05). Todos offline em `make test`.

## Format: [ID] [P?] [Story] Descrição

## Phase 1: Contratos (commits separados)

- [ ] T001 [US1] Isolar os pacotes de extensão reais nos testes: conftest,
  marcador `extensoes_reais` e nota em contratos §6 (FR-016).
- [ ] T002 [US1] Documentar a chave `acompanhamento_contexto` em contratos
  §6 (FR-010).

## Phase 2: Núcleo puro

- [ ] T010 [P] [US1] `money.py` e `periods.py` (FR-001, FR-005).
- [ ] T011 [P] [US1] `desvio.py`: tolerância, status, linha de base e
  categoria (FR-003, FR-004).
- [ ] T012 [P] [US1] `progress.py`: acumulado, restante, percentual e meses
  (FR-005).
- [ ] T013 [P] [US2] `routes.py`: rotas A e B, validação da resposta MCP e
  fallback (FR-006).
- [ ] T014 [US1] Testes de unidade de T010–T013.

**Checkpoint**: regras puras verdes.

## Phase 3: Portas, plano ativo e ferramentas

- [ ] T020 [US1] `ports.py`: gateway MCP sobre `chamar_ferramenta` e porta
  do registro (FR-009).
- [ ] T021 [US1] `fakes.py`: `FixtureMcp` a partir de `contracts/fixtures`,
  gateway fake e `ScriptedLlm`.
- [ ] T022 [US1] `plan_context.py`: resolução do plano ativo (FR-007,
  FR-008).
- [ ] T023 [US1] `audit.py`: eventos e logs com campos de §9 (FR-009,
  FR-013).
- [ ] T024 [US1] `avancar_mes` (FR-001, FR-002, FR-010).
- [ ] T025 [US2] `ajustar_plano` com guarda de consentimento (FR-007).
- [ ] T026 [US3] `status_plano` (FR-008).
- [ ] T027 [US1] `instructions.py` e `__init__.register()` (FR-011, FR-012).
- [ ] T028 Testes das ferramentas, do adaptador (escopo) e do registro.

**Checkpoint**: ferramentas verdes com fakes.

## Phase 4: Integração e eval

- [ ] T030 [US1] [US2] Integração `InMemoryRunner` de 202506 a 202508, com
  corte temporal (FR-002, FR-015).
- [ ] T031 [US1] [US2] Eval offline de 202506 a 202509 e `make
  eval-acompanhamento` (FR-014).
- [ ] T032 `resultado.md` e `RESULTADOS.md`.

## Phase 5: Fechamento

- [ ] T040 `make lint` e `make test` verdes.
- [ ] T041 `traceability.md`.
