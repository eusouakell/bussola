# Bússola

**Uma jornada agentic que transforma sonhos e objetivos financeiros em planos executáveis.**

Bússola é uma proposta para a **Batalha de Agentes**. O agente parte de um objetivo declarado pelo cliente, entende sua situação financeira, antecipa cenários, orienta a tomada de decisão, aciona próximos passos com consentimento e acompanha a evolução até a realização do objetivo.

> **Projeto concluído · outubro de 2026.** Esta é a documentação histórica de uma prova de conceito desenvolvida em equipe para a Batalha de Agentes. **O protótipo estático e simulado permanece público no GitHub Pages; somente a landing page do case foi descontinuada.** Não há produto bancário em operação nem novo roadmap de desenvolvimento. [Registro de encerramento](docs/PROJECT-CLOSURE-2026-10.md).

## Protótipo navegável — demonstração preservada

**[Abrir o protótipo da Bússola](https://eusouakell.github.io/bussola/)**

Explore a jornada simulada de Fernando, persona criada pela equipe para planejar a compra do primeiro apartamento. A experiência usa dados sintéticos e não constitui serviço bancário, aprovação de crédito ou atendimento real do Itaú. O GitHub Pages deve permanecer ativado.

## Evidências e materiais preservados

- [Context Engineering: estudo de caso](docs/context-engineering-case-study.md), documentado como parte do aprendizado.
- [Código do protótipo simulado](web/) e [documentação de operação](docs/operacao.md), disponíveis para consulta histórica.
- [Auditoria de UX/UI e UX Writing](web/public/auditoria/index.html) e [fonte HTML da landing page do case](web/public/case/index.html), mantidos no repositório como evidência. **A rota pública `/bussola/case/` não integra mais o artefato publicado.**
- [Arquitetura](docs/arquitetura.md), [decisões](docs/escopo-decisoes.md), [ficha de submissão](docs/ficha-submissao.md) e histórico de PRs.

O encerramento não implica certificação de prontidão de produção, ganho medido de produtividade nem validação financeira das recomendações.

## Auditoria de UX/UI e UX Writing

O projeto documenta a evolução da experiência com um [relatório visual antes/depois](web/public/auditoria/index.html): scorecard heurístico, problemas rastreáveis no código, soluções propostas e melhorias implementadas. O relatório distingue correções de interface de testes ainda pendentes; a nota pós-melhoria depende de validação.

Para revisar o HTML no repositório: [web/public/auditoria/index.html](web/public/auditoria/index.html).

## Colaboração e autoria

Bússola foi desenvolvida em equipe para a **Batalha de Agentes — Itaú × Google**. **Victor Lopes ([theguitarvity](https://github.com/theguitarvity)) originou e liderou o repositório e a implementação técnica.**

Este é o fork de Kell Bonassoli e registra sua participação no projeto, especialmente na camada de estratégia, contexto, pesquisa, Responsible AI, narrativa e materiais compartilhados. O enquadramento do produto e os materiais de apoio foram desenvolvidos colaborativamente pela equipe. Este fork não representa uma reivindicação de autoria técnica exclusiva de Kell.

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

A PoC demonstra Fernando, 30 anos, cliente pessoa física, usando o app do banco para planejar a compra do primeiro apartamento.

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

- **Experiência:** app do banco (chat web).
- **Orquestração agentic:** Gemini e ADK.
- **Dados sintéticos:** BigQuery.
- **Conhecimento:** RAG financeiro com políticas, produtos, regras e conteúdos de educação financeira.
- **Integração:** MCP para ferramentas de dados e conhecimento.
- **Execução:** Cloud Run.
- **Segurança:** Model Armor, Secret Manager, controles de consentimento e autonomia governada.
- **Observabilidade:** Cloud Logging.

## Reprodução local e arquitetura histórica (sem manutenção)

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

### Implantação Cloud Run (histórico, desativada)

O projeto utilizou uma arquitetura de referência com ADK, MCP, BigQuery, RAG e Cloud Run. Os procedimentos históricos constam de [docs/operacao.md](docs/operacao.md) e do histórico do Git. Os workflows de deploy e promoção da nuvem foram removidos do fork e **não devem ser reativados como parte da manutenção estática do protótipo**.

O GitHub Pages publica exclusivamente a demonstração estática, sem credenciais ou dependência dos serviços GCP originais. A landing page `/case/` é excluída durante o build, mas seu código-fonte permanece preservado.

## Arquitetura de contexto

O projeto também oferece um caso aplicado para estudar como agentes dependem de camadas distintas de contexto:

```text
OBJETIVO DO USUÁRIO
→ SAÚDE FINANCEIRA
→ DADOS CONHECIDOS vs INFERIDOS
→ CENÁRIOS DETERMINÍSTICOS
→ PRODUTOS / POLÍTICAS
→ RAG REGULATÓRIO
→ CONSENTIMENTO + ESCOPO DE AÇÃO
→ AGENTE / FERRAMENTAS
→ RASTREABILIDADE + ACOMPANHAMENTO
```

As regras de projeto incluem preservar fontes e confiança, evitar inferências demográficas sem dados, usar ferramentas determinísticas para números, distinguir regras atuais de futuras e exigir consentimento antes de ações sensíveis.

O [estudo de caso de Context Engineering](docs/context-engineering-case-study.md) conecta essas camadas à documentação pública existente. Descreve a arquitetura e seus limites; não apresenta resultados de avaliação novos.

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
