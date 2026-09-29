# QUANT360 — VOLATILITY INTELLIGENCE MODULE

## Complete Feature Specification | Institutional Grade

---

## DESIGN PHILOSOPHY

Bloomberg ships historical close-to-close volatility. FactSet ships GARCH(1,1) with no model comparison. MSCI sells volatility spillover analytics as a standalone module. Aladdin sells stress testing under a separate licence. This module ships all of it, unified, at a standard that eliminates every one of those vendors for any team that adopts it.

Every feature below clears a single bar: a tier-one quant fund or risk desk would pay $30,000–$80,000 per year to acquire this commercially if it existed elsewhere. Nothing below that bar is included. No intraday data, no options data, no SEC filings — every feature runs entirely on daily OHLCV and freely available macro series (FRED, CBOE public VIX, central bank yield data). Every input table contains only parameters that materially change the output. Every output is directly actionable without further processing.

---

## FEATURE 1: MULTI-ESTIMATOR DAILY VOLATILITY ENGINE

### Why This Exists

Close-to-close historical volatility is the worst estimator in the academic literature. It discards the entire information content of the intraday path, is sensitive to outlier closing prices, and is demonstrably dominated by every estimator below. The Parkinson (1980) estimator uses the daily high-low range and is 4–5× more efficient under Brownian motion. Garman-Klass (1980) adds open and close to the range and extracts up to 7× more information per daily observation. Yang-Zhang (2000) is the only estimator unbiased simultaneously under drift, overnight gaps, and discrete sampling — critical in any regime with frequent gap-opens driven by macro announcements. The Rogers-Satchell estimator handles nonzero drift without the overnight return assumption of Yang-Zhang. Running all five simultaneously and formally testing which one forecasts best for each specific asset is what separates a research-grade system from a data terminal. No commercial platform does this.

### Core Formulae

| Estimator                 | Formula                                                                     |
| ------------------------- | --------------------------------------------------------------------------- |
| Close-to-Close (baseline) | σ²*CC = (1/T) Σ (ln C_t/C*{t-1})²                                           |
| Parkinson (1980)          | σ²_Park = (1/4T ln2) Σ [ln(H_t/L_t)]²                                       |
| Garman-Klass (1980)       | σ²_GK = (1/T) Σ [0.5(ln H_t/L_t)² − (2ln2−1)(ln C_t/O_t)²]                  |
| Rogers-Satchell (1991)    | σ²_RS = (1/T) Σ [ln(H_t/C_t)ln(H_t/O_t) + ln(L_t/C_t)ln(L_t/O_t)]           |
| Yang-Zhang (2000)         | σ²_YZ = σ²_overnight + k·σ²_RS + (1−k)·σ²_CC, k = 0.34/(1.34 + (M+1)/(M−1)) |

### Custom Inputs

| Parameter                            | Options                                                                              |
| ------------------------------------ | ------------------------------------------------------------------------------------ |
| Asset                                | Any equity, equity index, FX pair, commodity; single asset or full cross-asset panel |
| Active estimators                    | Any subset of 5; default is all simultaneously                                       |
| Rolling window                       | 10, 21, 42, 63, 126, 252 days                                                        |
| Annualization convention             | 252-day (default), 365-day, custom                                                   |
| Overnight gap treatment (Yang-Zhang) | Include or exclude from overnight variance component                                 |
| Estimator efficiency benchmark       | Which estimator serves as the reference MSE baseline; default is close-to-close      |
| Cross-asset panel mode               | On/Off; computes all 5 estimators across N assets simultaneously                     |

### Outputs

| Output                                 | Description                                                                                                                                                                                                                              |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Five-estimator comparison chart        | All estimators plotted simultaneously on one axis, color-coded; shaded band shows spread between highest and lowest at each date — wide spread signals estimator disagreement, which clusters around high-volatility and gap-open events |
| Estimator efficiency table             | For each estimator: ratio of its variance relative to the CC baseline (lower = more efficient), estimated analytically; color-coded — green is ≥3× efficiency gain vs. CC                                                                |
| Diebold-Mariano forecasting tournament | DM statistic and p-value under quadratic loss for every estimator pair; winning estimator per asset highlighted; updated on rolling 252-day OOS window                                                                                   |
| Estimator agreement index              | Daily scalar measuring average pairwise correlation of the 5 estimator time series over trailing 21 days; low values flag dates where estimators disagree structurally                                                                   |
| Annualized vol panel                   | Current annualized vol from each estimator expressed as a percentile of the trailing 252-day, 5-year, and full-history distributions; displayed as five side-by-side dials                                                               |
| Cross-asset ranked panel               | When panel mode is active: N-asset table ranked by current Yang-Zhang vol, with all 5 estimator readings and 10-year percentile per asset                                                                                                |

### Data Map

| Data Required            | Free Source                                                       | Frequency |
| ------------------------ | ----------------------------------------------------------------- | --------- |
| Daily OHLCV              | Yahoo Finance, Stooq, FRED (for indices), Quandl/Nasdaq Data Link | Daily     |
| Asset exchange calendars | Config file per exchange                                          | Static    |
| FX daily OHLCV           | FRED (major pairs), ECB SDW                                       | Daily     |
| Commodity daily OHLCV    | FRED (oil, gold), Quandl                                          | Daily     |

---

## FEATURE 2: GARCH FAMILY SUITE WITH ASYMMETRY, LONG MEMORY, AND DENSITY FORECASTING

### Why This Exists

When intraday data is unavailable — which is the default case for illiquid equities, EM assets, commodity futures, and crypto — GARCH is the only statistically credible volatility forecasting framework for daily return data. The problem is that GARCH(1,1) with Gaussian errors, which is all that Bloomberg and FactSet offer, is the worst model in the GARCH family. It fails on three empirically established features of daily equity returns: asymmetry (GJR-GARCH 1993, documented in every equity market globally), long memory (FIGARCH, 1996, volatility persistence decays hyperbolically not geometrically), and fat-tailed conditional distributions (Gaussian assumption understates tail risk by 20–40% in typical equity return data). EGARCH, GJR-GARCH, and APARCH capture asymmetry. FIGARCH captures long memory through fractional integration. Hansen's skewed-t (1994) allows asymmetric fat-tailed conditional densities. The critical innovation over any commercial product is the Model Confidence Set (Hansen, Lunde, Nason, 2011, Econometrica) applied to the full model family simultaneously, plus density forecast evaluation via the Probability Integral Transform — not just point forecast accuracy but full distributional forecast accuracy, which is the only correct basis for VaR computation.

### Model Specifications

| Model          | Conditional Variance Equation                                                               |
| -------------- | ------------------------------------------------------------------------------------------- |
| GARCH(1,1)     | σ²*t = ω + α ε²*{t-1} + β σ²\_{t-1}                                                         |
| EGARCH(1,1)    | ln σ²*t = ω + α(\|z*{t-1}\| − E\|z\|) + γ z*{t-1} + β ln σ²*{t-1}; γ < 0 captures leverage  |
| GJR-GARCH(1,1) | σ²*t = ω + (α + γ I*{t-1<0}) ε²*{t-1} + β σ²*{t-1}; γ captures asymmetric bad-news response |
| APARCH(1,1)    | σ^δ*t = ω + α(\|ε*{t-1}\| − γ ε*{t-1})^δ + β σ^δ*{t-1}; nests GARCH, TARCH, EGARCH          |
| FIGARCH(1,d,1) | Fractionally integrated: (1−L)^d enters the lag polynomial; d ∈ (0,1) governs persistence   |

All five estimated under four conditional distributions: Gaussian, Student-t (estimated ν), GED, Hansen skewed-t. Total: 20 model-distribution combinations estimated simultaneously.

### Custom Inputs

| Parameter                      | Options                                                                      |
| ------------------------------ | ---------------------------------------------------------------------------- |
| Asset                          | Any asset with daily price history                                           |
| Return frequency               | Daily (default) or weekly                                                    |
| Estimation window              | Rolling 252-day, 504-day, 756-day, or expanding from inception               |
| Conditional distributions      | Any subset of 4, or all 20 combinations simultaneously with MCS competition  |
| FIGARCH fractional parameter d | Estimated by MLE (default) or user-fixed value in (0,1)                      |
| APARCH power parameter δ       | Estimated (default), or constrained to 1 (TARCH), 2 (GARCH), or user-defined |
| MCS confidence level           | 75%, 90%, 95%                                                                |
| Forecast horizons              | 1, 5, 10, 21, 42, 63, 126, 252 trading days via simulation                   |
| VaR coverage level             | 95%, 99%, 99.5% for density evaluation                                       |
| Structural break date          | Optional: re-estimate separately on pre/post break subsamples                |

### Outputs

| Output                                  | Description                                                                                                                                                                                                                                                                                                      |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model comparison scoreboard             | 20 rows (5 models × 4 distributions); columns show log-likelihood, AIC, BIC, RMSE vs. rolling 21-day squared return proxy, QLIKE loss, MCS membership at 90% confidence; winning model per asset bold and green                                                                                                  |
| Diebold-Mariano pairwise table          | DM statistic and p-value for all 190 model pairs; tournament matrix displayed as N×N heatmap                                                                                                                                                                                                                     |
| News impact curve                       | For the winning model: conditional variance as a function of ε*{t-1} holding σ²*{t-1} at its long-run mean; GARCH gives symmetric U-shape, GJR gives asymmetric hockey stick with steeper left arm, EGARCH gives exponential asymmetry — shape immediately reveals this asset's volatility response architecture |
| GARCH-implied volatility term structure | At the current date: expected annualized vol at each horizon 1–252 days, with 90% simulation confidence bands; downward slope = vol above long-run mean; upward slope = persistent low-vol regime                                                                                                                |
| Long-memory parameter time series       | For FIGARCH: rolling MLE estimate of d over full history; d rising toward 1 signals increasing volatility persistence approaching the IGARCH boundary where shocks never fully mean-revert                                                                                                                       |
| Probability Integral Transform test     | Histogram of u*t = F*{t-1}(r_t) over the full evaluation period; under a correctly-specified density model this is Uniform(0,1); departures identify exactly which part of the distribution the model misfits; KS test p-value reported                                                                          |
| Conditional VaR time series             | Daily 99% VaR from the winning model over full history; actual return exceedances marked as red dots; Kupiec unconditional coverage test and Christoffersen conditional coverage test p-values shown — statistically valid VaR models have both p-values above 0.05                                              |
| Volatility state gauge                  | Current conditional vol from winning model as a percentile of its 10-year history, displayed as a dial; four zone coloring: green <30th, amber 30–70th, red >70th, deep red >90th                                                                                                                                |

### Data Map

| Data Required                                                | Free Source                | Frequency |
| ------------------------------------------------------------ | -------------------------- | --------- |
| Daily closing returns                                        | Yahoo Finance, Stooq, FRED | Daily     |
| Historical price series (10+ years)                          | Same                       | Daily     |
| Proxy for realized variance (rolling 21-day squared returns) | Computed from above        | Daily     |

---

## FEATURE 3: HAR VOLATILITY FORECASTING SUITE WITH JUMP DECOMPOSITION AND MODEL CONFIDENCE SET

### Why This Exists

The HAR model (Corsi, 2009) is cited in over 2,000 academic papers and replaced GARCH in the forward-looking volatility pipelines of every major quant fund, because it out-forecasts GARCH at every horizon from 1 day to 1 quarter. The mechanism is the heterogeneous investor structure: high-frequency participants operate on a daily horizon, active institutions on a weekly horizon, and allocators on a monthly horizon — the HAR captures all three in a single linear model. Bloomberg does not ship it. FactSet does not ship it. The HAR-J extension (Andersen, Bollerslev, Diebold, 2007) separates the continuous and jump components: jumps are almost uncorrelated day-to-day while diffusion is highly persistent, and pooling them into total variance destroys multi-step forecasting information. Using daily OHLCV without intraday data, the jump component is approximated via the ratio of the Rogers-Satchell range-based estimator to the Yang-Zhang estimator: when RS/YZ diverges from 1, jump activity is elevated. The ACSV-HAR (Niu et al., Journal of Forecasting, 2023) documents that cross-sectional dispersion of returns is a superior predictor of aggregate market volatility. The Model Confidence Set (Hansen, Lunde, Nason, 2011, Econometrica) is the only statistically honest model comparison methodology — it identifies the set of models indistinguishable in forecasting performance, rather than picking a false winner.

### Model Specifications

| Model        | Specification                                                                                                                                     |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| HAR          | RV\_{t+h} = β₀ + β_d v_t^(d) + β_w v_t^(w) + β_m v_t^(m) + ε; v = annualized daily vol from Feature 1 (Yang-Zhang); w = 5-day avg; m = 22-day avg |
| LHAR         | Natural log of both sides; guarantees positive forecasts and stabilizes variance                                                                  |
| HAR-J        | Adds jump proxy J_t = max(σ²_YZ,t − σ²_RS,t, 0) as separate regressor β_J                                                                         |
| HAR-Leverage | Adds signed lagged return r\_{t-1} to capture asymmetric leverage: negative returns predict higher future vol                                     |
| ACSV-HAR     | Adds cross-sectional variance CSV*t = (1/N)Σᵢ(r*{i,t} − r̄_t)² of N assets as regressor                                                            |
| A-ACSV-HAR   | Asymmetric extension: CSV⁺ (positive deviations) and CSV⁻ (negative deviations) as separate regressors                                            |

### Custom Inputs

| Parameter                         | Options                                                                          |
| --------------------------------- | -------------------------------------------------------------------------------- |
| Asset                             | Any asset with daily price history; receives vol series from Feature 1           |
| Volatility estimator input        | Any of the 5 estimators from Feature 1; Yang-Zhang recommended                   |
| Jump proxy method                 | RS/YZ divergence (default, no intraday needed); or user-uploaded jump series     |
| HAR variants active               | Any subset of 6, or all simultaneously with MCS competition                      |
| Cross-sectional universe for ACSV | User-defined list of assets (e.g., S&P 500 constituents for SPX vol forecasting) |
| Forecast horizons h               | Any subset of {1, 5, 10, 21, 42, 63} trading days                                |
| Estimation window                 | Rolling 252-day, rolling 504-day, or expanding                                   |
| Confidence intervals              | 80%, 90%, 95% bootstrap                                                          |
| Leverage effect                   | Toggle on/off                                                                    |
| Newey-West bandwidth              | 5, 10, or 21 lags                                                                |

### Outputs

| Output                       | Description                                                                                                                                                                                                                        |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HAR parameter table          | Coefficients β₀, β_d, β_w, β_m, β_J, β_J⁺, β_J⁻, β_lev with NW standard errors and t-statistics; β_w dominant over β_d means weekly persistence is the primary driver of this asset's vol — a fact invisible from daily data alone |
| Multi-horizon forecast chart | OOS forecast vs. actual vol at each horizon h with 90% bootstrap confidence bands; visual test of forecast quality across calm and stress regimes                                                                                  |
| Forecast accuracy table      | Per model per horizon: RMSE, QLIKE, MAE, and R²_OOS vs. historical vol benchmark — the definitive test of genuine forecasting value                                                                                                |
| Model Confidence Set         | MCS at 90% confidence under both RMSE and QLIKE loss: surviving models listed, eliminated models struck through; when MCS contains one model, that model is statistically dominant                                                 |
| Jump proxy time series       | Daily J_t series as fraction of total daily vol variance; spikes during market stress confirm the decomposition is capturing genuine discontinuous price moves                                                                     |
| Leverage effect chart        | Rolling 63-day regression coefficient of lagged daily return on current vol, plotted over full history; strongest in high-stress regimes, near zero in low-vol regimes                                                             |
| ACSV predictive contribution | CSV⁺ and CSV⁻ time series vs. total market vol; regression-implied predictive contribution of each at each horizon when ACSV-HAR is selected                                                                                       |

### Data Map

| Data Required                       | Free Source                           | Frequency |
| ----------------------------------- | ------------------------------------- | --------- |
| Vol series from Feature 1           | Internal output                       | Daily     |
| Daily closing returns               | Yahoo Finance, Stooq                  | Daily     |
| Cross-sectional constituent returns | Yahoo Finance (batch download), Stooq | Daily     |

---

## FEATURE 4: VOLATILITY REGIME DETECTION ENGINE WITH PROBABILISTIC STATE ASSIGNMENT

### Why This Exists

