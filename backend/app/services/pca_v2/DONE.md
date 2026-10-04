# PCA V2 backend rebuild, 2026-10-04

The backend now produces observed-data results through a validated manifest and durable jobs. The frontend rebuild is reserved for Claude and was not changed in this work.

## Architecture

Previously, `core/analytics.py` held 2,342 lines of mixed analytics, silent fallbacks and full-sample residual backtests. It is now a compatibility import facade. Feature implementations are grouped by their mathematical responsibility:

| Feature | Core implementation | Estimators |
|---|---|---|
| 01 | `pca_math.py`, `model.py` | Sample, Ledoit-Wolf, OAS, EWMA, MCD; fitted MP bulk; covariance or correlation PCA |
| 02 | `factors.py` | PCA, Varimax, Promax, two-level HPCA, Hoyer sparsity, asset R-squared, biplot data |
| 03 | `risk.py` | PC/idiosyncratic variance, marginal contributions, tracking error, Gaussian/CF/historical tail risk |
| 04 | `ou.py`, `causal.py` | AR(1) OU OLS, exact OU MLE, volume time, rolling historical PCA/residual fits, next-observation trading |
| 05 | `regimes.py` | Rolling spectra/cosines/angles, CUSUM with library p-value, dynamic-programming mean breaks with BIC, HOSVD |
| 06 | `optimization.py`, `allocation.py` | Constrained mean variance, ERC, max Sharpe, PC risk parity, QP frontier, ellipsoidal robust frontier, BL asset/PC views, rolling portfolio backtest |
| 07 | `bootstrap.py` | Case, circular block, residual bootstrap; Bai-Ng criteria; principal angles and subsampling |
| 08 | `contagion.py` | Residual correlation, groups, eigenvalue diagnostics, HOSVD; optional causal rolling residuals |
| 09 | `scenarios.py` | PC/joint shocks, historical replay, Mahalanobis analogs, full-factor-covariance Monte Carlo, up to four portfolios, PDF |
| 10 | `cross_asset.py` | Actual LW equity block, FX EWMA, commodities/rates OAS, fixed-df Student-t EM crypto; DCC, unified RMT, block MP bounds |
| 11 | `liquidity.py`, `stats.py` | Amihud, Pastor-Stambaugh, MP-selected liquidity components, IML alternative, orthogonal liquidity regression, statsmodels HAC |

`common.py` owns JSON-safe records and metadata. `data_loader.py` owns observed prices and strict tickers. `uploads.py` owns opaque, validated upload ids. `features/inputs.py` and each feature's `INPUTS`/`OUTPUTS` declare the frontend contract. Registry imports remain lazy until discovery or execution.

## Data and numerical rules

- Unknown or partially unknown ticker lists fail with listed symbols; undersized universes are never replaced.
- Price gaps are not forward-filled. Return panels use complete observed adjacent-price log returns and report coverage and discarded dates. Explicit oversized universes require an increased limit.
- Historical end dates filter source prices before return computation. Rolling, expanding and anchored windows use the requested interval; anchored windows require an anchor date.
- Default universes are labelled as ranked by observed history. They are not historical index constituents. Default portfolios are equal weighted because historical shares are unavailable.
- Correlation PCA normalizes the estimated matrix diagonal to one. Return-unit covariances and loadings are restored for downstream risk calculations; factor scoring uses the corresponding standardized coordinates.
- Kaiser selection requires correlation PCA. A retention rule with no eligible components fails instead of silently labelling a noise PC as signal.
- MCD requires more than twice as many observations as assets. Invalid estimators/preprocessing and insufficient trimming fail explicitly.
- F04 fits PCA and residual betas using only prior observations. Signals formed at t earn returns and incur trade costs at t+1. Signal exits now actually clear positions. Historical backtests use observed unprocessed returns, avoiding full-sample outlier preprocessing.
- F06 applies common sector, factor, turnover and tracking-error constraints. Solver failures are explicit. Annual expected returns and covariance use consistent units. OOS K candidates use training data and a default 21-observation embargo; the universe-selection limitation is disclosed.
- Bootstrap requests execute the requested 2-1,000 replications. Counts below 200 are labelled previews. No silent cap remains.
- F10 uses complete shared dates, real block estimators and DCC cross-covariance. `gamma_cross=0` uses conditional cross-covariance; `1` uses unconditional sample cross-covariance. PSD projection magnitude is reported. Historical DCC output starts after its initial parameter-training window.
- F11 uses observed positive dollar volume, never synthetic zeros or an Amihud fallback under another estimator name. HAC standard errors use statsmodels; the prior implementation's extra sample-size division was removed. The augmented regression orthogonalizes liquidity against PCs to avoid counting existing idiosyncratic variance twice.

