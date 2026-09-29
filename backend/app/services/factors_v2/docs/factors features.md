

# QUANT360 — Factor Intelligence Module: Complete Money-Bagger Feature Spec
## Post-Research, Post-Audit, Fully Rebuilt

**Design philosophy extracted from research:** In 2026, allocators and quant PMs want three things above everything else: (1) crowding transparency they can show their LPs, (2) a capacity map per strategy, and (3) live proof a signal is still working. Every feature below is pressure-tested against what institutions actually pay five-to-six figures per year for. Three features from the original spec have been cut and replaced with features that are demonstrably more monetizable. The full logic for each cut is stated.

## REALTIME CONSTRAINTS, DROPPED DEFAULTS, AND RESEARCH MODE

This section is now binding for Factors V2 implementation. The feature descriptions below remain the complete institutional target, but the production backend/UI must distinguish between:

- **Realtime default:** synchronous analysis suitable for the interactive Labs page.
- **Research Mode:** explicit `compute_mode="research"` payload setting for expensive diagnostics, cached/nightly outputs, or async exports.
- **Dropped live default:** functionality removed from the normal run path because it creates unacceptable latency or misleading UX at full-universe scale.

| Feature | Dropped or constrained from realtime default | Realtime default | Research Mode / cached path |
|---|---|---|---|
| F02 Portfolio X-Ray | Full 5000-stock characteristic z-score recomputation and animated rolling exposure heatmap are not live defaults. | Characteristic exposure computes only for portfolio constituents or a capped local sample; static exposure bar, static heatmap, and static time series remain. | Full-universe z-scores are nightly cached; animated rolling heatmap is on-demand export only. |
| F03 Attribution | Daily granularity over histories above 5 years is not a realtime computation. | Full history defaults to monthly; daily attribution is capped to trailing 12 months. | Full daily history is Research Mode/async. |
| F04 Regime | GMM on rolling 63-day factor covariance matrices is not a realtime default. | HMM is primary probabilistic method; macro/rules model is secondary; composite uses log-space probability averaging. | GMM is toggle/cached weekly or Research Mode. |
| F05 Alpha Decay | Cross-sector decay comparison across all GICS sectors is not a realtime default. | Full-universe decay, IC/ICIR, half-life, confidence intervals, and rebalancing curve. | Sector decay is selected-sector drill-down. |
| F06 Crowding | Bid-ask spread trend and alternative-data proxies are not included in the realtime composite. | Composite uses three metrics only: valuation spread, return autocorrelation, and HHI concentration. | Bid-ask trend is an explicit toggle; live external fetching is not performed inside local-only compute. |
| F07 Backtest | Daily walk-forward ML refit, >250 Monte Carlo bands, and timing-cost implementation shortfall are not realtime defaults. | Weekly refit, 250 Monte Carlo cap, explicit + linear spread + Kyle-style square-root impact. | Daily refit, 500 Monte Carlo cap, and timing cost require Research Mode/toggle. |
| F08 Covariance | DCC-GARCH is not realtime default for factor sets above 15 factors. | Ledoit-Wolf default above 15 factors; sample/EWMA/Ledoit-Wolf available; finite/symmetric validation is mandatory. | DCC-GARCH for larger sets requires Research Mode. |
| F09 Capacity | Dense AUM sweeps above 20 points are not realtime defaults. | 20 log-spaced AUM points from $1M to $10B. | 50 points in Research Mode. |
| F10 Optimizer | Integer programming cardinality constraints are removed as a live optimization option; full Goldfarb-Iyengar robust solve is not realtime default for N > 100. | Continuous relaxation plus greedy cardinality post-processing; N > 100 robust mode uses expected-return shrinkage approximation. | Full robust optimization available in Research Mode where feasible. |
| F11 Stress Testing | VAR with 21-day lags and 500 bootstrap reps is not realtime default. | VAR capped at 5 lags with 200 bootstrap replications and 90% bands. | 21 lags and 500 reps require Research Mode. |
| F13 Signal Monitor | Chow structural break test at every date in trailing 252-day window is not realtime. | Single rolling CUSUM test per factor per run; alert cooldown and resolution metadata included. | Chow diagnostic is weekly cached. |
| F14 Report Generator | PDF rendering above 20 pages is not realtime default. | JSON/HTML/reportlab PDF up to 20 pages. | Longer reports are Research Mode/async exports. |

UI implementation note: despite `factors design.md` specifying a 12-column workstation grid, Factors V2 uses the PortfolioVisualizer-style sequential flow requested for Labs: full input form first, single Run Analysis action, then stacked output cards with a sticky output navigation and compact analysis context. The token system, chart styling, panel anatomy, table density, and four-second legibility test from `factors design.md` still apply.

F02 rolling exposure time series as a historical output, replace with static snapshot clearly labeled
F06 bid-ask spread trend input field
F06 institutional ownership and short interest proxy rows from crowding metrics table
F12 sector DNA time series animation, replace with static snapshot
F12 correlation DNA rolling grid, replace with latest single-date factor correlation bar chart
F14 embedded chart images from PDF scope
F14 external notification delivery claims



## FEATURE 1: Factor Valuation Spread Monitor (The "Factor PE Ratio")

**What it is and why it is a money-bagger:** This is the single feature most practitioners report checking every morning and cannot find cleanly anywhere. Bloomberg gives you the raw data, but you have to build the computation yourself. Portfolio Visualizer does not compute it at all. The question is: right now, today, is Value expensive or cheap relative to its own history? Is Momentum stretched? Is Quality overcrowded by valuation? This is the "factor PE ratio" concept and it is the bridge between historical analytics and live decision-making. Every meeting with an allocator or CIO starts here.

