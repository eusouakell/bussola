# Bússola V5 — parecer de direção de experiência

**Escopo:** protótipo + case público no fork `eusouakell/bussola`  
**Data:** 2026-10-08  
**Status:** proposta em branch; sem merge ou publicação automáticos.

## Papéis de revisão

Esta rodada adota um modelo de **UX Lead → UX Designer → UX Writer → QA**.

- **UX Lead (coordenação da revisão):** define o problema prioritário, critérios de aceite e o que remover. Não é uma declaração de novo agente formal cadastrado no Registry.
- **Experience Designer (contrato `experience-designer` da Fábrica Agêntica):** hierarquia de decisão, divisão entre jornada e ferramentas de demonstração, opções de cenário e colapsos.
- **UX Writing (revisão de conteúdo):** textos curtos, uma ação por momento, consequências antes dos detalhes, microcopy sem promessas financeiras; o Registry não possui agente ativo específico `ux-writer`, portanto não se declara execução desse agente.
- **Accessibility Auditor / Code Reviewer / Readiness Evaluator:** critérios dos contratos registrados, verificação de semântica, regressões, código e riscos. Os testes disponíveis não equivalem a certificação WCAG.

## Diagnóstico baseado no código e na observação das páginas

| Prioridade | Problema identificado | Evidência | Resolução |
|---|---|---|---|
| P0 | Bastidores abrem no desktop, desviando espaço da conversa | `App.tsx`: estado inicial `painel=true` | `false` como padrão; acesso continua no cabeçalho |
| P0 | Azul domina a experiência mesmo após redesign do case | `app.css`: `#02036c` em tokens, fundo dinâmico e estado visual | Paleta clara neutra no protótipo, preto legível e laranja reservado às ações |
| P0 | Badge do comparador se sobrepõe ao limite superior | `app.css`: `.rec-flag { position:absolute;top:-15px }` | Badge no fluxo do card |
| P0 | Cards comprimidos nos 3 cenários em larguras variáveis | `.grid-cen`: três colunas fixas até breakpoint por viewport | Grid responsivo por tamanho mínimo de coluna |
| P1 | Tela de entrada apresenta mais explicação do que decisão | `BoasVindas.tsx` com título, descrição longa, ícone, quatro opções, aviso | Pergunta principal, quatro rótulos curtos e aviso mínimo |
| P1 | Percentual do medidor podia representar só parcela-base | `ComparadorCenarios.tsx`: barra de `pct_capacidade`, excluindo cortes | Mostrar a proporção total quando é derivável; divulgar os cortes necessários |
| P1 | Case repete premissas e notas técnicas ao longo de 8 seções | `web/public/case/index.html` V4 | Reconstrução editorial curta; fontes e limites em disclosure final |

## Critérios de aceite objetivos

1. **Case:** apenas um H1; fotos reais acessíveis; sem fundo azul; links internos sem âncoras quebradas; conteúdo editorial visivelmente mais curto; documentos internos não publicados.
2. **Protótipo:** Bastidores continuam acessíveis, mas fechados inicialmente; quatro objetivos continuam enviando as intenções originais ao agente; grids não forçam três cartões quando não há espaço.
3. **Responsabilidade financeira:** valor de cortes nunca desaparece; proporção total não é confundida com contribuição-base; detalhes ficam disponíveis em `details`.
4. **Técnico:** testes do case, welcome, cenários, lint/build e CI aprovados.
5. **Visual:** inspeção humana em desktop, 390px e 320px, contraste, navegação por teclado e zoom/reflow. **Sem afirmar ausência total de sobreposição até a verificação renderizada.**

## O que não alteramos nesta rodada

- O modelo de IA, contratos de tools e cálculo do agente.
- A lógica de recomendação e elegibilidade (ainda requer trabalho específico).
- Scorecard de usabilidade: a nota inicial não foi promovida a 10/10.
- Critérios canônicos da Fábrica Agêntica: os contratos foram consultados como método, sem promover agentes ou conceder novas permissões.

**Gate humano:** aprovação de UX / merge na branch; publicação só após o workflow Pages na `main`.
