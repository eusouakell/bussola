# Implementation Plan: Front web da Bússola (simulação da jornada)

**Branch**: `008-front-web` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-front-web/spec.md`

## Summary

SPA React em `web/` que reproduz o protótipo Dynamic Glass
(`docs/design/`) e conversa com a Bússola por **eventos no formato do ADK**.
Dois transportes emitem o mesmo tipo de evento:

- **ao vivo:** cliente HTTP da API do ADK (`/apps/.../sessions`, `/run_sse`),
  com proxy do Vite para o `make agent` em desenvolvimento;
- **simulado (padrão):** agente em TypeScript no navegador que responde ao
  roteiro da demo com os goldens de `contracts/fixtures/ferramentas/`, sem
  alteração, e emula as ferramentas locais de 004/005/006 pelas regras
  publicadas nos contextos desses ciclos.

Um reducer puro converte eventos em itens de conversa, estado da sessão e
trilha de auditoria. Os componentes só renderizam esse modelo e só formatam
números (constituição I). Um gerador empacota os goldens e grava o roteiro da
demo em `web/fixtures/`; um teste garante que regenerar não produz diff.

## Technical Context

**Language/Version**: TypeScript 6.0 (strict; < 6.1 por compatibilidade com typescript-eslint), ES2022; Node 24 / npm 11 no
build.

**Primary Dependencies**: React 19, Vite 8, Tailwind CSS v4.3
(`@tailwindcss/vite`). Sem biblioteca de estado, roteador ou UI kit: o
modelo é um reducer (`useReducer`) e as vistas P1–P5 são trocadas por
estado local.

**Storage**: nenhum. Estado em memória; a sessão ao vivo vive no agente.

**Testing**: Vitest 5 + Testing Library + jsdom (`web/src/**/*.test.ts(x)`);
ESLint (typescript-eslint, react-hooks); `tsc --noEmit`.

**Target Platform**: navegadores modernos (Chrome, Safari, Firefox atuais),
390 px a 1440 px, claro e escuro.

**Project Type**: web-app estático (SPA) consumidor de uma API existente.

**Performance Goals**: tela inicial utilizável em ≤ 2 s sem rede (SC-005);
bundle JS alvo < 300 kB gzip.

**Constraints**: sem rede no modo simulado; sem segredos, SQL, nome de
projeto ou UUID completo no bundle (SC-006); o front não calcula números
(FR-007); só escreve em `web/`, `specs/008-front-web/` e acréscimos no
`Makefile` (contexto §4).

**Scale/Scope**: 1 usuário (âncora), ~30 componentes, 6 estados de jornada,
5 estados de borda, 5 vistas de produto.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Como o plano atende | Status |
|---|---|---|
| I. Números de ferramentas | A UI só formata valores de `functionResponse`. As ferramentas locais emuladas no modo simulado aplicam as fórmulas publicadas de 005/006 e marcam a resposta com aviso de simulação; é o "agente" que calcula, nunca um componente. Teste de componente usa envelope golden e confere os valores formatados. | PASS |
| II. Isolado de SQL e infra | O front só vê envelopes; `ErroFerramenta` mostra mensagem pt-BR fixa por código, nunca `erro.mensagem` técnica bruta nem SQL. Varredura do bundle (AC-11). | PASS |
| III. Escopo por cliente | O front não envia `id_usuario`; o agente preenche a partir do ambiente (`inicializar_sessao`). ID só mascarado. | PASS |
| IV. Rotulado e explicável | Tags Diagnóstico / Simulação / Recomendação / Ação em cada card; `ChipFonte` em todo número; `ExplicacaoRecomendacao` com fontes. | PASS |
| V. Sintéticos e logs seguros | Selo e disclaimer fixos; o front não loga texto do cliente (sem `console.log` de mensagens; regra ESLint `no-console`). | PASS |
| VI. Consentimento | Botões só enviam `sim` / `não`; o card deriva de `consentimentos` do state; auditoria da sessão visível. O front não decide consentimento. | PASS |
| VII. Segredos | Nenhuma variável secreta; `VITE_*` só com modo e nome do app. Varredura do bundle. | PASS |
| VIII. pt-BR | Toda copy em pt-BR; teste procura palavras proibidas nos textos do roteiro. | PASS |
| IX. Testes e gates sem rede | `make web-lint`, `make web-test`, `make web-build` rodam sem rede. `make lint`/`make test` não mudam. Ver exceção de stack abaixo. | PASS com proposta |
| X. Contratos e paralelismo | Não altera `contracts/`, `agent/`, `mcp_server/`, `deploy/`. `web/` entra no mapa de contratos §1 por commit `contracts:` próprio (aditivo). Usa fixtures em vez de código não mergeado de 004–006. | PASS |
| Restrições de plataforma | A seção lista a stack Python. Um front Node/TS não é previsto; o contexto 008 o pede explicitamente e o roadmap §5 já o prevê no 007. A constituição está congelada: registramos `proposta-constituicao.md` (MINOR, aditiva) e seguimos com a exceção justificada em Complexity Tracking. | EXCEÇÃO JUSTIFICADA |

Re-check pós-Phase 1: sem mudanças; o contrato de eventos
([contracts/eventos-agente.md](./contracts/eventos-agente.md)) só consome
contratos v1.

## Project Structure

### Documentation (this feature)

```text
specs/008-front-web/
├── plan.md                    # este arquivo
├── research.md                # Phase 0
├── data-model.md              # Phase 1
├── quickstart.md              # Phase 1
├── contracts/
│   ├── eventos-agente.md      # front ↔ agente (ADK API, eventos, envelopes, state)
│   └── fixtures-web.md        # formato de web/fixtures/
├── proposta-constituicao.md   # stack web (MINOR)
├── checklists/requirements.md
├── tasks.md                   # Phase 2 (speckit-tasks)
└── traceability.md            # exportado no fim do run
```

### Source Code (repository root)

```text
web/
├── index.html
├── package.json / package-lock.json
├── vite.config.ts             # React + Tailwind v4 + proxy /apps e /run_sse → :8000; config do Vitest
├── tsconfig.json / tsconfig.node.json
├── eslint.config.js
├── .gitignore                 # node_modules, dist, coverage
├── README.md
├── fixtures/                  # GERADO por scripts/gerar-fixtures.ts
│   ├── goldens.json           # cópia literal de contracts/fixtures/ferramentas/*.json
│   └── roteiro-demo.json      # eventos ADK do roteiro F1–F7 (+ E1, E2)
├── scripts/
│   ├── gerar-fixtures.ts      # contracts/fixtures → web/fixtures (determinístico)
│   └── varrer-bundle.ts       # AC-11: segredos, SQL, projeto, UUID em dist/
└── src/
    ├── main.tsx / App.tsx / app.css   # tokens do docs/design (tailwind-theme + bussola.css)
    ├── config.ts              # VITE_BUSSOLA_MODO, VITE_ADK_APP
    ├── agente/
    │   ├── tipos.ts           # EventoAdk, Envelope, Erro, EstadoSessao
    │   ├── sse.ts             # parser text/event-stream (parcial, linhas vazias)
    │   ├── envelope.ts        # extrair envelope de functionResponse.response
    │   ├── cliente-adk.ts     # transporte ao vivo
    │   └── transporte.ts      # interface comum (iniciar, enviar → AsyncIterable<EventoAdk>)
    ├── simulado/
    │   ├── agente-simulado.ts # transporte simulado (intenções → eventos)
    │   ├── intencoes.ts       # classificação determinística do texto do cliente
    │   ├── locais.ts          # emulação de 004/005/006 (objetivo, consentimento, plano, avanço, rotas)
    │   ├── guardrails.ts      # E1/E2 e compartilhar_dados
    │   └── textos.ts          # copy do agente (prompt do design §6–§7, com números dos goldens)
    ├── sessao/
    │   ├── modelo.ts          # ItemConversa, EstadoSessao, EventoAuditoria
    │   ├── reducer.ts         # eventos → modelo (puro)
    │   ├── auditoria.ts       # derivação de tipo_evento
    │   └── useSessao.ts       # hook: transporte + reducer + ações (enviar, repetir, avançar)
    ├── formatacao/
    │   └── formatar.ts        # BRL, período, data/hora, mês por extenso, máscara de ID
    ├── componentes/           # nomes da §5 do prompt do design
    │   ├── layout/            # HeaderBussola, MTopo, Ambiente, BarraDemo, Composer, Bastidores
    │   ├── jornada/           # StepperJornada
    │   ├── conversa/          # MensagemCliente, MensagemAgente, LinhaFerramenta, BlocoAnalise, RespostasRapidas, ErroFerramenta, AlertaGuardrail, Skeleton
    │   ├── cards/             # CardObjetivo, CardDiagnostico, CardDividas, CardOportunidadesCorte, CardSimulacao, ComparadorCenarios, CardCenario, ExplicacaoRecomendacao, CardConsentimento, CardPlano, DivisorMes, CardPlanejadoRealizado, CardRotaRecalculada, CardOportunidade
    │   └── base/              # ChipFonte, Tag, SeloSintetico, Disclaimer, Avisos, Icone
    ├── vistas/                # P1Encerramento, P2MeuPlano, P3Trilha, P4Resumo, P5CheckIn, EstadoVazio
    └── test/                  # setup do Vitest e helpers (renderizar com goldens)
