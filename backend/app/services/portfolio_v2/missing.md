## Performance Pass Checklist — 2026-06-17

[x] Added `core/performance.py` with bounded in-process LRU caches, timing counters, stable dataframe fingerprints, vectorized matrix serialization, vectorized graph edge extraction, PSD stabilization, safe inverse helpers, rolling scan helpers, and vectorized rank-IC computation.

[x] `compact_records()` now uses bounded deterministic row sampling through `compact_table()`.

[x] `matrix_records()` now uses `fast_matrix_records()` to cap large matrix payloads and reduce Python loop overhead.

[x] `covariance_matrix()` now uses bounded covariance caching keyed by estimator and returns fingerprint.

[x] `covariance_matrix()` now applies PSD stabilization to reduce optimizer failures and repeated numerical repair work downstream.

[x] `correlation_diagnostics()` and `network_edges()` now reuse cached correlation matrices.

[x] `network_edges()` now uses vectorized upper-triangle extraction rather than nested Python pair loops.

[x] `precision_matrix_network()` now uses Ledoit-Wolf covariance plus `safe_inverse()` and vectorized edge extraction.

[x] `leading_eigenvalue_series()` now uses the shared stepwise rolling eigenvalue helper.

[x] `diversification_ratio_series()` now uses the shared stepwise rolling diversification helper.

[x] `alpha_decay()` now uses cached vectorized cross-sectional rank-IC curves instead of nested horizon/date loops.

[x] `cvar_minimize()` now uses a cached result path and vectorized LP constraint matrix construction.

[x] F01 no longer eagerly evaluates Black-Litterman/CVaR fallback calls when optimized weights already exist.

[x] `kelly_sizing()` no longer performs an O(n²) `cols.index()` lookup inside the row loop.

[x] Feature response metadata now includes `meta.performance` with timing/cache snapshots for profiling live runs.

[x] Compile validation passed after the performance pass.

[x] Smoke validation passed after the performance pass. Same F01-F13 payload improved from about `62.3s` to `42.7s` in-process, with F09 and F10 dropping from about `10s` each to about `2.1-2.5s`.

[ ] F01 remains the slowest feature because it still solves multiple constrained optimizers and the Rockafellar-Uryasev CVaR LP. Further speed would require research-mode gating, fewer frontier points, or approximate CVaR, which I did not do because it would change output completeness/methodology.

## Attachment Fix Pass Checklist — 2026-06-17

[x] Routed `covariance_matrix()` to the advanced covariance estimators already present in analytics: `dcc_garch`, `factor_structured`, and `gerber`.

[x] Routed `optimize_portfolios()` to advanced objective weights for `black_litterman` and `cvar_min`, with safe fallback metadata if an objective cannot solve.

[x] F01 now computes DCC covariance once per run and reuses it for covariance condition numbers and DCC average correlation output.

[x] F01 now labels the cross-objective dispersion output honestly instead of presenting it as rolling rebalance stability.

[x] F02 PBO now compares strategy variants from the same run rather than passing unrelated gross/net series into CSCV.

[x] F02 equity curve output now contains separate gross and net equity curves, not duplicated net values.

[x] F03 now links attribution effects against portfolio monthly returns, separates the skill/luck summary from the bootstrap null distribution, and keeps deterministic drawdown fallback behavior.

[x] F04 historical crisis replay rows now normalize into a consistent scenario schema before being combined with stress scenarios.

[x] F05 factor risk budget now uses an asset-by-factor exposure matrix estimated from macro regressions instead of a single-row loading vector.

[x] F06 regime driver alignment now uses datetime-indexed regime probabilities and reindexed driver data.

[x] F07 liquidity half-life now calls the `liquidity_halflife()` helper on Amihud series instead of using a days-to-liquidate shortcut.

[x] F08 Chow breakpoint diagnostics now run across the strongest correlation pairs, not one arbitrary pair.

[x] F08 sector block analysis is exposed as both a table and chart-ready payload.

