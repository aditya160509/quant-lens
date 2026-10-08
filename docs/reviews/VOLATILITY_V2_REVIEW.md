> **Backend follow-up verified (2026-10-08).** The retained nine-feature backend has strict contracts, durable jobs, real held-out estimation, corrected diagnostics and explicit unsupported-method dispositions. **88 targeted backend tests pass; all nine real-data feature runs return their declared outputs.** Common/statistics/estimators are split into focused modules. See `backend/app/services/volatility_v2/DONE.md` for the current feature-by-feature closure, file fates, commands and limitations. This historical review is preserved below. It does not imply all original aspirational estimators were implemented. Frontend changes and browser checks are excluded by the latest user instruction; the remaining landing hero literals and renderer migration remain frontend work.

# Volatility V2 Review: Spec vs Implementation vs Frontend

Date: 2026-09-29
Scope: `backend/app/services/volatility_v2/` (spec: `backend/app/services/volatility_v2/docs/volitality features.md`, code: `core/analytics.py` 1,495 lines, `core/data_loader.py`, `core/performance.py`, `core/contracts.py`, 9 feature files), `backend/app/services/volatility_intelligence.py` (legacy), `backend/app/api/volatility_v2.py` + mount in `backend/main.py:179`, `frontend/src/app/labs/volatility-v2/`, `frontend/src/components/volatility-v2/`.

Smoke check: no smoke runner or test suite ships with the module (`volatility_v2/tests/` does not exist; no `smoke_test.py`). The internal `review.md` (2026-07-13) claims Features 01, 02, 09 compile and run on local parquet and that all nine contracts load. Every feature returns `status: ok` shapes, so it *looks* complete. The review below is about whether the numbers are right and whether a user can reach them.

---

## 1. Verdict

| Area | State | One line |
|---|---|---|
| Wiring (backend to frontend) | **Broken** | Backend route exists and is mounted, but all 9 pages render without `onRun`, so **Run does nothing**. The module cannot be used from the app. |
| Data integrity | **Broken** | Unknown tickers silently fall back to SPY; missing VIX is synthesized as `yz * 115`; missing macro is filled with 0. VRP, HAR-X, and single-ticker runs can be silently fake. |
| Features 1, 4, 6 (estimators/regime/DY) | Partly correct | Real YZ/GK/Parkinson/RS math, real SJM/HMM/VAR-FEVD, but crypto YZ fallback, rank-heuristic probabilities, and non-daily rolling connectedness. |
| Features 2, 3 | Partly correct | Real `arch` MLE GARCH and real HAR OLS/MCS, but DM table is a stub, FIGARCH d and Nyblom are proxies, HAR-X VRP is inline, ACSV universe is uncontrolled. |
| Feature 5 (VRP) | Partly correct | Real GARCH-physical VRP and BTZ with Hodrick SE, but synthetic-VIX circularity, fixed-weight HAR physical, YZ-rank regime conditioning instead of Feature 4. |
| Feature 7 (DCC) | Partly correct | Two-stage DCC-GARCH MLE is real; `dcc_proxy` is an EWMA copy, DCC time series is rolling correlation, crisis masks are naive, MIDAS is display-only. |
| Features 8, 9 (stress/budget) | Mostly fine after fixes | Lookahead and NIC fixes landed; copula/adversarial/Kelly/preset gaps remain. |
| Tests | **None** | No test file anywhere in `volatility_v2/`. Only the stale self-review `review.md`. |
| Frontend | Shell only | Rich workbench, generic renderer, duplicated input contract, no data flow; landing page is hardcoded sine data; several output cards render reshaped wrong data via fallbacks. |

Bottom line: the module *returns shapes* for every output in the spec, and the vol math core is substantially more honest than Research V2 (real `arch` fits, fixed Bandi-Russell, fixed Parkinson, fixed F09 lookahead), but a risk user would get silent-ticker substitution, synthetic VIX, proxy DCC/Stability/d-values, and stub DM tables, and cannot run it from the UI anyway. Fix order: wire the pages, kill the silent fallbacks, replace the named proxies with the real estimators, then add tests.

---

## 2. Blockers (fix first)

