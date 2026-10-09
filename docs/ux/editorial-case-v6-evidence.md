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
- **Accessibility Auditor:** controles de flip são botões reais, têm foco e atributos `inert` nas faces ocultas; oferecer redução de movimento. Não declarar aprovação WCAG sem inspeção com assistivos.
- **Readiness Evaluator:** preparar PR em modo draft e apontar fontes/limites para revisão antes de divulgar.

## Fontes de fato: rastreabilidade

| Afirmativa do case | Evidência | Status |
|---|---|---|
| Segmentação por saldo negativo, dívida formal e rotativo; 4 perfis | Drive: `Personas de Clientes - Agente de Saúde Financeira.docx`, autoria registrada de Carlos, 26/09/2026; `Proposta de Negócio — Bussola` | **Revisar autorização de divulgação** de agregados derivados da base |
| 1.000 usuários sintéticos e Fernando como personagem narrativo | Proposta de Negócio e Racional de Prototipação, 26/09 | Confirmado como dado de projeto; **não** extrapolar |
| ADK + Gemini / BigQuery / RAG / Cloud Run / Secret Manager | Documento Explicativo de Arquitetura do Drive e commits do período do evento | Arquitetura documentada; implementação individual varia |
| Victor: arquitetura, integração, RAG, governança e BigQuery | Commits de `theguitarvity` no repositório até 27/09; exemplos `85cd9d25c` (BigQuery real), `4ade78407` (Model Armor), `723194057` (corpus) | Provado no histórico técnico |
| João: agente, contratos e deploy | Commits de `joaopaulodevv` em 27/09: `df8cd6b11` (deploy), `1104e9d0b` (simulação), `9fea0312e` (catálogo) | Provado no histórico técnico |
| Fotos do time | Arquivos nomeados e fornecidos na conversa, em `web/public/case/assets` | Quatro WebPs decodificavam; retrato da mentora foi corrigido com a fonte original fornecida |
| Foto de Fernando | Drive `06 — Pitch final/Fernando em fotos/1.png`, criada no projeto | Incluída como `fernando-persona-ai.png`, rotulada imagem gerada com IA |
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

Duas comparações de celular lado a lado (entrada e cenários) são **reconstituições visuais baseadas no código/roteiro**, e levam aviso explícito. Ainda não são capturas reais das versões executadas. Substituir por screenshots verificáveis, caso sejam recuperadas; não alterar silenciosamente a legenda.

## Gates antes do merge/publicação

1. **Autorização para divulgar números derivados da base sintética** (40,8%, 26,5%, 22,5%, 10,2%). O regulamento original pode limitar divulgação de informação acessada no hackathon mesmo após seu término. Se não houver liberação, remover a distribuição e reter apenas a narrativa sem percentuais.
2. **Confirmação dos cinco retratos e permissão de uso público**. Arquivos têm nomes individuais, mas a extração do LinkedIn foi bloqueada.
3. **Aprovar cargo/título de cada mini-bio**, em especial Carlos (cargo no LinkedIn por indexação), João (estudante / laboratório) e Yasmim (posição atual).
4. **Revisão visual humana:** duas telas de 320px e 390px; desktop; scroll horizontal dos mockups; cartões flip por teclado, touch e leitor de tela; ausência de sobreposições.
5. **CI verde:** testes de links, imagens reais, stack, telas e compilação. Não confundir CI verde com teste de experiência em produção.

Não há placeholders intencionais, mas os itens 1–4 ainda são decisões e validações reais de publicação.
