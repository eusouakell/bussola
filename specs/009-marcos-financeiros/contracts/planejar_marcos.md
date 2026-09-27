# Contrato — ferramenta MCP `planejar_marcos` (ciclo 009)

Aditivo a [contratos.md](../../../docs/ciclos/contratos.md) §5. Read-only.
Entra em `docs/ciclos/contratos.md`, `contratos.py` (`FERRAMENTAS`,
`TABELAS_FERRAMENTA`) e no mapa §1 pelo commit `contracts:` deste ciclo.

## Descrição para o LLM (pt-BR)

> Monta a rota de marcos financeiros intermediários quando um objetivo não
> cabe nas condições atuais do cliente. Use depois de `simular_objetivo` ou
> `comparar_cenarios` voltarem inviáveis. Devolve o diagnóstico do que impede o
> objetivo, o próximo marco concreto e a trajetória até quatro marcos. Não
> rejeita o objetivo e não promete que ele será alcançado.

## Entrada

| Parâmetro | Tipo | Regra |
|---|---|---|
| `id_usuario` | `str` | UUID v4, obrigatório (sobrescrito pelo agente) |
| `ate_anomes` | `int` | 202501–202512, obrigatório (sobrescrito pelo agente) |
| `valor_alvo` | `float` | `> 0` |
| `prazo_meses` | `int` | 1–360 |
| `prioridade` | `str \| None` | ≤ 100 caracteres; só ecoado, nunca calculado |
| `usar_saldo_atual` | `bool` | default **`true`** |

**Divergência declarada:** em `simular_objetivo`, `usar_saldo_atual` é `false`
por padrão. Aqui é `true`, por decisão Q-009-3 ([questoes.md](../questoes.md)):
sem dado de patrimônio na base, o saldo em conta é o único recurso já
disponível mensurável. O saldo tem piso zero e a premissa vai nos `avisos`.

## `dados`

Campos e tipos em [data-model.md](../data-model.md) §`DadosPlanejarMarcos`:
`objetivo`, `situacao`, `motivos[]`, `marcos[]`, `proximo`,
`aporte_necessario`, `capacidade_sustentavel`, `trajetoria_incerta`,
`ressalvas[]`, `regras`.

Garantias:

- todo valor monetário é `float` BRL com 2 casas; todo prazo é `int` de meses;
- `marcos` tem no máximo `regras.max_marcos` (4) itens, e exatamente um deles
  é o `proximo`;
- com `trajetoria_incerta = true`, `marcos` tem no máximo 1 item;
- `motivos = []` implica `marcos = []` e `proximo = null`;
- nenhuma frase gerada rejeita o objetivo, promete o objetivo, supõe aumento de
  renda ou rendimento, nem recomenda endividamento (FR-011, teste léxico);
- nenhum campo de `dados` contém SQL, nome de projeto, credencial ou texto de
  lançamento.

## `fonte`

```json
{
  "ferramenta": "planejar_marcos",
  "tabelas": ["bussola_dados.perfil_mensal", "bussola_dados.parcelas"],
  "periodo": {"inicio": 202501, "fim": 202506}
}
```

`periodo.inicio` = primeiro mês com dado no período; `periodo.fim` =
`ate_anomes`.

## `avisos`

Lista determinística, conforme a tabela de avisos de
[data-model.md](../data-model.md). Sempre inclui a ressalva de que marco não
garante objetivo e o aviso de dado ausente de patrimônio/investimentos.

## Erros (envelope, nunca exceção)

| Situação | Código |
|---|---|
| `id_usuario` não é UUID; `ate_anomes` fora de 202501–202512; `valor_alvo ≤ 0`; `prioridade` acima de 100 caracteres; parâmetro não esperado | `ENTRADA_INVALIDA` |
| `prazo_meses` de **entrada** fora de 1–360 | `PRAZO_IMPLAUSIVEL` |
| UUID válido e inexistente | `USUARIO_INEXISTENTE` |
| Nenhum mês de `perfil_mensal` até `ate_anomes` | `DADOS_INSUFICIENTES` |
| Falha do repositório (BigQuery, fixture inválida) | `INDISPONIVEL` |

**Prazo calculado nunca vira erro.** Acima de `regras.prazo_maximo_marco` ele
vira `trajetoria_incerta = true` com o marco de prazo omitido, porque devolver
erro seria justamente o "não é viável" que a feature existe para eliminar
(FR-010, SC-008). Justificativa em [research.md](../research.md) R4.

Isso vale só para o prazo **calculado**. O `prazo_meses` de entrada é validado
pela regra central do runner (`ferramentas/base.py`), igual às demais
ferramentas: fora de 1–360 é `PRAZO_IMPLAUSIVEL`. Ajustado na integração em
`main`, onde essa validação passou a ser centralizada (ciclo 003).

A mensagem de `ENTRADA_INVALIDA` cita só nomes de campos
(`contratos.mensagem_entrada_invalida`), nunca o valor recebido.

## Logs (contratos §9)

Uma linha por chamada, com `servico`, `ferramenta`, `latencia_ms`,
`erro_codigo` e `ate_anomes`. Nunca `prioridade`, nunca texto de lançamento.

## Estado do agente (contratos §6)

`session.state["marcos"]` recebe o último `dados`, gravado pelo callback
`after_tool` de **ordem 30** do pacote `bussola_agent.marcos`. Nenhuma chave
existente é renomeada ou removida, e o callback devolve `None` (não substitui o
resultado da ferramenta).

Não há ferramenta ADK local no 009: o nome colidiria com esta ferramenta MCP,
já exposta ao modelo pelo `McpToolset` (ver [research.md](../research.md) R8).

## Instrução de prompt (ordem 90, contratos §6)

Reserva as ordens 90–99 para o ciclo 009. O trecho registra: quando chamar a
ferramenta, o mapeamento dos 5 blocos da resposta dentro de Diagnóstico /
Simulação / Recomendação (Q-009-6), as 9 proibições e a regra de citar a fonte
de cada número.
