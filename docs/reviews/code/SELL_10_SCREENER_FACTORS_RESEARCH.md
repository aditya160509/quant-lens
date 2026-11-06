# SELL-10: Screener V2 + Factors V2 + Research V2 Sellability Scorecard

**Scope:** SCREENER V2 (S1-S8), FACTORS V2 (F01-F14), RESEARCH V2 (shipped: F01-F09 + F11; **F10 has no module in `backend/app/services/research_v2/features/` or `registry.py` and is not scored**).
**Method:** read-only code review of `backend/app/services/{screener_v2,factors_v2,research_v2}` (registries, FEATURES/DONE/review audits) + `frontend/src/components/{screener,factors,research}-v2/registry.js`, grounded against incumbents via web search.
**Rubric (1-5 each, 40 max):** C1 Existence vs incumbents (differentiated = high) | C2 Parity gap (close to incumbent = high) | C3 WTP lift | C4 Habit frequency | C5 Trust cost (5 = low burden, easy to trust) | C6 Distribution power (demo/viral ease) | C7 Moat durability | C8 Bundle fit.
**Verdicts:** `LEAD` sell now >= 30 | `GATE` fix-then-sell 22-29 | `HIDE` hide/cut < 22.

## Incumbent anchors (web search, Sep 2026)

| Incumbent | What it sets | Price anchor |
|---|---|---|
| TradingView Screens + Pine Screener (custom formulas, alerts) | Retail screen bar: custom formulas, alerts on paid plans | Free + 4 paid tiers; alerts/formulas gated by plan |
| finviz Elite (screener + basic backtest + export/API) | Retail screen+backtest bar | $39.50/mo monthly, ~$24.96/mo annual |
| Koyfin (global screener, 500+ metrics; Plus/Advisor tiers) | Pro-sumer screen + charts bar | Plus from $39/mo |
| QuantConnect (research notebooks, fee/slippage-adjusted backtest) | Quant backtest/research bar | Free community + paid cloud |
| Bloomberg EQS/SRCH + PORT (screening + factor risk) | Institutional ceiling | ~$24k-32k/yr per terminal |
| MSCI Barra / Axioma (exposure, attribution, crowding, optimizer, stress) | Institutional factor gold standard | Enterprise (5-6 figs/yr) |
| alphalens / pyfolio (free factor IC/decay tear sheets) | Free floor for F05/R01/R08-type analysis | Free open source |

## Tally

| Module | LEAD | GATE | HIDE |
|---|---|---|---|
| Screener V2 (8) | 2 | 6 | 0 |
| Factors V2 (14) | 3 | 11 | 0 |
| Research V2 (10 shipped) | 1 | 7 | 2 |
| **Total (32 scored)** | **6** | **24** | **2** |

## 1. Screener V2 vs TradingView / finviz Elite / Koyfin / Bloomberg EQS

Known code caveats shaping scores: no durable saved screens, alerts are run-emitted candidates only (no scheduler/email), no true point-in-time fundamentals or delisted history (`screener_v2/FEATURES.md`, `review.md`).

| ID | Feature | Incumbent equiv. | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Tot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | Core Multi-Factor Screener | TradingView/finviz/Koyfin base screen | 2 | 3 | 2 | 5 | 3 | 5 | 2 | 5 | **27** | GATE |
| S2 | Formula Builder + expression backtest | TradingView Pine Screener; StockRover equations | 4 | 4 | 4 | 4 | 4 | 4 | 3 | 4 | **31** | LEAD |
| S3 | Composite Quant Score (IC/IR, ridge, neutralized, regime split) | None at retail (Koyfin/finviz lack IC weighting) | 4 | 4 | 4 | 3 | 3 | 3 | 4 | 5 | **30** | LEAD |
| S4 | Academic Strategy Library | None turnkey at retail | 4 | 4 | 3 | 3 | 4 | 5 | 2 | 4 | **29** | GATE |
| S5 | Backtester + PIT validation, PBO proxy, attribution | finviz Elite basic backtest; QuantConnect | 4 | 3 | 4 | 3 | 2 | 3 | 4 | 5 | **28** | GATE |
| S6 | Alert Engine + watchlist monitor | TradingView alerts (incumbent strength) | 2 | 2 | 3 | 5 | 2 | 4 | 1 | 4 | **23** | GATE |
| S7 | Relative Valuation (4-D card, sector map, peer table) | Koyfin peer/sector compare | 3 | 4 | 3 | 4 | 4 | 5 | 2 | 4 | **29** | GATE |
| S8 | Export + integration layer | finviz Elite export/API | 3 | 3 | 2 | 2 | 3 | 3 | 2 | 5 | **23** | GATE |

Gate fixes: S1/S5 label non-PIT fundamentals openly and cap lookback claims; S4 publish per-strategy metadata + data requirements; S6 needs persistence + scheduler + delivery before it leads (highest habit score in the module, currently a shell); S8 needs run-history storage for the change report to be real; S7 is closest to lead, needs only sector-map polish.

