# Roteiro da demo (≤ 5 min)

Roteiro do apresentador para mostrar a Bússola nos 6 estados da jornada.
Ela vai de um objetivo ao acompanhamento com desvio, e o consentimento é
explícito. A operação (canal, smoke, logs, rollback) está em
[operacao.md](operacao.md).

## Legenda

- **[confirmar na integração]** marca números e textos que vêm do
  roteiro gravado (`web/fixtures/roteiro-demo.json`, modo `Simulado`) e dos
  goldens do motor.
  - Os ciclos 004 (agente e jornada), 005 (consentimento) e 006
    (acompanhamento) podem mudar a redação.
  - Os números devem ser os mesmos, porque vêm das ferramentas
    determinísticas sobre os mesmos dados. O LLM não calcula.
  - Refaça o ensaio completo no ADK real depois do merge desses ciclos e
    atualize as linhas marcadas.
- As **falas** são o que o apresentador digita (ou clica na resposta
  rápida). A **narração** é o que ele diz para a plateia enquanto o agente
  responde.

## Preparação

| Item | Valor |
|---|---|
| Canal | Front do BFF: `https://bussola-bff-wimifi56uq-uc.a.run.app` ([operacao.md §7](operacao.md#7-operação-da-demo)) |
| Persona | **Fernando** (sintético): renda média de ~R$ 6,7 mil, parcelas altas, um mês de viagem cara em jul/2025 |
| Barra "Modo demonstração" | `Agente: Ao vivo (ADK)`; painel "Bastidores" aberto (estado, ferramentas e fontes) |
| Mês inicial | jun/2025 (`REPLAY_START_ANOMES=202506`), com o extrato de jan a jun/2025 |
| Duração alvo | 4 min 30 s, com 30 s de folga |

## Linha do tempo

| Tempo | Estado | Fala do apresentador | Ferramentas esperadas (Bastidores) | O que aparece |
|---|---|---|---|---|
| 0:00 | — | (login como Fernando) | — | Saudação e estado `OBJETIVO` na barra |
| 0:15 | OBJETIVO | "Quero comprar meu primeiro apartamento" | `registrar_objetivo` | O agente anota o objetivo e pergunta valor e prazo |
| 0:40 | ENTENDER → ANTECIPAR | "R$ 30 mil em 2 anos" | `perfil_financeiro`, `capacidade_poupanca`, `dividas_e_parcelas`, `oportunidades_corte`, `simular_objetivo` | Perfil e viabilidade com fonte **[confirmar na integração]** |
| 1:30 | ORIENTAR | "Me mostra os caminhos" | `comparar_cenarios`, `buscar_contexto_financeiro` | Três caminhos, com o acelerado recomendado **[confirmar na integração]** |
| 2:10 | AGIR | "Quero o caminho acelerado" | `escolher_cenario`, `solicitar_consentimento` | Cartão de consentimento: "Posso …? Responda **sim** ou **não**." |
| 2:30 | AGIR | "Sim, autorizo" | `criar_plano` | Plano criado, com o botão "Avançar um mês" liberado |
| 2:50 | ACOMPANHAR | "Avançar um mês" (botão da barra) | `avancar_mes`, `resumo_mes`, `simular_objetivo` | jul/2025 com **desvio** e duas rotas **[confirmar na integração]** |
| 3:35 | ACOMPANHAR | "Quero adotar a rota A" | `solicitar_consentimento` | Novo cartão de consentimento (ajuste do plano) |
| 3:50 | ACOMPANHAR | "Sim, autorizo" | `ajustar_plano` | Plano ajustado **[confirmar na integração]** |
| 4:05 | ACOMPANHAR | "Avançar um mês" | `avancar_mes`, `resumo_mes` | ago/2025 acima do planejado **[confirmar na integração]** |
| 4:20 | (guardrail) | "Então meu financiamento vai ser aprovado?" | nenhuma | Recusa de garantir crédito, com uma alternativa |
| 4:35 | — | (fechamento) | — | Bastidores: estados percorridos e fontes |

### Narração e números esperados

**0:15, OBJETIVO.** "O cliente começa pelo que quer, não por um produto. A
Bússola registra o objetivo e só pergunta o que falta."

**0:40, ENTENDER e ANTECIPAR.** "Agora ela lê o extrato de seis meses e
simula. Cada número tem fonte: é ferramenta, não o modelo." Números
**[confirmar na integração]**:

- renda média de R$ 6.691,39;
- sobra mediana de R$ 1.729,00 por mês;
- parcelas de 35,35% da renda;
- aporte de R$ 1.250,00 por mês para R$ 30.000,00 em 24 meses, com folga
  de R$ 479,00.

A frase de exemplo do ciclo 004 (§7) usa 60 mil. A demo usa **30 mil em 2
anos** porque o roteiro gravado e os goldens do motor usam esse valor.

**1:30, ORIENTAR.** "Três caminhos, com trade-offs explícitos. A
recomendação cabe no prazo." Números **[confirmar na integração]**:

- acelerado: R$ 1.681,15 por mês, 18 meses, com cortes sugeridos em
  Restaurantes, Compras e Assinaturas;
- conservador: 44 meses;
- equilibrado: 29 meses.

**2:10–2:30, AGIR.** "Nada acontece sem autorização. O cartão diz o que
ela vai e o que não vai fazer, e só um 'sim' explícito cria o plano." Se o
apresentador responder algo ambíguo, o agente pergunta de novo. Isso também
serve de demonstração.

**2:50, ACOMPANHAR com desvio.** "Avançamos o relógio: é julho. A viagem
pesou." Números **[confirmar na integração]**:

- sobra de R$ 884,53 contra R$ 1.681,15 planejados;
- desvio de -R$ 796,62;
- maior peso em Viagens: R$ 935,14 no mês, contra uma média de R$ 6,51;
- duas rotas para voltar ao plano: rota A, novo aporte; rota B, novo prazo.

**3:35–3:50, ajuste com novo consentimento.** "Mudar o plano também pede
autorização." Resultado **[confirmar na integração]**: aporte de R$ 1.712,67
por mês, 17 meses até a meta.

**4:05, mês seguinte.** "Agosto voltou ao trilho." Números **[confirmar na
integração]**:

- sobra de R$ 4.218,74;
- acumulado de R$ 5.103,27, 17,01% da meta.

**4:20, guardrail.** "Ela não promete o que não pode: aprovação de crédito
depende do banco." O roteiro gravado também traz um pedido de dados de outro
cliente (E1). **Não o envie no `Ao vivo (ADK)`**: por decisão do time, nada de
prompt injection contra o Gemini real. Os guardrails são validados por testes
determinísticos, e o E1 só aparece no modo `Simulado`.

**4:35, fechamento.** "Seis estados, números sempre com fonte,
consentimento antes de agir e acompanhamento mês a mês. Tudo auditado."

## Checklist pré-demo

Na véspera:

- [ ] `main` congelada: nenhum push até o fim da demo. O canal usa a tag
      `main` do agente.
- [ ] Revisões finais promovidas na ordem MCP → agente → BFF
      ([operacao.md §8](operacao.md#8-promoção-e-rollback)).
- [ ] `make smoke` verde ([operacao.md §4](operacao.md#4-smoke)).
- [ ] Ensaio completo no `Ao vivo (ADK)`, cronometrado (≤ 5 min).
- [ ] Vídeo de backup gravado e baixado no computador da demo.

No dia, 15 min antes:

- [ ] `make smoke` de novo.
- [ ] Front aberto e logado como Fernando, com o painel Bastidores visível.
- [ ] Proxy do ADK aberto num terminal, de reserva ([operacao.md §7](operacao.md#7-operação-da-demo)).
- [ ] **Warm-up**, 2 min antes: uma pergunta simples ("oi"). Ela sobe a
      instância e o primeiro turno não paga o cold start.
- [ ] **Sessão nova** logo antes de começar: "Trocar persona" e entrar de
      novo como Fernando. A conversa do warm-up não pode contaminar o
      roteiro.
- [ ] Vídeo de backup aberto no player, pausado no início.
- [ ] Terminal com os logs de erro à mão para quem opera
      ([operacao.md §5](operacao.md#5-logs)).

## Contingência

| Problema | Ação imediata | Frase para a plateia |
|---|---|---|
| Resposta lenta (> 20 s) ou `503`/`429` do Gemini | Espere uma nova tentativa (o agente troca de Flash). Se falhar de novo, troque o `Agente` para `Simulado` e recomece do passo atual | "Vou seguir no modo gravado, que usa as mesmas ferramentas." |
| O agente "esqueceu" a conversa (sessão perdida) | "Trocar persona", entre de novo e recomece pelo passo 0:40 com "Quero comprar meu primeiro apartamento, R$ 30 mil em 2 anos" | "Nova sessão: a auditoria da anterior continua registrada." |
| Front fora do ar | ADK Web pelo proxy (`http://localhost:8080`, app `bussola_agent`), mesmas falas | — |
| Tudo fora do ar ou menos de 2 min restantes | Vídeo de backup | "Vou mostrar a gravação da mesma jornada." |
| Resposta com número diferente do roteiro | Siga. Os números vêm das ferramentas e aparecem com fonte nos Bastidores | — |

A troca para `Simulado` reinicia a sessão. Por isso, nesse modo, recomece do
primeiro turno com as mesmas falas. Ele leva ~1 min até o ponto onde estava.

## Roteiro do vídeo de backup

Grave na integração final, com o produto completo (ciclos 001 a 008 em
produção). O vídeo segue a linha do tempo acima.

1. **Preparação:**
   - resolução 1920×1080, zoom do navegador em 125%;
   - tema claro, notificações desligadas;
   - painel Bastidores aberto.
2. **Take único** no `Ao vivo (ADK)`, com as mesmas falas e ≤ 4 min 30 s.
   Se o Gemini falhar no meio, grave no `Simulado` e diga isso na
   legenda.
3. **Legendas** (sem narração de áudio obrigatória), uma por estado:
   - "1. Objetivo";
   - "2. Entender";
   - "3. Antecipar";
   - "4. Orientar";
   - "5. Agir: consentimento";
   - "6. Acompanhar: desvio e ajuste".
4. **Cortes permitidos:** só nas esperas do modelo acima de 5 s, com o
   marcador "[corte]".
5. **Não mostrar:** terminal, console do GCP, URLs de tag, tokens ou a
   senha do login simulado. Comece a gravar já logado.
6. **Arquivo:**
   - nome `bussola-demo-backup-AAAAMMDD.mp4`;
   - uma cópia local no computador da demo e outra no drive do time;
   - registre o link abaixo.

Link do vídeo: _(preencher na integração final)_

## Referências

- Roteiro gravado turno a turno: `web/fixtures/roteiro-demo.json`
  ([web/README.md](../web/README.md)).
- Jornada e estados: [jornada-agentic.md](jornada-agentic.md).
- Consentimento: [ciclo 005](ciclos/005-consentimento-governanca.md).
  Acompanhamento e rotas: [ciclo 006](ciclos/006-acompanhamento-replay.md).
