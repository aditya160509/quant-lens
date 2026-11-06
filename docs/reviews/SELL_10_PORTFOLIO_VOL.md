# SELL_10: Portfolio V2 (13 engines) + Volatility V2 (F1-F9) Sellability Review

Date: 2026-09-29. Scope: `backend/app/services/portfolio_v2` (13 features, F01-F13 impl = spec 1-10, 12, 13, 15), `backend/app/services/volatility_v2` (F01-F09), `frontend/src/components/portfolio-v2/registry.js`, `frontend/src/components/volatility-v2/registry.js`. Evidence: `docs/reviews/PORTFOLIO_V2_REVIEW.md`, `docs/reviews/VOLATILITY_V2_REVIEW.md`, code reads of both services. Read-only except this doc.

## Rubric (1-5 each, 40 max)

| # | Criterion | 5 means |
|---|---|---|
| E | Existence | Runs today, wired, real numbers |
| P | Parity | Meets or beats named comps |
| W | WTP lift | Buyer pays extra for this |
| H | Habit | Used daily/weekly, not quarterly |
| T | Trust cost | Cheap to trust (verified, disclosed, no silent fallbacks). Low score = expensive to trust |
| D | Distribution | Demoable/sharable from the UI today |
| M | Moat | Hard to clone (ensemble, proprietary combo, data) |
| B | Bundle fit | Belongs in the sellable bundle |

Verdicts: >=30 SELL NOW, 22-29 FIX-THEN-SELL, <22 HIDE/CUT.

Competitor price anchors (web search, Sep 2026): Bloomberg Terminal ~$28-32k/seat/yr (PORT/MAC3/MARS/OVDV included, MAC3 expanded Apr 2026 to private markets); Axioma liquidity/risk six figures/yr; FactSet Attribution/StatPro $50-200k/yr; Koyfin $15-79/mo (Premium $79/mo unlocks risk/hypotheticals); TradingView ~$13-60/mo; Riskfolio-Lib/PyPortfolioOpt/skfolio free OSS (optimizers, HRP, CVaR, BL basics); V-Lab free academic (GARCH/DCC vols and correlations, no trading UI); QuantConnect cloud backtest w/ point-in-time, fees, slippage (no DSR/PBO product surface).

## Counts

SELL NOW: 3. FIX-THEN-SELL: 18. HIDE/CUT: 1. Total scored: 22.

## Portfolio V2 (13 engines)

| ID | Feature | E | P | W | H | T | D | M | B | Total | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F01 | Construction (9 objectives, 8 cov estimators, HRP, CVaR-LP, BL) | 4 | 3 | 3 | 3 | 2 | 4 | 2 | 5 | 26 | FIX |
| F02 | Honest backtest (DSR, PBO, PSR, MinTRL, HLZ, walk-forward) | 4 | 4 | 5 | 3 | 2 | 4 | 4 | 5 | 31 | SELL NOW* |
| F03 | Attribution (Brinson/Fachler, linking, drawdown, skill-vs-luck) | 3 | 4 | 4 | 3 | 3 | 3 | 3 | 5 | 28 | FIX |
| F04 | Stress (historical replay, reverse Mahalanobis + percentile, MC, corr break) | 4 | 4 | 5 | 2 | 4 | 4 | 4 | 5 | 32 | SELL NOW |
| F05 | Macro factor (price-derived VIX/curve/OAS/USD, MCTE, crowding) | 3 | 3 | 3 | 4 | 3 | 3 | 2 | 4 | 25 | FIX |
| F06 | Regime (HMM/GMM/vol fallback, KM survival, transitions) | 3 | 4 | 4 | 4 | 2 | 4 | 3 | 4 | 28 | FIX |
| F07 | Liquidity (Amihud, DTL, LVaR, crisis gap, schedule, half-life) | 4 | 4 | 5 | 2 | 3 | 2 | 3 | 4 | 27 | FIX |
| F08 | Correlation/contagion (eigenvalue, ENB, MST + precision dual, crisis delta) | 5 | 5 | 4 | 3 | 3 | 4 | 5 | 5 | 34 | SELL NOW |
| F09 | Alpha decay (IC curve, half-life, optimal rebalance, crowding, capacity) | 3 | 4 | 3 | 2 | 2 | 4 | 4 | 3 | 25 | FIX |
| F10 | Kelly sizing (multi-asset, drawdown cap, ruin surface, turnover f*) | 3 | 4 | 4 | 2 | 2 | 4 | 4 | 4 | 27 | FIX |
| F11 | Execution/TCA (AC trajectory, IS frontier, multi-asset schedule) | 2 | 3 | 3 | 3 | 2 | 2 | 3 | 4 | 22 | FIX (borderline) |
| F12 | Systemic/fire-sale (overlap, DebtRank, spiral, cascade) | 2 | 4 | 2 | 1 | 5 | 2 | 3 | 2 | 21 | HIDE/CUT |
| F13 | Multi-strategy (Kelly across sleeves, tilt, kill switch, netting) | 3 | 3 | 3 | 2 | 3 | 2 | 2 | 3 | 22 | FIX (borderline) |

