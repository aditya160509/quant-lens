# Studio competitors, November 2026

Researched 2026-11-15 with TinyFish search and fetch. Dates on sources are as read in this pass.

## Marks

- **[official]** read on the vendor page, docs or repo today.
- **[third party]** review site, forum or blog.
- **[unverified]** not confirmed. Also used where a page was empty or blocked. Never a guess.
- `?` in the matrix means unverified, not absent.

## Summary

| # | Product | Type | Price read today | Main lesson for us |
|---|---|---|---|---|
| 1 | TradingView | Charts + Pine strategies | Yes [official] | Bar magnifier, deep backtest, Pine as a familiar language |
| 2 | QuantConnect | Cloud IDE, LEAN engine | Tiers yes, $ no | Full report PDF, research notebooks |
| 3 | Composer | No-code symphonies + broker | Not read | AI writes the strategy from plain English |
| 4 | Portfolio123 | Ranking + screen backtests | Not read | Ranking systems, rolling tests, optimiser |
| 5 | TrendSpider | Charts + auto-trendlines + tester | Tiers only | Drawing automation on charts |
| 6 | StrategyQuant X | Strategy generator | Yes [official] | Cross-checks and walk-forward matrix |
| 7 | Build Alpha | Robustness suite | Yes [official] | 16+ named robustness tests, plain statements |
| 8 | WealthLab 8 | C# strategy designer | Partly [official] | Optimiser and C# designer |
| 9 | AmiBroker | Desktop, AFL | Yes [official] | Built-in walk-forward mode with IS and OOS equity |
| 10 | MultiCharts | Desktop, EasyLanguage/PowerLanguage | Partly [third party] | Portfolio Trader: test whole portfolios |
| 11 | NinjaTrader | Desktop futures | Software $ not read | Monte Carlo and optimiser inside the Strategy Analyzer |
| 12 | TradeStation | Broker + SPR | Commissions only [official] | 100+ report fields, tabbed report |
| 13 | Tradetron | Algo builder, India | Yes [official] | Build, backtest and run live from one place |
| 14 | Streak (Zerodha) | No-code, India | Not read | Scanner and backtest for Indian retail |
| 15 | Option Alpha | Options bots | Pro plan yes [official] | Turn a backtest into a bot in one step |
| 16 | Surmount | Automated investing | Not read | Strategy library linked to a brokerage |
| 17 | Quantpedia | Research library + tools | Partner prices [official] | Strategy library with pre-tested ideas |
| 18 | QuantRocket | Python research stack | Not read | Data and Zipline-based research |

---

## 1. TradingView (Pine Script)

- **Source:** https://www.tradingview.com/pricing/ [official]; Bar Magnifier blog https://tradingview.com/blog/en/accurate-backtesting-with-bar-magnifier-31746 [official]; Deep Backtesting help https://tradingview.com/support/solutions/43000666265-how-deep-backtesting-works [official]; Pine strategies docs https://www.tradingview.com/pine-script-docs/concepts/strategies/ [official].

**Price tiers [official]:** Free $0. Paid tiers at special prices of $12.95, $29.95, $59.95 and $199.95 per month (annual saving shown). Alert counts rise by tier (20, 100, 400, 1,000 price alerts).

**How a strategy is built:** Pine Script `strategy()` declaration. It sets capital, commission, slippage, pyramiding, margin, order size and close-execution defaults. Users override them in the Properties tab.

**Fill and cost model:**
- Commission and slippage are inputs in `strategy()`, not hidden in the engine [official].
- Bar Magnifier (premium) uses lower-timeframe bars to order intrabar fills. The blog gives a table of intrabar timeframe per chart timeframe and an example where results fell about 50% with it on [official].
- `process_orders_on_close`, `calc_on_every_tick` and `calc_on_order_fills` are `strategy()` settings [official]. The default fill timing for each is **[unverified]** in this pass.

**Reports and outputs:** Strategy Tester tabs (Overview, List of trades, Properties), exported trade list. Field definitions are on a help page not extracted in this pass. Field list **[unverified]**.

**Robustness and validation:** Deep Backtesting keeps every closed trade and does not trim orders; results show only in the Strategy Report tab, not on the chart [official]. No walk-forward, Monte Carlo or CPCV built in **[unverified]**.

**Optimisation:** Input-based parameter tuning exists **[unverified]** in this pass.

**Paper and live:** Alerts run on TradingView servers; broker connections via brokers that support TradingView (**[unverified]** list).

**Users praise:** Chart quality, Pine as a common language, public scripts. **[unverified]** review sources not read this pass.

**Users complain:** Proprietary language, limits on alerts by tier, backtests that look better than live. **[unverified]** (earlier research note cites third-party reviews; not re-read).

**Steal for us:**
1. Show the fill model as settings the user can read and change (commission, slippage, order-on-close).
2. Offer an intrabar refinement toggle, with a clear note of how much results move.
3. Keep every closed trade in a deep-test mode, so the report never silently trims.

---

## 2. QuantConnect (LEAN)

- **Source:** https://www.quantconnect.com/pricing/ [official]; LEAN report tutorial https://www.quantconnect.com/tutorials/open-source/lean-report-creator [official]; LEAN licence https://github.com/QuantConnect/Lean/blob/master/LICENSE [official, Apache-2.0 via GitHub API].

**Price tiers [official]:** Free Plan, Researcher, Team, Trading Firm, Institution. Dollar amounts were not in the rendered page text: **[unverified]**.

**Free plan [official]:** equities, indexes, forex, crypto, futures and options data; unlimited cloud backtesting; community support.

