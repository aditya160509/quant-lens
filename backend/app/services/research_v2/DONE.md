# Research V2: Implementation Status

Spec: `docs/research features.md` (Features 1-9 and 11; the spec defines no Feature 10).
Review that drove this rebuild: `docs/reviews/RESEARCH_V2_REVIEW.md`.

## Layout

| Path | Role |
|---|---|
| `core/data_loader.py` | Local parquet/CSV access, strict ticker resolution, point-in-time fundamentals, upload sandbox |
| `core/panel.py` | Point-in-time research panel: signals, controls, weights, dependent variables, universe filters |
| `core/stats.py` | Newey-West, stationary bootstrap, Patton-Timmermann MR, Chow, Andrews sup-F (simulated p-values), Fisher/Stouffer, power, HLZ |
| `core/estimators.py` | Fama-MacBeth (numba), sorts, double sorts, GRS, spanning, Shanken vs GLS-GMM two-pass, weak identification, panel OLS + Hausman |
| `core/canonical.py` ... `core/zoo.py` | One module per feature |
| `core/holdout.py` | Protected OOS windows and locked (confirmatory) specifications |
| `features/feature_XX.py` | Input and output declarations plus `run()`; the frontend renders forms and cards from these |
| `registry.py` | Lazy feature registry and manifest |
| `fetchers/fetch_missing_data.py` | Append-only FRED and ETF refresh (run manually) |
| `backend/app/api/research_v2.py` | `/api/labs/research/v2`: manifest, symbol search, validated uploads, background jobs, holdouts, locks |

## Data rules

- Price signals at month t use prices up to t; the dependent variable covers (t, t+h].
- Fundamentals become usable 90 days after `reportDate`, expire after 550 days, and are never back-filled. Flow items (net income, gross profit) use annual reports only.
- Market cap = month-end price x point-in-time shares outstanding.
- Named universes resolve to US common equities (no exchange suffix, with a sector). Unknown tickers are rejected.
- Uploads are only readable from `backend/data/research_v2/uploads/`.

## Features

| # | Feature | Estimators |
|---|---|---|
| 01 | Canonical Test Engine | FM with NW SEs and a validity regime (bootstrap SE outside it), linearmodels panel OLS with FE and clustered/Driscoll-Kraay SEs, FE-vs-RE Hausman, single/independent/sequential double sorts, MLE GRS, Patton-Timmermann MR test, FF spanning, calendar-time portfolio, Shanken vs GLS-GMM two-pass on 25 portfolios, weak-identification check, bootstrap vs t disagreement, LaTeX/CSV |
| 02 | Robustness Engine | Sequential or full specification curve over time windows, subsamples, crisis exclusions, universes, transforms, controls, SEs and weighting; Simonsohn-style permutation test on the curve; eta-squared decision attribution; AIC/BIC/sample/inverse-variance weighting |
| 03 | Placebo Suite | Within-date permutation, overlap-free time displacement, wrong direction, McLean-Pontiff OOS with Campbell-Thompson R², adjacent asset classes (bond, commodity, FX ETFs), Fisher/Stouffer, power, protected holdout |
| 04 | Regime Conditional | 9 conditioning variables plus intersections, fixed or data-driven thresholds, Chow on slopes net of date effects, signal x regime interaction (date-clustered), FM premium difference test, quantile regression on the condition, Markov switching, amplification factor |
| 05 | Diagnostic Center | DW, Ljung-Box, JB and Andrews on FM premia; VIF, White, Breusch-Pagan, RESET, Wooldridge panel AR(1), Cook's by month, DFBETA/DFFITS, partial residuals on the within-date pooled regression |
| 06 | Specification Builder | 2-8 columns, each with its own estimator (FM or panel OLS), controls, FE, SEs, weighting (WLS) and period; booktabs LaTeX, 6.5-inch PDF, CSV, forest plot; columns auto-picked from the Feature 2 curve; confirmatory tags only for locked specs |
| 07 | Causal Identification | DiD: TWFE, Callaway-Sant'Anna, Sun-Abraham, did2s, Goodman-Bacon (sums to TWFE), pre-trend Wald test, placebo dates, propensity matching and balance. Event study: market/FF3/FF5/Dimson, CAR/BHAR, t, Patell, BMP, Kolari-Pynnonen, drift, continuation, calendar-time alpha. RD: rdrobust (CCT bandwidth, robust bias-corrected), rddensity, covariate continuity, placebo cutoffs, bandwidth sensitivity, donut. IV: 2SLS/LIML, first-stage F vs 10 and 104.7, Anderson-Rubin set, Wu-Hausman, Durbin, Sargan, Wooldridge |
| 08 | Signal Decay | McLean-Pontiff split (discovery and publication), exponential/linear/hyperbolic fits in months since discovery, block-bootstrap half-life CI, Andrews arbitrage-arrival date with CI, vitality, cheap vs costly-to-arbitrage decomposition, international replication, Sharpe life cycle |
| 09 | Synthetic Control | pysyncon classic (V optimised), augmented, robust; Xu generalized SC with CV rank; placebo in space and time; leave-one-out; Chernozhukov-Wuthrich-Zhu conformal bands; staggered adoption; donor concentration |
| 11 | Factor Zoo | Spanning against FF5+MOM or an extended library (quality, low-vol, BAB, STR, internal factors, uploads); HLZ Bonferroni/Holm/BHY and a current Bonferroni bar; correlation map and IC-IR positioning |

## Known limitations

- Fundamentals start in 2021, so value, quality, profitability, investment, leverage and size have about four years of history. Runs using them say so.
- Sector is treated as time-invariant.
- No single-stock implied volatility, so a VRP signal is not offered.
- The credit-spread regime uses Moody's Baa-10y; ICE BofA IG OAS is licence-limited to about three years on FRED.
- RD uses the CCT bandwidth (the successor to Imbens-Kalyanaraman) and the Cattaneo-Jansson-Ma density test (the modern McCrary).
- Markov switching models the monthly FM premium, not a joint panel regression with regime-specific coefficients.
- A "geographic average" IV instrument is not offered because the data has no geography.
- Cancelling a job stops publication of its result; a computation already running finishes in the background.
- International replication uses local-currency returns.

## Checks

```
cd backend && PYTHONPATH=. python3.11 -m pytest tests/test_research_v2_*.py
cd frontend && npx jest src/components/research-v2 && npm run build
```

Refresh macro data: `python3.11 -c "from app.services.research_v2.fetchers.fetch_missing_data import fetch_fred_series; print(fetch_fred_series())"`