### B1. Volatility V2 is unreachable from the UI
- Backend exists (unlike Research): `backend/app/api/volatility_v2.py:14` defines `GET /labs/volatility/v2/features` from `contracts.all_contracts()` and `POST /labs/volatility/v2/feature/{id}/run` via `registry.run_feature`, mounted at `backend/main.py:179` (`app.include_router(volatility_v2.router, prefix="/api")`, so live at `/api/labs/volatility/v2/...`).
- Frontend: all 9 pages (`app/labs/volatility-v2/feature-01/page.js:168`, `feature-02/page.js`, `feature-03/page.js`, `feature-04/page.js`, `feature-05/page.js`, `feature-06/page.js`, `feature-07/page.js`, `feature-08/page.js`, `feature-09/page.js`) render `<VolatilityV2Workbench featureId="0X" sections={sections} />` with no `onRun` or `response`. `run()` (`customPagePrimitives.jsx:1402-1408`) calls `onRun?.(form)`, which is undefined, so **Run sets the error "Volatility V2 UI shell is ready. API run handler is intentionally not wired in this pass."** and fires a "not wired yet" toast.
- Fix: copy the `factors_v2` page pattern (React Query hook against `/api/labs/volatility/v2/feature/{id}/run`, pass `response`/`onRun` from pages). Run heavy features (02 full 20-model MLE, 04 HMM restarts, 08 100k-path MC, 09 full-regime call) through the existing Studio job transport so the request does not block.

### B2. Silent data fallbacks
- `load_assets` (`analytics.py:287-294`): if the filtered OHLCV frame is empty, it silently loads `SPY` and rewrites `assets = ["SPY"]`. A user asking for "XYZ, ABC" gets SPY results with only `meta.assets` as a clue. Same bug class as Research B3. Fix: return a 422 with the missing tickers.
- `feature_05.py:37-40`: when local macro dates do not overlap the asset window, VIX is synthesized as `(yang_zhang * 115).clip(5, 95)` and VIX3M/6M are NaN. Then `vrp = iv - physical ≈ 0.15 * yz`, so the VRP is a rescaled copy of its own physical leg. Fix: 422 when VIX is absent, or label the panel "physical-only, no implied leg" and disable VRP/Z/BTZ outputs.
- `feature_03.py:37-39`: missing VRP/yield-slope/credit macro is `.fillna(0)`, so HAR-X silently fits on zeros. `feature_06.py:19-23`: a < 2-asset vol panel silently falls back to the `cc` estimator panel. `feature_04.py:66`: missing curve data defaults to 0, which forces the `curve < 0` rule False. Fix: fail closed or surface an explicit `data_gaps` warning per output; never zero-fill regressors.
- `parse_weights` (`analytics.py:1482-1491`): a string `weights` payload (exactly what the frontend textarea placeholder suggests, `registry.js:113`) is not a dict, so it is ignored and replaced with equal weights. Fix: parse JSON strings or reject with 422.

### B3. Placeholders presented as real outputs
- Fake spark: `Spark` (`customPagePrimitives.jsx:705-708`) plots `Math.sin(i * .7)` plus `value % 7`, not the row data. Every metric-deck card carries a sine-wave sparkline.
- Surface flatten: `SurfaceGrid` (`customPagePrimitives.jsx:1218-1220`) renders the 7 x 7 synthetic vol surface as a flat heatmap (`row = horizon_days, col = moneyness_quantile`); the landing `GarchVisual` (`page.js:503-552`) plots a hardcoded `sin`-based Plotly surface, not backend data.
- Unreachable-output fallbacks: F01 pages request `vol_calendar`, `vol_ridge`, `volatility_cone`, `vol_signature` (`feature-01/page.js:17-67`), none of which `feature_01.py:73-98` returns; `pickData` (`customPagePrimitives.jsx:240-251`) then reshapes the efficiency table or comparison series into a calendar/ridge/cone/signature. A calendar of efficiency-table rows is not a calendar.
- Mislabeled proxy: `covariance_methods` returns `"dcc_proxy": dcc` where `dcc = ewma.copy()` (`analytics.py:809-810`); F07 overwrites with real `dcc_mle` later, but any caller of `covariance_methods` alone gets EWMA labeled DCC.
- Fix: delete `Spark` sine or feed it the row history; mark the surface "illustrative synthetic, not fitted"; remove fallbackKeys that cross output types (calendar/ridge/cone/signature must render empty, not reshaped wrong data); rename `dcc_proxy` to `ewma_copy` until a real DCC is present.

---

## 3. Feature-by-feature

Legend: OK = matches spec; WRONG = computes something else under the spec's name; PROXY = explicit stand-in; MISSING = not present.

