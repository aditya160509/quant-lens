"""Shared bounded execution for synchronous and durable robustness runs."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .data_source_test import DataSourceRobustnessTest
from .extended import ExtendedRobustnessRunner
from .parameter_interaction import ParameterInteractionTest
from .tests import TimingPerturbationTest


def run_core_diagnostics(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, float]]:
    """Run the existing bounded core diagnostics without HTTP or persistence concerns."""

    outputs: dict[str, Any] = {}
    if payload.get("prices") is not None and payload.get("strategy_source") is not None:
        outputs["data_source"] = DataSourceRobustnessTest().perturb_strategy(
            payload["prices"],
            payload["strategy_source"],
            payload.get("strategy_parameters"),
            payload.get("noise_std", 0.001),
            payload.get("n_simulations", 200),
            payload.get("seed", 42),
        )
    elif payload.get("returns") is not None:
        noise_std = payload.get("noise_std")
        if noise_std is None and payload.get("noise_bps") is not None:
            noise_std = float(payload["noise_bps"]) / 10_000.0
        outputs["data_source"] = DataSourceRobustnessTest().perturb(
            payload["returns"],
            0.001 if noise_std is None else noise_std,
            payload.get("n_simulations", 200),
            payload.get("seed", 42),
        )

    if payload.get("sources"):
        outputs["data_source"] = DataSourceRobustnessTest().run(
            payload["sources"], payload.get("tolerance_bps", 10)
        )

    if payload.get("parameter_grid"):
        outputs["parameter_interaction"] = ParameterInteractionTest().run(
            payload["parameter_grid"], observations=payload.get("observations")
        )
    elif payload.get("parameter_ranges") and payload.get("observations"):
        interaction = ParameterInteractionTest()
        outputs["parameter_interaction"] = interaction.run(
            interaction.auto_grid(payload["parameter_ranges"], 11),
            observations=payload["observations"],
        )
    elif payload.get("parameter_ranges") and payload.get("backtest_config"):
        outputs["parameter_interaction"] = ParameterInteractionTest().run_backtests(
            payload["parameter_ranges"], payload["backtest_config"]
        )

    if payload.get("trade_log"):
        outputs["timing"] = TimingPerturbationTest().run(
            pd.DataFrame(payload["trade_log"]), payload.get("n_simulations", 1000)
        )

    if not outputs:
        raise ValueError("provide sources, parameter_grid/observations, or trade_log")

    components: dict[str, float] = {}
    timing = outputs.get("timing")
    if timing is not None:
        components["timing"] = float(
            np.clip(getattr(timing, "sensitivity_score", 0.0), 0.0, 1.0)
        )
    interaction = outputs.get("parameter_interaction", {})
    if isinstance(interaction, dict) and interaction.get("marginal_stability"):
        components["parameter_stability"] = float(
            np.mean(list(interaction["marginal_stability"].values()))
        )
    return outputs, components


def run_extended_diagnostic(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float]]:
    """Run one existing bounded extended diagnostic."""

    return ExtendedRobustnessRunner().run(payload)

