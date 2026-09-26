# Spec Master — Pessoa A: dados, ferramentas e tempo

> **Disparo:** `/spec-master docs/ciclos/pessoa-a-dados-ferramentas.md`, no
> Claude Code, **dentro da worktree do ciclo da vez** (§2). O mesmo comando
> serve para todos os ciclos da Pessoa A: a branch diz qual ciclo roda.
>
> **Responsável:** ______ · **Revisora dos PRs:** Pessoa B (______).
> **Plano:** [roadmap de 2 pessoas](./roadmap-2-pessoas.md) ·
> [plano de ciclos](./README.md) · [contratos](./contratos.md).
>
> **Leitura obrigatória antes do Step 3:**
>
> - o arquivo do ciclo alvo (§2), inteiro;
> - [roadmap de 2 pessoas](./roadmap-2-pessoas.md) §1, §3 e §4;
> - [plano de ciclos](./README.md) §5;
> - as seções de [contratos.md](./contratos.md) citadas no arquivo do ciclo.

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Um run = um ciclo = uma feature.** Este arquivo é só a porta de entrada
   da trilha. Ele não junta ciclos numa execução só e não muda as regras do
   [README §5](./README.md).
2. **Resolver o ciclo alvo antes do Step 1:**
   - leia a branch atual (`git branch --show-current`) e ache a linha
     correspondente na §2;
   - se `SPECIFY_FEATURE_DIRECTORY` estiver definido, ele tem de apontar
     para o mesmo `specs/NNN-slug`; se não bater, pare e mostre a
     divergência;
   - se a branch não estiver na §2 (por exemplo, `main`), **pare** com
     `BLOCKED` e mostre os comandos da §5. Não crie worktree nem branch.
3. **Fonte da feature: o arquivo do ciclo alvo.** Dele saem `id`,
   `spec_directory`, escopo, propriedade, critérios de aceite, cenários e
   gate de merge.
   - Os outros ciclos desta trilha entram no Step 3 só como contexto
     (sequência e dependências), **nunca** como `FeatureExecution`.
   - Se esta trilha e o arquivo do ciclo divergirem, vale o arquivo do
     ciclo. Registre a divergência em `specs/NNN-slug/questoes.md`.
4. **Checar os marcos antes do Step 5** (§3). Grave o resultado em
   `specs/NNN-slug/marcos.md`. Ele define o modo de trabalho de cada parte
   do ciclo: fakes ou real.
5. **Tarefa que depende de marco ausente** fica marcada `[aguarda Sx]` no
   `tasks.md` e não é implementada.
   - Se sobrar alguma no fim, o run termina `BLOCKED (aguardando Sx)`.
   - Quando o marco sair, rode o mesmo comando na mesma worktree. O Step 0
     do Spec Master retoma de onde parou.
6. **Escreva só nos caminhos do ciclo alvo** (§4 do arquivo do ciclo).
   - No 000, valem todos os caminhos marcados como 000 em
     [contratos §1](./contratos.md), inclusive em `agent/` e `deploy/`.
   - Nos demais ciclos, **nunca** escreva nos caminhos da Pessoa B:
     `agent/` (exceto `agent/bussola_agent/acompanhamento/` e
     `agent/tests/acompanhamento/`, que são do 006), `deploy/`, `web/`,
     `eval/agente/`, `eval/seguranca/`, `AGENTS.md`, `docs/operacao.md` e
     `docs/roteiro-demo.md`.
7. **Step 2:** estratégia Git **Trunk-Based**. `specify init --here` só no
   000; nos outros ciclos o Spec Kit já vem de `main`.
8. **Constituição:** só o 000 cria. Nos outros ciclos, a proposta de
   mudança vai para `specs/NNN-slug/proposta-constituicao.md`, sem aplicar.
9. **Mensagens:** o Spec Master não envia mensagens. No relatório final, ele
   deixa pronto o texto do **aviso de marco** (§4) para a Pessoa A enviar.
10. **Ao final de cada run:**
    - `make test` e `make lint` verdes;
    - rastreabilidade em `specs/NNN-slug/traceability.md`;
    - PR para `main` com revisão da Pessoa B.

## 2. Ciclos da trilha

