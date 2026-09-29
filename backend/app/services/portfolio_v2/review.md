# Portfolio V2 — Implementation Checklist and Comprehensive Spec Compliance Audit

## Implementation Checklist, 2026-07-10 Follow-Up

- [x] F01: added growth-optimal weights, an actual hierarchical risk-parity recursion, 100-point frontier, per-asset bounds, sector caps, and turnover constraints. CSV/LaTex exports and rolling rebalancing stability remain outside the feature response contract.
- [x] F02: added Bailey-Lopez de Prado deflated Sharpe, combinatorially symmetric cross-validation with bounded enumeration, historical/parametric/Monte Carlo VaR-CVaR, and configurable walk-forward windows. Point-in-time constituent survivorship remains external data.
- [ ] F03: existing Brinson and risk-attribution outputs run, but full Fama-French attribution, sector-resampled 10,000-draw skill/luck, GIPS composite reporting, and document exports require factor/benchmark and reporting inputs not carried by the local response.
- [x] F04: expanded the scenario book, added stationary block-bootstrap paths, minimum-Mahalanobis reverse stress, user-defined shocks, and explicit stress verdicts. Historical scenario labels remain constrained by available local history.
- [x] F05: portfolio beta outputs now use the OLS/Newey-West regression already implemented in the shared layer, rather than Ridge coefficients. USD conversion, target bands, and alert delivery require FX/portfolio policy inputs.
- [x] F06: uses a temporal Gaussian HMM when installed and sufficient history is available, with an explicit fallback only for short samples; adds expected regime duration. Hamilton switching, VIX classification labels, and alert delivery are not implemented.
- [x] F07: adds 20% ADV days-to-liquidate alongside the backward-compatible 15% measure and applies it to schedules and regulatory buckets. Full UCITS classification and calibrated bid-ask spreads need security-master data.
- [x] F08: adds Mantegna minimum-spanning-tree and agglomerative hierarchy payloads. Equity-bond tracking and DCC top-pair dynamics remain separate time-series extensions.
- [x] F09: adds exponential, hyperbolic, and stretched-exponential decay model selection. Taxonomy is input-driven; publication data and ETF-AUM crowding are unavailable locally.
- [x] F10: added a per-asset Kelly versus Markowitz comparison while retaining Kelly/ruin and drawdown outputs. F09 response handoff and a denser contour renderer remain unimplemented.
- [ ] F11: square-root impact and Almgren-Chriss trajectories run, but empirically calibrated permanent/temporary impact, F09 signal handoff, and coupled cross-asset Riccati control remain unimplemented.
- [x] F12: accepts real `peer_portfolios` and intentionally refuses synthetic shuffled peer books. Monte Carlo cascades, betweenness centrality, rolling DebtRank, and path-level simulation still need historical peer holdings.
- [x] F13: accepts uploaded `strategy_returns` and otherwise labels derived strategy proxies explicitly. Correlation constraint enforcement and a forward kill-switch simulation remain unimplemented.
- [x] Shared: holdings parquet I/O is cached safely, correlation cache keys include method, correlation preserves missing data pairwise, and cache fingerprints sample across the full time axis.

The original audit below is retained as historical context; exact line counts and some gap descriptions predate this follow-up implementation pass.

# Original Audit

**Audit Date**: 2026-07-10
**Spec Source**: `/Users/adityabalaji/Downloads/quant  2/portfolio features.md` (781 lines, ~13 features)
**Implementation**: `backend/app/services/portfolio_v2/` (~3,413 lines across 17 files)

---

## 1. Total Lines of Code

| Component | Lines |
|---|---|
| `core/analytics.py` | 1,563 |
| `core/data_loader.py` | 369 |
| `core/performance.py` | 464 |
| `fetchers/fetch_missing_data.py` | 69 |
| `features/feature_01.py` | 99 |
| `features/feature_02.py` | 121 |
| `features/feature_03.py` | 93 |
| `features/feature_04.py` | 79 |
| `features/feature_05.py` | 101 |
| `features/feature_06.py` | 48 |
| `features/feature_07.py` | 46 |
| `features/feature_08.py` | 98 |
| `features/feature_09.py` | 74 |
| `features/feature_10.py` | 99 |
| `features/feature_11.py` | 40 |
| `features/feature_12.py` | 47 |
| `features/feature_13.py` | 62 |
| **Total (portfolio_v2 only)** | **~3,413** |
| `api/portfolio_v2.py` | 1,243 (separate system — see Section 6) |

---

## 2. Per-Feature Audit (F01–F13)

### F01 — Portfolio Construction Engine — Score: **6/10**

