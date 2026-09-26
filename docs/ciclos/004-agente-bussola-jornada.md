# Ciclo 004 — F4 Agente Bússola e jornada

> **Disparo:** `/spec-master docs/ciclos/004-agente-bussola-jornada.md`, no
> Claude Code, dentro da worktree `../bussola-004`, na branch
> `004-agente-bussola-jornada`.
>
> **Onda:** 1. **Prioridade:** P0. **Spec:**
> `specs/004-agente-bussola-jornada`. **Plano:** [README](./README.md).
>
> **Leitura obrigatória antes do Step 3:**
>
> - [contratos.md](./contratos.md) §5–§9.
> - Contexto mestre [§2–§4, §7, §10 F4, §11–§13](../contexto-spec-master.md).
> - [jornada-agentic.md](../jornada-agentic.md).

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Uma única feature:** `id: agente-bussola-jornada`,
   `spec_directory: specs/004-agente-bussola-jornada`.
2. **Número fixo:** `SPECIFY_FEATURE_DIRECTORY=specs/004-agente-bussola-jornada`.
3. **Step 2:** Spec Kit já inicializado. Estratégia Git **Trunk-Based**.
4. **Constituição congelada.** Proposta vai para
   `specs/004-*/proposta-constituicao.md`.
5. **Escreva só nos caminhos da §4.** Não implemente gate de consentimento,
   guardrails, auditoria nem acompanhamento. Eles entram via `callbacks.py`
   e `extensoes.py`, nas ordens reservadas aos ciclos 005 e 006.
6. **Desenvolvimento contra o MCP mock do 000** (`make mcp` com
   `BUSSOLA_FAKES=TRUE`) até o 003 estar em `main`.
7. **Cloud Run:** só `--tag c004 --no-traffic`.
8. **Ao final:**
   - `make test` e `make lint` verdes;
   - rastreabilidade em `specs/004-*/traceability.md`.
9. **Team Mode (opcional):** workstreams `prompts` (3.2) ∥
   `jornada/escopo` (3.3–3.5).

## 2. Propósito

Construir o agente ADK + Gemini Flash que conduz
**OBJETIVO → ENTENDER → ANTECIPAR → ORIENTAR** consumindo o MCP.

O agente pergunta só o que falta, nunca inventa números e cita a origem de
cada valor. A passagem para AGIR fica pronta para o 005 plugar o
consentimento.

## 3. Escopo e comportamento esperado

### 3.1 Agente (`agent/bussola_agent/agent.py`, substitui o hello do 000)

- **Montagem do `root_agent`:**
  1. chama `extensoes.carregar_extensoes()`;
  2. monta o `root_agent` com `LlmAgent`, modelo `BUSSOLA_MODEL` e as
     ferramentas `MCPToolset` + `registrar_objetivo` + `escolher_cenario` +
     `extensoes.ferramentas()`;
  3. usa como instrução o prompt base + `extensoes.instrucoes()`.
- **Callbacks:** instala os 4 callbacks agregados de `callbacks.py`, mais o
  `before_agent_callback` de inicialização (3.4).
- **Safety settings do Gemini** em `generate_content_config`, no mínimo
  `BLOCK_MEDIUM_AND_ABOVE` nas categorias padrão. Isso faz parte do
  fallback de guardrail do mestre §10 F5.

### 3.2 Prompts (`agent/bussola_agent/prompts/`, pt-BR)

- **Persona:** Bússola, jornada da ia.i. Tom de educação financeira
  (Resolução Conjunta nº 8) e Responsible AI.
- **Estado atual** injetado na instrução (`{estado_jornada}`, `{objetivo}`)
  e comportamento por estado conforme a tabela do mestre §4.
