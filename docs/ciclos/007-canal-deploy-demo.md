# Ciclo 007 — F7 Canal da demo, deploy e operação no Antigravity

> **Disparo:** `/spec-master docs/ciclos/007-canal-deploy-demo.md`, no Claude
> Code, dentro da worktree `../bussola-007`, na branch
> `007-canal-deploy-demo`.
>
> **Onda:** 1. **Prioridade:** P0. **Spec:** `specs/007-canal-deploy-demo`.
> **Plano:** [README](./README.md).
>
> **Leitura obrigatória antes do Step 3:**
>
> - [contratos.md](./contratos.md) §1, §3, §7 e §9.
> - Contexto mestre [§5, §6, §10 F7, §13, §14, §16, §17 e §19](../contexto-spec-master.md).
> - [Blueprint](../blueprint-arquitetura.md) §7–§9.

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Uma única feature:** `id: canal-deploy-demo`,
   `spec_directory: specs/007-canal-deploy-demo`.
2. **Número fixo:** `SPECIFY_FEATURE_DIRECTORY=specs/007-canal-deploy-demo`.
3. **Step 2:** Spec Kit já inicializado. Estratégia Git **Trunk-Based**.
4. **Constituição congelada.** Proposta vai para
   `specs/007-*/proposta-constituicao.md`.
5. **Escreva só nos caminhos da §4.** Este ciclo **não altera** código dos
   serviços. Ele empacota, publica e documenta.
6. **Divisão de papéis:**
   - **Desenvolvimento:** Claude Code.
   - **Operação do produto pronto:** Google Antigravity. Este ciclo entrega
     o que o agente do Antigravity precisa para operar: `AGENTS.md` e
     `docs/operacao.md`.
   - **Não** gerar adaptador de Spec Master para Antigravity.
7. **Segredos:**
   - scripts nunca fazem `echo` de chave ou token;
   - `GOOGLE_API_KEY` (Plano B) é lida do Secret Manager no momento do
     deploy e nunca versionada;
   - o uso fica registrado como dívida técnica.
8. **Tráfego:** este é o **único** ciclo que move tráfego no Cloud Run.
   Mudanças de IAM são feitas por um integrante, com confirmação humana.
9. **Ao final:**
   - `make lint` verde, incluindo `shellcheck` nos scripts;
   - rastreabilidade em `specs/007-*/traceability.md`.

## 2. Propósito

Deixar os dois serviços rodando em Cloud Run no projeto do time, com um
canal conversacional para a demo e um roteiro ensaiado.

Também entrega o runbook que permite **operar o produto pelo Antigravity**:

- deploy;
- logs;
- auditoria;
- reset da demo;
- avanço de mês;
- rollback;
- Plano B.

## 3. Escopo e comportamento esperado

### 3.1 Deploy final (`deploy/`, assume o hello do 000)

- **`config.sh`:**
  - projeto, região (`us-central1`) e AR `agentes`;
  - nomes `bussola-mcp` e `bussola-agent`;
  - SA de runtime (`bussola-runtime`, se o owner criar; senão, a default
    compute).
- **`build_push.sh <servico>`:** `docker buildx --platform linux/amd64`,
  com tag = SHA do git, e push para o AR.
- **`deploy_mcp.sh`:**
  - `--no-allow-unauthenticated`;
  - `--service-account`;
  - `--max-instances=1`;
  - variáveis `BQ_*`, `RAG_BACKEND`, `EMBEDDING_MODEL` e `LOG_LEVEL`.
- **`deploy_agent.sh`:**
  - `--max-instances=1` (sessão em memória, mestre §13);
  - `MCP_URL` = URL do MCP + `/mcp`;
  - `MCP_USE_OIDC=TRUE`;
  - `BUSSOLA_MODEL`, `MODEL_ARMOR_TEMPLATE`, `ANCHOR_USER_ID`,
    `REPLAY_START_ANOMES` e `BQ_DATASET_APP=bussola_app`.
- **Invoker:** `roles/run.invoker` no `bussola-mcp` para a SA do agente, em
  nível de serviço.
- **Tags e tráfego:** `deploy_*.sh --tag cNNN` publica sem tráfego.
  `promover.sh <servico> <revisao|tag>` move 100%. `rollback.sh <servico>`
  volta para a revisão anterior registrada.
- **`plano_b.sh`:** alterna, por variáveis, para:
  - `BQ_MODO_LEITURA=memoria`;
  - `RAG_BACKEND=numpy`;
  - `GOOGLE_GENAI_USE_VERTEXAI=FALSE` + `GOOGLE_API_KEY` vinda do Secret
    Manager, sem imprimir.

  Depende de `deploy/iam_datasets.sh` do 000 já aplicado.
