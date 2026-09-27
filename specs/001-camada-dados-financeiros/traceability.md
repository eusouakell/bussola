# Rastreabilidade de requisitos: 001 camada de dados financeiros

Legenda de status:

- `TESTED`: coberto por teste automatizado. `make test` é offline; `make test-bq` só lê
  `bussola_dados`.
- `DONE`: entregue e verificado manualmente.

Os caminhos de teste são relativos a `mcp_server/tests/`.

| Requisito | Origem | Task | Código | Teste | Commit | Status |
|---|---|---|---|---|---|---|
| FR-001 SQL das 7 tabelas + `users` | ciclo §3.1; contratos §3 | T001, T002 | `data/sql/*.sql`; `contracts/bigquery/bussola_dados.sql` | `dados/test_build_dados.py` (placeholder, transação, só o dataset alvo); `contrato/test_ddl_modelos.py` | 3de32c9, 8c6cd3e | TESTED |
| FR-002 `perfil_mensal` (saldos D-03, juros D-04) | ciclo §3.1 | T002 | `data/sql/perfil_mensal.sql` | `dados/test_repositorio_bq_real.py::test_ancora_a_1_por_cento_do_contrato` (bq) | 8c6cd3e | TESTED |
| FR-003 `gastos_categoria` / `entradas_categoria` | ciclo §3.1 | T002 | `data/sql/gastos_categoria.sql`, `entradas_categoria.sql` | validações pós-build (`EXPECTED_CHECKS`); `dados/test_repositorio_bq_real.py` (bq) | 8c6cd3e | TESTED |
| FR-004 `recorrentes` (≥ 3 meses) | ciclo §3.1 | T002, T010 | `data/sql/recorrentes.sql`; filtro D-05 em `repositorio_bq.py` | `dados/test_repositorio_bq_fake.py::test_recorrencia_so_com_meses_ate_o_corte` | 8c6cd3e, 6688fd5 | TESTED |
| FR-005 `parcelas` | ciclo §3.1 | T002 | `data/sql/parcelas.sql` | `dados/test_repositorio_bq_real.py::test_linhas_das_fixtures_v1_iguais_ao_dataset` (bq) | 8c6cd3e | TESTED |
| FR-006 seed `categorias` (98, D-06) | ciclo §3.1 | T002 | `data/sql/seed_categorias.sql` | `dados/test_build_dados.py::test_seed_has_98_unique_pairs_with_valid_cut`; `test_catalogo_e_coorte_publicados` (bq) | 8c6cd3e | TESTED |
| FR-007 `referencia_coorte` (≥ 5 usuários) | ciclo §3.1 (P1) | T002 | `data/sql/referencia_coorte.sql` | `dados/test_repositorio_bq_real.py::test_catalogo_e_coorte_publicados` (bq) | 8c6cd3e | TESTED |
| FR-008 `build_dados.py` (idempotente, `--dataset`, validações, `--fixtures`) | ciclo §3.2 | T003, T004, T012 | `data/scripts/build_dados.py`; `Makefile` (`fixtures-v1`) | `dados/test_build_dados.py`; `dados/test_fixtures_v1.py` | 8c6cd3e, 12e5c9b, 728e4b0 | TESTED |
| FR-009 `RepositorioBigQuery` `query`/`memoria` | ciclo §3.3 | T010, T011 | `bussola_mcp/dominio/repositorio_bq.py` | `dados/test_repositorio_bq_fake.py`; `dados/test_repositorio_bq_real.py` (bq) | 6688fd5, acb890b | TESTED |
| FR-010 UUID v4 e corte validados antes da consulta | ciclo §3.3; constituição | T008, T010 | `metricas.py`, `repositorio_bq.py` | `test_id_invalido_antes_do_cliente`, `test_parametros_invalidos_antes_do_cliente`, `test_corte_fora_do_intervalo_rejeitado` | 04960ec, 6688fd5 | TESTED |
| FR-011 `metricas.py`: uma função por ferramenta + `build_envelope` | ciclo §3.4; contratos §5 | T008, T009, T014 | `bussola_mcp/dominio/metricas.py` | `dados/test_metricas_dominio.py`; `dados/test_fixtures_v1.py::test_golden_versionado_igual_a_metricas_sobre_as_linhas` | 04960ec, 728e4b0 | TESTED |
| FR-012 corte temporal | constituição IV | T009 | `metricas.py` | `dados/test_metricas_dominio.py::test_futuro_nao_muda_o_corte`, `test_periodo_termina_no_corte` | 04960ec | TESTED |
| FR-013 funções puras do §4 | ciclo §3.5; contratos §4 | T006, T007 | `bussola_mcp/dominio/simulacao.py` | `dados/test_simulacao_dominio.py` | 8a58f5a | TESTED |
| FR-014 `RegrasCenario` 40/60/80% | ciclo §3.5 (Q2) | T006 | `simulacao.py` | `test_cenarios_respeitam_regras_informadas`, `test_cenarios_em_ordem_de_aporte_e_prazo` | 8a58f5a | TESTED |
| FR-015 `trade_offs` por regras | ciclo §3.5 | T006 | `simulacao.py` | `dados/test_simulacao_dominio.py` | 8a58f5a | TESTED |
| FR-016 fixtures v1 em commit `contracts:` | ciclo §3.6; contratos §8 | T012, T013, T014 | `contracts/fixtures/`; `build_dados.py --fixtures` | `dados/test_fixtures_v1.py` (export byte a byte, só leitura); `test_metricas_sobre_bigquery_igual_ao_golden_v1` (bq) | 728e4b0, d266474 | TESTED |
| FR-017 marco "tabelas v1" | ciclo §3.2 | T005 | `marcos.md` | build real + 13 validações pós-build | 385b623 | DONE |
| FR-018 `perguntas-ancora.md` | ciclo §3.7 | T016 | `perguntas-ancora.md` | `dados/test_perguntas_ancora.py` | a5a96a8 | TESTED |
| FR-019 sem logs sensíveis, sem SQL/projeto na saída | constituição | T010, T012 | `repositorio_bq.py` (`RepositoryUnavailableError` genérico); `build_dados.py` | `test_falha_da_consulta_vira_indisponivel`; `test_falha_do_bigquery_sai_2_com_mensagem_generica`; `test_meses_faltando_sai_2_sem_gravar`; `contrato/test_politicas_repo.py` | 6688fd5, 728e4b0 | TESTED |

