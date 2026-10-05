# ML V2 product review: research, scores and plan (2026-10-05, v2)

Status marks: `[x]` done and verified · `[~]` in part · `[ ]` open. Tags: **[B]** backend or external · **[F]** frontend · **[B+F]** both.

This review covers the Machine learning module at `/ml` (12 features). It replaces the first version from earlier today, adding:
- a competitor matrix with prices
- a per-method evidence table from the academic replication literature
- a scored feature table
- product principles drawn from competitor reviews

Several first-pass recommendations changed because the evidence did not support them; they are marked **(changed)**.

> **Final decision: see §13.** Every feature we keep must score 5 on every axis. Anything that can't get there is removed, including heavy infrastructure that doesn't pay for itself. §13 overrides §5–§7 and §11 where they differ.

---

## Contents
1. Method and criteria
2. Verdict
3. Market and competitor matrix
4. Evidence per method (does it work out of sample?)
5. Scored feature table (keep, merge, demote)
6. What to add
7. What to remove or merge
8. UI and experience
9. Inputs
10. Pricing and business model
11. Build order
12. Sources

---

## 1. Method and criteria

About 25 searches (Exa) across Reddit (r/quant, r/algotrading), the academic replication literature, competitor pricing pages, Trustpilot reviews and GitHub. Each feature and proposal was scored on 34 criteria in eight groups:

| Group | Criteria |
|---|---|
| A. Demand | How often the pain comes up, who has it, current workaround, willingness to pay, open-source interest (GitHub stars and downloads) |
| B. Evidence | Academic support, replication, failure modes, whether it works on daily data |
| C. Competition | Feature matrix, prices, complaints in competitor reviews, unclaimed space |
| D. Trust | Leakage protection, overfitting controls, honest output, reproducibility |
| E. User value | Does it change a decision, time to insight, clarity, actionability |
| F. Product and UX | Best-in-class comparison for each screen, visual standard, interaction depth, onboarding |
| G. Business | Recurring value, tier fit, cost to serve, shareability, data and legal |
| H. Engineering | Build cost, maintenance, performance, architecture fit |

The scores in §5 condense these into six columns:
- **Demand**, **Evidence**, **Differentiation** and **Decision value**: 1–5, higher is better.
- **Recurring value**: 1–5, how much reason to come back.
- **Cost**: 1–5, lower is better.

---

## 2. Verdict

**Build it as "the place that kills bad ML ideas cheaply, and shows its work", not as an AI that predicts the market.** The strongest demand signal in the research is a builder's answer on r/algotrading to "what's missing":

> "what actually doesnt exist for normal people is boring validation… out of sample testing by default… monte carlo, testing the same strat on an asset it wasnt tuned on… its all standard at funds and basically nonexistent under $100/mo… dont build another oracle, build the thing that proves ideas wrong. everyone has ideas. nobody has a cheap way to kill the bad ones."

The rest of the evidence agrees:
- **Validation is the hard part.** "the hard part isnt building signals but figuring out if theyre real." And: "every beautiful backtest (Sharpe 4+) was a bug… AI helps you fail faster."
- **Users distrust AI branding**, and competitors' reviews show it. Tickeron: "More than 85% of the AI-generated trades result in losses." Trade Ideas: "you only have 63 days of backtesting available." PortfolioPilot: "Bad advice all dressed up as AI."
- **Where ML genuinely helps is narrow** (§4):
  - nonlinear cross-sectional models (trees beat linear; Gu, Kelly and Xiu)
  - volatility forecasting (HAR and GJR-GARCH)
  - meta-labelling as a filter
  - Ledoit–Wolf shrinkage for allocation

  Weak or failing out of sample:
  - deep sequence models on daily data
  - most liquidity and microstructure anomalies (93% fail replication)
  - volatility-managed portfolios (72 of 103 underperform in real time)
  - HRP against shrinkage

**What we already have that nobody else sells under $100 a month:** purged CPCV, purged chronological splits, training-only preprocessing, forward-only regime filtering, honest "unavailable" states and conditional (not causal) language.

**The closest new competitor** is AgentTrading ($49/month, launched 2026): plain-English rule → backtest → verdict against buy-and-hold. It validates simple rules only, with no ML, no CPCV, no PBO and no multi-seed. That validates the market and shows the gap we fill.

**Pitch:** "Machine learning that shows its work. Every split purged, every result checked against a control, every claim reproducible. We tell you when your model is a bug."

**What blocks paying customers today:**
1. No "validate my strategy or model" input. Users can't bring returns, predictions or features.
2. No controls, multi-seed or plateau checks, which are now the expected bar.
3. 12 disconnected tools instead of one workflow.
4. Nothing live (no refresh, alerts or monitoring), so nothing to subscribe to.
5. Some engines promote methods the evidence doesn't support (§4): deep sequence models, liquidity anomalies, and HRP as the default allocator.

---

## 3. Market and competitor matrix

### 3.1 Prices (checked October 2026)

