# Requirement Traceability

| Requirement | Source | Feature | Spec | Plan | Task | Test | Status |
|---|---|---|---|---|---|---|---|
| FR-001 Spec Kit + constituição | 000 §3.1; AC-01 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T000 | manual: .specify/ + constituição | DONE |
| FR-002 CLAUDE.md | 000 §3.1; AC-01 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T002 | manual: CLAUDE.md | DONE |
| FR-003 .gitignore preservado | 000 §3.1 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T001 | manual: .gitignore | DONE |
| FR-004 Makefile targets | contratos §2; 000 §3.1 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T005 | make lint; make test | TESTED |
| FR-005 Projetos mcp_server/agent + Dockerfiles | 000 §3.2 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T003, T004, T034 | build local das imagens (smoke.md) | TESTED |
| FR-006 DDL bussola_* | contratos §3; AC-03 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T006 | mcp_server/tests/contrato/test_ddl_modelos.py; agent/tests/contrato/test_ddl_modelos.py | TESTED |
| FR-007 env.example sem segredos | contratos §7 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T007 | manual: sem segredos | DONE |
| FR-008 Modelos Pydantic + envelopes | contratos §3, §5; AC-03 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T008 | mcp_server/tests/contrato/test_contratos.py | TESTED |
| FR-009 Interfaces + fakes | contratos §4 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T013, T014 | mcp_server/tests/contrato/test_fakes.py | TESTED |
| FR-010 Fakes com escopo/tempo | contratos §3, §4; TS-05 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T014, T015 | mcp_server/tests/contrato/test_fakes.py | TESTED |
| FR-011 Logger JSON | contratos §9 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T016, T017 | mcp_server/tests/contrato/test_logging_json.py; agent/tests/contrato/test_logging_json.py | TESTED |
| FR-012 Estado/callbacks/extensões/persistência/conexão MCP | contratos §6 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T024, T027, T028 | agent/tests/contrato/test_estado.py; agent/tests/contrato/test_persistencia.py; agent/tests/contrato/test_mcp_conexao.py | TESTED |
| FR-013 Encadeador de callbacks | contratos §6; AC-08; TS-04 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T025 | agent/tests/contrato/test_callbacks.py | TESTED |
| FR-014 carregar_extensoes tolerante | contratos §6; AC-09 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T026 | agent/tests/contrato/test_extensoes.py | TESTED |
| FR-015 gerar_fixtures.py | 000 §3.4; contratos §8; AC-04 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T030, T031, T032 | mcp_server/tests/contrato/test_gerar_fixtures.py; mcp_server/tests/contrato/test_fixtures_oficiais.py | TESTED |
| FR-016 trechos RAG de exemplo | 000 §3.4; contratos §8 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T030 | mcp_server/tests/contrato/test_gerar_fixtures.py | TESTED |
| FR-017 MCP mock 8 ferramentas | 000 §3.4; contratos §5, §8; AC-05; TS-02 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T020, T021, T022 | mcp_server/tests/contrato/test_mock_servidor.py; mcp_server/tests/contrato/test_mock_http.py | TESTED |
| FR-018 Validação de entrada no mock | contratos §5; AC-05; TS-03 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T020, T021 | mcp_server/tests/contrato/test_mock_servidor.py; mcp_server/tests/contrato/test_contratos.py | TESTED |
| FR-019 Agente hello | 000 §3.4; AC-06; AC-07 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T029, T039 | agent/tests/contrato/test_agent_hello.py; agent/tests/contrato/test_mcp_conexao.py | IMPLEMENTED (AC-07 CRED pendente) |
| FR-020 aplicar_ddl.py idempotente | 000 §3.5; AC-11 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T033, T038 | mcp_server/tests/contrato/test_aplicar_ddl.py | IMPLEMENTED (T038 CRED pendente) |
| FR-021 smoke_modelos.py | 000 §3.5; AC-12 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T036, T038 | smoke.md (offline) | IMPLEMENTED (T038 CRED pendente) |
| FR-022 build_push/deploy | 000 §3.5; AC-13 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T035, T038 | bash -n; smoke.md | IMPLEMENTED (T038 CRED pendente) |
| FR-023 iam_datasets.sh com confirmação | 000 §3.5 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T037 | simulação com stubs (smoke.md) | TESTED |
| FR-024 pedidos-owner.md | mestre §16; AC-14 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T040 | manual: pedidos-owner.md | DONE (envio pela Pessoa B) |
| FR-025 questoes.md | 000 §1.5 | fundacao-contratos | specs/000-fundacao-contratos/spec.md | specs/000-fundacao-contratos/plan.md | T041 | manual: questoes.md | DONE |

