"""Append-only data fetch helpers for Portfolio V2.

This module is intentionally not imported by runtime feature code. It documents
and prepares the missing external datasets needed for the few outputs that
cannot be fully computed from local parquet files.

Run manually only after setting the required provider keys / data sources.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = ROOT / "backend" / "data" / "portfolio_v2"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def append_parquet(path: Path, rows: pd.DataFrame, subset: Iterable[str] | None = None) -> None:
    """Append rows to a parquet file without overwriting existing records."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, rows], ignore_index=True)
    else:
        combined = rows.copy()
    if subset:
        combined = combined.drop_duplicates(list(subset), keep="last")
    combined.to_parquet(path, index=False)


def required_missing_datasets() -> list[dict[str, str]]:
    """Datasets needed for the remaining non-live outputs."""

    return [
        {
            "dataset": "point_in_time_constituents",
            "target": str(DATA_DIR / "point_in_time_constituents.parquet"),
            "needed_for": "F02 survivorship-bias corrected backtest and historical membership audit",
            "source_hint": "Index provider archive, CRSP/Compustat, Norgate, or internally licensed membership history",
        },
        {
            "dataset": "factor_etf_aum_history",
            "target": str(DATA_DIR / "factor_etf_aum_history.parquet"),
            "needed_for": "F09 ETF AUM crowding regime indicator",
            "source_hint": "ETF issuer files, ETF.com, Bloomberg, or fund sponsor CSVs",
        },
        {
            "dataset": "peer_fund_holdings",
            "target": str(DATA_DIR / "peer_fund_holdings.parquet"),
            "needed_for": "F12 true overlap network and DebtRank against actual funds",
            "source_hint": "13F/EDGAR parsed filings or user-uploaded peer books",
        },
        {
            "dataset": "strategy_position_books",
            "target": str(DATA_DIR / "strategy_position_books.parquet"),
            "needed_for": "F13 inter-strategy turnover netting and capacity-constrained redeployment",
            "source_hint": "Internal strategy-level holdings/export files",
        },
    ]


if __name__ == "__main__":
    print(pd.DataFrame(required_missing_datasets()).to_string(index=False))
