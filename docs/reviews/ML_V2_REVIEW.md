# ML V2 Review: Spec vs Implementation vs Frontend

Date: 2026-09-29
Scope: `backend/app/services/ml_v2/` (spec: `docs/ml_final_features.md`, 644 lines, 12 features; code: `core/analytics.py` 2,986 lines, `core/data_loader.py` 313 lines, `core/performance.py`, 12 feature files with `INPUT_CONTRACT`/`OUTPUT_CONTRACT`/`run()`), `backend/app/api/ml_api.py` ML V2 routes + mount in `backend/main.py`, `frontend/src/app/labs/ml-v2/`, `frontend/src/components/ml-v2/`, `frontend/src/lib/api.js`, `backend/tests/`.

Evidence basis: every line of `registry.py`, `core/data_loader.py`, all 12 `features/feature_*.py` contracts, `frontend/src/components/ml-v2/registry.js`, `frontend/src/lib/api.js` ML V2 helpers, and `core/analytics.py` sections for F01 (`run_cpcv_engine`), F02 (`run_gbt_alpha`), F05 BL (`run_hrp_optimizer` posterior block), F08 IC-IR, F10 `signal_families`, F12 proxies was read in current code. F03/F04/F06/F07/F09/F11 engine bodies are carried from the 2026-07-12 audit (`ml_v2/review.md`, 566+ lines) plus the `README.md` changelog, which documents exact fixes since; those items are marked "carryover, re-verify" where current code was not re-read. No runtime smoke was run (read-only brief).

Prior audits fixed real bugs before this review: DSR is now a proper Bailey-Lopez de Prado probability (`analytics.py:453-462`), PBO is the empirical fraction below median (`:465-470`), embargo sensitivity does real CPCV re-runs at E=0/5/10/21 (`:673-687`), zero-IC models get zero weight (`:755-757`), ticker hash is deterministic blake2 (`:1224`), F08 IC-IR is `mean/std` (`:2131`), `signal_families` is honored (`:2708`), fabricated SHAP beeswarm/waterfall now return empty with `disabled_no_fabricated_values` status (`feature_02.py:45-46`, `analytics.py:839-840`), and F05 Black-Litterman is full posterior math with tau, views, and bounds (`analytics.py:1594-1610`). Credit where due. The review below is about what is still wrong and whether a user can reach it.

---

## 1. Verdict

| Area | State | One line |
|---|---|---|
| Wiring (backend to frontend) | **Broken** | The route exists but the frontend calls the wrong URL, so every Run 404s. |
| Data integrity | **Broken** | Unknown tickers silently fall back to the default universe in two places. |
| Train/test hygiene | **Broken outside F01** | F02 splits a ticker-major stacked panel 75/25 with no date sort and no purge; F01 sorts correctly. |
| Feature 1 (CPCV) | Mostly correct | Real purge, embargo, CPCV paths, fixed DSR/PBO, but `triple_barrier` label type is accepted and ignored. |
| Feature 2 (GBT alpha) | Partly correct | Real ensemble/IC/decay, honest proxy labels, but no Optuna, no sample weighting, no universe filter. |
| Feature 3 (vol) | Partly correct | HAR-Ridge/GBM, GK/YZ, GARCH-AIC, spillover real; GINN and HAR-X integration missing. |
| Feature 4 (triple barrier) | Mostly fine | CQR + calibration real per changelog; primary model still momentum-only. |
| Feature 5 (HRP/BL) | Mostly fine | HRP/NCO/HERC/BL math real; RL is a labeled proxy; sector-cap input needs a binding check. |
| Feature 6 (regimes) | Mostly fine | Gaussian HMM Baum-Welch real; ensemble is RF-only; agreement metric double-dips in-sample. |
| Feature 7 (DMA/OBS) | Partly correct | Real sequential DMA + simplex OBS; 5-model library vs spec up-to-20; uncertainty is a proxy. |
| Feature 8 (composite) | Mostly fine | IC-IR fixed, Gram-Schmidt/walk-forward/interactions real; `dml_ape` has no persisted artifact to read. |
| Feature 9 (pairs) | Mostly fine | Kalman hedge path + ADF screening real; RL threshold is a labeled proxy; "ML classifier" is a rule score. |
| Feature 10 (microstructure) | Mostly fine | Daily estimators honest, families toggle now honored; tick-level data still absent as declared. |
| Feature 11 (DML) | Mostly correct | Real K-fold cross-fit DML + HC3; LightGBM optional; causal labels are a heuristic. |
| Feature 12 (deep sequence) | **Proxy** | All "architectures" are Ridge/RF/ET on transformed inputs; attention/cost outputs are diagnostics with honest labels. |
| Tests | **None** | No `test_ml*` in `backend/tests/`; no tests dir in `ml_v2/`; only compileall + smoke per README. |
| Frontend | Shell with a live wire to nowhere | Self-contained workbench, but Run 404s; 2,361-line static registry duplicates the backend contract and already drifts. |

