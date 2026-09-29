# P6-P8 Polish Execution — 2026-09-29

**Scope:** Phases 6-8 polish per `docs/ORIGINAL_STUDIO_COMPLETE_EXECUTION_PLAN.md`
§12-14 (lines ~635-793). Main plan file NOT updated. No `npm run build`
per instructions.

## Files changed

Backend (`backend/`):
- `app/routers/studio.py`
  - `_benchmark_buy_and_hold()` — deterministic buy-and-hold benchmark from the
    same observed closes, normalized to 1.0; `[]` when unusable (renders as
    unavailable, never zero).
  - `_orders_from_signals()` + `FILLS_UNAVAILABLE` — orders derived ONLY from
    persisted nonzero-direction signals; `fills: None` with an explicit
    unavailable reason (no fill synthesis).
  - Both execution paths (`run_momentum_strategy`, `_process_strategy_results`)
    now return `orders`, `fills: None`, `fills_status`, and a `benchmark_equity`
    series aligned to the equity curve.
  - `SensitivityRequest` + `POST /validation/sensitivity` — bounded 1D/2D grid
    (max 100 cells) over lookback/threshold running deterministic momentum
    Sharpe per cell via the canonical metrics engine.
  - `ScenarioRequest` + `POST /validation/scenarios` — cost-shock, missing-data
    (seeded, deterministic), and delay (lag) variants reusing
    `WalkForwardEngine.run_analysis`; liquidity/regime/adversarial returned as
    named `skipped` with reasons.
  - Incidental repair (own edit, same class as the P13 note): my model insert
    swallowed the `class PortfolioOptimizeRequest` header, merging its body
    into `ScenarioRequest`; header restored, portfolio contract verified.
- `tests/test_studio_p6p8_polish.py` (new, 6 tests) — benchmark normalization +
  empty-on-unusable, orders-only-from-nonzero-signals, sensitivity
  determinism, scenario transform determinism + walk-forward reuse, skipped
  scenario identities.

Frontend (`frontend/src/`):
- `lib/studioResults.js` — `normalizeStudioExecutionResult` carries
  `orders`/`fills`/`fillsStatus`; `deriveOrdersFromSignals()`,
  `replayFillLinkage()`; `buildStudioResultsJson()` (+download) and
  `buildStudioResultsHtml()` (+download, print-friendly save-as-PDF).
- `lib/studioReplay.js` — `positionStateAtCursor()`, `matchesReplayBreakpoint()`,
  `replayFillCausality()`.
- `lib/studioApi.js` — `runSensitivityGrid()`, `runValidationScenarios()`.
- `lib/studioValidators.js` — execution validator tolerates optional
  `benchmark_equity` (length-matched or absent), `series: null`, and
  `orders`/`fills` fields; new `isSensitivityResponse`/`isScenarioResponse`.
- `components/studio/TearsheetView.jsx` — benchmark dotted-blue overlay on the
  same synchronized x-scale (min/max includes it); `OrdersFillsPanel`
  (observed orders table, fills-unavailable note); CSV+JSON+HTML export
  buttons; Arrow-deferred + PDF-via-print notes with reasons.
- `components/studio/ValidateView.jsx` — `SensitivityPanel` (editable
  lookback/threshold grid, result table + Canvas2D heatmap, no 3D) and
  `ScenarioPanel` (cost shock / missing % / delay bars, observed scenario
  table + skipped list), rendered with and without walk-forward results.
- `components/studio/ReplayView.jsx` — position/log sync strip (position state
  after N events, fill causality status, persisted job-event count), O/X
  position timeline, conditional breakpoint predicate (event type + metric +
  operator + threshold) pausing autoplay, persisted job-log panel
  (`getStudioJob().events`, first 50), fill-causality banner.
- `lib/__tests__/studioResults.test.ts` (+2), `lib/__tests__/studioReplay.test.ts`
  (+3) — orders/fills honesty, JSON/HTML exports, position tracking,
  breakpoint matching, fill causality.

## Tests + results

- `npx eslint` on all 9 changed/new frontend files — clean (exit 0). One
  rewrite was needed: a single-line HTML template tripped the babel parser,
  replaced with joined string parts; one insert split `FoldCard`, repaired.
- Focused frontend gate (Results/Validate/Replay/composer suites) —
  **8 suites / 37 tests passed**.
- Broader Studio frontend gate (`src/components/studio`, studio lib tests,
  studio stores) — **42 suites / 160 tests passed**.
- Backend (run with `/opt/homebrew/bin/python3.11`, the interpreter carrying
  deps+pytest; default `python3` is 3.9 and cannot parse the router's 3.10+
  syntax): `test_studio_p6p8_polish + metrics + execution + jobs + schemas +
  portfolio + paper + reports` — **69 passed, 1 failed**.
  The failure (`test_monte_carlo_resampling_methods_are_named_and_reproducible
  [moving_block_bootstrap]`) is pre-existing and untouched by this change:
  `MonteCarloEngine` with a 4-value repeating series yields a degenerate
  final-value range and `np.histogram(..., bins=50)` raises under the installed
  numpy. No P6-P8 code path touches that engine.
- Router model smoke: `SensitivityRequest`, `ScenarioRequest`,
  `PortfolioOptimizeRequest` construct correctly; 100-cell grid bound enforced.
- `npm run build` NOT executed per instructions.

## Limitations / truth boundary

- Benchmark is buy-and-hold of the same observed closes, not an external index;
  labeled as such; absent when closes are unusable.
- Orders are signal-derived intent records, not venue orders; fills do not
  exist anywhere in the contract and are never synthesized — Replay shows
  fill causality as unavailable with the reason.
- PDF is the browser print dialog over the print-friendly HTML export; Arrow
  is deferred (no governed columnar schema; CSV/JSON carry identical values).
- Sensitivity Sharpe uses a deterministic momentum proxy through the canonical
  metrics engine, not a re-run of arbitrary user strategy code.
- Missing-data scenario zeroes deterministically selected bars (seeded); it
  marks absence without inventing values. Delay scenario cold-starts with
  zeros for the lagged bars.
- Replay log panel reads persisted `job.events` via `getStudioJob` (same
  owner digest as the existing client); the SSE `/jobs/{id}/events` stream
  remains the live transport.

## Rollback

`git checkout` does not apply (worktree files untracked/staged, no HEAD for
these paths). To revert P6-P8 polish only: restore
`backend/app/routers/studio.py` (keep the `PortfolioOptimizeRequest` header
repair if the concurrent editor has not fixed it),
`frontend/src/lib/studioResults.js`, `frontend/src/lib/studioReplay.js`,
`frontend/src/lib/studioApi.js`, `frontend/src/lib/studioValidators.js`,
`frontend/src/components/studio/TearsheetView.jsx`,
`frontend/src/components/studio/ValidateView.jsx`,
`frontend/src/components/studio/ReplayView.jsx`,
`frontend/src/lib/__tests__/studioResults.test.ts`,
`frontend/src/lib/__tests__/studioReplay.test.ts` from backup, and delete
`backend/tests/test_studio_p6p8_polish.py` plus `docs/evidence/studio/P6-P8-polish/`.

## Next

- Consider router-level tests for `/validation/sensitivity` and
  `/validation/scenarios` (currently covered at engine/model level) once the
  concurrent `studio.py` refactor settles.
- If an external-index benchmark or venue fills ever enter the execution
  contract, wire them into `benchmark_equity` / `fills` and flip the
  unavailable states; no UI rework needed beyond that.
- Pre-existing failure to watch: MC moving-block histogram binning under the
  installed numpy (unrelated to P6-P8).
