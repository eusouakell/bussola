-- Bússola: contratos v1 §3, dataset bussola_rag (corpus do RAG).
-- Escrita: ciclo 002. Aplicado por data/scripts/aplicar_ddl.py (idempotente).
-- ARRAY não aceita NOT NULL no BigQuery (um array vazio equivale a nulo).

CREATE SCHEMA IF NOT EXISTS bussola_rag OPTIONS (location = "us-central1");

CREATE TABLE IF NOT EXISTS bussola_rag.documentos (
  doc_id STRING NOT NULL,
  id_usuario STRING,
  tipo STRING NOT NULL,
  anomes INT64,
  texto STRING NOT NULL,
  fonte JSON NOT NULL,
  embedding ARRAY<FLOAT64>,
  modelo_embedding STRING NOT NULL,
  gerado_em TIMESTAMP NOT NULL
);
