# Requirement Traceability

Testes em `agent/tests/governanca/` (abreviado `tg/`). `make test` roda todos,
exceto `bq`; `make test-bq` roda `tg/test_persistencia_bq_real.py`.

| Requirement | Source | Feature | Spec | Plan | Task | Test | Status |
|---|---|---|---|---|---|---|---|
| FR-001 Catálogo livre/sensível, desconhecida = sensível | 005 §3.1; §6 item 1 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T012 | tg/test_catalog.py | TESTED |
| FR-002 solicitar_consentimento | 005 §3.2; contratos §6; eventos-agente (008) | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T021 | tg/test_consent.py; tg/test_flow.py | TESTED |
| FR-003 Analisador sim/não (ambíguos e negações) | 005 §3.2, §10; §6 item 5 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T020 | tg/test_consent.py (tabela do parser) | TESTED |
| FR-004 Leitura do consentimento (before_model 20) | 005 §3.2; §6 item 2 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T022 | tg/test_consent.py; tg/test_flow.py | TESTED |
| FR-005 Gate de uso único (before_tool 20) | 005 §3.2; §6 itens 2 e 5 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T023 | tg/test_consent.py (gate, paralelo); tg/test_flow.py | TESTED |
| FR-006 Ações simuladas (compartilhar_dados sempre recusada) | 005 §3.3; §6 item 5 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T024 | tg/test_actions.py; tg/test_flow.py | TESTED |
| FR-007 RegistroBigQuery + seleção por BUSSOLA_FAKES | 005 §3.4; §6 item 3; contratos §3, §7 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T011, T053 | tg/test_persistencia_bq.py; tg/test_persistencia_bq_real.py (bq, bussola_app_dev) | TESTED |
| FR-008 Auditoria minimizada (before/after_tool 90) | 005 §3.4; §6 item 3 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T030 | tg/test_audit.py; tg/test_flow.py | TESTED |
| FR-009 Guardrail de entrada (before_model 10) | 005 §3.5; §6 item 4 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T040, T041 | tg/test_guardrails.py; tg/test_model_armor.py; tg/test_flow.py | TESTED |
| FR-010 Guardrail de saída + chips (after_model 10) | 005 §3.5; §6 item 4 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T040, T041 | tg/test_guardrails.py (inclui SSE); tg/test_flow.py | TESTED |
| FR-011 Instruções 50–69 | 005 §3.2; contratos §6 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T025, T050 | tg/test_wiring.py | TESTED |
| FR-012 Eval de segurança determinístico | 005 §3.6; §6 item 6; decisão D1 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T060, T061 | tg/test_eval_seguranca.py; eval/seguranca/resultado.md (16/16) | TESTED |
| FR-013 Logs só com campos de §9 | contratos §9; constituição V | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T030, T040 | tg/test_audit.py (minimização); logging_json filtra campos (contrato 000) | TESTED |
| SC-001 Nenhuma ação sensível sem "sim" | 005 §6 item 2; decisão D2 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T052 | tg/test_flow.py (InMemoryRunner + ScriptedLlm) | TESTED |
| SC-002 8 casos do eval | 005 §3.6, §6 item 6 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T060 | make eval-seguranca; tg/test_eval_seguranca.py | TESTED |
| SC-003 make lint / test / test-bq verdes | 005 §6; CLAUDE.md | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T062, T053 | make lint; make test; make test-bq | TESTED |
| Registro sem editar agent.py | 005 §3; contratos §6 | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T050 | tg/test_wiring.py (root_agent real) | TESTED (rever após o merge do 004) |
| Contrato: isolamento dos testes do 000 + campos opcionais §6 | contratos §6; constituição X | consentimento-governanca | specs/005-consentimento-governanca/spec.md | specs/005-consentimento-governanca/plan.md | T003 | agent/tests/contrato/test_extensoes.py; agent/tests/contrato/test_agent_hello.py | TESTED (PR `contracts:`) |
