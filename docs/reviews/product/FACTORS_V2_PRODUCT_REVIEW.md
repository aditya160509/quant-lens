# Factors product review: factor lab, redone against the feature rule

Redone 2026-11-09 against the feature rule in `docs/plans/PLAN.md` section 1b. It replaces the 2026-11-06 version. Code claims were read in `backend/app/services/factors_v2/` on this date (registry, `core/contracts.py`, `features/inputs.py`, `core/alerts.py`, features 06, 11, 13). Data counts are carried from the 2026-11-06 measurement and not re-measured. Nothing was run: no tests, no manifest call, no servers. The frontend was removed on 2026-11-06 (PLAN line 77), so there is no UI to judge.

## Contents
1. Verdict
2. What is real and what is hollow
3. Parity with paid tools
4. Feature table: keep, build, later, cut
5. Our own ideas: freedom and customisation
6. Open-source picks
7. Build checklist
8. Sources and unverified

---

## 1. Verdict

Factors is a factor lab that prints its own limits. It is not a Barra replacement. The backend is a real, wide estimator set (14 features, `FEATURE_CONTRACTS` in `core/contracts.py`); the gap is the UI, the generic input help text, and three features whose names promise more than the code does (F06 crowding, F11 hedging, F13 "live").

- **Keep** 11 features, merge F03 and F06 into hosts as tabs (F12 stays as its own DNA tab), and fold F08/F10/F11 into the shared covariance and construction engines (merge map decisions 3 and 7).
- **Build** the five-page workspace from the manifest, the data banner, the alert scoreboard and the Validate hand-off.
- **Later**: true crowding data, real-time monitoring, non-US factor sets.
- **Cut**: nothing in the backend; cut UI names that over-claim.

---

## 2. What is real and what is hollow

| Area | Real (read in code) | Hollow or over-named |
|---|---|---|
| Manifest | `feature_manifest()` returns id, title, inputs, outputs per feature, built from `features/inputs.py` and `OUTPUT_KEYS` | Every input's `help` string is the same sentence ("Applied by the backend; invalid or unsupported values fail explicitly", or "See module DONE.md..."). A form built from the manifest has no per-field help |
| Run path | `prepare_payload` validates, resolves uploads, defaults `as_of_date` to the latest SPY date and errors if SPY is missing; `run_feature` stamps `source_versions` into `meta` | None found |
| F01 valuation spread | Spread, percentile series, crisis anchors, expected-return regression in `OUTPUT_KEYS` | Output quality unverified |
| F02 exposure | Characteristic and return-regression exposures, rolling snapshots, active exposure vs `benchmark_holdings` | Unverified |
| F03 attribution | Takes supplied `factor_exposures`; returns contribution and reconciliation tables | It accounts for exposures the user types in; it does not estimate them |
| F04 regimes | Imports `GaussianHMM` and `GaussianMixture`; docstring says training-only fit with causal filtered holdout probabilities | Unverified beyond the docstring |
| F05 decay | IC by horizon, decay model fits, `arch` stationary bootstrap for half-life interval | Unverified |
| F06 "crowding" | Top-quintile HHI, sector HHI, 63-day volatility percentile, Roll implied spread from price changes | **No ownership, short-interest, 13F or flow data.** It is a concentration and liquidity proxy, not crowding. Rename or label |
| F07 backtest | Shared `core/backtest.py`; costs, borrow, turnover, Monte Carlo bands, quintile and decile monotonicity | Unverified |
| F08 covariance | Methods `ledoit_wolf`, `sample`, `ewma`, `dcc_ewma`; stress VIX, pair correlation, risk decomposition | DCC overlaps Volatility (decision 14) |
| F09 capacity | Capacity curve, slippage by AUM, sensitivity; Almgren-style impact constants in code | Impact constants are fixed in code (`_ALMGREN_ETA = 0.1`); not calibrated to data |
| F10 optimiser | Risk aversion, robust penalty, Black-Litterman inputs, turnover and tracking-error limits | Unverified |
| F11 stress | VAR impulse responses, reverse stress, historical analog, multi-scenario | `hedging_recommendation` returns the text "No executable hedge instrument mapping supplied" in one branch (`feature_11.py:153`). The output name over-promises |
| F12 DNA | Purity regression, concentration, comparison factors | Unverified |
| F13 "live" monitoring | Cross-sectional IC drift, CUSUM structural-break test, alert events in SQLite with idempotent ids (`core/alerts.py`) | The module docstring says "no delivery claim". Events are in-app state changes (triggered, recovered); there is no scheduler, no delivery and no matured hit rate. Not live |
| F14 report | ReportLab PDF with section order, fund name, disclaimer, `aima_ddq_cross_reference` output; docstring says section failures are explicit | Unverified; CSV export not seen |
| Data guards | Statements lagged 90 days (`fundamental_lag_days=90` in `core/panel.py`); unknown IC stays unknown (alerts skip null `ic_z_score`) | Survivorship and 2021-only statement history remain (carried measurement) |

