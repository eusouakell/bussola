# Runbook de operação da Bússola

Comandos prontos para copiar, na raiz do repositório. Quem opera (integrante
ou agente do Antigravity) segue o [`AGENTS.md`](../AGENTS.md).

## Regras que valem para todo o runbook

- **Confirmação humana** para mover tráfego (promover ou rollback), trocar
  de plano, publicar revisão, mudar variável ou segredo e mudar IAM. Antes
  de rodar, mostre o comando e o efeito e espere um "sim" explícito no chat.
  Os blocos marcados com **[confirmação humana]** são esses.
- **Revisão nova sempre com tag e 0% de tráfego** (`main`, `cNNN` ou
  `cNNN-<rótulo>`). Só a promoção (§8) move tráfego. O `ci.yml` e o
  `deploy.yml` não movem.
- **Segredos:** a `gemini-api-key` e o hash da senha ficam só no Secret
  Manager, e o Cloud Run os injeta por `secretKeyRef`. Nenhum comando daqui
  lê o valor. ID token só em variável (`TOKEN=$(...)`), nunca em `echo`,
  arquivo ou chat, e `unset TOKEN` no fim.
- O `/tmp/*.json` e o `/tmp/*.yaml` dos comandos abaixo guardam só estado de
  serviço e manifestos, sem segredo.

## 1. Pré-requisitos

- `gcloud` autenticado com a conta do integrante (`gcloud auth login`) e ADC
  para o `bq` (`gcloud auth application-default login`). No Antigravity, o
  terminal do agente usa a sessão `gcloud` de quem está logado na máquina
  (Q5 do mestre). Confira a conta ativa com `gcloud auth list` antes de
  operar.
- `jq`, `helm` (v4, como no CI) e `uv`. Para build, `docker buildx`.
- Para o smoke: `roles/iam.serviceAccountTokenCreator` na SA de runtime (o
  ID token sai por impersonação). Conceder é mudança de IAM (§11).
- Para publicar ou promover: `roles/run.admin` (ou `run.developer` +
  `iam.serviceAccountUser` na SA de runtime).

```bash
export PROJECT=batalha-time-07-lkbv REGION=us-central1
export SA=1061873050224-compute@developer.gserviceaccount.com
gcloud config set project "$PROJECT"
```

## 2. Status

Serviços, URLs e última revisão pronta:

```bash
gcloud run services list --project "$PROJECT" --region "$REGION" \
  --format='table(metadata.name,status.url,status.latestReadyRevisionName)'
```

Tráfego e tags (tag, revisão, percentual, URL da tag):

```bash
for s in bussola-mcp bussola-agent bussola-bff; do
  printf '== %s\n' "$s"
  gcloud run services describe "$s" --project "$PROJECT" --region "$REGION" --format=json \
    | jq -r '.status.traffic[] | [(.tag // "-"), .revisionName, "\(.percent // 0)%", (.url // "-")] | @tsv'
done
```

Revisões de um serviço, com a tag de release gravada pelo chart:

```bash
gcloud run revisions list --service bussola-agent --project "$PROJECT" --region "$REGION" \
  --format='table(metadata.name,metadata.labels.release-tag,status.conditions[0].status,metadata.creationTimestamp)'
```

Privacidade do MCP e do agente. Esperado: só a SA de runtime como
`roles/run.invoker`, sem `allUsers`, e 403 sem token:

```bash
gcloud run services get-iam-policy bussola-mcp --project "$PROJECT" --region "$REGION"
curl -s -o /dev/null -w 'mcp sem token: %{http_code}\n' https://bussola-mcp-wimifi56uq-uc.a.run.app/mcp
```

### Quem fala com quem

| De | Para | Como |
|---|---|---|
| `bussola-bff` | agente | `AGENT_URL` = URL da tag `main` do agente (`https://main---bussola-agent-...`), com audience = URL principal |
| `bussola-agent` | MCP | `MCP_URL` = URL **principal** do MCP + `/mcp`. O agente usa a revisão do MCP que tem 100% |

Consequências:

- o canal da demo usa a revisão com a tag `main` do agente, e não a que tem
  100%;
- com o WIF, cada push na `main` move a tag `main` e muda o canal. No dia da
  demo, congele a `main` (§7);
- promova o MCP antes do agente, porque o agente só enxerga o MCP pela URL
  principal. O ID token não aceita a URL de tag como audience.

