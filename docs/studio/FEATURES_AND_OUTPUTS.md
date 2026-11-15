# Studio v3: every feature and every output

Date: 2026-11-15. Rule (from Outputs v2): **an output exists only if it has a lead figure or a one-line finding, and nobody else on the page says the same thing.** Everything cut stays reachable as a card's Table view or in Export.

Sources for what each competitor sells: [COMPETITORS.md](COMPETITORS.md). Marks: **(TV)** TradingView, **(SQ)** StrategyQuant X, **(BA)** Build Alpha, **(QC)** QuantConnect, **(P123)** Portfolio123, **(C)** Composer, **(AB)** AmiBroker, **(WL)** WealthLab. **Ours** = nobody sells it this way.

### Why each feature exists (from [COMPETITORS.md](COMPETITORS.md), third pass)

| What users said or what competitors lack | Feature here |
|---|---|
| "Show the trade list… whether a single trade carried the result" (r/FxBacktest) | st01 trade list first-class + **Carried by** output |
| TradingView assumes a favourable path when stop and target share a bar; bar magnifier is a paid toggle | Conservative same-bar rule by default + **Fill check** (bar vs hourly result delta) |
| Repainting and look-ahead run without warning in Pine; 40–45% of Pine-to-Python ports reintroduce look-ahead (codertrader) | Engine gives data to bar *t* only + **Repaint check** in Build lint |
| Composer backtests at the close, trades at 3:50 PM; timing is a paid upgrade | Fill timing printed on every result; Paper uses the identical spec and timing |
| One symbol per script, no portfolio (TradingView) | Portfolio mode with shared capital, limits and portfolio drawdown |
| No walk-forward, purged split or OOS report (TradingView) | st03, st06 |
| Generated and AI-ranked strategies fail live (StrategyQuant, Composer "Trade with AI") | **Trial counter** on every strategy; DSR uses it; AI never sorts by backtest |
| Build Alpha's 12–16 tests are a Windows licence | st04 on the user's own strategy, in the browser |
| QuantConnect's report: PSR, capacity, crisis events, rolling beta and Sharpe, exposure | st01 adds **Crisis events** and **Capacity**; PSR in metrics |
| Portfolio123 users asked for borrow cost, long-short in one sim, portfolio of portfolios, limit orders | Borrow cost and dividends in costs; long-short in one run; st08 Combine; limit orders in the event engine |
| TrendSpider sells variance tests, multi-symbol tests, seasonality | st04 variance test, Universe of many symbols, st07 seasonality |
| Point-in-time universe with delisted names (r/FxBacktest) | Universe input says how many delisted names it holds |
| "Same config runs live without editing" | One spec from Build to Paper; no second code path |

Pages map onto the lab shell exactly like Screener: each page is a feature with inputs (Inspector), a hero, a KPI strip, sections of cards, a run header, Compare runs, Export, Share.

---

## 0. Pages

| id | Page | Group in nav | Runs a job |
|---|---|---|---|
| — | Home | Overview | no |
| — | Build | Build | compile only |
| st01 | Backtest | Test | yes |
| st02 | Optimise | Test | yes |
| st03 | Walk-forward | Validate | yes |
| st04 | Robustness | Validate | yes |
| st05 | Monte Carlo | Validate | yes |
| st06 | Overfitting | Validate | yes |
| — | Verdict | Validate | reads st03–st06 |
| st07 | Regimes | Understand | yes |
| st08 | Combine | Understand | yes |
| st09 | Signals today | Live | yes |
| st10 | Paper | Live | yes (daily) |
| st11 | Certify | Live | yes |
| st12 | Chart | Chart | bars only |

## 1. Shared strategy inputs (every run page reads the same spec)