**Researcher [official]:** local coding (VS Code and CLI), expanded data, up to 2 compute nodes, basic AI automation.

**Team [official]:** project collaboration, up to 10 compute nodes, larger logs and file limits.

**Trading Firm and Institution [official]:** unlimited nodes, permissions, on-premises platform, FIX brokers, AES-256 code encryption.

**How a strategy is built:** code in Python or C#. Cloud IDE and local CLI.

**Fill and cost model:** LEAN engine. Fill and fee models are code-level, not in the UI **[unverified]** in this pass.

**Reports and outputs:** Backtest PDF report on the Researcher tier and up [official via earlier read]. LEAN CLI can generate a local report with `lean report` **[unverified]** flags.

**Robustness and validation:** Not a built-in suite in what was read **[unverified]**.

**Optimisation:** Parameter optimisation in cloud (**[unverified]** details).

**Paper and live:** LEAN live trading with supported brokers, paid tiers **[unverified]**.

**Users praise:** Open-source engine, cloud data, scale. **[unverified]** review sources.

**Users complain:** Heavy setup for local runs, code-first, plan limits (log size, node count). Plan limits are [official].

**Steal for us:**
1. A one-page PDF of each backtest, generated from the same run data as the UI.
2. Plan limits shown as visible numbers (logs, nodes, imports), not hidden caps.

---

## 3. Composer (composer.trade)

- **Source:** https://composer.trade [official]; https://composer.trade/pricing [official page, no prices extracted]; help article https://help.composer.trade/article/55-discover-tutorial [official].

**Price tiers:** Page says "no subscription needed to start" [official]. Fee schedule **[unverified]**.

**How a strategy is built:** "symphony" built from a natural-language prompt with an AI-assisted editor, or by hand. Page shows a generated example with cumulative return, annualised return, trailing 3-month return and Sharpe ratio, against a benchmark [official].

**Fill and cost model:** "No commissions on trades"; other fees per schedule [official]. Fill model **[unverified]**.

**Reports and outputs:** Cumulative return, annualised return, trailing 3-month return, Sharpe ratio, benchmark comparison [official, from product page]. Full list **[unverified]**.

**Robustness and validation:** Not read **[unverified]**.

**Optimisation:** Not read **[unverified]**.

**Paper and live:** Composer is a brokerage (Composer Securities LLC, executed through Alpaca Securities and Apex Clearing) [official]. Live execution is automatic rebalancing.

**Users praise:** Plain-English strategy creation, pre-built and community strategies [official claims]. Review sources **[unverified]**.

**Users complain:** Not read **[unverified]**.

**Steal for us:**
1. Plain English to an editable formula, validated by our parser, with the same stats card shown beside the prompt.
2. A community tab where users can copy a strategy and see its original backtest.

---

## 4. Portfolio123

- **Source:** https://www.portfolio123.com/pricing [official, prices not in rendered text]; feature list on the same page [official]; ranking system help https://help.portfolio123.com/hc/en-us/articles/360016347131-Stock-ETFs-Ranking-System [official].

**Price tiers:** Plan names and prices not extracted: **[unverified]**. Designer Models are sold by designers, and P123 keeps no subscription for them. Designers keep 65% of revenue [official].

**How a strategy is built:** Universe, then ranking system (factors, weights), then screen rules, then simulation (buy and sell rules, position count, rebalancing). Also books (combined simulations), short and hedged screens [official].

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs:** Stock Pages, Rebalance X-Ray (per-stock reasons for each buy and sell), Fundamental and Macro charts, Stock Compare [official]. Simulation metrics list **[unverified]**.

**Robustness and validation:** Rolling Screen Backtests (run a screen every week or four weeks for a holding period) and Rolling Tests (overlapping start and end dates) [official]. CPCV, deflated Sharpe: **[unverified]**.

**Optimisation:** Optimizer re-runs a simulation with varied parameters; limited by the plan's optimizer combinations [official].

**Paper and live:** Live strategies run in real time; can link Interactive Brokers accounts for orders [official].

**Users praise:** Large point-in-time fundamentals (4,300+ factors and 430+ functions) [official]. Review sources **[unverified]**.

**Users complain:** Learning curve, plan limits (resource units, combinations) [official limit list]. Review sources **[unverified]**.

**Steal for us:**
1. Rolling tests: the same rule run at many start dates, shown as a spread.
2. Rebalance X-Ray: for each rebalance, show why each stock was picked and why others were not.
3. Show every plan limit as a visible unit, as P123 does.

---

## 5. TrendSpider

- **Source:** https://trendspider.com/pricing [official]; strategy tester help https://help.trendspider.com/kb/strategy-tester/understanding-strategy-tester-from-trendspider [official].

**Price tiers [official]:** Standard, Enhanced, Advanced, Premium. The pricing page shows Black Friday promotional prices and bonuses. List monthly prices are **[unverified]**.

**How a strategy is built:** No-code strategy tester on automated trendlines and indicators [official, page title "strategy tester"]. Builder details **[unverified]**.

**Fill and cost model:** Extended-hours support was added to the tester per a product post [official blog, date unverified].

**Reports and outputs:** Strategy tester help exists [official]. Field list **[unverified]**.

**Robustness and validation:** Not read **[unverified]**.

**Optimisation:** Not read **[unverified]**.

**Paper and live:** Not read **[unverified]**.

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. Automatic drawing of the levels a strategy uses onto the chart (levels as drawing objects, not just text).
2. Tier names with feature lists, shown beside the same metric.

