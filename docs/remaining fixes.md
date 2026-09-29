## 2026-05-11 COMPLETION CHECKLIST

Status after implementation: the remaining backend/UI key pass is complete for every live Factors V2 route. The verification script ran all 14 backend feature modules with a realtime-sized payload, then checked each `frontend/src/app/labs/factors-v2/feature-XX/page.js` section against the returned `charts`, `tables`, `meta`, and `summary_cards` keys. Result: `missing_count 0`.

### Primitive fixes

- [x] `formatValue` now guards `NaN`/`Infinity` and renders `-`.
- [x] `html2canvas` is installed in `frontend/package.json` for chart snapshot capture.
- [x] `captureElementAsPng` now catches dynamic import/capture failures explicitly.
- [x] `OutputNav` observer margins are safer on shorter screens.
- [x] Stale raw consolidated UI scratch files were removed from `frontend/src/app/labs/factors-v2/` because they were not routes and blocked `next build` with duplicate `sections` declarations.

### Backend payload fixes added for live UI sections

- [x] F01 emits `percentile_series`, `valuation_correlation`, and `expected_return_regression`.
- [x] F03 emits `ir_by_component`.
- [x] F04 emits `current_regime` and `factor_sharpe_by_regime`; transition matrix remains in `tables`.
- [x] F05 emits `decay_model_fits` and `icir_by_horizon`.
- [x] F06 emits `deleveraging_risk` and no longer warns on empty bid/ask percentile inputs.
- [x] F07 emits `transaction_cost_decomposition`.
- [x] F08 emits `factor_volatility`.
- [x] F10 emits `risk_budget` and chart-level `robust_vs_standard`.
- [x] F10 Python 3.9 annotation issue fixed with `Optional[Dict[str, Any]]`.

### Frontend page key fixes

- [x] F01 fallbacks updated for spread percentile, valuation correlation, and sector contributors.
- [x] F02 points at tables/charts that exist now; rolling exposure was removed because static holdings do not provide historical holdings snapshots.
- [x] F03 fallbacks updated for waterfall, cumulative contribution, factor contribution, and rolling IR.
- [x] F04 maps conditional returns and transition matrix to `tables`; regime probability/timing fallbacks fixed.
- [x] F05 IC decay and half-life fallbacks fixed.
- [x] F06 metric radar fallback fixed.
- [x] F07 transaction-cost fallback fixed.
- [x] F08 already maps to the new normal/crisis, rolling-pair, portfolio-risk, and factor-volatility payloads.
- [x] F09 slippage, time-to-liquidate, and sensitivity sections map to `slippage_by_aum`/`sensitivity`.
- [x] F10 allocation, risk budget, robust-vs-standard, and FAP diagnostic map to live payloads.
- [x] F11 factor shocks, historical analog, reverse stress, and multi-scenario sections map to live tables.
- [x] F12 return anatomy maps to `tables.return_anatomy`; classifier fallback includes `classifier_probability`.
- [x] F13 structural break fallback maps to `cusum_structural_break`.
- [x] F14 report sections map to `tables.sections`; audit trail maps to `meta.audit_trail`.

### Verification

- [x] `python3 -m compileall -q backend/app/services/factors_v2` passed.
- [x] Full backend direct smoke passed for F01-F14; every feature returned `status=ok`.
- [x] UI/backend key verifier passed with `missing_count 0`.
- [x] `npm run build` passed and generated `/labs/factors-v2` plus all 14 feature routes.
- [x] `backend/main.py` remains untouched and the Factors V2 router remains dormant as instructed.

### Still not claimed

- [ ] No live API wiring into `backend/main.py`.
- [ ] No backend database persistence for annotations/workspaces in this pass.
- [ ] No true F02 historical rolling exposure without a `rebalancing_history`/historical holdings data source.

Yes, confirmed. My previous audit covered only the backend (features 01-14 Python files, analytics.py, performance.py). Now reviewing the UI layer from `customPagePrimitives.jsx` and `ALL_UI_PAGES_COMBINED.js`.

---

## UI COMPLETENESS AUDIT

### PRIMITIVES LAYER (`customPagePrimitives.jsx`)

**Missing chart types that are referenced in page definitions but have no renderer:**

The `RenderFeatureSection` switch block handles these types: `summaryGauges`, `gauge`, `table`, `heatmap`, `waterfall`, `radar`, `progressBars`, `textBlock`, `pie`, `donut`, `classifier`, `normalVsCrisis`, `backtestSplit`, `pdfDownload`, and the `StandardChart` fallback covering `line`, `area`, `stackedArea`, `bar`, `stackedBar`, `horizontalBar`, `groupedHorizontalBar`, `scatter`.