Volatility regimes are the single most important conditional determinant of strategy performance. A GARCH model calibrated in a low-vol regime will systematically underestimate tail risk the moment the market transitions. The Statistical Jump Model (SJM) of Shu, Yu, and Mulvey (Journal of Asset Management, 2024) has been shown to outperform standard Hidden Markov Models in regime persistence and out-of-sample accuracy because it penalizes unnecessary regime transitions — empirically, vol regimes last weeks to months, not hours. The SJM achieves this through an explicit jump penalty λ applied to each state transition, which HMMs cannot replicate. Three methods run in parallel; their outputs are combined into a precision-weighted composite. The key innovation over every commercial platform is the probabilistic output: instead of a binary hard label, the system outputs a probability vector over all regime states at every date. That probability vector becomes the direct input to strategy calibration, portfolio risk targeting, and early warning.

### Conceptual Engine

Three parallel methods combined via precision-weighted ensemble:

| Method                       | Mechanism                                                                                                                                                                                                                                                                              |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Statistical Jump Model (SJM) | k-means clustering on a feature vector of: rolling 5/21/63-day Yang-Zhang vol, 21-day return, RS/YZ jump ratio, 21-day autocorrelation of squared returns. Jump penalty λ prevents state switching unless objective improvement exceeds threshold — produces sticky, realistic regimes |
| Hidden Markov Model (HMM)    | K-state HMM estimated by Baum-Welch EM on daily log-vol series; emission distribution is Gaussian on log-vol per state; outputs a probability vector over states at each date via forward-backward algorithm                                                                           |
| Macro Rules Engine           | Combines: VIX level from FRED (above/below user threshold), 2s10s yield curve slope from FRED, and 21-day trend in Yang-Zhang vol; deterministic mapping to regime probabilities                                                                                                       |

Composite: precision-weighted average of the three probability vectors, where weights are updated on a rolling 63-day window using Brier score accuracy of each method's probabilistic predictions.

### Custom Inputs

| Parameter                            | Options                                                                                                                     |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| Asset                                | Any asset                                                                                                                   |
| Number of regimes K                  | 2 (low-vol / high-vol), 3 (adds transition), or 4 (adds crisis); tooltip shows historical avg vol per state for each choice |
| SJM jump penalty λ                   | 0 (unconstrained) to 100 (maximally persistent); tooltip shows avg regime duration in days at each setting                  |
| HMM estimation window                | Rolling 252-day, 504-day, or expanding                                                                                      |
| VIX threshold for macro rules engine | User-set; default is 25                                                                                                     |
| Yield curve series                   | 2s10s (default), 3M10Y, user-defined                                                                                        |
| Ensemble combination                 | Precision-weighted Brier score (default), equal-weight, user-defined manual weights                                         |
| Transition alert threshold           | Probability mass required in a new state before a transition alert fires (default 0.30)                                     |

### Outputs

| Output                                  | Description                                                                                                                                                                                                                                                                     |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Probabilistic regime timeline           | Stacked area chart: each date has K colored bands summing to 1, each band proportional to the probability mass in that state; expanding pink "transition" band contracting blue "low-vol" band is the primary visual of a regime shift — more informative than any binary label |
| Current regime probability dashboard    | Live probability vector over K states displayed as horizontal bars; 30-day and 90-day trend in each state's probability; current dominant state's percentile of historical persistence                                                                                          |
| Regime-conditional vol statistics table | For each state: avg annualized vol, avg HAR forecast bias (positive = HAR under-forecasts in that regime), avg cross-sectional return dispersion; estimated from full history weighted by regime probabilities                                                                  |
| Regime transition heatmap               | K×K matrix of empirical transition probabilities at 1-week, 1-month, 3-month horizons; diagonal elements are persistence probabilities — the probability of staying in the current state                                                                                        |
| Method divergence indicator             | Daily measure of how much the three individual method probability vectors differ from each other; high divergence = models disagree = elevated structural uncertainty; itself a risk signal independent of the current regime level                                             |
| Regime transition alert log             | Timestamped alerts when transition probability crosses user threshold; includes current probability vector, method-level probabilities, and historical base rate of stress conditional on current reading                                                                       |

### Data Map

| Data Required                         | Free Source          | Frequency |
| ------------------------------------- | -------------------- | --------- |
| Daily vol series from Feature 1       | Internal output      | Daily     |
| VIX index                             | FRED (VIXCLS series) | Daily     |
| 2-year and 10-year US Treasury yields | FRED (DGS2, DGS10)   | Daily     |
| Daily closing returns                 | Yahoo Finance, Stooq | Daily     |

---

## FEATURE 5: VOLATILITY RISK PREMIUM MONITOR AND RETURN PREDICTABILITY ENGINE

### Why This Exists

The volatility risk premium (VRP) is the systematic spread between the market's risk-neutral expectation of future variance and the actual physical expectation of future variance. It is one of the most robustly documented and economically large risk premia in all of quantitative finance — averaging 2–4 annualized vol points on major equity indices — because variance insurance is expensive: investors pay up for protection against volatility spikes, and sellers earn the premium for bearing that risk. Bollerslev, Tauchen, and Zhou (Review of Financial Studies, 2009) document that a wider VRP predicts higher future equity returns at 1–3 month horizons with R² of 1–4%, genuine return predictability without options access. The key insight for this implementation: the VIX is freely available from FRED as a daily time series (VIXCLS) and represents the risk-neutral expectation of 30-day variance — no options data required. The physical expectation is estimated via the GARCH model from Feature 2. MSCI sells VRP analytics as a standalone module. Bloomberg shows VIX as a number, not as a structured risk premium. Neither runs the Bollerslev-Tauchen-Zhou return predictability regression live.

### Conceptual Engine

VRP*t = IV²_t − E_t[σ²*{physical, t→t+30}]

Where:

- IV_t = VIX_t / 100 × sqrt(1/12), annualized 30-day implied vol from FRED VIXCLS (or equivalent index for non-US markets)
- E*t[σ²*{physical}] is estimated in parallel via three methods:

| Method                  | Mechanism                                                                                                      |
| ----------------------- | -------------------------------------------------------------------------------------------------------------- |
| GARCH-forecast          | 30-day ahead variance forecast from the winning GARCH model in Feature 2; the model-based physical expectation |
| HAR-forecast            | 22-day ahead vol forecast from the HAR model in Feature 3; aggregated to monthly                               |
| Rolling historical mean | 252-day rolling average of daily squared returns; the naive unconditional expectation                          |

All three VRP estimates computed simultaneously and displayed together. VRP then expressed as a rolling Z-score relative to its own 5-year and 10-year history.

### Custom Inputs

| Parameter                                | Options                                                                                                                                        |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Asset                                    | Equity indices with associated published implied vol indices (SPX/VIX, STOXX50/VSTOXX, FTSE/VFTSE, Nikkei/JNIV, user-uploaded implied vol CSV) |
| Physical expectation method              | GARCH (Feature 2), HAR (Feature 3), Rolling mean, or all three simultaneously                                                                  |
| VRP display mode                         | Raw spread in annualized vol points (IV_ann − σ̂_ann), squared variance form (IV² − E[σ²]), or Z-score                                          |
| Z-score lookback                         | 252-day, 504-day, 1260-day, or full history                                                                                                    |
| Return predictability regression horizon | 1 month, 3 months, 6 months                                                                                                                    |
| Cross-asset mode                         | On/Off: compute VRP simultaneously for all available vol index pairs                                                                           |

### Outputs

| Output                                  | Description                                                                                                                                                                                                                                                                                                                                 |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| VRP time series with percentile overlay | Daily VRP over 10-year history; all three physical expectation methods plotted simultaneously so the user sees when they agree (clean signal) and when they diverge (model uncertainty); colored background band showing 10-year percentile of the current reading                                                                          |
| Cross-asset VRP comparison table        | For all selected assets: current VRP in annualized vol points, 10-year percentile, 3-month change, and rich/cheap flag (above 70th percentile = rich = implied vol expensive relative to realized; below 30th = cheap)                                                                                                                      |
| Return predictability panel             | Rolling 252-day expanding regression of next-period equity returns on current VRP; coefficient, t-statistic, R², and current predicted return implied by the VRP level; when VRP is in the top quartile, the regression-implied expected return is elevated, confirming the Bollerslev-Tauchen-Zhou finding is active in the current market |
| VRP mean reversion speed                | Rolling 252-day estimate of the Ornstein-Uhlenbeck mean-reversion half-life of the VRP series itself; shortening half-life signals faster regime normalization, which is information for volatility sellers about the expected duration of the current premium level                                                                        |
| VRP component attribution               | Total VRP decomposed into the contribution from the GARCH conditional variance (the persistent expected vol component) vs. the contribution from the VIX-GARCH spread (the pure risk aversion component); these have different investment implications                                                                                      |

### Data Map

| Data Required                          | Free Source                   | Frequency |
| -------------------------------------- | ----------------------------- | --------- |
| VIX daily closing level                | FRED (VIXCLS)                 | Daily     |
| VSTOXX, VFTSE, JNIV daily levels       | CBOE public data, Quandl, ECB | Daily     |
| GARCH variance forecast from Feature 2 | Internal output               | Daily     |
| HAR vol forecast from Feature 3        | Internal output               | Daily     |
| Equity index daily returns             | Yahoo Finance, FRED           | Daily     |

---

## FEATURE 6: CROSS-ASSET VOLATILITY CONNECTEDNESS AND SPILLOVER NETWORK

### Why This Exists

Volatility does not stay contained within asset classes. When realized vol in US equities spikes, it transmits to European equities, EM equities, credit spreads, FX vol, and commodities within hours to days. The Diebold-Yilmaz connectedness framework (2009, 2012, 2014) — based on generalized forecast error variance decompositions from a VAR on daily volatility series — is the academic benchmark for measuring these spillovers. It produces a single connectedness index (the fraction of forecast error variance attributable to spillovers rather than own shocks) that summarizes in one number how integrated the global vol system is. A high index means a shock to any single market will rapidly contaminate all others. The rolling Diebold-Yilmaz index rose in the months before the Liberation Day shock of April 2025 and spiked on impact — consistent with connectedness functioning as a leading systemic stress indicator. The decomposition into to-spillovers and from-spillovers per asset identifies which market is currently the transmitter of systemic risk versus which is the receiver — the single most important cross-asset risk insight for any portfolio with multi-asset exposure. MSCI sells this analytics package as a standalone product. Bloomberg does not compute it at all.

### Conceptual Engine

VAR(p) on the N-dimensional vector of daily log-Yang-Zhang vol series:

ln(v*t) = A₁ ln(v*{t-1}) + ... + Aₚ ln(v\_{t-p}) + u_t, u_t ~ (0, Σ)

Lag order p selected by BIC from p ∈ {1,2,3,4,5}. Generalized FEVD (Pesaran-Shin, 1998) is used — ordering-invariant unlike Cholesky:

θ̃ᴴ_ij = θᴴ_ij / Σₖ θᴴ_ik (row-normalized)

| Connectedness Measure      | Formula                              |
| -------------------------- | ------------------------------------ |
| Total connectedness index  | C = [Σ_{i≠j} θ̃ᴴ_ij] / N × 100        |
| From-spillovers to asset i | C*{others→i} = Σ*{j≠i} θ̃ᴴ_ij / N     |
| To-spillovers from asset i | C*{i→others} = Σ*{j≠i} θ̃ᴴ_ji / N     |
| Net spillover of asset i   | NET*i = C*{i→others} − C\_{others→i} |

H (FEVD forecast horizon) set at 10 days. Estimated on rolling 252-day window updated daily.

### Custom Inputs

| Parameter                 | Options                                                                                                                                                                                                                                                                                                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Asset universe            | Any combination of: equity indices (SPX, STOXX50, FTSE, Nikkei, HSI, MSCI EM), FX daily vol proxies (rolling 21-day Yang-Zhang of EURUSD, USDJPY, GBPUSD, DXY), commodity vol proxies (gold, WTI, copper, natural gas), credit spread proxy (CDX IG and HY trailing 21-day vol), crypto vol proxies (BTC, ETH rolling YZ vol); or user-defined custom subset |
| VAR lag order             | BIC-selected (default) or manual override 1–5                                                                                                                                                                                                                                                                                                                |
| FEVD forecast horizon H   | 5, 10, 21 trading days                                                                                                                                                                                                                                                                                                                                       |
| Rolling estimation window | 126-day, 252-day, 504-day                                                                                                                                                                                                                                                                                                                                    |
| Alert threshold           | User-set total connectedness index level above which elevated-spillover alert fires                                                                                                                                                                                                                                                                          |
| Network display layout    | Force-directed graph, adjacency matrix heatmap, or ranked bar chart                                                                                                                                                                                                                                                                                          |

### Outputs

| Output                                | Description                                                                                                                                                                                                                                                                                                         |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Total connectedness index time series | Daily scalar C over rolling history; 10-year percentile on secondary axis; crisis dates annotated — each major systemic episode produces a visible spike, self-validating the monitor; horizontal alert line with all historical breaches highlighted                                                               |
| Net spillover ranking table           | All N assets ranked by current NET_i; positive = transmitter (currently exporting vol shocks to the rest of the system); negative = receiver (currently importing vol from others); updated daily; the largest positive NET asset is the single most important piece of cross-asset risk intelligence in the module |
| Dynamic connectedness network         | N nodes sized by total from-spillovers received; directed edges colored by net flow direction; edge thickness proportional to FEVD magnitude; static snapshot at current date and animated time-lapse across full history                                                                                           |
| Pairwise FEVD heatmap                 | N×N matrix where cell (i,j) shows current C\_{j→i}: fraction of asset i's forecast error variance attributable to shocks from asset j; deep red cells are the dominant transmission channels currently active                                                                                                       |
| Rolling to/from decomposition chart   | For any selected asset: stacked area chart of from-spillovers and to-spillovers over rolling history; a market whose from-spillover is rising while to-spillover is falling is absorbing shocks from the rest of the system — a classic late-cycle stress pattern                                                   |
| Connectedness regime alert            | When total C crosses the top quartile of its history: lists the top 5 pairwise spillovers driving the elevated reading, current NET by asset, and historical average multi-asset portfolio return in the 30 days following a top-quartile C reading                                                                 |

### Data Map

| Data Required                        | Free Source                                 | Frequency |
| ------------------------------------ | ------------------------------------------- | --------- |
| Daily OHLCV for all N assets         | Yahoo Finance, Stooq, FRED                  | Daily     |
| Yang-Zhang vol series from Feature 1 | Internal output                             | Daily     |
| FX daily rates                       | FRED, ECB SDW                               | Daily     |
| Commodity prices (gold, WTI, copper) | FRED (GOLDAMGBD228NLBM, DCOILWTICO), Quandl | Daily     |
| Credit spreads CDX IG/HY             | FRED (BAMLC0A0CM, BAMLH0A0HYM2)             | Daily     |

---

## FEATURE 7: MULTIVARIATE VOLATILITY AND DYNAMIC CONDITIONAL CORRELATION ENGINE

### Why This Exists

Portfolio volatility is not the sum of individual asset volatilities. It depends critically on the correlation structure, and correlations are not constant — they spike dramatically during crises, precisely when you need diversification most. The DCC-GARCH model of Engle (2002, Nobel Prize 2003) is the gold-standard approach for estimating time-varying correlations from daily return data. It models both individual conditional variances (via individual GARCH equations per asset) and the conditional correlation matrix simultaneously, producing a daily N×N conditional covariance matrix that is positive-definite and economically interpretable. The DCC captures the correlation spike during crises that a rolling-window sample covariance misses because the GARCH variance dynamics respond faster than window estimates. The Ledoit-Wolf shrinkage estimator (2004) produces a well-conditioned matrix even when N is large relative to T, eliminating the matrix inversion instability that makes sample covariance unusable for N > 30. Running all three estimation methods — sample, EWMA, Ledoit-Wolf, DCC — simultaneously and comparing the normal-period vs. crisis-period correlation matrices is the feature that makes risk managers understand why diversification fails when they need it most. No commercial platform presents all four simultaneously with the crisis-vs-normal comparison built in.

### Conceptual Engine

