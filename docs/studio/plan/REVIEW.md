# Studio v3: harsh review

Date: 2026-11-15. Reviewed: PLAN, FEATURES_AND_OUTPUTS, FRONTEND (read fully); COMPETITORS, OPEN_SOURCE, REUSE, CHECKLIST, OUTPUTS_V2 (skimmed). Companion: [PAGES.md](PAGES.md) (the replacement page spec).

Marks: **[official]** vendor's own page. **[third party]** review, blog, forum or news. **[unverified]** snippet only, single anonymous source, or contradicts another source. **[repo]** measured in this repository today. Source ids `Sn` are in section 8 with URL and date.

---

## 1. Verdict

The plan is strong on testing depth and honest on limits. It is weak in five places, and two of them are blockers.

| # | Finding | Severity |
|---|---|---|
| 1 | **The data is not what the plan says, and it is stale.** Daily parquet runs 1996-03-18 to **2026-07-06** (10.78M rows, 4,158 tickers) [repo]. PLAN says 1999 to 2026-01-28. Hourly parquet holds **23 tickers**, 122,113 rows, 2023-02-27 to 2026-04-03 [repo]. Today is 2026-11-15, so "Signals today", Paper and alerts have no fresh bars, and the "bar magnifier" and "Fill check" lead outputs cannot run on almost any universe. No phase 0 item covers a daily data update. | Blocker |
| 2 | **"Nobody has an agent API" is false.** QuantConnect (2026-11-03), StrategyQuant (2026-10-27), Build Alpha (2026-11-13), Tactfolio (2026-10-16), Canli and NinjaTrader (2026-09-22) all ship MCP or AI builders [S2, S7, S9, S13, S27, S4]. The agent API is table stakes. The edge is the guard rails (trial ledger across actors, sealed hold-out), which the plan has only as a trial counter. | High |
| 3 | **The validation verdict is no longer unique.** Stochastly, Canli, QuantProof and Manifold-BT launched DSR, PBO, grades, planted checks and crash tests in 2026 [S26-S29]. Our edge is that the tests run on the user's own compiled strategy, on data we hold, with delisted names, a trial ledger, a sealed hold-out and a paper record that continues the same strategy. The plan says "nobody combines all tests" and stops there. | High |
| 4 | **Too many pages for one question.** 15 pages; five of them (walk-forward, robustness, Monte Carlo, overfitting, verdict) answer "is it real?" and the verdict page reads the other four. A user must open five pages and run four jobs before the first answer. Replace with 9 pages (section 4). | High |
| 5 | **Everyday features are missing** (section 3, P0): start-date sensitivity, survivorship delta, per-name results table, cost ladder on the first screen, risk-per-trade sizing, time and scale-out exits, higher-timeframe rules without look-ahead, daily digest, autosave, trade import and reconcile. | High |
| 6 | **Scope creep in section 9 of FEATURES.** Manual replay plus journal (G2), public gallery (G4), prop-firm page (G5), wash-sale tax (G10) are separate products with separate data needs. Cut or demote (section 3). | Medium |
| 7 | **Several silent assumptions the plan itself warns against**: delisted holdings settle at last close (a known silent bias, [S21]); the trial counter counts raw tries and can be gamed by near-duplicates [S24]; "cheapest fix" in the Verdict invites tuning on the verdict. | Medium |

Net: keep the engine design, the principles, the metric set, the limits pill and the hero rule. Replace the page plan. Add the P0 list. Cut the four products-in-disguise. Fix the data blocker in phase 0 before any UI work.

---

## 2. What traders and quants want, and what they complain about

Evidence only; no invented numbers.

