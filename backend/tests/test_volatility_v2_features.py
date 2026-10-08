"""Authoritative declarations, strict controls and feature envelope regressions."""

import ast
from pathlib import Path

import pytest
from app.services.volatility_v2.registry import (
    contract_for,
    feature_manifest,
    prepare_payload,
)


def test_all_actual_response_outputs_are_declared():
    root = Path(__file__).parents[1] / "app/services/volatility_v2/features"
    for contract in feature_manifest():
        keys = [field["key"] for field in contract["inputs"]]
        assert len(keys) == len(set(keys))
        assert all(
            {"label", "type", "group", "default", "help"} <= set(field)
            for field in contract["inputs"]
        )
        declared = {(output["source"], output["key"]) for output in contract["outputs"]}
        assert declared
        tree = ast.parse((root / f"feature_{contract['id']}.py").read_text())
        actual = set()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "response"
            ):
                for keyword in node.keywords:
                    if keyword.arg in {"charts", "tables"} and isinstance(
                        keyword.value, ast.Dict
                    ):
                        actual.update(
                            (keyword.arg, key.value)
                            for key in keyword.value.keys
                            if isinstance(key, ast.Constant)
                        )
        assert actual == declared
        assert all(
            output["render"]
            in {
                "line",
                "heatmap",
                "table",
                "bar",
                "cards",
                "network",
                "network_history",
                "waterfall",
                "histogram",
                "gauge",
                "band",
                "stacked_area",
            }
            for output in contract["outputs"]
        )


def test_strict_controls_reject_ignored_flags_and_invalid_values():
    for payload in [
        {"rolling_window": 0},
        {"rolling_window": 2.5},
        {"include_hourly_variation": "maybe"},
        {"annualization": float("nan")},
        {"made_up": 1},
    ]:
        with pytest.raises((ValueError, TypeError)):
            prepare_payload("01", payload)
    assert prepare_payload(
        "09",
        {
            "gross_exposure_cap": "1.5",
            "cash_rate_annual": ".02",
            "breach_threshold": ".15",
        },
    ) == {"gross_exposure_cap": 1.5, "cash_rate_annual": 0.02, "breach_threshold": 0.15}
    assert prepare_payload(
        "03", {"forecast_horizons": "1,5", "volatility_estimator": "cc"}
    ) == {"horizons": [1, 5], "estimator": "cc"}
    with pytest.raises(ValueError, match="Conflicting"):
        prepare_payload("01", {"rolling_window": 21, "window_days": 42})
    copied = contract_for("01")
    copied["inputs"].clear()
    assert contract_for("01")["inputs"]


def test_full_history_vrp_and_new_model_controls_are_accessible():
    assert (
        prepare_payload("05", {"zscore_lookback": "full"})["zscore_lookback"] == "full"
    )
    assert prepare_payload("05", {"zscore_lookback": "2520"})["zscore_lookback"] == 2520
    assert (
        prepare_payload(
            "02",
            {
                "return_frequency": "weekly",
                "aparch_delta": 1.5,
                "mcs_confidence": 0.95,
                "bootstrap_reps": 100,
            },
        )["aparch_delta"]
        == 1.5
    )
    for feature, payload in [
        ("06", {"ew_delta": 1}),
        ("02", {"aparch_delta": 4}),
        ("03", {"mcs_loss": "invented"}),
        ("05", {"zscore_lookback": True}),
    ]:
        with pytest.raises(ValueError):
            prepare_payload(feature, payload)


@pytest.mark.parametrize("feature_id", [f"{number:02}" for number in range(1, 10)])
def test_every_feature_executes_and_returns_declared_outputs(monkeypatch, feature_id):
    """Run actual estimators on an explicit synthetic test fixture, never demo output."""
    import importlib
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(183)
    dates = pd.bdate_range("2023-01-02", periods=650)
    frames = []
    assets = ["SPY", "QQQ", "IWM"]
    shared = rng.normal(0, 0.008, len(dates))
    for asset in assets:
        close = 100 * np.exp(np.cumsum(shared + rng.normal(0, 0.007, len(dates))))
        opening = close * np.exp(rng.normal(0, 0.003, len(dates)))
        frames.append(
            pd.DataFrame(
                {
                    "Ticker": asset,
                    "Date": dates,
                    "Open": opening,
                    "High": np.maximum(opening, close)
                    * np.exp(rng.uniform(0.003, 0.02, len(dates))),
                    "Low": np.minimum(opening, close)
                    * np.exp(-rng.uniform(0.003, 0.02, len(dates))),
                    "Close": close,
                    "Volume": 1e6,
                }
            )
        )
    observed = pd.concat(frames, ignore_index=True)
    module = importlib.import_module(
        f"app.services.volatility_v2.features.feature_{feature_id}"
    )
    monkeypatch.setattr(
        module, "load_assets", lambda *args, **kwargs: (assets, observed.copy())
    )
    from app.services.volatility_v2.core import vrp

    implied = pd.DataFrame(
        {30: 0.2 + 0.015 * np.sin(np.arange(650) / 30), 90: 0.21, 180: 0.22},
        index=dates,
    )
    monkeypatch.setattr(
        vrp, "observed_iv", lambda *args: (implied.copy(), "explicit test IV fixture")
    )
    # Feature 05 imports the primitive into its own module namespace.
    if hasattr(module, "observed_iv"):
        monkeypatch.setattr(module, "observed_iv", vrp.observed_iv)
    options = {
        "01": {},
        "02": {
            "models": ["GARCH"],
            "distributions": ["Gaussian"],
            "evaluation_days": 60,
            "horizons": [1, 5],
            "simulations": 100,
        },
        "03": {
            "models": ["HAR", "LHAR", "A-ACSV-HAR"],
            "horizons": [1, 5],
            "bootstrap_reps": 30,
        },
        "04": {"states": 2, "hmm_restarts": 1, "refit_interval": 252},
        "05": {"return_horizons": [21], "refit_interval": 126},
        "06": {
            "rolling_window": 126,
            "rolling_interval": 63,
            "max_lag": 1,
            "irf_bootstrap_reps": 20,
        },
        "07": {"refit_interval": 252},
        "08": {"mc_paths": 1000, "irf_bootstrap_reps": 20},
        "09": {
            "forecast_source": "ewma",
            "include_regime_comparison": False,
            "include_kelly": False,
        },
    }
    baseline_calls = []
    if feature_id == "09":
        original_simulate = module.simulate

        def monitored_simulate(*args, **kwargs):
            if "target" not in kwargs:
                baseline_calls.append(kwargs.copy())
            return original_simulate(*args, **kwargs)

        monkeypatch.setattr(module, "simulate", monitored_simulate)
        options["09"].update(
            cost_model="almgren_chriss_temporary",
            volume_units={a: "shares" for a in assets},
            quote_currencies={a: "USD" for a in assets},
        )
    result = module.run({"min_train": 120, **options[feature_id]})
    if feature_id == "09":
        assert len(baseline_calls) == 2
        assert all(
            call["impact_gamma"] == 0.1 and call["adv"] is not None
            for call in baseline_calls
        )
    assert result["status"] in {"ok", "warning"}
    assert result["summary_cards"]
    assert len(result["output_status"]) == len(module.OUTPUTS)
    assert all(
        row["reason"]
        for row in result["output_status"]
        if row["status"] == "not_produced"
    )
    for definition in module.OUTPUTS:
        assert definition["key"] in result[definition["source"]]
