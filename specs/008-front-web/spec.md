# Feature Specification: Front web da Bússola (simulação da jornada)

**Feature Branch**: `008-front-web`

**Created**: 2026-09-26

**Status**: Draft

**Input**: `docs/ciclos/008-front-web.md` (via `/spec-master
docs/ciclos/008-front-web.md`). Pedido do time (26/09/2026): "precisamos do
front para simular o uso da Bússola; desenvolva com React a aplicação com
base no protótipo, integrando todas as soluções do MVP". Protótipo:
`docs/design/`. Formatos: `docs/ciclos/contratos.md` (contratos v1).

> **Nota sobre o nível de detalhe.** O front é o **consumidor** de um
> contrato técnico (eventos do agente, envelopes das ferramentas, chaves do
> estado da sessão). Por isso a spec cita nomes de ferramentas, códigos de
> erro e chaves de estado do contrato. Decisões de *como* implementar ficam no
> `plan.md`.

## Clarifications

### Session 2026-09-26

Resolvidas automaticamente (Spec Master, fase clarify). Classificação entre
parênteses.

- Q: Qual objetivo o roteiro simulado usa, já que o protótipo mostra R$ 60
  mil em 36 meses? → A: R$ 30 mil de entrada em 24 meses, a única entrada com
  golden de `simular_objetivo` e `comparar_cenarios` (contratos §8). Os
  valores do protótipo são placeholders e não aparecem.
  (RESOLVABLE_FROM_CONTEXT)
- Q: Com os goldens, só o cenário acelerado cabe em 24 meses. Qual é o
  recomendado? → A: o cenário viável de menor esforço; com os goldens do
  âncora, o acelerado. O texto da recomendação explica que os outros dois não
  cabem no prazo. (RESOLVABLE_FROM_CONTEXT)
- Q: Quem produz os números das ferramentas locais de 005/006 (plano, desvio,
  rotas) no modo simulado? → A: o **agente simulado**, que emula as
  ferramentas com as regras publicadas nos contextos 005 e 006 (desvio com
  tolerância de 10%, rotas "manter prazo" e "manter aporte", acumulado dos
  realizados positivos). A interface nunca calcula; ela recebe esses números
  em respostas de ferramenta, como no modo ao vivo. Cada resposta emulada
  traz o aviso "Resposta simulada pelo front; regravar após o ciclo NNN".
  (SAFE_DEFAULT)
- Q: A rota recalculada chama `simular_objetivo` com entradas sem golden. O
  que o simulado devolve? → A: um envelope no formato de §5, com
  `fonte.ferramenta = "simular_objetivo"`, calculado pela mesma regra do
  golden (aporte = valor/prazo; prazo = teto de valor/aporte; rendimento 0)
  e com o aviso de resposta simulada. (SAFE_DEFAULT)
- Q: Como os estados de borda E1–E5 são disparados no modo simulado? → A:
  pelas próprias mensagens do roteiro (E1 e E2 por texto do cliente) e por
  um menu "Cenários de borda" na barra de demonstração (E3 falha de
  ferramenta, E4 dados insuficientes, E5 carregamento lento). O menu só
  existe no modo simulado. (SAFE_DEFAULT)
- Q: O modo ao vivo precisa de login? → A: não. Usa o usuário fixo da sessão
  do agente; o `id_usuario` é preenchido pelo agente (contratos §6), e o
  front nunca envia nem mostra o UUID completo. (RESOLVABLE_FROM_CONTEXT)
- Q: A auditoria vem do BigQuery? → A: não. A aba Auditoria deriva os
  eventos da própria sessão (chamadas, mudanças de estado, consentimentos,
  bloqueios e acompanhamento) a partir dos eventos do agente.
  (RESOLVABLE_FROM_CONTEXT)
- Q: Quais vistas de produto (P1–P5) entram? → A: todas, como vistas de
  leitura do plano criado, alimentadas pelo estado da sessão e pelas últimas
  respostas de ferramenta; nenhuma cria números próprios. Sem plano, cada
  vista mostra um estado vazio que leva à conversa. (SAFE_DEFAULT)
- Q: Open Finance? → A: fora de escopo; um card desabilitado "em breve".
  (EXPLICIT, contexto §9)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Simular a jornada completa sem backend (Priority: P1)

Uma pessoa do time (ou da banca) abre o front e percorre a jornada do
Fernando: define o objetivo, vê o diagnóstico, a simulação, compara cenários,
autoriza o plano e avança um mês para ver o desvio e a nova rota. Tudo roda no
navegador, sem backend, com os dados sintéticos do cliente-âncora.

