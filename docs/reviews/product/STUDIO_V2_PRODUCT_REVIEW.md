# Studio product review: strategy research, validation and paper, with Chart inside

Written 2026-11-09 against the feature rule in `docs/plans/PLAN.md` section 1b and Step 7 of `docs/plans/CHECKLIST.md`. Research sources are in `docs/references/2026-11-studio-research.md`. Code claims were checked by reading function bodies in the files named; anything not read is marked. No servers were run and no tests were run (docs-only task).

## Contents
1. Verdict
2. What is real and what is hollow (code)
3. Paid-feature parity table
4. Keep, build, later, cut
5. Paper: stays or goes
6. Chart as a Studio tab
7. Our ideas for user freedom
8. Open-source picks
9. Data limits
10. Build checklist (E, M, H)
11. Unverified

---

## 1. Verdict

Studio is the most serious backend in the repo. Strategy execution runs user code in a locked Docker container, costs are charged on every trade, the portfolio optimiser is a real SLSQP solver, and certification bundles are hash-bound. The problem is the layer around it. Four things undercut the promise "every result says how far it can be trusted":

- **The strategy is not what the validation tests.** The sensitivity grid runs a built-in momentum rule, not the user's code (section 2).
- **Some controls look wired but are not.** The `universe` field on execute is accepted and ignored. The `end_date` on execute is applied in a way that breaks for any date before the last data row (section 2).
- **Paper trading is a journal, not a feed.** The lifecycle gates and kill switch are real. Nothing produces orders, fills or prices (section 5).
- **Two data stacks.** Studio reads `market_universe.parquet`. Chart reads live `robust_data_fetcher` (yfinance). Studio's data inspector still depends on the retired `studio_v2` routes.

Position, following the platform rule: **Studio is where a strategy is tested until it is either certified or rejected, with the test named, the data limits printed and the code visible.** Sell Results and Validate first. Keep Develop, Replay and Composer as supporting modes. Merge Portfolio into its own module (Step 6). Keep Paper only as a gated ledger until a feed exists.

Decisions proposed, not yet taken (the owner decides):
1. Chart becomes a Studio tab and `/trade` redirects there.
2. Paper stays as a ledger, renamed in the UI, with its schedule and free-text universe removed until a feed exists.
3. Portfolio tab is removed from Studio and linked to Step 6's `/portfolio`. The paper gate chain (portfolio version, validation, promote) moves with it.
4. The sensitivity grid is either re-pointed at the user's strategy parameters or removed from Validate.

---

## 2. What is real and what is hollow (code)

Read in this session. File and function are given so each claim can be checked.

### Real

| Area | Where | What the body does |
|---|---|---|
| Sandboxed strategy execution | `backend/app/services/studio/execution.py` `DockerExecutionProvider._command` | `docker run --network none --read-only --cap-drop ALL`, non-root user, 512 MB, 1 CPU, 15 s timeout. Source is screened with `ast` (no imports, denied names and attributes). Runner image `quant360-studio-runner:1.0` is referenced; whether it is built on this machine is **unverified** (`docs/evidence/studio/P1-W3/readiness.md` mentions it) |
| Cost and turnover in the equity curve | `backend/app/routers/studio.py` `_process_strategy_results` | Each trade charges `traded_notional × (slippage + commission)`. Trades record MAE and MFE via `_trade_excursion`. Gross and net equity are both kept |
| Metrics | `services/studio/metrics.py` `calculate_performance_metrics` (called by `_compute_metrics`) | Delegated to one canonical calculator with warnings. Body not read in full |
| Monte Carlo | `MonteCarloEngine.run_simulation` | Gaussian, i.i.d. bootstrap and moving-block bootstrap, seeded. Ruin, drawdown percentiles and histogram are computed from the simulated paths |
| Walk-forward folds | `WalkForwardEngine.run_analysis` | Expanding training window, purge and embargo gaps, fixed out-of-sample windows. Returns a deterministic PASSED / FAILED / UNAVAILABLE verdict with thresholds. The verdict is labelled "not statistical confidence" in its own methodology field |
| Scenario evidence | `run_scenarios` | Reuses the walk-forward engine on cost shock, missing-data and delay variants. Liquidity, regime and adversarial scenarios are returned as **skipped** with reasons, not faked |
| Portfolio optimiser | `services/studio/portfolio.py` `optimize_portfolio` | Real `scipy.optimize.minimize` with SLSQP. Objectives: max Sharpe, max return, diversification, tracking error, multi-objective. Constraints: weights, gross leverage, turnover, linear constraints, target return. Sample and diagonal-shrinkage covariance from observations |
| Paper gate and kill switch | `services/studio/paper.py` `create_deployment`, `_limit_breaches`, `set_kill_switch` | Refuses a deployment unless the portfolio version is saved, the walk-forward job completed and PASSED, and an exact promote audit exists. Limit breaches (order notional, position weight, gross exposure, daily loss, stale data, missing price) are recorded as events |
| Reconciliation | `PaperLifecycle.reconciliation` | Joins fill events to intended orders and computes slippage in basis points from expected and actual prices |
| Certification bundles | `services/studio/certification.py` `create`, `reproduce` | Content hash over source artifact, validation input and result hashes. `reproduce` recomputes the hashes and compares |
| Job store | `services/studio/jobs.py` `JobStore` | Persistent job records, owner checks, audit trail, SSE events (`/jobs/{id}/events`) |