**Conceptual engine:** For each factor, define the long book (top quintile) and short book (bottom quintile) of your ticker universe. Compute the spread in underlying fundamental characteristics (Price-to-Book spread for Value, EV/EBITDA spread, trailing 12-month price return spread for Momentum, ROE spread for Quality). Express this spread as a historical percentile versus the prior 10 years of daily history.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Factor Selector | Value (P/B, EV/EBITDA, E/P), Momentum (trailing 12M, trailing 6M skip-1, trailing 3M), Quality (ROE, gross profitability, accruals), Low-Vol (realized vol spread, beta spread), Size (market cap spread), Growth (LTM revenue growth spread), Investment (asset growth spread), Profitability (operating margin spread), any user-defined custom factor from ticker universe |
| Percentile Lookback Window | 3-year / 5-year / 10-year / custom |
| Universe Filter | Full ticker universe / by GICS sector |
| Characteristic to Measure Spread | Choose any fundamental metric or composite |
| Historical Comparison Anchors | Auto-flag to GFC 2008, COVID Mar 2020, rate shock Oct 2022, Liberation Day Apr 2025 percentile levels |
| Display Mode | Current snapshot / time series of percentile / all factors simultaneously (dashboard view) |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Live Factor Valuation Gauge Panel | For every factor, a dial showing current percentile from 0 (historically cheapest) to 100 (historically most stretched). Color-coded: green < 30th, amber 30th-70th, red > 70th. |
| Historical Percentile Time Series | 10-year evolution of the factor's valuation spread, shown as a band chart with the current level marked. |
| Expected Return Implied by Spread | Regression-implied 12-month expected return based on today's spread percentile, shown with 90% confidence interval. |
| Factor Valuation Correlation Matrix | Heatmap showing which factors are simultaneously stretched (e.g., Value cheap + Momentum stretched). |
| Alert System | Flags when any factor crosses user-defined threshold percentiles with email or dashboard notification. |
| Cross-Sector Valuation Spread Table | Table showing which GICS sectors contribute most to the current factor spread. |
| Factor Valuation History Table | Current percentile alongside the percentile level at every major crisis start date for reference. |

---

## FEATURE 2: Factor Exposure Decomposition (Portfolio X-Ray)

**What it is and why it is a money-bagger:** This is the most universally demanded feature in institutional quant finance. Barra charges approximately $50,000 per year for exactly this. Every allocator DDQ now explicitly requires monthly factor attribution showing beta, value, momentum, quality, low-vol, sector, and country. As of 2026, funds that cannot show clean factor attribution to their LPs are losing allocations. The research from Resonanz Capital is unambiguous: "Show factor attribution monthly. Don't accept 'it's neutral.'"

**Conceptual engine:** Two simultaneous exposure methodologies run in parallel and their divergence is reported. Method 1 is characteristic-based (forward-looking): for each stock in the portfolio, compute its z-scored fundamental characteristics relative to the universe (P/B percentile = Value loading, 12M return percentile = Momentum loading, ROE percentile = Quality loading). Method 2 is return-based (backward-looking): run a time-series OLS regression of each stock's daily returns on contemporaneous factor returns over the estimation window. Portfolio-level exposures are the value-weighted aggregate of constituent exposures. Active exposures are computed relative to a chosen benchmark. When the two methods diverge for a given stock, that divergence is itself flagged as an "exposure surprise" signal, since a stock whose characteristics say it is cheap but whose returns behave like momentum is a genuine anomaly.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Portfolio Input Method | Manual ticker + weight entry, CSV or JSON upload, equal-weight toggle, long-only vs. long-short flag, multiple portfolio upload for comparison |
| Factor Model | FF3 / FF5 / Carhart / extended (adds BAB, QMJ, Liquidity, Idiosyncratic Volatility) / fully custom |
| Benchmark | S&P 500 / Russell 1000 / Russell 2000 / MSCI World / custom ticker list / no benchmark |
| Exposure Methodology | Characteristic-based / return-based / both simultaneously (shows divergence) |
| Exposure Type | Raw factor loading / active (relative to benchmark) / standardized z-score relative to cross-section |
| Estimation Window | 6 / 12 / 24 / 36 / 60 months custom (for return-based method) |
| Rebalancing Date | Point-in-time snapshot / rolling monthly (shows exposure evolution over entire history) |
| Neutralization Level | Raw exposures / sector-neutral |
| Comparison Mode | Up to three portfolios side by side |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Factor Exposure Bar Chart | Portfolio factor loadings with 95% confidence band from bootstrapped estimation uncertainty. |
| Active Exposure Chart | Portfolio exposure minus benchmark exposure, revealing actual active bets vs. stated mandate. |
| Characteristic vs. Return Divergence | Simultaneous display of both estimates; flags stocks where divergence exceeds 0.3 standard deviations. |
| Holdings-Level Factor Contribution | positions ranked by their contribution to each factor loading (e.g., top 5 stocks driving Value tilt). |
| Exposure Heatmap | Stocks (rows) by factors (columns) showing individual characteristic z-scores. |
| Unintended Exposure Detector | Flags factors where |active exposure| > 0.4 sigma that were not in the stated investment mandate. |
| Tilt Plain-Language Summary | Automated narrative summary of portfolio tilts and unintended exposures. |
| Rolling Exposure Time Series | Month-by-month evolution of portfolio factor loadings over history. |
| Factor Exposure Budget | Percentage of tracking error coming from factor tilts vs. specific selection. |
| Exposure Surprise Signal Table | Stocks where characteristic-implied and return-implied exposures diverge most. |

