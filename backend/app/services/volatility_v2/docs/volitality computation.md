I'll read the skills first, then build this wall-to-wall.

Let me make sure I understand: you want the **Volatility Intelligence Module** specified at the same mathematical depth as the Factor Intelligence Module example — every formula, every step, every input/output, end-to-end, for all 9 volatility features. The Factor module is just the format template.

Let me build this now.

---

# QUANT360 — VOLATILITY INTELLIGENCE MODULE

## Complete Mathematical and Computational Specification

---

## FEATURE 1 — MULTI-ESTIMATOR DAILY VOLATILITY ENGINE

### What you are building mathematically

A system that computes five theoretically distinct volatility estimators simultaneously from daily OHLCV data, formally tests which estimator best forecasts future realized variance for a given asset, and produces a unified efficiency-ranked output with disagreement diagnostics.

---

### Step 1 — Data ingestion and return series construction

For asset i at date t, the raw inputs are: Open Oₜ, High Hₜ, Low Lₜ, Close Cₜ, all in price levels (not log-transformed yet). All five estimators operate on log-price ratios.

Define the following intermediate log-ratio series:

overnight return: uₜ = ln(Oₜ / Cₜ₋₁)

open-to-close return: dₜ = ln(Cₜ / Oₜ)

close-to-close return: rₜ = ln(Cₜ / Cₜ₋₁) = uₜ + dₜ

normalized high: hₜ = ln(Hₜ / Oₜ)

normalized low: lₜ = ln(Lₜ / Oₜ)

These five series are the only raw inputs required for all five estimators. Compute them once and store as the shared input layer.

---

### Step 2 — Close-to-close estimator (CC)

The baseline estimator using only daily closing prices. For a rolling window of M trading days ending at date t:

σ²*CC,t = (1/M) × Σ*{s=t-M+1}^{t} rₛ²

Under the simplifying assumption of zero drift (standard for daily returns):

σ²*CC,t = (1/M) × Σ*{s=t-M+1}^{t} [ln(Cₛ / Cₛ₋₁)]²

Annualized volatility: σ_CC,t^{ann} = √(252 × σ²_CC,t)

This estimator has maximum variance (minimum efficiency) because it discards all information about the intraday price path. Its theoretical relative efficiency compared to the true instantaneous variance is 1.0 (the baseline). Everything else is measured relative to it.

For window M, the asymptotic standard error of σ²_CC,t under the assumption of i.i.d. Gaussian returns:

SE(σ²_CC) = σ²_CC × √(2/(M-1))

This standard error is used later in the Diebold-Mariano test to construct the appropriate loss differential variance.

---

### Step 3 — Parkinson estimator (PARK)

Uses the daily high-low range. Under geometric Brownian motion with zero drift and no overnight gaps:

σ²*PARK,t = (1 / (4M ln 2)) × Σ*{s=t-M+1}^{t} [ln(Hₛ / Lₛ)]²

The constant 4 ln 2 ≈ 2.773 is the theoretical correction factor that makes the estimator unbiased under GBM. This can be derived: if Xₜ ~ N(0, σ²) then E[max Xₜ - min Xₜ]² = 4σ² ln 2 for a Brownian bridge.

Annualized: σ_PARK,t^{ann} = √(252 × σ²_PARK,t)

Theoretical relative efficiency vs. CC: approximately 4.0 under GBM (uses 4× as much statistical information per observation as the close-to-close). Empirically ranges from 2.5 to 5.0 depending on the asset's intraday microstructure.

Bias correction for discrete sampling: the discrete high and low observed over N intraday observations underestimate the true continuous high-low range. The discrete-sampling bias factor (Garman-Klass, 1980) is:

E[ln(H_discrete / L_discrete)] ≈ E[ln(H_continuous / L_continuous)] × (1 - (N)^{-0.5})

For daily data with N ≈ 390 intraday minutes (for equities): the bias is approximately 3.2%. Apply this correction by multiplying σ²_PARK,t by 1 / (1 - 390^{-0.5}) ≈ 1.033.

---

### Step 4 — Garman-Klass estimator (GK)

Adds open and close to the high-low range. The GK estimator simultaneously uses the range (for efficiency) and the close-to-open return (to correct for overnight gaps):

σ²*GK,t = (1/M) × Σ*{s=t-M+1}^{t} [0.5 × (ln(Hₛ/Lₛ))² − (2 ln 2 − 1) × (ln(Cₛ/Oₛ))²]

The constant (2 ln 2 − 1) ≈ 0.386 is derived analytically: it is the coefficient that minimizes the variance of the estimator subject to unbiasedness. It weights the close-to-open squared return negatively because the open-to-close range already contains most of the day's variance information; the closing return is negatively correlated with the range contribution when both are normalized to the same-day path.

Annualized: σ_GK,t^{ann} = √(252 × σ²_GK,t)

Theoretical relative efficiency vs. CC: approximately 7.4 under GBM. This is the most efficient estimator among the first three under ideal conditions (GBM, no drift, no overnight gaps). Its weakness: it is biased when overnight gaps are large relative to intraday moves, because it models the full period from previous close to current close as a single continuous process when it is in fact two separate segments.

---

### Step 5 — Rogers-Satchell estimator (RS)

The first estimator unbiased under nonzero drift. It uses all four prices (O, H, L, C) but does not require an overnight return, making it robust to gap-opens:

σ²*RS,t = (1/M) × Σ*{s=t-M+1}^{t} [ln(Hₛ/Cₛ) × ln(Hₛ/Oₛ) + ln(Lₛ/Cₛ) × ln(Lₛ/Oₛ)]

Derivation insight: the RS estimator is the sum of two products. ln(Hₛ/Cₛ) × ln(Hₛ/Oₛ) captures how far the high exceeded both the close and the open — large values mean the high was a genuine intraday extreme, not merely an artifact of open-to-close direction. Similarly for the low terms. Under GBM with drift μ, E[σ²_RS] = σ² for any μ — drift-unbiased. Under CC: E[σ²_CC] = σ² + μ² (biased by the squared drift term, which is negligible for daily returns over short windows but meaningful over longer windows).

Annualized: σ_RS,t^{ann} = √(252 × σ²_RS,t)

Theoretical relative efficiency vs. CC: approximately 6.2 under GBM. Slightly less efficient than GK in the zero-drift case, but more robust when drift is nonzero.

---

### Step 6 — Yang-Zhang estimator (YZ)

The only estimator unbiased simultaneously under drift, overnight gaps, and discrete sampling. It is a weighted combination of three components:

Component 1 — overnight variance:

σ²*overnight,t = (1/(M-1)) × Σ*{s=t-M+1}^{t} (uₛ − ū)²

where uₛ = ln(Oₛ/Cₛ₋₁) is the overnight log-return and ū = (1/M) Σ uₛ is the sample mean.

Component 2 — Rogers-Satchell intraday variance (from Step 5):

σ²_RS,t (already computed above)

Component 3 — open-to-close variance:

σ²*OC,t = (1/(M-1)) × Σ*{s=t-M+1}^{t} (dₛ − d̄)²

where dₛ = ln(Cₛ/Oₛ) and d̄ = (1/M) Σ dₛ.

Optimal weighting coefficient:

k = 0.34 / (1.34 + (M+1)/(M-1))

For M = 21: k = 0.34 / (1.34 + 22/20) = 0.34 / (1.34 + 1.10) = 0.34 / 2.44 ≈ 0.139

For M = 63: k ≈ 0.34 / (1.34 + 64/62) = 0.34 / 2.372 ≈ 0.143

As M → ∞: k → 0.34 / (1.34 + 1) = 0.34 / 2.34 ≈ 0.145

The Yang-Zhang composite:

σ²_YZ,t = σ²_overnight,t + k × σ²_RS,t + (1-k) × σ²_OC,t

Annualized: σ_YZ,t^{ann} = √(252 × σ²_YZ,t)

Theoretical relative efficiency vs. CC: approximately 14.0 under GBM. The highest of all five estimators. It achieves this by extracting variance information from three independent segments of the daily price path: the overnight gap, the intraday range (via RS), and the open-to-close return. Each segment contributes independent information; the k coefficient is the exact weight that minimizes the combined estimator's variance.

When overnight gaps should be excluded (e.g., for 24-hour FX markets where there is no genuine gap):

Set σ²_overnight,t = 0 and set k = 0, reducing YZ to the RS estimator. This is the correct specification for any asset without a genuine market close.

---

### Step 7 — Rolling window computation across all five estimators

For each estimator E ∈ {CC, PARK, GK, RS, YZ} and each window M ∈ {10, 21, 42, 63, 126, 252}:

Compute σ²_E,M,t for all dates t from the first date where M observations are available through the most recent date T.

The output is a 5 × 6 matrix of rolling vol time series, each of length T - M_max + 1.

Annualize: multiply each σ²_E,M,t by the annualization factor A:

A = 252 (standard equity convention)
A = 365 (for crypto or FX where markets trade continuously)
A = user-defined N_trading_days_per_year

Annualized vol: σ_E,M,t^{ann} = √(A × σ²_E,M,t)

Percentile rank of current vol within history: for each estimator E and window M:

Pct_E,M,T = #{t < T : σ_E,M,t > σ_E,M,T} / (T - M) × 100

This gives the current vol reading as a percentile of its own distribution — the "vol-of-vol" positioning signal.

---

### Step 8 — Estimator efficiency table (analytical)

The theoretical relative efficiency of each estimator vs. CC under GBM:

RE_CC = 1.00 (baseline by definition)

RE_PARK = 1 / (4 ln 2) ≈ 1 / 2.773... wait — the efficiency gain comes from the ratio of the variance of the CC estimator to the variance of each alternative estimator. The theoretical values (derived by Parkinson, 1980; Garman and Klass, 1980; Yang and Zhang, 2000) are:

RE_CC = 1.0
RE_PARK ≈ 4.0 to 5.0 (exactly: 1/(4 ln 2) × π ≈ 1.13... — the Parkinson correction factor gives efficiency gain ≈ 4 times fewer observations needed to achieve the same MSE)
RE_GK ≈ 6.2 to 7.4
RE_RS ≈ 6.2
RE_YZ ≈ 10.0 to 14.0

More precisely, the relative efficiency is defined as:

RE_E = Var(σ²_CC) / Var(σ²_E)

Under GBM: Var(σ²_CC) = 2σ⁴/M. For the Parkinson estimator: Var(σ²_PARK) = σ⁴ × (π²/6 - 1) / (4M ln²2) ... which simplifies to approximately σ⁴ × 0.407 / M. Therefore RE_PARK = (2/M) / (0.407/M) = 4.91.

Display the RE values as a color-coded table: green for RE ≥ 3.0, amber for RE between 1.5 and 3.0, red for RE < 1.5 (which should never occur by construction since CC is the worst).

---

### Step 9 — Diebold-Mariano forecasting tournament

The DM test determines which estimator best forecasts future realized variance, not which is most efficient analytically. The proxy for true realized variance is the squared 5-minute return sum (unavailable from daily data) or, using only daily data: the rolling 5-day squared close-to-close return as the "true" variance proxy.

Define the proxy realized variance: RV*t^{proxy} = Σ*{s=t}^{t+4} r²ₛ (5-day sum of squared daily returns, forward-looking)

For each pair of estimators (E₁, E₂), define the loss differential at each date t:

d*t = L(σ²*{E1,t}, RV*{t+1}^{proxy}) − L(σ²*{E2,t}, RV\_{t+1}^{proxy})

Under quadratic loss: L(σ², RV) = (σ² − RV)²

Under QLIKE loss (preferred for variance forecasting — robust to outliers and has superior statistical properties): L(σ², RV) = RV/σ² − ln(RV/σ²) − 1

The QLIKE loss is the correct loss function when the target is variance forecasting (as opposed to volatility forecasting in levels), because it is the quasi-likelihood implied by the log-normal distribution of realized variance.

The DM test statistic:

DM = d̄ / √(Ŝ_d / T)

where d̄ = (1/T) Σ_t d_t is the mean loss differential and Ŝ_d is the long-run variance of d_t estimated by the Newey-West HAC estimator with bandwidth h = int(T^{1/3}):

Ŝ*d = γ̂₀ + 2 Σ*{l=1}^{h} (1 − l/(h+1)) × γ̂_l

where γ̂*l = (1/T) Σ*{t=l+1}^{T} (d*t − d̄)(d*{t-l} − d̄) is the sample autocovariance at lag l.

Under the null of equal forecast accuracy: DM ~ N(0,1) asymptotically.

The two-sided p-value: p = 2 × (1 − Φ(|DM|))

Reject the null (E₁ significantly outperforms E₂) when p < 0.05.

Number of pairs tested: C(5,2) = 10. Apply Bonferroni correction: reject when p < 0.05/10 = 0.005 for family-wise error rate control.

Execute this tournament on a rolling 252-day out-of-sample window, updated daily. The winner at each date is the estimator not rejected by any other at the Bonferroni-corrected level — or if multiple estimators survive, the one with the lowest average QLIKE loss.

---

### Step 10 — Estimator agreement index

The pairwise Pearson correlation matrix of the five estimator time series over the trailing 21-day window:

ρ*{E1,E2,t} = Corr(σ*{E1,t-20:t}, σ\_{E2,t-20:t})

Average pairwise correlation (the agreement index):

Agree*t = (2 / (5×4)) × Σ*{E1 < E2} ρ\_{E1,E2,t}

This is the mean of the C(5,2) = 10 off-diagonal correlations in the 5×5 correlation matrix.

Agree_t → 1: all five estimators are moving in lockstep — high confidence signal about true volatility direction.

Agree_t → 0 or negative: structural disagreement — estimators are diverging, typically because gap-opens, extreme ranges, or microstructure issues are causing some estimators to spike while others do not. This is itself a risk signal: uncertainty about the true volatility regime.

Alert threshold: Agree_t < 0.50 triggers an estimator disagreement flag with a tooltip identifying which estimator pair has the lowest pairwise correlation (the primary source of disagreement).

---

### Outputs

**Five-estimator comparison chart:** All five σ_E,t^{ann} plotted simultaneously on one axis, color-coded. A shaded band spans from min_E(σ_E,t) to max_E(σ_E,t) at each date — wide band = estimator disagreement, narrow band = consensus. The shaded band's width is the primary visual indicator: it widens around gap-open events, earnings announcements, and volatility regime transitions.

**Estimator efficiency table:** Five rows, one per estimator. Columns: theoretical RE vs. CC (analytical), empirical RE vs. CC (measured as ratio of sample variances of the two estimator time series over full history), DM tournament win/loss record (how many of the 9 pairwise tests the estimator wins), and current annualized vol reading. Color: green for RE ≥ 3×, amber for RE between 1.5× and 3×, red for RE < 1.5× (baseline only).

**Diebold-Mariano tournament matrix:** 5×5 heatmap where cell (E1, E2) shows the DM statistic for E1 vs. E2 under QLIKE loss. Positive values (green) = E1 forecasts better. Negative values (red) = E2 forecasts better. The winning estimator for this asset and window is highlighted in bold.

**Estimator agreement index time series:** Daily Agree_t plotted over the full history. Horizontal dashed line at 0.50 (the alert threshold). Red dot markers on dates where agreement fell below the threshold; these cluster around crisis events and validate the diagnostic.

**Annualized vol panel — five dials:** Five circular gauge charts, one per estimator, each showing the current annualized vol as a percentile of the trailing 252-day, 5-year, and full-history distribution. Three concentric rings per dial correspond to the three lookback windows. Colors: green < 30th percentile, amber 30th–70th, red 70th–90th, deep red > 90th.

**Cross-asset ranked panel (panel mode):** When N assets are active: N-row table ranked by descending current σ_YZ^{ann}. Columns: asset name, σ_CC, σ_PARK, σ_GK, σ_RS, σ_YZ (all annualized), DM winner estimator for each asset, 10-year vol percentile. Color-coded by percentile tier per row.

---

### Data map

| Series                     | Source                   | Ticker / Code                | Frequency |
| -------------------------- | ------------------------ | ---------------------------- | --------- |
| Daily OHLCV (equities)     | Yahoo Finance            | Per ticker (e.g., ^GSPC)     | Daily     |
| Daily OHLCV (FX)           | FRED                     | DEXUSEU, DEXJPUS, DEXUSUK    | Daily     |
| Daily OHLCV (commodities)  | FRED                     | GOLDAMGBD228NLBM, DCOILWTICO | Daily     |
| Exchange trading calendars | Config file per exchange | Static                       | Static    |

---

## FEATURE 2 — GARCH FAMILY SUITE WITH ASYMMETRY, LONG MEMORY, AND DENSITY FORECASTING

