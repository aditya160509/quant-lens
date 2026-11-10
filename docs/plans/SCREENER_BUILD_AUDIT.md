# Screener build audit

Date: 2026-11-10. Read-only audit; no code or checklist changed. Method: traced each item from the page code (`frontend/src/modules/screener`, `kit`, `workspace`, `modules/research`) to `backend/app/api/screener_v2.py` and `services/screener_v2`, then tried what was practical in the built-in browser at `/screener` (dark theme, one run at a time: Screen on the top 50 by liquidity, Composite and Backtest on 12 pasted US names).

## Summary

| Status | Count |
|---|---|
| WORKS (seen on the page) | 27 |
| WIRED (connected, not seen working) | 61 |
| HIDDEN | 6 |
| BROKEN | 5 |
| BACKEND ONLY | 4 |
| FRONTEND ONLY | 0 |
| MISSING | 34 |
| Total de-duplicated items | 137 |

- WORKS only: 27 of 137 = 20%.
- WORKS plus WIRED: 88 of 137 = 64%. This is an upper bound: WIRED means the code path exists, not that it was run.
- Counting HIDDEN as built: 94 of 137 = 69%.

The Screen page, composite ranking with its waterfall, the composite-vs-SPY chart, run provenance, the scatter and the universe picker work. The two things the owner will hit first are broken: the default universe (top N by liquidity) mixes currencies, so Rank fails and the market-cap filter fails.

## By area

| Area | Items | WORKS | WIRED | WORKS % | WORKS+WIRED % |
|---|---|---|---|---|---|
| Foundation | 8 | 5 | 3 | 62 | 100 |
| Screen | 31 | 8 | 19 | 26 | 87 |
| Search | 6 | 2 | 3 | 33 | 83 |
| Quick look | 4 | 0 | 4 | 0 | 100 |
| Formula | 7 | 0 | 4 | 0 | 57 |
| Freedom | 17 | 4 | 9 | 24 | 76 |
| Trust | 7 | 1 | 6 | 14 | 100 |
| Rank | 10 | 4 | 1 | 40 | 50 |
| Test | 8 | 0 | 6 | 0 | 75 |
| Monitor | 6 | 0 | 6 | 0 | 100 |
| Extras (behind More) | 4 | 0 | 0 | 0 | 0 (all HIDDEN) |
| Signature | 2 | 0 | 0 | 0 | 0 |
| Ship | 5 | 0 | 0 | 0 | 0 |
| Frontend plan only | 10 | 3 | 0 | 30 | 30 |
| Later data | 12 | 0 | 0 | 0 | 0 |

## Top gaps, by importance

1. Rank fails on the default universe: "Non-USD portfolios require explicit instrument_metadata and calendar_ticker". Top N by USD liquidity pulls in KRW, JPY and ZAc names.
2. Market-cap filter fails on that universe: "Requested filter Market cap is unavailable in the local data". Market cap is blank for all 50 rows.
3. Composite is slow: about a minute for 12 names in the browser against a target of 2 s on 50.
4. "Train a ranker on this" is unreachable: the Rules and ML tab shows "Unknown" until an ML run exists, and the button only renders after that.
5. Factor correlation heatmap renders with column labels as dashes.
6. No live counts on filter pills and no distribution sliders; the plan's core filter experience is Min/Max boxes.
7. Test page (backtest, proof, trial ledger, rolling starts) never seen with results; the earlier Backtest run on the default universe is recorded as Failed.
8. Strategies (sc04, Piotroski and Altman pages) exist in the backend with no page.
9. Valuation-ready stocks is 0 of 50 and Altman Z, RSI-type technicals and trend are blank on the 50-name run, so most quality and technical filters would return nothing.
10. Plan items that make filters usable are missing: add metric from header, column sets, multi-sort, footer medians, bulk select, chart grid.
11. Plain English, Markets, share links and API keys are all behind More, and More is not in the main flow.
12. CSV universe upload, JSON and ticker-list export are backend routes with no buttons.
13. Docs tab in search, header Save/Share/Export, keyboard Shift+F and F are absent.
14. Live funnel and time machine (Batch 10) are not built.
15. Ship batch is entirely open: phone, accessibility, baselines, tag `screener-v1`.

