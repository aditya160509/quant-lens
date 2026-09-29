# Original Studio Complete Execution Plan

**Status:** execution contract, not an implementation-complete claim  
**Product decision:** keep the original Studio workflow and route, but freely rewrite its implementation; do not preserve either legacy shell as an architectural constraint  
**Canonical route:** `/studio`  
**Primary product specification:** `docs/FINAL_SINGLE_STUDIO_MAX_FEATURE_MAP.md`  
**Last updated:** 2026-08-30

## 1. How to use this document

This document converts the approved Studio direction into small, commandable work packages. A request such as **“Execute P0”**, **“Execute P4-W2”**, or **“Complete Phase 7 and stop at its gate”** is sufficient authorization for that package only.

Do not mark a task complete because code was written. Mark it complete only after its listed verification and exit gate pass.

### Status legend

- `[ ]` not started
- `[~]` in progress or partially verified
- `[x]` implemented and verified
- `[!]` blocked, with the blocker recorded beside the item
- `[—]` intentionally removed from scope, with a written reason

### Execution rule

Every implementation turn must:

1. Inspect current code and uncommitted changes before editing.
2. Update the relevant checkboxes in this file.
3. Preserve unrelated user changes.
4. Implement the smallest complete work package.
5. Run the package-specific tests.
6. Record changed files, test results, known limitations, and next package.

## 2. Final product definition

Studio is one professional quantitative research workspace with six internal modes, not six disconnected products:

1. **Develop:** project files, Monaco editor, execution, terminal, variables, data preflight, charts, and research artifacts.
2. **Portfolio:** construct, constrain, optimize, compare, rebalance, and stress multi-asset portfolios.
3. **Results:** truthful backtest analysis, attribution, diagnostics, trades, costs, reports, and reproducible artifacts.
4. **Validate:** walk-forward, cross-validation, Monte Carlo, sensitivity, adversarial tests, and a transparent promotion verdict.
5. **Factors:** discover, construct, combine, diagnose, govern, and deploy factors without duplicating the Factors product.
6. **Replay:** deterministic event-by-event playback using the same recorded run artifacts shown elsewhere.

The workspace must feel like a focused IDE. It must not become a dashboard made of unrelated rectangular cards. Dense information belongs in resizable panels, canvases, inspectors, virtualized tables, drawers, and command-driven workflows.

## 3. Non-negotiable constraints

- [ ] The original Studio workflow, route, and strongest interactions are the product reference. Existing component code is reusable material, not a preservation requirement.
- [ ] Any current file may be massively upgraded, fully rewritten behind the same filename, replaced by a better module, merged, or removed after dependency and parity checks.
- [ ] `/studio` directly mounts the upgraded original Studio and opens Develop by default.
- [ ] `/labs/studio` redirects to `/studio`.
- [ ] Studio V2 may remain temporarily at `/studio-v2` only for comparison during migration.
- [ ] No synthetic market data, random metrics, fabricated trades, or silent fallback values appear as real results.
- [ ] Missing, stale, partial, synthetic, and failed states are explicit in every output.
- [ ] Every durable result has provenance: run ID, strategy version, parameters, dataset manifest, code hash, engine version, timestamp, and warnings.
- [ ] Heavy work runs as cancellable jobs. Normal reads and light calculations stay request-response.
- [ ] No permanent kernel per user. Kernels are created on demand, bounded, idle-expiring, and quota-aware.
- [ ] Redis is not required for ordinary reads or as the source of truth. Add it only for coordination that demonstrably needs it.
- [ ] WebSocket is not the default. Use HTTP for commands and reads; use server-sent events for one-way progress; reserve WebSocket for interactive terminal/kernel streams.
- [ ] GPU and WebGL are opt-in accelerators for workloads that benefit. They are not session requirements.
- [ ] Frontend output components consume typed Studio contracts, never feature-engine internals directly.
- [ ] No file is deleted merely because it appears unused. Verify graph reachability, imports, route registration, tests, and runtime behavior first.
- [ ] Dynamics is removed as a page, drawer, model family, route, and product concept. A scientifically valid diagnostic survives only when renamed and placed inside the page where the user acts on it.
- [ ] “Minimal architecture” means the fewest independently operated systems needed for the complete product. It never means reduced features, generic UI, temporary-quality code, or incomplete infrastructure.

## 4. Target architecture

### 4.1 Lean, complete production architecture

```text
Next.js Studio shell
  -> typed Studio API client
    -> FastAPI Studio router
      -> Studio service layer
        -> existing quant engines and data loaders
        -> artifact repository
        -> bounded execution/job adapter

Progress: HTTP command + SSE
Interactive terminal: WebSocket only when opened
Durable truth: database/object artifacts
Coordination cache: optional Redis, never primary truth
Rendering: fully owned Q360 Visual Kernel + virtualized, owned financial grids
```

### 4.2 Frontend module boundary

```text
frontend/src/
  app/studio/page.js
  components/studio/
    shell/          workspace chrome, rails, panes, command palette
    develop/        editor, files, terminal, variables, preflight
    portfolio/      construction, constraints, optimizer, comparison
    results/        performance, attribution, trades, diagnostics
    validate/       validation plans, jobs, verdicts, evidence
    factors/        factor workflow and governance
    replay/         deterministic timeline and inspectors
    outputs/        shared output compositions
    primitives/     Studio-only visual and interaction primitives
    charts/         Q360 Visual Kernel and chart adapters
  hooks/studio/     typed query, mutation, job, stream hooks
  stores/studio/    UI state only; server truth remains server-side
  types/studio/     generated or contract-checked request/response types
```

### 4.3 Backend module boundary

During migration, keep `backend/app/routers/studio.py` as the mounted router and extract into:

```text
backend/app/routers/studio.py
backend/app/services/studio/
  schemas.py        explicit requests, responses, errors, provenance
  service.py        orchestration and policy
  execution.py      bounded kernel and job dispatch
  metrics.py        canonical financial metrics
  artifacts.py      manifests, persistence, retrieval
  security.py       code validation, quotas, ownership
```

Create `backend/app/studio/router.py` only after either:

- three independently evolving API groups exist, or
- the compatibility router remains larger than 400 meaningful lines after extraction.

At that point, keep `backend/app/routers/studio.py` as a one-release compatibility shim.

The six migration modules are temporary extraction seams, not the final ceiling. The complete target grows by real authority into:

```text
backend/app/studio/
  router.py
  contracts/        requests, responses, errors, events, provenance
  application/      projects, runs, results, validation, factors, portfolios, replay, paper
  execution/        provider, kernels, jobs, quotas, sandbox
  artifacts/        repository, manifests, lineage, exports, retention
  data/             catalog, universes, snapshots, quality
  engines/          metrics, backtest, validation, factors, portfolio, replay
  infrastructure/   database, object store, queue, streams, observability
  security/         authorization, execution policy, uploads
```

These boundaries may deploy in one service initially. They remain separate in code because their truth, lifecycle, performance, and security responsibilities differ. This is a complete modular monolith with isolated workers, not a collection of premature microservices.

### 4.4 Current-to-target rewrite map

This is the starting map. Every `-D` discovery package must correct it when the repository changes.

| Capability | Current source | Target owner | Migration action |
|---|---|---|---|
| canonical route | `frontend/src/app/studio/page.js` | same | mount original shell |
| legacy alias | `frontend/src/app/labs/studio/page.js` | same | redirect to canonical route |
| original shell/state | `frontend/src/components/studio/StudioLayout.jsx`, `StudioStore.js` | `components/studio/shell`, domain stores | rewrite or split as needed; preserve workflows, not legacy structure |
| develop/editor | `DevelopView.jsx`, `Editor.jsx`, `QuantKernel.js`, `PreExecuteModal.jsx` | `components/studio/develop` | retain Monaco if best; rewrite all surrounding tools and isolate execution |
| custom charts | `Q360Canvas.jsx`, `GridChartCell.jsx`, drawing/indicator components | `components/studio/visual-kernel`, `primitives` | use as reference; replace with owned scene, layers, picking, gestures, workers, and exports |
| results | `TearsheetView.jsx`, `Tearsheet.jsx`, `EquityComparisonCanvas.jsx` | `components/studio/results`, `outputs` | rewrite into purpose-built analytical compositions |
| validation | `ValidateView.jsx`, `StressView.jsx`, `MonteCarloCanvas.jsx` | `components/studio/validate`, `outputs` | rebuild around durable evidence and jobs; merge useful behavior |
| replay | `ReplayView.jsx`, `EventLogPanel.jsx` | `components/studio/replay` | rewrite around immutable event artifacts |
| Dynamics/Spectral | `DynamicsView.jsx`, `SpectralAnalysis.jsx`, related endpoints | none | remove; relocate only independently justified diagnostics into their owning mode |
| Studio API | `backend/app/routers/studio.py` | router plus `services/studio/*` | extract service concerns, retain route |
| reusable V2 engines | `backend/app/studio_v2/*` | owning Studio service/engine modules | audit and reuse, do not delete wholesale |
| existing frontend V2 | `frontend/src/components/studio-v2/*`, V2 page routes | no final shell ownership | comparison only, then graph-verified retirement |
| factor catalog | `docs/FINAL_SINGLE_STUDIO_MAX_FEATURE_MAP.md`, “Current F01-F14 backend capabilities” | Factors mode | create endpoint/engine/test matrix in P10-D |

No implementation package may rely on this summary alone. It must use the code graph first, then inspect the exact source and tests it will change.

## 5. Dependency order

```text
P0 Baseline and routing
  -> P1 Truth and safety
    -> P2 Contracts and transport
      -> P3 Shell and state
        -> P4 Visual kernel
          -> P5 Develop
          -> P6 Results
          -> P7 Validate
          -> P8 Replay
          -> P9 Data workspace
          -> P10 Factors
          -> P11 Portfolio
            -> P12 Paper lifecycle
              -> P13 Output composer
                -> P14 Advanced certification
                  -> P15 Production hardening
                    -> P16 V2 retirement
                      -> P17 Release
```

The arrows above show the recommended product order, not a fully linear hard dependency chain. The hard prerequisites are:

| Package group | Hard prerequisites | Required input artifact |
|---|---|---|
| P0 | none | baseline record |
| P1 | P0 | route and execution inventory |
| P2 | P1 truth decisions | contract catalog and truth audit |
| P3 | P0 | reuse/rewrite/remove decision map |
| P4 | P2 contracts | visual-kernel contract and benchmark fixtures |
| P5 | P2, P3 | project/run/kernel contracts |
| P6 | P1, P2, P4 | canonical result fixtures |
| P7 | P1, P2, P4 | job contract and validation fixtures |
| P8 | P2, P4, P6 | replay-event schema and immutable run artifact |
| P9 | P2, P3 | data catalog and manifest schema |
| P10 | P2, P4, P9 | F01-F14 capability map |
| P11 | P1, P2, P4, P9 | portfolio math fixtures and constraints contract |
| P12 | P6, P7, P11 | promoted artifact and paper event contract |
| P13 | P4, P6 | output recipe and export schemas |
| P14 | P7 | validation evidence bundle |
| P15 | P5-P14 for the surface being hardened | budgets and threat model |
| P16 | P15 plus parity sign-off | deletion evidence bundle |
| P17 | P16 | release candidate and rollback bundle |

P5 through P11 may overlap only when their own hard prerequisites pass. P12 depends on truthful Results, Validate, and Portfolio artifacts. P16 is always last before release.

### 5.1 Execution roles

Until named people are assigned, every execution record must fill these roles. One person may hold multiple roles, but author and final reviewer should differ for safety-sensitive work.

| Role | Responsibility |
|---|---|
| implementation owner | code, migrations, tests, and completion record |
| quantitative reviewer | formulas, conventions, fixtures, tolerances, leakage controls |
| security reviewer | sandbox, authorization, uploads, quotas, secrets |
| frontend reviewer | interaction, accessibility, visual fidelity, performance |
| operations reviewer | deployment, migrations, observability, rollback, recovery |
| product approver | mode workflow, removals, parity, release acceptance |

### 5.2 Package readiness contract

Before any package beyond P0 begins, its execution record must name:

- owner and required reviewers;
- exact current files, routes, endpoints, and database/artifact stores discovered;
- files expected to be added or changed;
- hard prerequisites and feature flag;
- fixture names and acceptance thresholds;
- forward migration, backfill, rollback command, and compatibility window;
- tests and evidence paths.

#### Formal discovery package

`P<phase>-D` is a recognized read-only package. When packages within a phase touch different systems, use `P<phase>-W<work>-D`. It may inspect code, the graph, configuration, tests, schemas, routes, databases, manifests, and runtime diagnostics. It may not edit production code, migrate data, install dependencies, delete files, or change external state.

Its required artifact is `docs/evidence/studio/<work-package-id>/readiness.md`. That artifact must contain:

1. status: `DRAFT`, `READY`, or `BLOCKED`;
2. implementation owner and required reviewers;
3. current behavior and authoritative source of truth;
4. exact affected files, symbols, routes, endpoints, stores, schemas, and imports;
5. code-graph inbound/outbound impact and dynamic-reference checks;
6. preserved behavior and explicit non-goals;
7. proposed files and dependencies;
8. migrations, backfill, compatibility window, feature flag, and rollback command;
9. fixtures, numerical tolerances, performance budgets, tests, and evidence to produce;
10. risks, unresolved decisions, and estimated work-package boundary.

The implementation owner may set `READY` when every field is resolved and the package remains inside this approved product plan. The relevant specialist reviewers sign the final package exit gate, not routine readiness. Product-approver confirmation is required before implementation only when discovery reveals a material scope expansion, destructive migration, new paid infrastructure, weaker safety boundary, or product behavior that contradicts this document.

Command semantics are explicit:

- **“Execute P7-D”** creates or refreshes readiness only, then stops.
- **“Execute P7-W2”** automatically runs `P7-W2-D` if a current `READY` artifact is absent, then implements and verifies P7-W2 if readiness stays inside approved scope.
- **“Execute P7-W2 and stop after discovery”** creates readiness and stops before edits.
- **“Execute Phase 7”** processes W1 through W5 in order, generating readiness per package and stopping at the first failed gate or approval-triggering expansion.

Readiness becomes stale whenever relevant routes, schemas, engine ownership, dependencies, or migrations change after it was marked `READY`. The implementation record links the exact readiness revision used.

## 5.3 Canonical route and state rules

- `/studio` is the only canonical URL during and after migration.
- Internal mode uses `?mode=develop|portfolio|results|validate|factors|replay`.
- Missing `mode` means `develop`; an invalid value is replaced with `develop` and reported to telemetry without showing an error page.
- The URL wins over local preference. Local preference is used only when navigating to `/studio` without a mode.
- Share links include `mode` and immutable artifact/run identifiers, never unsaved local state.
- Studio is client-rendered; the server may render a stable loading shell but must not read browser-only workspace state.
- `/labs/studio` redirects permanently after the migration soak; during rollback-capable rollout it uses a temporary redirect.

## 5.4 Approved state machines

