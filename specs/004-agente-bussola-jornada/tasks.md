# Tarefas 004: Agente Bússola e jornada

Legenda: `[x]` feito, `[ ]` pendente. Commits pequenos (`agent:`, `eval:`,
`004:`).

## Fase 0: bug de produção (commit isolado, primeiro)

- [x] T000 `resilient_model.py`: `NonStreamingModel` + `build_fallback_chain`
  + `capacity_error_response`; testes SSE com `InMemoryRunner`
  (`agent/tests/jornada/test_resilient_model.py`).

## Fase 1: spec

- [x] T001 `spec.md`, `plan.md`, `tasks.md`.

## Fase 2: núcleo da jornada

- [x] T010 `jornada/state_machine.py` (FR-007) + testes.
- [x] T011 `jornada/tool_results.py` (extração de envelope) + testes.
- [x] T012 `jornada/tools.py`: `registrar_objetivo`, `escolher_cenario`
  (FR-009, FR-010) + testes.
- [x] T013 `jornada/progress.py`: aplica resultado ao state, logs
  `estado_alterado` (FR-008, FR-013) + testes.

## Fase 3: escopo e fontes

- [x] T020 `escopo.py`: `initialize_session` (FR-011), `enforce_scope`
  (FR-012), `record_tool_result` (FR-013) + testes (controle → âncora).

## Fase 4: prompts

- [x] T030 `prompts/`: base pt-BR, estados, regras, catálogo embutido
  (FR-004, FR-005, FR-006) + testes (render, catálogo = contrato, recusas).

## Fase 5: resposta final

- [x] T040 `jornada/number_check.py` (FR-014) + testes.
- [x] T041 `jornada/annotations.py` (FR-016) + testes.
- [x] T042 `jornada/respostas_rapidas.py` por jornada (FR-015) + testes.

## Fase 6: agente

- [x] T050 `agent.py` da jornada (FR-001, FR-002, FR-003);
  `tests/contrato/test_agent_hello.py` atualizado.
- [x] T051 Integração roteirizada OBJETIVO → ORIENTAR → AGIR contra o mock
  MCP real (AC-07); chamadas paralelas fora de ordem (D-11).

## Fase 7: eval e rastreabilidade

- [ ] T060 `eval/agente/perguntas.yaml` + `rodar_eval.py` (offline e ao vivo),
  alvo no `Makefile` (FR-017).
- [ ] T061 Rodar eval offline e ao vivo; `eval/agente/RESULTADOS.md`.
- [ ] T062 `traceability.md`; `make lint` e `make test` verdes.
