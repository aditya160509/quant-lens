# Screener V2 rebuild

Status: the backend remediation, explicit FX/unit contract and scoped verification are implemented. Unsupported inputs are unavailable or rejected instead of estimated. Whole-project Phase 6 is not green because unrelated frontend Jest/lint failures remain. Frontend rebuilding and browser work remain reserved for Claude under playbook commit `9451bc32`; this backend handoff does not claim those gates passed.

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
| `backend` | `PYTHONPATH=. python3.11 -m pytest tests/test_screener_v2_*.py -q --tb=short` | 63 passed in 19.86 seconds; three dependency/lifecycle deprecation warnings. |
| `backend` | `PYTHONPATH=. python3.11 -m compileall -q app/services/screener_v2 app/api/screener_v2.py` | Passed. |
| repo root | `git diff --check` | Passed. |
| `frontend` | `npm test -- --runInBand src/components/screener-v2/__tests__/screenerV2.test.ts` | 1 suite, 2 tests passed. Covers job URL/envelope/publication and error propagation. |
| `frontend` | `npm run lint -- src/components/screener-v2` | Passed. |
| `frontend` | `npm run build` | Passed: compilation, TypeScript and 169-page generation; compilation took 13.5 seconds. |
| `frontend` | `npm test -- --runInBand` | 40 suites passed, one unrelated Studio suite failed because `../algorithmLabStore` is absent. All 151 executed tests passed. |
| `frontend` | `npm run lint` | Failed outside Screener: 13 errors and 27 warnings, including existing effect/state errors in CommandBar and Studio components. No unrelated frontend changes were made. |

The four backend test files cover independent portfolio/cost/CSCV/Piotroski/Altman/statement-valuation goldens, future-data mutation invariance, matured training labels, missing prices, formula nulls, strict universes, manifest/import boundaries, state/idempotency, schedules, alerts, complete exports and an actual owned job-route feature run. These tests cannot correct missing historical vintages or survivorship bias.

Exact final live smoke and panel benchmark command, from `backend`:

```bash
PYTHONPATH=. python3.11 - <<'PY'
import time,json,tempfile
from pathlib import Path
from app.services.screener_v2.registry import run_feature
from app.services.screener_v2.core import state
state.STATE_PATH=Path(tempfile.mkdtemp())/'verified.sqlite3'
s=['AAPL','MSFT','NVDA'];m={x:{'quote_currency':'USD','financial_currency':'USD','quoted_units_per_ordinary_share':1} for x in s}
for f in range(1,9):
    t=time.perf_counter();r=run_feature(str(f),{'tickers':s,'watchlist':s,'instrument_metadata':m,'lookback_days':126 if f==5 else 60,'top_n':1,'strategy_perf_limit':2,'run_full_pbo':f==5,'pbo_partitions':4})
    json.dumps(r,allow_nan=False)
    print('feature',f,r['status'],round(time.perf_counter()-t,3),'asof',r['meta']['as_of_date'],flush=True)
    if f==5: print('PBO',r['meta']['pbo_status'],r['tables']['cscv_pbo'][0]['pbo'],flush=True)
for n in [30,100,500]:
    t=time.perf_counter();r=run_feature('01',{'max_symbols':n})
    print('panel',n,round(time.perf_counter()-t,3),'filtered',r['summary_cards'][1]['value'],flush=True)
PY
```

All eight returned `ok` and serialized to finite JSON. The default date was the observed SPY calendar date, 2026-01-28. S1-S8 durations were 6.804, 0.812, 0.661, 1.013, 10.380, 0.174, 0.240 and 0.159 seconds. S5 includes real CSCV computation: status `computed`, five candidates, four partitions, six combinations, PBO 1.0. This verifies calculation and execution, not profitability. Currency/share declarations for these three US ordinary-share listings are explicit test inputs; the backend does not fabricate them.

The 30/100/500-symbol panel computation timings were 0.311/0.683/2.976 seconds. These measure computation, **not successful full-universe rankings**: unconfigured global pools had zero rows after the USD penny-stock filter because quote denomination/conversion or contemporaneous prices were unavailable. Missing financial/share metadata also leaves valuation and the value-containing core score unavailable. No filled rate, native-notional-as-USD substitution or alternative score blend is introduced to make those results look populated.

No browser rebuild/test is claimed. The active user goal explicitly excluded browser checks, and playbook commit `9451bc32` reserves frontend rebuilding for Claude. Thus the original full Phase 6 frontend gate remains outside this backend handoff. No other V2 or V1 screener implementation was modified.

## Logical commits

- `3d2270fb`: API wiring and fabricated-fallback removal.
- `60264c1a`: dated access and missing-observation preservation.
- `4b79dfdb`: module split, historical training and portfolio execution.
- `5c2cbcbe`: saved screens, schedules, uploads, exports and durable job wiring.
- `617912a7`: numerical correctness, observed FX loading, prior-VIX attribution and additional regressions.
- `268d9989`: rebuild verification and repository-wide data audit.
- `96ff9f0c`: observed FX, explicit share/financial units, common session calendars and 63 regression tests.

## Repository-wide data audit, reopened 2026-10-03

The earlier lack-of-FX assessment was incorrect. `backend/data/canonical/fx_daily.parquet` contains 83,894 observations across 29 pairs, from 2015 to February 2026, including USDINR, USDHKD, USDJPY, EURUSD and GBPUSD. `factors/data/processed/category7_macro_regime.parquet` contains 12,368 dated rows and 22 columns, including Treasury yields, VIX, credit spreads and exchange rates. Five smaller macro caches also exist under `backend/data/parquet_cache`. These files are real available sources and must be evaluated before removing FX or macro functionality.

