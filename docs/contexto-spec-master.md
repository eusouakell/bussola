# Bússola — Contexto de Implementação (Spec Master)

> Arquivo de contexto único para `/spec-master docs/contexto-spec-master.md`.
> Consolida produto (README + `docs/`), inventário real do projeto GCP
> `batalha-time-07-lkbv` (levantado em 26/09/2026), perfil da base sintética e
> roadmap de implementação em **contexto acelerado** (hackathon).
> Onde este arquivo diz "recomendação", trata-se de decisão técnica proposta,
> ainda não ratificada pelo time — ver §20.
>
> **Execução paralela:** este arquivo é a referência de produto. Os runs do
> Spec Master são disparados **por ciclo**, com os arquivos de
> [`docs/ciclos/`](./ciclos/README.md) (um por feature, com contratos
> congelados em [`docs/ciclos/contratos.md`](./ciclos/contratos.md)).

---

## §1 Propósito

Construir a PoC da **Bússola** para a Batalha de Agentes (Grupo
07, Sala 215): uma jornada agentic que parte de um objetivo financeiro
declarado pelo cliente e o transforma em plano executável, seguindo
`OBJETIVO → ENTENDER → ANTECIPAR → ORIENTAR → AGIR → ACOMPANHAR`.

Time: Carlos Guevara, João Paulo Soares Lopes, Kell Bonassoli, Victor Lucas
Lopes. Mentora: Yasmin Mafra Maroum.

## §2 Problema e resultado desejado

O cliente não começa escolhendo um produto bancário; começa com uma intenção
humana ("comprar meu primeiro apartamento"). O resultado desejado é uma
demonstração ponta a ponta, rodando na GCP do time, em que o agente:

1. entende o objetivo e pergunta apenas o que não consegue inferir dos dados;
2. transforma o extrato sintético em diagnóstico com números corretos e
   rastreáveis;
3. simula cenários comparáveis (conservador, equilibrado, acelerado, outro
   caminho);
4. orienta com explicabilidade, citando de onde veio cada número;
5. propõe próximos passos e **pede consentimento explícito** antes de qualquer
   ação sensível;
6. registra decisões e consentimentos para auditoria;
7. acompanha a evolução do plano e recalcula a rota quando a realidade muda.

## §3 Persona e cenário da demo

- **Fernando, 30 anos**, pessoa física, quer comprar o primeiro apartamento.
- A base não tem idade nem nome: a persona é narrativa e é **ancorada em um
  `id_usuario` real** da base sintética.
- **Usuário-âncora recomendado:** `36a21505-d6d4-42d3-b319-d51a133c7269`.
  Médias mensais em 2025: renda ≈ R$ 7.451, gasto ≈ R$ 4.615, sobra ≈
  R$ 2.836, aluguel ≈ R$ 1.077, comer fora ≈ R$ 364, assinaturas ≈ R$ 101,
  juros pagos ≈ R$ 61. Saldo mínimo ≈ −R$ 2.072 (já entrou no negativo) e
  saldo máximo ≈ R$ 49.321. Renda via "Recebimentos diversos" (PIX /
  autônomo), sem financiamento imobiliário. Paga aluguel, sem financiamento e
  com sobra positiva, portanto encaixa no perfil de "primeiro apartamento".
- **Alternativas:** `31e94f2f-1463-49f9-a41a-b3f220ed976a` (aluguel alto ≈
  R$ 1.649, comer fora ≈ R$ 609) e `0231d306-f210-40a2-8ce3-a86d07384734`
  (comer fora ≈ R$ 718, boa história de "cortar gastos").
- **Cenários:** os valores R$ 600/mês (conservador) e R$ 900/mês (acelerado)
  citados em `docs/dados-tecnologia.md` são ilustrativos. Na PoC, **os
  valores dos cenários são calculados a partir dos dados do usuário-âncora**,
  nunca fixados no prompt (ver §11 e §20).

## §4 Jornada e comportamento por estado

| Estado | Comportamento esperado | Fonte de números |
|---|---|---|
| OBJETIVO | Interpreta intenção, tipo de objetivo, valor-alvo, prazo e prioridade. Pergunta só o que falta. | Conversa |
| ENTENDER | Consolida o perfil: renda, gastos recorrentes, parcelas, dívidas/juros, saldo e capacidade mensal de poupança. | Ferramentas determinísticas (BigQuery) |
| ANTECIPAR | Simula prazo × esforço mensal, riscos (reserva, dívidas, saldo negativo). | Funções de simulação determinísticas |
| ORIENTAR | Apresenta conservador, equilibrado e acelerado, mais "outro caminho" em linguagem natural, com trade-offs e recomendação explicada. | Simulação + RAG (contexto) |
| AGIR | Propõe ações (plano mensal, cortes, reserva, simulação de financiamento, produto adequado, lembretes). Ações sensíveis exigem consentimento. | Gate de consentimento |
| ACOMPANHAR | Compara o realizado com o planejado mês a mês, alerta desvio e oportunidade, e recalcula a rota. | Replay temporal da base (§10 F6) |