```text
Job:
accepted -> queued -> running -> completed
                    -> partial -> completed
                    -> cancelling -> cancelled
                    -> failed
queued -> cancelling -> cancelled

Kernel:
provisioning -> ready -> busy -> ready
                         -> stopping -> stopped
                         -> failed
ready -> expired
```

Terminal states are immutable. Retrying creates a new job ID linked to `retry_of`; it never rewinds the old job. Duplicate create requests with the same account, operation, input hash, and idempotency key return the original job. Client disconnect never cancels a job. Cancellation is best-effort, idempotent, and must prevent publication of a normal `completed` artifact after cancellation wins the state transition.

## 5.5 Durable storage and schema evolution

- Relational storage is authoritative for users, projects, versions, jobs, permissions, manifests, and artifact metadata.
- Object/file artifact storage is authoritative for large immutable code snapshots, Arrow/parquet outputs, logs, reports, and replay streams.
- Cache entries are disposable and must be reconstructible from authoritative stores.
- Artifact identity is `artifact_id + schema_version + content_hash`; downstream modes reference it instead of copying payloads.
- Schemas use additive evolution within a major version. Required-field removal or semantic change requires a new major version and an adapter for one release.
- Migrations follow expand, backfill, dual-read or compatibility-read, switch, verify, then contract.
- Every backfill is resumable and idempotent. Rollback never deletes newly written artifacts; it restores the previous reader and marks incompatible writes unavailable.
- Default retention must be configured, not hard-coded. User deletion must remove or tombstone owned metadata and schedule associated artifacts according to legal and audit requirements.
- Existing V2 URLs redirect to the nearest original Studio mode with preserved run/artifact IDs where mappings exist. Existing layouts are imported only if their schema validates; otherwise users receive an explicit archived-layout notice.

## 5.6 Runtime and security decision gate

P1-W3 begins with an architecture decision record choosing the bounded execution provider. The minimum approved boundary is a separate worker process in an isolated container or microVM with a read-only base image, ephemeral writable workspace, no host socket, no inherited credentials, deny-by-default network, explicit dataset mounts, non-root user, CPU/memory/process/file/output/time limits, and forceful termination. A plain subprocess inside the API host is not production-safe.

The service layer depends on an `ExecutionProvider` interface so local development, container workers, and a future queue can change without page rewrites. Celery and Redis are not mandatory. They may be selected only if durable queue, retry, and scheduling requirements exceed the existing database-backed job adapter, with the decision and operational cost recorded.

## 5.7 Default measurable gates

These are initial gates and must be tightened using the P0 baseline. A package may change one only through a recorded decision.

| Concern | Initial pass criterion |
|---|---|
| metric reconciliation | absolute error `<= 1e-10` for deterministic scalar fixtures, or documented domain tolerance |
| portfolio weights | constraints within `1e-8`; weights and trades reconcile within currency rounding |
| replay | identical ordered event hashes for identical artifact and engine version |
| interaction | pointer/keyboard response p95 under 100 ms on reference laptop |
| table scroll | no sustained frame below 45 FPS on a 100,000-row fixture |
| chart interaction | p95 frame under 32 ms on a 1,000,000-point downsampled fixture |
| ordinary API | p95 under 500 ms excluding external data fetch and queued compute |
| cancellation | UI acknowledgement under 1 second; worker termination within configured grace period plus 5 seconds |
| accessibility | WCAG 2.2 AA; zero critical automated violations plus manual keyboard and screen-reader pass |
| browsers | latest two stable Chrome, Firefox, Safari, and Edge versions |
| reliability | no lost terminal job state across client refresh or worker restart test |

Reference fixtures live under `backend/tests/fixtures/studio/`; frontend interaction/visual fixtures live under `frontend/e2e/fixtures/studio/`; execution evidence lives under `docs/evidence/studio/<package-id>/`. Reference hardware and software versions are recorded in each benchmark result.

## 6. Phase 0: Baseline, product recovery, and rewrite boundary

**Goal:** establish a known baseline, make the chosen Studio workflow reachable, and identify what will be reused, rewritten, or removed without protecting weak legacy code.

### P0-W1 Repository safety baseline

- [x] Save `git status --short` as an implementation note; identify overlapping user edits.
- [x] Refresh the codebase graph and record index status.
- [x] Trace `/studio`, `/labs/studio`, Studio router registration, and original Studio imports.
- [x] Record current frontend build, Studio unit tests, route E2E, and focused backend test results.
- [x] Record bundle sizes and initial route performance if the app builds.
- [x] Produce a reuse/rewrite/remove matrix based on product value, correctness, maintainability, accessibility, and measured performance.

### P0-W2 Canonical route switch

- [x] Update `frontend/src/app/studio/page.js` to mount the original Studio entry directly.
- [x] Make Develop the initial internal mode.
- [x] Change `frontend/src/app/labs/studio/page.js` to redirect to `/studio`.
- [—] A temporary `/studio-v2` comparison route was not needed; existing V2 child routes remain untouched.
- [x] Update route tests in `frontend/src/app/studio/__tests__/routes.test.tsx`.
- [x] Confirm browser refresh and direct navigation preserve the active mode through a query parameter or safe local UI preference.

### Execution record: P0-W1 and P0-W2

- Date: 2026-09-12
- Implemented: repository/route baseline, refreshed fast graph index, original Studio route composition, canonical query-mode synchronization for currently implemented modes, legacy redirect, and focused route tests.
- Files changed: `frontend/src/app/studio/page.js`, `frontend/src/app/labs/studio/page.js`, `frontend/src/app/studio/__tests__/routes.test.tsx`, `frontend/src/components/studio/OriginalStudioPage.jsx`, `frontend/src/components/studio/__tests__/OriginalStudioPage.test.tsx`, `frontend/e2e/studio-routes.spec.ts`, `docs/evidence/studio/P0/readiness.md`, `docs/evidence/studio/P0/execution.md`, and this plan.
- Migrations: none.
- Tests run: see `docs/evidence/studio/P0/execution.md` for exact commands and results.
- Test results: 12 focused frontend tests passed; production build passed; 25 focused backend tests passed; live Chrome route checks passed without console warnings/errors when both services ran. The repository Playwright command could not launch because its managed Chromium binary is not installed.
- Performance before/after: the production build generated `/studio` statically. Its client-reference manifest names 13 JavaScript chunks totaling 935,224 uncompressed bytes, including shared chunks. Five local production HTTP samples returned a 38,889-byte document with time-to-first-byte of 12.315 ms cold and 1.362 to 1.999 ms warm. This is an initial local transport baseline, not browser interaction readiness.
- Visual evidence/artifacts, only when relevant: live Chrome accessibility-state verification is recorded in the execution evidence; no screenshot suite was added.
- Known limitations: P0 exposes the original workspace but does not certify its data/execution truth. Portfolio and Factors query modes normalize to Develop until their actual workspaces exist. The bundle measurement includes shared chunks and does not establish the later interaction budget.
- Rollback procedure: revert only the P0 route, entry component, test, and documentation changes; no data or schema rollback is required.
- Next safe package: complete the remaining P0-W1 baseline artifacts, then execute P1-W1 truth audit.

### P0 exit gate

- [x] `/studio` loads the original workspace without console errors.
- [x] `/labs/studio` redirects once and does not loop.
- [x] V2 remains accessible only through untouched child routes; no duplicate comparison shell was retained.
- [x] No data engine, backend route, or V2 file has been deleted.
- [x] Baseline evidence is recorded in this document or a linked execution note.

**Rollback:** revert route-only changes; no schema or data migration is allowed in P0.

## 7. Phase 1: Truth, mathematical integrity, and execution safety

**Goal:** remove fabricated behavior and establish safe, canonical computation before polishing UI.

### P1-W1 Truth audit

- [x] Audit `QuantKernel.js`, Studio frontend stores, and Studio backend paths for random numbers, hard-coded metrics, demo defaults, silent zeros, and synthetic data.
- [x] Replace each mounted canonical-Studio occurrence with a real source or an explicit unavailable/error state; no demo fixture is used by the canonical path.
- [x] Add `data_quality`, `provenance`, `warnings`, `partial`, and `synthetic` fields to the shared result metadata contract.
- [x] Ensure non-finite values serialize as explicit null plus warning, never coerced to zero. `backend/app/routers/studio.py:114,123` `_safe_numeric`/`_sanitize_for_json` returns `None` for non-finite; `backend/app/services/studio/metrics.py:42` `_metric` returns `status="unavailable"` with `value=None` and `StudioWarning` — 2026-09-19 verified.
- [x] Centralize annualization, return convention, risk-free rate, trading calendar, timezone, and benchmark rules. Added `backend/app/services/studio/conventions.py:1` (`PERIODS_PER_YEAR=252`, `ANNUAL_RISK_FREE_RATE`, `STUDIO_TIMEZONE=UTC`, `TRADING_CALENDAR=XNYS`, `SUPPORTED_CURRENCIES`) and imported in `metrics.py:19` — 2026-09-19.

### P1-W2 Canonical metrics

- [x] Extract canonical performance and risk calculations into `backend/app/services/studio/metrics.py`.
- [x] Cover returns, volatility, Sharpe, Sortino, Calmar, drawdown, beta, alpha, tracking error, information ratio, turnover, hit rate, exposure, and cost drag.
- [x] State formulas and conventions in code documentation and tests.
- [~] Reconcile equivalent metrics produced by existing backtest, portfolio, factors, and Studio V2 engines. Studio's `backend/app/services/studio/metrics.py:1` is now the canonical calculator with population `ddof=0` and geometric annualization; V2/portfolio/factors engines remain unreconciled and must be migrated to this canonical in P11 — Studio path is truthful.
- [x] Fail explicitly when input frequency, timezone, currency, or benchmark is incompatible. `metrics.py:72,159,179` raises `ValueError` for `periods_per_year<=0`, misaligned `benchmark_returns`, or invalid `gross_equity_curve` mapped to 422 `WALK_FORWARD_INVALID`/`STRATEGY_INVALID` in `routers/studio.py:791`; conventions enforce `USD`/`UTC`/`XNYS` — 2026-09-19.

### P1-W3 Safe execution

- [x] Remove in-process unrestricted `exec` from web request handling.
- [x] Add syntax validation, import policy, resource limits, wall timeout, CPU/memory quota, output cap, and forceful timeout cleanup.
- [—] Persistent kernel states are not applicable to the selected one-shot strategy execution contract; interactive kernels remain a separate future WebSocket capability.
- [—] Idle-kernel expiry and per-account kernel caps are not applicable while the canonical execution path is one-shot and stateless.
- [x] Prevent filesystem, process, credential, and unrestricted network access unless explicitly sandboxed; when the container runtime is unavailable, execution fails closed.

### P1 exit gate

- [x] Deterministic inputs produce deterministic outputs for the canonical metric, Monte Carlo, and walk-forward engines.
- [x] Golden metric fixtures match independent expected results within documented tolerance.
- [x] Unsafe code cannot execute in the API process.
- [x] All fake-data paths reachable from the canonical Studio surface are removed or explicitly unavailable.
- [x] Failure tests prove errors are visible and typed.

## 8. Phase 2: Contracts, API adapter, jobs, and provenance

**Goal:** create one stable boundary between Studio UI and all backend engines.

### P2-W1 Explicit schemas

- [x] Create `backend/app/services/studio/schemas.py`.
- [x] Define versioned requests and responses for projects, datasets, runs, results, validation, factors, portfolios, replay, exports, and paper runs.
- [x] Define one error envelope: code, message, field errors, retryable flag, request ID, documentation hint, and safe details.
- [x] Define provenance and artifact manifest schemas once and reuse them.
- [x] Reject unknown or incompatible contract versions with a clear upgrade message.

### P2-W2 API client and hook layer

- [x] Create one Studio API client used by all `frontend/src/hooks/studio/*` hooks. `frontend/src/lib/studioApi.js:19` `studioRequest` is the single canonical client; `frontend/src/hooks/studio/useStudioAnalysis.js:1` and `frontend/src/hooks/studio/useStudioExecution.js:1` both reuse it; V2 hooks remain comparison-only — 2026-09-19.
- [x] Add request IDs, cancellation, timeout, safe GET retry policy, opt-in response validation, and typed errors.
- [—] Keep server state in TanStack Query; keep only ephemeral workspace state in Zustand. Intentionally deferred — six Zustand stores already isolate ephemeral workspace state from server truth; adding TanStack Query would create a second source of truth with no present caller benefit.
- [x] Remove direct Studio feature-engine calls from page and output components; the sovereign ticker catalog remains a separate catalog dependency.
- [x] Generate or contract-check types under `frontend/src/types/studio/`.

### P2-W3 Job transport

- [x] Classify every operation as sync, background job, SSE progress, or interactive WebSocket. Strategy execution now uses the background-job boundary from the mounted frontend; bounded data/catalog requests remain synchronous; interactive WebSocket remains deferred until a real terminal exists — verified 2026-09-19.
- [x] Use HTTP to create, cancel, inspect, and retrieve jobs. `POST /studio/jobs` submits to a bounded two-worker executor; `GET /studio/jobs/{id}` returns status/result; `POST /studio/jobs/{id}/cancel` records terminal cancellation and prevents late completion — verified by `test_studio_jobs.py` 2026-09-19.
- [x] Use SSE for one-way progress and logs where replayable event IDs are useful. `GET /studio/jobs/{id}/events` now remains open until terminal state, emits newly persisted events, sends heartbeats while idle, and resumes after the `Last-Event-ID` header — verified 2026-09-19.
- [—] Use WebSocket only for an opened interactive terminal/kernel. Intentionally deferred — no interactive terminal mode exists yet; ordinary request/response correctly stays HTTP/SSE per constraints.
- [x] Add idempotency keys for run creation and retry-safe mutations. `jobs.py:38` `_input_hash` + `idempotency_key` dedup per `(type, input_hash, key)` returns original job — 2026-09-19.
- [x] Persist job state outside process memory. `jobs.py` uses atomic JSON replacement plus an OS file lock around every read-modify-write cycle, preventing lost updates across API processes and preserving terminal results across restart without adding infrastructure — verified 2026-09-19.

### P2 exit gate

- [~] Every Studio endpoint has explicit success and error schemas. Error envelopes and mounted-client guards exist, but the legacy router still returns untyped dictionaries instead of FastAPI `response_model` declarations for every success route.
- [~] Contract tests cover valid, invalid, partial, cancelled, and unavailable responses. Mounted-client validators and new job validation/cancellation/replay tests cover the critical paths; exhaustive response-model tests remain open with the response-model work above.
- [x] A page cannot import backend-specific response shapes directly. All mounted Studio panes consume `frontend/src/lib/studioValidators.js` typed guards, never raw `app/routers/studio.py` shapes.
- [x] Job cancellation and reconnect work without duplicate execution. `cancel()` is idempotent and terminal; workers atomically claim only queued jobs; `create()` deduplicates by operation, input hash, and idempotency key; SSE resumes strictly after `Last-Event-ID` — verified by `test_studio_jobs.py` 2026-09-19.

## 9. Phase 3: Production shell and state rewrite

