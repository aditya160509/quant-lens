# Factors V2 backend rebuild

Updated: 2026-10-07. Scope: Factors V2 only, with frontend request/job wiring and deletion of fabricated hub results. Frontend forms, renderers, design, and layout remain Claude-owned. This is a supported-backend completion record, not a claim that every original speculative feature or the frontend has been delivered.

## Architecture before and after

Before: a 797-line shared analytics module, duplicated feature mathematics, three drifting input/output descriptions, raw frontend requests that lost their inputs, synchronous batches, latest-snapshot fundamentals in historical sorts, fabricated valuation fillers and classifier labels, and weak/unbounded caches.

After: lazy `registry.py` dispatch; authoritative, validated feature `INPUTS` and `OUTPUTS` in `features/inputs.py`; 14 feature entrypoints; focused core modules for dated panels, statistics, covariance, stock execution, capacity, optimization, uploads, and alerts. `analytics.py` is a compatibility export surface, with no second computation implementation. Existing descriptive wrapper modules continue importing the same feature `run` functions. Tests use the existing backend test directory, rather than a second testing infrastructure.

The mounted prefix remains `/api/labs/factors/v2`. `GET /features` is the backend contract. Feature requests accept exactly `{ "payload": {...} }`; unknown fields and invalid values fail explicitly. Unknown features/jobs return 404; input failures return 422. Heavy UI runs use `/feature/{id}/jobs`, status polling, and the existing Studio JobStore. Explicit batch payloads are asynchronous. Cancellation suppresses publication; running numerical code finishes in its worker. Results publish through atomic JSON replacement. Jobs fail if source files change between queueing and publication. This is local durable storage, not a distributed task queue.

## Data rules

- Primary prices must exist at `backend/data/market_universe.parquet`. No paper/export/demo fallback.
- Explicit ticker lists are validated in full, never partly replaced by a default list. Explicit universes exceeding the limit fail.
- Automatic universes require declared currencies and exact-date USD quotes; no mixed-native-currency notional ranking. Selection is repeated at every formation date.
- Every reader applies a single effective cutoff, including an earlier `end_date`. Source caches are bounded and keyed by file paths, nanosecond modification times, sizes, and cutoff. Raw caches are built outside request scope to prevent a first historical request poisoning later runs.
- Annual statements must satisfy `reportDate + 90 days <= formation_date`. Latest vendor market caps and valuation ratios are excluded from historical characteristics. The lag is an assumption, not verified filing-vintage evidence.
- Value uses contemporaneous observed quote, lagged shares/equity/earnings, declared compatible statement/quote currencies, and explicit share units. Unavailable fields stay missing. Growth/investment use observed annual statement changes.
- Momentum uses actual skipped-month endpoints; volatility and IC retain missing observations. IC labels become available only at the realized horizon maturity. No return-zero imputation or price forward fill.
- Currency conversion uses `canonical/fx_daily.parquet` and direct/inverse pairs on the exact observed date. GBp/ZAc minor units are explicit. Missing FX or currency declarations remain unavailable. USD metadata enables USD scoring and return labels; explicitly selected price-only screens without metadata report native quote characteristics. Stock execution and stock regressions require USD conversion.
- Stock factor regressions subtract observed RF before fitting USD factor risk premia.
- Fama–French CSV units are explicitly percent-to-decimal. AQR is opt-in and fails when the requested local region is unavailable; no USA substitution.
- Job/report source versions are exposed. Source metadata is provenance, not proof of adjustment or survivorship completeness.

## Feature and estimator disposition

