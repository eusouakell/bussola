# Tasks: Canal da demo, deploy e operação no Antigravity

**Input**: `specs/007-canal-deploy-demo/` (spec.md, plan.md)

**Tests**: obrigatórios (constituição IX), offline em `make test`.

## Format: `[ID] [P?] Descrição (requisito)`

- `[P]`: pode rodar em paralelo (arquivos diferentes).
- `[ORQ]`: executado pelo orquestrador, com confirmação humana (GCP real).

## Phase 1: Setup

- [ ] T001 spec.md, plan.md e tasks.md do ciclo
- [ ] T002 Ler o estado vivo (`gcloud run services describe`, só leitura) de `bussola-mcp`, `bussola-agent` e `bussola-bff`

## Phase 2: Chart (US1, US4)

- [ ] T003 `values.yaml` igual ao estado vivo: imagens por digest, tráfego do `bff` e das tags `main`; `Chart.yaml` com os três serviços (FR-001)
- [ ] T004 [P] `values-plan-b.yaml` e `values-plan-a.yaml` (FR-002)
- [ ] T005 Modo promoção: `templates/promotion.yaml`, helper `bussola.promotion`, `deploy/helm/promote.jq` e templates de serviço desligados no modo promoção (FR-003)
- [ ] T006 Testes: overlays, promoção (guardas, tags, `previous`, rollback), `promote.jq` e default por digest em `deploy/tests/` (FR-006)

## Phase 3: Workflow (US1)

- [ ] T007 `.github/workflows/promote.yml` com environment `production`, confirmação digitada, WIF, dry-run e conferência (FR-004)
- [ ] T008 Uma linha no resumo do `deploy.yml` apontando para o `promote.yml` (edição mínima)
- [ ] T009 Testes de coerência do `promote.yml` com o chart e com as regras de tráfego (FR-006)

## Phase 4: Smoke (US2)

- [ ] T010 `deploy/smoke.py` (MCP `tools/list`, sessão ADK + `perfil_financeiro`, BFF `/` e `/auth/me`) (FR-005)
- [ ] T011 Testes unitários com fakes e integração com o MCP mock local e servidores fake do ADK e do BFF (FR-006)
- [ ] T012 Makefile: `shellcheck` no `lint`, `deploy/tests` no `test`, alvo `smoke` (FR-005, FR-007)
- [ ] T013 Diretivas `shellcheck` justificadas em `deploy/iam_datasets.sh` (FR-007)
- [ ] T014 Smoke só do BFF contra produção (GETs públicos, só leitura)

## Phase 5: Documentação (US3, US5)

- [ ] T015 [P] `AGENTS.md` (FR-008)
- [ ] T016 [P] `docs/operacao.md` (FR-009)
- [ ] T017 [P] `docs/roteiro-demo.md` + roteiro do vídeo de backup (FR-010)
- [ ] T018 Seção "Como rodar local / publicar" do README; `deploy/README.md` e `deploy/helm/README.md` atualizados (FR-011)
- [ ] T019 `ensaio-antigravity.md` (modelo), `proposta-constituicao.md` e `traceability.md` (FR-013)

## Phase 6: Polish

- [ ] T020 `make lint` e `make test` verdes; grep de chaves e tokens (SC-001, SC-003, FR-012)

## Orquestrador (GCP real, confirmação humana)

- [ ] T021 [ORQ] Publicar a revisão `c007` (values atuais) e `c007-bad` sem tráfego; smoke pela URL da tag
- [ ] T022 [ORQ] Promover `c007` → rollback (`previous`) no `bussola-agent`, medindo disponibilidade
- [ ] T023 [ORQ] Plano B em revisão com tag e 0% (`-f values-plan-b.yaml`, tag `c007`), smoke pela tag
- [ ] T024 [ORQ] Ensaio no Antigravity, registrado em `ensaio-antigravity.md`
- [ ] T025 [ORQ] Vídeo de backup (integração final)