### Hollow, or not what the label says

| Issue | Where | Evidence in code | Consequence |
|---|---|---|---|
| **Sensitivity grid tests a built-in momentum rule, not the user's strategy** | `routers/studio.py` `_sensitivity_sharpe` and `run_sensitivity`; UI heading "Parameter sensitivity surface" in `ValidateView.jsx` | `_sensitivity_sharpe` takes `closes` and runs a hard-coded `momentum > threshold` rule for each `(lookback, threshold)` cell. The user's `Strategy.generate_signals` is never called | A surface that looks like robustness of the user's parameters is robustness of a different strategy. This is the most serious label problem in Studio |
| **`universe` is accepted and ignored on execute** | `routers/studio.py` `StrategyExecutor.__init__` stores `self.universe` (line 461); no read of it afterwards. `ExecuteStrategyRequest.universe` defaults to `US_TOP50` | Any ticker in the parquet runs. The UI sends `universe: 'US_TOP50'` (`StudioStore.js` around line 390) | Users believe execution is limited to a universe. It is not |
| **`end_date` breaks for past dates** | `StrategyExecutor.get_price_data` calls `data_engine.get_full_ohlcv(ticker, lookback_days + 100)`; `services/data_engine.py` `get_full_ohlcv` (line 231) anchors the window to the data's last date, not `end_date` | Then the executor filters to `[end_date - lookback_years*365, end_date]`. For an `end_date` earlier than the last data row the filtered set can be empty, which raises "No observed OHLCV data". **Read from code, not run**. Needs a test before anything else is built on as-of runs |
| **Fills at the signal bar's close** | `_process_strategy_results`: `entry_price_adj = closes[i] × (1 ± slippage)` and the strategy receives the whole frame including bar `i` | Same-bar execution. Pine's default is the same (market orders fill on the closing tick the script creates them), but Pine users can switch it. Our UI has no switch and no next-bar option. The strategy also sees future rows in the frame (`execution.py` passes all records); whether a strategy looks ahead is the user's choice, and nothing prevents it |
| **Certification test results are asserted by the browser** | `AdvancedValidationView.jsx` builds `tests` with `status` values; `services/studio/certification.py` `create` accepts them as given | The server hashes the claimed results and checks the validation job's status, but does not re-run the tests. A "certified" bundle is a signed-by-hash claim by the client |
| **Paper has no feed** | `services/studio/paper.py` module docstring says it "records user or simulator supplied events. It never fabricates market prices". `PaperView.jsx` posts events typed by the user. `schedule` is stored (`create_deployment`) and read nowhere | A deployment is a journal with gates. Nothing trades, prices or reconciles against a market |
| **Alerts live in the browser** | `chart_engine/AlertEngine/useAlerts.ts` stores alerts in `localStorage` and evaluates them in a `setInterval` in the open tab; notifications through the Notification API | Alerts fire only while the page is open and only on the device that set them |
| **Chart data is live, not parquet** | `backend/app/api/prices.py` calls `robust_data_fetcher.get_price_data` (yfinance fallback, `robust_data_fetcher.py` line 635 onward) | Chart and Studio give different prices for the same ticker on different days. Plan step 7.2 names these files for deletion |
| **Studio data inspector depends on retired code** | `frontend/src/hooks/studio/useDataStudio.js` calls `/api/v2/data-studio/*`; `backend/main.py` keeps only `/api/v2/data-studio/` and `/api/v2/health/` from `studio_v2`. `routers/studio.py`, `services/studio/paper.py`, `certification.py` and `reports.py` import `app.studio_v2.shared.persistence` and observability | "Remove the rest of studio_v2" (checklist Step 7.7) cannot delete the directory until `persistence` and `observability` move to `services/shared/` (merge map decision 2) and the data-studio routes are replaced |
| **Sensitivity on non-US data** | `/data` serves any ticker in the parquet; no `.NS` handling | Consistent with merge decision 16. Not a bug, a limit |

