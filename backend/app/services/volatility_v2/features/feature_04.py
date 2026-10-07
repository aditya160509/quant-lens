"""Feature 04: past-only HMM probabilities and hard jump-model states."""

from __future__ import annotations
import numpy as np
from app.services.volatility_v2.core.analytics import (
    load_assets,
    volatility_estimators,
    compact_records,
    response,
    summary_card,
    clean_json,
)
from app.services.volatility_v2.core.regimes import (
    regime_features,
    filtered_regimes,
    duration_survival,
    transition_matrices,
    transition_alerts,
    state_names,
)


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload)
    asset = assets[0]
    features = regime_features(ohlcv, asset)
    fitted = filtered_regimes(
        features,
        states=int(payload.get("states", 4)),
        min_train=int(payload.get("min_train", 252)),
        refit_interval=int(payload.get("refit_interval", 126)),
        restarts=int(payload.get("hmm_restarts", 3)),
        select_k=bool(payload.get("select_k_by_bic", False)),
        jump_penalty=float(payload.get("sjm_jump_penalty", 15)),
        training_window=payload.get("training_window"),
    )
    names = state_names(fitted["selected_states"])
    timeline = fitted["probabilities"]
    probabilities = timeline[names]
    latest = probabilities.iloc[-1]
    current = [
        {
            "regime": name,
            "probability": float(latest[name]),
            "trend_30d": float(probabilities[name].diff(30).iloc[-1])
            if len(probabilities) > 30
            else None,
            "trend_90d": float(probabilities[name].diff(90).iloc[-1])
            if len(probabilities) > 90
            else None,
        }
        for name in names
    ]
    vols = volatility_estimators(ohlcv, 21)
    g = vols.loc[vols.asset.eq(asset)].set_index("date").reindex(probabilities.index)
    stats = []
    for name in names:
        weights = probabilities[name]
        mean = float((g.yang_zhang * weights).sum() / weights.sum())
        stats.append(
            {
                "regime": name,
                "avg_ann_vol": mean,
                "std_ann_vol": float(
                    np.sqrt(
                        ((g.yang_zhang - mean) ** 2 * weights).sum() / weights.sum()
                    )
                ),
                "avg_log_return": float((g["return"] * weights).sum() / weights.sum()),
                "effective_probability_mass": float(weights.sum()),
            }
        )
    heat = transition_matrices(probabilities)
    alerts = transition_alerts(
        probabilities,
        asset,
        float(payload.get("transition_alert_threshold", 0.30)),
        int(payload.get("alert_horizon", 5)),
    )
    seq = probabilities.to_numpy().argmax(axis=1)
    duration = duration_survival(seq, names)
    # A trailing rank of observed volatility is a stress percentile, not a state probability.
    panel = vols.pivot(index="date", columns="asset", values="yang_zhang")
    ranked = panel.rolling(252, min_periods=252).rank(pct=True)
    sync = (
        (ranked.ge(0.7).sum(axis=1) / ranked.notna().sum(axis=1))
        .where(ranked.notna().all(axis=1))
        .rename("fraction_above_trailing_70th_percentile")
    )
    failed = sum(not row.get("converged", False) for row in fitted["hmm_diagnostics"])
    result = response(
        "04",
        [
            summary_card("Dominant Regime", latest.idxmax()),
            summary_card("Probability", float(latest.max()), "prob"),
            summary_card("State Count", len(names)),
        ],
        charts={
            "probabilistic_regime_timeline": compact_records(timeline.reset_index()),
            "current_regime_dashboard": current,
            "statistical_jump_state_timeline": fitted["jump_states"],
            "transition_heatmap": heat,
            "global_vol_regime_sync_index": compact_records(sync.reset_index()),
        },
        tables={
            "regime_conditional_stats": stats,
            "regime_transition_heatmap": heat,
            "regime_duration_survival": duration,
            "hmm_bic_k_selection": fitted["hmm_diagnostics"],
            "transition_alert_log": alerts,
        },
        alerts=alerts,
        meta={
            "asset": asset,
            "assets": assets,
            "selected_hmm_states": len(names),
            "source_fingerprint": fitted["source_fingerprint"],
            "estimation": "hmmlearn Gaussian HMM with past-only standardization/estimation and stable forward filtering; iterative Viterbi jump objective with causal hard assignments",
            "state_labels": "Ordered by training log-volatility mean; statistical states rather than economic regime labels",
            "nonconverged_restart_count": failed,
            "removed_outputs": {
                "precision_weighted_ensemble": "No external observed regime truth; scoring against self-derived HMM/rank truth is circular",
                "macro_rules_probabilities": "Deterministic macro scores are not calibrated probabilities; historical release vintages unavailable",
                "adaptive_EW_HMM": "Previous weighted-mean modification did not implement weighted Baum-Welch",
                "smoothed_posterior": "Future-conditioned smoothing cannot drive historical decisions",
            },
        },
    )
    if not bool(timeline.hmm_converged.all()):
        result["status"] = "warning"
        result["alerts"].append(
            {
                "level": "warning",
                "message": "Some selected HMM fits reached the iteration limit or did not satisfy likelihood convergence; see diagnostics",
            }
        )
    return clean_json(result)
