# Screener V2 Review: Spec vs Implementation vs Frontend

Date: 2026-09-29
Scope: `backend/app/services/screener_v2/` (spec: `docs/screener features.md`, `docs/screener computation.md`; code: `core/analytics.py` 2,385 lines, `core/data_loader.py` 240 lines, `core/gics.py`, `core/performance.py`, 8 feature files, `registry.py`), `backend/app/api/screener_v2.py` + mount in `backend/main.py:152`, `backend/app/api/screener_api.py` (V1), `backend/app/services/screener.py`, `backend/app/services/screener_quant360.py`, `frontend/src/app/labs/screener-v2/`, `frontend/src/components/screener-v2/`, `frontend/src/lib/api.js`, `backend/tests/test_screener_v2_math.py`.

Smoke check: no smoke runner was re-run in this pass (read-only on code). The module's own docs claim S1-S8 return `status: ok` on a 10-symbol universe. The review below is about whether the numbers are right, whether the UI reaches the backend, and whether what the user sees is real.

---

## 1. Verdict

| Area | State | One line |
|---|---|---|
| Wiring (backend to frontend) | **Broken** | Route exists and is mounted, but the frontend calls a different path with a different body envelope, so every UI run 404s and silently falls back to demo data. |
| Data integrity | Partly honest | Latest-snapshot fundamentals still drive screens/backtests (look-ahead), but it is disclosed in `meta.access_issues` and backtest stats carry a survivorship warning; OHLCV `as_of_date` truncation and 7-field PIT formula history exist. |
| Features 1, 2, 7, 8 | Mostly fine | Gap, YZ vol, configurable indicator periods, `if()` alias, division guard, rebalance-date costs, general ROIC, CSV export all fixed since the July audit. |
| Features 3, 4 | Partly correct | Real composites and 22+ academic strategies, but IC-IR/ridge weights and several named strategies are cross-sectional or proxy implementations. |
| Feature 5 (backtester) | **Wrong** | Not a walk-forward: names are picked once from today's scores and held for the whole window (see B4). Turnover/PBO/weekday are proxies or wrong; no PIT, no delisted correction. |
| Feature 6 (alerts) | Thin | Current-run threshold alerts only; no entry/exit detection, no scheduling, no delivery; performance tracker returns `precision_proxy: None`. |
| Tests | Thin | `backend/tests/test_screener_v2_math.py` has 5 focused regression tests; no golden-number, PIT-guard, or API-contract tests. |
| Frontend | **Misleading** | Wired run path is wrong, so users always see synthetic demo rows, fake funnel counts, and `Math.random()` strategy stats labeled only by a small "LOCAL PREVIEW" tag. |

Bottom line: the backend is in much better shape than the July self-audit left it (duplicate deleted, math fixes landed, routes mounted), but the frontend never reaches it: path and envelope both mismatch, and the catch block renders fake numbers that look like results. Fix order: align the run path and envelope, rebuild the backtester as a true walk-forward (B4), delete or gate the demo fallback, fail loudly on unknown tickers, then finish the IC-IR/strategy-proxy and persistence gaps.

---

## 2. Blockers (fix first)

### B1. Frontend run path and body envelope both mismatch the mounted route
- Backend: `backend/app/api/screener_v2.py:17` defines `prefix="/screener-v2"` with `POST /run/{feature_id}` (`:30`) expecting a `FeatureRequest` body shaped `{"payload": {...}}` (`:20-21`). Mounted in `backend/main.py:152` as `app.include_router(screener_v2.router, prefix="/api")`, so the live URL is `POST /api/screener-v2/run/{id}`.
- Frontend: `frontend/src/lib/api.js:1036-1044` posts the raw form to `` `${API_BASE_URL}/labs/screener/v2/feature/${normalized}/run` ``. Wrong path *and* wrong envelope (raw payload instead of `{payload}`).
- Effect: every workbench Run 404s or 422s. Fix: point `runScreenerV2Feature` at `/api/screener-v2/run/{id}` and wrap the body as `{payload: form}` (or accept raw dicts server-side). Add one API-contract test asserting path plus envelope.

### B2. Silent universe fallback
- `parse_symbols` (`core/data_loader.py:100-120`): unknown tickers are filtered at `:116`, and if nothing remains the function silently returns `universe[:default_limit]` at `:117-118`. A user asking for "XYZ, ABC" gets results on up to 500 unrelated stocks.
- Related bias: the default is 500 symbols (`default_limit=500`, `feature_01.py:39`), i.e. "master" is the top-500 by price-history coverage, not the spec's 5,000-ticker universe. Counts shown ("Universe loaded") reflect the cap, not the market.
- Fix: return 422 listing unknown tickers when the user gave explicit tickers; reserve silent defaulting for the empty/`master` case only. Label capped runs with the cap in the UI.