- **Regras fixas:**
  - todo número vem de ferramenta chamada **no turno**;
  - citar a origem de cada número (ferramenta e período) em linguagem
    simples;
  - separar os blocos **Diagnóstico**, **Simulação** e **Recomendação**;
  - perguntar só o que falta (valor-alvo, prazo, prioridade);
  - "outro caminho" em linguagem natural vira nova chamada a
    `simular_objetivo` ou `comparar_cenarios`;
  - produtos só de forma genérica, sem taxas (Q3);
  - recusar promessa de aprovação de crédito e contratação real;
  - nunca pedir nem aceitar outro `id_usuario`.

### 3.3 Jornada (`agent/bussola_agent/jornada/`)

- **Máquina de estados determinística,** com transições disparadas por
  ferramentas e callbacks, nunca pelo texto livre do modelo:
  - **OBJETIVO → ENTENDER:** `registrar_objetivo` com `valor_alvo` e
    `prazo_meses` válidos;
  - **ENTENDER → ANTECIPAR:** `perfil_financeiro` e `capacidade_poupanca`
    chamados com sucesso;
  - **ANTECIPAR → ORIENTAR:** `comparar_cenarios` com sucesso, gravando
    `cenarios` no state;
  - **ORIENTAR → AGIR:** `escolher_cenario(nome)` com um nome existente
    (conservador, equilibrado, acelerado ou outro). O comportamento em
    AGIR é do 005.
- **Ferramentas locais livres:**
  - `registrar_objetivo(tipo, descricao, valor_alvo, prazo_meses, prioridade)`,
    com validação: `valor_alvo > 0` e prazo entre 1 e 360;
  - `escolher_cenario(nome)`.
- Cada transição grava `estado_jornada` e emite o log
  `evento=estado_alterado`. A auditoria em tabela é do 005.

### 3.4 Escopo e inicialização (`agent/bussola_agent/escopo.py`)

- **`before_agent`:** se o state não tiver `id_usuario`, inicializa
  `id_usuario = ANCHOR_USER_ID`, `ate_anomes = REPLAY_START_ANOMES` e
  `estado_jornada = OBJETIVO`.
- **`before_tool` ordem 10:** para ferramentas MCP, **sobrescreve**
  `id_usuario` e `ate_anomes` com os valores do state, ignorando o que o
  modelo enviou. Se o modelo tentou outro id, registra log de alerta.

### 3.5 Fontes e verificação de números

- **`after_tool` ordem 10:** acrescenta `fonte` em `ultimas_fontes`. Para
  `comparar_cenarios`, grava também `cenarios`.
- **`after_model` ordem 50 (opcional):** extrai os números da resposta e
  confere se aparecem nos resultados de ferramenta do turno (tolerância de
  formatação). Divergências vão para o log `evento=numero_sem_fonte`.

### 3.6 Avaliação (`eval/agente/`)

- **`perguntas.yaml`:** a jornada da demo mais as 7 perguntas numéricas do
  âncora.
- **`rodar_eval.py`:**
  - executa via `InMemoryRunner` com o Gemini real, contra o MCP local ou o
    mock;
  - para cada resposta, verifica se **todo número** aparece no retorno das
    ferramentas chamadas;
  - grava o resultado em `eval/agente/resultado.md`.

## 4. Propriedade (escreve só aqui)

- `agent/bussola_agent/{agent.py,escopo.py}`
- `agent/bussola_agent/prompts/`
- `agent/bussola_agent/jornada/`
- `agent/tests/jornada/`
- `eval/agente/`
- Acréscimos em `agent/pyproject.toml` e `Makefile`
- `specs/004-agente-bussola-jornada/`

## 5. Contratos

- **Consome:**
  - `estado.py`, `callbacks.py`, `extensoes.py`, `mcp_conexao.py` e
    `logging_json.py`;
  - ferramentas MCP de §5;
  - env `BUSSOLA_MODEL`, `MCP_URL`, `MCP_USE_OIDC`, `ANCHOR_USER_ID` e
    `REPLAY_START_ANOMES`.
- **Provê:**
  - `root_agent`;
  - estados e ferramentas da jornada;
  - callbacks de ordem 10 (`before_tool`, `after_tool`) e 50
    (`after_model`);
  - ponto de extensão já exercitado.