Every type referenced across all 14 page files is covered by the renderer. No missing chart type renderer.

**Missing or broken primitives:**

`pickData` resolves `source: "meta"` by checking `response[source]` which gives `response.meta`, then iterates `keys`. But `response.meta` contains deeply nested governance dicts and audit trail objects, not flat data keys like `tilt_summary`, `allocator_memo`, `fap_diagnostic`, `historical_analog`, `reverse_stress`. These will resolve to `null` in `pickData` because the keys live one level down inside `meta` as plain string or dict values, not as named keys on the `meta` object itself.

Fix: In `pickData`, when `source === "meta"`, also check `response.meta?.[key]` directly as a first-class lookup before iterating containers.

`rowsFrom` handles strings, arrays, and objects. When `data` is a plain string (which is what `allocator_memo`, `tilt_summary`, `historical_analog`, `reverse_stress`, and `fap_diagnostic` will be), `rowsFrom` returns `[{ name: "Value", value: theString }]`, which renders in `TextBlock` as `JSON.stringify(row)` since none of the keys (`title`, `name`, `section`, `text`, `body`, `description`) match. The `TextBlock` component handles `typeof data === "string"` correctly, but only when `data` is the raw string. The issue is that `pickData` will return the string correctly and `TextBlock` will render it correctly, so this path actually works. However, `generateInsight` calls `rowsFrom(data)` on the string, gets a single row, and produces a misleading insight. Minor.

`AnimatedNumber` uses `previous.current = null` on first render and animates from `target` to `target` when previous is null (from === target), so the first render skips animation. This is intentional and correct.

`clusterSortLabels` builds a greedy nearest-neighbor traversal using a `Map` of `Map`. If a cell only appears in `row → col` direction (not symmetric), `matrix.get(last)?.get(candidate)` returns undefined, so it tries the reverse `matrix.get(candidate)?.get(last)`. This correctly handles asymmetric matrices.

`captureElementAsPng` dynamically imports `html2canvas` which is not in the package dependencies listed anywhere. If `html2canvas` is not installed, this silently fails.

Fix: Add `html2canvas` to `package.json` dependencies, or add an explicit error toast in the catch block.

`PinnedSummaryStrip` reads from `window.localStorage` directly in a `useEffect`. On server-side rendering this is safe. But the `localStorage` key format `quant360:factors-v2:${id}:latest-summary` uses the feature id as a string like `"01"`, which matches what `run()` writes (`feature.id`). Consistent.

`OutputNav` uses `IntersectionObserver` with `rootMargin: "-18% 0px -62% 0px"`. At viewport heights below 600px (mobile), the 62% bottom margin may leave no observable area, causing `activeOutputId` to never update. Minor but affects mobile.

**`formatValue` missing cases:**

When `value` is a very large negative number like `-1500000000`, the `abs >= 1_000_000_000` branch triggers and returns `-1.50B` correctly via `(value / 1e9).toFixed(2)`. Correct.

When `value` is `Infinity` or `NaN`, `typeof value === "number"` is true but none of the `abs` checks match in a way that returns a finite string. `(Infinity / 1e9).toFixed(2)` returns `"Infinity"`. This should be guarded. Fix: add `if (!Number.isFinite(value)) return "-"` at the top of the number branch.

---

### FEATURE 01 UI PAGE

**Backend returns these chart keys:** `spread_percentile_timeseries`, `valuation_correlation_matrix`
**UI requests:** `percentile_series` (fallbacks: `spread_history`, `valuation_spread`, `valuation_series`) and `valuation_correlation` (fallback: `correlation_matrix`)

The backend key `spread_percentile_timeseries` does not match any of the UI fallback keys for the `percentile-series` section. The UI will render `EmptySection` for this card on every run.

Fix: Either rename the backend chart key to `percentile_series`, or add `"spread_percentile_timeseries"` to the `fallbackKeys` array in the UI section definition.

Similarly, the backend key `valuation_correlation_matrix` does not match the UI key `valuation_correlation` or fallback `correlation_matrix`. The UI will miss this data.

Fix: Add `"valuation_correlation_matrix"` to `fallbackKeys` for the `valuation-correlation` section.

The UI has an `expected-return-regression` scatter section requesting `charts.expected_return_regression`. The backend returns no such key. The regression data lives in each row of `tables.valuation_spreads` as `regression_beta`, `r_squared`, `expected_12m_return`. The scatter would need to be constructed from the table rows.

