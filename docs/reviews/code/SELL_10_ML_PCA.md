# SELL_10: ML V2 (F01-F12) + PCA V2 (F01-F11) Sellability Scorecard

Date: 2026-09-29. Read-only review except this doc.
Sources: `frontend/src/components/ml-v2/registry.js` (2,361 lines, 12 features), `frontend/src/components/pca-v2/registry.js` (11 features), `backend/app/services/ml_v2/registry.py`, `backend/app/services/pca_v2/registry.py`, `docs/reviews/ML_V2_REVIEW.md`, `docs/reviews/PCA_V2_REVIEW.md`, plus web search on comparables (QuantConnect, MLflow/W&B, Bloomberg MAC3/Barra, NYU V-Lab, general PCA tools).

## Rubric (per feature, 1-5 each, 40 max)

EXI existence (backend runs, reachable) | PAR parity (vs best comparable) | WTP willingness-to-pay lift | HAB habit (repeat-use frequency) | TRU trust cost inverted (5 = low trust cost, honest labels) | DIS distribution (demoable, shareable) | MOA moat (hard to copy) | BUN bundle fit.

Bands: >=30 sell now, 22-29 fix-then-sell, <22 hide/cut.

## Gate warning (applies to everything below)

Nothing below is sellable until two wiring fixes land (both documented in the V2 reviews):

1. ML V2: frontend POSTs `/api/labs/ml/v2/feature/{id}/run` but backend serves `/api/ml/v2/features/{id}/run`. Every Run 404s. One-line URL fix.
2. PCA V2: router (`backend/app/api/pca_v2.py`) is never mounted and every workbench renders `Math.sin` filler with a dead "API pending" button. Mount router, bind workbench to response, delete filler.
3. Both: silent universe fallback (unknown tickers return default-universe results with no warning). Return 422 or flag `meta.universe_substituted`.

"Sell now" below means "sell now after gates 1-3". Scores assume gates fixed; EXI is scored on backend reality today.

## Comparables used

- QuantConnect: full research-to-live-trade loop, point-in-time backtest, Alpha Models framework. No built-in purged CPCV/DSR/PBO, triple-barrier, or DML. Our edge is validation rigor, not execution.
- MLflow / W&B: best-in-class experiment tracking UX (params, metrics, artifacts, registry). W&B Pro ~$60/mo, Enterprise $315-400/seat/mo; MLflow self-hosted free. We have no run registry, no artifact versioning, no comparison UX. Do not sell "experiment tracking" as a category; sell finance-specific validation panels.
- Bloomberg MAC3 / MSCI Barra: institutional multi-asset factor risk models, daily refreshed, with tracking error, stress, and consultant-grade reporting. Our PCA F03/F09 are a credible lite version, not a replacement.
- NYU V-Lab: free GARCH-family vol measurement and forecasting. Our ML F03 must beat "free GARCH" with HAR+spillover+QLIKE+term-structure, not with GARCH alone.
- General PCA/biplot tools (sklearn, FactorAnalyzer, Origin): loadings/scree/biplots are commodities. Our moat is RMT cleaning, OU-on-residuals, contagion alerts, LaVaR, not basic PCA.

## ML V2 scores (F01-F12)

| F | Feature | EXI | PAR | WTP | HAB | TRU | DIS | MOA | BUN | Tot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | Purged K-Fold + CPCV + DSR/PBO | 4 | 5 | 5 | 3 | 4 | 3 | 5 | 5 | 34 | SELL NOW |
| 02 | GBT Alpha + attribution | 3 | 4 | 5 | 5 | 2 | 4 | 3 | 5 | 31 | SELL NOW* |
| 03 | Multi-horizon vol forecasting | 4 | 3 | 4 | 4 | 3 | 4 | 2 | 4 | 28 | FIX-THEN-SELL |
| 04 | Meta-labeling + triple-barrier | 4 | 5 | 4 | 3 | 4 | 3 | 4 | 4 | 31 | SELL NOW |
| 05 | HRP optimizer (+RL/BL proxies) | 4 | 3 | 3 | 3 | 3 | 3 | 2 | 5 | 26 | FIX-THEN-SELL |
| 06 | Regime detection + routing | 4 | 4 | 4 | 5 | 3 | 4 | 3 | 5 | 32 | SELL NOW |
| 07 | Bayesian DMA/OBS ensemble | 3 | 5 | 3 | 4 | 3 | 2 | 4 | 3 | 27 | FIX-THEN-SELL |
| 08 | IC-weighted composite optimizer | 3 | 4 | 5 | 5 | 3 | 4 | 3 | 5 | 32 | SELL NOW |
| 09 | Pairs / stat-arb engine | 4 | 3 | 4 | 5 | 3 | 4 | 2 | 4 | 29 | FIX-THEN-SELL |
| 10 | Microstructure observatory | 4 | 4 | 3 | 3 | 4 | 3 | 3 | 3 | 27 | FIX-THEN-SELL |
| 11 | Causal (DML) factor discovery | 4 | 5 | 4 | 2 | 3 | 2 | 5 | 3 | 28 | FIX-THEN-SELL |
| 12 | Deep sequence alpha | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 13 | HIDE/CUT |

