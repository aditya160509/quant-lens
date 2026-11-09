# Volatility checklist

Checked against the redone review (2026-11-09, feature rule in PLAN section 1b). Code checks: hero literals and the stale output keys are gone from `backend/app`; `connectedness_at_risk` duplicate, `regime_probability_input` and the bootstrap RNG issue are still open. Frontend controls were not read in that pass.

Open-source picks for every batch: [Open source stack](../references/2026-11-open-source.md).

Tick Volatility items here only. Spec: [product review](../reviews/product/VOLATILITY_V2_PRODUCT_REVIEW.md). Stages: [PLAN step 4](PLAN.md). Merge decisions: [merge map section 8](../architecture/CROSS_MODULE_MERGE_MAP.md). V numbers are the review's features; "step" numbers are its section 13 build order. Items marked "reuse" use a Screener or kit piece that already exists.

This is the one list of everything to build. The review stays the spec and has no ticks.

Tags: `E` easy, the review's size S. `M` medium, size M. `H` hard, size L. Items the review does not size carry a tag set here. Work batches in order; within a batch, top to bottom.

## Rules for every batch

- Finish matches [the finish target](../reviews/design/ML_UI_ISSUES.md); none of the 23 logged issues appear here
- Competitors teach features only. V-Lab, Koyfin and Bloomberg set what to include, never how it looks
- Every number is real. Unknown is shown as unknown, never zero or blank; the IV surface page says "no observed options surface"
- Every result prints its limits: ETF history 2015 to January 2026, FX to February 2026, hourly 2023+ for 272 tickers, VIX term legs from 2016, source of the price files unrecorded
- Volatility claims no trading signal
- Nothing is capped silently

## Batch 1: Clean

Steps 1 to 3. E3 M1 H0

- [ ] `E` Step 1: fix the test environment: pin Starlette and httpx so the two API tests run; confirm on Python 3.11 (the 88-passing result is unverified)
- [ ] `E` Step 2: remove the hero literals (V01 18.4%, V04, V06 72), the cross-type fallback keys, the synthetic-surface request and the stale output keys (`vol_calendar`, `vol_ridge`, `volatility_cone`, `vol_signature`); remove the dead `SurfaceGrid`. Checked 2026-11-09: done in code; left: the `asset` alias and the display-only controls (verify in frontend first)
- [ ] `E` Step 3: fix duplicate manifest keys: `connectedness_at_risk` in feature 06 (`feature_06.py` lines 144, 156, 235, 307), and the duplicates in review section 6.1
- [ ] `M` Merge duplicate outputs per review section 6.1 (V01 opening gap, momentum and multi-window; V02 PIT; V04 transition heatmap; V08 contagion IRF; V09 backtest and Kelly), and confirm `regime_probability_input` in `feature_09.py` before cutting it
- [ ] `E` Fix the bootstrap RNG: `stationary_bootstrap_jit` (`core/performance.py`) seeds the global RNG and draws inside `prange`, so results depend on thread count. Use one seed per replicate; add a check that two thread counts give the same draws
- [ ] `E` Label connectedness IRFs and the VAR simulation (`core/connectedness.py`) as model-implied, not observed, on every output that shows them

## Batch 2: Workspace

Step 4. E3 M1 H0

- [ ] `M` Step 4: `/volatility` on `LabConfig`; forms rendered from `GET /features`; the `registry.js` form contract removed
- [ ] `E` First-screen inputs pruned per review section 10 (research-mode group behind a toggle; `asset` alias hidden; first-class controls kept: `assets`, `as_of_date`, `lookback_days`, `annualization`, `estimator`, `horizons`, `models`, `vol_target`, `gross_exposure_cap`, `scenario`, `iv_upload_id`)
- [ ] `E` Display-only controls removed or wired (`compute_mode`, `active_estimators`, `cross_asset_panel`, `network_layout`, `cross_asset_mode`)
- [ ] `E` Reuse: `Exhibit`, `KpiStrip`, `DataTable v2`, `QuickLook`, `FilterChips` and the universe picker from `frontend/src/kit/` and Screener; hatched cells for unknowns. No new per-module primitives

## Batch 3: Estimators and Forecast

Step 5, lead pages. E0 M2 H0

- [ ] `M` Estimators page (V01) on the cinema-kit shell: five estimators per ticker with the efficiency table, and the best estimator for this name and window with the reason printed (A++ 1)
- [ ] `M` Forecast page (V02, V03; default 4 GARCH models, 8 HAR variants): forecast band and scoreboard in one view, with the model confidence set shown, never a single "best" model (A++ 2)

## Batch 4: Regime

Step 6. E0 M1 H0

- [ ] `M` Step 6: Regime page (V04) on the shared regime engine with Factors F04 (merge map decision 7: Volatility owns the kernel); same answer as Factors on the same input

## Batch 5: Cross-asset and stress

Step 7. E0 M1 H1

- [ ] `M` Step 7: Cross-asset page (V06, V07) on the shared covariance engine with Factors F08 and Portfolio F01 (Portfolio owns covariance, decision 3; `volatility_v2/core/dcc.py` is the one DCC, decision 14)
- [ ] `H` V08 stress on one engine with Factors F11 and Portfolio F04; one reverse-stress exhibit with the copula option (tag set here)

## Batch 6: Risk premium

Gated on matched implied vol. E0 M1 H0

- [ ] `M` Risk premium page (V05): shows whether matched implied vol exists, otherwise "physical only" and VRP disabled (tag set here; the review's build order has no step for it)

## Batch 7: Budget

Step 8. E0 M1 H0

- [ ] `M` Step 8: Budget page (V09) with the shared Kelly engine (Portfolio F10 owns it) and the Validate hand-off with the trial count (A++ 4; same hand-off as Factors F07)

## Batch 8: Trust

Step 9. E2 M0 H0

- [ ] `E` Step 9: data gap ledger on every page, extending `data_gaps` (V05) and `estimation_failures` (V06) (A++ 3)
- [ ] `E` Step 9: pre-registered vol target: save the target, gross cap and forecast source before a run, then score the realised outcome against the breach log (A++ 5)

## Batch 9: Consolidate

Step 10. E0 M0 H1

- [ ] `H` Step 10: move loaders and estimators to shared modules; retire or link `volatility_intelligence.py` so there is one volatility API (graph and import check before deleting)

## Batch 10: Ship

E1 M1 H0

- [ ] `M` Verified pages, phone layout (KPI strip two columns), accessibility pass and baselines (PLAN recipe stage 6); price-file source and licence recorded before any charging
- [ ] `E` Tag `volatility-v1`

## Later: free data

Tags set here. E0 M0 H1

- [ ] `H` Refresh ETF history (ends January 2026) and FX (ends February 2026)

## Later: paid data

Tags set here. E0 M0 H2

- [ ] `H` Observed options surface and implied vol for non-US and single-stock names (today only by `iv_upload_id`)
- [ ] `H` Point-in-time data add-on (Desk tier)
