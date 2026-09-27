# Fase 0 — Pesquisa e decisões técnicas

## R1 — Aritmética de prazo/aporte sem o `simulacao.py` do 001

**Contexto.** `dominio/simulacao.py` (`prazo_para_meta`, `aporte_para_prazo`)
é do ciclo 001 e **não existe em `main`**. A constituição X proíbe depender de
código não mergeado.

**Decisão.** `dominio/marcos.py` implementa `meses_para(falta, aporte)` e
`aporte_para(falta, prazo)` como forma fechada com rendimento zero — a mesma
premissa de `RegrasCenario` (`rendimento_mensal = 0.0`). São duas funções de
duas linhas, isoladas no topo do módulo, com o comentário de que passam a
delegar a `simulacao` quando o marco S1 sair.

**Alternativas rejeitadas.**

- Injetar a função de cálculo por parâmetro (hotspot): abstração sem segundo
  caso de uso hoje; some assim que o 001 chega.
- `importlib.util.find_spec("bussola_mcp.dominio.simulacao")` com fallback:
  dois caminhos de código e dois resultados possíveis para o mesmo número —
  pior para o determinismo exigido pelo FR-018.
- Esperar o 001: pararia o ciclo.

## R2 — Contexto financeiro sem o `metricas.py` do 001

**Decisão.** `contexto_de_perfil(perfil, parcelas, regras)` em
`dominio/marcos.py` calcula, sobre `list[PerfilMes]` e `list[Parcela]` já
filtrados por `ate_anomes`: renda média, gasto médio, sobra média, sobra
mediana, meses negativos, meses considerados, saldo atual (último mês), juros
médios pagos, valor mensal das parcelas ativas e comprometimento da renda.

**Sobreposição assumida.** O futuro `metricas.py` (001) calculará os mesmos
agregados para `perfil_financeiro`, `capacidade_poupanca` e
`dividas_e_parcelas`. A função fica com assinatura compatível (entra
`list[PerfilMes]`/`list[Parcela]`, sai um objeto) para virar uma chamada
delegada depois. Registrado em Complexity Tracking do plano.

**Definições determinísticas.**

- "Parcela ativa" = linha de `parcelas` do último `anomes` disponível com
  `parcela_atual <= parcela_total`; `meses_restantes = parcela_total -
  parcela_atual`.
- `comprometimento_renda_pct` = soma das parcelas ativas ÷ renda média × 100,
  em pontos percentuais (mesma unidade de `DadosDividasParcelas`).
- `juros_pagos_media` = média de `perfil_mensal.juros` no período.
- `saldo_atual` = `saldo_final` do último mês do período.

## R3 — Quem dispara o cálculo de marcos

**Decisão.** Ferramenta nova `planejar_marcos`, chamada pelo agente quando a
simulação volta inviável ou com prazo implausível. `simular_objetivo` e
`comparar_cenarios` **não** mudam (Q-009-5 em [questoes.md](./questoes.md)).

**Por quê.** Alterar `simular_objetivo` mexeria em ferramenta, golden e modelo
de outro ciclo (003/001, Pessoa A) e quebraria contrato existente. Ferramenta
nova é aditiva (contratos §0).

## R4 — Códigos de erro: o que esta ferramenta não usa

**Decisão.** `planejar_marcos` usa `ENTRADA_INVALIDA`,
`USUARIO_INEXISTENTE`, `DADOS_INSUFICIENTES` e `INDISPONIVEL`. **Não** usa
`PRAZO_IMPLAUSIVEL`: prazo fora de 1–360 na entrada já é `ENTRADA_INVALIDA`, e
prazo **calculado** acima de 360 meses vira `trajetoria_incerta = true` com o
marco de prazo omitido.

**Por quê.** Devolver erro nesse caso é exatamente o comportamento que a
feature existe para eliminar (FR-010, SC-008): o cliente com objetivo distante
receberia "não é possível" em vez de um primeiro marco. A divergência está
registrada em [contracts/planejar_marcos.md](./contracts/planejar_marcos.md).

## R5 — Integração no front

