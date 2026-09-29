"""Empirical execution-quality audit against historical bars."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from ..shared.data_loader import get_ohlcv
from .repository import BacktestResultRepository


class SlippageAuditor:
    def __init__(self, results: Optional[BacktestResultRepository] = None) -> None:
        self.results = results or BacktestResultRepository()

    @staticmethod
    def _reference_fill(row: pd.Series, direction: float) -> tuple[float, float, str]:
        if {"bid", "ask"}.issubset(row.index) and np.isfinite(row["bid"]) and np.isfinite(row["ask"]):
            spread = max(0.0, float(row["ask"]) - float(row["bid"]))
            midpoint = (float(row["ask"]) + float(row["bid"])) / 2.0
            return midpoint + np.sign(direction) * spread * 0.25, spread, "quoted_bid_ask"
        typical = float(row.get("vwap", np.nan))
        if not np.isfinite(typical):
            typical = float(np.nanmean([row.get("high", np.nan), row.get("low", np.nan), row.get("close", np.nan)]))
        spread_proxy = max(0.0, float(row.get("high", typical)) - float(row.get("low", typical))) * 0.10
        return typical + np.sign(direction) * spread_proxy * 0.25, spread_proxy, "bar_range_proxy"

    def audit(self, run_id: str) -> dict[str, Any]:
        result = self.results.get_result(run_id)
        trades = pd.DataFrame(result.get("trade_log", []))
        if trades.empty:
            raise ValueError(f"run '{run_id}' contains no trades")
        per_trade: list[dict[str, Any]] = []
        total_modeled = 0.0
        total_realistic = 0.0
        for index, trade in trades.iterrows():
            ticker = str(trade["ticker"]).upper()
            date = pd.Timestamp(trade.get("fill_date", trade.get("date"))).normalize()
            history = get_ohlcv(ticker, date - pd.Timedelta(days=7), date + pd.Timedelta(days=2))
            history = pd.DataFrame(history)
            history["date"] = pd.to_datetime(history["date"]).dt.normalize()
            rows = history.loc[history["date"] == date]
            if rows.empty:
                continue
            direction = np.sign(float(trade.get("quantity", 0.0)))
            modeled_fill = float(trade["price"])
            realistic_fill, spread, methodology = self._reference_fill(rows.iloc[0], direction)
            notional = abs(float(trade.get("quantity", 0.0)) * realistic_fill)
            modeled_reference = float(rows.iloc[0].get("open", rows.iloc[0].get("close", realistic_fill)))
            modeled_cost = abs(modeled_fill - modeled_reference) * abs(float(trade.get("quantity", 0.0)))
            realistic_cost = abs(realistic_fill - modeled_reference) * abs(float(trade.get("quantity", 0.0)))
            total_modeled += modeled_cost
            total_realistic += realistic_cost
            per_trade.append(
                {
                    "trade_id": str(trade.get("trade_id", f"T-{index:06d}")),
                    "ticker": ticker,
                    "date": date.date().isoformat(),
                    "direction": int(direction),
                    "size": abs(float(trade.get("quantity", 0.0))),
                    "modeled_fill": modeled_fill,
                    "realistic_fill": realistic_fill,
                    "slippage_bps": ((modeled_fill - realistic_fill) / realistic_fill * 10_000.0 * direction) if realistic_fill else 0.0,
                    "spread": spread,
                    "reference_method": methodology,
                    "notional": notional,
                }
            )
        if not per_trade:
            raise ValueError("no historical reference bars were available for the run trades")
        bias = total_realistic - total_modeled
        ratio = total_modeled / total_realistic if total_realistic > 0 else 1.0
        verdict = "overoptimistic" if ratio < 0.70 else "slightly_optimistic" if ratio < 0.90 else "realistic"
        return {
            "per_trade": per_trade,
            "aggregate": {
                "total_trades": len(per_trade),
                "avg_slippage_bps": float(np.mean([row["slippage_bps"] for row in per_trade])),
                "total_modeled_cost": total_modeled,
                "total_realistic_cost": total_realistic,
                "optimistic_bias": bias,
                "modeled_to_realistic_ratio": ratio,
                "verdict": verdict,
            },
        }