### B3. Silent demo fallback renders fake numbers as results
- `ScreenerV2Workbench.run()` (`customPagePrimitives.jsx:493-505`) catches *any* fetch failure (including B1) and renders `makeDemoResponse` (`:124-214`) with `status: "preview"`, while the hero tag just says "LOCAL PREVIEW" (`:490`, `:516`).
- The demo data is synthetic: hard-coded tickers/scores (`:95-110`), sinusoidal equity curves (`:112-118`), a fake funnel (4200 to 2600 to 1300 to 180, `:142-148`), universe label "4,000+" (`:130`), and `Math.random()` strategy Sharpes (`:176`). Feature 08 demo even reports the endpoint as `wired: false` (`:210`) against a stale path.
- Fix: on fetch failure show an error state with retry, never a full fake workspace. Keep deterministic preview behind an explicit `?demo=1` flag, watermarked as sample data, and delete the `Math.random()` stat.

### B4. The backtester is a static look-ahead portfolio, not a walk-forward
- `score_backtest` (`analytics.py:1734-1800`) ranks names by *today's* scores (`:1750-1752`) and holds those same names for the whole 756-day window. Nothing is ever reselected. "Rebalancing" just subtracts `cost_bps` every `rebalance_days` (`:1781-1786`), and equal weights come from the daily mean, which is an implicit daily rebalance with no cost.
- Eligibility is checked at the window start (`:1751`), but selection uses end-of-window information. That is look-ahead plus survivorship; disclosing it does not fix it.
- The long-short short leg (`:1776-1779`) skips the eligibility filter.
- The weekday table (`:1841-1866`) compounds only the one-day return on each weekday (`reindex(rebal_dates)`), so it measures a day-of-week return effect, not rebalancing on that day. It also annualizes with 52 and spreads one cost over all observations.
- Every S3/S4/S5 "historical performance" number inherits this.
- Fix: monthly (or `rebalance_days`) loop. At each date t, recompute scores with `as_of_date=t` (the formula engine already supports this for prices and 7 PIT fields), select eligible names, hold to t+1, and charge cost on the turnover actually traded. Weekday sensitivity is then this loop with dates snapped to the weekday. Until PIT fundamentals exist, restrict fundamental-score backtests to the post-2021 window and label them.

---

## 3. Feature-by-feature

Legend: OK = matches spec; WRONG = computes something else under the spec's name; PROXY = explicit stand-in; MISSING = not present.

### S1: Core Multi-Factor Screener Engine (`features/feature_01.py`)
| Spec item | State | Detail |
|---|---|---|
| Universe select, CSV upload route | OK / MISSING | `parse_symbols` handles master/ticker lists; `POST /run/{id}/csv` (`screener_v2.py:39-61`, 2 MB cap) exists but only runs a screen, it does not persist a reusable universe. |
| Descriptive/technical/fundamental filters | OK | `apply_filters` (`analytics.py:711-810`) covers sector/industry/industry-group, 30+ range filters, exchange, dividend, negative-P/E exclusion, penny exclusion, SMA/MACD/OBV toggles; `golden_cross_within_n_days` now uses real event age (`:800-805`). |
| Configurable indicator periods | OK | `periods` dict threads RSI/stochastic/ADX/ATR/Bollinger/MACD/cross-lookback (`analytics.py:233-245`). Old hardcoded-period gap closed. |
| Gap, YZ vol, ROIC | OK | Gap uses open vs prior close (`:369`); Yang-Zhang 63d scaled to 21d (`:401-415`); general `ROIC = EBIT(1-t)/invested capital` at `:562` alongside Greenblatt ROIC. |
| Three-tier percentiles, funnel, heatmap, quick-look | OK | Sector/industry-group/industry relative scores (`:679-692`); funnel stages (`:727-733`); `heatmap_view` accepts a metric param (`feature_01.py:90`); `quick_look` chart windows present. |
| Saved screens, scheduling | MISSING | `saved_screens: []` (`feature_01.py:96`); persistence/scheduler explicitly deferred in `FEATURES.md`. |

