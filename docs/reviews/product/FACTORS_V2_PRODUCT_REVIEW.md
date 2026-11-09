# Factors product review: factor lab, redone against the feature rule (deepened)

Deepened 2026-11-09. The first pass of the same day read headers and docstrings. This version reads function bodies in `backend/app/services/factors_v2/` (registry, `core/contracts.py`, `core/backtest.py`, `core/capacity.py`, `core/alerts.py`, `features/inputs.py`, and features 03, 04, 05, 06, 07, 09, 11, 13, plus parts of 01, 08, 10, 12). Competitor claims were fetched where marked. Nothing was run: no tests, no manifest call, no servers. The frontend was removed on 2026-11-06 (PLAN line 77), so there is no UI to judge.

## Contents
1. Verdict
2. What is real and what is hollow (verified in code)
3. Parity with paid tools (fetched)
4. Feature table: keep, build, later, cut
5. Our own ideas: freedom and customisation
6. Open-source picks and licences (fetched)
7. Data limits
8. Build checklist (E easy, M medium, H hard)
9. Sources and unverified

---

## 1. Verdict

Factors is a factor lab with a real backtest core and honest "missing reason" fields, but it has three correctness bugs and several names that promise more than the code does. It is not a Barra replacement and should not be sold as one.

- **Fix before any page.** Two bugs change numbers users would see: the F05 half-life formulas add constant offsets (section 2), and the F10 optimiser takes its expected returns from the in-sample factor mean by default. A third, F04's conditional returns, may use the same-day return to define the regime (to verify).
- **Keep** the 11 features that do real work. Merge F03 and F12 into tabs, F06 into F05 as a tab, and move F08, F10 and F11 onto shared engines (merge map decisions 3, 7 and 14).
- **Relabel** F06 "Factor Crowding Monitor" to concentration and liquidity. The registry title over-claims; the meta block already says it is a proxy.
- **Build** the five-page workspace, the data banner, the Validate hand-off with trial count, and the monitor's delivery.
- **Later**: ownership-based crowding, stock-level specific risk, non-US factor sets, real-time monitoring.

---

## 2. What is real and what is hollow (verified in code)

