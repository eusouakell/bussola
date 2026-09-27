# Bússola: targets comuns (contratos §2). Acréscimos de outros ciclos: por união.
.PHONY: test lint format mcp agent fixtures test-bq

# .env local (não versionado) é opcional.
ifneq (,$(wildcard .env))
include .env
export
endif

MCP_PORT ?= 8080
AGENT_PORT ?= 8000
# shellcheck do sistema (o runner ubuntu do CI já tem); sem ele, o shellcheck-py pelo uvx.
SHELLCHECK ?= $(shell command -v shellcheck 2>/dev/null || echo "uvx --from shellcheck-py==0.11.0.1 shellcheck")

test:
	cd mcp_server && BUSSOLA_FAKES=TRUE uv run pytest -m "not bq"
	cd agent && BUSSOLA_FAKES=TRUE uv run pytest -m "not bq"
	cd agent && BUSSOLA_FAKES=TRUE uv run pytest ../deploy/tests -p no:cacheprovider

lint:
	cd mcp_server && uv run ruff check . ../data/scripts && uv run ruff format --check . ../data/scripts
	cd agent && uv run ruff check . ../deploy && uv run ruff format --check . ../deploy
	cd agent && uv run ruff check ../eval/agente && uv run ruff format --check ../eval/agente
	$(SHELLCHECK) deploy/*.sh
	cd mcp_server && uv run ruff check ../data/rag ../eval/rag && uv run ruff format --check ../data/rag ../eval/rag

format:
	cd mcp_server && uv run ruff check --fix . ../data/scripts && uv run ruff format . ../data/scripts
	cd agent && uv run ruff check --fix . ../deploy && uv run ruff format . ../deploy
	cd agent && uv run ruff check --fix ../eval/agente && uv run ruff format ../eval/agente
	cd mcp_server && uv run ruff check --fix ../data/rag ../eval/rag && uv run ruff format ../data/rag ../eval/rag

mcp:
	cd mcp_server && BUSSOLA_FAKES=$${BUSSOLA_FAKES:-TRUE} PORT=$(MCP_PORT) uv run python -m bussola_mcp.server

agent:
	cd agent && GOOGLE_CLOUD_LOCATION=$${BUSSOLA_LOCAL_MODELO:-global} GOOGLE_API_USE_CLIENT_CERTIFICATE=$${GOOGLE_API_USE_CLIENT_CERTIFICATE:-false} uv run adk web --port $(AGENT_PORT) .

fixtures:
	cd mcp_server && uv run python ../data/scripts/gerar_fixtures.py --saida ../contracts/fixtures

# Fixtures v1 (ciclo 001): só lê bussola_dados (ADC + GOOGLE_CLOUD_PROJECT) e preserva
# bussola_dados/users.json e rag/. O conjunto provisório continua em `make fixtures`.
.PHONY: fixtures-v1
fixtures-v1:
	cd mcp_server && uv run python ../data/scripts/build_dados.py --fixtures ../contracts/fixtures

# Exit code 5 = nenhum teste bq coletado (aceito).
test-bq:
	cd mcp_server && uv run pytest -m bq; s=$$?; [ $$s -eq 0 ] || [ $$s -eq 5 ]
	cd agent && uv run pytest -m bq; s=$$?; [ $$s -eq 0 ] || [ $$s -eq 5 ]

# --- RAG de conhecimento (ciclo 002). ---
.PHONY: validar-corpus indice indice-embeddings eval-rag test-gemini

validar-corpus:
	cd mcp_server && uv run python ../data/rag/validar_corpus.py

# Só trechos + manifesto (backend lexico), sem GCP.
indice:
	cd mcp_server && uv run python ../data/rag/indexar.py --sem-embeddings

# Com embeddings (backend numpy). Plano B: GOOGLE_GENAI_USE_VERTEXAI=FALSE e
# GOOGLE_API_KEY passado inline na linha de comando, nunca gravado.
indice-embeddings:
	cd mcp_server && uv run python ../data/rag/indexar.py

# Top-3 dos dois backends, offline (cache de perguntas versionado).
eval-rag:
	cd mcp_server && uv run python ../eval/rag/rodar_eval.py --resultados ../eval/rag/RESULTADOS.md

# Chama a API real do Gemini (fora do make test); exige credencial no ambiente.
test-gemini:
	cd mcp_server && BUSSOLA_TESTE_GEMINI=TRUE uv run pytest -m gemini tests/rag

# --- Front web (ciclo 008). Node 24 + npm; sem rede depois do web-install. ---
.PHONY: web-install web web-lint web-test web-build bff

web-install:
	cd web && npm ci --no-audit --no-fund

web:
	cd web && npm run dev

web-lint:
	cd web && npm run lint

web-test:
	cd web && npm test

# Inclui a varredura do bundle (segredos, SQL, projeto, UUID completo).
web-build:
	cd web && npm run build

# BFF (web/bff) em :8080; precisa de AUTH_PASSWORD_HASH (npm run hash-password).
bff:
	cd web && npm run bff

# --- Deploy com Helm (templater para Cloud Run; sem GKE). ---
.PHONY: helm-lint test-helm

HELM_CHART := deploy/helm/bussola

helm-lint:
	helm lint $(HELM_CHART) --set release.tag=c999 --set release.revisionSuffix=lint

# Renderiza o chart e valida as regras de plataforma (sem rede, sem GCP).
test-helm:
	cd agent && uv run pytest ../deploy/tests -p no:cacheprovider

# --- Eval do agente (ciclo 004): números com fonte (AC-08). ---
# Offline: roteiro no lugar do modelo, mock do 000 local (também roda no make test).
# Ao vivo: Gemini real; a chave é lida do Secret Manager na hora e nunca impressa.
.PHONY: eval-agente eval-agente-ao-vivo

eval-agente:
	cd agent && uv run python ../eval/agente/rodar_eval.py --modo offline

eval-agente-ao-vivo:
	cd agent && GOOGLE_GENAI_USE_VERTEXAI=FALSE GOOGLE_API_KEY="$$(gcloud secrets versions access latest --secret=gemini-api-key --project $${GOOGLE_CLOUD_PROJECT:-batalha-time-07-lkbv})" uv run python ../eval/agente/rodar_eval.py --modo ao-vivo

# --- Smoke de produção (ciclo 007). Só leitura; precisa de gcloud autenticado e
# roles/iam.serviceAccountTokenCreator na SA. Ex.: make smoke SMOKE_ARGS="--tag c007".
.PHONY: smoke

SMOKE_ARGS ?=

smoke:
	cd agent && uv run python ../deploy/smoke.py $(SMOKE_ARGS)
