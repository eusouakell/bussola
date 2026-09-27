# Proposta de emenda à constituição: complemento do ciclo 007

**Status:** complemento da proposta do 000, **aguardando revisão do João**
(trilha B).
**Autor:** Victor (trilha A). **Data:** 2026-09-27.
**Base:** [specs/000-fundacao-contratos/proposta-constituicao.md](../000-fundacao-contratos/proposta-constituicao.md)
(trunk-based e deploy com Helm, versão alvo 1.1.0).

Este arquivo não repete a proposta do 000. Ele acrescenta ao **mesmo PR de
emenda** os três pontos que o 007 introduziu. A constituição continua
congelada: nada aqui altera `.specify/memory/constitution.md`.

## 1. O que o 007 acrescenta

1. **Promoção declarativa.**
   - Mover tráfego passa a ser o modo promoção do chart
     (`templates/promotion.yaml` + `deploy/helm/promote.jq`), aplicado com
     `gcloud run services replace`.
   - Não usa `gcloud run services update-traffic`.
   - Roda pelo `.github/workflows/promote.yml` (`workflow_dispatch`,
     environment `production`, confirmação digitada) ou pelo fluxo local de
     `docs/operacao.md` §8.
2. **Tag `cNNN-<rótulo>`.** Revisões de teste de um ciclo, como
   `c007-bad` (defeito proposital) e `c007-planob`, saem com tag própria e
   0% de tráfego. Sem isso, cada teste tomaria a `cNNN` do ciclo. O chart
   aceita `^(main|c[0-9]{3}(-[a-z]{1,10})?)$`. O `deploy.yml` segue só com
   `main` ou `cNNN`.
3. **Tag `previous`.** A promoção marca com `previous` a revisão que
   servia. O rollback é promover `previous`, também com confirmação humana.

## 2. Texto proposto (sobre o §2.3 do 000)

Princípio X, item de Cloud Run, na redação da proposta do 000, com o trecho
novo em negrito:

> - Cloud Run: toda revisão nova entra com 0% de tráfego e tag `main`
>   (rolante: a última revisão publicada pela `main`) ou `cNNN` (marco de um
>   ciclo, por disparo manual)**, ou `cNNN-<rótulo>` (revisão de teste do
>   ciclo)**. Só o ciclo 007 move tráfego, com confirmação humana**, pela
>   promoção do chart (`promote.yml` ou o fluxo local do runbook). A revisão
>   que servia recebe a tag `previous`, e o rollback é promovê-la**.

A versão continua 1.1.0 (MINOR): nenhum princípio sai, e a regra de 0% na
revisão nova fica igual.

## 3. O que muda fora da constituição (no mesmo PR)

| Arquivo | Mudança |
|---|---|
| `CLAUDE.md`, "Regras que não se negociam" | Na linha do Cloud Run proposta pelo 000, acrescentar: "Promover e voltar só pelo `promote.yml` ou pelo fluxo de `docs/operacao.md` §8." |
| `docs/ciclos/007-canal-deploy-demo.md` §6 e §7 | `smoke.sh`, `promover.sh`, `rollback.sh` e `plano_b.sh` passam a ser `make smoke`, `promote.yml` (alvo `cNNN`), `promote.yml` (alvo `previous`) e o overlay `values-plan-b.yaml` |

## 4. Decisão

- [ ] Aprovada pelo João (trilha B)
- [ ] Aprovada pelo Victor (trilha A)
- [ ] Incluída no PR da emenda 1.1.0