## §5 Ambiente GCP disponível (inventário de 26/09/2026)

- **Projeto:** `batalha-time-07-lkbv` ("Batalha Agentes Time 07"). Região dos
  recursos: `us-central1`. Billing: "Instrumentless Billing Account for
  Trial".
- **Owner:** `andre.favretto@santodigital.com.br`, o único que concede IAM de
  projeto.
- **Papéis do time** (os 4 integrantes):
  - Agent Platform User
  - Artifact Registry Writer
  - BigQuery Admin, BigQuery Data Editor e BigQuery Job User
  - Cloud Build Editor
  - Cloud Run Admin
  - Discovery Engine Editor
  - Logs Viewer e Monitoring Viewer
  - Secret Manager Secret Accessor
  - Service Account Token Creator e Service Account User
  - Service Usage Consumer
  - Storage Object Admin
  - Viewer
- **O time NÃO tem:** Model Armor (nenhum papel), Secret Manager Admin,
  Storage Admin (não cria bucket), IAM Admin, criação de Service Account,
  Discovery Engine Admin (não cria engine/app).
- **Service Account de runtime:** só existe a default compute
  `1061873050224-compute@developer.gserviceaccount.com`. Ela tem apenas
  Artifact Registry Writer, Logs Writer e Storage Admin. **Não tem** BigQuery,
  Agent Platform/Vertex, Discovery Engine, Secret Accessor nem Model Armor.
- **Recursos existentes:**
  - BigQuery: `hackathon_dados.extrato_sintetico` (ver §8).
  - Secret Manager: `gemini-api-key` (o time tem accessor).
  - Artifact Registry: repositório Docker `agentes` em `us-central1`, vazio.
  - Vazios: Cloud Run sem serviços, Agent Runtime (Deployments) sem agentes,
    nenhum bucket, nenhum template de Model Armor.
- **Modelos serverless (Model Garden):**
  - Gemini: 3.8 Flash, 3.7 Flash, 3.6 Flash, 3.5 Flash, 3.5 Flash Lite, 3.1
    Flash Lite e 3.1 Pro Preview.
  - Também há modelos Claude, mas **fora do escopo**: a stack do produto é
    Gemini.
- **Agent Platform (ex-Vertex AI):** a console expõe Agent Garden, ADK, MCP
  Servers, RAG Engine, Vector Search, Search, Deployments (Agent Runtime),
  Memory Bank, Sessions e Evaluation.

## §6 Restrições da organização (org policy `gcp.restrictServiceUsage`)

Somente estes serviços são permitidos:

- `aiplatform`, `generativelanguage`, `discoveryengine`, `modelarmor`
- `bigquery`, `bigquerystorage`
- `run`, `cloudfunctions`, `cloudbuild`, `artifactregistry`, `storage`,
  `pubsub`, `secretmanager`
- `logging`, `monitoring`
- `apikeys`, `cloudbilling`, `billingbudgets`, `cloudresourcemanager`,
  `serviceusage`, `cloudshell`

**Bloqueados**, com a consequência de cada um:

| Serviço bloqueado | Consequência | Substituto na PoC |
|---|---|---|
| Firestore, Cloud SQL, Redis | Sem banco transacional | Datasets BigQuery próprios + sessão em memória (§13) |
| Cloud Scheduler, Tasks, Workflows, Eventarc | Sem agendamento ou orquestração gerenciada | ACOMPANHAR via replay temporal disparado na demo (F6); Pub/Sub e Functions se precisar de evento |
| Compute Engine, GKE | Sem VM ou cluster | Cloud Run |
| Cloud Trace / Telemetry | Sem tracing distribuído | Logs estruturados no Cloud Logging |
| BigQuery Connection API | `ML.GENERATE_EMBEDDING` / modelos remotos provavelmente indisponíveis | Embeddings gerados em Python (Agent Platform ou Gemini API) e versionados com o índice no repositório (F2) |
| BigQuery Data Transfer | Sem scheduled queries | Pipeline de carga executado manualmente/script |
| Agent Registry (MCP gerenciado) | Página de MCP Servers gerenciados bloqueada | **MCP server próprio** em Cloud Run (F3) |
| Dataplex, Dataform | — | Não usados |

