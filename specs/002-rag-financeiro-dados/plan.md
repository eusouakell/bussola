# Implementation Plan: RAG de conhecimento financeiro

**Branch**: `002-rag-financeiro-dados` | **Spec**: [spec.md](./spec.md) |
**Input**: `docs/ciclos/002-rag-financeiro-dados.md`

## Summary

O ciclo entrega três coisas:

- um corpus educativo em Markdown (`data/rag/corpus/`);
- um índice versionado em `mcp_server/bussola_mcp/rag/indice/`;
- dois buscadores atrás do Protocol `BuscadorContexto`.

O `lexico` usa BM25, é puro Python e é o padrão. O `numpy` usa cosseno
sobre embeddings Gemini. O 003 pluga `criar_buscador(RAG_BACKEND)` no
`server.py` sem mudar a ferramenta.

## Technical Context

- **Linguagem:** Python 3.12, com `uv`. O projeto é o `mcp_server`, e os
  scripts de `data/rag/` e `eval/rag/` rodam com
  `uv run --project mcp_server`.
- **Dependências:**
  - `google-genai`, nova em runtime e importada só pelo adaptador de
    embedding;
  - `numpy` (já existia);
  - `pyyaml`, nova em dev e usada só pelo eval.
- **Armazenamento:** arquivos no repositório. Não há BigQuery (Q-17 do
  000).
- **Testes:** `pytest`, sem rede (guarda do `conftest.py`). O teste com
  Gemini real leva `@pytest.mark.gemini` e é excluído do `make test`.
- **Restrições:**
  - o índice cabe no repositório (menos de 1 MB);
  - o embedding usa 768 dimensões;
  - o texto do corpus é original.

## Constitution Check

| Princípio | Como o plano cumpre | Status |
|---|---|---|
| I. Números de ferramentas | O RAG só explica conceitos. Os produtos não têm taxa (validador), e os números do cliente continuam no 003. | PASS |
| II. Agente isolado de SQL/infra | Não há SQL. A falha de embedding vira `EmbeddingUnavailableError`, com mensagem genérica em pt-BR e sem detalhe do provedor. | PASS |
| III. Read-only e escopo | O buscador não recebe `id_usuario`. O validador barra UUID, CPF, CNPJ, e-mail e números longos no corpus. | PASS |
| IV. Respostas rotuladas | Cada trecho traz `fonte` (nome, referência e url). O rótulo é do 004. | PASS |
| V. Dados sintéticos e logs seguros | O corpus não tem dado de cliente. O log usa só `evento` e `erro_codigo`, nunca a pergunta ou o texto. | PASS |
| VI. Consentimento | Não se aplica: busca de conhecimento geral. | N/A |
| VII. Segredos | A chave do Plano B entra só inline no ambiente do processo. Nada a lê, imprime ou grava. | PASS |
| VIII. pt-BR | O corpus, as mensagens e as docs estão em pt-BR. Módulos internos usam inglês técnico, com consistência por módulo. | PASS |
| IX. Testes sem rede | Todos os testes do `make test` rodam offline, com embedder fake injetado. O teste Gemini é marcado. | PASS |
| X. Contratos | O código só fica nos caminhos do 002. `Makefile` e `pyproject.toml` só recebem acréscimos. Nenhum arquivo de contrato é alterado. | PASS |

Sem violações, então não há `proposta-constituicao.md`.

## Project Structure

```text
data/rag/
├── corpus/{norma_bacen,credito,boas_praticas,produto}/<doc_id>.md
├── validar_corpus.py        # CLI: valida o corpus (exit 1 + lista de erros)
└── indexar.py               # CLI: gera o índice (idempotente, --sem-embeddings)
mcp_server/bussola_mcp/rag/
├── __init__.py              # criar_buscador, BuscadorLexico, BuscadorNumpy
├── text.py                  # normalização pt-BR, stopwords, radical leve
├── corpus.py                # parser do Markdown + validação (build)
├── index.py                 # formato do índice, manifesto, hash, carga
├── lexical.py               # BuscadorLexico (BM25 + título + cobertura)
├── vector.py                # BuscadorNumpy (cosseno + máscara de tema)
├── embedding.py             # porta Embedder + GeminiEmbedder
└── indice/{trechos.jsonl, embeddings.npy, manifesto.json}
mcp_server/tests/rag/        # unidade, integração, contrato, índice versionado
eval/rag/{perguntas.yaml, rodar_eval.py, RESULTADOS.md, embeddings_perguntas.npz}
```

