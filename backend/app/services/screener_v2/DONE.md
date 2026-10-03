# Screener V2 rebuild

Status: backend rebuild remains in progress. A repository-wide FX/macro and currency-metadata audit is correcting the initial available-data assessment. Whole-project Phase 6 is not green: unrelated frontend Jest/lint failures remain, and the frontend/browser rebuild is reserved for Claude. Frontend rebuilding is reserved for Claude under playbook commit `9451bc32`. Only route wiring and removal of fabricated results are in scope here.

## Architecture before and after

Previously, eight feature wrappers depended on a single large `core/analytics.py`, current-snapshot scores were reused across historical returns, failures could produce frontend demo results, and membership differences had no persistent baseline.

The backend now separates common response handling, statistics, technical estimators, statement fundamentals, point-in-time panels, screening, formulas, composite training, academic strategies, portfolio simulation, performance validation, alerts, relative valuation, exports, and SQLite state. Feature modules own backend input/output declarations. The registry stays unloaded at package import and dispatches computations inside a request-scoped as-of context. The HTTP router owns symbol search, capped CSV handling, background jobs, saved definitions, uploaded universes, recurring interval dispatch and run history.

## Implemented changes

- Corrected the Screener API route and request envelope; removed demo-result generation and demo fallback after failed runs.
- Rejected partially unknown ticker lists and fake S&P 500 aliases. Required the primary market parquet instead of the research submission export.
- Retained missing prices, volumes and returns. Removed forward-filled prices and zero-return substitution. Missing held-position or execution prices cause an explicit invalid-data error, rather than a fabricated payoff.
- Added dated market access and conservative report availability at period end plus 90 days. Statement flows use four complete consecutive quarters or a matching fiscal annual report. Current vendor `.info` valuation snapshots do not become historical observations.
- Corrected Wilder initialization, zero-gain/zero-loss RSI, Bollinger population deviation, observed dollar volume, OBV regression slope and FF3 residual volatility using statsmodels. Removed the universe-beta substitution.
- Replaced static-selection historical portfolios with per-formation reselection, next-session execution, drifted holdings, and costs proportional to actual traded notional. Added bounded stock attribution and real position entry/exit records. Benchmark data must be observed SPY data.
- Implemented combinatorially symmetric cross-validation PBO with all half-partition train/test combinations and out-of-sample rank logits. Offset strategies are explicit candidates; benchmark-beating fractions are not PBO.
- Removed the current-cross-section IC-IR bootstrap and fake Monte Carlo PBO. IC-IR and sklearn Ridge weights train on historical monthly formation features with fully matured forward labels. Unavailable training dates hold cash and are disclosed; no weights are substituted.
- Formula rank is unit scaled. Missing formula inputs remain missing. OHLC history uses actual corresponding columns, and fundamental lags use dated trading-session series. Formula signal comparisons use disjoint matured forward-return intervals.
- Renamed sector breakdowns honestly. Removed named approximate academic strategies that could not meet their definitions. Graham Net-Net uses the two-thirds NCAV condition. Greenblatt capital uses observed statement inputs. Piotroski follows the original nine conditions, preserves unknown criteria, and does not substitute total debt for long-term debt including its current portion. Altman Z and Z-double-prime use their distinct market/book equity measures.
- Relative valuation no longer substitutes another focus ticker. Peer scopes validate membership, historical ratios are repriced from available statements, and sector heatmaps compare against the full universe instead of averaging within-sector ranks.
- Added SQLite saved definitions, reusable universes, dated run history, true membership/rank differences and persisted directional alerts. Initial observations establish baselines. Definitions and universe memberships are immutable under an existing id.
- Added sandboxed UUID-named universe uploads with UTF-8/CSV validation, symbol validation and a 2 MB size cap.

## Final audit corrections

