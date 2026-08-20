# SDLC Brainstorm Brief

This brief accompanies [`SDLC-brainstorm.pptx`](SDLC-brainstorm.pptx). It is the editable content
source for a discussion about the repository's AI-assisted software delivery control plane.

## Working thesis

SDLC turns an ambiguous product goal into an observable, reviewable, locally runnable artifact.
Specialist agents do the work, while an explicit state machine, bounded tools, runtime evidence,
security review, and fail-closed gates control the delivery.

## Latest run: what failed

Session `352113f34cb642009348f1f7a4ff30a4` ran from 23:08 to 23:12 Pacific time on 19 August 2026.
The generated React login UI met the static requirements, but QA could not start Vitest because
frontend dependencies had not been installed. The QA report said it was blocked, yet the
Verification stage was recorded as passed. The final reviewer correctly rejected the delivery.

Two distinct defects caused the outcome:

1. Frontend dependency preparation occurred during Preview, after QA and final review.
2. Verification treated agent prose as evidence but had no explicit machine-readable verdict gate.

## Changes made

- Frontend test execution now rejects floating `latest` dependencies.
- The test tool creates and preserves `package-lock.json` when needed, installs with `npm ci
  --ignore-scripts`, executes the suite, and removes transient `node_modules` afterward.
- QA must begin with `QA PASSED` or `QA BLOCKED`.
- Security review must begin with `SECURITY PASSED` or `SECURITY BLOCKED`.
- Verification fails immediately on a blocked or missing verdict.
- A regression test proves that blocked QA cannot complete Verification or invoke final review.
- Frontend and infrastructure agent guidance now requires reproducible dependency and container
  builds.

## Discussion prompts

1. Which delivery archetypes should SDLC support first: static web, API service, data pipeline, or
   infrastructure change?
2. What constitutes sufficient runtime proof for each archetype?
3. Should a blocked run fail immediately or enter a bounded automated remediation loop?
4. Which controls belong in deterministic code versus agent prompts or signed policy manifests?
5. How should reusable tools earn, retain, and lose trusted status?
6. Which operational metrics change decisions rather than merely describe activity?

## Proposed north star

Measure verified, locally runnable deliveries per unit of time and cost. Count a delivery only when
runtime QA, security review, final review, packaging, and preview all pass.

## Suggested 30 / 60 / 90-day path

- **30 days:** structured verdict schemas, browser test harness, failure taxonomy, golden workflow
  fixtures, and dashboarded gate reasons.
- **60 days:** bounded remediation loops, project-type policy profiles, provenance/SBOM support,
  and a lifecycle for reusable tools.
- **90 days:** outcome-linked scoring, cross-run pattern analysis, human-feedback calibration, and
  portfolio-level policy controls.

## Rebuilding the deck

Install the `converters` extra, then run:

```bash
python scripts/generate_sdlc_presentation.py
```

The deck uses editable PowerPoint text and shapes plus the project visuals under `docs/assets/`.