| Feature | Supported computation | Removed or unavailable claims |
|---|---|---|
| F01 | Actual dated characteristic spreads, causal historical percentiles, additive sector contributions, prior-only crisis anchors; matched stock-strategy forward-return OLS with Newey–West HAC and mean-forecast intervals when sufficiently mature | 50/-0.002/0.18 fillers, FF returns standing in for valuation history, future nearest anchors, automatic economic cheapness claims |
| F02 | Actual holdings, per-stock excess-return OLS and 95% t intervals, weighted portfolio beta, observed characteristic exposures, supplied benchmark active characteristic exposure, sector-neutral characteristic option, supplied dated holding snapshots | Arbitrary first-30 portfolio, zero-imputed characteristics, uncalibrated beta-minus-z-score surprise |
| F03 | Supplied factor-exposure daily P&L contributions, calendar contribution buckets, reconciled additive totals, frequency-aware IR | Latest-stock Brinson proxy, autocorrelation carryover, invented selection residual; no claimed observed portfolio performance without supplied history |
| F04 | Training-only scaling and Gaussian HMM, causal forward filtering on holdout, requested 2–6 states, optional training-only GMM, prior exact-day VIX/yield rules | Full-sample smoothing, future-volatility fusion weights, binary/three-state relabelling, unsupported macro-release regime names |
| F05 | Formation-date cross-sectional Spearman IC at mature horizons, empirical ICIR, arch stationary-block mean intervals, fitted decay, joint horizon-block half-life refits where sufficient | Return persistence as IC, scaled sector copies, normal-width bootstrap fallback, negative/growing curves called positive half-lives, assumed-volatility optimal rebalance |
| F06 | Actual stock/sector HHI, published factor persistence, Roll price-change spread where mathematically defined, observed volatility percentile | Institutional crowding score, Bayesian crash probability and uncalibrated 0–100 composite; volatility is explicitly identified as volatility |
| F07 | Date-by-date stock re-ranking, next-close execution, drifted traded-notional fees solved self-consistently, borrow costs, observed quintile/decile portfolios, statistics, compounded yearly returns, genuine arch stationary-bootstrap paths | Published factors called a stock backtest, interpolated deciles, duplicate capacity formula, fake adaptive walk-forward optimization, ignored daily refit/MC caps |
| F08 | Sample, EWMA, Ledoit–Wolf covariance; explicit fixed-parameter EWMA-standardized DCC recursion; exact-prior-VIX normal/crisis histories; measured calendar presets; risk decomposition on supplied weights | DCC called GARCH/MLE, silent estimator substitution, 1260-row cap, identity/preset crisis matrices, equal-weight solver fallback |
| F09 | Shared per-security cost sweep on observed USD ADV/volatility, same stock-backtest gross return, declared square-root impact assumptions, declared turnover, recomputed frequency/participation scenarios, full-book liquidation and measured crossing | Guessed ADV, hand-scaled sensitivities, assumed half-capacity optimum, square-root eta called empirical Kyle lambda |
| F10 | CVXPY CLARABEL constrained SOCP with covariance-square-root mean uncertainty; common bounds/gross/turnover/tracking-error constraints on every frontier point; structured Black–Litterman; actual supplied cross-sectional FAP OLS | Robust shrinkage proxy, correlation FAP, infeasible equal-weight fallback, greedy cardinality, factor-space stock-sector constraints |
| F11 | Daily-unit reverse stress, labelled Gaussian radial tail diagnostic, observed one-day analogs, exposure-weighted VaR/CVaR, VAR lag selection, recursively simulated residual paths with coefficient refit and 90% IRF bands at 1/5/10/21 sessions, base residual-sigma shock units | Variance-scaling pseudo-bootstrap, weak inverse cache, radial tail called scenario-occurrence probability, invented executable hedge mapping |
| F12 | Observed IC/half-life/concentration, raw-unit diagnostics, HAC spanning alpha/R2, measured factor correlations and requested comparison factors | Handwritten academic archetypes, jitter-trained classifier probabilities, arbitrary 50-filled radar scores, correlation shares called economic return anatomy |
| F13 | Matured cross-sectional IC drift, disjoint baseline/recent samples, statsmodels residual CUSUM statistic/p-value, SQLite idempotent dated alert transitions and recovery events | Return autocorrelation IC, CUSUM called Chow, invented weighted health score, dormant delivery-success claims |
| F14 | Actual upstream sections/statuses, explicit partial failure reasons, escaped narrative, uploaded opaque-ID logo, vector charts from actual numeric records, PDF page enforcement/page numbers, source/version audit, JSON and CSV tables | Unbounded fragment cache, hidden section errors, server-path logos, fake successful subscription/report exports |

## Old-file fate table