Bottom line: the module computes honest shapes with mostly honest labels, and the July audit fixes were real, but a user cannot run anything from the UI (wrong URL), would get default-universe results for bad tickers without warning, and gets unpurged single-split IC numbers everywhere except F01. Fix order: correct the URL, fail on unknown tickers, sort and purge the shared train/test path, then resync the frontend contract from the backend manifest.

---

## 2. Blockers (fix first)

### B1. Frontend calls a URL the backend never serves
- Frontend: `runMlV2Feature` (`frontend/src/lib/api.js:1022-1030`) POSTs to `` `${API_BASE_URL}/labs/ml/v2/feature/${normalized}/run` ``, i.e. `/api/labs/ml/v2/feature/01/run` with singular `feature` and a `labs/` prefix.
- Backend: `execute_ml_v2_feature` (`backend/app/api/ml_api.py:54-62`) serves `/ml/v2/features/{feature_id}/run` (plural `features`, no `labs/`), mounted at prefix `/api` (`backend/main.py:175`), i.e. `/api/ml/v2/features/01/run`.
- No router serves the `/labs/ml/v2/feature/...` path (`backend/app/api/labs.py` has `/ml/v2/regime`, `/ml/v2/anomalies`, `/ml/v2/montecarlo`, `/ml/v2/liquidity`, `/ml/v2/valuation`, galaxy routes, but no feature-run route). Every ML V2 Run ends in the `catch` at `customPagePrimitives.jsx:860-862`, whose fallback text ("ML V2 API route is not wired yet.") is itself wrong, since the route exists.
- The sibling convention is `POST /labs/factors/v2/feature/{id}/run` (`factors_v2.py:105`), `POST /labs/volatility/v2/feature/{id}/run`, `POST /labs/portfolio/v2/feature/{id}/run`. ML V2 is the odd one out.
- Fix (one line plus manifest): point `runMlV2Feature` at `/api/ml/v2/features/${normalized}/run`, or add a thin `ml_v2.py` router on the `/labs/ml/v2` prefix mirroring `factors_v2.py` and keep `ml_api.py` as the alias. Then fetch `GET /api/ml/v2/features` (`ml_api.py:48-51`) instead of the static registry.

### B2. Silent universe fallback
- `parse_symbols` (`core/data_loader.py:147-148`): when none of the requested tickers exist, it silently returns `universe[:default_limit]`. A user asking for "XYZ, ABC" gets results on 80 unrelated stocks.
- `load_context` (`core/analytics.py:248-250`): when post-load coverage is below `min_symbols`, it silently re-parses defaults and rebuilds on a different universe, with no flag in `meta`.
- Fix: return 422 with the missing tickers (the route already maps `ValueError` to 422 at `ml_api.py:61-62`), or at minimum set `meta.universe_substituted: true` with requested vs served lists. Same class as Research B3.

