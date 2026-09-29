# PCA V2 — Full Spec Compliance Review

## Remediation Checklist (2026-07-13)

- [x] F01: optional outlier modes (none, two winsorization bands, trimming, Huber), true raw covariance blending, and expanded audit metadata.
- [x] F02: Promax factor correlation matrix, AR(1) t-statistic, and genuine hierarchical-PCA cluster loadings.
- [x] F03: correct active-risk table wiring, historical tail VaR/CVaR contribution decomposition, and factor/benchmark correlations.
- [x] F04: residual-correlation diagnostics, OU parameter distributions, signal age/holding period, and volume-time comparison.
- [x] F05: rolling top-five eigenvalues, per-PC cosine drift, crisis bands, and regime summary output.
- [x] F06: 100-point optimization-based frontier, transaction-cost comparison, and RMT-versus-sample allocation comparison.
- [x] F07: residual bootstrap, selectable confidence level, full-spectrum bands, and full K-by-K subsampling stability matrix.
- [x] F08: rolling residual-correlation lambda-one series, historical percentile alert, and ten crisis annotations.
- [x] F09: true factor-correlation Mahalanobis distance, current factor Z-scores, shock percentiles, and 60-day analog summaries.
- [x] F10: Student-t EM crypto covariance, block-specific covariance assembly, cross-block shrinkage, unified RMT cleaning, block MP bounds, asset loadings, and factor returns.
- [x] F11: selectable illiquidity normalization, liquidity-driven correlation, augmented factor-risk decomposition, configurable ADV participation, and three-signal unwind monitoring.
- [x] API: V2 feature discovery and execution routes are wired under `/api/labs/pca/v2`.
- [x] Verification: Python compilation, focused math regression tests, and local-data smoke execution for features 01 through 11.
- [ ] Deliberately deferred: 500/1000-run default bootstrap, mixed-integer cardinality optimization, GPU paths, and exhaustive daily rolling refits. These remain opt-in or omitted because they add substantial compute cost without being necessary for the interactive user path.

> This checklist records the remediation state. The audit narrative below is the pre-remediation finding set retained for traceability.

## 1. Lines of Code Summary

| Component | File | Lines |
|---|---|---|
| Core analytics | `core/analytics.py` | 2,192 |
| Core cross-asset | `core/cross_asset.py` | 424 |
| Core data loader | `core/data_loader.py` | 342 |
| Core data pooling | `core/data_pooling.py` | 434 |
| Core performance | `core/performance.py` | 80 |
| Feature F01 | `features/feature_01.py` | 80 |
| Feature F02 | `features/feature_02.py` | 126 |
| Feature F03 | `features/feature_03.py` | 76 |
| Feature F04 | `features/feature_04.py` | 94 |
| Feature F05 | `features/feature_05.py` | 124 |
| Feature F06 | `features/feature_06.py` | 75 |
| Feature F07 | `features/feature_07.py` | 72 |
| Feature F08 | `features/feature_08.py` | 72 |
| Feature F09 | `features/feature_09.py` | 57 |
| Feature F10 | `features/feature_10.py` | 57 |
| Feature F11 | `features/feature_11.py` | 57 |
| Registry | `registry.py` | 56 |
| Package init | `__init__.py` | 19 |
| Features init | `features/__init__.py` | 2 |
| **Total backend** | **18 files** | **4,359 lines** |

Supporting files (not code):
| README | `README.md` | 182 |
| Existing audit (spec) | `audit.md` | 348 |
| Existing audit (code) | `audit code.md` | 1,231 |

Spec document: `pca features.md` — 919 lines

---

## 2. Per-Feature Audit (F01–F11)

### F01 — RMT Noise-Filtered Covariance Engine

**Spec targets**: 5 covariance estimators (Sample/LW/OAS/EWMA/MCD), MP threshold with iterative σ² fitting, 5 K-selection criteria, RMT-cleaned reconstruction (signal + diagonal idio), condition number comparison, outlier pre-processing (none/winsorize 1%/99% + 2.5%/97.5%/Huber/trimming), shrinkage blend slider, full audit trail JSON, 9 defined outputs.

**Implemented**: `rmt_model()` + `mp_threshold()` + `fit_mp_sigma2()` + `covariance_estimator()` + `choose_k()` + `preprocess_returns()` + `blend_covariance()`. All 5 estimators implemented. Iterative moment-matching σ² fitting (lines 256-260, 353-376). 5 K criteria (lines 230-242). Reconstruction (lines 264-266). Condition numbers computed (lines 25-27). Blend slider wired (line 44-45). 9 charts/tables returned.

**Gaps**:
- Outlier preprocessing only implements z-score winsorization (|z| > threshold, line 379-390). Spec requires 5 distinct methods: none, winsorize at 1%/99%, winsorize at 2.5%/97.5%, Huber M-estimation, trimming. Only z-score winsorization is present, no payload option to select method.
- z-score winsorization uses the same threshold for both tails (one parameter). Spec separates upper/lower quantiles.
- Huber M-estimation is entirely absent.
- Trimming path is absent.
- MCD path in `covariance_estimator()` falls back silently when T < N + 5 (line 186). Spec requires roughly T > 2N for reliability, but this is a minor data-constraint issue.
- Audit trail response from `metadata()` (line 1505-1522) returns symbols, dates, K criteria, mp parameters — but does not return the full audit trail the spec describes (retained eigenvectors, condition numbers before/after, q ratio, λ_max, σ²). Condition numbers are returned in the charts but not in the meta/audit_trail table structure the spec defines.

**Bugs/Issues**:
- Line 251: `bool(payload.get("outlier_filter", True))` — default is True, meaning outlier filtering is ON by default. This silently clips extreme returns without user awareness. Spec describes these as optional modes the user selects; having winsorization on by default will change results for any payload that doesn't explicitly pass `outlier_filter=false`.
- The `blend_covariance()` function (line 1529) reconstructs c_sample from raw eigenvectors — but these eigenvectors come from the *cleaned* estimator (e.g., LW/OAS), not the raw sample cov. Line 1547: `(raw_evecs[:, :n] * raw_evals[:n]) @ raw_evecs[:, :n].T` — raw_evals are from the cleaned estimator's eigenvalue spectrum, not the sample cov. This means the "sample" side of the blend is actually the estimator's full-rank spectrum, not the raw sample covariance.

**Score**: 6/10 — core RMT math is correct, but outlier preprocessing is limited to one method, the blend slider has a subtle bug, and audit trail output is incomplete.

---

### F02 — PCA Factor Extraction and Loading Matrix

**Spec targets**: Loading matrix heatmap, factor return time series with stats (Sharpe/vol/maxDD/skew/kurtosis/AR(1)), explained variance bar chart, top-N loading table per component, rotated vs unrotated side-by-side with Hoyer sparsity, hierarchical PCA cluster map, PC interpretation panel, full loading CSV + eigenvector JSON, per-asset R², factor correlation matrix for Promax.

