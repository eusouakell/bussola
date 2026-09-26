# Bússola: imagem do agente ADK (serviço Cloud Run `bussola-agent`).
#
# O contexto de build é a RAIZ do repositório, como no MCP (research R-15).
# O BuildKit usa `agent/Dockerfile.dockerignore`.
#
#   docker buildx build --platform linux/amd64 -f agent/Dockerfile .
#
# Publicação: `deploy/build_push.sh agent`.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

LABEL org.opencontainers.image.title="bussola-agent"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PORT=8080

# Usuário sem privilégios; o código fica com dono root e só leitura para ele.
RUN groupadd --system --gid 10001 bussola \
    && useradd --system --uid 10001 --gid bussola --create-home --home-dir /home/bussola bussola

# /app/agent é o AGENTS_DIR do ADK: cada subdiretório (bussola_agent) é um agente.
WORKDIR /app/agent

# 1) Dependências: camada que só muda quando pyproject/uv.lock mudam.
COPY agent/pyproject.toml agent/uv.lock agent/.python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 2) Código do serviço.
COPY agent/ /app/agent/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/agent/.venv/bin:${PATH}"

USER bussola:bussola

EXPOSE 8080

# ADK Web UI em $PORT. Sessão, artefatos e memória em memória (mestre §13:
# InMemorySessionService com max-instances=1); nada é gravado no disco da imagem.
CMD ["sh", "-c", "exec adk web --host 0.0.0.0 --port \"${PORT:-8080}\" --session_service_uri memory:// --artifact_service_uri memory:// --memory_service_uri memory:// /app/agent"]
