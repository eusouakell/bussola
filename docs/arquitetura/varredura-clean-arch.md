# Varredura de Clean Architecture e DDD — Bússola

Gerada em 2026-09-27 pelo `ai-clean-arch-hero-skill`, com um agente de
varredura por subprojeto e uma checagem mecânica de direção de dependência.
Somente leitura: nenhum arquivo foi alterado durante a varredura.

> **Contexto que enquadra tudo abaixo:** a Bússola é uma PoC de hackathon, com
> dados sintéticos e prazo curto, construída por quatro ciclos em paralelo sob
> um contrato explícito (`docs/ciclos/contratos.md`). Boa parte do que um
> checklist genérico marcaria como violação aqui é **decisão de contrato**, e
> está assinalada como tal. O relatório separa atalho de decisão.

## Veredito em uma linha

A arquitetura é melhor do que o normal para o prazo: a inversão de dependência
do `mcp_server/` é real e testada, o BFF tem Clean Architecture **executável**
(com teste que falha o CI), e há núcleos de domínio genuinamente puros. Os
problemas reais são poucos e localizados — e três deles já custaram dinheiro.

## 1. Checagem mecânica de direção de dependência

Regras derivadas do contrato do protocolo, aplicadas sobre os imports reais.

| Regra | Violações | Severidade |
|---|---|---|
| domínio do MCP importa a camada de ferramentas | **0** | — |
| domínio do MCP importa o framework MCP/FastMCP | **0** | — |
| domínio do MCP importa cliente de BigQuery | 2 | ALTA |
| regra de negócio do agente importa o SDK do ADK/Gemini | 12 | MÉDIA |
| regra de negócio do agente importa BigQuery | **0** | — |
| domínio do BFF importa camada externa ou runtime | **0** | — |
| application do BFF importa infraestrutura concreta | **0** | — |
| estado da sessão (front) importa componentes de UI | 1 | MÉDIA |
| componente de UI importa transporte direto | 1 | MÉDIA |
| motor simulado importa componentes de UI | **0** | — |

As duas do MCP são `dominio/repositorio_bq.py:205` e `:249` — um **adapter de
infraestrutura morando dentro da pasta `dominio/`**, não uma inversão de
dependência. O nome da pasta mente; a direção está certa.

## 2. Os achados que importam

Ordenados por custo real, não por pureza.

### A1 — Decisão de consentimento por `sys.modules` · ALTA · `agent/`

`agent/bussola_agent/acompanhamento/tools.py:476`

```python
if GOVERNANCE_PACKAGE not in sys.modules and not _consent_accepted(state):
```

A guarda local de consentimento de `ajustar_plano` (ação **sensível**,
contratos §6) só roda se o pacote `governanca` **não** estiver em
`sys.modules`. O proxy está errado: "módulo importado" não é "gate
registrado". Qualquer caminho que importe `governanca` sem registrar o
callback desliga a guarda **e** não tem o gate — e a ação executa sem
consentimento, contra o princípio VI da constituição.

Que isso já é sutil demais está provado no próprio repo: `fakes.py:486`
manipula `sys.modules` para contornar.

### A2 — 300 linhas de produção desligadas, mas load-bearing nos testes · ALTA · `mcp_server/`

`mcp_server/bussola_mcp/ferramentas/golden_adapter.py`

A própria docstring diz "No longer wired". Confirmado: `build_computations`
devolve sempre `DomainComputations`. Mas **8 arquivos de teste** dependem dele.

**Custo já pago:** a correção do BUG-05 (ciclo 010) foi aplicada nesse adapter
— ou seja, num caminho que produção não executa, porque os testes o
exercitam. Toda regra vale duas vezes, e a suíte valida caminho morto.

### A3 — Arnês de teste de 597 linhas dentro do pacote de produção · ALTA · `agent/`

`agent/bussola_agent/acompanhamento/fakes.py`

Importa o bootstrap (`:491`, `:555` → `bussola_agent.agent`) e o `InMemoryRunner`
do ADK. Três consequências concretas: embarca na imagem do Cloud Run; importar
`fakes` **constrói o `root_agent` como efeito colateral**; e é a razão de ser
do atalho de A1.

### A4 — Modo ao vivo consome copy do agente simulado · ALTA · `web/`

`web/src/sessao/sugestoes.ts:3,22`, `componentes/conversa/BoasVindas.tsx:2`,
`componentes/layout/BarraDemo.tsx:8`, `vistas/P{1,2,3,5}*.tsx`

Os chips do composer, a tela de boas-vindas e os CTAs das vistas importam
textos de `simulado/` **sem condicional de modo**. A demo ao vivo exibe
sugestões que o agente real não propôs, e `simulado/` deixa de ser removível.

### A5 — Guardrails que falham em silêncio · ALTA · `agent/`