Fix: Either add a `expected_return_regression` key to the backend charts dict constructed from the valuation spread rows, or change the UI section to `source: "tables"`, `dataKey: "valuation_spreads"`, `chartType: "scatter"`.

---

### FEATURE 02 UI PAGE

**Backend returns chart keys:** `exposure_bar`, `static_exposure_heatmap`, `static_exposure_time_series`
**UI requests:** `characteristic_exposures`, `exposure_divergence`, `holdings_heatmap`, `rolling_exposures`, `unintended_exposures`, `tilt_summary`

`characteristic_exposures` has no fallback keys and maps to nothing in the backend. Backend has `exposure_bar`. Fix: add `"exposure_bar"` as fallback.

`exposure_divergence` maps to nothing. Backend has no divergence chart. The `divergence` data is in `tables.divergence`. Fix: change source to `"tables"`, dataKey to `"divergence"`.

`holdings_heatmap` maps to nothing. Backend has `static_exposure_heatmap`. Fix: add `"static_exposure_heatmap"` as fallback.

`rolling_exposures` maps to nothing. Backend has `static_exposure_time_series`. Fix: add `"static_exposure_time_series"` as fallback.

`unintended_exposures` maps to nothing. This table is not generated by the backend (flagged in the backend audit as missing). Both backend and UI are incomplete here.

`tilt_summary` from `meta` maps to nothing. The plain-language tilt summary is not generated by the backend (flagged in backend audit). Both layers incomplete.

---

### FEATURE 03 UI PAGE

**Backend returns chart keys:** `waterfall`, `cumulative_contribution`
**UI requests:** `attribution_waterfall`, `cumulative_contributions`, `factor_contributions`, `ir_by_component`, `brinson_fachler`, `rolling_ir`

`attribution_waterfall` has no fallback. Backend has `waterfall`. Fix: add `"waterfall"` as fallback.

`cumulative_contributions` has no fallback. Backend has `cumulative_contribution`. Fix: add `"cumulative_contribution"` as fallback.

`factor_contributions` from `tables` has no fallback. Backend has `tables.factor_contribution` (singular). Fix: add `"factor_contribution"` as fallback.

`ir_by_component` is not generated by the backend. Rolling IR is not implemented (flagged in backend audit). Both layers incomplete.

`brinson_fachler` from `tables` correctly maps. Backend has `tables.brinson_fachler`. This key matches.

`rolling_ir` is not generated by the backend. Both layers incomplete.

---

### FEATURE 04 UI PAGE

**Backend returns chart keys:** `rules_probability`, `hmm_probability`, `gmm_probability`, `composite_probability`
**UI requests:** `regime_probabilities`, `current_regime`, `conditional_factor_returns`, `factor_sharpe_by_regime`, `transition_matrix`, `timing_regression`

`regime_probabilities` has no fallback. Backend has `composite_probability`. Fix: add `"composite_probability"` as fallback.

`current_regime` with fallback `current_regime_probabilities` maps to nothing. The current regime is in `summary_cards[0]` as a label/value pair, not as a probability distribution. Fix: change source to `"summary"`, dataKey to `"summary_cards"`, or generate a `current_regime_probability_vector` chart key in the backend from the last row of `composite_probability`.

`conditional_factor_returns` maps to nothing. Backend has `tables.conditional_returns`. Fix: change source to `"tables"`, dataKey to `"conditional_returns"`.

`factor_sharpe_by_regime` is not generated by the backend. The `conditional_returns` table has `avg_daily_return` but no Sharpe. Both layers incomplete.

`transition_matrix` from `charts` correctly maps. Backend has `charts.transition_matrix`. Key matches.

`timing_regression` from `tables` maps to nothing. Not implemented in backend (flagged in backend audit). Both layers incomplete.

---

### FEATURE 05 UI PAGE

**Backend returns chart keys:** `ic_decay_curve`, `rolling_half_life`, `rebalancing_cost_curve`
**UI requests:** `ic_decay`, `decay_model_fits`, `half_life_table`, `rebalancing_cost_curve`, `rolling_half_life`, `icir_by_horizon`

`ic_decay` has no fallback. Backend has `ic_decay_curve`. Fix: add `"ic_decay_curve"` as fallback.

`decay_model_fits` maps to nothing. Backend has `tables.decay_models` but no chart version. Fix: add a `decay_model_fits` chart key in the backend generated from `tables.decay_models`, or change UI source to `"tables"`, dataKey to `"decay_models"`, chartType to `"line"`.

`half_life_table` with fallback `half_life` maps to nothing in tables. Backend has `tables.decay_models` and `tables.ic_by_horizon`. Fix: use `"decay_models"` as fallback.