## 2. Factors V2 vs Barra/Axioma / Bloomberg PORT / QuantConnect / alphalens

Known code caveats: no true PIT characteristics, no benchmark constituent histories, missing optional AQR/macro feeds, no durable alert history or scheduled refresh; DCC/VAR caps are honest Research-mode gates (`factors_v2/review.md`, realtime constraints in `registry.js`).

| ID | Feature | Incumbent equiv. | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Tot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F01 | Valuation Spread Monitor | MSCI crowding-adjacent; Koyfin charts | 4 | 3 | 3 | 3 | 3 | 3 | 3 | 4 | **26** | GATE |
| F02 | Exposure Decomposition (X-Ray) | Barra/Axioma exposure; Bloomberg PORT | 3 | 2 | 4 | 4 | 2 | 4 | 2 | 5 | **26** | GATE |
| F03 | Return Attribution (Brinson-Fachler-factor + carryover) | Barra/FactSet attribution | 4 | 3 | 4 | 3 | 3 | 3 | 3 | 5 | **28** | GATE |
| F04 | Probabilistic Regime (macro + HMM + GMM) | Assorted regime models, none composite turnkey | 4 | 3 | 4 | 3 | 2 | 4 | 3 | 4 | **27** | GATE |
| F05 | Alpha Decay + half-life | alphalens (free floor) | 3 | 4 | 3 | 2 | 4 | 3 | 2 | 4 | **25** | GATE |
| F06 | Crowding Monitor | MSCI Integrated Factor Crowding Model | 5 | 3 | 4 | 3 | 3 | 4 | 4 | 4 | **30** | LEAD |
| F07 | Backtest + implementation shortfall | QuantConnect cost-adjusted backtest | 4 | 4 | 4 | 3 | 3 | 3 | 3 | 4 | **28** | GATE |
| F08 | Covariance Matrix (Ledoit-Wolf/EWMA/DCC) | Barra covariance (gold standard) | 3 | 3 | 3 | 2 | 3 | 2 | 3 | 4 | **23** | GATE |
| F09 | Capacity Analyzer (Kyle lambda, AUM sweep) | Rare outside institutional desks | 5 | 4 | 4 | 2 | 3 | 3 | 4 | 4 | **29** | GATE |
| F10 | Factor Optimizer + FAP detection | Barra optimizer (gold standard) | 4 | 3 | 4 | 3 | 2 | 3 | 4 | 5 | **28** | GATE |
| F11 | Stress + reverse stress + VAR contagion | Barra stress; Bloomberg scenarios | 4 | 4 | 4 | 2 | 3 | 4 | 3 | 4 | **28** | GATE |
| F12 | Factor DNA card | No direct incumbent (synthesis card) | 5 | 4 | 3 | 3 | 3 | 5 | 3 | 4 | **30** | LEAD |
| F13 | Live Signal Monitoring | MSCI monitoring; QuantConnect live | 4 | 2 | 4 | 5 | 2 | 4 | 3 | 4 | **28** | GATE |
| F14 | Allocator Transparency Report (LP DDQ supplement) | Barra/FactSet client reporting | 5 | 3 | 5 | 2 | 2 | 4 | 4 | 5 | **30** | LEAD |

Gate fixes: F02/F10 need PIT-characteristics disclaimers (biggest trust drags); F13 needs durable alert history + scheduler to justify its habit-5 monitoring claim; F09 needs borrow-constraint honesty to cross 30; F04 needs regime-label out-of-sample discipline; F08 stays gated behind Research-mode compute positioning, do not sell as realtime.

## 3. Research V2 vs QuantConnect / alphalens-pyfolio / Stata-R academic stack

Known code caveats: several proxies (FM Shanken = NW x 1.05 hardcoded, OLS without fixed effects, simplified GRS/monotonicity, calendar-time portfolio missing), no tests beyond compileall, no caching or async (`research_v2/review.md`). Scores penalize trust/parity accordingly; novelty still scores where no turnkey retail equivalent exists.

| ID | Feature | Incumbent equiv. | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Tot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F01 | Canonical Test Engine (FM, sorts, spanning) | alphalens/pyfolio (free) + QuantConnect | 3 | 2 | 3 | 3 | 2 | 3 | 2 | 4 | **22** | GATE |
| F02 | Robustness Engine (spec curve, researcher DF) | No turnkey retail equiv. | 5 | 3 | 4 | 2 | 3 | 3 | 4 | 4 | **28** | GATE |
| F03 | Placebo + Falsification Suite | No turnkey retail equiv. | 5 | 3 | 3 | 2 | 3 | 3 | 4 | 4 | **27** | GATE |
| F04 | Regime Conditional Analyzer | Manual QuantConnect/forum workflows | 4 | 3 | 3 | 2 | 3 | 3 | 3 | 4 | **25** | GATE |
| F05 | Diagnostic Center | statsmodels/R (free, better) | 2 | 2 | 2 | 2 | 3 | 2 | 1 | 3 | **17** | HIDE |
| F06 | Spec Builder + Publication Output (JFE/RFS styles, LaTeX) | No turnkey retail equiv. | 5 | 4 | 4 | 2 | 4 | 4 | 4 | 3 | **30** | LEAD |
| F07 | Causal ID Engine (DiD/RDD/IV/matching) | Stata/R (gold standard, free) | 4 | 2 | 4 | 2 | 2 | 3 | 3 | 3 | **23** | GATE |
| F08 | Signal Decay + Arbitrage Clock | alphalens decay (free partial) | 4 | 3 | 3 | 2 | 3 | 4 | 3 | 4 | **26** | GATE |
| F09 | Synthetic Control Engine | R Synth/Stata (gold standard, free) | 4 | 2 | 3 | 1 | 2 | 2 | 3 | 3 | **20** | HIDE |
| F11 | Factor Zoo Positioning (HLZ t>3, spanning) | AQR library/manual workflows | 5 | 3 | 3 | 2 | 3 | 5 | 3 | 4 | **28** | GATE |

