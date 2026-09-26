# Bússola — Contratos compartilhados entre ciclos (v1)

> Fonte canônica das interfaces que permitem executar os ciclos em paralelo.
> O **ciclo 000** materializa este documento em código (`contracts/`,
> `contratos.py`, `interfaces.py`, `fakes.py`, `callbacks.py`, `estado.py`,
> `persistencia.py`, `mcp_conexao.py`). Os demais ciclos **consomem** esses
> artefatos e não os alteram.
>
> Este documento prevalece sobre `docs/blueprint-arquitetura.md` §4–§5 e
> sobre a lista de views de `docs/contexto-spec-master.md` §10 F1, onde
> houver diferença.

## §0 Regras de mudança

- **Versão:** `contratos-v1`, tag git criada no merge do ciclo 000.
- **Como mudar:** abrir PR próprio com título `contracts: <mudança>`. O PR
  atualiza este documento e o código de contrato no mesmo commit, e precisa
  da revisão de pelo menos um ciclo consumidor afetado. Avise no canal do
  time antes do merge.
- **Compatibilidade:** mudanças devem ser aditivas (campo novo opcional,
  ferramenta nova). Remover ou renomear campo exige acordo de todos os ciclos
  ativos.
- **Números:** valores monetários em BRL como `float` arredondado a 2 casas
  nas saídas. Formatação (R$, vírgula) é responsabilidade do agente, nunca
  das ferramentas.
- **Período:** `anomes` é inteiro `AAAAMM`, válido de `202501` a `202512`.
  `ate_anomes` é **inclusivo**.

## §1 Mapa de diretórios e propriedade

Cada ciclo escreve somente nos seus caminhos. Os arquivos marcados com
"acréscimo" aceitam linhas de qualquer ciclo; nesses casos, o conflito de
merge se resolve pela união das linhas.

```text
.
├── CLAUDE.md                          000  (convenções p/ Claude Code)
├── AGENTS.md                          007  (operação no Antigravity)
├── Makefile                           000  (acréscimo de targets)
├── .specify/                          000  (constituição congelada após 000)
├── .github/workflows/                000 (ci.yml, deploy.yml; Q-18) → 007 (promoção de tráfego)
├── specs/NNN-*/                       cada ciclo, só o seu NNN
├── contracts/                         000  (mudança só via PR "contracts:")
│   ├── bigquery/bussola_dados.sql
│   ├── bigquery/bussola_app.sql
│   ├── fixtures/…                     (§8)
│   └── env.example                    (§7)
├── data/
│   ├── scripts/aplicar_ddl.py         000
│   ├── scripts/gerar_fixtures.py      000 (001 pode regenerar via PR "contracts:")
│   ├── sql/                           001
│   ├── scripts/build_dados.py         001
│   └── rag/                           002  (corpus/<tema>/<doc_id>.md e indexar.py; Q-17)
├── mcp_server/
│   ├── pyproject.toml, Dockerfile     000  (acréscimo de dependências)
│   ├── bussola_mcp/
│   │   ├── contratos.py               000  (modelos Pydantic de I/O)
│   │   ├── logging_json.py            000
│   │   ├── dominio/interfaces.py      000  (Protocols)
│   │   ├── dominio/fakes.py           000  (implementações sobre fixtures)
│   │   ├── dominio/repositorio_bq.py  001
│   │   ├── dominio/metricas.py        001
│   │   ├── dominio/simulacao.py       001
│   │   ├── rag/                       002  (buscadores e indice/ versionado; Q-17)
│   │   ├── ferramentas/               003
│   │   └── server.py                  000 (mock) → 003 (real)
│   └── tests/{contrato,dados,rag,ferramentas}/   000/001/002/003
├── agent/
│   ├── pyproject.toml, Dockerfile     000  (acréscimo de dependências)
│   ├── bussola_agent/
│   │   ├── estado.py                  000  (chaves de session.state)
│   │   ├── callbacks.py               000  (encadeador de callbacks)
│   │   ├── persistencia.py            000  (Protocol + fake em memória)
│   │   ├── mcp_conexao.py             000  (MCPToolset + OIDC opcional + chamada direta)
│   │   ├── extensoes.py               000  (registro de ferramentas/instruções de outros ciclos)
│   │   ├── logging_json.py            000
│   │   ├── agent.py                   000 (hello) → 004
│   │   ├── prompts/, jornada/, escopo.py             004
│   │   ├── governanca/, persistencia_bq.py           005
│   │   └── acompanhamento/                           006
│   └── tests/{contrato,jornada,governanca,acompanhamento}/  000/004/005/006
├── eval/
│   ├── rag/                           002
│   ├── agente/                        004
│   ├── seguranca/                     005
│   └── acompanhamento/                006
├── deploy/                            000 (hello) → 007
├── docs/
│   ├── operacao.md, roteiro-demo.md   007
│   └── ciclos/                        só por PR de planejamento
└── README.md                          007 (seção "Como rodar/publicar")
```

