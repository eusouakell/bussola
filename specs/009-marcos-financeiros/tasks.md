---

description: "Tarefas do ciclo 009 — marcos financeiros intermediários"
---

# Tasks: Marcos financeiros intermediários

**Input**: `specs/009-marcos-financeiros/` (spec.md, plan.md, research.md,
data-model.md, contracts/, questoes.md)

**Tests**: obrigatórios (constituição IX e critérios AC-01..AC-18). A engine
nasce por TDD: o teste do comportamento vem antes da implementação.

**Organização**: por fase e por história (US1..US4 de [spec.md](./spec.md)).

## Format: `[ID] [P?] [Story] Descrição`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência).
- **[aguarda Sx]**: depende de ciclo não mergeado; **não** é implementada
  neste run ([pessoa-b §1.5](../../docs/ciclos/pessoa-b-agente-plataforma.md)).

---

## Fase 1: Contrato (bloqueia todo o resto) — commit `contracts:`

**Purpose**: publicar a interface antes de qualquer implementação. Tudo
aditivo; nada é removido ou renomeado (AC-18).

- [x] T001 `mcp_server/bussola_mcp/contratos.py`: acrescentar
      `EntradaPlanejarMarcos`, `RegrasMarco`, `ContextoFinanceiro`, `Motivo`,
      `Marco`, `DadosPlanejarMarcos`, mais as entradas de `planejar_marcos` em
      `FERRAMENTAS` e `TABELAS_FERRAMENTA` (campos e defaults em
      [data-model.md](./data-model.md)). Não tocar `FERRAMENTAS_P0`,
      `FERRAMENTAS_MOCK` nem `FERRAMENTAS_GOLDEN`.
- [x] T002 [P] `agent/bussola_agent/estado.py`: `CHAVE_MARCOS = "marcos"`,
      entrada em `CHAVES` e `estado_inicial` (`None`).
- [x] T003 [P] `agent/bussola_agent/extensoes.py`: `"bussola_agent.marcos"` em
      `PACOTES_EXTENSAO` e ordens 90–99 na docstring.
- [x] T004 [P] `docs/ciclos/contratos.md`: §1 (caminhos do 009), §5 (linha de
      `planejar_marcos` + `TABELAS_FERRAMENTA`), §6 (chave `marcos`, ordens
      90–99).
- [x] T005 Ajustar os testes de contrato que enumeram chaves e ferramentas
      (`agent/tests/contrato/test_estado.py`,
      `mcp_server/tests/contrato/test_contratos.py`,
      `mcp_server/tests/contrato/test_politicas_repo.py` se ele listar
      caminhos), mantendo as listas fechadas — só com o item novo.
- [ ] T006 Commit `contracts: ferramenta planejar_marcos e chave marcos`
      (T001–T005 juntos), para a revisão da Pessoa A ficar isolada.
      **Pendente:** as mudanças estão na árvore de trabalho, sem commit, à
      espera da decisão da Pessoa B sobre a divisão dos commits.

---

## Fase 2: Engine determinística (US1, US2, US3) — TDD

**Purpose**: o cálculo, puro e testado, em `mcp_server/bussola_mcp/dominio/marcos.py`.

- [x] T007 [US1] `mcp_server/tests/marcos/test_engine.py`: casos dos 8 motivos
      (um por código), cada um com `observado`/`limite` esperados, e o caso
      "objetivo cabe" com `motivos == []` e `marcos == []` (AC-01, AC-02).
- [x] T008 [US1] `dominio/marcos.py`: `meses_para`, `aporte_para`,
      `contexto_de_perfil` (médias, mediana, meses negativos, saldo atual,
      juros médios, parcelas ativas, comprometimento, dados ausentes)
      ([research.md](./research.md) R1, R2).
- [x] T009 [US1] `dominio/marcos.py`: `diagnosticar` com os 8 motivos e as
      frases de explicação determinísticas.
