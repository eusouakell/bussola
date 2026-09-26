# Ciclo 006 — F6 Acompanhamento com replay temporal

> **Disparo:** `/spec-master docs/ciclos/006-acompanhamento-replay.md`, no
> Claude Code, dentro da worktree `../bussola-006`, na branch
> `006-acompanhamento-replay`.
>
> **Onda:** 3. **Prioridade:** P1 (linha de corte). **Spec:**
> `specs/006-acompanhamento-replay`. **Plano:** [README](./README.md).
>
> **Leitura obrigatória antes do Step 3:**
>
> - [contratos.md](./contratos.md) §3 (`acompanhamento`), §5 (`resumo_mes`,
>   `simular_objetivo`), §6 e §8.
> - Contexto mestre [§4 (ACOMPANHAR), §6, §10 F6 e §19](../contexto-spec-master.md).

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Uma única feature:** `id: acompanhamento-replay`,
   `spec_directory: specs/006-acompanhamento-replay`.
2. **Número fixo:** `SPECIFY_FEATURE_DIRECTORY=specs/006-acompanhamento-replay`.
3. **Step 2:** Spec Kit já inicializado. Estratégia Git **Trunk-Based**.
4. **Constituição congelada.** Proposta vai para
   `specs/006-*/proposta-constituicao.md`.
5. **Escreva só nos caminhos da §4.** Tudo entra no agente por
   `extensoes.registrar_ferramenta` e `registrar_instrucao` (ordens 70–89).
   Não edite o `agent.py` (004) nem a `governanca/` (005).
6. **Chamadas ao MCP são determinísticas:** use
   `mcp_conexao.chamar_ferramenta`, que já aplica o escopo. O LLM **não**
   escolhe os argumentos de `resumo_mes` no avanço de mês.
7. **Sem Cloud Scheduler nem notificação push** (mestre §6). O avanço de
   mês acontece na conversa.
8. **Desenvolvimento com o MCP mock** (`resumo_mes__<AAAAMM>.json`) e
   `RegistroEmMemoria` até 003, 004 e 005 estarem em `main`.
9. **Ao final:**
   - `make test` e `make lint` verdes;
   - rastreabilidade em `specs/006-*/traceability.md`.

## 2. Propósito

Fechar o ciclo da jornada (ACOMPANHAR): com o plano ativo, o usuário
"avança o mês" na demo e o Bússola:

1. compara o planejado com o realizado no mês revelado;
2. detecta o desvio e explica a causa (categoria);
3. propõe a rota recalculada;
4. só ajusta o plano com consentimento.

É a prova de agente proativo sem infraestrutura de agendamento.

## 3. Escopo e comportamento esperado

### 3.1 Ferramenta `avancar_mes()` (livre)

- **Pré-condições:**
  - `plano_id` presente no state; senão, erro local `SEM_PLANO_ATIVO` com
    orientação;
  - `ate_anomes < 202512`; senão, erro local `FIM_DO_REPLAY`.
- **Passos:**
  1. incrementa `ate_anomes` no state (AAAAMM, com virada de ano) e emite
     `acompanhamento_mes_avancado`;
  2. chama `resumo_mes(anomes = novo ate_anomes)` via `chamar_ferramenta`;
  3. calcula o desvio (3.2);
  4. grava a linha em `acompanhamento` via `RegistroApp` e devolve um
     resultado estruturado com a `fonte` do `resumo_mes`.
- **Transição:** o estado vai para **ACOMPANHAR** (vindo de AGIR ou do
  próprio ACOMPANHAR).
- **Escopo temporal:** o novo `ate_anomes` passa a valer para **todas** as
  ferramentas MCP seguintes (escopo do 004). O agente nunca "vê o futuro".

### 3.2 Desvio (`agent/bussola_agent/acompanhamento/desvio.py`, função pura)

- **`planejado`:** `aporte_mensal` do plano ativo (tabela `planos`, ou
  state).
