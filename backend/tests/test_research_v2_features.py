"""Every Research V2 feature runs on local data and returns every output it declares."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from app.services.research_v2.core.data_loader import UPLOAD_DIR, us_equity_symbols
from app.services.research_v2.registry import feature_manifest, run_feature

SMALL = {"max_symbols": 120, "bootstrap_replications": 100, "permutation_replications": 30, "max_specifications": 12}


@pytest.fixture(scope="module")
def event_upload() -> str:
    tickers = list(us_equity_symbols()[:12])
    dates = pd.date_range("2018-01-01", "2023-06-30", periods=12)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / "event_pytest_fixture.csv"
    pd.DataFrame({"ticker": tickers, "treatment_date": dates}).to_csv(path, index=False)
    return path.name


def _payload(fid: str, event_upload: str) -> dict:
    extra = {
        "07": {"identification_design": "all", "event_csv_path": event_upload, "running_variable": "size_rank", "cutoff": 60, "bootstrap_replications": 20},
        "08": {"signal": "reversal", "discovery_date": "2019-01-01", "international_replication": False},
        "09": {"treated_unit": "AAPL", "treatment_date": "2023-01-31", "donor_limit": 25, "max_symbols": 60},
    }
    return {**SMALL, **extra.get(fid, {})}


@pytest.mark.parametrize("fid", [f["id"] for f in feature_manifest()])
def test_feature_returns_declared_outputs(fid: str, event_upload: str) -> None:
    result = run_feature(fid, _payload(fid, event_upload))
    assert result["status"] == "ok"
    json.dumps(result)  # fully JSON-serialisable
    present = set(result["charts"]) | set(result["tables"])
    declared = next(f for f in feature_manifest() if f["id"] == fid)["outputs"]
    missing = [o["key"] for o in declared if o["key"] not in present and not o.get("conditional")]
    assert not missing, f"feature {fid} is missing declared outputs {missing}"