---

## 3. Parity with paid tools

Searches run 2026-11-09 (snippets only; no page fetched).

| Tool | What the money buys | Where we stand |
|---|---|---|
| Portfolio123 | Screen, rank, backtest; 20 years of US, Canada, Europe data; custom ranking systems; $84 per month for custom rankings and 10Y backtests, $125 per month for 15Y (fool.com, Dec 2024, snippet; vendor page lists $84 per month, $1,000 per year for Professional) | We lack stored custom ranking systems and long point-in-time fundamentals. We have IC, decay and capacity that the snippets do not mention |
| Bloomberg PORT | Four scenario types: factor-based, full-valuation, macro, climate; fundamental risk models with tracking error | F11 covers factor-based only. Full revaluation, macro and climate are not built |
| Axioma, MSCI Barra | Equity factor risk models, risk attribution, scenario testing, daily updates | We have a factor-return covariance (F08). We have no stock-level risk model with specific risk. Not a replacement |
| Stock Rover, Koyfin, Finviz, TradingView | Screens and metrics; no factor backtest or capacity (prior review, partly snippet) | We lead on tests and honesty |
| Alphalens, pyfolio | Free IC, quantile and tear sheets | F05, F07 and F14 match or exceed this |

Parity gaps worth closing: stored ranking systems, benchmark-relative tear sheet, scheduled monitors. Parity we should not chase: licensed risk-model data, full revaluation.

---

## 4. Feature table

| ID | Feature | Call | Reason |
|---|---|---|---|
| F01 | Valuation spread | Keep, page Value and exposure | Clear decision value; crisis anchors give context |
| F02 | Exposure decomposition | Keep, page Value and exposure | Core holdings view; needs holdings beside benchmark |
| F03 | Return attribution | Keep as tab of F02 | Duplicates the exposure workflow; uses typed exposures |
| F04 | Regime analysis | Keep, page Regime and timing | Regime kernel moves to Volatility (decision 7); F04 calls it |
| F05 | Alpha decay | Keep, page Regime and timing | Half-life with interval; add the published decay warning |
| F06 | Crowding | Keep as tab of F05, relabel "concentration and liquidity" | Proxy only; the name over-claims |
| F07 | Backtest engine | Keep, page Test and capacity | Execution kernel shared (step 5) |
| F08 | Covariance | Keep as lens on the shared covariance engine | Portfolio owns covariance (decision 3) |
| F09 | Capacity | Keep, page Test and capacity | Needs calibrated impact and break-even cost |
| F10 | Optimiser | Keep as lens on shared construction | One engine with Portfolio |
| F11 | Stress | Keep as lens; **later** for real hedges | Hedge output is empty without an instrument map |
| F12 | DNA | Keep as tab of F02 | Radar of exposures; same data |
| F13 | Monitor | Build up: scheduler, delivery, matured hit rate | Today it is state tracking only |
| F14 | Report | Keep as export plumbing, with CSV | PDF exists; CSV to build |