`jornada/number_check.py:250-281`, `jornada/action_claims.py:131-145`

~40 `getattr` com default `None`/`False` para ler objetos do ADK. Se a forma
do `LlmResponse` mudar numa atualização do `google-adk`, a verificação de
números (princípio constitucional I) e a detecção de ação sem ferramenta viram
no-op — **sem erro, sem log e com os testes verdes**. É falha-aberta num
controle de Responsible AI.

### A6 — Fronteira de consentimento definida pelo módulo de transporte · MÉDIA · `agent/`

`governanca/catalogo.py:22,25` deriva `FREE_TOOLS` de
`mcp_conexao.FERRAMENTAS_MCP`, com `is_sensitive = not is_free`. Acrescentar
um nome àquela tupla — o gesto natural ao expor uma ferramenta nova, e que
**já aconteceu no 009** — concede execução sem consentimento em silêncio.
Hoje é seguro porque o contrato garante que toda MCP é leitura; a garantia
está num documento, não no código.

### A7 — Registry ferramenta→card espalhado em 3 arquivos · ALTA · `web/`

`sessao/catalogo.ts:12-37`, `sessao/reducer.ts:27,131-137`,
`componentes/conversa/Conversa.tsx:92-123`

Adicionar um card exige 3 edições coordenadas, e um typo faz o card
**desaparecer sem erro de tipo e sem erro em runtime** (`card?: string`). Já há
dois nomes que só existem no reducer e não no catálogo.

### A8 — `dados` do envelope sem tipo no front · ALTA · `web/`

`web/src/agente/tipos.ts:36` — `type Dados = Record<string, unknown>`.
O genérico `Envelope<D>` existe e nunca é usado. Resultado medido: **202**
acessos por string e **20** casts `as number`. Do lado Python o mesmo dado é
Pydantic fechado. É a maior superfície de drift silencioso entre as pontas.

### A9 — Duplicação do kernel aritmético · MÉDIA · `mcp_server/`

`dominio/marcos.py:73-112` reimplementa `meses_para`, `aporte_para`, `_media`,
`_mediana`, `_texto_brl` e `_texto_meses`, que já existem em
`dominio/simulacao.py`. A docstring data a dívida (tarefa T032) sob a premissa
"enquanto o 001 não estiver em `main`" — **o 001 já está**. `normalize_label`
tem 3 cópias idênticas. Formatação monetária duplicada vai para o texto ao
cliente e drift silencioso vira inconsistência na tela.

### A10 — O front não tem gate de arquitetura · MÉDIA · `web/`

O BFF só se mantém limpo porque `bff/architecture.test.ts` é uma régua
executável que falha o CI. O front tem as mesmas boas intenções e **nenhuma
rede** — e é exatamente por isso que A4 e A7 degradaram.

## 3. O que está bem feito

Registrado com a mesma seriedade, porque é ativo do projeto e não deve ser
quebrado por refactor.

1. **A inversão de dependência do `mcp_server/` é real, não decorativa.**
   `dominio/` nunca importa `ferramentas/`. O `RepositorioBigQuery` é
   referenciado por **string** no bootstrap e carregado por `importlib`.
   `tests/ferramentas/test_escopo_ferramentas.py` prova a inversão injetando
   espiões na porta.
2. **`ToolRunner` centraliza todo o cross-cutting uma vez** — validação,
   códigos de erro, envelope e log. Resultado: as 10 ferramentas têm 25–30
   linhas de mapeamento de protocolo puro.
3. **Taxonomia de exceções correta:** `DomainError` (resultado de negócio) ×
   `BackendUnavailable` (infra falhou), tratadas de formas diferentes, com o
   log guardando só a classe da causa — nunca o detalhe.
4. **Fake e produção compartilham o mesmo caminho de cálculo.** Modo fake não
   é implementação paralela: é o mesmo código sobre outro adapter.
5. **O BFF tem Clean Architecture executável.** `bff/architecture.test.ts`
   varre imports reais (inclusive `import type`, reexport e import dinâmico) e
   falha o CI. `domain` e `application` são **puros**: nenhum import
   não-relativo. Portas com duas implementações reais cada.
6. **Zero dependência de runtime no BFF:** HTTP nativo, BigQuery por REST sem
   SQL, credenciais por metadata server. Três dependências no `package.json`,
   todas do front.
7. **Zero aritmética sobre dados na apresentação do front.** Verificado por
   varredura: nenhum card, conversa ou vista calcula. O princípio I está
   honrado de verdade.
8. **Núcleos de domínio puros que servem de modelo:** `acompanhamento/`
   (`money`, `periods`, `desvio`, `progress`, `plan_context`),
   `jornada/state_machine.py`, `dominio/simulacao.py`, `dominio/marcos.py`.