### What you are building mathematically

Simultaneous estimation of 20 model-distribution combinations (5 GARCH variants × 4 error distributions), formal model selection via the Model Confidence Set, density forecast evaluation via the Probability Integral Transform, and multi-horizon volatility term structure forecasting.

---

### Step 1 — Return series and initial variance filter

For a daily return series {rₜ}\_{t=1}^T, demean the series:

ε_t = rₜ − μ̂, where μ̂ = (1/T) Σ_t rₜ

Initialize the conditional variance at the sample variance:

σ²₀ = (1/T) Σ_t ε²_t

The initialization matters because the GARCH variance recursion σ²*t = f(σ²*{t-1}, ε\_{t-1}) requires a starting value. Set the first M_burnin = 100 observations as a burn-in period: the log-likelihood is computed only from t = M_burnin + 1 onward, and the burn-in observations serve only to initialize the recursion.

---

### Step 2 — GARCH(1,1) model

Conditional variance equation:

σ²*t = ω + α × ε²*{t-1} + β × σ²\_{t-1}

Parameter constraints for stationarity: ω > 0, α ≥ 0, β ≥ 0, α + β < 1.

Long-run (unconditional) variance: σ²_∞ = ω / (1 − α − β)

The persistence parameter α + β measures how slowly shocks decay. If α + β = 0.98 (typical for daily equity returns), a shock to variance decays to half its magnitude in:

T\_{1/2} = ln(0.5) / ln(α + β) = ln(0.5) / ln(0.98) ≈ 34.3 trading days

Maximum likelihood estimation under Gaussian errors. Log-likelihood:

ℓ(θ; ε₁:T) = −(T/2) ln(2π) − (1/2) Σ\_{t=M+1}^{T} [ln(σ²_t) + ε²_t / σ²_t]

where θ = (ω, α, β) and σ²_t is computed recursively from the parameter values.

Gradient:

∂ℓ/∂θ = (1/2) Σ_t [(ε²_t / σ²_t − 1) × (1/σ²_t) × ∂σ²_t/∂θ]

The recursion for ∂σ²*t/∂ω = 1 + β × ∂σ²*{t-1}/∂ω, ∂σ²*t/∂α = ε²*{t-1} + β × ∂σ²*{t-1}/∂α, ∂σ²_t/∂β = σ²*{t-1} + β × ∂σ²\_{t-1}/∂β

Maximize via L-BFGS-B with analytical gradients. Multiple starting points to avoid local optima: initialize from (ω = σ²_∞ × 0.1, α = 0.1, β = 0.85), (α = 0.05, β = 0.90), and (α = 0.15, β = 0.80). Take the solution with the highest log-likelihood.

---

### Step 3 — EGARCH(1,1) model

Models log-variance to ensure positivity without parameter constraints:

ln(σ²*t) = ω + α × (|z*{t-1}| − E|z|) + γ × z*{t-1} + β × ln(σ²*{t-1})

where z_t = ε_t / σ_t is the standardized innovation.

Under Gaussian errors: E|z| = √(2/π) ≈ 0.7979

The γ parameter captures leverage (asymmetric response): γ < 0 means negative shocks (z\_{t-1} < 0) increase variance more than positive shocks of equal magnitude. This is the Nelson-Black leverage effect.

The total effect of a negative shock (z\_{t-1} = −|z|):

∂ ln(σ²*t) / ∂ε*{t-1}|_{ε<0} = (1/σ_{t-1}) × (α × (−1) + γ) = (1/σ\_{t-1}) × (−α + γ)...

More precisely, for z*{t-1} < 0: the coefficient is (−α + γ)/σ*{t-1} (since |z\_{t-1}| − E|z| has derivative −1 with respect to z for z < 0).

For z*{t-1} > 0: the coefficient is (α + γ)/σ*{t-1}.

The asymmetry ratio: (−α + γ) / (α + γ). For typical equity returns: α ≈ 0.15, γ ≈ −0.10, giving ratio (−0.15 − 0.10) / (0.15 − 0.10) = −0.25 / 0.05 = −5. Negative shocks have 5× the variance impact of positive shocks of equal size.

Log-likelihood: same form as GARCH but with ln(σ²_t) computed from the EGARCH recursion instead of σ²_t.

No parameter constraints needed (positivity guaranteed by the log-variance specification). Stationarity requires |β| < 1.

---

### Step 4 — GJR-GARCH(1,1) model

The Glosten-Jagannathan-Runkle (1993) model adds an asymmetric response to negative shocks via an indicator function:

σ²*t = ω + α × ε²*{t-1} + γ × I*{t-1} × ε²*{t-1} + β × σ²\_{t-1}

where I*{t-1} = 1 if ε*{t-1} < 0 (bad news), I*{t-1} = 0 if ε*{t-1} ≥ 0.

For bad news (ε*{t-1} < 0): the shock coefficient is (α + γ)
For good news (ε*{t-1} ≥ 0): the shock coefficient is α

γ > 0 is the "news impact asymmetry" — the additional variance caused by negative shocks.

Long-run variance: σ²_∞ = ω / (1 − α − β − γ/2), because E[I × ε²] = (1/2) × σ² (by symmetry of the innovation distribution, half of all shocks are negative).

Stationarity constraint: α + β + γ/2 < 1

Parameter constraints: ω > 0, α ≥ 0, β ≥ 0, α + γ ≥ 0 (to prevent negative conditional variance on bad news days).

Log-likelihood: same form as GARCH with σ²_t from the GJR recursion.

---

### Step 5 — APARCH(1,1) model

The Asymmetric Power ARCH model of Ding, Granger, and Engle (1993):

σ^δ*t = ω + α × (|ε*{t-1}| − γ × ε*{t-1})^δ + β × σ^δ*{t-1}

where δ > 0 is the power parameter and γ ∈ (−1, 1) is the asymmetry parameter.

Special cases:
δ = 1, γ = 0: TARCH (Threshold ARCH)
δ = 2, γ = 0: GARCH(1,1)
δ = 2, γ ≠ 0: GJR-GARCH (approximately)
δ free, γ free: APARCH (most general)

The term (|ε*{t-1}| − γ × ε*{t-1}): for ε < 0, this equals |ε|(1 + γ); for ε > 0, this equals |ε|(1 − γ). So γ > 0 amplifies negative shocks, γ < 0 amplifies positive shocks.

Estimated by MLE via numerical optimization. δ is initialized at 1.5 and constrained to (0, 3] to prevent numerical instability. When the user fixes δ = 1: the model reduces to TARCH. When fixed at δ = 2: reduces to GJR-GARCH.

---

### Step 6 — FIGARCH(1,d,1) model

The Fractionally Integrated GARCH model of Baillie, Bollerslev, and Mikkelsen (1996):

(1 − β L) σ²_t = ω + [(1 − β L) − (1 − φ L)(1 − L)^d] ε²_t

where L is the lag operator, d ∈ (0,1) is the fractional integration parameter, and (1 − L)^d is the fractional differencing operator:

(1-L)^d = Σ\_{k=0}^{∞} [Γ(k-d) / (Γ(-d) × Γ(k+1))] × L^k

The binomial expansion coefficients: π_k = Γ(k-d) / (Γ(-d) × Γ(k+1)) for k = 0, 1, 2, ...

π*0 = 1, π_k = π*{k-1} × (k - 1 - d) / k for k ≥ 1

In practice, truncate the infinite expansion at K = 1000 lags. The FIGARCH conditional variance recursion (truncated):

σ²_t = ω/(1-β) + [1 - (1-βL)^{-1}(1-φL)(1-L)^d] ε²_t

≈ ω/(1-β) + Σ*{k=1}^{K} λ_k × ε²*{t-k}

where {λ_k} are the FIGARCH lag coefficients derived from the polynomial expansion. These decay hyperbolically: λ_k ~ k^{d-1} as k → ∞ (for GARCH: λ_k ~ (α+β)^k, geometric decay — much faster than hyperbolic).

The fractional parameter d governs the memory structure:
d = 0: standard GARCH (geometric decay of persistence)
d = 1: IGARCH (integrated GARCH, shocks never die)
0 < d < 0.5: stationary long memory
0.5 ≤ d < 1: nonstationary long memory but mean-reverting

Estimation: the d parameter is estimated by MLE alongside ω, φ, β. The log-likelihood computation is numerically intensive because σ²_t requires the full truncated lag polynomial at each date. Use the `arch` library's FIGARCH class or implement the truncated recursion directly in NumPy with the lag coefficients precomputed.

---

### Step 7 — Four conditional error distributions

Each of the 5 models above is estimated under each of 4 error distributions. Total: 20 model-distribution combinations.

**Distribution 1 — Gaussian:**

z_t ~ N(0, 1)

Log-likelihood contribution at date t: −(1/2)[ln(2π) + ln(σ²_t) + z²_t]

No additional parameters.

**Distribution 2 — Student-t with estimated degrees of freedom ν:**

z*t ~ t*ν (standardized so that Var(z_t) = 1)

The standardized t-distribution density:

f(z | ν) = Γ((ν+1)/2) / [Γ(ν/2) × √(π(ν-2))] × (1 + z²/(ν-2))^{-(ν+1)/2}

Log-likelihood contribution at date t:

ln f(ε_t | σ²_t, ν) = ln Γ((ν+1)/2) − ln Γ(ν/2) − (1/2) ln(π(ν-2)) − (1/2) ln(σ²_t) − ((ν+1)/2) × ln(1 + ε²_t / ((ν-2)σ²_t))

ν is estimated by MLE alongside the GARCH parameters. Constraint: ν > 2 (for finite variance). For daily equity returns, typical estimates: ν ∈ [4, 8].

**Distribution 3 — Generalized Error Distribution (GED):**

f(z | ν) = ν × exp(−(1/2)|z/λ|^ν) / [λ × 2^{1+1/ν} × Γ(1/ν)]

where λ = [2^{-2/ν} × Γ(1/ν) / Γ(3/ν)]^{1/2} is the scale parameter ensuring unit variance.

ν = 2: Gaussian; ν = 1: Laplace (double-exponential); ν → ∞: Uniform. Daily equity returns typically imply ν ∈ [1.2, 1.8], reflecting fatter tails than Gaussian.

**Distribution 4 — Hansen skewed-t (1994):**

f(z | ν, η) = bc × (1 + 1/(ν-2) × ((bz+a)/(1+sign(bz+a)η))²)^{-(ν+1)/2}

where η ∈ (−1, 1) is the skewness parameter, ν > 2 is the degrees of freedom, and the constants a, b, c are functions of η and ν:

a = 4ηc × (ν-2)/(ν-1)
b² = 1 + 3η² − a²
c = Γ((ν+1)/2) / (√(π(ν-2)) × Γ(ν/2))

η > 0: right-skewed (positive skewness); η < 0: left-skewed. Daily equity returns typically show η ∈ (−0.15, 0), slight left skew.

---

### Step 8 — MLE estimation for all 20 combinations

For each of the 20 (model, distribution) combinations, maximize the log-likelihood:

ℓ(θ, φ) = Σ\_{t=M+1}^{T} ln f(ε_t / σ_t | φ) − (1/2) ln(σ²_t)

where θ = GARCH parameters (model-specific), φ = distribution parameters (ν, η as applicable).

Optimization: L-BFGS-B with analytical or numerical gradients (use central differences for the distribution parameters, analytical gradients for the GARCH parameters where tractable). Run 5 starting points per combination to avoid local optima; keep the global maximum.

Compute the Hessian at the optimum (via numerical second differences) to get the covariance matrix of parameter estimates:

Cov(θ̂) ≈ [−∂²ℓ/∂θ∂θ'|_{θ̂}]^{-1}

Standard errors: SE(θ̂*j) = √[Cov(θ̂)]*{jj}

t-statistics: t_j = θ̂_j / SE(θ̂_j)

---

### Step 9 — Model comparison scoreboard

For each of the 20 combinations, compute:

**AIC:** AIC = −2ℓ(θ̂) + 2k, where k = number of parameters

**BIC:** BIC = −2ℓ(θ̂) + k × ln(T)

**RMSE vs. rolling squared return proxy:**

σ²*proxy,t = Σ*{s=t}^{t+20} r²\_{s} / 21 (21-day realized variance proxy, forward-looking)

RMSE_E = √[(1/T) Σ_t (σ²_E,t − σ²_proxy,t)²]

**QLIKE loss:**

QLIKE_E = (1/T) Σ_t [σ²_proxy,t / σ²_E,t − ln(σ²_proxy,t / σ²_E,t) − 1]

The QLIKE loss is preferred over RMSE for variance forecasting because it is the proper scoring rule for the log-normal distribution of conditional variance.

**Model Confidence Set (MCS) — Hansen, Lunde, Nason, 2011:**

The MCS identifies the subset M\* of models that are not significantly outperformed by any other model in the set, at a given confidence level (e.g., 90%).

Algorithm:

1. Initialize M = all 20 models.
2. Compute the loss differential for each pair (i,j): d*{ij,t} = L*{i,t} − L\_{j,t} under QLIKE loss.
3. Compute the test statistic: T*R = max*{i∈M} t*i where t_i = d̄_i / √(Var(d̄_i)) and d̄_i = (1/|M|-1/1) Σ*{j≠i} d̄\_{ij} is model i's average loss differential vs. all other models in the current set.
4. Bootstrap the null distribution of T_R using the stationary bootstrap of Politis and Romano (1994) with block size b = int(T^{1/3}).
5. If T_R exceeds the 90th percentile of the bootstrap null distribution: eliminate the model with the worst average loss (highest d̄_i) from M. Return to step 2.
6. Repeat until T_R does not exceed the critical value. The remaining M\* is the Model Confidence Set.

The MCS membership column in the output: ✓ (in the MCS) or ✗ (eliminated). This is the only statistically honest model comparison: it acknowledges uncertainty about which model is truly best, rather than forcing a false winner.

---

### Step 10 — News impact curve

For the MCS-winning model at the current date:

The news impact curve plots σ²*t as a function of ε*{t-1} holding σ²*{t-1} fixed at its long-run mean σ²*∞:

**GARCH:** NIC(ε) = ω + α × ε² + β × σ²_∞ — symmetric U-shape with minimum at ε = 0.

**GJR-GARCH:**
For ε ≥ 0: NIC(ε) = ω + α × ε² + β × σ²*∞
For ε < 0: NIC(ε) = ω + (α+γ) × ε² + β × σ²*∞
The left arm is steeper than the right arm by factor (α+γ)/α — the asymmetry ratio.

**EGARCH:**
For ε > 0: NIC(ε) = exp[ω + α(|ε|/σ_∞ − E|z|) + γ(ε/σ_∞) + β × ln(σ²_∞)] × σ²*∞^β
For ε < 0: NIC(ε) = exp[ω + α(|ε|/σ*∞ − E|z|) − γ(|ε|/σ*∞) + β × ln(σ²*∞)] × σ²_∞^β
Exponential curvature — the EGARCH NIC curves sharply upward for large negative shocks.

**APARCH:** NIC(ε) = [ω + α(|ε| − γ_A × ε)^δ + β × σ^δ_∞]^{2/δ} where γ_A is the APARCH asymmetry parameter.

Evaluate the NIC on the grid ε ∈ [−3σ_∞, +3σ_∞] with 200 grid points. Display all active model NICs on one plot for direct shape comparison — the shape difference between GARCH's symmetric U and GJR's asymmetric hockey stick is the primary visual communication of the leverage effect.

---

### Step 11 — GARCH-implied volatility term structure

For the winning model, compute the expected annualized vol at each horizon h ∈ {1, 5, 10, 21, 42, 63, 126, 252}:

**For GARCH(1,1):** The h-step-ahead conditional variance forecast has a closed form:

E*t[σ²*{t+h}] = σ²*∞ + (α+β)^{h-1} × (σ²*{t+1} − σ²_∞)

where σ²\_{t+1} = ω + α × ε²_t + β × σ²_t is the one-step-ahead forecast.

Annualized h-day vol forecast: V(h) = √(252 × E*t[σ²*{t+h}])

For h → ∞: V(h) → √(252 × σ²_∞), the long-run unconditional vol.

**For GJR-GARCH:** The term structure requires simulation (no closed form for the asymmetric case). Simulate S = 10,000 paths of {ε*{t+s}}*{s=1}^{h} by drawing innovations from the estimated distribution, propagating the GJR recursion, and averaging the realized variance over each path:

E*t[σ²*{t+h}] ≈ (1/S) Σ*{s=1}^{S} σ²*{t+h}^{(s)}

**For FIGARCH:** The h-step-ahead forecast must account for the long memory. The FIGARCH impulse response of a unit shock to ε²*t on future σ²*{t+h} decays as h^{d-1}, much more slowly than geometric decay. Simulate as for GJR-GARCH with the FIGARCH recursion.

90% simulation confidence bands: for each horizon h, the 5th and 95th percentile of the S simulated h-step-ahead vol forecasts.

Interpretation:
Downward-sloping term structure (V(1) > V(252)): current vol is above long-run mean; regime persistence will pull it down.
Upward-sloping (V(1) < V(252)): current vol is below long-run mean; the market will normalize upward.
Humped (V peaks at intermediate h): transitional state — the model expects a vol spike before mean reversion.

---

### Step 12 — Probability Integral Transform test

For each of the 20 models, compute the PIT series:

u*t = F*{t-1}(ε_t | θ̂)

where F\_{t-1}(· | θ̂) is the estimated conditional CDF of ε_t given information at t-1 and the estimated parameter vector θ̂.

For the Gaussian GARCH: u_t = Φ(ε_t / σ_t)
For the Student-t GARCH: u_t = CDF_t(ε_t / σ_t; ν̂)
(Replace with the appropriate CDF for GED and skewed-t)

Under a correctly specified model: {u_t} ~ i.i.d. Uniform(0,1).

**Uniformity test — Kolmogorov-Smirnov:**

D*T = max*{u ∈ [0,1]} |F_T(u) − u|

where F_T is the empirical CDF of {u_t}. Under the null of Uniform(0,1): D_T × √T → Kolmogorov distribution. p-value from the KS distribution tables.

**Independence test — Ljung-Box on u²_t:**

Q*LB(L) = T(T+2) × Σ*{l=1}^{L} ρ̂²_l(u²) / (T-l)

where ρ̂_l is the sample autocorrelation of u²_t at lag l. Under the null of no autocorrelation: Q_LB ~ χ²_L. Use L = 10.

PIT histogram: bin {u_t} into 20 equal-width bins on [0,1]. Under correctly specified model: all bins should have approximately T/20 observations. The histogram shape reveals model misspecification:

- U-shaped histogram (excess in tails): model underestimates tail probability (fat-tail misspecification).
- Hump at center: model overestimates tail probability (overdispersed conditional density).
- Left-skewed histogram: model underpredicts the probability of negative returns.

---

### Step 13 — Conditional VaR and backtesting

For the winning model, compute daily 99% VaR:

VaR\_{99,t} = μ̂ + σ_t × F^{-1}(0.01)

where F^{-1}(0.01) is the 1st percentile of the estimated conditional distribution. For Gaussian: F^{-1}(0.01) = −2.326. For t*ν: F^{-1}(0.01) = −t*{0.01,ν} × √((ν-2)/ν).

An exceedance at date t: I*t = 1 if r_t < −VaR*{99,t}, else 0.

**Kupiec (1995) unconditional coverage test:**

Expected number of exceedances: E = T × 0.01 (for 99% VaR)

Observed: n = Σ_t I_t

LR_UC = −2 × [n × ln(0.01) + (T-n) × ln(0.99) − n × ln(n/T) − (T-n) × ln(1-n/T)]

Under the null: LR*UC ~ χ²(1). p-value: 1 − CDF*{χ²(1)}(LR_UC).

A statistically valid VaR model has p_UC > 0.05 (cannot reject the null that the coverage rate equals 1%).

**Christoffersen (1998) conditional coverage test:**

This additionally tests whether exceedances are serially independent (i.e., not clustered). Clustered exceptions indicate the model is not adapting to volatility regimes.

Define the transition matrix of the {I_t} sequence:

n*{00} = #{t : I*{t-1}=0, I*t=0}, n*{01} = #{t : I*{t-1}=0, I_t=1}, n*{10} = #{t : I*{t-1}=1, I_t=0}, n*{11} = #{t : I\_{t-1}=1, I_t=1}

π̂₀₁ = n*{01}/(n*{00}+n*{01}): probability of exception given no previous exception
π̂₁₁ = n*{11}/(n*{10}+n*{11}): probability of exception given previous exception

LR_IND = −2 × ln[L_independent / L_Markov]

where L*independent uses a single frequency p̂ = (n*{01}+n\_{11})/T and L_Markov uses π̂₀₁, π̂₁₁.

LR_CC = LR_UC + LR_IND ~ χ²(2) under the joint null of correct unconditional coverage and independence.

A statistically valid VaR model requires both p_UC > 0.05 and p_CC > 0.05.

---

### Outputs

**Model comparison scoreboard:** 20 rows. Columns: model name, distribution, log-likelihood, AIC, BIC, RMSE, QLIKE, MCS membership (✓/✗ at 90% confidence). Winning model bold green. MCS survivors highlighted. All others grayed.

**DM pairwise tournament heatmap:** 20×20 matrix under QLIKE loss. Color: green = row model significantly outperforms column model, red = column model significantly outperforms row model, gray = no significant difference.

**News impact curve:** Overlay of all 5 active model NICs on a single chart with ε on the x-axis (ranging ±3σ_∞) and σ²_t on the y-axis. The x-axis is annotated with historical percentiles of |ε_t|.

**GARCH volatility term structure:** Line chart with horizon h on the x-axis (1 to 252 days), expected annualized vol on the y-axis. Shaded 90% simulation confidence band. Horizontal dashed line at long-run unconditional vol σ_∞^{ann}. The slope of the term structure at the current date is the primary signal.

**Long-memory parameter time series (FIGARCH only):** Rolling 252-day MLE estimate of d over full history. Horizontal bands at d = 0.5 (transition to nonstationarity boundary) and d = 1.0 (IGARCH boundary). A rising d over time is the empirical signature of increasing volatility persistence.

**PIT histogram with KS test:** 20-bin histogram of {u_t} for the winning model. Horizontal reference line at T/20 (expected uniform count). KS statistic and p-value annotated.

**Conditional VaR time series:** Daily −VaR*{99,t} plotted over full history as a shaded band below zero. Actual return r_t plotted as a line. Red dot exceedances where r_t < −VaR*{99,t}. Kupiec p-value and Christoffersen p-value annotated.

**Volatility state gauge:** Single circular dial showing current conditional vol from the winning model as a percentile of its 10-year history. Zone coloring: green < 30th percentile, amber 30th–70th, red 70th–90th, deep red > 90th.

---

### Data map

| Series                                            | Source                          | Ticker / Code | Frequency |
| ------------------------------------------------- | ------------------------------- | ------------- | --------- |
| Daily closing returns                             | Yahoo Finance / Stooq / FRED    | Per ticker    | Daily     |
| Historical price series (10+ years)               | Same                            | Same          | Daily     |
| Realized variance proxy (rolling squared returns) | Computed internally from prices | —             | Daily     |

---

## FEATURE 3 — HAR VOLATILITY FORECASTING SUITE WITH JUMP DECOMPOSITION AND MODEL CONFIDENCE SET

### What you are building mathematically

A linear heterogeneous autoregressive framework operating on the vol series from Feature 1, extended with jump decomposition, leverage effects, and cross-sectional volatility predictors — all estimated simultaneously with a Model Confidence Set competition.

---

### Step 1 — Input vol series construction

From Feature 1, retrieve the Yang-Zhang annualized daily vol series {σ_YZ,t} for all available dates.

Define the three HAR regressors at each date t:

Daily vol (d): v_t^{(d)} = σ_YZ,t

Weekly vol (w): v*t^{(w)} = (1/5) × Σ*{s=t-4}^{t} σ_YZ,s (5-day trailing average)

Monthly vol (m): v*t^{(m)} = (1/22) × Σ*{s=t-21}^{t} σ_YZ,s (22-day trailing average)

The dependent variable at forecast horizon h: v\_{t+h}^{(d)} = σ_YZ,t+h (the realized Yang-Zhang vol h days ahead).

---

### Step 2 — HAR model

The baseline Corsi (2009) specification:

v\_{t+h} = β₀ + β_d × v_t^{(d)} + β_w × v_t^{(w)} + β_m × v_t^{(m)} + ε_t

This is a linear OLS regression. Define the N×4 regressor matrix X = [1, v^{(d)}, v^{(w)}, v^{(m)}] and the N×1 dependent vector y = [v_{t+h}]. OLS:

β̂ = (X'X)^{-1} X'y

Standard errors corrected for heteroskedasticity and autocorrelation (Newey-West with bandwidth = h):

Ŝ_NW = (X'X)^{-1} × Ω̂_NW × (X'X)^{-1}

where Ω̂*NW = (1/T) Σ_t x_t x_t' ε̂²_t + (1/T) Σ*{l=1}^{h} (1 − l/(h+1)) × Σ*{t=l+1}^{T} (x_t x*{t-l}' ε̂*t ε̂*{t-l} + x*{t-l} x_t' ε̂*{t-l} ε̂_t)

The Newey-West bandwidth must equal h when the forecast horizon is h > 1, because the overlapping returns in the dependent variable create MA(h-1) serial correlation in the residuals by construction.

t-statistics: t_j = β̂_j / SE_NW(β̂_j) for each coefficient j ∈ {0, d, w, m}.

Interpretation:
β_w dominant (|β_w| > |β_d| + |β_m|): weekly persistence is the primary volatility driver. Typical in equity indices.
β_m dominant: volatility is driven by monthly regime persistence. Typical in FX and commodities.
β_d dominant and β_w, β_m ≈ 0: highly mean-reverting volatility — spikes decay quickly. Typical in VIX itself.

---

### Step 3 — LHAR model (log-HAR)

Apply the natural log transformation to both sides:

ln(v\_{t+h}) = β₀ + β_d × ln(v_t^{(d)}) + β_w × ln(v_t^{(w)}) + β_m × ln(v_t^{(m)}) + ε_t

Advantages: (1) guarantees positive vol forecasts by exponentiating the fitted value, (2) stabilizes the variance of the regression residuals (volatility is log-normally distributed approximately, so log-vol has a more homoskedastic error structure), (3) coefficients become elasticities: β_d = 0.6 means a 10% increase in daily vol predicts a 6% increase in forward vol.

Back-transformation to get vol forecasts in levels: v̂*{t+h} = exp(β̂₀ + β̂_d × ln(v_t^{(d)}) + β̂_w × ln(v_t^{(w)}) + β̂_m × ln(v_t^{(m)}) + σ̂²*ε/2)

The last term σ̂²_ε/2 is the Jensen's inequality bias correction: E[exp(X)] = exp(E[X] + Var(X)/2) for log-normal X. Without this correction, the back-transformed forecast is systematically biased downward.

---

### Step 4 — Jump proxy construction (no intraday data required)

The jump component is isolated from the vol series using the ratio of the Rogers-Satchell (pure diffusion) to Yang-Zhang (total) estimators from Feature 1:

Jump_proxy_t = max(σ²_YZ,t − σ²_RS,t, 0)

When σ²_YZ,t ≫ σ²_RS,t: the YZ estimator (which includes overnight gap variance) detects a much larger variance than the RS estimator (which only uses the intraday range). This divergence signals a genuine gap-open — the overnight jump component is large.

Normalize the jump proxy to a fraction of total daily variance:

J_t = Jump_proxy_t / σ²_YZ,t ∈ [0, 1]

J_t → 0: variance is entirely from continuous diffusion (normal trading day)
J_t → 1: variance is entirely from an overnight jump (gap-open day — earnings, macro announcements, policy decisions)

Separate the jump into signed components:

J*t^+ = J_t × I*{r*t > 0} (jump occurred in the positive direction, based on daily close-to-close return sign)
J_t^− = J_t × I*{r_t < 0} (jump occurred in the negative direction)

---

### Step 5 — HAR-J model

Extends the baseline HAR by adding the jump proxy as an additional regressor:

v\_{t+h} = β₀ + β_d × v_t^{(d)} + β_w × v_t^{(w)} + β_m × v_t^{(m)} + β_J × J_t + ε_t

Economic interpretation: β_J measures the marginal forecasting contribution of the jump component beyond the smooth vol component. If β_J > 0 and statistically significant: jumps today predict elevated vol tomorrow, but less persistently than the diffusion component (because jumps are largely uncorrelated day-to-day, unlike diffusion vol which is highly autocorrelated). If β_J ≈ 0: jumps do not contain additional predictive information beyond total vol — common in assets with infrequent gap-opens.

To separate the forecasting effect of positive vs. negative jumps:

v\_{t+h} = β₀ + β_d × v_t^{(d)} + β_w × v_t^{(w)} + β_m × v_t^{(m)} + β_J^+ × J_t^+ + β_J^− × J_t^− + ε_t

Test: β_J^− > β_J^+ (negative jumps predict more future vol than positive jumps — consistent with the leverage/fear-of-falling asymmetry in equity markets).

---

### Step 6 — HAR-Leverage model

Adds the signed lagged daily return to capture the leverage effect:

v*{t+h} = β₀ + β_d × v_t^{(d)} + β_w × v_t^{(w)} + β_m × v_t^{(m)} + β_lev × r*{t-1} + ε_t

β_lev < 0 (statistically): negative returns today predict higher future vol (the leverage/volatility feedback effect). This has been documented empirically in every major equity market globally.

To separate the effect by return sign:

r*t^+ = r_t × I*{r*t > 0}, r_t^− = r_t × I*{r_t < 0}

v*{t+h} = β₀ + β_d × v_t^{(d)} + β_w × v_t^{(w)} + β_m × v_t^{(m)} + β*{lev}^+ × r*t^+ + β*{lev}^− × r_t^− + ε_t

If |β*{lev}^−| > |β*{lev}^+|: negative returns have a stronger vol impact than positive returns (the expected asymmetry).

---

### Step 7 — ACSV-HAR model

The Asymmetric Cross-Sectional Variance extension (Niu et al., 2023):

Cross-sectional variance at date t across N assets:

CSV*t = (1/N) × Σ*{i=1}^{N} (r\_{i,t} − r̄_t)²

where r*{i,t} is the return of asset i and r̄_t = (1/N) Σᵢ r*{i,t} is the cross-sectional mean return.

CSV measures the dispersion of returns across stocks at each date — it is high when individual stocks are behaving idiosyncratically and low when all stocks move together (high correlation regime). CSV is publicly available information (computed from cross-sectional return data) and contains predictive information about aggregate market volatility because it captures the breadth of uncertainty: when many stocks are moving differently from each other, future market vol tends to be elevated.

ACSV-HAR (symmetric):

v\_{t+h} = β₀ + β_d × v_t^{(d)} + β_w × v_t^{(w)} + β_m × v_t^{(m)} + β_CSV × CSV_t + ε_t

A-ACSV-HAR (asymmetric — separates above-mean vs. below-mean return dispersion):

CSV*t^+ = (1/N) × Σᵢ (max(r*{i,t} − r̄*t, 0))² (upside dispersion)
CSV_t^− = (1/N) × Σᵢ (min(r*{i,t} − r̄_t, 0))² (downside dispersion)

v*{t+h} = β₀ + β_d × v_t^{(d)} + β_w × v_t^{(w)} + β_m × v_t^{(m)} + β*{CSV}^+ × CSV*t^+ + β*{CSV}^− × CSV_t^− + ε_t

If β*{CSV}^− > β*{CSV}^+: downside dispersion is the dominant predictor of future aggregate vol — consistent with loss aversion and fear-driven trading being the primary channel through which cross-sectional dispersion forecasts market risk.

---

### Step 8 — Walk-forward OOS evaluation

For each of the 6 HAR variants and each forecast horizon h ∈ {1, 5, 10, 21, 42, 63}:

Define an expanding estimation window: at each evaluation date t, estimate the model using data from t₀ to t−1 (never using data from t onward).

The OOS forecast: v̂\_{t+h|t} = β̂(t)' × x_t where β̂(t) is the coefficient vector estimated on [t₀, t−1].

This is strictly out-of-sample — no data after t is used in any way. This is the correct procedure for evaluating genuine forecasting value.

---

### Step 9 — Forecast accuracy metrics

For each model E and horizon h, compute over the OOS evaluation window:

**RMSE:** RMSE*{E,h} = √[(1/T_OOS) Σ_t (v̂*{t+h|t} − v\_{t+h})²]

**QLIKE:** QLIKE*{E,h} = (1/T_OOS) Σ_t [v²*{t+h} / v̂²*{t+h|t} − ln(v²*{t+h} / v̂²\_{t+h|t}) − 1]

**MAE:** MAE*{E,h} = (1/T_OOS) Σ_t |v̂*{t+h|t} − v\_{t+h}|

**OOS R²:** R²*OOS,{E,h} = 1 − Σ_t (v̂*{t+h|t} − v*{t+h})² / Σ_t (v̄*{hist} − v\_{t+h})²

where v̄\_{hist} is the historical mean vol — the naive benchmark. R²_OOS > 0 means the model outperforms the naive historical mean; R²_OOS < 0 means the model is worse than the simple average.

The Model Confidence Set is then applied across the 6 HAR variants using the same procedure as Feature 2, Step 9, under QLIKE loss.

---

### Outputs

**HAR parameter table:** 6 rows (one per HAR variant). Columns: β₀, β*d, β_w, β_m, β_J, β_J^+, β_J^−, β_lev, β*{CSV}^+, β\_{CSV}^− (as applicable), with Newey-West standard errors and t-statistics beneath each coefficient. Coefficient cells color-coded: green for t > 2, amber for 1 < t < 2, gray for t < 1.

**Multi-horizon forecast chart:** For each horizon h: OOS forecast v̂*{t+h|t} vs. actual v*{t+h} plotted over the full OOS window. 90% bootstrap confidence bands shaded. Separate panels per horizon, or a single animated panel with h as the slider variable.

**Forecast accuracy table:** 6 rows × 6 horizons = 36 cells for each metric (RMSE, QLIKE, MAE, R²_OOS). The MCS-surviving models are highlighted. The cell color encodes R²_OOS: green for R² > 0.1 (meaningful improvement over the naive benchmark), amber for 0 < R² < 0.1, red for R² < 0.

**Model Confidence Set panel:** List of surviving models at 90% MCS confidence under QLIKE loss. Eliminated models struck through. When only one model survives: "Model [X] is statistically dominant at the 90% confidence level for this asset and horizon."

**Jump proxy time series:** Daily J_t = σ²_YZ,t − σ²_RS,t plotted as a fraction of total daily variance. Spike dates annotated with the corresponding price event. A histogram of J_t in the top panel shows the fraction of trading days with J_t > 0.1 (elevated jump activity).

**Leverage effect chart:** Rolling 63-day regression coefficient of r\_{t-1} on σ_YZ,t (i.e., the coefficient from regressing today's vol on yesterday's return, with a 63-day rolling window). Plotted over full history. Should be consistently negative for equity indices; near zero during sustained low-vol regimes (2017, 2024); most negative during crisis transitions (2008, 2020, 2025).

**ACSV predictive contribution chart:** CSV*t^+ and CSV_t^− time series vs. the target σ_YZ,t^{(m)} (monthly vol). Annotated with the regression-implied predictive contribution β̂*{CSV}^+ × CSV*t^+ and β̂*{CSV}^− × CSV_t^−. Separated by sign and displayed as stacked contributions to the A-ACSV-HAR fitted value.

---

### Data map

| Series                                      | Source                | Ticker / Code                   | Frequency |
| ------------------------------------------- | --------------------- | ------------------------------- | --------- |
| Vol series from Feature 1                   | Internal output       | —                               | Daily     |
| Daily closing returns                       | Yahoo Finance / Stooq | Per ticker                      | Daily     |
| Cross-sectional constituent returns for CSV | Yahoo Finance batch   | S&P 500 / user-defined universe | Daily     |

---

## FEATURE 4 — VOLATILITY REGIME DETECTION ENGINE WITH PROBABILISTIC STATE ASSIGNMENT

### What you are building mathematically

Three parallel regime detection methods — a Statistical Jump Model, a Hidden Markov Model, and a Macro Rules Engine — each producing a probability vector over K regime states at every date, combined into a precision-weighted composite via rolling Brier score accuracy.

---

### Step 1 — Feature vector construction for the SJM

At each date t, construct the regime feature vector:

f*t = (σ_5,t, σ_21,t, σ_63,t, r*{21,t}, RS_YZ_ratio_t, AC²_21,t) ∈ ℝ^6

where:

σ*5,t = 5-day Yang-Zhang annualized vol (from Feature 1)
σ_21,t = 21-day Yang-Zhang annualized vol
σ_63,t = 63-day Yang-Zhang annualized vol
r*{21,t} = cumulative 21-day return (to capture the directional momentum of the current regime)
RS*YZ_ratio_t = σ_RS,t / σ_YZ,t ∈ [0,1] (the jump ratio from Feature 3 — low values indicate jump-dominated regimes)
AC²_21,t = 21-day sample autocorrelation of squared daily returns (Σ*{s=t-20}^{t-1} (r²*{s} − r̄²)(r²*{s+1} − r̄²)) / (Σ*{s=t-20}^{t} (r²*{s} − r̄²)²) — captures GARCH clustering intensity

Standardize the feature vector: for each feature j, compute the z-score using the trailing 252-day mean and standard deviation:

f̃*{j,t} = (f*{j,t} − μ̂*{j,t-252:t}) / σ̂*{j,t-252:t}

This ensures no single feature dominates the clustering due to scale differences.

---

### Step 2 — Statistical Jump Model (SJM)

The SJM modifies k-means clustering by adding a penalty for regime transitions, producing more persistent (realistic) regime assignments.

**Standard k-means initialization:**

For K regimes, initialize centroids μ¹_k (k = 1,...,K) using k-means++ algorithm:

1. Choose the first centroid μ¹_1 uniformly at random from {f̃_t}.
2. For each subsequent centroid: choose f̃_t with probability proportional to d(f̃_t, nearest existing centroid)².
3. Repeat until K centroids are chosen.

**SJM objective function:**

The SJM minimizes the total within-cluster variance plus a jump penalty for each state transition:

L*SJM(z, μ) = Σ*{t=1}^{T} ‖f̃*t − μ*{z*t}‖² + λ × Σ*{t=2}^{T} I*{z_t ≠ z*{t-1}}

where z_t ∈ {1,...,K} is the state assignment at date t, μ_k is the centroid of state k, and λ is the jump penalty.

The optimization is a dynamic programming problem. For each date t, define:

V_t(k) = minimum cost of assigning states z_1,...,z_t such that z_t = k

Bellman recursion:

V*t(k) = ‖f̃_t − μ_k‖² + min*{j=1}^{K} [V_{t-1}(j) + λ × I_{j ≠ k}]

This recursion runs in O(T × K²) time. The optimal state sequence is recovered by backtracking from the minimizing state at T.

Alternating optimization (for updating centroids):

1. Fix {μ_k}: solve the DP for optimal {z_t}.
2. Fix {z_t}: update centroids μ_k = mean{f̃_t : z_t = k}.
3. Repeat until convergence (change in L_SJM < 10^{-6}).

Convert the hard state assignments to a probability vector: for the SJM, the hard assignment z_t = k* corresponds to a probability vector p_SJM(t) with p_SJM(t)[k*] = 1 and all other elements = 0. This is a degenerate distribution — the SJM is a hard-assignment model.

**Soft SJM:** To produce a genuine probability vector (not degenerate), replace the hard assignment with a softmax over the negative squared distances:

p*SJM(t)[k] = exp(−‖f̃_t − μ_k‖² / τ) / Σ*{k'} exp(−‖f̃*t − μ*{k'}‖² / τ)

where τ > 0 is a temperature parameter (τ → 0 recovers the hard assignment; τ = 1.0 is a reasonable default). This soft-SJM output is a valid probability vector.

**Jump penalty calibration:** For λ = 0 (unconstrained): typical regime duration = 5–10 days (too jumpy). For λ = 50: typical regime duration = 40–80 days (realistic). Display the average regime duration at each λ in the tooltip. The user selects λ based on their desired regime persistence.

---

### Step 3 — Hidden Markov Model (HMM)

The HMM operates on the daily log-vol series: o_t = ln(σ_YZ,t) (log-Yang-Zhang vol).

**Model specification:** K-state Gaussian HMM with:
Emission distributions: P(o*t | state = k) = N(μ_k, σ²_k) (Gaussian on log-vol per state)
Transition matrix: A ∈ ℝ^{K×K}, A*{kj} = P(state*t = j | state*{t-1} = k), each row sums to 1
Initial distribution: π₀ ∈ ℝ^K, π₀_k = P(state_1 = k)

**Baum-Welch (EM) estimation:**

E-step — Forward pass (α_t(k) = P(o_1,...,o_t, state_t = k)):

α_1(k) = π₀_k × N(o_1 | μ_k, σ²_k)

α*t(k) = N(o_t | μ_k, σ²_k) × Σ*{j=1}^{K} α*{t-1}(j) × A*{j,k}

Scale at each step: ĉ_t = Σ_k α_t(k); set α̃_t(k) = α_t(k)/ĉ_t to prevent numerical underflow. Store {ĉ_t} for the log-likelihood: ℓ = Σ_t ln(ĉ_t).

E-step — Backward pass (β*t(k) = P(o*{t+1},...,o_T | state_t = k)):

β_T(k) = 1

β*t(k) = Σ*{j=1}^{K} A*{k,j} × N(o*{t+1} | μ*j, σ²_j) × β*{t+1}(j) / ĉ\_{t+1}

Smoothed posterior (the probabilistic regime output):

γ*t(k) = α̃_t(k) × β_t(k) / Σ*{j} α̃_t(j) × β_t(j)

This is the probability that the system is in state k at date t, given the entire observation sequence — it uses both past and future observations and is therefore retrospective (smoothed). For a live (real-time) system, use the filtered posterior α̃_t(k) instead, which uses only past observations.

Joint state transition posterior:

ξ*t(k,j) = α̃_t(k) × A*{k,j} × N(o*{t+1} | μ_j, σ²_j) × β*{t+1}(j) / (ĉ*{t+1} × Σ*{k',j'} α̃*t(k') × A*{k',j'} × N(o*{t+1} | μ*{j'}, σ²*{j'}) × β*{t+1}(j'))

M-step updates:

π̂₀_k = γ_1(k)

Â*{k,j} = Σ*{t=1}^{T-1} ξ*t(k,j) / Σ*{t=1}^{T-1} γ_t(k)

μ̂_k = Σ_t γ_t(k) × o_t / Σ_t γ_t(k)

σ̂²_k = Σ_t γ_t(k) × (o_t − μ̂_k)² / Σ_t γ_t(k)

Iterate E-step and M-step until |ℓ_new − ℓ_old| < 10^{-6}. Initialize with 20 random restarts; keep the solution with the highest log-likelihood.

The HMM probabilistic output: p_HMM(t) = (γ_t(1), ..., γ_t(K)) ∈ ΔK (the K-dimensional probability simplex).

Select K by BIC: BIC_K = −2ℓ(K) + p_K × ln(T) where p_K = K² + 2K − 1 is the total number of HMM parameters. Choose K\* = argmin_K BIC_K, evaluated over K ∈ {2, 3, 4}.

---

### Step 4 — Macro Rules Engine

Define three binary macro variables at each date t:

Stress*t = I*{VIX*t > VIX_threshold} (default VIX_threshold = 25; adjustable)
Inverted_t = I*{(DGS10*t − DGS2_t) < 0} (inverted yield curve)
HighVol_trend_t = I*{σ_21,t > σ_63,t} (21-day vol above 63-day vol — short-term acceleration above the medium-term trend)

For K = 2 regimes (low-vol / high-vol):

P_macro(high-vol | t) = (Stress_t + Inverted_t + HighVol_trend_t) / 3

P_macro(low-vol | t) = 1 − P_macro(high-vol | t)

p_macro(t) = (P_macro(low-vol | t), P_macro(high-vol | t)) ∈ {(1,0), (0.67, 0.33), (0.33, 0.67), (0, 1)}

For K = 3 regimes (low-vol / medium-vol / high-vol):

Define a transition region: any date where exactly one of the three binary variables is in the stressed state.

The probability mass is distributed across the three states via a softmax over the macro score S_t ∈ {0, 1, 2, 3}:

P*macro(k | t) = exp(−(k − (K-1) × S_t/3)² / (2 × 0.5²)) / Σ*{k'} exp(−(k' − (K-1) × S_t/3)² / (2 × 0.5²))

