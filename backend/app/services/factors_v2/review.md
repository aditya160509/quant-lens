# Factors V2 Full Spec Compliance Audit

## Remediation checklist (2026-07-13)

- [x] Confirmed the Factors V2 router is mounted under `/api/labs/factors/v2`; the original audit finding was stale.
- [x] Removed the unreferenced 3,115-line `FACTOR_FEATURES_MASTER.py` duplicate after repository-wide reference verification.
- [x] Added an explicit `features/__init__.py` package boundary.
- [x] Fixed legitimate single-factor F01 requests, compacted time-series output, corrected regression CI keys, and preserved every factor's sector contributors.
- [x] Added Newey-West heteroskedasticity and autocorrelation consistent standard errors to overlapping-horizon predictive regressions.
- [x] Replaced F02's factor-return self-regression with actual weighted holding returns when local prices exist.
- [x] Removed fabricated sinusoidal rolling exposures and hash-derived comparison-portfolio exposures.
- [x] Added actual rebalancing-history exposure snapshots; unavailable history now returns an empty result instead of invented data.
- [x] Corrected F03 date-range handling, frequency resampling, residual reconciliation, and annualization.
- [x] Fixed F05 rolling windows to use every selected horizon, added true bootstrap IC intervals, corrected linear half-life algebra, and removed the max-IC-horizon half-life proxy.
- [x] Corrected F06 long-short spread differential percentiles and made composite weights explicit/configurable.
- [x] Replaced F07's shifted-index pseudo Monte Carlo with stationary block-bootstrap equity paths.
- [x] Removed fabricated perfect quintile returns and moved forward-return formation to the next session to prevent same-close execution bias.
- [x] Fixed F08 so permitted DCC requests actually drive the primary covariance result.
- [x] Replaced F09's discontinuous $100M impact switch with one continuous square-root model and tied liquidation time to configured turnover.
- [x] Added manual expected returns, gross limits, position limits, and collision-free optimizer warm-start keys to F10.
- [x] Added F11 impulse-response paths at 1/5/10/21 days and historical 5th/95th percentile factor ranges.
- [x] Corrected F13's default drift threshold and stopped labeling return persistence as true cross-sectional IC.
- [x] Expanded F14 PDF content, contact/disclaimer sections, and JSON-formatted audit output.
- [x] Added focused mathematical regression tests and complete F01-F14 smoke validation.
- [ ] Requires external data: FX conversion histories, true point-in-time fundamentals/characteristics, benchmark constituent histories, and missing optional AQR/macro feeds.
- [ ] Requires infrastructure: durable cross-feature portfolio state, saved alert history, email/webhook workers, scheduled refresh, and page-aware document rendering.
- [ ] Intentionally deferred as disproportionate interactive compute: DCC maximum-likelihood estimation, full nested walk-forward optimization, per-request VAR coefficient bootstraps, and full-universe historical characteristic reconstruction. These belong in offline cached research jobs.

---

## 1. Lines of Code Summary Table

| Component | Files | Lines |
|---|---|---|
| Core analytics | `core/analytics.py` | 777 |
| Core data loader | `core/data_loader.py` | 415 |
| Core performance | `core/performance.py` | 575 |
| Core contracts | `core/contracts.py` | 138 |
| Feature F01 | `features/feature_01.py` | 133 |
| Feature F02 | `features/feature_02.py` | 244 |
| Feature F03 | `features/feature_03.py` | 256 |
| Feature F04 | `features/feature_04.py` | 323 |
| Feature F05 | `features/feature_05.py` | 333 |
| Feature F06 | `features/feature_06.py` | 232 |
| Feature F07 | `features/feature_07.py` | 250 |
| Feature F08 | `features/feature_08.py` | 183 |
| Feature F09 | `features/feature_09.py` | 114 |
| Feature F10 | `features/feature_10.py` | 211 |
| Feature F11 | `features/feature_11.py` | 203 |
| Feature F12 | `features/feature_12.py` | 215 |
| Feature F13 | `features/feature_13.py` | 146 |
| Feature F14 | `features/feature_14.py` | 188 |
| **Feature subtotal** | **14 files** | **3,031** |
| FACTOR_FEATURES_MASTER | `features/FACTOR_FEATURES_MASTER.py` | 3,115 |
| 14 stub re-export files | `features/{descriptive_name}.py` | 14 × 1 |
| Package init | `__init__.py` | 1 |
| API router | `api/factors_v2.py` | 164 |
| **Total backend** | **~33 files** | **~8,230** |
| **Deduplicated (excl. master + stubs)** | **19 files** | **5,101** |

---

## 2. Per-Feature Audit (F01–F14)

### F01 — Factor Valuation Spread Monitor (spec p.43-71, impl `feature_01.py`)

**Spec targets:** Factor selector (Value/Momentum/Quality/Low-Vol/Size/Growth/Investment/Profitability), percentile lookback window (3/5/10yr/custom), universe filter (full/GICS sector), characteristic-to-measure spread, historical comparison anchors (GFC 2008, COVID 2020, Rate Shock 2022, Liberation Day 2025), display mode (snapshot/time series/dashboard). Outputs: live gauge panel, historical percentile time series, expected return regression with 90% CI, valuation correlation matrix, alert system, cross-sector valuation spread table, crisis anchor table.

**Implemented:** Covers 5 factor aliases from DEFAULT_FACTORS (`value_pb`, `momentum_12_1`, `quality_roe`, `low_vol`, `size`). Uses cross-sectional quintile spread on characteristic panel. Crisis anchors for 4 events. Expected return via `predictive_regression()`. Sector breakdown from quintile sector spreads. Alerts for stretched/cheap thresholds.

