# Studio V2 Remaining Work and Completion Plan

## Live Completion Checklist

- [x] Expose and verify the factor-library read API used by the frontend.
- [x] Expose and verify the optimizer trial-list API used by the frontend.
- [x] Expose and verify the optimizer overfitting-verdict API.
- [x] Expose and verify Data Studio catalog and freshness APIs.
- [x] Expose and verify Data Studio series, anomaly, and missingness APIs.
- [x] Expose and verify the bounded Data Studio universe builder API.
- [x] Implement and verify Algorithm Lab paper-trade execution for saved strategies.
- [x] Implement and verify Algorithm Lab strategy handoff to Backtest Studio.
- [x] Implement and verify kernel checkpoint restoration.
- [x] Implement and verify JSON, CSV/ZIP, and PDF backtest-result exports.
- [x] Connect portfolio backtesting to explicit selections from persisted strategies.
- [x] Align attribution consumers with current and compatibility response keys.
- [x] Add bounded, typed, persisted extended robustness diagnostics.
- [x] Add an explicit composite robustness contract with completeness reporting.
- [x] Align robustness panel discriminators and parameters with strict requests.
- [x] Move factor IC diagnostics from JSON query strings to a bounded POST body.
- [x] Refresh the backend handoff’s APDI references, status, and test evidence.
- [x] Populate backtest comparison from persisted historical lineage runs.
- [x] Surface backtest panel failures, including attribution, through visible errors.
- [x] Add persistent factor-library create, inspect, edit, approve, deprecate, remove, and restore workflows.
- [x] Add route-level and reusable per-panel frontend recovery boundaries.
- [x] Generate bounded deterministic Monte Carlo paths for completed backtests.
- [x] Define and expose dataset-date freshness SLOs across all Studio asset classes.
- [x] Persist optimizer studies and trials across Router instances with typed read APIs.
- [x] Expose bounded real-backtest CPCV and walk-forward optimizer APIs.
- [x] Add authenticated, quota-bounded CSV, JSON, and Parquet uploads with atomic owner-scoped storage.
- [x] Add explicit authenticated atomic manifest refreshes for selected known datasets.
- [x] Persist bounded robustness jobs with typed progress, cancellation,
  timeouts, restart recovery, and durable results.
- [x] Close the identified Algorithm Lab and Backtest HTTP API blockers.
- [x] Close the identified Robustness and Optimizer HTTP API blockers.
- [x] Add Studio hook contract, component-state, route-render, and browser-smoke coverage.
- [x] Add request IDs, aggregate HTTP telemetry, health/readiness endpoints,
  Parquet scan metrics, and manifest/data-access checks.
- [x] Refresh normalized Fama-French Parquets through June 30, 2026 and
  verify exact source-to-Parquet values.
- [x] Harden custom factor execution against reviewed amplification, timeout,
  field-discovery, and memory-accounting failures.
- [x] Persist deterministic manifest snapshot identity on new backtest lineage.
- [x] Regenerate and verify the 103-route API inventory and 84-call frontend
  traceability artifacts with zero missing calls.
- [x] Upgrade shared Studio primitives for accessible responsive navigation,
  semantic analytics, keyboard dialogs, reduced motion, and faster rendering.
- [x] Build the generational seven-environment Studio UI: Algorithm flight
  deck, Backtest forensics console, Robustness falsification chamber, Factor
  alpha observatory, Optimizer search topology, Data lineage command center,
  and Portfolio Risk loss cockpit.
- [x] Integrate custom live-result instruments across every Studio domain while
  preserving typed hooks, request states, and existing API contracts.
- [x] Add a searchable keyboard command deck and persistent research-context
  rail across the shared Studio shell.
- [x] Visually inspect all seven routes in a real browser and fix the missing
  shared base-style import discovered during the inspection.
- [ ] Complete production persistence, jobs, security, observability, and release gates.

Last audited: August 10, 2026

## Purpose

This document is the authoritative list of work that is missing, incomplete,
unverified, or not production-ready for the complete Studio V2 product. It
covers the frontend, backend integration, data operations, testing,
infrastructure, security, deployment, and documentation.

