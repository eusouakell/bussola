# Ciclo 002 — F2 RAG de conhecimento (normas do BACEN, crédito e boas práticas)

> **Disparo:** `/spec-master docs/ciclos/002-rag-financeiro-dados.md`, no
> Claude Code, dentro da worktree `../bussola-002`, na branch
> `002-rag-financeiro-dados`.
>
> **Onda:** 2 (pode começar junto com a Onda 1). **Prioridade:** P0 (itens
> 1–3), P1 (item 4). **Spec:** `specs/002-rag-financeiro-dados`.
> **Plano:** [README](./README.md).
>
> **Leitura obrigatória antes do Step 3:**
>
> - [contratos.md](./contratos.md) §4 (`BuscadorContexto` e corpus de
>   conhecimento), §5 (`buscar_contexto_financeiro`), §7 e §8.
> - Q-17 em `specs/000-fundacao-contratos/questoes.md` (por que o RAG saiu
>   do BigQuery).
> - Contexto mestre [§8, §9, §10 F2, §17](../contexto-spec-master.md).
> - [Catálogo de produtos](../catalogo/README.md) §1 e §2.

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Uma única feature:** `id: rag-financeiro-dados`,
   `spec_directory: specs/002-rag-financeiro-dados`.
2. **Número fixo:** `SPECIFY_FEATURE_DIRECTORY=specs/002-rag-financeiro-dados`.
3. **Step 2:** Spec Kit já inicializado. Estratégia Git **Trunk-Based**.
4. **Constituição congelada.** Proposta vai para
   `specs/002-*/proposta-constituicao.md`.
5. **Escreva só nos caminhos da §4.** O RAG não tem dataset no BigQuery
   (Q-17 do 000): corpus e índice ficam no repositório.
6. **Sem dado de cliente no corpus.** O RAG é conhecimento geral. Dados do
   cliente (saldo, dívidas, gastos) vêm só das ferramentas determinísticas
   do 003, que já consultam `bussola_dados`.
7. **Texto original.** O corpus é escrito pelo time em pt-BR, cita a norma
   pelo número e não copia texto legal ou de terceiros. Nenhum LLM escreve
   o corpus; o LLM só aparece no embedding.
8. **Ao final:**
   - `make test` e `make lint` verdes;
   - rastreabilidade em `specs/002-*/traceability.md`.

## 2. Propósito

Dar ao agente **conhecimento de apoio** para explicar o que as ferramentas
mostram: o que é o CET, como funciona o rotativo do cartão, o que diz a
norma sobre portabilidade, como montar uma reserva de emergência. O RAG
explica conceitos e regras; os números do cliente continuam vindo das
ferramentas determinísticas.

## 3. Escopo e comportamento esperado

### 3.1 Corpus (`data/rag/corpus/<tema>/<doc_id>.md`)

- Um documento por arquivo, no formato de contratos §4: cabeçalho com
  `titulo`, `tema`, `fonte_nome`, `fonte_referencia` e `fonte_url`
  (opcional); cada seção `##` vira um trecho `"<doc_id>#<n>"`.
- **Ponto de partida:** os 13 trechos curados de
  `contracts/fixtures/rag/trechos_exemplo.json` (000).
- **Cobertura mínima (P0, exceto `produto`, que é P1):**

| Tema | Conteúdo |
|---|---|
| `norma_bacen` | Rotativo e parcelamento do cartão, teto de juros do rotativo, CET, portabilidade de crédito, Registrato, cheque especial, direitos do consumidor bancário |
| `credito` | Modalidades (pessoal, consignado, cartão, cheque especial, financiamento), como comparar custo, renegociação, superendividamento |
| `boas_praticas` | Reserva de emergência, orçamento mensal, ordem de quitação de dívidas, uso consciente do cartão, metas |
| `produto` | Os 8 produtos do recorte do MVP (`contracts/catalogo_produtos.json`, vindo de [`docs/catalogo/`](../catalogo/README.md) §2), um documento por `produto_id`: nome, categoria, uso, cuidado de elegibilidade e `fonte_url` oficial (obrigatória). Sem taxa, rentabilidade, parcela, prazo ou condição comercial |

