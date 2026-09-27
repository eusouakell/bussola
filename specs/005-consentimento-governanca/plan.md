# Implementation Plan: Consentimento, governança e auditoria

**Branch**: `005-consentimento-governanca` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)

## Summary

O ciclo entrega a autonomia governada do estado AGIR. Tudo entra no agente
pelos pontos de extensão do 000, sem editar o `agent.py`:

- catálogo livre/sensível;
- pedido, leitura determinística e gate de consentimento de uso único;
- ações sensíveis simuladas;
- auditoria mínima em `bussola_app`;
- guardrails de entrada e saída: regras determinísticas, mais Model Armor
  opcional atrás de uma porta;
- `RegistroBigQuery`;
- eval de segurança determinístico.

## Technical Context

- **Linguagem**: Python 3.12, `uv`, ADK 2.10 (`google-adk[mcp]`).
- **Dependências novas**: `google-cloud-bigquery` (adaptador BigQuery), `httpx`
  (adaptador Model Armor; já era transitiva) e `pyyaml` (dev, casos do eval).
- **Armazenamento**: `bussola_app` (produção) e `bussola_app_dev` (testes `bq`).
  Streaming insert, sem SQL montado por texto. A única consulta
  (`obter_plano`) usa `@plano_id`.
- **Testes**: pytest + pytest-asyncio, guarda de rede do 000. Integração com o
  `InMemoryRunner` e um `BaseLlm` roteirizado.
- **Restrições**: nada de rede no import. Registro, relógio e screener são
  criados sob demanda e trocáveis nos testes.

## Constitution Check

| Princípio | Como o plano cumpre | Status |
|---|---|---|
| I. Números de ferramentas | `criar_plano` copia aporte e prazo de `state.cenarios` (saída do `comparar_cenarios`). O LLM não calcula. | PASS |
| II. Agente isolado de SQL/infra | O guardrail de saída bloqueia SQL, o nome do projeto e credenciais. Erros saem como envelope sem detalhe interno. | PASS |
| III. Escopo por cliente | O `id_usuario` vem só do state (UUID v4). O guardrail bloqueia outro UUID na entrada e na saída. | PASS |
| IV. Respostas rotuladas | Ações devolvem envelope com `fonte`. | PASS |
| V. Logs seguros | Só `logging_json` com os campos de §9. O `resumo` da auditoria traz chaves e números, nunca texto livre. | PASS |
| VI. Consentimento auditado | Gate em `before_tool` 20, leitura determinística em `before_model` 20. Grava `consentimentos` + `auditoria`. | PASS |
| VII. Segredos | Model Armor e BigQuery usam ADC. Nada de chave no código ou em log. | PASS |
| VIII. pt-BR | Textos ao cliente em pt-BR. Identificadores internos novos em inglês técnico, consistentes por módulo (D3). | PASS |
| IX. Testes sem rede | Portas com fakes. Integração offline. Testes `bq` só em `bussola_app_dev`. | PASS |
| X. Contratos | Um commit `contracts:` aditivo (isolamento dos testes de contrato + campos opcionais em §6). | PASS (com PR `contracts:`) |

## Project Structure

```text
agent/bussola_agent/
├── persistencia_bq.py          # RegistroBigQuery + build_registry/default_registry
└── governanca/
    ├── __init__.py             # register(): ferramentas, instruções e callbacks
    ├── catalogo.py             # livres/sensíveis/bloqueadas; catálogo de produtos
    ├── catalogo_produtos.json  # cópia de contracts/catalogo_produtos.json
    ├── consent.py              # parser sim/não, solicitar_consentimento, leitura, gate
    ├── acoes.py                # criar_plano, ativar_lembretes, simular_contratacao, compartilhar_dados
    ├── guardrails.py           # regras puras + callbacks de entrada e saída
    ├── model_armor.py          # porta ModelArmorClient + adaptador HTTP + screener
    ├── audit.py                # before/after_tool 90, sessao_iniciada, estado_alterado
    ├── instructions.py         # trechos de instrução 50–69
    ├── envelope.py             # envelopes {dados, fonte, avisos} / {erro}
    ├── clock.py                # porta de relógio
    └── services.py             # registro, relógio e screener sob demanda
agent/tests/governanca/         # unitários, integração (runner) e bq
eval/seguranca/                 # casos.yaml, rodar_eval.py, resultado.md
```

## Mudanças por componente

1. **Registro**: `register()` usa `extensoes.registrar_ferramenta` e
   `registrar_instrucao`, além de `callbacks.registrar`:
   - `before_model` 10: `sessao_iniciada` + guardrail de entrada;
   - `before_model` 20: leitura do consentimento;
   - `before_tool` 20: gate;
   - `before_tool` e `after_tool` 90: auditoria;
   - `after_model` 10: guardrail de saída + chips do consentimento.
2. **Fluxo de consentimento**:
   - `solicitar_consentimento` cria a entrada `pendente` com
     `invocation_id`;
   - no turno seguinte, a leitura decide;
   - no aceite, anexa uma instrução para o LLM executar;
   - na recusa e no ambíguo, responde sem chamar o LLM;
   - o gate consome (`usado: true`) antes da execução.
3. **Respostas determinísticas** (bloqueios, recusa, confirmação) levam
   `custom_metadata.bussola` próprio, porque o ADK não chama `after_model`
   quando um `before_model` responde.
4. **Streaming**: o `after_model` também recebe pedaços parciais. O guardrail
   de saída acumula o texto por invocação (limite de tamanho), esconde
   parciais depois do disparo e substitui a resposta final.
5. **Falhas**:
   - se o registro falha no aceite, o pedido fica pendente e o cliente é
     avisado;
   - se falha na recusa, a recusa vale mesmo assim;
   - se falha na auditoria, o erro vai para o log e o turno segue;
   - se `criar_plano` não grava, devolve `INDISPONIVEL`;
   - se o Model Armor falha, valem só as regras.
6. **Contrato** (commit `contracts:` separado):
   - `criar_extensao` passa a ter prioridade sobre o pacote real;
   - fixture `sem_extensoes`;
   - três testes do 000 passam a usá-la;
   - contratos §6 documenta os campos opcionais da entrada de consentimento.

## Estratégia de testes e validação

- **Unitários**: parser, catálogo (inclui a igualdade da cópia do JSON), gate
  e consumo, ações, regras de guardrail (strings estáticas), callbacks com
  `LlmRequest`/`LlmResponse` estáticos, Model Armor com `httpx.MockTransport`
  e cliente falso, auditoria (minimização), `RegistroBigQuery` com cliente
  falso.
- **Integração**: `InMemoryRunner` + `ScriptedLlm`.
  - `criar_plano` sem pedido é bloqueado;
  - pedido → "sim" → plano gravado → nova tentativa bloqueada;
  - "não, agora não" → nada executado;
  - guardrail de entrada sem chamar o LLM;
  - o `root_agent` real traz as ferramentas e os callbacks do 005.
- **`bq`**: `RegistroBigQuery` grava e lê em `bussola_app_dev`.
- **Eval**: `eval/seguranca/rodar_eval.py` roda os casos do `casos.yaml` no
  mesmo runner roteirizado e grava `resultado.md`. Um teste do `make test`
  roda o eval.

## Complexity Tracking

Nenhuma violação.
