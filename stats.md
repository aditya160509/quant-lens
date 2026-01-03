  SYSTEM PROMPT: RESEARCH LABS — STATISTICAL & MARKET INTELLIGENCE PLATFORM
You are building a Research Labs module for an institutional-grade trading platform. This is a decision-first, data-driven research environment where every feature exists to prevent bad trades before capital is deployed.
This is NOT a backtesting engine. This is NOT a portfolio manager. This is a statistical validation and market intelligence suite that sits upstream of all trading decisions.

CORE PHILOSOPHY
Your north star:
* Every feature outputs actionable visualizations: charts, tables, heatmaps, flags — never just scores
* Everything must be interpretable by humans making capital allocation decisions
* No black boxes. No ML vanity metrics. Only deterministic, institution-used mathematics
* The goal is to kill bad strategies early, not to optimize good ones
Design principles:
* Mobile-first is irrelevant here. This is desktop professional software. Optimize for large screens, multiple monitors, and dense information display
* Information density matters. Traders need to see 10+ metrics simultaneously without scrolling
* Charts are first-class citizens. Every insight should be visual-first, with raw data accessible on demand
* Color signals meaning. Use color strategically: red = danger/rejection, green = pass/confirmation, yellow = caution, blue = neutral data
* Tables are scannable. Bold headers, monospace numbers, zebra striping, sortable columns
* Flags and alerts are unambiguous. Use clear iconography: ✓ (pass), ✗ (reject), ⚠ (warning), ⓘ (info)

APPLICATION ARCHITECTURE
Navigation Structure
Research Labs
├── Time Series (GROUP 1)
│   ├── Stationarity (ADF Test)
│   ├── Cointegration (Johansen)
│   ├── Granger Causality
│   ├── VAR Model
│   └── Autocorrelation
├── Factors (GROUP 2)
│   ├── Eigen Decomposition
│   └── Random Matrix Filter
├── Drawdowns (GROUP 3)
│   ├── Max Drawdown Duration
│   └── Pain Index
├── Performance (GROUP 4)
│   ├── Calmar Ratio
│   ├── Sortino Ratio
│   └── Omega Ratio
├── Tails (GROUP 5)
│   ├── Jarque-Bera
│   ├── Tail Risk Analysis
│   └── GPD (Extreme Value)
├── Validation (GROUP 6)
│   └── Bootstrap Simulation
├── Signals (GROUP 9)
│   └── Information Coefficient
└── Breadth (GROUP 10)
    ├── McClellan Oscillator
    └── McClellan Summation
Layout Standards
Every feature page follows this structure:
1. Top Control Bar
    * Asset/Strategy selector (dropdown or search)
    * Time period selector (date range picker)
    * Parameter controls (specific to each feature)
    * "Run Analysis" button (prominent, right-aligned)
2. Primary Output Panel (60% width)
    * Main visualization (chart/heatmap)
    * Always includes: title, axes labels, legend, tooltips
3. Secondary Insights Panel (40% width)
    * Summary statistics table
    * Decision flags/alerts
    * Interpretive guidance text
4. Raw Data Drawer (collapsible, bottom)
    * Exportable CSV/JSON
    * Full numerical output

GROUP 1: TIME SERIES VALIDITY & INFORMATION FLOW
Purpose: Gate-keeping. Nothing proceeds without passing these tests.

1.1 ADF Test (Augmented Dickey-Fuller)
Mathematical Logic:
* Tests null hypothesis: series has unit root (non-stationary)
* Runs regression: Δy_t = α + βt + γy_{t-1} + Σδ_i Δy_{t-i} + ε_t
* Test statistic compared to critical values (-3.43 at 5% significance)
* If test statistic < critical value → reject null → series is stationary
* Rolling window analysis detects regime changes
Input Requirements:
* Price series OR spread series (minimum 100 observations)
* Optional: rolling window size (default 60 periods)
* Optional: significance level (default 5%)
Output Specifications:
PRIMARY VISUALIZATION: Rolling Stationarity Heatmap
* X-axis: Time
* Y-axis: Window position
* Color: ADF test statistic value
    * Deep red: < -3.43 (stationary, safe)
    * Yellow: -3.0 to -2.0 (borderline)
    * Dark gray: > -2.0 (non-stationary, danger)
* Horizontal line overlay: critical value threshold
* Tooltip: date, test statistic, p-value, conclusion
SECONDARY OUTPUTS:
Decision Flag Panel:
┌─────────────────────────────────────┐
│ ✓ SERIES IS STATIONARY              │
│   Test Statistic: -4.12              │
│   Critical Value: -3.43 (5%)         │
│   P-Value: 0.0008                    │
│                                      │
│ ⚠ REGIME INSTABILITY DETECTED        │
│   3 breaks in last 252 periods       │
└─────────────────────────────────────┘
Transformation Recommendation Table:
Transformation	ADF Stat	P-Value	Status
Raw Prices	-1.23	0.65	✗ Non-stationary
First Difference	-8.91	0.00	✓ Stationary
Log Returns	-9.45	0.00	✓ Stationary
Stability Regime Timeline:
* Line chart showing test statistic over time
* Shaded regions: red (non-stationary periods), green (stationary periods)
* Vertical lines marking regime breaks
UI Layout:
* Top: Asset selector, date range, window size slider
* Left (60%): Rolling stationarity heatmap
* Right (40%):
    * Top: Decision flag (large, color-coded)
    * Middle: Transformation table
    * Bottom: Regime timeline chart