| Group | Inputs |
|---|---|
| Strategy | Saved strategy and version (or the draft open in Build) |
| Universe | Point in time, delisted names kept (count shown); one symbol, a list, a saved Screener screen (re-run point in time each rebalance), a Screener universe preset, an index proxy (top N by liquidity or cap) |
| Period | Presets 1Y…Max, custom start/end, as-of date; in-sample / out-of-sample split line (held out by default: last 20%) |
| Timeframe | 1d, 1h (where held), weekly and monthly resampled |
| Fill | Next open (default), same close (labelled optimistic), bar magnifier from hourly |
| Costs | Commission bps or $/share with minimum, slippage bps or % of range, short borrow bps/yr, dividends on shorts, max % of bar volume |
| Sizing | Fixed shares, fixed $, % of equity, volatility target (ATR or stdev), Kelly fraction (capped), equal weight, score weight, risk parity |
| Portfolio | Max positions, max weight, rebalance (daily, weekly day, monthly, on signal), long only / long-short / short only, cash yield |
| Benchmark | SPY default, any symbol, or 60/40, or buy-and-hold of the universe |
| Capital | Starting capital, currency, leverage cap, margin rate |

## 2. Build (no job; compile on every keystroke)

Three editors, one spec, switchable without losing work (blocks → formula and formula → blocks where the rule fits blocks; Python is one-way).

| Part | What it does | From |
|---|---|---|
| Blocks | Rows of "When [condition] then [action]"; conditions from indicator, price, fundamental, calendar and cross-sectional blocks; and/or groups; nested rules; no graph spaghetti | (C) symphonies, (WL) building blocks, (SQ) builder; **ours**: same object as code |
| Formula | One-line rules in the safe language (`sma(close,50) > sma(close,200) and rsi(close,14) < 30`), with autocomplete, inline docs and errors under the token | research_v2 `signal_lang`; Screener formula bar |
| Python | `class Strategy` with `init`, `on_bar(ctx)`, `on_fill`; Monaco editor with types for `ctx`; runs in the sandbox | (QC), (TV) Pine as model |
| Plain English | "Buy when the 50-day crosses above the 200-day, sell on a 10% trailing stop" → formula, shown and editable before it runs | Screener `/nl-filter`; (TV) AI, Capitalise.ai |
| Templates | 20 starters: trend (SMA cross, Donchian breakout, Supertrend), mean reversion (RSI(2), Bollinger fade, IBS), momentum rotation (12-1, dual momentum), factor (value/quality/low vol from Screener ranks), pairs (z-score spread), calendar (turn of month), volatility target, risk parity | (TV) public scripts, (C) templates, Quantpedia |
| Parameters | Any number in a rule can be lifted to a named parameter with a range (used by Optimise and robustness) | (TV) inputs, (SQ) |
| Repaint check | Signals recomputed on data cut at 50 random bars; any signal that changes after the fact is listed with its bar. Runs before every backtest | **ours** (users run this by hand in TradingView bar replay) |
| My limits | Before the first run the user writes walk-away conditions (max drawdown, max drawdown duration, min trades, min years, beta ceiling, max cost share). Every result opens with pass/fail against them, before the equity curve | **ours**; the practice tear-sheet readers recommend (datapigtechnologies 2026-08) |
| Stated regime | Optional "works when…" claim (e.g. trend up, dispersion high). Saved with the version, tested in st07 and watched in Paper; a claim written after a drawdown is marked as written after | **ours**; pre-registration (halleytech 2026-09) |
| Trial counter | Every backtest, sweep cell and AI suggestion on this strategy is counted; shown on Build and fed to DSR (st06) | **ours** |
| Lint | Look-ahead (future index, centred windows), unused parameter, signals that never fire on the chosen universe, too few trades expected, missing exit | **ours**, live |
| Versions | Every save is immutable; diff any two versions (rules and code side by side); results stay tied to the version | Screener saved screens; `@pierre/diffs` |
| Preview | Last 2 years on the first symbol, signals on a mini chart, updates as you type (< 300 ms) | **ours** |

## 3. Outputs by page

Format per output: **Lead figure / finding** · view · notes. ★ = cinematic (has a still fallback, respects Reduce motion). $ = paid-tier feature elsewhere.

### st01 Backtest
Hero: **"+142% vs SPY +81%"** over equity and benchmark lines, drawdown shaded under; line "6.0 years · Sharpe 1.12 · worst drawdown −18% · 214 trades".

