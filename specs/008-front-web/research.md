# Research: Front web da Bússola

Phase 0 do plano. Cada item: decisão, motivo e alternativas rejeitadas.

## R1. API HTTP do ADK

- **Decisão:** usar os endpoints do servidor FastAPI do ADK (`adk web` /
  `adk api_server`):
  - `POST /apps/{app}/users/{user}/sessions` (corpo `{}`) → `{id, appName,
    userId, state, events, lastUpdateTime}`;
  - `POST /run_sse` com `{appName, userId, sessionId, newMessage: {role:
    "user", parts: [{text}]}, streaming: true}` → `text/event-stream`;
  - `GET /apps/{app}/users/{user}/sessions/{id}` para ressincronizar o
    `state` depois de cada turno.
- **Motivo:** é a API que o `make agent` já expõe (app `bussola_agent`) e que
  o `bussola-agent` servirá em produção (007). O modelo de requisição aceita
  camelCase (alias pydantic), igual ao formato dos eventos.
- **`userId`:** fixo `"fernando"`. O `id_usuario` do contrato é preenchido
  pelo agente a partir de `ANCHOR_USER_ID` (`inicializar_sessao`), então o
  front nunca envia nem conhece o UUID.
- **Alternativas:** `/run` sem streaming (perde o texto aparecendo aos
  poucos); WebSocket `/run_live` (voltado a áudio, mais complexo).

## R2. Leitura do SSE

- **Decisão:** `fetch` + `ReadableStream` + `TextDecoder`, com parser
  próprio (`web/src/agente/sse.ts`): acumula bytes, separa blocos por linha
  em branco, junta as linhas `data:` de cada bloco e faz `JSON.parse`. Linhas
  vazias extras e comentários (`:`) são ignorados; bloco incompleto fica no
  buffer até o próximo pedaço. `data: {"error": "..."}` vira falha do turno.
- **Motivo:** `EventSource` não faz `POST`. O parser é pequeno e testável sem
  rede.
- **Alternativas:** `@microsoft/fetch-event-source` (dependência a mais para
  ~40 linhas).

## R3. Formato dos eventos e streaming

- **Decisão:** tratar o evento ADK em camelCase: `author`, `invocationId`,
  `partial`, `timestamp`, `content.parts[]` com `text`, `functionCall {id,
  name, args}` ou `functionResponse {id, name, response}`, e `actions`
  com `stateDelta`. Texto `partial: true` é acumulado num rascunho por autor;
  o evento final (não parcial) do mesmo autor **substitui** o rascunho, o
  que evita duplicar mensagem quando o ADK reenvia o texto agregado.
- **`customMetadata.bussola` (opcional):** extensão para respostas rápidas,
  tag semântica e guardrail. O simulado sempre envia; o agente real pode
  passar a enviar (proposta registrada em
  [contracts/eventos-agente.md](./contracts/eventos-agente.md)). Sem ela, o
  front cai em sugestões por estado da jornada e mensagens sem tag.

## R4. Extração do envelope

- **Decisão:** espelhar `mcp_conexao._extrair_envelope` do agente: aceitar o
  envelope direto, `{result: envelope}`, `{structuredContent: envelope}`,
  `{structuredContent: {result: envelope}}` e `{content: [{type: "text",
  text: "<json>"}]}`. Resultado sem envelope reconhecível é tratado como
  dados crus da ferramenta local (sem `fonte`).
- **Motivo:** o `McpToolset` do ADK entrega a resposta da ferramenta MCP em
  formatos diferentes conforme a versão; o agente já normaliza, e o front
  precisa tolerar os mesmos formatos no modo ao vivo.

## R5. Agente simulado

- **Decisão:** um transporte em TypeScript com a mesma interface do cliente
  ao vivo (`iniciar()` e `enviar(texto) → AsyncIterable<EventoAdk>`). Ele
  classifica o texto do cliente por regras determinísticas (intenções do
  roteiro, E1, E2, consentimento) e emite eventos ADK:
  - ferramentas MCP → **goldens sem alteração** (`web/fixtures/goldens.json`);
  - ferramentas locais de 004/005/006 → emuladas por `simulado/locais.ts`
    com as regras dos contextos:
    - consentimento: ações sensíveis, "sim"/"não"/ambíguo, consumo único;
    - `avancar_mes`: planejado = aporte do plano; realizado = sobra do mês
      (`resumo_mes`); desvio = realizado − planejado; tolerância 10% do
      planejado; `categoria_desvio` = macro com maior alta sobre a média
      por macro de jan–jun/2025 (meses sem a macro contam como 0);
      acumulado = soma dos realizados positivos desde o plano;
    - rotas: A mantém o prazo (aporte = restante ÷ meses restantes); B mantém
      o aporte (prazo = teto de restante ÷ aporte); resposta no formato do
      `simular_objetivo`, com a capacidade do golden de jan–jun/2025;
    - valores arredondados a 2 casas **dentro da emulação** (a "ferramenta").
  - toda resposta emulada leva o aviso `Resposta simulada pelo front;
    regravar após o ciclo NNN` (004, 005 ou 006).
- **Relógio injetável** (`agora()`): real no navegador; fixo no gerador e nos
  testes, o que torna o roteiro gravado determinístico.
