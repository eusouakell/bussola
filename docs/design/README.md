# Design · Bússola

Resultado do [prompt do Claude Design](./prompt-claude-design-chat.md)
(Dynamic Glass, Tailwind CSS v4).

- **Canvas (fonte da verdade):** <https://claude.ai/artifact/X4fj9hrEEqmzFijJqiDpsa>
- **Snapshot versionado:** [`canvas/`](./canvas/), versão `1790445228-b6cb`,
  baixada em 26/09/2026.
- **Handoff Tailwind:** [`tailwind-theme.css`](./tailwind-theme.css), ponto de
  partida do `web/src/app.css` no 007
  ([pessoa B §5.3](../ciclos/pessoa-b-agente-plataforma.md)).

Os `.dc.html` só renderizam dentro do canvas (dependem do runtime
`support.js` do Claude Design). Aqui eles servem como referência de markup,
copy e estados. Para ver as telas, abra o canvas.

## Direção adotada

- **App primeiro.** A Bússola abre como jornada dentro do app do banco. Os frames
  390 px são o roteiro principal da demo; a versão 1440 px ficou como
  secundária (telão e web). O prompt original tratava o desktop como
  principal.
- **Tipografia:** Nunito Sans (texto) e JetBrains Mono (Bastidores, IDs).
  Se o brand kit oficial do banco chegar, ele prevalece sobre acento e
  tipografia.
- **Acento:** `#FF6200`, com `#FF6200` no CTA e `#FF6200` para texto sobre
  claro.

## Frames

### App (390 × 844) · roteiro da demo

| Frame | Arquivo | Prompt |
|---|---|---|
| M1 · Boas-vindas | [M1BoasVindas](./canvas/M1BoasVindas.dc.html) | §6 F1 |
| M2 · OBJETIVO | [M2Objetivo](./canvas/M2Objetivo.dc.html) | §6 F2 |
| M3 · ENTENDER | [M3Entender](./canvas/M3Entender.dc.html) | §6 F3 |
| M4 · ANTECIPAR | [M4Antecipar](./canvas/M4Antecipar.dc.html) | §6 F4 |
| M5 · ORIENTAR (herói) | [M5Orientar](./canvas/M5Orientar.dc.html) | §6 F5 |
| M6 · AGIR, consentimento | [M6Agir](./canvas/M6Agir.dc.html) | §6 F6 |
| M7 · AGIR, recibo e plano | [M7Plano](./canvas/M7Plano.dc.html) | §6 F6 |
| M8 · ACOMPANHAR, desvio e nova rota | [M8Acompanhar](./canvas/M8Acompanhar.dc.html) | §6 F7 |
| M9 · ACOMPANHAR, oportunidade | [M9Oportunidade](./canvas/M9Oportunidade.dc.html) | §6 F7b |
| M10 · Bastidores (bottom sheet) | [M10Bastidores](./canvas/M10Bastidores.dc.html) | §4 mobile |

### Produto final (390 × 844) · fora do prompt

Telas novas, interativas no canvas, mostrando o que a jornada entrega depois
da conversa.

| Frame | Arquivo |
|---|---|
| P1 · Sua jornada virou um plano | [P1Encerramento](./canvas/P1Encerramento.dc.html) |
| P2 · Meu plano (casa do objetivo) | [P2MeuPlano](./canvas/P2MeuPlano.dc.html) |
| P3 · Trilha mês a mês | [P3Trilha](./canvas/P3Trilha.dc.html) |
| P4 · Resumo, fontes e autorizações | [P4Resumo](./canvas/P4Resumo.dc.html) |
| P5 · Check-in do dia 5 | [P5CheckIn](./canvas/P5CheckIn.dc.html) |

### Estados de borda (390 × 844) · §7