**Implemented**: Loadings returned (lines 301-310), factor returns with full stats (lines 26-36, 73), explained variance (lines 313-321), top-N table (lines 65-71), varimax (lines 324-336) and promax (lines 339-350) rotation, hoyer sparsity (lines 393-404), asset R² (lines 407-422), hierarchical PCA (lines 425-476). PC interpretation labels (lines 74-79). 11 outputs claimed in meta.

**Gaps**:
- `_cluster_map()` (line 122-126 in feature_02.py) is NOT hierarchical PCA output — it's sector-level average of absolute PC1 loadings. It's labeled `hierarchical_pca_cluster_map` but is just a sector aggregation proxy. The real HPCA output (`hpca_cross_factor_returns`) is in a separate chart.
- Promax factor correlation matrix Φ = (AᵀA)⁻¹ is not returned. The spec explicitly requires it (spec line 350: "should be reported alongside the rotated loadings"). Missing from feature_02 output.
- Side-by-side rotated vs unrotated heatmap comparison is not structured for the frontend — both are flat lists of dicts. The frontend would need to reconstruct heatmaps.
- Hoyer sparsity is computed (line 85) and returned in both charts and tables, but the spec describes it as "displayed below each heatmap" in the rotated vs unrotated comparison — weak structure for frontend rendering.
- Factor return AR(1) t-statistic is computed in `_stats()` (line 35: `series.autocorr(1)`) but the t-stat is not computed. The spec explicitly says "AR(1) coefficient and its t-statistic" (spec line 52).

**Bugs/Issues**: None algorithmic. Output structure gap for Promax correlation matrix.

**Score**: 7/10 — all major math present. Three spec outputs missing (factor correlation matrix, AR(1) t-stat, proper HPCA cluster map labeling).

---

### F03 — PCA Portfolio Risk Decomposition and Attribution

**Spec targets**: Risk attribution stacked bar (PC contributions + idiosyncratic), marginal risk contribution table, factor VaR waterfall, CVaR decomposition, systematic vs idiosyncratic pie, rolling risk decomposition chart, active risk attribution with tracking error, benchmark correlation by PC.

**Implemented**: `risk_decomposition()` (lines 1062-1107) returns all factor/position risk breakdowns with VaR/CVaR. `active_risk_attribution()` (lines 479-531) returns tracking error decomposition. `rolling_risk_decomposition()` (lines 534-557) returns per-PC attribution over rolling windows. Feature 03 wires all of these (lines 20-71).

**Gaps**:
- VaR waterfall uses proportional approximation (line 53: `total * pct_total_variance / 100`). The spec requires exact factor contribution to VaR, not proportionally allocated variance share. For non-Gaussian portfolios (especially with the Cornish-Fisher correction already computed at line 1098), the proportional approximation is mathematically wrong — the individual factor VaR contributions should be derived from the portfolio's factor-level return distribution, not from variance shares. This means the waterfall bars won't correctly decompose the Cornish-Fisher VaR.
- CVaR decomposition (line 54) has the same proportional approximation issue.
- Rolling risk decomposition in feature_03 (line 57) uses `rolling_risk_decomposition()` which refits PCA on each rolling window — correct approach. But the fallback (line 33-37) falls back to simple rolling vol, which is not the spec output.
- Benchmark correlation by PC (line 57) uses `pct_total_variance / 100` as a proxy for correlation contribution — this is not the correct formula. The spec (F03 output 8) requires per-PC contribution to portfolio-benchmark correlation, not variance share.
- Active risk attribution table (line 64) uses `risk["factor_rows"]` instead of `active["attribution_rows"]`. This duplicates the total-risk decomposition under the label `active_risk_attribution_table` — these are total-risk rows, not active-risk rows. The `active["attribution_rows"]` from `active_risk_attribution()` is never included in the response.

**Bugs/Issues**:
- Line 64 in feature_03.py: `"active_risk_attribution": risk["factor_rows"]` — BUG. Should be `active["attribution_rows"]`. This returns the wrong data.
- The `_waterfall()` helper (line 75) allocates VaR proportionally, not by factor-level quantiles.

**Score**: 5/10 — the math infrastructure is solid but the output wiring has a critical bug (wrong table data), VaR waterfall is a proportional approximation not the spec's exact decomposition, and CVaR decomposition is duplicate logic.

---

### F04 — PCA Residual OU Statistical Arbitrage Signal Engine

**Spec targets**: Ranked signal table with Z-score, half-life, κ, μ, σ_eq, direction, breakeven Z, OU SE; Z-score time series per stock; OU parameter dashboard with confidence intervals; OU parameter distribution histograms (half-life, κ, σ_eq); residual correlation heatmap; backtest P&L engine full stats (gross/net Sharpe, max DD, hit rate, avg holding period, turnover); signal decay analysis; volume-time vs calendar-time comparison.

**Implemented**: `ou_signal_table()` (lines 1121-1166) with OU parameters, SE via delta method (lines 1155-1160), breakeven Z (line 1162), volume-time (lines 1124-1131). `signal_decay_analysis()` (lines 1625-1679) with forward Z horizons. `residual_ou_backtest()` (lines 1682-1745) with full stats. MLE OU via `ou_mle()` (lines 2052-2109). Feature 04 wires all of these.

**Gaps**:
- Residual correlation heatmap (spec F04 output 5) — NOT in feature_04 outputs. This is only in feature_08. The spec requires it in F04 as a diagnostic: "In a well-specified K-PC model, all off-diagonal entries should be near zero."
- OU parameter distribution charts (histograms of half-lives, κ values, σ_eq values across universe) — NOT implemented. Feature_04 has half-life vs zscore scatter plot (line 74) but not full distribution histograms.
- Volume-time vs calendar-time comparison (spec F04 output 9) — NOT implemented. The volume_time flag exists (line 38) but there's no side-by-side comparison of signals under both regimes.
- Backtest P&L engine: the "average holding period in days" stat is in the spec's output list but not in `residual_ou_backtest()` stats (lines 1732-1744).
- The spec describes "days since the current signal triggered" and "estimated time to mean reversion at current κ" — neither is computed in `ou_signal_table()`.
- `ou_signal_table()` uses cumulative residuals (line 1138: `.cumsum()`) instead of raw residuals as the OU input. The spec says Xᵢₜ = Σₛ₌₁ᵗ εᵢₛ which is the cumulative sum — this is correct. But the Z-score formula (line 1152) uses `(x[-1] - mu) / sigma_eq` where `x` is the cumulative residual. The spec defines sᵢₜ = (Xᵢₜ − μ̂ᵢ) / σ̂ᵢ_eq where Xᵢₜ is cumulative — correct.

**Bugs/Issues**:
- Line 1138: `.cumsum()` on the residual *before* fitting the OU. The spec fits OU to the cumulative residual process. This is correct per Avellaneda-Lee (2010).
- The MLE path (lines 45-55) only runs on the top 20 most active tickers — reasonable performance choice but not documented in the feature's docstring.
- Signal decay analysis (line 58) is gated behind `payload["signal_decay"]` but not listed as a required input in the docstring.

