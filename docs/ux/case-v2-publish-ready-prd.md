# Bússola — Publish-ready Case PRD V2

**Status:** binding production PRD  
**Workflow:** `bussola-public-case-v2-deliberative`  
**Oversight:** human on exception; final publication/merge remains Kell-owned  
**Quality target:** publish-ready council score ≥ 9.2/10, no dimension < 9.0, no blocker, no unresolved dissent  
**Production branch:** `case/publish-ready-v2`

## 1. Outcome

Produce a single public case page that demonstrates, at portfolio level, strong product thinking, content design, UX, art direction and technical depth without overstating what the hackathon PoC proved.

The page must be credible to:
- senior product/design/engineering readers;
- hiring/peer reviewers evaluating Kell's craft;
- people interested in agents, data and Context Engineering;
- the original team, whose collective authorship must remain visible.

The page is not a product landing page and must not behave like one.

## 2. One-line story

> A signal in a synthetic financial dataset exposed a mismatch between visible balance and financial pressure; the team turned that tension into a goal-first agent PoC, then revisited the experience to make choices, effort and consent clearer.

## 3. Hook / turn / payoff

### Hook
**O saldo está no azul. E a dívida?**

### Turn
The visible balance was insufficient to explain financial health. Product logic therefore had to understand context before proposing action.

### Payoff
The case shows how a data-informed idea became a bounded PoC and how later UX/content work made the decisions inside that idea clearer.

The payoff is not a promised financial result.

## 4. Visual idea

### **O que aparece / o que pesa**

The page repeatedly contrasts:
- the surface signal the person sees;
- the underlying context that changes the decision.

This should govern composition, evidence, architecture and before/after work.

### Visual grammar
- warm white: `#FFFDFA`;
- ink/navy: `#172331`;
- muted text: `#59636E`;
- rules: `#D7D9D5`;
- existing product orange: `#BD4900` only for decisions/action/annotation;
- large sans display;
- neutral sans body;
- monospace evidence/source labels;
- rules, crop and alignment before cards;
- rectangular surfaces only when the artifact itself is rectangular.

### Explicit exclusions
- full-wall campaign red;
- AI gradients;
- serif-as-editorial shorthand;
- bento/card-grid grammar;
- pill/chip systems as default organization;
- translucent blur nav;
- phone mockup chrome around every UI state;
- corporate team-directory cards;
- motion needed to create depth.

## 5. Page architecture

### 0 — Hero / contradiction
**Job:** create the question and establish human + product in one scene.

Content:
- event label;
- headline;
- short intro;
- Fernando + one UI state as one visual mass;
- discrete provenance.

No secondary evidence cards.
No debt/rotativo explanation here.
No sales CTA.

Desktop:
- copy left;
- visual scene right;
- UI is cropped and partially occluded by Fernando;
- Fernando may extend beyond the visual field.

390/320:
- headline + intro;
- one recomposed scene;
- UI intentionally cropped;
- Fernando overlaps it;
- neither object needs to be fully visible.

Motion:
- optional single entrance of UI + Fernando only;
- 400–600 ms;
- no loop/parallax;
- final state complete under `prefers-reduced-motion`.

### 1 — Discovery / evidence
**Job:** prove where the problem came from.

Primary visual:
**SALDO POSITIVO**
**MESMO COM**
**USO DO ROTATIVO**

Supporting copy:
- base sintética de 1.000 usuários;
- qualitative observation only;
- why this changed the question.

Do not publish retained percentages.
Do not invent charts or transactions.
Do not use red/green traffic semantics.

### 2 — Fernando / consequence
**Job:** translate the contradiction into a human decision without replaying the hero.

Do not repeat the hero portrait as another large image.

Use:
- goal: primeiro apartamento;
- one large editorial statement;
- a small goal/product artifact;
- the question: **o que já compete com esse objetivo?**

Provenance remains explicit: narrative persona; financial data simulated.

### 3 — Product decision / orient before offering
**Job:** bridge evidence → product.

One continuous sequence:
`OBJETIVO → CONTEXTO → CENÁRIO → DECISÃO → CONSENTIMENTO`

Each step gets one sentence maximum.
No feature-card grid.
Orange marks only the active decision point.

Core product principle:
> começar pelo objetivo; entender o contexto; mostrar trade-offs; pedir consentimento antes de ação sensível.

### 4 — What we built / architecture
**Job:** show technical ambition while bounding maturity.

Use a faithful editorial rendering of the documented architecture:
- Cliente / app do banco;
- Model Armor;
- consentimento + autonomia governada;
- Gemini + ADK;
- Agente Bússola;
- MCP;
- agente de dados/conhecimento;
- BigQuery;
- RAG financeiro;
- Cloud Run;
- Secret Manager;
- Cloud Logging;
- Open Finance only as future evolution.

Label: **arquitetura de referência da PoC**.

Do not imply every component was simultaneously production-validated.

### 5 — UX evolution / craft centerpiece
**Job:** demonstrate content design and UX decisions.

Four comparisons:
1. Entrada — less explanation, more direct choice.
2. Esforço — show cuts/additional effort before choice.
3. Consentimento — say what happens and what does not.
4. Legibilidade — contrast/focus/hierarchy.

