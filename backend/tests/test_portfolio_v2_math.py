"""Independent golden numbers for Portfolio V2 estimators and constraint enforcement."""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm
from app.services.portfolio_v2.core.context import parse_weights
from app.services.portfolio_v2.core.construction import (
    solve_portfolio,
    OptimizationError,
    black_litterman,
    optimize_portfolios,
)
from app.services.portfolio_v2.core.allocation import kelly_sizing
from app.services.portfolio_v2.core.stats import (
    performance_metrics,
    probabilistic_sharpe,
    min_track_record_length,
    pbo_cscv,
)
from app.services.portfolio_v2.core.attribution import brinson_fachler, linked_effects
from app.services.portfolio_v2.core.stress import minimum_mahalanobis_reverse_stress
from app.services.portfolio_v2.core.execution import optimal_schedule
from app.services.portfolio_v2.core.systemic import (
    portfolio_overlap_index,
    debtrank_propagate,
)
from app.services.portfolio_v2.features.feature_08 import risk_entropy
from app.services.portfolio_v2.core.performance import (
    dataframe_fingerprint,
    fast_network_edges_from_corr,
)


def sample():
    return pd.DataFrame(
        np.random.default_rng(41).normal(
            [0.0004, 0.0003, 0.0002], [0.01, 0.02, 0.03], (300, 3)
        ),
        columns=["A", "B", "C"],
        index=pd.bdate_range("2020-01-01", periods=300),
    )


def test_signed_weights_preserved():
    w = parse_weights({"weights": {"A": 1.3, "B": -0.3}}, ["A", "B"])
    assert list(w) == [1.3, -0.3]
    assert list(parse_weights({"weights": {"A": 0.5, "B": -0.5}}, ["A", "B"])) == [
        0.5,
        -0.5,
    ]


@pytest.mark.parametrize("raw", [{"D": 1}, {"A": float("nan")}, "A:1,A:2", []])
def test_invalid_weights_rejected(raw):
    with pytest.raises(ValueError):
        parse_weights({"weights": raw}, ["A", "B"])


def test_gmv_closed_form():
    r = sample()
    cov = r.cov().to_numpy()
    inv = np.linalg.inv(cov)
    expected = inv @ np.ones(3)
    expected /= expected.sum()
    w, _ = solve_portfolio(r, {"covariance_estimator": "sample"}, "global_min_variance")
    assert w.to_numpy() == pytest.approx(expected, abs=2e-5)


def test_risk_parity_equal_contributions():
    r = sample()
    w, _ = solve_portfolio(r, {"covariance_estimator": "sample"}, "risk_parity")
    contribution = w * (r.cov() @ w)
    assert (contribution / contribution.sum()).to_numpy() == pytest.approx(
        np.full(3, 1 / 3), abs=2e-5
    )


def test_optimizer_failure_never_equal_weights():
    with pytest.raises(OptimizationError, match="infeasible"):
        solve_portfolio(sample(), {"max_weights": 0.2})


def test_frontier_targets_feasible():
    result = optimize_portfolios(
        sample(), {"covariance_estimator": "sample", "frontier_points": 4}
    )
    mu = result["mu"]
    gmv = float(result["weights"]["global_min_variance"] @ mu)
    assert all(p["target_return"] >= gmv - 1e-10 for p in result["frontier"])
    assert all(p["success"] for p in result["frontier"])
    assert all(
        p["return"] == pytest.approx(p["target_return"], abs=1e-5)
        for p in result["frontier"]
    )


def test_sector_and_turnover_constraints_bind():
    r = sample()
    w, d = solve_portfolio(
        r,
        {
            "sector_map": {"A": "tech", "B": "other", "C": "other"},
            "sector_max_weights": {"tech": 0.1},
            "current_weights": {"A": 0.1, "B": 0.45, "C": 0.45},
            "max_turnover": 0.1,
        },
        "global_min_variance",
    )
    assert w.A <= 0.10001
    assert (w - pd.Series({"A": 0.1, "B": 0.45, "C": 0.45})).abs().sum() / 2 <= 0.10001
    assert not any(row["status"] == "violated" for row in d["constraints"])


def test_130_30_structure():
    w, _ = solve_portfolio(
        sample(),
        {"position_structure": "130_30", "short_symbols": ["C"], "leverage_cap": 1.6},
        "global_min_variance",
    )
    assert w.sum() == pytest.approx(1)
    assert w[w > 0].sum() == pytest.approx(1.3)
    assert w[w < 0].sum() == pytest.approx(-0.3)


