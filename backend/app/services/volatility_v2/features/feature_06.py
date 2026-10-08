"""Feature 06: daily generalized volatility connectedness and frequency shares."""

from __future__ import annotations
from .inputs import field
import numpy as np
import pandas as pd
from app.services.volatility_v2.core.analytics import (
    load_assets,
    volatility_estimators,
    response,
    summary_card,
    matrix_records,
    clean_json,
)
from app.services.volatility_v2.core.connectedness import (
    rolling_connectedness,
    frequency_connectedness,
    spillovers,
    connectedness_alerts,
    autoregressive_cor,
    bootstrap_irf,
)


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload, default=["SPY", "QQQ", "IWM", "TLT", "GLD"])
    if len(assets) < 2:
        raise ValueError("Connectedness requires at least two explicit assets")
    vol = volatility_estimators(
        ohlcv,
        window=int(payload.get("estimator_window", 21)),
        annualization=int(payload.get("annualization", 252)),
    )
    estimator = str(payload.get("estimator", "yang_zhang"))
    if estimator not in (
        "cc",
        "parkinson",
        "garman_klass",
        "rogers_satchell",
        "yang_zhang",
    ):
        raise ValueError("Unknown volatility estimator")
    panel = vol.pivot(index="date", columns="asset", values=estimator).reindex(
        columns=assets
    )
    complete = panel.notna().all(axis=1) & panel.gt(0).all(axis=1)
    logvol = np.log(panel.loc[complete])
    weighting = str(payload.get("var_weighting", "ols"))
    result = rolling_connectedness(
        logvol,
        window=int(payload.get("rolling_window", 252)),
        interval=int(payload.get("rolling_interval", 1)),
        fevd_horizon=int(payload.get("fevd_horizon", 10)),
        include_network_history=bool(payload.get("include_network_history", False)),
        max_lag=int(payload.get("max_lag", 5)),
        weighting=weighting,
        lag_order=int(payload.get("lag_order", 1)),
        delta=float(payload.get("ew_delta", 0.99)),
    )
    date, model, theta = result["latest"]
    timeline = result["timeline"]
    ranking = spillovers(theta, assets).sort_values("net_spillover", ascending=False)
    history = result["attribution"]
    # Change is measured in observed rolling updates; there is no fabricated month value during warmup.
    for asset in assets:
        previous = [row["net_spillover"] for row in history if row["asset"] == asset]
        ranking.loc[ranking.asset.eq(asset), "net_change_21_updates"] = (
            previous[-1] - previous[-22] if len(previous) > 21 else np.nan
        )
    edges = [
        {
            "source": assets[j],
            "target": assets[i],
            "weight": float(theta[i, j]),
            "net_directional_weight": float(theta[i, j] - theta[j, i]),
        }
        for i in range(len(assets))
        for j in range(len(assets))
        if i != j and theta[i, j] >= float(payload.get("edge_threshold", 0.05))
    ]
    nodes = [
        {
            "id": row["asset"],
            "net_spillover": row["net_spillover"],
            "received_spillover": row["from_spillover"],
        }
        for row in ranking.to_dict("records")
    ]
    gaps = list(result["failures"])
    try:
        frequency = frequency_connectedness(model)
    except (ValueError, np.linalg.LinAlgError) as exc:
        frequency = []
        gaps.append(
            {"output": "frequency_decomposed_connectedness", "reason": str(exc)}
        )
    cor = autoregressive_cor(
        timeline,
        int(payload.get("cor_horizon", 21)),
        float(payload.get("cor_quantile", 0.95)),
    )
    alerts = connectedness_alerts(
        timeline, theta, assets, float(payload.get("alert_threshold", 75))
    )
    ma = model.ma(21)
    irf = [
        {
            "horizon": h,
            "source": assets[j],
            "target": assets[i],
            "response": float(ma[h, i, j]),
        }
        for h in (1, 5, 10, 21)
        for i in range(len(assets))
        for j in range(len(assets))
    ]
    bootstrap_reps = int(payload.get("irf_bootstrap_reps", 100))
    bands, bootstrap_info = bootstrap_irf(
        logvol.iloc[-int(payload.get("rolling_window", 252)) :],
        model,
        reps=bootstrap_reps,
        confidence=float(payload.get("confidence_level", 0.90)),
        max_lag=int(payload.get("max_lag", 5)),
        weighting=weighting,
        lag_order=int(payload.get("lag_order", 1)),
        delta=float(payload.get("ew_delta", 0.99)),
    )
    if "unavailable_reason" in bootstrap_info:
        gaps.append({"output": "var_impulse_response_bands", **bootstrap_info})
    snapshot = clean_json(timeline.reset_index().to_dict("records"))
    out = response(
        "06",
        [
            summary_card(
                "Connectedness", float(timeline.connectedness.iloc[-1]), "pct"
            ),
            summary_card("Top Transmitter", ranking.asset.iloc[0]),
            summary_card("Asset Count", len(assets)),
        ],
        charts={
            "connectedness_index": snapshot,
            "frequency_decomposed_connectedness": frequency,
            "connectedness_at_risk": cor,
            "spillover_network_graph": {"date": date, "nodes": nodes, "edges": edges},
            "network_history": result["network_history"],
            "pairwise_fevd_heatmap": matrix_records(
                pd.DataFrame(theta, index=assets, columns=assets)
            ),
            "rolling_to_from_decomposition": history,
            "var_impulse_response": irf,
            "var_impulse_response_bands": bands,
        },
        tables={
            "net_spillover_ranking": ranking.to_dict("records"),
            "connectedness_at_risk": [cor],
            "connectedness_regime_alert": alerts,
            "estimation_failures": gaps,
        },
        alerts=alerts,
        meta={
            "assets": assets,
            "estimator": estimator,
            "rolling_interval": int(payload.get("rolling_interval", 1)),
            "complete_aligned_observations": len(logvol),
            "excluded_incomplete_or_nonpositive_dates": int((~complete).sum()),
            "var_lag_order": model.lag,
            "var_bic": model.bic,
            "var_method": weighting,
            "var_stable": model.stable,
            "native_quote_returns": True,
            "estimation": "statsmodels OLS VAR with common-range BIC or fixed-lag decay-weighted WLS; Pesaran-Shin generalized FEVD; full-spectrum Barunik-Krehlik shares",
            "ew_lag_selection": "Fixed declared lag_order; no claim that weighted pseudo-likelihood is ordinary BIC",
            "network_history_enabled": bool(
                payload.get("include_network_history", False)
            ),
            "cor_model": "Explicit autoregressive quantile alternative; macro-conditioned predictions require release vintages",
            "frequency_scope": "Infinite-horizon stable VAR spectrum; band contributions sum to full-spectrum connectedness, which need not equal a short finite FEVD horizon",
            "irf_units": "Unorthogonalized response to a unit residual innovation in log volatility",
            "data_gaps": gaps,
            "irf_bootstrap": bootstrap_info,
        },
    )
    if gaps or not model.stable or cor.get("converged") is False:
        out["status"] = "warning"
    return out


