"""Corporate event calendar sourced from durable event records."""

from __future__ import annotations

from typing import Any
import hashlib
from pathlib import Path

import pandas as pd

from ..shared.persistence import SQLiteStore
from ..shared.data_loader import get_trading_sessions


class EventCalendar:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore()
        self._populated: set[str] = set()

    def upsert(self, event: dict[str, Any]) -> dict[str, Any]:
        required = {"id", "ticker", "date", "event_type"}
        missing = required.difference(event)
        if missing:
            raise ValueError(f"event missing fields: {sorted(missing)}")
        record = {**event, "ticker": str(event["ticker"]).upper(), "date": str(pd.Timestamp(event["date"]).date())}
        return self.store.put("corporate_events", str(event["id"]), record)

    @staticmethod
    def _root() -> Path:
        return Path(__file__).resolve().parents[4]

    def _fundamental_rows(self, ticker: str) -> pd.DataFrame:
        safe = str(ticker).upper().replace(".", "_").replace("-", "-")
        path = self._root() / "backend/data/fundamentals/shards" / f"{safe}_fin.parquet"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    def _known_events(self, ticker: str) -> list[dict[str, Any]]:
        symbol = str(ticker).upper()
        output: list[dict[str, Any]] = []
        fundamentals = self._fundamental_rows(symbol)
        if not fundamentals.empty:
            date_column = next((column for column in ("reportDate", "date", "asOfDate") if column in fundamentals), None)
            if date_column:
                for value in pd.to_datetime(fundamentals[date_column], errors="coerce").dropna().unique():
                    output.append({"ticker": symbol, "date": value, "event_type": "earnings",
                                   "description": "Reported fundamental period end", "source": "fundamentals_shard"})
            if date_column and "dividendYield" in fundamentals:
                rows = fundamentals[[date_column, "dividendYield"]].copy()
                rows[date_column] = pd.to_datetime(rows[date_column], errors="coerce")
                rows = rows.sort_values(date_column).dropna(subset=[date_column])
                changed = pd.to_numeric(rows["dividendYield"], errors="coerce").diff().abs().gt(1e-12)
                for _, row in rows.loc[changed].iterrows():
                    output.append({"ticker": symbol, "date": row[date_column], "event_type": "dividend",
                                   "description": "Reported dividend-yield change", "source": "fundamentals_shard"})
        # Use actual sessions in the master market-universe parquet. The
        # quarterly third-Friday rule is a schedule proxy, not an assertion
        # that a security entered or left a specific proprietary index.
        sessions = get_trading_sessions()
        if len(sessions):
            quarters = pd.date_range(sessions.min(), sessions.max(), freq="QE")
            for quarter in quarters:
                month = quarter.month
                month_sessions = sessions[(sessions.year == quarter.year) & (sessions.month == month)]
                fridays = month_sessions[month_sessions.weekday == 4]
                if len(fridays) < 3:
                    continue
                output.append({
                    "ticker": symbol,
                    "date": fridays[2],
                    "event_type": "index_rebalance",
                    "description": "Quarterly index-rebalance calendar proxy",
                    "source": "market_universe_trading_calendar",
                    "market_wide": True,
                    "is_proxy": True,
                })
        for event in output:
            identity = f"{event['ticker']}|{event['date']}|{event['event_type']}|{event['description']}"
            event["id"] = "auto_" + hashlib.sha256(identity.encode()).hexdigest()[:20]
        return output

    def populate(self, ticker: str) -> int:
        symbol = str(ticker).upper()
        if symbol in self._populated:
            return 0
        events = self._known_events(ticker)
        for event in events:
            self.upsert(event)
        self._populated.add(symbol)
        return len(events)

    def get(self, ticker: str, start: Any = None, end: Any = None,
            event_type: str | None = None) -> list[dict[str, Any]]:
        self.populate(ticker)
        rows = [row for row in self.store.list("corporate_events", limit=1000) if row["ticker"] == ticker.upper()]
        if start is not None:
            rows = [row for row in rows if pd.Timestamp(row["date"]) >= pd.Timestamp(start)]
        if end is not None:
            rows = [row for row in rows if pd.Timestamp(row["date"]) <= pd.Timestamp(end)]
        if event_type:
            rows = [row for row in rows if row["event_type"] == event_type]
        return sorted(rows, key=lambda row: row["date"])
