# Dados e Tecnologia

Este documento descreve a camada de dados e tecnologia da PoC da Bússola para a Batalha de Agentes — Itaú x Google.

## 1. Dados financeiros e contexto do cliente

A Bússola parte da base sintética do desafio no BigQuery, com extratos de mil clientes, para compreender renda, gastos recorrentes, dívidas, reserva, investimentos, perfil de crédito e capacidade mensal de poupança ao longo do tempo.

Esses dados são complementados pelo contexto que o próprio cliente fornece na conversa — objetivo, valor-alvo, prazo, prioridade e recursos já disponíveis — e, como evolução de escopo, por informações de Open Finance, sempre mediante consentimento explícito.

## 2. Agente de Dados e Conhecimento — MCP

Um agente especializado funciona como ponte entre a experiência conversacional e as fontes de informação. O Agente Bússola faz consultas em linguagem natural, como:

- "Qual é o perfil financeiro do Fernando?"
- "Quanto ele consegue guardar por mês hoje?"
- "Onde existem oportunidades de redução de gastos?"
- "Quanto falta para a entrada do apartamento?"
- "O objetivo cabe no prazo desejado?"
- "Como o prazo muda se ele economizar mais R$ 300 por mês?"
- "Há dívidas que reduzem a capacidade de realizar o objetivo?"
- "Quais produtos do Itaú são adequados para este objetivo?"

O agente MCP traduz essas necessidades para consultas às fontes adequadas, sem expor SQL ou detalhes de infraestrutura ao agente conversacional.

## 3. Dados estruturados + RAG financeiro

O agente MCP combina duas classes de informação.

**Dados estruturados**, no BigQuery, são usados para números e cálculos relacionados ao cliente: renda, gastos, capacidade de poupança, saldo, dívidas, reserva, histórico e projeções.

**RAG financeiro**, por outro lado, fornece conhecimento atualizado sobre: produtos Itaú, jornadas, regras de elegibilidade, características de investimentos, crédito imobiliário, consórcio, políticas, educação financeira e informações de mercado relevantes.

Assim, condições comerciais e regras de produto não ficam hardcoded na aplicação, e cada recomendação pode ser explicada com base na fonte consultada.

## 4. Agente Conversacional — ia.i + Gemini / ADK

A ia.i conduz toda a experiência com o cliente, seguindo a jornada:

```text
OBJETIVO -> ENTENDER -> ANTECIPAR -> ORIENTAR -> AGIR -> ACOMPANHAR
```

Ela começa entendendo um objetivo, por exemplo:

> "Quero comprar meu primeiro apartamento."

Depois faz perguntas progressivas — apenas o que não consegue inferir dos dados — para entender valor-alvo, prazo, prioridades e restrições.

Com as informações recebidas do agente MCP, a Bússola simula cenários e apresenta caminhos comparáveis:

- **Caminho conservador** — prazo maior, menor esforço mensal e menor risco. Manter o padrão atual e reservar R$ 600/mês, atingindo a meta alguns meses depois.
- **Caminho equilibrado** — prazo viável, esforço moderado e ajustes pontuais no orçamento, combinando poupança com um produto financeiro adequado à meta.
- **Caminho acelerado** — prazo menor e maior disciplina. Reduzir determinados gastos e reservar R$ 900/mês.
- **Outro caminho** — o cliente descreve em linguagem natural o que gostaria de fazer.

Após o cliente escolher uma alternativa, a Bússola transforma aquela opção em um plano passo a passo, propõe próximos passos acionáveis, acompanha a evolução e recalcula a rota quando a realidade mudar — alertando quando o cliente se distancia do plano ou quando surge oportunidade de acelerar.

O modelo não inventa números financeiros nem decide pelo cliente: cálculos e regras permanecem nas camadas determinísticas e nas fontes consultadas, e o agente diferencia claramente diagnóstico, simulação e ação.

## 5. Segurança, governança e operação

A solução utiliza a infraestrutura GCP para garantir segurança, rastreabilidade e operação:

- **BigQuery / MCP read-only** para acesso controlado aos dados sintéticos;
- **Model Armor** para proteção de entrada e saída das interações com os modelos;
- **Secret Manager** para credenciais e chaves, sem exposição no código ou nas mensagens do agente;
- **Cloud Run** para execução da aplicação, dos conectores MCP e dos agentes;
- **Cloud Logging** e métricas para observabilidade e auditoria de decisões, chamadas de ferramenta e consentimentos;
- **Autonomia governada:** o agente analisa, simula, recomenda e acompanha com autonomia, mas contratação, compartilhamento de dados e qualquer alteração financeira exigem consentimento explícito;
- guardrails de Responsible AI e princípios previstos na Resolução Conjunta nº 8 sobre educação financeira.