1.2 Johansen Cointegration
Mathematical Logic:
* VECM framework: Δy_t = Πy_{t-1} + ΣΓ_i Δy_{t-i} + ε_t
* Decomposition: Π = αβ' (where β = cointegrating vectors)
* Eigenvalue test on Π matrix
* Test statistics: trace test and max eigenvalue test
* Estimates cointegration rank (r) and hedge ratios (β)
Input Requirements:
* Multiple asset price series (2-10 assets, minimum 100 observations each)
* Optional: lag order (default auto-selected via AIC)
* Optional: deterministic trend specification
Output Specifications:
PRIMARY VISUALIZATION: Cointegration Heatmap
* Matrix layout: assets on both axes
* Cell color intensity: cointegration strength (trace statistic normalized)
* Diagonal: self (always max intensity)
* Hover: shows eigenvalues, trace stat, p-value
* Overlay: green checkmarks on pairs passing at 5% significance
SECONDARY OUTPUTS:
Cointegration Rank Table:
┌──────────────────────────────────────────────────────┐
│ Rank  Trace Stat  Critical (5%)  P-Value    Conclusion│
│  0      45.23        29.79        0.0003    ✗ Reject  │
│  1      12.45        15.49        0.1420    ✓ Accept  │
│  2       3.21         3.84        0.0731    ✓ Accept  │
│                                                        │
│ COINTEGRATION RANK: 1                                 │
└──────────────────────────────────────────────────────┘
Hedge Ratio Table:
Asset Pair	Hedge Ratio	Std Error	Half-Life (days)	Status
SPY-QQQ	1.23	0.08	12.4	✓ Valid
GLD-SLV	0.67	0.15	8.1	⚠ Unstable
Rolling Stability Chart:
* Line chart: hedge ratio over rolling windows
* Confidence bands (± 2 std errors)
* Alert markers where ratio breaks out of bands
* Color: green (stable), red (break)
Cointegration Break Alerts Panel:
┌─────────────────────────────────────────┐
│ ⚠ STABILITY WARNING                      │
│   SPY-QQQ hedge ratio shifted            │
│   Previous: 1.23 → Current: 1.45         │
│   Break Date: 2024-11-15                 │
│   Recommend re-estimation                │
└─────────────────────────────────────────┘
UI Layout:
* Top: Multi-asset selector, date range, lag order dropdown
* Left (50%): Cointegration heatmap (square)
* Right (50%):
    * Top: Rank table (compact)
    * Middle: Hedge ratio table (sortable)
    * Bottom: Rolling stability chart

1.3 Granger Causality
Mathematical Logic:
* Tests whether past values of X improve prediction of Y
* Restricted model: Y_t = Σα_i Y_{t-i} + ε_t
* Unrestricted model: Y_t = Σα_i Y_{t-i} + Σβ_j X_{t-j} + ε_t
* F-test: F = [(RSS_r - RSS_u)/q] / [RSS_u/(n-k)]
* Null hypothesis: X does not Granger-cause Y
* Test across multiple lag windows to find optimal lead time
Input Requirements:
* Signal series (predictor)
* Asset return series (target)
* Lag range to test (e.g., 1-20 periods)
* Optional: significance level (default 5%)
Output Specifications:
PRIMARY VISUALIZATION: Lead-Lag Heatmap
* X-axis: Signal variables (if multiple)
* Y-axis: Asset returns (if multiple)
* Cell color: F-statistic value (normalized)
    * Dark green: high F-stat, low p-value (strong causality)
    * Light yellow: moderate
    * Gray: no causality detected
* Cell annotation: optimal lag number if significant
* Tooltip: F-stat, p-value, lag, conclusion
SECONDARY OUTPUTS:
Valid Predictor Table:
Signal	Target	F-Stat	P-Value	Optimal Lag	Status
VIX_Change	SPY_Return	12.45	0.001	1	✓ Valid
Oil_Return	XLE_Return	8.32	0.004	2	✓ Valid
News_Sentiment	AAPL_Return	1.23	0.267	-	✗ Invalid
Lag Window Recommendation Table:
┌──────────────────────────────────────────────┐
│ Signal: VIX_Change → Target: SPY_Return      │
│                                              │
│ Lag  F-Stat  P-Value  Status                │
│  1    12.45   0.001   ✓ Significant          │
│  2     8.21   0.005   ✓ Significant          │
│  3     3.12   0.078   ✗ Not Significant      │
│  5+    <2.0   >0.10   ✗ Not Significant      │
│                                              │
│ RECOMMENDED LAG: 1 period                    │
└──────────────────────────────────────────────┘
F-Statistic by Lag Chart:
* Line chart: F-statistic (Y) vs lag (X)
* Horizontal line: critical F-value
* Shaded region above line: significant lags
* Peak marker: optimal lag
UI Layout:
* Top: Signal selector, target selector, lag range inputs
* Center (70%): Lead-lag heatmap (if multiple pairs)
* Right (30%):
    * Top: Valid predictor table
    * Bottom: Lag chart for selected pair

1.4 VAR Model (Vector Autoregression)
Mathematical Logic:
* System of equations: Y_t = A_1 Y_{t-1} + ... + A_p Y_{t-p} + ε_t
* Each variable regressed on lagged values of all variables
* Impulse Response Function (IRF): response of one variable to shock in another
* Variance Decomposition: % of forecast error variance due to each variable
* Orthogonalized shocks via Cholesky decomposition
Input Requirements:
* Multi-asset return matrix (2-10 assets)
* Optional: macro variable series (VIX, rates, etc.)
* Lag order (default auto-selected via AIC)
* IRF horizon (default 20 periods)
Output Specifications:
PRIMARY VISUALIZATION: Impulse Response Function Charts
* Grid layout: rows = shocked variable, columns = responding variable
* Each cell: line chart showing response over time (X: periods, Y: response magnitude)
* Confidence bands (±2 std errors) as shaded region
* Zero line (horizontal)
* Peak response annotated
* Color: blue line (positive response), red line (negative response)
SECONDARY OUTPUTS:
Shock Impact Table:
Shock Variable	Response Variable	Peak Impact	Time to Peak	Persistence (half-life)
SPY	QQQ	0.65	2 days	8 days
VIX	SPY	-0.42	1 day	5 days
Spillover Network Diagram:
* Node-edge graph
* Nodes: asset names (sized by total spillover given + received)
* Edges: directed arrows (thickness = spillover magnitude)
* Color: red edges (negative spillover), green edges (positive spillover)
* Layout: force-directed or circular
* Tooltip on edge: % variance explained
Variance Decomposition Stacked Bar Chart:
* X-axis: Forecast horizon (1, 5, 10, 20 periods)
* Y-axis: % of forecast error variance
* Stacked bars: each color = contributing variable
* Separate chart per target variable
* Legend: variable names with colors
Stress Scenario Table:
┌─────────────────────────────────────────────────────┐
│ SCENARIO: VIX spikes +10%                           │
│                                                     │
│ Asset    1-Day Impact  5-Day Cumulative  10-Day    │
│ SPY         -2.3%          -3.1%          -2.8%    │
│ QQQ         -3.1%          -4.2%          -3.7%    │
│ IWM         -2.8%          -3.8%          -3.3%    │
└─────────────────────────────────────────────────────┘
UI Layout:
* Top: Asset selector (multi-select), lag order, IRF horizon
* Left (60%): IRF charts grid (3x3 or scrollable)
* Right (40%):
    * Top: Shock impact table
    * Middle: Spillover network diagram
    * Bottom: Variance decomposition chart

