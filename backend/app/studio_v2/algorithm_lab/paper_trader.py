from __future__ import annotations

"""
Forward paper trading with backtest-to-live code parity (F1.9).

Daily cron job that calls the same generate_signals() function as
Backtest Studio on delayed yfinance data. Logs signals, computes
forward reliability score after N days.
"""

import ast
import importlib.util
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from ..shared.data_loader import get_ohlcv_batch


@dataclass
class PaperTradeResult:
    strategy_name: str
    timestamp: str
    signals: pd.DataFrame
    reliability_score: Optional[float]
    warning: Optional[str] = None


@dataclass
class PaperTradingStatus:
    strategy_name: str
    burn_in_days_completed: int
    reliability_score: Optional[float]
    num_signals: int
    status: str


class CodeParityBridge:
    def __init__(self) -> None:
        self._module_cache: Dict[str, ModuleType] = {}

    def validate_strategy_signature(self, strategy_file: str) -> bool:
        tree = ast.parse(Path(strategy_file).read_text(encoding="utf-8")); functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "generate_signals"]; return bool(functions and len(functions[0].args.args) >= 1 and functions[0].args.args[0].arg == "data")

    def load_strategy_module(self, strategy_file: str) -> ModuleType:
        path = Path(strategy_file)
        if not path.exists(): raise FileNotFoundError(f"Strategy file not found: {path}")
        if not self.validate_strategy_signature(str(path)): raise ValueError("Strategy must define generate_signals(data)")
        cache_key = str(path.resolve()) + ":" + str(path.stat().st_mtime_ns)
        if cache_key in self._module_cache:
            return self._module_cache[cache_key]
        spec = importlib.util.spec_from_file_location(f"paper_strategy_{uuid.uuid4().hex}", path)
        if spec is None or spec.loader is None: raise ImportError(f"Unable to load strategy module: {path}")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); self._module_cache = {cache_key: module}; return module

    def call_generate_signals(self, strategy_module: ModuleType, data: pd.DataFrame) -> pd.DataFrame:
        result = strategy_module.generate_signals(data)
        if isinstance(result, pd.Series): result = result.rename("signal").reset_index().rename(columns={"index": "ticker"})
        elif isinstance(result, dict): result = pd.DataFrame({"ticker": list(result), "signal": list(result.values())})
        else: result = pd.DataFrame(result)
        if "ticker" not in result.columns: result = result.reset_index().rename(columns={"index": "ticker"})
        signal = next((column for column in ("signal", "signals", "weight", "position") if column in result.columns), None)
        if signal is None: raise ValueError("generate_signals(data) must return signal values")
        return result[["ticker", signal]].rename(columns={signal: "signal"})


class PaperTrader:
    def __init__(self, configs: Optional[dict] = None, feed: Any = None) -> None:
        self._configs: Dict[str, dict] = dict(configs or {})
        self._logs: Dict[str, pd.DataFrame] = {}
        self.feed = feed
        self.bridge = CodeParityBridge()

    def register_strategy(self, strategy_name: str, strategy_file: str, universe: list, burn_in_days: int = 20) -> None:
        self._configs[strategy_name] = {"strategy_file": strategy_file, "universe": list(universe), "burn_in_days": int(burn_in_days), "status": "active"}

    def run_daily_paper_trade(self, strategy_name: str) -> PaperTradeResult:
        config = self._configs.get(strategy_name)
        if not config: raise KeyError(f"No paper-trading configuration for '{strategy_name}'")
        module = self.bridge.load_strategy_module(config["strategy_file"]); rows = []
        tickers = [str(t).upper() for t in config.get("universe", [])]
        if self.feed is not None and hasattr(self.feed, "get_ohlcv_batch"):
            batch = self.feed.get_ohlcv_batch(tickers)
        elif callable(self.feed):
            batch = {ticker: self.feed(ticker) for ticker in tickers}
        else:
            batch = get_ohlcv_batch(tickers)
        for ticker in tickers:
            frame = batch.get(ticker, pd.DataFrame())
            if len(frame) < 2: continue
            data = frame.tail(252).copy(); output = self.bridge.call_generate_signals(module, data); signal = pd.to_numeric(output["signal"], errors="coerce").dropna(); value = float(signal.iloc[-1]) if len(signal) else 0.0; current = float(data["adjusted_close"].iloc[-1]); previous = float(data["adjusted_close"].iloc[-2]); actual = current / previous - 1.0 if previous else np.nan; vol = float(pd.to_numeric(data["adjusted_close"], errors="coerce").pct_change(fill_method=None).std()) if len(data) > 2 else 0.0; predicted = float(np.sign(value) * min(abs(value), 1.0) * max(vol, 1e-6)); rows.append({"timestamp": str(data["date"].iloc[-1]), "ticker": ticker, "signal_direction": value, "predicted_return": predicted, "actual_return": actual, "entry_price": current, "exit_price": current, "status": "recorded"})
        new = pd.DataFrame(rows); prior = self._logs.get(strategy_name, pd.DataFrame()); self._logs[strategy_name] = pd.concat([prior, new], ignore_index=True).drop_duplicates(["timestamp", "ticker"], keep="last") if not new.empty else prior
        reliability = self.compute_forward_reliability(strategy_name, config.get("burn_in_days", 20)); warning = "strategy not producing signals in live conditions" if new.empty else None; return PaperTradeResult(strategy_name, datetime.now(timezone.utc).isoformat(), new, reliability, warning)

    def compute_forward_reliability(self, strategy_name: str, min_days: int = 20) -> Optional[float]:
        log = self._logs.get(strategy_name, pd.DataFrame())
        if log.empty or log["timestamp"].nunique() < int(min_days): return None
        predicted = pd.to_numeric(log["predicted_return"], errors="coerce"); actual = pd.to_numeric(log["actual_return"], errors="coerce"); valid = predicted.notna() & actual.notna()
        return float(predicted[valid].rank().corr(actual[valid].rank())) if valid.sum() >= 2 else None

    def get_status(self, strategy_name: str) -> PaperTradingStatus:
        config = self._configs.get(strategy_name, {}); log = self._logs.get(strategy_name, pd.DataFrame()); score = self.compute_forward_reliability(strategy_name, config.get("burn_in_days", 20)); days = int(log["timestamp"].nunique()) if not log.empty else 0; return PaperTradingStatus(strategy_name, days, score, len(log), "reliable" if score is not None and score >= 0.3 else ("burn-in" if score is None else "not surviving live contact"))

    def get_equity_curve(self, strategy_name: str) -> pd.DataFrame:
        log = self._logs.get(strategy_name, pd.DataFrame())
        if log.empty: return pd.DataFrame(columns=["date", "return", "equity"])
        daily = log.assign(date=pd.to_datetime(log["timestamp"], errors="coerce")).groupby("date")["actual_return"].mean().fillna(0.0); return pd.DataFrame({"date": daily.index, "return": daily.values, "equity": (1.0 + daily.values).cumprod()})

    def get_signal_log(self, strategy_name: str) -> pd.DataFrame: return self._logs.get(strategy_name, pd.DataFrame()).copy()


def daily_cron_job() -> None:
    trader = _default_paper_trader()
    for name, config in list(trader._configs.items()):
        if config.get("status", "active") == "active":
            try: trader.run_daily_paper_trade(name)
            except (OSError, ValueError, KeyError): continue


_PAPER_TRADER: Optional[PaperTrader] = None


def _default_paper_trader() -> PaperTrader:
    global _PAPER_TRADER
    if _PAPER_TRADER is None:
        _PAPER_TRADER = PaperTrader()
    return _PAPER_TRADER
