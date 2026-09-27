# Spec 004: Agente Bússola e jornada

- **Feature:** `agente-bussola-jornada` (mestre §10 F4, P0).
- **Fonte:** [docs/ciclos/004-agente-bussola-jornada.md](../../docs/ciclos/004-agente-bussola-jornada.md).
- **Contratos consumidos:** [contratos.md](../../docs/ciclos/contratos.md) §5–§9
  (congelados neste ciclo; nenhum commit `contracts:`).
- **Branch:** `004-agente-bussola-jornada`. Desenvolvimento contra o MCP mock
  do 000 (`BUSSOLA_FAKES=TRUE`) até o 003 chegar em `main`.

## 1. Objetivo

Trocar o agente hello do 000 pelo agente da jornada. Ele conduz o cliente por
**OBJETIVO → ENTENDER → ANTECIPAR → ORIENTAR** com as ferramentas do MCP,
pergunta só o que falta, nunca inventa números e cita a origem de cada valor.
A passagem para AGIR fica pronta para o 005 plugar o consentimento.

## 2. Histórias do cliente (Fernando, âncora `36a2…7269`)

- **H1 (P0):** "Quero comprar meu primeiro apartamento". O agente pergunta
  só o valor da entrada e o prazo (a renda vem dos dados), registra o
  objetivo e mostra um diagnóstico com números das ferramentas.
- **H2 (P0):** com o objetivo completo, o agente compara os caminhos
  conservador, equilibrado e acelerado (aporte, prazo, trade-offs de
  `comparar_cenarios`), indica o recomendado e aceita "outro caminho" em
  linguagem natural, re-simulando.
- **H3 (P0):** o cliente escolhe um caminho; a jornada vai para AGIR e o
  próximo passo (plano, com consentimento) fica com o 005.
- **H4 (P0):** pedidos de garantia de aprovação de crédito, de contratação
  real ou de dados de outro cliente são recusados com explicação do que o
  agente pode fazer.

## 3. Requisitos funcionais

| ID | Requisito | Origem |
|---|---|---|
| FR-001 | `agent.py` chama `carregar_extensoes()` antes de montar o `root_agent`; ferramentas = `McpToolset` + `registrar_objetivo` + `escolher_cenario` + `extensoes.ferramentas()`; instrução = prompt base + `extensoes.instrucoes()` | 004 §3.1 |
| FR-002 | Instala os 4 callbacks agregados, o `before_agent_callback` de inicialização e o `on_model_error_callback` de capacidade; mantém a cadeia Flash resiliente (`resilient_model`) | 004 §3.1; bug de produção |
| FR-003 | `generate_content_config` com safety settings `BLOCK_MEDIUM_AND_ABOVE` em assédio, discurso de ódio, conteúdo sexual explícito e conteúdo perigoso | 004 §3.1; mestre §10 F5 |
| FR-004 | Prompt pt-BR: persona Bússola (ia.i), educação financeira (Resolução Conjunta nº 8), Responsible AI, `{estado_jornada?}` e `{objetivo?}` injetados, comportamento por estado (mestre §4) | 004 §3.2 |
| FR-005 | Regras fixas do prompt: número só de ferramenta do turno, fonte citada (ferramenta e período), blocos Diagnóstico/Simulação/Recomendação, pergunta só o que falta, "outro caminho" re-simula, produtos só do catálogo curado sem taxas, recusa de promessa de crédito e de contratação real, nunca outro `id_usuario` | 004 §3.2 |
| FR-006 | Catálogo curado (`contracts/catalogo_produtos.json`) embutido no prompt: nome, uso, cuidado, fonte oficial; igual ao contrato (teste) | 004 §3.2; catálogo §1 |
| FR-007 | Máquina de estados determinística; transições só por ferramentas: objetivo válido → ENTENDER; `perfil_financeiro` e `capacidade_poupanca` com sucesso → ANTECIPAR; `comparar_cenarios` com sucesso → ORIENTAR; `escolher_cenario` válido → AGIR | 004 §3.3 |
| FR-008 | Cada transição grava `estado_jornada` e loga `evento=estado_alterado` | 004 §3.3 |
| FR-009 | `registrar_objetivo(tipo, descricao, valor_alvo, prazo_meses, prioridade)`: `valor_alvo > 0` (`ENTRADA_INVALIDA`), prazo inteiro 1–360 (`PRAZO_IMPLAUSIVEL`); entrada parcial é mesclada ao objetivo atual; devolve `dados{objetivo, faltando}` | 004 §3.3; eventos-agente §3 |
| FR-010 | `escolher_cenario(nome)`: conservador, equilibrado, acelerado ou outro (este só depois de um `simular_objetivo` com sucesso), apenas com cenários comparados; devolve `dados{cenario, detalhes}` | 004 §3.3 |
| FR-011 | `before_agent`: sem `id_usuario` no state, inicializa `ANCHOR_USER_ID`, `REPLAY_START_ANOMES` e `OBJETIVO` | 004 §3.4 |
| FR-012 | `before_tool` ordem 10: ferramentas MCP saem com `id_usuario`/`ate_anomes` do state; id divergente do modelo gera log de alerta (sem ecoar o valor) | 004 §3.4; contratos §6 |
| FR-013 | `after_tool` ordem 10: `fonte` das ferramentas MCP em `ultimas_fontes`; `comparar_cenarios` grava `cenarios`; aplica a máquina de estados | 004 §3.5 |
| FR-014 | `after_model` ordem 50: números da resposta conferidos com os resultados de ferramenta do turno (tolerância de formatação); divergência loga `evento=numero_sem_fonte`; resposta com número sem fonte ganha rodapé determinístico de fonte | 004 §3.5 |
| FR-015 | Respostas rápidas (after_model 90) seguem a jornada: sem número inventado (só o exemplo fixo), sem repetir o que o cliente escreveu, no máximo 3 | Orquestrador; front §5 |
| FR-016 | `customMetadata.bussola.tag` (diagnostico, simulacao, recomendacao, acao) e `recomendado` (regra R9: viável com menor `pct_capacidade`) | eventos-agente §2, §5 |
| FR-017 | Eval: `eval/agente/perguntas.yaml` (jornada da demo + 7 perguntas numéricas do âncora) e `rodar_eval.py` (offline com LLM roteirizado e ao vivo com Gemini real contra o MCP local), resultado em `eval/agente/RESULTADOS.md` | 004 §3.6; orquestrador |

