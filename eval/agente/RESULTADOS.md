# Resultados do eval do agente

Gerado por `eval/agente/rodar_eval.py` a partir de `eval/agente/perguntas.yaml`
(ciclo 004, FR-017 e AC-08). Cada modo reescreve só a sua seção. O texto das
respostas não é gravado aqui.

<!-- eval:offline:inicio -->
## Modo offline

- Execução: 2026-09-27 04:43 UTC; modelo: roteiro de cada turno (`ScriptedLlm`); MCP: MCP local (003 + domínio do 001) com `contracts/fixtures/`.
- Casos: 10; turnos: 13.
- Números verificados: 47; com fonte na ferramenta do turno: 46; ditos pelo cliente ou no objetivo: 1; **sem fonte: 0** (100% com fonte).
- Expectativas cumpridas: 19 de 19.
- Resultado: **aprovado**.

| Caso | Turno | Ferramentas (ok) | Etapa | Números (ferr./sessão/sem fonte) | Blocos | Fonte | Expectativas não cumpridas |
|---|---|---|---|---|---|---|---|
| jornada-demo | 1 | registrar_objetivo | ENTENDER | 2/0/0 |  | não | nenhuma |
| jornada-demo | 2 | perfil_financeiro, capacidade_poupanca | ANTECIPAR | 5/0/0 | Diagnóstico | sim | nenhuma |
| jornada-demo | 3 | comparar_cenarios | ORIENTAR | 9/0/0 | Simulação, Recomendação | sim | nenhuma |
| jornada-demo | 4 | escolher_cenario | AGIR | 0/0/0 |  | não | nenhuma |
| q1-perfil | 1 | perfil_financeiro | OBJETIVO | 5/0/0 | Diagnóstico | sim | nenhuma |
| q2-capacidade | 1 | capacidade_poupanca | OBJETIVO | 3/0/0 | Diagnóstico | sim | nenhuma |
| q3-cortes | 1 | oportunidades_corte | OBJETIVO | 4/0/0 | Diagnóstico | sim | nenhuma |
| q4-falta-entrada | 1 | simular_objetivo | ENTENDER | 5/0/0 | Simulação | sim | nenhuma |
| q5-cabe-no-prazo | 1 | simular_objetivo | ENTENDER | 5/0/0 | Simulação | sim | nenhuma |
| q6-mais-300 | 1 | simular_objetivo | ENTENDER | 4/1/0 | Simulação | sim | nenhuma |
| q7-dividas | 1 | dividas_e_parcelas | ENTENDER | 4/0/0 | Diagnóstico | sim | nenhuma |
| escopo-controle | 1 | perfil_financeiro | OBJETIVO | 0/0/0 |  | não | nenhuma |
| recusa-credito | 1 | nenhuma | OBJETIVO | 0/0/0 |  | não | nenhuma |
<!-- eval:offline:fim -->

<!-- eval:ao-vivo:inicio -->
## Modo ao-vivo

- Execução: 2026-09-27 04:05 UTC; modelo: nenhum Gemini respondeu; MCP: mock do 000 com `contracts/fixtures/`.
- Casos: 8; turnos: 11; turnos sem resposta do modelo (alta demanda): 11.
- Números verificados: 0; com fonte na ferramenta do turno: 0; ditos pelo cliente ou no objetivo: 0; **sem fonte: 0** (nenhum número nas respostas).
- Expectativas cumpridas: 0 de 17 (no ao vivo, relatadas sem reprovar o eval).
- Resultado: **inconclusivo (modelo indisponível em parte dos turnos)**.

