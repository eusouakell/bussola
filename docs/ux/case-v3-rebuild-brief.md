# Bússola V3 — rebuild after failed independent visual gate

**Status:** active rebuild brief  
**Source:** post-publication review of V2  
**Canonical orchestration:** Agentic Factory `main` after PR #42  
**Human operating model:** human on exception; final publication gate only

## 1. Why V3 exists

The V2 case passed the old council process and was published, but Kell's final visual inspection immediately found the page strange in image proportions and hierarchy.

That is treated as a **workflow defect**, not merely a preference change.

Agentic Factory PR #42 then made the missing enforcement executable:

- bounded owner → challenger → arbiter deliberation;
- independent primary/secondary review runs;
- evidence-backed score computation;
- visual evidence manifests with section/viewport integrity;
- duplicate screenshot-content detection;
- root-cause revision budgets;
- convergence and human-intervention observability.

When V2 was re-reviewed through independent browser runs, it no longer passed the new gate.

## 2. Independent post-publication evidence

### Creative Director review

Execution run:

`ee56881b-7574-4f0b-8ebc-9ff4e13ccd96`

Scores:
- art direction: **7.5 / 10**
- memorability/coherence: **7.0 / 10**

Material findings:
- hero headline and Fernando image compete for dominance;
- UX evolution is too dense;
- team portrait treatment is generic/default;
- the overall language is competent but not distinctive enough for an exceptional case.

### Experience Designer review

Execution run:

`4f0a3181-bd82-44e8-bfb5-bc6891169754`

Scores:
- content design: **7.0 / 10**
- responsive/mobile: **8.0 / 10**

Material findings:
- hero contains competing focal points;
- UX evolution becomes a long text-heavy wall;
- architecture reads as documentation rather than visual evidence;
- Fernando is introduced repeatedly rather than progressively deepened.

## 3. Gate result

Agentic Factory publish-readiness threshold:

- weighted score **>= 9.2**;
- every applicable dimension **>= 9.0**;
- primary and secondary reviews from distinct `review_run_id` values;
- no unresolved blocker/dissent;
- trustworthy visual evidence at 1440 / 390 / 320.

**V2 result under the new gate: FAIL.**

The V2 publication is therefore retained as negative pilot evidence, not as the V3 visual baseline.

## 4. What V3 preserves

Preserve unless new evidence requires change:

- hook: **“O saldo está no azul. E a dívida?”**;
- synthetic-data / confidentiality boundaries;
- Fernando as narrative persona with AI-image disclosure;
- PoC vs later refinement distinction;
- collective authorship;
- architecture/product evidence as part of the story;
- four UX/content decisions as evidence of later refinement;
- prototype access;
- accessibility and provenance honesty.

## 5. What V3 must not inherit by default

Do not treat these as approved direction:

- current hero proportions;
- current oversized type hierarchy;
- current Fernando/UI scale relationship;
- repeated numbered-section rhythm;
- circular team portraits;
- current text-heavy architecture presentation;
- current dense Before/After treatment;
- current section spacing merely because it is already implemented.

## 6. Required convergence sequence

### Stage A — diagnose

Independent specialist reviews of the same V2 evidence:

- Editorial Storyteller;
- Experience Designer;
- Editorial Art Director;
- Creative Director;
- Repository Analyst for evidence constraints.

Questions must be first-class convergence issues, not informal comments.

### Stage B — V3 PRD

Produce one binding V3 PRD covering:

- narrative jobs;
- information hierarchy;
- visual system;
- image/product/evidence proportions;
- section rhythm;
- responsive rules;
- what must be visually proved before production.

### Stage C — representative proofs

Before full implementation, prove at least:

1. hero;
2. Discovery/data relationship;
3. one UX evolution pair;
4. team treatment;
5. 390 px recomposition.

Static first. Motion does not enter until the static system passes.

### Stage D — production

Only after the internal art-direction gate passes.

### Stage E — independent council

Use distinct review runs and the Agentic Factory executable publish-readiness evaluator.

## 7. Human exception policy

Do not ask Kell to arbitrate ordinary:

- visual hierarchy;
- responsive composition;
- copy hierarchy;
- image treatment;
- section rhythm;
- architecture presentation.

Escalate only:

- factual/rights/confidentiality conflict;
- canonical authority conflict;
- exhausted bounded deliberation;
- final publication decision.

## 8. Definition of done

A V3 staged candidate reaches Kell only when:

- weighted score >= 9.2;
- every applicable dimension >= 9.0;
- reviewer spread is within threshold or formally resolved;
- visual evidence manifest passes;
- no open material convergence issue;
- no unresolved dissent;
- no release blocker;
- recommendation = `PUBLISH`.

## 9. Related

- Agentic Factory PR #42 — executable deliberation / independent evidence enforcement
- Bússola PR #13 — V2 published pilot
- `docs/ux/case-v2-council-review.md`
- `docs/ux/case-v2-final-publication-packet.md`
