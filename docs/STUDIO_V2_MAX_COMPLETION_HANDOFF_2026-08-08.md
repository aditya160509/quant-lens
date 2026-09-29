# Studio V2 Maximum Completion Handoff

**Freeze date:** August 8, 2026  
**Workspace:** `/Users/adityabalaji/Downloads/quant  2`  
**Authoritative checklist:** `docs/STUDIO_V2_REMAINING_WORK.md`  
**Status:** Major product and backend gaps closed; not yet production-release complete

## August 10, 2026 Upgrade Pass

This section supersedes the older frozen counts elsewhere in this historical
handoff.

- Full backend: **189 passed, 12 third-party warnings, zero failures**.
- Generated API inventory: **103 HTTP plus one WebSocket route**, current and
  passing its drift check.
- Frontend traceability: **84 of 84 calls registered, zero missing**, current
  and passing its drift check.
- Factor sandbox: all four audit findings closed; 44 focused tests and 127
  adjacent tests passed. Amplification guards, `vix` discovery, column-index
  memory accounting, and worker-bounded preprocessing are implemented.
- Data reproducibility: every new backtest lineage record stores the exact
  deterministic manifest snapshot and legacy lineage files remain compatible.
- Studio frontend: shared primitives were rebuilt as an accessible high-density
  institutional control plane across all seven routes. Framer Motion and row
  animation were removed from hot shared paths; charts use memoized linear
  normalization; large panels use `content-visibility`; navigation, dialogs,
  tables, heatmaps, focus, reduced motion, and mobile behavior were upgraded.
- Frontend verification after the upgrade: **61 Jest tests passed, TypeScript
  passed, production build passed for 185 pages, and Playwright passed 8 of 8**.
- Repository lint now exits successfully with **zero errors and 29 warnings**.
  The four blocking React lint errors were fixed without suppressions. The
  final production build and Playwright run were repeated on the finished tree.
- The remaining release work is the real-backend persisted journey, production
  authentication/authorization and tenant isolation, shared database/queue
  infrastructure, deployment operations, deeper accessibility/visual testing,
  and propagating snapshot IDs to non-backtest stored artifacts.

### Generational Studio UI pass

- Algorithm Lab is now an IDE-grade research flight deck with explicit author,
  guard, execute, and forward states, research assets, execution dock, variable
  inspection, quality gates, paper routing, and run history.
- Backtest Studio is now an execution-forensics console with simulation-chain
  navigation, a credibility dossier, DSR/PBO/PSR emphasis, event integrity,
  attribution, lineage, Monte Carlo, reconciliation, and dynamic heavy panels.
- Robustness Lab is now a falsification chamber with evidence protocols,
  completion telemetry, stability/noise/timing/universe/cost/capacity surfaces,
  radar topology, adversarial testing, and composite certification.
- Factor Sandbox is now an alpha observatory with a signal helix, honest
  eight-metric IC verdict, decay, distribution, crowding, orthogonalization,
  interaction, regime, comparison, library, and governance instrumentation.
- Optimizer is now a search observatory with topology radar, live trial
  telemetry, and explicit Explore, Survive Time, and Decide stages.
- Data Studio is now a point-in-time lineage command center connecting source,
  universe, series, and reality layers with quality and liquidity evidence.
- Portfolio Risk is now a loss cockpit with confidence gauge, exposure ledger,
  breach-aware policy state, alerts, and a collapsible raw-observation console.
- The shared shell adds a searchable keyboard command deck and a seven-cell
  research-context rail. Domain visuals remain responsive, reduced-motion
  aware, accessible, and free of unnecessary heavy animation dependencies.
- Real-browser inspection of all seven routes found and fixed a missing base
  stylesheet import that had left the market tape and brand unstyled on six
  pages. This defect was invisible to compilation and unit tests.
