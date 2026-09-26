# Smoke do ciclo 000 (AC-07, AC-11, AC-13)

**Status geral:** o que roda sem GCP passou; o que depende de credencial está
pendente (T038, T039).

## Sem credenciais (feito)

| Verificação | Resultado |
|---|---|
| `make lint` | verde (mcp_server, agent, data/scripts, deploy) |
| `make test` | mcp_server: 301 passaram, 45 pulados (fixtures oficiais ausentes); agent: 161 passaram |
| AC-06 contra o mock real | `McpToolset` lista as 8 ferramentas; escopo do state prevalece |
| `aplicar_ddl.py --dry-run` | 20 `CREATE ... IF NOT EXISTS` nos 4 datasets |
| Build local das imagens (arm64, sem push) | MCP responde `initialize` em `/mcp` com 200; agente lista `bussola_agent` em `/list-apps` |
| `iam_datasets.sh` em simulação | só imprime os GRANT e os REVOKE; não chama gcloud nem bq |

## Com credenciais (pendente)

| Item | AC | Comando | Resultado |
|---|---|---|---|
| DDL aplicado 2 vezes | AC-11 | `uv run --project mcp_server python data/scripts/aplicar_ddl.py` | pendente |
| Fixtures oficiais | AC-04 | `make fixtures` e `make test` | pendente |
| Smoke de modelos | AC-12 | ver [`modelos.md`](./modelos.md) | pendente |
| Build/push das imagens | AC-13 | `deploy/build_push.sh mcp && deploy/build_push.sh agent` | pendente |
| Deploy hello | AC-13 | `deploy/deploy.sh mcp --tag c000 && deploy/deploy.sh agent --tag c000` | pendente |
| MCP privado | AC-13 | `curl` sem token → 403; com `gcloud auth print-identity-token` → 200 | pendente |
| Agente hello local contra o mock | AC-07 | `make mcp` e `make agent` | pendente |

## Observações

- Com ADC de usuário, `google.oauth2.id_token.fetch_id_token` não emite ID
  token (R-04). Para testar o MCP privado da máquina local, use
  `gcloud auth print-identity-token`. No Cloud Run, o metadata server emite o
  token.
- A primeira revisão de um serviço novo recebe 100% do tráfego desse serviço
  (o gcloud não aceita `--no-traffic` na criação). As seguintes saem com
  `--tag cNNN --no-traffic`.
- Esperado no Plano B: a chamada ao Gemini do agente no Cloud Run falha com a
  SA default (sem `aiplatform.user` nem `secretAccessor`). O resultado
  alimenta a decisão de [`pedidos-owner.md`](./pedidos-owner.md).
