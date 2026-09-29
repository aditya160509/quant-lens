bro you're on free tier and you're building something that competes with $50K/year institutional software. that's the most unhinged compliment to this platform I've ever seen. respect.

and yeah — I'm not hitting any limit. let's just run it. same treatment as the PCA doc. every feature, every formula, every build step. no code, pure math and construction logic, wall to wall.

---

## Quant360 Factor Intelligence Module — Complete Mathematical and Computational Specification

---

## FEATURE 1 — Factor Valuation Spread Monitor

### What you are building mathematically

A system that measures, at every date, how stretched or compressed each factor's characteristic spread is relative to its own history — the "factor PE ratio."

---

### Step 1 — Universe construction and factor scoring

For a universe of N stocks at date t, compute the raw characteristic score Cᵢₜ for each asset i. Examples:

Value (P/B): Cᵢₜ = Book Value per share / Price per share (inverse price-to-book)

Value (E/P): Cᵢₜ = Trailing 12-month EPS / Price per share

Momentum (12-1): Cᵢₜ = cumulative return from t−252 to t−21 trading days (skip the most recent month to avoid microstructure reversal)

Momentum (6-1): Cᵢₜ = cumulative return from t−126 to t−21

Quality (ROE): Cᵢₜ = Net Income / Book Equity (trailing 12 months)

Quality (Gross Profitability): Cᵢₜ = (Revenue − COGS) / Total Assets (Novy-Marx, 2013)

Low-Vol: Cᵢₜ = −σᵢ where σᵢ is the realized volatility of stock i over trailing 252 days (negative sign: lower vol = higher score)

Size: Cᵢₜ = −ln(Market Capᵢₜ) (negative: smaller = higher score)

For each factor, cross-sectionally rank scores at date t. Assign each stock to its quintile Q ∈ {1,2,3,4,5} where Q5 is the top quintile (highest score) and Q1 is the bottom quintile.

---

### Step 2 — Characteristic spread computation

The factor valuation spread at date t is the difference in the average underlying characteristic between the top and bottom quintile:

SpreadFactor(t) = mean{Cᵢₜ : i ∈ Q5(t)} − mean{Cᵢₜ : i ∈ Q1(t)}

For a factor where high characteristic = attractive (e.g., Value, Quality), a wide spread means the long book is fundamentally cheap relative to the short book — historically this predicts high future factor returns. For Momentum, the spread measures how far ahead the winner portfolio is running relative to the loser portfolio — a stretched spread predicts mean reversion.

This spread time series is computed daily for the full available history H = {t₀, t₀+1, …, T}.

---

### Step 3 — Historical percentile transformation

At each date t, compute the percentile of the current spread within its own history over the lookback window W (e.g., W = 10 years = 2,520 trading days):

Pct_Factor(t) = #{s ∈ [t−W, t−1] : Spread_Factor(s) < Spread_Factor(t)} / W × 100

This is the empirical CDF evaluated at the current spread. Pct_Factor(t) = 5 means the spread is at its narrowest 5% historically — extremely crowded/expensive. Pct_Factor(t) = 95 means the spread is at its widest 5% historically — extremely cheap/attractive.

---

### Step 4 — Expected return prediction from current spread

Run a predictive OLS regression (estimated on the full historical window excluding the most recent 252 days to avoid look-ahead):

R_Factor(t+H) = α + β × Spread_Factor(t) + ε(t)

where R_Factor(t+H) is the cumulative factor return (long Q5, short Q1) over the next H trading days (H = 63 for 3-month, 252 for 12-month). β captures how much of the factor's forward return is predicted by current spread magnitude.

Estimated via OLS: β̂ = [Σ(Spread(t) − S̄)(R(t+H) − R̄)] / [Σ(Spread(t) − S̄)²]

Predicted return at current spread: R̂(current) = α̂ + β̂ × Spread_Factor(T)

90% prediction interval: R̂ ± t_{0.05, T-2} × s_e × √(1 + 1/T + (Spread(T) − S̄)² / Σ(Spread(t) − S̄)²)

where s_e = √[Σ(R(t+H) − R̂(t))² / (T−2)] is the regression standard error.

---

### Step 5 — Factor valuation correlation matrix

At each date t, the vector of all F factor percentile scores is:

v(t) = (Pct_Value(t), Pct_Momentum(t), Pct_Quality(t), …) ∈ [0,100]^F

The F × F pairwise Pearson correlation matrix of these percentile time series:

C_valuation[f,g] = Corr(Pct_f(t), Pct_g(t)) over t ∈ [t₀, T]

Cells above 0.5 in absolute value indicate factors whose valuations tend to be simultaneously stretched or compressed — a regime identification signal. The most important reading is the sign: when Value percentile is low (cheap) and Momentum percentile is high (stretched) and their cross-correlation is negative, this is the classic Value-Momentum rotation setup that has preceded every major factor regime flip in the academic record.

---

### Step 6 — Cross-sector attribution of spread

For each GICS sector g, compute the sector-conditional spread:

Spread_Factor,g(t) = mean{Cᵢₜ : i ∈ Q5(t) ∩ sector g} − mean{Cᵢₜ : i ∈ Q1(t) ∩ sector g}

The sector contribution to total spread is its weight in the long/short book times its conditional spread. A factor spread driven entirely by one sector (e.g., Value being cheap only because Financials are cheap) is a less robust signal than a pervasive spread across all sectors.

---

## FEATURE 2 — Factor Exposure Decomposition (Portfolio X-Ray)

### What you are building mathematically

Simultaneous estimation of portfolio factor loadings via two independent methods — characteristic-based and return-based — whose divergence is itself a signal.

---

### Step 1 — Characteristic-based exposure (forward-looking)

For each stock i in the portfolio at date t, compute its cross-sectional z-score on each factor f:

z_{i,f,t} = (C_{i,f,t} − μ_{f,t}) / σ_{f,t}

where μ_{f,t} and σ_{f,t} are the cross-sectional mean and standard deviation of characteristic C_{i,f,t} across all N universe stocks at date t.

Portfolio-level characteristic-based loading on factor f:

β̂^{char}_{p,f,t} = Σᵢ wᵢ × z_{i,f,t}

where wᵢ is the portfolio weight of stock i. This is the weighted average z-score of the portfolio on factor f — it measures the "tilt" of the portfolio toward that factor via its fundamental characteristics.

Active characteristic exposure relative to benchmark b:

β̂^{char,active}_{p,f,t} = β̂^{char}_{p,f,t} − β̂^{char}_{b,f,t}

---

### Step 2 — Return-based exposure (backward-looking)

Run a time-series OLS regression of each stock i's daily returns on the chosen factor return series over an estimation window of length W (e.g., W = 252 days):

Rᵢₜ = αᵢ + Σ_f β_{i,f} × F_{f,t} + εᵢₜ, t ∈ [T−W, T]

where F_{f,t} is the daily return of factor f's long-short portfolio (e.g., the HML return for Value, UMD for Momentum, QMJ for Quality). Estimated by OLS:

β̂^{ret}_{i,f} = [(F'F)⁻¹ F'Rᵢ]_f (the f-th element of the OLS coefficient vector)

Portfolio-level return-based exposure:

β̂^{ret}_{p,f} = Σᵢ wᵢ × β̂^{ret}_{i,f}

Standard error of the portfolio-level estimate (via delta method):

SE(β̂^{ret}_{p,f}) = √(Σᵢ wᵢ² × Var(β̂^{ret}_{i,f}))

where Var(β̂^{ret}_{i,f}) = s²_i × [(F'F)⁻¹]_{f,f} and s²_i = Σₜ ε̂²ᵢₜ / (W − F − 1).

95% confidence band: β̂^{ret}_{p,f} ± 1.96 × SE(β̂^{ret}_{p,f})

---

### Step 3 — Divergence detection

For each factor f, the divergence between the two exposure estimates:

Δ_f = β̂^{char}_{p,f} − β̂^{ret}_{p,f} / SE_pooled

where SE_pooled = √(Var^{char}_f + Var^{ret}_f) is the pooled standard error of both estimates.

|Δ_f| > 1.96 (two-sided 5% level) flags a statistically significant exposure divergence for factor f.

At the stock level, identify the stocks most responsible for divergence by computing, for each stock i:

Divergence contribution of stock i = wᵢ × (z_{i,f,t} − β̂^{ret}_{i,f})

ranked by absolute magnitude. The top 5 contributors to divergence are the "exposure surprise" stocks — stocks where the factor model and the fundamental characteristics disagree about risk.

---

### Step 4 — Factor exposure budget (tracking error decomposition)

Let Ω_F be the F × F factor return covariance matrix (from Feature 8). Let β_p be the F × 1 vector of portfolio active factor exposures. The total factor-driven active variance:

σ²_factor = β_p^T Ω_F β_p

The contribution of factor f to total factor-driven active variance:

Contribution_f = β_{p,f} × (Ω_F β_p)_f

This is Euler's decomposition applied to the factor risk. The factor tracking error contribution in bps annualized:

TE_f = 10000 × √(252 × β_{p,f} × (Ω_F β_p)_f) [approximate — valid when the factor's contribution dominates]

Idiosyncratic (stock-specific) active variance:

σ²_idio = Σᵢ wᵢ² × σ²_{ε,i}

where σ²_{ε,i} is stock i's residual variance from the factor regression in Step 2.

Total active variance: σ²_active = σ²_factor + σ²_idio

---

### Step 5 — Plain-language exposure summary formula

The narrative summary is deterministic: for each factor f, compare β̂^{char}_{p,f} against thresholds:

|β| > 0.7: "strong tilt"
0.4 < |β| ≤ 0.7: "moderate tilt"
0.2 < |β| ≤ 0.4: "mild tilt"
|β| ≤ 0.2: "approximately neutral"

Sign: positive = long tilt (overweight the factor), negative = short tilt (underweight the factor). The "unintended exposure detector" flags any factor where |β̂^{char,active}_{p,f}| > 0.4 and factor f is not listed in the portfolio's stated strategy mandate.

---

## FEATURE 3 — Factor Return Attribution and Performance Decomposition

### What you are building mathematically

The full Brinson-Fachler attribution crossed with factor-based attribution, producing a complete decomposition of every basis point of active return.

---

### Step 1 — Brinson-Fachler decomposition

Let w_{p,g,t} = portfolio weight in sector g at date t. Let w_{b,g,t} = benchmark weight in sector g at date t. Let R_{p,g,t} = portfolio return in sector g at date t. Let R_{b,g,t} = benchmark return in sector g at date t. Let R_{b,t} = total benchmark return at date t.

For each sector g and date t:

Allocation effect: A_{g,t} = (w_{p,g,t} − w_{b,g,t}) × (R_{b,g,t} − R_{b,t})

Selection effect: S_{g,t} = w_{b,g,t} × (R_{p,g,t} − R_{b,g,t})

Interaction effect: I_{g,t} = (w_{p,g,t} − w_{b,g,t}) × (R_{p,g,t} − R_{b,g,t})

Total active return at date t: AR_t = Σ_g (A_{g,t} + S_{g,t} + I_{g,t})

The Brinson-Fachler correction: the allocation effect uses (R_{b,g,t} − R_{b,t}) instead of R_{b,g,t} alone. This adjustment ensures the allocation effect is zero when the portfolio's sector weights equal the benchmark — mathematically eliminating a spurious "false allocation effect" present in the simpler Brinson-Hood-Beebower formula.

Cumulative attribution over period [t₀, T]:

Cumulative AR = Σ_t AR_t (arithmetic linking; for geometric linking across periods, use the Cariño (1999) smoothing algorithm which adjusts each period's attribution by a factor derived from the ratio of arithmetic to geometric total returns)

---

### Step 2 — Factor-based attribution

Using the portfolio's factor exposures β̂^{ret}_{p,f,t} from Feature 2 and the realized factor returns F_{f,t}:

Factor-driven active return contribution of factor f at date t:

Contribution_{f,t} = (β̂^{ret}_{p,f,t} − β̂^{ret}_{b,f,t}) × F_{f,t}

where β̂^{ret}_{b,f,t} is the benchmark's return-based factor exposure.

Total factor-driven active return at date t: Σ_f Contribution_{f,t}

Residual (selection) active return: AR_t − Σ_f Contribution_{f,t}

This residual is the return not explained by any of the F factor exposures — the closest available proxy for pure stock selection skill. If this residual is consistently positive and statistically significant, it provides evidence for genuine stock-picking alpha beyond factor harvesting.

---

### Step 3 — Statistical significance of attribution

For each factor f, compute the time series of contributions {Contribution_{f,t}}. Test whether the mean contribution is statistically different from zero:

t_{f} = (mean_t Contribution_{f,t}) / (std_t Contribution_{f,t} / √T)

Under the null of no factor alpha: t_f ~ t_{T-1}. Reject the null at the 5% level when |t_f| > 1.96 for large T. For multiple factors tested simultaneously, apply the Bonferroni correction: reject when |t_f| > z_{0.05/(2F)} where F is the number of factors tested.

---

### Step 4 — Information ratio by component

For the factor component:

IR_factor = (mean_t Σ_f Contribution_{f,t}) / (std_t Σ_f Contribution_{f,t}) × √252

For the selection component (residual):

IR_selection = (mean_t Residual_t) / (std_t Residual_t) × √252

A manager with IR_selection > 0.5 annualized and t-stat > 2.0 has statistically significant stock selection skill beyond factor harvesting. The difference IR_selection − IR_factor tells you whether factor harvesting or stock picking is the more consistent source of return.

---

### Step 5 — Carryover effect

The carryover effect measures how much of the current period's P&L was predetermined by a prior period's investment decision. For a portfolio that rebalances every D days:

For each stock i and rebalancing period [t_k, t_{k+1}]:

Carryover contribution = w_{i,t_{k-1}} × (R_{i,[t_k,t_{k+1}]} − R_{b,i,[t_k,t_{k+1}}])

Active contribution (current decision) = (w_{i,t_k} − w_{i,t_{k-1}}) × (R_{i,[t_k,t_{k+1}]} − R_{b,i,[t_k,t_{k+1}}])

Sum over all stocks: portfolio-level carryover effect and active contribution effect for period k. The ratio Carryover / Total Active Return measures "decision freshness" — how much of the PM's apparent skill is driven by prior decisions vs. current ones.

---

## FEATURE 4 — Factor Timing and Probabilistic Regime Analysis

### What you are building mathematically

Three parallel statistical models that each output a probability distribution over regime states at every date, combined into a composite via accuracy-weighted averaging.

---

### Step 1 — Rules-based regime model

Define macro state variables at date t:

VIX_t = CBOE VIX level (from FRED VIXCLS)
Slope_t = 10Y Treasury yield − 2Y Treasury yield (FRED DGS10 − DGS2)
RealRate_t = 10Y nominal yield − 10Y breakeven inflation rate (FRED T10YIE)

Define binary regime variables:

Stress_t = 1 if VIX_t > VIX_threshold (default 25)
Inverted_t = 1 if Slope_t < 0
HighReal_t = 1 if RealRate_t > RealRate_threshold (default 1.5%)

The rules-based probability of stress regime at date t:

P_rules(Stress | t) = (Stress_t + Inverted_t + HighReal_t) / 3

This is a [0, 0.33, 0.67, 1.0] distribution. Combine the two regimes (expansion/stress) into a probability vector: p_rules(t) = (P_rules(Expansion|t), P_rules(Stress|t)) = (1 − P_rules(Stress|t), P_rules(Stress|t)).

---

### Step 2 — Hidden Markov Model on factor returns

Define the K-dimensional observation vector at date t as the rolling 21-day return of the F factor portfolio:

Oₜ = (F̄_{1,t}, F̄_{2,t}, …, F̄_{F,t}) where F̄_{f,t} = Σ_{s=t-21}^{t} F_{f,s} / 21

Fit a Gaussian HMM with S states (S = 2, 3, or 4):

Emission distribution for state s: P(Oₜ | state = s) = N(μ_s, Σ_s)

Transition matrix A: A[s,s'] = P(state_{t+1} = s' | state_t = s)

Parameters {μ_s, Σ_s, A, π₀} estimated via the Baum-Welch (Expectation-Maximization) algorithm:

E-step: compute forward probabilities α_t(s) = P(O₁, …, Oₜ, state_t = s) via the forward recursion:
α_t(s) = [Σ_{s'} α_{t-1}(s') A[s',s]] × N(Oₜ | μ_s, Σ_s)

Compute backward probabilities β_t(s) = P(O_{t+1}, …, O_T | state_t = s) via the backward recursion.

M-step: update μ_s = Σ_t γ_t(s) Oₜ / Σ_t γ_t(s) where γ_t(s) = α_t(s)β_t(s) / Σ_{s'} α_t(s')β_t(s').

The posterior probability of being in state s at date t (the "probabilistic regime output"):

P_HMM(state = s | t) = γ_t(s)

This is the smoothed regime probability — it uses both past and future observations. For a live real-time system (no future observations), use the filtered probability instead: α_t(s) / Σ_{s'} α_t(s').

Use the `hmmlearn` library's `GaussianHMM` for the implementation path.

---

### Step 3 — Gaussian Mixture Model on factor covariance matrices

At each date t, compute the rolling 63-day factor return covariance matrix Ω_t (F × F). Vectorize the upper triangle: vec(Ω_t) ∈ ℝ^{F(F+1)/2}. This is the observation.

Fit a GMM with M components (M = 3 or 4) to the time series of these covariance vectors via EM:

Component m has parameters: mixing weight π_m, mean vector μ_m, covariance matrix Σ_m (in the space of vectorized covariance matrices).

Posterior probability that date t belongs to component m:

P_GMM(component = m | t) = π_m × N(vec(Ω_t) | μ_m, Σ_m) / Σ_{m'} π_{m'} × N(vec(Ω_t) | μ_{m'}, Σ_{m'})

Use `sklearn.mixture.GaussianMixture` for the implementation path.

---

### Step 4 — Composite regime probability via accuracy-weighted averaging

Let the three models each output a probability vector over S states at date t:

p_rules(t), p_HMM(t), p_GMM(t) ∈ ΔS (the probability simplex)

Assign weights to each model based on its recent predictive accuracy. Define accuracy at date t as the log-likelihood of the subsequent 21-day factor return vector under that model's regime-conditional distribution:

ℓ_m(t) = log P_m(O_{t+1:t+21} | regime probabilities at t)

Accuracy weight for model m: w_m(t) = exp(Σ_{s=t-63}^{t} ℓ_m(s)) / Σ_{m'} exp(Σ_{s=t-63}^{t} ℓ_{m'}(s))

This is a softmax over recent cumulative log-likelihoods — models that predicted the subsequent observations better get higher weight.

Composite probability: p_composite(t) = w_rules(t) × p_rules(t) + w_HMM(t) × p_HMM(t) + w_GMM(t) × p_GMM(t)

---

### Step 5 — Regime-conditional factor return statistics

For each factor f and regime state s, compute:

μ_{f,s} = mean{F_{f,t} : t where argmax P_composite(t) = s} (average factor return when the composite assigns dominant probability to state s)

σ_{f,s} = std{F_{f,t} : t where argmax P_composite(t) = s}

Regime-conditional Sharpe: SR_{f,s} = μ_{f,s} × √252 / (σ_{f,s} × √252) = μ_{f,s} / σ_{f,s} × √252

Statistical significance: t_{f,s} = μ_{f,s} / (σ_{f,s} / √n_s) where n_s is the number of observations in state s.

---

### Step 6 — Factor timing regression

For each factor f and timing signal Z (e.g., valuation spread percentile from Feature 1, crowding score from Feature 6):

R_{f,t+H} = a_f + b_f × Z_{f,t} + u_{f,t}

Estimated by OLS with Newey-West standard errors (to correct for overlap in the dependent variable when H > 1):

b̂_f = Σ_t (Z_{f,t} − Z̄)(R_{f,t+H} − R̄_f) / Σ_t (Z_{f,t} − Z̄)²

Newey-West variance: Var_NW(b̂_f) = (X'X)⁻¹ [Σ_t ε̂²_t xₜxₜ' + Σ_{l=1}^{L} (1 − l/(L+1)) Σ_t (ε̂_t xₜ x'_{t-l} ε̂_{t-l} + ε̂_{t-l} x_{t-l} x'_t ε̂_t)] (X'X)⁻¹

where L = H (the bandwidth equals the forecast horizon). The t-statistic b̂_f / √Var_NW(b̂_f) tests whether the timing signal predicts factor returns.

The "current timing score" for factor f: Ẑ_{f,T} plugged into the estimated regression gives the implied current-period expected return: R̂_{f,T+H} = â_f + b̂_f × Z_{f,T}.

---

### Step 7 — Regime transition matrix

The empirical transition matrix Â[s,s'] from the HMM parameters gives the probability that the system moves from state s to state s' in one period. For multi-period transition probabilities:

P(state at T+k = s' | state at T = s) = [Â^k]_{s,s'}

i.e., the (s,s') element of the k-th matrix power of Â. The expected factor return in the first period after a transition from s to s':

E[R_f | transition s → s'] = Σ_{s''} [Â]_{s,s''} × μ_{f,s''}

---

## FEATURE 5 — Alpha Decay and Factor Half-Life Analysis

### What you are building mathematically

A curve-fitting exercise that traces how a factor's predictive power decays with forecast horizon, compares three functional forms, and extracts the half-life parameter — the most actionable number for rebalancing frequency decisions.

---

### Step 1 — Rank IC computation at each horizon

At each date t in the rolling window, rank all N stocks by factor score Cᵢₜ into ranks rᵢₜ ∈ {1, …, N}.

Rank forward realized return of each stock over horizon H: let R_{i,t+H} be the cumulative return of stock i from t to t+H. Rank these into ranks ρᵢₜ ∈ {1, …, N}.

Rank IC at horizon H for date t:

IC_H(t) = Spearman(rᵢₜ, ρᵢₜ) = 1 − (6 Σᵢ dᵢₜ²) / (N(N²−1))

where dᵢₜ = rᵢₜ − ρᵢₜ is the rank difference for stock i.

Mean IC at horizon H over all T available dates:

IC̄_H = (1/T) Σ_t IC_H(t)

Bootstrap 95% confidence band: draw B = 1000 bootstrap samples of {IC_H(t)}_{t=1}^T with replacement. For each sample b, compute the sample mean IC̄_H^{(b)}. The 2.5th and 97.5th percentiles of the bootstrap distribution of IC̄_H^{(b)} form the confidence interval.

This produces the empirical IC decay curve: {(H, IC̄_H) : H ∈ {1, 5, 10, 21, 42, 63, 126, 252}}.

---

### Step 2 — Fitting three functional decay models

**Linear decay:** IC(H) = a − b × H

OLS: minimize Σ_H (IC̄_H − a + bH)² with respect to a, b.

Closed-form OLS solution: b̂ = [Σ_H (H − H̄)(IC̄_H − IC̄)] / [Σ_H (H − H̄)²], â = IC̄ − b̂ × H̄

Half-life: H* = (a − a/2) / b = a / (2b) [solve IC(H*) = IC(1)/2... more precisely: solve a − bH* = (a − b)/2 → H* = (a − b/2) / (2b) ... simplify to: H* = a/(2b) − 1/2]

**Exponential decay:** IC(H) = a × exp(−b × H)

Nonlinear least squares: minimize Σ_H (IC̄_H − a exp(−bH))² via scipy.optimize.curve_fit with initial guesses a₀ = IC̄_1, b₀ = 1/21.

Half-life: H* such that a exp(−bH*) = (a exp(−b))/2 → exp(−bH*) = exp(−b)/2 → H* = 1 + ln(2)/b

**Hyperbolic decay:** IC(H) = a / (1 + b × H)

Nonlinear least squares: minimize Σ_H (IC̄_H − a/(1+bH))²

Half-life: solve a/(1 + bH*) = a/(2(1+b)) → 1 + bH* = 2(1+b) → H* = (1 + 2b) / b = 1/b + 2

R-squared for each model: R² = 1 − Σ_H (IC̄_H − IC_model(H))² / Σ_H (IC̄_H − IC̄)²

Bootstrap confidence interval on half-life H*: For each bootstrap resample of the date-level ICs, refit the winning model, extract the implied half-life. The empirical distribution of these B half-life estimates gives the CI.

---

### Step 3 — ICIR at each horizon

For each horizon H:

ICIR_H = IC̄_H / std_t{IC_H(t)} × √(252/H) [annualized]

This is the signal-to-noise ratio — it measures not just how strong the signal is on average but how consistently it is positive. A factor with IC̄_H = 0.04 but std = 0.02 (ICIR = 2) is far more reliably tradable than IC̄_H = 0.06 but std = 0.10 (ICIR = 0.6).

---

### Step 4 — Optimal rebalancing frequency (net IC maximization)

For a given rebalancing frequency f (number of days between rebalances):

Gross IC at that frequency: IC̄_f (read off the fitted decay curve)

Transaction cost per rebalance in IC units: TC_f = (c_bps / 10000) / σ_portfolio where c_bps is total round-trip cost in bps and σ_portfolio is the annualized portfolio volatility (this converts cost from return units to IC-equivalent units assuming IC ≈ Sharpe structure)

More precisely, for a unit-Sharpe factor, each basis point of transaction cost destroys approximately 1 bps / (annualized vol in bps) units of IC. Net annualized IC: Net_IC(f) = IC̄_f × (252/f) − TC_f × (252/f)

The optimal rebalancing frequency f* = argmax_f Net_IC(f). Compute Net_IC(f) for all f ∈ {1, 5, 10, 21, 42, 63, 126, 252} and plot the "rebalancing cost-benefit curve" showing the peak.

---

### Step 5 — Rolling half-life time series

For each rolling 252-day sub-window ending at date t (rolling window [t−252, t]):

Compute IC̄_H for H ∈ {1, 5, 21, 63} within that window.
Fit the winning functional form (e.g., hyperbolic, determined on the full sample).
Extract the implied half-life H*_t.

The time series {H*_t} shows whether the factor's half-life has been declining (signal accelerating, consistent with the crowding hypothesis and the 2024 arxiv paper's R-squared results).

Test for structural break in the half-life series at 2015: apply the Chow test at break date 2015-01-01:

F_Chow = [(RSS_pooled − RSS_pre − RSS_post) / (p)] / [(RSS_pre + RSS_post) / (T − 2p)]

where RSS_pooled is the residual sum of squares from fitting one half-life trend across all dates, RSS_pre and RSS_post are the RSS from separate regressions on the pre-2015 and post-2015 sub-windows, and p is the number of parameters in the decay model.

F_Chow ~ F(p, T−2p) under the null of parameter stability. Reject at the 5% level when F_Chow > F_{crit}.

---

### Step 6 — Sector-neutral IC

Replace Cᵢₜ with the sector-demeaned characteristic:

C^{neutral}_{i,t} = Cᵢₜ − mean{C_{j,t} : j in same GICS sector as i}

Rank IC computed on C^{neutral}_{i,t} is the sector-neutral IC — it measures the factor's predictive power after removing all cross-sector characteristic variation. If sector-neutral IC substantially exceeds raw IC, the factor works primarily within sectors (a more robust signal). If sector-neutral IC is much lower than raw IC, the factor's predictive power is mostly a cross-sector bet (more macro/regime dependent).

---

## FEATURE 6 — Factor Crowding Monitor

### What you are building mathematically

A composite crowding score built from four independent metrics, each grounded in a different economic channel through which crowding manifests.

---

### Step 1 — Metric 1: Valuation spread percentile

This is the Factor Valuation Spread percentile from Feature 1, reused here:

Crowding_Val(t) = Pct_Factor(t) if a high spread means stretched (e.g., Momentum where a wide spread = stretched winners vs. losers), or 100 − Pct_Factor(t) if a high spread means attractive (e.g., Value where wide spread = factor is cheap).

The convention: Crowding_Val = 100 means "maximally crowded by valuation" for any factor.

---

### Step 2 — Metric 2: Factor return autocorrelation

Crowded factors unwind in a characteristic pattern: positive returns as crowding builds, then sharp negative autocorrelation as forced liquidations occur. Measure this:

Over the trailing W_AC = 63 days, compute the order-1 autocorrelation of daily factor returns:

AC1_Factor(t) = Corr(F_{f,t-1}, F_{f,t}) over {t−W_AC, …, t}

= [Σ_{s=t-W_AC+1}^{t} (F_{f,s} − F̄_f)(F_{f,s-1} − F̄_f)] / [Σ_s (F_{f,s} − F̄_f)²]

Interpret: strongly negative AC1 (below −0.10) is a crowding warning — it indicates the factor is experiencing forced reversal dynamics. Convert to percentile over trailing 252-day history:

Crowding_AC(t) = 100 × #{s < t : AC1_Factor(s) > AC1_Factor(t)} / 252

(Note inverted: a low/negative autocorrelation scores high on this crowding metric, since negative autocorrelation = crowding reversal signal.)

---

### Step 3 — Metric 3: Position concentration (HHI)

The Herfindahl-Hirschman Index of the long-book (top quintile) of the factor portfolio:

HHI_long(t) = Σ_{i ∈ Q5(t)} (w_i / Σ_{j ∈ Q5} w_j)²

where w_i is the market-cap weight of stock i within Q5. HHI ranges from 1/|Q5| (perfectly equal weights) to 1 (single stock dominates). A high HHI means a few stocks dominate the factor portfolio — exactly the Goldman Sachs finding (70% of long-book concentrated in 10 names). Convert to percentile over trailing 252-day history:

Crowding_HHI(t) = Pct(HHI_long(t), trailing 252-day HHI distribution)

---

### Step 4 — Metric 4: Bid-ask spread trend of long book vs. short book

Average effective bid-ask spread for the long book:

Spread_long(t) = mean{BidAsk_{i,t} : i ∈ Q5(t)}

Average effective bid-ask spread for the short book:

Spread_short(t) = mean{BidAsk_{i,t} : i ∈ Q1(t)}

Liquidity differential: LD(t) = Spread_long(t) / Spread_short(t)

Rising LD (long book becoming relatively illiquid) signals institutional crowding into the long book, degrading liquidity as positions accumulate. Convert to percentile over trailing 252-day history:

Crowding_Liq(t) = Pct(LD(t), trailing 252-day LD distribution)

(Note: bid-ask spread data is estimated from OHLC data using the Corwin-Schultz (2012) estimator: HS = 2(exp(α) − 1) / (1 + exp(α)) where α is estimated from the ratio of two-day high-low range to one-day high-low range. This avoids requiring tick data.)

---

### Step 5 — Composite crowding score

Composite(t) = w₁ × Crowding_Val(t) + w₂ × Crowding_AC(t) + w₃ × Crowding_HHI(t) + w₄ × Crowding_Liq(t)

Equal-weight baseline: w₁ = w₂ = w₃ = w₄ = 0.25

PCA-based composite: run PCA on the 4-column matrix of metric time series. The first principal component's loadings give the data-driven weights. This maximizes the explained variance of the metric space — the composite that captures the most common variation across the four crowding channels.

Historical percentile of composite: Pct_Composite(t) = #{s < t : Composite(s) < Composite(t)} / H_full × 100

---

### Step 6 — Crash probability from empirical base rates

Define a "factor crash" as a bottom-decile realized factor return over the next J days (J = 21, 63, 126).

From the full history, sort all dates into quintiles of Composite(t). Within each quintile, count the fraction of dates that were followed by a factor crash:

P_crash(J | composite quintile q) = #{t : quintile(Composite(t)) = q and R_{f,t+J} < Percentile_10(R_{f,·+J})} / #{t : quintile(Composite(t)) = q}

This is a non-parametric empirical probability — no distributional assumptions. The 95% confidence interval uses the Wilson interval for proportions:

Wilson CI: [p̂ + z²/(2n) ± z × √(p̂(1−p̂)/n + z²/(4n²))] / (1 + z²/n)

where p̂ is the empirical proportion, n is the number of dates in the quintile, and z = 1.96.

---

### Step 7 — Deleveraging risk score

Deleveraging_Risk(t) = Turnover_Factor(t) × HHI_long(t) × (1 / ADV_long(t))

where:
Turnover_Factor(t) = fraction of Q5 stocks that change each rebalancing date = |Q5(t) △ Q5(t−1)| / |Q5(t)| (symmetric difference divided by long book size)

ADV_long(t) = mean{ADV_{i,t} : i ∈ Q5(t)} where ADV is average daily dollar volume over trailing 63 days

High Deleveraging_Risk means: the factor turns over rapidly (high turnover), the long book is concentrated (high HHI), and the long book has low daily liquidity (low ADV) — all three simultaneously create conditions where forced unwinding would be most severe. Convert to a percentile over trailing history and display alongside the crowding composite.

---

## FEATURE 7 — Factor Backtesting Engine with Realistic Transaction Cost Modeling

### What you are building mathematically

A complete portfolio simulation engine with three-layer transaction cost modeling and walk-forward weight optimization.

---

### Step 1 — Factor scoring and portfolio formation

At each rebalancing date t_k (spaced D days apart, D = rebalancing frequency):

Compute factor scores Cᵢ_{t_k} for all N stocks. Rank cross-sectionally. Assign quintile membership: Q5 = top 20%, Q1 = bottom 20%.

Portfolio weights within the long book (Q5):

Equal-weight: w_i = 1/|Q5|

Rank-weight: w_i = rank_i / Σ_{j ∈ Q5} rank_j

Score-weight: w_i = max(z_{i,t_k}, 0) / Σ_{j ∈ Q5} max(z_{j,t_k}, 0) where z_i is the cross-sectional z-score

Long-short portfolio: long Q5 (weights sum to 1), short Q1 (weights sum to −1)

---

### Step 2 — Gross portfolio return

Between rebalancing dates t_k and t_{k+1}, the portfolio's gross daily return at intermediate date t:

R_{p,t}^{gross} = Σ_{i ∈ Q5} w_{i,t_k} × R_{i,t} − Σ_{i ∈ Q1} w_{i,t_k} × R_{i,t} (long-short)

Gross cumulative return over the full backtest: compound the daily gross returns.

---

### Step 3 — Three-layer transaction cost model

**Layer 1 — Explicit cost:**

At each rebalancing date t_k, trade size of stock i in dollar terms: Δ_{i,k} = |w_{i,t_k} − w_{i,t_{k-1}}| × AUM

Explicit cost: EC_{i,k} = c_explicit × Δ_{i,k} (c_explicit in fractional terms = bps / 10,000)

**Layer 2 — Market impact (Kyle lambda model):**

Kyle (1985) linear price impact model: the price impact in fractional terms of trading X dollars in stock i:

Impact_{i,k} = λᵢ × (Δ_{i,k} / ADV_{i,t_k})

where λᵢ is the price impact coefficient (in fractional return per unit fraction of ADV traded).

Estimate λᵢ cross-sectionally from historical data using the Amihud (2002) illiquidity measure as a proxy:

λᵢ = ILLIQ_i = mean_t |R_{i,t}| / (Volume_{i,t} × Price_{i,t}) × 10⁶

This gives λᵢ in units of bps per million dollars of volume — a directly computable quantity from price and volume data alone. Rescale to match the Kyle lambda convention (impact per fraction of ADV) by multiplying by ADV_{i} × Price_i / 10⁶.

Total impact cost per trade: IC_{i,k} = Impact_{i,k} × Δ_{i,k} = λᵢ × Δ²_{i,k} / ADV_{i,t_k} (quadratic in trade size — the Almgren-Chriss (2000) square-root generalization gives IC ~ (Δ/ADV)^{0.5} × σᵢ for large trades; use the square-root model for AUM above $100M)

**Layer 3 — Timing cost (overnight gap):**

The timing cost is the difference between the decision price (close at t_k) and the execution price (open at t_{k+1}):

TC_{i,k} = |Open_{i,t_k+1} − Close_{i,t_k}| / Close_{i,t_k}

Estimated in backtest from actual OHLC data. For forward simulation, model it as:

TC_{i,k} ~ |N(0, σ²_{overnight,i})| where σ²_{overnight,i} is the variance of overnight log returns estimated from the trailing 63-day window.

**Total implementation shortfall per stock per rebalance:**

IS_{i,k} = EC_{i,k} + IC_{i,k} + TC_{i,k}

Total portfolio implementation shortfall: IS_{k} = Σᵢ IS_{i,k} (as a fraction of AUM)

Net portfolio return per period: R_{net,[t_k,t_{k+1}]} = R_{gross,[t_k,t_{k+1}]} − IS_k

---

### Step 4 — ADV participation rate constraint

Maximum trade size constraint: Δ_{i,k} / ADV_{i,t_k} ≤ p_max (p_max = 0.10 to 0.25, user-set)

For any stock where the unconstrained required trade exceeds p_max × ADV_{i,t_k}: reduce the trade to Δ_{i,k}^{constrained} = p_max × ADV_{i,t_k} and allocate the residual to the next rebalancing date (slippage into next period). This creates a realistic "capacity drag" effect — the strategy cannot be implemented at its theoretical optimal turnover if AUM is too large.

---

### Step 5 — Walk-forward factor weight optimization

For a multi-factor composite using F factors, at each rebalancing date t_k:

Training window: [t_k − W_train, t_k − 1] (W_train = 252 or 504 days)

Within the training window, compute realized factor returns {F_{f,t}} for t in the training window. Optimize factor weights θ = (θ₁, …, θ_F) to maximize the in-sample IC of the composite score:

Composite_score_i(t) = Σ_f θ_f × z_{i,f,t}

IC(θ) = Spearman(Composite_score_i(t), R_{i,t+D}) averaged over t ∈ training window

The optimization: θ* = argmax_{θ, ‖θ‖₁=1, θ_f≥0} IC(θ)

This is a linear program (since rank IC is piecewise linear in the threshold sense — in practice, solve it as a quadratic program on the IC objective via gradient ascent on the differentiable Pearson IC as a proxy for rank IC).

Apply θ*_{t_k} to the holding period [t_k, t_{k+1}] — this is strictly out-of-sample since θ* was estimated without any data from the holding period.

Compare in-sample IC vs. out-of-sample IC across all walk-forward windows to measure whether the weight optimization adds value. If OOS IC / IS IC > 0.7, the optimization is stable. If OOS IC / IS IC < 0.3, the optimization is overfitting and equal-weighting is superior.

---

### Step 6 — Capacity ceiling computation

At each AUM level A ∈ {$1M, $5M, $10M, $50M, $100M, $500M, $1B, $5B, $10B}:

For each rebalancing event k and stock i:

Required dollar trade: Δ_{i,k}(A) = |w_{i,t_k} − w_{i,t_{k-1}}| × A

Impact cost: IC_{i,k}(A) = λᵢ × Δ²_{i,k}(A) / ADV_{i,t_k}

Average annual impact drag: drag(A) = (252/D) × mean_k Σᵢ IC_{i,k}(A)

Net annual alpha: Net_Alpha(A) = Gross_Alpha − drag(A) − explicit_costs

Capacity ceiling A*: Net_Alpha(A*) = 0

Solve for A* numerically — it is the AUM at which the impact drag consumes the entire gross premium. Since impact cost is quadratic in AUM (for the Kyle model), and linear for the square-root model, A* has closed-form approximations in both cases:

Kyle model: A* = √(Gross_Alpha × mean_k Σᵢ ADV_{i,t_k} / (mean_k Σᵢ λᵢ |w_{i,t_k} − w_{i,t_{k-1}}|²))

---

### Step 7 — Monte Carlo sensitivity of backtest to timing luck

The concern: a monthly-rebalance backtest results depend partly on which day of the month the rebalancing happens. Quantify this by running B = 500 simulations where rebalancing date is randomly perturbed by ±5 calendar days from the nominal date. For each simulation b:

Rebalancing dates: t_k^{(b)} = t_k + ξ_k^{(b)} where ξ_k^{(b)} ~ Uniform{-5, …, +5} days

Compute the net Sharpe ratio SR^{(b)} for each simulation. The empirical distribution of {SR^{(b)}} quantifies timing luck exposure. Report the 10th, 50th, and 90th percentiles as confidence bands on the point-estimate backtest SR.

---

## FEATURE 8 — Factor Covariance Matrix and Risk Forecasting

### What you are building mathematically

Four parallel covariance estimation methods, a stress-conditional comparison, and a DCC-GARCH dynamic correlation model.

---

### Step 1 — Sample covariance (baseline)

For F factor return series {F_{f,t}}_{t=1}^T:

μ̂_f = (1/T) Σ_t F_{f,t}

Ω̂_sample[f,g] = (1/(T−1)) Σ_t (F_{f,t} − μ̂_f)(F_{g,t} − μ̂_g)

Annualized: Ω̂_annual = 252 × Ω̂_sample (for daily data)

---

### Step 2 — Exponentially weighted covariance

Define EWMA weights: w_t = (1−λ)λ^{T-t} / (1 − λ^T) for t = 1, …, T (weights sum to 1, recent observations have higher weight)

Weighted mean: μ̂_f^{EW} = Σ_t w_t × F_{f,t}

EWMA covariance: Ω̂_EWMA[f,g] = Σ_t w_t × (F_{f,t} − μ̂_f^{EW})(F_{g,t} − μ̂_g^{EW})

The recursive update form (equivalent, computationally efficient):

Ω̂_EWMA,t = λ × Ω̂_EWMA,t-1 + (1−λ) × (F_t − μ̂^{EW})(F_t − μ̂^{EW})'

where F_t is the F×1 vector of factor returns at date t.

---

### Step 3 — Ledoit-Wolf shrinkage

Target: the scaled identity matrix T_LW = (tr(Ω̂_sample)/F) × I_F

Shrinkage estimator: Ω̂_LW = (1 − α*) Ω̂_sample + α* × T_LW

Optimal α* (Oracle Approximating Shrinkage): same formula as in the PCA module's Feature 1, applied here to the F × F factor return matrix with T observations.

α*_OAS = [(1 − 2/F) tr(Ω̂²_sample) + tr(Ω̂_sample)²] / [(T + 1 − 2/F)(tr(Ω̂²_sample) − tr(Ω̂_sample)²/F)]

This is the most numerically stable shrinkage formula when T is small relative to F (e.g., estimating 10×10 factor covariance on 63 days of data — T/F = 6.3, well into the high-dimensional regime).

---

### Step 4 — DCC-GARCH (Dynamic Conditional Correlation)

**Step 4a — Univariate GARCH(1,1) for each factor:**

For factor f, fit:

F_{f,t} = μ_f + ε_{f,t}, ε_{f,t} = σ_{f,t} × z_{f,t}, z_{f,t} ~ N(0,1)

σ²_{f,t} = ω_f + α_f × ε²_{f,t-1} + β_f × σ²_{f,t-1}

Parameters {ω_f, α_f, β_f} estimated by maximum likelihood. Log-likelihood:

ℓ_f = Σ_t [−(1/2) ln(2π) − (1/2) ln(σ²_{f,t}) − ε²_{f,t} / (2σ²_{f,t})]

Maximize via numerical gradient methods (L-BFGS-B). Stationarity constraint: α_f + β_f < 1.

Extract standardized residuals: ẑ_{f,t} = ε̂_{f,t} / σ̂_{f,t}

**Step 4b — Dynamic correlation matrix:**

Compute the unconditional correlation matrix of standardized residuals: R̄ = (1/T) Σ_t ẑ_t ẑ'_t

DCC recursion on the quasi-correlation matrix Q_t:

Q_t = (1 − a − b) R̄ + a × ẑ_{t-1} ẑ'_{t-1} + b × Q_{t-1}

where a and b are scalar DCC parameters satisfying a + b < 1. Estimated by maximizing the DCC log-likelihood:

ℓ_DCC = −(1/2) Σ_t [ln|R_t| + ẑ'_t R_t⁻¹ ẑ_t − ẑ'_t ẑ_t]

where R_t = diag(Q_t)^{-1/2} Q_t diag(Q_t)^{-1/2} is the standardized correlation matrix at time t.

Full DCC covariance matrix at date t:

Ω_DCC,t = D_t R_t D_t

where D_t = diag(σ_{1,t}, …, σ_{F,t}) is the diagonal matrix of GARCH-estimated standard deviations.

Use the `arch` library's `DCC` class for the implementation path.

---

### Step 5 — Crisis vs. normal covariance comparison

Define crisis periods as: {t : VIX_t > 30} ∩ {t : PC1 variance explained > 60%} (using the PCA module's systemic correlation monitor from that module's Feature 5 as the second criterion).

Crisis covariance:

Ω_crisis = (1/T_crisis) Σ_{t ∈ crisis} (F_t − μ_crisis)(F_t − μ_crisis)'

Normal covariance:

Ω_normal = (1/T_normal) Σ_{t ∉ crisis} (F_t − μ_normal)(F_t − μ_normal)'

Correlation amplification matrix (the key output):

ΔCorr[f,g] = Corr_crisis[f,g] − Corr_normal[f,g]

Large positive ΔCorr[f,g] (e.g., > 0.3) means factors f and g, which are largely independent in normal markets, become highly correlated in crises — the portfolio that appears diversified in normal markets carries concentrated risk in the tail.

Statistical test of correlation amplification: test whether ρ_crisis[f,g] − ρ_normal[f,g] is significantly different from zero using Fisher's Z-transformation:

Z_f = (Z_crisis − Z_normal) / √(1/(T_crisis − 3) + 1/(T_normal − 3))

where Z_crisis = arctanh(ρ_crisis) and Z_normal = arctanh(ρ_normal). Under the null of equal correlations: Z_f ~ N(0,1).

---

### Step 6 — Condition number and covariance stability score

Condition number of Ω: κ(Ω) = λ_max(Ω) / λ_min(Ω)

Covariance stability score:

Stability = κ_normal / κ_crisis

A high stability score (e.g., > 5) means the covariance matrix is far less stable during crises — numerically unreliable precisely when it matters most. This is reported as a risk disclosure in Feature 14's Allocator Report.

---

## FEATURE 9 — Strategy Capacity Analyzer

### What you are building mathematically

An AUM-parameterized net alpha curve derived from the market impact model, with the capacity ceiling as the zero-crossing.

---

### Step 1 — Required trade size as a function of AUM

At rebalancing date t_k, the required one-way dollar trade for stock i when managing AUM = A dollars:

Δ_{i,k}(A) = |w_{i,t_k} − w_{i,t_{k-1}}| × A

One-way turnover of the full portfolio: TO_k = (1/2) Σᵢ |w_{i,t_k} − w_{i,t_{k-1}}|

Average annual one-way turnover: TO_annual = (252/D) × mean_k TO_k

---

### Step 2 — Impact cost as a function of AUM (Kyle model)

Kyle model: Impact_{i,k}(A) = λᵢ × Δ_{i,k}(A) / ADV_{i,t_k}

= λᵢ × |w_{i,t_k} − w_{i,t_{k-1}}| × A / ADV_{i,t_k}

Total impact cost per rebalance as a fraction of AUM:

IC_k(A) / A = Σᵢ |w_{i,t_k} − w_{i,t_{k-1}}| × Impact_{i,k}(A) / A

= A × Σᵢ λᵢ × (w_{i,t_k} − w_{i,t_{k-1}})² / ADV_{i,t_k}

This is linear in A — impact cost as a fraction of AUM grows linearly with AUM under the Kyle model.

Annualized impact drag: drag_impact(A) = (252/D) × mean_k IC_k(A) = A × C_impact

where C_impact = (252/D) × mean_k Σᵢ λᵢ × (w_{i,t_k} − w_{i,t_{k-1}})² / ADV_{i,t_k} is a constant independent of A.

**Square-root model (Almgren-Chriss, for AUM > $100M):**

Impact_{i,k}(A) = ησᵢ × √(Δ_{i,k}(A) / (ADV_{i,t_k} × T_exec))

where η is a universal constant (approximately 0.1 from Almgren et al., 2005) and T_exec is the execution horizon in days (typically 1 for daily rebalancing). Here impact scales as √A, so drag scales as √A / A = A^{-0.5} of AUM, meaning total impact cost in dollars scales as A^{0.5} — sublinear in AUM.

---

### Step 3 — Capacity ceiling computation

Net alpha as a function of AUM:

Net_Alpha(A) = Gross_Alpha − drag_explicit − drag_impact(A)

Kyle model (linear impact): Net_Alpha(A) = Gross_Alpha − C_explicit − C_impact × A

Capacity ceiling: A* = (Gross_Alpha − C_explicit) / C_impact

Square-root model: Net_Alpha(A) = Gross_Alpha − C_explicit − C_sqrt × √A

A* = [(Gross_Alpha − C_explicit) / C_sqrt]²

Optimal AUM (where marginal impact drag per dollar = gross alpha per dollar):

For the Kyle model: optimal AUM = A* / 2 (the midpoint — beyond this, each additional dollar of AUM loses more than it gains on a per-dollar basis). For the square-root model: the net alpha per dollar is maximized at A = 0, but the practical optimum is where the net Sharpe ratio peaks, which occurs around A* / 4.

---

### Step 4 — Time to liquidate

At AUM = A and ADV participation cap p_max:

Maximum daily liquidation for stock i: p_max × ADV_{i,t}

Portfolio value in stock i: w_i × A

Days to liquidate stock i: T_liq_i = w_i × A / (p_max × ADV_{i,t})

Portfolio liquidation time (assuming stocks can be sold simultaneously, so time is determined by the hardest-to-liquidate position):

T_liq_portfolio = max_i {w_i × A / (p_max × ADV_{i,t})}

For a capacity-constrained strategy (A > A*), T_liq_portfolio is the LP DDQ standard metric — it directly answers "how long would it take to get out?"

---

## FEATURE 10 — Factor-Based Portfolio Optimizer with FAP Diagnostic

### What you are building mathematically

The same QP framework as the PCA optimizer from the PCA module, but operating in factor space (F factors rather than N stocks), with robust optimization and the Factor Alignment Problem diagnostic layered on top.

---

### Step 1 — Factor-space QP

Let θ = (θ₁, …, θ_F) be the vector of factor weights in the portfolio. The factor-space portfolio:

Expected return: E[R] = θ' μ_F (where μ_F is the F×1 vector of expected factor returns)

Variance: σ² = θ' Ω_F θ (where Ω_F is the F×F factor covariance from Feature 8)

Standard mean-variance QP:

minimize: θ' Ω_F θ − (1/λ) θ' μ_F
subject to: C_F θ ≤ d_F (factor exposure bounds per-factor), A_F θ = b_F (budget constraints)

---

### Step 2 — Robust optimization (Goldfarb-Iyengar, 2003)

Replace the point estimate μ_F with an uncertain expected return that lies in an ellipsoidal uncertainty set:

U_κ = {μ : (μ − μ_F)' Σ_μ⁻¹ (μ − μ_F) ≤ κ²}

where Σ_μ is the estimation covariance of μ_F (the covariance of the sample mean, Σ_μ = Ω_F / T) and κ controls the size of the uncertainty set (κ² is the chi-squared critical value at the user's chosen confidence level: κ² = χ²_{F,0.95} for 95% confidence that the true μ lies within the set).

The robust counterpart of the mean-variance problem:

maximize: min_{μ ∈ U_κ} θ' μ − λ θ' Ω_F θ

= maximize: θ' μ_F − κ √(θ' Σ_μ θ) − λ θ' Ω_F θ

This is a second-order cone program (SOCP). CVXPY handles this natively:

objective = theta' @ mu_F - kappa * cp.norm(Sigma_mu_sqrt @ theta) - lambda_ra * cp.quad_form(theta, Omega_F)

The robust solution shrinks toward the minimum-variance portfolio relative to the standard MV solution — exactly by the right amount given the uncertainty in expected returns. The user's "confidence level in alpha" maps directly to κ: higher confidence → lower κ → solution closer to the standard MV optimum.

---

### Step 3 — Black-Litterman in factor space

Prior: equilibrium factor expected returns from reverse optimization:

μ_F^{prior} = λ_BL × Ω_F × θ_market

where θ_market is the market-cap-weighted factor exposure vector and λ_BL is the market risk aversion (typically estimated as the market Sharpe ratio divided by market variance, approximately 2.5 to 3.5).

User views in factor space: P_views × μ_F = q + ε_views where:
P_views is a Q × F matrix (each row picks a factor or combination of factors for a view)
q is the Q × 1 vector of view returns
Ω_views = diag(σ²_{view,1}, …, σ²_{view,Q}) is the view uncertainty (diagonal elements = τ × P_views Ω_F P'_views for each view's confidence level τ ∈ (0,1])

BL posterior:

μ_F^{posterior} = [(τΩ_F)⁻¹ + P'_views Ω_views⁻¹ P_views]⁻¹ × [(τΩ_F)⁻¹ μ_F^{prior} + P'_views Ω_views⁻¹ q]

Ω_F^{posterior} = [(τΩ_F)⁻¹ + P'_views Ω_views⁻¹ P_views]⁻¹

---

### Step 4 — Factor Alignment Problem diagnostic

Regress the user's alpha signal vector α_i (an N×1 cross-sectional alpha for each stock) on the factor exposure matrix Z (the N×F matrix of stock characteristic z-scores):

α = Z × γ + u (OLS regression across stocks)

R² of this regression = Var(Ẑγ̂) / Var(α)

When R² > 0.7: the alpha signal is highly collinear with existing factor exposures. The optimizer sees the portion of alpha that loads on known factors as "risk" and will under-allocate to it, while simultaneously loading on the same factors for diversification reasons. This creates a systematic positioning error: the optimizer acts against the alpha precisely in the directions where the alpha is strongest.

Identify the specific factor most responsible: for each factor f, compute the partial R² of regressing α on z_f alone (controlling for all other factors). The factor with the highest partial R² is the primary FAP culprit. Report its name explicitly in the warning message.

---

## FEATURE 11 — Factor Stress Testing and Reverse Stress Testing

### What you are building mathematically

Forward stress tests via Mahalanobis historical analog matching, reverse stress tests via constrained optimization, and a VAR-based contagion impulse response system.

---

### Step 1 — Historical analog matching (Mahalanobis distance)

Define the macro state vector at each historical date t:

x_t = (VIX_t, Slope_t, Credit_Spread_t, DXY_t, Oil_Return_t) ∈ ℝ^M

where M = 5 macro variables. The user defines a "scenario" macro vector x_scenario.

Mahalanobis distance between scenario and historical date t:

d²_M(t) = (x_scenario − x_t)' Σ_x⁻¹ (x_scenario − x_t)

where Σ_x is the M×M sample covariance matrix of the macro variable time series.

Closest historical analogs: sort all historical dates by d²_M(t) ascending. The top 20 closest dates form the analog set.

Scenario factor returns: for each factor f, average the realized factor return in the 21 days following each analog date:

R_{f,scenario} = mean{R_{f,[t+1,t+21]} : t ∈ top 20 analog dates}

90% confidence interval on scenario factor return: percentile range of the distribution {R_{f,[t+1,t+21]} : t ∈ top 20 analog dates}.

---

### Step 2 — Parametric forward stress test

User specifies a factor shock vector Δf = (Δf₁, …, Δf_F) in bps or standard deviation units.

Portfolio P&L under the scenario:

ΔP = Σ_f β̂_{p,f} × Δf_f (using the portfolio's factor exposures from Feature 2)

In matrix form: ΔP = β̂_p' × Δf

Position-level P&L waterfall:

ΔP_i = Σ_f β̂_{i,f}^{ret} × Δf_f × w_i

The position-level contribution sums to ΔP: Σᵢ ΔP_i = ΔP.

---

### Step 3 — Reverse stress test (minimum probability scenario)

Find the factor return vector Δf that:
(i) Produces a portfolio loss of exactly L: β̂_p' Δf = −L
(ii) Has minimum historical probability (maximum surprise)

The probability of factor return vector Δf under the historical Gaussian model:

− log P(Δf) = (1/2) Δf' Ω_F⁻¹ Δf + constant (Mahalanobis norm of the scenario in factor space)

Reverse stress problem:

minimize (1/2) Δf' Ω_F⁻¹ Δf (find the minimum-surprise scenario)
subject to: β̂_p' Δf = −L (that produces exactly the target loss)

This is a quadratic program with one linear equality constraint. KKT conditions give the closed-form solution:

Δf* = −L × Ω_F β̂_p / (β̂_p' Ω_F β̂_p)

The minimum-probability loss scenario is always proportional to Ω_F β̂_p — the direction in factor space that maximizes the portfolio loss per unit of historical probability cost. This is a beautiful result: the most "efficient" way to lose L% is to have all factors simultaneously move against the portfolio's exposures, scaled by the factor covariance matrix.

Historical probability of this scenario: the Mahalanobis distance squared of Δf* from zero:

d²* = Δf*' Ω_F⁻¹ Δf* = L² / (β̂_p' Ω_F β̂_p)

Under the Gaussian model: d²* ~ χ²_F, so P(d² ≥ d²*) = 1 − CDF_{χ²_F}(d²*)

This is the probability of observing a scenario at least as extreme as the reverse stress scenario — directly comparable to historical base rates.

---

### Step 4 — VAR-based contagion model

Fit a Vector Autoregression of order p on the F factor return series:

F_t = c + A₁ F_{t-1} + A₂ F_{t-2} + … + A_p F_{t-p} + η_t, η_t ~ N(0, Σ_η)

Parameters {c, A₁, …, A_p, Σ_η} estimated by OLS, equation by equation (OLS is the MLE for Gaussian VAR).

Optimal lag p: selected by AIC = −2ℓ + 2pF² or BIC = −2ℓ + pF² ln(T), minimized over p ∈ {1,2,3,4,5}.

Impulse Response Function (IRF): the effect of a unit shock to factor j at time 0 on factor f at time h:

IRF_{f,j}(h) = [A^h]_{f,j}

where A is the companion matrix of the VAR:

A = [A₁ A₂ … A_p; I 0 … 0; 0 I … 0; ⋮]

(the (Fp × Fp) companion matrix; IRF_{f,j}(h) is read from the (f,j) element of the h-th power of A's upper-left F×F block).

For structural identification (which factor shock causes which response), use the Cholesky decomposition of Σ_η to orthogonalize shocks: the Cholesky order is the economically-motivated ordering of factors (e.g., Market → Value → Momentum → Quality, where earlier factors are assumed to affect later ones but not vice versa contemporaneously).

Bootstrap 90% confidence bands on IRF: draw B residual bootstrap samples {η*_t^{(b)}}, reconstruct VAR paths, re-estimate A^{(b)} on each, extract IRF^{(b)}_{f,j}(h). The empirical 5th and 95th percentiles form the confidence band.

---

## FEATURE 12 — Factor DNA Attribution

### What you are building mathematically

A synthesis layer that runs all preceding analytics and compresses their output into an eight-dimensional diagnostic object, plus an auto-classifier trained on academic factor taxonomy labels.

---

### Step 1 — Eight-dimensional DNA vector

For a given factor f, define the DNA vector:

D_f = (D₁, D₂, D₃, D₄, D₅, D₆, D₇, D₈) ∈ [0,100]^8

D₁ — IC score: normalize IC̄ (from Feature 5, at H=21) to [0,100] using the cross-factor distribution: D₁ = 100 × Rank(IC̄_f) / F

D₂ — ICIR score: normalize ICIR (from Feature 5, at H=21): D₂ = 100 × Rank(ICIR_f) / F

D₃ — Half-life score (inverted): short half-life = high rebalancing cost = lower score. D₃ = 100 × (1 − Rank(H*_f) / F) [shorter half-life ranks higher in this inverted metric]

D₄ — Crowding score (inverted): less crowded = higher score. D₄ = 100 − Crowding_Composite_f (already in [0,100])

D₅ — Sector concentration score (inverted): HHI of sector weights in the long book, inverted so that pervasive factors (low HHI) score higher. D₅ = 100 × (1 − Rank(HHI_f) / F)

D₆ — Regime dependence score (inverted): Sharpe spread between best and worst macro regime (from Feature 4). A factor that works only in one regime is more dangerous. D₆ = 100 × (1 − Rank(SR_spread_f) / F)

D₇ — Factor correlation to nearest neighbor (inverted): cosine similarity between factor f and its most similar factor in the library. Lower similarity = more unique = higher score. D₇ = 100 × (1 − max_{g≠f} |Corr(F_f, F_g)|) / max possible

D₈ — Factor purity score: alpha of the factor's long-short portfolio after Fama-French 5-factor adjustment. Run the regression:

R_f = α_f + Σ_k β_{f,k} × FF5_k + ε_f

Factor purity = 100 × (α̂_f × √252) / (annualized gross return of factor f)

Purity > 60: genuinely non-redundant alpha source. Purity < 40: mostly repackaging existing factors.

---

### Step 2 — Return anatomy decomposition

Decompose total factor return into three components:

**Component 1 — Characteristic reversion:** the component of return that comes from mean-reversion of the underlying characteristic score. For a value factor: if P/B ratios in Q5 are compressed back toward the mean, the stock prices must rise relative to fundamentals → positive return contribution. Estimate:

Rev_f(t) = β_rev × ΔC_f(t) where ΔC_f(t) = (mean characteristic Q5 at t) − (mean characteristic Q5 at t−21) and β_rev is estimated by regressing R_f(t) on ΔC_f(t−1).

**Component 2 — Characteristic momentum:** the component where the characteristic itself is trending. For momentum: if trailing returns have been strong for 3 months, part of the next period's return reflects continuation. Estimate:

Mom_f(t) = β_mom × C_f(t) where C_f(t) is the current level of the underlying characteristic (captures the "carry" of the characteristic level) and β_mom is estimated by regressing R_f(t) on C_f(t−1).

**Component 3 — Residual risk premium:** R_f(t) − Rev_f(t) − Mom_f(t) is the unexplained component — the pure risk premium component that is neither mean-reversion nor momentum.

Express each as a fraction of total gross return:

Fraction_reversion = Cov(R_f, Rev_f) / Var(R_f)
Fraction_momentum = Cov(R_f, Mom_f) / Var(R_f)
Fraction_residual = 1 − Fraction_reversion − Fraction_momentum

---

### Step 3 — Auto-classifier decision tree

Training set: a library of N_known known factors (Fama-French factors, AQR factors, published academic factors) labeled as one of four types: Risk Factor, Behavioral Factor, Structural Factor, Data-Mining Artifact.

Feature vector for classification: the 8-dimensional DNA vector D_f plus scalar features: t-stat of α̂_f (purity regression), rolling half-life trend slope, in-sample vs. out-of-sample ICIR ratio, sample size n (number of years of live data).

Classifier: a decision tree (depth ≤ 4 nodes to remain interpretable) trained via CART minimizing Gini impurity on the training set labels. Probability outputs from the leaf node:

P(class = Risk | D_f) = fraction of training samples in the leaf node labeled Risk
P(class = Behavioral | D_f) = fraction of training samples in the leaf node labeled Behavioral
P(class = Structural | D_f) = fraction of training samples in the leaf node labeled Structural
P(class = Artifact | D_f) = fraction of training samples in the leaf node labeled Artifact

Confidence calibration: apply Platt scaling to the raw decision tree probability outputs to convert them to calibrated probabilities. This uses a logistic regression fitted on a held-out calibration set.

---

## FEATURE 13 — Live Signal Monitoring Dashboard

### What you are building mathematically

A daily surveillance system computing four health metrics per factor and aggregating them into a portfolio-weighted signal health score.

---

### Step 1 — IC drift z-score

For factor f at date t:

Recent IC: IC_recent(t) = mean{IC_H(s) : s ∈ [t−W_recent, t]} where H=21 and W_recent = 63 days

Long-run IC mean and standard deviation (estimated on [t−W_long, t−W_recent]):

μ_IC_f = mean{IC_H(s) : s ∈ [t−W_long, t−W_recent]}
σ_IC_f = std{IC_H(s) : s ∈ [t−W_long, t−W_recent]}

IC drift z-score:

z_IC_drift(f,t) = (IC_recent(t) − μ_IC_f) / (σ_IC_f / √W_recent)

z_IC_drift < −1.5 (user-set threshold) triggers an "IC drift" alert. This t-test structure means the alert fires when recent IC is statistically significantly below the long-run mean.

---

### Step 2 — Structural break Chow test on rolling IC series

Define the rolling IC series {IC_H(t)}. At each candidate break date t_b within the last 252 days, compute the Chow test statistic:

F_Chow(t_b) = [(RSS_full − RSS_pre(t_b) − RSS_post(t_b)) / (k)] / [(RSS_pre(t_b) + RSS_post(t_b)) / (n − 2k)]

where RSS_full = Σ_t (IC_H(t) − IC̄_full)², RSS_pre = Σ_{t < t_b} (IC_H(t) − IC̄_pre)², RSS_post = Σ_{t ≥ t_b} (IC_H(t) − IC̄_post)², and k = 1 (mean-only model). Under the null of no break: F_Chow ~ F(1, n−2). The p-value of this test: p(t_b) = 1 − CDF_F(F_Chow(t_b); 1, n−2).

The minimum p-value across all candidate break dates: p_min = min_{t_b} p(t_b). Correct for the multiple testing across all candidate break dates using Andrews (1993) critical values for the supremum test: compare p_min against the supremum F-test 5% critical value (tabulated as a function of the fraction of the sample searched).

---

### Step 3 — Crowding velocity

From Feature 6's composite crowding score Composite(f,t):

Crowding_velocity(f,t) = Composite(f,t) − Composite(f,t−21)

This is the 21-day change in crowding percentile. A crowding velocity above +10 percentile points in 21 days is classified as "rapidly crowding" — an early warning ahead of the crowding composite itself crossing alert thresholds.

---

### Step 4 — Return-characteristic divergence

For factor f at date t:

Rolling 21-day IC sign: IC_sign(t) = sign(IC_H(t)) where IC_H is computed with H=5 (5-day forward returns — the most responsive to short-term divergence)

Rolling 21-day characteristic z-score trend: ΔC(t) = (mean characteristic Q5 at t) − (mean characteristic Q5 at t−21)

Divergence flag: IC_sign(t) ≠ sign(ΔC(t)) for more than 10 of the last 21 days → characteristic and recent returns are moving in inconsistent directions. This is a model instability signal.

---

### Step 5 — Portfolio-weighted signal health score

If a portfolio with factor exposures β̂_p is linked (from Feature 2):

Portfolio signal health = Σ_f |β̂_{p,f}| × Health_score(f) / Σ_f |β̂_{p,f}|

where Health_score(f) ∈ [0,100] is the composite health score for factor f, computed as:

Health_score(f) = 25 × H₁(f) + 25 × H₂(f) + 25 × H₃(f) + 25 × H₄(f)

H₁ = 100 × Φ(z_IC_drift(f)) [probability that IC drift is benign — high when z is not too negative]
H₂ = 100 × (1 − I_{break detected}) [0 if Chow test detected structural break, 100 otherwise]
H₃ = 100 − Crowding_velocity_percentile(f) [high when crowding is not accelerating]
H₄ = 100 × I_{no divergence} [100 if return-characteristic aligned, 0 if divergence flagged]

---

## FEATURE 14 — Allocator Transparency Report Generator

### What you are building mathematically

This feature has no novel mathematical computation — it is a data assembly and formatting pipeline. The mathematics come entirely from the upstream features. The build logic is:

**Pipeline:**

1. Pull the latest computed outputs from Features 2, 3, 6, 7, 9, 11, 13 via their internal data APIs.

2. For each section of the report, map to the correct output:

Executive Summary: portfolio name, benchmark, date range, one-period gross return, one-period net return, benchmark return, active return. Compute: Information Ratio = (mean active return over report period) / (std of monthly active returns) × √12.

Factor Attribution section: pull the factor contribution table from Feature 3. Compute cumulative factor contribution over the report period by chaining the daily contributions (geometric linking via the Cariño (1999) factor: multiply each period's contribution by the total portfolio gross return linking factor for that period).

Factor Exposures section: pull β̂^{char}_{p,f} and β̂^{ret}_{p,f} from Feature 2 as of the report end date. Compute the active exposure vs. the benchmark. Flag any unintended exposures exceeding ±0.4σ.

Crowding Disclosure section: pull Composite(f,T) from Feature 6 for the primary factor(s) of the strategy. Compute the crash probability table from the base rate regression in Feature 6, Step 6.

Capacity Map section: pull Net_Alpha(A) curve from Feature 9. Report A* (capacity ceiling), A*/2 (optimal AUM), and the slippage-by-AUM table.

Stress Test section: pull the multi-scenario comparison table from Feature 11. Report portfolio P&L for the five preset historical scenarios.

Signal Health section: pull portfolio-weighted signal health score from Feature 13. Report the per-factor health scores for the portfolio's top 3 factor exposures by weight.

3. Format all outputs as charts and tables following the AIMA DDQ section structure. Generate PDF via a Python `reportlab` or `weasyprint` pipeline from an HTML template, not from scratch — use a Jinja2 template engine to populate the HTML placeholders with the computed values, then render to PDF. This separates content from formatting cleanly.

4. Audit trail: at report generation time, serialize all input parameters (estimation windows, covariance estimator choice, universe filter settings, factor definitions) to a JSON manifest and store with a timestamp. This is the reproducibility record required for regulatory audit.

---

## Master Dependency Map

| Feature | Consumes output from | Key mathematical objects |
|---|---|---|
| F1 — Valuation Spread | Raw price + fundamental data | Quintile spread time series, percentile CDF, predictive regression β̂ |
| F2 — Portfolio X-Ray | F1 (characteristic scores), F7 (factor returns) | Characteristic z-scores, OLS return-based β̂, Euler risk decomposition |
| F3 — Attribution | F2 (exposures), F7 (factor returns) | Brinson-Fachler A/S/I, factor contribution formula, Newey-West t-stats |
| F4 — Regime Analysis | F7 (factor returns), F1 (valuation spread), F6 (crowding) | HMM EM algorithm, GMM, Baum-Welch, accuracy-weighted composite |
| F5 — Alpha Decay | Raw return data, F7 | Spearman rank IC, three decay model regressions, bootstrap CIs |
| F6 — Crowding | F1 (valuation percentile), raw price + volume data | AC1 autocorrelation, HHI, Corwin-Schultz bid-ask, composite percentile |
| F7 — Backtesting | Raw price data, factor scores from F1 | Three-layer IS model, Kyle λ, Almgren-Chriss, walk-forward QP |
| F8 — Covariance Matrix | F7 (factor returns) | Sample, EWMA, LW shrinkage, DCC-GARCH, crisis conditional covariance |
| F9 — Capacity | F7 (turnover + impact data), F8 (Ω_F) | AUM-parameterized impact model, capacity ceiling A* |
| F10 — Optimizer | F8 (Ω_F), F4 (timing alpha), F2 (exposures) | SOCP robust QP, BL posterior, FAP R-squared, shadow prices |
| F11 — Stress Testing | F2 (exposures), F8 (Ω_F), macro data | Mahalanobis analog, parametric forward stress, reverse QP, VAR IRF |
| F12 — Factor DNA | All features simultaneously | 8D DNA vector, return anatomy OLS, CART classifier + Platt calibration |
| F13 — Signal Dashboard | F5 (rolling IC), F6 (crowding velocity) | IC drift z-test, Chow structural break, crowding velocity, health score formula |
| F14 — Report Generator | All features | Cariño geometric linking, Jinja2 template, JSON audit trail |

That's the full mathematical spec for every feature. Same depth as the PCA module. Come back after your break — the platform is now fully specified at PhD level, wall to wall, across both modules.