**Not read in full (so not graded):** `reports.py` render bodies and HTML export; `ReplayView.jsx`; `TearsheetView.jsx`; `Q360Canvas.jsx`; chart drawing tools. Their status is in section 4 as **unverified**.

**Dead-looking code to confirm before deletion (checked with `rg` on this date, graph not run):** `backend/app/studio_v2/algorithm_lab/*`, `backtest/*`, `optimizer/*`, `robustness/*`, `factors/*`, `portfolio_risk/*` are not imported by `routers/studio.py`, `services/studio/*` or `backend/main.py`. They are reached only from the retired router. Deletion needs the graph and a backend smoke test first, per `AGENTS.md`.

---

## 3. Paid-feature parity table

Status values: **have** (code exists and was read), **partial** (exists, with a gap named), **build** (data in hand), **later, free data**, **later, paid data**, **cut**. Competitor abbreviations: TV TradingView Pine, QC QuantConnect, P123 Portfolio123, TL Trendlyne (Screener review).

### 3.1 Strategy authoring and data

| # | Feature | Who offers it | Status | Note |
|---|---|---|---|---|
| S1 | Code editor with syntax highlight | TV, QC | partial | Monaco loaded on demand (`Editor.jsx`). Command palette exists. Diff and tree are from PLAN step 7.4 |
| S2 | Sandboxed user code | QC (cloud), TV (Pine) | have | Docker runner, no network, read-only (`execution.py`) |
| S3 | Strategy templates | TV, QC | partial | One built-in momentum strategy (`run_momentum_strategy`); templates list not read |
| S4 | Fills, commission, slippage as inputs | TV | have | `slippage_bps`, `commission_pct` on execute |
| S5 | Fill timing choice (close, next bar, open) | TV | later | Only same-bar close exists (section 2) |
| S6 | Order types (limit, stop) | TV, QC | later | Market only in the engine |
| S7 | Multi-asset (crypto, FX, futures) | TV, QC | later, free data | Parquet holds FX, crypto, futures daily (Screener review section 2). Not wired to execute |
| S8 | Universe selection in code | QC | build | Needs the `universe` field fixed first (section 2) |
| S9 | Minute and intraday bars | TV, QC | later, paid data | Hourly file exists for the Screener; not wired to Studio |
| S10 | Corporate actions and point-in-time data | QC | later, paid data | Screener review row 82 |
| S11 | Bring your own CSV | TV (import), QC (upload) | have | Data inspector upload through `/api/v2/data-studio/upload` (retained route) |

### 3.2 Results, validation and proof