- Cada documento tem pelo menos uma `fonte_referencia` verificável (número
  da norma, página institucional). Datas de vigência aparecem no texto
  quando a regra mudou.
- **Validação (`data/rag/validar_corpus.py`):** cabeçalho completo, tema
  válido, `doc_id` único, nenhuma seção vazia, nenhum UUID ou valor de
  cliente no texto. No tema `produto`, exige `fonte_url` e rejeita `%`,
  `a.a.`, `a.m.` e `R$`.

### 3.2 Índice (`data/rag/indexar.py`)

- Lê o corpus, gera os trechos e grava em
  `mcp_server/bussola_mcp/rag/indice/` os três arquivos de contratos §4
  (`trechos.jsonl`, `embeddings.npy`, `manifesto.json`).
- Embeddings com `EMBEDDING_MODEL` via `google-genai`, tipo de tarefa
  `RETRIEVAL_DOCUMENT`. O caminho padrão é Vertex;
  `GOOGLE_GENAI_USE_VERTEXAI=FALSE` + chave é o Plano B.
- **Idempotente:** `hash_corpus` no manifesto. Se o corpus não mudou, não
  chama o modelo e não reescreve o índice.
- `--sem-embeddings` grava só `trechos.jsonl` e o manifesto (basta para o
  backend `lexico`, sem GCP).
- O índice é versionado. Um teste falha se `hash_corpus` não bate com o
  corpus atual (índice desatualizado).

### 3.3 Buscadores (`mcp_server/bussola_mcp/rag/`)

- **`criar_buscador(backend)`:** retorna `BuscadorLexico` (`lexico`) ou
  `BuscadorNumpy` (`numpy`). Ambos implementam `BuscadorContexto` e carregam
  o índice em memória uma vez.
- **`BuscadorLexico`** (padrão, sem GCP): mesma regra do `BuscadorFake`
  (sobreposição de termos sem acento e sem caixa), com stopwords pt-BR e
  título com peso maior.
- **`BuscadorNumpy`:**
  - gera o embedding da pergunta com `RETRIEVAL_QUERY`;
  - calcula a similaridade de cosseno contra `embeddings.npy`;
  - aplica o filtro de `tema` por máscara e devolve o top-k com
    `score > 0`.
- Pergunta vazia devolve `[]` sem chamar o modelo. Falha no embedding vira
  `INDISPONIVEL` na ferramenta (003), sem vazar detalhe do provedor.
- O modelo de embedding da pergunta tem de ser o mesmo do manifesto. Se
  divergir, o buscador recusa subir.

### 3.4 Avaliação (`eval/rag/`) (P1)

- **`perguntas.yaml`:** 10 ou mais perguntas, cada uma com os `trecho_id`
  esperados. Exemplos:
  - "o que é o CET?";
  - "posso levar meu empréstimo para outro banco?";
  - "quanto guardar de reserva de emergência?".
- **`rodar_eval.py`:** calcula o acerto no top-3 dos dois backends e grava
  `eval/rag/resultado.md`.
- **Testes negativos:**
  - perguntas fora do domínio ("previsão do tempo") devolvem lista vazia
    no `lexico` e score abaixo do limiar no `numpy`;
  - nenhum trecho `produto` contém `%`, `a.a.`, `a.m.` ou `R$`.
- **Perguntas de produto:** 2 ou mais no `perguntas.yaml`, ex.: "onde guardo
  o dinheiro da entrada?" espera `cofrinhos`.

## 4. Propriedade (escreve só aqui)

- `data/rag/`
- `mcp_server/bussola_mcp/rag/` (inclui `indice/`)
- `mcp_server/tests/rag/`
- `eval/rag/`
- Acréscimos em `mcp_server/pyproject.toml` e `Makefile` (ex.:
  `make indice`)
- `specs/002-rag-financeiro-dados/`

## 5. Contratos

- **Consome:**
  - `interfaces.BuscadorContexto` e os modelos `Trecho`, `TrechoCorpus` e
    `TemaConhecimento`;
  - `contracts/catalogo_produtos.json` (000), fonte do tema `produto`;
  - env `EMBEDDING_MODEL` e `RAG_BACKEND`.