`canonical/asset_metadata.parquet` contains five dataset inventory rows, not per-instrument currency metadata. The fundamentals master and per-symbol shards contain one ambiguous `currency` field, without `financialCurrency`, quote currency or exchange metadata. IHG.L is labelled USD despite being a London listing. Therefore the recently added USD eligibility filter is not a validated trading-currency filter; the incorrect USD-only filter has now been removed, restoring equities from the observed-price/fundamentals inventory. Supported USD conversion has now been integrated through explicit instrument metadata; missing finance/share-unit facts are not inferred. No completion claim rests on the removed USD filter.

Added versioned FX loading and as-of cutoffs for both FX and macro reads. Macro observation timestamps do not establish original release timestamps for revised CPI/recession data; contemporaneous daily market series must be distinguished from revised economic series before historical regime attribution. S3 now integrates a separate prior-observation VIX attribution table; monthly/revised economic regimes remain unsupported.

Audit verification: `PYTHONPATH=. python3.11 -m pytest tests/test_screener_v2_*.py -q --tb=short` from `backend`: 53 passed, three existing deprecation warnings, 17.21 seconds. `git diff --check`: passed. New regressions protect FX/macro as-of bounds and prior-day VIX attribution/expiry. Source manifest adjustment claims remain unverified; backend return-basis metadata now discloses this.

The whole-repository schema audit examined 5,319 parquet files in 15 directories (zero read errors), plus headers of 1,857 CSV files and 35 data JSON files. Separate quote/financial currency and ADR ratio fields were not found. Per-symbol fundamentals shards repeat the same ambiguous currency field. One research-export hourly panel has Country, which does not establish trading units or reporting currency. The FX quotes end in January/February 2026 depending on pair; treating them as current quotes for later equity dates would be a stale-rate fallback and is prohibited. The master source manifest also states currency adjustment is not applied.

Numerical remediation commit: `617912a7` Correct Screener V2 financial calculations and historical validation. This includes the dated FX loader, observed prior-VIX attribution and removal of the invalid USD-only discovery restriction. This was an intermediate checkpoint. Currency conversion is implemented in the 2026-10-04 completion section; source compatibility remains an explicit constraint.

## FX and calendar completion, 2026-10-04

`core/currency.py` centralizes request-scoped instrument declarations and exact-date observed USD rates. Supported direct/inverse USD pairs come from the audited canonical FX panel. GBp and ZAc are explicit hundredth units; ILA requires an actual USD/ILS quote and remains unavailable without one. Currency pegs are not conversion data. No FX observations are filled or carried forward.

The shared backend input contract now includes `instrument_metadata` and `calendar_ticker`. Per symbol, metadata can declare `quote_currency`, `financial_currency`, and `quoted_units_per_ordinary_share`. For an ADR representing eight ordinary shares, the final multiplier is 1/8. Declarations assert compatibility throughout the requested history, not merely today. Invalid JSON shape, unsupported keys and nonpositive/nonfinite share units are rejected before job creation. Source fields, when present, use eligible report dates; future metadata cannot alter past valuations. A bare local USD-denominated US quote can establish quote USD, but it does not establish financial currency or ADR units.

Market values are USD. Valuation multiples compare the USD-converted quoted-share value against statements in their explicitly declared reporting currency. Enterprise value converts observed claims using the same spot basis. Native statement amounts retain `financial_currency`; dimensionless accounting ratios do not need a market currency guess. Graham compares NCAV and market value in the same statement currency. Historical valuations and formula market-value series apply the same quote-unit/FX rules. Gross Share Issued is not substituted for outstanding Ordinary Shares Number. Market value explicitly uses the most recently eligible statement share count, not an undisclosed current vendor share count; observation date and calculation basis are exported.

Dollar volume, USD price filters and penny-stock exclusion use actual USD-converted prices. SPY beta, residual FF3 volatility, SPY-relative returns and portfolio returns use USD. Technical price/momentum fields and training targets remain native quote returns, as disclosed in response metadata. The input-selected observed calendar controls indicator and portfolio session grids; default is SPY. The default as-of date comes from that calendar, not a newer unrelated instrument in the global file. Venue quote gaps remain unknown, and missing execution/held prices still reject a run. Instrument metadata is cached within a request as a narrow frame, without caching future report values as historical metadata. FX file versions participate in background job identity.

Additional regressions cover direct/inverse FX, minor quote units, no rate filling, ADR/share multipliers, differing reporting currency, USD turnover/portfolio returns, USD dollar volume/beta, missing-rate rejection, missing financial-unit metadata, future metadata invariance, default date isolation, invalid job inputs and Sunday-through-Thursday calendars for both indicators and execution.

### Remaining source limitations, not pending implementations

- The repo has FX history but incomplete exact-date coverage. For example, USDINR lacks several stock-trading Fridays in 2025 and some holidays. Primary market and local pair/alias price files also lacked the checked missing Friday. A real INR screen for RELIANCE on 2026-01-28 executed with explicit instrument/calendar declarations; affected USD history/backtest windows rejected missing conversion marks. One missing conversion does not become a carried-forward price.
- The audited fundamentals master lacks separate verified quote/financial currency and quote-share unit fields. Consumers must provide accurate instrument declarations for affected valuations; otherwise those numbers and dependent scores remain null with reasons. This does not automatically enrich or certify every instrument.
- There is no historical currency/share-unit change registry or complete venue-calendar registry. Static declarations must be valid throughout the run. A mixed-venue portfolio with missing held/execution quotes is rejected; the backend does not simulate trading a closed exchange using another market's close.
- Corporate-action adjustment provenance and filing/share-count vintages remain limited. USD conversion does not eliminate those data limitations.

Frontend files were not rebuilt or modified in this completion pass. All remaining frontend rendering and full-project Jest/lint remediation belongs to its separately reserved scope.
