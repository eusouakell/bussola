<!--
Sync Impact Report
- Version change: 1.0.0 → 1.0.1 (PATCH, antes do congelamento)
  - X. Contratos e paralelismo: o RAG não tem dataset (Q-17 do 000). O 002
    escreve o corpus e o índice no repositório, não em `bussola_rag`.
  - Templates: sem mudança.
- Histórico: template (não versionado) → 1.0.0
- Princípios definidos (todos novos):
  I. Números vêm de ferramentas determinísticas
  II. Agente isolado de SQL e infraestrutura
  III. Read-only com escopo por cliente
  IV. Respostas rotuladas e explicáveis
  V. Somente dados sintéticos e logs seguros
  VI. Consentimento explícito e auditado
  VII. Segredos fora do repositório
  VIII. pt-BR e Responsible AI
  IX. Testes obrigatórios e gates sem rede
  X. Contratos e paralelismo entre ciclos
- Seções adicionadas: Restrições de plataforma; Fluxo de desenvolvimento; Governance
- Seções removidas: nenhuma
- Templates:
  ✅ .specify/templates/plan-template.md (Constitution Check genérico, lê este arquivo)
  ✅ .specify/templates/spec-template.md (sem seção obrigatória nova)
  ✅ .specify/templates/tasks-template.md (categorias de teste compatíveis)
  ✅ CLAUDE.md (runtime guidance atualizado no ciclo 000)
- TODOs adiados:
  TODO(RATIFICATION_DATE): data do merge do ciclo 000 em main (tag contratos-v1).
- Fontes e classificação: ver seção "Rastreabilidade dos princípios" no fim.
-->

# Bússola Constitution

## Core Principles

### I. Números vêm de ferramentas determinísticas

- O LLM MUST NOT calcular nem inventar valores financeiros. Todo número exibido ao
  cliente MUST vir de uma ferramenta determinística (SQL parametrizado ou função
  Python testada) e ser rastreável ao envelope `dados`/`fonte` da ferramenta.
- O modelo só redige. Formatação monetária (R$, vírgula) é responsabilidade do
  agente; ferramentas devolvem `float` BRL com 2 casas.

Rationale: a proposta de valor da PoC é orientação confiável; um número
alucinado invalida a demo e o princípio de Responsible AI.

### II. Agente isolado de SQL e infraestrutura

- O agente conversacional MUST NOT ver SQL, nomes de projeto, credenciais nem
  detalhes de infraestrutura. Ele só enxerga ferramentas semânticas do MCP.
- Nenhuma ferramenta MCP MAY aceitar ou devolver SQL; `fonte.tabelas` traz só
  `dataset.tabela`.
- Erros de ferramenta são envelopes `{"erro": {"codigo", "mensagem"}}`, não
  exceções com detalhes internos.

Rationale: reduz a superfície de prompt injection e mantém o contrato estável.

### III. Read-only com escopo por cliente

- Acesso a `hackathon_dados` MUST ser somente leitura. Escrita só nos datasets
  `bussola_*` do respectivo dono (contratos §3).
- Toda sessão está presa a um `id_usuario`; nenhuma ferramenta MAY devolver
  dados de outro cliente, exceto agregados de coorte.
- `id_usuario` MUST ser validado como UUID v4 por regex antes de qualquer uso;
  `anomes`/`ate_anomes` MUST estar em 202501–202512 (`ate_anomes` inclusivo).
- SQL MUST ser parametrizado (`@id_usuario`, `@ate_anomes`); montar SQL por
  concatenação com texto do usuário ou do modelo é proibido.
- O agente sobrescreve `id_usuario` e `ate_anomes` a partir do `session.state`;
  valores enviados pelo modelo são ignorados.

Rationale: isolamento de cliente e defesa contra injeção de SQL e de prompt.

### IV. Respostas rotuladas e explicáveis

- Diagnóstico, simulação e recomendação/ação MUST ser rotulados de forma
  distinta nas respostas ao cliente.
- Recomendações MUST citar a fonte (ferramenta/período) e o raciocínio.
- `trade_offs` e textos de cenários são gerados por regra determinística, não
  por LLM.

Rationale: explicabilidade e tom de educação financeira.

### V. Somente dados sintéticos e logs seguros

- O projeto MUST usar apenas dados sintéticos; nenhum dado real de cliente.
- Logs MUST ser JSON estruturado em stdout (`severity`, `message` e campos de
  contratos §9) e MUST NOT conter prompt completo, texto de lançamentos, chaves
  ou tokens. O `id_usuario` sintético pode ser logado.

Rationale: privacidade por padrão, mesmo com dados sintéticos.

### VI. Consentimento explícito e auditado

- Nenhuma ação sensível MAY ser executada sem "sim" explícito do cliente,
  registrado com `consent_id` válido.
- Consentimentos, planos e eventos relevantes MUST ser auditados em
  `bussola_app` (tipos de evento de contratos §6).

Rationale: governança e confiança do cliente.

### VII. Segredos fora do repositório

- Segredos MUST viver no Secret Manager ou ser injetados no deploy; nunca no
  código, em arquivos versionados, em logs ou impressos no terminal.
- `contracts/env.example` MUST conter apenas nomes e valores não secretos.
- Uso de `GOOGLE_API_KEY` (Plano B) é dívida registrada e restrita à PoC.

Rationale: o repositório e os logs são compartilhados.

### VIII. pt-BR e Responsible AI

- Todo texto ao cliente MUST estar em português do Brasil, com tom de educação
  financeira (Resolução Conjunta nº 8) e princípios de Responsible AI.
- Identificadores de código em português (domínio) ou inglês técnico, com
  consistência dentro de cada módulo.

### IX. Testes obrigatórios e gates sem rede

