# P4-D Visual Kernel Readiness

**Status:** READY
**Date:** 2026-09-19
**Implementation owner:** Studio frontend owner
**Required reviewers:** frontend reviewer, quantitative reviewer, product approver
**Work package:** P4 Visual Kernel — reuse/rewrite/remove decision for Q360 + equity comparison + Monte Carlo + tearsheet canvases before any kernel extraction

## 1. Current behavior and authoritative source of truth

- `frontend/src/components/studio/Q360Canvas.jsx:1` (1057 lines) is the canonical Studio chart: Canvas2D with `devicePixelRatio` scaling, `ResizeObserver`, `effectiveOffset`/`effectiveScale` viewport, synced `syncedOffset/syncedScale/syncedHover`, `drawVolumeProfile`, `drawOverlay`, `drawPriceAxis`, `drawPatterns`, `drawCrosshair`, pattern scanning via `scanForPatterns`. Used by `DevelopView.jsx:25` (dynamic import) and `GridChartCell.jsx:4`.
- `frontend/src/components/studio/EquityComparisonCanvas.jsx:1` (375 lines) renders equity/ghost curves with ghost overlay metrics derived from `primaryMetrics.canonical`. Used by `DevelopView.jsx:8`.
- `frontend/src/components/studio/MonteCarloCanvas.jsx:1` (140 lines) renders `data.samplePaths` as density heatmap with median path and 5th/95th markers. Used by `StressView.jsx:6`.
- `frontend/src/components/studio/TearsheetView.jsx:39,123` contains two additional inline canvases: `EquityCurveChart` and `DrawdownChart` (each ~80 lines) with duplicated `dpr` + gradient fill + `scaleX`/`scaleY` logic.
- Truth remains: Canvas2D baseline is correct; no WebGL path is measured as needed. Numerical truth for equity/drawdown comes from `backend/app/services/studio/metrics.py:1` canonical metrics, not canvas.

## 2. Exact affected files, symbols, routes, endpoints, stores, schemas, imports

- Files: `Q360Canvas.jsx`, `EquityComparisonCanvas.jsx`, `MonteCarloCanvas.jsx`, `TearsheetView.jsx`, `GridChartCell.jsx`, `DevelopView.jsx`, `StressView.jsx`, `TearsheetView.jsx` canvas sections, `frontend/src/components/chart_engine/*` (indicator registry, pattern scanner) referenced by Q360Canvas.
- Symbols: `scaleY`, `scaleX`, `drawPriceAxis`, `drawVolumeProfile`, `drawCrosshair`, `handleResize`+`ResizeObserver`+`dpr`, `syncedOffset/syncedScale/syncedHover`, `effectiveOffset/effectiveScale`, `calculateCumulativeReturn`/`calculateMaxDrawdown` (EquityComparison), `allPoints→minV/maxV→scaleY` (MonteCarlo).
- Routes: `/studio` → `OriginalStudioPage` → `StudioLayout` → `ModeStage` → Develop/Stress/Tearsheet (all mount Q360/Equity/Monte Carlo canvases).
- Imports: Q360Canvas imports `getIndicator` and `scanForPatterns`; EquityComparisonCanvas imports none beyond React/lucide; MonteCarloCanvas none; Tearsheet charts inline no imports. No backend shape import in these canvases — they consume already-validated props (`isStudio*Response`).
- No backend endpoint change required for this decision.

## 3. Code-graph inbound/outbound impact and dynamic-reference checks

- `rg "Q360Canvas|EquityComparisonCanvas|MonteCarloCanvas"` shows 6 inbound references: `DevelopView:8,25`, `GridChartCell:4`, `StressView:6`, `TearsheetView` (inline). No dynamic `import()` beyond the `dynamic(()=>import('./Q360Canvas'))` in DevelopView; no string-based canvas resolution.
- Outbound from Q360Canvas: to `../chart_engine/IndicatorEngine/registry` and `../chart_engine/PatternScanner` — retained as-is; no backend import.
- Deletion check: removing any of the three canvases without replacement would break mounted `DevelopView`/`StressView`; extraction must keep same import paths or provide a compatibility alias for one release.

## 4. Preserved behavior and explicit non-goals