## §2 Convenções gerais

- **Linguagem:** Python 3.12 com `uv`. Há dois projetos independentes,
  `mcp_server/` e `agent/`, um por serviço Cloud Run.
- **Qualidade:** testes com `pytest` e lint/format com `ruff`.
- **Targets do Makefile:**
  - `make test` e `make lint` rodam nos dois projetos;
  - `make mcp` sobe o MCP local na porta 8080;
  - `make agent` sobe o agente local com ADK Web;
  - `make fixtures` regenera `contracts/fixtures/`.
- **Testes que dependem de BigQuery real:** marcados com `@pytest.mark.bq` e
  fora do `make test` padrão. `make test-bq` roda esses testes.
- **Modo fake:** `BUSSOLA_FAKES=TRUE` faz MCP e agente usarem `fakes.py` e as
  fixtures, sem nenhuma chamada ao GCP. É o modo padrão dos testes.
- **Identificadores:** `id_usuario` é UUID v4 em string; toda entrada é
  validada por regex antes de qualquer uso.
- **SQL:** sempre parametrizado (`@id_usuario`, `@ate_anomes`). Nunca montar
  SQL por concatenação com texto vindo do usuário ou do modelo.
- **Idioma:** textos ao cliente em pt-BR. Identificadores de código em
  português (padrão do domínio) ou inglês técnico, com consistência dentro de
  cada módulo.

## §3 BigQuery (projeto `batalha-time-07-lkbv`, `us-central1`)

DDL em `contracts/bigquery/*.sql`, aplicado de forma idempotente por
`data/scripts/aplicar_ddl.py` (`CREATE SCHEMA IF NOT EXISTS` /
`CREATE TABLE IF NOT EXISTS`). A origem é somente leitura:
`hackathon_dados.extrato_sintetico`.

**Nulidade:** só as colunas marcadas `NULL` são anuláveis. As demais são
`NOT NULL` no DDL, exceto `ARRAY`, que o BigQuery não aceita com `NOT NULL`.
Os modelos Pydantic de
`contratos.py` seguem a mesma nulidade, e um teste de contrato compara os
dois (Q-10 do 000).

### `bussola_dados`: métricas determinísticas (escrita pelo 001, leitura por todos)

| Tabela | Colunas | Observação |
|---|---|---|
| `perfil_mensal` | `id_usuario STRING, anomes INT64, renda FLOAT64, gasto FLOAT64, sobra FLOAT64, saldo_inicial FLOAT64, saldo_final FLOAT64, saldo_minimo FLOAT64, saldo_maximo FLOAT64, juros FLOAT64` | 1 linha por usuário/mês. Substitui as views `perfil_mensal` e `saldo` de §10 F1. |
| `gastos_categoria` | `id_usuario STRING, anomes INT64, macro STRING, micro STRING, total FLOAT64, qtd INT64` | Apenas saídas (`tipo = 'S'`). |
| `entradas_categoria` | `id_usuario STRING, anomes INT64, macro STRING, micro STRING, total FLOAT64, qtd INT64` | Apenas entradas (`tipo = 'E'`). Base de `perfil_financeiro.fontes_renda`. |
| `recorrentes` | `id_usuario STRING, anomes INT64, descr_norm STRING, macro STRING, micro STRING, valor FLOAT64` | 1 linha por ocorrência mensal. A agregação respeita `ate_anomes` na consulta, para não vazar o futuro. |
| `parcelas` | `id_usuario STRING, anomes INT64, descr STRING, macro STRING, parcela_atual INT64, parcela_total INT64, vlr FLOAT64` | Substitui `parcelas_dividas`. Juros ficam em `perfil_mensal.juros`. |
| `categorias` | `macro STRING, micro STRING, discricionaria BOOL, corte_max_pct FLOAT64` | Seed versionado em `data/sql/`. Base de `oportunidades_corte`. |
| `referencia_coorte` | `faixa_renda STRING, macro STRING, media FLOAT64, mediana FLOAT64, qtd_usuarios INT64` | Agregado (P1). Faixas: `ate_3k`, `3k_6k`, `6k_10k`, `10k_20k`, `acima_20k`. |

`capacidade_poupanca` **não é tabela**: é calculada em
`dominio/metricas.py` a partir de `perfil_mensal` filtrado por `ate_anomes`.

### Sem dataset de RAG (Q-17 do 000)