### S2: Formula Builder (`features/feature_02.py`)
| Spec item | State | Detail |
|---|---|---|
| `if()` alias, division/log guards | OK | `if()` template present (`:1170`); division-by-zero raises `FormulaError` (`:984`); `log()` validates positivity (`:1042-1048`). Covered by `test_formula_if_alias_and_division_guard`. |
| Time operators | OK / PROXY | True local history for price/OHLC, all return horizons, `momentum_jt` (`:1072-1087`) and PIT filing-period history for roa/roe/current_ratio/debt_equity/gross_margin/operating_margin/mcap (`:1089-1130`); everything else falls back to panel-order approximation with a warning diagnostic (`:1140-1156`). |
| Field registry, templates | OK | 15 templates (`:1163-1180`); FF factors injected as latest-row constants (`:657-662`), so factor *levels* work but factor *time series* do not. |
| as_of_date execution | OK | OHLCV truncated at `as_of_date` (`:251-255`); fundamentals cut by `reportDate` (`:494-499`); threaded from `metric_panel` (`:644`) and feature INPUTS (`feature_02.py:21`). |
| Walk-forward ICIR / purged CV | MISSING | `score_backtest` proxy only; correctly not claimed otherwise. |
| Zoo comparison | Partial | Real Spearman IC vs six forward horizons (`feature_02.py:44-52`), but only against returns, not "every other platform signal" as specced. |

### S3: Composite Quant Score (`features/feature_03.py`)
| Spec item | State | Detail |
|---|---|---|
| Manual/equal presets, neutralization, winsorize, scales | OK | 7 presets, sector/beta neutralization, 1/99 winsorize, signed-rank and percentile scales (`:1205-1238` and follow-ons). |
| IC-IR weighting | PROXY | `_rolling_ic_ir` (`:1183-1202`) is a seeded bootstrap over the *current* cross-section, not walk-forward history; response metadata says so (`feature_03.py:70-72`). |
| Ridge weighting | PROXY | Current-cross-section ridge; same disclosure. |
| Regime-conditional breakdown | WRONG label | `panel.groupby("sector")` relabeled as `regime_proxy` (`feature_03.py:62`); not a VIX/yield-curve regime. Disclosure exists but the key name still misleads. |
| Redundancy alerts, N_eff, decomposition | OK | Pairwise > 0.6 flagged (`:63-66`); `effective_num_factors`; per-stock decomposition. |

### S4: Academic Strategy Library (`features/feature_04.py`)
| Spec item | State | Detail |
|---|---|---|
| Strategy breadth | OK / PROXY | 22+ strategies wired; QMJ four-block, momentum smoothness, dual-momentum risk-free gating fixed per `missing.md`. Graham Net-Net (working-capital vs total-liab), Dogs-of-the-Dow (sector placeholder), Mohanram (6-factor proxy), ERP5 5Y averages remain approximations. |
| Leaderboard, Piotroski, Altman trend, correlation | OK | Leaderboard, 9-criterion scorecard, 8-quarter Altman history, correlation matrix all present. |
| Historical performance | PROXY | Deterministic price-history backtests on latest-snapshot scores, disclosed in meta (`feature_04.py:70`). No PIT, no regime-conditional series. |

### S5: Backtester (`features/feature_05.py`, `analytics.py:1734-1866`)
| Spec item | State | Detail |
|---|---|---|
| Walk-forward sim, costs, stats | **WRONG** | See B4: one selection from current scores, held across the window; "rebalancing" only subtracts cost (`:1784-1786`). Stats math (Sharpe net of RF, Sortino/Calmar/MDD) is fine, but it runs on a look-ahead portfolio. |
| Holding-period sensitivity | OK | Now measures independent forward horizons without refetching (`feature_05.py:22-35,90`), regression-tested. Old `rebalance_days`-as-holding bug closed. |
| Rebalance sensitivity, weekday, turnover | OK / PROXY | Offset grid (`:142-145`), weekday table (`:1841-1866`, though cost math at `:1858` smears cost across observations), rank-drift turnover proxy (disclosed `:155`). |
| Monte Carlo / PBO | WRONG label | 250-draw bootstrap Sharpe in-run (`:91-99`). The "PBO" (`analytics.py:2110-2135`) varies `rebalance_offset_days`, which only drops the first 0-20 days (`:1757-1758`), so every trial is the same portfolio on a slightly shorter window, compared against SPY. It is not PBO (Bailey et al. CSCV) in any sense. |
| PIT enforcement, survivorship | MISSING (disclosed) | Stats carry `survivorship_bias_warning` (`:1824-1827`); meta requires PIT/delist datasets (`feature_05.py:155`). Stock attribution uses one shared entry/exit date (`:100-105`), not per-position dates. |

