# Volatility V2 rebuild

**Status: in progress. This is a progress record, not a completion claim.**
Frontend design remains reserved for Claude. Other V2 modules and V1 are outside this rebuild.

## Completed implementation steps

1. Strict price loading rejects unknown assets, empty explicit selections, invalid OHLC, and duplicate ticker/date observations. It reads the main observed market parquet using symbol/date predicates. `as_of_date` applies before lookback truncation; lookback is an exact count of observed sessions per asset.
2. Bounded price and macro caches include file path, nanosecond modification time, and size. Calculation fingerprints include all observed values and dates. No unknown-symbol substitution with SPY remains in `load_assets`.
3. Explicit weight strings accept JSON or `SYMBOL:value` pairs. Invalid weights fail. User exposure is preserved rather than silently gross-normalized.
4. Yang–Zhang uses overnight sample variance plus k times open-to-close sample variance plus (1-k) times Rogers–Satchell variance. Complete rolling windows are required. Crypto/FX suffixes no longer silently substitute Rogers–Satchell. Daily bar boundaries define the observed sessions; exchange session metadata remains to be completed/disclosed.
5. Numba `fastmath` is disabled to preserve missing-value checks. Pandas extension dtype compatibility in response serialization is fixed.
6. HAR lives in `core/har.py`. Every forecast at t uses only origins s whose response at s+h has matured by t. Coefficients are refitted on an expanding schedule. All requested horizons receive held-out forecasts and accuracy. OOS R² compares against the contemporaneous training mean. Missing predictors are neither filled with zero nor backfilled. LHAR transforms both predictors and target. OLS/HAC and prediction intervals use statsmodels.
7. MCS uses `arch.bootstrap.MCS` on aligned held-out losses. Historical combination weights derived from the whole evaluation sample were removed. HAR-X, daily “intraday jump” variants, and fabricated contribution coefficients were removed; their reasons appear in the feature response.
8. GARCH lives in `core/garch.py`. All five arch families and four innovation distributions can be evaluated with expanding past-only fits and one-step held-out forecasts. PIT and VaR use the fitted distribution at each refit. QLIKE and RMSE use observed squared daily returns, explicitly identified as noisy variance observations. Failed fits are reported and make the result a warning. Pairwise DM uses actual held-out loss differences. Kupiec, independence, and conditional coverage likelihood-ratio diagnostics are distinct; unidentifiable independence tests are unavailable.
9. GARCH term structure uses the fitted arch model recursion and innovation simulator. It describes terminal-day conditional variance, not an observed options surface. Synthetic option surfaces, fake FIGARCH d paths, chunk-dispersion “Nyblom”, unscored Realized-GARCH, and rolling breach-count “duration tests” were removed from Feature 02.

10. Feature 04 now uses causal HMM filtering: every refit standardizes and learns only through the preceding observation. K selection uses the initial training sample and remains fixed so historical labels do not change when future data arrive. The SJM alternates Viterbi paths and centroid updates, then emits causal hard states rather than uncalibrated probabilities. Brier-weighted self-scoring ensembles, fake macro probabilities and future smoothing were removed.
11. Regime duration Weibull MLE includes an ongoing spell as right-censored and excludes the first left-censored spell. Insufficient completed spells produce an explicit unavailable reason. Probability-weighted transition matrices and stable timestamped probability-change alerts replace the old latest-max alert.
12. Feature 05 requires observed matching IV. Local VIX is usable for its S&P 500 index benchmark (`^GSPC`), not arbitrary stocks, ETFs or non-US indices. Validated user IV CSVs enable other assets. Exact dates are joined without stale fill. VIX3M/VIX6M are observed or explicitly unavailable, never multiplied versions of VIX.
13. Physical GARCH forecasts average all next-h daily conditional variances, rather than multiplying a terminal variance. Direct log-HAR forecasts integrated future variance using only matured labels. Three separate physical methods, daily component identities, display modes, multi-asset comparisons, and all selected return horizons are implemented.
14. BTZ inference uses actual monthly variance VRP, causal Feature 04 probability weights, statsmodels Newey–West regression and expanding OOS forecasts. Hodrick (1992) 1B uses daily demeaned returns times lagged predictor sums, with correct sandwich scaling and an explicit restriction to testing no predictability. Exact discrete AR(1) half-life replaces the invalid continuous-time units in the spec.

