# Studio checklist

Open-source picks for every batch: [Studio research](../references/2026-11-studio-research.md) and the [open source stack](../references/2026-11-open-source.md). Copyleft engines (backtrader GPL-3.0, backtesting.py AGPL-3.0) are ideas only.

Tick Studio items here only. Spec: [product review](../reviews/product/STUDIO_V2_PRODUCT_REVIEW.md). Stages: [PLAN step 7](PLAN.md). Merge decisions: [merge map section 8](../architecture/CROSS_MODULE_MERGE_MAP.md). S, R, P and C numbers are the review's parity rows; "idea" numbers are its section 7. Items marked "reuse" use a Screener or kit piece that already exists.

This is the one list of everything to build. The review stays the spec and has no ticks. Chart is built inside Studio as a tab; there is no separate Chart checklist.

Tags: `E` easy, under a day, one file or a rename. `M` medium, a few days, several files, tests. `H` hard, a week or more, needs data or a decision. Work batches in order; within a batch, top to bottom. Tick nothing until verified.

## Rules for every batch

- Finish matches [the finish target](../reviews/design/ML_UI_ISSUES.md); none of the 23 logged issues appear here
- Competitors teach features only. TradingView, QuantConnect and Portfolio123 set what to include, never how it looks
- Every number is real. Unknown is shown as unknown, never zero or blank
- Every result and export prints its limits: US daily prices only, no delisted names, same-bar close fills, Monte Carlo assumes representative returns, walk-forward is a fixed-rule stability split, paper has no feed
- Nothing was run for the review (no servers, no tests); the `end_date` bug is read from code and needs a test first
- Delete only after the graph, `rg` and a backend smoke test (`AGENTS.md`)
- Nothing is capped silently

## Batch 1: Decisions

The review proposes these; the owner takes them. E1 M0 H0

- [ ] `E` Owner decides: Chart as a Studio tab with `/trade` redirecting; Paper stays as a ledger; Portfolio tab removed in favour of `/portfolio`; sensitivity grid re-pointed at the user's parameters or removed

## Batch 2: Fix what is wrong

Before any new feature. E4 M2 H0

- [ ] `E` Rename the sensitivity grid to say it tests the built-in momentum rule, or remove it from Validate
- [ ] `E` Enforce or remove the `universe` field on execute, and remove the `US_TOP50` default from the UI (idea 4: the strategy declares its universe and execute refuses others)
- [ ] `M` Reproduce the `end_date` bug with a test on a past date; fix `get_full_ohlcv` to anchor to `end_date`. Unverified until the test runs
- [ ] `E` Relabel walk-forward as a stability split in the UI and verdict text (R6)
- [ ] `E` Relabel Paper as a Ledger; remove the schedule and the free-text universe; take the universe from the saved portfolio version
- [ ] `M` Derive certification test status from stored runs, not from the browser payload

## Batch 3: Trust features

Sell Validate. E2 M3 H0

- [ ] `M` Parameter grid over the user's `PARAMS` in the sandbox, same costs, search size shown (idea 1, R7)
- [ ] `M` Trial counter per strategy; deflated Sharpe uses it and the count shows on the result (idea 2, R9; Research store owns the ledger, decision 4)
- [ ] `E` Fill-timing switch: same bar close, next bar open, next bar close; the choice is recorded in the result (idea 3, S5)
- [ ] `M` Look-ahead guard: the runner gives the strategy an expanding view of rows `0..i`, with a test that future rows are unreachable (idea 5)
- [ ] `E` Printed data-limit block on results and exports (Screener U10)

## Batch 4: Data and the end of studio_v2

E1 M1 H2

- [ ] `M` Move `SQLiteStore`, observability and request id to `services/shared/` (merge map decision 2)
- [ ] `H` Parquet-first loader replaces `data_loader.py`, `robust_data_fetcher.py` and `indicators.py`, with the per-ticker store for `.NS` names (decision 16)
- [ ] `H` Replace `/api/v2/data-studio/*` in the data inspector with the new loader; delete `studio_v2` after graph and smoke checks. Includes the unused `algorithm_lab`, `backtest`, `optimizer`, `robustness`, `factors` and `portfolio_risk` modules
- [ ] `E` Delete `data_loader.py` and `indicators.py` only after `backend/main.py` and `api/prices.py` stop importing them (both do today)

## Batch 5: Develop

Libraries the review adopts. E1 M1 H0

- [ ] `M` T3 Code shell ideas, `@pierre/diffs` and `@pierre/trees` (Apache-2.0, pinned versions) so strategy changes show as diffs (PLAN 7.4)
- [ ] `E` Undo and redo in the editor store with zundo (MIT)

## Batch 6: Chart as a tab

Only after Batch 4. E2 M2 H0

- [ ] `M` Chart price source moves to the parquet-first loader; `/api/prices` removed for Studio
- [ ] `M` Chart alerts: a server job, or labelled "while this tab is open"
- [ ] `E` Save drawings and indicator sets, or label them browser-local (drawing persistence is unverified)
- [ ] `E` Mount Chart as a Studio tab; `/trade` redirects. Read and keep `ReplayView` first (unverified)

## Batch 7: Merge and present

E0 M5 H0

- [ ] `M` Remove the Portfolio tab; link to `/portfolio`; keep the saved version id in the paper gate
- [ ] `M` Merge Stress into Validate (already a sub-tab)
- [ ] `M` Results and Validate use the shared exhibits (`Exhibit`, `KpiStrip`, `DataTable v2` from `frontend/src/kit/`); no second report style. `TearsheetView.jsx` layout unverified
- [ ] `M` Typst PDF of a certified run (P8)
- [ ] `M` Reuse: `QuickLook`, `FilterChips` and the Screener universe picker where Studio chooses tickers; TA-Lib replaces hand-rolled indicators

## Batch 8: Freedom

E2 M2 H0

- [ ] `E` Strategy as a file: source, parameters, data hash, costs and result as one bundle that reproduces with `reproduce` (idea 6)
- [ ] `M` Bring your own bars: OHLCV CSV with the Data Studio upload validation, scoped to the owner on disk (idea 7, decision 9)
- [ ] `M` Formula indicators in `signal_lang`, usable in code and on Chart; one language across Screener, Research and Studio (idea 8)
- [ ] `E` Layout and view presets extended from `reports.py` saved views to Chart layouts (idea 9)

## Batch 9: Ship

E2 M1 H0

- [ ] `M` Verified pages, phone layout, accessibility pass; Docker runner reported as 503 when absent (build state of `quant360-studio-runner:1.0` unverified)
- [ ] `E` Remove the rest of `studio_v2`; fix its manifest and tests
- [ ] `E` Tag `studio-v1`

## Later: free data

Tags set here; the review gives them as H. E0 M0 H3

- [ ] `H` Server-side alert delivery through Apprise (Screener rows 73 to 75)
- [ ] `H` Multi-asset execution: FX, crypto, futures (S7)
- [ ] `H` Order types: limit and stop (S6)

## Later: paid data

E0 M0 H3

- [ ] `H` Paper feed and scheduler with market hours (data licence needed)
- [ ] `H` Intraday execution with the hourly file (S9)
- [ ] `H` Corporate actions and point-in-time data (S10)