**Gaps:**
- Only 5 factor types implemented vs ~12 in spec. Missing: value_ep, growth, investment, profitability as standalone selectors, custom user-defined factors (F01-05: `feature_01.py:20-24`).
- Lookback defaults to 2520 (10yr) but spec requires 3/5/10yr/custom options (F01-06: `feature_01.py` doesn't expose percentile_lookback as a proper UI dropdown).
- Universe filter (full/GICS sector) is not an input option; sector breakdown is computed post-hoc but universe can't be narrowed pre-computation (F01-27: `analytics.py:394-405`).
- Historical comparison anchors are hardcoded as 4 events; spec says "auto-flag to GFC 2008, COVID Mar 2020, rate shock Oct 2022, Liberation Day Apr 2025" — implemented correctly (F01-09: `feature_01.py:9-14`).
- Display mode not supported; always returns all outputs simultaneously.
- Factor valuation correlation matrix is just `series.corr()` — spec requests a "Heatmap showing which factors are simultaneously stretched" (F01-09: `feature_01.py:49-50`).
- Alert system only supports in-app payload delivery; spec requires "email or dashboard notification" (F01-06: `feature_01.py:76-83`).

**Bugs/Issues:**
- `feature_01.py:20`: Bug — `requested_factors` always falsy check `if not requested_factors or len(requested_factors) <= 1`. If user sends `factors = ["value_pb"]`, this overwrites to DEFAULT_FACTORS. A single-factor query is a legitimate use case.
- `feature_01.py:48`: `series.reset_index().to_dict("records")` for percentile_series chart — this dumps the entire time series (potentially thousands of rows) into a single chart field. Should use `compact_series`.
- `feature_01.py:59-60`: Expected return CI hardcodes fallback values `_expected_return_value(r) +/- 0.035` when `expected_return_ci_low_90`/`ci_high_90` are None. The actual `predictive_regression` output uses keys `ci_90_low`/`ci_90_high` (analytics.py:457-458). The feature_01.py references `expected_return_ci_low_90` which doesn't exist in the regression output — this fallback path will always fire.
- `feature_01.py:68-69`: `rows[0].get("sector_contributors", [])` — only returns first factor's sector contributors. If multiple factors are requested, all sector tables show the same first factor.
- `analytics.py:389`: `pd.qcut(chars[f].rank(method="first"), 5, ... )` — `rank(method="first")` + `qcut` is redundant; `qcut` already handles ties. `duplicates="drop"` means if ties prevent 5 equal bins, fewer bins will be created silently.
- Expected return regression uses historical proxy spread (FF factor cumulative return) as signal, not the actual cross-sectional valuation spread. The spec says "Regression-implied 12-month expected return based on today's spread percentile" but the implementation regresses the FF cumulative return against itself lagged.

**Score: 5/10**

---

### F02 — Factor Exposure Decomposition (Portfolio X-Ray) (spec p.74-108, impl `feature_02.py`)

**Spec targets:** Portfolio input (manual/CSV/JSON/equal-weight/long-short), factor model (FF3/FF5/Carhart/extended), benchmark (SP500/R1K/R2K/MSCI/custom), exposure methodology (characteristic/return-based/both), exposure type (raw/active/z-score), estimation window (6-60mo), rebalancing date, neutralization (raw/sector-neutral), comparison mode (up to 3 portfolios). Outputs: factor exposure bar chart with 95% CI, active exposure chart, characteristic vs return divergence, holdings-level factor contribution, exposure heatmap, unintended exposure detector, tilt summary, rolling exposure time series, factor exposure budget, exposure surprise table.

**Implemented:** Characteristic-based exposures from z-scored fundamentals. Return-based exposures via OLS on FF factor returns. Divergence flagged >0.3 sigma. Unintended exposure detector at 0.4 sigma threshold. Stock-level divergence table. Tracking error budget. Multi-portfolio comparison. Plain-language tilt summary.

**Gaps:**
- Only characteristic-based + one proxy return method. True return-based methodology (time-series OLS of each stock's daily returns on factor returns) is approximated by running OLS on the portfolio proxy (equal-weighted average of factor returns) once, not per-stock (`feature_02.py:36-37`).
- Estimation window parameter is accepted but the OLS is always run on the full tail; no per-stock windowed regression (`feature_02.py:35`).
- 95% confidence bands on exposure bar chart are not implemented. Standard errors from OLS are returned but no confidence interval constructed (`feature_02.py:38`).
- No sector-neutral exposure toggle. The `mandate_factors` parameter checks mandate compliance but doesn't neutralize exposures (`feature_02.py:47-58`).
- No benchmark selection UI parameter; comparison portfolios are a separate feature using ticker-level data, not benchmark-relative active exposure (`feature_02.py:214-243`).
- Rolling exposure time series is a fake deterministic drift proxy generated from sinusoidal noise (`feature_02.py:120-138`). The spec requires "month-by-month evolution of portfolio factor loadings over history" from actual rebalancing history.
- Holdings upload (CSV/JSON) not fully implemented; only inline `holdings` parameter or auto-generated sample (`feature_02.py:20`).

**Bugs/Issues:**
- `feature_02.py:20`: Auto-generated sample holdings use `chars["Ticker"].head(30)` — but `head(30)` selects arbitrary tickers, not the most representative ones.
- `feature_02.py:37`: `port_proxy = rets.mean(axis=1)` — this is an equal-weighted factor return composite, not the actual portfolio return. The return-based exposure is then contaminated by the factor model's own returns.
- `feature_02.py:44`: `ret_map.get(proxy, 0.0)` — if the proxy factor (e.g., "HML") appears in ret_rows but the factor name used as key doesn't match, this silently returns 0.
- `feature_02.py:75`: Rolling heatmap generation uses sinusoidal noise + linear drift (`0.12 * phase`, `0.05 * sin(...)`) — this is cosmetic fake data that violates the spec's requirement for actual historical evolution.
- `feature_02.py:214-243`: Multi-portfolio comparison for missing tickers uses deterministic hash-based exposure scaling `sum(ord(ch) for ch in ticker)` — essentially random noise pretending to be data.

**Score: 4/10**

---

### F03 — Factor Return Attribution (spec p.111-145, impl `feature_03.py`)

**Spec targets:** Portfolio history upload, attribution period (10yr), attribution model (factor-based/Brinson-Fachler/hybrid), factor model (FF3/FF5/Carhart/custom), frequency (daily/weekly/monthly/quarterly), benchmark, transaction cost model (flat bps or Kyle lambda), carryover effect toggle. Outputs: attribution waterfall chart, cumulative contribution area, factor return contribution table with t-stats, IR by component, Brinson-Fachler table by GICS sector, carryover effect report, factor hit rate table, best/worst periods, rolling IR, active return waterfall.

**Implemented:** Factor contribution table with t-stats. Brinson-Fachler sector attribution via `sector_brinson_fachler()` with allocation/selection/interaction effects. Rolling IR (12/36 period). Best/worst period detector. Carryover proxy via autocorrelation fallback. Stacked waterfall.

**Gaps:**
- Rebalancing history upload is accepted but only used for carryover; no holdings interpolation between dates (`feature_03.py:91-150`).
- Transaction cost model not integrated into attribution; only flat carryover analysis. Spec requires explicit bps cost decomposition (`feature_03.py` never reads `transaction_cost_model` from payload).
- Brinson-Fachler uses `sector_brinson_fachler()` which computes sectors from the characteristic panel's sector metadata, not from an input benchmark. The spec requires the benchmark parameter for active return decomposition (`feature_03.py:27`).
- Cumulative contribution area chart not implemented as stacked area; just `contrib.cumsum()` records (`feature_03.py:60`).
- True carryover effect requires per-holding snapshots across rebalancing dates; fallback is IC autocorrelation, which is a completely different concept (`feature_03.py:153-165`).
- Factor hit rate table returns factor-by-factor hit rate but without the periods breakdown the spec asks for (`feature_03.py:71`).

**Bugs/Issues:**
- `feature_03.py:15`: `raw_rets = factor_returns(payload).dropna().tail(requested_window)` — uses last N days of data, not actual calendar period. Attribution period parameter should be start/end dates, not `window_days`.
- `feature_03.py:19`: `rets = raw_rets.resample("ME").sum() if frequency == "monthly"` — the `hasattr(raw_rets.index, "freq")` check is likely false for arbitrary factor return indexes, so monthly resampling may silently not happen.
- `feature_03.py:23`: `weights = payload.get("factor_exposures") or {c: 1 / len(rets.columns) for c in rets.columns}` — factor exposures from Feature 2 are not imported; equal weights are always used.
- `feature_03.py:27`: `residual = brinson["active"].reindex(total.index).fillna(0) - total.reindex(brinson["active"].index).fillna(0)` — residual is computed twice, first from `rets.mean(axis=1) - total`, then overwritten by Brinson active minus total. The logic is confusing and the first computation is wasted.
- `feature_03.py:35`: `ir_factor = float(total.mean() / total.std() * np.sqrt(252))` — uses daily returns even when frequency is monthly, creating wrong annualization factor.
- `feature_03.py:65`: `ir_by_component` chart only has 2 components (factor_harvesting, selection_residual). Spec requires "IR for selection vs. factor component to distinguish stock-picking skill from factor harvesting."

**Score: 4/10**

---

### F04 — Probabilistic Regime Analysis (spec p.148-179, impl `feature_04.py`)

**Spec targets:** Regime model selection (rules/HMM/GMM/composite), HMM states (2/3/4), VIX threshold (default 25), yield curve metric (2s10s/3M10Y), factor scope, factor timing model signals (valuation spread/factor momentum/crowding/macro composite), factor momentum params (ranking/holding period/L-O vs L-S), statistical significance toggle. Outputs: probabilistic regime timeline, live regime probability with 30/90d trend, factor return heatmap by regime with t-stats, factor Sharpe by regime, factor momentum backtest, regime transition matrix, timing regression output, factor seasonality, portfolio regime sensitivity.

**Implemented:** Three-model composite (rules + HMM + optional GMM). Log-space probability averaging with rolling volatility IC weights. Factor timing regression. Factor momentum backtest. Calendar-month seasonality. Portfolio regime sensitivity. Transition matrix.

**Gaps:**
- Rules-based model uses VIX > threshold, yield curve < 0, 10y > 4.5% — all equal weighted. The spec requires using VIX threshold + yield curve slope + real interest rate level, but the implementation doesn't use real rates at all (`feature_04.py:22-26`).
- GMM on rolling 63-day factor covariance is correctly implemented but only runs in research mode by default — meets spec's realtime constraint (`feature_04.py:42-58`).
- Factor timing signals from spec: valuation spread, factor momentum, crowding score, macro composite. Implemented only: stress probability, factor momentum cross-section, volatility state — missing valuation spread and crowding score (`feature_04.py:204-207`).
- Factor momentum params (ranking period, holding period, long-short vs long-only) are not exposed. The momentum backtest uses a fixed lookback of 63d (`feature_04.py:259`).
- Statistical significance toggle not implemented.
- No factor seasonality by "calendar month for each factor" — only average daily return by month (`feature_04.py:277-287`).
- Regime sensitivity output computes portfolio return by regime using `factor_exposures` param, but the spec says "based on current exposures" which should come from F02 (`feature_04.py:290-322`).

**Bugs/Issues:**
- `feature_04.py:72`: `dominant = pd.cut(rules["stress"], ...)` — labels set as "expansion", "transition", "stress" but only 2 probabilities exist. The labels for bins [-0.01, 0.34, 0.67, 1.01] produce 3 groups from a [0,1] range, which is fine, but the labels imply the spec's 4-state model (expansion, recession, transition, liquidity crisis) has been collapsed to 3.
- `feature_04.py:73`: `cond = rets.groupby(dominant, observed=False)` — `observed=False` requires pandas 1.1+ and categorical groups, but `dominant` is a CategoricalIndex so this is fine.
- `feature_04.py:130-136`: HMM and GMM state-to-binary mapping uses 21-day rolling vol to identify the "stress" state. This is reasonable but fragile: if the highest-vol state coincides with an expansion regime by luck, the mapping inverts.
- `feature_04.py:148-163`: Weighted log-space averaging uses Spearman correlation of each model's stress probability with lagged realized vol to set weights. If all correlations are negative, it falls back to equal weights. This is a novel research contribution not specified in the spec.

**Score: 6/10**

---

### F05 — Alpha Decay and Factor Half-Life (spec p.183-215, impl `feature_05.py`)

**Spec targets:** Factor selector (up to 10 simultaneously), decay horizons ([1,5,10,21,42,63,126,252]), IC method (Pearson/Spearman/sector-neutral/beta-neutral), decay model (linear/exponential/hyperbolic/all), rolling sub-window (252/504/756), universe filter (full/GICS sector/size bucket), transaction cost input (bps), ICIR toggle. Outputs: IC decay curve with 95% bootstrap bands, fitted decay model overlay with R-squared, half-life with 90% CI, optimal rebalance frequency, rolling half-life time series, cross-sector decay, ICIR by horizon, factor signal power radar, post-2015 acceleration test.

**Implemented:** Full spec horizon set. Three decay models with curve fitting. Bootstrap 95% CI for half-life. Rolling half-life time series. Post-2015 acceleration test. Signal power radar. ICIR by horizon. Cross-sector decay (via dispersion adjustment). Multi-factor power radar.

**Gaps:**
- IC method: only Spearman rank IC is used (via `vectorized_rolling_ic_matrix`); Pearson IC, sector-neutral IC, beta-neutral IC not implemented. The spec requires all four (`feature_05.py:28`).
- Rolling sub-window for half-life is hardcoded at 252; payload's `window_days` is only used for the data length cap, not the sliding window size (`feature_05.py:52`).
- Universe filter (size bucket, full/GICS sector) not supported as input. Cross-sector decay is computed via dispersion adjustment, not by actually running the decay analysis on sector-subsets (`feature_05.py:222-250`).
- Optimal rebalance frequency cost-benefit uses hardcoded `portfolio_vol=0.15` fallback and doesn't integrate with actual transaction cost model from F07 (`feature_05.py:58-60`).
- Bootstrapping for IC mean CI uses normal approximation (`1.96 * se`) instead of actual bootstrap resampling (`feature_05.py:98-105`). The bootstrap_samples parameter is only used for half-life CI, not IC CI.

**Bugs/Issues:**
- `feature_05.py:31-37`: IC series construction: `ic_matrix[idx]` is transposed relative to the batched_forward_sums output. `batched_forward_sums` returns shape `(hcount, n)` where axis 1 is time; `vectorized_rolling_ic_matrix` expects the same shape. The indexing `ic_matrix[idx]` along axis 0 yields one horizon's IC across time — correct.
- `feature_05.py:42`: `_fit_decay(x, y)` is called once with x=horizons array and y=mean_ic array. This fits across only 8 data points (one per horizon). The spec describes fitting the decay curve to `IC(h)` across all 8 horizons — which is what happens, but 8 points for 3-parameter nonlinear optimization is extremely fragile and explains the tight bounds in `optimize.curve_fit`.
- `feature_05.py:52`: Rolling half-life: `sub_y = [float(np.nanmean(ic_matrix[hidx, idx0:end])) for hidx in range(min(4, ic_matrix.shape[0]))]`. This only uses the first 4 horizons (1, 5, 10, 21) for the rolling half-life, regardless of what horizons the user requested. The spec shows all 8 horizons in the decay curve.
- `feature_05.py:277`: Multi-factor radar computes half-life as `horizons[int(np.nanargmax(np.abs(mean_ics)))]` — picks the horizon with highest absolute mean IC as a "half-life proxy." This is not a half-life.
- `feature_05.py:291`: Linear half-life formula: `abs(float(y[0] / (2 * coef[0])))` — this is incorrect. The spec says "solve for the horizon h* at which IC(h*) = 0.5 * IC(1)". For linear model IC(h) = a - b*h, solving a - b*h* = 0.5 * (a - b) gives h* = (a - 0.5*(a-b))/b = (0.5a + 0.5b)/b. The code does `y[0] / (2*coef[0])` where `y[0]` is the first actual IC value not a. This is off by the intercept.

**Score: 5/10**

---

### F06 — Factor Crowding Monitor (spec p.218-247, impl `feature_06.py`)

**Spec targets:** Factor selector (any factor or portfolio), crowding metrics toggle (valuation spread/return autocorrelation/concentration HHI/bid-ask spread trend), composite method (equal-weight/PCA/user-defined), historical percentile lookback (3/5/10yr), alert threshold, crash probability conditioning toggle. Outputs: crowding composite gauge 0-100, crowding time series (10yr), individual metric breakdown radar, crash probability table (1/3/6mo), factor crowding league table, crowding percentile heatmap overlay, deleveraging risk score, crowding vs forward return scatter.

**Implemented:** 4-metric composite (valuation spread percentile, return autocorrelation percentile, concentration HHI, bid-ask spread proxy via Roll+Amihud). Crash probability via Bayesian beta-binomial. Crowding league table. Forward-return scatter with regression. Deleveraging risk score. Crowding return overlay with event detection.

**Gaps:**
- Composite score method: only equal-weight used; PCA and user-defined weights not implemented (`feature_06.py:39-40`).
- Historical percentile lookback is not user-configurable; defaults to full history from the data (`feature_06.py:36`).
- Crash probability conditioning on liquidity regime is not implemented. The crash table uses a simple current-score proximity bucket (`feature_06.py:99-127`).
- Crowding percentile heatmap overlay (factor return chart with crowding percentile colored in background) is approximated as time series + event annotations, not as an overlaid heatmap (`feature_06.py:51-63`).
- Bid-ask spread trend is computed from local OHLCV data (Roll 1984 + Amihud 2002). The spec requires external data as optional; the realtime constraint says "bid-ask spread trend and alternative-data proxies are not included in the realtime composite" but the code includes it by default anyway (`feature_06.py:37`).

**Bugs/Issues:**
- `feature_06.py:36`: `crowd_val = 100 - val_pct if factor in {"value_pb", "quality_roe", "profitability"} else val_pct` — this inverts the valuation percentile for value/quality/profitability factors based on an undocumented assumption about which factors are "cheap when spread is low."
- `feature_06.py:39`: `composite = float(np.mean(composite_inputs))` — simple average of up to 4 metrics. If one metric is NaN (e.g., spread_proxy fails), the remaining metrics re-weight implicitly. This is undocumented behavior.
- `feature_06.py:99-127`: Bayesian crash table uses prior Beta(1, 9) which encodes a 10% prior crash probability. The `credible_low_90` uses `stats.beta.ppf(0.05, ...)` — should be 0.025/0.975 for 95% CI if labeled "90% credible interval". Mixed conventions.
- `feature_06.py:130-133`: `_roll_spread` uses `2 * sqrt(max(0, -cov_series))`. If autocovariance is positive (common for trending series), the spread is 0. This is correct per Roll 1984 but means many periods produce 0 spread.
- `feature_06.py:168-169`: `differential_percentile` takes the average of long and short book spread percentiles, not the percentile of the difference. This conflates the two books rather than measuring the spread between them.

**Score: 6/10**

---

### F07 — Factor Backtesting Engine (spec p.250-288, impl `feature_07.py`)

**Spec targets:** Factor selection (single/multi up to 15 factors), composite method (equal-weight/rank/z-score/manual/walk-forward), universe filter (full/sector/custom), portfolio construction (top quintile L-O, L-S, full decile), weighting (equal/rank/proportional), rebalancing freq (daily/weekly/monthly/quarterly/annual/signal-triggered), transaction cost model (flat/Kyle-lambda/full 3-component), ADV participation cap, short selling toggle, benchmark, neutralization, walk-forward window, backtest period. Outputs: two-panel equity curve, full statistics table, quintile monotonicity, factor premium spread, transaction cost decomposition, gross vs net by year, turnover analysis, ADV capacity report, walk-forward report, Monte Carlo bands, out-of-sample toggle.

**Implemented:** Single-factor backtest via `backtest_series`. Two-panel equity curves (gross/net). Full statistics via `perf_stats`. Transaction cost decomposition via `implementation_shortfall_kernel`. Quintile monotonicity test. Annual gross/net table. Rolling premium spread. ADV capacity curve. Walk-forward proxy. Monte Carlo bands via `vectorized_mc_equity`.

**Gaps:**
- Multi-factor composite not implemented; only single factor via `normalize_factor_name` (`feature_07.py:95-96`).
- Portfolio construction limited to top-quintile L-O / bottom-quintile L-S via F01 valuation spread. Full decile analysis not implemented (`feature_07.py:32-33`).
- Weighting scheme not configurable; always uses equal-weight within quintile (`feature_07.py:96-130`).
- Rebalancing frequency parameter is accepted but only used for forward return computation; actual rebalancing is a single-formation portfolio over the full window, not periodic rebalancing (`feature_07.py:97-98`).
- Short selling toggle not implemented. Benchmark not supported.
- Walk-forward is a single-factor proxy (IS train vs OOS test Sharpe comparison), not a multi-factor weight optimization (`feature_07.py:203-215`).
- Full three-component transaction cost model is only the Kyle-lambda impact; timing cost is an explicit toggle but its computation uses `np.sqrt(execution_days)` scaling which is not how the spec describes it (`performance.py:172`).
- Monte Carlo bands use random offsets (+/-5 days) for the starting point, not randomized rebalance dates as the spec requests (`feature_07.py:26`).

**Bugs/Issues:**
- `feature_07.py:27`: `vectorized_mc_equity(net.to_numpy(dtype=float), mc_sims, offsets)` — offsets are randomly chosen integers in [-5, 5]. The function uses `returns[j]` where `j = i + offset`, meaning all simulations are just shifted versions of the same return series. This is not a Monte Carlo simulation; it's a small shift in indexing.
- `feature_07.py:95-135`: Quintile monotonicity: `fwd_returns = close.pct_change(rebalance_days, fill_method=None).shift(-rebalance_days)` — this computes forward returns from the same close prices used to compute factor scores, introducing lookahead bias. The factor score is computed from current fundamentals (point-in-time model), but the forward return window uses the exact same day's close.
- `feature_07.py:139-151`: Empty quintile fallback returns hardcoded proxy returns `[-0.021, 0.032, 0.071, 0.106, 0.142]` with perfect monotonicity score 1.0 — this is fabricated data that falsely reports signal strength when data is unavailable.
- `feature_07.py:218-250`: ADV capacity curve uses a simplified impact model (`12.0 * sqrt(participation) * 252/21`) that doesn't match the Kyle lambda model in `implementation_shortfall_kernel`. This is a duplicate calculation with different math.

**Score: 4/10**

---

### F08 — Factor Covariance Matrix (spec p.292-322, impl `feature_08.py`)

**Spec targets:** Factor set (any subset), estimation method (sample/EWMA/Ledoit-Wolf/DCC-GARCH/all comparison), estimation window (252/504/756/1260/full), display mode (correlation/covariance toggle), stress period (GFC/COVID/2022/2025), portfolio context (import from F02). Outputs: correlation heatmap, factor volatility bars, normal vs crisis comparison, eigenvalue decomposition, rolling correlation chart, condition number, portfolio risk decomposition, min-variance combination, covariance stability score.

**Implemented:** Four covariance methods (sample, EWMA with half-life, Ledoit-Wolf shrinkage, DCC-GARCH via local recursion). All outputs present: heatmap, eigendecomposition, condition number, normal/crisis comparison via VIX threshold, minimum variance, rolling pair correlation, portfolio risk decomposition, crisis preset comparison.

**Gaps:**
- Estimation window parameter only controls `rets.tail(1260)` — the actual window is always capped at 1260 even if user requests 252 (`feature_08.py:15`).
- Portfolio context import from F02 is expected via `portfolio_weights` payload key, not actually wired to F02 output (`feature_08.py:136-138`).
- DCC-GARCH is a local approximation using EWMA vol + Engle DCC recursion, not a proper GARCH fit. The spec says "DCC-GARCH (Dynamic Conditional Correlation)" — the implementation skips the GARCH step entirely (`analytics.py:516-548`).
- Covariance stability score uses condition number ratio, which is correct. But it only compares normal vs crisis based on VIX threshold, not the full covariance estimation method comparison (`feature_08.py:112-120`).
- Normal vs crisis comparison for multiple stress periods (GFC, COVID, 2022, 2025) is implemented as `_crisis_preset_comparison` but only returns pre-computed periods, not interactive selection (`feature_08.py:155-183`).

**Bugs/Issues:**
- `feature_08.py:19`: `method = "ledoit_wolf" if mode == "realtime" and len(rets.columns) > 15 and requested_method in {"dcc", "dcc_garch"} else requested_method` — DCC is disabled for >15 factors in realtime, which matches the spec. But line 21 then hard-overrides DCC to Ledoit-Wolf regardless: `if method in {"dcc", "dcc_garch"}: method = "ledoit_wolf"` — so DCC is effectively always disabled at the method level even when allowed.
- `feature_08.py:23`: `dcc_allowed = len(rets.columns) <= 15 or mode == "research"` — allowed flag exists but `method` is already forced to `ledoit_wolf` by line 21-22. The DCC payload is still computed at line 24 when allowed, but the main covariance output uses the forced Ledoit-Wolf method. This creates two covariance matrices with confusing semantics.
- `analytics.py:489-493`: EWMA covariance formula: `cov = (xm * w).T @ xm * 252` — uses `(1-lam) * lam^i` weights but applies them as point-wise multipliers on the outer product rather than as proper EWMA. The standard EWMA covariance is `(1-lam) * sum(lam^(t-i) * r_i * r_i')`. The implementation is approximately correct but the weights are applied to recentered returns (`xm`) rather than to the outer product directly.
- `analytics.py:500-504`: Vectorized correlation via matrix multiplication. The denominator `norms.T @ norms` produces a k×k matrix of product-of-norms. The formula `(centered.T @ centered) / (norms.T @ norms)` correctly produces the correlation matrix. This is fine.

**Score: 6/10**

---

### F09 — Strategy Capacity Analyzer (spec p.325-350, impl `feature_09.py`)

**Spec targets:** Strategy reference (import from F07 or new), AUM range sweep ($1M-$10B), ADV participation cap (10-25%), Kyle lambda method (platform-estimated/user-provided), cost components (explicit/impact/full implementation shortfall), rebalance frequency from F07 config. Outputs: capacity curve chart (AUM vs net alpha with ceiling), slippage by AUM table, time to liquidate, capacity sensitivity analysis, allocator capacity memo.

**Implemented:** AUM sweep (20 log-spaced points default), capacity ceiling via zero-crossing, piecewise impact model (Kyle linear below $100M, Almgren-Chriss sqrt above $100M), time to liquidate, allocator memo, sensitivity table (ADV cap 25%, double frequency).

**Gaps:**
- Strategy reference from F07: the implementation calls `backtest_series(payload)` independently rather than importing F07's precomputed results (`feature_09.py:15`).
- Allocator capacity memo is a plain-text paragraph, not a "formatted one-page summary for investor reporting" (`feature_09.py:47`).
- Capacity sensitivity analysis only shows 2 manual cases (ADV cap 25%, double frequency). The spec asks for "Impact of changes in frequency, ADV cap, or universe on the capacity ceiling" as a systematic analysis (`feature_09.py:53`).
- Rebalance frequency from F07 config is manually re-specified via `rebalance_days` parameter, not imported (`feature_09.py:38`).
- Time to liquidate formula `0.02 * aum / (cap * adv)` has a mysterious `0.02` factor that represents an assumed 2% of AUM must be traded. Not documented (`feature_09.py:102`).

**Bugs/Issues:**
- `feature_09.py:17`: `gross_alpha = perf_stats(bt["gross"]).get("annualized_return", 0.0) or 0.0` — `perf_stats` returns key `"annualized_return"` which is computed as `(1+r.mean())**252 - 1`. This produces a tiny number for daily returns (e.g., 0.02% daily mean → ~5% annual). The fallback `or 0.0` also incorrectly treats 0.0 as falsy — if alpha is actually 0, it remains 0.0.
- `feature_09.py:19`: `adv = float(chars.get("adv").dropna().median())` — `chars.get("adv")` returns a Series if column exists, but if "adv" column doesn't exist, returns None which causes AttributeError.
- `feature_09.py:88-95`: Piecewise transition at $100M is arbitrary. The Kyle linear model `lambda * turnover * aum / adv` at $100M: if turnover=0.35, adv=$50M, lambda=0.1, impact = 0.1 * 0.35 * 100M / 50M = 0.07 = 7%. The Almgren-Chriss model at the same point: impact = 0.1 * 0.25 * sqrt(0.35*100M / 50M) = 0.1 * 0.25 * sqrt(0.7) ≈ 2.1%. These models produce very different impacts at the transition point, creating a discontinuity.
- `feature_09.py:102`: `ttl = (0.02 * aum_arr) / (participation_cap * max(adv_median, 1.0))` — computes time to liquidate by assuming 2% of AUM must be traded, divided by the maximum daily trading capacity. But the 2% factor doesn't reference actual portfolio turnover or factor weight. Misleading.

**Score: 5/10**

---

### F10 — Factor-Based Portfolio Optimizer (spec p.354-383, impl `feature_10.py`)

**Spec targets:** Alpha source (hist factor returns/manual ER/Black-Litterman/F04 timing alphas), risk aversion lambda (slider), robust optimization (toggle + confidence slider), constraints (gross/net limit, factor bounds, sector bounds, position limits, turnover, TE, TC budget), efficient frontier sweep (50 portfolios), optimization horizon (short/long/mixed). Outputs: efficient frontier chart, optimal factor allocation table, optimal exposure profile link to F02, risk budget pie, constraint binding report with shadow prices, Black-Litterman comparison, robust vs standard comparison, FAP diagnostic, rebalancing cost-benefit.

**Implemented:** cvxpy quadratic programming with CVaR/quadratic objective. Efficient frontier via lambda sweep (25 points). Robust optimization via Goldfarb-Iyengar SOCP formulation. Greedy cardinality post-processing. Black-Litterman structured views. FAP diagnostic (R-squared of alpha on risk model). Constraint binding report. Robust vs standard comparison.

**Gaps:**
- Alpha source: only historical mean returns (`rets.mean() * 252`) or Black-Litterman posterior. Manual expected returns not supported; F04 timing alphas not wired (`feature_10.py:20-24`).
- Risk aversion lambda is a float input, not a slider; the spec's UI requirement can't be enforced here (backend limitation is acceptable).
- Constraints implemented: budget, long/short bounds. Missing: gross/net limit, sector bounds, position limits, turnover constraint, tracking error constraint, transaction cost budget (`feature_10.py:44-48`).
- Efficient frontier: 25 points generated, spec requires 50. Maximum points are reduced but this matches the realtime constraint language (`feature_10.py:140-145`).
- Optimization horizon (short/long/mixed) — not implemented; always uses the full history (`feature_10.py:16`).
- FAP diagnostic: R-squared of alpha vs prior. Spec requires "regression of alpha signals on the factors in the risk model." The implementation does `np.corrcoef(alpha[:n], mu[:n])` which is a pairwise correlation, not a regression. This only works if alpha and mu have the same dimension; if alpha is a different length (e.g., stock-level alpha), it slices to match (`feature_10.py:82`).

**Bugs/Issues:**
- `feature_10.py:24`: `bl_result = _black_litterman_factor(payload, names, cov.values, mu)` — BL views are checked. If BL views exist but produce an error (e.g., singular matrix), returns None and mu remains unchanged. No warning is raised to the user.
- `feature_10.py:29-36`: Robust optimization logic is inverted. `if robust_requested and mode == "realtime" and n > 100`: sets `robust = 0.0` (no robustness penalty) and shrinks mu. The spec says "N > 100 realtime robust optimization uses expected-return shrinkage approximation" but the approximation is returning standard QP with shrunk mu, which defeats the purpose of robust optimization.
- `feature_10.py:38-42`: The objective function is `mu @ theta - robust * norm(sigma_mu @ theta) - lam * quad_form(theta, cov)`. The robust term (`cp.norm(cp.psd_wrap(sigma_mu) @ theta, 2)` with sigma_mu being cov / len(rets)) is the Goldfarb-Iyengar SOCP formulation. This is technically correct but the `sigma_mu` scaling (`cov_values / max(len(rets), 1)`) uses `len(rets)` (observations) as the shrinkage denominator, which is not standard.
- `feature_10.py:50`: Cache key `hash(tuple(names))` has potential collisions. The cache stores previous warm-start weights — if `n` is the same but `names` changes (same count, different factors), the cache returns stale weights.
- `feature_10.py:56-59`: Solver fallback from OSQP to CLARABEL is reasonable but CLARABEL may also fail; no third fallback.
- `feature_10.py:64-75`: Cardinality post-processing is `keep = np.argsort(np.abs(w))[-k:]` — keeps top k by absolute weight, then re-normalizes. This is "greedy cardinality post-processing" as claimed, but it ignores risk contribution of dropped factors, potentially creating corner solutions.

**Score: 5/10**

---

### F11 — Factor Stress Testing (spec p.387-415, impl `feature_11.py`)

**Spec targets:** Scenario type (historical preset/historical custom date range/parametric/macro-linked), historical preset library (GFC/COVID/Taper Tantrum/Rate Shock/China Deleveraging/Liberation Day/Quant Unwind), parametric shock inputs (bps or SD per factor, linear/nonlinear), reverse stress test (loss threshold), contagion model VAR lags (1/2/5/21d), portfolio to stress (import from F02). Outputs: factor return bar chart with 5th/95th percentiles, portfolio P&L waterfall, historical analog comparison via Mahalanobis distance, reverse stress result + plain-language description, contagion impulse response (1/5/10/21d), multi-scenario comparison, hedging recommendation, stress VaR/CVaR.

**Implemented:** Forward stress via shock vector dot product with exposures. Reverse stress via minimum-probability factor return vector. Historical analog via Mahalanobis distance. VAR contagion model with AIC/BIC lag selection. IRF with bootstrap confidence bands. Multi-scenario comparison. Hedging recommendation. Stress VaR/CVaR. Plain-language reverse stress description.

**Gaps:**
- Historical preset library: only 4 presets in `_crisis_preset_comparison` (GFC, COVID, Rate Shock, Quant Unwind). Missing: Taper Tantrum 2013, China Deleveraging 2015, Liberation Day 2025 (`feature_11.py:155-161`). But the F08 version has GFC/COVID/RATE SHOCK/QUANT UNWIND.
- Macro-linked scenarios (mapping macro variables via Mahalanobis distance on macro variable vector) not implemented. The historical analog uses Mahalanobis distance on factor returns, not macro variables.
- Parametric nonlinear propagation not implemented; always linear (`feature_11.py:22-24`).
- Portfolio to stress from F02 is manually specified via `exposures` payload, not imported (`feature_11.py:21`).
- Factor return bar chart with 5th/95th percentile historical range is just scenario_rows, not the percentile bands the spec requests (`feature_11.py:63`).

**Bugs/Issues:**
- `feature_11.py:25-33`: Reverse stress computation: `denom = float(beta @ cov @ beta)` — this is the variance of the portfolio return (beta-weighted). `rev = -loss * (cov @ beta) / denom` — this computes the factor return vector that produces loss with minimum norm under the covariance metric. The formula is: minimize 0.5 * x' * inv(cov) * x subject to beta' * x = -loss. The closed-form solution is x = -loss * cov * beta / (beta' * cov * beta). This is mathematically correct.
- `feature_11.py:48`: `selector = VAR(var_data).select_order(maxlags=min(max_lags, max(1, len(rets) // 80)))` — `len(rets) // 80` as max lag ceiling is a magic number. For 1260 days of data, max_lags = 15, but `len(rets) // 80 = 15` so it caps there.
- `feature_11.py:57`: `irf = var.irf(21).irfs[-1]` — the impulse response at horizon 21. The `irfs` attribute contains the full response path; `[-1]` takes the 21st step. For `k` factors, `irf = var.irf(21)` has `.irfs` of shape `(22, k, k)` (including step 0). Indexing with `[-1]` correctly gets step 21 only. But the contagion output only shows horizon 21, not the 1/5/10/21d progression the spec requests (`feature_11.py:57`).
- `feature_11.py:93-146`: Bootstrap IRF CI uses a "fixed-design" bootstrap that scales the base IRF by the ratio of bootstrapped-to-original diagonal covariance. This is a variance approximation, not a proper bootstrap of the VAR coefficients. The method comment says "This preserves uncertainty bands without the expensive statsmodels refit loop" — but it's a crude approximation.

**Score: 6/10**

---

### F12 — Factor DNA Attribution (spec p.419-445, impl `feature_12.py`)

**Spec targets:** Primary factor (any single factor), comparison factors (up to 4 for radar), analysis depth (quick/full), period focus (full/expansion/recession/high-vol), auto-classifier training (academic labels / user-provided). Outputs: factor DNA card (octagonal radar: IC, ICIR, Half-life, Crowding, Sector HHI, Regime Sensitivity, Purity), sector DNA chart (long vs short GICS sector distribution), regime DNA bar (6 macro regimes), correlation DNA (rolling 252d heatmap), return anatomy (valuation reversion/characteristic momentum/risk premium), factor purity score (FF5-adjusted alpha), auto-classifier output (4-class probability stack).

**Implemented:** 8-axis DNA radar. CART auto-classifier with 4 classes (Risk/Behavioral/Structural/Data-Mining). Return anatomy decomposition. Purity score via elastic net FF5 regression. Sector DNA snapshot. Regime DNA bar from F04 outputs. Latest correlation DNA bar. Training audit metadata.

**Gaps:**
- Comparison factors (up to 4 for radar chart) not implemented; only the primary factor's DNA is computed (`feature_12.py:17-22`).
- Analysis depth (quick/full) not implemented; always runs full sub-module analysis (`feature_12.py:17-53`).
- Period focus (full/expansion/recession/high-vol) not implemented; always full history (`feature_12.py:17-22`).
- Auto-classifier training with user-provided labels not implemented; only academic archetype library used (`feature_12.py:161-163`).
- Sector DNA animation replaced by static snapshot per realtime constraint (`feature_12.py:109-125`).
- Rolling correlation DNA grid replaced by latest single-date correlation bar per realtime constraint (`feature_12.py:136-146`).
- Regime DNA bar shows 3 regimes (expansion/transition/stress) not the "6 macro regimes (Growth x Rates)" specified (`feature_12.py:128-133`).

**Bugs/Issues:**
- `feature_12.py:18-22`: Runs F05, F06, F08, F04 sequentially — these are expensive modules (Numba compilation, covariance computation, HMM fitting). A single F12 call triggers ~2000 lines of computation. This is architecturally expensive but functionally correct.
- `feature_12.py:34`: `"IC": min(100, max(0, 50 + ic * 1000))` — maps IC from [-0.05, 0.05] range to [0, 100]. The constant 1000 is a scaling choice that assumes typical IC magnitude.
- `feature_12.py:36`: `"Half-Life": max(0, 100 - half / 5)` — maps half-life 0-500 to 100-0. A factor with 100-day half-life gets score 80. This is reasonable but arbitrary.
- `feature_12.py:39`: `"Sector Breadth": max(0, min(100, 100 - float(hhi or 0.1) * 500))` — an HHI of 0.2 (concentrated) gives score 0, HHI of 0.02 (diversified) gives score 90. The scaling factor 500 assumes HHI range [0, 0.2].
- `feature_12.py:59`: Purity regression column map: `"low_vol": "BAB"`. If BAB isn't in the returns data (AQR files not downloaded), the purity regression silently uses Mkt-RF as the col_map default fallback with `y_col = "HML"`.
- `feature_12.py:77`: Elastic net coordinate descent parameters `alpha=0.002, l1_ratio=0.15, max_iter=160` — these are hardcoded and not validated for convergence. 160 iterations may not be enough for high-dimensional problems.
- `feature_12.py:177-202`: Academic archetype library has 24 entries, with 6 data-mining artifacts (label 3). The deterministic jitter augmentation (4 copies at +/-4 points) creates 120 training samples. The classes are imbalanced: ~7 Risk/7 Behavioral/6 Structural/4 Artifact before augmentation, so after augmentation it becomes ~35/35/30/20. This imbalance is carried into the CART leaf probability calibration.

**Score: 6/10**

---

### F13 — Live Signal Monitoring Dashboard (spec p.450-475, impl `feature_13.py`)

**Spec targets:** Factor library scope (full/subset), IC drift threshold (z-score default -1.5), rolling window (21/42/63 days recent, 252/504 baseline), alert preferences (dashboard/email/webhook), portfolio linkage (connect to F02 for weighted health). Outputs: signal health dashboard table (IC, IC z-score, crowding, alignment, overall score), IC drift time series (252-day chart), structural break detector (Chow p-values), crowding velocity gauge, weighted health score, alert log, signal recovery tracker.

**Implemented:** 4-health-metric composite (IC drift z-score, CUSUM structural break, crowding velocity, return-characteristic alignment). Multi-factor aggregation. Alert system with cooldown. Alert policy metadata. Single rolling CUSUM structural break. Chow diagnostic (weekly cached). Portfolio-weighted health. Signal recovery tracking via alert resolution metadata.

**Gaps:**
- IC drift threshold: spec says default z = -1.5. Implementation default is z = -1.0 (`feature_13.py:55`). Minor but a mismatch.
- Rolling window configuration (21/42/63 for recent, 252/504 for baseline): the code hardcodes 63d for recent IC average, 252d for baseline via `welford_rolling` window 252 (`feature_13.py:40-42`). The payload's `window_days` parameter controls the data window, not the signal monitoring windows.
- Portfolio linkage from F02: only accepts `factor_weights` in payload, not actually wired (`feature_13.py:109-114`).
- Signal recovery tracker: only returns alert resolution metadata ("open" / "clear"), not actual post-alert return monitoring as the spec requires (`feature_13.py:76`).
- Email/webhook alert delivery is referenced in alert_policy metadata but not functional (`feature_13.py:70-75`).

**Bugs/Issues:**
- `feature_13.py:35-36`: Forward returns for IC computation: `fwd[:-21] = r_arr[21:]` — this shifts the array by 21 positions. The IC is then computed as rolling correlation of `r_arr` (contemporaneous) with `fwd` (shifted), which correctly measures the correlation between factor return today and factor return in 21 days. This is an autocorrelation IC, not the cross-sectional rank IC the spec describes. The spec says "IC drift: is the current 63-day IC significantly below the trailing 252-day average IC" — IC here refers to the Information Coefficient (rank correlation between factor score and forward return), not return autocorrelation.
- `feature_13.py:37`: `ic = pd.Series(rolling_corr_kernel(r_arr, fwd, 21), index=r.index).dropna()` — this computes a rolling 21-day Pearson correlation of the factor return with its own forward value (21-day ahead). This is the "return autocorrelation" metric from F06, not the factor IC from F05. The spec's "IC drift" concept requires the cross-sectional rank IC from F05.
- `feature_13.py:46`: Crowding uses F06's composite score: `crowd = (f6.get("summary_cards") or [{}])[0].get("value") or 50` — this is the F06 crowding composite, not a separate computation. The spec wants "crowding velocity: is the crowding score from Feature 6 rising at an unusual rate?" The code does compute velocity correctly as `crowd_pct.diff(21).iloc[-1]` (`feature_13.py:47`).
- `feature_13.py:52`: `alignment_score = bitwise_alignment_score(ic.to_numpy(dtype=float)[-252:], r_arr[-252:])` — compares sign of IC series with sign of raw returns. The spec says "Return-characteristic divergence: is the factor's characteristic moving in a direction inconsistent with its recent return behavior?" The spec requires checking the characteristic (e.g., P/B ratio), not the raw returns.

**Score: 5/10**

---

### F14 — Allocator Transparency Report Generator (spec p.479-504, impl `feature_14.py`)

**Spec targets:** Report type (full LP DDQ / quarterly investor letter / monthly risk report / custom), portfolio reference (from F02), date range (from F03), section data sourcing (crowding F06 / capacity F09 / stress F11 / signal F13), white-labeling (fund name, logo, contact, disclaimer), narrative text, chart styling (light/dark theme, color palette, export size). Outputs: formatted PDF report, section-by-section export, AIMA DDQ index, audit trail log.

**Implemented:** Template-based report pulling from F02, F03, F06, F07, F09, F11, F13. ReportLab PDF rendering up to 20 pages. AIMA/ILPA DDQ cross-reference mapping. Audit trail log. HTML report. White-labeling (fund name, logo, custom narrative, disclosures).

**Gaps:**
- Chart styling (light/dark theme, color palette, export size) not implemented; PDF uses a single ReportLab default style (`feature_14.py:154-187`).
- Section-by-section export not implemented; only full report or deferred async (`feature_14.py:98-99`).
- Date range is a manual parameter, not linked to F03 (`feature_14.py:93-94`).
- Portfolio reference from F02 is a manual parameter, not linked (`feature_14.py:34`).
- Contact info and disclaimer text not included in report; only custom_narrative and fund_disclosures are supported (`feature_14.py:35-36`).
- AIMA DDQ index is a table mapping section titles to DDQ question strings, not a full cross-reference index with page numbers (`feature_14.py:17-27`).

**Bugs/Issues:**
- `feature_14.py:38-45`: Feature map lists F02, F03, F06, F07, F09, F11, F13. But error handling at `feature_14.py:66-67` and `76-78` catches exceptions and produces "Section unavailable" summaries. If any of these upstream features aren't functional (e.g., routing hasn't been wired), the report silently degrades.
- `feature_14.py:48-53`: Parallel section collection disabled by default because "Numba parallel kernels are not thread-safe under workqueue." This is a real concern — if any upstream feature uses Numba `prange`, running from multiple threads can crash the process. But for features that don't use Numba (F02, F03, F09, F10), parallel execution would be safe. The warning is correct but overly conservative.
- `feature_14.py:162-167`: Logo embedding catches exceptions and adds a fallback paragraph. If the logo_path is invalid, the error is silently consumed and only an italic note is added to the story.
- `feature_14.py:168-183`: PDF content is a single table of section titles/statuses/summaries — no actual charts, tables, or data visualizations are embedded. The spec requires "Professional-grade document with all selected feature outputs integrated." What's produced is essentially a table of contents.
- `feature_14.py:186`: Audit trail is rendered as `str(audit)` (Python dict representation) in the PDF. This is not investor-facing quality.

**Score: 3/10**

---

## 3. Shared Infrastructure Audit

### `analytics.py` (777 lines)

**Completeness:**
- `valuation_spread()` — functional but the valuation spread is computed from FF factor cumulative returns, not from the actual cross-sectional fundamental spread percentile. The FF cumulative return proxy is a reasonable stand-in but the spec specifically asks for the spread in underlying fundamental characteristics (e.g., P/B spread for Value).
- `sector_brinson_fachler()` — the Brinson-Fachler decomposition is implemented correctly using allocation/selection/interaction effects. However, it uses the characteristic panel's sector metadata rather than the user's benchmark sector weights, which limits its accuracy for active return decomposition.
- `covariance_payload()` — supports sample, EWMA, Ledoit-Wolf. The EWMA implementation uses deterministic exponential weighting. The DCC-GARCH is a local approximation using EWMA vol standardization, not a true DCC-GARCH fit.
- `implementation_shortfall()` — uses `implementation_shortfall_kernel` from performance.py. The kernel models explicit + linear spread + square-root impact + timing cost. The impact formula `eta * sigma * sqrt(participation)` is the Kyle lambda formulation, which is a square-root impact model (Almgren-Chriss), not a Kyle lambda (linear) model. Mixed conventions.
- `backtest_series()` — computes gross and net return series from FF factor column + implementation shortfall costs. This is a factor-level backtest, not a stock-level portfolio backtest.

**Math correctness:**
- `predictive_regression()` (line 432-461): OLS regression with 90% confidence interval. The forecast variance formula includes the `1 + x0'(X'X)^{-1}x0` term, which is correct for the prediction interval. However, the regression uses future returns (shifted -horizon) on the left and current signal on the right — this is correct for predictive regression but the standard errors need Newey-West adjustment for overlapping observations when horizon > 1. The OLS standard errors are biased.
- `ols_beta()` (line 464-481): Standard multi-factor OLS. The covariance matrix computation tries `inv` first with `pinv` fallback — good.
- `dcc_garch_payload()` (line 516-548): The DCC implementation uses a simplified Engle (2002) two-step estimator. Step 1: EWMA vol estimation. Step 2: DCC recursion on standardized residuals. The Qbar uses the sample covariance of standardized residuals. The parameters `a=0.03, b=0.94` are typical for daily data. The constraint `b <= 0.995 - a` ensures mean-reversion. This is a reasonable local approximation but doesn't estimate the parameters via MLE.

**Missing functions needed by spec:**
- No macro-linked stress scenario mapping (F11)
- No PCA-based crowding composite (F06)
- No Amihud illiquidity measure (defined in `feature_06.py`, should be in analytics)
- No DCC-GARCH MLE estimation (true DCC, not just recursion)
- No Newey-West standard errors (needed by F03, F11)

### `contracts.py` (138 lines)

The contracts are well-structured metadata. The FEATURE_CONTRACTS dictionary matches the 14 features with proper inputs/outputs/math_source/realtime_constraint fields.

Issues:
- `line 23-38`: FEATURE_MODULES maps numeric IDs to descriptive module names (e.g., `"01": "factor_valuation_spread_monitor"`). These are used by the API router to import the stub files. The stub files exist (14 × 1-line re-exports). This architecture works but is fragile: if a stub file is deleted or the module name changes, the API breaks.
- The output_schema keys match the standard `response()` function output. No gaps.

### `data_loader.py` (415 lines)

**Data source coverage vs spec:**
- Category 1 (OHLCV): ✓ `load_market_universe()` loads parquet. `load_price_file()` for individual tickers.
- Category 2 (Benchmark): Partially. No specific benchmark loading; assumes benchmark tickers are in the market universe.
- Category 3 (Fundamentals): ✓ `load_fundamentals()` loads master_fundamentals.parquet with P/B, ROE, margins, etc. But the spec's note about lookahead bias is only documented in the spec doc, not in code.
- Category 4 (Fama-French): ✓ `load_ff_file()` loads FF3, FF5, momentum CSV files. The `load_factor_returns()` assembles models.
- Category 5 (AQR): ✓ `load_aqr_factor_returns()` loads BAB, QMJ, HML Devil from CSV conversion.
- Category 6 (Risk-free rate): ✓ Included in FF files.
- Category 7 (Macro): ✓ `load_category7_macro()` loads from parquet.
- Category 8 (Sector): ✓ `load_sector_maps()` extracts from fundamentals.
- Category 10 (FX): ✗ **Not implemented**. No FX rate data loader exists. This means all global-universe computations are done in local currency without USD normalization, per the spec's warning.
- Category 11 (Bid-Ask): ✓ Implemented as `_roll_spread()` in `feature_06.py` — but this is in the feature file, not in data_loader.

Issues:
- `line 181-193`: `load_fundamentals()` loads all columns; no column selection option. For a 500-MB parquet, this is wasteful.
- `line 344-361`: `load_price_file()` loads from multiple file extensions. But the comment says "for individual ticker loading" which is primarily used by comparison_portfolios in F02.
- `line 363-365`: `available_aqr_csvs()` lists available AQR files — this exists but isn't used by any feature.
- No lazy loading for fundamentals or FF files (except `load_market_universe_lazy` and `load_fundamentals_lazy` which are unused by features).

### `performance.py` (575 lines)

**Caching:**
- `_ARRAY_CACHE` with FIFO eviction at 512 entries. `cache_array` and `get_cached_array` — used by `characteristic_panel` for the characteristic block. Reasonable.
- `stable_cache_key()` uses blake2b with 8-byte digest — fast and collision-resistant.
- Static `_SCRATCH_CACHE` for reusable numpy arrays via `scratch_array()`. Not used by any feature code; appears to be a forward-looking optimization.

**JIT kernels:**
- `rolling_autocorr_1`, `drawdown_curve`, `implementation_shortfall_kernel`, `cusum_statistic`, `dcc_recursion_kernel`, `rolling_ols_kernel`, `welford_rolling`, `rolling_corr_kernel`, `batched_forward_sums`, `vectorized_rolling_ic_matrix`, `rolling_std_percentile_kernel`, `vectorized_mc_equity`, `elastic_net_coordinate_descent`, `tiled_dot_kernel`, `rolling_percentile_numba` — all compiled at import via `_prewarm_kernels()`.
- Smart design choice: the `njit` shim allows pure-Python fallback when Numba isn't installed.

**Issues:**
- `implementation_shortfall_kernel` (line 147-179): The timing cost formula `timing_bps / 10000 * turnover * weights[i] * sqrt(execution_days)` is not documented in the spec. The spec's timing cost is "slippage between decision price at close and execution price the following open" — this is a gap-dependent cost, not a sqrt(days) scaling.
- `vectorized_mc_equity` (line 363-377): The seed offset approach is useful but the actual usage in F07 uses random offsets in [-5, +5], which is not meaningful Monte Carlo. The function itself is correct.
- `dcc_recursion_kernel` (line 197-218): The `dcc_recursion_kernel` uses `for r in range(k): for c in range(k):` nested loops — this is O(k²) per time step, which is fine for small k but will be slow for large factor sets.

### `registry.py`

**Does not exist.** The user's list mentioned `registry.py` but this file is absent from the filesystem. No imports reference it. Likely planned but never implemented.

### `FACTOR_FEATURES_MASTER.py` (3,115 lines)

**Assessment: Monolithic duplicate of all 14 feature files.**

The file concatenates all 14 `feature_XX.py` files sequentially with header banners (`# FEATURE 01`, `# FEATURE 02`, etc.). A diff of `feature_01.py` vs the master shows only 2 extra lines (the header banner and a trailing blank line). The master file is **byte-for-byte identical in content** to the individual files minus the header comments.

**Dead code confirmation**: There are zero imports or references to `FACTOR_FEATURES_MASTER` anywhere in the codebase (confirmed by grep). The DEAD_CODE_CLEANUP_AUDIT.md already identifies it for deletion.

**Risk**: Low — zero external refs, confirmed duplicate. Safe to delete after confirming no dynamic import references it.

### 14 Stub Re-Export Files

Each is a 1-line `from .feature_XX import run` redirect. These are named by the FEATURE_MODULES descriptive names (e.g., `factor_valuation_spread_monitor.py` → `from .feature_01 import run`).

**Assessment**: These are **functional re-exports**, not placeholders. They correctly route `run()` to the individual feature files. They are used by the API router's `_feature_module()` function (via `importlib.import_module(f"app.services.factors_v2.features.{module_name}")`) where `module_name` is taken from `FEATURE_MODULES` (e.g., `factor_valuation_spread_monitor`).

**However**: `features/__init__.py` does NOT exist. With Python 3.3+ namespace packages, this works implicitly, but the import path `app.services.factors_v2.features.factor_valuation_spread_monitor` relies on the directory being auto-discovered as a namespace package. If `app/services/__init__.py` exists and doesn't have a proper package structure, these imports may fail.

---

## 4. API Layer Audit

### `api/factors_v2.py` (164 lines)

**Endpoint patterns:**
- `GET /labs/factors/v2/features` — lists all features with contracts (line 61)
- `GET /labs/factors/v2/governance` — governance metadata (line 83)
- `GET /labs/factors/v2/symbols` — ticker search (line 88)
- `POST /labs/factors/v2/feature/{feature_id}/run` — run a single feature (line 103)
- `POST /labs/factors/v2/run-all` — run all features (line 116)
- `POST /labs/factors/v2/export/{feature_id}` — export endpoint (line 138)
- `POST /labs/factors/v2/alert-subscription` — dormant alert subscription (line 154)

**Does it serve V2 features or V1?** It serves V2 features only. The `_feature_module()` function (line 40-43) imports from `app.services.factors_v2.features.{module_name}` where module_name comes from the V2 FEATURE_MODULES contract. There is no V1 routing here.

**Is it wired in main.py?** Confirmed: **no references** to `factors_v2` in `main.py`. The router is defined with `prefix="/labs/factors/v2"` but is never mounted. The README says "When you are ready to wire V2, create a new router file... And register it in backend app startup (main.py include_router)." This has not yet been done.

**Issues:**
- `line 104`: `def run_feature(feature_id: str, request: Dict[str, Any])` — accepts `request` as a raw dict, not as a Pydantic model. The `FactorsV2RunRequest` model exists (line 22-23) but isn't used. This means no validation of the request body happens at the API layer.
- `line 108-112`: Error handler wraps all exceptions into 500 with the message `f"Factors V2 feature_{normalized} failed: {exc}"`. This leaks internal error details to API clients.
- `line 116-135`: `run-all` iterates over all 14 features and catches exceptions individually. If one feature fails, others still return results. Correct design.
- `line 138-151`: `export_feature` endpoint is explicitly labeled "Dormant export endpoint" — it works functionally but is not intended for production use yet.
- `line 154-163`: `alert_subscription` returns `"status": "registered_dormant"` — stub that validates the schema but doesn't actually deliver alerts.

**run(payload) pattern**: All features implement `def run(payload: Dict[str, Any]) -> Dict[str, Any]`. The API calls `_feature_module(normalized).run(payload)`. Consistent across all 14 features.

---

## 5. Overall Assessment

### Total Lines of Code
- **Deduplicated production code: 5,101 lines** (core 1,905 + features 3,031 + API 164 + __init__ 1)
- **With duplicate master: +3,115 = 8,216 lines** (FACTOR_FEATURES_MASTER.py is 100% duplicate)
- **With stubs: +14 lines (14 re-export files)**

### Missing Functions/Models from Spec
1. **No FX rate data loader** (Category 10) — global universe factor construction is contaminated by currency effects
2. **No Amihud illiquidity in shared infrastructure** — implemented separately in feature_06.py
3. **No PCA-based crowding composite** — F06 only supports equal-weight
4. **No true DCC-GARCH MLE estimation** — uses local EWMA approximation
5. **No Newey-West standard errors** — needed for overlapping predictive regressions in F01, F03, F05
6. **No macro-linked stress scenarios** — F11 uses historical analog but not macro variables
7. **No user-customizable factor definitions** — spec allows "any user-defined custom factor from ticker universe"
8. **No sector-neutral/beta-neutral IC computation** (F05)
9. **No benchmark parameter for F02/F03** — always uses internal proxies
10. **No portfolio rebalancing history integration** — rolling exposures are fake drifts

### Data Dependency Gaps
- **FX rates missing**: global universe factor ranks will be contaminated by currency momentum
- **AQR data**: `load_aqr_factor_returns()` exists but depends on pre-converted CSV files in `factors/data/processed/aqr_csv/`. If files are missing, silently returns empty DataFrame
- **FRED macro data**: `load_category7_macro()` depends on a pre-computed parquet file. No pipeline for daily refresh
- **Fundamentals lookahead bias**: explicitly acknowledged in spec (Category 3 caveat) but no runtime enforcement or warning in the code
- **All data is "best effort"**: every loader silently returns empty DataFrame on failure. Features degrade to "warning" status but don't block

### Code Quality Rating
- **Strengths**: Numba JIT compilation for hot loops, smart caching (module-level TTL, LRU for hash, FIFO for arrays), consistent response schema, realtime vs research mode enforcement, governance metadata, type hints throughout
- **Weaknesses**: No tests (confirmed by absence of test files), no error propagation from loaders to users, stale/duplicate master file (3,115 lines), fake deterministic proxy data in F02 and F07, undocumented math assumptions in formula constants, no integration between features (F02→F03, F07→F09, F04→F10 all re-compute independently)

### Overall Rating: 4.5/10

The infrastructure (performance.py, data_loader.py, analytics.py) is well-engineered with real engineering trade-offs documented. The feature implementations range from solid (F04, F06, F08, F11) to thin shells with hardcoded fallback data (F02, F07). No feature fully matches its spec. The API router is well-designed but unconnected. The master file is pure dead weight.

### Top 10 Critical Fixes in Priority Order

1. **Wire the V2 router in `main.py`** — the entire API layer is dormant; no endpoint can be called.
2. **Delete `FACTOR_FEATURES_MASTER.py`** — 3,115 lines of dead duplicate code identified in the deletion manifest.
3. **Add `features/__init__.py`** — namespace packages work but an explicit init is safer for import resolution.
4. **Fix F01 single-factor bug** (line 20) — `len(requested_factors) <= 1` should not overwrite to defaults for a single legitimate factor.
5. **Fix F02 rolling exposure from fake data** — stop using sinusoidal drift; compute actual rolling exposures from the data (even if approximate).
6. **Fix F07 fabricated quintile returns** — empty quintile fallback returns hardcoded monotonic returns with perfect score 1.0, which falsely reports signal strength.
7. **Fix F07 Monte Carlo simulation** — offsets of ±5 days are not a Monte Carlo simulation; implement proper randomized rebalance dates.
8. **Fix F13 IC computation** — the current implementation computes return autocorrelation (F06 metric), not the cross-sectional Information Coefficient from F05. The spec's "IC drift" requires rank IC between factor scores and forward returns.
9. **Add FX rate data loader** — Category 10 is explicitly required and missing; without it, global-universe factorization is contaminated by currency effects.
10. **Remove or correct F02 deterministic ticker proxy** — `sum(ord(ch) for ch in ticker)` hash-based exposure generation for missing tickers is random noise, not data.