**Spec targets**: 9 optimization objectives (Markowitz, GMV, Max Sharpe, Black-Litterman, Risk Parity, HRP, CVaR, Max Diversification, Growth-Optimal/Kelly), 7 covariance estimators (Sample, Ledoit-Wolf linear, Ledoit-Wolf nonlinear, DCC-GARCH, Constant Correlation, Factor-Structured, Gerber), efficient frontier at 100 λ values, constraint binding report, turnover/cost summary, LaTeX/CSV export, weight stability index.

**Implemented**: 8 objectives (GMV, Max Sharpe, Inverse Vol, Risk Parity, Max Diversification, HRP, Black-Litterman, CVaR-min). 6 covariance estimators (Ledoit-Wolf, OAS, EWMA, Sample, Constant Correlation, Factor-Structured, DCC-GARCH, Gerber). Frontier at only **24 λ values** (line 415: `np.linspace(float(mu.min()), float(mu.max()), 24)` — spec demands 100). Weight stability index computed but simplified (line 856-859: `weight_history.std().mean()` — single number, not rolling 12-rebalance heatmap).

**Gaps**:
- **Growth-Optimal/Kelly missing** from optimization objectives — only available in F10 separately
- **Ledoit-Wolf nonlinear shrinkage maps to sklearn LedoitWolf (linear shrinkage)** — `feature_01.py:11-12` calls `LedoitWolf` even for `nonlinear_shrinkage` method. The spec explicitly requires Stein's loss eigenvalue-specific shrinkage for N > 100
- **No Markowitz trace** — the spec demands: "traced across 100 λ values" and "all 9 objectives plotted simultaneously"
- **No sector constraints** in optimizer — spec requires "Max weight per GICS sector — hard constraint"
- **No turnover constraint** or transaction cost in optimizer (line 451-452: only equality constraints + weight bounds)
- **No weight bound parsing** from payload for per-asset min/max
- **No LaTeX or CSV export** — output is JSON only
- **No covariance diagnostic table** with condition number, Frobenius distance, effective bets, OOS variance (partially — condition numbers reported for 4 estimators)
- **Bugs/Issues**:
  - `_min_var_target` (line 449-453): `float(w @ mu) - target` constraint uses closure over `mu` and `target` — correct for SLSQP but fragile with lambda closure
  - `_hrp_weights` (line 484-493): **Not true HRP** — it's inverse-vol sorted by correlation magnitude. No Ward's linkage, no quasi-diagonalization, no recursive bisection. This is a fast proxy, not the spec's HRP
  - `optimize_portfolios` (line 438): `black_litterman_weights` is called inside a try/except that catches ALL exceptions — hides failures

---

### F02 — Honest Backtesting Engine — Score: **5/10**

**Spec targets**: PSR, DSR (proper Bailey-López de Prado), PBO via full CSCV (all C(T,T/2) combos), Sortino, Calmar, Omega, Max DD table, Ulcer, VaR/CVaR (parametric, historical, Monte Carlo — all 3), Info Ratio, Up/Down capture, Survivorship bias quantification, MinTRL, Harvey-Liu correction, Politis-Romano block bootstrap.

**Implemented**: PSR, DSR (simplified), PBO (simplified CSCV), Sortino, Calmar, Omega, Ulcer, Up/Down capture, MinTRL, Harvey-Liu, Politis-Romano, walk-forward, VaR_95/CVaR_95 (from `performance_metrics`).

**Gaps**:
- **DSR formula is wrong** (feature_02.py:64-65): `max(0.0, psr - 0.05 * math.log(max(rets.shape[1], 2)))` — this is a crude approximation, not the proper DSR. The spec requires DSR = PSR(SR₀) where SR₀ accounts for M trials via the extreme value distribution of Sharpe ratios
- **PBO implementation is not full CSCV** (analytics.py:862-877): Uses `n_splits=8` with chunk-based IS/OOS folds, not all C(T,T/2) combinations. The spec requires "evaluate all C(T,T/2) IS/OOS combinations"
- **VaR/CVaR**: Only in the single `_jit_portfolio_metrics` function (line 345-354) as a single historical estimate. Spec requires "parametric, historical, Monte Carlo — all three compared side by side"
- **Information ratio** (spec line 122): Not computed anywhere
- **No bias audit quantification**: Survivorship bias is flagged as "data_limited" (feature_02.py:115) but no before/after comparison is shown. The spec demands "gap in bps"
- **Walk-forward**: Hardcoded 25% split (line 74: `len(net) // 4`), not configurable
- **Politis-Romano**: Computed but never used for block bootstrap in PBO
- **Equity curve with regime overlay** not present (no NBER shading)

