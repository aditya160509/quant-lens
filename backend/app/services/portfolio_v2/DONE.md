# Portfolio V2 backend rebuild

Completed backend verification: 2026-10-08. Scope: Portfolio V2 engines, its API router, four targeted test files, and these status documents. Frontend design, frontend renderers, and browser work were excluded by the user. This is backend completion, not certification of the existing frontend.

## Architecture before and after

Before: `core/analytics.py` contained the estimator, optimizer, attribution, backtest, regime, liquidity, execution, and strategy implementations. Feature inputs/outputs were string lists; the API served module names and synchronous runs. Several failures produced equal weights or replacement universes. Missing observations became zero returns, current metadata entered historical calculations, execution assumptions appeared measured, and backend-specific tests were absent.

After: one focused engine per feature, shared covariance/statistical/data/serialization primitives, a lazy registry, typed backend contracts, and module-owned uploads/jobs/results. The old analytics implementation is removed. Feature files assemble measured outputs and disclose unavailable inputs. The router keeps its existing `/api/labs/portfolio/v2` mount and adds discovery, search, uploads, exports, jobs, polling, and cancellation.

| Engine | Responsibility |
|---|---|
| `construction.py` | Constrained portfolio objectives, feasibility diagnostics, frontier, Black-Litterman views, HRP |
| `backtest.py` | Prefix-only estimation, drifting positions, calendar/threshold rebalancing, executed-notional fees |
| `attribution.py` | Distinct BHB/Fachler effects, exact Carino/Menchero/GRAP linking, factor contributions, selection null |
| `stress.py` | Observed factor crisis replay, stationary bootstrap, Mahalanobis reverse stress |
| `regimes.py` | Prefix-fitted HMM/Hamilton or observed VIX classifier, conditional optimizations, censored duration analysis |
| `liquidity.py` | Observed ADV/Amihud/DTL and capacity-constrained liquidation |
| `correlation.py` | Correlation graphs, partial correlations, eigen diagnostics, HAC trend-break tests |
| `decay.py` | Actual formation-score ICs, bootstrap bands, taxonomy-aware fitting, publication mean-shift test |
| `allocation.py` | Fraction-first Kelly and explicitly assumed annual cost/growth comparisons |
| `execution.py` | CVXPY discrete Almgren-Chriss schedules, covariance-coupled risk, actual cost-risk frontier |
| `systemic.py` | Supplied peer-book overlap, exposure-based DebtRank, declared fire-sale scenarios |
| `strategies.py` | Supplied strategy histories, binding risk/capacity/correlation constraints, causal switches and allocation |
| `covariance.py`, `stats.py` | Shared library-backed estimators and inference |
| `data_loader.py`, `context.py`, `uploads.py` | Strict observed-data reads, request cutoff, signed exposures, validated upload sandbox |
| `common.py`, `performance.py` | JSON-safe contract responses, finite matrix operations, bounded thread-safe caches |
| `features/inputs.py`, `registry.py` | Backend-owned defaults/options/bounds/aliases, input validation, render hints, lazy dispatch |

The macro feature uses `statsmodels` OLS/HAC directly from its feature assembler; it has no duplicate regression engine. Existing CVXPY, SciPy, scikit-learn, arch, statsmodels, hmmlearn, NetworkX, pandas, Polars, and numba dependencies suffice. No new dependency or test infrastructure was added.

## Old-file fate

| Original path or implementation | Fate and reason |
|---|---|
| `core/analytics.py` | Removed after graph caller checks, `rg`, feature/API import checks, route checks, and feature tests. All retained calculations moved into focused engines. No duplicate compatibility implementation retained. |
| `core/data_loader.py` | Rebuilt in place; eliminated paper-export paths, loaded-once global merge cache, holdings-price/equal-weight substitutions, and unused full-panel readers. |
| `core/performance.py` | Retained and corrected: PSD reconstruction, finite checks, complete-frame fingerprints, cache locking/isolation, no manufactured below-threshold edges. |
| `features/feature_01.py` through `feature_13.py` | Rebuilt in place; no old feature runner remains alongside the new path. |
| `backend/app/api/portfolio_v2.py` | Rebuilt at the existing mount; flat and `{payload: ...}` request envelopes remain supported, ambiguous envelopes are rejected. |
| `README.md` | Replaced the inaccurate scaffold/proxy checklist with current routing and a link here. |
| `docs/portfolio features.md` | Preserved as original design history. Current manifest and this document specify what is supported. |
| `NOT_DONE.md`, `missing.md`, `review.md`, `docs_review.md`, `speed upgrades.md` | Mentioned by the review but absent from the current checkout and tracked module inventory. No invented deletion or duplicate checklist created. |
| `fetchers/fetch_missing_data.py` | Preserved unchanged; operator helper is not invoked by feature runs. |
| Other V2 modules, V1 Portfolio services, all frontend files | Unchanged in this pass. Cross-module consolidation and legacy deletion are outside the authorized scope. |

