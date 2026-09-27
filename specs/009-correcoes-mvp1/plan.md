# Plan — Ciclo 009: correções dos unhappy paths do MVP1

## Constitution Check

| Princípio | Impacto do ciclo | Como fica |
|---|---|---|
| I. Números de ferramenta determinística | FR-03 mostra aporte necessário e sobra típica | `sobra_mediana` vem do golden de `capacidade_poupanca`; a divisão `valor/prazo` é função em código. Nenhum número inventado, nenhuma projeção de rendimento. |
| II. Agente isolado de SQL e infra | — | inalterado |
| III. Read-only com escopo por cliente | FR-05 passa a servir não-âncora | continua preso ao `id_usuario` da sessão; nenhum dado de outro cliente |
| IV. Respostas rotuladas e explicáveis | FR-06 muda a apresentação de avisos | aviso de demonstração continua visível, só muda o peso visual — não se esconde a natureza do dado |
| V. Dados sintéticos e logs seguros | FR-04 acrescenta log de omissão de ferramenta | usa `logging_json` com campos permitidos; nunca prompt nem texto do cliente |
| VI. Consentimento explícito e auditado | FR-04 força tool call **após** o consentimento | o gate de consentimento continua intacto; o `tool_config` só atua depois do "sim" |
| VII. Segredos fora do repositório | — | inalterado |
| VIII. pt-BR e Responsible AI | FR-01, 02, 03, 06, 07 são texto ao cliente | todos revisados: pt-BR, sem "garantido/aprovado", sem urgência, sem culpar o cliente |
| IX. Testes obrigatórios e gates sem rede | todos os FR | cada FR com teste; 4 gates verdes; `BUSSOLA_FAKES=TRUE` |
| X. Contratos e paralelismo | FR-01 acrescenta motivo de guardrail | **aditivo**: novo valor no union `MotivoGuardrail` e em `REASONS`; nada removido nem renomeado |

Nenhuma violação. Nenhuma exceção a registrar.

## Decisões de arquitetura

**D1 — Corrigir front simulado e agente, nos dois.** As telas dos bugs vieram
do simulado, que é o modo padrão e o que os avaliadores vão usar. Mas o agente
real tem a mesma lacuna de guardrail. Corrigir só um lado deixaria o defeito
vivo no outro.

**D2 — Guardrail de atividade ilícita por regra determinística, não por
prompt.** `governanca/instructions.py:1-7` já declara que prompt não é
enforcement. A regra entra em `_INPUT_RULES` (Python) e em `REGRAS` (TS), antes
das demais, para vencer o extrator de valor.

**D3 — Viabilidade calculada, não hardcoded.** O `if (valor === 30000 && prazo
=== 24)` de `agente-simulado.ts:290` sai. No lugar, comparação entre aporte
necessário e `sobra_mediana` da ferramenta. Mantém a constituição I e faz o
comportamento generalizar para qualquer meta.

**D4 — `tool_config` só onde a chamada é determinística.** Forçar
`FunctionCallingConfig(mode=ANY)` em todos os estados impediria o modelo de
fazer perguntas de esclarecimento. Só se aplica depois do consentimento
concedido, onde a ferramenta a chamar já é conhecida. Nos demais estados,
detecção + log.

**D5 — Avisos de demonstração ficam, o jargão sai.** Esconder que os números
vêm de exemplo gravado seria desonesto (constituição IV). O que sai é "mock",
`valor_alvo=`, `prazo_meses=`, `202506`. O peso visual cai para badge.

**D6 — Não trocar o id da Renata.** O pedido do time parte de diagnóstico
errado (ela tem 12 meses, como o Fernando). A causa é a regra anchor-only do
mock do 000. Trocar o id não resolveria e espalharia a mudança por ~25 arquivos
(fixtures, contratos, evals, deploy, docs). Corrige-se a regra.

## Workstreams (Team Mode, paralelos, particionados por arquivo)

| WS | Papel | Bugs | Arquivos |
|---|---|---|---|
| WS-1 | frontend-dev | 01, 02, 03 | `web/src/simulado/{guardrails,intencoes,textos,agente-simulado}.ts`, `web/src/agente/tipos.ts` |
| WS-2 | backend-dev | 01b, 04 | `agent/bussola_agent/governanca/guardrails.py`, `prompts/base.py`, `jornada/`, `agent.py` |
| WS-3 | backend-dev | 05, 06, 07 | `mcp_server/.../golden_adapter.py`, `agent/.../acompanhamento/fakes.py`, `agent/.../resilient_model.py` |
| WS-4 | frontend-dev | 05b, 06 | `web/src/componentes/base/Avisos.tsx`, `conversa/BlocoAnalise.tsx`, `cards/CardDiagnostico.tsx`, `web/src/sessao/catalogo.ts` |

Sem interseção de arquivos entre workstreams. Contrato compartilhado entre
WS-1 e WS-2: a string `"atividade_ilicita"`. Entre WS-3 e WS-4: os textos dos
avisos de demonstração, conferidos na integração.

## Integração

Tech-lead (sessão principal) reconcilia, resolve o que quebrou fora do escopo
de cada WS, roda os 4 gates completos, e só então faz merge em `main`.