- Final integrated evidence: full lint exits with zero errors and 29 warnings,
  six Jest suites pass 64 tests, TypeScript passes, the production build emits
  185 pages, and Playwright passes all eight Studio route smokes.

## 1. Executive Summary

This document freezes the work completed across Studio V2 and records what is
still required. It consolidates the primary agent's work and the final reports
from all agents that were active before the documentation freeze.

The implementation is materially beyond the original review state. The seven
Studio routes exist, the identified frontend-to-backend HTTP mismatches were
closed, the core analytics have typed contracts, long robustness workloads now
have a durable job lifecycle, optimizer studies persist, factor governance is
persistent, data access uses normalized manifest-backed Parquet files, and the
frontend has hook, component, route, and real-browser smoke coverage.

It is not honest to call the product production complete. The August 10
backend run is **189 passed with zero failures**, and the finished frontend tree
passes lint, Studio Jest, TypeScript, the 185-page production build, and all
eight Playwright smokes. The highest-value next work is now the real persisted
end-to-end journey, production infrastructure and security, deeper browser and
accessibility coverage, and snapshot identity for non-backtest artifacts.

## 2. Frozen Verification Ledger

### Backend

| Check | Frozen result | Interpretation |
|---|---:|---|
| Full `backend/tests` pytest run | 189 passed, 12 warnings | Fully green; warnings originate from third-party deprecations |
| Robustness job tests | 8 passed | Durable lifecycle, cancellation, timeout, restart recovery, and typed results are covered |
| Optimizer edge and adjacent tests | 13 passed | Empty, duplicate, failed, NaN, all-failed, and direction edge cases are covered |
| Optimizer CPCV and walk-forward focused tests | 4 passed; 54 shared tests passed | New bounded temporal routes and shared contracts were green when finalized |
| Factor sandbox tests | 44 passed; 127 adjacent passed | All four reviewed resource, field-discovery, accounting, and timeout findings are closed |
| Upload and manifest focused tests | 6 passed; broader scoped run 63 passed | Auth, validation, owner storage, atomic refresh, and error paths are covered |
| Data loader and manifest edge tests | 11 focused tests | Schema, timezone, dedupe, fallback, atomic install, rollback, and telemetry are covered |
| Observability, health, and related focused group | 51 passed | Request IDs, aggregate telemetry, health, readiness, and data metrics are integrated |
| Python compile check | Passed for interrupted manifest file | `data_manifest.py` is structurally intact after the interrupted edit |

The prior readiness-response, traceability-drift, and FF3 row-count failures are
fixed. The inventory retains strict `ErrorResponse` enforcement while allowing
the readiness route's intentional typed 503 response. Factor row assertions
derive from the live manifest instead of obsolete constants.

### Frontend

| Check | Last verified result | Freeze caveat |
|---|---:|---|
| Studio Jest suites | 5 suites, 61 tests passed | Passed on the finished upgrade tree |
| Real Chromium route smoke | 8 of 8 passed | Seven desktop routes plus narrow-mobile Data Studio |
| TypeScript | Passed | Verified after the frontend upgrade |
| Production build | Passed, 185 pages | Repeated on the final tree |
| Full repository lint | 0 errors, 29 warnings | Exits successfully; remaining findings are non-blocking warnings |

The Playwright suite uses deterministic API interception. It proves production
page shells, visible route identity, enabled core actions, and the absence of
unexpected page, console, and intercepted API failures. It does not prove a
real backend journey, authentication, multi-client collaboration, or every
compute action.

## 3. Completed Backend Work

### 3.1 Typed API surface and contracts

- Registered the Studio V2 router in the main application.
- Added explicit request, response, and structured error models across the
  Studio domains.
- Closed the identified HTTP route gaps for Algorithm Lab, Backtest,
  Robustness, Factors, Optimizer, and Data Studio.
- Added request IDs to error details and response headers.
- Added route-aware aggregate latency, status, request-size, response-size,
  and failure-category metrics without recording raw strategy code or bodies.