**Decisão.** Seguir o caminho já usado pelos outros cards: entrada em
`web/src/sessao/catalogo.ts` (`planejar_marcos` → `card: "CardMarcos"`,
`tag: "recomendacao"`), `case "CardMarcos"` no `switch` de
`Conversa.tsx`, e `CardMarcos.tsx` lendo `dados` com os helpers defensivos de
`cards/ler.ts` (`num`, `txt`, `lista`, `textos`), cabeçalho com `CabecalhoCard`
(que já traz `ChipFonte`) e `Avisos`.

**Fora do escopo mínimo.** O modo simulado do 008 (`web/src/simulado/`) só
ganha marcos se houver fixture de eventos; não é necessário para os critérios
de aceite, e entra depois se a demo pedir.

## R6 — Onde a instrução de prompt entra

**Decisão.** `extensoes.registrar_instrucao(90, ...)`. As ordens 0–49 (004),
50–69 (005) e 70–89 (006) estão reservadas em contratos §6; 90–99 passam a ser
do 009 no mesmo commit `contracts:`.

**Consequência.** `PACOTES_EXTENSAO` em `extensoes.py` precisa incluir
`"bussola_agent.marcos"` — é a única forma de o pacote ser carregado sem
editar o `agent.py` do 004 (a lista é fixa e `carregar_extensoes` não descobre
pacotes por convenção). Mudança aditiva de uma linha, no commit `contracts:`.

**Alternativa rejeitada.** Descoberta automática de pacotes
`bussola_agent.*` por convenção: mudaria o comportamento contratado do 000 e
esconderia erro de import que o contrato manda propagar (Q-04 do 000).

## R8 — Sem ferramenta ADK local: instrução + callback (drift do `implement`)

**Contexto.** O plano previa uma ferramenta ADK local em
`agent/bussola_agent/marcos/ferramenta.py` que chamaria `planejar_marcos` por
`mcp_conexao.chamar_ferramenta`. Na implementação ficou claro que o
`McpToolset` (`criar_toolset()` sem `tool_filter`) expõe **todas** as
ferramentas do MCP ao modelo, inclusive `planejar_marcos`: a ferramenta local
teria o mesmo nome, e o modelo veria dois caminhos idênticos. Dar outro nome à
local só criaria um sinônimo para a mesma coisa.

**Decisão.** O 009 não registra ferramenta local. O agente recebe:

- a **instrução** (ordem 90) dizendo quando chamar `planejar_marcos` e como
  apresentar a resposta;
- um **callback `after_tool` de ordem 30** que grava `dados` em
  `session.state["marcos"]` — exatamente o que o 004 já faz no `after_tool` 10
  para `cenarios`.

A ordem 30 é nova e entra em contratos §6 no mesmo commit `contracts:` (10 é do
004, 20 e 90 são do 005).

**Consequência nos artefatos.** AC-14 e AC-15 passam a falar de instrução e
callback; `plan.md`, `tasks.md`, `data-model.md` e
`contracts/planejar_marcos.md` foram atualizados. Nenhum FR de `spec.md`
mudou: FR-013 pede a ferramenta **de leitura no MCP** e FR-016 pede o estado da
sessão — as duas coisas continuam valendo.

**Alternativa rejeitada.** `tool_filter` no `McpToolset` para esconder
`planejar_marcos` do modelo e manter a ferramenta local: mexeria na montagem do
`root_agent` (004) e deixaria o MCP com uma ferramenta inalcançável.

## R7 — Verificação das nove proibições (FR-011)

**Decisão.** Teste léxico determinístico sobre **todas** as frases geradas pela
engine em todos os casos de teste: `por_que`, `relacao_com_objetivo`,
`indicador`, `titulo`, explicações de motivo e ressalvas. A lista de termos
proibidos vive no teste, não no código de produção, e cobre: `inviável`,
`impossível`, `nunca`, `desista`, `abandone`, `mais barato`, `aumento de
renda`, `renda maior`, `empréstimo`, `financiamento`, `com certeza`,
`garantido`, `garantimos`, `vai conseguir`.

**Cuidado.** A ressalva legítima contém "não garante"; por isso a lista proíbe
`garantido`/`garantimos`/`com certeza`, não a palavra "garantir".
