# ML V2 rebuild record

Date: 2026-10-05. Backend rebuild implemented and verified on fixtures and local observations. Full platform acceptance is not claimed: browser verification was waived by the user, and browser-dependent behavior is unverified. This file supersedes historical module audits.

## Architecture before and after

Before: a 2,986-line analytics monolith, mixed V1/V2 router, static frontend contract, unpurged panel splits, fabricated architecture substitutes, current market-cap features and silent price/universe fills.

After: lazy registry and backend INPUTS/OUTPUTS manifest; dedicated `app/api/ml_v2.py`; focused `core/cpcv.py`, `alpha.py`, `volatility.py`, `barriers.py`, `allocation.py`, `regimes.py`, `dma.py`, `composite.py`, `pairs.py`, `microstructure.py`, `dml.py`, and `sequence.py`. Shared panel/data, date validation, statistics and portfolio accounting remain explicit helpers. Background jobs use the existing Studio JobStore with module-owned result and upload directories. Four pytest files cover data/API, math, feature execution and contract/causality regressions.

## Implemented changes

- Strict ticker validation including partially unknown lists; one requested ticker stays one. No fabricated S&P 500 universe, demo data or alternate Research-export price source. Missing quotes/returns remain missing. `as_of_date` limits observed price history. Current market cap is excluded from historical model features; missing helper caps return null, never one.
- Daily frequency is explicit; unsupported frequencies and undeclared feature inputs fail. Latest sector metadata is disclosed as time-invariant. Backend routes are correctly wired in the existing API helper; frontend layout/renderers were not rebuilt.
- F01: date-group CPCV, event-overlap purge/embargo, assembled complete paths, non-overlapping horizon label-payoff diagnostics, with simple-return compounding; actual CSCV PBO and deflated Sharpe require a caller-supplied dated strategy trial matrix. They return an unavailable reason when no matrix is supplied.
- F02: nested chronological validation selects models/ensemble weights before holdout; training-only median imputation; actual Optuna TPE and manual estimator configuration; equal/time-decay sample weights; formation-history notional/sector filters; latest feature-date predictions refit on matured labels; genuine SHAP values and attribution, no importance-as-SHAP substitutes.
- F03: per-horizon future squared-return targets and purged validation; interval calibration before holdout; real HAR Ridge/GBM and cross-asset HAR-X ElasticNet, plus explicit one-step ARCH family selection; corrected GJR/APARCH news-impact formulas and explicit ARCH candidate failures. Removed outcome-based intervals and unsupported neural/macro/jump claims.
- F04: actual high/low event paths; same-bar ordering ambiguity stays null; primary side observable at formation; purged out-of-fold meta probabilities; disjoint quantile training/calibration/test; actual path reruns for barrier sensitivity. Unsupported directional-barrier and Kelly controls removed.
- F05: true HRP bisection, NCO and constrained minimum variance; actual covariance choices and binding position/sector bounds; Black-Litterman views including zero views; historical monthly refits; next-close execution and actual turnover costs. Equal-weight reference prior is disclosed, never called market-cap equilibrium.
- F06: train-only scaler/HMM/GMM, causal forward filtering with no backward smoothing; out-of-sample classifier agreement; rolling PC1 variance and genuine correlation network density. Removed fabricated random-graph and strategy attribution claims.
- F07: calibrated model members, date-batched updates only after complete forward-label maturity; chosen member library and method honoured; actual squared-error simplex updates/regret. Removed false probabilistic bands and pruning claims. Static BMA is explicitly equal-prior weighting.
- F08: training-only transforms and historical rolling IC/IC-IR/shrinkage weights; historical re-selection, lagged execution and turnover costs. No full-period medians or same-period weight fitting.
- F09: actual statsmodels Engle-Granger formation tests; fixed formation-selected pair evaluated out of sample; static/rolling OLS/Kalman methods; configured entry/exit; observed portfolio returns and costs. No heuristic called ML, copula or RL.
- F10: historical signal panels and daily forward IC; rolling OLS market-residual IVOL; Roll on price changes with quote-price units; current snapshots remain null where undefined; historical daily portfolios with lag/cost accounting. Relative volume is not shares-outstanding turnover; notional is native quote currency, not USD.
- F11: date-purged expanding cross-fit DML residualization, HC3 inference, explicit unidentified-factor reasons, conditional associations rather than causal rule labels. Removed fabricated causal-network/performance panels.
- F12: actual CPU PyTorch PatchTST, iTransformer, LSTM and MLP training; real depth/heads/dropout/epochs, ticker-isolated windows, training-only preprocessing, purged test dates and measured runtime. Training requests serialize around global PyTorch RNG initialization.

