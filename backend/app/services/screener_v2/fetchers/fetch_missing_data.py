"""Append-only fetcher scaffolds for Screener V2.

This file does not run automatically. It documents and implements safe append
helpers for datasets the live screener can use later without overwriting the
current parquet files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[5]
SCREENER_DATA = ROOT / "backend" / "data" / "screener_v2"
PIT_FUNDAMENTALS = SCREENER_DATA / "point_in_time_fundamentals.parquet"
DELISTED_SECURITIES = SCREENER_DATA / "delisted_securities.parquet"
SAVED_SCREENS = SCREENER_DATA / "saved_screens.parquet"
ALERT_STATE = SCREENER_DATA / "alert_state.parquet"
SCREEN_RUN_HISTORY = SCREENER_DATA / "screen_run_history.parquet"


def required_missing_datasets() -> list[dict[str, Any]]:
    return [
        {
            "dataset": "point_in_time_fundamentals",
            "path": str(PIT_FUNDAMENTALS),
            "needed_for": ["S5 true PIT validation", "S4 historical academic screens", "S7 own-history valuation accuracy"],
            "available_now": PIT_FUNDAMENTALS.exists(),
            "append_key": ["ticker", "report_date", "asof_date", "field"],
        },
        {
            "dataset": "delisted_securities",
            "path": str(DELISTED_SECURITIES),
            "needed_for": ["S5 survivorship-bias corrected backtests"],
            "available_now": DELISTED_SECURITIES.exists(),
            "append_key": ["ticker", "delist_date"],
        },
        {
            "dataset": "saved_screens",
            "path": str(SAVED_SCREENS),
            "needed_for": ["S1 saved screens", "S6 watchlist monitor", "S8 export history"],
            "available_now": SAVED_SCREENS.exists(),
            "append_key": ["screen_id", "updated_at"],
        },
        {
            "dataset": "alert_state",
            "path": str(ALERT_STATE),
            "needed_for": ["S6 persistent alert feed and delivery tracking"],
            "available_now": ALERT_STATE.exists(),
            "append_key": ["alert_id", "updated_at"],
        },
        {
            "dataset": "screen_run_history",
            "path": str(SCREEN_RUN_HISTORY),
            "needed_for": ["S8 change report", "S6 alert performance tracker"],
            "available_now": SCREEN_RUN_HISTORY.exists(),
            "append_key": ["run_id", "feature_id", "created_at"],
        },
    ]


def append_parquet(path: Path, rows: list[dict[str, Any]] | pd.DataFrame, subset: list[str] | None = None) -> int:
    """Append rows to a parquet file and drop duplicates by ``subset``.

    This helper never deletes the target and never overwrites with an empty
    frame. It materializes a merged parquet only when new rows are supplied.
    """

    incoming = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if incoming.empty:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_parquet(path, engine="pyarrow")
        merged = pd.concat([existing, incoming], ignore_index=True)
    else:
        merged = incoming.copy()
    if subset:
        merged = merged.drop_duplicates(subset=subset, keep="last")
    else:
        merged = merged.drop_duplicates(keep="last")
    merged.to_parquet(path, index=False, engine="pyarrow")
    return int(len(merged))


def fetch_point_in_time_fundamentals_placeholder(*_: Any, **__: Any) -> None:
    """Operator hook for future vendor/yfinance PIT enrichment.

    The current repo has latest and historical report-date fundamentals, but not
    a clean as-of-date PIT panel. This function is intentionally inert so it is
    never mistaken for a data fetch that has already occurred.
    """

    raise NotImplementedError("Configure a PIT fundamentals source, then call append_parquet(PIT_FUNDAMENTALS, rows, subset=[...]).")


def fetch_delisted_securities_placeholder(*_: Any, **__: Any) -> None:
    raise NotImplementedError("Configure a delisting source, then append to DELISTED_SECURITIES.")
