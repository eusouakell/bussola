# Case unificado V6 — revisão editorial, autoria e publicação

**Branch:** `case/unificado-v6-data-story`  
**Estado:** revisão humana obrigatória; não publicar antes dos gates.

## Tese editorial escolhida

**O saldo estava no azul. A dívida, fora de vista.**

Uma equipe multidisciplinar investigou os dados sintéticos do desafio e descobriu que pessoas que nunca ficavam no vermelho ainda podiam pagar rotativo no cartão. O insight direcionou a Bússola para **orientação contextual antes de ofertas**. Depois da hackathon, o código e a interface foram refinados para explicar a decisão com mais clareza.

### Debate editorial por papéis — revisão analítica, não execução autônoma

- **UX Lead:** exigir uma experiência editorial única, sem página paralela de diagnóstico; mostrar na ordem descoberta → criação → evolução → evidência → pessoas; a separação anterior enfraquecia a história.
- **Experience Researcher:** não extrapolar a amostra sintética. A segmentação tem 1.000 registros, definidos por sinais transacionais, não por gênero, idade ou região; Fernando é uma persona *narrativa*.
- **UX Writer:** evitar `o agente revolucionou as finanças`, `plano perfeito` e `a IA conhece você`. Usar sujeitos, verbos e condições observáveis. A headline é expressiva sem transformar hipótese em garantia.
- **Editorial Art Director / UX Designer:** dispositivos lado a lado, mesmo tamanho, rótulos Antes/Depois; cards reviráveis apenas onde adicionam valor; contraste do código antigo aparece somente nos telefones `Antes`.
- **Accessibility Auditor:** controles de flip são botões reais, têm foco e atributos `aria-hidden` alternado nas faces ocultas; oferecer redução de movimento. Não declarar aprovação WCAG sem inspeção com assistivos.
- **Readiness Evaluator:** preparar PR com aprovação humana obrigatória e apontar fontes/limites para revisão antes de divulgar.

## Fontes de fato: rastreabilidade

| Afirmativa do case | Evidência | Status |
|---|---|---|
| Segmentação por saldo negativo, dívida formal e rotativo; 4 perfis | Drive: `Personas de Clientes - Agente de Saúde Financeira.docx`, autoria registrada de Carlos, 26/09/2026; `Proposta de Negócio — Bussola` | **Revisar autorização de divulgação** de agregados derivados da base |
| 1.000 usuários sintéticos e Fernando como personagem narrativo | Proposta de Negócio e Racional de Prototipação, 26/09 | Confirmado como dado de projeto; **não** extrapolar |
| ADK + Gemini / BigQuery / RAG / Cloud Run / Secret Manager | Documento Explicativo de Arquitetura do Drive e commits do período do evento | Arquitetura documentada; implementação individual varia |
| Victor: arquitetura, integração, RAG, governança e BigQuery | Commits de `theguitarvity` no repositório até 27/09; exemplos `85cd9d25c` (BigQuery real), `4ade78407` (Model Armor), `723194057` (corpus) | Provado no histórico técnico |
| João: agente, contratos e deploy | Commits de `joaopaulodevv` em 27/09: `df8cd6b11` (deploy), `1104e9d0b` (simulação), `9fea0312e` (catálogo) | Provado no histórico técnico |
| Fotos do time | Arquivos nomeados e fornecidos na conversa, em `web/public/case/assets` | Quatro WebPs decodificavam; retrato da mentora foi corrigido com a fonte original fornecida |
| Foto de Fernando | Drive `06 — Pitch final/Fernando em fotos/1.png`, criada no projeto | Incluída como `fernando-ai.png`, rotulada imagem gerada com IA |
| Trabalho posterior de UX | PRs #4, #5, #7, #8, independentes da entrega original | Links públicos de diff e testes |

## Mini-bios — fontes públicas verificadas por indexação

Os quatro links do LinkedIn retornaram bloqueio automatizado (HTTP 999), mas indexação pública suporta descrições **sem inventar promoções ou prêmios**:

- [Carlos Guevara](https://www.linkedin.com/in/carlosreisguevara/): MSc COPPEAD, estratégia de produto, growth e experiência em CX de produtos com IA; a participação em criação das personas é documentada no Drive.
- [Kell Bonassoli](https://www.linkedin.com/in/eusouakell): Design, UX Writing e Context Engineering; participação no projeto e revisão pós-evento como dona do fork.
- [João Paulo Soares Lopes](https://www.linkedin.com/in/joao-paulo-so-lopes/): estudante de Engenharia de Computação, PUC-Rio, vínculo AISE Lab, foco em engenharia de software e backend. A página do AISE Lab também o descreve.
- [Victor Lucas Lopes](https://www.linkedin.com/in/victorllsilvdev/): especialista em Arquitetura de Software na Vivo, atuação com sistemas distribuídos e IA. GitHub `theguitarvity` traz currículo e commits.
- [Yasmim Mafra Maroum](https://www.linkedin.com/in/mafrayasmim/): cientista de dados coordenadora, dados e crédito; mentoria registrada na ficha de submissão.

**Limite:** não houve extração de imagens do LinkedIn. O mapeamento de retratos está baseado nos nomes dos arquivos originais compartilhados, não em reconhecimento facial. A confirmação de direitos/identificação dos retratos permanece responsabilidade dos respectivos titulares.

## Antes/depois no case

Quatro comparações de celular lado a lado (entrada, cenários, consentimento e legibilidade) são **reconstituições visuais baseadas no código/roteiro**, e levam aviso explícito. Ainda não são capturas reais das versões executadas. Substituir por screenshots verificáveis, caso sejam recuperadas; não alterar silenciosamente a legenda.

## Gates antes do merge/publicação

1. **Percentuais retirados da página pública por precaução editorial.** Os agregados permanecem na documentação interna para rastreabilidade, mas a publicação dos números depende de autorização explícita sob o regulamento do evento. A narrativa pública utiliza somente o insight qualitativo.
2. **Retratos: confirmação informada pela autora em 09/10/2026.** Ela declarou ter confirmado com os participantes a identificação e o uso das fotografias. Não houve verificação independente dos consentimentos; manter o registro dessa confirmação.
3. **Aprovar cargo/título de cada mini-bio**, em especial Carlos (cargo no LinkedIn por indexação), João (estudante / laboratório) e Yasmim (posição atual).
4. **Revisão visual humana:** duas telas de 320px e 390px; desktop; scroll horizontal dos mockups; cartões flip por teclado, touch e leitor de tela; ausência de sobreposições.
5. **CI verde:** testes de links, imagens reais, stack, telas e compilação. Não confundir CI verde com teste de experiência em produção.

Não há placeholders intencionais, mas os itens 1–4 ainda são decisões e validações reais de publicação.

## Inspeção visual preliminar (preview HTML)

Uma revisão via navegador em um proxy de preview HTML da branch observou os **quatro pares de celulares lado a lado e sem sobreposição no desktop**. No entanto, a reprodução pelo proxy não foi conclusiva para:

- carregamento da foto do Fernando (arquivo PNG existe na tree do GitHub e foi obtido do Drive);
- foto da mentora, que fica separada da grade principal; o navegador não percorreu completamente o rodapé para confirmar sua exibição;
- animação e estado acessível dos cards de verso;
- viewport 390px / 320px, não testável na sessão.

**Não afirmar QA mobile concluído.** A observação automática chamou indevidamente a quinta pessoa de “Maria”; o crédito correto e documentado é **Yasmim Mafra Maroum**, como está no HTML. Os testes estáticos validam os cinco arquivos locais, mas não substituem inspeção da renderização no Pages após merge.


## Situação dos problemas prioritários (P0/P1)

A V6 reúne as evidências na experiência narrativa e demonstra os quatro pares de estados. É incorreto afirmar que *todas as pendências técnicas* foram eliminadas pelo case. Estado de controle:

| Critério | Situação | Evidência ou próximo gate |
|---|---|---|
| Página única com protótipo e prova visual | Implementado na branch, CI pendente | `web/public/case/index.html` + iframe `/bussola/` |
| Quatro pares de mockups móveis lado a lado | Implementado como reconstituição, não captura real | 8 telas desenhadas com HTML e aviso editorial |
| Eliminar sobreposições da página | Layout responsivo aplicado, revisão mobile pendente | Inspeção visual desktop/320/390 px após build |
| Fotos da equipe e Fernando | Retratos dos participantes: confirmação de autorização informada pela autora em 09/10/2026; Fernando: imagem sintética identificada | WebPs no repo + PNG do Drive |
| Texto conciso e precisão financeira | Revisado; interface real segue PRs anteriores | Conferir cálculo, consentimento, fluxos completos |
| Cenários financeiros atendem preferências do usuário | **Pendente** | Validação da lógica do agente, não apenas copy |
| Revogação efetiva de consentimento | **Pendente** | Integrar controle real ou não prometer revogação |
| Teste assistivo e compreensão com usuários | **Pendente** | WCAG 2.2 AA, leitor de tela, teclado, zoom e testes com participantes |
| Publicação de cifras da base | **Não publicadas na página** | Manter agregados somente no material de trabalho até autorização explícita |

A navegação pública de auditoria pode permanecer como registro histórico do código, mas a narrativa e as demonstrações do produto precisam ser consultáveis na única URL do case.

## Revisão editorial — 09/10/2026

- **Enquadramento aprovado pela autora:** case de uma prova de conceito produzida em hackathon, seguida por refinamento posterior de UX e escrita. Não representar a Bússola como serviço bancário em produção.
- **Privacidade dos dados do evento:** substituição da taxa de 40,8% na página pública por descrição qualitativa do uso do rotativo mesmo com saldo positivo. Os percentuais detalhados continuam neste documento de evidência para controle editorial, sem aprovação de divulgação.
- **Retratos:** autora informou ter confirmado com os participantes a identificação e autorização de uso público das imagens; títulos e mini-bios continuam baseados em fontes públicas e sujeitos à validação de atualização.
- **Precisão técnica:** trocar promessas categóricas sobre o agente por formulações relativas ao que a PoC explorou; não declarar recomendação validada, revogação real de consentimento nem conformidade assistiva.
- **Autoria:** distinguir trabalho coletivo entregue na hackathon do refinamento de UX e conteúdo realizado depois do evento.
- **Evidência visual:** preservar o rótulo de reconstituições editoriais enquanto não houver screenshots verificáveis. QA responsivo/assistivo e estado do CI ainda precisam ser conferidos.