### Feature 1: Multi-Estimator Daily Volatility Engine
| Spec item | State | Detail |
|---|---|---|
| CC / Parkinson / GK / RS / YZ formulae | OK | `volatility_estimators` (`analytics.py:315-362`): CC = mean of squared log-returns, Park = `mean(log(H/L)^2)/(4 ln 2)`, GK = `0.5 log(H/L)^2 - (2 ln 2 - 1) log(C/O)^2`, RS = `log(H/C)log(H/O) + log(L/C)log(L/O)`, YZ = overnight-var + `k` RS + `(1-k)` open-close-var with `k = 0.34/(1.34 + (M+1)/(M-1))`, `M = window`. Prior Parkinson `1/(1-390^-0.5)` inflation multiplier is gone. |
| Annualization | OK | `sqrt(max(var,0) * annualization)` per estimator (`:345-349`); 252/365 selectable. |
| YZ crypto/FX branch | PROXY | `ticker endswith _USD/=X → yz_var = rs_var` (`:337-340`, same in `_multi` `:390`). Documented nowhere in UI; silently discards the overnight leg. Fix: warn in `meta` or use 24/7 session adjustment. |
| YZ variance ddof | WRONG (minor) | `_rolling_var_np` uses `ddof=1` (`:205`); YZ conventionally uses population variance. Small systematic upward bias. |
| Efficiency table + fat-tail warning | OK | Theoretical 1.0/4.9/7.4/6.2/10.0 with empirical variance ratio, deviation, and `>30%` warning (`:420-445`). Previously missing; now present. |
| DM tournament | OK | QLIKE loss vs 5-day forward summed-squared-return proxy, Newey-West SE, full 5x5 matrix with Bonferroni flag (`:448-483`). Loss proxy choice is debatable but disclosed. |
| Agreement index | OK | Mean pairwise trailing-21d correlation (`:486-508`). |
| Annualized vol panel / ranked panel | OK | Percentiles 252d/5y/full (`feature_01.py:46-53`). |
| Bandi-Russell | OK (fixed) | `bandi_russell_daily_proxy` (`:866-878`): Park variance minus `2 * noise_var` where noise = negative first-order autocovariance of squared returns. Prior `(0.62CC+0.38HL)` heuristic is gone. |
| Range correlation | OK (fixed) | Parkinson cross-product normalization (`:893-906`), not Pearson. |
| Opening-gap fragility | OK | Overnight/range ratio with rolling percentile (`:881-890`). OGF auto-routing (demote YZ / promote RS) still MISSING. |
| Liquidity-threshold toggle, overnight-gap include/exclude, estimator-efficiency benchmark selector, FX/commodity calendar inputs | MISSING | Frontend exposes only window/annualization/estimators/lookback (`registry.js:9-16`). |

### Feature 2: GARCH Family Suite
| Spec item | State | Detail |
|---|---|---|
| 5 models x 4 dists via `arch` MLE | OK | `garch_scoreboard` (`analytics.py:618-678`): GARCH/EGARCH/GJR/APARCH/FIGARCH x Gaussian/t/GED/skew-t, AIC/BIC/RMSE/QLIKE, QLIKE winner, stationary-bootstrap MCS (`reps=150`). Real estimation, not hand-rolled. |
| Realized-GARCH | PROXY | Appended with `qlike: None, rmse: None, mcs_member: False` (`feature_02.py:24-32`), never scored against the 20. Spec wants it in the MCS. |
| DM pairwise table | WRONG (stub) | `diebold_mariano_pairwise_table` (`feature_02.py:153`) dumps one row per model with its own QLIKE, no pairs, no p-values. Frontend books it as a heatmap. Fix: reuse the F01 `dm_tournament` pattern on variance-loss series. |
| News impact curve + regime ribbon | OK (fixed) | NIC conditioned on p10/p50/p90 of fitted conditional-variance history (`feature_02.py:63-68`). Prior fixed 0.75/1.0/1.35 multipliers gone. APARCH/FIGARCH NIC branches remain stylized. |
| Term structure with bands | OK | `garch_term_structure_with_bands` (`:1345-1384`): analytic point + Student-t Monte Carlo p05-p95. Realtime uses 750 paths, research 2500 (disclosed in `meta`). |
| PIT + KS | OK | Gaussian PIT on standardized residuals with hand-rolled KS p-value (`feature_02.py:69-89`). Correct only under the Gaussian row; t/GED/skew-t winners get Gaussian PIT. Fix: PIT under each row's fitted distribution. |
| VaR + Kupiec/Christoffersen | OK | Coverage from `var_coverage` payload (`:73-74`, previously hardcoded 99%), exceedance vs `norm.ppf` cutoff, Kupiec + Christoffersen LR (`:90-111`). Duration/clustering test still a rolling-sum proxy in the table. |
| Long-memory d series | PROXY | `figarch_d_proxy` is rolling autocorr of squared returns (`feature_02.py:146`). Not an MLE of `d`. Spec FIGARCH `d` estimated-or-fixed input MISSING. |
| Nyblom stability | PROXY | Chunk-stddev of `beta[1]` across 4 splits (`feature_02.py:123-136`), not Nyblom (1989)/Hansen (1992) score-process `L` with critical values. |
| APARCH delta benchmark | Partial | Delta rows collected (`:118-122`) but the percentile line indexes a still-empty accumulator, so percentile is always None. |
| Structural break date, weekly frequency, APARCH delta input | MISSING | Spec inputs with no payload path. |