[x] F09 decay-adjusted weights now use the actual helper output when available and explicitly fall back to the age grid only when the helper cannot return weights.

[x] F10 ruin probability now uses portfolio volatility from the active weights and covariance matrix instead of a hardcoded proxy.

[x] F10 signal-decay sizing now uses the actual IC decay curve emitted by the alpha decay helper.

[x] F11 Almgren-Chriss trajectory now uses daily return volatility as sigma instead of impact cost.

[x] F11 implementation-shortfall outputs now keep aggregate and Almgren-Chriss frontier schemas separate.

[x] F12 DebtRank now receives an exposure-style matrix derived from normalized portfolio overlap, with proxy status documented in metadata.

[x] F12 cascade and spiral probability inputs now use overlap, leverage, and connectivity derived from the run context/payload.

[x] F13 regime index alignment now uses datetime-indexed regime probabilities.

[x] F13 netting savings now runs on a deterministic trade matrix between equal, Sharpe-momentum, and Kelly-style allocation rules instead of an empty placeholder.

[x] Compile and smoke validation passed for F01-F13 after this fix pass.

[ ] Full peer-book DebtRank remains data-limited because actual peer fund holdings are not present. Current implementation uses normalized overlap as an explicit proxy.

[ ] True rolling rebalance weight stability remains data-limited because historical rebalance snapshots are not persisted yet. F01 now reports cross-objective dispersion instead.

[ ] True inter-strategy netting savings from real strategy order books remains data-limited. F13 now computes netting across generated allocation-rule trade matrices.

## Implementation Checklist — 2026-06-17

[x] Added `black_litterman()` posterior return/covariance calculation.

[x] Added `cvar_minimize()` and `min_cvar_target()` using the Rockafellar-Uryasev LP formulation.

[x] Added `dcc_garch_cov()` as a fast DCC-style estimator using EWMA volatility plus DCC correlation recursion. It is not a full univariate GARCH MLE fit per asset; it is the current-data-safe dynamic covariance implementation.

[x] Added `factor_structured_cov()` using observed factor inputs when supplied, otherwise PCA factor structure from returns.

[x] Added `gerber_statistic_cov()` threshold co-movement covariance.

[x] Added `black_litterman_weights()` and wired Black-Litterman weights into F01.

[x] Added `weight_stability_index()` and wired it into F01 stability output.

[x] F01 now emits Black-Litterman weights, CVaR minimum weights, covariance condition numbers, and DCC average correlation series.

[x] Added PBO CSCV, MinTRL, Harvey-Liu correction, Omega ratio, Ulcer index, Calmar ratio, up/down capture, and Politis-Romano block-length selector.

[x] F02 now emits PBO distribution, richer performance stats, MinTRL, Harvey-Liu adjusted threshold, and block length.

[x] Added Brinson-Fachler, Carino, Menchero, GRAP, X-Sigma-Rho risk attribution, skill/luck bootstrap, and drawdown attribution helpers.

[x] F03 now emits Brinson-Fachler, linking methods, XSR risk attribution, bootstrap skill/luck, and drawdown attribution.

[x] Added historical crisis replay, reverse stress test, Mahalanobis plausibility, and correlation-breakdown stress helpers.

[x] F04 now emits historical crisis scenarios including SVB-style 2023 window when data exists, reverse stress plausibility, correlation stress, and stress verdict.

[x] Added Newey-West regression, MCTE, implied alpha requirements, factor crowding rank, and macro factor risk budget helpers.

[x] F05 now emits Newey-West t-stats, MCTE, implied alpha, factor crowding rank, and factor risk budget.

[x] Added HMM-style regime fit helper, non-homogeneous transition table, Kaplan-Meier survival, regime-conditional covariance, and factor performance by regime.

[x] F06 now emits non-homogeneous transitions, Kaplan-Meier survival curves, regime-conditional correlation matrices, factor performance by regime, and transition alerts.

[x] Added recency-weighted Amihud, liquidity-adjusted VaR primitive, crisis liquidation cost, liquidity frontier, liquidity half-life helper, and regulatory bucket classification.

