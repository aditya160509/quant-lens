from __future__ import annotations

"""
Live-vs-Backtest Reconciliation Panel (F2.8).

Computes running divergence score between projected backtest returns
and actual paper trading returns. Rolling 20-day window.
"""

from dataclasses import asdict, dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd


@dataclass
class ReconciliationResult:
    backtest_equity_curve: pd.Series
    paper_trading_equity_curve: pd.Series
    divergence_scores: pd.Series
    mean_divergence: float
    reliability_decay_rate: float
    verdict: str
    num_trading_days: int

    def to_dict(self) -> dict: return asdict(self)


class Reconciliation:
    def __init__(self, backtest_returns: Optional[dict] = None, paper_trader: Any = None, lineage: Any = None, strategy_name: Optional[str] = None) -> None:
        self.backtest_returns = backtest_returns or {}; self.paper_trader = paper_trader; self.lineage = lineage; self.strategy_name = strategy_name

    def compute_running_divergence_score(self, actual: pd.Series, predicted: pd.Series, window: int = 20) -> pd.Series:
        left, right = pd.Series(actual, dtype=float), pd.Series(predicted, dtype=float); frame = pd.concat([left.rename("actual"), right.rename("predicted")], axis=1).replace([np.inf, -np.inf], np.nan).dropna();
        if frame.empty: return pd.Series(dtype=float)
        volatility = frame["predicted"].rolling(max(1, int(window)), min_periods=1).std(ddof=1).fillna(0.0).clip(lower=1e-8); return (frame["actual"] - frame["predicted"]).abs().div(volatility)

    def compute_reliability_decay_rate(self, divergence_scores: pd.Series) -> float:
        values = pd.Series(divergence_scores, dtype=float).replace([np.inf, -np.inf], np.nan).dropna();
        if len(values) < 2: return 0.0
        return float(np.polyfit(np.arange(len(values), dtype=float), values.to_numpy(), 1)[0])

    def status_verdict(self, divergence_scores: pd.Series) -> str:
        values = pd.Series(divergence_scores, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
        if values.empty: return "Insufficient"
        mean = float(values.mean()); return "Green" if mean < 0.5 else ("Amber" if mean <= 1.0 else "Red")

    def compute_divergence(self, backtest_run_id: str, paper_trading_name: str) -> ReconciliationResult:
        if self.lineage is not None:
            record = self.lineage.get_run(backtest_run_id)
            predicted = pd.Series(record.metrics.get("daily_returns", []), dtype=float)
        else:
            predicted = pd.Series(self.backtest_returns.get(backtest_run_id, []), dtype=float)
        if self.paper_trader is not None: actual = pd.Series(self.paper_trader.get_signal_log(paper_trading_name).groupby("timestamp")["actual_return"].mean(), dtype=float)
        else: actual = pd.Series(dtype=float)
        if predicted.empty or actual.empty: return ReconciliationResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float), np.nan, 0.0, "Insufficient", 0)
        if not isinstance(predicted.index, pd.DatetimeIndex): predicted.index = pd.RangeIndex(len(predicted)); actual.index = pd.RangeIndex(len(actual)) if not isinstance(actual.index, pd.DatetimeIndex) else actual.index
        aligned = pd.concat([predicted.rename("predicted"), actual.rename("actual")], axis=1).dropna(); predicted, actual = aligned["predicted"], aligned["actual"]; divergence = self.compute_running_divergence_score(actual, predicted); bt_curve = (1.0 + predicted).cumprod(); pt_curve = (1.0 + actual).cumprod(); verdict = self.status_verdict(divergence) if len(divergence) >= 20 else "Insufficient"; return ReconciliationResult(bt_curve, pt_curve, divergence, float(divergence.mean()) if len(divergence) else np.nan, self.compute_reliability_decay_rate(divergence), verdict, len(divergence))