## Old-file fate

| Old path | Fate |
|---|---|
| core/analytics.py | Removed after graph, rg, feature import/manifest and route registration checks; implementations split into feature engines |
| core/performance.py | Retained shared helpers; tied Spearman ranks corrected |
| registry.py | Retained lazy entry point and authoritative manifest |
| api/ml_api.py V2 handlers | Moved to dedicated ml_v2.py; V1 retained |
| review.md, upgrades.md, speed upgrades.md, gap_classification.md | Retained historical evidence with superseded banners |
| schemas/__init__.py, utils/__init__.py | Retained empty namespace files; no alternate implementation |
| frontend registry/primitives | Retained for Claude; no frontend rebuild |

## Known limitations and excluded features

- Local inventory contains 10,776,471 daily observations/4,157 symbols, 122,111 hourly rows/23 symbols, 12,368 macro rows and 26,190 Fama-French dates. Macro/FX/factor data exist. Price availability is not a release-vintage guarantee. Historical macro modelling without verified release timestamps/vintages is excluded; FX conversion and stock-borrow financing are not integrated into these native-currency portfolios.
- Daily Close series are used as stored; dividend-inclusive total-return and corporate-action adjustment guarantees are not asserted.
- Present-day universe/sector metadata do not provide historical constituents, complete delisted coverage or historical sector membership. No survivorship-free global-universe claim is made. Missing held returns fail valuation.
- Supported feature/model subsets are intentional: no classification/triple-barrier CPCV; no GINN/TFT/Mamba/PPO, HERC, copula-trained pair classifier, Student-t HMM, calibrated uncertainty split, tick/order-flow analytics, FF3/FF5 IVOL or cross-feature auto-pruning. Available data alone does not make these implementations complete. Unsupported options are removed/rejected, not represented by proxies.
- CPCV path curves are hypothetical label-direction payoff diagnostics, not executable next-close portfolio backtests.
- PBO needs actual trial configurations; CPCV paths are not trial strategies. CSCV/DSR assumptions and trial dependence limit interpretation.
- DML HC3 inference does not establish causal identification or date-cluster robustness. Conformal coverage with dependent financial observations is not guaranteed.
- Jobs persist state/results; active estimator cancellation prevents job result publication but does not interrupt numerical fitting. Automatic resumption of interrupted estimators and persisted trained-model checkpoints are not implemented.
- F08 scores include the observed live tail while fitting weights only on matured historical labels. F01 optional embargo sensitivity reruns actual CPCV at 0/5/10/21 sessions. Cross-feature artifact routing is excluded rather than advertised.
- Backend dependency ranges are retained; a full deployment lockfile is not created. Torch is enabled in requirements. Existing dependencies include Optuna and SHAP.

## Verification commands and results

Commands run from backend unless stated otherwise:

1. `OMP_NUM_THREADS=1 PYTHONPATH=. /tmp/ml-v2-check-env/bin/python -m pytest tests/test_ml_v2_*.py -q --tb=short`: 40 passed; third-party Starlette/SHAP deprecation warnings. Environment is Python 3.11, system packages plus torch 2.14.1, optuna 4.9.0, shap 0.51.0.
2. `OMP_NUM_THREADS=1 PYTHONPATH=. /tmp/ml-v2-check-env/bin/python tests/ml_v2_local_smoke.py`: all twelve features exercised on eight actual local symbols, 756-session lookback; one-epoch MLP smoke is execution proof, not predictive validation. Sector cap disabled explicitly for SPY because sector metadata is unavailable. Initial reporting script used the wrong summary key and was corrected.
3. Frontend `npm test -- --runInBand`: 41 suites, 152 tests passed after removing obsolete assertions importing deleted algorithm/composition stores. The live data persistence assertion remains.
4. Frontend `npm run lint`: passed, zero errors/20 existing warnings after excluding generated output assets and repairing static component/viewport synchronization violations.
5. Frontend `npm run build`: passed: production compilation, TypeScript and page generation. ReportCard/SignalPage generic and union narrowing repaired; existing Studio JS API/scale types and test mocks corrected without disabling checks.
6. Frontend `npx tsc --noEmit --pretty false`: passed after correcting Studio test props/context mock typing, API option defaults and financial-scale JSDoc. No type-check disabling was introduced.
7. Browser end-to-end/console check: not performed at user's request. No browser automation ran.

## Commits and scope

Earlier logical commits: 5e29ca10 (routes/data honesty), c44d82f1 (historical purging), ecb7ef6b (meta-label/conformal leakage), 839d7beb (split engines/sequence training). Intermediate API work was included by a concurrent unrelated commit 76df0cff; history was preserved. Final rebuild changes are committed in explicit ML-owned path groups. Research backend and all other V2 modules are preserved. User explicitly authorized the separate minimal frontend build/test repairs; these are recorded separately.

Final authorized frontend verification repairs: stale tests for deleted stores removed (live data persistence test retained); explicit generic/union narrowing; missing test props and canvas overload typing; financial-scale return JSDoc; existing Studio option defaults; component definitions hoisted with props; viewport state synchronized in a cancellable animation frame; generated `output/**` excluded from lint. No frontend layout or feature renderer rebuild.

Removed unused pooled-row portfolio statistics, final-holdout tuning grid and obsolete attribution helpers only after graph discovery (zero inbound callers) and repo-wide Python rg checks; feature import/manifest tests remain passing. Historical README content was preserved with a superseded status banner.

## Review disposition

| Item | Disposition |
|---|---|
| B1 | Correct ML route and own symbol search; frontend manifest rendering remains Claude-owned |
| B2 | Unknown/partially unknown universes fail, never substituted |
| B3 | Date ordering, horizon purging, train-only transformations and look-ahead regressions |
| B4 | Supported controls execute; unsupported controls removed/rejected rather than ignored |
| A1/A2/A3 | Snapshot cap feature removed, price gaps preserved, false SP500/default substitutions rejected |
| A4 | Time-invariant sector snapshot explicitly disclosed |
| A5 | Allocation uses requested assets; incomplete histories/constraints fail explicitly |
| A6 | Active model/data failures raise or expose warning/reasons; obsolete proxy helpers removed |
| A7 | Existing Studio jobs, durable results, upload validation, cancellation and API regressions |
| A8 | Feature engines split; old-doc/namespace fates recorded; historical evidence retained |
| A9 | Four test files with golden accounting, independent OLS/HRP checks and temporal guards |

Supplementary run: `OMP_NUM_THREADS=1 PYTHONPATH=. /tmp/ml-v2-check-env/bin/python -c 'from app.services.ml_v2.registry import run_feature; r=run_feature("01",{"symbols":["AAPL","MSFT","AMZN","GOOGL"],"max_symbols":4,"lookback_days":500,"cpcv_n_groups":4,"calculate_embargo_sensitivity":True}); print(r["status"],r["charts"]["embargo_sensitivity"])'`, verifies actual reruns at four embargo settings.

Charts using matrix adapters display up to 80 assets, and compact record adapters sample rows at declared call-site caps (typically 500). These visualization summaries do not constrain the numerical allocation universe. Full model checkpoints and cross-feature learned-artifact routing remain outside the supported contract.

Final change commits: `349ec94a` (ML calculation/contract rebuild), `ad94905b` (authorized frontend verification repairs); `4a21b431` (CPCV/ARCH diagnostic corrections); this documentation is a separate logical commit. The Studio API JS helper was previously ignored by the broad `lib/` rule and was explicitly tracked so its type/interface fix is reproducible.
