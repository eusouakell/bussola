# Data Model: Fundação e contratos (Phase 1)

Fonte canônica: [`docs/ciclos/contratos.md`](../../docs/ciclos/contratos.md),
§3–§6. Este arquivo descreve como as entidades viram código e as regras de
validação. Os tipos seguem o mapeamento DDL → Pydantic:

| BigQuery | Python |
|---|---|
| `STRING` | `str` |
| `INT64` | `int` |
| `FLOAT64` | `float` |
| `BOOL` | `bool` |
| `JSON` | `dict` |
| `TIMESTAMP` | `datetime` (UTC) |
| `ARRAY<FLOAT64>` | `list[float]` |

Uma coluna marcada `NULL` em §3 vira `X | None` no modelo. As demais têm
`NOT NULL` no DDL e são obrigatórias no modelo.

## Linhas de `bussola_dados` (`mcp_server/bussola_mcp/contratos.py`)

| Modelo | Tabela | Campos |
|---|---|---|
| `PerfilMes` | `perfil_mensal` | `id_usuario, anomes, renda, gasto, sobra, saldo_inicial, saldo_final, saldo_minimo, saldo_maximo, juros` |
| `GastoCategoria` | `gastos_categoria` | `id_usuario, anomes, macro, micro, total, qtd` |
| `EntradaCategoria` | `entradas_categoria` | `id_usuario, anomes, macro, micro, total, qtd` |
| `Recorrente` | `recorrentes` | `id_usuario, anomes, descr_norm, macro, micro, valor` |
| `Parcela` | `parcelas` | `id_usuario, anomes, descr, macro, parcela_atual, parcela_total, vlr` |
| `Categoria` | `categorias` | `macro, micro, discricionaria, corte_max_pct` |
| `RefCoorte` | `referencia_coorte` | `faixa_renda, macro, media, mediana, qtd_usuarios` |

`faixa_renda` ∈ `ate_3k`, `3k_6k`, `6k_10k`, `10k_20k`, `acima_20k` (`FaixaRenda`).

## Corpus de conhecimento (sem tabela; Q-17)

| Modelo | Onde | Campos |
|---|---|---|
| `TrechoCorpus` | `contracts/fixtures/rag/trechos_exemplo.json`; `bussola_mcp/rag/indice/trechos.jsonl` (002) | `doc_id, trecho_id, titulo, tema, texto, fonte: FonteTrecho{nome, referencia, url: str\|None}` |

`tema` ∈ `norma_bacen`, `credito`, `boas_praticas` (`TemaConhecimento`).
`trecho_id` = `<doc_id>#<n>`. Sem dado de cliente.

## Linhas de `bussola_app` (`agent/bussola_agent/persistencia.py`)

| Modelo | Tabela | Campos | Padrões |
|---|---|---|---|
| `Plano` | `planos` | `plano_id, session_id, id_usuario, objetivo, valor_alvo, prazo_meses, cenario, aporte_mensal, ate_anomes, criado_em` | `plano_id` = uuid4; `criado_em` = agora UTC |
| `Consentimento` | `consentimentos` | `consent_id, session_id, plano_id: str\|None, acao, decisao, texto_apresentado, ts` | `consent_id` = uuid4; `decisao: Literal["aceito","recusado"]` |
| `EventoAuditoria` | `auditoria` | `evento_id, session_id, estado, tipo_evento, ferramenta: str\|None, resumo: dict, ts` | `evento_id` = uuid4; `tipo_evento: TipoEvento` (12 valores de §6) |
| `Acompanhamento` | `acompanhamento` | `plano_id, anomes, planejado, realizado, desvio, categoria_desvio: str\|None, acao_sugerida: str\|None, ts` | — |

## Entradas das ferramentas (validação)

Base `EntradaComum` (`extra="forbid"`):

| Campo | Regra | Erro |
|---|---|---|
| `id_usuario` | regex UUID v4 `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$` sem diferenciar maiúsculas; normalizado para minúsculas | `ENTRADA_INVALIDA` |
| `ate_anomes` | inteiro de 202501 a 202512 | `ENTRADA_INVALIDA` |