## 3. Deploy de uma versão nova

**Caminho normal: GitHub Actions** ([deploy/helm/README.md](../deploy/helm/README.md)).
Todo push na `main` roda o CI e publica os três serviços com a tag `main` e
0% de tráfego. Para marcar a revisão de um ciclo:

```bash
gh workflow run deploy.yml -f service=all -f tag=c007
```

O workflow só autentica por WIF. Sem as variáveis `GCP_WIF_PROVIDER` e
`GCP_DEPLOY_SA` (pedido 5 ao owner), o deploy é pulado.

**Sem WIF: o mesmo fluxo, local.** Quem tem `run.admin` roda o fluxo abaixo.
Ele é o mesmo para `mcp` (`mcp_server/Dockerfile`), `agent`
(`agent/Dockerfile`) e `bff` (`web/Dockerfile`).

1. build;
2. estado vivo;
3. `helm template`;
4. dry-run;
5. `replace` **[confirmação humana]**.

Leia o estado vivo logo antes de cada renderização: um `traffic.json` velho
apaga tags que surgiram depois.

```bash
KEY=agent; NAME=bussola-$KEY; DOCKERFILE=agent/Dockerfile
SHA=$(git rev-parse --short HEAD); TAG=c007; SUFFIX=$TAG-$SHA-1
AR=us-central1-docker.pkg.dev/$PROJECT/agentes

# 1. Imagem (pule para reusar o digest de values.yaml).
docker buildx build --platform linux/amd64 --provenance=false --push \
  -f "$DOCKERFILE" --metadata-file /tmp/build.json -t "$AR/$NAME:$SHA-local" .
IMAGE=$(jq -r '."containerimage.digest"' /tmp/build.json)

# 2. Tráfego vivo, mantido como está.
gcloud run services describe "$NAME" --project "$PROJECT" --region "$REGION" --format=json \
  > /tmp/before.json
jq --arg key "$KEY" --arg tag "$TAG" -f deploy/helm/traffic.jq /tmp/before.json > /tmp/traffic.json

# 3. Manifesto (as guardas do chart falham aqui, antes do GCP).
helm template bussola deploy/helm/bussola -f /tmp/traffic.json \
  --set release.tag="$TAG" --set release.revisionSuffix="$SUFFIX" \
  --set services.$KEY.image="$IMAGE" \
  --show-only templates/$KEY-service.yaml > /tmp/$NAME.yaml

# 4. Validação no Cloud Run, sem aplicar.
gcloud run services replace /tmp/$NAME.yaml --project "$PROJECT" --region "$REGION" --dry-run
```

**[confirmação humana]** Publique a revisão, com tag e 0% de tráfego:

```bash
gcloud run services replace /tmp/$NAME.yaml --project "$PROJECT" --region "$REGION"
```

Confira que os percentuais não mudaram (§2) e rode o smoke pela tag (§4).
Só então promova (§8).

## 4. Smoke

O `deploy/smoke.py` só usa a stdlib do Python e roda pelo `make smoke`. Ele:

- **MCP:** faz `initialize` e `tools/list` com ID token;
- **agente:** abre uma sessão na API do ADK, pergunta "qual é o meu perfil
  financeiro?", exige a chamada da ferramenta `perfil_financeiro` e apaga a
  sessão no fim;
- **BFF:** confere `GET /` (200, HTML) e `GET /auth/me` (401
  `NAO_AUTENTICADO`).

O ID token sai de `gcloud auth print-identity-token
--impersonate-service-account=$SA --audiences=<URL principal>`. Ele não
aparece na saída, e a saída passa por uma redação de tokens.

```bash
make smoke                                          # produção: MCP principal, agente e BFF
make smoke SMOKE_ARGS="--tag c007 --only agent"     # revisão com tag, antes de promover
make smoke SMOKE_ARGS="--only bff"                  # só GETs públicos
make smoke SMOKE_ARGS="--json"                      # relatório em JSON
```

- Sai com código 0 só quando todas as checagens passam.
- `[AVISO]` não reprova: por exemplo, quando o texto do agente não menciona
  a ferramenta.
- Com `--tag`, a URL chamada é a da tag, mas a audience continua sendo a URL
  principal. Com a URL de tag como audience, o Cloud Run devolve 401.
- Quando a auditoria do 005 estiver ativa, o smoke deixa uma sessão curta
  registrada na auditoria.

