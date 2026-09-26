# Quickstart: Fundação e contratos

## Pré-requisitos

- `uv` ≥ 0.11 e `make`.
- Opcionais para a plataforma: Docker com buildx e `gcloud`.

## Verificação local (sem rede, sem GCP)

```bash
make lint
make test          # BUSSOLA_FAKES=TRUE, os dois projetos
```

## MCP mock + agente hello

```bash
make mcp           # terminal 1: http://localhost:8080/mcp
make agent         # terminal 2: ADK Web em http://localhost:8000
```

- O agente usa `MCP_URL=http://localhost:8080/mcp` por padrão.
- O modelo vem de `BUSSOLA_MODEL` (ver `contracts/env.example`).
- O LLM precisa de credencial: Vertex (ADC) ou `GOOGLE_API_KEY` no `.env`
  local, que não é versionado.

Pergunta de smoke: "qual é o meu perfil financeiro?". A resposta esperada
chama `perfil_financeiro`.

## Com credenciais GCP (integrante)

```bash
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project batalha-time-07-lkbv
gcloud config set project batalha-time-07-lkbv
gcloud auth configure-docker us-central1-docker.pkg.dev

make fixtures                                          # gera contracts/fixtures/
uv run --project mcp_server python data/scripts/aplicar_ddl.py --dry-run
uv run --project mcp_server python data/scripts/aplicar_ddl.py   # 2 vezes (idempotência)
uv run --project agent python deploy/smoke_modelos.py            # só relatório
uv run --project agent python deploy/smoke_modelos.py --gravar   # grava modelos.md e env.example
deploy/build_push.sh mcp && deploy/build_push.sh agent
deploy/deploy.sh mcp --tag c000 && deploy/deploy.sh agent --tag c000
make test-bq
```

`deploy/iam_datasets.sh` (Plano B) só aplica mudanças depois de uma
confirmação digitada. Sem ela, apenas mostra o plano.

## Validação dos critérios de aceite

| AC | Como validar |
|---|---|
| AC-02 | `make lint && make test` |
| AC-03 | `tests/contrato/test_ddl_modelos.py` (os dois projetos) |
| AC-04 | `make fixtures`, depois `make test` (o teste de referência deixa de ser pulado) |
| AC-05 | `tests/contrato/test_mock_servidor.py` e `test_mock_http.py` |
| AC-06 | `agent/tests/contrato/test_mcp_conexao.py` |
| AC-07 | `smoke.md` |
| AC-08..10 | `agent/tests/contrato/test_{callbacks,extensoes,persistencia}.py` |
| AC-11..13 | scripts de plataforma, com registro em `modelos.md` e `smoke.md` |
| AC-14 | `pedidos-owner.md` (envio pela Pessoa B) |
