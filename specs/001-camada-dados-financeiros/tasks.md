# Tarefas 001: camada de dados financeiros determinística

- **Spec:** [spec.md](./spec.md). **Plano:** [plan.md](./plan.md).
- **Legenda:** `[P]` = paralelizável; `[x]` = concluída.
- **Rastreio:** requisitos (FR/AC/TS) em [traceability.md](./traceability.md).

## Fase 1: contratos e tabelas (workstream `sql`)

- [x] T001 `contracts:` tabela `users` de personas (DDL, `UserPersona`, fixture, contratos §3).
- [x] T002 SQL das 7 tabelas + `users` em `data/sql/`, com `TRUNCATE`+`INSERT` em
  transação (D-01) e seed de `categorias` (D-06). → FR-001..FR-007
- [x] T003 `data/scripts/build_dados.py`: DDL idempotente, etapas, `--dataset` restrito,
  `--dry-run`, `--somente-validar` e 13 validações pós-build. → FR-008
- [x] T004 Testes offline do build (`tests/dados/test_build_dados.py`). → FR-008
- [x] T005 Build real em `bussola_dados` e marco "tabelas v1" em `marcos.md`. → FR-017, AC-07

## Fase 2: domínio (workstream `simulacao`)

- [ ] T006 [P] `dominio/simulacao.py`: funções puras do §4, resultados imutáveis e
  auxiliares de estatística e texto. → FR-013..FR-015
- [ ] T007 [P] Testes de simulação: casos conhecidos, bordas e sem divisão por zero.
  → AC-02, TS-03, TS-04
- [ ] T008 `dominio/metricas.py`: uma função por ferramenta de dados, com validação,
  corte temporal, avisos e `build_envelope`. → FR-010..FR-012
- [ ] T009 Testes de métricas sobre fixtures sintéticas: corte 202506 por métrica,
  controle isolado e injeção rejeitada. → AC-04, AC-05, TS-05
- [ ] T010 `dominio/repositorio_bq.py`: modos `query` e `memoria`, validação antes do
  cliente, ordem estável e filtro de recorrência até o corte (D-05). → FR-009, FR-010
- [ ] T011 Testes do repositório com cliente BigQuery falso: SQL constante e
  parametrizado, `query` == `memoria`, injeção antes do cliente. → AC-04, AC-06

## Fase 3: fixtures v1 e verificação real

- [ ] T012 `build_dados.py --fixtures SAIDA` e alvo `make fixtures-v1`, com testes
  offline. → FR-016
- [ ] T013 `contracts:` fixtures v1 a partir de `bussola_dados` (commit separado),
  com a nota em contratos §8. → FR-016, AC-07
- [ ] T014 Teste de consistência offline: goldens v1 == `metricas.*` sobre
  `RepositorioFake(contracts/fixtures)`. → FR-011, FR-016
- [ ] T015 `@pytest.mark.bq`: `query` == `memoria` (âncora e controle) e âncora a 1%
  do §8. → AC-03, AC-06, TS-01, TS-02
- [ ] T016 `perguntas-ancora.md` (202506 e 202512). → AC-01, FR-018
- [ ] T017 `make lint`, `make test` e `make test-bq`; `traceability.md`. → todos