## 5. Logs

Os serviços escrevem JSON com os campos de contratos §9 (`servico`,
`session_id`, `estado_jornada`, `ferramenta`, `evento`, `consentimento`,
`ate_anomes`, `latencia_ms`, `erro_codigo`). Os erros do ADK e do Gemini
chegam como `textPayload`, com traceback.

```bash
# Funções (e não variáveis) para funcionar igual no bash e no zsh.
logs() { gcloud logging read --project "$PROJECT" --freshness=1h --limit 30 "$@"; }
BASE='resource.type="cloud_run_revision" AND resource.labels.service_name=~"^bussola-"'
```

| Pergunta | Filtro (acrescente a `$BASE`) |
|---|---|
| Últimos erros | `AND severity>=ERROR` |
| Erros das ferramentas | `AND jsonPayload.erro_codigo:*` |
| Um serviço | `AND jsonPayload.servico="bussola-agent"` |
| Uma sessão | `AND jsonPayload.session_id="<session_id>"` |
| Guardrails | `AND jsonPayload.evento="guardrail_bloqueio"` |
| Número sem fonte | `AND jsonPayload.evento="numero_sem_fonte"` |
| Sessões abertas | `AND jsonPayload.evento="sessao_iniciada"` |
| Mudança de estado | `AND jsonPayload.evento="estado_alterado"` |
| MCP recusando o agente | `AND resource.labels.service_name="bussola-mcp" AND httpRequest.status=403` |
| Gemini sem capacidade | `AND textPayload:("503" OR "429" OR "RESOURCE_EXHAUSTED")` |

```bash
logs "$BASE AND severity>=ERROR" \
  --format='table(timestamp,resource.labels.service_name,resource.labels.revision_name,jsonPayload.erro_codigo,jsonPayload.message)'
logs "$BASE AND jsonPayload.evento=\"guardrail_bloqueio\"" \
  --format='table(timestamp,jsonPayload.session_id,jsonPayload.estado_jornada,jsonPayload.ferramenta)'
```

Resumo de um traceback: `--format='value(textPayload)'` e procure a linha
`...Error:` no fim. Os logs não trazem prompt nem chave. Se aparecer algo
assim, não copie para o chat e avise o dono do serviço.

## 6. Auditoria no BigQuery

As tabelas ficam em `batalha-time-07-lkbv.bussola_app`. Elas só recebem
linhas com a persistência do 005 ativa (`BUSSOLA_FAKES=FALSE` no agente).
Com `BUSSOLA_FAKES=TRUE`, estado de hoje, a auditoria fica em memória e as
consultas voltam vazias.

As consultas são só `SELECT`. Valor vindo de fora entra por parâmetro, nunca
concatenado.

```bash
bqq() { bq query --project_id="$PROJECT" --use_legacy_sql=false --max_rows=50 "$@"; }
```

Últimas sessões:

```bash
bqq 'SELECT session_id, MIN(ts) AS inicio, MAX(ts) AS fim, COUNT(*) AS eventos
FROM `batalha-time-07-lkbv.bussola_app.auditoria`
GROUP BY session_id ORDER BY fim DESC LIMIT 5'
```

Consentimentos da última sessão:

```bash
bqq 'WITH ultima AS (
  SELECT session_id FROM `batalha-time-07-lkbv.bussola_app.auditoria` ORDER BY ts DESC LIMIT 1)
SELECT c.ts, c.acao, c.decisao, c.plano_id
FROM `batalha-time-07-lkbv.bussola_app.consentimentos` AS c JOIN ultima USING (session_id)
ORDER BY c.ts'
```

Linha do tempo de uma sessão (parâmetro `@session_id`):

```bash
bqq --parameter=session_id::<session_id> 'SELECT ts, estado, tipo_evento, ferramenta,
  TO_JSON_STRING(resumo) AS resumo
FROM `batalha-time-07-lkbv.bussola_app.auditoria`
WHERE session_id = @session_id ORDER BY ts'
```

Eventos por `tipo_evento` nas últimas 24 h (`guardrail_bloqueio`,
`desvio_detectado` etc.):

```bash
bqq 'SELECT tipo_evento, COUNT(*) AS n, MAX(ts) AS ultimo
FROM `batalha-time-07-lkbv.bussola_app.auditoria`
WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
GROUP BY tipo_evento ORDER BY n DESC'
```

