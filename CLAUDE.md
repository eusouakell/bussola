# Bússola: convenções para Claude Code

A Bússola é uma PoC de assistente financeiro com dados **sintéticos**. Tem
dois serviços Cloud Run:

- `mcp_server/`: ferramentas determinísticas via MCP;
- `agent/`: agente Google ADK + Gemini Flash.

A constituição fica em [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## Comandos

| Comando | O que faz |
|---|---|
| `make lint` | `ruff check` + `ruff format --check` nos dois projetos (e em `data/scripts`, `deploy`) |
| `make test` | `pytest` nos dois projetos com `BUSSOLA_FAKES=TRUE`, sem rede e sem GCP |
| `make mcp` | MCP local (mock no 000) em `http://localhost:8080/mcp` |
| `make agent` | ADK Web em `http://localhost:8000`, apontando para `MCP_URL` |
| `make fixtures` | Regenera `contracts/fixtures/` (precisa de ADC do GCP) |
| `make test-bq` | Testes `@pytest.mark.bq` contra BigQuery real (precisa de ADC) |

Os projetos usam `uv`. Para dependências, rode `cd mcp_server && uv add <pkg>`
(ou `agent`) e versione o `uv.lock`.

## Modo fake

`BUSSOLA_FAKES=TRUE` (padrão nos testes) faz MCP e agente usarem
`bussola_mcp/dominio/fakes.py` e `contracts/fixtures/`, sem nenhuma chamada ao
GCP. Um ciclo não depende de código não mergeado: use os fakes até a
dependência chegar em `main`.

## Contratos

- A fonte canônica é [`docs/ciclos/contratos.md`](docs/ciclos/contratos.md).
- O código de contrato fica em:
  - `contracts/` (DDL, `env.example`, fixtures);
  - `mcp_server/bussola_mcp/{contratos.py, dominio/interfaces.py, dominio/fakes.py}`;
  - `agent/bussola_agent/{estado, callbacks, extensoes, persistencia, mcp_conexao}.py`.
- Mudanças só via PR `contracts: <mudança>`, aditivas e revisadas por um
  ciclo consumidor.
- Propriedade de diretórios: [contratos §1](docs/ciclos/contratos.md#1-mapa-de-diretórios-e-propriedade).
  Cada ciclo escreve **somente** nos seus caminhos. Em `Makefile` e
  `pyproject.toml` valem acréscimos, e os conflitos se resolvem por união.

## Regras que não se negociam

- **SQL sempre parametrizado** (`@id_usuario`, `@ate_anomes`). Nunca
  concatenar texto do usuário ou do modelo em SQL.
- `id_usuario` é validado como UUID v4 antes de qualquer uso. `ate_anomes`
  fica entre 202501 e 202512, inclusivo.
- O agente sobrescreve `id_usuario` e `ate_anomes` a partir do
  `session.state`.
- Ferramentas devolvem envelope `{dados, fonte, avisos}` ou
  `{erro: {codigo, mensagem}}`. Nunca SQL, nomes de projeto ou credenciais.
- Valores em BRL como `float` com 2 casas. O LLM não calcula números.
- **Nunca logar** prompt completo, texto de lançamentos, chaves ou tokens.
  Use `logging_json` (lista de campos permitidos de contratos §9).
- **Segredos** ficam só no Secret Manager ou no `.env` local, que não é
  versionado. Nunca imprimir o valor de `gemini-api-key`.
- Testes gravam só em `bussola_app_dev`. Testes com BigQuery real levam
  `@pytest.mark.bq`.
- Cloud Run: novas revisões com `--tag cNNN --no-traffic`. Só o 007 move
  tráfego.
- Mudanças de IAM ou de tráfego exigem confirmação humana.
- Textos ao cliente em pt-BR.

## Fluxo de trabalho e PR

1. 1 ciclo = 1 worktree = 1 branch `NNN-<slug>` = 1 execução do Spec Master,
   com `SPECIFY_FEATURE_DIRECTORY=specs/NNN-<slug>`.
2. Rebase em `main` antes do PR.
3. O PR exige `make lint` e `make test` verdes e os critérios de aceite do
   ciclo.
4. `.spec-master/` é local. A rastreabilidade é exportada para
   `specs/NNN-*/traceability.md`.
5. Ordem de merge e revisores: [docs/ciclos/README.md](docs/ciclos/README.md)
   e [roadmap-2-pessoas.md](docs/ciclos/roadmap-2-pessoas.md).

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
[specs/000-fundacao-contratos/plan.md](specs/000-fundacao-contratos/plan.md)
<!-- SPECKIT END -->
