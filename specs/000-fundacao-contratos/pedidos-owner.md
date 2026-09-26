# Pedidos ao owner (Bloco 0)

Fonte: [contexto mestre §16](../../docs/contexto-spec-master.md) e
[000 §3](../../docs/ciclos/000-fundacao-contratos.md). Atende ao FR-024.

- **Destinatário:** `andre.favretto@santodigital.com.br` (owner do projeto
  `batalha-time-07-lkbv`) ou mentores com Storage/Secret Admin.
- **Quem envia:** a Pessoa B ([roadmap de 2 pessoas](../../docs/ciclos/roadmap-2-pessoas.md)).
  O agente não envia mensagens.
- **Quem atualiza este arquivo:** quem enviar, a cada resposta recebida.

## Status

| # | Pedido | Status | Enviado em | Resposta |
|---|---|---|---|---|
| 1 | Service Account de runtime com 6 papéis | A enviar | — | — |
| 2 | Template de Model Armor `bussola-guard` | A enviar | — | — |
| 3 | Bucket `batalha-time-07-lkbv-bussola` com Storage Object Admin | A enviar | — | — |
| 4 | Confirmar `allUsers` como invoker no Cloud Run | A enviar | — | — |

Valores de status: `A enviar`, `Enviado`, `Atendido`, `Negado`, `Sem resposta`.

## Decisão Plano A/B

- **Decisão atual:** **Plano B** (provisória), até a resposta do item 1.
  O ciclo 000 deixa os dois caminhos prontos:
  - `deploy/deploy.sh` aceita a SA de runtime por variável. O padrão é a SA
    default de compute; basta trocar para `bussola-runtime` no Plano A;
  - `deploy/iam_datasets.sh` aplica o IAM de dataset do Plano B, com
    confirmação humana;
  - `BQ_MODO_LEITURA` e o fallback da Gemini API cobrem a ausência de
    `jobUser` e de `aiplatform.user`.
- **Regra de decisão:**
  - item 1 atendido antes do deploy do 003 → **Plano A** para BigQuery e
    LLM;
  - item 1 negado ou sem resposta até lá → **Plano B** fica definitivo;
  - item 2 negado → guardrails só com callbacks do ADK e safety settings
    (005 sem Model Armor);
  - item 4 negado → o 007 publica o canal com autenticação (token de identidade)
    em vez de `allUsers`.
- **Registro:** quem receber a resposta atualiza a tabela acima, esta seção
  e `docs/contexto-spec-master.md` §20 (Q7).

## Mensagem pronta para envio

> **Assunto:** Batalha Agentes, Time 07: pedidos de acesso para o projeto
> `batalha-time-07-lkbv`
>
> Olá, André. Somos o Time 07 e estamos construindo a Bússola, um agente de
> planejamento financeiro sobre `hackathon_dados.extrato_sintetico`. Para
> rodar a solução no Cloud Run com o menor privilégio possível, precisamos de
> quatro itens que o nosso papel no projeto não permite fazer:
>
> 1. **Service Account de runtime.** Criar uma SA nova (sugestão:
>    `bussola-runtime`) ou conceder à SA default de compute
>    (`1061873050224-compute@developer.gserviceaccount.com`) os papéis:
>    - `roles/aiplatform.user` (Gemini via Vertex);
>    - `roles/bigquery.jobUser` (consultas);
>    - `roles/bigquery.dataViewer` (leitura dos dados);
>    - `roles/secretmanager.secretAccessor` (segredos em runtime);
>    - `roles/modelarmor.user` (guardrails);
>    - `roles/logging.logWriter` (logs estruturados).
>
>    Se for uma SA nova, pedimos também `roles/iam.serviceAccountUser` sobre
>    ela para o time, para podermos fazer o deploy com ela.
> 2. **Template de Model Armor** (sugestão: `bussola-guard`, em
>    `us-central1`), criado por quem tem `modelarmor.admin`, com filtros de
>    prompt injection/jailbreak, dados sensíveis e conteúdo nocivo.
> 3. **Um bucket** (sugestão: `batalha-time-07-lkbv-bussola`, em
>    `us-central1`) com `roles/storage.objectAdmin` para o time. Ele habilita
>    `gcloud run deploy --source`, Cloud Build e staging.
> 4. **Confirmação de política:** é permitido conceder `allUsers` como
>    invoker (`roles/run.invoker`) em um serviço Cloud Run, para o canal
>    público da demo? O servidor MCP continua privado em qualquer caso.
>
> Se algum item não puder ser atendido, temos um plano alternativo com os
> papéis atuais do time; só precisamos saber para seguir por ele.
>
> Obrigado!
> Time 07

## Plano B (sem os pedidos)

Tudo abaixo funciona com os papéis atuais do time (mestre §5 e §16):

| Área | Plano A (com pedidos) | Plano B (sem pedidos) | Custo do Plano B |
|---|---|---|---|
| BigQuery | SA de runtime com `jobUser` + `dataViewer` | O time concede `dataViewer` em `bussola_dados` e `dataEditor` em `bussola_app`/`bussola_app_dev` à SA default, no nível de dataset (`deploy/iam_datasets.sh`). Leitura por `list_rows`/Storage Read e escrita por streaming insert, sem `jobUser` | Sem SQL ad hoc no runtime: tabelas pré-agregadas pelo 001; o RAG já roda em memória, sem BigQuery (Q-17) |
| LLM | Gemini via Vertex (`aiplatform.user`) | Gemini API (`generativelanguage`) com `gemini-api-key` injetada por `--set-secrets` por quem tem accessor | Chave de API em runtime: aceitável só na PoC; registrar como dívida |
| Guardrails | Model Armor (`bussola-guard`) + callbacks | Callbacks do ADK + safety settings do Gemini | Sem filtro gerenciado de prompt injection |
| Build | `--source` / Cloud Build com bucket | `docker buildx` local + push para `agentes` (Artifact Registry Writer) | Build depende da máquina do integrante |
| Canal | ADK Web público (`allUsers`) | Serviço privado + acesso autenticado na demo | Demo exige login ou token |

**Risco no LLM do Plano B:** `--set-secrets` injeta o segredo em runtime com a
identidade da **SA de runtime**, não de quem faz o deploy. A SA default de
compute não tem `secretAccessor` em `gemini-api-key`, e o time não tem Secret
Admin para conceder. Sem o item 1 (ou um accessor no segredo), o agente no
Cloud Run fica sem LLM. O T038 confirmou que a SA default tem só
`artifactregistry.writer`, `logging.logWriter` e `storage.admin` no projeto
(sem `aiplatform.user`). A alternativa de injetar a chave por valor foi
descartada (constituição VII).

**Agente → MCP (Q-16):** nos dois planos, a SA de runtime do agente precisa de
`roles/run.invoker` no serviço `bussola-mcp`. É concessão no nível do
serviço, feita pelo time com confirmação humana. Se o time não tiver
permissão para alterar a política IAM do serviço, entra como item extra do
pedido 1.

## Dívidas registradas se o Plano B ficar definitivo

- Chave da Gemini API em runtime (constituição VII: segredos só por Secret
  Manager, nunca em arquivo ou log).
- Sem Model Armor: o 005 cobre só callbacks e safety settings.
- SA default de compute compartilhada por MCP e agente (menor isolamento).
