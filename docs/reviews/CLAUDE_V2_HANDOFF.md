# Claude handoff: ML and PCA V2 frontend

Date: 2026-10-05. Repository: https://github.com/aditya160509/quant-lens (private), branch `main`.

## Start here

Read `docs/reviews/V2_REBUILD_PLAYBOOK.md`, then the ML/PCA review status notes and each module's `DONE.md`. Those records distinguish supported features from exclusions. Backend work is committed; the frontend rebuild is reserved for Claude by the user and Phase 4 of the playbook.

ML implementation commits: `349ec94a`, `4a21b431`; verification repairs: `ad94905b`; rebuild documentation: `9d2ae903`. PCA rebuild: `1011a999`.

## Work to do

1. Check the backend manifests and actual response envelopes before editing. Build forms from backend `INPUTS` and render outputs from `OUTPUTS`; do not maintain another feature contract in the frontend.
2. Rebuild ML and PCA frontend wiring, forms, renderers and workbenches using the playbook's Phase 4 layout. Use each module's own symbol search, validated uploads and background jobs. Confirm router prefixes and singular/plural feature paths against the actual routers.
3. Show validation errors, job failures, missing-output reasons and documented limitations. Remove demo results and unsupported controls. Never fill missing values with plausible numbers or label an approximation as a real estimator.
4. Preserve truthful labels: ML CPCV curves are hypothetical label-payoff diagnostics; PBO requires an actual dated strategy-trial matrix; DML reports conditional associations. Present-day sectors/universes do not establish historical membership. PCA F08 requires `rolling_refit` for causal historical residuals. Read both DONE files for the full limitations.
5. Add relevant frontend payload, renderer and missing-output tests. Run Jest, lint, TypeScript and production build, then exercise one feature per rebuilt module end to end in the browser and check console errors. Record exact commands and results.
6. Commit in logical steps and update the review status/DONE records with actual frontend verification. If the frontend exposes a backend defect, report the reproducible request and fix only the necessary scope.

Do not redesign other V2 modules or change V1 behavior as part of this handoff. Before deleting old frontend files, check callers, imports and routes with the graph and `rg`.

## Verified baseline

- ML: 40 backend tests passed; all 12 supported features passed real-local-data smoke runs.
- PCA: 30 backend tests passed; all 11 features passed real-local-data smoke runs.
- Frontend: 41 Jest suites / 152 tests passed; lint passed with zero errors and 20 warnings; TypeScript and production build passed.
- Browser verification was waived by the user for the backend pass and has not been performed. It remains necessary to claim frontend end-to-end completion.

These results prove the recorded checks, not complete implementation of every original spec proposal. Unsupported features and runtime limitations remain listed in each module's DONE file.

## Local working tree

At handoff, unrelated uncommitted Research V2 edits and new review/spec documents remain in the shared checkout. They were deliberately excluded from these commits. Inspect `git status` and preserve them; do not reset, overwrite or include them in a frontend commit without reviewing their ownership and scope.
