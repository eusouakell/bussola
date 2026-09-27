# Ciclo 009 — questões e decisões

Respostas dadas na fase `clarify` do Spec Master (2026-09-26), pela Pessoa B.
As quatro primeiras são premissas numéricas que **não** existiam no
repositório; decidi-las era condição para não violar o FR-004 ("não inventar
informação ausente").

## Q-009-1 — Reserva de emergência adequada

**Pergunta.** A base não tem campo de reserva. Quantos meses de gasto médio
definem reserva adequada?

**Decisão.** Alvo de **3× o gasto médio mensal**. Quando esse alvo exigir prazo
incompatível com a capacidade sustentável, o próximo marco passa a ser o alvo
parcial de **1× o gasto médio**, e o alvo de 3× continua como marco seguinte.

**Por quê.** 3–6 meses é a referência usual de educação financeira; 3× mantém o
marco alcançável (fonte §2.3.1), e o marco parcial resolve o caso de sobra
pequena sem abandonar o alvo. Para o âncora (gasto médio ≈ R$ 4.615), o alvo
fica ≈ R$ 13.845 e o parcial ≈ R$ 4.615.

**Vira** `RegrasMarco.meses_reserva = 3` e
`RegrasMarco.fracao_reserva_parcial = 1/3`, mais o FR-021.

## Q-009-2 — Critério de "dívida cara"

**Pergunta.** Não há taxa por contrato. Os dados são `juros_pagos_media`
(juros médios pagos por mês) e `comprometimento_renda_pct` (parcelas sobre
renda). Qual critério determinístico marca a dívida como cara?

**Decisão.** Dívida cara quando **juros médios pagos ≥ 1% da renda média**
**ou** **parcelas ativas > 30% da renda média**. Abaixo dos dois pisos, o
gatilho de nível 1 não acende.

**Por quê.** Usa os dois sinais disponíveis, cada um com piso de
materialidade. O âncora paga ≈ R$ 61/mês de juros sobre renda ≈ R$ 7.451
(0,8%): não acende, então a demo do âncora vai para reserva/patrimônio, e um
perfil endividado sintético acende o nível 1. Sem piso, R$ 61 dominariam a
demo inteira.

**Vira** `RegrasMarco.pct_juros_renda_divida_cara = 0.01` e
`RegrasMarco.pct_comprometimento_renda_max = 0.30`, mais o FR-022.

## Q-009-3 — Patrimônio e recursos já disponíveis

**Pergunta.** A base não tem investimento nem patrimônio. Em que a engine se
apoia para o marco de patrimônio?

**Decisão.** O **saldo atual em conta conta como recurso já disponível**, com
**piso em zero**: saldo negativo vale zero de recurso *e* acende o gatilho de
risco/fluxo de caixa, com aviso. Patrimônio e investimentos além do saldo
seguem como dado ausente (`DADO_AUSENTE_PATRIMONIO`,
`DADO_AUSENTE_INVESTIMENTOS`) e não geram marco.

**Divergência registrada.** `RegrasCenario` (contratos §4) usa
`saldo_inicial = 0.0` porque "saldo de conta não é reserva", e
`simular_objetivo` só considera o saldo com `usar_saldo_atual = true`. A
ferramenta de marcos passa a considerá-lo por padrão
(`usar_saldo_atual = true`), por decisão explícita da Pessoa B no `clarify`.
Consequências aceitas:

- os números de marcos e os de `simular_objetivo` partem de pontos diferentes
  quando o cliente tem saldo positivo — a resposta cita a premissa nos
  `avisos`, para não parecer inconsistência;
- o âncora tem saldo mínimo ≈ −R$ 2.072 no histórico, então o piso em zero e o
  aviso são obrigatórios, não opcionais;
- se o time preferir alinhar com `RegrasCenario` depois, basta trocar o default
  de `usar_saldo_atual` — a regra está em `RegrasMarco`, versionada.

**Vira** `RegrasMarco.usar_saldo_atual = True`,
`RegrasMarco.piso_recursos = 0.0` e o FR-023.

## Q-009-4 — Quantidade de marcos devolvidos

**Pergunta.** Devolver só o próximo marco ou a trajetória inteira?

**Decisão.** Trajetória com **até 4 marcos**, com exatamente um destacado como
próximo. Quando `trajetoria_incerta` estiver ligada, a resposta traz **apenas o
próximo marco**.

**Por quê.** A progressão da fonte §2.3.4 fica visível, e a exceção evita a
"sequência artificial" proibida pela fonte §2.5 justamente nos casos de
desnível grande.

**Vira** `RegrasMarco.max_marcos = 4` e o FR-024.

## Q-009-5 — Quem dispara o cálculo de marcos

**Pergunta.** O modelo chama uma ferramenta nova quando a simulação não fecha,
ou `simular_objetivo` passa a sinalizar a necessidade de marcos?

**Decisão (minha, documentada).** Ferramenta nova `planejar_marcos`, chamada
pelo agente. `simular_objetivo` e `comparar_cenarios` **não** mudam.

**Por quê.** Mexer em `simular_objetivo` significaria alterar ferramenta e
golden do ciclo 003/001 (propriedade da Pessoa A) e quebrar o contrato
existente; ferramenta nova é aditiva (contratos §0). A instrução de prompt
liga o gatilho: quando a simulação volta inviável ou com erro de prazo
implausível, o agente chama `planejar_marcos` antes de responder.

## Q-009-6 — Cinco blocos × Diagnóstico/Simulação/Recomendação

**Pergunta.** Como os 5 blocos da fonte §2.7 convivem com os rótulos exigidos
pela constituição IV?

**Decisão (minha, documentada).** Os 5 blocos ficam **dentro** dos rótulos
existentes, sem criar um terceiro padrão de resposta:

| Rótulo da constituição IV | Blocos da fonte §2.7 |
|---|---|
| Diagnóstico | Objetivo · Situação atual |
| Simulação | Próximo marco (valor, prazo, indicador) |
| Recomendação | Por que esse marco importa · Depois disso |

**Por quê.** A constituição está congelada e exige os três rótulos; a fonte
exige os cinco blocos. O mapeamento satisfaz as duas sem emenda
constitucional, e é o que a instrução de prompt do 009 registra.
