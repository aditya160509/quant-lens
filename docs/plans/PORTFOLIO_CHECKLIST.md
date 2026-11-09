# Portfolio checklist

Open-source picks for every batch: [Open source stack](../references/2026-11-open-source.md). Portfolio review section 7 adds skfolio and Riskfolio-Lib as dev-only test oracles, Typst for the PDF and XlsxWriter for Excel. Ghostfolio and Portfolio Performance are copyleft: ideas only.

Tick Portfolio items here only. Spec: [product review](../reviews/product/PORTFOLIO_V2_PRODUCT_REVIEW.md). Stages: [PLAN step 6](PLAN.md). Merge decisions: [merge map section 8](../architecture/CROSS_MODULE_MERGE_MAP.md). F numbers are the review's engines, P numbers its parity rows, A1 to G6 its checklist ids; "idea" numbers are its section 6. Items marked "reuse" use a Screener or kit piece that already exists.

This is the one list of everything to build. The review stays the spec and has no ticks.

Tags: `E` easy, one file or one component on existing data. `M` medium, a new endpoint or page section with some new maths or tests. `H` hard, a new data path, new engine or multi-page UI. Work batches in order; within a batch, top to bottom.

## Rules for every batch

- Finish matches [the finish target](../reviews/design/ML_UI_ISSUES.md); none of the 23 logged issues appear here
- Competitors teach features only. Portfolio Visualizer, Sharesight and Morningstar set what to include, never how it looks
- Every number is real. Unknown is shown as unknown, never zero or blank; a hatched cell means not computable from our data
- Every result prints its limits: no survivorship correction, static sector labels, no delisted names, end-of-day data, no measured spreads
- The backend refuses or discloses what it cannot compute; the UI shows the same limit next to the number
- Nothing is capped silently

## Batch 1: Clean the backend

Before any UI. E4 M1 H0

- [ ] `E` A1: F04 verdict thresholds become request inputs, default 20% and 10%, shown in `meta`
- [ ] `E` A2: remove the Kelly ruin probability from `feature_10.py` output and the `ruin_probability` tables; keep the fraction table
- [ ] `E` A3: confirm the Amihud definition with the owner; switch to close-to-close, or rename the output to `open_to_close_amihud` everywhere
- [ ] `M` A4: confirm with the codebase graph and an import check, then delete the unused helpers (`reverse_stress_test`, `weight_stability_index`, `cvar_minimize`, `min_cvar_target`, `black_litterman_weights`, `geometric_growth_rate`, `turnover_optimal_kelly`, `regime_conditional_cov`). No deletion without the check
- [ ] `E` A5: study-level `meta` warning for survivorship on every backtest result (already in `bias_audit`)

## Batch 2: Workspace

B1 to B5. E1 M5 H0

- [ ] `M` B1: `/portfolio` route on `LabConfig`; forms from `GET /labs/portfolio/v2/features`, not hand-written
- [ ] `M` B2: input panel: universe (typed tickers with exact-match validation, or a saved universe), weights and objective, defaults from the manifest. Reuse the Screener universe picker and saved universes; uploads follow merge map decision 9
- [ ] `M` B3: output switcher per output (table, chart, CSV), reading `render` and `source` from the manifest (idea 1)
- [ ] `E` B4: `meta` limits strip on every page, with hatched cells for unknown values (idea 5)
- [ ] `M` B5: symbol search: replace the substring match in `GET /symbols` with prefix and exact ranking, reusing the Screener search
- [ ] `M` Reuse: `Exhibit`, `KpiStrip`, `DataTable v2` and `tableView`, `QuickLook` and `FilterChips` from `frontend/src/kit/`; one shared loader (merge map steps 11 to 13). No new per-module primitives

## Batch 3: Construct

C1 to C6. Covariance owner is Portfolio (decision 3). E2 M5 H0

- [ ] `M` C1: objective selector with six defaults (min variance, max Sharpe, risk parity, HRP, Black-Litterman, MVO); CVaR, maximum diversification and growth-optimal behind "advanced"
- [ ] `M` C2: frontier chart and weights comparison across objectives
- [ ] `M` C3: constraint report: binding constraints, with value and margin
- [ ] `E` C4: sizing lens: Kelly fraction table from F10 with the cost drag, without the ruin column
- [ ] `E` C5: covariance diagnostics lens: condition number and out-of-sample variance per estimator; F08 correlation heatmap as a lens, no separate network page
- [ ] `M` C6: friendly weights input: pasted tickers and weights, or a holdings CSV with market values converted to weights in one place (idea 7)
- [ ] `M` Golden tests for the optimisers against Riskfolio or skfolio (PLAN 6.4)

## Batch 4: Test

D1 to D5. E1 M4 H0

- [ ] `M` D1: honest performance card: DSR, PBO, PSR and Sharpe, colour-coded by thresholds the owner sets; literature defaults stated on the card
- [ ] `M` D2: equity curve, drawdown and monthly heatmap (F02 charts)
- [ ] `E` D3: walk-forward table with the in-sample to out-of-sample ratio
- [ ] `M` D4: trial counter: every objective and rerun counts and feeds `parameter_trials` (idea 6; Research store owns the ledger, decision 4)
- [ ] `M` D5: attribution lens: factor attribution always, Brinson when constituent weights exist, with the skill-versus-luck null

## Batch 5: Stress

E1 to E5. E1 M4 H0

- [ ] `M` E1: crisis replay chart with the ten windows (`historical_crisis_paths`); unavailable windows shown as unavailable
- [ ] `M` E2: scenario table and reverse-stress card, with plausibility percentile and asset shocks
- [ ] `E` E3: Monte Carlo fan chart from `monte_carlo`, with horizon and block length as inputs
- [ ] `M` E4: macro exposure lens (F05): target versus observed beta, alerts and the market-implied warning
- [ ] `M` E5: liquidity lens (F07): days-to-liquidate table, non-USD symbols listed as refused

## Batch 6: Freedom and export

F1 to F5. E1 M3 H1

- [ ] `M` F1: shareable run link with the input payload and view state in the URL (idea 2)
- [ ] `M` F2: run diff for two results: weights, risk contributions, drawdowns, DSR (idea 3)
- [ ] `M` F3: assumption sliders that rerun through the job store with progress (idea 4)
- [ ] `H` F4: one-page PDF report from the current view, with Typst (P20)
- [ ] `E` F5: CSV, LaTeX and JSON export from the current view (routes exist; wire the buttons; Excel with XlsxWriter per section 7)

## Batch 7: Ship

One Vitest or Playwright smoke check per page; no new test framework. E1 M1 H0

- [ ] `M` Smoke check per page for the switcher, diff and sliders; verified pages, phone layout, accessibility and baselines (PLAN recipe stage 6)
- [ ] `E` Tag `portfolio-v1`

## Later: free data

Tags are the review's G items. E0 M0 H5

- [ ] `H` G1: F06 regime lens, after a run-time check (the refit loop over every date is slow)
- [ ] `H` G2: F13 multi-strategy on Monitor, with user return uploads
- [ ] `H` G3: F09 signal decay hand-off to ML
- [ ] `H` G6: P1 holdings tracker with trade input
- [ ] `H` Monitor page: saved portfolios and drift alerts (P21; shared with the Screener scheduler)

## Later: paid data

E0 M0 H2

- [ ] `H` G4: F11 execution, with a broker feed for measured spreads
- [ ] `H` G5: F12 systemic, with fund holdings data