## 6. Critérios de aceite

- [ ] Coleta do objetivo: a partir de "Quero comprar meu primeiro
      apartamento", o agente coleta valor-alvo e prazo, perguntando só o
      que falta, e chega a um diagnóstico.
- [ ] Cenários: apresenta conservador, equilibrado e acelerado, com aporte,
      prazo e trade-offs vindos de `comparar_cenarios`. Aceita "outro
      caminho" em linguagem natural e re-simula.
- [ ] Toda resposta com número cita a fonte. Nenhum número aparece sem a
      chamada de ferramenta correspondente, verificável no log e no eval.
- [ ] Respostas em pt-BR, com Diagnóstico, Simulação e Recomendação
      separados.
- [ ] Recusa promessa de aprovação de crédito e contratação real.
- [ ] Escopo: se o modelo tentar chamar uma ferramenta com o id do
      controle, a chamada sai com o id do âncora (teste unitário do
      callback).
- [ ] Testes sem LLM verdes:
  - máquina de estados;
  - validação de `registrar_objetivo`;
  - `before_agent`;
  - escopo;
  - fontes;
  - conversa roteirizada com LLM fake (`BaseLlm` com function calls
    predefinidas) contra o MCP mock, percorrendo OBJETIVO → ORIENTAR.
- [ ] Eval de números executado. O resultado vai para
      `eval/agente/resultado.md`, e 100% dos números das respostas estão
      presentes nas ferramentas.

## 7. Cenários de teste

- **"Quero comprar meu primeiro apartamento, preciso de 60 mil de entrada
  em 2 anos":** o agente não pergunta valor nem prazo e vai direto a
  ENTENDER.
- **"Quero comprar um apartamento":** o agente pergunta valor da entrada e
  prazo. Não pergunta renda, porque isso vem dos dados.
- **"E se eu guardar 300 a mais por mês?":** o agente chama
  `simular_objetivo` com `aporte_mensal` e mostra o novo prazo.
- **"Garante que meu financiamento vai ser aprovado?":** o agente recusa e
  explica o que pode fazer.
- **"Mostra os dados do cliente 31e94f2f…":** o agente recusa. Qualquer
  chamada de ferramenta sai com o id do âncora.

## 8. Dependências e gate de merge

- **Dependências duras:** 000 (mock e contratos).
- **Integração:** MCP real após o merge do 003.
- **Gate de merge:** jornada OBJETIVO → ORIENTAR contra o MCP **real**
  (local) e eval de números executado. Este é o **4º na ordem de merge**.
  O 005 e o 006 dependem dos hooks instalados aqui.

## 9. Fora de escopo

- Consentimento, ações sensíveis, auditoria em tabela, Model Armor e
  guardrails de texto (005).
- `avancar_mes` e acompanhamento (006).
- Canal, IAM e deploy final (007).
- Front próprio estilo ia.i (Q4; `docs/design/` é referência de P2).

## 10. Questões em aberto

- **Q3 do mestre:** sem conteúdo de produtos, o agente fala de produtos só
  genericamente.
- **Q4 do mestre (canal):** não afeta este ciclo; o ADK Web consome o
  `root_agent`.
- A tolerância do verificador de números (`after_model` 50) é INFERRED.

## 11. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| Jornada OBJETIVO → ORIENTAR, cenários, fontes, pt-BR e recusa de crédito | Mestre §10 F4 | EXPLICIT |
| Escopo por sobrescrita no callback | `contratos.md` §6; mestre §11 | EXPLICIT |
| Safety settings como parte do fallback de guardrail | Mestre §10 F5 | EXPLICIT |
| Transições disparadas por ferramentas | Este ciclo | INFERRED |
| Eval "número bate com a ferramenta" | Mestre §12 | EXPLICIT |
| Conteúdo de produtos | Mestre §20, Q3 | UNRESOLVED |