- **`realizado`:** `sobra` do mês em `resumo_mes`.
- **`desvio`:** `realizado - planejado`.
- **`status`,** com tolerância de 10% do planejado (INFERRED):
  - `no_plano` se `|desvio| ≤ 10%`;
  - `desvio` se o realizado ficou abaixo da faixa;
  - `folga` se ficou acima.
- **`categoria_desvio`:** a macro com o maior aumento contra a linha de base.
  - A linha de base é a média por macro dos `resumo_mes` até o
    `ate_anomes` do momento da criação do plano.
  - Ela é calculada no primeiro avanço e guardada no state.
  - Com `status != desvio`, `categoria_desvio` é nulo.
- **Sem I/O e sem LLM:** 100% testável com os fixtures.

### 3.3 Rota recalculada

- Quando `status == desvio`, emite `desvio_detectado` e calcula duas
  alternativas com `simular_objetivo` via `chamar_ferramenta`:
  - **a) manter o prazo:** novo aporte para o valor restante no prazo
    restante;
  - **b) manter o aporte:** novo prazo.
- **Acumulado (INFERRED, ver §10):**
  - acumulado = soma dos `realizado` positivos desde a criação do plano;
  - valor restante = `valor_alvo - acumulado`;
  - prazo restante = `prazo_meses - meses decorridos`.
- Emite `rota_recalculada` e grava `rota_recalculada` em `acompanhamento`.
  O resultado traz as duas rotas com as `fonte`.

### 3.4 Ajuste do plano (sensível)

- **`ajustar_plano(aporte_mensal, prazo_meses)`:** registrada com
  `sensivel=True`. Passa pelo gate do 005, com consentimento explícito e de
  uso único.
- Com consentimento: grava a nova versão em `planos` (novo `plano_id`,
  referência ao anterior no campo de metadados) e atualiza o state.
  Evento `plano_ajustado`.
- Recusa: mantém o plano e registra.

### 3.5 Ferramenta `status_plano()` (livre)

- Devolve:
  - objetivo e plano ativo;
  - meses decorridos;
  - acumulado e percentual do objetivo;
  - último status;
  - lista de meses acompanhados.

### 3.6 Instruções (ordens 70–89)

- Em ACOMPANHAR, cada avanço de mês é contado em três blocos:
  1. **o que aconteceu no mês** (realizado contra planejado, com a fonte);
  2. **por quê** (categoria, com trecho do RAG se for útil);
  3. **o que fazer** (rotas a e b, e o pedido de consentimento para ajustar).
- Na folga: sugerir manter ou antecipar, sem pressão.
- Explicar que o "avanço do mês" é uma simulação sobre dados históricos.

### 3.7 Avaliação (`eval/acompanhamento/`)

- Roteiro com o âncora:
  1. plano criado em 202506 (objetivo de 60 mil em 24 meses);
  2. `avancar_mes` para 202507, 202508 e 202509;
  3. em cada mês, o status bate com `desvio.py` calculado sobre os
     fixtures;
  4. nenhuma ferramenta retorna dado depois do `ate_anomes` corrente.
- Resultado em `eval/acompanhamento/resultado.md`.

## 4. Propriedade (escreve só aqui)

- `agent/bussola_agent/acompanhamento/`
- `agent/tests/acompanhamento/`
- `eval/acompanhamento/`
- Acréscimos em `agent/pyproject.toml` e `Makefile`
- `specs/006-acompanhamento-replay/`

## 5. Contratos

- **Consome:**
  - `extensoes.py`, `mcp_conexao.chamar_ferramenta`, `estado.py`,
    `persistencia.RegistroApp` e `logging_json.py`;
  - ferramentas MCP `resumo_mes` e `simular_objetivo` (003);
  - gate e catálogo do 005 (`ajustar_plano` sensível);
  - estados da jornada (004);
  - fixtures `resumo_mes__<AAAAMM>.json`.
- **Provê:** as ferramentas `avancar_mes`, `status_plano` e `ajustar_plano`,
  os eventos `acompanhamento_*`, `desvio_detectado`, `rota_recalculada` e
  `plano_ajustado`, e as linhas em `bussola_app.acompanhamento`.

