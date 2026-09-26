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

