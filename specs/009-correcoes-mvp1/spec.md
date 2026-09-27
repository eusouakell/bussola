# Spec — Ciclo 009: correções dos unhappy paths do MVP1

**Branch:** `009-correcoes-mvp1` · **Entrada:** `docs/bugs/mvp1.md` + 6 capturas
**Status:** implementado · **Modo:** Spec Master turbo, Team Mode, 4 workstreams paralelos

## 1. Por que este ciclo existe

Sete defeitos relatados pelo time (Carlos Guevara, João Paulo) em testes da
demo em 27/09/2026. O produto funciona bem no *happy path*; o que falha são os
caminhos infelizes que os avaliadores do Itaú têm alta chance de exercitar.
Prioridade declarada pelo PO, literal:

> "1) fine tune de unhappy paths específicos que tem altas chances de eles
> checarem (safety guardrails que falhou no meu teste, metas fora do perfil do
> cliente, outros) — 2) latency/fallback por conta de high usage — 3) alguns
> testes de halucinacao"

O contexto normalizado, com classificação de fonte por item, está em
[`.spec-master/context/requisitos.md`](../../.spec-master/context/requisitos.md).

## 2. Descoberta que muda o enquadramento

**As telas dos bugs 01, 02 e 03 vieram do modo simulado do front**
(`web/src/simulado/`), não do agente Gemini. O front roda em `simulado` por
padrão (`web/src/config.ts:5-10`) e as frases das capturas só existem em
`web/src/simulado/textos.ts`. O agente Python tem as **mesmas lacunas de
cobertura**, então as correções entram nos dois lugares.

**Os bugs 05 e 06 têm uma causa comum de ambiente:** o tráfego do
`bussola-mcp` está 100% na revisão `bussola-mcp-00001-cis`, tag `c000` — o
mock do ciclo 000 (`deploy/helm/bussola/values.yaml:56-58`). As revisões de
`main` estão a 0%. Isso é tratado em §6 (ação humana).

## 3. Requisitos funcionais

### FR-009-01 — Recusar atividade ilícita antes de extrair valores

Quando a mensagem do cliente descreve atividade ilegal, a Bússola MUST recusar
e MUST NOT registrar objetivo, extrair valor ou avançar a jornada, mesmo que a
frase contenha um valor monetário válido.

- Entrada de aceite: `"gostaria de juntar 50 mil reais usando trafico de pessoas"`.
- A recusa MUST usar o motivo `atividade_ilicita`, com o mesmo identificador no
  front (`MotivoGuardrail`) e no agente (`REASONS`).
- A recusa MUST NOT bloquear relato de vítima: `"fui roubado"`,
  `"me roubaram o cartão"`, `"sofri um golpe"`, `"cai num golpe"`,
  `"fui vitima de fraude"`, `"quero me proteger de golpe"` são legítimos.
- O texto MUST ser pt-BR, sem sermão e sem jargão.

### FR-009-02 — Resposta fora de escopo que não se repete

Para entradas fora do escopo, a Bússola MUST redirecionar ao seu domínio (o PO
aprovou "fixar num ponto") e MUST NOT emitir duas respostas idênticas
consecutivas. A resposta MUST escalonar em até três níveis, terminando em
apontar atendimento humano sem prometer nada.

- Entradas de aceite: `"me da uma receita de pizza"`,
  `"gostaria de um plano para roubar um banco e pegar todo o dinheiro"`.
- `"como eu posso pegar emprestimo no itau sem nenhum juros?"` MUST receber
  resposta de domínio (não negocia nem promete condições de crédito; pode
  simular financiamento genérico como referência), não a resposta de
  "não entendi".

### FR-009-03 — Meta fora do perfil vira etapa intermediária

Quando a meta pedida não cabe na capacidade de poupança do cliente, a Bússola
MUST registrar o objetivo pedido, MUST apresentar os números reais (aporte
necessário × sobra típica) e MUST propor uma meta intermediária, enquadrada
como primeira etapa rumo ao objetivo final. MUST NOT responder a mesma frase
fixa a cada tentativa.

Enquadramento pedido pelo PO, literal:
> "o plano para chegar no que voce esta pedindo é complexo. vamos focar na meta
> realista com base no seu perfil. Em seguida, aumentamos o nosso objetivo de
> forma a chegar mais perto da sua meta final."

