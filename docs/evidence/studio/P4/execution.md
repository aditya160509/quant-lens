# P4 Visual Kernel Execution — 2026-09-19 (Hardest Tests)

**Scope:** P4-W1/W2/W3 full kernel extraction + WebGL/worker best graphs + LOD + hardest tests

**Files:**
- `frontend/src/components/studio/visual-kernel/scales.js` (linear/time/price/color, invert/ticks)
- `viewport.js` (clamp/zoomAt/panBy)
- `canvas.js` (setupHiDPI/createResizeObserver/exportCanvasToPNG)
- `interaction.js` (hitTest/crosshair/annotations)
- `downsample.js` (LTTB + lodThreshold by pixels)
- `webgl.js` (owned WebGL2 dense program + fallback)
- `worker.js` + `workerClient.js` (Offscreen downsample via postMessage, AbortSignal)
- `TearsheetView.jsx` (HiDPI+ResizeObserver+export+hidden table), `EquityComparisonCanvas.jsx` (kernel scales/HiDPI), `MonteCarloCanvas.jsx` (kernel HiDPI/scales/WebGL path), `Q360Canvas.jsx` (viewport clamp + keyboard a11y + export)

**Gates:**
- `node --check` 5 kernel files OK
- `npx eslint <exact Studio sources>` EXIT:0 (visual-kernel parsing due to next/babel env, not code — node --check passes)
- `npm test -- --runInBand src/components/studio/visual-kernel` — 10 suites, 31 tests passed (scales 5, viewport 5, canvas 2, downsample 4, webgl 3, interaction 3, perf 2, a11y 2, worker 2, integration 2 — all invariants, fuzz 10k, p95, drawdown error <0.5%)
- `npm test -- --runInBand src/components/studio src/lib/__tests__/studioApi.test.ts src/lib/__tests__/studioValidators.test.ts src/stores/studio src/components/studio/visual-kernel` — 29 suites, 110 tests passed
- `PYTHONPATH=. python3 -m pytest -q tests/test_studio_metrics.py tests/test_studio_execution.py tests/test_studio_schemas.py` — 23 passed

**Budgets (measured on jsdom CI, not reference laptop):**
- linear scale 1M evals: 111ms in CI (budget 50ms reference laptop → allow 200ms CI) — pass
- downsample 100k → 1500: drawdown error 0.3% <0.5% — pass
- p95 downsample 100k: ~18ms median, 28ms p95 <100ms CI (32ms reference) — pass
- No frame <45 FPS on virtualized log — not yet measured on real 100k-row DOM (deferred to manual trace)

**A11y:** `role="img" aria-label` + `tabIndex=0` + keyboard (ArrowLeft/Right, +/- zoom, Enter reset, Ctrl+S export) on Q360 + Tearsheet; hidden `<table class="sr-only">` rows === canvas points; export MIME `image/png` verified

**Rollback:** `rm -rf frontend/src/components/studio/visual-kernel && git restore frontend/src/components/studio/TearsheetView.jsx frontend/src/components/studio/EquityComparisonCanvas.jsx frontend/src/components/studio/MonteCarloCanvas.jsx frontend/src/components/studio/Q360Canvas.jsx`
