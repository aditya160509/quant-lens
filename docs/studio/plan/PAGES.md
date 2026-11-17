# Studio v3: page spec

Date: 2026-11-15. Replaces the page plan in FRONTEND.md §1-2 and the page list in FEATURES_AND_OUTPUTS.md §0. Engine, principles, metric set and customisation layers in PLAN.md and FEATURES_AND_OUTPUTS.md §4, §10 stay. Reasons for every change: [REVIEW.md](REVIEW.md).

Style rule (Outputs v2): one lead figure or one-line finding per card; no taglines; no helper text a good layout would not need. Everything cut from a card stays in its Table view or Export.

Reuse paths are from [REUSE.md](../research/REUSE.md) (checked 2026-11-15). "Shared" = already in `modules/research` or `kit`.

---

## 0. Pages, routes, nav

| Page | Route | Job | Nav group |
|---|---|---|---|
| Home | `/studio` | none | top |
| Build | `/studio/build/:id?` | compile only | top |
| Backtest | `/studio/backtest` | `st01` | Test |
| Optimise | `/studio/optimise` | `st02` | Test |
| Validate | `/studio/validate` | `st03` (validate, composed of tests) | Test |
| Portfolio | `/studio/portfolio` | `st04` | top |
| Live | `/studio/live` | `st05` (daily step, signals) | top |
| Chart | `/studio/chart/:symbol?` | bars only | top |
| Library | `/studio/library/:section?` | none | bottom |

Nav: `Home · Build · Test (Backtest, Optimise, Validate) · Portfolio · Live · Chart · Library`. Dot on a page = fresh unseen run. Old ids st03-st12 retire; the manifest keeps one id per job.

Every run page reads `?strategy=<id>@<version>&run=<job>`. The strategy picker is in the run header on every page.

## 0.1 Shared pieces (used by every page)

| Piece | What it shows | Rule |
|---|---|---|
| Run header | Title, strategy chip (name, version), status, Save, Share, Export, Run | Reuse `FeatureView` |
| Hero | The lead figure of the page | Kinds: `figure`, `versus`, `lines`, `bars`, `fan`, `heatmap`, `tiles`, `gauge`, `grade`. New: `fan`, `heatmap`, `tiles`, `gauge`, `grade` in `modules/research/Hero.tsx` |
| KPI strip | 4-6 numbers, user-pickable | `kit/KpiStrip.tsx` |
| Limits pill | "N limits"; popover: data range, coverage, delisted share and rule, fill model, costs, fundamentals lag, hourly held for K names, data freshness date | One source: `/api/studio-v3/limits` |
| Freshness pill | "Data to 2026-07-06 (132 days old)" amber after 3 days, red after 10 | Blocks Live when red |
| My limits strip | Pass or fail against the user's walk-away conditions with the closest call: "Drawdown 22% of 25% limit: 12% room" | Opens every result before the hero |
| Trial chip | "1,840 raw / 212 effective trials" | Opens ledger (section 3.9) |
| Verdict chip | Grade letter if validated, else "not validated" | Links to Validate |
| Stale marker | Settings changed after the run | `FeatureView` |