- Testes unitários MUST cobrir funções de simulação e validação de entrada;
  testes de contrato MUST cobrir o MCP (schema das ferramentas) e os dados
  (DDL ↔ modelos Pydantic).
- `make lint` e `make test` MUST passar antes de qualquer PR, com
  `BUSSOLA_FAKES=TRUE` e sem acesso à rede ou ao GCP.
- Testes que dependem de BigQuery real MUST ser marcados `@pytest.mark.bq` e só
  rodam em `make test-bq`.
- Testes MUST gravar apenas em `bussola_app_dev`.

Rationale: ciclos paralelos só convergem se cada PR prova o contrato isolado.

### X. Contratos e paralelismo entre ciclos

- `docs/ciclos/contratos.md` e o código de contrato (`contracts/`,
  `contratos.py`, `interfaces.py`, `fakes.py`, `estado.py`, `callbacks.py`,
  `extensoes.py`, `persistencia.py`, `mcp_conexao.py`) MUST mudar só via PR
  com título `contracts: <mudança>`, revisado por um ciclo consumidor afetado.
  Mudanças MUST ser aditivas; remover ou renomear campo exige acordo de todos
  os ciclos ativos.
- Cada ciclo MUST escrever somente nos caminhos que possui (contratos §1). Em
  `Makefile` e `pyproject.toml` valem acréscimos, resolvidos por união.
- Um ciclo MUST NOT depender de código não mergeado: usa fakes e fixtures
  (`BUSSOLA_FAKES=TRUE`) até a dependência chegar em `main`.
- `bussola_dados` é escrito só pelo 001. O RAG não tem dataset: o corpus e o
  índice ficam no repositório, nos caminhos do 002 (Q-17 do 000).
- Cloud Run: revisões com `--tag cNNN --no-traffic`; só o ciclo 007 move tráfego.

Rationale: 8 ciclos rodam em worktrees paralelas; propriedade clara evita
conflitos e regressões silenciosas.

## Restrições de plataforma

- GCP `batalha-time-07-lkbv`, região `us-central1`. Serviços limitados pela org
  policy `gcp.restrictServiceUsage` (sem Firestore, Cloud SQL, Scheduler,
  Workflows, GKE, Trace).
- Stack: Python 3.12 com `uv`; `mcp_server/` (FastMCP, streamable HTTP em
  `/mcp`) e `agent/` (Google ADK + Gemini Flash via `MCPToolset`); BigQuery com
  consultas parametrizadas; `pytest` e `ruff`.
- Deploy por imagem: `docker buildx --platform linux/amd64` → Artifact Registry
  `agentes` → `gcloud run deploy --image`. `--source`, `adk deploy` e Agent
  Runtime não são o caminho padrão (não há bucket de staging).
- Mudanças de IAM ou de tráfego exigem confirmação humana explícita.

## Fluxo de desenvolvimento

- 1 ciclo = 1 worktree = 1 branch (`NNN-<slug>`) = 1 execução do Spec Master = 1
  feature, com `SPECIFY_FEATURE_DIRECTORY=specs/NNN-<slug>` fixo.
- Estratégia dentro do run: Trunk-Based; a extensão git do Spec Kit fica
  desabilitada.
- Rebase em `main` antes do PR; PR com `make test` e `make lint` verdes e os
  critérios de aceite do ciclo. Ordem de merge e revisores conforme o plano de
  ciclos.
- `.spec-master/` é local; a rastreabilidade de cada ciclo é exportada para
  `specs/NNN-*/traceability.md` e versionada.

## Governance

- Esta constituição prevalece sobre práticas locais. Ela é criada no ciclo 000
  e **congela** no merge desse ciclo (tag `contratos-v1`).
- Após o congelamento, um ciclo que precise de mudança MUST NOT aplicá-la: MUST
  registrar `specs/NNN-*/proposta-constituicao.md` para discussão no time. Uma
  emenda aprovada entra por PR próprio revisado pelas duas trilhas.
- Versionamento semântico: MAJOR para remoção ou redefinição de princípio;
  MINOR para princípio ou seção nova; PATCH para redação.
- Todo PR MUST verificar conformidade com esta constituição (Constitution Check
  do plano) e justificar qualquer exceção no próprio plano.
- Orientação de runtime para agentes: `CLAUDE.md` na raiz.

**Version**: 1.0.1 | **Ratified**: TODO(RATIFICATION_DATE): data do merge do ciclo 000 em main (tag contratos-v1) | **Last Amended**: 2026-09-26

<!--
Rastreabilidade dos princípios
| Princípio | Fonte | Classificação |
|---|---|---|
| I | mestre §7, §11; contratos §0 | EXPLICIT |
| II | mestre §7; contratos §5 | EXPLICIT |
| III | mestre §7, §11; contratos §0, §2, §5 | EXPLICIT |
| IV | mestre §7, §11; contratos §5 | EXPLICIT |
| V | mestre §11, §12; contratos §9 | EXPLICIT |
| VI | mestre §11; contratos §6 | EXPLICIT |
| VII | mestre §11, §16; 000 §1.7 | EXPLICIT |
| VIII | mestre §11; contratos §2 | EXPLICIT |
| IX | mestre §12; contratos §2; README §5.9-5.10 | EXPLICIT |
| X | README §5; contratos §0, §1 | EXPLICIT |
| Restrições de plataforma | mestre §5, §6, §13 | EXPLICIT |
| Confirmação humana para IAM/tráfego | 000 §3.5; README §5.9 | INFERRED (generalização) |
| Fluxo de desenvolvimento | README §5-§6; mestre §14 | EXPLICIT |
| Governance (congelamento, proposta-constituicao.md) | 000 §1.4; README §5.5 | EXPLICIT |
| Emenda por PR revisado pelas duas trilhas | roadmap §4 | INFERRED |
-->
