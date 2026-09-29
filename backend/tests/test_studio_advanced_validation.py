import numpy as np
import pytest

from app.services.studio.advanced_validation import (
    AdvancedValidationError,
    data_substitution_sensitivity,
    implementation_feasibility,
    parameter_instability,
    sharpe_evidence,
)


def test_probabilistic_and_deflated_sharpe_have_formula_and_trial_penalty() -> None:
    returns = [0.002, -0.001, 0.003, 0.0005, -0.0004] * 30
    single = sharpe_evidence(returns, trials=1)
    searched = sharpe_evidence(returns, trials=100)
    assert 0 <= searched["deflated_sharpe_probability"] <= 1
    assert searched["deflated_sharpe_probability"] < single["deflated_sharpe_probability"]
    assert searched["selection_bias"]["expected_max_null_annualized_sharpe"] > 0
    assert "Bailey" in searched["formulas"]["probabilistic_sharpe"]


def test_sharpe_fixture_matches_direct_psr_calculation() -> None:
    values = np.asarray([0.01, -0.004, 0.006, 0.003, -0.002] * 20)
    result = sharpe_evidence(values.tolist(), trials=1, periods_per_year=12, benchmark_sharpe=0)
    period_sr = values.mean() / values.std(ddof=1)
    variance = 1 - result["sample_skewness"] * period_sr + ((result["sample_kurtosis_pearson"] - 1) / 4) * period_sr**2
    expected = 0.5 * (1 + pytest.importorskip("scipy.special").erf(period_sr / np.sqrt(variance / (len(values) - 1)) / np.sqrt(2)))
    assert result["probabilistic_sharpe_probability"] == pytest.approx(expected)


def test_parameter_instability_reports_dispersion_and_sign_flip() -> None:
    result = parameter_instability([
        {"label": "low", "returns": [0.01, -0.002] * 10},
        {"label": "high", "returns": [-0.01, 0.002] * 10},
    ])
    assert result["diagnostics"]["sign_flip"] is True
    assert result["diagnostics"]["sharpe_range"] > 0


def test_feasibility_uses_only_supplied_market_inputs_and_lists_omissions() -> None:
    result = implementation_feasibility([
        {"asset": "SPY", "side": "buy", "notional": 200_000, "average_daily_dollar_volume": 1_000_000, "daily_volatility": 0.02, "spread_bps": 1.5},
        {"asset": "SMALL", "side": "short", "notional": 10_000},
    ], participation_limit=0.1, portfolio_value=1_000_000, holding_days=5)
    assert result["trades"][0]["capacity_breach"] is True
    assert result["trades"][0]["estimated_impact_bps"] == pytest.approx(0.02 * np.sqrt(0.2) * 10_000)
    assert any("borrow" in item for item in result["skipped_tests"])
    assert result["trades"][1]["estimated_impact_bps"] is None
    assert result["summary"]["one_way_turnover"] == pytest.approx(0.21)


def test_source_substitution_requires_exact_alignment() -> None:
    primary = [0.01, -0.005, 0.002] * 10
    result = data_substitution_sensitivity(primary, {"vendor_b": [value + 0.0001 for value in primary]})
    assert result["alternatives"][0]["mean_absolute_return_delta"] == pytest.approx(0.0001)
    with pytest.raises(AdvancedValidationError, match="align"):
        data_substitution_sensitivity(primary, {"short": primary[:-1]})