| Method                | Mechanism                                                                                                                                                                                        |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Sample covariance     | Standard N×N covariance on estimation window; simple baseline                                                                                                                                    |
| EWMA                  | Exponentially-weighted covariance, σᵢⱼ,t = λ σᵢⱼ,t₋₁ + (1−λ) rᵢ,t rⱼ,t; half-life = ln(0.5)/ln(λ)                                                                                                |
| Ledoit-Wolf shrinkage | σ̂_LW = (1−α) S + α F; F is a structured target matrix; α is data-driven shrinkage intensity minimizing mean squared estimation error                                                             |
| DCC-GARCH             | Stage 1: estimate GARCH(1,1) per asset, standardize residuals; Stage 2: estimate dynamic correlation Qt = (1−a−b)Q̄ + a z*{t-1}z'*{t-1} + b Q\_{t-1}; R_t = diag(Q_t)^{-1/2} Q_t diag(Q_t)^{-1/2} |

### Custom Inputs

| Parameter                       | Options                                                                                                             |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Asset universe                  | Any N assets with daily returns; N up to 50 recommended for DCC stability                                           |
| Estimation methods              | Any subset of 4 or all simultaneously                                                                               |
| EWMA half-life                  | 21, 42, 63, 126 days or user-defined                                                                                |
| DCC parameters a, b             | Estimated by MLE (default) or constrained by user                                                                   |
| Estimation window               | 252, 504, 756, 1260 days or expanding                                                                               |
| Stress period for crisis matrix | Preset: GFC 2008–2009, COVID Mar 2020, Rate shock Oct 2022, Liberation Day Apr–May 2025; or user-defined date range |
| Display mode                    | Correlation matrix (default) or covariance matrix                                                                   |
| Portfolio input                 | Optional: input portfolio weights to get portfolio volatility attribution using the estimated matrix                |

### Outputs

| Output                                   | Description                                                                                                                                                                                                                                |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Correlation matrix heatmap               | N×N matrix colored from deep blue (−1) to deep red (+1); cell annotations for all \|ρ\| > 0.3; four tabs: Sample, EWMA, Ledoit-Wolf, DCC                                                                                                   |
| Normal vs. crisis correlation comparison | Two side-by-side heatmaps (normal-period and user-selected stress period) with a third heatmap showing the difference; deep red difference cells identify which pair correlations spike most during crises — the hidden concentration risk |
| DCC time series chart                    | For any selected asset pair: rolling daily DCC correlation over 10-year history; confirms correlations are regime-dependent, not constant — the direct empirical case against any static correlation model                                 |
| Eigenvalue decomposition                 | Bar chart of eigenvalues in descending order with cumulative variance explained curve; a single dominant eigenvalue means all assets are effectively one correlated risk factor                                                            |
| Condition number history                 | Rolling condition number of the covariance matrix: high values signal matrix instability, meaning optimization using this matrix produces unreliable weights                                                                               |
| Portfolio risk attribution               | For input portfolio weights w: total portfolio variance wᵀΣw, marginal risk contribution per asset MRC_i = w_i (Σw)\_i / σ_p, and pairwise covariance contribution heatmap showing which asset pairs contribute most to portfolio risk     |
| Minimum variance portfolio               | Given the DCC current estimate: analytical minimum variance weights, projected vol, and comparison to equal-weight projected vol                                                                                                           |

### Data Map

| Data Required                            | Free Source                | Frequency |
| ---------------------------------------- | -------------------------- | --------- |
| Daily returns for all N assets           | Yahoo Finance, Stooq, FRED | Daily     |
| Sufficient history (252+ days per asset) | Same                       | Daily     |

---

## FEATURE 8: VOLATILITY STRESS TESTING AND SCENARIO ENGINE

### Why This Exists

Stress testing asks: "Given this scenario, what happens to my volatility model and my portfolio?" Bloomberg charges separately for its scenario engine. The critical advancement beyond what any commercial platform offers is reverse stress testing: instead of "given this scenario, what is my loss?" it solves the inverse: "what scenario would cause my vol model to break and my portfolio to lose X%?" This is now a regulatory expectation under ESMA guidelines and Basel III frameworks and is the first question institutional risk committees ask after a drawdown. The historical analog engine adds a layer that pure parametric stress cannot: for any user-defined scenario defined by macro variables, it finds the closest historical periods by Mahalanobis distance and reports exactly what happened to volatility and portfolio returns in those periods. The contagion model completes the picture: given a shock to one asset's volatility, what is the impulse response across all connected assets at 1, 5, 10, 21-day horizons — estimated directly from the VAR already used in Feature 6.

### Stress Scenario Types

| Type              | Mechanism                                                                                                                                                                                                                                                                                      |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Historical preset | Replay a defined historical window; apply realized daily vol paths of that episode to current portfolio weights                                                                                                                                                                                |
| Historical analog | User defines a scenario via macro variable changes (e.g., equity drawdown −15%, yield spike +100bps, credit spread widening +200bps); system finds the K closest historical 30-day windows by Mahalanobis distance on the macro variable vector and reports average vol and portfolio outcomes |
| Parametric        | User directly inputs vol shocks per asset in annualized bps or standard deviations; system propagates through Feature 7's DCC correlation matrix                                                                                                                                               |
| Reverse stress    | User inputs a portfolio loss threshold L%; system solves for the minimum-probability vol shock vector (constrained by the historical DCC covariance) consistent with that loss                                                                                                                 |

### Custom Inputs

| Parameter                      | Options                                                                                                                                                                                            |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scenario type                  | Historical preset, Historical analog, Parametric, Reverse stress, or all simultaneously                                                                                                            |
| Historical preset library      | GFC Sep–Dec 2008, COVID crash Feb–Mar 2020, COVID recovery Apr–Jun 2020, Taper tantrum Jun 2013, EM crisis Aug 2015, Rate shock Oct 2022, Liberation Day Apr–May 2025, user-saved custom scenarios |
| Analog macro variables         | Any subset of: equity index drawdown, yield curve shift, credit spread change, VIX change, FX move, commodity price change (all from FRED or Yahoo Finance)                                        |
| Number of historical analogs K | 3, 5, 10 closest periods displayed                                                                                                                                                                 |
| Parametric shock unit          | Annualized bps of vol or number of standard deviations of historical vol distribution                                                                                                              |
| Portfolio input                | Weights from any format; or pull from Feature 7 portfolio                                                                                                                                          |
| Reverse stress loss threshold  | % of portfolio value; or absolute dollar amount                                                                                                                                                    |
| Contagion VAR lags             | 1, 5, 21 days                                                                                                                                                                                      |

### Outputs

| Output                              | Description                                                                                                                                                                                                                                                                                                                            |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Vol shock bar chart                 | Each asset's vol change under the scenario in annualized bps; color-coded red (vol spike) or green (vol compression); 5th and 95th historical percentile bands shown around the point estimate                                                                                                                                         |
| Portfolio P&L attribution waterfall | Total portfolio P&L under the scenario decomposed by asset; vol impact (via DCC covariance change) and return impact shown as separate bars; the vol-induced loss vs. the return-induced loss are often very different                                                                                                                 |
| Historical analog comparison        | Closest K historical periods ranked by Mahalanobis distance; for each: the vol path of each asset in the 30 days around the period, portfolio return, and max drawdown; plain-language summary: "The most similar historical episode to your scenario is [date]. At that time, avg vol rose X% and the portfolio lost Y% over 30 days" |
| Reverse stress scenario output      | The vol shock vector of minimum historical probability that exactly produces the stated portfolio loss; expressed as: "This portfolio loses [L]% if [asset A] vol spikes by [X] sigma and [asset B] vol spikes by [Y] sigma simultaneously — a combination observed in [Z]% of rolling 30-day windows historically"                    |
| Contagion impulse response chart    | Given a 1-standard-deviation shock to one asset's vol: impulse response of all other assets' vols at 1, 5, 10, 21-day horizons with 90% bootstrap confidence bands from VAR                                                                                                                                                            |
| Multi-scenario comparison table     | Up to 6 scenarios simultaneously: portfolio P&L, max single-asset vol spike, DCC correlation average, and estimated recovery time side-by-side                                                                                                                                                                                         |
| Stress VaR and CVaR                 | Under each scenario distribution: portfolio 95% and 99% loss estimates from Monte Carlo simulation using the shocked DCC covariance matrix                                                                                                                                                                                             |

### Data Map

| Data Required                          | Free Source                                       | Frequency |
| -------------------------------------- | ------------------------------------------------- | --------- |
| Daily returns for all portfolio assets | Yahoo Finance, Stooq                              | Daily     |
| DCC covariance matrix from Feature 7   | Internal output                                   | Daily     |
| Macro variable history (for analog)    | FRED: equity indices, yields, credit spreads, VIX | Daily     |
| VAR system from Feature 6              | Internal output                                   | Daily     |

---

## FEATURE 9: PORTFOLIO VOLATILITY BUDGET MONITOR AND DYNAMIC RISK TARGETING ENGINE

### Why This Exists

Volatility targeting — sizing positions so that portfolio realized vol tracks a stated target — is the foundation of every systematic risk-managed strategy, from the simplest 1/vol weighting to the most sophisticated overlay used by multi-strategy hedge funds. The 2025 institutional research is unambiguous: risk-targeting using dynamically updated volatility forecasts outperforms fixed-weight strategies by 30–60% on Sharpe ratio in high-volatility regimes. The critical institutional-grade extension beyond basic risk targeting is volatility budget attribution: decomposing the portfolio's current realized vol into the exact contribution of each position in real time, showing which position is responsible for excess vol beyond the target. The innovation over any existing platform is regime-conditional targeting: a PM maintaining a fixed 10% vol target is systematically under-risked in low-vol regimes and over-risked in high-vol regimes. Weighting the target by the Feature 4 regime probability vector produces a smooth, continuously-adapting target that solves both problems simultaneously.

### Conceptual Engine

Portfolio realized variance: σ²_p,t = wᵀ Σ_t w, where Σ_t is the DCC covariance matrix from Feature 7.

Marginal risk contribution per position i: MRC_i,t = w_i (Σ_t w)\_i / σ_p,t

Vol targeting scalar: λ*scale = σ_target / σ̂*{p,t+1}, applied uniformly to all weights; σ̂\_{p,t+1} is the 1-day-ahead portfolio vol forecast from the DCC system.

Regime-conditional target: σ_target,t = Σₖ P(regime k | F_t) × σᵏ_target, where σᵏ_target is user-specified per regime and P(regime k) comes from Feature 4.

### Custom Inputs

| Parameter                   | Options                                                                                               |
| --------------------------- | ----------------------------------------------------------------------------------------------------- |
| Portfolio weights           | Manual entry, CSV upload, or equal-weight default                                                     |
| Covariance estimator        | DCC-GARCH (default), EWMA, Ledoit-Wolf, or sample from Feature 7                                      |
| Vol target level            | Fixed: 5%–30% in 1% steps; or regime-conditional                                                      |
| Regime-conditional targets  | User-sets σᵏ_target per regime (e.g., 8% in low-vol, 10% normal, 14% high-vol)                        |
| Regime probabilities source | Feature 4 output (default)                                                                            |
| Forward vol forecast source | DCC 1-day ahead (default), GARCH from Feature 2, or EWMA                                              |
| Rebalancing trigger         | Daily, weekly, or signal-triggered when portfolio vol deviates from target by more than X% (user-set) |
| Gross exposure constraint   | Maximum gross exposure multiple (e.g., 1.5× for long-only, 3× for long-short)                         |
| Transaction cost input      | Flat bps per trade for rebalancing cost calculation                                                   |

### Outputs

| Output                              | Description                                                                                                                                                                                                                                                                                         |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Portfolio vol dashboard             | Four large-format numerals: current 21-day realized annualized portfolio vol; DCC/GARCH 1-day forward forecast of vol; current regime-conditional vol target; scaling factor λ_scale needed to hit target — the primary operational output; updates daily                                           |
| Vol-to-target gap gauge             | Signed bar: positive = over-target (reduce risk), negative = under-target (add risk); with 7-day and 30-day trend                                                                                                                                                                                   |
| Vol budget attribution waterfall    | Each position: current MRC in annualized bps and as % of total portfolio vol; assigned budget fraction; signed deviation (over-budget or under-budget); sorted from most over-budget to most under-budget — tells the PM exactly which position to cut and which to add to restore budget alignment |
| Scaling factor history              | Daily time series of λ_scale over the full backtested history; periods where λ < 1 (deleveraging required) exactly correspond to high-vol regimes — visual confirmation the system would have reduced risk before crisis drawdowns                                                                  |
| Regime-conditional target evolution | Time series of σ_target,t (regime-weighted) vs. actual portfolio vol; shows how the target adapts ahead of regime transitions from Feature 4                                                                                                                                                        |
| Rebalancing recommendation          | Proposed new weight vector after applying λ_scale and vol budget realignment; associated one-way turnover, estimated transaction cost, and net-of-cost expected improvement in risk-adjusted return                                                                                                 |
| Historical vol-targeting backtest   | Cumulative return, annualized vol, Sharpe ratio, max drawdown, and Calmar ratio of the vol-targeted overlay vs. unscaled equal-weight baseline over full history — the empirical proof of concept for the system on the user's own universe                                                         |

### Data Map

| Data Required                             | Free Source          | Frequency |
| ----------------------------------------- | -------------------- | --------- |
| Daily returns for all portfolio assets    | Yahoo Finance, Stooq | Daily     |
| DCC covariance matrix from Feature 7      | Internal output      | Daily     |
| Regime probability vector from Feature 4  | Internal output      | Daily     |
| GARCH/HAR vol forecasts from Features 2–3 | Internal output      | Daily     |

---

## MODULE INTEGRATION MAP

| Feature                                | Primary Input                     | Primary Dependency                                       |
| -------------------------------------- | --------------------------------- | -------------------------------------------------------- |
| 1. Multi-Estimator Vol Engine          | Daily OHLCV                       | None; foundational                                       |
| 2. GARCH Family Suite                  | Daily returns                     | Feature 1 (vol proxy for evaluation)                     |
| 3. HAR Forecasting Suite               | Feature 1 vol series              | Feature 1 required; Feature 2 optional (GARCH residuals) |
| 4. Regime Detection Engine             | Feature 1 vol series, FRED macro  | Feature 1 required                                       |
| 5. Volatility Risk Premium Monitor     | FRED VIX, Features 2–3            | Features 2 and 3 required for physical expectation       |
| 6. Connectedness and Spillover Network | Feature 1 vol series (all assets) | Feature 1 required across N assets                       |
| 7. Multivariate Vol and DCC            | Daily returns (all assets)        | Standalone; Feature 1 for evaluation                     |
| 8. Stress Testing and Scenario Engine  | Features 6 and 7 outputs          | Features 6 and 7 required                                |
| 9. Portfolio Vol Budget and Targeting  | Features 4 and 7 outputs          | Features 4 and 7 required                                |

---

## MASTER DATA MANIFEST

All features in this module are buildable exclusively from the following freely available daily data sources. No intraday data, no options data, no proprietary data feeds required.

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
| VIX daily closing level                                     | FRED                             | VIXCLS                         | Feature 5           |
| VSTOXX daily level                                          | STOXX / Quandl                   | V2X                            | Feature 5           |
| 2-year US Treasury yield                                    | FRED                             | DGS2                           | Feature 4           |
| 10-year US Treasury yield                                   | FRED                             | DGS10                          | Feature 4           |
| US IG credit spread (BAML index)                            | FRED                             | BAMLC0A0CM                     | Features 4, 6       |
| US HY credit spread (BAML index)                            | FRED                             | BAMLH0A0HYM2                   | Features 4, 6       |
| All computed vol series                                     | Internal pipeline from Feature 1 | —                              | Features 2–9        |

Here is the complete upgrade manifest, organized by feature, written to be handed directly to Claude Code as a specification amendment.

Here is the complete upgrade manifest, organized by feature, written to be handed directly to Claude Code as a specification amendment.

---

## VOLATILITY INTELLIGENCE MODULE — PEAK UPGRADE MANIFEST

---

### FEATURE 1 — MULTI-ESTIMATOR DAILY VOLATILITY ENGINE

**Gap 1: Microstructure noise contamination in small-cap and illiquid assets**

The Parkinson, GK, RS, and YZ estimators all assume the observed high and low are the true intraday extremes. For small-cap equities and illiquid assets, bid-ask bounce inflates the observed high-low range, causing all four range-based estimators to overstate true volatility by 10-40% depending on liquidity. This bias is systematic and directional.