| # | Feature | Who offers it | Status | Note |
|---|---|---|---|---|
| R1 | Equity curve, drawdown, exposure, turnover, costs | TV strategy report, QC | have | `series` in execute result |
| R2 | Trade list with MAE, MFE, holding period | TV (Deep Backtesting) | have | `_process_strategy_results` |
| R3 | Metrics bundle with warnings | TV, QC | have | `calculate_performance_metrics` |
| R4 | Benchmark (buy and hold) | TV, QC | have | `_benchmark_buy_and_hold` |
| R5 | Monte Carlo risk of ruin | None strong | have | `MonteCarloEngine` |
| R6 | Walk-forward folds with purge and embargo | QC (walk-forward optimisation in cloud), P123 | partial | Folds are fixed-rule IS/OOS splits. **No parameter is re-fit per fold** (no optimiser in the loop). Label it as a stability split, not walk-forward optimisation |
| R7 | Parameter sensitivity of the user's strategy | P123 (optimiser, with warnings) | build | Currently tests a built-in momentum rule (section 2) |
| R8 | Scenario stress (cost shock, delay, missing data) | None strong | have | Liquidity, regime and adversarial skipped with reasons |
| R9 | Deflated Sharpe and trial count | None (we add) | later, uses Validate | Merge map decision 6; trial ledger owner is Research (decision 4) |
| R10 | Certification bundle, reproducible | None | have, partial | Hash-bound; test results are client-asserted (section 2) |
| R11 | Promotion audit (promote, reject, override with rationale) | None | have | `/jobs/{id}/promotion-audit` |
| R12 | Replay of a run | TV bar replay | unverified | `ReplayView.jsx` not read |
| R13 | Tearsheet | QC PDF report, P123 | unverified | `TearsheetView.jsx` not read; reports render in `reports.py` not read |

### 3.3 Portfolio, paper and reporting

| # | Feature | Who offers it | Status | Note |
|---|---|---|---|---|
| P1 | Portfolio optimisation with constraints | P123, QC (Portfolio construction) | have | `services/studio/portfolio.py` SLSQP. Overlaps Step 6 `/portfolio` (merge) |
| P2 | Saved, immutable portfolio versions and compare | P123 | have | `/portfolio/versions`, compare endpoint |
| P3 | Paper trading with feed | TV (paper via broker), QC (paper trading) | partial | Gated ledger only; no feed (section 5) |
| P4 | Kill switch | QC (live), brokers | have | `set_kill_switch` |
| P5 | Reconciliation (slippage vs expected) | QC live | have | `reconciliation` |
| P6 | Live trading with a broker | QC | cut | Broker connect is Screener cut C3; not in Studio's scope |
| P7 | Alerts on a strategy | TV (alerts with webhooks) | later | Server-side delivery layer (Screener rows 73 to 74, Apprise). Chart alerts are browser-only today |
| P8 | Report PDF, one click | QC (backtest PDF) | build | Typst, PLAN step 7.6. `reports.py` export_html exists; PDF not built |
| P9 | Output recipes and saved views | None | have | `reports.py` `save_recipe`, `save_view` |
| P10 | Research notes linked to artifacts | None | have | `save_note` |

### 3.4 Chart

| # | Feature | Who offers it | Status | Note |
|---|---|---|---|---|
| C1 | Candles, volume, intraday | TV | have | `chart_engine` (ChartCanvas, IntradayChartWrapper) on `/trade` |
| C2 | Indicators | TV (100+) | have | `IndicatorEngine/registry.ts` registers 233 indicator ids (count from `rg`, not an audit of quality) |
| C3 | Drawing tools | TV | have | `DrawingEngine/registry.ts` lists 86 tool registrations (count from `rg`); tools not individually tested |
| C4 | Chart layouts, multi-pane | TV | partial | `GridChartCell.jsx` in Studio; layout manager modal |
| C5 | Replay | TV Bar Replay | partial | `ReplayView.jsx` (not read) |
| C6 | Alerts | TV | partial | Browser-only (section 2) |
| C7 | Pattern scanner | TV, SE (Screener review) | have | `PatternScanner/` (candlestick patterns, 782-line file). Evidence weak (Screener review section 11) |
| C8 | Persisted drawings and indicator sets | TV (cloud) | partial | Indicators in `localStorage` (`ChartContext.tsx`). Drawings server-side: **unverified** |

---

## 4. Keep, build, later or cut

Each row has a reason. Cut means deleted, after the graph and `rg` checks and a smoke test.

### Modes (tabs)

| Mode | Verdict | Reason |
|---|---|---|
| Develop (editor, execute, equity) | **Keep, build** | The core of the product. Fix `universe` and `end_date` first. Add fill-timing option (later) |
| Results (tearsheet) | **Keep, merge** | Same exhibits as Validate and the labs (PLAN step 7.5). Layout not read |
| Validate (walk-forward, Monte Carlo stress, advanced) | **Keep, sell first** | Real engines. Replace the sensitivity grid with one over the user's parameters (R7). Rename walk-forward as a stability split until it re-fits |
| Replay | **Keep, unverified** | Read the component before any decision beyond keep |
| Compose (reports, notes) | **Keep** | Output recipes are real. PDF build via Typst (P8) |
| Paper | **Keep as ledger, re-scope** | See section 5 |
| Portfolio | **Merge into Step 6 and remove the tab** | Duplicates `/portfolio` by PLAN section 1 rule. The paper gate chain stays intact via the saved version id |
| Stress (Monte Carlo) | **Merge into Validate** | Already a sub-tab of Validate in `StudioModeStage.jsx`; the separate mode is redundant |
| Chart | **Build as tab** | Section 6 |

