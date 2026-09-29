# ML V2 — Comprehensive Spec Compliance Audit

## Resolution Checklist

Updated 2026-07-12. This checklist is the implementation status source of truth. A checked item is either fixed or deliberately excluded under the requested compute and user-value rule.

### Fixed

- [x] F01: corrected Deflated Sharpe Ratio (DSR) sampling variance and made the result a probability.
- [x] F01: replaced parametric Probability of Backtest Overfitting (PBO) approximation with the empirical fraction below the median path.
- [x] F01: replaced fabricated embargo penalties with real embargo-specific validation reruns.
- [x] F01: added Linear Support Vector Regression (SVR), Multilayer Perceptron (MLP), and CatBoost contract options.
- [x] F02: stopped assigning nonzero ensemble weight to models with zero Information Coefficient (IC), except equal weighting when every model has nonpositive IC.
- [x] F02: made multidimensional coefficient importance aggregation safe.
- [x] F04: replaced process-randomized ticker hashes with deterministic BLAKE2 hashes.
- [x] F04: removed the forward-return leakage fallback from meta-probabilities.
- [x] F08: replaced the constant-like IC Information Ratio formula with rolling IC mean divided by rolling IC standard deviation.
- [x] F10: corrected Roll spread to use lag-one return autocovariance rather than differenced returns.
- [x] F10: made `signal_families` selection control the signals actually evaluated.
- [x] API: exposed ML V2 feature discovery and execution at `GET /api/ml/v2/features` and `POST /api/ml/v2/features/{feature_id}/run`.
- [x] Validation: Python compilation and focused mathematical/model checks pass.

### Intentionally skipped: intrinsically compute-heavy and not required for normal user requests

- [x] F02/F11/F12: broad Optuna hyperparameter searches.
- [x] F03: GARCH-Informed Neural Network (GINN) training and deep sequence research models.
- [x] F05: Proximal Policy Optimization (PPO) reinforcement-learning rebalancing.
- [x] F07: large recurrent-model Dynamic Model Averaging (DMA) libraries.
- [x] F11: repeated LightGBM nuisance tuning for every cross-fit and rolling slice; the deterministic Ridge path remains the realtime default.
- [x] F12: full PatchTST, iTransformer, and Temporal Fusion Transformer training plus real transformer attention extraction.

### Not implemented because they require external data, uploaded artifacts, or product decisions

- [x] User-model, event-time, label-file, and custom-exclusion uploads.
- [x] Live Federal Reserve Economic Data (FRED), earnings-calendar, and other network data acquisition.
- [x] Cross-feature persistent strategy routing and frontend controls.
- [x] Exact Global Industry Classification Standard (GICS) constraints where the local universe lacks complete classifications.

### Completed realtime enhancements

- [x] Full Black-Litterman posterior integration with configurable views, tau, asset bounds, sector caps, and linkage selection.
- [x] Dynamic and side-specific triple barriers with purged out-of-fold meta-model validation and probability, Kelly, or binary position sizing.
- [x] HAR-X/HAR-ML integration with peer volatility, available macro features, ElasticNet selection, and direct multi-horizon forecasts.
- [x] Rolling monthly IC ensemble weights; fabricated SHAP beeswarm and waterfall values were removed, while capped exact TreeSHAP remains available when supported.
- [x] Pair-specific Kalman process/observation-noise maximum-likelihood estimation and copula-calibrated threshold integration.
- [x] Performance: corrected array cache-key construction, including shape, dtype, and boundary samples, to prevent collisions without hashing full arrays.

**Audit Date**: 2026-07-10
**Spec Source**: `/Users/adityabalaji/Downloads/quant  2/ml_final_features.md` (644 lines, ~12 features)
**Implementation**: `backend/app/services/ml_v2/` (~4,718 lines across 17 files)
**API (old/separate)**: `backend/app/api/ml_api.py` (1,081 lines — not wired to V2)

---

## 1. Total Lines of Code

| Component | Lines |
|---|---|
| `core/analytics.py` | 2,873 |
| `core/data_loader.py` | 313 |
| `core/data_fetcher.py` | 68 |
| `core/performance.py` | 524 |
| `features/feature_01.py` | 98 |
| `features/feature_02.py` | 78 |
| `features/feature_03.py` | 70 |
| `features/feature_04.py` | 63 |
| `features/feature_05.py` | 69 |
| `features/feature_06.py` | 68 |
| `features/feature_07.py` | 71 |
| `features/feature_08.py` | 81 |
| `features/feature_09.py` | 67 |
| `features/feature_10.py` | 64 |
| `features/feature_11.py` | 67 |
| `features/feature_12.py` | 68 |
| `registry.py` | 57 |
| **Total (ML V2 only)** | **~4,718** |
| `api/ml_api.py` | 1,081 (old ML system, not wired to V2 — see Section 6) |

---

## 2. Per-Feature Audit (F01–F12)

### F01 — Purged K-Fold and CPCV Engine — Score: **7/10**

**Spec targets** (spec lines 9–50): Purged K-Fold with embargo period E, CPCV with N groups (4/6/8) and k test groups (1/2), full CPCV Sharpe distribution, Deflated Sharpe Ratio (proper Bailey-López de Prado), Probability of Backtest Overfitting, DSR+PBO joint decision panel, embargo sensitivity table at E=0/5/10/21, per-fold performance table, label fractional uniqueness audit, model performance vs. embargo chart, backtest path envelope. 12 model types supported (XGBoost/LightGBM/CatBoost/RF/Extra Trees/Ridge/LASSO/ElasticNet/Linear SVM/MLP/user upload). Triple-barrier labels and custom label CSV upload.

**Implemented** (`analytics.py:596–699`, `feature_01.py`):
- Purged K-Fold with embargo ✓
- CPCV combinatorial path generation with C(N,k) splits ✓
- Naive vs. purged leakage-bias comparison ✓
- Deflated Sharpe Ratio ✓
- PBO ✓
- DSR+PBO joint decision panel with verdict ✓
- Backtest path envelope (semi-transparent equity curves) ✓
- Embargo sensitivity table at E=0/5/10/21 ✓
- Per-fold performance table ✓
- Label fractional uniqueness audit (simplified) ✓
- Model performance vs. embargo chart ✓

