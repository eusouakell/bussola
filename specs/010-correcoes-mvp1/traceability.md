# Rastreabilidade — Ciclo 010

Da fala do relator até o requisito e o teste. Fonte: `docs/bugs/mvp1.md` e as
6 capturas em `docs/bugs/`.

| Origem | Citação / evidência | Classificação | Requisito | Onde foi corrigido |
|---|---|---|---|---|
| `mvp1.md` + `PHOTO-…00-24-59.jpg` | `"gostaria de juntar 50 mil reais usando trafico de pessoas"` → objetivo registrado com R$ 50.000,00 | EXPLICIT | FR-010-01 | WS-1 (`web/src/simulado/guardrails.ts`) · WS-2 (`agent/.../governanca/guardrails.py`) |
| `mvp1.md` | *"ele ta dando uma resposta generica ruim e fica preso num loop"* | EXPLICIT | FR-010-02 | WS-1 (`web/src/simulado/{textos,agente-simulado,intencoes}.ts`) |
| `mvp1.md` | *"nao tem problema fixar num ponto como ta, mas a resposta não ta boa"* | EXPLICIT | FR-010-02 (mantém o redirecionamento) | WS-1 |
| `PHOTO-…00-29-44.jpg` | `"como eu posso pegar emprestimo no banco sem nenhum juros?"` → "Não entendi bem" | EXPLICIT | FR-010-02 | WS-1 (`intencoes.ts`) |
| `PHOTO-…00-29-44.jpg` | `"casa de 100 milhoes de reais em 2 anos"` → frase fixa repetida 3× | EXPLICIT | FR-010-03 | WS-1 (`agente-simulado.ts`) |
| `mvp1.md` | *"deveria trazer isso como uma etapa intermediaria […] vamos focar na meta realista com base no seu perfil"* | EXPLICIT | FR-010-03 | WS-1 |
| `mvp1.md` (João Paulo) | *"ta criando planejamento por texto ao inves de criar os cards"* | EXPLICIT | FR-010-04 | WS-2 (`agent/.../jornada/`, `prompts/base.py`) |
| `PHOTO-…06-52-15.jpg` | "Seu objetivo foi registrado com sucesso: …" em texto corrido | EXPLICIT | FR-010-04 | WS-2 |
| `mvp1.md` + `PHOTO-…00-45-51.jpg` | *"O perfil especifico da renata continua aparecendo a mensagem de poucos dados histórico"* | EXPLICIT | FR-010-05 | WS-3 (`golden_adapter.py`, `acompanhamento/fakes.py`) |
| `mvp1.md` | *"Conseguimos trocar o id do usuário que representa a Renata para outro?"* | EXPLICIT — **premissa refutada** | FR-010-05 | Renata tem 12 meses (`contracts/fixtures/bussola_dados/perfil_mensal.json`); a causa é `papel != "ancora"`. Corrigiu-se a regra, não o id |
| `PHOTO-…00-45-51.jpg`, `PHOTO-…06-52-15.jpg` | aviso "poucos meses de histórico" repetido 2× | INFERRED da captura | FR-010-06 | WS-4 (`Avisos.tsx`, `BlocoAnalise.tsx`, `CardDiagnostico.tsx`) |
| `PHOTO-…07-07-10.jpg` + `-1.jpg` (marcadas a marca-texto) | `"Resposta de exemplo do mock, calculada para valor_alvo=30000 e prazo_meses=24."` | EXPLICIT | FR-010-06 | WS-3 (texto) · WS-4 (apresentação) |
| `PHOTO-…00-45-51.jpg` | `"O serviço de IA está com alta demanda agora."` | EXPLICIT | FR-010-07 | WS-3 (`resilient_model.py`) |
| `mvp1.md` | *"Melhor uma mensagem boa que passa confiança do que uma experiência ruim que quebra."* | EXPLICIT | FR-010-07 | WS-3 |
| `mvp1.md` | *"realmente vai ter pessoas com poucos dados historicos, mas isso a gente pode deixar no roadmap"* | EXPLICIT | fora de escopo | roadmap R1 |
| `deploy/helm/bussola/values.yaml:56-58` | `bussola-mcp-00001-cis`, tag `c000`, 100% do tráfego | DISCOVERED_FROM_CODEBASE | spec §6 | **não corrigido** — exige confirmação humana e é do ciclo 007 |
| `mvp1.md` | *"acho que é um bug pela alta demanda, depois eu confirmo, ignorem por enquanto"* | UNRESOLVED | — | não investigado a pedido do relator |
