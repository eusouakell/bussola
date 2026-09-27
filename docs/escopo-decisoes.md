# Escopo e Decisões

## Escopo confirmado

A Bússola é uma jornada agentic orientada a objetivos financeiros.

O escopo da PoC contempla:

- objetivo financeiro declarado pelo cliente;
- interpretação conversacional do objetivo;
- dados sintéticos no BigQuery;
- agente de dados/conhecimento via MCP;
- combinação de dados estruturados com RAG financeiro;
- orquestração com Gemini/ADK;
- execução em GCP, com Cloud Run;
- proteção com Model Armor;
- gestão de segredos com Secret Manager;
- auditoria e observabilidade com Cloud Logging;
- autonomia governada e consentimento;
- Open Finance como evolução.

## Fora do escopo da PoC

- uso de dados reais de clientes;
- contratação real de produtos financeiros;
- execução financeira sem consentimento;
- integração obrigatória com Open Finance no MVP;
- promessa de aprovação de crédito;
- substituição de assessoria financeira humana em casos regulados ou sensíveis.

## Hipóteses da PoC

- Os dados financeiros usados na demonstração são sintéticos.
- O cliente demonstrado é Fernando, 30 anos, interessado em comprar o primeiro apartamento.
- O agente pode recomendar próximos passos, mas ações sensíveis ficam condicionadas a consentimento explícito.
- A experiência deve ser explicável, auditável e compatível com um ambiente bancário.

## Critérios de sucesso

A demonstração deve deixar claro que a Bússola:

- entende o objetivo do cliente;
- transforma dados financeiros em diagnóstico;
- antecipa cenários;
- orienta com explicabilidade;
- propõe ações concretas;
- respeita consentimento e governança;
- acompanha a evolução do plano;
- conecta objetivos humanos ao ecossistema do banco.

