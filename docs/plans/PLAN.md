# Plan

The single forward plan. Progress lives in [CHECKLIST.md](CHECKLIST.md). Updated 2026-11-08.

## 0. Use now

| Job | Command or tool |
|---|---|
| Frontend packages | `pnpm` (npm is gone) |
| Types | `pnpm typecheck` (tsrs); `pnpm typecheck:ref` (TypeScript 7) |
| Lint, format | `pnpm lint` (oxlint), `pnpm format` (oxfmt) |
| Web tests | `pnpm test` (Vitest); `pnpm test:e2e:labs` (Playwright) |
| All web checks | `pnpm check` |
| Web gates | `pnpm knip`, `pnpm dup`, `pnpm size`, `pnpm compiler:check` |
| Python | `cd backend`, then `uv sync`, `uv run ...` (Python 3.12) |
| Python checks | `uv run ruff check .`, `uv run pyrefly check app`, `uv run deptry .`, `uv run vulture app --min-confidence 80` |
| Python tests | `.venv/bin/python -m pytest tests -q -n auto` |
| Commit hooks | `lefthook install` once |
| Code search | codebase-memory first; TinyFish for web research |

## 1. Goal

One quant research platform where every number is real, every result says how far it can be trusted, and every screen matches the ML cinema standard.

Modules: Home, Chart, ML, Research, Screener, Factors, PCA, Volatility, Portfolio, Studio, and a widget workspace. PCA, Factors, Portfolio and Volatility keep their own pages. Only duplicated features merge.

## 1b. What the product is about

**Proposed position: the research platform that tells you whether to trust the answer.** Other tools give you a list, a chart or a backtest. We give the same things, then show the evidence, the limits and what would change the result.

- **For everyone.** A retail user gets a clear answer in plain words and one click. A professional opens the same result and finds the method, controls and raw numbers. One product, with depth on demand.
- **The loop.** Find, rank, prove, size, monitor. Every module serves a step of this loop and hands off to the next.
- **The edge.** Honest validation, shown on every result. It should be the reason people stay.

### Feature rule for every module

1. **Parity:** list what the best paid and free tools in India and globally offer. Everything people actually pay for goes in the feature table.
2. **Ours:** add what only we can do.
3. **Cut:** remove anything fancy, technical or unused. If a retail user or a professional would not miss it, it goes.
4. **Data:** a feature needing data we do not have is marked "needs data", with the source and cost, and is not faked.
5. Learn from competitors' ideas; build our own design. Do not copy their look, text or code.

Every product review, including those already written, is redone against this rule before its module is built.

### Global search (shared, built for Screener)

One search everywhere, at the level of TradingView's. It replaces the current weak search.

- Opens from anywhere by keyboard; a large overlay, not a small box.
- Finds symbol, name and ISIN; tolerant of typos; instant.
- Tabs for Symbols, Screens, Runs and Docs. Filter chips for Stocks, Funds, Indices, Forex and similar, shown only where we hold data.
- Rows show logo, ticker, full name, type and exchange.
- Hover or arrow keys reveal actions: open chart, see overview, add to screen, run in a lab.
- Shows recent and popular symbols before typing.

## 2. Where we are

| Area | Backend | Frontend | Plan doc |
|---|---|---|---|
| ML | Done | Done, tagged `ml-design-v1`; polish open | `ML_CINEMA_PLAN.md` |
| Research | Done | On the new workspace | `../reviews/product/RESEARCH_PRODUCT_REVIEW_FINAL_BATCH.md` |
| Screener | Done | Removed; rebuild | `../reviews/product/SCREENER_V2_PRODUCT_REVIEW.md` |
| Factors | Done | Removed; rebuild | `../reviews/product/FACTORS_V2_PRODUCT_REVIEW.md` |
| Volatility | Done | Removed; rebuild | `../reviews/product/VOLATILITY_V2_PRODUCT_REVIEW.md` |
| PCA | Done | Removed; rebuild | Product review missing |
| Portfolio | Done | Removed; rebuild | Product review missing |
| Studio | Working | Working | Product review missing |
| Chart | On legacy data files | Working; moving into Studio | Part of the Studio review |
| Widget workspace | None | Removed with Sovereign | Plan missing |
| Auth, payments, docs pages | Removed | Removed | Rebuild last |