### B3. Non-chronological, unpurged train/test split outside F01
- F01 does it right: sorts the panel by date before splitting (`analytics.py:605-609`), purges `horizon` rows around each test fold plus embargo (`:624-627`, `:652-655`).
- F02 does not: `split = int(len(x) * 0.75)` (`:722`), then `x.iloc[:split]` / `x.iloc[split:]` (`:748-749`) on `make_feature_panel` output, whose rows are concatenated ticker-by-ticker (`:380-405`), never date-sorted in this path. The "test" set holds early dates of later tickers while "train" holds later dates of earlier tickers: time leakage across the panel, plus no purge/embargo for the `horizon`-day forward label (`:308`, `:356`).
- Same helper pattern feeds F08/F11/F12 (`numeric_xy` + contiguous split or `KFold(shuffle=False)` on row order at `:2295`, where folds are ticker blocks, not time blocks). IC numbers from these paths are single-split, unpurged point estimates.
- Scaling note: no `StandardScaler` touches the F02 train/test path (tree/linear models fit raw), so there is no scaler-leak to fix there; but `StandardScaler().fit_transform` on the full sample at `:1018` (regime classifier input) and `:1645-1646` (HMM/GMM input) fits on all data including the "future" relative to any OOS read of those states.
- Fix: centralize one `chronological_purged_split(panel, horizon, embargo)` helper (sort by date, purge `horizon`, embargo E), use it in F02/F08/F11/F12, and fit any scaler on the train partition only.

### B4. Accepted-but-ignored inputs
- F01 `label_type: triple_barrier` is in `INPUT_CONTRACT` (`feature_01.py:46`) and survives normalization, but `run_cpcv_engine` always builds regression forward-return labels (`analytics.py:601-602`, `:308`). Requesting triple-barrier CPCV silently runs regression CPCV.
- F12 `transformer_depth`, `attention_heads`, `dropout_rate` are in `INPUT_CONTRACT` (`feature_12.py:34-36`), but the proxies are Ridge/RF/ET (`analytics.py:2904-2907`), which take none of these. Tuning them changes nothing.
- F07 `model_library` options (`feature_07.py:29`: xgboost, lightgbm, random_forest, ridge, elastic_net, lstm, gru, har, rolling_mean) do not even contain the models actually run (defaults at `:14`: momentum, reversal, low_vol, ridge, extra_trees). Selecting `lstm`/`har` cannot do anything.
- Fix: reject unsupported values with 422 listing what realtime supports, or wire them. Never silently accept.

---

## 3. Feature-by-feature

Legend: OK = matches spec; WRONG = computes something else under the spec's name; PROXY = labeled stand-in; MISSING = not present.

### Feature 1: Purged K-Fold and CPCV Engine (mostly correct)
| Spec item | State | Detail |
|---|---|---|
| Purged K-Fold + embargo | OK | Date sort, horizon purge, embargo (`analytics.py:605-627`). |
| CPCV C(N,k) paths | OK | `combinations(range(n_groups), ...)` (`:650`), path Sharpe + equity envelope (`:659-665`). |
| Naive vs purged bias panel | OK | Side-by-side Sharpe with leakage gap (`:698`). |
| DSR | OK | Proper BLP probability after July fix (`:453-462`). |
| PBO | OK | Empirical fraction below median (`:465-470`). |
| Embargo sensitivity | OK | Real re-runs at E=0/5/10/21 (`:673-687`). |
| Per-fold table, path metrics | OK | (`:634-646`, `:709`). |
| Fractional uniqueness | PROXY | Horizon-inferred overlap (`:435-450`), honestly marked `live_proxy` (`feature_01.py:65`). Needs user event end-times for exactness. |
| `label_type: triple_barrier` | WRONG (B4) | Accepted, ignored; always regression labels. |
| `model_type: linear_svm/mlp` | Verify | Listed in contract (`feature_01.py:45`); confirm `_fit_base_model` (`:473`) honors them or 422. |
| Scoring metric, trials, variance | Partial | Sharpe path live; Sortino/Accuracy/F1/AUC/MAE/IC menu from spec (`ml_final_features.md:29`) not exposed; trials feed DSR (`:669`). |

