"""Observed crisis correlations and explicitly distinguished diversification measures."""

import numpy as np
import pandas as pd
from ..core.context import load_context, feature_meta
from ..core.common import response, matrix_records, compact_records
from ..core.data_loader import returns_matrix
from ..core.covariance import dcc_garch_cov
from ..core.correlation import (
    network_edges,
    mantegna_mst,
    correlation_hierarchy,
    precision_matrix_network,
    leading_eigenvalue_series,
    diversification_ratio_series,
    chow_test_breakpoints,
    sector_block_analysis,
    marchenko_pastur_threshold,
)

from .inputs import inputs_for, output

FEATURE_ID = "08"
FEATURE_NAME = "Correlation, Diversification and Contagion Network Engine"


def risk_entropy(returns, weights):
    cov = returns.cov()
    w = weights.reindex(cov.columns)
    variance = float(w @ cov @ w)
    if variance <= 0:
        return None, "Zero portfolio variance"
    shares = w * (cov @ w) / variance
    if (shares < -1e-12).any():
        return (
            None,
            "Signed or hedging risk contributions cannot define probability entropy",
        )
    positive = shares[shares > 0]
    return float(np.exp(-(positive * np.log(positive)).sum())), None


def run(payload=None):
    payload = payload or {}
    ctx = load_context(payload)
    r = ctx["returns"]
    window = int(payload.get("correlation_window", 126))
    current = r.tail(window)
    corr = current.corr()
    values = np.linalg.eigvalsh(corr)
    enb, reason = risk_entropy(current, ctx["weights"])
    history = returns_matrix(ctx["symbols"], 20000, ctx["frequency"]).dropna()
    start = pd.Timestamp(payload.get("crisis_start", "2020-02-15"))
    end = pd.Timestamp(payload.get("crisis_end", "2020-04-30"))
    if end < start:
        raise ValueError("crisis_end precedes crisis_start")
    crisis = history.loc[start:end]
    delta = crisis.corr() - corr if len(crisis) >= 20 else pd.DataFrame()
    edges = network_edges(current, float(payload.get("correlation_threshold", 0.6)))
    breaks = []
    pair_paths = []
    dynamics = payload.get("correlation_dynamics", "rolling")
    for edge in sorted(
        network_edges(current, 0), key=lambda e: abs(e["weight"]), reverse=True
    )[:10]:
        rolling = r[edge["source"]].rolling(window).corr(r[edge["target"]])
        pair = f"{edge['source']}:{edge['target']}"
        breaks.extend({"pair": pair, **row} for row in chow_test_breakpoints(rolling))
        if dynamics == "rolling":
            pair_paths.extend(
                {
                    "pair": pair,
                    "date": date,
                    "correlation": float(value),
                    "method": "observed_rolling",
                }
                for date, value in rolling.dropna().items()
            )
        else:
            # Refit on prefixes at each evaluation origin. Never expose a
            # full-sample fitted DCC path as historical causal estimates.
            pair_returns = r[[edge["source"], edge["target"]]]
            if window < 100:
                raise ValueError("DCC dynamics require correlation_window >=100")
            for origin in range(window, len(r) + 1, 21):
                fit = dcc_garch_cov(pair_returns.iloc[:origin])
                cov = fit["covariance"].to_numpy()
                value = cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1])
                pair_paths.append(
                    {
                        "pair": pair,
                        "date": r.index[origin - 1],
                        "correlation": float(value),
                        "method": "prefix_fitted_dcc_garch",
                        "training_end": r.index[origin - 1],
                    }
                )
    # Correct across the displayed pair family as well as candidate split dates.
    for row in breaks:
        if "bonferroni_p_value" in row:
            row["family_adjusted_p_value"] = min(
                1.0,
                row["bonferroni_p_value"] * max(1, len({x["pair"] for x in breaks})),
            )
    bond = payload.get("bond_benchmark", "AGG")
    br = (
        returns_matrix([bond], ctx["lookback_days"], ctx["frequency"])
        .iloc[:, 0]
        .reindex(r.index)
    )
    equity = r @ ctx["weights"]
    tracker = equity.rolling(window).corr(br).dropna()
    issues = (
        []
        if len(crisis) >= 20
        else [
            "Selected crisis window has fewer than 20 complete observed intervals; no zero delta substitute"
        ]
    )
    if reason:
        issues.append(reason)
    covariance = current.cov()
    w = ctx["weights"]
    sigma = float(np.sqrt(w @ covariance @ w))
    dr = float(w.abs() @ current.std() / sigma) if sigma > 0 else None
    return response(
        FEATURE_ID,
        [
            {"label": "Risk Entropy Bets", "value": enb},
            {"label": "Diversification Ratio", "value": dr},
        ],
        {
            "correlation_heatmap": matrix_records(corr),
            "crisis_delta": matrix_records(delta),
            "contagion_network": edges,
            "mantegna_mst": mantegna_mst(corr),
            "partial_correlation_network": precision_matrix_network(current),
            "leading_eigenvalue_series": leading_eigenvalue_series(r, window),
            "diversification_ratio_series": diversification_ratio_series(r, w, window),
            "pair_correlation_paths": pair_paths,
            "equity_bond_correlation": compact_records(
                tracker.rename("correlation").reset_index()
            ),
        },
        {
            "diversification_report": [
                {
                    "risk_entropy_effective_bets": enb,
                    "entropy_unavailable_reason": reason,
                    "eigenvalue_participation_ratio": float(
                        values.sum() ** 2 / (values**2).sum()
                    ),
                    "diversification_ratio": dr,
                    "leading_eigenvalue": float(values[-1]),
                    "mp_lambda_max": marchenko_pastur_threshold(
                        len(r.columns), len(current)
                    ),
                }
            ],
            "eigenvalues": [
                {"rank": i + 1, "eigenvalue": float(v)}
                for i, v in enumerate(values[::-1])
            ],
            "pair_redundancy": edges,
            "trend_break_tests": breaks,
            "sector_block_analysis": sector_block_analysis(current, ctx["sectors"]),
            "hierarchy": correlation_hierarchy(corr),
        },
        meta={
            **feature_meta(ctx, issues),
            "crisis_window": [str(start.date()), str(end.date())],
            "correlation_dynamics": dynamics,
            "dcc_policy": "DCC option refits each prefix at 21-observation evaluation origins, no full-sample retrospective path",
        },
    )


INPUTS = inputs_for(FEATURE_ID)
OUTPUTS = [
    output("correlation_heatmap", "charts", "heatmap", True),
    output("crisis_delta", "charts", "heatmap", False),
    output("contagion_network", "charts", "network", False),
    output("mantegna_mst", "charts", "network", False),
    output("partial_correlation_network", "charts", "network", False),
    output("leading_eigenvalue_series", "charts", "line", False),
    output("diversification_ratio_series", "charts", "line", False),
    output("pair_correlation_paths", "charts", "line", False),
    output("equity_bond_correlation", "charts", "line", False),
    output("diversification_report"),
    output("eigenvalues"),
    output("pair_redundancy"),
    output("trend_break_tests"),
    output("sector_block_analysis"),
    output("hierarchy"),
]
