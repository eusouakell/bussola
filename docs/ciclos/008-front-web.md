# Ciclo 008 — Front web da Bússola (simulação da jornada)

> **Disparo:** `/spec-master docs/ciclos/008-front-web.md`, no Claude Code,
> dentro da worktree `../bussola-008`, na branch `008-front-web`.
>
> **Onda:** 1. **Prioridade:** P1 (item 6 da linha de corte do
> [roadmap](./roadmap-2-pessoas.md) §6). **Spec:** `specs/008-front-web`.
>
> **Leitura obrigatória antes do Step 3:**
>
> - [contratos.md](./contratos.md) §1, §5, §6, §8 e §9.
> - [Prompt do Claude Design](../design/prompt-claude-design-chat.md) §3–§11.
> - [Design versionado](../design/README.md) (`docs/design/canvas/` e
>   `docs/design/tailwind-theme.css`).
> - [Roadmap de 2 pessoas](./roadmap-2-pessoas.md) §5 e
>   [pessoa B](./pessoa-b-agente-plataforma.md) §5.3.

## 1. Regras de execução (EXPLICIT; prevalecem sobre qualquer inferência)

1. **Uma única feature:** `id: front-web`,
   `spec_directory: specs/008-front-web`.
2. **Número fixo:** `SPECIFY_FEATURE_DIRECTORY=specs/008-front-web`.
3. **Step 2:** Spec Kit já inicializado. Estratégia Git **Trunk-Based**.
   Não habilitar a extensão git do Spec Kit.
4. **Constituição congelada.** Proposta vai para
   `specs/008-*/proposta-constituicao.md`.
5. **Escreva só nos caminhos da §4.** Este ciclo não altera `agent/`,
   `mcp_server/`, `contracts/` nem `deploy/`.
6. **Branch empilhada.** O 000 ainda não está em `main`. A branch
   `008-front-web` parte do 000 rebaseado em `main` e é rebaseada de novo
   (`git rebase --onto main 000-fundacao-contratos`) depois do S0. O front
   não importa código Python: consome só os contratos (documento e
   `contracts/fixtures/`).
7. **Origem da decisão (Q4).** O time pediu um front próprio para simular o
   uso da Bússola (pedido de 26/09/2026). Isso fecha a Q4 a favor do front
   próprio **para simulação e demo**. A ADK Web UI continua como fallback
   (roadmap §5, item 6).
8. **Ao final:**
   - `make web-lint`, `make web-test` e `make web-build` verdes;
   - `make lint` e `make test` continuam verdes (não são alterados);
   - rastreabilidade em `specs/008-*/traceability.md`.

## 2. Propósito

Entregar uma aplicação React que permite **simular o uso da Bússola** de
ponta a ponta, a partir do protótipo versionado em `docs/design/`, e que
integra todas as peças do MVP pela API do agente:

- a jornada de 6 estados (004);
- as ferramentas MCP e seus envelopes (003, contratos §5);
- consentimento e auditoria (005);
- o acompanhamento com "Avançar um mês" (006).

Enquanto 003–006 não estão em `main`, o front roda sobre fixtures e um
**agente simulado** que emite os mesmos eventos do ADK.

## 3. Escopo e comportamento esperado

### 3.1 Stack (`web/`)

- Vite, React, TypeScript e **Tailwind CSS v4**.
- Tokens Dynamic Glass de `docs/design/tailwind-theme.css` e
  `docs/design/canvas/bussola.css` (claro e escuro), com os keyframes
  `drift1`, `drift2` e `drift3` (lacuna conhecida do handoff).
- Tipografia Nunito Sans e JetBrains Mono.
- Testes de componente com Vitest + Testing Library. Lint com ESLint e
  checagem de tipos com `tsc`.
- Sem segredo no bundle. Nenhuma chamada ao GCP nem ao BigQuery.

### 3.2 Dois modos de conexão

- **Simulado (padrão):**
  - um agente simulado no navegador responde ao roteiro da demo emitindo
    **eventos no formato do ADK** (`content.parts` com `text`,
    `functionCall` e `functionResponse`, e `actions.stateDelta`);
  - os `functionResponse` das ferramentas MCP são **os goldens de
    `contracts/fixtures/ferramentas/`** do usuário-âncora, sem alteração;
  - as ferramentas locais do agente (004, 005, 006) que ainda não existem
    em `main` são simuladas com as formas de contratos §6 e dos contextos
    004, 005 e 006;
  - o roteiro gravado fica em `web/fixtures/` e é gerado por script a
    partir de `contracts/fixtures/`.