### Feature 2: GBT Alpha (partly correct)
- Real: 7-family fit (Ridge/RF/ET/GBM + XGB/LGBM/CatBoost when installed, `analytics.py:723-745`), zero-IC models get zero weight (`:755-757`), per-model IC + MAE leaderboard (`:754`), monthly rolling IC-weight evolution (`:797-806`), IC decay across 1/5/21/63/126/252 (`:811-825`), ICE rows, fast-grid landscape, signal-to-portfolio stats.
- Honest proxies: global/long/short attribution are importance/coefficient proxies labeled `live_importance_proxy` (`feature_02.py:37-39`); beeswarm/waterfall emit `[]` with `disabled_no_fabricated_values` (`:45-46`); capped exact TreeSHAP (`live_capped`, `:40`).
- MISSING vs spec (`ml_final_features.md:61-79`): Optuna TPE tuning (3x3 GBM grid only), sample weighting (equal/time-decay/uniqueness; `model.fit(x_train, y_train)` at `:751` takes no weights), universe filter (no GICS/mcap/volume path), microstructure and higher-moment factor toggles (panel has the columns, contract has no switches), binary/quintile/triple-barrier targets (contract lists them at `feature_02.py:30`, runner is regression-only).
- Leakage: B3 (unsorted 75/25 split). Also `best_model` refit on train then predicts the latest book (`:762-763`): legitimate, but the "latest" book includes the same trailing window the test IC was measured on, so rank-table confidence inherits test overlap; disclose or refit cutoff.
- Perf nit: comment at `:813` claims IC-decay reuses the fitted model, but `:816-822` rebuilds the panel and fits a fresh clone per horizon. Fix the comment or the code path.

### Feature 3: Vol Forecasting (partly correct; engine body carryover, re-verify)
- Real per July audit: HAR-Ridge/HAR-GBM, close-to-close/Garman-Klass/Yang-Zhang estimators, ARCH-family AIC selection with cap, bipower jump split, ElasticNet spillover network, rolling QLIKE weights, macro overlay when the category7 parquet is present.
- MISSING: GINN (spec `ml_final_features.md:102-106` model 3 of 4; contract exposes only `ginn_research` placeholder, `feature_03.py:27,55`), HAR-X exogenous integration (VIX/slope/skew/jump/VRP toggles exist as `macro_features` but spillover stays a separate diagnostic), proper per-horizon term structure (sqrt-scaling carryover from July audit).
- Contract/UX: `forecast_horizons` limited to [1,5,21,63] vs spec [1,5,10,21,63,126,252]; `model_suite: har_ml` default while HAR-X integration is the gap above.

### Feature 4: Triple Barrier + CQR (mostly fine; body carryover, re-verify)
- Contract now exposes `barrier_mode` (fixed/vol_scaled), `barrier_side` (bilateral/long_only/short_only), `position_sizing` (probability/kelly/binary) (`feature_04.py:19-21,34-36`), matching the README changelog claim of dynamic, side-specific barriers with purged out-of-fold meta validation. If the engine honors all three, this feature is the closest to spec.
- Still thin: `primary_side_model` is effectively `momentum_sign` (external upload and F02-prediction routing are `RESEARCH_ONLY`, `:55`); no event-timestamp upload; confirm vol_scaled path and Kelly/binary sizing outputs in the current engine before claiming spec parity.

### Feature 5: HRP/BL (mostly fine)
- Real: Ledoit-Wolf/OAS/EWMA/RMT estimators, Ward/single/complete/average linkage, HRP/NCO/HERC/min_variance variants, dendrogram records, quasi-diagonal heatmap, risk contributions, full BL posterior with tau/views/bounds (`analytics.py:1594-1610`). Contract exposes `min_weight`, `max_sector_weight`, `black_litterman_tau`, `views` (`feature_05.py:31-34`).
- PROXY (honestly labeled): `rl_rebalancing_vs_fixed_schedule` (`research_proxy`), `tail_dependence_matrix` (quantile-correlation stub at `:1621`, `live_proxy`), `rolling_cluster_stability` (HRP Sharpe renamed at `:1622`), BL panels (`live_proxy`).
- Verify: `max_sector_weight` binds in the SLSQP constraints (input exists; binding not confirmed in the read section), and default BL with no user `views` collapses views to equilibrium (`:1599`), making the posterior a no-op unless views are passed; the UI has no view editor (declared research-only, `:59`). Both are honest if disclosed, misleading if not.

