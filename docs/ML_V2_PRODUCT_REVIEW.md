# ML V2 product review: what to build, cut and polish (2026-10-05)

Status marks: `[x]` done and verified · `[~]` in part · `[ ]` open.

This is a hard review of the Machine learning module (`/ml`, 12 features), written in the same format as `RESEARCH_PRODUCT_REVIEW_FINAL_BATCH.md`. It has five parts: the verdict, what to add, what to remove or merge, UI work, and inputs.

Inputs for the review:
- every ML page built and run this session on real data
- `docs/ML_V2_OUTPUTS_PLAN.md` and `docs/ML_V2_MAX_PASS.md`
- the competitor screenshots: QuantConnect, Koyfin, TradingView, Portfolio Visualizer, TradeStation
- practitioner discussion on r/quant and r/algotrading (2026 threads on ML validity, AI hype, overfitting, regime filters and volatility forecasting)
- QuantConnect's pricing page, and recent validation work on spurious predictability and multi-seed instability

Tags: **[B]** backend or external · **[F]** frontend · **[B+F]** both.

---

## 0. Verdict: is the module worth it?

**Yes, if it is sold as "ML you can trust", not "AI that picks stocks".** The demand evidence points in one direction:

- **People can build models; they can't tell whether they're real.** From r/algotrading: "the hard part isnt building signals but figuring out if theyre real in the first place." And: "every beautiful backtest (Sharpe 4+) was a bug… AI helps you fail faster."
- **Failures are plumbing, not technique.** One practitioner: "my actual failures were never technique, they were plumbing… one unfiltered data path leaking future info." Their rule is to treat every backtest as "guilty until independently reproduced".
- **Black boxes are distrusted.** Platforms leading with "AI selects the best stocks" are called "a black-box regression with a slick UI". The proposed test: "remove the word AI from the copy; if the pitch falls apart, it's branding."
- **Where ML is known to work** is narrower than the marketing:
  - volatility forecasting (HAR and GJR-GARCH beat EWMA out of sample)
  - meta-labelling past trades ("I've personally had luck using ML for predicting volatility and conducting metalabelling")
  - regime filters, with honest controls
  - feature ranking with gradient boosting

  Directional ML alpha is weak, around 56% precision at best.
- **Validation has moved past one backtest.** The new bar is:
  - multi-seed stability: picking the best of 20 seeds inflated Sharpe by 44%
  - a full log of the search, because the trial count changes the bar
  - controls: "compare your filter against always-long over the same periods"; a constant-exposure control beat two signal rules
  - parameter plateaus ("smooth decay vs a cliff")

**Our position is already right.** Purged CPCV, purged chronological splits, train-only preprocessing, forward-only regime filtering, honest "unavailable" states and conditional rather than causal language are exactly what the skeptics ask for. No retail or prosumer product shows the purge, the embargo and the provenance.

**The pitch:** "Machine learning that shows its work: every split purged, every number reproducible, every claim checked against a control."

What stops it being worth paying for today:
1. **It's 12 separate tools, not one workflow.** Users want to go from idea to validated to sized to monitored. There are no hand-offs between features (Alpha → Barriers → Allocation, Regimes → Volatility).
2. **No controls or stability checks.** There are no null or always-long baselines, no multi-seed runs and no parameter plateaus. These are the checks practitioners now demand.
3. **Nothing is live.** There's no daily refresh of the ranking, regime, vol forecast or pair z-score, and no alerts. Subscriptions are paid for things that update.
4. **You can't bring your own model or features.** No custom features (the Research formula language exists but isn't connected), no uploaded predictions, no "validate my strategy's returns".
5. **No search log is shared with Research.** ML trials don't count in the project ledger, so a deflated Sharpe here would be dishonest.

---

## A. Features to add (ranked by demand × how different it makes us)

### A1. Validation as the product (the core, and the money)
1. `[ ]` **[B+F] "Validate my strategy": bring your own returns or predictions.**
   - Upload a dated returns series, or predictions plus labels, and get:
     - CPCV paths
     - PBO from your trial matrix
     - deflated Sharpe at the real trial count
     - a minimum backtest length
     - a one-page verdict like the Research report card
   - This is the highest-demand item: it serves people who build models anywhere (QuantConnect, notebooks, TradingView) and makes us the referee, not a competitor.
