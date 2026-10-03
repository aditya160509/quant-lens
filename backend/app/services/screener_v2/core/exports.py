"""Screener V2 exports computations."""
from __future__ import annotations
from typing import Any
import pandas as pd


def build_export_payload(feature_id: str, payload: dict[str, Any], result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    cols = list(result_rows[0].keys()) if result_rows else []
    tsv = "\t".join(cols)
    for row in result_rows:
        tsv += "\n" + "\t".join("" if row.get(c) is None else str(row.get(c)) for c in cols)
    csv_text = pd.DataFrame(result_rows).to_csv(index=False) if result_rows else ""
    tickers = [str(row.get("ticker")) for row in result_rows if row.get("ticker")]
    return {
        "feature_id": feature_id,
        "row_count": len(result_rows),
        "columns": cols,
        "tsv_preview": tsv[:5000],
        "tsv": tsv,
        "csv": csv_text,
        "ticker_list": ",".join(tickers),
        "json_payload": {"payload": payload, "rows": result_rows[:1000]},
    }

