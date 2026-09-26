# Modelos validados no ciclo 000

Gerado por `deploy/smoke_modelos.py` (FR-021, research R-17) com as
credenciais ADC de um integrante.

- Data: 2026-09-26 19:11 UTC
- Projeto: `batalha-time-07-lkbv`
- Locais do Vertex testados: `us-central1`, `global`

## Resultado

| Variável | Modelo | Via | Local | Latência (ms) | Dimensão |
|---|---|---|---|---|---|
| `BUSSOLA_MODEL` | `gemini-3.8-flash` | vertex | global | 2416 | - |
| `EMBEDDING_MODEL` | `gemini-embedding-001` | vertex | us-central1 | 1153 | 3072 |

## Implicações

- O Flash só respondeu em `global`: no deploy do agente use `BUSSOLA_LOCAL_MODELO=global`.
- Dimensão do embedding `gemini-embedding-001`: 3072. O índice do RAG (002) grava `embeddings.npy` com essa dimensão e registra `modelo_embedding` e `dimensao` no `manifesto.json` (Q-17).
- O local do agente virou a variável `BUSSOLA_LOCAL_MODELO=global` (contratos §7, Q-15 em [`questoes.md`](./questoes.md)).
- Este teste usa as credenciais do integrante. A SA de runtime do Cloud Run pode não ter o mesmo acesso (ver o deploy hello).

## Listagem de modelos

- vertex / `us-central1`: 133 modelos. Flash listados: `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.7-flash`, `gemini-3.8-flash`. Embeddings: `gemini-embedding-001`, `gemini-embedding-2`, `text-embedding-005`, `text-embedding-large-exp-03-07`, `text-multilingual-embedding-002`.
- vertex / `global`: 27 modelos. Flash listados: `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.7-flash`, `gemini-3.8-flash`. Embeddings: `gemini-embedding-2`.

## Tentativas

| Tipo | Modelo | Via | Local | Resultado | Latência (ms) | Dimensão | Detalhe |
|---|---|---|---|---|---|---|---|
| flash | `gemini-3.8-flash` | vertex | us-central1 | falha | - | - | 404 NOT_FOUND: Publisher model `projects/batalha-time-07-lkbv/locations/us-central1/publishers/google/models/gemini-3.8-flash` was not found or your project doe |
| flash | `gemini-3.7-flash` | vertex | us-central1 | falha | - | - | 404 NOT_FOUND: Publisher model `projects/batalha-time-07-lkbv/locations/us-central1/publishers/google/models/gemini-3.7-flash` was not found or your project doe |
| flash | `gemini-3.5-flash` | vertex | us-central1 | falha | - | - | 404 NOT_FOUND: Publisher model `projects/batalha-time-07-lkbv/locations/us-central1/publishers/google/models/gemini-3.5-flash` was not found or your project doe |
| embedding | `gemini-embedding-001` | vertex | us-central1 | ok | 1153 | 3072 | - |
| embedding | `gemini-embedding-2` | vertex | us-central1 | falha | - | - | 404 NOT_FOUND: Publisher model `projects/batalha-time-07-lkbv/locations/us-central1/publishers/google/models/gemini-embedding-2` was not found or your project d |
| embedding | `text-embedding-005` | vertex | us-central1 | ok | 1003 | 768 | - |
| embedding | `text-embedding-large-exp-03-07` | vertex | us-central1 | ok | 1280 | 3072 | - |
| embedding | `text-multilingual-embedding-002` | vertex | us-central1 | ok | 1039 | 768 | - |
| flash | `gemini-3.8-flash` | vertex | global | ok | 2416 | - | ok |
| flash | `gemini-3.7-flash` | vertex | global | ok | 1856 | - | ok |
| flash | `gemini-3.5-flash` | vertex | global | ok | 1815 | - | ok |
| embedding | `gemini-embedding-001` | vertex | global | ok | 11198 | 3072 | - |
| embedding | `gemini-embedding-2` | vertex | global | ok | 753 | 3072 | - |
