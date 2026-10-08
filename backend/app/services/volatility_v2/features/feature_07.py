"""Feature 07: causal multivariate risk with observed USD returns."""

from __future__ import annotations
from .inputs import field

import numpy as np
from app.services.volatility_v2.core.analytics import (
    DEFAULT_ASSETS,
    load_assets,
    parse_weights,
    response,
    summary_card,
    matrix_records,
)
from app.services.volatility_v2.core.data_loader import resolve_symbols
from app.services.volatility_v2.core.currency import portfolio_returns
from app.services.volatility_v2.core.covariance import (
    covariance_estimates,
    portfolio_attribution,
)
from app.services.volatility_v2.core.dcc import expanding_dcc, correlation
from app.services.volatility_v2.core.crisis import crisis_correlations
from app.services.volatility_v2.core.torsion import minimum_torsion


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload, default=DEFAULT_ASSETS[:8])
    ret, currency_meta = portfolio_returns(ohlcv, payload)
    ret = ret.reindex(columns=assets)
    if len(assets) < 2:
        raise ValueError("Multivariate volatility requires at least two assets")
    annualization = int(payload.get("annualization", 252))
    methods = covariance_estimates(
        ret, half_life=float(payload.get("half_life", 63)), annualization=annualization
    )
    controls = {
        "min_train": int(payload.get("min_train", 252)),
        "refit_interval": int(payload.get("refit_interval", 63)),
        "annualization": annualization,
        "midas_k": int(payload.get("midas_k", 36)),
    }
    dynamics = payload.get("dynamics", "dcc")
    dcc = expanding_dcc(ret, dynamics=dynamics, **controls)
    methods[dynamics] = dcc["forecast_covariance"]
    warnings, midas = [], dcc if dynamics == "dcc_midas" else None
    if dynamics == "dcc" and payload.get("include_midas", True):
        try:
            midas = expanding_dcc(ret, dynamics="dcc_midas", **controls)
            methods["dcc_midas"] = midas["forecast_covariance"]
        except (ValueError, np.linalg.LinAlgError) as exc:
            warnings.append(f"DCC-MIDAS comparison unavailable: {exc}")
    cov = dcc["forecast_covariance"]
    correlations = {name: covariance.copy() for name, covariance in methods.items()}
    for name, covariance in methods.items():
        correlations[name].iloc[:, :] = correlation(covariance.to_numpy())
    current = correlations[dynamics]
    weights = parse_weights(payload, assets)
    attribution = portfolio_attribution(cov, weights)
    torsion = minimum_torsion(cov, weights)
    crisis = crisis_correlations(ret, ohlcv, payload)
    warnings.extend(crisis["warnings"])
    pair = payload.get("factor_pair", payload.get("asset_pair", assets[:2]))
    if isinstance(pair, str):
        pair = [
            part.strip() for part in pair.replace(";", ",").split(",") if part.strip()
        ]
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise ValueError(
            "asset_pair must contain exactly two distinct requested assets"
        )
    pair = resolve_symbols(pair)
    if len(set(pair)) != 2 or not set(pair).issubset(assets):
        raise ValueError(
            "asset_pair must contain exactly two distinct requested assets"
        )
    left, right = [assets.index(asset) for asset in pair]
    path = [
        {
            "date": row["date"],
            "dcc_correlation": row["correlation"][left][right],
            "training_observed_through": row["training_observed_through"],
            "forecast_observed_through": row["forecast_observed_through"],
        }
        for row in dcc["timeline"]
    ]
    midas_path = (
        [
            {
                "date": row["date"],
                "dcc_midas_correlation": row["correlation"][left][right],
                "long_run_correlation": row["long_run_correlation"][left][right],
                "training_observed_through": row["training_observed_through"],
            }
            for row in midas["timeline"]
        ]
        if midas
        else []
    )
    eigenvalues = np.linalg.eigvalsh(cov.to_numpy())[::-1]
    cumulative = np.cumsum(eigenvalues) / eigenvalues.sum()
    minimum = attribution["minimum_variance_weights"]
    equal = np.ones(len(assets)) / len(assets)
    off_diagonal = np.triu_indices(len(assets), 1)

    def matrix(value):
        return matrix_records(value) if value is not None else []

    result = response(
        "07",
        [
            summary_card("Portfolio Vol", attribution["volatility"], "annual decimal"),
            summary_card(
                "Avg Corr", float(current.to_numpy()[off_diagonal].mean()), "corr"
            ),
            summary_card("Condition No", float(np.linalg.cond(cov.to_numpy()))),
        ],
        charts={
            "correlation_heatmap": matrix(current),
            "correlation_matrices": {
                name: matrix(value) for name, value in correlations.items()
            },
            "dcc_midas_long_run_correlation": matrix(
                midas["forecast_long_run_correlation"]
            )
            if midas
            else [],
            "normal_vs_crisis_correlation": {
                name: matrix(crisis[name]) for name in ("normal", "crisis", "delta")
            },
            "probability_weighted_crisis_correlation": matrix(
                crisis["probability_weighted"]
            ),
            "dcc_time_series": path,
            "dcc_midas_time_series": midas_path,
            "condition_number_history": [
                {"date": row["date"], "condition_number": row["condition_number"]}
                for row in dcc["timeline"]
            ],
            "eigenvalue_decomposition": [
                {
                    "rank": i + 1,
                    "eigenvalue": float(value),
                    "cumulative_variance": float(cumulative[i]),
                }
                for i, value in enumerate(eigenvalues)
            ],
            "pairwise_covariance_contribution": matrix(
                attribution["pairwise_variance"]
            ),
            "minimum_torsion_loadings": matrix(torsion["transformation"]),
            "minimum_torsion_factor_covariance": matrix(torsion["factor_covariance"]),
        },
        tables={
            "sample_ewma_lw_dcc_comparison": [
                {
                    "method": name,
                    "avg_correlation": float(
                        correlations[name].to_numpy()[off_diagonal].mean()
                    ),
                    "condition_number": float(np.linalg.cond(value.to_numpy())),
                    "estimation": "next observation conditional forecast"
                    if name in ("dcc", "dcc_midas")
                    else "observed sample estimate",
                }
                for name, value in methods.items()
            ],
            "portfolio_risk_attribution": attribution["assets"],
            "minimum_torsion_risk_attribution": torsion["attribution"],
            "fisher_z_crisis_amplification": crisis["fisher_tests"],
            "dcc_parameters": dcc["parameters"],
            "dcc_midas_parameters": midas["parameters"] if midas else [],
            "minimum_variance_portfolio": [
                {"asset": asset, "weight": float(weight)}
                for asset, weight in zip(assets, minimum)
            ],
            "portfolio_comparison": [
                {
                    "portfolio": name,
                    "projected_vol": float(np.sqrt(vector @ cov.to_numpy() @ vector)),
                }
                for name, vector in (
                    ("current", weights.to_numpy()),
                    ("equal_weight", equal),
                    ("minimum_variance", minimum),
                )
            ],
            "diversification_ratio": [
                {
                    "value": float(
                        weights.abs()
                        @ np.sqrt(np.diag(cov))
                        / attribution["volatility"]
                    )
                }
            ],
        },
        meta={
            "assets": assets,
            **currency_meta,
            "selected_dynamics": dynamics,
            "asset_pair": pair,
            "annualization": annualization,
            "forecast_observed_through": dcc["forecast_observed_through"],
            "forecast_date": dcc["forecast_date"],
            "forecast_calendar": dcc["forecast_calendar"],
            "minimum_variance_constraint": "fully invested, unconstrained signed weights",
            "torsion": {
                "iterations": torsion["iterations"],
                "objective": torsion["objective"],
                "effective_number_of_bets": torsion["effective_number_of_bets"],
            },
            "crisis_definition": crisis["hard_rule"],
            "probability_weighting": crisis.get("probability_weighting"),
            "midas_target": "estimated Beta(1,theta) convex weights on completed prior monthly standardized-residual correlations",
            "warnings": warnings,
        },
    )
    if warnings:
        result["status"] = "warning"
    return result


