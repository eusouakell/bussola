# Tasks: Front web da Bússola (simulação da jornada)

**Input**: Design documents from `specs/008-front-web/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/eventos-agente.md, contracts/fixtures-web.md, quickstart.md

**Tests**: pedidos pelo contexto 008 (AC-04, AC-05, AC-09, AC-10, AC-11) e
pela constituição IX. Os testes ficam ao lado do código (`*.test.ts(x)`).

**Organization**: tarefas agrupadas por história (US1–US5) para
implementação e teste independentes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência
  pendente).
- **[Story]**: história da spec (US1…US5).

## Path Conventions

Projeto único `web/` na raiz do repositório (ver plan.md, Project Structure).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: projeto `web/` com toolchain e gates.

- [x] T001 Criar `web/package.json` com React 19, Vite 8, Tailwind 4.3 (`@tailwindcss/vite`), TypeScript 6.0.3, Vitest 5, Testing Library, jsdom, ESLint 10 + typescript-eslint + react-hooks, tsx; scripts `dev`, `build`, `lint`, `test`, `fixtures`, `varrer`; e gerar `web/package-lock.json`
- [x] T002 [P] Criar `web/tsconfig.json` e `web/tsconfig.node.json` (strict, ES2022, `resolveJsonModule`, `noEmit`)
- [x] T003 [P] Criar `web/vite.config.ts` (plugin React + Tailwind, proxy `/apps` e `/run_sse` → `http://localhost:8000`, bloco `test` do Vitest com jsdom e `src/test/setup.ts`)
- [x] T004 [P] Criar `web/eslint.config.js` (typescript-eslint, react-hooks, `no-console` como erro)
- [x] T005 [P] Criar `web/.gitignore` (`node_modules`, `dist`, `coverage`) e `web/index.html` (lang pt-BR, título "Bússola")
- [x] T006 Acrescentar ao `Makefile` os alvos `web-install`, `web`, `web-lint`, `web-test`, `web-build` (build roda a varredura do bundle), sem alterar alvos existentes

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: tipos, parser, reducer, formatação, fixtures, tema e casca da
tela. Nenhuma história começa antes disto.

- [x] T007 Criar tipos `EventoAdk`, `Envelope`, `Fonte`, `ErroEnvelope`, `EstadoSessao`, `MetadadosBussola` em `web/src/agente/tipos.ts`
- [x] T008 [P] Criar interface `Transporte` (`iniciar`, `enviar → AsyncIterable<EventoAdk>`) em `web/src/agente/transporte.ts`
- [x] T009 [P] Implementar `extrairEnvelope` (direto, `{result}`, `structuredContent`, `content[].text`, cru) em `web/src/agente/envelope.ts` com testes em `web/src/agente/envelope.test.ts`
- [x] T010 [P] Implementar formatação pt-BR (BRL, período `jan–jun/2025`, data e hora, mês por extenso, percentual, máscara de ID) em `web/src/formatacao/formatar.ts` com testes em `web/src/formatacao/formatar.test.ts`
- [x] T011 Criar `ItemConversa`, `EventoAuditoria`, `ModeloSessao`, `RegistroFerramenta` em `web/src/sessao/modelo.ts`
- [x] T012 Implementar derivação de auditoria (`tipo_evento` de contratos §6) em `web/src/sessao/auditoria.ts`
- [x] T013 Implementar reducer puro (rascunho parcial, texto final, `functionCall`, `functionResponse`, `stateDelta` raso sem `temp:*`, jornada, ferramentas, agrupamento) em `web/src/sessao/reducer.ts` com testes em `web/src/sessao/reducer.test.ts`
- [x] T014 [P] Implementar gerador `web/scripts/gerar-fixtures.ts` que copia `contracts/fixtures/ferramentas/*.json` e `contracts/fixtures/rag/trechos_exemplo.json` para `web/fixtures/goldens.json` (chaves ordenadas, 2 espaços, `\n` final)
- [x] T015 Portar tokens e vidro de `docs/design/tailwind-theme.css` e `docs/design/canvas/bussola.css` para `web/src/app.css` (claro, escuro, fallback sem `backdrop-filter`, movimento e transparência reduzidos)
- [x] T016 [P] Criar `web/src/config.ts` (`VITE_BUSSOLA_MODO`, `VITE_ADK_APP`) e `web/src/test/setup.ts`
- [x] T017 [P] Criar componentes base `Icone`, `Tag`, `SeloSintetico`, `Disclaimer`, `Avisos`, `ChipFonte` em `web/src/componentes/base/`
- [x] T018 Criar `web/src/main.tsx` e casca `web/src/App.tsx` com `Ambiente`, `HeaderBussola`, `MTopo` em `web/src/componentes/layout/`