### Feature 3: HAR Forecasting Suite
- Real OLS-HAC HAR stack (OK): 8 variants (HAR, LHAR, HAR-J, HAR-J-Signed, HAR-Leverage, ACSV-HAR, A-ACSV-HAR, HAR-X) with Newey-West SE, RMSE/QLIKE/MAE/R2, directional hit-rate + directional DM, stationary-bootstrap forecast bands, walk-forward checkpoints, MCS equal- and inverse-QLIKE combos (`feature_03.py:40-113`). HAR-J-Signed extra vs spec is fine.
- **HAR-X VRP is inline** (WRONG): `x["vrp"] = vix/100 - yang_zhang` (`feature_03.py:37`). Spec VRP comes from Feature 5 (GARCH physical expectation). This leg ignores the model-based expectation entirely.
- **ACSV universe not configurable** (WRONG): `csv = ret_panel.var(axis=1)` (`:28`) uses every loaded asset, not the frontend "ACSV Universe" field. Cross-sectional dispersion of an ad-hoc panel is not the spec's index-constituent dispersion.
- Jump/leverage/ACSV outputs present (OK): BPV decomposition (`bipower_variation`, `:933-941`), jump-signed splits, leverage rolling-corr chart, macro contribution, walk-forward chart.
- Jump disagreement is a one-row scalar (`:127` `latest_bpv_jump_share` + 21d mean abs gap), not the spec time series with threshold bands. Confidence-level, leverage-toggle, NW-bandwidth, estimator-input (payload honors only first horizon; `volatility_estimator` frontend option is ignored, YZ hardcoded at `:19-21`), and per-horizon MCS-under-QLIKE inputs MISSING.

### Feature 4: Regime Detection Engine
- Three methods real (OK): 9-feature macro-augmented SJM with Viterbi (`:844-863`), `GaussianHMM` Baum-Welch EM with research-mode 20 restarts + BIC K-selection (`feature_04.py:48-57`, `analytics.py:691-738`), adaptive EW-HMM, filtered vs smoothed posteriors, Weibull duration survival, KL method-divergence, 1w/1m/3m transition heatmaps, global sync index.
- **Macro rules + "realized" probs are rank heuristics** (PROXY): `_soft_probs` (`feature_04.py:11-28`) maps cross-sectional rank to probabilities; the same heuristic builds the Brier-score `realized` target (`:69-75`), so ensemble weights are scored against a circular construct. Weights `0.45/0.20/0.25/0.10` (`:66`) undocumented.
- Conditioning gaps (MISSING): 2s10s vs 3M10Y selector exists but macro column `curve_10y_2y` vs `yield_curve_series` mapping is unchecked; K=2/3/4 supported but 6-feature vs 9-feature SJM toggle MISSING; transition-alert threshold honored only as a latest-max gate (`:108`), no timestamped crossing log beyond one row.

### Feature 5: VRP Monitor
- Core VRP real (OK): GARCH-physical (Feature 2 winner), HAR-weighted physical, 252d rolling physical, `vrp = iv - physical`, squared form, z-scores at 252/504/1260/full, Hodrick-SE BTZ alongside OLS-HAC, OU half-life, 30/90/180d HAR term structure.
- **Synthetic VIX circularity** (WRONG when triggered): B2 above. Even when present, VIX3M/6M fall back to `iv * 1.05/1.08` interpolated proxies (`feature_05.py:89`) without a UI flag beyond `implied_source`.
- **HAR physical is fixed-weight** (PROXY): `0.45/0.35/0.20` daily/weekly/monthly (`:47`), not Feature 3 OLS estimates.
- **Regime BTZ uses YZ rank, not Feature 4** (WRONG): `low_mask = yz_rank < 0.35`, `high = rank > 0.70` (`:104-106`). Spec conditions on `p_composite` from Feature 4.
- MISSING: cross-asset mode (single asset only), VSTOXX/VFTSE/JNIV and uploaded-IV support, display-mode selector (raw/variance/zscore exists in frontend `registry.js:78` but backend ignores it), component attribution is a single-date snapshot (`:113`), not a stacked time series.

