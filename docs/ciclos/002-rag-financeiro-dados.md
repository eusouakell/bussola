# Ciclo 002 — F2 RAG financeiro a partir da base

> **Disparo:** `/spec-master docs/ciclos/002-rag-financeiro-dados.md`, no
> Claude Code, dentro da worktree `../bussola-002`, na branch
> `002-rag-financeiro-dados`.
>
> **Onda:** 2 (pode começar junto com a Onda 1). **Prioridade:** P0 (itens
> 1–2), P1 (item 3), P2 (item 4 e recategorização). **Spec:**
> `specs/002-rag-financeiro-dados`. **Plano:** [README](./README.md).
>
> **Leitura obrigatória antes do Step 3:**
>
> - [contratos.md](./contratos.md) §3 (`bussola_rag`), §4 e §5
>   (`buscar_contexto_financeiro`), §7 e §8.
> - Contexto mestre [§8, §9, §10 F2, §17](../contexto-spec-master.md).

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Uma única feature:** `id: rag-financeiro-dados`,
   `spec_directory: specs/002-rag-financeiro-dados`.
2. **Número fixo:** `SPECIFY_FEATURE_DIRECTORY=specs/002-rag-financeiro-dados`.
3. **Step 2:** Spec Kit já inicializado. Estratégia Git **Trunk-Based**.
4. **Constituição congelada.** Proposta vai para
   `specs/002-*/proposta-constituicao.md`.
5. **Escreva só nos caminhos da §4.** Só este ciclo escreve em
   `bussola_rag`.
6. **Antes do marco "tabelas v1" do 001:** desenvolva os templates e o
   buscador sobre `contracts/fixtures/bussola_dados/`. O corpus real só é
   gerado depois do marco.
7. **Texto determinístico.** Nenhum LLM gera fatos do corpus; o LLM só
   aparece no embedding.
8. **Ao final:**
   - `make test` e `make lint` verdes;
   - rastreabilidade em `specs/002-*/traceability.md`.

## 2. Propósito

