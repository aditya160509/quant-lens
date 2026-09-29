# P15 Execution Record (Production Hardening)

Date: 2026-09-29. Plan ref: `docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md` Phase 15 (P15-W1..W4). Main plan not updated, per instruction.

## W1 Performance

- `docs/evidence/studio/P15/budgets.md`: budgets set (initial JS <= 350 KB gzip per mode, interaction p95 <= 100 ms, chart p95 <= 250 ms, API read p95 <= 500 ms, queue delay <= 5 s, memory <= 350 MB growth). Formal measurement on fixed hardware remains open.
- `frontend/src/components/studio/shell/StudioModeStage.jsx`: all nine mode surfaces via `React.lazy` + `Suspense` status fallback; crash isolation via `StudioPaneBoundary` retained.
- Bundle analysis in `budgets.md` section 3: zero ECharts/Plotly/recharts/lightweight-charts/d3/visx imports in `frontend/src/components/studio/**` (canonical path uses the in-house visual kernel). Package-level heavies remain for non-canonical pages; removal deferred to P16 graph-verified cleanup.
- Profiling notes in `budgets.md` section 4 (selector subscriptions, JSON copy points, bounded executor). No Arrow/worker/GPU added; flags reserve the paths.

## W2 Accessibility and UX

- New `shell/useStudioModalA11y.js`: focus-in on open, focus restoration to opener, Escape close, Tab trap. Wired into `PreExecuteModal.jsx` (role=dialog, aria-modal, labelled title) and `LayoutManagerModal.jsx` (same; also fixed `close` declaration order above the hook).
- New `shell/studioA11y.css`: `prefers-reduced-motion` kill-switch, `:focus-visible` ring, imported by `StudioModeStage`.
- New `shell/StudioConfirm.jsx`: standardized destructive confirmation (`role=alertdialog`, labelled destructive action, Escape/cancel restores focus, native `confirm()` fallback only via `forceNative`).
- New `shell/useUnsavedGuard.js`: `beforeunload` while dirty; ready for Composer/Develop draft state (wiring to concrete dirty flags is open).
- Canvas alternatives: reuse confirmed, no new tables needed (`TearsheetView.jsx` sr-only equity/drawdown tables capped at 20 rows; lab tables carry sr-only captions).
- Contrast: shell chrome uses slate-400+ on near-black and amber accents; `studioA11y.css` adds a `.contrast-note` baseline. A formal contrast audit with measured ratios is open.
- All-state audit (Develop/Results/Validate/Replay/Composer): empty (preflight blocking errors, "no observed orders", empty panes), loading (Suspense fallback, SSE progress), stale (as-of age warnings), partial (`partial` job status surfaced as failure with message), warning (amber preflight box), failed (pane boundary + job error), cancelled (`STUDIO_CANCELLED` path), forbidden (new `403 STUDIO_FORBIDDEN`), quota-exceeded (429 quota codes + `resource_limit` log category). States exist across shell, API client, and preflight; a scripted screenshot/AT pass per mode is open.

## W3 Security and tenancy

- New `backend/app/services/studio/tenancy.py`: `owner_hash` (sha256, 32 hex, never echoes raw id), `owner_from_request` (`X-Owner-Id`), `require_owner_match` (legacy stamp-less records stay readable), plus `studio_owner_index` sidecar helpers for service-owned schemas.
- Enforced in `backend/app/routers/studio.py` on jobs (create stamps, get/cancel/promotion-audit check), portfolio versions (stamp + list filter + get/compare check), paper deployments and events (sidecar), recipes/notes/views/render (sidecar), certifications (sidecar + validation-job ownership on create). Cross-owner access returns `403 STUDIO_FORBIDDEN`.
- `services/studio/security.py` extended: `validate_filename` (traversal/separator/archive rejection), `validate_upload_meta` (size/type envelope), `assert_no_secret_material_in_export` (scans rendered bodies with existing patterns). Export route validates the download filename and scans content before responding.
- Quotas centralized in `services/studio/quotas.py`; `paper.py`, `reports.py`, `certification.py`, and the version-save route read through `get_quota`. Documented in `operations.md` section 3. Per-tenant accounting remains open (global counters only).
- Supply-chain: no new deps; pin/audit notes in `budgets.md` section 5 (`pip-audit`, `npm audit` operator commands; `>=`/`^` ranges recorded as-is).

