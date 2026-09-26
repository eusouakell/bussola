# Bússola: imagem do servidor MCP (serviço Cloud Run `bussola-mcp`).
#
# O contexto de build é a RAIZ do repositório, porque o mock lê as fixtures de
# `contracts/` (research R-15). O BuildKit usa `mcp_server/Dockerfile.dockerignore`.
#
#   docker buildx build --platform linux/amd64 -f mcp_server/Dockerfile .
#
# Publicação: `deploy/build_push.sh mcp`.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

LABEL org.opencontainers.image.title="bussola-mcp"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PORT=8080

# Usuário sem privilégios; o código fica com dono root e só leitura para ele.
RUN groupadd --system --gid 10001 bussola \
    && useradd --system --uid 10001 --gid bussola --create-home --home-dir /home/bussola bussola

# Mesmo layout do repositório: /app/mcp_server e /app/contracts.
WORKDIR /app/mcp_server

# 1) Dependências: camada que só muda quando pyproject/uv.lock mudam.
COPY mcp_server/pyproject.toml mcp_server/uv.lock mcp_server/.python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 2) Contratos (DDL, env.example e, quando existirem, fixtures) e código do serviço.
COPY contracts/ /app/contracts/
COPY mcp_server/ /app/mcp_server/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/mcp_server/.venv/bin:${PATH}"

USER bussola:bussola

EXPOSE 8080

# Forma shell só para expandir ${PORT}; `exec` mantém o Python como PID 1 (SIGTERM).
CMD ["sh", "-c", "exec python -m bussola_mcp.server --host 0.0.0.0 --port \"${PORT:-8080}\""]