*F02 SELL NOW with a stats errata (see fixes). Trust is 2 (DSR trials = asset count, HLZ wrong units, MinTRL off ~252x) but WTP/parity carry it; ship with corrected numbers, not as-is.

### Why each score (one line per feature, load-bearing gaps named)

- F01 (26 FIX): wired and 9 objectives real, but SLSQP failures return silent 1/N, frontier holds infeasible points, BL has no views plumbing (always reverse-GMV), binding report hardcoded, OSS covers the basics (M2). Fix B2-class fallbacks + cvxpy certificates first.
- F02 (31 SELL NOW*): DSR+PBO+PSR+MinTRL+H LZ combo exists nowhere at prosumer level (QuantConnect has no DSR/PBO surface; PORT has no overfitting correction). WTP 5 = fundraising-grade honesty. Trust 2 is the asterisk: trials input, HLZ scale, MinTRL units must be fixed before quoting numbers.
- F03 (28 FIX): Brinson/Fachler + Carino/Menchero/GRAP linking real, but `benchmark` input ignored (always equal-weight universe), factor decomposition is holdings-weighted mean not FF loadings x returns, skill bootstrap is iid not within-sector 10k. Fix benchmark plumbing + label the proxy.
- F04 (32 SELL NOW): reverse Mahalanobis projection + chi2 plausibility percentile is the strongest single implementation in the module; crisis menu + block-bootstrap MC + flat-rho corr break are honest sketches. Replay is own-history not factor-mapped (disclosed proxy). Event-driven habit (H2) is the only drag.
- F05 (25 FIX): regressions + Newey-West + MCTE real, but targets/bands/budgets/fair-value missing, Ridge regularization inconsistent, MAC3 is the comp and we are price-derived-only. Daily-monitor habit (H4) is its strength.
- F06 (28 FIX): HMM/GMM/vol chain + KM survival + transitions real, but allocation is `1 + sharpe/4` heuristic, not the spec's probability-weighted per-regime optimum. Fix = actually optimize per regime.
- F07 (27 FIX): Amihud/DTL/schedule/half-life real and compliance-adjacent (W5), but UI `aum` vs backend `portfolio_nav` means every UI run prices $1M not $100M (D2), crisis 5x/0.30x hardcoded, schedule orderly-only. One-key NAV fix unlocks it.
- F08 (34 SELL NOW): strongest feature in either module. Crisis-delta, eigenvalue, MST + precision-matrix dual, sector blocks all real. Deductions only for ENB formula mislabel and trend-break "Chow-F" with no p-value. Relabel, ship.
- F09 (25 FIX): IC fit + half-life + optimal rebalance real, but crowding percentile is an arbitrary affine map, Kyle lambda hardcoded, taxonomy path (no forced fit for judgment factors) missing. Monthly habit (H2) caps it.
- F10 (27 FIX): Kelly core + f* + ruin/drawdown real, but cap-before-fraction ordering understates fractional Kelly and `port_mu` is cross-sectional mean ignoring weights (both WRONG). Two-line math fix.
- F11 (22 FIX borderline): AC closed form real, but IS 35/65 split hardcoded with delay always 0, volume profile synthetic U-shape, and no target-weight input in UI so every UI run trades zero (E2/D2). Wire target weights + label assumptions or hide.
- F12 (21 HIDE): best disclosure in the module (honest refusal, T5) but from the UI it is always a refusal stub (no peer-upload input): nothing to sell, quarterly habit, weak bundle fit. Hide until peer/13F upload exists. Do not delete; the math is real.
- F13 (22 FIX borderline): strategy proxies with explicit note are honest, Kelly/tilt/kill-switch/netting real, but correlation constraint unenforced, kill-switch backward-only, no strategy-returns upload in UI (D2). Wire the upload.

## Volatility V2 (F1-F9)

