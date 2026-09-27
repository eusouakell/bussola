-- Bússola 001: bussola_dados.gastos_categoria (contratos §3; ciclo 001 §3.1).
-- Saídas (tipo = 'S') por usuário, mês, macro e micro: total (NUMERIC, 2 casas) e qtd.

BEGIN TRANSACTION;

TRUNCATE TABLE {{dataset}}.gastos_categoria;

INSERT INTO {{dataset}}.gastos_categoria (id_usuario, anomes, macro, micro, total, qtd)
SELECT
  LOWER(id_usuario) AS id_usuario,
  anomes,
  nom_cate_macro AS macro,
  nom_cate_micro AS micro,
  CAST(ROUND(SUM(CAST(vlr AS NUMERIC)), 2) AS FLOAT64) AS total,
  COUNT(*) AS qtd
FROM `hackathon_dados.extrato_sintetico`
WHERE tipo = 'S' AND anomes BETWEEN 202501 AND 202512
GROUP BY id_usuario, anomes, macro, micro;

COMMIT TRANSACTION;