| Product | What it sells | Price | ML / validation depth |
|---|---|---|---|
| QuantConnect | Code-first backtesting and live trading (LEAN) | Free; Researcher about $10/month; live nodes $20–60+ each | Engine, data and live trading. Validation is up to the user's own code. |
| Portfolio123 | Factor screens, ranking, AI Factor (ML) | Subscription, plus AI training billed per worker hour ($50 credit), plus a Prediction add-on | Real ML on fundamentals (training, hyperparameters, predictions in screens). Validation is basic holdout and walk-forward. |
| Composer | No-code rules and AI strategy builder with execution | Free start; Advanced about $10/month; Pro higher | Rule backtests; no ML validation |
| Tickeron | "AI robots", pattern and trend engines | Robots $90–145/month; tools $20–40 each | Black-box signals; poor reviews |
| Trade Ideas | Real-time scanner, Holly AI | $127/month Standard; $254/month Premium (Holly) | Black-box AI; backtests only 63 days |
| Danelfin | AI Score 1–10 per stock | $29 / $79 / $179 per month | Score track record only; you can't test your own rule |
| AgentTrading | Plain-English idea → backtest → verdict | $49 / $99 / $199 per month (half on yearly) | Simple-rule validation against buy-and-hold; no ML |
| Koyfin | Research terminal and dashboards | $39 / $79; advisors $209–299 | None (charts and data) |
| TradingView | Charts, Pine strategies, alerts | About $15–60/month | Pine backtests; no ML validation |
| Numerai | Data-science tournament on obfuscated data | Free; stake NMR | Scores CORR and MMC on live rounds: real out-of-sample, but on their data only |
| WorldQuant BRAIN | Formula alpha platform; paid consultants | Free | Simulation, fitness and correlation checks for formula alphas |
| Qlib (Microsoft, open source) | ML quant platform | Free; 47k GitHub stars | Strong ML pipelines; code-only; no UI product |

### 3.2 Positioning map

- **Black-box signals** (Tickeron, Trade Ideas, Danelfin): high price, low trust, poor reviews.
- **Engines for coders** (QuantConnect, Qlib): powerful, free or cheap, but validation is do-it-yourself.
- **Simple-rule validators** (AgentTrading, Composer backtests): cheap and friendly, but no ML.
- **Unclaimed: ML validation and an ML workbench with a UI under $100/month.** That's us. Portfolio123's AI Factor is the nearest, but it's fundamentals-only, has metered training costs and shallow validation.

### 3.3 What competitors' reviews teach us (product principles)

From Trustpilot and Reddit complaints about Trade Ideas, Tickeron, Composer, TradingView, PortfolioPilot and QuantVue:
1. **No black boxes.** Every number shows how it was made and what it was trained on.
2. **Long history by default.** "63 days of backtesting… not enough." Default to at least 10 years where data allows.
3. **Honest billing.** The top complaints are trial-to-annual traps and impossible cancellation. Make cancel one click, send reminder emails before renewal, and offer monthly billing.
4. **Support and onboarding inside the product.** "they send you to their YouTube channel." Use guided first runs and explanations on every card.
5. **Modern, fast UI on the web and on Mac.** "software written in the early 2000's", "not suitable for Mac users".
6. **Never trade for the user, and never promise returns.** Every page carries a "historical, not predictive" line.

---

## 4. Evidence per method: does it work out of sample?

Grade: **A** strong and replicated · **B** works with caveats · **C** mixed or fragile · **D** fails replication or rarely beats simple baselines.

