"""Feature 04: past-only HMM probabilities and hard jump-model states."""

from __future__ import annotations
from .inputs import field
import numpy as np
import pandas as pd
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
    # Synchronization uses each asset's causal HMM high-state probability.
    sync = pd.DataFrame()
    sync_failures = []
    if payload.get("include_global_sync", True):
        high_probabilities = {}
        for symbol in assets:
            try:
                model = (
                    fitted
                    if symbol == asset
                    else filtered_regimes(
                        regime_features(ohlcv, symbol),
                        states=int(payload.get("states", 4)),
                        min_train=int(payload.get("min_train", 252)),
                        refit_interval=int(payload.get("refit_interval", 126)),
                        restarts=int(payload.get("hmm_restarts", 3)),
                        select_k=bool(payload.get("select_k_by_bic", False)),
                        jump_penalty=float(payload.get("sjm_jump_penalty", 15)),
                        training_window=payload.get("training_window"),
                    )
                )
                states = state_names(model["selected_states"])
                high = [state for state in states if state in {"high_vol", "crisis"}]
                observations = model["probabilities"]
                nonconverged = int((~observations.hmm_converged).sum())
                if nonconverged:
                    sync_failures.append(
                        {
                            "asset": symbol,
                            "reason": f"{nonconverged} causal HMM dates did not converge; synchronization is unavailable on those dates",
                        }
                    )
                high_probabilities[symbol] = (
                    observations[high].sum(axis=1).where(observations.hmm_converged)
                )
            except (ValueError, np.linalg.LinAlgError) as exc:
                sync_failures.append({"asset": symbol, "reason": str(exc)})
        if len(high_probabilities) == len(assets):
            panel = pd.DataFrame(high_probabilities)
            complete = panel.notna().all(axis=1)
            sync = (
                pd.DataFrame(
                    {
                        "mean_high_state_probability": panel.mean(axis=1).where(
                            complete
                        ),
                        "fraction_high_probability_above_half": panel.gt(0.5)
                        .mean(axis=1)
                        .where(complete),
                        "observed_assets": panel.notna().sum(axis=1),
                    }
                )
                .rename_axis("date")
                .reset_index()
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
            "global_vol_regime_sync_index": compact_records(sync, limit=len(sync)),
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
            "global_sync": {
                "definition": "Mean per-asset causal HMM probability of high_vol plus crisis, with breadth above 0.5; requires all selected assets and converged fits",
                "failures": sync_failures,
                "enabled": payload.get("include_global_sync", True),
            },
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
    if sync_failures:
        result["status"] = "warning"
        result["alerts"].append(
            {
                "level": "warning",
                "message": "Global HMM synchronization unavailable for one or more assets; see metadata",
            }
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


# Authoritative contract consumed by the lazy backend manifest.

INPUTS = [
    field("include_global_sync", True),
    field("assets", ["SPY"], kind="symbols", group="Data"),
    field("asset", None, kind="text", group="Data"),
    field("lookback_days", 2520, kind="integer", group="Data"),
    field("as_of_date", None, kind="date", group="Data"),
    field("training_window", None, kind="integer", group="Model"),
    field("transition_alert_threshold", 0.3, kind=None, group="Model"),
    field("alert_horizon", 5, kind=None, group="Model"),
    field("states", 4, kind=None, group="Model"),
    field("min_train", 252, kind=None, group="Model"),
    field("refit_interval", 126, kind=None, group="Model"),
    field("hmm_restarts", 3, kind=None, group="Model"),
    field("select_k_by_bic", False, kind=None, group="Model"),
    field("sjm_jump_penalty", 15, kind=None, group="Model"),
]

OUTPUTS = [
    {
        "key": "probabilistic_regime_timeline",
        "source": "charts",
        "label": "Probabilistic regime timeline",
        "render": "line",
        "primary": True,
        "help": "Actual observed or fitted probabilistic regime timeline. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "current_regime_dashboard",
        "source": "charts",
        "label": "Current regime dashboard",
        "render": "cards",
        "primary": False,
        "help": "Actual observed or fitted current regime dashboard. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "statistical_jump_state_timeline",
        "source": "charts",
        "label": "Statistical jump state timeline",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted statistical jump state timeline. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "transition_heatmap",
        "source": "charts",
        "label": "Transition heatmap",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted transition heatmap. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "global_vol_regime_sync_index",
        "source": "charts",
        "label": "Global vol regime sync index",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted global vol regime sync index. Independent causal HMM histories are unavailable or global synchronization was not requested.",
        "empty_reason": "Independent causal HMM histories are unavailable or global synchronization was not requested.",
    },
    {
        "key": "regime_conditional_stats",
        "source": "tables",
        "label": "Regime conditional stats",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted regime conditional stats. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "regime_transition_heatmap",
        "source": "tables",
        "label": "Regime transition heatmap",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted regime transition heatmap. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "regime_duration_survival",
        "source": "tables",
        "label": "Regime duration survival",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted regime duration survival. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "hmm_bic_k_selection",
        "source": "tables",
        "label": "Hmm bic k selection",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted hmm bic k selection. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "transition_alert_log",
        "source": "tables",
        "label": "Transition alert log",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted transition alert log. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
]
