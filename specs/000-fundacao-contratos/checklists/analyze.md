# Analyze: Fundação e contratos

Ciclo de reparo 1 de 3 (Spec Master). Consistência entre `spec.md`,
`plan.md`, `tasks.md` e a constituição v1.0.0.

| ID | Categoria | Severidade | Achado | Reparo |
|---|---|---|---|---|
| A1 | Cobertura | Média | FR-001 (Spec Kit inicializado) sem linha no plano nem tarefa | Linha 0 no plano e T000 (concluída) em `tasks.md` |
| A2 | Cobertura | Baixa | AC-01 sem tarefa que o cite | T000 e T002 citam AC-01 |
| A3 | Cobertura | Média | AC-15 (tag `contratos-v1` após o merge) no estado do Spec Master e em 000 §4, sem rótulo na spec | Rótulo AC-15 na premissa da spec e T045 `[HUMANO]` fora do PR |
| A4 | Inconsistência | Baixa | Tabela de subagentes: trilha mcp não excluía `test_aplicar_ddl.py` da trilha dados | Corrigida em `tasks.md` |
| A5 | Divergência de contrato | Média | 10 divergências entre trilha, spec e contratos | `questoes.md` Q-01..Q-10 e correções aditivas em `contratos.md` (FR-025) |

Constituição: nenhuma violação. IV (respostas rotuladas) é N/A no 000.
Sem achados bloqueantes depois do reparo. Tarefas `[CRED]` (T032, T038,
T039) seguem pendentes de credencial, sem inventar dados.
