-- Bússola 001: bussola_dados.entradas_categoria (contratos §3; ciclo 001 §3.1).
-- Entradas (tipo = 'E') por usuário, mês, macro e micro: total (NUMERIC, 2 casas) e qtd.

BEGIN TRANSACTION;

TRUNCATE TABLE {{dataset}}.entradas_categoria;

INSERT INTO {{dataset}}.entradas_categoria (id_usuario, anomes, macro, micro, total, qtd)
SELECT
  LOWER(id_usuario) AS id_usuario,
  anomes,
  nom_cate_macro AS macro,
  nom_cate_micro AS micro,
  CAST(ROUND(SUM(CAST(vlr AS NUMERIC)), 2) AS FLOAT64) AS total,
  COUNT(*) AS qtd
FROM `hackathon_dados.extrato_sintetico`
WHERE tipo = 'E' AND anomes BETWEEN 202501 AND 202512
GROUP BY id_usuario, anomes, macro, micro;

COMMIT TRANSACTION;
