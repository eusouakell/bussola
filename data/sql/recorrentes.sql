-- Bússola 001: bussola_dados.recorrentes (contratos §3; ciclo 001 §3.1).
-- Saídas cuja descr normalizada aparece em >= 3 meses distintos do ano, por usuário.
-- Uma linha por usuário, mês, descr_norm, macro e micro, com valor = soma do mês.
--
-- descr_norm: minúsculas, sem marcação de parcela ("parc 1/12", "parcela 2 de 10") nem
-- datas ("05/03", "05/03/2025", "2025-03-05"), espaços simples, sem espaço nas pontas.
-- A tabela marca a recorrência no ano todo. O RepositorioBigQuery reaplica o critério
-- só com os meses <= ate_anomes, para não vazar o futuro (plan.md D-05).

BEGIN TRANSACTION;

TRUNCATE TABLE {{dataset}}.recorrentes;

INSERT INTO {{dataset}}.recorrentes (id_usuario, anomes, descr_norm, macro, micro, valor)
WITH saidas AS (
  SELECT
    LOWER(id_usuario) AS id_usuario,
    anomes,
    nom_cate_macro AS macro,
    nom_cate_micro AS micro,
    CAST(vlr AS NUMERIC) AS vlr_num,
    TRIM(
      REGEXP_REPLACE(
        REGEXP_REPLACE(
          REGEXP_REPLACE(
            LOWER(descr), r'\bparc(?:ela)?\.?\s*\d{1,3}\s*(?:/|de)\s*\d{1,3}\b', ' '
          ),
          r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b',
          ' '
        ),
        r'\s+',
        ' '
      )
    ) AS descr_norm
  FROM `hackathon_dados.extrato_sintetico`
  WHERE tipo = 'S' AND anomes BETWEEN 202501 AND 202512
),
recorrencia AS (
  SELECT id_usuario, descr_norm
  FROM saidas
  WHERE descr_norm != ''
  GROUP BY id_usuario, descr_norm
  HAVING COUNT(DISTINCT anomes) >= 3
)
SELECT
  s.id_usuario,
  s.anomes,
  s.descr_norm,
  s.macro,
  s.micro,
  CAST(ROUND(SUM(s.vlr_num), 2) AS FLOAT64) AS valor
FROM saidas AS s
JOIN recorrencia AS r USING (id_usuario, descr_norm)
GROUP BY s.id_usuario, s.anomes, s.descr_norm, s.macro, s.micro;

COMMIT TRANSACTION;