Construir o corpus e a recuperação do mestre §9 **a partir da própria base
sintética**. O RAG dá **contexto e explicação** ("em março seu saldo ficou
negativo depois do aluguel"). Os valores apresentados continuam vindo das
ferramentas determinísticas.

## 3. Escopo e comportamento esperado

### 3.1 Gerador de corpus (`data/rag/gerar_corpus.py`)

- **Entrada:** tabelas `bussola_dados`, ou fixtures com `--fixtures`.
- **Saída:** linhas de `bussola_rag.documentos` com as colunas de
  `contratos.md` §3.

| `tipo` | Prio | Conteúdo (templates pt-BR em `data/rag/templates/`) |
|---|---|---|
| `ficha_mensal` | P0 | 1 por usuário/mês. Renda e fontes; gasto total e top macro; parcelas ativas; juros; saldo inicial, final e mínimo; eventos: saldo negativo, gasto atípico (acima de 1,5× a média da categoria), sobra negativa |
| `perfil_anual` | P0 | 1 por usuário, `anomes = 202512`. Recorrentes (aluguel, assinaturas), comer fora, delivery, transporte; tendência do 1º contra o 2º semestre; mês de maior gasto |
| `coorte` | P1 | 1 por faixa de renda × macro, a partir de `referencia_coorte`, com `id_usuario = NULL`. Nunca dado individual |
| `lancamento` | P2 | `descr` normalizada por usuário (busca semântica e apoio à recategorização) |

- **`fonte` (JSON):** `{id_usuario, anomes, categorias[], tabelas[]}`.
- **Idempotência:**
  - `doc_id = sha1(tipo|id_usuario|anomes|versao_template)`;
  - a gravação usa tabela de staging + `MERGE`, ou `DELETE` por `doc_id` +
    insert;
  - uma segunda execução não duplica linhas.
- **Opções:**
  - `--usuarios <uuid,...>` para desenvolvimento rápido (âncora +
    controle);
  - `--todos` para o corpus completo (~13 mil documentos P0);
  - `--dry-run` para imprimir amostras sem gravar.

### 3.2 Embeddings (`data/rag/embeddings.py`)

- Usa `EMBEDDING_MODEL` (validado no 000) via `google-genai`. O caminho
  padrão é Vertex; `GOOGLE_GENAI_USE_VERTEXAI=FALSE` + chave é o Plano B.
- Tipos de tarefa: `RETRIEVAL_DOCUMENT` no corpus e `RETRIEVAL_QUERY` na
  pergunta.
- Lotes com retry e backoff. Grava `modelo_embedding` e `gerado_em`.
- A dimensão do vetor é registrada em `specs/002-*/embeddings.md`.

### 3.3 Buscadores (`mcp_server/bussola_mcp/rag/`)

- **`criar_buscador(backend)`:** retorna `BuscadorBigQuery` (`bq`) ou
  `BuscadorNumpy` (`numpy`). Ambos implementam `BuscadorContexto`.
- **`BuscadorBigQuery`:**
  1. gera o embedding da pergunta;
  2. roda `VECTOR_SEARCH` sobre uma subconsulta **já filtrada** (pré-filtro
     exato):
     `(id_usuario = @id_usuario OR tipo = 'coorte') AND (anomes IS NULL OR anomes <= @ate_anomes)`;
  3. usa `distance_type => 'COSINE'` e `top_k => @k`;
  4. passa o vetor da pergunta como parâmetro.

  Índice vetorial é opcional: com ~13 mil linhas, a busca exata basta.
- **`BuscadorNumpy`** (Plano B, sem `jobUser`):
  - carrega a tabela via `list_rows` no startup;
  - aplica o mesmo filtro por máscara;
  - calcula similaridade de cosseno e retorna o top-k.
- **`score`:** 1 − distância.
- **`origem`:** `{id_usuario, anomes, categoria}` (primeira categoria da
  `fonte`).

### 3.4 Avaliação (`eval/rag/`)

- **`perguntas.yaml`:** 10 ou mais perguntas sobre o âncora, cada uma com os
  `doc_id` esperados. Exemplos:
  - "em que mês meu saldo ficou negativo?";
  - "quanto gasto com assinaturas?";
  - "tenho parcelas ativas?".
- **`rodar_eval.py`:** calcula o acerto no top-3 e grava
  `eval/rag/resultado.md`.
- **Testes negativos:**
  - perguntas sobre particularidades do controle, feitas na sessão do
    âncora, nunca retornam documentos do controle;
  - com `ate_anomes = 202506`, nunca retorna `anomes > 202506` nem
    `perfil_anual`.

## 4. Propriedade (escreve só aqui)

- `data/rag/`
- `mcp_server/bussola_mcp/rag/`
- `mcp_server/tests/rag/`
- `eval/rag/`
- Dados em `bussola_rag`
- Acréscimos em `mcp_server/pyproject.toml` e `Makefile` (ex.:
  `make corpus`)
- `specs/002-rag-financeiro-dados/`

## 5. Contratos

- **Consome:**
  - tabelas `bussola_dados` (001);
  - `interfaces.BuscadorContexto` e o modelo `Trecho`;
  - env `EMBEDDING_MODEL`, `BQ_DATASET_RAG` e `RAG_BACKEND`.
- **Provê:**
  - `bussola_rag.documentos` preenchida;
  - `bussola_mcp.rag.criar_buscador`, plugado pela fábrica do `server.py`
    do 003 sem mudar a ferramenta.

## 6. Critérios de aceite

- [ ] Um script idempotente gera o corpus (fichas mensais + perfil anual) a
      partir de F1 e grava textos e embeddings em `bussola_rag`. Uma
      segunda execução não duplica.
- [ ] A busca retorna top-k trechos **somente** do `id_usuario` da sessão
      ou de coorte. Há teste negativo nos dois backends.
- [ ] Cada trecho traz a referência de origem (usuário, mês, categoria).
- [ ] O corte temporal é respeitado nos dois backends.
- [ ] 10 ou mais perguntas de avaliação sobre o âncora, com o trecho
      esperado no top-3 em pelo menos 80% dos casos. Resultado em
      `eval/rag/resultado.md`.
- [ ] Os dois backends devolvem o mesmo top-3 para as perguntas do eval,
      ou uma diferença justificada por empate de score.
- [ ] A ferramenta `buscar_contexto_financeiro` do 003 funciona com
      `RAG_BACKEND=bq` e `RAG_BACKEND=numpy`, sem alteração de código na
      ferramenta.

## 7. Cenários de teste

- Duas execuções de `gerar_corpus --usuarios <âncora>`: a contagem por
  `tipo` fica igual.
- A ficha de um mês com `saldo_minimo < 0` contém a frase de evento de
  saldo negativo.
- Buscador com o id do controle e uma pergunta sobre aluguel: todos os
  trechos têm `id_usuario` do controle ou `tipo = coorte`.
- Pergunta vazia ou só com espaços: é rejeitada na ferramenta (003). No
  buscador, retorna lista vazia sem chamar embedding.

## 8. Dependências e gate de merge

- **Dependências duras:** 000. Para o corpus real, o marco "tabelas v1" do
  001 no BigQuery, não o merge.
- **Runtime:** o MCP precisa gerar o embedding da pergunta. A SA precisa de
  `aiplatform.user` (pedido ao owner) ou do Plano B com chave.
- **Gate de merge:** corpus real + eval com pelo menos 80% + buscador
  plugado na ferramenta do 003. Este é o **6º na ordem de merge**.

## 9. Fora de escopo

- Catálogo de produtos Itaú e conteúdos de educação financeira (Q3).
- Recategorização assistida (P2), só se sobrar tempo.
- RAG Engine do Agent Platform (alternativa, Q6).
- Valores numéricos para o cliente: são das ferramentas (001/003).

## 10. Questões em aberto

- **Q3 do mestre:** haverá conteúdo curto escrito pelo time? Se sim, entra
  como novo `tipo` via PR `contracts:`.
- **Q6 do mestre:** `VECTOR_SEARCH` (recomendado) ou RAG Engine.
- O limiar de "gasto atípico" (1,5×) é INFERRED.

## 11. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| Corpus derivado da base (fichas, perfil anual, coorte, lançamentos) | Mestre §9; decisão do time | EXPLICIT |
| Filtro por usuário, origem e eval top-3 ≥ 80% | Mestre §10 F2 | EXPLICIT |
| Embeddings em Python e `VECTOR_SEARCH`, com Plano B numpy | Mestre §9 e §17 | EXPLICIT |
| `doc_id` por hash e staging + `MERGE` | Este ciclo | INFERRED |
| Limiar de gasto atípico | Este ciclo | INFERRED |
| Conteúdo de produtos e backend final | Mestre §20, Q3 e Q6 | UNRESOLVED |
