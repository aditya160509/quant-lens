"""Price-derived macro loadings with consistent OLS/HAC inference and declared targets."""

import numpy as np
import pandas as pd
from ..core.context import load_context, feature_meta
from ..core.common import response, compact_records
from ..core.data_loader import load_macro
from ..core.stats import portfolio_return_series, newey_west_regression
from ..core.attribution import risk_attribution_xsr

from .inputs import inputs_for, output

FEATURE_ID = "05"
FEATURE_NAME = "Market-Implied Macro Factor Model"


def run(payload=None):
    payload = payload or {}
    ctx = load_context(payload)
    returns = ctx["returns"]
    port = portfolio_return_series(returns, ctx["weights"])
    if payload.get("factor_returns"):
        X = pd.DataFrame(payload["factor_returns"])
        X.date = pd.to_datetime(X.date)
        X = X.set_index("date")
    else:
        macro = load_macro().set_index("date")
        selected = payload.get(
            "macro_factors", ["vixcls", "yc_slope_10y_2y", "bamlh0a0hym2"]
        )
        allowed = {
            "vixcls",
            "vix_close",
            "yc_slope_10y_2y",
            "bamlh0a0hym2",
            "bamlc0a0cm",
            "dgs10",
            "dgs2",
            "dexuseu",
            "dexjpus",
        }
        if set(selected) - allowed or set(selected) - set(macro):
            raise ValueError("Unsupported observed price-derived macro factors")
        # Rate and spread changes are differences in percentage-point units;
        # percent changes of a sign-changing yield curve are undefined.
        levels = macro[selected].reindex(port.index)
        X = pd.DataFrame(index=port.index)
        for c in selected:
            X[c] = (
                levels[c].diff()
                if c
                in {"yc_slope_10y_2y", "bamlh0a0hym2", "bamlc0a0cm", "dgs10", "dgs2"}
                else levels[c].pct_change(fill_method=None)
            )
    X = X.replace([np.inf, -np.inf], np.nan).reindex(port.index)
    joined = X.join(port.rename("portfolio")).dropna()
    X = joined[X.columns]
    y = joined.portfolio
    fit = newey_west_regression(y, X, 4)
    betas = {r["factor"]: r["beta"] for r in fit["coefficients"]}
    targets = payload.get("target_exposures", {})
    bands = payload.get("tolerance_bands", {})
    limits = payload.get("risk_budget_limits", {})
    if (set(targets) | set(bands) | set(limits)) - set(X):
        raise ValueError("Targets and limits contain unknown factors")
    exposure = np.array([betas[c] for c in X])
    fcov = X.cov().to_numpy()
    factor_variance = float(exposure @ fcov @ exposure)
    total_variance = float(y.var())
    contributions = exposure * (fcov @ exposure)
    rows = []
    alerts = []
    for i, c in enumerate(X):
        target = targets.get(c)
        tolerance = bands.get(c)
        deviation = betas[c] - float(target) if target is not None else None
        if tolerance is not None and float(tolerance) <= 0:
            raise ValueError("Tolerance bands must be positive")
        severity = (
            "red"
            if tolerance is not None and abs(deviation or 0) > 2 * float(tolerance)
            else "amber"
            if tolerance is not None and abs(deviation or 0) > float(tolerance)
            else "clear"
        )
        share = float(contributions[i] / total_variance) if total_variance > 0 else None
        rows.append(
            {
                **next(r for r in fit["coefficients"] if r["factor"] == c),
                "target": target,
                "deviation": deviation,
                "tolerance": tolerance,
                "alert_status": severity,
                "variance_contribution": float(contributions[i]),
                "total_variance_fraction": share,
                "risk_budget_limit": limits.get(c),
                "budget_breached": share > float(limits[c])
                if c in limits and share is not None
                else None,
            }
        )
        if severity != "clear":
            alerts.append(
                {
                    "factor": c,
                    "severity": severity,
                    "message": "Observed beta exceeds declared tolerance",
                }
            )
    asset = []
    for c in returns:
        afit = newey_west_regression(returns[c].reindex(X.index), X, 4)
        asset.extend({"ticker": c, **row} for row in afit["coefficients"])
    window = int(payload.get("rolling_window", 126))
    rolling = []
    for end in range(window, len(X) + 1, 21):
        rfit = newey_west_regression(
            y.iloc[end - window : end], X.iloc[end - window : end], 4
        )
        rolling.extend(
            {"date": X.index[end - 1], **row} for row in rfit["coefficients"]
        )
    tables = {
        "macro_exposures": rows,
        "asset_exposures": asset,
        "unintended_macro_bets": [r for r in rows if r["alert_status"] != "clear"],
        "factor_risk_budget": rows,
        "marginal_portfolio_risk": [
            {
                "ticker": row["ticker"],
                "marginal_daily_volatility": row["mcte"],
                "component_daily_volatility": row["component_te"],
            }
            for row in risk_attribution_xsr(returns, ctx["weights"])
        ],
        "variance_decomposition": [
            {
                "explained_variance": factor_variance,
                "residual_variance": float(total_variance - factor_variance),
                "r2": fit["r2"],
            }
        ],
    }
    return response(
        FEATURE_ID,
        [{"label": "Macro R2", "value": fit["r2"]}],
        {
            "macro_factor_returns": compact_records(X.reset_index()),
            "rolling_exposure": rolling,
        },
        tables,
        meta={
            **feature_meta(ctx),
            "transform": "Treasury slope is simultaneous observed DGS10 minus DGS2 when daily yields are available. Observed rate/spread differences in percentage points; observed VIX/FX simple percentage changes; no zero-fill",
            "interpretation": "Descriptive market-implied exposure, not a vintage-safe economic forecasting model; fair-value prices and population crowding ranks are not fabricated",
        },
        alerts=alerts,
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("macro_factor_returns", "charts", "line", True),
    output("rolling_exposure", "charts", "line", False),
    output("macro_exposures"),
    output("asset_exposures"),
    output("unintended_macro_bets"),
    output("factor_risk_budget"),
    output("marginal_portfolio_risk"),
    output("variance_decomposition"),
]