### Feature 6: Connectedness
- DY core real (OK): BIC VAR(p) (`fit_var`, `:813-833`), Pesaran-Shin generalized FEVD, total/from/to/net, pairwise heatmap, network nodes/edges, Barunik-Krehlik 3-band frequency split, quantile Connectedness-at-Risk, VAR IRF with bootstrap bands.
- Rolling index is **not daily** (WRONG vs spec): step `len(logv)//300` (`feature_06.py:36`), ~300 points regardless of history; rolling loop always calls OLS `fit_var`, never `fit_var_ew`, even when EW is selected (`:38`).
- EW-VAR BIC accounting is suspect (WRONG): weighted-residual outer product without dof adjustment (`:1094`); lag comparisons under EW weighting are not on the same likelihood scale.
- MISSING: FEVD horizon/alert-threshold payload paths exist in code (`payload.get("fevd_horizon")`, hardcoded alert = top quartile `:67-68`) but the frontend alert-threshold/rolling-window selectors are not all honored; animated time-lapse network MISSING (static snapshot only).

### Feature 7: Multivariate/DCC Engine
| Spec item | State | Detail |
|---|---|---|
| Sample / EWMA / Ledoit-Wolf | OK | `covariance_methods` (`:792-808`): sample, EWMA with half-life lambda, LW-style shrinkage (closed-form intensity, diagonal target). |
| `dcc_proxy` | PROXY | `dcc = ewma.copy()` inside `covariance_methods` (`:809-810`). Real DCC is added later by the feature runner; the helper name lies. |
| Two-stage DCC-GARCH MLE | OK | Per-asset GARCH(1,1)-t via `arch`, then L-BFGS-B over `(a, b)` on the Engle likelihood (`dcc_garch_mle`, `:741-777`) with warm-start store. The genuine article. |
| DCC time series | WRONG | `dcc_correlation` is a 126d rolling Pearson of the selected pair (`feature_07.py:55`), not the DCC path (`dcc_correlation_path` exists in `performance.py` but is never exported to the chart). |
| Normal vs crisis | WRONG labels | "Normal" = first 75% of sample (`:29`); crisis = top-decile absolute-return days (`:31`). Not regime-probability or VIX>30 definitions from the spec. |
| Probability-weighted crisis | PROXY | Weights = rank of mean absolute return (`:37`), not Feature 4 `p_composite[high-vol]`. |
| DCC-MIDAS | PROXY | Static Beta-weighted monthly correlation matrix (`:1148-1169`), displayed but never used as the DCC long-run target. |
| Attribution/torsion/Fisher/condition history | OK | MRC attribution, min-variance portfolio, torsion factor split, Fisher-Z amplification, rolling condition number. Torsion factor labels are indices, not asset-loading descriptions. |

### Feature 8: Stress Testing
- Scenario stack real (OK): 4 historical presets with realized window shocks, parametric fallback, Mahalanobis + GraphicalLASSO analogs, VAR contagion IRF with bootstrap bands (120 realtime / 500 research), 20k/100k-path Monte Carlo stress VaR/CVaR, multi-scenario comparison.
- **Clayton copula computed but unused** (PROXY): theta/lower-tail dependence attached to reverse-stress rows (`feature_08.py:82-85`) while the shock vector stays linear (`delta = loss * Omega d / denom`, `:75`). The nonlinear `P(r | vol shock)` mapping in the spec never happens.
- **Adversarial is discrete search** (PROXY): best 30d window within Mahalanobis radius `c` (`analytics.py:1261-1279`), not projected-gradient continuous optimization.
- Arbitrary formulas: `recovery_time_days = 21 * vol_mult` (`feature_08.py:117`); GLASSO `alpha=0.1` fixed, not BIC-selected rho; analog grid steps 21d (may skip the closest window); VAR lag hardcoded 5 for IRF; 3 preset crises (COVID recovery, taper tantrum, EM crisis) MISSING.

### Feature 9: Vol Budget Monitor
- Lookahead fixed (OK): exposure uses one-step-ahead EWMA variance forecast shifted by 1 (`feature_09.py:61-62`); prior `rolling(21).std()` bug from `review.md` is gone. Verify before closing: rescale uses `scaling.shift(1)` on the gross leg (`:64`) and cost drag is netted (`:66-69`).
- Regime-conditional target real but expensive (OK/PROXY): calls full `run_regime` per invocation (`feature_09.py:24`), i.e. HMM+SJM+EW-HMM+Weibull on every budget request. No cache. `regime_targets` string from the frontend (`registry.js:137` `"low:0.08,..."`) is never parsed; the dict default (`:26`) always wins.
- Kelly uses 252d historical mean (`:57`), not the Feature 5 BTZ-implied return the spec requires (WRONG label: output key `btz_implied_return` holds a historical mean).
- MISSING: GARCH/EWMA forecast-source selector (DCC only), weekly/signal rebalance triggers (daily-ish only), flat-bps vs Almgren-Chriss side-by-side, fixed-vs-regime backtest comparison leg.

---

## 4. Use open source that is already installed

Already importable (verify with `python3.11 -c "import arch, hmmlearn, sklearn, statsmodels"`; `arch`, `hmmlearn`, `sklearn`, `scipy`, `statsmodels` are all exercised by the code):

