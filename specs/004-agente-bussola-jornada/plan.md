# Plano 004: Agente Bússola e jornada

## 1. Contexto técnico

- Python 3.12, `uv`, Google ADK 2.10, google-genai 2.25, pytest-asyncio,
  ruff (100 colunas).
- Contratos congelados: `estado.py`, `callbacks.py`, `extensoes.py`,
  `mcp_conexao.py`, `logging_json.py`, `persistencia.py`, `contracts/`.
- MCP mock do 000 (`python -m bussola_mcp.server`, golden do âncora em
  `contracts/fixtures/`), sem dependência do 003.

## 2. Arquitetura (portas e adaptadores)

```text
agent/bussola_agent/
  agent.py                 # composição: root_agent (adaptador ADK)
  resilient_model.py       # cadeia Flash sem streaming (bug de produção)
  escopo.py                # callbacks: before_agent, before_tool 10, after_tool 10
  prompts/
    __init__.py            # build_instruction(extensions)
    base.py                # texto base pt-BR (persona, estados, regras)
    catalog.py             # catálogo curado embutido + render
  jornada/
    state_machine.py       # núcleo puro: JourneyFacts, advance()
    progress.py            # aplica o resultado de ferramenta ao state + logs
    tool_results.py        # extrai envelope §5 dos formatos do ADK/MCP
    tools.py               # registrar_objetivo, escolher_cenario (puras)
    number_check.py        # extração pt-BR, evidência, after_model 50
    annotations.py         # tag e recomendado (after_model 90)
    respostas_rapidas.py   # chips por jornada (after_model 90)
```

- **Núcleo puro** (`state_machine`, `number_check` na parte de extração e
  comparação, validação em `tools`): sem ADK, testado por unidade.
- **Adaptadores ADK** (`escopo`, `progress`, callbacks de `after_model`):
  leem o `session.state`/eventos e chamam o núcleo.
- **Ferramentas locais** só validam e devolvem envelope; quem grava no state
  é o `after_tool` (um ponto único de escrita da jornada).

## 3. Fluxo de um turno

1. `before_agent` (`escopo.initialize_session`) garante o escopo.
2. `before_model` (005, ordens 10/20).
3. Modelo chama ferramenta → `before_tool` 10 (`escopo.enforce_scope`)
   sobrescreve o escopo das MCP; 20 é o gate do 005; 90 auditoria.
4. `after_tool` 10 (`escopo.record_tool_result`): fonte → `ultimas_fontes`,
   `cenarios`, `objetivo`, `cenario_escolhido`, máquina de estados.
5. Resposta final → `after_model` 10 (guardrail 005), 50 (números), 90
   (tag/recomendado e respostas rápidas).

## 4. Máquina de estados

| De | Para | Guarda |
|---|---|---|
| OBJETIVO | ENTENDER | objetivo com `valor_alvo` e `prazo_meses` válidos |
| ENTENDER | ANTECIPAR | `perfil_financeiro` e `capacidade_poupanca` com sucesso (fontes) |
| ANTECIPAR | ORIENTAR | `cenarios` gravado por `comparar_cenarios` |
| ORIENTAR | AGIR | `cenario_escolhido` gravado por `escolher_cenario` |

As guardas são encadeadas (um único resultado pode avançar mais de um passo;
cada passo gera um log). Troca de objetivo reinicia em ENTENDER (D-02).

## 5. Testes

- Unidade: máquina, validação das ferramentas, extração de envelope,
  extração de números pt-BR, verificação, prompts, catálogo, chips, tag.
- Integração (ADK `InMemoryRunner`, SSE, LLM roteirizado):
  - escopo com o id do controle → MCP recebe o âncora;
  - jornada OBJETIVO → ORIENTAR (e AGIR) contra o mock MCP real em
    subprocesso local, com fontes, cenários, metadados e verificação.
- Eval (fora do `make test`): offline roteirizado e ao vivo com Gemini real
  (só prompts benignos; chave lida do Secret Manager na hora, nunca impressa).

## 6. Riscos

- **Formatação livre do modelo** (ex.: "R$ 1,7 mil"): o verificador aceita
  arredondamentos coerentes; o eval ao vivo mede o que sobra.
- **Gemini 503** no eval ao vivo: a cadeia resiliente cai para outro Flash.
- **003 ainda não mergeado:** a integração roda no mock; o gate de merge
  exige repetir a jornada contra o MCP real local.