def test_bl_one_view_closed_form():
    cov = pd.DataFrame([[0.04]], index=["A"], columns=["A"])
    result = black_litterman(
        cov, pd.Series({"A": 1}), {"A": 0.2}, tau=0.05, risk_aversion=2.5
    )
    assert result["posterior_mu"].A == pytest.approx(0.15)
    assert result["posterior_cov"].iloc[0, 0] == pytest.approx(0.041)


def test_kelly_fraction_before_cap():
    mu = pd.Series({"A": 0.2})
    cov = pd.DataFrame([[0.04]], index=["A"], columns=["A"])
    rows = kelly_sizing(mu, cov, fraction=0.5, leverage_cap=1)["table"]
    assert rows[0]["kelly_weight"] == pytest.approx(5, rel=1e-6)
    assert rows[0]["constrained_weight"] == pytest.approx(1)


def test_simple_return_metrics_and_initial_drawdown():
    r = pd.Series([-0.1, 0.1])
    m = performance_metrics(r, 2)
    assert m["cagr"] == pytest.approx(-0.01)
    assert m["max_drawdown"] == pytest.approx(-0.1)
    assert m["sortino"] == pytest.approx(0)


def test_psr_period_units_and_track_record():
    sr = 0.1
    T = 100
    assert probabilistic_sharpe(sr, T) == pytest.approx(
        norm.cdf(sr * np.sqrt(T - 1) / np.sqrt(1 + sr**2 / 2))
    )
    assert min_track_record_length(sr) == pytest.approx(
        1 + (1 + 0.5 * sr**2) * (norm.ppf(0.95) / sr) ** 2
    )


def test_brinson_identity_and_linking():
    r = sample().iloc[:15]
    wp = pd.Series({"A": 0.6, "B": 0.3, "C": 0.1})
    wb = pd.Series(1 / 3, index=r.columns)
    groups = {"A": "x", "B": "x", "C": "y"}
    rows = brinson_fachler(r, wp, wb, groups)
    assert sum(
        row[k] for row in rows for k in ["allocation", "selection", "interaction"]
    ) == pytest.approx(float((r @ wp - r @ wb).mean()))
    effects = pd.DataFrame(
        {
            "asset_a": r.A * (wp.A - wb.A),
            "asset_b": r.B * (wp.B - wb.B),
            "asset_c": r.C * (wp.C - wb.C),
        }
    )
    for method in ["carino", "menchero", "grap"]:
        linked = linked_effects(effects, r @ wp, r @ wb, method)
        assert linked.sum().sum() == pytest.approx(
            (1 + r @ wp).prod() - (1 + r @ wb).prod()
        )


def test_reverse_stress_hits_exact_target():
    r = sample()
    w = pd.Series(1 / 3, index=r.columns)
    result = minimum_mahalanobis_reverse_stress(r, w, 0.15)
    assert result["portfolio_loss"] == pytest.approx(-0.15)


def test_ac_conserves_trades_and_risk_frontier():
    low = optimal_schedule([100], np.array([[0.01]]), [0.001], 5, 0)
    high = optimal_schedule([100], np.array([[0.01]]), [0.001], 5, 0.1)
    assert low[0].sum() == pytest.approx(100)
    assert high[0].sum() == pytest.approx(100)
    assert low[0][:, 0] == pytest.approx(np.full(5, 20), abs=1e-4)
    assert high[3] < low[3]
    assert high[2] > low[2]


def test_overlap_and_directional_debtrank():
    overlap = portfolio_overlap_index(
        {"p": pd.Series({"A": 0.6, "B": 0.4}), "q": pd.Series({"A": 0.2, "B": 0.8})}
    )
    assert overlap.loc["p", "q"] == pytest.approx(0.6)
    exposure = pd.DataFrame([[0, 0], [0.5, 0]], index=["a", "b"], columns=["a", "b"])
    assert debtrank_propagate(exposure, pd.Series({"a": 0.4})).b == pytest.approx(0.2)


def test_risk_entropy_distinct_from_eigenvalue_ratio():
    r = sample()
    w = pd.Series([1, 0, 0], index=r.columns)
    value, reason = risk_entropy(r, w)
    assert value == pytest.approx(1)
    assert reason is None


def test_cache_fingerprint_checks_middle_and_all_columns():
    r = sample()
    changed = r.copy()
    changed.iloc[151, 1] *= 2
    assert dataframe_fingerprint(r) != dataframe_fingerprint(changed)


def test_network_threshold_does_not_invent_edges():
    corr = pd.DataFrame(np.eye(3), index=list("ABC"), columns=list("ABC"))
    assert fast_network_edges_from_corr(corr, 0.5) == []