**Gaps**:
- **DSR formula is wrong** (`analytics.py:452–460`): Uses an approximation `expected_max = (1-γ)·Φ⁻¹(1-1/m) + γ·Φ⁻¹(1-1/(m·e))` then `(SR - expected_max) / √σ²`. The spec demands the proper Bailey-López de Prado DSR = Prob(SR̂ > SR₀) where SR₀ accounts for M trials via the extreme value distribution of Sharpe ratios under the null. The variance term at line 459 `max((1+0.5·SR²)/(n-1), σ_SR² / m, 1e-12)` takes a max of two different variance estimates — this is not correct. Proper DSR variance is `(1 + 0.5·SR̂²) / (T-1)` only, not a max with empirical variance.
- **PBO uses parametric approximation** (`analytics.py:463–474`): Custom logit-rank-loss approximation instead of the spec's simple definition: "fraction of CPCV backtest paths that underperform the median path." The implementation uses `stats.norm.cdf(0, loc=mean(logits), scale=sd(logits))` which assumes logistic-normal. When `sd ≤ 1e-12`, it falls back to `mean(ranks < 0.5)` which is correct. But the main path is an overcomplicated parametric approximation where the spec wants the direct empirical fraction.
- **No triple-barrier label support** despite being listed in `INPUT_CONTRACT` `label_type` options (`feature_01.py:46`). Only regression returns are used.
- **Only 6 model types in regression**, not 12 — no Linear SVM, no MLP. The `_fit_base_model` at line 477 only supports ridge/lasso/elastic_net/xgboost/lightgbm/catboost/random_forest/extra_trees — missing Linear SVM, MLP.

**Bugs/Issues**:
- `analytics.py:459`: `sr_std * sr_std / max(m, 1)` — `m` here is `trials`, not the number of observations. This term divides empirical std of trial SR by number of trials, which is conceptually wrong for DSR variance.
- `analytics.py:648`: `for j, group_ids in enumerate(combinations(range(n_groups), min(k_test, n_groups - 1)), start=1)` — When k_test = 1, this selects min(1, n_groups-1) = 1 group. But the spec says "k=2 generates the maximum number of paths" — this means k_test should normally be 2. When k_test=2 and n_groups=6, C(6,2)=15 paths. But at line 611, `k_test = min(2, n_groups-1)` — this caps correctly.
- `analytics.py:652`: `mask[max(0, lo - horizon): min(len(x), hi + embargo + horizon + 1)]` — purging starts `horizon` days before the test fold and extends `embargo + horizon` after. This uses the same `horizon` as prediction horizon. The spec says purge removes observations whose "label-formation windows overlap" — this is horizon for regression, but for triple-barrier, the label-formation window = max_holding_period, not prediction_horizon. For regression this is approximately correct.
- `analytics.py:673`: `embargo_rows` simply adjusts purged_scores by `-0.015 * max(e - embargo, 0)` — a hardcoded penalty. This is not re-running CPCV at each embargo value as the spec demands. The spec wants a proper CPCV re-run at each embargo value to show the true sensitivity.

---

### F02 — Gradient-Boosted Tree Alpha Engine — Score: **5/10**

**Spec targets** (spec lines 53–99): XGBoost, LightGBM, CatBoost, RF, Extra Trees with IC-weighted ensemble. Full SHAP attribution via TreeExplainer (exact Shapley values). SHAP beeswarm, waterfall per stock, ICE plots. Rolling IC time series, IC decay by horizon (1/5/21/63/126/252 days), Bayesian hyperparameter landscape via Optuna TPE sampler. Sample weighting (equal/time decay/uniqueness-weighted). Microstructure factor library (Amihud, Roll, Volume Ratio, Turnover, Dollar Vol Momentum, Volume Surprise) and higher-moment factor library (MAX, 52-week high proximity, realized skewness/kurtosis, IVOL). Corwin-Schultz spread. Universe filter by GICS sector / market cap decile / volume. Prediction target supports regression, binary, quintile, triple-barrier.

**Implemented** (`analytics.py:702–841`, `feature_02.py`):
- Ridge, RF, Extra Trees, GBM ✓
- XGBoost, LightGBM, CatBoost when installed ✓
- IC-weighted ensemble with per-model weights ✓
- Prediction rank table ✓
- Feature importance via model importances/coefficient magnitudes ✓
- Long-side and short-side importance proxies ✓
- Capped exact TreeSHAP sample importance ✓
- IC decay profile across 1/5/21/63/126/252 horizons ✓
- Rolling monthly IC series ✓
- ICE partial dependence plots ✓
- Hyperparameter landscape (3×3 grid, not Optuna) ✓
- Signal-to-portfolio stats ✓
- SHAP beeswarm proxy ✓
- SHAP waterfall proxy ✓
- Prediction distribution and top-bottom spread ✓

**Gaps**:
- **No Optuna Bayesian tuning**: The spec says "Bayesian optimization via Optuna (user sets trial count and objective metric; Optuna's TPE sampler)." The implementation uses a hardcoded 3×3 grid of `GradientBoostingRegressor` at line 567 (`for depth in [2,3,4]: for lr in [0.025, 0.05, 0.08]`). This is not Optuna, not configurable, and only applies to one model family.
- **SHAP output is fabricated for most charts**: The beeswarm proxy (`analytics.py:815–823`) uses `shap_proxy` (which is `feature_importances_` or `coef_`, not actual SHAP values) and generates fake sign patterns via `((-1) ** i)`. The waterfall (`analytics.py:824`) also uses `mean_abs_shap` from the proxy. Only the capped `exact_shap_sample_importance` at line 780 uses real TreeSHAP. This is acknowledged in metadata ("shap_mode: capped_exact_shap_when_supported_else_importance_proxy") but frontend consumers cannot distinguish real SHAP from proxy.
- **No microstructure factor library toggle**: The spec has detailed toggle controls for Amihud, Roll spread, Volume Ratio, Turnover, Dollar Vol Momentum, Volume Surprise (spec lines 77–79). These are in the shared feature panel but not togglable via F02 input contract.
- **No higher-moment factor library toggle**: The spec has MAX factor, 52-week high proximity, realized skewness/kurtosis, IVOL (spec line 78). Some exist in panel but not user-selectable.
- **No sample weighting**: Spec offers equal / exponential time decay / uniqueness-weighted. Implementation uses no weighting — all OLS/GradientBoosting samples are equally weighted (line 499: `model.fit(x_train, y_train)`).
- **No universe filter**: Spec has GICS sector filter, market cap decile, min volume, custom exclusion list. Not implemented.
- **IC-weighted ensemble limited**: Uses only weights from the single train/test split. The spec says "IC-weighted ensemble dynamically reweights each model family daily on recent predictive accuracy." Rolling window IC update is not implemented — only one-shot split.

**Bugs/Issues**:
- `analytics.py:744`: `r["ensemble_weight"] = float((r["ic_weight"] or 1.0 / len(perf)) / total_ic)` — when `ic_weight` is 0.0, the `or` gives `1.0/len(perf)`, then divides by total_ic. This means failed models (IC=0) still get weight `(1/n)/total_ic` instead of 0. The intent is to give them a minimal non-zero weight, but this inflates weak models.
- `analytics.py:758`: `importances = np.abs(np.asarray(best_model.coef_, dtype=float))` — for linear models with multiple targets or multi-class, `coef_` can be 2D. This would incorrectly ravel or produce wrong shape.
- `analytics.py:773`: `scale = scale / max(float(scale.sum()), 1e-12)` — side importance (long/short) uses `base_importance * (0.5 + scale)`. The `scale` is the mean absolute feature value for that side, normalized. This heuristic has no theoretical justification — the spec wants proper per-side SHAP decomposition.
- `analytics.py:788–801`: IC decay re-fits a new model for each horizon using `make_feature_panel(ctx, horizon=h)`. Despite the comment "reuse the already-fitted best model," it still calls `make_feature_panel` for each of 6 horizons, which rebuilds the entire feature panel from scratch. The model at line 797 `_fit_base_model(best_name, h)` is a new fit each time.