## §7 Arquitetura alvo (ajustada às restrições)

```text
[Canal do banco na PoC: chat web]  ──►  [Serviço Bússola — Cloud Run]
                                        ├─ Guardrails de entrada/saída
                                        │    (Model Armor se liberado; senão callbacks ADK + safety settings)
                                        ├─ Agente Bússola (ADK + Gemini Flash) — estados da jornada
                                        ├─ Gate de consentimento + trilha de auditoria
                                        └─ Cliente MCP (streamable HTTP)
                                                 │
                                                 ▼
                               [MCP server "dados e conhecimento" — Cloud Run, read-only]
                                        ├─ Ferramentas determinísticas ──► BigQuery (views/tabelas bussola_*)
                                        └─ Recuperação RAG financeiro  ──► corpus de conhecimento no repositório (F2)
Persistência: BigQuery `bussola_app` (planos, consentimentos, auditoria) + Cloud Logging
Segredos: Secret Manager (`gemini-api-key` e futuros)   Imagens: Artifact Registry `agentes`
```

Princípios:

- O LLM **não calcula nem inventa números**. Números vêm de ferramentas
  determinísticas (SQL e funções Python testadas).
- O agente conversacional **não vê SQL nem infraestrutura**. O MCP expõe
  ferramentas semânticas.
- Acesso a dados é **read-only** e sempre com escopo de `id_usuario` (o agente
  só enxerga o cliente da sessão).
- Diagnóstico, simulação e ação são rotulados de forma distinta nas respostas.

## §8 Dados disponíveis

Tabela `batalha-time-07-lkbv.hackathon_dados.extrato_sintetico` (`us-central1`,
467.585 linhas, ~56 MB):

| Coluna | Tipo | Observação |
|---|---|---|
| `id_usuario` | STRING | 1.000 usuários, todos com 12 meses |
| `anomesdia` | TIMESTAMP | 2025-01-01 a 2025-12-31 |
| `anomes` | INTEGER | AAAAMM |
| `tipo` | STRING | `E` entrada / `S` saída (valor sempre positivo) |
| `descr` | STRING | ex.: "pix transf alug", "cart credito loja esport parc 1/12", "assin amazon prime" |
| `vlr` | FLOAT | valor positivo |
| `nom_cate_macro` | STRING | 25 macrocategorias |
| `nom_cate_micro` | STRING | 98 microcategorias |
| `saldo_apos` | FLOAT | saldo após o lançamento |
| `parcela_atual`, `parcela_total` | FLOAT | 29.847 lançamentos parcelados (até 12x) |

**Fatos da base (para testes e narrativa):**

- **Entradas:**
  - Recebimentos diversos: 999 usuários
  - Salários e bonificações (CLT, PLR, 13º): 800 usuários
  - Rendimentos (aluguel recebido): 300 usuários
  - Benefícios (INSS): 100 usuários
- **Maiores saídas (total no ano):**
  - Empréstimos e financiamentos: R$ 24,96 mi (inclui financiamento de imóvel)
  - Produtos financeiros: R$ 20,0 mi (seguros, anuidade, capitalização, juros,
    consórcio, fatura)
  - Casa: R$ 14,3 mi
- **Por usuário/mês, mediana:** renda ≈ R$ 8.513, gasto ≈ R$ 8.670, sobra ≈
  R$ 17. Metade da base não poupa.
- **Contagens de usuários:**
  - 700 têm financiamento imobiliário
  - 893 têm dívidas
  - 695 pagam juros
  - 286 têm consórcio
  - 327 ficaram com saldo negativo em algum momento
  - 59 candidatos a "primeiro apartamento" (pagam aluguel, sem financiamento,
    sobra positiva)
- **Lacunas da base:**
  - não há posição de investimentos nem reserva explícita; a reserva é
    inferida de `saldo_apos`;
  - não há score/perfil de crédito, idade nem nome;
  - a base parece gerada por arquétipos (coortes de ~100 usuários).
- **Ruído de rótulo proposital:** ex. "cart credito 99 corrida" rotulado como
  Restaurantes; "cart credito posto shell" rotulado como Jardinagem. A
  recategorização assistida é diferencial opcional (F2, P2).

## §9 RAG de conhecimento — normas do BACEN, crédito e boas práticas

