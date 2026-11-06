# Plan

The single forward plan. Progress lives in [CHECKLIST.md](CHECKLIST.md). Updated 2026-11-06.

## 1. Goal

One quant research platform where every number is real, every result says how far it can be trusted, and every screen matches the ML cinema standard.

Modules: Home, Chart, ML, Research, Screener, Factors, PCA, Volatility, Portfolio, Studio, and a widget workspace. PCA, Factors, Portfolio and Volatility keep their own pages. Only duplicated features merge.

## 2. Where we are

| Area | Backend | Frontend | Plan doc |
|---|---|---|---|
| ML | Done | Done, tagged `ml-design-v1`; polish open | `design/ML_CINEMA_PLAN.md` |
| Research | Done | On the new workspace | `product/RESEARCH_PRODUCT_REVIEW_FINAL_BATCH.md` |
| Screener | Done | Old v2 pages | `product/SCREENER_V2_PRODUCT_REVIEW.md` |
| Factors | Done | Old v2 pages, fake sparkline | `product/FACTORS_V2_PRODUCT_REVIEW.md` |
| Volatility | Done | Old v2 pages, hardcoded hero | `product/VOLATILITY_V2_PRODUCT_REVIEW.md` |
| PCA | Done | Old v2 pages | Product review missing |
| Portfolio | Done | Old v2 pages | Product review missing |
| Studio | Working | Working | Product review missing |
| Chart | On legacy data files | Working; moving into Studio | Part of the Studio review |
| Widget workspace | None | Removed with Sovereign | Plan missing |
| Auth, payments, docs pages | Removed | Removed | Rebuild last |

## 3. Rules

- Build only with data we have. Print data limits on results.
- Open source first. Check licence, maintenance and bundle size, then adopt. Hand-write only what is our product.
- Each module moves to `LabConfig` and the shared kit. No new per-module primitives.
- A rebuild ships, then its old `/labs/*-v2` pages and `components/*-v2` are deleted in the same change.
- Commit and push to `main` after each verified step.

## 4. Quality bar and research

The working standard is the F1 project (`~/Documents/f1/daedalus-x/docs/build`). Copy its method here:

- Research before building anything visual or algorithmic, with TinyFish search then fetch, 3 to 6 sources, official docs first. Record sources in `docs/references/<task>.md`.
- Pick the best tool available today, not the familiar one. Prefer Rust and Go rewrites when they are faster. Measure before and after.
- Check API names against the installed version.
- T3 Code is one example, not the limit. For every UI area, find the best open source component first and use it. MIT and Apache code may be copied with its notice kept in `THIRD_PARTY.md`.

### Toolchain target

| Job | Now | Target (as used in F1) |
|---|---|---|
| Packages | npm | pnpm 12 |
| Type check | tsc | tsrs for speed, TypeScript 7 as reference |
| Lint | ESLint | oxlint `--type-aware` |
| Format | none enforced | oxfmt |
| Web tests | Jest | Vitest 5 |
| Web gates | none | React Compiler, knip, jscpd, size-limit |
| Python env | uv, Python 3.12 | Done |
| Python lint and types | ruff partly | ruff and Pyrefly |
| Python tests | pytest serial | pytest with xdist; record the time |
| Python gates | none | deptry, vulture, pip-audit |
| Commit hooks | none | lefthook with gitleaks on staged files |

## 5. Open source stack

Licences and activity were checked on GitHub on 2026-11-06. Sources are in `references/2026-11-open-source.md`. A pick is confirmed by a short spike in our app before it replaces anything.

### Interface