# Authoritative contract consumed by the lazy backend manifest.

INPUTS = [
    field(
        "assets",
        ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "USO"],
        kind="symbols",
        group="Data",
    ),
    field("asset", None, kind="text", group="Data"),
    field("lookback_days", 2520, kind="integer", group="Data"),
    field("as_of_date", None, kind="date", group="Data"),
    field("dynamics", "dcc", kind=None, group="Model"),
    field("factor_pair", None, kind="list", group="Model"),
    field("annualization", 252, kind=None, group="Model"),
    field("include_midas", True, kind=None, group="Model"),
    field("min_train", 252, kind=None, group="Model"),
    field("refit_interval", 63, kind=None, group="Model"),
    field("midas_k", 36, kind=None, group="Model"),
    field("half_life", 63, kind=None, group="Model"),
    field("quote_currencies", None, kind="object", group="Data"),
    field("weights", None, kind="object", group="Portfolio"),
    field("states", 4, kind="integer", group="Model"),
    field("regime_min_train", 252, kind="integer", group="Model"),
    field("regime_refit_interval", 126, kind="integer", group="Model"),
    field("hmm_restarts", 3, kind="integer", group="Model"),
    field("crisis_vix_threshold", 30.0),
    field("crisis_percentile_window", 2520),
    field("crisis_percentile_min_history", 252),
    field("regime_asset"),
    field("base_currency", "USD", options=["USD"]),
]