---

### F03 — Performance Attribution — Score: **6/10**

**Spec targets**: Brinson-Hood-Beebower, Brinson-Fachler, Factor-based (FF3/FF5/FF5+Momentum), Risk-based (X-Sigma-Rho), Drawdown attribution, Multi-period linking (Carino, Menchero, GRAP, arithmetic), Skill-vs-luck bootstrap (random stock selection within sectors, 10,000 draws), GIPS-compatible summary, LaTeX/CSV export.

**Implemented**: Brinson (BHB variant), Brinson-Fachler, Carino/Menchero/GRAP linking, Drawdown attribution, X-Sigma-Rho risk attribution, Skill-luck bootstrap (t-stat based, 2,000 draws).

**Gaps**:
- **No factor-based attribution**: The spec requires "Active_return = Σ_k(βk^P−βk^B)×F_k + α_residual" using FF3/FF5. The implementation has no factor return data — waterfall is just asset-level contribution
- **Skill-luck bootstrap doesn't match spec** (analytics.py:972-984): The spec says "random stock selection within each sector, 10,000 draws" — the implementation uses a centered t-statistic bootstrap (randomize sign of active returns). Different methodology
- **Carino linking formula** (analytics.py:929-934): Uses `log(1+rp) / sum(log1p(rp))` — this is correct Carino but only applied at monthly level, missing the full multi-period framework
- **No GIPS-compatible summary**
- **No LaTeX/CSV export**
- **Brinson table uses equal-weight benchmark** (line 499: `bench_w = np.repeat(1 / max(len(cols), 1), len(cols))`) instead of a proper benchmark weight from payload
- **Bugs/Issues**:
  - `brinson_attribution` (line 499): Equal-weight benchmark means allocation effect is always biased — a proper Brinson needs actual benchmark weights
  - `drawdown_attribution` (analytics.py:987-997): Only reports top 5 positions, spec expects waterfall for all

---

### F04 — Stress Testing — Score: **5/10**

**Spec targets**: Historical crisis replay (10 crisis windows), Hypothetical multi-factor shock with DCC-GARCH co-movement, Correlation breakdown stress, Monte Carlo tail simulation (block bootstrap, 3 horizons), Reverse stress test (Mahalanobis distance minimization), Stress verdict card (green/amber/red), Implied probability percentile.

**Implemented**: Historical crisis replay (4 of 10 scenarios), Correlation breakdown (flat correlation), Monte Carlo (i.i.d. normal, not block bootstrap), Reverse stress test (analytical, not proper minimization).

**Gaps**:
- **Only 4 crisis scenarios** (analytics.py:1001): GFC 2008, COVID 2020, Rate shock 2022, SVB 2023. Spec lists 10: dot-com, GFC, Lehman week, EU debt, China devaluation, 2018 Q4, COVID, 2022 rates, 2025 tariffs, 2023 SVB. Missing 6 scenarios
- **No hypothetical multi-factor shock**: The spec requires "simultaneous user-defined shocks with cross-factor correlations from DCC-GARCH." Not implemented
- **Monte Carlo uses i.i.d. normal** (feature_04.py:43): `rng.normal(mu, sigma, size=(paths, horizon))` — spec requires "block bootstrap" with "block length 1-60 months"
- **Reverse stress test is simplified** (analytics.py:1011-1017): The spec requires `min_Δf ‖Σ^{-1/2}Δf‖₂` (Mahalanobis distance minimization subject to portfolio loss constraint). The implementation uses `shock = -loss * (cov @ w) / (w @ cov @ w)` — this is a proportional allocation of the shock, not the minimum-Mahalanobis-distance solution
- **No stress verdict card** (feature_04.py:58 has a simplified version based only on MC 5% quantile, not the full 5-test framework)
- **No implied probability percentile** for reverse stress
- **Correlation breakdown**: Uses flat `crisis_corr = 0.75` (line 47: `crisis_corr_arr = corr_arr[iu].mean()` then feature_04.py line 66: `min(1.0, avg_corr * 1.25 + 0.10)`), not the spec's 2008 GFC peak correlation matrix

---

### F05 — Macro Factor Model — Score: **5/10**

**Spec targets**: Macro factor loadings via OLS with Newey-West (4 lags), Macro R² decomposition into per-factor fractions, Ex-ante tracking error decomposition (X-Sigma-Rho), MCTE, Factor crowding rank, Implied alpha requirements, Macro regime-conditional exposure, Factor drift time series with target bands, Alert system, Tracking error waterfall chart.

