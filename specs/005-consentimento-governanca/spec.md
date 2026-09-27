# Feature Specification: Consentimento, governança e auditoria

**Feature Branch**: `005-consentimento-governanca`

**Created**: 2026-09-26

**Status**: Implementada (aguarda o merge do 004 para o gate de merge)

**Input**: `docs/ciclos/005-consentimento-governanca.md`. Fonte canônica de
formatos: `docs/ciclos/contratos.md` (§3, §6, §7, §9). Contrato do front:
`specs/008-front-web/contracts/eventos-agente.md`.

## Clarifications

### Session 2026-09-26

Decisões do usuário (prevalecem sobre o documento do ciclo):

- **D1. Sem prompt injection ao vivo.** Os guardrails são validados só de forma
  determinística:
  - regras puras testadas com strings estáticas;
  - callbacks testados com `LlmRequest`/`LlmResponse` montados no teste;
  - os casos do eval rodam contra um LLM falso roteirizado;
  - o cliente do Model Armor é mockado.

  Nenhum payload adversarial é enviado ao Gemini ou ao Model Armor reais. Isso
  substitui o "`rodar_eval.py` roda com o Gemini real" do ciclo §3.6 e cumpre
  "testes de prompt injection" (§6) com os casos estáticos.
- **D2. Portas e adaptadores.** Model Armor, BigQuery e relógio são portas.
  Testes unitários e de integração rodam offline em `make test`. A integração
  usa o `InMemoryRunner` do ADK com um `BaseLlm` falso roteirizado.
- **D3. Nomes.** Caminhos e nomes de contrato ficam como estão
  (`governanca/catalogo.py`, `acoes.py`, `guardrails.py`,
  `persistencia_bq.py`, `RegistroBigQuery`, ferramentas, tabelas e colunas).
  Módulos, classes e funções internas novas usam inglês técnico, permitido
  pela constituição VIII. Textos ao cliente e documentação ficam em pt-BR.
- **D4. Deploy por Helm.** Este ciclo não cria scripts de deploy. As variáveis
  novas são listadas no relatório para o chart do 007.

Resolvidas automaticamente (classificação entre parênteses):

- Q: Quando gravar a linha de `consentimentos`, se `decisao` é `NOT NULL` e só
  aceita `aceito`/`recusado`? → A: na decisão. A solicitação grava só o evento
  `consentimento_solicitado`. O `texto_apresentado` é o texto padronizado
  gerado de forma determinística. (RESOLVABLE_FROM_CONTEXT)
- Q: O que acontece com a entrada do state depois do uso? → A: continua
  `status: "aceito"` e ganha `usado: true`. O front mantém o cartão
  "Autorizado" e o passo do plano como feito, e o gate exige `aceito` sem
  `usado`. Campos opcionais (`resumo`, `invocation_id`, `usado`) são
  acréscimos documentados em contratos §6. (SAFE_DEFAULT)
- Q: Quando o consentimento é consumido? → A: no gate, antes da execução.
  Chamadas duplicadas em paralelo são bloqueadas, e uma tentativa que falha
  (ex.: `PRODUTO_FORA_DO_CATALOGO`) também consome. É a leitura mais estrita
  de "uso único". (SAFE_DEFAULT)
- Q: Vários pedidos pendentes ao mesmo tempo? → A: no máximo um. Um novo
  `solicitar_consentimento` remove os outros pendentes, e o front mostra
  "Pedido encerrado". (SAFE_DEFAULT)
- Q: Vocabulário do analisador? → A: o mesmo do front simulado
  (`web/src/simulado`), sem acentos. Negação vence aceite, "sim, mas…" e
  "talvez" são ambíguos, e uma mensagem sem sim/não mantém o pedido pendente.
  Desvio do front: "?", "mas" e "depois" só contam como dúvida junto de um
  sim ou não, para que uma pergunta curta sem relação vá ao modelo (que pede
  a resposta de novo) em vez de virar "Só para confirmar". (INFERRED, ciclo
  §10)