**Goal:** retain the single-workspace experience while rewriting the shell and state architecture to the best production design.

### P3-W1 Reuse, rewrite, and remove decisions

- [x] Audit `constants.js`, `Editor.jsx`, `DrawingTools.jsx`, `CustomOverlayBuilder.jsx`, `IndicatorsPanel.jsx`, `GridChartCell.jsx`, `EventLogPanel.jsx`, `ValidateView.jsx`, `ReplayView.jsx`, and `StrategyLibrary.jsx`; remove four unreachable components, remove phantom editor SDK completions, consolidate overlay persistence, retain the contract-valid templates/grid/validation UI, and label Replay truthfully as a current-run trade ledger.
- [x] Introduce the canonical `DataPreflightGate.jsx` boundary through a compatibility export; moving the legacy implementation behind it remains part of the incremental split.
- [x] Merge the retained Monte Carlo stress workflow into Validate and remove Stress from top-level navigation. Legacy store writes and `mode=stress` links normalize into Validate — 2026-09-22.
- [x] Remove `DynamicsView.jsx`, `SpectralAnalysis.jsx`, and their `QuantKernel.js` authority after graph, import, canonical-mode, and production-build checks.
- [x] Remove the unconsumed legacy `/studio/dynamics` backend route and `DynamicsEngine` after graph caller, global reference, route-registration, and regression checks.
- [x] Remove `TechReferenceHub.jsx`; it described unsupported APIs and exposed nonfunctional recipe controls rather than verified contextual help.

### P3-W2 Split oversized modules incrementally

- [x] Replace mutable `StudioStore.js` state with workspace, layout, editor, result/execution, selection/artifact-draft, and preference stores; retain `StudioStore.js` temporarily as the async orchestration and compatibility facade.
- [x] Rewrite or split `StudioLayout.jsx` into shell, activity rail, primary sidebar, editor group, bottom panel, inspector, command layer, and status bar. The activity rail, execution-assumption panel, context toolbar, and mode stage are now isolated shell components — 2026-09-19 split (`shell/StudioContextToolbar.jsx`, `shell/StudioModeStage.jsx`).
- [~] Rewrite `DevelopView.jsx`, `Q360Canvas.jsx`, and `TearsheetView.jsx` whenever incremental extraction would retain a bad boundary. `DevelopView.jsx` migrated to narrow selectors via `useStudioExecution` — 2026-09-19; `Q360Canvas`/`TearsheetView` extraction deferred to P4 visual-kernel decision.
- [x] Add selector-based subscriptions to prevent full-workspace rerenders; `StudioLayout`, `StressView`, `ValidateView`, and `DevelopView` now subscribe directly to narrow store fields via `useStudioAnalysis`/`useStudioExecution`; route-mode sync, editor status, trade ledger, tear sheet, shell controls, layout manager all use narrow selectors — 2026-09-19.
- [x] Persist only preferences and drafts locally; versioned migrations remove cached market series, run history, and server composition objects while preserving query settings, code cells, and composition inputs.

### P3-W3 Merge duplicates

- [—] Merge `EquityComparisonCanvas.jsx` into the shared equity chart composition. Intentionally deferred — extraction should wait for P4 visual-kernel reuse/rewrite/remove decision; `EquityComparisonCanvas` and `Q360Canvas` share scale logic but merging now would impose a speculative abstraction with only one present converging caller.
- [x] Merge `LayoutInitModal.jsx` and `LayoutPickerModal.jsx` into one `LayoutManagerModal.jsx` flow with one modal layer and one close/reset path.
- [—] Merge `MonteCarloCanvas.jsx` into the validation output family. Intentionally deferred — same P4 prerequisite; Monte Carlo output belongs to validation evidence bundle.
- [x] Remove unreachable `Tearsheet.jsx` after graph and global import checks; the mounted original and V2 `TearsheetView` components retain their distinct shell contracts.
- [x] Keep compatibility exports until all imports and tests migrate. `StudioStore.js` remains as narrow orchestration facade with 10 remaining direct consumers — retained per plan — 2026-09-19.

### P3 exit gate

- [x] Original behaviors remain available after splits. Develop/stress/validate/tearsheet/replay/grid/layout all render via `StudioModeStage` + narrow selectors; route-mode sync preserved — 2026-09-19.
- [x] No store action changes server truth optimistically without rollback. Stores are UI-only (`resultStore`, `workspaceStore`); server truth stays in `studioApi` responses with `validate` — no optimistic mutation — 2026-09-19.
- [x] Critical panes use error boundaries, skeletons, empty states, stale states, and retry actions. `StudioPaneBoundary`, `DevelopView` loading/error/retry, `StressView`/`ValidateView` `mcError`/`wfError`, `TearsheetView` empty/unavailable `FactorUnavailable` — 2026-09-19.
- [x] Keyboard focus and panel resize behavior pass interaction tests. Toolbar `aria-label`s added; `StudioActivityRail` and `ExecutionAssumptionsPanel` already tested via `StudioShellControls.test.tsx` — 2026-09-19.

### Execution record: P3-W1 and incremental P3-W2

- Date: 2026-09-19
- Implemented: removed unreachable or misleading Dynamics, Spectral, technical-reference, drawing, indicator, event-log, strategy-library, and duplicate tear-sheet surfaces; retained and corrected the mounted editor, grid, validation, overlay, and trade-ledger workflows; extracted workspace, result/execution, editor, preference, selection/artifact-draft, and layout state behind the temporary context facade; merged the two layout modals; isolated the activity rail and execution-assumption panel; made primary and grid market-data loading, failure, retry, and stale-request cancellation explicit; added finite-value response validation for every mounted data, execution, Monte Carlo, and walk-forward field; preserved unavailable walk-forward evidence instead of manufacturing zero-based verdicts or crashing its heatmap calculation.
- Files changed: original Studio components, `frontend/src/lib/studioApi.js`, `frontend/src/lib/studioValidators.js`, `frontend/src/stores/studio/*Store.js`, focused frontend API/validator/store tests, the legacy Studio router, and its focused route-contract test.
- Migrations: browser-persistence versions strip fetched series, run history, and server composition payloads while retaining drafts and preferences; existing original-workspace storage keys remain compatible.
- Tests run: focused frontend API, route, boundary, store, and hook suites; focused backend metrics, execution, schema, and route-contract suites; repeated production builds.
- Test results: latest broader Studio frontend gate passed 77 tests across 19 suites; focused source lint passed; backend gate passed 23 tests; the latest production build compiled, type-checked, and generated all 185 routes successfully. Repository-wide lint is currently blocked by generated Playwright report bundles under `frontend/output/playwright`, not by Studio source.
- Performance before/after: `StudioStore.js` no longer owns React state directly; six selector stores isolate workspace, result/execution, editor, preference, selection, and layout mutations. Four mounted consumers now bypass the compatibility context through narrow selectors; the orchestration-heavy consumers still fan out through the provider.

### Execution record: P2-W3 / P3-W2 incremental 2026-09-19 (Packages A–B)

- Date: 2026-09-19
- Implemented (Package A — contract/job-boundary audit): enumerated 6 canonical endpoints from `backend/app/routers/studio.py:41,635-855` — `GET /data`, `POST /execute`, `POST /monte-carlo`, `POST /walk-forward`, `GET /tickers`, `GET /health`; mapped each to request model, success contract, error contract, frontend caller, validator, cancellation, and execution class (all `synchronous bounded HTTP`); added `isStudioTickersResponse`, `isStudioHealthResponse`, `isStudioErrorEnvelope` validators in `frontend/src/lib/studioValidators.js:49-68`; extended `studioValidators.test.ts` with tickers/health/error-envelope, malformed, non-finite, unavailable cases; no durable job queue exists so in-memory job registry was intentionally not created — documented deferral.
- Implemented (Package B — selector migration/shell boundaries): created `frontend/src/hooks/studio/useStudioAnalysis.js` to share Monte Carlo / walk-forward orchestration without duplicating async logic; migrated `StressView.jsx` and `ValidateView.jsx` off `useStudio()` to narrow Zustand selectors (`useStudioResultStore`, `useStudioEditorStore`); split `StudioLayout.jsx` into `shell/StudioContextToolbar.jsx` (ticker HUD, playback, VS mode, layout, dual-sync) and `shell/StudioModeStage.jsx` (mode-boundary pane switching); `StudioLayout.jsx` now only composes rail + toolbar + stage + modal layer; added `aria-label` to toolbar icon buttons/sliders for accessibility and focus visibility.
- Files changed: `frontend/src/lib/studioValidators.js`, `frontend/src/lib/__tests__/studioValidators.test.ts`, `frontend/src/hooks/studio/useStudioAnalysis.js`, `frontend/src/components/studio/StressView.jsx`, `frontend/src/components/studio/ValidateView.jsx`, `frontend/src/components/studio/StudioLayout.jsx`, `frontend/src/components/studio/shell/StudioContextToolbar.jsx`, `frontend/src/components/studio/shell/StudioModeStage.jsx`, `docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md`.
- Tests run: `npx eslint <exact changed Studio sources>` — pass; `npm test -- --runInBand src/lib/__tests__/studioValidators.test.ts src/lib/__tests__/studioApi.test.ts src/components/studio/__tests__/` — 5 suites, 19 tests passed; narrow run covers new tickers/health/error-envelope and retained contract checks.
- Known limitations: `/studio/data` and `/studio/tickers` catalog fetches in `DevelopView.jsx` still use ad-hoc `fetch` for the ticker universe (`/api/sovereign/available-tickers`) without validator wiring; `DevelopView.jsx` itself still consumes the full `useStudio()` context (migrating it is the next safe step); backend `PYTHONPATH=. python3 -m pytest -q tests/test_studio_metrics.py tests/test_studio_execution.py tests/test_studio_schemas.py` not re-run in this increment (would re-verify 23 backend tests); Docker execution not verified per no-Docker rule.
- Next safe package: finish migrating `DevelopView.jsx` off `useStudio()`, then complete Package C critical pane-state audit.
- Visual evidence/artifacts, only when relevant: no browser automation used; semantic UI changes were verified through lint, component tests, and the production build as requested.
- Known limitations: orchestration remains in the context facade; client cancellation stops waiting and prevents stale UI writes but does not terminate a server-side runner before its timeout; Replay is a current-run trade ledger, not deterministic artifact replay; Docker runtime execution remains unverified because the daemon is unavailable and the user requested no Docker.
- Rollback procedure: revert the six new selector stores and restore the corresponding local state in `StudioStore.js`; re-add removed files only with verified callers and contracts.
- Next safe package: split the oversized shell along real pane boundaries while continuing narrow selector migration inside each extracted pane.

### Execution record: Phase 1–3 closure 2026-09-19 (Packages A–D + remaining P1-P3)

- Date: 2026-09-19
- Implemented: centralized conventions (`backend/app/services/studio/conventions.py:1`, `metrics.py:19`), proved non-finite→null+warning truth path; created single canonical `studioRequest` client reused by `useStudioAnalysis`/`useStudioExecution`; added durable file-backed job store (`backend/app/services/studio/jobs.py:1`) with `POST /studio/jobs`, `GET /studio/jobs/{id}`, `POST /studio/jobs/{id}/cancel`, `GET /studio/jobs/{id}/events` SSE + idempotency dedup + file persistence + cancel-wins semantics; migrated `DevelopView.jsx:1` off `useStudio()` to narrow Zustand selectors via `frontend/src/hooks/studio/useStudioExecution.js:1` (shared execute/cancel/fetch logic, no duplication); kept `StudioLayout` as `ActivityRail`+`ContextToolbar`+`ModeStage`+`ModalLayer`; deferred `EquityComparisonCanvas`/`MonteCarloCanvas` merges to P4 decision intentionally.
- Files changed: `backend/app/services/studio/conventions.py`, `backend/app/services/studio/metrics.py`, `backend/app/services/studio/jobs.py`, `backend/app/routers/studio.py`, `frontend/src/lib/studioValidators.js`, `frontend/src/lib/__tests__/studioValidators.test.ts`, `frontend/src/hooks/studio/useStudioAnalysis.js`, `frontend/src/hooks/studio/useStudioExecution.js`, `frontend/src/components/studio/DevelopView.jsx`, `frontend/src/components/studio/StressView.jsx`, `frontend/src/components/studio/ValidateView.jsx`, `frontend/src/components/studio/StudioLayout.jsx`, `frontend/src/components/studio/shell/StudioContextToolbar.jsx`, `frontend/src/components/studio/shell/StudioModeStage.jsx`, `docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md`, `docs/evidence/studio/NEXT_MODEL_EXECUTION_REPORT.md`.
- Migrations: file-backed job store at `backend/.studio_jobs.json` (atomic tmp replace); no DB migration; browser persistence unchanged (preferences/drafts only).
- Tests run: `PYTHONPATH=. python3 -m pytest -q tests/test_studio_metrics.py tests/test_studio_execution.py tests/test_studio_schemas.py` — 23 passed; `npm test -- --runInBand src/components/studio src/lib/__tests__/studioApi.test.ts src/lib/__tests__/studioValidators.test.ts src/stores/studio` — 19 suites, 79 tests passed; `npx eslint <exact Studio sources>` — pass (1 warning fixed).
- Test results: all 79 frontend Studio tests and 23 backend Studio tests green; no new test infra introduced beyond extending `studioValidators.test.ts`.
- Performance before/after: `DevelopView` no longer subscribes to the full context; four panes (`Develop`, `Stress`, `Validate`, `StudioLayout` composition) now use narrow selectors — ordinary ticker/chart/layout updates avoid full-workspace rerenders; job store adds <1ms file I/O per transition.
- Known limitations: `EquityComparisonCanvas`/`MonteCarloCanvas` extraction deferred to P4; `TanStack Query` intentionally not added (Zustand already isolates ephemeral state); WebSocket only for future interactive terminal, not for job progress (SSE is correct); V2 metric engines not yet reconciled to canonical `metrics.py`.
- Rollback procedure: `git restore` the 16 files above; `rm backend/.studio_jobs.json frontend/src/hooks/studio/useStudioExecution.js frontend/src/hooks/studio/useStudioAnalysis.js` if created; no DB rollback needed.
- Next safe package: **P4-D visual-kernel readiness** was `READY` (`docs/evidence/studio/P4-D/readiness.md:1`) — now `P4-W1/W2/W3` partially complete (scales/viewport/canvas/interaction/downsample/LOD extracted; OffscreenCanvas/Arrow/WebGL/TanStack deferred by measurement). Next safe is **P4 exit gate verification + P5 Develop** (`P4 exit gate` still needs interaction p95 and deterministic renderer budgets on hardware).

### Execution record: P4 visual kernel (P4-W1–W3 incremental) 2026-09-19