**Score**: 7/10 — core OU engine is strong with both OLS and MLE, delta-method SE, volume-time adjustment, backtest engine. Missing: residual correlation heatmap, parameter distribution histograms, volume-time comparison, signal aging columns.

---

### F05 — Rolling Eigenvalue Stability and Regime Transition Monitor

**Spec targets**: PC1 explained variance time series (10-year daily rolling), cosine similarity drift chart (up to 5 PCs), multi-eigenvalue time series (top K eigenvalues over time), PC1 loading evolution heatmap, CUSUM structural break probability chart, regime summary table, live status alert panel.

**Implemented**: `rolling_pca_metrics()` (lines 1169-1207) computes rolling PC1 share, cosine stability, principal angles, effective dimensions, eigen ratio. `pc1_percentile_rank()` (lines 2160-2192) for alert panel. `rolling_loading_evolution()` (lines 2116-2153) for loading evolution heatmap. `cusum_table()` (lines 1210-1217) for structural breaks. `bai_perron_breakpoints()` (lines 1748-1810) for multiple breaks. `tensor_hosvd_proxy()` (lines 1813-1862). Feature 05 wires 14 outputs.

**Gaps**:
- Multi-eigenvalue time series (top K eigenvalues simultaneously over time) — NOT returned as a dedicated chart. The `rolling_pca_metrics()` output only has `pc1_share`, not λ₁(t), λ₂(t), …, λₖ(t) separately. The spec requires separate colored lines for each eigenvalue. The `eigen_ratio_k` is the only multi-eigenvalue metric.
- Regime summary table (spec F05 output 6): "For each detected structural break: start date, end date, duration in days, dominant asset in PC1 before/after, PC1 variance explained before/after, average cross-sectional equity volatility in the regime before/after." — NOT implemented. CUSUM and Bai-Perron tables exist but lack asset-level breakdowns.
- The spec requires crisis annotation bands (GFC, Flash Crash, COVID, etc.) on the PC1 chart. Feature 05 does not return `CRISIS_DATES` — those are in feature_08 only.
- Cosine similarity drift chart in the spec tracks up to 5 PCs. `rolling_pca_metrics()` only tracks PC1 cosine stability. The multi-PC version is available through `subspace_principal_angles()` (line 851) but only the max principal angle is stored, not per-PC cosine similarity for PCs 2-5.
- The spec describes PC1 z-score percentile rank watch (252-day historical percentile). `pc1_percentile_rank()` computes this ✓ but the spec also wants the CUSUM statistic vs critical value and traffic-light status — all three are partially returned.

**Bugs/Issues**:
- Line 1201: `arr.std(ddof=1) or 1.0` — if std is zero, this defaults to 1.0, which will suppress the z-score signal entirely (no alert ever fires). Minor edge case.
- The alert logic (line 63-69) uses `latest["pc1_zscore"].abs() > 2` as the instability threshold — this detects when PC1 share is extreme in z-score terms but NOT when cosine similarity drops below threshold. Line 64: `latest["pc1_cosine_stability"] < 0.85` — this IS correct but the threshold 0.85 is hardcoded, not from payload.

**Score**: 6/10 — solid rolling PCA mechanics, but multi-eigenvalue tracking, regime summary table, crisis annotations, and multi-PC cosine drift are missing.

---

### F06 — Constrained PCA Portfolio Optimization with RMT Covariance

**Spec targets**: Efficient frontier with GMVP/MSP/ERC markers, K sensitivity chart (OOS Sharpe vs K), optimal weight table, risk budget decomposition, constraint binding diagnostic with shadow prices, transaction cost impact panel, RMT vs sample allocation comparison, rolling backtest of optimal portfolio.

**Implemented**: `optimize_portfolio()` (lines 1220-1298) with mean-variance/ERC/max-sharpe objectives, CVXPY with constraints. `optimize_portfolio_with_duals()` (lines 1555-1618) for shadow prices. `k_sensitivity_sweep()` (lines 669-712) for OOS Sharpe vs K. `erc_portfolio()` (lines 571-591). `max_sharpe_portfolio()` (lines 594-620). `pc_factor_risk_parity_portfolio()` (lines 623-666). `robust_frontier_ellipsoidal()` (lines 1938-1991). `black_litterman_posterior()` (lines 715-759). Feature 06 wires 12 outputs.

**Gaps**:
- Transaction cost impact panel (spec F06 output 6) — NOT implemented. The turnover constraint exists (line 1270-1275) but the side-by-side comparison of portfolio with and without the constraint (showing which positions were trimmed and the Sharpe cost) is not output.
- RMT vs sample allocation comparison (spec F06 output 7) — NOT implemented. `optimize_portfolio()` always uses `cleaned_cov`. There's no dual optimization using raw sample cov for comparison.
- Rolling backtest of optimal portfolio (spec F06 output 8) — NOT implemented. The `k_sensitivity_sweep()` does a single IS/OOS split but not rolling rebalances with point-in-time information. No cumulative return, rolling Sharpe, drawdown, or turnover charted over time.
- The efficient frontier in the spec has 100 equally-spaced portfolios. The implementation uses 35 (line 1292: `np.linspace(0, 1, 35)`) — fewer than spec.
- Sector concentration constraints and factor exposure constraints (spec F06 input 5) — NOT wired. Line 1264-1268 only has sum-to-one, long-only, and max-weight constraints. No sector-level or PC-factor-level constraints.
- Target tracking error vs benchmark constraint — NOT wired.
- Maximum number of assets (cardinality cap with integer programming) — NOT wired.
- The Black-Litterman integration only supports views on assets (via `payload["bl_views"]`), not on K PC factors directly as the spec describes (spec F06 input 7: "User enters views on any subset of the K PC factors").

**Bugs/Issues**:
- The frontier computation (lines 1292-1296) blends between equal-weight and optimal — this is NOT a proper efficient frontier sweep over λ. It's a linear interpolation between two points. The spec says "λ from 0 to ∞ to produce the full efficient frontier at 100 equally-spaced Pareto-optimal portfolios." The implementation computes 35 points that are convex combinations of the GMVP and the optimal portfolio — this does not sweep the full frontier and will miss intermediate Pareto-optimal portfolios.
- Line 1292: `np.linspace(0, 1, 35)` — the blend parameter t goes from 0 (equal weight) to 1 (optimal). This is a straight line in weight space, not λ-parameterized efficient frontier.
- This "frontier" is misleading because there's no guarantee these intermediate blends are Pareto-optimal.

**Score**: 4/10 — the most gaps of any feature. Frontier is a pseudo-frontier (linear blend, not λ-sweep), no transaction cost comparison panel, no RMT vs sample comparison, no rolling backtest, no sector/factor constraints, no cardinality constraints, only 35 frontier points vs spec's 100.

---

### F07 — Out-of-Sample Bootstrap Validation and Factor Genuineness Scorecard