**Implemented**: Ridge regression (not OLS), Newey-West standard errors, MCTE, Factor risk budget, Factor crowding rank, Implied alpha required, Rolling exposures, Asset-level factor exposures.

**Gaps**:
- **Uses Ridge regression instead of OLS** (feature_05.py:50): `Ridge(alpha=1.0)`. The spec demands "OLS with Newey-West standard errors (4 lags)." Ridge introduces regularization bias, making betas hard to interpret
- **No proper R² decomposition**: Feature outputs `model.score(X_arr, y_arr)` as a single R², but spec requires "what fraction of portfolio variance is inflation, credit, rates, USD, growth, idiosyncratic"
- **No ex-ante TE decomposition** (X-Sigma-Rho per factor)
- **Missing USD factor**: Feature code (line 42) selects `["vix_close", "vixcls", "yc_slope_10y_2y", "bamlh0a0hym2", "bamlc0a0cm", "dgs10", "dgs2"]`. The spec explicitly lists USD (FRED DTWEXBGS) as a factor. Not loaded
- **Implied alpha**: Based on MCTE (line 89), but not on macro factor MCTE specifically
- **Factor crowding**: Takes absolute value of beta coefficients as loading, not rank comparison within universe of 500 stocks as spec says
- **No target exposure or tolerance band** handling in payload
- **No alert system** for tolerance breaches

---

### F06 — Regime Detection — Score: **4/10**

**Spec targets**: HMM (Gaussian emissions), Hamilton (1989) Markov switching, VIX-based classifier, 2/3/4/up-to-8 regimes, Transition matrix, Regime-conditional covariances, Regime-conditional factor performance, Kaplan-Meier survival curves, Expected regime duration, Regime-aware portfolio weights, Alert system (30%/50% transition probability), Non-homogeneous transitions.

**Implemented**: GMM (fallback to quantile-cut on vol), Transition matrix, Kaplan-Meier survival, Regime-conditional covariances, Regime-conditional factor performance, Non-homogeneous transitions.

**Gaps**:
- **Uses GMM, not HMM**: The spec explicitly requires "Hidden Markov Model (Gaussian emissions)" and "Hamilton (1989) Markov regime-switching." The implementation uses `sklearn.mixture.GaussianMixture` which is a static mixture model with no temporal structure — it doesn't model the Markov transition dynamics
- **No VIX-based classifier**: The spec offers VIX < 15/15-25/25-35/> 35 as an option
- **No expected regime duration**: The spec requires `E[duration in regime k] = 1/(1-A_{kk})`. Not computed (though derivable from transition matrix)
- **No regime-aware portfolio weights** (spec line 359): `w*_regime = Σ_k γₜ(k)×w*(Σ_k, μ_k)`. Not implemented — feature outputs a simple "recommended_weight_scale" based on performance
- **Regime-conditional correlation**: Computed but uses full sample cov, not DCC-GARCH per regime
- **Alert system**: Basic one-line "watch" / "stable" (feature_06.py:46)
- **Bugs/Issues**:
  - `rolling_regimes` (analytics.py:524-546): When GMM is available, it fits on the entire dataset at once — this is look-ahead biased. The spec requires rolling re-estimation
  - `hmm_regime_fit` (analytics.py:1073-1081): Same GMM, same look-ahead issue

---

### F07 — Liquidity Analytics — Score: **6/10**

**Spec targets**: Recency-weighted Amihud ILLIQ (open-to-close only, linearly increasing weights), Days-to-liquidate at 20% ADV, Liquidity-adjusted VaR (with bid-ask + market impact γ), Liquidation cost (normal and crisis 2008-calibrated), Liquidity concentration index, Liquidity frontier via DTL constraints 5/10/20/30 days, Liquidity half-life, SEC Rule 22e-4 / ESMA UCITS classification.

**Implemented**: Recency-weighted Amihud, Days-to-liquidate at 15% ADV, LVaR proxy, Liquidation schedule, Liquidity frontier, Liquidity half-life, Crisis cost, Regulatory classification.

**Gaps**:
- **Uses 15% ADV participation rate** (analytics.py:577): `adv * 0.15`. The spec says "institutional standard: 20%"
- **LVaR is a proxy, not full formula** (analytics.py:584): `10000 * sqrt(amihud * position)`. The spec requires `LVaR = VaR + ½×bid-ask×position + γ×position²`. None of these components are properly estimated
- **No liquidity concentration index**: The spec requires "Fraction of total Amihud-weighted illiquidity in top 10% least liquid positions"
- **Liquidation cost crisis calibration**: Simplified factor of 5× (analytics.py:1159), not the spec's "volume at 30% normal, spread at 5× normal"
- **No ESMA UCITS classification**: Only SEC 22e-4
- **Bugs/Issues**:
  - `recency_weighted_amihud` (analytics.py:1139-1151): Uses open-to-close return absolute value. But `open` may be NaN or zero for some tickers, and `gb` groupby object re-created per ticker — inefficient

