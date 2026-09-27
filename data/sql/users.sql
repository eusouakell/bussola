-- Bússola 001: bussola_dados.users (personas do login simulado; contratos §3).
-- As linhas chegam só pelo parâmetro @usuarios (ARRAY<STRUCT<...>>), montado por
-- data/scripts/build_dados.py a partir de contracts/fixtures/bussola_dados/users.json
-- depois de validar cada id_usuario (UUID v4 e presente no extrato). Sem senha nem hash.

BEGIN TRANSACTION;

TRUNCATE TABLE {{dataset}}.users;

INSERT INTO {{dataset}}.users (login, id_usuario, display_name, summary, featured)
SELECT u.login, u.id_usuario, u.display_name, u.summary, u.featured
FROM UNNEST(@usuarios) AS u;

COMMIT TRANSACTION;