*F02 sells on the condition the unpurged 75/25 split (review B3) is fixed or the IC panel is labeled in-sample. Do not sell unpurged IC as validated alpha.

Score notes (one line each):
- F01: only feature with correct chronological purge; DSR/PBO fixed per July audit; `triple_barrier` label accepted-but-ignored, 422 or wire it.
- F02: real 7-family ensemble + IC decay, but split is ticker-blocked not date-sorted; SHAP beeswarm/waterfall honestly disabled; no Optuna, no sample weights.
- F03: HAR-Ridge/GBM + GK/YZ + ARCH-AIC + spillover real; GINN research-only; competes with free V-Lab so sell the ensemble/tournament, not GARCH.
- F04: CQR + calibration real; primary side still momentum-only; F02-prediction routing research-only.
- F05: HRP/NCO/HERC/BL-posterior math real; RL rebalancing and BL-without-views are labeled proxies; confirm `max_sector_weight` binds.
- F06: Gaussian HMM Baum-Welch real; ensemble RF-only; RF-vs-HMM agreement double-dips in-sample, relabel or OOS it.
- F07: sequential DMA + simplex OBS real; 5 hardcoded members vs spec up-to-20; `model_library` options do not match members run (B4).
- F08: IC-IR `mean/std` fixed; Gram-Schmidt/walk-forward/interactions real; `dml_ape` selectable with no persisted F11 artifact, needs fallback warning.
- F09: Kalman hedge path + ADF screen real; "ML classifier" is a rule score, rename it; RL threshold research proxy.
- F10: daily estimators (Amihud, Roll, Corwin-Schultz, MAX, 52w-high, IVOL) honest about no tick data; niche but differentiated.
- F11: real K-fold cross-fit DML + HC3; Causal/Proxy/Spurious labels are heuristics; low habit (research cadence), high moat.
- F12: all "architectures" are Ridge/RF/ET proxies; `transformer_depth/heads/dropout` accepted-but-ignored. Hide the tab, keep code behind a research flag.

## PCA V2 scores (F01-F11)

| F | Feature | EXI | PAR | WTP | HAB | TRU | DIS | MOA | BUN | Tot | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | RMT noise-filtered covariance | 4 | 5 | 4 | 3 | 3 | 3 | 5 | 5 | 32 | SELL NOW |
| 02 | Loadings / factor extraction | 3 | 3 | 3 | 3 | 3 | 3 | 2 | 4 | 24 | FIX-THEN-SELL |
| 03 | Risk decomposition + attribution | 4 | 4 | 5 | 4 | 4 | 4 | 3 | 5 | 33 | SELL NOW |
| 04 | Residual OU stat-arb engine | 4 | 4 | 5 | 5 | 4 | 4 | 3 | 5 | 33 | SELL NOW |
| 05 | Rolling stability / regime monitor | 4 | 5 | 4 | 4 | 3 | 3 | 4 | 4 | 31 | SELL NOW |
| 06 | Constrained optimization (RMT) | 4 | 3 | 4 | 3 | 3 | 3 | 2 | 5 | 27 | FIX-THEN-SELL |
| 07 | Bootstrap validation scorecard | 4 | 5 | 3 | 2 | 4 | 2 | 4 | 3 | 27 | FIX-THEN-SELL |
| 08 | Residual contagion monitor | 4 | 5 | 4 | 5 | 4 | 4 | 4 | 4 | 34 | SELL NOW |
| 09 | PC-shock stress + P&L attribution | 4 | 4 | 5 | 3 | 4 | 4 | 3 | 5 | 32 | SELL NOW |
| 10 | Cross-asset RMT engine | 3 | 4 | 4 | 3 | 3 | 3 | 4 | 4 | 28 | FIX-THEN-SELL |
| 11 | Liquidity PCA + LaVaR | 4 | 5 | 4 | 3 | 4 | 3 | 5 | 4 | 32 | SELL NOW |