Hide treatment: F05 (Diagnostic Center) and F09 (Synthetic Control) come out of nav and out of the bundle; keep API/research-mode accessible, do not demo or price them. F05 loses to free statsmodels/R on parity with no novelty; F09 loses to free R Synth/Stata on inference rigor with habit-1 usage. Revisit only with real inference upgrades (F05: proper diagnostics depth; F09: conformal/placebo inference rigor + async).

## 4. Bundle + price tier (anchored to finviz $39.50/mo, Koyfin $39/mo+, Bloomberg ~$24-32k/yr)

| Tier | Price | Includes | Logic |
|---|---|---|---|
| Explorer (free) | $0 | S1 capped (100 symbols), S4 one strategy, S7 one ticker, F12 quick card | Distribution funnel; everything demoable in 60 seconds |
| Pro | $49/mo | All S1-S4 + S7 + S8; F01, F05, F12-quick; R08, R11 | Beats finviz Elite/Koyfin Plus on formulas + composites + DNA; S2/S3 are the conversion drivers |
| Quant | $149/mo | + S5 (labeled research-grade PIT), F02-F04, F06-F08, F11; R01-R04 | Full factor + robustness loop; gated features sold with honest beta badges |
| Institutional | $590/mo or $5.9k/yr | + F09, F10, F13, F14-full; R06; white-label PDF; API | F14 report + F09 capacity + R06 publication outputs are the enterprise close; priced at ~2 percent of a Bloomberg seat |

GATE features ship inside paid tiers behind `beta` badges with one-line caveats (PIT, scheduler, history). HIDE features (R-F05, R-F09) are excluded from pricing pages entirely.

## 5. Top 5 distribution moves

1. **Formula marketplace + share-links (S2):** every shared formula is a signup loop; TradingView proved this mechanic with Pine Script.
2. **Factor DNA card as shareable image (F12):** one-glance card built for social; no incumbent has this artifact.
3. **Weekly public crowding gauge post (F06):** content engine (e.g. "momentum crowding at 82nd percentile") that advertises the paid monitor.
4. **Publication template gallery (R06):** JFE/RFS LaTeX + forest plots aimed at quant Twitter/PhD students; cheapest credible acquisition channel in the set.
5. **Sample allocator PDF as sales collateral (F14):** a redacted LP DDQ supplement does the enterprise selling; attach to every outbound email.

## 6. Path

- **Week 1, hide (1 day):** remove R-F05 and R-F09 from nav/pricing/docs; keep API routes, add `research-only` flag. Counts become 6 lead / 24 gate / 0 visible-hide.
- **Week 1-2, sell (price + paywall the 6 leads):** S2, S3, F06, F12, F14, R-F06 front the landing page and the Pro/Quant/Institutional tiers above; ship Explorer caps.
- **Next, fix gates in money order:** (a) S6 persistence + scheduler + delivery; (b) F13 alert history + scheduler; (c) S5/F02/F10 PIT-characteristics labeling + constituent-history roadmap; (d) F09 borrow constraints; (e) S8 run-history storage; (f) Research proxies (real Shanken SE, fixed effects, GRS) for R-F01/R-F07 before any academic marketing.
- **Cut decision:** R-F05/R-F09 stay hidden unless a paying user asks twice; two requests = build signal, otherwise permanent cut.

## Return summary

- **Counts: 6 LEAD / 24 GATE / 2 HIDE** across 32 scored features (Research F10 absent from code, unscored).
- **Top 3 money features:** (1) **F14 Allocator Report** (only WTP-5 in the set; closes enterprise deals), (2) **S2 Formula Builder** (retail conversion engine with Pine-proven virality), (3) **F06 Crowding Monitor** (differentiated vs MSCI, content-engine distribution). Runners-up: S3 composite engine, R-F06 publication output.
- **Path: hide 2 this week, sell the 6 leads on a $0/$49/$149/$590 ladder, fix gates in money order (alerts infra, then PIT honesty, then research rigor), cut the hides unless customers pull them back.**
