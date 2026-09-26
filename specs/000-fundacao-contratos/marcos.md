# Marcos — ciclo 000 (Fundação e contratos)

Checado em 2026-09-26, antes do Step 5 (trilha A, regra 4).

| Marco | Necessário para o 000? | Estado | Modo |
|---|---|---|---|
| — | Não. O 000 não depende de nenhum marco (000 §6; trilha A §4.1) | — | sem dependências |

Este ciclo **entrega** o S0: merge do 000 em `main` + tag `contratos-v1`
(checagem: `git ls-remote --tags origin contratos-v1`).

## Pré-condições externas (não são marcos)

| Item | Dono | Estado em 2026-09-26 | Efeito |
|---|---|---|---|
| Credenciais GCP do integrante (ADC) | Pessoa A | pendente (`gcloud` instalado; login do usuário) | tarefas GCP e `make fixtures` aguardam |
| Pedidos ao owner (mestre §16) | Pessoa B envia | não enviados | define Plano A/B |
| Q4 (canal da demo) | Pessoa B confirma | aberta | gate do merge (trilha A §4.1) |