- [x] T010 [US2] `test_engine.py`: priorização — dívida cara antes de reserva,
      reserva antes de acumulação, fluxo negativo antes de tudo, e nenhum marco
      de nível posterior como próximo quando há gatilho anterior (AC-03, AC-04,
      AC-05); dois perfis com o mesmo objetivo e próximos marcos de tipos
      diferentes (AC-13).
- [x] T011 [US2] `dominio/marcos.py`: geradores por tipo de marco
      (`EQUILIBRAR_FLUXO`, `REDUZIR_DIVIDA_CARA`, `FORMAR_RESERVA` com alvo
      parcial, `ACUMULAR_PARTE_DA_META`, `AUMENTAR_CAPACIDADE`,
      `AJUSTAR_PRAZO`) e `planejar` (ordem, `proximo`, `max_marcos`, piso de
      materialidade) — regras na tabela de [data-model.md](./data-model.md).
- [x] T012 [US3] `test_engine.py`: `trajetoria_incerta` com só o próximo marco
      (AC-07, FR-024); ressalvas presentes; varredura léxica das nove
      proibições sobre **todas** as frases geradas em todos os casos (AC-08,
      [research.md](./research.md) R7); avisos de dado ausente sem marco
      correspondente (AC-09); valores BRL com 2 casas e prazos inteiros
      (AC-06).
- [x] T013 [US3] `dominio/marcos.py`: ressalvas, `trajetoria_incerta`, avisos e
      arredondamento BRL.
- [x] T014 [US1] `test_engine.py`: determinismo — duas execuções com a mesma
      entrada produzem saída idêntica; nenhuma chamada a hora corrente ou
      aleatoriedade (FR-018).

---

## Fase 3: Ferramenta MCP (US1)

- [x] T015 [US1] `mcp_server/bussola_mcp/ferramentas/__init__.py` e
      `planejar_marcos.py`: validar entrada, checar usuário, ler
      `perfil_mensal` e `parcelas`, chamar a engine, montar envelope
      `dados`/`fonte`/`avisos` (contrato em
      [contracts/planejar_marcos.md](./contracts/planejar_marcos.md)).
- [x] T016 [US1] `mcp_server/tests/marcos/test_ferramenta.py`: envelope
      completo com `RepositorioFake`, `fonte.ferramenta`, `fonte.tabelas` só
      com `dataset.tabela`, `fonte.periodo.fim == ate_anomes`, avisos fixos
      (AC-10); varredura por `SELECT`, `batalha-time-07`, `googleapis` e
      `Bearer` na saída.
- [x] T017 [US1] `test_ferramenta.py`: um caso por código de erro —
      `ENTRADA_INVALIDA` (UUID, `ate_anomes`, `valor_alvo`, `prazo_meses`,
      `prioridade` longa, parâmetro extra), `USUARIO_INEXISTENTE`,
      `DADOS_INSUFICIENTES`, `INDISPONIVEL` (repositório que lança) — com a
      mensagem citando só nomes de campo (AC-11, AC-12); escopo: o id do
      controle nunca devolve números do âncora.
- [x] T018 [US1] Log JSON pela lista de permitidos (`ferramenta`,
      `latencia_ms`, `erro_codigo`, `ate_anomes`), com teste de que
      `prioridade` não é logada.

---

## Fase 4: Agente (US1, US3)

- [x] T019 [US1] `agent/bussola_agent/marcos/instrucao.py`: trecho de prompt
      (ordem 90) com quando chamar a ferramenta, os 5 blocos dentro de
      Diagnóstico / Simulação / Recomendação (Q-009-6), as 9 proibições e a
      regra de citar a fonte de cada número (AC-14).
- [x] T020 [US1] `agent/bussola_agent/marcos/registro.py`: callback `after_tool`
      de ordem 30 que grava `session.state["marcos"]` com o `dados` do envelope
      de `planejar_marcos` (AC-15). **Sem ferramenta ADK local**: o nome
      colidiria com a ferramenta MCP homônima exposta pelo `McpToolset`
      ([research.md](./research.md) R8).
- [x] T021 [US1] `agent/bussola_agent/marcos/__init__.py`: registrar instrução
      (ordem 90) e callback (ordem 30) por `extensoes`/`callbacks`, sem tocar
      `agent.py`.