| Old file/path | Fate |
|---|---|
| `core/analytics.py` | Retained compatibility exports; implementations extracted into focused modules |
| `core/contracts.py` | Reduced to identities/titles; stale aspirational executable controls removed |
| `core/data_loader.py` | Hardened in place; versioned raw/cutoff caches and strict sources/symbols |
| `core/performance.py` | Only referenced numerical/runtime kernels retained; unused scratch/array caches, duplicate costs, handwritten elastic-net/IC helpers and import-time prewarming removed; no fastmath with NaN checks |
| `features/feature_01.py`–`feature_14.py` | Reworked in place; each declares backend INPUTS/OUTPUTS |
| Descriptive feature wrapper modules | Retained for import compatibility; no duplicated implementations |
| Duplicate ADV/capacity, fake walk-forward, synthetic DNA training, fake crowding probability and unused hedge helpers | Removed after graph discovery and repo reference searches |
| Legacy README / implementation-status document | Retained as historical material with supersession notices |
| Feature/data/design specs | Retained as specifications; supported executable contract and this disposition table govern current behavior |
| `review.md`, empty `schemas/` / `utils/` | Not present in this Factors module; nothing deleted |
| Frontend hub synthetic arrays/charts and d3 import | Fabricated results removed; layout retained, future visuals reserved for Claude |
| Other V2 modules / V1 Factors | Unmodified |

## Known limitations and deliberate exclusions

1. This local dataset does not establish verified filing timestamps, restatement vintages, historical constituent membership, delisted-stock total returns, corporate-action-adjustment provenance, or historical instrument-unit changes. Historical outputs are conditional on observed local coverage; they are not certified survivorship-free investable histories.
2. USD/share-unit declarations are explicit inputs. Without them, cross-currency valuation, USD stock execution, and USD stock regressions are unavailable. Currency-mismatched statement/quote value ratios are not guessed. Automatic universe selection requires USD conversion.
3. AQR processed CSVs were not present in this checkout during real-data validation. Their published daily decimal return convention must be verified for any newly supplied files; mixed-frequency tabs are not a supported daily estimator input.
4. F03 does not provide stock-selection/Brinson/carryover attribution without actual dated portfolio and benchmark holdings/returns. F07 has fixed declared composite weights, not a trained adaptive weight optimizer. Quintile/decile returns and stationary-block confidence intervals are measured; sparse invested histories retain null intervals.
5. F06 institutional positioning and crash calibration need matched observations that are not supplied. F12 classifier probabilities require a measured labelled training set. These outputs are removed, not represented by invented training labels.
6. F04 states are statistical model states, not six economically named growth/rates regimes. Market-observation rules are separate diagnostics. HMM holdout filtering is causal conditional on its training cutoff; it is not a walk-forward retraining trading strategy.
7. EWMA/DCC parameters and impact eta are declared assumptions. No claim of estimated GARCH/DCC likelihood or empirically calibrated Kyle impact is made. Capacity is a current-book scenario under those assumptions, not a guarantee of future alpha or liquidity.
8. Factor-space optimization has no cardinality/mixed-integer or stock-sector constraint claim. FAP requires actual matched alpha/loadings. Black–Litterman views are structured numeric inputs, not natural-language parsing.
9. The half-life interval is conditional on the selected curve model and needs enough joint mature observations. Drift z-scores can be affected by IC dependence; CUSUM inference retains its residual assumptions. Sparse local pre-2015 formation history does not support an acceleration significance claim.
10. Only in-app alert persistence exists. No email, Slack, webhook, scheduler, subscription-delivery worker, or automatic external message is claimed. Jobs run in local threads with durable records; they are not process-isolated compute.
11. PDF DDQ mappings are broad disclosure topics, not certified question-level compliance. Plots identify the actual source field and ordered records; bespoke frontend/report renderer design is outside this backend pass.
12. Claude must migrate frontend controls/renderers to `GET /features`: unsupported legacy controls now correctly return 422. Frontend design, manifest form construction, upload UI, progress/cancel UI, and browser console verification remain outside this backend task. No browser end-to-end success is claimed.

## Validation