### Features

| Feature | Verdict | Reason |
|---|---|---|
| Sandboxed Python strategy | Keep | Real, locked down |
| Sensitivity grid on built-in momentum | **Cut** | Tests a different strategy and says so only in methodology text. Replace with R7 |
| `universe` field on execute | **Build (fix) or cut** | Accepted and ignored. Either enforce it or remove it from the contract |
| Walk-forward naming | **Keep, relabel** | Honest as a stability split; not walk-forward optimisation |
| Client-asserted certification tests | **Keep, build fix** | Server should derive test status from the stored runs, not accept it |
| Paper schedule (JSON) and free-text universe | **Cut until feed exists** | Stored and read nowhere |
| Browser-only alerts | **Later** | Move to server delivery (Screener delivery layer) |
| Manual paper events as the only input | **Keep for test, label as journal** | Useful for reconciliation practice; not a trading record |
| Studio data inspector on `/api/v2/data-studio` | **Build (replace)** | Move to parquet-first loader, then delete `studio_v2` |
| `studio_v2` algorithm lab, optimizer, robustness, factors, portfolio risk | **Cut** | Not imported by the live router (section 2). Check with the graph first |
| Multi-asset execution | **Later, free data** | FX, crypto, futures parquet exists |
| Minute and intraday execution | **Later, paid data** | Needs intraday history in the execution path |
| Order types, live broker | **Later / cut** | Broker is out of scope (Screener C3) |
| Pine-style language | **Cut** | Python is the language; a second language splits the tests |
| Community strategy sharing | **Cut** | Moderation cost; the share link comes from Screener row 45 later |

---

## 5. Paper: stays or goes

**Recommendation: stays, as a ledger, until a feed exists. Re-scope it now; do not delete it.**

Why keep: the gate chain is the only place in the product that turns "validated" into a state with rules. Portfolio version, completed walk-forward with PASSED, exact promote audit, limit breaches, kill switch and reconciliation are all real and tested in code (section 2). That is the honest path from research to a live decision, and no competitor in the tables above gates on validation this way.

Why re-scope: today a paper deployment cannot trade. It records what the user types. The UI calls it "Create armed deployment" and "Paper". Users will read that as simulated trading. Changes, all small:

1. Rename the tab "Ledger" in the UI and state in one line that no orders are generated.
2. Remove the schedule JSON field and the free-text universe; take the universe from the saved portfolio version. The backend already stores `schedule` unused.
3. Keep the kill switch and reconciliation as they are.
4. When a feed exists (Screener rows 27 and 72 style, or a daily end-of-day job), add a scheduler that writes `signal` and `valuation` events. Until then, nothing is built.

Cost: E for the rename and field removal; H for a feed (data licence, scheduler, market hours).

---

## 6. Chart as a Studio tab

**Recommendation: yes.** Chart is not sold alone. Studio needs it for replay, for showing the price path behind a trade, and for the drawing and indicator work that a strategy author does. The PLAN proposal (`/trade` redirects to a Studio tab) holds.

Conditions before the move:

1. **One data path.** Chart reads `/api/prices` through `robust_data_fetcher` (yfinance). Studio reads parquet. Move Chart's price source to the parquet-first loader (step 7.2), with the per-ticker store for `.NS` names (merge decision 16). Yahoo fallback is removed or labelled.
2. **Alerts on the server.** Browser-only alerts do not belong in a research tool that users are told is reliable. Either move alert evaluation to a server job with the delivery layer, or label alerts "while this tab is open" in the UI.
3. **Drawings and indicator sets saved server-side** or labelled as local to this browser.
4. **Replace the redirect target only after** `ReplayView` is read and kept.