---

### F08 — Correlation/Diversification/Contagion Network — Score: **6/10**

**Spec targets**: Full pairwise correlation with hierarchical dendrogram, Leading eigenvalue λ₁, ENB, Diversification ratio, Contagion network via MST (Mantegna 1999), DCC-GARCH per top-10 pairs for regime shift detection, Equity-bond correlation tracker, Sector block analysis, Marchenko-Pastur threshold, Partial correlation network, Pair-level redundancy report.

**Implemented**: Correlation heatmap, Eigenvalues/ENB, Crisis delta matrix, Network edges (correlation threshold-based, not MST), Leading eigenvalue series, Diversification ratio series, Precision matrix network, Sector block analysis, Chow breakpoints, Marchenko-Pastur threshold.

**Gaps**:
- **No Minimum Spanning Tree**: The spec requires "Prim's algorithm for MST" following Mantegna (1999). Implementation uses threshold-based correlation edges instead
- **No hierarchical dendrogram data**: The spec shows dark red/white/dark blue heatmap with dendrogram — implementation returns raw matrix records
- **Regime shift detector**: Uses Chow test on rolling correlation (analytics.py:1214-1228), not the spec's "Rolling DCC-GARCH per top-10 pairs"
- **No equity-bond correlation tracker**: Spec requires "Rolling 252-day correlation of equity portfolio vs AGG"
- **DCC-GARCH average correlation**: Computed in F01 via `dcc_garch_cov` but not reused in F08
- **Bugs/Issues**:
  - `network_edges` (analytics.py:687-689): Uses threshold=0.45 by default but feature_08.py uses 0.0 to get all edges then filters. The MST approach would be more principled
  - `fast_network_edges_from_corr` (performance.py:293-321): Good implementation, but MST edges would be more interpretable

---

### F09 — Alpha Decay / Factor Half-Life — Score: **5/10**

**Spec targets**: IC decay curve at multiple horizons, Hyperbolic/exponential/linear fits with AIC selection, Factor half-life, Optimal rebalancing frequency (IC − cost maximization), Post-publication decay (Chow test), Crowding regime indicator (ETF AUM growth rate percentile removed, replaced by cross-sectional dispersion percentile), Alpha capacity estimation, Factor taxonomy (Mechanical vs Judgment-based with different decay models), Decay-adjusted position sizing.

**Implemented**: IC decay curve (rank IC), Half-life, Hyperbolic fit, Optimal rebalance frequency, Crowding proxy (cross-sectional dispersion of trailing std), Alpha capacity, Decay-adjusted weights.

**Gaps**:
- **No exponential or linear fits**: The spec requires all three (hyperbolic, exponential, linear) with AIC selection. Only hyperbolic is fitted (analytics.py:1253-1264)
- **No factor taxonomy**: The spec differentiates Mechanical factors (hyperbolic decay fitted) from Judgment factors (empirical IC only). No such distinction exists
- **Crowding proxy uses trailing std dispersion** (feature_09.py:42-52): `rolling_std.iloc[-1] / global_std`. The spec says "cross-sectional signal rank dispersion within universe at each period"
- **Optimal rebalancing formula** (analytics.py:1267-1275): `ic/h - 2*tc_bps/10000/h` — this is simplified. The spec requires full holding period return net of cost
- **Alpha capacity**: Uses `ic * sigma / (2 * kyle_lambda)` with kyle_lambda hardcoded as 0.10 (feature_09.py:55), not estimated from data
- **Publication decay**: Marked as "not_available" — acceptable given data limitation

---

### F10 — Growth-Optimal Position Sizing — Score: **6/10**

**Spec targets**: Multi-asset Kelly weights, Drawdown-constrained leverage (max drawdown constraint, not E[MDD]), Long-run geometric growth rate curve, Kelly vs Markowitz comparison, Signal-decay adjusted sizing via IC decay from F09, Effective Kelly fraction under constraints, Ruin probability surface (contour over μ vs σ²), Turnover-adjusted net Kelly, Turnover-optimal Kelly fraction f*.

