"""Matured cross-sectional IC monitoring and observed structural-break tests."""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import breaks_cusumolsresid
from app.services.factors_v2.core.analytics import response
from app.services.factors_v2.core.panel import cross_sectional_ic


def break_diagnostic(series):
    y = pd.to_numeric(series, errors="coerce").dropna().to_numpy()
    if len(y) < 30 or np.std(y) == 0:
        return {"status": "insufficient_or_flat_history", "sample_size": len(y)}
    fit = sm.OLS(y, np.ones((len(y), 1))).fit()
    stat, pvalue, critical = breaks_cusumolsresid(fit.resid, ddof=1)
    return {
        "diagnostic": "statsmodels_ols_residual_cusum",
        "statistic": float(stat),
        "p_value": float(pvalue),
        "critical_values": critical,
        "sample_size": len(y),
    }


def run(payload):
    factors = payload.get("factors") or [payload.get("factor", "momentum_12_1")]
    rows = []
    charts = {}
    breaks = []
    alerts = []
    recent = int(payload.get("recent_observations", 21))
    baseline = int(payload.get("baseline_observations", 63))
    for factor in factors:
        ic = cross_sectional_ic(
            {**payload, "factor": factor},
            int(payload.get("ic_horizon", 21)),
            int(payload.get("snapshot_step", 5)),
        )
        s = ic.set_index("date").ic if len(ic) else pd.Series(dtype=float)
        recent_s = s.iloc[-recent:]
        reference = s.iloc[-baseline - recent : -recent]
        z = (
            (recent_s.mean() - reference.mean())
            / (reference.std() / np.sqrt(len(recent_s)))
            if len(reference) >= 20 and len(recent_s) >= 5 and reference.std() > 0
            else None
        )
        diagnostic = break_diagnostic(s.tail(baseline + recent))
        breaks.append({"factor": factor, **diagnostic})
        row = {
            "factor": factor,
            "recent_ic": float(recent_s.mean()) if len(recent_s) else None,
            "ic_z_score": float(z) if z is not None else None,
            "observations": len(s),
            "break_p_value": diagnostic.get("p_value"),
        }
        rows.append(row)
        charts[factor] = [{"date": d, "value": v} for d, v in s.tail(260).items()]
        if z is not None and z < float(payload.get("ic_drift_threshold", -1.5)):
            alerts.append({"type": "ic_drift", "level": "high", **row})
    from app.services.factors_v2.core.alerts import record

    events = record(payload, rows, alerts)
    return response(
        "feature_13",
        "ok" if any(r["observations"] for r in rows) else "warning",
        charts={"ic_drift": charts},
        tables={
            "signal_health": rows,
            "structural_break_diagnostic": breaks,
            "alert_log": events,
            "alert_policy": [
                {"channel": "in_app", "status": "persisted_idempotent_dated_events"},
                {
                    "channel": "email_webhook_slack",
                    "status": "unavailable_no_delivery_worker",
                },
            ],
        },
        alerts=alerts,
        meta={
            "method": "Formation-date cross-sectional Spearman IC; disjoint recent/baseline observations, labels available only at maturity",
            "missing_output_reasons": {
                "weighted_health_score": "No empirically calibrated 0-100 health mapping",
                "chow": "CUSUM is reported under its actual name, not a Chow coefficient test",
            },
            "inference_limitations": "IC dependence can invalidate naive drift-z calibration; CUSUM assumes its documented residual conditions",
        },
    )


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("13")
OUTPUTS = _outputs("13")
