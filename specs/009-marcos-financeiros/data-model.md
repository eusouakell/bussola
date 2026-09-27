# Fase 1 — Modelo de dados

Todos os modelos são Pydantic (`_Modelo` de `bussola_mcp.contratos`, extra
proibido), BRL como `float` de 2 casas (`brl()`), prazos em meses inteiros.
Nenhum deles guarda texto de lançamento nem identificador além de
`id_usuario` na entrada.

## `EntradaPlanejarMarcos(EntradaComum)` — contratos.py

| Campo | Tipo | Regra |
|---|---|---|
| `id_usuario` | `str` | UUID v4 (herdado) |
| `ate_anomes` | `int` | 202501–202512 (herdado) |
| `valor_alvo` | `float` | `> 0` |
| `prazo_meses` | `int` | 1–360 |
| `prioridade` | `str \| None` | ≤ 100 caracteres, texto da prioridade informada pelo cliente; só ecoa no `objetivo`, nunca entra em cálculo |
| `usar_saldo_atual` | `bool` | default `True` (Q-009-3; divergente de `simular_objetivo`, que usa `False`) |

## `RegrasMarco` — contratos.py (premissas versionadas, FR-019)

| Campo | Default | Papel |
|---|---|---|
| `meses_reserva` | `3` | alvo da reserva = `meses_reserva × gasto_medio` (Q-009-1) |
| `fracao_reserva_parcial` | `0.3333` | marco parcial ≈ 1× gasto médio quando o alvo não cabe no horizonte |
| `pct_juros_renda_divida_cara` | `0.01` | juros médios ≥ 1% da renda média ⇒ dívida cara (Q-009-2) |
| `pct_comprometimento_renda_max` | `30.0` | parcelas acima de 30 pontos percentuais da renda ⇒ dívida cara |
| `pct_capacidade_sustentavel` | `0.60` | fração da sobra mediana usada como aporte sustentável (mesmo valor do cenário `equilibrado`) |
| `pct_aporte_renda_max` | `0.30` | aporte acima de 30% da renda ⇒ `RENDA_NAO_SUSTENTA` |
| `pct_recursos_minimo_meta` | `0.10` | recursos abaixo de 10% do valor-alvo ⇒ `VALOR_DISTANTE_DOS_RECURSOS` |
| `meses_fluxo_equilibrado` | `3` | meses seguidos de sobra ≥ 0 que fecham `EQUILIBRAR_FLUXO` |
| `fator_desnivel_incerto` | `3.0` | aporte necessário acima de 3× a capacidade ⇒ `trajetoria_incerta` |
| `piso_valor_marco` | `500.0` | marco com valor abaixo do piso não é proposto (materialidade) |
| `max_marcos` | `4` | tamanho máximo da trajetória (Q-009-4) |
| `prazo_maximo_marco` | `360` | prazo calculado acima disso ⇒ marco omitido e trajetória incerta |
| `rendimento_mensal` | `0.0` | nunca supor valorização (fonte §2.6) |
| `usar_saldo_atual` | `True` | saldo em conta conta como recurso, com piso zero (Q-009-3) |

## `ContextoFinanceiro` — contratos.py

Retrato determinístico do cliente até `ate_anomes`. Calculado por
`marcos.contexto_de_perfil(perfil, parcelas, regras)`.

| Campo | Tipo | Origem |
|---|---|---|
| `renda_media` | `float` | média de `perfil_mensal.renda` |
| `gasto_medio` | `float` | média de `perfil_mensal.gasto` |
| `sobra_media` | `float` | média de `perfil_mensal.sobra` |
| `sobra_mediana` | `float` | mediana de `perfil_mensal.sobra` |
| `meses_negativos` | `int` | meses com `sobra < 0` |
| `meses_considerados` | `int` | linhas de `perfil_mensal` no período |
| `saldo_atual` | `float` | `saldo_final` do último mês |
| `recursos_disponiveis` | `float` | `max(saldo_atual, 0)` se `usar_saldo_atual`, senão `0.0` |
| `juros_pagos_media` | `float` | média de `perfil_mensal.juros` |
| `parcelas_mensais` | `float` | soma das parcelas ativas do último mês |
| `comprometimento_renda_pct` | `float` | `parcelas_mensais ÷ renda_media × 100` |
| `meses_ate_fim_parcela` | `int \| None` | menor `meses_restantes` entre as parcelas ativas |
| `dados_ausentes` | `list[str]` | `PATRIMONIO`, `INVESTIMENTOS` (sempre, não há na base); `RESERVA` quando `usar_saldo_atual` é `False` |