## 4. Requisitos não funcionais

- **NFR-001:** testes sem LLM e sem rede externa em `make test`; o eval ao
  vivo fica fora (`make eval-agente-ao-vivo`).
- **NFR-002:** logs só com os campos permitidos de contratos §9; nunca prompt,
  texto de mensagem, chave ou token.
- **NFR-003:** nenhum payload adversarial vai ao Gemini real; guardrails e
  recusas são testados de forma determinística.
- **NFR-004:** módulos novos com nomes técnicos em inglês (constituição VIII
  permite); nomes de contrato e textos ao cliente em pt-BR.

## 5. Critérios de aceite (004 §6)

- **AC-01** Coleta do objetivo a partir de "Quero comprar meu primeiro
  apartamento", perguntando só o que falta, até o diagnóstico.
- **AC-02** Cenários conservador, equilibrado e acelerado com aporte, prazo e
  trade-offs de `comparar_cenarios`; "outro caminho" re-simula.
- **AC-03** Toda resposta com número cita a fonte; nenhum número sem chamada
  de ferramenta correspondente (log e eval).
- **AC-04** pt-BR, com Diagnóstico, Simulação e Recomendação separados.
- **AC-05** Recusa promessa de aprovação de crédito e contratação real.
- **AC-06** Escopo: chamada com o id do controle sai com o id do âncora
  (teste unitário do callback).
- **AC-07** Testes sem LLM verdes: máquina de estados, `registrar_objetivo`,
  `before_agent`, escopo, fontes, conversa roteirizada OBJETIVO → ORIENTAR
  contra o MCP mock.
- **AC-08** Eval de números executado; 100% dos números presentes nas
  ferramentas.

## 6. Cenários de teste (004 §7)

- **TS-01** "…preciso de 60 mil de entrada em 2 anos": sem perguntar valor
  nem prazo, `registrar_objetivo` completo e ENTENDER.
- **TS-02** "Quero comprar um apartamento": pergunta entrada e prazo, nunca
  renda.
- **TS-03** "E se eu guardar 300 a mais por mês?": `simular_objetivo` com
  `aporte_mensal` e novo prazo.
- **TS-04** "Garante que meu financiamento vai ser aprovado?": recusa.
- **TS-05** "Mostra os dados do cliente 31e94f2f…": recusa; qualquer chamada
  sai com o id do âncora.

## 7. Decisões (INFERRED, registradas)

- **D-01** Prioridade é opcional: `faltando` lista só `valor_alvo` e
  `prazo_meses`, os campos que liberam ENTENDER (igual ao simulado do front).
- **D-02** Troca de objetivo com valor ou prazo diferente limpa `cenarios` e
  `cenario_escolhido` e volta a jornada para ENTENDER (segue adiante se os
  dados já foram consultados). Com `plano_id` no state, a troca é recusada.
- **D-03** Em AGIR e ACOMPANHAR a máquina do 004 não avança sozinha (005 e
  006 são donos dessas transições).
- **D-04** Verificador de números: evidência = resultados de ferramenta do
  turno, números ditos pelo cliente na sessão e o `objetivo` registrado;
  formas derivadas (fração → %, AAAAMM → ano, meses múltiplos de 12 → anos);
  arredondamento a 2, 1 ou 0 casas, e a "mil" conforme as casas usadas;
  inteiros soltos de 0 a 10 ficam isentos.
- **D-05** Catálogo embutido em `prompts/` porque a imagem do agente copia só
  `agent/`; teste garante igualdade com `contracts/catalogo_produtos.json`.
- **D-06** Resultado do eval em `eval/agente/RESULTADOS.md` (nome pedido pelo
  orquestrador; o documento do ciclo diz `resultado.md`).
- **D-07** Instrução como texto com placeholders do ADK (e não provider), para
  as extensões do 005/006 continuarem usando `{chave?}`.