Unused proxy helpers were removed, including the old linking functions, iid skill bootstrap, fixed-parameter DCC loop, fabricated alpha-capacity/net-IC-as-alpha helpers, heuristic leverage/ruin helpers, and holdings fallback path. Graph inbound callers were checked; any inbound calls belonged to the removed set. Current Python imports and route registration were checked after removal.

## Data rules

- Main observed market parquet is required. Canonical asset panels supplement it with explicit canonical precedence for duplicate master/canonical observations. Duplicate observations within one source fail. No research-paper-export fallback is used.
- Symbol selection is exact. Unknown symbols and unsupported named index universes fail with 422. Registry defaults are explicitly `SPY, QQQ, IWM, EFA, EEM`; direct loader `default` selection is history-ranked and disclosed, never called S&P 500 membership.
- `as_of_date` cuts every reader before selecting its estimation window. Daily return intervals are simple observed close-price changes. No forward fill or zero replacement is used. Weekly/monthly prices use completed observed period endpoints.
- Complete-case estimation reports excluded intervals. Walk-forward retains the sparse panel and fails if an actually held asset has an unobserved return. Alpha IC labels retain gaps rather than compounding across missing intervals.
- Signed weights are preserved. Equal weights, when omitted, are an explicit default, not holdings inferred from average cost or fabricated market caps. Net and gross exposure are separate constraints.
- Current sector labels are disclosed as static. Historical sector caps are refused; historical stability is not generated under current sector caps. Historical index membership, delisting recovery, and point-in-time shares are not inferred.
- Actual FF5 and momentum daily parquets are used in decimal units. Macro exposure uses observed VIX/FX changes and rate/spread differences. Daily yield-curve slope is simultaneous observed `DGS10 - DGS2`, correcting the archived slope column's sparse/weekend-only coverage. Economic levels without vintage histories are not sold as predictive inputs.
- Liquidity and day-based stress/execution paths require daily observations. Dollar-volume claims require supported USD equity/share-volume provenance; FX/crypto/non-USD data are not relabeled dollar ADV. US unsuffixed equity symbols without currency metadata rely on the declared US equity source convention, not an FX conversion.
- File path/mtime/size versions invalidate data caches and accompany jobs. Numeric caches fingerprint the full frame, index, and columns; they are bounded, locked, and return isolated values. Jobs refuse publication if sources change during estimation.
- CSV uploads are capped at 2 MB, content-addressed, shape/date/value validated, stored atomically under `backend/data/portfolio_v2/uploads/`, and accessed only through sandboxed IDs. No arbitrary upload file path is accepted.

## Feature and estimator status

