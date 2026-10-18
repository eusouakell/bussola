# Encerramento do projeto Bússola — outubro de 2026

**Decisão:** desenvolvimento concluído pela mantenedora em 18/10/2026. O protótipo simulado segue público; a landing page do case sai de publicação. Esta decisão corrige o escopo anterior do PR #16, que havia proposto desativar o GitHub Pages por inteiro.

## Estado pretendido

| Superfície | Estado |
|---|---|
| `https://eusouakell.github.io/bussola/` | Manter disponível como demonstração estática com dados sintéticos |
| `https://eusouakell.github.io/bussola/case/` | Retirar do artefato GitHub Pages; preservar HTML e assets no Git |
| `https://eusouakell.github.io/bussola/auditoria/` | Preservar como documentação histórica |
| `main` e histórico Git | Preservar código, PRs, documentos, equipe e créditos |
| Cloud Run / serviços GCP | Não manter como parte do protótipo estático; recursos externos exigem conferência independente |

## Decisões técnicas

1. Restaurar **somente** o workflow de GitHub Pages (`.github/workflows/static-demo-pages.yml`), que testa, faz lint e publica o build do modo `simulado` com `VITE_BUSSOLA_MODO=simulado`, `VITE_BUSSOLA_LOGIN=FALSE` e base `/bussola/`.
2. Após `npm run build`, remover `dist/case` do **artefato publicado** e conferir `dist/index.html`. Não apagar `web/public/case` do repositório: sua presença é histórico, não obrigação de manter a página no ar.
3. Manter desativados os workflows de deploy/promoção do GCP. Não permitir que scripts de publicação estática usem segredos da nuvem.
4. README aponta para o protótipo ativo, não para a LP rejeitada. A revisão visual V3 PR #14 permanece encerrada sem merge, e a integração de marcos PR #15 fica registrada no histórico.
5. Projeto concluído não significa sistema financeiro de produção nem evidência de economia de tempo mensurada. Manter autoria e créditos coletivos; evitar republicar dados restritos.

## Critérios para encerrar as pendências

- [ ] PR corretivo aprovado e integrado à `main`.
- [ ] Job de GitHub Pages executado com sucesso na `main` e novo artefato implantado.
- [ ] Protótipo `/bussola/` carregando e com jornada simulada funcional.
- [ ] Rota `/bussola/case/` não entrega mais a landing page rejeitada (testar em janela anônima para evitar cache).
- [ ] Auditoria `/bussola/auditoria/` permanece acessível, se antes publicada.
- [ ] Se desejar arquivar o repositório, fazê-lo **somente depois** de verificar a implantação final. Arquivamento torna código e configurações somente leitura, impedindo novos ajustes até reabrir o repositório.

**Importante:** Não usar **Unpublish site**, não desligar GitHub Pages e não alterar a visibilidade do repositório para privado apenas para esconder o case. Essas ações podem indisponibilizar também o protótipo.

## Prioridade posterior

Nenhuma evolução funcional ou sprint da Bússola está prevista. O foco editorial e comercial passa para a Cereja Flamejante; manter o protótipo como evidência navegável, sem trabalhos de redesign.
