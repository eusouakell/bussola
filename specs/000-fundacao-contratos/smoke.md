# Smoke do ciclo 000 (AC-07, AC-11, AC-13)

**Status geral:** o que roda sem GCP passou; o que depende de credencial está
pendente (T038, T039).

## Sem credenciais (feito)

| Verificação | Resultado |
|---|---|
| `make lint` | verde (mcp_server, agent, data/scripts, deploy) |
| `make test` | mcp_server: 346 passaram (com as fixtures oficiais); agent: 161 passaram |
| AC-06 contra o mock real | `McpToolset` lista as 8 ferramentas; escopo do state prevalece |
| `aplicar_ddl.py --dry-run` | 20 `CREATE ... IF NOT EXISTS` nos 4 datasets |
| Build local das imagens (arm64, sem push) | MCP responde `initialize` em `/mcp` com 200; agente lista `bussola_agent` em `/list-apps` |
| `iam_datasets.sh` em simulação | só imprime os GRANT e os REVOKE; não chama gcloud nem bq |

## Com credenciais (pendente)

| Item | AC | Comando | Resultado |
|---|---|---|---|
| DDL aplicado 2 vezes | AC-11 | `uv run --project mcp_server python data/scripts/aplicar_ddl.py` | ok: 20 objetos nos 4 datasets; a 2ª execução não mudou nada |
| Fixtures oficiais | AC-04 | `make fixtures` e `make test` | ok: 35 arquivos (942 lançamentos lidos); 9 valores de referência dentro de 1% |
| Smoke de modelos | AC-12 | ver [`modelos.md`](./modelos.md) | ok: `gemini-3.8-flash` em `global`; `gemini-embedding-001` em `us-central1`, dimensão 3072 |
| Build/push das imagens | AC-13 | `deploy/build_push.sh mcp && deploy/build_push.sh agent` | pendente |
| Deploy hello | AC-13 | `deploy/deploy.sh mcp --tag c000 && deploy/deploy.sh agent --tag c000` | pendente |
| MCP privado | AC-13 | `curl` sem token → 403; com `gcloud auth print-identity-token` → 200 | pendente |
| Agente hello local contra o mock | AC-07 | `make mcp` e `make agent` | ok: chamou `perfil_financeiro` (ver abaixo) |

## AC-07: agente hello local contra o mock

- Data: 2026-09-26. Mock em `127.0.0.1:8080` com as fixtures oficiais; agente
  pelo `Runner` do ADK com Vertex (ADC do integrante), `gemini-3.8-flash` em
  `global`, `MCP_USE_OIDC=FALSE`.
- Pergunta: "qual é o meu perfil financeiro?".
- Ferramentas chamadas: só `perfil_financeiro`. O log do mock registra
  `evento=ferramenta_chamada` com `ferramenta=perfil_financeiro`.
- `session.state`: `ate_anomes = 202506`, preenchido por
  `inicializar_sessao`.
- Resposta em pt-BR com renda média de R$ 6.691,39, gasto médio de
  R$ 4.789,93, sobra média de R$ 1.901,47 e saldo de R$ 17.652,15. Os valores
  são os do golden `perfil_financeiro__ate_202506`, e a fonte é citada.
- Em `us-central1` o mesmo teste falha com 404 no modelo, daí a variável
  `BUSSOLA_LOCAL_MODELO=global` (Q-15).

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