---

## FEATURE 3: Factor Return Attribution and Performance Decomposition

**What it is and why it is a money-bagger:** Bloomberg's PORT Enterprise charges per seat for this. It answers the one question every PM faces every Monday morning: "Where did my returns actually come from?" Brinson-Hood-Beebower decomposition, factor-based attribution, and the interaction effect are the three components that separate systematic from speculative performance. The 2026 allocator DDQ standard explicitly requires this at monthly frequency.

**Conceptual engine:** Full Brinson-Fachler framework (the corrected Brinson, which adjusts for benchmark sector weights, not the simpler BHB) crossed with factor-based attribution. Total active return = allocation effect (did you over/underweight the right factors?) + selection effect (did you pick the right stocks within each factor quintile?) + interaction effect (was the timing of your factor bets value-additive?). Each component is computed daily and aggregated. The carryover effect is separately computed: for each holding, what fraction of this period's P&L was determined by a decision made in a prior rebalancing period versus the current active decision.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Portfolio History | Upload snapshots at each rebalancing date (system interpolates holdings between dates) |
| Attribution Period | Any date range from 10-year history |
| Attribution Model | Pure factor-based (Barra-style) / Brinson-Fachler sector-based / hybrid / choose per panel |
| Factor Model | FF3 / FF5 / Carhart / custom |
| Frequency | Daily / weekly / monthly / quarterly cumulative |
| Benchmark | For active return decomposition |
| Transaction Cost Model | Flat bps or size-dependent price impact (user-specified Kyle lambda coefficient) |
| Carryover Effect Toggle | Show return stemming from prior vs. current period active decisions |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Attribution Waterfall Chart | Total return broken into Market + Factor Contribution + Selection + Interaction + Carryover. |
| Cumulative Contribution Area | Stacked area chart showing dominance of return components over time. |
| Factor Return Contribution Table | Exposure x factor return = contribution, with t-stats for statistical significance. |
| Information Ratio by Component | IR for selection vs. factor component to distinguish stock-picking skill from factor harvesting. |
| Brinson-Fachler Table | Allocation, selection, and interaction effects decomposed by GICS sector. |
| Carryover Effect Report | P&L fraction from prior vs. current decisions with "decision freshness score". |
| Factor Hit Rate Table | Percentage of periods where portfolio earned positive contribution from factor exposure. |
| Attribution Outliers | Identifies best/worst 5 periods and their dominant drivers. |
| Rolling Information Ratio | 12m and 36m rolling IR for factor and selection components. |
| Active Return Waterfall vs Benchmark | Decomposition of outperformance vs. benchmark with statistical significance. |

---

## FEATURE 4: Factor Timing and Probabilistic Regime Analysis

**What it is and why it is a money-bagger:** MSCI charges separately for regime-conditional factor analytics. The 2025 quant unwind confirmed empirically that crowded factor trades fail at regime transitions, and the 2026 Resonanz Capital research explicitly identifies regime change as one of the two primary failure modes for quant strategies. The critical upgrade here over the original spec is probabilistic regime output: instead of labeling each date as "regime 1" or "regime 2" like a binary switch, the system outputs a probability vector at every date. This is what actually-used quant fund infrastructure computes.

**Conceptual engine:** Three parallel regime detection methods are run simultaneously and their outputs are averaged into a composite regime probability. Method 1: rules-based macro regime using VIX threshold + yield curve slope (2s10s) + real interest rate level. Method 2: Hidden Markov Model with two to four states fitted directly to rolling factor return vectors (not to macro variables), so the regimes are defined by how factors actually behave, not by how economists classify the economy. Method 3: Gaussian Mixture Model on rolling 63-day factor return covariance matrices, clustering them into states representing "normal," "risk-off synchronized," "factor dispersion," and "liquidity crisis." At every date, each model outputs a probability distribution over states. The composite is a weighted average of the three model outputs, with weights determined by each model's recent predictive accuracy.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Regime Model | Rules-based only / HMM only / GMM only / Composite (weighted by recent accuracy) |
| HMM States | 2 / 3 / 4 (Expansion, Recession, Transition, Liquidity Crisis) |
| VIX Threshold | User-set (default 25) for rules-based stress regime |
| Yield Curve Metric | 2s10s slope / 3M10Y slope / user-defined |
| Factor Scope | Any subset from full library for regime-conditional return analysis |
| Factor Timing Model | Signals: valuation spread, factor momentum, crowding score, macro composite |
| Factor Momentum Params | Ranking period (1/3/6/12m), Holding period (1/3/6/12m), L-O vs L-S |
| Statistical Significance | Hypothesis test toggle for regime-conditional differences |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Probabilistic Regime Timeline | Stacked probability chart showing probability of each state (Expansion, Stress, etc.) at each date. |
| Live Regime Probability Readout | Current probability vector across states with 30d and 90d trend. |
| Factor Return Heatmap by Regime | Average monthly return per factor conditional on regime state with t-stats. |
| Factor Sharpe by Regime | Annualized Sharpe ratio per factor per regime. |
| Factor Momentum Backtest | Cumulative return of factor-momentum strategy vs. equal-weighted portfolio. |
| Regime Transition Matrix | Empirical probabilities of switching states over 1, 3, and 6 months. |
| Timing Regression Output | Coefficient, t-stat, R-squared, and current timing score per factor/signal pair. |
| Factor Seasonality Chart | Average return by calendar month for each factor. |
| Portfolio Regime Sensitivity | Expected portfolio return in each regime state based on current exposures. |

---

## FEATURE 5: Alpha Decay and Factor Half-Life Analysis

