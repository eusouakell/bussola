# Bússola V2 — Final publication packet

**State:** publish-ready candidate  
**Human action required:** final publication / merge decision only  
**PR:** https://github.com/eusouakell/bussola/pull/13

## Candidate

Staging candidate:

https://raw.githack.com/eusouakell/bussola/6a2d1dbf8c7cbfac3dd5f7e20a30a9c151d89524/web/public/case/index.html

The staging proxy may show its standard third-party-content interstitial. The production destination after merge is:

https://eusouakell.github.io/bussola/case/

## What materially changed

1. The case is one narrative rather than a collection of product/design modules.
2. Discovery is treated as qualitative evidence, with synthetic-data and publication limits explicit.
3. Fernando, product UI and evidence share one authored visual system instead of generic fintech/card grammar.
4. UX/content refinement is shown through four readable decisions, not device-shell documentation.
5. Prototype, architecture and team are evidence surfaces with honest PoC / later-refinement / collective-authorship boundaries.

## Quality

- weighted council calibration: **9.42 / 10**;
- lowest applicable dimension: **9.1 / 10**;
- release blockers: **0**;
- open material questions: **0**;
- unresolved dissent: **0**;
- recommendation: **PUBLISH**.

Full review: `docs/ux/case-v2-council-review.md`

## Visual evidence

Desktop:
- `outputs/case-v2-qa/desktop-hero.png`
- `outputs/case-v2-qa/desktop-discovery.png`
- `outputs/case-v2-qa/desktop-evolution.png`
- `outputs/case-v2-qa/desktop-team.png`

390:
- `outputs/case-v2-qa/mobile-390-hero.png`
- `outputs/case-v2-qa/mobile-390-discovery.png`
- `outputs/case-v2-qa/mobile-390-evolution.png`
- `outputs/case-v2-qa/mobile-390-team.png`

320:
- `outputs/case-v2-qa/mobile-320-hero.png`
- `outputs/case-v2-qa/mobile-320-discovery.png`
- `outputs/case-v2-qa/mobile-320-evolution.png`
- `outputs/case-v2-qa/mobile-320-team.png`

## Browser release QA

- anchor navigation: PASS;
- images: PASS;
- horizontal overflow / blank sections: no blocker observed;
- prototype iframe: PASS after canonical-URL correction;
- prototype external launch: PASS.

## Residual risks

Only limitations already disclosed in the case remain: no complete assistive-tech user study, no validated recommendation efficacy, no claim of real consent revocation, reconstructed historical UI states, reference architecture rather than production certification.

## Final decision

- **APPROVE PUBLISH** → merge PR #13; Pages deployment publishes the case.
- **REJECT WITH ONE MATERIAL REASON** → route only that issue back to its owning discipline.

Do not reopen resolved craft choices as preference-level micro-iterations at this gate.
