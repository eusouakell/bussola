# Deploy com Helm (Cloud Run)

O projeto não tem cluster Kubernetes: a org policy `gcp.restrictServiceUsage`
bloqueia o GKE, e a constituição diz "sem GKE". O Helm entra só como
**templater**. O chart `bussola/` gera os manifestos Knative
(`serving.knative.dev/v1`) dos serviços `bussola-mcp`, `bussola-agent` e
`bussola-bff` (front e BFF, `web/Dockerfile`), e o
`gcloud run services replace` aplica esses manifestos. Não existe
`helm install`.

## O que o chart garante

O `helm template` falha, antes de chegar ao GCP, quando:

- falta `release.tag` ou ela não é `main`, `cNNN` ou `cNNN-<rótulo>` (até 10
  minúsculas, para revisões de teste como `c007-bad` e `c007-planob`);
- falta `release.revisionSuffix` ou ele é inválido (só minúsculas, dígitos e
  hífen, com o nome da revisão até 63 caracteres);
- a tag já está em outra revisão;
- o tráfego mantido (`services.<nome>.traffic`) não soma 100%;
- `create: true` aparece num serviço que já tem tráfego mantido;
- há uma variável com cara de segredo (`KEY`, `TOKEN`, `SECRET`, `PASSWORD`)
  em `env`. Segredo vai em `secretEnv`, que vira `secretKeyRef` no Secret
  Manager.

