# Deploy com Helm (Cloud Run)

O projeto não tem cluster Kubernetes: a org policy `gcp.restrictServiceUsage`
bloqueia o GKE, e a constituição diz "sem GKE". O Helm entra só como
**templater**. O chart `bussola/` gera os manifestos Knative
(`serving.knative.dev/v1`) dos serviços `bussola-mcp` e `bussola-agent`, e o
`gcloud run services replace` aplica esses manifestos. Não existe
`helm install`.

## O que o chart garante

O `helm template` falha, antes de chegar ao GCP, quando:

- falta `release.tag` ou ela não é `main` nem `cNNN`;
- falta `release.revisionSuffix` ou ele é inválido (só minúsculas, dígitos e
  hífen, com o nome da revisão até 63 caracteres);
- a tag já está em outra revisão;
- o tráfego mantido (`services.<nome>.traffic`) não soma 100%;
- há uma variável com cara de segredo (`KEY`, `TOKEN`, `SECRET`, `PASSWORD`)
  em `env`. Segredo vai em `secretEnv`, que vira `secretKeyRef` no Secret
  Manager.

Com isso, a revisão nova sempre sai com **0% de tráfego** e a tag `main`
(ou a do ciclo), e as revisões atuais seguem com o mesmo percentual. Só o
007 muda percentuais. O `replace` não altera IAM, então o serviço continua
privado.

## Deploy pelo GitHub Actions

O caminho normal é o `.github/workflows/deploy.yml`. Todo push na `main`
(trunk-based: merge ou commit direto) roda o CI e, verde, publica `mcp` e
depois `agent`:

1. build `linux/amd64` e push para `agentes/<serviço>:<sha curto>`;
2. `gcloud run services describe` lê o tráfego vivo e o
   [`traffic.jq`](traffic.jq) o converte em `services.<nome>.traffic`;
3. `helm template` com `release.tag=main`,
   `release.revisionSuffix=main-<sha>-<tentativa>` e a imagem por digest;
4. `gcloud run services replace --dry-run` e, em seguida, o `replace`;
5. confere que os percentuais não mudaram e escreve o resumo com a URL da
   tag (`https://main---<serviço>-...run.app`).

A tag `main` é rolante: sempre aponta para a última revisão publicada pela
`main`. Para marcar a revisão de um ciclo, dispare o workflow à mão com
`tag=cNNN`:

```bash
gh workflow run deploy.yml -f service=both -f tag=c007
```

O workflow só autentica por Workload Identity Federation. Sem as variáveis
do repositório `GCP_WIF_PROVIDER` e `GCP_DEPLOY_SA` (pedido 5 ao owner), o
push na `main` roda só o CI e avisa que o deploy foi pulado.

## Renderizar e validar à mão

Útil para depurar o chart. Rode na raiz do repositório. Troque `c007` pela
tag e dê um sufixo novo a cada renderização.

```bash
helm template bussola deploy/helm/bussola \
  --set release.tag=c007 --set release.revisionSuffix=c007-01 \
  --show-only templates/agent-service.yaml > /tmp/bussola-agent.yaml
```

Primeiro valide sem aplicar:

```bash
gcloud run services replace /tmp/bussola-agent.yaml \
  --project batalha-time-07-lkbv --region us-central1 --dry-run
```

Para o MCP, use `templates/mcp-service.yaml`. Fora do workflow, o tráfego
vem de `services.<nome>.traffic` em `values.yaml`, que pode estar
desatualizado. Aplicar é papel do workflow.

## Pré-requisitos no GCP (mudanças de IAM: confirmação humana)

| Para quê | Quem pode aplicar | Comando |
|---|---|---|
| Agente ler a `gemini-api-key` (plano B). O Cloud Run recusa a revisão sem isso. | Admins de Secret Manager do time | `gcloud secrets add-iam-policy-binding gemini-api-key --project batalha-time-07-lkbv --member="serviceAccount:1061873050224-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"` |
| Agente chamar o MCP privado (Q-16) | Quem tem `run.admin` | `gcloud run services add-iam-policy-binding bussola-mcp --project batalha-time-07-lkbv --region us-central1 --member="serviceAccount:1061873050224-compute@developer.gserviceaccount.com" --role="roles/run.invoker"` |
| MCP ler `bussola_dados` e agente gravar em `bussola_app` (modo `memoria`, sem `bigquery.jobUser`) | Quem tem `bigquery.admin` | `deploy/iam_datasets.sh` (dry-run por padrão) |

## Testes

```bash
make helm-lint   # helm lint
make test-helm   # pytest: chart, traffic.jq e coerência com o deploy.yml
```

Os testes ficam em `deploy/tests/` e rodam no CI (job `helm`). Eles não usam
rede nem GCP e são pulados se o `helm` ou o `jq` não estiverem instalados.
