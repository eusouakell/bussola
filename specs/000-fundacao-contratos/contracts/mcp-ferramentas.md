# Contrato: ferramentas do MCP mock (`bussola-mcp`)

Transporte: streamable HTTP em `/mcp`, `0.0.0.0:$PORT` (padrão 8080).
Fonte: contratos §5 e §8. Os modelos Pydantic ficam em
`mcp_server/bussola_mcp/contratos.py`.

## Assinaturas expostas (`list_tools`)

Todas têm `id_usuario: str` e `ate_anomes: int` como obrigatórios.

| Ferramenta | Parâmetros adicionais (padrão) |
|---|---|
| `perfil_financeiro` | — |
| `capacidade_poupanca` | — |
| `oportunidades_corte` | `top_n: int = 5` |
| `dividas_e_parcelas` | — |
| `simular_objetivo` | `valor_alvo: float`, `prazo_meses: int \| None = None`, `aporte_mensal: float \| None = None`, `usar_saldo_atual: bool = False` |
| `comparar_cenarios` | `valor_alvo: float`, `prazo_meses: int` |
| `buscar_contexto_financeiro` | `pergunta: str`, `k: int = 5` |
| `resumo_mes` | `anomes: int` |

`referencia_coorte` (P1) tem modelos em `contratos.py`, mas não é servida pelo
mock. Ela entra no 003.

## Resultado

- Todo resultado é um objeto JSON: `structuredContent` e o mesmo JSON em
  `TextContent`.
- O resultado é sempre um destes dois envelopes:
  - `{"dados", "fonte", "avisos"}`;
  - `{"erro": {"codigo", "mensagem"}}`.
- Erros de negócio **não** usam `isError`.

## Regras do mock

1. Valida a entrada com `Entrada*`. Se falhar, devolve `ENTRADA_INVALIDA`,
   com uma mensagem que cita só os nomes dos campos.
2. Se o `id_usuario` (normalizado) não estiver em `usuarios.json`, devolve
   `USUARIO_INEXISTENTE` ("Cliente não encontrado.").
3. Se o usuário não for o âncora, devolve `DADOS_INSUFICIENTES` ("O mock só
   tem respostas do cliente âncora.").
4. Escolha do golden:
   - P0 com `ate_anomes < 202512`: `<ferramenta>__ate_202506.json`, com o
     aviso "Resposta de exemplo do mock (corte 202506)." acrescentado a
     `avisos`;
   - P0 com `ate_anomes = 202512`: `<ferramenta>__ate_202512.json`, sem
     alteração;
   - `resumo_mes`: `resumo_mes__<anomes>.json`, sem alteração;
   - `oportunidades_corte`: `dados.categorias[:top_n]`;
   - `buscar_contexto_financeiro`: `dados.trechos[:k]`;
   - `simular_objetivo` e `comparar_cenarios`: o golden da entrada canônica
     (`valor_alvo=30000`, `prazo_meses=24`), com o aviso "Resposta de
     exemplo do mock, calculada para valor_alvo=30000 e prazo_meses=24.".
5. Sem fixtures (arquivo ausente), devolve `INDISPONIVEL` ("Dados de exemplo
   indisponíveis.").

## Exemplo

Chamada: `perfil_financeiro(id_usuario="36a21505-d6d4-42d3-b319-d51a133c7269", ate_anomes=202506)`

```json
{
  "dados": {"renda_media": 0.0, "...": "..."},
  "fonte": {"ferramenta": "perfil_financeiro",
            "tabelas": ["bussola_dados.perfil_mensal", "bussola_dados.entradas_categoria"],
            "periodo": {"inicio": 202501, "fim": 202506}},
  "avisos": ["Resposta de exemplo do mock (corte 202506)."]
}
```
