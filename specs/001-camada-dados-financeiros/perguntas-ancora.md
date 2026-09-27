# Perguntas do cliente âncora: pergunta → função → valor

Este documento atende ao AC-01 e ao FR-018. Cobre o cliente âncora
`36a21505-d6d4-42d3-b319-d51a133c7269` ("Fernando") em dois cortes, `ate_anomes = 202506`
e `ate_anomes = 202512`.

**De onde vêm os valores**

- As funções são as de `bussola_mcp.dominio.metricas`, rodando sobre as fixtures v1.
- As fixtures v1 são iguais a `bussola_dados`. Isso é conferido por
  `tests/dados/test_repositorio_bq_real.py` no `make test-bq`.
- `tests/dados/test_perguntas_ancora.py` fixa cada número desta página no `make test`,
  sem rede.
- Os valores estão em BRL. O LLM não calcula nenhum deles.

**Premissas de demo (INFERRED, spec AC-01)**

- Objetivo: entrada de apartamento de R$ 60.000, com prazo desejado de 24 meses.
- "Economizar mais R$ 300/mês" significa somar R$ 300 ao aporte do cenário
  equilibrado.
- Rendimento zero: a base não tem taxas, e elas não se inventam.
- A capacidade de poupança é a sobra mensal **mediana** do período.

**Como reproduzir**

```python
from bussola_mcp.dominio import metricas
from bussola_mcp.dominio.fakes import RepositorioFake

repo = RepositorioFake("contracts/fixtures")  # ou RepositorioBigQuery("query")
metricas.comparar_cenarios(repo, ID_ANCORA, 202512, 60000.0, 24)
```

## Respostas

| # | Pergunta | Função | 202506 (6 meses) | 202512 (12 meses) |
|---|---|---|---|---|
| 1 | Qual é o perfil financeiro do Fernando? | `perfil_financeiro` | renda média 6.691,39; gasto médio 4.789,93; sobra média 1.901,47; saldo mínimo −2.072,31, máximo 19.023,89, atual 17.652,15; aviso de saldo negativo em 2 meses | renda média 7.451,27; gasto médio 4.614,52; sobra média 2.836,75; saldo mínimo −2.072,31, máximo 49.320,95, atual 47.597,68; aviso de saldo negativo em 2 meses |
| 2 | Quanto ele consegue guardar por mês hoje? | `capacidade_poupanca` | sobra mediana 1.729,00 (média 1.901,47; desvio 1.677,98); 1 mês com gasto acima da renda | sobra mediana 2.489,44 (média 2.836,75; desvio 2.093,00); 1 mês com gasto acima da renda |
| 3 | Onde existem oportunidades de redução de gastos? | `oportunidades_corte(top_n=3)` | Restaurantes 96,61/mês (30% de 322,04); Compras 85,50 (30% de 285,00); Assinaturas 54,01 (50% de 108,02). Aluguel não entra (não discricionário) | Restaurantes 103,61/mês (30% de 345,35); Compras 88,22 (30% de 294,05); Assinaturas 50,27 (50% de 100,54). Aluguel não entra |
| 4 | Quanto falta para a entrada do apartamento? | `simular_objetivo(60000, prazo_meses=24, usar_saldo_atual=True)` | com o saldo atual (17.652,15), faltam 42.347,85: aporte de 1.764,49/mês por 24 meses, acima da capacidade (folga −35,49) | com o saldo atual (47.597,68), faltam 12.402,32: aporte de 516,76/mês por 24 meses, dentro da capacidade (folga 1.972,68) |
| 5 | O objetivo cabe no prazo desejado? | `simular_objetivo(60000, prazo_meses=24)` e `comparar_cenarios(60000, 24)` | não. Sem usar o saldo, pede 2.500,00/mês contra capacidade de 1.729,00 (folga −771,00). Cenários: conservador 691,60 → 87 meses; equilibrado 1.037,40 → 58; acelerado 1.660,85 → 37 (com 9 cortes sugeridos) | por pouco, não. Pede 2.500,00/mês contra 2.489,44 (folga −10,56). Cenários: conservador 995,78 → 61 meses; equilibrado 1.493,66 → 41; acelerado 2.277,07 → 27 (com 9 cortes sugeridos) |
| 6 | Como o prazo muda se ele economizar mais R$ 300 por mês? | `comparar_cenarios` + `simular_objetivo(60000, aporte_mensal=equilibrado + 300)` | equilibrado vai de 1.037,40 para 1.337,40/mês: o prazo cai de 58 para 45 meses (−13), dentro da capacidade (folga 391,60) | equilibrado vai de 1.493,66 para 1.793,66/mês: o prazo cai de 41 para 34 meses (−7), dentro da capacidade (folga 695,78) |
| 7 | Há dívidas que reduzem a capacidade de realizar o objetivo? | `dividas_e_parcelas` | sim, temporariamente: 6 parcelas ativas somam 35,35% da renda média, puxadas por uma parcela de IPTU de 2.256,42 (4 meses restantes); juros pagos 56,07/mês em média | não relevantes: 6 parcelas ativas somam 1,47% da renda média (maior 42,01/mês); juros pagos 60,51/mês em média |
| 8 | Quais produtos do banco são adequados para este objetivo? | catálogo curado (`contracts/catalogo_produtos.json`, RAG do 002), sem cálculo | Reserva por objetivo para a meta e a reserva. Controle de Gastos para os cortes da linha 3. Crédito Imobiliário e Consórcio de Imóveis como caminhos alternativos. CDB/renda fixa e LCI/LCA só com perfil e fonte atual. **Nenhuma taxa**: rentabilidade e condições vêm da fonte oficial | igual |

## Observações

- **Cortes e AC-05.** Em 202506, todas as funções só enxergam janeiro a junho (`fonte.periodo`
  = 202501–202506). A mesma pergunta muda de resposta com o corte, e isso é esperado:
  - no segundo semestre, a sobra do âncora cresce;
  - o IPTU parcelado termina.
- **Pergunta 4.** "Quanto falta" usa o saldo atual (`usar_saldo_atual=True`), que o
  cliente escolhe usar ou não. Sem o saldo, a resposta é a da linha 5.
- **Pergunta 5.** Em 202512, o objetivo fica a R$ 10,56/mês de caber. O agente deve dizer
  "por pouco, não" e oferecer os cenários, sem arredondar para "cabe".
- **Goldens.** Os goldens de `comparar_cenarios` (`contracts/fixtures`) usam a entrada
  canônica R$ 30.000 em 24 meses, não os R$ 60.000 da demo. O acelerado de 202506 do
  golden é 1.660,85 → 19 meses.
- **Controle.** O controle (`31e94f2f…`) não aparece aqui. Os testes TS-05 garantem que
  as linhas dele nunca se misturam com as do âncora.
