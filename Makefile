# Bússola: targets comuns (contratos §2). Acréscimos de outros ciclos: por união.
.PHONY: test lint format mcp agent fixtures test-bq

# .env local (não versionado) é opcional.
ifneq (,$(wildcard .env))
include .env
export
endif

MCP_PORT ?= 8080
AGENT_PORT ?= 8000

test:
	cd mcp_server && BUSSOLA_FAKES=TRUE uv run pytest -m "not bq"
	cd agent && BUSSOLA_FAKES=TRUE uv run pytest -m "not bq"

lint:
	cd mcp_server && uv run ruff check . ../data/scripts && uv run ruff format --check . ../data/scripts
	cd agent && uv run ruff check . ../deploy && uv run ruff format --check . ../deploy

format:
	cd mcp_server && uv run ruff check --fix . ../data/scripts && uv run ruff format . ../data/scripts
	cd agent && uv run ruff check --fix . ../deploy && uv run ruff format . ../deploy

mcp:
	cd mcp_server && BUSSOLA_FAKES=$${BUSSOLA_FAKES:-TRUE} PORT=$(MCP_PORT) uv run python -m bussola_mcp.server

agent:
	cd agent && GOOGLE_CLOUD_LOCATION=$${BUSSOLA_LOCAL_MODELO:-global} GOOGLE_API_USE_CLIENT_CERTIFICATE=$${GOOGLE_API_USE_CLIENT_CERTIFICATE:-false} uv run adk web --port $(AGENT_PORT) .

fixtures:
	cd mcp_server && uv run python ../data/scripts/gerar_fixtures.py --saida ../contracts/fixtures

# Exit code 5 = nenhum teste bq coletado (aceito).
test-bq:
	cd mcp_server && uv run pytest -m bq; s=$$?; [ $$s -eq 0 ] || [ $$s -eq 5 ]
	cd agent && uv run pytest -m bq; s=$$?; [ $$s -eq 0 ] || [ $$s -eq 5 ]