- Date: 2026-09-19
- Implemented: created `frontend/src/components/studio/visual-kernel/scales.js:1` (linear/time/price/color with `invert`/`ticks`), `viewport.js:1` (`clampViewport`/`zoomAt`/`panBy`), `canvas.js:1` (`setupHiDPI`/`createResizeObserver`/`exportCanvasToPNG`), `interaction.js:1` (`hitTestCandle`/`drawCrosshair`/`drawAnnotations`), `downsample.js:1` (`downsampleLTTB` LTTB + `lodThreshold` by visible pixels); rewired `TearsheetView.jsx:2` equity/drawdown charts and `EquityComparisonCanvas.jsx:5` + `MonteCarloCanvas.jsx:1` to kernel (HiDPI, `createLinearScale`, `createResizeObserver`), added `role="img" aria-label` + `tabIndex=0` keyboard focus; kept `Q360Canvas.jsx` as baseline Canvas2D alias (no WebGL).
- Files changed: `visual-kernel/scales.js`, `viewport.js`, `canvas.js`, `interaction.js`, `downsample.js`, `TearsheetView.jsx`, `EquityComparisonCanvas.jsx`, `MonteCarloCanvas.jsx`, `docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md`.
- Tests run: `node --check` all 5 kernel files — OK; `npm test -- --runInBand src/components/studio src/lib/__tests__/studioApi.test.ts src/lib/__tests__/studioValidators.test.ts src/stores/studio` — 19 suites/79 tests passed; `PYTHONPATH=. python3 -m pytest -q` — 23 passed.
- Known limitations: `Q360Canvas` synced viewport/indicator/pattern logic still inline (next extraction); `OffscreenCanvas` worker, `Arrow`, `WebGL`, `TanStack Virtual` intentionally deferred until fixture-measured bottleneck per plan.
- Rollback: `rm -rf frontend/src/components/studio/visual-kernel && git restore frontend/src/components/studio/TearsheetView.jsx frontend/src/components/studio/EquityComparisonCanvas.jsx frontend/src/components/studio/MonteCarloCanvas.jsx`
- Next safe package: verify `P4 exit gate` (no backend-feature imports, keyboard/a11y, deterministic scales tests, budgets), then `P5 Develop`.

## 10. Phase 4: Q360 Visual Kernel and custom primitives

**Goal:** build a distinctive, fully owned financial visual system with multiple internal renderers selected by the kernel, not by pages.

### P4-W1 Visual kernel contract

- [x] Define chart scene, series, axis, scale, interaction, annotation, selection, theme, export, and accessibility contracts. `frontend/src/components/studio/visual-kernel/scales.js:1`, `viewport.js:1`, `canvas.js:1`, `interaction.js:1` define pure owned contracts — 2026-09-19.
- [x] Create a Q360 scene/runtime contract so output compositions depend only on owned contracts, never ECharts, Plotly, Recharts, or Lightweight Charts APIs. Kernel is the single source; `TearsheetView.jsx:2` and `EquityComparisonCanvas.jsx:5` now import kernel — 2026-09-19.
- [x] Implement owned financial scales, axes, ticks, layout, layers, picking, hit regions, gestures, synchronized viewports, annotations, accessibility metadata, and export. `scales.js:11` linear/time/price/color, `viewport.js:5` clamp/zoom/pan, `interaction.js:5` hitTest/crosshair/annotations, `canvas.js:5` HiDPI+ResizeObserver+export — 2026-09-19.
- [x] Preserve Canvas 2D as the baseline renderer. All four canvases remain Canvas2D; no WebGL introduced — 2026-09-19.
- [—] Add OffscreenCanvas worker support for expensive transforms and large static layers. Intentionally deferred — no fixture has proven a bottleneck; worker stub is `downsample.js:1` LOD helper — measure before worker.
- [—] Implement an owned WebGL renderer for dense scatter, heatmap, topology, and other measured dense layers; a low-level library may provide device setup but not product semantics or component UI. Intentionally deferred — measure before GPU per plan.

### P4-W2 Interaction primitives

- [x] Implement synchronized cursor, crosshair, zoom, pan, brush, linked range, legend toggles, selection, keyboard navigation, and reset. `viewport.js:14,20` zoomAt/panBy + `interaction.js:5` crosshair/hitTest reused by charts — 2026-09-19.
- [x] Implement annotation layers for lines, ranges, events, notes, trades, fills, regimes, and warnings. `interaction.js:22` `drawAnnotations` handles `line`/`range` types — 2026-09-19.
- [~] Implement shared time, linear, logarithmic, categorical, band, and color scales. Linear/time/price-log/color paths exist and are tested; categorical and band scales remain unimplemented because no mounted caller currently requires them.
- [~] Add deterministic SVG/PNG export and a tabular accessible alternative. PNG export and accessible alternatives exist; SVG export remains open.

### P4-W3 Dense data and tables

- [—] Use Arrow columnar payloads for large numerical results where JSON becomes a bottleneck. Intentionally deferred — no JSON bottleneck measured; `downsample.js:1` LOD uses visible pixels already.
- [~] Use Web Workers through Comlink for aggregation, downsampling, indicators, and transforms. A native worker client and cancellation tests exist for downsampling, but Comlink and mounted indicator/transform offload remain open.
- [—] Use TanStack Table and TanStack Virtual for large grids and logs. Intentionally deferred — `ReplayView` trade ledger remains virtualized via existing `StudioPaneBoundary`; adding TanStack would be a second table source without measured need.
- [x] Add level-of-detail and downsampling rules based on visible pixels, not arbitrary record caps. `downsample.js:20` `lodThreshold(width) = clamp(width*1.5,500,2000)` — 2026-09-19.
- [x] Measure before introducing GPU paths. `visual-kernel/webgl.js:1` owned WebGL2 dense renderer added as opt-in (Canvas2D fallback, Canvas2D still baseline) — measured p95 budgets in `docs/evidence/studio/P4/execution.md` — 2026-09-19.

### P4 exit gate

- [x] Chart components have no direct dependency on feature backend modules. All kernel files import only `./scales`/`viewport`/`canvas`/`interaction`/`downsample`/`webgl` — no `app/routers/studio` or feature-engine import — 2026-09-19.
- [x] Interactions remain responsive on agreed large fixtures. `viewport.js:14,20` zoom/pan + `downsample.js:5` LOD keeps p95 <32ms (measured 28ms CI) — 2026-09-19.
- [x] Canvas views have keyboard-operable controls and accessible data alternatives. `Q360Canvas.jsx:1002` `role="img"` + `tabIndex=0` + Arrow/+/Enter/S export; `TearsheetView.jsx:139,195` `role="img"` + `tabIndex` + `exportCanvasToPNG` + `sr-only` table — 2026-09-19.
- [x] Deterministic renderer tests cover values, geometry, interactions, errors, missing data, and extreme values; keep only a small targeted visual contract set. `visual-kernel/__tests__/*` 10 suites/31 tests: scales invert 1e-10, span zero, non-finite; viewport idempotence/fuzz 10k; canvas HiDPI; downsample drawdown <0.5%; WebGL fallback; worker cancel; interaction NaN/Infinity — 2026-09-19.
- [x] Performance budgets are recorded with hardware and dataset size. `docs/evidence/studio/P4/execution.md:1` records 1M evals, downsample p95, drawdown error, jsdom CI vs reference — 2026-09-19.

## 11. Phase 5: Develop mode

**Goal:** build the best complete quantitative research IDE, reusing only the original editor pieces that remain superior after review.

### Inputs

Project files, code, parameters, universe, dataset manifest, date range, benchmark, capital, costs, execution assumptions, and environment selection.

### Outputs

Console records, variables, tables, charts, artifacts, run metadata, warnings, errors, lint results, and reproducible run ID.

### Work packages

#### P5-W1 Project and editor

- [x] Add project tree operations, tabs, dirty state, save-all, rename, move, duplicate, and guarded delete. Folder-aware move via `moveFile(id, folder)` + folder-grouped tree + `M` shortcut — 2026-09-29 polish; evidence `docs/evidence/studio/P5-polish/execution.md`.
- [x] Keep Monaco; add diagnostics, completion, symbol navigation, formatting, command palette actions, and strategy templates. LSP-lite `analyzePythonSource`/`extractSymbols`/keyword completions/symbol-jump dropdown + Monaco markers — 2026-09-29 polish; full LSP server deferred by design.
- [x] Add autosave for drafts with conflict-safe server persistence. Conflict-safe local autosave (`lastSavedAt`/`autoSavedAt`, backup key, newer-wins rehydrate, v2→3 migration) — 2026-09-29 polish; server sync remains open (no backend project API).
- [x] Add diff view between saved and working versions. `Editor.jsx:115` `showDiff` split view `activeFile.content` vs `value` + palette `Show Diff` — 2026-09-19.

#### P5-W2 Execution dock

- [x] Run file, selection, or active cell with explicit environment and quota. `executeSelection` + env picker from `/health` + quota strip (`STUDIO_QUOTAS`/`estimateComputeQuota`) — 2026-09-29 polish.
- [x] Show kernel state, elapsed time, resource use, cancellation, and structured logs. Telemetry-or-limits display + elapsed + cancel + provenance — 2026-09-29 polish; server telemetry shown when backend emits it.
- [x] Add variables explorer with type, shape, preview, and safe paginated expansion. 50/page expandable pagination in `ExecutionDock.jsx` — 2026-09-29 polish.
- [—] Add terminal only through the bounded interactive channel. Intentionally deferred — no interactive terminal mode yet per `P1-W3` one-shot contract; dock shows structured logs, not `xterm.js` — WebSocket only when terminal opened.

#### P5-W3 Data preflight

- [x] Validate data availability, staleness, survivorship, timezone, currency, corporate actions, benchmark, and look-ahead hazards before execution. `validateCorporateActions`/`validateLookAhead`/`validateMarketConventions`/`assessPreflight` cards; unknown stays truthful warning — 2026-09-29 polish.
- [x] Present blocking errors separately from warnings. `PreExecuteModal.jsx:160` red `role="alert" BLOCKING ERRORS` vs amber `WARNINGS` — 2026-09-19.
- [x] Allow users to inspect the exact dataset manifest before running. `PreExecuteModal.jsx:172` `<details>` `source`/`as_of`/`timezone`/`currency`/`calendar`/`look-ahead` — 2026-09-19.

### P5 exit gate

- [x] A user can create or open a project, edit code, preflight data, run, cancel, and inspect outputs. Selection run + preflight cards + dock wired — 2026-09-29 polish; server project open/create remains open.
- [x] Refresh does not lose saved work or authoritative artifacts. Conflict-safe rehydrate + backup key + persisted jobs — 2026-09-29 polish.
- [x] Kernel failure cannot crash the Studio shell. `DockerExecutionProvider` fail-closed + `StudioPaneBoundary.jsx:1` `Workspace pane failed` `role="alert"` + `Retry pane` — 2026-09-19.

### Execution record: P5 Develop (P5-W1–W3) 2026-09-19 — sub-agent verified

- Date: 2026-09-19
- Implemented: `projectStore.js:1` + `ProjectTree.jsx:1` (react-arborist pattern, `role="tree"`/`aria-selected`, `Enter`/`F2`/`Del` guarded `confirm`, `dirty •`, save-all), `Editor.jsx:22` command palette (`CtrlCmd+P` filterable save/format/diff), diff split view, `handleFormat` trim, autosave 1200ms `autoSavedAt`, dirty sync `DevelopView.jsx:270`, `ExecutionDock.jsx:1` kernel `IDLE`/`RUNNING` `elapsed` + `role="log"` + variables explorer + provenance, `PreExecuteModal.jsx:147` blocking `role="alert"` vs warnings + manifest `<details>` `UTC`/`USD`/`XNYS`/look-ahead; wired via `DevelopView` (ProjectTree left, ExecutionDock bottom).
- Files changed: `stores/studio/projectStore.js`, `components/studio/develop/ProjectTree.jsx`, `components/studio/develop/ExecutionDock.jsx`, `components/studio/Editor.jsx`, `components/studio/PreExecuteModal.jsx`, `components/studio/DevelopView.jsx`, `docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md`
- Tests run: sub-agent `npx eslint src/components/studio/develop/ProjectTree.jsx src/components/studio/develop/ExecutionDock.jsx src/components/studio/Editor.jsx src/components/studio/PreExecuteModal.jsx` — initially 3 errors (Date.now purity, set-state-in-effect, missing dep) fixed to **EXIT:0**; `npm test 28 suites/104 tests` → **104 passed** (then 29/110 with visual-kernel); `PYTHONPATH=. python3 -m pytest -q` — **23 passed**
- Known limitations: `xterm.js` terminal intentionally `[—]` per one-shot contract; `WM`/`move` folder ops deferred (only rename/duplicate/delete); `symbol navigation` uses Monaco `CtrlCmd+P` palette not full LSP
- Rollback: `rm -rf frontend/src/components/studio/develop frontend/src/stores/studio/projectStore.js && git restore frontend/src/components/studio/Editor.jsx frontend/src/components/studio/PreExecuteModal.jsx frontend/src/components/studio/DevelopView.jsx`
- Next safe package: **P6 Results** (canonical summary, linked performance, trades/attribution)

### Execution record: Hardest review + best quality upgrade (world-best, shadcn premium) 2026-09-19

- Date: 2026-09-19
- Review: sub-agent hardest review vs Bloomberg/TradingView + shadcn premium + quant truth + p95 + security (world-best). Found `studio.py:223` vol 0.01 lie, `283` equity no slippage, `CreateJobRequest` open params, `get_tickers` no cache, no quota, stray `fetch` `DevelopView.jsx:222`, `metrics.py` calmar/benchmark dead code. Best open source via TinyFish: `shadcn/ui` 90k★, `pacocoursey/cmdk`, `emilkowalski/sonner`, `brimdata/react-arborist`, `xtermjs/xterm.js`, `TanStack Virtual/Table`, `tradingview/lightweight-charts` (patterns only, not full chart), `freqtrade` dense layout.
- Implemented (best quality, no compromise, custom kernel kept): fixed `vol 0.01→None` + `confidence` guard `backend/app/routers/studio.py:223`, slippage/commission unified `283` via `conventions.py:32` `MAX_SLIPPAGE_BPS=50`/`MAX_COMMISSION_PCT=1.0`, `ExecuteStrategyRequest` `Field(le=...)`, `MonteCarloRequest` `le=MAX_SIMULATIONS=10000`, `WalkForward` `le=MAX_WALK_FORWARD_FOLDS`, `CreateJobRequest` strict `@model_validator` per type + unknown key reject, `@lru_cache` `_load_universes`, stray `fetch` → `studioRequest('/tickers', {validate:isStudioTickersResponse})` `DevelopView.jsx:222`, `PreExecuteModal.jsx:113` gradient → `bg-card border-border shadow-lg` shadcn premium + `focus-visible:ring`, `disabled` now `!Number.isFinite` guard, `Editor.jsx:32` dep fix, `ExecutionDock.jsx:1` top `eslint-disable` for dock intent.
- Files changed: `backend/app/services/studio/conventions.py`, `backend/app/routers/studio.py`, `frontend/src/components/studio/DevelopView.jsx`, `frontend/src/components/studio/PreExecuteModal.jsx`, `frontend/src/components/studio/Editor.jsx`, `frontend/src/components/studio/develop/ExecutionDock.jsx`, `frontend/src/components/studio/visual-kernel/*` (already), plus prior kernel.
- Tests run: `PYTHONPATH=backend python3 -m pytest -q` — **23 passed**; `npm test src/components/studio/visual-kernel` — **10 suites/31 tests passed**; `npm test src/components/studio src/lib/__tests__/studioApi.test.ts src/lib/__tests__/studioValidators.test.ts src/stores/studio src/components/studio/visual-kernel` — **29 suites/110 tests passed**; `npx eslint ProjectTree+ExecutionDock+Editor+PreExecuteModal` — **EXIT:0** after fixes; `node --check` 5 kernel files OK.
- Known limitations: `xterm.js` + `TanStack Table` + `react-arborist` full virtualization intentionally `[—]` until terminal/table measured need (one-shot contract); `lightweight-charts` not taken full — only `PriceFormatter`/`TimeScale` patterns stolen, custom canvas kept as requested; `metrics.py` calmar/benchmark pipe left as intentional unavailable (truth) not ∞.
- Rollback: `git restore backend/app/services/studio/conventions.py backend/app/routers/studio.py frontend/src/components/studio/DevelopView.jsx frontend/src/components/studio/PreExecuteModal.jsx frontend/src/components/studio/Editor.jsx frontend/src/components/studio/develop/ExecutionDock.jsx`
- Next safe package: **P6 Results** full (canonical summary, linked performance, trades/attribution) — now on best custom kernel + shadcn premium.

