# Implementation Plan: Fundação e contratos

**Branch**: `000-fundacao-contratos` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/000-fundacao-contratos/spec.md`

## Summary

Materializar os contratos v1 (`docs/ciclos/contratos.md`) em código. O ciclo
entrega:

- dois projetos Python 3.12 com `uv`: `mcp_server/` e `agent/`;
- DDL dos datasets `bussola_*` e `env.example`;
- modelos Pydantic, Protocols e fakes sobre fixtures;
- um MCP **mock** (FastMCP, streamable HTTP) que serve os golden;
- os pontos de extensão do agente: estado, callbacks, extensões,
  persistência e conexão MCP;
- um agente hello;
- scripts de plataforma GCP: DDL, fixtures, smoke de modelos,
  build/push/deploy e IAM do Plano B.

Os gates são `make lint` e `make test`, com `BUSSOLA_FAKES=TRUE` e sem rede.
Tudo o que depende de credenciais GCP fica isolado em scripts e testes
`@pytest.mark.bq`.

## Technical Context

**Language/Version**: Python 3.12 (`.python-version` = `3.12`;
`requires-python = ">=3.12,<3.13"`). Bash para `deploy/*.sh`. GoogleSQL para
o DDL.

**Primary Dependencies**: as versões foram resolvidas em 2026-09-26 (ver
[research.md](./research.md)).

- `mcp_server`:
  - `mcp>=1.24,<2` (1.30.0; FastMCP em `mcp.server.fastmcp`);
  - `pydantic>=2.13`, `google-cloud-bigquery>=3.45`, `numpy>=2.5`.
- `agent`:
  - `google-adk[mcp]>=2.10` (`McpToolset`,
    `StreamableHTTPConnectionParams`, `header_provider`);
  - `mcp>=1.24,<2`, `google-genai>=2.25`, `google-auth>=2.58`,
    `pydantic>=2.13`.
- dev: `pytest>=9.1`, `pytest-asyncio>=1.4`, `ruff>=0.16`.

**Storage**:

- BigQuery `bussola_dados`, `bussola_rag`, `bussola_app` e
  `bussola_app_dev`. Só DDL neste ciclo.
- Arquivos JSON em `contracts/fixtures/`.

**Testing**: pytest nos dois projetos, com `asyncio_mode=auto` e o marcador
`bq`. Um guarda de rede na `conftest.py` bloqueia conexões fora do loopback.
Os testes de contrato cobrem DDL ↔ Pydantic, o schema das ferramentas ↔ §5 e
os golden ↔ modelos `dados`.

**Target Platform**: Cloud Run `us-central1` (imagens `linux/amd64`,
`python:3.12-slim` + uv). Desenvolvimento em macOS/Linux.

**Project Type**: dois web-services (servidor MCP e agente ADK), mais scripts.

**Performance Goals**: não se aplica ao esqueleto. O mock responde com
arquivos locais.

**Constraints**:

- `make test` roda sem rede e sem GCP;
- nenhum segredo em arquivos, logs ou saída de terminal;
- SQL só parametrizado;
- Cloud Run com `--no-traffic` em revisões novas;
- IAM só com confirmação humana.

**Scale/Scope**: 2 usuários nas fixtures (âncora e controle), 12 meses,
8 ferramentas no mock e 12 tipos de evento de auditoria.

## Constitution Check

*GATE: avaliado antes da Phase 0 e reavaliado após a Phase 1.*

| Princípio | Como o plano cumpre | Status |
|---|---|---|
| I. Números de ferramentas determinísticas | O mock só serve golden gerados por código Python determinístico (`gerar_fixtures.py`). O agente hello não calcula nada. | PASS |
| II. Agente isolado de SQL/infra | As ferramentas do mock recebem só parâmetros semânticos. `fonte.tabelas` = `dataset.tabela`. Erros saem como envelope, com mensagens sem detalhe interno. | PASS |
| III. Read-only e escopo por cliente | Fakes filtram por `id_usuario` e `anomes ≤ ate_anomes`. Os modelos de entrada validam UUID v4 e faixas. O mock nunca devolve golden do âncora para outro UUID (controle → `DADOS_INSUFICIENTES`). `chamar_ferramenta` força o escopo a partir do `state`. O SQL de `gerar_fixtures.py` usa `@id_usuario`. | PASS |
| IV. Respostas rotuladas | Fora do escopo do 000 (004). O hello não produz recomendação. | N/A |
| V. Dados sintéticos e logs seguros | O logger JSON só emite campos de uma lista permitida (§9, mais `id_usuario`). Campos desconhecidos são descartados. | PASS |
| VI. Consentimento auditado | O 000 entrega `RegistroApp`, os modelos e o enum `TipoEvento`. O gate é do 005. | PASS (contrato) |
| VII. Segredos fora do repo | `env.example` só tem nomes e valores não secretos. `smoke_modelos.py` lê `gemini-api-key` em memória e não imprime. `.gitignore` cobre `.env`. | PASS |
| VIII. pt-BR | Mensagens de erro, avisos e a instrução do hello em pt-BR. | PASS |
| IX. Testes e gates sem rede | Guarda de rede nos testes; testes `bq` fora do `make test`; `aplicar_ddl.py` e os testes `bq` só escrevem em `bussola_*` (DDL) e nunca em `bussola_app`. | PASS |
| X. Contratos e paralelismo | Só caminhos marcados como 000 em §1. Mudanças de contrato são registradas em `questoes.md` e aplicadas em `contratos.md` neste PR (o 000 é o dono até o merge). | PASS |

Sem violações. A Complexity Tracking fica vazia.

**Reavaliação pós-design (Phase 1):** PASS. As decisões de
[research.md](./research.md) (mcp<2, `header_provider`, fixtures por
parâmetro, extensões via `find_spec`) não violam nenhum princípio.

## Project Structure

### Documentation (this feature)

```text
specs/000-fundacao-contratos/
├── plan.md            # este arquivo
├── research.md        # decisões técnicas (Phase 0)
├── data-model.md      # entidades e validações (Phase 1)
├── quickstart.md      # como rodar e validar (Phase 1)
├── contracts/         # schemas das ferramentas MCP e interfaces (Phase 1)
├── tasks.md           # /speckit-tasks
├── questoes.md        # divergências e decisões (FR-025)
├── pedidos-owner.md   # 4 pedidos de mestre §16 (FR-024)
├── modelos.md         # relatório do smoke de modelos (FR-021)
├── smoke.md           # smoke do agente hello e do deploy (AC-07, AC-13)
├── marcos.md
└── traceability.md    # exportado do Spec Master
```

### Source Code (repository root)

```text
CLAUDE.md                     # FR-002
Makefile                      # FR-004
.gitignore                    # FR-003 (acréscimos)
contracts/
├── bigquery/{bussola_dados,bussola_rag,bussola_app}.sql   # FR-006
├── env.example               # FR-007
└── fixtures/                 # FR-015/016 (gerado por make fixtures)
    ├── usuarios.json
    ├── bussola_dados/<tabela>.json
    ├── ferramentas/<ferramenta>__ate_{202506,202512}.json
    ├── ferramentas/resumo_mes__AAAAMM.json
    └── rag/trechos_exemplo.json
data/scripts/
├── aplicar_ddl.py            # FR-020
└── gerar_fixtures.py         # FR-015/016 (SQL de referência + golden)
mcp_server/
├── pyproject.toml, uv.lock, .python-version       # FR-005
├── Dockerfile, Dockerfile.dockerignore            # FR-005 (contexto = raiz)
├── bussola_mcp/
│   ├── __init__.py
│   ├── contratos.py          # FR-008
│   ├── logging_json.py       # FR-011
│   ├── dominio/{__init__,interfaces,fakes}.py     # FR-009/010
│   └── server.py             # FR-017/018 (mock)
└── tests/
    ├── conftest.py           # guarda de rede, fixtures sintéticas
    └── contrato/             # DDL↔Pydantic, fakes, mock, golden, logging
agent/
├── pyproject.toml, uv.lock, .python-version, Dockerfile, Dockerfile.dockerignore
├── bussola_agent/
│   ├── __init__.py
│   ├── estado.py, callbacks.py, extensoes.py      # FR-012/013/014
│   ├── persistencia.py, mcp_conexao.py            # FR-012
│   ├── logging_json.py                            # FR-011
│   └── agent.py              # FR-019 (hello)
└── tests/
    ├── conftest.py
    └── contrato/             # callbacks, extensões, persistência, estado, MCP, hello
deploy/
├── build_push.sh, deploy.sh  # FR-022
├── smoke_modelos.py          # FR-021
└── iam_datasets.sh           # FR-023
```

**Structure Decision**: dois projetos `uv` independentes, conforme o mapa de
contratos §1. Os scripts de `data/scripts/` e `deploy/smoke_modelos.py` não
são projetos. Eles rodam com o ambiente de um dos serviços:

- `uv run --project mcp_server` para dados e fixtures, porque usa
  `bussola_mcp.contratos` para validar os golden;
- `uv run --project agent` para o smoke de modelos, porque usa
  `google-genai`.

Os Dockerfiles usam a raiz como contexto. Assim, o mock leva
`contracts/fixtures/` e mantém o mesmo layout relativo do repositório. Cada
Dockerfile tem um `.dockerignore` próprio.

## Mudanças por componente

Cada linha traz o componente, a responsabilidade, a razão, os testes, os
riscos e os requisitos atendidos.

| # | Componente | Responsabilidade | Razão | Testes | Riscos | Req. |
|---|---|---|---|---|---|---|
| 0 | `.specify/`, `.claude/skills/speckit-*`, constituição | Spec Kit 0.8.17 com integração Claude e constituição v1.0.0 (feito antes deste plano) | 000 §3.1 | Leitura dos artefatos (AC-01) | — | FR-001 |
| 1 | `CLAUDE.md`, `.gitignore`, `Makefile` | Convenções, targets `test lint mcp agent fixtures test-bq` e carga opcional de `.env` | Contratos §2; 000 §3.1 | `make lint`/`make test` no fim; revisão manual | O `Makefile` recebe acréscimos de outros ciclos (união) | FR-002, FR-003, FR-004 |
| 2 | `mcp_server/` e `agent/` (`pyproject`, lock, Dockerfile) | Projetos uv com Python 3.12 e dependências fixadas | 000 §3.2 | `uv sync --frozen`; build da imagem (credencial) | `mcp` 2.x quebra `mcp.server.fastmcp` (mitigado por `<2`) | FR-005 |
| 3 | `contracts/bigquery/*.sql` | DDL idempotente, com `NOT NULL` em tudo que o contrato não marca como `NULL` | Contratos §3 | `test_ddl_modelos` (os dois projetos) | Divergir do texto de §3 (o teste cobre) | FR-006 |
| 4 | `contracts/env.example` | Variáveis de §7 sem segredos | Contratos §7 | Teste que confere a lista de §7 e a ausência de `GOOGLE_API_KEY` com valor | Alguém preencher a chave (revisão, `.gitignore`) | FR-007 |
| 5 | `bussola_mcp/contratos.py` | Linhas de §3, entradas com validação de faixa e UUID, `dados` de §5, envelopes e `CodigoErro` | Base de 001/002/003 | Validação de entrada (unit), DDL ↔ modelos, golden ↔ modelos | Mudança futura precisa ser aditiva | FR-008 |
| 6 | `dominio/interfaces.py`, `dominio/fakes.py` | Protocols de §4; fakes sobre as fixtures, com diretório por parâmetro | Contratos §4 | TS-05; filtro do buscador; `isinstance` com Protocol | Fixtures ausentes antes da credencial (conjunto sintético nos testes) | FR-009, FR-010 |
| 7 | `*/logging_json.py` | Formatador JSON com lista de campos permitidos | Contratos §9 | Campos, severidade e descarte de campo proibido | Logar dado sensível por `message` livre (revisão) | FR-011 |
| 8 | `bussola_mcp/server.py` | Mock FastMCP: 8 ferramentas, validação, regra de §8 e CLI `--host --port --fixtures` | Destravar 004/007 | `list_tools` ↔ §5; TS-02; TS-03; AC-05; HTTP real em subprocess | Coerção de tipos do FastMCP; os golden de simulação usam entrada canônica (aviso) | FR-017, FR-018 |
| 9 | `bussola_agent/estado.py` | Chaves, `EstadoJornada` e helpers | Contratos §6 | Unit | — | FR-012 |
| 10 | `bussola_agent/callbacks.py` | `registrar` e 4 agregados assíncronos com as assinaturas do ADK | Contratos §6 | TS-04 nas 4 fases; funções sync/async | Assinatura do ADK mudar (teste com o ADK real) | FR-012, FR-013 |
| 11 | `bussola_agent/extensoes.py` | Registro de ferramentas e instruções; `carregar_extensoes` via `find_spec` | Contratos §6 | AC-09; ordem das instruções; nome duplicado | Pacote presente mas quebrado: o erro é propagado de propósito | FR-012, FR-014 |
| 12 | `bussola_agent/persistencia.py` | `RegistroApp`, 4 modelos, `TipoEvento`, `RegistroEmMemoria` | Contratos §6 | AC-10; DDL `bussola_app` ↔ modelos | — | FR-012 |
| 13 | `bussola_agent/mcp_conexao.py` | `criar_toolset` (OIDC via `header_provider`), `aplicar_escopo`, `chamar_ferramenta` | Contratos §6 | AC-06 com o mock em subprocess; escopo forçado; OIDC com `fetch_id_token` simulado | ID token de usuário local não serve para OIDC (só Cloud Run/SA) | FR-012 |
| 14 | `bussola_agent/agent.py` | Hello: `root_agent`, instrução pt-BR, 4 callbacks e extensões | 000 §3.4 | Import sem rede; callbacks instalados; smoke manual (AC-07) | ID do modelo desconhecido até o smoke | FR-019 |
| 15 | `data/scripts/gerar_fixtures.py` | SQL de referência parametrizado → tabelas; golden por implementação de referência pura | Contratos §8 | Funções puras com linhas sintéticas (unit); AC-04 com as fixtures oficiais (pulado sem elas) | Precisa de ADC; fixtures provisórias | FR-015, FR-016 |
| 16 | `data/scripts/aplicar_ddl.py` | Datasets e tabelas idempotentes; `bussola_app_dev` a partir do DDL de `bussola_app`; `--dry-run` | 000 §3.5 | Parser do DDL (unit); execução real (credencial, AC-11) | Tabela existente com schema divergente (reportar, não alterar) | FR-020 |
| 17 | `deploy/smoke_modelos.py` | Descobrir e testar Flash (3.8 → 3.7 → 3.5) e embedding; relatório; atualizar `env.example` | 000 §3.5 | Execução real (credencial); seleção de candidatos (unit) | Modelos só em `location=global` (tentar e registrar) | FR-021 |
| 18 | `deploy/build_push.sh`, `deploy/deploy.sh` | Build `linux/amd64` com tag = SHA curto, push para o AR e deploy privado | 000 §3.5 | `bash -n`; execução real (credencial) | A primeira revisão de um serviço não aceita `--no-traffic` | FR-022 |
| 19 | `deploy/iam_datasets.sh` | Plano B por dataset, com confirmação obrigatória | 000 §3.5 | Sem confirmação não aplica nada (`bash -n` + execução com "não") | Mudança de IAM (confirmação humana) | FR-023 |
| 20 | `specs/.../pedidos-owner.md`, `questoes.md`, `modelos.md`, `smoke.md` | Pedidos, divergências e relatórios | 000 §3.5, §1.5 | Revisão | — | FR-024, FR-025 |

## Estratégia de testes e validação

- **Unit/contrato (`make test`)**:
  - modelos e validação de entrada;
  - DDL ↔ Pydantic (`bussola_dados`, `bussola_rag` no MCP; `bussola_app` no
    agente);
  - fakes, com o conjunto sintético gerado nos testes;
  - mock em memória (`create_connected_server_and_client_session`) e via
    HTTP real em subprocess;
  - callbacks, extensões, persistência e estado;
  - `McpToolset` e `chamar_ferramenta` contra o mock em subprocess (AC-06);
  - funções puras de `gerar_fixtures.py`;
  - logger JSON.
- **Fixtures oficiais (AC-04)**: o teste pula, com motivo, enquanto
  `contracts/fixtures/usuarios.json` não existir. Depois do `make fixtures`,
  valida os 9 valores de referência com tolerância de 1% e todos os golden
  contra os modelos.
- **`make test-bq`**: schema das tabelas vivas ↔ DDL (depois do
  `aplicar_ddl.py`).
- **Manual/credencial**: AC-07 (`smoke.md`), AC-11, AC-12, AC-13, registrados
  nos relatórios.

## Complexity Tracking

Sem violações da constituição.