Com isso, a revisão nova sempre sai com **0% de tráfego** e a tag `main`
(ou a do ciclo), e as revisões atuais seguem com o mesmo percentual. Só a
[promoção](#promoção-e-rollback) muda percentuais, com confirmação humana. A
exceção é a criação de um serviço (abaixo).

O `replace` não mexe em bindings de IAM. Sem `public: true`, o serviço exige
`roles/run.invoker`. Com ele, a checagem de invoker fica desligada
(`run.googleapis.com/invoker-iam-disabled`). Só o `bff` é público: ele faz o
login simulado por persona, e `mcp` e `agent` continuam privados.

## Deploy pelo GitHub Actions

O caminho normal é o `.github/workflows/deploy.yml`. Todo push na `main`
(trunk-based: merge ou commit direto) roda o CI e, verde, publica `mcp` e
depois `agent` e `bff`:

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
gh workflow run deploy.yml -f service=all -f tag=c007
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

Para o MCP, use `templates/mcp-service.yaml` (BFF: `templates/bff-service.yaml`).
Sem `-f /tmp/traffic.json`, o tráfego vem de `services.<nome>.traffic` em
`values.yaml`. Ele espelha o estado vivo da última conferência e pode estar
desatualizado. Para aplicar, gere o `traffic.json` do `describe` logo antes,
como no deploy local.

## Deploy local (sem WIF)

Enquanto o WIF não existe, o mesmo fluxo roda da máquina de quem tem
`run.admin`, sem script: build, tráfego vivo, `helm template`, dry-run e
`replace`. O sufixo termina em `-local` para marcar que a imagem saiu de uma
máquina, e não do workflow.

```bash
SHA=$(git rev-parse --short HEAD); KEY=bff; NAME=bussola-bff
docker buildx build --platform linux/amd64 --provenance=false --push \
  -f web/Dockerfile --metadata-file /tmp/build.json \
  -t us-central1-docker.pkg.dev/batalha-time-07-lkbv/agentes/$NAME:$SHA-local .
gcloud run services describe $NAME --project batalha-time-07-lkbv \
  --region us-central1 --format=json \
  | jq --arg key $KEY --arg tag main -f deploy/helm/traffic.jq > /tmp/traffic.json
helm template bussola deploy/helm/bussola -f /tmp/traffic.json \
  --set release.tag=main --set release.revisionSuffix=main-$SHA-local \
  --set services.$KEY.image=$(jq -r '."containerimage.digest"' /tmp/build.json) \
  --show-only templates/$KEY-service.yaml > /tmp/$NAME.yaml
gcloud run services replace /tmp/$NAME.yaml \
  --project batalha-time-07-lkbv --region us-central1 --dry-run
```

Sem erro no dry-run, rode o mesmo `replace` sem `--dry-run`. A revisão nova
fica na URL `https://main---<serviço>-wimifi56uq-uc.a.run.app`, com 0% de
tráfego. Para `mcp` e `agent`, troque o Dockerfile (`mcp_server/Dockerfile`,
`agent/Dockerfile`).

## Criar um serviço (confirmação humana)

Serviço novo não tem tráfego para manter, e o chart recusa renderizar sem
ele. Para criar, passe `create: true` e zere o tráfego de `values.yaml`
(`traffic=null`). A primeira revisão recebe 100%, com a tag da release:

```bash
helm template bussola deploy/helm/bussola \
  --set release.tag=main --set release.revisionSuffix=main-$SHA-local \
  --set services.bff.create=true --set services.bff.traffic=null \
  --set services.bff.image=<digest> \
  --show-only templates/bff-service.yaml > /tmp/bussola-bff.yaml
```

Depois do `replace`, registre a primeira revisão em
`services.<nome>.traffic`, como o `traffic.jq` a devolveria (sem a tag
`main`). Assim os outros templates voltam a renderizar. O `bussola-bff` foi
criado assim, em 2026-09-26, com a revisão `bussola-bff-main-1f2a380-local`.

## Planos A e B (overlays)

O `values.yaml` espelha o estado vivo, que é o **Plano B**. Os overlays
trocam o plano de forma explícita:

| Overlay | SA | MCP | Agente |
|---|---|---|---|
| `values-plan-b.yaml` | default de compute | `BQ_MODO_LEITURA=memoria`, `RAG_BACKEND=lexico` | Gemini API: `GOOGLE_API_KEY` por `secretKeyRef` em `gemini-api-key` |
| `values-plan-a.yaml` | `bussola-runtime` (pedido 1) | `query`, `numpy` | Vertex AI, sem chave |

Nenhum overlay lê a chave: o Cloud Run resolve o `secretKeyRef` em tempo de
execução. Publique numa revisão com tag (`c007-planob`, por exemplo) e 0% de
tráfego, rode o smoke pela tag e só então promova:

```bash
helm template bussola deploy/helm/bussola \
  -f deploy/helm/bussola/values-plan-b.yaml -f /tmp/traffic.json \
  --set release.tag=c007-planob --set release.revisionSuffix=c007-planob-1 \
  --show-only templates/agent-service.yaml > /tmp/bussola-agent.yaml
```

Passo a passo: [docs/operacao.md §9](../../docs/operacao.md#9-plano-b-e-volta).

## Promoção e rollback

Promover é mudar **só o tráfego**. No modo promoção
(`promotion.service` preenchido), o chart renderiza apenas
`templates/promotion.yaml`. Esse manifesto:

- copia o `spec.template` vivo sem nenhuma mudança, e por isso o Cloud Run
  não cria revisão nova;
- dá 100% ao alvo (`main`, `cNNN`, o nome de uma revisão ou `previous`);
- mantém as tags vivas com 0%;
- põe a tag `previous` na revisão que servia.

O **rollback** é promover `previous`.

O estado vivo vem do `describe`, convertido pelo [`promote.jq`](promote.jq):

```bash
gcloud run services describe bussola-agent --project batalha-time-07-lkbv \
  --region us-central1 --format=json \
  | jq --arg key agent --arg target c007 -f deploy/helm/promote.jq > /tmp/promotion.json
helm template bussola deploy/helm/bussola -f /tmp/promotion.json \
  --show-only templates/promotion.yaml > /tmp/promotion.yaml
gcloud run services replace /tmp/promotion.yaml \
  --project batalha-time-07-lkbv --region us-central1 --dry-run
```

O `helm template` recusa, antes do GCP:

- serviço desconhecido, ou estado vivo de outro serviço;
- estado vivo sem `template`;
- tráfego dividido entre revisões ou que não soma 100%;
- alvo fora do tráfego vivo, ou que já recebe 100%;
- drift de `public` ou de ingress entre o vivo e o `values.yaml`, porque
  promover não muda IAM.

O `replace` sem `--dry-run` move tráfego e **exige confirmação humana**:

- **no GitHub:** `.github/workflows/promote.yml`, com o nome do serviço
  digitado em `confirm` e aprovação no environment `production`;
- **na máquina:** o fluxo de [docs/operacao.md §8](../../docs/operacao.md#8-promoção-e-rollback).

## Pré-requisitos no GCP (mudanças de IAM: confirmação humana)

| Para quê | Quem pode aplicar | Comando |
|---|---|---|
| Agente ler a `gemini-api-key` (plano B). O Cloud Run recusa a revisão sem isso. | Admins de Secret Manager do time | `gcloud secrets add-iam-policy-binding gemini-api-key --project batalha-time-07-lkbv --member="serviceAccount:1061873050224-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"` |
| Agente chamar o MCP privado (Q-16) | Quem tem `run.admin` | `gcloud run services add-iam-policy-binding bussola-mcp --project batalha-time-07-lkbv --region us-central1 --member="serviceAccount:1061873050224-compute@developer.gserviceaccount.com" --role="roles/run.invoker"` |
| MCP ler `bussola_dados` e agente gravar em `bussola_app` (modo `memoria`, sem `bigquery.jobUser`) | Quem tem `bigquery.admin` | `deploy/iam_datasets.sh` (dry-run por padrão) |
| BFF ler o hash da senha padrão de teste | Admins de Secret Manager do time | `gcloud secrets add-iam-policy-binding bussola-auth-password-hash --project batalha-time-07-lkbv --member="serviceAccount:1061873050224-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"` |
| BFF chamar o agente privado | Quem tem `run.admin` | `gcloud run services add-iam-policy-binding bussola-agent --project batalha-time-07-lkbv --region us-central1 --member="serviceAccount:1061873050224-compute@developer.gserviceaccount.com" --role="roles/run.invoker"` |
| BFF público (`public: true`) | Quem tem `run.services.setIamPolicy` | vem do chart, no `replace` |

O segredo `bussola-auth-password-hash` guarda só o hash scrypt. Quem cria
escolhe a senha, que não vai para o repositório nem para o chat. O hash fica
só na variável e vai ao `gcloud` pela entrada padrão. Ele é gravado só se a
geração deu certo:

```bash
cd web && H=$(npm run -s hash-password) \
  && gcloud secrets versions add bussola-auth-password-hash --data-file=- \
       --project batalha-time-07-lkbv <<<"$H"; unset H
```

## Testes

```bash
make helm-lint   # helm lint
make test-helm   # pytest em deploy/tests (também roda no make test)
```

Os testes ficam em `deploy/tests/`:

- chart e `traffic.jq`, com as guardas e os overlays de plano;
- modo promoção e `promote.jq`;
- coerência entre `deploy.yml`, `promote.yml` e o chart;
- `smoke.py`, com HTTP e `gcloud` falsos.

Eles não usam rede nem GCP. Os de renderização são pulados se o `helm` ou
o `jq` não estiverem instalados.