> **Revisão (26/09/2026, Q-17 do ciclo 000):** a versão anterior desta seção
> previa um corpus derivado da base (fichas mensais, perfil anual, coorte e
> lançamentos) gravado em `bussola_rag` e buscado com `VECTOR_SEARCH`. O time
> cortou esse desenho: os dados do cliente já são servidos pelas ferramentas
> determinísticas sobre `bussola_dados`, e o RAG passa a ser conhecimento
> geral.

**Decisão do time:** o RAG traz **conhecimento de apoio**, não dados do
cliente. Quatro temas:

1. **Normas do BACEN e do CMN** (`norma_bacen`): rotativo e parcelamento do
   cartão, teto de juros, CET, portabilidade, Registrato, cheque especial.
2. **Crédito** (`credito`): conteúdo geral sobre modalidades, custo,
   renegociação e superendividamento. As dívidas e parcelas do próprio
   cliente vêm da ferramenta `dividas_e_parcelas`.
3. **Boas práticas** (`boas_praticas`): reserva de emergência, orçamento,
   ordem de quitação, uso consciente do cartão.
4. **Produtos** (`produto`): o catálogo curado de
   [`docs/catalogo/`](./catalogo/README.md), com os 8 produtos do recorte do
   MVP (§20, Q3).

Diretrizes:

- **Texto original do time**, em pt-BR, educativo e geral. Cita a norma pelo
  número e não copia texto legal. Nenhum LLM escreve o corpus.
- **Sem dado de cliente no corpus.** O buscador não recebe `id_usuario` nem
  `ate_anomes`.
- Cada trecho recuperado carrega **título e fonte** (nome, referência e URL)
  para explicabilidade.
- O RAG explica conceitos e regras; os valores apresentados ao cliente
  continuam vindo das ferramentas determinísticas.
- **Produtos (Q3):** os produtos do catálogo curado de
  [`docs/catalogo/`](./catalogo/README.md) entram no tema `produto`, com uso,
  cuidado de elegibilidade e link da fonte oficial, **sem taxas nem
  condições comerciais**. Produto fora do catálogo é citado só de forma
  genérica.

**Implementação (contratos §4):**

- corpus em Markdown no repositório (`data/rag/corpus/<tema>/`);
- embeddings gerados offline em Python via Agent Platform (ou Gemini API) e
  versionados com o índice (`mcp_server/bussola_mcp/rag/indice/`);
- busca em memória no MCP server: léxica (padrão, sem GCP) ou por cosseno
  com numpy (embedding só da pergunta em tempo de execução);
- sem dataset no BigQuery, sem `VECTOR_SEARCH` e sem RAG Engine.

## §10 Features

Ordem de dependência: F1 → F2 → F3 → F4 → F5 → F6. F7 é transversal e fecha a
entrega. Prioridades: P0 é essencial para a demo, P1 é importante, P2 é
diferencial se sobrar tempo.

### F1 — Camada de dados financeiros determinística (`001-camada-dados-financeiros`) — P0

**Objetivo:** transformar o extrato em métricas confiáveis por usuário e
funções de simulação testadas.

**Comportamento:**

- Dataset `bussola_dados` com views/tabelas derivadas:
  - `perfil_mensal` (renda, gasto, sobra por usuário/mês);
  - `gastos_categoria`;
  - `recorrentes` (assinaturas, aluguel etc.);
  - `parcelas_dividas` (parcelas ativas, juros);
  - `saldo` (mín/máx/final);
  - `capacidade_poupanca`.
- Módulo Python de simulação:
  - prazo para atingir valor-alvo dado aporte mensal e saldo inicial;
  - aporte necessário dado prazo;
  - geração dos cenários conservador, equilibrado e acelerado a partir da
    capacidade real;
  - impacto de cortes por categoria;
  - impacto de dívidas.
- Regras de cenário parametrizadas e documentadas; nenhum valor fixo no
  prompt.

**Critérios de aceite:**

- [ ] Para o usuário-âncora, as 8 perguntas de `docs/dados-tecnologia.md` §2
      têm resposta numérica reproduzível a partir das tabelas.
- [ ] Funções de simulação têm testes unitários com casos conhecidos
      (inclusive borda: sobra ≤ 0, objetivo já atingido, prazo impossível).
- [ ] Métricas do usuário-âncora batem com a consulta de referência de §3
      (tolerância de arredondamento).
- [ ] Todas as consultas filtram por `id_usuario` parametrizado (sem SQL
      montado por concatenação de texto do usuário).

### F2 — RAG de conhecimento (`002-rag-financeiro-dados`) — P0 (corpus, índice, buscadores), P1 (eval)

