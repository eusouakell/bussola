# Eval do acompanhamento (ciclo 006)

Gerado por `make eval-acompanhamento`. Offline: fixtures de `contracts/fixtures/`,
LLM roteirizado (`ScriptedLlm`), `InMemoryRunner` do ADK, sem rede, GCP ou
modelo real. O agente tem a composição de produção: escopo e verificação
de números do 004, consentimento, guardrails e auditoria do 005.

**Resultado: 51/51 verificações ok** (aprovado).

- Chamadas MCP no roteiro principal: 16.
- Envelopes de ferramenta conferidos quanto ao corte: 10.
- Números citados nas respostas e conferidos nos envelopes: 42.

## Roteiro: plano de 60 mil em 24 meses criado em 202506

Status esperado = `desvio.compute_deviation(planejado, sobra do fixture)`,
calculado pelo eval sem passar pela ferramenta. Tolerância de 10% do planejado.

| Mês | Planejado | Realizado | Desvio | Status | Esperado | Acumulado | % meta | Categoria | Rotas |
|---|---:|---:|---:|---|---|---:|---:|---|---|
| 202507 | R$ 2.500,00 | R$ 884,53 | -R$ 1.615,47 | desvio | desvio (ok) | R$ 884,53 | 1,47% | Viagens | A: R$ 2.570,24 x 23; B: R$ 2.500,00 x 24 (estimativa local) |
| 202508 | R$ 2.570,24 | R$ 4.218,74 | R$ 1.648,50 | folga | folga (ok) | R$ 5.103,27 | 8,51% | - | - |
| 202509 | R$ 2.570,24 | R$ 3.723,47 | R$ 1.153,23 | folga | folga (ok) | R$ 8.826,74 | 14,71% | - | - |
| 202510 | R$ 2.570,24 | R$ 5.812,02 | R$ 3.241,78 | folga | folga (ok) | R$ 14.638,76 | 24,40% | - | - |
| 202511 | R$ 2.570,24 | R$ 6.484,20 | R$ 3.913,96 | folga | folga (ok) | R$ 21.122,96 | 35,20% | - | - |
| 202512 | R$ 2.570,24 | R$ 1.509,25 | -R$ 1.060,99 | desvio | desvio (ok) | R$ 22.632,21 | 37,72% | Outros gastos | A: R$ 2.075,99 x 18; B: R$ 2.570,24 x 15 (estimativa local) |

Em 202507 o cliente adota a rota A com consentimento; de 202508 em diante o
planejado é o aporte da rota A.

## Auditoria (registro em memória, compartilhado por 005 e 006)

| Evento | Quantidade |
|---|---:|
| `acompanhamento_mes_avancado` | 6 |
| `consentimento_decidido` | 1 |
| `consentimento_solicitado` | 1 |
| `desvio_detectado` | 2 |
| `estado_alterado` | 1 |
| `ferramenta_chamada` | 10 |
| `plano_ajustado` | 1 |
| `rota_recalculada` | 2 |
| `sessao_iniciada` | 1 |

## Verificações