- Preserved: all visible chart behavior, synced viewports, crosshair, patterns, volume profile, equity ghosting, Monte Carlo density/median/percentile markers, tearsheet equity/drawdown gradients, responsive resize, `Number.isFinite` guards for metrics.
- Non-goals for this readiness: no new visual language, no gradient/branding redesign, no WebGL, no OffscreenCanvas worker, no Arrow payload migration, no TanStack Table introduction. Those belong to `P4-W1/W3` only after measurement.

## 5. Proposed files and dependencies

- `frontend/src/components/studio/visual-kernel/scales.js` — pure functions `linearScale(domain, range)`, `timeScale`, `priceScale` with `invert` and `ticks` helpers. Replaces 4 ad-hoc `scaleX/scaleY` closures (Q360Canvas:322,351; EquityComparison: ~scaleY; MonteCarlo:54; Tearsheet:64,153).
- `frontend/src/components/studio/visual-kernel/viewport.js` — viewport math `computeViewport(offset,scale,width)` + `clampViewport` reused by Q360Canvas and GridChartCell.
- `frontend/src/components/studio/visual-kernel/canvas.js` — `setupHiDPI(canvas, rect)` (dpr + `ctx.scale`) and `createResizeObserver(canvas, draw)` helper (deduplicates Q360Canvas:24, MonteCarlo:22, Tearsheet:48,131 patterns).
- No new dependency. No Redis, no WebGL, no `three`, no `comlink` until measured.

## 6. Migrations, backfill, compatibility window, feature flag, rollback command

- Migrations: none (no schema, no storage).
- Compatibility: keep `frontend/src/components/studio/Q360Canvas.jsx` as a re-export of `visual-kernel/Q360Canvas.jsx` for one release if moved; same for Equity/Monte Carlo aliases.
- Feature flag: none — extraction is refactor, behavior unchanged.
- Rollback: `git restore frontend/src/components/studio/Q360Canvas.jsx frontend/src/components/studio/EquityComparisonCanvas.jsx frontend/src/components/studio/MonteCarloCanvas.jsx frontend/src/components/studio/TearsheetView.jsx && rm -rf frontend/src/components/studio/visual-kernel`

## 7. Fixtures, numerical tolerances, performance budgets, tests, evidence to produce

- Fixtures: `frontend/e2e/fixtures/studio/q360-1k-candles.json` (already exists as real observed data), 100k-row table fixture for virtualized trade log, large-path fixture for Monte Carlo (10k paths × 252 steps).
- Tolerances: renderer geometry within 0.5px per `scaleY` round-trip; metric→canvas value error `<= 1e-10` for deterministic equity fixtures; no fabricated metrics in canvas.
- Budgets: chart interaction p95 <32 ms on 1M-point downsampled fixture; table scroll no sustained frame below 45 FPS on 100k rows; ordinary API p95 <500 ms (existing).
- Tests: deterministic renderer tests for `scales.js`/`viewport.js` (values, geometry, empty/missing/extreme, non-finite → unavailable), `StudioPaneBoundary` empty/loading, existing 79-frontend/23-backend gates must stay green. No new visual snapshot suite — keep small targeted contract tests.
- Evidence: `docs/evidence/studio/P4-D/execution.md` will record extraction diffs, test counts, and before/after frame traces on reference hardware.

## 8. Risks, unresolved decisions, estimated work-package boundary

- Risks: over-abstracting before two callers converge (Rule of Three) — mitigated by extracting only where `Q360Canvas` + at least one of EquityComparison/MonteCarlo/Tearsheet share logic (scales, HiDPI, resize). Pattern/indicator layers stay in Q360Canvas until P5/P7 demand them elsewhere.
- Unresolved: whether equity comparison needs synchronized viewport linking with Q360 (currently independent) — defer to P6 Results linked-performance decision; whether Monte Carlo density opacity/threshold needs a user control — defer to P7 scenario evidence.
- Effort: `P4-D` is 0.5 day (this doc). `P4-W1` extraction is ~2 days; `P4-W2` interaction primitives ~3 days; `P4-W3` Arrow/worker/table ~3 days with measurement. All require `P2 contracts` (already satisfied) and `P3` shell (now satisfied).
- Boundary: this D package does not edit production code, install deps, or delete files — readiness only.