| Modelo | Campos adicionais e regras |
|---|---|
| `EntradaPerfilFinanceiro`, `EntradaCapacidadePoupanca`, `EntradaDividasParcelas` | — |
| `EntradaOportunidadesCorte` | `top_n: int = 5`, entre 1 e 10 |
| `EntradaSimularObjetivo` | `valor_alvo > 0`; **exatamente um** entre `prazo_meses` (1–360) e `aporte_mensal > 0`; `usar_saldo_atual: bool = False` |
| `EntradaCompararCenarios` | `valor_alvo > 0`; `prazo_meses` entre 1 e 360 |
| `EntradaBuscarContexto` | `pergunta` com 1 a 500 caracteres (depois de `strip`); `k: int = 5`, entre 1 e 10; `tema: TemaConhecimento \| None = None` |
| `EntradaResumoMes` | `anomes` entre 202501 e 202512 e `anomes ≤ ate_anomes` |
| `EntradaReferenciaCoorte` | `categoria` (macro) com 1 a 100 caracteres |

Ordem de validação no mock:

1. Formato e faixas (`ENTRADA_INVALIDA`).
2. Usuário em `usuarios.json` (`USUARIO_INEXISTENTE`).
3. Dados disponíveis (`DADOS_INSUFICIENTES`).

## Envelopes

```text
Resposta[D]    = { dados: D, fonte: Fonte, avisos: list[str] = [] }
Fonte          = { ferramenta: str, tabelas: list[str], periodo: Periodo }
Periodo        = { inicio: int, fim: int }
RespostaErro   = { erro: Erro }
Erro           = { codigo: CodigoErro, mensagem: str }
CodigoErro     = USUARIO_INEXISTENTE | ENTRADA_INVALIDA | PRAZO_IMPLAUSIVEL
               | DADOS_INSUFICIENTES | INDISPONIVEL
```

## `dados` de cada ferramenta

| Modelo | Campos |
|---|---|
| `DadosPerfilFinanceiro` | `renda_media, gasto_medio, sobra_media, sobra_mediana, fontes_renda: list[FonteRenda{macro, micro, media}], saldo: Saldo{minimo, maximo, atual}, serie_mensal: list[PontoMensal{anomes, renda, gasto, sobra}], meses_considerados` |
| `DadosCapacidadePoupanca` | `sobra_media, sobra_mediana, desvio_padrao, meses_negativos, meses_considerados` |
| `DadosOportunidadesCorte` | `categorias: list[Oportunidade{macro, micro, media_mensal, discricionaria, economia_potencial_mensal, criterio}]` |
| `DadosDividasParcelas` | `parcelas_ativas: list[ParcelaAtiva{descr, parcela_atual, parcela_total, valor, meses_restantes}], juros_pagos_media, comprometimento_renda_pct` |
| `DadosSimularObjetivo` | `modo: Literal["prazo","aporte"], valor_alvo, aporte_mensal, prazo_meses, viavel, folga_mensal, premissas: dict` |
| `DadosCompararCenarios` | `cenarios: list[Cenario{nome, pct_capacidade, aporte_mensal, prazo_meses, viavel, cortes_sugeridos: list[CorteSugerido{macro, micro, valor_mensal}], trade_offs: list[str]}], regras: RegrasCenario` |
| `DadosBuscarContexto` | `trechos: list[Trecho]`, com `Trecho` = `TrechoCorpus` + `score: float` (> 0). Avisos fixos `AVISO_CONHECIMENTO` e `AVISO_SEM_TRECHOS`; `fonte.tabelas = []` |
| `DadosResumoMes` | `anomes, renda, gasto, sobra, gastos_macro: list[GastoMacro{macro, total}]` |
| `DadosReferenciaCoorte` | `faixa_renda, macro, media, mediana, qtd_usuarios` |

`RegrasCenario`:

- `pct_capacidade: dict[str, float]`, padrão `{conservador: 0.40,
  equilibrado: 0.60, acelerado: 0.80}`;
- `base: str = "sobra_mediana"`;
- `rendimento_mensal: float = 0.0`;
- `saldo_inicial: float = 0.0`;
- `cortes_no_acelerado: bool = True`.

## `session.state` (`agent/bussola_agent/estado.py`)

As chaves são constantes `CHAVE_*`, com os valores de §6.

- `EstadoJornada` (enum str): `OBJETIVO`, `ENTENDER`, `ANTECIPAR`,
  `ORIENTAR`, `AGIR`, `ACOMPANHAR`.
- `estado_inicial(id_usuario, ate_anomes)` devolve o estado inicial:
  - `estado_jornada = OBJETIVO`;
  - listas vazias;
  - `None` nos opcionais.
- Helpers:
  - `obter_id_usuario(state)`, `obter_ate_anomes(state)`;
  - `obter_estado_jornada(state)`, `definir_estado_jornada(state, e)`;
  - `adicionar_fonte(state, fonte)`.

## Transições de estado

Não há transições no 000. O enum e os helpers existem. A máquina de estados é
do 004, e as transições para AGIR e ACOMPANHAR são do 005 e do 006.
