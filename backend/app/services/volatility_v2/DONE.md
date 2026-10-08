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

Current: strict request-scoped `core/data_loader.py`, dedicated `core/har.py`, `core/garch.py`, `core/regimes.py`, `core/vrp.py`, `core/connectedness.py`, `core/currency.py` and `core/uploads.py`, rewritten Features 02–08, and golden/data regression tests. Splitting remaining estimators, covariance, connectedness, stress and budget code, plus updating the manifest/router, remains required.

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
| `features/feature_07.py` | Replaced with causal DCC/DCC-MIDAS, observed USD returns, explicit crisis conditioning and exact minimum torsion |
| `features/feature_08.py` | Replaced with observed historical replay, BIC-selected exact-date macro analogs, continuous constrained adversary, rotated Clayton conditional stress and real bootstrapped contagion |
| `core/performance.py` | Retained; unsafe fastmath disabled |
| Old audit/spec documents | Pending explicit supersession review; no deletion yet |

## Known limitations and remaining work

- Rebuild is incomplete. Feature 09, remaining Feature 01 proxy outputs, full contracts, uploads/jobs/export, frontend wiring/fake removal, and final verification are pending.
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

Feature 07 integration checks:

- Replaced the rolling-Pearson series advertised as DCC with the actual conditional correlation path. No asset dropping, missing-return zero filling, default DCC parameter substitution, or EWMA copy under a DCC label remains in this feature.
- DCC-MIDAS jointly estimates a, b and Beta(1, theta) decay. Its completed prior monthly standardized-residual correlations enter the daily DCC recursion. Convex matrix weighting preserves positive definiteness; the spec's unconstrained per-pair intercept/slope regressions do not guarantee a valid multivariate covariance. The next-observation label explicitly discloses its next-business-day calendar assumption, without inferring exchange holidays.
- Exact minimum torsion uses scipy polar/eigen decompositions in an alternating Procrustes/diagonal-scale solution. A separate two-asset angular minimization verifies the objective. Factor exposures conserve actual signed-weight portfolio variance. The review's proposed factor-square-root constraint is not the return transformation defining minimum torsion.
- Observed VIX and trailing USD-return volatility ranks define the hard crisis comparison. Missing VIX/insufficient history are excluded with counts. Separate Feature 04 causal HMM weights use a weighted mean and exclude nonconverged fits. Fisher tests use actual group sizes and Bonferroni correction; IID/serial-dependence limitations are explicit.
- Removed four replaced unused analytics functions after graph/rg consumer checks and all-feature/router import checks. The old DCC helper remains temporarily because Features 08/09 still call it; it must be removed when those consumers are rewritten.
- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_volatility_v2_*.py -q`: **32 passed**. Covers actual MIDAS likelihood recursion, completed-month targets, partial first-month warmup, causal forecasts, weighted centering, true torsion objective, and explicit optimizer failure.
- `ruff check backend/app/services/volatility_v2/core/{dcc,midas,torsion,crisis,covariance}.py backend/app/services/volatility_v2/features/feature_07.py backend/tests/test_volatility_v2_*.py`: passed.
- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -c 'from app.services.volatility_v2.registry import VOLATILITY_V2_FEATURES,get_runner; from app.api.volatility_v2 import router; print({"imported_features":[key for key in VOLATILITY_V2_FEATURES if callable(get_runner(key))],"routes":[r.path for r in router.routes]})'`: all nine feature imports and both registered routes passed.
- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -c 'from app.services.volatility_v2.registry import run_feature; r=run_feature("07", {"assets":["SPY","QQQ","TLT"],"lookback_days":1000,"min_train":252,"refit_interval":126,"midas_k":12,"hmm_restarts":1}); print({"status":r["status"],"dcc_days":len(r["charts"]["dcc_time_series"]),"midas_days":len(r["charts"]["dcc_midas_time_series"]),"methods":[x["method"] for x in r["tables"]["sample_ewma_lw_dcc_comparison"]],"warnings":r["meta"]["warnings"],"risk_fraction_sum":sum(x["fraction_total_risk"] for x in r["tables"]["portfolio_risk_attribution"]),"torsion_fraction_sum":sum(x["fraction_total_variance"] for x in r["tables"]["minimum_torsion_risk_attribution"])})'`: **ok**, 731 DCC and 611 MIDAS dates, six estimators, no warnings, both contribution sums equal one to floating-point tolerance.

References: [DCC-MIDAS component model](https://www.sciencedirect.com/science/article/pii/S0304407611000406), [minimum torsion reference implementation/documentation](https://reckziegel.github.io/uncorbets/). The monthly convex-target variant is deliberate and its parameters are estimated, not configured proxies.

Feature 08 stress step:

- Added focused `core/stress.py`, `core/analogs.py`, and `core/tails.py`; replaced hardcoded preset return/volatility shocks. All seven preset dates are defined; each is replayed only when the requested observed sample covers it. GFC/taper dates precede the main price dataset's observed coverage and are explicitly unavailable. The feature defaults to a 10,000-observation history request so available early episodes are not needlessly omitted; an explicit shorter user window is honored.
- Portfolio replay compounds USD simple daily returns. Its per-asset waterfall contributions use pre-return NAV and sum to the compounded portfolio return. Recovery times use observed NAV/volatility baseline crossings and disclose right censoring.
- Historical and analog scenarios use actual episode covariance and means. Parametric covariance applies explicitly supplied annual-decimal volatility shocks to current causal DCC correlations; return shocks are separately declared assumptions. This avoids propagating a normal-period correlation through a replay while claiming observed crisis correlation. Simulation uses a declared IID Gaussian simple-return model with daily variance equal to annual variance / annualization, and compounds the requested horizon. Return replay, modeled VaR/CVaR, and volatility-only risk-capital changes have separate labels/units.
- Macro changes use observed VIX, 10-year yield, credit, actual DX_Y_NYB dollar index and ^GSPC equity closes. No macro filling or dimension dropping. All eligible ending dates are searched; the query episode's overlaps are excluded for an observed-reference query. GLASSO uses a declared standardized Gaussian BIC grid, reports failed candidates, and applies its precision in that same standardized coordinate system. BIC is an IID approximation for overlapping windows, explicitly disclosed.
- The adversary is continuous: a descriptive OLS conditional-return surface is minimized exactly over the selected GLASSO ellipsoid. This is an exact linear-objective solution rather than a discrete historical grid advertised as a continuous optimizer. Tests compare its loss with 1,000 independent feasible points. A real-data smoke exposed covariance/precision inversion tolerance differences; the optimizer now solves using the actual constraint precision, guaranteeing the stated radius. No causal or held-out forecasting claim is made.
- Clayton fits full-sample rank pseudo-likelihood using statsmodels. Positive vol changes are rotated into the lower tail via negative vol changes; fitting a selected tail without selection normalization was removed. The conditional CDF is C(u,v)/v for a volatility-spike event. Configurable reverse horizons default to 30 sessions. Losses beyond empirical marginal support and absent qualifying shocks are unavailable, not extrapolated into invented stress magnitudes. The aggregate portfolio bivariate model preserves actual portfolio dependence instead of multiplying independent per-asset tail estimates.
- Contagion uses the declared OLS/EW VAR controls and source asset, with actual stationary residual-block bootstrap refits. One-source-residual-SD response units and their uncertainty are computed within each bootstrap refit. No exponential IRF fallback remains.
- Removed four obsolete tail/analog/adversarial/IRF helpers after graph + rg consumer checks; all nine feature imports and the API router still import successfully.
- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_volatility_v2_*.py -q`: **37 passed**, no warnings.
- `ruff check backend/app/services/volatility_v2/core/{stress,analogs,tails,connectedness}.py backend/app/services/volatility_v2/features/feature_08.py backend/tests/test_volatility_v2_*.py`: passed.
- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -c 'from app.services.volatility_v2.registry import run_feature; r=run_feature("08", {"assets":["SPY","QQQ","TLT"],"lookback_days":1000,"scenario":"liberation_day_2025","min_train":252,"refit_interval":126,"irf_bootstrap_reps":20,"irf_window":252,"var_max_lag":2,"mc_paths":5000}); print({"status":r["status"],"replay_days":len(r["charts"]["historical_stress_path"]),"analogs":len(r["tables"]["historical_analog_comparison"]),"analog_bands":len(r["charts"]["analog_volatility_bands"]),"adversarial_distance_squared":r["tables"]["adversarial_scenario"][0]["distance_squared_from_query"],"irf_bands":len(r["charts"]["contagion_impulse_response"]),"warnings":r["meta"]["warnings"]})'`: **ok**, 42 replay sessions, 10 analogs, 90 observed analog volatility bands, adversarial distance squared 4, 12 IRF bands, no warnings.

Library references: [statsmodels Clayton copula](https://www.statsmodels.org/stable/generated/statsmodels.distributions.copula.api.ClaytonCopula.html), [sklearn GraphicalLasso](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.GraphicalLasso.html).

## Feature 09 allocation and execution step (2026-10-08)

- Replaced the budget wrapper with dedicated `allocation.py`, `budget_forecasts.py`, `execution.py` and `liquidity.py`. Fixed, causal probability-weighted regime and actual BTZ Kelly targets use forecast information available before each replay return. EWMA, expanding GARCH with declared rolling correlation, and genuine DCC are distinct selectable sources.
- Risk budgeting solves the convex log-barrier problem. The second step preserves net exposure and achieved variance while minimizing Euler-budget deviation. The review's original minimum-adjustment quadratic objective had zero adjustment as a feasible optimum and could not align budgets; this corrected objective is documented in the response. Higher-dimensional local optimization does not claim a global optimum.
- Replay maintains drifting holdings and solves self-financing transaction costs against post-cost NAV. One-way turnover includes cash; traded asset notional is separate. Temporary-impact comparisons require observed USD ADV and declared volume units. The one-day linear Almgren–Chriss temporary-impact coefficient is a user assumption, not an estimated execution model. No permanent impact or short borrow fee is claimed.
- Kelly uses observed matching IV, integrated physical variance, and expanding BTZ return predictions trained only on matured labels. Negative estimated edge yields cash. Matching IV, 252-session annualization and USD denomination are required for this leg; unsupported legs report why they are unavailable.
- Removed `dcc_garch_mle`, `two_step_rebalance`, `almgren_chriss_costs` and `kelly_vol_target` from analytics after graph and repository reference checks confirmed no remaining callers. All nine feature imports and registered API routes passed afterward.

Verified commands:

- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_volatility_v2_math.py -q`: **36 passed**.
- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_volatility_v2_*.py -q`: **44 passed**.
- `ruff check backend/app/services/volatility_v2/core/allocation.py backend/app/services/volatility_v2/core/budget_forecasts.py backend/app/services/volatility_v2/core/execution.py backend/app/services/volatility_v2/core/liquidity.py backend/app/services/volatility_v2/features/feature_09.py backend/tests/test_volatility_v2_math.py`: passed.
- Real Feature 09 SPY/QQQ/TLT, 700 sessions, 252 training observations, 126 refit interval, one HMM restart: **ok**, 364 common replay dates, both cost models, no warnings.
- Real Feature 09 `^GSPC`, EWMA, Kelly, 650 sessions, 120 BTZ training observations, 63 refit interval: **warning** solely because index ADV is unavailable; Kelly was produced from observed IV with 389 replay dates and target 0.35451755355165415.

The complete review is still in progress: Feature 01, remaining estimator controls, contracts/jobs, frontend wiring/fake removal and final verification remain.

## Feature 01 diagnostic correction (2026-10-08)

- Moved estimator comparison diagnostics into `core/estimator_diagnostics.py`. DM forecasts and targets now share the selected h-session horizon and annualization. Comparisons stay within each asset and use statsmodels HAC inference; insufficient or zero-variance loss differences are unavailable rather than fictitious zero test statistics.
- Removed the daily Bandi–Russell proxy. Covariance of squared returns has fourth-power return units and cannot be subtracted from daily variance. Daily and coarse hourly OHLC cannot identify genuine optimal tick-noise sampling.
- Range correlations now use actual pairwise observed dates, without stale fill. Pearson is default; the old uncentered normalization is available only under the explicit `uncentered_cosine` name.
- Replaced falsely identified empirical sampling-efficiency/fat-tail diagnostics with an explicitly named temporal variance ratio. Rolling-estimate dispersion combines changing volatility and sampling noise and cannot identify either sampling efficiency or fat tails.
- Connected the actual canonical hourly panel through `core/intraday.py`. Exact symbols, declared input/session timezones, consecutive-hour checks and explicit incomplete-day exclusion are required. Returned hourly close variation and bipower variation exclude opening/overnight returns. Their positive difference is descriptive, not a statistical jump identification. Unknown assets are never substituted with another hourly instrument.
- The replaced four analytics helpers were removed after graph/repository references were checked and Feature 01 imports updated. All nine feature imports and API route checks still pass.

Checks:

- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_volatility_v2_*.py -q`: **47 passed**. Added horizon-unit invariance, cross-asset isolation, observed-date range correlation and hourly no-gap/no-overnight regression tests.
- `ruff check backend/app/services/volatility_v2/core/intraday.py backend/app/services/volatility_v2/core/estimator_diagnostics.py backend/app/services/volatility_v2/features/feature_01.py backend/tests/test_volatility_v2_math.py`: passed.
- Real Feature 01 SPY/QQQ, 400 sessions: **ok**, 25 actual DM comparisons and explicit unsupported-output reasons.
- Real Feature 01 `^GSPC`, 400 sessions, hourly input timezone UTC and session timezone America/New_York: **ok**, 372 observed hourly variation dates, ending 2026-02-20.

