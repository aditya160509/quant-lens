"""Actual signal IC decay with bootstrap bands and taxonomy-aware model fitting."""

import numpy as np
import pandas as pd
from ..core.context import load_context, feature_meta
from ..core.common import response, compact_records
from ..core.decay import empirical_ic, decay_model_selection, publication_mean_shift

from .inputs import inputs_for, output

FEATURE_ID = "09"
FEATURE_NAME = "Alpha Decay and Factor Half-Life Engine"


def run(payload=None):
    payload = payload or {}
    ctx = load_context(payload)
    r = ctx["raw_returns"]
    taxonomy = payload.get("factor_taxonomy", "mechanical")
    if payload.get("signal_scores"):
        scores = pd.DataFrame(payload["signal_scores"])
        scores.date = pd.to_datetime(scores.date)
        scores = scores.set_index("date")
        if scores.index.duplicated().any() or set(scores.columns) != set(r.columns):
            raise ValueError(
                "Signal dates must be unique and columns must match selected assets"
            )
        signals = scores.reindex(index=r.index, columns=r.columns).astype(float)
        signal_name = "supplied observed scores"
    else:
        if taxonomy == "judgment":
            raise ValueError(
                "Judgment signals require actual signal_scores; momentum is not a value/quality proxy"
            )
        signals = np.expm1(
            np.log1p(r).rolling(int(payload.get("signal_window", 21))).sum()
        )
        signal_name = "Observed trailing cumulative-return momentum at formation close"
    rows = empirical_ic(
        r,
        signals,
        int(payload.get("max_horizon", 63)),
        int(payload.get("bootstrap_draws", 200)),
    )
    valid = [row for row in rows if row["ic"] is not None]
    models = decay_model_selection(valid) if taxonomy == "mechanical" else []
    half = None
    if valid:
        threshold = abs(valid[0]["ic"]) / 2
        half = next(
            (row["horizon"] for row in valid if abs(row["ic"]) <= threshold), None
        )
    fitted_half = None
    if models:
        best = models[0]
        params = best["parameters"]
        fitted_half = (
            params[0] / (2 * params[1])
            if best["model"] == "linear"
            else params[1]
            if best["model"] == "hyperbolic"
            else params[1] * np.log(2)
            if best["model"] == "exponential"
            else params[1] * np.log(2) ** (1 / params[2])
        )
    dispersion = signals.std(axis=1).dropna()
    history = dispersion.tail(1260)
    measured = (
        []
        if history.empty
        else [
            {
                "signal_dispersion": float(history.iloc[-1]),
                "historical_dispersion_percentile": float(
                    history.rank(pct=True).iloc[-1] * 100
                ),
                "observations": len(history),
                "interpretation": "Measured raw-score dispersion; not ETF AUM crowding or a calibrated crash probability",
            }
        ]
    )
    return response(
        FEATURE_ID,
        [{"label": "Empirical Half-Life", "value": half}],
        {
            "ic_decay_curve": rows,
            "signal_history": compact_records(signals.reset_index()),
        },
        {
            "half_life_table": [
                {
                    "signal": signal_name,
                    "taxonomy": taxonomy,
                    "empirical_half_life_observations": half,
                    "fitted_half_life_observations": fitted_half,
                    "selected_model": models[0]["model"] if models else None,
                }
            ],
            "decay_model_selection": models,
            "signal_dispersion": measured,
            "publication_decay": publication_mean_shift(
                r, signals, payload["publication_date"]
            )
            if payload.get("publication_date")
            else [],
        },
        meta=feature_meta(
            ctx,
            [
                "ETF AUM histories and signed-flow Kyle calibration are absent; crowding crash probabilities and dollar alpha capacity are not produced. IC is dimensionless and is not mislabeled as return alpha net of bps costs."
            ],
        ),
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("ic_decay_curve", "charts", "band", True),
    output("signal_history", "charts", "line", False),
    output("half_life_table"),
    output("decay_model_selection"),
    output("signal_dispersion"),
    output("publication_decay"),
]