---

## 6. StrategyQuant X (SQ X)

- **Source:** https://strategyquant.com/pricing [official]; features https://strategyquant.com/features [official]; Walk-Forward Matrix https://strategyquant.com/doc-new/walk-forward-matrix [official]; cross-checks https://strategyquant.com/doc/strategyquant/cross-checks-automated-strategy-robustness-tests [official].

**Price tiers [official, partial read]:** Lifetime licence sold as a one-time price or as monthly payments for 12 months, then lifetime. Top tier read as "Ultimate": one-time $2,900 (struck from $4,900), or $290 per month for 12 months (struck from $420). Other tiers: $1,490 one-time (from $1,790) and $1,290 (from $1,290 shown with a monthly plan) **[unverified mapping of names to prices]**.

**How a strategy is built:** SQ X generates strategies from building blocks, then tests them. Users can also write their own in its editor **[official features page, partial]**.

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs:** Walk-Forward Matrix report (a grid of walk-forward optimisations with different re-optimisation periods and OOS lengths) [official]. Full report list **[unverified]**. Market and volume profile, Results AI plugin, lifetime support and upgrades listed on pricing [official].

**Robustness and validation:** Cross-checks run automatically: Monte Carlo trade manipulation (re-orders and resamples existing trades) and Monte Carlo retest (each run is a new backtest with small variations), plus tests on other markets [official]. Walk-Forward Matrix [official].

**Optimisation:** Genetic and brute-force generator and optimiser **[unverified]** in this pass.

**Paper and live:** Not read **[unverified]**.

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. A Walk-Forward Matrix: a grid over re-optimisation period and OOS length, showing where a strategy holds up.
2. Cross-checks that run on other markets as a separate test, shown as their own row.
3. Monte Carlo split into two kinds: reorder existing trades, and rerun with small changes.

---

## 7. Build Alpha

- **Source:** https://buildalpha.com/licensing-new [official]; robustness guide https://buildalpha.com/robustness-testing-guide [official].

**Price tiers [official]:** Starter $497 one-time, or $49 per month (upgrade to Lifetime $1,197). Pro $997 one-time, or $197 per year (upgrade to Lifetime $697). Lifetime $1,497 (struck from $2,497).

**How a strategy is built:** Strategy generation and testing on its own platform **[unverified]** for builder details.

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs:** Not read in full **[unverified]**.

**Robustness and validation [official guide]:** 16+ tests, grouped:
- Data split: in-sample / out-of-sample, randomised out-of-sample, walk-forward.
- Edge vs luck: vs random (best random strategy as benchmark), Monte Carlo permutation test (MCPT), noise test versus MCPT.
- Alternate price paths: noise test, vs shifted (shifted data), vs other related markets, synthetic stress tests.
- Trade-list Monte Carlo: reshuffle and resample, randomised exits, variance testing.

**Optimisation:** Not read **[unverified]**.

**Paper and live:** Not read **[unverified]**.

**Users praise / complain:** Not researched this pass **[unverified]**. Forum claims are not used.

**Steal for us:**
1. A named list of robustness tests, each with one plain sentence on what it checks and a pass or fail.
2. Noise test: add noise to prices and rerun; show the spread of outcomes.
3. Vs shifted: shift the data in time and rerun; a real edge should degrade.

---

## 8. WealthLab 8

- **Source:** https://wealthlab.azurewebsites.net/Software/SubscriptionPlans [official]; features https://wealthlab.azurewebsites.net/Software/Features [official, short page].

**Price tiers [official, partial]:** Subscription $49.95 per month or $399.95 per year (Premium plan; a second plan at $499.95 per year). Lifetime licence $1,595, includes two years of free maintenance. A $149.95 item was on the page; its name is **[unverified]**.

**How a strategy is built:** C# strategy designer with building blocks, optimiser, portfolio backtests [official features page; detail not extracted, so list is **[unverified]**].

**Fill and cost model:** Stated costs per trade are mentioned in a third-party review **[third party, stockmarketstack.com]**.

**Reports and outputs:** Not read in full **[unverified]**.

**Robustness and validation:** Not read **[unverified]**.

**Optimisation:** Optimiser exists **[official]**; method list **[unverified]**.

**Paper and live:** Not read **[unverified]**.

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. Lifetime plus maintenance pricing as a clear option beside monthly.
2. Strategy designer that compiles code without running it (a check step before a run). Third-party source only, so treat as an idea.

---

## 9. AmiBroker

- **Source:** https://www.amibroker.com/order.html [official]; walk-forward guide https://amibroker.com/guide/h_walkforward.html [official]; report guide https://amibroker.com/guide/h_report.html (search result, not read in full).

**Price tiers [official, partial]:** Standard Edition $299 (new single-user licence), includes 24 months of free upgrades and maintenance. Other editions and bundles on the same page.

**How a strategy is built:** AFL (AmiBroker Formula Language) code. Exploration, backtest and optimise from the same formula.

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs:** Backtest report; a walk-forward out-of-sample summary report for all OOS steps (new in version 5.60) [official]. Full list **[unverified]**.

**Robustness and validation [official]:** Automatic walk-forward mode (version 5.10). Optimise on an in-sample segment, test on the next out-of-sample segment, repeat over time. Combined in-sample and out-of-sample equity lines are available through the `~~~ISEQUITY` and `~~~OSEQUITY` composite tickers. The guide notes the IS and OOS equity is scaled to keep continuity, and it assumes compounding.

**Optimisation:** Built in with walk-forward; custom criteria per the forum **[third party]**.