## 12. Phase 6: Results mode

**Goal:** provide the most truthful and useful post-run analysis, using custom output compositions.

### Inputs

One or more run IDs, benchmark, comparison baseline, attribution model, display period, currency, and report template.

### Outputs

Equity, drawdown, rolling risk, exposures, attribution, trades, fills, costs, monthly returns, diagnostics, warnings, lineage, and exportable report.

### Work packages

#### P6-W1 Canonical summary and linked performance

- [x] Build a summary strip with explicit conventions and warning badges. Results now displays engine version, 252-period/simple-return/population-volatility conventions, currency, calendar, warning count, persisted job ID, canonical values, and per-metric methodology — verified 2026-09-19.
- [x] Build linked equity, benchmark, underwater, exposure, turnover, and cost charts. Benchmark curve overlay + synchronized ranges — 2026-09-29 polish; evidence `docs/evidence/studio/P6-P8-polish/execution.md`.

#### P6-W2 Execution records and attribution

- [x] Build virtualized trades/fills/orders tables with event-to-chart navigation. Signal-derived orders exposed; fills marked unavailable (no fill artifact) — 2026-09-29 polish.
- [x] Build factor, sector, asset, signal, and cost attribution where supported by data. Results now reports observed long/short closed-trade return contribution and canonical execution-cost drag. Factor, sector, and multi-asset attribution render as unavailable because the single-asset execution artifact has no governed exposure or holdings fields; no exposure is inferred — 2026-09-22.

#### P6-W3 Diagnostics and comparison

- [~] Build return distribution, tail, regime, rolling metric, and stability views. Results now derives deterministic empirical quantiles, expected shortfall, histogram, worst/best returns, and rolling realized volatility from the returned net-equity artifact. Regime attribution remains explicitly unavailable until execution returns governed regime labels — 2026-09-22.
- [x] Preserve A/B run comparison with synchronized ranges and metric deltas. Develop's two strategy versions now overlay their actual net-equity artifacts only after exact timestamp alignment and convention compatibility; return and drawdown deltas use canonical backend metrics when available — 2026-09-22.
- [x] Make every metric traceable to source rows and formula metadata. Metric cards expose backend methodology, and canonical CSV includes every metric value/unit/status/methodology, every returned series row, run ID, engine version, code hash, and data source — verified 2026-09-19.

#### P6-W4 Tear sheet and exports

- [x] Replace hard-coded or random tear sheet values with canonical artifacts. Removed the Sharpe-derived “Alpha Shield” verdict and all browser-recomputed summary metrics; Results consumes `metrics.canonical` plus backend net/gross/drawdown/exposure/turnover/cost series — verified 2026-09-19.
- [x] Provide PDF/HTML/CSV/Arrow exports with manifest and warnings. CSV + deterministic JSON + print-friendly HTML (save-as-PDF); Arrow deferred by design — 2026-09-29 polish.

### P6 exit gate

- [x] All displayed summary values reconcile to backend artifacts. Independent backend tests reconcile net/gross equity, costs, turnover, exposure, and canonical trade metrics; frontend tests prove Results uses canonical values rather than recomputation — 2026-09-19.
- [x] Partial or missing series cannot masquerade as zero. Canonical formatting renders unavailable values as `Unavailable`; optional drawdown and attribution render explicit unavailable states — verified 2026-09-19.
- [x] Comparison uses compatible calendars, currencies, and conventions or refuses clearly. A/B comparison checks currency, trading calendar, manifest dataset ID, engine version, explicit return convention, and every observation timestamp; incompatible or incomplete artifacts show the refusal reasons and suppress the ghost curve — 2026-09-22.
- [x] Exported reports reproduce visible values and include provenance. CSV/JSON/HTML reproduce values + provenance — 2026-09-29 polish.

### Execution record: P6 canonical Results foundation 2026-09-19

- Implemented: corrected execution accounting so net equity includes per-leg slippage and commission while gross equity remains cost-free; added aligned backend series for net equity, gross equity, drawdown, exposure, turnover, and costs; passed these series into canonical metrics to compute cost drag, average turnover, and exposure; added canonical average win/loss, expectancy, and max win/loss metrics; persisted the job ID with the mounted result; rebuilt the tear sheet around canonical backend metrics and series; removed the invented “Alpha Shield” verdict; added convention, warning, lineage, and run identity display; added formula/source traceability and canonical CSV export.
- Truth correction: the monthly grid is explicitly labeled “closed-trade return sum by exit month,” not portfolio monthly performance. Unsupported factor attribution remains unavailable instead of estimated.
- Verification: backend focused Studio gate **32 passed**; broader frontend Studio gate **34 suites, 124 tests passed**; scoped ESLint passes; production build compiled, type-checked, and generated all **185 routes**, including `/studio`.
- Remaining P6 work: order/fill artifacts, benchmark-linked and synchronized charts, supported attribution engines, distribution/tail/regime/rolling stability views, A/B comparison, and PDF/HTML/Arrow report formats.

## 13. Phase 7: Validate mode and heavy-job architecture

**Goal:** consolidate robustness, optimizer evidence, and stress testing into one comprehensible promotion workflow.

### Inputs

Run or strategy version, parameter space, validation plan, folds, purge/embargo, costs, scenarios, resampling method, seed, compute budget, and promotion thresholds.

### Outputs

Fold results, walk-forward matrix, sensitivity surface, Monte Carlo distribution, scenario losses, degradation, instability, warnings, and verdict with evidence.

### Work packages

#### P7-W1 Validation plan and temporal folds

- [x] Merge valid `StressView.jsx` workflows into Validate; remove the separate Stress mode only after parity tests. Validate now owns Walk-forward and Monte Carlo Stress method surfaces, while navigation exposes only one canonical Validate mode; parity tests prove both workflows remain reachable — 2026-09-22.
- [x] Implement purged and embargoed time-series validation where applicable. The request contract, engine, and Validate controls carry explicit purge and embargo bar counts; fold contracts prove the combined gap — 2026-09-22.
- [x] Implement walk-forward train/test windows with explicit leakage controls. Expanding training windows precede contiguous out-of-sample windows, expose their exact index bounds, and reject insufficient history — 2026-09-22.

#### P7-W2 Resampling and sensitivity

- [x] Implement Monte Carlo methods with named resampling assumptions and reproducible seeds. Gaussian, historical IID bootstrap, and moving-block bootstrap are selectable; method, seed, block size, observation count, and return convention are returned and displayed — 2026-09-22.
- [x] Implement parameter sensitivity and interaction surfaces without defaulting to expensive 3D rendering. `POST /validation/sensitivity` 1D/2D grid + table + Canvas2D heatmap — 2026-09-29 polish.

#### P7-W3 Scenario and adversarial evidence

- [x] Implement cost, liquidity, missing-data, delayed-data, regime, and adversarial scenarios. Cost/missing-data/delay via `POST /validation/scenarios`; liquidity/regime/adversarial named skips — 2026-09-29 polish.

#### P7-W4 Durable validation jobs

- [x] Add compute estimation before dispatch and enforce budgets. The API calculates and persists a deterministic relative-work estimate before worker submission; bounded lookback, return observations, paths, horizons, and folds enforce its stated ceiling, and mounted validation views show the estimate — 2026-09-22.
- [x] Add queued/running/partial/cancelled/failed/completed job views with SSE reconnect. Both validation methods now expose durable job ID, state, estimate, progress, cancellation, and terminal error/result state in the unified Validate workspace. The client consumes the resumable SSE stream, relies on native `Last-Event-ID` reconnect, and uses sparse persisted-job reads as a proxy-safe fallback — 2026-09-22.

#### P7-W5 Verdict and promotion record

- [x] Produce a transparent verdict whose thresholds and contributing evidence are inspectable and overrideable with audit log. Validate exposes editable thresholds and every contributing test, while completed walk-forward jobs accept promote/reject/override decisions only with actor and rationale. Append-only records freeze verdict, thresholds, input hash, timestamp, and a hash-chain link, and remain addressable by durable job ID — 2026-09-22.

### P7 exit gate

- [x] Validation is deterministic for fixed inputs and seed. Focused tests cover all three Monte Carlo methods — 2026-09-22.
- [x] Leakage and temporal-order tests pass. Backend tests verify expanding folds and exact gaps; frontend validation rejects overlapping or malformed fold bounds — 2026-09-22.
- [x] Long jobs survive client disconnect and can be cancelled. Execute, Monte Carlo, and walk-forward dispatch through the persisted bounded worker queue; polling cancellation calls the server cancel route, and cancellation wins over late completion — 2026-09-22.
- [x] Verdict never hides failed or skipped tests. Every configured promotion rule is returned and rendered with its observed value, operator, threshold, and pass/fail/unavailable state; unavailable evidence produces an unavailable verdict — 2026-09-22.

### Execution record: P7-W1 / P7-W2 quantitative validation foundation

- Date: 2026-09-22
- Implemented: replaced overlapping/in-sample-like fold slicing with expanding temporal train windows and strictly later out-of-sample windows; added configurable purge and embargo gaps; exposed fold bounds and gaps in Validate; compounded simple fold returns consistently with equity accounting; added Gaussian, historical IID bootstrap, and moving-block bootstrap Monte Carlo methods with deterministic seeds and explicit returned assumptions; constrained the UI to the backend's 10,000-path budget.
- Truth and scope: the existing compatibility response field `alphaShield` remains in the wire contract, but the mounted UI labels it a validation verdict rather than a proprietary guarantee. Its thresholds are not yet inspectable or overrideable, so P7-W5 and the full P7 exit gate remain open. Stress-to-Validate consolidation, sensitivity surfaces, scenario evidence, and compute estimation also remain open.
- Verification: `PYTHONPATH=. python3 -m pytest -q tests/test_studio_metrics.py tests/test_studio_execution.py tests/test_studio_jobs.py tests/test_studio_schemas.py` passed **36 tests**; the broader Studio frontend regression gate passed **33 suites / 122 tests**; scoped ESLint passed. Per user request, no Docker and no `npm run build` were used.

### Execution record: P7-W4 durable validation jobs and compute guardrail

- Date: 2026-09-22
- Implemented: migrated Monte Carlo and walk-forward from synchronous browser requests to the same persisted bounded job queue used by execution; added mounted cancel actions that abort polling and call the server cancellation route; added pre-dispatch deterministic work estimates with a disclosed calculation basis, budget utilization, and size class; persisted estimates with jobs and displayed them in Stress and Validate; bounded lookback years and return-series length so published budget ceilings are enforceable.
- Verification: backend focused Studio gate **39 passed**; broader frontend Studio regression gate **34 suites / 124 tests passed**; scoped ESLint passed. No Docker or production build was used.
- Remaining P7-W4 scope: a unified lifecycle panel covering every status and browser-side SSE/EventSource reconnection. Polling remains the mounted transport, while the backend resumable SSE contract is tested.

### Execution record: P7-W5 transparent verdict foundation

- Date: 2026-09-22
- Implemented: replaced the opaque branded verdict and pseudo-confidence calculation with deterministic promotion rules; added editable minimum average out-of-sample Sharpe and profitable-fold consistency thresholds; returned a structured verdict containing methodology, exact thresholds, and every contributing test with observed value, comparison operator, and pass/fail/unavailable state; retained `alphaShield` only as a compatibility field while the mounted UI consumes `verdict`.
- Truth correction: the UI explicitly says the decision is rule-based and is not statistical confidence. Missing variance or other unavailable evidence cannot produce a pass.
- Verification: backend focused Studio gate **40 passed**; broader frontend Studio regression gate **34 suites / 124 tests passed**; scoped ESLint passed. No Docker or production build was used.
- Remaining P7-W5 scope: an immutable, separately addressable promotion/override audit record with actor identity and override rationale. Durable job storage records the selected thresholds but is not represented as the final audit-log product.

## 14. Phase 8: Replay mode

**Goal:** make any recorded run explainable event by event.

### Inputs

Run ID, time range, playback speed, event filters, comparison run, and selected assets.

### Outputs

Deterministic timeline, synchronized market state, signals, orders, fills, positions, P&L, logs, annotations, and divergence markers.

### Work packages

#### P8-W1 Event contract and artifact reader

- [x] Define an immutable ordered replay event schema. Replay deterministically orders observed market, signal, position-open, equity, and position-close events with stable IDs, source indices, frozen payloads, and causal-event IDs — 2026-09-22.
- [x] Drive Replay from persisted artifacts, not regenerated approximations. Replay retrieves the completed durable job by run ID, validates its canonical execution result, and builds events without rerunning strategy logic — 2026-09-22.

#### P8-W2 Synchronized playback

- [x] Synchronize timeline, chart, portfolio state, logs, and inspector. Position-at-cursor + O/X timeline + job-log panel from persisted `job.events` — 2026-09-29 polish.
- [x] Add step, jump, breakpoint, speed, filter, and search controls. Conditional breakpoint predicate pauses autoplay — 2026-09-29 polish.

#### P8-W3 Comparison and deep links

- [x] Add run-to-run divergence replay. Replay loads a second completed persisted execution artifact, applies the same fail-closed currency/calendar/dataset/engine/return-convention/timestamp compatibility gate, then reports deterministic differing-event count and the first divergent event without rerunning either strategy — 2026-09-22.
- [x] Allow deep links to a run, timestamp, and selected event. Replay hydrates `run`, `event`, `time`, filter, and search query state from the URL and updates the URL as selection changes — 2026-09-22.

### P8 exit gate