1.5 Autocorrelation
Mathematical Logic:
* Autocorrelation at lag k: ρ_k = Cov(r_t, r_{t-k}) / Var(r_t)
* Partial autocorrelation: correlation removing intermediate lags
* Ljung-Box Q-test: tests whether group of autocorrelations differs from zero
* Decay rate: measure how quickly autocorrelation diminishes
* Identifies mean reversion speed and overtrading risk
Input Requirements:
* Return series (minimum 100 observations)
* Maximum lag to compute (default 40)
* Significance level (default 5%)
Output Specifications:
PRIMARY VISUALIZATION: Autocorrelation Function (ACF) Chart
* Bar chart: X-axis = lag, Y-axis = autocorrelation coefficient
* Bars: blue (positive), red (negative)
* Horizontal confidence bands: ±1.96/√n (dashed lines)
* Bars outside bands = statistically significant
* Decay envelope overlay (exponential fit)
SECONDARY OUTPUTS:
Persistence Decay Table:
┌─────────────────────────────────────────┐
│ First significant lag: 1                │
│ Last significant lag: 5                 │
│ Half-life: 3.2 periods                  │
│ Decay rate: 0.78 (fast mean reversion) │
│                                         │
│ INTERPRETATION:                         │
│ ✓ Strong mean reversion detected       │
│   Optimal holding period: 3-5 periods   │
└─────────────────────────────────────────┘
Valid Lookback Window Table:
Strategy Type	Recommended Lookback	Rationale
Mean Reversion	5-10 periods	Matches half-life
Trend Following	NOT RECOMMENDED	No persistence detected
Momentum	NOT RECOMMENDED	Negative autocorrelation
Churn Risk Flag:
┌─────────────────────────────────────┐
│ ⚠ HIGH CHURN RISK                   │
│   Autocorrelation drops to zero by  │
│   lag 2. Any lookback > 2 trades    │
│   pure noise.                       │
└─────────────────────────────────────┘
Partial Autocorrelation Function (PACF) Chart:
* Same format as ACF chart
* Shows direct correlation at each lag (removes indirect effects)
* Used to determine AR model order
UI Layout:
* Top: Asset selector, max lag slider
* Left (50%): ACF chart (large)
* Right (50%):
    * Top: Decay table
    * Middle: Lookback window table
    * Bottom: PACF chart (smaller)

GROUP 2: FACTORS & CORRELATION HYGIENE
Purpose: Reveal true diversification. Remove noise from correlation matrices.

2.1 Eigen Decomposition
Mathematical Logic:
* Eigen decomposition of correlation matrix: C = QΛQ'
* Q = eigenvectors (factor loadings)
* Λ = eigenvalues (factor importance)
* Principal components: ranked by eigenvalue size
* Explained variance: λ_i / Σλ
* Asset loadings show exposure to each factor
Input Requirements:
* Asset return correlation matrix (minimum 5 assets)
* Time period for correlation calculation
* Optional: number of top factors to display (default 5)
Output Specifications:
PRIMARY VISUALIZATION: Factor Importance Bar Chart
* X-axis: Factor number (PC1, PC2, PC3, ...)
* Y-axis: Explained variance (%)
* Bars: descending height
* Cumulative line overlay (right Y-axis)
* Horizontal line at 80% cumulative variance
* Color: gradient from dark blue (PC1) to light blue
* Annotation: eigenvalue on each bar
SECONDARY OUTPUTS:
Factor Summary Table:
Factor	Eigenvalue	Explained Variance	Cumulative %	Interpretation
PC1	4.23	42.3%	42.3%	Market Factor
PC2	1.87	18.7%	61.0%	Sector Rotation
PC3	0.95	9.5%	70.5%	Size Factor
PC4	0.62	6.2%	76.7%	Volatility Factor
PC5	0.41	4.1%	80.8%	Noise
Asset Factor Loading Heatmap:
* Rows: Assets
* Columns: Factors (PC1, PC2, PC3, ...)
* Cell color: loading magnitude
    * Dark red: strong negative loading
    * White: zero loading
    * Dark blue: strong positive loading
* Cell value: loading coefficient (e.g., -0.85, 0.92)
* Sortable by any factor column
True Diversification Panel:
┌──────────────────────────────────────────────┐
│ EFFECTIVE # OF INDEPENDENT BETS: 2.7         │
│ (based on eigenvalue concentration)          │
│                                              │
│ ⚠ WARNING: Portfolio appears to have 10      │
│   assets but only 2.7 independent drivers.   │
│   True diversification is LIMITED.           │
└──────────────────────────────────────────────┘
Factor Contribution Pie Chart:
* Shows % contribution of top 3 factors
* "Other factors" slice
* Labels with percentages
UI Layout:
* Top: Asset selector (multi-select), correlation period
* Left (40%): Factor importance bar chart
* Center (35%): Asset loading heatmap
* Right (25%):
    * Top: Factor summary table
    * Bottom: Diversification panel + pie chart

2.2 Random Matrix Filter (Marchenko-Pastur)
Mathematical Logic:
* Marchenko-Pastur theorem: eigenvalue bounds for random correlation matrix
* λ_min = σ²(1 - √(N/T))², λ_max = σ²(1 + √(N/T))²
* N = number of assets, T = time series length, σ = volatility
* Eigenvalues within [λ_min, λ_max] are considered noise
* Remove noisy eigenvalues, reconstruct cleaned correlation matrix
* Improves covariance matrix stability for optimization
Input Requirements:
* Correlation matrix
* Time series length (T)
* Number of assets (N)
* Optional: noise threshold multiplier (default 1.0)
Output Specifications:
PRIMARY VISUALIZATION: Eigenvalue Spectrum Chart
* X-axis: Eigenvalue rank
* Y-axis: Eigenvalue magnitude (log scale)
* Scatter plot: blue dots = eigenvalues
* Horizontal bands:
    * Red band: [λ_min, λ_max] = Marchenko-Pastur noise region
    * Green region above: signal eigenvalues
* Annotation: "X eigenvalues removed" in red band
SECONDARY OUTPUTS:
Noise vs Signal Table:
┌─────────────────────────────────────────────┐
│ Total Eigenvalues: 20                       │
│ Signal Eigenvalues: 6                       │
│ Noise Eigenvalues: 14 (REMOVED)            │
│                                             │
│ Marchenko-Pastur Bounds:                    │
│   Lower: 0.18                               │
│   Upper: 2.42                               │
└─────────────────────────────────────────────┘
Clean vs Raw Correlation Heatmap (Side-by-Side):
* Two heatmaps: "Raw Correlation" | "Filtered Correlation"
* Same assets on both axes
* Color scale: -1 (red) to +1 (blue), 0 (white)
* Visual comparison of correlation stability
* Difference heatmap below showing (Clean - Raw)
Stability Score Table:
Metric	Raw Matrix	Filtered Matrix	Improvement
Condition Number	245.3	12.7	✓ 94.8%
Min Eigenvalue	0.004	0.21	✓ 52.5x
Frobenius Norm	4.23	3.89	✓ Stable
Optimization Impact Panel:
┌──────────────────────────────────────────┐
│ ✓ PORTFOLIO OPTIMIZER SAFETY             │
│                                          │
│   Condition number reduced from 245 → 13 │
│   Matrix is now SAFE for optimization    │
│   Risk of extreme weights: LOW           │
└──────────────────────────────────────────┘
UI Layout:
* Top: Asset selector, time period, threshold multiplier
* Left (50%): Eigenvalue spectrum chart
* Right (50%):
    * Top: Noise vs signal table
    * Middle: Side-by-side heatmaps (stacked vertically)
    * Bottom: Stability table + impact panel