**Why this priority**: é o pedido do time e o roteiro da demo. Sem isso,
ninguém consegue usar a Bússola antes de 003–006 chegarem em `main`.

**Independent Test**: abrir o front no modo simulado e seguir as sugestões da
conversa de F1 a F7; cada etapa mostra o card esperado, com números iguais
aos goldens.

**Acceptance Scenarios**:

1. **Given** o front aberto no modo simulado, **When** a tela carrega,
   **Then** aparece a saudação da Bússola, as 4 sugestões de objetivo, o
   stepper em OBJETIVO e o selo "Dados sintéticos".
2. **Given** a saudação, **When** o cliente escolhe "Quero comprar meu
   primeiro apartamento", **Then** aparece o `CardObjetivo` com tipo e
   prioridade inferidos (✓) e valor e prazo faltando (?), e a pergunta sobre
   entrada e prazo com respostas rápidas.
3. **Given** a pergunta do objetivo, **When** o cliente responde "R$ 30 mil
   em 2 anos", **Then** o objetivo fica completo, o stepper vai para
   ENTENDER e aparecem 4 linhas de ferramenta (Perfil financeiro,
   Capacidade de poupança, Dívidas e parcelas, Oportunidades de corte) que
   passam de "consultando" para "ok", seguidas de `CardDiagnostico` e
   `CardDividas` com os valores dos goldens de jan–jun/2025.
4. **Given** o diagnóstico, **When** o agente simula o objetivo, **Then**
   aparece o `CardSimulacao` com o aporte e as premissas do golden, e o
   stepper vai para ANTECIPAR.
5. **Given** a simulação, **When** o cliente pede para comparar caminhos,
   **Then** aparece o `ComparadorCenarios` com os 3 cenários do golden, o
   selo "Recomendado" no cenário viável de menor esforço, o campo "Outro
   caminho" e a `ExplicacaoRecomendacao`; o stepper vai para ORIENTAR.
6. **Given** o comparador, **When** o cliente clica em "Escolher este
   caminho", **Then** o stepper vai para AGIR e aparece o
   `CardConsentimento` para criar o plano.
7. **Given** o consentimento pendente, **When** o cliente clica em
   "Autorizar", **Then** o front envia "sim", o card vira recibo
   (Autorizado, data e hora, ID do consentimento) e aparece o `CardPlano`
   com meta, aporte, prazo e próximos passos.
8. **Given** um plano criado, **When** o apresentador clica em "Avançar um
   mês ▸", **Then** o front envia "avançar um mês", aparece o `DivisorMes`
   "Julho de 2025 liberado", o `CardPlanejadoRealizado` com planejado,
   realizado, desvio e causa principal, e o `CardRotaRecalculada` com as
   rotas A e B; o stepper vai para ACOMPANHAR e a barra de demonstração
   mostra jul/2025.

---

### User Story 2 - Ver os bastidores e a governança (Priority: P1)

Durante a conversa, a pessoa abre os Bastidores e vê a jornada, as
ferramentas chamadas (com nome técnico, parâmetros sem dados pessoais e
fonte), os consentimentos e a trilha de auditoria da sessão.

**Why this priority**: a "autonomia governada" é o diferencial da Bússola e
precisa ficar visível para a banca.

**Independent Test**: depois de criar o plano no modo simulado, abrir cada
aba dos Bastidores e conferir que os itens batem com o que aconteceu na
conversa.

**Acceptance Scenarios**:

1. **Given** qualquer momento da conversa, **When** a pessoa abre os
   Bastidores, **Then** vê 4 abas (Jornada, Ferramentas, Consentimentos,
   Auditoria) e o rodapé com o estado da sessão (cliente mascarado
   `36a2…7269`, mês de referência, estado da jornada, plano).
2. **Given** um número num card, **When** a pessoa abre o `ChipFonte`,
   **Then** vê a ferramenta, as tabelas, o período e os avisos da resposta
   que gerou o número.
3. **Given** um consentimento decidido, **When** a pessoa abre a aba
   Consentimentos, **Then** vê ação, status, horário e ID.
4. **Given** um avanço de mês com desvio, **When** a pessoa abre a aba
   Auditoria, **Then** vê `acompanhamento_mes_avancado`, `desvio_detectado`
   e `rota_recalculada`, em ordem, com horário.