2. `[ ]` **[B] Controls on every backtest.** Equal-weight universe, buy-and-hold, constant-exposure (same average exposure, no signal), and a permuted signal (shuffled labels). The verdict says whether the strategy beats its controls, not just zero.
3. `[ ]` **[B+F] Multi-seed stability.** Rerun stochastic models (GBM, sequence models, HMM initialisations) over N seeds. Show the distribution of IC and Sharpe, and flag when the best seed exceeds the median by more than X%.
4. `[ ]` **[B+F] Parameter plateau map.** Sweep the one or two most important settings (horizon, barrier width, entry z, lookback) and show a heatmap. Plateaus read as robust; cliffs read as fragile. The Dock already has a sweep, so this needs a backend batch endpoint.
5. `[ ]` **[B] Leakage audit.** Perturb all data after date *t*, rerun, and assert that outputs at *t* are unchanged. Report pass or fail per feature. The tests already do this; expose it as a product feature with a badge on every result.
6. `[ ]` **[B+F] A shared trial ledger with Research.** Every ML run is a trial in the active project, so deflated Sharpe and PBO use the true count across both modules.
7. `[ ]` **[B+F] Reproducibility receipt.** A result hash covering data version, code version, settings and seed, plus a "rerun exactly" button and an export of the run manifest.

### A2. One workflow instead of twelve tools
8. `[ ]` **[B+F] Pipeline hand-offs** (artifact ids):
   - Alpha predictions → Barriers (primary side), Allocation (views) and Composite (as a factor)
   - Regimes → Volatility (regime-conditioned models) and Averaging (regime-conditional weights)
   - Microstructure signals → Composite and Alpha (as features)
9. `[ ]` **[B] Regime-switching volatility.** Use the regime to pick or weight the forecast model, following the evidence that HAR wins in calm markets and GJR-GARCH wins in stress. This is a concrete, proven improvement.
10. `[ ]` **[B+F] Volatility-targeted sizing.** Turn the vol forecast into position sizes for any backtest, with a rebalance buffer to stop "fee bleed".
11. `[ ]` **[F] Strategy studio:** one page that chains signal (Alpha or Composite), filter (Regime), sizing (vol target or meta-label probability), portfolio (HRP) and costs, then validates the whole chain with A1.

### A3. Live and monitored (what subscriptions pay for)
12. `[ ]` **[B] Daily refresh jobs** for: the ranking (F02), current regime (F06), vol forecasts (F03), live pair z-scores (F09) and composite scores (F08).
13. `[ ]` **[B+F] Alerts:** regime change, a z-score crossing entry or exit, a vol spike above forecast, a ranking change in the top N. Delivered by email, webhook or in-app.
14. `[ ]` **[B+F] Model monitoring:**
    - feature drift per input (Wasserstein distance against the training window)
    - rolling live IC against backtest IC
    - "retrain recommended" when drift or IC decay crosses a threshold
15. `[ ]` **[F] Watchlist dashboard:** the ML overview becomes a live board with the current regime, top 10 names, vol forecasts for a watchlist, the open pair and the latest verdicts.

### A4. Bring your own inputs
16. `[ ]` **[B+F] Custom features from the Research formula language** (`rank(ts_mean(...))`). Alpha, Composite and Averaging can use them as inputs. Reuse `signal_lang`.
17. `[ ]` **[B] Upload a feature panel** (date, ticker, features) or predictions, validated for dates and point-in-time.
18. `[ ]` **[B] Universe presets** from the Research universes API: sectors, regions, ETFs, crypto (on its own 7-day calendar, kept separate), high volatility, and "same as last run".
19. `[ ]` **[B] Macro features with vintages** (ALFRED/FRED vintages) so macro inputs are point-in-time. Currently excluded for good reason; vintages make them honest.

