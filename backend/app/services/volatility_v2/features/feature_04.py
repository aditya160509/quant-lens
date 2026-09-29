"""Feature 04: Volatility regime detection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.volatility_v2.core.analytics import autocorr_raw_jit, compact_records, compute_mode, fit_hmm_regimes, fit_hmm_regimes_adaptive, hmm_filtered_posterior, load_assets, macro_frame, number_like, response, runtime_meta, statistical_jump_model, summary_card, volatility_estimators, weibull_duration_model


def _soft_probs(score: pd.Series, k: int) -> pd.DataFrame:
    q = score.rank(pct=True).fillna(0.5)
    if k <= 2:
        cols = ["low_vol", "high_vol"]
        arr = np.column_stack([1 - q, q])
    elif k == 3:
        trans = 1 - np.abs(q - 0.5) * 2
        arr = np.column_stack([(1 - q) * (1 - 0.35 * trans), trans * 0.7, q * (1 - 0.35 * trans)])
        cols = ["low_vol", "transition", "high_vol"]
    else:
        crisis = np.clip((q - 0.82) / 0.18, 0, 1)
        high = np.clip((q - 0.55) / 0.35, 0, 1) * (1 - crisis)
        trans = np.clip(1 - np.abs(q - 0.5) * 2, 0, 1) * 0.45
        low = np.maximum(0, 1 - high - trans - crisis)
        arr = np.column_stack([low, trans, high, crisis])
        cols = ["low_vol", "transition", "high_vol", "crisis"]
    arr = arr / np.maximum(arr.sum(axis=1, keepdims=True), 1e-12)
    return pd.DataFrame(arr, index=score.index, columns=cols)


def run(payload=None):
    payload = payload or {}
    mode = compute_mode(payload)
    assets, ohlcv = load_assets(payload)
    states = int(number_like(payload.get("states")) or number_like(payload.get("regimes")) or 4)
    threshold = float(number_like(payload.get("transition_alert_threshold")) or 0.30)
    vol = volatility_estimators(ohlcv, window=21)
    asset = assets[0] if assets[0] in set(vol["asset"]) else vol["asset"].iloc[0]
    g = vol[vol["asset"].eq(asset)].sort_values("date").set_index("date")
    m = macro_frame().set_index("date")
    joined = g.join(m, how="left").ffill()
    features = pd.DataFrame({"vol_5": joined["yang_zhang"].rolling(5).mean(), "vol_21": joined["yang_zhang"].rolling(21).mean(), "vol_63": joined["yang_zhang"].rolling(63).mean(), "return_21d": joined["return"].rolling(21).sum(), "rs_yz_jump_ratio": joined["jump_proxy"] / joined["yang_zhang"].pow(2).replace(0, np.nan), "sqret_autocorr_21": joined["return"].pow(2).rolling(21).apply(autocorr_raw_jit, raw=True)}, index=joined.index)
    features["d_credit_21d"] = joined.get("credit", pd.Series(index=joined.index, dtype=float)).diff(21).fillna(0)
    features["d_slope_21d"] = joined.get("curve_10y_2y", pd.Series(index=joined.index, dtype=float)).diff(21).fillna(0)
    features["vix_zscore"] = ((joined.get("vix", pd.Series(index=joined.index, dtype=float)) - joined.get("vix", pd.Series(index=joined.index, dtype=float)).rolling(252).mean()) / joined.get("vix", pd.Series(index=joined.index, dtype=float)).rolling(252).std()).fillna(0)
    sjm = statistical_jump_model(features, states=states, jump_penalty=float(payload.get("sjm_jump_penalty") or 15.0)).reindex(joined.index).ffill().bfill()
    hmm_features = pd.DataFrame({"log_vol": np.log(joined["yang_zhang"].replace(0, np.nan)), "jump_proxy": joined["jump_proxy"], "return_21d": joined["return"].rolling(21).sum(), "sqret_autocorr": joined["return"].pow(2).rolling(63).apply(autocorr_raw_jit, raw=True)}, index=joined.index)
    hmm_raw = fit_hmm_regimes(
        hmm_features,
        states=states,
        n_restarts=20 if mode == "research" else 3,
        select_k_by_bic=mode == "research",
        max_k=max(states, 4),
    )
    bic_table = hmm_raw.attrs.get("bic_table", [])
    selected_states = int(hmm_raw.attrs.get("selected_states", states))
    hmm = hmm_raw.reindex(joined.index).ffill().bfill()
    try:
        ew_hmm = fit_hmm_regimes_adaptive(hmm_features, states=states, delta=float(payload.get("ew_hmm_delta") or 0.995)).reindex(joined.index).ffill().bfill()
    except Exception:
        ew_hmm = hmm.copy()
    try:
        filtered = hmm_filtered_posterior(hmm_features, states=states).reindex(joined.index).ffill().bfill()
    except Exception:
        filtered = hmm.copy()
    rules_score = (joined["yang_zhang"].rank(pct=True) * 0.45 + (joined["yang_zhang"].rolling(21).mean() > joined["yang_zhang"].rolling(63).mean()).astype(float) * 0.20 + (joined.get("vix", 0) > float(payload.get("vix_threshold") or 25)).astype(float) * 0.25 + (joined.get("curve_10y_2y", 0) < 0).astype(float) * 0.10)
    rules = _soft_probs(rules_score, states)
    realized = _soft_probs(joined["yang_zhang"], states)
    weights = []
    for probs in [sjm, hmm, rules]:
        brier = (probs.sub(realized, fill_value=0).pow(2).sum(axis=1)).rolling(63).mean().reindex(joined.index).ffill().bfill()
        weights.append(1 / brier.replace(0, np.nan))
    wdf = pd.concat(weights, axis=1).fillna(1.0)
    wdf = wdf.div(wdf.sum(axis=1), axis=0)
    comp = sjm.mul(wdf.iloc[:, 0], axis=0) + hmm.mul(wdf.iloc[:, 1], axis=0) + rules.mul(wdf.iloc[:, 2], axis=0)
    timeline = comp.reset_index().rename(columns={"index": "date"})
    latest = comp.tail(1).iloc[0]
    dominant = str(latest.idxmax())
    current = [{"regime": c, "probability": float(latest[c]), "trend_30d": float(comp[c].diff(30).iloc[-1]) if len(comp) > 30 else 0.0} for c in comp.columns]
    state_id = comp.to_numpy().argmax(axis=1)
    duration_model = weibull_duration_model(state_id, list(comp.columns))
    heat = []
    trans = None
    for horizon, label in [(5, "1w"), (21, "1m"), (63, "3m")]:
        mat = np.zeros((len(comp.columns), len(comp.columns)))
        for a, b in zip(state_id[:-horizon], state_id[horizon:]):
            mat[a, b] += 1
        mat = mat / np.maximum(mat.sum(axis=1, keepdims=True), 1)
        if horizon == 5:
            trans = mat
        heat.extend([{"horizon": label, "row": comp.columns[i], "col": comp.columns[j], "value": float(mat[i, j])} for i in range(len(comp.columns)) for j in range(len(comp.columns))])
    stats = []
    for c in comp.columns:
        w = comp[c].reindex(g.index).fillna(0)
        stats.append({"regime": c, "avg_ann_vol": float((g["yang_zhang"] * w).sum() / max(w.sum(), 1e-12)), "avg_return": float((g["return"] * w).sum() / max(w.sum(), 1e-12)), "persistence_probability": float(trans[list(comp.columns).index(c), list(comp.columns).index(c)])})
    def kl(p, q):
        p = p.clip(lower=1e-12)
        q = q.clip(lower=1e-12)
        return (p * np.log(p / q)).sum(axis=1)
    divergence = pd.DataFrame({"date": comp.index, "method_divergence": (kl(sjm, comp) + kl(hmm, comp) + kl(rules, comp)) / 3})
    sync_vol = volatility_estimators(ohlcv, window=21)
    try:
        sync_panel = sync_vol.pivot(index="date", columns="asset", values="yang_zhang")
    except ValueError:
        sync_panel = sync_vol.pivot_table(index="date", columns="asset", values="yang_zhang", aggfunc="last")
    sync_idx = (sync_panel.rank(pct=True) > 0.7).mean(axis=1).rename("sync_index").reset_index() if not sync_panel.empty else pd.DataFrame()
    alerts = []
    if float(latest.max()) >= threshold:
        alerts.append({"level": "info", "message": f"Dominant volatility regime is {dominant} at {latest.max():.0%} probability."})
    return response(
        "04",
        [summary_card("Dominant Regime", dominant, ""), summary_card("Probability", float(latest.max()), "prob"), summary_card("State Count", len(comp.columns), ""), summary_card("HMM Selected K", selected_states, "")],
        charts={"probabilistic_regime_timeline": compact_records(timeline), "adaptive_hmm_timeline": compact_records(ew_hmm.reset_index().rename(columns={"index": "date"})), "smoothed_vs_filtered_comparison": {"smoothed": compact_records(hmm.reset_index().rename(columns={"index": "date"})), "filtered": compact_records(filtered.reset_index().rename(columns={"index": "date"}))}, "current_regime_dashboard": current, "method_divergence_indicator": compact_records(divergence), "transition_heatmap": heat, "global_vol_regime_sync_index": compact_records(sync_idx)},
        tables={"regime_conditional_stats": stats, "regime_transition_heatmap": heat, "regime_duration_survival": duration_model, "hmm_bic_k_selection": bic_table, "transition_alert_log": alerts},
        alerts=alerts,
        meta={"asset": asset, "implemented_outputs": 11, "selected_hmm_states": selected_states, "estimation": "Macro-augmented SJM, GaussianHMM Baum-Welch EM with research-mode restart/BIC selection, adaptive EW-HMM, filtered/smoothed posteriors, and Weibull regime duration survival.", **runtime_meta(payload, ["hmm_uses_3_restarts_without_bic_in_realtime"])},
    )
