# Bússola V7 — UX Lead + UX Designer + UX Writing

## Problema observado
Captura real no Android em 08/10/2026: uma opção de 29 meses exibia, simultaneamente, nome abstrato ("Equilibrado"), "60% da sobra típica", barra gráfica repetida, valor mensal, prazo, aviso de atraso, lista de ressalvas, CTA e sugestões de acompanhamento. A tela pedia compreensão de termos e decisões demais.

## Direção decidida
Aplicação dos critérios de Experience Designer, Accessibility Auditor e Code Reviewer da [Fábrica Agêntica](https://github.com/eusouakell/agentic-factory), com coordenação de UX Lead e revisão de UX Writing. Os contratos são referência para a revisão; não alegamos execução independente de agentes especializados.

**Princípio:** decisão em primeiro plano; consequência essencial imediatamente visível; justificativa e fontes por demanda.

## Glossário de interface
| Antes | Agora | Condição |
|---|---|---|
| Aporte (mensal) | Guardar por mês | O valor vem da ferramenta de cálculo |
| Sobra (mensal) mediana / típica | Dinheiro que costuma sobrar no mês | Explicar, nos detalhes, que é o valor central dos meses analisados |
| Compromete X% | Usa X% do dinheiro que costuma sobrar | Evitar sensação de aprovação automática |
| Viabilidade financeira | Cabe / não cabe no dinheiro disponível pelo histórico | Não misturar isso com o prazo |
| Cenário equilibrado | Plano de 29 meses | Rótulo orientado a consequência, não julgamento |
| Marco | Etapa | Preservar etapa seguinte separada |
| Categorias com corte | Onde seria preciso economizar | Gastos cortados são hipóteses, não economias efetivas |

## Mudanças implementadas
- **Comparar:** somente uma alternativa completa por vez, com 3 seletores de prazo/valor e uma CTA. A troca de opção não dispara nenhuma ação financeira.
- **Ler o plano:** valor mensal e prazo primeiro. Atraso frente à meta, insuficiência financeira e cortes obrigatórios ficam no primeiro nível.
- **Detalhar:** composição do valor, percentuais e outras consequências disponíveis em `details` (fechado inicialmente). Os números permanecem auditáveis.
- **Diagnóstico:** um valor principal (quanto costuma sobrar); renda, gastos, médias, fontes e variações detalhadas apenas se a pessoa quiser.
- **Simulação:** uma resposta principal e premissas adicionais acessíveis por demanda.
- **Outras telas:** redução de jargão em dívidas, primeiro passo, plano criado e possibilidades de economia.
- **Ação correta no momento correto:** sem sugerir avançar meses ou ativar lembretes antes da criação do plano.
- **Safety:** ferramentas financeiras, consentimento e critérios de viabilidade não foram alterados. Avisos materiais continuam fora de áreas recolhíveis.

## Verificações
- Testes de comparação: escolha única, prazo atrasado, corte adicional, percentual e comunicação em linguagem simples.
- Testes de diagnóstico: valor central preservado, fontes sob demanda e avisos de dados insuficientes.
- Testes de transição: não exibir ações de acompanhamento antes de existir plano.
- CI: lint, testes do front, testes gerais e build.
- **Pendência humana:** teste visual e assistivo em Android (320–390 px), 200–400% de zoom e leitores de tela; teste de compreensão com participantes. Não inferir nota 10/10 de CI.
- **Próxima etapa separada:** revisar o roteiro verbal do agente simulado juntamente com suas fixtures canônicas para não quebrar rastreabilidade.

## Gate de aprovação
PR apenas, sem merge automático. No review, validar o trecho equivalente ao print: Equilibrado/29 meses/R$1.037,40, troca entre alternativas, detalhe financeiro, atalhos e estado de criação do plano.
