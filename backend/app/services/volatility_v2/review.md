# Volatility V2 — Spec Compliance & Implementation Review

## Resolution Checklist

Updated 2026-07-13.

- [x] Implemented `contract_for()` and explicit contracts for all nine features.
- [x] Removed Feature 09 lookahead bias. Exposure at date t now uses a one-step-ahead EWMA variance forecast based only on information through t-1.
- [x] Replaced the Bandi-Russell heuristic with the specified Parkinson variance minus twice the estimated microstructure-noise variance.
- [x] Removed the undocumented Parkinson inflation multiplier from both single-window and multi-window estimators.
- [x] Added empirical relative-efficiency deviation and the greater-than-30-percent fat-tail warning.
- [x] Replaced Pearson range correlation with the specified Parkinson range cross-product normalization.
- [x] Replaced fixed News Impact Curve (NIC) multipliers with the 10th, 50th, and 90th percentiles of fitted conditional-variance history.
- [x] Added configurable conditional Value at Risk coverage through `var_coverage` and removed fragile dynamic SciPy imports.
- [x] Added Volatility V2 API discovery and execution routes at `GET /api/labs/volatility/v2/features` and `POST /api/labs/volatility/v2/feature/{feature_id}/run`.
- [x] Python compilation and local-data smoke tests pass for Features 01, 02, and 09; all nine contracts load successfully.

### Still requiring broader research or external-data work

- [ ] Exact Nyblom score-process stability statistic with Hansen critical values.
- [ ] Non-US implied-volatility indices and uploaded implied-volatility datasets.
- [ ] Full cross-feature cached regime probability sharing for Features 05 and 07.
- [ ] Continuous projected-gradient adversarial scenarios and copula-conditioned reverse-stress simulation.
- [ ] Full DCC-MIDAS recursion and daily frequency-connectedness history.

## 1. Lines of Code Summary

| Component | Files | Lines |
|-----------|-------|-------|
| Core analytics | `core/analytics.py` | 1,495 |
| Core data loader | `core/data_loader.py` | 93 |
| Core data pooling | `core/data_pooling.py` | 146 |
| Core performance (JIT) | `core/performance.py` | 321 |
| Core contracts | `core/contracts.py` | Implemented after review |
| Feature 01 | `features/feature_01.py` | 98 |
| Feature 02 | `features/feature_02.py` | 154 |
| Feature 03 | `features/feature_03.py` | 129 |
| Feature 04 | `features/feature_04.py` | 117 |
| Feature 05 | `features/feature_05.py` | 116 |
| Feature 06 | `features/feature_06.py` | 78 |
| Feature 07 | `features/feature_07.py` | 72 |
| Feature 08 | `features/feature_08.py` | 120 |
| Feature 09 | `features/feature_09.py` | 78 |
| Registry | `registry.py` | 49 |
| Features init | `features/__init__.py` | 61 |
| Package init | `__init__.py` | 20 |
| Stub | `features/_stub.py` | 37 |

| **Total backend** | **18 files** | **3,215 lines** |

The original implementation contained 3,215 lines of backend code. The frontend has additional code not audited here. An API router has now been added.

---

## 2. Per-Feature Audit

### Feature 01 — Multi-Estimator Daily Volatility Engine

**Spec targets**: 5 estimators (CC, Parkinson, GK, RS, YZ) + Bandi-Russell (upgrade 6th), windows [10/21/42/63/126/252], outputs: comparison chart, efficiency table, DM tournament, agreement index, OGF indicator, annualized vol dials, range correlation matrix, cross-asset ranked panel, vol-adjusted momentum.

**Implemented**: All 5 base estimators via numpy array ops. Multi-window via `volatility_estimators_multi()`. Bandi-Russell proxy. OGF fragility. Range correlation matrix. Vol-adjusted momentum. Efficiency table with theoretical + empirical RE. Full DM tournament.

**Gaps**:
1. **Bandi-Russell is NOT the spec formula** (`analytics.py:864-882`). The spec demands σ²_BR,t = σ²_PARK,t − 2×η²_t where η²_t is the negative first-order autocovariance of squared daily returns. The implementation uses `(0.62*CC + 0.38*HL) * (1 + noise_penalty)` — a completely different heuristic. The noise_penalty from dollar volume rank is interesting but not Bandi-Russell.
2. **Empirical RE deviation >30% fat-tail warning not implemented** (`analytics.py:420-443`). The efficiency table computes empirical RE but never flags when it diverges from theoretical by >30%.
3. **OGF auto-routing not implemented**. Spec says when OGF < 0.05: demote YZ and promote RS; when OGF > 0.30: flag YZ as mandatory, suppress RS. Code computes OGF but doesn't adjust rankings.
4. **Range correlation matrix uses `np.corrcoef` on raw log ranges** (`analytics.py:897-906`). The spec gives the Parkinson cross-product correlation formula: ρ_PARK = sum(ln(H_i/L_i) × ln(H_j/L_j)) / (σ_PARK,i × σ_PARK,j × 4 ln 2). The code uses standard Pearson correlation of range series — different formula, less efficient.
5. **No liquidity threshold parameter** for microstructure noise correction toggle.
6. **Missing upgrade items**: Bandi-Russell toggled on/off by liquidity threshold, empirical RE fat-tail warning, OGF auto-routing.