**Checkpoint**: tipos, reducer e tema prontos; histórias podem começar.

---

## Phase 3: User Story 1 - Simular a jornada completa sem backend (Priority: P1) 🎯 MVP

**Goal**: roteiro F1–F7 no navegador, sem rede, com números dos goldens.

**Independent Test**: `make web`, seguir as sugestões de F1 a F7; cada etapa
mostra o card esperado com os números dos goldens.

### Tests for User Story 1

- [x] T019 [P] [US1] Teste de componente: golden `perfil_financeiro__ate_202506` + `capacidade_poupanca__ate_202506` → `CardDiagnostico` com valores formatados em `web/src/componentes/cards/CardDiagnostico.test.tsx`
- [x] T020 [P] [US1] Teste: consentimento `pendente` → `CardConsentimento`; `aceito` → recibo com data, hora e ID em `web/src/componentes/cards/CardConsentimento.test.tsx`
- [x] T021 [P] [US1] Teste: `estado_jornada = ORIENTAR` → 3 passos concluídos no `StepperJornada` em `web/src/componentes/jornada/StepperJornada.test.tsx`
- [x] T022 [P] [US1] Teste de roteiro: agente simulado de F1 a F7b gera os números canônicos (1681.15, 884.53, −796.62, Viagens, 1712.67 × 17, 18 meses) em `web/src/simulado/agente-simulado.test.ts`

### Implementation for User Story 1

- [x] T023 [P] [US1] Implementar classificação determinística de intenções em `web/src/simulado/intencoes.ts`
- [x] T024 [P] [US1] Implementar emulação das ferramentas locais (registrar_objetivo, escolher_cenario, solicitar_consentimento, criar_plano, ativar_lembretes, simular_contratacao, ajustar_plano, avancar_mes, status_plano, rotas A e B) com aviso de resposta simulada em `web/src/simulado/locais.ts`
- [x] T025 [P] [US1] Escrever a copy do agente (pt-BR, com números vindos dos envelopes) em `web/src/simulado/textos.ts`
- [x] T026 [US1] Implementar `AgenteSimulado` (relógio e atrasos injetáveis, IDs por contador, `customMetadata.bussola`) em `web/src/simulado/agente-simulado.ts`
- [x] T027 [US1] Estender `web/scripts/gerar-fixtures.ts` para gravar `web/fixtures/roteiro-demo.json` com o relógio fixo e teste de determinismo em `web/src/simulado/roteiro.test.ts`
- [x] T028 [US1] Implementar hook `useSessao` (transporte, reducer, `enviar`, `repetir`, `trocarModo`) em `web/src/sessao/useSessao.ts`
- [x] T029 [P] [US1] Criar `StepperJornada` (completo e compacto "N/6 · Estado") em `web/src/componentes/jornada/StepperJornada.tsx`
- [x] T030 [P] [US1] Criar `MensagemCliente`, `MensagemAgente` (cursor de digitação, tag), `RespostasRapidas`, `LinhaFerramenta`, `BlocoAnalise` e `ErroFerramenta` (copy fixa por `erro.codigo`, contrato §4) em `web/src/componentes/conversa/`
- [x] T031 [P] [US1] Criar `CardObjetivo`, `CardDiagnostico`, `CardDividas`, `CardOportunidadesCorte`, `CardSimulacao` em `web/src/componentes/cards/`
- [x] T032 [P] [US1] Criar `ComparadorCenarios`, `CardCenario` (selo Recomendado por metadado ou regra R9, campo "Outro caminho") e `ExplicacaoRecomendacao` em `web/src/componentes/cards/`
- [x] T033 [P] [US1] Criar `CardConsentimento` (O que vou fazer, O que não vou fazer, Dados usados, Autorizar/Agora não → "sim"/"não", recibo) e `CardPlano` em `web/src/componentes/cards/`
- [x] T034 [P] [US1] Criar `DivisorMes`, `CardPlanejadoRealizado`, `CardRotaRecalculada`, `CardOportunidade` em `web/src/componentes/cards/`
- [x] T035 [US1] Criar `Composer` e `BarraDemo` (mês de `ate_anomes`, "Avançar um mês ▸" desabilitado sem plano ou em dez/2025, controle de modo) em `web/src/componentes/layout/`
- [x] T036 [US1] Montar a conversa em `web/src/App.tsx` (saudação, 4 sugestões de objetivo, mapeamento item → componente, rolagem)