## Checklist ticks that disagree with what I found

- SCREENER_CHECKLIST Batch 2 "Filter by sector, industry, exchange, market-cap range (1)": ticked; market cap fails on the default run.
- Batch 2 "Live count after each filter, with the bottleneck filter shown (42)": ticked; the funnel shows after a run only, no live count on pills.
- Batch 2 "Chips with greater, less, between, in, top N, and live counts (37)": ticked; no live counts, and the pill editor offers Min/Max only.
- Batch 2 "Export CSV, Excel, JSON, ticker list (56)": ticked; JSON and ticker list have no UI.
- Batch 3 "Tabs: Symbols, Screens, Runs, Docs": ticked; no Docs tab.
- Batch 7 "ML hand-off; rules and learned ranks side by side (81, U6)": ticked; dead end without a prior ML run.
- Batch 5 "Every output opens as table, bars, scatter, heatmap, treemap, ranked list, distribution or mini-chart grid": ticked; no distribution or mini-chart grid.
- Batch 5 "Group by and pivot": ticked; no pivot.
- Batch 4 "Type a formula as a new column; filter, sort, rank, chart": ticked; only wiring seen, not run.
- FRONTEND_PLAN section 15 "Composite runs on default settings": ticked; it fails on the default universe.
- Under-claims (unticked but present): "Compare with benchmark (79)" works inside Composite; "Exhibits hide, expand" partly works.
- Rolling start dates (83) is ticked but is one start per year computed in the browser.
- OPEN_ISSUES "55 items marked (untested)" still stands; I tested few of them.

## Could not check

- Test, Monitor, Saved, More, Formula, Valuation pages and the quick-look drawer were not opened in the browser after the pane dropped its preview; they are WIRED from code only.
- Backtest on 12 names completed in the job store, but I did not see its page.
- Why-here, near-miss with a real filter, diff, downloads, share links, Apprise, schedules, as-of runs and any Indian names: not run.
- Runs over 50 names and speed targets other than Composite: not timed.
- The two review files (HARD_REVIEW, REVIEW_2) and `docs/evidence/.../review.md` are mostly backend speed and correctness fixes or an older UI review; I did not verify each edit, so they are not itemised. OPEN_ISSUES.md lists their Rust, memory and data items as open.
- Many FRONTEND_PLAN items (sections 3 to 14: tooltips, skeletons, toasts, output card settings, drawer radar, statements sparklines and others) were not traced one by one; only the groups in the table are counted.

## Full table