| Area | Real (read in code) | Hollow, wrong or over-named |
|---|---|---|
| Manifest and run path | `features/inputs.py` builds the manifest; `registry.py` titles every feature from `contracts.py`; `run_feature` stamps `source_versions` | Every input help string is still the shared sentence (idea 3) |
| Backtest core (`core/backtest.py`) | Signals at t execute at the t+1 close. Positions earn from t+2. Costs are drift-based (the trade is solved with `brentq`, so cost is on turnover after drift). Borrow is charged on short notional. A missing held return raises, it is not filled | Real. The strongest code in the module |
| Stationary bootstrap (F07, F05) | `arch` `StationaryBootstrap` with a seeded generator | Real |
| F03 attribution | Takes supplied `factor_exposures`; raises if none given; says in `meta` that Brinson, carry-over and selection residual are missing | Real and honest. It attributes typed exposures; it does not estimate them |
| F04 regimes (`feature_04.py`) | Gaussian HMM trained on the first 60% of a 21-day rolling mean; holdout probabilities from causal forward filtering; `meta` says holdout only | **To verify:** `conditional_returns` label each day by the regime probability that uses that day's return (`obs` is a rolling mean that includes day t), so the average return per regime is partly in-sample by construction. Needs a one-day lag test before the table is shown as a conditional return |
| F05 decay (`feature_05.py`) | IC by horizon, stationary-bootstrap intervals on mean IC, decay fits | **Wrong formulas.** Exponential fit `a*exp(-b*h)` reaches half at `h = ln2/b`; the code returns `1 + ln2/b` (`feature_05.py`, `_fit_decay`). Hyperbolic `a/(1+b*h)` reaches half at `h = 1/b`; the code returns `1/b + 2`. Every half-life card is off by a constant. Also: overlapping horizons (63 and 126 sessions) make the bootstrap intervals too narrow, and the module does not say so |
| F06 "crowding" | Top-quintile equal-weight count (`1/len(top)`), sector HHI, 63-day volatility percentile, Roll spread on price changes | **No ownership, short-interest, 13F or flow data.** Registry title "Factor Crowding Monitor" (`core/contracts.py:60`). The Roll spread runs on `price_sample(max_tickers=240)`, a sample, not the universe; the output does not say so. The meta block does say "not an institutional-positioning composite" |
| F07 backtest | Gross and net equity, Monte Carlo bands, quintile and decile monotonicity from the shared backtest | Real. `_empty_quintile_rows` and `_rolling_premium_spread` are defined and never called (grep: one hit each) |
| F08 covariance | `ledoit_wolf`, `sample`, `ewma`, `dcc_ewma`; matrix validation shows requested and used method | The DCC here is EWMA volatility with fixed recursion parameters, not GARCH/MLE. Volatility's canonical DCC is `dcc.py`. Label the difference |
| F09 capacity | Per-security square-root impact on observed USD ADV; sensitivity grid recomputed per case; time to liquidate; missing ADV raises | `_ALMGREN_ETA` and `_SQRT_MODEL_THRESHOLD_USD` are defined and never used (dead constants). The impact coefficient is `payload impact_eta`, default 0.1, not calibrated. Capacity uses one as-of cross-section of ADV, not a time series |
| F10 optimiser (`feature_10.py`) | Mean-variance on factor returns with robust penalty and optional Black-Litterman | **Expected returns default to the in-sample mean:** `mu = rets.mean() * 252` (line ~31). The optimiser then maximises the estimation errors it was given. Robust penalty default 0.25 helps but does not fix it. Weights are not out-of-sample |
| F11 stress (`feature_11.py`) | VAR with AIC/BIC lag choice, IRFs, residual-bootstrap bands, historical analog, reverse stress | **Silent defaults:** exposures default to `1/N` each, shocks default to `-2 sigma` per factor, neither is listed in `meta`. `var_error` and `max_lags_used` read through `locals().get(...)`, a fragile pattern. `hedging_recommendation` table is always empty (`hedge_rows = []`) |
| F12 DNA | HAC spanning regression on the other selected factors | Real. It inherits the F06 concentration proxy in its `concentration` axis |
| F01 valuation spread | Spread, percentile series, crisis anchors, expected-return regression | The "high" alert fires at the 70th percentile by default (`alert_percentile or 70`) and its text says "upper historical tail". 70th is not a tail. Rename |
| F13 "live" monitoring (`feature_13.py`, `core/alerts.py`) | Cross-sectional IC, CUSUM break test (statsmodels), idempotent SQLite events (`triggered`, `recovered`), unknown IC skipped | Not live. In-app state only. `alert_policy` says email, webhook and Slack are "unavailable_no_delivery_worker". No matured hit rate |
| F14 report | ReportLab PDF; section order; "Crowding Disclosure" section (ILPA DDQ 2.0 wording: "concentration, liquidity, and crowding controls") | The section claims crowding controls on the strength of the F06 proxy. Rename the section and drop "crowding controls" |
| Data guards | Statements lagged 90 days (`fundamental_lag_days=90` in `core/panel.py`); unknown IC stays unknown | Survivorship and 2021-only statement history remain (carried measurement, not re-measured) |

**Summary of corrections to the 2026-11-09 first pass.** The first pass called F13 and F11 over-claims (correct) and rated F05 as "unverified" (it is wrong in the half-life formula). It did not see the F10 default, the F04 conditional-return question or the F09 dead constants.

---

## 3. Parity with paid tools (fetched 2026-11-09)

| Tool | What the money buys | Price | Where we stand |
|---|---|---|---|
| Portfolio123 | Screen, rank, backtest; point-in-time stock data; ranking systems | Screener $84/month ($1,000/year): 5-year backtest, expert ranking systems, customisable formulas. Backtest $167/month ($2,000/year): 10-year backtest, custom ranking systems, book of strategies. Portfolio $250/month ($3,000/year): 15-year backtest, hedging and long/short, AI Factor. Ultimate $500/month ($6,000/year): 20-year backtest, optimiser, regression functions. Fetched from `portfolio123.com/sv/register/pro` | Correction: the first pass put custom ranking systems at $84. They start at the $167 tier. We lack stored custom ranking systems and long point-in-time history (we hold 2021 to 2025 statements) |
| Bloomberg PORT | Factor, full-revaluation, macro and climate scenarios | Not priced. Page blocked when fetched 2026-11-09 | F11 covers factor-based stress only |
| Axioma, MSCI Barra | Equity risk models with specific risk, attribution, scenarios | Not priced. Barra URL returned "Document Not Found" and the Axioma URL was invalid on 2026-11-09 | We have factor covariance (F08) and no stock-level specific risk. Not a replacement |
| Alphalens (alphalens-reloaded) | IC, quantile returns, turnover, tear sheets | Free, Apache-2.0 (fetched) | F05 and F07 cover the same ground; use Alphalens as a cross-check |
| Stock Rover, Koyfin, Finviz, TradingView | Screens; no factor backtest or capacity | Koyfin $0, $39, $79 per month (fetched 2026-11-09) | We lead on tests and limits |

