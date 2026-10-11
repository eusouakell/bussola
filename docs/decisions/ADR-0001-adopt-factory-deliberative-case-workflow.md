# ADR-0001 — Adopt Agentic Factory creative convergence for the public case

**Status:** proposed — merge implies acceptance  
**Decision owner:** Kell  
**Scope:** Bússola public-case workflow only  
**Date:** 2026-10-11

## Canonical shared decisions

This repository consumes, and does not redefine:

- Agentic Factory ADR-0001 — cross-repository decision governance;
- Agentic Factory Creative Convergence V1;
- Agentic Factory Deliberative Quality Loop V1.

Canonical authority remains in `eusouakell/agentic-factory`.

## Local decision

For the Bússola public case:

- reversible intermediate narrative, experience, visual and implementation decisions use bounded internal deliberation;
- ordinary specialist disagreement is resolved through owner → challenger → arbiter;
- factual/product truth remains owned by this repository and its evidence;
- publication and merge remain Kell-owned;
- an intermediate human review is an exception, not the default workflow;
- the final candidate must satisfy the publish-readiness rubric before the PR leaves Draft.

## Why

Previous iterations repeatedly used Kell as the integration layer between content, UX, visual direction and implementation. The intended operating model is different: Kell defines the outcome and final publication authority; the workflow resolves routine craft questions before surfacing the result.

## Consequences

- this repository stores project evidence and local adoption consequences;
- shared orchestration policy is linked, not copied;
- PR #13 is the first validation of this adoption;
- unresolved authority, consent, confidentiality or evidence conflicts still escalate to Kell.

## Related

- https://github.com/eusouakell/agentic-factory/blob/main/docs/decisions/ADR-0001-cross-repository-decision-governance.md
- https://github.com/eusouakell/agentic-factory/blob/main/docs/orchestration/creative-convergence-v1.md
- https://github.com/eusouakell/agentic-factory/blob/main/docs/orchestration/deliberative-quality-loop-v1.md
- https://github.com/eusouakell/agentic-factory/pull/41
- PR #13
