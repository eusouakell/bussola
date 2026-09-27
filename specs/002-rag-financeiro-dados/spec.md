# Feature Specification: RAG de conhecimento financeiro

**Feature Branch**: `002-rag-financeiro-dados`

**Created**: 2026-09-26

**Status**: Implemented

**Input**: `docs/ciclos/002-rag-financeiro-dados.md`. Formatos canônicos:
`docs/ciclos/contratos.md` §4 (corpus, índice, `BuscadorContexto`), §5
(`buscar_contexto_financeiro`), §7 (`EMBEDDING_MODEL`, `RAG_BACKEND`) e §9
(logs).

## Clarifications

### Session 2026-09-26

Resolvidas sem perguntar ao usuário (regra do orquestrador). A
classificação vem entre parênteses.

- **Título do trecho.**
  - Q: O `titulo` do trecho é o título do documento ou o da seção `##`?
  - A: É o da seção, como nas fixtures do 000 (`cartao-rotativo#2` tem
    título próprio). O título do documento entra só no peso de título da
    busca léxica. (RESOLVABLE_FROM_CONTEXT)
- **Fonte por trecho.**
  - Q: Cada trecho pode ter fonte própria?
  - A: Não. A fonte vem do cabeçalho do documento (contratos §4). Quando um
    documento cita mais de uma norma, `fonte_referencia` lista todas.
    (EXPLICIT)
- **Tema do Registrato.**
  - Q: Em qual tema entra o Registrato?
  - A: Em `norma_bacen`, como pede a tabela do ciclo §3.1. A fixture do 000
    o marca como `credito`, mas ela só alimenta o fake e não precisa bater
    com o índice real. (EXPLICIT)
- **Valor de cliente.**
  - Q: O que conta como "valor de cliente" no validador?
  - A: Padrões de identificação pessoal: UUID, CPF, CNPJ, e-mail e
    sequências longas de dígitos (cartão ou conta). Valores regulatórios,
    como o mínimo existencial, podem aparecer fora do tema `produto`.
    (SAFE_DEFAULT)
- **Pergunta fora do domínio no léxico.**
  - Q: Como ela devolve lista vazia se uma palavra comum ("tempo") casa com
    o corpus?
  - A: O `BuscadorLexico` exige cobertura mínima da pergunta: a soma de IDF
    dos termos encontrados dividida pela soma de IDF de todos os termos
    (termo ausente vale o IDF máximo). A regra tem dois níveis, calibrados
    no eval: `min_coverage=0.2` quando o trecho casa dois ou mais termos e
    `single_term_coverage=0.5` quando casa um só. Com um único nível de 0.3,
    "previsão do tempo" vazava pelo termo "tempo" (cobertura 0.38).
    (INFERRED)
- **Limiar do numpy.**
  - Q: Qual o limiar de "nada relevante" do `numpy`?
  - A: O `BuscadorNumpy` só devolve trechos com cosseno acima de
    `min_score=0.64`. No eval, o menor score do 1º acerto foi 0.6860 e o
    maior score de uma negativa ("previsão do tempo") foi 0.5995; o limiar
    fica perto do ponto médio. Detalhes em `eval/rag/RESULTADOS.md`.
    (INFERRED, ciclo §10)
- **Embeddings (linha de corte, item 1).**
  - Q: Deu para gerar os embeddings, ou o `numpy` fica sem índice?
  - A: Deu. O Plano B (Gemini API com `GOOGLE_API_KEY` passado inline,
    lido do Secret Manager e nunca gravado) gerou `embeddings.npy` com
    `gemini-embedding-001`, dimensão 768, 75 trechos. O item 1 da linha de
    corte não foi usado. O eval do `numpy` roda offline com o cache
    versionado dos embeddings das perguntas
    (`eval/rag/embeddings_perguntas.npz`, `RETRIEVAL_QUERY`). (EXPLICIT)
- **Dimensão do embedding.**
  - Q: Qual dimensão usar?
  - A: `output_dimensionality=768`, que cabe folgado no repositório. A
    dimensão fica no manifesto e é usada também no embedding da pergunta.
    (SAFE_DEFAULT)
- **Nome do resultado do eval.**
  - Q: O resultado do eval vai para `resultado.md` ou `RESULTADOS.md`?
  - A: Para `eval/rag/RESULTADOS.md`, por instrução do orquestrador. O
    `eval/RESULTADOS.md` compartilhado não é tocado. (EXPLICIT)
- **Nomes internos.**
  - Q: Como nomear o que não é fixado por contrato?
  - A: O que o contrato fixa (`criar_buscador`, `BuscadorLexico`,
    `BuscadorNumpy`, `indexar.py`, `validar_corpus.py`, arquivos do índice)
    mantém o nome. Módulos internos novos usam inglês técnico, o que a
    constituição VIII permite com consistência por módulo. Conteúdo e docs
    ficam em pt-BR. (EXPLICIT, decisão do usuário)

## User Scenarios & Testing

### US1: Explicar um conceito com fonte (P0)

