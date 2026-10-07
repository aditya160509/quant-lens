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

## Architecture before and current state

Before: a 1,495-line analytics file, nine feature wrappers, aspirational output contracts, a synchronous router, and disconnected frontend workbench.

Current: strict request-scoped `core/data_loader.py`, dedicated `core/har.py` and `core/garch.py`, rewritten Features 02/03, and golden/data regression tests. Splitting remaining estimators, regimes, covariance, connectedness, stress and budget code, plus updating the manifest/router, remains required.

## Old-file fate table

| File | Fate |
|---|---|
| `core/data_loader.py` | Replaced in place; public loader entry points preserved, invalid inputs now fail |
| `core/analytics.py` | Still used; HAR/GARCH functions are being moved to focused modules; obsolete functions remain pending verified removal |
| `features/feature_02.py` | Replaced with true held-out GARCH suite |
| `features/feature_03.py` | Replaced with true expanding HAR forecasts |
| `core/performance.py` | Retained; unsafe fastmath disabled |
| Old audit/spec documents | Pending explicit supersession review; no deletion yet |

## Known limitations and remaining work

- Rebuild is incomplete. Features 04–09, remaining Feature 01 proxy outputs, full contracts, uploads/jobs/export, frontend wiring/fake removal, and final verification are pending.
- Macro history contains observations but no release-vintage guarantee. HAR-X is unavailable rather than silently imputing macro predictors.
- Daily OHLC does not support intraday bipower jump identification, genuine Bandi–Russell noise correction, or a Realized-GARCH measurement equation.
- The current GARCH winner is retrospective selection over a held-out evaluation window. Its historical diagnostics are post-selection and do not represent a tradable winner-switching strategy.
- PIT KS diagnostics do not correct for serial dependence or model selection.
- HAR confidence intervals are conditional OLS prediction intervals, transformed for LHAR; they do not incorporate model selection uncertainty.
- Source versions use filesystem metadata, not cryptographic content checksums. Calculations use full-content fingerprints.
- Historical delistings, adjusted-price conventions, mixed-currency handling and macro source availability still require the remaining data audit.

## Checks run so far

- `cd backend && PYTHONPATH=. /tmp/pca-v2-check-env/bin/python -m pytest tests/test_volatility_v2_*.py -q`: **12 passed**.
- `ruff check backend/app/services/volatility_v2/core/garch.py backend/app/services/volatility_v2/core/har.py backend/app/services/volatility_v2/features/feature_02.py backend/app/services/volatility_v2/features/feature_03.py backend/tests/test_volatility_v2_*.py`: passed.
- `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python - <<'PY' ... PY`: real Feature 01 run with SPY, 400 sessions, `as_of_date=2025-01-31`, returned `ok` and last chart date exactly 2025-01-31.
- Same Python entry point: real Feature 03 run with SPY/QQQ, 450 sessions, horizons 1/5, 120 training observations, 100 MCS repetitions: `ok`, eight model/horizon accuracy rows.
- Same Python entry point: real Feature 02 SPY, 400 sessions, GARCH/Student-t, 252 minimum training observations, 63 evaluation days, 200 simulations, horizons 1/5/21: `ok`, 63 held-out observations, finite likelihood-ratio diagnostics.
- No Jest, full frontend lint/build, or browser completion is claimed yet.

Yang–Zhang formula reference: [TTR volatility documentation](https://mirror.las.iastate.edu/CRAN/web/packages/TTR/TTR.pdf). The review’s swapped k/(1-k) formula was corrected against the estimator definition.
