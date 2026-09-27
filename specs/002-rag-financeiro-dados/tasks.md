# Tasks: RAG de conhecimento financeiro

**Input**: `specs/002-rag-financeiro-dados/` (spec.md, plan.md)

**Tests**: obrigatórios (constituição IX), todos offline no `make test`.

## Format: `[ID] [P?] [Story] Descrição`

## Phase 1: Setup

- [x] T001 `uv add google-genai` (runtime) e `uv add --dev pyyaml` em `mcp_server/`; marcador `gemini` no `pyproject.toml` (FR-009, FR-012)
- [x] T002 Makefile: lint de `data/rag` e `eval/rag`; `make test` exclui `gemini`; alvos `validar-corpus`, `indice`, `indice-embeddings`, `eval-rag` e `test-gemini` (FR-004, FR-005, FR-011, FR-012)

## Phase 2: Foundational

- [x] T003 `bussola_mcp/rag/text.py`: normalização, stopwords e radical leve pt-BR (FR-007)
- [x] T004 `bussola_mcp/rag/corpus.py`: parser do Markdown + validação (FR-001, FR-004)
- [x] T005 `bussola_mcp/rag/index.py`: manifesto, hash canônico, carga e `InvalidIndexError` (FR-005, FR-006)
- [x] T006 `bussola_mcp/rag/embedding.py`: porta `Embedder`, `GeminiEmbedder`, `EmbeddingUnavailableError` (FR-009)

## Phase 3: US2 Corpus e índice (P0)

- [x] T007 [P] [US2] Corpus `norma_bacen` (FR-002)
- [x] T008 [P] [US2] Corpus `credito` (FR-002)
- [x] T009 [P] [US2] Corpus `boas_praticas` (FR-002)
- [x] T010 [P] [US2] Corpus `produto`: 8 documentos do catálogo (FR-003)
- [x] T011 [US2] `data/rag/validar_corpus.py` (FR-004)
- [x] T012 [US2] `data/rag/indexar.py` idempotente, com `--sem-embeddings` (FR-005)
- [x] T013 [US2] Gerar e versionar o índice (FR-006)
- [x] T014 [US2] Testes: validador, parser, indexação idempotente, índice versionado (FR-004–FR-006)

## Phase 4: US1/US3 Buscadores (P0)

- [x] T015 [US1] `lexical.py`: `BuscadorLexico` (FR-007)
- [x] T016 [US3] `vector.py`: `BuscadorNumpy` (FR-008)
- [x] T017 [US3] `__init__.py`: `criar_buscador` (FR-010)
- [x] T018 [US1] [US3] Testes de unidade dos buscadores e do embedder (FR-007–FR-010)
- [x] T019 [US3] Teste de integração via Protocol, como a ferramenta usa, e contrato `Trecho` (FR-010, FR-012)
- [x] T020 [US3] Teste marcado `gemini` (fora do `make test`) (FR-012)

## Phase 5: US4 Avaliação (P1)

- [x] T021 [US4] `eval/rag/perguntas.yaml` (10 ou mais, 2 ou mais de produto, negativas) (FR-011)
- [x] T022 [US4] `eval/rag/rodar_eval.py` + calibragem dos limiares (FR-011)
- [x] T023 [US4] `eval/rag/RESULTADOS.md` (FR-011, SC-003)
- [x] T024 [US4] Teste do eval léxico e dos negativos no `make test` (FR-011)

## Phase 6: Polish

- [x] T025 `make lint` + `make test` verdes (SC-004)
- [x] T026 `traceability.md` e tarefas marcadas
