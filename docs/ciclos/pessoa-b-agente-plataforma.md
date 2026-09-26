# Spec Master — Pessoa B: agente, experiência e plataforma

> **Disparo:** `/spec-master docs/ciclos/pessoa-b-agente-plataforma.md`, no
> Claude Code, **dentro da worktree do ciclo da vez** (§3). O mesmo comando
> serve para todos os ciclos da Pessoa B: a branch diz qual ciclo roda.
>
> **Responsável:** ______ · **Revisora dos PRs:** Pessoa A (______).
> **Plano:** [roadmap de 2 pessoas](./roadmap-2-pessoas.md) ·
> [plano de ciclos](./README.md) · [contratos](./contratos.md).
>
> **Leitura obrigatória antes do Step 3:**
>
> - o arquivo do ciclo alvo (§3), inteiro;
> - [roadmap de 2 pessoas](./roadmap-2-pessoas.md) §1, §3, §4 e §5;
> - [plano de ciclos](./README.md) §5;
> - as seções de [contratos.md](./contratos.md) citadas no arquivo do ciclo;
> - no 007, também o [prompt do Claude Design](../design/prompt-claude-design-chat.md)
>   e o que estiver versionado em `docs/design/`.

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Um run = um ciclo = uma feature.** Este arquivo é só a porta de entrada
   da trilha. Ele não junta ciclos numa execução só e não muda as regras do
   [README §5](./README.md).
2. **Resolver o ciclo alvo antes do Step 1:**
   - leia a branch atual (`git branch --show-current`) e ache a linha
     correspondente na §3;
   - se `SPECIFY_FEATURE_DIRECTORY` estiver definido, ele tem de apontar
     para o mesmo `specs/NNN-slug`; se não bater, pare e mostre a
     divergência;
   - se a branch não estiver na §3 (por exemplo, `main`), **pare** com
     `BLOCKED` e mostre os comandos da §6. Não crie worktree nem branch.
3. **Fonte da feature: o arquivo do ciclo alvo.** Dele saem `id`,
   `spec_directory`, escopo, propriedade, critérios de aceite, cenários e
   gate de merge.
   - Os outros ciclos desta trilha entram no Step 3 só como contexto
     (sequência e dependências), **nunca** como `FeatureExecution`.
   - Exceção única: no 007, a §5.3 desta trilha acrescenta o escopo do
     front **se** o marco Q4 estiver presente (§4).
   - Se esta trilha e o arquivo do ciclo divergirem, vale o arquivo do
     ciclo. Registre a divergência em `specs/NNN-slug/questoes.md`.
4. **Checar os marcos antes do Step 5** (§4). Grave o resultado em
   `specs/NNN-slug/marcos.md`. Ele define o modo de trabalho de cada parte
   do ciclo: mock/fixtures ou real.
5. **Tarefa que depende de marco ausente** fica marcada `[aguarda Sx]` no
   `tasks.md` e não é implementada.
   - Se sobrar alguma no fim, o run termina `BLOCKED (aguardando Sx)`.
   - Quando o marco sair, rode o mesmo comando na mesma worktree. O Step 0
     do Spec Master retoma de onde parou.
6. **Escreva só nos caminhos do ciclo alvo** (§4 do arquivo do ciclo).
   **Nunca** escreva nos caminhos da Pessoa A: `contracts/` (mudança só por
   PR `contracts:` aprovado pelos dois), `data/`, `mcp_server/`,
   `agent/bussola_agent/acompanhamento/`, `agent/tests/acompanhamento/`,
   `eval/rag/` e `eval/acompanhamento/`.
7. **Step 2:** o Spec Kit já vem de `main` (quem inicializa é o 000, da
   Pessoa A). Estratégia Git **Trunk-Based**.
8. **Constituição congelada** desde o `contratos-v1`. Proposta de mudança
   vai para `specs/NNN-slug/proposta-constituicao.md`, sem aplicar.
9. **Mensagens e IAM:** o Spec Master não envia mensagens nem muda IAM ou
   tráfego sem confirmação humana. No relatório final, ele deixa pronto o
   texto do **aviso de marco** (§5) para a Pessoa B enviar.
10. **Ao final de cada run:**
    - `make test` e `make lint` verdes (no 007, com `shellcheck`);
    - rastreabilidade em `specs/NNN-slug/traceability.md`;
    - PR para `main` com revisão da Pessoa A.