| Feature | Supported calculations and corrections |
|---|---|
| F01 Construction | Sample/Ledoit-Wolf/OAS/EWMA/constant-correlation covariance; honestly named rotation-equivariant eigenvalue regularization; fitted GARCH/DCC; actual FF5 structured covariance; Gerber-2. Convex GMV/MVO/Gaussian growth-optimal/BL/CVaR solve through CLARABEL. Positive-excess maximum Sharpe uses a homogeneous convex tangency solve; remaining nonlinear objectives use SciPy with success and constraint-residual checks. Risk budgeting uses a convex log-barrier seed. HRP is recursive bisection, including the correct two-asset inverse-variance allocation. Frontier targets begin at GMV and end at constrained maximum expected return; failed points/objectives carry reasons. BL accepts actual user views and an explicit user/equal prior. Sector, bounds, gross/net, 130/30, turnover and real binding reports are enforced. |
| F02 Backtest | Re-estimates exclusively before each holding interval, holds drifting positions, preserves cash/shorts, and charges absolute executed post-fee notional including initial funding. Default calendar rebalancing is truly calendar based; explicit observed-bar intervals and drift thresholds are supported. Monthly heatmap compounds. More than 30 measured performance fields, historical/normal/Monte Carlo/Cornish-Fisher VaR, block-length selection, PSR, DSR, observation-unit MinTRL, actual CSCV PBO. Eight partitions evaluate all 70 half-splits. Manual weights count as one strategy, not repeated optimizer trials. Multiplicity correction is honestly named Bonferroni, not HLZ. |
| F03 Attribution | Honors actual benchmark returns or constituent weights. Distinct BHB/Fachler allocation effects, exact geometric active-return linking for Carino/Menchero/GRAP, actual FF factor loadings times realized factor returns, reconciled drawdown contributions, active risk attribution, within-sector weight-permutation selection null. No factors inferred from rank correlations. |
| F04 Stress | Actual archived FF5 crisis sequences mapped through measured trailing exposures, explicitly a factor replay rather than historical realized holdings P&L. Observed daily tail scenarios, stationary-block bootstrap, covariance-based flat-correlation assumptions, and exact minimum-Mahalanobis projection to requested portfolio loss. |
| F05 Macro | Consistent statsmodels OLS/Newey-West HAC for portfolio, assets, and rolling exposures. Actual factor transforms, target/tolerance flags and risk limits. Portfolio marginal risk is correctly named; it is not benchmark tracking error. No Ridge or zero-fill fallback. |
| F06 Regimes | Prefix-trained/filtered Gaussian HMM, converged Hamilton switching, or observed VIX classifier. No GMM/quantile fallback. Conditional portfolios are actually optimized and probability mixed; sparse states disclose unavailable mixtures. Nonhomogeneous transitions fit multinomial models on observed prior volatility/momentum and fail when unidentified, rather than silently retaining constant rows. Kaplan-Meier uses right censoring and excludes the initial left-censored spell. |
| F07 Liquidity | Observed open-to-close Amihud, exact linear-recency weighting, return volatility, observed dollar ADV, participation-specific DTL, observed-session liquidity trend, complete capacity-constrained orderly/distressed/crisis schedules. Stress volume reductions and square-root impact coefficients are stated assumptions. DTL buckets are not regulatory certification. |
| F08 Correlation | Correct risk-contribution entropy and separately named eigenvalue participation. MST, hierarchy, precision networks, true crisis-window comparison, equity/bond tracker. Rolling paths or prefix-refitted GARCH/DCC at 21-observation evaluation origins. HAC Wald intercept/trend breaks include p-values, split-date adjustment and displayed-pair family adjustment. No nominal polyfit F described as Chow. |
| F09 Decay | Actual supplied scores or explicitly trailing momentum; matured forward compounded labels, Spearman IC, stationary-bootstrap bands, empirical half-life. Mechanical taxonomy fits linear/exponential/hyperbolic/stretched curves by AIC; judgment taxonomy requires supplied scores and does not force a curve. Real raw-score dispersion percentile, not ETF crowding/crash probability. Optional supplied publication date receives an actual HAC mean-shift test on matured ICs. |
| F10 Kelly | Applies fraction before gross cap, uses actual weighted drift/covariance, compares measured growth approximations and annual traded-notional cost assumptions. Ruin surface explicitly states an infinite-horizon arithmetic-Brownian model, not a drawdown guarantee. No heuristic “safe leverage” or fabricated signal-decay input. |
| F11 Execution (spec 12) | Requires non-implied target weights and honors NAV/aum alias. Discrete CVXPY AC schedules conserve signed trade notional and finish at zero inventory; measured covariance couples risk. Cost-risk frontier is generated by actual schedule solves. Temporary/permanent impact assumptions and supplied observed delay returns are distinguished. No fixed 35/65 split, synthetic U-shaped volume profile, or invented cross-impact calibration. |
| F12 Systemic (spec 13) | Requires supplied normalized peer books. Actual overlap, degree/eigenvector/betweenness networks, peer-NAV/observed-ADV fire-sale scenarios with declared depth coefficient. Genuine transmit-once DebtRank requires supplied directional counterparty exposures, not normalized overlap. No invented cascade probabilities or path-level peer history. |
| F13 Strategies (spec 15) | Requires actual supplied strategy return histories. Fixed/inverse-vol/Sharpe-momentum/Kelly/regime-conditional allocation, complete-prefix estimation and prior-close staged kill switches. Two-state full-covariance HMM forecasts conditional strategy moments when requested. Correlation exclusions use an actual MILP independent set; capacity, total volatility, and component-risk caps bind and are verified. Remaining capital stays cash. Actual post-fee traded notional drives costs. Netting requires actual underlying security trades. |