---

### F03 — Multi-Horizon Volatility Forecasting Engine — Score: **5/10**

**Spec targets** (spec lines 102–151): Four model families in parallel — HAR (Corsi 2009), GARCH family (GARCH/EGARCH/GJR-GARCH/TGARCH with AIC selection), GINN (LSTM with GARCH-consistency loss), HAR-ML (HAR with cross-asset spillover features selected via ElasticNet/LightGBM). IC-weighted ensemble at each horizon updated on rolling QLIKE accuracy. Garman-Klass and Yang-Zhang estimators. Multiple forecast horizons 1/5/10/21/63/126/252 days. Cross-asset spillover network (Diebold-Yilmaz style). Jump component decomposition. Vol regime HMM classification. HAR-X exogenous features: VIX, yield curve slope, cross-asset spillovers, realized skewness/kurtosis, jump component, volatility risk premium. GARCH error distributions (normal/t/skewed-t/GED). GINN architecture config: LSTM hidden size 32–256, layers 1–3, λ slider 0–1, dropout 0–0.5. Mamba/PatchTST/CrossMamba deep sequence models. Deep sequence toggle research-mode only.

**Implemented** (`analytics.py:1058–1159`, `feature_03.py`):
- HAR-Ridge and HAR-GBM forecasts ✓
- Close-to-close, Garman-Klass, Yang-Zhang realized volatility ✓
- GARCH family (GARCH/GJR-GARCH/EGARCH/APARCH/FIGARCH) with AIC selection ✓
- News impact curve for best GARCH model ✓
- Bipower variation jump decomposition ✓
- Vol spillover network via ElasticNet ✓
- Vol HMM regime classification (3-state) ✓
- Batch universe vol heatmap ✓
- Rolling QLIKE ensemble weights ✓
- Macro overlay ✓
- Forecast error distribution ✓
- Volatility term structure ✓

**Gaps**:
- **GINN not implemented** (research-only): The GARCH-Informed Neural Network — an LSTM with GARCH-consistency loss — is absent. This is one of the four required model families. Listed as `research_only` in `feature_03.py:55` but the spec presents GINN as a primary model, not an add-on.
- **HAR-ML not implemented**: Spec requires HAR extended with cross-asset spillover features (VIX, yield curve, cross-asset vol) selected via ElasticNet or LightGBM. Implementation has `HAR-Ridge` and `HAR-GBM` (`analytics.py:1099`) — just 2 models, no exogenous features, no variable selection.
- **Only 2 models instead of 4 families**: The `models` dict at line 1099 only has `HAR-Ridge` and `HAR-GBM`. The spec requires HAR, GARCH, GINN, HAR-ML — four distinct families. GARCH is in `arch_family_vol_models` but as a separate diagnostic, not an integrated forecast.
- **No cross-asset spillover features in HAR**: Though `vol_spillover_network` exists at line 972, it's a separate diagnostic, not integrated as HAR-X inputs. The spec says HAR-X should include "VIX level, VIX term structure slope, yield curve slope, cross-asset realized vol spillover."
- **Term structure scaling is crude** (`analytics.py:1123`): `base * math.sqrt(h / 21)` — scales the 21-day HAR forecast by sqrt(h/21). This is not a proper multi-horizon forecast, just a scaled extrapolation.


**Bugs/Issues**:
- `analytics.py:1059–1060`: Asset detection falls back to `ctx.symbols[0]` if `asset` key not in payload — this may silently pick the wrong asset.
- `analytics.py:1088`: `s = s_close if len(s_close) >= 80 else (gk_series if len(gk_series) >= 80 else yz_series)` — silently falls back between estimators. User will not know which estimator was used.
- `analytics.py:1103`: Only 2 HAR models fitted. The GARCH ensemble exists separately at line 1130 and merging at line 1134–1135 simply appends GARCH rows to the errors list — not integrated into a unified forecast ensemble.
- `analytics.py:1121–1123`: Term structure is based on a single 21-day HAR forecast (base_model at line 1120), scaled by sqrt factor. This is not a proper term structure forecast at each horizon.
- `analytics.py:1134`: `errors.extend(...)` — appends GARCH rows with `mae: None, bias: None, correlation: None` to the error list. The `summary("Best MAE", min(r["mae"] for r in errors if r.get("mae") is not None))` at line 1139 will silently ignore GARCH in the MAE comparison.

---

### F04 — Meta-Labeling and Triple-Barrier Label Engine — Score: **7/10**

**Spec targets** (spec lines 154–199): Triple-barrier labeling with profit-taking (fixed/dynamic EWMA/ATR), stop-loss (same options, asymmetric), vertical barrier (max holding). Barrier side (bilateral/long-only/short-only). Price for checking (close only / high-low intraday). Meta-labeling with primary model (MA crossover/RSI/CUSUM/GBT output/user upload) and meta-model (LogisticRegression/RF/XGBoost/LightGBM) under Purged K-Fold. CQR for position sizing with calibration set size control (20%/30%). Conformalized prediction intervals per trade. Interval width distribution. CQR coverage audit. Barrier sensitivity surface. Regime-conditional label distribution.

**Implemented** (`analytics.py:1162–1368`, `feature_04.py`):
- Triple-barrier via high-low price path ✓
- Forward-return fallback when OHLCV path unavailable ✓
- Label distribution ✓
- Meta-labeling with LogisticRegression classifier ✓
- LightGBM quantile CQR with chronological conformal calibration ✓
- CQR interval width ✓
- CQR coverage audit (rolling empirical coverage) ✓
- Label method comparison (fixed/vol-scaled/tercile) ✓
- Barrier sensitivity surface ✓

**Gaps**:
- **No dynamic barriers**: Spec requires dynamic PT = N × EWMA vol or ATR-based. Only fixed percentage barriers are implemented (`analytics.py:1164–1165`).
- **No barrier side configuration**: Spec says bilateral/long-only/short-only. Only bilateral is implemented.
- **No high-low intraday path checking**: Spec says "price for barrier checking: close only OR high-low range intraday path check." The implementation uses high-low path (`analytics.py:1226–1277`) which partially addresses this, but the fallback uses close-only forward return.
- **No event time upload**: Spec says "user uploads event timestamps." No upload mechanism exists.
- **No meta-model validation under Purged K-Fold**: Spec says "each validated under Purged K-Fold from Feature 1." The meta-model at line 1194–1195 uses a simple 70/30 train/test split, not purged CV.
- **No primary model selection beyond momentum**: Spec allows MA crossover, RSI, CUSUM, GBT output, user upload. Only `momentum_sign` is used as primary (`feature_04.py:31`).
- **No position sizing integration**: Spec says position sizing = meta-model probability, Kelly-scaled, or binary threshold. None of these are output as tradable signals — just meta_probability in the DataFrame.