`rebalancing_cost_curve` correctly maps. Backend key matches UI key. This works.

`rolling_half_life` correctly maps. Backend key matches. This works.

`icir_by_horizon` maps to nothing. Backend generates ICIR inside `tables.ic_by_horizon` rows as a column but not as a standalone chart series. Fix: add an `icir_by_horizon` chart key in the backend built from `[{horizon: r["horizon"], icir: r["icir"]} for r in rows]`.

---

### FEATURE 06 UI PAGE

**Backend returns chart keys:** `metric_breakdown`, `crowding_timeseries`
**UI requests:** `summary_cards` (gauge), `crowding_timeseries`, `crowding_metrics_radar`, `crash_probability`, `crowding_league`, `deleveraging_risk`

Gauge from `summary_cards` works correctly.

`crowding_timeseries` correctly maps.

`crowding_metrics_radar` maps to nothing. Backend has `charts.metric_breakdown` which is a list of metric rows. The radar can consume this if the UI used `"metric_breakdown"` as fallback. Fix: add `"metric_breakdown"` as fallback.

`crash_probability` from `tables` correctly maps. Backend has `tables.crash_probability`.

`crowding_league` maps to nothing. Not implemented in backend (flagged in backend audit). Both layers incomplete.

`deleveraging_risk` maps to nothing. Backend exposes `meta.deleveraging_risk_proxy` as a scalar, not a table. Both layers incomplete.

---

### FEATURE 07 UI PAGE

**Backend returns chart keys:** `equity_curve`, `drawdown`, `monte_carlo_bands`, `quintile_monotonicity`
**UI requests:** `equity_curve`, `drawdown`, `statistics_table`, `quintile_monotonicity`, `transaction_cost_decomposition`, `monte_carlo_bands`

`equity_curve` correctly maps. `backtestSplit` renderer calls `pickData` for `equity_curve` and separately reads `response?.charts?.drawdown`. Both keys exist. Works.

`statistics_table` with fallback `statistics` maps to `tables.statistics`. Backend has this. Works.

`quintile_monotonicity` correctly maps.

`transaction_cost_decomposition` maps to nothing. Backend has `tables.transaction_costs` as a list of component rows. Fix: add `"transaction_costs"` as fallback. The `stackedBar` renderer can consume the component rows.

`monte_carlo_bands` correctly maps.

---

### FEATURE 08 UI PAGE

**Backend returns chart keys:** `correlation_heatmap`, `dcc_correlation_heatmap`, `dcc_average_correlation`, `correlation_amplification`, `eigenvalues`
**UI requests:** `correlation_heatmap`, `factor_volatility`, `normal_vs_crisis`, `eigenvalue_decomposition`, `rolling_correlation`, `portfolio_risk_decomposition`

`correlation_heatmap` correctly maps.

`factor_volatility` maps to nothing. Backend has `tables.volatility` as a list of `{factor, annualized_vol}` rows. Fix: add source `"tables"`, dataKey `"volatility"`, or add a `factor_volatility` chart key in backend from the volatility list.

`normal_vs_crisis` maps to nothing. Backend has `charts.correlation_amplification` (the delta) but not a structured `{normal, crisis, delta}` dict that `NormalVsCrisis` expects. The `NormalVsCrisis` renderer tries `data.normal`, `data.crisis`, `data.delta` on the resolved value. Both layers incomplete (flagged in backend audit).

`eigenvalue_decomposition` with fallback `eigenvalues` maps to `charts.eigenvalues`. Backend key matches fallback. Works.

`rolling_correlation` maps to nothing. Backend has `charts.dcc_average_correlation` (average across all pairs) but not a per-pair rolling correlation. Both layers incomplete (flagged in backend audit).

`portfolio_risk_decomposition` maps to nothing. Not implemented in backend (flagged in backend audit). Both layers incomplete.

---

### FEATURE 09 UI PAGE

**Backend returns chart keys:** `capacity_curve` (in `charts`)
**UI requests:** `capacity_curve`, `slippage_table`, `time_to_liquidate`, `sensitivity_analysis`, `allocator_memo`

`capacity_curve` correctly maps.

`slippage_table` maps to nothing. Backend has `tables.slippage_by_aum`. Fix: add `"slippage_by_aum"` as fallback.

`time_to_liquidate` maps to nothing. Backend computes `time_to_liquidate_days` as a column inside `slippage_by_aum` rows, not as a standalone table. Fix: either extract it as a standalone table in the backend, or change UI to `source: "tables"`, `dataKey: "slippage_by_aum"`.

