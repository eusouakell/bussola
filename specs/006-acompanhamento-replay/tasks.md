# Tasks: Acompanhamento com replay temporal

**Input**: [spec.md](spec.md) e [plan.md](plan.md).

**Tests**: obrigatórios (AC-05). Todos offline em `make test`.

## Format: [ID] [P?] [Story] Descrição

## Phase 1: Contratos (commits separados)

- [x] T001 [US1] Isolar os pacotes de extensão reais nos testes: conftest,
  marcador `extensoes_reais` e nota em contratos §6 (FR-016).
- [x] T002 [US1] Documentar a chave `acompanhamento_contexto` em contratos
  §6 (FR-010).

## Phase 2: Núcleo puro

- [x] T010 [P] [US1] `money.py` e `periods.py` (FR-001, FR-005).
- [x] T011 [P] [US1] `desvio.py`: tolerância, status, linha de base e
  categoria (FR-003, FR-004).
- [x] T012 [P] [US1] `progress.py`: acumulado, restante, percentual e meses
  (FR-005).
- [x] T013 [P] [US2] `routes.py`: rotas A e B, validação da resposta MCP e
  fallback (FR-006).
- [x] T014 [US1] Testes de unidade de T010–T013.

**Checkpoint**: regras puras verdes.

## Phase 3: Portas, plano ativo e ferramentas

- [x] T020 [US1] `ports.py`: gateway MCP sobre `chamar_ferramenta` e porta
  do registro (FR-009).
- [x] T021 [US1] `fakes.py`: `FixtureMcp` a partir de `contracts/fixtures`,
  gateway fake, `ScriptedLlm`, jornada simulada do 004/005 e o harness
  `Conversation` compartilhado com o eval.
- [x] T022 [US1] `plan_context.py`: resolução do plano ativo (FR-007,
  FR-008).
- [x] T023 [US1] `audit.py` e `envelopes.py`: eventos, logs com campos de
  §9 e mensagens de erro pt-BR (FR-009, FR-013).
- [x] T024 [US1] `avancar_mes` (FR-001, FR-002, FR-010).
- [x] T025 [US2] `ajustar_plano` com guarda de consentimento (FR-007).
- [x] T026 [US3] `status_plano` (FR-008).
- [x] T027 [US1] `instructions.py` e `__init__.register()` (FR-011, FR-012).
- [x] T028 Testes das ferramentas, do adaptador (escopo) e do registro.

**Checkpoint**: ferramentas verdes com fakes.

## Phase 4: Integração e eval

- [x] T030 [US1] [US2] Integração `InMemoryRunner` de 202506 a 202509, com
  corte temporal e fidelidade dos números (FR-002, FR-015).
- [x] T031 [US1] [US2] Eval offline de 202506 a 202512 (cobre o mínimo até
  202509) e `make eval-acompanhamento` (FR-014).
- [x] T032 `resultado.md` e `RESULTADOS.md`.

## Phase 5: Fechamento

- [x] T040 `make lint` e `make test` verdes.
- [x] T041 `traceability.md`.