- **`smoke.sh`:**
  - lista as ferramentas do MCP com um ID token;
  - abre uma sessão no agente pela API do ADK e envia "qual é o meu perfil
    financeiro?";
  - valida que a resposta cita `perfil_financeiro`.

### 3.2 Canal da demo (Q4)

- **Recomendado:** ADK Web UI servida pelo próprio `bussola-agent`.
- **Invoker público:** se `allUsers` for permitido (mestre §16, item 4),
  usar `--allow-unauthenticated` **só** no agente, **nunca** no MCP.
- **Sem invoker público:** `gcloud run services proxy bussola-agent
  --region us-central1 --port 8080` na máquina da demo.
- **Front próprio no estilo ia.i (`docs/design/`):** fora deste ciclo, a
  menos que a Q4 seja fechada a favor dele **antes do merge do 000**.
  Nesse caso:
  - `web/` entra no mapa de contratos §1 como dono 007, via PR
    `contracts:`;
  - a trilha segue o [roadmap de 2 pessoas](./roadmap-2-pessoas.md) §5
    (Vite + React + Tailwind v4, servido pelo `bussola-agent`, fixtures
    SSE);
  - a ADK Web UI continua como fallback.

### 3.3 Operação no Antigravity

- **`AGENTS.md`** (raiz), lido pelo agente do Antigravity:
  - **O que é o produto:** serviços, região, datasets e URLs obtidas por
    comando.
  - **Papel do agente:** operar, não desenvolver. Mudança de código vira
    tarefa de ciclo no Claude Code.
  - **Comandos permitidos:** scripts de `deploy/`, `gcloud run services
    describe`, `gcloud logging read` e `bq query` de leitura.
  - **Ações que exigem confirmação humana:**
    - promover ou dar rollback;
    - trocar para o Plano B;
    - mudar IAM ou variáveis.
  - **Proibido:**
    - imprimir segredos;
    - apagar datasets, tabelas ou auditoria;
    - `allUsers` no MCP;
    - editar código dos serviços.
  - **Referência:** tudo aponta para `docs/operacao.md`.
- **`docs/operacao.md`** (runbook com comandos prontos para copiar):
  1. pré-requisitos: autenticação gcloud no Antigravity, projeto e região;
  2. status: serviços, revisões, tags, tráfego e URLs;
  3. deploy de uma nova versão: build → push → tag → smoke → promover;
  4. smoke test;
  5. logs no Cloud Logging, com filtros por `servico`, `session_id`,
     `erro_codigo`, `evento=guardrail_bloqueio` e
     `evento=numero_sem_fonte`;
  6. auditoria no BigQuery: consentimentos por sessão, eventos por
     `tipo_evento`, planos criados e acompanhamentos;
  7. operação da demo:
     - abrir o canal ou o proxy;
     - resetar a sessão (nova sessão na UI; um restart da revisão limpa a
       memória);
     - avançar mês pela conversa ("avançar um mês");
     - mudar o mês inicial ou o usuário-âncora via variável;
  8. rollback;
  9. troca para o Plano B e volta;
  10. troubleshooting: 403 no MCP (invoker/OIDC), 429/quota do Gemini,
      `INDISPONIVEL` do BigQuery (IAM do dataset) e sessão perdida (mais de
      uma instância);
  11. pendências com o owner e dívidas (chave de API em variável).

### 3.4 Roteiro e documentação

- **`docs/roteiro-demo.md`** (≤ 5 min):
  - falas exatas do apresentador para os 6 estados;
  - ferramentas esperadas em cada passo;
  - o momento do consentimento ("sim");
  - um avanço de mês com desvio;
  - checklist pré-demo (warm-up da instância, proxy aberto, sessão nova,
    vídeo de backup à mão);
  - plano de contingência.
- **README, seção "Como rodar local / publicar":**
  - `make mcp` + `make agent` com `BUSSOLA_FAKES`;
  - como rodar com GCP;
  - como publicar (scripts de `deploy/`);
  - links para `docs/operacao.md` e `docs/roteiro-demo.md`.
- **Vídeo de backup:** roteiro de gravação neste ciclo. A gravação acontece
  na integração final, com o produto completo.

### 3.5 Entrega antecipada (reduz risco)

- Assim que este ciclo começar, publique os serviços **mock/hello** com a
  IAM final (MCP privado, invoker, OIDC, `max-instances=1`) e teste o
  rollback.
- No fim, o deploy real vira só troca de imagem.

## 4. Propriedade (escreve só aqui)