This document does not repeat backend features already closed in
`STUDIO_V2_BACKEND_GAPS.md`. A checked backend feature is treated as implemented
unless current workspace evidence contradicts it.

## Executive Status

The identified Studio V2 HTTP route gaps are closed. The regenerated inventory
proves 103 HTTP routes and one WebSocket route. Frontend traceability proves all
84 discovered frontend calls are registered, with zero missing.

The full backend run on August 10, 2026 is green: 189 tests passed with 12
third-party deprecation warnings. The factor sandbox's four audit findings are
closed, and persisted backtest lineage now records the exact deterministic data
manifest snapshot ID. Frontend evidence includes 61 passing Jest tests, a
passing TypeScript check and 185-page production build, and eight passing
Playwright Chromium route smokes after the shared Studio UI upgrade. Full real-
backend journey, production security, shared infrastructure, and deployment
gates remain incomplete.

## Status Legend

- [ ] Missing or still required
- [~] Partially implemented or present but not proven end to end
- [x] Verified baseline that does not need to be rebuilt

## Verified Baseline

- [x] Main Studio route exists at `frontend/src/app/studio/page.js`.
- [x] Backtest, robustness, factors, optimizer, data, and portfolio-risk pages
  exist under `frontend/src/app/studio/`.
- [x] Major Studio V2 visual components exist under
  `frontend/src/components/studio-v2/`.
- [x] Shared Studio hooks and stores exist.
- [x] The backend registers the Studio V2 router from `backend/main.py`.
- [x] Backend request, response, and error model infrastructure exists.
- [x] Dataset manifests and normalized Fama-French Parquets exist.
- [x] Master-universe predicate pushdown and bounded liquidity calibration exist.
- [x] The historical backend gap checklist is checked and has recorded test
  evidence.

## P0: End-to-End API Integration Blockers

These items block existing UI controls from completing their intended actions.
For each item, either implement the backend route with typed contracts or
change the frontend to use an existing equivalent route. Do not leave silent
`catch(() => {})` behavior as the final UX.

### Algorithm Lab

- [x] Implement or remove `POST /api/v2/algorithm-lab/paper-trade/run`.
  The route now matches the `AlgorithmLab.jsx` workflow.
- [x] Implement or replace `POST /api/v2/algorithm-lab/push-to-backtest`.
  `useAlgorithmLab.js` exposes this flow without a matching backend route.
- [x] Implement or replace
  `POST /api/v2/algorithm-lab/kernel/restore/{run_id}`.
- [ ] Verify the WebSocket collaboration path through the deployed reverse
  proxy, including authentication, disconnect cleanup, and reconnect behavior.
- [ ] Verify exported ZIP downloads in the real browser, including content type,
  filename, corrupted archives, and missing strategy errors.

### Backtest Studio

- [x] Implement or replace `POST /api/v2/backtest/export/{run_id}`. The frontend
  hook now has the matching backtest-result export route.
- [x] Connect `PortfolioBacktestRunner` to actual selected strategies. The
  current backtest page renders it with `strategies={[]}`.
- [x] Verify that attribution consumers use the current backend keys. The page
  reads legacy `sector_attribution` and `factor_attribution` keys while the
  backend also exposes newer `sectors` and `factors` shapes.
- [x] Populate strategy comparison with selectable historical runs. The page
  now constructs `availableRuns` from persisted historical lineage.
- [x] Verify Monte Carlo data is actually generated by the selected backtest
  workflow rather than rendering an empty state indefinitely.
- [x] Add user-visible errors to slippage, scenarios, attribution, and
  comparison panels instead of swallowing request failures.

### Robustness Lab

- [x] Implement or replace `POST /api/v2/robustness/run-extended`.
- [x] Implement or replace `GET /api/v2/robustness/composite-score`.
- [x] Confirm every robustness panel sends a payload accepted by
  `RobustnessCoreRequest`. Some components include a `test` discriminator that
  is not part of the strict backend model.
- [x] Persist long-running robustness jobs and expose progress/cancellation.
  Request-time execution alone is not sufficient for upper-bound workloads.
