# Marcos do ciclo 001

## Marco "tabelas v1" (ciclo 001 §3.2)

- **Data:** 2026-09-27.
- **Situação:** publicado e validado. Isso desbloqueia o `make test-bq` do 003 e a
  espera do 002.
- **Registro:** feito antes de terminar a simulação (§3.5), como o ciclo pede.
- **Aviso ao time:** vai no relatório final do ciclo. O 001 não tem canal próprio.

**Como as tabelas foram publicadas:**

- **Projeto:** `batalha-time-07-lkbv`, dataset `bussola_dados` (`us-central1`).
- **Comando:**

  ```bash
  cd mcp_server && uv run python ../data/scripts/build_dados.py --projeto batalha-time-07-lkbv
  ```

- **Tempo total:** cerca de 54 s.
- **Método:** DDL idempotente de `contracts/bigquery/bussola_dados.sql` e, depois,
  `TRUNCATE` + `INSERT` por tabela, dentro de uma transação (plan.md D-01).
- **Origem:** `hackathon_dados.extrato_sintetico`, somente leitura.

| Tabela | Linhas | Observação |
|---|---:|---|
| `perfil_mensal` | 12.000 | 1.000 usuários × 12 meses |
| `gastos_categoria` | 261.152 | só saídas |
| `entradas_categoria` | 27.889 | só entradas |
| `recorrentes` | 292.193 | `descr_norm` em ≥ 3 meses distintos do ano |
| `parcelas` | 29.847 | `parcela_total > 1` |
| `categorias` | 98 | seed versionado (`data/sql/seed_categorias.sql`, INFERRED) |
| `referencia_coorte` | 63 | P1: faixa × macro, só grupos com ≥ 5 usuários |
| `users` | 2 | personas do login simulado, sem senha nem hash |

**Validação pós-build.** As 13 checagens de `build_dados.py` (`EXPECTED_CHECKS`) passaram
("Validação pós-build: ok."):

- `usuarios` = 1.000 e `linhas_perfil` = 12.000 (1.000 usuários × 12 meses);
- `perfil_duplicado` = 0: nenhum usuário/mês repetido;
- `fora_periodo` = 0: nenhum `anomes` fora de 202501–202512 nas 5 tabelas por cliente;
- `ids_invalidos` = 0: todo `id_usuario` é UUID v4 em minúsculas;
- `gasto_divergente` = 0: Σ `gastos_categoria` = `perfil_mensal.gasto` por usuário/mês;
- `renda_divergente` = 0: Σ `entradas_categoria` = `perfil_mensal.renda` por usuário/mês;
- `gastos_sem_perfil` = 0;
- `categorias` = 98 e `pares_sem_categoria` = 0;
- `categorias_invalidas` = 0: `corte_max_pct` entre 0,2 e 0,5 nas discricionárias e 0
  nas demais;
- `coorte_pequena` = 0: nenhum grupo da coorte com menos de 5 usuários;
- `users_sem_extrato` = 0.

**Para reproduzir só a validação:**

```bash
cd mcp_server && uv run python ../data/scripts/build_dados.py --projeto batalha-time-07-lkbv --somente-validar
```

## Marco "fixtures v1" (ciclo 001 §3.6)

O registro está na seção "Fixtures v1" de `traceability.md` e no commit
`contracts: fixtures v1 a partir de bussola_dados`.