---

### User Story 3 - Conversar com o agente real (Priority: P2)

Com o agente rodando localmente (`make agent`) ou publicado, a pessoa troca o
modo para "ao vivo" e conversa com o agente real; o front mostra as
chamadas, os cards e o estado exatamente como no modo simulado.

**Why this priority**: garante que o front é o canal da demo final quando
004–006 chegarem, e não só uma maquete.

**Independent Test**: com o agente hello do 000 no ar, trocar para "ao
vivo", enviar uma pergunta que dispare uma ferramenta MCP e ver a
`LinhaFerramenta` e o card correspondente.

**Acceptance Scenarios**:

1. **Given** o modo ao vivo e o agente no ar, **When** a tela carrega,
   **Then** o front cria uma sessão e mostra o estado inicial lido dela.
2. **Given** uma mensagem enviada, **When** o agente responde em streaming,
   **Then** o texto aparece aos poucos, as chamadas viram
   `LinhaFerramenta` e as respostas viram cards, com o mesmo mapeamento do
   simulado.
3. **Given** o agente fora do ar, **When** a pessoa tenta conversar,
   **Then** vê uma mensagem clara de indisponibilidade com "Tentar de novo"
   e a sugestão de voltar ao modo simulado, sem detalhes técnicos.

---

### User Story 4 - Ensaiar estados de borda (Priority: P2)

A pessoa reproduz os estados de borda da demo: guardrail (E1), promessa de
crédito (E2), ferramenta indisponível com "Tentar de novo" (E3), dados
insuficientes (E4) e carregamento com skeleton (E5).

**Why this priority**: a banca vai testar limites; o time precisa ensaiar as
respostas.

**Independent Test**: no modo simulado, enviar as frases de E1 e E2 e
disparar E3–E5 pelo menu da barra de demonstração.

**Acceptance Scenarios**:

1. **Given** o modo simulado, **When** o cliente pede dados de outro cliente
   ou manda ignorar as instruções, **Then** aparece o `AlertaGuardrail` e a
   Auditoria registra `guardrail_bloqueio`.
2. **Given** o modo simulado, **When** o cliente pergunta se o financiamento
   vai ser aprovado, **Then** o agente recusa a promessa e oferece uma
   simulação genérica, sem taxas.
3. **Given** E3 ativado, **When** o diagnóstico roda, **Then** a linha de
   Oportunidades de corte fica em erro com "Tentar de novo", o agente segue
   com o que tem, e o clique em "Tentar de novo" repete a consulta com
   sucesso.
4. **Given** E4 ativado, **When** o diagnóstico roda, **Then** o card mostra
   o aviso de poucos meses de histórico, sem erro fatal.
5. **Given** E5 ativado, **When** o agente responde, **Then** aparecem
   skeletons de card e o cursor de digitação antes do conteúdo.

---

### User Story 5 - Consultar o plano fora da conversa (Priority: P3)

Depois de criar o plano, a pessoa navega pelas vistas de produto: encerramento
(P1), meu plano (P2), trilha da jornada (P3), resumo (P4) e check-in mensal
(P5).

**Why this priority**: completa a experiência do protótipo, mas a demo se
sustenta sem ela.

**Independent Test**: criar o plano no simulado e abrir cada vista; os
números batem com os cards da conversa.

**Acceptance Scenarios**:

1. **Given** um plano criado, **When** a pessoa abre "Meu plano", **Then** vê
   meta, aporte, prazo, progresso e meses acompanhados, com `ChipFonte`.
2. **Given** nenhum plano, **When** a pessoa abre uma vista de produto,
   **Then** vê um estado vazio que leva de volta à conversa.

---

### Edge Cases

- Resposta de ferramenta com `erro.codigo` desconhecido: mostra
  `ErroFerramenta` com mensagem genérica em pt-BR.
- Resposta de ferramenta local com campos extras ou faltando: o card mostra o
  que reconhece e ignora o resto, sem quebrar a tela.
- "Avançar um mês" sem plano: erro `SEM_PLANO_ATIVO` com orientação para
  criar o plano.
- "Avançar um mês" em dez/2025: erro `FIM_DO_REPLAY`; o botão fica
  desabilitado com a explicação.
- Resposta ambígua ao consentimento ("sim, mas…"): o consentimento continua
  pendente e o agente pede nova confirmação.
- "Agora não": o card vira recibo "Recusado", respeitoso, e nenhum plano é
  criado.
