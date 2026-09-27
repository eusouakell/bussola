# Implementation Plan: Marcos financeiros intermediários

**Branch**: `009-marcos-financeiros` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-marcos-financeiros/spec.md`

## Summary

Quando o objetivo do cliente não fecha, a Bússola passa a devolver uma
trajetória de marcos intermediários em vez de rejeitar o objetivo. O cálculo
vive numa engine determinística nova no domínio do MCP
(`dominio/marcos.py`), é exposto por uma ferramenta MCP read-only
(`ferramentas/planejar_marcos.py`), apresentado pelo agente por uma extensão
registrada em `extensoes.py` (sem tocar o `agent.py` do 004) e renderizado
por um card novo no front. A mudança de contrato (ferramenta, modelos, chave
de estado, mapa de propriedade) é aditiva e vai num commit `contracts:`
separado, revisado pela Pessoa A.

## Technical Context

**Language/Version**: Python 3.12 (`mcp_server/`, `agent/`), TypeScript 5+
(`web/`), com `uv` e npm.

**Primary Dependencies**: FastMCP, Pydantic v2, Google ADK, React 19 + Vite +
Tailwind v4. **Nenhuma dependência nova.**

**Storage**: nenhum armazenamento novo. Leitura por `RepositorioFinanceiro`
(fake sobre `contracts/fixtures/` neste ciclo; BigQuery quando o 001 chegar).
Marcos vivem só em `session.state`.

**Testing**: `pytest` (`BUSSOLA_FAKES=TRUE`, sem rede), `vitest` no front.

**Target Platform**: Cloud Run (`us-central1`), dois serviços; front estático
servido pelo agente.

**Project Type**: monorepo de dois serviços Python + front web.

**Performance Goals**: a engine é aritmética sobre ≤ 12 meses de linhas; o
custo é desprezível diante da chamada ao BigQuery. Nenhuma meta específica.

**Constraints**: determinismo total (sem `datetime.now()`, sem aleatoriedade);
sem I/O em `dominio/`; envelope e códigos de erro de contratos §5 sem
alteração; textos ao cliente em pt-BR; nenhum número gerado pelo LLM.

**Scale/Scope**: 1 engine (~6 funções puras), 1 ferramenta MCP, 1 extensão de
agente, 1 card de front, 4 suítes de teste. 8 motivos, 6 tipos de marco, 4
níveis de prioridade, 5 códigos de erro.

## Constitution Check

*GATE: verificado antes da Fase 0 e revisto após a Fase 1.*

| Princípio | Como este plano cumpre |
|---|---|
| I. Números vêm de ferramentas determinísticas | Todo valor e prazo sai de `dominio/marcos.py`, função pura testada. O prompt proíbe o modelo de calcular e manda citar a fonte. |
| II. Agente isolado de SQL e infraestrutura | A extensão do agente chama a ferramenta MCP por `mcp_conexao.chamar_ferramenta`; nenhum SQL, nome de projeto ou credencial atravessa. Erro previsto é envelope. |
| III. Read-only com escopo por cliente | Ferramenta só lê. `id_usuario` e `ate_anomes` validados por `EntradaComum` e sobrescritos pelo callback de escopo do 004 (`aplicar_escopo` no caminho direto). Nenhuma escrita. |
| IV. Respostas rotuladas e explicáveis | Os 5 blocos da fonte entram **dentro** de Diagnóstico / Simulação / Recomendação (mapa em [questoes.md](./questoes.md) Q-009-6). `por_que`, `relacao_com_objetivo` e ressalvas são frases determinísticas da engine, como os `trade_offs`. |
| V. Dados sintéticos e logs seguros | Só fixtures sintéticas. Log com `ferramenta`, `latencia_ms`, `erro_codigo`, `ate_anomes`; nada de texto de lançamento. |
| VI. Consentimento explícito e auditado | Nada sensível: ferramenta de leitura, sem ação externa. Não altera o gate do 005. |
| VII. Segredos fora do repositório | Nenhum segredo, nenhuma variável de ambiente nova. |
| VIII. pt-BR e Responsible AI | Todo texto ao cliente em pt-BR; as 9 proibições da fonte entram como teste léxico (FR-011) e como instrução de prompt. |
| IX. Testes obrigatórios e gates sem rede | Unitários da engine, contrato da ferramenta, teste sem LLM no agente, componente no front. `make lint`/`make test` com fakes. |
| X. Contratos e paralelismo | Mudança aditiva, commit `contracts:`, revisão da Pessoa A. Arquivos **novos** em `dominio/` e `ferramentas/`; nenhum arquivo de outro ciclo é editado, exceto os acréscimos de contrato listados em §"Mudança de contrato". Nada depende de código não mergeado. |

**Constituição congelada:** este plano **não** propõe emenda. Se o `analyze`
apontar necessidade, ela vai para `specs/009-marcos-financeiros/proposta-constituicao.md`.

**Desvio deliberado registrado:** `RegrasMarco.usar_saldo_atual = True`
diverge da premissa `saldo_inicial = 0.0` de `RegrasCenario` (contratos §4).
Decisão da Pessoa B no `clarify` (Q-009-3), com piso em zero, aviso na
resposta e registro em [questoes.md](./questoes.md). Ver Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/009-marcos-financeiros/
├── plan.md              # este arquivo
├── spec.md              # especificação
├── questoes.md          # decisões Q-009-1..6 (clarify)
├── research.md          # Fase 0
├── data-model.md        # Fase 1
├── quickstart.md        # Fase 1
├── contracts/
│   └── planejar_marcos.md   # contrato da ferramenta (entrada, dados, erros)
├── checklists/requirements.md
├── tasks.md             # gerado pelo /speckit-tasks
└── traceability.md      # exportada no fim do run
```