- Added atomic SQLite claims for recurring schedules, durable job identifiers and logged/persisted dispatch failures. Reused Studio JobStore with owned Screener storage and source-file versions in job identity.
- Preserved every selected export row, requested columns and nulls; pandas quotes CSV/TSV delimiters/newlines. JSON and newline-separated ticker formats are supported. Unsupported export features are rejected.
- Removed copied `adj_close`, HAR forecast naming and unused full-sample macro regime helpers. `yang_zhang_vol_21d_estimate` is a trailing 63-session historical estimate, requiring complete observations. ADX uses its own configured smoothing period; missing inputs cannot manufacture crossover events.
- S2/S3/S4 pass the requested universe into historical simulations, not today's filtered stocks. Numerical filters are applied on each formation date.
- Removed ROA substitution under ROE. Annual growth requires adjacent fiscal years. Enterprise ratios no longer assume missing preferred/minority claims are zero. The default core valuation formula explicitly uses net-income yield, FCF yield, inverse P/B and inverse P/S.
- S3 correlations use configured component names; sector breakdown uses the configured composite. `composite_raw_score` preserves the weighted sum before scaling. Zero/nonfinite weights, duplicate names and unavailable focus tickers are errors.
- S7 cards now contain absolute ratios, sector/universe comparisons and dated own-history percentiles/counts. The 252/756/2520 selector controls actual history. SciPy rerating regression uses observed weekday spacing, with exchange-holiday limitations disclosed.
- Added actual volume and daily factor series to formula operators. Relabelled approximate academic templates by their expressions and corrected Net Payout Yield's duplicate dividend component.
- API errors distinguish missing datasets/artifacts (503), bad inputs (422) and unknown features/jobs (404). Future/zoned as-of dates and invalid indicator windows are rejected; input overrides preserve declared bounds.

## Old-file fate

| Old path | Fate |
| --- | --- |
| `core/analytics.py` | Removed after graph, text-reference, route-mount, import and pytest checks; implementations moved to domain modules, unused proxy helpers removed. |
| `core/data_loader.py` | Retained and hardened; strict universe validation and dated local access. |
| `core/performance.py` | Retained for file-versioned caches; no stale-price or fabricated zero-return fills. |
| `features/feature_01.py` through `feature_08.py` | Retained as feature entry points with declarations and domain imports. |
| Frontend `customPagePrimitives.jsx` | Retained for Claude; only fabricated results were removed. No form, layout or visual rebuild. |
| Frontend `registry.js` | Retained for Claude; backend manifest is the authoritative new contract. |
| `review.md`, `missing.md` | Historical audit/checklists; superseded by this document and the central review. |
| `schemas/`, `utils/` | Removed after graph showed no inbound references, repository text checks found no imports, route registration was confirmed and import/contract tests passed. |

## Data and estimator rules

Every formation uses observations available on that date. Forward labels must mature before training. Simulator signals execute at the next observed session close; execution-session returns belong to previous holdings. Commissions apply to gross traded notional after drift, including initial purchases. PBO compares aligned strategy candidates, not a strategy with its benchmark.

Libraries used are already present in requirements: pandas/numpy for panels, scipy for ranks/regression primitives, statsmodels for regression estimators, and scikit-learn for Ridge. No new dependency was required. SQLite is the Python standard library. Versioned caches avoid reusing changed data files, and cross-strategy backtests share formation panels.

