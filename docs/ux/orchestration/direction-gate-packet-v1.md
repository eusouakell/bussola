# Bússola — Direction / PRD Gate packet V1

**Workflow:** `bussola-public-case-v1`  
**State:** waiting for Kell  
**Quality Gate A:** PASS  
**Production:** frozen

## What changed in this run

Instead of iterating another hero in code, the workflow consolidated the work upstream:

1. repository truth;
2. reference principles;
3. narrative architecture;
4. experience structure;
5. art direction;
6. independent creative preflight.

## The proposal in one paragraph

The case should tell one precise story: a synthetic-data signal exposed a mismatch between visible balance and financial pressure; the team turned that tension into a goal-first agent PoC during the hackathon; later UX/content work revisited the experience to make choices, effort and consent clearer.

The visual idea is **“O que aparece / o que pesa”**: human scale, product surfaces and evidence share one composition. Warm white + ink/navy form the base; existing orange marks decisions. No full-wall campaign color, no generic card grid, no serif-as-editorial shortcut, no motion required for the composition.

## Review only these artifacts

### 1. Repository truth
`docs/ux/orchestration/case-context-packet-v1.md`

### 2. Reference synthesis
`docs/ux/orchestration/reference-synthesis-v1.md`

### 3. Narrative
`docs/ux/orchestration/narrative-architecture-v1.md`

### 4. Experience structure
`docs/ux/orchestration/experience-structure-v1.md`

### 5. Art direction
`docs/ux/orchestration/art-direction-packet-v1.md`

### 6. Representative proof
`outputs/art-direction-v1/proof-sheet.html`

### 7. Independent preflight
`docs/ux/orchestration/creative-preflight-v1.md`

## Decisions already resolved upstream

Do not reopen unless Kell explicitly requests it:

- public case is PoC + later refinement, not production banking product;
- Fernando remains a narrative persona with AI-image disclosure;
- retained hackathon percentages remain out of the public page;
- reconstructed UI states remain labelled;
- debt/rotativo insight sits in Discovery, not as a second hero artifact;
- mobile is recomposed, not stacked desktop;
- motion is downstream progressive enhancement.

## What Kell is deciding now

Only three questions:

1. **Narrative:** is the hook → discovery → Fernando → product decision → PoC → later UX refinement → evidence/team/colophon arc the right story?
2. **Experience:** is the information hierarchy and responsive behavior appropriate?
3. **Art direction:** is “O que aparece / o que pesa” the visual world we should execute?

## Allowed gate responses

- **APPROVE** — production roles may begin.
- **REVISE: <owner + issue>** — return one focused problem to the correct upstream role.
- **STOP / REFRAME** — reject the underlying story/direction.

Do not provide implementation micro-feedback at this gate. Production details come later.

## If approved

The next route is:

`visual/interface execution → optional motion if justified → frontend → accessibility + code review → readiness → final Kell merge gate`
