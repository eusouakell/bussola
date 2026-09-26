# Formato de `web/fixtures/`

Gerado por `npm run fixtures` (`web/scripts/gerar-fixtures.ts`). Não editar
à mão: um teste regenera e compara.

## `goldens.json`

```json
{
  "fonte": "contracts/fixtures",
  "ferramentas": {
    "perfil_financeiro__ate_202506": { "dados": {}, "fonte": {}, "avisos": [] },
    "resumo_mes__202507": { "...": "..." }
  },
  "rag_trechos": [ { "trecho_id": "reserva-emergencia#1", "...": "..." } ]
}
```

- `ferramentas`: um item por arquivo de `contracts/fixtures/ferramentas/`,
  chave = nome do arquivo sem `.json`, valor **literal**.
- `rag_trechos`: conteúdo literal de `contracts/fixtures/rag/trechos_exemplo.json`.
- JSON com chaves ordenadas e indentação de 2 espaços, `\n` no fim.

## `roteiro-demo.json`

```json
{
  "versao": 1,
  "relogio_inicio": "2026-09-26T14:30:00-03:00",
  "turnos": [
    { "mensagem": null, "eventos": [ { "author": "bussola", "actions": { "stateDelta": {} } } ] },
    { "mensagem": "Quero comprar meu primeiro apartamento", "eventos": [] }
  ]
}
```

- Turnos do roteiro F1–F7: início, objetivo, valores, comparar, escolher,
  `sim`, `avançar um mês`, adotar rota, `sim`, `avançar um mês` (F7b), e os
  turnos de E1 e E2.
- `eventos`: `EventoAdk` em camelCase, sem os pedaços parciais (só o texto
  final), para o diff ser legível.
- `timestamp` sai do relógio fixo; IDs (`consent_id`, `plano_id`,
  `functionCall.id`) saem de um contador determinístico.

## Regravação depois de S4/S6

Quando 004–006 chegarem em `main`, gravar o mesmo roteiro contra o `make
agent` e comparar com `roteiro-demo.json`: diferenças de forma indicam
ajuste no parser tolerante ou na emulação.