## 3. Rules

- Build only with data we have. Print data limits on results.
- Open source first. Check licence, maintenance and bundle size, then adopt. Hand-write only what is our product.
- Each module moves to `LabConfig` and the shared kit. No new per-module primitives.
- Old v2 frontends were removed on 2026-11-06 (tag `pre-v2-frontend-removal`). Screener, Factors, PCA, Volatility and Portfolio have backends but no UI until rebuilt.
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

Licences and activity were checked on GitHub on 2026-11-06. Sources are in `../references/2026-11-open-source.md`. A pick is confirmed by a short spike in our app before it replaces anything.

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

### Chart system: ours

Charts are the product, so we own them. Open source is only the engine underneath: d3 for scales, uPlot or canvas for speed, `lightweight-charts` or KLineChart for price. Nothing ships with a library's default look. Every chart goes through `src/charts`, so its look, behaviour and options are ours.

Every exhibit gives the user as much freedom as possible:

| Control | Choice |
|---|---|
| Form | Switch between sensible chart types for the same data, including a table |
| Data | Series on or off, compare a run, change range, sort, top N |
| Scale | Linear, log, percent, indexed to 100, shared or separate axes |
| Look | Palette, line and bar style, labels, grid, density, light or dark |
| Marks | Annotations, reference lines, regime bands, events |
| Output | SVG, PNG, CSV, copy, add to report, send to workspace |
| Memory | Save as a preset per exhibit or for all exhibits; reset to our default |

Our default must already look finished, so nobody needs the controls. Options are declared once per chart type, so a new chart gets the panel for free and a saved preset works in the widget workspace.

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

### Merge order (6a)

From `../architecture/CROSS_MODULE_MERGE_MAP.md`. Each merge needs its golden tests first. The proposed defaults wait for the owner (map section 0).

| Order | Merge | Map steps | Needed by |
|---|---|---|---|
| 1 | Chart kit and UI: `Exhibit`, `KpiStrip`, `DataTable v2`, shared `RankList` | 18 | Screener, then every module |
| 2 | Validation statistics with golden fixtures first: DSR, PBO, purged CV, Monte Carlo into ML Validate | 0 to 4 | Screener Test |
| 3 | Execution and covariance kernels | 5, 6 | Factors, Volatility, PCA, Portfolio |
| 4 | Optimisers, risk, HAC and bootstrap, regime filter | 7 to 10 | Factors, Volatility, PCA, Portfolio |
| 5 | Data, universes, uploads, jobs | 11 to 14 | When a rebuild needs them. Screener needs the data path for India (map decision 16) |
| 6 | Trial ledger, formula language, scheduler, within Screener | 15 to 17 | Screener Test, Rank, Monitor |

Screener carries merges 1, 2 and 6. Merges 3 to 5 wait for the module that needs them. Proposed defaults, awaiting owner decision: PBO uses ML's form, the Research store owns the trial ledger, deflated Sharpe uses cross-trial variance, HRP uses ward linkage.

### Step 1: Finish ML (now)

From `ML_CINEMA_PLAN.md`: 17 items done, 3 partly done, 16 open, so about half. Two open items are platform work that belongs to Step 2, which leaves 14 for ML. The ticks may lag the code, so the first task is to check each one.

Before Screener, finish the items Screener reuses:

1. One tooltip and legend.
2. Empty, error and stale states.
3. Study panel groups and validation.
4. Compare mode and Inspect panel.
5. Finish RankList, Calendar heatmap and Treemap, then tick them.
6. Accessibility: chart summaries from the takeaway, AA contrast, visible focus.

