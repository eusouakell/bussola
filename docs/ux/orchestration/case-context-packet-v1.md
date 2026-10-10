# Bússola — case context packet V1

**Run:** `bussola-public-case-v1`  
**Agent contract:** `repository-analyst`  
**Source branch:** `design/case-v7-editorial-ui@9b1ebf5`  
**Purpose:** consolidate repository truth before narrative, experience and art-direction work.

## 1. Authority order

Use this precedence when sources conflict:

1. explicit human decisions recorded in `docs/ux/case-reframe-gate.md` and the latest approved editorial notes;
2. factual/evidence constraints in `docs/ux/editorial-case-v6-evidence.md`;
3. repository history and implementation artifacts;
4. V7 briefs/reviews as diagnostic input;
5. visual proofs and reference notes as exploration evidence only.

The current V7/V8 hero proofs are **not** design authority.

## 2. Confirmed facts that may anchor the public case

- Bússola originated in the Batalha de Agentes hackathon involving Itaú, Google Cloud and SantoDigital.
- The project is a hackathon proof of concept followed by later UX/content refinement; it is not a production banking service.
- The public story is allowed to say that the team analyzed a **synthetic base of 1,000 users**.
- The qualitative signal that survives public review is: **use of credit-card revolving credit can appear even when the visible account balance is positive**.
- Detailed percentages/aggregates from the hackathon dataset are retained in working documentation but are not approved for public disclosure.
- Fernando is a **narrative persona**, not a researched real customer.
- Fernando’s image is generated with AI and must remain labelled as such.
- Before/after interface states currently used in the case are **editorial reconstructions based on documented code/text**, not verified screenshots of historical executions.
- The public case should distinguish:
  - work delivered during the hackathon;
  - later UX/content refinement;
  - capabilities that remain proposal, architecture or unvalidated behavior.
- Architecture/stack documented in the repository includes Google Cloud, BigQuery, Gemini/ADK, Cloud Run, Secret Manager and RAG-related components. Documentation does not prove every proposed capability was implemented or validated in the same state.
- The repository records collective authorship. Victor originated/led the technical repository; Kell’s fork documents her strategy/context/research/Responsible-AI/narrative contribution and later public-case refinement.
- Participant-photo identification/use was reported by Kell as confirmed with participants; the repository does not independently audit those consents.

## 3. Editorial decisions already approved

### Preserve

- Headline/tension around: **“O saldo está no azul. E a dívida?”**
- Core arc: data-informed discovery → human problem → PoC → later UX/content refinement → evidence/limits → people.
- Simple, concrete language.
- Responsible framing: no promise that the system “knows” the user, no product-maturity inflation, no guaranteed financial outcome.
- Public phrasing **“agentes de IA”** when it is clearer than “IA agentiva/agentic”.
- Clear distinction between observation, hypothesis, implemented behavior and unvalidated behavior.
- Provenance close to the artifact it qualifies.
- The qualitative debt/rotativo insight belongs in **Descoberta**, not as a second competing hero card.

### Do not reopen without new evidence

- publication of confidential/retained dataset percentages;
- Fernando as protagonist/persona;
- disclosure that Fernando’s image is AI-generated;
- disclosure that before/after states are reconstructions;
- PoC vs production distinction;
- collective authorship framing.

## 4. Existing assets worth preserving

### Human / documentary

- `web/public/case/assets/fernando-ai.png` — Fernando, synthetic persona image.
- participant portraits in `web/public/case/assets`, with identification/use confirmation recorded in the evidence document.
- team/mentor credits and source notes already present in the public-case implementation.

### Product / UI

- current public-case HTML: `web/public/case/index.html`;
- embedded prototype route already referenced by the case;
- reconstructed before/after states for:
  - entry;
  - financial scenario/comparison;
  - consent;
  - legibility.

### Technical / evidence

- architecture documentation in `docs/arquitetura.md` and related project docs;
- commit history and repository implementation as evidence of technical contribution;
- V6/V7 renders in `outputs/`;
- `outputs/qa-render.json` for the previous responsive/visual QA run;
- reference bank in `docs/ux/visual-reference-bank-v1.md`.

## 5. Implementation constraints