| Hand-rolled today | Replace with | Why |
|---|---|---|
| MCS elimination loop (`analytics.py:539-558`, 150-200 reps) | `arch.bootstrap.MCS` / `SPA` / `StepM` | Hansen-Lunde-Nason test with correct bootstrap distribution and p-values; removes the range-of-means shortcut. HAR/Feature 2 share one implementation. |
| HAR/HAR-X OLS-HAC (`ols_table`, `ols_hac_fast`) | `statsmodels.regression.linear_model.OLS` + `cov_type='HAC'` with `cov_kwds={'maxlags': h}` | Tested NW covariance, automatic bandwidth hooks, `f_test` for joint jump/leverage blocks. |
| BTZ Hodrick SE (`hodrick_se`, `:981-994`) | `statsmodels` HAC with `maxlags = horizon-1` (Hodrick 1992 = Newey-West with rectangular kernel) or `linearmodels` | Removes a second SE implementation; F05/F03 agree by construction. |
| Stationary bootstrap indices (`stationary_bootstrap_jit`) | `arch.bootstrap.StationaryBootstrap` / `MovingBlockBootstrap` | Correct Politis-Romano resampling for HAR bands, DM tests, half-life CIs. |
| Hand-rolled KS p-value (`feature_02.py:84-89`, 5-term series) | `scipy.stats.kstest` / `statsmodels.stats.diagnostic.kstest_normal` | Tested tail accuracy; the 5-term exponential sum truncates early under small n. |
| Quantile CoR (`connectedness_at_risk`, `:1129-1145`) | keep `sklearn QuantileRegressor`, add `statsmodels QuantReg` CIs | Point CoR exists; CIs and coefficient table missing. |
| Weibull duration (`weibull_duration_model`, `:1047-1073`) | `lifelines.WeibullFitter` (new dep, needs approval) or keep | Censored current-regime duration, CIs, hazard bands. Current fit ignores right-censoring of the running spell. |
| VAR BIC (`fit_var`, `:813-833`) | `statsmodels.tsa.api.VAR` with `.select_order()` / `.fit()` + `fevd`/`irf` | Tested lag selection, generalized FEVD, IRF CIs; kills the `fit_var_ew` BIC-scale question. |
| DCC time-series export | the already-computed `dcc_correlation_path` in `performance.py` | The 3-D path is computed inside MLE and thrown away; persist and chart it instead of rolling Pearson. |
| GraphicalLASSO `alpha=0.1` (`:1243`) | `sklearn.covariance.GraphicalLassoCV` | BIC/CV-selected rho per the spec. |

Worth adding (new dependencies, need approval):

| Library | For | Notes |
|---|---|---|
| `lifelines` | F04 Weibull durations with censoring | Pure Python, small. Fixes the completed-spell-only bias. |
| `ruptures` | F02/F03 break overlays | Optional; only if break-date search becomes a real input. |

Frontend: `@tanstack/react-query` is installed (per Research review); use it for the run hook. Charts already standardize on `recharts` for workbench cards plus one `react-plotly.js` surface on the landing page; keep it that way (one 3-D exception, everything else `recharts`).

---

## 5. Frontend review