- Q: Model Armor sem template? → A: o template não existe (mestre §16, item
  2). O adaptador fica atrás de uma porta, testado com cliente mockado. Sem
  `MODEL_ARMOR_TEMPLATE`, só as regras determinísticas atuam. Com template, as
  regras continuam ligadas (só elas conhecem o UUID da sessão) e uma falha do
  Model Armor cai para as regras. (UNRESOLVED → fallback é a entrega)
- Q: Como o 005 entra no agente sem editar o `agent.py`? → A:
  `governanca/__init__.py` registra ferramentas, instruções (50–69) e
  callbacks nas ordens reservadas. O import não abre rede, e o registro da
  aplicação é criado sob demanda. (RESOLVABLE_FROM_CONTEXT)
- Q: Testes de contrato do 000 que exigem a ausência de `governanca`? → A:
  ganham a fixture `sem_extensoes`, e `criar_extensao` passa a ter prioridade
  sobre o pacote real. Mudança aditiva num commit `contracts:` separado.
  (SAFE_DEFAULT)
- Q: Onde fica o catálogo de produtos na imagem, se o Dockerfile do agente não
  copia `contracts/`? → A: uma cópia em `governanca/catalogo_produtos.json`,
  com teste de igualdade com `contracts/catalogo_produtos.json`.
  (RESOLVABLE_FROM_CONTEXT)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ação sensível só com "sim" explícito (Priority: P1)

O cliente escolhe um cenário. O agente pede autorização e só cria o plano
depois do "sim".

**Acceptance Scenarios**:

1. **Given** um cenário escolhido, **When** o modelo chama `criar_plano` sem
   pedir, **Then** o gate devolve `CONSENTIMENTO_NECESSARIO` e nada é gravado.
2. **Given** um pedido pendente, **When** o cliente responde "sim", **Then** o
   consentimento fica `aceito`, é gravado em `consentimentos` e `auditoria`,
   e `criar_plano` grava o plano e preenche `plano_id`.
3. **Given** um consentimento já usado, **When** o modelo chama `criar_plano`
   de novo, **Then** o gate exige um novo consentimento.
4. **Given** um pedido pendente, **When** o cliente responde "não, agora
   não", **Then** fica `recusado`, nada é executado e a recusa é gravada.
5. **Given** um pedido pendente, **When** o cliente responde "sim, mas…",
   **Then** o pedido continua pendente e o agente pede nova confirmação.

### User Story 2 - Guardrails de entrada e saída (Priority: P1)

**Acceptance Scenarios**:

1. **Given** uma mensagem com o UUID de outro cliente, "ignore as
   instruções", pedido de SQL/prompt/infra, promessa de crédito ou envio de
   dados a terceiros, **Then** o modelo não é chamado, o cliente recebe uma
   recusa educada em pt-BR com `customMetadata.bussola.guardrail` e o evento
   `guardrail_bloqueio` é gravado com o motivo.
2. **Given** uma resposta do modelo com `SELECT … FROM`, outro UUID, nome do
   projeto, credencial ou promessa de aprovação, **Then** a resposta é
   substituída por uma recusa e o bloqueio é gravado.

### User Story 3 - Auditoria mínima e persistência (Priority: P1)

**Acceptance Scenarios**:

1. Toda chamada de ferramenta gera `ferramenta_chamada` com chaves dos
   argumentos, valores numéricos, status e `erro_codigo`, sem texto livre.
2. Mudança de `estado_jornada` gera `estado_alterado`. O primeiro turno gera
   `sessao_iniciada`.
3. Com `BUSSOLA_FAKES=FALSE`, `RegistroBigQuery` grava via `insert_rows_json`
   em `BQ_DATASET_APP`. Os testes `bq` gravam só em `bussola_app_dev`.

### Edge Cases

- `compartilhar_dados` é sempre recusada (ferramenta e pedido de
  consentimento), com `guardrail_bloqueio`.
- `simular_contratacao` com produto fora do catálogo ou com
  `acao_simulada=false` → `PRODUTO_FORA_DO_CATALOGO`, sem `acao_executada`.