### A5. Data integrity (shown, not just done)
20. `[ ]` **[B+F] Provenance on every result:** train and test windows, purge and embargo, universe, and missing-data share. One chip per result, with details on click.
21. `[ ]` **[B] Calendar-aware panels.** Align multi-asset data to one exchange calendar and state how missing days were handled. The default-universe bug this session came from mixed calendars.
22. `[ ]` **[B] Corporate-action and total-return check:** flag series that look unadjusted (gaps the size of a split).

### A6. Money features `[ ]` (sequence after A1–A3)
23. **[B+F] Tiers:**
    - **Free:** 3 features with delayed data and the default universe.
    - **Pro, about $29–49/month:** all features, custom universes, daily refresh and alerts.
    - **Research, about $99/month:** "Validate my strategy" uploads, multi-seed, plateau maps, exports and API.

    QuantConnect anchors this market with a free tier, "Quant Researcher" and team tiers, and add-ons for data. Our differentiator is validation, not compute.
24. **[F] Share a validated result** as a read-only link or embed. This is already built for Research; extend it to ML.
25. **[B] Credits for heavy jobs** (sequence models, large universes, multi-seed), the way QuantConnect meters compute.

---

## B. Remove, merge or demote (bloat)

Rule: keep what practitioners report as useful, and fold niche methods into the features they serve.

| Feature | Verdict | Why |
|---|---|---|
| F01 CPCV | **Keep, and generalise into A1** | This is the core trust story. Its CPCV and PBO overlap Research's walk-forward/CPCV validation, so share one engine. |
| F02 Alpha model | **Keep** | Ranking plus SHAP is the most-used view. Make GBM the default and keep linear as the baseline. |
| F03 Volatility | **Keep, and promote** | The strongest evidence that ML helps. Add A9 and A10. |
| F04 Triple barrier and meta-labelling | **Keep** | Practitioners use meta-labelling. Reframe it as "size and filter my trades", not as labels. |
| F05 HRP allocation | **Keep** | A known, valued method. Black–Litterman stays expert-level (no views means no effect). |
| F06 Regimes | **Keep, and make it a shared input** | High demand for filters. Feed it into F03, F07 and any backtest as a filter (A8). |
| F07 Model averaging (DMA/OBS) | **Merge into F02** as an "Ensemble weighting" tab | Niche on its own. It answers "which model to trust now", which is a question about F02's models. |
| F08 Composite signal | **Keep** | The practical signal-combination tool. It also receives F10 signals and custom features. |
| F09 Pairs | **Keep** | Long-standing demand. Needs top-N pairs, not one (C, below). |
| F10 Microstructure | **Merge into F08** as signal families, with the cross-section kept as a tab | Daily proxies without tick data are weak alone; as composite inputs they're useful. |
| F11 Factor associations (DML) | **Move to Research** (Factor zoo / Causal) | It is factor-validation research, it overlaps Research's spanning and factor-zoo tests, and its "not causal" caveat confuses ML users. |
| F12 Sequence models | **Demote to Labs / Expert** | Rarely beats GBM on daily cross-sections, slow (about 30 seconds), and invites hype. Keep it as "do deep models beat GBM here?" with multi-seed results. |

**Result:** 12 features become 8 pages a user can name: Validate, Alpha, Volatility, Trade sizing, Allocation, Regimes, Composite, Pairs, plus Labs.

Also remove:
- `[ ]` Duplicate chart and table payloads (F07 and F10 results are about 3 MB). Send one table and let the view-as menu draw it.
- `[ ]` Black–Litterman outputs when no views are given. They currently show "no change", which is noise.
- `[ ]` Raw `training_audit` tables once provenance chips (A20) exist.
- `[ ]` Inputs that rarely change (garch_fit_cap, some solver settings). Move them to Expert.

---

## C. UI and frontend

### C1. Make each output best in class (detail in `ML_V2_MAX_PASS.md` §A)
- `[ ]` A one-line reading under every card, from templates (no AI).
- `[ ]` Axis titles and units on every chart. Percent for returns, vol and weights.
- `[ ]` Benchmarks and controls drawn on every equity curve (A2).
- `[ ]` Dense charts collapse: matrices above 20 names group into clusters, line charts show the top 6, the beeswarm shows the top 12.