Piotroski definitions were checked against the [original paper](https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf). CSCV follows [Bailey and colleagues](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

## Known limitations

- Local fundamentals do not provide historical filing vintages, revision timestamps or a complete pre-2021 panel. A 90-day lag is conservative availability modelling and cannot remove restatement bias.
- No reliable historical index membership or complete delisting payoff/corporate-action history exists. A missing held-position price invalidates that backtest; there is no guessed liquidation or zero return. Results are conditional on the selected local universe.
- Sector/industry descriptions are current classifications; historical classification changes are unavailable. Historical classification filtering and sector-neutral execution are rejected. Industry groups are a disclosed static mapping of vendor industry labels, not verified company-level GICS.
- Forward analyst P/E and historical float data are unavailable and are not reconstructed from current snapshots.
- Piotroski F-score is unknown when original required inputs, including current portions of long-term debt or equity issuance, are absent. Missing conditions are reported individually.
- Dogs of the Dow lacks historical Dow membership. Mohanram and ERP5 lack complete required histories/inputs. Approximate QMJ, dual/twin momentum, conservative formula, quantitative momentum and named VC2 outputs were removed; the explicit five-ratio `value_composite` is labelled by its actual definition.
- Email delivery has no configured provider. Interval schedules run while the backend is alive; this is not a managed external cron service. One missed interval produces one catch-up dispatch. A process crash between claiming and dispatching can miss that interval; dispatch errors are persisted and logged.
- The market source manifest describes Close as an adjusted-close proxy without a corporate-action guarantee. Backend metadata discloses source Close returns and unverified total-return status; copied adjusted-close columns and guaranteed total-return claims were removed.
- Enterprise ratios require observed debt, preferred equity and noncontrolling interests. Missing claims remain unknown. The default valuation blend uses its disclosed net-income yield, FCF yield, inverse P/B and inverse P/S definition, with all four inputs required.
- External factor-zoo comparisons and HAR forecasts are absent. S3 now exposes prior-observation VIX regime attribution with a fixed threshold and explicit missing states. Honest sector/local-signal/trailing-estimate outputs replace those claims. Formula historical operators support observed OHLCV, return horizons, seven statement ratios/market cap and daily factors; other fields fail explicitly.
- CSCV requires variable aligned candidate returns. Zero-variance splits produce an unavailable reason and no probability. Invalid partitions or insufficient samples are errors. RF-dependent statistics remain null without observed RF data.
- Historical classification filtering and sector-neutral composites are rejected even when the current snapshot has classification labels; those current labels cannot be used as historical evidence.
- Frontend forms, renderers, layout, polish and browser completion are reserved for Claude. Backend declarations provide the handoff contract.

## Backend feature handoff

| Feature | Authoritative behavior |
| --- | --- |
| S1 | Dated numerical filters, observed technical estimators and statement-derived fundamentals; ranking, funnel, classifications, quick look and saved definitions. |
| S2 | Safe AST expressions and supported true historical operators; next-session IC with disjoint matured labels; dated formula backtests and descriptive templates. Output is `historical_local_signal_ic`. |
| S3 | Manual/equal and historically trained IC-IR/Ridge weights; configured correlation, raw/scaled scores, decomposition and honest sector breakdown. Output is `composite_vs_spy_backtest`. |
| S4 | Thirteen declared strategies; actual Greenblatt capital, two-thirds NCAV, original Piotroski unknown handling, separate Altman variants and dated backtests. Approximate named strategies were removed. |
| S5 | Per-formation reselection, next-session execution, actual turnover costs, stock/episode attribution, holding/offset/weekday sensitivity and real CSCV. Disabled or undefined PBO has an explicit status. |
| S6 | Observed threshold/crossover alerts, persistent entry/exit/rank differences and matured directional-alert precision. Condition replay is separately labelled. |
| S7 | Actual absolute ratios plus sector, universe and own-history comparisons, dated coverage and selectable history windows. Missing ratios remain null. |
| S8 | Lossless CSV/TSV/JSON/ticker downloads, change reports against real saved baselines and an owned API endpoint. |

`GET /api/screener-v2/features` is the frontend contract: inputs declare key, type, default, label, group, help and applicable constraints; outputs declare key, response source, render type, primary flag and label. The fourth backend test file validates this contract. Claude should consume these declarations rather than the old hardcoded frontend catalog.

Domain modules keep shared estimators, panels and execution in one implementation instead of duplicating them across eight feature modules. This preserves one entry module per feature. No additional framework or dependency was required.

## Final verification

Failed intermediate checks were repaired and rerun. These are the final results:

| Directory | Exact command | Result |
| --- | --- | --- |
| `backend` | `PYTHONPATH=. python3.11 -m pytest tests/test_screener_v2_*.py -q --tb=short` | 53 passed in 17.08 seconds; three dependency/lifecycle deprecation warnings. |
| `backend` | `PYTHONPATH=. python3.11 -m compileall -q app/services/screener_v2 app/api/screener_v2.py` | Passed. |
| repo root | `git diff --check` | Passed. |
| `frontend` | `npm test -- --runInBand src/components/screener-v2/__tests__/screenerV2.test.ts` | 1 suite, 2 tests passed. Covers job URL/envelope/publication and error propagation. |
| `frontend` | `npm run lint -- src/components/screener-v2` | Passed. |
| `frontend` | `npm run build` | Passed: compilation, TypeScript and 179-page generation; compilation took 18.6 seconds. |
| `frontend` | `npm test -- --runInBand` | 40 suites passed, one unrelated Studio suite failed because `../algorithmLabStore` is absent. All 152 executed tests passed. |
| `frontend` | `npm run lint` | Failed outside Screener: 13 errors and 26 warnings, including existing effect/state errors in CommandBar and Studio components. No unrelated frontend changes were made. |

The four backend test files cover independent portfolio/cost/CSCV/Piotroski/Altman/statement-valuation goldens, future-data mutation invariance, matured training labels, missing prices, formula nulls, strict universes, manifest/import boundaries, state/idempotency, schedules, alerts, complete exports and an actual owned job-route feature run. These tests cannot correct missing historical vintages or survivorship bias.

Exact live smoke command, from `backend`:

```bash
PYTHONPATH=. python3.11 - <<'PY'
import json,time
from app.services.screener_v2.registry import run_feature
for feature in ['01','02','03','04','05','06','07','08']:
    start=time.monotonic()
    result=run_feature(feature,{'tickers':['AAPL','MSFT','NVDA'],'watchlist':'AAPL MSFT NVDA','lookback_days':126,'top_n':1,'strategy_perf_limit':2,'run_full_pbo':feature=='05','pbo_partitions':4})
    json.dumps(result,allow_nan=False)
    print(feature,result['status'],round(time.monotonic()-start,2),'seconds',flush=True)
    if feature=='05': print('CSCV',result['meta']['pbo_status'],result['tables']['cscv_pbo'][0]['pbo'],flush=True)
PY
```

All eight returned `ok`, with finite JSON serialization. S1-S8 durations were 4.80, 1.53, 1.22, 1.56, 9.70, 0.15, 0.21 and 0.13 seconds on the three-stock sample. S5 computed CSCV PBO 1.0 over five candidates/four partitions/six combinations. This verifies execution, not profitability or full-universe latency.

No browser rebuild/test is claimed. The active user goal explicitly excluded browser checks, and playbook commit `9451bc32` reserves frontend rebuilding for Claude. Thus the original full Phase 6 frontend gate remains outside this backend handoff. No other V2 or V1 screener implementation was modified.

## Logical commits

- `3d2270fb`: API wiring and fabricated-fallback removal.
- `60264c1a`: dated access and missing-observation preservation.
- `4b79dfdb`: module split, historical training and portfolio execution.
- `5c2cbcbe`: saved screens, schedules, uploads, exports and durable job wiring.
- Numerical/contract and documentation follow-ups are reported in the final handoff.

## Repository-wide data audit, reopened 2026-10-03

The earlier lack-of-FX assessment was incorrect. `backend/data/canonical/fx_daily.parquet` contains 83,894 observations across 29 pairs, from 2015 to February 2026, including USDINR, USDHKD, USDJPY, EURUSD and GBPUSD. `factors/data/processed/category7_macro_regime.parquet` contains 12,368 dated rows and 22 columns, including Treasury yields, VIX, credit spreads and exchange rates. Five smaller macro caches also exist under `backend/data/parquet_cache`. These files are real available sources and must be evaluated before removing FX or macro functionality.

`canonical/asset_metadata.parquet` contains five dataset inventory rows, not per-instrument currency metadata. The fundamentals master and per-symbol shards contain one ambiguous `currency` field, without `financialCurrency`, quote currency or exchange metadata. IHG.L is labelled USD despite being a London listing. Therefore the recently added USD eligibility filter is not a validated trading-currency filter; the incorrect USD-only filter has now been removed, restoring equities from the observed-price/fundamentals inventory. Integrating supported FX conversion remains outstanding. No completion claim rests on that filter.

Added versioned FX loading and as-of cutoffs for both FX and macro reads. Macro observation timestamps do not establish original release timestamps for revised CPI/recession data; contemporaneous daily market series must be distinguished from revised economic series before historical regime attribution. S3 now integrates a separate prior-observation VIX attribution table; monthly/revised economic regimes remain unsupported.

Audit verification: `PYTHONPATH=. python3.11 -m pytest tests/test_screener_v2_*.py -q --tb=short` from `backend`: 53 passed, three existing deprecation warnings, 17.21 seconds. `git diff --check`: passed. New regressions protect FX/macro as-of bounds and prior-day VIX attribution/expiry. Source manifest adjustment claims remain unverified; backend return-basis metadata now discloses this.

The whole-repository schema audit examined 5,319 parquet files in 15 directories (zero read errors), plus headers of 1,857 CSV files and 35 data JSON files. Separate quote/financial currency and ADR ratio fields were not found. Per-symbol fundamentals shards repeat the same ambiguous currency field. One research-export hourly panel has Country, which does not establish trading units or reporting currency. The FX quotes end in January/February 2026 depending on pair; treating them as current quotes for later equity dates would be a stale-rate fallback and is prohibited. The master source manifest also states currency adjustment is not applied.

Numerical remediation commit: `617912a7` Correct Screener V2 financial calculations and historical validation. This includes the dated FX loader, observed prior-VIX attribution and removal of the invalid USD-only discovery restriction. Currency conversion and source compatibility remain open, as documented above.