**What it is and why it is a money-bagger:** This is genuinely frontier research that has been productized by nobody. The December 2024 arxiv paper confirmed that hyperbolic decay fits better than exponential (R-squared of 0.65 vs. 0.61 for Momentum) and that crowding accelerated post-2015 beyond what historical models predicted, with factor ETF volume growth correlating at -0.63 with remaining alpha. This is now a demonstrably critical input for any fund deciding rebalancing frequency, and no commercial platform shows it.

**Conceptual engine:** Rank all 5,000 stocks by each factor at time T. Compute realized portfolio returns at T+1, T+5, T+21, T+63, T+126, and T+252 trading days. Compute the rank IC (Spearman correlation between factor rank and forward return rank) at each horizon. This traces the decay curve. Fit three functional forms: linear IC(h) = a - b*h, exponential IC(h) = a*exp(-b*h), and hyperbolic IC(h) = a / (1 + b*h). Compare R-squared for all three. Extract the half-life parameter: for the winning functional form, solve for the horizon h* at which IC(h*) = 0.5 * IC(1). Run the full analysis on rolling 252-day sub-windows to get a time series of half-life estimates showing whether decay has accelerated.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Factor Selector | Any factor or custom formula; up to 10 simultaneously for comparison |
| Decay Horizons | Any subset of [1, 5, 10, 21, 42, 63, 126, 252] trading days |
| IC Method | Pearson IC / Spearman Rank IC / Sector-neutral / Beta-neutral |
| Decay Model | Linear / Exponential / Hyperbolic / All Three |
| Rolling Sub-Window | 252 / 504 / 756 days for time-varying half-life |
| Universe Filter | Full universe / GICS sector / Size bucket (Micro, Small, Mid, Large) |
| Transaction Cost Input | Bps per trade for optimal frequency recommendation |
| ICIR Computation | Include volatility-adjusted IC mean/std alongside raw IC |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| IC Decay Curve | Rank IC vs. forward horizon in trading days with 95% bootstrap bands. |
| Fitted Decay Model Overlay | Comparison of linear/exponential/hyperbolic fits with R-squared annotations. |
| Half-Life Parameter Table | Estimated half-life in trading and calendar days with 90% confidence intervals. |
| Optimal Rebalance Frequency | Cost-benefit curve maximizing net IC after transaction costs. |
| Rolling Half-Life Time Series | Evolution of factor half-life over 10 years (e.g., pre/post-2015 split). |
| Cross-Sector Decay Comparison | Separately estimated decay curves per GICS sector for the same factor. |
| ICIR Chart by Horizon | Signal-to-noise ratio consistency across forward horizons. |
| Factor Signal Power Radar | 8D chart plotting IC, ICIR, half-life, hit rate, crowding, and premium survival. |
| Post-2015 Acceleration Test | Statistical test for half-life shortening in the factor ETF era. |

---

## FEATURE 6: Factor Crowding Monitor

**What it is and why it is a money-bagger:** MSCI sells this as a standalone product. The 2025 quant unwind was driven by factor crowding in Quality and concentrated shared books, with the July 2025 stat-arb collapse traced explicitly to crowded positioning. Goldman Sachs data shows 70% of typical long holdings concentrated in the ten largest positions across quant funds. Allocators in 2026 DDQs explicitly require crowding disclosure. This is a feature that pays for itself the first time it prevents a crowding-driven drawdown.

**Conceptual engine:** Four crowding metrics combined into a composite score. Metric 1: valuation spread percentile (are top-quintile factor stocks expensive relative to their own 10-year history?). Metric 2: return autocorrelation of the factor return series (crowded factors exhibit negative autocorrelation as forced unwinding accelerates and decelerates). Metric 3: position concentration HHI (how concentrated is the factor portfolio in a small number of names?). Metric 4: bid-ask spread trend of the top-quintile portfolio relative to the bottom-quintile (crowding in the long book degrades liquidity).

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Factor Selector | Any factor or portfolio of factors simultaneously |
| Crowding Metrics | Toggle metrics: valuation spread, return autocorrelation, concentration HHI, bid-ask spread trend |
| Composite Score Method | Equal-weight / PCA-based composite / User-defined manual weights |
| Historical Percentile Lookback | 3 / 5 / 10 years for historical context |
| Alert Threshold | Trigger notification when composite score exceeds user-set percentile level |
| Crash Probability Conditioning | Toggle whether probability estimate should be conditioned on current liquidity regime |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Crowding Composite Gauge | 0-to-100 percentile dial with color zones (green < 40th, amber 40th-70th, red > 70th). |
| Crowding Time Series | 10-year history of composite crowding score annotated with historical factor crash dates. |
| Individual Metric Breakdown | Radar chart showing current reading on each crowding metric (valuation, autocorrelation, etc.). |
| Crash Probability Table | Empirical probability of bottom-decile return in next 1, 3, and 6 months. |
| Factor Crowding League Table | Cross-factor comparison of crowding scores, changes, and crash probabilities. |
| Crowding Percentile Heatmap | Factor return chart with crowding percentile colored in background. |
| Deleveraging Risk Score | Measure of unwind speed based on turnover, concentration, and inverse liquidity. |
| Crowding vs. Forward Return | Scatterplot showing relationship between crowding percentile and subsequent 3-month return. |

---

## FEATURE 7: Factor Backtesting Engine with Realistic Transaction Cost Modeling