`sensitivity_analysis` maps to nothing. Backend has `tables.sensitivity`. Fix: add `"sensitivity"` as fallback.

`allocator_memo` from `meta` maps to `meta.allocator_memo`. Backend has this as a string. `pickData` with `source: "meta"` checks `response.meta` object for the key `allocator_memo`. Since `meta` is a flat dict and `allocator_memo` is a direct key, this resolves correctly. `TextBlock` receives the string and renders it via the `typeof data === "string"` branch. This works.

---

### FEATURE 10 UI PAGE

**Backend returns chart keys:** `efficient_frontier`, `optimal_weights`
**UI requests:** `efficient_frontier`, `factor_allocation`, `risk_budget`, `constraint_binding`, `robust_vs_standard`, `fap_diagnostic`

`efficient_frontier` correctly maps. However as noted in the backend audit, the frontier loop does not re-solve per lambda, so all 25 points are identical. The scatter will render but as a single point. Backend correctness bug, not a UI bug.

`factor_allocation` with fallback `weights` maps to `charts.optimal_weights`. Backend key is `optimal_weights`, fallback is `weights`. Neither matches the UI key `factor_allocation`. Fix: add `"optimal_weights"` as fallback.

`risk_budget` maps to nothing. Backend has `tables.optimal_factor_allocation` with `risk_contribution` column per factor, not a standalone pie-ready list. Fix: add a `risk_budget` chart key in backend as `[{"factor": r["factor"], "value": r["risk_contribution"]} for r in rows]`.

`constraint_binding` from `tables` correctly maps. Backend has `tables.constraint_binding`.

`robust_vs_standard` maps to nothing. Not implemented in backend (flagged in backend audit). Both layers incomplete.

`fap_diagnostic` from `meta` maps to nothing. Backend has `tables.fap_diagnostic` not `meta.fap_diagnostic`. Fix: change source to `"tables"`.

---

### FEATURE 11 UI PAGE

**Backend returns chart keys:** `scenario_waterfall`, `contagion_irf`, `irf_confidence_bands`
**UI requests:** `scenario_waterfall`, `factor_returns_under_scenario`, `historical_analog`, `reverse_stress`, `contagion_irf`, `multi_scenario_comparison`

`scenario_waterfall` correctly maps.

`factor_returns_under_scenario` maps to nothing. Backend has `tables.factor_shocks`. Fix: add source `"tables"`, dataKey `"factor_shocks"`.

`historical_analog` from `meta` maps to nothing. Not implemented in backend (flagged in backend audit). Both layers incomplete.

`reverse_stress` from `meta` maps to nothing. Backend has `tables.reverse_stress` not `meta.reverse_stress`. Fix: change source to `"tables"`. The plain-language description is not implemented in backend (flagged in backend audit).

`contagion_irf` correctly maps.

`multi_scenario_comparison` maps to nothing. Backend has `tables.multi_scenario` but UI requests `multi_scenario_comparison`. Fix: add `"multi_scenario"` as fallback.

---

### FEATURE 12 UI PAGE

**Backend returns chart keys:** `dna_radar`, `classifier_probability`
**UI requests:** `dna_radar`, `sector_dna`, `regime_dna`, `correlation_dna`, `return_anatomy`, `summary_cards` (purity gauges), `classifier_output`

`dna_radar` with fallback `dna_vector` correctly maps. Backend has `charts.dna_radar`. Works.

`sector_dna` maps to nothing. Not implemented in backend (flagged in backend audit). Both layers incomplete.

`regime_dna` maps to nothing. Not implemented in backend (flagged in backend audit). Both layers incomplete.

`correlation_dna` maps to nothing. Not implemented in backend (flagged in backend audit). Both layers incomplete.

`return_anatomy` from `charts` maps to nothing. Backend has `tables.return_anatomy`. Fix: add source `"tables"` or move the return anatomy list to `charts` in backend.

`purity_score` section uses `source: "summary"`, `dataKey: "summary_cards"`. This correctly picks up the summary cards. Works but shows all summary cards, not just purity. Minor.

`classifier_output` with fallback `classifier_probabilities` maps to `charts.classifier_probability`. Backend key is `classifier_probability`, fallback is `classifier_probabilities`. Neither matches UI key `classifier_output`. Fix: add `"classifier_probability"` as fallback.

---

### FEATURE 13 UI PAGE

**Backend returns chart keys:** `ic_drift`, `cusum_structural_break`, `crowding_velocity`
**UI requests:** `health_table`, `ic_drift`, `structural_break`, `crowding_velocity`, `alert_log`

