"""Feature 8: Factor Covariance Matrix and Risk Forecasting."""

from typing import Any, Dict

import numpy as np
import pandas as pd

from app.services.factors_v2.core.analytics import (
    covariance_payload,
    dcc_garch_payload,
    factor_returns,
    matrix_records,
    response,
)
from app.services.factors_v2.core.data_loader import load_category7_macro
from app.services.factors_v2.core.performance import compute_mode, runtime_meta


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    mode = compute_mode(payload)
    rets = factor_returns(payload).dropna().tail(int(payload.get("window_days", 1260)))
    if rets.empty:
        return response(
            "feature_08", "warning", meta={"warning": "No factor returns available"}
        )
    requested_method = str(payload.get("method", "ledoit_wolf")).lower()
    method = requested_method
    dcc_allowed = True
    dcc = (
        dcc_garch_payload(
            rets,
            a=float(payload.get("dcc_a", 0.03)),
            b=float(payload.get("dcc_b", 0.94)),
        )
        if method == "dcc_ewma"
        else {}
    )
    if method == "dcc_ewma" and not dcc:
        raise ValueError("Insufficient data for EWMA-standardized DCC recursion")
    if method == "dcc_ewma" and dcc:
        cov = covariance_payload(
            rets, method="sample", half_life=int(payload.get("half_life", 63))
        )
        cov["covariance"] = dcc["covariance"]
        cov["correlation"] = dcc["correlation"]
        cov["volatility"] = np.sqrt(np.diag(dcc["covariance"])).tolist()
        eig = np.linalg.eigvalsh(dcc["covariance"].values)
        cov["eigenvalues"] = sorted([float(v) for v in eig], reverse=True)
        cov["condition_number"] = float(
            np.nanmax(eig)
            / max(np.nanmin(eig[eig > 1e-12]) if (eig > 1e-12).any() else 1e-12, 1e-12)
        )
    else:
        cov = covariance_payload(
            rets, method=method, half_life=int(payload.get("half_life", 63))
        )
    cov_matrix = cov["covariance"]
    cov_values = cov_matrix.to_numpy(dtype=float)
    finite_symmetric = bool(
        pd.notna(cov_values).all()
        and (abs(cov_values) < 1e12).all()
        and cov_matrix.sub(cov_matrix.T).abs().max().max() < 1e-8
    )
    macro = load_category7_macro().set_index("date").reindex(rets.index).shift(1)
    if "vix_close" not in macro:
        raise ValueError("Observed VIX series is unavailable")
    vix = macro.vix_close
    stress_mask = vix > float(payload.get("stress_vix", 30))
    crisis = rets.loc[stress_mask & vix.notna()]
    normal = rets.loc[~stress_mask & vix.notna()]
    stress_method = "prior_observed_vix_threshold"
    crisis_corr = crisis.corr() if len(crisis) > 20 else pd.DataFrame()
    normal_corr = normal.corr() if len(normal) > 20 else pd.DataFrame()
    delta = (
        crisis_corr - normal_corr
        if len(crisis_corr) and len(normal_corr)
        else pd.DataFrame()
    )
    min_var = _minimum_variance_combination(cov_matrix)
    stability = _covariance_stability(normal, crisis)
    pair_corr = _rolling_pair_correlation(rets, payload)
    risk_decomp = _portfolio_risk_decomposition(cov_matrix, payload)
    preset_comparison = _crisis_preset_comparison(rets, normal_corr, crisis_corr, delta)
    return response(
        "feature_08",
        "ok",
        summary_cards=[
            {"label": "Condition Number", "value": cov.get("condition_number")},
            {"label": "Factors", "value": len(rets.columns)},
        ],
        charts={
            "correlation_heatmap": matrix_records(cov["correlation"]),
            "dcc_correlation_heatmap": matrix_records(dcc["correlation"])
            if dcc
            else [],
            "dcc_average_correlation": [
                {"date": k, "value": v}
                for k, v in dcc.get("avg_correlation_path", pd.Series(dtype=float))
                .tail(260)
                .items()
            ],
            "normal_correlation": matrix_records(normal_corr)
            if not normal_corr.empty
            else [],
            "crisis_correlation": matrix_records(crisis_corr)
            if not crisis_corr.empty
            else [],
            "correlation_amplification": matrix_records(delta),
            "normal_vs_crisis": {
                "normal": matrix_records(normal_corr) if not normal_corr.empty else [],
                "crisis": matrix_records(crisis_corr) if not crisis_corr.empty else [],
                "delta": matrix_records(delta),
            },
            "crisis_preset_comparison": preset_comparison,
            "rolling_pair_correlation": pair_corr,
            "portfolio_risk_decomposition": risk_decomp.get(
                "pairwise_contributions", []
            ),
            "eigenvalues": [
                {"rank": i + 1, "value": v} for i, v in enumerate(cov["eigenvalues"])
            ],
            "factor_volatility": [
                {"factor": c, "annualized_vol": float(v)}
                for c, v in zip(rets.columns, cov["volatility"])
            ],
        },
        tables={
            "annualized_covariance": matrix_records(cov["covariance"]),
            "dcc_annualized_covariance": matrix_records(dcc["covariance"])
            if dcc
            else [],
            "volatility": [
                {"factor": c, "annualized_vol": float(v)}
                for c, v in zip(rets.columns, cov["volatility"])
            ],
            "minimum_variance_factor_combination": min_var,
            "covariance_stability": stability,
            "portfolio_risk_decomposition": risk_decomp.get("factor_contributions", []),
            "portfolio_pairwise_risk_decomposition": risk_decomp.get(
                "pairwise_contributions", []
            ),
            "matrix_validation": [
                {
                    "finite_symmetric": finite_symmetric,
                    "factors": len(rets.columns),
                    "requested_method": requested_method,
                    "used_method": method,
                    "dcc_allowed": dcc_allowed,
                }
            ],
            "crisis_preset_comparison": [
                {
                    "preset": row.get("preset"),
                    "observations": row.get("observations"),
                    "method": row.get("method"),
                }
                for row in preset_comparison.get("presets", [])
            ],
        },
        alerts=(
            [{"level": "medium", "message": "Covariance matrix is ill-conditioned"}]
            if cov.get("condition_number", 0) > 100
            else []
        )
        + (
            []
            if finite_symmetric
            else [
                {
                    "level": "high",
                    "message": "Covariance validation failed finite/symmetric check",
                }
            ]
        )
        + (
            [
                {
                    "level": "medium",
                    "message": "DCC-GARCH disabled for >15 factors in realtime; Ledoit-Wolf used",
                }
            ]
            if requested_method in {"dcc_ewma"} and not dcc_allowed
            else []
        ),
        meta={
            **runtime_meta(
                "feature_08",
                payload,
                ["Requested covariance estimator is applied without fallback"],
            ),
            "method": method,
            "requested_method": requested_method,
            "dcc_method": "EWMA volatility with fixed requested DCC recursion parameters; not GARCH/MLE"
            if dcc
            else "not_requested",
            "dcc_a": dcc.get("a"),
            "dcc_b": dcc.get("b"),
            "finite_symmetric": finite_symmetric,
            "stress_method": stress_method,
            "crisis_observations": int(len(crisis)),
            "normal_observations": int(len(normal)),
            "audit_closures": [
                "normal/crisis/delta structured matrices",
                "minimum variance factor combination",
                "covariance stability score",
                "factor-pair rolling correlation",
                "optional portfolio risk decomposition",
            ],
        },
    )