- Added liveness, readiness, and metrics endpoints.
- Added API-inventory and frontend-traceability generators and tests.

The live router has **103 HTTP routes and one WebSocket route**. The last
successfully generated inventory covers the earlier 100-route state and must be
regenerated after the readiness validator is corrected.

### 3.2 Algorithm Lab and Backtest Studio

- Implemented paper-trade execution for saved strategies.
- Implemented strategy handoff from Algorithm Lab to Backtest Studio.
- Implemented kernel checkpoint restoration.
- Implemented JSON, CSV/ZIP, and PDF backtest result exports.
- Connected portfolio backtesting to explicit persisted strategy selections.
- Added historical lineage runs to backtest comparison.
- Aligned attribution consumers with current and compatibility keys.
- Added visible panel failures instead of silently swallowing errors.
- Added bounded deterministic Monte Carlo paths for completed backtests.
- Added route-level and panel-level recovery boundaries on the frontend.

Browser verification of real downloads, WebSocket proxy behavior, and one
complete persisted strategy-to-risk journey remains.

### 3.3 Robustness Lab

- Added bounded typed extended diagnostics.
- Added composite robustness output with completeness reporting.
- Aligned panel discriminators and request parameters.
- Added SQLite-backed durable jobs with queued, running, completed, failed,
  cancelled, and recovered states.
- Added subprocess isolation, hard cancellation, timeouts, input/output caps,
  queue limits, and concurrency limits.
- Added typed create, status, cancel, and result routes.
- Added restart recovery and durable result retrieval.

This closes the local durable-job requirement for robustness. It does not
replace the production need for a shared database and job queue.

### 3.4 Optimizer Lab

- Added SQLite persistence for optimizer studies and trials.
- Added typed paginated study and trial read APIs.
- Added overfitting verdict retrieval.
- Added bounded real-backtest CPCV and walk-forward routes.
- Added strict temporal-validation contracts and real master-universe inputs.
- Bounded CPCV to 28 paths, 756 sessions, and 10 tickers.
- Bounded walk-forward work to 6 candidates, 8 windows, and 756 sessions.
- Kept probability of backtest overfitting null when the evidence cannot
  support an honest estimate.
- Hardened cross-validation, multi-objective, search, ensemble, and registry
  behavior for empty, duplicate, failed, nonfinite, and mixed-direction trials.
- Prevented invalid objectives from corrupting persisted best-trial selection.

Long Bayesian, Pareto, ensemble, and cross-validation workloads still need a
shared background-job contract for production multi-worker operation.

### 3.5 Factor Lab

- Added persistent factor library creation, inspection, editing, approval,
  deprecation, removal, restoration, and history.
- Added bounded typed POST bodies for information-coefficient diagnostics.
- Added synthetic-data provenance propagation.
- Added expression evaluation with AST allowlists, private and dunder access
  rejection, unsafe-call rejection, source/AST/input/output limits, subprocess
  timeout, numeric-output validation, normalized errors, and vectorized
  time-series rank.

The final security review found four open issues:

1. **High:** sequence repetition and nested exponent expressions can amplify
   CPU or memory before post-output limits apply.
2. **Medium:** `vix` validates as a factor field but is missing from runtime
   field discovery, producing a worker `NameError`.
3. **Medium:** DataFrame byte accounting excludes column-index memory.
4. **Medium/low:** input loading, frame construction, winsorization, and
   normalization occur outside the timed worker.

The review found no direct import escape, dunder escape, NumPy/pandas I/O path,
arbitrary-code execution path, or reproducible process-cleanup leak.

### 3.6 Data Studio, manifests, and Fama-French data

- Replaced API-dependent discovery with the master-universe Parquet and
  manifest-backed datasets used by other backend loaders.
- Added asset aliases, UTC normalization, deduplication, schema validation,
  column projection, date/symbol predicate pushdown, and bounded CSV fallback.