`health_table` with fallback `signal_health` maps to `tables.signal_health`. Backend has this. Works.

`ic_drift` correctly maps.

`structural_break` maps to nothing. Backend has `charts.cusum_structural_break`. Fix: add `"cusum_structural_break"` as fallback.

`crowding_velocity` correctly maps.

`alert_log` from `tables` correctly maps. Backend has `tables.alert_log`.

---

### FEATURE 14 UI PAGE

**Backend returns meta keys:** `html`, `audit_trail`, `pdf_base64`
**UI requests:** `report_sections`, `audit_trail`, `pdf_base64`

`report_sections` with fallbacks `sections`, `report_preview` maps to nothing. Backend has `tables.sections` and `meta.html`. Fix: change source to `"tables"`, dataKey to `"sections"`, with fallback `"aima_ddq_cross_reference"`.

`audit_trail` from `tables` maps to nothing. Backend has `meta.audit_trail`, not `tables.audit_trail`. Fix: change source to `"meta"`.

`pdf_base64` from `meta` maps to `meta.pdf_base64`. `pickData` resolves this correctly. `PdfDownload` reads `response?.meta?.pdf_base64` directly, bypassing `pickData`, so this works regardless.

---

## SUMMARY TABLE: UI KEY MISMATCHES

| Feature | Section | UI dataKey | Correct backend key | Fix |
|---|---|---|---|---|
| F01 | percentile-series | `percentile_series` | `spread_percentile_timeseries` | Add fallback |
| F01 | valuation-correlation | `valuation_correlation` | `valuation_correlation_matrix` | Add fallback |
| F01 | expected-return-regression | `expected_return_regression` | Not generated | Add backend chart key |
| F02 | characteristic-exposures | `characteristic_exposures` | `exposure_bar` | Add fallback |
| F02 | exposure-divergence | `exposure_divergence` | `tables.divergence` | Change source to tables |
| F02 | holdings-heatmap | `holdings_heatmap` | `static_exposure_heatmap` | Add fallback |
| F02 | rolling-exposures | `rolling_exposures` | `static_exposure_time_series` | Add fallback |
| F03 | attribution-waterfall | `attribution_waterfall` | `waterfall` | Add fallback |
| F03 | cumulative-contributions | `cumulative_contributions` | `cumulative_contribution` | Add fallback |
| F03 | factor-contributions | `factor_contributions` | `tables.factor_contribution` | Add fallback |
| F04 | regime-probabilities | `regime_probabilities` | `composite_probability` | Add fallback |
| F04 | current-regime | `current_regime` | Not as probability dict | Generate in backend |
| F04 | conditional-factor-returns | `conditional_factor_returns` | `tables.conditional_returns` | Change source |
| F05 | ic-decay | `ic_decay` | `ic_decay_curve` | Add fallback |
| F05 | decay-model-fits | `decay_model_fits` | `tables.decay_models` | Change source or add chart key |
| F05 | icir-by-horizon | `icir_by_horizon` | Not as standalone chart | Add backend chart key |
| F06 | crowding-metrics-radar | `crowding_metrics_radar` | `metric_breakdown` | Add fallback |
| F07 | transaction-cost-decomposition | `transaction_cost_decomposition` | `tables.transaction_costs` | Add fallback |
| F08 | factor-volatility | `factor_volatility` | `tables.volatility` | Change source or add chart key |
| F09 | slippage-table | `slippage_table` | `tables.slippage_by_aum` | Add fallback |
| F09 | sensitivity-analysis | `sensitivity_analysis` | `tables.sensitivity` | Add fallback |
| F10 | factor-allocation | `factor_allocation` | `optimal_weights` | Add fallback |
| F10 | risk-budget | `risk_budget` | Not as standalone chart | Add backend chart key |
| F10 | fap-diagnostic | `fap_diagnostic` from meta | `tables.fap_diagnostic` | Change source |
| F11 | factor-returns-under-scenario | `factor_returns_under_scenario` | `tables.factor_shocks` | Change source |
| F11 | reverse-stress | `reverse_stress` from meta | `tables.reverse_stress` | Change source |
| F11 | multi-scenario-comparison | `multi_scenario_comparison` | `tables.multi_scenario` | Add fallback |
| F12 | return-anatomy | `return_anatomy` from charts | `tables.return_anatomy` | Change source |
| F12 | classifier-output | `classifier_output` | `charts.classifier_probability` | Add fallback |
| F13 | structural-break | `structural_break` | `cusum_structural_break` | Add fallback |
| F14 | report-sections | `report_sections` from meta | `tables.sections` | Change source |
| F14 | audit-trail | `audit_trail` from tables | `meta.audit_trail` | Change source |