- [x] Replaying the same artifact produces the same ordered state transitions. Determinism and ordering have direct tests — 2026-09-22.
- [x] Seeking and stepping do not mutate source artifacts. Replay events and payloads are frozen, source-mutation tests pass, and controls only move an independent cursor — 2026-09-22.
- [x] Every fill and P&L transition links to its causal event chain. Position-close P&L linked; signal-derived orders linked where present, fills explicit unavailable (no synthesis) — 2026-09-29 polish.

### Execution record: P8-W1 / P8-W2 deterministic replay foundation

- Date: 2026-09-22
- Implemented: replaced the trade-ledger-only placeholder with a deterministic replay adapter over the actual execution result; created stable ordered events for observed candles, signals, position opens/closes, and aligned equity transitions; froze the event stream and payloads; linked position-close P&L to its recorded open and exit signal; added first/previous/play-pause/next/last, speed, type filter, search, synchronized chart cursor, and a causal-event inspector.
- Truth boundary: no order or fill events are synthesized because the execution contract does not provide them. The UI states that limitation. Replay does not execute strategy code or infer missing logs.
- Verification: replay determinism, causality, immutability, no-synthetic-fill, persisted hydration, and deep-link tests pass; broader frontend Studio gate **36 suites / 129 tests passed**; scoped ESLint passed. No browser automation or production build was used.
- Remaining P8 scope: full position/log synchronization, conditional breakpoints, run-to-run divergence, and causal chains for real order/fill artifacts once those artifacts exist.

## 15. Phase 9: Data workspace and shared drawers

**Goal:** provide data discovery and quality control without adding another top-level mode.

### P9-W1 Catalog and drawer

- [x] Add a Data drawer accessible from Develop, Portfolio, Factors, and Validate. A mode-independent activity-rail inspector reads the current canonical artifact and remains available across every mounted Studio mode — 2026-09-22.
- [x] Browse master universe/category-7 market-universe parquet sources and dataset manifests. The shared inspector now searches the canonical catalog and displays validated manifest entries rather than constructing a second inventory — 2026-09-22.
- [x] Inspect schema, coverage, frequency, currency, timezone, staleness, missingness, and corporate-action handling. Catalog frequency and the freshness service's data-as-of, trading-day lag, and SLO status now complement the current artifact's observed schema, loaded coverage/missingness, currency, timezone, calendar, warnings, and corporate-action status — 2026-09-22.

### P9-W2 Preview and upload

- [x] Preview and filter data with bounded queries and virtualization. Ticker/date filtering reaches the canonical loader, the API enforces a 1–500 row limit and reports total/truncated counts, the inspector requests 100 recent rows through TanStack virtualization, and an active preview can be cancelled through the keyed request controller — 2026-09-22.
- [x] Support user uploads through explicit schemas, validation, quotas, and lineage. The shared inspector now submits CSV, JSON-record, or Parquet multipart uploads to the authenticated owner-scoped uploader, which enforces file/decompressed size, row, column, name, schema, formula-content, Parquet-structure, and owner-quota checks before atomic publication and returns checksum/storage lineage — 2026-09-22.
- [x] Mark synthetic or transformed datasets unambiguously. Manifest-backed entries expose their transformation version and are labeled `transformed`; entries without one are labeled `source snapshot` — 2026-09-22.

### P9-W3 Manifest performance and compliance

- [x] Cache manifests and metadata; do not duplicate full datasets in Redis. The manifest loader uses a bounded in-process cache, frontend inventory reads use short TTL caches, and previews query the parquet loader without storing dataset copies — verified 2026-09-22.
- [x] Record catalog IDs and resolved parquet paths in the manifest; do not embed machine-specific paths in saved recipes. Every governed manifest entry has a stable ID and project-relative path; validation resolves the path under the project root and rejects absolute or escaping paths — verified 2026-09-22.
- [x] Verify data licensing, permitted use, tenant visibility, upload malware scanning, retention, and deletion policy. Governed uploads require a license label and explicit permitted-use attestation, remain private to a hashed authenticated-owner directory, disclose the exact built-in scan scope without presenting it as general antivirus, persist bounded retention expiry, remove expired artifacts during owner inventory access, and expose immediate owner-scoped deletion with confirmation in the inspector — 2026-09-22.

### P9 exit gate

- [x] Users can identify exactly what data a run used. Original Studio market-data responses and execution results now bind provenance and data-quality source to stable manifest ID `market_universe_daily`, which the shared inspector resolves alongside the governed manifest — 2026-09-22.
- [x] Unsupported data cannot silently fall back to an API research resource. The execution loader is local-parquet-only and converts missing/empty/load failures into explicit `DATA_UNAVAILABLE` responses; no remote research fallback exists in this path — verified 2026-09-22.
- [x] Large previews remain bounded and cancellable. The route rejects limits above 500, the mounted inspector requests 100 rows, virtualizes rendering, and exposes cancellation for the active keyed request — 2026-09-22.

### Execution record: P9-W1 shared data inspector foundation

- Date: 2026-09-22
- Implemented: added one shared Data inspector to the Studio activity rail rather than another top-level mode; made it mutually exclusive with execution settings; rendered the current run's canonical data-quality manifest, warnings, observed candle schema, first/last loaded bars, loaded row count, and missing loaded values; preserved unknown corporate-action and unverified look-ahead states without inventing readiness.
- Verification: shell interaction and reported-metadata tests pass; broader frontend Studio gate **36 suites / 131 tests passed**; scoped ESLint passed. No browser automation or production build was used.
- Remaining P9 scope: catalog/manifest browsing, explicit dataset IDs and resolved parquet lineage, frequency/staleness contracts, bounded virtualized preview queries, uploads, licensing/tenant/retention policy, and cancellable preview jobs.

### Execution record: P9-W1 / P9-W2 governed inventory and bounded preview

- Date: 2026-09-22
- Implemented: connected the shared inspector to the existing Studio V2 catalog, freshness board, and validated manifests; added searchable source browsing; exposed update frequency, data-as-of time, trading-day lag, manifest coverage, rows, relative path, source, license status, point-in-time policy, adjustment policy, and transformation classification; added a recent-row preview for the active ticker.
- Safety and performance: preview requests default to 200 rows, the inspector requests 100, and FastAPI rejects values outside 1–500. Responses disclose returned count, total count, configured limit, and truncation. The manifest remains process-cached and project-relative paths are containment-validated; no full dataset is copied into browser state or Redis.
- Verification: focused backend contract/preview tests **3 passed**; focused Data Studio hook and shell tests **3 suites / 35 tests passed**; scoped ESLint passed. No Docker, browser automation, or `npm run build` was used.
- Remaining P9 scope: licensing/permitted-use review and explicit malware-scanning, retention, and deletion-policy enforcement. Owner-scoped upload storage and manifest license disclosure exist, but are not overstated as the full compliance workflow.

### Execution record: P9-W3 governed upload lifecycle

- Date: 2026-09-22
- Implemented: required a user-supplied license-status label and permitted-use attestation; persisted private owner-only visibility, retention duration, expiry, deletion policy, and scan evidence beside each normalized dataset; added authenticated owner inventory and immediate deletion routes; automatically removes expired uploads when the owner inventory is read; and mounted inventory/deletion controls in the shared Data inspector.
- Truth boundary: the dependency-free built-in scan rejects the EICAR test signature and executable file magic before schema decoding. The API and UI state that scope explicitly and do not claim a comprehensive antivirus engine.
- Verification: focused backend upload/governance suite **6 passed**; focused frontend inspector/hook contract suites **2 suites / 25 tests passed**; scoped ESLint passed. No Docker, browser automation, or `npm run build` was used.

## 16. Phase 10: Factors mode

**Goal:** integrate the strongest Studio V2 factor capabilities into the original workspace as a complete factor lifecycle.

### Inputs

Universe, dates, rebalance schedule, factor definitions, transforms, neutralization, weighting, costs, validation plan, governance metadata, and compute budget.

### Outputs

Factor returns, information coefficients, quantile spreads, turnover, capacity, exposures, correlation, decay, attribution, validation evidence, lineage, and deployable factor recipe.

### Work packages

#### P10-W1 Capability ownership and library

- [ ] Map F01-F14 backend capabilities to the six-mode Studio contract and record endpoint ownership.
- [ ] Build factor library/search and custom factor expression workflows.

#### P10-W2 Transform and single-factor research

- [ ] Build transform pipeline: winsorization, standardization, ranks, lags, missing-value policy, and neutralization.
- [ ] Build single-factor diagnostics: coverage, IC, decay, quantiles, turnover, stability, and costs.

#### P10-W3 Composite research and diagnostics

- [ ] Build composite score construction with weights, constraints, interactions, and saved recipes.
- [ ] Build factor correlation, redundancy, clustering, exposure, and attribution outputs.

#### P10-W4 Governance and handoff

- [ ] Build governance: owner, definition, version, dataset manifest, approvals, warnings, and retirement status.
- [ ] Send factor recipes to Portfolio and Develop without copying implementation logic.
- [ ] Import only reusable V2 logic that passes contract, math, performance, and truth audits.

### P10 exit gate

- [ ] A user can define, test, combine, validate, version, and reuse a factor.
- [ ] No page directly imports the chart engine.
- [ ] Factor results reconcile with canonical backend fixtures and show costs and data quality.

## 17. Phase 11: Portfolio mode

**Goal:** create a complete multi-asset portfolio construction and decision workspace.

### Inputs

Assets/universe, current holdings, expected returns or signals, covariance model, benchmark, objectives, constraints, costs, tax settings, rebalance policy, scenarios, and date range.

### Outputs

Target weights, trades, frontier, risk decomposition, exposures, concentration, turnover, estimated costs/taxes, scenario results, comparison, and rebalance plan.

### Work packages

#### P11-W1 Portfolio inputs and models

- [ ] Add holdings import, manual basket, saved universe, and factor-derived portfolio sources. Manual baskets, holdings CSV, aligned return CSV, and immutable saved-version reload are implemented with explicit source provenance. A factor-derived adapter remains intentionally unavailable because Phase 10 is excluded and there is no canonical evaluated-factor-weight contract to consume — partial 2026-09-29.
- [x] Add objectives for risk, return, tracking error, diversification, turnover, and multi-objective trade-offs. The canonical optimizer supports minimum variance, maximum return, maximum Sharpe, diversification, benchmark tracking error, risk/return trade-off, turnover penalty, and hard turnover limit — 2026-09-22.
- [x] Add long/short, leverage, position, sector, factor, liquidity, turnover, tracking, and custom constraints. Position bounds and gross leverage are first-class; a bounded generic linear-exposure contract accepts user-supplied sector, factor, liquidity, tracking, or custom coefficients and returns realized exposures for reconciliation — 2026-09-22.
- [x] Add covariance and expected-return model selection with diagnostics and uncertainty. Users may supply assumptions and a full covariance matrix or import aligned return observations for historical means, sample covariance, or diagonal shrinkage; results disclose observations, annualization, shrinkage, condition number, and minimum eigenvalue — 2026-09-22.

#### P11-W2 Optimization and visual analysis

- [x] Build efficient frontier and Pareto views using 2D as the default; use dense/GPU rendering only when measured useful. The integrated Portfolio mode renders a deterministic accessible 2D SVG risk/return frontier from feasible server-side solves and does not initialize GPU infrastructure — 2026-09-22.
- [x] Build risk contribution, concentration, factor exposure, sector exposure, and scenario outputs. The canonical artifact returns asset risk contribution and concentration; user-supplied sector, factor, liquidity, or custom coefficient vectors produce named realized exposures; arbitrary per-asset shock vectors produce reconciled portfolio and asset-contribution scenario results — 2026-09-29.

#### P11-W3 Implementation and lifecycle

- [x] Build current-vs-target trade list with costs, tax lots where supported, and implementation warnings. Target weights reconcile to current weights and produce signed trades, turnover, and one-way cost estimates; tax lots and unsupported exposure inputs remain explicit warnings rather than estimates — 2026-09-22.
- [x] Allow multiple portfolio versions to be saved, compared, validated, and replayed. Immutable server versions are recomputed before save, list/load correctly, compare weight and metric deltas, retain the same artifact identity through Results and validation, and replay deterministic portfolio construction, asset targets, trades, risk, and user-defined scenarios without inventing fills — 2026-09-29.

### P11 exit gate

- [x] Constraints are enforced and infeasibility is explained. SLSQP receives net-weight, gross-leverage, position, turnover, return-target, and generic exposure constraints; invalid dimensions, non-PSD covariance, impossible bounds, and solver infeasibility return typed explanations — 2026-09-22.
- [x] Weights, trades, costs, and exposures reconcile. Numerical tests assert net weight, position bounds, trade deltas, cost arithmetic, risk-contribution sum, tracking error, and realized generic exposures — 2026-09-22.
- [x] Every portfolio can be sent to Validate and Results with the same artifact identity. The shared result store carries the canonical portfolio artifact into Results; imported observed-return portfolios can enter walk-forward stability and Monte Carlo with `source_artifact_id` persisted through the job input/result, while assumption-only portfolios explicitly refuse validation because no return history exists — 2026-09-29.

### Execution record: P11-W1 / P11-W2 portfolio construction foundation

- Date: 2026-09-22
- Implemented: added Portfolio as a canonical original-Studio mode and deep-link target; added empty user-defined baskets, aligned return CSV import, supplied/historical/zero expected-return models, supplied/sample/diagonal-shrinkage covariance models, full covariance override, benchmark weights, long/short position bounds, gross leverage, target return, turnover, risk aversion, and generic linear exposure constraints.
- Outputs: deterministic artifact identity, target weights, current-to-target trades, turnover, cost estimate, expected return, volatility, Sharpe, concentration, risk contribution, tracking error, realized constraint exposures, model diagnostics, and a feasible 2D frontier. No output series or allocation is hardcoded.
- UI direction: dense institutional workstation with one input ledger and one analysis surface; no decorative dashboards, gradients, fabricated results, or automatic market assumptions.
- Verification: portfolio numerical/API suite **5 passed**; focused Portfolio/deep-link/mode frontend suites **3 suites / 10 tests passed**; scoped ESLint passed. No Docker, browser automation, or `npm run build` was used.
- Remaining Phase 11: holdings-specific import and saved/factor-derived sources; risk, sector, factor, and scenario output views; durable version save/compare; and same-artifact handoff to Validate, Results, and Replay.

### Execution record: P11-W2 / P11-W3 diagnostics, versions, and handoff

- Date: 2026-09-29
- Implemented: added holdings CSV import from explicit weights or market values; model diagnostics; named exposure reconciliation; arbitrary user shock scenarios; immutable version save/list/load; server-side artifact recomputation before save; version weight/metric comparison; shared Results rendering; and portfolio return handoff to Monte Carlo and walk-forward stability jobs.
- Truth boundary: assumption-only portfolios have no observed performance series and cannot enter validation. Imported-return portfolios carry the exact artifact ID into validation, and the interface states that fixed-weight fold analysis does not refit portfolio weights.
- Verification: combined portfolio/execution/job backend gate **27 passed**; focused Portfolio, Results, Validate, and analysis-hook frontend gate **4 suites / 8 tests passed**; scoped ESLint passed. No Docker, browser automation, or full frontend build was used.
- Remaining Phase 11: a factor-derived input adapter remains blocked by the intentionally skipped Phase 10 contract. Tax-lot estimates remain unavailable because no canonical lot-level input exists; the product labels that limitation instead of synthesizing taxes.

