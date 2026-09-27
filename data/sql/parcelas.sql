-- Bússola 001: bussola_dados.parcelas (contratos §3; ciclo 001 §3.1).
-- Um lançamento por linha, para todo lançamento com parcela_total > 1 e parcela_atual
-- informada (sem filtro de tipo). As parcelas vêm como FLOAT na origem e viram INT64.

BEGIN TRANSACTION;

TRUNCATE TABLE {{dataset}}.parcelas;

INSERT INTO {{dataset}}.parcelas (
  id_usuario, anomes, descr, macro, parcela_atual, parcela_total, vlr
)
SELECT
  LOWER(id_usuario) AS id_usuario,
  anomes,
  descr,
  nom_cate_macro AS macro,
  CAST(ROUND(parcela_atual) AS INT64) AS parcela_atual,
  CAST(ROUND(parcela_total) AS INT64) AS parcela_total,
  CAST(ROUND(CAST(vlr AS NUMERIC), 2) AS FLOAT64) AS vlr
FROM `hackathon_dados.extrato_sintetico`
WHERE ROUND(parcela_total) > 1
  AND parcela_atual IS NOT NULL
  AND anomes BETWEEN 202501 AND 202512;

COMMIT TRANSACTION;
