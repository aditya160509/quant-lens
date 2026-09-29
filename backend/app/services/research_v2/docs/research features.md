QUANT360 — RESEARCH MODULE
Complete Mathematical and Computational Specification
DESIGN PHILOSOPHY
Every other module on this platform is analytical — it gives you answers about what is happening in markets. This module is different. It is the place where you come to ask whether something you found is actually true. The entire empirical finance literature is built on a small set of canonical procedures that every researcher repeats from scratch in R, Stata, or Python each time they start a new project. The infrastructure is not the contribution — the idea is. This module eliminates the infrastructure cost entirely. A researcher brings their idea, configures it through structured menus, and receives publication-grade output with every diagnostic, assumption test, and robustness check the literature requires. Nothing arbitrary. Nothing AI-generated. Pure rigorous statistical machinery applied to structured inputs. The result is either a defensible empirical finding or a clearly killed hypothesis — both outcomes have value.

FEATURE 1 — THE CANONICAL TEST ENGINE
What You Are Building
The single most-used set of procedures in empirical finance, unified in one place. Every paper in asset pricing, corporate finance, and market microstructure runs a subset of these tests. Researchers currently build each one individually from scratch. You give them all of them simultaneously, with every standard error option, every output format, and every diagnostic built in.

Custom Inputs
Parameter Options
Asset universe Broad market, large cap only (top market cap tercile), mid cap, small cap, ex-financials, ex-utilities, ex-microcaps, user-defined ticker list (comma-separated), any combination
Time period 2010 to present; user-defined start date and end date; minimum window enforced per test
Signal definition Pre-built signals from factor module (value, momentum, quality, low-vol, size, profitability, investment); pre-built signals from volatility module (Yang-Zhang vol, GK vol, VRP, regime probability); user-inputs raw cross-sectional rankings (1 to N integer ranks per asset per period uploaded as structured CSV)
Dependent variable 1-month forward return, 3-month forward return, 6-month forward return, 12-month forward return, risk-adjusted return (FF3 or FF5 alpha), realized volatility 1-month forward, bid-ask spread, trading volume
Control variables Market beta, log market cap, book-to-market, 12-1 momentum, 1-month reversal, idiosyncratic volatility, asset growth, profitability, leverage — any combination selected from fixed menu
Standard errors OLS, Newey-West (user-set lag length 1 to 24 months), clustered by time, clustered by asset, double-clustered by time and asset, Driscoll-Kraay for spatial and temporal dependence
FM variance regime check Auto-detect (compares N/T ratio against known validity thresholds)
Weak identification check On (default) / off
EIV correction method Shanken (SE only) / One-step GMM (corrects estimate itself)
Bootstrap sort inference Off / On — stationary bootstrap, 1000/2000 replications, block length auto or user-set
Weighting scheme Equal-weight, value-weight (market cap), rank-weight
Rebalancing frequency Monthly, quarterly, annual
Number of sort portfolios Terciles (3), quintiles (5), deciles (10)
Double sort type Independent (4×4, 5×5 grids), sequential (conditional sort)
Factor benchmark CAPM, Fama-French 3-factor, Fama-French 5-factor, Fama-French 5-factor plus momentum, user-defined combination
Tests Included
Fama-MacBeth Two-Stage Cross-Sectional Regression

Stage 1: At each month t, run a cross-sectional OLS regression of asset returns on signal scores and controls across all N assets. Produces a time series of slope coefficients {β̂_t}.

Stage 2: Compute the time-series mean of each slope coefficient and test whether it is statistically different from zero.

λ̂ = (1/T) Σ_t β̂_t

Standard error: SE_FM = std(β̂_t) / √T