**Spec targets**: Bootstrap scree plot with 90%/95% confidence bands, eigenvector cosine similarity distribution, subsampling stability heatmap (K×K with diagonal/off-diagonal), Bai-Ng IC1/IC2/IC3 criteria sweep, factor genuineness scorecard with composite verdict, principal angle analysis.

**Implemented**: `bootstrap_validation()` (lines 1301-1354) with case/block bootstrap, eigenvalue confidence bands, cosine stability scorecard, subsampling stability, principal angles. `bai_ng_criteria()` (lines 762-797) with proper SSR-based IC1/IC2/IC3. `block_bootstrap_sample()` (lines 800-814). `subsampling_stability()` (lines 817-848). Feature 07 wires 10 outputs.

**Gaps**:
- Bootstrap replication count is capped very low. Line 1304: default B=30 (realtime) / 80 (research), max 60/250. Spec says 200/500/1000. At 30 replications, eigenvalue confidence bands will be unreliable — 30 samples are insufficient for 5th/95th percentile estimation. This is a performance trade-off but should be documented.
- Residual bootstrap (preserves factor structure by resampling residuals) — NOT implemented. Only case bootstrap (full row resampling) and block bootstrap are implemented.
- The subsampling stability heatmap (spec wants K×K matrix with diagonal = stability, off-diagonal = interchangeability) is partially implemented. `subsampling_stability()` returns per-PC mean/min/std cosine, not the full K×K cross-matrix. The `_stability_heatmap()` (feature_07.py line 66) converts this to a diagonal-only heatmap. Off-diagonal substitution-swap detection is not computed.
- The composite verdict logic (line 1339): "Statistically Robust" if mean > 0.9 AND p05 > 0.8, "Marginal" if mean > 0.7, else "Potentially Spurious". This is simpler than the spec which also requires eigenvalue 5th percentile crossing the MP threshold and subsampling stability scores.
- Eigenvalue confidence bands in `bootstrap_validation()` are at 5th/95th percentile (90% CI). The spec requires user-selectable 90%/95%/99% bands — only hardcoded 90% is implemented.
- The spec describes Bai-Ng as being computed in F01 as well (spec line 306: "Bai-Ng criteria computed here, displayed here: See Feature 7"). The implementation computes Bai-Ng only in F07, not in F01.

**Bugs/Issues**:
- Line 1325: `evals_list.append(vals[: min(25, len(vals))])` — truncates eigenvalues at 25 even if the asset count is larger. This means only the top 25 eigenvalues get confidence bands.
- Line 1346: `principal_angles` returns angles named "Angle1", "Angle2" etc. — the spec would benefit from PC-component labeling.
- Line 1329: `subspace_principal_angles(full_subspace, vecs[:, :k])` — correct SVD computation ✓

**Score**: 7/10 — all major math correct (Bai-Ng, bootstrap, principal angles). Low replication count hurts reliability. Subsampling heatmap missing off-diagonal. Residual bootstrap absent.

---

### F08 — PCA Residual Cross-Correlation and Contagion Monitor

**Spec targets**: Residual correlation time series by group (primary), residual correlation matrix heatmap, λ₁ of residual correlation matrix over time, contagion spike detector table, under-specification diagnostic (scatter plot of residual correlation vs K), residual correlation regime alert.

**Implemented**: `residual_contagion()` (lines 1357-1385) with group rows, pair table, under-specification diagnostic by K. `rolling_group_residual_corr()` (lines 862-891) for rolling time series. `residual_tensor_hosvd()` (lines 1865-1935) for tensor decomposition. Feature 08 wires 13 outputs.

**Gaps**:
- λ₁ of residual correlation matrix over time (spec F08 output 3) — only the CURRENT λ₁ is returned (line 34: `cont["lambda1_residual"]`). The rolling history of λ₁(t) over time is not saved and charted. The current value alone doesn't serve as a "daily rolling chart."
- The under-specification diagnostic scatter plots (spec shows two panels: average intra-sector residual correlation vs K, AND λ₁ of residual matrix vs K) — only one version is returned (line 57: `cont["under_specification"]` has both `avg_abs_residual_corr` and `lambda1_residual` per K). Both metrics are in the same data structure.
- Group-level correlation time series IS returned (line 54: `rolling_group_ts`) — this addresses the original audit gap ✓.
- The spec requires a "252-day historical percentile of both metrics" in the regime alert. Feature 08 line 33-34 only checks λ₁ against a threshold, not historical percentile.

**Bugs/Issues**:
- The `residual_contagion()` function uses the full residual history (line 1360: `r.tail(window)`). The window is user-set but the PCA refit for the factor model is NOT re-done at each window — it uses the fixed model from `rmt_model()`. This means the residuals are based on a fixed-lookback PCA, not rolling.
- Crisis overlay dates are hardcoded (feature_08.py lines 20-25) and include only 4 events. The spec has 10: GFC, Flash Crash, European Debt Crisis, Taper Tantrum, China Devaluation, Vol Shock, COVID, Rate Shock, Quant Unwind Liberation Day, custom.

**Score**: 7/10 — correct mechanics for residual correlation. Missing λ₁ time series chart, limited crisis dates, no historical percentile in alert.

---

### F09 — PCA Stress Scenario Generator and PC-Shock P&L Attribution

**Spec targets**: PC scenario P&L heatmap (2K × M), position-level P&L waterfall per scenario, scenario sensitivity table (worst-case/best-case/Z-score/percentile/label), maximum loss scenario identifier, Mahalanobis historical analog finder, joint multi-PC shock P&L, stress VaR and stress CVaR (10K MC+2K parametric), scenario report PDF export.

**Implemented**: `stress_scenarios()` (lines 1388-1431) with 2K parametric scenarios, 10K MC augmentation (lines 1418-1426), Mahalanobis analog finder using Euclidean distance (lines 1408-1416), historical worst-day scenarios (line 1428), joint multi-PC shock (line 1430). `stress_pdf_report_base64()` (lines 1994-2045) for PDF export. `historical_worst_day_scenarios()` (lines 894-918). `joint_scenario_pnl()` (lines 921-953). Feature 09 wires 12 outputs.

**Gaps**:
- Mahalanobis analog finder uses Euclidean distance (line 1414: `(q_hist - target) ** 2).sum(axis=1)`). The spec requires proper Mahalanobis distance using the factor correlation matrix C_F^{-1} (spec line 702: "d²_Mahal(t) = (q_scenario − q_historical(t))ᵀ C_F⁻¹ (q_scenario − q_historical(t))"). The implementation notes this is valid for orthogonal PCA factors but incorrect for shrinkage-estimator PCA where factors have off-diagonal correlation.
- The scenario sensitivity table (spec F09 output 3) requires "current Z-score of that PC (where is the factor in its historical distribution)" and "historical percentile of the shock magnitude." Only the shock magnitude is in the output. The current Z-score of each PC (a measure of whether the factor is stressed in the current regime) is not in the response.
- The spec requires a 60-day return chart centered on each analog date (spec line 222). The analog finder only returns date and realized P&L, not a 60-day window of returns.
- Multiple portfolio comparison (up to 4 portfolios compared in the heatmap) — NOT implemented. Only a single portfolio is supported.
- PDF export is conditional on reportlab being installed (line 1997-2001). Without it, returns `None`.

