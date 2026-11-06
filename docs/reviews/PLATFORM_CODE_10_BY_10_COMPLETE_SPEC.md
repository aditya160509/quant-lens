# Platform Code 10/10 Complete Spec: Correctness, Truth, and Implementation Bar

Date: 2026-09-29
Scope: Studio workspace + 7 V2 modules (Factors F01-F14, Research F1-F11, ML F01-F12, PCA F01-F11, Portfolio 13 engines, Volatility F1-F9, Screener S1-S8).
Aspect: **10/10 CODE + QUANT CORRECTNESS ONLY** (not sellability). Meaning: correct math, no look-ahead, no fabricated numbers, right libraries, wired runs, golden tests, honest labels.
Sources: `docs/reviews/*_V2_REVIEW.md` (8 audits), live contracts/registries, max open-source research (alphalens, pyfolio, quantstats, linearmodels, statsmodels, arch, pyfixest, rdrobust, pysyncon, Riskfolio-Lib, PyPortfolioOpt, skfolio, cvxportfolio, mlfinpy, pypbo, ruptures, umap, SHAP, Optuna, MLflow).

## Global 10/10 Rules (all modules)

KEEP: `STANDARD_OUTPUT_SCHEMA` envelope; sklearn/hmmlearn/scipy/cvxpy/statsmodels cores; React Query run hooks; one chart lib.
REPLACE:
1. 7x `core/data_loader.py` -> one `backend/app/services/shared/market_data.py` (`load_prices`, `load_pit_fundamentals(lag_days=90)`, `load_french_factors`, `parse_symbols_strict` 422, never silent).
2. 7x `customPagePrimitives.jsx` (10,754 lines) -> one shared Lab workbench + renderer registry.
3. Hand HAC loops -> `statsmodels.stats.sandwich_covariance.cov_hac` (Bartlett, auto-lag).
4. Hand `registry.js` contracts -> render from `GET /features` = `registry.feature_manifest()`.
REMOVE: all `dormant` badges; demo sine/fake numbers as normal path; server-path inputs (use upload IDs); silent universe fallbacks; inert/accepted-but-ignored options.
DATA MUST: PIT fundamentals or price-only gate + banner; `price x shares` monthly cap; French FF5+MOM cached parquet with `data_through`; FX loader or US-only gate; 422 with missing tickers.

## Factors V2 (F01-F14) — Code 10/10

- F01: REPLACE FF-return spread with PIT characteristic spread (alphalens pattern), hand HAC with `cov_hac`. REMOVE synthetic filler rows. NEED: PIT B/M-E/P-profit, gauge + history + correlation heatmap, golden HML test.
- F02: REPLACE portfolio-OLS proxy with Barra two-leg (holdings z-scores + `PanelOLS` clustered/DK). REMOVE silent `head(30)`. NEED: CI bands, sector-neutral toggle, stacked bar + heatmap.
- F03: REPLACE carryover proxy with Brinson-Fachler allocation/selection/interaction + F09 costs. REMOVE equal-weight default. NEED: waterfall + IR bar, sum=return identity test.
- F04: KEEP HMM/GMM/rules. REPLACE 3->4 states, fixed 63d with input lookback, add valuation/crowding timing, breaks with `breaks_cusumolsresid` + Andrews table. NEED: probability area + transition heatmap, GFC/COVID fixture.
- F05: REPLACE proxy significance with `MovingBlockBootstrap` 1000 reps; add Pearson + beta-neutral IC. NEED: decay curve + rolling half-life, DGP recovery test.
- F06: REPLACE equal-only with weighted/bayesian; fix CI label. REMOVE undocumented sign inversion. NEED: time series + scatter + league, HHI golden test.
- F07: REPLACE deciles with alphalens quantiles, stats with quantstats/pyfolio, costs from F09. REMOVE duplicate ADV curve. NEED: gross/net equity + underwater + quintile bars, PIT gate.
- F08: VERIFY local recursion vs `arch_model(p=1,q=1)` + bound. REMOVE EWMA labeled DCC. NEED: corr/cov heatmaps + rolling corr + eigenvalues, PSD test.
- F09: REPLACE 2 cases with 20-pt AUM sweep; memo to allocator one-pager. NEED: Sharpe-vs-AUM + slippage curves, monotonicity test.
- F10: REPLACE robust label with real SOCP or relabel; FAP corr with OLS on exposures. REMOVE hash key (blake2b). NEED: 50-pt frontier + weights + risk contrib, sum-to-1 test.
- F11: REPLACE IRF bands with VAR refit resample + full path export. REMOVE macro-linked label. NEED: waterfall + IRF + contagion, hit-threshold identity test.
- F12: REPLACE radar scales with z/percentile + units; 3->6 regimes; honor depth/focus. REMOVE always-run-4. NEED: radar + regime + correlation bars, archetype test.
- F13: REPLACE autocorr drift with true rank IC or relabel persistence; Chow proxy with CUSUM + Andrews/ruptures. REMOVE webhook UI + frontend -1.0. NEED: health series + CUSUM bands + alert log, break-fixture test.
- F14: REPLACE title-only PDF with quantstats/pyfolio-style embedded PNGs server-side; JSON block with prose + appendix. REMOVE unbounded cache + silent ok. NEED: figures per section, DDQ table, async job + page cap.

