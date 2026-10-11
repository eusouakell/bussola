# Bússola V2 — Publish-readiness council review

**Workflow:** `bussola-public-case-v2-deliberative`  
**Candidate:** `case/publish-ready-v2`  
**Review date:** 2026-10-11  
**Verdict:** **READY FOR FINAL HUMAN PUBLICATION GATE**

> Runtime note: Agentic Factory A2 does not yet invoke isolated model agents. This is a role-separated, contract-based council review executed through one orchestration surface. Authority, reviewer lenses, challenges and evidence are separated in the artifacts; runtime agent isolation remains infrastructure work.

## Resolved blockers discovered during release challenge

### 1. Prototype embed — RESOLVED

**Owner:** Frontend Engineer  
**Challenger:** Readiness / browser QA  
**Finding:** the branch-staging environment exposed that relative `../` prototype URLs produced a 404 in the embedded evidence.

**Resolution:** case links and iframe now use the canonical public prototype URL:

`https://eusouakell.github.io/bussola/`

**Re-check:** live-browser QA confirmed both the iframe and external launch link load successfully.

### 2. Visual QA evidence — RESOLVED

**Owner:** Test / Readiness  
**Challenger:** Creative Director / Experience review  
**Finding:** the first screenshot automation produced misleading evidence: several files labelled Discovery, Evolution and Team still showed the hero because section scrolling was not reliably captured.

**Resolution:** visual-QA capture was rebuilt to isolate each target section in a QA-only page before capture.

**Re-check:** the committed renders now show the intended sections at 1440, 390 and 320 px.

## Quality council

Scores are calibration signals. Blockers remain authoritative.

| Dimension | Primary review lens | Score | Evidence / rationale | Status |
| --- | --- | ---: | --- | --- |
| Narrative | Editorial Storyteller | 9.6 | Hook → discovery → consequence → product → PoC → later refinement → collective authorship → limits is coherent and scannable. | PASS |
| Content design | Experience + editorial | 9.5 | Each section has one job; labels and limitations reduce ambiguity without legalistic repetition. | PASS |
| Art direction | Editorial Art Director + Creative Director | 9.3 | One restrained visual world; evidence/rules/scale replace SaaS card grammar; hero is memorable without campaign effects. | PASS |
| Product evidence | Repository Analyst + Experience | 9.5 | Synthetic data, architecture, reconstructions and prototype are clearly distinguished and materially support the story. | PASS |
| Responsive / mobile | Experience Designer | 9.3 | 390/320 are recomposed; section hierarchy survives narrow screens; no desktop two-column comparison is merely shrunk. | PASS |
| Accessibility / inclusion | Accessibility lens | 9.1 | Semantic hierarchy, skip link, focus, reduced motion, contrast and mobile reflow are covered; full assistive-tech user testing remains explicitly unclaimed. | PASS |
| Technical quality | Code review | 9.4 | Static implementation, no new framework/dependency, canonical prototype links, CI/build/tests, and bounded motion. | PASS |
| Provenance / honesty | Repository Analyst + Readiness | 9.8 | Synthetic/persona/AI/reconstruction/PoC boundaries are explicit; retained data claims remain unpublished. | PASS |
| Motion / interaction | Motion + accessibility lenses | 9.4 | Motion is optional one-time progressive enhancement; static state is complete and reduced-motion behavior exists. | PASS |
| Memorability / coherence | Creative Director | 9.4 | “O saldo está no azul. E a dívida?” plus “o que aparece / o que pesa” persists from opening through evidence and closing. | PASS |

**Weighted council calibration:** **9.42 / 10**  
**Lowest dimension:** **9.1 / 10**  
**Required threshold:** weighted ≥ 9.2; every applicable dimension ≥ 9.0.

## Deterministic / release evidence

- one H1 and semantic anchor structure;
- skip link and visible focus;
- `prefers-reduced-motion` path;
- four explicit Before/After UX comparisons;
- five local team portraits with visible contributions and LinkedIn links;
- retained confidential percentages excluded;
- absolute canonical prototype iframe/link;
- browser QA: navigation anchors, images, full-page layout and prototype evidence pass;
- visual QA renders inspected at 1440, 390 and 320;
- GitHub CI is the source of truth for lint/test/build status on the final PR head.

## Visual inspection notes

### Desktop

- Hero: authored person + product scene; no secondary evidence overload.
- Discovery: strong evidence hierarchy; relationship is legible before explanatory copy.
- Evolution: craft is visible at artifact scale rather than inside device mockups.
- Team: documentary scale and uneven composition avoid leadership-directory grammar.

### 390 / 320

- Headline hierarchy remains intentional rather than mechanically scaled.
- Discovery and Evolution preserve their editorial identity.
- Team credits become linear without hiding essential information.
- No visual dependency on hover or motion was found.

## Residual risks — accepted as disclosed limitations

These are not release blockers because the page states them explicitly:

1. no complete screen-reader/user assistive-tech study;
2. recommendation effectiveness remains unvalidated;
3. consent revocation is not claimed as proven operational behavior;
4. Before/After artifacts are editorial reconstructions;
5. architecture is a reference artifact, not a production certification;
6. financial dataset is synthetic and retained event percentages remain non-public.

## Open material questions

**0**

## Unresolved specialist dissent

**0**

## Release blockers

**0**

## Recommendation

**PUBLISH**, subject to Kell's final merge/publication decision.