### C2. Interaction
- `[ ]` Clicking a name in the ranking shows its SHAP waterfall.
- `[ ]` Clicking a pair in the leaderboard or network loads that pair (backend: top-N pair series).
- `[ ]` Hovering a regime highlights those dates across the page, with a "shade regimes" toggle on every time series.
- `[ ]` Clicking a barrier-surface cell reruns with that profit-taking/stop-loss pair; clicking a CPCV split highlights it on the path fan.

### C3. Workflow surfaces
- `[ ]` **Strategy studio** (A11) as a page of its own.
- `[ ]` **ML compare:** two runs side by side on IC, Sharpe, drawdown and coverage, with the differences highlighted.
- `[ ]` **Live overview board** (A15).
- `[ ]` **"Send to…" menu on outputs** (A8): send predictions to Barriers, Allocation or Composite.

### C4. Polish and coverage
- `[ ]` A visual pass against the competitor screenshots: density, 8 px grid, one accent colour, equal hero heights.
- `[ ]` Light theme on every page. Fix the e2e light snapshots, which render dark.
- `[ ]` Phone width from 360 px.
- `[ ]` ML wording everywhere: "Train and test" instead of "Run study", ML empty states, and the API's stage names in progress.
- `[ ]` Loading skeletons shaped like each chart.

### C5. Known issues
- `[ ]` The default universe is fixed at 35 names. Add presets (A18).
- `[ ]` F12 defaults to one architecture. Run two by default, multi-seed (A3).
- `[ ]` Pairs only ever shows one pair (C2).

---

## E. Inputs

- **Levels:** Quick shows only universe, horizon and lookback. Standard adds the model and costs. Expert holds everything else. Most inputs belong in Expert.
- **Presets per feature,** taken from the literature, with a citation:
  - "AFML defaults": purge 5, embargo 1%, CPCV with 6 groups and 2 test groups
  - "Corsi HAR"
  - "Lopez de Prado HRP"
- **Universe:** presets (A18), "same as last run", and a validated custom list showing unknown and calendar-mismatched names.
- **Guard rails:** warn before a run that will be slow (sequence models, large universes) or underpowered (too few dates for the horizon plus embargo). The backend already raises; show it before submission using `/validate`.
- **Settings link and presets saved per user.** This exists in Research and applies here unchanged.

---

## D. Order to build

1. **A1.2 controls, A1.5 leakage badge, A20 provenance, C1 readings.** These make every existing result more convincing, for the least work.
2. **B merges:** F07 into F02, F10 into F08, F11 to Research, F12 to Labs. Do this before adding features, so new work lands on the final page set.
3. **A1.1 "Validate my strategy", A1.3 multi-seed, A1.4 plateau map, A1.6 shared ledger.** The paid core.
4. **A2 pipeline hand-offs and the Strategy studio, plus A9 and A10 vol improvements.**
5. **A3 live refresh, alerts and monitoring, plus the live overview.** The subscription value.
6. **A4 bring-your-own inputs, and A6 tiers and sharing.**

## Sources (2026 practitioner discussion and references)

- r/algotrading on signal validation: "the hard part isnt building signals but figuring out if theyre real" (thread on systematic crypto validation, May 2026).
- r/algotrading on where AI helps versus branding, including "every beautiful backtest (Sharpe 4+) was a bug… AI helps you fail faster" and a meta-labelling plus volatility report (June 2026).
- r/quant on research books: "my actual failures were never technique, they were plumbing" (July 2026).
- r/algotrading on regime filters versus always-long and constant-exposure controls, and parameter plateaus (September 2026).
- "How to Validate Financial ML Beyond Accuracy and Backtests", HackerNoon, September 2026: multi-seed Sharpe inflation of 44%, turnover dispersion, spurious predictability.
- Rebellion Research, "Overfitting in Financial ML" and "Preventing overfitting", October 2026: logging every trial, chronological splits, purge and embargo.
- Regime and volatility evidence: GitHub `ArkaKhorchidian/Regime-Detection-Volatility-Forecasting` (HAR-RV best overall, GJR-GARCH best in stress; forward-filtered HMM) and `wisdomgu/regim` (permutation-tested regime signals).
- QuantConnect pricing (quantconnect.com/pricing): tiered plans with data add-ons and metered AI and compute.