This is a Gaussian bump centered at the "stress-implied" state (K-1) × S_t/3, with width 0.5. For K = 3: the implied state ranges from 0 (all-clear) to 2 (full crisis); the Gaussian spreads probability mass to neighboring states.

---

### Step 5 — Precision-weighted ensemble combination

At each date t, the three model outputs are:

p_SJM(t) ∈ ΔK, p_HMM(t) ∈ ΔK, p_macro(t) ∈ ΔK

**Brier score accuracy of each method:**

The Brier score for model m at date t:

BS*m(t) = Σ*{k=1}^{K} (p_m(t)[k] − o_t[k])²

where o*t[k] = I*{dominant state at t = k} (the "truth" is taken as the HMM Viterbi state for the evaluation benchmark, to maintain internal consistency — the HMM's hard Viterbi assignment provides the "realized state" for evaluating all three models).

Rolling 63-day average Brier score for each method:

BS̄*m(t) = (1/63) × Σ*{s=t-62}^{t} BS_m(s)

Accuracy weight (lower Brier score = better = higher weight):

w*m(t) = exp(−BS̄_m(t)) / Σ*{m'} exp(−BS̄\_{m'}(t))

This is a softmax over negative average Brier scores — methods that predicted the realized regimes more accurately in the trailing 63 days receive exponentially higher weight.

Composite probability:

p_composite(t) = w_SJM(t) × p_SJM(t) + w_HMM(t) × p_HMM(t) + w_macro(t) × p_macro(t)

p_composite(t) is always in ΔK (it is a convex combination of probability vectors). The composite is the primary output of Feature 4 and feeds directly into Features 5, 8, and 9.

---

### Step 6 — Regime-conditional volatility statistics

For each regime state k, compute the regime-conditional statistics using the soft regime assignments (probability-weighted, not hard):

**Probability-weighted mean vol:**

μ_vol,k = Σ_t p_composite(t)[k] × σ_YZ,t / Σ_t p_composite(t)[k]

**Probability-weighted vol standard deviation:**

σ_vol,k = √[Σ_t p_composite(t)[k] × (σ_YZ,t − μ_vol,k)² / Σ_t p_composite(t)[k]]

**Probability-weighted HAR forecast bias:**

Bias*k = Σ_t p_composite(t)[k] × (v̂*{t+21|t}^{HAR} − σ_YZ,t+21) / Σ_t p_composite(t)[k]

Positive Bias_k: HAR under-forecasts future vol when the system is in state k (the model is too optimistic in state k). Negative Bias_k: HAR over-forecasts (too pessimistic in state k).

**Probability-weighted cross-sectional return dispersion:**

CSV_k = Σ_t p_composite(t)[k] × CSV_t / Σ_t p_composite(t)[k]

High CSV in the high-vol state confirms that broad market stress (not idiosyncratic noise) is the mechanism behind vol elevation.

---

### Step 7 — Regime transition probability matrix

The empirical K×K transition matrix at the 1-week horizon:

T̂\_{1W}[k, j] = Σ_t p_composite(t)[k] × p_composite(t+5)[j] / Σ_t p_composite(t)[k]

This is the expected probability of transitioning from state k to state j over the next 5 trading days, estimated by regressing the joint probability mass on the current state.

At the 1-month horizon: T̂*{1M}[k,j] using t+22 instead of t+5. At the 3-month horizon: T̂*{3M}[k,j] using t+63.

The diagonal of each matrix gives the persistence probability: the probability of remaining in the current regime over the given horizon. High diagonal values (e.g., T̂\_{1W}[k,k] > 0.8) indicate the current regime is likely to persist.

---

### Outputs

**Probabilistic regime timeline:** Stacked area chart with dates on the x-axis and probability mass on the y-axis (always summing to 1). K colored stacked areas, one per regime. Expanding transition-state probability (if K = 3) is the visual signature of an impending regime change. Historical crisis dates annotated as vertical dashed lines, self-validating the regime identification.

**Current regime probability dashboard:** K horizontal bar gauges, one per state, each showing the current p*composite(t=T)[k]. Below each gauge: the 30-day and 90-day trend in that state's probability (expressed as a signed change). Below the gauges: the current dominant state's average historical persistence duration (expected number of days before a transition, estimated as 1 / (1 − T̂*{1W}[k*,k*]) × 5 days).

**Regime-conditional vol statistics table:** K rows. Columns: regime label (auto-labeled by μ*vol,k as "low", "medium", "high", "crisis"), μ_vol,k (annualized), σ_vol,k, Bias_k (HAR forecast bias), CSV_k, T̂*{1W}[k,k] (persistence). Color-coded by regime severity.

**Regime transition heatmap:** K×K matrix for each of the three horizons (1W, 1M, 3M). Cell (k,j) shows T̂[k,j] as a number and color intensity. Diagonal cells (persistence) annotated with their value in bold.

**Method divergence indicator:** Daily scalar measuring the average KL divergence between the three method probability vectors:

KL_avg(t) = (1/3) × [KL(p_SJM ‖ p_composite) + KL(p_HMM ‖ p_composite) + KL(p_macro ‖ p_composite)]