GROUP 3: DRAWDOWN & HUMAN PAIN
Purpose: Measure survivability, not just returns.

3.1 Max Drawdown Duration
Mathematical Logic:
* Drawdown at time t: DD_t = (Equity_t - Peak_t) / Peak_t
* Peak_t = max equity up to time t
* Drawdown duration: time between peak and recovery to new peak
* Underwater period: time equity is below previous peak
* Distribution analysis: histogram of all drawdown durations
Input Requirements:
* Strategy equity curve (cumulative returns)
* Optional: drawdown threshold to flag (default 10%)
Output Specifications:
PRIMARY VISUALIZATION: Underwater Equity Chart
* X-axis: Time
* Y-axis: Equity value
* Line chart: equity curve (blue line)
* Peak line overlay (dotted black line connecting peaks)
* Shaded regions: underwater periods (red fill between equity and peak)
* Duration annotations on longest drawdown periods
* Tooltip: date, equity, drawdown %, days underwater
SECONDARY OUTPUTS:
Drawdown Duration Table:
Rank	Start Date	End Date	Max DD %	Duration (days)	Recovery Date	Status
1	2023-03-15	2023-09-22	-18.5%	191	2024-01-10	✓ Recovered
2	2024-06-01	2024-10-15	-12.3%	136	-	⚠ Ongoing
3	2022-11-08	2023-02-20	-9.2%	104	2023-02-20	✓ Recovered
Time Underwater Histogram:
* X-axis: Duration buckets (0-30 days, 31-60, 61-90, 90-180, 180+)
* Y-axis: Frequency
* Bars: count of drawdown periods in each bucket
* Color: gradient from green (short) to red (long)
* Mean line overlay
Capital Lockup Warning Panel:
┌──────────────────────────────────────────────┐
│ ⚠ LONG DRAWDOWN ALERT                        │
│                                              │
│   Current drawdown: 136 days (ongoing)       │
│   Average recovery: 78 days                  │
│   Longest historical: 191 days               │
│                                              │
│   Capital has been locked for 4.5 months     │
└──────────────────────────────────────────────┘
Drawdown Statistics Summary:
Average Drawdown Duration: 78 days
Median: 62 days
90th Percentile: 145 days
Max: 191 days
% Time Underwater: 42%
UI Layout:
* Top: Strategy selector, date range
* Center (70%): Underwater equity chart (full width)
* Right (30%):
    * Top: Drawdown duration table (scrollable)
    * Middle: Histogram
    * Bottom: Warning panel + stats

3.2 Pain Index
Mathematical Logic:
* Pain Index = Σ|DD_t| over all time periods
* Integrates drawdown depth and duration
* Higher pain = longer/deeper drawdowns
* Normalized by number of periods
* Compare strategies: lower pain per unit return is better
Input Requirements:
* Strategy equity curve
* Optional: comparison strategies
Output Specifications:
PRIMARY VISUALIZATION: Pain vs Return Scatter Plot
* X-axis: Annualized Return (%)
* Y-axis: Pain Index
* Scatter points: each strategy
* Point size: Sharpe ratio (larger = better)
* Color: Calmar ratio (green = high, red = low)
* Efficient frontier overlay (convex hull of Pareto-optimal strategies)
* Quadrant lines: median return, median pain
* Tooltip: strategy name, return, pain, Sharpe, Calmar
SECONDARY OUTPUTS:
Strategy Survivability Ranking Table:
Rank	Strategy	Annual Return	Pain Index	Pain-Adjusted Return	Verdict
1	Mean Rev 60d	12.3%	8.4	1.46	✓ Best
2	Trend 20d	15.1%	14.2	1.06	⚠ High Pain
3	L/S Equity	9.8%	6.1	1.61	✓ Excellent
4	Vol Arb	7.2%	18.9	0.38	✗ Unsustainable
Pain-Adjusted Return = Annual Return / Pain Index
Cumulative Pain Chart:
* Line chart: X-axis = time, Y-axis = cumulative pain
* Multiple lines: one per strategy
* Steeper slope = more pain accumulating
* Flat regions = no drawdown (good)
* Color-coded by strategy
Pain Decomposition Panel:
┌──────────────────────────────────────────────┐
│ PAIN BREAKDOWN: Mean Rev 60d                 │
│                                              │
│ Total Pain Index: 8.4                        │
│   From depth: 4.2 (50%)                      │
│   From duration: 4.2 (50%)                   │
│                                              │
│ Worst pain period: Mar-Sep 2023 (3.1 pain)  │
└──────────────────────────────────────────────┘
Psychological Cost Summary:
If you invested $100K:
- Max paper loss: $18,500
- Total pain-days: 1,247
- Expected annual pain: 8.4 units
- Survivability: MODERATE
UI Layout:
* Top: Strategy selector (multi-select for comparison)
* Left (50%): Pain vs return scatter plot
* Right (50%):
    * Top: Ranking table
    * Middle: Cumulative pain chart
    * Bottom: Pain decomposition + cost summary

GROUP 4: PERFORMANCE EFFICIENCY
Purpose: Decide what deserves capital allocation.