| Output | Lead | View | Notes |
|---|---|---|---|
| Equity and drawdown | Total return vs benchmark | Line + underwater | Log scale toggle; gross vs net (costs) overlay; in/out-of-sample split line |
| Key stats | Sharpe, CAGR, max DD, trades | KPI strip | Full metric list §4 in the table view |
| My limits | "Passes 5 of 6 of your limits: drawdown lasted 19 months (limit 12)" | Checklist above the hero | First thing on the page |
| Returns by period | Best and worst year; "without the best 3 months: CAGR 4.2%" | Monthly heatmap + yearly bars vs benchmark; toggle hides best months | Merged card (Outputs v2 rule) |
| Trade list | Win rate, average win/loss, profit factor | DataTable, virtualised | Columns: entry/exit time and price, side, size, P&L, %, bars held, MAE, MFE, exit reason, costs; click opens the trade on the Chart |
| Carried by | "Best 5 trades made 62% of profit; without them CAGR 3.1%" | Bars: P&L share of top 1/5/10 trades; equity with and without them | **ours**, asked for by name |
| Fill check | "Hourly fills cut return by 11%" | Bar result vs bar-magnifier result, side by side | TV sells the magnifier; we show the difference |
| Crisis events | Return vs benchmark in each named period held | Small multiples, 17 periods (DotCom 2000 … AI Boom 2022–) clipped to our data range | (QC) |
| Capacity | "About $4M before impact" | One number from average daily dollar volume and position sizes | (QC) |
| Trade analysis | "Losers would have been winners in 31% of cases": MFE ≥ 1R on losing trades | MAE/MFE scatter + edge ratio | (AB), finlab; **ours**: the one-line finding |
| P&L distribution | Skew and tail | Histogram of trade returns with normal overlay | |
| Holding time | Median bars held, winners vs losers | Two box plots | |
| Exposure | Time in market, average gross and net | Area over time | |
| Costs | "Costs ate 23% of gross return" | Gross vs net bars, turnover | **ours**: the share eaten |
| Holdings (portfolio) | Top contributors | Treemap by P&L; weights over time | Screener C3 replay re-used ★ |
| Benchmark relation | Beta, alpha, correlation, up/down capture | Rolling beta and correlation lines | |
| Rolling metrics | "Sharpe 1.4 in the first third, 0.3 in the last: decaying" | Rolling 6M/12M Sharpe, vol and beta; first vs last third marked | (QC rolling; decay check is **ours**) | |
| Replay ★ | — | Play/scrub: equity draws, trades pop on price, holdings fly in/out | Screener C3 |
| Limits | "5 limits" pill | Popover | Fill model, costs, survivorship, data range, fundamentals lag |

### st02 Optimise
Hero: **"Plateau at fast 40–60, slow 180–220: Sharpe 0.9–1.1"**, not the single best cell. Picture: the heatmap.

| Output | Lead | View | Notes |
|---|---|---|---|
| Parameter map | Plateau found / spike only | 2D heatmap (pick any two params), others fixed at plateau centre | (SQ), Strateda, (AB) |
| Surface ★ | Shape of the surface | 3D surface, rotate; still = contour | Strateda, QANTHOS |
| Stability score | "71% of neighbours within 20% of best" | Gauge + neighbourhood histogram | **ours**: one number for plateau width |
| Top sets | Best 20 by objective | Table: params, Sharpe, CAGR, DD, trades, stability | Click to backtest that set |
| Objective trade-off | Pareto front | Scatter return vs DD, front highlighted | Optuna multi-objective |
| Parameter importance | "slow matters 3× more than fast" | Bars (fANOVA from Optuna) | |
| Equity fan | Spread of outcomes across the plateau | Overlaid equity lines, best bold | Strateda |
| Search settings | Grid / random / Bayesian (Optuna, TPE), budget, objective (Sharpe, CAGR/DD, profit factor, custom formula), min trades filter | Inspector | Results include **number of trials**, fed to DSR (st06) |

### st03 Walk-forward
Hero: **"Walk-forward efficiency 68%: out-of-sample kept two thirds of in-sample return"**.

| Output | Lead | View | Notes |
|---|---|---|---|
| Stitched OOS equity | OOS return vs benchmark | Line, each window shaded and labelled with its chosen params | |
| Windows table | Windows passed / total | Table: IS and OOS dates, chosen params, IS and OOS Sharpe/return, WFE | Anchored or rolling, purge and embargo |
| WF matrix | Best (re-opt period × OOS %) cell and how many cells pass | Heatmap | (SQ) walk-forward matrix |
| Parameter drift | "fast moved 20→65 across windows: unstable" | Line of chosen params per window | **ours** |
| IS vs OOS | Decay ratio | Paired bars per window | |