15. Feature 06 now computes a rolling fit for every complete aligned observation by default, including the final observation. OLS VAR uses statsmodels common-range BIC over positive lag orders. EW VAR uses decay-weighted statsmodels WLS at an explicitly declared fixed lag with effective residual degrees of freedom; it does not mislabel an ad hoc weighted score as BIC. Every rolling model uses the chosen weighting and inputs.
16. Generalized FEVD uses the Pesaran–Shin formula and statsmodels MA coefficients. Spillover attribution excludes own variance. Historical percentiles compare only earlier observed readings. Timestamped threshold crossings, full daily attribution histories and optional full network matrices support Claude's time-lapse frontend without inventing visuals.
17. Barunik–Krehlik uses direct VAR transfer-function inversion and full-spectrum normalization. Frequency contributions from disjoint bands add to the total; within-band connectedness is reported separately. Unstable VARs explicitly disable the infinite-horizon spectrum. Macro-conditioned CoR is unavailable without release vintages; the returned alternative is explicitly named autoregressive quantile CoR.
18. IRF bands use `arch.bootstrap.StationaryBootstrap` residual vectors and refit the declared VAR estimator per replication. Failures are counted and insufficient successful replications produce an unavailable reason.
19. `core/currency.py` computes USD portfolio returns with explicitly known or user-declared quote currencies and observed canonical FX on exact dates. It rejects unknown denomination, missing rates and currency suffix guesses. Price-adjustment provenance is disclosed; no total-return claim is made. The FX file is included in source versions.

## Architecture before and current state

Before: a 1,495-line analytics file, nine feature wrappers, aspirational output contracts, a synchronous router, and disconnected frontend workbench.

Current: strict request-scoped `core/data_loader.py`, dedicated `core/har.py`, `core/garch.py`, `core/regimes.py`, `core/vrp.py`, `core/connectedness.py`, `core/currency.py` and `core/uploads.py`, rewritten Features 02–06, and golden/data regression tests. Splitting remaining estimators, covariance, connectedness, stress and budget code, plus updating the manifest/router, remains required.

## Old-file fate table

| File | Fate |
|---|---|
| `core/data_loader.py` | Replaced in place; public loader entry points preserved, invalid inputs now fail |
| `core/analytics.py` | Still used; HAR/GARCH functions are being moved to focused modules; obsolete functions remain pending verified removal |
| `features/feature_02.py` | Replaced with true held-out GARCH suite |
| `features/feature_03.py` | Replaced with true expanding HAR forecasts |
| `features/feature_04.py` | Replaced with causal HMM filtering, genuine hard SJM states and censored durations |
| `features/feature_05.py` | Replaced with observed matching IV and actual integrated physical forecasts |
| `features/feature_06.py` | Replaced with daily, consistently weighted library VAR estimates and correctly normalized frequency shares |
| `core/performance.py` | Retained; unsafe fastmath disabled |
| Old audit/spec documents | Pending explicit supersession review; no deletion yet |

## Known limitations and remaining work

- Rebuild is incomplete. Features 07–09, remaining Feature 01 proxy outputs, full contracts, uploads/jobs/export, frontend wiring/fake removal, and final verification are pending.
- Macro history contains observations but no release-vintage guarantee. HAR-X is unavailable rather than silently imputing macro predictors.
- Daily OHLC alone does not support intraday bipower jump identification or genuine Bandi–Russell noise correction. The repo has hourly panels for indices and selected assets, verified directly during this pass; their available coverage still needs to be connected before marking sampled-realized-measure outputs supported. SPY has no hourly series in the canonical hourly panel. No blanket claim that the repo lacks intraday data is made.
- The current GARCH winner is retrospective selection over a held-out evaluation window. Its historical diagnostics are post-selection and do not represent a tradable winner-switching strategy.
- PIT KS diagnostics do not correct for serial dependence or model selection.
- HAR confidence intervals are conditional OLS prediction intervals, transformed for LHAR; they do not incorporate model selection uncertainty.
- Source versions use filesystem metadata, not cryptographic content checksums. Calculations use full-content fingerprints.
- Historical delistings, adjusted-price conventions, mixed-currency handling and macro source availability still require the remaining data audit.

## Checks run so far