```

**Structure Decision**: projeto único `web/`, irmão de `agent/` e
`mcp_server/`. Testes ficam ao lado do código (`*.test.ts(x)`), padrão do
Vitest. `web/fixtures/` é versionado porque é contrato de saída (contexto
§5: "fixtures de eventos para regravar depois de S4 e S6").

### Mapeamento ferramenta → UI

| `functionCall.name` | Nome legível (conversa) | Card | Tag |
|---|---|---|---|
| `perfil_financeiro` | Perfil financeiro | `CardDiagnostico` (com `capacidade_poupanca`) | Diagnóstico |
| `capacidade_poupanca` | Capacidade de poupança | complementa `CardDiagnostico` | Diagnóstico |
| `dividas_e_parcelas` | Dívidas e parcelas | `CardDividas` | Diagnóstico |
| `oportunidades_corte` | Oportunidades de corte | `CardOportunidadesCorte` | Diagnóstico |
| `resumo_mes` | Resumo do mês | usado por `CardPlanejadoRealizado` (fonte) | Diagnóstico |
| `simular_objetivo` | Simulação do objetivo | `CardSimulacao` (ou rota, se chamada por `avancar_mes`) | Simulação |
| `comparar_cenarios` | Comparação de cenários | `ComparadorCenarios` + `ExplicacaoRecomendacao` | Recomendação |
| `buscar_contexto_financeiro` | Base de conhecimento | fontes da `ExplicacaoRecomendacao` | Recomendação |
| `registrar_objetivo` | Registro do objetivo | `CardObjetivo` | — |
| `escolher_cenario` | Escolha do cenário | (sem card; atualiza state) | — |
| `solicitar_consentimento` | Pedido de autorização | `CardConsentimento` | Ação |
| `criar_plano` | Criação do plano | `CardPlano` | Ação |
| `ativar_lembretes` / `ajustar_plano` | Lembretes / Ajuste do plano | recibo de ação | Ação |
| `avancar_mes` | Avanço de mês | `DivisorMes` + `CardPlanejadoRealizado` + `CardRotaRecalculada` (ou `CardOportunidade` em folga) | Diagnóstico / Recomendação |
| `status_plano` | Status do plano | alimenta P2/P5 | Diagnóstico |
| desconhecida | nome técnico em Bastidores; "Consulta" na conversa | JSON resumido só em Bastidores | — |

Erros: qualquer `erro.codigo` → `ErroFerramenta` com copy fixa por código
(tabela em [contracts/eventos-agente.md](./contracts/eventos-agente.md)).
`CONSENTIMENTO_NECESSARIO` não é falha: o card de consentimento aparece
pelo state.

### Agent context update

O passo "update agent context" do Spec Kit (`update-agent-context.sh`)
**não é executado**: o `CLAUDE.md` da raiz pertence ao 000 e a regra do
contexto §1.5 limita a escrita a `web/`, `specs/008-*` e `Makefile`. Os
comandos do front ficam em `web/README.md` e no quickstart.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Stack Node/TypeScript fora das "Restrições de plataforma" (Python-only) | O pedido do time (contexto §1.7) e o roadmap §5 exigem um front React; o protótipo foi desenhado para Tailwind v4. | ADK Web UI não mostra cards, consentimento como momento nem Bastidores; um front em Python (ex.: Mesop) não reaproveita o handoff Tailwind. A proposta de emenda fica em `proposta-constituicao.md`. |
| Emulação das ferramentas locais de 004–006 no front | Constituição X: o ciclo não depende de código não mergeado; o roteiro precisa das respostas dessas ferramentas. | Esperar 004–006 bloquearia a demo; usar números do design violaria a constituição I. A emulação fica isolada em `web/src/simulado/`, marcada com aviso e regravável. |