### S6: Alerts (`features/feature_06.py`)
| Spec item | State | Detail |
|---|---|---|
| Threshold/technical/volume/fundamental alerts | OK | Score/move/RSI/metric/formula/volume-spike/SMA-cross/MACD/Bollinger/consecutive-day plus YoY fundamental changes (`:36-62`). |
| Entry/exit detection | WRONG label | `screen_entry_exit_log` is tickers above threshold tagged `"entered"` (`:63-64`); no comparison to prior state, no exits. |
| Percentile-shift alerts, scheduling, email, history | MISSING | `precision_proxy: None` with "requires persistent alert history" (`:65`); historical replay covers golden-cross/RSI only (`:66`, `:1869-1896`). |

### S7: Relative Valuation (`features/feature_07.py`, `analytics.py:2143-2236`)
| Spec item | State | Detail |
|---|---|---|
| Four-dimension card, peers, universe table | OK | Absolute/sector/universe/own-history card (`:2201-2212`); sector/industry/market-cap-bucket/custom peer scopes (`:2154-2170`); per-metric universe percentiles. |
| History window | Partial | `history_window` accepted (`:2191-2193`) but only as a date cutoff, not the spec's 252/756/2520-trading-day toggle. |
| Sector heatmap | Partial | Sectors x 8 metrics with counts and median caps (`:2213-2217`); sector-mean-of-percentile construction is coarse but real. |
| Inversion, slope | Partial | `fcf_yield` treated higher-better, rest inverted via `higher_better=False` (`:2175`); re-rating OLS slope present. |

### S8: Export (`features/feature_08.py`, `analytics.py:2361-2377`)
| Spec item | State | Detail |
|---|---|---|
| CSV/TSV/ticker-list/JSON | OK | `build_export_payload` emits real `csv`, `tsv`, `ticker_list`, column list; streaming download at `POST /export/{id}.csv` (`screener_v2.py:64-76`); endpoint metadata now `status: available` (`feature_08.py:43`). |
| Change report, scheduler, optimizer/ML feed, columns | MISSING | `change_report` is still `row_count`/`columns` with `status: current_run` (`feature_08.py:29-32`); no run history, no delivery, no feed handoff, no column selection. |

---

## 4. Use open source that is already installed

No new dependencies are needed for the remaining correctness work; everything below is importable or already in the stack:

| Hand-rolled or missing today | Replace with | Why |
|---|---|---|
| Seeded bootstrap IC-IR (`_rolling_ic_ir`, `:1183-1202`) | Walk-forward Spearman IC over stored score snapshots with `pandas` rolling windows | Turns the disclosed proxy into the specced estimator with zero new deps. |
| Offset-grid "PBO" (`feature_05.py:91-119`) | Combinatorial rebalance-date resampling + deflated-Sharpe check in `numpy`/`pandas` | Honest overfit statistic from the same price panel. |
| Weekday cost smear (`:1858`) | Same rebalance-date deduction used in `score_backtest` (`:1784-1786`) | One-line consistency fix. |
| Alert `entered`-only log (`feature_06.py:63-64`) | Persist last-run member set (SQLite or JSON sidecar) and diff | Unlocks entry/exit log, rank-shift alerts, and the S8 change report together. |
| `parse_symbols` silent fallback (`data_loader.py:116-118`) | 422 with unknown tickers, reusing FastAPI `HTTPException` as in `screener_v2.py:53-60` | Same file already shows the pattern for CSV uploads. |
| Parquet reads at scale (`data_loader.py:45-56`) | `polars` lazy scan (already optionally imported at `:22-25`) | Falls back cleanly to pandas today; make it the primary path. |
| Frontend tables/heatmaps (custom divs + `recharts`) | Keep `recharts` (already used); add virtualization for tables | One chart lib, no new dep; fixes the 160-row wall without a rewrite. |

Data gaps no library can fix (already scaffolded in `fetchers/fetch_missing_data.py`): PIT fundamentals by as-of date, delisted-security history, saved-screen/run-history/alert-state storage, scheduler and email delivery. All are correctly listed in `NOT_POSSIBLE_WITH_CURRENT_DATA.md`.

---

## 5. Frontend review