- Corrected percentage scaling in factor CSV fallback.
- Added scan telemetry for rows, bytes, pushdown versus fallback, cache hits,
  cache misses, and hit rate.
- Added authenticated, quota-bounded CSV, JSON, and Parquet uploads.
- Added formula-injection and path-traversal protections, owner-scoped storage,
  schema checks, atomic writes, and normalized errors.
- Added authenticated manifest refresh for selected known datasets.
- Added manifest schema versions, schema fingerprints, migrations, checksums,
  provenance, source URLs, licensing status, transformation version,
  generation command, point-in-time policy, and adjustment policy.
- Added atomic dataset installation with temporary copies, validation,
  hard-link or copy backup, atomic replacement, manifest write, and rollback.
- Added a deterministic manifest snapshot identifier helper. Stored analytics
  do not yet consistently persist this snapshot ID.
- Added a data-management CLI for validate, refresh, install, and migrate.
- Added a deterministic Fama-French build/check script using normalized Zstandard
  Parquet output.

The Fama-French data was refreshed through **June 30, 2026**:

| Dataset | Rows | Current Parquet SHA-256 prefix | Status |
|---|---:|---|---|
| FF3 daily | 26,274 | `e349` | Exact source-to-Parquet verification passed |
| FF5 daily | 15,854 | `ccd` | Exact source-to-Parquet verification passed |
| Momentum daily | 26,173 | `e11` | Exact source-to-Parquet verification passed |

All six Studio manifest datasets had healthy checksum and schema validation in
the last deep validation. Point-in-time and survivorship guarantees are still
documented limitations rather than enforced guarantees.

### 3.7 Portfolio, risk, journal, and governance edge coverage

Targeted tests now cover:

- Missing, empty, duplicate, invalid, negative, and non-normalized portfolio
  compositions plus allocator failures.
- Missing benchmarks and sector mappings, singular factor regressions, empty
  return overlap, and mismatched attribution calendars.
- Futures expiry gaps, missing settlement, roll boundaries, negative prices,
  division by zero, and duplicate contracts.
- Explicit and heuristic synthetic flags through persisted flows.
- Journal ordering, invalid ranges, concurrent edits, and pagination during
  inserts.
- Unequal risk histories, missing weights, singular covariance, zero
  volatility, extreme leverage, empty strategies, and alert deduplication.
- Governance exclusion and explicit restoration of deprecated factors.

## 4. Completed Frontend Work

### 4.1 Studio API reliability

- Added tests for all 11 exported Studio hooks:
  `useStudioApi`, `useAlgorithmLab`, `useBacktest`, `useCollaboration`,
  `useDataStudio`, `useFactors`, `useOptimizer`, `usePortfolioComposition`,
  `usePortfolioRisk`, `useRobustness`, and `useSnippets`.
- Covered success normalization, structured errors, GET query and caching,
  PUT/DELETE, mutations, retry, cancellation, timeout, reset, duplicate
  submission, unmount abort, and stale response suppression.
- Fixed the bug where an older same-key request could overwrite replacement
  request state.
- Fixed domain-hook error spread order and exposed both store errors and
  transport `requestError`.

### 4.2 Shared states and route coverage

- Added accessible loading, empty, validation, permission, server, stale, and
  partial-data states.
- Added retry and refresh actions with provenance and coverage context.
- Added direct error-boundary recovery tests.
- Added jsdom route-render smoke tests for all seven Studio pages.
- Added Playwright configuration, deterministic Studio API fixtures, and real
  Chromium smoke tests.
- Proved all seven desktop routes and Data Studio at 390 by 844 pixels.

### 4.3 Interrupted repository lint cleanup

A broad lint cleanup landed across documentation, Factors V2, command and
navigation components, chart workspace initialization, landing visuals, macro
modules, portfolio components, research charts, Studio overlays, trading tabs,
responsive UI, theme context, performance hooks, and universe loading.