| # | Ciclo | Sessão | Onda | Branch · worktree | Contexto do ciclo | Pode começar | Gate exige |
|---|---|---|---|---|---|---|---|
| 1 | **000** Fundação e contratos (lidera) | A1 | 0 | `000-fundacao-contratos` · `../bussola-000` | [000-fundacao-contratos.md](./000-fundacao-contratos.md) | já | revisão de B e Q4 confirmada por B |
| 2 | **001** Dados financeiros | A1 | 1 | `001-camada-dados-financeiros` · `../bussola-001` | [001-camada-dados-financeiros.md](./001-camada-dados-financeiros.md) | S0 | — |
| 3 | **003** MCP de dados e conhecimento | A2 | 1 | `003-mcp-dados-conhecimento` · `../bussola-003` | [003-mcp-dados-conhecimento.md](./003-mcp-dados-conhecimento.md) | S0 | S2 |
| 4 | **002** RAG financeiro | A1 | 2 | `002-rag-financeiro-dados` · `../bussola-002` | [002-rag-financeiro-dados.md](./002-rag-financeiro-dados.md) | S0 (corpus real após S1) | S1, S3 |
| 5 | **006** Acompanhamento com replay | A2 | 2 | `006-acompanhamento-replay` · `../bussola-006` | [006-acompanhamento-replay.md](./006-acompanhamento-replay.md) | S0 | S2, S3, S4, S6 |

A sessão A1 faz 000 → 001 → 002. A sessão A2 abre com o 003 logo após o S0
e segue para o 006. No máximo 2 sessões abertas ao mesmo tempo.

## 3. Marcos e como checar

Rode `git fetch origin` antes. Cada ciclo versiona a própria
rastreabilidade no merge ([README §5](./README.md), regra 4). Por isso,
"ciclo NNN em `main`" = o arquivo `specs/NNN-*/traceability.md` existe em
`origin/main`.

| Marco | Significa | Quem entrega | Como checar |
|---|---|---|---|
| **S0** | 000 em `main` e tag publicada | A | `git ls-remote --tags origin contratos-v1` devolve uma linha |
| **S1** | Tabelas v1 publicadas em `bussola_dados` | A (001) | `bq ls --project_id=batalha-time-07-lkbv bussola_dados` lista as 6 tabelas P0 de [contratos §3](./contratos.md), e `perfil_mensal` tem linhas do âncora |
| **S2** | 001 em `main` | A | `git cat-file -e origin/main:specs/001-camada-dados-financeiros/traceability.md` |
| **S3** | 003 em `main` | A | `git cat-file -e origin/main:specs/003-mcp-dados-conhecimento/traceability.md` |
| **S4** | 004 em `main` | **B** | `git cat-file -e origin/main:specs/004-agente-bussola-jornada/traceability.md` |
| **S6** | 005 em `main` | **B** | `git cat-file -e origin/main:specs/005-consentimento-governanca/traceability.md` |

Se o `bq` falhar por credencial ou permissão, pergunte à Pessoa A se o S1
saiu. Não suponha.

## 4. O que muda em cada ciclo na trilha A

### 4.1 000 — Fundação e contratos (A lidera)

- **Modo:** sem dependências. É o único ciclo que cria a constituição e
  roda `specify init --here`.
- **Com a Pessoa B, antes do PR:**
  - B roda o Bloco 0 em paralelo: envia os pedidos ao owner, valida cedo os
    IDs de modelo e o `allUsers`, e fecha a Q4 com o time.
  - O `pedidos-owner.md` deste ciclo é o texto que **B envia**. Registre no
    PR o status e a decisão Plano A/B.
  - Se B já validou os IDs do Gemini Flash e do embedding, use como ponto de
    partida e confirme com `deploy/smoke_modelos.py`.
- **Q4 antes do merge:** se o time escolher front próprio, este PR inclui no
  mapa de [contratos §1](./contratos.md):
  - `web/` com dono 007;
  - o ponto de entrada que serve o build pelo `bussola-agent`, como
    acréscimo em `agent/` com dono 007.
- **Gate:** critérios do arquivo do ciclo + revisão de B (os 2 integrantes
  revisam, porque congela os contratos). Depois do merge, crie a tag
  `contratos-v1`.
- **Aviso S0 para B:** "000 em `main` e `contratos-v1` publicada. Pode abrir
  as worktrees do 004 e do 007."

### 4.2 001 — Dados financeiros

- **Modo:** fixtures provisórias do 000.
- **S1 no meio do ciclo:** publique as tabelas v1 em `bussola_dados` assim
  que `build_dados.py` rodar para o âncora e o controle. Isso libera o
  corpus real do 002 na sua própria sessão A1.
- **Fixtures golden:** a troca das provisórias do 000 é PR `contracts:`,
  com aprovação de A e B.
- **Team Mode:** desligado por padrão, porque a sessão A2 já roda o 003 em
  paralelo.
- **Aviso S2 para B:** "001 em `main`. Números reais do âncora no
  BigQuery e fixtures golden atualizadas; o eval de números do 004 passa a
  usar esses valores."

### 4.3 003 — MCP de dados e conhecimento

- **Modo:** `BUSSOLA_FAKES=TRUE` até o S2.
- **Troca fake → real:** depois do S2, no mesmo PR, se ainda estiver
  aberto; senão, num PR de integração imediato.