## Known limitations and removed claims

1. Historical index membership and complete delisted-stock returns/recoveries are absent. This is an explicit fixed-universe backtest, not a survivorship-corrected index replication. Missing held returns fail; they are not marked zero. Close-price returns are not claimed to include all dividends or corporate-action adjustments unavailable in their source.
2. Full point-in-time sector/share/cap records are absent. Current classifications are descriptive only; historical sector constraints are refused. No fabricated BL market caps or historical cap weighting.
3. FF/macro coverage varies by date, asset, and frequency. Unsupported/missing matched observations fail or disclose unavailable diagnostics. The macro model describes market-implied exposure; it is not a vintage-safe macro forecast or fundamental fair-value price model.
4. ETF AUM/flow histories, measured bid/ask spreads, signed order-flow calibration, calibrated intraday profiles, and permanent/cross-impact coefficients are absent. Dollar alpha capacity, calibrated liquidity VaR, crowding crash probabilities, regulatory certification, cross-impact Riccati estimates, and synthetic volume profiles are removed. Declared impact/volume/depth assumptions remain visible as assumptions.
5. Peer fund histories, balance-sheet loss buffers, counterparty exposures and strategy security trades are not generated from prices. Users must supply actual peer books/NAVs/exposures and strategy returns/trades. Without them the relevant outputs explain what is missing. Rolling DebtRank, liquidation-spiral/cascade probabilities, and hypothetical future kill-switch probabilities are not produced.
6. Gaussian Kelly/ruin and impact models are assumptions, not guarantees. Explicit cash carry defaults to zero; the zero risk-free comparison is labeled. DSR assumes independent trial Sharpes and requires the total user-known trial count; unreported searches cannot be reconstructed. Large CSCV partition sets are deterministically sampled at 5,000 combinations and disclose the sample/total counts.
7. Nonlinear constrained risk parity/diversification, nonpositive-excess Sharpe and strategy risk caps are verified local SciPy solves, not claimed global convex certificates. Exact constrained risk contributions may deviate from desired shares. HRP/inverse-vol refuse incompatible constraints instead of projecting into a different named estimator. Solver failures are not equal-weight portfolios.
8. Cornish-Fisher VaR is reported only when the estimated quantile expansion is monotonic on the checked tail range; CF CVaR is not fabricated. Zero-risk ratios/marginal risk and unobserved capture periods remain null with interpretation rather than epsilon-generated large numbers.
9. Jobs run on the existing local Studio JobStore. Cancellation suppresses result publication; an already active numerical solver may finish in the background. This is not a distributed queue or forcible solver preemption. Exports provide JSON, CSV tables, and LaTeX source; backend PDF rendering was not introduced.
10. Frontend manifest consumption, sign-aware charts, fake decorative sparklines/static dial removal, renderer/layout rebuild, Jest, frontend lint/build, and browser console checks remain frontend work. None was performed or certified in this backend-only pass. Shared workbench/data-loader consolidation across unrelated V2 modules and V1 removal remain outside scope.

## Verification

All commands ran from `/Users/adityabalaji/Downloads/quant  2`. Existing test runtime `/tmp/pca-v2-check-env/bin/python` is Python 3.11.15.