### Source Code (repository root)

```text
mcp_server/bussola_mcp/
├── contratos.py                    # ACRÉSCIMO (contracts:): Entrada/Dados de marcos
├── dominio/
│   └── marcos.py                   # NOVO (009): engine determinística, funções puras
└── ferramentas/
    ├── __init__.py                 # NOVO (009): pacote criado por este ciclo
    └── planejar_marcos.py          # NOVO (009): ferramenta MCP read-only
mcp_server/tests/marcos/
├── test_engine.py                  # NOVO (009)
└── test_ferramenta.py              # NOVO (009)

agent/bussola_agent/
├── estado.py                       # ACRÉSCIMO (contracts:): CHAVE_MARCOS
├── extensoes.py                    # ACRÉSCIMO (contracts:): pacote marcos em PACOTES_EXTENSAO
└── marcos/
    ├── __init__.py                 # NOVO (009): registra instrução + callback
    ├── registro.py                 # NOVO (009): after_tool ordem 30 grava o state
    └── instrucao.py                # NOVO (009): trecho de prompt (ordem 90)
agent/tests/marcos/
└── test_extensao.py                # NOVO (009)

web/src/
├── sessao/catalogo.ts              # ACRÉSCIMO: entrada planejar_marcos
├── componentes/conversa/Conversa.tsx  # ACRÉSCIMO: case "CardMarcos"
└── componentes/cards/
    ├── CardMarcos.tsx              # NOVO (009)
    └── CardMarcos.test.tsx         # NOVO (009)

docs/ciclos/contratos.md            # ACRÉSCIMO (contracts:): §1 mapa, §5 ferramenta, §6 chave
contracts/fixtures/ferramentas/     # ACRÉSCIMO (contracts:): golden de planejar_marcos (2 cortes)
Makefile                            # ACRÉSCIMO: nada previsto (os targets atuais já cobrem)
```

**Structure Decision**: o ciclo cria arquivos novos e só acrescenta linhas em
arquivos de contrato. `ferramentas/` pertence ao ciclo 003 no mapa atual; como
o diretório ainda não existe em `main` e o 009 entrega a primeira ferramenta,
o commit `contracts:` declara a co-propriedade (`ferramentas/planejar_marcos.py`
→ 009). Mesma lógica de `dominio/marcos.py` ao lado de `dominio/simulacao.py`
(001).

## Mudança de contrato (commit `contracts: ferramenta planejar_marcos e chave marcos`)

Aditiva, sem remover nem renomear nada:

1. `docs/ciclos/contratos.md`
   - §1: linhas `dominio/marcos.py 009`, `ferramentas/planejar_marcos.py 009`,
     `agent/bussola_agent/marcos/ 009`, `mcp_server/tests/marcos/ 009`,
     `agent/tests/marcos/ 009`.
   - §5: linha de `planejar_marcos` na tabela de ferramentas + entrada em
     `TABELAS_FERRAMENTA`.
   - §6: chave `marcos` na tabela de `session.state`; ordens de instrução
     90–99 e `after_tool` ordem 30 reservadas ao 009
     ([research.md](./research.md) R8).
2. `mcp_server/bussola_mcp/contratos.py`: `EntradaPlanejarMarcos`,
   `Motivo`, `Marco`, `RegrasMarco`, `DadosPlanejarMarcos`, entradas em
   `FERRAMENTAS` e `TABELAS_FERRAMENTA`. **Não** entra em `FERRAMENTAS_P0`,
   `FERRAMENTAS_MOCK` nem `FERRAMENTAS_GOLDEN` no primeiro passo (ver Fase 2).
3. `agent/bussola_agent/estado.py`: `CHAVE_MARCOS = "marcos"`, entrada em
   `CHAVES` e em `estado_inicial` (valor `None`).
4. `agent/bussola_agent/extensoes.py`: `"bussola_agent.marcos"` em
   `PACOTES_EXTENSAO`.
5. Testes de contrato existentes que enumeram chaves/ferramentas
   (`agent/tests/contrato/test_estado.py`,
   `mcp_server/tests/contrato/test_contratos.py`,
   `mcp_server/tests/contrato/test_politicas_repo.py`) são ajustados **no mesmo
   commit**, sem afrouxar asserção: o que era lista fechada continua fechada,
   com o item novo.

