"""Observed-VIX crisis conditioning and causal HMM probability weighting."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm
from .analytics import macro_frame
from .dcc import correlation
from .regimes import filtered_regimes, regime_features, state_names


def weighted_correlation(returns, weights):
    aligned = returns.join(weights.rename("probability"), how="inner").dropna()
    vector = aligned.pop("probability").to_numpy(dtype=float)
    values = aligned.to_numpy(dtype=float)
    if (
        len(values) < 30
        or not np.isfinite(vector).all()
        or (vector < 0).any()
        or vector.sum() <= 0
    ):
        raise ValueError(
            "Weighted crisis correlation requires 30 aligned observations and positive probability mass"
        )
    normalized = vector / vector.sum()
    centered = values - normalized @ values
    covariance = (centered * normalized[:, None]).T @ centered
    result = pd.DataFrame(
        correlation(covariance), index=returns.columns, columns=returns.columns
    )
    return result, {
        "observations": len(values),
        "probability_mass": float(vector.sum()),
        "effective_sample_size": float(1 / (normalized @ normalized)),
        "centering": "probability-weighted mean",
    }


def crisis_correlations(returns, ohlcv, payload):
    threshold = float(payload.get("crisis_vix_threshold", 30))
    history = int(payload.get("crisis_percentile_window", 2520))
    minimum = int(payload.get("crisis_percentile_min_history", 252))
    if threshold <= 0 or not 21 <= minimum <= history:
        raise ValueError("Invalid crisis threshold or percentile history")
    vol = returns.rolling(21, min_periods=21).std(ddof=1)
    ranks = vol.rolling(history, min_periods=minimum).rank(pct=True)
    vix = macro_frame().set_index("date")["vix"].reindex(returns.index)
    eligible = vix.notna() & ranks.notna().all(axis=1)
    crisis_mask = eligible & vix.gt(threshold) & ranks.gt(0.9).any(axis=1)
    normal_mask = eligible & ~crisis_mask
    crisis, normal = returns.loc[crisis_mask], returns.loc[normal_mask]
    output = {
        "hard_rule": {
            "vix_threshold": threshold,
            "percentile_threshold": 0.9,
            "percentile_window": history,
            "minimum_percentile_history": minimum,
            "excluded_unobserved_dates": int((~eligible).sum()),
            "crisis_observations": len(crisis),
            "normal_observations": len(normal),
        },
        "normal": None,
        "crisis": None,
        "delta": None,
        "fisher_tests": [],
        "probability_weighted": None,
        "warnings": [],
    }
    if len(crisis) >= 10 and len(normal) >= 10:
        output["normal"], output["crisis"] = normal.corr(), crisis.corr()
        output["delta"] = output["crisis"] - output["normal"]
        pairs = len(returns.columns) * (len(returns.columns) - 1) // 2
        for i, left in enumerate(returns.columns):
            for right in returns.columns[i + 1 :]:
                first, second = (
                    output["crisis"].loc[left, right],
                    output["normal"].loc[left, right],
                )
                if (
                    not np.isfinite(first + second)
                    or abs(first) >= 1
                    or abs(second) >= 1
                ):
                    output["fisher_tests"].append(
                        {
                            "asset_1": left,
                            "asset_2": right,
                            "status": "unavailable",
                            "reason": "Degenerate conditional correlation",
                        }
                    )
                    continue
                statistic = (np.arctanh(first) - np.arctanh(second)) / np.sqrt(
                    1 / (len(crisis) - 3) + 1 / (len(normal) - 3)
                )
                pvalue = float(2 * norm.sf(abs(statistic)))
                output["fisher_tests"].append(
                    {
                        "asset_1": left,
                        "asset_2": right,
                        "z_statistic": float(statistic),
                        "p_value": pvalue,
                        "bonferroni_p_value": min(1, pvalue * pairs),
                        "crisis_observations": len(crisis),
                        "normal_observations": len(normal),
                        "inference": "IID Fisher approximation; serial dependence is not corrected",
                    }
                )
    else:
        output["warnings"].append(
            "Hard-rule crisis comparison unavailable: each group requires 10 observed returns"
        )
    asset = payload.get("regime_asset", returns.columns[0])
    if asset not in returns.columns:
        raise ValueError("regime_asset must be a requested portfolio asset")
    try:
        fitted = filtered_regimes(
            regime_features(ohlcv, asset),
            states=int(payload.get("states", 4)),
            min_train=int(payload.get("regime_min_train", 252)),
            refit_interval=int(payload.get("regime_refit_interval", 126)),
            restarts=int(payload.get("hmm_restarts", 3)),
        )
        names = state_names(fitted["selected_states"])
        high = [name for name in names if name in ("high_vol", "crisis")]
        probabilities = fitted["probabilities"]
        # Nonconverged fits remain visible in Feature 04, but cannot supply a risk estimate here.
        weights = probabilities[high].sum(axis=1).where(probabilities.hmm_converged)
        output["probability_weighted"], output["probability_weighting"] = (
            weighted_correlation(returns, weights)
        )
        output["probability_weighting"].update(
            {
                "regime_asset": asset,
                "states": high,
                "model": "Feature 04 causal filtered HMM",
                "nonconverged_dates_excluded": int(
                    (~probabilities.hmm_converged).sum()
                ),
            }
        )
    except (ValueError, np.linalg.LinAlgError) as exc:
        output["warnings"].append(
            f"Probability-weighted crisis correlation unavailable: {exc}"
        )
    return output