Contracts/API/jobs, remaining estimator controls, frontend transport/fake deletion and completion gates remain in progress.

## API lifecycle step (2026-10-08)

- Added own-universe symbol search, validated size-capped IV upload and actual JSON/CSV-table export routes. Existing flat runs remain compatible; mixed/invalid payload envelopes fail. Unknown feature ids return 404 and invalid data/types return 422.
- Added module-local durable Studio JobStore routes for enqueue/status/cancel, atomic separate result files and bounded workers. Jobs verify source versions before and after computation, including the chosen IV upload and optional hourly panel. Cancellation suppresses publication and clearly states that active estimator computation finishes in background. Progress reports the actual estimation stage without fabricated percentages.
- A constant-price job regression exposed a false agreement-zero fallback and alert formatting crash. Zero-dispersion correlations now remain unavailable and no false disagreement alert is produced. DM losses mask nonpositive forecasts before taking logarithms.
- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_volatility_v2_*.py -q`: **49 passed** after the final logarithm adjustment. The environment's FastAPI TestClient emits a Starlette/httpx deprecation warning; it is not an application failure.
- `ruff check backend/app/api/volatility_v2.py backend/tests/test_volatility_v2_data_and_api.py`: passed.

The feature manifest and early validation are still being completed; these API additions do not close the review.
