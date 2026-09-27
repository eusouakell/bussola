# Proposta de constituição (ciclo 001)

A constituição está congelada (`contratos-v1`). Nada aqui foi aplicado.

## Proposta P-01: nomes mistos por decisão do usuário (princípio VIII)

- **Situação:** o princípio VIII pede identificadores em português (domínio) ou inglês
  técnico, "com consistência dentro de cada módulo". A decisão do usuário para os
  ciclos manda outra coisa:
  - nomes fixados pelo contrato ficam como estão, em português
    (`prazo_para_meta`, `ResultadoPrazo`, `RepositorioBigQuery`, `perfil_financeiro`);
  - módulos, classes e funções novos, que o contrato não nomeia, ficam em inglês
    técnico (`MetricResult`, `income_band`, `rank_opportunities`, `READ_MODES`).

  Por isso, `simulacao.py`, `metricas.py` e `repositorio_bq.py` misturam os dois idiomas.
- **Proposta:** acrescentar ao VIII: "Nomes definidos em `contratos.md` prevalecem.
  Nomes novos seguem inglês técnico, mesmo em módulo cujo nome é fixado em português".
- **Impacto:** nenhum código muda. A proposta só formaliza a regra já seguida.

## Sem outras propostas

Os princípios I–VII, IX e X foram seguidos sem conflito:

- **I:** os números saem de funções puras.
- **III:** o SQL é parametrizado e o escopo por cliente é validado.
- **IV:** o corte temporal é testado por métrica.
- **IX:** os testes rodam sem rede, e os testes com BigQuery real levam o marcador `bq`.
- **X:** as mudanças de contrato estão em commits `contracts:` separados.