| Want or complaint | Evidence | Source |
|---|---|---|
| Live results never match the backtest; fill price, costs, inside-bar moves are the top causes | Nine-reason list; trade-by-trade reconcile table (same trades? fill difference? residue? grows with volatility?) | S17 [official], 2026-09-08 |
| Dead companies change the answer | One user: same strategy 20.7% a year with today's survivors vs 18.1% with delisted names kept (2015 to mid-2026); 1999-2019 edge 7.9% vs 6.3% | S18 [unverified, single poster], 2026-10-10 |
| ... but not for every strategy | Intraday test: profit factor 1.23 without vs 1.25 with delisted; "different story for overnight holds" | S50 [third party], 2026-06-02 |
| Presence of delisted rows is not enough: delisting return, point-in-time membership, split handling decide | Vendor guide: most tools value a vanished stock at its last price "with no flag" | S21 [third party, data vendor], 2026-08-27 |
| Check the data before the strategy | Symbols per year (410 in 2003, 3,251 in 2006 in one feed); equity-curve rows / 252 = years; fundamentals filed a median 54 days after year end; 1,000 coin-flip traders: 9 cleared Sharpe 2 | S19 [third party], 2026-11-09 |
| Costs decide more than signal | ML ranking: +13.2% a year before costs, 11.0% at 2 bp, 7.7% at 5 bp, 2.4% at 10 bp | S18 [unverified] |
| High win rate is meaningless without a random-entry control with the same stop and target | Same post | S18 [unverified] |
| Limit orders: unfilled ones are the winners | ~20% of limits never filled; non-filled went on to +1.95% on average | S18 [unverified] |
| Pass mark written before the run; one look per idea at the validation block | Three date-locked blocks, worst-case same-bar fills, every run logged | S20 [third party], 2026-09 |
| Look-ahead through higher-timeframe requests and order-on-close settings | In 751 TradingView strategies, `process_orders_on_close` was on in 13%, `calc_on_every_tick` 7%, HTF future leak 6%, bar magnifier 3% | S35 [third party, snippet], 2026-11-01; S36 [third party], 2026-10-18 |
| An empty run should be refused, not shown as a thin result | Tradetron's engine refuses and refunds | S17 [official] |
| Code-first tools are slow to learn; IDE instability | "Steep learning curve, code-only", "IDE stability issues" | S48 [third party], 2026-03-13 |
| India: no tool combines no-code, cross-sectional ranking, 15+ years survivorship-free NSE data and a live path; Streak caps a backtest near 20 stocks and about 4 years on close prices | Competitor-written map | S16 [third party, vendor-authored], 2026-06-02 |
| India costs are specific (delivery STT 0.1% both sides, intraday 0.025% sell side) | Broker blog; F&O STT change from 2026-04-01 is only in an Instagram snippet | S40 [third party], 2026-10-21; [unverified] for the F&O change |
| Prop traders want rule simulation (profit target, daily loss, max drawdown, min days) on a backtest | LuxAlgo Prop tab, SQX build 144, GoatFundedTrader, Tradatix | S11 [official] 2026-10-23; S8 [official, undated snippet]; S45 [third party] 2026-08-14 |
| Agents overclaim edge | LLM agents "claim predictability too often in worlds without a signal"; need a fixed decision rule outside the agent and a sealed holdout | S23 [third party, preprint], 2026-11-02 |
| Searches by agents inflate results; a naive in-loop bar is exploitable by near-duplicates | "Variance-dilution effect" | S24 [third party, preprint snippet], 2026-11-13 |

---

## 3. What is missing from the plan (by priority)

### P0: everyday features and blockers