O agente pergunta "o que é o CET?" pela ferramenta
`buscar_contexto_financeiro` e recebe trechos do corpus. Cada trecho traz
título, tema e fonte (norma ou página).

**Aceite:**

- A busca devolve até `k` trechos com `score > 0`, do mais relevante ao
  menos relevante, com empate desfeito por `trecho_id`.
- `tema=credito` restringe o resultado ao tema `credito`.
- "previsão do tempo" devolve lista vazia no `lexico`.

### US2: Manter o corpus e o índice (P0)

O time edita `data/rag/corpus/`, roda `validar_corpus.py` e `indexar.py` e
versiona o índice.

**Aceite:**

- Um arquivo sem `fonte_referencia` falha com o nome do arquivo.
- Um UUID no texto falha.
- Duas indexações sem mudança deixam o índice byte a byte igual e chamam o
  modelo uma única vez.
- Um teste falha se o índice versionado estiver desatualizado.

### US3: Trocar o backend sem mudar a ferramenta (P0)

O `server.py` do 003 chama `criar_buscador(RAG_BACKEND)`.

**Aceite:**

- `lexico` e `numpy` implementam `BuscadorContexto`.
- O `numpy` recusa subir com modelo diferente do manifesto.
- Pergunta vazia devolve `[]` sem chamar o embedding.

### US4: Medir a qualidade (P1)

`eval/rag/rodar_eval.py` mede o acerto no top-3.

**Aceite:** 10 ou mais perguntas (2 ou mais de produto), meta de 80%.

## Requirements

- **FR-001:** O corpus fica em `data/rag/corpus/<tema>/<doc_id>.md`, com
  cabeçalho `titulo`, `tema`, `fonte_nome`, `fonte_referencia` e
  `fonte_url` (opcional). Cada seção `##` vira o trecho `<doc_id>#<n>`.
- **FR-002:** Os temas `norma_bacen`, `credito` e `boas_praticas` somam 30
  ou mais trechos com a cobertura do ciclo §3.1. O texto é original, cita a
  norma pelo número e não traz dado de cliente.
- **FR-003:** O tema `produto` tem um documento por `produto_id` do
  catálogo, com `fonte_url` oficial e sem `%`, `a.a.`, `a.m.` ou `R$`.
- **FR-004:** `validar_corpus.py` checa:
  - cabeçalho completo e tema válido (inclusive coerente com a pasta);
  - `doc_id` único e nenhuma seção vazia;
  - ausência de UUID e de dado pessoal;
  - no tema `produto`, `fonte_url` presente e nenhum marcador de taxa.
- **FR-005:** `indexar.py` grava `trechos.jsonl`, `embeddings.npy` e
  `manifesto.json`, com `hash_corpus` e tipo de tarefa
  `RETRIEVAL_DOCUMENT`. É idempotente. `--sem-embeddings` grava só os
  trechos e o manifesto.
- **FR-006:** O índice versionado corresponde ao corpus. Um teste compara
  o `hash_corpus`.
- **FR-007:** `BuscadorLexico` usa BM25 com normalização pt-BR (sem acento,
  sem caixa, stopwords, radical leve), título com peso maior, filtro de
  tema e cobertura mínima. Não usa GCP.
- **FR-008:** `BuscadorNumpy`:
  - embute só a pergunta, com `RETRIEVAL_QUERY` e `EMBEDDING_MODEL`;
  - compara por cosseno, com máscara de tema e `min_score`;
  - recusa subir se o modelo divergir do manifesto;
  - com pergunta vazia, devolve `[]` sem chamar o modelo;
  - uma falha no embedding vira erro genérico, sem detalhe do provedor.
- **FR-009:** O embedding é uma porta (`Embedder`) com adaptador Gemini
  (`google-genai`, Vertex ou Plano B com chave).
- **FR-010:** `bussola_mcp.rag.criar_buscador(backend)` escolhe o backend
  (`lexico` | `numpy`) e rejeita valores desconhecidos.
- **FR-011:** `eval/rag/` tem `perguntas.yaml` (10 ou mais), `rodar_eval.py`
  e `RESULTADOS.md` com o top-3 dos backends e os testes negativos.
- **FR-012:** Testes sem rede em `make test`, com unidade e integração
  (via Protocol, como a ferramenta usaria) e contrato (`Trecho` de
  `contratos.py`). Testes com Gemini real ficam marcados e fora do
  `make test`.

## Success Criteria

- **SC-001:** `validar_corpus.py` passa. Os três temas têm 30 ou mais
  trechos e os 8 produtos estão presentes.
- **SC-002:** A segunda indexação não chama o modelo e não altera nenhum
  byte.
- **SC-003:** O top-3 fica em 80% ou mais no eval.
- **SC-004:** `make lint` e `make test` estão verdes.

## Fora de escopo

Ficam fora deste ciclo:

- alterar `server.py` ou a ferramenta (o 003 pluga o buscador);
- taxas e ofertas;
- dataset no BigQuery, `VECTOR_SEARCH` e RAG Engine;
- recomendação individual;
- prompt injection (a validação é só determinística).