| Feature | Method | Evidence | Grade | Implication |
|---|---|---|---|---|
| F01 | CPCV, purging, embargo, PBO, DSR | AFML (López de Prado); Bailey et al. on backtest overfitting; skfolio and purgedcv implementations; standard practice in 2026 guides | **A** (as a validation method) | Make it the core of the product (A1). |
| F02 | Gradient boosting and linear cross-sectional return models, SHAP | Gu, Kelly and Xiu (2020): trees and neural nets beat linear, with monthly stock R² of 0.33–0.40% and value-weighted long-short Sharpe 1.35 vs 0.61 for OLS. Dominant signals are momentum, liquidity and volatility. Qlib with LightGBM is the open-source default. | **A−** (monthly horizon) / **C** (daily) | Keep. Default to a monthly or 21-day horizon, gradient boosting with a linear baseline, and report against an OLS-3 control. |
| F03 | HAR-RV, GARCH, GJR-GARCH vol forecasting | HAR-RV ranks first by QLIKE out of sample; GJR-GARCH wins in high-vol regimes; Diebold–Mariano tests significant against EWMA and GARCH | **A** | Promote. Add regime-switching model choice (A9). |
| F03 → sizing | Vol targeting and vol-managed portfolios | **Cederburg et al. (2020, JFE): across 103 strategies, real-time vol-managed versions underperform unmanaged in 72 of 103.** Moreira–Muir alphas are not implementable. | **C−** | **(changed)** Don't promote vol-targeted sizing as an improvement. Offer it only with a side-by-side control against unmanaged. |
| F04 | Triple-barrier labels and meta-labelling | Joubert (2022, JFDS) framework; Hudson & Thames: out-of-sample precision and risk-adjusted metrics improve (2 strategies, futures); practitioners report using it | **B** (limited evidence base) | Keep, framed as "filter and size my existing trades". Always show the primary strategy beside the meta-filtered one. |
| F05 | HRP, NCO, minimum variance, Black–Litterman | **HRP loses to Ledoit–Wolf minimum variance at almost every sample length in controlled tests**, does not converge, and has higher turnover. A 2026 empirical paper finds no evidence that hierarchical methods beat traditional risk-based portfolios. Its insurance value against naive Markowitz is real. | **C** (HRP) / **A−** (shrinkage minimum variance) | **(changed)** Default allocator: Ledoit–Wolf minimum variance. Show HRP, 1/N and inverse-variance beside it as controls. Keep HRP as an option for short windows. |
| F06 | HMM regimes (forward-filtered) | Regimes line up with 2008, 2020 and 2022; forward-only filtering is required; daily HMM signals are uninformative, emerging at 3–10 day aggregation (permutation-tested); regime-conditioned vol models help in moderate stress; filters often just reduce exposure (beaten by a constant-exposure control) | **B** (as a risk input) / **C** (as a timing signal) | Keep, as an input to volatility and risk. Every regime filter must be shown against a constant-exposure control. |
| F07 | Dynamic model averaging, online simplex weights | Sound theory; niche in practice; little equity evidence | **C** | Merge into F02 as "ensemble weighting". |
| F08 | IC-weighted composite of factors | Standard multi-factor practice; Gu–Kelly–Xiu show combining signals nonlinearly helps; IC-IR weighting is common | **B** | Keep. Add custom features and controls. |
| F09 | Pairs trading (cointegration, Kalman) | Profits declined from 0.86%/month (1962–88) to 0.24% (2003–09) (Do & Faff). The distance method is unprofitable after costs since 2002. Cointegration gives 33 bps/month after costs and works best in turbulence; copula opportunity frequency is stable (Rad et al.). Industry homogeneity and the zero-crossing count add 22 bps/month. | **C+** | Keep, with honest expectations: costs on by default, top-N pairs, industry matching and a zero-crossing filter (A14). |
| F10 | Daily liquidity and microstructure anomalies (Amihud, Roll, Corwin–Schultz, MAX, IVOL, 52-week high) | **Hou, Xue and Zhang: 95 of 102 trading-friction variables (93%) are insignificant** with NYSE breakpoints and value weights, including Amihud, IVOL, MAX and Corwin–Schultz. The Amihud effect weakened after 1997. MAX survives only in a modified form. | **D** (as standalone alphas) | **(changed, stronger)** Demote. Fold into F08 as candidate features, always reported with value weights and NYSE breakpoints. No standalone page. |
| F11 | Double ML conditional factor effects | Sound econometrics (Chernozhukov et al.); it is factor research, not ML trading | **B** (method) / out of scope | Move to Research (Factor zoo and Causal). |
| F12 | PatchTST, iTransformer, LSTM, MLP on daily data | Several 2025–26 studies: gradient boosting and linear models often beat deep models on daily data, and all struggle against naive baselines. Deep models can win on direction at some horizons on single names, with overfitting. | **D** (daily cross-section) | **(confirmed)** Demote to Labs: "do deep models beat gradient boosting here?", multi-seed, with a gradient-boosting control. |

**Cross-cutting evidence:**
- **Multi-seed:** best-of-20 seeds inflated Sharpe by 44% (2026, Journal of Finance and Data Science).
- **Spurious predictability:** significant-looking backtests arise on synthetic data with no signal. Test the whole workflow, not the winner.
- **Plumbing over technique:** leakage bugs dominate real failures.

---

## 5. Scored feature table

Higher is better, except Cost (lower is better). Priority = (Demand × Differentiation × Decision value + Evidence + Recurring) ÷ Cost, rounded.