- **Ao vivo:**
  - usa a API HTTP do ADK: `POST /apps/{app}/users/{user}/sessions`,
    `POST /run_sse` e `GET /apps/{app}/users/{user}/sessions/{id}`;
  - em desenvolvimento, o Vite faz proxy para o `make agent` (porta 8000,
    app `bussola_agent`), sem CORS;
  - em produção, o build é servido pelo `bussola-agent` na mesma origem
    (o ponto de montagem é do 007, fora deste ciclo).
- A escolha do modo fica num controle da barra de demonstração e numa
  variável de build (`VITE_BUSSOLA_MODO`).

### 3.3 Contrato front ↔ agente (pessoa B §5.3)

- `functionCall` vira `LinhaFerramenta` (executando).
- `functionResponse` com envelope `{dados, fonte, avisos}` vira o card da
  ferramenta e o `ChipFonte`; a linha passa a ok.
- `functionResponse` com `erro.codigo` vira `ErroFerramenta`, inclusive os
  códigos locais `CONSENTIMENTO_NECESSARIO`, `SEM_PLANO_ATIVO` e
  `FIM_DO_REPLAY`.
- `session.state` (via `stateDelta` ou leitura da sessão) alimenta o
  `StepperJornada`, o rodapé dos Bastidores e a barra de demonstração.
- **Nenhum número na tela** que não tenha vindo de um `functionResponse`.
  O front só formata (R$, `jan–jun/2025`), nunca calcula.
- A aba Auditoria mostra os eventos da própria sessão, derivados dos
  eventos do agente (tipos de contratos §6). O front nunca consulta o
  BigQuery.
- Consentimento: os botões do `CardConsentimento` enviam `sim` ou `não`
  como mensagem.
- "Avançar um mês ▸" envia a mensagem `avançar um mês`.
- Nomes legíveis das ferramentas na conversa; o nome técnico aparece só em
  Bastidores.

### 3.4 Telas e componentes (protótipo em `docs/design/canvas/`)

- **Layout:** app primeiro (390 px); 3 zonas a partir de `lg`
  (conversa 720–760 px + Bastidores 360 px); bottom sheet dos Bastidores
  abaixo de `lg`; stepper compacto "3/6 · Antecipar" no mobile; carrossel
  de cenários no mobile.
- **Roteiro:** F1–F7 (M1–M9 no app) e F7b, com o texto do agente do
  prompt do design, trocando os números pelos dos goldens.
- **Estados de borda:** E1 guardrail, E2 promessa de crédito, E3
  ferramenta indisponível com "Tentar de novo", E4 dados insuficientes,
  E5 streaming com skeleton.
- **Produto final:** P1–P5 (encerramento, meu plano, trilha, resumo e
  check-in) como vistas a partir do plano criado.
- **Componentes da §5 do prompt**, com os mesmos nomes, como
  `aria-label` dos cards.
- **Acessibilidade:** AA, foco visível, alvos ≥ 44 px no mobile, status
  com texto e ícone, `prefers-reduced-motion`,
  `prefers-reduced-transparency` e fallback sem `backdrop-filter`.
- **Modo escuro** pelos tokens `.dark`.

### 3.5 Objetivo do roteiro simulado

- Os goldens de `simular_objetivo` e `comparar_cenarios` existem só para a
  entrada canônica `valor_alvo=30000`, `prazo_meses=24` (contratos §8).
  O roteiro simulado usa esse objetivo: "R$ 30 mil de entrada em 2 anos".
- Os valores do protótipo (R$ 60 mil, 36 meses, R$ 7.451…) são
  placeholders do design e **não** aparecem no front.

## 4. Propriedade (escreve só aqui)

- `web/` (novo; entra no mapa de contratos §1 por PR `contracts:`).
- `specs/008-front-web/`.
- `Makefile`: acréscimo dos targets `web`, `web-install`, `web-lint`,
  `web-test` e `web-build`.
- `docs/ciclos/008-front-web.md` (este arquivo, PR de planejamento).

## 5. Contratos

- **Consome:**
  - envelopes e códigos de erro de §5;
  - chaves de `session.state`, ações e `tipo_evento` de §6;
  - fixtures de §8;
  - API HTTP do ADK servida por `adk web` / `bussola-agent`.
- **Provê:**
  - `web/dist` estático para o 007 montar no `bussola-agent`;
  - fixtures de eventos em `web/fixtures/` para regravar depois de S4 e S6.

## 6. Critérios de aceite

- [ ] AC-01: `make web` sobe o front em modo simulado, sem backend, e o
      roteiro F1–F7 roda de ponta a ponta com o âncora (objetivo, entender,
      antecipar, orientar, agir com consentimento, plano e um avanço de mês
      com desvio e nova rota).