Não há `bussola_rag`. O RAG responde com conhecimento geral (normas do
BACEN, crédito e boas práticas), a partir de um corpus curado no
repositório (§4). Dado do cliente vem só das tabelas de `bussola_dados`,
pelas outras ferramentas.

### `bussola_app`: estado de aplicação (escrita pelo 005/006 via streaming insert)

| Tabela | Colunas |
|---|---|
| `planos` | `plano_id STRING, session_id STRING, id_usuario STRING, objetivo STRING, valor_alvo FLOAT64, prazo_meses INT64, cenario STRING, aporte_mensal FLOAT64, ate_anomes INT64, criado_em TIMESTAMP` |
| `consentimentos` | `consent_id STRING, session_id STRING, plano_id STRING NULL, acao STRING, decisao STRING, texto_apresentado STRING, ts TIMESTAMP` (`decisao` ∈ `aceito`, `recusado`) |
| `auditoria` | `evento_id STRING, session_id STRING, estado STRING, tipo_evento STRING, ferramenta STRING NULL, resumo JSON, ts TIMESTAMP` |
| `acompanhamento` | `plano_id STRING, anomes INT64, planejado FLOAT64, realizado FLOAT64, desvio FLOAT64, categoria_desvio STRING NULL, acao_sugerida STRING NULL, ts TIMESTAMP` |

`bussola_app_dev` tem o mesmo DDL e é **o único dataset onde testes gravam**.
A demo grava em `bussola_app`.

## §4 Interface de domínio (MCP server, Python)

`mcp_server/bussola_mcp/dominio/interfaces.py` (000):

```python
class RepositorioFinanceiro(Protocol):
    def usuario_existe(self, id_usuario: str) -> bool: ...
    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[PerfilMes]: ...
    def gastos_categoria(self, id_usuario: str, ate_anomes: int,
                         desde_anomes: int | None = None) -> list[GastoCategoria]: ...
    def entradas_categoria(self, id_usuario: str, ate_anomes: int) -> list[EntradaCategoria]: ...
    def recorrentes(self, id_usuario: str, ate_anomes: int) -> list[Recorrente]: ...
    def parcelas(self, id_usuario: str, ate_anomes: int) -> list[Parcela]: ...
    def categorias(self) -> list[Categoria]: ...
    def referencia_coorte(self, faixa_renda: str, macro: str | None = None) -> list[RefCoorte]: ...

class BuscadorContexto(Protocol):
    def buscar(self, pergunta: str, k: int,
               tema: TemaConhecimento | None = None) -> list[Trecho]: ...
```

- Os modelos (`PerfilMes`, `GastoCategoria`, …) espelham as colunas do §3.
- `fakes.py` (000) implementa os dois Protocols sobre `contracts/fixtures/`.
- O 001 entrega `RepositorioBigQuery`, com dois modos de leitura via
  `BQ_MODO_LEITURA`:
  - `query`: jobs parametrizados;
  - `memoria`: carga via `list_rows` no startup e filtro em Python. É o
    Plano B, sem `bigquery.jobUser` na SA de runtime.
- O buscador não recebe `id_usuario` nem `ate_anomes`: o corpus é
  conhecimento geral, sem dado de cliente (Q-17 do 000). Devolve até `k`
  trechos com `score > 0`, do mais relevante ao menos relevante, com empate
  por `trecho_id`. `tema` restringe a busca a um tema.
- O 002 entrega `BuscadorLexico` (padrão, sem GCP) e `BuscadorNumpy`
  (similaridade de cosseno sobre embeddings; só a pergunta é embutida em
  tempo de execução, com `EMBEDDING_MODEL`), escolhidos via `RAG_BACKEND`. O
  ponto de entrada é
  `bussola_mcp.rag.criar_buscador(backend: str) -> BuscadorContexto`.
- O `server.py` (003) monta as dependências numa fábrica única:
  - com `BUSSOLA_FAKES=TRUE`, usa os fakes;
  - sem isso, usa `RepositorioBigQuery(modo=BQ_MODO_LEITURA)` e
    `criar_buscador(RAG_BACKEND)`;
  - enquanto `bussola_mcp.rag` não existir em `main`, cai no buscador fake
    com aviso.

**Corpus de conhecimento** (002, Q-17 do 000):

- **Fonte:** `data/rag/corpus/<tema>/<doc_id>.md`, um documento por
  arquivo, com cabeçalho (front matter) `titulo`, `tema`, `fonte_nome`,
  `fonte_referencia` e `fonte_url` (opcional). `doc_id` é o nome do arquivo.
  Cada seção `##` vira um trecho, com `trecho_id = "<doc_id>#<n>"` (n a
  partir de 1).