Planos criados e acompanhamento:

```bash
bqq 'SELECT criado_em, plano_id, session_id, objetivo, valor_alvo, prazo_meses, cenario,
  aporte_mensal, ate_anomes
FROM `batalha-time-07-lkbv.bussola_app.planos` ORDER BY criado_em DESC LIMIT 10'
bqq 'SELECT ts, plano_id, anomes, planejado, realizado, desvio, categoria_desvio, acao_sugerida
FROM `batalha-time-07-lkbv.bussola_app.acompanhamento` ORDER BY ts DESC LIMIT 20'
```

Sem `bigquery.jobUser`, use `bq head -n 20 $PROJECT:bussola_app.consentimentos`,
que lê por `list_rows`.

## 7. Operação da demo

### Canal

- **Principal:** o front público do BFF, `https://bussola-bff-wimifi56uq-uc.a.run.app`.
  - O login é simulado: persona **Fernando** e a senha padrão de teste,
    combinada com o time. Ela não fica no repositório.
  - Na barra "Modo demonstração", deixe `Agente: Ao vivo (ADK)`.
- **Contingência 1: modo `Simulado`.** Fica no mesmo front e roda sem rede,
  com o roteiro gravado em `web/fixtures/roteiro-demo.json`.
- **Contingência 2: ADK Web, pelo proxy local.** Autentica com a sua conta,
  sem invoker público. Abra `http://localhost:8080` e escolha
  `bussola_agent`:

```bash
gcloud run services proxy bussola-agent --project "$PROJECT" --region "$REGION" \
  --tag main --port 8080
```

### Sessão

- **Sessão nova:** no front, use "Trocar persona" e entre de novo. No ADK
  Web, use "New session".
- A sessão fica **em memória**, numa instância só (`max-instances=1`). Ela
  se perde quando:
  - a instância é reciclada: ociosidade, falha ou uma revisão nova
    recebendo tráfego;
  - o Cloud Run sobe uma segunda instância.

  A sessão antiga não volta: abra uma nova. A auditoria continua no BigQuery,
  com o `session_id` antigo (§6), porque cada evento é gravado na hora.
  Nada precisa ser apagado.
- **Avançar mês:** use o botão "Avançar um mês" da barra (ele envia o texto
  "avançar um mês") ou digite o texto. O botão só funciona depois do plano
  criado e para em dez/2025, com o erro `FIM_DO_REPLAY`.

### Mês inicial e usuário-âncora

`REPLAY_START_ANOMES` (padrão `202506`) e `ANCHOR_USER_ID` (Fernando) ficam em
`services.agent.env` do `values.yaml`. Mudar é configuração:

1. commit na `main`;
2. revisão nova com tag (§3);
3. smoke;
4. promoção **[confirmação humana]**.

### Antes da demo