- [ ] Verify audit PDF download from the browser and JSON/PDF content
  negotiation.

### Factor Lab

- [x] Implement `GET /api/v2/factors/library` or update the frontend library
  hook to another authoritative endpoint.
- [x] Add complete factor-library CRUD if users are expected to create, edit,
  inspect, approve, deprecate, and restore factors from the UI. The current
  router exposes governance transitions and history, but not a complete public
  library surface.
- [x] Align IC diagnostics query encoding. Large factor/return arrays should not
  be passed as JSON query strings; use a typed POST body or stored dataset IDs.
- [x] Verify synthetic-data provenance appears in factor diagnostics when
  factor inputs overlap an explicit or detected synthetic range.
- [x] Custom factor code has AST allowlists, amplification guards, worker-bound
  preprocessing/evaluation, normalized errors, and complete input/output memory
  accounting for the reviewed paths.

### Optimizer Lab

- [x] Implement or replace `GET /api/v2/optimizer/verdict`.
- [x] Implement or replace `GET /api/v2/optimizer/trials`.
- [x] Persist optimizer studies and trials so refreshes and multiple workers do
  not lose state.
- [ ] Move long Bayesian, Pareto, ensemble, and cross-validation workloads to
  a background-job contract with progress, cancellation, and timeouts.
- [ ] Add bounded real-backtest integration tests for multi-objective search and
  ensemble output aggregation.
- [ ] Verify Optuna-unavailable behavior and all objective direction/metric
  combinations.

### Data Studio

- [x] Register or replace `GET /api/v2/data-studio/catalog`.
- [x] Register or replace `GET /api/v2/data-studio/freshness`.
- [x] Register or replace
  `GET /api/v2/data-studio/explorer/series/{ticker}`.
- [x] Register or replace `GET /api/v2/data-studio/explorer/anomalies`.
- [x] Register or replace `GET /api/v2/data-studio/explorer/heatmap`.
- [x] Register or replace `POST /api/v2/data-studio/universe/build`.
- [x] Expose custom upload through a typed, authenticated multipart endpoint if
  the upload dialog is intended to work. Validate file size, schema, formulas,
  path traversal, and storage quotas.
- [x] Add an authenticated manifest refresh workflow. Dataset updates currently
  regenerate manifest row counts, sizes, coverage, and checksums atomically.
- [x] Add freshness/service-level objectives for market universe, Category 7,
  factors, fundamentals, crypto, FX, and futures.

## P0: Frontend Testing and Reliability

Studio V2 now has hook, component-state, route-render, and real Chromium smoke
coverage. The remaining work is full-journey, collaboration, accessibility,
visual-regression, and release-matrix depth.

- [x] Add contract tests for every Studio hook against representative success
  and error payloads.
- [x] Add component tests for loading, empty, success, validation-error,
  permission-error, and server-error states.
- [x] Add browser tests for the seven Studio routes:
  `/studio`, `/studio/backtest`, `/studio/robustness`, `/studio/factors`,
  `/studio/optimizer`, `/studio/data`, and `/studio/portfolio-risk`.
- [ ] Add a full journey: create/fork strategy, execute it, push to backtest,
  inspect results, run robustness, optimize, compose a portfolio, inspect risk,
  and save a journal entry.
- [x] Test request cancellation, navigation during a request, timeout behavior,
  double submission, stale responses, retry behavior, and offline recovery.
- [ ] Test WebSocket collaboration with two clients and reconnects.
- [ ] Add accessibility checks for keyboard navigation, focus trapping, labels,
  dialogs, charts, contrast, reduced motion, and screen-reader summaries.
- [ ] Add visual regression screenshots for desktop, tablet, and narrow mobile
  layouts.
- [x] Run and record Studio tests, full lint, TypeScript, production build, and
  Playwright route smoke. Current evidence: 61 Jest tests, lint with zero errors
  and 29 warnings, TypeScript pass, 185-page build, and 8 Playwright passes.

## P1: Backend Work Not Yet Production-Grade

The analytics exist, but the following infrastructure remains necessary for a
production deployment.