The chart engine is large (`ChartCanvas/index.tsx` 1,679 lines, `q360_chart_core.tsx` 2,013 lines, `IndicatorEngine/registry.ts` 2,765 lines). Moving it does not require rewriting it. Split only where a second caller needs a part.

---

## 7. Our ideas for user freedom and customisation

These are ours. Each is tied to a gap in section 2 or 3, so nothing is added for novelty.

1. **Parameter grids over the user's own strategy.** The strategy declares its parameters in a `PARAMS` dict. Execute runs the grid by calling the user's `generate_signals` with each value, in the same sandbox, with the same costs. This replaces the momentum-only sensitivity grid (R7) and gives P123-style optimisation with an honest penalty, so users see the search size. (M)
2. **Trial counter on every run.** Each execute, grid cell and variant counts as a trial in the strategy's ledger, and the deflated Sharpe uses that count (R9, merge decision 4). The count is shown on the result. (M)
3. **Fill-timing switch.** Same bar close (current, Pine default), next bar open, next bar close. The user chooses; the result records which was used. (E)
4. **Universe enforcement.** The strategy declares its universe. Execute refuses tickers outside it. Fixes the ignored field. (E)
5. **Look-ahead guard.** The runner gives the strategy an expanding frame: at bar `i` it sees rows `0..i` only, through a view, and a test shows future rows are not reachable. This is the strongest freedom-with-trust feature we can offer, because Pine and most code-first tools do not enforce it. (M)
6. **Strategy as a file.** Export the strategy source, parameters, data hash, costs and result as one bundle that reproduces with `reproduce` (already exists for portfolio versions). (E)
7. **Bring your own bars.** Upload OHLCV CSV with the same validation as the Data Studio upload, usable as the execute ticker. Stays on disk, scoped to the owner (merge decision 9). (M)
8. **Formula indicators.** Users define custom indicators in the research formula language (`signal_lang`, safe `ast`, with spans) and use them in code or on Chart. One language across Screener, Research and Studio. (M)
9. **Layout and view presets**, already in `reports.py` as saved views; extend to Chart layouts. (E)

---

## 8. Open-source picks

Licences checked in `docs/references/2026-11-studio-research.md`. Copyleft is ideas only.

| Need | Pick | Licence | Verdict |
|---|---|---|---|
| Charts | lightweight-charts (already installed) | Apache-2.0 | Keep |
| Code editor | Monaco (already used) | MIT | Keep |
| Diffs, file tree | @pierre/diffs, @pierre/trees | Apache-2.0 | Adopt at step 7.4, pin versions |
| Indicators | TA-Lib | BSD | Adopt, replaces hand-rolled indicators (Screener open-source reference) |
| Typeset PDF | Typst (typst-py) | Apache-2.0 (confirm) | Adopt at step 7.6 |
| Optimiser | scipy (already used) | BSD | Keep |
| Backtest engine idea | QuantConnect LEAN | Apache-2.0 | Ideas only: heavy, C# and Python, runs as its own service |
| Backtest engine idea | vectorbt (open source) | Apache-2.0 (unverified today) | Ideas only until licence re-read |
| Backtest engine idea | backtrader | GPL-3.0 | Ideas only (copyleft) |
| Backtest engine idea | backtesting.py | AGPL-3.0 (memory) | Ideas only (copyleft) |
| Strategy tables | react-querybuilder core | MIT | Adopt for AND/OR rule trees (Screener open-source reference) |
| Undo and redo | zundo | MIT | Adopt for the editor store |

---

## 9. Data limits

Printed on every Studio result and export. These are the limits the code has, not the ones we would like.

| Limit | Source | Effect |
|---|---|---|
| US daily prices, 1996 to 2026 | `market_universe.parquet` via `data_engine.py` | Executes on any ticker in the parquet. No delisted names (survivorship bias) |
| Non-US per-ticker files | `backend/data/prices/` | Not read by Studio. Merge decision 16 |
| No minute bars | Not held in Studio path | Intraday execution is later |
| Fundamentals | Not used by Studio execute | Paper and portfolio use return inputs only |
| Live prices | Chart uses yfinance through `robust_data_fetcher` | Chart and Studio disagree; fix in step 7.2 |
| `end_date` | Breaks for past dates (section 2) | Do not publish as-of runs until fixed and tested |
| Fill model | Same bar close, slippage and commission as inputs | Optimistic relative to next-bar fills; state it |
| Monte Carlo | Assumes the input returns are representative | Says so in `assumptions` |
| Walk-forward | Fixed rule, no re-fit | A stability split; say so |
| Paper | No feed | Ledger only |
| Docker runner | Must be built and present | Unavailable is reported as 503 |