**Objetivo:** construir o corpus e a recuperação descritos em §9.

**Critérios de aceite:**

- [ ] Corpus curado nos três temas de §9 (P0) e no tema `produto` com os 8
      produtos do catálogo (P1), com fonte em cada documento, e índice
      gerado por script idempotente.
- [ ] Busca retorna top-k trechos, com filtro opcional por tema, sem receber
      dado de cliente.
- [ ] Cada trecho retornado inclui título e fonte (nome, referência, URL).
- [ ] Conjunto de ≥ 10 perguntas de avaliação, com trecho esperado no top-3
      em ≥ 80% dos casos.

### F3 — MCP server de dados e conhecimento (`003-mcp-dados-conhecimento`) — P0

**Objetivo:** expor F1 e F2 ao agente como ferramentas semânticas, read-only,
via MCP (streamable HTTP) em Cloud Run.

**Ferramentas mínimas:**

- `perfil_financeiro(id_usuario)`
- `capacidade_poupanca(id_usuario)`
- `oportunidades_corte(id_usuario)`
- `dividas_e_parcelas(id_usuario)`
- `simular_objetivo(id_usuario, valor_alvo, prazo_meses | aporte_mensal)`
- `comparar_cenarios(id_usuario, valor_alvo, prazo_meses)`
- `buscar_contexto_financeiro(id_usuario, pergunta)` (RAG)
- `referencia_coorte(id_usuario, categoria)` (P1)

**Critérios de aceite:**

- [ ] Nenhuma ferramenta aceita SQL livre ou devolve SQL/infra ao chamador.
- [ ] Todas as respostas incluem os números **e** a origem (tabela/período).
- [ ] Ferramentas validam entrada (`id_usuario` existente, valores
      positivos, prazo plausível) e retornam erro legível.
- [ ] Testes de contrato por ferramenta; servidor sobe local e em Cloud Run.

### F4 — Agente Bússola e jornada (`004-agente-bussola-jornada`) — P0

**Objetivo:** agente ADK + Gemini Flash que conduz OBJETIVO → ENTENDER →
ANTECIPAR → ORIENTAR, consumindo o MCP de F3.

**Critérios de aceite:**

- [ ] A partir de "Quero comprar meu primeiro apartamento", o agente coleta
      valor-alvo/entrada e prazo (só pergunta o que falta) e chega a um
      diagnóstico.
- [ ] Apresenta os cenários conservador, equilibrado e acelerado, com aporte
      mensal, prazo e trade-offs vindos de `comparar_cenarios`, e aceita
      "outro caminho" em linguagem natural (re-simulando).
- [ ] Toda resposta com número cita a ferramenta/fonte; nenhum número
      aparece sem chamada de ferramenta correspondente (verificável no
      log).
- [ ] Respostas em pt-BR, linguagem clara, diferenciando diagnóstico,
      simulação e recomendação.
- [ ] Recusa promessas de aprovação de crédito e contratação real.

### F5 — Consentimento, governança e auditoria (`005-consentimento-governanca`) — P0 (gate + auditoria), P1 (Model Armor)

**Objetivo:** autonomia governada no estado AGIR.

**Critérios de aceite:**

- [ ] Ações classificadas em livres (analisar, simular, recomendar) e
      sensíveis (contratar, compartilhar dados, alterar algo financeiro, usar
      dado externo).
- [ ] Ação sensível só executa (simulada) após consentimento explícito na
      conversa. Recusa é respeitada e registrada.
- [ ] Plano escolhido e cada consentimento gravados em `bussola_app`
      (`planos`, `consentimentos`, `auditoria`) e em log estruturado no Cloud
      Logging, sem dados desnecessários.
- [ ] Guardrail de entrada/saída ativo: Model Armor (template liberado pelo
      owner) **ou**, na falta dele, callbacks `before_model` / `after_model`
      do ADK + safety settings do Gemini, com teste de prompt injection
      básico.

### F6 — Acompanhamento com replay temporal (`006-acompanhamento-replay`) — P1

**Objetivo:** demonstrar ACOMPANHAR sem Cloud Scheduler.

**Comportamento:**

- O plano é criado com dados até o mês N de 2025.
- Um comando de demo ("avançar um mês") libera o mês N+1 e compara o
  realizado com o planejado.
- O agente alerta desvio ou oportunidade e recalcula a rota.

**Critérios de aceite:**

- [ ] Corte temporal parametrizável aplicado a todas as ferramentas de F1/F3
      (o agente não "vê o futuro").
