"""Direct smoke runner for Research V2.

Run from the repository root:

    python3 backend/app/services/research_v2/smoke_test.py
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.research_v2.registry import FEATURES, run_feature  # noqa: E402


def main() -> None:
    payload = {
        "universe": "master",
        "max_symbols": 40,
        "lookback_days": 500,
        "max_specifications": 6,
        "permutation_replications": 8,
        "bootstrap_replications": 20,
        "donor_limit": 8,
        "controls": "size,value",
        "weighting": "rank",
    }
    for feature_id in FEATURES:
        result = run_feature(feature_id, payload)
        assert result["status"] == "ok", feature_id
        assert result["feature_id"] == feature_id, feature_id
        assert "summary_cards" in result, feature_id
        assert "charts" in result, feature_id
        assert "tables" in result, feature_id
        print(feature_id, "ok", len(result["charts"]), len(result["tables"]))


if __name__ == "__main__":
    main()