- **Atrasos injetáveis:** ~250 ms entre ferramentas e ~25 ms por pedaço de
  texto; E5 multiplica os atrasos para mostrar skeleton e cursor; zero nos
  testes.
- **Alternativas:** tocar só um roteiro gravado (não responde a "não", E1,
  E3 com retry nem a meses seguintes); MSW interceptando `/run_sse` (acopla o
  simulado ao HTTP sem ganho, e o objetivo é justamente não depender de
  backend).

## R6. Fixtures do front

- **Decisão:** `web/scripts/gerar-fixtures.ts`, executado com `tsx`:
  1. lê `contracts/fixtures/ferramentas/*.json` e
     `contracts/fixtures/rag/trechos_exemplo.json`;
  2. grava `web/fixtures/goldens.json` (chaves ordenadas, conteúdo literal);
  3. roda o agente simulado com relógio fixo sobre as mensagens do roteiro
     e grava `web/fixtures/roteiro-demo.json` (turnos com mensagem e
     eventos).
  Um teste do Vitest regenera em memória e compara com os arquivos: regenerar
  não produz diff (contexto §7). Outro teste confere que cada golden em
  `goldens.json` é igual ao arquivo de `contracts/fixtures/`.
- **Motivo:** o front não lê fora de `web/` em runtime; o roteiro gravado
  é o artefato para regravar e comparar depois de S4 e S6.
- **Alternativas:** importar `../contracts/fixtures` direto no Vite (mistura
  raiz do build com contrato e esconde a dependência); `node
  --experimental-strip-types` (exigiria extensões `.ts` em todos os imports
  do código de app).

## R7. Estilo: Tailwind v4 e Dynamic Glass

- **Decisão:** `@tailwindcss/vite`; `src/app.css` parte de
  `docs/design/tailwind-theme.css` (tema, `glass-*`, ambiente com `drift1–3`)
  e das classes de `docs/design/canvas/bussola.css` que os frames usam
  (tags, chips, stepper, cards de cenário, consentimento, tokens escuros).
  Modo escuro por classe `.dark` no container (custom variant do handoff),
  iniciado por `prefers-color-scheme` e alternável no header.
- **Fallbacks:** `prefers-reduced-transparency` e `@supports not
  (backdrop-filter)` → superfície sólida; `prefers-reduced-motion` → sem
  `drift` nem `enter`.
- **Fontes:** Nunito Sans e JetBrains Mono via Google Fonts no
  `index.html`, com fallback de sistema (sem rede, a tela continua legível).

## R8. Auditoria derivada

- **Decisão:** `sessao/auditoria.ts` gera eventos de auditoria a partir dos
  eventos do agente:
  - início da sessão → `sessao_iniciada`;
  - mudança de `estado_jornada` → `estado_alterado`;
  - `functionCall` de ferramenta → `ferramenta_chamada`;
  - consentimento novo `pendente` → `consentimento_solicitado`; mudança para
    `aceito`/`recusado` → `consentimento_decidido`;
  - `criar_plano` ok → `plano_criado` e `acao_executada`;
  - `ativar_lembretes`/`simular_contratacao` ok → `acao_executada`;
  - `ajustar_plano` ok → `plano_ajustado` e `acao_executada`;
  - `avancar_mes` ok → `acompanhamento_mes_avancado`, e com status `desvio`
    também `desvio_detectado` e `rota_recalculada`;
  - `customMetadata.bussola.guardrail` → `guardrail_bloqueio`.
- **Motivo:** o front não consulta o BigQuery (contexto §3.3); a trilha da
  sessão basta para a banca ver a governança.

## R9. Números na tela

- **Decisão:** componentes recebem envelopes e só chamam
  `formatar.ts` (`Intl.NumberFormat('pt-BR')` para BRL e percentuais,
  mês por extenso, período `jan–jun/2025`, data `26/09/2026 14:32`).
  Nenhum componente soma, subtrai, divide ou arredonda para gerar valor
  novo. Percentuais que já vêm como fração (`pct_capacidade: 0.8`) são
  exibidos como `80%` (mudança de escala na formatação, sem valor novo).
- **Sparkline:** desenhada com as `sobra` da `serie_mensal` (escala visual,
  sem número novo na tela).
- **Recomendado:** o selo vai para o cenário que o agente indicar em
  `customMetadata.bussola.recomendado`; sem essa indicação, para o cenário
  `viavel` de menor `pct_capacidade` (seleção, não cálculo).

## R10. Varredura do bundle (AC-11)

- **Decisão:** `web/scripts/varrer-bundle.ts`, depois do `vite build`, varre
  `dist/` procurando: UUID completo (regex v4), o ID do projeto GCP, padrões
  de SQL (`SELECT … FROM`, `INSERT INTO`), chaves (`AIza…`, `-----BEGIN`),
  e nomes de segredo (`gemini-api-key`). Falha o `make web-build` se achar.
  O ID do projeto e o UUID âncora não aparecem literais no script: ele os lê
  de `contracts/env.example` (`GOOGLE_CLOUD_PROJECT`, `ANCHOR_USER_ID`) em tempo de
  execução.
