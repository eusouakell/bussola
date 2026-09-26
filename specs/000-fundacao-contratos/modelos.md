# Modelos Gemini e embedding (AC-12)

**Status:** pendente de credencial (T038). Este arquivo é substituído pelo
relatório de `deploy/smoke_modelos.py --gravar` quando um integrante com ADC
rodar o smoke.

## Valores provisórios (`contracts/env.example`)

| Variável | Valor provisório | Origem |
|---|---|---|
| `BUSSOLA_MODEL` | `gemini-3.5-flash` | mestre §5, não validado |
| `EMBEDDING_MODEL` | `gemini-embedding-001` | mestre §5, não validado |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | mestre §5 |

## Como validar

```bash
uv run --project agent python deploy/smoke_modelos.py            # só relatório
uv run --project agent python deploy/smoke_modelos.py --gravar   # grava este arquivo e env.example
```

- O smoke tenta cada candidato em `us-central1` e em `global`, e escolhe o
  primeiro que responde, com preferência por `us-central1`.
- Se o Flash só responder em `global`, faça o deploy do agente com
  `BUSSOLA_LOCAL_MODELO=global`. O `--gravar` não altera a localização.
- Sem `aiplatform.user` (Plano B), o smoke testa o fallback pela Gemini API.
  A chave vem do Secret Manager e nunca é impressa.
