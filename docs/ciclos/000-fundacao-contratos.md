# Ciclo 000 — Fundação e contratos

> **Disparo:** `/spec-master docs/ciclos/000-fundacao-contratos.md`, no
> Claude Code, dentro da worktree `../bussola-000`, na branch
> `000-fundacao-contratos`.
>
> **Onda:** 0 (bloqueia todos os outros ciclos). **Spec:**
> `specs/000-fundacao-contratos`. **Plano:** [README](./README.md).
>
> **Leitura obrigatória antes do Step 3:**
>
> - [contratos.md](./contratos.md), inteiro. É o que este ciclo materializa.
> - Contexto mestre [§5–§7, §11–§13 e §16](../contexto-spec-master.md).
> - [Blueprint](../blueprint-arquitetura.md) §7–§10.

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Uma única feature.** Este arquivo define exatamente uma:
   `id: fundacao-contratos`, `spec_directory: specs/000-fundacao-contratos`.
   Não gere features F1–F7: elas pertencem a outros ciclos.
2. **Número fixo:** rode as fases do Spec Kit com
   `SPECIFY_FEATURE_DIRECTORY=specs/000-fundacao-contratos`.
3. **Step 2:**
   - aceite `specify init --here --integration claude --script sh`, se
     ainda não estiver inicializado;
   - estratégia Git: **Trunk-Based**. A worktree já está na branch do
     ciclo; não crie branch nem instale a extensão git do Spec Kit.
4. **Step 4:** este é o **único** ciclo que cria a constituição. Ela
   congela no merge (tag `contratos-v1`).
5. **Seguir os contratos à risca.** Qualquer divergência encontrada vai para
   `specs/000-fundacao-contratos/questoes.md`. Corrija o contrato no mesmo
   PR, porque o 000 é o dono do contrato até o merge.
6. **Ciclo curto:** é esqueleto, não produto. Nada de lógica de negócio real
   (métricas, prompts, gate); isso pertence aos ciclos 001–007.
7. **Segredos:** nunca imprima nem versione o valor de `gemini-api-key` ou de
   qualquer token.
8. **Ao final:**
   - `make test` e `make lint` verdes;
   - rastreabilidade exportada para
     `specs/000-fundacao-contratos/traceability.md`.

## 2. Propósito

Criar o esqueleto do repositório e **materializar os contratos v1 em
código**, para que os ciclos 001–007 rodem em paralelo sem depender uns dos
outros.

O ciclo também valida a plataforma GCP: modelos, datasets e o pipeline
build → push → Cloud Run. Por fim, formaliza os pedidos ao owner.

## 3. Escopo e comportamento esperado

### 3.1 Governança e convenções

- **Spec Kit** inicializado com a integração Claude.
- **Constituição** (`.specify/memory/constitution.md`), com princípios
  extraídos do contexto mestre:
  - **§7:**
    - o LLM não calcula nem inventa números;
    - o agente não vê SQL nem infraestrutura;
    - acesso read-only, sempre com escopo de `id_usuario`;
    - diagnóstico, simulação e recomendação rotulados.
  - **§11:**
    - só dados sintéticos;
    - consentimento explícito e auditado;
    - segredos fora do repositório;
    - pt-BR e Responsible AI.
  - **§12:** testes obrigatórios para simulação, validação e contratos
    MCP.
  - **Regras de paralelismo** ([README](./README.md) §5):
    - contratos só via PR `contracts:`;
    - propriedade de diretórios;
    - fakes antes de dependências não mergeadas;
    - testes só gravam em `bussola_app_dev`;
    - Cloud Run `--no-traffic` fora do 007.
- **`CLAUDE.md`** na raiz:
  - comandos `make`;
  - modo `BUSSOLA_FAKES`;
  - onde ficam os contratos;
  - tabela de propriedade (link para `contratos.md` §1);
  - proibição de SQL concatenado e de logar prompts ou segredos;
  - fluxo de PR.