where KL(p ‖ q) = Σ_k p[k] × ln(p[k]/q[k]) is the Kullback-Leibler divergence. High KL_avg = high model disagreement = elevated structural uncertainty — this is a risk signal independent of the current vol level.

**Regime transition alert log:** Timestamped entries when any regime state's probability changes by more than the user-set threshold (default: 0.30 change in 5 days). Each entry shows: date, previous and current probability vectors, method-level probabilities (to identify which method drove the alert), and the base rate of forward stress conditional on this level of transition probability.

---

### Data map

| Series                          | Source                | Ticker / Code | Frequency |
| ------------------------------- | --------------------- | ------------- | --------- |
| Daily vol series from Feature 1 | Internal output       | —             | Daily     |
| VIX index                       | FRED                  | VIXCLS        | Daily     |
| 2-year US Treasury yield        | FRED                  | DGS2          | Daily     |
| 10-year US Treasury yield       | FRED                  | DGS10         | Daily     |
| Daily closing returns           | Yahoo Finance / Stooq | Per ticker    | Daily     |

---

## FEATURE 5 — VOLATILITY RISK PREMIUM MONITOR AND RETURN PREDICTABILITY ENGINE

### What you are building mathematically

A daily monitor of the spread between risk-neutral and physical variance expectations — estimated via three parallel physical expectation methods — with the Bollerslev-Tauchen-Zhou return predictability regression run live.

---

### Step 1 — Risk-neutral variance from the VIX

The CBOE VIX is the square root of the model-free risk-neutral expected variance of the S&P 500 over the next 30 calendar days, annualized and expressed in percentage points.

Convert to a raw variance in (daily return)² units:

IV²_t = (VIX_t / 100)² / 12

This is the 30-calendar-day risk-neutral variance, expressed as a monthly variance. The division by 12 converts from annualized variance ((VIX/100)²) to monthly variance (divide by 12 months).

Annualized implied vol: IV_ann,t = VIX_t / 100 (already annualized by construction).

For non-US assets with available implied vol indices (VSTOXX for STOXX50, VFTSE for FTSE100, JNIV for Nikkei):

Convert using the same formula: IV²_t = (V_index_t / 100)² / 12

For assets without published implied vol indices: skip Feature 5 or use user-uploaded implied vol CSV data.

---

### Step 2 — Physical variance expectation: Method 1 (GARCH-based)

From Feature 2, the winning GARCH model produces a 21-trading-day-ahead (≈ 1-month) variance forecast at each date t:

E*t^{GARCH}[σ²*{t+21}] = GARCH 21-step-ahead conditional variance

For GARCH(1,1): closed-form (Step 11 of Feature 2):

E*t^{GARCH}[σ²*{t+21}] = σ²*∞ + (α+β)^{20} × (σ²*{t+1} − σ²_∞)

This is expressed in daily variance units. Convert to monthly variance: multiply by 21 (sum the 21 one-day variance forecasts). Then convert to annualized variance: multiply by 252/21 = 12.

Physical variance expectation (Method 1):

E*t^{M1}[σ²*{phys}] = 12 × E*t^{GARCH}[Σ*{s=t+1}^{t+21} σ²*s / 21] = E_t^{GARCH}[σ²*{t+21}] × 252

(Approximately, under the mean-reversion structure of GARCH, this equals the annualized 1-month-ahead conditional variance from the model.)

---

### Step 3 — Physical variance expectation: Method 2 (HAR-based)

From Feature 3, the HAR model at the 21-day horizon gives:

E*t^{HAR}[v*{t+21}] = β̂₀ + β̂_d × v_t^{(d)} + β̂_w × v_t^{(w)} + β̂_m × v_t^{(m)}

where v represents annualized Yang-Zhang vol (from Feature 1). The HAR forecasts vol in annualized levels, so:

Physical variance expectation (Method 2): E*t^{M2}[σ²*{phys}] = (E*t^{HAR}[v*{t+21}])²

(Squaring the annualized vol forecast gives the annualized variance expectation.)

---

### Step 4 — Physical variance expectation: Method 3 (rolling historical mean)

The naive unconditional estimator: the trailing 252-day average of daily squared returns, annualized:

E*t^{M3}[σ²*{phys}] = 252 × (1/252) × Σ*{s=t-251}^{t} r²_s = Σ*{s=t-251}^{t} r²_s

This is the unconditional realized variance over the trailing year. It serves as the benchmark: the VRP relative to Method 3 answers whether implied vol is expensive even relative to the simple historical average.

---

### Step 5 — VRP computation (three versions)

For each method m ∈ {GARCH, HAR, historical}:

**Raw spread (annualized vol points):**

VRP*ann,m,t = IV_ann,t − √(E_t^{Mm}[σ²*{phys}])

This is the spread between the market's implied vol and the model-estimated physical vol, both in annualized percentage point units. Positive VRP = implied vol exceeds realized expectations = sellers of variance earn the premium.

**Variance form:**

VRP*var,m,t = IV²_t − E_t^{Mm}[σ²*{phys}] / 12

(Monthly variance form; both sides expressed in monthly variance units — the form used in Bollerslev, Tauchen, and Zhou, 2009.)

**Z-score:**

Compute the rolling mean and standard deviation of VRP_ann,m,t over the lookback window W_z ∈ {252, 504, 1260} days:

μ*VRP,m = (1/W_z) × Σ*{s=t-W_z+1}^{t} VRP_ann,m,s

σ*VRP,m = √[(1/W_z) × Σ*{s=t-W_z+1}^{t} (VRP_ann,m,s − μ_VRP,m)²]

VRP_zscore,m,t = (VRP_ann,m,t − μ_VRP,m) / σ_VRP,m

A VRP z-score above +2 means the current risk premium is exceptionally wide by historical standards (sellers of variance face historically attractive entry conditions). A z-score below −1 means the premium has compressed or inverted (rare, but occurs briefly after volatility spikes when realized vol temporarily exceeds implied vol).

---

### Step 6 — VRP return predictability regression (Bollerslev-Tauchen-Zhou, 2009)

The BTZ regression tests whether current VRP predicts future equity returns:

R\_{equity,t+H} = a + b × VRP_var,t + u_t

where R\_{equity,t+H} is the cumulative equity index return from t to t+H (H = 21, 63, or 126 trading days), and VRP_var,t is the variance-form VRP from Method 1 (GARCH physical expectation, which is the specification in the original BTZ paper).

**OLS estimation** with Newey-West standard errors (bandwidth = H, because the overlapping returns in the dependent variable create MA(H-1) serial correlation):

b̂ = Σ*t (VRP_var,t − VRP̄)(R*{t+H} − R̄) / Σ_t (VRP_var,t − VRP̄)²

SE_NW(b̂) using the Newey-West formula with bandwidth H (same as Feature 3, Step 2).

t-statistic: t_b = b̂ / SE_NW(b̂)

In-sample R²: R² = 1 − Σ*t (R*{t+H} − â − b̂ × VRP*var,t)² / Σ_t (R*{t+H} − R̄)²

OOS R² (using expanding window to avoid look-ahead): R²*OOS = 1 − Σ_t (R*{t+H} − â(t) − b̂(t) × VRP*var,t)² / Σ_t (R*{t+H} − R̄\_{t})²

where â(t), b̂(t) are estimated using only data up to t−1.

**Current implied return prediction:**

R̂\_{t+H} = â + b̂ × VRP_var,T

This is the BTZ-implied forward equity return given the current VRP reading. When VRP is in the top quartile of its history: the BTZ-implied return is elevated (the most widely supported finding in the BTZ paper — R² of 1–4% for H = 63 days in US equities).

**Rolling 252-day expanding regression:** At each date t, re-estimate the BTZ regression using all data from t₀ to t. The time series of b̂(t) and R²(t) shows whether the predictive power of VRP is stable over time or has changed regime.

---

### Step 7 — VRP mean reversion speed (Ornstein-Uhlenbeck fit)

Model the VRP series as an OU process:

dVRP_t = κ × (θ − VRP_t) × dt + σ_VRP × dW_t

Discretized for daily data:

VRP*t − VRP*{t-1} = κ × (θ − VRP\_{t-1}) × Δt + σ_VRP × √Δt × z_t

This is a first-order autoregression: VRP*t = (1 − κΔt) × VRP*{t-1} + κθΔt + σ_VRP√Δt × z_t

OLS estimation: regress ΔVRPt = VRP*t − VRP*{t-1} on VRP\_{t-1}:

β̂*OU = Σ_t ΔVRP_t × VRP*{t-1} / Σ*t VRP²*{t-1} − VRP̄ × ΔV̄RP / (Σ*t VRP²*{t-1}/T − VRP̄²)

More simply: OLS slope of ΔVRP on VRP\_{t-1}: slope = −κΔt.

Mean reversion speed: κ = −slope / Δt = −slope × 252 (per year, since Δt = 1/252)

Half-life: t\_{1/2} = ln(2) / κ = ln(2) × 252 / (−slope) trading days

A shortening half-life (t\_{1/2} decreasing over time via rolling 252-day estimation) means VRP is mean-reverting faster — risk aversion spikes are being resolved more quickly by the market, which is favorable for variance sellers.

---

### Step 8 — VRP component attribution

Decompose the VRP_var,m,t into two sub-components:

**GARCH conditional variance contribution (the "expected vol" component):**

This is the component of the risk-neutral variance explained by the current GARCH conditional variance:

C*GARCH,t = β̂_GARCH × σ²*{GARCH,t}

where β̂*GARCH is the OLS coefficient from regressing IV²_t on σ²*{GARCH,t} over the full history.

**Pure risk aversion component:**

C*RA,t = VRP_var,M1,t − C_GARCH,t = IV²_t − E_t^{M1}[σ²*{phys}] − β̂*GARCH × σ²*{GARCH,t} + E*t^{M1}[σ²*{phys}]

More precisely:

C*GARCH,t = E_t^{M1}[σ²*{phys}] / 12 (the physical expectation component — what the market would price if it were risk-neutral)

C_RA,t = IV²_t − C_GARCH,t (the excess over physical expectation — the pure risk premium)

VRP_var,t = C_GARCH,t + C_RA,t

The ratio C_RA,t / VRP_var,t: the fraction of total VRP attributable to pure risk aversion vs. expected volatility. Rising C_RA / VRP means risk aversion is increasing even as expected vol is stable — a fear-driven premium. Falling C_RA / VRP means the VRP is wide primarily because expected vol is high, not because risk aversion is elevated — an informationally-driven premium.

---

### Outputs

**VRP time series with percentile overlay:** Three lines on one chart (one per physical expectation method), plotted over the full 10-year history. Background shading in four bands: deep red (top quartile of VRP — implied vol very expensive), red (50th–75th percentile), white (25th–50th), blue (bottom quartile — implied vol cheap). The three lines converging = clean signal; diverging = model uncertainty about the true physical expectation.

**Cross-asset VRP comparison table:** One row per asset with an associated vol index. Columns: asset name, current VRP_ann (in vol point spread), 10-year percentile of VRP, 3-month change in VRP (the momentum of the premium), rich/cheap flag (>70th percentile = "Rich — implied vol expensive relative to realized", <30th = "Cheap"). Color coded: red for rich, green for cheap.

**Return predictability panel:** Four sub-charts, one per horizon H ∈ {21, 63, 126, 252} days. Each sub-chart shows: (1) expanding-window b̂(t) over time with 90% confidence bands, (2) expanding-window R²(t), and (3) current predicted return R̂\_{T+H}. The R²(t) time series shows whether the BTZ effect has strengthened or weakened over time.

**VRP mean reversion speed chart:** Rolling 252-day half-life t\_{1/2}(t) over full history. Horizontal dashed lines at 21 days (one month) and 63 days (one quarter). A rising half-life means VRP is becoming less mean-reverting (structural shift in risk premium dynamics). A falling half-life means faster normalization.

**VRP component attribution stacked chart:** Daily stacked area chart showing C_GARCH,t (bottom, gray — the expected vol component) and C_RA,t (top, red or green — the pure risk aversion component). Total height = VRP_var,t. The ratio of C_RA to total VRP is the primary investment signal for variance sellers: high C_RA means the premium is fear-driven and likely to normalize quickly.

---

### Data map

| Series                                 | Source               | Ticker / Code          | Frequency |
| -------------------------------------- | -------------------- | ---------------------- | --------- |
| VIX daily closing level                | FRED                 | VIXCLS                 | Daily     |
| VSTOXX daily level                     | STOXX / Quandl       | V2TX                   | Daily     |
| VFTSE daily level                      | CBOE public / Quandl | VFTSE                  | Daily     |
| GARCH variance forecast from Feature 2 | Internal output      | —                      | Daily     |
| HAR vol forecast from Feature 3        | Internal output      | —                      | Daily     |
| Equity index daily returns             | Yahoo Finance / FRED | ^GSPC, ^STOXX50E, etc. | Daily     |

---

## FEATURE 6 — CROSS-ASSET VOLATILITY CONNECTEDNESS AND SPILLOVER NETWORK

### What you are building mathematically

A rolling Diebold-Yilmaz connectedness framework on daily log-vol series across N assets, producing a total connectedness index, asset-level net spillover rankings, and a directed dynamic network — all updated daily.

---

### Step 1 — Log-vol panel construction

For each asset i ∈ {1,...,N} at date t, compute the log-Yang-Zhang vol:

y\_{i,t} = ln(σ_YZ,i,t) (from Feature 1)

where σ_YZ,i,t is the annualized Yang-Zhang vol of asset i. Log-transform ensures: (1) the series is approximately stationary (log-vol is more normally distributed than vol in levels), (2) the VAR residuals are better-behaved, (3) the FEVD decomposition has a cleaner economic interpretation (shocks in log-vol space are proportional rather than absolute).

The N-dimensional panel: Y*t = (y*{1,t}, ..., y\_{N,t})' ∈ ℝ^N

Define the rolling estimation window: W ∈ {126, 252, 504} days. At each date T, use Y\_{T-W+1}, ..., Y_T as the estimation sample.

---

### Step 2 — VAR(p) estimation

Fit a VAR of order p to the rolling window sample:

Y*t = c + A₁ Y*{t-1} + A₂ Y*{t-2} + ... + Aₚ Y*{t-p} + u_t, u_t ~ (0, Σ_u)

where c ∈ ℝ^N, A_l ∈ ℝ^{N×N} for l = 1,...,p, and Σ_u is the N×N residual covariance matrix.

**OLS estimation (equation by equation):** For each equation i:

[c_i, A_{i,1,1}, ..., A_{i,p,N}]' = (Z'Z)^{-1} Z' y_i

where Z = [1, Y_{t-1}', ..., Y_{t-p}'] is the (W-p) × (1+Np) design matrix and y*i is the (W-p)×1 vector of y*{i,t}.

**Lag order selection:** BIC over p ∈ {1,2,3,4,5}:

BIC(p) = ln|Σ̂_u(p)| + p × N² × ln(W-p) / (W-p)

where |Σ̂*u(p)| is the determinant of the OLS residual covariance matrix with lag p. Choose p\* = argmin*{p∈{1,...,5}} BIC(p).

Estimate Σ_u: Σ̂_u = (1/(W-p*-Np*-1)) × U'U where U is the (W-p\*)×N matrix of OLS residuals.

---

### Step 3 — Generalized Forecast Error Variance Decomposition (GFEVD)

The Pesaran-Shin (1998) generalized FEVD is ordering-invariant (unlike Cholesky-based FEVD). It measures the fraction of asset i's forecast error variance at horizon H attributable to shocks originating from asset j.

**MA representation of the VAR:**

Y*t = Σ*{h=0}^{∞} Φ*h u*{t-h}

where the MA coefficient matrices Φ_h satisfy:

Φ_0 = I_N

Φ*h = Σ*{l=1}^{min(h,p)} A*l Φ*{h-l} for h ≥ 1

In practice, truncate at H_max = max(H, 50) lags (the GFEVD at horizon H requires MA coefficients up to H steps).

**Generalized FEVD at horizon H:**