- Ferramenta desconhecida → sensível.
- `criar_plano` sem objetivo ou cenários no state → `ENTRADA_INVALIDA`.
- Falha do BigQuery ou do Model Armor não derruba o turno: log com
  `erro_codigo` e fallback.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** Catálogo: livres (ferramentas MCP, `registrar_objetivo`,
  `escolher_cenario`, `avancar_mes`, `status_plano`,
  `solicitar_consentimento`) e sensíveis (`criar_plano`, `ativar_lembretes`,
  `simular_contratacao`, `compartilhar_dados`, `ajustar_plano`, mais
  `extensoes.ferramentas_sensiveis()`). Desconhecida = sensível.
- **FR-002** `solicitar_consentimento(acao, resumo)` cria o `consent_id`, marca
  `pendente` no state, devolve `consent_id, acao, resumo, status, o_que_faz,
  o_que_nao_faz, dados_usados` e grava `consentimento_solicitado`. Move
  `estado_jornada` para `AGIR` (nunca sai de `ACOMPANHAR`).
- **FR-003** Analisador sim/não determinístico: aceite, recusa, ambíguo e
  "sem resposta". Negação vence aceite.
- **FR-004** Leitura (`before_model` 20): decide o pendente com a última
  mensagem do cliente. Grava `consentimentos` + `consentimento_decidido` e loga
  `consentimento`. Na recusa e no ambíguo responde sem chamar o LLM.
- **FR-005** Gate (`before_tool` 20): sensível sem `aceito` não usado →
  `CONSENTIMENTO_NECESSARIO`. O uso consome o consentimento.
- **FR-006** Ações simuladas `criar_plano`, `ativar_lembretes`,
  `simular_contratacao` e `compartilhar_dados` (ciclo §3.3).
- **FR-007** `RegistroBigQuery` (streaming insert, sem SQL montado por texto) e
  seleção fake/BigQuery por `BUSSOLA_FAKES`.
- **FR-008** Auditoria (`before_tool`/`after_tool` 90): `ferramenta_chamada`,
  `estado_alterado`, `sessao_iniciada`, com minimização.
- **FR-009** Guardrail de entrada (`before_model` 10): regras + Model Armor
  opcional. Recusa em pt-BR com `customMetadata.bussola.guardrail` ∈
  `outro_cliente | ignorar_instrucoes | infra | promessa_credito |
  compartilhar_dados | fora_do_escopo` e `respostas_rapidas`.
- **FR-010** Guardrail de saída (`after_model` 10): regras + Model Armor
  opcional. Também anexa os chips "Sim, autorizo" / "Agora não" quando há
  pedido pendente.
- **FR-011** Instruções 50–69: quando e como pedir consentimento, nunca
  executar sem "sim", como explicar recusas.
- **FR-012** Eval `eval/seguranca/` com 8+ casos, determinístico (D1), gravando
  `resultado.md`.
- **FR-013** Logs só com os campos de contratos §9. Nunca prompt, mensagem do
  cliente, chaves ou tokens.

### Key Entities

- Entrada `session.state.consentimentos[acao]`: `{consent_id, status, ts,
  resumo?, invocation_id?, usado?}`.
- Linhas `Plano`, `Consentimento`, `EventoAuditoria` (`persistencia.py`).

## Success Criteria *(mandatory)*

- **SC-001** Nenhuma ação sensível executa sem "sim" (teste de integração com
  o runner do ADK).
- **SC-002** Os 8 casos do eval passam.
- **SC-003** `make lint`, `make test` e `make test-bq` verdes.

## Assumptions

- O 004 instala os quatro agregados de callback no `agent.py` e chama
  `carregar_extensoes()`. O hello do 000 já faz isso.
- `session.state.objetivo` e `session.state.cenarios` são escritos pelo 004.
  Nos testes, são preenchidos à mão.
- O 004 usa um modelo não-streaming (`NonStreamingModel`). Mesmo assim, o
  guardrail de saída trata pedaços parciais: esconde o texto parcial quando
  uma regra dispara e substitui a resposta final. Limite conhecido: um
  pedaço parcial já entregue antes do disparo não volta.
