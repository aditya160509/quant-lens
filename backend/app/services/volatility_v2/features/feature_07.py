"""Feature 07: Multivariate volatility and DCC proxy engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.linalg import eigh as scipy_eigh

from app.services.volatility_v2.core.analytics import DEFAULT_ASSETS, compact_records, corr_from_cov, covariance_methods, dcc_garch_mle, dcc_midas_long_run_corr, fisher_z_test_correlation_amplification, load_assets, matrix_records, minimum_torsion, parse_weights, response, returns_panel, summary_card


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload, default=payload.get("assets") or DEFAULT_ASSETS[:8])
    ret = returns_panel(ohlcv)
    ret = ret[[c for c in ret.columns if c in assets]].dropna(axis=1, thresh=120).fillna(0)
    methods = covariance_methods(ret, half_life=int(payload.get("half_life") or 63))
    dcc_cov, dcc_corr, dcc_params = dcc_garch_mle(ret)
    methods["dcc_mle"] = dcc_cov
    corr = {name: corr_from_cov(cov) for name, cov in methods.items()}
    corr["dcc_mle"] = dcc_corr
    current = corr["dcc_mle"]
    assets_live = list(current.columns)
    weights = parse_weights(payload, assets_live)
    cov = methods["dcc_mle"].reindex(index=assets_live, columns=assets_live)
    port_var = float(weights.to_numpy() @ cov.to_numpy() @ weights.to_numpy())
    sigma = float(np.sqrt(max(port_var, 0)))
    contrib = weights * (cov @ weights) / max(sigma, 1e-12)
    normal = ret.iloc[: max(1, int(len(ret) * 0.75))].corr().fillna(0)
    avg_abs = ret.abs().mean(axis=1)
    crisis_mask = avg_abs >= np.percentile(avg_abs.to_numpy(dtype=float), 90)
    normal_mask = ~crisis_mask
    crisis = ret[crisis_mask].corr().fillna(0)
    delta = crisis - normal
    try:
        prob_weights = ret.abs().mean(axis=1).rank(pct=True).clip(0, 1)
        eps = ret[assets_live].sub(ret[assets_live].mean()).to_numpy(dtype=float)
        w = prob_weights.reindex(ret.index).fillna(0).to_numpy(dtype=float)
        wcov = (eps * w[:, None]).T @ eps / max(w.sum(), 1e-12) * 252
        prob_crisis_corr = corr_from_cov(pd.DataFrame(wcov, index=assets_live, columns=assets_live))
    except Exception:
        prob_crisis_corr = crisis
    eig = scipy_eigh(cov.to_numpy(dtype=float), check_finite=False, eigvals_only=True)
    eig_sorted = np.array(sorted(eig, reverse=True), dtype=float)
    cum = np.cumsum(eig_sorted) / max(eig_sorted.sum(), 1e-12)
    try:
        minv = np.linalg.solve(cov.to_numpy(dtype=float) + np.eye(len(cov)) * 1e-10, np.ones(len(cov)))
    except Exception:
        minv = np.linalg.pinv(cov.to_numpy(dtype=float)) @ np.ones(len(cov))
    minv = minv / max(minv.sum(), 1e-12)
    pair = payload.get("factor_pair") or payload.get("asset_pair") or (assets_live[:2] if len(assets_live) >= 2 else assets_live)
    if isinstance(pair, str):
        pair = pair.replace(";", ",").split(",")
    pair = [p for p in pair if p in ret.columns][:2]
    dcc_ts = pd.DataFrame({"date": ret.index, "dcc_correlation": ret[pair[0]].rolling(126).corr(ret[pair[1]])}) if len(pair) == 2 else pd.DataFrame()
    midas_corr = dcc_midas_long_run_corr(ret[assets_live], k_lags=int(payload.get("midas_k") or 36))
    if len(pair) == 2 and not midas_corr.empty:
        dcc_ts["dcc_midas_long_run"] = float(midas_corr.loc[pair[0], pair[1]])
    condition_rows = []
    roll = min(252, max(80, len(ret) // 3))
    for i in range(roll, len(ret), max(1, len(ret) // 220)):
        sub_cov = ret.iloc[i - roll : i][assets_live].cov() * 252
        condition_rows.append({"date": ret.index[i], "condition_number": float(np.linalg.cond(sub_cov.to_numpy() + np.eye(len(sub_cov)) * 1e-10))})
    torsion = minimum_torsion(cov, weights)
    fisher = fisher_z_test_correlation_amplification(ret[assets_live], normal_mask, crisis_mask)
    return response(
        "07",
        [summary_card("Portfolio Vol", sigma, "ann"), summary_card("Avg Corr", float(current.to_numpy()[np.triu_indices(len(current), 1)].mean()) if len(current) > 1 else 1, "corr"), summary_card("Condition No", float(np.linalg.cond(cov.to_numpy())), "")],
        charts={"correlation_heatmap": matrix_records(current), "dcc_midas_long_run_correlation": matrix_records(midas_corr) if not midas_corr.empty else [], "normal_vs_crisis_correlation": {"normal": matrix_records(normal), "crisis": matrix_records(crisis), "delta": matrix_records(delta)}, "probability_weighted_crisis_correlation": matrix_records(prob_crisis_corr), "dcc_time_series": compact_records(dcc_ts), "condition_number_history": compact_records(pd.DataFrame(condition_rows)), "eigenvalue_decomposition": [{"rank": i + 1, "eigenvalue": float(v), "cumulative_variance": float(cum[i])} for i, v in enumerate(eig_sorted)], "pairwise_covariance_contribution": matrix_records(cov.mul(np.outer(weights, weights), axis=0))},
        tables={"sample_ewma_lw_dcc_comparison": [{"method": name, "avg_correlation": float(corr[name].to_numpy()[np.triu_indices(len(corr[name]), 1)].mean()) if len(corr[name]) > 1 else 1, "condition_number": float(np.linalg.cond(methods[name].to_numpy()))} for name in methods], "portfolio_risk_attribution": [{"asset": a, "weight": float(weights[a]), "mrc": float(contrib[a]), "pct_total_risk": float(contrib[a] / max(contrib.sum(), 1e-12))} for a in assets_live], "minimum_torsion_risk_attribution": torsion, "fisher_z_crisis_amplification": fisher[:50], "minimum_variance_portfolio": [{"asset": a, "weight": float(w)} for a, w in zip(assets_live, minv)], "portfolio_comparison": [{"portfolio": "current", "projected_vol": sigma}, {"portfolio": "equal_weight", "projected_vol": float(np.sqrt((np.ones(len(cov))/len(cov)) @ cov.to_numpy() @ (np.ones(len(cov))/len(cov))))}, {"portfolio": "minimum_variance", "projected_vol": float(np.sqrt(minv @ cov.to_numpy() @ minv))}], "diversification_ratio": [{"value": float((weights.abs() @ np.sqrt(np.diag(cov))) / max(sigma, 1e-12))}]},
        meta={"assets": assets_live, "implemented_outputs": 11, "estimation": "Two-stage DCC-GARCH MLE with DCC-MIDAS long-run component, probability-weighted crisis correlation, Fisher amplification tests, and minimum torsion attribution.", **dcc_params},
    )