- **No data flow** (B1). All 9 feature pages pass only `featureId` + `sections`; `VolatilityV2Workbench` (`customPagePrimitives.jsx:1316`) supports `response`/`onRun` but never receives them.
- **Duplicated contract**: `components/volatility-v2/registry.js` re-declares every feature's inputs/defaults by hand. Backend `contracts.py` carries only `{title, required_data, outputs}` with no inputs/defaults, so the frontend cannot fetch a manifest. Drift already exists: F01 overnight-gap treatment, efficiency benchmark, FX/commodity universe; F02 FIGARCH-d, APARCH-delta, break date, weekly frequency; F03 estimator-input/horizon-grid/confidence; F05 display-mode/z-lookback mapping; F06 alert-threshold semantics; F08 preset names (`gfc_2008` vs backend `gfc`, `covid_2020` vs `covid`); F09 `regime_targets` string vs backend dict, `gross_exposure_constraint` vs `gross_exposure_cap`, `cost_bps` vs `explicit_bps`. Fix: extend `contracts.py` with inputs/defaults (or a `/features` manifest with them) and render from it; keep only presentation hints (chart type, rank) in the frontend.
- **Fake Spark** (B3): `Spark` (`:705-708`) renders `sin(i*.7)` decor on every metric card. `HeaderSparkline` (`:530-539`) is data-driven and fine; `Spark` is not.
- **Surface flatten** (B3): `SurfaceGrid` (`:1218-1220`) squeezes the 49-point synthetic surface into a 2-D heatmap with no axis labels; landing `GarchVisual` is a hardcoded sine surface. Either fit a real surface or label both "illustrative".
- **Landing hardcoded data**: `page.js:55-93` (`series`, `harForecast`, `corrMatrix`, `stressBars`, `budgetRows`) plus hero pills `V01 Yang-Zhang 18.4% / V04 Crisis 14% / V06 Spillover 72` (`:960-964`) are constants. No fetch, no timestamp, no "illustrative" tag. A visitor reads them as live outputs.
- **Unreachable UI beyond Run**: `file_path`-style inputs are absent here (good), but `weights` textareas accept JSON the backend silently ignores when it is a string (B2); `forecast_horizons`, `har_variants`, `estimation_window`, `return_frequency`, `display_mode`, `cross_asset_mode`, `network_layout`, `stress_period` selectors have no backend path or are ignored. Misleading options in the Research sense.
- `customPagePrimitives.jsx`: ~1,500 lines with the `volStyles` CSS-in-JS blob (`:1473+`), 14+ renderer branches (`VolRenderer`, `:640-669`), fallback-key reshaping (`pickData`), table truncation at 300 rows / 14 columns (`VolTable`, `:1248-1289`), network cap at 80 edges (`:1065`). Split into Workbench, ConfigCurtain, OutputCard, renderers, and a CSS module; cut cross-type `fallbackKeys`; paginate don't truncate.
- No loading/error/empty/cancel states for long jobs beyond the fake progress timer (`run`, `:1402-1427`: `setInterval` to 92% regardless of server progress), because nothing runs yet. GARCH-20, HMM-20-restart, and 100k-path MC need real progress + cancel.

---

## 6. Codebase-wide pattern (same issues across the V2 modules)

Seen while reviewing; each deserves the same pass.
- **Duplicated data loaders**: `volatility_v2/core/data_loader.py` (93 lines, Polars pushdown + joblib cache) is one of several per-module loaders (Research review counts seven `data_loader.py` / seven `analytics.py`). Fix: one shared `app/services/shared/market_data.py`; modules keep only their analytics.
- **Duplicated workbenches**: `components/volatility-v2/customPagePrimitives.jsx` (~1,500 lines) is one of several per-module primitives files with its own tokens and generic renderer. Fix: one shared Lab workbench + renderer registry; per-module files only declare sections.
- **Legacy vs V2 volatility split**: `backend/app/services/volatility_intelligence.py` (`run_volatility_intelligence`, `compute_vol_dna/surface/edge/traps/skew/dispersion/clusters`) still serves `backend/app/api/labs.py` Vol endpoints alongside Volatility V2. No import or contract links the two. Decide: retire, re-export, or cross-link; do not leave two "volatility" APIs diverging silently.
- Backend deps are ranges, no lock (Research P17 gap, still open).
- `review.md` inside `volatility_v2/` marks prior gaps resolved; several entries overstate status (DM table "tournament heatmap", Nyblom "stability", FIGARCH-d "proxy", cross-feature regime sharing "broader work" while F05/F07 ship rank substitutes). Update it after fixes, same as Research `DONE.md`.
- `contracts.py` (31 lines) is real but thin: no input schema, no defaults, no output field lists. The registry normalizes `feature_01`/`feature-01`/`01` (good), but nothing validates payloads before the estimators run.

---

## 7. Remaining work, by type, in order

