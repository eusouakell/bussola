# Questões e divergências do ciclo 000

Atende ao FR-025. Cada item registra uma divergência entre a spec, a trilha
([000](../../docs/ciclos/000-fundacao-contratos.md)) e os
[contratos](../../docs/ciclos/contratos.md), a decisão tomada e onde ela foi
corrigida. As correções em `contratos.md` são **aditivas** (contratos §0) e
entram neste mesmo PR, que cria `contratos-v1`.

| ID | Tema | Decisão | Correção |
|---|---|---|---|
| Q-01 | Controle no mock | `DADOS_INSUFICIENTES` | contratos §8 |
| Q-02 | Cliente MCP nos testes | `ClientSession` do SDK `mcp` | só registro |
| Q-03 | Golden de simulação | Entrada canônica 30000/24 + aviso | contratos §8 |
| Q-04 | `carregar_extensoes()` | `find_spec`; pacote presente e quebrado propaga | contratos §6 |
| Q-05 | Campo `excecao` nos logs | Só o nome da classe | contratos §9 |
| Q-06 | Semântica de `modo` | `modo` = o que a entrada informou | contratos §5 |
| Q-07 | `fonte.tabelas` por ferramenta | Tabela fixa em `TABELAS_FERRAMENTA` | contratos §5 |
| Q-08 | Agente hello privado | `--no-allow-unauthenticated` nos dois serviços | só registro |
| Q-09 | Funções auxiliares do agente | `ferramentas_sensiveis`, `limpar`, `criar_toolset`, `aplicar_escopo` | contratos §6 |
| Q-10 | Nulidade e validação de entrada | `NOT NULL` explícito; erro como envelope, sem eco | contratos §3 e §5 |
| Q-11 | Formato JSON das fixtures | Lista JSON por arquivo; golden = envelope | contratos §8 |
| Q-12 | Mensagem de `INDISPONIVEL` no mock | "Dados de exemplo indisponíveis." explícita | só registro |
| Q-13 | Premissas do AC-04 | Categorias por palavra-chave; saldo mín./máx. do ano | confirmado no T032 |
| Q-14 | Regras de métrica das fixtures | Regras provisórias em `gerar_fixtures.py` | confirmar no 001 |
| Q-15 | Local do Gemini × BigQuery | Agente em `global` via `BUSSOLA_LOCAL_MODELO`; resto em `us-central1` | contratos §7 |
| Q-16 | Invoker do agente no MCP privado | `roles/run.invoker` no `bussola-mcp` para a SA do agente, com confirmação humana | contratos §6 e `deploy/README.md` |

## Q-01 Usuário de controle no mock

- **Divergência:** contratos §8 diz que o mock serve o golden do âncora, mas
  não diz o que fazer com o controle (`31e94f2f-…`), que está em
  `usuarios.json`.