**Invariantes**: `meses_considerados ≥ 1` (senão a ferramenta devolve
`DADOS_INSUFICIENTES`); `renda_media > 0` para os percentuais — renda média
zero desliga os motivos que dividem por renda e acrescenta aviso.

## `Motivo` — contratos.py

| Campo | Tipo | Descrição |
|---|---|---|
| `codigo` | `str` | um dos 8 abaixo |
| `observado` | `float` | valor medido |
| `limite` | `float` | limite que ele ultrapassou (ou não alcançou) |
| `explicacao` | `str` | frase determinística em pt-BR |

| Código | Acende quando | Nível |
|---|---|---|
| `CAPACIDADE_INSUFICIENTE` | `sobra_mediana <= 0` | 1 |
| `RISCO_EXCESSIVO` | `meses_negativos > 0` ou `saldo_atual < 0` | 1 |
| `DIVIDA_A_RESOLVER` | `juros_pagos_media ≥ 1% da renda` **ou** `comprometimento_renda_pct > 30` | 1 |
| `SEM_RESERVA` | `recursos_disponiveis < meses_reserva × gasto_medio` | 2 |
| `VALOR_DISTANTE_DOS_RECURSOS` | `recursos_disponiveis < 10% do valor_alvo` | 3 |
| `RENDA_NAO_SUSTENTA` | `aporte_necessario > 30% da renda_media` | 3 |
| `PREMISSA_IRREALISTA` | `aporte_necessario > sobra_mediana` (só fecharia poupando 100% da sobra ou supondo rendimento) | 4 |
| `PRAZO_NAO_CABE` | `aporte_necessario > capacidade_sustentavel` | 4 |

Derivados: `falta = max(valor_alvo − recursos_disponiveis, 0)`;
`aporte_necessario = falta ÷ prazo_meses`;
`capacidade_sustentavel = pct_capacidade_sustentavel × max(sobra_mediana, 0)`.

Nenhum motivo aceso ⇒ `motivos = []`, `marcos = []` (FR-002).

## `Marco` — contratos.py

| Campo | Tipo | Regra |
|---|---|---|
| `ordem` | `int` | 1..`max_marcos`, sequencial na trajetória |
| `nivel` | `int` | 1–4 (prioridade da fonte §2.4) |
| `tipo` | `str` | `EQUILIBRAR_FLUXO`, `REDUZIR_DIVIDA_CARA`, `FORMAR_RESERVA`, `ACUMULAR_PARTE_DA_META`, `AUMENTAR_CAPACIDADE`, `AJUSTAR_PRAZO` |
| `titulo` | `str` | frase curta determinística |
| `indicador` | `str` | condição verificável ("reserva de R$ 13.845,00 formada") |
| `valor_alvo` | `float \| None` | BRL; ao menos um entre `valor_alvo` e `prazo_meses` é preenchido (FR-006) |
| `prazo_meses` | `int \| None` | meses estimados com a capacidade sustentável |
| `aporte_mensal` | `float \| None` | aporte usado na estimativa |
| `por_que` | `str` | por que este marco importa |
| `relacao_com_objetivo` | `str` | como aproxima do objetivo declarado (FR-007) |

Regras por tipo:

