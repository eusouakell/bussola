# Revisão V6 — disclosure financeiro e créditos do Grupo 07

## Evidência visual
A captura fornecida em 08/10/2026 mostra a etapa 4/6 "Orientar" em Android, com um card muito grande de "Recomendação / Base de conhecimento" com três camadas redundantes: descrição genérica, aviso educativo e marcador técnico de ciclo simulado. A decisão de UX é manter as fontes consultáveis sob demanda, sem competir com a seleção de cenários.

## Protótipo
- `ExplicacaoRecomendacao` não renderiza card, tag, cabeçalho "Recomendação" ou marcador `Resposta simulada pelo front · ciclo 003`.
- Se houver trechos consultados, renderiza um disclosure inline com `details/summary`, preservando título, fonte e texto.
- Avisos materiais seguem visíveis; são filtrados somente o marcador técnico de ciclo, um aviso educativo padrão que já está coberto pelo aviso geral, e metadados com jargão interno.
- Não altera o `ComparadorCenarios`, a lógica de recomendação, os dados ou a prestação de consentimento.
- Testes verificam estado vazio, disclosure e avisos relevantes.

## Case
- Cards com retrato **compacto** (92 px, formato circular), nome, categoria, mini bio e referência LinkedIn.
- Categorias oficiais extraídas do formulário de inscrição público do evento: **DESIGN, PRODUTO, TECNOLOGIA E DADOS**. Fonte: https://live.popcast.com.br/itau/batalha_agentes/.
- Associação às pessoas: Carlos (Produto), Kell (Design), João Paulo e Victor (Tecnologia e Dados), conforme confirmação da integrante do time. A ficha de submissão registra nomes, mas **não registra a categoria escolhida individualmente**.
- Mentora: Yasmim Mafra Maroum (grafia do perfil público), com LinkedIn verificado em https://br.linkedin.com/in/mafrayasmim.
- Links diretos disponíveis: Kell e Yasmim. Carlos, João Paulo e Victor seguem com indicação não clicável "LinkedIn: perfil a confirmar"; não reutilizar perfis homônimos sem confirmação.
- Mini bios descrevem contribuições por disciplina, sem afirmar cargos profissionais, atribuição individual de módulos ou formações não comprovadas.
- Retratos são os **assets já presentes** no projeto. Correspondência foto→nome e autorização de publicação precisam da confirmação da própria equipe antes da divulgação ampla.

## Gates
- QA automatizado: `ExplicacaoRecomendacao.test.tsx` e `case-publico.test.ts`.
- CI: lint, testes do front e build, testes gerais, Helm.
- Revisão visual humana em Android 360/390px e desktop após deploy. Prestar atenção à leitura do disclosure e dos cards no fluxo vertical.
- Merge continua sob aprovação humana; nenhuma nota 10/10 atribuída por código.