- [ ] Ao avançar o mês, o agente detecta desvio (ex.: gasto acima do plano
      em uma categoria) ou folga e propõe ajuste com novo prazo/aporte.
- [ ] Evento de acompanhamento registrado na auditoria.

### F7 — Canal da demo, deploy e roteiro (`007-canal-deploy-demo`) — P0

**Objetivo:** tudo rodando em Cloud Run no projeto do time, com canal
conversacional para a demo.

**Critérios de aceite:**

- [ ] MCP server e serviço Bússola publicados em Cloud Run (`us-central1`) a
      partir de imagens no Artifact Registry `agentes`.
- [ ] Canal de conversa acessível na demo (ver §20, Q4).
- [ ] Roteiro de demo (≤ 5 min) cobrindo os 6 estados, com consentimento e
      um avanço de mês; vídeo de backup gravado.
- [ ] README com como rodar local e como publicar.

## §11 Requisitos transversais

- **Sem números inventados.** Todo valor financeiro exibido vem de ferramenta
  determinística; o modelo só redige.
- **Dados sintéticos apenas**; nenhum dado real de cliente.
- **Escopo por cliente.** Cada sessão está presa a um `id_usuario`, e nenhuma
  ferramenta retorna dados de outro cliente (exceto agregados de coorte).
- **Read-only** sobre `hackathon_dados`. Escrita só em `bussola_app`.
- **Explicabilidade.** Recomendações citam a fonte e o raciocínio.
- **Consentimento.** Nada sensível sem "sim" explícito; tudo auditado.
- **Segredos só no Secret Manager ou injetados no deploy**, nunca no código
  ou no repositório.
- **Linguagem e princípios.** Português do Brasil, tom de educação financeira
  (Resolução Conjunta nº 8) e Responsible AI.

## §12 Requisitos de qualidade

- Testes unitários obrigatórios para funções de simulação e validação de
  entrada (F1/F3).
- Testes de contrato do MCP (F3).
- Conjunto de avaliação do agente: perguntas da demo + casos de prompt
  injection, com critério "número bate com a ferramenta" (F4/F5).
- Logs estruturados (JSON) com `session_id`, estado da jornada, ferramenta
  chamada e decisão de consentimento.
- Metas de latência e disponibilidade: **não definidas pelo contexto**.

## §13 Stack técnica

- **Linguagem:** Python 3.12.
- **Agente:** Google ADK (`google-adk`) com Gemini Flash (versão mais recente
  disponível no Model Garden do projeto; ID exato a validar no Bloco 0).
- **MCP:** SDK oficial MCP para Python (FastMCP), transporte streamable HTTP;
  o ADK consome via `MCPToolset`.
- **Dados:** `google-cloud-bigquery` com consultas parametrizadas.
- **Embeddings:** Agent Platform (Vertex) ou Gemini API (§9).
- **Sessão:** `InMemorySessionService` do ADK com Cloud Run
  `max-instances=1` na demo. Persistência de plano, consentimento e
  auditoria em BigQuery. Memory Bank/Sessions do Agent Platform são P2 e
  dependem de validação.
- **Execução:** Cloud Run (2 serviços: `bussola-mcp`, `bussola-agent`).
- **Build:** `docker buildx --platform linux/amd64` local → push para
  `us-central1-docker.pkg.dev/batalha-time-07-lkbv/agentes/...` →
  `gcloud run deploy --image`. `gcloud run deploy --source`, `adk deploy`
  e Agent Runtime **não** são o caminho padrão, pois exigem bucket de
  staging, que o time não pode criar.
- **Observabilidade:** Cloud Logging (stdout JSON).
- **Segurança:** Secret Manager e Model Armor (se liberado).

## §14 Ambiente de desenvolvimento e operação

- **Desenvolvimento no Claude Code.** O Spec Master (engine em
  `~/.spec-master-engine`, instalado via `init.sh`) e as fases do Spec Kit
  (`specify init --here --integration claude --script sh`) rodam no Claude
  Code. Cada ciclo é disparado com `/spec-master docs/ciclos/NNN-....md`,
  numa worktree e branch próprias. Passo a passo em
  [`docs/ciclos/README.md`](./ciclos/README.md) §6.
- **Operação no Google Antigravity (provisionado pela Santo Digital).** O
  Antigravity opera o produto **pronto**: deploy de imagens já construídas,
  promoção de revisão, rollback, smoke tests, consultas de auditoria e
  apoio à demo. Ele não desenvolve e não roda o Spec Master. O ciclo 007
  entrega:
  - `AGENTS.md` na raiz, com as instruções e os limites do agente
    operador;
  - [`docs/operacao.md`](./operacao.md), o runbook.