### Router and contracts

- [ ] Split the 838-line `studio_v2/router.py` into domain routers for algorithm
  lab, backtest, robustness, factors, optimizer, data studio, portfolio risk,
  and journal.
- [ ] Split the 442-line contracts module by domain while keeping a composed
  OpenAPI schema.
- [ ] Remove `extra="allow"` from response models where the response is stable.
  Dynamic analytics may use typed nested maps, but stable keys should not be
  accepted silently.
- [ ] Add descriptions, units, allowed ranges, and examples for financial
  response fields.
- [x] Add request IDs to error envelopes and logs.
- [ ] Add versioning/deprecation policy for payload keys and compatibility
  aliases.
- [ ] Decide how clients obtain the API schema. The current main application
  does not expose `/openapi.json`; use an authenticated documentation route or
  publish a generated schema artifact.

### Persistence and multi-worker operation

- [ ] Replace production SQLite usage with a migration-managed database such as
  PostgreSQL, while retaining SQLite for local development if desired.
- [ ] Add schema migrations, indexes, transaction boundaries, backup/restore,
  retention, and corruption-recovery procedures.
- [ ] Move collaboration maps, job state, and cross-worker cache coordination
  to Redis or another shared service.
- [ ] Make alert ingestion idempotent across processes and repeated reads.
- [ ] Add optimistic concurrency/version checks to editable journal, snippet,
  composition, factor, and risk-limit records.

### Background jobs

- [ ] Add a durable queue for optimizer, robustness, large backtest, export, and
  audit jobs.
- [ ] Expose job creation, status, progress, cancellation, result, expiration,
  and failure endpoints.
- [ ] Enforce per-user concurrency, CPU, memory, wall-time, and output-size
  quotas.
- [ ] Recover or mark interrupted jobs after process restart.
- [ ] Keep extremely compute-heavy analyses opt-in and bounded. Do not add work
  that has no user-visible value.

### Observability

- [x] Record endpoint latency, status, request ID, payload size, and failure
  category without logging secrets or raw strategy code.
- [x] Record Parquet rows/bytes scanned and predicate-pushdown effectiveness.
- [~] Record cache hit rate, cache memory, and eviction counts. Hit/miss/rate is
  implemented for Studio data access; memory and eviction counts remain.
- [ ] Record background queue time, execution time, cancellation, and resource
  high-water marks.
- [x] Add health, readiness, and dependency checks for the database, queue,
  manifests, and data files.
- [ ] Add alerts and dashboards for error rate, latency, stale data, failed jobs,
  and checksum failures.

## P1: Remaining Backend Edge-Case Verification

These are not necessarily known defects. They remain unproven until targeted
tests demonstrate correct behavior.

- [x] Composition: missing strategies, empty compositions, duplicate strategy
  IDs, invalid/negative/non-normalized weights, and custom allocator failures.
- [x] Attribution: missing benchmark, missing sector mapping, singular factor
  regressions, empty return overlap, and mismatched calendars.
- [x] Futures: expiry gaps, missing settlement, roll boundaries, negative prices,
  ratio division by zero, and contract-table duplicates.
- [x] Synthetic data: explicit and heuristic flags through the real backtest and
  factor flows, including stored-run reload.
- [x] Journal: deterministic ordering when timestamps match, concurrent edits,
  invalid date ranges, and pagination during inserts.
- [x] Risk: unequal strategy histories, missing weights, singular covariance,
  zero volatility, extreme leverage, empty active strategy set, and alert
  deduplication.
- [x] Governance: deprecated factors excluded from every baseline and restored
  only through an explicit transition.
- [x] Optimizer: empty/disjoint preferred regions, duplicate trials, failed
  trials, NaN objectives, and mixed minimize/maximize objectives.
- [x] Data loader: unknown asset class, malformed schema, duplicate rows,
  timezone-aware ranges, missing symbols, empty ranges, and CSV fallback when
  Parquet is unavailable.
- [x] Manifest validation: intentional data refresh, checksum mismatch, partial
  file, schema migration, and atomic manifest replacement.

## P1: Frontend Integration and UX Completion