4.1 Calmar Ratio
Mathematical Logic:
* Calmar = CAGR / |Max Drawdown|
* CAGR = (Ending Value / Starting Value)^(1/Years) - 1
* Max Drawdown = largest peak-to-trough decline
* Ratio > 1.0 is good, > 2.0 is excellent
* Measures return per unit of worst-case risk
4.2 Sortino Ratio
Mathematical Logic:
* Sortino = (Return - Risk-Free Rate) / Downside Deviation
* Downside Deviation = √(Σ min(r_t - target, 0)² / n)
* Only penalizes downside volatility (ignores upside)
* Ratio > 1.0 is good, > 2.0 is excellent
4.3 Omega Ratio
Mathematical Logic:
* Omega(τ) = Σ(r_t - τ | r_t > τ) / Σ(τ - r_t | r_t < τ)
* τ = threshold return (often 0% or risk-free rate)
* Ratio of probability-weighted gains to losses
* Considers full return distribution
* Ratio > 1.0
means more gains than losses
Combined Output Specifications:
PRIMARY VISUALIZATION: Risk-Return Frontier Plot
* X-axis: Risk measure (Max DD for Calmar, Downside Dev for Sortino)
* Y-axis: Return
* Scatter points: strategies
* Point color: Omega ratio (green high, red low)
* Efficient frontier curve overlay
* Reference lines: risk-free rate, market benchmark
* Tooltip: all three ratios + return + risk
SECONDARY OUTPUTS:
Strategy Efficiency Leaderboard:
Rank	Strategy	Return	Calmar	Sortino	Omega	Overall Score
1	L/S Equity	14.2%	2.3	1.8	1.4	✓ Excellent
2	Mean Rev	11.8%	1.9	1.6	1.3	✓ Good
3	Trend	15.6%	1.2	1.1	1.1	⚠ Moderate
4	Vol Arb	8.3%	0.7	0.9	0.8	✗ Poor
Overall Score = weighted average of normalized ratios
Ratio Comparison Radar Chart:
* Pentagon shape: 5 axes (Return, Calmar, Sortino, Omega, Sharpe)
* Separate colored overlay per strategy
* Larger area = better performance
* Industry benchmark outline (gray)
Capital Allocation Recommendation Table:
┌──────────────────────────────────────────────────┐
│ RECOMMENDED ALLOCATION (100% capital)            │
│                                                  │
│ Strategy          Weight    Rationale           │
│ L/S Equity         45%      Best risk-adjusted  │
│ Mean Rev           35%      Diversifying        │
│ Trend              20%      Upside potential    │
│ Vol Arb             0%      Below threshold     │
│                                                  │
│ Expected Portfolio Calmar: 2.1                   │
│ Expected Portfolio Sortino: 1.7                  │
└──────────────────────────────────────────────────┘
Ratio Percentile Ranks (vs Historical):
Ratio	Current	25th %	Median	75th %	Percentile Rank
Calmar	2.3	1.2	1.8	2.4	72nd
Sortino	1.8	1.0	1.4	1.9	68th
Omega	1.4	1.1	1.3	1.6	55th
UI Layout:
* Top: Strategy selector (multi-select), benchmark selector
* Left (50%): Risk-return frontier plot
* Right (50%):
    * Top: Leaderboard table
    * Middle: Radar chart
    * Bottom: Allocation recommendation

GROUP 5: TAIL RISK & EXTREME LOSS
Purpose: Prevent fund-killing events.

5.1 Jarque-Bera Test
Mathematical Logic:
* Tests null hypothesis: distribution is normal
* JB = (n/6) * [S² + (K-3)²/4]
* S = skewness, K = kurtosis
* Test statistic follows χ²(2) distribution
* Reject null if JB > critical value (5.99 at 5%)
* Normality assumption violations invalidate VaR/Sharpe
Input Requirements:
* Return distribution (minimum 100 observations)
* Significance level (default 5%)
Output Specifications:
PRIMARY VISUALIZATION: Distribution Comparison Chart
* Histogram: actual return distribution (bars)
* Overlay: fitted normal distribution curve (red dashed line)
* Overlay: actual kernel density estimate (blue solid line)
* Shaded tails: returns beyond ±2σ
* Annotation: skewness, kurtosis values
* Vertical line: mean
SECONDARY OUTPUTS:
Normality Test Results Panel:
┌──────────────────────────────────────────────┐
│ ✗ NORMALITY REJECTED                         │
│                                              │
│ Jarque-Bera Statistic: 45.3                  │
│ P-Value: < 0.001                             │
│ Critical Value (5%): 5.99                    │
│                                              │
│ Skewness: -0.42 (left tail heavier)         │
│ Excess Kurtosis: +2.8 (fat tails)           │
│                                              │
│ ⚠ WARNING: Gaussian VaR is UNRELIABLE       │
│   Use EVT or historical VaR instead          │
└──────────────────────────────────────────────┘
Distribution Moments Table:
Statistic	Actual	Normal Equivalent	Deviation
Mean	0.08%	0.08%	-
Std Dev	1.2%	1.2%	-
Skewness	-0.42	0.00	✗ Negative skew
Kurtosis	5.8	3.0	✗ Fat tails
Q-Q Plot (Quantile-Quantile):
* X-axis: Theoretical normal quantiles
* Y-axis: Sample quantiles
* Scatter points: actual data
* 45-degree reference line (perfect normality)
* Deviation from line shows non-normality
* Tail regions highlighted
UI Layout:
* Top: Strategy selector, date range
* Left (60%): Distribution comparison chart (large)
* Right (40%):
    * Top: Test results panel
    * Middle: Moments table
    * Bottom: Q-Q plot

5.2 Tail Risk Analysis
Mathematical Logic:
* Focus on worst X% of returns (e.g., bottom 5%)
* Conditional Value at Risk (CVaR): expected loss beyond VaR
* Tail probability: P(Return < threshold)
* Tail severity: average return in worst percentile
* Compare actual tail vs theoretical normal tail
Input Requirements:
* Return distribution
* Tail percentile (default 5%)
* Optional: loss threshold (e.g., -2%)
Output Specifications:
PRIMARY VISUALIZATION: Tail Distribution Zoom
* Histogram: focused only on left tail (worst 10% of returns)
* X-axis: Return bins (only negative)
* Y-axis: Frequency
* Color gradient: darker red = more extreme losses
* Overlay: exponential fit to tail
* Annotation: VaR and CVaR lines (vertical)
SECONDARY OUTPUTS:
Extreme Loss Probability Table:
Loss Threshold	Probability	Expected Frequency	Observed Count
< -1%	28.3%	71 days/year	68 days
< -2%	12.4%	31 days/year	35 days
< -3%	4.7%	12 days/year	18 days ⚠
< -5%	1.2%	3 days/year	6 days ⚠
VaR and CVaR Summary:
┌──────────────────────────────────────────────┐
│ TAIL RISK MEASURES (95% confidence)          │
│                                              │
│ Value at Risk (VaR):                         │
│   Historical: -2.8%                          │
│   Parametric: -2.1%                          │
│   ⚠ Parametric underestimates by 33%        │
│                                              │
│ Conditional VaR (CVaR):                      │
│   Expected loss beyond VaR: -4.2%            │
│   Worst observed: -7.8%                      │
└──────────────────────────────────────────────┘
Tail Severity vs Normal Comparison Chart:
* Two side-by-side histograms:
    * Left: "Actual Tail"
    * Right: "Expected (Normal)"
