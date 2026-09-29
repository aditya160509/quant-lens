"""Detect and report imputed, interpolated, and synthetic market-data ranges."""

from __future__ import annotations

from typing import Any
import uuid

import pandas as pd

from ..shared.data_loader import get_ohlcv
from ..shared.persistence import SQLiteStore, utc_now


class SyntheticRangeDetector:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore()
        self._ranges_cache: list[dict[str, Any]] | None = None

    def record(self, ticker: str, start: Any, end: Any, reason: str,
               method: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        start_date, end_date = pd.Timestamp(start), pd.Timestamp(end)
        if end_date < start_date:
            raise ValueError("synthetic range end must be on or after start")
        if not str(reason).strip() or not str(method).strip():
            raise ValueError("synthetic reason and method are required")
        identifier = str(uuid.uuid4())
        result = self.store.put("synthetic_ranges", identifier, {
            "id": identifier,
            "ticker": str(ticker).upper(),
            "start": str(start_date.date()),
            "end": str(end_date.date()),
            "reason": str(reason),
            "method": str(method),
            "metadata": metadata or {},
            "recorded_at": utc_now(),
        }, create_only=True)
        self._ranges_cache = None
        return result

    def get_all_ranges(self, ticker: str | None = None, limit: int = 10_000) -> list[dict[str, Any]]:
        if self._ranges_cache is None:
            self._ranges_cache = self.store.list("synthetic_ranges", limit=limit)
        rows = list(self._ranges_cache)
        if ticker:
            rows = [row for row in rows if row.get("ticker") == str(ticker).upper()]
        return sorted(rows, key=lambda row: (row.get("ticker", ""), row.get("start", "")))

    def detect(self, ticker: str, data: Any = None) -> dict[str, Any]:
        frame = pd.DataFrame(data) if data is not None else get_ohlcv(ticker)
        if frame.empty:
            explicit_ranges = self.get_all_ranges(ticker)
            return {"ticker": ticker.upper(), "ranges": explicit_ranges,
                    "synthetic_fraction": 0.0, "observations": 0,
                    "has_synthetic_data": bool(explicit_ranges)}
        if "date" in frame:
            frame = frame.set_index(pd.to_datetime(frame["date"]))
        explicit = frame.get("is_synthetic", pd.Series(False, index=frame.index)).fillna(False).astype(bool)
        close = pd.to_numeric(frame.get("close"), errors="coerce")
        repeated = close.diff().eq(0) & frame.get("volume", pd.Series(0, index=frame.index)).fillna(0).eq(0)
        interpolated = frame.get("source", pd.Series("", index=frame.index)).astype(str).str.lower().isin({"synthetic", "imputed", "interpolated", "backfilled"})
        mask = explicit | repeated | interpolated
        ranges, start, prior = [], None, None
        for timestamp, flagged in mask.items():
            if flagged and start is None:
                start = prior = timestamp
            elif flagged:
                prior = timestamp
            elif start is not None:
                ranges.append({"start": str(pd.Timestamp(start).date()), "end": str(pd.Timestamp(prior).date()), "observations": int(mask.loc[start:prior].sum())})
                start = prior = None
        if start is not None:
            ranges.append({"start": str(pd.Timestamp(start).date()), "end": str(pd.Timestamp(prior).date()), "observations": int(mask.loc[start:prior].sum())})
        explicit_ranges = self.get_all_ranges(ticker)
        combined = [*ranges, *explicit_ranges]
        return {"ticker": ticker.upper(), "ranges": combined,
                "synthetic_fraction": float(mask.mean()), "observations": int(len(mask)),
                "has_synthetic_data": bool(combined)}