## 2. Bloco 0 (Onda 0, fora do Spec Master)

Roda em paralelo ao 000 da Pessoa A. São tarefas humanas; não abra
`/spec-master` para elas.

- [ ] **Pedidos ao owner** (mestre §16): enviar o texto de
      `specs/000-fundacao-contratos/pedidos-owner.md` assim que ele existir
      no PR do 000. Registrar a resposta e a decisão Plano A/B no PR.
- [ ] **Modelos:** validar cedo, com credenciais próprias via Vertex, os IDs
      do Gemini Flash e do embedding. Passar o resultado para A; o
      `deploy/smoke_modelos.py` do 000 formaliza.
- [ ] **Invoker:** confirmar se `allUsers` é permitido no `bussola-agent`
      (mestre §16, item 4). Isso define canal por invoker público ou por
      proxy.
- [ ] **Design:** rodar o [prompt do Claude Design](../design/prompt-claude-design-chat.md)
      (Dynamic Glass com Tailwind) e versionar frames F1–F7, componentes e
      tokens em `docs/design/`.
- [ ] **Q4, antes do merge do 000:** fechar com o time entre ADK Web UI e
      front próprio. Se for front próprio, pedir a A que inclua no mapa de
      [contratos §1](./contratos.md), no próprio PR do 000:
  - `web/` com dono 007;
  - o ponto de entrada que serve o build pelo `bussola-agent`, como
    acréscimo em `agent/` com dono 007.
- [ ] **S0:** revisar o PR do 000.

## 3. Ciclos da trilha

| # | Ciclo | Sessão | Onda | Branch · worktree | Contexto do ciclo | Pode começar | Gate exige |
|---|---|---|---|---|---|---|---|
| 1 | **004** Agente e jornada | B1 | 1 | `004-agente-bussola-jornada` · `../bussola-004` | [004-agente-bussola-jornada.md](./004-agente-bussola-jornada.md) | S0 | S3 |
| 2 | **007** Canal, deploy e operação | B2 | 1–2 | `007-canal-deploy-demo` · `../bussola-007` | [007-canal-deploy-demo.md](./007-canal-deploy-demo.md) | S0 | S5 |
| 3 | **005** Consentimento e governança | B1 | 2 | `005-consentimento-governanca` · `../bussola-005` | [005-consentimento-governanca.md](./005-consentimento-governanca.md) | S4 | S4 |

A sessão B1 faz 004 → 005. A sessão B2 fica com o 007 nas Ondas 1 e 2: o
run para em `BLOCKED (aguardando S5)` depois da parte sobre hello e
fixtures, e retoma no mesmo worktree quando o S5 sair. No máximo 2 sessões
abertas ao mesmo tempo.

## 4. Marcos e como checar

Rode `git fetch origin` antes. Cada ciclo versiona a própria
rastreabilidade no merge ([README §5](./README.md), regra 4). Por isso,
"ciclo NNN em `main`" = o arquivo `specs/NNN-*/traceability.md` existe em
`origin/main`.

| Marco | Significa | Quem entrega | Como checar |
|---|---|---|---|
| **S0** | 000 em `main` e tag publicada | **A** | `git ls-remote --tags origin contratos-v1` devolve uma linha |
| **Q4** | Front próprio aprovado | A + B (no 000) | `git show origin/main:docs/ciclos/contratos.md \| grep -E '── web/ +007'` encontra a linha |
| **S3** | 003 em `main` | **A** | `git cat-file -e origin/main:specs/003-mcp-dados-conhecimento/traceability.md` |
| **S4** | 004 em `main` | B | `git cat-file -e origin/main:specs/004-agente-bussola-jornada/traceability.md` |
| **S5** | 003 e 004 em `main` | A + B | S3 e S4 presentes |
| **S6** | 005 em `main` | B | `git cat-file -e origin/main:specs/005-consentimento-governanca/traceability.md` |
| 002 / 006 em `main` | Novas imagens para publicar | **A** | mesmo teste com `specs/002-*` e `specs/006-*` |

Sem a linha de `web/` no mapa de contratos, o canal é a ADK Web UI e o
escopo do front **não** entra no 007.

## 5. O que muda em cada ciclo na trilha B

### 5.1 004 — Agente e jornada

- **Modo:** MCP mock do 000 (`make mcp` com `BUSSOLA_FAKES=TRUE`) até o
  S3.