- **`.gitignore`:** já existe. Preservar e acrescentar o que faltar.
- **`Makefile`** com os targets de `contratos.md` §2: `test`, `lint`,
  `mcp`, `agent`, `fixtures`, `test-bq`.

### 3.2 Projetos Python (uv, Python 3.12)

- **`mcp_server/`:**
  - `pyproject.toml` com `mcp`/FastMCP, `pydantic`,
    `google-cloud-bigquery`, `numpy`, `pytest` e `ruff`;
  - `Dockerfile` (`python:3.12-slim` + uv, `PORT=8080`, `linux/amd64`).
- **`agent/`:**
  - `pyproject.toml` com `google-adk`, `google-genai`, `google-auth`,
    `pydantic`, `pytest` e `ruff`;
  - `Dockerfile` servindo o ADK com Web UI em `$PORT`.

### 3.3 Contratos em código (`contratos.md` §1, itens marcados como 000)

| Artefato | Conteúdo |
|---|---|
| `contracts/bigquery/{bussola_dados,bussola_app}.sql` | DDL de §3; `bussola_app_dev` reutiliza o DDL de `bussola_app`. Sem `bussola_rag` (Q-17) |
| `contracts/env.example` | Variáveis de §7, **sem valores secretos** |
| `contracts/catalogo_produtos.json` | Recorte do MVP de `docs/catalogo/` §2 (8 produtos), no formato de §3, com teste de contrato "sem taxas" |
| `mcp_server/bussola_mcp/contratos.py` | Modelos Pydantic: linhas de §3, entrada e `dados` de cada ferramenta de §5, envelopes `Resposta`/`Fonte`/`Periodo`/`Erro`, enum de códigos |
| `mcp_server/bussola_mcp/dominio/interfaces.py` | `RepositorioFinanceiro` e `BuscadorContexto` (§4) |
| `mcp_server/bussola_mcp/dominio/fakes.py` | `RepositorioFake` e `BuscadorFake` sobre `contracts/fixtures/` |
| `*/logging_json.py` (os dois serviços) | Logger JSON de §9 |
| `agent/bussola_agent/estado.py` | Chaves e enum de §6, mais os helpers de leitura e escrita |
| `agent/bussola_agent/callbacks.py` | Encadeador `registrar(fase, funcao, ordem)` e os 4 callbacks agregados |
| `agent/bussola_agent/extensoes.py` | Registro de ferramentas e instruções (§6) |
| `agent/bussola_agent/persistencia.py` | `RegistroApp`, modelos `Plano`/`Consentimento`/`EventoAuditoria`/`Acompanhamento` e `RegistroEmMemoria` |
| `agent/bussola_agent/mcp_conexao.py` | `MCPToolset` (streamable HTTP, OIDC opcional) e `chamar_ferramenta` |

### 3.4 Fixtures e mock

- **`data/scripts/gerar_fixtures.py`:**
  - usa SQL de referência direto em `hackathon_dados.extrato_sintetico`,
    só leitura;
  - gera `contracts/fixtures/` conforme `contratos.md` §8, para o âncora e
    o controle, 12 meses;
  - os golden das ferramentas P0 (`__ate_202506`, `__ate_202512`) e
    `resumo_mes__AAAAMM` são calculados por uma implementação de
    referência simples dentro do próprio script. São **provisórios**: o 001
    os substitui.
- **`contracts/fixtures/rag/trechos_exemplo.json`:** trechos curados do
  corpus de conhecimento (lista de `TrechoCorpus`), nos temas `norma_bacen`,
  `credito`, `boas_praticas` e `produto` (`reserva_objetivo`, com `fonte.url`).
- **`mcp_server/bussola_mcp/server.py` (mock):**
  - FastMCP em streamable HTTP, `/mcp`, `0.0.0.0:$PORT`;
  - registra as 7 ferramentas P0 e `resumo_mes`, com as assinaturas exatas
    de §5;
  - responde com as fixtures (regra de §8);
  - valida o UUID;
  - devolve `USUARIO_INEXISTENTE` para UUID fora de `usuarios.json`.
