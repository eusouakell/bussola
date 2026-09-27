-- Bússola 001: bussola_dados.referencia_coorte (P1; contratos §3; ciclo 001 §3.1).
-- Média e mediana do gasto mensal por faixa de renda × macro, entre todos os usuários.
-- Roda depois de perfil_mensal e gastos_categoria, que são a base.
--
-- - faixa_renda: renda média mensal do usuário no ano, com limites inferiores
--   inclusivos (3 mil, 6 mil, 10 mil e 20 mil);
-- - gasto mensal do usuário na macro = Σ gastos da macro ÷ meses com lançamento;
-- - entram só os usuários com gasto na macro (sem zeros para quem não gasta);
-- - grupos com menos de 5 usuários não são publicados. Nunca há dado individual.

BEGIN TRANSACTION;

TRUNCATE TABLE {{dataset}}.referencia_coorte;

INSERT INTO {{dataset}}.referencia_coorte (faixa_renda, macro, media, mediana, qtd_usuarios)
WITH usuarios AS (
  SELECT id_usuario, AVG(renda) AS renda_media, COUNT(*) AS meses
  FROM {{dataset}}.perfil_mensal
  GROUP BY id_usuario
),
gastos AS (
  SELECT id_usuario, macro, SUM(total) AS total
  FROM {{dataset}}.gastos_categoria
  GROUP BY id_usuario, macro
),
por_usuario AS (
  SELECT
    CASE
      WHEN u.renda_media < 3000 THEN 'ate_3k'
      WHEN u.renda_media < 6000 THEN '3k_6k'
      WHEN u.renda_media < 10000 THEN '6k_10k'
      WHEN u.renda_media < 20000 THEN '10k_20k'
      ELSE 'acima_20k'
    END AS faixa_renda,
    g.macro,
    g.total / u.meses AS media_mensal
  FROM gastos AS g
  JOIN usuarios AS u USING (id_usuario)
),
estatisticas AS (
  SELECT
    faixa_renda,
    macro,
    media_mensal,
    PERCENTILE_CONT(media_mensal, 0.5) OVER (PARTITION BY faixa_renda, macro) AS mediana
  FROM por_usuario
)
SELECT
  faixa_renda,
  macro,
  ROUND(AVG(media_mensal), 2) AS media,
  ROUND(ANY_VALUE(mediana), 2) AS mediana,
  COUNT(*) AS qtd_usuarios
FROM estatisticas
GROUP BY faixa_renda, macro
HAVING COUNT(*) >= 5;

COMMIT TRANSACTION;