**What it is and why it is a money-bagger:** Quantpedia Pro charges $1,600 per year purely for access to pre-built backtests. Your engine is fully custom. The critical upgrade over the original spec is implementation shortfall modeling: real transaction costs have three components (explicit commissions, market impact as a function of trade size relative to ADV, and timing cost), and without all three the backtest net returns are optimistic enough to be meaningfully wrong. Walk-forward optimization is the second critical addition: it is the only statistically defensible way to set factor weights in a multi-factor composite.

**Conceptual engine:** At each rebalancing date, sort the 5,000-stock universe by factor score (or composite multi-factor score). Form quintile or decile portfolios. Compute forward returns. Chain across 10 years. Transaction costs modeled in three layers. Layer 1: explicit cost (user-input bps per trade). Layer 2: market impact using a Kyle lambda-style model estimated from ADV data per stock (estimated impact in bps = lambda times trade size as fraction of ADV, where lambda is calibrated cross-sectionally from your price and volume data). Layer 3: timing cost (the slippage between decision price at close and execution price the following open, estimated as a function of overnight volatility and average overnight gap for each stock). Walk-forward optimization runs the factor weight optimization on a rolling training window and applies the weights out-of-sample on the subsequent holding window.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Factor Selection | Single factor or multi-factor composite (up to 15 factors) |
| Composite Method | Equal-weight / rank-then-combine / z-score average / manual weights / walk-forward ML-optimized |
| Universe Filter | Full universe / Sector filter / Custom screen (market cap, ADV thresholds) |
| Portfolio Construction | Top quintile L-O / L-S top vs. bottom quintile / Full decile analysis |
| Portfolio Weighting | Equal-weight / rank-weight / factor-score-proportional |
| Rebalancing Frequency | Daily / weekly / monthly / quarterly / annual / signal-triggered |
| Transaction Cost Model | Flat bps / Kyle-lambda market impact / full three-component implementation shortfall |
| ADV Participation Cap | Max percentage of ADV per trade (e.g., 10-25%) |
| Short Selling | Include/exclude with borrow cost input in bps |
| Benchmark | None / S&P 500 / Russell 1000 / custom |
| Neutralization | Raw / sector-neutral / beta-neutral |
| Walk-Forward Window | Training window (252/504/756d), Holding window (21/63/126d) |
| Backtest Period | User-defined start and end date |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Two-Panel Equity Curve | Cumulative return (gross/net) with benchmark and time-series drawdown. |
| Full Statistics Table | Return, Vol, Sharpe, Sortino, Calmar, Max DD, Skew, Kurtosis, VaR, CVaR, Hit Rate. |
| Quintile Monotonicity | Average annualized return per quintile/decile to test signal monotonicity. |
| Factor Premium Spread | Time-series of rolling 12m and 36m return spread between top and bottom portfolios. |
| Transaction Cost Decomposition | Stacked bars showing explicit cost, market impact, and timing cost over time. |
| Gross vs. Net Sub-Period | Table showing gross premium, total costs, and net premium per calendar year. |
| Turnover Analysis | One-way monthly turnover time-series and stability chart. |
| ADV Capacity Report | AUM-dependent net alpha curve showing where impact costs consume premium. |
| Walk-Forward Report | In-sample vs. out-of-sample IC comparison for optimized weights. |
| Monte Carlo Bands | 10th-50th-90th percentile equity curves from randomized rebalance dates. |
| Out-of-Sample Toggle | Statistics reported separately for training and OOS periods. |

---

## FEATURE 8: Factor Covariance Matrix and Risk Forecasting

**What it is and why it is a money-bagger:** Bloomberg and Axioma charge as a standalone data product. The critical insight from 2026 research is that the covariance matrix changes dramatically between normal and crisis periods: crowding causes correlations to spike simultaneously across factors, so a normal-period matrix massively underestimates tail risk. Showing the crisis vs. normal matrix comparison is the feature that makes risk managers wake up.

**Conceptual engine:** Four covariance estimation methods run in parallel. (1) Sample covariance on the chosen estimation window. (2) Exponentially-weighted covariance with user-set half-life, giving more weight to recent observations. (3) Ledoit-Wolf shrinkage estimator, producing a well-conditioned matrix even when the number of factors approaches the number of observations. (4) DCC-GARCH (Dynamic Conditional Correlation), the most sophisticated method, which models both time-varying volatilities and time-varying correlations using the GARCH framework. The stress covariance is estimated by filtering the factor return history to only crisis periods and computing the sample covariance on that subset.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Factor Set | Any subset from factor library |
| Estimation Method | Sample / EWMA (21-252d half-life) / Ledoit-Wolf / DCC-GARCH / All Comparison |
| Estimation Window | 252 / 504 / 756 / 1260 days / Full history |
| Display Mode | Correlation vs. Covariance toggle |
| Stress Period | GFC 2008, COVID 2020, Rate Shock 2022, 2025 Unwind, etc. |
| Portfolio Context | Import holdings from Feature 2 for risk attribution |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Correlation Heatmap | N-by-N matrix with numerical annotations for correlations > 0.3. |
| Factor Volatility Bars | Annualized volatility per factor with historical percentile context. |
| Normal vs. Crisis Comparison | Side-by-side heatmaps showing correlation spikes during stress periods. |
| Eigenvalue Decomposition | Chart of eigenvalues and cumulative variance explained curve. |
| Rolling Correlation Chart | Time-series of 252-day DCC correlation for any factor pair. |
| Matrix Condition Number | Mathematical measure of numerical stability and optimization reliability. |
| Portfolio Risk Decomposition | Breakdown of active factor risk into variance and covariance contributions. |
| Min-Variance Combination | Optimized weights and projected volatility for the minimum variance factor set. |
| Covariance Stability Score | Ratio of crisis-to-normal condition numbers as a risk disclosure. |

---