- Pedido de compartilhar dados: sempre recusado, com `guardrail_bloqueio`.
- Evento de streaming cortado no meio: o parser espera o restante e não
  duplica mensagem.
- Mobile 390 px: stepper compacto, Bastidores em bottom sheet, cenários em
  carrossel.
- Navegador sem `backdrop-filter` ou com transparência reduzida: superfícies
  sólidas legíveis.

## Requirements *(mandatory)*

### Functional Requirements

**Conversa e jornada**

- **FR-001**: O front MUST mostrar a conversa com mensagens do cliente e do
  agente, com o texto do agente aparecendo em streaming.
- **FR-002**: O front MUST mostrar cada chamada de ferramenta como
  `LinhaFerramenta` com nome legível, período e status (consultando, ok,
  erro); o nome técnico aparece só nos Bastidores.
- **FR-003**: O front MUST transformar cada resposta de ferramenta com
  envelope `{dados, fonte, avisos}` no card da ferramenta, conforme a tabela
  do plano (perfil → `CardDiagnostico`, dívidas → `CardDividas`,
  oportunidades → `CardOportunidadesCorte`, simulação → `CardSimulacao`,
  cenários → `ComparadorCenarios`, plano → `CardPlano`, avanço de mês →
  `DivisorMes` + `CardPlanejadoRealizado` + `CardRotaRecalculada`).
- **FR-004**: O front MUST transformar cada resposta com `erro.codigo` em
  `ErroFerramenta` com mensagem em pt-BR e "Tentar de novo" quando o erro for
  temporário (`INDISPONIVEL`), sem SQL, nomes de projeto ou detalhes
  técnicos.
- **FR-005**: O `StepperJornada` MUST refletir `estado_jornada` do estado da
  sessão (6 estados; concluídos, atual e futuros) e ter versão compacta
  "N/6 · Estado" no mobile.
- **FR-006**: O front MUST oferecer sugestões de resposta rápida quando o
  agente as propõe e sugestões de objetivo na tela inicial.

**Números e fontes**

- **FR-007**: Todo número na tela MUST vir de uma resposta de ferramenta; o
  front só formata (BRL com separador brasileiro, período `jan–jun/2025`,
  data `26/09/2026 14:32`) e nunca soma, divide ou arredonda para gerar um
  valor novo.
- **FR-008**: Todo card com número MUST ter `ChipFonte` com ferramenta,
  tabelas, período e avisos da resposta de origem.
- **FR-009**: Avisos da resposta (`avisos`) MUST aparecer no card como
  alerta âmbar, não como erro.

**Consentimento e ações**

- **FR-010**: Com um consentimento `pendente` no estado, o front MUST
  mostrar o `CardConsentimento` (O que vou fazer, O que não vou fazer, Dados
  usados, Autorizar, Agora não) com o visual de consentimento.
- **FR-011**: "Autorizar" e "Agora não" MUST enviar as mensagens "sim" e
  "não"; o front não decide o consentimento.
- **FR-012**: Após a decisão, o card MUST virar recibo com status, data e
  hora, e ID do consentimento.
- **FR-013**: O front MUST NOT ter botões de contratação, transferência ou
  investimento; ações do `CardPlano` e da rota recalculada só enviam
  pedidos ao agente, que passam pelo consentimento.

**Acompanhamento**

- **FR-014**: A barra de demonstração MUST mostrar o mês de referência lido
  de `ate_anomes` e o botão "Avançar um mês ▸", que envia "avançar um mês".
- **FR-015**: O botão MUST ficar desabilitado com explicação quando não há
  plano ou quando o mês é dez/2025.

**Bastidores e auditoria**

- **FR-016**: Os Bastidores MUST ter as abas Jornada, Ferramentas,
  Consentimentos e Auditoria e um rodapé com o estado da sessão.
- **FR-017**: A aba Auditoria MUST listar os eventos da sessão com os
  `tipo_evento` de contratos §6, derivados dos eventos do agente, sem
  consultar serviços externos.
- **FR-018**: O ID do cliente MUST aparecer só mascarado (`36a2…7269`).

**Modos de conexão**

- **FR-019**: O modo simulado MUST funcionar sem rede, com um agente
  simulado que emite os mesmos tipos de evento do agente real e usa as
  respostas golden das ferramentas MCP sem alteração.
- **FR-020**: O modo ao vivo MUST criar uma sessão no agente, enviar
  mensagens e receber a resposta em streaming, aplicando o mesmo mapeamento
  de eventos do simulado.
