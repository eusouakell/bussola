# Quickstart — ciclo 009 (marcos financeiros)

## Rodar os gates

```bash
make lint                 # ruff check + format --check nos dois projetos
make test                 # pytest com BUSSOLA_FAKES=TRUE, sem rede e sem GCP
npm --prefix web test -- --run    # vitest do front
npm --prefix web run build        # build do front
```

## Exercitar a engine sem servidor

```bash
cd mcp_server && uv run python - <<'PY'
from bussola_mcp.contratos import ID_ANCORA, RegrasMarco
from bussola_mcp.dominio import marcos
from bussola_mcp.dominio.fakes import RepositorioFake

repo = RepositorioFake()
regras = RegrasMarco()
ctx = marcos.contexto_de_perfil(
    repo.perfil_mensal(ID_ANCORA, 202512), repo.parcelas(ID_ANCORA, 202512), regras
)
plano = marcos.planejar(valor_alvo=300000.0, prazo_meses=24, contexto=ctx, regras=regras)
print([m.codigo for m in plano.motivos])
print(plano.proximo.tipo if plano.proximo else None, plano.trajetoria_incerta)
PY
```

## Exercitar a ferramenta com fakes

```bash
cd mcp_server && uv run python - <<'PY'
import json
from bussola_mcp.contratos import ID_ANCORA
from bussola_mcp.dominio.fakes import RepositorioFake
from bussola_mcp.ferramentas.planejar_marcos import planejar_marcos

print(json.dumps(planejar_marcos(
    {"id_usuario": ID_ANCORA, "ate_anomes": 202512,
     "valor_alvo": 300000, "prazo_meses": 24},
    repositorio=RepositorioFake(),
), ensure_ascii=False, indent=2)[:1200])
PY
```

Casos rápidos de erro:

```python
planejar_marcos({"id_usuario": "abc", "ate_anomes": 202512, "valor_alvo": 1, "prazo_meses": 1}, ...)
# -> {"erro": {"codigo": "ENTRADA_INVALIDA", ...}}
planejar_marcos({"id_usuario": "<uuid v4 inexistente>", ...}, ...)
# -> {"erro": {"codigo": "USUARIO_INEXISTENTE", ...}}
```

## Ver o card no front

```bash
npm --prefix web run dev     # modo simulado; o card aparece quando a ferramenta responde
```

No teste de componente (`CardMarcos.test.tsx`), o card é alimentado por um
envelope literal — é o caminho mais rápido para inspecionar a renderização.

## Valores de referência do âncora (contratos §8)

Renda ≈ 7.451 · gasto ≈ 4.615 · sobra ≈ 2.836 · juros ≈ 61 · saldo mínimo
≈ −2.072 · saldo máximo ≈ 49.321.

Com as regras padrão: juros ≈ 0,8% da renda (abaixo de 1%), então
`DIVIDA_A_RESOLVER` **não** acende por juros; a reserva-alvo é
3 × 4.615 ≈ 13.845; a capacidade sustentável é 0,60 × 2.836 ≈ 1.702/mês.

## Marcos de dependência

| Marco | O que libera | Como checar |
|---|---|---|
| S1 (001 em `main`) | `contexto_de_perfil` e `meses_para` passam a delegar a `metricas`/`simulacao` | `git cat-file -e origin/main:specs/001-camada-dados-financeiros/traceability.md` |
| S3 (003 em `main`) | registro da ferramenta no `server.py` real, golden e `FERRAMENTAS_MOCK` | `git cat-file -e origin/main:specs/003-mcp-dados-conhecimento/traceability.md` |
| S4 (004 em `main`) | instrução integrada ao prompt base e eval de números | `git cat-file -e origin/main:specs/004-agente-bussola-jornada/traceability.md` |