Most visual components exist, but they require systematic wiring and behavior
verification.

- [ ] Replace swallowed request failures with visible, actionable error states.
- [x] Standardize loading, empty, stale, partial, permission, validation, and
  retry states through shared primitives.
- [ ] Ensure each control is either wired to a real capability or visibly
  disabled with an explanation.
- [ ] Validate every chart against real backend payloads, including NaN, null,
  empty, negative, and extreme values.
- [ ] Add chart legends, units, accessible summaries, tooltips, source dates,
  and data-quality indicators.
- [ ] Persist selected strategy, run, universe, factor, optimizer study, and
  portfolio context across navigation and refresh.
- [x] Prevent stale cached responses from overwriting newer requests.
- [ ] Add URL-addressable state where sharing/reloading a result is expected.
- [ ] Verify responsive behavior for dense tables, Monaco editor, dialogs,
  heatmaps, correlation matrices, and risk dashboards.
- [ ] Reconcile `labPrimitives.jsx` and `remainingPrimitives.jsx` into a clearly
  owned design-system layer. Remove duplication only after import migration and
  visual regression coverage.
- [x] Add an application-level error boundary and per-panel recovery boundaries.

## P1: Security and Abuse Resistance

- [ ] Authenticate and authorize every Studio V2 route, including WebSockets,
  downloads, manifests, journal, snippets, and collaboration invites.
- [ ] Define ownership and tenant isolation for strategies, runs, compositions,
  jobs, alerts, limits, and journal entries.
- [ ] Apply CSRF protections where cookie authentication is used.
- [ ] Rate-limit execution, optimization, robustness, export, uploads, and invite
  creation independently from ordinary reads.
- [ ] Revalidate Python AST restrictions and subprocess isolation for custom
  strategy, factor, and allocator code.
- [ ] Disable network, filesystem, process creation, environment access, and
  secret access inside code-execution workers unless explicitly required.
- [ ] Add archive decompression and spreadsheet/CSV formula-injection defenses.
- [ ] Add audit events for execution, data upload, factor governance, risk-limit
  changes, collaboration, exports, and administrative actions.
- [ ] Run dependency, static security, and secret scans as CI gates.

## P2: Data Operations and Reproducibility

- [ ] Create one shared market-data package instead of maintaining similar
  loaders across Studio V2, Factors V2, PCA V2, Portfolio V2, Research V2,
  Screener V2, ML V2, and Volatility V2.
- [ ] Define schema versions and migration rules for every Parquet dataset.
- [x] Make Studio manifest dataset refresh atomic: write temporary file, validate, update
  manifest, then swap.
- [x] Store source provenance, licensing, transformation version, and generation
  command in manifests.
- [ ] Add point-in-time and survivorship guarantees for backtest datasets.
- [ ] Define adjustment policy for splits, dividends, symbol changes, delistings,
  and futures rolls.
- [~] Persist reproducible manifest snapshot IDs. New backtest lineage records
  now store them; extend the same identity to optimizer, robustness, factor,
  portfolio, and exported analytical artifacts.
- [ ] Add data retention and cleanup for custom uploads and generated artifacts.

## P2: Deployment and Release Engineering

- [ ] Add a production deployment topology for frontend, API workers, job
  workers, database, Redis/queue, object storage, and monitoring.
- [ ] Add environment validation for required paths, secrets, database URLs,
  queue URLs, worker limits, and frontend API base URL.
- [ ] Add CI stages for backend compile/lint/tests, frontend lint/tests/build,
  OpenAPI compatibility, manifest validation, security scans, and browser smoke.
- [ ] Add staging with representative data volumes and production-like worker
  counts.
- [ ] Add database migrations and rollback to the deployment procedure.
- [ ] Add canary/rollback strategy and release health checks.
- [ ] Add backup restore drills and disaster-recovery targets.
- [ ] Publish an operational runbook for stale data, failed manifests, stuck
  jobs, high memory, database failure, and WebSocket incidents.

## P2: Documentation Still Required

- [x] Generate and validate the API inventory for the 103-route live router,
  including the route-specific readiness 503 response contract.
  an artifact even if production OpenAPI access remains protected.