# Authoritative contract consumed by the lazy backend manifest.

INPUTS = [
    field("assets", ["SPY", "QQQ", "IWM", "TLT", "GLD"], kind="symbols", group="Data"),
    field("asset", None, kind="text", group="Data"),
    field("lookback_days", 2520, kind="integer", group="Data"),
    field("as_of_date", None, kind="date", group="Data"),
    field("estimator", "yang_zhang", kind=None, group="Model"),
    field("var_weighting", "ols", kind=None, group="Model"),
    field("irf_bootstrap_reps", 100, kind=None, group="Model"),
    field("cor_horizon", 21, kind=None, group="Model"),
    field("cor_quantile", 0.95, kind=None, group="Model"),
    field("alert_threshold", 75, kind=None, group="Model"),
    field("estimator_window", 21, kind=None, group="Model"),
    field("annualization", 252, kind=None, group="Model"),
    field("rolling_window", 252, kind="integer", group="Model"),
    field("rolling_interval", 1, kind=None, group="Model"),
    field("fevd_horizon", 10, kind=None, group="Model"),
    field("include_network_history", False, kind=None, group="Model"),
    field("max_lag", 5, kind=None, group="Model"),
    field("lag_order", 1, kind=None, group="Model"),
    field("ew_delta", 0.99, kind=None, group="Model"),
    field("confidence_level", 0.9, kind=None, group="Model"),
    field("edge_threshold", 0.05, kind=None, group="Model"),
]

OUTPUTS = [
    {
        "key": "connectedness_index",
        "source": "charts",
        "label": "Connectedness index",
        "render": "line",
        "primary": True,
        "help": "Actual observed or fitted connectedness index. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "frequency_decomposed_connectedness",
        "source": "charts",
        "label": "Frequency decomposed connectedness",
        "render": "bar",
        "primary": False,
        "help": "Actual observed or fitted frequency decomposed connectedness. The fitted VAR is unstable, so the frequency integral is unavailable.",
        "empty_reason": "The fitted VAR is unstable, so the frequency integral is unavailable.",
    },
    {
        "key": "connectedness_at_risk",
        "source": "charts",
        "label": "Connectedness at risk",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted connectedness at risk. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "spillover_network_graph",
        "source": "charts",
        "label": "Spillover network graph",
        "render": "network",
        "primary": False,
        "help": "Actual observed or fitted spillover network graph. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "network_history",
        "source": "charts",
        "label": "Network history",
        "render": "network_history",
        "primary": False,
        "help": "Actual observed or fitted network history. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "pairwise_fevd_heatmap",
        "source": "charts",
        "label": "Pairwise fevd heatmap",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted pairwise fevd heatmap. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "rolling_to_from_decomposition",
        "source": "charts",
        "label": "Rolling to from decomposition",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted rolling to from decomposition. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "var_impulse_response",
        "source": "charts",
        "label": "Var impulse response",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted var impulse response. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "var_impulse_response_bands",
        "source": "charts",
        "label": "Var impulse response bands",
        "render": "band",
        "primary": False,
        "help": "Actual observed or fitted var impulse response bands. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "net_spillover_ranking",
        "source": "tables",
        "label": "Net spillover ranking",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted net spillover ranking. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "connectedness_at_risk",
        "source": "tables",
        "label": "Connectedness at risk",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted connectedness at risk. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "connectedness_regime_alert",
        "source": "tables",
        "label": "Connectedness regime alert",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted connectedness regime alert. No historical threshold crossing occurred.",
        "empty_reason": "No historical threshold crossing occurred.",
    },
    {
        "key": "estimation_failures",
        "source": "tables",
        "label": "Estimation failures",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted estimation failures. No estimation failures occurred.",
        "empty_reason": "No estimation failures occurred.",
    },
]