[x] F07 now emits recency-weighted Amihud, crisis liquidation cost, liquidity frontier, regulatory compliance buckets, and liquidity half-life.

[x] Added precision matrix partial-correlation network, rolling leading eigenvalue, rolling diversification ratio, Chow breakpoint scanner, sector block analysis, and Marchenko-Pastur threshold.

[x] F08 now emits partial-correlation network, rolling leading eigenvalue, diversification ratio series, Chow breakpoints, sector block analysis, pair redundancy report, and MP threshold.

[x] Added IC decay alias, hyperbolic decay fit, optimal rebalance frequency, alpha capacity, post-publication Chow helper, and decay-adjusted weights.

[x] F09 now emits hyperbolic fit, optimal rebalance frequency, alpha capacity proxy, factor zoo comparison, and decay-adjusted weights.

[x] Added drawdown-constrained leverage, geometric growth rate, ruin probability surface, signal-decay sizing, effective Kelly fraction, and turnover-optimal Kelly helpers.

[x] F10 now emits drawdown-constrained leverage, effective Kelly fraction, ruin probability surface, turnover-optimal curve, and signal-decay sizing.

[x] Added Almgren-Chriss closed-form trajectory, IS frontier, IS decomposition, signal-decay urgency, volume-profile trajectory, impact calibration, and correlated multi-asset IS helper.

[x] F11 now emits Almgren-Chriss trajectory, volume-adjusted trajectory, IS decomposition, signal-decay urgency, and correlated multi-asset cross-impact estimate.

[x] Added portfolio overlap index, fire-sale impact, DebtRank propagation, cascade probability, systemic risk contribution, overlap centrality, liquidation spiral probability, and overlap-reducing trade recommendations.

[x] F12 now emits propagated DebtRank, cascade/spiral probability, SRC, overlap centrality, and overlap-reducing reallocation.

[x] Added Sharpe-momentum reallocation, regime-conditional strategy weights, kill-switch P&L calibration, cross-strategy VaR attribution, capacity-constrained reallocation, netting savings helper, and diversification benefit.

[x] F13 now emits Sharpe-momentum weights, regime-conditional strategy weights, kill-switch P&L, cross-strategy risk attribution, capacity-constrained reallocation, diversification benefit, and side-by-side allocation rule chart.

[ ] Full per-asset univariate GARCH MLE feeding DCC is not implemented in this pass. Current `dcc_garch_cov()` is a deterministic DCC-style dynamic covariance estimator from local returns.

[ ] Full Riccati-equation multi-asset Almgren-Chriss optimizer is not implemented. F11 now computes closed-form single-asset AC trajectories and a cross-impact portfolio estimate.

[ ] True post-publication decay report remains data-limited because factor publication dates are not in local parquet.

[ ] True peer-fund systemic risk remains data-limited because actual peer fund books are not present. F12 uses deterministic peer proxies and marks this in metadata.

[ ] True inter-strategy netting savings remains data-limited without per-strategy position books. Helper exists; F13 reports empty until those books are supplied.

## Original Audit

```
analytics.py — MISSING FUNCTIONS (not implemented at all):
→ black_litterman()          # posterior mu_BL, view matrix P/Q/Omega
→ cvar_minimize()            # Rockafellar-Uryasev LP formulation
→ dcc_garch_cov()            # dynamic conditional correlation estimator
→ factor_structured_cov()    # B*Omega*B^T + D (FF5 loading matrix)
→ gerber_statistic_cov()     # co-movement matrix via threshold h
```

```
analytics.py — MISSING FUNCTIONS (optimization):
→ min_cvar_target()          # CVaR frontier analog of _min_var_target()
→ black_litterman_weights()  # full BL posterior into optimizer
→ weight_stability_index()   # rolling sigma of weights across rebalances
```

