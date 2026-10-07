"""Fixed supplied factor-exposure contribution accounting."""

import numpy as np
from app.services.factors_v2.core.analytics import factor_returns, response


def run(payload):
    raw = factor_returns(payload).tail(int(payload.get("window_days", 252)))
    if payload.get("start_date"):
        raw = raw.loc[payload["start_date"] :]
    weights = payload.get("factor_exposures")
    if not weights:
        raise ValueError(
            "Supply actual factor_exposures; no invented equal-weight portfolio"
        )
    unknown = set(weights) - set(raw.columns)
    if unknown:
        raise ValueError("Unknown return factors: " + ", ".join(sorted(unknown)))
    raw = raw[list(weights)].dropna()
    frequency = payload.get("frequency", "daily")
    rule = {"weekly": "W-FRI", "monthly": "ME", "quarterly": "QE"}.get(frequency)
    # Contributions sum exactly to the declared daily synthetic factor portfolio.
    contributions = raw.mul(weights)
    if rule:
        contributions = contributions.resample(rule).sum(min_count=1)
    total = contributions.sum(axis=1)
    annual = {"weekly": 52, "monthly": 12, "quarterly": 4}.get(frequency, 252)
    rows = [
        {
            "factor": f,
            "additive_contribution": float(contributions[f].sum()),
            "mean_period": float(contributions[f].mean()),
            "hit_rate": float((contributions[f] > 0).mean()),
        }
        for f in contributions
    ]
    ir = (
        float(total.mean() / total.std() * np.sqrt(annual)) if total.std() > 0 else None
    )
    return response(
        "feature_03",
        summary_cards=[{"label": "Factor portfolio IR", "value": ir}],
        charts={
            "waterfall": rows,
            "cumulative_contribution": contributions.cumsum()
            .reset_index()
            .to_dict("records"),
        },
        tables={
            "factor_contribution": rows,
            "attribution_reconciliation": [
                {
                    "factor_sum": float(total.sum()),
                    "basis": "additive daily P&L contributions, not compounded cumulative returns",
                }
            ],
        },
        meta={
            "frequency": frequency,
            "factor_exposures": weights,
            "missing_output_reasons": {
                "brinson_fachler": "Requires dated stock and benchmark holdings",
                "carryover": "Requires dated stock holdings and realized stock returns",
                "selection_residual": "No observed portfolio return series supplied",
            },
            "method": "Fixed supplied exposure factor P&L; calendar buckets sum daily contributions",
        },
    )


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("03")
OUTPUTS = _outputs("03")