| Need | Pick | Licence | Why, and what we skip |
|---|---|---|---|
| Shell, sidebar, panels, composer | Port from `pingdotgg/t3code` | MIT | Copy components into Next and keep the notice. Its stack is Vite and TanStack Router, so the app itself is not adopted |
| Primitives | shadcn/ui on Base UI | MIT | Reported as shadcn's default since July 2026, and T3 Code uses it. Move off Radix as components are touched |
| Accessible edge cases | React Aria | Apache-2.0 | Only where Base UI lacks a component, such as date ranges |
| Command palette | `cmdk` | MIT | Installed; last pushed October 2025, so watch it |
| Toasts | `sonner` | MIT | Replaces `react-hot-toast` |
| Split panes | `react-resizable-panels` | MIT | Installed |
| Widget grid | `react-grid-layout` | MIT | Installed, with a hooks API. `gridstack` is the fallback. Dockview's licence was unclear, so it stays out |
| Code diffs, file tree | `@pierre/diffs`, `@pierre/trees` | Apache-2.0 | Studio only. Pin versions: a report says Pierre is being acquired |
| Code editor | Monaco | MIT | Studio only, loaded on demand |
| Formula bar | CodeMirror 6 with a Lezer grammar | MIT (confirm) | Far smaller than Monaco and built for custom languages. The GitHub mirror shows as archived, so check where it lives before adopting |

### Tables and charts

| Need | Pick | Licence | Why, and what we skip |
|---|---|---|---|
| Result tables | TanStack Table and Virtual | MIT | Installed and headless, so it matches our design. Our 4,158 rows do not need more |
| Grid fallback | Glide Data Grid | MIT | Canvas grid. Only if the spike shows TanStack lagging. AG Grid's best features are paid |
| Research exhibits | Our `src/charts` kit on d3 | Ours | The figures4papers look needs full control |
| Dense time series | uPlot | MIT | Small and fast on canvas. Use above about 10k points |
| Price chart | `lightweight-charts` v5 | Apache-2.0 | Keep. Spike KLineChart (Apache-2.0) for built-in drawing tools and indicators |
| GPU charts | None yet | | ChartGPU is young. SciChart and LightningChart are paid |
| Remove later | Plotly, ECharts, Recharts, visx, three.js, ogl, gsap, lenis | | Six chart and animation stacks are too many. Remove each once nothing imports it |

### Type

| Use | Pick | Licence |
|---|---|---|
| Interface | Inter, variable | OFL-1.1 |
| Numbers and code | JetBrains Mono, with IBM Plex Mono as the side-by-side test | OFL-1.1 |
| Headline test | Geist | OFL-1.1 |

Self-host through `next/font`. Numbers always use tabular figures. One screenshot test at 375 and 1440 decides the mono font.

### Data and backend

| Need | Pick | Licence | Why, and what we skip |
|---|---|---|---|
| Screener sort, filter, count | DuckDB over parquet | MIT | Reports show it streams parquet with a low memory peak, which also helps the RAM problem |
| Dataframe work | Polars for new code | MIT | Do not rewrite working pandas until it is measured as slow |
| Scheduling | APScheduler | MIT | Daily re-runs without a service |
| Alert delivery | Apprise | BSD-2-Clause | One library for email, Slack, Telegram and ntfy. Replaces the plan to wire one email provider |
| Phone push | ntfy | Apache-2.0 | Optional, self-hosted |
| Reports | Typst | Apache-2.0 | One-click PDF, as in F1 |
| Portfolio checks | skfolio, Riskfolio-Lib | BSD-3-Clause | Golden test references for our optimisers |
| Backtests | Our engines | | Next-session execution and honest costs are the product. NautilusTrader (LGPL) targets live trading, and vectorbt's licence needs review |
| Workspace ideas | OpenBB, TakeProfit | Check before copying | Study the widget model only. Copy no code |

## 6. Order of work

Phase 0 tooling is deferred by the owner. The repo stays private on GitHub.

### Step 1: Finish ML (now)

From `design/ML_CINEMA_PLAN.md`: 17 items done, 3 partly done, 16 open, so about half. Two open items are platform work that belongs to Step 2, which leaves 14 for ML. The ticks may lag the code, so the first task is to check each one.

Before Screener, finish the items Screener reuses:

1. One tooltip and legend.
2. Empty, error and stale states.
3. Study panel groups and validation.
4. Compare mode and Inspect panel.
5. Finish RankList, Calendar heatmap and Treemap, then tick them.
6. Accessibility: chart summaries from the takeaway, AA contrast, visible focus.

Then hill climb: Heat table, Distribution, Scatter v2, Waterfall v2, Dendrogram linking, live overview tiles, pipeline diagram. A fresh design pass follows, using what was learned since the plan was written.

### Step 2: Screener

