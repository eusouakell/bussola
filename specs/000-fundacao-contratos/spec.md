# Feature Specification: Fundação e contratos

**Feature Branch**: `000-fundacao-contratos`

**Created**: 2026-09-26

**Status**: Draft

**Input**: `docs/ciclos/000-fundacao-contratos.md` (via `/spec-master
docs/ciclos/pessoa-a-dados-ferramentas.md`). Fonte canônica de formatos:
`docs/ciclos/contratos.md` (contratos v1).

> **Nota sobre o nível de detalhe.** Esta feature **é** a materialização de um
> contrato técnico entre equipes. Os "usuários" são os integrantes que executam
> os ciclos 001–007 em paralelo. Por isso a spec cita nomes de artefatos e
> formatos do contrato; decisões de *como* implementar ficam no `plan.md`.

## Clarifications

### Session 2026-09-26

Resolvidas automaticamente (Spec Master, fase clarify). Classificação entre
parênteses.

- Q: O que o mock devolve para o usuário-controle, que existe em
  `usuarios.json` mas não tem golden? → A: `DADOS_INSUFICIENTES` ("o mock só
  tem respostas do cliente âncora"); nunca o golden de outro cliente
  (constituição III). Registrado em `questoes.md`. (SAFE_DEFAULT)
- Q: Ordem de validação no mock? → A: formato e faixas de todos os parâmetros
  (`ENTRADA_INVALIDA`) → existência do usuário (`USUARIO_INEXISTENTE`) →
  disponibilidade de dados (`DADOS_INSUFICIENTES`). (SAFE_DEFAULT)
- Q: Restrições de faixa vão no schema da ferramenta ou na validação interna?
  → A: assinatura com tipos simples e padrões de §5; faixas validadas dentro
  da ferramenta, que devolve envelope de erro (contratos §5: erro é resultado,
  não exceção). (RESOLVABLE_FROM_CONTEXT)
- Q: Quando o mock acrescenta o aviso de mock? → A: nas ferramentas P0 com
  `ate_anomes < 202512` (inclusive 202506, TS-02); com `202512` e em
  `resumo_mes` devolve o arquivo sem alteração (contratos §8).
  (RESOLVABLE_FROM_CONTEXT)
- Q: Regex do `id_usuario`? → A: UUID v4 (versão 4, variante 8/9/a/b), sem
  diferenciar maiúsculas; normalizado para minúsculas antes do uso.
  (SAFE_DEFAULT)
- Q: Qual cliente MCP cumpre AC-05? → A: o servidor usa o FastMCP do SDK
  oficial (`mcp`, mestre §13); os testes usam o cliente do mesmo SDK
  (`ClientSession`), equivalente funcional ao `fastmcp.Client` citado, sem
  dependência extra. Registrado em `questoes.md`. (RESOLVABLE_FROM_CONTEXT)
- Q: Como os testes rodam antes de existirem fixtures reais? → A: fakes e
  mock recebem o diretório de fixtures por parâmetro (padrão
  `contracts/fixtures/`); a lógica é testada com um conjunto sintético de
  teste criado pelo próprio teste; o teste das fixtures oficiais (AC-04) só é
  pulado, com motivo explícito, enquanto `make fixtures` não tiver rodado.
  (SAFE_DEFAULT)
- Q: Porta local do agente? → A: `make mcp` usa 8080 (contratos §2) e
  `make agent` usa 8000, para os dois rodarem juntos com
  `MCP_URL=http://localhost:8080/mcp`. (SAFE_DEFAULT)
- Q: `resumo_mes` com `anomes` fora de 202501–202512 ou maior que
  `ate_anomes`? → A: `ENTRADA_INVALIDA`. (RESOLVABLE_FROM_CONTEXT)
- Q: Q4 (canal da demo) bloqueia o 000? → A: não; é decisão da Pessoa B antes
  do merge e só pode acrescentar `web/` ao mapa §1. (UNRESOLVED, externa)
- Q: O RAG continua sobre `bussola_rag` com dados do cliente? → A: não
  (Q-17, decisão do usuário). O RAG é conhecimento geral (normas do BACEN,
  crédito, boas práticas) num corpus curado no repositório, com busca em
  memória. `bussola_rag` sai do DDL; o buscador não recebe `id_usuario` nem
  `ate_anomes`; `buscar_contexto_financeiro` não tem golden. Mudança
  incompatível em `Trecho` (sai `origem`, `tipo`, `anomes`), feita antes da
  tag `contratos-v1`, sem consumidor afetado. (EXPLICIT)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Desenvolver um ciclo isolado sobre contratos e fakes (Priority: P1)

Um integrante abre a worktree de qualquer ciclo (001–007) a partir de `main` e
desenvolve contra interfaces estáveis, dados de exemplo e dublês, sem esperar
nenhum outro ciclo e sem acesso à nuvem.

**Why this priority**: é o propósito do ciclo (000 §2). Sem isso não há
paralelismo.

**Independent Test**: num clone limpo, sem rede, com `BUSSOLA_FAKES=TRUE`,
`make lint` e `make test` passam nos dois projetos; os dublês respondem a partir
das fixtures.

**Acceptance Scenarios**:

1. **Given** um clone limpo sem credenciais de nuvem, **When** o integrante roda
   `make lint` e `make test` com `BUSSOLA_FAKES=TRUE`, **Then** ambos terminam
   com sucesso e nenhum teste acessa a rede (AC-02).
2. **Given** as definições de tabela do contrato, **When** o teste de contrato
   roda, **Then** cada tabela tem um modelo de dados com os mesmos nomes e tipos
   de coluna (AC-03, TS-01).
3. **Given** o repositório fake, **When** se pede o perfil mensal do usuário
   controle até 202503, **Then** voltam exatamente 3 meses do controle e nenhum
   do âncora (TS-05).

---

### User Story 2 - Consumir o servidor de ferramentas mock (Priority: P1)

O integrante do agente (004) ou do canal (007) sobe localmente um servidor de
ferramentas que expõe as 8 ferramentas do contrato com as assinaturas exatas e
respostas determinísticas, para construir a jornada antes das ferramentas reais.

**Why this priority**: destrava 004 e 007 na Onda 1 (roadmap S0).

**Independent Test**: `make mcp` sobe o servidor; um cliente de protocolo lista
as 8 ferramentas e chama algumas com entradas válidas e inválidas.

**Acceptance Scenarios**:

1. **Given** o mock no ar, **When** um cliente lista as ferramentas, **Then**
   recebe `perfil_financeiro`, `capacidade_poupanca`, `oportunidades_corte`,
   `dividas_e_parcelas`, `simular_objetivo`, `comparar_cenarios`,
   `buscar_contexto_financeiro` e `resumo_mes`, com os parâmetros de
   contratos §5 (AC-05).
2. **Given** o mock, **When** `perfil_financeiro(âncora, 202506)` é chamado,
   **Then** volta o golden `__ate_202506` com um aviso de mock; **When**
   `ate_anomes=202512`, **Then** volta o golden `__ate_202512` (TS-02).
3. **Given** o mock, **When** a chamada usa um UUID bem formado fora de
   `usuarios.json`, **Then** volta o erro `USUARIO_INEXISTENTE`; **When** usa
   um UUID malformado, **Then** volta `ENTRADA_INVALIDA` (AC-05).
4. **Given** o mock, **When** `simular_objetivo` recebe `prazo_meses` e
   `aporte_mensal` juntos, ou qualquer ferramenta recebe `ate_anomes=202601`,
   **Then** volta `ENTRADA_INVALIDA` (TS-03).

---

### User Story 3 - Estender o agente sem editar o arquivo de outro ciclo (Priority: P1)

Os ciclos 004, 005 e 006 acrescentam callbacks, ferramentas, instruções e
persistência ao agente por registro, sem editar o arquivo principal do agente,
que pertence ao 004.

**Why this priority**: evita conflitos entre três ciclos que mexem no mesmo
serviço (contratos §6).

**Independent Test**: testes unitários do encadeador de callbacks, do registro
de extensões e do registro de aplicação em memória, sem LLM.

**Acceptance Scenarios**:

1. **Given** duas funções registradas na mesma fase com ordens 10 e 20, **When**
   a de ordem 10 retorna um valor, **Then** a de ordem 20 não roda e o valor da
   10 é o resultado (TS-04, AC-08); vale para as 4 fases.
2. **Given** que os pacotes `governanca` e `acompanhamento` ainda não existem,
   **When** as extensões são carregadas, **Then** não há erro (AC-09).
3. **Given** o registro de aplicação em memória, **When** planos, consentimentos,
   eventos e acompanhamentos são registrados, **Then** ele cumpre a interface
   `RegistroApp` e devolve o plano gravado (AC-10).
4. **Given** o mock local no ar, **When** o conjunto de ferramentas do agente
   conecta nele (sem LLM), **Then** lista as ferramentas (AC-06).

---

### User Story 4 - Dados de exemplo fiéis à base sintética (Priority: P2)

A equipe gera, a partir da base sintética, fixtures do usuário-âncora e do
usuário-controle (12 meses) e respostas-padrão (golden) provisórias das
ferramentas, com valores de referência verificáveis.

**Why this priority**: os fakes da US1/US2 precisam de dados; mas as fixtures
dependem de credenciais de nuvem e podem ser regeneradas depois.

**Independent Test**: `make fixtures` com credenciais gera `contracts/fixtures/`;
um teste compara as médias do âncora com os valores de referência de
contratos §8 (tolerância de 1%).

**Acceptance Scenarios**:

1. **Given** credenciais de leitura na base sintética, **When** `make fixtures`
   roda, **Then** são gerados `usuarios.json`, as tabelas de `bussola_dados` para
   os 2 usuários, os golden P0 `__ate_202506`/`__ate_202512`, os 12
   `resumo_mes__AAAAMM`, preservando o corpus curado de RAG (AC-04).
2. **Given** as fixtures geradas, **When** o teste de referência roda, **Then**
   renda, gasto, sobra, aluguel, comer fora, assinaturas, juros, saldo mínimo e
   saldo máximo do âncora ficam a até 1% dos valores de contratos §8 (AC-04).

---

### User Story 5 - Plataforma de nuvem validada (Priority: P2)

A equipe confirma que a plataforma aceita o caminho de produção: datasets
criados de forma idempotente, modelos respondendo, imagens publicadas e os dois
serviços hello rodando, com o serviço de ferramentas privado.

**Why this priority**: remove incertezas de plataforma cedo (mestre §15, Bloco
0), mas não bloqueia o desenvolvimento local.

**Independent Test**: execução dos scripts de plataforma com credenciais do
integrante; registro em `modelos.md` e `smoke.md`.

**Acceptance Scenarios**:

1. **Given** credenciais do integrante, **When** o script de DDL roda duas vezes,
   **Then** os 4 datasets e suas tabelas existem e a segunda execução não altera
   nada (AC-11).
2. **Given** credenciais, **When** o smoke de modelos roda, **Then** o primeiro
   Gemini Flash que responder (3.8 → 3.7 → 3.5) e o modelo de embedding ficam
   registrados em `contracts/env.example` e em `modelos.md`, com latência e
   dimensão (AC-12).
3. **Given** as imagens publicadas, **When** os serviços são implantados, **Then**
   o serviço de ferramentas é privado e aceita chamada com ID token de um
   integrante, e o agente hello é publicado (AC-13).
4. **Given** o agente hello local apontando para o mock, **When** alguém pergunta
   "qual é o meu perfil financeiro?", **Then** o agente chama
   `perfil_financeiro`, e o resultado fica registrado em `smoke.md` (AC-07).

---

### User Story 6 - Governança e pedidos de desbloqueio (Priority: P2)

O time tem constituição, convenções de repositório e o texto dos pedidos ao owner
pronto para envio, com os caminhos Plano A e Plano B preparados.

**Why this priority**: congela as regras antes do paralelismo; os pedidos têm
lead time externo.

**Independent Test**: leitura dos artefatos (`constitution.md`, `CLAUDE.md`,
`pedidos-owner.md`) e do script de IAM do Plano B em modo de simulação.

**Acceptance Scenarios**:

1. **Given** o repositório, **When** um integrante abre a constituição e o
   `CLAUDE.md`, **Then** encontra os princípios de 000 §3.1, os comandos `make`,
   o modo fake, onde ficam os contratos, a tabela de propriedade, a proibição de
   SQL concatenado e de logar prompts/segredos, e o fluxo de PR (AC-01).
2. **Given** `pedidos-owner.md`, **When** a Pessoa B o envia, **Then** os 4 itens
   de mestre §16 estão presentes e o status e a decisão Plano A/B são registrados
   (AC-14).
3. **Given** o script de IAM do Plano B, **When** é executado sem confirmação
   explícita, **Then** não aplica nenhuma mudança.

---

### Edge Cases

- `ate_anomes` fora de 202501–202512 → `ENTRADA_INVALIDA`.
- `anomes` de `resumo_mes` maior que `ate_anomes` → `ENTRADA_INVALIDA`.
- `top_n`/`k` fora de 1–10, `pergunta` com mais de 500 caracteres, `valor_alvo ≤
  0`, `prazo_meses` fora de 1–360 → `ENTRADA_INVALIDA`.
- `simular_objetivo` sem `prazo_meses` nem `aporte_mensal` → `ENTRADA_INVALIDA`.
- Usuário-controle nas ferramentas do mock: o mock só tem golden do âncora
  (contratos §8). Ver Q-01 em `questoes.md`.
- Fixtures ausentes (antes de `make fixtures`): testes que dependem delas não
  podem ficar verdes → ver Assumptions.
- Pacotes de extensão ausentes → carregamento silencioso.
- Nenhum Gemini Flash responde via Vertex → testar via Gemini API com chave lida
  do Secret Manager, nunca impressa.

## Requirements *(mandatory)*

### Functional Requirements

**Governança (000 §3.1)**

- **FR-001**: O repositório MUST ter o Spec Kit inicializado com a integração
  Claude e a constituição com os princípios de mestre §7, §11, §12 e README §5.
- **FR-002**: O repositório MUST ter `CLAUDE.md` com: comandos `make`, modo
  `BUSSOLA_FAKES`, local dos contratos, link para a tabela de propriedade
  (contratos §1), proibição de SQL concatenado e de logar prompts/segredos, e
  fluxo de PR.
- **FR-003**: O `.gitignore` existente MUST ser preservado, com acréscimos do
  que faltar.
- **FR-004**: O `Makefile` MUST expor `test`, `lint`, `mcp`, `agent`,
  `fixtures` e `test-bq` (contratos §2).

**Projetos (000 §3.2)**

- **FR-005**: MUST existir dois projetos independentes, `mcp_server/` e
  `agent/`, com as dependências listadas em 000 §3.2 e imagens de contêiner
  `linux/amd64` escutando em `PORT` (padrão 8080); a imagem do agente serve a
  interface web do ADK.

**Contratos em código (000 §3.3; contratos §3–§7, §9)**

- **FR-006**: MUST existir DDL dos datasets `bussola_dados` e `bussola_app`
  idêntico a contratos §3; `bussola_app_dev` reutiliza o DDL de `bussola_app`.
  Não há dataset de RAG (Q-17).
- **FR-007**: MUST existir `contracts/env.example` com todas as variáveis de
  contratos §7 e nenhum valor secreto.
- **FR-008**: MUST existir modelos de dados para cada linha de tabela de §3, para
  a entrada e o `dados` de cada ferramenta de §5, para os envelopes de sucesso
  (`dados`, `fonte{ferramenta, tabelas, periodo{inicio, fim}}`, `avisos`) e erro
  (`erro{codigo, mensagem}`), e o enum dos 5 códigos de erro.
- **FR-009**: MUST existir as interfaces `RepositorioFinanceiro` e
  `BuscadorContexto` com as assinaturas de contratos §4, e implementações fake
  sobre `contracts/fixtures/`.
- **FR-010**: Os fakes MUST respeitar escopo e tempo: só linhas do `id_usuario`
  pedido e com `anomes ≤ ate_anomes` (e `≥ desde_anomes`, quando informado); o
  buscador fake não recebe cliente nem corte (corpus geral, Q-17) e devolve até
  `k` trechos com `score > 0`, ordenados por score e `trecho_id`, com filtro
  opcional por `tema`.
- **FR-011**: Cada serviço MUST ter um logger JSON em stdout com `severity`,
  `message` e os campos de contratos §9, sem prompt, texto de lançamentos,
  chaves ou tokens.
- **FR-012**: O agente MUST ter: chaves e enum de `session.state` com helpers de
  leitura/escrita (§6); encadeador `registrar(fase, funcao, ordem)` com 4
  callbacks agregados; registro de extensões (`registrar_ferramenta`,
  `registrar_instrucao`, `ferramentas`, `instrucoes`, `carregar_extensoes`);
  interface `RegistroApp`, os 4 modelos e `RegistroEmMemoria`; e a conexão MCP
  (streamable HTTP, OIDC opcional, `chamar_ferramenta` que força `id_usuario` e
  `ate_anomes` do `state`).
- **FR-013**: O encadeador MUST executar em ordem crescente e interromper no
  primeiro retorno não nulo, nas fases `before_model`, `after_model`,
  `before_tool` e `after_tool`.
- **FR-014**: `carregar_extensoes()` MUST importar `bussola_agent.governanca` e
  `bussola_agent.acompanhamento` quando existirem e ignorar `ImportError`;
  `instrucoes()` concatena por ordem crescente.

**Fixtures e mock (000 §3.4; contratos §8)**

- **FR-015**: `data/scripts/gerar_fixtures.py` MUST gerar `contracts/fixtures/`
  a partir de SQL de referência parametrizado, somente leitura em
  `hackathon_dados.extrato_sintetico`, para âncora e controle, 12 meses, com
  golden P0 (`__ate_202506`, `__ate_202512`) e `resumo_mes__AAAAMM`
  (202501–202512) calculados por uma implementação de referência simples,
  marcados como provisórios.
- **FR-016**: `contracts/fixtures/rag/trechos_exemplo.json` MUST conter um
  corpus curado de `TrechoCorpus` (texto original em pt-BR), cobrindo os três
  temas (`norma_bacen`, `credito`, `boas_praticas`), todos com `fonte`;
  `make fixtures` MUST preservá-lo (Q-17).
- **FR-017**: O mock MUST servir, em streamable HTTP no caminho `/mcp` em
  `0.0.0.0:$PORT`, as 7 ferramentas P0 e `resumo_mes` com as assinaturas de
  §5, respondendo pela regra de §8 (`< 202512` → golden `__ate_202506` + aviso
  de mock; `= 202512` → golden `__ate_202512`); `buscar_contexto_financeiro`
  responde pelo buscador fake sobre o corpus curado, para qualquer cliente
  conhecido (Q-17).
- **FR-018**: O mock MUST validar as entradas (UUID por regex, faixas de §5) e
  devolver `ENTRADA_INVALIDA` para entrada inválida e `USUARIO_INEXISTENTE` para
  UUID fora de `usuarios.json`, como envelope de erro (não exceção).
- **FR-019**: O agente hello MUST montar `root_agent` com o conjunto de
  ferramentas MCP, instrução mínima em pt-BR, os 4 callbacks agregados (cadeias
  vazias) e chamar `carregar_extensoes()`.

**Plataforma (000 §3.5)**

- **FR-020**: `data/scripts/aplicar_ddl.py` MUST criar de forma idempotente os
  datasets `bussola_dados`, `bussola_app` e `bussola_app_dev` e suas tabelas em
  `us-central1`.
- **FR-021**: `deploy/smoke_modelos.py` MUST testar Gemini Flash na ordem 3.8 →
  3.7 → 3.5 e o modelo de embedding via Vertex, gravar os IDs validados em
  `contracts/env.example` e o relatório (modelos testados, latência, dimensão do
  embedding) em `specs/000-fundacao-contratos/modelos.md`, sem imprimir segredos.
- **FR-022**: `deploy/build_push.sh <servico>` MUST construir a imagem
  `linux/amd64` com tag = SHA curto e publicá-la em
  `us-central1-docker.pkg.dev/batalha-time-07-lkbv/agentes/<servico>`;
  `deploy/deploy.sh <servico> [--tag cNNN --no-traffic]` MUST implantar no Cloud
  Run, com `bussola-mcp` privado (`--no-allow-unauthenticated`).
- **FR-023**: `deploy/iam_datasets.sh` MUST aplicar o Plano B (dataViewer em
  `bussola_dados`, dataEditor em `bussola_app`/`bussola_app_dev`
  para a SA default) somente após confirmação humana explícita.
- **FR-024**: `specs/000-fundacao-contratos/pedidos-owner.md` MUST conter os 4
  itens de mestre §16 prontos para envio pela Pessoa B, com campos de status e
  decisão Plano A/B.
- **FR-025**: Divergências entre esta spec, a trilha e os contratos MUST ser
  registradas em `specs/000-fundacao-contratos/questoes.md`, corrigindo o
  contrato no mesmo PR.

### Key Entities

- **Usuário sintético**: âncora (`36a21505-…`) e controle (`31e94f2f-…`),
  identificados por UUID v4.
- **Linhas de `bussola_dados`**: `PerfilMes`, `GastoCategoria`,
  `EntradaCategoria`, `Recorrente`, `Parcela`, `Categoria`, `RefCoorte`.
- **Trecho de RAG** (`TrechoCorpus`/`Trecho`): `doc_id`, `trecho_id`,
  `titulo`, `tema`, `texto`, `fonte{nome, referencia, url}` e, na busca,
  `score`.
- **Registros de aplicação**: `Plano`, `Consentimento`, `EventoAuditoria`,
  `Acompanhamento`.
- **Envelope de ferramenta**: sucesso (`dados`, `fonte`, `avisos`) ou erro
  (`codigo`, `mensagem`).
- **Estado de sessão**: `id_usuario`, `ate_anomes`, `estado_jornada` e demais
  chaves de contratos §6.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos artefatos marcados como 000 em contratos §1 existem no
  PR (AC-03).
- **SC-002**: A verificação local completa (lint + testes) passa num clone limpo,
  sem rede, em uma única execução (AC-02).
- **SC-003**: 8 de 8 ferramentas do mock são listadas com os parâmetros do
  contrato e 100% dos cenários de erro de TS-03/AC-05 retornam o código
  esperado.
- **SC-004**: Os 9 valores de referência do âncora ficam dentro de 1%
  (AC-04).
- **SC-005**: Uma segunda execução do script de DDL produz 0 alterações
  (AC-11).
- **SC-006**: Os ciclos 001, 003, 004 e 007 conseguem iniciar a partir de `main`
  sem pedir mudança de contrato na primeira semana (INFERRED, 000 §2).

## Assumptions

- Os golden e as fixtures são **provisórios** e serão substituídos pelo 001 via
  PR `contracts:` (contratos §8). EXPLICIT.
- A geração de fixtures e as tarefas de plataforma dependem de credenciais GCP do
  integrante; enquanto elas não existirem, essas tarefas ficam pendentes e não se
  inventam dados de fixture. DISCOVERED_FROM_CODEBASE.
- `RegrasCenario` usa a proposta de contratos §4 até a decisão da Q2. EXPLICIT.
- A ordem 3.8 → 3.7 → 3.5 para Flash vem do inventário do Model Garden (mestre
  §5). INFERRED.
- A tag `contratos-v1` é criada somente após o merge, por um integrante (AC-15). EXPLICIT.
- A Q4 (canal da demo) pode acrescentar `web/` (dono 007) ao mapa de contratos
  §1 neste PR; decisão da Pessoa B antes do merge. UNRESOLVED.