**Bugs/Issues**:
- `analytics.py:1186`: Meta-label target uses `(np.sign(labels["label"]) == np.sign(labels["forward_return"].fillna(0)))` — this compares the high-low path label's sign with the forward return sign. The spec says meta-label = 1 where primary model was profitable. Using `forward_return` (which is the _realized_ outcome) leaks the outcome into the meta-feature if not handled carefully. However, the features at line 1188–1190 don't include forward_return (only vol_21, label_abs, ticker_hash), so this is correct.
- `analytics.py:1190`: `hash(x) % 100 / 100.0` — Python's `hash()` is randomized across interpreter sessions (PYTHONHASHSEED). This produces different values in different processes, making the model non-deterministic. Should use `hashlib` or a fixed seed hash.
- `analytics.py:1200`: Fallback meta-probability when LogisticRegression fails: `1.0 / (1.0 + np.exp(-forward_return / vol_std))` — this literally leaks the forward return into the meta-probability, which is exactly what the comment at line 1180 warns against. The spec says explicitly: "not sigmoid of forward_return which leaks."
- `analytics.py:1246`: The loop start `for i in range(start, max(0, len(df) - horizon))` — when `max_events` is small relative to data, the loop starts near the end, losing most events. The intent is to get the last `max_events` valid events but the implementation silently drops early events without warning.

---

### F05 — Hierarchical Risk Parity Portfolio Optimizer — Score: **6/10**

**Spec targets** (spec lines 201–246): HRP with hierarchical clustering (Ward/single/complete/average), quasi-diagonalization, recursive bisection. Five covariance estimators (Sample/Ledoit-Wolf/OAS/EWMA/RMT-cleaned). Nested Clustered Optimization (NCO), HERC. Black-Litterman with view integration from F02 GBT predictions, τ slider (0.01–0.50). RL rebalancing (PPO agent, Kang-Tian 2025). Sector constraints, per-asset min/max weight. Tail dependence distance metric. Rolling cluster stability. View attribution backtest.

**Implemented** (`analytics.py:1499–1549` + `hrp_weights` at 1380, `nco_weights` at 1433, `herc_weights` at 1471):
- HRP with Ward linkage, quasi-diagonalization, recursive bisection ✓
- Covariance estimators: Ledoit-Wolf, OAS, EWMA, RMT-cleaned ✓
- NCO weights ✓
- HERC weights ✓
- Dendrogram records ✓
- Quasi-diagonalized covariance heatmap ✓
- Risk contribution decomposition ✓
- Tail dependence proxy matrix ✓
- Rolling cluster stability ✓
- Black-Litterman posterior return proxy ✓

**Gaps**:
- **Black-Litterman is a proxy, not full BL** (`analytics.py:1527`): `bl = pd.DataFrame({"asset": weights.index, "equilibrium_return": (cov @ eq_w).values, "posterior_return": (cov @ weights).values})` — the "posterior_return" is just `cov @ hrp_weights`, not a proper Black-Litterman posterior blending market equilibrium with view vectors, tau, and uncertainty. The BL comparison at line 1541 `"bl_hrp_proxy": float(min(0.25, v * 1.05))` is fabricated — hardcoded 5% boost capped at 25%.
- **No RL rebalancing**: Research-only proxy (`feature_05.py:55`), outputs a dummy placeholder row.
- **No sector constraints**: Spec requires "max weight per GICS sector." No sector constraint implementation.
- **No per-asset min/max weight**: Spec requires these as constraints. The optimizer at line 1518 uses only equal-weight bounds.
- **No BL τ control**: The spec has "slider 0.01–0.50." Not exposed.

