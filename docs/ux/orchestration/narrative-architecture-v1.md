# Bússola — narrative architecture V1

**Run:** `bussola-public-case-v1`  
**Agent contract:** `editorial-storyteller`  
**Inputs:** `case-context-packet-v1.md` + `reference-synthesis-v1.md`

## 1. Central tension

A healthy-looking balance can hide a financial behavior that pushes a goal farther away.

The story is not “an AI agent solves personal finance”. It is:

> **We looked at synthetic financial behavior, found a mismatch between visible balance and actual financial pressure, turned that tension into a hackathon PoC, and later revisited the experience to make the decisions easier to understand.**

That distinction protects both the case and the craft.

## 2. Narrative promise

By the end of the case, the reader should understand:

1. **why this problem was chosen** — it emerged from the data, not from a preselected product pitch;
2. **who the product idea was for** — Fernando is a narrative lens for a real design tension, not evidence of a researched individual;
3. **what the team actually built** — a PoC in a hackathon context;
4. **what happened later** — UX/content work clarified choices, trade-offs and consent;
5. **what is evidence vs hypothesis** — the case is explicit about its limits.

## 3. Recommended story sequence

### 0 — Opening / the contradiction

**Job:** create the question that makes the rest worth reading.

**Core line:**  
**O saldo está no azul. E a dívida?**

**What the reader needs immediately:**
- this is a Bússola case;
- it came from a hackathon;
- the contradiction is about visible balance vs hidden financial pressure;
- this is a PoC/refinement story, not a live banking product.

**Do not explain everything here.** The opening should not carry the data insight, architecture, provenance, team and UX evolution at the same time.

---

### 1 — Discovery / the problem changed when we looked at the data

**Job:** prove that the product direction came from observation.

**Key beat:**
- synthetic dataset;
- segmentation looked at financial behavior;
- use of revolving credit appeared even with positive visible balance;
- qualitative conclusion: **saldo positivo não é sinônimo de saúde financeira**.

**Narrative function:** this is the first turn. The case stops being “save for a goal” and becomes “understand financial pressure before planning the goal”.

**Required limit:** no retained percentages, no population-level inference.

---

### 2 — Fernando / make the tension human

**Job:** translate the abstract financial mismatch into a person-sized decision.

Fernando wants to buy an apartment. The useful question is not yet “how much should he save?” but:

> **What is already competing with that goal?**

**Narrative function:** connect observation → consequence.

**Guard:** Fernando is a narrative persona. Do not write as though his transaction history were a real customer record.

---

### 3 — Product decision / orient before offering

**Job:** make the product thesis explicit.

The insight should lead to a design/product decision:

> **Start from the goal, understand the financial context, then show possible next steps. Do not begin by selling a banking product.**

This section is important because it connects the discovery to the interface. Without it, the page jumps from research to “we built an agent”.

**Evidence that belongs here:**
- goal-first entry;
- context before recommendation;
- scenario comparison;
- explicit consent boundaries.

---

### 4 — What we built in two days / a bounded PoC

**Job:** show ambition without inflating maturity.

The hackathon team moved from:
- data;
- product framing;
- agent;
- architecture;
- demonstration.

Use the documented architecture and repository evidence to show technical depth.

**Narrative function:** prove that the idea became a working/prototyped system, while keeping the scope bounded.

**Guard:** architecture ≠ proof that every proposed capability was live and validated at once.

---

### 5 — After the hackathon / making the decisions clearer

**Job:** turn later UX/content work into a second act, not an appendix.

Opening line should express the transition:

> **Fazer funcionar foi o começo. Fazer entender foi o próximo passo.**

Show the later work through concrete decisions:
- shorter entry;
- financial effort made explicit;
- consent tied to an action;
- legibility/contrast/navigation issues surfaced.

**Narrative function:** demonstrate design/content-design craft through the consequences of changes.

**Guard:** do not claim usability outcomes that were not tested with users.

---

### 6 — Try the prototype / evidence with limits

**Job:** let the reader inspect the work.

Provide:
- embedded demo/prototype;
- what is simulated;
- what is reconstructed;
- what remains unvalidated;
- direct route to code/architecture when useful.

This is not a conversion CTA. It is an evidence surface.

---

### 7 — The team / collective authorship

**Job:** close the loop on how the work happened.

Show:
- people;
- contribution in the hackathon;
- later refinement distinction;
- mentor;
- links/source where appropriate.

The tone should be documentary, not leadership-page institutional.

---

### 8 — Colophon / what this case actually proves

**Job:** leave the reader with a precise takeaway.

Three blocks are enough:

**What we observed**
- a hidden financial tension in synthetic data.

**What we explored**
- a goal-first agent experience and supporting architecture.

**What we refined later**
- clarity, legibility, comparison and consent.

Then state what remains hypothesis/unfinished.

## 4. Hook, turn and payoff

### Hook

**“O saldo está no azul. E a dívida?”**

It works because it is:
- simple;
- concrete;
- financially legible;
- tied to the actual data insight;
- not a promise.

### Turn

The meaningful turn is not “then we used AI”.

It is:

> **The visible balance was insufficient to explain financial health, so the product needed to understand context before proposing action.**

### Payoff

The payoff is not a numeric financial outcome.

It is:

> **The case shows how a data-informed product idea became a PoC and how later UX/content work made the decisions inside that idea clearer.**

That payoff supports both product/design credibility and honest scope.

## 5. One-line retell

> **A synthetic-data signal exposed a gap between visible balance and financial pressure; the team turned it into a goal-first agent PoC, then revisited the experience to make choices and consent clearer.**

If the page cannot be retold this way after reading, the structure is carrying too much secondary material.

## 6. What to omit or demote

### Omit from the public narrative unless separately authorized

- retained confidential percentages;
- “17 years → 5 years” outcome;
- “more than R$1,000/year in interest” as a generalized/public claim;
- claims of validated financial recommendation;
- claims of effective consent revocation;
- full WCAG-conformance claims;
- any “production-ready banking agent” wording.

### Demote from primary narrative

- exhaustive stack enumeration in the opening;
- every repository implementation detail;
- long career biographies;
- every technical source link inline;
- duplicate explanations of “synthetic data” in every section;
- provenance blocks that visually compete with the artifact they qualify.

## 7. Factual risk map

| Risk | Narrative control |
| --- | --- |
| Synthetic dataset read as real-customer evidence | label dataset once clearly; keep note close to Discovery |
| Fernando read as real person/customer | persona + AI-image provenance close to first appearance |
| PoC read as production product | repeat only at major evidence transitions, not as legalistic boilerplate |
| Architecture read as fully implemented | distinguish documented architecture from verified runtime evidence |
| UX refinement read as validated outcome | describe decisions/changes, not user-performance gains |
| Later work read as hackathon delivery | visibly separate “hackathon” and “after the hackathon” |
| Collective work read as single-person authorship | team section + repository/history evidence |

## 8. Editorial tone

Use:
- short declarative sentences;
- active subjects;
- concrete verbs;
- restrained contrast;
- “marketing do bem”: make the work desirable by making the reasoning visible, not by exaggerating results.

Avoid:
- “revolutionize” language;
- “AI knows you”;
- “perfect plan”;
- overexplaining agentic terminology;
- consultant-style abstraction when a concrete product decision exists.

## 9. Handoff

**Narrative architecture: READY for Experience Design.**

Experience Design may change presentation order within sections for responsive reading, but should preserve the eight narrative jobs and the hook → turn → payoff logic.