### Feature 6: Regimes (mostly fine; body carryover, re-verify)
- Real: Gaussian HMM Baum-Welch via hmmlearn with deterministic state ordering, GMM fallback, transition matrix, PC1 break monitor, regime-conditional factor/vol/attribution panels.
- Gaps: ensemble is RF-only vs spec XGBoost+RF+HMM vote; no routing to F03/F05/F07 (needs workspace store, see section 7); RF-vs-HMM agreement trains on the same full-sample HMM states it evaluates (`ensemble_hmm_classifier` path), so agreement is in-sample; regime-alert threshold input exists (`feature_06.py:33`) but confirm it fires an alert vs just rendering.

### Feature 7: DMA/OBS (partly correct; body carryover, re-verify)
- Real: sequential DMA weights with forgetting factor, simplex-projected OBS on Gaussian NLL with regret curve, pruning log, forgetting-factor sensitivity, regime-conditional lambda path.
- Gaps: 5 hardcoded members vs spec library up to 20 (no XGB/LGBM/HAR/GINN/LSTM/user upload); B4 option/default mismatch (`feature_07.py:14` vs `:29`); epistemic/aleatoric split is dispersion-vs-residual proxy (labeled `live_proxy`, `:45-46`).

### Feature 8: Composite Optimizer (mostly fine)
- Real: IC table with fixed `mean/std` IC-IR (`analytics.py:2131`), sector neutralization, Gram-Schmidt, walk-forward stability, long-short backtest, pairwise interaction screen, forward-selection FM-style screen, elastic/lasso selection.
- Gaps: `weighting_scheme: dml_ape` is selectable (`feature_08.py:33`) but F11 APE persistence does not exist (declared research-only at `:65`); confirm the runner falls back to IC weights with a warning rather than failing silently. `output_signal_construction` zscore/signed_rank path vs composite sum: confirm both honored.

### Feature 9: Pairs (mostly fine; body carryover, re-verify)
- Real: correlation/OU/ADF candidate screen, spread z-score, Kalman random-walk-beta hedge path for the top pair, entry/exit timeline, backtest equity, copula thresholds table.
- PROXY (honestly labeled): `rl_threshold_policy` (`research_proxy`), `cointegration_network` (`live_proxy`), `ml_pair_classifier_scores` (`live_fast_score`, rule score per July audit).

### Feature 10: Microstructure (mostly fine)
- Honest scope: contract declares repo has OHLCV not tick quotes (`feature_10.py:51-54`); research-only lists true spread/imbalance/signed volume/Lee-Ready (`:50`). `signal_families` now honored (`analytics.py:2708`); IC-IR uses `mean/std` (`:2725`).
- Note: `ic_protocol: cpcv_research` is selectable (`feature_10.py:26`) but research keys gate it (`:58`); confirm realtime rejects or downgrades loudly. Roll-spread formula was fixed per changelog; re-verify against estimator code before closing.

### Feature 11: Causal DML (mostly correct; body carryover, re-verify)
- Real: K-fold cross-fit DML residualization, APE/SE/t per factor, bias decomposition, APE time series, nuisance R2, HC3 robust table, DML-vs-OLS backtest. Nuisance menu ridge/elastic_net/random_forest/lightgbm (`feature_11.py:31`) with Ridge default for speed.
- Heuristic, disclose: Causal/Proxy/Spurious labels from t-stat plus bias-vs-IC rule; `recommended_weight_adjustment: max(ape, 0)` drops negative-APE factors to zero rather than shorting; `spurious_factor_action: auto_prune` has no cross-feature persistence to act on (research-only, `:52`).

### Feature 12: Deep Sequence (proxy with honest labels)
- All four "architectures" are classical stand-ins: Ridge on raw (MLP_proxy), Ridge on patch stats (PatchTST_proxy), ExtraTrees on cross-sectional ranks (iTransformer_proxy), RF on raw (TFT_proxy) (`analytics.py:2904-2907`). No torch training despite torch being installed.
- `training_time_seconds_proxy = N x features / 1e6` (`:2915`) is arithmetic, not measurement. Attention heatmaps are lagged Spearman correlations (`data_derived_attention`, `:2954`). Regime split indexes `perf[2]`/`perf[3]` positionally (`:2945`): fragile, breaks silently if ordering changes.
- The contract is the honest part: `live_proxy`/`live_diagnostic` statuses and research-only full training (`feature_12.py:39-51,53`). Keep F12 visible only with its proxy banner; never let these charts be screenshotted as transformer evidence. B4 depth/heads/dropout inputs change nothing.