Hard cap: D <= 2 everywhere. Backend is mounted but all 9 pages render with no `onRun`; Run does nothing (VOL review B1). Backend math ranges partly-correct to mostly-fine, but silent SPY/VIX-synth/zero-fill fallbacks (B2) tax Trust.

| ID | Feature | E | P | W | H | T | D | M | B | Total | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V01 | Multi-estimator (CC/Park/GK/RS/YZ, DM/QLIKE, Bandi-Russell, range-corr) | 3 | 4 | 3 | 5 | 4 | 2 | 2 | 5 | 28 | FIX |
| V02 | GARCH suite (20-model arch MLE, MCS, NIC, term bands, PIT, VaR) | 3 | 4 | 4 | 3 | 2 | 2 | 4 | 5 | 27 | FIX |
| V03 | HAR suite (8 variants, HAC, MCS, jump/leverage/ACSV, bands, walk-forward) | 3 | 5 | 4 | 3 | 2 | 2 | 5 | 5 | 29 | FIX |
| V04 | Regime (SJM + HMM + EW-HMM ensemble, survival, transitions, sync) | 3 | 4 | 4 | 4 | 2 | 2 | 4 | 4 | 27 | FIX |
| V05 | VRP monitor (GARCH/HAR/rolling physical, BTZ, OU half-life, term structure) | 2 | 4 | 4 | 4 | 2 | 2 | 3 | 4 | 25 | FIX |
| V06 | Connectedness (DY FEVD, frequency split, CaR, IRF bands, network) | 3 | 5 | 4 | 2 | 3 | 2 | 5 | 4 | 28 | FIX |
| V07 | Multivariate/DCC (sample/EWMA/LW, 2-stage DCC-GARCH MLE, attribution) | 3 | 4 | 3 | 2 | 2 | 2 | 3 | 4 | 23 | FIX |
| V08 | Vol stress (4 presets, Mahalanobis/GLASSO analogs, MC VaR/CVaR, IRF) | 3 | 3 | 3 | 2 | 3 | 2 | 2 | 4 | 22 | FIX (borderline) |
| V09 | Vol budget (EWMA ex-ante targeting, regime targets, Kelly, cost netting) | 3 | 3 | 4 | 4 | 3 | 2 | 3 | 4 | 26 | FIX |

### Why each score

- V01 (28): formulae correct (Parkinson fix landed), DM/QLIKE + agreement + fragility real; crypto/FX YZ branch silently drops overnight leg; textbook moat (M2); daily habit (H5) is its money trait. Wire + warn.
- V02 (27): 20-model `arch` MLE + MCS + term bands genuine vs V-Lab single-model pages; DM table is a stub (no pairs/p-values), FIGARCH-d and Nyblom are proxies, PIT Gaussian-only, realized-GARCH unscored. Fix DM + per-distribution PIT.
- V03 (29, highest vol): 8-variant HAR + HAC + MCS + bands has no product equivalent (P5/M5). Trust 2 is load-bearing: HAR-X uses inline `vix/100 - yz` instead of Feature 5 expectation, ACSV uses every loaded asset instead of the selected universe. Fix those two lines and it is the fourth SELL NOW.
- V04 (27): SJM/HMM/EW-HMM + survival + sync real, but ensemble weights 0.45/0.20/0.25/0.10 scored against rank-heuristic "realized" targets (circular). Re-wire scoring to realized vol outcomes.
- V05 (25): GARCH-physical VRP + BTZ/Hodrick + term structure real, but missing VIX is synthesized as `yz*115` making VRP a rescaled copy of itself (E2/T2), HAR-physical fixed-weight, regime BTZ uses YZ rank not Feature 4. Fail-closed on missing VIX first.
- V06 (28): BIC-VAR + generalized FEVD + frequency split + CaR + IRF bands real; rolling index steps ~len/300 not daily, rolling loop ignores EW selection, alert threshold unhonored. Academic moat (M5, no retail DY product).
- V07 (23): two-stage DCC-GARCH MLE genuine (beats V-Lab display), but `dcc_proxy = ewma.copy()` lies by name, time series chart is rolling Pearson not the DCC path, normal/crisis definitions naive. Export the real path, rename the proxy.
- V08 (22 borderline): scenario stack + MC + IRF real; Clayton copula computed-but-unused, adversarial is discrete search not PGO, recovery-time and GLASSO-alpha arbitrary. Most substitutable by MARS (P3/M2).
- V09 (26): lookahead fix landed, cost-netted ex-ante scaling real, regime targets parsed-but-ignored (frontend string vs backend dict), Kelly uses historical mean mislabeled BTZ-implied. Operational daily habit (H4/W4) is the sell.