* Same X-axis scale
* Visual comparison of tail thickness
Stress Loss Scenario Table:
Scenario	Return	Probability	Portfolio Impact ($100K)
Bad Day	-3%	4.7%	-$3,000
Very Bad Day	-5%	1.2%	-$5,000
Disaster Day	-7%	0.3%	-$7,000
Black Swan	-10%+	0.1%	-$10,000+
UI Layout:
* Top: Strategy selector, tail percentile slider
* Left (50%): Tail distribution zoom
* Center (25%): Loss probability table + VaR/CVaR summary
* Right (25%): Tail comparison chart + stress scenarios

5.3 GPD (Generalized Pareto Distribution) - Extreme Value Theory
Mathematical Logic:
* EVT: model tail of distribution separately
* Peaks Over Threshold (POT) method
* GPD fit: F(x) = 1 - (1 + ξx/σ)^(-1/ξ)
* ξ = shape parameter (tail heaviness)
* σ = scale parameter
* Estimate extreme quantiles (99%, 99.9%)
* Calculate tail VaR and CVaR
Input Requirements:
* Return distribution
* Threshold for defining "extreme" (default 95th percentile)
* Confidence level for VaR (default 99%)
Output Specifications:
PRIMARY VISUALIZATION: GPD Tail Fit Chart
* Scatter plot: exceedances over threshold (blue points)
* Overlay: fitted GPD curve (red line)
* X-axis: Exceedance magnitude
* Y-axis: Probability (log scale)
* Confidence bands (±2 std errors)
* Annotation: ξ (shape) and σ (scale) parameters
* Extrapolation region shaded (beyond observed data)
SECONDARY OUTPUTS:
GPD Parameters Panel:
┌──────────────────────────────────────────────┐
│ EXTREME VALUE THEORY PARAMETERS              │
│                                              │
│ Threshold: -2.5% (95th percentile)          │
│ Number of exceedances: 23                    │
│                                              │
│ Shape (ξ): 0.32                              │
│   → Heavy-tailed distribution (ξ > 0)       │
│   → Tail is HEAVIER than exponential        │
│                                              │
│ Scale (σ): 1.1%                              │
│                                              │
│ ⚠ FRAGILITY WARNING: Positive ξ indicates   │
│   unlimited loss potential in tail           │
└──────────────────────────────────────────────┘
Extreme Loss Estimates Table:
Confidence Level	Tail VaR	Tail CVaR	vs Gaussian VaR
95%	-3.2%	-4.1%	+15% worse
99%	-5.8%	-7.3%	+42% worse
99.9%	-9.7%	-12.1%	+89% worse
Tail Loss Distribution Chart:
* Line chart: X-axis = loss magnitude, Y-axis = probability
* Multiple lines:
    * Historical tail (blue)
    * GPD fitted tail (red)
    * Gaussian tail (gray, for comparison)
* Log scale on Y-axis
* Shows GPD predicts more extreme losses than Gaussian
Expected Extreme Loss Table:
┌──────────────────────────────────────────────┐
│ EXPECTED WORST OUTCOMES                      │
│                                              │
│ Period        Expected Worst Loss            │
│ 1 Year        -5.8% (99% confidence)         │
│ 5 Years       -8.4%                          │
│ 10 Years      -10.1%                         │
│                                              │
│ On $100K investment:                         │
│   1-Year worst: -$5,800                      │
│   10-Year worst: -$10,100                    │
└──────────────────────────────────────────────┘
Diagnostic Plots (2x2 grid):
1. Probability-Probability plot (GPD vs empirical)
2. Quantile-Quantile plot
3. Return level plot (predicted vs observed)
4. Density plot (GPD vs histogram)
UI Layout:
* Top: Strategy selector, threshold slider, confidence level
* Left (50%): GPD tail fit chart (large)
* Right (50%):
    * Top: Parameters panel
    * Middle: Extreme loss estimates table + comparison chart
    * Bottom: Expected loss table
* Bottom drawer (collapsible): Diagnostic plots grid

GROUP 6: ROBUSTNESS & LUCK FILTER
Purpose: Separate skill from randomness.

6.1 Bootstrap Simulation
Mathematical Logic:
* Resample returns with replacement (1000+ iterations)
* Generate distribution of performance metrics (Sharpe, return, drawdown)
* Calculate confidence intervals (5th, 50th, 95th percentiles)
* Compare actual performance to bootstrap distribution
* Percentile rank: where actual falls in distribution
* If actual < 25th percentile → likely lucky
Input Requirements:
* Strategy returns
* Number of bootstrap samples (default 1000)
* Metrics to test (Sharpe, Calmar, return, max DD)
Output Specifications:
PRIMARY VISUALIZATION: Bootstrap Distribution Histogram
* Histogram: bootstrapped Sharpe ratios (or selected metric)
* X-axis: Metric value
* Y-axis: Frequency
* Vertical line: actual observed metric (bold red)
* Shaded regions:
    * Dark gray: 5th-95th percentile (90% confidence)
    * Light gray: full distribution
* Annotation: percentile rank of actual
* Overlay: fitted normal curve (dotted)
SECONDARY OUTPUTS:
Confidence Intervals Table:
Metric	Actual	5th %	25th %	Median	75th %	95th %	Percentile Rank
Sharpe	1.45	0.82	1.12	1.38	1.67	2.01	58th ✓
Annual Return	12.3%	6.1%	9.2%	11.8%	14.5%	17.9%	62nd ✓
Max DD	-18.2%	-12.4%	-16.8%	-19.3%	-22.1%	-27.6%	48th ✓
Calmar	2.1	1.2	1.7	2.0	2.3	2.8	55th ✓
Skill vs Luck Classification Panel:
┌──────────────────────────────────────────────┐
│ ✓ PERFORMANCE IS ROBUST                      │
│                                              │
│ Sharpe ratio percentile: 58th               │
│ Return percentile: 62nd                      │
│                                              │
│ INTERPRETATION:                              │
│   Performance is near median of random       │
│   resamples. This suggests GENUINE EDGE,     │
│   not luck. Strategy is repeatable.          │
│                                              │
│ ⚠ If percentile > 90th: Likely overfitted   │
│ ⚠ If percentile < 25th: Likely lucky        │
└──────────────────────────────────────────────┘
Bootstrap Metric Comparison (Multi-Panel):
* 2x2 grid of histograms, one per metric
* Same format as primary viz
* Allows side-by-side comparison
Stability Over Time Chart:
* Line chart: rolling bootstrap percentile rank
* X-axis: Time
* Y-axis: Percentile rank (0-100)
* Reference lines at 25th, 50th, 75th percentiles
* Shows if strategy degraded over time
Robustness Score Summary:
OVERALL ROBUSTNESS SCORE: 87/100

