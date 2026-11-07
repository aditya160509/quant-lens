# Checklist

Tick items here only. The plan is in [PLAN.md](PLAN.md).

## Now: finish ML
- [ ] Check every open item in the cinema plan against the code
- [ ] One tooltip and legend
- [ ] Empty, error and stale states
- [ ] Study panel groups and validation
- [ ] Compare mode and Inspect panel
- [ ] Finish RankList, Calendar heatmap, Treemap
- [ ] Accessibility pass
- [ ] Heat table, Distribution, Scatter v2, Waterfall v2, Dendrogram linking
- [ ] Live overview tiles and pipeline diagram
- [ ] Fresh design pass

## Phase 0: Foundation (deferred)
- [x] Remove v1 pages, legacy services and routers
- [x] Remove trades, Sovereign, CLI and auth
- [x] Organize docs
- [x] Python 3.12 with uv
- [ ] Backend tests green (3 fail: stale `category7_macro_regime` manifest entry)
- [x] pnpm 12
- [x] tsrs and TypeScript 7
- [x] oxlint and oxfmt, remove ESLint (2026-11-07: about 990 warnings backlog; no bulk format yet)
- [x] Vitest, remove Jest
- [ ] Pyrefly, deptry, vulture, pip-audit
- [ ] pytest-xdist, with before and after timings
- [x] knip, jscpd, size-limit (duplication 11.6%, above the 5% target)
- [x] lefthook with gitleaks
- [x] `THIRD_PARTY.md`
- [ ] Replace BEA, BLS, EIA, FRED and QuickStats keys (owner)
- [ ] Choose history rewrite or keep (owner), then make repo public
- [ ] Measure the 4.6 GB launch per process and fix the top cause
- [ ] Run Playwright after the cleanup
- [x] Remove `@supabase` and other unused npm packages

## Shared kit (with Step 2)
- [ ] Port T3 Code shell components
- [ ] Research the best open source option for each kit component
- [ ] `Exhibit`
- [ ] `KpiStrip`
- [ ] `RankList` in all modules
- [ ] `DataTable v2`
- [ ] Quick-look drawer
- [ ] One token source
- [ ] Shared tooltip and legend
- [ ] ML leftovers: Study panel, Inspect panel, Compare mode, empty and error states, accessibility

## Planning
- [ ] Agree the product position
- [ ] Redo ML, Research, Factors and Volatility reviews against the feature rule
- [x] Factors product review
- [x] Volatility product review
- [x] Cross-module merge map
- [ ] PCA product review
- [ ] Portfolio product review
- [ ] Studio product review
- [ ] Widget workspace plan
- [ ] Decide PBO convention
- [ ] Decide HRP linkage
- [ ] Decide trial ledger owner
- [ ] Decide the other merge map items

## Chart system
- [ ] Option schema per chart type
- [ ] Customise panel on every exhibit
- [ ] Form switch
- [ ] Scale and axis controls
- [ ] Palette and style controls
- [ ] Annotations and reference lines
- [ ] SVG, PNG and CSV export
- [ ] Saved presets
- [ ] Dense series engine with uPlot or canvas

## Step 2: Screener
- [ ] Redo product review: full paid feature parity, India and global
- [ ] Global search
- [ ] `/screener` on `LabConfig`
- [ ] Shared kit used by ML and Screener
- [ ] DuckDB table, filters and counts
- [ ] CodeMirror formula bar on `signal_lang`
- [ ] Why-here and near-miss
- [ ] Quick-look drawer
- [ ] Rank and ML hand-off
- [ ] Golden fixtures, one PBO, one deflated Sharpe
- [ ] Test through ML Validate, with trial ledger
- [ ] Monitor with APScheduler and Apprise
- [ ] Templates and plain English to formula
- [ ] Ship, tag `screener-v1`

## Step 3: Factors
- [ ] Remove sine sparkline, duplicate keys
- [ ] Look-ahead audit and data banner
- [ ] `/factors` from the manifest
- [ ] Value and exposure page
- [ ] Regime kernel; Regime and timing page
- [ ] Execution kernel; Test and capacity page
- [ ] Covariance and construction engines; Risk page
- [ ] Monitor page with alert precision
- [ ] Validate hand-off
- [ ] PDF and CSV report
- [ ] Shared loader for Factors
- [ ] Ship, tag `factors-v1`

## Step 4: Volatility
- [ ] Remove hero literals, fallbacks, synthetic surface request
- [ ] `/volatility` from the manifest, inputs pruned
- [ ] Estimators page with estimator choice
- [ ] Forecast page with confidence set
- [ ] Regime page on shared kernel
- [ ] Risk premium page, gated
- [ ] Cross-asset page, one DCC
- [ ] Budget page, shared Kelly, Validate hand-off
- [ ] Data gap ledger
- [ ] Pre-registered vol target
- [ ] Ship, tag `volatility-v1`

## Step 5: PCA
- [ ] Product review
- [ ] Remove filler; show fallback flags
- [ ] `/pca` from the manifest
- [ ] Biplot, MP overlay, loading heatmap, rolling loadings
- [ ] Stat-arb trade list with Validate
- [ ] Contagion alerts
- [ ] Ship, tag `pca-v1`

## Step 6: Portfolio
- [ ] Product review
- [ ] One NAV key; no fake sparklines
- [ ] `/portfolio` from the manifest, uploads
- [ ] Construction engines with golden tests
- [ ] Risk kernel, reverse stress, contagion
- [ ] Honest backtest through Validate
- [ ] Shared loader, uploads, universes
- [ ] Ship, tag `portfolio-v1`

## Step 7: Studio and Chart
- [ ] Product review; decide Paper
- [ ] Decide Chart as a Studio tab
- [ ] Parquet-first data; delete old data files
- [ ] Custom chart with drawings, indicators, layouts, replay
- [ ] T3 Code shell, diffs, file tree
- [ ] Shared exhibits in Results and Validate
- [ ] Typst one-click report
- [ ] Remove rest of `studio_v2`; tag `studio-v1`

## Step 8: Widget workspace
- [ ] Plan and research
- [ ] Any exhibit as a widget
- [ ] Grid, save, restore, templates
- [ ] Linked ticker, date, universe
- [ ] Refresh, alerts, presets
- [ ] Ship, tag `workspace-v1`

## Step 9: Product shell
- [ ] New Home
- [ ] Auth, profile, per-user data
- [ ] Data licence decision
- [ ] Payments and pricing
- [ ] Public docs and method pages

