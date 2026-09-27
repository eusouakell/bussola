# Tasks — Ciclo 009: correções dos unhappy paths do MVP1

Ordenadas por dependência. `[P]` = pode rodar em paralelo com as demais `[P]`
da mesma onda (sem interseção de arquivos).

## Onda 0 — preparação

- [x] T000 Descoberta read-only e baseline dos 4 gates
      (`.spec-master/reports/discovery.md`)
- [x] T001 Contexto normalizado com classificação de fonte
      (`.spec-master/context/requisitos.md`)
- [x] T002 Investigação paralela das 7 falhas (5 agentes read-only)
- [x] T003 Adoção do Team Mode (`.spec-master/team/adoption-report.md`)

## Onda 1 — implementação paralela

### WS-1 · frontend-dev · `web/src/simulado/`, `web/src/agente/tipos.ts`

- [x] T100 [P] Acrescentar `"atividade_ilicita"` a `MotivoGuardrail` — FR-01
- [x] T101 [P] Regra de atividade ilícita em `REGRAS`, antes das demais, com
      proteção explícita para relato de vítima — FR-01
- [x] T102 [P] Contador de turnos fora de escopo e resposta escalonada em três
      níveis, sem repetição idêntica — FR-02
- [x] T103 [P] Intenção nova para perguntas de crédito/juros/financiamento — FR-02
- [x] T104 [P] Remover o early return de `agente-simulado.ts:290`; sempre
      registrar o objetivo pedido — FR-03
- [x] T105 [P] Viabilidade a partir de `capacidade_poupanca.sobra_mediana` e
      proposta de meta intermediária, com variação na insistência — FR-03
- [x] T106 [P] `lerValor` entende `milhao`/`milhoes`/`mi` — FR-03
- [x] T107 [P] Testes com as frases literais do relato

### WS-2 · backend-dev · `agent/bussola_agent/{governanca,prompts,jornada}`

- [x] T200 [P] Razão `atividade_ilicita` em `REASONS`/`MESSAGES` e regra em
      `_INPUT_RULES`, com proteção para relato de vítima — FR-01
- [x] T201 [P] `tool_config` com `FunctionCallingConfig(mode=ANY)` após o
      consentimento concedido — FR-04
- [x] T202 [P] Callback `after_model` que detecta afirmação de ação sem tool
      call no turno, com log estruturado seguro — FR-04
- [x] T203 [P] Reforço de prompt em `prompts/base.py` — FR-04
- [x] T204 [P] Testes

### WS-3 · backend-dev · mock, persona e fallback

- [x] T300 [P] Adaptador golden cai no cálculo de domínio para não-âncora;
      `DADOS_INSUFICIENTES` só quando não há nenhum mês — FR-05
- [x] T301 [P] Mesma regra no fake do agente — FR-05
- [x] T302 [P] Reescrever os 4 avisos de demonstração em linguagem de cliente,
      sem "mock", `valor_alvo=`, `prazo_meses=`, `anomes` cru — FR-06
- [x] T303 [P] Reescrever `CAPACITY_MESSAGE` — FR-07
- [x] T304 [P] Testes

### WS-4 · frontend-dev · apresentação de avisos

- [x] T400 [P] Dedup de avisos em `Avisos.tsx` — FR-06
- [x] T401 [P] Dedup de mensagens de erro em `BlocoAnalise.tsx` — FR-06
- [x] T402 [P] Dedup de `faltas` em `CardDiagnostico.tsx` — FR-06
- [x] T403 [P] Badge compacto para aviso de demonstração e supressão de jargão
      interno, com aviso de negócio preservado — FR-06
- [x] T404 [P] `Avisos.test.tsx` (não existia) e demais testes

## Onda 2 — integração (tech-lead)

- [x] T500 Reconciliar workstreams e resolver quebras fora do escopo de cada WS
- [x] T501 Evitar repetição do bloco de diagnóstico a cada renegociação de
      valor (apareceu só na integração, quando o early return saiu) — FR-06
- [x] T502 3 casos novos no eval de segurança: as duas frases ilícitas do
      relato e um relato de vítima que não pode bloquear (`eval/seguranca/casos.yaml`)
- [x] T503 Regerar `eval/acompanhamento/resultado.md` (51/51) e
      `eval/seguranca/resultado.md` (19/19)
- [x] T504 Sincronizar `docs/ciclos/contratos.md`: regra do mock para
      não-âncora, texto dos avisos de demonstração e ordens de callback novas
- [x] T505 `make lint` · `make test` · `make web-lint` · `make web-test`
- [x] T506 Rastreabilidade e relatório final
- [x] T507 Merge em `main` e push

## Roadmap (fora deste ciclo, decisão do PO)

- R1 Cliente com histórico real curto: hoje `DADOS_INSUFICIENTES` é tudo ou
      nada. Falta degradação graciosa com faixa de confiança.
- R2 Mover o tráfego do `bussola-mcp` das revisões `c000` para `main`
      (spec §6) — exige confirmação humana e é responsabilidade do ciclo 007.
