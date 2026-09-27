# Requirement Traceability

Caminhos de teste relativos a `agent/tests/acompanhamento/`, salvo indicação.

| Requirement | Source | Feature | Spec | Plan | Task | Test | Status |
|---|---|---|---|---|---|---|---|
| FR-001 `avancar_mes` livre: escopo, plano, fim do replay, +1 mês via `chamar_ferramenta` | 006 §3.1; AC-01 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T010, T020, T024 | test_acomp_core.py::test_next_month_turns_the_year; test_acomp_tools.py::test_advance_reveals_the_next_month_and_detects_the_deviation, ::test_invalid_scope_is_rejected_before_any_call, ::test_mcp_errors_pass_through_and_keep_the_month; test_acomp_adapters.py::test_the_default_gateway_goes_through_mcp_conexao | TESTED |
| FR-002 Corte temporal: nada acima do novo `ate_anomes` | 006 §3.1, §7; AC-01 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T024, T030 | test_acomp_tools.py::test_a_summary_beyond_the_cut_is_refused, ::test_envelopes_never_leak_sql_project_or_future_periods; test_acomp_routes.py::test_simulation_after_the_cut_is_discarded; test_acomp_runner.py::test_no_tool_response_reveals_a_month_after_the_cut; test_acomp_adapters.py::test_scope_is_forced_from_the_state_by_mcp_conexao | TESTED (corte do `perfil_financeiro` real: reverificar com 003/004) |
| FR-003 `desvio.py` puro, faixa de 10% com limite incluído | 006 §3.2; AC-02; AC-05 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T011, T014 | test_acomp_core.py::test_deviation_status_uses_ten_percent_band, ::test_deviation_values_follow_the_contract_names, ::test_negative_actual_is_a_deviation | TESTED |
| FR-004 Categoria do desvio contra a linha de base guardada | 006 §3.2; AC-02 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T011, T024 | test_acomp_core.py::test_baseline_counts_months_without_data_in_the_denominator, ::test_category_is_the_largest_positive_increase; test_acomp_tools.py::test_the_baseline_is_fetched_once_per_lineage, ::test_a_baseline_month_without_data_counts_as_zero, ::test_a_failed_baseline_month_leaves_the_month_without_category | TESTED |
| FR-005 Progresso: acumulado, restante, percentual, meses | 006 §3.3; AC-05 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T010, T012, T014 | test_acomp_core.py::test_accumulated_ignores_negative_months, ::test_progress_after_three_months, ::test_progress_without_months_and_after_the_goal | TESTED |
| FR-006 Rotas A/B só no desvio, via `simular_objetivo` com fallback | 006 §3.4; AC-03 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T013, T014 | test_acomp_routes.py (10 testes); test_acomp_tools.py::test_months_without_deviation_have_no_routes | TESTED (fallback local em uso até o 003 real) |
| FR-007 `ajustar_plano` sensível, guarda local de consentimento | 006 §3.5; AC-03; AC-05 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T025, T028 | test_acomp_tools.py::test_adjust_is_blocked_without_consent, ::test_the_governance_gate_replaces_the_local_guard, ::test_adjust_adopts_route_a_and_the_next_month_follows_it, ::test_ambiguous_or_invented_routes_are_refused; test_acomp_runner.py::test_the_consent_gate_blocks_ajustar_plano_without_consent, ::test_the_local_guard_blocks_ajustar_plano_while_005_is_absent; ::test_replay_conversation_from_june_to_september (consentimento real do 005) | TESTED |
| FR-008 `status_plano` livre no formato do front | 006 §3.3; front `eventos-agente.md` §3 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T026, T028 | test_acomp_tools.py::test_status_after_three_months_follows_the_lineage, ::test_status_does_not_advance_the_month, ::test_status_without_plan, ::test_envelopes_carry_every_field_the_front_reads | TESTED |
| FR-009 Persistência pela porta `RegistroApp` (acompanhamento, planos, eventos) | 006 §3.5; AC-04 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T020, T023 | test_acomp_adapters.py::test_advance_month_through_the_real_adapter, ::test_registry_port_rejects_objects_that_are_not_a_registry; test_acomp_tools.py::test_registry_failures_do_not_break_the_month, ::test_adjust_keeps_the_current_plan_when_storage_fails; test_acomp_adapters.py::test_default_registry_is_the_process_registry_shared_with_005; eval: auditoria em resultado.md | TESTED (registro do processo compartilhado com o 005; BigQuery com `BUSSOLA_FAKES=FALSE`) |
| FR-010 State: `ate_anomes`, `ACOMPANHAR`, `acompanhamento`, `acompanhamento_contexto` | contratos §6; 006 §3.1 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T002, T022, T024 | test_acomp_plan_context.py (8 testes); test_acomp_runner.py::test_replay_conversation_from_june_to_september | TESTED |
| FR-011 Instruções nas ordens 70–89, pt-BR, três blocos | 006 §3.6 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T027 | test_acomp_registration.py::test_instructions_use_only_the_reserved_orders; test_acomp_runner.py::test_the_model_sees_the_006_instructions_and_the_three_tools | TESTED |
| FR-012 Registro idempotente por `extensoes`, sem editar `agent.py` | contratos §6; 006 §4 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T027, T028 | test_acomp_registration.py (6 testes); test_acomp_runner.py::test_hello_root_agent_exposes_the_006_tools_and_instructions; governanca/test_wiring.py::test_real_agent_loads_the_governance_package | TESTED (com o `agent.py` do 004) |
| FR-013 Logs JSON só com campos de §9 | contratos §9 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T023 | test_acomp_tools.py::test_logs_carry_only_the_allowed_fields | TESTED |
| FR-014 Eval offline 202506 → 202509 (implementado até 202512) | 006 §3.7; AC-06 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T031, T032 | test_acomp_eval.py (3 testes); `make eval-acompanhamento` → eval/acompanhamento/resultado.md (51/51) | TESTED |
| FR-015 Unidade + integração offline (`InMemoryRunner` + LLM roteirizado + MCP fake) | 006 §6; AC-05 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T014, T028, T030, T040 | test_acomp_runner.py (8 testes); `make test` | TESTED |
| FR-016 Testes do 000 continuam sem extensões com o pacote real presente | contratos §6 | acompanhamento-replay | specs/006-acompanhamento-replay/spec.md | specs/006-acompanhamento-replay/plan.md | T001 | agent/tests/contrato/test_extensoes.py com a fixture `extensoes_reais_ocultas` (agent/tests/conftest.py) | TESTED |

