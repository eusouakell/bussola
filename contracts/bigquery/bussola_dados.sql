-- Bússola: contratos v1 §3, dataset bussola_dados (métricas determinísticas).
-- Escrita: ciclo 001. Leitura: todos. Aplicado por data/scripts/aplicar_ddl.py (idempotente).
-- Colunas sem "NULL" explícito no contrato são NOT NULL.

CREATE SCHEMA IF NOT EXISTS bussola_dados OPTIONS (location = "us-central1");

CREATE TABLE IF NOT EXISTS bussola_dados.perfil_mensal (
  id_usuario STRING NOT NULL,
  anomes INT64 NOT NULL,
  renda FLOAT64 NOT NULL,
  gasto FLOAT64 NOT NULL,
  sobra FLOAT64 NOT NULL,
  saldo_inicial FLOAT64 NOT NULL,
  saldo_final FLOAT64 NOT NULL,
  saldo_minimo FLOAT64 NOT NULL,
  saldo_maximo FLOAT64 NOT NULL,
  juros FLOAT64 NOT NULL
);

CREATE TABLE IF NOT EXISTS bussola_dados.gastos_categoria (
  id_usuario STRING NOT NULL,
  anomes INT64 NOT NULL,
  macro STRING NOT NULL,
  micro STRING NOT NULL,
  total FLOAT64 NOT NULL,
  qtd INT64 NOT NULL
);

CREATE TABLE IF NOT EXISTS bussola_dados.entradas_categoria (
  id_usuario STRING NOT NULL,
  anomes INT64 NOT NULL,
  macro STRING NOT NULL,
  micro STRING NOT NULL,
  total FLOAT64 NOT NULL,
  qtd INT64 NOT NULL
);

CREATE TABLE IF NOT EXISTS bussola_dados.recorrentes (
  id_usuario STRING NOT NULL,
  anomes INT64 NOT NULL,
  descr_norm STRING NOT NULL,
  macro STRING NOT NULL,
  micro STRING NOT NULL,
  valor FLOAT64 NOT NULL
);

CREATE TABLE IF NOT EXISTS bussola_dados.parcelas (
  id_usuario STRING NOT NULL,
  anomes INT64 NOT NULL,
  descr STRING NOT NULL,
  macro STRING NOT NULL,
  parcela_atual INT64 NOT NULL,
  parcela_total INT64 NOT NULL,
  vlr FLOAT64 NOT NULL
);

CREATE TABLE IF NOT EXISTS bussola_dados.categorias (
  macro STRING NOT NULL,
  micro STRING NOT NULL,
  discricionaria BOOL NOT NULL,
  corte_max_pct FLOAT64 NOT NULL
);

CREATE TABLE IF NOT EXISTS bussola_dados.referencia_coorte (
  faixa_renda STRING NOT NULL,
  macro STRING NOT NULL,
  media FLOAT64 NOT NULL,
  mediana FLOAT64 NOT NULL,
  qtd_usuarios INT64 NOT NULL
);

-- Personas do login simulado (web/bff). Uma linha por massa sintética; sem senha
-- nem hash (o hash fica só no Secret Manager). Carga: data/scripts/build_dados.py.
CREATE TABLE IF NOT EXISTS bussola_dados.users (
  login STRING NOT NULL,
  id_usuario STRING NOT NULL,
  display_name STRING NOT NULL,
  summary STRING NOT NULL,
  featured BOOL NOT NULL
);