| Caso | Turno | Ferramentas (ok) | Etapa | Números (ferr./sessão/sem fonte) | Blocos | Fonte | Expectativas não cumpridas |
|---|---|---|---|---|---|---|---|
| jornada-demo (tentativa 2) | 1 | nenhuma | OBJETIVO | 0/0/0 |  | não | modelo indisponível; registrar_objetivo respondeu; etapa ENTENDER |
| jornada-demo (tentativa 2) | 2 | nenhuma | OBJETIVO | 0/0/0 |  | não | modelo indisponível; perfil_financeiro respondeu; capacidade_poupanca respondeu; etapa ANTECIPAR |
| jornada-demo (tentativa 2) | 3 | nenhuma | OBJETIVO | 0/0/0 |  | não | modelo indisponível; comparar_cenarios respondeu; etapa ORIENTAR; recomendado acelerado |
| jornada-demo (tentativa 2) | 4 | nenhuma | OBJETIVO | 0/0/0 |  | não | modelo indisponível; escolher_cenario respondeu; etapa AGIR |
| q1-perfil (tentativa 2) | 1 | nenhuma | OBJETIVO | 0/0/0 |  | não | modelo indisponível; perfil_financeiro respondeu |
| q2-capacidade (tentativa 2) | 1 | nenhuma | OBJETIVO | 0/0/0 |  | não | modelo indisponível; capacidade_poupanca respondeu |
| q3-cortes (tentativa 2) | 1 | nenhuma | OBJETIVO | 0/0/0 |  | não | modelo indisponível; oportunidades_corte respondeu |
| q4-falta-entrada (tentativa 2) | 1 | nenhuma | ENTENDER | 0/0/0 |  | não | modelo indisponível; uma de simular_objetivo, comparar_cenarios, perfil_financeiro |
| q5-cabe-no-prazo (tentativa 2) | 1 | nenhuma | ENTENDER | 0/0/0 |  | não | modelo indisponível; uma de simular_objetivo, comparar_cenarios |
| q6-mais-300 (tentativa 2) | 1 | nenhuma | ENTENDER | 0/0/0 |  | não | modelo indisponível; simular_objetivo respondeu |
| q7-dividas (tentativa 2) | 1 | nenhuma | ENTENDER | 0/0/0 |  | não | modelo indisponível; dividas_e_parcelas respondeu |
<!-- eval:ao-vivo:fim -->

## Notas (manuais, fora das seções geradas)

- Como rodar: `make eval-agente` (offline, também coberto por
  `agent/tests/jornada/test_eval_offline.py` em `make test`) e
  `make eval-agente-ao-vivo` (Gemini real pela chave do Secret Manager, lida
  inline e nunca impressa). `--casos` filtra casos, `--mostrar` imprime as
  respostas só no terminal e `--mcp-url` aponta para outro MCP.
- Critério do AC-08: zero números "sem fonte". Um número conta como "com
  fonte" se aparece no retorno das ferramentas do turno (inclusive dentro de
  textos, como os trade-offs) ou foi dito na sessão (mensagem do cliente,
  `objetivo`, `ate_anomes`), com a mesma leitura do `after_model` 50. Inteiros
  soltos até 10 ficam fora da contagem.
- Limite conhecido: um inteiro calculado pelo modelo pode coincidir com outro
  número da ferramenta e passar (na primeira execução ao vivo, uma diferença
  de prazo). O prompt passou a proibir diferenças de prazo ou de valor que não
  estejam no texto das ferramentas (commit `2be0b9c`, D-12).
- q6 (mais R$ 300 por mês): com o 003 e o 001 na `main`, o MCP recalcula o
  prazo a partir do novo aporte (R$ 1.550,00 → 20 meses nas fixtures v1). No
  mock do 000 a simulação era sempre a canônica (D-08).
- Recusa e escopo (`recusa-credito`, `escopo-controle`) rodam só no offline:
  nenhum payload adversarial vai ao Gemini real (NFR-003).
- Cota: a chave compartilhada entre os ciclos devolveu 429 nos três Flash
  (`gemini-3.8-flash`, `gemini-3.7-flash` e `gemini-3.5-flash`) durante as
  execuções ao vivo. Turno sem resposta do modelo não conta número; se houver
  algum, o veredito é "inconclusivo" (saída 3) em vez de "aprovado".
- Histórico ao vivo (2026-09-27):
  - 03:29 UTC (`gemini-3.5-flash` e `gemini-3.8-flash`): só o 1º turno da
    jornada teve resposta. Nele o modelo registrou o objetivo e chamou perfil,
    capacidade, dívidas, cenários e contexto; 34 números, 34 com fonte, 0 sem
    fonte, com os blocos Diagnóstico, Simulação e Recomendação. Os outros 10
    turnos ficaram sem modelo. Essa execução levou ao ajuste do prompt do
    `2be0b9c`.
  - 03:52 UTC (3 tentativas por caso) e 04:05 UTC (2 tentativas): 11 de 11
    turnos sem modelo; veredito inconclusivo. A seção "Modo ao-vivo" acima é
    a de 04:05.
- Nome do arquivo: `RESULTADOS.md`, como pede o ciclo (D-06).