**Paper and live:** Not read **[unverified]**.

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. Show IS and OOS equity on one chart, with the stitched OOS line as the headline.
2. An OOS summary report that covers every OOS step, not just the last.

---

## 10. MultiCharts

- **Source:** https://multicharts.com/features/portfolio-trading [official]; https://multicharts.com/purchase [official, partial]; pricing https://www.multicharts.com/pricing [bot-blocked, not read]; plan prices from https://stockmarketstack.com/tools/multicharts [third party].

**Price tiers [third party]:** Standard $99 per month, $79 per month billed yearly, or $1,499 once. Advanced $149 per month (other figures **[unverified]**). Switching between MultiCharts and MultiCharts x .NET editions costs a one-time $200 fee [official].

**How a strategy is built:** EasyLanguage / PowerLanguage style code. Portfolio Trader builds a portfolio from many instruments (100s of stocks, futures and other instruments) [official].

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs:** Not read **[unverified]**.

**Robustness and validation:** Not read **[unverified]**.

**Optimisation:** Not read **[unverified]**.

**Paper and live:** Live auto-trading through supported brokers [official feature page, partial].

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. Portfolio Trader: simulate a whole portfolio of instruments in one run, not one symbol at a time.

---

## 11. NinjaTrader

- **Source:** Monte Carlo help https://ninjatrader.com/support/helpguides/nt8/monte_carlo_simulation.htm [official]; optimise help https://ninjatrader.com/support/helpguides/nt8/optimize_a_strategy.htm [official]; pricing https://ninjatrader.com/pricing [official, commissions only].

**Price tiers:** Software tiers not extracted **[unverified]**. Published page shows commissions (for example $0.39 to $1.29 per contract for micro and standard futures) and day trading margin [official].

