# Feature Specification: Acompanhamento com replay temporal

**Feature Branch**: `006-acompanhamento-replay`

**Created**: 2026-09-26

**Status**: Implementada (aguarda 001, 003, 004 e 005 em `main` para o gate)

**Input**: `docs/ciclos/006-acompanhamento-replay.md` (F6). Formatos:
`docs/ciclos/contratos.md` §3, §5, §6, §8 e §9. Formato das respostas:
`web/src/simulado/locais.ts` (o front já exibe `avancar_mes`,
`status_plano` e `ajustar_plano` no modo simulado).

## Clarifications

### Session 2026-09-26

Resolvidas sem perguntar ao usuário (regra do ciclo). Classificação entre
parênteses.

- Q: Onde ficam a linha de base e o início do plano? → A: numa chave nova e
  aditiva do state, `acompanhamento_contexto`, que só o 006 escreve. O
  documento do ciclo já diz "calculada no primeiro avanço e guardada no
  state". Commit `contracts:` só de documentação. (RESOLVABLE_FROM_CONTEXT)
- Q: `Plano` não tem campo de metadados para apontar o plano anterior. → A:
  a referência vai no `resumo` do evento `plano_ajustado`
  (`plano_anterior_id`). O DDL de `planos` não muda. (SAFE_DEFAULT)
- Q: O mock devolve sempre o golden de `simular_objetivo` (30 mil em 24
  meses). → A: a rota usa a resposta do MCP só quando ela corresponde à
  entrada (valor e prazo ou aporte). Se não corresponder, aplica a mesma
  regra do golden (rendimento 0) numa função pura testada, com a
  `capacidade_mensal` devolvida pelo MCP, e acrescenta um aviso. Com o 003
  real, a resposta corresponde e a regra local não entra. (SAFE_DEFAULT)
- Q: O modelo passa números para `ajustar_plano`? → A: não precisa. O
  parâmetro aditivo `rota` ("A" ou "B") escolhe uma rota guardada. Se vierem
  `aporte_mensal` e `prazo_meses`, eles precisam bater com uma rota guardada.
  (SAFE_DEFAULT, princípio I)
- Q: E se `resumo_mes` falhar no avanço? → A: o avanço é atômico. O corte só
  muda depois que o mês é revelado com sucesso; em erro, o state fica como
  estava. (SAFE_DEFAULT)
- Q: Regra do acumulado, tolerância e linha de base? → A: as do documento do
  ciclo (INFERRED), iguais às do front simulado. O acumulado é a soma dos
  `realizado` positivos dos meses do mesmo objetivo, incluindo os planos
  ajustados. (INFERRED)
- Q: Replay de mais de um mês (item 4 da linha de corte)? → A: não é
  cortado. Cada chamada avança exatamente um mês, até 202512. (EXPLICIT)

## User Scenarios & Testing

### US1: avançar o mês e entender o resultado (P1)

Com plano ativo, o cliente diz "avançar um mês". O Bússola revela o mês
seguinte e compara a sobra com o aporte planejado. Em caso de desvio, diz
qual categoria pesou mais.

**Acceptance**:

1. Plano de 60 mil em 24 meses (aporte 2.500) criado em 202506, com
   `avancar_mes` → `ate_anomes` 202507, realizado 884,53, desvio −1.615,47,
   status `desvio` e categoria Viagens.
2. Com `ate_anomes` 202512 → `FIM_DO_REPLAY`, e o state não muda.
3. Sem `plano_id` → `SEM_PLANO_ATIVO`.
4. Nenhuma resposta traz dado depois do novo corte.

### US2: rota recalculada e ajuste com consentimento (P1)

No desvio, o Bússola propõe a rota A (manter o prazo) e a rota B (manter o
aporte). O plano só muda depois do "sim".

**Acceptance**:

1. 202507 do cenário acima → A: 2.570,24 por 23 meses (total 24); B: 2.500
   por 24 meses (total 25).
2. `ajustar_plano` sem consentimento `aceito` → `CONSENTIMENTO_NECESSARIO`,
   e nada é gravado.
3. Com consentimento → nova versão em `planos` (novo `plano_id`), state
   atualizado e evento `plano_ajustado` com `plano_anterior_id`.

### US3: status do plano (P2)

"Ver status do plano" mostra o plano vigente, os meses decorridos, o
acumulado, o percentual, o restante, o último status e o histórico.

## Requirements

### Functional Requirements

- **FR-001**: `avancar_mes()` (livre) valida o escopo, depois o plano
  (`SEM_PLANO_ATIVO`), depois o fim do replay (`FIM_DO_REPLAY`). Em seguida
  avança um mês, com virada de ano, e busca `resumo_mes(anomes=novo corte)`
  via `mcp_conexao.chamar_ferramenta`. O modelo não escolhe argumentos.
- **FR-002**: Corte temporal. O novo `ate_anomes` vale para todas as
  ferramentas seguintes, e nenhuma resposta traz período ou mês acima dele.