- `cd backend && PYTHONPATH=. /tmp/pca-v2-check-env/bin/python -m pytest tests/test_volatility_v2_*.py -q`: **18 passed**.
- `ruff check backend/app/services/volatility_v2/core/garch.py backend/app/services/volatility_v2/core/har.py backend/app/services/volatility_v2/features/feature_02.py backend/app/services/volatility_v2/features/feature_03.py backend/tests/test_volatility_v2_*.py`: passed.
- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python - <<'PY' ... PY`: real Feature 01 run with SPY, 400 sessions, `as_of_date=2025-01-31`, returned `ok` and last chart date exactly 2025-01-31.
- Same Python entry point: real Feature 03 run with SPY/QQQ, 450 sessions, horizons 1/5, 120 training observations, 100 MCS repetitions: `ok`, eight model/horizon accuracy rows.
- Same Python entry point: real Feature 02 SPY, 400 sessions, GARCH/Student-t, 252 minimum training observations, 63 evaluation days, 200 simulations, horizons 1/5/21: `ok`, 63 held-out observations, finite likelihood-ratio diagnostics.
- No Jest, full frontend lint/build, or browser completion is claimed yet.

Yang–Zhang formula reference: [TTR volatility documentation](https://mirror.las.iastate.edu/CRAN/web/packages/TTR/TTR.pdf). The review’s swapped k/(1-k) formula was corrected against the estimator definition.

Additional checks in the regime/VRP step:

- `cd backend && PYTHONPATH=. /tmp/pca-v2-check-env/bin/python -m pytest tests/test_volatility_v2_*.py -q`: **18 passed**. New tests cover causal filtering, cache mutation, right censoring, transition crossings, integrated variance versus arch, Hodrick covariance versus independent lagged-score construction, uploaded IV validation and sandbox traversal, and incompatible IV benchmarks.
- `ruff check backend/app/services/volatility_v2/core/regimes.py backend/app/services/volatility_v2/core/vrp.py backend/app/services/volatility_v2/core/uploads.py backend/app/services/volatility_v2/features/feature_04.py backend/app/services/volatility_v2/features/feature_05.py backend/tests/test_volatility_v2_*.py`: passed.
- Real Feature 04 SPY, 700 sessions, 252 training observations, one HMM restart, three states: `ok`, 365 causal timeline rows and 14 transition alerts.
- Real Feature 05 `^GSPC`, 1,000 sessions, 120 training observations, refits every 42 observations, horizons 21/63, one HMM restart: `warning` because a selected HMM fit did not meet convergence. All three maturity IVs were observed at 2026-02-20; no synthetic values were used.

Hodrick 1B reference: [Federal Reserve FEDS 2009-27, Section 2](https://www.federalreserve.gov/pubs/feds/2009/200927/index.html), which distinguishes this null-only covariance from Hansen–Hodrick HAC and general coefficient confidence intervals.

Connectedness/currency step checks:

- `cd backend && PYTHONPATH=. /tmp/pca-v2-check-env/bin/python -m pytest tests/test_volatility_v2_*.py -q`: **23 passed**. Tests add generalized FEVD golden values, permutation invariance, full-spectrum additivity, statsmodels VAR agreement, causal daily updates, EW method preservation, seeded bootstrap refits, and exact-date FX conversion.
- `ruff check backend/app/services/volatility_v2/core/connectedness.py backend/app/services/volatility_v2/core/currency.py backend/app/services/volatility_v2/features/feature_06.py backend/tests/test_volatility_v2_*.py`: passed.
- Real Feature 06 SPY/QQQ/TLT, 500 price observations, 126-observation rolling windows: OLS and EW returned `ok`, each with 338 daily connectedness readings and 338 requested network snapshots. OLS with 20 bootstrap replications returned 36 source/target/horizon bands.

Frequency decomposition reference: [Barunik and Krehlik, spectral connectedness definitions](https://arxiv.org/html/1507.01729). statsmodels supplies estimation and MA primitives; the short generalized/spectral aggregation is implemented directly because its built-in FEVD is Cholesky-orthogonalized and is not the required ordering-invariant estimator.

Covariance/DCC core step, feature wiring still pending:

- Added `core/covariance.py`: sklearn Ledoit–Wolf and OAS estimates, explicit complete-observation checks, weighted-mean EW covariance, Euler marginal/component volatility and ordered pairwise variance attribution. No missing return is replaced by zero.
- Added `core/dcc.py`: past-only arch GARCH/Student-t marginal forecasts and constrained two-stage DCC maximum likelihood, with multiple optimization starts and explicit failure. Historical covariance uses information through the previous observation; next-day covariance uses the final observed return. Correlation diagonals are exactly one, without the old 0.999 diagonal clipping.
- These cores are not yet exposed by Feature 07. DCC-MIDAS, crisis conditioning, minimum torsion, and complete feature wiring remain pending; the existing feature is not declared repaired.
- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_volatility_v2_math.py -q`: **18 passed**. New tests compare shrinkage estimates directly to sklearn, check signed-weight risk conservation, and mutate future returns to verify DCC causality and positive definiteness.
- `ruff check backend/app/services/volatility_v2/core/dcc.py backend/app/services/volatility_v2/core/covariance.py`: passed.
