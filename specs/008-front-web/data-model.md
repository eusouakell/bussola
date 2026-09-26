# Data Model: Front web da Bússola

Tipos em `web/src/agente/tipos.ts` e `web/src/sessao/modelo.ts`. Nomes em
português (domínio), como no resto do repositório.

## EventoAdk (entrada)

Subconjunto do `Event` do ADK em camelCase (ver
[contracts/eventos-agente.md](./contracts/eventos-agente.md)).

| Campo | Tipo | Uso |
|---|---|---|
| `id` | string? | deduplicação |
| `invocationId` | string? | agrupa um turno |
| `author` | string | `user` ou nome do agente |
| `timestamp` | number (s) | horário dos itens e da auditoria |
| `partial` | boolean? | texto em streaming |
| `content.parts[]` | `{text}` \| `{functionCall}` \| `{functionResponse}` | conteúdo |
| `actions.stateDelta` | objeto? | atualização rasa do `EstadoSessao` |
| `customMetadata.bussola` | `{respostas_rapidas?, tag?, guardrail?, recomendado?}` | extensão opcional |

## RespostaFerramenta

- `Envelope`: `{dados: object, fonte: Fonte, avisos: string[]}`.
- `Fonte`: `{ferramenta: string, tabelas: string[], periodo?: {inicio,
  fim}}` (AAAAMM).
- `ErroEnvelope`: `{erro: {codigo: string, mensagem: string}}`.
- `DadosCrus`: qualquer outro objeto (ferramenta local sem envelope).

Regra: `extrairEnvelope(response)` devolve um dos três (R4).

## EstadoSessao

Espelha as chaves de contratos §6; todas opcionais no front.

| Chave | Tipo | Leitura na UI |
|---|---|---|
| `id_usuario` | string | rodapé dos Bastidores, **mascarado** |
| `ate_anomes` | number | barra de demo, `DivisorMes`, habilita "Avançar" |
| `estado_jornada` | `OBJETIVO`…`ACOMPANHAR` | stepper, tint do fundo |
| `objetivo` | `{tipo, descricao, valor_alvo, prazo_meses, prioridade}` | `CardObjetivo`, P1–P5 |
| `cenarios` | cenários do `comparar_cenarios` | vistas |
| `cenario_escolhido` | string | rodapé, `CardCenario` escolhido |
| `ultimas_fontes` | `Fonte[]` | aba Ferramentas |
| `consentimentos` | `{[acao]: {consent_id, status, ts, resumo?}}` | `CardConsentimento`, aba Consentimentos |
| `plano_id` | string | rodapé, habilita "Avançar", P1–P5 |
| `acompanhamento` | `{historico[], ultimo?, acumulado?, percentual?}` | P2, P3, P5 |

Transição: `estado = {...estado, ...stateDelta}` (semântica do ADK: chave de
topo substituída). Chaves `temp:*` são ignoradas.

## ItemConversa

União discriminada por `tipo`, na ordem de chegada:

| `tipo` | Campos | Componente |
|---|---|---|
| `mensagem_cliente` | `texto`, `ts` | `MensagemCliente` |
| `mensagem_agente` | `texto`, `ts`, `emStreaming`, `tag?`, `respostasRapidas?` | `MensagemAgente` (+ `RespostasRapidas`) |
| `ferramenta` | `chamadaId`, `nome`, `args` (sem PII), `status` (`consultando`\|`ok`\|`erro`), `resposta?`, `inicio`, `fim?` | `LinhaFerramenta`; o card vem de `resposta` |
| `card` | `componente`, `chamadaId`, `envelope`, `estado` (snapshot) | cards da tabela do plano |
| `consentimento` | `acao`, `consentId` | `CardConsentimento` (status lido do state atual) |
| `guardrail` | `motivo`, `texto` | `AlertaGuardrail` |
| `divisor_mes` | `anomes` | `DivisorMes` |
| `falha_conexao` | `mensagem` | `ErroFerramenta` de conexão (modo ao vivo) |

Ferramentas consecutivas do mesmo turno são agrupadas no bloco colapsável
"Analisando sua situação" (`BlocoAnalise`).

## EventoAuditoria

`{tipo_evento, ts, estado_jornada, resumo}`; `tipo_evento` ∈ contratos §6.
`resumo` é texto curto gerado pelo front a partir de nomes e códigos (ex.:
"perfil_financeiro · ok"), nunca o texto do cliente.

## ModeloSessao (saída do reducer)

`{itens: ItemConversa[], estado: EstadoSessao, auditoria: EventoAuditoria[],
jornada: {estado, ts}[], ferramentas: RegistroFerramenta[], ocupado: boolean,
erroConexao?: string}`

- `jornada`: entrada em cada estado, com horário (aba Jornada).
- `ferramentas`: chamada, fonte, período, duração, avisos (aba Ferramentas).

## Roteiro simulado (fixture)

`{versao, relogio_inicio, turnos: [{mensagem: string|null, eventos:
EventoAdk[]}]}`; o turno com `mensagem: null` é o início da sessão. Formato
completo em [contracts/fixtures-web.md](./contracts/fixtures-web.md).

## Estado interno do agente simulado

`{estado: EstadoSessao, consentimentosUsados: Set, baseline?: {[macro]:
media}, falhas: {oportunidades?: boolean, poucosDados?: boolean}, lento:
boolean, seq: number}`. Nunca exposto à UI, só via eventos.
