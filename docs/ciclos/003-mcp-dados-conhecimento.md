# Ciclo 003 — F3 MCP server de dados e conhecimento

> **Disparo:** `/spec-master docs/ciclos/003-mcp-dados-conhecimento.md`, no
> Claude Code, dentro da worktree `../bussola-003`, na branch
> `003-mcp-dados-conhecimento`.
>
> **Onda:** 1. **Prioridade:** P0. **Spec:**
> `specs/003-mcp-dados-conhecimento`. **Plano:** [README](./README.md).
>
> **Leitura obrigatória antes do Step 3:**
>
> - [contratos.md](./contratos.md) §0–§5, §7–§9.
> - Contexto mestre [§7, §10 F3, §11–§13](../contexto-spec-master.md).
> - [Blueprint](../blueprint-arquitetura.md) §2–§4.

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Uma única feature:** `id: mcp-dados-conhecimento`,
   `spec_directory: specs/003-mcp-dados-conhecimento`.
2. **Número fixo:** `SPECIFY_FEATURE_DIRECTORY=specs/003-mcp-dados-conhecimento`.
3. **Step 2:** Spec Kit já inicializado. Estratégia Git **Trunk-Based**.
4. **Constituição congelada.** Proposta de mudança vai para
   `specs/003-*/proposta-constituicao.md`, sem aplicar.
5. **Escreva só nos caminhos da §4.** Mudança de contrato só via PR
   `contracts:`.
6. **Desenvolvimento com fakes:** use `BUSSOLA_FAKES=TRUE`, com
   `RepositorioFake` e `BuscadorFake`, até 001 e 002 estarem em `main`. Não
   importe código de branches não mergeadas.
7. **Cloud Run:** publique só revisões com `--tag c003 --no-traffic`.
   Tráfego é do 007.
8. **Ao final:**
   - `make test` e `make lint` verdes;
   - rastreabilidade em `specs/003-*/traceability.md`.

## 2. Propósito

Expor F1 (métricas e simulação) e F2 (RAG) ao agente como **ferramentas
semânticas, read-only**, via MCP streamable HTTP em Cloud Run.

O agente nunca vê SQL, projeto ou credenciais. Cada resposta traz os
números **e** a origem.

## 3. Escopo e comportamento esperado

### 3.1 Servidor (`mcp_server/bussola_mcp/server.py`, substitui o mock do 000)

- FastMCP em streamable HTTP no caminho `/mcp`, escutando em
  `0.0.0.0:$PORT`.
- A fábrica de dependências segue `contratos.md` §4:
  - fakes quando `BUSSOLA_FAKES=TRUE`;
  - senão `RepositorioBigQuery(BQ_MODO_LEITURA)` e
    `criar_buscador(RAG_BACKEND)`, com fallback para o fake com aviso
    enquanto o 002 não estiver em `main`.
- O serviço é privado (Cloud Run IAM). Não há autenticação dentro da
  aplicação.

### 3.2 Ferramentas (`mcp_server/bussola_mcp/ferramentas/`, um módulo por ferramenta)

- **P0:** `perfil_financeiro`, `capacidade_poupanca`, `oportunidades_corte`,
  `dividas_e_parcelas`, `simular_objetivo`, `comparar_cenarios` e
  `buscar_contexto_financeiro`.
- **P1:** `resumo_mes` e `referencia_coorte`.
  - `resumo_mes` é necessário ao 006.
  - `referencia_coorte` fica na linha de corte.
- **Parâmetros, tipos e campos de `dados`:** exatamente como em
  `contratos.md` §5. Descrições em pt-BR, escritas para o LLM escolher bem
  a ferramenta.
- **O que cada ferramenta faz:**
  1. valida a entrada;
  2. chama `metricas.*` ou `simulacao.*`, ou o buscador;
  3. monta o envelope.

  **Nenhuma regra de negócio duplicada** fora de `dominio/`.

### 3.3 Validação e erros (resultado da ferramenta, nunca exceção)

| Situação | Código |
|---|---|
| `id_usuario` não é UUID, `ate_anomes` fora de 202501–202512, `valor_alvo ≤ 0`, `prazo_meses` e `aporte_mensal` juntos ou ausentes, `k`/`top_n` fora da faixa, `pergunta` com mais de 500 caracteres, `anomes > ate_anomes` | `ENTRADA_INVALIDA` |
| UUID válido e inexistente | `USUARIO_INEXISTENTE` |
| `prazo_meses` fora de 1–360, ou prazo calculado acima de 360 meses | `PRAZO_IMPLAUSIVEL` |
| Nenhum mês disponível até `ate_anomes` | `DADOS_INSUFICIENTES` |
| Falha do BigQuery ou do embedding | `INDISPONIVEL` (detalhe só no log, nunca stack ao chamador) |

### 3.4 Envelope e segurança

- **`fonte`:**
  - `ferramenta`;
  - `tabelas` (só `dataset.tabela`);
  - `periodo`: `inicio` = primeiro mês considerado, `fim` =
    `ate_anomes`.