Parity gaps worth closing: stored ranking systems, benchmark-relative tear sheet, scheduled monitors with delivery. Gaps not to chase: licensed risk-model data, full revaluation stress.

---

## 4. Feature table: keep, build, later, cut

| # | Feature (registry title) | Decision | Page | Reason |
|---|---|---|---|---|
| F01 | Valuation spread | Keep; fix the alert wording and the 70th-percentile tail label | Value and exposure | Real computation. Output quality still unverified |
| F02 | Exposure | Keep; list the default exposures in `meta` or require them | Value and exposure | Silent defaults elsewhere (F11) show the same risk |
| F03 | Attribution | Keep as tab of F02 | Value and exposure | Honest about typed exposures |
| F04 | Regime analysis | Keep; fix conditional-return lag (to verify) | Regime and timing | Regime kernel moves to Volatility (decision 7) |
| F05 | Alpha decay | Keep; **fix half-life formulas**; widen intervals for overlapping horizons | Regime and timing | Real after the fix |
| F06 | Crowding | Keep as tab of F05, **renamed "concentration and liquidity"**; registry title changes too | Regime and timing | Proxy only |
| F07 | Backtest engine | Keep | Test and capacity | Real. Delete two unused helpers after a smoke test |
| F08 | Covariance | Keep as lens on the shared covariance engine; label the EWMA DCC | Risk and construction | Portfolio owns covariance (decision 3); Volatility owns DCC (decision 14) |
| F09 | Capacity | Keep; calibrate impact or label it uncalibrated; remove two dead constants | Test and capacity | Needs calibration to call capacity a result |
| F10 | Optimiser | Keep; **expected returns must be explicit or shrunk**, not the in-sample mean by default | Risk and construction | Shared construction engine with Portfolio |
| F11 | Stress | Keep as lens; **name defaults in `meta`**; drop the empty hedge table until an instrument map exists | Risk and construction | Real hedges later |
| F12 | DNA | Keep as tab of F02 | Value and exposure | Inherits the F06 proxy |
| F13 | Monitor | Keep; build delivery, scheduler and matured hit rate | Monitor | Today state tracking only |
| F14 | Report | Keep; rename "Crowding Disclosure" and drop "crowding controls"; add CSV | Export | PDF exists |
| Cut | "Crowding" wording on F06, F12 and F14 | Cut | all | Over-claims |
| Cut | `hedging_recommendation` table until an instrument map exists | Cut | Risk and construction | Always empty |
| Cut | Dead helpers and constants in F07 and F09 | Cut | none | Defined, never called |
| Later | Stock-level specific risk | Later, paid data | none | Needs a risk-model data source |
| Later | Ownership-based crowding | Later, paid data | none | No ownership, short-interest, 13F or flow data |
| Later | Real-time monitoring | Later, paid data | none | Intraday data not held |

---

## 5. Our own ideas: freedom and customisation

1. **Bring your own factor.** `factor` is a fixed list of 10 in `inputs.py`. Add an upload or formula slot so any column becomes a factor through F01, F05 and F07. Honest limit: it joins the trial count.
2. **Choose your own factor model.** `factor_model` offers ff3, ff5, ff5_mom, carhart, capm. Let the user pick any subset of factors and a custom benchmark.
3. **Explicit expected returns.** Three choices with the default named on the page: user input, shrunk historical mean, or Black-Litterman views. Never the raw in-sample mean without a label.
4. **Named defaults.** Every default the engine fills (exposures, shocks, weights, half-life horizons) appears in the output `meta`. A silent default becomes a visible one.
5. **Trial ledger on every run.** Count each changed input as a trial and feed the deflated Sharpe, shown beside the result (decision 4).
6. **Saved recipes.** Save a full payload as a named recipe and re-run it; shareable as a file.
7. **Limits banner as an object.** Survivorship, 90-day lag, 2021+ statements, printed on every result and in the PDF.
8. **Compare any two runs** side by side, differences highlighted.
9. **Export everything** as CSV or JSON with the payload and `source_versions` attached.

---

## 6. Open-source picks and licences (fetched 2026-11-09)