Shanken correction for errors-in-variables bias (when betas are estimated in Stage 1 rather than directly observed): multiply the standard error by √(1 + λ̂' Σ_f^{-1} λ̂) where Σ_f is the factor return covariance matrix. This is the Shanken (1992) correction that accounts for sampling error in the Stage 1 beta estimates propagating into Stage 2.

FM variance regime check: before reporting λ̂, the platform compares N/T against known Fama-MacBeth validity thresholds. If the panel is in a conservative or invalid regime, the Research Module auto-switches to a corrected estimator and flags the result with an FM validity indicator.

Weak identification check: scans the first-stage beta matrix for small or collinear betas and flags possible bias before the point estimate is shown.

EIV correction method: optionally replace Shanken-only correction with one-step GMM to correct the estimate itself rather than only its SE.

t-statistic: t = λ̂ / SE_FM (Shanken-corrected)

Panel OLS with Fixed Effects

Pooled OLS, time fixed effects only, asset fixed effects only, double fixed effects (within estimator). Residual standard errors clustered by the user-selected dimension. Hausman test for endogeneity of fixed effects reported automatically.

Single Portfolio Sort

At each rebalancing date t, sort all N assets into K portfolios by signal rank. Compute the equal- or value-weighted return of each portfolio in the subsequent holding period. Report the time-series mean return, standard deviation, Sharpe ratio, and alpha (from FF5 regression) for each portfolio and for the long-short spread (top minus bottom).

Double Portfolio Sort

Independent sort: sort independently on two signals, form K×K portfolios (e.g., 5×5 = 25 portfolios), report the full return matrix. Identifies whether signal 1 predicts returns after controlling for signal 2.

Sequential sort: first sort on signal 1, then within each signal-1 quintile sort on signal 2. Produces a cleaner within-group test but reduces power.

GRS Test of Joint Alpha Significance (Gibbons, Ross, Shanken 1989)

Tests whether the K sorted portfolio alphas are jointly equal to zero — the formal test of whether a factor model is correctly specified for this set of assets.

GRS = (T/K) × ((T-N-K)/(T-N)) × [1 + μ̂'_f Ω̂_f^{-1} μ̂_f]^{-1} × α̂' Σ̂^{-1} α̂

where α̂ is the K×1 vector of portfolio alphas, Σ̂ is the K×K residual covariance matrix, μ̂_f is the N_factor-dimensional vector of mean factor returns, and Ω̂_f is the factor return covariance matrix.

Under the null of all zero alphas: GRS ~ F(K, T-N-K)

p-value: P(F(K, T-N-K) > GRS_observed)

Reject at 5%: the model fails to price this cross-section and the signal captures something the benchmark factors miss.

Patton-Timmermann Monotonicity Test

Tests whether the expected monotonic ordering of returns across sort portfolios (Q1 < Q2 < ... < QK) holds — not just the top-minus-bottom spread.

MR statistic: bootstrap-based test of the null that returns are weakly monotonically increasing across all K portfolios simultaneously. Under the null, returns can be in any order. Under the alternative, they are monotonically ordered.

Bootstrap procedure: draw B = 1000 block bootstrap samples of the T×K return matrix (block length = 12 months to preserve time-series dependence). For each sample, compute the proportion of adjacent portfolio pairs where Q\_{k+1} > Q_k. The MR statistic is the fraction of all B bootstrap samples where this monotonicity condition holds more strongly than in the data. p-value = 1 − MR.

This test is strictly more powerful than the top-minus-bottom t-test when there are 5 or more portfolios because it uses all K-1 adjacent comparisons simultaneously.

Rolling Regression

OLS regression of the dependent variable on the signal, estimated on a rolling window of user-defined length (12, 24, 36, 60 months). Produces a time series of rolling coefficients with 95% confidence bands. Identifies whether the predictive relationship is stable or whether it strengthens and weakens over time.

Calendar-Time Portfolio Approach

At each calendar month t, form a portfolio of all assets that triggered a user-defined event condition in the prior N months (N = 3, 6, 12, 24 — user-set). Regress the monthly portfolio return on FF5 factors. The intercept is the long-run abnormal return of the event with correct time-series inference. This is the standard alternative to CAR-based event studies that avoids clustering problems.

Factor Spanning Test

Tests whether a signal adds incremental explanatory power beyond existing factor benchmarks. Regress the signal's long-short portfolio return on the factor benchmark:

R\_{LS,t} = α + β₁ × Mkt_t + β₂ × SMB_t + β₃ × HML_t + β₄ × RMW_t + β₅ × CMA_t + β₆ × UMD_t + ε_t

If α is statistically significant: the signal is not spanned by the benchmark — it captures something genuinely new. If α ≈ 0: the signal is redundant.

Outputs
Output Description
Fama-MacBeth regression table Coefficient λ̂, Shanken-corrected SE, t-statistic, p-value, R² per cross-section (mean and std), sample size, time period. Journal-formatted with significance stars
Panel OLS table Coefficient, clustered SE, t-statistic, R², within-R², fixed effects indicators, Hausman test p-value
Portfolio sort table Mean return, std, Sharpe, FF5 alpha, t-statistic for each portfolio and for the long-short spread
Double sort matrix K×K table of mean returns; row-by-row and column-by-column spreads
GRS test output GRS statistic, degrees of freedom, p-value, mean alpha across portfolios, Sharpe ratio of the tangency portfolio formed from the pricing errors
Monotonicity test output MR statistic, bootstrap p-value, proportion of adjacent pairs ordered correctly, comparison to top-minus-bottom t-test
Rolling coefficient chart Time series of rolling β̂ with 95% bands; horizontal line at zero; periods where the coefficient is significantly positive shaded green, significantly negative shaded red
Factor spanning table α, t-statistic, full factor loadings, R², Newey-West SE with lag = 4
FM validity flag “Your N/T ratio places this in the [valid / conservative / invalid] regime for classical FM SEs — [corrected SE reported instead]”
Weak identification card Flags small/collinear betas before the point estimate is shown, states the likely bias direction
GMM vs Shanken comparison Side-by-side λ̂ and standard errors under both corrections, flagged if they materially disagree
Bootstrap vs t-test disagreement flag Highlights any portfolio spread where bootstrap and classical t-test give different significance verdicts
LaTeX export All tables formatted in LaTeX code, copy-paste ready for any journal submission
CSV export All numerical outputs
Data Map
Series Source Code / Ticker Used In
Daily and monthly OHLCV for all assets Yahoo Finance / Stooq Per ticker All tests
Fama-French 3, 5, momentum factors Ken French data library FF3, FF5, MOM Spanning test, alpha, GRS
Pre-built signal series from Factor module Internal output — Signal definition
Pre-built vol series from Volatility module Internal output — Signal definition
Risk-free rate FRED DGS3MO (3-month T-bill) Sharpe ratio, alpha
FEATURE 2 — THE ROBUSTNESS ENGINE
What You Are Building
A systematic specification variation engine that takes any result — from Feature 1 or from the researcher's own external work — and automatically re-runs it across every dimension of legitimate variation that reviewers will ask about. The output is a robustness matrix that either confirms a finding survives or honestly shows where it breaks. This is the single most time-consuming part of empirical research and the part that most often determines whether a paper is accepted or rejected.

Custom Inputs
Parameter Options
Base result input Run directly from Feature 1 (auto-populates), or manual input (coefficient, SE, t-statistic, R², sample period, specification description)
Mode Sequential (current, one dimension at a time) / Full specification curve (every combination simultaneously)
Max specifications Auto-computed from selected dimensions, hard cap 5,000 for compute; warning shown before running
Weighting philosophy Unweighted (all specs equal) / AIC-weighted / BIC-weighted / sample-size-weighted
Time window variations Rolling 5-year, rolling 10-year, full sample; user-defined start/end date splits at any month
Subsample splits Pre-2008 vs post-2008, pre-2020 vs post-2020, pre-2022 vs post-2022, user-defined split date
Crisis exclusion toggles Exclude 2008-2009 (GFC), exclude March-April 2020 (COVID crash), exclude 2022 rate shock, exclude Liberation Day Apr-May 2025, user-defined exclusion window
Universe variations Broad market → large cap only, broad market → ex-financials, broad market → ex-utilities, top 500 by market cap, top 1000 by market cap
Signal transformations Raw signal → winsorized at 1%/99%, raw signal → rank-normalized (uniform distribution), raw signal → standardized z-score, raw signal → decile-dummied
Control variable variations Baseline (no controls), add size, add size + value, add size + value + momentum, add size + value + momentum + volatility, full controls — all sequentially in separate columns
Standard error variations OLS → Newey-West (lag 3), Newey-West (lag 6), Newey-West (lag 12), clustered by time, clustered by asset, double-clustered
Weighting variations Equal-weight → value-weight → rank-weight
Tests Run Automatically
For each specification variation, the platform re-runs the exact same test as the base result with only that one dimension changed. This produces a clean robustness matrix where each row is one change and columns show how the result responds.

Coefficient stability: does the coefficient maintain its sign and rough magnitude across all rows?

Statistical significance persistence: in how many of the Y specification variations does the result remain significant at the 5% level? At the 10% level?

Economic magnitude stability: does the economic effect size (annualized return spread, or coefficient × signal standard deviation) stay within 50% of the base result across all variations?

Joint permutation test: when full specification curve mode is active, compute a permutation-based p-value on the curve's median or weighted-average effect against a null distribution built by reshuffling the underlying signal.

Researcher degrees of freedom count: compute the number of distinct reasonable specifications available from the selected dimensions before running.

Decision-attribution panel: determine which single specification choice (universe, controls, SE, weighting, etc.) explains the most variance in the curve.

Outputs
Output Description
Robustness matrix Full table: rows are specification variations, columns are coefficient, SE, t-statistic, significance stars, R², sample size. Color gradient: dark green for strongest result, white for boundary, red for sign flip or insignificance
Specification curve chart Every specification's point estimate sorted and plotted as a curve, with a decision panel below showing which choice was active for each point
Curve-level joint p-value Single permutation-based significance test on the whole curve, not per-specification
Researcher degrees of freedom counter "You had access to N distinct reasonable specifications" computed before running
Decision-attribution panel Which single specification choice explains the most variance in the curve
Robustness summary line "Result significant in X of Y specifications (Z%). Coefficient positive in W of Y specifications." — the single most important line in the table
Weakest specification flag The single specification where the result is weakest, with plain-language explanation of why
Strongest specification flag The single specification where the result is strongest — equally important for understanding what is driving the finding
Coefficient stability chart Box plot of the distribution of coefficients across all specification variations, showing median, interquartile range, and outliers
Economic magnitude range Min and max of the annualized return spread across all specifications
LaTeX export Formatted robustness table ready for a paper's appendix
Data Map
Series Source Used In
All data from Feature 1 Internal / Yahoo Finance / Ken French All variations
No additional data required — —
FEATURE 3 — THE PLACEBO AND FALSIFICATION SUITE
What You Are Building
A structured battery of tests designed to show that a result is real by demonstrating that it dies when it should die. Every serious empirical finance paper includes at least one falsification test. This feature provides four of the most powerful and widely cited ones, all automatically generated. The output is either validation that the finding is genuine or a clean flag that it is spurious — both are valuable.

Custom Inputs
Parameter Options
Base result input From Feature 1 (auto-populates) or manual input
Placebos to activate Any subset or all four — independently selectable
Permutation replications 500, 1000, 2000 (default 1000)
Time displacement period 6 months, 1 year, 2 years forward
Out-of-sample split 50/50, 60/40, 70/30 (first fraction for estimation, remainder for OOS evaluation)
Adjacent asset class If main test is on equities: run same test on fixed income returns, commodity returns, FX returns — tests whether an equity-specific mechanism is driving the result or whether it is just a statistical pattern
Placebos Included
Combined significance method Fisher's method / Stouffer's method
Power analysis On (default) / off
Protected OOS window None / reserve most recent N months, locked from all other platform features once reserved

Permutation Placebo

Randomly shuffle the signal values across assets within each time period 1000 times, destroying any signal-return relationship while preserving the cross-sectional distribution of both signals and returns. Re-run the full test on each shuffled dataset.

Produces an empirical null distribution of t-statistics under the null of no relationship. The real t-statistic is then placed against this distribution.

Permutation p-value: fraction of 1000 shuffled t-statistics that exceed the real t-statistic in absolute value. A permutation p-value below 0.05 means the real result is in the top 5% of what random noise can produce — the result is unlikely to be spurious.

Visual: histogram of the 1000 shuffled t-statistics with a vertical red line at the real t-statistic. If the real result is far in the tail, the finding is genuine. If it is in the middle of the distribution, it is noise.

Time Displacement Placebo

Use the signal value from T+12 months in the future (or T+6, T+24 — user-set) to predict returns at time T. If the signal contains genuine predictive information about future returns, the future signal should not predict past returns. If the time-displaced result is also significant, the signal is not truly predictive — it is correlated with something contemporaneous rather than leading it.

This is the most direct test of whether the signal has genuine forward-looking information content.

Wrong-Direction Placebo

Multiply the signal by -1 and re-run the full test. If the original result is positive (high signal predicts high returns), the flipped signal should produce a negative result of similar magnitude. If the result does not flip cleanly — for example, if both the original and flipped signal both produce positive returns — then the signal is not the mechanism and something else is driving the result (e.g., a size bias, a market beta tilt, or a look-ahead bias).

Out-of-Sample McLean-Pontiff Test

Estimate the model on the first X% of the sample (e.g., 70%). Evaluate the estimated model on the remaining (100-X)%. Compare the OOS coefficient to the in-sample coefficient.

OOS R²: R²*OOS = 1 − Σ_t∈OOS (ŷ_t^{IS} − y_t)² / Σ_t∈OOS (ȳ*{IS} − y_t)²

where ŷ*t^{IS} is the prediction from the in-sample model applied to OOS data and ȳ*{IS} is the in-sample mean. R²_OOS > 0 means the model outperforms the historical mean out-of-sample.

OOS coefficient stability: ratio of OOS coefficient to IS coefficient. Ratio > 0.7 means strong OOS stability. Ratio < 0.3 means the finding is likely a data-mining artifact.

This is the McLean-Pontiff (2016) framework applied within sample rather than requiring actual post-publication data.

Adjacent Asset Class Placebo

Re-run the exact same test on a completely different asset class (equities → government bonds, equities → commodities, equities → FX). If an equity-specific mechanism is driving the result (e.g., the leverage effect, the value premium, earnings momentum), it should not appear in bond or commodity returns. If it does appear with similar magnitude, the result is more likely a statistical artifact than a genuine economic mechanism.

Outputs
Output Description
Permutation distribution chart Histogram of 1000 shuffled t-statistics with real t-statistic marked as vertical line. p-value from permutation distribution annotated
Combined placebo significance Single Fisher/Stouffer p-value replacing the hand-built green/amber/red count
Power disclosure card "This placebo battery has ~X% power to detect a spurious result at your sample size" shown alongside the verdict
Protected-window OOS result True holdout test result, flagged as genuinely out-of-sample rather than an in-platform split
Time displacement result Side-by-side table: real coefficient and t-statistic vs time-displaced coefficient and t-statistic. Should be near zero for a genuine signal
Wrong-direction result Side-by-side table: real result vs flipped-signal result. Should be of equal magnitude and opposite sign
OOS McLean-Pontiff panel IS coefficient, OOS coefficient, OOS/IS ratio, OOS R², OOS period length. Color: green if OOS/IS > 0.7, amber if 0.3-0.7, red if < 0.3
Adjacent asset class panel Same test applied to 2-3 alternative asset classes. Result should be insignificant if mechanism is asset-class-specific
Falsification verdict card Green: all four placebos pass (result is real). Amber: 2-3 placebos pass (result is plausible but fragile). Red: fewer than 2 placebos pass (result is likely spurious). Most emotionally impactful output in the module
Data Map
Series Source Used In
Signal and return series from Feature 1 Internal All placebos
Fixed income returns (for adjacent asset test) FRED: 10Y Treasury, investment grade index Adjacent class
Commodity returns (for adjacent asset test) Yahoo Finance: GLD, USO, DJP Adjacent class
FX returns (for adjacent asset test) FRED: DEXUSEU, DEXJPUS Adjacent class
FEATURE 4 — THE REGIME CONDITIONAL ANALYZER
What You Are Building
A conditional testing engine that re-runs any base test separately within different market states, then formally tests whether the result is statistically different across states. The unconditional result tells you what happens on average. The regime-conditional result tells you when it works and when it doesn't — which is almost always a more interesting and more publishable finding.

Custom Inputs
Parameter Options
Base result input From Feature 1 or manual
Conditioning variables VIX level above/below 20, VIX level above/below 30, yield curve slope positive vs inverted (DGS10 minus DGS2 positive vs negative), trailing 12-month market return positive vs negative, trailing 6-month market return positive vs negative, realized vol in top vs bottom tercile of trailing 5-year history, credit spread above/below trailing 5-year median (BAMLC0A0CM), NBER recession indicator on/off, expansion vs contraction (user-defined rule), regime state from platform's Feature 4 Volatility module (low-vol, medium-vol, high-vol, crisis)
Threshold selection Fixed (current menu) / Data-driven search (grid search over conditioning variable for max Chow F-stat)
Regime structure Two-state (current) / Quantile regression across full range / Markov-switching (latent regime, jointly estimated)
Number of simultaneous conditions 1 or 2 (intersection of two conditions — e.g., high VIX AND inverted yield curve)
Minimum observations Minimum number of months required in each conditional subsample before the test is run (default 24 months)
Tests Run Automatically
Conditional regression — re-run the base Feature 1 regression restricted to observations in each regime state. Report coefficient, SE, t-statistic per state.

Chow test for structural difference — formally tests whether the coefficients across two regime states are statistically different from each other.

F_Chow = [(RSS_pooled − RSS_regime1 − RSS_regime2) / k] / [(RSS_regime1 + RSS_regime2) / (n₁ + n₂ − 2k)]

where RSS is residual sum of squares and k is the number of parameters. Under the null of equal coefficients: F_Chow ~ F(k, n₁+n₂-2k). A significant Chow test (p < 0.05) confirms the finding is genuinely regime-dependent — it is not just sampling variation that makes the two estimates look different.

Threshold search: when data-driven threshold selection is enabled, the platform grid-searches the conditioning variable for the cutoff that maximizes the Chow F-statistic, in the spirit of Andrews tests but over the state variable instead of time.

Quantile regression: fit coefficients continuously across the full range of the conditioning variable using quantile regression rather than a binary split.

Markov-switching model: estimate a latent two-state regime model jointly with regime-specific coefficients, removing the need for an externally imposed threshold.

Interaction term test — augments the pooled regression with a regime dummy variable and a signal × regime interaction term. The interaction coefficient tests whether the signal's predictive power is significantly higher or lower in one regime than another, within a single unified regression. More efficient than running two separate regressions because it uses all observations.

r*{i,t+h} = α + β × signal*{i,t} + γ × regime*t + δ × (signal*{i,t} × regime_t) + controls + ε

δ is the interaction coefficient. t-statistic on δ is the primary test of regime-dependence. Large |δ| means the signal behaves very differently across regimes.

Economic magnitude by regime — the annualized return spread (long-short portfolio mean return × 12) separately in each regime state. The ratio of high-stress to low-stress spread gives the "regime amplification factor."

Outputs
Output Description
Regime-conditional coefficient table Coefficient and t-statistic in each regime state, side by side, with sample size per state
Chow test result F-statistic, degrees of freedom, p-value, plain-language verdict (statistically different vs not statistically different)
Interaction term table Full regression table with signal, regime dummy, and interaction term. Primary focus: interaction coefficient and its t-statistic
Coefficient comparison chart Visual showing coefficient ± 95% confidence interval in each regime state side by side — the clearest possible display of whether the result is regime-dependent
Regime-conditional Sharpe ratio Long-short portfolio Sharpe ratio in each regime. Often more striking than the return difference because it captures risk-adjusted magnitude
Economic magnitude table Annualized long-short return spread in each regime, with regime amplification factor (ratio of strongest to weakest regime)
Data Map
Series Source Code Used In
VIX daily level FRED VIXCLS VIX conditioning
2Y and 10Y Treasury yields FRED DGS2, DGS10 Yield curve conditioning
IG credit spread FRED BAMLC0A0CM Credit conditioning
NBER recession dates FRED USREC Recession conditioning
Market return Yahoo Finance ^GSPC Momentum conditioning
Realized vol from Volatility module Internal — Vol regime conditioning
Regime probabilities from Volatility module Internal — Regime state conditioning
FEATURE 5 — THE DIAGNOSTIC CENTER
What You Are Building
A full statistical validity report that runs automatically on any regression result. Reviewers always ask about these diagnostics. Researchers almost always skip building them because they are tedious to code and tangential to the main analysis. You make them automatic and mass-friendly by presenting every test result in plain language with a specific correction recommendation, not just a number.

Custom Inputs
Parameter Options
Base result input From Feature 1 or manual input of residuals and fitted values
Significance level for flagging 1%, 5%, 10%
Structural break candidate dates Auto-scan full sample (Andrews), or user-specified date (Chow)
Influential observation threshold Top 5, top 10, top 20 most influential dates flagged
RESET test On (default)
Partial residual plots Toggle per regressor
Extended influence diagnostics DFBETA / DFFITS, toggle on top of existing Cook's distance
Tests Run Automatically
Multicollinearity — Variance Inflation Factor (VIF)

For each control variable j in the regression: regress it on all other regressors. VIF_j = 1 / (1 − R²_j).

VIF < 5: no problem. VIF 5-10: moderate concern, flagged amber. VIF > 10: severe multicollinearity, flagged red. Recommendation: drop the variable with highest VIF or orthogonalize correlated controls.

Residual Autocorrelation — Durbin-Watson and Ljung-Box

Durbin-Watson: d = Σ*{t=2}^{T} (ε̂_t − ε̂*{t-1})² / Σ_t ε̂²_t. d ≈ 2 means no autocorrelation. d < 1.5 or d > 2.5 flagged.

Ljung-Box at lags 1, 5, 12, 21: Q*LB(L) = T(T+2) Σ*{l=1}^{L} ρ̂²_l / (T-l) ~ χ²_L under null. Significant Q at lag l means autocorrelation up to lag l is present. Recommendation: switch to Newey-West standard errors with bandwidth = significant lag.

Heteroskedasticity — White Test and Breusch-Pagan

White test: regress ε̂²_t on all regressors, their squares, and cross-products. nR² ~ χ² under null of homoskedasticity. Significant: standard OLS SEs are invalid.

Breusch-Pagan: regress ε̂²_t on regressors only (simpler version). Same null.

Recommendation: switch to heteroskedasticity-robust or clustered standard errors.

Structural Break — Chow Test and Andrews Supremum Test

Chow test at user-specified date τ: split sample into [t₀, τ] and [τ+1, T]. F_Chow as defined in Feature 4. Tests whether the regression coefficients are the same before and after the break date.

Andrews (1993) supremum test: scan all candidate break dates in the central 70% of the sample (avoid the tails where subsample sizes are too small). Compute the Chow F-statistic at each candidate date. The supremum statistic is max\_{τ} F_Chow(τ). Compare against Andrews (1993) critical values for the supremum test, which account for the multiple testing across all candidate dates.

If significant: the relationship is unstable and the full-sample coefficient is an average of potentially very different pre- and post-break coefficients. The estimated break date is reported with a confidence interval.

Non-normality — Jarque-Bera

JB = T/6 × (skewness² + (kurtosis − 3)²/4) ~ χ²(2) under normality. Significant: residuals are non-normal, which matters for small samples but is asymptotically unimportant. Recommendation: use bootstrap standard errors if T < 60.

RESET test — regress residuals on powers of fitted values to detect missing nonlinear structure. Significant result flags potential model misspecification and recommends polynomial or interaction terms.

Partial residual plots — component-plus-residual plots for each regressor, enabling visual diagnosis of whether a nonlinear transformation is needed.

DFBETA / DFFITS — compute coefficient-level influence diagnostics for every observation. DFBETA measures the effect of dropping each observation on each coefficient, while DFFITS measures the effect on predicted values. Both are reported for top influencers.

Influential Observations — Cook's Distance

Cook's*i = (β̂*{(-i)} − β̂)' (X'X) (β̂\_{(-i)} − β̂) / (k × s²)

where β̂\_{(-i)} is the coefficient vector estimated with observation i removed. Large Cook's distance means observation i has high leverage on the estimates.

Flag top 10 dates by Cook's distance. For each flagged date: the date, the asset or time period it corresponds to, and the change in the main coefficient if that observation is removed. If removing a single month changes the coefficient by more than 20%, the result is fragile to outliers.

Outputs
Output Description
Diagnostic report card One row per test. Column 1: test name. Column 2: test statistic. Column 3: p-value or threshold comparison. Column 4: green tick or red flag. Column 5: plain-language explanation. Column 6: specific recommended correction. Designed so a researcher who does not know econometrics can still act on every red flag
VIF table Each regressor with its VIF, color-coded
Residual autocorrelation correlogram Bar chart of autocorrelations ρ̂_l for l = 1 to 24, with 95% confidence bands. Bars outside the bands indicate significant autocorrelation at that lag
Residual heteroskedasticity plot Scatter plot of ε̂² against fitted values. A flat cloud means homoskedasticity. A funnel or pattern means heteroskedasticity
RESET test result Statistic, p-value, plain-language flag for missing nonlinear structure
Partial residual plots One plot per regressor showing component-plus-residuals to diagnose functional-form misspecification
DFBETA / DFFITS table Top influencers on each coefficient and on predicted values, highlighting which observations drive the result most
Andrews structural break chart F-statistic at each candidate break date plotted as a time series, with the Andrews 5% critical value as a horizontal dashed line. The peak identifies the most likely break date
Influential observation table Top 10 dates by Cook's distance: date, Cook's D, coefficient with this observation, coefficient without this observation, change in percentage
Data Map
All inputs are the regression residuals and fitted values from Feature 1 or user-uploaded. No additional external data required.

FEATURE 6 — THE SPECIFICATION BUILDER AND PUBLICATION OUTPUT
What You Are Building
A multi-column regression table builder that produces publication-grade output automatically. The researcher builds up their main results table exactly the way a journal paper does — one model at a time, each adding a layer of controls or robustness — and receives a formatted table ready for submission. The LaTeX output is the defining feature for academic users: nobody else generates correctly formatted journal-table LaTeX automatically.

Custom Inputs
Parameter Options
Number of model columns 2 to 8 (each column is one specification)
Per-column configuration For each column: dependent variable, signal, control set, standard error type, fixed effects, weighting, time period — all independently configurable
Table title User-defined free text
Variable labels User-defined display names for each coefficient row (e.g., rename "signal_rank" to "Value Signal")
Significance stars \*10%, **5%, \***1% (standard); **5%, \***1% only; custom thresholds
Additional statistics shown R², adjusted R², within-R², sample size, time period, fixed effects indicators — all toggleable
Notes row User-defined free text for the table notes (appears below the table)
Auto-populate source Manual (current) / From Feature 2 specification curve median or mode
Confirmatory tagging Off / On (requires a locked spec from Feature 2 or 1)
What It Produces
The researcher configures each column through the same input menus as Feature 1. They click Run All. The platform runs all specified models simultaneously and assembles the results into a single formatted output.

Column 1: baseline signal only, no controls, no fixed effects. Column 2: signal + size control. Column 3: signal + size + value. Column 4: signal + full controls, no fixed effects. Column 5: signal + full controls + time fixed effects. Column 6: signal + full controls + asset fixed effects. Column 7: signal + full controls + double fixed effects. Column 8: alternative signal definition for comparison.

This is exactly the structure of the main results table in any top finance journal paper.

Outputs
Output Description
Formatted HTML table Rendered in the browser exactly as it would appear in a journal. Coefficients in each cell, standard errors in parentheses below, significance stars, horizontal lines separating header, body, and statistics rows
LaTeX export Complete LaTeX table code using the booktabs package (the journal standard). Column alignment, \midrule, \toprule, \bottomrule, all correctly formatted. Copy-paste directly into any LaTeX document — works immediately
PDF export Rendered as a standalone PDF page formatted at journal width (6.5 inches)
CSV export All coefficients and standard errors as structured data for further processing
Auto-built table from curve Main table columns chosen algorithmically from the robustness distribution rather than hand-picked
Confirmatory/exploratory tags in LaTeX Every column visibly marked in both the HTML and LaTeX export
Coefficient plot Forest plot version of the table: coefficients as dots with 95% confidence interval bars, one color per model column. Allows visual comparison of how the coefficient changes as controls are added
Data Map
Same as Feature 1. No additional data required.

FEATURE 7 — THE CAUSAL IDENTIFICATION ENGINE
Design Philosophy
Finance is years behind applied microeconomics in causal identification. The credibility revolution — the shift from showing correlations to credibly identifying causal effects — has transformed economics but arrived late to finance. The reason is not lack of interest. It is lack of accessible infrastructure. Difference-in-differences with staggered timing, regression discontinuity with correct bandwidth selection, and instrumental variables with weak-instrument diagnostics each require substantial econometric code that researchers build from scratch in R or Stata. This feature gives them four fully implemented causal identification frameworks, each with every required diagnostic and robustness check, in a structured browser interface. A researcher who uses this feature can make a causal claim in their paper, not just a correlational one. That distinction increasingly determines whether a paper is accepted at a top journal.

Custom Inputs
Parameter Options
Causal framework Difference-in-Differences, Event Study with Abnormal Returns, Regression Discontinuity, Instrumental Variables — select one or run multiple
Outcome variable Forward return (1M, 3M, 6M, 12M), realized volatility, trading volume, bid-ask spread, any metric from platform modules
Asset universe Broad market, large cap only, ex-financials, user-defined ticker list
Time period 2010 to present, user-defined
Standard errors HC2 heteroskedasticity-robust, clustered by asset, clustered by time, double-clustered
Bootstrap replications 500, 1000, 2000
Significance level 1%, 5%, 10%
Framework 1 — Difference-in-Differences
What it tests: Whether a market event, policy change, regulatory shock, or structural shift had a causal effect by comparing treated assets to untreated controls before and after the event.

Framework-Specific Inputs:

Parameter Options
Treatment definition Index inclusion/exclusion, rating change, regulatory threshold crossing, user-defined binary event (CSV of asset, treatment date pairs)
Treatment timing Single event date (canonical 2×2 DiD), staggered adoption (different assets treated at different dates)
Control group All untreated assets, nearest-neighbor matched controls on pre-period characteristics (propensity score matching using logistic regression on market cap, beta, value, momentum — user selects matching variables)
Pre-period 3, 6, 12, 24, 36 months
Post-period 3, 6, 12, 24, 36 months
Covariates From fixed control menu: market cap, beta, value, momentum, volatility
Estimator Two-way fixed effects (TWFE), Callaway-Sant'Anna (2021) group-time ATT, Sun-Abraham (2021) interaction-weighted
Anticipation window 0, 1, 2, 3 months pre-treatment excluded
Tests Run Automatically:

Parallel trends pre-test: formal test of whether the pre-treatment trend in the outcome is the same for treated and control assets. Regress outcome on event-time dummies for each of the 12 months before treatment. F-test of joint significance of all pre-period dummies. Null: all pre-period event-time coefficients are jointly zero. Visual: event-study plot with pre-period coefficients + confidence bands.

Goodman-Bacon decomposition: when staggered timing is present, decomposes the TWFE estimate into all underlying 2×2 DiD comparisons with their weights. Identifies whether any comparisons receive negative weights (a signal of treatment effect heterogeneity contaminating the TWFE estimate).

Callaway-Sant'Anna estimation: group-time average treatment effects ATT(g,t) for each cohort g (assets first treated in period g) and time t. Aggregated into event-study style estimates by averaging across cohorts at each event-time. Robust to heterogeneous treatment effects across cohorts and time.

Placebo treatment: randomly assign false treatment dates to the control group. Re-run the DiD. Effect on placebo-treated controls should be zero. Distribution of 500 placebo estimates shown with real estimate marked.

Covariate balance table: mean of each control variable for treated vs control in the pre-period. Standardized mean difference for each variable. Values above 0.1 flagged as imbalanced.

Outputs:

Event-time coefficient plot (pre and post treatment, with 95% bands), TWFE regression table, Callaway-Sant'Anna group-time ATT table, Goodman-Bacon decomposition chart, parallel trends F-test result, placebo distribution chart, covariate balance table. All formatted as journal tables.

Framework 2 — Event Study with Abnormal Returns
What it tests: Whether a specific event produced statistically significant abnormal returns relative to a factor benchmark, and whether those returns were anticipated or followed by reversal.

Framework-Specific Inputs:

Parameter Options
Event dates User uploads CSV of (asset ticker, event date) pairs
Estimation window 120, 180, 250 trading days before the event window
Event window (-1,+1), (-3,+3), (-5,+5), (-10,+10), (-20,+20), user-defined
Benchmark model Market model, FF3, FF5, Dimson beta (for infrequently traded assets — uses lagged market return as additional regressor)
Abnormal return type Cumulative abnormal return (CAR), buy-and-hold abnormal return (BHAR)
Aggregation Equal-weighted, value-weighted
Contamination filter Exclude events within N days of another event for the same asset (N = 10, 20, 30)
Tests Run Automatically:

Standard cross-sectional t-test on mean CAR.

Patell (1976) standardized test: standardize each event's abnormal return by its estimation-window standard deviation before aggregating. More powerful than the raw t-test when residual variances differ across firms.

Boehmer-Musumeci-Poulsen (1991) test: accounts for event-induced variance increase. Events typically cause volatility to spike in the event window, inflating the variance of abnormal returns relative to the estimation window. BMP standardizes by the cross-sectional standard deviation of standardized returns rather than the estimation-window standard deviation, correctly accounting for this event-induced variance change.

Kolari-Pynnönen (2010) adjusted test: corrects for cross-sectional correlation of abnormal returns when events cluster in calendar time. When many assets experience the same type of event simultaneously, their abnormal returns are correlated. Standard tests assume independence and therefore overreject. The KP correction deflates the BMP test statistic by the factor √[(1 + (n-1)r̄) where r̄ is the average sample correlation of standardized abnormal returns across all event pairs in the same calendar month.

Calendar-time portfolio alpha: forms a monthly portfolio of all event assets in the post-event window. Regresses monthly portfolio return on FF5 factors. Intercept = long-run event alpha with correct time-series inference (avoids clustering problems entirely).

Pre-event drift test: tests whether abnormal returns in the (-20, -2) window are statistically significant. Significant pre-event drift means information leakage or momentum into the event date.

Post-event continuation/reversal test: tests whether abnormal returns in the (+2, +20) window are positive (continuation) or negative (reversal). Reversal is evidence of overreaction; continuation is evidence of underreaction or gradual information diffusion.

Outputs:

CAR event-time chart (-20 to +20) with 95% confidence bands. Distribution of individual CARs as a histogram (reveals whether the average is driven by a few extreme events). Cross-sectional t-test result. Patell test result. BMP test result. KP-adjusted test result. Calendar-time alpha with full factor loadings. All five test results in a single comparison table with plain-language verdict: which tests support significance, which do not, and what the disagreement implies.

Framework 3 — Regression Discontinuity
What it tests: Whether a threshold-based rule (index inclusion cutoff, rating boundary, regulatory size threshold) produces a causal discontinuity in outcomes at the cutoff — by comparing assets just above and just below the threshold.

Framework-Specific Inputs:

Parameter Options
Running variable Market cap (for index cutoffs), credit rating score, size rank, leverage ratio, any continuous characteristic available in platform data
Cutoff value User-specified (e.g., $5 billion market cap, rank 500, rating BBB-)
Design type Sharp RD (treatment deterministically assigned at cutoff), fuzzy RD (treatment probability jumps but not from 0 to 1 at cutoff)
Bandwidth Imbens-Kalyanaraman (IK) optimal data-driven bandwidth (default), manual override with user-specified half-bandwidth
Kernel Triangular (default — gives more weight to observations closer to the cutoff), uniform, Epanechnikov
Polynomial order Linear (local linear regression, default), quadratic, cubic
Outcome variable Any of the standard outcomes plus any platform module output
Tests Run Automatically:

Local linear regression at the cutoff: estimate separate linear regressions on each side of the cutoff within the chosen bandwidth. The estimated jump at the cutoff is the RD treatment effect.

Imbens-Kalyanaraman optimal bandwidth: data-driven procedure that minimizes the asymptotic mean squared error of the local linear RD estimator. Balances bias (wider bandwidth = more smoothing bias) against variance (narrower bandwidth = fewer observations = more variance). The IK bandwidth is the standard for credible RD implementation.

McCrary density test: tests whether the density of the running variable has a discontinuity at the cutoff. A density jump at the cutoff suggests manipulation — assets are sorting themselves just above (or just below) the cutoff to receive (or avoid) treatment, which would invalidate the RD identifying assumption. McCrary (2008) test statistic and p-value reported. Visual: density histogram of running variable with the estimated density on each side of the cutoff plotted as smooth curves.

Covariate continuity test: tests whether pre-determined characteristics (market cap, beta, volatility, value ratio) themselves have a discontinuity at the cutoff. If they do, the RD is picking up the effect of these characteristics, not the treatment. Runs the RD design with each covariate as the outcome variable. All covariate RD estimates should be near zero and statistically insignificant.

Placebo cutoff tests: moves the cutoff to 10 alternative values within the data (e.g., ±5%, ±10%, ±15%, ±20%, ±25% of the real cutoff). Estimates the RD at each fake cutoff. None should be significant — a finding only at the real cutoff confirms it is the threshold that matters, not a smooth trend.

Bandwidth sensitivity analysis: re-estimates the RD at 50%, 75%, 125%, 150%, and 200% of the IK optimal bandwidth. If the estimate changes dramatically with bandwidth, the result is sensitive to the local regression window choice — a sign of fragility. If it is stable across bandwidths, the finding is robust.

Donut hole test: excludes observations within a narrow band immediately around the cutoff (e.g., within 1% of the threshold) and re-estimates. This tests whether the result is driven by assets that are just barely complying — which might reflect sorting or strategic behavior — rather than by the full distribution of assets in the bandwidth.

Outputs:

RD plot: binned scatter plot of the outcome vs running variable, centered at the cutoff, with the local linear fit on each side. The estimated jump at the cutoff is the visual centerpiece of any RD paper. McCrary density plot. Placebo cutoff chart (RD estimates at fake cutoffs with confidence intervals — real cutoff should be the only significant one). Bandwidth sensitivity chart. Covariate continuity table. Full RD regression output with treatment effect, SE, confidence interval. All formatted as journal figures and tables.

Framework 4 — Instrumental Variables
What it tests: When a signal or treatment variable is endogenous (correlated with the regression error), OLS is biased. An instrument that affects the signal but not the outcome except through the signal allows consistent estimation of the causal effect.

Framework-Specific Inputs:

Parameter Options
Endogenous variable Any signal or characteristic from the platform data
Instrument User-defined (CSV of instrument values per asset per period); platform-provided instruments: lagged values (1M, 3M, 6M lag), geographic average of signal among peer assets, industry mean excluding the asset itself
Outcome variable Standard outcomes menu
Controls Fixed controls menu
Estimator 2SLS (two-stage least squares), LIML (limited information maximum likelihood — less biased when instruments are weak)
Additional endogenous regressors Up to 3 additional endogenous variables with corresponding instruments
Tests Run Automatically:

First-stage regression: regress the endogenous variable on the instrument(s) and controls. Reports R², F-statistic, and coefficient on each instrument with its t-statistic. The first stage is the empirical proof that the instrument is relevant.

Staiger-Stock weak instrument test: the first-stage F-statistic is the standard test of instrument strength. Staiger and Stock (1997) original rule: F > 10. Modern robust threshold (Lee et al., 2022): F > 104 for 2SLS to have less than 5% size distortion. The platform reports both thresholds, flags which is met, and explicitly warns if neither is met (instruments are weak — results unreliable).

Anderson-Rubin confidence set: a test and confidence interval that remains valid even when instruments are weak. Unlike the standard 2SLS t-test which becomes unreliable with weak instruments, the AR confidence set has correct coverage regardless of instrument strength. It inverts the test of H₀: β = β₀ for each candidate value of β, forming the confidence set of all β₀ values not rejected at the 5% level. When instruments are strong the AR interval is approximately the same as the standard 2SLS interval. When instruments are weak the AR interval may be wider or even unbounded — which is the honest answer.

Sargan-Hansen overidentification test: when there are more instruments than endogenous variables (overidentified), tests whether all instruments are valid (not correlated with the error). If the test rejects, at least one instrument is invalid. Not computable in the just-identified case (one instrument per endogenous variable).

Hausman endogeneity test: tests whether the endogenous variable is actually endogenous (whether OLS and 2SLS differ significantly). If not significant: OLS is consistent and more efficient; IV is unnecessary. This is the test that determines whether IV is required at all.

Wu-Hausman F-test: the F-test version of the Hausman test, more reliable in small samples.

Outputs:

First-stage regression table with F-statistic, Staiger-Stock thresholds flagged. 2SLS second-stage regression table with treatment effect, SE, confidence interval. OLS result in adjacent column for comparison. Anderson-Rubin confidence set (with explicit statement if it is unbounded, indicating weak instruments). Sargan-Hansen test result (if overidentified). Hausman test result with verdict: IV required or OLS sufficient. Plain-language instrument validity assessment: is the instrument strong? Is it likely valid? Are the results credible? All formatted as journal tables.

Data Map (Feature 7)
Series Source Code Used In
Daily and monthly OHLCV Yahoo Finance / Stooq Per ticker All frameworks
Fama-French factors Ken French data library FF5, MOM Abnormal return computation
Market cap, beta, value, momentum, volatility Platform internal computation — Controls, matching, covariates
VIX FRED VIXCLS Regime conditioning in DiD
NBER recession dates FRED USREC Timing reference
Credit spreads FRED BAMLC0A0CM Control variable
FEATURE 8 — THE SIGNAL DECAY AND ARBITRAGE CLOCK
Design Philosophy
Every researcher who documents a return anomaly or factor faces the same question from practitioners and reviewers alike: is this still working, or has it been arbitraged away? McLean and Pontiff (2016) showed that anomaly returns decay by approximately 50% after academic publication, because publication attracts arbitrage capital. Falck, Rej, and Thesmar (2021) showed that every additional year of publication increases Sharpe decay by 5 percentage points. This is now one of the most cited empirical facts in asset pricing. Yet no platform provides a structured, live, formally tested tool that answers the decay question for any signal. This feature is that tool. It is the most emotionally powerful feature in the module for both academics and practitioners: academics want to know if their anomaly is still publishable; practitioners want to know if a strategy they are running is dying. The same engine answers both questions.

What It Does
Takes any signal — from the platform's factor module, volatility module, or user-defined — along with a discovery or publication date, and runs a complete decay analysis: formal pre/post comparison, exponential decay curve fitting with half-life extraction, structural break detection for the arbitrage arrival date, signal vitality score, and a decomposition of whether decay is driven by arbitrage or data mining. The output is a complete, publication-grade decay analysis that takes researchers weeks to produce manually.

Custom Inputs
Parameter Options
Signal Any factor signal from Factor module (value, momentum, quality, low-vol, size, profitability, investment), any vol signal from Volatility module, user-defined signal (CSV of asset, date, signal value)
Discovery date User-specified month and year (the date the anomaly was first documented — not the publication date, which is typically later)
Publication date User-specified (separate from discovery date — allows testing discovery vs publication decay separately)
Performance metric IC (information coefficient — Spearman rank correlation between signal and forward return), long-short Sharpe ratio, long-short mean return, Fama-MacBeth lambda
Evaluation horizon 1-month forward return, 3-month, 6-month, 12-month
Rolling window for IC computation 12-month, 24-month, 36-month rolling window
Decay model Exponential, linear, hyperbolic — or all three simultaneously with model comparison
Bootstrap replications for half-life CI 500, 1000
Asset universe Broad market, large cap only, ex-financials — consistent with the original anomaly's universe
Time period 2010 to present (full available history)
Tests Run Automatically
McLean-Pontiff Pre/Post Comparison

Split the full sample at the discovery date into two subsamples: in-sample (before discovery) and out-of-sample (after discovery).

For each subsample compute the mean monthly IC and its standard error. Test whether IC_OOS < IC_IS using a one-sided t-test:

t = (IC_IS − IC_OOS) / √(SE²_IS + SE²_OOS)

Report: IS mean IC, OOS mean IC, the ratio OOS/IS (the "survival fraction"), and the t-statistic and p-value of the decay test. A survival fraction below 0.5 means more than half of the predictive power is gone — consistent with McLean-Pontiff's median finding. A survival fraction above 0.7 means the anomaly is largely intact.

Separately test post-discovery vs post-publication to measure the effect of publication itself (publication attracts more arbitrage than discovery alone because of broader dissemination).

Exponential Decay Curve Fitting

Model the rolling IC over time as an exponential decay:

IC(t) = a × exp(−b × (t − t_discovery)) + c

where a is the initial IC level, b is the decay rate, c is the long-run floor, and t_discovery is the discovery date.

Non-linear least squares: minimize Σ_t (IC_rolling(t) − IC_model(t))² over parameters (a, b, c).

Half-life extraction: H\* = ln(2) / b — the number of months for the IC to fall to halfway between its initial value and its long-run floor.

Bootstrap 90% confidence interval on H*: draw 1000 bootstrap samples of the rolling IC time series (block bootstrap, block length = 12 months to preserve autocorrelation). Re-fit the exponential model on each sample. The 5th and 95th percentiles of the bootstrap distribution of H* form the CI.

Compare with linear decay: IC(t) = a − b × (t − t_discovery) and hyperbolic decay: IC(t) = a / (1 + b × (t − t_discovery)). AIC and BIC for all three models. The best-fitting model determines whether the decay is fast (exponential) or slow (hyperbolic — consistent with limits-to-arbitrage where some residual mispricing persists).

Structural Break Detection — Arbitrage Arrival Date

Run the Andrews (1993) supremum test on the rolling IC time series to identify the most likely structural break date — the date at which the IC most sharply declined.

F*Andrews(τ) = [(RSS_pooled − RSS*{pre}(τ) − RSS*{post}(τ)) / k] / [(RSS*{pre}(τ) + RSS\_{post}(τ)) / (T − 2k)]

Scan τ over the central 70% of the post-discovery period (avoid the tails). The τ\* that maximizes F_Andrews is the estimated "arbitrage arrival date" — when smart money started trading against the anomaly aggressively enough to break its statistical properties.

Report: τ* (the estimated arbitrage arrival date), 90% confidence interval around τ*, the F-statistic and its p-value relative to Andrews critical values, and the IC in the pre-break vs post-break subperiod.

This is the most novel output of this feature. Nobody else has formalized the arbitrage arrival date concept as a detectable structural break with a confidence interval. It directly answers: when, specifically, did this anomaly start dying?

Signal Vitality Score

Compute the signal's recent performance relative to its in-sample performance:

Vitality_t = IC_rolling,t / IC_IS_mean × 100

where IC_rolling,t is the rolling 12-month IC ending at the most recent date and IC_IS_mean is the average IC in the in-sample period.

Vitality = 100: signal is performing exactly as strongly as it did in-sample. Full vitality.
Vitality = 50: signal is at half its original strength. Partially arbitraged.
Vitality = 0: signal has no predictive power. Fully arbitraged.
Vitality < 0: signal has reversed — trading it now would lose money.

Display as a gauge: green > 70, amber 30-70, red < 30, deep red < 0.

Arbitrage vs Data-Mining Decomposition

Following Falck, Rej, and Thesmar (2021), test two competing hypotheses for decay:

Arbitrage hypothesis: decay is faster for signals with lower transaction costs (more liquid stocks), lower idiosyncratic volatility (easier to arbitrage), and shorter holding periods (faster capital deployment). Test by running a cross-sectional regression of the signal's OOS/IS IC ratio on these characteristics across multiple signals if the user activates the cross-signal comparison mode.

Data-mining hypothesis: decay is faster for signals that are more complex (more operations to compute), were published later (more competition from prior anomaly hunters), and have IC that is more sensitive to outlier observations (fragile signals). These decay faster because they were never real — they were in-sample artifacts.

For a single signal: the decomposition estimates how much of the observed OOS decline is consistent with each hypothesis. An anomaly that decays faster in low-cost, high-liquidity assets is more consistent with arbitrage. An anomaly that decays by the same amount regardless of arbitrage cost is more consistent with data mining.

Report: arbitrage-consistent fraction of decay, data-mining-consistent fraction of decay, plain-language interpretation.

International Replication Test

Re-run the same signal test on 3-5 international markets simultaneously (US, Europe (STOXX50 constituents), Japan (Nikkei 225 constituents), UK (FTSE 350 constituents), emerging markets proxy). A genuine anomaly tends to exist across markets. A data-mined US-specific artifact tends not to replicate internationally.

For each market: IS IC, OOS IC, survival fraction, vitality score. Cross-market consistency score: fraction of markets where the signal is still statistically significant (IC t-statistic > 2) in the post-discovery period.

Long-Short Sharpe Decay Curve

In addition to the IC-based analysis, compute the long-short portfolio Sharpe ratio in rolling 12-month windows from the earliest available date through the present. Plot as a time series. The Sharpe should be highest in the in-sample period, decline after discovery/publication, and stabilize at a lower level (if arbitrage) or near zero (if data mining).

Superimpose: the discovery date, the publication date, and the Andrews structural break date (arbitrage arrival date) as vertical dashed lines. These three dates segment the Sharpe time series into four periods: pre-discovery, discovery-to-publication, publication-to-arbitrage, post-arbitrage. The Sharpe in each period tells the complete life cycle story of the anomaly.

Outputs
Output Description
Vitality gauge Large circular dial showing current signal vitality score 0-100+. Green, amber, red, deep red zones. The first thing a researcher sees when the analysis finishes
McLean-Pontiff comparison table IS IC, OOS IC, OOS/IS ratio, t-statistic of decay, p-value. Separate rows for post-discovery and post-publication
Decay curve chart Rolling IC time series with fitted exponential/linear/hyperbolic curves overlaid. Discovery and publication dates as vertical lines. Long-run floor as horizontal dashed line. Half-life annotated
Half-life output Point estimate and 90% bootstrap CI. "The signal's predictive power has a half-life of X months (90% CI: Y to Z months)"
Decay model comparison table AIC, BIC, R² for exponential vs linear vs hyperbolic. Winning model bolded
Andrews structural break chart F_Andrews(τ) over all candidate break dates. Peak is the arbitrage arrival date with 90% CI annotated
Long-short Sharpe decay chart Rolling 12-month Sharpe over full history with discovery, publication, and arbitrage arrival dates marked. Four-period segmentation with mean Sharpe per period
Arbitrage vs data-mining decomposition Two-row summary: fraction of decay consistent with arbitrage, fraction consistent with data mining. Plain-language interpretation
International replication panel Table of IS IC, OOS IC, survival fraction, vitality score for each market. Cross-market consistency score at bottom
Anomaly life cycle summary A plain-language paragraph auto-generated from the statistical outputs: "This signal was discovered in [date] with an in-sample IC of [X]. Since publication, predictive power has declined by [Y]%, with an estimated half-life of [Z] months. The arbitrage arrival date is estimated at [month], [year]. Current vitality is [score] — [interpretation]." This is the only auto-generated text in the entire module
Data Map
Series Source Code Used In
Daily and monthly OHLCV (US) Yahoo Finance / Stooq Per ticker All computations
Daily and monthly OHLCV (International) Yahoo Finance / Stooq ^STOXX50E, ^N225, ^FTSE, per EM ticker International replication
Factor signals from Factor module Internal — Pre-built signal mode
Volatility signals from Volatility module Internal — Pre-built signal mode
Fama-French factors Ken French data library FF5, MOM Alpha computation, long-short portfolio
Risk-free rate FRED DGS3MO Sharpe ratio computation

FEATURE 9 — THE SYNTHETIC CONTROL ENGINE
What You Are Building
The canonical single-unit causal inference tool that fills the Research Module's causal gap. Every serious asset pricing or event-study question with one treated unit — a single stock added to an index, a single country hit by a policy shock, a single regulatory event — is best answered with Synthetic Control rather than a standard DiD or placebo. SCM constructs a counterfactual from a weighted donor pool, with pre-treatment fit itself serving as the credibility test.

Custom Inputs
Parameter Options
Treated unit Single ticker, single sector index, single country ETF (as country proxy)
Donor pool All untreated assets in universe / user-restricted candidate list / same-sector only / same-market-cap-decile only
Treatment date User-specified
Pre-treatment window Minimum 24 months enforced
Predictor variables Pre-treatment outcome values at multiple lags / additional covariates (market cap, beta, sector, book-to-market)
SCM variant Classic SCM (convex weights summing to 1) / Augmented SC (ridge bias correction) / Generalized SC (interactive fixed effects) / Robust SC (matrix completion denoising)
Weight constraint Convex (weights ≥ 0, sum to 1) / unconstrained (augmented only)
Inference method Placebo-in-space / placebo-in-time / conformal inference
Multiple treated units Off / staggered adoption mode

Tests Run Automatically
Pre-treatment fit diagnostic RMSPE of the synthetic control in the pre-period. If pre-fit is weak, the platform flags the result as unreliable.
Post/pre RMSPE ratio The primary inferential statistic in SCM.
Placebo distribution (in-space) Re-run SCM on every donor as if it were treated. Rank the real unit's post/pre RMSPE ratio among placebos.
Donor weight concentration Reports whether the synthetic control is dominated by 2-3 donors or distributed across many.
Leave-one-out donor sensitivity Refit SCM excluding each nonzero-weight donor. Flag fragile results where the estimated effect swings materially.
In-time placebo test Refit SCM with a fake treatment date in the pre-period. A real effect should not appear at the fake date.
Conformal inference intervals Construct valid confidence bands on the treatment effect path without relying solely on placebo exchangeability.

Outputs
Output Description
Treated vs. synthetic path chart Treated unit and synthetic control plotted across the full window, with treatment date marked and the post-treatment gap shaded
Gap plot Post-minus-pre treatment gap time series with zero line and treatment date marker
Placebo distribution chart All placebo gap paths in gray, real unit in bold red
Donor weight table Donors with nonzero weight sorted descending, including their pre-treatment characteristics
RMSPE ratio ranking Bar chart of post/pre RMSPE ratios across placebos, with treated unit highlighted and p-value shown
Leave-one-out sensitivity band Treatment effect range across all leave-one-out refits
Conformal confidence band Treatment effect path with conformal prediction interval overlay
Staggered adoption event-study plot When multiple treated units are active: pooled event-time treatment effect with confidence bands
LaTeX export Formatted table of treatment effect, RMSPE ratio, placebo p-value, donor weights

Data Map
Series Source Used In
Daily and monthly OHLCV Yahoo Finance / Stooq Per ticker SCM outcome and predictor series
Fama-French factors Ken French data library FF5, MOM Covariate adjustment and benchmark outcomes
Pre-built signal series from Factor module Internal Counterfactual predictors
Risk-free rate FRED DGS3MO Sharpe calculation on event windows

FEATURE 11 — THE CROSS-SECTIONAL DEPENDENCE AND FACTOR ZOO POSITIONING ENGINE
Design Philosophy
A new signal is only interesting if it is not already explained by the factor zoo. This feature benchmarks any tested signal against a maintained library of existing factors, applies a literature-adjusted significance bar, and shows where the signal sits in the broader cross-sectional dependence structure.

Custom Inputs
Parameter Options
Candidate signal Any Feature 1 output or user-uploaded signal
Benchmark factor library FF5+MOM / extended library (quality, low-vol, BAB, short-term reversal) / user-uploaded factor returns
Significance threshold t > 2.0 / t > 3.0 / custom
Spanning test set Full extended library / user-selected subset

Tests Run Automatically
Extended spanning test Regress the signal's long-short return on the larger benchmark library rather than just FF5+MOM.
Harvey-Liu-Zhu multiple-testing-adjusted t-statistic Recompute the effective credibility threshold given the current factor literature size.
Factor correlation map Show whether the signal is near-duplicate, genuinely new, or a blend of existing factors.

Outputs
Output Description
Zoo positioning chart Scatter of the new signal's IC-IR against benchmark factors' IC-IR.
Harvey-Liu-Zhu adjusted significance card Plain statement of required t, observed t, and verdict.
Correlation with existing factors Table of correlations with benchmark factors, flagging near-duplicates (ρ > 0.7).

Data Map
Same as Feature 1 plus extended factor library built from OHLCV and internal signals.

MODULE ARCHITECTURE
Feature Entry Requirement Primary Input Standalone

1. Canonical Test Engine None Platform data + signal selection Yes — primary entry point
2. Robustness Engine None Feature 1 result OR manual input Yes — accepts external results
3. Placebo Suite None Feature 1 result OR manual input Yes — accepts external results
4. Regime Conditional None Feature 1 result OR manual input Yes — accepts external results
5. Diagnostic Center None Regression residuals from F1 or uploaded Yes — pure statistical tests
6. Specification Builder None Same menus as Feature 1 Yes — independent table builder
7. Causal Identification None Platform data, user-defined events/instruments Yes — completely independent
8. Signal Decay and Arbitrage Clock None Signal selection + discovery date Yes — completely independent
9. Synthetic Control Engine None Treated unit + donor pool + outcome series Yes — single-unit causal inference for event studies
11. Factor Zoo Positioning Engine None Candidate signal + benchmark factor library Yes — cross-sectional dependence and literature-adjusted credibility
   No feature requires any other feature to run first. Feature 1 is the natural starting point for most users, and Features 2, 3, 4, 5, 6 can auto-populate from Feature 1 results. But every feature accepts manual input and is fully usable as a standalone tool by researchers who bring their own results from R, Stata, or Python.

MASTER DATA MANIFEST
Series Source FRED Code / Ticker Used In
US equity daily OHLCV Yahoo Finance / Stooq Per ticker All features
US equity monthly returns Yahoo Finance (computed) Per ticker All features
Fama-French 3-factor Ken French library FF3 Features 1, 6, 7, 8
Fama-French 5-factor Ken French library FF5 Features 1, 6, 7, 8
Momentum factor Ken French library UMD Features 1, 6, 7, 8
VIX daily level FRED VIXCLS Features 4, 7
2Y and 10Y Treasury yields FRED DGS2, DGS10 Feature 4
IG credit spread FRED BAMLC0A0CM Features 4, 7
NBER recession indicator FRED USREC Features 4, 7
3-month T-bill rate (risk-free) FRED DGS3MO Features 1, 8
International equity OHLCV Yahoo Finance ^STOXX50E, ^N225, ^FTSE Feature 8
Factor signals from Factor module Internal — Features 1, 8
Volatility signals from Volatility module Internal — Features 1, 8
Regime probabilities from Volatility module Internal — Feature 4

Close
