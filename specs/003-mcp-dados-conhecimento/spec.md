# Feature Specification: MCP server de dados e conhecimento

**Feature Branch**: `003-mcp-dados-conhecimento`
**Created**: 2026-09-26
**Status**: Implementado (modo fake; integração com 001/002 pendente do merge)
**Input**: `docs/ciclos/003-mcp-dados-conhecimento.md`, `docs/ciclos/contratos.md` §0–§5, §7–§9

## Clarifications

### Session 2026-09-26

Decisões tomadas pelo ciclo, sem perguntas ao usuário (regra de execução),
pela linha de corte:

- **D-01 (9 ferramentas):** o servidor registra as 9 ferramentas de contratos §5,
  incluindo `referencia_coorte` (P1). O mock do 000 servia 8. O contrato
  prevalece. `FERRAMENTAS_MCP` do agente não muda. Dois testes do agente que
  exigiam `== 8` passam a exigir que as 8 do agente estejam no servidor
  (commit separado, fora da propriedade, sinalizado).
- **D-02 (PRAZO_IMPLAUSIVEL):** `prazo_meses` fora de 1–360 devolve
  `PRAZO_IMPLAUSIVEL` (tabela §3.3 do ciclo), quando é o único erro da entrada.
  O mock do 000 devolvia `ENTRADA_INVALIDA` (spec 000, linha 244). Prazo
  calculado acima de 360 meses também vira `PRAZO_IMPLAUSIVEL` (erro de domínio).
- **D-03 (porta de cálculo):** `metricas`, `simulacao` e `repositorio_bq` são do
  001 e ainda não estão em `main`. As ferramentas dependem da porta
  `FinancialComputations` (`ferramentas/ports.py`), que espelha contratos §4.
  Até o merge do 001, o adaptador `GoldenFixtureComputations` serve os golden
  de `contracts/fixtures/ferramentas/`. Não copia lógica de métrica nem de
  simulação.