Based on:
✓ Sharpe within 25-75 percentile
✓ Return consistent across resamples
✓ Low variance in bootstrap outcomes
✓ No extreme outlier dependence
UI Layout:
* Top: Strategy selector, metric selector (dropdown), bootstrap iterations
* Left (60%): Primary bootstrap histogram (large)
* Right (40%):
    * Top: Confidence intervals table
    * Middle: Skill vs luck panel
    * Bottom: Robustness score summary
* Bottom: Multi-panel comparison (expandable)

GROUP 9: SIGNAL QUALITY
Purpose: Kill bad alpha sources.

9.1 Information Coefficient (IC)
Mathematical Logic:
* IC = correlation between signal and forward returns
* Rank IC: Spearman correlation (rank-based, robust to outliers)
* Pearson IC: Linear correlation (sensitive to outliers)
* Calculate IC at each time period
* Rolling IC: measure stability over time
* T-stat: test if IC significantly different from zero
Input Requirements:
* Signal values (can be continuous or ranks)
* Forward returns (1-day, 5-day, etc.)
* Optional: rolling window for stability (default 60 periods)
Output Specifications:
PRIMARY VISUALIZATION: IC Distribution Histogram
* Histogram: IC values across all time periods
* X-axis: IC value (-1 to +1)
* Y-axis: Frequency
* Vertical line: mean IC (bold)
* Shaded region: ±1 std dev
* Color: green (positive IC), red (negative IC)
* Annotation: mean IC, t-stat, p-value, hit rate
SECONDARY OUTPUTS:
Signal Effectiveness Table:
┌──────────────────────────────────────────────┐
│ SIGNAL: Momentum 20d                         │
│ TARGET: SPY 1-day forward return             │
│                                              │
│ Mean IC: 0.042                               │
│ Std Dev: 0.18                                │
│ T-Statistic: 3.47                            │
│ P-Value: 0.0006                              │
│                                              │
│ IC > 0 (hit rate): 58%                       │
│ IC < 0 (miss rate): 42%                      │
│                                              │
│ ✓ SIGNAL HAS PREDICTIVE POWER               │
│   Statistically significant at 5% level      │
└──────────────────────────────────────────────┘
Rolling IC Chart:
* Line chart: IC over time
* X-axis: Date
* Y-axis: IC value
* Reference line: zero
* Shaded band: ±1 std error
* Color: green above zero, red below
* Annotation: regime breaks (where IC flips sign for >20 periods)
IC by Forward Horizon Table:
Forward Period	Mean IC	T-Stat	P-Value	Status
1 Day	0.042	3.47	0.001	✓ Significant
5 Days	0.038	2.91	0.004	✓ Significant
20 Days	0.015	1.23	0.219	✗ Not Significant
Keep or Kill Decision Panel:
┌──────────────────────────────────────────────┐
│ ✓ KEEP SIGNAL                                │
│                                              │
│ Criteria:                                    │
│   ✓ Mean IC > 0.03                           │
│   ✓ T-Stat > 2.0                             │
│   ✓ Hit rate > 55%                           │
│   ✓ Stable over rolling windows              │
│                                              │
│ RECOMMENDED USAGE:                           │
│   Forward horizon: 1-5 days                  │
│   Confidence: MODERATE                       │
└──────────────────────────────────────────────┘
IC Stability Heatmap:
* Rows: Rolling time windows
* Columns: Forward horizons (1d, 5d, 20d)
* Cell color: IC value (green positive, red negative)
* Shows if signal degrades over time or across horizons
UI Layout:
* Top: Signal selector, target asset, forward horizon
* Left (50%): IC distribution histogram
* Center (25%):
    * Top: Effectiveness table
    * Bottom: IC by horizon table
* Right (25%):
    * Top: Keep/kill decision panel
    * Bottom: Rolling IC chart

GROUP 10: MARKET BREADTH
Purpose: Confirm or reject market moves.

10.1 McClellan Oscillator
Mathematical Logic:
* A-D = (Advancing issues - Declining issues) daily
* EMA_short = 19-day EMA of A-D
* EMA_long = 39-day EMA of A-D
* McClellan Oscillator = EMA_short - EMA_long
* Positive: short-term bullish participation
* Negative: short-term bearish participation
* Divergence from price = warning signal
Input Requirements:
* Advance-decline data (daily advancing and declining stock counts)
* Optional: market index (SPY, etc.) for divergence analysis
Output Specifications:
PRIMARY VISUALIZATION: McClellan Oscillator Chart
* Dual-pane chart:
    * Top pane: Market index price (line chart)
    * Bottom pane: McClellan Oscillator (bar chart)
* X-axis: Time (synchronized)
* Oscillator bars:
    * Green: positive (above zero)
    * Red: negative (below zero)
    * Bar height = magnitude
* Zero line (horizontal)
* Reference lines: +50, -50 (overbought/oversold)
* Divergence annotations: circles where price and oscillator diverge
SECONDARY OUTPUTS:
Market Participation State Panel:
┌──────────────────────────────────────────────┐
│ CURRENT STATE: BULLISH BREADTH               │
│                                              │
│ McClellan Oscillator: +67                    │
│ Interpretation: Strong positive momentum     │
│                                              │
│ 19-day EMA A-D: +245                         │
│ 39-day EMA A-D: +178                         │
│                                              │
│ ✓ BREADTH CONFIRMS PRICE RALLY              │
│   Most stocks participating in uptrend       │
└──────────────────────────────────────────────┘
Regime Classification Table:
Oscillator Range	State	Current	Meaning
> +100	Extreme Bullish		Potentially overbought
+50 to +100	Strong Bullish	✓	Healthy rally
0 to +50	Mild Bullish		Weak rally
0 to -50	Mild Bearish		Weak decline
-50 to -100	Strong Bearish		Healthy decline
< -100	Extreme Bearish		Potentially oversold
Divergence Alert Table:
Date	Price Action	Oscillator Action	Divergence Type	Outcome
2024-11-15	Higher high	Lower high	⚠ Bearish	Pending
2024-09-20	Lower low	Higher low	✓ Bullish	Rally followed
Breadth Statistics:
Current A-D Line: +245
10-day average: +198
Advancing issues: 68%
Declining issues: 32%
UI Layout:
* Top: Market selector (SPY/QQQ/etc.), date range
* Center (80%): Dual-pane price + oscillator chart (full width)
* Right (20%):
    * Top: Participation state panel
    * Middle: Regime table
    * Bottom: Breadth statistics