| # | Missing | Why it matters (evidence) | Where it goes |
|---|---|---|---|
| 1 | **Fresh daily data and an update job.** Daily bars end 2026-07-06 [repo]. A signal or paper step "as of" a date months old is wrong. Add: data freshness pill on every page, a daily load job, "stale: N days" blocking Signals and Paper. | Plan hero example uses 2026-01-28; Paper "steps daily from parquet". | Phase 0, Library > Data |
| 2 | **Hourly reality check.** 23 tickers [repo]. Bar magnifier and Fill check become "available for these 23 names", else "worst-case same-bar rule". Stop selling it as a lead output of st01. | Plan §5.1 and st01 "Fill check". | Backtest > Risk, limits pill |
| 3 | **Start-date sensitivity**: run the strategy from N start dates; show the share that pass My limits and the spread of CAGR and drawdown. | LuxAlgo shows "start dates: 5 of 12" per challenge and "closest call" [S11, official, 2026-10-23]. Composer's start date is set by the youngest ticker [S37, third party, 2026-09-25 snippet]. Missing from the plan. | Backtest > Overview |
| 4 | **Survivorship delta**: same run with delisted names removed (today's survivors) vs kept; one line "dead companies cost 2.6 points a year". We hold the data. Plus a **delisting-return setting** (last close, or a haircut) instead of the silent last-close rule. | S18, S21, S50. Shumway correction is named in S21; size of the haircut not verified here. | Backtest > Risk; Build settings |
| 5 | **Per-name results table** (group tester): rank every symbol's trades, contribution, best and worst names, where stops hit. | TrendSpider Group Strategy Tester [S6, official, 2026-07-22]; Build Alpha Quick Test lists top and worst tickers, when stops and profits hit [S10, official, 2026-01-28]. Plan has "Holdings treemap" only. | Backtest > Names |
| 6 | **Cost ladder on the first screen**: net result at 1×, 2×, 4× costs next to the hero, not buried in Robustness. | Tactfolio shows 0.05% with extra checks at 0.10, 0.20, 0.40% [S13, official, 2026-10-16]; S18 shows the same thing. | Backtest hero |
| 7 | **Sizing by risk per trade** (fixed fractional: risk 1% of equity to the stop). Plan lists fixed, %, vol target, Kelly, equal, score, parity but not 1R sizing, while its metrics use R. | NinjaTrader's own example includes stop, target, quantity [S4, official, 2026-09-22]. | Build > Sizing |
| 8 | **Exits people use every day**: time stop (N bars), breakeven move, scale out in parts, scale in; `orders.py` lists market, limit, stop, stop-limit, trailing, take-profit, OCA, pyramiding only. Add partial close, time stop, move-stop rules. | Same S4 example uses an exit after 10 bars. | Build > Exit; engine |
| 9 | **Higher-timeframe rules that cannot leak** ("weekly 30 SMA up" on a daily rule), aligned to the last closed higher bar. | S36, S35. Plan has MTF only as a chart badge. | Build > Blocks |
| 10 | **Daily digest and signal alerts** (email, push, Telegram, webhook) tied to Signals, with quota shown. Promote G1 from phase 5 to phase 3. | Tactfolio paper trading sends a daily email [S13]. TradingView webhooks need Essential or above; active-alert limits 20/100/400/1000 by tier [S32, third party, 2026-09-16]. QuantConnect MCP can send email, SMS, Telegram [S2]. | Live > Alerts |
| 11 | **Autosave, draft recovery, undo history** in Build; duplicate, folders, tags, search on Home. Plan has versions only (explicit saves). | Basic editor expectation; IDE instability is a stated pain [S48]. | Build, Home |
| 12 | **Refuse zero-trade or too-few-trade runs** with a named reason ("0 entries: rule never true on this universe"), never a thin result. | S17. | Backtest empty states |
| 13 | **Reconcile live vs backtest** as a table: same trades triggered, average fill difference, residue, grows with volatility. | S17 [official]. Plan has "cost leak" only. | Live > Reconcile |
| 14 | **Import real trades (CSV)** and **import other tools' strategies** (Composer symphony JSON, QuantMage spell JSON via a mapper; Pine as stretch). | Tactfolio imports Composer symphonies and QuantMage spells [S15, official snippet, 2026-10-28]. Real-trade import is the reconcile input. Pine import: LuxAlgo open-sourced PineTS and Vela core [S44-adjacent, github.com/luxalgo, 2026-10-13, official snippet]; licence **[unverified]**. | Home, Live |
| 15 | **Data audit card**: symbols per year, bars per symbol, rows / 252 check, fundamentals filing lag, adjusted-price status, delisted share, gaps. Printed on every result's "N limits" popover and in Library > Data. | S19. | Library, limits pill |

### P1: raises the product from complete to best

| # | Missing | Evidence | Where |
|---|---|---|---|
| 16 | **Luck lottery** as the lead of Overfitting: "With 1,840 tries, pure luck reaches Sharpe 1.9; yours is 1.4." Simulated from our own noise. | S19 placebo (9 of 1,000 skill-free traders cleared Sharpe 2). Plan's DSR is correct but not legible. | Validate > Luck |
| 17 | **Effective number of trials** (cluster correlated tries) instead of a raw counter. | S24: near-duplicate mediocre candidates lower a naive bar. Canli's API takes `effective_independent_trials` [S27, third party listing, 2026-10-07]. | Build trial ledger |
| 18 | **Sealed hold-out with a look budget** that agents and AI helpers cannot spend freely; every look logged by actor. | S23, S20. Plan has "touched N times" only for humans. | Validate > Hold-out; Agent API |
| 19 | **Verdict power card**: plant a known edge in the user's universe and trade count, report the smallest Sharpe the pipeline detects 80% of the time and its false-positive rate on shuffled data. | SSRN paper on planted-signal power of validation pipelines, posted 2026-11-14 [S25, third party, snippet only]. No retail tool shows it. | Validate > Verdict |
| 20 | **Closest call** on every My limit: "drawdown limit 25%, worst 22%, 12% room". | LuxAlgo card [S11]. | Backtest limits strip |
| 21 | **Deterministic "what this strategy does" paragraph** from the spec (no LLM), shown on Build, Backtest, report. AI reviewer is then optional. | TradeZella sells an AI that tells you what results mean [S49, competitor-authored, 2026-07-07]; NinjaTrader says "read what it wrote" [S4]. | Build, report |
| 22 | **Limit-order outcome**: for limit entries, the return of unfilled orders. | S18 [unverified]. | Backtest > Trades |
| 23 | **Meta strategies promoted** (if/else on regime, rotate, weight): this is the core no-code retail pattern (Composer, QuantMage, Tactfolio's "hold the S&P 500 while above its 200-day, else bonds" example [S13]). Plan puts it in phase 5 as G7. | S13, S37. | Build > Allocate block, phase 2 |
| 24 | **Optimise: plateau metric on the sweep page** and trade-off with trial ledger. Plan already has it; keep. | Strategy Optimizer for TradingView sells a plateau metric and 1,000 resamples [S30, vendor, 2026-09-05]. | Optimise |
| 25 | **Notes inside Build** (hypothesis, decisions) merged from G12. | Cheap; supports pre-registration [S20]. | Build |
| 26 | **Share an unfinished read-only run** (link with settings, no private prefs). Plan has share; add "expires" and "view count". | Standard. | Cross-page |

### P2: later

India cost profiles dated by rate change (STT schedule is versioned); earnings-date avoid filter if earnings dates are held (check); strategy health score for saved strategies on Home; Pine import; public gallery after a real paper record exists; per-strategy API tokens.

### What to cut or demote from the grand-stage list

| Item | Verdict | Reason (with evidence) |
|---|---|---|
| G2 manual replay + journal | **Cut from v3** | Separate product category (FX Replay $17.99 and $35 a month, Forex Tester $159 a year, TradeZella and Tradervue [S33, S34, third party, 2026-09-10 and 2026-07-13]). They win on 1-minute and tick history back to 2003 and 23 years of tick data; we hold daily bars and 23 hourly tickers [repo]. Keep strategy Replay on the chart (automated trades), not hand trading. |
| G4 verified gallery | **Defer past v3** | Needs a track record that does not exist yet; ranking by return is the failure mode (a study cited on r/algotrading says in-sample metrics from 888 Quantopian strategies had virtually no predictive value, [S47, third party snippet, 2026-03-01]). Share links do the job now. |
| G5 prop-firm page | **Demote to a panel in Backtest > Paths** | Prop rules target futures and forex; we hold neither. LuxAlgo, SQX and Stochastly all ship it [S11, S8, S26], so a small rule check (target, daily loss, drawdown, min days, start dates) on US equities is cheap; a page is not. |
| G10 tax and wash-sale | **Defer**; keep dated cost profiles with taxes as a later option | Not asked by any source read; adds legal weight. |
| G14 capacity curve | **Merge into the Capacity card** (one number plus the curve in Table view) | Two outputs saying one thing. |
| G15 stress scenarios | **Merge into Validate > Robustness** as "Shocks" | Same inputs as noise test. |
| G12 notebook | **Merge into Build > Notes** | Not a page. |
| G11 AI reviewer | **Keep, as optional text over deterministic findings** | Never produces the grade; S23 says agent verdicts need a fixed rule outside the agent. |
| G13 agent API | **Keep, promote to phase 1**, rewrite claim from "nobody" to "with guard rails" | S2, S7, S9, S13. |
| G9 India | **Keep; blocked on coverage measure** | S16 shows the gap; also shows saral.money targets it. |

---

## 4. What to remove, cut or merge

| Item in current plan | Action | Reason |
|---|---|---|
| 5 Validate pages + Verdict + Certify | Merge into one **Validate** page (tabs: Verdict, Walk-forward, Robustness, Luck, Certificate) | One question, one run, one verdict; SSE tile flip (S6 moment) works on one page; competitors expose it as one call (Canli `audit_backtest`, QuantProof "38 checks in 2 seconds") [S27, S28]. |
| Monte Carlo as its own page | Split: **trade-based Monte Carlo (reshuffle, resample)** moves to Backtest > Paths (one second to compute, LuxAlgo puts the same thing in its backtest viewer [S12]); **price-based tests** (MCPT, noise) live in Validate > Robustness | Two meanings of "Monte Carlo" confuse users. |
| Regimes page | Merge into Backtest > When | Reads the same trades; adds one tab, not a page. |
| Signals today + Paper | Merge into **Live** (Today, Forward, Ledger, Health, Reconcile, Alerts) | Same strategy, same daily step, same alerts. |
| Certify page | Becomes Validate > Certificate | Action on a verdict, not a destination. |
| Combine | Rename **Portfolio**; absorbs meta strategies | Name says what it is. |
| Backtest outputs "Rolling metrics", "P&L distribution", "Holding time", "Exposure", "Benchmark relation" as five cards | Merge into **Trade shape** and **Stability** cards; rolling Sharpe decay becomes the one-line finding on Stability | Outputs v2 rule: one lead figure; these five had no lead. |
| "Crisis events" 17 small multiples | One strip with only the periods inside our data; table in Table view | Outputs v2 rule: fewer, bigger. |
| Cinematic S2 (replay pops) and S4 (windows sweep) | Keep one replay (Backtest hero action); S4 optional | S2 duplicates Replay. |
| Optimise 3D surface rotation (S5) | Heatmap leads; 3D lazy-loaded, off by default | Heatmap carries the finding; 3D costs bundle and rarely changes a decision. |
| Verdict "What would change it: cheapest fix" that proposes parameter changes | Replace with fixes that do **not** tune on the verdict ("needs 40 more trades", "costs break it at 2.1×"); any parameter suggestion increments the trial ledger and opens a new version | Tuning to pass the verdict is the overfitting the verdict exists to catch. |
| Workspace presets bundle | Fold into Library > Profiles (cost, validation, report order) | One place for customisation. |
| Compare 8 strategies as a separate "Compare" concept | Keep Compare as a cross-page action, Portfolio shows the combined view | Remove the duplicate. |
| PLAN §6 "dissect and port the old chart" | Keep indicator maths and drawings; do not port `PatternScanner` until a use is named | Patterns have no output in any page spec; Chart-only. |

---

## 5. Page structure proposal

Nine pages replace fifteen. Full spec in [PAGES.md](PAGES.md).

| Page | Action | Replaces | Why |
|---|---|---|---|
| Home | **Keep, extend** | Home | Adds "needs attention", data freshness, import |
| Build | **Keep, extend** | Build | Adds autosave, notes, trial ledger, allocate blocks, explain paragraph |
| Backtest | **Keep, absorb** | Backtest, Regimes (as When), trade Monte Carlo (as Paths), Holdings (as Names) | One run, seven tabs |
| Optimise | **Keep** | Optimise | Heavy, own job, own inputs |
| Validate | **Merge, new** | Walk-forward, Robustness, Monte Carlo (price tests), Overfitting, Verdict, Certify | One verdict, one run |
| Portfolio | **Rename, extend** | Combine, G7 | Meta strategies live here and in Build |
| Live | **Merge, new** | Signals today, Paper, G1 alerts, G3 import | Daily-use page, phone-first |
| Chart | **Keep** | Chart | Replay, trades on price |
| Library | **New** | scattered "saved universe, cost profile, regime, metric, block, validation profile" | Customisation had no home; data audit lives here |
| (deleted) | **Delete** | Walk-forward, Robustness, Monte Carlo, Overfitting, Verdict, Regimes, Signals today, Paper, Certify as pages | Merged above |

Nav: `Home · Build · Test (Backtest, Optimise, Validate) · Portfolio · Live · Chart · Library`.

---

## 6. Best outputs found elsewhere: copy or beat

I read text descriptions, not screenshots, except where noted. [unverified] where only a vendor claim.

| Output | Who | What to copy | How we beat it |
|---|---|---|---|
| Challenge card: equity against Target, Drawdown, Loss limit lines; three numbers under it ("passed in 90 days", "closest call 18% room", "start dates 5 of 12"); ring with Pass / Almost / No fit | LuxAlgo Vela [S11, official, 2026-10-23] | "Closest call" and "start dates" on every My limit | Same card for any limit, not only prop rules; with trial ledger |
| Simulated net-profit paths: actual, median, 25-75 and 5-95 bands; Resample vs Shuffle; 250/1,000/2,500 runs; caution that bands are not boundaries | LuxAlgo [S12, official, 2026-09-18] | Copy the caveat text and the two methods | Add block bootstrap and trade skip; lead finding as a sentence |
| Quick Test: summary, top and worst tickers, when stops hit, when profits hit | Build Alpha [S10, official, 2026-01-28] | Names tab | Per-name table with contribution and virtualised rows |
| Group Strategy Tester: one sortable table across symbols, timeframes, depths | TrendSpider [S6, official, 2026-07-22] | Names tab | Whole universe, point in time, delisted kept |
| `audit_backtest` returns each check with a receipt and `fix_next` | Canli [S27, third party listing, 2026-10-07] | Verdict returns "next test to run" | Re-run reproduces the whole result, not only the statistic |
| Edge Score out of 100 weighing profit, drawdowns, consistency, execution, proof | Quantprove [S28, vendor, 2026-10-29] | One number is easy to read | Show weights and let users edit (already in plan); letter grade, never a score without reasons |
| 38 checks in 2 seconds, crash simulations, "profit concentration: share from top 3 trades" | QuantProof [S28, vendor, 2026-03-10] | Speed target for Validate quick pass | Carried-by already covers concentration |
| Plateau metric and 1,000 resamples for optimisation | Strategy Optimizer for TradingView [S30, vendor, 2026-09-05] | Already planned | Plateau shown as outline on the heatmap |
| Reconcile table: same trades? fill difference? residue? grows with volatility? | Tradetron [S17, official, 2026-09-08] | Live > Reconcile | Automatic from Paper ledger or imported CSV |
| Honest reading order (fine print first) | Tear-sheet readers [S, in FEATURES §8] | Already planned | Keep |
| Forward test as "a record after a frozen definition"; revision starts a separate segment; never join winning periods across versions | Quandora docs [S22, official, 2026-10-17] | Paper freeze rules | Enforce in code: a new version cannot inherit a Paper record |
| Deep backtest 2M bars and 1M trades per run | TradingView Premium [S31, third party, 2026-10-17] | None | Default for everyone; no cap |

---

## 7. Ideas we can own

Each is checked against sources read; "no source found" is a research finding, not proof.

| # | Idea | Why ours | Evidence of gap |
|---|---|---|---|
| O1 | **Luck lottery** (noise-only best Sharpe after N tries, drawn from our data) as the lead of Overfitting | Needs our engine and our trial ledger | Competitors show DSR, PBO as numbers [S26, S27]; no source read shows a noise-only comparison as the lead figure. |
| O2 | **Start-date lottery** and **closest call** for every limit | Cheap on our vector engine | Only LuxAlgo's prop card [S11]. |
| O3 | **Survivorship delta card** (same rule, with and without dead companies) | We hold delisted names; most retail tools do not | S18, S21; no retail tool in the 2026 comparison guides read states it as an output [third party guides S33]. |
| O4 | **Actor-aware trial ledger and sealed hold-out** (human, AI helper, MCP agent) with effective N | MCP makes every tool a search engine; nobody found says how it deflates | S23, S24; MCP launches [S2, S7, S9] do not mention it in the pages read ([unverified] absence). TrendSpider's Sidekick "select[s] the top contenders" from backtests [S5, official, 2026-09-30]: the pattern we refuse. |
| O5 | **Verdict power card** (smallest detectable edge, false-positive rate) | Needs our engine to plant signals | S25 is a paper posted 2026-11-14; no product found. |
| O6 | **Screener to strategy in two clicks, point in time, delisted kept, with validation** | Screener ranks already exist in this repo | saral.money describes exactly this gap for NSE and is in open beta [S16, 2026-06-02]. We have the data advantage on US and the Screener advantage on both. |
| O7 | **Reproducible receipt**: hash plus full re-run, not a signed statistic | Server re-runs; browser never sends results | Canli signs statistics [S27]; ours re-runs the whole backtest. |
| O8 | **Same strategy object across blocks, formula, Python, paper** with a deterministic "what it does" paragraph | Already principle 1 | NinjaTrader says reading the generated script is the only check [S4]. |
| O9 | **Live-vs-backtest reconcile as a first-class tab** | Paper uses the identical spec and fills | Only a how-to article found [S17]. |
| O10 | **Data audit as an output** (coverage by year, rows / 252, filing lag) | We own the loader | S19 lists the checks as manual homework. |

---

## 8. Risks and contradictions in the current plan

| # | Where | Problem | Fix |
|---|---|---|---|
| 1 | PLAN §5.3 vs [repo] | States daily 1999 to 2026-01-28; actual 1996-03-18 to 2026-07-06. Hourly "to be measured": 23 tickers, 2023-02-27 to 2026-04-03. | Update the plan; add a daily update job to phase 0; gate Signals and Paper on freshness. |
| 2 | PLAN §5.1 bar magnifier; FEATURES st01 "Fill check" | Depends on hourly data that exists for 23 names. | Mark as conditional; default to the worst-case same-bar rule; Fill check card says "hourly held for 23 names". |
| 3 | PLAN §3.7 "every output has a lead figure or it is cut" vs FEATURES st01 | ~18 outputs; at least five have no lead (rolling, P&L distribution, holding time, exposure, benchmark relation). | Merge per section 4. |
| 4 | PLAN §9 "AI with no human review is out" vs FEATURES G13 agent API | An agent can write, run and iterate with no human in the loop. | Allow agents to build and test; they cannot freeze Paper, certify or open the sealed hold-out beyond the look budget without a human click. (Tactfolio's pattern is similar: the AI cannot switch on live trading, [S13/aistocktradingbots 2026-11-09, third party].) |
| 5 | PLAN §9 "Crypto and forex unless the loader covers them" vs G5 prop firms, G2 FX replay, G8 crypto cost profile | Scope depends on data not yet checked. | Phase 0 decision first; the spec treats these as conditional. |
| 6 | PLAN §5.1 "delisted holdings settle at last close into cash" | Known silent bias (S21). | Add delisting-return setting; print which rule applied; survivorship delta shows the effect. |
| 7 | FEATURES trial counter | Raw count is gameable (near-duplicate trials lower the bar [S24]). | Count effective independent trials; show raw and effective. |
| 8 | FEATURES Verdict "cheapest fix" | Suggests tuning on the verdict. | Section 4 rewrite. |
| 9 | FEATURES §7 TradingView prices "€12.95/€29.95/€59.95/€199.95" | 2026 sources give dollars: monthly $14.95, $34.95, $69.95, $239.95 and annual-billing $12.95, $29.95, $59.95, $199.95 [S31 third party, 2026-11-06]; another source says Premium $49.95 annual [third party, 2026-03-04]. Bars per plan not verified here. | Re-verify on the official pricing page before publishing any price; do not print competitor prices in the product. |
| 10 | FEATURES st01 "(TV) No walk-forward, purged split or OOS report" | One 2026-05-23 guide says Pine v6 Strategy Tester now has walk-forward and Monte Carlo natively [S42, third party, **[unverified]**, contradicts COMPETITORS]. | Check TradingView's release notes before claiming "nobody has it". Do not use competitor gaps as copy until verified. |
| 11 | FRONTEND §2 five new hero kinds vs REUSE "add a fan kind" | REUSE undercounts work. | Count heatmap, tiles, fan, gauge, grade as five shared components in phase 1 estimates. |
| 12 | PLAN phases: phone last | Daily-check users (Live > Today, alerts) are phone users. No usage data read either way [unverified]. | Live page designed phone-first; the rest stays desktop. |
| 13 | Budgets | 500 names × 10 years < 5 s cold and 1,000-cell sweep < 10 s are targets with no baseline; Manifold-BT claims 500,000 backtests in seconds on Rust [S29, vendor, 2026-08-29]. | Spike in phase 0 reports measured speed before budgets are promised in the UI. |
| 14 | Hold-out "last 20% held out by default" vs Backtest showing the full period | The user sees the hold-out in the equity curve on the first run, which burns it. | Default Backtest shows development period only; hold-out opens in Validate with a logged look. |
| 15 | OPEN_SOURCE: `arch` licence unverified, OpenBB conflict, Pyodide | Already in checklist "Decisions for the owner". | Keep as is. |
| 16 | Competitor strategy: Tactfolio, QuantMage, Composer all use **long-only daily** and 0.05% costs [S13] | We do more; the risk is shipping more than a retail user can read. | The default Backtest view is the honest order with five numbers; everything else is a tab. |

---

## 9. Research log

Search tool: TinyFish `search` (web), 2025-06-01 cutoff on current items. About 40 queries; about 30 pages fetched; 5 fetches blocked (Product Hunt ×4, SSRN), so those are cited from search snippets.

Queries run (abbreviated):

1. AI trading strategy builder launch no-code backtest 2026
2. best backtesting software 2026 comparison features retail traders missing
3. QuantConnect new features 2026 changelog Mia AI backtest
4. TradingView Pine Script new feature 2026 strategy tester update
5. Streak Zerodha Tradetron Sensibull algo backtest India retail traders want features 2026
6. backtest results don't match live trading frustration what I wish my backtesting tool had
7. prop firm traders backtesting tool features drawdown rules challenge simulator 2026
8. Hacker News Show HN backtesting platform trading strategy 2026
9. Product Hunt trading backtest launch 2026 strategy validation overfitting
10. TradingView Premium plan price 2026 deep backtesting replay limits
11. Composer trade pricing 2026 plans AI backtest symphonies
12. backtest tear sheet design best visualization strategy report 2026
13. forward testing paper trading strategy decay live vs backtest tracker 2026
14. trading journal features traders pay for 2026 Tradervue TradeZella Edgewonk
15. Stochastly deflated Sharpe probability of overfitting prop-firm node editor
16. retail traders want "wish" survivorship bias delisted point-in-time complaint 2026
17. Tactfolio AI-compatible MCP trading strategies launch
18. Canli Validation MCP signed receipt deflated Sharpe minimum track record
19. QuantProof backtest grade overfitting profit concentration alpha decay
20. I backtested 100+ retail trading strategies placebo delisted execution
21. AlgoTest pricing 2026 features backtest forward test India options
22. QuantMage vs Composer vs Portfolio Visualizer 2026
23. TradingView alerts webhook limits plan 2026 TradersPost PineConnector
24. StrategyQuant X 2026 new version features
25. Build Alpha 2026 new features robustness tests
26. LuxAlgo Vela backtest viewer tabs
27. Trade Ideas OddsMaker TrendSpider Sidekick top contenders
28. backtest alerts email push strategy signal fires without broker
29. Statistical Power of Backtest Validation Pipelines planted-signal
30. in-loop deflation autonomous strategy discovery AI agents overfit
31. Moomoo / Alpaca / IBKR strategy builder 2026
32. QuantConnect complaints learning curve slow backtests review 2026
33. TradingView strategy tester limitations repainting bar magnifier complaints 2026
34. STT brokerage India backtest realistic costs NSE
35. strategy explanation plain English AI explains why backtest failed
36. backtest sharing verified track record leaderboard Quantopian lesson
37. backtesting UI command palette keyboard trading research tool design

Pages read in full or in part: S1-S7, S10 (via search snippets), S11, S12, S13, S16-S23, S27 (listing), S33, S50. Repo: PLAN, FEATURES_AND_OUTPUTS, FRONTEND, CHECKLIST, REUSE, OPEN_SOURCE (head), COMPETITORS (headings), `backend/data/market_universe*.parquet` (read with pyarrow: row counts, date min/max, ticker counts).

Not verified: Reddit threads beyond one fetch (S18) and search snippets; Product Hunt pages (blocked); competitor prices other than those in S13 and S31; TradingView's own release notes; PineTS licence; Quantprove demo visuals; whether phones dominate any user group; F&O STT change; any claim that a competitor "lacks" a feature (absence cannot be proved from search).

### Source list

| Id | URL | Date | Mark |
|---|---|---|---|
| S1 | https://quantconnect.com/announcements/19846/your-ai-quant-developer | 2025-12-19 | official |
| S2 | https://quantconnect.com/announcements/21675/remote-mcp-for-quantconnect | 2026-11-03 | official |
| S3 | https://www.quantconnect.com/docs/v2/ai-assistance/agent-teams | 2026-09-09 | official (snippet) |
| S4 | https://ninjatrader.com/futures/blogs/build-trading-strategy-with-ai | 2026-09-22 | official |
| S5 | https://trendspider.com/blog/sidekick-ai-strategy-builder | 2026-09-30 | official (snippet) |
| S6 | https://trendspider.com/blog/group-strategy-tester/ | 2026-07-22 | official |
| S7 | https://strategyquant.com/blog/ai-can-now-control-strategyquant-x-meet-the-new-era-of-algorithmic-trading | 2026-10-27 | official |
| S8 | https://www.facebook.com/strategyquantcom/posts/strategyquant-x-build-144-dev-1-is-finally-here-and-its-a-big-onethis-update-int/2106941370129324/ | undated | official (snippet) |
| S9 | https://x.com/buildalpha/status/2121242958796145102/video/1 | 2026-11-13 | official (snippet) |
| S10 | https://buildalpha.com/software-update-v3 ; https://buildalpha.com/robustness-testing-guide ; https://buildalpha.com/variance-test | 2026-01-28 ; 2026-01-17 ; 2026-10-25 | official |
| S11 | https://luxalgo.com/blog/your-backtest-now-shows-which-prop-firm-challenges-it-passes | 2026-10-23 | official |
| S12 | https://luxalgo.com/blog/backtests-now-show-alternative-outcomes | 2026-09-18 | official |
| S13 | https://tactfolio.com/about/facts | 2026-10-16 (prices 2026-11-02) | official |
| S14 | https://globenewswire.com/news-release/2026/11/06/3397856/0/en/tactfolio-inc-launches-ai-compatible-platform-for-building-backtesting-and-automating-trading-strategies.html | 2026-11-06 | official (snippet) |
| S15 | https://tactfolio.com/docs/mcp | 2026-10-28 | official (snippet) |
| S16 | https://saral.money/blog/indian-algo-tooling-gap | 2026-06-02 | third party (written by a competitor) |
| S17 | https://tradetron.tech/blog/nine-reasons-your-backtest-doesnt-match-live-trading | 2026-09-08 | official |
| S18 | https://reddit.com/r/algotrading/comments/1x2owmo/i_backtested_100_retail_trading_strategies_700 | 2026-10-10 | unverified (single poster) |
| S19 | https://whatworksintrading.substack.com/p/i-audited-two-years-of-my-own-backtests | 2026-11-09 | third party |
| S20 | https://cbailey.uk/trading/how-i-test | 2026-09 | third party |
| S21 | https://algoseek.com/blog/data-guides/survivorship-bias-in-backtesting-what-to-ask-a-data-vendor/ | 2026-08-27 | third party (data vendor) |
| S22 | https://quandora.gitbook.io/en/paper-trade-a-strategy/paper-trading-and-monitoring | 2026-10-17 | official |
| S23 | https://arxiv.org/abs/2611.04070v1 | 2026-11-02 | third party (preprint) |
| S24 | https://arxiv.org/pdf/2611.14539 | 2026-11-13 | third party (preprint, snippet) |
| S25 | https://ssrn.com/abstract=7687365 | 2026-11-09 to 2026-11-14 | third party (snippet; fetch blocked) |
| S26 | https://producthunt.com/p/stochastly/stochastly ; https://stochastly.com/what-is-stochastly | 2026-10-05 ; 2026-10-18 | official (vendor, snippet) |
| S27 | https://glama.ai/mcp/servers/arhancanli/canli-validation-mcp/tools/audit_backtest ; https://producthunt.com/products/canli-validation | 2026-10-07 ; 2026-09-26 | third party listing / vendor |
| S28 | https://producthunt.com/products/grade-algo-validation ; https://quantprove.com/backtest | 2026-03-10 ; 2026-10-29 | official (vendor, snippet) |
| S29 | https://producthunt.com/p/manifold-bt/manifold-bt | 2026-08-29 | official (vendor, snippet) |
| S30 | https://producthunt.com/p/strategy-optimizer-for-tradingview/strategy-optimizer-for-tradingview | 2026-09-05 | official (vendor, snippet) |
| S31 | https://www.quantvps.com/blog/tradingview-pricing ; https://strategyarena.io/en/blog/plan-tradingview-pour-backtester-2026 | 2026-11-06 ; 2026-10-17 | third party |
| S32 | https://blog.traderspost.io/article/automate-tradingview-remix ; https://blog.pickmytrade.trade/tradingview-plan-you-need-for-webhook-automated-trading | 2026-09-16 ; 2026-07-21 | third party |
| S33 | https://thedtterminal.com/guides/best-backtesting-software-2026 | 2026-09-10 | third party |
| S34 | https://tradezella.com/blog/best-trading-journal-software | 2026-07-13 | third party (competitor-authored) |
| S35 | https://aioindicator.com/blog/tradingview-strategy-backtest-settings-commission-slippage | 2026-11-01 | third party (snippet) |
| S36 | https://fortraders.com/blog/tradingview-backtesting | 2026-10-18 | third party (snippet) |
| S37 | https://stockmarketstack.com/tools/composer ; https://help.composer.trade/article/78-slippage-and-fees | 2026-09-13 ; 2026-09-02 | third party ; official (snippet) |
| S38 | https://quantpower.tech/best-algo-trading-platform-india | 2026-11-06 | third party |
| S40 | https://aliceblueonline.com/blog/how-to-backtest-trading-strategy-steps-data-results | 2026-10-21 | third party (snippet) |
| S42 | https://iatraderpro.com/en/pine-script-v6-tradingview-2026-update-guide | 2026-05-23 | unverified |
| S44 | https://luxalgo.com/blog/luxalgo-charting-platform ; https://github.com/luxalgo | 2026-08-31 ; 2026-10-13 | official (snippet) |
| S45 | https://thegodfunded.com/en/news/goatfundedtrader-launches-prop-challenge-backtesting-with-real-firm-rules | 2026-08-14 | third party (snippet) |
| S47 | https://reddit.com/r/algotrading/comments/1rhjlzk/backtesting_study | 2026-03-01 | unverified (snippet) |
| S48 | https://www.newtrading.io/quantconnect-review | 2026-03-13 | third party (snippet) |
| S49 | https://tradezella.com/blog/ai-backtesting | 2026-07-07 | third party (competitor-authored, snippet) |
| S50 | https://davemabe.com/a-backtest-with-and-without-delisted-stocks | 2026-06-02 | third party |
