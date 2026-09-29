# ML V2 — Gap Classification: Possible vs Heavy vs Data-Limited

## ✅ 100% Possible, Worth Implementing

| Gap | File | Effort |
|---|---|---|
| **F01 — DSR formula wrong** — Fix variance term, use proper Bailey-Lopez de Prado | `analytics.py:452-460` | 2hr |
| **F01 — PBO parametric approximation** — Replace with direct `mean(ranks < 0.5)` | `analytics.py:463-474` | 1hr |
| **F01 — Embargo sensitivity** — Re-run CPCV at each E value instead of penalty | `analytics.py:673` | 3hr |
| **F01 — Only 6 model types, spec says 12** — Add Linear SVM, MLP (both in sklearn) | `analytics.py:477` | 1hr |
| **F01 — Triple-barrier labels** — F04 already implements this, just wire to F01 | `feature_01.py:46` | 2hr |
| **F02 — Sample weighting** — Add sample_weight param to model.fit() | `analytics.py:499` | 1hr |
| **F02 — Universe filter** — Filter panel by sector/mcap before training | `feature_02.py` | 2hr |
| **F02 — IC-weighted ensemble rolling window** — Add lookback window param | `analytics.py:744` | 2hr |
| **F02 — Fix IC-IR formula** — `ic / max(abs(ic)*0.5, 1e-4)` → `mean(ic)/std(ic)` | `analytics.py:2043` | 30min |
| **F02 — Fix ensemble_weight float division for zero-IC models** | `analytics.py:744` | 30min |
| **F02 — Microstructure/higher-moment factor toggles** — Wire payload selection | `feature_02.py` | 2hr |
| **F03 — HAR-ML with cross-asset spillover** — Spillover network already exists | `analytics.py:972, 1099` | 4hr |
| **F03 — Term structure** — Replace sqrt(h/21) with proper per-horizon forecasts | `analytics.py:1121-1123` | 3hr |
| **F04 — Dynamic barriers** — EWMA vol and ATR-based PT/SL | `analytics.py:1164-1165` | 3hr |
| **F04 — Barrier side config** — Add long-only/short-only mode | `analytics.py` | 1hr |
| **F04 — Meta-model under Purged K-Fold** — F01's purged CV already exists | `analytics.py:1194-1195` | 2hr |
| **F04 — Primary model selection** — Add MA crossover, RSI, CUSUM options | `feature_04.py:31` | 3hr |
| **F04 — Position sizing integration** — Kelly-scaled or binary threshold | `feature_04.py` | 2hr |
| **F04 — Event time upload** — User-supplied event timestamps | API feature | 3hr |
| **F04 — Fix ticker_hash non-determinism** | `analytics.py:1190` | 30min |
| **F04 — Fix meta-probability forward-return leak** | `analytics.py:1200` | 30min |
| **F05 — Proper Black-Litterman** — Implement `(τΣ⁻¹+PᵀΩ⁻¹P)⁻¹(τΣ⁻¹Π+PᵀΩ⁻¹Q)` | `analytics.py:1527` | 4hr |
| **F05 — Sector constraints** — Add to optimizer constraint matrix | `analytics.py:1518` | 3hr |
| **F05 — Per-asset min/max weight** — Parse bounds from payload | `feature_05.py` | 2hr |
| **F05 — BL τ slider** — Expose parameter | `feature_05.py` | 1hr |
| **F06 — Add XGBoost to ensemble** (RF only currently) | `analytics.py:1726` | 1hr |
| **F06 — Regime alert thresholds** — Alert when P(bear) > 0.65 | `feature_06.py` | 2hr |
| **F07 — Expand model library** — Wire XGBoost, LightGBM, etc. from F02 | `analytics.py:1772-1778` | 3hr |
| **F08 — Fix IC-IR formula** | `analytics.py:2043` | 30min |
| **F09 — Kalman filter Q/R estimation** — MLE per pair | `analytics.py:2358` | 3hr |
| **F09 — Fix entry/exit to use copula thresholds** | `analytics.py:2344` | 1hr |
| **F10 — Fix Roll spread formula** — Use raw returns, not differenced | `analytics.py:2539-2541` | 1hr |
| **F10 — Respect signal_families from payload** | `analytics.py:2598` | 1hr |
| **F11 — LightGBM nuisance by default** | `analytics.py:2706` | 1hr |
| **F12 — Improve patched features** — Per-asset lag features | `analytics.py:2769-2775` | 3hr |
| **F12 — Fix attention heatmap** — Replace lag-correlation with real attention proxy | `analytics.py:2841-2865` | 4hr |

## ⚠️ Possible But Heavy Compute (Research-Mode Only)

| Gap | Why Heavy | Est. Runtime |
|---|---|---|
| **F02 — Optuna Bayesian hyperparameter tuning** | TPE sampler runs 50-200 model fits with CV | 5-20 min |
| **F02 — Full TreeSHAP for all predictions** | Exact Shapley values O(2^N) per tree | 1-5 min |
| **F03 — GINN (LSTM + GARCH-consistency loss)** | Full LSTM training, 100+ epochs | 5-30 min per asset |
| **F05 — RL rebalancing (PPO agent)** | PPO needs 10k+ environment steps | 10-30 min |
| **F09 — Johansen basket cointegration tests** | O(N²) per basket pair | 5-10 min for 200 pairs |
| **F09 — PPO threshold optimizer** | RL training same as F05 | 10-30 min |
| **F11 — Optuna for nuisance models** | Nuisance tuning × K folds × N factors | 5-15 min |
| **F12 — Full PatchTST/iTransformer/TFT training** | Transformer training on seq data | 30 min - 2 hrs |

## ❌ Data-Limited / Impossible (Removed from Review)

- Tick-level bid/ask/order-book data (F10) — vendor data required
- Signed volume / order-flow imbalance (F10) — same
- Lee-Ready trade classification (F10) — same
- User model upload (F01, F02, F07) — needs API platform feature
- Custom label CSV upload (F01) — needs API
- Label fractional uniqueness proper (F01) — needs user event timestamps
- DML APE auto-prune to F08 (F11) — cross-feature persistence
- Nested Fama-MacBeth research sweep (F08) — research-only
- Custom factor CSV upload (F08) — needs API

## Summary

| Category | Count | Action |
|---|---|---|
| **✅ Worth implementing** | 36 gaps | Formula fixes, wiring existing code, adding missing features |
| **⚠️ Research-mode only** | 8 gaps | Gate behind toggle, document expected runtime |
| **❌ Removed** | 9 gaps | Data-limited or not worth the effort |
