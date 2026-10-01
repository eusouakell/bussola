# Reactivation plan — colocar a Bússola de volta no ar

> Estado em 01/10/2026: a infraestrutura GCP usada no hackathon foi encerrada. O repositório continua reproduzível localmente e o front possui um modo simulado sem rede.

## Objetivo

Voltar a ter uma URL pública útil para portfólio e demonstração sem transformar uma PoC em um serviço financeiro aberto ao público, sem depender da antiga conta do hackathon e sem criar custo desnecessário.

## Recomendação

Usar **dois ambientes com propósitos diferentes**:

### 1. Demo pública — simulada e estática

Para qualquer visitante.

```text
Browser
  ↓
React/Vite
  ↓
Agente simulado
  ↓
Fixtures sintéticas
```

Características:

- sem GCP;
- sem backend;
- sem chave de modelo;
- sem BigQuery;
- sem login real;
- sem custo de inferência;
- demonstra toda a jornada e os estados de UX;
- pode ser hospedada em Netlify, Cloudflare Pages ou GitHub Pages.

O front já suporta esse desenho: o modo `simulado` é o padrão e funciona sem rede.

**CTA público recomendado:**  
**Explorar a Bússola com Fernando — dados sintéticos**

### 2. Live Lab — agentic e controlado

Para demos, recrutadores, palestras, estudos técnicos e revisão do time.

```text
Browser
  ↓
BFF
  ↓
ADK Agent
  ↓
MCP
  ↓
fixtures/memória + Gemini API
```

Características:

- acesso controlado;
- Gemini/ADK real;
- MCP real;
- dados sintéticos;
- `BUSSOLA_FAKES=TRUE` inicialmente;
- sem BigQuery na primeira reativação;
- observabilidade suficiente para demo;
- pode voltar ao desenho completo depois.

Essa separação evita disponibilizar uma API generativa aberta para qualquer visitante e mantém a demo pública estável mesmo quando o modelo está indisponível.

---

# Opções de hospedagem

## Opção A — Static Showcase

**Recomendação imediata.**

Build:

```bash
cd web
npm ci
VITE_BUSSOLA_MODO=simulado npm run build
```

Publicar `web/dist`.

### Vantagens

- menor superfície de ataque;
- custo praticamente nulo;
- impossível consumir quota do Gemini pela página pública;
- experiência sempre reproduzível;
- melhor para link em GitHub/LinkedIn.

### Limitação

Não demonstra chamadas reais ADK/MCP.

A solução é apresentar claramente:

> Demo pública reproduz a experiência com dados e respostas sintéticas.  
> A arquitetura agentic completa pode ser executada localmente ou no Live Lab.

---

## Opção B — Novo projeto GCP, modo Live Lite

**Recomendação para segunda etapa.**

Criar um novo projeto GCP pessoal/equipe e reaproveitar a arquitetura atual, mas com o mínimo necessário:

- Cloud Run: `bussola-mcp`;
- Cloud Run: `bussola-agent`;
- Cloud Run/BFF: `bussola-bff`;
- Secret Manager;
- Artifact Registry;
- Gemini Developer API;
- fixtures/memória no lugar do BigQuery.

Configuração inicial:

```text
BUSSOLA_FAKES=TRUE
GOOGLE_GENAI_USE_VERTEXAI=FALSE
MCP_USE_OIDC=TRUE
AGENT_USE_OIDC=TRUE
min instances = 0
max instances = 1
```

### Por que essa opção

Mantém a arquitetura agentic que queremos demonstrar e evita, inicialmente:

- migração de datasets;
- IAM de BigQuery;
- persistência de auditoria;
- Vertex AI;
- dependência de serviços criados especificamente para o hackathon.

### Custo

Cloud Run continua com cobrança por uso e free tier; em `us-central1`, a documentação atual lista free tier mensal para CPU, memória e 2 milhões de requests no modelo request-based. Isso reduz o custo de uma demo de baixo tráfego, mas **não equivale a um hard cap de gasto**.

Referência:
https://cloud.google.com/run/pricing

A Gemini Developer API possui modelos com free tier e opções pagas. Para o Live Lab, utilizar somente dados sintéticos. A página atual de preços indica que conteúdo enviado no free tier pode ser usado para melhoria dos produtos do Google; portanto, não usar dados pessoais ou de clientes nesse modo.

Referência:
https://ai.google.dev/gemini-api/docs/pricing