| Tipo | `valor_alvo` | `prazo_meses` | Indicador |
|---|---|---|---|
| `EQUILIBRAR_FLUXO` | `abs(min(sobra_mediana, 0))` (quanto falta por mês para a sobra virar positiva) | `meses_fluxo_equilibrado` | sobra ≥ 0 em 3 meses seguidos |
| `REDUZIR_DIVIDA_CARA` | valor mensal a liberar: `max(parcelas_mensais − 30% da renda, juros_pagos_media)` | `meses_ate_fim_parcela` (ou `None`) | juros abaixo de 1% da renda e parcelas abaixo de 30% |
| `FORMAR_RESERVA` | alvo `3 × gasto_medio`, ou parcial `1 × gasto_medio` quando o prazo do alvo passa do horizonte do objetivo | `meses_para(falta_reserva, capacidade)` | reserva formada no valor-alvo |
| `ACUMULAR_PARTE_DA_META` | `capacidade_sustentavel × prazo_meses` do objetivo | `prazo_meses` do objetivo | parte da meta acumulada |
| `AUMENTAR_CAPACIDADE` | `aporte_necessario` | `None` | capacidade sustentável de aporte no valor-alvo |
| `AJUSTAR_PRAZO` | `valor_alvo` do objetivo | `meses_para(falta, capacidade)` | objetivo alcançado no novo prazo |

`AUMENTAR_CAPACIDADE` **não** é proposto quando `RENDA_NAO_SUSTENTA` está
aceso (seria pedir aporte acima de 30% da renda). Marco com `valor_alvo`
abaixo de `piso_valor_marco` não é proposto.

## `DadosPlanejarMarcos` — contratos.py (campo `dados` do envelope)

| Campo | Tipo | Descrição |
|---|---|---|
| `objetivo` | `dict` | eco de `valor_alvo`, `prazo_meses`, `prioridade` |
| `situacao` | `ContextoFinanceiro` | o retrato usado no cálculo |
| `motivos` | `list[Motivo]` | vazio quando o objetivo fecha |
| `marcos` | `list[Marco]` | até `max_marcos`; só o próximo quando `trajetoria_incerta` |
| `proximo` | `Marco \| None` | o marco destacado (o de menor nível/ordem) |
| `aporte_necessario` | `float` | para o objetivo no prazo desejado |
| `capacidade_sustentavel` | `float` | aporte sustentável estimado |
| `trajetoria_incerta` | `bool` | FR-010 |
| `ressalvas` | `list[str]` | frases determinísticas, sempre incluindo a de que marco não garante objetivo |
| `regras` | `RegrasMarco` | premissas usadas |

## Estado da sessão

`session.state["marcos"]` (`CHAVE_MARCOS` em `estado.py`) guarda o último
`dados` da ferramenta, como `cenarios` já faz para `comparar_cenarios`. Valor
inicial `None` em `estado_inicial`. Nenhuma chave existente muda.

Quem grava é o callback `after_tool` de **ordem 30**, registrado pelo pacote
`bussola_agent.marcos` (não há ferramenta ADK local — ver
[research.md](./research.md) R8). O callback devolve `None`, então nunca
substitui o resultado da ferramenta nem interrompe a cadeia.

## Avisos (campo `avisos` do envelope)

| Aviso | Quando |
|---|---|
| `"Marcos são uma rota adaptativa: atingir um marco não garante o objetivo final."` | sempre que há marco |
| `"Não há dado de patrimônio nem de investimentos nesta base; os marcos consideram só renda, gastos, parcelas e saldo em conta."` | sempre (dado ausente, FR-004) |
| `"O saldo atual em conta foi considerado como recurso já disponível."` | `usar_saldo_atual` e `saldo_atual > 0` |
| `"O saldo atual está negativo; ele foi considerado como zero e entrou no diagnóstico de risco."` | `saldo_atual < 0` |
| `"Sem rendimento considerado: nenhuma valorização de investimento entra nas contas."` | sempre |
| `"Renda média zero no período: os limites que dependem de renda não foram avaliados."` | `renda_media <= 0` |