- **Provê:**
  - corpus em `data/rag/corpus/` e índice em `bussola_mcp/rag/indice/`;
  - `bussola_mcp.rag.criar_buscador`, plugado pela fábrica do `server.py`
    do 003 sem mudar a ferramenta.

## 6. Critérios de aceite

- [ ] O corpus cobre os três temas, com pelo menos 30 trechos, todos com
      `fonte_referencia`, mais o tema `produto` com os 8 produtos (P1).
      `validar_corpus.py` passa.
- [ ] `indexar.py` é idempotente: uma segunda execução sem mudança no
      corpus não chama o modelo nem altera o índice.
- [ ] O índice versionado corresponde ao corpus (`hash_corpus`).
- [ ] Cada trecho devolvido traz `titulo`, `tema` e `fonte`.
- [ ] O filtro por `tema` funciona nos dois backends.
- [ ] 10 ou mais perguntas de avaliação com o trecho esperado no top-3 em
      pelo menos 80% dos casos, no backend `numpy`. Resultado em
      `eval/rag/resultado.md`, com o `lexico` como linha de base.
- [ ] A ferramenta `buscar_contexto_financeiro` do 003 funciona com
      `RAG_BACKEND=lexico` e `RAG_BACKEND=numpy`, sem alteração de código na
      ferramenta.

## 7. Cenários de teste

- Duas execuções de `indexar.py` sobre o mesmo corpus: o índice fica
  byte a byte igual e o modelo é chamado só na primeira.
- Um arquivo do corpus sem `fonte_referencia`: `validar_corpus.py` falha
  com o nome do arquivo.
- Um trecho com um UUID no texto: `validar_corpus.py` falha.
- Busca com `tema=credito`: todos os trechos são do tema `credito`.
- Pergunta vazia ou só com espaços: é rejeitada na ferramenta (003). No
  buscador, devolve lista vazia sem chamar o embedding.
- Manifesto com outro `modelo_embedding`: `BuscadorNumpy` recusa subir.

## 8. Dependências e gate de merge

- **Dependências duras:** 000. Não depende do 001: o corpus não vem da
  base sintética.
- **Runtime:** só o backend `numpy` gera o embedding da pergunta. A SA
  precisa de `aiplatform.user` (pedido ao owner) ou do Plano B com chave.
  O `lexico` não usa GCP.
- **Gate de merge:** corpus nos três temas + eval com pelo menos 80% +
  buscador plugado na ferramenta do 003. Este é o **6º na ordem de merge**.

## 9. Fora de escopo

- Taxas, condições, ofertas e as APIs públicas de dados abertos do
  catálogo ([`docs/catalogo/`](../catalogo/README.md) §3).
- Dado do cliente no corpus (fichas mensais, perfil anual, coorte): o
  agente obtém esses números das ferramentas do 003 (Q-17 do 000).
- `VECTOR_SEARCH`, dataset no BigQuery e RAG Engine do Agent Platform
  (Q6, Q-17).
- Recomendação individual de crédito ou de investimento.

## 10. Questões em aberto

- ~~**Q3 do mestre**~~ **Respondida:** o catálogo entra como tema
  `produto` (P1).
- O limiar de score do `numpy` para "nada relevante" é INFERRED; calibrar
  no eval.
- Revisão jurídica do corpus antes da demo: quem faz? (Pessoa B confirma.)

## 11. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| Corpus de conhecimento (normas do BACEN, crédito, boas práticas), sem BigQuery | Decisão do usuário (Q-17 do 000) | EXPLICIT |
| Crédito como conteúdo geral; dívidas do cliente via ferramentas | Decisão do usuário (Q-17 do 000) | EXPLICIT |
| Corpus no repositório + busca em memória | Decisão do usuário (Q-17 do 000) | EXPLICIT |
| Embeddings em Python, eval top-3 ≥ 80% | Mestre §9, §10 F2 e §17 | EXPLICIT |
| `BuscadorLexico` como padrão sem GCP | Este ciclo | INFERRED |
| Limiar de score do `numpy` | Este ciclo | INFERRED |
| Tema `produto` a partir do catálogo curado | Mestre §20 Q3; `docs/catalogo/` | EXPLICIT |
