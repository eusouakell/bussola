# Bússola — revisão UX/UI e editorial V4

Data: 2026-10-08. Escopo: protótipo `web/src/` e página pública `web/public/case/`.

## Decisão de direção

- **Case**: apresentação editorial minimalista, inspirada em ritmo tipográfico e espaço negativo de páginas de produto da Apple, **sem replicar sua identidade**.
- **Protótipo**: preservar a linguagem Bússola / Dynamic Glass e melhorar leitura, progressão e controles.
- **Fundamento compartilhado**: usar [Fluent 2 — layout](https://fluent2.microsoft.design/layout), [typography](https://fluent2.microsoft.design/typography/), [content design](https://fluent2.microsoft.design/content-design), [accessibility](https://fluent2.microsoft.design/accessibility) e [design tokens](https://fluent2.microsoft.design/design-tokens) como referências abertas, sem importar o kit ou componentes da Microsoft.
- Não criar nova fonte, dependência, variante canônica do DS ou política de recomendação financeira silenciosamente.

## Roteamento pelos contratos da Fábrica Agêntica

Contratos consultados no repositório `eusouakell/agentic-factory`. Esta revisão **aplica suas competências, guardas e critérios como método de trabalho**; não afirma execução autônoma, promoção de agentes nem testes humanos que não ocorreram.

| Contrato | Contribuição / evidência | Gate |
|---|---|---|
| `experience-designer` (pilot) | Diagnóstico: distinção entre viabilidade e prazo; disclosure de consequências e redução da informação simultânea nos cenários | Validar decisão de UX antes de produção |
| `editorial-art-director` (pilot) | Uma ideia dominante: narrativa monumental com grande tipografia, espaços generosos, fundos neutros e imagens documentais apenas nos créditos | Aprovação da direção visual |
| `editorial-typography-director` (pilot) | Font stack nativa com fallbacks, escala responsiva, hierarquia tipográfica e diacríticos pt-BR | Sem substituição de fonte canônica |
| `flame-ui-composer` (active) | Case com CSS próprio e protótipo usando tokens de marca existentes, sem inventar novo DS | Aprovação da composição |
| `frontend-engineer` (active) | Código/estilos/testes apenas nesta branch | PR + CI |
| `accessibility-auditor` (pilot) | Inspeção estática: semântica de títulos, foco, reflow, links e imagens. **Não é teste com leitor de tela** | Auditoria assistiva independente antes de afirmar WCAG |
| `code-reviewer` (active) | Escopo reduzido, sem motores financeiros ou mudança de contratos/rotas | Revisão de PR |
| `readiness-evaluator` (active) | Síntese de CI e problemas pendentes, sem autodeclaração de nota 10/10 | Aprovação humana de merge e divulgação |

## Achados e soluções

| Superfície | Antes | Mudança V4 | Verificação |
|---|---|---|---|
| Case — hero | Grande fundo azul, círculo decorativo e várias superfícies glass | Hero claro, headline dominante, uma CTA e contraste tipográfico | Conferir mobile/desktop visualmente |
| Case — scorecard | Nove barras concorrendo visualmente com história e lições | Nota de baseline permanece visível; dimensões completas abertas por `details/summary` | Gate automatizado de existência de summary |
| Case — créditos | Fotos e papéis do time | Retratos preservados, com alt; sem imagens inventadas | Gate de 5 assets reais |
| Protótipo — cenários | Badge de prazo baseado só em `viavel` podia induzir interpretação errada | Prazo comparado explicitamente ao prazo desejado, sem confundir viabilidade financeira | Teste de regressão `ComparadorCenarios.test.tsx` |
| Protótipo — sobrecarga | Trade-offs acumulados na coluna de decisão | Detalhes secundários em `details`; valor mensal/cortes no primeiro plano | Inspeção visual pendente |
| Protótipo — copy | Mensagem inicial longa; orientação creditava normas públicas sem prova visível | Saudação concisa, decisão mais clara e fonte contingente às evidências expostas | Testes existentes, revisão editorial |

## Critérios de aceite

1. Lint, build, testes unitários e gate do case aprovados no GitHub Actions.
2. Sem referências quebradas a retratos e âncoras internas.
3. Nenhum novo pacote, font proprietário ou alteração de contrato do agente.
4. PR documenta limites da avaliação, sem alegar WCAG 2.2 AA integral.
5. Conferir visualmente `/bussola/` e `/bussola/case/` em 320px, 390px e desktop, por teclado; revisão humana antes do merge.

## Pendências explícitas

- Testes assistivos com leitor de tela, 400% zoom e cenário de teclado completo.
- Validação com pessoas de compreensão financeira e consentimento.
- Regras do agente real para oferecer o prazo solicitado com folga financeira; não resolvidas por ajuste de copy.
- Publicação depende do merge na `main` e de workflow Pages bem sucedido.