- **`agent/bussola_agent/agent.py` (hello):**
  - `root_agent` ADK com `MCPToolset` via `mcp_conexao`;
  - instrução mínima em pt-BR;
  - instala os 4 callbacks agregados (cadeias vazias) e chama
    `carregar_extensoes()`.

  O 004 substitui este agente.

### 3.5 Plataforma GCP (`batalha-time-07-lkbv`, `us-central1`)

- **`data/scripts/aplicar_ddl.py`:** cria de forma idempotente
  `bussola_dados`, `bussola_app` e `bussola_app_dev`, com
  suas tabelas, em `us-central1`.
- **`deploy/smoke_modelos.py`:** valida o ID do Gemini Flash (§5 do mestre:
  3.8 → 3.7 → 3.5 Flash, o primeiro que responder) e do modelo de
  embedding, via Vertex (`GOOGLE_GENAI_USE_VERTEXAI=TRUE`) com credenciais
  do integrante.
  - Grava os IDs em `contracts/env.example` e o relatório em
    `specs/000-fundacao-contratos/modelos.md`: modelos testados, latência e
    dimensão do embedding.
- **`deploy/` hello:**
  - `build_push.sh <servico>`: `docker buildx --platform linux/amd64`,
    com tag = SHA curto, e push para
    `us-central1-docker.pkg.dev/batalha-time-07-lkbv/agentes/<servico>`;
  - `deploy.sh <servico> [--tag cNNN --no-traffic]`.
  - Publica `bussola-mcp` (mock) **privado** (`--no-allow-unauthenticated`)
    e `bussola-agent` (hello).
  - Registra o que funcionou com a SA default. Espera-se que a chamada ao
    Gemini no Cloud Run falhe por falta de IAM; isso alimenta a decisão
    Plano A/B.
- **`deploy/iam_datasets.sh`:** Plano B de IAM em nível de dataset para a
  SA default:
  - `dataViewer` em `bussola_dados`;
  - `dataEditor` em `bussola_app` e `bussola_app_dev`.

  Deve ser executado por um integrante **com confirmação humana**.
- **Pedidos ao owner:** redigir `specs/000-fundacao-contratos/pedidos-owner.md`
  com os 4 itens do mestre §16, prontos para envio. Quem envia é um
  integrante (Pessoa D no plano de 4 pessoas, Pessoa B no
  [roadmap de 2 pessoas](./roadmap-2-pessoas.md)); o agente não envia
  mensagens. Registrar o status e a decisão Plano A/B.

## 4. Critérios de aceite

- [ ] Spec Kit inicializado (integração Claude), com a constituição contendo
      os princípios de 3.1. `CLAUDE.md` presente.
- [ ] `make lint` e `make test` verdes nos dois projetos com
      `BUSSOLA_FAKES=TRUE`, **sem acesso à rede ou ao GCP**.
- [ ] Todos os artefatos marcados como 000 em `contratos.md` §1 existem.
      Teste de contrato garante que as colunas do DDL batem com os modelos
      Pydantic e que o schema das ferramentas do mock bate com §5.
- [ ] Fixtures geradas para âncora e controle. Valores de referência do
      âncora dentro de 1% (`contratos.md` §8).
- [ ] `make mcp` sobe o mock. Um `fastmcp.Client` lista as 8 ferramentas
      com os parâmetros de §5. Chamada com UUID desconhecido retorna
      `USUARIO_INEXISTENTE`; UUID malformado retorna `ENTRADA_INVALIDA`.
- [ ] Teste sem LLM: o `MCPToolset` do agente conecta no mock local e lista
      as ferramentas.
- [ ] Smoke manual registrado em `specs/000-*/smoke.md`: agente hello local
      responde "qual é o meu perfil financeiro?" chamando
      `perfil_financeiro`.