- **Decisão:** usuário presente em `usuarios.json` e diferente do âncora
  recebe `DADOS_INSUFICIENTES` ("O mock só tem respostas do cliente
  âncora."). Nunca devolve o golden de outro cliente (constituição III).
- **Referência:** research R-08.

## Q-02 Cliente MCP nos testes

- **Divergência:** 000 §4 cita `fastmcp.Client` para testar o mock. O
  projeto usa o SDK oficial `mcp` (1.x), sem o pacote `fastmcp`.
- **Decisão:** testes usam `mcp.shared.memory.create_connected_server_and_client_session`
  (em memória) e `mcp.client.streamable_http.streamable_http_client` +
  `ClientSession` (HTTP). É equivalente funcional e não acrescenta
  dependência.
- **Referência:** research R-02 e R-03. Não muda contrato.

## Q-03 Golden de `simular_objetivo` e `comparar_cenarios`

- **Divergência:** contratos §8 prevê um golden por ferramenta e corte, mas
  essas duas ferramentas dependem da entrada (`valor_alvo`, `prazo_meses`).
- **Decisão:** os golden são gerados com a entrada canônica
  `valor_alvo=30000`, `prazo_meses=24`. O mock serve esse golden para
  qualquer entrada válida e acrescenta o aviso "Resposta de exemplo do mock,
  calculada para valor_alvo=30000 e prazo_meses=24.". O 001 substitui por
  cálculo real.
- **Referência:** research R-09 e R-10 (truncamento em `top_n` e `k`).

## Q-04 `carregar_extensoes()` e `ImportError`

- **Divergência:** contratos §6 diz "ignora `ImportError`". Engolir o
  `ImportError` de um pacote **presente** esconderia bugs do 005/006 (por
  exemplo, dependência faltando), e a demo rodaria sem governança sem
  ninguém perceber.
- **Decisão:** para cada pacote, `importlib.util.find_spec`:
  - `None` (pacote ausente): pula, sem erro (AC-09);
  - pacote presente: importa, e erros dentro dele **propagam**.
- **Referência:** research R-12.

## Q-05 Campo `excecao` nos logs

- **Divergência:** contratos §9 lista os campos permitidos, mas não diz como
  registrar exceções. Traceback e mensagem podem conter dados do usuário ou
  do prompt.
- **Decisão:** o logger usa lista de campos permitidos. Exceções viram só
  `excecao` com o **nome da classe**, sem traceback nem mensagem. Outros
  extras são descartados.
- **Referência:** research R-14.

## Q-06 Semântica de `modo` em `simular_objetivo`

- **Divergência:** contratos §5 lista `modo ("prazo" | "aporte")`, mas não
  define o significado.
- **Decisão:** `modo` indica o que a **entrada informou**:
  - `"prazo"`: a entrada trouxe `prazo_meses`, e a ferramenta calcula
    `aporte_mensal`;
  - `"aporte"`: a entrada trouxe `aporte_mensal`, e a ferramenta calcula
    `prazo_meses`.

  Nos dois casos, `aporte_mensal` e `prazo_meses` vêm preenchidos na saída.

## Q-07 `fonte.tabelas` por ferramenta

- **Divergência:** contratos §5 mostra `fonte.tabelas` só no exemplo. Sem
  uma tabela fixa, o mock, o 001 e o 003 podem citar tabelas diferentes, e
  o teste de contrato não consegue comparar.
- **Decisão:** mapeamento fixo em `contratos.TABELAS_FERRAMENTA`,
  acrescentado a contratos §5.

## Q-08 Agente hello privado

- **Divergência:** 000 §3 só exige o MCP privado. O agente hello não tem
  regra.
- **Decisão:** os dois serviços sobem com `--no-allow-unauthenticated`. O
  agente fica privado até o 007 decidir o canal (Q4 do mestre e item 4 de
  [`pedidos-owner.md`](./pedidos-owner.md)).
- **Referência:** research R-18. Não muda contrato.

## Q-09 Funções auxiliares de `extensoes` e `mcp_conexao`

- **Divergência:** contratos §6 não lista como o gate do 005 descobre quais
  ferramentas são sensíveis, nem como os testes isolam os registros
  globais, nem como o 004 cria o toolset.
- **Decisão:** acréscimos aditivos:
  - `extensoes.ferramentas_sensiveis() -> set[str]` (nomes registrados com
    `sensivel=True`);
  - `extensoes.limpar()` e `callbacks.limpar()` (só para testes);
  - `mcp_conexao.criar_toolset(url=None, usar_oidc=None, tool_filter=None)`;
  - `mcp_conexao.aplicar_escopo(args, state) -> dict`;
  - `chamar_ferramenta(..., url=None, usar_oidc=None)`: falha de transporte
    devolve `INDISPONIVEL` em vez de levantar.
- **Referência:** `contracts/interfaces-python.md`.

## Q-10 Nulidade no DDL e validação de entrada

- **Divergência:**
  - contratos §3 marca só as colunas `NULL`, sem dizer que as demais são
    `NOT NULL`;
  - contratos §5 não diz se faixa inválida é erro de protocolo ou envelope,
    nem o que a mensagem pode conter.
- **Decisão:**
  - colunas sem `NULL` recebem `NOT NULL` no DDL, exceto `ARRAY` (o
    BigQuery não aceita `NOT NULL` em `ARRAY`);
  - faixas e UUID são validados **dentro** da ferramenta e devolvem o
    envelope `ENTRADA_INVALIDA`. A mensagem cita só os nomes dos campos,
    nunca o valor recebido.
- **Referência:** research R-05, R-06 e R-16.

## Q-11 Formato JSON das fixtures

- **Divergência:** contratos §8 lista os arquivos, mas não diz se cada um é
  uma lista ou um objeto que contém a lista.
- **Decisão:** arquivos de tabela, `usuarios.json` e
  `rag/trechos_exemplo.json` são **listas JSON**; cada golden é um envelope.
  Os fakes também aceitam objeto com a lista em `usuarios`, `linhas`,
  `trechos` ou `dados`, por tolerância.

## Q-12 Mensagem de `INDISPONIVEL` no mock

- **Divergência:** contratos §8 pede "Dados de exemplo indisponíveis." para
  fixture ausente, mas `MENSAGENS_ERRO[INDISPONIVEL]` é "Serviço
  temporariamente indisponível.".
- **Decisão:** o mock passa a mensagem de §8 explicitamente; o padrão de
  `contratos.py` continua valendo para os serviços reais. Não muda contrato.

## Q-13 Premissas do AC-04

- **Divergência:** contratos §8 não define as categorias de aluguel, comer
  fora e assinaturas, e chama de "média de 2025" o saldo mínimo e máximo.
- **Decisão provisória** (`test_fixtures_oficiais.py`):
  - categorias casadas por palavra-chave em `gastos_categoria` ("aluguel";
    "restaurante"/"comer fora"; "assinatura"/"streaming");
  - saldo mínimo e máximo = mínimo e máximo do ano, não média.
- **Confirmado no T032** (fixtures reais, âncora, `ate_anomes = 202512`): os
  9 valores ficam dentro de 1%. Maior desvio: juros, −0,80% (60,51 × 61);
  assinaturas −0,46% (100,54 × 101); os demais abaixo de 0,2%.

## Q-14 Regras de métrica das fixtures provisórias

- **Divergência:** o 001 ainda não definiu várias regras de cálculo, e o
  `gerar_fixtures.py` do 000 precisa delas para produzir os golden.
- **Decisão provisória** (o 001 confirma ou troca e regenera por PR
  `contracts:`):
  - ordem no dia: `(anomesdia, tipo, descr, vlr, saldo_apos)`, com desempate
    pela cadeia de saldo; saldo mínimo e máximo vêm de `saldo_apos`;
  - `recorrentes`: só tipo S, mesma `descr` normalizada (sem "parc m/n" e
    datas) em pelo menos 3 meses distintos do ano;
  - `parcelas`: qualquer linha com `parcela_total > 1`; ativas são as do mês
    de corte, inclusive com 0 restantes;
  - categorias discricionária/essencial por palavra-chave (micro, depois
    macro), como semente provisória;
  - coorte: uma consulta agregada sobre todos os usuários que não devolve
    ids, com grupo mínimo de 5 usuários; faixa pela renda média do ano;
  - `comprometimento_renda` na escala 0–100;
  - cenário "acelerado" usa os cortes do top 10 de oportunidades;
  - `usar_saldo_atual`: `saldo_inicial = max(0, saldo)`; desvio por
    `pstdev`;
  - golden de `buscar_contexto_financeiro` com ranking fixo (coorte,
    perfil anual e fichas mensais da mais recente para a mais antiga).
- **Observação:** `contratos.py` não tem campo "provisório". A marcação fica
  na docstring e na mensagem da CLI do gerador.

## Q-15 Local do Gemini × BigQuery

- **Divergência:** contratos §7 define um único `GOOGLE_CLOUD_LOCATION`
  (`us-central1`) para os dois serviços. O smoke de modelos (AC-12,
  [`modelos.md`](./modelos.md)) mostrou que, neste projeto, os Flash
  (`gemini-3.8-flash`, `3.7`, `3.5`) dão 404 em `us-central1` e só
  respondem em `global`. O embedding `gemini-embedding-001` responde em
  `us-central1`.
- **Decisão:** variável nova `BUSSOLA_LOCAL_MODELO` (agent, padrão `global`),
  que vira o `GOOGLE_CLOUD_LOCATION` do agente em `make agent` e em
  `deploy/deploy.sh agent`. MCP, embedding e BigQuery continuam em
  `us-central1`. A mudança é aditiva: sem a variável, o agente volta a usar
  `GOOGLE_CLOUD_LOCATION`.
- **Correção:** contratos §7 (linha nova e nota em `GOOGLE_CLOUD_LOCATION`),
  `contracts/env.example`, `Makefile` (alvo `agent`) e `deploy/deploy.sh`.
- **Confirmado no T039:** o agente hello local em `global` chamou
  `perfil_financeiro` no mock ([`smoke.md`](./smoke.md)).

## Q-16 Invoker do agente no MCP privado

- **Divergência:** contratos §6 manda o agente chamar o `bussola-mcp` com ID
  token (`MCP_USE_OIDC=TRUE`), mas nenhum script nem pedido concede
  `roles/run.invoker` à SA de runtime do agente. O `deploy.sh` cria o MCP
  privado sem política IAM, por regra. No deploy hello o agente recebeu 403
  ([`smoke.md`](./smoke.md)).
- **Decisão:** conceder `roles/run.invoker` **no nível do serviço**
  `bussola-mcp`, e não do projeto, à SA de runtime do agente. Plano B: SA
  default de compute. Plano A: `bussola-runtime`. É mudança de IAM: um
  integrante aplica, com confirmação humana. Se o time não tiver
  `run.services.setIamPolicy`, vira pedido ao owner.
- **Correção:** contratos §6 (Conexão MCP, aditivo) e `deploy/README.md`
  (ordem de uso). Comando:

  ```bash
gcloud run services add-iam-policy-binding bussola-mcp \
  --project batalha-time-07-lkbv --region us-central1 \
  --member serviceAccount:1061873050224-compute@developer.gserviceaccount.com \
  --role roles/run.invoker
  ```

## Questões ainda abertas (herdadas)

- **Q2 do mestre (regras de cenário):** `RegrasCenario` usa os percentuais
  propostos (40/60/80% da sobra mediana) até decisão do time.
- **Q4 do mestre (canal da demo):** decide se o agente fica público no 007.
- **Q7 do mestre (pedidos ao owner):** ver
  [`pedidos-owner.md`](./pedidos-owner.md).
- **Modelo Gemini e embedding:** resolvido no smoke de modelos (AC-12):
  `gemini-3.8-flash` em `global` e `gemini-embedding-001` (dimensão 3072) em
  `us-central1`, gravados em `env.example` e em [`modelos.md`](./modelos.md).