Then hill climb: Heat table, Distribution, Scatter v2, Waterfall v2, Dendrogram linking, live overview tiles, pipeline diagram. A fresh design pass follows, using what was learned since the plan was written.

### Step 2: Screener

Spec: `../reviews/product/SCREENER_V2_PRODUCT_REVIEW.md`, redone 2026-11-08 against the feature rule. Sources: `../references/2026-11-screener-competitors.md`. It lists 83 features people pay for in India and globally: 35 exist in the backend, 29 are builds on data we hold, 19 need data we do not have. Twenty items are cut, with reasons.

The product is Screen, Rank, Test, Monitor, plus global search. Other screeners stop at a list. We add trust on every result, why-here, near-miss, proof in one click, a trial counter and alert precision. Plain-English screening is offered by Fiscal.ai, YCharts and TradingView already, so it is parity, not an edge.

| Stage | Build | Merge step used | Tools | Done when |
|---|---|---|---|---|
| 2.1 Workspace | `/screener` on `LabConfig`, 4 pages, manifest adapter | None | Current kit | Pages load from the backend manifest |
| 2.2 Kit | `Exhibit`, `KpiStrip`, `DataTable v2`, shared `RankList` | Merge 1 (step 18) | TanStack | ML uses them too |
| 2.3 Table and data | Server sort, page and count; column sets and saved views; filter chips with live counts and coverage; universes, watchlists, country; per-ticker price loader so about 400 Indian names open | Map decision 16 | DuckDB | 4,158 names scroll smoothly; no silent cap; an NSE name screens |
| 2.4 Formula | One language on `signal_lang`, named custom metrics, autocomplete, preview | Merge 6 (step 16), data path only | CodeMirror 6 | `core/formula.py` is a thin adapter |
| 2.5 Trust | Trust badges, hatched unknowns, why-here rows, near-miss explorer, evidence badge per filter | None | Funnel data | Each name shows every filter, value and margin |
| 2.6 Search and quick look | Global search (symbol, name, typo-tolerant; ISIN marked needs data); ticker drawer shared with ML; pros, cons and red flags; one-page report | None | Base UI, cmdk, Typst | Any symbol opens from anywhere by keyboard |
| 2.7 Rank | Composite, weights, waterfall, template gallery of about 30 formulas, ML ranker hand-off | None | ML Alpha | Rules and learned ranks compare side by side |
| 2.8 Test | S5 returns into ML Validate, data banner, trial counter, rolling start dates | Merge 2 (steps 0 to 4), merge 6 (step 15) | ML Validate | One PBO and deflated Sharpe; trials counted |
| 2.9 Monitor | Schedules, alert rules, delivered-alert tracking, precision scoreboard, digest, email, push and webhook | Merge 6 (step 17) | APScheduler, Apprise | An alert reaches a real channel and its outcome is scored |
| 2.10 Extras | Plain English to formula, API keys, share links | None | LLM call | Output is an editable formula |
| 2.11 Ship | Verified pages, palette, phone, accessibility, baselines | None | Playwright | Tag `screener-v1` |

Rules for the build:

- Every result prints its limits: 90-day statement lag, survivorship, 2021+ fundamentals.
- A feature that needs data we lack is marked "needs data" on screen and in the docs. It is not faked. The 19 items and their sources are in the review, section 4.
- Remove S4 leaderboard, correlation and historical strategy outputs, the S2 factor zoo, and S5 Monte Carlo and PBO duplicates.
- Open decisions needed before 2.8: PBO convention and trial ledger owner. Needed before 2.3: the India price-store decision.
- Data purchases (estimates, shareholding, long history, delisted, real-time) are business decisions after launch of `screener-v1`.

### The module recipe

Steps 3 to 6 repeat the same six stages. Module tables below list only what is specific.