- **Gate:** o `make test-bq` contra as tabelas do 001 exige o S2. Essas
  tarefas ficam `[aguarda S2]`.
- **Cloud Run:** só `--tag c003 --no-traffic`. Quem move tráfego é B, no
  007.
- **Aviso S3 para B:** "003 em `main`. Valide o 004 contra o MCP real
  (`make mcp` sem fakes) e mergeie. Com o 004 em `main`, o 007 já pode
  publicar os dois serviços reais (S5)."

### 4.4 002 — RAG financeiro

- **Modo:** templates e buscador sobre `contracts/fixtures/bussola_dados/`
  até o S1. O corpus real só é gerado depois do S1.
- **Runtime:** o MCP gera o embedding da pergunta. Isso exige
  `aiplatform.user` na SA (pedido ao owner, enviado por B) ou o Plano B com
  chave.
- **Buscador plugado:** a fábrica do `server.py` (003) já procura
  `rag.criar_buscador` e cai no fake com aviso. O 002 entrega o módulo e
  prova o plug com o MCP rodando, o que exige o S3. Essas tarefas ficam
  `[aguarda S3]`.
- **Aviso para B, no merge:** "002 em `main`. A nova imagem do MCP está
  pronta para deploy pelo runbook (`docs/operacao.md`)."

### 4.5 006 — Acompanhamento com replay

- **Modo:** MCP mock (`resumo_mes__<AAAAMM>.json`) e `RegistroEmMemoria`.
- **Entrada no agente:** só por `extensoes.registrar_ferramenta` e
  `registrar_instrucao` (ordens 70–89). O teste no agente real exige o S4.
- **`ajustar_plano`:** usa o gate real do 005 e exige o S6. Essas tarefas
  ficam `[aguarda S6]`.
- **Gate:** roteiro 202506 → 202508 contra o MCP real (S3), com o gate do
  005 ativo (S6), e eval executado. Na prática, o 006 é o último PR da
  trilha.
- **Contrato com o front de B (se a Q4 for front próprio):** o botão
  "Avançar um mês ▸" envia a mensagem `avançar um mês`. A instrução
  registrada pelo 006 precisa levar essa frase a `avancar_mes()`.
- **Linha de corte:** se o prazo apertar, fica só `avancar_mes` + desvio +
  rota, sem `ajustar_plano`. Registre em `specs/006-*/corte.md` e avise B,
  que ajusta o roteiro da demo.
- **Aviso para B, no merge:** "006 em `main`. S7 completo do lado A;
  integração final liberada."

## 5. Como disparar

```bash
git switch main && git pull
git worktree add ../bussola-NNN -b NNN-slug
cd ../bussola-NNN
SPECIFY_FEATURE_DIRECTORY=specs/NNN-slug claude
```

No Claude Code, dentro da worktree:

```text
/spec-master docs/ciclos/pessoa-a-dados-ferramentas.md
```

- **Só no 000:** antes de abrir o Claude, rode
  `specify init --here --integration claude --script sh` e confira
  `specify extension list` (se `git` estiver habilitada:
  `specify extension disable git`).
- **No app desktop:** abra uma sessão nova apontando para `../bussola-NNN`.
  Sem a variável de ambiente, o número da spec vem da §2.
- **Respostas nos gates do Spec Master:** as do [README §6](./README.md).
- **Limpeza após o merge:** `git worktree remove ../bussola-NNN` e
  `git branch -d NNN-slug`.

## 6. Integração final (Onda 3, liderada por B)

A Pessoa A:

- fecha o 006;
- confirma o buscador do 002 no MCP publicado depois do deploy de B;
- entrega os resultados dos evals do 002 e do 006 para
  `eval/RESULTADOS.md`;
- participa do ensaio do roteiro e do vídeo de backup
  ([README §8](./README.md)).

## 7. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| Divisão A/B por serviço e diretório | [Roadmap de 2 pessoas](./roadmap-2-pessoas.md) §1 | EXPLICIT |
| Um contexto de Spec Master por pessoa | Pedido do time | EXPLICIT |
| Um run = um ciclo = uma feature | [README §5](./README.md), regra 1 | EXPLICIT |
| Ciclo alvo resolvido pela branch da worktree | Esta trilha | INFERRED |
| Marco de merge = `traceability.md` em `origin/main` | [README §5](./README.md), regra 4 | INFERRED |
| Tarefas `[aguarda Sx]` e retomada pelo Step 0 | Esta trilha + protocolo do Spec Master | INFERRED |
| Frase `avançar um mês` como contrato front ↔ 006 | [Roadmap](./roadmap-2-pessoas.md) §5, item 5 | INFERRED |
| Data-limite | Mestre §20, Q1 | UNRESOLVED |
| Canal da demo | Mestre §20, Q4 | UNRESOLVED |