| Verificação | Esperado | Obtido | Ok |
|---|---|---|---|
| Escopo das chamadas MCP vem do state (modelo pediu controle e 202512) | {('âncora', 202507)} | {('âncora', 202507)} | sim |
| Consentimento pendente antes do ajuste | pendente | pendente | sim |
| Ajuste adota a rota A | A | A | sim |
| Plano novo vira o plano_id da sessão | True | True | sim |
| 202507: status igual ao desvio.py sobre o fixture | desvio | desvio | sim |
| 202507: realizado igual ao fixture | 884.53 | 884.53 | sim |
| 202507: acumulado igual à soma dos meses positivos | 884.53 | 884.53 | sim |
| 202507: ate_anomes da sessão avançou | 202507 | 202507 | sim |
| 202508: status igual ao desvio.py sobre o fixture | folga | folga | sim |
| 202508: realizado igual ao fixture | 4218.74 | 4218.74 | sim |
| 202508: acumulado igual à soma dos meses positivos | 5103.27 | 5103.27 | sim |
| 202508: ate_anomes da sessão avançou | 202508 | 202508 | sim |
| 202509: status igual ao desvio.py sobre o fixture | folga | folga | sim |
| 202509: realizado igual ao fixture | 3723.47 | 3723.47 | sim |
| 202509: acumulado igual à soma dos meses positivos | 8826.74 | 8826.74 | sim |
| 202509: ate_anomes da sessão avançou | 202509 | 202509 | sim |
| 202510: status igual ao desvio.py sobre o fixture | folga | folga | sim |
| 202510: realizado igual ao fixture | 5812.02 | 5812.02 | sim |
| 202510: acumulado igual à soma dos meses positivos | 14638.76 | 14638.76 | sim |
| 202510: ate_anomes da sessão avançou | 202510 | 202510 | sim |
| 202511: status igual ao desvio.py sobre o fixture | folga | folga | sim |
| 202511: realizado igual ao fixture | 6484.2 | 6484.2 | sim |
| 202511: acumulado igual à soma dos meses positivos | 21122.96 | 21122.96 | sim |
| 202511: ate_anomes da sessão avançou | 202511 | 202511 | sim |
| 202512: status igual ao desvio.py sobre o fixture | desvio | desvio | sim |
| 202512: realizado igual ao fixture | 1509.25 | 1509.25 | sim |
| 202512: acumulado igual à soma dos meses positivos | 22632.21 | 22632.21 | sim |
| 202512: ate_anomes da sessão avançou | 202512 | 202512 | sim |
| Meses revelados em ordem | [202507, 202508, 202509, 202510, 202511, 202512] | [202507, 202508, 202509, 202510, 202511, 202512] | sim |
| Status não avança o mês | 202512 | 202512 | sim |
| Status: acumulado igual ao do último mês | 22632.21 | 22632.21 | sim |
| Depois de 202512: FIM_DO_REPLAY | FIM_DO_REPLAY | FIM_DO_REPLAY | sim |
| FIM_DO_REPLAY mantém o corte | 202512 | 202512 | sim |
| Chamadas MCP nunca pedem mês depois do corte | [] | [] | sim |
| Auditoria: um acompanhamento_mes_avancado por mês | 6 | 6 | sim |
| Auditoria: plano_ajustado registrado | 1 | 1 | sim |
| Registro: plano ajustado gravado | 1 | 1 | sim |
| Registro: uma linha de acompanhamento por mês | 6 | 6 | sim |
| Corte em 202512: FIM_DO_REPLAY | FIM_DO_REPLAY | FIM_DO_REPLAY | sim |
| Corte em 202512: corte mantido | 202512 | 202512 | sim |
| Corte em 202512: texto é a mensagem da ferramenta | Chegamos ao fim da demonstração: os dados vão até dezembro de 2025. | Chegamos ao fim da demonstração: os dados vão até dezembro de 2025. | sim |
| Sessão sem plano_id: SEM_PLANO_ATIVO | SEM_PLANO_ATIVO | SEM_PLANO_ATIVO | sim |
| Sessão sem plano_id: corte mantido | 202506 | 202506 | sim |
| Sessão sem plano_id: texto é a mensagem da ferramenta | Para acompanhar mês a mês, primeiro precisamos criar o seu plano. | Para acompanhar mês a mês, primeiro precisamos criar o seu plano. | sim |
| Cliente de controle: DADOS_INSUFICIENTES | DADOS_INSUFICIENTES | DADOS_INSUFICIENTES | sim |
| Cliente de controle: corte mantido | 202506 | 202506 | sim |
| Cliente de controle: texto é a mensagem da ferramenta | O mock só tem respostas do cliente âncora. | O mock só tem respostas do cliente âncora. | sim |
| Ajuste sem consentimento (gate do 005) | CONSENTIMENTO_NECESSARIO | CONSENTIMENTO_NECESSARIO | sim |
| Ajuste sem consentimento (gate do 005): plano mantido | plano-inicial | plano-inicial | sim |
| Ajuste sem consentimento (guarda local do 006, sem o 005) | CONSENTIMENTO_NECESSARIO | CONSENTIMENTO_NECESSARIO | sim |
| Ajuste sem consentimento (guarda local do 006, sem o 005): plano mantido | plano-inicial | plano-inicial | sim |

## Respostas ao cliente (LLM roteirizado, números das ferramentas)

**Cliente:** avançar um mês

> **O que aconteceu:** em julho de 2025, o planejado era R$ 2.500,00 e o realizado foi R$ 884,53 (abaixo do planejado). Você acumulou R$ 884,53 (1,47% da meta).
> 
> **Por quê:** Viagens somou R$ 935,14, contra uma média de R$ 6,51 antes do plano.
> 
> **O que fazer (simulação):** rota A (manter o prazo): R$ 2.570,24 por mês durante 23 meses, acima da capacidade mensal estimada; rota B (manter o aporte): R$ 2.500,00 por mês durante 24 meses, acima da capacidade mensal estimada.

**Cliente:** sim

> Plano ajustado: R$ 2.570,24 por mês, 23 meses até a meta. Nenhum dinheiro foi movido.

**Cliente:** Ver status do plano

> Seu plano está em 37,72% da meta: R$ 22.632,21 acumulados e faltam R$ 37.367,79 em 18 meses.

## Limitações

- O LLM é roteirizado: o eval mede ferramentas, estado, corte temporal e
  auditoria, não a redação do Gemini.
- O `simular_objetivo` do mock devolve sempre o golden do corte. Quando a
  resposta não corresponde ao pedido, a rota usa a estimativa local de
  `routes.py` e avisa. Reavaliar com o 003 (resposta calculada pelo MCP real).
- Os números dependem dos fixtures do 001. Se `make fixtures` mudar os
  valores, rode de novo e revise esta página.