- [ ] Encadeador de callbacks testado: ordem crescente, primeiro retorno não
      nulo interrompe, as 4 fases funcionam.
- [ ] `extensoes.carregar_extensoes()` tolera pacotes ausentes (teste).
- [ ] `RegistroEmMemoria` implementa `RegistroApp` (teste).
- [ ] `aplicar_ddl.py` cria os 3 datasets e as tabelas. Uma segunda execução
      não altera nada.
- [ ] IDs de Gemini Flash e de embedding validados e gravados em
      `contracts/env.example`.
- [ ] Imagens dos 2 serviços no AR `agentes`, e ambos publicados em Cloud
      Run `us-central1`. O MCP é privado e aceita chamada com ID token de
      um integrante.
- [ ] Pedidos ao owner redigidos e decisão Plano A/B registrada.
- [ ] Após o merge em `main`: tag `contratos-v1` publicada.

## 5. Cenários de teste

- **Contrato de dados:** para cada tabela do DDL, o modelo Pydantic tem os
  mesmos nomes e tipos.
- **Mock:**
  - `perfil_financeiro(âncora, 202506)` devolve o golden `__ate_202506`
    com um aviso de mock;
  - com `202512`, devolve o golden `__ate_202512`.
- **Mock, entradas inválidas:**
  - `simular_objetivo` com `prazo_meses` e `aporte_mensal` juntos retorna
    `ENTRADA_INVALIDA`;
  - `ate_anomes = 202601` retorna `ENTRADA_INVALIDA`.
- **Callbacks:** função com ordem 10 que retorna um valor impede a execução
  da função com ordem 20.
- **Fakes:** `RepositorioFake.perfil_mensal(controle, 202503)` retorna 3
  meses do controle e nenhum do âncora.

## 6. Dependências e gate de merge

- **Dependências:** nenhuma.
- **Gate de merge:**
  - critérios da §4, exceto os que dependem do owner, que ficam
    registrados como pendência;
  - revisão por **pelo menos 2 pessoas** do time, porque congela os
    contratos.
- **Depois do merge:** criar a tag `contratos-v1` e avisar o time. Os
  ciclos 001, 003, 004 e 007 (e, se houver capacidade, 002 e 005) criam
  suas worktrees a partir de `main`.

## 7. Fora de escopo

- Métricas e simulação reais (001).
- Corpus completo e embeddings do RAG (002). O 000 entrega só o corpus
  curado de exemplo em `contracts/fixtures/rag/` (Q-17).
- Ferramentas reais do MCP (003).
- Prompts e jornada (004).
- Gate de consentimento e guardrails (005).
- Replay (006).
- IAM final, canal da demo e runbook do Antigravity (007).

## 8. Questões em aberto

- **Q2 do mestre (regras de cenário):** usar a proposta de `RegrasCenario`
  de `contratos.md` §4 até decisão do time.
- **Q7 do mestre (pedidos ao owner):** o resultado define Plano A ou B. O
  000 deixa os dois caminhos preparados.
- Se nenhum Gemini Flash responder via Vertex com credenciais do
  integrante, registrar e testar via Gemini API. O valor da chave vem do
  Secret Manager na hora e nunca é impresso.

## 9. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| Contratos v1 materializados | `contratos.md` | EXPLICIT |
| Datasets `bussola_*` e pipeline build → push → deploy hello | Mestre §15, Bloco 0 | EXPLICIT |
| Validação dos IDs de modelo | Mestre §13 e §17 | EXPLICIT |
| Pedidos ao owner e Plano B | Mestre §16 | EXPLICIT |
| MCP mock servindo fixtures | Plano de ciclos §5.8 | INFERRED |
| Ordem de tentativa dos modelos Flash | Mestre §5 (lista do Model Garden) | INFERRED |
| Resultado dos pedidos ao owner | Mestre §20, Q7 | UNRESOLVED |