This batch is **unverified after its final edits**. The current error and warning
count is unknown. Known warning groups were not yet addressed in several
factor, research, regime, order book, reporting, PCA, visualization, security,
watchlist, trading-context, and refresh-hook files. Treat the lint cleanup as
work in progress until lint, Jest, TypeScript, build, and Playwright all rerun.

## 5. Performance and Compute Decisions

The implementation maximizes useful speed without adding computation that does
not improve a visible user decision.

- Parquet reads project only required columns and push predicates where the
  storage engine supports it.
- Full-universe in-memory reads are avoided for workflows that can use bounded
  scans.
- Fama-French data is normalized once and stored as compressed Parquet instead
  of repeatedly parsing CSV.
- Deterministic caches avoid repeated calculation and now expose hit-rate
  telemetry.
- Optimizer and robustness workloads enforce explicit windows, paths,
  candidates, rows, outputs, timeouts, and concurrency caps.
- Robustness jobs persist results so refreshes do not force recomputation.
- Failed and nonfinite optimizer trials are isolated rather than poisoning a
  full study.
- Unbounded Monte Carlo, automatic giant parameter grids, continuous
  recomputation, and analytics without user-visible value remain intentionally
  excluded.

## 6. Generated and Operational Artifacts

Key artifacts created or expanded include:

- `docs/STUDIO_V2_REMAINING_WORK.md`
- `docs/STUDIO_V2_API_INVENTORY.md`
- `docs/STUDIO_V2_FRONTEND_API_TRACEABILITY.md`
- `backend/scripts/generate_studio_v2_api_inventory.py`
- `backend/scripts/generate_studio_v2_frontend_traceability.py`
- `backend/scripts/extract_studio_v2_frontend_calls.mjs`
- `backend/scripts/manage_studio_v2_data.py`
- `backend/scripts/build_fama_french_parquets.py`
- `backend/app/studio_v2/shared/data_loader.py`
- `backend/app/studio_v2/shared/data_manifest.py`
- `backend/app/studio_v2/shared/observability.py`
- `backend/app/studio_v2/shared/health.py`
- `backend/app/studio_v2/robustness/jobs.py`
- `backend/app/studio_v2/robustness/execution.py`
- `backend/app/studio_v2/optimizer/validation.py`
- `backend/app/studio_v2/factors/evaluator.py`
- `frontend/playwright.config.ts`
- `frontend/e2e/studio-routes.spec.ts`
- `frontend/e2e/fixtures/studioApi.ts`

The workspace has extensive pre-existing and user-owned changes. No broad
cleanup, deletion, reset, staging, or commit was performed. The repository's
global `*.md` ignore rule means the new documentation files may require
force-staging if they are committed intentionally.

## 7. Remaining Work by Priority

### P0: Restore a fully green frozen baseline

1. Permit a route-specific typed 503 readiness response in the inventory
   validator while retaining `ErrorResponse` validation for ordinary errors.
2. Regenerate API inventory and frontend traceability for 103 HTTP routes and
   one WebSocket route.
3. Change the FF3 loader test expectation from the obsolete 26,253 rows to the
   verified manifest value, preferably by reading the manifest instead of
   hard-coding it.
4. Rerun the full backend suite and require zero failures.
5. Run full frontend lint and finish only the remaining real findings.
6. Rerun all Studio Jest suites, TypeScript, the production build, and
   Playwright after the lint edits.

### P0: Security and end-to-end acceptance

1. Reject or tightly bound sequence repetition and nested exponentiation in
   custom factor expressions.
2. Add OS-level CPU and memory limits to factor workers.
3. Move all expensive factor preprocessing inside the bounded worker or apply
   equivalent limits before it.
4. Include DataFrame column-index memory in byte accounting.
5. Add `vix` to runtime field discovery or remove it from accepted fields.
6. Run one real journey against the application and persisted data: create or
   fork a strategy, execute, push to backtest, inspect results, run robustness,
   optimize, compose a portfolio, inspect risk, and save a journal entry.