1. **Clean:** remove fake numbers and duplicate keys; add the data banner.
2. **Workspace:** new route on `LabConfig`; forms from the backend manifest; prune inputs.
3. **Pages:** build each page from `Exhibit`, `KpiStrip`, `DataTable v2` and custom charts, with finding titles and chart controls.
4. **Merge:** pull in only the merge map steps this module needs, with golden tests first.
5. **New:** add the module's A++ features.
6. **Ship:** states, phone, accessibility, tests, baselines. Tag it and hill climb.

### Step 3: Factors

Spec: `../reviews/product/FACTORS_V2_PRODUCT_REVIEW.md`. About 4 to 6 sessions. A factor lab that shows its own limits; it is not sold as a Barra replacement.

| Stage | Build | Merge | Done when |
|---|---|---|---|
| 3.1 Clean | Remove the sine sparkline and duplicate manifest keys; add the look-ahead audit and banner; fix the `hedging_recommendation` doc mismatch | None | No number is drawn from a formula or literal |
| 3.2 Workspace | `/factors`, 14 features behind 5 pages, display-only controls removed | None | Forms come from `GET /features` |
| 3.3 Value and exposure | F01, F02, with F03 and F12 as tabs; holdings beside benchmark; DNA with units | None | Bottleneck exposure is named |
| 3.4 Regime and timing | F04, F05, with F06 persistence; regime pill; decay curves | Regime kernel (step 10) | Half-life has an interval and the published decay warning |
| 3.5 Test and capacity | F07, F09; capacity sweep; break-even cost | Execution kernel (step 5) | NAV matches the old run within tolerance |
| 3.6 Risk and construction | F08, F10, F11 as lenses | Covariance and construction (steps 6, 8) | One engine serves Factors and Portfolio |
| 3.7 Monitor | F13, alert precision, F14 export | Scheduler and alerts from Screener | Alerts show their matured hit rate |
| 3.8 Validate | F07 hand-off with trial count | Already built for Screener | One click reaches Validate |
| 3.9 Ship | Recipe stage 6; PDF and CSV report | Shared loader for this module (step 11) | Tag `factors-v1` |

### Step 4: Volatility

Spec: `../reviews/product/VOLATILITY_V2_PRODUCT_REVIEW.md`. About 5 to 7 sessions. Lead with V03 HAR, V01 estimators and V06 connectedness.

| Stage | Build | Merge | Done when |
|---|---|---|---|
| 4.1 Clean | Remove hero literals, cross-type fallback keys, the synthetic surface request, duplicate keys | None | Missing data shows the backend's message |
| 4.2 Workspace | `/volatility`, 6 pages, inputs pruned, 41-input Budget form cut down | None | Forms come from the manifest |
| 4.3 Estimators | V01; estimator choice with the reason | Range-based estimators (row 27) | Each ticker shows its best estimator and why |
| 4.4 Forecast | V02, V03; model confidence set exhibit | GARCH owner decision | No single "best" model without its set |
| 4.5 Regime | V04 on the kernel built for Factors | Reuse | Same answer as Factors on the same input |
| 4.6 Risk premium | V05, gated when IV data is missing | None | Page says plainly what it cannot compute |
| 4.7 Cross-asset | V06, V07 on the shared covariance engine | Reuse, plus one DCC | Spillover chart uses shared kernels |
| 4.8 Budget | V09, shared Kelly, Validate hand-off | Kelly (row 22) | Sizing lives in the Portfolio engine |
| 4.9 New | Data gap ledger on every page; pre-registered vol target | None | Saved targets are scored after the fact |
| 4.10 Ship | Recipe stage 6 | Shared loader for this module | Tag `volatility-v1` |

### Step 5: PCA

Write `../reviews/product/PCA_V2_PRODUCT_REVIEW.md` first; page cuts below are provisional. Lead with F04 residual stat-arb, F03 risk decomposition and F08 contagion.