- **D-04 (corte temporal no adaptador de golden):** corte 202506 ou 202512
  devolve o golden exato. Corte de 202507 a 202511 devolve o golden de 202506,
  com aviso e `fonte.periodo.fim = 202506`, sem dado posterior ao corte. Corte
  anterior a 202506 devolve `INDISPONIVEL` ("Dados de exemplo indisponíveis
  para este corte."). O mock servia o golden de 202506 para qualquer corte
  anterior a 202512, o que expunha meses depois do corte (constituição IV).
- **D-05 (simulação no adaptador de golden):** a entrada canônica
  (`valor_alvo=30000`, `prazo_meses=24`, sem aporte, `usar_saldo_atual=false`)
  recebe o golden exato. Outra entrada recebe o mesmo golden com o aviso
  "Resposta de exemplo calculada para valor_alvo=30000 e prazo_meses=24."
  (mesma regra do mock, contratos §8).
- **D-06 (escopo do controle):** no adaptador de golden, só o cliente âncora de
  `usuarios.json` tem golden; os outros recebem `DADOS_INSUFICIENTES`. A busca e
  a `referencia_coorte` (agregado da faixa de renda, sem dado individual) valem
  para qualquer cliente conhecido.
- **D-07 (testes do mock):** `tests/contrato/test_mock_servidor.py` e
  `test_mock_http.py` testavam o mock que este ciclo substitui. A cobertura
  equivalente passa para `tests/ferramentas/` e os dois arquivos saem (fora da
  propriedade, sinalizado).
- **D-08 (cliente de teste):** o teste de schema usa o cliente do SDK oficial
  (`ClientSession` em memória e por HTTP), como o 000 decidiu (R-03/Q-02). O
  pacote `fastmcp` não é dependência do projeto.
- **D-09 (nomes):** nomes de contrato em pt-BR não mudam. Módulos, classes e
  funções internas novas usam nomes técnicos em inglês (constituição VIII
  permite, com consistência por módulo). Textos ao cliente em pt-BR. Sem
  conflito com a constituição.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agente consulta números do cliente com origem (Priority: P1)

O agente (004) chama ferramentas read-only e recebe números determinísticos
com `fonte` completa, sem SQL, projeto ou credencial.

**Acceptance Scenarios**:

1. **Given** o âncora e corte 202506 ou 202512, **When** o agente chama uma
   ferramenta de `FERRAMENTAS_GOLDEN`, **Then** o envelope bate com o golden.
2. **Given** o id do controle, **When** chama qualquer ferramenta, **Then**
   nunca recebe números ou trechos do âncora.
3. **Given** uma entrada fora do contrato, **When** chama, **Then** recebe o
   código de §3.3 como resultado (não exceção), citando só nomes de campos.

### User Story 2 - Agente busca conhecimento geral (Priority: P1)

`buscar_contexto_financeiro` devolve trechos do corpus, iguais para qualquer
cliente, com os avisos fixos. O buscador não recebe `id_usuario` nem corte.

**Acceptance Scenarios**:

1. **Given** `tema="produto"`, **Then** todos os trechos são do tema e trazem `fonte.url`.
2. **Given** pergunta sem trecho relevante, **Then** `trechos=[]` e `AVISO_SEM_TRECHOS`.
3. **Given** pergunta com 501 caracteres ou `tema="politica"`, **Then** `ENTRADA_INVALIDA`.

### User Story 3 - Replay e canal usam o servidor (Priority: P1)

O 006 chama `resumo_mes`; o 007 publica o mesmo servidor em Cloud Run. `make mcp`
sobe local em `http://localhost:8080/mcp`.

### Edge Cases

- Backend falha (BigQuery, embedding, fixture ausente ou inválida):
  `INDISPONIVEL`, com o detalhe só no log (`excecao` = nome da classe).
- `bussola_mcp.rag` ou `repositorio_bq` ausentes fora do modo fake: o servidor
  cai nos fakes e registra `evento=dependencia_ausente`.
- Nenhum mês até o corte: `DADOS_INSUFICIENTES`.
- `id_usuario` em maiúsculas: aceito (normalizado).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `server.py` serve FastMCP em streamable HTTP em `/mcp`, em `0.0.0.0:$PORT`, com a mesma CLI do mock (`--host`, `--port`, `--fixtures`).
- **FR-002**: Fábrica única de dependências: fakes com `BUSSOLA_FAKES=TRUE` ou `--fixtures`; senão `RepositorioBigQuery(modo=BQ_MODO_LEITURA)` e `criar_buscador(RAG_BACKEND)`, importados sob demanda, com fallback para os fakes e aviso no log enquanto o módulo não existir.
- **FR-003**: As 9 ferramentas de contratos §5, um módulo por ferramenta em `ferramentas/`, com nomes, parâmetros, tipos e padrões exatos, descrições em pt-BR e anotações read-only.
- **FR-004**: Schema sem restrições de faixa (R-05 do 000); faixas validadas na ferramenta pelos `Entrada*`.
- **FR-005**: Códigos de erro de §3.3 como resultado da ferramenta: `ENTRADA_INVALIDA`, `USUARIO_INEXISTENTE`, `PRAZO_IMPLAUSIVEL`, `DADOS_INSUFICIENTES`, `INDISPONIVEL`. Ordem: entrada → usuário → domínio.
- **FR-006**: Envelope `{dados, fonte, avisos}` com `fonte.ferramenta`, `fonte.tabelas = TABELAS_FERRAMENTA` e `fonte.periodo` (primeiro mês considerado → corte); avisos determinísticos do domínio repassados.
- **FR-007**: As ferramentas dependem só das portas (`RepositorioFinanceiro`, `BuscadorContexto`, `FinancialComputations`). Nenhuma regra de negócio fora de `dominio/`.
- **FR-008**: Busca sem dado de cliente: o buscador recebe só `pergunta`, `k` e `tema`; `fonte.tabelas=[]`; `AVISO_CONHECIMENTO` sempre e `AVISO_SEM_TRECHOS` com lista vazia.
- **FR-009**: Uma linha de log `ferramenta_chamada` por chamada, via `logging_json`, com `ferramenta`, `latencia_ms`, `erro_codigo` e `ate_anomes`. Nunca `pergunta`, texto de lançamento, chave ou token.
- **FR-010**: Nenhuma resposta contém SQL, nome de projeto, host de API do Google ou credencial.
- **FR-011**: Após o merge do 001, trocar o adaptador de golden pelo de domínio muda um único arquivo (`ferramentas/computations.py`).
- **FR-012**: Testes `@pytest.mark.bq` contra `bussola_dados` real (modos `query` e `memoria`), fora do `make test`.

### Key Entities

- **FinancialComputations** (porta): um método por ferramenta de dados; devolve `Computation(dados, periodo, avisos)`.
- **ToolDependencies**: repositório, buscador e cálculos injetados no servidor.
- **ToolRunner**: valida, confere o usuário, chama a porta, monta o envelope e registra o log.

## Success Criteria *(mandatory)*

- **SC-001**: `make lint` e `make test` verdes, sem rede e sem GCP.
- **SC-002**: 100% das ferramentas de `FERRAMENTAS_GOLDEN` batem com os golden nos dois cortes.
- **SC-003**: Ao menos 1 teste por código de erro e ferramenta aplicável.
- **SC-004**: A varredura de todas as saídas não encontra `SELECT`, `batalha-time-07`, `googleapis` nem `Bearer`.

## Assumptions

- `RepositorioBigQuery(modo=...)` e `criar_buscador(backend)` terão as assinaturas de contratos §4.
- O adaptador de golden é provisório e sai no PR de integração com o 001.
- `referencia_coorte` usa a `faixa_renda` de `usuarios.json` até o 001 definir a faixa (questão aberta do ciclo).