The raw (unnormalized) GFEVD entry (fraction of asset i's H-step FEVD from asset j):

θ^H*{ij} = (σ*{jj})^{-1} × Σ*{h=0}^{H-1} (e_i' Φ_h Σ_u e_j)² / Σ*{h=0}^{H-1} (e_i' Φ_h Σ_u Φ_h' e_i)

where σ*{jj} = [Σ_u]*{jj} is the j-th diagonal element of Σ_u, and e_i is the i-th standard basis vector in ℝ^N.

The numerator (e_i' Φ_h Σ_u e_j)² = (Σ_u-weighted impulse response from asset j to asset i at horizon h)².

The denominator Σ\_{h=0}^{H-1} e_i' Φ_h Σ_u Φ_h' e_i = total forecast error variance of asset i at horizon H.

**Row-normalization:**

θ̃^H*{ij} = θ^H*{ij} / Σ*{j=1}^{N} θ^H*{ij}

This ensures Σ*{j=1}^{N} θ̃^H*{ij} = 1 for all i (each row sums to 1, so the off-diagonal elements represent the total fraction explained by spillovers and 1 − θ̃^H\_{ii} is the own-variance fraction explained by spillovers from others).

Use H = 10 trading days as the default FEVD horizon (following Diebold and Yilmaz, 2012).

---

### Step 4 — Connectedness measures

**Total connectedness index:**

C*t = [Σ*{i=1}^{N} Σ*{j≠i} θ̃^H*{ij}] / N × 100

This is the fraction of total forecast error variance due to cross-asset spillovers (as opposed to own-asset shocks). C_t = 0 means all assets are completely independent. C_t = 100 means no asset's variance is explained by its own past — pure spillover.

Typical values for a 10-asset global equity panel: C_t ∈ [40, 70] in calm markets, rising to [70, 90] during crises.

**From-spillovers (received by asset i):**

C*{others→i,t} = Σ*{j≠i} θ̃^H\_{ji} / N × 100

Wait — the correct formula is the sum of what i receives from all j ≠ i:

C*{from,i,t} = Σ*{j≠i} θ̃^H*{ij} = 1 − θ̃^H*{ii}

(From-spillover to asset i is the sum of off-diagonal elements in row i, which equals 1 minus the own-variance fraction.)

**To-spillovers (transmitted by asset i):**

C*{to,i,t} = Σ*{j≠i} θ̃^H\_{ji}

(To-spillover from asset i is the sum of column i's off-diagonal elements — how much of each other asset's FEVD is attributable to asset i's shocks.)

**Net spillover:**

NET*{i,t} = C*{to,i,t} − C\_{from,i,t}

NET*{i,t} > 0: asset i is a net transmitter of volatility shocks to the rest of the system.
NET*{i,t} < 0: asset i is a net receiver — it absorbs shocks from the rest of the system.

The asset with the highest NET is the current primary systemic risk transmitter — the most important cross-asset risk signal in the module.

---

### Step 5 — Rolling daily update

At each date T (the most recent observation date):

1. Extract the rolling window of log-vol data: Y\_{T-W+1:T}.
2. Select optimal lag p\* by BIC.
3. Estimate VAR parameters A₁,...,Aₚ and Σ_u by OLS.
4. Compute MA coefficients Φ*0,...,Φ*{H-1}.
5. Compute θ^H\_{ij} for all N² pairs.
6. Row-normalize to θ̃^H\_{ij}.
7. Compute C*T, C*{from,i,T}, C*{to,i,T}, NET*{i,T} for all i.

The rolling update produces time series {C*t}, {NET*{i,t}}, {θ̃^H\_{ij,t}} — the connectedness dynamics over the full history.

---

### Step 6 — 10-year percentile of the total connectedness index

At each date T, compute the percentile of C_T within its own trailing 10-year history (2,520 trading days):

Pct_C(T) = #{t ∈ [T-2520, T-1] : C_t < C_T} / 2520 × 100

Alert threshold: when C_T crosses the user-set percentile (default: 75th percentile of its own history), fire an elevated-spillover alert.

---

### Outputs

**Total connectedness index time series:** Daily C_t over the full rolling history. Secondary y-axis shows the 10-year percentile Pct_C(t). Crisis dates annotated as vertical dashed lines — each corresponds to a visible spike in C_t, self-validating the monitor. Horizontal dashed alert line at the user threshold. Historical threshold breaches highlighted in red.

**Net spillover ranking table:** N rows ranked by NET*{i,T} (descending — largest positive at top). Columns: asset name, C*{from,i,T}, C*{to,i,T}, NET*{i,T}, 1-month change in NET\_{i,T}. Color: red for NET > 0 (transmitter), blue for NET < 0 (receiver). The top-ranked asset (largest NET) is labeled "Primary Systemic Risk Transmitter."

**Dynamic connectedness network:** N nodes arranged by a force-directed layout (forces proportional to FEVD magnitude — heavily connected asset pairs are positioned closer together). Node size proportional to C*{from,i,T} (total received spillover). Edge direction from j to i when θ̃^H*{ij} > threshold (default: 0.05). Edge color: red for net transmission from j to i (θ̃^H*{ij} > θ̃^H*{ji}), blue for net transmission from i to j. Edge thickness proportional to |θ̃^H*{ij} − θ̃^H*{ji}|. Static snapshot at current date; time-lapse animation available.

**Pairwise FEVD heatmap:** N×N matrix where cell (i,j) = θ̃^H\_{ij,T}. Row i represents how much of asset i's forecast error variance is explained by each column asset j. Diagonal = own-variance fraction (green). Off-diagonal cells with θ̃ > 0.10 are labeled and deep red — these are the dominant spillover transmission channels currently active.

**Rolling to/from decomposition chart:** For a user-selected asset i: stacked area chart of C*{from,i,t} (blue, bottom) and C*{to,i,t} (red, top) over rolling history. An asset whose C*{from} is rising while C*{to} is falling is absorbing shocks from the rest of the system (receiver role) — a classic late-cycle stress pattern for "safe haven" assets.

**Connectedness regime alert:** When C_T crosses the top quartile of its own history: a summary panel lists the top 5 pairwise θ̃ values driving the elevated reading, the full NET ranking, and the historical distribution of multi-asset portfolio returns in the 30 days following a top-quartile C reading (computed empirically from all past instances where Pct_C(t) > 75).

---

### Data map

| Series                               | Source                       | Ticker / Code                | Frequency |
| ------------------------------------ | ---------------------------- | ---------------------------- | --------- |
| Daily OHLCV for all N assets         | Yahoo Finance / Stooq / FRED | Per ticker                   | Daily     |
| Yang-Zhang vol series from Feature 1 | Internal output              | —                            | Daily     |
| FX daily rates                       | FRED / ECB SDW               | DEXUSEU, DEXJPUS, DEXUSUK    | Daily     |
| Commodity prices                     | FRED                         | GOLDAMGBD228NLBM, DCOILWTICO | Daily     |
| Credit spreads (CDX IG/HY proxy)     | FRED                         | BAMLC0A0CM, BAMLH0A0HYM2     | Daily     |

---

## FEATURE 7 — MULTIVARIATE VOLATILITY AND DYNAMIC CONDITIONAL CORRELATION ENGINE

### What you are building mathematically

Four parallel covariance estimation methods — sample, EWMA, Ledoit-Wolf shrinkage, and DCC-GARCH — with a built-in crisis vs. normal comparison and portfolio risk attribution.

---

### Step 1 — Return panel construction

For N assets with daily returns {r*{i,t}}*{t=1}^T, construct the N×T return matrix R. For the estimation window of length W, use R\_{T-W+1:T}.

Compute the sample mean vector: μ̂*i = (1/W) Σ_t r*{i,t} for each asset i.

Demean: ε*{i,t} = r*{i,t} − μ̂_i. The N×W matrix of demeaned returns: E.

---

### Step 2 — Sample covariance (baseline)

Ω̂_sample = (1/(W-1)) × E E'

This is the standard N×N sample covariance matrix. The corresponding sample correlation matrix:

R̂_sample[i,j] = Ω̂_sample[i,j] / √(Ω̂_sample[i,i] × Ω̂_sample[j,j])

For N large relative to W (N > W/5): the sample covariance has poor conditioning (small eigenvalues are biased downward, large eigenvalues are biased upward). The condition number κ(Ω̂_sample) can be very large, making the matrix near-singular.

**Condition number:** κ = λ_max / λ_min where λ_max and λ_min are the largest and smallest eigenvalues of Ω̂_sample.

---

### Step 3 — EWMA covariance

Define the EWMA decay factor λ ∈ (0,1). Half-life: τ = −ln(2)/ln(λ) days. For λ = 0.94: τ ≈ 11 days. For λ = 0.97: τ ≈ 22.7 days.

Unnormalized EWMA weights: w_t = (1−λ) × λ^{T-t} for t = 1,...,T (recent dates get higher weight)

Normalized: w̃_t = w_t / Σ_t w_t = (1−λ) × λ^{T-t} / (1 − λ^T)

EWMA covariance: Ω̂*EWMA[i,j] = Σ_t w̃_t × ε*{i,t} × ε\_{j,t}

Recursive update form (computationally efficient for real-time updating):

Ω̂_EWMA,T = λ × Ω̂_EWMA,T-1 + (1−λ) × ε_T ε_T'

Initialize Ω̂_EWMA,1 = Ω̂_sample on the first M_init = 63 days.

The EWMA correlation matrix:

R̂_EWMA[i,j] = Ω̂_EWMA[i,j] / √(Ω̂_EWMA[i,i] × Ω̂_EWMA[j,j])

---

### Step 4 — Ledoit-Wolf shrinkage

The Oracle Approximating Shrinkage (OAS) estimator of Chen, Wiesel, Eldar, and Hero (2010), which improves on the original Ledoit-Wolf (2004) formula:

Target matrix F = (tr(Ω̂_sample) / N) × I_N (scaled identity — each diagonal element equals the average sample variance)

OAS shrinkage intensity:

α\*\_OAS = [(1 − 2/N) × tr(Ω̂²_sample) + tr²(Ω̂_sample)] / [(W + 1 − 2/N) × (tr(Ω̂²_sample) − tr²(Ω̂_sample) / N)]

Shrinkage estimator:

Ω̂_LW = (1 − α*\_OAS) × Ω̂_sample + α*\_OAS × F

For W >> N (time series much longer than cross-section): α\*\_OAS → 0 and Ω̂_LW → Ω̂_sample (no shrinkage needed — sample covariance is well-conditioned).

For N ≈ W or N > W: α\*\_OAS is substantial (e.g., 0.3–0.6), providing significant regularization. The shrinkage pulls all eigenvalues toward the average eigenvalue — reducing the spread between the largest and smallest eigenvalues, improving condition number.

The LW correlation matrix: R̂_LW[i,j] = Ω̂_LW[i,j] / √(Ω̂_LW[i,i] × Ω̂_LW[j,j])

---

### Step 5 — DCC-GARCH

**Stage 1 — Univariate GARCH(1,1) per asset:**

For each asset i, fit GARCH(1,1) to the daily return series r\_{i,t}:

σ²*{i,t} = ω_i + α_i × ε²*{i,t-1} + β*i × σ²*{i,t-1}

MLE as described in Feature 2, Step 2. Extract the standardized residuals:

ẑ*{i,t} = ε*{i,t} / σ̂\_{i,t}

Collect the N×T matrix of standardized residuals: Ẑ.

**Stage 2 — Dynamic correlation:**

Compute the unconditional correlation matrix of standardized residuals:

R̄ = (1/T) × Ẑ Ẑ'

This is the long-run (unconditional) correlation matrix. It is used as the target of the DCC recursion.

DCC quasi-correlation matrix recursion:

Q*t = (1 − a − b) × R̄ + a × ẑ*{t-1} ẑ'_{t-1} + b × Q_{t-1}

where a ≥ 0, b ≥ 0, a + b < 1 are the DCC parameters. Initialize Q_1 = R̄.

Interpretation:
(1 − a − b) × R̄: the mean-reverting target component (pulls Q*t back toward the long-run correlation).
a × ẑ*{t-1} ẑ'_{t-1}: the innovation component (updates the quasi-correlation based on yesterday's joint innovation).
b × Q_{t-1}: the persistence component (yesterday's quasi-correlation carries forward).

Standardize Q_t to a proper correlation matrix:

R_t = diag(Q_t)^{-1/2} × Q_t × diag(Q_t)^{-1/2}

where diag(Q_t) is the diagonal matrix with the same diagonal as Q_t. By construction: R_t[i,i] = 1 for all i and |R_t[i,j]| ≤ 1 for all i, j.

Full conditional covariance matrix:

Ω_DCC,t = D_t × R_t × D_t

where D*t = diag(σ̂*{1,t}, ..., σ̂\_{N,t}) is the N×N diagonal matrix of GARCH-estimated conditional standard deviations.

**DCC parameter estimation:** MLE in two stages.

Stage 1 log-likelihood (individual GARCH): ℓ*1 = Σ_i Σ_t [−(1/2)(ln(2π) + ln(σ²*{i,t}) + ε²*{i,t}/σ²*{i,t})]

Stage 2 log-likelihood (DCC, conditional on Stage 1 estimates):

ℓ_2 = −(1/2) Σ_t [ln|R_t| + ẑ'_t R_t^{-1} ẑ_t − ẑ'_t ẑ_t]

The last term −ẑ'\_t ẑ_t is subtracted because it is already accounted for in the Stage 1 likelihood. Maximize ℓ_2 over (a, b) subject to a + b < 1, a ≥ 0, b ≥ 0, using L-BFGS-B.

---

### Step 6 — Crisis vs. normal correlation comparison

**Define crisis periods:** Any date t where VIX_t > 30 AND at least one asset's rolling 21-day vol is in the top decile of its 10-year history.

**Define normal periods:** The complement.

**Crisis correlation matrix:**

Ω*crisis = (1/T_crisis) × Σ*{t ∈ crisis dates} ε_t ε_t'

R_crisis[i,j] = Ω_crisis[i,j] / √(Ω_crisis[i,i] × Ω_crisis[j,j])

**Normal correlation matrix:**

R_normal[i,j] similarly computed on non-crisis dates.

**Correlation amplification matrix:**

ΔCorr[i,j] = R_crisis[i,j] − R_normal[i,j]

Large positive ΔCorr[i,j] (e.g., > 0.3) means the diversification benefit from holding both assets i and j collapses during crises — the hidden concentration risk.

**Statistical test for amplification:** Fisher's Z-transformation:

Z*{crisis}[i,j] = (1/2) × ln((1 + R_crisis[i,j]) / (1 − R_crisis[i,j]))
Z*{normal}[i,j] = (1/2) × ln((1 + R_normal[i,j]) / (1 − R_normal[i,j]))

Test statistic: Z_test[i,j] = (Z_crisis[i,j] − Z_normal[i,j]) / √(1/(T_crisis − 3) + 1/(T_normal − 3))

Under the null of equal correlations: Z_test ~ N(0,1). Bonferroni-corrected significance level: 0.05 / (N(N-1)/2) for N(N-1)/2 pairwise tests.

---

### Step 7 — Eigenvalue decomposition and condition number

**Eigenvalue decomposition of Ω̂_DCC,T:**

Ω̂_DCC,T = V Λ V'

where Λ = diag(λ₁, ..., λ_N) is the diagonal matrix of eigenvalues in descending order and V = [v₁, ..., v_N] is the matrix of eigenvectors.

Cumulative variance explained: CVE(k) = Σ*{j=1}^{k} λ_j / Σ*{j=1}^{N} λ_j

A single dominant eigenvalue (CVE(1) > 0.70): all assets are effectively one correlated risk factor — the portfolio has less diversification benefit than it appears.

**Condition number:** κ(Ω̂_DCC,T) = λ₁ / λ_N

Rolling condition number history: plot κ_t over the full estimation window. Spikes in κ during crisis periods indicate that the correlation matrix becomes near-singular exactly when reliable estimation matters most.

---

### Step 8 — Portfolio risk attribution

For a portfolio with weight vector w = (w₁, ..., w_N)' (where Σ_i w_i = 1 for long-only):

**Total portfolio variance:**

σ²_p = w' Ω_DCC,T w

**Marginal risk contribution (Euler decomposition):**

MRC_i = w_i × (Ω_DCC,T w)\_i / σ_p

where (Ω_DCC,T w)\_i is the i-th element of the vector Ω_DCC,T w. By Euler's theorem: Σ_i MRC_i = σ_p (marginal risk contributions sum to total portfolio vol).

MRC_i as a fraction of total portfolio vol: fMRC_i = MRC_i / σ_p = w_i × (Ω_DCC,T w)\_i / σ²_p.

Σ_i fMRC_i = 1 always.

**Pairwise covariance contribution:**

The contribution of the (i,j) covariance term to total portfolio variance:

CC\_{ij} = w_i × w_j × Ω_DCC,T[i,j] (for i ≠ j, multiply by 2 since the pair appears twice in the quadratic form)

This N×N matrix sums to σ²*p. The largest off-diagonal CC*{ij} cells identify the dominant covariance risk concentration.

**Minimum variance portfolio:**

Analytical solution: w*MV = Ω^{-1}*{DCC,T} 1 / (1' Ω^{-1}\_{DCC,T} 1)

where 1 is the N×1 vector of ones. This requires Ω*DCC,T to be invertible (guaranteed by DCC construction). σ²_MV = 1 / (1' Ω^{-1}*{DCC,T} 1).

Equal-weight portfolio vol: σ*EW = √(w*{EW}' Ω*DCC,T w*{EW}) where w\_{EW} = (1/N)×1.

Diversification ratio: DR = (w' σ_diag) / √(w' Ω w) where σ_diag = (σ̂₁, ..., σ̂_N)' is the vector of individual asset vols. DR > 1 always for a non-trivially correlated portfolio; DR close to 1 means minimal diversification benefit; DR > 1.5 means substantial diversification benefit.

---

### Outputs

**Correlation matrix heatmap — four tabs (Sample, EWMA, LW, DCC):** Each tab shows the N×N correlation matrix. Color: deep blue at ρ = −1, white at ρ = 0, deep red at ρ = +1. Cell annotations for all |ρ| > 0.3. Row and column labels are asset names. Below each heatmap: the condition number κ and the average off-diagonal correlation.

**Normal vs. crisis correlation comparison — three panels side by side:** Left: R_normal. Center: R_crisis. Right: ΔCorr = R_crisis − R_normal. Cells in the right panel with |ΔCorr| > 0.3 annotated and highlighted — these are the hidden concentration risks.

**DCC time series — any selected asset pair (i,j):** Daily R_DCC,t[i,j] over the full estimation window. Horizontal dashed lines at the normal-period mean and crisis-period mean from Step 6. The dynamic nature of DCC (fluctuating between these levels) visually demonstrates why static correlation assumptions are inadequate.

**Eigenvalue bar chart:** N bars in descending order (λ₁ to λ_N). Overlaid cumulative variance explained curve (secondary y-axis). Vertical dashed line at the k* where CVE(k*) = 90%.

**Rolling condition number chart:** Daily κ_t over the full history. Annotated crisis dates. The spikes in κ during crisis periods are the empirical case for why portfolio optimization becomes unreliable exactly when risk management matters most.

**Portfolio risk attribution dashboard (when portfolio weights are provided):** Waterfall chart: each asset i's fMRC_i as a percentage bar. Sorted from largest contributor to smallest. Color: red for assets above their equal-weight MRC share (1/N), blue for assets below. A risk-budgeted portfolio should have uniform fMRC_i = 1/N.

**Minimum variance portfolio comparison:** Table with three columns: equal-weight, current portfolio (user-input), minimum variance. Rows: projected annualized vol, vol as percentile of 10-year history, diversification ratio, top 3 holdings by weight. The σ_MV cell is green by construction (it is the theoretical minimum achievable vol with this asset universe).

---

### Data map

| Series                                   | Source                       | Ticker / Code | Frequency |
| ---------------------------------------- | ---------------------------- | ------------- | --------- |
| Daily returns for all N assets           | Yahoo Finance / Stooq / FRED | Per ticker    | Daily     |
| VIX for crisis period definition         | FRED                         | VIXCLS        | Daily     |
| Sufficient history (252+ days per asset) | Same                         | Same          | Daily     |

---

## FEATURE 8 — VOLATILITY STRESS TESTING AND SCENARIO ENGINE

### What you are building mathematically

Four stress scenario types — historical preset, Mahalanobis historical analog, parametric, and reverse stress — each propagated through the DCC covariance system from Feature 7, with a contagion VAR from Feature 6 for impulse response mapping.

---

### Step 1 — Historical preset stress replay

For a selected historical stress episode (e.g., GFC Sep–Dec 2008, COVID crash Feb–Mar 2020, Liberation Day Apr–May 2025), retrieve the realized daily returns and vol paths of each asset i:

r*{i,t}^{hist} for t ∈ [t*{start}, t\_{end}]

σ\_{YZ,i,t}^{hist} = Yang-Zhang vol of asset i during the stress episode (computed from Feature 1 on historical data)

Apply these historical vol paths to the current portfolio weights w (user-input or from Feature 7):

**Stressed portfolio return on day t:**

R*p^{stress,t} = Σ_i w_i × r*{i,t}^{hist}

**Cumulative stressed portfolio return:**

R*p^{stress,cumul} = Π*{t=t*{start}}^{t*{end}} (1 + R_p^{stress,t}) − 1

**Maximum drawdown during the episode:**

MDD = min*{τ∈[t*{start},t*{end}]} [Π*{t=t\_{start}}^{τ} (1 + R_p^{stress,t}) − 1]

(The worst cumulative loss from inception of the episode to any point within it.)

**Average annualized portfolio vol during the episode:**

σ*p^{stress} = √(252 × (1/(t*{end}−t\_{start}+1)) × Σ_t (R_p^{stress,t})²) (approximately, using the stressed returns as a proxy)

---

### Step 2 — Historical analog matching via Mahalanobis distance

The user defines a scenario by specifying changes in macro variables over a 30-day horizon:

Scenario vector: x_scenario = (ΔVIX, Δ(10Y yield), Δ(Credit spread), Δ(DXY), ΔEquity return) ∈ ℝ^M, M = 5

At each historical date t (rolling 30-day windows over the full history), compute the realized macro variable change vector:

x*t = (VIX*{t+30} − VIX*t, (DGS10*{t+30} − DGS10*t), Δ(BAMLC0A0CM)*{t,t+30}, Δ(DXY)_{t,t+30}, R_{equity,t,t+30})

This gives a history of macro change vectors {x*t}*{t=1}^{T-30}.

Compute the sample covariance matrix of the macro change vectors:

Σ_x = (1/(T-30)) × Σ_t (x_t − x̄)(x_t − x̄)'

**Mahalanobis distance between the scenario and each historical window:**

d²_M(t) = (x_scenario − x_t)' Σ_x^{-1} (x_scenario − x_t)

Sort all historical windows by d²_M ascending. The top K closest analogs (K = 5, 10, or 20 — user-set) form the analog set Ω_analog.

**Analog-implied vol scenario:**

For each asset i and each analog window t ∈ Ω*analog: retrieve the vol path {σ*{YZ,i,s}}\_{s=t}^{t+30}.

Average vol path across K analogs:

σ̄*{vol,i,s} = (1/K) × Σ*{t ∈ Ω*analog} σ*{YZ,i,t+s} for s = 1,...,30

This is the scenario-implied expected vol path for asset i, averaged across the K most historically similar macro environments.

**90% confidence interval on vol path:** For each day s within the 30-day window, compute the 5th and 95th percentile of {σ\_{YZ,i,t+s} : t ∈ Ω_analog} across the K analog windows.

**Analog-implied portfolio return:**

For each analog window t: compute the 30-day portfolio return R*{p,t}^{analog} = Π*{s=1}^{30} (1 + Σ*i w_i × r*{i,t+s}) − 1.

Distribution of analog portfolio returns: {R\_{p,t}^{analog} : t ∈ Ω_analog}. Mean, 10th percentile, and 90th percentile form the scenario return distribution.

**Plain-language summary:** "The most similar historical episode to your scenario is [t*] (Mahalanobis distance = [d*]). In that episode, average vol rose [X]% and the portfolio lost [Y]% over 30 days."

t* = argmin_t d²_M(t). [X] = average annualized vol during the t* window minus pre-episode vol. [Y] = R\_{p,t\*}^{analog}.

---

### Step 3 — Parametric stress test

The user directly specifies a vol shock vector: Δσ = (Δσ₁, ..., Δσ_N)' in annualized vol points or in standard deviations of each asset's historical vol distribution.

**Convert to standard deviations if needed:**

For shock specified in annualized vol points: Δσ_i in bps → in levels: Δσ_i / 10000 × √252 per day.

For shock specified in standard deviations of historical vol: Δσ*i^{SD} → in vol levels: Δσ_i = Δσ_i^{SD} × σ*{vol,i}^{hist} where σ\_{vol,i}^{hist} is the historical standard deviation of σ_YZ,i.

**Stressed covariance matrix:**

The stressed individual vol of asset i: σ̂*i^{stress} = σ̂*{i,T} + Δσ_i (current GARCH vol + shock)

Stressed diagonal matrix: D^{stress} = diag(σ̂_1^{stress}, ..., σ̂_N^{stress})

The stressed covariance matrix (using the current DCC correlation R_T):

Ω^{stress} = D^{stress} × R_T × D^{stress}

This assumes the correlation matrix is unchanged under the stress scenario — a conservative assumption consistent with the normal-period correlation. Alternatively, use the crisis correlation matrix R_crisis from Feature 7 for a more severe scenario (correlation jumps to crisis levels simultaneously with the vol shock).

**Stressed portfolio variance:**

σ²_p^{stress} = w' Ω^{stress} w

**Stressed marginal risk contributions:**

MRC_i^{stress} = w_i × (Ω^{stress} w)\_i / σ_p^{stress}

**Portfolio P&L under the vol shock:**

The vol-induced P&L is not the same as the return P&L. The vol shock changes the required risk capital (the VaR and CVaR), not the portfolio return directly.

Vol-induced VaR change:

ΔVaR*{99,p} = −z*{0.01} × (σ_p^{stress} − σ_p^{current}) × √H × AUM

where z\_{0.01} = 2.326 (Gaussian 1st percentile), H = 1 day, AUM is the portfolio size.

The return-induced P&L under a parametric scenario is modeled separately: if the vol shock is accompanied by an expected mean return shift (e.g., a 15% equity drawdown with a simultaneous spike in vol), the user inputs both Δr_i (return shock) and Δσ_i (vol shock):

ΔP_return = Σ_i w_i × Δr_i

ΔP_vol = ΔVaR change (the risk-capital impact)

---

### Step 4 — Reverse stress test

Find the minimum-probability vol shock that produces a specified portfolio loss L (expressed as a fraction of AUM, e.g., L = −0.15 for a 15% loss).

**Problem formulation:**

The portfolio return under vol shock Δσ (assuming returns are proportional to vol through the leverage effect):

R*p(Δσ) ≈ Σ_i w_i × (β*{lev,i} × Δσ_i)

where β\_{lev,i} is the leverage effect coefficient from Feature 3, Step 6 — the expected return change per unit vol change for asset i.

Constraint: R*p(Δσ) = L → Σ_i w_i × β*{lev,i} × Δσ_i = L

**Objective: minimum historical probability scenario.**

Under the Gaussian model for vol shocks: the probability of a vol shock vector Δσ is proportional to exp(−(1/2) Δσ' Ω_vol^{-1} Δσ) where Ω_vol is the historical covariance matrix of the N-dimensional daily vol change series {Δσ_t = σ_YZ,t − σ_YZ,t-1}.

Minimize the Mahalanobis norm of the shock: (1/2) Δσ' Ω_vol^{-1} Δσ

Subject to: (β_lev ∘ w)' Δσ = L, where ∘ denotes elementwise multiplication.

This is a quadratic program with one linear equality constraint. KKT conditions give the closed-form solution:

Define c = Ω_vol (w ∘ β_lev): the covariance-weighted exposure vector.

Δσ\* = L × Ω_vol (w ∘ β_lev) / ((w ∘ β_lev)' Ω_vol (w ∘ β_lev))

= L × c / (c' (w ∘ β_lev))

The Mahalanobis distance of the optimal reverse stress scenario:

d²* = Δσ*' Ω_vol^{-1} Δσ\* = L² / ((w ∘ β_lev)' Ω_vol (w ∘ β_lev))

Under the Gaussian model: d²\* ~ χ²_N, so the probability of observing a shock at least as extreme:

P*reverse = 1 − CDF*{χ²_N}(d²\*)

**Plain-language output:** "This portfolio loses [L]% if [asset A] vol spikes by [Δσ*_A] annualized vol points and [asset B] vol spikes by [Δσ*_B] annualized vol points simultaneously — a combination observed in [P_reverse × 100]% of rolling 30-day windows historically."

---

### Step 5 — Contagion impulse response

Using the VAR system from Feature 6 (already estimated):

For a 1-standard-deviation shock to asset j's log-vol:

u*j = (0, ..., 0, σ̂*{u,j}, 0, ..., 0)' (the shock vector with only the j-th element nonzero)

where σ̂*{u,j} = √[Σ̂_u]*{jj} is the estimated standard deviation of the j-th VAR residual.

**Impulse response of asset i's log-vol to asset j's shock at horizon h:**

IRF*{i,j}(h) = e_i' Φ_h u_j = σ̂*{u,j} × [Φ_h]\_{ij}

where Φ_h are the MA coefficient matrices from Feature 6, Step 3.

Convert from log-vol IRF to vol level IRF: approximate via the delta method:

ΔσYZ*{i,j}(h) ≈ σ_YZ,i,T × IRF*{i,j}(h) (proportional approximation for small shocks)

Compute for h = 1, 5, 10, 21 trading days.

**Bootstrap 90% confidence bands:**

Draw B = 1000 residual bootstrap samples: for each bootstrap b, resample the VAR residuals {û*t^{(b)}} with replacement, reconstruct the VAR time series, re-estimate {A_l^{(b)}}, compute {Φ_h^{(b)}}, extract IRF*{i,j}^{(b)}(h).

The 5th and 95th percentiles of {IRF*{i,j}^{(b)}(h)}*{b=1}^{B} form the 90% confidence band at each horizon h.

---

### Outputs

**Vol shock bar chart:** N bars showing Δσ_i^{stress} (the vol shock for each asset, in annualized bps) for the selected scenario. Color: red for positive shock (vol spike), green for negative shock (vol compression). Historical 5th and 95th percentile bands of Δσ_i shown as error bars around each bar.

**Portfolio P&L attribution waterfall:** Total portfolio P&L under the scenario decomposed by asset. Two bars per asset: the return-induced P&L (Σ_i w_i × Δr_i^{scenario}) and the vol-induced risk capital change (ΔVaR_i^{stress}). Sorted from most negative to most positive. Net P&L shown as the final bar.

**Historical analog comparison panel:** K rows (one per analog), sorted by Mahalanobis distance. Columns: date, d²_M distance, equity return in the 30 days following the analog, average vol change across assets, max drawdown. Each row expandable to show the full 30-day vol path per asset. Bottom row: mean across all K analogs. The "most similar episode" row is highlighted in bold.

**Reverse stress scenario output:** A formatted summary card: the reverse stress shock vector Δσ* displayed as a bar chart of per-asset vol spikes; the Mahalanobis distance d²* and historical probability P_reverse; the plain-language interpretation. A secondary chart shows the trade-off curve: portfolio loss L on the x-axis, minimum d²\*(L) on the y-axis — the "stress efficiency frontier" that shows how severe a shock must be to produce each level of portfolio loss.

**Contagion impulse response chart:** For the user-selected originating asset j: N−1 sub-panels, one per receiving asset i. Each sub-panel shows IRF\_{i,j}(h) at h = 1, 5, 10, 21 days with 90% bootstrap confidence bands. Assets whose confidence band excludes zero at h = 5 are labeled "significant contagion."

**Multi-scenario comparison table:** Up to 6 scenarios side by side. Rows: total portfolio P&L, maximum single-asset vol spike, average DCC correlation under stress (compare to normal-period average), estimated days to return to pre-stress vol (inferred from GARCH mean-reversion speed), stress VaR at 95%, stress CVaR at 99%. The table provides a direct comparison of scenario severity.

**Stress VaR and CVaR (Monte Carlo):**

Under the stressed DCC covariance Ω^{stress}, simulate S = 100,000 portfolio returns:

R_p^{(s)} ~ N(0, w' Ω^{stress} w) (for each simulation draw one portfolio return from the stressed Gaussian)

More precisely, simulate the full N-dimensional return vector r^{(s)} ~ N(0, Ω^{stress}) and compute R_p^{(s)} = w' r^{(s)}.

Stress VaR*{95%}: the 5th percentile of {R_p^{(s)}}*{s=1}^{S} (the loss exceeded by only 5% of simulations).

Stress CVaR*{99%}: mean{R_p^{(s)} : R_p^{(s)} < VaR*{99%}} — the expected loss conditional on exceeding the 99% VaR.

Both expressed in annualized percentage loss and in absolute dollar terms (× AUM).

---

### Data map

| Series                                                    | Source                | Ticker / Code                          | Frequency |
| --------------------------------------------------------- | --------------------- | -------------------------------------- | --------- |
| Daily returns for all portfolio assets                    | Yahoo Finance / Stooq | Per ticker                             | Daily     |
| DCC covariance matrix from Feature 7                      | Internal output       | —                                      | Daily     |
| Macro variable history (VIX, yields, credit, DXY, equity) | FRED                  | VIXCLS, DGS10, DGS2, BAMLC0A0CM, ^GSPC | Daily     |
| VAR system from Feature 6                                 | Internal output       | —                                      | Daily     |
| Vol series from Feature 1                                 | Internal output       | —                                      | Daily     |

---

## FEATURE 9 — PORTFOLIO VOLATILITY BUDGET MONITOR AND DYNAMIC RISK TARGETING ENGINE

### What you are building mathematically

A real-time vol-targeting system that computes the daily scaling factor needed to bring portfolio vol to a regime-conditional target, decomposes the current vol budget by position, and backtests the vol-targeting overlay vs. the unscaled baseline.

---

### Step 1 — Portfolio realized vol computation

From Feature 7's DCC covariance matrix Ω_DCC,t and the portfolio weight vector w_t:

Portfolio realized variance (instantaneous, based on the DCC estimate at t):

σ²_p,t = w_t' Ω_DCC,t w_t

Portfolio realized vol: σ_p,t = √(σ²_p,t), annualized (since Ω_DCC,t contains annualized covariances: each element is 252 × daily covariance).

Alternatively, the trailing 21-day realized portfolio vol from actual portfolio returns:

σ^{21d}_{p,t} = √(252 × (1/21) × Σ_{s=t-20}^{t} (R\_{p,s} − R̄_p)²)

where R*{p,s} = Σ_i w*{i,s} × r\_{i,s} is the daily portfolio return. The 21-day trailing realized vol is the empirical counterpart to the instantaneous DCC-based estimate.

---

### Step 2 — One-day-ahead portfolio vol forecast

For each asset i, the one-step-ahead GARCH conditional variance σ²\_{i,t+1} (from Feature 2):

σ²*{i,t+1} = ω̂_i + α̂_i × ε²*{i,t} + β̂*i × σ²*{i,t}

The one-step-ahead DCC covariance matrix:

Ω*DCC,t+1 = D*{t+1} × R*{t+1} × D*{t+1}

where D*{t+1} = diag(σ̂*{1,t+1}, ..., σ̂*{N,t+1}) and R*{t+1} is estimated from the DCC recursion:

Q*{t+1} = (1 − a − b) × R̄ + a × ẑ_t ẑ'\_t + b × Q_t
R*{t+1} = diag(Q*{t+1})^{-1/2} × Q*{t+1} × diag(Q\_{t+1})^{-1/2}

One-day-ahead portfolio vol forecast:

σ̂\_{p,t+1} = √(w_t' Ω_DCC,t+1 w_t)

This is the key forecasting object: it is the best available prediction of tomorrow's portfolio volatility, used to compute the scaling factor.

---

### Step 3 — Regime-conditional vol target

From Feature 4, the composite regime probability vector at date t:

p_composite(t) = (p₁(t), ..., p_K(t)) ∈ ΔK

The user specifies K regime-conditional vol targets: σ^{target,1}, ..., σ^{target,K} (in annualized terms, e.g., 8%, 10%, 14%, 20% for K = 4 regimes).

Regime-conditional target at date t:

σ*target(t) = Σ*{k=1}^{K} p_k(t) × σ^{target,k}

This is a probability-weighted average of the per-regime targets. It varies smoothly over time as the regime probabilities evolve, rather than jumping discretely between two levels.

Example: if K = 3 and σ^{target} = (8%, 10%, 16%) for (low-vol, normal, high-vol) regimes:

p_composite(t) = (0.6, 0.3, 0.1) → σ_target(t) = 0.6×8% + 0.3×10% + 0.1×16% = 4.8% + 3% + 1.6% = 9.4%

The target adapts: in a rising-stress environment, the high-vol probability p_K(t) rises, pulling σ_target(t) upward, which reduces the scaling factor, deleveraging the portfolio before the crisis fully materializes.

---

### Step 4 — Vol-targeting scaling factor

λ*scale,t = σ_target(t) / σ̂*{p,t+1}

This is the ratio of the desired portfolio vol to the forecast portfolio vol. Interpretation:

λ_scale,t > 1: portfolio is under-target (forecast vol is below target) → scale up (add risk)
λ_scale,t < 1: portfolio is over-target (forecast vol is above target) → scale down (reduce risk)
λ_scale,t = 1: portfolio vol matches the target exactly

The scaled weight vector:

w_t^{scaled} = λ_scale,t × w_t

Constraint: if a gross exposure cap G_max is specified (e.g., G_max = 1.5 for long-only with leverage limit):

λ_scale,t^{constrained} = min(λ_scale,t, G_max / (w_t' 1)) (for long-only)

The post-scaling portfolio vol:

σ_p,t^{scaled} = λ_scale,t × σ_p,t ≈ σ_target(t)

(Exact equality only if σ̂\_{p,t+1} = σ_p,t, i.e., the forecast equals the current realized vol. In practice, the scaling is applied to the next day's weights using today's forecast, so there is a one-day lag.)

---

### Step 5 — Vol budget attribution (Euler decomposition)

The marginal risk contribution per position (same as Feature 7, Step 8):

MRC*{i,t} = w*{i,t} × (Ω_DCC,t w_t)\_i / σ_p,t

In annualized bps (basis points of vol):

MRC*{i,t}^{bps} = MRC*{i,t} × 10000

As a fraction of total portfolio vol: fMRC*{i,t} = MRC*{i,t} / σ_p,t

The user assigns a vol budget to each position: B_i (e.g., equal budget: B_i = 1/N for all i).

**Budget deviation per position:**

Dev*{i,t} = fMRC*{i,t} − B_i

Dev*{i,t} > 0: position i is consuming more vol budget than assigned (over-budget → candidate for reduction).
Dev*{i,t} < 0: position i is consuming less vol budget than assigned (under-budget → candidate for addition).

**Budget-realignment rebalancing proposal:** To move each position from w*{i,t} to a budget-aligned weight w*{i,t}^{budget}:

The budget-aligned weights satisfy: MRC\_{i,t}^{budget} / σ_p^{budget} = B_i for all i. This requires solving:

w\_{i,t}^{budget} × (Ω_DCC,t w^{budget})\_i / (w^{budget}' Ω_DCC,t w^{budget}) = B_i

This is generally solved iteratively: start from w_t^{budget} = w_t, then update each weight proportionally to its budget deviation until convergence (Jacobi-style iteration). Convergence is fast (10–20 iterations typically).

---

### Step 6 — Rebalancing trigger and cost

**Trigger 1 (fixed schedule):** Rebalance on a fixed frequency: daily, weekly (every 5 days), or monthly (every 21 days).

**Trigger 2 (signal-triggered):** Rebalance only when |σ_p,t − σ_target(t)| / σ_target(t) > X% (user-set, e.g., X = 20%), i.e., when the portfolio vol deviates from the target by more than X%.

**Transaction cost computation:**

One-way turnover from the current weights to the new scaled weights:

TO*t = (1/2) × Σ_i |w*{i,t}^{new} − w\_{i,t}|

where w*{i,t}^{new} = λ_scale,t × w*{i,t} (scaling) and/or w\_{i,t}^{budget} (budget realignment).

Estimated transaction cost (in bps per AUM):

TC*t = c*{explicit} × TO_t × 10000

where c\_{explicit} is the flat round-trip transaction cost in bps (user-set, e.g., 5 bps). The cost reduces the expected vol-targeting benefit: the net benefit is positive only when the vol-targeting alpha exceeds the rebalancing friction.

---

### Step 7 — Vol-targeting backtest

For each trading day t from t₀ to T:

1. Compute σ̂\_{p,t+1} from Feature 2/7 (one-day-ahead forecast as of date t).
2. Compute σ_target(t) from Feature 4 (regime-conditional target).
3. Compute λ*scale,t = σ_target(t) / σ̂*{p,t+1}.
4. Apply constraint: λ_scale,t^{constrained} = min(λ_scale,t, G_max / ‖w_t‖\_1).
5. Record: scaled portfolio weights w_t^{scaled} = λ_scale,t^{constrained} × w_t.
6. Compute the portfolio return from t to t+1 under scaled weights: R*p^{scaled,t+1} = (w_t^{scaled})' r*{t+1}.
7. Subtract transaction costs: R_p^{net,t+1} = R_p^{scaled,t+1} − TC_t × (1/252) (amortize cost over 1 day).

Baseline (unscaled equal-weight portfolio):

R*p^{EW,t+1} = (1/N × 1)' r*{t+1}

**Performance statistics for vol-targeted overlay vs. EW baseline:**

Annualized return: Σ_t R_p^{net} × 252/T vs. Σ_t R_p^{EW} × 252/T

Annualized vol: √(252 × Var(R_p^{net})) vs. √(252 × Var(R_p^{EW}))

Sharpe ratio: (annualized return − risk-free rate) / annualized vol

Maximum drawdown: min*{τ∈[t₀,T]} (Π*{t=t₀}^{τ}(1+R_p^{net,t}) − 1)

Calmar ratio: annualized return / |max drawdown|

---

### Outputs

**Portfolio vol dashboard — four large numerals:**

Numeral 1: Current 21-day trailing realized portfolio vol σ^{21d}\_{p,T} (annualized %, to 2 decimal places)

Numeral 2: DCC/GARCH one-day-ahead forecast σ̂\_{p,T+1} (annualized %)

Numeral 3: Regime-conditional vol target σ_target(T) (annualized %, updating daily)

Numeral 4: Scaling factor λ_scale,T (displayed as e.g., "0.76×" meaning "reduce portfolio exposure to 76% of current size to hit vol target")

These four numerals are the primary operational output of the entire module. A risk manager reads them at the start of each day.

**Vol-to-target gap gauge:** Signed horizontal bar: the gap (σ_p,T − σ_target(T)) × 100 in annualized bps. Positive (red) = over-target (too much risk). Negative (green) = under-target (underinvested relative to risk budget). The 7-day and 30-day trend in this gap shown as small arrows.

**Vol budget attribution waterfall:** N bars sorted from most over-budget to most under-budget. Each bar shows Dev\_{i,T} × 100 in annualized bps. The bar height represents how much vol budget that position is consuming beyond its assigned share. Red bars are candidates for weight reduction; blue bars are candidates for addition. The sum of all bars = 0 by construction (deviations sum to zero).

**Scaling factor history:** Daily time series of λ_scale,t over the full backtest period. A horizontal dashed line at λ = 1 (no action needed). Periods where λ < 1 (deleverage) are shaded red; these should coincide with high-vol regimes from Feature 4, self-validating the system. The correlation between λ_scale,t < 1 events and Feature 4's high-vol regime probability is the empirical validation metric.

**Regime-conditional target evolution:** Two time series on one chart: σ_target(t) (the regime-weighted target, varying daily) and σ_p,t (the actual portfolio vol). The gap between them drives λ_scale,t. When σ_target(t) falls (rising crisis probability) ahead of a vol spike in σ_p,t, the system is proactively deleveraging — the most important feature of the regime-conditional specification vs. a fixed target.

**Rebalancing recommendation panel:** A formatted table:
Row 1: Current weights w_t. Row 2: Scaled weights w_t^{scaled} = λ_scale,t × w_t. Row 3: Budget-aligned weights w_t^{budget}. Row 4: Weight change Δw_i = w_t^{scaled/budget} − w_t. Row 5: One-way turnover TO_t. Row 6: Estimated transaction cost TC_t (in bps). Row 7: Net-of-cost expected improvement in Sharpe ratio (estimated from historical relationship between λ_scale deviation and forward Sharpe improvement).

**Historical vol-targeting backtest summary:** Two cumulative return lines on one chart (net-of-cost vol-targeted vs. equal-weight baseline). Below the chart: a 5-row performance table:

| Metric            | Vol-Targeted | Equal-Weight |
| ----------------- | ------------ | ------------ |
| Annualized Return | X.X%         | X.X%         |
| Annualized Vol    | X.X%         | X.X%         |
| Sharpe Ratio      | X.XX         | X.XX         |
| Max Drawdown      | −X.X%        | −X.X%        |
| Calmar Ratio      | X.XX         | X.XX         |

---

### Data map

| Series                                    | Source                | Ticker / Code | Frequency |
| ----------------------------------------- | --------------------- | ------------- | --------- |
| Daily returns for all portfolio assets    | Yahoo Finance / Stooq | Per ticker    | Daily     |
| DCC covariance matrix from Feature 7      | Internal output       | —             | Daily     |
| Regime probability vector from Feature 4  | Internal output       | —             | Daily     |
| GARCH/HAR vol forecasts from Features 2–3 | Internal output       | —             | Daily     |

---

## MODULE INTEGRATION MAP

| Feature                        | Primary Input                          | Primary Dependency                     | Key Mathematical Objects                                           |
| ------------------------------ | -------------------------------------- | -------------------------------------- | ------------------------------------------------------------------ |
| 1. Multi-Estimator Vol Engine  | Daily OHLCV                            | None — foundational                    | u_t, d_t, h_t, l_t; 5 σ² estimator formulas; DM statistic; Agree_t |
| 2. GARCH Family Suite          | Daily returns; Feature 1 vol proxy     | Feature 1 for OOS evaluation           | 20 MLE problems; MCS; PIT u_t; VaR Kupiec/Christoffersen           |
| 3. HAR Forecasting Suite       | Feature 1 YZ vol series; daily returns | Feature 1 required; Feature 2 optional | 6 OLS regressions; NW SE; J_t jump proxy; R²_OOS                   |
| 4. Regime Detection Engine     | Feature 1 YZ vol; FRED macro           | Feature 1 required                     | SJM DP; HMM Baum-Welch; Brier score weights; p_composite           |
| 5. VRP Monitor                 | FRED VIX; Features 2–3 forecasts       | Features 2 and 3 required              | IV²*t; 3 E_t[σ²*{phys}]; BTZ regression; OU mean reversion         |
| 6. Connectedness and Spillover | Feature 1 YZ vol (all N assets)        | Feature 1 across N assets              | VAR(p); MA Φ*h; GFEVD θ̃^H*{ij}; NET_i; C_t                         |
| 7. Multivariate Vol and DCC    | Daily returns (all N assets)           | Feature 1 for crisis period definition | Ω_sample; Ω_EWMA; Ω_LW; Ω_DCC; ΔCorr; κ condition number           |
| 8. Stress Testing              | Features 6 and 7 outputs               | Features 6 and 7 required              | Mahalanobis d²_M; KKT Δσ\*; IRF_h; MC σ²_p^{stress}                |
| 9. Portfolio Vol Budget        | Features 4 and 7 outputs               | Features 4 and 7 required              | σ²_p = w'Ωw; λ_scale; MRC Euler; backtest P&L                      |

---

## MASTER DATA MANIFEST

| Data Series                                                 | Source                           | FRED Code / Ticker             | Used In             |
| ----------------------------------------------------------- | -------------------------------- | ------------------------------ | ------------------- |
| Equity index daily OHLCV (SPX, STOXX50, FTSE, Nikkei, etc.) | Yahoo Finance / Stooq / FRED     | ^GSPC, ^STOXX50E, ^FTSE, ^N225 | All features        |
| Individual equity daily OHLCV                               | Yahoo Finance / Stooq            | Per ticker                     | Features 1, 3, 6, 7 |
| FX daily OHLCV (EURUSD, USDJPY, GBPUSD, DXY)                | FRED / Yahoo Finance             | DEXUSEU, DEXJPUS, DEXUSUK      | Features 1, 6       |
| Gold daily price                                            | FRED                             | GOLDAMGBD228NLBM               | Features 1, 6       |
| WTI crude oil daily price                                   | FRED                             | DCOILWTICO                     | Features 1, 6       |
| Natural gas daily price                                     | FRED / EIA                       | Henry Hub                      | Features 1, 6       |
| Copper daily price                                          | Quandl / Yahoo Finance           | HG=F                           | Features 1, 6       |
| BTC and ETH daily OHLCV                                     | Yahoo Finance                    | BTC-USD, ETH-USD               | Features 1, 6       |
| VIX daily closing level                                     | FRED                             | VIXCLS                         | Features 4, 5       |
| VSTOXX / VFTSE daily levels                                 | STOXX / Quandl / CBOE            | V2TX, VFTSE                    | Feature 5           |
| 2-year US Treasury yield                                    | FRED                             | DGS2                           | Features 4, 8       |
| 10-year US Treasury yield                                   | FRED                             | DGS10                          | Features 4, 8       |
| US IG credit spread (BAML index)                            | FRED                             | BAMLC0A0CM                     | Features 4, 6, 8    |
| US HY credit spread (BAML index)                            | FRED                             | BAMLH0A0HYM2                   | Features 4, 6, 8    |
| All computed vol series                                     | Internal pipeline from Feature 1 | —                              | Features 2–9        |