---

## 4. Use open source that is already installed

Already importable (per README inventory: CatBoost, XGBoost, LightGBM, sklearn, shap, hmmlearn, arch, torch):

| Hand-rolled or missing today | Replace with | Why |
|---|---|---|
| Contiguous 75/25 split + `KFold(shuffle=False)` on stacked panels (B3) | `sklearn.model_selection.TimeSeriesSplit` + one shared `chronological_purged_split` helper | Chronological, purged, embargoed splits everywhere, not just F01. |
| Fast-grid "hyperparameter landscape" (F02) | `optuna` (new dep, research toggle, capped trials) | Spec-mandated TPE tuning (`ml_final_features.md:69`); grid point is not a landscape. |
| PPO placeholders (F05/F09) | `stable-baselines3` (new dep, research jobs only) | Removes the two `research_proxy` panels or keeps them behind a real trainer. |
| GINN / PatchTST / iTransformer / TFT training (F03/F12) | `torch` (already installed) + job transport + artifact cache | Turns the biggest PROXY area into an opt-in research path; realtime stays classical. |
| Regime HMM extras (Student-t emissions) | `hmmlearn` custom emissions or `pomp`-style EM (new work) | Currently research-only; keep gated, not realtime. |
| Break p-values (F06 PC1 monitor) | `statsmodels.stats.diagnostic.breaks_cusumolsresid` + Andrews table, or `ruptures` (new dep) | Monitor without critical values cannot alert. |
| Block-respecting CIs anywhere they are added later | `arch.bootstrap.MovingBlockBootstrap` | iid resampling of time series is the Research-V2 MR-test mistake; do not repeat it here. |
| DML SEs beyond HC3 | keep `statsmodels` + current cross-fit | Fine; add date/sector-clustered SEs only with an explicit clustering policy. |

Worth adding (new dependencies, need approval): `optuna`, `stable-baselines3`, optionally `ruptures`. Do not add GINN/transformer libraries until the job transport + artifact store exist; otherwise they become more dead inputs like B4.

Frontend: plain `fetch` in `frontend/src/lib/api.js`; no React Query hook, no cancellation, no job polling. Either adopt `@tanstack/react-query` (installed per Research review) for run/manifest queries or keep fetch but add `AbortController` + manifest fetch. For charts pick one of the four installed libs (same P16 rule as Research review).

---

## 5. Frontend review

- **Broken data flow (B1)**, different shape from Research V2. Research pages rendered a workbench with no `onRun`/`response`, so Run did nothing. Here `MLV2Workbench` (`customPagePrimitives.jsx:814-904`) is self-contained: `run()` calls `runMlV2Feature(feature.id, form)` (`:855`) and stores `response` (`:856`), with loading/progress/error states (`:821-823`, `:860-867`). The component is correct; the URL it calls is not. One-line fix, high leverage.
- **Duplicated contract, drift already real**: `components/ml-v2/registry.js` (2,361 lines) hand-copies every feature's inputs/defaults/outputs, while each backend response already carries `input_contract`/`output_contract` in `meta` (`analytics.py:197-208`) and `GET /api/ml/v2/features` serves the manifest. Drift example: backend F01 `model_type` offers `linear_svm/mlp/catboost` (`feature_01.py:45`); frontend F01 offers only ridge/lasso/elastic_net/random_forest/extra_trees/xgboost/lightgbm (`registry.js:36-46`). Users cannot select what the backend advertises, and the frontend advertises `triple_barrier` targets the backend ignores (B4). Fix: fetch the manifest, render inputs/outputs from it, keep only presentation hints (renderer, rank) locally.
- **Misleading affordances**: F05 `rl_rebalancing` boolean, F08 `dml_ape`, F10 `cpcv_research`, F12 depth/heads/dropout, F07 lstm/har options are selectable but inert or research-gated. Gate them behind a research toggle or disable with a tooltip citing the exact `researchOnly` note, which the registry already carries.
- **Unreachable-in-practice UI**: 12 feature pages (`app/labs/ml-v2/feature-*/page.js`, each `<MLV2Workbench featureId="XX" />`) plus home render fine, but with B1 every output card shows "Awaiting run"/"Output unavailable" (`:563-571`) forever. The export modal (`:774`) will export empty sections; disable export until `response` exists.
- **`customPagePrimitives.jsx`**: 1,186 lines, single file for workbench, curtains, cards, dock, export, toasts, plus a global CSS string. Same disease as Research V2 (51 KB there). Split into Workbench/ConfigCurtain/OutputCard/renderers; move CSS to a module.
- **Persistence is localStorage-only** (`:859` stores `summary_cards` per feature). Cross-feature routing the spec needs (F11 APE into F08, F02/F03/F12 libraries into F07, regimes into F03/F05/F07) has no server store; `ml_v2/workspace_store.py` does not exist (README honest about this).
- **No cancel for long jobs**: CPCV/DML/HMM runs are synchronous `asyncio.to_thread` (`ml_api.py:58`) with a fake progress timer (`:853`). Heavy features need the Studio job transport (same recommendation as Research B1) plus `AbortController` on the client.