- **Temas** (`TemaConhecimento`): `norma_bacen`, `credito` e
  `boas_praticas`. Crédito é conteúdo geral (modalidades, custo, direitos,
  renegociação). As dívidas do cliente vêm de `dividas_e_parcelas`.
- **Conteúdo:** texto original em pt-BR, educativo e geral. Cita a norma
  pelo número (ex.: Resolução CMN 4.549/2017) e não copia o texto legal.
  Sem dado de cliente, sem recomendação individual.
- **Índice:** `mcp_server/bussola_mcp/rag/indice/` (versionado, gerado
  offline por `data/rag/indexar.py`): `trechos.jsonl` (um `TrechoCorpus` por
  linha), `embeddings.npy` (float32, uma linha por trecho, na mesma ordem) e
  `manifesto.json` (`modelo_embedding`, `dimensao`, `qtd_trechos`,
  `hash_corpus`, `gerado_em`). O MCP carrega o índice em memória no
  startup, sem BigQuery.

**Simulação** (`dominio/simulacao.py`, 001). Funções puras, sem I/O:

```python
def prazo_para_meta(valor_alvo, aporte_mensal, saldo_inicial=0.0, rendimento_mensal=0.0) -> ResultadoPrazo
def aporte_para_prazo(valor_alvo, prazo_meses, saldo_inicial=0.0, rendimento_mensal=0.0) -> ResultadoAporte
def gerar_cenarios(capacidade: Capacidade, valor_alvo, prazo_meses,
                   gastos: list[GastoCategoria], categorias: list[Categoria],
                   regras: RegrasCenario = RegrasCenario()) -> list[Cenario]
def impacto_cortes(gastos, cortes: dict[str, float]) -> ImpactoCortes
def impacto_dividas(parcelas, renda_media: float) -> ImpactoDividas
```

**`RegrasCenario`** (proposta; a decisão final é a Q2 do contexto mestre):

- `pct_capacidade = {conservador: 0.40, equilibrado: 0.60, acelerado: 0.80}`,
  aplicado sobre a **sobra mensal mediana**;
- no acelerado entram os cortes sugeridos das categorias discricionárias;
- `rendimento_mensal = 0.0` por padrão, porque não há dado de investimento na
  base e não se inventam taxas;
- `saldo_inicial = 0.0` por padrão (saldo de conta não é reserva); pode ser
  ligado com `usar_saldo_atual`.

**Métricas** (`dominio/metricas.py`, 001). Funções que transformam as linhas
do repositório no campo `dados` de cada ferramenta (§5). As ferramentas do 003
só validam a entrada, chamam métricas/simulação e montam o envelope.

## §5 Ferramentas MCP (servidor `bussola-mcp`, streamable HTTP em `/mcp`)

**Parâmetros comuns (obrigatórios em todas):**

- `id_usuario: str` (UUID);
- `ate_anomes: int` (`202501`–`202512`).

O agente sobrescreve os dois a partir do `session.state` (§6). Valores
enviados pelo modelo são ignorados.

**Validação:** faixas, UUID e regras de entrada são verificadas **dentro**
da ferramenta, pelos modelos `Entrada*` de `contratos.py`, e uma falha
devolve o envelope `ENTRADA_INVALIDA` (não é erro de protocolo). A mensagem
cita só os nomes dos campos inválidos, nunca o valor recebido (Q-10 do 000).

**Envelope de sucesso:**

```json
{
  "dados": { "...": "..." },
  "fonte": {
    "ferramenta": "perfil_financeiro",
    "tabelas": ["bussola_dados.perfil_mensal"],
    "periodo": {"inicio": 202501, "fim": 202506}
  },
  "avisos": ["Saldo ficou negativo em 1 mês do período."]
}
```

**Envelope de erro** (é retornado como resultado da ferramenta; não é
exceção):

```json
{"erro": {"codigo": "USUARIO_INEXISTENTE", "mensagem": "Cliente não encontrado."}}
```

Códigos de erro:

- `USUARIO_INEXISTENTE`
- `ENTRADA_INVALIDA`
- `PRAZO_IMPLAUSIVEL`
- `DADOS_INSUFICIENTES`
- `INDISPONIVEL`