| Item | Source | Status | File:line | Evidence |
|---|---|---|---|---|
| Shared kit: KpiStrip, DataTable, Exhibit | SC B1 | WORKS | kit/DataTable.tsx:79 | KPI cards and table seen on Screen |
| /screener on LabConfig, pages Screen, Rank, Test, Monitor | SC B1 | WORKS | modules/screener/screenerLab.ts:93 | Nav and pages load from manifest |
| Every passing name reaches table, no silent cap | SC B1 (48) | WORKS | screenerLab.ts:104 | 34 of 34 passing rows listed |
| Virtual scroll for thousands of rows | SC B1 | WIRED | kit/DataTable.tsx:206 | Virtualizer above 200 rows; not run at scale |
| Result header: count, universe, as-of, updated, hash | SC B1 | WORKS | screenerLab.ts:56 | Seen: 34 of 50 names pass, as of, updated, data hash |
| Limits printed on results | SC B1 (U10) | WORKS | screenerLab.ts:72 | Caveats block seen on Screen and Rank; Test banner not seen |
| Panels close and give space to content | SC B1 | WIRED | workspace/WorkspaceShell.tsx | Not exercised |
| Shared price loader; an NSE name screens | SC B1 (9) | WIRED | backend core/data_loader.py | Not tested with an Indian name |
| Sector, industry, exchange, country, currency filters | SC B2 (1,8) | WIRED | filters/InFilter.tsx; screenerLab.ts:140 | Widgets mapped to inputs; not exercised |
| Market-cap range filter | SC B2 (1) | BROKEN | screenerLab.ts:80 | Min 100B on Top 50 run failed: Requested filter Market cap is unavailable in the local data |
| Price, dollar-volume floors, penny-stock exclusion | SC B2 (3) | WORKS | backend features/inputs.py | Funnel showed Penny stock exclusion removing 16 of 50 |
| Valuation filters P/E, P/B, P/S, EV | SC B2 (15) | WIRED | UniverseBar.tsx:20 | Pills exist; Valuation-ready stocks 0 of 50 on this run |
| Profitability, growth, health filters | SC B2 (16-18) | WIRED | filters/UniverseBar.tsx:20 | Pills and Add filter list; not run with values |
| Piotroski F-score column | SC B2 (19) | WORKS | screenerLab.ts:79 | Passed counts 1 to 8 seen per row |
| Altman Z | SC B2 (19) | WIRED | screenerLab.ts:79 | Column present, unknown for all 34 rows |
| Momentum, 52w proximity | SC B2 (20) | WORKS | screenerLab.ts:79 | Prox52 values seen |
| Technicals RSI, MACD, ADX, Bollinger | SC B2 (21) | WIRED | screenerLab.ts:79 | Columns exist, dashes in this run |
| Risk: volatility, drawdown, beta | SC B2 (22) | WORKS | screenerLab.ts:79 | Realized vol and drawdown values seen |
| Liquidity: Amihud, volume ratio | SC B2 (23) | WIRED | backend core/panel.py | Amihud percentile dash in run |
| Percentile versus sector or universe as filter | SC B2 (24) | WIRED | modules/research/FilterChips.tsx | Percentile columns show; filter not exercised |
| Chips: greater, less, between, in, top N | SC B2 (37) | WIRED | UniverseBar.tsx:74; FilterChips.tsx | Pill editor is Min/Max only; top N and in sit in Add filter |
| Live count on each pill before run | SC B2 (42); FP s5 | MISSING | UniverseBar.tsx:74 | Typing a value showed no count; no count endpoint |
| Funnel with bottleneck after run | SC B2 (42) | WORKS | screenerLab.ts:112 | Funnel tab table: remaining, removed, bottleneck marked; a table, not a drawn funnel |
| Market-cap bucket counts | SC B2 (2) | WIRED | screenerLab.ts:112 | Output mounted in Funnel tab; not opened |
| Run as of a past date | SC B2 (6) | WIRED | UniverseBar.tsx:61 | Date input present; not run |
| Coverage per metric | SC B2 (7) | WIRED | screenerLab.ts:113 | Coverage tab exists; not opened |
| Pasted tickers as universe | SC B2 (4) | WORKS | UniverseBar.tsx:138 | Paste gave 14 stocks, bad tickers rejected by run |
| Saved universes and watchlists as universe | SC B2 (4,5) | WIRED | UniverseBar.tsx:134 | Listed in picker; none saved to try |
| CSV upload of a universe | SC B2 (4) | BACKEND ONLY | api/screener_v2.py:574 | /uploads route; no UI in the picker |
| Watchlist as filter | SC B2 (5) | WIRED | filters/WatchlistFilter.tsx | Not exercised |
| Returns 1D, 1M, quarterly variance | SC B2 | WORKS | screenerLab.ts:79 | Values seen |
| Sparkline column (Trend 3m) | SC B2 | WIRED | kit/DataTable.tsx:220 | Column present, all dashes in run |
| Row actions: star, alert, ML, Research | SC B2 (59) | WIRED | screener/RowActions.tsx:12 | Mounted via rowActions; not clicked |
| Undo, redo, disable a filter | SC B2 (47) | WIRED | modules/research/formHistory.ts | History file exists, not exercised |
| AND/OR groups and nesting | SC B2 (38) | WIRED | filters/FilterTree.tsx | Not exercised |
| Sector-relative percentile bars in rows | SC B2 (51) | WORKS | screenerLab.ts:81 | Bars drawn in table |
| Trust badge and hatched unknowns | SC B2 (U1) | WIRED | screenerLab.ts:68; DataTable.tsx:340 | Warn tone when under 60 percent known; hatch option on |
| Export CSV and Excel | SC B2 (56) | WIRED | kit/DataTable.tsx:254 | Buttons in Table menu; no download tried |
| Export JSON and ticker list | SC B2 (56) | BACKEND ONLY | api/screener_v2.py:590 | /export routes; no UI buttons |
| Search overlay from anywhere | SC B3 | WIRED | workspace/WorkspaceShell.tsx:13 | Mounted; not opened |
| Tabs Symbols, Screens, Runs | SC B3 | WIRED | search/SearchOverlay.tsx:16 | Tabs All, Symbols, Screens, Runs, Actions |
| Docs tab | SC B3 | MISSING | search/SearchOverlay.tsx:16 | No Docs tab |
| Hover and arrow actions | SC B3 | WIRED | SearchOverlay.tsx:131 | Chart, overview, add, sector actions coded |
| Recent and popular before typing | SC B3 | WORKS | search/state.ts; kit/QuickLookData.ts | Popular list seen in picker (same hook) |
| Universe selector as picker | SC B3 | WORKS | filters/UniverseBar.tsx:88 | Sizes, paste, saved, search seen |
| Drawer with Overview, Ratios, Health, Peers, Financials, Compare | SC B3 (60-66) | WIRED | kit/QuickLook.tsx:71 | Tabs coded; no ticker opened |
| One-page PDF | SC B3 (67) | WIRED | kit/QuickLook.tsx:85 | Link to /lookup/{t}/pdf; not downloaded |
| Compare up to 6 names | SC B3 (55) | WIRED | api/screener_v2.py:192 | Route and tab; not tried |
| Pros, cons, red flags | SC B3 (65) | WIRED | kit/QuickLook.tsx | Not opened |
| CodeMirror formula bar with autocomplete, preview | SC B4 | WIRED | formula/FormulaBar.tsx; FormulaControl.tsx:12 | Preview endpoint wired; Formula page not run |
| Named custom metrics | SC B4 (40) | WIRED | FormulaControl.tsx:30 | PUT /metrics; not saved |
| Formula as column, filter, sort | SC B4 (40) | WIRED | FormulaControl.tsx | Not exercised |
| Historical functions lag, change, cross | SC B4 (41) | BACKEND ONLY | backend core/formula.py | No UI help; unchecked in code |
| core/formula.py thin adapter on signal_lang | SC B4 | MISSING | OPEN_ISSUES.md Code to clean up | Two engines remain |
| Plain English to formula | SC B11 (46) | HIDDEN | extras/MorePage.tsx:31 | Under More; not run |
| About 30 templates gallery | SC B7 (44) | WIRED | home/ScreenerHome.tsx:97 | Overview shows gallery; clicks not tested |
| Scatter lens | SC B5 (53) | WORKS | trust/Charts.tsx; screenerLab.ts:108 | Scatter drawn with X/Y selects, Lasso, Select all 29 |
| Sector treemap lens | SC B5 (52) | HIDDEN | screenerLab.ts:91 | Only as View menu alternate |
| Heatmap lens | SC B5 (52) | WIRED | screenerLab.ts:113 | Heatmap output in More tab; not opened |
| Mini-chart grid / chart grid view | SC B5 (54) | MISSING | screenerLab.ts | No grid view registered |
| Any column as x, y, size, colour, group, facet | SC B5 | WIRED | trust/Charts.tsx | Only X and Y pickers seen |
| Filter from a chart (brush) | SC B10 | WIRED | trust/Charts.tsx | Lasso and Filter to N selected shown |
| Add metric by typing name from header | SC B5 (49) | MISSING | kit/DataTable.tsx:247 | Table menu only shows or hides existing columns |
| Absolute or percentile per column | SC B5 (50) | WIRED | kit/DataTable.tsx:277 | Select coded; not used |
| Group by with median, mean, sum | SC B5 | WIRED | kit/DataTable.tsx:260 | Group only; no pivot |
| Conditional formats | SC B5 | WIRED | kit/DataTable.tsx:76 | Bars, heat, signed, rule |
| Density, order, width, pin, hide | SC B5 | WIRED | kit/DataTable.tsx:251 | Controls coded |
| Exhibits hide, expand, view menu | SC B5 | WORKS | research/OutputCard.tsx | View menu and expand icon seen; checklist says unticked |
| Saved table views, this or all | SC B5 (49) | WIRED | kit/DataTable.tsx:297 | Not saved |
| State in URL | SC B5 | WORKS | screener/UrlState.tsx | URL carried form= and table= after edit |
| Export PNG, SVG, PDF | SC B5 | WIRED | research/ReportCard.tsx:91 | PDF report link; Report button seen |
| Keyboard Cmd+Enter run | FP s3 | WORKS | workspace/WorkspaceShell.tsx | Ran three studies with it |
| Keyboard Shift+F, F, brackets | FP s3 | MISSING | workspace/WorkspaceShell.tsx:95 | Only slash found |
| Why-here row expander | SC B6 (U2) | WIRED | trust/Explain.tsx:29 | Row detail coded; not opened |
| Near-miss explorer | SC B6 (U3) | WIRED | trust/Explain.tsx:71 | Rendered empty state only (no range filter ran) |
| Evidence badge per filter | SC B6 (U8) | WIRED | trust/Explain.tsx:24 | Not seen |
| Reproducible run id, data hash, formula | SC B6 (U9) | WORKS | trust/Explain.tsx:92 | Run id, As of, Data, Formula shown |
| Screen diff between runs | SC B6 (U9) | WIRED | trust/Explain.tsx:110 | Run chooser seen; diff not run |
| Explain difference A vs B | SC B6 | WIRED | trust/Explain.tsx:56 | Not tried |
| Sensitivity strip | SC B10 | WIRED | trust/Charts.tsx | Empty state shown: No range filter set |
| Composite ranking table with factor scores | SC B7 (43) | WORKS | screenerLab.ts:119 | 12-name run: scores, ranks seen |
| Score waterfall for top name | SC B7 | WORKS | rank/RankViews.tsx:15 | GOOGL contributions seen |
| Weight sliders | SC B7 | WIRED | rank/ComponentWeights.tsx | Widget coded; not moved |
| Composite on default Top 50 universe | FP s15 | BROKEN | backend composite error | Run failed: Non-USD portfolios require explicit instrument_metadata and calendar_ticker |
| Composite under 2 s on 50 names | FP s15 | BROKEN | backend composite.py | 12 names took about a minute in the browser |
| Composite vs SPY backtest | SC B8 (79) | WORKS | screenerLab.ts:124 | Strategy 2.02 vs benchmark 1.81 chart; checklist unticked |
| Factor correlation heatmap | FP s10 | BROKEN | screenerLab.ts:122 | Renders with col labels as dashes |
| Sector breakdown, redundancy alerts, regime bars | FP s10 | WORKS | screenerLab.ts:122 | Tables seen; alert column all dashes |
| Rules vs ML ranks, train a ranker | SC B7 (81,U6) | BROKEN | rank/RankViews.tsx:38 | Tab shows Unknown; Train button hidden until an ML run exists |
| Strategies sc04 in catalog | FP s10 | BACKEND ONLY | backend features/feature_04.py | Not in CATALOG, no page |
| Backtest a screen with rebalances | SC B8 (78) | WIRED | screenerLab.ts:127 | 12-name job completed; page not viewed |
| Overfitting: deflated Sharpe, PBO, bootstrap | SC B8 (80) | WIRED | test/ProofViews.tsx:50 | Computed in panel; not viewed |
| Prove it in ML Validate | SC B8 (U4) | WIRED | test/ProofViews.tsx:61 | Not clicked |
| Trial ledger counter | SC B8 (U5) | WIRED | test/ProofViews.tsx:54 | /ledger fetch; not viewed |
| Rolling start dates | SC B8 (83) | WIRED | test/ProofViews.tsx:76 | One start per year, in browser |
| Data banner | SC B8 | WIRED | screenerLab.ts:72 | Not viewed |
| Services/shared single PBO and DSR | SC B8 | MISSING | OPEN_ISSUES.md | PBO copies remain |
| Remove old S4 leaderboard, S2 zoo, S5 duplicates | SC B8 | MISSING | OPEN_ISSUES.md | S5 PBO duplicate remains |
| Saved screens, rename, duplicate | SC B9 (70) | WIRED | saved/SavedPage.tsx:20 | Not opened |
| Scheduled re-runs | SC B9 (72) | WIRED | SavedPage.tsx:76 | Select coded |
| Run history entries, exits | SC B9 (71) | WIRED | SavedPage.tsx:88 | Not opened |
| Apprise email, push, webhook | SC B9 (73,74) | WIRED | SavedPage.tsx:82 | URL input; capabilities.email_delivery is false |
| Price and fundamental alerts, digest | SC B9 (75,76) | WIRED | screenerLab.ts:29 | sc06 and sc08 pages not opened |
| Delivered-alert precision | SC B9 (U7) | WIRED | SavedPage.tsx:90 | Not opened |
| Crypto, forex, futures, hourly | SC B11 (14,26) | HIDDEN | extras/MorePage.tsx:12 | Under More |
| Share links | SC B11 (45) | HIDDEN | extras/MorePage.tsx:59 | Under More |
| API keys | SC B11 (57) | HIDDEN | extras/MorePage.tsx:70 | Under More |
| Chart patterns, weak evidence | SC B11 (25) | HIDDEN | extras/MorePage.tsx:20 | Under More Markets |
| Live funnel while moving a threshold | SC B10 | MISSING | UniverseBar.tsx | No live counts |
| Time machine as-of drag | SC B10 | MISSING | UniverseBar.tsx:61 | Date input only |
| Verified pages and palette actions | SC B12 | MISSING | none | Unticked |
| Phone layout | SC B12 | MISSING | kit/DataTable.tsx:351 | Card rows exist; not verified |
| Accessibility pass | SC B12 | MISSING | none | Unticked |
| Visual baselines | SC B12 | MISSING | none | Unticked |
| Tag screener-v1 | SC B12 | MISSING | git tag | No screener tag |
| Dark palette, labelled nav | FP s3 | WORKS | workspace/workspace.css | Seen |
| Overview stat cards, gallery, sectors | FP s4 | WORKS | home/ScreenerHome.tsx:66 | Cards seen (3,199 / 1,343 / 3,811 / 4) |
| Universe size 25 to 1000, cap 1000 | FP s5 | WORKS | UniverseBar.tsx:17 | Seen |
| One-row header with Save, Share, Export | FP s3 | MISSING | research/ResearchApp.tsx | Header has title and Run only |
| Filter slider with distribution | FP s5 | MISSING | UniverseBar.tsx:74 | Min/Max boxes only |
| Column sets as tabs | FP s6 | MISSING | kit/DataTable.tsx | None |
| Multi-sort, footer medians, bulk select | FP s6 | MISSING | kit/DataTable.tsx | Single sort; no footer |
| Rank basis, presets, multi-market in picker | FP s5 | MISSING | UniverseBar.tsx:88 | Liquidity only |
| Distribution and live-count endpoints | FP s15 | MISSING | api/screener_v2.py | None |
| Overview search box, breadth strip, sector treemap | FP s4 | MISSING | ScreenerHome.tsx | None |
| Nifty lists, logos, India universe, earnings, delivery, insider, 13F, shareholding | SC Later free | MISSING | none | Eight rows, all unticked |
| Statement depth, estimates, real-time, point-in-time | SC Later paid | MISSING | none | Four rows, all unticked |