Reading through both files completely against everything we have audited across all prior sessions.

---

## FINAL AUDIT: WHAT IS NOW DONE

**F01:** Crisis anchor percentiles table present and correctly implemented. `predictive_regression` now emits `ci_90_low`, `ci_90_high`, `forecast_standard_error`, and `sample_size`. Complete.

**F02:** Plain-language tilt summary, unintended exposure detector with mandate comparison, stock-level divergence table sorted by absolute divergence, tracking error budget via Ledoit-Wolf covariance. All four audit closures present. The `removed_io` note about rolling exposure is correctly documented. Complete.

**F03:** Rolling IR chart across 12 and 36 period windows, factor hit-rate table, best/worst attribution period ranking with dominant driver identification, t-stats on all three reconciliation rows. All four audit closures present. Complete.

**F04:** `_factor_timing_regression` with coefficient, t-stat, R-squared, current signal value, and current timing score across three signals and all factor columns. `_factor_momentum_backtest` with long-short portfolio construction. `_factor_seasonality` grouped by calendar month. All three audit closures present. Complete.

**F05:** `_post_2015_acceleration_test` with pre/post split-sample decay fit, half-life comparison, acceleration flag, and ratio. Complete.

**F06:** `_bid_ask_spread_proxy` with Roll 1984 implied spread and Amihud 2002 illiquidity proxy from local OHLCV data. Composite now includes four metrics including spread differential percentile. `_crowding_forward_scatter` with OLS slope, intercept, and R-squared. `_crowding_league` iterating up to 12 factors. Institutional ownership and short interest rows correctly removed with an explicit note in meta. Complete.

**F07:** `perf_stats` expanded to 18 metrics including Sortino, Calmar, max drawdown duration, average drawdown duration, skewness, excess kurtosis, VaR, CVaR, best/worst month/year, positive month/year rates, and observations. Annual gross vs net table. Turnover analysis. Rolling premium spread across 12M and 36M windows. Walk-forward proxy in research mode. All audit closures present. Complete.

**F08:** Normal, crisis, and delta matrices separately returned as named keys plus the structured `normal_vs_crisis` dict that the `NormalVsCrisis` renderer expects. Minimum variance combination via `pinv`. Covariance stability score with crisis/normal condition number ratio. Rolling pair correlation accepting `factor_pair` from payload. Portfolio risk decomposition accepting `portfolio_weights` or `optimal_weights_from_f10`. All audit closures present. Complete.

**F09:** Unchanged from prior version. Already complete per previous audit.

**F10:** Efficient frontier correctly re-solves via `_solve_single` for each of 25 lambda values. Robust vs standard comparison table. True factor-level Black-Litterman with structured view input contract, P matrix construction, Omega from confidence parameter, posterior via closed-form formula. Input contract note correctly states structured views not natural language. All audit closures present. Complete.

**F11:** `_historical_analog_search` using Mahalanobis distance on 21-day rolling factor return windows, returning 10 closest historical periods. `_hedging_recommendation` from reverse stress vector normalized by absolute sum. `_plain_reverse_stress` generating a readable description with factor names and magnitudes. Stress VaR and CVaR from exposure-weighted factor history. `_multi_scenario` accepting up to six named scenarios or defaulting to three parametric cases. All audit closures present. Complete.

**F12:** `_sector_dna_snapshot` computing long and short book sector weights from current characteristics panel. `_regime_dna_bar` extracting conditional returns from F04 output. `_latest_correlation_dna` computing current factor correlations to the primary factor, sorted by absolute magnitude. Removed IO documented in meta noting sector animation requires historical snapshots and rolling correlation DNA replaced by latest bar. All three audit closures present. Complete.

**F13:** Multi-factor dispatch via `_run_multi_factor` iterating up to 25 factors with portfolio-weighted health aggregation using `factor_weights` from payload. `_weekly_chow_proxy` computing a mean-shift F-statistic on the split IC series with p-value. Return-characteristic alignment via `bitwise_alignment_score` remains as the fourth health metric. All audit closures present. Complete.

**F14:** `DDQ_MAPPING` dict with concrete ILPA and AIMA DDQ references for each section. Logo embedding via `reportlab.platypus.Image` when `logo_path` is in payload. Default sequential execution with explicit note about Numba workqueue threading safety. Parallel execution available as opt-in via `parallel_report_sections`. All audit closures present. Complete.