## API

The existing `backend/main.py` mount already exposes `/api/labs/pca/v2` and was preserved.

- `GET /features`, `GET /symbols`
- `POST /uploads?kind=returns|weights|groups`: CSV, 20 MB cap, required columns, finite values and duplicate checks, opaque ids under `backend/data/pca_v2/uploads/`
- `POST /feature/{id}/run`: retained Python/HTTP compatibility path
- `POST /feature/{id}/jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel`: Studio JobStore with PCA-owned index and per-job result files

Unknown features/jobs return 404; invalid payloads/tickers return 422; oversized uploads return 413. Cancellation prevents result publication; a running numerical computation finishes in the background. Empty declared outputs carry explicit missing-output metadata.

## Old-file fate

| Previous path | Fate |
|---|---|
| `core/analytics.py` | Retained as compatibility exports; algorithms moved to focused modules |
| Old ERC/Sharpe/PC-parity and duplicate frontier paths | Removed after graph and import checks; replaced by the shared constrained solver |
| Unused MCD-as-Student-t fallback and daily Kyle approximation | Removed; insufficient Student-t data fails and true Kyle is unavailable |
| `core/data_loader.py`, `core/cross_asset.py`, `core/performance.py` | Retained and corrected |
| Feature modules and registry | Retained; declarations/validation added, blanket feature fallbacks removed |
| Existing `analytics.py.bak` and historical module audit documents | Pre-existing files preserved, not created or modified by this work |
| Frontend components and shared `main.py` / `lib/api.js` | Untouched |

## Known limitations

- Frontend pages still require Claude's rebuild. No frontend renderer, lint/build or browser verification is claimed.
- Cardinality is rejected because the supported solver stack has no mixed-integer quadratic solver. True Kyle lambda requires signed intraday order flow; turnover illiquidity requires historical shares. Neither is offered as a proxy.
- Historical index membership, point-in-time shares and currency-hedged portfolio attribution are unavailable. Named index aliases are no longer silently mapped to a generic universe. Static sector metadata is used for grouping.
- F08's default fixed-model historical residual charts are explicitly retrospective. Enable `rolling_refit` for causal historical residuals.
- F04 and F06 backtests use observed unprocessed returns and fixed explicitly selected symbols. They do not reconstruct historical index membership. F04 still uses flat basis-point trading costs rather than a spread-proportional model.
- F10 futures inputs are raw vendor continuous series; independent contract roll adjustment is not verified. Student-t EM uses fixed degrees of freedom 8, explicitly disclosed. DCC reports its 1e-8 numerical volatility floor. The crypto volume check is a local positive-volume quality screen, not proof of wash trading. Block MP bounds and the heavy-tail correction are diagnostics, not exact finite-sample significance tests.
- F11 exposes all MP-retained liquidity component series; the scalar beta/LaVaR panel uses the first liquidity factor or the selected IML factor. Liquidation costs are explicitly square-root impact estimates.
- MP noise variance uses iterative bulk moment matching, not maximum likelihood. Mathematical noise thresholds are asymptotic diagnostics.
- Real-data runs use the existing local parquet's dates; freshness is not guaranteed by the runtime.

## Verification

30 tests in four dedicated PCA test files cover numerical references, causal guards, data/API/jobs, every feature's declared outputs and the retained remediation regressions.

Command:

```sh
PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_pca_v2_*.py -q
```

Python 3.11 verification environment contains the existing declared backend libraries, including cvxpy. Homebrew Python 3.11 supports the non-solver checks but lacks cvxpy; no repository dependency was added.

Observed local-parquet smoke runs: all 11 features returned `status: ok`. Features 01-09/11 used SPY, QQQ, IWM, EFA, EEM, TLT, GLD, USO, AAPL, MSFT, NVDA, AMZN, lookback 300, manual K=2; the observed complete panel had 284 rows. F10 used its declared default blocks and produced a 64-asset, 243-date aligned panel. Fixture smoke checks also exercise all declared output keys.