**Checkpoint**: F1–F7 e F7b funcionam no modo simulado.

---

## Phase 4: User Story 2 - Ver os bastidores e a governança (Priority: P1)

**Goal**: Bastidores com Jornada, Ferramentas, Consentimentos e Auditoria.

**Independent Test**: depois de criar o plano, abrir as 4 abas e conferir os
itens contra a conversa.

### Tests for User Story 2

- [x] T037 [P] [US2] Teste: auditoria após avanço de mês com desvio lista `acompanhamento_mes_avancado`, `desvio_detectado`, `rota_recalculada` em ordem em `web/src/sessao/auditoria.test.ts`
- [x] T038 [P] [US2] Teste: Bastidores mostram 4 abas e o rodapé com `36a2…7269`, sem UUID completo em `web/src/componentes/layout/Bastidores.test.tsx`

### Implementation for User Story 2

- [x] T039 [US2] Criar `Bastidores` (painel lateral no desktop, bottom sheet no mobile) com abas Jornada, Ferramentas (nome técnico, parâmetros mascarados, fonte, duração), Consentimentos e Auditoria e rodapé de estado em `web/src/componentes/layout/Bastidores.tsx`
- [x] T040 [US2] Ligar o `ChipFonte` de cada card ao envelope de origem (ferramenta, tabelas, período, avisos) em `web/src/componentes/base/ChipFonte.tsx`
- [x] T041 [US2] Abrir e fechar Bastidores pelo header e pelo `MTopo` em `web/src/App.tsx`

**Checkpoint**: governança visível em todas as etapas.

---

## Phase 5: User Story 3 - Conversar com o agente real (Priority: P2)

**Goal**: transporte ao vivo pela API do ADK com o mesmo mapeamento.

**Independent Test**: `make mcp`, `make agent`, `make web`; trocar para "Ao
vivo" e ver uma chamada MCP virar `LinhaFerramenta` e card.

### Tests for User Story 3

- [x] T042 [P] [US3] Teste do parser SSE com eventos parciais, blocos cortados, linhas vazias e `data: {"error"}` em `web/src/agente/sse.test.ts`
- [x] T043 [P] [US3] Teste do cliente ADK com `fetch` falso (criar sessão, `run_sse`, falha HTTP → `falha_conexao`) em `web/src/agente/cliente-adk.test.ts`

### Implementation for User Story 3

- [x] T044 [P] [US3] Implementar parser `text/event-stream` em `web/src/agente/sse.ts`
- [x] T045 [US3] Implementar `ClienteAdk` (sessão, `run_sse` com streaming, ressincronizar state) em `web/src/agente/cliente-adk.ts`
- [x] T046 [US3] Estender `ErroFerramenta` e o reducer para a falha de conexão ("Não consegui falar com a Bússola agora.", "Tentar de novo", "Usar modo simulado") em `web/src/componentes/conversa/ErroFerramenta.tsx`

**Checkpoint**: modo ao vivo funcional com o agente do 000.

---

## Phase 6: User Story 4 - Ensaiar estados de borda (Priority: P2)

**Goal**: E1–E5 reproduzíveis em até 3 interações.

**Independent Test**: enviar as frases de E1 e E2; ativar E3–E5 no menu da
barra de demonstração.

### Tests for User Story 4

- [x] T047 [P] [US4] Teste: `INDISPONIVEL` → `ErroFerramenta` com copy pt-BR, "Tentar de novo" e sem `erro.mensagem`, SQL ou nome de projeto em `web/src/componentes/conversa/ErroFerramenta.test.tsx`
- [x] T048 [P] [US4] Teste: E1, E2 e `compartilhar_dados` geram guardrail e `guardrail_bloqueio`; E3 falha uma vez e depois dá certo; E4 vira aviso âmbar em `web/src/simulado/guardrails.test.ts`

### Implementation for User Story 4