---

## 6. Codebase-wide pattern (same issues as the Research V2 review)

- **Duplicated data loaders**: `ml_v2/core/data_loader.py` (313 lines) repeats the parquet readers, symbol parsing, and silent-default-universe behavior found in the other V2 modules. Fix: one shared `app/services/shared/market_data.py`; modules keep only analytics. The silent-fallback fix (B2) should land in the shared copy once.
- **Duplicated Lab primitives**: `components/ml-v2/customPagePrimitives.jsx` (1,186 lines) parallels `components/research-v2/customPagePrimitives.jsx` (51 KB). Fix: one shared Lab workbench + renderer registry; per-module files declare sections only.
- **Two ML systems, one router file**: `ml_api.py` mixes the old ML God Stack (`app.services.ml.*`, ~1,000 lines) with the two new ML V2 endpoints (`:41`, `:48-62`). Split into `ml_v2_api.py` (or a dedicated `ml_v2.py` labs router) so V2 has the same shape as factors/pca/volatility/portfolio V2.
- **Changelog honesty varies by layer**: `README.md` and contract `researchOnly`/`status` fields are blunt and accurate; the July `review.md` Section 6 contradicts current code (claims "zero references to ml_v2" and "not wired to V2" at `review.md:516-518`, stale since `:41` landed). Update or archive it so the next reader trusts the docs.
- **`DONE.md`-style overstatement risk**: README marks feature checklists `[x]` while the same file lists the honest gaps; keep the "Honest Remaining Work" section as the status source of truth and link it from the top.
- **Backend deps**: same P17-style gaps as Research (ranges, no lock); `linearmodels`-type gaps do not apply here, but `optuna`/`stable-baselines3` must go through approval before any research toggle lands.

---

## 7. Remaining work, by type, in order

| # | Type | Work | Size |
|---|---|---|---|
| 1 | Wiring | Point `runMlV2Feature` at `/api/ml/v2/features/{id}/run` (or add `/labs/ml/v2` router mirroring `factors_v2.py`); fetch `GET .../features` manifest; drop static `registry.js` to presentation hints | S |
| 2 | Data integrity | 422 on unknown tickers (`data_loader.py:147-148`, `analytics.py:248-250`); `meta.universe_substituted` until then | S |
| 3 | Leakage | Shared `chronological_purged_split` (sort, purge `horizon`, embargo) for F02/F08/F11/F12; scaler fit on train only (`:1018`, `:1645-1646`); look-ahead guard test | M |
| 4 | Honest inputs | 422-or-wire for B4 (F01 triple_barrier, F12 depth/heads/dropout, F07 library options, F08 dml_ape fallback, F05 sector-cap binding, F10 cpcv_research) | S |
| 5 | Correctness (F01/F02) | Wire existing triple-barrier labels into CPCV option; confirm `linear_svm/mlp` in `_fit_base_model`; Optuna research toggle; sample weighting; universe filter; fix IC-decay comment-vs-code (`:813-822`) | M |
| 6 | Correctness (F03/F06/F07/F09) | HAR-X integration; GINN/training behind research jobs; RF+XGB vote + in-sample fix for regime agreement; expand DMA library from F02 registry; Kalman Q/R MLE check; copula thresholds drive entry/exit | M |
| 7 | F12 honesty | Keep proxy banner; positional `perf[2]/perf[3]` to named lookup; replace fake `training_time_seconds_proxy` with measured or remove; research job path for real training | S |
| 8 | Tests | Golden-number tests per estimator (DSR/PBO vs Bailey reference values; purge accounting; HRP weights vs `riskfolio`/`PyPortfolioOpt` spot check; DML on simulated DGP with known APE); unknown-ticker 422 test | M |
| 9 | Frontend | Manifest-driven inputs; research-gate inert options; export disabled pre-run; split primitives; one chart lib; cancel + job transport for heavy features | M |
| 10 | Cleanup | Split `ml_api.py` V1/V2; shared data loader + shared Lab workbench across V2 modules; refresh stale `review.md` Section 6; pin deps | L |

