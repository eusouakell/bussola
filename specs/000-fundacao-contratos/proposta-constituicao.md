# Proposta de emenda à constituição: trunk-based e deploy com Helm

**Status:** proposta, **aguardando revisão do João** (trilha B).
**Autor:** Victor (trilha A). **Data:** 2026-09-26.
**Versão alvo:** 1.0.1 → 1.1.0 (MINOR).

A constituição está congelada desde o merge do 000. Por isso esta proposta
não altera `.specify/memory/constitution.md`. Se for aprovada, a emenda entra
num PR próprio, revisado pelas duas trilhas (Governance).

## 1. Por quê

1. **Somos duas pessoas.** O fluxo atual (1 ciclo = 1 worktree = 1 branch,
   rebase antes do PR, ordem de merge por ciclo) foi desenhado para até 8
   sessões em paralelo. Com duas pessoas, branches longas só acumulam rebase
   e conflito. Trunk-based mantém a `main` integrada o tempo todo, e os fakes
   (`BUSSOLA_FAKES=TRUE`) já permitem integrar trabalho incompleto sem quebrar
   nada.
2. **Deploy declarativo, não por script.** Hoje o deploy é o `deploy.sh`
   (`gcloud run deploy --image`), rodado à mão. O chart
   `deploy/helm/bussola` declara o estado desejado dos serviços, e o
   `helm template` valida as regras de plataforma antes de chegar ao GCP.
   Essas regras são: 0% de tráfego na revisão nova, tag válida, tráfego
   somando 100% e nenhum segredo em `env`. O chart tem testes no CI, e o
   GitHub Actions publica a cada push na `main`, só por WIF.
3. **Toda a `main` publicada.** Com deploy automático, a URL
   `main---<serviço>` sempre mostra a última revisão da `main`, sem tráfego
   de produção. O 007 continua sendo o único que promove.

## 2. Texto proposto

### 2.1 Seção "Fluxo de desenvolvimento" (substitui a seção inteira)

> ## Fluxo de desenvolvimento
>
> - Trunk-based: `main` é o tronco e MUST estar sempre publicável. Mudanças
>   pequenas entram direto na `main` ou por branches curtas (até cerca de um
>   dia), integradas por merge ou PR.
> - Todo push em branch que não é a `main` e todo PR MUST rodar o CI
>   (`.github/workflows/ci.yml`): `make lint`, `make test`, front web e BFF
>   (`web-lint`, `web-test`, `web-build`) e chart Helm (`helm-lint`,
>   `test-helm`). Todo push na `main` MUST rodar o CI e, verde, o deploy
>   (`.github/workflows/deploy.yml`). CI vermelho na `main` é prioridade de
>   quem quebrou.
> - Trabalho incompleto entra desligado (`BUSSOLA_FAKES=TRUE`, variável de
>   ambiente ou código ainda não roteado) e MUST NOT quebrar o que já está
>   na `main`.
> - Cada ciclo continua com spec própria e uma execução do Spec Master, com
>   `SPECIFY_FEATURE_DIRECTORY=specs/NNN-<slug>` fixo. Worktree por ciclo é
>   opcional: serve para rodar duas sessões em paralelo na mesma máquina.
> - Mudanças de contrato (`contracts: <mudança>`), de IAM, de tráfego e desta
>   constituição MUST ter revisão da outra pessoa antes de entrar na `main`.
>   O resto pode ter revisão depois do merge.
> - `.spec-master/` é local; a rastreabilidade de cada ciclo é exportada para
>   `specs/NNN-*/traceability.md` e versionada.

### 2.2 Seção "Restrições de plataforma", item de deploy

Hoje:

> - Deploy por imagem: `docker buildx --platform linux/amd64` → Artifact
>   Registry `agentes` → `gcloud run deploy --image`. `--source`,
>   `adk deploy` e Agent Runtime não são o caminho padrão (não há bucket de
>   staging).

Proposto:

> - Deploy por imagem, com Helm como templater, pelo GitHub Actions
>   (`deploy.yml`, autenticado só por WIF):
>   `docker buildx --platform linux/amd64` → Artifact Registry `agentes` →
>   `helm template deploy/helm/bussola` (imagem por digest e tráfego vivo
>   mantido) → `gcloud run services replace`. Não há `helm install` nem
>   GKE (org policy). `--source`, `adk deploy`, Agent Runtime e scripts de
>   deploy manuais não são o caminho padrão.