### st04 Robustness (the Build Alpha set, on the user's own strategy)
Hero: **"Passes 7 of 9 tests"** with the two failures named, over a strip of pass/fail tiles.

| Test | Lead | View | What it catches |
|---|---|---|---|
| Vs random | "Beats 96% of 1,000 random strategies with the same trade count and holding time" | Histogram of random Sharpes, ours marked | Luck (BA) |
| Monte Carlo permutation (MCPT) | p-value | Histogram of permuted-price results | Edge from path order (BA) |
| Noise test | "Sharpe holds above 0.7 in 90% of 500 noised histories" | Fan of equity lines + width band | Fit to noise (BA) |
| Vs shifted | Result when bars start 1–4 sessions later | Bars per shift | Arbitrary bar alignment (BA) |
| Vs other markets | Pass rate on related symbols / sector peers | Small multiples | Over-specific to one symbol (BA, SQ multi-market) |
| Delay | Return with entries 1 and 2 bars late | Bars | Execution sensitivity (BA) |
| Cost shock | Return at 2× and 3× costs | Line return vs cost multiple, break-even cost marked | (SQ what-if) |
| Liquidity | Result with max 1% of bar volume | Before/after | Capacity |
| Parameter permutation | Share of nearby settings still profitable | Heatmap from st02 neighbourhood | (BA), (SQ) |
| Variance | Spread of results when trades are randomly skipped (5–20%) | Fan + width | (TrendSpider, BA) |
| Data source | Same run on adjusted vs unadjusted, daily vs hourly-resampled | Two lines | Data artefacts |

Each tile: pass/fail/skipped with reason, the threshold used, and "run again with more paths".

### st05 Monte Carlo
Hero: **"95% of reshuffled paths stay above −27% drawdown"**.

| Output | Lead | View |
|---|---|---|
| Equity bands ★ | 5th/50th/95th percentile end value | Fan chart, original bold |
| Drawdown distribution | 95th percentile max DD vs backtest DD | Histogram |
| Risk of ruin | P(DD > user threshold) | Gauge + table of thresholds |
| Return distribution | P(CAGR < 0) | Histogram |
| Randomized exits | "Exits beat random exits in 88% of runs" | Histogram (BA "are your exits overfit?") |
| Streaks | 95th percentile losing streak | Bars |
| Methods | Reshuffle, resample with replacement, block bootstrap, trade skip (drop k%), seeded | Inspector |

### st06 Overfitting
Hero: **"Deflated Sharpe 0.62 after 1,840 trials: likely real"** or **"Probability of overfitting 71%: the best setting is a fluke"**.

| Output | Lead | View |
|---|---|---|
| Deflated Sharpe | DSR and the trial count it corrects for | Gauge; Sharpe vs expected max of N skill-free trials |
| Probabilistic Sharpe | P(true Sharpe > 0) | Gauge |
| PBO (CSCV) | Probability of backtest overfitting | Logit histogram; IS-rank vs OOS-rank scatter |
| CPCV | Distribution of OOS Sharpe across combinatorial paths | Violin + path equities (reuse ml_v2 cpcv) |
| Minimum track record | "Needs 3.4 years of live record to trust at 95%" | One number with formula |
| Haircut Sharpe | Sharpe after multiple-testing haircut | Before/after bars |
| Hold-out | The untouched last 20%: return and Sharpe vs in-sample | Paired bars; "touched N times" counter (**ours**: each peek is logged) |

### Verdict (reads st03–st06, no own job)
Hero: grade **A–F** with a one-line reason ("Real edge, fragile to costs: break-even at 2.1× costs").
- Score table: each test, weight, pass/fail, link.
- What would change the verdict: the cheapest fix ("needs 40 more trades", "loosen stop from 3% to 5% sits on plateau").
- **Ours**: nobody combines all tests into one graded, explained verdict.

### st07 Regimes
Hero: **"Makes all its money in trending, low-vol markets: 84% of P&L"**.