## Top 3 money features

1. Portfolio F08 Diversification/Contagion (34): crisis-delta + eigenvalue + MST/precision dual. Nobody prosumer has it; committee-demo gold. Ship after two relabels.
2. Portfolio F04 Reverse stress (32): Mahalanobis + plausibility percentile vs MARS $25k+/yr. The IC-signoff question, answered with a probability.
3. Portfolio F02 Honest backtest (31*): DSR/PBO/MinTRL vs QuantConnect honesty gap and PORT's missing overfitting correction. Fundraising-grade. Asterisk = fix trials/HLZ/MinTRL units first (small, bounded).

Challenger: Vol V03 HAR suite (29) becomes #4 the day HAR-X reads Feature 5 and ACSV honors its universe input.

## Bundle and price

- Bundle A, "IC-Ready Portfolio" (sell now + near): F08, F04, F02* + F06, F07, F01, F03, F10. Story: construct, prove honest, attribute, stress, regime-tilt, liquidate. F05/F09 join after their fixes; F11/F13 stay out until inputs wired; F12 hidden.
- Bundle B, "Vol Desk" (gated on wiring): V03, V06, V01, V04, V02, V05 + V09 operating layer. Story: measure, forecast, regime-condition, connect, budget. V07/V08 include as diagnostics, not headlines.
- Cross-bundle bridge (demo flow): F06<->V04 regimes, F08<->V06/V07 correlation, F04<->V08 stress. One narrative, two checkouts.
- Price: comps say Bloomberg $28-32k/seat and Axioma six figures above, Koyfin $79/mo and TradingView $13-60/mo below, OSS free at the bottom. Position Bundle A at $199-249/mo solo / $1.5-2k/mo team (IC-grade stats OSS and Koyfin cannot produce, 100x under Bloomberg). Bundle B at $99-149/mo solo (vol-desk niche, V-Lab is free but not tradable). Combined $299/mo solo. Do not price against free (Riskfolio/V-Lab); price against the committee meeting and the compliance filing.

## Distribution moves (in order)

1. Wire Vol UI (B1): pages pass `response`/`onRun` via the Portfolio/Factors React-Query pattern; heavy jobs (V02 MLE, V04 restarts, V08 100k MC, V09 regime call) via job transport with progress/cancel. Unlocks D2 -> D4 across all nine.
2. Kill silent fallbacks (both modules): unknown tickers 422, no SPY substitution; no synthetic VIX (physical-only mode or 422); no zero-filled HAR-X macro; parse-or-reject string `weights`. Every silent fake is a refund risk.
3. Fix the $1M-vs-$100M bug: one NAV key (`aum` vs `portfolio_nav`, registry F07/F11 vs backend). Demo-blocker for the liquidity story.
4. Manifest-driven inputs: serve backend INPUTS/OUTPUTS from GET /features; render UI from it. Kills `objective: min_variance` serving max-Sharpe, preset-name drift (`gfc_2008` vs `gfc`), `regime_targets` string-vs-dict.
5. De-fake the frontend: delete sine `Spark`, label synthetic surfaces illustrative, drop cross-type fallbackKeys (no calendars made of efficiency tables), live-or-labeled landing numbers.
6. Stats errata batch (small, bounded): F02 trials/HLZ/MinTRL, F10 Kelly order + weight-aware mu, F08 ENB label + Chow relabel, F06 per-regime optimum, V03 HAR-X + ACSV wiring, V02 DM + PIT, V07 DCC path export. Each is a named line, not a project.
7. Proof artifacts: golden-number tests per engine (vs riskfolio-lib closed forms, Brinson identity, Mahalanobis projection, estimator fixtures) + silent-fallback guard tests. Required before any SELL NOW demo is quoted.

## Path

Now (sellable today): F08, F04, F02* (with errata disclosed and fixed first; F02 numbers must not ship as-is). Hide F12 everywhere (nav, landing pills, docs screenshots). Everything else stays behind "Beta / fixing" labeling, led by V03 and F07 (closest to the line once wiring + NAV + two math lines land). One wiring sprint (moves 1-4) converts ~10 FIX rows into SELL NOW candidates; the stats errata (move 6) is the second gate. Do not add features until D >= 4 on every SELL NOW row.