The existing four targeted test files are `backend/tests/test_factors_v2_math.py`, `test_factors_v2_data_and_api.py`, `test_factors_v2_contract.py`, and `test_factors_v2_features.py`, with reusable local fixture data in `factors_v2_fixtures.py`. They cover numerical library references, next-close execution and exact costs, missing held quotes, optimizer constraints/infeasibility, RF-based regressions, real API errors/envelopes/jobs/uploads/exports, file-refresh invalidation, future-data mutation, statement lag, FX dates, momentum endpoints, all 14 features and every declared output.

Commands and results are recorded below after the final pass. Full repository pytest is intentionally unnecessary: this task changes only Factors, and all affected shared Factors paths are exercised by its suite.

Final check results (2026-10-07):

```sh
# Repository root, Python 3.11 test environment
OMP_NUM_THREADS=1 PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_factors_v2_math.py backend/tests/test_factors_v2_data_and_api.py backend/tests/test_factors_v2_contract.py backend/tests/test_factors_v2_features.py -q --tb=short
# 40 passed in 15.00s. Eight dependency/pandas deprecation warnings, no failures.

ruff check backend/app/services/factors_v2 backend/app/api/factors_v2.py --select F821
# All checks passed.
PYTHONPATH=backend /opt/homebrew/opt/python@3.11/bin/python3.11 -m compileall -q backend/app/services/factors_v2 backend/app/api/factors_v2.py
# Exit 0.
git diff --check
# Exit 0.

# Frontend directory; only affected Factors wiring/surfaces
npx jest src/components/factors-v2/__tests__/factorsV2.test.ts --runInBand
# 3 passed.
npx eslint src/lib/api.js src/app/labs/factors-v2/page.js src/components/factors-v2/customPagePrimitives.jsx src/components/factors-v2/__tests__/factorsV2.test.ts
# Exit 0; baseline-browser-mapping package-age notice only.
npx tsc --noEmit
# Exit 0.
npm run build
# Exit 0; compilation, TypeScript, and all 142 route page generation passed.

# Actual local-data smoke, not fixture/demo output
OMP_NUM_THREADS=1 PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python /tmp/factors_real_smoke.py
# All 14 statuses ok; every result serialized with allow_nan=False.
```

The local smoke script used explicit AAPL, MSFT, NVDA, AMZN, GOOGL, META, JPM, V, MA, UNH, HD, PG, KO, PEP, COST, WMT, BAC, XOM, CVX, ABBV, MRK, TMO, AVGO, CSCO, ACN, MCD, DIS, ADBE, NFLX, and SPY; explicit USD/ordinary-share declarations; 360 sessions; momentum; formation interval 21; 20 F05/F11 bootstrap draws; 10 F07 MC paths. F02 used actual declared AAPL/MSFT 50/50 holdings, F03 declared HML .4/Mom .6 exposures, and F14 selected Current Factor Exposures with a declared AAPL holding. It is a local validation recipe, not product data. Measured feature seconds: F01 11.61, F02 2.56, F03 .02, F04 .18, F05 18.64, F06 .51, F07 9.68, F08 .03, F09 8.49, F10 .28, F11 .19, F12 30.74, F13 5.75, F14 .69. Cold file loading/JIT and universe/window sizes change these timings; no latency SLA is claimed.

A `pkgutil.walk_packages`/`importlib.import_module` smoke imported all 31 discovered Factors modules and verified the owned run/job route registrations. Graph searches plus repo reference searches preceded removing unused helpers; the main mount was checked without modifying `backend/main.py`.

The test environment initially lacked `arch` and `hmmlearn`, both already declared in `backend/requirements.txt`; installed with `uv pip install --python /tmp/pca-v2-check-env/bin/python 'arch>=6.0.0' 'hmmlearn>=0.3.0'`. Initial failed tests identified and fixed scoped return-cache cutoff leakage, a missing capacity crossing helper, and a CVXPY lower-bound operator-precedence error. A first local report smoke supplied the wrong section label and correctly failed; the exact supported Current Factor Exposures label then passed. No fallback was added to conceal these failures.

Full-repository pytest/lint and browser verification were not run. Targeted Factors backend/frontend checks and the shared frontend build were sufficient for the requested backend scope. Phase 6 browser/frontend acceptance remains pending Claude's frontend rebuild.