- **FR-003**: `desvio.py` é puro. Calcula planejado, realizado, desvio
  (`realizado − planejado`) e tolerância (10% do planejado). O status é
  `desvio` abaixo da faixa, `folga` acima e `no_plano` dentro dela, com o
  limite incluído.
- **FR-004**: A categoria do desvio é a macro com o maior aumento positivo
  contra a linha de base. A linha de base é a média por macro de 202501 até
  o início do plano (mês ausente conta 0), calculada no primeiro desvio e
  guardada no state. É nula fora de `desvio`.
- **FR-005**: Progresso, com funções puras:
  - acumulado = soma dos realizados positivos;
  - restante = `max(valor_alvo − acumulado, 0)`;
  - percentual;
  - meses decorridos e meses restantes.
- **FR-006**: Rotas, só no `desvio`:
  - A: `simular_objetivo(restante, prazo_meses=meses_restantes)`, se houver
    meses restantes;
  - B: `simular_objetivo(restante, aporte_mensal=aporte)`.

  Cada rota traz `id, titulo, descricao, aporte_mensal, prazo_meses,
  prazo_total_meses, simulacao` (envelope com `fonte`).
- **FR-007**: `ajustar_plano(aporte_mensal, prazo_meses, rota)` é registrada
  como sensível.
  - Sem o 005 carregado, uma guarda local exige consentimento `aceito`.
  - Com consentimento: grava um novo `Plano`, atualiza `plano_id` e o
    contexto e limpa as rotas.
- **FR-008**: `status_plano()` (livre) segue o formato do front.
- **FR-009**: Persistência pela porta `RegistroApp`:
  - linhas `acompanhamento`;
  - `planos`;
  - eventos `acompanhamento_mes_avancado`, `desvio_detectado`,
    `rota_recalculada` e `plano_ajustado`.

  No modo fake, usa `RegistroEmMemoria`.
- **FR-010**: State:
  - `ate_anomes`;
  - `estado_jornada` = `ACOMPANHAR`;
  - `acompanhamento` (lista de `{plano_id, anomes, planejado, realizado,
    desvio, status, categoria_desvio}`);
  - `acompanhamento_contexto`.

  Todas as escritas reatribuem a chave.
- **FR-011**: Instruções nas ordens 70–89, em pt-BR:
  - comandos do front ("avançar um mês", "Ver status do plano", "Quero
    adotar a rota X");
  - três blocos rotulados;
  - folga sem pressão;
  - aviso de simulação sobre dados históricos;
  - o modelo nunca calcula.
- **FR-012**: Registro por `extensoes` no `__init__.py`, idempotente, sem
  editar `agent.py`.
- **FR-013**: Logs JSON só com campos de §9. Sem prompt nem texto de
  lançamentos.
- **FR-014**: Eval offline em `eval/acompanhamento/`: 202506 → 202509 com
  desvio, recálculo, ajuste e auditoria (o roteiro implementado vai até
  202512 e cobre também `FIM_DO_REPLAY` e os casos de borda).
- **FR-015**: Testes de unidade e de integração (`InMemoryRunner` + LLM fake
  roteirizado + MCP fake no transporte), todos offline no `make test`.
- **FR-016**: Os testes de contrato do 000 continuam descrevendo o agente
  sem extensões, mesmo com o pacote real presente (commit `contracts:`).

### Key Entities

- **Plano vigente**: `plano_id, cenario, valor_alvo, aporte_mensal,
  prazo_meses, criado_em_anomes, inicio_anomes` (+ `objetivo`, interno).
- **Resultado mensal**: a linha do state e da tabela `acompanhamento`.
- **Rota**: A ou B, com a simulação que a sustenta.

## Success Criteria

- **AC-01** (§6.1): corte avança de 202506 para 202507, e o teste de corte
  temporal passa.
- **AC-02** (§6.2): planejado contra realizado, com a categoria
  identificada.
- **AC-03** (§6.3): o desvio gera rotas, e o ajuste passa pelo
  consentimento.
- **AC-04** (§6.4): acompanhamento, planos e auditoria gravados.
- **AC-05** (§6.5): testes sem LLM:
  - limites de 10%;
  - virada de ano;
  - `FIM_DO_REPLAY` e `SEM_PLANO_ATIVO`;
  - acumulado e restante;
  - ajuste bloqueado;
  - conversa fake de 202506 a 202508.
- **AC-06** (§6.6): eval executado, com `eval/acompanhamento/resultado.md`.

## Assumptions

- O 005 põe `plano_id` no state ao criar o plano e grava em `planos` com o
  `ate_anomes` da criação.
  - Enquanto o registro do 005 não estiver ligado ao do 006, o plano é
    derivado do state (`objetivo` + `cenarios` + `cenario_escolhido`).
- O catálogo do 005 classifica `avancar_mes` e `status_plano` como livres e
  `ajustar_plano` como sensível.
- O consentimento é consumido depois da execução da ação (documento do
  005).