## W4 Observability and operations

- `X-Request-ID` already flowed on fetch; P15 adds `?request_id=` correlation for `EventSource` streams (`studioApi.js`), echoed as the SSE `X-Request-ID` header by `job_events`, and falls back to the middleware contextvar when storing `request_id` on job create.
- Structured JSON logs with route templates already existed (`observability.py`); unchanged, documented in `operations.md`.
- `GET /api/studio/health` extended with job-by-status counts, per-namespace storage counts, quota snapshot, flag snapshot, and propagated `request_id`. No payloads, IDs, or secrets leave the endpoint.
- New `backend/app/services/studio/feature_flags.py` + mirrored `frontend/.../shell/studioFeatureFlags.js` (renderer/worker/GPU/parquet flags, all default off, visible in health).
- `docs/evidence/studio/P15/operations.md`: correlation, diagnostics, quotas, tenancy, flags, backup/restore/retention/cleanup, incident runbook.

## Files changed

Backend (new): `services/studio/tenancy.py`, `services/studio/quotas.py`, `services/studio/feature_flags.py`, `tests/test_studio_p15_hardening.py`.
Backend (edited): `routers/studio.py` (owner scoping, export guards, SSE correlation header, health diagnostics), `services/studio/security.py` (filename/upload/export validators), `services/studio/jobs.py` (`owner_hash` on create), `services/studio/paper.py`, `services/studio/reports.py`, `services/studio/certification.py` (central quota reads).
Frontend (new): `shell/studioA11y.css`, `shell/useStudioModalA11y.js`, `shell/useUnsavedGuard.js`, `shell/StudioConfirm.jsx`, `shell/studioFeatureFlags.js`, `shell/__tests__/StudioHardening.test.tsx`.
Frontend (edited): `shell/StudioModeStage.jsx` (lazy modes), `PreExecuteModal.jsx` + `LayoutManagerModal.jsx` (modal a11y), `lib/studioApi.js` (SSE request correlation), `lib/__tests__/studioApi.test.ts` (URL assertion), `components/studio/__tests__/StudioModeStage.test.tsx` (async lazy render).
Evidence (new): `docs/evidence/studio/P15/budgets.md`, `operations.md`, `execution.md` (this file).

## Test results

- `npx eslint` on all 12 changed/new frontend files: clean (exit 0).
- Frontend focused: 14 suites / 90 tests passed (shell, StudioModeStage, ShellControls, Composer, Portfolio, Paper, AdvancedValidation, hooks/studio, studioApi, studioValidators, studioReplay).
- Backend: `PYTHONPATH=backend python3.11 -m pytest -q backend/tests -k "studio or security or job"`: 262 passed, 10 failed. All 10 failures are pre-existing and untouched by P15 (details below). New `test_studio_p15_hardening.py`: 11 tests pass. Note: repo Python is 3.9 but the codebase uses 3.10+ union syntax, so verification used `/opt/homebrew/bin/python3.11`; `npm run build` was not executed per instruction.

## Gaps and pre-existing failures (not caused by P15)

1. `test_studio_v2_api_inventory` fails: committed inventory doc is stale vs working-tree data-studio routes (uploads list/delete, explorer `limit`). V2 router untouched by P15.
2. `test_studio_v2_frontend_traceability` (2 tests) fails: node extractor rejects unclassified `/api/v2` paths in `frontend/src/hooks/studio/useDataStudio.js:73,83`. File untouched by P15.
3. Futures roll edge cases (3), optimizer edges (3): numeric failures in untouched studio-v2 math (`Too many bins for data range`, `output array is read-only`: numpy-version behavior).
4. Monte-Carlo resampling `moving_block_bootstrap`: same numpy-behavior class, untouched engine.
5. Frontend `studioResults.js:200` has a pre-existing syntax error (`Expected ',', got '}'`) breaking 4 suites (ReplayView, TearsheetView, ValidateView.audit, studioResults). File untouched by P15; left alone as out-of-scope user work in progress.
6. P15 exit-gate items still open: measured budget run on fixed hardware, formal a11y/contrast audit, per-tenant quota accounting, centralized error aggregation, full cross-service trace correlation, Composer/Develop dirty-flag wiring for the unsaved guard.