7. Verify WebSocket authentication, two-client collaboration, reconnect, and
   cleanup through the deployed proxy.
8. Verify ZIP and PDF downloads in a real browser, including corrupt and
   missing-result errors.

### P1: Production architecture

1. Replace production SQLite state with migration-managed PostgreSQL while
   retaining SQLite for local development.
2. Add Redis or an equivalent shared service for collaboration, cross-worker
   caches, and coordination.
3. Add a durable shared queue for optimizer, large backtest, export, and audit
   jobs. Robustness has a local durable implementation but still needs shared
   production infrastructure.
4. Add transaction, index, backup, restore, retention, corruption recovery,
   job expiry, and interrupted-worker procedures.
5. Add per-user CPU, memory, wall-time, output, and concurrency enforcement at
   the service boundary.
6. Split the large router and contracts modules into domain modules without
   changing the composed OpenAPI contract.

### P1: Security, authorization, and abuse resistance

1. Prove authentication and authorization for every HTTP route, WebSocket,
   download, upload, manifest action, invite, journal, and snippet operation.
2. Prove owner and tenant isolation for strategies, runs, compositions, jobs,
   alerts, limits, factors, and journal entries.
3. Add CSRF protection for cookie-authenticated mutations.
4. Add independent rate limits for execution, optimization, robustness,
   exports, uploads, and invites.
5. Add CI dependency, static-security, and secret scans.
6. Complete audit events for all execution, governance, risk, collaboration,
   data, export, and administrative mutations.

### P1: Observability and operations

1. Add cache memory and eviction metrics.
2. Add job resource high-water marks and shared-queue timing.
3. Add dashboards and alerts for errors, latency, stale data, failed jobs,
   checksum failures, queue depth, and saturation.
4. Add production dependency checks for PostgreSQL, Redis/queue, object
   storage, and worker pools.
5. Publish incident runbooks for stale data, failed manifests, stuck jobs,
   memory pressure, database failure, queue failure, and WebSocket incidents.

### P2: Data reproducibility and lifecycle

1. Persist `manifest_snapshot()` IDs on every stored analytical run.
2. Enforce rather than merely document point-in-time and survivorship rules.
3. Define and test corporate-action, symbol-change, delisting, dividend, split,
   and futures-roll adjustment policies.
4. Add upload and generated-artifact retention and cleanup.
5. Consolidate overlapping loaders across Studio V2, Factors V2, PCA V2,
   Portfolio V2, Research V2, Screener V2, ML V2, and Volatility V2 only after
   graph, import, route, and smoke verification.

### P2: Frontend depth and release engineering

1. Add real-backend compute journeys rather than only intercepted route smoke.
2. Add accessibility checks for keyboard flow, focus, labels, dialogs, charts,
   contrast, reduced motion, and screen-reader summaries.
3. Add desktop, tablet, and narrow-mobile visual regression.
4. Verify dense tables, Monaco, dialogs, matrices, heatmaps, and risk
   dashboards responsively.
5. Add CI gates for backend compile/lint/tests, frontend lint/tests/build,
   generated inventory drift, security, manifest validation, and browser smoke.
6. Add staging with production-like workers and representative data volume.
7. Define canary, rollback, backup restore, disaster recovery, and release
   health procedures.

## 8. Known Warnings and Constraints

- `pyiceberg` emits dependency-level deprecation warnings.
- The API inventory and traceability artifacts are current and drift-checked.
- The reviewed factor-sandbox findings are closed; production deployments still
  require service-level OS quotas and isolation.
- Frontend lint has zero errors and 29 non-blocking warnings.
- SQLite persistence is local durability, not production multi-worker state.
- Browser smoke uses intercepted data and does not establish real-backend
  correctness.