def _minimum_variance_combination(cov_matrix: pd.DataFrame) -> list[dict[str, Any]]:
    if cov_matrix.empty:
        return []
    sigma = cov_matrix.to_numpy(dtype=float)
    n = sigma.shape[0]
    inv = np.linalg.pinv(sigma)
    ones = np.ones(n)
    denominator = float(ones @ inv @ ones)
    if denominator <= 0 or not np.isfinite(denominator):
        raise ValueError("Minimum-variance weights are undefined for this covariance")
    w = inv @ ones / denominator
    return [
        {"factor": factor, "min_variance_weight": float(w[i])}
        for i, factor in enumerate(cov_matrix.columns)
    ]


def _covariance_stability(
    normal: pd.DataFrame, crisis: pd.DataFrame
) -> list[dict[str, Any]]:
    if len(normal) < 20 or len(crisis) < 20:
        return [
            {
                "status": "insufficient_crisis_or_normal_observations",
                "normal_obs": int(len(normal)),
                "crisis_obs": int(len(crisis)),
            }
        ]

    def condition(frame):
        eig = np.linalg.eigvalsh(np.cov(frame.dropna().values.T))
        return float(
            np.nanmax(eig)
            / max(np.nanmin(eig[eig > 1e-12]) if (eig > 1e-12).any() else 1e-12, 1e-12)
        )

    normal_cond = condition(normal)
    crisis_cond = condition(crisis)
    return [
        {
            "normal_condition_number": normal_cond,
            "crisis_condition_number": crisis_cond,
            "crisis_normal_ratio": crisis_cond / max(normal_cond, 1e-12),
            "normal_obs": int(len(normal)),
            "crisis_obs": int(len(crisis)),
        }
    ]