| # | Item | Demand | Evidence | Diff. | Decision | Recurring | Cost | Priority | Call |
|---|---|---|---|---|---|---|---|---|---|
| A1.1 | Validate my strategy or model (upload returns or predictions) | 5 | 5 | 5 | 5 | 3 | 3 | **44** | Build first |
| A1.2 | Controls on every backtest | 5 | 5 | 4 | 5 | 2 | 2 | **56** | Build first |
| A1.3 | Multi-seed stability | 4 | 5 | 5 | 4 | 2 | 2 | **44** | Build |
| A1.4 | Parameter plateau map | 4 | 4 | 4 | 4 | 2 | 2 | **35** | Build |
| A1.5 | Leakage audit badge | 4 | 5 | 5 | 3 | 1 | 1 | **66** | Build first (tests exist) |
| A1.6 | Shared trial ledger with Research | 3 | 5 | 5 | 3 | 2 | 2 | **26** | Build |
| A1.8 | Transfer test (run on assets and periods not tuned on) | 5 | 5 | 4 | 5 | 1 | 2 | **53** | Build first |
| A1.9 | Monte Carlo and bootstrap of trades and paths | 4 | 4 | 3 | 4 | 1 | 2 | **27** | Build |
| F02 | Alpha model (monthly gradient boosting + SHAP) | 5 | 4 | 3 | 4 | 4 | — | keep | Keep and refocus |
| F03 | Volatility forecasts | 4 | 5 | 3 | 4 | 4 | — | keep | Promote |
| F01 | CPCV | 4 | 5 | 5 | 4 | 2 | — | keep | Generalise into A1 |
| F04 | Meta-labelling | 3 | 3 | 4 | 4 | 3 | — | keep | Reframe as a filter |
| F05 | Allocation (shrinkage minimum variance by default) | 4 | 4 | 2 | 4 | 3 | — | keep | Change the default |
| F06 | Regimes (as a risk input) | 4 | 3 | 3 | 3 | 4 | — | keep | Feed other features |
| F08 | Composite | 4 | 4 | 3 | 4 | 4 | — | keep | Absorb F10 |
| F09 | Pairs | 4 | 2 | 2 | 3 | 4 | — | keep | Honest defaults |
| F07 | DMA/OBS | 2 | 2 | 3 | 2 | 2 | — | merge | Into F02 |
| F10 | Microstructure | 2 | 1 | 2 | 2 | 2 | — | demote | Into F08 |
| F11 | DML | 2 | 4 | 3 | 2 | 1 | — | move | To Research |
| F12 | Sequence models | 3 | 1 | 2 | 1 | 1 | — | demote | To Labs |
| A3 | Live refresh and alerts | 5 | — | 3 | 4 | 5 | 3 | **25** | Build (subscriptions) |
| A2 | Pipeline hand-offs and Strategy studio | 4 | — | 4 | 4 | 3 | 4 | **17** | Build after A1 |
| A4 | Bring your own features (formula language) | 4 | — | 4 | 4 | 3 | 2 | **35** | Build (reuse Research) |

---

## 6. What to add

### A1. Validation as the product (the core, and the money)

1. `[ ]` **[B+F] "Validate my strategy or model".** Upload a dated returns series, or predictions with dates, tickers and outcomes, or trial returns for PBO. The report gives:
   - CPCV paths
   - PBO from the trial matrix
   - deflated Sharpe at the true trial count
   - minimum backtest length
   - comparison with the controls (A1.2)
   - the transfer test (A1.8)
   - a one-page HELD UP / MIXED / FAILED verdict in the style of the Research report card

   This beats AgentTrading because it handles ML models and trial searches, not just simple rules.
2. `[ ]` **[B] Controls on every backtest:**
   - buy-and-hold
   - equal-weight universe
   - constant exposure (same average exposure, no signal)
   - permuted or shuffled signal
   - a model control: OLS on 3 features for alpha models; 1/N and inverse-variance for allocators

   The verdict is measured against the best control, not against zero.
3. `[ ]` **[B+F] Multi-seed stability.** Rerun stochastic fits over N seeds and show the distribution. Flag when the best seed is more than 25% above the median.
4. `[ ]` **[B+F] Parameter plateau map.** Sweep the one or two key settings and show a heatmap; label results as plateau (robust) or cliff (fragile).
5. `[ ]` **[B] Leakage audit badge.** Perturb data after *t* and confirm results at *t* are unchanged. Show the badge on every result.
6. `[ ]` **[B+F] Shared trial ledger with Research,** so the deflated Sharpe and PBO count trials across both modules.
7. `[ ]` **[B+F] Reproducibility receipt:** data, code, settings and seed hash, with a "rerun exactly" button.
8. `[ ]` **[B+F] Transfer test.** Apply the frozen model or rule to other assets, sectors or later periods it wasn't tuned on. (Requested directly on Reddit.)
9. `[ ]` **[B] Monte Carlo:** block-bootstrap the path or trade sequence for a drawdown and Sharpe distribution (`arch.bootstrap.MovingBlockBootstrap`).

### A2. One workflow instead of twelve tools

10. `[ ]` **[B+F] Hand-offs via artifact ids:**
    - Alpha predictions → Meta-label filter, Allocation (views) and Composite (as a factor)
    - Regimes → Volatility and risk
11. `[ ]` **[B] Regime-switching volatility model choice:** HAR-RV in calm regimes, GJR-GARCH in stress, scored against the single-model baseline.
12. `[ ]` **[B+F] Sizing options (with controls):** volatility targeting, meta-label probability and Kelly fraction. Always shown against unmanaged sizing, because of the evidence in §4.
13. `[ ]` **[F] Strategy studio:** signal → filter → sizing → portfolio → costs, then validated with A1.
14. `[ ]` **[B] Pairs upgrades:**
    - top-N pairs, not one
    - industry-homogeneous matching
    - a zero-crossing (reversal frequency) filter
    - costs on by default
    - a copula-based option for stable opportunity frequency

### A3. Live and monitored (what subscriptions pay for)

15. `[ ]` **[B] Daily refresh** of the ranking, regime, vol forecasts, pair z-scores and composite scores.
16. `[ ]` **[B+F] Alerts:** regime change, a z-score crossing, vol above forecast, top-N ranking changes. Email, webhook and in-app.
17. `[ ]` **[B+F] Model monitoring:**
    - per-feature drift (Wasserstein distance against the training window)
    - live IC against backtest IC
    - a "retrain recommended" flag
18. `[ ]` **[F] Live overview board.**

### A4. Bring your own inputs