- [x] T022 [US1] `agent/tests/marcos/test_extensao.py`: instrução visível em
      `extensoes.instrucoes()` com os 5 blocos e as proibições, callback
      registrado na ordem 30, `state` gravado a partir de um envelope, envelope
      de erro e outras ferramentas não gravam `state`, e o callback nunca
      substitui o resultado da ferramenta.

---

## Fase 5: Front (US4)

- [x] T023 [P] [US4] `web/src/sessao/catalogo.ts`: entrada `planejar_marcos`
      (`legivel`, `tag: "recomendacao"`, `card: "CardMarcos"`).
- [x] T024 [US4] `web/src/componentes/cards/CardMarcos.tsx`: situação atual,
      próximo marco em destaque, trajetória, ressalvas, `CabecalhoCard`
      (com `ChipFonte`) e `Avisos`; leitura defensiva por `cards/ler.ts`, sem
      recalcular nada (AC-16).
- [x] T025 [US4] `web/src/componentes/conversa/Conversa.tsx`: `case
      "CardMarcos"` no `switch` de cards.
- [x] T026 [US4] `web/src/componentes/cards/CardMarcos.test.tsx`: envelope →
      card (trajetória, destaque, chip, ressalva) e `erro.codigo` →
      `ErroFerramenta`.

---

## Fase 6: Gates e fechamento

- [x] T027 `make lint`, `make test` e `npm --prefix web test -- --run` verdes;
      `npm --prefix web run build` sem erro (AC-17).
- [x] T028 `specs/009-marcos-financeiros/traceability.md` exportada da
      rastreabilidade do Spec Master.
- [x] T029 Revisão final do commit `contracts:` (aditividade, nenhuma lista
      afrouxada, mapa §1 coerente com os arquivos criados) (AC-18).

---

## Bloqueadas por dependência (não implementar neste run)

- [ ] T030 [aguarda S3] Registrar `planejar_marcos` no `server.py` real e
      acrescentar a ferramenta a `FERRAMENTAS_MOCK`/`FERRAMENTAS_GOLDEN`, com
      golden `planejar_marcos__ate_202506.json` e `__ate_202512.json` em
      `contracts/fixtures/ferramentas/` (o `server.py` de hoje é o mock do
      000, caminho do 000/003).
- [ ] T031 [aguarda S4] Integrar a instrução ao prompt base do 004 e incluir
      uma pergunta de marcos no eval de números (`eval/agente/perguntas.yaml`).
- [ ] T032 [aguarda S1] Trocar `meses_para`/`aporte_para` por
      `dominio.simulacao` e `contexto_de_perfil` por `dominio.metricas`,
      mantendo os testes da Fase 2 verdes.
- [ ] T033 [aguarda S4] Fixture de eventos SSE com `planejar_marcos` para o
      modo simulado do front (`web/src/simulado/`), se a demo pedir.

---

## Dependências

```text
T001..T006 (contrato)
        ↓
T007..T014 (engine, TDD)  →  T015..T018 (ferramenta)
        ↓                            ↓
T019..T022 (agente)          T023..T026 (front, [P] entre si)
        ↓
T027..T029 (gates)
```

- T002, T003, T004 são paralelos entre si (arquivos diferentes).
- T023 é paralela a T024 e T026 até o `case` de T025.
- Nenhuma tarefa da Fase 2 começa antes de T006, porque os modelos vivem em
  `contratos.py`.

---

## Situação no fim do run (2026-09-26)

- **Feitas:** T001–T005 e T007–T029.
- **Pendente de decisão humana:** T006 (dividir os commits `contracts:` e
  `feat:`), porque o Spec Master não faz commit sem pedido explícito.
- **Bloqueadas por dependência:** T030 `[aguarda S3]`, T031 e T033
  `[aguarda S4]`, T032 `[aguarda S1]`.
- **Gates:** `make lint`, `make test` (532 + 175), `make web-test` (253),
  `make web-lint` e `make web-build` verdes, todos com `BUSSOLA_FAKES=TRUE`,
  sem rede e sem GCP.