- **Desenvolvimento local:** credenciais do próprio integrante via
  `gcloud auth application-default login`. Os papéis do time já permitem
  BigQuery, Agent Platform e Discovery Engine localmente.
- **Estratégia Git:**
  - uma branch por ciclo (`NNN-<feature-id>`), cada uma em sua worktree;
  - PR para `main` na ordem de merge do plano de ciclos;
  - dentro de cada run, a resposta no Step 2 é **Trunk-Based**
    (`create_branch: false`), porque a branch já existe.
  - `.spec-master/` é local (gitignored). A rastreabilidade é exportada para
    `specs/NNN-*/traceability.md`.

## §15 Roadmap acelerado

A data-limite da demo não está neste contexto (§20, Q1). O roadmap é sequencial
por blocos, com **caminho crítico primeiro** (fatia vertical ponta a ponta) e
linha de corte explícita.

> **Execução paralela (vigente):** os blocos abaixo foram reorganizados em
> ciclos paralelos no [plano de ciclos](./ciclos/README.md):
>
> - **Onda 0:** 000 (fundação e contratos);
> - **Onda 1:** 001 ∥ 003 ∥ 004 ∥ 007;
> - **Onda 2:** 002 ∥ 005 (podem começar junto com a Onda 1);
> - **Onda 3:** 006, seguido da integração final.
>
> A tabela abaixo continua valendo como visão de entrega e linha de corte.

| Bloco | Entrega | Features | Paralelização sugerida |
|---|---|---|---|
| **0 — Desbloqueio** | Pedidos ao owner/mentores (§16), validação de modelos (Gemini Flash + embedding), datasets `bussola_*` criados, esqueleto do repo, pipeline build → push → deploy testado com "hello" no Cloud Run | — | 1 pessoa em IAM/infra, 1 em dados, 2 no esqueleto agente/MCP |
| **1 — Dados** | Views de F1, simulação com testes, números do usuário-âncora validados | F1 | Dados (SQL) ∥ simulação (Python) |
| **2 — Fatia vertical** | MCP com `perfil_financeiro`, `capacidade_poupanca`, `comparar_cenarios`; agente ADK respondendo OBJETIVO → ORIENTAR local e em Cloud Run | F3 (parcial), F4 (parcial) | MCP ∥ agente/prompt |
| **3 — RAG** | Corpus de conhecimento + embeddings + busca em memória; ferramenta `buscar_contexto_financeiro` | F2, F3 | 1–2 pessoas |
| **4 — Governança** | Gate de consentimento, gravação em `bussola_app`, guardrails (Model Armor ou fallback) | F5 | ∥ Bloco 3 |
| **5 — Acompanhar** | Replay temporal e recálculo de rota | F6 | — |
| **6 — Demo** | Canal, roteiro, ensaio, vídeo de backup, README | F7 | Todos |

**Linha de corte**, se faltar tempo, cortar nesta ordem:

1. recategorização (P2);
2. `referencia_coorte` (P1);
3. Model Armor, substituído pelo fallback de callbacks;
4. replay de mais de um mês.

**Nunca cortar:** números determinísticos, consentimento e auditoria, e a
fatia vertical em Cloud Run.

## §16 Pedidos de desbloqueio (Bloco 0)

Ao owner (`andre.favretto@santodigital.com.br`) ou mentores com Storage/Secret
Admin:

1. **Service Account de runtime** (nova, ex. `bussola-runtime`, ou a default
   compute) com estes papéis:
   - `roles/aiplatform.user`
   - `roles/bigquery.jobUser`
   - `roles/bigquery.dataViewer`
   - `roles/secretmanager.secretAccessor`
   - `roles/modelarmor.user`
   - `roles/logging.logWriter`
2. **Template de Model Armor** (ex. `bussola-guard`) criado por quem tem
   `modelarmor.admin`.
3. **Um bucket** (ex. `batalha-time-07-lkbv-bussola`) com Storage Object
   Admin para o time. Isso habilita `--source`, Cloud Build e staging, se
   necessário.
4. Confirmar se é permitido `allUsers` como invoker no Cloud Run (política de
   domínio) para o canal da demo.

**Plano B**, caso os pedidos não saiam a tempo. Tudo isto funciona com os
papéis atuais do time:

- **BigQuery:**
  - O time (BigQuery Admin) concede `dataViewer` em `bussola_dados` e
    `dataEditor` em `bussola_app` para a SA default, no nível de dataset.
  - O runtime lê tabelas pré-agregadas via `list_rows`/Storage Read e grava
    via streaming insert, sem precisar de `jobUser`.
  - A busca do RAG já roda em memória, sem BigQuery (§9).
