# Proposta de emenda à constituição (ciclo 008)

**Tipo:** MINOR (seção ampliada, aditiva). **Status:** proposta para
discussão no time; não aplicada (constituição congelada, Governance).

## Motivo

O ciclo 008 entrega um front React em `web/` (pedido do time, 26/09/2026;
roadmap §5 e pessoa B §5.3). A seção "Restrições de plataforma" lista só a
stack Python, e o princípio IX só cita `make lint` e `make test`. O plano do
008 registra a exceção em Complexity Tracking.

## Texto proposto

Em **Restrições de plataforma**, acrescentar ao item "Stack":

> Front web em `web/`: TypeScript, React, Vite e Tailwind CSS v4, com Node 24
> e `npm` (lockfile versionado). O build estático é servido pelo
> `bussola-agent` na mesma origem. O front não acessa GCP nem BigQuery e só
> fala com o agente pela API HTTP do ADK.

Em **IX. Testes obrigatórios e gates sem rede**, acrescentar:

> PRs que tocam `web/` MUST passar `make web-lint`, `make web-test` e
> `make web-build` sem rede. O `make web-build` inclui a varredura do bundle
> por segredos, SQL, nome de projeto e UUID completo de cliente.

## Impacto

- Nenhum princípio muda de sentido. Nenhum ciclo em andamento é afetado.
- O 007 passa a ter base para o estágio Node no `Dockerfile` do agente.