---

## Opção C — GCP Reference Deployment completo

Usar quando o objetivo passar de “ter a demo online” para “demonstrar a arquitetura de referência”.

Reativar:

- Cloud Run MCP;
- Cloud Run Agent;
- Cloud Run BFF;
- BigQuery `bussola_dados`;
- BigQuery `bussola_app`;
- Secret Manager;
- Artifact Registry;
- Cloud Logging;
- WIF do GitHub Actions;
- service accounts dedicadas;
- Vertex AI / Model Armor quando fizer sentido.

O BigQuery possui atualmente free tier de 10 GiB de armazenamento e 1 TiB de consultas on-demand/mês. O dataset sintético da PoC pode ser compatível com uma operação pequena, mas isso deve ser conferido após a migração.

Referência:
https://cloud.google.com/bigquery/pricing

### Quando vale

- apresentação técnica da arquitetura;
- estudo de observabilidade;
- medição de custo por jornada;
- retomada de auditoria persistida;
- evolução do case de agentes governados.

---

# O que eu não recomendo agora

## Migrar o backend inteiro para outra nuvem

Render/Fly.io/Railway e similares podem executar os contêineres, mas o repositório tem decisões explícitas de Cloud Run, IAM/OIDC, BigQuery, Secret Manager e deploy por chart.

Trocar tudo apenas para “colocar online” aumenta o escopo e enfraquece a reprodutibilidade da arquitetura.

Para o site público, hosting estático é suficiente.
Para o live agent, um novo projeto GCP é a menor mudança.

## Abrir o Live Lab sem controle

Uma URL pública que chama Gemini a cada mensagem cria:

- consumo imprevisível;
- abuso automatizado;
- quota exhaustion;
- experiência ruim para visitantes legítimos;
- risco de conteúdo inesperado.

Use pelo menos:
- senha/access code;
- rate limit;
- limite de sessão;
- `max-instances=1`;
- quota de API;
- monitoramento de custos.

---

# Migração da infraestrutura antiga

O `docs/operacao.md` atual contém IDs, URLs e service accounts do projeto do hackathon. Eles devem ser considerados **referência histórica**, não instrução operacional válida.

Antes do primeiro deploy novo:

1. criar novo project ID;
2. criar service accounts novas;
3. criar novos secrets;
4. gerar nova chave Gemini se usada;
5. configurar WIF novo;
6. atualizar valores do Helm;
7. remover qualquer dependência de IDs antigos;
8. testar `BUSSOLA_FAKES=TRUE`;
9. smoke test;
10. só depois habilitar BigQuery/Vertex.

**Não reutilizar credenciais ou secrets do hackathon.**

---

# Arquitetura recomendada de exposição

```text
                 ┌──────────────────────────┐
Visitante ──────▶│  DEMO PÚBLICA            │
                 │  static + simulado       │
                 │  sem modelo / sem custo  │
                 └──────────────────────────┘

                          link técnico
                               ↓

                 ┌──────────────────────────┐
Convidado ──────▶│  LIVE LAB                │
                 │  access code             │
                 │  BFF → ADK → MCP         │
                 │  Gemini + dados fake     │
                 └──────────────────────────┘

                               ↓
                        quando necessário

                 ┌──────────────────────────┐
Equipe ─────────▶│  REFERENCE DEPLOYMENT    │
                 │  BigQuery + observability│
                 │  IAM + persistent audit  │
                 └──────────────────────────┘
```

## Roadmap

### R0 — URL pública novamente
- publicar o modo simulado;
- adicionar URL ao README;
- testar desktop/mobile;
- deixar explícito “dados sintéticos”.

### R1 — UX pass
Executar as prioridades de `ux-review.md`.

### R2 — Live Lab
- novo GCP;
- backend em fakes;
- Gemini;
- access code;
- smoke + quotas.

### R3 — Reference mode
- BigQuery;
- auditoria persistente;
- WIF;
- observabilidade;
- medição de custo/latência.

## Critério de sucesso

A reativação não está concluída quando “o Cloud Run sobe”.

Está concluída quando:

- há uma URL pública estável;
- o visitante entende que os dados são sintéticos;
- o happy path pode ser concluído sem orientação externa;
- a versão pública não depende de quota de LLM;
- o Live Lab pode ser demonstrado sob demanda;
- custos e limites são observáveis;
- nenhuma credencial antiga é necessária.