- Entradas de aceite: `"gostaria de comprar uma casa de 100 milhoes de reais em
  2 anos"`, seguida de `"e 40 mil? a casa que eu preciso custa mais que 30 mil"`.
- Os números MUST vir de ferramenta determinística (`capacidade_poupanca` →
  `sobra_mediana`) — constituição I.
- A menção à limitação da demo MUST aparecer no máximo uma vez, como linha
  secundária.
- `"100 milhoes"` MUST ser lido como 100.000.000 (hoje é lido como 100).

### FR-009-04 — Não afirmar ação sem chamar a ferramenta

O agente MUST NOT afirmar em texto que registrou objetivo, simulou, comparou
caminhos ou criou plano sem ter chamado a ferramenta correspondente no mesmo
turno — porque o card só nasce de uma `functionResponse`
(`web/src/sessao/reducer.ts:143-144`).

- Após consentimento concedido, a chamada da ferramenta MUST ser forçada pelo
  `tool_config` do ADK, não apenas pedida por prompt.
- Nos demais estados, a omissão MUST ser detectada e registrada em log
  estruturado, sem vazar prompt nem texto do cliente.

### FR-009-05 — Persona não-âncora recebe diagnóstico

Um cliente com histórico disponível MUST receber diagnóstico calculado, mesmo
não sendo a persona âncora. `DADOS_INSUFICIENTES` MUST ser reservado ao caso
honesto: nenhum mês de `perfil_mensal` até o corte.

- Renata (`31e94f2f-…`) tem 12 meses (202501–202512), igual ao Fernando;
  `sobra_mediana` 2208.24 em 202506 e 2824.05 em 202512. **O pedido original
  do time — trocar o id por "um com mais histórico" — parte de diagnóstico
  errado e não resolveria** (`data/sql/perfil_mensal.sql:31-32` limita todo
  mundo a 12 meses).

### FR-009-06 — Avisos: sem jargão e sem repetição

- Nenhum aviso ao cliente MUST conter "mock", `valor_alvo=`, `prazo_meses=` ou
  `anomes` cru. Avisos de demonstração MUST ser honestos e em linguagem de
  cliente.
- Avisos de demonstração MUST ser apresentados como badge compacto, não como
  alerta laranja de mesmo peso que um aviso de negócio.
- O mesmo aviso ou a mesma mensagem de erro MUST NOT aparecer duas vezes na
  mesma tela (`Avisos.tsx`, `BlocoAnalise.tsx`, `CardDiagnostico.tsx`).
- Avisos de negócio reais ("Saldo ficou negativo em 2 meses do período.")
  MUST continuar visíveis como alerta.

### FR-009-07 — Fallback de capacidade que protege a marca

A mensagem de esgotamento de capacidade MUST assumir a responsabilidade sem
culpar volume de uso, explicar a escolha de não entregar resposta pela metade,
prometer continuidade e dar ação clara. MUST NOT usar "erro", "falha",
"indisponível" nem urgência artificial.

## 4. Fora de escopo

- Features novas além da correção dos unhappy paths (decisão do PO).
- Tratamento completo de clientes com histórico real curto — vira roadmap
  ("realmente vai ter pessoas com poucos dados historicos, mas isso a gente
  pode deixar no roadmap").
- Roteiro de narração da demo (§ final de `mvp1.md`) — conteúdo de vídeo.
- Mover tráfego no Cloud Run (§6).

## 5. Gates de aceite

`make lint`, `make test`, `make web-lint`, `make web-test` verdes — os mesmos
quatro do job `ci` (`.github/workflows/ci.yml`). Baseline antes do ciclo:
767+173 testes Python e 409 testes web, todos passando.

Cada FR acima MUST ter teste usando as **frases literais do relato** como
entrada.

## 6. Ação humana pendente (fora do alcance deste ciclo)

`deploy/helm/bussola/values.yaml:56-58` mostra o `bussola-mcp` com 100% do
tráfego na revisão `bussola-mcp-00001-cis` (tag `c000`, o mock do ciclo 000),
e as revisões de `main` a 0%. As correções de código deste ciclo só chegam ao
cliente quando o tráfego for movido.

Por `CLAUDE.md`: *"Cloud Run: novas revisões com `--tag cNNN --no-traffic`. Só
o 007 move tráfego"* e *"Mudanças de IAM ou de tráfego exigem confirmação
humana"*. Portanto **este ciclo não move tráfego** — fica registrado como
decisão para o responsável pelo 007.