## Research V2 (F1-F9 + F11) — Code 10/10

- F1: REPLACE GMM/Shanken with `LinearFactorModel` + `LinearFactorModelGMM` + J-test; SEs with `FamaMacBeth` + `PanelOLS` DK/cluster; GRS with MLE + dof exact; MR with recentered block bootstrap; fake `|t|>2.1` with real or delete. REMOVE Shanken-on-characteristics. NEED: French 25-portfolio GRS golden test + sequential sorts + N/T flag.
- F2: REPLACE grid with crisis/splits/universe/transform/SE spec grid + full spec-curve + SPA/MCS/StepM + dummy attribution. REMOVE signal-mixing rows. NEED: spec curve + heatmap, null-centers-zero test.
- F3: REPLACE permutation with same-FM-kernel rerun; t-ratio degradation with coef degradation; fake power with null-simulated power. REMOVE equity-ticker adjacent class + wrong-direction from combiner. NEED: null histogram + OOS line + 4-placebo verdict card.
- F4: REPLACE ANOVA-Chow with real Chow/CUSUM-Andrews; dummies-only with `signal x regime` + HAC; signal-mean search with conditioning-var search + guard. NEED: premia bars + F-scan, break-DGP test.
- F5: REPLACE stacked-panel input with lambda-series + per-asset residuals; Andrews path with table + CI/ruptures. REMOVE row-index-only influence. NEED: QQ + partial-residual + leverage plots.
- F6: VERIFY column config vs linearmodels. NEED: LaTeX-compiles test.
- F7: REPLACE DiD with pyfixest TWFE/did2s/SA; CS with `differences` ATT(g,t); RD with rdrobust/rddensity cross-sectional; IV with IV2SLS/LIML/GMM + Sargan/Wu-Hausman; CAR with multi-event study. REMOVE all `_proxy` wearing real names; hide behind prototype banner. NEED: events CSV upload, ATT/RD/IV tables, recovery tests.
- F8: REPLACE origin with required `t_discovery`; IID 99 with block 1000; whole-scan with post-discovery + CI; arbitrary formulas with sort or heuristic label. NEED: decay-from-discovery chart, DGP test.
- F9: REPLACE augmented/generalized/robust/conformal with pysyncon Synth/AugSynth/Penalized + placebo p-values; returns-only with levels + predictors + donor filters. NEED: gap + placebo + weights charts, Basque-style fixture.
- F11: REPLACE typed threshold with computed HLZ hurdle + DSR; mislabeled IC-IR with true rank IC; FF5-only with quality/low-vol/BAB/STR. NEED: hurdle scatter, duplicate-flag test.

## ML V2 (F01-F12) — Code 10/10