**How a strategy is built:** NinjaScript (C#) strategies in the Strategy Analyzer [official, NT8 help].

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs:** Strategy Analyzer reports; Monte Carlo display in the report drop-down [official]. Full list **[unverified]**.

**Robustness and validation [official]:** Monte Carlo randomises trade results and runs them through many simulations to show the probability of outcomes, including whether the strategy risks wiping out the account before it turns a profit.

**Optimisation [official]:** Optimise a strategy from the Strategy Analyzer. Method list (for example brute force or genetic) and objectives **[unverified]** in this pass.

**Paper and live:** Simulation and live through NinjaTrader brokerage **[unverified]** details.

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. Monte Carlo answer in plain terms: "chance of losing X% before profit", not only a chart.
2. Put Monte Carlo as a display mode of the same report, not a separate page.

---

## 12. TradeStation

- **Source:** Strategy Performance Report help https://help.tradestation.com/10_00/eng/tradestationhelp/subsystems/spr_topics/spr/strategy_performance_report_tabs_and_fields.htm [official]; pricing https://www.tradestation.com/pricing [official, commissions].

**Price tiers:** Volume-based commissions and fees on the pricing page [official]. Software plan prices **[unverified]**.

**How a strategy is built:** EasyLanguage strategies on TradeStation charts [official, SPR help context].

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs [official]:** Strategy Performance Report with over 100 fields, in tabs: Performance Summary, Trade Analysis, Trades List, Periodical Returns (and others). Tab names read; full field list **[unverified]**.

**Robustness and validation:** Not read **[unverified]**.

**Optimisation:** Not read **[unverified]**.

**Paper and live:** Paper trading and live through TradeStation **[unverified]** in this pass.

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. Tab layout for the report (Summary, Trade Analysis, Trades List, Periodical Returns).
2. Trades List as a table we can sort and export.

---

## 13. Tradetron

- **Source:** https://tradetron.tech/pricing [official]; backtest page https://tradetron.tech/pages/backtest [official, marketing text only].

**Price tiers [official]:**

| Tier | Monthly | Yearly |
|---|---|---|
| Free | $0 (build and run in Live Offline, free for life) | n/a |
| Starter | $13/mo | $150/yr (save 16%) |
| Retail | $42/mo | $500/yr (save 16%) |
| Retail+ | $83/mo | $990/yr (save 17%) |
| Creator | $249/mo | $2,990/yr (save 16%) |

(Monthly and yearly figures read from the pricing text; the page calls out Retail as "Best value".)

**How a strategy is built:** Visual and code-based strategy builder [official, pricing page and backtest page]. Details **[unverified]**.

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs:** Backtest results **[unverified]** field list.

**Robustness and validation:** Not read **[unverified]**.

**Optimisation:** Not read **[unverified]**.

**Paper and live:** Build and run in Live Offline (free); live trading needs a paid plan and a user's own broker account [official].

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. Free tier that runs live offline (paper) to show value before payment.
2. Plan table with monthly and yearly prices side by side and the saving stated.

---

## 14. Streak (Zerodha)

- **Source:** https://streak.zerodha.com/ [official]; Zerodha Z-Connect announcements https://zerodha.com/z-connect/streak [official]; help https://help.streak.zerodha.com [search snippet only, fetch failed].

**Price tiers:** Not read **[unverified]**. Zerodha announcement says Streak Unlimited is open to all Zerodha users [official, announcement].

**How a strategy is built:** No-code technical strategies, scanners and backtests on Indian markets [official, product page]. Builder details **[unverified]**.

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs:** Not read **[unverified]**.

**Robustness and validation:** Not read **[unverified]**.

**Optimisation:** Not read **[unverified]**.

**Paper and live:** Live orders and virtual (paper) deployment on the product page [official]. A help snippet mentions a 7-day trial and backtesting of up to 50 items **[unverified]** (snippet not read in full).

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. A scanner that uses the same rule as the backtest, so a result on the scanner matches the backtest.

---

## 15. Option Alpha

- **Source:** https://optionalpha.com/pricing [official]; backtesting docs https://docs.optionalpha.com/tools/backtesting [official].

**Price tiers [official, partial]:** Pro $99 per month with annual billing, or $149 monthly. A free tier exists; its limits are on the pricing page with a $10k minimum balance mentioned **[unverified mapping]**.

**How a strategy is built:** Options bot builder with entry and exit criteria, position settings and technical indicators [official docs].

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs [official]:** Performance history, detailed trade log for every trade, combined portfolio curve from several backtests.

**Robustness and validation:** Compare and combine several backtest variations to stress-test settings [official]. Named tests **[unverified]**.

**Optimisation:** Variation testing across multiple backtests [official]. Automatic optimiser **[unverified]**.

**Paper and live:** Turn any backtest into a bot that trades the same rules [official].

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. One click from a backtest to a paper bot with the same rules and the same trade log.
2. Combine several backtests into one portfolio curve.

---

## 16. Surmount

- **Source:** https://surmount.ai/pricing [official]; strategies https://surmount.ai/strategies [official].

**Price tiers [official, partial]:** Plans shown with monthly prices. Exact plan names and prices not cleanly extracted **[unverified]**. Plan rules: "1 external account (including paper trading)" on the lower plan and "up to 3 external accounts" on the next [official].

**How a strategy is built:** Browse and invest in pre-built automated strategies; users can backtest them [official, strategy and backtest pages].

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs:** Not read **[unverified]**.

**Robustness and validation:** Not read **[unverified]**.

**Optimisation:** Not read **[unverified]**.

**Paper and live:** Paper trading through a linked external account [official]; live trading through Alpaca and other connected accounts [official].

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. Plan limits as "accounts linked" and "paper included", shown in plain words.

---

## 17. Quantpedia

- **Source:** https://quantpedia.com/links-tools/backtesting-software [official]; https://quantpedia.com/pricing [official page, prices not extracted].

**Price tiers:** Own plan prices not extracted **[unverified]**. Partner pricing for StrategyQuant X on the Quantpedia tools page [official]: Starter $99 per month shown as $89 (partner); Professional $125 as $112; Ultimate $245 as $220; Free Limited Access free. Those are Quantpedia's partner prices, not StrategyQuant's list prices.

**How a strategy is built:** It is a research library of published strategies with links to tools, not a builder **[official, page description]**.

**Fill and cost model:** Not applicable.

**Reports and outputs:** Not applicable.

**Robustness and validation:** Not read **[unverified]**.

**Optimisation:** Not applicable.

**Paper and live:** Links to brokers and backtest tools; not an execution product **[official, partial]**.

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. A library of ready strategy ideas that a user can load into Studio as a starting point.

---

## 18. QuantRocket

- **Source:** https://www.quantrocket.com/pricing/ [official page, prices not extracted]; https://support.quantrocket.com/t/moonshot-vs-zipline/1821 (search snippet).

**Price tiers:** Not extracted **[unverified]**.

**How a strategy is built:** Python research in Jupyter, with Moonshot (a Zipline-based backtester) [official support thread, snippet].

**Fill and cost model:** Not read **[unverified]**.

**Reports and outputs:** Not read **[unverified]**.

**Robustness and validation:** Not read **[unverified]**.

**Optimisation:** Not read **[unverified]**.

**Paper and live:** Live trading through supported brokers **[unverified]**.

**Users praise / complain:** Not researched this pass **[unverified]**.

**Steal for us:**
1. Data and backtest run kept as separate steps (fetch once, backtest many times).

---

## Feature matrix

Legend: ✓ yes, ✗ no, partial, ? unverified (not read today).

| Feature | TV | QC | Composer | P123 | TrendSp | SQ X | Build Alpha | WL8 | AmiBroker | MultiCh | NinjaTr | TradeSt | Tradetron | Streak | Opt Alpha | Surmount | Quantpedia | QuantRocket |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| No-code builder | partial | ✗ | ✓ | partial | ✓ | partial | ? | ✗ | ✗ | ✗ | ✗ | ✗ | partial | ✓ | ✓ | ✓ | ✗ | ✗ |
| Code (own language) | ✓ Pine | ✓ Py/C# | ✗ | ✗ | ✗ | partial | ? | ✓ C# | ✓ AFL | ✓ EL | ✓ C# | ✓ EL | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ Py |
| AI writes strategy | ? | ? | ✓ | ✗ | ? | ✓ | ? | ? | ✗ | ✗ | ✗ | ✗ | ? | ? | ✗ | ✗ | ✗ | ✗ |
| Intrabar fill refinement | ✓ bar magnifier | ? | ? | ? | ✗ | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ✗ | ✗ | ? |
| Deep / all-trade backtest | ✓ | ? | ? | ? | ? | ? | ? | ? | ? | ? | ✓ | ✓ | ? | ? | ✓ | ? | ✗ | ? |
| Walk-forward | ✗ | ? | ✗ | partial (rolling) | ✗ | ✓ matrix | ✓ | ? | ✓ | ? | ? | ? | ? | ? | ✗ | ✗ | ✗ | ? |
| Monte Carlo | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Noise / shifted-data test | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| CPCV | ✗ | ? | ✗ | ? | ✗ | ? | ? | ? | ? | ? | ? | ? | ? | ? | ✗ | ✗ | ✗ | ? |
| Deflated Sharpe | ✗ | ? | ✗ | ? | ✗ | ? | ? | ? | ? | ? | ? | ? | ? | ? | ✗ | ✗ | ✗ | ? |
| Parameter sensitivity / heatmap | ? | ? | ✗ | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ? | ✗ | ✗ | ? |
| Regime split | ✗ | ? | ✗ | ✗ | ✗ | ? | ? | ? | ? | ? | ? | ? | ? | ? | ✗ | ✗ | ✗ | ? |
| Optimiser | partial (inputs) | ✓ | ✗ | ✓ | ? | ? | ? | ? | ✓ | ✓ | ✓ | ? | ? | ? | partial (variations) | ✗ | ✗ | ? |
| Tearsheet / PDF | ✗ | ✓ | ✗ | ✗ | ✗ | ? | ? | ? | ? | ? | ? | ✓ | ? | ? | ✓ | ✗ | ✗ | ? |
| Paper trading | partial (replay, alerts) | ? | ✗ | ✓ | ✓ | ? | ? | ? | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ? |
| Live trading | ✓ (brokers) | ✓ | ✓ | ✓ | ✓ | ? | ? | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Public sharing / community | ✓ | ✓ | ✓ | ✓ | ✗ | ? | ? | ✗ | ✗ | ✗ | ✗ | ✗ | ? | ✗ | ✗ | ✓ | ✗ | ✗ |

Notes on the matrix:
- TV "paper" is replay and alerts, not a full paper account [official docs, partial].
- Cells changed to ? where the claim was not read in this pass (for example sensitivity heatmaps, tearsheets for AmiBroker, NinjaTrader and WealthLab).
- Entries marked ✓ rest on pages read in this pass. Entries marked ? are unknown, not no.

---

## What nobody does well (our opening)

Based on what was read today, the gaps are:

1. **One validation verdict, in plain words, with each test's cost shown.** Build Alpha has the most named tests, and SQ X has cross-checks and a walk-forward matrix. None of the pages read here show one verdict card that combines walk-forward, Monte Carlo, CPCV, deflated Sharpe and sensitivity, with the cost and fill assumptions printed beside it.
2. **Unknowns stay unknown.** No page read today marks a missing metric as "not computed" with a reason. Our rule "unknown stays unknown" is a gap to fill.
3. **Fill and cost model shown as settings in the report.** TradingView does this in code and inputs. Most others do not show the model next to the numbers.
4. **Charts, drawing tools and backtest in one browser surface, with export to code and data.** TradingView is closest, but its strategies are Pine-only and not portable. AmiBroker and NinjaTrader are desktop. Composer and Surmount do not show charts with drawn levels.
5. **Paper trading on the same engine as the backtest, with a live diff.** Option Alpha does one-click bots; the diff between backtest and paper is not shown on pages read today.
6. **Plain-English strategy writing that is checked by a real parser.** Composer does plain English, but its output is not shown to be validated against a formal grammar **[unverified]**.

Gaps 1, 3 and 5 are the strongest openings. Gap 2 is cheap to build and easy to explain.

---

## Second pass (added 2026-11-15): five more products

Read with TinyFish search and fetch (MCP tools, with `after_date` 2025-06-01 for pricing). Vendor pages are marked [official]; comparison and review pages are [third party].

### 19. Trade Ideas (OddsMaker)

- **Source:** https://www.trade-ideas.com/pricing/ [official]; https://trade-ideas.com/features/backtesting/ [official, linked from search].

**Price tiers [official]:** TI Standard $127/mo or $1,068/yr (promo $89/mo shown). TI Premium $254/mo or $2,136/yr (promo $178/mo shown). Free account on delayed data.

**Where backtesting sits [official]:** OddsMaker is on TI Premium only. It backtests a formula or alert across all stocks with no code. Standard has paper trading and the Formula Editor.

**How a strategy is built:** Formula or alert, then OddsMaker replays past events. Multi-day holds can exit at the future close or future open [official, marketing page].

**Reports and outputs:** Trades, win rate and profit factor [official, comparison page].

**Robustness and validation:** Not read [unverified].

**Optimisation:** Not read [unverified].

**Paper and live:** Paper trading on Standard. Live through in-app brokerage [official].

**Users praise / complain:** Not researched this pass [unverified].

**Steal for us:** Replay a rule across a whole universe, not only one chart. Show win rate and profit factor next to trade count.

### 20. TradeZella

- **Source:** https://help.tradezella.com/en/articles/8911582-our-pricing [official]; https://tradezella.com/blog/is-tradezella-a-backtesting-tool [official blog, search snippet].

**Price tiers [official]:** three tiers at $35, $59 and $99 per month; annual billing $26, $44 and $74 per month. Trade Replay: 10 replays per month on the lowest tier, unlimited above. 1-second replay chart on the higher tiers.

**How a strategy is built:** Backtesting is manual bar-by-bar, or automated with no code. 11+ years of data across stocks, forex, futures and crypto [official blog].

**Reports and outputs:** Journal, replay of executed trades, pre-trade checklist [official blog].

**Robustness and validation:** Not read [unverified].

**Optimisation:** Not read [unverified].

**Paper and live:** Journal of live trades. Paper mode not confirmed [unverified].

**Users praise / complain:** Complaint on price ("no free plan", $35 to $99 a month) [third party, thegodfunded.com review].

**Steal for us:** Replay the user's own trades bar by bar. Tie a checklist to each strategy.

### 21. FX Replay

- **Source:** https://support.fxreplay.com/articles/what-are-the-differences-between-fx-replay-plans-and-their-pricing [official]; https://fxreplay.com/playbooks/education/top-backtesting-software-for-forex-traders-a-comprehensive-guide [official, search snippet].

**Price tiers [official]:** Free (core backtesting workflow). Intermediate $17.99/mo or $180/yr. Higher tier $35/mo or $350/yr (unlimited sessions and seconds-level data).

**How a strategy is built:** Bar-by-bar replay of historical forex and other data, with simulated trades. Built-in analytics and CSV import [official].

**Reports and outputs:** Analytics dashboard, export and sharing of analytics on the higher tier [official].

**Robustness and validation:** Not read [unverified].

**Optimisation:** Not read [unverified].

**Paper and live:** Simulated trades only. No live execution claim read [unverified].

**Users praise / complain:** Not researched this pass [unverified].

**Steal for us:** Free tier that covers the core workflow, with paid tiers for depth. Replay as a way to check each signal by eye.

### 22. Forex Tester

- **Status:** not researched in this pass. No vendor page or review fetched. All facts [unverified].

**Steal for us:** [unverified] until read.

### 23. MetaTrader 5 Strategy Tester

- **Source:** https://www.metatrader5.com/en/terminal/help/algotrading/strategy_optimization [official]; release notes and MCP/AI pages [official, search snippets].

**Price:** Included with the free MetaTrader 5 terminal [official, terminal help; price line not re-read this pass, so **[unverified]** on exact terms].

**How a strategy is built:** MQL5 Expert Advisors. Optimisation runs over many parameter sets, with the criterion chosen by the user [official].

**Reports and outputs:** Optimisation results tab and forward results tab, both comparable [official].

**Robustness and validation [official]:** Forward optimisation: the data is split into an optimisation period and a forward period (a half, a third, a quarter, or a custom start date). The best runs are re-run on the forward period to test for overfitting. Forward testing mode is also available.

**Optimisation [official]:** Parallel optimisation through local agents; genetic and other modes **[unverified]** on exact list.

**Paper and live:** Live trading in the same terminal [official]. AI assistant can configure and launch tests (2026 release notes) [official].

**Users praise / complain:** Not researched this pass [unverified].

**Steal for us:** Forward split inside the optimiser: optimise on one part, rerun the top results on the rest, and show both side by side.

### Matrix rows for second-pass products

| Feature | Trade Ideas | TradeZella | FX Replay | Forex Tester | MT5 tester |
|---|---|---|---|---|---|
| No-code builder | ✓ (OddsMaker) | ✓ (automated, no code) | ✗ | ? | ✗ (MQL5 code) |
| Code | partial (formula editor) | ✗ | partial (FXR Script) | ? | ✓ MQL5 |
| Bar replay | ✗ | ✓ | ✓ | ? | ✓ visual test |
| Walk-forward / forward | ✗ | ? | ? | ? | ✓ forward optimisation |
| Monte Carlo | ✗ | ✗ | ✗ | ? | ✗ |
| Optimiser | ? | ? | ? | ? | ✓ |
| Paper trading | ✓ (Standard) | ? | ✓ (simulated) | ? | ✓ (demo accounts) |
| Live trading | ✓ (brokerage) | ✗ | ✗ | ? | ✓ |

Only the rows marked ✓ or ✗ above were read in this pass. Others are unknown.

---

## Third pass (2026-11-15, TinyFish MCP): what users praise, complain about and ask for

Read today on the pages named. These replace the **[unverified]** praise and complaint lines above where they overlap.

| Product | Complaint or limit | Praise | Source |
|---|---|---|---|
| TradingView | Short loaded history on intraday (one regime); when stop and target sit in one bar the tester assumes a path that can favour the target; repainting scripts run without warning; one symbol per script, no portfolio; no walk-forward, purged split or OOS report; free tier shows no Sharpe, Sortino, MFE/MAE or regimes, no parameter loop | Best charting; Pine is the friendliest way to state a rule; entries and exits visible on the bar | wiseapple.com/compare/tradingview-strategy-tester-limits (2026-08) [third party]; codertrader.com 2026-08 [third party]; fortraders.com/blog/tradingview-backtesting (2026-10) [third party] |
| QuantConnect | IDE "minimum viable product", files fail to save, projects break after platform updates; learning curve of platform syntax; 512 MB on the free node | Data included (US equities from 1998, options from 2012); unattended live trading; full report | trustpilot.com/review/quantconnect.com (2026-03); newtrading.io/quantconnect-review (2026-03); thedtterminal.com (2026-09) [third party] |
| QuantConnect report (what it contains) | — | Key stats (runtime, turnover, CAGR, markets, trades per day, drawdown, **PSR**, Sharpe, information ratio, **strategy capacity**); returns per trade histogram, daily, monthly heatmap, annual with average line, cumulative vs benchmark; asset allocation; drawdown; rolling 6M and 12M beta and Sharpe; leverage; long-short exposure by asset class; **crisis events** (17 named periods from DotCom 2000 to AI Boom 2022–present); parameters; PDF | quantconnect.com/docs/v2/cloud-platform/backtesting/report [official] |
| Composer | Backtests use the daily close but live trades at 3:50 PM: "backtests massively inflated"; execution timing near the close is a paid upgrade; thinks in weights and rebalances, not trade rules on one stock; no read-only mode (must move money to its broker); "Trade with AI" ranks community strategies by past results (an overfitting machine); AI output "thin", a dual-momentum strategy lagged its backtest by 3–4 points a year | Unlimited free backtests; build and live in one editor; documentation says backtests "benefit from hindsight" | reddit r/ComposerTrade (2025-05, snippet); agenttrading.ai/blog/composer-trade-review (2026-09); wallstreetdebug.com (2026-10) [third party] |
| Composer price | Starter $0 (1 automated strategy, 200 nodes, unlimited backtests); Advanced $10/mo (5, 350 nodes); Pro $32/mo billed yearly ($384); Business quote (15,000 nodes, "full IP ownership") | | agenttrading.ai 2026-09 [third party, quoting pricing page] |
| TrendSpider | Pricey, no free plan (14-day paid trial from $19); AI sidekick extra; complicated | No-code tester with costs, **variance testing**, multi-symbol tests, AI backtesting, forward testing; auto trendlines and patterns, legend says "Not found on this chart" for patterns it looked for; seasonality view; multi-timeframe on one chart | stockresearchhub.com/reviews/trendspider (2026-11); stockbrokers.com (2025-08) [third party] |
| StrategyQuant X | Mass generation is data mining by design; most generated strategies fail live (Forex Peace Army reviewers); $1,290–$2,900; no live trading; weak bundled equities data (Yahoo EOD) | Deep robustness battery; careful fill arithmetic per trigger mode; responsive support | backtestscore.com/tools/strategyquant (2026-08) [third party] |
| Build Alpha | Focused on generation; needs expertise to read results; Windows only | 7,000+ signals; 12–16 named robustness tests (vs random, MCPT, noise, vs shifted, vs others, delay, liquidity, variance); auto-kills curve-fit strategies; suggests improvements to saved strategies | agenttrading.ai/blog/build-alpha-review (2026-10); buildalpha.com/robustness-testing-guide [official] |
| Portfolio123 | Users asked for: limit-order simulation, real short simulations with **borrow cost** and dividends, **long-short in one sim**, **portfolio of portfolios**, taxes | Point-in-time simulation infrastructure | community.portfolio123.com feature poll [third party, old thread] |
| Generic (r/FxBacktest 2026-09 top answer) | "Show the trade list, not just the summary… whether a single trade carried the result"; fills against the bar, not the close on thin names; **point-in-time universe with delisted and renamed symbols**; "let the same config run live without editing it" | | reddit.com/r/FxBacktest (2026-09) [third party] |

### What this adds to "What nobody does well"

7. **No tool shows whether one trade carried the result.** Users ask for it by name.
8. **Repaint and look-ahead are the user's problem everywhere.** No tool runs a truncation check that proves a signal never changes after the fact.
9. **Backtest and live disagree on timing** (Composer close vs 3:50 PM; TradingView same-bar path). Nobody prints the fill timing beside the result and uses the same timing in paper.
10. **AI ranks by past results.** Every "AI strategy" product sorts by backtest. Nobody counts the trials and deflates the Sharpe for them.

## Fourth pass (2026-11-15): what each paid tier sells

| Product | Tiers and what the money buys | Source |
|---|---|---|
| TradingView | Basic €0 (5,000 bars, 2 indicators/chart, 20 s Pine time); Essential €12.95 (10,000, 5); Plus €29.95 (10,000, 10); Premium €59.95 (20,000, 25, Deep Backtesting: 2M bars / 1M trades, seconds replay); Ultimate €199.95 (40,000, 50, 100 s) | strategyarena.io 2026-10 [third party, read on tradingview.com]; kagels-trading.com 2026-09 |
| TrendSpider | Standard, Premium, Enhanced, Advanced: same features, limits differ. Enhanced: 1-min backtests 20K depth, 250 symbols per test; 2-hr 2K depth, 50 symbols. Add-on: 20K depth for Standard/Premium $39/mo. Standard from $54/mo; 14-day trial from $19 | trendspider.com/pricing [official]; stockresearchhub.com 2026-11 |
| QuantConnect | Free (unlimited backtests, 1 node, no live, no paper); Researcher $84/mo (tick and second data, LEAN CLI, API, PDF report); Team $168/user; Trading Firm $480/user; Institution $1,272/user | stockmarketstack.com 2026-10; cryptomarkets.tools 2026-09 [third party] |
| Portfolio123 | $300, $1,000, $1,500, $2,400 a year (or $35–$278/mo); custom ranking systems and simulations from the $1,000 Backtest plan (10 years); 20 years PIT on higher plans; AI Factor on Portfolio/Ultimate | stockmarketstack.com 2026-10; findmymoat.com 2026-09 [third party] |
| Option Alpha | Pro $149/mo or $99/mo yearly: 50 bots, $100k per bot, unlimited backtests; free through partner brokers | stockmarketstack.com 2026-10; optionalpha.com [official] |
| StrategyQuant X | Professional $1,490 one-time (advanced robustness, optimiser, Portfolio Master for 4 strategies); Ultimate $2,900 | backtestscore.com 2026-08 [third party] |

### What tear-sheet readers and live traders ask for (added to features)

- Read the fine print, drawdown, monthly table without the best months, skew, rolling Sharpe and beta before the equity curve; write walk-away conditions before opening the report (datapigtechnologies.com 2026-08).
- Telling decay from bad luck: Sharpe standard error ≈ 1/√years, so three months of live P&L catches a dead edge 18% of the time; check costs (gross vs net) and the signal's IC first; keep a shadow book of retired strategies (halleytech.substack.com 2026-09).
- "Can you open individual trades on a chart? Can you save and rerun the exact setup? Can you watch paper signals before real capital?" (backtest.click 2026-07 checklist).