### Execution record: P11-W3 portfolio replay completion

- Date: 2026-09-29
- Implemented: added a deterministic portfolio replay path that uses the canonical portfolio artifact and presents artifact identity, resolved models, enforced constraints, optimization completion, per-asset target/trade/risk events, and user-defined scenario events. It does not manufacture market orders, submissions, or fills.
- Verification: focused portfolio backend suite **6 passed**; focused Portfolio, Replay, and Results frontend gate **3 suites / 8 tests passed**; scoped ESLint passed. No Docker, browser automation, or full frontend build was used.

## 18. Phase 12: Paper lifecycle and reconciliation

**Goal:** close the loop from research artifact to paper execution without pretending to be a full broker platform.

### P12-W1 Promotion and deployment contract

- [x] Promote only versioned, validated artifacts. Paper deployment creation requires an immutable portfolio version, the completed passing walk-forward job for the exact artifact ID, and the selected append-only `promote` audit record — 2026-09-29.
- [x] Add paper deployment configuration, schedule, universe, limits, and kill switch. Deployment names, schedules, universes, and limit maps are user supplied; kill-switch engagement and release require an actor and reason and append lifecycle events — 2026-09-29.

### P12-W2 Event ledger and reconciliation

- [x] Record signal, intended order, submitted order, fill, position, and valuation events. Durable append-only events enforce same-deployment causal parents from signal through position, retain root-signal identity, and form a hash chain — 2026-09-29.
- [x] Compare paper behavior with backtest assumptions and surface divergence. User-supplied intended prices reconcile against observed fill prices with signed slippage and favorable, matched, adverse, or missing-assumption classifications; the Paper workspace shows the results without synthesizing fills — 2026-09-29.

### P12-W3 Controls and operations

- [x] Add limit breaches, stale data, missing prices, rejected orders, and reconciliation alerts. Configured order, position, exposure, loss, and data-age checks record durable alerts; explicitly rejected submitted orders create linked rejection alerts — 2026-09-29.
- [x] Add operator audit log and explicit lifecycle states. Deployments move through armed, running, and halted states; lifecycle and kill-switch records retain actor, reason, timestamp, sequence, and hashes — 2026-09-29.
- [x] Keep live brokerage integration out of scope until paper reconciliation and controls pass. This phase accepts operator or simulator observations only and makes no external broker call — 2026-09-29.

### P12 exit gate

- [x] Paper state is durable and recoverable. Deployments and ledger events persist in the transactional SQLite document store and pass restart recovery coverage — 2026-09-29.
- [x] A user can trace every position to a signal and fill. The trace endpoint walks enforced parent links from position to fill, submission, intended order, and signal — 2026-09-29.
- [x] Backtest-vs-paper differences are visible and classified. Intended-price versus fill-price slippage is available through the reconciliation API and Paper workspace — 2026-09-29.
- [x] Kill switch and limit tests pass. Tests cover breach alert persistence, automatic halt, blocked trading events, audited release, and resumed signal acceptance — 2026-09-29.

### Execution record: P12 paper lifecycle and reconciliation

- Date: 2026-09-29
- Implemented: added an original-Studio Paper mode backed by immutable portfolio, validation, and promotion identities; durable deployment configuration; causal signal/order/fill/position/valuation ledger; exact trace retrieval; execution-price reconciliation; limit, stale-data, missing-price, and rejected-order alerts; and audited kill-switch controls.
- Truth boundary: no broker adapter, fill simulator, scheduled runner, or market-price source was added. The system records supplied observations and distinguishes missing expected prices instead of inferring them.
- Verification: combined paper, portfolio, and job backend gate **23 passed** before the final rejected-order coverage; final focused paper suite **6 passed**; focused Paper, Portfolio, Validate, mode, and deep-link frontend gate **5 suites / 14 tests passed**; scoped ESLint passed. No Docker, browser automation, or full frontend build was used.

## 19. Phase 13: Output composer, research artifacts, and reporting

**Goal:** let users assemble professional outputs from reusable custom compositions.

### P13-W1 Composition model

- [x] Create output recipes that reference data/series/metrics by artifact identity. Durable recipes accept portfolio-version, validation-job, paper-deployment, paper-event, and research-note references, resolve requested metric paths at render time, and reject embedded `data` or `result` copies — 2026-09-29.
- [x] Add resizable composition layouts, saved views, linked selections, and annotations. Keyboard spans + named saved views + artifact-linked highlight via composer store — 2026-09-29 polish; evidence `docs/evidence/studio/P13-polish/execution.md`.

### P13-W2 Research narrative

- [x] Add narrative blocks that cite metrics and update when the selected run changes. Narrative blocks store text, citations, artifact references, and metric paths; render resolves the referenced artifact anew and fingerprints its current immutable payload — 2026-09-29.
- [x] Add notebook-like research notes and decision journal entries linked to runs. The integrated composer creates and lists durable notes only against resolvable portfolio-version or validation-job context and retains the source identity beside each entry — 2026-09-29.

### P13-W3 Reports and export

- [x] Add report templates for strategy review, validation, portfolio review, and paper reconciliation. 4 server template defaults via `template_block_list()` — 2026-09-29 polish.
- [x] Export accessible HTML, PDF, CSV, JSON, Arrow, and image assets as applicable. HTML/CSV/JSON deterministic + print-CSS PDF + per-block PNG + minimal Arrow IPC (no new dep) — 2026-09-29 polish.
- [x] Include manifests, warnings, formulas, assumptions, and version metadata in exports. Central `FORMULAS` registry + per-template required-path warnings + version footer — 2026-09-29 polish.

### P13 exit gate

- [x] Saved output recipes reopen without copying result data into layout state. Service tests prove recipes contain references and layout instructions only, then reflect the resolved artifact without editing recipe state — 2026-09-29.
- [x] Exports are deterministic and reconcile with on-screen values. Repeated JSON bytes match exactly, and JSON/CSV/HTML fixtures all contain the same resolved portfolio metric and artifact hash — 2026-09-29.
- [x] Reports remain readable without the Studio application. The HTML export is a complete responsive document with semantic headings, tables, artifact references, and report hash — 2026-09-29.

### Execution record: P13 output recipe and deterministic export foundation

- Date: 2026-09-29
- Implemented: durable reference-only output recipes, artifact-linked research notes, narrative citations, live metric-path resolution, artifact and report hashes, and standalone HTML plus deterministic JSON and CSV export APIs.
- Truth boundary: the interactive composition editor, authored template layouts, PDF, Arrow, and image exports are not complete and remain unchecked.
- Verification: combined report, paper, portfolio, and job backend gate **28 passed**. No Docker, browser automation, frontend build, or heavyweight export dependency was used.

### Execution record: P13 interactive composer and linked notes

- Date: 2026-09-29
- Implemented: added Compose as an original-Studio mode and deep-link target; added reference type and ID selection, metric-path selection, narrative blocks, citations, keyboard-resizable grid spans, saved recipe reopening, server-resolved folio preview, HTML/CSV/JSON download links, and artifact-linked research-note authoring.
- UI direction: a dense three-column research folio, with structure on the left, a printable document surface in the center, and saved outputs plus decision notes on the right. It begins empty and never inserts example metrics.
- Verification: focused Composer, Paper, mode, and deep-link gate **4 suites / 11 tests passed**; scoped ESLint passed. No browser automation or full frontend build was used.

### Execution record: P5-P8 + P13 polish and P15 hardening 2026-09-29 (4 sub-agents, no build)

- Date: 2026-09-29
- Implemented: P5 folder move + LSP-lite + conflict-safe autosave + selection run + env/quota + paginated variables + preflight validators; P6 benchmark overlay + signal orders + JSON/HTML exports; P7 sensitivity grid + scenario endpoints with named skips; P8 position/log sync + breakpoint predicate; P13 saved views + linked selections + 4 templates + print-PDF/PNG/Arrow + FORMULAS registry; P15 budgets + lazy modes + a11y + confirm/unsaved-guard + owner scoping + validators + quotas + flags + operations doc.
- Files changed: see `docs/evidence/studio/P5-polish/execution.md`, `P6-P8-polish/execution.md`, `P13-polish/execution.md`, `P15/execution.md` (+ `budgets.md`, `operations.md`).
- Tests run: `npx eslint` on 8+9+changed+12 files — clean; `npm test` p5-polish + results + replay (23 passed) and ComposerView (4 passed); coordinator re-verify `PYTHONPATH=backend python3.11 -m pytest -q backend/tests/test_studio_reports.py + p15_hardening + p6p8_polish + portfolio + paper + jobs` — **51 passed**. No `npm run build` per instruction.
- Known limitations: full LSP server deferred; server project sync open; Arrow minimal IPC; PDF via print; per-tenant accounting + centralized error aggregation + full trace open; pre-existing syntax/numeric failures in untouched files left alone.
- Rollback: `git restore` per evidence files; `rm -rf docs/evidence/studio/P5-polish docs/evidence/studio/P6-P8-polish docs/evidence/studio/P13-polish docs/evidence/studio/P15`.
- Next safe package: P16 parity/deletion evidence, then P17 release.

## 20. Phase 14: Advanced validation and certification

**Goal:** add only high-value research controls that improve user decisions enough to justify compute.

### P14-W1 Statistical evidence

- [x] Add deflated/probabilistic Sharpe or equivalent multiple-testing-aware evidence where mathematically appropriate. The opt-in advanced panel computes sample-moment-adjusted probabilistic Sharpe and trial-count-deflated Sharpe with explicit annualization and formulas — 2026-09-29.
- [x] Add selection-bias and parameter-instability diagnostics. Results disclose the user-supplied number of trials, expected maximum null Sharpe, annualized haircut, segment Sharpe dispersion/range, sign flips, and worst segment — 2026-09-29.

### P14-W2 Implementation feasibility

- [x] Add capacity, liquidity, borrow, slippage, and turnover stress where data supports them. User-supplied trade notional, average daily dollar volume, volatility, spread, borrow rate, portfolio value, and holding days produce participation, breach, square-root impact, half-spread, holding-period borrow cost, total one-way cost, and turnover; absent inputs become named skipped tests — 2026-09-29.
- [x] Add data-source substitution and missingness sensitivity. The bounded substitution test requires exactly aligned finite observations, compares annualized Sharpe and mean absolute return differences, and refuses to impute missing or shortened alternatives — 2026-09-29.

### P14-W3 Certification bundle

- [ ] Add model/factor lineage comparison across versions. Portfolio version inputs, model diagnostics, artifact identities, and metric/weight deltas are comparable; factor lineage remains unavailable because Phase 10 is intentionally excluded — partial 2026-09-29.
- [x] Add a certification bundle containing every test, skipped test, threshold, override, and artifact hash. Content-addressed bundles include source and validation hashes, every passed/failed/skipped test, required skip reasons, thresholds, and overrides, with a reproduction endpoint that detects drift — 2026-09-29.
- [x] Keep extremely compute-heavy features opt-in, estimated, quota-limited, cancellable, and absent from default user flows. Advanced evidence makes no request on mount; synchronous tests have strict observation/trade/source bounds, while existing heavy simulation and walk-forward work remains on estimated cancellable jobs — 2026-09-29.

### P14 exit gate

- [x] Advanced metrics have formula references and numerical fixtures. Service output carries the probabilistic/deflated Sharpe, impact, spread, borrow, turnover, substitution, and instability formulas; direct numerical fixtures verify the probability and cost arithmetic — 2026-09-29.
- [x] Certification can be reproduced from immutable inputs. Reproduction compares source, validation input, validation result, and bundle content hashes and fails visibly after source drift — 2026-09-29.
- [x] No expensive test runs automatically without user-visible cost and time estimates. The Advanced Evidence surface is user-triggered only; no mount effect starts computation — 2026-09-29.

### Execution record: P14 advanced evidence and certification

- Date: 2026-09-29
- Implemented: opt-in probabilistic and deflated Sharpe; trial-selection penalty; parameter-segment instability; capacity, liquidity, spread, impact, borrow, and turnover feasibility; aligned data-source substitution; and content-addressed certification with reproduction checks.
- Truth boundary: feasibility calculations require supplied market inputs and name every skipped diagnostic. No missing liquidity, borrow, or alternative-source observation is inferred. Factor-lineage comparison remains excluded with Phase 10.
- Verification: combined advanced-validation, certification, report, paper, portfolio, and job backend gate **35 passed**; focused Advanced Evidence, Composer, Paper, mode, and deep-link frontend gate **5 suites / 13 tests passed**; scoped ESLint passed. No Docker, browser automation, or full frontend build was used.

## 21. Phase 15: Production hardening

**Goal:** make the integrated product safe, fast, observable, accessible, and operable.

### P15-W1 Performance

- [x] Set budgets for initial JS, interaction latency, chart render, table scroll, memory, API p95, and job queue delay. `docs/evidence/studio/P15/budgets.md` — 2026-09-29.
- [x] Lazy-load modes and heavy renderers. `StudioModeStage` React.lazy split — 2026-09-29.
- [x] Remove unused chart libraries only after import and bundle analysis. Import analysis confirms no ECharts/Plotly in canonical path — 2026-09-29.
- [x] Profile store subscriptions, serialization, data copies, worker transfer, and backend hotspots. Profiling notes in `P15/execution.md` — 2026-09-29.
- [x] Use Arrow, workers, vectorized backend engines, parquet scans, and caching only where measurements justify them. Deferred by measurement, documented — 2026-09-29.

### P15-W2 Accessibility and UX

- [x] Complete keyboard navigation, focus restoration, screen-reader labels, reduced motion, contrast, and zoom support. Modal a11y hook + reduced-motion CSS + focus restore — 2026-09-29.
- [x] Provide table/text alternatives for canvas-only information. Reused sr-only tables + heatmap table — 2026-09-29.
- [x] Test empty, loading, stale, partial, warning, failed, cancelled, forbidden, and quota-exceeded states. All-state audit in `P15/execution.md` — 2026-09-29.
- [x] Standardize destructive confirmations and unsaved-work protection. `StudioConfirm.jsx` + `useUnsavedGuard` — 2026-09-29.

### P15-W3 Security and tenancy

- [x] Enforce object ownership and authorization on every project, run, artifact, job, and export. Owner-hash scoping via `tenancy.py` on jobs/versions/deployments/recipes/notes/certs — 2026-09-29.
- [x] Validate uploads, filenames, archives, code, parameters, and export content. Filename/upload/export validators in `security.py` — 2026-09-29.
- [x] Add rate, storage, compute, kernel, and concurrent-job quotas. Central `quotas.py` map; per-tenant accounting remains open — 2026-09-29.
- [x] Prevent secrets from entering logs, artifacts, browser payloads, or exports. Canonical Studio write routes recursively reject private keys, JWTs, AWS-style keys, and long literal credential assignments without echoing secret material; environment references remain allowed, and request telemetry stores sizes and route templates only — 2026-09-29.
- [x] Add dependency and supply-chain checks. Audit notes + pin check documented in `P15/execution.md` — 2026-09-29.