- [x] Generate frontend-to-backend traceability: 84 of 84 discovered calls are
  registered against the current router, with zero missing.
  request model, response model, and error behavior.
- [ ] Add data dictionary and units for every financial field.
- [ ] Add operator documentation for data refresh and manifest regeneration.
- [ ] Add user documentation for each Studio workflow and its limitations.
- [ ] Add architecture diagrams for request flow, job flow, data flow,
  persistence, and collaboration.
- [x] Replace stale statements in `STUDIO_V2_BACKEND_HANDOFF.md`, including old
  pre-final test counts and references to APDI loading.

## Explicitly Not Required Unless Product Needs It

The following work should not be added merely to maximize computation:

- [ ] Unbounded Monte Carlo or robustness simulation counts.
- [ ] Automatic 121-point parameter grids on every interaction.
- [ ] Large optimizer searches without an explicit user request and budget.
- [ ] Full-universe in-memory loads when projected Parquet reads satisfy the
  workflow.
- [ ] Continuous recomputation of results that can be cached or persisted.
- [ ] Expensive analytics that do not change a decision or user-visible result.

These items remain intentionally excluded unless a concrete user workflow,
latency budget, resource budget, and acceptance test justify them.

## Recommended Completion Order

1. Complete the primary real-backend create-strategy-to-risk journey.
2. Extend data snapshot identity beyond backtest lineage to every persisted
   analytical artifact.
3. Close the remaining repository-wide frontend lint warnings without hiding
   them through blanket suppressions.
4. Add real-backend authentication, download, and collaboration browser tests.
5. Verify WebSocket collaboration and exported downloads through the deployed
   proxy and browser.
6. Add shared durable jobs for optimizer, large backtest, export, and audit
   work; retain the completed robustness lifecycle.
7. Move shared production state to PostgreSQL and Redis/queue infrastructure.
8. Complete security, authorization, accessibility, and visual-regression
   testing.
9. Add staging, CI gates, dashboards, deployment, backup, and operational
   runbooks.
10. Run the final release acceptance checklist below on one frozen revision.

## Release Acceptance Checklist

Studio V2 is complete only when all of the following are true:

- [ ] Every visible UI action calls a registered backend route or is explicitly
  disabled.
- [ ] Every route has tested request, success response, and error contracts.
- [x] All seven Studio pages pass component and browser smoke tests.
- [ ] The complete user journey passes against the real application and real
  persisted data.
- [ ] No request failure is silently swallowed.
- [ ] Long-running work is bounded, observable, cancellable, and durable.
- [x] Data files and manifests validate after a production-style refresh.
- [ ] Authentication, authorization, tenant isolation, and code sandboxing pass
  security review.
- [x] Frontend lint, Studio tests, TypeScript, production build, and Studio
  browser smoke pass. Current evidence: 64 Jest tests, 8 Playwright passes,
  TypeScript pass, 185-page build, and lint with zero errors and 29 warnings.
- [ ] Backend lint, compile, tests, and real-app smoke pass.
- [ ] API compatibility and frontend/backend route-diff checks pass in CI.
- [ ] Staging load tests meet documented latency and memory budgets.
- [ ] Database, queue, cache, object storage, backup, rollback, and monitoring
  procedures are operational.
- [ ] User, developer, data-operations, and incident-response documentation is
  current.

## Evidence Used for This Audit

- `STUDIO_V2_BACKEND_GAPS.md`
- `docs/STUDIO_V2_BACKEND_HANDOFF.md`
- `backend/app/studio_v2/router.py`
- `backend/app/studio_v2/contracts.py`
- `backend/app/studio_v2/shared/data_loader.py`
- `backend/app/studio_v2/shared/data_manifest.py`
- `frontend/src/app/studio/`
- `frontend/src/components/studio-v2/`
- `frontend/src/hooks/studio/`
- `frontend/src/stores/studio/`
- `frontend/package.json`

This audit is intentionally conservative. An item is marked remaining when the
workspace does not contain direct evidence that the complete production
behavior has been implemented and verified.