**Implemented**: Kelly weights (multi-asset), Drawdown-constrained leverage, Growth curve, Ruin probability (discrete points), Signal-decay sizing, Effective Kelly fraction, Turnover-optimal Kelly fraction.

**Gaps**:
- **No Kelly vs Markowitz comparison**: The spec demands "Side-by-side weight vectors at same expected return; difference explained in risk-adjusted terms." Not implemented
- **Drawdown-constrained leverage formula** (analytics.py:1303-1306): Uses E[MDD] ≈ (σ²/2μ)×|log(m)| inverted. The spec says to derive "maximum safe leverage multiplier" from a max drawdown constraint, not E[MDD]
- **Signal decay inputs**: Uses `alpha_decay(ctx["returns"])` on asset returns, not on actual factor signals from F09
- **Ruin probability formula** (analytics.py:1316-1323): `P(ruin) = exp(-2μC / σ²ℒ²)` — this is for continuous-time Brownian motion, which the spec does use, but implementation does not provide the contour plot spec requires
- **Turnover-optimal Kelly** (analytics.py:1334-1337): Wraps `kelly_sizing` with f=1 then finds best from grid — this is correct per spec, but the cost model is simplified
- **Growth rate frontier**: Only 40 discrete points (analytics.py:633) — reasonable but the spec implies a continuous curve

---

### F11 — Optimal Execution & Transaction Cost — Score: **5/10**

**Spec targets (doc Feature 12)**: Almgren-Chriss optimal trajectory with κ² = λσ²/η, IS efficient frontier (E[IS] vs √Var[IS] across full λ), IS decomposition (delay/permanent impact/temporary impact/timing risk/opportunity cost), Signal decay-adjusted urgency from F09 half-life, Market impact calibration (γ and η from ADV/spread), Volume profile-adjusted trajectory, Correlated multi-asset liquidation via coupled Riccati equations.

**Implemented**: Almgren-Chriss trajectory, IS frontier, IS decomposition (simplified), Market impact calibration, Volume profile adjustment, Correlated multi-asset IS (simplified).

**Gaps**:
- **Almgren-Chriss trajectory uses daily time steps** (analytics.py:1341-1352): The spec requires continuous-time formulation with sinh/coth — the math is correct but uses a simplified implementation
- **IS decomposition hardcodes ratios** (analytics.py:1364-1365): `permanent_impact_bps = impact * 0.35`, `temporary = impact * 0.65` — these ratios should be calibrated per ticker, not fixed
- **Signal decay urgency uses defaults** (feature_11.py:38): `signal_decay_urgency(0.05, 63, ...)` — hardcoded alpha0=0.05 and half-life=63. The spec requires connection to F09
- **No actual Riccati solution** for correlated multi-asset: The implementation uses `correlated_multiasset_is` which computes `γ·tᵀ·C·t` — not the coupled Riccati equations from the spec
- **Bugs/Issues**:
  - `impact_calibration` (analytics.py:1383-1386): `gamma = sigma / sqrt(max(adv, 1))`, `eta = sigma / max(adv, 1)` — these are heuristic, not estimated from historical data
  - `almgren_chriss_trajectory` (analytics.py:1349): When risk_aversion <= 0, falls back to VWAP schedule. The VWAP case should still report impact
- **README.md:64**: Acknowledges full Almgren-Chriss cross-impact Riccati is not implemented

---

### F12 — Systemic Risk & Fire-Sale Contagion — Score: **4/10**

**Spec targets (doc Feature 13)**: Portfolio overlap index with peer universe, Fire-sale impact per scenario (10/20/30/50%), DebtRank contagion measure (Battiston et al. 2012), Cascade probability (Gai-Kapadia framework), Systemic risk contribution (delta-CoVaR analog), Overlap network centrality (degree, betweenness, eigenvector), Liquidation spiral probability, Overlap-reducing reallocation, Monte Carlo iterations.

**Implemented**: Overlap index, Fire-sale impact, DebtRank (simplified), Cascade probability (simplified threshold), Systemic risk contribution, Overlap centrality (degree + eigenvector), Liquidation spiral probability, Overlap-reducing reallocation.