## Critérios de aceite (§6 do ciclo)

| AC | Evidência | Status |
|---|---|---|
| AC-01 corte 202506 → 202507, teste de corte temporal | FR-001, FR-002 | TESTED |
| AC-02 planejado × realizado com categoria | FR-003, FR-004; eval 202507 Viagens, 202512 Outros gastos | TESTED |
| AC-03 rotas no desvio e consentimento antes do ajuste | FR-006, FR-007 (consentimento e gate reais do 005) | TESTED |
| AC-04 acompanhamento, planos e auditoria gravados | FR-009 (registro do processo, `RegistroEmMemoria` nos testes) | TESTED com fakes |
| AC-05 testes sem LLM | FR-003, FR-005, FR-007, FR-015 | TESTED |
| AC-06 eval executado | FR-014, eval/acompanhamento/resultado.md | TESTED |

## Integração em `main` (006 §8)

Integrado sobre 001, 003, 004 e 005 em `main`:

- **004**: o arnês (`fakes.build_conversation`) monta o agente como o
  `root_agent` (prompt base, ferramentas locais, extensões e os 4 agregados);
  escopo no `before_tool` 10 e verificação de números no `after_model` 50
  rodam nos testes de conversa e no eval.
- **005**: `solicitar_consentimento`, leitura do "sim" e gate reais; o
  catálogo já rotula `ajustar_plano`. A porta de registro do 006 usa
  `persistencia_bq.default_registry()`, o mesmo registro do processo do 005
  (`RegistroBigQuery` em produção). As simulações do 004/005 saíram dos fakes.
  A guarda local do `ajustar_plano` segue coberta com o 005 fora de
  `sys.modules`.
- **003**: o eval ainda usa as regras do mock (`simular_objetivo` devolve o
  golden do corte, então as rotas usam a estimativa local). Pendente: roteiro
  202506 → 202508 contra o MCP real local, no ensaio da demo (007).
- **001**: fixtures v1; se `make fixtures` mudar os números, rode de novo o
  eval.