- F01: REPLACE loops with `PurgedGroupTimeSeriesSplit`; hand DSR/PBO with pypbo/mlfinpy check; ignored barriers with `mlfinpy.labeling`; trials with MLflow. REMOVE uniqueness claim + unhonored model types. NEED: purge test, golden DSR/PBO.
- F02: REPLACE split with purged Pipeline (scaler-train-only); grid with Optuna TPE + MLflow; equal weights with decay/uniqueness; static registry with manifest. REMOVE SHAP-as-attribution + unhonored targets. NEED: leakage test, purged CPCV IC.
- F03: REPLACE sqrt scaling with per-horizon direct + block CI; disconnected macro with HAR-X; GINN placeholder with torch LSTM job. REMOVE horizon limit + F12 inputs. NEED: MZ + DM tests.
- F04: REPLACE momentum-only with `get_events/get_bins/meta_labels`; flat bps with spread + sqrt impact. REMOVE external routing realtime. NEED: event upload path.
- F05: REPLACE PPO panels with SB3 job or delete; add BL view editor. REMOVE realtime RL-compare/tail/rolling-Sharpe + unbound cap. NEED: dendrogram + heatmap + risk contrib.
- F06: REPLACE RF-vote with XGB+RF+HMM proba vote; in-sample agreement with OOS purged; add CUSUM/ruptures; localStorage with MLflow + store. REMOVE dead alert. NEED: agreement-OOS test.
- F07: REPLACE 5 members with registry up to 20; ad-hoc uncertainty with labeled epistemic/aleatoric. REMOVE unrunnable options + fake timer (job + cancel). NEED: member-registry test.
- F08: REPLACE silent dml_ape fail with fallback + warning + store; single IC with purged CPCV + block CI. NEED: weight + CI test.
- F09: REPLACE rule-score with purged RF or permanent fast-score label; hand Q/R with MLE + MLflow. REMOVE RL realtime. NEED: half-life/ADF golden test.
- F10: REPLACE gated cpcv with 422-or-downgrade; keep tick placeholders researchOnly + banner. REMOVE intraday realtime. NEED: estimator-definition test.
- F11: REPLACE HC3-only with clustered SEs; silent zeroing with exposed policy; memory APE with ape.parquet + MLflow. REMOVE hard labels as truth. NEED: known-APE DGP test.
- F12: REPLACE stand-ins with torch Transformer/PatchTST/TFT job + MLflow; positional split with named lookup; fake time with measured. REMOVE realtime depth/heads/dropout + proxy screenshots. NEED: watermark-survives-export test.

## PCA V2 (F01-F11) — Code 10/10

- F01: REPLACE hand-MP with pyRMT check + sklearn PCA golden test; cov-only with corr/StandardScaler branch (Kaiser only there); scalar max with density series; weak MCD with T>2N else LedoitWolf. REMOVE silent clip + rolling claims. NEED: spike-recovery + MP + condition tests.
- F02: REPLACE Phi with textbook or empirical label; dict cluster with real clustergram + dendrogram; unsigned rolling with sign-aligned; add biplot type. NEED: eigh-vs-PCA equivalence test.
- F03: REPLACE always-cleaned with source toggle; add PORT exposure/MRC/waterfall tables. REMOVE FX-hedge claim. NEED: risk-budget-sums test.
- F04: REPLACE swallowed volume-time with surfaced meta; flat bps with spread/sqrt. NEED: OU golden test.
- F05: REPLACE hardcoded thresholds with wired inputs; hand breaks with CUSUM + ruptures. REMOVE free-text windows. NEED: break-recovery test.
- F06: REPLACE asset-only BL with PC views + editor; single K with rolling backtest. REMOVE sector/factor/TE/cardinality claims. NEED: weights-sum + monotonic tests.
- F07: REPLACE hand-only with arch oracle check; silent caps with requested_vs_executed + research defaults. NEED: golden-spectra test.
- F08: REPLACE fixed-model rolling with rolling-refit option; sector-only with CSV upload. NEED: refit-vs-fixed test.
- F09: REPLACE diagonal MC with full factor cov; single portfolio with 4-compare. NEED: joint-tail test.
- F10: REPLACE OAS-as-LW with real LedoitWolf; sample PCA with unified RMT + block MP + DCC shrinkage; share-only with full heatmap + series; ignored blocks key with fix/422. REMOVE roll-adjusted claims. NEED: unified-cleaning test.
- F11: REPLACE hand HAC with statsmodels verify; PC1-only with MP-K + IML. REMOVE turnover claim. NEED: HAC-oracle test.

