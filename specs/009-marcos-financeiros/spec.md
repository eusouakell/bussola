# Feature Specification: Marcos financeiros intermediários

**Feature Branch**: `009-marcos-financeiros`

**Created**: 2026-09-26

**Status**: Draft

**Input**: pedido do usuário (transcrito em `.spec-master/context.generated.md` §2):
"Quando o objetivo final do cliente estiver muito distante, inviável ou
incompatível com sua situação financeira atual, você NÃO deve simplesmente
rejeitar o objetivo […] Em vez disso, transforme o objetivo final em uma
sequência de milestones financeiros intermediários."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - O objetivo não cabe, e o cliente recebe o próximo marco (Priority: P1)

O cliente diz o que quer ("R$ 300 mil para a entrada de um apartamento em 2
anos"). As contas mostram que, com a capacidade de poupança atual, esse
objetivo não fecha no prazo. Em vez de ouvir "não é viável", o cliente recebe:
por que ainda não fecha, qual é o próximo marco concreto (valor e prazo), por
que esse marco importa para o objetivo maior, e que o plano é recalculado
quando ele chegar lá.

**Why this priority**: é o requisito central do pedido. Sem isso, o único
caminho da Bússola diante de um objetivo grande é rejeitá-lo, o que a fonte
proíbe explicitamente.

**Independent Test**: com o cliente-âncora das fixtures e um objetivo grande,
verificar que a resposta traz motivo determinístico, um marco com valor e
prazo, e nenhuma frase de rejeição. Entrega valor mesmo sem as histórias 2–4.

**Acceptance Scenarios**:

1. **Given** um cliente cuja capacidade sustentável de poupança é menor que o
   aporte necessário, **When** ele pede um objetivo de valor alto em prazo
   curto, **Then** a Bússola apresenta o motivo pelo qual o objetivo ainda não
   fecha e um marco intermediário com valor-alvo e prazo calculados.
2. **Given** o mesmo cliente, **When** o objetivo cabe na capacidade
   sustentável, **Then** nenhum marco é proposto e a jornada segue normalmente
   com os cenários já existentes.
3. **Given** um objetivo que não fecha, **When** a resposta é gerada,
   **Then** ela contém os cinco blocos Objetivo, Situação atual, Próximo
   marco, Por que esse marco importa e Depois disso, em pt-BR.

---

### User Story 2 - A ordem do marco se adapta à situação do cliente (Priority: P2)

Duas pessoas com o mesmo sonho recebem marcos diferentes. Quem tem dívida
cara resolve primeiro o custo da dívida. Quem tem fluxo de caixa negativo
equilibra o fluxo. Quem está equilibrado mas sem reserva forma reserva. Quem
já tem base construída parte direto para acumular a meta ou aumentar aporte.

**Why this priority**: é o que impede a Bússola de dar conselho genérico e o
que evita empurrar o cliente para risco desnecessário.

**Independent Test**: rodar o mesmo objetivo contra dois perfis financeiros
diferentes e verificar que o próximo marco tem tipo diferente, na ordem
estrutural → vulnerável → patrimônio → eficiência.

**Acceptance Scenarios**:

1. **Given** um cliente com dívida classificada como cara, **When** ele pede
   um objetivo que não cabe, **Then** o próximo marco é de redução de dívida
   ou de equilíbrio de fluxo, antes de qualquer marco de reserva ou de
   patrimônio.
2. **Given** um cliente sem dívida cara e com reserva abaixo do alvo,
   **When** ele pede o mesmo objetivo, **Then** o próximo marco é formar
   reserva, com valor e prazo calculados.
3. **Given** um cliente sem dívida cara e com reserva adequada, **When** ele
   pede o mesmo objetivo, **Then** o próximo marco é de acumulação ligada ao
   objetivo (parte da meta ou aumento de capacidade).
4. **Given** qualquer cliente, **When** existe gatilho de um nível anterior,
   **Then** nenhum marco de nível posterior é apresentado como próximo passo.

---

### User Story 3 - Objetivo muito distante, sem falsa esperança (Priority: P2)

Quando a distância entre objetivo e realidade financeira é grande demais, o
cliente não recebe uma sequência bonita que sugira que o sonho está garantido.
Recebe um primeiro marco alcançável **e** a informação explícita de que
atingi-lo não garante o objetivo final, e que renda, patrimônio, prazo ou
condições podem precisar mudar.

**Why this priority**: é a diferença entre orientação responsável e falsa
esperança; está entre as proibições explícitas da fonte.

**Independent Test**: com um objetivo desproporcional ao perfil, verificar que
a resposta marca a trajetória como incerta e traz a ressalva, sem prometer o
objetivo e sem propor objetivo mais barato.

**Acceptance Scenarios**:

1. **Given** um objetivo cujo aporte necessário continua muito acima da
   capacidade mesmo depois de todos os marcos, **When** a resposta é gerada,
   **Then** ela sinaliza trajetória incerta e inclui a ressalva de que o marco
   não garante o objetivo final.
2. **Given** qualquer resposta com marcos, **When** o texto é verificado,
   **Then** ele não diz que o cliente nunca conseguirá, não ridiculariza o
   objetivo, não promete o objetivo final, não supõe aumento de renda nem
   valorização extraordinária, não recomenda novo endividamento e não troca o
   sonho por um mais barato sem consentimento.
3. **Given** um insumo financeiro ausente (patrimônio, investimentos,
   reserva), **When** a resposta é gerada, **Then** ela declara o dado ausente
   como aviso e não apresenta marco baseado em número inventado.

---

### User Story 4 - O cliente vê a trajetória na tela (Priority: P3)

Na interface, o cliente vê a trajetória — situação atual, próximo marco em
destaque, marcos seguintes — com a origem dos números e a ressalva, no mesmo
padrão visual dos outros cards da jornada.

**Why this priority**: melhora a demo e a compreensão, mas o valor essencial
já existe na conversa.

**Independent Test**: alimentar o card com uma resposta gravada da ferramenta
e verificar trajetória, destaque do próximo marco, chip de fonte e ressalva;
alimentar com uma resposta de erro e verificar o componente de erro.

**Acceptance Scenarios**:

1. **Given** uma resposta de marcos, **When** a tela é renderizada, **Then**
   aparecem a trajetória, o próximo marco em destaque, o chip de fonte e a
   ressalva, e nenhum número que não venha da resposta da ferramenta.
2. **Given** uma resposta de erro, **When** a tela é renderizada, **Then**
   aparece o componente de erro já usado pelas outras ferramentas.

---

### Edge Cases

- **Objetivo que fecha:** nenhum marco é proposto (não inventar marco onde não
  há problema).
- **Capacidade de poupança zero ou negativa:** o marco é equilibrar o fluxo de
  caixa, não acumular.
- **Reserva já adequada e sem dívida:** pular direto para acumulação, sem
  propor reserva redundante.
- **Prazo desejado muito curto (1 mês) ou muito longo (360 meses):** o prazo
  segue a faixa já válida no produto; fora dela, erro de entrada.
- **Cliente sem nenhum mês de dados até o corte do período:** resposta de
  dados insuficientes, sem marco.
- **Valor de objetivo absurdo:** trajetória incerta declarada, sem promessa e
  sem sequência artificial.
- **Marco de valor irrelevante** (abaixo do piso de materialidade): não é
  proposto como marco.
- **Identificador de cliente inválido, inexistente, ou período fora da faixa:**
  erro de entrada/usuário inexistente, sempre como resposta estruturada, nunca
  como falha técnica exposta.
- **Falha da fonte de dados:** resposta de indisponibilidade, sem detalhe
  interno.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST identificar, por regra determinística, os motivos
  pelos quais um objetivo não cabe nas condições atuais, cobrindo os oito
  gatilhos da fonte: prazo não cabe, capacidade de poupança insuficiente,
  valor distante dos recursos disponíveis, dívida ou compromisso a resolver
  antes, ausência de reserva adequada, renda que não sustenta o objetivo com
  segurança, premissa necessária pouco realista e risco financeiro excessivo.
- **FR-002**: O sistema MUST devolver lista de motivos vazia e nenhum marco
  quando o objetivo couber nas condições atuais.
- **FR-003**: O sistema MUST propor marcos apenas a partir do contexto
  financeiro real do cliente (renda, gastos recorrentes, capacidade
  sustentável de poupança, dívidas e seu custo, reserva, recursos
  disponíveis, valor do objetivo, prazo desejado e prioridade informada).
- **FR-004**: O sistema MUST NOT inventar informação ausente. Cada insumo
  indisponível MUST virar aviso explícito, e o marco que dependeria dele MUST
  NOT ser proposto.
- **FR-005**: Todo valor monetário e todo prazo de marco MUST ser calculado
  por regra determinística testada, nunca redigido livremente pelo modelo de
  linguagem.
- **FR-006**: Cada marco MUST ter indicador verificável e ao menos um entre
  valor-alvo e prazo, com valores monetários em BRL com duas casas e prazos em
  meses inteiros.
- **FR-007**: Cada marco MUST declarar a sua relação com o objetivo final
  (por que aproxima o cliente do objetivo).
- **FR-008**: O sistema MUST ordenar os marcos em quatro níveis de prioridade —
  (1) problemas estruturais: reduzir dívida cara, equilibrar fluxo de caixa;
  (2) situação equilibrada mas vulnerável: formar reserva; (3) capacidade de
  construir patrimônio: acumular parte da meta, aumentar aporte sustentável;
  (4) base estruturada: ajustar prazo e eficiência — e MUST NOT apresentar
  marco de nível posterior como próximo passo enquanto houver gatilho de nível
  anterior.
- **FR-009**: O sistema MUST destacar um único próximo marco, mesmo quando
  devolver a trajetória completa.
- **FR-010**: O sistema MUST sinalizar trajetória incerta e incluir a ressalva
  de que atingir o marco não garante o objetivo final quando a distância
  persistir depois de todos os marcos aplicáveis.
- **FR-011**: As frases apresentadas ao cliente MUST NOT rejeitar o objetivo,
  afirmar que o cliente nunca conseguirá, ridicularizar o objetivo, prometer
  que a sequência levará ao objetivo final, supor aumento futuro de renda,
  supor valorização extraordinária de investimentos, recomendar endividamento
  para aproximar a meta, substituir o sonho por um objetivo mais barato sem
  consentimento, ou decidir unilateralmente que aspectos da vida do cliente
  devem ser sacrificados.
- **FR-012**: A apresentação ao cliente MUST seguir cinco blocos: Objetivo,
  Situação atual, Próximo marco, Por que esse marco importa e Depois disso,
  em pt-BR, conviventes com os rótulos Diagnóstico, Simulação e Recomendação
  já exigidos pela constituição.
- **FR-013**: O resultado MUST ser exposto ao agente como ferramenta de
  leitura, com os números e a origem dos números (ferramenta e período), no
  mesmo formato de resposta das ferramentas existentes.
- **FR-014**: Entrada fora das regras (identificador de cliente inválido,
  período fora da faixa permitida, valor-alvo não positivo, prazo fora da
  faixa) MUST devolver resposta de entrada inválida citando apenas o nome do
  campo, sem ecoar o valor recebido.
- **FR-015**: Cliente inexistente, ausência de meses no período e falha da
  fonte de dados MUST devolver, respectivamente, resposta de usuário
  inexistente, dados insuficientes e indisponibilidade — sempre como resposta
  estruturada, sem detalhe interno, SQL, nome de projeto ou credencial.
- **FR-016**: O último resultado de marcos MUST ficar disponível no estado da
  sessão, sem renomear nem remover nenhuma chave de estado já existente.
- **FR-017**: A interface MUST derivar a trajetória exclusivamente da resposta
  da ferramenta, sem exibir número que não tenha vindo dela, e MUST mostrar a
  resposta de erro com o componente de erro já existente.
- **FR-018**: O comportamento MUST ser determinístico: a mesma entrada produz
  a mesma saída, sem dependência de hora corrente nem de aleatoriedade.
- **FR-019**: As premissas numéricas que definem reserva adequada, dívida
  cara, fração sustentável da capacidade e piso de materialidade do marco MUST
  ser explícitas, versionadas e citadas na resposta, e MUST NOT ficar
  implícitas no texto do modelo.
- **FR-020**: A extensão MUST ser aditiva: nenhuma ferramenta, campo de
  resposta, chave de estado ou comportamento existente é removido ou
  renomeado.
- **FR-021**: A reserva de emergência adequada MUST ter como alvo três vezes o
  gasto médio mensal do cliente. Quando esse alvo exigir prazo incompatível
  com a capacidade sustentável, o próximo marco MUST ser o alvo parcial de uma
  vez o gasto médio, preservando o alvo de três vezes como marco seguinte.
  (Decisão Q-009-1 do `clarify`.)
- **FR-022**: Uma dívida MUST ser classificada como cara quando os juros médios
  pagos por mês forem maiores ou iguais a 1% da renda média, **ou** quando as
  parcelas ativas comprometerem mais de 30% da renda média. Abaixo dos dois
  pisos, o custo da dívida MUST NOT acender o gatilho de nível 1.
  (Decisão Q-009-2 do `clarify`.)
- **FR-023**: O saldo atual em conta MUST ser considerado recurso já disponível
  do cliente, com piso em zero: saldo negativo MUST contar como zero de
  recurso **e** MUST acender o gatilho de risco/fluxo de caixa, com aviso. Não
  há dado de investimento nem de patrimônio na base: qualquer outro componente
  de patrimônio MUST ser declarado como dado ausente e MUST NOT gerar marco.
  (Decisão Q-009-3 do `clarify`.)
- **FR-024**: A trajetória MUST conter até quatro marcos, com exatamente um
  destacado como próximo. Quando a trajetória for marcada como incerta, a
  resposta MUST conter apenas o próximo marco, para não sugerir sequência
  garantida. (Decisão Q-009-4 do `clarify`.)

### Key Entities

- **Objetivo**: o que o cliente quer alcançar — tipo, descrição, valor-alvo,
  prazo desejado e prioridade informada. Já existe na jornada.
- **Contexto financeiro**: retrato determinístico do cliente até o período de
  corte — renda média, gasto médio, sobra média e mediana, variabilidade,
  meses negativos, parcelas ativas, juros médios, comprometimento de renda,
  recursos disponíveis.
- **Motivo**: código determinístico que explica por que o objetivo não fecha,
  com o valor observado e o limite que ele ultrapassou.
- **Marco**: meta intermediária — ordem, nível de prioridade, tipo, título,
  indicador verificável, valor-alvo, prazo, aporte associado, por que importa
  e relação com o objetivo final.
- **Trajetória**: sequência ordenada de marcos, o próximo marco destacado, as
  ressalvas, os avisos de dado ausente e a marca de trajetória incerta.
- **Premissas**: conjunto versionado de regras numéricas (reserva, dívida
  cara, fração da capacidade, piso de materialidade, rendimento assumido
  zero, saldo inicial assumido zero).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das respostas com marcos citam a origem dos números, e
  nenhum número apresentado deixa de existir na resposta da ferramenta
  (verificação automatizada).
- **SC-002**: 0 ocorrências das nove proibições de linguagem e premissa em
  todas as frases geradas, medido por verificação léxica automatizada sobre
  todos os casos de teste.
- **SC-003**: Em 100% dos casos com gatilho de nível 1 aceso, o próximo marco
  é de nível 1.
- **SC-004**: Dois perfis financeiros distintos com o mesmo objetivo recebem
  próximos marcos de tipos distintos em 100% dos pares de teste definidos.
- **SC-005**: Todos os oito motivos e todos os tipos de marco têm ao menos um
  caso de teste, e todos os códigos de erro previstos têm ao menos um caso.
- **SC-006**: A mesma entrada produz saída idêntica em execuções repetidas
  (determinismo verificado em teste).
- **SC-007**: Os gates de qualidade do projeto passam sem rede e sem acesso à
  nuvem.
- **SC-008**: Nenhum objetivo apresentado pelo cliente é recusado: 100% dos
  casos inviáveis produzem pelo menos um marco alcançável ou a declaração
  explícita de trajetória incerta com um primeiro marco.

## Assumptions

- **A-01**: "Goal Planning Engine" e "Financial Health Context" do pedido
  correspondem, neste produto, à simulação determinística de objetivo e às
  métricas de perfil, capacidade, dívidas e cortes já contratadas. (INFERRED)
- **A-02**: Não há dado de investimento, patrimônio ou reserva na base; o que
  existe é renda, gasto, sobra, saldo de conta, parcelas e juros. (DISCOVERED)
- **A-03**: Rendimento assumido é zero, como já vale para os cenários —
  coerente com a proibição de supor valorização extraordinária. O saldo atual
  em conta, por decisão do `clarify` (Q-009-3), **conta** como recurso já
  disponível, com piso em zero; isso diverge da premissa dos cenários
  (`saldo_inicial = 0`, "saldo de conta não é reserva") e fica registrado como
  divergência deliberada em [questoes.md](./questoes.md). (EXPLICIT, decidido)
- **A-04**: A trajetória devolve até quatro marcos, com o próximo destacado, e
  apenas o próximo quando a trajetória é incerta; devolver a trajetória não é
  promessa de que ela será percorrida. (EXPLICIT, decidido — Q-009-4)
- **A-05**: A decisão de trocar o objetivo por um mais barato é sempre do
  cliente; o sistema pode apenas oferecer o recálculo. (EXPLICIT)
- **A-06**: Marcos vivem no estado da sessão; não há persistência em banco
  neste ciclo. (INFERRED)
- **A-07**: O ciclo é desenvolvido com dados sintéticos, fakes e fixtures,
  porque as camadas de dados, ferramentas e agente ainda não estão integradas
  na linha principal. (DISCOVERED)
- **A-08**: Prazo válido de marco segue a faixa já usada no produto, de 1 a
  360 meses. (DISCOVERED)

## Rastreabilidade das fontes

| Requisito | Fonte | Classificação |
|---|---|---|
| FR-001 | pedido do usuário §2.1 | EXPLICIT |
| FR-002 | pedido do usuário §2 (só criar marco quando necessário) | EXPLICIT |
| FR-003 | pedido do usuário §2.2 | EXPLICIT |
| FR-004 | pedido do usuário §2.2 ("não invente informações ausentes") | EXPLICIT |
| FR-005 | pedido do usuário §2.2; constituição I | EXPLICIT |
| FR-006, FR-007 | pedido do usuário §2.3 | EXPLICIT |
| FR-008 | pedido do usuário §2.4 | EXPLICIT |
| FR-009 | pedido do usuário §2.3 item 4 | EXPLICIT |
| FR-010 | pedido do usuário §2.5 | EXPLICIT |
| FR-011 | pedido do usuário §2.6 | EXPLICIT |
| FR-012 | pedido do usuário §2.7; constituição IV | EXPLICIT |
| FR-013 | contratos §5; constituição I e II | EXPLICIT |
| FR-014, FR-015 | contratos §5 (códigos de erro); constituição II | EXPLICIT |
| FR-016 | contratos §6 | EXPLICIT |
| FR-017 | trilha da pessoa B §5.3 | EXPLICIT |
| FR-018 | constituição I e IX | INFERRED |
| FR-019 | pedido do usuário §2.2 + §2.6; constituição IV | INFERRED |
| FR-020 | contratos §0; constituição X | EXPLICIT |
| FR-021 | decisão Q-009-1 do `clarify` ([questoes.md](./questoes.md)) | EXPLICIT |
| FR-022 | decisão Q-009-2 do `clarify` ([questoes.md](./questoes.md)) | EXPLICIT |
| FR-023 | decisão Q-009-3 do `clarify` ([questoes.md](./questoes.md)) | EXPLICIT |
| FR-024 | decisão Q-009-4 do `clarify` ([questoes.md](./questoes.md)) | EXPLICIT |
| SC-001..SC-008 | derivados dos FR acima | INFERRED |