```
analytics.py — MISSING FUNCTIONS (backtesting/stats):
→ pbo_cscv()                 # combinatorially symmetric cross-validation
→ min_track_record_length()  # MinTRL from Lopez de Prado 2012
→ harvey_liu_correction()    # adjusted SR threshold across M trials
→ omega_ratio()              # integral-based, no distributional assumption
→ ulcer_index()              # sqrt(mean(DD_t^2))
→ calmar_ratio()             # CAGR / max_drawdown
→ up_down_capture()          # up/down month capture vs benchmark
→ politis_romano_block()     # automatic block-length selector
```

```
analytics.py — MISSING FUNCTIONS (attribution):
→ brinson_fachler()          # benchmarked allocation vs total return
→ carino_link()              # logarithmic multi-period smoothing
→ menchero_link()            # optimized coefficient multi-period linking
→ grap_link()                # geometric multi-period linking
→ risk_attribution_xsr()     # X-Sigma-Rho tracking error decomposition
→ skill_luck_bootstrap()     # 10k draws null distribution per sector
→ drawdown_attribution()     # per-asset contribution to each DD episode
```

```
analytics.py — MISSING FUNCTIONS (stress testing):
→ historical_crisis_replay()     # factor return sequence applied to current portfolio
→ hypothetical_factor_shock()    # multi-factor simultaneous with DCC cross-correlations
→ reverse_stress_test()          # min Mahalanobis s.t. portfolio loss <= -L*
→ mahalanobis_percentile()       # F_chi2(k)(D^2) plausibility conversion
→ correlation_breakdown_stress() # reprice under 2008 peak correlation matrix
```

```
analytics.py — MISSING FUNCTIONS (macro/factor):
→ newey_west_regression()    # OLS with Newey-West SE (4 lags)
→ mcte_per_position()        # marginal contribution to tracking error dTE/dw_i
→ implied_alpha_required()   # minimum return to justify active risk per factor
→ factor_crowding_rank()     # loading rank within universe of 500 stocks
→ factor_risk_budget()       # fraction of active risk per macro factor
```

```
analytics.py — MISSING FUNCTIONS (regime):
→ hmm_regime_fit()               # Baum-Welch MLE, forward-backward smoothed probs
→ nonhomogeneous_transition()    # A_ij(t) = softmax(alpha + beta*VIX + gamma*OAS)
→ kaplan_meier_survival()        # S_k(t) per regime, non-parametric
→ regime_conditional_cov()       # separate Sigma_k per regime
→ regime_factor_performance()    # factor mean/Sharpe split by regime label
```

```
analytics.py — MISSING FUNCTIONS (liquidity):
→ recency_weighted_amihud()      # linearly increasing w_t, open-to-close returns only
→ liquidity_adjusted_var()       # VaR + spread cost + gamma*position^2
→ crisis_liquidation_cost()      # 2008-calibrated: volume 30%, spread 5x
→ liquidity_frontier()           # return vs DTL tradeoff across DTL constraints
→ liquidity_halflife()           # lambda = OLS slope of log(ILLIQ) over 60 days
→ regulatory_classification()    # SEC 22e-4 / ESMA UCITS buckets
```

```
analytics.py — MISSING FUNCTIONS (correlation/network):
→ precision_matrix_network()     # Theta = Sigma^-1 regularized, partial correlations
→ leading_eigenvalue_series()    # rolling lambda_1/N time series
→ diversification_ratio_series() # rolling DR = (w^T sigma)/sigma_p
→ chow_test_breakpoints()        # structural break detection per pair
→ equity_bond_correlation()      # rolling 252d corr vs AGG
→ sector_block_analysis()        # 11x11 GICS within/between ratio
→ marchenko_pastur_threshold()   # lambda_max = sigma^2*(1+sqrt(N/T))^2
```

```
analytics.py — MISSING FUNCTIONS (alpha decay):
→ ic_decay_curve()               # IC(h) = corr(signal_t, return_t+h) per horizon h
→ hyperbolic_decay_fit()         # IC(h) = K/(1+lambda*h), AIC model selection
→ optimal_rebalance_frequency()  # argmax_h [IC(h) - 2*TC*h] net alpha per unit time
→ alpha_capacity()               # Q = IC*sigma / (2*kyle_lambda)
→ post_publication_chow()        # structural break at publication date
→ decay_adjusted_weights()       # w_i(t) = w_kelly * IC(age)/IC(0) * exp(-age/t_half)
```