**Gaps**:
- **Peers are synthetic** (feature_12.py:21-24): Each peer is a randomly shuffled copy of the user's own portfolio. This means overlap is purely an artifact of the shuffle, not real peer data. The spec requires "S&P 500 index constituents with market-cap-based institutional ownership proxy" or "custom peer portfolio upload"
- **DebtRank is simplified** (analytics.py:1409-1421): Uses `W / max(W.sum(axis=1), 1e-12)` as exposure matrix. The spec requires V_{ij} = exposure of i to j as fraction of equity. Normalized overlap is a weak proxy
- **Cascade probability** (analytics.py:1429-1432): Simplified threshold model with uniform random thresholds. The spec requires "Gai-Kapadia cascade framework" with connectivity, leverage, and initial shock — this matches partly but the implementation is trivial
- **No Monte Carlo iterations**: The spec requires 1,000-10,000 MC iterations for cascade estimation. Not implemented
- **No betweenness centrality**: Only degree and eigenvector computed
- **No rolling DebtRank time series**: Spec expects "Rolling DebtRank of portfolio in peer network over backtest history"
- **No contagion cascade chart**: The spec shows "network diagram with cascade propagation visualized step by step"

---

### F13 — Multi-Strategy Allocation — Score: **4/10**

**Spec targets (doc Feature 15)**: Cross-strategy correlation matrix, Multi-strategy Kelly allocation, Vol-scaled dynamic allocation, Sharpe-momentum reallocation, Regime-conditional strategy weights, Drawdown kill-switch with auto-cut at 50/75/100% of limit, Diversification benefit quantification, Cross-strategy risk attribution (VaR, marginal VaR), Capacity-constrained reallocation, Inter-strategy turnover netting, Strategy dashboard with all key metrics.

**Implemented**: Strategy correlation, Kelly sizing, Inverse-vol/vol-scaled allocation, Sharpe-momentum, Regime-conditional weights, Kill-switch calibration, Diversification benefit, Risk attribution, Netting savings, Capacity-constrained reallocation.

**Gaps**:
- **Strategy returns are entirely synthetic** (analytics.py:1537-1551): `build_strategy_returns` creates momentum_ls, reversal_ls, risk_parity_proxy, and equal_weight from the same asset returns. These are deterministic functions of the same data, not independent strategies. The spec requires "each defined by: return series (CSV upload), or live connection from Features 1–14 as strategy definitions"
- **No user-uploadable strategy returns**: The payload doesn't support strategy return series directly
- **Kill-switch is backward-looking** (analytics.py:1483-1492): `pnl_saved_after_trigger: -saved` — this is historical P&L if the trigger had been applied. The spec requires forward-looking simulation
- **No full strategy dashboard**: The spec requires "current capital weight, risk budget utilization, rolling Sharpe, drawdown status, kill-switch proximity per strategy — every PM's morning screen"
- **Capacity-constrained reallocation**: Uses hardcoded capacity limit from payload, not connected to F09
- **Correlation constraint**: Parsed from payload but not enforced in allocation logic
- **README.md:61**: Acknowledges "inter-strategy netting is marked data-limited until per-strategy asset holdings exist"

---

## 3. Shared Infrastructure Audit

### data_loader.py (369 lines) — Score: 7/10

**Strengths**:
- Good coverage: market_universe, canonical cross-asset panels (equity/fx/crypto/futures), hourly data, holdings history, fundamentals metadata, macro regime data
- Efficient: `lru_cache` decorators, `_MERGED_OHLCV_CACHE` global for deduplication, category dtype for fast dedup
- Proper frequency normalization (daily/weekly/monthly/hourly)
- `parse_symbols` handles multiple input formats (string, list, dict, special values "all"/"sp500")

**Weaknesses**:
- **No point-in-time constituent data** (acknowledged in README, line 55)
- **Returns matrix uses log returns** (line 239-240): `log_ret = log(prices[t] / prices[t-1])`. Not documented. Spec doesn't specify, but arithmetic returns are more common in portfolio optimization
- **Holding history**: `load_holdings_history` (line 322) doesn't cache properly (no `@lru_cache`). Called multiple times per feature run
- **Macro data**: `load_macro` (line 309) only loaded from one parquet source — if CATEGORY7_MACRO missing, returns empty. Missing USD factor (DTWEXBGS) from FRED

### performance.py (464 lines) — Score: 7/10

**Strengths**:
- Excellent caching infrastructure: `BoundedLRU` with `OrderedDict`, cache hit/miss tracking, `PerfRegistry` for instrumenting
- `cached_covariance_frame` / `cached_correlation_frame` prevent redundant matrix computation
- `nearest_psd` (line 224-238) properly handles degenerate matrices
- `safe_eigh`, `safe_inverse`, `fast_matrix_records`, `fast_network_edges_from_corr` all well-optimized with NumPy
- `rank_ic_curve` with JIT-compiled `_jit_rank_ic` — very efficient Spearman IC

