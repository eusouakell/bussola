# V7 — Creative Director + UX Writing Review

Implementação local na branch design/case-v7-editorial-ui, a partir de a1d44e9. Sem nova rota, publicação, push ou merge.

## Evidências visuais

| Largura | V6 | V7 |
|---|---|---|
| Desktop · 1440 px | [V6](v6-1440.png) | [V7](v7-1440.png) |
| 390 px | [V6](v6-390.png) | [V7](v7-390.png) |
| 320 px | [V6](v6-320.png) | [V7](v7-320.png) |

Detalhes: [abertura desktop](v7-1440-hero.png), [abertura 320 px](v7-320-hero.png), [Fernando 390 px](v7-390-fernando.png), [descoberta desktop](v7-1440-descoberta.png), [UX 390 px](v7-390-evolucao.png), [equipe 320 px](v7-320-pessoas.png).

## Comparação com a V6

- Hero: abertura serif, links textuais, cabeçalho opaco no fluxo. Metadado aprovado inclui Batalha de Agentes Itaú, Google Cloud e SantoDigital.
- Descoberta: registros separados por fios, observação qualitativa e nota metodológica próxima. Relação verbal “saldo positivo / mesmo com / uso do rotativo”; nenhum percentual retido foi acrescentado.
- Fernando: retrato sintético amplo, sem moldura arredondada, com legenda de imagem gerada com IA. Altura responsiva corrigida após inspeção.
- Processo: trilha documental e lista técnica em linhas. Arquitetura vinculada ao documento existente no commit de referência, com limite explícito; não foi criado diagrama conceitual.
- UX: quatro comparações maiores. Desktop lado a lado; 390 e 320 px empilhadas. Reconstituições e textos internos preservados; aviso também antes dos pares.
- Protótipo: iframe sem painel decorativo e link externo disponível. Limites da PoC permanecem antes da demonstração.
- Equipe: quatro créditos visíveis e mentoria identificada. Contribuições e trajetórias completas; flip removido.
- Fechamento: links textuais e fontes/limites expostos, sem exigir expansão.

## Escrita e provenance

Todos os headings da V6 foram preservados, inclusive os títulos das trajetórias. Os parágrafos factuais/editoriais permanecem.

Exceções delimitadas: metadado institucional aprovado; orientação “Vire os cartões…” substituída para refletir créditos sempre visíveis; “A foto do Fernando…” passou a “A imagem do Fernando…”. Adições são labels, referências e legendas de limite.

Continuam explícitos: base sintética de 1.000 usuários; Fernando como persona narrativa; caráter coletivo da hackathon; refinamento posterior; reconstituições; lógica de recomendação, revogação e testes assistivos pendentes. Nenhum resultado de uso financeiro foi acrescentado.

## Tipografia

Stack serif sem dependência externa: Palatino Linotype, Book Antiqua, Palatino, Noto Serif, Georgia, serif. A inspeção do navegador confirmou Palatino Linotype neste Windows; Georgia permanece alternativa de fallback.

Sans de sistema para leitura e Consolas/monoespaçada de sistema para metadados técnicos. As capturas mostram a combinação; renderizações em outros sistemas ainda podem variar.

## QA

- Suíte front/BFF: 53 arquivos, 534 testes passaram.
- Após preservar títulos das trajetórias: 6 testes do case passaram novamente.
- Lint, compilação e varredura de bundle passaram.
- Nenhuma imagem local quebrada nem âncora local sem destino.
- Sem overflow horizontal em 1440, 390 e 320 px.
- Skip link recebeu foco por Tab e navegou para o conteúdo.
- Links do índice navegaram para os quatro destinos.
- Reduced motion resultou em scroll sem animação.
- Créditos profissionais permanecem visíveis sem interação.
- Axe: 20 regras passaram por largura; uma ocorrência de contraste insuficiente no botão branco/laranja do estado “Antes” de legibilidade, preservado como evidência histórica. Não corrigir silenciosamente a reconstituição.
- Axe também deixou verificações inconclusivas. Não equivale a aprovação WCAG 2.2 AA.
- Inspeção visual realizada sobre abertura, descoberta, UX, equipe e retrato sintético, incluindo mobile.

[Dados da inspeção no navegador](qa-render.json).

## Limites da revisão

Capturas geradas a partir de arquivos locais com assets locais. Não comprovam publicação no Pages nem execução de toda a jornada do protótipo remoto. Entrada/saída por teclado no iframe remoto e teste com leitor de tela continuam pendentes.

A instalação pelo lockfile informou uma vulnerabilidade alta nas dependências existentes. Nenhuma atualização de dependências foi feita nesta revisão visual.

## Gate

CREATIVE DIRECTOR + UX WRITING REVIEW

Aguardando revisão humana da composição, da combinação tipográfica e da precisão dos labels. Não fazer merge.