- `deploy/`
- `AGENTS.md`
- `docs/operacao.md` e `docs/roteiro-demo.md`
- Seção "Como rodar / publicar" do `README.md`
- `specs/007-canal-deploy-demo/`
- Ajuste da linha de entrada (`CMD`) dos `Dockerfile`s, **só** se o canal
  exigir. Acréscimo coordenado com o dono (000).

## 5. Contratos

- **Consome:**
  - imagens dos dois serviços;
  - variáveis de `contratos.md` §7;
  - logs de §9;
  - tabelas de `bussola_app` (§3) para as consultas de auditoria.
- **Provê:**
  - serviços publicados e canal;
  - scripts de operação;
  - `AGENTS.md` e runbook;
  - roteiro.

## 6. Critérios de aceite

- [ ] MCP server e serviço Bússola publicados em Cloud Run (`us-central1`) a
      partir de imagens do AR `agentes`. O MCP é privado e o agente o
      chama com OIDC. `max-instances=1`.
- [ ] Canal de conversa acessível na demo, por invoker público no agente
      ou por proxy documentado.
- [ ] `smoke.sh` passa contra a produção.
- [ ] Rollback testado: `promover.sh` → `rollback.sh` volta a revisão
      anterior sem downtime perceptível.
- [ ] `plano_b.sh` testado ao menos uma vez em revisão com tag
      (`--no-traffic`).
- [ ] `AGENTS.md` e `docs/operacao.md` publicados. **Ensaio no
      Antigravity:** um integrante pede ao agente do Antigravity
      "status dos serviços", "últimos erros", "consentimentos da última
      sessão" e "faça rollback do agente". O agente executa seguindo o
      runbook e pede confirmação antes do rollback. Resultado registrado em
      `specs/007-*/ensaio-antigravity.md`.
- [ ] Roteiro de demo (≤ 5 min) cobrindo os 6 estados, com consentimento e
      um avanço de mês.
- [ ] Vídeo de backup gravado. Pode ser concluído na integração final, mas
      a responsabilidade é deste ciclo.
- [ ] O README permite a outro integrante rodar local e publicar
      (DoD §19.5).

## 7. Cenários de teste

- O agente em produção chama o MCP sem OIDC (`MCP_USE_OIDC=FALSE`): 403
  esperado, documentado no troubleshooting.
- Uma nova revisão com defeito (tag `c007-bad`) não recebe tráfego.
  `rollback.sh` depois de `promover.sh` volta ao estado anterior.
- Uma instância nova (restart) perde a sessão em memória. O runbook explica
  como iniciar uma sessão nova sem perder a auditoria.
- `grep` nos scripts e no histórico: nenhuma chave ou token em texto.

## 8. Dependências e gate de merge

- **Dependências duras:** 000 (pipeline hello, datasets, IAM de dataset).
- **Para o deploy real:** 003 e 004 mergeados. 005 e 006 entram por troca
  de imagem.
- **Gate de merge:**
  - os dois serviços reais em Cloud Run com OIDC;
  - canal acessível;
  - ensaio no Antigravity registrado.

  Este é o **5º na ordem de merge**. Os ciclos seguintes (002, 005, 006)
  entram por novo deploy seguindo o runbook.

## 9. Fora de escopo

- Código do MCP e do agente.
- Front próprio estilo ia.i (P2).
- Cloud Scheduler, Workflows ou tracing (bloqueados).
- Criação de SA, bucket ou Model Armor. Esses são pedidos ao owner (§16).

## 10. Questões em aberto

- **Q4 do mestre:** canal ADK Web UI (recomendado) ou front próprio.
- **Mestre §16 item 4:** `allUsers` permitido?
- **Q5 do mestre:** as credenciais GCP no Antigravity são as mesmas dos
  integrantes? Isso define o que o runbook pode executar.
- **Q1 do mestre:** data e duração da demo.

## 11. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| Deploy em Cloud Run a partir do AR, canal, roteiro, vídeo e README | Mestre §10 F7 | EXPLICIT |
| Build local `linux/amd64` + `--image` (sem bucket) | Mestre §13 e §17 | EXPLICIT |
| Operação do produto pronto no Antigravity | Pedido do time (desenvolver no Claude Code, operar no agy) | EXPLICIT |
| `AGENTS.md` + runbook como interface de operação | Este ciclo | INFERRED |
| `max-instances=1` | Mestre §13 | EXPLICIT |
| Plano B por variáveis | Mestre §16 | EXPLICIT |
| Canal final e invoker público | Mestre §20 Q4 e §16 item 4 | UNRESOLVED |
| Credenciais no Antigravity | Mestre §20, Q5 | UNRESOLVED |