19. `[ ]` **[B+F] Custom features in the Research formula language** (reuse `signal_lang`).
20. `[ ]` **[B] Upload feature panels and predictions,** with date and point-in-time validation.
21. `[ ]` **[B] Universe presets:** sectors, regions, ETFs, crypto (on its own calendar), high volatility, and "same as last run".
22. `[ ]` **[B] Macro features with ALFRED vintages.**

### A5. Data integrity shown, not just done

23. `[ ]` **[B+F] Provenance chip on every result:** train and test windows, purge and embargo, universe, missing-data share.
24. `[ ]` **[B] Calendar-aligned panels,** with gap handling stated.
25. `[ ]` **[B] Value-weight and NYSE-breakpoint reporting** for any anomaly or feature sort. Hou, Xue and Zhang show equal-weight results mislead.
26. `[ ]` **[B] Split and adjustment anomaly check.**

---

## 7. What to remove or merge

| Change | Why |
|---|---|
| **F07 DMA/OBS → tab in F02** ("Ensemble weighting") | Niche; it answers a question about F02's own models. |
| **F10 Microstructure → feature families in F08,** no standalone page | 93% of trading-friction anomalies fail replication. Useful only as candidate inputs with value weights. |
| **F11 DML → Research** (Factor zoo and Causal) | It is factor research, and it overlaps Research's spanning and factor-zoo tests. |
| **F12 Sequence models → Labs,** with multi-seed and a gradient-boosting control | Rarely beats gradient boosting or linear on daily data; slow; invites hype. |
| **F05 default HRP → Ledoit–Wolf minimum variance** (HRP stays as an option) | Shrinkage beats HRP in controlled and empirical tests. |
| **Vol-targeting presented as an improvement → shown only with a control** | Cederburg et al.: real-time vol management usually underperforms. |
| Duplicate chart and table payloads (F07 and F10 are about 3 MB) | Send one table and let the view-as menu draw it. |
| Black–Litterman outputs when there are no views | "No change" is noise. |
| Raw `training_audit` tables | Replace with provenance chips (A5). |
| Rarely changed solver inputs | Move to Expert. |

**Result:** 8 pages: Validate, Alpha (with ensembles), Volatility, Trade filter and sizing, Allocation, Regimes, Composite (with microstructure), Pairs, plus Labs.

---

## 8. UI and experience

### 8.1 Outputs (see `ML_V2_MAX_PASS.md` §A)
- `[ ]` A one-line reading under every card, from templates.
- `[ ]` Axis titles and units on every chart.
- `[ ]` Controls drawn on every equity curve (A1.2).
- `[ ]` Dense charts collapse: matrices to clusters above 20 names, top 6 lines, top 12 beeswarm rows.
- `[ ]` Verdict chips (HELD UP / MIXED / FAILED) with the threshold stated on hover.

### 8.2 Interaction
- `[ ]` Clicking a name in the ranking opens its SHAP waterfall.
- `[ ]` Clicking a pair loads its spread.
- `[ ]` Hovering a regime highlights those dates everywhere.
- `[ ]` Clicking a barrier cell reruns with it.
- `[ ]` Clicking a CPCV split highlights its test dates.

### 8.3 Surfaces
- `[ ]` Validate page (A1.1) as the ML landing page.
- `[ ]` Strategy studio (A13).
- `[ ]` ML compare (two runs).
- `[ ]` Live overview board (A18).
- `[ ]` "Send to…" menu on outputs.

### 8.4 Principles from competitor reviews (§3.3)
- `[ ]` Explanations inside the product, no YouTube redirects.
- `[ ]` "Historical, not predictive" line on every verdict.
- `[ ]` Long history by default.
- `[ ]` One-click cancel and billing reminders (business).

### 8.5 Polish
- `[ ]` A visual pass against Koyfin, TradingView and QuantConnect.
- `[ ]` Light theme everywhere, and fix the e2e light snapshots.
- `[ ]` Phone width from 360 px.
- `[ ]` ML wording throughout.
- `[ ]` Chart-shaped loading skeletons.

---

## 9. Inputs

- **Levels:** Quick = universe, horizon, lookback. Standard adds the model and costs. Expert holds the rest.
- **Evidence-based defaults:**
  - Alpha: 21-day horizon, gradient boosting with a linear baseline.
  - Allocation: Ledoit–Wolf minimum variance.
  - Volatility: HAR-RV.
  - Pairs: cointegration with costs on.
  - CPCV: 6 groups, 2 test groups.
- **Presets with citations:** "AFML defaults", "Gu–Kelly–Xiu monthly", "Corsi HAR", "Do & Faff pairs".
- **Guard rails before submission:**
  - warn when too few dates for the horizon plus embargo
  - warn on slow configurations
  - warn when the universe mixes calendars
- **Universe presets and "same as last run".**

---

## 10. Pricing and business model

Anchors: Danelfin $29–179, AgentTrading $49–199, Koyfin $39–79, Tickeron $90–145, Trade Ideas $127–254, QuantConnect $0–60+.

