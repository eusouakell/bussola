# Contrato front ↔ agente (consumo)

O front **consome** contratos v1 (contratos §5, §6) e a API HTTP do ADK. Este
documento fixa como o front interpreta cada peça. Ele não altera contratos
v1; a extensão `customMetadata.bussola` é **proposta** para 004/005.

## 1. Transporte ao vivo

| Passo | Requisição | Resposta usada |
|---|---|---|
| Criar sessão | `POST /apps/{app}/users/fernando/sessions` `{}` | `id`, `state` |
| Turno | `POST /run_sse` `{appName, userId, sessionId, newMessage: {role: "user", parts: [{text}]}, streaming: true}` | `data: <EventoAdk>` por bloco |
| Ressincronizar | `GET /apps/{app}/users/fernando/sessions/{id}` | `state` |

- `app` = `VITE_ADK_APP` (padrão `bussola_agent`).
- Em dev, o Vite encaminha `/apps` e `/run_sse` para `http://localhost:8000`.
- Falha de rede, HTTP ≠ 2xx ou `data: {"error": …}` → item
  `falha_conexao` com "Não consegui falar com a Bússola agora." e as ações
  "Tentar de novo" (reenvia a última mensagem) e "Usar modo simulado".

## 2. Evento → UI

| Evento | Efeito |
|---|---|
| `text` com `partial: true` | acrescenta ao rascunho do autor (cursor de digitação) |
| `text` sem `partial` | fecha a mensagem; substitui o rascunho do mesmo autor |
| `functionCall` | item `ferramenta` em `consultando`; auditoria `ferramenta_chamada` |
| `functionResponse` com envelope | linha → `ok`; card conforme a tabela do plano; fonte registrada |
| `functionResponse` com `erro` | linha → `erro`; `ErroFerramenta` (ver §4), exceto os casos da §4.1 |
| `functionResponse` sem envelope | linha → `ok`; card da ferramenta local lê os dados crus |
| `actions.stateDelta` | `estado = {...estado, ...delta}`; auditoria de estado e consentimento |
| `customMetadata.bussola.respostas_rapidas` | chips abaixo da mensagem |
| `customMetadata.bussola.tag` | tag semântica da mensagem |
| `customMetadata.bussola.guardrail` | `AlertaGuardrail` (ou nota de recusa para `promessa_credito`); auditoria `guardrail_bloqueio` |
| `customMetadata.bussola.recomendado` | selo "Recomendado" no `ComparadorCenarios` |

Nome legível na conversa, nome técnico só nos Bastidores. Parâmetros
exibidos nos Bastidores passam por máscara: `id_usuario` vira `36a2…7269`.

## 3. Resultados das ferramentas locais (formas esperadas)

Formas dos contextos 004–006, toleradas com campos extras ou faltando. O
simulado as devolve como envelope com `fonte.ferramenta` = nome da
ferramenta e o aviso `Resposta simulada pelo front; regravar após o ciclo
NNN`.

| Ferramenta | `dados` (campos lidos) |
|---|---|
| `registrar_objetivo` | `objetivo {tipo, descricao, valor_alvo, prazo_meses, prioridade}`, `faltando[]` |
| `escolher_cenario` | `cenario` |
| `solicitar_consentimento` | `consent_id`, `acao`, `resumo`, `status`, `o_que_faz`, `o_que_nao_faz`, `dados_usados` |
| `criar_plano` | `plano_id`, `cenario`, `valor_alvo`, `aporte_mensal`, `prazo_meses`, `criado_em_anomes`, `proximos_passos[{texto, acao?}]` |
| `ativar_lembretes` / `simular_contratacao` | `acao`, `status`, `mensagem` |
| `ajustar_plano` | `plano_id`, `aporte_mensal`, `prazo_meses`, `rota` |
| `avancar_mes` | `anomes`, `planejado`, `realizado`, `desvio`, `tolerancia`, `status` (`no_plano`\|`desvio`\|`folga`), `categoria_desvio {macro, valor_mes, media_base, aumento}`, `acumulado`, `percentual`, `restante`, `meses_decorridos`, `meses_restantes`, `resumo_mes` (envelope), `rotas[{id, titulo, descricao, simulacao (envelope simular_objetivo)}]` |
| `status_plano` | `objetivo`, `plano`, `meses_decorridos`, `acumulado`, `percentual`, `ultimo_status`, `historico[]` |

## 4. Códigos de erro → copy do `ErroFerramenta`

| Código | Mensagem ao cliente | "Tentar de novo" |
|---|---|---|
| `INDISPONIVEL` | Não consegui consultar {nome legível} agora. Sigo com o que tenho. | sim |
| `DADOS_INSUFICIENTES` | Tenho poucos meses de histórico para estimar sua sobra com segurança. | não |
| `ENTRADA_INVALIDA` | Não entendi os valores desse pedido. Pode reformular? | não |
| `PRAZO_IMPLAUSIVEL` | Esse prazo não é possível de simular. Tente outro prazo. | não |
| `USUARIO_INEXISTENTE` | Não encontrei seus dados nesta demonstração. | não |
| `SEM_PLANO_ATIVO` | Você ainda não tem um plano ativo. Crie o plano para acompanhar mês a mês. | não |
| `FIM_DO_REPLAY` | A demonstração vai até dez/2025. Não há mais meses para avançar. | não |
| outro | Algo deu errado nesta consulta. Sigo com o que tenho. | não |

O texto de `erro.mensagem` nunca é exibido (pode trazer detalhe técnico).
"Tentar de novo" envia a mensagem `Tentar de novo: {nome legível}`.

### 4.1 Casos que não são falha visual

- `CONSENTIMENTO_NECESSARIO`: linha em `erro` só nos Bastidores; na conversa
  o `CardConsentimento` aparece pelo `state`.
- `DADOS_INSUFICIENTES` em `capacidade_poupanca`/`perfil_financeiro`: aviso
  âmbar dentro do `CardDiagnostico` (E4), não erro fatal.

## 5. Proposta para 004/005 (`customMetadata.bussola`)

O ADK permite `custom_metadata` no `Event`. Proposta aditiva para os
callbacks do agente preencherem:

```json
{"bussola": {"tag": "diagnostico", "respostas_rapidas": ["Me mostra os caminhos"],
             "guardrail": "outro_cliente", "recomendado": "acelerado"}}
```

Sem a extensão, o front continua funcionando: mensagens sem tag, sugestões
por estado da jornada e selo pela regra de R9.