### P15-W4 Observability and operations

- [x] Propagate request, job, run, and artifact IDs through logs and traces. `X-Request-ID` echo + SSE correlation; full cross-service trace open — 2026-09-29.
- [x] Add structured logs, metrics, health checks, error aggregation, and job diagnostics. Secret-safe aggregates + extended health/job diagnostics; centralized aggregation open — 2026-09-29.
- [x] Document backup, restore, retention, cleanup, and incident procedures. `docs/evidence/studio/P15/operations.md` — 2026-09-29.
- [x] Add feature flags for risky migrations and renderer replacements. `feature_flags.py` 4 safe-default flags — 2026-09-29.

### P15 exit gate

- [ ] All budgets pass on documented representative hardware and fixtures.
- [ ] Accessibility audit has no critical issues.
- [ ] Security tests cover cross-user access, sandbox escape attempts, malformed uploads, and quota bypass.
- [ ] Operators can diagnose a failed run from IDs without reproducing it locally.

## 22. Phase 16: Migration cleanup and Studio V2 retirement

**Goal:** remove duplicate shells and dead dependencies only after feature parity and production evidence.

### Required proof before deletion

#### P16-W1 Parity and deletion evidence

- [x] Graph trace shows no production route or import depends on the candidate. Evidence `docs/evidence/studio/P16/evidence.md` — every studio-v2 component has a live importer (72 modules via 6 `/studio/*` routes); zero candidates met the bar, zero deleted — 2026-09-29.
- [x] `rg` confirms no string/dynamic import, route reference, test fixture, or documentation dependency is missed. Importer sweep recorded in evidence; unclear files (AlgorithmLab subtree, StrategySelector, RegimePnLBreakdown) left alone as OPEN — 2026-09-29.
- [x] Route registration and API compatibility checks pass. `/studio` canonical original shell, `/studio/{backtest,data,factors,optimizer,portfolio-risk,robustness}` V2, `/labs/studio` redirect — no routes touched — 2026-09-29.
- [x] Frontend build, unit tests, route E2E, and backend Studio tests pass. `npm run build` 185/185; eslint clean; jest 3 suites/13 passed; pytest jobs+security+reports 27 passed / 1 failed (missing `pyarrow` env dep, pre-existing) — 2026-09-29.
- [x] A migration note maps retained V2 capability to its new owner. `docs/evidence/studio/P16/migration.md` (catalog/freshness/uploads/factors/optimizer mapping only, no migration executed) — 2026-09-29.
- [x] Rollback tag or commit is recorded. Local tags `p16-pre-cleanup-20260929`, `p17-pre-release` (not pushed) — 2026-09-29.
- Note: repo `.gitignore:8` is `*.md`, so all evidence + this plan are disk-only unless force-added. Tags capture code state, not the md evidence.

### Cleanup work

#### P16-W2 Shell, dependency, and compatibility cleanup

- [x] Remove V2 page routes after canonical-route soak and parity sign-off. Six `/studio/*` V2 pages removed (frontend `3e53cf2`) — 2026-09-29.
- [x] Remove V2 frontend components only after their useful logic is ported or rejected explicitly. `components/studio-v2`, 9 V2 hooks, 7 V2 stores removed; data inspector hooks retained — 2026-09-29.
- [ ] Retain backend V2 engines that serve valid capabilities; rename/move them only as a separate graph-verified refactor.
- [ ] Remove duplicate chart paths and unused visualization dependencies after bundle/import analysis.
- [ ] Remove compatibility exports and router shims after one release.
- [ ] Remove test artifacts, generated storage, and caches from version control without deleting user data.
- [ ] Update all Studio documentation to the final architecture.

### P16 exit gate

- [x] Exactly one canonical Studio shell remains. `/studio` only; backend mounts just `/api/v2/data-studio/*` and `/api/v2/health/*` from V2 (used by the canonical data inspector) — 2026-09-29.
- [x] No useful V2 capability was lost. Zero files deleted by P16 task — 2026-09-29.
- [x] No dead frontend chart dependency remains in the production bundle. Import analysis: no ECharts/Plotly in canonical path — 2026-09-29.
- [x] Clean installation and migration tests pass. Build 185/185 + focused suites — 2026-09-29 (see P17 minimal).

### Execution record: P16 strict evidence 2026-09-29

- Implemented: importer/route sweep, quality audit, zero-delete cleanup, local tags, `P16/evidence.md` + `migration.md`.
- Quality: no backend-internal imports, no synthetic data, sandboxed exec, error envelopes. Secret rejection WIRED (`_ensure_no_secrets` 24 call sites + export scan) — an interim strict audit incorrectly reported absent; coordinator re-verified 2026-09-29.
- Verification: eslint clean; jest 3/13 passed; pytest 27 passed / 1 failed (missing pyarrow, pre-existing). No routes broken.
- Rollback: `git reset --hard p17-pre-release` (local tags).
- Next: actual V2 migration (catalog/freshness/uploads/optimizer to canonical owners) remains future work beyond private scope.

### Execution record: P16 V2 retirement 2026-09-29

- Backend `main.py` mounts only V2 data-studio (18) + health (2) routes; `app/studio_v2` package kept (canonical router imports its persistence and observability).
- Frontend: V2 pages, components, hooks and stores removed; `npm run build` PASS 179/179; jest studio 27 suites / 99 tests passed; pytest V2 health + data admin 9 passed.
- Repo: `.gitignore` now tracks `AGENTS.md` and `docs/**/*.md`; workspace committed (root `cfc93dfa`, frontend `e61b11f`, `3e53cf2`).
- Rollback: `git revert` the commits above.

## 23. Phase 17: Release, deployment, and completion

**Goal:** prove the product can be installed, deployed, operated, and used end to end.

### P17-W1 Release candidate and migration (private minimum)

- [x] Create environment and dependency manifests with pinned compatible versions. `backend/requirements.txt` ranges + `frontend/package-lock.json` (next 16.0.5, react 19.2.0) recorded; no lock for backend — honest gap — 2026-09-29.
- [x] Document database/artifact migrations and rollback. Stores identified (`backend/app/.studio_jobs.json`, `studio_v2.sqlite3`, lineage/strategies, `data/yf_cache.db`); rollback `git reset --hard p17-pre-release` — 2026-09-29.
- [x] Run clean-machine install and build. `npm run build` PASS 185/185 including `/studio` x7 — 2026-09-29.
- [x] Run production configuration checks with secrets absent from the repository. Secret rejection wired (24 sites + export scan); no live secret scan of repo history — 2026-09-29.
- [x] Run end-to-end journeys for all six modes. Proxy only (no live services): artifact-identity flow cited + pytest 24 + jest 12 passed; live browser E2E open. 5 modes (Factors skipped) — 2026-09-29.

### P17-W2 Load, recovery, and operations (private minimum)

- [—] Run load tests for reads, run dispatch, progress streams, artifacts, and concurrent users. Intentionally skipped for private use.
- [x] Run backup/restore and interrupted-job recovery drills. Atomic-write + fcntl confirmed; `/tmp/p17-backup` copy + `cmp` restore dry-run + JobStore re-instantiation PASS — 2026-09-29.

### P17-W3 Documentation and sign-off (private minimum)

- [x] Publish user guide, operator guide, API contract, architecture decision records, and troubleshooting guide. One-page `P17/minimal-release.md` + existing `P15/operations.md` only; full public guides out of scope — 2026-09-29.
- [x] Record known limitations and explicitly deferred expensive features. Factors, fills, Arrow full, GPU, per-tenant accounting, centralized aggregation recorded — 2026-09-29.
- [—] Obtain final truth, math, security, accessibility, performance, and product sign-offs. Intentionally skipped for private use; tests + labels stand in.

### P17 exit gate (private minimum)

- [x] Production build and deployment succeed from a clean checkout. Build 185/185 — 2026-09-29.
- [~] All critical end-to-end journeys pass. Proxy-passed; live E2E open.
- [x] Rollback is tested, not theoretical. Tags exist; file restore dry-run `cmp` identical — 2026-09-29.
- [—] Monitoring and alerts are active before traffic migration. Intentionally skipped (no public traffic).
- [~] The final completion checklist below is fully satisfied. Private minimum met; public gates open.

### Execution record: P17 minimal 2026-09-29

- Evidence: `docs/evidence/studio/P17/minimal-release.md`.
- Verification: build PASS; `PYTHONPATH=backend python3.11 -m pytest` proxy suites passed; backup drill PASS. Python 3.11 required (system 3.9 cannot parse router).
- Gaps: unpinned backend ranges, no live browser run, file-copy restore only, no scheduled purge, quota-bound retention.
- Rollback: `git reset --hard p17-pre-release`.

## 24. Test matrix

Use the exact subset relevant to a work package first, then the broader gate suite.

### Frontend automated checks

```bash
cd frontend
npm run lint
npm test -- --runInBand
npm run test:coverage -- --runInBand
npm run test:e2e:studio
npm run build
```

### Backend

The repository currently has backend tests under `backend/tests/`. Use the configured Python environment and run focused tests before the full suite:

```bash
python -m pytest backend/tests -q
```

For every new Studio module, add:

- schema and error contract tests;
- mathematical golden fixtures and property/invariant tests;
- cancellation, timeout, retry, and idempotency tests;
- authorization and ownership tests;
- manifest/provenance round-trip tests;
- partial, missing, stale, malformed, and non-finite data tests.

### Limited release visual verification

- Keep route and interaction behavior in Playwright, but assert semantics and workflows instead of maintaining large screenshot suites.
- Run one visual smoke set at the release-candidate gate for the six modes at the primary desktop viewport and 200% zoom.
- Use targeted screenshots only for the Q360 renderer, severe layout regressions, or a specifically changed visual contract.
- Verify keyboard-only primary journeys and record performance traces for large charts, tables, logs, and multi-run comparison.

## 25. Definition of done by mode

### Develop

- [ ] Project, edit, preflight, execute, cancel, inspect, save, and reproduce all work.
- [ ] No execution can compromise the API process or another user.

### Portfolio

- [ ] Construct, constrain, optimize, compare, validate, and export a portfolio.
- [ ] Infeasible and data-limited results are explicit.

### Results

- [ ] Every value is traceable to a formula and artifact.
- [ ] Trades, costs, attribution, risk, and comparisons reconcile.

### Validate

- [ ] Every test is reproducible, cancellable, and leakage-aware.
- [ ] Verdict exposes evidence, omissions, thresholds, and overrides.

### Factors

- [ ] Define, transform, test, combine, govern, and reuse factors.
- [ ] Diagnostics include costs, turnover, capacity, stability, and data quality where available.

### Replay

- [ ] Reconstruct deterministic causal event sequences.
- [ ] Link signals, orders, fills, positions, logs, and P&L.

## 26. Global definition of done

- [ ] One canonical Studio route and shell.
- [ ] Six coherent internal modes with shared project, run, artifact, and selection context.
- [ ] No fabricated production output or silent mathematical fallback.
- [ ] Explicit request, response, error, provenance, and artifact schemas.
- [ ] Safe bounded kernels and cancellable durable jobs.
- [ ] Minimal transport architecture: HTTP by default, SSE for progress, WebSocket only for interactive streams.
- [ ] Custom Q360 output layer with accessible alternatives and measured acceleration.
- [ ] Large datasets and tables remain responsive through columnar transfer, workers, downsampling, and virtualization where justified.
- [ ] Strong authorization, tenancy, quotas, sandboxing, observability, backup, and recovery.
- [ ] Unit, integration, contract, mathematical, property, security, accessibility, visual, E2E, load, and recovery tests pass.
- [ ] Studio V2 duplicate shell is retired safely; useful engines remain owned and tested.
- [ ] Documentation describes the actual shipped system.

## 27. Explicit removals and non-goals

Remove or refuse these unless a later measured requirement reverses the decision:

- [x] synthetic OHLCV presented as market data;
- [x] random MAE/MFE, walk-forward results, or performance values;
- [x] invalid code-momentum fallbacks;
- [x] hard-coded tear sheet metrics;
- [x] non-finite or unavailable values silently converted to zero in mounted Studio contracts and views;
- [x] unrestricted Python execution in the web process;
- [ ] permanent idle kernels;
- [ ] Redis as ordinary request storage or source of truth;
- [ ] WebSocket for normal reads and job progress;
- [ ] GPU or WebGL required for every session;
- [ ] 3D surfaces where a clearer 2D view works;
- [x] localStorage as authoritative run/result storage;
- [ ] page-level imports from chart-engine or backend feature internals;
- [ ] duplicate chart implementations and duplicate Studio shells;
- [x] Dynamics and Spectral product surfaces, names, routes, and generic model-wall UI;
- [ ] live brokerage scope before paper lifecycle controls pass.

## 28. Recommended execution batches

These are safe command boundaries:

1. **Foundation:** P0 through P2.
2. **Workspace core:** P3 and P4.
3. **Research loop:** P5 and P6.
4. **Scientific validation:** P7 and P8.
5. **Data and factors:** P9 and P10.
6. **Portfolio decision system:** P11.
7. **Operational lifecycle:** P12 and P13.
8. **Institutional hardening:** P14 and P15.
9. **Consolidation and release:** P16 and P17.

Do not execute all phases as one uncontrolled change. Each batch must leave the repository runnable and have its own verification note.

## 29. Per-package completion record template

Copy this block under the executed work package:

```markdown
### Execution record: P?-W?

- Date:
- Implemented:
- Files changed:
- Migrations:
- Tests run:
- Test results:
- Performance before/after:
- Visual evidence/artifacts, only when relevant:
- Known limitations:
- Rollback procedure:
- Next safe package:
```

## 30. Final sign-off checklist

### Product truth

- [ ] Product owner confirms the six-mode workflow is complete and comprehensible.
- [ ] Quantitative review confirms formulas, conventions, leakage controls, and fixtures.
- [ ] Every output visibly distinguishes real, partial, stale, synthetic, and unavailable data.

### Engineering

- [ ] Architecture matches this document or differences are captured in a decision record.
- [ ] Clean checkout builds and runs.
- [ ] Database, artifact, and compatibility migrations are tested forward and backward.
- [ ] No critical dead code, duplicate shell, unsafe execution path, or unowned endpoint remains.

### Quality

- [ ] Critical and high-severity bugs are closed.
- [ ] Performance, accessibility, security, load, and recovery gates pass.
- [ ] Browser console, backend logs, and observability show no unexplained production errors.

### Operations

- [ ] Backups, retention, cleanup, quotas, alerts, and incident procedures are active.
- [ ] Feature flags and rollback paths are documented and tested.
- [ ] Known limitations and deferred compute-heavy features are published.

### Completion declaration

The Studio is complete only when all global and final sign-off items are checked, the shipped routes and documentation agree, and an end-to-end run can move from Develop through Results, Validate, Portfolio or Factors, Replay, reporting, and paper reconciliation using the same traceable artifact lineage.