| Tier | Price (monthly; about 35% off yearly) | Includes |
|---|---|---|
| **Free** | $0 | Validate up to 3 uploads a month, default universe, delayed data, every page in read-only demo |
| **Pro** | $39 | All engines, custom universes, daily refresh, 20 alerts, controls, multi-seed (up to 5 seeds) |
| **Research** | $99 | Unlimited validation, plateau maps, transfer tests, 20 seeds, exports (LaTeX, PDF), API, shared ledger, sharing |
| **Team** | $299 | Seats, shared projects, priority compute, SSO |

- **Metered extras, like Portfolio123's worker hours:** large universes, sequence models, high seed counts, billed as credits.
- **Growth:** shareable verdict pages and embeds, the way people share TradingView ideas.
- **Legal:** analysis only, no execution, no advice. Respect data licences on redistribution.

---

## 11. Build order

1. **Trust layer on what exists:** A1.2 controls, A1.5 leakage badge, A23 provenance, readings. Low cost, and every result becomes more convincing.
2. **Evidence-driven corrections:**
   - F05 default to shrinkage
   - vol-targeting shown with a control
   - value-weight reporting
   - Alpha default horizon to 21 days
3. **Merges:** F07 into F02, F10 into F08, F11 to Research, F12 to Labs.
4. **Paid core:** A1.1 validate-my-model, A1.3 multi-seed, A1.8 transfer test, A1.4 plateau map, A1.9 Monte Carlo, A1.6 shared ledger.
5. **Workflow:** A2 hand-offs, Strategy studio, regime-switching volatility, pairs upgrades.
6. **Subscriptions:** A3 live refresh, alerts, monitoring, live board.
7. **Bring your own inputs (A4), tiers, sharing and billing.**

---

## 12. Sources

**Practitioners**
- r/algotrading, "Building an AI-powered trading tool — what's missing" (July 2026): "build the thing that proves ideas wrong".
- r/algotrading, signal validation thread (May 2026): "figuring out if theyre real".
- r/algotrading, AI value versus branding (June 2026): "every beautiful backtest (Sharpe 4+) was a bug".
- r/quant, research books (July 2026): "failures were never technique, they were plumbing".
- r/algotrading, regime-filter controls and plateaus (September 2026).

**Validation research**
- HackerNoon, "How to Validate Financial ML Beyond Accuracy" (September 2026): multi-seed inflation of 44%, spurious predictability.
- Rebellion Research, overfitting guides (October 2026).
- López de Prado, *Advances in Financial Machine Learning* (2018).
- Bailey et al., "The Probability of Backtest Overfitting" (2014).

**Methods**
- Gu, Kelly and Xiu, "Empirical Asset Pricing via Machine Learning", *RFS* 33(5) 2020.
- Hou, Xue and Zhang, "Replicating Anomalies", *RFS* 2020 (NBER w23394).
- Harris and Amato, "Illiquidity and Stock Returns: A Replication", *Critical Finance Review* 2019.
- Cederburg, O'Doherty, Wang and Yan, "On the performance of volatility-managed portfolios", *JFE* 138 (2020).
- "When Does HRP Beat Markowitz? A Controlled Comparison" (hrp.marketmaker.cc).
- "Hierarchical risk clustering versus traditional risk-based portfolios", *Empirical Economics* (2026).
- López de Prado, "Building Diversified Portfolios that Outperform Out-of-Sample" (2016).
- Joubert, "Meta-Labeling: Theory and Framework", *JFDS* 4(3) 2022.
- Hudson & Thames, "Does Meta-Labeling Add to Signal Efficacy?".
- Do and Faff, "Does Simple Pairs Trading Still Work?", *FAJ* 2010.
- Rad, Low and Faff, "The profitability of pairs trading strategies", *Quantitative Finance* 2016.
- Huck and Afawubo, "Pairs trading and selection methods: Is cointegration superior?".
- HAR vs GARCH out-of-sample comparison: GitHub `ArkaKhorchidian/Regime-Detection-Volatility-Forecasting`.
- Regime signals with permutation tests: GitHub `wisdomgu/regim`.
- Deep vs tree models: "Machine Learning and Transformer-Based Equity Return Forecasting" (2026); "15-Year Empirical Comparison of Deep Learning, Tree-Based and Regression Models" (2025); Krauss, Do and Huck, *EJOR* 2017.

**Market**
- QuantConnect pricing and review (Insigtrade, July 2026).
- Portfolio123 AI Factor costs (help centre; RU reduction, June 2026).
- Composer pricing.
- Tickeron and Trade Ideas pricing (AgentTrading at-source reads, October 2026).
- Danelfin pricing.
- AgentTrading pricing.
- Koyfin plan comparison.
- TradingView pricing.
- Numerai documentation (scoring, staking).
- Trustpilot pages for Trade Ideas, Composer, TradingView, PortfolioPilot and QuantVue.
- GitHub stats: Qlib (47k stars), Riskfolio-Lib (4.4k stars, 104k downloads a month), Alphalens (4.4k), skfolio (2.3k).

---

## 13. Final cut: five across the board

**The rule:** a feature ships only if it can score **5** on Demand, Evidence, Differentiation, Decision value and Recurring value, after the upgrades listed for it. Cost is not one of the five, but anything that needs heavy infrastructure for little gain is cut.

