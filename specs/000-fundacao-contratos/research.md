# Research: Fundação e contratos (Phase 0)

Decisões técnicas do ciclo 000. Cada entrada traz a decisão, a razão e as
alternativas consideradas. Versões resolvidas em 2026-09-26 com `uv 0.11.17`.

## R-01 Python 3.12 fixo

- **Decisão:** `.python-version` = `3.12` e `requires-python =
  ">=3.12,<3.13"` nos dois projetos.
- **Razão:** contratos §2 exige 3.12. Sem o teto, o `uv` escolhe o Python
  mais novo instalado (3.14) e o venv diverge da imagem `python:3.12-slim`.
- **Alternativas:** `>=3.12` sem teto. Descartada porque criou um venv 3.14
  na primeira tentativa.

## R-02 SDK MCP `mcp>=1.24,<2` (FastMCP em `mcp.server.fastmcp`)

- **Decisão:** `mcp>=1.24,<2`, que resolve para 1.30.0. O servidor usa
  `from mcp.server.fastmcp import FastMCP`, `transport="streamable-http"` e
  `streamable_http_path="/mcp"`.
- **Razão:** a série 2.x removeu `mcp.server.fastmcp`, que agora é
  `mcp.server.mcpserver.MCPServer`. O `google-adk` 2.10 depende de
  `mcp>=1.24,<2`. Assim os dois projetos ficam na mesma série.
- **Alternativas:**
  - `fastmcp` (pacote independente): dependência extra e divergente do SDK
    oficial citado no mestre §13;
  - `mcp` 2.x: incompatível com o ADK.

## R-03 Cliente MCP nos testes: `ClientSession` do SDK `mcp`

- **Decisão:** testes do mock usam:
  - `mcp.shared.memory.create_connected_server_and_client_session` (em
    memória);
  - `mcp.client.streamable_http.streamable_http_client` + `ClientSession`
    (HTTP real, servidor em subprocess).
- **Razão:** é equivalente funcional ao `fastmcp.Client` citado em 000 §4 e
  não acrescenta dependência. Registrado em `questoes.md` (Q-02).

## R-04 ADK `google-adk[mcp]` 2.10: `McpToolset` + `header_provider`

- **Decisão:**
  - `McpToolset(connection_params=StreamableHTTPConnectionParams(url=...),
    tool_filter=..., header_provider=...)`;
  - com `MCP_USE_OIDC=TRUE`, o `header_provider` devolve
    `{"Authorization": f"Bearer {token}"}`;
  - o token vem de `google.oauth2.id_token.fetch_id_token(Request(),
    audience)`, com `audience` = `scheme://host` do `MCP_URL`, e fica em
    cache por ~45 minutos.
- **Razão:** o `header_provider` é chamado a cada sessão. Com ele, o token
  é renovado sem recriar o toolset. `fetch_id_token` funciona no Cloud Run
  (metadata server) e com uma SA local.
- **Limitação:** com ADC de usuário (`gcloud auth application-default
  login`), `fetch_id_token` não emite ID token. Para teste local contra o
  MCP privado, use `gcloud auth print-identity-token` fora do agente.
  Registrado em `smoke.md`.

## R-05 Faixas validadas dentro da ferramenta, não no schema

- **Decisão:** a assinatura das ferramentas do mock usa tipos simples com os
  padrões de §5 (`top_n: int = 5`, `k: int = 5`, `prazo_meses: int | None =
  None`...). A validação de faixa e UUID é feita pelos modelos `Entrada*`
  de `contratos.py`. Uma falha devolve o envelope `ENTRADA_INVALIDA`.
- **Razão:** contratos §5 define o erro como resultado, não como exceção.
  Restrições no JSON Schema fariam o SDK rejeitar a chamada com erro de
  protocolo (`isError`) antes da ferramenta, sem o envelope.
- **Nota:** para aceitar valores fora do tipo (ex.: `ate_anomes="abc"`),
  o FastMCP ainda valida os tipos básicos. Isso vira `isError` do protocolo.
  É aceitável porque o agente força `id_usuario`/`ate_anomes` (§6).

## R-06 Mensagens de erro sem eco de valores