| Ferramenta | Prioridade | Entrada adicional | `dados` |
|---|---|---|---|
| `perfil_financeiro` | P0 | — | `renda_media, gasto_medio, sobra_media, sobra_mediana, fontes_renda[{macro, micro, media}], saldo{minimo, maximo, atual}, serie_mensal[{anomes, renda, gasto, sobra}], meses_considerados` |
| `capacidade_poupanca` | P0 | — | `sobra_media, sobra_mediana, desvio_padrao, meses_negativos, meses_considerados` |
| `oportunidades_corte` | P0 | `top_n: int = 5` (1–10) | `categorias[{macro, micro, media_mensal, discricionaria, economia_potencial_mensal, criterio}]` |
| `dividas_e_parcelas` | P0 | — | `parcelas_ativas[{descr, parcela_atual, parcela_total, valor, meses_restantes}], juros_pagos_media, comprometimento_renda_pct` |
| `simular_objetivo` | P0 | `valor_alvo > 0` e **um** entre `prazo_meses` (1–360) ou `aporte_mensal > 0`; `usar_saldo_atual: bool = false` | `modo ("prazo" \| "aporte"), valor_alvo, aporte_mensal, prazo_meses, viavel, folga_mensal, premissas{…}` |
| `comparar_cenarios` | P0 | `valor_alvo > 0`, `prazo_meses` (1–360) | `cenarios[{nome, pct_capacidade, aporte_mensal, prazo_meses, viavel, cortes_sugeridos[{macro, micro, valor_mensal}], trade_offs[str]}], regras{…}` |
| `buscar_contexto_financeiro` | P0 | `pergunta: str` (≤ 500 caracteres), `k: int = 5` (1–10), `tema: str \| None = None` (`norma_bacen` \| `credito` \| `boas_praticas`) | `trechos[{doc_id, trecho_id, titulo, tema, texto, fonte{nome, referencia, url}, score}]` |
| `resumo_mes` | P1 | `anomes` (≤ `ate_anomes`) | `anomes, renda, gasto, sobra, gastos_macro[{macro, total}]` (usado pelo 006) |
| `referencia_coorte` | P1 | `categoria` (macro) | `faixa_renda, macro, media, mediana, qtd_usuarios` |