- [ ] AC-02: Todo número exibido vem de um `functionResponse`; cada card
      numérico tem `ChipFonte` com ferramenta, tabelas, período e avisos.
- [ ] AC-03: `functionCall` → `LinhaFerramenta` (executando → ok/erro);
      envelope → card; `erro.codigo` → `ErroFerramenta` com "Tentar de
      novo".
- [ ] AC-04: Consentimento pendente → `CardConsentimento`; Autorizar/Agora
      não enviam `sim`/`não`; após a decisão, o card vira recibo com
      status, horário e ID.
- [ ] AC-05: `StepperJornada`, Bastidores (Jornada, Ferramentas,
      Consentimentos, Auditoria e estado da sessão) e barra de demo leem o
      estado da sessão.
- [ ] AC-06: "Avançar um mês ▸" envia `avançar um mês` e mostra
      `DivisorMes`, `CardPlanejadoRealizado` e `CardRotaRecalculada`.
- [ ] AC-07: Estados de borda E1–E5 reproduzíveis no modo simulado.
- [ ] AC-08: Modo ao vivo cria sessão e conversa com o `make agent` via
      `/run_sse`, com o mesmo mapeamento de eventos.
- [ ] AC-09: Mobile 390 e modo escuro.
- [ ] AC-10: Testes de componente cobrindo envelope → card, `erro.codigo`
      → `ErroFerramenta` e consentimento pendente → `CardConsentimento`.
- [ ] AC-11: Nenhum segredo, SQL, nome de projeto ou ID completo de
      cliente no bundle ou na tela (ID mascarado `36a2…7269`).
- [ ] AC-12: Selo "Dados sintéticos" e disclaimer de simulação visíveis;
      nenhum botão de contratação, transferência ou investimento.

## 7. Cenários de teste

- Envelope golden de `perfil_financeiro` renderiza `CardDiagnostico` com os
  mesmos valores do arquivo, formatados em BRL.
- Envelope `{erro: {codigo: "INDISPONIVEL"}}` renderiza `ErroFerramenta`
  sem mostrar SQL nem detalhes técnicos.
- `stateDelta` com `consentimentos.criar_plano.status = "pendente"` mostra
  `CardConsentimento`; com `aceito`, mostra o recibo.
- `stateDelta` com `estado_jornada = "ORIENTAR"` marca 3 estados concluídos
  no stepper.
- O parser de SSE aceita eventos parciais e ignora linhas vazias.
- O gerador de fixtures é determinístico: regenerar não produz diff.

## 8. Dependências e gate de merge

- **Dependências duras:** 000 (contratos e fixtures).
- **Para o modo ao vivo completo:** 004, 005 e 006 em `main`. Antes disso,
  o modo ao vivo mostra o que o agente hello expõe.
- **Gate de merge:** AC-01 a AC-12 e rebase em `main` após S0.

## 9. Fora de escopo

- Servir o build no `bussola-agent` (ponto de entrada e estágio Node no
  `Dockerfile`): 007.
- Deploy e tráfego no Cloud Run: 007.
- Autenticação de usuário final.
- Open Finance (só um card desabilitado "em breve").

## 10. Questões em aberto

- Forma exata do resultado de `solicitar_consentimento`, `criar_plano`,
  `avancar_mes` e `status_plano` (definida em 005/006). O front usa as
  formas descritas nos contextos 005 e 006 e tolera campos extras.
- Brand kit oficial do banco: se chegar, prevalece sobre acento e
  tipografia.

## 11. Rastreabilidade

| Requisito | Fonte | Classificação |
|---|---|---|
| Front React para simular o uso, com base no protótipo e integrando o MVP | Pedido do time (26/09/2026) | EXPLICIT |
| Vite + React + TS + Tailwind v4, servido pelo `bussola-agent` | Roadmap §5 e pessoa B §5.3 | EXPLICIT |
| Contrato front ↔ agente (ADK API, envelopes, state, sim/não, avançar um mês) | Pessoa B §5.3 | EXPLICIT |
| Frames, componentes, tokens e copy | `docs/design/` | EXPLICIT |
| Modo simulado com agente no navegador sobre goldens | Roadmap §5 item 4 (fixtures SSE) | INFERRED |
| Objetivo canônico 30 mil / 24 meses no roteiro | Contratos §8 (golden canônico) | INFERRED |
| Auditoria derivada dos eventos da sessão | Pessoa B §5.3 ("eventos da própria sessão") | INFERRED |
| Ciclo próprio 008 em vez do escopo do 007 | Pedido do time; 007 fica com deploy | INFERRED |
| Formas das ferramentas locais de 005/006 | Contextos 005 e 006 | UNRESOLVED |