## 6. Critérios de aceite

- [ ] `avancar_mes()` move o corte do âncora (ex.: 202506 → 202507) e revela
      o mês seguinte. Nenhuma ferramenta retorna dado depois do corte
      (teste de corte temporal).
- [ ] Compara o planejado (aporte) com o realizado (sobra do mês) e
      identifica a categoria que causou o desvio.
- [ ] Em caso de desvio, propõe rota recalculada (novo aporte ou novo prazo)
      e pede consentimento antes de ajustar o plano.
- [ ] Acompanhamento e ajustes gravados em `bussola_app.acompanhamento` e
      `planos`, com eventos de auditoria.
- [ ] Testes sem LLM:
  - `desvio.py` (no plano, desvio, folga, limites exatos de 10%);
  - virada de ano no incremento;
  - `FIM_DO_REPLAY`;
  - `SEM_PLANO_ATIVO`;
  - acumulado e restante;
  - `ajustar_plano` bloqueado sem consentimento;
  - conversa roteirizada com LLM fake de 202506 a 202508.
- [ ] Eval de acompanhamento executado, com resultado em
      `eval/acompanhamento/resultado.md`.

## 7. Cenários de teste

- **Avanço sem plano:** `avancar_mes()` sem `plano_id` → `SEM_PLANO_ATIVO`,
  e o agente sugere criar o plano.
- **Avanço com plano:** plano com aporte de 2.000 em 202506, e
  `resumo_mes(202507).sobra` = 1.500 → `status = desvio`,
  `categoria_desvio` = macro com o maior aumento → duas rotas → pedido de
  consentimento.
- **Consentimento aceito:** "sim" → `ajustar_plano` grava a nova versão.
  Um novo `status_plano` mostra o aporte atualizado.
- **Fim do replay:** com `ate_anomes = 202512`, `avancar_mes()` →
  `FIM_DO_REPLAY`.
- **Corte temporal:** depois do avanço para 202507,
  `perfil_financeiro` considera meses até 202507, nunca 202508.

## 8. Dependências e gate de merge

- **Dependências duras:**
  - 000 (extensões, `chamar_ferramenta`, fixtures `resumo_mes`);
  - para o gate: 001, 003, 004 e 005 em `main`.
- **Gate de merge:**
  - roteiro 202506 → 202508 contra o MCP real (local), com o gate do 005
    ativo;
  - eval executado.

  Este é o **8º (último) na ordem de merge**.
- **Linha de corte:** se o prazo apertar, a demo usa só `avancar_mes` +
  desvio + rota (sem `ajustar_plano`), registrado em
  `specs/006-*/corte.md`.

## 9. Fora de escopo

- Cloud Scheduler, notificações push e jobs agendados (mestre §6).
- Rendimento do valor guardado (as `RegraCenario` do contrato usam 0).
- Canal e deploy (007).

## 10. Questões em aberto

- **Regra do acumulado:** "soma dos realizados positivos" é INFERRED. A
  alternativa é "soma do aporte planejado nos meses no plano ou em folga".
  Validar com o time antes do Step 5.
- A tolerância de 10% e a linha de base por média são INFERRED.
- **Mês inicial do replay (Q2 do mestre):** padrão 202506 (EXPLICIT via
  `REPLAY_START_ANOMES`).

## 11. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| `avancar_mes`, planejado contra realizado, categoria, rota e consentimento | Mestre §10 F6 | EXPLICIT |
| Sem Scheduler; replay na conversa | Mestre §6 | EXPLICIT |
| `resumo_mes` e `chamar_ferramenta` | `contratos.md` §5 e §6 | EXPLICIT |
| Tolerância de 10%, linha de base e regra do acumulado | Este ciclo | INFERRED |
| Mês inicial do replay | Mestre §20, Q2 | EXPLICIT (padrão) / UNRESOLVED (confirmação) |