| Output | Lead | View |
|---|---|---|
| By regime | Return and Sharpe per regime | Bars; regimes: trend up/down/sideways (SPY 200d), vol terciles (VIX or realised), drawdown state, rate regime (if macro held), HMM states |
| Regime timeline | — | Price with regime bands, strategy equity under |
| By year and month | Best/worst year | From st01 (linked, not duplicated) |
| By sector / symbol (portfolio) | Top and bottom contributors | Bars |
| By day of week / hour (hourly) | Strongest slot | Heatmap |
| Seasonality | Month of year hit rate | Bars (TrendSpider) |
| Trades per regime | "Only 9 trades in bear markets: too few to judge" | Count beside each regime bar (wiseapple) |
| Conditional | "When VIX > 25, Sharpe −0.4" | Table of conditions |

### st08 Combine
Hero: **"Three strategies together: Sharpe 1.4 vs best single 1.1, drawdown −12% vs −18%"**.

| Output | Lead | View |
|---|---|---|
| Correlation | Lowest-correlated pair | Heatmap + dendrogram (reuse charts) |
| Combined equity | Combined vs each | Lines |
| Allocation | Weights by method (equal, inverse vol, risk parity, max Sharpe, HRP) | Stacked bars; reuse portfolio_v2 / ml_v2 allocation |
| Marginal contribution | Which strategy adds most | Bars |
| Overlap | Shared trades and names | Matrix |

### st09 Signals today
Hero: **"7 entries, 3 exits as of 2026-01-28"**.
- Signal table: symbol, action, signal value, distance to trigger, last trade, position size; tick rows → Compare (Screener X1) or add to Paper.
- Near triggers: names within x% of firing.
- Map: universe as dots, firing ones lit (Screener C5 sorting field, re-used).

### st10 Paper
Hero: **"+4.1% since freeze on 2026-01-02 vs backtest expectation +3.2% ± 5.0%"**.
- Forward equity vs the backtest's Monte Carlo band (st05): inside or outside the band.
- Fills ledger: daily EOD from parquet, same fill model and costs.
- Drift alert: live Sharpe or DD leaves the 95% band → Monitor alert (Screener alerts + notify).
- **What the data can tell you yet** (**ours**, from halleytech 2026-09): "After 3 months a dead edge is caught 18% of the time; a halved one 10%." Shown with the date when each test gains 80% power, so nobody retires a strategy on noise.
- **Cost leak first**: paper fills vs the backtest's assumed costs, per day; a cost gap is visible in weeks where a Sharpe gap needs years.
- **Signal health**: for ranking strategies, the daily rank IC against its backtest mean; resolves decay about 8× faster than P&L.
- **Is this drawdown expected?**: probability of a drawdown this deep under the backtest Sharpe and under half of it (e^(−2SD)); the ratio as plain odds.
- **Sizing from evidence**: live Sharpe blended with the deflated backtest Sharpe (weight by live years); suggested size change.
- **Shadow book**: a stopped strategy keeps running on paper for 12 months, so the stop rule can be judged later.
- Gates kept: freeze only from a certified or validated version; kill switch; limits (position, exposure, daily loss).
- Schedule: runs after the daily data load (Screener scheduler).

### st11 Certify
Hero: grade + hash + "reproduced 2026-11-15 ✓".
- Server re-runs backtest and every validation test from the stored spec, data version and seed; compares hashes.
- One-page PDF (Screener P7 pattern): hero, equity, verdict table, limits, code or rules, hash.
- Share link and embed (Screener `/share/<token>`).

### st12 Chart
- Price with volume; indicators (ported library); drawings; multi-pane.
- Strategy overlay: entry/exit markers, stop and target lines, position shading, signal values in a pane.
- Trade navigator: next/previous trade, jump from any trade list.
- Replay ★ bar by bar with play/scrub and speed.
- Sync crosshair across panes and symbols; compare symbols rebased.
- Alerts on indicator or strategy conditions, server-side.

### Home
- Your strategies as cards: mini equity, grade, last run, paper status; sort and folders (Screener Saved page pattern).
- Recent runs, templates, "start from a Screener screen" button.

## 4. The metric set (one function, every page)

