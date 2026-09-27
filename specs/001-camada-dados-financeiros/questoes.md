# Questões e premissas do ciclo 001

O ciclo roda sem perguntas ao usuário. Cada ponto abaixo foi decidido pela linha de
corte ([docs/ciclos/README.md §3](../../docs/ciclos/README.md)) e fica aberto para
revisão humana.

| ID | Questão | Decisão adotada | Classificação | Quem revisa |
|---|---|---|---|---|
| Q-01 | Seleção de discricionárias e `corte_max_pct` do seed (ciclo §10) | Seed em `data/sql/seed_categorias.sql`: 0,5 em assinaturas e delivery; 0,3 em restaurantes, lazer e compras; 0,2 em padaria, clubes, infantis e viagens. As essenciais ficam com 0 (plan.md D-06) | INFERRED | Produto e dados |
| Q-02 | Lista de microcategorias de juros (ciclo §10) | Micro normalizada com palavra iniciada por "juros" (D-04). No âncora dá 60,51/mês, contra 61 no §8 | INFERRED | Dados |
| Q-03 | Percentuais dos cenários (Q2 do mestre) | Proposta do §4: 40/60/80% da sobra mediana, sempre via `RegrasCenario`. Nada fixo no código | UNRESOLVED | Q2 do mestre |
| Q-04 | Entrada da demo | R$ 60.000 em 24 meses. "+R$ 300/mês" soma 300 ao aporte do cenário equilibrado ([perguntas-ancora.md](./perguntas-ancora.md)) | INFERRED | Produto |
| Q-05 | `CREATE OR REPLACE` (ciclo §3.2) contra o DDL `NOT NULL` do contrato | `TRUNCATE`+`INSERT` em transação, igualmente idempotente (D-01). É desvio consciente do texto do ciclo | INFERRED | 003 (consumidor) |
| Q-06 | Regra de `saldo_inicial`/`saldo_final` em empates de `anomesdia` | Cadeia de `saldo_apos` com fim do dia (D-03). Muda `saldo_inicial` do âncora em 21,05 em 202506 e 202512, em relação às fixtures do 000 | INFERRED | Dados |
| Q-07 | Recorrência sem vazar o futuro | O repositório reaplica o critério de ≥ 3 meses só sobre as linhas `≤ ate_anomes` (D-05). O `RepositorioFake` (congelado) não reaplica | INFERRED | 003 |
| Q-08 | Faixa de renda da coorte | Pela renda média dos meses `≤ ate_anomes` (`metricas.income_band`), com os limites do 000 (3k/6k/10k/20k) | INFERRED | 003 |
| Q-09 | `web/fixtures/goldens.json` é cópia dos goldens | O 001 não edita `web/`. Depois das fixtures v1, o dono do web roda `npm run fixtures` | EXPLICIT (propriedade) | Web |
| Q-10 | `make fixtures` (000) regenera as fixtures provisórias e sobrescreveria as v1 | Novo alvo `make fixtures-v1` (acréscimo ao Makefile). `make fixtures` fica como está; o README do 000 pode apontar para o novo alvo depois do merge | INFERRED | 000/007 |
| Q-11 | Pergunta 8 (produtos do banco) | Não é numérica. É respondida pelo catálogo curado (`docs/catalogo/`, tema `produto` do RAG do 002), sem taxas | EXPLICIT | 002 |