## Portfolio V2 (13 engines) — Code 10/10

REPLACE: hand minimize + HRP approx with `Riskfolio-Lib Portfolio + assets_stats + optimization + efficient_frontier(50)` + PyPortfolioOpt/skfolio referee; metrics/sim with quantstats + `cvxportfolio MarketSimulator`; F05 OLS with `skfolio.FactorModel` + HAC + LedoitWolf; F06 GMM with `GaussianHMM(3,full)` + Viterbi; F11 impact-only with `SinglePeriod/MultiPeriodOptimization + TransactionCost + HoldingCost` + Almgren-Chriss frontier. KEEP: Brinson core (charts to plotly Waterfall), history core (MC to arch shocked paths + PORT builder + stressed PSD), Amihud/DTL (add calibration + 30d cap), corr/ENB/edges (viz to force graph), IC decay (add half-life fit), Kelly (add 0.25-0.5x cap + 20% max). REMOVE: F12/F13 numbers until 13F/strategy books land (gated shells with access_issues). CHARTS: plotly frontier(50) + markers, lightweight-charts series, Waterfall, fan/cone, force network, quantstats blocks. COSTS: spread + sqrt + holding + tax-lots; turnover + DTL@15% + LVaR on every answer. TESTS: weights-sum 1e-8, RC-sums-to-vol, frontier-reproduces, gross-costs=net, PSD, no-lookahead WF.

## Volatility V2 (F1-F9) — Code 10/10

- F1: KEEP estimators; ADD efficiency disclosure + ann-factor test + overnight flag; fan via lightweight-charts.
- F2: REPLACE hand-MLE with `arch_model(GARCH/EGARCH/APARCH/FIGARCH, t/ged/skewt)` + fit + AIC/BIC + 22d forecast; delete MODEL_PARAMS.
- F3: REPLACE OLS-HAR with `HARX(1,5,22)` + log-RV + HAC + MZ + DM.
- F4: KEEP HMM; ADD V-Lab bands + VIX overlay + persistence.
- F5: KEEP shell; GATE on IV (proxy banner); ADD VIX term + `VRP=IV-E[RV(HAR)]`.
- F6: KEEP FEVD/VAR; viz to directed network + heatmap + spillover index.
- F7: KEEP DCC + GL/LW; ADD cho_solve + PSD + wTΣw test + skfolio referee.
- F8: REPLACE generic shocks with macro-named (VIX40/+100bps/+200bps) + GARCH paths + VaR repricing.
- F9: KEEP RC math; ADD `RC=w(Σw)/σ` assertion + rebalance cost.
TESTS: estimator-reconcile, PSD, weight-sum, frontier-monotonic, cone-coverage 70-90%.

## Screener V2 (S1-S8) — Code 10/10

- S1: REPLACE grid with TradingView filter panel (grouped + operators + chips + count <300ms); table with TanStack Table+Virtual+Query server 25/50/100 + sticky ticker; add units kit. REMOVE saved_screens stub, DEMO_TICKERS, sin D1-D96, random Sharpe, fake funnel, silent top-500 (422). NEED: envelope-tested run, saved views (URL+storage), column sets, visible-CSV, aria-live, keyboard, handoff.
- S2: REPLACE textarea with Monaco + autocomplete + diagnostics; fallback with MethodBadge; registry with manifest fetch. REMOVE score_backtest-as-validation. NEED: unit + golden formula tests + as_of picker.
- S3: REPLACE seeded bootstrap with walk-forward IC; regime_proxy with sector_breakdown or real regimes; current ridge with lagged. REMOVE regime key + fake 3D. NEED: proxy labels, ComputeBadge, versioning.
- S4: REPLACE placeholders with spec or proxy badge + note; snapshot test with survivorship header + PIT badges. REMOVE 8-list (manifest render) + random Sharpes. NEED: searchable ⌘K, formula + PIT per card, golden Piotroski/Altman.
- S5: REPLACE weekday smear with rebalance-date parity; offset PBO with combinatorial + DSR; pandas with polars scan. REMOVE V1 random stub + unattributed single-date + 9k/20k defaults. NEED: event-order persistence, editable slippage, SSE + cancel, golden + look-ahead tests.
- S6: REPLACE entered-only with persisted diff; 3 knobs with full surface; none with Beat + delivery log. REMOVE precision-None + misnamed log. NEED: diff test, percentile alerts, schedule, history, ⌘K, provenance.
- S7: REPLACE window with 252/756/2520 presets; coarse heatmap with median + counts + diverging legend + domain switch; fixed charts with Quick-Look template. REMOVE fake waterfall. NEED: peer counts, keyboard + CSV, formatters, 1+3 compare, PNG + data.
- S8: REPLACE copy-JSON with ExportMenu (CSV/TSV/Parquet/JSON + visible + manifest); wired:false with live manifest; stub change_report with real diff after S6 store. REMOVE scheduler/ML claims + drift. NEED: parity export, manifest-replay, contract test.