Siga o checklist de [roteiro-demo.md](roteiro-demo.md#checklist-pré-demo).
Os pontos de operação:

- congele a `main` (sem push) desde a véspera, porque o canal usa a tag
  `main` do agente;
- rode `make smoke`;
- aqueça a instância 2 min antes com uma pergunta simples.

## 8. Promoção e rollback

A promoção muda **só o tráfego**. O chart copia o `spec.template` vivo sem
mudança, e por isso nenhuma revisão nova é criada. O alvo recebe 100%, as
tags vivas continuam com 0% e a revisão que servia ganha a tag `previous`.

O rollback é promover `previous`. As guardas do chart recusam antes do GCP:

- tráfego dividido;
- alvo fora do tráfego vivo;
- alvo que já tem 100%;
- drift de `public` ou de ingress.

### Pelo GitHub Actions: `promote.yml` [confirmação humana]

A confirmação tem duas camadas:

- quem dispara digita o nome do serviço no campo `confirm`;
- o job espera aprovação no environment `production`.

O workflow roda o dry-run e confere 100% no alvo sem revisão nova.

```bash
gh workflow run promote.yml --ref main -f service=agent -f target=c007 -f confirm=bussola-agent
gh workflow run promote.yml --ref main -f service=agent -f target=previous -f confirm=bussola-agent  # rollback
```

O workflow também usa WIF (pedido 5). O environment `production` precisa
ser configurado por um admin do repositório (pendência em §12):

1. Settings → Environments → `production`;
2. **Required reviewers**: os dois integrantes, com "Prevent self-review";
3. **Deployment branches**: só `main`.

### Local, sem WIF

Leia o estado vivo, gere o manifesto e rode o dry-run:

```bash
KEY=agent; NAME=bussola-$KEY; TARGET=c007     # rollback: TARGET=previous
gcloud run services describe "$NAME" --project "$PROJECT" --region "$REGION" --format=json \
  > /tmp/before.json
jq --arg key "$KEY" --arg target "$TARGET" -f deploy/helm/promote.jq /tmp/before.json \
  > /tmp/promotion.json
helm template bussola deploy/helm/bussola -f /tmp/promotion.json \
  --show-only templates/promotion.yaml > /tmp/promotion.yaml
jq -c '.promotion.live.traffic' /tmp/promotion.json                  # tráfego antes
sed -n '/^  traffic:/,$p' /tmp/promotion.yaml                        # tráfego depois
gcloud run services replace /tmp/promotion.yaml --project "$PROJECT" --region "$REGION" --dry-run
```

**[confirmação humana]** Mostre o tráfego de antes e o de depois. Depois
do "sim", aplique:

```bash
gcloud run services replace /tmp/promotion.yaml --project "$PROJECT" --region "$REGION"
```

Confira: 100% no alvo, `previous` na revisão que servia e o mesmo
`latestCreatedRevisionName` de antes.

```bash
gcloud run services describe "$NAME" --project "$PROJECT" --region "$REGION" --format=json \
  | jq '{latest: .status.latestCreatedRevisionName, traffic: [.status.traffic[] | {revisionName, percent, tag}]}'
jq -r '.status.latestCreatedRevisionName' /tmp/before.json
```

**Ordem:** para promover, MCP → agente → BFF. Para o rollback, a ordem
inversa.

### Medir a disponibilidade durante a troca

Rode o laço num segundo terminal, antes da promoção, e pare depois do
rollback. O esperado é só `200`. O token fica na variável e sai com o
`unset`.

```bash
AUD=https://bussola-agent-wimifi56uq-uc.a.run.app
TOKEN=$(gcloud auth print-identity-token --impersonate-service-account="$SA" --audiences="$AUD")
for _ in $(seq 1 180); do
  curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" "$AUD/list-apps"
  sleep 1
done | sort | uniq -c
unset TOKEN
```

No BFF, que é público, não precisa de token: troque a URL pela do BFF e o
caminho por `/`.

## 9. Plano B e volta

| | Plano B (ativo) | Plano A |
|---|---|---|
| SA | default de compute + IAM por dataset (`deploy/iam_datasets.sh`) | `bussola-runtime` (pedido 1) |
| BigQuery (MCP) | `BQ_MODO_LEITURA=memoria` (`list_rows`) | `query` (jobUser) |
| RAG (MCP) | `RAG_BACKEND=lexico` | `numpy` (embeddings) |
| LLM (agente) | `GOOGLE_GENAI_USE_VERTEXAI=FALSE` + `GOOGLE_API_KEY` por `secretKeyRef` em `gemini-api-key` | Vertex AI, sem chave |
| Overlay | `deploy/helm/bussola/values-plan-b.yaml` | `deploy/helm/bussola/values-plan-a.yaml` |

O `values.yaml` já é o Plano B. Os overlays trocam o plano de forma
explícita. Nenhum deles lê a chave: o Cloud Run resolve o `secretKeyRef` em
tempo de execução, e a SA precisa de `secretAccessor` no segredo (§11).

**Trocar para o Plano B:**

1. publique numa revisão com tag e 0%;
2. rode o smoke pela tag;
3. promova **[confirmação humana]**.

Use `c007-planob` (ou `cNNN-planob`), porque uma tag já em uso é recusada.

```bash
KEY=agent; NAME=bussola-$KEY; TAG=c007-planob
gcloud run services describe "$NAME" --project "$PROJECT" --region "$REGION" --format=json \
  | jq --arg key "$KEY" --arg tag "$TAG" -f deploy/helm/traffic.jq > /tmp/traffic.json
helm template bussola deploy/helm/bussola \
  -f deploy/helm/bussola/values-plan-b.yaml -f /tmp/traffic.json \
  --set release.tag="$TAG" --set release.revisionSuffix="$TAG-1" \
  --show-only templates/$KEY-service.yaml > /tmp/$NAME.yaml
gcloud run services replace /tmp/$NAME.yaml --project "$PROJECT" --region "$REGION" --dry-run
# [confirmação humana] o mesmo replace sem --dry-run: revisão com tag e 0%
make smoke SMOKE_ARGS="--tag $TAG --only agent"
```

Confira o plano da revisão. A chave aparece só como referência, sem valor:

```bash
gcloud run revisions describe "$NAME-$TAG-1" --project "$PROJECT" --region "$REGION" --format=json \
  | jq '.spec.containers[0].env | map({name, value, secret: .valueFrom.secretKeyRef.name})'
```

Repita com `KEY=mcp` para o MCP. Promova com `TARGET=$TAG` (§8).

**Voltar ao Plano A:** o mesmo fluxo com `values-plan-a.yaml`. Ele depende de:

- pedido 1, com a SA `bussola-runtime` e seus papéis;
- `roles/run.invoker` para essa SA no `bussola-mcp` e no `bussola-agent`;
- `iam.serviceAccountUser` para quem publica.

Todos são mudanças de IAM (§11). Sem elas, o agente falha com `403
PERMISSION_DENIED ... aiplatform` (§10).

## 10. Troubleshooting

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Agente: `Failed to create MCP session ... 403 Forbidden`; MCP com `httpRequest.status=403` | `MCP_USE_OIDC=FALSE` (sem ID token) ou SA do agente sem `roles/run.invoker` no `bussola-mcp` | Confira o env da revisão (§2, `revisions list`). A revisão de teste `c007-bad` reproduz isso de propósito: nunca promova. Invoker: §11 **[confirmação humana]** |
| Smoke: 401 | Audience do ID token é a URL da tag | Use a URL principal como audience. O `smoke.py` já faz isso |
| Smoke: 403 no agente ou no MCP | A SA impersonada não é invoker, ou falta `serviceAccountTokenCreator` para quem roda | §11 **[confirmação humana]** |
| BFF: `/healthz` dá 404 | O Cloud Run reserva `/healthz` no GFE | Use `GET /` e `GET /auth/me` (401) |
| Agente: `429 Too Many Requests` / `RESOURCE_EXHAUSTED` | Cota da Gemini API (Plano B) | Espere 1 min. O agente tenta de novo e cai para outro Flash. Na demo, use o modo `Simulado` |
| Agente: `503 UNAVAILABLE` ("model is currently experiencing high demand") | Demanda alta no Gemini | O mesmo: nova tentativa e fallback entre os Flash. Se persistir, use `Simulado` ou o vídeo |
| Agente: `403 PERMISSION_DENIED ... aiplatform` | Vertex sem `aiplatform.user` (Plano A sem o pedido 1) | Volte ao Plano B (§9) |
| Ferramenta com `erro_codigo=INDISPONIVEL` | SA sem IAM no dataset (`dataViewer` em `bussola_dados`, `dataEditor` em `bussola_app`) ou `BQ_MODO_LEITURA=query` sem jobUser | `deploy/iam_datasets.sh` (simulação), depois `--aplicar` **[confirmação humana]**; ou volte o `BQ_MODO_LEITURA` para `memoria` |
| Revisão não sobe: segredo inacessível | SA sem `secretAccessor` em `gemini-api-key` ou `bussola-auth-password-hash` | §11 **[confirmação humana]** |
| Sessão sumiu, ou o agente "esqueceu" a conversa | Instância reciclada ou uma segunda instância (sessão em memória) | Sessão nova (§7). Confira `maxScale=1` na revisão. A auditoria continua no BigQuery |
| `helm template` falhou | Guarda do chart: tag em uso, tráfego que não soma 100, segredo em `env`, alvo inválido | Leia a mensagem. Ela diz o que corrigir, antes de tocar no GCP |
| `promote` falhou em "Revisão alvo pronta" | A revisão alvo não está `Ready` | `gcloud run revisions describe <revisão>`. Corrija e publique outra; não promova |

## 11. Referência de IAM (só com confirmação humana)

Os comandos ficam aqui para um integrante rodar. Nenhum script ou workflow
muda IAM. A tabela completa, com quem pode aplicar, está em
[deploy/helm/README.md](../deploy/helm/README.md#pré-requisitos-no-gcp-mudanças-de-iam-confirmação-humana).

```bash
# Agente -> MCP privado (Q-16). Nunca allUsers no MCP.
gcloud run services add-iam-policy-binding bussola-mcp --project "$PROJECT" --region "$REGION" \
  --member="serviceAccount:$SA" --role=roles/run.invoker
# BFF -> agente privado.
gcloud run services add-iam-policy-binding bussola-agent --project "$PROJECT" --region "$REGION" \
  --member="serviceAccount:$SA" --role=roles/run.invoker
# Runtime lê a chave do Gemini (Plano B) e o hash da senha do BFF.
gcloud secrets add-iam-policy-binding gemini-api-key --project "$PROJECT" \
  --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor
# Integrante roda o smoke (ID token por impersonação).
gcloud iam service-accounts add-iam-policy-binding "$SA" --project "$PROJECT" \
  --member="user:<email do integrante>" --role=roles/iam.serviceAccountTokenCreator
# IAM por dataset (Plano B): simulação; aplicar só com o projeto digitado.
deploy/iam_datasets.sh
```

## 12. Pendências com o owner e dívidas

Fonte: [specs/000-fundacao-contratos/pedidos-owner.md](../specs/000-fundacao-contratos/pedidos-owner.md).

| # | Pedido | Impacto enquanto pendente |
|---|---|---|
| 1 | SA de runtime `bussola-runtime` com 6 papéis | Plano B: SA default de compute compartilhada, chave de API do Gemini em runtime |
| 2 | Template de Model Armor `bussola-guard` | Guardrails só por callbacks do ADK (005) |
| 3 | Bucket do projeto | Build local com `docker buildx` |
| 4 | `allUsers` como invoker | Não bloqueia: o canal é o BFF (`invoker-iam-disabled` só nele); MCP e agente continuam privados |
| 5 | WIF + SA de deploy | `deploy.yml` e `promote.yml` não rodam; deploy e promoção pelo fluxo local (§3, §8) |
| — | Environment `production` com revisores (admin do repositório) | Sem isso, o GitHub cria o environment sem proteção; resta a confirmação digitada |

**Dívidas:**

- chave da Gemini API em runtime (Plano B);
- sem Model Armor;
- a SA default de compute é compartilhada pelos três serviços, e não há SA
  por serviço;
- sessão em memória com `max-instances=1`, sem alta disponibilidade;
- o canal segue a tag `main` do agente, e não a revisão promovida;
- `BUSSOLA_FAKES=TRUE` nos serviços até 001, 003 e 005 entrarem, com a
  auditoria em memória até lá;
- `build_push.sh` e `deploy.sh` antigos ficam até a emenda da constituição.

## 13. Comandos do orquestrador (ciclo 007, GCP real)

Rodam fora deste ciclo, sempre com confirmação humana antes de cada
`replace` sem `--dry-run`. Use o bloco de §3 com as variáveis abaixo e
**leia o estado vivo de novo antes de cada render**.

| Passo | Variáveis e extras | Depois |
|---|---|---|
| T021 revisão `c007` do agente (imagem de `values.yaml`, sem build) | `KEY=agent TAG=c007 SUFFIX=c007-$SHA-1`, sem `--set services.agent.image` | `make smoke SMOKE_ARGS="--tag c007 --only agent"` (espera OK) |
| T021 revisão com defeito `c007-bad` | `KEY=agent TAG=c007-bad SUFFIX=c007-bad-1` + `--set-string services.agent.env.MCP_USE_OIDC=FALSE` | `make smoke SMOKE_ARGS="--tag c007-bad --only agent"` (espera FALHA com 403 do MCP); tráfego igual (§2) |
| T022 promover e voltar | §8 com `TARGET=c007` e depois `TARGET=previous`, com o laço de disponibilidade rodando | Estado final igual ao inicial (§2); só `200` no laço |
| T023 Plano B | §9 com `KEY=agent TAG=c007-planob` (e `KEY=mcp`) | `make smoke SMOKE_ARGS="--tag c007-planob --only agent"`; env conferido |
| T024 ensaio no Antigravity | [ensaio-antigravity.md](../specs/007-canal-deploy-demo/ensaio-antigravity.md) | Registro no mesmo arquivo |
| T025 vídeo de backup | [roteiro-demo.md](roteiro-demo.md#roteiro-do-vídeo-de-backup) | Link do vídeo no roteiro |
| Produção final (integração) | `deploy.yml` (ou §3) com `TAG=cNNN` nos três serviços; §8 na ordem MCP → agente → BFF | `make smoke` |
