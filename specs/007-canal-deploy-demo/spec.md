# Feature Specification: Canal da demo, deploy e operação no Antigravity

**Feature Branch**: `007-canal-deploy-demo`

**Created**: 2026-09-26

**Status**: Draft

**Input**: `docs/ciclos/007-canal-deploy-demo.md`, adaptado às decisões do
usuário registradas depois dele: deploy com Helm (sem GKE, sem script),
trunk-based, front próprio `web/` + BFF público como canal (Q4 fechada),
nomes de artefatos em inglês e documentação em pt-BR.

> **Nota.** O ciclo empacota, publica e documenta. Não altera código dos
> serviços, `contracts/`, `web/` nem Dockerfiles.

## Clarifications

### Session 2026-09-26

Resolvidas sem perguntar ao usuário (regra do disparo). Classificação entre
parênteses.

- Q: `config.sh`, `deploy_*.sh`, `promover.sh`, `rollback.sh`, `plano_b.sh`
  e `smoke.sh` do documento do ciclo? → A: substituídos pelo chart Helm já na
  `main` (`deploy/helm/bussola`), por overlays de values
  (`values-plan-a.yaml`, `values-plan-b.yaml`), pelo workflow
  `promote.yml` e por `deploy/smoke.py`. Decisão do usuário: deploy com Helm,
  não script. (EXPLICIT)
- Q: Remover `deploy/build_push.sh` e `deploy/deploy.sh`? → A: não. O teste
  de contrato `mcp_server/tests/contrato/test_politicas_repo.py` (fora dos
  caminhos do 007) exige os dois, e a retirada depende da emenda da
  constituição do 000. Ficam como caminho de emergência, com `shellcheck` no
  `make lint`. (RESOLVABLE_FROM_CONTEXT)
- Q: IAM como script? → A: não. Os comandos de IAM ficam como referência em
  `docs/operacao.md`, para um integrante rodar com confirmação humana. O
  `iam_datasets.sh` do 000 continua (exigido pelo teste de contrato) e já é
  simulação por padrão, com confirmação digitada. (EXPLICIT)
- Q: Como promover com `gcloud run services replace` sem criar revisão? →
  A: o chart ganha o modo promoção (`templates/promotion.yaml`). Ele copia o
  `spec.template` vivo sem mudança (mesmo nome, nenhuma revisão nova) e troca
  só o tráfego: 100% no alvo, tags preservadas e a tag `previous` na revisão
  que servia. Rollback = promover `previous`. (INFERRED)
- Q: O smoke valida a citação de `perfil_financeiro` como? → A: exige a
  chamada da ferramenta `perfil_financeiro` nos eventos do ADK (fonte
  verificável). A menção no texto vira aviso, porque a redação é do LLM.
  (SAFE_DEFAULT)
- Q: Saúde do BFF em produção? → A: o Cloud Run reserva `/healthz` (o GFE
  responde 404 antes do contêiner). O smoke usa `GET /` (200, HTML) e
  `GET /auth/me` (401 `NAO_AUTENTICADO`, JSON do BFF). Mudar a rota é do
  dono de `web/`. (RESOLVABLE_FROM_CONTEXT)
- Q: Quem roda deploy, promoção, rollback e Plano B reais? → A: o
  orquestrador, com confirmação humana. Este ciclo roda só leitura
  (`describe`, `list`, `logging read`, GETs públicos do BFF) e deixa os
  comandos exatos em `docs/operacao.md` e no relatório. (EXPLICIT)
- Q: Environment protegido do `promote.yml`? → A: `production`, com
  revisores obrigatórios. Um admin do repositório cria o environment; sem
  ele, o GitHub cria um environment sem proteção, por isso o workflow também
  exige digitar o nome do serviço. (SAFE_DEFAULT)

## User Scenarios & Testing

### User Story 1: Promover e voltar com segurança (P1)

O integrante publica uma revisão com tag e 0% de tráfego (deploy.yml, sem
mudança), testa pela URL da tag e promove com aprovação humana. Se der
errado, volta para a revisão anterior.

**Acceptance**:

1. **Given** uma revisão `main` pronta, **when** o `promote.yml` roda com
   `target=main` e é aprovado no environment, **then** ela recebe 100% e a
   revisão anterior fica com a tag `previous`, sem revisão nova.