Full spec: `product/SCREENER_V2_PRODUCT_REVIEW.md`. The product is Screen, Rank, Test, Monitor. It wins on the step after the filter, because other screeners stop at a list. Perplexity and Fiscal.ai already offer plain-English screening, so that alone is no edge; proof is.

Only these merge steps are pulled in. The rest of the merge map waits for the module that needs it.

| Stage | Build | Merge step used | Tools | Done when |
|---|---|---|---|---|
| 2.1 Workspace | `/screener` on `LabConfig`, 4 pages, manifest adapter | None | Current kit | Pages load from the backend manifest |
| 2.2 Kit | `Exhibit`, `KpiStrip`, `DataTable v2`, shared `RankList` | Step 18 | TanStack | ML uses them too |
| 2.3 Table | Server sort, page and count; column sets; filter chips with live counts | None | DuckDB | 4,158 names scroll smoothly; no silent cap |
| 2.4 Formula | One language on `signal_lang`, autocomplete, preview | Step 16, with only the data path it needs | CodeMirror 6 | `core/formula.py` is a thin adapter |
| 2.5 Trust | Why-here rows and near-miss explorer | None | Funnel data | Each name shows every filter, value and margin |
| 2.6 Quick look | Ticker drawer shared with ML | None | Base UI | Opens from any ranked table |
| 2.7 Rank | Composite, weights, waterfall, ML ranker hand-off | None | ML Alpha | Rules and learned ranks compare side by side |
| 2.8 Test | S5 returns into ML Validate, data banner | Steps 0 to 3 and 15 | ML Validate | One PBO and deflated Sharpe; trials counted |
| 2.9 Monitor | Schedules, alert rules, precision scoreboard, digest | Step 17 | APScheduler, Apprise | An alert reaches a real channel |
| 2.10 Extras | Template gallery, plain English to formula | None | LLM call | Output is an editable formula |
| 2.11 Ship | Verified pages, palette, phone, accessibility, baselines | None | Playwright | Tag `screener-v1`; old pages deleted |

Rules for the build:

- Every result prints its limits: 90-day statement lag, survivorship, 2021+ fundamentals.
- Remove S4 leaderboard, correlation and historical strategy outputs, the S2 factor zoo, and S5 Monte Carlo and PBO duplicates.
- Open decisions needed before 2.8: PBO convention, trial ledger owner.

### Step 3: Remaining merges

Execution and covariance kernels, purged CV, Monte Carlo and the rest of `architecture/CROSS_MODULE_MERGE_MAP.md`, each pulled in by the module that needs it.

### Step 4: Module rebuilds

First write the PCA and Portfolio product reviews. Then rebuild Factors, Volatility, PCA and Portfolio. Each one: `LabConfig`, exhibits, finding titles, data banner, tests, baselines, delete old pages.

### Step 5: Studio with Chart inside

Proposal: Chart becomes a tab in Studio and `/trade` redirects there. Chart is not sold on its own, Studio needs the same chart for replay and results, and it removes one app. Write the Studio review first, then add diffs and the file tree, and replace `data_loader.py`, `robust_data_fetcher.py` and `indicators.py` with parquet-first data.

### Step 6: Widget workspace

TakeProfit-style drag-and-drop dashboard built from module exhibits, with one shared ticker and date context.

### Step 7: Product shell

New Home, auth, profile, payments and docs. Pricing waits for the data licence.

### Deferred: Phase 0

Fast toolchain, the 3 failing Studio tests, the 4.6 GB measurement, key rotation and going public.

### Always on: UI hill climb

Every session: screenshot a page at 375 and 1440 in light and dark, score it, fix the worst item, commit.

## 7. Definition of done for a module

1. Every number traces to real data; no literals, demo values or silent fallbacks.
2. Empty, loading, error and stale states exist.
3. Each exhibit has a finding title.
4. Works at 375 and 1440, light and dark, and by keyboard.
5. Tests pass, with visual baselines that cover loaded results.
6. Old pages are deleted and docs updated.

## 8. Known risks

- Five real API keys sit in old git history. Rotate before the repo goes public.
- Statement fundamentals cover 2021 to 2025 with no delisted names, so backtests carry survivorship limits.
- Playwright baselines may not cover loaded exhibits.
- The 4.6 GB launch is unmeasured.