- The case is a public web surface in `web/public/case/index.html`.
- Existing prototype/build/test conventions must remain intact.
- WCAG 2.2 AA is a baseline target, but automated scans cannot be presented as complete conformance.
- Reduced motion must remain supported.
- Keyboard/focus behavior cannot be sacrificed for visual effects.
- Historical contrast failures shown as evidence in “Antes” states must not be silently corrected inside the reconstruction; the case may explain them.
- Mobile must be authored at 390px/320px rather than treated as a desktop stack.
- No new dependency should be introduced only to create visual spectacle.
- No new confidential dataset numbers or unverified performance claims may enter the public case.

## 6. Evidence boundaries / unresolved factual issues

These remain gates or explicit limitations:

1. **Historical screenshots:** current before/after states are reconstructions. Replace only when verifiable screenshots are recovered.
2. **Current titles/mini-bios:** public-profile information can age; validate before final publication if changed.
3. **Recommendation logic:** the PoC explored recommendation/scenario behavior, but its effectiveness is not validated.
4. **Consent revocation:** effective revocation is not proven; do not imply it is operational.
5. **Assistive technology:** automated/static checks are not a substitute for screen-reader/user testing.
6. **Architecture vs implementation:** architecture docs are valid artifacts, but do not imply all components were live simultaneously in the event build.
7. **Dataset disclosure:** qualitative insight is public-safe; retained percentages remain non-public until explicitly authorized.

## 7. Rejected / negative visual evidence

The following are preserved as **anti-pattern evidence**, not as instructions to refine incrementally:

- V6 generic SaaS/Tailwind grammar:
  - repeated rounded cards;
  - pills/chips as default organization;
  - uniform section rhythm;
  - translucent/blurred nav;
  - team as flip-card/directory pattern.
- V7 “editorial by typography”:
  - serif + whitespace carrying too much of the authorship;
  - academic/report-like data presentation;
  - UX comparison reading as design-system documentation;
  - institutional team-directory treatment.
- Hero red-field exploration:
  - full red wall chosen for impact;
  - top black bar;
  - multiple independent floating cards/annotations;
  - provenance as a visual block;
  - mobile collapse into sequential boxes.
- Final mobile/hero exploration before freeze:
  - phone + Fernando relationship improved;
  - still too dependent on resizing/stacking rather than a fully authored responsive scene;
  - motion was being considered before whole-page art direction was locked.

**Repository decision:** stop local hero iteration. Rebuild from an upstream PRD/art-direction packet.

## 8. Constraints for the next agents

### Editorial Storyteller

May change sequence/section emphasis only when supported by the approved facts above. Must not invent stronger outcomes to create drama.

### Experience Designer

Must define responsive reading order and interaction logic for the **entire case**, not just hero geometry.

### Editorial Art Director

Must create one coherent visual world across data, Fernando, architecture, UX evolution, prototype and team. It may use the reference bank for principles, but must not inherit the red-field/V7 grammar by default.

### Creative Director

Must reject:
- generic fintech/SaaS presentation;
- “editorial” that depends mainly on serif/whitespace;
- mobile as stacked desktop;
- motion used to compensate for weak static composition;
- evidence hidden for decorative effect.

## 9. Working source map

| Need | Primary repository source |
| --- | --- |
| Factual/publication constraints | `docs/ux/editorial-case-v6-evidence.md` |
| UX/content decisions | `docs/ux/review-v6-content-team.md` |
| V7 diagnosis/anti-patterns | `docs/ux/case-v7-editorial-ui-brief.md` |
| Reference inventory | `docs/ux/visual-reference-bank-v1.md` |
| Freeze/reframe decision | `docs/ux/case-reframe-gate.md` |
| Previous rendered review | `outputs/revisao-v7.md` |
| ShiftKey extraction attempt | `outputs/shiftkey-direcao-completa.md` |
| Current implementation | `web/public/case/index.html` |
| Current delta vs main | branch compare: 6 commits ahead, 0 behind at run start |

## 10. Handoff

**Repository truth packet: READY.**

The next roles should consume this file as approved upstream context. If a later role finds a factual conflict, it must return the conflict to Repository Analyst / human authority rather than silently selecting a preferred version.