```
analytics.py — MISSING FUNCTIONS (kelly/sizing):
→ drawdown_constrained_leverage()  # m* s.t. E[MDD] <= threshold
→ geometric_growth_rate()          # G(w) = w^T mu - 0.5*w^T Sigma w
→ ruin_probability_surface()       # P(ruin) = exp(-2*mu*capital/(sigma^2*lev^2))
→ signal_decay_sizing()            # w_i(t) scaled by IC(age)/IC(0)
→ effective_kelly_fraction()       # G_constrained / G_unconstrained
→ turnover_optimal_kelly()         # argmax_f [G(f) - C(f)] numerically
```

```
analytics.py — MISSING FUNCTIONS (execution):
→ almgren_chriss_trajectory()    # x(t) = X0*sinh(k(T-t))/sinh(kT)
→ is_efficient_frontier()        # E[IS] vs sqrt(Var[IS]) across all lambda
→ is_decomposition()             # delay + permanent + timing risk + opportunity cost
→ signal_decay_urgency()         # alpha_remaining(t) = alpha0*exp(-t/tau_signal)
→ volume_profile_trajectory()    # U-shape adjusted x_adj(t) from open/close ratio
→ correlated_multiasset_is()     # joint Riccati with cross-impact gamma_ij
→ impact_calibration()           # gamma, eta from historical ADV and spread data
```

```
analytics.py — MISSING FUNCTIONS (systemic risk):
→ portfolio_overlap_index()      # Overlap_ij = sum_k min(w_ik, w_jk)
→ fire_sale_impact()             # price_impact_k = -gamma*(theta*NAV*w_jk)/ADV_k
→ debtrank_propagate()           # V_ij * h_j iterated to convergence
→ cascade_probability()          # Gai-Kapadia Monte Carlo
→ systemic_risk_contribution()   # portfolio delta-CoVaR analog
→ overlap_centrality()           # degree, betweenness, eigenvector centrality
→ liquidation_spiral_prob()      # P(spiral) over Monte Carlo paths
→ overlap_reducing_trades()      # argmin overlap s.t. TE constant
```

```
analytics.py — MISSING FUNCTIONS (multi-strategy):
→ sharpe_momentum_realloc()      # overweight top tertile 1.5x, underweight bottom 0.5x
→ regime_conditional_strategy_weights()  # w(t) = sum_k P(regime_k,t) * w*(regime_k)
→ kill_switch_pnl_calibration()  # cumulative return saved/lost at each trigger level
→ cross_strategy_var_attribution()  # standalone VaR, marginal VaR, diversification credit
→ capacity_constrained_realloc() # redeploy freed capital subject to corr + risk budget
→ netting_savings()              # gross vs net turnover per asset across strategies
→ diversification_benefit()      # DR = sigma_weighted_avg / sigma_combined
```

```
F01 — missing outputs/objectives:
→ Black-Litterman weights
→ CVaR minimization objective
→ Weight stability index
→ Condition number per covariance estimator
→ DCC-GARCH covariance estimator
→ Factor-structured (FF5) covariance estimator
→ Gerber statistic covariance estimator
```

```
F02 — missing outputs/metrics:
→ Probability of Backtest Overfitting (PBO) via CSCV
→ Minimum Track Record Length (MinTRL)
→ Harvey-Liu multiple testing correction
→ Omega ratio
→ Ulcer index
→ Calmar ratio
→ Up/down capture
→ Politis-Romano automatic block-length selector
→ PBO distribution chart
```

```
F03 — missing outputs/frameworks:
→ Multi-period Carino linking
→ Multi-period Menchero linking
→ Multi-period GRAP linking
→ Brinson-Fachler variant
→ Risk-based attribution (X-Sigma-Rho)
→ Skill vs luck bootstrap decomposition
→ GIPS-compatible summary export
```