## FEATURE 9: Strategy Capacity Analyzer (NEW — Replacing Original Feature 12)

**What it is and why it is a money-bagger:** The 2026 allocator research from Resonanz Capital is explicit: "Provide a capacity map: expected slippage by AUM, turnover, and liquidity bucket." This is what kills allocations when it is missing. A quant fund that cannot show its capacity ceiling in concrete numbers is, in allocator perception, hiding something. The capacity question is the one that distinguishes a research insight from a deployable strategy. No commercial platform builds this as a standalone feature because it is uncomfortable (it bounds how much money you can raise), but institutional allocators require it.

**Conceptual engine:** For a given factor strategy defined in Feature 7, compute the capacity ceiling as the AUM level at which implementation shortfall costs fully consume the gross factor premium. Three-step computation. Step 1: for each stock in the factor portfolio, compute its average daily dollar volume over the trailing 63 days. Step 2: for each rebalancing event, model the required dollar trades as a function of AUM and the portfolio's one-way turnover. Step 3: apply the Kyle lambda market impact model from Feature 7 to translate dollar trade size into basis points of price impact. Aggregate across all stocks and all rebalancing events to produce the AUM-dependent net alpha curve. The capacity ceiling is where net alpha crosses zero.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Strategy Reference | Import from Feature 7 or define new inline |
| AUM Range Sweep | $1 million to $10 billion (user-defined sweep points) |
| ADV Participation Cap | 10-25% (industry standard or user-set) |
| Kyle Lambda Method | Platform-estimated / User-provided coefficient |
| Cost Components | Explicit only / Explicit + Impact / Full implementation shortfall |
| Rebalance Frequency | Sourced from Feature 7 config |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Capacity Curve Chart | AUM (x-axis) vs. Net Alpha (y-axis) with capacity ceiling and optimal AUM point. |
| Slippage vs. AUM Table | Estimated slippage, net alpha, and net Sharpe for $10M, $100M, $1B, $10B levels. |
| Time to Liquidate | Trading days required to liquidate portfolio at each AUM level based on ADV cap. |
| Capacity Sensitivity Analysis | Impact of changes in frequency, ADV cap, or universe on the capacity ceiling. |
| Allocator Capacity Memo | Formatted one-page summary for investor reporting and LP DDQs. |

---

## FEATURE 10: Factor-Based Portfolio Optimizer

**What it is and why it is a money-bagger:** Axioma's standalone optimizer costs $30,000-$50,000 per year. The critical additions over the original spec are robust optimization and the Factor Alignment Problem (FAP) diagnostic. Robust optimization is what separates a toy optimizer from a production one: when expected returns are uncertain (which they always are), the standard mean-variance solution is notoriously unstable and overfit to small estimation errors. Robust optimization treats the uncertainty explicitly as part of the constraint set.

