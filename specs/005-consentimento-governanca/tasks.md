# Tasks: Consentimento, governança e auditoria

**Input**: `specs/005-consentimento-governanca/` (spec.md, plan.md)

**Tests**: obrigatórios (constituição IX). Execução sequencial numa única
sessão.

## Phase 1: Setup

- [x] T001 Dependências: `google-cloud-bigquery`, `httpx` e `pyyaml` (dev) em `agent/pyproject.toml` + `uv.lock`
- [x] T002 spec.md, plan.md e tasks.md
- [x] T003 `contracts:` isolar os testes de contrato das extensões reais (`criar_extensao` com prioridade, fixture `sem_extensoes`) e documentar os campos opcionais da entrada de consentimento em contratos §6

## Phase 2: Fundação

- [x] T010 `governanca/clock.py`, `envelope.py`, `services.py` (registro, relógio e screener sob demanda)
- [x] T011 `persistencia_bq.py`: `RegistroBigQuery` (porta de cliente, `insert_rows_json`, `obter_plano` parametrizado), `build_registry`, `default_registry` (FR-007)
- [x] T012 `governanca/catalogo.py` + `catalogo_produtos.json` (FR-001)

## Phase 3: US1 consentimento e ações (P1)

- [x] T020 `consent.py`: parser sim/não (FR-003)
- [x] T021 `consent.py`: `solicitar_consentimento` (FR-002)
- [x] T022 `consent.py`: leitura `before_model` 20 (FR-004)
- [x] T023 `consent.py`: gate `before_tool` 20 com consumo (FR-005)
- [x] T024 `acoes.py`: quatro ações simuladas (FR-006)
- [x] T025 `instructions.py` (FR-011)

## Phase 4: US3 auditoria (P1)

- [x] T030 `audit.py`: `ferramenta_chamada`, `estado_alterado`, `sessao_iniciada` (FR-008, FR-013)

## Phase 5: US2 guardrails (P1)

- [x] T040 `guardrails.py`: regras puras de entrada e saída + callbacks (FR-009, FR-010)
- [x] T041 `model_armor.py`: porta, adaptador HTTP e screener com fallback (FR-009, FR-010)

## Phase 6: Integração

- [x] T050 `governanca/__init__.py`: `register()` nas ordens reservadas
- [x] T051 Testes unitários em `agent/tests/governanca/`
- [x] T052 Integração com `InMemoryRunner` + LLM roteirizado (SC-001)
- [x] T053 Testes `bq` em `bussola_app_dev` + `make test-bq`

## Phase 7: Eval e fechamento

- [x] T060 `eval/seguranca/casos.yaml`, `rodar_eval.py` e `resultado.md` (FR-012, SC-002)
- [x] T061 Target `eval-seguranca` no `Makefile` (acréscimo)
- [x] T062 `make lint` + `make test` verdes (SC-003)
- [x] T063 `traceability.md`