2. **Given** a promoção acima, **when** roda com `target=previous`, **then**
   o tráfego volta para a revisão anterior.
3. **Given** tráfego dividido, alvo inexistente, alvo já com 100% ou drift
   de `public`/ingress, **then** o `helm template` falha antes do GCP.

### User Story 2: Smoke de produção (P1)

**Acceptance**: `make smoke` lista as ferramentas do MCP com ID token
(audience = URL principal), abre uma sessão no agente, pergunta "qual é o
meu perfil financeiro?", confere a chamada de `perfil_financeiro` e confere
`/` e `/auth/me` do BFF. Nenhum token aparece na saída. Código de saída 0 só
com tudo OK.

### User Story 3: Operar pelo Antigravity (P1)

**Acceptance**: `AGENTS.md` e `docs/operacao.md` bastam para responder
"status dos serviços", "últimos erros", "consentimentos da última sessão" e
para pedir confirmação antes de "faça rollback do agente".

### User Story 4: Plano A e Plano B por overlay (P2)

**Acceptance**: `-f values-plan-b.yaml` renderiza `BQ_MODO_LEITURA=memoria`,
`RAG_BACKEND=lexico`, `GOOGLE_GENAI_USE_VERTEXAI=FALSE` e `GOOGLE_API_KEY`
por `secretKeyRef`. `-f values-plan-a.yaml` renderiza Vertex, `query`,
`numpy`, SA `bussola-runtime` e nenhuma chave. Nenhum deles lê a chave no
deploy.

### User Story 5: Roteiro da demo e README (P2)

**Acceptance**: `docs/roteiro-demo.md` cabe em 5 min, passa pelos 6 estados,
pelo "sim" do consentimento e por um avanço de mês com desvio, e tem
checklist, contingência e roteiro do vídeo de backup. O README explica como
rodar local e publicar.

### Edge Cases

- Tag URL como audience do ID token: 401. O smoke sempre usa a URL
  principal como audience, mesmo chamando a URL da tag.
- `MCP_USE_OIDC=FALSE` em produção: 403 do MCP. Documentado.
- Restart ou segunda instância: a sessão em memória se perde. Documentado
  (`max-instances=1`, nova sessão, auditoria preservada no BigQuery).
- Promoção concorrente com deploy: mesmo grupo de `concurrency`.

## Requirements

- **FR-001** `values.yaml` espelha o estado vivo (imagens por digest,
  tráfego, SA, env e secretEnv), conferido com `gcloud run services
  describe`.
- **FR-002** Overlays `values-plan-a.yaml` e `values-plan-b.yaml`, com a
  chave só por `secretKeyRef`.
- **FR-003** Modo promoção no chart: `templates/promotion.yaml` +
  `deploy/helm/promote.jq`, com as guardas da US1.
- **FR-004** `.github/workflows/promote.yml`: `workflow_dispatch`
  (serviço, alvo, confirmação), environment `production`, WIF, render pelo
  chart, `replace --dry-run` e `replace`, conferência de 100% no alvo e de
  nenhuma revisão nova. `ci.yml` e `deploy.yml` seguem sem tráfego.
- **FR-005** `deploy/smoke.py` + `make smoke` (US2), só stdlib, com
  transporte, token e URLs injetáveis.
- **FR-006** Testes offline em `deploy/tests/` (chart, overlays, promoção,
  workflows, smoke com fakes e com o MCP mock local) dentro de `make test`.
- **FR-007** `shellcheck` dos `.sh` restantes no `make lint`.
- **FR-008** `AGENTS.md` na raiz.
- **FR-009** `docs/operacao.md` com as seções do ciclo §3.3 e a
  confirmação humana explícita para tráfego e IAM.
- **FR-010** `docs/roteiro-demo.md` + roteiro do vídeo de backup.
- **FR-011** Seção "Como rodar local / publicar" do README.
- **FR-012** Nenhum `echo` de chave ou token em código ou documentação.
- **FR-013** `specs/007-canal-deploy-demo/ensaio-antigravity.md` (modelo do
  ensaio, preenchido na integração).

## Success Criteria

- **SC-001** `make lint` e `make test` verdes, sem rede e sem GCP.
- **SC-002** Critérios §6 do ciclo com status registrado em
  `traceability.md`; os que dependem do orquestrador têm o comando exato em
  `docs/operacao.md`.
- **SC-003** `grep` por padrões de chave e token no repositório: nada.