Score notes (one line each):
- F01: real `eigh` + iterative MP sigma2 + 5 estimators + blend; Kaiser `lambda>1` WRONG on covariance path, no correlation-matrix toggle (review B3).
- F02: loadings/variance/Hoyer/R2/HPCA real; no biplot (the one visual every PCA user expects); sign-flicker across rolling windows.
- F03: historical VaR waterfall + active attribution bugs from old audit now fixed; closest thing to a Barra-lite story.
- F04: OU OLS+MLE with half-life/kappa/se + decay + backtest real; volume-time silent fallback needs a meta flag.
- F05: CUSUM + Bai-Perron + multi-PC drift + 10 crisis bands real; alert thresholds hardcoded, wire payload values.
- F06: 100-point lambda-sweep QP frontier real (old pseudo-frontier fixed); no sector/TE/cardinality constraints.
- F07: bootstrap + Bai-Ng + principal angles real; replication caps silent; low habit, sell as audit artifact not dashboard.
- F08: genuinely rare retail feature; rolling lambda1 + group residual correlation; alert-ready.
- F09: PC shocks + worst-history replay + P&L attribution; true Mahalanobis fixed; bundle with F03.
- F10: EWMA/OAS/Student-t EM + DCC + CASCI real; no unified RMT cleaning or block MP overlay; heavy-request path needs job transport.
- F11: Amihud/PS/Kyle + liquidation cost + unwind scorecard; quant-unwind framing is the most differentiated risk story here.

## Counts

- ML V2: 12 scored. Sell now 5 (F01, F02, F04, F06, F08). Fix-then-sell 6 (F03, F05, F07, F09, F10, F11). Hide/cut 1 (F12).
- PCA V2: 11 scored. Sell now 7 (F01, F03, F04, F05, F08, F09, F11). Fix-then-sell 4 (F02, F06, F07, F10). Hide/cut 0.
- Combined: 23 scored. Sell now 12. Fix-then-sell 10. Hide/cut 1.

## Top 3 money features

1. ML F01 Purged CPCV + DSR/PBO (34). Reason: the single highest-moat item vs QuantConnect and every retail backtester; overfitting-proof is the story funds pay for. Sell as "don't trust any backtest without this" and attach it to every other feature's output.
2. PCA F04 Residual OU stat-arb (33) tied with PCA F03 risk decomp (33); trade-ready pick is F04. Reason: emits a ranked trade list with half-life and decay, the shortest path from screen to P&L. Demo: top-pair spread chart to entry/exit timeline to backtest equity.
3. ML F08 IC-weighted composite (32). Reason: highest habit x WTP combo (daily signal book + long-short backtest); it is the natural upsell surface for F11 DML weights and F02 predictions.

Runners-up: PCA F08 contagion monitor (34, best alert product), PCA F09 stress (institutional bundle with F03), ML F06 regimes (daily habit, routes content).

## Bundle and price

- Bundle A "Validate" (ML F01 + PCA F07 + ML F04): overfitting audit pack. Gate every backtest claim behind F01.
- Bundle B "Daily alpha" (ML F08 + ML F02 + ML F06 + PCA F04 + ML F09): the subscription core, daily/weekly habit loop.
- Bundle C "Risk institutional" (PCA F01 + F03 + F09 + F05 + F08 + F11 + ML F03 + ML F05): Barra-lite story for advisors/funds; price highest.
- Price anchors: W&B Pro ~$60/mo and QuantConnect cloud cores set the floor for tooling; Barra/Bloomberg set the ceiling for risk. Suggested: Solo $49-79/mo (Bundle B), Pro $149-249/mo (A+B), Institutional $500+/mo or seat-based (A+B+C with F11/F01 white-label reports). F12 stays out of all tiers until real training exists.

## Distribution moves (in order)

1. Fix gates 1-3 above; nothing demos until Runs work and filler is gone.
2. Ship one public artifact per money feature: F01 "purged vs naive Sharpe gap" chart, F04 "spread to backtest" video, F08 "IC decay" post. These are the only three demos that beat V-Lab/QuantConnect screenshots.
3. Rename dishonest labels before marketing: F09 "ML classifier" to rule score, PCA F01 Kaiser to covariance heuristic until corr path exists, F12 tab hidden.
4. Add the missing biplot (PCA F02) and corr-matrix toggle; they are the two most-requested commodity expectations and block conversion.
5. Content wedge: "every IC number on this platform is purged" once ML B3 is fixed across F02/F08/F11/F12; until then disclose single-split status on those panels.

## Fix list for the 10 fix-then-sell items (minimal)

- ML F03: term-structure per-horizon (not sqrt-scaled), HAR-X toggle wiring; else keep at 28.
- ML F05: bind `max_sector_weight`, disclose BL-noop-without-views; drop RL panel from sales screenshots.
- ML F07: align `model_library` options with members run; cap story at 5 members honestly.
- ML F09: rename classifier output; disclose Kalman top-pair-only scope.
- ML F10: fine as is; needs tick-data roadmap note in sales copy.
- ML F11: persist APE artifact so F08 `dml_ape` mode works; that single wire lifts both scores.
- PCA F02: add biplot + sign alignment; corr toggle shared with F01.
- PCA F06: add turnover default story + at least sector-cap constraint for institutional bundle.
- PCA F07: surface requested-vs-executed bootstrap runs; sell as PDF audit, not dashboard.
- PCA F10: unified RMT cleaning + block MP overlay; job-transport for heavy runs.