OUTPUTS = [
    {
        "key": "correlation_heatmap",
        "source": "charts",
        "label": "Correlation heatmap",
        "render": "heatmap",
        "primary": True,
        "help": "Actual observed or fitted correlation heatmap. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "correlation_matrices",
        "source": "charts",
        "label": "Correlation matrices",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted correlation matrices. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "dcc_midas_long_run_correlation",
        "source": "charts",
        "label": "Dcc midas long run correlation",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted dcc midas long run correlation. DCC-MIDAS was not selected or completed-month lag history is insufficient.",
        "empty_reason": "DCC-MIDAS was not selected or completed-month lag history is insufficient.",
    },
    {
        "key": "normal_vs_crisis_correlation",
        "source": "charts",
        "label": "Normal vs crisis correlation",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted normal vs crisis correlation. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "probability_weighted_crisis_correlation",
        "source": "charts",
        "label": "Probability weighted crisis correlation",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted probability weighted crisis correlation. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "dcc_time_series",
        "source": "charts",
        "label": "Dcc time series",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted dcc time series. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "dcc_midas_time_series",
        "source": "charts",
        "label": "Dcc midas time series",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted dcc midas time series. DCC-MIDAS was not selected or completed-month lag history is insufficient.",
        "empty_reason": "DCC-MIDAS was not selected or completed-month lag history is insufficient.",
    },
    {
        "key": "condition_number_history",
        "source": "charts",
        "label": "Condition number history",
        "render": "line",
        "primary": False,
        "help": "Actual observed or fitted condition number history. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "eigenvalue_decomposition",
        "source": "charts",
        "label": "Eigenvalue decomposition",
        "render": "bar",
        "primary": False,
        "help": "Actual observed or fitted eigenvalue decomposition. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "pairwise_covariance_contribution",
        "source": "charts",
        "label": "Pairwise covariance contribution",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted pairwise covariance contribution. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "minimum_torsion_loadings",
        "source": "charts",
        "label": "Minimum torsion loadings",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted minimum torsion loadings. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "minimum_torsion_factor_covariance",
        "source": "charts",
        "label": "Minimum torsion factor covariance",
        "render": "heatmap",
        "primary": False,
        "help": "Actual observed or fitted minimum torsion factor covariance. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "sample_ewma_lw_dcc_comparison",
        "source": "tables",
        "label": "Sample ewma lw dcc comparison",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted sample ewma lw dcc comparison. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "portfolio_risk_attribution",
        "source": "tables",
        "label": "Portfolio risk attribution",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted portfolio risk attribution. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "minimum_torsion_risk_attribution",
        "source": "tables",
        "label": "Minimum torsion risk attribution",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted minimum torsion risk attribution. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "fisher_z_crisis_amplification",
        "source": "tables",
        "label": "Fisher z crisis amplification",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted fisher z crisis amplification. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "dcc_parameters",
        "source": "tables",
        "label": "Dcc parameters",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted dcc parameters. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "dcc_midas_parameters",
        "source": "tables",
        "label": "Dcc midas parameters",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted dcc midas parameters. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "minimum_variance_portfolio",
        "source": "tables",
        "label": "Minimum variance portfolio",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted minimum variance portfolio. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "portfolio_comparison",
        "source": "tables",
        "label": "Portfolio comparison",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted portfolio comparison. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
    {
        "key": "diversification_ratio",
        "source": "tables",
        "label": "Diversification ratio",
        "render": "table",
        "primary": False,
        "help": "Actual observed or fitted diversification ratio. No complete observations for this conditional output; consult data gaps and estimator metadata.",
        "empty_reason": "No complete observations for this conditional output; consult data gaps and estimator metadata.",
    },
]