### 2.3 Princípio X, item de Cloud Run

Hoje:

> - Cloud Run: revisões com `--tag cNNN --no-traffic`; só o ciclo 007 move
>   tráfego.

Proposto:

> - Cloud Run: toda revisão nova entra com 0% de tráfego e tag `main`
>   (rolante: a última revisão publicada pela `main`) ou `cNNN` (marco de um
>   ciclo, por disparo manual). Só o ciclo 007 move tráfego, com confirmação
>   humana.

E, no rationale do X, trocar "8 ciclos rodam em worktrees paralelas" por
"os ciclos rodam em paralelo, com duas pessoas".

### 2.4 Versão

`**Version**: 1.1.0` e `**Last Amended**` com a data do PR da emenda. No
Sync Impact Report: seção "Fluxo de desenvolvimento" redefinida, item de
deploy em "Restrições de plataforma" e item de Cloud Run no X.

É MINOR porque nenhum princípio é removido: o X mantém a revisão nova sem
tráfego e o 007 como único a promover, e ganha a tag `main`. Se o time
entender que isso redefine o X, a versão vira 2.0.0 (MAJOR).

## 3. O que muda fora da constituição (no PR da emenda)

| Arquivo | Mudança |
|---|---|
| `CLAUDE.md`, "Fluxo de trabalho e PR" | Itens 1 a 3 viram: "1. Trunk-based: `main` é o tronco. Commits pequenos direto na `main` ou branches curtas. 2. Spec por ciclo com `SPECIFY_FEATURE_DIRECTORY=specs/NNN-<slug>`; worktree opcional. 3. CI (`ci.yml`) em todo push de branch e PR; push na `main` roda CI e deploy (`deploy.yml`)." |
| `CLAUDE.md`, "Regras que não se negociam" | "Cloud Run: novas revisões com `--tag cNNN --no-traffic`" vira "Cloud Run: revisão nova com 0% de tráfego e tag `main` (deploy automático) ou `cNNN` (manual). Só o 007 move tráfego." |
| `docs/ciclos/README.md` §5 | Item 1: worktree opcional. Item 3: Trunk-Based sem branch de ciclo obrigatória. Item 9 (Cloud Run): texto do §2.3. Item 10: "Rebase antes do PR" vira "CI verde em todo push; a `main` sempre publicável". |
| `docs/ciclos/roadmap-2-pessoas.md` §4 | A "ordem de merge" vira ordem de integração na `main`. A coluna "Revisor" vale para `contracts:`, IAM, tráfego e constituição; o resto tem revisão depois do merge. |
| `deploy/build_push.sh`, `deploy/deploy.sh` | Removidos, com a linha correspondente do `deploy/README.md`. |

## 4. Já aplicado na `main`, antes da emenda

A pedido do Victor, entraram na `main` antes desta aprovação:

- `ci.yml`: CI em todo push de branch que não é a `main` e em todo PR, com
  os jobs de front/BFF e Helm;
- `deploy.yml`: deploy com Helm a cada push na `main`, com a tag `main` e
  0% de tráfego;
- o chart aceita `release.tag=main` além de `cNNN`;
- o teste de contrato `mcp_server/tests/contrato/test_workflows.py` (Q-18)
  passou a exigir esses gatilhos e o deploy com Helm sem scripts. Os
  invariantes continuam: só WIF, deploy só depois do CI, nada de tráfego ou
  IAM e nenhuma entrada do disparo no shell. **Precisa da revisão do João**,
  como todo `contracts:`.

O deploy segue **inerte** até o owner criar o WIF (pedido 5): sem
`GCP_WIF_PROVIDER` e `GCP_DEPLOY_SA`, o push na `main` roda só o CI. Se a
emenda for recusada, o `deploy.yml` volta a ser só manual com `cNNN` e o
chart volta a recusar `main` (e o teste de contrato volta junto). O `ci.yml`
e os scripts antigos não precisam mudar.

## 5. Decisão

- [ ] Aprovada pelo João (trilha B)
- [ ] Aprovada pelo Victor (trilha A)
- [ ] PR da emenda aberto (`docs: emenda da constituição 1.1.0`)