**Result:** 12 engines become **4 pages, each scoring 5 on all five axes**, plus **6 new A++ features**. Five engines are removed or moved.

### 13.1 Removed (cannot reach 5)

| Feature | Best reachable | Blocking axis | Decision |
|---|---|---|---|
| F12 Sequence models | E1 · D2 · Dec1 · R1 | Evidence: gradient boosting and linear beat deep models on daily data | **Delete.** Remove PyTorch from the ML stack, which saves about 300–600 MB of RAM per worker and about 30 s per run. Gradient boosting with multi-seed covers "does a bigger model help?". |
| F09 Pairs | E2–3 | Evidence: profits fell from 0.86% to 0.24% a month; the distance method is unprofitable after costs since 2002 | **Delete** from ML. If users ask for it, return later as a watchlist spread monitor (a charting tool, not ML). |
| F10 Microstructure (standalone page) | E1 | Evidence: 93% of trading-friction anomalies fail replication | **Delete the page.** Keep its 8 cheap daily estimators as optional features inside Alpha (13.2-B), reported with value weights. |
| F07 Model averaging (DMA/OBS) | D3 · Dem2 | Demand and differentiation | **Delete.** Alpha keeps one honest ensemble: validation-chosen weights on gradient boosting and linear. |
| F11 DML factor associations | Dem2 for ML users | Wrong audience | **Move to Research** (Factor zoo and Causal), where it scores well. |

**Infrastructure removed with them:**
- **Torch:** gone (F12).
- **The shap package:** use LightGBM `pred_contrib`, which gives exact TreeSHAP; keep linear contributions for linear models.
- **XGBoost and CatBoost:** optional extras, not defaults (LightGBM plus Ridge cover the evidence).
- **Never add:** stable-baselines/RL, NAS, transformer libraries or GPU paths.
- **Expected effect:** ML worker idle RAM drops toward about 250 MB; see `RAM_PLAN.md`.

### 13.2 Kept: the four pages, and what makes each a 5

**A. Validate** (F01 CPCV + F04 meta-labelling + all of A1). This is the landing page and the paid core.

| Axis | Today | Upgrades to reach 5 |
|---|---|---|
| Demand | 4 | Upload your own returns, predictions or trial matrix (A1.1); the top request on Reddit is "cheap way to kill bad ideas". |
| Evidence | 5 | CPCV, PBO, DSR, MinBTL and block bootstrap are standard and replicated. |
| Differentiation | 5 | No product under $100 offers CPCV, PBO, multi-seed and transfer tests in a UI. AgentTrading tests simple rules only. |
| Decision value | 4 | A one-page HELD UP / MIXED / FAILED verdict against the best control (A1.2), plus an **overfitting autopsy** (13.3-1) naming the exact reason. |
| Recurring | 2 | **Forward tracking** (13.3-2): freeze a validated model and score it daily on new data; alerts when live results diverge from the backtest. |

Includes:
- **"Improve my strategy"**: meta-label filter and sizing, always beside the unfiltered strategy (absorbs F04).
- **Transfer test**: other assets, sectors and later periods.
- **Plateau map**, **multi-seed**, **leakage badge** and **reproducibility receipt**.

**B. Alpha** (F02 + F08 composite + F10 features + custom formula features). One page for cross-sectional prediction.

| Axis | Today | Upgrades to reach 5 |
|---|---|---|
| Demand | 5 | Ranking plus explanation is the most-used ML output. |
| Evidence | 4 | **Monthly or 21-day horizon by default** (Gu–Kelly–Xiu scale); LightGBM with a Ridge baseline; the IC-weighted composite as a built-in control; value-weight decile reporting. With those, results match the replicated literature. |
| Differentiation | 3 | **Bring your own features** in the Research formula language; every alpha passes through Validate automatically (controls, multi-seed, transfer). Nobody else joins a formula language, ML and validation. |
| Decision value | 4 | Ranking with drivers, "what changed since last week" (rank moves explained by SHAP deltas), and capacity and turnover after costs. |
| Recurring | 3 | **Daily refreshed ranking and alerts** (top-N entries and exits), plus **forward tracking** of the live ranking's IC. |

Includes:
- the SHAP beeswarm and waterfall (click any name)
- feature families: momentum, value, quality, volatility, liquidity (the F10 estimators) and custom
- the composite as a baseline
- the ensemble tab (gradient boosting and Ridge weights)

**C. Volatility and risk state** (F03 + F06 regimes). Forecasts plus the market's current risk state.

| Axis | Today | Upgrades to reach 5 |
|---|---|---|
| Demand | 4 | Add **VaR and expected-shortfall forecasts** and a **position-size helper** (vol-scaled, always beside unmanaged per Cederburg). Watchlist mode for many tickers at once. |
| Evidence | 5 | HAR-RV first by QLIKE; GJR-GARCH best in stress; **regime-switching model choice** (calm → HAR, stress → GJR), scored against the single model with Diebold–Mariano tests. |
| Differentiation | 4 | A forecast tournament with significance tests, forward-filtered (no look-ahead) regime probabilities and calibrated intervals. Retail tools show only historical volatility. |
| Decision value | 4 | A "risk today" card: forecast range for 1, 5 and 21 days, the regime, the suggested size at a target risk, and VaR. |
| Recurring | 4 | **Daily refresh and alerts:** volatility above the forecast band, regime change, VaR breach. |