- `trade_offs` são frases geradas por regra determinística (ex.: "exige
  reduzir R$ 250/mês em Restaurantes"). Não são geradas por LLM.
- **`buscar_contexto_financeiro`** responde com o corpus de conhecimento
  (§4), igual para qualquer cliente (Q-17 do 000). `id_usuario` e
  `ate_anomes` seguem obrigatórios e validados, mas não filtram o corpus.
  Avisos:
  - sempre `"Conteúdo educativo e geral, não é recomendação individual.
    Confira a norma em vigor no site do Banco Central."`;
  - com lista vazia, também `"Nenhum trecho da base de conhecimento
    responde a esta pergunta."`.
- Nenhuma ferramenta aceita SQL nem devolve SQL, nomes de projeto ou
  credenciais. `fonte.tabelas` traz só `dataset.tabela`.
- **`modo` de `simular_objetivo`** indica o que a entrada informou (Q-06 do
  000):
  - `"prazo"`: a entrada trouxe `prazo_meses`, e a ferramenta calcula
    `aporte_mensal`;
  - `"aporte"`: a entrada trouxe `aporte_mensal`, e a ferramenta calcula
    `prazo_meses`.

  Nos dois casos, `aporte_mensal` e `prazo_meses` vêm preenchidos.
- **`fonte.tabelas` por ferramenta** (`contratos.TABELAS_FERRAMENTA`, Q-07
  do 000):

  | Ferramenta | `fonte.tabelas` |
  |---|---|
  | `perfil_financeiro` | `bussola_dados.perfil_mensal`, `bussola_dados.entradas_categoria` |
  | `capacidade_poupanca` | `bussola_dados.perfil_mensal` |
  | `oportunidades_corte` | `bussola_dados.gastos_categoria`, `bussola_dados.categorias` |
  | `dividas_e_parcelas` | `bussola_dados.parcelas`, `bussola_dados.perfil_mensal` |
  | `simular_objetivo` | `bussola_dados.perfil_mensal` |
  | `comparar_cenarios` | `bussola_dados.perfil_mensal`, `bussola_dados.gastos_categoria`, `bussola_dados.categorias` |
  | `buscar_contexto_financeiro` | nenhuma (`[]`): corpus no repositório |
  | `resumo_mes` | `bussola_dados.perfil_mensal`, `bussola_dados.gastos_categoria` |
  | `referencia_coorte` | `bussola_dados.referencia_coorte` |

## §6 Agente (serviço `bussola-agent`)

### Chaves de `session.state` (`agent/bussola_agent/estado.py`, 000)

| Chave | Tipo | Quem escreve |
|---|---|---|
| `id_usuario` | str | 004, no início da sessão, a partir de `ANCHOR_USER_ID` |
| `ate_anomes` | int | 004 no início (`REPLAY_START_ANOMES`); **só o 006 avança** |
| `estado_jornada` | enum `OBJETIVO` \| `ENTENDER` \| `ANTECIPAR` \| `ORIENTAR` \| `AGIR` \| `ACOMPANHAR` | 004 (005 e 006 nas transições para AGIR e ACOMPANHAR) |
| `objetivo` | `{tipo, descricao, valor_alvo, prazo_meses, prioridade}` | 004 |
| `cenarios` | último `dados` de `comparar_cenarios` | 004 |
| `cenario_escolhido` | str \| None | 004 |
| `ultimas_fontes` | list[`fonte`] | 004 |
| `consentimentos` | `{acao: {consent_id, status: pendente \| aceito \| recusado, ts}}` | 005 |
| `plano_id` | str \| None | 005 |
| `acompanhamento` | list[resultado mensal] | 006 |

### Encadeador de callbacks (`agent/bussola_agent/callbacks.py`, 000)

- `registrar(fase, funcao, ordem)` com `fase` ∈ `before_model`,
  `after_model`, `before_tool`, `after_tool`.
- A cadeia roda em ordem crescente, e o primeiro retorno não nulo interrompe
  a execução.
- O `agent.py` (004) só instala os quatro callbacks agregados.
- Os agregados são `async` e recebem os argumentos do ADK por palavra-chave.
  Cada função registrada pode ser sync ou async. Empates de `ordem` seguem a
  ordem de registro, e uma fase inválida gera `ValueError`.
- `limpar()` esvazia os registros e existe só para testes (Q-09 do 000).

Ordens reservadas:

| Fase | Ordem | Dono | Função |
|---|---|---|---|
| `before_model` | 10 | 005 | guardrail de entrada (Model Armor ou fallback) |
| `before_model` | 20 | 005 | leitura determinística da resposta de consentimento |
| `before_tool` | 10 | 004 | **escopo**: sobrescreve `id_usuario` e `ate_anomes` com o `session.state` |
| `before_tool` | 20 | 005 | gate: ação sensível sem consentimento `aceito` é bloqueada |
| `before_tool` / `after_tool` | 90 | 005 | auditoria |
| `after_tool` | 10 | 004 | registra `fonte` em `ultimas_fontes` |
| `after_model` | 10 | 005 | guardrail de saída |
| `after_model` | 50 | 004 | verificação de números (opcional) |

### Ações do estado AGIR (ferramentas ADK locais, não MCP)

- **Livres:** todas as ferramentas MCP (leitura), além de
  `registrar_objetivo` e `escolher_cenario` (004).
- **Sensíveis:** exigem consentimento `aceito` com `consent_id` válido. São
  todas **simuladas**, sem efeito externo além de gravar em `bussola_app`.
  Dono: 005.
  - `criar_plano(cenario)`
  - `ativar_lembretes(frequencia)`
  - `simular_contratacao(tipo_produto)` (genérico, sem taxas)
  - `compartilhar_dados(destino)` (sempre recusada na PoC; existe só para
    demonstrar a classificação)
  - `ajustar_plano(aporte_mensal, prazo_meses)`, do 006: adota a rota
    recalculada no ACOMPANHAR. O catálogo do 005 já a classifica como
    sensível.
- **Consentimento:** `solicitar_consentimento(acao, resumo)` (005). Uma ação
  sensível chamada sem consentimento `aceito` recebe do gate o resultado
  `{"erro": {"codigo": "CONSENTIMENTO_NECESSARIO", "mensagem": "..."}}`.
  Esse código é local do agente, não do MCP.
- **ACOMPANHAR:** `avancar_mes()` e `status_plano()` (006). Erros locais do
  agente: `SEM_PLANO_ATIVO` (sem `plano_id` no state) e `FIM_DO_REPLAY`
  (`ate_anomes` já em 202512).

### Extensões (`agent/bussola_agent/extensoes.py`, 000)

Permite que 005 e 006 acrescentem comportamento sem editar o `agent.py` do
004.

```python
def registrar_ferramenta(fn: Callable, sensivel: bool = False) -> None: ...
def registrar_instrucao(ordem: int, texto: str) -> None: ...   # trecho do prompt
def ferramentas() -> list[Callable]: ...
def instrucoes() -> str: ...                                    # concatenadas por ordem
def carregar_extensoes() -> None: ...
def ferramentas_sensiveis() -> set[str]: ...                    # nomes com sensivel=True (Q-09)
def limpar() -> None: ...                                       # só testes (Q-09)
```

- `carregar_extensoes()` importa `bussola_agent.governanca` e
  `bussola_agent.acompanhamento` quando existirem. Um pacote ausente
  (`importlib.util.find_spec` devolve `None`) é pulado; um pacote presente
  com erro de import **propaga** o erro, para não esconder falhas do 005/006
  (Q-04 do 000).
- Registrar duas ferramentas com o mesmo nome gera `ValueError`.
- O `__init__.py` de cada pacote registra suas ferramentas, instruções e
  callbacks.
- O `agent.py` chama `carregar_extensoes()` e depois monta o
  `root_agent`, usando `ferramentas()` e acrescentando `instrucoes()` ao
  prompt base.
- Ordens de instrução reservadas: 004 usa 0–49, 005 usa 50–69 e 006 usa
  70–89.

### Persistência (`agent/bussola_agent/persistencia.py`, 000)

```python
class RegistroApp(Protocol):
    def registrar_plano(self, plano: Plano) -> str: ...
    def registrar_consentimento(self, c: Consentimento) -> str: ...
    def registrar_evento(self, e: EventoAuditoria) -> str: ...
    def registrar_acompanhamento(self, a: Acompanhamento) -> None: ...
    def obter_plano(self, plano_id: str) -> Plano | None: ...
```

- `RegistroEmMemoria` (000) é o fake.
- `RegistroBigQuery` (005, `persistencia_bq.py`) grava via streaming insert
  em `BQ_DATASET_APP`.

**`tipo_evento` da auditoria:**

- `sessao_iniciada`
- `estado_alterado`
- `ferramenta_chamada`
- `consentimento_solicitado`
- `consentimento_decidido`
- `plano_criado`
- `acao_executada`
- `guardrail_bloqueio`
- `acompanhamento_mes_avancado`
- `desvio_detectado`
- `rota_recalculada`
- `plano_ajustado`

### Conexão MCP (`agent/bussola_agent/mcp_conexao.py`, 000)

- Cria o `MCPToolset` com `StreamableHTTPConnectionParams(url=MCP_URL)`.
- Com `MCP_USE_OIDC=TRUE`, adiciona o header `Authorization: Bearer <ID token>`
  com `audience` = URL base do `bussola-mcp`.
- A SA de runtime do agente precisa de `roles/run.invoker` no serviço
  `bussola-mcp` (nível do serviço, com confirmação humana; Q-16 do 000).
- `async def chamar_ferramenta(nome: str, args: dict, state: dict) -> dict`
  chama uma ferramenta MCP diretamente, sem passar pelo LLM. Aplica o mesmo
  escopo do callback do 004, forçando `id_usuario` e `ate_anomes` a partir
  do `state`. O 006 usa essa chamada para `resumo_mes` e `simular_objetivo`.
- Acréscimos do 000 (Q-09):
  - `criar_toolset(url=None, usar_oidc=None, tool_filter=None) -> McpToolset`
    lê `MCP_URL` e `MCP_USE_OIDC` quando os argumentos são `None`;
  - `aplicar_escopo(args, state) -> dict` devolve uma cópia de `args` com
    `id_usuario` e `ate_anomes` do `state`;
  - `chamar_ferramenta(nome, args, state, url=None, usar_oidc=None)`: uma
    falha de transporte devolve o envelope `INDISPONIVEL` em vez de levantar
    exceção.

## §7 Variáveis de ambiente (`contracts/env.example`)

| Variável | Serviço | Valor padrão / exemplo |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | ambos | `batalha-time-07-lkbv` |
| `GOOGLE_CLOUD_LOCATION` | ambos | `us-central1` (BigQuery, embedding); no agente, vem de `BUSSOLA_LOCAL_MODELO` |
| `GOOGLE_GENAI_USE_VERTEXAI` | agent, rag | `TRUE`; `FALSE` no Plano B |
| `GOOGLE_API_KEY` | agent, rag | só no Plano B; **nunca** versionar |
| `BUSSOLA_MODEL` | agent | ID do Gemini Flash validado no 000 |
| `BUSSOLA_LOCAL_MODELO` | agent | `global`: `GOOGLE_CLOUD_LOCATION` do agente (local e deploy); o Flash validado só responde em `global` (Q-15 do 000) |
| `EMBEDDING_MODEL` | mcp, rag | ID validado no 000 |
| `MCP_URL` | agent | `http://localhost:8080/mcp` |
| `MCP_USE_OIDC` | agent | `FALSE` local, `TRUE` no Cloud Run |
| `MODEL_ARMOR_TEMPLATE` | agent | vazio = fallback de callbacks |
| `ANCHOR_USER_ID` | agent | `36a21505-d6d4-42d3-b319-d51a133c7269` |
| `REPLAY_START_ANOMES` | agent | `202506` |
| `BQ_DATASET_DADOS` / `BQ_DATASET_APP` | mcp / agent | `bussola_dados` / `bussola_app` (testes: `bussola_app_dev`) |
| `BQ_MODO_LEITURA` | mcp | `query` \| `memoria` |
| `RAG_BACKEND` | mcp | `lexico` (padrão, sem GCP) \| `numpy` (embeddings, Plano A) |
| `BUSSOLA_FAKES` | ambos | `TRUE` em testes e desenvolvimento isolado |
| `LOG_LEVEL` | ambos | `INFO` |
| `PORT` | ambos | `8080` (Cloud Run) |

## §8 Fixtures (`contracts/fixtures/`)

Geradas pelo 000 com `data/scripts/gerar_fixtures.py`, por SQL de referência
direto no extrato. São **provisórias**: quando as tabelas oficiais estiverem
prontas, o 001 regenera as fixtures a partir delas (PR `contracts:`).

- `usuarios.json`: âncora `36a21505-d6d4-42d3-b319-d51a133c7269` e controle
  `31e94f2f-1463-49f9-a41a-b3f220ed976a`. O controle serve aos testes
  negativos de escopo.
- `bussola_dados/<tabela>.json`: linhas das tabelas do §3 para os 2
  usuários, com 12 meses.
- `ferramentas/<ferramenta>__ate_202506.json` e `…__ate_202512.json`:
  envelopes esperados de cada ferramenta P0 para o usuário-âncora (golden),
  exceto `buscar_contexto_financeiro`, que não tem golden
  (`contratos.FERRAMENTAS_GOLDEN`, Q-17 do 000).
- `ferramentas/resumo_mes__<AAAAMM>.json`: um envelope por mês, de 202501 a
  202512, para o âncora. O 006 usa esses arquivos antes do 003 real.
- O MCP mock do 000 serve as ferramentas P0 e também `resumo_mes`, a partir
  desses arquivos:
  - `ate_anomes < 202512` recebe o golden `__ate_202506`, com um aviso de
    mock;
  - `ate_anomes = 202512` recebe o golden `__ate_202512`.
  - usuário de `usuarios.json` que não é o âncora (o controle) recebe
    `DADOS_INSUFICIENTES` ("O mock só tem respostas do cliente âncora."). O
    mock nunca devolve o golden de outro cliente (Q-01 do 000);
  - `simular_objetivo` e `comparar_cenarios` têm golden só para a entrada
    canônica `valor_alvo=30000`, `prazo_meses=24`. O mock serve esse golden
    para qualquer entrada válida, com o aviso "Resposta de exemplo do mock,
    calculada para valor_alvo=30000 e prazo_meses=24." (Q-03 do 000);
  - o golden de `oportunidades_corte` guarda até 10 itens, e o mock corta
    a lista em `top_n`;
  - arquivo de fixture ausente devolve `INDISPONIVEL` ("Dados de exemplo
    indisponíveis.");
  - `referencia_coorte` (P1) não é servida pelo mock.
  - `buscar_contexto_financeiro` roda o buscador fake sobre
    `rag/trechos_exemplo.json` para qualquer usuário de `usuarios.json`,
    inclusive o controle, e para qualquer corte. Corpus ausente ou inválido
    devolve `INDISPONIVEL`.
- `rag/trechos_exemplo.json`: amostra curada à mão do corpus de
  conhecimento (lista de `TrechoCorpus`, cobrindo os três temas). Não é
  gerada por `gerar_fixtures.py`, que também não a apaga.
- Formato: cada arquivo de tabela, `usuarios.json` e `rag/trechos_exemplo.json`
  é uma **lista JSON** de objetos; cada golden é um envelope JSON (Q-11 do
  000).

**Valores de referência do âncora** (média de 2025, `ate_anomes = 202512`,
tolerância de 1%):

- renda ≈ 7.451
- gasto ≈ 4.615
- sobra ≈ 2.836
- aluguel ≈ 1.077
- comer fora ≈ 364
- assinaturas ≈ 101
- juros ≈ 61
- saldo mínimo ≈ −2.072
- saldo máximo ≈ 49.321

## §9 Logs estruturados (os dois serviços)

- **Formato:** JSON em stdout, uma linha por evento, compatível com Cloud
  Logging (`severity`, `message`).
- **Campos:**
  - `servico`
  - `session_id`
  - `estado_jornada`
  - `ferramenta`
  - `evento`
  - `consentimento`
  - `ate_anomes`
  - `latencia_ms`
  - `erro_codigo`
- **Nunca logar:** prompt completo, texto de lançamentos, chaves ou tokens.
  O `id_usuario` sintético pode ser logado.
- **Lista de permitidos:** o logger emite só `severity`, `message`,
  `timestamp`, os campos acima e `id_usuario`. Outros campos extras são
  descartados.
- **Exceções:** registradas só no campo `excecao`, com o **nome da classe**,
  sem traceback nem mensagem (Q-05 do 000).