## Decisões de design

- **Hash do corpus.** `hash_corpus` é o sha256 do conteúdo canônico de
  `trechos.jsonl`: JSON com chaves ordenadas, uma linha por trecho, na
  ordem tema → doc_id → n.
- **Idempotência.** Com o mesmo hash, `trechos.jsonl` igual e, quando há
  embedder, manifesto com o mesmo modelo e a mesma dimensão, nada é escrito
  e o modelo não é chamado. Se o corpus mudar com `--sem-embeddings`, o
  `embeddings.npy` antigo é removido e `modelo_embedding`/`dimensao` ficam
  `null`.
- **Léxico.**
  - É um BM25 (`k1=1.5`, `b=0.75`) em que o título da seção conta em
    dobro.
  - Um trecho só entra se a cobertura de IDF dos termos da pergunta passar
    do mínimo: `min_coverage=0.2` com dois ou mais termos casados e
    `single_term_coverage=0.5` com um só. Isso barra perguntas fora do
    domínio que casam por acaso com uma palavra comum.
  - O radical não tira vogal final depois de vogal ("cartão" não vira
    "carta", que colidia com a carta de crédito do consórcio).
  - O score é o BM25 arredondado a 4 casas.
- **Numpy.**
  - A matriz é normalizada na carga. A pergunta é embutida com
    `RETRIEVAL_QUERY` e a dimensão do manifesto.
  - Só entram scores acima de `min_score=0.64`, calibrado no eval.
  - O modelo vem de `EMBEDDING_MODEL`, ou do manifesto quando a variável
    está vazia. Se divergir do manifesto, ou se o embedder injetado tiver
    outro modelo ou dimensão, sobe `InvalidIndexError(ValueError)`.
- **Erros.**
  - `InvalidIndexError(ValueError)` cobre índice ausente, inconsistente ou
    sem embeddings.
  - `EmbeddingUnavailableError(RuntimeError)` sai com `from None`. Em
    qualquer dos casos, a ferramenta do 003 devolve `INDISPONIVEL`.
- **Adaptador Gemini.**
  - O `genai.Client()` lê `GOOGLE_GENAI_USE_VERTEXAI`, o projeto, o local e
    `GOOGLE_API_KEY` do ambiente.
  - O lote é de 1 no Vertex e de 20 na Gemini API.
  - Há 3 tentativas com espera crescente, só na indexação.

## Estratégia de testes

- **Unidade:**
  - `text`: acentos, stopwords e radical;
  - `corpus`: parser e cada regra do validador, com o nome do arquivo;
  - `index`: hash, manifesto e carga inválida;
  - `lexical`: ranking, tema, empate, `score > 0` e fora do domínio;
  - `vector`, com embedder fake: cosseno, máscara, limiar, pergunta vazia
    sem chamada, modelo divergente e falha genérica;
  - `embedding`, com cliente fake: tarefa, dimensão e lote.
- **Integração:**
  - `indexar.build_index` duas vezes sobre um corpus temporário: bytes
    iguais e modelo chamado uma vez;
  - `criar_buscador("lexico"/"numpy")` sobre o índice versionado, usado via
    Protocol e validado com `DadosBuscarContexto`, como a ferramenta faria.
- **Contrato:** o `Trecho` devolvido é o modelo de `contratos.py`, e
  `trechos.jsonl` valida como `TrechoCorpus`.
- **Índice versionado:**
  - o `hash_corpus` bate com o corpus atual;
  - o corpus passa no validador;
  - nenhum trecho `produto` tem marcador de taxa.
- **Eval offline:** o `numpy` usa o cache versionado dos embeddings das
  perguntas (`RETRIEVAL_QUERY`, mesmo modelo do índice). O `make test`
  exige 80% ou mais no `numpy`, 75% ou mais no `lexico`, negativas vazias
  nos dois e `RESULTADOS.md` em dia.
- **Marcado `gemini`:** um embedding real e uma busca real
  (`make test-gemini`), que só rodam com `BUSSOLA_TESTE_GEMINI=TRUE` e
  credencial no ambiente.

## Complexity Tracking

Vazio.
