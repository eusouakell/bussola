# Ficha de Submissão — Parte 1 do Projeto

**Batalha de Agentes — Itaú x Google**  
**Versão alinhada ao case oficial — 26/09/2026**

## Nome do agente

# Bússola

**Uma jornada da ia.i que transforma sonhos e objetivos financeiros em planos executáveis.**

## Equipe

**Grupo 07 — Sala 215**

- Carlos Guevara
- João Paulo Soares Lopes
- Kell Bonassoli
- Victor Lucas Lopes

**Mentora:** Yasmin Mafra Maroum

## O problema

Clientes têm objetivos financeiros concretos, como comprar um imóvel, viajar, estudar, trocar de carro, formar uma reserva ou reorganizar dívidas. Porém, muitas vezes não conseguem transformar sua situação financeira atual em um plano claro de decisão e ação.

A gestão financeira acontece em frentes conectadas: organizar o hoje, construir o amanhã e usar crédito a favor do cliente. Na prática, o cliente precisa juntar sozinho renda, gastos, reservas, dívidas, crédito, capacidade de pagamento e prazo para descobrir se um sonho é viável.

### Evidência e impacto

O case oficial reforça que o cliente quer mais do que produtos: quer ajuda para decidir na hora certa. Existe interesse em se organizar financeiramente, mas ainda há barreiras de letramento, engajamento e clareza sobre os próximos passos.

Quando o banco apresenta produtos sem antes compreender o objetivo do cliente, a experiência fica transacional. A Bússola muda esse ponto de partida: primeiro entende o sonho, depois estrutura o caminho financeiro e, só então, conecta produtos, ações e recomendações adequadas.

## Momento do usuário

### Persona

Carlos, 30 anos, cliente pessoa física com um sonho ou objetivo financeiro concreto.

### Caso demonstrado na PoC

Fernando, 30 anos, quer comprar seu primeiro apartamento.

### Gatilhos de uso

O cliente abre a ia.i e diz:

- "Quero comprar um apartamento. O que eu preciso fazer para conseguir?"
- "Quero viajar no ano que vem. Quanto preciso guardar?"
- "Quero fazer uma pós. Como encaixo isso na minha vida financeira?"

A Bússola usa os dados disponíveis e pergunta apenas o que não consegue inferir: objetivo, valor-alvo aproximado, prazo desejado, prioridade e recursos já disponíveis.

## Proposta do agente

### Proposta de valor

A Bússola completa a jornada da ia.i transformando dados financeiros em contexto, contexto em previsão e previsão em plano executável.

O agente guia o cliente por uma sequência simples:

```text
OBJETIVO -> ENTENDER -> ANTECIPAR -> ORIENTAR -> AGIR -> ACOMPANHAR
```

### Como funciona

1. **Objetivo:** o cliente declara o que quer realizar.
2. **Entender:** a Bússola interpreta intenção, prazo, valor estimado, prioridade e restrições.
3. **Antecipar:** o agente cruza dados financeiros sintéticos com conhecimento financeiro para simular cenários.
4. **Orientar:** apresenta caminhos possíveis, trade-offs e recomendações explicáveis.
5. **Agir:** sugere próximos passos e só executa ações sensíveis mediante consentimento.
6. **Acompanhar:** monitora progresso, recalcula rota e alerta quando o plano precisa mudar.

## Diferencial

A Bússola não é apenas um chatbot financeiro. Ela funciona como uma jornada agentic orientada a objetivos, capaz de combinar:

- entendimento conversacional;
- dados financeiros estruturados;
- conhecimento financeiro recuperado por RAG;
- simulação de cenários;
- recomendações explicáveis;
- autonomia governada;
- consentimento explícito para ações sensíveis;
- acompanhamento contínuo.

## Arquitetura proposta

A solução usa a ia.i como interface de conversa e o Gemini/ADK como base de orquestração agentic. Um agente de dados e conhecimento acessa ferramentas via MCP, combinando dados sintéticos no BigQuery com RAG financeiro.

A camada de execução roda em Cloud Run, com segredos no Secret Manager, proteção de entrada e saída por Model Armor e rastreabilidade via Cloud Logging.

Open Finance é tratado como evolução: no MVP, a PoC usa dados sintéticos; na visão futura, o cliente poderá consentir o uso de dados externos para ampliar a precisão do diagnóstico.

## Resultado esperado

Ao final da experiência, o cliente sai com:

- diagnóstico da situação atual;
- viabilidade do objetivo;
- cenários possíveis;
- plano financeiro mensal;
- próximos passos priorizados;
- recomendações conectadas ao ecossistema Itaú;
- acompanhamento contínuo pela ia.i.