- **LLM:**
  - Gemini via `generativelanguage` com a `gemini-api-key`, injetada como
    variável de ambiente no deploy por quem tem accessor.
  - Isso é menos seguro, aceitável só na PoC e deve ficar registrado como
    dívida.
- **Guardrails:** callbacks do ADK + safety settings.

## §17 Riscos

| Risco | Mitigação |
|---|---|
| IAM da SA de runtime não liberado a tempo | Plano B de §16 |
| Sem bucket: `--source`/Cloud Build/Agent Runtime falham | Build local `linux/amd64` + push no AR `agentes` |
| `ML.GENERATE_EMBEDDING` indisponível (Connection API bloqueada) | Embeddings em Python (§9) |
| ID do modelo Gemini/embedding diferente do esperado | Validar no Bloco 0; parametrizar por variável de ambiente |
| LLM "arredonda"/inventa números | Números só via ferramenta; teste de avaliação compara resposta com retorno da ferramenta |
| Sessão perdida entre instâncias do Cloud Run | `max-instances=1` na demo; estado crítico persistido em BigQuery |
| Rótulos de categoria ruidosos distorcem cortes sugeridos | Priorizar macrocategorias robustas; recategorização como P2 |
| Invoker público bloqueado por política | `gcloud run services proxy` / token de identidade na máquina da demo |
| Demo ao vivo instável | Vídeo de backup + roteiro ensaiado |

## §18 Não objetivos

- dados reais de clientes;
- contratação real de produtos;
- execução financeira sem consentimento;
- integração com Open Finance no MVP (fica como evolução);
- promessa de aprovação de crédito;
- substituição de assessoria humana em casos regulados;
- integração com o app real do banco (a PoC simula o canal);
- catálogo real de produtos do banco com taxas/condições (o catálogo curado de
  `docs/catalogo/` só descreve produtos e aponta a fonte oficial; as APIs
  públicas de dados abertos ficam fora);
- banco transacional, agendamento gerenciado, tracing distribuído (todos
  bloqueados por política);
- uso de modelos não-Gemini.

## §19 Definition of Done e condições de parada

1. F1–F5 e F7 implementados e publicados em Cloud Run; F6 publicado ou
   formalmente cortado conforme §15.
2. Demo ponta a ponta com o usuário-âncora percorre os 6 estados (ou 5, se F6
   for cortado), com números idênticos aos das ferramentas.
3. Consentimento e auditoria verificáveis em `bussola_app` e no Cloud
   Logging.
4. Testes de F1/F3 passando; conjunto de avaliação de F2/F4 executado com
   resultado registrado.
5. README permite outro integrante rodar local e publicar.
6. Nenhum item de §18 implementado.

Não avançar para Open Finance, contratação real ou canais além da demo: isso
é nova especificação.

## §20 Questões em aberto

- **Q1.** Data e hora limite da demo e duração da apresentação. *(define o
  tamanho de cada bloco de §15)*
- **Q2.** Confirmar o usuário-âncora (`36a21505…` recomendado) e se os
  cenários usam percentuais da capacidade real (recomendado) ou os valores
  ilustrativos R$ 600/R$ 900.
- **Q3.** ~~Haverá conteúdo curto de produtos escrito pelo time?~~
  **Respondida (Q-17 do 000 e catálogo):** sim. O corpus do RAG é só
  conteúdo escrito pelo time: normas do BACEN, crédito, boas práticas e o
  catálogo PF de [`docs/catalogo/`](./catalogo/README.md) (recorte de 8
  produtos no MVP, sem taxas), no tema `produto` (§9).
- **Q4.** Canal da demo: ADK Web UI publicada no Cloud Run (mais rápido) ou
  front de chat próprio no estilo do app do banco.
- **Q5.** ~~Papel exato do Antigravity~~ **Respondida em parte:** o
  desenvolvimento é no Claude Code e o Antigravity opera o produto pronto
  (§14). Ainda em aberto: as credenciais GCP no Antigravity são as mesmas
  dos integrantes?
- **Q6.** ~~Busca vetorial: `VECTOR_SEARCH` ou RAG Engine~~ **Respondida
  (Q-17 do 000):** nenhum dos dois. Índice versionado no repositório e busca
  em memória no MCP (léxica ou numpy).
- **Q7.** Os pedidos de §16 serão atendidos? Se não, seguir o Plano B.