- **Decisão:** `ENTRADA_INVALIDA` cita só os nomes dos campos inválidos
  (ex.: "Entrada inválida: ate_anomes."), nunca o valor recebido.
- **Razão:** constituição II e V. Evita refletir texto do modelo ou do
  usuário e não expõe detalhes internos.

## R-07 Fixtures por parâmetro e conjunto sintético nos testes

- **Decisão:**
  - `RepositorioFake(dir_fixtures)`, `BuscadorFake(dir_fixtures)` e o mock
    (`--fixtures DIR`, padrão `contracts/fixtures/` resolvido a partir da
    raiz do repositório) recebem o diretório;
  - os testes geram um conjunto sintético mínimo em `tmp_path`;
  - o teste das fixtures oficiais (AC-04) é pulado com motivo enquanto
    `contracts/fixtures/usuarios.json` não existir.
- **Razão:** as fixtures reais dependem de ADC do integrante, e não se
  inventam dados de fixture (spec, Assumptions).

## R-08 Controle no mock → `DADOS_INSUFICIENTES`

- **Decisão:** um usuário presente em `usuarios.json` com `papel !=
  "ancora"` recebe `DADOS_INSUFICIENTES` ("O mock só tem respostas do
  cliente âncora.").
- **Razão:** constituição III. Nunca devolver o golden de outro cliente.
  Registrado em `questoes.md` (Q-01).

## R-09 Golden de simulação com entrada canônica

- **Decisão:**
  - `simular_objetivo`: golden gerado para `valor_alvo=30000,
    prazo_meses=24`;
  - `comparar_cenarios`: golden gerado para `valor_alvo=30000,
    prazo_meses=24`;
  - o mock serve o golden para qualquer entrada válida e acrescenta o aviso
    "Resposta de exemplo do mock, calculada para valor_alvo=30000 e
    prazo_meses=24.".
- **Razão:** contratos §8 prevê um golden por ferramenta e corte. O 001
  substitui por cálculo real. Registrado em `questoes.md` (Q-03).

## R-10 Truncamento no mock

- **Decisão:** os golden de `oportunidades_corte` e
  `buscar_contexto_financeiro` guardam o máximo de itens (10). O mock
  corta a lista em `top_n` e em `k`.
- **Razão:** a resposta fica coerente com o parâmetro sem gerar golden por
  valor.

## R-11 `RegrasCenario` como modelo de contrato

- **Decisão:** `RegrasCenario` (Pydantic) fica em `contratos.py`, com
  `pct_capacidade={"conservador":0.40,"equilibrado":0.60,"acelerado":0.80}`,
  `base="sobra_mediana"`, `rendimento_mensal=0.0` e `saldo_inicial=0.0`. O
  campo `regras` de `comparar_cenarios` usa esse modelo.
- **Razão:** o 001 (`simulacao.py`) e o 003 consomem o mesmo objeto. A Q2
  continua aberta: o modelo aceita outros valores.

## R-12 `carregar_extensoes()` com `importlib.util.find_spec`

- **Decisão:** para cada pacote (`bussola_agent.governanca`,
  `bussola_agent.acompanhamento`):
  - se `find_spec` devolver `None`, o pacote é pulado;
  - se existir, é importado e erros de import dentro dele **propagam**.
- **Razão:** contratos §6 diz "ignora `ImportError`". Mas engolir o
  `ImportError` de um pacote presente e quebrado esconderia bugs do 005/006
  (ex.: dependência faltando), e a demo rodaria sem governança. A decisão é
  compatível com o AC-09 (pacotes ausentes). Registrado em `questoes.md`
  (Q-04).

## R-13 Callbacks agregados assíncronos com assinaturas por palavra-chave

- **Decisão:** os agregados de `callbacks.py` são `async def` com as
  assinaturas do ADK 2.10:
  - `before_model(callback_context, llm_request)`;
  - `after_model(callback_context, llm_response)`;
  - `before_tool(tool, args, tool_context)`;
  - `after_tool(tool, args, tool_context, tool_response)`.

  Cada função registrada recebe os mesmos argumentos por palavra-chave e
  pode ser sync ou async: o agregado faz `await` quando o retorno é
  awaitable.
- **Razão:** o ADK chama callbacks por palavra-chave e aceita corrotinas.
  Com isso o 005 pode usar Model Armor async.
- **Ordem estável:** a ordenação é por `(ordem, seq_registro)`. Uma fase
  inválida gera `ValueError`.

## R-14 Logger JSON com lista de campos permitidos

- **Decisão:** `JsonFormatter` emite:
  - `severity` (nome do nível), `message`, `servico` e `timestamp`;
  - só os campos extras da lista de §9 (`session_id`, `estado_jornada`,
    `ferramenta`, `evento`, `consentimento`, `ate_anomes`, `latencia_ms`,
    `erro_codigo`), mais `id_usuario` (§9 permite o sintético);
  - para exceções, apenas `excecao` com o **nome da classe**, sem
    traceback nem mensagem.

  Outros extras são descartados.
- **Razão:** constituição V. É uma lista de campos permitidos, não de
  proibidos. `excecao` é acréscimo ao §9 e está registrado em `questoes.md`
  (Q-05), com a correção de contratos §9 neste PR.

## R-15 Dockerfiles com contexto na raiz

- **Decisão:**
  - build com `docker buildx build --platform linux/amd64 -f
    <svc>/Dockerfile .` e o `.dockerignore` específico
    `<svc>/Dockerfile.dockerignore` (BuildKit);
  - imagem `python:3.12-slim` + `COPY --from=ghcr.io/astral-sh/uv:0.11`;
  - `uv sync --frozen --no-dev`.
  - O MCP copia `mcp_server/` e `contracts/fixtures/` para `/app` (mesmo
    layout do repositório).
  - O agente copia `agent/` e roda `adk web --host 0.0.0.0 --port $PORT
    /app/agent`.
- **Razão:** o mock precisa das fixtures, que ficam fora de `mcp_server/`.

## R-16 DDL: `NOT NULL` e datasets

- **Decisão:**
  - colunas sem `NULL` explícito em §3 recebem `NOT NULL`, exceto `ARRAY`,
    que o BigQuery não aceita com `NOT NULL`; o `embedding` fica como está;
  - `CREATE SCHEMA IF NOT EXISTS <ds> OPTIONS(location="us-central1")`;
  - os `.sql` usam nomes sem projeto (`bussola_dados.perfil_mensal`), e o
    `aplicar_ddl.py` executa os jobs com `project=GOOGLE_CLOUD_PROJECT`;
  - `bussola_app_dev` aplica o `bussola_app.sql` trocando o identificador
    de dataset.
- **Razão:** a nulidade fica explícita e o teste de contrato compara nome,
  tipo e nulidade com os modelos.

## R-17 Smoke de modelos

- **Decisão:** `deploy/smoke_modelos.py` roda com o ambiente do `agent`
  (`google-genai`) e segue esta ordem:
  1. lista os modelos via Vertex;
  2. testa `gemini-3.8-flash`, depois `gemini-3.7-flash`, depois
     `gemini-3.5-flash` (e variantes `-preview` encontradas na listagem),
     primeiro em `us-central1` e depois em `global`;
  3. testa o embedding (`gemini-embedding-*` / `text-embedding-*`
     encontrados) e mede a dimensão;
  4. se nada responder, usa o fallback via Gemini API, com a chave lida por
     `gcloud secrets versions access latest --secret=gemini-api-key` direto
     para a memória do processo, sem imprimir.
- **Razão:** mestre §5 e §17. O ID exato só é conhecido com as credenciais.

## R-18 Deploy hello

- **Decisão:** `deploy.sh <servico> [--tag cNNN --no-traffic]` e
  `--no-allow-unauthenticated` nos dois serviços:
  - o `bussola-mcp` é privado por contrato;
  - o agente também fica privado até o 007 decidir o canal.

  Na primeira criação do serviço, o `gcloud` não aceita `--no-traffic`, e o
  script detecta isso com `gcloud run services describe`.
- **Razão:** constituição X (só o 007 move tráfego) e restrição de IAM (sem
  mudança de IAM sem confirmação).