- **`avisos`:** repassa os avisos determinísticos das métricas.
- **RAG sem dado de cliente (Q-17 do 000):** o buscador não recebe
  `id_usuario` nem `ate_anomes`; a ferramenta valida os dois (escopo e
  corte da sessão), repassa `pergunta`, `k` e `tema` e devolve
  `fonte.tabelas = []`. Avisos: `AVISO_CONHECIMENTO` sempre e
  `AVISO_SEM_TRECHOS` quando a lista vem vazia.
- **Logs** conforme `contratos.md` §9: `ferramenta`, `latencia_ms`,
  `erro_codigo` e `ate_anomes`. **Nunca** logar `pergunta` nem textos de
  lançamentos.

## 4. Propriedade (escreve só aqui)

- `mcp_server/bussola_mcp/ferramentas/`
- `mcp_server/bussola_mcp/server.py`
- `mcp_server/tests/ferramentas/`
- Acréscimos em `mcp_server/pyproject.toml` e `Makefile`
- `specs/003-mcp-dados-conhecimento/`

## 5. Contratos

- **Consome:**
  - `contratos.py`, `interfaces.py` e `fakes.py`;
  - `metricas`, `simulacao` e `repositorio_bq` (001, após o merge);
  - `rag.criar_buscador` (002, após o merge);
  - fixtures golden.
- **Provê:** o servidor `bussola-mcp` com as ferramentas de §5, local e em
  Cloud Run. O 004, o 006 e o 007 consomem esse servidor.

## 6. Critérios de aceite

- [ ] Nenhuma ferramenta aceita SQL livre nem devolve SQL, nome de projeto
      ou credencial. Um teste varre todas as saídas procurando `SELECT`,
      `batalha-time-07`, `googleapis` e `Bearer`.
- [ ] Todas as respostas de sucesso trazem `dados` e `fonte` completos,
      conforme §5.
- [ ] Validação de entrada com os códigos da §3.3. Há pelo menos 1 teste por
      código e por ferramenta aplicável.
- [ ] Testes de contrato por ferramenta de `FERRAMENTAS_GOLDEN`: com
      fakes, o envelope bate com os golden `__ate_202506` e `__ate_202512`.
      `buscar_contexto_financeiro` não tem golden (Q-17 do 000) e é testada
      sobre o corpus curado.
- [ ] Teste de schema via `fastmcp.Client`: `list_tools` expõe os
      parâmetros e tipos de §5.
- [ ] Escopo: chamadas com o id do controle nunca retornam linhas ou trechos
      do âncora, e vice-versa.
- [ ] `make mcp` sobe local. A revisão `c003` sobe em Cloud Run
      (`--no-traffic`) e responde a um cliente autenticado.
- [ ] Após o merge do 001: `make test-bq` passa contra `bussola_dados` real,
      nos modos `query` e `memoria`.

## 7. Cenários de teste

- `simular_objetivo(âncora, 202512, valor_alvo=60000, prazo_meses=24)`:
  `modo = "prazo"`, com `aporte_mensal` e `viavel` coerentes com
  `simulacao.aporte_para_prazo`.
- `simular_objetivo` com `prazo_meses` e `aporte_mensal` juntos:
  `ENTRADA_INVALIDA`.
- `comparar_cenarios(âncora, 202506, 60000, 24)`: 3 cenários, e
  `fonte.periodo.fim = 202506`.
- `buscar_contexto_financeiro` com `pergunta` de 501 caracteres:
  `ENTRADA_INVALIDA`.
- `buscar_contexto_financeiro` com `tema="politica"`: `ENTRADA_INVALIDA`.
- `buscar_contexto_financeiro` sem trecho relevante: `trechos = []` e
  `AVISO_SEM_TRECHOS`.
- BigQuery indisponível (mock que lança exceção): `INDISPONIVEL`, e o log
  contém `erro_codigo`.

## 8. Dependências e gate de merge

- **Dependências duras:** 000.
- **Integração:**
  - fakes → real após o merge do 001 (mesmo PR, se já estiver em `main`;
    senão, PR de integração imediato);
  - buscador real após o merge do 002.
- **Gate de merge:** critérios da §6, incluindo `test-bq` contra as tabelas
  do 001. Este é o **3º na ordem de merge**.

## 9. Fora de escopo

- Cálculo de métricas (001) e corpus RAG (002).
- Qualquer ferramenta de escrita.
- Autenticação por usuário final.
- IAM do serviço e tráfego (007).

## 10. Questões em aberto

- **Q6 do mestre:** respondida pela Q-17 do 000 (índice no repositório,
  busca em memória). Para este ciclo é transparente, via
  `BuscadorContexto`.
- Nome e prazo exatos da faixa de renda em `referencia_coorte` (P1) vêm do
  001.

## 11. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| Ferramentas mínimas, read-only, números e origem, validação e testes de contrato | Mestre §10 F3 | EXPLICIT |
| Envelope, códigos de erro e `resumo_mes` | `contratos.md` §5 | EXPLICIT |
| RAG sem dado de cliente; avisos de conhecimento geral | Q-17 do 000 | EXPLICIT |
| Limite de 360 meses para prazo plausível | `contratos.md` §5 | INFERRED |
| Backend vetorial final | Mestre §20, Q6 | UNRESOLVED |