def _rolling_pair_correlation(
    rets: pd.DataFrame, payload: Dict[str, Any]
) -> list[dict[str, Any]]:
    pair = payload.get("factor_pair") or []
    if isinstance(pair, str):
        pair = [p.strip() for p in pair.split(",")]
    if len(pair) < 2:
        pair = list(rets.columns[:2])
    a, b = pair[0], pair[1]
    if a not in rets.columns or b not in rets.columns:
        raise ValueError("Unknown factor_pair column")
    corr = (
        rets[a]
        .rolling(int(payload.get("rolling_corr_window", 252)), min_periods=60)
        .corr(rets[b])
        .dropna()
        .tail(260)
    )
    return [
        {
            "date": str(idx.date()),
            "factor_a": a,
            "factor_b": b,
            "correlation": float(value),
        }
        for idx, value in corr.items()
    ]


def _portfolio_risk_decomposition(
    cov_matrix: pd.DataFrame, payload: Dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    weights = (
        payload.get("portfolio_weights")
        or payload.get("optimal_weights_from_f10")
        or {}
    )
    if not weights:
        return {"factor_contributions": [], "pairwise_contributions": []}
    names = list(cov_matrix.columns)
    w = np.asarray([float(weights.get(name, 0.0)) for name in names], dtype=float)
    if np.allclose(w, 0):
        return {"factor_contributions": [], "pairwise_contributions": []}
    if set(weights) - set(names) or not np.isfinite(w).all():
        raise ValueError("Portfolio weights must be finite and name observed factors")
    sigma = cov_matrix.to_numpy(dtype=float)
    port_var = float(w @ sigma @ w)
    port_vol = np.sqrt(max(port_var, 1e-12))
    mcr = (sigma @ w) / port_vol
    contrib = w * mcr
    pair = np.outer(w, w) * sigma
    factor_rows = [
        {
            "factor": name,
            "weight": float(w[i]),
            "marginal_risk": float(mcr[i]),
            "risk_contribution": float(contrib[i]),
            "pct_of_total_risk": float(contrib[i] / port_vol * 100),
        }
        for i, name in enumerate(names)
    ]
    return {
        "factor_contributions": factor_rows,
        "pairwise_contributions": matrix_records(
            pd.DataFrame(pair, index=names, columns=names)
        ),
    }


def _crisis_preset_comparison(
    rets: pd.DataFrame,
    normal_corr: pd.DataFrame,
    fallback_crisis: pd.DataFrame,
    fallback_delta: pd.DataFrame,
) -> dict[str, list[dict[str, Any]]]:
    presets = [
        ("GFC", "2008-01-01", "2009-06-30"),
        ("COVID", "2020-02-01", "2020-05-31"),
        ("RATE SHOCK 2022", "2022-01-01", "2022-12-31"),
        ("QUANT UNWIND 2025", "2025-07-01", "2025-08-31"),
    ]
    out = []
    base_normal = normal_corr
    for name, start, end in presets:
        window = (
            rets.loc[pd.Timestamp(start) : pd.Timestamp(end)]
            if isinstance(rets.index, pd.DatetimeIndex)
            else pd.DataFrame()
        )
        if len(window) > 20:
            crisis_corr = window.corr()
            method = "calendar_preset"
        else:
            crisis_corr = pd.DataFrame()
            method = "unavailable_preset_history"
        delta = crisis_corr - base_normal.reindex_like(crisis_corr)
        out.append(
            {
                "preset": name,
                "observations": int(len(window)),
                "method": method,
                "normal": matrix_records(base_normal),
                "crisis": matrix_records(crisis_corr),
                "delta": matrix_records(delta),
            }
        )
    return {"presets": out}


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("08")
OUTPUTS = _outputs("08")