Returns: total, CAGR, annual vol, Sharpe, Sortino, Calmar, Omega, gain-to-pain, Ulcer index, UPI, MAR, tail ratio, skew, kurtosis, VaR/CVaR 95, best/worst day, month, year, % positive months.
Drawdown: max DD, average DD, max DD duration, recovery time, time under water, number of DDs > 10%.
Trades: count, per year, win rate, profit factor, payoff ratio, expectancy ($ and R), average win/loss, largest win/loss, max consecutive wins/losses, average bars held (win/loss), SQN, Kelly, edge ratio (MFE/MAE).
Exposure and cost: time in market, average gross/net exposure, turnover per year, costs total and as % of gross.
Vs benchmark: alpha, beta, correlation, R², tracking error, information ratio, up/down capture, excess return.
Trust: PSR, DSR (with N trials), PBO, min track record, trades in hold-out, data coverage.

Each metric has a one-line definition in a tooltip and a link to its formula (same as Screener format tooltips).

## 5. Compare (any two of anything)

- Two runs of one strategy (settings changed, numbers, curves overlaid): Screener X4 pattern.
- Two versions of one strategy: rule/code diff + result diff.
- Strategy vs benchmark vs buy-and-hold: permanent rows.
- Up to 8 strategies: equity, metrics table with winner per row (Screener X3), correlation.

## 6. Export

CSV of every table, trade list as CSV, equity as CSV, PNG/SVG of any chart, one-page PDF, full report PDF, the strategy as JSON spec and as Python.

## 7. Paid features elsewhere, free here (researched 2026-11-15)

Prices as read on the pages cited in [COMPETITORS.md](COMPETITORS.md).

| Feature | Who charges, and how much | Here |
|---|---|---|
| More history per test | TradingView: 5,000 bars free, 10,000 Essential/Plus (€12.95/€29.95), 20,000 Premium (€59.95), 40,000 Ultimate (€199.95) | All history we hold (1999– daily) |
| Deep backtest, every trade kept | TradingView Premium+ (2M bars, 1M trades) | Default |
| Bar magnifier (intrabar fills) | TradingView, paid; Composer sells near-close execution on Pro ($32/mo, yearly) | From hourly bars where held, plus the Fill check |
| More indicators per chart | TradingView 2 free → 50 Ultimate | No cap |
| Backtest depth and symbols per test | TrendSpider: 10K–20K candles, 50–250 symbols per test by plan; +$39/mo for 20K depth | Whole universe, all history |
| Test a whole watchlist at once | TrendSpider (marketed as a plan feature) | Universe input |
| Backtest PDF report, local coding, tick data | QuantConnect Researcher $84/mo | One-page and full PDF (st11) |
| Point-in-time history, custom ranking simulations | Portfolio123 $300–$2,400/yr; custom ranking from $1,000/yr | Screener ranks as strategies; PIT fundamentals from 2021 (said plainly) |
| Robustness battery (vs random, noise, shifted, MCPT) | Build Alpha licence; StrategyQuant X Pro $1,490 / Ultimate $2,900 | st04 |
| Walk-forward matrix | StrategyQuant X Ultimate | st03 |
| Strategy correlation and portfolio of strategies | StrategyQuant Portfolio Master (Pro: 4 strategies), Portfolio123 users ask for it | st08, no cap |
| Unlimited backtests, many bots | Option Alpha Pro $149/mo ($99 yearly) | Unlimited runs; Paper slots uncapped |
| AI strategy help | TrendSpider Sidekick (25 free messages, paid more), Composer AI | Plain English → formula, shown before run |
| Multi-timeframe on one chart | TrendSpider | Chart MTF badge |
| Seasonality | TrendSpider | st07 |

## 8. Best-in-class report: the honest reading order

Tear-sheet readers read in this order because "the equity curve is persuasive while the rest of the sheet is informative" (datapigtechnologies 2026-08). The Backtest page offers it as a layout ("Honest order"), default for new users:

1. Fine print: period, costs, fill timing, OOS split, data limits (and My limits pass/fail)
2. Drawdown: depth, duration, recovery
3. Monthly table, with the best 3 months removable
4. Return distribution and skew
5. Rolling Sharpe, first third vs last third
6. Rolling beta and exposure
7. Equity curve last, log scale
