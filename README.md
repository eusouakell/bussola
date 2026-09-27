# Bússola

**Uma jornada agentic da ia.i que transforma sonhos e objetivos financeiros em planos executáveis.**

Bússola é uma proposta para a **Batalha de Agentes — Itaú x Google**. O agente parte de um objetivo declarado pelo cliente, entende sua situação financeira, antecipa cenários, orienta a tomada de decisão, aciona próximos passos com consentimento e acompanha a evolução até a realização do objetivo.

## Norte do produto

O cliente não começa escolhendo um produto bancário. Ele começa com uma intenção humana:

- comprar o primeiro apartamento;
- viajar no ano que vem;
- fazer uma pós-graduação;
- trocar de carro;
- formar reserva;
- reorganizar dívidas;
- realizar outro objetivo financeiro concreto.

A Bússola traduz essa intenção em uma jornada estruturada:

```text
OBJETIVO -> ENTENDER -> ANTECIPAR -> ORIENTAR -> AGIR -> ACOMPANHAR
```

## Escopo da PoC

A PoC demonstra Fernando, 30 anos, cliente pessoa física, usando a ia.i para planejar a compra do primeiro apartamento.

A Bússola deve:

- interpretar o objetivo financeiro informado pelo cliente;
- consultar dados sintéticos organizados no BigQuery;
- combinar dados estruturados com RAG financeiro;
- usar um agente de dados/conhecimento via MCP;
- gerar diagnóstico, cenários e plano de ação;
- recomendar próximos passos com autonomia governada;
- pedir consentimento antes de qualquer ação sensível;
- registrar decisões e eventos para auditoria;
- tratar Open Finance como evolução de escopo.

## Stack de referência

- **Experiência:** ia.i.
- **Orquestração agentic:** Gemini e ADK.
- **Dados sintéticos:** BigQuery.
- **Conhecimento:** RAG financeiro com políticas, produtos, regras e conteúdos de educação financeira.
- **Integração:** MCP para ferramentas de dados e conhecimento.
- **Execução:** Cloud Run.
- **Segurança:** Model Armor, Secret Manager, controles de consentimento e autonomia governada.
- **Observabilidade:** Cloud Logging.

## Como rodar local / publicar

Pré-requisitos: [`uv`](https://docs.astral.sh/uv/), Node 24 (front), `jq` e
`helm` v4 (deploy). Os dados são sintéticos. Segredos só no `.env` local
(não versionado) ou no Secret Manager, nunca no repositório.

### Local, com dados fake

```bash
cp contracts/env.example .env   # ajuste; o .env não é versionado
make mcp     # MCP em http://localhost:8080/mcp (BUSSOLA_FAKES=TRUE)
make agent   # ADK Web em http://localhost:8000, falando com o MCP local
make lint && make test          # o que o CI roda; sem rede e sem GCP
```

Com `BUSSOLA_FAKES=TRUE`, ferramentas e persistência usam fakes e
`contracts/fixtures/`, sem BigQuery. O LLM do `make agent` ainda precisa de
credencial: ADC do Vertex (`gcloud auth application-default login`) ou
`GOOGLE_API_KEY` no `.env` (Plano B).

O front (ciclo 008):

```bash
make web-install && make web    # http://localhost:5173
```

Na barra "Modo demonstração", o `Simulado` roda sem rede. O `Ao vivo (ADK)`
usa o `make agent` pelo proxy do Vite. O BFF (`make bff`) precisa de
`AUTH_PASSWORD_HASH` no `.env` ([web/README.md](web/README.md#bff-webbff)).

### Local, com GCP

1. Autentique: `gcloud auth login` e `gcloud auth application-default login`.
2. No `.env`, use `BUSSOLA_FAKES=FALSE` e escolha o plano do LLM:
   - Plano A: `GOOGLE_GENAI_USE_VERTEXAI=TRUE`;
   - Plano B: `FALSE` + `GOOGLE_API_KEY` no `.env`.
3. Rode `make mcp` e `make agent`.

Os testes contra o BigQuery real: `make test-bq` (gravam só em
`bussola_app_dev`).

### Publicar no Cloud Run

O deploy é o chart Helm `deploy/helm/bussola`, usado só como templater e
aplicado com `gcloud run services replace`. Não existe GKE. A revisão nova
sai **sempre com tag e 0% de tráfego**. Só a promoção move tráfego, com
confirmação humana.

| Passo | Como |
|---|---|
| Publicar (tag `main` ou `cNNN`, 0%) | Push na `main` → `.github/workflows/deploy.yml`. Sem WIF: fluxo local de [operacao.md §3](docs/operacao.md#3-deploy-de-uma-versão-nova) |
| Testar a revisão pela tag | `make smoke SMOKE_ARGS="--tag cNNN --only agent"` ([operacao.md §4](docs/operacao.md#4-smoke)) |
| Promover ou voltar | `.github/workflows/promote.yml` (aprovação no environment `production`) ou o fluxo local de [operacao.md §8](docs/operacao.md#8-promoção-e-rollback) |
| Conferir produção | `make smoke` |

Mais detalhes:

- operação, logs, auditoria, rollback e Plano B: [docs/operacao.md](docs/operacao.md);
- roteiro da demo (≤ 5 min): [docs/roteiro-demo.md](docs/roteiro-demo.md);
- chart e guardas: [deploy/helm/README.md](deploy/helm/README.md);
- operação por agente (Antigravity): [AGENTS.md](AGENTS.md).

## Documentação

- [Ficha de submissão](./docs/ficha-submissao.md)
- [Arquitetura](./docs/arquitetura.md)
- [Dados e tecnologia](./docs/dados-tecnologia.md)
- [Jornada agentic](./docs/jornada-agentic.md)
- [Escopo e decisões](./docs/escopo-decisoes.md)
- [Contexto de implementação (Spec Master)](./docs/contexto-spec-master.md)
- [Blueprint de arquitetura](./docs/blueprint-arquitetura.md)
- [Plano de ciclos paralelos (Spec Master)](./docs/ciclos/README.md)
- [Contratos entre ciclos](./docs/ciclos/contratos.md)