| Stage | Build | Merge | Done when |
|---|---|---|---|
| 5.1 Review | Keep, cut, merge per feature, with TinyFish research | None | Review committed |
| 5.2 Clean | Remove preview filler; surface fallback flags in results | None | Requested and resolved data both show |
| 5.3 Workspace | `/pca` with the agreed pages | None | Forms come from the manifest |
| 5.4 Custom exhibits | Real biplot, MP overlay, loading heatmap, rolling loadings | PCA kernel (row 8) | Marchenko-Pastur bound is drawn on the spectrum |
| 5.5 Trade list | Stat-arb list with half-life and decay | Validate hand-off | Each trade has its evidence |
| 5.6 Monitor | Contagion alerts | Scheduler and alerts | Alerts show precision |
| 5.7 Ship | Recipe stage 6 | Shared loader | Tag `pca-v1` |

### Step 6: Portfolio

Write `../reviews/product/PORTFOLIO_V2_PRODUCT_REVIEW.md` first; 13 engines become fewer pages. Lead with F08 contagion, F04 reverse stress and F02 honest backtest.

| Stage | Build | Merge | Done when |
|---|---|---|---|
| 6.1 Review | Keep, cut, merge per engine, with research | None | Review committed |
| 6.2 Clean | One NAV key, real sparklines or none, infeasible points shown | None | Every number means what it says |
| 6.3 Workspace | `/portfolio` with the agreed pages and uploads | None | Forms come from the manifest |
| 6.4 Construction | Optimisers, HRP, Black-Litterman, risk budgets | Steps 6 and 8 | Golden tests match Riskfolio or skfolio |
| 6.5 Risk | VaR, reverse stress, contagion | Risk kernel (step 7) | One VaR across the platform |
| 6.6 Backtest | Honest backtest through Validate | Reuse | DSR uses the true trial count |
| 6.7 Ship | Recipe stage 6 | Shared loader, uploads, universes (steps 11 to 13) | Tag `portfolio-v1` |

### Step 7: Studio with Chart inside

Write `../reviews/product/STUDIO_PRODUCT_REVIEW.md` first. Sell Results and Validate first. Proposal: Chart becomes a tab in Studio and `/trade` redirects there, because it is not sold alone and Studio needs it for replay and results.

| Stage | Build | Done when |
|---|---|---|
| 7.1 Review | Keep, cut, merge the six modes, and decide Paper | Review committed |
| 7.2 Market data | Parquet-first data replaces `data_loader.py`, `robust_data_fetcher.py`, `indicators.py` | Those files are deleted |
| 7.3 Chart | Custom TradingView-grade chart: drawings, indicators, layouts, replay | Chart tab replaces `/trade` |
| 7.4 Develop | T3 Code shell ideas, `@pierre/diffs`, `@pierre/trees` | Strategy changes show as diffs |
| 7.5 Results and Validate | Same exhibits and Validate as the labs | No second report style |
| 7.6 Compose | One-click report with Typst | Certified run becomes a PDF |
| 7.7 Ship | Remove the rest of `studio_v2`; fix its manifest and tests | Tag `studio-v1` |

### Step 8: Widget workspace

Write the plan first. Research TakeProfit and OpenBB widget models.

| Stage | Build | Done when |
|---|---|---|
| 8.1 Model | Any exhibit can become a widget | One config, no copied charts |
| 8.2 Grid | Drag, resize, save, restore, templates | Layout survives reload |
| 8.3 Context | Linked ticker, date and universe | Changing a ticker updates linked widgets |
| 8.4 Live | Refresh, alerts and presets in widgets | Saved chart presets carry over |
| 8.5 Ship | Phone view, accessibility, baselines | Tag `workspace-v1` |

### Step 9: Product shell

| Stage | Build | Done when |
|---|---|---|
| 9.1 Home | New landing on real product screens | Old `landing` removed |
| 9.2 Auth | Accounts, profile, per-user data | Local user removed |
| 9.3 Data licence | Check what we can resell | Written decision |
| 9.4 Payments | Pricing and billing | Test payment passes |
| 9.5 Docs | Public docs, method notes, onboarding | Each module has a method page |

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