- **Run is broken (B1), preview is fake (B3).** `runScreenerV2Feature` (`lib/api.js:1038`) hits a path the backend never serves with a body the backend never accepts, so the `catch` branch (`customPagePrimitives.jsx:499-502`) is the *normal* path, not the exception path.
- **160-row cap, no pagination or virtualization.** `DataTable` renders `filtered.slice(0, 160)` (`:389`) with a client-side search box; heatmaps cap at 18 rows x 24 cols (`:432-434`); backend sends up to 250 ranked rows and 1,000 export rows, most of which the user can never page through. No `cmdk`, no column selector (dense tables hard-slice 12 columns, others 8, `:372`), no saved views; "Saved Screens" renders the backend's permanent `[]` (`registry.js:139`).
- **Duplicated contract.** `registry.js` re-declares all 8 features' inputs/defaults/outputs by hand while the backend serves `feature_manifest()` at `GET /api/screener-v2/features`. Drift already exists (e.g. F08 default `tsv` vs backend default `csv`; F04 frontend lists 8 strategies vs 22+ implemented).
- **Unreachable or dead UI.** F06 exposes only 3 of ~10 effective backend alert knobs (no metric/formula/volume-spike/fundamental thresholds). F03 `components` is a raw JSON textarea. F02 `as_of_date` input exists backend-side but has no frontend field. `ScreenerV2Home` hero links only 4 of 8 modules (`:541`) though the grid below lists all 8.
- **One 583-line primitives file** with a ~30-line global CSS string, all renderers, demo fabricators, and workbench state in one module. Split demo fixtures, renderers, and workbench; move CSS to a module.
- **V1 coexistence.** `screener_api.py:586-621` `POST /screener/backtest` still returns `random.uniform` metrics, and `screener_quant360.py:604-659` documents live-with-fallback behavior. Neither is labeled demo in the UI paths that surface them. Gate or remove the random stub now that V2 backtests deterministically.

---

## 6. Codebase-wide pattern (same issues across the V2 modules)

- **Copy-paste data loaders and workbenches.** Seven `core/data_loader.py`-style readers and seven `customPagePrimitives.jsx`-style workbenches persist across V2 modules; Screener's duplicates (`screener_v2_combined.py`, 3,025 lines) were deleted per `review.md:5`, but `analytics.py` at 2,385 lines still bundles technicals, fundamentals, formula engine, composites, academic scores, backtests, alerts, and valuation in one file.
- **Spec-complete claims vs proxy reality.** `FEATURES.md`/`README.md` check every box while `NOT_POSSIBLE_WITH_CURRENT_DATA.md` quietly lists the load-bearing gaps (PIT, delisted, persistence). Same shape as Research V2's `DONE.md` problem. Keep one checklist that marks proxies as proxies.
- **Silent fallbacks as a house style.** Unknown tickers fall back to top-500 (`data_loader.py:117-118`), missing SPY falls back to universe-mean beta (`analytics.py:386-393`), failed fetches fall back to demo UI (`customPagePrimitives.jsx:499-502`). Each is individually defensible; together they mean the user is rarely told they are looking at substitute data. Standardize on: disclose in `meta.access_issues` *and* in the UI status line.
- **Envelope drift between frontend lib and backend routers.** Screener V2 posts raw payloads to a `/labs/...` path; the router expects `{payload}` at `/api/screener-v2/...`. Audit the other V2 `run*Feature` helpers against their routers the same way.
- **Stale-data handling is the one pattern Screener V2 gets right.** `mtime`-stamped caches, `as_of_date` truncation, NaN-safe `clean_json`, duplicate-ticker `ValueError` (`analytics.py:649-651`), and per-response `access_issues` are worth copying to the sibling modules.

---

## 7. Remaining work, by type, in order