**Weaknesses**:
- **`dataframe_fingerprint`** (line 171-194): Uses head(80) + tail(80) sampling — can produce collisions if the middle portion changes significantly
- **Correlation cache key** (line 214): Uses only `dataframe_fingerprint`, no method parameter. This means different method calls share the same cache — currently all methods use Pearson correlation, but this is a potential bug
- **`normalize_numeric_frame`** (line 149-158): Replaces NaN with 0.0 by default — silently hiding missing data
- **No JIT for covariance computation** beyond the DCC loop — `_jit_portfolio_metrics` is excellent (analytics.py:310-366) but lives in analytics.py, not performance.py

### fetchers/fetch_missing_data.py (69 lines) — Score: 7/10

Good documentation of 4 required external datasets with source hints. The `append_parquet` helper is well-designed. This file is intentionally not imported by runtime code — clean design.

---

## 4. API Wiring — Removed

`api/portfolio_v2.py` (1,243 lines) was removed on 2026-07-10. It was a **completely separate system** from the portfolio_v2 feature files — imported from old `portfolio_brain`/`portfolio_risk`/`portfolio_regimes`/etc. modules, used its own numbering (Features 1-29), and returned synthetic/hardcoded data. None of the 13 feature files (F01-F13) were wired to its routes.

**Status**: No API routes exist yet for portfolio_v2. Feature files F01-F13 implement `run(payload)` but have no HTTP entry points. The `backend/main.py` import was also removed.

---

## 5. Overall Assessment

| Category | Score | Notes |
|---|---|---|
| **Spec Coverage** | 5/10 | All 13 features have some implementation, but depth varies wildly |
| **Math Correctness** | 5/10 | Several formulas are simplified approximations (DSR, PBO, HRP, Reverse Stress) |
| **Code Quality** | 7/10 | Well-structured, good NumPy/numba optimization, strong caching |
| **Error Handling** | 5/10 | Overly broad try/except in many places; silent fallbacks |
| **Output Completeness** | 4/10 | Missing ~30-40% of spec-defined outputs per feature |
| **API Wiring** | N/A | Removed — no API routes exist for portfolio_v2 yet |
| **Data Coverage** | 6/10 | Good local parquet coverage but missing PIT, FRED USD, factor returns |

### Overall Rating: **4.5/10**

### What's Done Well
- Consistent `run(payload)` → `response(...)` interface across all 13 features
- Excellent NumPy optimization: `einsum` for covariance, JIT for portfolio metrics, vectorized operations throughout
- Good caching strategy — bounded LRU with instrumentation
- Honest about data limitations (README.md "Honest Gaps" section, `access_issues` in meta)
- `performance_metrics` JIT kernel is a standout (analytics.py:310-366)
- Open-to-close Amihud with recency weighting is correct per spec amendments
- Netting savings and capacity-constrained reallocation in F13 are well-implemented

### Critical Issues That Must Be Fixed
1. **No API routes exist** for portfolio_v2 — feature files F01-F13 implement `run(payload)` but need HTTP entry points
2. **HRP is a proxy** — not true hierarchical risk parity (analytics.py:484-493)
3. **DSR is wrong** — simplified approximation (feature_02.py:64-65)
4. **PBO is not full CSCV** — uses 8 folds, not combinatorial (analytics.py:862-877)
5. **Reverse stress test is not minimizing Mahalanobis distance** (analytics.py:1011-1017)
6. **Peers in F12 are random shuffles** — not real peer funds (feature_12.py:21-24)
7. **Strategies in F13 are deterministic functions of the same returns** — not independent (analytics.py:1537-1551)
8. **Regime detection uses GMM, not HMM** — no temporal structure (analytics.py:1073-1081)
9. **Growth-optimal/Kelly missing from F01 objectives**
10. **Frontier only at 24 λ values, spec demands 100**

### Data Dependency Gaps
- Point-in-time constituents (F02 survivorship bias)
- Factor ETF AUM history (F09 crowding)
- Peer fund holdings (F12 overlap/DebtRank)
- Per-strategy asset holdings (F13 inter-strategy netting)
- FRED USD index (DTWEXBGS) for F05
- FF5 factor return series for F03 factor attribution

### Speed Issues
- `rolling_regimes` refits GMM on every call — no caching of regime assignments
- `ohlcv_for_symbols` in `liquidity_table` reloads OHLCV per ticker (unnecessary — groupby already available)
- `recency_weighted_amihud` loops over groupby `gb` which is already computed — creates separate Series per ticker
- `brinson_fachler` and `brinson_attribution` both compute identical mean returns independently (same call, different functions called from feature_03.py)
- `feature_03.py`: `brinson_attribution` and `brinson_fachler` are called separately, both computing `returns.mean()`
