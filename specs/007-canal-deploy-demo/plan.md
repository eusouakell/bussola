# Implementation Plan: Canal da demo, deploy e operação no Antigravity

**Branch**: `007-canal-deploy-demo` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)

## Summary

Fechar o caminho de produção sobre o que o 000 e o 008 já deixaram na `main`
(chart Helm, `traffic.jq`, `ci.yml`, `deploy.yml`, BFF público):

1. values do chart iguais ao estado vivo e overlays de Plano A e B;
2. modo promoção no chart e workflow `promote.yml` com aprovação humana;
3. smoke de produção em Python (`deploy/smoke.py`);
4. runbook para o Antigravity (`AGENTS.md`, `docs/operacao.md`), roteiro
   da demo e README.

## Technical Context

- **Deploy**: Helm 4.2.4 só como templater; `gcloud run services replace`
  aplica o manifesto Knative. Sem GKE.
- **Promoção**: `gcloud run services describe` → `promote.jq` (estado vivo
  como values) → `helm template --show-only templates/promotion.yaml` →
  `replace --dry-run` → `replace`.
- **Smoke**: Python 3.12, só stdlib (`urllib`, `subprocess`, `json`), roda
  no ambiente `uv` do `agent/`. ID token por
  `gcloud auth print-identity-token --impersonate-service-account=<SA>
  --audiences=<URL principal>`.
- **Testes**: pytest em `deploy/tests/`, pelo ambiente do `agent/`
  (pyyaml disponível). Helm e jq opcionais (testes pulados sem eles). O
  teste de integração do smoke sobe o MCP mock real (`mcp_server`) em
  `127.0.0.1` e fakes do ADK e do BFF em `http.server`.
- **Lint**: ruff (já cobre `deploy/`) + `shellcheck` nos `.sh` de
  `deploy/` (binário do sistema ou `uvx shellcheck-py` como alternativa).

## Constitution Check

| Princípio | Como o plano atende |
|---|---|
| VII Segredos | `secretKeyRef` nos overlays; smoke guarda o token em memória e nunca o imprime; docs mostram comandos que mantêm tokens em variáveis |
| IX Testes | render do chart, promoção, overlays, workflows e smoke com fakes, tudo offline em `make test` |
| X Tráfego | só o `promote.yml` (e o fluxo local equivalente) muda percentuais, com environment protegido e confirmação digitada; `ci.yml` e `deploy.yml` intactos quanto a tráfego |
| Emenda do 000 | trunk-based e Helm dependem da proposta do 000; ver [proposta-constituicao.md](./proposta-constituicao.md) |

## Design

### Modo promoção do chart

- Entrada: `promotion.service` (`mcp|agent|bff`), `promotion.target` (tag
  `main`, `cNNN`, `previous` ou nome de revisão) e `promotion.live` (saída
  do `promote.jq`: nome, `spec.template` verbatim, tráfego, `public`,
  ingress).
- Guardas: serviço conhecido; estado vivo do mesmo serviço; `public` e
  ingress vivos iguais aos values; exatamente uma revisão com 100%; alvo
  presente no tráfego vivo; alvo diferente da revisão atual.
- Saída: alvo com 100%, todas as tags vivas com 0% (menos `previous`) e
  `previous` na revisão que servia. `spec.template` igual ao vivo: o
  `replace` não cria revisão.
- Os templates de serviço ficam desligados no modo promoção (o Helm
  renderiza todos, mesmo com `--show-only`).

### Workflow `promote.yml`

`check` (entradas, confirmação, WIF) → `promote` (environment
`production`, `id-token: write`): estado vivo, alvo pronto
(`revisions describe`), render, dry-run, replace, conferência (100% no
alvo, `latestCreatedRevisionName` igual) e resumo com o comando de rollback.
Mesmo grupo de `concurrency` do `deploy.yml`.

### Smoke

Três checagens independentes (`mcp`, `agent`, `bff`), cada uma devolve
`CheckResult(ok, detail, warnings)`. `Transport`, `TokenProvider` e URLs são
injetáveis. Padrão: o caminho da demo (BFF público → agente na tag `main`
→ MCP principal), igual aos values; `--tag` e `--principal` trocam o alvo.

## Project Structure (arquivos do ciclo)

```text
deploy/helm/bussola/{values.yaml, values-plan-a.yaml, values-plan-b.yaml, Chart.yaml}
deploy/helm/bussola/templates/{promotion.yaml, _helpers.tpl, *-service.yaml}
deploy/helm/{promote.jq, README.md}
deploy/{smoke.py, README.md, iam_datasets.sh (diretivas shellcheck)}
deploy/tests/{conftest.py, test_helm_chart.py, test_promotion.py, test_smoke.py}
.github/workflows/promote.yml (+1 linha no resumo do deploy.yml)
AGENTS.md, docs/operacao.md, docs/roteiro-demo.md, README.md (seção)
Makefile (acréscimos: shellcheck, deploy/tests no test, smoke)
```

## Riscos

- Environment `production` sem revisores se o admin não o configurar:
  mitigado pela confirmação digitada e registrado como pendência.
- Roteiro depende de 004/005/006 (falas e ferramentas): linhas marcadas
  "confirmar na integração".
