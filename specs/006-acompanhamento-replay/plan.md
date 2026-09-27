# Implementation Plan: Acompanhamento com replay temporal

**Branch**: `006-acompanhamento-replay` | **Date**: 2026-09-26 | **Spec**:
[spec.md](spec.md)

## Summary

Pacote `agent/bussola_agent/acompanhamento/`, carregado por
`extensoes.carregar_extensoes()`, que registra:

- `avancar_mes` e `status_plano` (livres);
- `ajustar_plano` (sensível);
- as instruções nas ordens 70–89.

Os números vêm de `resumo_mes` e `simular_objetivo` (MCP, via
`mcp_conexao.chamar_ferramenta`) e de funções puras testadas. O modelo não
calcula. A persistência passa pela porta `RegistroApp`.

## Technical Context

- **Stack**: Python 3.12, Google ADK 2.10, pydantic 2 e `uv`.
- **Testes**: pytest com `asyncio_mode=auto`, todos offline com
  `BUSSOLA_FAKES=TRUE`. A integração usa `InMemoryRunner` do ADK, um
  `BaseLlm` roteirizado e o MCP fake no transporte (`_chamar_mcp`
  substituído).
- **Restrições**:
  - não importar `mcp_server`;
  - não editar `agent.py`, `governanca/`, `jornada/` nem `web/`;
  - não mudar código de contrato, exceto pelo commit `contracts:` isolado
    (abaixo).

## Constitution Check

| Princípio | Como o 006 atende |
|---|---|
| I. Números determinísticos | `desvio.py`, `progress.py` e `routes.py` são puros e testados. As rotas vêm do MCP ou da regra do golden, documentada. `ajustar_plano` escolhe rota por id. |
| II. Escopo e SQL | Sem SQL. Escopo sempre do `state` (`aplicar_escopo`). O novo corte é validado (≤ 202512). |
| IV. Rótulos | A instrução pede três blocos: diagnóstico, por que aconteceu e o que fazer (simulação/recomendação). |
| V. Consentimento | `ajustar_plano` é sensível (gate do 005), com guarda local enquanto o 005 não está carregado. |
| VIII. Nomes | Nomes de contrato em pt (`avancar_mes`, `desvio.py`, chaves). Módulos internos novos em inglês técnico, consistentes por módulo. Sem conflito. |
| IX. Logs | `logging_json`, só com campos de §9. |
| X. Contratos | Dois commits `contracts:` aditivos e sinalizados (abaixo). |

Sem conflito com a constituição, então não há `proposta-constituicao.md`.
Nada da linha de corte foi usado, então não há `corte.md`.

## Design

```text
agent/bussola_agent/acompanhamento/
  __init__.py      register() idempotente (ferramentas + instruções); FREE_TOOLS, SENSITIVE_TOOLS
  desvio.py        TOLERANCE, compute_deviation, baseline_by_macro, deviation_category
  money.py         money() (half-up, 2 casas), format_brl, format_months (texto pt-BR)
  periods.py       next_month, months_between, month_range
  progress.py      accumulated, compute_progress (acumulado, restante, percentual, meses)
  routes.py        simulate_locally, response_matches, resolve_simulation, build_routes
  ports.py         McpGateway (Protocol), McpToolGateway, configure/get gateway e registry, reset
  plan_context.py  ActivePlan, resolve_active_plan (contexto > registro > state), lineage, history_for
  envelopes.py     códigos e mensagens de erro/aviso pt-BR, error(), within_cut()
  audit.py         record_event, record_follow_up, suggested_action (logs só com campos §9)
  tools.py         avancar_mes, status_plano, ajustar_plano
  instructions.py  INSTRUCTIONS [(ordem, texto)], ordens 70, 75, 80 e 85
  fakes.py         FixtureMcp (espelho do mock), FixtureMcpGateway, fake_transport, ScriptedLlm,
                   jornada simulada do 004/005 (escopo, solicitar_consentimento, gate) e o
                   harness Conversation/build_conversation usado pela integração e pelo eval
```

### Fluxo de `avancar_mes`

1. Escopo do state (`ENTRADA_INVALIDA`).
2. Plano ativo (`SEM_PLANO_ATIVO`).
3. `ate_anomes == 202512` → `FIM_DO_REPLAY`.
4. `resumo_mes(anomes=novo)` com uma cópia do state já no novo corte. Em
   erro, devolve o erro, e o state não muda.
5. Grava o novo `ate_anomes`. Calcula desvio e progresso. No desvio, calcula
   a categoria (linha de base guardada) e as rotas.
6. Grava eventos (`acompanhamento_mes_avancado`, `desvio_detectado`,
   `rota_recalculada`) e a linha `acompanhamento`. Passa a jornada para
   `ACOMPANHAR` e atualiza `acompanhamento` e `acompanhamento_contexto`.
7. Devolve o envelope no formato do front, com `fonte.periodo` = novo mês.

### Plano ativo (`plan_context`)

A ordem de resolução é:

1. o snapshot em `acompanhamento_contexto.plano_vigente`, se o `plano_id`
   bater;
2. `registro.obter_plano(plano_id)`;
3. derivação do state: `objetivo.valor_alvo` + o cenário escolhido em
   `cenarios` (aporte e prazo). Serve enquanto o registro do 005 não estiver
   ligado.

O início do acompanhamento é o `ate_anomes` da criação do plano. Os planos
ajustados herdam o início da linhagem.

### Rotas

- A = manter o prazo; B = manter o aporte.
- A resposta do MCP é usada quando corresponde à entrada.
- Se não corresponder (o mock sempre devolve o golden), usa
  `simulate_locally` com a `capacidade_mensal` do MCP, a mesma regra do
  golden (rendimento 0), mais um aviso.
- Um erro de envelope pula a rota, com aviso.

### Contratos (commits separados, sinalizados)

- **A**, `contracts: isola pacotes de extensão reais nos testes do agente`:
  - fixture autouse no `agent/tests/conftest.py` que esconde os pacotes reais
    de `find_spec`/`sys.modules`, a menos que o teste tenha o marcador
    `extensoes_reais`;
  - `criar_extensao` põe o diretório temporário na frente;
  - marcador no `agent/pyproject.toml`;
  - nota em contratos §6.

  Sem isso, os testes do 000 quebram quando o pacote real existe.
- **B**, `contracts: chave acompanhamento_contexto no session.state`: só
  documentação (contratos §6). É uma chave nova, aditiva, que só o 006
  escreve.

## Testing Strategy

- **Unidade**:
  - limites de 10%, virada de ano, meses entre, dinheiro;
  - linha de base e categoria, acumulado e restante;
  - rotas: MCP correspondente, fallback, erro, restante 0;
  - resolução do plano;
  - ferramentas com o gateway fake;
  - escopo do adaptador real (`_chamar_mcp` substituído);
  - registro com o marcador `extensoes_reais`.
- **Integração**:
  - `InMemoryRunner` com o LLM roteirizado, de 202506 a 202509, incluindo o
    texto `"avançar um mês"` do front e o pedido de status;
  - escopo (004) e gate/consentimento (005) simulados em `fakes.py`;
  - corte temporal verificado em todos os envelopes;
  - fidelidade: todo número citado no texto final aparece em algum envelope
    do turno.
- **Eval**: `eval/acompanhamento/rodar_eval.py` (`make eval-acompanhamento`)
  cobre de 202506 a 202512 e os casos de borda, e gera `resultado.md` e
  `RESULTADOS.md`. `tests/acompanhamento/test_acomp_eval.py` roda a mesma
  função em `make test`.