**Bugs/Issues**:
- The Mahalanobis distance Euclidean fallback is undocumented in the response. The metadata should indicate whether Euclidean or true Mahalanobis was used.
- The stress VaR combines 2K param + 10K MC (line 1424). At 95% VaR with 10,020 total losses, this is reasonable but the comment is misleading (line 714 of spec: "fitted distribution" approach vs the implementation's empirical percentile).

**Score**: 7/10 — all core scenario math present. Mahalanobis is Euclidean (documented trade-off), sensitivity table missing PC Z-scores and percentiles, no multi-portfolio comparison, no 60-day analog window.

---

### F10 — Cross-Asset RMT Covariance Engine with Hedged Block Decomposition

**Spec targets**: Block-specific covariance estimators (LW for equities, EWMA for FX, OAS for commodities, MCD+Student-t EM for crypto), DCC conditional correlation, calendar alignment (equity-day vs 7-day), block-aware shrinkage (cross-block shrunk more aggressively), Cornish-Fisher adjusted MP for crypto, FX hedge ratio matrix, rolling block correlation monitor with CASCI, stress-date overlays, unified cross-asset PCA factors, asset-class-specific MP bounds.

**Implemented**: `cross_asset.py` (424 lines) with `cross_asset_feature_outputs()` (lines 313-424). Block covariance dispatch (lines 89-100): EWMA for FX, OAS for commodities/rates, MCD/OAS for crypto, fast_cov for equity. DCC via `dcc_correlation()` (lines 195-239). Calendar alignment (lines 164-192). Crypto volume filter (lines 103-118). CF-adjusted MP for crypto (lines 121-136). FX hedge ratios (lines 242-255). Block correlation monitor with CASCI (lines 258-280). Stress overlays (lines 283-310). PCA on unified matrix (lines 332-335). Hourly inventory (lines 366). 10 outputs claimed.

**Gaps**:
- Student-t EM for crypto block — NOT implemented. The best available is MCD robust (which standardizes but doesn't fit the multivariate t). The spec requires full EM estimation (spec lines 753-757) with weight wₜ = (ν+N) / (ν + (Rₜ−μ)ᵀ Σ⁻¹ (Rₜ−μ)) and reported ν per asset.
- Block-aware shrinkage (cross-block entries shrunk more aggressively than within-block) — NOT implemented. The unified covariance is computed via simple `aligned.cov()` (line 330), not through block-aware assembly. The DCC correlation feeds into the DCC chart but not into the covariance matrix used for PCA.
- Asset-class-specific MP bounds (spec F10 output 1: "four asset-class-specific MP upper bounds computed at the block-level q ratios") — NOT computed. Only the unified MP threshold is applied (indirectly via not being applied — `cross_asset.py` doesn't actually RMT-clean the unified matrix). The eigenvalues are returned (line 401-404) but no MP filtering is applied.
- Cross-asset PCA factor loading matrix by asset class (spec F10 output 3) — partially implemented via `asset_class_pc_loading_share` (line 361) which gives per-asset-class loading squared share. But the spec wants a full loading heatmap (N_total × K) with asset-level entries.
- The spec requires the unified RMT reconstruction (spec line 789) but `cross_asset_feature_outputs()` does not clean the matrix — it's just empircal cov/corr on aligned returns.
- PCA on the unified matrix uses `aligned.cov()` (line 330) — this is sample covariance, not block-specific estimators assembled into a unified matrix.
- The cross-asset PC factor return time series are NOT returned as an output.
- Futures roll methodology: the implementation uses raw Yahoo continuous proxies. The spec requires Panama backward adjustment or ratio-adjusted rolling with contract-specific roll schedules. The `verify_futures_roll_methodology()` in data_pooling.py (line 399) explicitly documents this is not verified.

**Bugs/Issues**:
- `cross_asset_feature_outputs()` does NOT apply any RMT cleaning to the unified matrix. The eigenvalues are returned raw (line 401-404). The summary cards include "PC1 Share" (line 376) from the raw eigenvalues.
- The "unified cross-asset covariance heatmap" (line 384) is from raw sample covariance, not RMT-cleaned.
- FX volume note (line 93): "FX volume is not meaningful in local Yahoo-style files" — this is documented but means the EWMA covariance for FX uses equal-weighting? No — line 93 only adds a metadata note. The actual EWMA computation (line 61-68) uses standard EWMA, which doesn't need volume. So this is fine, just an honest data note.

**Score**: 5/10 — impressive data assembly and block-awareness, but the unified matrix is not RMT-cleaned, no Student-t EM for crypto, no block-aware shrinkage, no asset-class MP thresholds, no cross-asset factor loading heatmap.

---

### F11 — Latent Liquidity Factor Extraction and Illiquidity-Adjusted Risk

**Spec targets**: Cross-sectional illiquidity heatmap, latent liquidity factor time series (first PC of illiquidity panel), liquidity beta ranking table with Newey-West SE, illiquidity-augmented risk decomposition (PC1+...+PCK+liquidity+idiosyncratic), liquidation cost map, LaVaR, illiquidity-driven correlation heatmap, quant unwind early warning system (3 simultaneous signals).

**Implemented**: `liquidity_outputs()` (lines 1434-1502) with Amihud/PS/Kyle branching, latent liquidity factor via PCA, liquidity beta with Newey-West SE, liquidation cost map, LaVaR, quant_unwind_score. Feature 11 wires 9 outputs.

**Gaps**:
- Illiquidity-augmented risk decomposition (spec F11 output 4) — NOT implemented as a proper decomposition. The `liquidity_variance_contribution` (line 1486) is `port_beta² × liq_var` but this isn't decomposed alongside the PC factors as the spec requires ("PC1 contribution + … + PCK contribution + liquidity factor contribution + idiosyncratic residual").
- Illiquidity-driven correlation detector (spec F11 output 7) — NOT implemented. Spec requires a heatmap of `Corr_Liq(i,j) = β_Liq,i × β_Liq,j × Var(ΔL) / √(σ²ᵢ σ²ⱼ)`. Not in any output.
- Quant unwind early warning system (spec F11 output 8) requires 3 simultaneous signals: (1) Lₜ crossing 90th percentile, (2) liquidity-driven correlation across top 20 positions crossing 0.30, (3) portfolio β_Liq crossing threshold. The implementation only computes (1) partially through `quant_unwind_score` — monitoring (2) and (3) are absent.
- Amihud normalization options (rank normalization, standardization, log transform) — only log1p transform is used (line 1462). Spec requires user-selectable option from payload.
- The spec requires the latent liquidity factor Lₜ to have MP-based K selection on the illiquidity panel eigenvalue spectrum. The implementation always takes PC1 (line 1467: `vecs[:, 0]`), not MP-selected K.
- The spec requires the IML (market-level illiquidity) factor as an alternative to PCA extraction. Not implemented.
- The spec requires the liquidity factor to be ADDED to the K-PC factor set as an explicit (K+1)th factor for the augmented covariance. The implementation keeps it separate as an additive layer (`liquidity_variance_contribution`).

**Bugs/Issues**:
- Line 1501: `quant_unwind_score = (port_beta * port_beta * liq_var) / max(standard["portfolio_vol_daily"] ** 2, 1e-12)` — formula correctly computes fraction of total variance driven by liquidity. ✓
- The liquidation cost map (lines 1491-1498) assumes 15% of ADV per day as the liquidation rate. The spec requires this to be user-configurable.

**Score**: 6/10 — core liquidity infrastructure present (3 illiquidity measures, latent factor via PCA, LaVaR, betas with NW SE). Missing: full augmented risk decomposition, illiquidity correlation heatmap, quant unwind 3-signal system, normalization options.

---

## 3. Shared Infrastructure Audit

### `analytics.py` (2,192 lines)

**Organization**: Monolithic but well-structured. Functions are grouped by feature area, with clear section comments (e.g., line 1525: `# Blend-gamma covariance reconstruction`). Contains all PCA math functions, optimization, bootstrap, stress testing, and liquidity — this is a single-file "everything" module.

**Strengths**:
- All core PCA math is correct: eigendecomposition via eigh, MP threshold calculations, K selection (all 5 criteria), RMT reconstruction, Varimax/Promax rotation.
- Comprehensive optimization machinery: mean-variance, ERC, max-Sharpe, PC risk parity, Black-Litterman, robust ellipsoidal frontier.
- Bootstrap validation with case/block methods, principal angles, subsampling stability.
- OU estimation with both OLS and MLE, volume-time adjustment, signal decay analysis, backtest engine.
- HOSVD/Tucker tensor decomposition for F05 and F08.
- Fallback paths for missing dependencies (cvxpy, reportlab).
- JSON-cleaning layer for safe serialization.

**Weaknesses**:
- No abstract base class or interface. Every function takes `model: dict[str, Any]` — no type safety on the model dictionary keys.
- 2,192 lines in one file is difficult to navigate. Could be split into `pca_math.py`, `optimization.py`, `bootstrap.py`, `ou.py`, `scenarios.py`, `liquidity.py`.
- The `model` dict passed between functions has undocumented key requirements — adding a new feature requires knowing what keys `rmt_model()` returns.
- No logging. Silent failures in many `try/except` blocks (e.g., lines 610-615, 654-660, 710-711).
- `number_like()` function (line 75) catches all exceptions — silent conversion failure on invalid inputs.
- Some duplicated computation: `model_annualization` called twice in `optimize_portfolio()` line 1226.

**Math correctness**: The core PCA math (eigendecomposition, MP threshold, covariance estimation) is correct and well-implemented. Notable correct implementations:
- `eig_sorted()` ensures symmetry and sorts descending (line 202-205).
- `mp_threshold()` correctly computes q and λ bounds (lines 208-219).
- `fit_mp_sigma2()` implements proper iterative moment-matching (lines 353-376).
- `bai_ng_criteria()` uses correct SSR-based IC1/IC2/IC3 formulas (lines 762-797).
- `black_litterman_posterior()` uses correct precision-weighted formula (lines 715-759).
- `subspace_principal_angles()` uses correct SVD of P₁ᵀP₂ (lines 851-859).

**Missing from analytics.py (spec functions not implemented)**:
- None of the "Additional Upgrades" from the spec (lines 907-919 of spec): hierarchical block MP thresholds, Kalman filter loading matrix, regime-conditional OU, robust optimization with bootstrap-based uncertainty sets, tensor residual correlation across regimes/frequencies.
- Residual bootstrap (preserves factor structure by resampling residuals) — not implemented anywhere.
- Full multivariate Student-t EM for crypto (only in cross_asset.py as a comment).

### `cross_asset.py` (424 lines)

Dedicated Feature 10 module, well-organized with block-specific functions. Strengths:
- Block covariance dispatch by asset class (lines 89-100)
- DCC correlation estimation with MLE (lines 195-239)
- FX hedge ratio computation (lines 242-255)
- CASCI cross-asset systemic correlation index (lines 258-280)
- Stress-date correlation overlays (lines 283-310)

Weaknesses:
- No RMT cleaning on the unified matrix (as noted in F10 gaps)
- No Student-t EM for crypto
- No block-aware shrinkage assembly
- `cross_asset_feature_outputs()` is 111 lines (313-424) — compact but mixes computation and output formatting

### `data_loader.py` (342 lines)

Reads from local parquet files. Well-structured with caching, symbol normalization, frequency handling. Strengths:
- `returns_matrix()` handles daily/weekly/monthly/hourly.
- `parse_symbols()` supports multiple universe definitions (all/master/SP500/custom/CSV).
- Cross-asset reading via `load_cross_asset_ohlcv()` and `cross_asset_returns_matrix()`.
- Local price file discovery (`price_file_candidates`, `local_price_file`).
- `dollar_volume_matrix()` for F04 volume-time and F11 Amihud.
- `sector_map()` and `latest_market_caps()` from fundamentals parquet.

Weaknesses:
- All reads are through `market_universe.parquet` — this is fine but creates a single point of data failure.
- FX, commodity, and crypto data are mixed in the same parquet with equities; no dedicated asset-class routing.
- `ohlcv_for_symbols()` has no frequency parameter — always returns daily data.
- Hourly path in `returns_matrix()` (lines 298-306) is clearly a second-class citizen compared to the daily path.

### `data_pooling.py` (434 lines)

Append-only operator tools. Good separation of concerns — runtime code doesn't call these. Strengths:
- `append_ohlcv_to_master()` with deduplication (line 89).
- Local price file discovery and master appending (line 146).
- Cross-asset append workflow with dry-run safety (line 180).
- FRED series fetcher (line 216).
- `missing_data_report()` (line 244) and `cross_asset_missing_report()` (line 259).
- Canonical panel materialization (line 317).
- Portfolio holdings history materialization (line 363).
- Futures roll methodology audit (line 399).

No gaps relative to spec — data_pooling is implementation-specific operator infrastructure, not spec-mandated.

### `performance.py` (80 lines)

Very thin. Contains:
- `timed()` decorator (lines 17-30) — basic perf timing.
- `contiguous_float_frame()` (line 33) — numpy-ascontiguousarray wrapper.
- `fast_cov()` (lines 37-42) — manual demeaning + cross-product.
- `safe_pinv()` (lines 45-49) — ridge-augmented pseudo-inverse.
- `batched_corr()` (lines 52-57) — manual correlation.
- `downsample_records()` (lines 60-64) — even-spacing downsampling.
- `normalized_symbol_tuple()` (line 67) — LRU-cached symbol normalization.
- `frame_fingerprint()` (line 72) — shape/size metadata.

For a "performance" module, 80 lines is minimal. No numba, no joblib parallelization, no memory-mapped I/O, no GPU support. The `fast_cov()` function is only used in `cross_asset.py` — most cov estimation goes through sklearn. No real optimization for the 2,192-line analytics monolith.

### `registry.py` (56 lines)

Standard pattern matching other V2 services:
- `PCAFeature` dataclass with id, title, module, status.
- `PCA_V2_FEATURES` dict mapping "01" through "11" to feature metadata.
- `get_runner()` does `importlib.import_module(f"...{feature.module}")` and returns `module.run`.
- `run_feature()` calls `get_runner(feature_id)(payload)`.

Follows the `run(payload) -> dict` convention from `response()` in analytics.py. ✓

No gaps — the registry is clean and functional.

### `__init__.py` (19 lines)

Sets thread environment variables and exports the registry API. Standard.

---

## 4. API & Wiring Status

**No V2 API exists.** There are zero references to `pca_v2` in `backend/app/main.py` or any API router. The existing files at `backend/app/api/pca_god_mode_api.py` and `backend/app/api/pca_eigenphysics.py` are V1 routes, not V2.

The existing audits both flag this:
- `README.md` line 182: "Wire API routes only when requested. This pass did not touch routing."
- `registry.py` docstring (line 4): "No API routes are wired here."

**Impact**: Features 01-11 are fully functional as Python calls via `registry.run_feature()`, but completely inaccessible through the web API. A user cannot get any PCA V2 output from the running server.

**To wire**: Needs a `backend/app/api/pca_v2.py` or similar with:
- `POST /api/v2/pca/run/<feature_id>` taking a JSON payload, calling `registry.run_feature()`, returning the response dict.
- `GET /api/v2/pca/features` listing all available features from `PCA_V2_FEATURES`.

---

## 5. Comparison with Existing Audits

### `audit code.md` (1,231 lines)

This is the original tech audit. It identifies all the gaps before they were fixed. The analysis is thorough and methodologically sound. Key findings that **this review confirms as resolved**:
- σ² fitting: was median, now iterative moment-matching ✓
- Outlier pre-processing: was absent, now z-score winsorization ✓
- Blend reconstruction: was absent, now `blend_covariance()` ✓
- Promax rotation: was absent, now `promax()` ✓
- Hierarchical PCA: was absent, now `hierarchical_pca()` ✓
- Asset R²: was absent, now `asset_r2()` ✓
- Hoyer sparsity: was absent, now `hoyer_sparsity()` ✓
- Active risk attribution: was absent, now `active_risk_attribution()` ✓
- Rolling per-PC decomposition: was absent, now `rolling_risk_decomposition()` ✓
- Volume-time: was absent, now `volume_time_residuals()` ✓
- Preak-even Z: was absent, now computed inline ✓
- OU SE: was absent, now computed via delta method ✓
- Signal decay: was absent, now `signal_decay_analysis()` ✓
- Bai-Ng IC2/IC3: were wrong (scaled proxies), now proper SSR-based ✓
- Block bootstrap: was absent, now `block_bootstrap_sample()` ✓
- Principal angles: was proxy, now SVD-based ✓
- Rolling group residual corr: was absent, now `rolling_group_residual_corr()` ✓
- Historical worst-day: was absent, now `historical_worst_day_scenarios()` ✓
- Joint multi-PC shock: was absent, now `joint_scenario_pnl()` ✓
- ERC: was absent, now `erc_portfolio()` ✓
- Max Sharpe: was absent, now `max_sharpe_portfolio()` ✓
- K-sensitivity: was absent, now `k_sensitivity_sweep()` ✓
- Black-Litterman: was absent, now `black_litterman_posterior()` ✓
- Turnover constraint: was absent, now wired in optimizer ✓
- Pastor-Stambaugh gamma: was absent, now `pastor_stambaugh_gamma()` ✓
- Kyle's lambda: was absent, now `kyle_lambda_daily()` ✓
- Newey-West SE: was plain OLS, now `newey_west_se()` ✓
- Feature 10 cross-asset: was stub, now `core/cross_asset.py` ✓
- DCC, CASCI, FX hedge, crisis overlays: all implemented ✓

Key findings from audit code.md that this review **disagrees or finds still incomplete**:

1. **Outlier preprocessing**: audit code.md proposed 5 methods (none/winsorize/Huber/trim). Implementation only has z-score winsorization. The audit code.md's proposed code (lines 56-89) was for 5 methods — only 1 was implemented.

2. **Feature 06 frontier**: audit code.md didn't flag the frontier being a linear blend — this review finds it's NOT a proper λ-sweep. New finding.

3. **Feature 03 active risk table BUG**: audit code.md didn't flag that `risk["factor_rows"]` is used instead of `active["attribution_rows"]`. New finding.

4. **Feature 06 sector/factor constraints**: audit code.md didn't note these are unwired. New finding.

5. **Promax factor correlation matrix**: audit code.md's proposed code returns it (line 154: `phi = np.linalg.inv(A.T @ A)`). Implementation doesn't return it. This review finds it still missing.

6. **Mahalanobis distance**: audit code.md didn't flag the Euclidean approximation. New finding (spec requires full Mahalanobis).

7. **Student-t EM for crypto**: audit code.md mentions it (line 1028: "Student-t EM for crypto block") but the implementation uses MCD only. This review confirms it's absent.

### `audit.md` (348 lines)

This is the self-assessment checklist. Dated 2026-06-10. It tracks resolved findings from audit code.md. Key callouts:

- The "Resolved" items in audit.md match what this review finds implemented.
- Audit.md section "Honest Remaining Limitations" (line 52-58) flags the same data constraints this review finds: futures roll methodology not verified, microstrucure data absent.
- Audit.md states Feature 06 had "most gaps of any feature" — this review agrees and still rates it lowest (4/10).
- Audit.md claims Feature 10 now `status="ok"` — this is true for the python execution path (no crashes) but the output doesn't match the spec's full cross-asset requirements (no RMT cleaning, no Student-t EM, no block-aware shrinkage).
- Audit.md does NOT flag the critical bugs this review found: F03 wrong table data, F06 pseudo-frontier.

**Overall**: The existing audits are honest about what was done and what remains. They correctly identified all the original gaps. The codebase addressed 90%+ of the original code audit findings. But this review finds several issues the original audits missed (F03 table bug, F06 frontier bug, F02 factor correlation matrix, F09 Mahalanobis approximation, gap between implementation and spec for F10/F11 complex features).

---

## 6. Overall Assessment

### Total Lines of Code

| Category | Files | Lines |
|---|---|---|
| Core modules (analytics, cross_asset, data_loader, data_pooling, performance) | 5 | 3,472 |
| Feature modules (F01-F11) | 11 | 890 |
| Registry + init files | 3 | 77 |
| **Backend total** | **19** | **4,439** |
| Existing audits (audit.md + audit code.md) | 2 | 1,579 |
| README | 1 | 182 |
| | | |
| **Grand total** | **22** | **6,200** |

### Missing Functions/Models from Spec

| Item | Feature | Status |
|---|---|---|
| Huber M-estimation & trimming outlier methods | F01 | Missing |
| Promax factor correlation matrix | F02 | Missing |
| AR(1) t-statistic on factor returns | F02 | Missing |
| True VaR/CVaR factor decomposition (not proportional) | F03 | Approximate |
| Active risk attribution table (wired wrong) | F03 | Bug: returns wrong data |
| Residual correlation heatmap in F04 | F04 | Missing (only in F08) |
| OU parameter distribution histograms | F04 | Missing |
| Volume-time vs calendar-time comparison | F04 | Missing |
| Multi-eigenvalue time series (top K over time) | F05 | Missing |
| Regime summary table with asset-level breakdown | F05 | Missing |
| Crisis annotation bands | F05 | Missing (only in F08) |
| Proper efficient frontier (λ-sweep, 100 points) | F06 | Bug: linear blend, 35 pts |
| Transaction cost impact panel | F06 | Missing |
| RMT vs sample allocation comparison | F06 | Missing |
| Rolling backtest of optimal portfolio | F06 | Missing |
| Sector/factor concentration constraints | F06 | Missing |
| Cardinality constraints | F06 | Missing |
| PC-factor views in Black-Litterman | F06 | Missing (asset views only) |
| Residual bootstrap | F07 | Missing |
| User-selectable confidence bands (90/95/99%) | F07 | Hardcoded 90% |
| λ₁ of residual matrix over time (rolling chart) | F08 | Missing |
| 10 annotated crisis events | F08 | Only 4 of 10 |
| True Mahalanobis distance | F09 | Euclidean fallback |
| PC Z-score in scenario sensitivity table | F09 | Missing |
| 60-day analog window | F09 | Missing |
| Multi-portfolio comparison | F09 | Missing |
| Student-t EM for crypto block | F10 | Missing |
| Block-aware shrinkage of unified matrix | F10 | Missing |
| RMT cleaning on unified cross-asset matrix | F10 | Missing |
| Asset-class-specific MP thresholds | F10 | Missing |
| Cross-asset factor loading heatmap | F10 | Missing |
| Futures roll adjustment (Panama/ratio) | F10 | Not verified |
| Illiquidity-augmented risk decomposition | F11 | Missing |
| Illiquidity-driven correlation heatmap | F11 | Missing |
| Quant unwind 3-signal system | F11 | Missing |
| Amihud normalization options | F11 | Missing |
| API router | All | Missing entirely |

### Data Dependency Gaps

- **Futures roll methodology**: All 21 target futures symbols use Yahoo continuous/proxy series. No contract IDs, roll dates, or Panama/ratio-adjusted stitching. Documented as "usable return proxy" but not independently verified.
- **Microstructure data**: Order flow, signed volume, bid/ask spread, tick-level trades absent. Kyle's lambda uses daily OHLCV approximation (Hasbrouck 2009).
- **Shares outstanding time series**: Only latest static values from fundamentals parquet. No daily panel for turnover ratio computation.
- **FX hedge exposure matrix**: FX prices exist, but structured hedge ratio mapping from holdings to currency exposures is not complete.
- **2 missing FX pairs**: USDTRY=X, USDCNH=X — not in market_universe.parquet or local files.

### Code Quality Rating

- **Architecture**: 6/10 — analytics.py monolith at 2,192 lines needs splitting. No abstract interfaces. Dict-based API unreliable for large teams.
- **Testing**: Not assessed (no test files visible).
- **Error handling**: 5/10 — heavy use of `try/except` with silent fallback. No logging. `number_like()` silently converts invalid inputs.
- **Performance**: 5/10 — 80-line performance module is inadequate for 4,000-line codebase. No parallelization, no numba, no memory optimization.
- **Documentation**: 7/10 — README.md is thorough. Docstrings are present and descriptive. Spec document is extremely detailed.
- **Correctness**: 7/10 — core math is correct. Issues with wiring (F03 table bug, F06 frontier) and approximations (proportional VaR, Euclidean Mahalanobis).

### Overall Rating: 6.5/10

The codebase represents a very substantial implementation effort (~4,400 lines of backend code) that covers the vast majority of the spec's mathematical requirements. The core RMT-PCA engine, OU stat arb, bootstrap validation, stress testing, and cross-asset modules are all correctly implemented at the math level.

However, the rating is pulled down by:
1. Several output wiring bugs (F03, F06 frontier)
2. Key spec outputs not implemented across all 11 features (~35 items in the missing list)
3. No API router — the code is inaccessible through the web service
4. 2,192-line analytics monolith
5. Most importantly: the gap between the implementation and the spec is widest for the mathematically richest features (F06 optimization, F10 cross-asset, F11 liquidity)

### Top 10 Critical Fixes Needed (Priority Order)

| # | Fix | Location | Impact |
|---|---|---|---|
| 1 | Wire correct active risk attribution table — `active["attribution_rows"]` instead of `risk["factor_rows"]` | `feature_03.py:64` | Bug: currently returns total-risk attribution in the active-risk table |
| 2 | Replace efficient frontier with proper λ-parameterized sweep (100 points) | `analytics.py:1291-1296` | Bug: current frontier is a linear blend of two portfolios, not a proper efficient frontier |
| 3 | Add API router for PCA V2 | New file: `backend/app/api/pca_v2.py` | No web access to any feature |
| 4 | Implement proper VaR/CVaR factor decomposition (not proportional variance share) | `feature_03.py:53-54` | VaR waterfall allocates proportionally by variance share — incorrect for non-Gaussian returns |
| 5 | Implement Student-t EM estimation for crypto block | `cross_asset.py:121-136` | Crypto covariance uses MCD/OAS fallback instead of spec's full t-distribution EM |
| 6 | Add block-aware shrinkage and RMT cleaning to unified cross-asset matrix | `cross_asset.py:330-335` | Unified matrix is raw sample covariance, not RMT-cleaned or block-shrunk |
| 7 | Add transaction cost impact panel + RMT vs sample comparison to F06 | `feature_06.py` | Two missing spec outputs; the second is critical for showing the value of RMT cleaning |
| 8 | Implement multi-eigenvalue time series (λ₁(t), λ₂(t), …, λₖ(t)) in F05 | `analytics.py:1169-1207` | Only PC1 share is tracked, not the full eigenvalue spectrum |
| 9 | Implement full Mahalanobis distance with factor correlation matrix in F09 | `analytics.py:1408-1416` | Currently uses Euclidean distance, incorrect for shrinkage-estimator PCA |
| 10 | Split `analytics.py` into domain-specific modules | `core/` directory | 2,192-line monolith is difficult to maintain, test, and extend |

---

*Review date: 2026-07-13. Based on spec document (919 lines), implementation (4,359 lines of Python), and existing audits (1,579 lines).*