**Bugs/Issues**:
- `analytics.py:1381–1382`: `corr = cov.corr().fillna(0.0) if cov.shape[0] != cov.shape[1] else cov.copy()` — if the matrix is already square, it's used as-is as correlation, which is wrong if the input is a covariance matrix. Line 1382 then overwrites with `cov / sqrt(outer(diag, diag))` — so the first line is dead code. Not a bug but redundant.
- `analytics.py:1433–1468` (NCO): `KMeans` on distance matrix `dist` — KMeans works on Euclidean distances, but `dist = sqrt(0.5 * (1 - corr))` is a valid Euclidean embedding (it's the angular distance). This is correct.
- `analytics.py:1521`: `rolling = pd.DataFrame(...)` with `rets @ weights` — the rolling 63-day Sharpe is computed on the full portfolio return series. For long-only HRP this is fine, but the spec expects comparison with Markowitz and equal-weight overlaid.
- `analytics.py:1540`: `"view_attribution_backtest": compact_records(rolling)` — this is just the HRP rolling Sharpe, not a proper view attribution backtest.

---

### F06 — Market Regime Detection and Adaptive Strategy Routing — Score: **7/10**

**Spec targets** (spec lines 248–287): Four parallel frameworks: Gaussian HMM (2/3/4 state, Baum-Welch), GMM on multi-variate feature space, Ensemble-HMM voting (XGBoost + RF + HMM majority vote), PCA structural break detector. HMM emissions: Gaussian/Student-t/Skewed-t. Random graph systemic risk indicator. Regime-conditional factor performance, vol term structure, strategy attribution. Regime-routing to F03/F05/F07. Erdős-Rényi random graph network density. PC1 explained variance with 35%/60% thresholds.

**Implemented** (`analytics.py:1552–1668`, `feature_06.py`):
- Gaussian HMM Baum-Welch with state reordering by mean return ✓
- Gaussian Mixture fallback ✓
- Transition probability matrix ✓
- PC1 structural break monitor ✓
- Regime-conditional factor performance ✓
- Strategy performance attribution by regime ✓
- Regime-conditional vol term structure ✓
- Random graph systemic risk indicator ✓
- Ensemble RF-vs-HMM agreement diagnostic ✓
- Parallel GMM regime probabilities ✓
- Regime factor forward IC ✓

**Gaps**:
- **Ensemble-HMM uses RF only**: Spec requires "XGBoost and Random Forest trained on labeled historical regimes combined with HMM state probabilities in a majority-vote ensemble." Only RandomForestRegressor is used (`analytics.py:1726`), and it's trained on HMM states as regression targets, not on labeled regimes. No majority-vote mechanism.
- **No regime-to-strategy routing**: Spec says "automatically route regime state to Feature 3, Feature 5, Feature 7." No cross-feature persistence mechanism exists. This is a platform-wiring issue.
- **No regime alert thresholds**: Spec says "alert when P(bear regime) > 0.65." Not implemented.

**Bugs/Issues**:
- `analytics.py:1555`: `feat = pd.DataFrame(...)` creates features from mean returns. The skewness and kurtosis at lines `skew` and `kurt` are computed on mean returns, which smooths out cross-sectional information.
- `analytics.py:1574–1591`: The HMM fitting tries covariance_type="full" first, falls back to "diag". If both fail, raises `hmm_error`. But `hmm_error` could be `None` if the try block never assigned it (though in practice both attempts at assignment). The fallback at line 1593 `raise hmm_error or RuntimeError(...)` handles this, but it's fragile.
- `analytics.py:1599`: State mean returns use `-np.inf` for empty states, then `order` sorts descending. The `state_mean_returns` list comprehension at line 1605 uses `raw_means[i] if math.isfinite(raw_means[i]) else 0.0` — so empty states get 0.0 return instead of being excluded or flagged.
- `analytics.py:1633–1637`: PC1 computation uses a rolling 63-day window but the step size is variable: `range(63, len(ctx.returns), max(1, len(ctx.returns)//160))`. For a 756-day dataset, this gives ~160 points. But the spec wants "PC1 explained variance of the full universe daily return cross-section; rolling window 21/63/126 days" — the step should be 1 day for a proper monitor.
- `analytics.py:1641`: `ensemble_result = ensemble_hmm_classifier(feat, states, n)` — this uses the full dataset (including future data relative to each state) to train the RF classifier versus the HMM states. The HMM was fit on all data (look-ahead), and the RF is then trained on all data to match HMM states, which means agreement_rate is double-counting look-ahead bias.

---

### F07 — Bayesian Online Learning and DMA Engine — Score: **7/10**

**Spec targets** (spec lines 289+): Model library of M models (XGBoost, LightGBM, CatBoost, RF, Ridge, ElasticNet, LASSO, LSTM, GRU, HAR, GINN, rolling mean, user upload — up to 20). DMA with forgetting factor λ (regime-conditional via F06). OBS (Waxman et al. 2026) with online convex optimization, formal regret guarantees. Distributional uncertainty (epistemic/aleatoric decomposition). Prediction calibration curve. Model pruning/reactivation log.

**Implemented** (`analytics.py:1766–1867`, `feature_07.py`):
- Candidate models: momentum, reversal, low-vol, Ridge, Extra Trees ✓
- Sequential DMA weight updates with forgetting factor ✓
- OBS simplex-projected online convex optimizer on Gaussian negative log-score ✓
- Live model weight dashboard ✓
- Weight evolution over time ✓
- DMA vs OBS vs static BMA comparison ✓
- Model pruning/reactivation log ✓
- OBS regret curve ✓
- Distributional uncertainty panel from model dispersion ✓
- Epistemic/aleatoric proxy ✓
- Forgetting factor half-life sensitivity ✓
- Regime-conditional λ via market vol percentile routing ✓

**Gaps**:
- **Limited model library**: Only 5 models (momentum, reversal, low-vol, ridge, extra_trees). Spec says up to 20 including XGBoost, LSTM, GRU, HAR, GINN, user upload.
- **No CatBoost, LightGBM, HAR, GINN in library**: Most of the spec's listed models absent.
- **No XGBoost/LightGBM as ensemble members**: These are available in F02 but not included in DMA library. The model library at `analytics.py:1772–1778` is hardcoded.
- **Distributional uncertainty is a proxy**: Spec requires "each model to output predictive distributions or bootstrapped prediction intervals." Implementation uses model dispersion percentiles (`analytics.py:1832–1833`: `np.nanpercentile(pred_vec, 5/95)`). This is reasonable but acknowledged as proxy.

**Bugs/Issues**:
- `analytics.py:1779–1780`: `lam = 0.97, eta = 0.01` — these defaults are reasonable but the input contract at `feature_07.py:31–32` lists different ranges (lambda 0.90–1.00, eta 0.001–0.1). The defaults are within range so this is cosmetic.
- `analytics.py:1786`: `warmup_errors = pred_matrix[20:max(40, min(...))] - y.iloc[...]` — uses first 20+ observations to estimate model sigma. This initializes model_sigma on the warmup period, which means the first 20 steps are skipped. The loop at `analytics.py:1799` starts at `t = 20`, so the first 20 observations are training-only. Fine for time series.
- `analytics.py:1803`: `likelihood = np.exp(-err / (np.nanstd(y.iloc[:t]) ** 2 + 1e-8))` — this is a Gaussian likelihood with variance estimated from the full history up to t. This is a reasonable approximation. But the scores at line 1808 use `gaussian_nll = 0.5 * log(2π·σ²) + 0.5 * ((y - pred)/σ)²` with model-specific σ — this is a proper negative log-score. The two are inconsistent: the DMA weight uses `exp(-err/σ²_global)` but the OBS score uses the per-model Gaussian NLL. This means DMA and OBS use different scoring rules. Not necessarily a bug, but may cause divergence between DMA and OBS weights.
- `analytics.py:1830`: `"epistemic_std": float(np.nanstd(pred_vec))` — the epistemic uncertainty is approximated as cross-model std. The spec wants proper decomposition into aleatoric (irreducible noise) and epistemic (model uncertainty). The "aleatoric" at line 1831 is `abs(realized - dma_pred)` — which is the residual, not aleatoric uncertainty.
- `analytics.py:1805`: `lam_eff = clip(lam - 0.04 * max(0, vol_pct - 0.7)/0.3 + 0.015 * max(0, 0.3 - vol_pct)/0.3, 0.88, 0.995)` — regime-adaptive λ: in high vol (pct > 0.7), λ decreases by up to 0.04; in low vol (pct < 0.3), λ increases by up to 0.015. The coefficients are hardcoded with no theoretical justification. This is reasonable but undocumented.

---

### F08 — Multi-Factor IC-Weighted Composite Signal Optimizer — Score: **7/10**

**Spec** (implied by README + general framework): Factor IC table, IC-weighted composite weights, sector-neutralized factors, Gram-Schmidt orthogonalization, walk-forward weight stability, long-short backtest, factor turnover, higher-order pairwise interaction screen, forward-selection Fama-MacBeth screen, elastic-net factor selection, AlphaForge dynamic weights, IC decay alerts, rolling composite IC.

**Implemented** (`analytics.py:2028–2103`, `feature_08.py`):
- Factor IC table with IC and IC-IR ✓
- IC-weighted composite weights ✓
- Sector neutralization via median subtraction ✓
- Gram-Schmidt orthogonalization ✓
- Walk-forward IC weights ✓
- Pairwise interaction screen ✓
- Forward-selection Fama-MacBeth ✓
- Elastic-net/Lasso factor selection ✓
- AlphaForge dynamic weights ✓
- IC decay alerts ✓
- Rolling composite IC ✓
- Composite signal distribution ✓
- Long-short backtest ✓
- Factor correlation heatmap ✓

**Gaps**:


**Bugs/Issues**:
- `analytics.py:2043`: `ic_ir = ic / max(abs(ic) * 0.5, 1e-4)` — IC-IR is approximated as `IC / (0.5 * |IC|)` = 2.0 for any non-zero IC. This means IC-IR is always ~2.0 regardless of the actual information coefficient variability. This is clearly wrong — IC-IR should be `mean(IC) / std(IC)`. The formula divides IC by half itself, giving a constant.
- `analytics.py:2044`: `ic_decay_ratio = ic_decay_ratio(x_neutralized[col], y)` — calls the function at line 2250 which properly computes short/long window IC. This is fine.
- `analytics.py:2060`: `walkforward_ic_weights(panel, y, factor_cols, window=252)` — the walk_forward_window default is 252 days. The function at line 2268 uses this to set the stride: `for i in range(window, len(dates), step)` with step=21. So walk-forward refits every 21 days with a 252-day window — reasonable.
- `analytics.py:2078`: `score = sum(x_neutralized[r["factor"]] * r["composite_weight"] for r in ic_rows)` — this computes the composite as a simple weighted sum of factor values. This is standard but the spec/input_contract also lists `zscore` and `signed_rank` options which are not implemented.

---

### F09 — ML-Enhanced Pairs and Statistical Arbitrage Engine — Score: **7/10**

**Spec** (implied by README + general framework): Pair candidate screen with correlation/OU half-life, Engle-Granger ADF p-value scoring, spread z-score time series, cointegration network, Kalman filter hedge ratio (random-walk beta), entry/exit signals, pair backtest equity, RL threshold policy, Johansen basket tests, sector-neutral pair selection.

**Implemented** (`analytics.py:2288–2355`, `feature_09.py`):
- Pair candidate leaderboard with correlation/OU half-life/ADF/score ✓
- Spread z-score time series ✓
- Cointegration network ✓
- Kalman filter hedge ratio path ✓
- Entry/exit signal timeline ✓
- Pair backtest equity ✓
- ADF p-value distribution ✓
- Pair preclusters ✓
- Copula entry thresholds ✓
- Pair network components ✓
- ML pair classifier scores ✓

**Gaps**:
- **Kalman filter uses simplified Q/R**: The `_kalman_hedge_ratio_path` at line 2358 uses hardcoded `q=1e-5` and `r=obs_var`. The spec says "estimate Q/R by MLE per pair and cache parameters by pair/window."

**Bugs/Issues**:
- `analytics.py:2313`: Pair score formula: `score = |z| * |corr| / max(half_life, 1) * (1.5 if p<0.05 else 1.0 if p<0.10 else 0.5)` — this boosts low-half-life (fast mean-reverting), high-correlation pairs with significant ADF. Reasonable heuristic, but the ADF multiplier creates a discontinuity at p=0.05 and p=0.10 boundaries.
- `analytics.py:2332–2334`: Fallback when Kalman fails uses log-spread with rolling 63-day z-score. This is fine but the fallback is silent — no metadata flag.
- `analytics.py:2344`: Entry/exit signal uses fixed |z|>2 threshold, which ignores the copula-based thresholds computed at line 2350.
- `analytics.py:2354`: `"pair_classifier": "fast_rule_score_no_training_labels"` — correctly documents that the "ML" classifier is just a heuristic score.

---

### F10 — Market Microstructure Signal Observatory — Score: **7/10**

**Spec** (implied by README + general framework): Microstructure IC leaderboard (Amihud, Roll spread, Corwin-Schultz, MAX, 52-week high, IVOL, volume surprise, dollar vol momentum, turnover). Amihud surface, Roll cross-section, MAX distribution, 52-week heatmap, IVOL sort, signal correlation, liquidity regime monitor, signal backtest, hl-Amihud vs standard Amihud, Amihud time surface.

**Implemented** (`analytics.py:2526–2635`, `feature_10.py`):
- Microstructure IC leaderboard with vectorized IC series ✓
- Amihud illiquidity surface ✓
- Roll spread cross-section ✓
- MAX factor distribution ✓
- 52-week high proximity heatmap ✓
- IVOL cross-sectional quintile sort ✓
- Volume surprise signal ✓
- Signal correlation matrix ✓
- Liquidity regime monitor ✓
- Signal backtest (long-short decile) ✓
- Corwin-Schultz spread cross-section ✓
- hl-Amihud vs standard Amihud ✓
- Amihud time surface (sector/month) ✓

**Gaps**:
**Bugs/Issues**:
- `analytics.py:2539–2541`: Roll spread formula `2*sqrt(max(0, -Cov(dr_t, dr_{t-1})))` — the rolling 22-window covariance computation `dr.rolling(22).cov(dr.shift(1).rolling(22))` is incorrect. Roll's spread requires the _autocovariance_ at lag 1, not a rolling covariance between the series and its lagged series. The correct expression is `-Cov(r_t, r_{t-1})` where `Cov` is the autocovariance. The implementation computes `Cov(Δr_t, Δr_{t-1})` where `Δ` diverges returns. This gives a different (and wrong) quantity. The spec says "Roll's Implied Spread (estimated bid-ask from negative serial covariance of daily returns: 2 × sqrt(max(0, −Cov(r_t, r_{t-1}))))" — the formula should use raw returns, not differenced returns.
- `analytics.py:2598`: `signals = ["amihud", "hl_amihud", "roll_spread", "corwin_schultz_spread", "max_factor", "high_52w_proximity", "ivol", "volume_surprise", "dollar_vol_momentum", "turnover_rate"]` — hardcoded, doesn't respect the user's `signal_families` selection from the payload.

---

### F11 — Causal Factor Discovery Engine — Score: **7/10**

**Spec** (implied by README + general framework): K-fold cross-fitted DML residualization for each factor. APE leaderboard with classification (Causal/Proxy/Spurious). Confounding bias decomposition (OLS IC - DML APE). APE time series. Spurious factor detection log. Nuisance model R² table. HC3 robust inference. Causal factor network (partial R² edges). DML vs OLS backtest comparison. Rolling spurious fraction.

**Implemented** (`analytics.py:2700–2755`, `feature_11.py`):
- K-fold cross-fitted DML for each factor ✓
- APE, SE, t-stat ✓
- Factor classification (Causal/Proxy/Spurious) ✓
- Confounding bias = OLS IC - DML APE ✓
- APE time series ✓
- Spurious factor detection log ✓
- Nuisance model R² ✓
- HC3 robust univariate inference ✓
- Causal factor network (partial R² proxy edges) ✓
- DML vs OLS backtest comparison ✓
- Rolling spurious fraction ✓

**Gaps**:
- **No LightGBM nuisance by default**: Uses Ridge for speed (`analytics.py:2706` default is "ridge"). Spec/README notes LightGBM nuisance is possible but not default.
- **No Optuna for nuisance models**: Research-only per `feature_11.py:52`.

**Bugs/Issues**:
- `analytics.py:2713`: Classification logic: "Causal" if `|t| > 1.96` AND `|bias| < |ols_ic| * 0.5 + 1e-6`. The second condition checks that confounding bias is less than half the OLS IC magnitude. If OLS IC = 0 and bias is tiny, this passes. If OLS IC = 0.10 and bias = 0.06, this rejects. Reasonable heuristic.
- `analytics.py:2721`: `"recommended_weight_adjustment": max(ape, 0.0)` — the recommended weight is capped at 0. This means negative APE (harmful factor) gets 0, not a negative weight. Skipping negative-APE factors is reasonable but should be documented as a design choice.
- `analytics.py:2730–2737`: APE time series recalculates DML for each sliding window. For 6 factors × 6 slices, this is ~36 full DML runs (each with 5-fold cross-fitting). This can be expensive.

---

### F12 — Deep Sequence Alpha Engine — Score: **5/10**

**Spec** (implied by README + general framework): Architecture comparison (PatchTST, iTransformer, TFT, GBT, MLP proxy). Multi-horizon IC decay. PatchTST attention heatmap, iTransformer cross-sectional attention map, TFT variable selection weights, integrated-gradients-style attribution. PatchTST vs iTransformer regime split. Ensemble contribution. Compute cost vs IC gain. Full deep training is explicitly research-mode.

**Implemented** (`analytics.py:2758–2838`, `feature_12.py`):
- Architecture comparison: GBT, MLP_proxy (Ridge), PatchTST_proxy (Ridge on patched features), iTransformer_proxy (ExtraTrees on cross-sectional features), TFT_proxy (RF) ✓
- Multi-horizon IC decay panel ✓
- PatchTST attention heatmap (data-derived lag-correlation diagnostic) ✓
- iTransformer cross-sectional attention map (correlation heatmap) ✓
- TFT variable selection weights (correlation-based) ✓
- Integrated-gradients-proxy attribution ✓
- PatchTST vs iTransformer regime split ✓
- Ensemble contribution chart ✓
- Compute cost vs IC gain (training_time proxy) ✓

**Gaps**:
- **No actual deep learning training**: All architectures are proxies (Ridge, RF, ET on transformed inputs). Spec/README states "full PatchTST/iTransformer/TFT training is not run in this backend pass."
- **Patched features are crude** (`analytics.py:2769–2775`): PatchTST proxy creates lagged mean/std of the cross-sectional mean. This is a single univariate time series, not the proper patch embedding of each asset's feature sequence.
- **iTransformer proxy is cross-sectional stats** (`analytics.py:2778–2784`): Creates z-scores and ranks of the feature panel at each date. This captures cross-sectional attention but has no temporal component, unlike the proper iTransformer which applies attention across both time and assets.
- **Attention heatmap** (`analytics.py:2841–2865`): `data_derived_attention` computes lagged Spearman correlations between feature means and target means. This is NOT attention — it's lagged cross-correlation. The spec wants actual transformer attention weights.

**Bugs/Issues**:
- `analytics.py:2773`: `feats[f"patch_{p}_mean"] = x_df.mean(axis=1).shift(lag)` — takes the mean across all assets, then shifts. This collapses the cross-section to a single series, losing all asset-level information. The spec's PatchTST operates on per-asset sequences.
- `analytics.py:2782`: `cs_rank = x_df.rank(axis=1, pct=True)` — cross-sectional percentile rank. This is fine as a feature transformation but is not a transformer attention mechanism.
- `analytics.py:2802`: `"training_time_seconds_proxy": float(len(x) * x_feat.shape[1] / 1e6)` — this is a fake compute proxy (N × features / 1e6). Not actual training time.
- `analytics.py:2830`: `"itransformer_cross_sectional_attention_map": matrix_records(ctx.returns.tail(126).corr())` — this is just the return correlation matrix, not an attention map.
- `analytics.py:2832`: `"patchtst_vs_itransformer_regime_split"` — uses hardcoded indices `perf[2]` and `perf[3]` which assume architecture ordering. If the dict order changes (Python 3.7+ preserves insertion order, so this works, but is fragile).

---

## 3. Shared Infrastructure Audit

### `core/analytics.py` (2,873 lines)

**Completeness**: Contains all feature runner functions and shared math. Features 01–12 all wire through here.

**Math Correctness Issues**:
- `analytics.py:459`: DSR variance formula uses `max()` of two different estimates — incorrect for proper DSR.
- `analytics.py:2043`: IC-IR is hardcoded to ~2.0 via `ic / (0.5 * |ic|)` — not a real IC-IR.
- `analytics.py:2540`: Roll spread uses differenced returns instead of raw returns — formula is wrong.
- `analytics.py:860`: Garman-Klass formula `0.5*(h-l)² - (2*ln(2)-1)*c²` — the coefficient `(2*ln(2)-1) ≈ 0.386`. The standard Garman-Klass is `0.5*(log(H/L))² - (2*log(2)-1)*(log(C/O))²` where H and L are high/low, C is close, O is open. The implementation uses `np.log(high/close.shift(1))` which is the _overnight-adjusted_ version. This is a valid variant (Yang & Zhang attribute this to Garman-Klass with overnight adjustment) but the standard Garman-Klass uses the current period's open, not the previous close.
- `analytics.py:864`: Yang-Zhang uses `k = 0.34 / (1.34 + (window+1)/(window-1))` — the standard Yang-Zhang k = 0.34 / (1.34 + (T+1)/(T-1)). This matches.

**Code Quality**:
- Heavy use of `clean_json` for type coercion — handles edge cases well but adds overhead.
- Most functions are well-structured with clear documentation.
- The feature runner pattern (normalize → run → merge_contract) is consistent.
- Some functions are very long (e.g., `run_gbt_alpha` is 140 lines, `run_dma_engine` is 100 lines) without internal helper extraction.

**Missing Error Handling**:
- `analytics.py:619`: `KFold(n_splits=max(3, min(k_folds, 10)), shuffle=False)` — no shuffle parameter validation. The spec doesn't mandate shuffle for time series, so this is correct.
- `analytics.py:719`: XGBoost import is tried, silently skipped on failure. Same for LGBM and CatBoost. This is documented and reasonable.
- `analytics.py:760`: `importances = np.ones(len(feature_names))` — if a model has neither `feature_importances_` nor `coef_`, equal importance is assumed. This could lead to misleading feature attribution.

### `core/data_loader.py` (313 lines)

**Data Source Coverage**: Reads from local parquet/CSV files only — no network fetching.
- Daily OHLCV: `market_universe.parquet` ✓
- Hourly OHLCV: `market_universe_hourly.parquet` ✓
- Fundamentals: `master_fundamentals.parquet` (sector, market cap, industry) ✓
- Macro/FRED: `category7_macro_regime.parquet` ✓
- Fama-French: FF3/FF5/Momentum daily CSVs ✓

**Gaps**:
- No VIXCLS / DGS2 / DGS10 from FRED directly — only available if `category7_macro_regime.parquet` contains them.
- No event/earnings calendar data — acknowledged as impossible without new data.
- No direct yfinance fetcher — `data_fetcher.py` documents the plan but doesn't execute it.

**Issues**:
- `data_loader.py:95`: `df["Ticker"] = df["Ticker"].map(normalize_symbol)` — applies to the entire DataFrame in-place. The ticker is normalized before return. This is fine.
- `data_loader.py:176–186`: The `returns_matrix` function uses `prices.shift(1)` then drops NaT rows. For hourly data, resampling to "1h" before computing returns is correct.

### `core/data_fetcher.py` (68 lines)

Intentionally inert — documents data sources but doesn't fetch. This is honest and deliberate. The `FRED_SERIES` dict and `YFINANCE_OPTIONAL` dict document exactly what would be needed for expansion.

### `core/performance.py` (524 lines)

**Strengths**: Excellent caching architecture with two-level LRU (memory + disk), blake2b cache keys, format-aware disk serialization (.npy/.json/.pkl), and vectorized implementations of sharpe/sortino/max_drawdown.

**Issues**:
- `performance.py:79–85`: `cache_key` with ndarray handling: the line `parts.append(str(a.shape).encode() + flat[:4].tobytes() ...)` is structured with chained `+` which may not evaluate as expected across the `if` conditions. Specifically, the `if len(flat) >= 4` guard applies only to the `flat[:4].tobytes()` part — the shape encoding is always appended, then if flat is long enough, first 4 and last 4 bytes are appended. This is mostly correct but the chained expression is confusing.
- `performance.py:295`: `ADFULLER = _try_import("statsmodels.tsa.stattools", "adfuller")` — pre-imported even though only used in one function. Minor overhead.
- `performance.py:503–517`: `_project_simplex` — there's a duplicate in `analytics.py:1870`. The analytics.py version shadows the performance.py import.

### `registry.py` (57 lines)

Clean, minimal registry. `run_feature(feature_id, payload)` dynamically imports the feature module. One minor concern: `importlib.import_module(f"app.services.ml_v2.features.{feature.module}")` — this assumes the import path `app.services.ml_v2.features.*`. This works for the current project structure.

### API Wiring: `ml_api.py` (1,081 lines)

**This is the OLD ML API, not ML V2.** It imports from `app.services.ml.*` (DatasetBuilder, SignalPredictor, EnsembleEngine, etc.) which are completely separate from the ML V2 module. There are zero references to `ml_v2` anywhere in this file.

The V2 features have no API endpoints wired. The README acknowledges this (`README.md:116`: "No API route or frontend wiring was added").

---

## 4. Overall Assessment

| Metric | Value |
|---|---|
| **Total LoC (ML V2)** | ~4,718 |
| **Total LoC (with old API)** | ~5,799 |
| **Feature files** | 12 (all expanded from stubs) |
| **Shared core files** | 4 (`analytics.py`, `data_loader.py`, `data_fetcher.py`, `performance.py`) |

### Missing Functions/Models from Spec

| Model / Function | Affected Feature | Severity |
|---|---|---|
| GINN (LSTM + GARCH-consistency loss) | F03 | Critical — one of 4 required model families |
| Optuna Bayesian hyperparameter tuning | F02, F11, F12 | High — spec presents as primary tuning method |
| Proper Black-Litterman with views | F05 | High — current output is fabricated proxy |
| Full deep architecture training (PatchTST/iTransformer/TFT) | F12 | High — feature name implies deep seq models |
| HAR-ML with cross-asset spillover features | F03 | High — replaces simple HAR-Ridge/HAR-GBM |
| Triple-barrier / binary labels in alpha engine | F02 | Medium — listed in input contract |
| Sample weighting (time decay / uniqueness) | F02 | Medium — spec input |
| Universe filter by sector/market cap/volume | F02 | Medium — spec input |
| Microstructure/higher-moment factor toggle | F02 | Medium — spec has detailed toggle table |

### Data Dependency Gaps

| Data | Affected Feature | Resolution |
|---|---|---|
| FRED VIXCLS, DGS2, DGS10 (live fetch) | F03, F06 | Possible via `data_fetcher.py` plan (not automated) |
| Ken French monthly/industry factors | F02 | Possible — FF3/FF5/Mom daily loaded |

### Code Quality Rating: **7/10**

**Strengths:**
- Consistent module structure across all 12 features
- Good separation of contract (feature files) from computation (analytics.py)
- Excellent caching infrastructure (performance.py)
- Honest documentation of limitations (README, feature metadata)
- Vectorized implementations with numpy instead of pandas loops in hot paths
- Thread-safe caching with proper memory budgeting
- Clean disk-cache layer with format-aware serialization

**Weaknesses:**
- analytics.py at 2,873 lines is too large — should be split into domain modules (volatility.py, portfolio.py, causal.py, dma.py, etc.)
- Several proxy/fabricated outputs masquerade as real (BL returns, SHAP beeswarm/waterfall, attention heatmaps)
- IC-IR formula at `analytics.py:2043` is mathematically wrong (always 2.0)
- Roll spread formula at `analytics.py:2540` uses wrong input (differenced returns vs raw returns)
- Some feature runners are very long monolithic functions with no internal decomposition
- No test files found for ML V2 (compile-clean check only)
- No cross-feature persistence layer — F02 predictions can't feed F05 BL views, F08 can't consume F11 DML weights

### Overall Rating: **6.5/10**

### Top 10 Critical Fixes

1. **Fix IC-IR formula** (`analytics.py:2043`): Currently `ic / (0.5 * |ic|)` = constant 2.0. Replace with proper `mean(IC) / std(IC)`.
2. **Fix Roll spread formula** (`analytics.py:2539–2541`): Use raw returns `r_t` not differenced returns `Δr_t` for autocovariance.
3. **Fix DSR formula** (`analytics.py:452–460`): Use proper Bailey-López de Prado DSR: Prob(SR̂ > max(SR_1, ..., SR_M)) under null, not the current approximation with `max()` over two variance estimates.
4. **Fix F02 SHAP proxy pollution** (`analytics.py:815–824`): The beeswarm and waterfall outputs use fabricated patterns. Either remove them or flag them prominently as "heuristic proxy, not SHAP."
5. **Remove meta-probability forward-return leak** (`analytics.py:1200`): The sigmoid fallback leaks `forward_return` into `meta_probability`. Replace with constant 0.5 or vol-based prior.
6. **Fix ticker_hash non-determinism** (`analytics.py:1190`): Python's `hash()` is randomized across sessions. Replace with deterministic hash.
7. **Remove fabricated Black-Litterman proxy** (`analytics.py:1527, 1541`): The "posterior_return = cov @ hrp_weights" and BL comparison with hardcoded 5% boost misrepresent functionality. Replace with proper BL or mark clearly as covariance-weighted proxy.
8. **Fix F02 side-importance heuristic** (`analytics.py:767–779`): The current `base_importance * (0.5 + scale)` has no theoretical basis. Replace with actual SHAP values restricted to long/short subsets, or clearly label as "prediction-weighted importance."
9. **Split analytics.py into domain modules** (2,873 lines): Extract vol forecasting (~300 lines), portfolio optimization (~300 lines), DMA (~250 lines), DML/causal (~200 lines), pairs (~200 lines), microstructure (~200 lines) into separate files under `core/`. This is essential for maintainability.