**D. Allocation** (F05 with corrected defaults).

| Axis | Today | Upgrades to reach 5 |
|---|---|---|
| Demand | 4 | "Allocate my holdings": paste holdings or import a watchlist; rebalance plan with trade list and costs. |
| Evidence | 3 | **Ledoit–Wolf minimum variance by default**; HRP, inverse-variance and 1/N always shown as controls; walk-forward, net of costs. |
| Differentiation | 2 | **Allocation uncertainty**: bootstrap weight stability bands and turnover-aware rebalancing (trade only when the gain beats costs). This is missing from Portfolio Visualizer and Koyfin. Every allocation is validated in Validate. |
| Decision value | 4 | A trade list with sizes, the cost of rebalancing and expected risk change; risk contributions per holding. |
| Recurring | 3 | **Drift alerts:** weights out of band, risk contribution breach, monthly rebalance reminder with the trade list ready. |

### 13.3 New A++ features (5 on every axis by design)

1. **Overfitting autopsy (inside Validate).** Diagnoses *why* a backtest is lying and ranks the causes with evidence:
   - leakage (perturbation test)
   - trial count (DSR haircut)
   - regime dependence (performance by regime)
   - cost sensitivity (breakeven bps)
   - parameter cliff (plateau)
   - single-asset luck (transfer test)
   - seed luck (multi-seed)

   Output: "Your Sharpe of 2.1 is mostly explained by 140 trials (DSR 0.18) and one regime (2020–21)."
   - D5: the core pain. E5: each test is standard. Diff5: nobody does this. Dec5: tells you exactly what to fix. R5: rerun on every iteration.
2. **Forward tracking (live out-of-sample record).** Freeze any validated model, ranking or allocation. It is scored every day on data it has never seen, with an equity curve, live IC and divergence from the backtest. This is Numerai's live scoring on your own model and your own universe.
   - E5: true out-of-sample. Diff5. Dec5: whether to trust it with money. R5: daily.
3. **Model and feature drift monitor.** For each tracked model:
   - Wasserstein drift per feature against the training window
   - live IC against backtest IC
   - "retrain recommended" when either crosses a threshold
   - D4–5. E5. Diff5. Dec5. R5.
4. **Verified result page (shareable).** A hash-stamped, read-only page holding the verdict, controls, autopsy and forward record. Edits are impossible; reruns are linked. This is a credibility asset for funds, students and newsletters, and brings in users.
   - D5. E5. Diff5. Dec4–5. R5 via forward-record updates.
5. **"What changed" digest.** A weekly or daily email or in-app note. Example: "3 names entered your top 10 (drivers: momentum, quality); regime moved to stress; your tracked model's live IC fell to 0.01."
   - Recurring 5 by construction; Decision 5.
6. **Strategy studio (thin).** Signal (Alpha or upload) → optional filter (meta-label) → sizing (vol-scaled or equal, beside unmanaged) → allocation → costs, then one click into Validate. No new engines; it wires the four pages together.

### 13.4 Backend work this implies (light infrastructure only)

| Item | Work | Heavy? |
|---|---|---|
| Validate uploads (returns, predictions, trial matrix) | Upload parsing and point-in-time checks, then the existing CPCV, PBO and DSR | No |
| Controls, multi-seed, plateau, transfer, Monte Carlo | Batch runner reusing the existing engines | No (reuses the job workers; caps seeds and grid size by tier) |
| Overfitting autopsy | Orchestrates the tests above and ranks causes | No |
| Forward tracking and drift | Freezes model artifacts (LightGBM text dump, Ridge coefficients, weights) and runs a nightly scoring job | Light: one nightly job, small artifacts |
| Daily refresh and alerts | Nightly jobs for Alpha rankings, volatility and regime, and allocation drift; alert rules table; email and webhook sender | Light |
| Formula features in Alpha | Reuse `signal_lang` | No |
| Regime-switching volatility, VaR and ES | Small additions to `volatility.py` | No |
| Shrinkage default, allocation bootstrap, turnover-aware rebalance | `allocation.py` changes | No |
| Remove F07, F09, F10 page, F11 (to Research), F12 and torch | Deletions with graph and `rg` checks | Reduces infrastructure |

### 13.5 Final build order

1. **Cut:** delete F12 and torch, F09, F07 and the F10 page; move F11 to Research; switch Alpha to LightGBM `pred_contrib`; make XGBoost and CatBoost optional.
2. **Correct defaults:** shrinkage allocation, Alpha at 21 days with Ridge and composite controls, vol sizing beside unmanaged, value-weight reporting.
3. **Validate core:** uploads, controls, leakage badge, multi-seed, transfer, plateau, Monte Carlo and the **overfitting autopsy**.
4. **Four-page restructure** of the frontend: Validate, Alpha, Volatility and risk, Allocation.
5. **Forward tracking, drift monitor and daily refresh with alerts**, then the **"what changed" digest**.
6. **Verified result pages**, the **thin Strategy studio**, pricing tiers and billing.
