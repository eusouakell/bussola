# Case Bússola V7 — direção de UX/UI editorial

## Diagnóstico

A narrativa V6 está mais forte, mas a execução visual ainda cai numa gramática genérica de landing page SaaS/Tailwind.

Não é um problema de Tailwind literal. É um problema de linguagem visual.

Sinais atuais no case:

- superfícies cinza-claro repetidas;
- muitos containers com cantos arredondados;
- CTAs e metadados em pills;
- navbar translúcida com blur;
- grids regulares e previsíveis;
- card dentro de card;
- hierarquia tipográfica concentrada em sans bold;
- seções com ritmo visual semelhante;
- equipe em flip cards;
- stack em chips;
- dados apresentados como tiles;
- mockups de telefone encaixados em painéis arredondados.

O resultado é funcional, mas se aproxima de template B2B/SaaS. O case precisa parecer **documentação editorial autoral de produto, dados e IA**.

## Direção

Transformar a página em um case editorial/documental:

**relatório visual + caderno de pesquisa + evidência de produto**

Princípios:

1. O conteúdo factual/editorial aprovado permanece.
2. Container só quando tiver função semântica.
3. Reduzir drasticamente cards, pills e chips.
4. Criar contraste de escala e ritmo entre seções.
5. Usar tipografia como parte da narrativa, não apenas sans bold.
6. Materialidade deve vir de evidência: extrato, ledger, anotação, tabela, commit, arquitetura, estados de interface.
7. Evitar qualquer estética “AI generic”: glow, cyberpunk, HUD, purple gradients, 3D icons, bento.
8. Não aproximar visualmente o case de um site oficial do Itaú ou de um produto bancário em produção.
9. WCAG 2.2 AA continua baseline.

## Gramática por seção

### Hero

Refazer como abertura editorial:

- headline dominante;
- subtítulo curto;
- metadados do evento em linha editorial;
- um artefato visual/financeiro ou fragmento de evidência;
- CTA textual como primário;
- sem navbar com blur;
- sem botão pill como elemento visual dominante.

### Descoberta / dados

Substituir os dois tiles por uma visualização inspirada em **extrato / ledger / anotação de análise**.

A tensão visual deve ser:

**saldo positivo ↔ uso do rotativo**

Sem reintroduzir percentuais retidos.

A nota metodológica deve parecer nota editorial, não disclaimer de rodapé genérico.

### Fernando

A imagem deve ganhar protagonismo.

- foto/persona maior;
- texto em coluna editorial;
- legenda clara: persona narrativa + imagem gerada com IA;
- sem card ao redor.

### O que construímos

Trocar os três cards iguais por uma trilha documental:

`dados → produto → agente → arquitetura → narrativa`

Quando houver evidência real, usar:
- commits;
- stack;
- arquitetura;
- fragmentos de artefatos.

Não transformar stack em pills.

### Evolução de UX

É a principal seção de craft.

Tratar como **contact sheet / spread de antes e depois**:

- pares maiores;
- menos molduras e painéis;
- rótulos Antes / Depois como metadado;
- uma decisão de UX por comparação;
- legibilidade real dos estados;
- preservar aviso de que são reconstituições.

### Protótipo

Tratar como área de demonstração/laboratório:

- iframe com contexto e limites;
- menos container genérico;
- link secundário para abrir completo;
- teclado e foco preservados.

### Equipe

Remover flip cards como padrão principal.

Usar retratos + crédito editorial visível:

- nome;
- contribuição na hackathon;
- trajetória curta;
- LinkedIn.

Nenhuma informação essencial deve exigir flip/hover.

### Fechamento

Evitar “mais uma seção com dois CTAs”.

Encerrar como colophon:

- síntese curta;
- o que foi validado;
- o que continua hipótese;
- links para código, protótipo, fontes e evolução.

## Tipografia

Criar contraste entre:

- display/editorial;
- corpo funcional;
- metadados técnicos.

Não depender apenas de peso alto + letter-spacing negativo.

Preferir uma combinação com caráter editorial e boa leitura. Se for necessário manter zero dependência externa, usar uma serif de sistema para display e sans de sistema para corpo, com escala e ritmo cuidadosamente definidos.

## Anti-padrões

Não usar:

- bento grid;
- card grid como estrutura padrão;
- pills em excesso;
- glassmorphism;
- gradients de startup;
- “AI purple”;
- ícones 3D;
- chips decorativos;
- seção = título + três cards;
- navbar com blur;
- flip card como truque;
- motion sem função.

## Escrita e UX Writing

A V7 não é desculpa para reescrever o case.

Preservar a versão editorial já aprovada e aplicar apenas:

- quebras de linha;
- labels;
- microcopy de navegação;
- legendas estritamente necessárias.

A linguagem deve continuar simples, concreta e responsável: marketing do bem, sem promessas de produto pronto, sem superlativos e sem transformar hipótese em resultado.

## Critérios de aceitação

- não parecer template Tailwind/SaaS;
- cada seção ter ritmo próprio e coerência editorial;
- narrativa e fatos da V6 preservados;
- nenhum dado confidencial reintroduzido;
- “PoC de hackathon” continua explícito;
- antes/depois legível em 320 px, 390 px e desktop;
- equipe legível sem interação;
- protótipo acessível por teclado;
- foco visível;
- reduced motion respeitado;
- revisão visual humana antes do merge.

## Fluxo de trabalho

1. Experience Design define estrutura e hierarquia.
2. Editorial Art Direction define composição, tipografia, ritmo e materialidade.
3. **KELL — DESIGN DIRECTION GATE**.
4. Codex executa no código sem inventar uma nova direção.
5. Creative Director + Accessibility review.
6. **KELL — FINAL GATE**.

O executor não deve transformar esta revisão em “trocar tokens e aumentar border-radius”. A mudança é de gramática visual, não cosmética.