Upgrade: implement the Bandi-Russell (2006) microstructure noise correction. The corrected estimator separates the variance of the true price process from the variance of the noise process using the autocorrelation of high-frequency returns. For daily data, the approximation is:

σ²_BR,t = σ²_PARK,t - 2 × η²_t

where η²*t is estimated as the negative first-order autocovariance of squared daily returns over a trailing 63-day window: η²_t = -min(0, (1/62) × Σ*{s=t-62}^{t-1} r²*s × r²*{s+1}). Add this as a sixth estimator, toggled on by default only when average daily dollar volume is below a user-set liquidity threshold (default: $50M/day).

**Gap 2: Estimator efficiency under fat tails is not tested**

The theoretical relative efficiency values (RE_PARK ≈ 4.0, RE_YZ ≈ 14.0) are derived under Gaussian returns. Under fat-tailed distributions (which all daily equity return series exhibit), these efficiency gains are attenuated. The platform currently displays the Gaussian-theory RE values without flagging this.

Upgrade: compute the empirical RE values alongside the theoretical ones. Empirical RE_E = Var(σ²_CC) / Var(σ²_E) measured directly from the rolling time series of estimator values over the full history. When the empirical RE for any estimator deviates from its theoretical value by more than 30%, display a fat-tail warning flag on that estimator's dial with the tooltip: "Empirical efficiency gain lower than Gaussian theory predicts — return distribution is fat-tailed, reducing the relative advantage of this estimator."

**Gap 3: No test for overnight gap regime**

The YZ estimator's advantage over RS depends on the magnitude of overnight gaps relative to intraday moves. In regimes where gaps are small (e.g., FX markets, 24-hour crypto), the RS estimator dominates YZ because the overnight component adds noise rather than information. The current spec does not detect this dynamically.

Upgrade: compute a daily overnight gap fraction OGF_t = σ²_overnight,t / σ²_YZ,t as a rolling 21-day average. When OGF_t < 0.05 (gaps contribute less than 5% of total variance), the system automatically demotes YZ and promotes RS in the DM tournament ranking, with a tooltip explaining the switch. When OGF_t > 0.30 (gaps dominate), flag YZ as the mandatory default and suppress RS from the tournament leaderboard.

**New addition: Realized range correlation matrix**

Implement the Parkinson cross-product realized correlation estimator for N assets simultaneously. For any asset pair (i,j):

ρ*PARK,ij,t = (1/M) × Σ*{s=t-M+1}^{t} [ln(H_{i,s}/L_{i,s}) × ln(H_{j,s}/L_{j,s})] / (σ_PARK,i,t × σ_PARK,j,t × 4 ln 2)

This produces a range-based realized correlation estimate that is more efficient than the sample correlation from closing returns, for exactly the same reason the Parkinson vol estimator dominates close-to-close vol. Display as an N×N heatmap tab labeled "Range Correlation" sitting alongside the DCC correlation tabs in Feature 7. This is the missing link between Feature 1 and Feature 7 and fills the only genuine gap in the module's coverage.

---

### FEATURE 2 — GARCH FAMILY SUITE

**Gap 1: News impact curve is regime-invariant**

The current NIC holds σ²*{t-1} fixed at the long-run mean σ²*∞ for all observations. This produces a single NIC curve per model. But the NIC shape changes substantially across vol regimes: in a high-vol regime (σ²*{t-1} >> σ²*∞), the GARCH NIC is shifted upward and the asymmetric arm of GJR-GARCH is proportionally steeper. A PM calibrating tail-risk hedges in a high-vol regime is using the wrong NIC if it was computed at the long-run mean.

Upgrade: compute three NICs simultaneously for each active model: (1) σ²*{t-1} = 10th percentile of its historical distribution (low-vol regime NIC), (2) σ²*{t-1} = median (normal NIC, current behavior), (3) σ²\_{t-1} = 90th percentile (high-vol regime NIC). Display all three as a ribbon on the same chart, with the ribbon width representing the vol-regime sensitivity of the model's shock response. Wide ribbon = highly regime-dependent asymmetry. This is not in any commercial platform.

**Gap 2: No test for parameter instability over time**

A GARCH model estimated on 10 years of data assumes the parameters (ω, α, β, γ) are constant. This is empirically false: the persistence parameter α+β has been shown to increase during crisis regimes and decrease during calm regimes. Using a single fixed parameter vector across the full history understates model uncertainty.

Upgrade: implement the Nyblom (1989) parameter stability test for each estimated GARCH model. The test statistic is:

L = T^{-2} × tr[Σ̂^{-1} × Σ_{t=1}^{T} (Σ_{s=1}^{t} ∂ℓ_s/∂θ)(Σ_{s=1}^{t} ∂ℓ_s/∂θ)']

where ∂ℓ_s/∂θ is the score vector at date s. Critical values tabulated in Hansen (1992). If the Nyblom test rejects parameter stability at the 5% level, automatically re-estimate the model on three subsamples (pre-GFC, GFC to COVID, post-COVID) and display the parameter evolution table alongside the full-sample estimates. Flag the winning model in the MCS as "parameters unstable" if it fails the Nyblom test, prompting the user to consider a rolling-window specification.

**Gap 3: APARCH power parameter δ is not benchmarked**

The APARCH model estimates δ freely, but the empirical distribution of δ across assets is informative. δ = 1 implies vol responds to absolute return shocks (Laplace-like). δ = 2 implies GARCH. δ between 1 and 2 (the empirical norm for equities) implies a power law intermediate between the two. The current spec estimates δ and reports it but does not contextualize it.

Upgrade: after estimating APARCH for any asset, plot the estimated δ against a distribution of δ values estimated across the full cross-asset panel (all N assets in the universe). The percentile of this asset's δ within the cross-sectional distribution is the key output: very low δ (below 10th percentile) means the asset's vol responds unusually sharply to small shocks, which is a tail-risk signal. Very high δ means the asset's vol is unusually insensitive to moderate shocks and responds primarily to extremes.

**New addition: Realized GARCH (Hansen, Huang, Shek, 2012)**

The Realized GARCH model augments the standard GARCH variance equation with a measurement equation linking the GARCH conditional variance to the range-based vol estimator from Feature 1:

ln(σ²*t) = ω + β × ln(σ²*{t-1}) + γ × ln(x\_{t-1})

ln(x_t) = ξ + φ × ln(σ²_t) + τ₁ × z_t + τ₂ × (z²_t - 1) + u_t, u_t ~ N(0, σ²_u)

where x_t = σ²_YZ,t is the Yang-Zhang estimator from Feature 1 (the realized measure), z_t = r_t/σ_t is the standardized return, and τ₁, τ₂ capture the leverage effect in the measurement equation. The Realized GARCH absorbs the information content of the full OHLCV path (through x_t) into the GARCH framework, producing a hybrid model that outperforms both standard GARCH and pure HAR in out-of-sample forecasting. Add this as the 6th model in the suite, making the total 24 model-distribution combinations. This is the correct bridge between Feature 1 and Feature 2 and is not available in any commercial volatility platform.

---

### FEATURE 3 — HAR FORECASTING SUITE

**Gap 1: Jump proxy is not the academic benchmark**

The RS/YZ divergence proxy for jumps is a reasonable approximation but the literature standard is bipower variation (Barndorff-Nielsen and Shephard, 2004), which is computable from daily returns:

BV*t = (π/2) × Σ*{s=t-M+1}^{t} |r*s| × |r*{s-1}|

The jump component under BPV is: J_BV,t = max(RV_t - BV_t, 0) where RV_t = Σ r²_s is the realized variance proxy. Add BPV as the primary jump estimator and retain the RS/YZ proxy as a secondary. When the two disagree by more than 20% of total variance, flag a "jump estimator disagreement" warning on the jump proxy time series chart. The disagreement itself carries information: it typically occurs when either the overnight gap or the intraday range is anomalously large relative to the other.

**Gap 2: HAR forecasts are not tested for directional accuracy**

The current accuracy metrics (RMSE, QLIKE, MAE, R²_OOS) measure magnitude accuracy. A PM using HAR forecasts to make regime-conditional position sizing decisions needs directional accuracy: does the HAR correctly predict whether vol will be above or below the current level? A model with good RMSE but poor directional accuracy is useless for trading.

Upgrade: add two directional accuracy metrics to the forecast accuracy table. (1) Hit rate: fraction of OOS periods where sign(v̂*{t+h} - v_t) = sign(v*{t+h} - v_t). (2) Directional Diebold-Mariano: apply the DM test to directional loss L_dir(v̂, v) = I{sign(v̂ - v_t) ≠ sign(v - v_t)} instead of squared loss. A model with DM-superior directional accuracy is the model to use for signal generation, even if its RMSE is not the lowest.

**Gap 3: No combination forecast**

The MCS identifies which models survive but does not combine them. The forecast combination literature (Timmermann, 2006) consistently shows that equally-weighted combinations of MCS survivors outperform any individual model in OOS R², particularly for volatile assets where no single model is stable.

Upgrade: add a "MCS combination forecast" row to the accuracy table. The combination forecast at horizon h: v̂*combo,t+h = (1/|M\*|) × Σ*{E ∈ M*} v̂\_{E,t+h} where M* is the 90% MCS. Weight by inverse QLIKE loss as an alternative: w*E = (QLIKE_E)^{-1} / Σ*{E'} (QLIKE\_{E'})^{-1}. Test whether the combination outperforms the individual MCS winner via DM. Empirically, it will in approximately 70% of assets and horizons.

**New addition: HAR-X with macro factors**

Extend the HAR framework with macroeconomic predictors from FRED that have been shown in the literature to contain incremental volatility forecasting information beyond the HAR regressors:

v\_{t+h} = β₀ + β_d × v_t^(d) + β_w × v_t^(w) + β_m × v_t^(m) + β_VRP × VRP_t + β_slope × slope_t + β_credit × spread_t + ε_t

where VRP_t is the volatility risk premium from Feature 5, slope_t = DGS10_t - DGS2_t is the yield curve slope from FRED, and spread_t = BAMLH0A0HYM2_t is the HY credit spread from FRED. All three macro variables are available daily from FRED at zero cost. Add this as the 7th HAR variant (HAR-X) and include it in the MCS competition. The VRP regressor in particular has been shown by Bekaert and Hoerova (2014, Journal of Financial Economics) to have incremental forecasting power over the standard HAR at the 1-month horizon, with R²_OOS improvement of 1-3%.

---

### FEATURE 4 — REGIME DETECTION ENGINE

**Gap 1: Emission distributions are stationary across the full sample**

The HMM estimates fixed Gaussian emission parameters (μ_k, σ²_k) across the full estimation window. But vol regime characteristics drift secularly: the "low-vol" regime in 2017 (VIX ≈ 10) looks nothing like the "low-vol" regime in 2004 (VIX ≈ 14). Using a fixed emission distribution conflates structurally different market environments.

Upgrade: implement exponentially weighted EM (EW-EM) for the HMM. In the M-step, replace the standard sufficient statistics with exponentially weighted versions:

μ̂_k = Σ_t (δ^{T-t} × γ_t(k) × o_t) / Σ_t (δ^{T-t} × γ_t(k))

σ̂²_k = Σ_t (δ^{T-t} × γ_t(k) × (o_t - μ̂_k)²) / Σ_t (δ^{T-t} × γ_t(k))

where δ ∈ (0.97, 0.9999) is a forgetting factor (user-set, default δ = 0.995, half-life ≈ 138 days). This makes the HMM emission parameters adaptive: recent observations of what "low-vol" looks like receive more weight than observations from 10 years ago. Display the time series of μ̂_k(t) and σ̂²_k(t) over history to show how regime characteristics have drifted.

**Gap 2: The SJM feature vector does not include credit or macro signals**

The current SJM feature vector is entirely constructed from the asset's own vol series (5-day, 21-day, 63-day YZ vol) plus the jump ratio and autocorrelation. It contains no cross-asset or macro information. Vol regimes are frequently triggered by macro events (rate shocks, credit spread widening) before the vol signal itself appears in the equity time series.

Upgrade: add three macro features to the SJM feature vector: (1) 21-day change in the HY credit spread (BAMLH0A0HYM2 from FRED), (2) 21-day change in the 2s10s yield curve slope (DGS10 - DGS2 from FRED), (3) VIX level normalized by its own 252-day z-score. The expanded feature vector is f_t ∈ ℝ^9 (6 existing + 3 macro). Standardize all 9 features before clustering. This allows the SJM to detect regime transitions using leading macro indicators rather than lagging vol signals, which is the core advantage over purely vol-based regime detection.

**Gap 3: No out-of-sample regime prediction**

The current system identifies regimes retrospectively using the full smoothed posterior from the HMM (forward-backward algorithm), which uses future data. For live trading, only the filtered posterior (forward algorithm only) is available. The current spec does not distinguish between the two or report the performance gap.

Upgrade: compute both the smoothed posterior (for historical analysis and self-validation) and the filtered posterior (for live signal generation) and display them as separate outputs. Measure the smoothed-to-filtered accuracy gap: the Brier score difference between the two tells the user how much forecasting accuracy is lost by not having future information. When the gap is large, the regime model is primarily backward-looking and its live signal quality will be degraded.

**New addition: Volatility regime duration model**

After identifying the regime sequence via the composite probability vector, fit a parametric duration model (Weibull or log-logistic) to the empirical distribution of regime durations:

f(t | λ, k) = (k/λ) × (t/λ)^{k-1} × exp(-(t/λ)^k) (Weibull)

where t is the observed regime duration in days, λ is the scale parameter, and k is the shape parameter. k < 1: hazard rate decreasing (regimes more likely to end when they are new than when they are old — consistent with crisis regimes). k > 1: hazard rate increasing (the longer you stay in a regime, the more likely it is to end — consistent with low-vol regimes). Estimate separately per regime state. Display the fitted duration distribution and the current regime's survival probability: P(regime lasts at least d more days | already lasted t days) = exp(-((t+d)/λ)^k + (t/λ)^k). This is the answer to the question every PM asks: "how long is this regime likely to last?"

---

### FEATURE 5 — VOLATILITY RISK PREMIUM MONITOR

**Gap 1: Overlapping return regression uses wrong standard errors**

The BTZ return predictability regression uses overlapping H-day returns as the dependent variable, which creates MA(H-1) serial correlation in the residuals. Newey-West with bandwidth H is the standard fix but is known to produce standard errors that are too small in finite samples, leading to over-rejection of the null of no predictability. This is documented in Boudoukh, Richardson, and Whitelaw (2008).

Upgrade: replace Newey-West with Hodrick (1992) standard errors for all overlapping return regressions. The Hodrick (1992) variance estimator for the OLS slope coefficient b̂ is:

Var*Hodrick(b̂) = (1/T²) × (X'X)^{-1} × (Σ_t x_t × (Σ*{s=t}^{t+H-1} û_s)²) × (X'X)^{-1}

where û*s = R*{equity,s} - â - b̂ × VRP*t is the residual from the non-overlapping daily regression and the sum Σ*{s=t}^{t+H-1} û_s accumulates the daily residuals over the H-day window. This is analytically correct for overlapping regressions and produces uniformly larger (more conservative) standard errors than Newey-West. The t-statistic on b̂ under Hodrick SE is the defensible one to report.

**Gap 2: No decomposition of VRP by market state**

The average VRP conceals important conditioning information. The BTZ return predictability finding is strongest when VRP is elevated conditionally on the market being in a low-vol regime (the "fear premium" state), and weakest when VRP is elevated because realized vol has spiked (the "realized vol catching up" state). The two states have opposite investment implications for variance sellers.

Upgrade: decompose the VRP time series into two conditional subsamples using the Feature 4 regime probabilities: (1) high VRP in low-vol regime (p_composite[low-vol] > 0.6 and VRP > 70th percentile), (2) high VRP in high-vol regime (p_composite[high-vol] > 0.6 and VRP > 70th percentile). Run the BTZ regression separately on each subsample. The regime-conditional BTZ coefficients and R² values will differ substantially and carry different investment signals.

**New addition: Term structure of the variance risk premium**

