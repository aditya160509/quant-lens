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
| Chart | On legacy data files | Working | Part of the Studio review |
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

| Need | Use | Licence | Status |
|---|---|---|---|
| App shell, sidebar, composer, panel feel | Study and borrow from `pingdotgg/t3code` | MIT | To do. Copy components freely, keeping the licence notice. It is a Vite and TanStack Router app, so port them into Next |
| Code and result diffs in Studio | `@pierre/diffs` | Apache-2.0 | To add |
| File tree in Studio | `@pierre/trees` | Apache-2.0 (confirm on install) | To add |
| Primitives | shadcn/ui on Radix | MIT | Partly in |
| Tables | TanStack Table and Virtual | MIT | Installed |
| Price charts | `lightweight-charts` | Apache-2.0 | Installed |
| Research charts | Own `src/charts` kit on d3 scales | Ours | Keep |
| Widget grid | `react-grid-layout` | MIT | Installed |
| Command palette | `cmdk` | MIT | Installed |
| Code editor | Monaco | MIT | Installed |

Remove after the rebuilds if nothing uses them: Plotly, ECharts, Recharts, visx, three.js and react-three, ogl, gsap, lenis, Supabase. Dockview is out until its licence is checked.

## 6. Order of work

### Phase 0: Foundation (now)
Finish repo hygiene, move to the toolchain target, get backend tests green on Python 3.12, measure the 4.6 GB launch, rotate leaked keys, decide on making the repo public.

### Phase 1: Shared kit
`Exhibit`, `KpiStrip`, `RankList`, `DataTable v2`, quick-look drawer, shell ideas from T3 Code. Move the tokens into one place. Every later phase is composition on this kit.

### Phase 2: Planning that is still missing
Product reviews for PCA, Portfolio and Studio. Widget workspace plan. Settle the merge decisions in `architecture/CROSS_MODULE_MERGE_MAP.md`.

### Phase 3: Validation merge
Golden fixtures, then one PBO, deflated Sharpe, purged CV and Monte Carlo owned by ML Validate. Then the execution and covariance kernels.

### Phase 4: Module rebuilds
Screener (10 steps in its review), Factors, Volatility, PCA, Portfolio. Each one: `LabConfig` wiring, exhibits, finding titles, data banner, tests, visual baselines, delete old pages.

### Phase 5: Studio and Chart
TradingView-grade charts. Replace `data_loader.py`, `robust_data_fetcher.py` and `indicators.py` with parquet-first market data. Add diffs and file tree.

### Phase 6: Widget workspace
TakeProfit-style grid built from module exhibits, with one shared ticker and date context.

### Phase 7: Product shell
New Home, auth, profile, payments and docs. Pricing only after the data licence is sorted.

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