**Conceptual engine:** Quadratic programming: minimize w-prime-Sigma-w subject to constraints, or equivalently maximize w-prime-mu minus lambda times w-prime-Sigma-w. The covariance matrix Sigma is taken from Feature 8 (user chooses which estimator). Robust optimization uses an uncertainty set around the expected return vector (an ellipsoidal uncertainty set parameterized by the user's confidence in their views, using the Goldfarb-Iyengar robust QP formulation). The Factor Alignment Problem is detected by computing the R-squared of regressing the user's alpha signals on the factors in the risk model: when alpha loads on factors outside the risk model, the optimizer systematically misbets because it sees those bets as "free" alpha when they are actually correlated risks.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Alpha Source | Hist. Factor Returns / Manual ER / Black-Litterman Views / Feature 4 Timing Alphas |
| Risk Aversion (Lambda) | Slider from max-return to min-risk with real-time frontier updates |
| Robust Optimization | Toggle; confidence level slider (Low = Max Robustness, High = Standard QP) |
| Constraints | Gross/Net limit, factor exposure bounds, sector bounds, position limits, turnover, TE, TC budget |
| Efficient Frontier Sweep | Generate 50 Pareto-optimal portfolios by sweeping lambda |
| Optimization Horizon | Short (Momentum-heavy) / Long (Value-heavy) / Mixed |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Efficient Frontier Chart | (Vol, ER) curve with current optimal, min-variance, and max-Sharpe points. |
| Optimal Factor Allocation | Table of factor weights, ER contribution, and marginal risk contribution. |
| Optimal Exposure Profile | Linkage to Feature 2 for full exposure decomposition of optimized solution. |
| Risk Budget Pie | Variance attribution to factors vs. idiosyncratic risk. |
| Constraint Binding Report | Active constraints at optimal solution with shadow prices. |
| Black-Litterman Adjustment | Comparison of prior vs. posterior expected return vectors. |
| Robust vs. Standard Comparison | side-by-side weight comparison showing robustness impact. |
| FAP Diagnostic | Regression of alpha signals on risk model; flags systemic positioning errors. |
| Rebalancing Cost-Benefit | Improvement in Sharpe vs. estimated transaction cost for current rebalance. |

---

## FEATURE 11: Factor Stress Testing and Reverse Stress Testing

**What it is and why it is a money-bagger:** Bloomberg charges separately for its scenario engine. The critical upgrade over the original spec is reverse stress testing: instead of "given this scenario, what is my loss?" it answers "what scenario would cause my portfolio to lose X%?" This is now a regulatory requirement in many jurisdictions (Basel III, ESMA) and is the first question institutional risk committees ask. Additionally, contagion modeling — when one factor crashes, which others follow and at what lag? — is directly applicable to the 2025 quant unwind experience.

**Conceptual engine:** Forward stress test: historical scenario replay (find all periods most similar to the user-defined scenario using Mahalanobis distance on a macro variable vector, then average factor returns in those periods) plus parametric stress (apply user-defined factor return shocks directly and propagate through Feature 2 exposures). Reverse stress test: define a loss threshold L, then solve for the factor return vector that minimizes probability while still producing a portfolio loss of L, using an ellipsoidal constraint on the factor return vector parameterized by the historical covariance matrix. Contagion model: VAR (Vector Autoregression) on daily factor returns with two to five lags, used to estimate the impulse response of each factor to a shock in any other factor.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Scenario Type | Historical preset / Historical custom date range / Parametric / Macro-linked (mapping macro variables to factor shocks) |
| Historical Preset Library | GFC 2008, COVID 2020, Taper Tantrum 2013, Rate Shock 2022, China Deleveraging 2015, Liberation Day 2025, Quant Unwind 2025 |
| Parametric Shock Inputs | Bps or Standard Deviation return shocks per factor with linear/nonlinear propagation |
| Reverse Stress Test | User-defined loss threshold (percentage or absolute $) to solve for minimum-probability scenario |
| Contagion Model Lag | VAR with 1 / 2 / 5 / 21-day lags |
| Portfolio to Stress | Import from Feature 2 or direct input |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Factor Return Bar Chart | Expected return per factor in scenario with 5th/95th percentile historical range. |
| Portfolio P&L Attribution | Waterfall chart showing gain/loss breakdown by contributing factor exposure. |
| Historical Analog Comparison | Closest historical period match via Mahalanobis distance with predictive performance overlay. |
| Reverse Stress Test Result | Minimum-probability factor return vector that triggers the defined loss; plain-language scenario description. |
| Contagion Impulse Response | Chart showing the propagation of a 1-SD shock across all factors at 1, 5, 10, and 21-day horizons. |
| Multi-Scenario Comparison | Side-by-side table of P&L, contribution, and recovery time for up to six scenarios. |
| Hedging Recommendation | Required short factor weights to offset scenario shock and estimated hedging cost in bps. |
| Stress VaR and CVaR | 95th and 99th percentile loss estimates based on scenario distribution. |

---

## FEATURE 12: Factor DNA Attribution (Quant360 Signature Feature)

**What it is and why it is a money-bagger:** This is entirely original. No commercial platform offers this framing. Instead of asking "what is my portfolio's factor exposure?" it asks "what kind of factor is this, at a fundamental level, and why does it work?" This is the feature that gets cited in academic papers and gets Quant360 into research conversations at AQR-level shops. The auto-classifier — which categorizes each factor as a Risk Factor, Behavioral Factor, Structural Factor, or Data-Mining Artifact with confidence scores — is the feature that practitioners will screenshot and share.

**Conceptual engine:** For a given factor strategy, run every other analytical module simultaneously and synthesize into a single diagnostic object. Sector attribution uses the Herfindahl-Hirschman Index on the sector weights of the long and short book. Regime dependence is computed from Feature 4's conditional returns. Crowding state comes from Feature 6. Decay profile comes from Feature 5. Correlation fingerprint comes from Feature 8's rolling correlation time series. The auto-classifier uses a decision tree trained on the outputs of all these diagnostics against a labeled training set of known factor types from the academic literature.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Primary Factor | Any single factor from the library or a custom composite |
| Comparison Factors | Up to four factors for side-by-side radar chart comparison |
| Analysis Depth | Quick (DNA card only) / Full (complete sub-module breakdown) |
| Period Focus | Full history / Expansion-only / Recession-only / High-vol regime only |
| Auto-Classifier Training | Use academic factor classification labels / Use user-provided labels |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Factor DNA Card | Octagonal radar chart: IC, ICIR, Half-life, Crowding, Sector HHI, Regime Sensitivity, Purity. |
| Sector DNA Chart | Long vs. Short book GICS sector distribution with historical evolution animation. |
| Regime DNA Bar | Performance breakdown across six macro regimes (Growth x Rates). |
| Correlation DNA | Rolling 252-day correlation heatmap showing evolution of factor co-movement. |
| Return Anatomy | Decomposition into Valuation Reversion, Characteristic Momentum, and Risk Premium. |
| Factor Purity Score | FF5-adjusted annualized alpha as a % of total gross premium; flags "copycat" factors. |
| Auto-Classifier Output | Probability stack: Risk Factor / Behavioral / Structural / Data-Mining Artifact. |

---

## FEATURE 13: Live Signal Monitoring Dashboard (NEW — Replacing Original Feature 8 Factor Zoo)

**What it is and why it is a money-bagger:** The 2026 allocator research from Resonanz Capital and HedgeCo explicitly identifies live signal monitoring as the key differentiator between adaptive quant funds (which survived 2025) and non-adaptive ones (which did not). "The most adaptive platform can identify when a signal is weakening." This is the feature that makes Quant360 a live operational tool rather than a historical research tool. No platform outside of internal quant fund infrastructure offers real-time signal health monitoring across a multi-factor library.

**Conceptual engine:** For every factor in the library, compute four health metrics daily using a rolling 63-day window. (1) IC drift: is the current 63-day IC significantly below the trailing 252-day average IC? Measured as a z-score of the recent IC vs. its long-run distribution. (2) IC autocorrelation break: has the pattern of IC autocorrelation changed, indicating a structural break in how the signal behaves? Tested via a structural break Chow test on the rolling IC series. (3) Crowding velocity: is the crowding score from Feature 6 rising at an unusual rate? Measured as the 21-day change in crowding percentile. (4) Return-characteristic divergence: is the factor's characteristic (e.g., the P/B ratio of the value portfolio) moving in a direction inconsistent with its recent return behavior? Flagged when the rolling IC sign disagrees with the 21-day z-score of the underlying characteristic.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Factor Library Scope | Full library / User-selected subset |
| IC Drift Threshold | User-set z-score for drift alerts (Default: -1.5 SD) |
| Rolling Window | 21 / 42 / 63 days for recent metrics; 252 / 504 days for baseline |
| Alert Preferences | Dashboard flag / Email notification / Webhook integration |
| Portfolio Linkage | Connect holdings from Feature 2 to weight health alerts by actual exposure |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Signal Health Dashboard | Live table: IC (21d), IC z-score, Crowding, return-characteristic alignment, Overall Score. |
| IC Drift Time Series | 252-day rolling IC chart with mean reference and shaded alert zones. |
| Structural Break Detector | Chow test p-values for IC series structural breaks over last 252 days. |
| Crowding Velocity Gauge | Rate-of-change chart for factor crowding; flags high-velocity signals in red. |
| Weighted Health Score | Exposure-weighted average factor health for the entire portfolio. |
| Alert Log | History of triggered alerts, thresholds, and subsequent 21-day forward returns. |
| Signal Recovery Tracker | Real-time monitoring of metrics post-alert to distinguish noise from structural decay. |

---

## FEATURE 14: Allocator Transparency Report Generator (NEW — Replacing Original Feature 12)

**What it is and why it is a money-bagger:** The 2026 LP DDQ standard (ILPA 2.0) now spans 250+ questions, and an estimated 85% of LPs rejected a manager over operational concerns alone in 2025. Factor attribution, crowding disclosure, capacity maps, and drawdown analysis are all explicitly required. Every quant fund using Quant360 needs to produce these documents for their LPs. Building a formatted, institutionally-standard report generator that pulls from all other features makes Quant360 a business-critical tool that cannot be canceled without disrupting the fund's LP relationship workflow.

**Conceptual engine:** Templated report generation that pulls live computed outputs from Features 2, 3, 6, 7, and 9. The report structure follows the AIMA DDQ and ILPA 2.0 standard sections. Each section auto-populates from the corresponding feature's output. The user can customize the narrative text, add context, and white-label the output. The final report is generated as a formatted PDF with professional typography, consistent chart styling, and page numbering.

**INPUTS**

| Parameter | Options |
| :--- | :--- |
| Report Type | Full LP DDQ / Quarterly Investor Letter / Monthly Risk Report / Custom selection |
| Portfolio Reference | Sourced from Feature 2 |
| Date Range | Sourced from Feature 3 (Performance Attribution) |
| Section Data Sourcing | Crowding (F6), Capacity (F9), Stress Tests (F11), Signal Health (F13) |
| White-Labeling | Fund name, Logo, Contact info, Disclaimer text |
| Narrative Narrative Text | User-defined free-text context blocks for each section |
| Chart Styling | Light / Dark theme, Color palette selection, Export size |

**OUTPUTS**

| Output | Description |
| :--- | :--- |
| Formatted PDF Report | Professional-grade document with all selected feature outputs integrated. |
| Section-by-Section Export | Individual PDF pages or high-res images for third-party document embedding. |
| AIMA DDQ Index | Cross-reference notation mapping each section to specific AIMA DDQ questions. |
| Audit Trail Log | Timestamped record of estimation parameters and data versions for compliance. |

---

## COMPLETE FEATURE MAP: WHAT EACH REPLACES AND WHY

| Feature | Status | Institutional $ Trigger |
|---|---|---|
| 1. Factor Valuation Spread Monitor | **New (replaced original Feature 1)** | First thing PMs check every morning; no clean source exists |
| 2. Portfolio X-Ray (Factor Exposure Decomposition) | **Upgraded** | Barra ~$50K/yr; LP DDQ now requires this monthly |
| 3. Performance Attribution | **Upgraded** | Bloomberg PORT per-seat pricing; DDQ standard |
| 4. Probabilistic Regime Analysis | **Upgraded** | MSCI sells separately; 2025 unwind shows stakes |
| 5. Alpha Decay and Half-Life | **Peaked (kept)** | No commercial platform; 2024 arxiv confirms hyperbolic > exponential |
| 6. Factor Crowding Monitor | **Peaked (kept)** | MSCI standalone product; LP DDQ required post-2025 |
| 7. Backtesting with Implementation Shortfall | **Upgraded** | Quantpedia $1,600/yr for pre-built; custom engine + realistic costs = moat |
| 8. Factor Covariance Matrix | **Peaked (kept)** | Bloomberg/Axioma data product; crisis vs. normal comparison critical |
| 9. Strategy Capacity Analyzer | **New (replaced Feature 12)** | Allocators require "capacity map" in 2026 DDQ; no platform offers it |
| 10. Portfolio Optimizer with FAP Diagnostic | **Upgraded** | Axioma optimizer $30-50K/yr; robust optimization + FAP = Axioma parity |
| 11. Stress Testing + Reverse Stress Testing | **Upgraded** | Bloomberg scenario engine; Basel III reverse stress = regulatory requirement |
| 12. Factor DNA Attribution | **Peaked (kept)** | Entirely original; auto-classifier is a shareable, citable research output |
| 13. Live Signal Monitoring Dashboard | **New (replaced Feature 8)** | Directly addresses 2025-2026 quant fund failure mode: signal degradation blindness |
| 14. Allocator Transparency Report Generator | **New (replaced Feature 12 diagnostics)** | ILPA 2.0 DDQ spans 250+ questions; 85% of LPs rejected managers on operational grounds in 2025 |