- **FR-021**: O modo MUST ser escolhido por configuração de build e por um
  controle na barra de demonstração; trocar de modo reinicia a conversa.
- **FR-022**: O roteiro simulado MUST ser determinístico: a mesma sequência
  de mensagens produz os mesmos eventos, e o roteiro gravado pode ser
  regenerado sem diferença.

**Estados de borda**

- **FR-023**: O modo simulado MUST reproduzir E1 (guardrail), E2 (promessa
  de crédito), E3 (ferramenta indisponível com nova tentativa), E4 (dados
  insuficientes) e E5 (carregamento com skeleton).

**Vistas de produto**

- **FR-024**: O front MUST oferecer as vistas P1–P5 a partir do plano
  criado, só com números já recebidos de ferramentas, e estado vazio sem
  plano.

**Visual, acessibilidade e segurança**

- **FR-025**: A interface MUST seguir o protótipo Dynamic Glass (tokens,
  3 níveis de vidro, tags semânticas, tipografia) em claro e escuro.
- **FR-026**: A interface MUST atender WCAG AA, foco visível, alvos de
  44 px no mobile, status com texto e ícone, e respeitar movimento e
  transparência reduzidos, com fallback sem desfoque.
- **FR-027**: O selo "Dados sintéticos" e o disclaimer "Simulação com dados
  sintéticos. Não é oferta nem garantia de crédito." MUST ficar visíveis.
- **FR-028**: O front MUST NOT conter segredos, SQL, nome de projeto de
  nuvem ou ID completo de cliente no código entregue ou na tela.
- **FR-029**: Todo texto ao cliente MUST estar em pt-BR, sem as palavras
  "garantido", "aprovado" ou "contrate agora".
- **FR-030**: Cada card MUST ter como rótulo acessível o nome do componente
  do protótipo (§5 do prompt do design).

### Key Entities

- **Evento do agente**: unidade que o agente emite (texto, chamada de
  ferramenta, resposta de ferramenta, mudança de estado), com autor, horário
  e indicação de parcial.
- **Estado da sessão**: as chaves de contratos §6 (`id_usuario`,
  `ate_anomes`, `estado_jornada`, `objetivo`, `cenarios`,
  `cenario_escolhido`, `ultimas_fontes`, `consentimentos`, `plano_id`,
  `acompanhamento`).
- **Resposta de ferramenta**: envelope `{dados, fonte, avisos}` ou
  `{erro: {codigo, mensagem}}`.
- **Item da conversa**: mensagem do cliente, mensagem do agente, linha de
  ferramenta, card ou alerta, na ordem em que chegaram.
- **Evento de auditoria**: `tipo_evento`, horário, estado da jornada e
  resumo sem texto livre.
- **Roteiro simulado**: sequência determinística de eventos para as
  mensagens da demo, gerada a partir dos goldens.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma pessoa sem contexto percorre F1–F7 no modo simulado em até
  5 minutos, só seguindo as sugestões da tela.
- **SC-002**: 100% dos números exibidos no roteiro simulado batem com os
  goldens ou com as respostas emuladas registradas no roteiro gravado.
- **SC-003**: 100% dos cards numéricos têm fonte consultável em um clique.
- **SC-004**: Os 5 estados de borda são reproduzíveis em até 3 interações
  cada.
- **SC-005**: A tela inicial fica utilizável em até 2 segundos num notebook
  comum, sem rede.
- **SC-006**: Nenhuma ocorrência de segredo, SQL, nome de projeto ou UUID
  completo no pacote entregue (verificação automatizada).
- **SC-007**: A jornada completa é utilizável numa tela de 390 px de largura
  e no modo escuro, sem rolagem horizontal.

## Assumptions

- O usuário da simulação é sempre o cliente-âncora (Fernando); não há
  seleção de cliente.
- O mês de referência inicial é jun/2025 (`REPLAY_START_ANOMES`).
- As formas dos resultados das ferramentas locais de 005/006 seguem os
  contextos 005 e 006; se mudarem, o roteiro é regravado e o front tolera
  campos extras (contexto §10).
- Em produção, o build é servido pelo agente na mesma origem (007); em
  desenvolvimento, um proxy local encaminha as chamadas ao agente.
- O brand kit oficial, se chegar, substitui acento e tipografia sem mudar a
  estrutura.
- Sem autenticação de usuário final (contexto §9).