```sh
PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_portfolio_v2_*.py -q
PORTFOLIO_V2_REAL_DATA=1 PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -m pytest backend/tests/test_portfolio_v2_*.py -q
ruff check backend/app/services/portfolio_v2 backend/app/api/portfolio_v2.py backend/tests/test_portfolio_v2_*.py
ruff format --check backend/app/services/portfolio_v2/core backend/app/services/portfolio_v2/features backend/app/services/portfolio_v2/registry.py backend/app/api/portfolio_v2.py backend/tests/test_portfolio_v2_*.py
git diff --check
```

Final results: 71 fixture/API/golden/look-ahead tests pass, with 13 opt-in integration cases skipped in the ordinary run. Enabling real repository data gives **84 passed**. Ruff lint/format and whitespace checks pass. The only pytest warning is an existing Starlette TestClient/httpx deprecation; no dependency change was made to suppress it.

The four test files cover independent GMV/max-Sharpe/HRP/BL golden numbers, independent HiGHS CVaR comparison, equal risk contributions, infeasible constraints/frontier, signed/130-30 exposure, exact attribution identities/linking, Mahalanobis projection, Amihud/ADV/DTL, AC frontier and trade conservation, DebtRank/entropy, full-frame cache mutation/isolation, PBO enumeration, strict inputs/API/upload/export/jobs, future mutation for walk-forward/HMM/strategy rules, calendar rebalance boundaries, missing held returns, and as-of slicing.

The 13 integration cases use repository SPY/QQQ/IWM prices as of 2026-01-28, actual local FF/macro/OHLCV data, supplied test target/peer books and NAV assumptions, and observed ETF sleeve returns for the strategy-input contract. Test peer allocations are supplied scenario inputs, not represented as measured external fund holdings. Each feature completes, has a produced declared output, and serializes without nonfinite JSON numbers.

Additional direct live checks completed: F08 prefix DCC produced nine causal endpoint records in approximately 1.45 seconds on a 180-observation panel; F09 supplied publication date produced a measured HAC test; F13 regime-conditional strategy allocation produced three training-prefix fits. An earlier all-feature live smoke script (`PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python /tmp/portfolio_real_smoke.py`) completed all 13 runners; the integration tests above are its reproducible retained equivalent.

Import/route proof ran this exact Python body with `PYTHONPATH=backend /tmp/pca-v2-check-env/bin/python -`:

```python
import importlib
from fastapi import FastAPI
from app.services.portfolio_v2.registry import feature_manifest
from app.api.portfolio_v2 import router
features = feature_manifest()
for row in features:
    importlib.import_module('app.services.portfolio_v2.features.feature_' + row['id'])
app = FastAPI()
app.include_router(router, prefix='/api')
paths = sorted(app.openapi()['paths'])
assert len(features) == 13 and len(paths) == 8
assert all(p.startswith('/api/labs/portfolio/v2/') for p in paths)
```

Result: 13 feature imports and eight mounted OpenAPI routes pass. An initial route-inspection attempt assumed all FastAPI route objects exposed `.path`; the check was corrected to the mounted OpenAPI schema. No application code was changed for that tooling assumption.

### Failures found and fixed during verification

- PSD reconstruction multiplied eigenvalues twice, changing the covariance scale. GMV golden tests exposed it; eigenvector reconstruction is corrected.
- Risk-parity SLSQP had a poor stationary solution. Convex risk-budget initialization plus verified constraints corrected equal-contribution golden numbers.
- Redundant long-only gross/net constraints could let SLSQP report a suboptimal tangency point as successful. An independent maximum-Sharpe vector exposed it; positive-excess Sharpe now has an exact homogeneous convex solve.
- Missing/weekly archived yield-curve values made live macro regression unusable. Simultaneous actual daily Treasury yields now define the same measured slope.
- Fixed-zero correlation-excluded strategies made the nonlinear allocation directions singular. The solver operates on eligible variables and verifies the original full constraints.
- Read-only pandas array assumptions in stress/network routines were removed. Manual strategies no longer create false trial multiplicity, two-asset HRP uses inverse variance, urgent liquidation schedules conserve notional, and strategy costs use executed post-fee trades.
- Initial combined fixture/live integration checks exposed test aliases captured while source readers were patched. Feature aliases now import before patching so teardown restores real readers; the combined suite passes.

No frontend or whole-repository test result is implied by these backend checks.
