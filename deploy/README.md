# deploy/

Scripts de plataforma do ciclo 000 (projeto `batalha-time-07-lkbv`,
`us-central1`). Todos rodam com as credenciais do integrante (ADC) e têm
`--help`.

| Script | O que faz | Efeito no GCP |
|---|---|---|
| `smoke_modelos.py` | Valida Gemini Flash (3.8 → 3.7 → 3.5) e embedding via Vertex; fallback pela Gemini API | Só chamadas de modelo. Grava `modelos.md` e `env.example` apenas com `--gravar` |
| `build_push.sh <mcp\|agent> [tag]` | Build `linux/amd64` e push para `us-central1-docker.pkg.dev/batalha-time-07-lkbv/agentes/<serviço>` | Push de imagem |
| `deploy.sh <mcp\|agent> [--tag cNNN]` | `gcloud run deploy` privado | Revisão nova sem tráfego (`--tag cNNN --no-traffic`). Só a criação do serviço recebe tráfego |
| `iam_datasets.sh [--aplicar]` | Plano B: papéis BigQuery por dataset para a SA default de compute | Simulação por padrão. Aplica só com `--aplicar` e o nome do projeto digitado |

## Ordem de uso (T038)

```bash
uv run --project agent python deploy/smoke_modelos.py            # revisar
uv run --project agent python deploy/smoke_modelos.py --gravar   # gravar
deploy/build_push.sh mcp && deploy/build_push.sh agent
deploy/deploy.sh mcp --tag c000
deploy/deploy.sh agent --tag c000        # depois do mcp (usa a URL dele)
# Agente → MCP (Q-16): invoker no serviço bussola-mcp. IAM: só com confirmação humana.
gcloud run services add-iam-policy-binding bussola-mcp --project batalha-time-07-lkbv \
  --region us-central1 --member serviceAccount:1061873050224-compute@developer.gserviceaccount.com --role roles/run.invoker
deploy/iam_datasets.sh                   # simulação; revisar
deploy/iam_datasets.sh --aplicar         # só com confirmação humana
```

## Pipeline (GitHub Actions, Q-18)

| Workflow | Disparo | O que faz |
|---|---|---|
| `.github/workflows/ci.yml` | Push em branch que não é a `main` e todo `pull_request` | `make lint` + `make test` (fake, sem GCP), front web e BFF (`web-lint`, `web-test`, `web-build`) e chart Helm (`helm-lint`, `test-helm`) |
| `.github/workflows/deploy.yml` | Todo push na `main`; manual para tag `cNNN` | CI e depois deploy com Helm: revisão nova com tag `main` e 0% de tráfego ([helm/README.md](helm/README.md)) |

O `deploy.yml` autentica só por Workload Identity Federation. Sem as
variáveis do repositório abaixo, o push na `main` roda só o CI e o deploy é
pulado com aviso:

- `GCP_WIF_PROVIDER`: nome completo do provider, criado pelo owner (pedido
  5 de `specs/000-fundacao-contratos/pedidos-owner.md`);
- `GCP_DEPLOY_SA`: e-mail da SA de deploy.

A SA de runtime e o plano do LLM ficam em `helm/bussola/values.yaml`.
Mudar um deles é um commit na `main`, não um parâmetro do workflow.

Os scripts `build_push.sh` e `deploy.sh` são o caminho antigo, do 000.
Ficam só para emergência até a emenda da constituição
(`specs/000-fundacao-contratos/proposta-constituicao.md`) ser aprovada. O
workflow não os usa.

Nenhum workflow move tráfego ou altera IAM. A promoção é do 007.

## Regras

- Mover tráfego (`gcloud run services update-traffic`) é do ciclo 007 e pede
  confirmação humana. Nenhum script daqui faz isso.
- Mudança de IAM pede confirmação humana. `deploy.sh` só passa
  `--no-allow-unauthenticated` na criação do serviço e não toca na política
  depois; `iam_datasets.sh` só muda IAM de dataset, nunca do projeto.
- Segredos só pelo Secret Manager (`--set-secrets`). Nenhum script imprime ou
  grava chave.
- SA de runtime: padrão = SA default de compute (Plano B). Para o Plano A:
  `BUSSOLA_SA_RUNTIME=bussola-runtime deploy/deploy.sh ...`.
