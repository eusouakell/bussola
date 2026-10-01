# UX review — Bússola

> Revisão de produto/experiência baseada no front atual, no README do ciclo 008, nos relatos de teste em `docs/bugs/mvp1.md` e na arquitetura da PoC.  
> Este documento recomenda próximos experimentos; não afirma que todos os problemas abaixo continuam presentes no build atual.

## O que já está bem resolvido

A Bússola tem alguns fundamentos de UX mais maduros do que uma PoC conversacional típica:

- a jornada tem um modelo mental claro: **Objetivo → Entender → Antecipar → Orientar → Agir → Acompanhar**;
- existe separação entre **orientação** e **ação**, com consentimento explícito;
- o modo simulado permite demonstrar a experiência sem depender da nuvem;
- o painel **Bastidores** torna ferramentas, consentimentos e auditoria inspecionáveis;
- há vistas específicas para plano e acompanhamento, em vez de manter tudo no chat;
- o produto já considera estados de erro, baixa disponibilidade e dados insuficientes.

## Prioridades recomendadas

### P0 — Recuperação de conversa fora do happy path

Os testes do MVP registraram dois problemas recorrentes: perda de contexto em respostas curtas e loops quando o usuário pede algo fora do caminho esperado.

**Padrão recomendado:**

```text
RECONHECER
"Entendi que você quer X."

EXPLICAR O LIMITE
"Com o seu cenário atual, eu não consigo transformar isso diretamente em um plano viável."

REORIENTAR
"Posso montar uma etapa intermediária que preserve o objetivo final."

AÇÃO CLARA
[Ver etapa intermediária] [Mudar objetivo]
```

A resposta fora de escopo não deveria apenas recusar nem repetir a pergunta anterior. Ela deveria preservar a intenção do usuário e oferecer uma rota de retorno.

### P0 — Contrato visual para resultados estruturados

Foi relatado que, em alguns casos, o agente produzia planejamento em texto quando a experiência esperava cards.

Recomendação: tratar **card vs. texto** como contrato de interface, não como preferência do modelo.

- resultados financeiros estruturados devem chegar ao front em schema próprio;
- copy explicativa pode acompanhar o objeto;
- o front decide a representação visual;
- respostas textuais não devem substituir um componente obrigatório.

Isso reduz inconsistência e evita que uma mudança de prompt quebre a experiência.

### P0 — Estado de disponibilidade que proteja confiança

Para latência, quota ou indisponibilidade, evitar mensagens que soem como falha genérica do banco.

Usar um padrão em três estágios:

1. **processando** — skeleton + mensagem específica ("Estou recalculando os caminhos com seus dados");
2. **demorando** — expectativa ("Isso está levando mais tempo que o normal");
3. **indisponível** — ação segura ("Seu objetivo foi preservado. Tente novamente ou continue no modo demonstração").

Nunca simular sucesso quando a ferramenta falhou.

---

## P1 — Tornar a jornada visível durante a conversa

O stepper existe no sistema, mas a pergunta principal para UX é se o usuário entende:

- onde está;
- por que a Bússola está perguntando aquilo;
- o que vem depois.

Recomendação para o topo da experiência:

```text
Entender  ●━━━━○━━━━○  Agir
          etapa 2 de 5

Agora estou entendendo quanto espaço existe no seu orçamento.
```

O rótulo deve usar linguagem de usuário, não estado técnico do agente.

### P1 — Simplificar “Meu plano”

Hoje existem cinco vistas P1–P5: Jornada, Meu plano, Trilha, Resumo e Check-in.

Hipótese para teste: isso pode ser excessivo para uma pessoa que acabou de criar um plano.

Testar uma IA mais simples:

- **Conversa**
- **Meu plano**
  - objetivo;
  - caminho;
  - próximos marcos;
  - check-in.

“Resumo” pode ser uma representação dentro do plano, não necessariamente uma navegação independente.

### P1 — Hierarquia de avisos

O teste com histórico insuficiente mostrou que um aviso visual pode transmitir gravidade maior do que o problema real.

Criar três níveis:

- **info** — contexto útil, sem impacto na tarefa;
- **atenção** — resultado com incerteza/limitação;
- **bloqueio** — não é seguro ou possível continuar.

“Pouco histórico, mas ainda consigo orientar com menor confiança” não deveria parecer erro.

### P1 — Evidência como parte da experiência

A Bússola já preserva fontes e auditoria. Isso pode aparecer para o usuário de forma menos técnica.

Exemplo:

> **Como cheguei a esse número?**  
> Baseado nos seus últimos 6 meses simulados e nas regras desta simulação.  
> [Ver detalhes]

O painel Bastidores continua sendo a visão técnica; a conversa recebe apenas a explicação suficiente para confiança.

### P1 — Consentimento como momento de decisão

Antes de uma ação sensível, mostrar:

- o que vai acontecer;
- qual dado/decisão será registrado;
- o que **não** vai acontecer;
- botão principal e alternativa.

Exemplo:

```text
Criar este plano?

A Bússola vai:
✓ registrar a meta e os marcos
✓ acompanhar a evolução na simulação

Não vai:
— contratar produto
— movimentar dinheiro
— garantir crédito

[Autorizar plano]  [Voltar]
```

---

## P2 — Separar Demo pública de Bastidores

Para uma versão pública de portfólio:

### Modo visitante
- conversa;
- objetivo;
- plano;
- acompanhamento;
- selo “dados sintéticos”.

### Modo laboratório
Ativado por “Ver como funciona”:
- ferramentas;
- contexto;
- consentimentos;
- auditoria;
- erros simulados.

Isso reduz carga cognitiva sem perder o valor técnico do projeto.

### P2 — Entrada pública sem fricção desnecessária

Para a demo **simulada**, não há necessidade de autenticação real.

CTA recomendado:

> **Explorar com Fernando — dados sintéticos**

O login/BFF continua relevante para o modo ao vivo e para testar isolamento de sessão.

### P2 — Acessibilidade a validar

Adicionar uma rodada específica de testes para:

- navegação integral por teclado;
- foco após mensagens/cards novos;
- `aria-live` para streaming, erro e consentimento;
- contraste de avisos;
- `prefers-reduced-motion`;
- tamanhos de toque no mobile;
- composer visível com teclado virtual;
- leitura correta dos cards por screen readers.

Não assumir conformidade até testar.

## Sequência recomendada

1. Padronizar recuperação fora do happy path.
2. Tornar cards um contrato de UI.
3. Melhorar estados de latência/erro.
4. Refinar avisos e consentimento.
5. Testar simplificação de “Meu plano”.
6. Criar Demo pública + modo laboratório.
7. Fazer rodada dedicada de acessibilidade.

## Métricas de produto para a próxima rodada

- % de usuários que concluem a criação de um plano;
- turnos até um plano válido;
- loops/repetições por sessão;
- abandonos depois de aviso/erro;
- ações de consentimento compreendidas;
- tempo para encontrar “Meu plano”;
- taxa de recuperação após pedido fora do escopo;
- SUS ou UMUX-Lite após demo;
- confiança percebida: “Entendi de onde veio a recomendação”;
- clareza de autonomia: “Ficou claro o que a Bússola pode ou não fazer”.