Riscos do contrato: conflito com o 003 em `FERRAMENTAS`/`TABELAS_FERRAMENTA` e
com o 004 em `estado.py`. Resolução por união das linhas, como manda
contratos §1.

## Fases

### Fase 0 — Pesquisa

Decisões e alternativas em [research.md](./research.md). Em resumo:

- **R1**: a engine não importa `simulacao.py` (001, ausente em `main`).
  Implementa `meses_para(valor, aporte)` própria, forma fechada com rendimento
  zero, isolada numa função de 3 linhas; quando o 001 entrar, ela passa a
  delegar (uma linha). Alternativa rejeitada: injetar a função por parâmetro
  (abstração sem segundo caso de uso hoje).
- **R2**: o contexto financeiro é calculado por `contexto_de_perfil(...)` em
  `dominio/marcos.py`, a partir de `list[PerfilMes]` e `list[Parcela]`. Há
  sobreposição conceitual com o futuro `metricas.py` (001); a função fica com
  assinatura compatível para delegar depois.
- **R3**: gatilho de uso é do agente (instrução de prompt), não de mudança em
  `simular_objetivo` (Q-009-5).
- **R4**: no front, o card entra pelo catálogo (`catalogo.ts`) e pelo `switch`
  de `Conversa.tsx`, como os outros; no modo simulado do 008, o roteiro só
  ganha marcos se houver fixture — fora do escopo mínimo.

### Fase 1 — Projeto

- [data-model.md](./data-model.md): `ContextoFinanceiro`, `Objetivo`,
  `RegrasMarco`, `Motivo`, `Marco`, `PlanoMarcos`, com tipos e invariantes.
- [contracts/planejar_marcos.md](./contracts/planejar_marcos.md): entrada,
  `dados`, `fonte`, `avisos` e os 5 códigos de erro.
- [quickstart.md](./quickstart.md): como rodar, testar e exercitar a
  ferramenta local.

**Ordem de prioridade implementada (FR-008)**

| Nível | Gatilhos que acendem | Tipos de marco |
|---|---|---|
| 1 | `CAPACIDADE_INSUFICIENTE`, `RISCO_EXCESSIVO`, `DIVIDA_A_RESOLVER` | `EQUILIBRAR_FLUXO`, `REDUZIR_DIVIDA_CARA` |
| 2 | `SEM_RESERVA` | `FORMAR_RESERVA` (alvo 3× gasto médio; parcial 1× quando o prazo não cabe) |
| 3 | `VALOR_DISTANTE_DOS_RECURSOS`, `RENDA_NAO_SUSTENTA` | `ACUMULAR_PARTE_DA_META`, `AUMENTAR_CAPACIDADE` |
| 4 | `PRAZO_NAO_CABE`, `PREMISSA_IRREALISTA` | `AJUSTAR_PRAZO` |

O próximo marco é o primeiro do menor nível aceso. A trajetória traz até 4
marcos; com `trajetoria_incerta`, só o próximo (FR-024).

### Fase 2 — Tarefas

Gerada por `/speckit-tasks` em [tasks.md](./tasks.md). Ordem pretendida:
contrato → engine (TDD) → ferramenta → extensão do agente → front → golden e
gates. Tarefas que exigem 001/003/004 em `main` ficam `[aguarda S1/S3/S4]`:

- golden de `planejar_marcos` em `contracts/fixtures/ferramentas/` e inclusão
  em `FERRAMENTAS_GOLDEN`/`FERRAMENTAS_MOCK` dependem do mock do 000 ser
  estendido, que é caminho do 000/003 → `[aguarda S3]`;
- registro da ferramenta no `server.py` real → `[aguarda S3]` (hoje o
  `server.py` é o mock do 000);
- instrução de prompt integrada ao prompt base e eval de números →
  `[aguarda S4]`.

Até lá, a ferramenta é exercitada por teste direto da função com
`RepositorioFake`, e a extensão do agente por teste sem LLM.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `usar_saldo_atual = True` por padrão, divergindo de `RegrasCenario` (contratos §4) | Decisão explícita da Pessoa B no `clarify` (Q-009-3): sem dado de patrimônio na base, o saldo em conta é o único recurso já disponível mensurável | Manter `saldo_inicial = 0` alinharia com os cenários, mas deixaria o marco de acumulação sem ponto de partida. Mitigação: piso em zero, aviso da premissa na resposta, regra versionada em `RegrasMarco` — trocar o default é uma linha |
| `contexto_de_perfil` em `dominio/marcos.py` calcula médias/medianas que o futuro `metricas.py` (001) também calculará | 001 não está em `main`, e a constituição X proíbe depender de código não mergeado | Esperar o 001 pararia o ciclo. A função fica com assinatura compatível e vira um `return metricas.…(…)` quando o S1 sair |
| Arquivo novo dentro de `ferramentas/`, diretório do 003 no mapa §1 | O 009 entrega uma ferramenta; não há outro lugar onde ela possa viver sem duplicar a camada | Colocar a ferramenta no agente poria cálculo financeiro no serviço do agente, contra o princípio II/I. O commit `contracts:` declara a co-propriedade |