- [x] T049 [P] [US4] Implementar regras de guardrail (outro cliente, ignorar instruções, SQL/prompt/infra, promessa de crédito, compartilhar dados) em `web/src/simulado/guardrails.ts`
- [x] T050 [P] [US4] Criar `AlertaGuardrail` e `Skeleton` em `web/src/componentes/conversa/`
- [x] T051 [US4] Adicionar menu "Cenários de borda" (E3, E4, E5; só no simulado) em `web/src/componentes/layout/BarraDemo.tsx` e as flags de falha e lentidão em `web/src/simulado/agente-simulado.ts`

**Checkpoint**: E1–E5 ensaiáveis.

---

## Phase 7: User Story 5 - Consultar o plano fora da conversa (Priority: P3)

**Goal**: vistas P1–P5 só com números recebidos.

**Independent Test**: criar o plano e abrir cada vista; sem plano, ver o
estado vazio.

### Tests for User Story 5

- [x] T052 [P] [US5] Teste: sem plano → `EstadoVazio` com volta à conversa; com plano → `P2MeuPlano` com meta, aporte e prazo em `web/src/vistas/vistas.test.tsx`

### Implementation for User Story 5

- [x] T053 [P] [US5] Criar `EstadoVazio`, `P1Encerramento`, `P2MeuPlano`, `P3Trilha`, `P4Resumo`, `P5CheckIn` em `web/src/vistas/`
- [x] T054 [US5] Adicionar navegação entre Conversa e vistas (estado local, sem roteador) em `web/src/App.tsx`

**Checkpoint**: experiência completa do protótipo.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T055 [P] Implementar varredura do bundle (UUID v4, projeto e âncora lidos de `contracts/env.example`, SQL, `AIza`, `-----BEGIN`, `gemini-api-key`) em `web/scripts/varrer-bundle.ts`
- [x] T056 [P] Teste: `web/fixtures/goldens.json` igual a `contracts/fixtures/` e ausência de "garantido", "aprovado", "contrate agora" nos textos do roteiro em `web/src/simulado/fixtures.test.ts`
- [x] T057 [P] Escrever `web/README.md` (comandos, modos, estados de borda, regravação)
- [x] T058 Commit `contracts:` separado acrescentando `web/` (dono 008) ao mapa de `docs/ciclos/contratos.md` §1
- [x] T059 Verificar acessibilidade (rótulos com nomes dos componentes, foco visível, alvos de 44 px, status com texto e ícone) e mobile 390 px e modo escuro no navegador
- [ ] T060 Rodar `make web-lint`, `make web-test`, `make web-build` (conferir JS < 300 kB gzip, SC-005), `make lint`, `make test` e seguir o quickstart

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (1)**: sem dependências.
- **Foundational (2)**: depende do Setup; bloqueia as histórias.
- **US1 (3)**: depende do Foundational. É o MVP.
- **US2 (4)**: depende do Foundational; usa o `ModeloSessao` e fica mais útil
  com US1 (dados para as abas), mas testa-se com eventos de fixture.
- **US3 (5)**: depende do Foundational (reducer e tipos); independe de US1.
- **US4 (6)**: depende de US1 (agente simulado e `BarraDemo`).
- **US5 (7)**: depende do Foundational; os dados vêm do estado da sessão.
- **Polish (8)**: depois das histórias desejadas.

### Within Each User Story

- Testes escritos junto e falhando antes da implementação quando possível.
- Tipos e regras puras antes dos componentes; componentes antes da montagem
  em `App.tsx`.

### Parallel Opportunities

- T002–T005 em paralelo depois do T001.
- T008, T009, T010, T014, T016, T017 em paralelo depois do T007.
- Em US1: T023–T025 e T029–T034 em paralelo (arquivos distintos).
- US3 e US5 podem andar em paralelo a US1 depois do Foundational.

## Parallel Example: User Story 1

```text
T031 CardObjetivo/CardDiagnostico/CardDividas/... em web/src/componentes/cards/
T032 ComparadorCenarios/CardCenario/ExplicacaoRecomendacao
T033 CardConsentimento/CardPlano
T034 DivisorMes/CardPlanejadoRealizado/CardRotaRecalculada/CardOportunidade
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 e Phase 2.
2. Phase 3 (US1) e validar F1–F7 no navegador.
3. Parar e demonstrar.

### Incremental Delivery

1. Setup + Foundational.
2. US1 (MVP, roteiro da demo) → US2 (governança) → US3 (ao vivo) → US4
   (bordas) → US5 (vistas).
3. Polish e gates.