9. **`rag/` é um bounded context selado:** entrada única, porta implementada
   estruturalmente, `numpy` e `google.genai` confinados em 2 de 8 módulos.
10. **Privacidade aplicada em quatro lugares independentes:** `hide_input_in_errors`,
    log sem eco de valores, `toPublicPersona` sem `idUsuario` (com teste), e
    `varrer-bundle.ts` falhando o build com UUID/SQL/chave no `dist/`.
11. **Docstrings com procedência de decisão** (citam FR, Q-, D- das specs). Foi
    o que permitiu esta varredura distinguir atalho de decisão.
12. **Nenhum diretório vazio ou cerimonial** em nenhum dos três subprojetos.

## 4. Decisões de contrato — não são violações

Registradas para quem ler o diagnóstico não "corrigir" o que foi escolhido:

- **Ordem numérica global de callbacks e instruções** (contratos §6): é o preço
  de deixar quatro worktrees comporem sem conflito de merge. Pagou-se. O custo
  é que reordenar exige ler os quatro pacotes.
- **`session.state` como `dict[str, Any]`**: imposto pelo ADK, não é preguiça
  de modelagem. O custo é a revalidação defensiva em `acompanhamento/tools.py`.
- **Pydantic no domínio do MCP**: usado como definição declarativa de
  VO/record, e a constituição IX **exige** o mecanismo (teste DDL ↔ modelos).
  A linha que não deve ser cruzada é `model_dump(mode="json")` dentro de
  `dominio/` — e ela está cruzada em exatamente um lugar
  (`dominio/metricas.py:207`).
- **`contratos.py` com 836 linhas e 6 responsabilidades**: é Shared Kernel
  protegido por processo (PR `contracts:` revisado por ciclo consumidor).
  Quebrar agora é o **pior** investimento do relatório: esforço G, benefício
  comportamental zero. Fica como dívida conhecida.
- **`consent.py` com `_used_ids` de processo**: só é correto com
  `max-instances=1`, e o código diz isso. Dívida consciente, não smell.

## 5. Nota sobre a ferramenta

O comando `validate-architecture` do `ai-clean-arch-hero-engine` não roda nesta
máquina: `lib/architecture_policy.py:10` calcula `SKILL_ROOT = ENGINE_ROOT.parent`
(resolvendo para `$HOME`) e a instalação em `~/.ai-clean-arch-hero-engine/` não
tem o diretório `config/`. O erro é
`FileNotFoundError: /home/mrlopito/config/architecture-policy.json`.

A checagem da §1 foi feita aplicando as regras do `PROTOCOL.md` diretamente
sobre os imports do repositório.

## 6. Refactors recomendados, por retorno

| # | O quê | Onde | Esforço | Risco |
|---|---|---|---|---|
| R1 | Guarda de consentimento explícita, sem `sys.modules` | `agent/.../acompanhamento/tools.py:476` | P | BAIXO |
| R2 | Mover `fakes.py` para fora do pacote de produção | `agent/.../acompanhamento/fakes.py` | P/M | BAIXO |
| R3 | Cortar a dependência de `simulado/` na aplicação e na apresentação | `web/src/{sessao,componentes,vistas}` | M | BAIXO |
| R4 | Gate de arquitetura para o front, nos moldes do BFF | `web/src/architecture.test.ts` (novo) | P | MUITO BAIXO |
| R5 | Port de `auth` e fechar o port `Transporte` | `web/src/auth/`, `web/src/agente/transporte.ts` | P | MUITO BAIXO |
| R6 | Mover `RepositoryUnavailableError` para `ports.py`; tool de busca para de importar `rag.embedding` | `mcp_server/.../ferramentas/` | P | BAIXO |
| R7 | Apagar `golden_adapter.py` e repontar os testes para `DomainComputations` | `mcp_server/` | M | MÉDIO |
| R8 | `marcos.py` delega o kernel aritmético a `simulacao.py`; unificar `normalize_label` | `mcp_server/.../dominio/` | P/M | MÉDIO |
| R9 | Registry único e tipado para ferramenta→card | `web/src/sessao/`, `componentes/conversa/` | M | MÉDIO |
| R10 | Tipar os `dados` do envelope por ferramenta | `web/src/agente/tipos.ts` | G (fatiável) | BAIXO |
| R11 | ACL nomeado para os objetos do ADK, no lugar dos ~40 `getattr` | `agent/.../jornada/` | M | MÉDIO |
| R12 | Extrair os casos de uso de `governanca/acoes.py` do `ToolContext` | `agent/.../governanca/` | G | MÉDIO |

**Não mexer:** `web/bff/` (a arquitetura se sustenta; o único achado é BAIXA e
conceitual), `reducer.ts`/`auditoria.ts` como pureza, `formatar.ts`,
`varrer-bundle.ts`, `fixtures.test.ts`, e a quebra de `contratos.py`.
