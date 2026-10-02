# Public prototype revival

Goal: put the Bússola prototype online again without depending on live GCP services for the public portfolio/demo.

## Recommended public mode

Use the existing **simulado** front as a static GitHub Pages deployment.

Why:
- uses synthetic data only;
- requires no API key, Secret Manager or BigQuery;
- does not expose the ADK/MCP stack;
- remains useful for demonstrating the journey, guardrails, consent and audit views;
- can be deployed from the fork independently of the hackathon GCP environment.

Expected URL after Pages is enabled:

`https://eusouakell.github.io/bussola/`

## What this branch adds

- configurable Vite base path;
- subpath-safe favicon;
- GitHub Pages workflow;
- CI gates before deployment;
- build forced to `VITE_BUSSOLA_MODO=simulado`.

## One manual repository setting

In GitHub:

**Settings → Pages → Build and deployment → Source → GitHub Actions**

The workflow can then be triggered manually or by a change under `web/` merged into `main`.

## Live mode remains separate

The Cloud Run architecture is still documented and can be restored separately.

That path depends on:
- current access to GCP project `batalha-time-07-lkbv`;
- valid WIF variables / deploy service account;
- existing Secret Manager configuration;
- current Cloud Run services and IAM;
- smoke testing before promotion;
- explicit human confirmation before traffic changes.

Do not make the public portfolio depend on that infrastructure unless there is a reason to demonstrate the live agent rather than the product journey.

## Validation after first deploy

- open the Pages URL on desktop and mobile;
- complete the default apartment journey;
- open Bastidores;
- test E1/E2 guardrails;
- test E3/E4/E5 simulated edge cases;
- verify no requests leave the browser during simulated operation;
- run keyboard/accessibility smoke checks;
- confirm the "dados sintéticos" disclosure remains visible.