- Documentation is ignored by the broad `*.md` rule unless force-added.
- The worktree contains many unrelated user changes and deletions. Preserve
  them and avoid destructive Git operations.

## 9. Exact Resume Commands

Run from `/Users/adityabalaji/Downloads/quant  2`:

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
python3 backend/scripts/generate_studio_v2_api_inventory.py
python3 backend/scripts/generate_studio_v2_api_inventory.py --check
python3 backend/scripts/generate_studio_v2_frontend_traceability.py
python3 backend/scripts/generate_studio_v2_frontend_traceability.py --check
PYTHONPATH=backend python3 backend/scripts/manage_studio_v2_data.py validate --deep
```

Then from `frontend`:

```bash
npm run lint
npm test -- --runInBand
npx tsc --noEmit
npm run build
npm run test:e2e:studio
```

Do not treat old passing output as a release gate after new edits. Record the
new command, date, commit or worktree identity, pass count, warning count, and
duration in this document or a release artifact.

## 10. Agent Contribution Ledger

### Primary agent

- Data loader normalization, pushdown, telemetry, and fallback correctness.
- Manifest validation, provenance, migrations, atomic install/rollback, and
  snapshot helper.
- Fama-French deterministic build and refresh.
- Observability middleware, request IDs, health/readiness/metrics routes.
- Broad backend edge-case expansion and integration verification.
- Checklist reconciliation and this final handoff.

### API inventory and factor sandbox agent

- Generated API inventory and frontend call traceability with drift tests.
- Built the factor expression sandbox and 34-test suite.
- Performed the final sandbox security audit and documented the four remaining
  resource and field-discovery gaps.
- Reported the live 103 HTTP plus one WebSocket route count and artifact drift.

### Frontend contract and browser agent

- Built all-hook contract coverage and shared state/recovery tests.
- Fixed stale same-key request state and hidden domain errors.
- Added seven-route jsdom smoke and eight-test Playwright Chromium smoke.
- Added stale and partial-data primitives.
- Began the repository-wide lint cleanup and documented that it remains
  unverified after interruption.

### Robustness and optimizer agents

- Added durable robustness jobs, typed lifecycle endpoints, cancellation,
  timeout, restart recovery, and tests.
- Added persisted optimizer study and trial access.
- Added CPCV and walk-forward routes with bounded real-backtest execution.
- Hardened optimizer edge behavior across cross-validation, objectives,
  search, ensembles, and persisted verdict selection.

### Data upload and manifest agent

- Added authenticated multipart upload, quotas, security validation,
  owner-scoped atomic storage, manifest refresh, and focused ASGI tests.

## 11. Definition of Completion

Studio V2 can be called complete only when:

- The backend suite is fully green and generated artifacts match the live
  router and frontend.
- Frontend lint, Jest, TypeScript, production build, and Playwright are green
  on the same frozen tree.
- Every visible action is wired or explicitly disabled with an explanation.
- One complete real-data, real-backend persisted journey passes.
- No request failure is silently swallowed.
- Long work is bounded, observable, cancellable, durable, and quota-controlled.
- Authentication, authorization, tenant isolation, sandboxing, downloads,
  uploads, and WebSockets pass security review.
- Data refreshes are atomic and reproducible, and stored runs identify their
  exact data snapshot.
- Production database, queue, cache, object storage, monitoring, backup,
  rollback, and incident procedures are operational.
- CI and staging enforce the same acceptance gates used for release.

## 12. Final Handoff Position

The current work is a strong, feature-rich, performance-conscious local and
pre-production foundation. The remaining work is no longer a vague request to
"finish the frontend" or "optimize the backend." It is a bounded release plan:
three backend drift fixes, frontend revalidation, four factor-sandbox hardening
items, real end-to-end acceptance, and production infrastructure/security.

Continue from the P0 list. Do not reopen already verified analytics or add
unbounded computation unless a concrete user workflow, latency budget,
resource budget, and acceptance test require it.