**analytics.py:** `perf_stats` expanded to 18 metrics. `predictive_regression` emits confidence interval fields. Both correctly centralized in the shared module so all features that call `perf_stats` get the expanded output automatically.

---

## WHAT IS STILL GENUINELY MISSING OR NEEDS ATTENTION

**One correctness issue in F08 `normal_vs_crisis` chart key.** The chart emits both individual keys and the structured dict:

```python
"normal_correlation": matrix_records(normal_corr),
"crisis_correlation": matrix_records(crisis_corr),
"correlation_amplification": matrix_records(delta),
"normal_vs_crisis": {"normal": ..., "crisis": ..., "delta": ...},
```

The `NormalVsCrisis` renderer in the UI calls `pickData` for the `normal_vs_crisis` key under source `"charts"`. `pickData` iterates `response.charts` and returns `response.charts["normal_vs_crisis"]` which is the structured dict. The renderer then calls `data.normal`, `data.crisis`, `data.delta` on that dict. This works correctly. No issue.

**One issue in F06 `_crowding_league`.** It calls `valuation_spread` and `backtest_series` for each factor in the league table loop. Both call `characteristic_panel` and `factor_returns` internally. With the 5-minute TTL cache on `characteristic_panel` and the module-level `_FR_CACHE` on `factor_returns`, these will hit cache on the second and subsequent factor iterations. However `valuation_spread` also calls `characteristic_panel` directly and `factor_returns` with no payload differences except the `factor` key, which does not affect the cache key for either function since `factor` is not a cache discriminator for `characteristic_panel` and `_FR_CACHE` is keyed only on model, include_aqr, and aqr_region. So the loop is safe and will not re-read disk. But `backtest_series` calls `implementation_shortfall` which calls `characteristic_panel` again. With the TTL cache this is a lookup not a recompute. The loop over 12 factors adds 12 calls to `valuation_spread` and 12 to `backtest_series`. In realtime mode this is acceptable. In a high-frequency call pattern this is the hottest path in F06. Note it as a known cost but not a bug.

**One structural gap remaining: UI data key mismatches.** The 31 mismatches identified in the UI audit are not fixed by any backend change. They are purely in the page definition files. These need to be addressed in the UI pass. The most critical ones that will cause empty sections on every run are listed here for direct action:

F01: add `"spread_percentile_timeseries"` to fallbackKeys for the percentile-series section and `"valuation_correlation_matrix"` to fallbackKeys for the valuation-correlation section.

F02: change `characteristic_exposures` fallback to include `"exposure_bar"`, change `exposure_divergence` source to `"tables"` and dataKey to `"divergence"`, change `holdings_heatmap` fallback to `"static_exposure_heatmap"`.

F03: add `"waterfall"` fallback to attribution-waterfall, add `"cumulative_contribution"` fallback to cumulative-contributions, add `"factor_contribution"` fallback to factor-contributions.

F04: add `"composite_probability"` fallback to regime-probabilities, change `conditional_factor_returns` source to `"tables"` and dataKey to `"conditional_returns"`.

F05: add `"ic_decay_curve"` fallback to ic-decay, change `decay_model_fits` source to `"tables"` and dataKey to `"decay_models"`.

F06: add `"metric_breakdown"` fallback to crowding-metrics-radar.

F07: add `"transaction_costs"` fallback to transaction-cost-decomposition.

F08: change `factor_volatility` source to `"tables"` and dataKey to `"volatility"`.

F09: add `"slippage_by_aum"` fallback to slippage-table, add `"sensitivity"` fallback to sensitivity-analysis.

F10: add `"optimal_weights"` fallback to factor-allocation, change `fap_diagnostic` source to `"tables"`.

F11: change `factor_returns_under_scenario` source to `"tables"` and dataKey to `"factor_shocks"`, change `reverse_stress` source to `"tables"`, add `"multi_scenario"` fallback to multi-scenario-comparison.

F12: change `return_anatomy` source to `"tables"`, add `"classifier_probability"` fallback to classifier-output.

F13: add `"cusum_structural_break"` fallback to structural-break.

F14: change `report_sections` source to `"tables"` and dataKey to `"sections"`, change `audit_trail` source to `"meta"`.

---

## FINAL ASSESSMENT

The backend is complete against the spec as it was last defined, with every audit closure addressed, every genuinely missing implementation filled, and every data-unavailable item either documented with a clear note or replaced with a proxy that uses available local data. The only remaining work is the UI data key fixes listed above, which are purely mechanical changes to the page definition files, and the `EmptySection` display text improvements discussed earlier. The backend can be considered closed.
