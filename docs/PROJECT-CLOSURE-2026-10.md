# Encerramento do projeto Bússola — outubro de 2026

**Estado editorial/operacional:** desenvolvimento encerrado por decisão da mantenedora em 18/10/2026.  
**Natureza:** prova de conceito colaborativa de hackathon, documentação e experimento de UX/Context Engineering; não é produto em operação.

## O que fica concluído

- A participação e a documentação do projeto desenvolvido para a Batalha de Agentes.
- O fork de Kell como registro de seus trabalhos em estratégia, pesquisa, UX/UX Writing, contexto, Responsible AI e narrativa, com créditos coletivos e procedência preservados.
- As integrações já incorporadas a `main`, incluindo `planejar_marcos` do PR #15, ficam arquivadas no código.
- As revisões e testes experimentais de landing page permanecem visíveis no histórico do Git, sem reivindicação de aprovação visual final.

## O que foi descontinuado

- Evolução do protótipo e redesign da landing page/case público.
- Releases do protótipo por GitHub Pages e deploy/promoção em Google Cloud por Actions.
- Dependências externas e trabalho planejado da reestruturação V3; PR #14 deve ser fechado sem merge como **not planned**, com referência a este encerramento.
- Atualizações editoriais ou métricas decorrentes de novas iterações do produto.

## Limites e propriedade intelectual

- Manter autoria coletiva, créditos e vínculos a contribuições verificáveis.
- Não caracterizar o protótipo como serviço bancário, produto validado em produção, resultado de experimento controlado ou caso com resultados medidos.
- Não republicar dados ou materiais não autorizados do hackathon.
- Não alterar repositórios de outros colaboradores.
- Preservar fonte, docs, PRs, decisões e assets do fork como arquivo histórico.

## Passos para concluir a retirada pública

1. Fazer merge do PR de encerramento e verificar que os workflows de publicação `static-demo-pages.yml`, `deploy.yml` e `promote.yml` não existem mais na `main`. O CI pode permanecer como registro de testes.
2. **Desativar GitHub Pages manualmente em Settings → Pages**, para retirar de fato `https://eusouakell.github.io/bussola/` e suas rotas `/case/` e `/auditoria/`. A remoção de workflows **não** derruba uma implantação já publicada.
3. Conferir eventuais serviços Google Cloud/Cloud Run fora do fork: cancelar recursos remanescentes somente após checar titularidade, permissões e custos. GitHub não comprova sua situação atual.
4. Em Settings → General → Danger Zone, escolher **Archive this repository** após confirmar a retirada pública. Arquivamento é reversível por administradores; não exclui o código ou histórico.
5. Marcar as referências externas de portfólio como **case arquivado**, sem apontar para uma landing page que não estará disponível.

## Prioridade posterior

Concentrar a produção em Cereja Flamejante e em uma oferta inicial monetizável. Nenhum novo sprint Bússola está previsto. Trabalho posterior exigirá decisão explícita de reabertura, e não será criado implicitamente por automações.

---
Este registro documenta a intenção de encerramento; ações em Settings, a retirada da hospedagem e o arquivamento só podem ser marcados como concluídos após verificação direta.
