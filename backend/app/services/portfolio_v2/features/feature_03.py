"""Observed benchmark, exact attribution linking and genuine FF factor contributions."""

import numpy as np
import pandas as pd
from ..core.context import load_context, feature_meta, parse_weights
from ..core.common import response, compact_records
from ..core.data_loader import returns_matrix, load_factor_returns
from ..core.stats import portfolio_return_series
from ..core.attribution import (
    brinson_fachler,
    risk_attribution_xsr,
    linked_effects,
    factor_attribution,
    sector_selection_null,
)

from .inputs import inputs_for, output

FEATURE_ID = "03"
FEATURE_NAME = "Performance Attribution Engine"


def run(payload=None):
    payload = payload or {}
    ctx = load_context(payload)
    r = ctx["returns"]
    w = ctx["weights"]
    port = portfolio_return_series(r, w)
    benchmark = payload.get("benchmark", "equal_weight")
    bench_w = None
    issues = []
    if payload.get("benchmark_weights") is not None:
        bench_w = parse_weights(
            {"weights": payload["benchmark_weights"]}, ctx["symbols"]
        )
        bench = portfolio_return_series(r, bench_w)
    elif benchmark == "equal_weight":
        bench_w = pd.Series(1 / len(r.columns), index=r.columns)
        bench = r @ bench_w
    else:
        bench = (
            returns_matrix([benchmark], ctx["lookback_days"], ctx["frequency"])
            .iloc[:, 0]
            .reindex(r.index)
        )
        if bench.isna().any():
            raise ValueError("Benchmark has missing observed returns")
        issues.append(
            "Brinson grouping requires actual benchmark constituent weights; an index return series cannot supply them"
        )
    active = port - bench
    bf = []
    brinson = []
    linked = []
    if (
        bench_w is not None
        and (w >= 0).all()
        and (bench_w >= 0).all()
        and np.isclose(w.sum(), 1)
        and np.isclose(bench_w.sum(), 1)
    ):
        bf = brinson_fachler(r, w, bench_w, ctx["sectors"])
        brinson = brinson_fachler(r, w, bench_w, ctx["sectors"], method="bhb")
        effects = pd.DataFrame(index=r.index)
        for date in r.index:
            per = brinson_fachler(r.loc[[date]], w, bench_w, ctx["sectors"])
            effects.loc[date, "allocation"] = sum(x["allocation"] for x in per)
            effects.loc[date, "selection"] = sum(x["selection"] for x in per)
            effects.loc[date, "interaction"] = sum(x["interaction"] for x in per)
        for method in ["carino", "menchero", "grap"]:
            values = linked_effects(effects, port, bench, method).sum()
            linked.extend(
                {
                    "method": method,
                    "effect": c,
                    "linked_contribution": float(values[c]),
                    "arithmetic_naive": float(effects[c].sum()),
                    "total_active_geometric": float(
                        (1 + port).prod() - (1 + bench).prod()
                    ),
                }
                for c in values.index
            )
    elif bench_w is not None:
        issues.append(
            "Brinson sector attribution requires long-only books with net weights summing to one"
        )
    model = payload.get("factor_model", "FF5+MOM")
    cols = (
        ["mkt_rf", "smb", "hml"]
        + (["rmw", "cma"] if model in {"FF5", "FF5+MOM"} else [])
        + (["mom"] if model == "FF5+MOM" else [])
    )
    factors = (
        pd.DataFrame(payload["factor_returns"])
        .assign(date=lambda df: pd.to_datetime(df.date))
        .set_index("date")
        if payload.get("factor_returns")
        else load_factor_returns().set_index("date")
    )
    if ctx["frequency"] != "daily":
        factors = (1 + factors).resample(
            "W-FRI" if ctx["frequency"] == "weekly" else "ME"
        ).prod(min_count=1) - 1
    if set(cols) - set(factors):
        raise ValueError("Matching observed factors unavailable")
    waterfall, fit = factor_attribution(active, factors[cols])
    skill = sector_selection_null(
        r, w, bench, ctx["sectors"], int(payload.get("bootstrap_draws", 1000))
    )
    eq = (1 + port).cumprod()
    dd = eq / eq.cummax().clip(lower=1) - 1
    trough = dd.idxmin()
    prefix = eq.loc[:trough]
    peak = prefix.idxmax() if prefix.max() >= 1 else None
    interval = (
        r.loc[(r.index > peak) & (r.index <= trough)]
        if peak is not None
        else r.loc[:trough]
    )
    pr = port.reindex(interval.index)
    preceding = (1 + pr).cumprod().shift(1, fill_value=1)
    contributions = interval.mul(w, axis=1).mul(preceding, axis=0).sum()
    active_weights = w - bench_w if bench_w is not None else w
    tables = {
        "brinson_table": brinson,
        "brinson_fachler": bf,
        "factor_attribution": waterfall,
        "factor_regression": fit["coefficients"],
        "linking_methods": linked,
        "drawdown_attribution": [
            {
                "ticker": c,
                "contribution": float(v),
                "episode_start": peak,
                "episode_trough": trough,
            }
            for c, v in contributions.items()
        ],
        "risk_attribution": risk_attribution_xsr(r, active_weights)
        if bench_w is not None
        else [],
        "skill_luck": [{k: v for k, v in skill.items() if k != "null_distribution"}],
        "skill_luck_null_distribution": skill["null_distribution"],
    }
    return response(
        FEATURE_ID,
        [
            {
                "label": "Active Annual Return",
                "value": float(active.mean() * ctx["annualization_factor"]),
            }
        ],
        {
            "attribution_waterfall": waterfall,
            "active_return_series": compact_records(
                active.rename("active_return").reset_index()
            ),
        },
        tables,
        meta={
            **feature_meta(ctx, issues),
            "benchmark": benchmark,
            "factor_model": model,
            "factor_attribution_units": "Mean return contribution per observed period; active factor loadings estimated by OLS/HAC",
            "skill_null": skill["null"],
        },
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("attribution_waterfall", "charts", "waterfall", True),
    output("active_return_series", "charts", "line", False),
    output("brinson_table"),
    output("brinson_fachler"),
    output("factor_attribution"),
    output("factor_regression"),
    output("linking_methods"),
    output("drawdown_attribution"),
    output("risk_attribution"),
    output("skill_luck"),
    output("skill_luck_null_distribution"),
]