- **Hooks:** instale os callbacks agregados e chame
  `extensoes.carregar_extensoes()`. O 005 (seu) e o 006 (da Pessoa A)
  entram por eles. Não implemente gate, guardrails, auditoria nem
  acompanhamento.
- **Pensando no front:** o front deriva cards, rótulos e stepper dos
  eventos (`functionCall`, `functionResponse` e `session.state`), não do
  texto. Por isso:
  - não renomeie chaves de `session.state` fora de
    [contratos §6](./contratos.md);
  - não reescreva o envelope `dados`/`fonte`/`avisos` das ferramentas.
- **Gate:** jornada OBJETIVO → ORIENTAR contra o MCP **real** (local) e
  eval de números. Exige o S3; essas tarefas ficam `[aguarda S3]`.
- **Cloud Run:** só `--tag c004 --no-traffic`.
- **Aviso S4 para A:** "004 em `main`, com hooks e `carregar_extensoes()`.
  O 006 já pode testar suas ferramentas no agente real. O 005 começa agora
  na sessão B1."

### 5.2 007 — Canal, deploy e operação

- **Primeiro passo (entrega antecipada):** publique os serviços mock/hello
  do 000 com a IAM final (MCP privado, invoker, OIDC, `max-instances=1`) e
  teste o rollback.
- **Canal:**
  - **sem o marco Q4:** ADK Web UI, conforme §3.2 do arquivo do ciclo;
  - **com o marco Q4:** ADK Web UI como fallback **e** o front da §5.3.
- **Deploy real:** exige o S5. Essas tarefas ficam `[aguarda S5]`.
- **Antigravity:** o ensaio depende das credenciais GCP no Antigravity
  (mestre Q5). Se não houver, registre em
  `specs/007-*/ensaio-antigravity.md` como pendência.
- **Depois do merge (5º na ordem):** 002, 005 e 006 entram por troca de
  imagem, seguindo `docs/operacao.md`.
- **Aviso para A, no merge:** "007 em `main`. Os dois serviços reais estão
  em Cloud Run com OIDC; deploys do 002 e do 006 seguem o runbook."

### 5.3 Front próprio, dentro do 007 (só com o marco Q4)

**Stack e entrega**

- `web/` com Vite, React, TypeScript e **Tailwind CSS v4**, com os tokens
  Dynamic Glass do handoff em `docs/design/`.
- O build estático é servido pelo próprio `bussola-agent`, na mesma origem
  da API do ADK: sem CORS e sem um terceiro serviço Cloud Run.
- O ponto de entrada que monta os estáticos e o estágio de build Node no
  `Dockerfile` do agente são acréscimos em `agent/`, declarados no mapa de
  contratos junto com `web/`. Como o 004 também é da Pessoa B, o conflito
  se resolve dentro da trilha.

**Contrato front ↔ agente**

- Sessões e mensagens pela API HTTP do ADK (criar sessão + `/run_sse`).
- `functionCall` vira `LinhaFerramenta`.
- `functionResponse` com o envelope de [contratos §5](./contratos.md) vira o
  card da ferramenta e o `ChipFonte`.
- Resposta com `erro.codigo` vira `ErroFerramenta`.
- `session.state` alimenta o `StepperJornada` e o painel "Bastidores".
- **Nenhum número na tela** que não tenha vindo de um `functionResponse`.
- O front **nunca** consulta o BigQuery. A aba "Auditoria" mostra os eventos
  da própria sessão.

**Momentos da jornada**

- **Consentimento:** os botões do `CardConsentimento` enviam `sim` ou `não`
  como mensagem. O gate do 005 lê a última mensagem do usuário, então o
  consentimento continua acontecendo na conversa.
- **Modo demo:** "Avançar um mês ▸" envia a mensagem `avançar um mês`. O 006
  (Pessoa A) leva essa frase a `avancar_mes()`.

**Desenvolvimento sem backend**

- Na Onda 1, grave fixtures de eventos SSE do agente hello do 000 em
  `web/fixtures/` e desenvolva sobre elas.
- Regrave as fixtures depois do S4 e do S6.

**Critérios de aceite a mais**

- [ ] F1–F7 do [prompt do Claude Design](../design/prompt-claude-design-chat.md)
      ponta a ponta com o âncora, contra o agente real, em desktop 1440.
- [ ] Mobile 390 e modo escuro, se não tiverem sido cortados
      ([roadmap §6](./roadmap-2-pessoas.md), item 5).
