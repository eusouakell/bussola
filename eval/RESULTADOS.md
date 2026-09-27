# Resultados dos evals (integração final)

Consolidação dos quatro evals dos ciclos para o checklist de integração
([docs/ciclos/README.md §8](../docs/ciclos/README.md#8-integração-final-e-demo-checklist-liderada-pela-pessoa-d-com-todos)).
Os detalhes ficam no arquivo de cada eval, que o próprio script regenera.
Conferido em 2026-09-27 sobre `main` com todos os ciclos (001–008)
integrados.

## Resumo

| Eval | Ciclo | Modo | Resultado | Critério | Detalhes |
|---|---|---|---|---|---|
| RAG (`buscar_contexto_financeiro`) | 002 | Embeddings reais (`gemini-embedding-001`) sobre o corpus versionado | **22/22 (100%)** no top-3 com `numpy`; linha de base `lexico` 18/22 (82%); 4/4 negativas vazias | ≥ 80% no `numpy` | [rag/RESULTADOS.md](rag/RESULTADOS.md) |
| Agente (jornada e números) | 004 | Offline: MCP local (003 + domínio do 001) com fixtures v1, LLM roteirizado | **23/23 expectativas**; 48 números verificados, **0 sem fonte** | AC-08: nenhum número sem fonte | [agente/RESULTADOS.md](agente/RESULTADOS.md) |
| Segurança (guardrails e consentimento) | 005 | Determinístico: LLM roteirizado, guardrail por regras, Model Armor fora | **16/16 casos**; 10/10 do ciclo §3.6 (itens 1–8) | Todos os casos ok | [seguranca/resultado.md](seguranca/resultado.md) |
| Acompanhamento (replay mês a mês) | 006 | Offline: `InMemoryRunner` com a composição de produção (004 + 005), fixtures v1 | **51/51 verificações**; 6 meses revelados, nenhum envelope depois do corte | Todas as verificações ok | [acompanhamento/RESULTADOS.md](acompanhamento/RESULTADOS.md) |

Como rodar de novo:

- `make eval-rag` (usa a chave do Gemini do Secret Manager, lida inline e
  nunca impressa);
- `make eval-agente`, `make eval-seguranca` e `make eval-acompanhamento`
  (offline, sem rede nem GCP).

## Destaques

- **Números com fonte.** No eval do 004, cada número das respostas aparece
  no retorno de uma ferramenta do turno ou foi dito pelo cliente. No do 006,
  42 números citados foram conferidos nos envelopes. O LLM não calcula.
- **Corte temporal.** O 006 revela 202507 a 202512 em ordem, sem nenhum
  envelope com período depois do `ate_anomes` da sessão. Depois de 202512,
  a ferramenta devolve `FIM_DO_REPLAY`.
- **Escopo.** Quando o modelo pede outro cliente ou outro corte, o escopo
  vem do `session.state` (004 e 006). O pedido de dados de outro cliente
  pelo UUID é barrado na entrada (005).
- **Consentimento.** "Sim, mas…" fica pendente, a recusa é registrada, o
  consentimento vale para uma única ação e compartilhar dados é sempre
  recusado (005). O ajuste do plano no 006 passa pelo gate do 005, com
  `consentimento_solicitado` e `consentimento_decidido` na auditoria.
- **RAG.** O limiar do `numpy` (0,64) fica entre o menor acerto (0,686) e
  a maior negativa (0,600). Nenhum trecho de produto traz taxa ou preço.

## Pendências (dependem de ação humana)

- **Eval do 004 contra a produção** (`make eval-agente-ao-vivo`). A última
  execução ao vivo, em 2026-09-27 04:05 UTC, ficou **inconclusiva**: nenhum
  Gemini respondeu (alta demanda), embora todas as ferramentas tenham
  respondido. Repita no ensaio da demo, com a revisão final promovida.
- **Eval do 005 contra a produção.** Por decisão do time, os guardrails são
  validados só de forma determinística: nenhum texto adversarial vai ao
  Gemini ou ao Model Armor reais. Na produção, confira apenas a auditoria e
  os consentimentos em `bussola_app` depois do ensaio (sem ataques).
- **Acompanhamento com o MCP publicado.** O roteiro de 202506 a 202508
  contra o MCP real fica para o ensaio da integração
  ([specs/006-acompanhamento-replay/traceability.md](../specs/006-acompanhamento-replay/traceability.md)).
- **Números da demo.** Conferidos contra as mesmas ferramentas em
  [docs/roteiro-demo.md](../docs/roteiro-demo.md).
