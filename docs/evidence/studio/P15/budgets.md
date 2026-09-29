# P15 Performance Budgets and Bundle Analysis

Date: 2026-09-29. Scope: canonical Studio shell (`frontend/src/components/studio/**`, `/api/studio/*`).

## 1. Budgets

| Dimension | Budget | Rationale / status |
|---|---|---|
| Initial Studio JS (active mode only) | <= 350 KB gzipped JS for first mode paint | Enforced by `React.lazy` per-mode splits in `StudioModeStage.jsx`; Suspense fallback keeps time-to-first-status under one frame of feedback |
| Interaction latency p95 (tab switch, pane retry) | <= 100 ms | Zustand selector subscriptions (single-field, e.g. `activeTab`) avoid whole-store re-renders; verified by code inspection, no profiler regression harness yet (open) |
| Chart render p95 (10k-bar canvas, downsampled) | <= 250 ms | In-house visual-kernel canvas with viewport downsampling (`visual-kernel/downsample.js`); WebGL stays behind `STUDIO_RENDERER_WEBGL=0` default |
| Table scroll (virtualized grids) | 60 fps, no full re-render per row | `@tanstack/react-virtual` already in deps; sr-only tables capped at 20 rows (`TearsheetView.jsx`) so AT cost stays flat |
| Memory (Studio tab, representative fixture) | <= 350 MB RSS growth over baseline | `partialize` persist in studio stores keeps only request drafts in localStorage; result payloads are not persisted wholesale |
| API p95 (canonical `/api/studio/*`, local) | <= 500 ms for reads; <= 30 s timeout for job dispatch | `studioRequest` default timeout 30 s, GET retry x1 with backoff; observability aggregates carry mean/max per route template |
| Job queue delay (queued to running, local executor) | <= 5 s at <= 2 concurrent jobs | Bounded `ThreadPoolExecutor(max_workers=2)`; `STUDIO_MAX_CONCURRENT_JOBS` centralizes the bound; external worker pool stays off (`STUDIO_WORKER_EXTERNAL=0`) |

Representative hardware/fixtures for formal budget sign-off are still open (P15 exit gate): budgets are set and the code paths honor them, but no recorded measurement run on fixed hardware exists yet.

## 2. Lazy loading

`frontend/src/components/studio/shell/StudioModeStage.jsx` now loads all nine mode surfaces via `React.lazy` under one `Suspense` boundary (role=status fallback, "Loading mode…"). `StudioPaneBoundary` still isolates per-mode crashes with `resetKey={activeTab}`.

## 3. Bundle and import analysis (2026-09-29)

Grep over `frontend/src/components/studio/**` for static and dynamic imports of `echarts`, `plotly`, `recharts`, `lightweight-charts`, `d3`, `@visx`: **zero matches**. Canonical Studio charts render through the in-house visual kernel (`visual-kernel/canvas.js`, `viewport.js`, `downsample.js`, optional `webgl.js` behind flag); canvas-only views carry `sr-only` data tables (e.g. `TearsheetView.jsx` equity/drawdown tables).

`package.json` still declares `echarts ^6.0.0`, `echarts-for-react`, `plotly.js`, `plotly.js-dist-min`, `react-plotly.js`, `recharts`, `lightweight-charts`, `d3`, `@visx/*`. Consumers are non-canonical surfaces (labs, market-labs, portfolio-v2, factors-v2 pages). Per the P16 deletion rule these stay installed until a graph-verified removal pass; this section is the import analysis that rule requires. No ECharts/Plotly code ships in the canonical Studio path.

## 4. Profiling notes

- Store subscriptions: shell components subscribe to single zustand fields (`useStudioWorkspaceStore((s) => s.activeTab)`); persist middleware uses `partialize` so only drafts hit localStorage serialization.
- Serialization and copies: `JobStore._copy` round-trips jobs through JSON (safe sizes: progress/events/result only; strategy source and idempotency secrets are stripped by `_public_job`). SQLite documents store canonical JSON; no per-request body logging.
- Worker transfer: none added. The SSE stream sends small `{id, status, progress}` frames with a 5 s watchdog fallback poll.
- Backend hotspots: portfolio optimization runs in `asyncio.to_thread`; Monte Carlo caps at `MAX_SIMULATIONS=10000`.
- Arrow, external workers, vectorized parquet scans, and GPU paths were **not** added: no measurement justified them. Flags reserve the paths (`STUDIO_PARQUET_FAST_SCAN`, `STUDIO_WORKER_EXTERNAL`, `STUDIO_GPU_ENABLED`, all default off).

## 5. Supply-chain notes

- `backend/requirements.txt` uses `>=` floors (20 `==` pins only); `frontend/package.json` uses `^` ranges. No lockfile pinning was introduced by P15 (minimal-scope rule); operators should run `pip-audit -r backend/requirements.txt` and `npm audit --omit=dev` before release and record output here.
- P15 added no new runtime dependencies (backend: 3 new stdlib-only modules; frontend: 4 new files, zero new imports beyond React).