- [ ] Testes de componente cobrindo envelope → card, `erro.codigo` →
      `ErroFerramenta` e consentimento pendente → `CardConsentimento`.
- [ ] Build servido pelo `bussola-agent` em Cloud Run; nenhum segredo no
      bundle.

**Fallback:** se, no início da Onda 3, o front não cobrir F1–F7 ponta a
ponta, a demo usa a ADK Web UI. Registre em `specs/007-*/corte.md` e ajuste
`docs/roteiro-demo.md`.

### 5.4 005 — Consentimento e governança

- **Modo:** `RegistroEmMemoria` e `BUSSOLA_FAKES`. Testes em BigQuery
  gravam **só** em `bussola_app_dev`.
- **Entrada no agente:** `callbacks.registrar` nas ordens reservadas e
  `extensoes` nas ordens 50–69, sem editar o `agent.py` do 004.
- **Model Armor:** template `bussola-guard` se o owner criar; senão, o
  fallback de callbacks (item 3 da linha de corte).
- **Pensando no front:** mantenha os nomes de `tipo_evento` e de ações de
  [contratos §6](./contratos.md). O `CardConsentimento` e o
  `AlertaGuardrail` dependem deles.
- **Gate:** S4, gate e auditoria verificados em `bussola_app_dev`, e
  guardrail com testes de injection.
- **Aviso S6 para A:** "005 em `main`. O `ajustar_plano` do 006 já pode
  usar o gate real; roteiro 202506 → 202508 liberado."

## 6. Como disparar

```bash
git switch main && git pull
git worktree add ../bussola-NNN -b NNN-slug
cd ../bussola-NNN
SPECIFY_FEATURE_DIRECTORY=specs/NNN-slug claude
```

No Claude Code, dentro da worktree:

```text
/spec-master docs/ciclos/pessoa-b-agente-plataforma.md
```

- **Antes do S0:** só o Bloco 0. Os ciclos 004 e 007 começam a partir de
  `main` com a tag `contratos-v1`.
- **No app desktop:** abra uma sessão nova apontando para `../bussola-NNN`.
  Sem a variável de ambiente, o número da spec vem da §3.
- **Respostas nos gates do Spec Master:** as do [README §6](./README.md).
- **Limpeza após o merge:** `git worktree remove ../bussola-NNN` e
  `git branch -d NNN-slug`.

## 7. Integração final (Onda 3, B lidera)

Fora do Spec Master. Checklist completo no [README §8](./README.md). Do
lado B:

- [ ] Decidir, no início da onda, front próprio ou ADK Web UI (§5.3,
      fallback).
- [ ] Publicar as imagens finais do 002, 005 e 006 pelo runbook e promover
      a revisão final nos dois serviços.
- [ ] Rodar o roteiro de ≤ 5 min ponta a ponta com o âncora: 6 estados,
      consentimento e um avanço de mês.
- [ ] Rodar o eval do 004 e o do 005 contra a produção e juntar com os do
      002 e do 006 (Pessoa A) em `eval/RESULTADOS.md`.
- [ ] Gravar o vídeo de backup e ensaiar a operação no Antigravity.
- [ ] Conferir a Definition of Done do mestre §19.

## 8. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| Divisão A/B por serviço e diretório | [Roadmap de 2 pessoas](./roadmap-2-pessoas.md) §1 | EXPLICIT |
| Um contexto de Spec Master por pessoa | Pedido do time | EXPLICIT |
| Um run = um ciclo = uma feature | [README §5](./README.md), regra 1 | EXPLICIT |
| Front Dynamic Glass com Tailwind | Pedido do time; [prompt do Claude Design](../design/prompt-claude-design-chat.md) | EXPLICIT |
| Stack do front e serviço pelo `bussola-agent` | [Roadmap](./roadmap-2-pessoas.md) §5 | INFERRED |
| Ciclo alvo resolvido pela branch da worktree | Esta trilha | INFERRED |
| Marco de merge = `traceability.md` em `origin/main` | [README §5](./README.md), regra 4 | INFERRED |
| Consentimento e avanço de mês por mensagens da conversa | Ciclos 005 §3.2 e 006 §3.1 | INFERRED |
| Canal da demo | Mestre §20, Q4 | UNRESOLVED |
| `allUsers` no invoker | Mestre §16, item 4 | UNRESOLVED |
| Credenciais GCP no Antigravity | Mestre §20, Q5 | UNRESOLVED |