| Frame | Arquivo |
|---|---|
| E1 · Guardrail | [E1Guardrail](./canvas/E1Guardrail.dc.html) |
| E2 · Promessa de crédito | [E2PromessaCredito](./canvas/E2PromessaCredito.dc.html) |
| E3 · Ferramenta indisponível | [E3FerramentaErro](./canvas/E3FerramentaErro.dc.html) |
| E4 · Dados insuficientes | [E4DadosInsuficientes](./canvas/E4DadosInsuficientes.dc.html) |
| E5 · Streaming / carregando | [E5Streaming](./canvas/E5Streaming.dc.html) |

### Telão / web (1440 × 1024) · secundária

| Frame | Arquivo |
|---|---|
| F1 · Boas-vindas | [Main](./canvas/Main.dc.html) |
| F2 · OBJETIVO | [F2Objetivo](./canvas/F2Objetivo.dc.html) |
| F3 · ENTENDER | [F3Entender](./canvas/F3Entender.dc.html) |
| F4 · ANTECIPAR | [F4Antecipar](./canvas/F4Antecipar.dc.html) |
| F5 · ORIENTAR | [F5Orientar](./canvas/F5Orientar.dc.html) |
| F6 · AGIR, consentimento | [F6Agir](./canvas/F6Agir.dc.html) |
| F6b · AGIR, plano | [F6bPlano](./canvas/F6bPlano.dc.html) |
| F7 · ACOMPANHAR | [F7Acompanhar](./canvas/F7Acompanhar.dc.html) |

### Modo escuro

[M5Escuro](./canvas/M5Escuro.dc.html), [M6Escuro](./canvas/M6Escuro.dc.html)
e [F5Escuro](./canvas/F5Escuro.dc.html). São os frames claros reaproveitados
com `tema="escuro"`; os tokens escuros estão em
[`bussola.css`](./canvas/bussola.css) (`.tokens.dark`).

## Sistema

| Peça | Arquivo | Conteúdo |
|---|---|---|
| Folha de tokens | [Tokens](./canvas/Tokens.dc.html) | Ambiente por estado, vidro em 3 níveis, cores, tipografia, raios, blur, handoff Tailwind |
| Folha de componentes | [Componentes](./canvas/Componentes.dc.html) | Tags, ChipFonte, SeloSintetico, botões, LinhaFerramenta/ErroFerramenta, StepperJornada, CardCenario, CardConsentimento, mensagens, DivisorMes, AlertaGuardrail, Open Finance |
| Handoff | [Handoff](./canvas/Handoff.dc.html) | Componente → evento do agente → origem do dado → estados |
| CSS base | [bussola.css](./canvas/bussola.css) | Implementação completa dos tokens (claro e escuro) e das classes usadas nos frames |
| Componentes reusados | [HeaderBussola](./canvas/HeaderBussola.dc.html), [StepperJornada](./canvas/StepperJornada.dc.html), [MTopo](./canvas/MTopo.dc.html) | Header desktop, stepper de 6 waypoints, topo mobile com indicador compacto `3/6 · Antecipar` |
| Layout do canvas | [canvas.json](./canvas/canvas.json) | Posição e título de cada frame |

Os nomes de componente seguem a §5 do prompt e aparecem como `aria-label`
nos cards dos frames (`CardDiagnostico`, `CardConsentimento`…), o que ajuda a
mapear cada um a um evento do agente.

## Lacunas conhecidas

- **`--animate-drift`** no `@theme` aponta para `@keyframes drift`, que não
  existe. O `bussola.css` usa `drift1`, `drift2` e `drift3`, um por blob. O
  [`tailwind-theme.css`](./tailwind-theme.css) traz os três.
- **F7b** (oportunidade) e os **estados de borda** só existem no app, sem
  versão 1440.
- **Modo escuro** cobre só cenários e consentimento (M5, M6, F5).
- **Sem exportações PNG.** Para o Obsidian ou a apresentação, exporte pelo
  canvas (Share › Export).

## Atualizar o snapshot

Quando o canvas mudar, baixe de novo os arquivos de `project/` para
`canvas/` e atualize a versão no topo deste arquivo. O canvas continua sendo
a fonte da verdade; não edite os `.dc.html` aqui.