| # | Type | Work | Size |
|---|---|---|---|
| 1 | Wiring | Align `runScreenerV2Feature` path to `/api/screener-v2/run/{id}` with `{payload}` envelope; add API-contract test (path + envelope + 404/422 cases) | S |
| 2 | Frontend honesty | Error state with retry on run failure; gate demo behind `?demo=1` with watermark; remove `Math.random()` stats; fix F08 endpoint string and "4,000+" label | S |
| 3 | Data integrity | 422 on unknown explicit tickers, including partial drops (A2); rename or fix the fake "sp500" default (A1); flag the research-export price fallback (A3); label capped universes with cap; single entry/exit date note in S5 attribution | S |
| 3b | API | Background jobs for runs (A4); error handling and field pass-through in CSV/export routes (A5); screener-owned symbol search (A6); lazy registry (A8) | S |
| 4 | Frontend scale | Pagination/virtualization past the 160-row cap; column selector; surface hidden knobs (F02 `as_of_date`, F06 thresholds, F03 component builder); fetch input contract from `/features` | M |
| 5 | Correctness (S3/S4) | Walk-forward IC-IR and ridge on stored snapshots; relabel sector-grouped "regime" or implement VIX/yield-curve regimes; Graham/Dogs/Mohanram/ERP5 upgrades or proxy labels | M |
| 6 | Correctness (S5/S7) | **True walk-forward backtest (B4)**: per-date reselection with `as_of_date`, turnover-based costs, weekday as snapped rebalance dates, real CSCV PBO; per-position entry/exit dates; 252/756/2520-day history toggle; full combinatorial PBO behind existing `run_full_pbo` flag | M |
| 7 | Persistence | Saved screens, run history (unlocks S8 change report, S6 entry/exit + shift alerts, realized precision), scheduler + email delivery | L |
| 8 | Data foundations | PIT fundamentals panel, delisted-security history via `fetchers/fetch_missing_data.py` scaffolds | L |
| 9 | Tests | Golden-number tests (indicators, Piotroski/Altman, backtest stats on fixtures); look-ahead guard test; unknown-ticker 422 test; demo-fallback absence test | M |
| 10 | Cleanup | Split `analytics.py` by domain; remove V1 random backtest stub (`screener_api.py:586-621`) or label it demo; reconcile `FEATURES.md` proxies; dedupe V2 loaders/workbenches | L |

Recommended next step: items 1-3b together (small, and they make the module usable and honest). Then do B4 from item 6 before trusting any S3/S4/S5 performance number. Then item 4, with tests from item 9 alongside.

---

## 8. Addendum (verified 2026-10-03)

These came from a second read of the code and were not in the first pass.

| # | Area | Finding | Where |
|---|---|---|---|
| A1 | Data | `"sp500"`/`"default"` resolves to the 500 tickers with the most price rows, not the S&P 500. The label is false and the selection is survivorship-biased (long-lived names only). | `data_loader.py:105-106` |
| A2 | Data | Unknown tickers are dropped silently even when others survive (`XYZ, AAPL` runs on AAPL alone, with no notice). The first pass only flagged the all-unknown case. | `data_loader.py:116` |
| A3 | Data | If `backend/data/market_universe.parquet` is missing, prices are read from the paper's frozen submission export (`research_exports/.../SUBMISSION_MAIN`), with no notice. | `data_loader.py:81`, `performance.py:51` |
| A4 | API | Runs are synchronous HTTP calls with no job, progress or cancel. A master-universe S5 run with `run_full_pbo` (60 full backtests) will exceed proxy timeouts. Reuse the Studio `JobStore` pattern as in Research V2. | `screener_v2.py:29-36` |
| A5 | API | `/export/{id}.csv` does not catch `ValueError`/`TypeError` (bad input gives a 500), and for any feature other than 08 it returns an empty CSV with 200. `/run/{id}/csv` does not catch `KeyError` (unknown feature gives a 500) and drops every other form field (filters, periods), so an uploaded universe always runs defaults. | `screener_v2.py:39-76` |
| A6 | API | Symbol search goes through Factors V2 (`/labs/factors/v2/symbols`), whose directory is not the screener's `available_symbols()`. Search can suggest tickers the screener then silently drops (A2). | `lib/api.js:1032-1034` |
| A7 | Frontend | The CSV-upload and streaming-export routes exist but nothing in the frontend calls them. | `components/screener-v2/` |
| A8 | Backend | `registry.py` imports all 8 feature modules (and the 2,385-line analytics) at package import, so `main.py` startup pays for it. Make it lazy like Research V2. | `registry.py:43`, `__init__.py:3` |
| A9 | Correctness | Two bare `except Exception` blocks in analytics, plus `_read_parquet` falling back to a full-file read when a column is missing. Errors become empty frames instead of messages. | `analytics.py`, `data_loader.py:48-56` |
| A10 | Performance | Row loops: `panel.iterrows()` in S6 alerts and S7 cards, plus three more in analytics. These run per request over up to 5,000 names. Vectorize. | `feature_06.py:36`, `analytics.py:873,1928,1951,2219` |
| A11 | Docs | `review.md` and `missing.md` are fully ticked checklists that conflict with this review (for example, "deduct costs on rebalance dates" is ticked, but the weekday path still smears costs). `schemas/` and `utils/` are empty packages. | `screener_v2/` |
| A12 | Tests | No frontend tests at all; no test would have caught B1 (path and envelope) or B4 (static portfolio). | `frontend/src/components/screener-v2/` |