10.2 McClellan Summation Index
Mathematical Logic:
* Summation Index = Cumulative sum of McClellan Oscillator
* Running total of daily oscillator values
* Measures long-term market participation health
* Rising summation = sustained breadth strength
* Falling summation = eroding breadth
* Absolute level matters: > +1000 bullish, < -1000 bearish
Input Requirements:
* McClellan Oscillator values (from 10.1)
* Historical baseline for comparison
Output Specifications:
PRIMARY VISUALIZATION: Summation Index Chart
* Dual-pane chart:
    * Top pane: Market index price
    * Bottom pane: McClellan Summation Index (area chart)
* X-axis: Time (synchronized)
* Summation area:
    * Green fill: above zero
    * Red fill: below zero
* Reference lines: +1000, 0, -1000
* Trend line overlay (linear regression)
SECONDARY OUTPUTS:
Long-Term Breadth Health Panel:
┌──────────────────────────────────────────────┐
│ LONG-TERM MARKET HEALTH: STRONG              │
│                                              │
│ Current Summation: +1,247                    │
│ 90-day change: +423                          │
│ Trend: ✓ Rising                              │
│                                              │
│ INTERPRETATION:                              │
│   Sustained broad participation in rally.    │
│   Market advance is HEALTHY and backed by    │
│   majority of stocks.                        │
└──────────────────────────────────────────────┘
Risk-On / Risk-Off Regime Table:
Summation Range	Regime	Current	Implication
> +1500	Extreme Risk-On		Late-stage rally
+500 to +1500	Risk-On	✓	Healthy bullish
-500 to +500	Neutral		Mixed conditions
-1500 to -500	Risk-Off		Bearish phase
< -1500	Extreme Risk-Off		Capitulation zone
Breadth Divergence Chart:
* Overlay chart: price (line) vs summation (line, different scale)
* Divergence regions shaded:
    * Yellow: price rising, summation flat/falling (bearish divergence)
    * Blue: price falling, summation rising (bullish divergence)
* Annotation: divergence start dates
Historical Regime Timeline:
* Bar chart: summation index colored by regime
* X-axis: Time (years)
* Y-axis: Summation value
* Color bands: green (risk-on), red (risk-off), gray (neutral)
* Major market events annotated (crashes, rallies)
Breadth Momentum Table:
Current: +1,247
1 month ago: +1,124 (△+123)
3 months ago: +824 (△+423)
6 months ago: +456 (△+791)

Momentum: ACCELERATING
UI Layout:
* Top: Market selector, date range
* Center (70%): Dual-pane price + summation chart
* Right (30%):
    * Top: Breadth health panel
    * Middle: Regime table
    * Bottom: Momentum table
* Bottom (expandable): Divergence chart + historical timeline

GLOBAL UI SPECIFICATIONS
Color Palette
* Pass/Good/Bullish: #10b981 (green)
* Fail/Bad/Bearish: #ef4444 (red)
* Warning/Caution: #f59e0b (amber)
* Neutral/Info: #3b82f6 (blue)
* Background: #111827 (dark gray) for charts, #ffffff (white) for tables
* Text: #1f2937 (dark gray) on light, #f9fafb (light gray) on dark
* Grid lines: #d1d5db (light gray), subtle
Typography
* Headers: 16-20px, bold, sans-serif
* Body: 14px, regular, sans-serif
* Table numbers: 13px, monospace (for alignment)
* Chart labels: 12px, sans-serif
Interactive Elements
* Hover states: Brighten by 10%, show detailed tooltip
* Tooltips: White background, 1px gray border, drop shadow, max 250px wide
* Buttons: Rounded corners (4px), solid fill, white text, hover = darken 10%
* Dropdowns: Native select styling, or custom with clear borders
* Sliders: Clear track, large thumb, show current value label
Chart Standards
* Axes: Always labeled with units
* Legends: Top-right or bottom, clear icons
* Tooltips: Show on hover, include date/value/interpretation
* Zoom/Pan: Enabled for time series charts
* Export: Every chart has download icon (PNG/SVG)
Table Standards
* Headers: Bold, bottom border, sortable (↑↓ icons)
* Rows: Zebra striping (alternating light gray)
* Numbers: Right-aligned, monospace font
* Status icons: ✓✗⚠ℹ clearly visible
* Scrollable: If > 10 rows, fixed header
Responsiveness
* Minimum width: 1280px (not mobile-optimized)
* Optimal: 1920px+ (multi-monitor setups)
* Layout: Collapsible sidebars if space constrained
* Font scaling: Respect browser zoom

CONSTRAINTS & OPTIMIZATION
Performance Constraints
* Initial load: All features lazy-load; only active section loads data
* Chart rendering: Use canvas for >1000 data points, SVG for <1000
* Table pagination: Max 50 rows visible, virtualize if more
* Computation: Heavy calculations (bootstrap, VAR) run in web workers
* Caching: Cache computed results for 5 minutes to avoid recalculation
Data Validation
* Minimum observations: Flag if <100 data points for statistical tests
* Missing data: Show warnings, interpolate only if <5% missing
* Outliers: Flag extreme values (>5σ) but don't auto-remove
* Date alignment: Automatically align multi-asset data to common dates
User Guidance
* Tooltips: Every metric has ⓘ icon with explanation
* Warnings: Yellow banner if data quality is poor
* Errors: Red banner if calculation fails, suggest fixes
* Interpretation text: Each output includes plain-English guidance
Accessibility
* Color blindness: Use patterns/shapes in addition to color
* Keyboard navigation: Tab through controls, Enter to submit
* Screen readers: Alt text on charts, ARIA labels on controls
Export Capabilities
* Charts: PNG, SVG, PDF
* Tables: CSV, Excel
* Reports: Generate PDF summary of all analyses in section
* Data: Export raw computation results as JSON

BUILD THIS
You are now building the Research Labs application using React. Create a fully functional, professional-grade interface that implements every feature detailed above.
Critical requirements:
1. Start with the navigation structure — allow users to switch between sections
2. Implement at least 3 complete features from different groups to demonstrate variety
3. Every feature must include:
    * Proper controls (selectors, sliders, buttons)
    * Primary visualization (chart/heatmap)
    * Secondary outputs (tables, panels)
    * Professional styling matching specifications
4. Use realistic sample data — generate plausible financial time series
5. Charts must be **interactive
** (tooltips, hover effects) 6. No placeholder content — every output must show real computed results 7. Use Recharts for charting, Tailwind for styling 8. Dense information layout — this is professional desktop software
Begin with the application shell and implement the most impactful features first. Make it look like software that a quantitative analyst would actually use.