**Bugs/Issues**:
- Parkinson estimator has unexplained multiplier `(1.0 / (1.0 - 390.0 ** -0.5))` (`analytics.py:333`). The spec formula is just σ²_Park = (1/4T ln 2) × Σ[ln(H_t/L_t)]². The extra factor is undocumented and would inflate the Parkinson estimate by ~2%.
- Yang-Zhang for crypto assets defaults to `yz_var = rs_var` (`analytics.py:337-338`). This silently discards the overnight component with no warning.
- `_rolling_var_np` uses `ddof=1` (sample variance) but YZ formula conventionally uses population variance. Minor but systematically different.
- Parkinson formula in `volatility_estimators_multi` (`analytics.py:387`) has the same undocumented multiplier.

**Score**: **6/10**

---

### Feature 02 — GARCH Family Suite

**Spec targets**: 5 models × 4 distributions (GARCH, EGARCH, GJR-GARCH, APARCH, FIGARCH × Gaussian, Student-t, GED, Skew-t) = 20 combos + Realized GARCH = 24 combos. Outputs: model comparison scoreboard, DM pairwise table, NIC regime ribbon, GARCH term structure, PIT test, conditional VaR, vol state gauge. Upgrades: regime-conditional NIC, Nyblom stability test, APARCH δ benchmarking.

**Implemented**: 5 models × 4 dist via `arch` library, Realized GARCH appended separately. Scoreboard with AIC/BIC/RMSE/QLIKE/MCS. NIC with "regime ribbon" (fixed multipliers). GARCH term structure with Monte Carlo bands. PIT + KS test. Kupiec + Christoffersen VaR tests. APARCH δ cross-asset benchmarking. Nyblom "stability" proxy.