## Studio Workspace — Code 10/10

- Develop: REPLACE exec() with isolated worker + typed records; playIndex rerender with rAF + hashed precompute; Canvas default + worker + Pixi only dense; god store with finished Zustand + server truth + cancel; dead ⌘K with cmdk. REMOVE synthetic OHLCV/momentum fallback/random/marketing grids. NEED: warm kernel + idle kill, real terminal, inspector + staleness, CRUD + diff, breakpoints + traceback, run-cell/file/strategy, PIT preview, virtualization, keyboard + table per chart.
- Results: REPLACE card grid with MetricStrip + dominant chart + linked diagnostics; hard-coded/MAE-random with real excursion/holding; canvas one-offs with kernel series. REMOVE invented zeros/unsupported attribution. NEED: gross-net + cost drag, benchmark-relative, rolling/underwater, VaR/CVaR + episodes + concentration, Brinson + waterfall, excursion/slippage/quality, 1+3 compare, units/method/sample/provenance per metric, manifest exports.
- Validate: REPLACE verdict with per-test evidence + batched MC + real surface + merged Quick/Stability/OOS/Costs/Scenarios/Cert page. REMOVE 9k/20k defaults, random WF, Dynamics. NEED: navigator + presets + registry + jobs, purge/embargo, per-fold rerun, sensitivity, break-even + ADV + capacity, crisis/macro/custom + bootstrap, test-by-test cert, tiered compute, persisted seeds, idea→backtest→paper gate.
- Replay: REPLACE playIndex with deterministic bar/signal/submit/fill/cost/MTM + positions/cash/exposure/orders/signals/variables/risk + decision trace; single chart with synced multi-chart; player with rAF timeline + jumps/snapping. REMOVE unreproducible reconstruction + card grid. NEED: 4 modes, lifecycle + overlays, preserved layout, gaps layer, bookmarks/clips, collapsible dock, keyboard + SR list, determinism tests, Core-vs-Job split, shareable URL.
- Compose: REPLACE sparkline with kernel MetricSparkline + server IDs; stringify with typed cells; modal-less with dialog trap; copy-JSON with ExportMenu + manifest. REMOVE uncited commentary + unprovenanced blocks. NEED: versioned binding, badges, template binding, views + snapshot, deltas + uncertainty, citations, keyboard reorder, export parity, Beat-only schedule.
- Paper: REPLACE all-loads with Query cache + validated forms + SSE stream + Jobs drawer (SSE not WS); blanket Unavailable with typed cells + quality/latency + limitations. REMOVE duplicated execution control. NEED: deploy gate, parent-linked ledger, divergence view, account state, breaches + pre-trade, assumptions, IDs, cancel/retry + stale guard, manifest export, reset audit, limitations banner.

## Done Means (code aspect)

No silent fallback; every proxy labeled; every estimator has a golden test vs its reference library; every run is wired end to end with envelope-tested contract; PIT or banner; 422 with names on unknown tickers; one shared loader + one workbench; deps pinned; DONE.md updated (current ones overstate).
