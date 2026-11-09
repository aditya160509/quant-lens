# Checklist

Tick items here only. The plan is in [PLAN.md](PLAN.md).

## Now: finish ML
- [x] Check every open item in the cinema plan against the code
- [x] One tooltip and legend
- [x] Empty, error and stale states
- [x] Study panel groups and validation
- [x] Compare mode and Inspect panel
- [x] Finish RankList, Calendar heatmap, Treemap
- [x] Accessibility pass
- [x] Heat table, Distribution, Scatter v2, Waterfall v2, Dendrogram linking
- [x] Live overview tiles and pipeline diagram
- [ ] Fresh design pass: [issues and finish target](../reviews/design/ML_UI_ISSUES.md)

## Phase 0: Foundation (deferred)
- [x] Remove v1 pages, legacy services and routers
- [x] Remove trades, Sovereign, CLI and auth
- [x] Organize docs
- [x] Python 3.12 with uv
- [x] Backend tests green (673 passed, 13 skipped, about 50s in parallel)
- [x] pnpm 12
- [x] tsrs and TypeScript 7
- [x] oxlint and oxfmt, remove ESLint (2026-11-07: about 990 warnings backlog; no bulk format yet)
- [x] Vitest, remove Jest
- [x] Pyrefly, deptry, vulture, pip-audit
- [x] pytest-xdist (130s to about 50s)
- [x] knip, jscpd, size-limit (duplication 11.6%, above the 5% target)
- [x] lefthook with gitleaks
- [x] `THIRD_PARTY.md`
- [x] History rewritten to remove old `.env` and `venv`
- [ ] Make repo public (owner)
- [x] Measure launch memory: about 1.6 GB with 5 pages compiled (plain requests; confirm in a browser)
- [x] Playwright: research spec run without the backend. Baselines refreshed for the six stale screenshots (signal dark/light, cinema 375/1440). Remaining failures are pages that need live results (`/research/canonical`, `/ml/cpcv`, `/ml/validate`); rerun with the backend up.
- [x] Remove `@supabase` and other unused npm packages

## Shared kit (with Step 2)
- [ ] Port T3 Code shell components
- [ ] Research the best open source option for each kit component
- [x] `Exhibit`
- [x] `KpiStrip`
- [x] `RankList` in all modules
- [x] `DataTable v2`
- [ ] Quick-look drawer
- [ ] One token source
- [ ] Shared tooltip and legend
- [ ] ML leftovers: Study panel, Inspect panel, Compare mode, empty and error states, accessibility

## Planning
- [ ] Agree the product position
- [ ] Redo ML, Research, Factors and Volatility reviews against the feature rule
  - Factors review redone 2026-11-09 (ML, Research and Volatility still open)
- [x] Factors product review
- [x] Volatility product review
- [x] Cross-module merge map
- [x] PCA product review
- [x] Portfolio product review
- [x] Studio product review
- [ ] Widget workspace plan
- [x] Decide PBO convention
- [x] Decide HRP linkage
- [x] Decide trial ledger owner
- [x] Decide the other merge map items

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
- [x] Redo product review: full paid feature parity, India and global
- [ ] Build: see [SCREENER_CHECKLIST.md](SCREENER_CHECKLIST.md); ship and tag `screener-v1`

## Step 3: Factors
- [ ] Build: see [FACTORS_CHECKLIST.md](FACTORS_CHECKLIST.md); ship and tag `factors-v1`

## Step 4: Volatility
- [ ] Redo product review against the feature rule (listed under Planning)
- [ ] Build: see [VOLATILITY_CHECKLIST.md](VOLATILITY_CHECKLIST.md); ship and tag `volatility-v1`

## Step 5: PCA
- [ ] Product review (written 2026-11-09)
- [ ] Remove preview filler; show fallback flags (PLAN 5.2; not in the review)
- [ ] Rolling loadings (PLAN 5.4; not in the review)
- [ ] Build: see [PCA_CHECKLIST.md](PCA_CHECKLIST.md); 33 correctness fixes first; ship and tag `pca-v1`

## Step 6: Portfolio
- [ ] Product review (written 2026-11-09)
- [ ] One NAV key; no fake sparklines (PLAN 6.2; not in the review)
- [ ] Build: see [PORTFOLIO_CHECKLIST.md](PORTFOLIO_CHECKLIST.md); ship and tag `portfolio-v1`

## Step 7: Studio and Chart
- [ ] Product review (written 2026-11-09); decide Paper
- [ ] Decide Chart as a Studio tab (first batch of the checklist)
- [ ] Custom chart with drawings, indicators, layouts, replay (PLAN 7.3; the review lists only the data and alert fixes)
- [ ] Build: see [STUDIO_CHECKLIST.md](STUDIO_CHECKLIST.md); Chart is built inside Studio; tag `studio-v1`

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