Recommended next step: items 1, 2, and 4 together, plus A1-A3 from the addendum, (all small, all honesty-class, and they make the module both reachable and truthful), then 3 with the guard test from 8 alongside.

---

## 8. Addendum (verified 2026-10-03)

These came from a second read of the code and were not in the first pass. Read [V2_REBUILD_PLAYBOOK.md](V2_REBUILD_PLAYBOOK.md) before fixing; frontend work (section 5, item 9) is reserved for Claude.

| # | Area | Finding | Where |
|---|---|---|---|
| A1 | Look-ahead | `market_cap` is today's snapshot `marketCap`, written as a constant into every historical row of the feature panel. It is both look-ahead and a non-varying feature, and it feeds F02/F08/F11/F12 models. Missing caps become `1.0` silently. Use month-end price x point-in-time shares (as Research V2 `panel.py`), or drop the feature. | `data_loader.py:224-232`, `analytics.py:360` |
| A2 | Data | Price matrices are forward-filled (`.ffill()`), so halted or delisted names carry a stale price with zero return. This biases volatility, covariance (F05 HRP) and IC down. Keep gaps as NaN (Screener V2 now does). | `data_loader.py:177,179,193,200` |
| A3 | Data | `"sp500"`/`"default"` resolves to the 80 tickers with the most price rows, not the S&P 500 (false label, survivorship-biased). Unknown tickers are dropped silently even when others survive, not only when all are unknown. The cap floors at 3 (`max(3, ...)`), so a 1-ticker request is padded. | `data_loader.py:137-150` |
| A4 | Sector | Sector and industry come from the latest snapshot and are applied to all history (F08 neutralization, F05 sector caps). Acceptable if disclosed as "time-invariant sector", like Research V2. | `data_loader.py:216-221` |
| A5 | F05 | HRP silently uses only the first 80 columns of the return matrix (`iloc[:, :80]`), ordered by data coverage, regardless of what the user asked for. Say so in `meta` or honour the request. | `analytics.py:1556` |
| A6 | Errors | 40 `except Exception` blocks across `core/`; many turn failures into empty outputs with `status: ok`. Audit each: raise, or return `status: warning` with the reason. | `core/*.py` |
| A7 | API | Runs are synchronous `asyncio.to_thread` calls with no job, progress or cancel (CPCV with many paths, DML, HMM will exceed proxy timeouts). Use the Studio `JobStore` pattern from Research V2 and Screener V2. | `ml_api.py:54-62` |
| A8 | Structure | `analytics.py` is 2,986 lines holding all 12 features. Split one module per feature (Research V2 and Screener V2 layout). `schemas/`, `utils/` and the stale `review.md`, `upgrades.md`, `speed upgrades.md`, `gap_classification.md` should be reconciled or removed, with fates recorded in `DONE.md`. | `ml_v2/` |
| A9 | Tests | Confirmed: zero `test_ml_v2*` files. Follow the playbook's four test files, including a look-ahead guard (perturbing data after t must not change outputs at t) and a no-forward-fill test. | `backend/tests/` |