```
F04 — missing outputs/tests:
→ Historical crisis replay (actual factor return sequences)
→ Hypothetical multi-factor shock with DCC-GARCH cross-factor correlations
→ Reverse stress test (Mahalanobis minimum-severity solver)
→ Reverse stress test plausibility percentile
→ SVB/Signature 2023 crisis scenario
→ Stress verdict card (green/amber/red)
```

```
F05 — missing outputs/metrics:
→ Marginal contribution to tracking error (MCTE) per position
→ Factor crowding signal (loading rank within universe)
→ Implied alpha requirements per factor bet
→ Risk budget utilization panel
→ Factor drift time series with alert dates
```

```
F06 — missing outputs/metrics:
→ Non-homogeneous transition matrix (VIX/OAS-varying)
→ Kaplan-Meier regime survival curves
→ Regime-conditional correlation matrices (separate per regime)
→ Factor performance by regime table
→ Regime transition alert system
```

```
F07 — missing outputs/metrics:
→ Recency-weighted Amihud (linearly increasing weights, open-to-close only)
→ Liquidation cost under crisis / 2008-calibrated stress
→ Liquidity frontier (return vs DTL tradeoff curve)
→ Regulatory compliance report (SEC 22e-4 / ESMA UCITS classification)
→ Liquidity half-life per position
```

```
F08 — missing outputs/metrics:
→ Precision matrix / partial correlation network
→ Partial correlation network diagram
→ Leading eigenvalue time series (rolling)
→ Diversification ratio time series (rolling)
→ Correlation regime shift detector (DCC-GARCH + Chow test breakpoints)
→ Equity-bond correlation tracker
→ Sector block analysis (11x11 GICS within/between ratio)
→ Pair-level redundancy report
```

```
F09 — missing outputs/metrics:
→ Hyperbolic decay model fitting (IC(h) = K/(1+λh))
→ Optimal rebalancing frequency (net alpha per unit time maximization)
→ Alpha capacity estimation (Kyle 1985 lambda)
→ Decay-adjusted position sizing (weight shrinks as signal ages)
→ Factor zoo comparison table
→ Post-publication decay report
```

```
F10 — missing outputs/metrics:
→ Drawdown-constrained Kelly leverage (E[MDD] derivation)
→ Signal-decay adjusted sizing (connected from F09 half-life)
→ Effective Kelly fraction under constraints (G_constrained / G_unconstrained)
→ Ruin probability surface (contour plot over mu vs sigma²)
→ Kelly vs MVO comparison chart
→ Turnover-optimal f* plotted as G(f) - C(f) curve
```

```
F11 (Execution — mapped as F12 in code) — missing outputs/metrics:
→ Almgren-Chriss optimal trajectory (full closed-form)
→ IS efficient frontier (E[IS] vs sqrt(Var[IS]) across all lambda)
→ IS decomposition (delay + permanent impact + timing risk + opportunity cost)
→ Signal decay-adjusted urgency (alpha remaining during execution)
→ Volume profile-adjusted trajectory (U-shape intraday approximation)
→ Correlated multi-asset joint liquidation (cross-impact Riccati equations)
```

```
F12 (Systemic Risk — mapped as F12 in code, conflicts with execution) — missing:
→ DebtRank propagation (Battiston et al. 2012 network convergence)
→ Cascade probability via Gai-Kapadia Monte Carlo
→ Systemic risk contribution (SRC) per position
→ Overlap network centrality (degree, betweenness, eigenvector)
→ Liquidation spiral probability
→ Overlap-reducing reallocation recommendation
```

```
F13 — missing outputs/metrics:
→ Sharpe-momentum reallocation rule
→ Regime-conditional strategy weights (connected from F06)
→ Drawdown kill-switch P&L calibration
→ Cross-strategy risk attribution (marginal VaR + diversification credit)
→ Capacity-constrained reallocation (connected from F09 alpha capacity)
→ Inter-strategy turnover netting savings report
→ Dynamic allocation time series under all reallocation rules side-by-side
```