Shared inputs on every run page (one `Inspector`, grouped; defaults from the user's saved profile):

| Group | Inputs |
|---|---|
| Strategy | Saved strategy and version, or the open draft |
| Universe | One symbol, list, saved Screener screen (re-run point in time each rebalance), Screener preset, top N by liquidity or cap, uploaded CSV set, saved Library universe; shows count and delisted count |
| Period | Presets 1Y to Max, custom start and end, as-of date. **Development period only** until Validate opens the hold-out (last 20% by default, editable once before the first run, then locked) |
| Timeframe | 1d; 1h only where held (K names shown); weekly and monthly resampled |
| Fill | Next open (default); same close (labelled optimistic); bar magnifier where hourly exists, else worst-case same-bar rule |
| Costs | Library cost profile (US retail, India retail with dated STT and charges, crypto maker and taker, custom); commission bps or per share with minimum; slippage bps or % of range; borrow bps a year; dividends on shorts; volume cap |
| Delisting | Delisting return: last close (default, labelled) / haircut % / custom per exchange |
| Sizing | Fixed shares, fixed $, % equity, **risk per trade (% equity to the stop)**, vol target (ATR, stdev), Kelly (capped), equal, score, risk parity |
| Portfolio | Max positions, max weight, rebalance (daily, weekly day, monthly, on signal), long, long-short, short, cash yield |
| Benchmark | SPY default, any symbol, 60/40, buy-and-hold of universe, own CSV |
| Capital | Starting capital, currency, leverage cap, margin rate |

---

## 1. Home

| Item | Spec |
|---|---|
| Purpose | Find a strategy, see what needs attention, start a new one. |
| Who, when | Everyone, on arrival. Daily users glance at "needs attention" then go to Live. |

**Inputs**

| Group | Inputs |
|---|---|
| Find | Search (name, tag, hypothesis text), filters (grade, paper status, folder, tag), sort (last run, grade, name) |
| Create | New blank, from template, from a Screener screen, duplicate, import (Studio JSON, trade CSV, Composer or QuantMage JSON via mapper) |

**Outputs**

| Output | Lead | View | Beats |
|---|---|---|---|
| Needs attention | "2 strategies: data stale, 1 drift alert" | List with one action each | TradingView alert emails scattered across inboxes |
| Strategy cards | Mini equity, grade, trial count, paper status, last run date | Card grid, folders | Composer and Tactfolio lists (name and return only) |
| Recent runs | Run, strategy, settings changed since previous | Table | |
| Templates | 20 starters with a one-line rule | Card grid | |
| Data freshness | "Daily data to 2026-07-06" | Pill | Nobody shows it |

**Interactions**: click card to open the last run; `N` new; `/` search; drag to folder; multi-select then Compare or Archive; press `D` duplicate. Compare up to 8 strategies opens Portfolio.

**Customisation**: card fields, sort, density, folder colours, which templates show.

**States**

| State | Shows |
|---|---|
| Empty | Three actions: blank, template, from a Screener screen |
| Loading | Card skeletons, 150 ms delay before showing |
| Error | Strategy list failed: retry; cached list kept |
| Skipped | Card without a run shows "not run" and a Run button |

**Reuses**: `screener/saved/SavedPage.tsx` (cards, mini result, folders, schedule pill), `kit/Compare.tsx`.

**Acceptance**

- H-1 With 50 saved strategies the page paints cards in under 400 ms (Playwright).
- H-2 "Needs attention" lists a strategy whose Paper last step is older than 3 trading days.
- H-3 Duplicate creates a new strategy with version 1 and an empty trial ledger; the source ledger is not copied.
- H-4 Importing a Studio JSON spec recompiles it and shows compile findings before saving.
- H-5 Screenshot at 1440 and 1024, dark and light.

---

## 2. Build

| Item | Spec |
|---|---|
| Purpose | Write the strategy once, in blocks, formula, Python or plain English, and see signals on price as you type. |
| Who, when | Anyone creating or editing; most time spent here before the first Backtest. |

**Inputs**

| Group | Inputs |
|---|---|
| Entry | Long and short conditions: indicator, price, fundamental, calendar, cross-sectional, higher-timeframe (aligned to the last closed higher bar; lookahead-safe by construction), earnings-date filter where dates are held |
| Exit | Stop % or ATR, trailing, take profit, **time stop (N bars)**, indicator exit, **breakeven move**, **scale out in parts**, **scale in** (pyramiding rules) |
| Allocate | Rotate among a basket, weight by score, **if/else on a condition (regime, trend)**, hold bonds or cash when off. Same object as the rest |
| Sizing | As shared inputs, including risk per trade |
| Parameters | Any number lifted to a named parameter with range and step; step count shown against the sweep size |
| Rules in words | Plain English box; result shown as blocks and formula; nothing runs until accepted |
| Code | Python `class Strategy` with `init`, `on_bar(ctx)`, `on_fill`, sandboxed |
| My limits | Walk-away conditions: max drawdown, max drawdown duration, min trades, min years, beta ceiling, max cost share, min pass share across start dates |
| Stated regime | Optional "works when..." claim, saved with the version; marked "written after" if added after a drawdown |
| Notes | Hypothesis, what was tried, decisions; saved with versions; exported with the certificate |
| Preview symbol and window | First universe symbol, last 2 years by default |

**Outputs**

| Output | Lead | View | Beats |
|---|---|---|---|
| Editor (four modes) | One spec | Blocks rows / Formula bar / Monaco / Plain English | NinjaTrader AI: script is the only check [S4]; ours shows blocks and a paragraph |
| What it does | A deterministic 3-line description of the spec, no LLM | Text under the editor | |
| Signals preview | "14 trades, +31%, last 2 years" | Mini chart, throttled 300 ms | TradingView inputs need a full run |
| Checks | "No look-ahead (50 cuts)"; lint; too few trades; missing exit; signals never fire | Rows with fix links | Pine ports reintroduce look-ahead silently |
| Trial ledger | "1,840 raw / 212 effective; humans 40, AI helper 12, agents 1,788" | Chip, drawer with list | Nobody found counts by actor |
| Versions | v7, diff against v5 (rules or code side by side, results side by side) | Drawer | `@pierre/diffs` |
| Compile findings | Errors mapped to Monaco markers and token underlines | Inline | |

**Interactions**: `⌘↵` run backtest; `⌘S` save version; autosave every 2 s to a draft (survives reload); undo and redo history of edits; Tab through block slots, Enter adds a row; drag rows; switch Blocks ⇄ Formula both ways, Formula → Python one way (original kept); `⌘K` palette: "new strategy from template", "lift number to parameter"; snippets in Monaco; paste Pine as a stretch import (only after the licence check).

**Customisation**: saved rule groups as reusable blocks; custom indicators by formula (shared with Chart and Screener); personal templates; parameter ranges per strategy; default sizing and costs per user; editor font and keymap.

**States**

| State | Shows |
|---|---|
| Empty | Template picker and Plain English box |
| Loading | Editor shows immediately; checks show "checking" rows |
| Error | Compile error inline at the token; Run stays disabled with the reason |
| Skipped | Repaint check "skipped: fewer than 60 bars of data" with reason; never blank |

**Reuses**: `screener/formula/*` (formula bar), `@monaco-editor/react`, `screener_v2/core/formula.py` and `nl_formula.py`, `research_v2/core/signal_lang.py` lifted to `services/shared/formula/`, `charts/PriceChart.tsx` for the preview until Chart lands, `kit/` DataTable not needed.

**Acceptance**

- B-1 The same rule written as blocks, formula and Python produces identical trades (backend test, three fixtures).
- B-2 A strategy that reads `close[+1]` or a centred window is refused with the line and token named (planted test).
- B-3 A higher-timeframe "weekly SMA" rule evaluated on a Wednesday uses the last closed week; test compares to a hand-built frame.
- B-4 Compile responds in under 100 ms server side for a 20-row strategy.
- B-5 Preview refreshes within 300 ms after typing stops (Playwright in-page timing).
- B-6 Reload restores the unsaved draft exactly.
- B-7 Trial ledger shows raw and effective counts; ten near-identical sweep cells add ten raw and fewer than four effective (test).
- B-8 Time stop, breakeven and scale-out each have a fixture strategy with exact expected trades.
- B-9 "What it does" paragraph for the SMA cross fixture equals a stored string.
- B-10 Screenshot at 1440 and 1024.

---

## 3. Backtest

| Item | Spec |
|---|---|
| Purpose | Show what the strategy would have done, after costs, and how fragile that result is. |
| Who, when | Everyone, right after Build, and again after every change. |

Runs on the development period. The hold-out is not drawn. Default layout: **honest order** (fine print, drawdown, monthly table, distribution, rolling, equity last); the user can switch to equity first.

### 3.1 Hero and strip

| Output | Lead | View | Beats |
|---|---|---|---|
| Hero | "+142% vs SPY +81%, 6.0 years, Sharpe 1.12, worst drawdown −18%, 214 trades" | `lines`: net equity vs benchmark, drawdown shade, split line at the hold-out boundary | |
| Cost ladder | "Net CAGR 9.1% at 1×, 6.4% at 2×, 2.2% at 4× costs" | Three numbers beside the hero | Tactfolio shows three cost checks on its page only |
| My limits strip | "Passes 5 of 6; drawdown 22% of 25%: 12% room; passes from 9 of 12 start dates" | Checklist above the hero | LuxAlgo shows closest call for prop rules only |
| KPI strip | Sharpe, CAGR, max DD, trades, win rate, profit factor (user picks) | `KpiStrip` | |

### 3.2 Tabs and cards

| Tab | Card | Lead | View | Notes |
|---|---|---|---|---|
| Overview | Equity and drawdown | Net vs gross vs benchmark | Line + underwater; log toggle; gross and net overlay | |
| Overview | Start dates | "Positive from 41 of 50 start dates; CAGR 3% to 14%" | Dot strip: CAGR by start date, My limits pass marked | Missing from the old plan; LuxAlgo has the idea on prop cards |
| Overview | Survivorship delta | "Dead companies cost 2.6 points a year (18.1% vs 15.5%)" | Two lines: delisted kept vs survivors only | We hold the dead names; most tools do not |
| Overview | Fill check | "Hourly fills cut return 11% (23 names with hourly data)" | Bar vs magnifier lines | Shown only where hourly exists; else "worst-case same-bar rule applied" |
| Trades | Trade list | Win rate, average win and loss, profit factor | Virtualised DataTable; all trades | Columns: entry, exit, side, size, P&L, %, bars, MAE, MFE, exit reason, costs, regime at entry, signal value; sets as tabs |
| Trades | Carried by | "Best 5 trades made 62% of profit; without them CAGR 3.1%" | Bars of P&L share; toggle "hide top 5" recomputes KPIs | |
| Trades | Trade shape | "Losers reached +1R in 31% of cases" | MAE/MFE scatter + P&L histogram + hold-time box plots in one card (three views) | Merges five old cards |
| Trades | Unfilled orders | "Unfilled limit entries returned +1.9% on average" | Two bars: filled, unfilled | Only when limit orders are used |
| Returns | Calendar | "Without the best 3 months: CAGR 4.2%" | Monthly heatmap + yearly bars vs benchmark; hide-best-months toggle | |
| Returns | Crisis strip | "−9% vs SPY −21% in 2022" | One strip with only the periods inside the data; table for the rest | |
| Risk | Drawdowns | "Longest drawdown 19 months (limit 12)" | Underwater + top 5 table (depth, length, recovery) | |
| Risk | Stability | "Sharpe 1.4 first third, 0.3 last third: decaying" | Rolling 6M and 12M Sharpe, vol, beta, correlation; thirds marked | Merges rolling and benchmark cards |
| Risk | Costs | "Costs ate 23% of gross return" | Gross vs net bars, turnover | |
| Risk | Capacity | "About $4M before impact; Sharpe halves at $18M" | One number, curve in Table view | Merges capacity and impact curve |
| Risk | Exposure | Time in market, gross and net | Area | Table view of Trade shape if no leverage |
| When | By regime | "84% of P&L in trend up, low vol" | Bars of return and Sharpe per regime; trades per regime beside each bar ("9 trades: too few") | Regimes: trend (200d), volatility terciles, drawdown state, HMM, custom |
| When | Conditions | "When VIX > 25, Sharpe −0.4" | Table of conditions | Library regimes |
| When | Seasonality | Month-of-year hit rate | Bars | |
| When | Timeline | Regime bands over price with equity under | Chart | |
| Names | Per-name results | "12 of 500 names made 55% of profit" | Virtualised table: trades, P&L, win rate, share, best and worst; click opens Chart | TrendSpider group table; Build Alpha top and worst tickers |
| Names | Holdings | Top contributors | Treemap; weights over time | |
| Paths | Trade Monte Carlo | "95% of reshuffled paths stay above −27% drawdown" | `fan`: median, 25-75, 5-95; Resample, Shuffle, block bootstrap, trade skip; 250/1,000/2,500 runs; caveat "bands are not limits" | LuxAlgo has two methods |
| Paths | Ruin | "P(drawdown > 30%) = 4%" | Table of thresholds | |
| Paths | Rule check | Pass share for user rules (target, daily loss, max drawdown, min days) across start dates | Ring + table | Replaces the prop page |
| Paths | Streaks | 95th percentile losing streak | Bars | |

Replay is a hero action (`R`): equity draws, trades appear on price, holdings fly in and out; still frame under Reduce motion.

**Interactions**: click a trade opens Chart at entry−20 to exit+20 with stops; tick trades and press `C` for aligned price paths; click a name row opens Chart; `[` `]` change tab; `T` Trades; `R` Replay; toggle gross and net; compare to previous run (`RunCompare`).

**Customisation**: hero kind, KPIs, tab order, card show, hide, duplicate, resize, view switch; range, log, one colour, mark a level; report order (honest, equity first, custom); custom metric by formula; custom crisis periods; custom regimes (Library).

**States**

| State | Shows |
|---|---|
| Empty | "Pick a strategy" and the last three strategies |
| Loading | Stage list with counts ("Loading 500 names 312 / 500"), cancel |
| Error | Job failed with the stage and reason; settings preserved |
| Skipped | A run with 0 entries is refused: "0 entries: rule never true on this universe", with the three most likely causes; fewer than 30 trades marks every statistic "few trades" |
| Stale | "Settings changed since this run" and a Run button |
| Data stale | Freshness pill amber or red; backtest still runs on the history it has and says so |

**Reuses**: `screener/test/TearSheet.tsx` (monthly heatmap, return histogram, underwater, drawdown story), `charts/Backtest.tsx`, `screener/Story.tsx` (replay, sorting field), `kit/DataTable.tsx`, `kit/KpiStrip.tsx`, `modules/research/outputs/*`, `RunCompare.tsx`, `services/screener_v2/core/backtest.py` (cross-check), `core/metrics.py` (one canonical, merged first).

**Acceptance**

- K-1 Hero numbers equal `metrics.py` outputs within 1e-9 on the SMA-cross fixture.
- K-2 Same run twice: identical trades and equity (hash equal).
- K-3 Fills at next open by default; a test with a gap through a stop fills at the open, not the stop.
- K-4 With zero costs every output shows a "costs off" pill.
- K-5 Start-date card reproduces a hand-computed result for 3 start dates.
- K-6 Survivorship delta changes the equity line on a fixture with one delisted name and shows the same delisting rule in the limits popover.
- K-7 Zero-entry run returns a refusal with a reason, not an empty report (API test and screenshot).
- K-8 Trade list with 10,000 rows scrolls with median frame ≤ 16.7 ms (`tablebench.mjs` pattern).
- K-9 500 names, 10 years: under 5 s cold (measured, not promised until the phase 0 spike).
- K-10 Hold-out dates do not appear in any Backtest series (test inspects the payload).
- K-11 Screenshot at 1440 and 1024, dark and light, each tab.

---

## 4. Optimise

| Item | Spec |
|---|---|
| Purpose | Find a stable range of settings, not the single best cell. |
| Who, when | After Backtest, when parameters matter. |

**Inputs**

| Group | Inputs |
|---|---|
| Search | Grid, random, Bayesian (Optuna TPE); budget (cells, seconds); seed |
| Parameters | Any lifted parameter, range, step, log scale, link two parameters (e.g. fast < slow) |
| Objective | Sharpe, CAGR / drawdown, profit factor, Ulcer, custom formula; multi-objective weights |
| Constraints | Min trades, max drawdown, min pass share across start dates |
| Neighbourhood | Radius for the stability score (default 1 step) |

**Outputs**

| Output | Lead | View | Beats |
|---|---|---|---|
| Hero | "Plateau at fast 40-60, slow 180-220: Sharpe 0.9-1.1" | `heatmap` of two chosen parameters, plateau outlined, others fixed at plateau centre | Single best cell views (backtesting.py heatmap) |
| Stability | "71% of neighbours within 20% of best" | `gauge` + neighbourhood histogram | |
| Surface | Shape | Contour (default), 3D rotate (lazy-loaded, off by default) | |
| Top sets | Best 20 by objective | Table: params, Sharpe, CAGR, DD, trades, stability; click backtests that set | |
| Trade-off | Pareto front | Scatter return vs drawdown, front highlighted | |
| Importance | "slow matters 3× more than fast" | Bars (fANOVA) | |
| Spread | Outcomes across the plateau | Overlaid equity lines, best bold | |
| Trial cost | "This sweep added 400 raw, 38 effective trials" | Line under the hero | Nobody found shows this |

**Interactions**: click a heatmap cell to backtest it; drag-select a region to set the plateau; pick any two parameters on the axes; `C` compare two sets; "Send plateau centre to Build" creates a new version (adds to the ledger).

**Customisation**: colour scale, objective formula, which parameter pair is default, table columns; saved search profiles.

**States**

| State | Shows |
|---|---|
| Empty | "No parameters yet: lift a number in Build" |
| Loading | Live cell counter ("612 / 1,000"), partial heatmap fills as cells finish (SSE), cancel |
| Error | Per-cell failures counted; run completes with the failures listed |
| Skipped | Cells with fewer trades than the minimum are greyed, counted, and named "too few trades" |

**Reuses**: `charts/Heatmap.tsx`, `charts/XYPlot.tsx`, `modules/research/outputs/plots.tsx` (specification curve), `kit/DataTable.tsx`, `services/screener_v2/core/validation.py` (signal cache pattern), Optuna (MIT).

**Acceptance**

- O-1 A planted spike strategy (one lucky cell) reports "spike only", not a plateau; a planted plateau strategy reports a plateau (backend tests).
- O-2 1,000-cell sweep on a single symbol under 10 s (vector engine).
- O-3 The sweep adds trials to the ledger equal to cells run; effective count is smaller when cells are neighbours.
- O-4 Cancel stops compute within 2 s and keeps finished cells.
- O-5 Screenshot of Map, Surface (still), Top sets.

---

## 5. Validate

| Item | Spec |
|---|---|
| Purpose | Decide whether the edge is real, with one graded verdict and the tests behind it. |
| Who, when | After Backtest and Optimise, before Paper. Also when an agent finishes a search. |

One page, one run. The run executes all selected tests on the user's compiled strategy, shows tiles flipping as each finishes (SSE), and ends with the verdict. Each test can be re-run alone.

**Inputs**

| Group | Inputs |
|---|---|
| Profile | Validation profile from Library (default, strict, quick); tests on or off; weights; pass thresholds |
| Walk-forward | Anchored or rolling; window and step; purge, embargo; re-optimise on or off |
| Robustness | Paths per test (100 / 500 / 2,000); noise level; shift range; delay bars (1, 2); cost multiples (2×, 3×); volume cap; related symbols; skip share |
| Luck | Trials: the ledger (raw, effective) with an override; CPCV groups and test groups |
| Shocks | Gap down %, volatility multiple and duration, correlation to 1 |
| Seed | Fixed per run, shown |

**Outputs (tabs)**

| Tab | Output | Lead | View | Beats |
|---|---|---|---|---|
| Verdict | Grade | "B: real edge, fragile to costs; break-even at 2.1× costs" | `grade` with reason; score table: test, weight, result, link | QuantProof Edge Score has no reasons shown in the text read |
| Verdict | Next test | "Run: delay 2 bars (not run)" | One line | Canli `fix_next` |
| Verdict | What would change it | "Needs 40 more trades"; "costs break it at 2.1×" | List; no parameter tuning suggestions; any suggestion that edits parameters opens a new version and adds to the ledger | |
| Verdict | Power | "Detects a Sharpe 0.5 edge 80% of the time at 212 trades; flags 4% of shuffled strategies" | Table and one line | No product found shows it |
| Verdict | My limits and start dates | Same strip as Backtest | | |
| Walk-forward | Stitched OOS | "Walk-forward efficiency 68%" | `lines` with window bands labelled by chosen params | |
| Walk-forward | Windows | "11 of 14 windows profitable" | Table: IS, OOS dates, params, Sharpe, return, WFE | |
| Walk-forward | Matrix | "9 of 25 (re-opt × OOS) cells pass" | Heatmap | SQX walk-forward matrix |
| Walk-forward | Drift | "fast moved 20 → 65: unstable" | Line of params per window | |
| Robustness | Tiles | "Passes 7 of 9" | `tiles`: pass, fail, skipped with reason and threshold | |
| Robustness | Vs random | "Beats 96% of 1,000 random strategies with the same trade count, holding time, stop and target" | Histogram, ours marked | Random entries with the same stop and target remove win-rate artefacts |
| Robustness | Price paths | Noise, permutation (MCPT), shifted starts | Fan + width; histogram; bars per shift | Build Alpha set, on the user's strategy |
| Robustness | Execution | Delay 1 and 2 bars, cost 2× and 3× (break-even marked), volume cap | Lines and bars | |
| Robustness | Parameters | Share of nearby settings profitable | Heatmap from Optimise neighbourhood | |
| Robustness | Others | Same rule on related symbols and sector peers | Small multiples | |
| Robustness | Shocks | "Gap down 10%: drawdown −31%" | Table | Merges stress scenarios |
| Luck | Luck lottery | "After 1,840 tries (212 effective), noise alone reaches Sharpe 1.9; yours is 1.4" | Histogram of best-of-N noise Sharpe, ours marked | Nobody found leads with it |
| Luck | Deflated Sharpe | "DSR 0.62 after 212 effective trials" | `gauge` | Stochastly, Canli numbers |
| Luck | PBO | "Probability of overfitting 71%" | Logit histogram; IS-rank vs OOS-rank scatter | |
| Luck | CPCV | OOS Sharpe across paths | Violin + path equities | |
| Luck | Track record | "Needs 3.4 years live at 95%" | One number | |
| Luck | Haircut Sharpe | Before and after | Bars | |
| Hold-out | Sealed hold-out | "Hold-out Sharpe 0.7 vs 1.1 in-sample; looked at 2 times (human 1, agent 1)" | Paired bars + look log | Look log by actor |
| Certificate | Certificate | Grade, hash, "reproduced 2026-11-15 ✓" | Report view; server re-runs backtest and every test from spec, data version, seed and compares hashes | Canli signs a statistic; this re-runs everything |
| Certificate | One-page PDF and share link | Hero, equity, verdict table, limits, rules, hash | PDF + `/share/<token>` | |

**Interactions**: click a tile to jump to its card; "Run again with more paths" on any test; edit weights live and see the grade recompute from stored results (no re-run); open hold-out requires a click and logs a look (humans: unlimited but logged; agents: budget of 3 per strategy, more needs a human click); Certify button greyed until all required tests have run on the current version.

**Customisation**: validation profiles (tests, weights, thresholds, default seed); tile order; report order for PDF; custom tests as formulas over the equity or trades (later).

**States**

| State | Shows |
|---|---|
| Empty | "No run on this version" and Run (all) or Run quick |
| Loading | Tiles flip live with counts ("Noise 312 / 500"), cancel one or all |
| Error | A failed test shows "failed: reason", others continue; verdict says "incomplete" |
| Skipped | Each skipped test: "skipped: only 18 trades" or "no related symbols held"; verdict lists skips and caps the grade at the letter allowed without them |
| Stale | New version or changed settings: verdict marked stale, never shown as current |

**Reuses**: `modules/research/outputs/robustness.tsx` (tile pattern), `research_v2/core/holdout.py`, `placebo.py`, `robustness.py`, `specification.py`, `ml_v2/core/cpcv.py` and `validation.py`, `skfolio` CPCV as test oracle, `screener_v2/core/exports.py` and `shares.py` (PDF and share), `charts/Distribution.tsx`, `charts/Forest.tsx`, `kit/DataTable.tsx`.

**Acceptance**

- V-1 A planted overfit strategy (best of 2,000 random rules) receives D or F with "luck" named as the reason; a known robust strategy (long-run trend on a broad index fixture) receives A, B or C.
- V-2 Verdict is computed on the server from stored test results; posting a modified result from the browser changes nothing (API test).
- V-3 Re-running Certificate on the same version reproduces the hash.
- V-4 Opening the hold-out writes a look with actor, time and the version; the count in the UI equals the log.
- V-5 An agent token cannot open the hold-out a fourth time without a human approval event (API test).
- V-6 Power card: on a fixture with a planted Sharpe 0.5 signal the detection rate printed is within 5 points of a direct simulation.
- V-7 Editing weights recomputes the grade without a job.
- V-8 A strategy with 12 trades gets "skipped" on walk-forward and the grade cap is shown.
- V-9 Tiles flip one by one during a run (screenshot sequence at 3 timestamps).
- V-10 Quick profile finishes in under 10 s on a single-symbol 10-year daily strategy.

---

## 6. Portfolio

| Item | Spec |
|---|---|
| Purpose | Combine several strategies and see whether the mix is better than the best one. |
| Who, when | After two or more strategies pass Validate; also for meta strategies. |

**Inputs**

| Group | Inputs |
|---|---|
| Members | Up to 12 strategies (versions), or "all in this folder" |
| Allocation | Equal, inverse vol, risk parity, max Sharpe, HRP, fixed weights; rebalance; cap per strategy |
| Meta rule | If condition then strategy A else B; rotate to the strongest by trailing N months; weight by regime |
| Period | Shared inputs; overlap only |

**Outputs**

| Output | Lead | View | Beats |
|---|---|---|---|
| Hero | "Three together: Sharpe 1.4 vs best single 1.1, drawdown −12% vs −18%" | `lines`: combined vs each | StrategyQuant Portfolio Master (Pro caps strategies) |
| Correlation | "Lowest pair: 0.12" | Heatmap + dendrogram | |
| Allocation | Weights by method | Stacked bars over time | |
| Marginal | "B adds the most" | Bars | |
| Overlap | Shared trades and names | Matrix | |
| Meta result | "Regime switch beat both parts in 2 of 3 crises" | Equity + switch markers | Composer symphony logic, with validation |
| Combined verdict | Grade of the combination | `grade` chip linking to Validate with the combined strategy as a member list | |

**Interactions**: drag to reorder; tick strategies in Home then "Combine"; `C` compare; export weights as CSV.

**Customisation**: allocation method defaults, correlation window, hero kind.

**States**: Empty "Add two strategies"; Loading stages per member; Error names the failing member and keeps the rest; Skipped "no common period".

**Reuses**: `ml_v2/core/allocation.py`, `portfolio_v2/`, `charts/Heatmap.tsx`, `charts/Dendrogram.tsx`, `kit/Compare.tsx`.

**Acceptance**

- P-1 Equal-weight combination of two fixtures equals a hand-computed series.
- P-2 A meta rule "SPY above 200d: stocks, else bonds" backtests with the switch on the next open; no look-ahead (planted test).
- P-3 Combined strategy can be sent to Validate and returns a verdict.
- P-4 Screenshot at 1440 and 1024.

---

## 7. Live

| Item | Spec |
|---|---|
| Purpose | Say what to do today, keep a frozen strategy on paper, and tell when it stops working. |
| Who, when | Daily users, mornings and after the close. **Phone-first layout** (this page is the one people open on a phone). |

**Inputs**

| Group | Inputs |
|---|---|
| Source | A strategy version (draft allowed for Today; Forward needs a frozen version from Validate with grade ≥ the user's gate) |
| Freeze | Start date, capital, limits (position, exposure, daily loss), kill switch |
| Alerts | Channel (email, push, Telegram, webhook JSON), events (entry, exit, near trigger, drift, data stale), quiet hours, quota shown |
| Import | CSV of real trades or a broker export column map |
| Schedule | Runs after the daily data load |

**Outputs (tabs)**

| Tab | Output | Lead | View | Beats |
|---|---|---|---|---|
| Today | Signals | "7 entries, 3 exits as of 2026-07-06" | Table: symbol, action, value, distance to trigger, size; tick to Compare or add to Paper | |
| Today | Near triggers | Names within x% of firing | Table | |
| Today | Map | Universe as dots, firing ones lit | Sorting field | |
| Today | Orders sheet | "Buy 41 AAPL at next open; stop 8%" | Copyable text and CSV | |
| Forward | Forward equity | "+4.1% since freeze vs expectation +3.2% ± 5.0%" | `lines` with the backtest Monte Carlo band | |
| Forward | Drift | "Live Sharpe left the 95% band on 2026-10-02" | Marker + alert | |
| Forward | Decay clock | "At 3 months a dead edge is caught 18% of the time; 80% power at 2.6 years" | Table and one line | halleytech idea in FEATURES st10 |
| Ledger | Fills | Daily fills, same fill model and costs | Table | Tradetron "Live Offline" |
| Health | Cost leak | "Paper costs 3 bp above backtest" | Daily line | |
| Health | Signal health | Rank IC vs backtest mean | Line (ranking strategies) | |
| Health | Drawdown odds | "A drawdown this deep: 1 in 14 at the backtest Sharpe, 1 in 3 at half" | Two numbers | |
| Health | Shadow book | Stopped strategy keeps running for 12 months | Equity | |
| Reconcile | Backtest vs paper vs real | "Same trades 91%; average fill 4 bp worse; residue small, grows with volatility" | Four-question table + trade diff list | Tradetron describes it as a manual how-to |
| Reconcile | Real trades on chart | "You skipped 6 signals and took 4 it never gave" | Chart overlay | TradeZella, Tradervue import trades, but do not compare to a strategy |
| Alerts | Rules and feed | Last 30 alerts, hit rate | List | `screener/monitor/*` |
| Digest | Daily email or push | One message: signals, positions, equity, drift | Message preview | Tactfolio daily email |

**Interactions**: `F` freeze; kill switch is one confirm; swipe between tabs on phone; tap a signal for QuickLook; test alert sends a sample; a new version cannot inherit a Paper record (starts a new segment).

**Customisation**: digest contents and time, alert channels per strategy, which Health cards show, units.

**States**

| State | Shows |
|---|---|
| Empty | "Freeze a validated strategy to start paper" and Today available for any draft |
| Loading | Step progress after the daily load |
| Error | Step failed: last good state kept, reason, retry |
| Skipped | Data stale (red): Today and Forward say "not updated: data to 2026-07-06" and do not compute; no zero-return days written |

**Reuses**: `screener_v2/core/scheduler.py`, `alerts.py`, `notify.py`, `snapshots.py`, `screener/monitor/*`, `screener/Story.tsx` (sorting field), `kit/QuickLook.tsx`, `kit/DataTable.tsx`, old Studio paper gates (idea only).

**Acceptance**

- L-1 With data stale beyond 10 days the daily step refuses and writes nothing (test).
- L-2 After a simulated new bar, the step produces fills at next open with the same costs as the backtest (test against vector engine).
- L-3 Freezing a version stores spec, data version and seed; the Forward curve before the freeze date is never drawn.
- L-4 A drift alert fires when live equity leaves the 95% band in a planted series and appears in the feed and in the digest.
- L-5 Reconcile on an imported CSV matches hand-built counts on a 10-trade fixture.
- L-6 A strategy with a newer version starts a new segment; the old record stays under the old version.
- L-7 Alert quota and channel verification states visible; a failed webhook shows status and retry.
- L-8 Screenshot at 390 px (phone, Today and Forward) and 1440.

---

## 8. Chart

| Item | Spec |
|---|---|
| Purpose | Show price, indicators and the strategy's trades on one data source. |
| Who, when | After Backtest (click a trade), and for chart reading. |

**Inputs**: symbol (or list for a grid), timeframe (1d, 1h where held, weekly, monthly), indicators (search, favourites, presets), drawings, strategy overlay (up to 2), compare symbols (rebased %), layout (1-4 panes with synced crosshair), alerts.

**Outputs**

| Output | Lead | View | Beats |
|---|---|---|---|
| Price + volume + indicator panes | The strategy's trades on price | lightweight-charts 5 panes | Pine tables and overlays limited by plan |
| Strategy overlay | Entry and exit arrows, stop and target lines, position shading, signal pane | Overlay toggle per strategy | |
| Trade navigator | "Trade 41 of 214: +6.2%, MAE −2.1%, exit: target" | Floating card; ← → steps | |
| Replay | Bar-by-bar with equity and position under | Play, pause, 1× to 20×, scrub | Automated trades only; hand-trading is out of v3 |
| Compare | Rebased lines | % scale overlay | |
| Alerts | Created on the chart, evaluated on the server | Marker + feed link | |

**Interactions**: `R` replay; ← → trades; `G` from Backtest jumps here; drawing toolbar with the 12 most used and the rest in a menu; drawings saved per symbol on the server; `⌘K` "add indicator".

**Customisation**: indicator presets, drawing templates, colours per series, layouts, key per tool.

**States**: Empty "Pick a symbol"; Loading skeleton pane, first paint under 400 ms; Error "bars unavailable for X" with the data range held; Skipped "hourly held for 23 names" when 1h is chosen elsewhere.

**Reuses**: `chart_engine/IndicatorEngine/registry.ts` maths (71 indicators), `DrawingEngine/*` geometry, `/api/studio-v3/bars`. Patterns are not ported until a page names a use.

**Acceptance**

- C-1 Every chart indicator matches the backend formula within 1e-6 on a fixture (shared test).
- C-2 Chart, Backtest and Live read the same bars: same close for the same symbol and date (test).
- C-3 10 years daily + 3 indicators first paint under 400 ms.
- C-4 Clicking a trade in Backtest opens Chart zoomed to that trade with its stop and target.
- C-5 Replay at 20× stays at 60 fps on 5,000 bars (Playwright frame sample).

---

## 9. Library

| Item | Spec |
|---|---|
| Purpose | One place for the things every other page reuses and the user customises. |
| Who, when | Occasionally; first use when setting defaults. |

| Section | Holds | Lead | Notes |
|---|---|---|---|
| Universes | Saved universes (Screener screens, lists, uploads), counts, delisted count | "Nifty 500 point in time: 12 delisted" if coverage exists | Phase 0 decides India |
| Costs | Profiles (US retail, India retail with **dated** STT and charges, crypto, custom) with effective-from dates | "STT schedule from 2026-04-01" only after verification | India rates change; every profile is dated |
| Benchmarks | Symbols, blends (60/40), own CSV | | |
| Blocks and indicators | Reusable rule groups, formula indicators | | Shared with Chart and Screener |
| Regimes and crises | Custom regimes by formula; extra crisis periods | | |
| Metrics | Custom metric formulas usable as KPI, column, objective, limit | | |
| Profiles | Validation profiles, report orders, default sizing, workspace layout | | Replaces "workspace presets" |
| Data | Data audit: symbols per year, bars per symbol, rows / 252 check, fundamentals filing lag, adjusted status, delisted share and rule, hourly coverage (K names), freshness and last update job result | "Daily data to 2026-07-06; 4,158 tickers; hourly 23" (measured 2026-11-15) | The audit is also in the limits popover |
| Imports | Uploaded CSV bars and trades, Composer and QuantMage JSON mapper | Mapping shows what could not be translated | |
| Agents | Tokens, scopes, actor log, look budget | | Section 11 |

**Interactions**: every item can be saved as default, reset, exported as JSON, shared by link (settings only, never private prefs); sync server-side (`prefsSync`).

**States**: Empty sections show one action; Loading list skeleton; Error "could not save, kept locally"; Skipped section "India costs: coverage not measured".

**Reuses**: `kit/DataTable.tsx`, `prefsSync`, Screener saved-universe and preset code.

**Acceptance**

- Y-1 A custom metric formula `cagr / ulcer` works as a KPI, a table column, an Optimise objective and a My limit (four tests).
- Y-2 Data audit counts equal a direct parquet query on the fixture.
- Y-3 Exported profile imports on another account and reproduces the same Backtest.
- Y-4 Screenshot at 1440 and 1024.

---

## 10. Cross-page behaviour

### 10.1 Navigation and palette

| Item | Spec |
|---|---|
| Left nav | Section 0; dot on fresh runs; collapses to icons |
| Strategy picker | In every run header; switching keeps the page |
| Palette `⌘K` | Pages, strategies, templates, "run validate on this strategy", "compare with previous run", "copy link with settings", "export one-page PDF", "freeze to paper", "open Library > Costs"; rebindable keys; pin favourites |
| Keys | `⌘↵` run, `⌘S` save, `[` `]` tabs, `C` compare, `R` replay, `T` trades, `G` chart, `F` freeze, `/` search, Esc closes drawers |
| Breadcrumb | None; the run header carries strategy and version |

### 10.2 Compare

Any two runs, versions or strategies; up to 8 strategies (Portfolio); two Validate runs side by side; Backtest vs Paper vs Real in Live > Reconcile. Output: settings changed, numbers with winner per row, curves overlaid. Reuse `RunCompare.tsx`, `kit/Compare.tsx`.

### 10.3 Share and export

| Item | Spec |
|---|---|
| Share link | Strategy, settings, layout, results; read-only; expiry and revoke; never private prefs |
| Embed | Hero and verdict chip |
| Export | CSV of every table, trades CSV, equity CSV, PNG and SVG of any chart, one-page PDF, full report PDF, spec as JSON and as Python |
| Reproduce | A shared run shows its hash and a "Reproduce" button that re-runs on the server |

### 10.4 Alerts and digest

One alert engine for Chart, Live and Library. Channels: email, push, Telegram, webhook JSON. Each alert shows quota used. A webhook failure shows status code and retry time. Quiet hours per strategy.

### 10.5 Agent API (AX)

| Item | Spec |
|---|---|
| Surface | REST plus an MCP server over the same jobs: `list_templates`, `compile`, `backtest`, `optimise`, `validate`, `get_verdict`, `get_ledger`, `get_signals`, `get_data_audit`, `open_holdout`, `freeze_paper` |
| Output | Typed spec, plain-text verdict, limits and trial ledger in every response |
| Guard rails | Every call is logged by actor; the effective trial count applies to agents the same as to humans; hold-out looks budgeted (3 per strategy) and logged; `freeze_paper` and `certify` need a human click; no endpoint sorts strategies by backtest return |
| Why | QuantConnect, StrategyQuant, Build Alpha, Tactfolio and Canli ship MCP already; agents overclaim and inflate search (REVIEW §2) |

### 10.6 Customisation

As FEATURES_AND_OUTPUTS §10, with two changes: presets live in Library > Profiles; every customisation is in the typed spec so agents read and set it. Reset-to-default on every control; a "Customised" marker (shared) on changed inputs.

### 10.7 Budgets (tested)

| Action | Budget |
|---|---|
| Compile | < 100 ms server |
| Preview refresh | < 300 ms after typing stops |
| Backtest 1 symbol, 10 years | < 1 s |
| Backtest 500 names, 10 years | < 5 s cold (confirm in phase 0) |
| 1,000-cell sweep, 1 symbol | < 10 s |
| Trade list 10,000 rows | median frame ≤ 16.7 ms |
| Chart first paint, 10 years + 3 indicators | < 400 ms |
| Tab, menu, palette | < 70 ms click to paint |
| Validate quick profile, 1 symbol | < 10 s |

### 10.8 Phases (replaces PLAN §7 ordering)

| Phase | Ships |
|---|---|
| 0 | Data audit, daily update job, hourly coverage (23 names measured), delisted share, India coverage; engine spike; merge `metrics.py` |
| 1 | Spec, compile, engine, Backtest (Overview, Trades, Returns, Risk), Home, agent API with ledger |
| 2 | Build (four modes, sizing by risk, new exits, higher-timeframe rules, allocate blocks, autosave), Names, When, Paths tabs |
| 3 | Optimise; Validate (verdict, walk-forward, robustness, luck, hold-out, certificate); alerts and digest |
| 4 | Chart (trades on price, replay) |
| 5 | Portfolio; Live (Today, Forward, Reconcile) |
| 6 | Library completion, imports, India profile if coverage allows |
| 7 | Remove old Studio (graph + `rg` + route checks + smoke test per AGENTS.md) |
| 8 | Phone layout for the rest (Live is phone-first from phase 5) |

### 10.9 Cross-page acceptance

- X-1 Every page has a Playwright screenshot at 1440 and 1024, dark and light; Live also at 390.
- X-2 Every page has an empty, loading, error and skipped state test.
- X-3 The same strategy through UI and through the agent API gives the same hash.
- X-4 A shared link opens read-only, shows the hash, and Reproduce matches.
- X-5 Changing a Library cost profile marks dependent runs stale.
- X-6 No page sends a computed result to the server for certification (API test).
- X-7 Old route `/trade` redirects to Chart; old Studio routes redirect to the nearest new page.
- X-8 `rg` finds no import of removed Studio modules after phase 7 (AGENTS.md rule).
