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
- [ ] pnpm 12
- [ ] tsrs and TypeScript 7
- [ ] oxlint and oxfmt, remove ESLint
- [ ] Vitest, remove Jest
- [ ] Pyrefly, deptry, vulture, pip-audit
- [ ] pytest-xdist, with before and after timings
- [ ] knip, jscpd, size-limit, React Compiler
- [ ] lefthook with gitleaks
- [ ] `THIRD_PARTY.md`
- [ ] Replace BEA, BLS, EIA, FRED and QuickStats keys (owner)
- [ ] Choose history rewrite or keep (owner), then make repo public
- [ ] Measure the 4.6 GB launch per process and fix the top cause
- [ ] Run Playwright after the cleanup
- [ ] Remove `@supabase` and other unused npm packages

## Phase 1: Shared kit
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

## Phase 2: Planning
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

## Phase 3: Validation merge
- [ ] Golden fixtures
- [ ] `services/shared` maths package
- [ ] One PBO
- [ ] One deflated Sharpe
- [ ] One purged CV and Monte Carlo
- [ ] Execution kernel
- [ ] Covariance kernel

## Phase 4: Module rebuilds
- [ ] Screener: `/screener` on `LabConfig`
- [ ] Screener: DuckDB table, filters and counts
- [ ] Screener: CodeMirror formula bar on `signal_lang`
- [ ] Screener: why-here and near-miss
- [ ] Screener: quick-look drawer
- [ ] Screener: Rank and ML hand-off
- [ ] Screener: Test through ML Validate
- [ ] Screener: Monitor with APScheduler and Apprise
- [ ] Screener: templates and plain English to formula
- [ ] Screener: tag `screener-v1`, delete old pages
- [ ] Factors rebuild, delete old pages
- [ ] Volatility rebuild, delete old pages
- [ ] PCA rebuild, delete old pages
- [ ] Portfolio rebuild, delete old pages

## Phase 5: Studio and Chart
- [ ] Decide Chart as a Studio tab
- [ ] Parquet-first market data
- [ ] Delete `data_loader.py`, `robust_data_fetcher.py`, `indicators.py`
- [ ] TradingView-grade chart
- [ ] `@pierre/diffs` and `@pierre/trees`
- [ ] Remove the rest of `studio_v2`

## Phase 6: Widget workspace
- [ ] Widget list and layout
- [ ] Shared ticker and date context
- [ ] Save and restore layouts

## Phase 7: Product shell
- [ ] New Home
- [ ] Auth and profile
- [ ] Data licence
- [ ] Payments and pricing
- [ ] Public docs