**Gaps**:
1. **Regime-conditional NIC uses fixed multipliers** (`feature_02.py:66`): 0.75/1.0/1.35 arbitrary scaling. The spec demands 10th/50th/90th percentile of σ²_{t-1} history — this is data-driven, not fixed ratios.
2. **Nyblom parameter stability test NOT implemented** (`feature_02.py:117-130`). The code splits the return series into 4 chunks, fits GARCH on each, and checks stddev of beta[1] < 0.08. The spec demands the actual Nyblom (1989) statistic: L = T^(-2) × tr[Σ̂^(-1) × Σ_t (Σ_s ∂ℓ_s/∂θ)(Σ_s ∂ℓ_s/∂θ)'] with Hansen (1992) critical values. What's implemented is a crude heuristic.
3. **DM pairwise table is a stub** (`feature_02.py:147`). Only dumps QLIKE values as a single-column table. Spec wants a proper N×N DM tournament heatmap with p-values.
4. **No structural break date** input parameter.
5. **No weekly return frequency** option.
6. **No VaR coverage level** customization (99% hardcoded).
7. **FIGARCH fractional parameter d**: not estimated — `figarch_d_proxy` at `feature_02.py:140` uses rolling autocorrelation of squared returns as a proxy for d, which is incredibly crude.

**Bugs/Issues**:
- `<built-in>` import at `feature_02.py:90`: `__import__("scipy")` — fragile, breaks static analysis.
- `Realized-GARCH` appended to scoreboard at `feature_02.py:27` with `qlike: None, rmse: None, mcs_member: False`. It's never evaluated against the other models. The spec says 24 model-distribution combinations in the MCS.
- NIC ribbon: GJR-GARCH and EGARCH NICs (`feature_02.py:52-56`) use `eps_arr` as shocks. For GJR-GARCH, `v_arr = omega + (alpha + gamma * (eps_arr < 0)) * eps_arr**2 + beta * prev_var`. The `prev_var` is `long_run` — correct per spec.
- `persistence` calculation (`feature_02.py:37`): `params.get("alpha[1]", params.get("phi[1]", 0.06))` — the `phi[1]` fallback is for EGARCH but the key name may vary across `arch` library versions.

**Score**: **5/10**

---

### Feature 03 — HAR Forecasting Suite

**Spec targets**: 6 HAR variants (HAR, LHAR, HAR-J, HAR-Leverage, ACSV-HAR, A-ACSV-HAR) + HAR-X (upgrade) = 7. Outputs: parameter table, multi-horizon forecast chart, accuracy table, MCS, jump proxy, leverage chart, ACSV contribution, HAR-X macro contribution. Upgrades: BPV jumps, directional DM, MCS combination, HAR-X macro.

**Implemented**: 8 variants (HAR, LHAR, HAR-J, HAR-J-Signed, HAR-Leverage, ACSV-HAR, A-ACSV-HAR, HAR-X). HAR-J-Signed is extra (not in spec). BPV jump decomposition. Directional accuracy (hit rate + directional DM). MCS combination forecast (equal + inverse-QLIKE). HAR-X with VRP, yield slope, credit spread. Walk-forward validation. Bootstrap forecast bands.

**Gaps**:
1. **ACSV cross-sectional universe not configurable** (`feature_03.py:28`). Uses `ret_panel.var(axis=1)` which takes the variance across ALL assets in the returns panel, not a user-specified subset.
2. **Jump estimator disagreement flag is a single scalar**, not a time series with threshold bands as spec demands.
3. **No leverage effect toggle** input parameter.
4. **Newey-West bandwidth not configurable** from payload.
5. **Confidence intervals not configurable** (80%/90%/95% bootstrap).
6. **MCS uses only RMSE-based loss**; spec wants both RMSE and QLIKE.
7. MCS combination forecast is never tested against individual winner via DM (as spec requires for the upgrade).

**Bugs/Issues**:
- **HAR-X VRP is computed inline** (`feature_03.py:37`): `(vix/100.0 - yz)`. The spec says VRP_t should come from Feature 5. This inline approximation ignores the full GARCH physical expectation and uses the raw YZ vol instead. This is a significant deviation.
- Macro data gaps silently filled with 0 (`feature_03.py:37-39`): `.fillna(0)` for VRP, yield slope, and credit spread. Missing macro data means the HAR-X signal will produce bogus forecasts.
- QLIKE computation (`feature_03.py:62`) differs from Feature 2's QLIKE. Inconsistent across features.
- MCS combination weighted (`feature_03.py:99`): `sum(forecast[k] * (inv[k] / denom) for k in inv)` — syntactically correct but computationally fragile since `forecast[k]` and `inv[k]` index by different keys.
- `MCS_combo_weighted` line 99: if a model appears in only some `horizons` calls, the combination may silently drop data.

**Score**: **6/10**

---

### Feature 04 — Volatility Regime Detection Engine

**Spec targets**: 3 parallel methods (SJM, HMM, Macro Rules) → precision-weighted ensemble. Outputs: probabilistic regime timeline, current dashboard, regime-conditional stats, transition heatmap, method divergence, transition alerts. Upgrades: EW-EM adaptive HMM, macro-augmented SJM (9 features), filtered vs smoothed comparison, Weibull duration model.

**Implemented**: All 3 methods. 9-feature SJM (vol_5/21/63, return_21d, rs_yz_jump_ratio, sqret_autocorr_21, d_credit_21d, d_slope_21d, vix_zscore). EW-EM HMM (`fit_hmm_regimes_adaptive`). Filtered vs smoothed posterior comparison. Weibull regime duration model. Global vol regime sync index. Method divergence via KL divergence. Transition heatmap at 3 horizons.

**Gaps**:
1. **Macro Rules Engine** (`feature_04.py:66`): uses arbitrary weighted formula `(YZ_rank × 0.45 + trend × 0.20 + VIX > 25 × 0.25 + curve<0 × 0.10)`. The spec wants a deterministic mapping from VIX level (FRED), yield curve slope (FRED), and 21-day YZ trend. The implementation is reasonable but the weights are undocumented.
2. **HMM BIC selection only active in research mode** — fine, documented behavior.
3. **No option to select standard 6-feature vs macro-augmented 9-feature SJM**. Spec makes this configurable.

**Bugs/Issues**:
- `_soft_probs()` (`feature_04.py:11-28`): a deterministic rank-to-probability heuristic, not a proper generative model. Used for both macro rules AND the "realized" probabilities in Brier score weighting. The Brier score uses these heuristic "realized" probabilities, which are themselves derived from the data being modeled — circular.
- Line 66: `joined.get("curve_10y_2y", 0) < 0` uses backward-fill of curve data. If curve data is completely missing, defaults to 0 which evaluates to `False` for the condition `0 < 0`. Silent data failure.
- Global sync index (`feature_04.py:106`): uses pct rank > 0.7 as high-vol threshold. Spec says p_composite[high-vol] > 0.5 from Feature 4. The code uses a different threshold.
- EW-HMM `fit_hmm_regimes_adaptive` (`analytics.py:997-1015`): only does 8 iterations of weighted EM after initial standard fit. May not converge properly.

**Score**: **7/10**

---

### Feature 05 — Volatility Risk Premium Monitor

**Spec targets**: VRP = IV² - E[σ²_physical] via 3 methods. Outputs: VRP time series, cross-asset comparison, return predictability panel, VRP mean reversion speed, VRP component attribution. Upgrades: Hodrick SE, regime-conditional BTZ decomposition, VRP term structure (30d/90d/180d).

**Implemented**: VRP as IV - physical (GARCH, HAR, rolling mean). GARCH physical from Feature 2's winner. HAR physical as weighted average of daily/weekly/monthly YZ. Rolling mean as 252-day squared return. VRP Z-score. VRP term structure (30d/90d/180d) using HAR forecasts. BTZ regression with both Newey-West and Hodrick SE. Regime-conditional BTZ. Mean-reversion half-life.

**Gaps**:
1. **Cross-asset mode not implemented**. Only single-asset VRP. Spec says multiple vol index pairs simultaneously.
2. **VSTOXX, VFTSE, JNIV not supported**. Only VIX from FRED. No non-US vol indices.
3. **User-uploaded implied vol CSV not supported**.
4. **VRP display mode not configurable** from payload (raw, squared, Z-score).
5. **VRP component attribution is a single-date snapshot** (`feature_05.py:113`), not the time series stacked chart the spec demands.

**Bugs/Issues**:
- **Regime-conditional BTZ uses YZ rank, NOT Feature 4 regime probabilities** (`feature_05.py:104-106`). The spec says "p_composite[low-vol] > 0.6 AND VRP > 70th percentile". The implementation uses `yang_zhang.rank(pct=True) < 0.35` to define "low vol". This is a fundamentally different conditioning variable. The feature_04 integration is missing here.
- **VIX fallback** (`feature_05.py:38`): when VIX data is missing entirely, it's approximated as `yz_vol * 1.15` clipped to [5, 95]. The 1.15× scaling factor has no empirical or theoretical justification.
- **HAR physical forecast** (`feature_05.py:47`): fixed weights 0.45/0.35/0.20 for daily/weekly/monthly. These weights are not estimated from data, unlike Feature 3's OLS estimation.
- **BTZ regression horizon**: defaults to 21 trading days (`feature_05.py:61`) — the canonical BTZ horizon is 30 calendar days (~22 trading days). Close but not exact.
- VRP term structure line 89: `iv_mult` of 1.05 (90d) and 1.08 (180d) are undocumented scaling factors used when VIX3M/VIX6M data are missing.

**Score**: **5/10**

---

### Feature 06 — Cross-Asset Volatility Connectedness

**Spec targets**: VAR(p) → generalized FEVD → connectedness measures. Outputs: total connectedness index, net spillover ranking, dynamic network, pairwise FEVD heatmap, to/from decomposition, regime alert. Upgrades: Barunik-Krehlik frequency decomposition, EW-VAR, Connectedness-at-Risk.

**Implemented**: VAR(p) with BIC lag selection. Generalized FEVD. Total/from/to/net connectedness. Rolling connectedness history. EW-VAR. Barunik-Krehlik 3-band decomposition (short/medium/long). Connectedness-at-Risk via quantile regression. Spillover network nodes/edges. Impulse response functions.

**Gaps**:
1. **FEVD forecast horizon not configurable** from payload (hardcoded default 10). Spec says 5/10/21.
2. **Alert threshold not configurable** from payload.
3. **No animated time-lapse network**. Static snapshot only.
4. **Connectedness-at-Risk uses default macro columns** from `macro_frame()`. Works but fragile if macro data changes.

**Bugs/Issues**:
- **EW-VAR BIC computation** (`analytics.py:1094`): `sigma = (resid * w[:, None]).T @ resid` — the weighted residual outer product needs proper degrees-of-freedom adjustment. Comparing this BIC across different lag orders p may produce inconsistent model selection.
- Rolling connectedness (`feature_06.py:36-43`): uses step size `len(logv) // 300`, producing ~300 data points. This means connectedness values are not computed for every date, and the step size varies by history length. The spec says "updated daily."
- Rolling EW-VAR inside the loop (`feature_06.py:38`): uses `fit_var` (standard OLS), not `fit_var_ew`. So the rolling connectedness doesn't use the frequency decomposition feature even when EW is selected.
- `generalized_fevd_fast` (`performance.py:282-290`): denom uses einsum that computes sum over horizon of `phi_sigma[i,h,:] * phi[h,k,:]`. The formula is correct for the Pesaran-Shin (1998) generalized FEVD approach.

**Score**: **7/10**

---

### Feature 07 — Multivariate Volatility and DCC Engine

**Spec targets**: 4 methods (Sample, EWMA, Ledoit-Wolf, DCC-GARCH). Outputs: correlation matrix heatmap (5 tabs), normal vs crisis comparison, DCC time series, eigenvalue decomp, condition number, portfolio risk attribution, min variance portfolio. Upgrades: DCC-MIDAS, probability-weighted crisis correlation, minimum torsion decomposition.

**Implemented**: 4 methods. DCC-MIDAS long-run correlation. Probability-weighted crisis correlation (rank-based heuristic). Minimum torsion decomposition. Fisher Z-test correlation amplification. Condition number history. Portfolio risk attribution with MRC. Min variance portfolio.

**Gaps**:
1. **Probability-weighted crisis correlation does NOT use Feature 4 regime probabilities** (`feature_07.py:36-38`). Uses `ret.abs().mean(axis=1).rank(pct=True)` as weights. The spec says p_composite(t)[high-vol] from Feature 4.
2. **DCC-MIDAS is computed but never integrated into the DCC model** (`feature_07.py:56-58`). It's computed as a static matrix and displayed, not used as the long-run target matrix in the DCC recursion.
3. **Normal vs crisis comparison only uses DCC correlation** — not all 4 methods. Spec shows "four tabs: Sample, EWMA, Ledoit-Wolf, DCC."
4. **No hard-threshold VIX > 30 crisis definition** as legacy fallback.
5. **Minimum torsion decomposition outputs Python object** — factor labels are just indices, not the primary asset loading description spec requires.

**Bugs/Issues**:
- **`covariance_methods()` returns `dcc` as EWMA copy** (`analytics.py:807`). The function name is misleading — it claims to return DCC but just copies EWMA. The real DCC is added later at `feature_07.py:19`.
- Normal period definition (`feature_07.py:30`): uses first 75% of returns as "normal". This is naive — normal periods should be identified by regime probability, not a fixed split.
- Crisis mask (`feature_07.py:31`): top 10% of absolute returns. Reasonable heuristic but not the spec's probability-weighted or VIX threshold approach.
- DCC-MIDAS (`analytics.py:1148-1169`): uses `freq="ME"` (month-end) to create monthly realized correlations, then fits Beta polynomial MIDAS weights. The weights formula `weights_x ** 0.5 * (1 - weights_x / (k_lags + 1)) ** 4` is a restricted Beta polynomial — reasonable but not the flexible two-parameter Beta polynomial the spec calls for.

**Score**: **6/10**

---

### Feature 08 — Volatility Stress Testing and Scenario Engine

**Spec targets**: 4 scenario types (Historical preset, Historical analog, Parametric, Reverse stress). Outputs: vol shock bar chart, portfolio P&L waterfall, historical analog comparison, reverse stress, contagion IRF, multi-scenario comparison, stress VaR/CVaR. Upgrades: Clayton copula reverse stress, graphical LASSO analog matching, adversarial scenario generator.

**Implemented**: Historical presets (4 of 7 from spec). Parametric scenario. Historical analog (Mahalanobis + GLASSO). Reverse stress (linear leverage). Clayton copula tail dependence (theta + lower tail dep). Adversarial scenario (discrete window search). Contagion IRF with bootstrap bands. Monte Carlo stress VaR/CVaR. Multi-scenario comparison.

**Gaps**:
1. **Historical preset library missing 3 crises**: COVID recovery (Apr-Jun 2020), Taper tantrum (Jun 2013), EM crisis (Aug 2015). Only GFC, COVID crash, Rate shock 2022, Liberation Day implemented.
2. **Clayton copula computed but NOT used for reverse stress** (`feature_08.py:71-87`). The reverse stress shock vector is still computed from the linear covariance approach (beta_lev × direction). The Clayton copula provides `theta` and `lower_tail_dependence` but these values are only attached to the output rows, not used to condition the return distribution given a vol shock.
3. **Adversarial scenario searches discrete 30-day windows** (`analytics.py:1261-1279`), NOT the spec's projected gradient ascent continuous optimization.
4. **Historical analog uses fixed 30-day windows stepping every 21 days** — non-overlapping means the closest window may be missed.
5. **Contagion VAR lags not configurable** from payload (hardcoded 5).

**Bugs/Issues**:
- Historical analog covariance matrix (`feature_08.py:56-57`): `np.nan_to_num(cov_analog, nan=0.0) + np.eye * 1e-8`. If `cov_analog` has NaN entries, setting them to 0 silently shrinks the covariance structure.
- Leverage effect proxy (`feature_08.py:71`): `ret.rolling(63).corr(ret.mean(axis=1))` computes correlation of individual asset returns with the equal-weighted portfolio. The spec wants Feature 3's HAR-leverage coefficient β_lev.
- GLASSO analogs (`analytics.py:1231-1258`): fixed `alpha=0.1`, not BIC-selected ρ as spec demands.
- Adversarial scenario (`analytics.py:1261-1279`): searches one window every 5 trading days — may miss the optimal window. The window average approach blurs the macro state.
- Multi-scenario comparison (`feature_08.py:117`): recovery time = `21 * vol_mult` — this is a purely arbitrary formula.

**Score**: **6/10**

---

### Feature 09 — Portfolio Volatility Budget Monitor

**Spec targets**: Portfolio vol = w'Σw. MRC computation. Vol targeting λ_scale. Regime-conditional target. Outputs: portfolio vol dashboard, vol-to-target gap, budget attribution waterfall, scaling factor history, regime-conditional target evolution, rebalancing recommendation, historical backtest. Upgrades: two-step rebalancing, Almgren-Chriss market impact, Kelly-criterion targeting.

**Implemented**: Portfolio vol from DCC. MRC. Vol targeting. Regime-conditional target (calls Feature 04). Two-step rebalancing (uniform + KKT QP). Almgren-Chriss costs. Kelly target. Historical backtest (gross + net of costs). Budget breach detection.

**Gaps**:
1. **Forward vol forecast source**: DCC only. Spec wants GARCH (Feature 2) and EWMA as alternatives.
2. **Rebalancing trigger**: daily only. Spec wants weekly and signal-triggered options.
3. **No flat bps vs Almgren-Chriss side-by-side comparison** as spec demands for the upgrade.
4. **No backward-looking comparison** of regime-conditional target vs fixed target in the backtest.
5. **Transaction cost comparison** not displayed — only Almgren-Chriss costs are computed.

**Bugs/Issues**:
- **Critical lookahead bias in backtest** (`feature_09.py:59-61`): `rolling_vol = (ret @ weights).rolling(21).std() * sqrt(252)`. Then `scaling_factor = target / rolling_vol`. This uses the realized portfolio vol over the NEXT 21 days to compute today's scaling factor. The spec says to use σ̂_{p,t+1}, the 1-day-ahead portfolio vol forecast from the DCC system. This is the single most important bug in Feature 09 — it makes the backtest results unreliable.
- Kelly target (`feature_09.py:58`): uses `(ret.tail(252).mean() @ weights) * 252` — the simple 252-day historical mean return, NOT the BTZ-implied expected return from Feature 5.
- Calls `run_regime()` (`feature_09.py:24`) — this runs the ENTIRE Feature 04 pipeline (HMM fits, SJM, EW-EM, Weibull duration) on every call. Massively expensive. Should cache.
- Iterative budget alignment loop (`feature_09.py:42-48`): hand-rolled multiplicative update with no convergence guarantee. The two-step KKT rebalance at line 52-55 is the proper approach — the iterative loop duplicates this with a heuristic.
- Two-step KKT: the `A` matrix (`analytics.py:1290`) uses `inv @ ones` where `inv = cho_solve(...)` is the full inverse matrix. `cho_solve` factors + solves — this computes the full inverse which is O(n³). Using `cho_solve(inv_fac, ones)` would be O(n²). Minor but unnecessary cost.

**Score**: **5/10**

---

## 3. Shared Infrastructure Audit

### `analytics.py` (1,495 lines) — Core Computation

**Strengths**:
- Well-organized with ~95 functions covering the full feature surface
- Consistent use of numpy arrays for performance
- Clean JSON serialization (`clean_json`, `compact_records`)
- LRU-cached `macro_frame()` with intelligent column renaming
- Bounded caches for primitives, MLE states, and GARCH results
- Proper error boundaries on all model fits

**Issues**:
- Yang-Zhang formula for crypto assets silently falls back to Rogers-Satchell (`analytics.py:337-338`) — documented but no user alert
- Parkinson estimator has undocumented multiplier `1/(1 - 390^(-0.5))` (`analytics.py:333, 387`)
- `covariance_methods()` mislabels EWMA as DCC (`analytics.py:807`)
- `model_confidence_set()` (`analytics.py:537-556`) — correct algorithm but `boot_means.max(axis=1) - boot_means.min(axis=1)` uses the range of bootstrap means as the null distribution, which is the correct MCS approach (T-max statistic)
- `fit_var()` (`analytics.py:811-831`) — incorrect BIC formula: `(math.log(len(Y)) * (Y.shape[1] * Y.shape[1] * p + Y.shape[1])) / len(Y)`. The standard BIC is k×ln(T) − 2×ln(L̂). The formula used mixes the dimension with log(T)/T but double-counts the intercept term. The BIC values will be systematically off, though for model selection (choosing p) the rank order may still be correct.

### `data_loader.py` (93 lines) — Data Access

- Polars pushdown for ticker filtering: good
- joblib disk cache for repeat loads: good
- LRU-cached full market and macro loads: good
- Missing: `load_category7_macro` doesn't filter by date range — all features load the full macro history
- When Polars is unavailable, `ohlcv_for_symbols` falls back to loading the entire parquet then filtering in pandas — this is a critical performance cliff

### `data_pooling.py` (146 lines) — Data Acquisition

- Yahoo Finance fetcher via `yfinance` — correct
- FRED fetcher without API key (scrapes CSV endpoint) — clever, but fragile
- `missing_data_report` for gap analysis — good utility
- No write operations in runtime code path (append-only) — correct per design

### `performance.py` (321 lines) — JIT Kernels

- All critical hot paths have JIT implementations with numpy fallbacks
- Kernels: NW variance, Viterbi, autocorrelation, rolling percentile, GARCH loop, Realized GARCH NLL, DCC NLL, stationary bootstrap, VAR MA, generalized FEVD, OLS HAC
- Numba cache directory set to `/tmp/numba_cache_vol_v2` — safe
- Stationary bootstrap uses global numpy RNG inside JIT (`np.random.seed(seed)`) — this creates thread-safety issues with `prange` in the caller
- Building: the design is correct and well-executed

### `contracts.py` — RESOLVED

The original review found this file empty despite:
- `_stub.py:7` importing `from app.services.volatility_v2.core.contracts import contract_for`
- `README.md` checklist marking "[x] Added explicit contract file listing required data and planned outputs per feature"
- The spec requiring data maps (required/free sources/frequency) and output manifests per feature

`contract_for()` and `all_contracts()` are now implemented with isolated contracts for Features 01 through 09.

### `registry.py` (49 lines)

- Clean dataclass-based registry
- Dynamic import via `importlib`
- `run_feature()` dispatcher — correct
- Frozen dataclass for immutability: good
- Z-fill normalization for feature IDs: good

### API Wiring — RESOLVED

The service is mounted from `backend/main.py` through `backend/app/api/volatility_v2.py` under `/api/labs/volatility/v2`.

---

## 4. Overall Assessment

### Total Lines of Backend Code
- **3,215 lines** across 18 files
- Core analytics: 1,495 lines (46%)
- Performance JIT kernels: 321 lines (10%)
- 9 feature runners: 962 lines (30%)
- Supporting infrastructure: 437 lines (14%)

### Missing Functions/Models from Spec

| Item | Spec Requirement | Status |
|------|-----------------|--------|
| Bandi-Russell (correct formula) | σ²_BR = σ²_PARK − 2×η²_t | Wrong formula (different heuristic used) |
| Nyblom parameter stability test | L = T^(-2) × tr[Σ̂^(-1) × Σ_t (Σ_s ∂ℓ_s)] | Crude chunk-stddev approximation |
| Regime-conditional NIC (percentile-based) | 10th/50th/90th percentile σ²_{t-1} | Fixed multipliers 0.75/1.0/1.35 |
| Feature 4 regimes wired into Feature 5 BTZ | p_composite[low-vol] > 0.6 | YZ rank < 0.35 used instead |
| Feature 4 regimes wired into Feature 7 crisis | Σ p_composite(t)[high-vol] × εε' | Rank of abs returns used |
| VSTOXX/VFTSE/JNIV support | Non-US vol index pairs | Not implemented |
| Cross-asset VRP mode | Multi-pair simultaneously | Not implemented |
| BIC-selected Graphical LASSO ρ | ρ by BIC | Fixed α=0.1 |
| Adversarial scenario (gradient ascent) | Projected gradient | Discrete window search |
| Clayton copula for reverse stress mapping | P(r < r* | Δσ > shock) | Copula computed but not used |
| Forward vol forecast for backtest | σ̂_{p,t+1} from DCC | Uses realized 21-day rolling vol (lookahead bias) |
| BTZ-implied Kelly return | μ̂_p,t from Feature 5 | Uses 252-day historical mean |
| `contract_for()` function | Required data/output contract | Does not exist |
| DCC-MIDAS integrated | Long-run target in DCC recursion | Static matrix, not integrated |
| OGF auto-routing | Demote/promote YZ vs RS | Not implemented |
| 3 missing historical presets | COVID recovery, Taper tantrum, EM crisis | Not implemented |
| VaR coverage customization | 95%/99%/99.5% | 99% hardcoded |
| Forecasting horizon customization | Multiple horizons spec | Defaults only |

### Data Dependency Gaps

Per README and `missing_data_report`:
- VIXCLS availability in `category7_macro_regime.parquet`: **not verified**
- DGS2, DGS10 columns: **not verified**
- BAA/credit spread fields: **not verified**
- Cross-asset benchmark coverage (FX, commodities, BTC/ETH): **not verified**
- Portfolio weight persistence for Feature 09: **not implemented**

### Code Quality Rating

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Structure/Architecture | 8/10 | Clean modular design, mirrors Factors V2 |
| NumPy vectorization | 8/10 | Good use of einsum, sliding_window_view |
| JIT optimization | 9/10 | Excellent performance layer with numba fallbacks |
| Error handling | 7/10 | Consistent try/except on model fits |
| Input validation | 6/10 | Inconsistent payload key parsing, fragile fallbacks |
| Math correctness | 5/10 | Bandi-Russell wrong, Parkinson inflated, lookahead bias in F09 |
| Spec compliance | 5/10 | Every feature has meaningful gaps from spec |
| Test coverage | 1/10 | No test files found in the package |
| Documentation | 6/10 | Good docstrings, README, but 0-line contracts.py |
| Frontend wiring | 2/10 | Frontend exists but not connected to any API |

### Overall Rating: **5/10**

### Top 10 Critical Fixes Needed

1. **`contracts.py` is empty** — `_stub.py` imports `contract_for()` from it. This will crash if any code path triggers it. Either implement the function or remove the import.

2. **Feature 09 lookahead bias** (`feature_09.py:59`): the backtest uses rolling 21-day realized vol for scaling, not the 1-day-ahead DCC forecast. This invalidates all backtest metrics (Sharpe, drawdown, Calmar). Replace `rolling_vol = (ret @ weights).rolling(21).std()` with the DCC 1-day portfolio vol forecast.

3. **Bandi-Russell formula wrong** (`analytics.py:864-882`): the spec formula is σ²_BR = σ²_PARK − 2×η²_t with η² from squared return autocovariance. The implementation uses a completely different heuristic `(0.62*CC + 0.38*HL) * (1 + noise_penalty)`.

4. **Parkinson estimator has undocumented multiplier** (`analytics.py:333, 387`): the `(1.0 / (1.0 - 390.0 ** -0.5))` factor is about 1.025, which systematically inflates all Parkinson-based estimates by ~2.5%. Either document or remove if unintended.

5. **Regime-conditional NIC uses fixed multipliers** (`feature_02.py:66`): the 0.75/1.0/1.35 scaling is arbitrary. Replace with data-driven percentiles of the σ²_{t-1} history distribution.

6. **Feature 5 regime-conditional BTZ uses wrong conditioning** (`feature_05.py:104-106`): uses YZ rank percentiles instead of Feature 4 regime probabilities. This means the regime-conditional BTZ output does not reflect actual volatility regimes.

7. **Feature 7 crisis correlation uses wrong weights** (`feature_07.py:36-38`): uses rank of absolute returns instead of Feature 4 p_composite[high-vol] regime probabilities. Inconsistent with the spec's probability-weighted crisis correlation.

8. **Nyblom stability test is not implemented** (`feature_02.py:117-130`): the chunk-stddev heuristic has no theoretical basis. The actual Nyblom (1989) statistic with score vectors and Hansen critical values is in the spec.

9. **Feature 5 VIX fallback** (`feature_05.py:38`): when VIX data is entirely missing, VIX is approximated as `yz_vol × 1.15`. This creates a circular dependency where VRP ≈ yz_vol × 1.15 - yz_vol = 0.15 × yz_vol. The VRP loses all independent information content.

10. **Feature 8 Clayton copula not used in reverse stress** (`feature_08.py:71-87`): the copula is computed and theta/lower_tail_dependence are attached to output rows, but the actual reverse stress shock calculation still uses the linear leverage proxy. The whole point of the upgrade is the nonlinear Clayton copula mapping.