The current spec computes the VRP at a single 30-day horizon (driven by the VIX definition). The variance risk premium has a term structure: the 1-month VRP, the 3-month VRP (using VXMT if available, or the 3-month HAR forecast as the physical expectation), and the 6-month VRP contain different information about the persistence and mean-reversion speed of risk aversion. Add a VRP term structure chart with three maturities (30 days, 90 days, 180 days) computed simultaneously using HAR forecasts at the corresponding horizons as the physical expectation for the longer maturities. The slope of the VRP term structure (upward-sloping vs. inverted) is a leading indicator of whether the current risk aversion spike is expected to persist (inverted VRP term structure) or resolve quickly (upward-sloping).

---

### FEATURE 6 — CONNECTEDNESS AND SPILLOVER NETWORK

**Gap 1: Fixed FEVD horizon misses frequency-domain structure**

The current spec uses H = 10 days as the fixed FEVD horizon. Barunik and Krehlik (2018, Journal of Financial Econometrics) demonstrate that short-run connectedness (H = 1 to 5 days) and long-run connectedness (H = 50 to 252 days) have fundamentally different economic interpretations. Short-run connectedness captures panic contagion driven by market microstructure and sentiment. Long-run connectedness captures structural financial integration driven by common macroeconomic exposures. Using only H = 10 conflates the two.

Upgrade: implement the Barunik-Krehlik frequency-domain connectedness decomposition. The total connectedness is decomposed into frequency bands:

C*[ω1,ω2] = [Σ*{i≠j} θ̃^{[ω1,ω2]}\_{ij}] / N × 100

where θ̃^{[ω1,ω2]}\_{ij} is the generalized FEVD contribution within the frequency band [ω1, ω2], computed via the spectral representation of the VAR:

θ^{[ω1,ω2]}_{ij} = (σ_{jj})^{-1} × ∫*{ω1}^{ω2} (e_i' Ψ(e^{-iω}) Σ_u e_j)² dω / ∫*{-π}^{π} (e_i' Ψ(e^{-iω}) Σ_u Ψ(e^{iω})' e_i) dω

where Ψ(e^{-iω}) = Σ\_{h=0}^{∞} Φ_h e^{-iωh} is the frequency response function of the VAR. Define three bands: short-run [1, 5 days], medium-run [5, 21 days], long-run [21, 252 days]. Display the total connectedness index decomposed into three stacked components. A rising short-run band during a stress episode signals panic contagion. A rising long-run band signals structural regime change in financial integration.

**Gap 2: Network is static within the rolling window**

The current rolling DY network updates daily but the network displayed at any date is a single cross-sectional snapshot computed on a 252-day window. This means a shock that happened 6 months ago still influences today's network. The most recent observations should have higher weight.

Upgrade: implement an exponentially weighted VAR within the rolling window. At each date T, the VAR coefficients are estimated using exponentially weighted OLS:

[c, A_1, ..., A_p] = argmin Σ*{t=T-W+1}^{T} δ^{T-t} × ‖Y_t - c - A_1 Y*{t-1} - ... - A*p Y*{t-p}‖²

where δ = 0.99 (user-adjustable). This gives recent observations approximately 2.7× the weight of observations from 100 days ago, making the network more responsive to structural breaks while retaining the statistical stability of a 252-day window.

**New addition: Connectedness-at-Risk**

Compute the 95th percentile of the historical connectedness index distribution, conditioned on the current macro state (VIX level, credit spread, yield curve slope). This is the connectedness analog of Value-at-Risk: the level of systemic integration that would be exceeded in only 5% of historically similar macro environments.

CoR*t = VaR*{95%}(C\_{t+21} | macro_t)

Estimated via quantile regression of C\_{t+21} on (VIX_t, spread_t, slope_t) over the full history. Display as a forward-looking systemic risk gauge: when current C_t is already near CoR_t, the systemic risk headroom is exhausted and the next macro shock is likely to push connectedness to historically extreme levels.

---

### FEATURE 7 — MULTIVARIATE VOLATILITY AND DCC ENGINE

**Gap 1: Single (a, b) parameter pair forces uniform correlation dynamics**

The standard DCC(1,1) model uses a single pair of parameters (a, b) governing the mean-reversion and persistence of all N(N-1)/2 pairwise correlations simultaneously. This forces the equity-bond correlation and the equity-commodity correlation to have the same persistence, which is empirically false: equity-bond correlations have much longer memory (reflecting macro regime persistence) than equity-commodity correlations (reflecting supply-demand cycles).

Upgrade: implement DCC-MIDAS (Colacito, Engle, Ghysels, 2011). The DCC-MIDAS separates the short-run correlation dynamics (daily DCC) from the long-run correlation component (driven by macroeconomic fundamentals at monthly frequency):

Q*t = (1-a-b) × R̄_t^{LR} + a × ẑ*{t-1}ẑ'_{t-1} + b × Q_{t-1}

where R̄_t^{LR} is the long-run correlation component estimated via a MIDAS regression on monthly realized correlations:

ρ̄*{ij,t}^{LR} = μ_ij + φ_ij × Σ*{k=1}^{K} β*k(θ_1, θ_2) × RC*{ij,t-k}

where RC\_{ij,t-k} is the realized correlation of the (i,j) pair in month t-k and β_k(θ_1, θ_2) are Beta polynomial MIDAS weights. The long-run component is smooth (monthly updates) while the short-run DCC captures daily fluctuations around it. This decomposition is implementable using only daily returns (compute monthly RC from daily returns) and is the correct model for any platform targeting investors who need to distinguish tactical correlation dynamics from strategic portfolio construction.

**Gap 2: Crisis period definition is deterministic**

The current crisis period is defined by VIX > 30 AND top-decile vol. This is a hard rule that treats VIX = 29.9 as non-crisis and VIX = 30.1 as crisis, which is arbitrary. The regime probabilities from Feature 4 already solve this problem.

Upgrade: replace the hard VIX threshold crisis definition with the Feature 4 composite regime probabilities. The probability-weighted crisis correlation matrix is:

Ω_crisis = Σ_t p_composite(t)[high-vol] × ε_t ε_t' / Σ_t p_composite(t)[high-vol]

This is a soft, probability-weighted crisis covariance matrix that weights each day's contribution by how likely the system was in a stress regime on that day. It is more statistically efficient (uses all observations with appropriate weights rather than discarding observations arbitrarily) and is internally consistent with the regime framework throughout the module.

**New addition: Minimum torsion bespoke correlation**

Implement the Meucci (2013) minimum torsion orthogonalization, which identifies the rotation of the N-asset return space that is closest to the original asset space while producing uncorrelated factors. Unlike PCA, which produces factors that are linear combinations of all assets and are not interpretable, minimum torsion produces a unique set of uncorrelated "bespoke" factors where each factor loads primarily on one asset:

T\* = argmin\_{T: TT'=Σ} ‖T - I‖²_F subject to T'Σ^{-1}T = I

The minimum torsion matrix T\* decomposes the portfolio's risk into N orthogonal uncorrelated risk sources, each interpretable as a "diversified" version of a specific asset. The risk contribution of the k-th torsion factor is then uncorrelated with all others, making the risk budget truly additive. Display the minimum torsion factor loadings and risk contributions alongside the standard MRC decomposition. This is the theoretically correct risk budgeting framework and is available in no commercial platform.

---

### FEATURE 8 — STRESS TESTING AND SCENARIO ENGINE

**Gap 1: Reverse stress test assumes linear return-vol relationship**

The current reverse stress test translates vol shocks into return shocks via the leverage effect coefficients β_lev from Feature 3. This is a linear approximation that breaks down for large shocks. The leverage effect (negative return predicts higher vol) is empirically nonlinear: it is strongest for extreme negative returns and much weaker for moderate negative returns.

Upgrade: fit a bivariate tail-dependent copula to the joint distribution of (r_t, Δσ_t) pairs over the full history. Use the Clayton copula for the lower tail (negative returns, positive vol spikes):

C_Clayton(u, v | θ) = (u^{-θ} + v^{-θ} - 1)^{-1/θ}, θ > 0

where u = F*r(r_t) and v = F*{Δσ}(Δσ_t) are the probability integral transforms of the return and vol change series. Estimate θ by maximum likelihood over the lower 20% of the bivariate distribution (tail region). The Clayton copula has lower tail dependence λ_L = 2^{-1/θ} > 0, meaning extreme negative returns and extreme vol spikes are more likely to co-occur than a Gaussian copula would predict.

For the reverse stress test, use the Clayton copula to simulate the conditional return distribution given an extreme vol shock: P(r_t < r\* | Δσ_t > shock) computed from the copula CDF. This gives a nonlinear, tail-accurate mapping from vol shock to portfolio return impact.

**Gap 2: Historical analog matching uses Euclidean macro space**

The Mahalanobis distance for analog matching normalizes each macro variable by its own variance, which is correct. But it does not account for the fact that some macro variable combinations are inherently more informative about future vol than others. A scenario with VIX spike + credit widening is more informative about stress than VIX spike + yield flattening, even if the Mahalanobis distances are equal.

Upgrade: replace the sample covariance matrix Σ_x in the Mahalanobis distance with a precision matrix estimated by LASSO-regularized precision (graphical LASSO):

Σ*x^{-1} ≈ Ω_GLASSO = argmin*Ω {tr(S × Ω) - log|Ω| + ρ × ‖Ω‖\_1}

where S is the sample covariance of macro change vectors and ρ is the regularization parameter chosen by BIC. The graphical LASSO shrinks small partial correlations among macro variables to zero, producing a sparse precision matrix that emphasizes the macro variable pairs with the strongest conditional relationships. Analogs computed under this precision matrix will weight the informationally relevant macro dimensions more heavily.

**New addition: Adversarial scenario generator**

Beyond user-defined scenarios, implement an adversarial scenario generator that identifies the historically plausible scenario most damaging to the specific portfolio. The adversarial scenario is:

x*adversarial\* = argmax*{x: d²_M(x) < c²} w' E[r | x] × (-1)

subject to the scenario being historically plausible (Mahalanobis distance from the current macro state less than c standard deviations, default c = 2). This is a constrained optimization: find the worst-case historically-plausible scenario for this specific portfolio. Solve via projected gradient ascent on the loss surface. The output is a scenario the user did not think to test: the blind spot in their stress testing framework. Display it as: "The most damaging historically plausible scenario for your portfolio is [description]. This scenario would produce a portfolio loss of [L]% and has occurred in [N] historical windows."

---

### FEATURE 9 — PORTFOLIO VOLATILITY BUDGET MONITOR

**Gap 1: Vol-targeting scaling is applied uniformly across all positions**

The current λ_scale is applied uniformly: w_i^{scaled} = λ_scale × w_i for all i. This is the correct approach when the portfolio is already at its vol budget target in terms of risk allocation. But when some positions are significantly over-budget and others are under-budget, uniform scaling does not restore budget alignment — it just scales the entire budget imbalance up or down.

Upgrade: implement a two-step rebalancing. Step 1: apply the uniform λ_scale to bring total portfolio vol to the target. Step 2: apply a within-portfolio budget-alignment rebalance that reallocates risk from over-budget positions to under-budget positions while keeping total portfolio vol at the target. The Step 2 rebalance solves:

min\_{Δw} Δw' Ω Δw subject to (w + Δw)' Ω (w + Δw) = σ²_target and Σ_i Δw_i = 0

This is a quadratic program with two equality constraints, solvable analytically via KKT. The two-step rebalancing simultaneously hits the vol target and realigns the risk budget, which is strictly superior to uniform scaling.

**Gap 2: Transaction cost model ignores market impact**

The current flat bps model (TC = c_explicit × TO) is appropriate for small portfolios but underestimates costs for institutional-scale portfolios where position sizes move market prices. This matters because the vol-targeting system generates the most rebalancing during high-vol periods, which are precisely the periods when market impact is highest.

Upgrade: implement the Almgren-Chriss (2001) market impact cost model as an option alongside the flat bps model. The Almgren-Chriss temporary impact cost for trading a fraction θ_i of asset i's average daily volume in a single day:

MI_i = γ_i × σ_i × |Δw_i × AUM| / (ADV_i × P_i)

where γ_i ≈ 0.1 (market impact coefficient), σ_i is the asset's daily vol, ADV_i is the average daily dollar volume (from Yahoo Finance), and P_i is the current price. Total transaction cost: TC_total = Σ_i (c_explicit + MI_i) × |Δw_i|. This gives a cost estimate that increases nonlinearly with position size and is sensitive to current vol, matching the empirical behavior of institutional transaction costs.

**New addition: Kelly-criterion vol targeting**

The standard vol-targeting framework targets a fixed annualized vol (e.g., 10%). The Kelly criterion provides a theoretically optimal vol target that maximizes long-run expected log wealth. For a portfolio with expected return μ_p and volatility σ_p, the Kelly-optimal leverage is:

f\* = μ_p / σ²_p

which implies a Kelly-optimal portfolio volatility of σ*\_Kelly = μ_p / (f* × σ_p) = σ²_p / σ_p = σ_p, a tautology unless μ_p is estimated independently. Estimate μ_p via the regime-conditional expected return from the BTZ regression in Feature 5 (the VRP-implied expected equity return) and from the HAR forecast of future vol (via the empirical return-vol tradeoff estimated from the full history). The Kelly-optimal vol target at each date:

σ\*\_Kelly,t = μ̂_p,t / σ̂_p,t

where μ̂_p,t is the current BTZ-implied expected portfolio return and σ̂_p,t is the DCC-forecast portfolio vol. Display this as a fourth option in the vol target selector (alongside fixed target and regime-conditional target). When the Kelly target is significantly below the user's fixed target, the system is identifying that the current risk-return tradeoff does not justify the stated risk budget.

---

### CROSS-MODULE ADDITIONS

**Addition 1: Volatility surface analytics (no options data)**

Construct a synthetic term structure of realized vol across multiple horizons (5, 10, 21, 42, 63, 126, 252 days) using the HAR model from Feature 3 and the GARCH term structure from Feature 2. Plot this as a "synthetic volatility surface" with horizon on one axis and moneyness-proxy (historical percentile of the return distribution) on the other. The moneyness dimension is constructed by evaluating the GARCH conditional density at different quantiles. This gives a daily-updated synthetic vol surface from daily OHLCV alone. It is not a true options-implied surface but it is the closest achievable without options data and it captures regime-conditional skew information via the asymmetric GARCH models.

**Addition 2: Global volatility regime synchronization index**

Compute the fraction of the N assets in the cross-asset panel that are simultaneously in their high-vol regime (p_composite[high-vol] > 0.5) at each date:

SYNC_t = (1/N) × Σ_i I{p_composite,i(t)[high-vol] > 0.5}

SYNC_t → 1: all assets are in high-vol regimes simultaneously — a global systemic stress event. SYNC_t → 0: vol is idiosyncratic — asset-specific shocks rather than macro contagion. Display SYNC_t as a time series alongside the total connectedness index from Feature 6. The two series should co-move during crisis episodes (both spike simultaneously) but diverge during idiosyncratic stress (connectedness can be high while SYNC is low, if the system is integrated but not simultaneously stressed). This divergence pattern is itself a leading indicator of the type of crisis: contagion vs. idiosyncratic.

**Addition 3: Volatility-adjusted momentum signal**

Construct a vol-adjusted momentum signal that rescales price momentum by the regime-conditional expected volatility. Standard momentum signals are contaminated by high-vol regimes where price moves are large but unpredictable. Vol-adjusted momentum:

MOM_adj,i,t = MOM_raw,i,t / σ_YZ,i,t

where MOM*raw,i,t = (P*{i,t} / P\_{i,t-252}) - 1 is the 12-month price return. Cross-sectional rank MOM_adj,i,t across the N-asset panel. The top-quintile ranked assets by vol-adjusted momentum have empirically higher Sharpe ratios than raw momentum in the literature (Daniel and Moskowitz, 2016). Display as a daily-updated ranked panel within Feature 1's cross-asset panel mode.

---

### REVISED MODULE INTEGRATION MAP

| Feature      | Key Upgrades Added                                                                                       | New Dependencies                        |
| ------------ | -------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| 1            | Bandi-Russell estimator, empirical RE, OGF detector, range correlation matrix                            | None added                              |
| 2            | Regime-conditional NIC, Nyblom stability test, APARCH cross-asset δ distribution, Realized GARCH         | Feature 1 YZ series (existing)          |
| 3            | Bipower variation jump estimator, directional DM test, MCS combination forecast, HAR-X with macro        | Feature 5 VRP (new dependency)          |
| 4            | EW-EM adaptive HMM, macro-augmented SJM feature vector, filtered vs. smoothed comparison, duration model | FRED macro (existing)                   |
| 5            | Hodrick SE, regime-conditional BTZ decomposition, VRP term structure                                     | Feature 4 regime probs (new dependency) |
| 6            | Barunik-Krehlik frequency decomposition, EW-VAR, Connectedness-at-Risk                                   | FRED macro for CoR (new)                |
| 7            | DCC-MIDAS, probability-weighted crisis correlation, minimum torsion bespoke correlation                  | Feature 4 regime probs (new dependency) |
| 8            | Clayton copula reverse stress, graphical LASSO analog matching, adversarial scenario generator           | Feature 5 copula (new)                  |
| 9            | Two-step rebalancing, Almgren-Chriss market impact, Kelly-criterion vol targeting                        | Feature 5 BTZ return (new dependency)   |
| Cross-module | Synthetic vol surface, SYNC index, vol-adjusted momentum                                                 | All features                            |

---

This is the complete upgrade manifest. Every item has a specific mathematical formulation, a specific academic citation where applicable, and a concrete implementation path using free data sources. Hand this document to Claude Code alongside the original spec and instruct it to treat this as the binding amendment.

Here is the fully merged specification, feature by feature. For each feature I show the upgraded **Custom Inputs** table and **Outputs** table, plus any new steps added inline. Everything from Document 3 is absorbed into the Document 2 structure.

---

# QUANT360 — VOLATILITY INTELLIGENCE MODULE

## Complete Upgraded Specification — All 9 Features

---

## FEATURE 1 — MULTI-ESTIMATOR DAILY VOLATILITY ENGINE

### Steps 1–10 remain as Document 2. The following are added:

**New Step 11 — Bandi-Russell microstructure noise correction (6th estimator)**

For illiquid assets, bid-ask bounce inflates the observed high-low range, causing all four range-based estimators to overstate true vol by 10–40%. The corrected estimator:

σ²_BR,t = σ²_PARK,t − 2 × η²_t

where η²*t = −min(0, (1/62) × Σ*{s=t−62}^{t−1} r²*s × r²*{s+1}) is the negative first-order autocovariance of squared daily returns over a trailing 63-day window. This is toggled on by default only when average daily dollar volume is below a user-set liquidity threshold (default: $50M/day).

**New Step 12 — Overnight gap fraction detector**

OGF_t = σ²_overnight,t / σ²_YZ,t as a rolling 21-day average. When OGF_t < 0.05: system automatically demotes YZ and promotes RS in the DM tournament ranking. When OGF_t > 0.30: YZ is flagged as the mandatory default and RS is suppressed from the tournament leaderboard.

**New Step 13 — Empirical relative efficiency**

Empirical RE_E = Var(σ²_CC) / Var(σ²_E) measured directly from the rolling time series over full history. When empirical RE deviates from theoretical RE by more than 30%, display a fat-tail warning flag on that estimator's dial: "Empirical efficiency gain lower than Gaussian theory predicts — return distribution is fat-tailed, reducing the relative advantage of this estimator."

**New Step 14 — Range-based realized correlation matrix**

For any asset pair (i,j):

ρ*PARK,ij,t = (1/M) × Σ*{s=t−M+1}^{t} [ln(H_{i,s}/L_{i,s}) × ln(H_{j,s}/L_{j,s})] / (σ_PARK,i,t × σ_PARK,j,t × 4 ln 2)

This produces a range-based realized correlation matrix more efficient than sample correlation from closing returns.

---

### Custom Inputs

| Parameter                            | Options                                                                                                 |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| Asset                                | Any equity, equity index, FX pair, commodity; single asset or full cross-asset panel                    |
| Active estimators                    | Any subset of 6 (5 original + Bandi-Russell); default is all simultaneously                             |
| Rolling window                       | 10, 21, 42, 63, 126, 252 days                                                                           |
| Annualization convention             | 252-day (default), 365-day, custom                                                                      |
| Overnight gap treatment (Yang-Zhang) | Include or exclude from overnight variance component                                                    |
| Estimator efficiency benchmark       | Which estimator serves as the reference MSE baseline; default is close-to-close                         |
| Cross-asset panel mode               | On/Off; computes all 6 estimators across N assets simultaneously                                        |
| Microstructure noise correction      | On/Off (Bandi-Russell 6th estimator); auto-activates when avg daily dollar volume < liquidity threshold |
| Liquidity threshold for BR estimator | Dollar volume threshold in $M/day; default $50M/day                                                     |
| OGF auto-routing                     | On/Off; automatically re-ranks estimators when overnight gap fraction exceeds thresholds                |

---

### Outputs

| Output                                 | Description                                                                                                                                                                                                                                                                            |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Five/six-estimator comparison chart    | All active estimators plotted simultaneously; shaded band shows spread between highest and lowest at each date                                                                                                                                                                         |
| Estimator efficiency table             | For each estimator: theoretical RE vs CC (analytical), empirical RE vs CC (measured from history), DM tournament win/loss record, current annualized vol. Fat-tail warning flag when empirical RE deviates >30% from theoretical. Color: green ≥3× efficiency, amber 1.5–3×, red <1.5× |
| Diebold-Mariano forecasting tournament | DM statistic and p-value under QLIKE loss for every estimator pair; Bonferroni-corrected at 0.005; winning estimator per asset highlighted; updated on rolling 252-day OOS window                                                                                                      |
| Estimator agreement index              | Daily scalar Agree_t measuring average pairwise correlation of estimator time series over trailing 21 days; alert when Agree_t < 0.50 with tooltip identifying the lowest-correlated pair                                                                                              |
| OGF indicator                          | Rolling 21-day overnight gap fraction time series; threshold bands at 0.05 and 0.30; auto-routing status displayed when thresholds are breached                                                                                                                                        |
| Annualized vol panel                   | Current annualized vol from each estimator as a percentile of the trailing 252-day, 5-year, and full-history distributions; five/six side-by-side dials                                                                                                                                |
| Range correlation matrix               | N×N heatmap tab labeled "Range Correlation" showing Parkinson cross-product realized correlations; sits alongside DCC correlation tabs in Feature 7                                                                                                                                    |
| Cross-asset ranked panel               | When panel mode is active: N-asset table ranked by current Yang-Zhang vol, with all estimator readings and 10-year percentile per asset                                                                                                                                                |

---

## FEATURE 2 — GARCH FAMILY SUITE WITH ASYMMETRY, LONG MEMORY, AND DENSITY FORECASTING

### Steps 1–13 remain as Document 2. The following are added:

**New Step 14 — Realized GARCH (6th model)**

The Realized GARCH model (Hansen, Huang, Shek, 2012) augments the GARCH variance equation with a measurement equation linking conditional variance to the Yang-Zhang estimator from Feature 1:

ln(σ²*t) = ω + β × ln(σ²*{t-1}) + γ × ln(x\_{t-1})

ln(x_t) = ξ + φ × ln(σ²_t) + τ₁ × z_t + τ₂ × (z²_t − 1) + u_t, u_t ~ N(0, σ²_u)

where x_t = σ²_YZ,t is the Yang-Zhang estimator from Feature 1, z_t = r_t/σ_t is the standardized return, and τ₁, τ₂ capture the leverage effect in the measurement equation. This makes total model-distribution combinations 24 (6 models × 4 distributions).

**New Step 15 — Regime-conditional news impact curves**

Three NICs computed simultaneously for each active model:

- NIC*low: σ²*{t-1} = 10th percentile of its historical distribution
- NIC*normal: σ²*{t-1} = median (current behavior)
- NIC*high: σ²*{t-1} = 90th percentile

All three displayed as a ribbon on the same chart. Wide ribbon = highly regime-dependent asymmetry.

**New Step 16 — Nyblom parameter stability test**

For each estimated GARCH model, the Nyblom (1989) statistic:

L = T^{-2} × tr[Σ̂^{-1} × Σ_{t=1}^{T} (Σ_{s=1}^{t} ∂ℓ_s/∂θ)(Σ_{s=1}^{t} ∂ℓ_s/∂θ)']

Critical values from Hansen (1992). If stability is rejected at the 5% level, the model is automatically re-estimated on three subsamples (pre-GFC, GFC-to-COVID, post-COVID) and the parameter evolution table is shown. The winning MCS model is flagged "parameters unstable" if it fails the test.

**New Step 17 — APARCH power parameter cross-sectional benchmarking**

After estimating APARCH for any asset, the estimated δ is plotted against the cross-sectional distribution of δ across the full N-asset panel. Very low δ (below 10th percentile): vol responds unusually sharply to small shocks — a tail-risk signal. Very high δ: vol responds primarily to extremes.

---

### Custom Inputs

| Parameter                       | Options                                                                                                                 |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Asset                           | Any asset with daily price history                                                                                      |
| Return frequency                | Daily (default) or weekly                                                                                               |
| Estimation window               | Rolling 252-day, 504-day, 756-day, or expanding from inception                                                          |
| Active models                   | Any subset of 6 (GARCH, EGARCH, GJR-GARCH, APARCH, FIGARCH, Realized GARCH); default all                                |
| Conditional distributions       | Any subset of 4 (Gaussian, Student-t, GED, Hansen skewed-t), or all 24 combinations simultaneously with MCS competition |
| FIGARCH fractional parameter d  | Estimated by MLE (default) or user-fixed value in (0,1)                                                                 |
| APARCH power parameter δ        | Estimated (default), or constrained to 1 (TARCH), 2 (GARCH), or user-defined                                            |
| MCS confidence level            | 75%, 90%, 95%                                                                                                           |
| Forecast horizons               | 1, 5, 10, 21, 42, 63, 126, 252 trading days via simulation                                                              |
| VaR coverage level              | 95%, 99%, 99.5% for density evaluation                                                                                  |
| Structural break date           | Optional: re-estimate separately on pre/post break subsamples                                                           |
| Regime-conditional NIC          | On/Off; when on, displays three NIC ribbons at 10th, 50th, 90th percentile of σ²\_{t-1}                                 |
| Nyblom stability test           | On/Off; when on, auto-re-estimates on three subsamples if stability rejected                                            |
| APARCH cross-asset benchmarking | On/Off; requires cross-asset panel mode active                                                                          |

---

### Outputs

| Output                                  | Description                                                                                                                                                 |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model comparison scoreboard             | 24 rows (6 models × 4 distributions); columns: log-likelihood, AIC, BIC, RMSE, QLIKE, MCS membership at 90% confidence; winning model bold green            |
| Diebold-Mariano pairwise table          | DM statistic and p-value for all model pairs under QLIKE loss; N×N heatmap                                                                                  |
| News impact curve — regime ribbon       | For each active model: three NIC curves at the 10th, 50th, and 90th percentile of σ²\_{t-1}; ribbon width shows regime sensitivity of shock response        |
| Parameter stability panel               | Nyblom test statistic and p-value per model; if rejected: three-subsample parameter table showing how ω, α, β, γ have drifted across market eras            |
| APARCH δ cross-sectional chart          | Estimated δ for the current asset plotted as a vertical line against the cross-sectional histogram of δ across the N-asset panel; percentile rank annotated |
| GARCH-implied volatility term structure | Expected annualized vol at each horizon 1–252 days with 90% simulation confidence bands; slope direction annotated                                          |
| Long-memory parameter time series       | For FIGARCH: rolling MLE estimate of d over full history with threshold bands at d=0.5 and d=1.0                                                            |
| Probability Integral Transform test     | Histogram of u_t with KS test p-value; shape reveals exactly which part of the distribution is misspecified                                                 |
| Conditional VaR time series             | Daily 99% VaR over full history; exceedances as red dots; Kupiec and Christoffersen test p-values                                                           |
| Volatility state gauge                  | Current conditional vol from winning model as a percentile of 10-year history; four-zone dial                                                               |

---

## FEATURE 3 — HAR VOLATILITY FORECASTING SUITE WITH JUMP DECOMPOSITION AND MODEL CONFIDENCE SET

### Steps 1–9 remain as Document 2. The following are added:

**New Step 10 — Bipower variation jump estimator (primary)**

BV*t = (π/2) × Σ*{s=t−M+1}^{t} |r*s| × |r*{s−1}|

Jump component: J_BV,t = max(RV_t − BV_t, 0) where RV_t = Σ r²_s. BPV is the academic benchmark (Barndorff-Nielsen and Shephard, 2004). The RS/YZ divergence proxy is retained as secondary. When the two disagree by more than 20% of total variance, a "jump estimator disagreement" warning is flagged on the jump proxy time series chart.

**New Step 11 — HAR-X model (7th variant) with macro factors**

v\_{t+h} = β₀ + β_d × v_t^(d) + β_w × v_t^(w) + β_m × v_t^(m) + β_VRP × VRP_t + β_slope × slope_t + β_credit × spread_t + ε_t

where VRP_t is the volatility risk premium from Feature 5, slope_t = DGS10_t − DGS2_t, and spread_t = BAMLH0A0HYM2_t (HY credit spread from FRED). All three macro variables are available daily from FRED at zero cost. HAR-X is included in the MCS competition.

**New Step 12 — MCS combination forecast**

v̂*combo,t+h = (1/|M\*|) × Σ*{E ∈ M*} v̂\_{E,t+h} where M* is the 90% MCS. Also computed as inverse-QLIKE-weighted combination: w*E = (QLIKE_E)^{-1} / Σ*{E'} (QLIKE\_{E'})^{-1}. Tested against the individual MCS winner via DM.

**New Step 13 — Directional accuracy metrics**

Hit rate: fraction of OOS periods where sign(v̂*{t+h} − v_t) = sign(v*{t+h} − v_t). Directional DM: DM test applied to directional loss L_dir(v̂, v) = I{sign(v̂ − v_t) ≠ sign(v − v_t)} instead of squared loss.

---

### Custom Inputs

| Parameter                         | Options                                                                                                                   |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Asset                             | Any asset with daily price history; receives vol series from Feature 1                                                    |
| Volatility estimator input        | Any of the 6 estimators from Feature 1; Yang-Zhang recommended                                                            |
| Jump proxy method                 | Bipower variation BPV (default/primary); RS/YZ divergence (secondary); user-uploaded jump series                          |
| Jump estimator disagreement alert | On/Off; fires when BPV and RS/YZ diverge by >20% of total variance                                                        |
| HAR variants active               | Any subset of 7 (HAR, LHAR, HAR-J, HAR-Leverage, ACSV-HAR, A-ACSV-HAR, HAR-X), or all simultaneously with MCS competition |
| HAR-X macro regressors            | Any subset of: VRP (from Feature 5), yield curve slope (FRED DGS10−DGS2), HY credit spread (FRED BAMLH0A0HYM2)            |
| Cross-sectional universe for ACSV | User-defined list of assets                                                                                               |
| Forecast horizons h               | Any subset of {1, 5, 10, 21, 42, 63} trading days                                                                         |
| Estimation window                 | Rolling 252-day, rolling 504-day, or expanding                                                                            |
| Confidence intervals              | 80%, 90%, 95% bootstrap                                                                                                   |
| Leverage effect                   | Toggle on/off                                                                                                             |
| Newey-West bandwidth              | 5, 10, or 21 lags                                                                                                         |
| MCS combination forecast          | On/Off; equal-weight or inverse-QLIKE-weighted                                                                            |
| Directional accuracy metrics      | On/Off; adds hit rate and directional DM to accuracy table                                                                |

---

### Outputs

| Output                             | Description                                                                                                                                                                       |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HAR parameter table                | Coefficients β₀, β_d, β_w, β_m, β_J, β_J+, β_J−, β_lev, β_CSV+, β_CSV−, β_VRP, β_slope, β_credit (as applicable) with Newey-West SE and t-statistics; color-coded by significance |
| Multi-horizon forecast chart       | OOS forecast vs. actual vol at each horizon h with 90% bootstrap confidence bands                                                                                                 |
| Forecast accuracy table            | Per model per horizon: RMSE, QLIKE, MAE, R²_OOS, hit rate, directional DM win/loss; MCS-surviving models highlighted; MCS combination forecast row added at bottom                |
| Model Confidence Set               | MCS at 90% confidence under QLIKE loss; surviving models listed, eliminated models struck through; combination forecast tested against individual winner via DM                   |
| Jump proxy time series             | Daily J_t from both BPV and RS/YZ methods plotted simultaneously; disagreement flag fires when divergence >20%; spike dates annotated                                             |
| Leverage effect chart              | Rolling 63-day regression coefficient of lagged daily return on current vol over full history                                                                                     |
| ACSV predictive contribution chart | CSV+ and CSV− time series vs. target vol; regression-implied predictive contribution of each                                                                                      |
| HAR-X macro contribution chart     | Rolling contribution of VRP, slope, and credit spread regressors to fitted vol forecast; shows when macro factors are most informative relative to pure HAR regressors            |

---

## FEATURE 4 — VOLATILITY REGIME DETECTION ENGINE WITH PROBABILISTIC STATE ASSIGNMENT

### Steps 1–7 remain as Document 2. The following are added:

**New Step 8 — Exponentially weighted EM for the HMM (adaptive emission)**

In the M-step, standard sufficient statistics are replaced with exponentially weighted versions:

μ̂_k = Σ_t (δ^{T−t} × γ_t(k) × o_t) / Σ_t (δ^{T−t} × γ_t(k))

σ̂²_k = Σ_t (δ^{T−t} × γ_t(k) × (o_t − μ̂_k)²) / Σ_t (δ^{T−t} × γ_t(k))

where δ ∈ (0.97, 0.9999), default δ = 0.995 (half-life ≈ 138 days). This makes emission parameters adaptive to secular drift in vol regime characteristics.

**New Step 9 — Macro-augmented SJM feature vector**

Three macro features added to the SJM feature vector: (1) 21-day change in HY credit spread (BAMLH0A0HYM2), (2) 21-day change in 2s10s yield curve slope (DGS10 − DGS2), (3) VIX level normalized by its own 252-day z-score. Expanded feature vector f_t ∈ ℝ^9 (6 existing + 3 macro). All 9 features standardized before clustering.

**New Step 10 — Filtered vs. smoothed posterior comparison**

Both computed simultaneously:

- Smoothed posterior γ_t(k): uses full forward-backward algorithm (retrospective, uses future data)
- Filtered posterior α̃_t(k): uses forward algorithm only (live-tradeable signal)

Brier score gap between the two measures the forecasting accuracy cost of not having future information.

**New Step 11 — Regime duration model**

Weibull duration model fitted separately per regime state:

f(t | λ, k) = (k/λ) × (t/λ)^{k−1} × exp(−(t/λ)^k)

k < 1: hazard rate decreasing (crisis regimes — more likely to end when new). k > 1: hazard rate increasing (low-vol regimes — the longer they persist, the more likely to end). Survival probability for the current regime: P(regime lasts at least d more days | already lasted t days) = exp(−((t+d)/λ)^k + (t/λ)^k).

---

### Custom Inputs

| Parameter                            | Options                                                                                                         |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| Asset                                | Any asset                                                                                                       |
| Number of regimes K                  | 2, 3, or 4; tooltip shows historical avg vol per state                                                          |
| SJM jump penalty λ                   | 0 to 100; tooltip shows avg regime duration in days at each setting                                             |
| SJM feature vector                   | Standard 6-feature (vol-only) or macro-augmented 9-feature (adds credit spread, yield curve slope, VIX z-score) |
| HMM estimation window                | Rolling 252-day, 504-day, or expanding                                                                          |
| HMM emission adaptation              | Fixed parameters (standard) or EW-EM adaptive with forgetting factor δ (default 0.995)                          |
| HMM forgetting factor δ              | 0.97 to 0.9999; half-life displayed in tooltip                                                                  |
| Filtered vs. smoothed output         | Smoothed only (default), filtered only, or both simultaneously with Brier score gap                             |
| VIX threshold for macro rules engine | User-set; default is 25                                                                                         |
| Yield curve series                   | 2s10s (default), 3M10Y, user-defined                                                                            |
| Ensemble combination                 | Precision-weighted Brier score (default), equal-weight, user-defined manual weights                             |
| Transition alert threshold           | Probability mass required in a new state before alert fires (default 0.30)                                      |
| Regime duration model                | On/Off; fits Weibull distribution per state                                                                     |
| Duration model type                  | Weibull (default) or log-logistic                                                                               |

---

### Outputs

| Output                                  | Description                                                                                                                                                                     |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Probabilistic regime timeline           | Stacked area chart with K colored probability bands summing to 1 at each date                                                                                                   |
| Current regime probability dashboard    | Live probability vector over K states; 30-day and 90-day trend; current dominant state's persistence duration from Weibull model                                                |
| Regime duration survival chart          | Fitted Weibull distribution per state; survival probability curve P(lasts ≥ d more days) for the current regime given it has already lasted t days; shape parameter k annotated |
| Smoothed vs. filtered comparison        | Two probability timeline charts side by side; Brier score gap quantifying the accuracy cost of live vs. retrospective regime identification                                     |
| HMM emission drift chart                | Time series of μ̂_k(t) and σ̂²_k(t) per regime state under EW-EM; shows how "what low-vol looks like" has drifted secularly                                                       |
| Regime-conditional vol statistics table | Per state: avg vol, HAR forecast bias, avg cross-sectional return dispersion, Weibull shape parameter k, persistence probability                                                |
| Regime transition heatmap               | K×K matrix of empirical transition probabilities at 1-week, 1-month, 3-month horizons                                                                                           |
| Method divergence indicator             | Daily KL divergence between the three method probability vectors; high divergence = elevated structural uncertainty                                                             |
| Regime transition alert log             | Timestamped alerts with current probability vector, method-level probabilities, and historical base rate of stress                                                              |

---

## FEATURE 5 — VOLATILITY RISK PREMIUM MONITOR AND RETURN PREDICTABILITY ENGINE

### Steps 1–8 remain as Document 2. The following are added:

**New Step 9 — Hodrick (1992) standard errors for the BTZ regression**

Replace Newey-West with Hodrick (1992) standard errors for all overlapping return regressions:

Var*Hodrick(b̂) = (1/T²) × (X'X)^{-1} × (Σ_t x_t × (Σ*{s=t}^{t+H−1} û_s)²) × (X'X)^{-1}

where û*s = R*{equity,s} − â − b̂ × VRP_t is the residual from the non-overlapping daily regression. Hodrick SE is analytically correct for overlapping regressions and uniformly more conservative than Newey-West.

**New Step 10 — Regime-conditional BTZ decomposition**

BTZ regression run separately on two conditional subsamples using Feature 4 regime probabilities:

- Subsample 1: High VRP in low-vol regime (p_composite[low-vol] > 0.6 AND VRP > 70th percentile) — the "fear premium" state
- Subsample 2: High VRP in high-vol regime (p_composite[high-vol] > 0.6 AND VRP > 70th percentile) — the "realized vol catching up" state

Regime-conditional b̂ and R² displayed separately. These have opposite investment implications for variance sellers.

**New Step 11 — VRP term structure (three maturities)**

Three maturities computed simultaneously using HAR forecasts at corresponding horizons as physical expectation:

- 30-day VRP: IV²_t (from VIX) − HAR 22-day forecast²
- 90-day VRP: 3-month implied vol² (VXMT if available, else interpolated) − HAR 63-day forecast²
- 180-day VRP: 6-month implied vol² − HAR 126-day forecast²

Slope of the VRP term structure: upward-sloping = risk aversion spike expected to resolve quickly; inverted = elevated risk aversion expected to persist.

---

### Custom Inputs

| Parameter                                | Options                                                                                                                                        |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Asset                                    | Equity indices with associated published implied vol indices (SPX/VIX, STOXX50/VSTOXX, FTSE/VFTSE, Nikkei/JNIV, user-uploaded implied vol CSV) |
| Physical expectation method              | GARCH (Feature 2), HAR (Feature 3), Rolling mean, or all three simultaneously                                                                  |
| VRP display mode                         | Raw spread in annualized vol points, squared variance form, or Z-score                                                                         |
| Z-score lookback                         | 252-day, 504-day, 1260-day, or full history                                                                                                    |
| Return predictability regression horizon | 1 month, 3 months, 6 months                                                                                                                    |
| Standard error method                    | Newey-West (legacy) or Hodrick 1992 (default/recommended)                                                                                      |
| Regime-conditional BTZ                   | On/Off; requires Feature 4 regime probabilities; splits regression into fear-premium and realized-vol subsamples                               |
| VRP term structure                       | On/Off; computes VRP at 30, 90, and 180-day maturities simultaneously                                                                          |
| Cross-asset mode                         | On/Off: compute VRP simultaneously for all available vol index pairs                                                                           |

---

### Outputs

| Output                                  | Description                                                                                                                                                                                                                                               |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| VRP time series with percentile overlay | Daily VRP over 10-year history; all three physical expectation methods plotted; colored background band showing 10-year percentile                                                                                                                        |
| VRP term structure chart                | Three VRP estimates (30d, 90d, 180d) plotted simultaneously; slope direction annotated; inverted term structure flagged as "persistent risk aversion" signal                                                                                              |
| Regime-conditional BTZ panel            | BTZ regression results split by regime state: b̂, Hodrick SE, t-statistic, R², and current predicted return shown separately for fear-premium state vs. realized-vol state; regime-state indicator on the x-axis shows which subsample is currently active |
| Return predictability panel             | Rolling 252-day expanding regression with Hodrick SE; coefficient, t-statistic, R², and current predicted return per horizon; comparison of Hodrick vs. Newey-West t-statistics showing the conservatism adjustment                                       |
| Cross-asset VRP comparison table        | Current VRP, 10-year percentile, 3-month change, rich/cheap flag per asset                                                                                                                                                                                |
| VRP mean reversion speed chart          | Rolling 252-day OU half-life; shortening half-life = faster normalization                                                                                                                                                                                 |
| VRP component attribution stacked chart | C_GARCH (expected vol component) and C_RA (pure risk aversion component) as stacked areas; ratio C_RA / VRP_total is the primary investment signal for variance sellers                                                                                   |

---

## FEATURE 6 — CROSS-ASSET VOLATILITY CONNECTEDNESS AND SPILLOVER NETWORK

### Steps 1–6 remain as Document 2. The following are added:

**New Step 7 — Barunik-Krehlik frequency-domain connectedness decomposition**

Total connectedness decomposed into frequency bands via spectral representation of the VAR:

θ^{[ω1,ω2]}_{ij} = (σ_{jj})^{-1} × ∫*{ω1}^{ω2} (e_i' Ψ(e^{−iω}) Σ_u e_j)² dω / ∫*{−π}^{π} (e_i' Ψ(e^{−iω}) Σ_u Ψ(e^{iω})' e_i) dω

where Ψ(e^{−iω}) = Σ\_{h=0}^{∞} Φ_h e^{−iωh} is the frequency response function of the VAR. Three bands: short-run [1, 5 days], medium-run [5, 21 days], long-run [21, 252 days].

**New Step 8 — Exponentially weighted VAR**

VAR coefficients estimated using exponentially weighted OLS:

[c, A_1, ..., A_p] = argmin Σ*{t=T−W+1}^{T} δ^{T−t} × ‖Y_t − c − A_1 Y*{t-1} − ... − A*p Y*{t-p}‖²

where δ = 0.99 (user-adjustable). Makes the network more responsive to structural breaks while retaining statistical stability of the full window.

**New Step 9 — Connectedness-at-Risk**

CoR*t = VaR*{95%}(C\_{t+21} | macro_t)

Estimated via quantile regression of C\_{t+21} on (VIX_t, spread_t, slope_t). When current C_t approaches CoR_t, systemic risk headroom is exhausted.

---

### Custom Inputs

| Parameter                 | Options                                                                                                                                            |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Asset universe            | Any combination of equity indices, FX vol proxies, commodity vol proxies, credit spread proxies, crypto vol proxies; or user-defined custom subset |
| VAR lag order             | BIC-selected (default) or manual override 1–5                                                                                                      |
| VAR weighting             | Standard OLS (default) or exponentially weighted OLS with decay factor δ (default 0.99)                                                            |
| EW-VAR decay factor δ     | 0.97 to 0.9999; half-life displayed in tooltip                                                                                                     |
| FEVD forecast horizon H   | 5, 10, 21 trading days                                                                                                                             |
| Frequency decomposition   | On/Off (Barunik-Krehlik); when on, decomposes total C into short-run [1–5d], medium-run [5–21d], long-run [21–252d] bands                          |
| Rolling estimation window | 126-day, 252-day, 504-day                                                                                                                          |
| Alert threshold           | User-set total connectedness index level above which elevated-spillover alert fires                                                                |
| Connectedness-at-Risk     | On/Off; requires FRED macro data (VIX, yield curve, credit spread)                                                                                 |
| Network display layout    | Force-directed graph, adjacency matrix heatmap, or ranked bar chart                                                                                |

---

### Outputs

| Output                                   | Description                                                                                                                                                                                                                                 |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Total connectedness index time series    | Daily scalar C over rolling history; 10-year percentile on secondary axis; crisis dates annotated; horizontal alert line                                                                                                                    |
| Frequency-decomposed connectedness chart | Stacked area chart of C decomposed into short-run (panic contagion), medium-run, and long-run (structural integration) bands; rising short-run band during stress = panic contagion signal; rising long-run band = structural regime change |
| Connectedness-at-Risk gauge              | Forward-looking systemic risk gauge showing CoR*t (95th percentile of C*{t+21} conditional on current macro state); gap between current C_t and CoR_t is the systemic headroom; when gap closes to zero, flag fires                         |
| Net spillover ranking table              | All N assets ranked by NET_i; positive = transmitter; negative = receiver; updated daily; top transmitter labeled "Primary Systemic Risk Transmitter"                                                                                       |
| Dynamic connectedness network            | N nodes sized by total from-spillovers; directed edges colored by net flow direction; thickness proportional to FEVD magnitude; static snapshot and animated time-lapse                                                                     |
| Pairwise FEVD heatmap                    | N×N matrix of current θ̃^H\_{ij}; deep red cells are dominant transmission channels                                                                                                                                                          |
| Rolling to/from decomposition chart      | For any selected asset: stacked area of from-spillovers and to-spillovers over rolling history                                                                                                                                              |
| Connectedness regime alert               | When C crosses top quartile: top 5 pairwise spillovers, NET by asset, and historical forward portfolio returns                                                                                                                              |

---

## FEATURE 7 — MULTIVARIATE VOLATILITY AND DYNAMIC CONDITIONAL CORRELATION ENGINE

### Steps 1–8 remain as Document 2. The following are added:

**New Step 9 — DCC-MIDAS for long-run correlation component**

Q*t = (1−a−b) × R̄_t^{LR} + a × ẑ*{t-1}ẑ'_{t-1} + b × Q_{t-1}

where R̄_t^{LR} is the long-run correlation component estimated via a MIDAS regression on monthly realized correlations:

ρ̄*{ij,t}^{LR} = μ*{ij} + φ*{ij} × Σ*{k=1}^{K} β*k(θ_1, θ_2) × RC*{ij,t−k}

with Beta polynomial MIDAS weights β_k(θ_1, θ_2). The long-run component updates monthly; the short-run DCC captures daily fluctuations around it.

**New Step 10 — Probability-weighted crisis correlation matrix**

Replaces the hard VIX > 30 threshold with Feature 4 regime probabilities:

Ω_crisis = Σ_t p_composite(t)[high-vol] × ε_t ε_t' / Σ_t p_composite(t)[high-vol]

More statistically efficient than the hard-threshold version; internally consistent with the regime framework throughout the module.

**New Step 11 — Minimum torsion bespoke correlation**

Meucci (2013) minimum torsion orthogonalization:

T\* = argmin\_{T: TT'=Σ} ‖T − I‖²_F subject to T'Σ^{-1}T = I

T\* decomposes portfolio risk into N orthogonal uncorrelated risk sources where each factor loads primarily on one asset. Risk contributions are truly additive (no cross-terms). Displayed alongside standard MRC decomposition.

---

### Custom Inputs

| Parameter                       | Options                                                                                                      |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Asset universe                  | Any N assets with daily returns; N up to 50 recommended for DCC stability                                    |
| Estimation methods              | Any subset of 4 (Sample, EWMA, Ledoit-Wolf, DCC-GARCH); DCC-MIDAS as 5th option                              |
| DCC model                       | Standard DCC(1,1) or DCC-MIDAS (separates short-run and long-run correlation components)                     |
| DCC-MIDAS MIDAS lag K           | Number of monthly lags for the long-run correlation MIDAS regression; default K = 36 months                  |
| EWMA half-life                  | 21, 42, 63, 126 days or user-defined                                                                         |
| DCC parameters a, b             | Estimated by MLE (default) or constrained by user                                                            |
| Estimation window               | 252, 504, 756, 1260 days or expanding                                                                        |
| Crisis correlation definition   | Hard threshold: VIX > 30 (legacy) or probability-weighted using Feature 4 regime probs (default/recommended) |
| Stress period for crisis matrix | Preset: GFC 2008–2009, COVID Mar 2020, Rate shock Oct 2022, Liberation Day Apr–May 2025; or user-defined     |
| Display mode                    | Correlation matrix (default) or covariance matrix                                                            |
| Minimum torsion decomposition   | On/Off; produces bespoke uncorrelated risk factors                                                           |
| Portfolio input                 | Optional: input portfolio weights for risk attribution                                                       |

---

### Outputs

| Output                                   | Description                                                                                                                                                                                |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----- | --------------- |
| Correlation matrix heatmap               | N×N matrix; five tabs: Sample, EWMA, Ledoit-Wolf, DCC, DCC-MIDAS (when active)                                                                                                             |
| DCC-MIDAS decomposition chart            | For any selected asset pair: short-run DCC correlation (daily) plotted against the smooth long-run MIDAS component (monthly); shows tactical vs. strategic correlation dynamics separately |
| Normal vs. crisis correlation comparison | Two heatmaps (normal-period and probability-weighted stress-period) with difference heatmap; cells with                                                                                    | ΔCorr | > 0.3 annotated |
| DCC time series chart                    | For any selected asset pair: rolling daily DCC correlation over 10-year history                                                                                                            |
| Minimum torsion risk attribution         | N-factor bar chart showing risk contribution per bespoke torsion factor; each factor labeled by its primary asset loading; contributions are genuinely additive with no cross-terms        |
| Eigenvalue decomposition                 | Bar chart of eigenvalues with cumulative variance explained curve                                                                                                                          |
| Condition number history                 | Rolling condition number over full history; crisis spikes annotated                                                                                                                        |
| Portfolio risk attribution               | MRC waterfall per asset; pairwise covariance contribution heatmap                                                                                                                          |
| Minimum variance portfolio               | Analytical minimum variance weights vs. equal-weight vs. current portfolio                                                                                                                 |

---

## FEATURE 8 — VOLATILITY STRESS TESTING AND SCENARIO ENGINE

### Steps 1–5 remain as Document 2. The following are added:

**New Step 6 — Clayton copula for reverse stress test**

Fits a bivariate tail-dependent Clayton copula to the joint distribution of (r_t, Δσ_t):

C_Clayton(u, v | θ) = (u^{−θ} + v^{−θ} − 1)^{−1/θ}, θ > 0

where u = F*r(r_t) and v = F*{Δσ}(Δσ_t) are the probability integral transforms. Estimated by MLE over the lower 20% of the bivariate distribution. Lower tail dependence: λ_L = 2^{−1/θ}. For the reverse stress test, use the Clayton copula to simulate P(r_t < r\* | Δσ_t > shock) — giving a nonlinear, tail-accurate mapping from vol shock to portfolio return impact that replaces the linear leverage-effect approximation.

**New Step 7 — Graphical LASSO precision matrix for analog matching**

Replace sample covariance Σ_x in the Mahalanobis distance with a LASSO-regularized precision matrix:

Ω*GLASSO = argmin*Ω {tr(S × Ω) − log|Ω| + ρ × ‖Ω‖\_1}

where ρ is chosen by BIC. The graphical LASSO shrinks small partial correlations among macro variables to zero, producing a sparse precision matrix that weights informationally relevant macro dimensions more heavily. Analogs computed under this precision matrix are more accurate.

**New Step 8 — Adversarial scenario generator**

x*adversarial\* = argmax*{x: d²_M(x) < c²} w' E[r | x] × (−1)

Finds the worst-case historically-plausible scenario for this specific portfolio (Mahalanobis distance from current macro state < c standard deviations, default c = 2). Solved via projected gradient ascent. Output: "The most damaging historically plausible scenario for your portfolio is [description]. This scenario would produce a portfolio loss of [L]% and has occurred in [N] historical windows."

---

### Custom Inputs

| Parameter                           | Options                                                                                                                                                                                            |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scenario type                       | Historical preset, Historical analog, Parametric, Reverse stress, Adversarial, or all simultaneously                                                                                               |
| Historical preset library           | GFC Sep–Dec 2008, COVID crash Feb–Mar 2020, COVID recovery Apr–Jun 2020, Taper tantrum Jun 2013, EM crisis Aug 2015, Rate shock Oct 2022, Liberation Day Apr–May 2025, user-saved custom scenarios |
| Analog macro variables              | Any subset of: equity drawdown, yield curve shift, credit spread change, VIX change, FX move, commodity price change                                                                               |
| Analog precision matrix             | Sample covariance Mahalanobis (legacy) or graphical LASSO precision matrix (default/recommended)                                                                                                   |
| GLASSO regularization               | BIC-selected ρ (default) or user-defined                                                                                                                                                           |
| Number of historical analogs K      | 3, 5, 10, 20 closest periods displayed                                                                                                                                                             |
| Parametric shock unit               | Annualized bps of vol or number of standard deviations                                                                                                                                             |
| Reverse stress loss threshold       | % of portfolio value or absolute dollar amount                                                                                                                                                     |
| Reverse stress return-vol mapping   | Linear leverage effect (legacy) or Clayton copula tail model (default/recommended)                                                                                                                 |
| Clayton copula tail region          | Lower percentile cutoff for copula fitting; default 20%                                                                                                                                            |
| Adversarial scenario                | On/Off; Mahalanobis plausibility constraint c; default c = 2 standard deviations                                                                                                                   |
| Adversarial optimization iterations | 50 to 500 projected gradient steps; default 200                                                                                                                                                    |
| Portfolio input                     | Weights from any format; or pull from Feature 7 portfolio                                                                                                                                          |
| Contagion VAR lags                  | 1, 5, 21 days                                                                                                                                                                                      |

---

### Outputs

| Output                              | Description                                                                                                                                                                                                             |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Vol shock bar chart                 | Each asset's vol change under the scenario in annualized bps; 5th/95th historical percentile bands                                                                                                                      |
| Portfolio P&L attribution waterfall | Total P&L decomposed by asset; vol impact and return impact shown as separate bars                                                                                                                                      |
| Historical analog comparison        | K closest periods ranked by Mahalanobis distance (GLASSO-precision); for each: vol path, portfolio return, max drawdown; plain-language summary of the closest episode                                                  |
| Reverse stress scenario output      | Minimum-probability vol shock vector producing the stated portfolio loss; Clayton copula-based probability; plain-language interpretation; stress efficiency frontier curve (loss L vs. minimum d²\*(L))                |
| Adversarial scenario card           | The single most damaging historically-plausible scenario for this specific portfolio; vol shocks per asset; portfolio loss estimate; number of historical occurrences; description of the macro state that generates it |
| Contagion impulse response chart    | 1-SD shock to one asset's vol: impulse response of all other assets at 1, 5, 10, 21-day horizons with 90% bootstrap confidence bands                                                                                    |
| Multi-scenario comparison table     | Up to 6 scenarios: portfolio P&L, max vol spike, DCC correlation average, estimated recovery time, stress VaR, stress CVaR                                                                                              |
| Stress VaR and CVaR                 | Portfolio 95% and 99% loss estimates from Monte Carlo simulation using the shocked DCC covariance matrix                                                                                                                |

---

## FEATURE 9 — PORTFOLIO VOLATILITY BUDGET MONITOR AND DYNAMIC RISK TARGETING ENGINE

### Steps 1–7 remain as Document 2. The following are added:

**New Step 8 — Two-step rebalancing**

Step 1: Apply uniform λ_scale to bring total portfolio vol to target. Step 2: Within-portfolio budget-alignment rebalance solving:

min\_{Δw} Δw' Ω Δw subject to (w + Δw)' Ω (w + Δw) = σ²_target and Σ_i Δw_i = 0

This is a quadratic program with two equality constraints solved analytically via KKT. Simultaneously hits the vol target and realigns the risk budget — strictly superior to uniform scaling alone.

**New Step 9 — Almgren-Chriss market impact cost model**

Temporary impact cost for trading a fraction of asset i's average daily volume in a single day:

MI_i = γ_i × σ_i × |Δw_i × AUM| / (ADV_i × P_i)

where γ_i ≈ 0.1 (market impact coefficient), σ_i is daily vol, ADV_i is average daily dollar volume (from Yahoo Finance), and P_i is current price. Total transaction cost: TC_total = Σ_i (c_explicit + MI_i) × |Δw_i|. Nonlinear in position size and sensitive to current vol.

**New Step 10 — Kelly-criterion vol targeting**

Kelly-optimal portfolio volatility at each date:

σ\*\_Kelly,t = μ̂_p,t / σ̂_p,t

where μ̂_p,t is the BTZ-implied expected portfolio return from Feature 5 and σ̂_p,t is the DCC-forecast portfolio vol. When the Kelly target is significantly below the user's fixed target, the system flags that the current risk-return tradeoff does not justify the stated risk budget.

---

### Custom Inputs

| Parameter                   | Options                                                                                                                          |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Portfolio weights           | Manual entry, CSV upload, or equal-weight default                                                                                |
| Covariance estimator        | DCC-GARCH (default), EWMA, Ledoit-Wolf, or sample from Feature 7                                                                 |
| Vol target level            | Fixed 5%–30% in 1% steps; regime-conditional; or Kelly-criterion (auto-computed from Feature 5 BTZ return and Feature 7 DCC vol) |
| Regime-conditional targets  | User-sets σ^k_target per regime                                                                                                  |
| Regime probabilities source | Feature 4 output (default)                                                                                                       |
| Rebalancing method          | Uniform scaling only (legacy) or two-step: uniform scaling + QP budget realignment (default/recommended)                         |
| Forward vol forecast source | DCC 1-day ahead (default), GARCH from Feature 2, or EWMA                                                                         |
| Rebalancing trigger         | Daily, weekly, or signal-triggered when portfolio vol deviates from target by more than X%                                       |
| Gross exposure constraint   | Maximum gross exposure multiple                                                                                                  |
| Transaction cost model      | Flat bps per trade (simple) or Almgren-Chriss market impact model (default/recommended for AUM > $100M)                          |
| Flat bps cost               | User-set bps per trade; used in simple model                                                                                     |
| Market impact coefficient γ | Default 0.1; user-adjustable for Almgren-Chriss model                                                                            |
| Kelly vol target            | On/Off; requires Feature 5 BTZ regression to be active                                                                           |
| Kelly target display        | Show Kelly-optimal target alongside fixed and regime-conditional targets for comparison                                          |

---

### Outputs

| Output                              | Description                                                                                                                                                                                                                                  |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Portfolio vol dashboard             | Four large numerals: current 21-day realized vol; DCC/GARCH 1-day forward forecast; current regime-conditional vol target; scaling factor λ_scale. Fifth numeral added when Kelly is active: Kelly-optimal target σ\*\_Kelly,t               |
| Kelly vs. fixed target comparison   | Time series of σ\*\_Kelly,t plotted against the fixed user target and the regime-conditional target; when Kelly target falls significantly below the fixed target, a "risk-return headroom exhausted" flag fires                             |
| Vol-to-target gap gauge             | Signed bar showing gap to target; 7-day and 30-day trend                                                                                                                                                                                     |
| Vol budget attribution waterfall    | Each position: current MRC in annualized bps and as % of total vol; assigned budget fraction; signed deviation; sorted from most over-budget to most under-budget                                                                            |
| Two-step rebalancing proposal       | Step 1 result (uniform-scaled weights); Step 2 result (QP budget-realigned weights); delta between the two; one-way turnover per step; Almgren-Chriss market impact cost estimate per step; net-of-cost expected improvement in Sharpe ratio |
| Transaction cost comparison         | Side-by-side of flat bps estimate vs. Almgren-Chriss estimate for the proposed rebalance; when the two diverge substantially (large AUM or high-vol period), the Almgren-Chriss estimate is highlighted as the binding constraint            |
| Scaling factor history              | Daily time series of λ_scale over full backtest; periods where λ < 1 shaded red                                                                                                                                                              |
| Regime-conditional target evolution | Time series of σ_target,t vs. actual portfolio vol                                                                                                                                                                                           |
| Historical vol-targeting backtest   | Cumulative return, annualized vol, Sharpe, max drawdown, and Calmar for vol-targeted overlay vs. equal-weight baseline                                                                                                                       |

---

## CROSS-MODULE ADDITIONS (new — no equivalent in Document 2)

These three outputs sit at the module level, fed by multiple features simultaneously.

**Cross-Module 1 — Global volatility regime synchronization index**

SYNC_t = (1/N) × Σ_i I{p_composite,i(t)[high-vol] > 0.5}

Fed by Feature 4 (regime probabilities across all N assets). SYNC_t → 1: all assets simultaneously in high-vol regimes (global systemic stress). SYNC_t → 0: idiosyncratic vol. Displayed alongside the total connectedness index from Feature 6. Divergence between C_t (high) and SYNC_t (low) = integrated but not simultaneously stressed = contagion type indicator.

**Cross-Module 2 — Synthetic volatility surface (no options data)**

Term structure of realized vol across horizons (5, 10, 21, 42, 63, 126, 252 days) from HAR (Feature 3) and GARCH term structure (Feature 2). The moneyness dimension constructed by evaluating the GARCH conditional density at different quantiles. Not a true options-implied surface but the closest achievable from daily OHLCV alone; captures regime-conditional skew via asymmetric GARCH models.

**Cross-Module 3 — Volatility-adjusted momentum signal**

MOM_adj,i,t = MOM_raw,i,t / σ_YZ,i,t

where MOM*raw,i,t = (P*{i,t} / P\_{i,t−252}) − 1 is the 12-month price return. Cross-sectionally ranked across the N-asset panel. Top-quintile ranked assets by vol-adjusted momentum have empirically higher Sharpe ratios than raw momentum (Daniel and Moskowitz, 2016). Displayed as a daily-updated ranked panel within Feature 1's cross-asset panel mode.

---

## REVISED MODULE INTEGRATION MAP

| Feature                        | Primary Input                      | Primary Dependency                      | Key Upgrades from Doc 3                                                          |
| ------------------------------ | ---------------------------------- | --------------------------------------- | -------------------------------------------------------------------------------- |
| 1. Multi-Estimator Vol Engine  | Daily OHLCV                        | None — foundational                     | Bandi-Russell estimator, empirical RE, OGF detector, range correlation matrix    |
| 2. GARCH Family Suite          | Daily returns; Feature 1 vol proxy | Feature 1 for OOS evaluation            | Regime NIC ribbon, Nyblom stability, APARCH δ benchmarking, Realized GARCH       |
| 3. HAR Forecasting Suite       | Feature 1 YZ vol; daily returns    | Feature 1 required; Feature 5 for HAR-X | BPV jump estimator, directional DM, MCS combination, HAR-X macro                 |
| 4. Regime Detection Engine     | Feature 1 vol; FRED macro          | Feature 1 required                      | EW-EM adaptive HMM, macro-augmented SJM, filtered vs. smoothed, duration model   |
| 5. VRP Monitor                 | FRED VIX; Features 2–3 forecasts   | Features 2 and 3 required               | Hodrick SE, regime-conditional BTZ, VRP term structure                           |
| 6. Connectedness and Spillover | Feature 1 vol (all N assets)       | Feature 1 across N assets               | Barunik-Krehlik frequency decomposition, EW-VAR, Connectedness-at-Risk           |
| 7. Multivariate Vol and DCC    | Daily returns (all N assets)       | Feature 1 for crisis definition         | DCC-MIDAS, probability-weighted crisis correlation, minimum torsion              |
| 8. Stress Testing              | Features 6 and 7 outputs           | Features 6 and 7 required               | Clayton copula, graphical LASSO analog matching, adversarial scenario generator  |
| 9. Portfolio Vol Budget        | Features 4 and 7 outputs           | Features 4 and 7 required               | Two-step QP rebalancing, Almgren-Chriss market impact, Kelly-criterion targeting |
| Cross-module                   | All features                       | All features                            | SYNC index, synthetic vol surface, vol-adjusted momentum                         |