| Library | Use | Licence | Status |
|---|---|---|---|
| alphalens-reloaded (stefan-jansen) | IC and quantile tear sheets; cross-check for F05 and F07 | Apache-2.0 (shown on repository page) | Cross-check only, not a dependency |
| skfolio | Optimisation, factor models, cross-validation on scikit-learn; 46 descriptors in its factor model | BSD-3-Clause (shown on repository page) | Candidate for F10 cross-checks and the shared construction engine, only if needed |
| Riskfolio-Lib | Mean-risk, HRP, Black-Litterman, 26 convex risk measures | Licence not in the fetched text. Prior "BSD-3" is **unverified** | Alternative for CVaR and Black-Litterman if skfolio is not used |
| arch | Stationary bootstrap (F05, F07) | Already used. Licence not fetched; **unverified** this pass | Keep |
| hmmlearn, scikit-learn, statsmodels | F04, F11, F13 | Standard BSD-3, **unverified** this pass | Keep |

Pick: keep the current stack. Add skfolio only if the shared optimiser needs cross-validated constructions. Do not add it for F10 alone.

---

## 7. Data limits

These print on every result and in the PDF:

- Statements lagged 90 days; statement history 2021 to 2025 only.
- Survivorship: no delisted names in the market universe.
- Roll spread (F06) estimated on a 240-ticker sample.
- Capacity (F09) uses one as-of cross-section of ADV.
- Decay intervals (F05) assume independence across overlapping horizons; they are too narrow.
- No ownership, short-interest or flow data.

---

## 8. Build checklist (E easy, M medium, H hard)

The list lives in `docs/plans/FACTORS_CHECKLIST.md`. The additions this deepening makes, placed in the batch that owns the code:

Batch 1 (clean):
- [ ] `E` F05 half-life formulas: `ln2/b` for exponential, `1/b` for hyperbolic; add one assert-based check that a known curve returns its known half-life
- [ ] `E` Rename the F06 registry title and labels to "concentration and liquidity"; rename F14 "Crowding Disclosure" and drop "crowding controls"
- [ ] `E` F01 alert wording: "70th percentile", not "upper historical tail"
- [ ] `E` Remove the dead constants `_ALMGREN_ETA`, `_SQRT_MODEL_THRESHOLD_USD` and the unused helpers `_empty_quintile_rows`, `_rolling_premium_spread` (grep confirms one hit each; smoke-test before deleting, per AGENTS)
- [ ] `E` F11: remove the `locals().get(...)` pattern; name the default exposures and shocks in `meta`

Batch 3 (value and exposure):
- [ ] `E` F04 conditional returns: lag the regime label one day and compare; keep the table only if the lagged version still shows the spread (to verify first)

Batch 6 (risk and construction):
- [ ] `M` F10: expected returns explicit or shrunk by default; print the default used; add one out-of-sample check on weights
- [ ] `E` F08: label the EWMA DCC as not the Volatility DCC

Batch 5 (test and capacity):
- [ ] `E` F09: label the impact coefficient as uncalibrated until calibrated; say the ADV snapshot is one date

Existing items keep their place: sparkline removal, per-field help, data banner, pages, Validate hand-off, freedom items, CSV, ship.

Size: E 9, M 3, H 4 across the batches, counting the existing items.

---

## 9. Sources and unverified

Fetched 2026-11-09:
- Portfolio123 Professional plan page: https://www.portfolio123.com/sv/register/pro (prices and tier features)
- Portfolio123 search snippet on plans: https://www.portfolio123.com/sv/register (search result only)
- Koyfin pricing: https://www.koyfin.com/pricing/
- alphalens-reloaded: https://github.com/stefan-jansen/alphalens-reloaded
- skfolio: https://github.com/skfolio/skfolio
- Riskfolio-Lib: https://github.com/dcajasn/Riskfolio-Lib

Failed on 2026-11-09 and not replaced: MSCI Barra page ("Document Not Found"), Axioma homepage (invalid URL), Bloomberg portfolio analytics (blocked), hmmlearn repository (404).

Unverified:
- Numerical correctness of F01, F02, F08, F10, F12 and F14 (read, not run). Outputs are unverified until a manifest run and tests.
- The F04 conditional-return lag question (read only; needs a one-day lag test).
- The F05 half-life fix (derived from the formula; not run).
- Data counts and Fama-French and AQR date ranges (carried from 2026-11-06).
- Prices of Barra, Axioma and Bloomberg.
- Licences of Riskfolio-Lib, arch, hmmlearn, scikit-learn and statsmodels.
- Whether the sparkline file still exists after the frontend removal.
