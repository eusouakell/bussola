-- Bússola 001: bussola_dados.perfil_mensal (contratos §3; ciclo 001 §3.1).
-- Uma linha por usuário e mês. Executado por data/scripts/build_dados.py, que troca
-- {{dataset}} pelo dataset validado. Não há texto de usuário nem parâmetro aqui.
--
-- - renda = Σ entradas; gasto = Σ saídas; sobra = renda - gasto (NUMERIC, 2 casas);
-- - juros = Σ saídas cuja micro normalizada tem uma palavra iniciada por "juros";
-- - saldo_minimo / saldo_maximo = mínimo / máximo de saldo_apos no mês;
-- - saldo_final = saldo no fim do último dia do mês com lançamento (plan.md D-03):
--   o valor de saldo_apos do dia que nenhum lançamento do dia consome como saldo
--   anterior (saldo_apos - valor com sinal). Empate: o valor que continua no dia
--   seguinte e, depois, o do lançamento mais alto na ordem estável
--   (tipo, descr, vlr, saldo_apos);
-- - saldo_inicial = saldo_final do mês anterior. No primeiro mês do usuário, é o saldo
--   anterior do primeiro lançamento (na ordem estável) cujo saldo anterior nenhum outro
--   lançamento do primeiro dia produz.

BEGIN TRANSACTION;

TRUNCATE TABLE {{dataset}}.perfil_mensal;

INSERT INTO {{dataset}}.perfil_mensal (
  id_usuario, anomes, renda, gasto, sobra, saldo_inicial, saldo_final,
  saldo_minimo, saldo_maximo, juros
)
WITH origem AS (
  SELECT
    LOWER(id_usuario) AS id_usuario,
    anomesdia,
    anomes,
    tipo,
    descr,
    vlr,
    saldo_apos,
    nom_cate_micro AS micro
  FROM `hackathon_dados.extrato_sintetico`
  WHERE anomes BETWEEN 202501 AND 202512
),
lancamentos AS (
  SELECT
    id_usuario,
    anomesdia,
    anomes,
    tipo,
    CAST(vlr AS NUMERIC) AS vlr_num,
    saldo_apos,
    saldo_apos - IF(tipo = 'E', vlr, -vlr) AS saldo_antes,
    REGEXP_CONTAINS(
      REGEXP_REPLACE(NORMALIZE(LOWER(micro), NFD), r'\p{M}', ''), r'\bjuros'
    ) AS eh_juros,
    ROW_NUMBER() OVER (
      PARTITION BY id_usuario, anomesdia ORDER BY tipo, descr, vlr, saldo_apos
    ) AS ordem
  FROM origem
),
dias AS (
  SELECT
    id_usuario,
    anomesdia,
    anomes,
    ARRAY_AGG(STRUCT(ordem, saldo_apos, saldo_antes)) AS itens
  FROM lancamentos
  GROUP BY id_usuario, anomesdia, anomes
),
dias_seq AS (
  SELECT
    id_usuario,
    anomesdia,
    anomes,
    itens,
    LEAD(itens) OVER (PARTITION BY id_usuario ORDER BY anomesdia) AS itens_seguinte,
    ROW_NUMBER() OVER (PARTITION BY id_usuario ORDER BY anomesdia) AS n_dia,
    ROW_NUMBER() OVER (PARTITION BY id_usuario, anomes ORDER BY anomesdia DESC) AS n_dia_desc
  FROM dias
),
fim_mes AS (
  SELECT
    id_usuario,
    anomes,
    COALESCE(
      (
        SELECT c.saldo
        FROM (
          SELECT ROUND(i.saldo_apos, 2) AS saldo, MAX(i.ordem) AS ordem
          FROM UNNEST(d.itens) AS i
          WHERE (
            SELECT COUNTIF(ABS(j.saldo_antes - i.saldo_apos) < 0.005) FROM UNNEST(d.itens) AS j
          ) = 0
          GROUP BY saldo
        ) AS c
        ORDER BY
          (
            SELECT COUNTIF(
              ABS(s.saldo_antes - c.saldo) < 0.005 OR ABS(s.saldo_apos - c.saldo) < 0.005
            )
            FROM UNNEST(d.itens_seguinte) AS s
          ) > 0 DESC,
          c.ordem DESC
        LIMIT 1
      ),
      (SELECT ROUND(i.saldo_apos, 2) FROM UNNEST(d.itens) AS i ORDER BY i.ordem DESC LIMIT 1)
    ) AS saldo_final
  FROM dias_seq AS d
  WHERE d.n_dia_desc = 1
),
inicio_usuario AS (
  SELECT
    id_usuario,
    COALESCE(
      (
        SELECT ROUND(i.saldo_antes, 2)
        FROM UNNEST(d.itens) AS i
        WHERE (
          SELECT COUNTIF(j.ordem != i.ordem AND ABS(j.saldo_apos - i.saldo_antes) < 0.005)
          FROM UNNEST(d.itens) AS j
        ) = 0
        ORDER BY i.ordem
        LIMIT 1
      ),
      (SELECT ROUND(i.saldo_antes, 2) FROM UNNEST(d.itens) AS i ORDER BY i.ordem LIMIT 1)
    ) AS saldo_inicial
  FROM dias_seq AS d
  WHERE d.n_dia = 1
),
mensal AS (
  SELECT
    id_usuario,
    anomes,
    ROUND(SUM(IF(tipo = 'E', vlr_num, 0)), 2) AS renda,
    ROUND(SUM(IF(tipo = 'S', vlr_num, 0)), 2) AS gasto,
    ROUND(MIN(saldo_apos), 2) AS saldo_minimo,
    ROUND(MAX(saldo_apos), 2) AS saldo_maximo,
    ROUND(SUM(IF(tipo = 'S' AND eh_juros, vlr_num, 0)), 2) AS juros
  FROM lancamentos
  GROUP BY id_usuario, anomes
)
SELECT
  m.id_usuario,
  m.anomes,
  CAST(m.renda AS FLOAT64) AS renda,
  CAST(m.gasto AS FLOAT64) AS gasto,
  CAST(m.renda - m.gasto AS FLOAT64) AS sobra,
  COALESCE(
    LAG(f.saldo_final) OVER (PARTITION BY m.id_usuario ORDER BY m.anomes), i.saldo_inicial
  ) AS saldo_inicial,
  f.saldo_final,
  m.saldo_minimo,
  m.saldo_maximo,
  CAST(m.juros AS FLOAT64) AS juros
FROM mensal AS m
JOIN fim_mes AS f USING (id_usuario, anomes)
JOIN inicio_usuario AS i USING (id_usuario);

COMMIT TRANSACTION;