Later: stock-level specific risk, ownership-based crowding, full revaluation stress, non-US factor sets. Cut: the `hedging_recommendation` label until an instrument map exists.

---

## 5. Our own ideas: freedom and customisation

1. **Bring your own factor.** `factor` is a fixed list of 10 in `inputs.py`. Add an upload or formula slot so any column becomes a factor, flowing through F01, F05, F07 unchanged. Honest limit: it joins the trial count.
2. **Choose your own factor model.** `factor_model` offers ff3, ff5, ff5_mom, carhart, capm. Let the user pick any subset of factors and a custom benchmark.
3. **Every input exposed, with real help.** Generate field help from the estimator docs, not the shared sentence.
4. **Trial ledger on every run.** Count each changed input as a trial and feed the deflated Sharpe, shown beside the result (decision 4).
5. **Saved recipes.** Save a full payload as a named recipe and re-run it; shareable as a file.
6. **Limits banner as a first-class object.** Survivorship, 90-day lag, 2021+ statements, printed on every result and in the PDF.
7. **Compare any two runs** side by side, difference highlighted.
8. **Export everything** as CSV/JSON with the payload and `source_versions` attached.

---

## 6. Open-source picks

From the 2026-11-09 search (snippets):
- **alphalens-reloaded** (stefan-jansen, github): IC and quantile analysis; use as a cross-check for F05 and F07, not a dependency.
- **skfolio** (skfolio.org): optimisation, factor models and risk on scikit-learn; candidate for F10 cross-checks and the shared construction engine. Licence not seen in the snippet; BSD-3 per the prior review (unverified).
- **Riskfolio-Lib**: BSD-3 per the prior review (unverified); alternative for Black-Litterman and CVaR.
- **arch**: already used (`arch.bootstrap`) in F05.
- **hmmlearn, scikit-learn, statsmodels**: already imported in F04, F11, F13.

Pick: keep the current stack; add skfolio only if the shared optimiser needs it.

---

## 7. Build checklist (E easy, M medium, H hard)

- [ ] Remove the sine sparkline (`customPagePrimitives.jsx`, carried from prior review, not re-read) E
- [ ] Write per-field help in `features/inputs.py` replacing the shared sentence E
- [ ] Rename F06 output labels and F11 hedge label to what the code does E
- [ ] Data banner on every result and in the PDF M
- [ ] `/factors` workspace from `GET /features`, five pages M
- [ ] Value and exposure page (F01, F02, tabs F03, F12) M
- [ ] Regime and timing page (F04, F05, tab F06), regime kernel from Volatility M
- [ ] Test and capacity page (F07, F09), execution kernel M
- [ ] Risk and construction page (F08, F10, F11) on shared engines H
- [ ] Monitor page: scheduler, delivery and matured hit rate for F13 H
- [ ] Validate hand-off with trial count M
- [ ] CSV export beside PDF E
- [ ] Custom factor upload (idea 1) H
- [ ] Saved recipes and run compare (ideas 5, 7) M
- [ ] Shared loader for Factors; FF date-range check; AQR verification M
- [ ] Ship, tag `factors-v1` E

---

## 8. Sources and unverified

Searches (TinyFish, 2026-11-09, snippets only): Portfolio123 (portfolio123.com, fool.com), alphalens-reloaded and skfolio (github.com, skfolio.org), Bloomberg PORT (professional.bloomberg.com), Axioma (simcorp.com), Barra (msci.com).

Unverified:
- Output correctness of every feature; no test or manifest run in this pass.
- Data counts and Fama-French/AQR date ranges (carried from 2026-11-06).
- Prices of Barra, Axioma, Bloomberg (not found this pass).
- Licences of skfolio and Riskfolio-Lib.
- Whether the sparkline file still exists after the frontend removal.
- F14 CSV export and F02 to F05, F07, F08, F10, F12 internals (only headers and docstrings read).