def test_cscv_enumerates_all_even_half_splits():
    result = pbo_cscv(sample(), 8)
    assert result["combination_count"] == 70
    assert result["total_combinations"] == 70
    assert not result["sampled"]
    assert all(0 < r["test_percentile"] < 1 for r in result["distribution"])
    with pytest.raises(ValueError):
        pbo_cscv(sample(), 7)


def test_hrp_two_asset_closed_form():
    from app.services.portfolio_v2.core.construction import _hrp_weights

    corr = pd.DataFrame(np.eye(2), index=list("AB"), columns=list("AB"))
    assert _hrp_weights(corr, np.array([0.1, 0.2]), list("AB")) == pytest.approx(
        [0.8, 0.2]
    )


def test_cvar_optimizer_against_independent_highs_lp():
    from scipy.optimize import linprog

    r = sample()
    n, k = r.shape
    alpha = 0.95
    # Independent Rockafellar-Uryasev epigraph formulation.
    c = np.r_[np.zeros(k), 1, np.full(n, 1 / ((1 - alpha) * n))]
    matrix = np.c_[-r.to_numpy(), -np.ones(n), -np.eye(n)]
    result = linprog(
        c,
        A_ub=matrix,
        b_ub=np.zeros(n),
        A_eq=[np.r_[np.ones(k), np.zeros(n + 1)]],
        b_eq=[1],
        bounds=[(0, 1)] * k + [(None, None)] + [(0, None)] * n,
        method="highs",
    )
    assert result.success
    weights, _ = solve_portfolio(r, {"var_confidence": alpha}, "cvar_min")
    loss = -(r @ weights).to_numpy()
    eta = np.quantile(loss, alpha)
    measured = eta + np.maximum(loss - eta, 0).mean() / (1 - alpha)
    assert measured == pytest.approx(result.fun, abs=1e-7)


def test_max_sharpe_closed_form_positive_tangency():
    r = sample()
    r = r - r.mean() + np.array([0.001, 0.0015, 0.002])
    # All-positive unconstrained tangency vector matches the long-only optimum.
    tangency = np.linalg.solve(r.cov().to_numpy(), r.mean().to_numpy())
    assert (tangency > 0).all()
    tangency /= tangency.sum()
    weights, _ = solve_portfolio(
        r,
        {"covariance_estimator": "sample", "expected_return_estimator": "sample"},
        "max_sharpe",
    )
    assert weights.to_numpy() == pytest.approx(tangency, abs=2e-5)


def test_bhb_and_fachler_allocation_differ_but_both_reconcile():
    r = pd.DataFrame({"A": [0.03], "B": [0.01]})
    w = pd.Series({"A": 0.7, "B": 0.3})
    b = pd.Series({"A": 0.5, "B": 0.5})
    groups = {"A": "one", "B": "two"}
    bhb = brinson_fachler(r, w, b, groups, method="bhb")
    fachler = brinson_fachler(r, w, b, groups)
    assert bhb[0]["allocation"] != fachler[0]["allocation"]
    for rows in [bhb, fachler]:
        assert sum(
            x[c] for x in rows for c in ["allocation", "selection", "interaction"]
        ) == pytest.approx(0.004)


@pytest.mark.parametrize("urgency", ["orderly", "distressed", "crisis"])
def test_liquidation_schedule_conserves_notional_and_capacity(urgency):
    from app.services.portfolio_v2.core.liquidity import liquidation_schedule

    rows = liquidation_schedule(
        [{"ticker": "A", "position_dollars": 450, "adv_dollars": 1000}], 0.2, urgency
    )
    assert sum(x["trade_dollars"] for x in rows) == pytest.approx(450)
    assert all(x["trade_dollars"] <= 200 for x in rows)
    assert rows[-1]["remaining_dollars"] == pytest.approx(0)


def test_cache_result_isolation():
    from app.services.portfolio_v2.core.performance import cached_result

    value = cached_result("isolation", "test", lambda: {"values": [1, 2]})
    value["values"][0] = 99
    assert cached_result("isolation", "test", lambda: None) == {"values": [1, 2]}


def test_publication_mean_shift_on_matured_ic():
    from app.services.portfolio_v2.core.decay import publication_mean_shift

    r = sample()
    scores = r.shift(-1).copy()
    publication = r.index[150]
    scores.loc[publication:] *= -1
    rows = publication_mean_shift(r, scores, publication)
    assert rows[0]["status"] == "ok"
    assert rows[0]["mean_shift"] == pytest.approx(-2)
    assert rows[0]["pre_observations"] == 150
    assert rows[0]["post_observations"] == 149