## Critérios de aceite e cenários

| Item | Evidência | Status |
|---|---|---|
| AC-01 perguntas do âncora (202506, 202512) | `perguntas-ancora.md`; `dados/test_perguntas_ancora.py` | TESTED |
| AC-02 simulação: casos conhecidos e bordas | `dados/test_simulacao_dominio.py` (`test_capacidade_sem_sobra_e_inviavel_com_motivo`, `test_prazo_saldo_cobre_alvo_da_zero_viavel`, `test_prazo_acima_do_limite_e_inviavel_mas_volta_o_prazo`) | TESTED |
| AC-03 âncora a 1% do §8 | `dados/test_repositorio_bq_real.py::test_ancora_a_1_por_cento_do_contrato` (9 métricas, bq) | TESTED |
| AC-04 SQL parametrizado; injeção rejeitada antes do BigQuery | `test_sql_executado_e_sempre_o_constante`; `test_id_invalido_antes_do_cliente`; `contrato/test_politicas_repo.py` | TESTED |
| AC-05 corte 202506, um teste por métrica | `dados/test_metricas_dominio.py::test_futuro_nao_muda_o_corte` (parametrizado por ferramenta) | TESTED |
| AC-06 `query` == `memoria` (âncora e controle) | `dados/test_repositorio_bq_real.py::test_query_igual_a_memoria` (bq, 202503/202506/202512); versão offline em `test_repositorio_bq_fake.py` | TESTED |
| AC-07 marco publicado e fixtures v1 em `contracts:` | `marcos.md`; commit d266474 | DONE |
| TS-01 12 meses, sobra ≈ 2.836 | `test_perfil_do_ancora_tem_12_meses`; `test_ancora_a_1_por_cento_do_contrato[sobra]` (bq) | TESTED |
| TS-02 top 3 com Restaurantes, sem aluguel | `test_ts02_oportunidades_top3_inclui_comer_fora_sem_aluguel` (bq); `test_perguntas_1_a_3` | TESTED |
| TS-03 ordem dos cenários | `test_cenarios_em_ordem_de_aporte_e_prazo` | TESTED |
| TS-04 `prazo_para_meta(60000, 0)` | `test_prazo_sem_aporte_nao_divide_por_zero` | TESTED |
| TS-05 controle isolado | `test_controle_isolado_do_ancora`; `test_repositorio_sem_filtro_nao_vaza`; `test_ts05_controle_nao_mistura_linhas_do_ancora` (bq) | TESTED |

## Fixtures v1

- **Como gerar:** `make fixtures-v1`, que roda `build_dados.py --fixtures ../contracts/fixtures`.
  Só lê do BigQuery (`us-central1`) e não toca em `users.json` nem em `rag/`.
- **O que mudou em relação ao conjunto provisório do 000:**
  - `categorias.json`, pelo seed D-06;
  - `perfil_mensal.json`, pelo `saldo_inicial` D-03;
  - os goldens de `oportunidades_corte` e `comparar_cenarios` nos dois cortes.
- **Verificação:**
  - offline, `dados/test_fixtures_v1.py`: golden == `metricas` sobre as linhas, e o
    export reproduz os arquivos;
  - no `make test-bq`, `test_metricas_sobre_bigquery_igual_ao_golden_v1` e
    `test_linhas_das_fixtures_v1_iguais_ao_dataset`.
- **Consequência fora do 001:** veja plan.md D-09 (job `web`).

## Verificação final (T017)

- `make lint`: verde.
- `make test`: mcp 876 passed (37 bq deselected); agent 179 passed.
- `make test-bq`: mcp 37 passed. O agente não tem testes `bq` (saída 5, esperada).