Visual rule:
- large UI surfaces;
- no decorative phone shell;
- one Before + one After per decision;
- annotation rail explains one change;
- reconstructed-state label attached to each artifact.

Desktop:
- wide comparison spreads;
- UI readable without zoom.

390/320:
- Before then After;
- labels remain attached;
- no slider/flip;
- readable text;
- no two tiny phones side by side.

### 6 — Prototype / lab
**Job:** let the reader inspect the work.

Desktop/tablet:
- embedded prototype in a large restrained frame;
- explicit PoC/simulation note;
- open-in-new-tab link.

Mobile:
- do not force a cramped iframe;
- show a concise explanation + strong launch link;
- preserve scope note.

### 7 — Team / collective authorship
**Job:** show the hackathon as collective work, not an institutional directory.

People:
- Carlos Guevara — Produto;
- Kell Bonassoli — Design / estratégia, contexto, Responsible AI, narrativa;
- João Paulo Soares Lopes — Tecnologia e Dados / agente, contratos, deploy;
- Victor Lucas Lopes — Tecnologia e Dados / arquitetura, integração, RAG, governança e BigQuery;
- Yasmim Mafra Maroum — Mentoria / ciência de dados, crédito e produtos orientados por dados.

Use:
- documentary/contact-sheet rhythm;
- actual local portraits;
- names + concise contribution;
- LinkedIn as secondary text link.

No flip cards.
No hover-only bios.
No invented current titles.

### 8 — Colophon / what this proves
Three statements:
- **Observamos** — a financial tension in synthetic data.
- **Exploramos** — a goal-first agent PoC and reference architecture.
- **Refinamos depois** — clarity, effort, consent and legibility.

Then:
- what remains hypothesis;
- code/prototype/source links;
- publication/provenance note.

No generic dual CTA.

## 6. Content rules

Use:
- simple Portuguese;
- active voice;
- concrete product decisions;
- short metadata labels;
- “agentes de IA” where clearer than “IA agentiva”.

Avoid:
- “a IA conhece você”;
- “plano perfeito”;
- “revolucionar finanças”;
- validated-outcome language without evidence;
- legalistic repetition of the same disclaimer.

## 7. Evidence / provenance rules

Public-safe:
- base sintética with 1,000 users;
- qualitative signal: rotating credit use can exist without negative balance;
- Fernando is a narrative persona;
- Fernando image is AI-generated;
- UI comparisons are editorial reconstructions based on documented code/text;
- architecture is documented reference architecture;
- hackathon PoC vs later UX/content refinement are distinct.

Not public without new authority:
- retained dataset percentages;
- generalized R$ interest claims;
- 17-years-to-5-years claim;
- validated recommendation effectiveness;
- real consent revocation;
- full WCAG conformance.

## 8. Navigation

Minimal sticky navigation:
- Bússola / case;
- Descoberta;
- Produto;
- Evolução;
- Equipe;
- Experimentar.

No blur.
No pill nav.
At narrow widths, preserve only wordmark + one direct action or compact anchor list without JS-heavy menu.

## 9. Accessibility

Required:
- one H1;
- semantic heading order;
- skip link;
- visible focus;
- no essential hover interaction;
- no color-only meaning;
- reduced-motion behavior;
- image alt/provenance;
- readable evidence at 320/390;
- architecture text alternative;
- iframe title;
- external prototype link;
- source/provenance notes available to screen readers.

Automated checks do not equal full WCAG conformance.

## 10. Performance / implementation

- static HTML/CSS/very small JS only if needed;
- no external framework or animation library for the case page;
- no new webfont dependency;
- hero image eager/high priority only if appropriate;
- team images lazy + async decode;
- no large decorative asset without narrative job;
- no runtime dependency for layout.

## 11. SEO / sharing

Title:
**Bússola — O que o saldo não conta**

Description:
**Case Bússola: de um insight em dados sintéticos a uma prova de conceito com agentes de IA — e ao refinamento posterior de UX, conteúdo e consentimento.**

No claim of Itaú endorsement.

## 12. Deliberation rules for this production

Ordinary questions are resolved internally.

Default arbitration:
- narrative/content/visual conflict → Creative Director;
- evidence/provenance → Readiness Evaluator after Repository Analyst;
- accessibility conflict → Readiness Evaluator;
- implementation drift → Code Reviewer / Readiness Evaluator;
- authority/rights/confidentiality → human exception.

Failure returns to earliest owning decision.

Maximum:
- 3 deliberation rounds per material question;
- 2 production revisions for same root cause.

## 13. Publish-ready acceptance

Do not surface to Kell until all are true:

- no deterministic blocker;
- no semantic `fail` / `unknown`;
- no open material question;
- no unresolved dissent;
- desktop + 390 + 320 visually inspected;
- static composition passes without motion;
- tests/build green;
- accessibility review has no unresolved blocker;
- code review has no unresolved blocker;
- readiness = READY;
- weighted council score ≥ 9.2;
- every applicable dimension ≥ 9.0;
- public claims/provenance publish-safe.

Then provide one final packet only:
- preview/live candidate;
- desktop/390/320 renders;
- scorecard;
- remaining risks;
- PR/diff;
- recommendation `PUBLISH` or `DO NOT PUBLISH`.