| # | Type | Work | Size |
|---|---|---|---|
| 1 | Wiring | Pages pass `response`/`onRun` via React Query against `/api/labs/volatility/v2/feature/{id}/run`; heavy features (02, 04, 08, 09) via job transport with progress/cancel | S |
| 2 | Data integrity | 422 on unknown tickers (`analytics.py:287-294`); 422 or physical-only mode on missing VIX (`feature_05.py:37-40`); stop zero-filling HAR-X macro (`feature_03.py:37-39`) and F06/F04 fallbacks; parse-or-reject string `weights` (`analytics.py:1482-1491`) | S |
| 3 | Correctness (F1) | Crypto/FX YZ branch warning or 24/7 adjustment; `_rolling_var_np` ddof review; OGF auto-routing; missing input selectors (overnight treatment, benchmark, calendars) | S |
| 4 | Correctness (F2) | Real N x N DM tournament with p-values (`feature_02.py:153`); score Realized-GARCH inside MCS; per-distribution PIT; real Nyblom/Hansen or relabel; MLE-or-fixed FIGARCH d; fix APARCH-delta percentile; expose break-date/weekly/coverage inputs | M |
| 5 | Correctness (F3/F5) | HAR-X VRP from Feature 5, configurable ACSV universe, jump-disagreement time series, honor estimator/horizon-grid/confidence inputs; F05 fixed-weight HAR-physical to estimated, Feature-4-conditioned BTZ, cross-asset + non-US IV + display-mode support | M |
| 6 | Correctness (F6/F7) | Daily rolling connectedness + EW-aware rolling loop, EW-VAR BIC scale check, honored horizon/threshold inputs; F07 export the real `dcc_correlation_path`, regime/VIX crisis definitions, Feature-4-weighted crisis corr, integrated DCC-MIDAS target | M |
| 7 | Feature 8/9 | Copula-conditioned reverse stress, gradient (or labeled discrete) adversarial, BIC GLASSO rho, full 7-preset library, non-arbitrary recovery time; F09 cache the regime call, parse `regime_targets` string, BTZ-implied Kelly return, forecast-source/trigger/cost-comparison options | M |
| 8 | Tests | Golden-number tests per estimator (Parkinson/GK/RS/YZ against closed-form fixtures), `arch` cross-check for one GARCH fit, DM/MCS smoke on simulated DGP, look-ahead guard (unknown ticker 422, no-synthetic-VIX, ex-ante scaling), contract-vs-registry-vs-frontend key parity test | M |
| 9 | Frontend | Manifest-driven inputs; JSON-weights parsing; drop sine `Spark`; label or replace synthetic surface; remove cross-type `fallbackKeys`; live (or labeled-illustrative) landing data; loading/error/cancel; split primitives; paginate tables | M |
| 10 | Cleanup | Shared data loader + shared Lab workbench across V2 modules; retire or link legacy `volatility_intelligence.py`; flesh out `contracts.py` with inputs/outputs; update `review.md`; pin deps | L |

Recommended next step: items 1 and 2 together (small, and they make the module both usable and honest), then 4 with tests from 8 alongside.

---

## 8. Addendum (verified 2026-10-05)

These came from a second read of the code and were not in the first pass. Read [V2_REBUILD_PLAYBOOK.md](V2_REBUILD_PLAYBOOK.md) before fixing; frontend work (section 5) is reserved for Claude. Blockers B1-B3 in section 2 were re-checked and are still open (no commits to this module since the review).

| # | Area | Finding | Where |
|---|---|---|---|
| A1 | In-sample "forecast" scoring (F02) | Every GARCH model is fitted on the **full sample** and its fitted conditional variance is scored with QLIKE/RMSE against future realized variance (`shift(-21)`) on the same dates. The winner, the MCS membership and the Diebold-Mariano table are all in-sample fit comparisons, not forecast comparisons. Use a rolling or expanding refit (`arch` `fit(last_obs=...)` + `forecast(start=...)`) and score only true out-of-sample forecasts. | `analytics.py:618-660`, `feature_02.py:153` |
| A2 | Mislabeled R² (F03) | HAR variants are fitted by OLS on the full sample and predicted on the same rows, but the output field is `r2_oos`. It is in-sample R². The QLIKE weights for the HAR combination (`:95-96`) inherit this. Do a rolling-window OOS evaluation or rename the field. | `feature_03.py:57-66,90` |
| A3 | Zero-filled regressors | Besides B2's macro `fillna(0)`, HAR predictions use `x.ffill().fillna(0)` for every variant, and missing returns in `analytics.py:599,793` become `0.0`. Zeros in variance regressions understate vol. | `feature_03.py:59`, `analytics.py:599,754,793` |
| A4 | Unbounded caches | `_GARCH_CACHE` keys on an md5 of the series and never evicts; every new ticker/window adds 20 fitted models' variance maps to process memory. | `analytics.py:615` |
| A5 | Errors | 22 `except Exception` blocks; GARCH fit failures become a row with `error` text, so a 20-model suite where most models fail still returns `status: ok`. Report fitted/failed counts in `meta` and set `status: warning`. | `core/*.py` |
| A6 | API | Runs are synchronous `asyncio.to_thread`; F02 (20 MLE fits), F04 (HMM restarts) and F08 (100k-path Monte Carlo) need background jobs (Studio `JobStore` pattern). The route takes a raw `Dict` with no validation. | `api/volatility_v2.py:23-26` |
| A7 | Docs | Six stale self-audit files (`AUDIT.MD`, `AUDIT 2.MD`, `review.md`, `speed upgrades.md`, `speed upgrade 2 .md`, `vol frontend upgrades.md`) plus empty `schemas/`, `utils/`. Reconcile into one `DONE.md` with a file-fate table. | `volatility_v2/` |
| A8 | Tests | Still zero. Add golden numbers (Yang-Zhang/Parkinson/GK on a fixed OHLC fixture; GARCH(1,1) parameters vs `arch` reference; HAR betas on simulated data), an OOS-only guard for A1/A2, and an unknown-ticker 422 test. | `backend/tests/` |