---

## 10. Build checklist

Tags: **E** easy (under a day, one file or a rename), **M** medium (a few days, several files, tests), **H** hard (a week or more, needs data or a decision). Batched by step. Tick nothing until verified.

### Batch A: fix what is wrong (before any new feature)
- [ ] (E) Rename sensitivity grid to say it tests the built-in momentum rule, or remove it from Validate
- [ ] (E) Enforce or remove the `universe` field on execute, and remove the `US_TOP50` default from the UI
- [ ] (M) Reproduce the `end_date` bug with a test on a past date; fix `get_full_ohlcv` to anchor to `end_date`
- [ ] (E) Relabel walk-forward as a stability split in the UI and verdict text
- [ ] (E) Relabel Paper as a ledger; remove schedule and free-text universe
- [ ] (M) Derive certification test status from stored runs, not from the browser payload

### Batch B: trust features (sell Validate)
- [ ] (M) Parameter grid over the user's `PARAMS` in the sandbox (section 7.1)
- [ ] (M) Trial counter per strategy; deflated Sharpe using it (section 7.2, merge decision 4)
- [ ] (E) Fill-timing switch with the choice recorded in the result (section 7.3)
- [ ] (M) Look-ahead guard test in the runner (section 7.5)
- [ ] (E) Printed data-limit block on results and exports (Screener U10)

### Batch C: data and removal of studio_v2
- [ ] (M) Move `SQLiteStore`, observability and request id to `services/shared/` (merge decision 2)
- [ ] (H) Parquet-first loader replaces `data_loader.py`, `robust_data_fetcher.py`, `indicators.py` (step 7.2)
- [ ] (H) Replace `/api/v2/data-studio/*` in the data inspector with the new loader; delete `studio_v2` after graph and smoke checks
- [ ] (E) Delete `data_loader.py`, `indicators.py` only after `backend/main.py` and `api/prices.py` stop importing them (both are imported today)

### Batch D: Chart as a tab
- [ ] (M) Chart price source moves to the parquet-first loader; `/api/prices` removed for Studio
- [ ] (M) Chart alerts: server job, or label as tab-open only
- [ ] (E) Save drawings and indicator sets, or label as browser-local
- [ ] (E) Mount Chart as a Studio tab; `/trade` redirects; read and keep `ReplayView` first

### Batch E: merge and present
- [ ] (M) Remove the Portfolio tab; link to Step 6 `/portfolio`; keep saved version id in the paper gate
- [ ] (M) Merge Stress into Validate (already a sub-tab)
- [ ] (M) Results and Validate use the shared exhibits (step 7.5)
- [ ] (M) Typst PDF of a certified run (step 7.6, P8)

### Batch F: later
- [ ] (H) Paper feed and scheduler with market hours (section 5)
- [ ] (H) Server-side alert delivery through Apprise (Screener rows 73 to 75)
- [ ] (H) Multi-asset execution (FX, crypto, futures) (S7)
- [ ] (H) Intraday execution with the hourly file (S9)

---

## 11. Unverified

- QuantConnect dollar prices; vectorbt and backtesting.py licence text; Typst licence.
- `ReplayView.jsx`, `TearsheetView.jsx`, `Q360Canvas.jsx`, `reports.py` render and HTML export: not read in full, so not graded.
- Whether `quant360-studio-runner:1.0` is built on this machine: not checked (no Docker run, per the docs-only rule).
- Drawing persistence on Chart: not read.
- Counts of indicators (233) and drawing tools (86) are `rg` counts of registrations, not a quality audit.
- The as-of bug in section 2 is read from code and not reproduced. A test must confirm it before the fix.
- The `studio_v2` modules listed as dead are not imported by the live router, per `rg` on this date. The graph has not been queried. Deletion waits for graph and smoke checks.
- Competitor tier prices are as read on 2026-11-09 and change often.

Sources and licence checks: `docs/references/2026-11-studio-research.md`.
