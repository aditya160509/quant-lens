import json
import subprocess

import pandas as pd
import pytest

from app.services.studio.execution import (
    DockerExecutionProvider,
    ExecutionUnavailableError,
    StrategyExecutionError,
    StrategyPolicyError,
    validate_strategy_source,
)
from app.routers.studio import StrategyExecutor, _metadata


VALID_CODE = """
class Strategy:
    def generate_signals(self, data):
        return [{'idx': 1, 'dir': 1}]
strategy = Strategy()
"""


def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": [100.0, 101.0], "High": [101.0, 102.0], "Low": [99.0, 100.0]},
        index=pd.date_range("2025-01-01", periods=2),
    )


def test_market_run_metadata_names_the_governed_dataset() -> None:
    metadata = _metadata(frame(), engine_version="test", parameters={"ticker": "SPY"})

    assert metadata["data_quality"]["source"] == "market_universe_daily"
    assert metadata["provenance"]["dataset_id"] == "market_universe_daily"


@pytest.mark.parametrize(
    "code, message",
    [
        ("import os\nclass Strategy: pass", "Imports are disabled"),
        ("class Strategy:\n x = open('/etc/passwd')", "not allowed"),
        ("class Strategy:\n x = object.__subclasses__()", "not allowed"),
        ("strategy = object()", "must define class Strategy"),
    ],
)
def test_policy_rejects_escape_surfaces(code: str, message: str) -> None:
    with pytest.raises(StrategyPolicyError, match=message):
        validate_strategy_source(code)


def test_docker_provider_uses_required_isolation_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"signals": [{"idx": 1, "dir": 1}]}), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = DockerExecutionProvider().execute(VALID_CODE, frame())

    command = observed["command"]
    assert result == [{"idx": 1, "dir": 1}]
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--name") + 1].startswith("quant360-studio-")
    assert "--read-only" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--user") + 1] == "65534:65534"
    assert observed["kwargs"]["timeout"] == 15
    assert observed["kwargs"]["env"] == {"PATH": observed["kwargs"]["env"]["PATH"]}


def test_provider_fails_closed_when_container_runtime_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 125, stdout="", stderr="daemon unavailable"),
    )
    with pytest.raises(ExecutionUnavailableError, match="unavailable"):
        DockerExecutionProvider().execute(VALID_CODE, frame())


def test_provider_reports_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def timeout(*args, **kwargs):
        calls.append(args[0])
        if args[0][1] == "run":
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(StrategyExecutionError, match="time limit"):
        DockerExecutionProvider().execute(VALID_CODE, frame())
    assert calls[1][:3] == ["docker", "rm", "--force"]


def test_strategy_result_reconciles_net_gross_cost_and_turnover_series() -> None:
    prices = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 110.0],
            "High": [101.0, 101.0, 111.0],
            "Low": [99.0, 99.0, 109.0],
            "Close": [100.0, 100.0, 110.0],
            "Volume": [1000, 1000, 1000],
        },
        index=pd.date_range("2025-01-01", periods=3),
    )
    executor = StrategyExecutor(
        universe="TEST",
        lookback_years=1,
        end_date="2025-01-03",
        slippage_bps=10,
        commission_pct=0.1,
    )

    result = executor._process_strategy_results(prices, [{"idx": 1, "dir": 1}])

    assert result["series"]["turnover"] == [0.0, 1.0, 0.0]
    assert result["series"]["costs"] == pytest.approx([0.0, 0.002, 0.0])
    assert result["series"]["equity_gross"][-1] == pytest.approx(1.1)
    assert result["series"]["equity_net"][-1] == pytest.approx(1.0978)
    assert result["metrics"]["canonical"]["cost_drag"]["value"] == pytest.approx(0.0022)
    assert result["metrics"]["canonical"]["turnover"]["value"] == pytest.approx(0.5)
