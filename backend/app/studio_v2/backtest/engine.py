from __future__ import annotations

"""
Event-driven simulation engine (F2.2).

Sequential bar-by-bar execution. Orders fire at close, fill at next open.
Handles corporate actions, partial fills via ADV ratio, short-sell flags.
"""

import hashlib
import importlib.util
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from ..shared.data_loader import get_all_tickers, get_ohlcv_batch
from ..shared.liquidity import LiquidityCalibrator, almgren_chriss_impact

try:
    import bottleneck as bn
    HAVE_BOTTLENECK = True
except ImportError:
    HAVE_BOTTLENECK = False


@dataclass
class Position:
    ticker: str
    shares: float = 0.0
    average_price: float = 0.0
    last_price: float = 0.0


@dataclass
class Order:
    ticker: str
    quantity: float
    side: str
    signal_date: pd.Timestamp
    target_weight: float = 0.0


@dataclass
class Fill:
    ticker: str
    quantity: float
    price: float
    side: str
    signal_date: pd.Timestamp
    fill_date: pd.Timestamp
    transaction_cost: float
    impact_bps: float


@dataclass
class DateNAV:
    date: pd.Timestamp
    nav: float


@dataclass
class SimulationConfig:
    strategy_source: Any = None
    universe_id: Any = None
    date_start: Any = None
    date_end: Any = None
    benchmark: str = "SPY"
    rebalance_freq: str = "daily"
    position_sizing: Any = "equal_weight"
    cost_model: str = "almgren_chriss"
    cost_bps: float = 0.0
    survivorship_bias: bool = True
    margin_enabled: bool = False
    max_fill_pct: float = 0.20
    hard_to_borrow_threshold: float = 0.05
    initial_cash: float = 1_000_000.0
    max_leverage: float = 1.0
    fixed_cost_bps: float = 0.0
    parameters: dict = field(default_factory=dict)
    corporate_actions: Any = None
    tax_config: Any = None
    date_range_override: Any = None


@dataclass
class PortfolioState:
    positions: Dict[str, Position] = field(default_factory=dict)
    cash: float = 1_000_000.0
    margin_used: float = 0.0
    nav_history: List[DateNAV] = field(default_factory=list)


@dataclass
class SimulationResult:
    trade_log: pd.DataFrame
    daily_returns: pd.Series
    daily_nav: pd.Series
    positions_log: pd.DataFrame
    orders_log: pd.DataFrame
    config: SimulationConfig
    run_duration_seconds: float
    warnings: List[str] = field(default_factory=list)
    tax_report: Optional[dict] = None
    synthetic_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"trade_log": self.trade_log.to_dict(orient="records"), "daily_returns": self.daily_returns.to_dict(), "daily_nav": self.daily_nav.to_dict(), "positions_log": self.positions_log.to_dict(orient="records"), "orders_log": self.orders_log.to_dict(orient="records"), "config": asdict(self.config), "run_duration_seconds": self.run_duration_seconds, "warnings": self.warnings, "tax_report": self.tax_report, "synthetic_data": self.synthetic_data}


def _empty_result(config: SimulationConfig, started: float, warning: str) -> SimulationResult:
    return SimulationResult(pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame(), pd.DataFrame(), config, time.monotonic() - started, [warning])


def compute_adv(volume_series: pd.Series, window: int = 63, close_price: Optional[pd.Series] = None) -> pd.Series:
    """Return rolling average dollar volume, using close prices when supplied."""
    if isinstance(volume_series, pd.DataFrame):
        dollar = volume_series.get("volume", pd.Series(dtype=float, index=volume_series.index)) * volume_series.get("close", 1.0)
    else:
        dollar = pd.Series(volume_series, copy=True)
        close = close_price if close_price is not None else getattr(volume_series, "attrs", {}).get("close")
        if close is not None:
            dollar = dollar * pd.Series(close, index=dollar.index)
    w = max(1, int(window))
    arr = pd.to_numeric(dollar, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if HAVE_BOTTLENECK:
        move_window = min(w, max(1, len(arr)))
        result = bn.move_mean(arr.to_numpy(), window=move_window, min_count=1)
        return pd.Series(result, index=arr.index, dtype=float)
    return arr.rolling(w, min_periods=1).mean()


def partial_fill_ratio(order_size: float, adv: float, max_fill_pct: float = 0.20) -> float:
    order, adv_value, cap = abs(float(order_size)), float(adv), max(0.0, float(max_fill_pct))
    if order == 0:
        return 1.0
    if not np.isfinite(adv_value) or adv_value <= 0:
        return 0.0
    return float(min(1.0, cap / (order / adv_value)))


def _load_strategy(source: Any) -> Optional[Callable[[pd.DataFrame], Any]]:
    if callable(source):
        return source
    module = source
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Strategy file not found: {path}")
        module_name = f"studio_strategy_{hashlib.sha256(str(path).encode()).hexdigest()[:12]}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load strategy module from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    function = getattr(module, "generate_signals", None)
    if function is None or not callable(function):
        raise ValueError("Strategy must expose callable generate_signals(data)")
    setattr(function, "_studio_input", getattr(module, "STUDIO_INPUT", "long_ohlcv"))
    return function


class EventDrivenEngine:
    """Sequential event-driven simulator with next-open fills."""

    def __init__(self) -> None:
        self.config: Optional[SimulationConfig] = None
        self.price_data: Dict[str, pd.DataFrame] = {}
        self.portfolio = PortfolioState()
        self.pending_orders: List[Order] = []
        self._strategy: Optional[Callable[[pd.DataFrame], Any]] = None
        self._warnings: List[str] = []
        self._corporate_actions = pd.DataFrame()
        self._liquidity = LiquidityCalibrator()

    def run(self, config: SimulationConfig) -> SimulationResult:
        started = time.monotonic()
        if not isinstance(config, SimulationConfig):
            config = SimulationConfig(**dict(config))
        if config.date_range_override:
            override = dict(config.date_range_override)
            config.date_start = override.get("start", override.get("date_start", config.date_start))
            config.date_end = override.get("end", override.get("date_end", config.date_end))
        self.config = config
        self.portfolio = PortfolioState(cash=float(config.initial_cash))
        self.pending_orders, self._warnings = [], []
        self._lambda_cache = {}
        self._full_combined = None
        self._corporate_actions = self._normalize_corporate_actions(config.corporate_actions)
        self._strategy = _load_strategy(config.strategy_source) if config.strategy_source is not None else None
        self.price_data = self._load_and_prepare_universe(config.universe_id, config.date_start, config.date_end)
        if not self.price_data:
            return _empty_result(config, started, "No tickers or price data available for the requested universe and date range")
        from ..data_studio.synthetic_flagging import SyntheticRangeDetector
        detector = SyntheticRangeDetector()
        synthetic_audit = {
            ticker: detector.detect(ticker, frame.reset_index())
            for ticker, frame in self.price_data.items()
        }
        synthetic_audit = {
            ticker: result for ticker, result in synthetic_audit.items()
            if result.get("has_synthetic_data")
        }
        if synthetic_audit:
            self._warnings.append(
                f"Synthetic or imputed data detected for {len(synthetic_audit)} instrument(s)"
            )
        all_dates = sorted(set().union(*(set(frame.index) for frame in self.price_data.values())))
        date_start = pd.Timestamp(config.date_start) if config.date_start is not None else pd.Timestamp.min
        date_end = pd.Timestamp(config.date_end) if config.date_end is not None else pd.Timestamp.max
        dates = [d for d in all_dates if date_start <= d <= date_end]
        if not dates:
            return _empty_result(config, started, "Empty date range: no trading days")
        trades, orders, navs, position_rows = [], [], [], []
        n = len(dates)
        for index in range(n):
            current_date = dates[index]
            self._apply_corporate_actions(self.portfolio, current_date)
            if self.pending_orders:
                fills = self._fill_orders(self.pending_orders, self.price_data, current_date)
                trades.extend(asdict(fill) for fill in fills)
                self.pending_orders = []
            nav = self._compute_nav(self.portfolio, self.portfolio.cash, self.price_data, current_date)
            navs.append(nav)
            self.portfolio.nav_history.append(DateNAV(current_date, nav))
            pos = self.portfolio.positions
            if pos:
                position_rows.extend(
                    (current_date, ticker, p.shares, p.last_price, p.shares * p.last_price)
                    for ticker, p in pos.items() if abs(p.shares) > 1e-12
                )
            if index < n - 1 and self._is_rebalance_date(current_date):
                new_orders = self._generate_orders(self._compute_signals(current_date, self.price_data), self.portfolio, current_date)
                self.pending_orders.extend(new_orders)
                orders.extend(asdict(order) for order in new_orders)
        nav_series = pd.Series(navs, index=pd.DatetimeIndex(dates), dtype=float)
        nav_series.index.name = "date"
        returns = nav_series.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if position_rows:
            pos_df = pd.DataFrame(position_rows, columns=["date", "ticker", "shares", "price", "market_value"])
        else:
            pos_df = pd.DataFrame()
        result = SimulationResult(pd.DataFrame(trades), returns, nav_series, pos_df, pd.DataFrame(orders), config, time.monotonic() - started, self._warnings)
        result.synthetic_data = synthetic_audit
        if config.tax_config is not None and not result.trade_log.empty:
            from .tax_engine import TaxEngine
            result.tax_report = TaxEngine().apply_tax(result.trade_log, config.tax_config, result.daily_nav)
        return result

    def _resolve_tickers(self, universe_id: Any) -> List[str]:
        if isinstance(universe_id, dict):
            values = universe_id.get("tickers", universe_id.get("constituents", []))
        elif isinstance(universe_id, (list, tuple, set, np.ndarray, pd.Index)):
            values = universe_id
        elif isinstance(universe_id, str) and "," in universe_id:
            values = universe_id.split(",")
        elif isinstance(universe_id, str) and universe_id.strip() and universe_id.upper() not in {"ALL", "UNIVERSE"}:
            values = [universe_id]
        else:
            values = get_all_tickers()
        return sorted({str(value).upper().strip() for value in values if str(value).strip()})

    def _load_and_prepare_universe(self, universe_id: str, start: date, end: date) -> Dict[str, pd.DataFrame]:
        data = {}
        tickers = self._resolve_tickers(universe_id)
        batch = get_ohlcv_batch(tickers, start, end)
        for ticker in tickers:
            frame = batch.get(ticker, pd.DataFrame())
            if frame.empty:
                self._warnings.append(f"Missing price data for {ticker}")
                continue
            frame = frame.copy()
            frame["date"] = pd.to_datetime(frame["date"])
            frame = frame.set_index("date").sort_index()
            dv_arr = pd.to_numeric(frame["dollar_volume"], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
            if HAVE_BOTTLENECK:
                adv_arr = bn.move_mean(dv_arr, window=min(63, max(1, len(dv_arr))), min_count=1)
            else:
                adv_arr = pd.Series(dv_arr).rolling(63, min_periods=1).mean().to_numpy()
            frame["adv"] = adv_arr
            ret = frame["close"].pct_change(fill_method=None).to_numpy(dtype=float, na_value=np.nan)
            if HAVE_BOTTLENECK:
                sigma_arr = bn.move_std(ret, window=min(21, max(1, len(ret))), min_count=2)
            else:
                sigma_arr = pd.Series(ret).rolling(21, min_periods=2).std().to_numpy()
            sigma_arr = np.nan_to_num(sigma_arr, nan=0.0) * np.sqrt(252.0)
            frame["sigma"] = sigma_arr
            data[ticker] = frame
        return data

    def _combined_history(self, current_date: pd.Timestamp) -> pd.DataFrame:
        if getattr(self, "_full_combined", None) is None:
            rows = []
            for ticker, frame in self.price_data.items():
                hist = frame.reset_index()
                hist["ticker"] = ticker
                rows.append(hist)
            self._full_combined = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
            self._full_combined["date"] = pd.to_datetime(self._full_combined["date"])
        return self._full_combined.loc[self._full_combined["date"] <= current_date].reset_index(drop=True)

    def _run_date_loop(self, dates: List[date], price_data: Dict[str, pd.DataFrame]) -> None:
        """Process supplied dates sequentially, retaining loop artifacts for callers."""
        self.price_data = price_data
        self._loop_trades, self._loop_orders, self._loop_navs = [], [], []
        for index, current_date in enumerate(pd.to_datetime(dates)):
            self._apply_corporate_actions(self.portfolio, current_date)
            if self.pending_orders:
                self._loop_trades.extend(asdict(fill) for fill in self._fill_orders(self.pending_orders, price_data, current_date))
                self.pending_orders = []
            nav = self._compute_nav(self.portfolio, self.portfolio.cash, price_data, current_date); self._loop_navs.append((current_date, nav))
            if index < len(dates) - 1 and self._is_rebalance_date(current_date):
                orders = self._generate_orders(self._compute_signals(current_date, price_data), self.portfolio, current_date); self.pending_orders.extend(orders); self._loop_orders.extend(asdict(order) for order in orders)

    def _compute_signals(self, current_date: date, price_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        if self._strategy is None:
            return pd.DataFrame(columns=["ticker", "signal"])
        history = self._combined_history(pd.Timestamp(current_date))
        if history.empty:
            return pd.DataFrame(columns=["ticker", "signal"])
        if getattr(self._strategy, "_studio_input", "long_ohlcv") == "wide_close":
            wide = history.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").sort_index()
            result = self._strategy(wide, dict(self.config.parameters or {}))
            if isinstance(result, pd.DataFrame) and not result.empty:
                result = result.iloc[-1]
        else:
            try:
                result = self._strategy(history, dict(self.config.parameters or {}))
            except TypeError:
                result = self._strategy(history)
        if isinstance(result, pd.Series):
            result = result.rename("signal").reset_index().rename(columns={"index": "ticker"})
        elif isinstance(result, dict):
            result = pd.DataFrame({"ticker": list(result), "signal": list(result.values())})
        elif np.isscalar(result):
            result = pd.DataFrame({"ticker": list(price_data), "signal": [result] * len(price_data)})
        else:
            result = pd.DataFrame(result)
        if "ticker" not in result.columns:
            result = result.reset_index().rename(columns={"index": "ticker"})
        signal_col = next((c for c in ("signal", "signals", "weight", "target_weight", "position") if c in result.columns), None)
        if signal_col is None:
            numeric = result.select_dtypes(include=[np.number]).columns.tolist()
            signal_col = numeric[0] if numeric else None
        if signal_col is None:
            return pd.DataFrame(columns=["ticker", "signal"])
        out = result[["ticker", signal_col]].rename(columns={signal_col: "signal"})
        out["ticker"] = out["ticker"].astype(str).str.upper()
        out["signal"] = pd.to_numeric(out["signal"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return out[out["ticker"].isin(price_data)]

    def _is_rebalance_date(self, current_date: pd.Timestamp) -> bool:
        custom_dates = (self.config.parameters or {}).get("rebalance_dates", []) if self.config else []
        if custom_dates:
            return current_date.normalize() in {pd.Timestamp(value).normalize() for value in custom_dates}
        frequency = str(self.config.rebalance_freq if self.config else "daily").lower()
        return frequency in {"daily", "d"} or (frequency in {"weekly", "w"} and current_date.weekday() == 4) or (frequency in {"monthly", "m"} and (current_date + pd.Timedelta(days=1)).month != current_date.month) or (frequency in {"quarterly", "q"} and current_date.month in (3, 6, 9, 12) and (current_date + pd.Timedelta(days=1)).month != current_date.month)

    def _generate_orders(self, signals: pd.DataFrame, positions: PortfolioState, current_date: date) -> List[Order]:
        if signals.empty:
            return []
        ts = pd.Timestamp(current_date)
        sig_arr = pd.to_numeric(signals["signal"], errors="coerce").fillna(0.0).to_numpy()
        nonzero_mask = sig_arr != 0
        if not nonzero_mask.any():
            weights = pd.Series(0.0, index=list(self.price_data))
        else:
            nonzero = signals.iloc[nonzero_mask].copy()
            if callable(self.config.position_sizing):
                raw = self.config.position_sizing(nonzero.copy())
                weights = pd.Series(raw, index=nonzero["ticker"]) if not isinstance(raw, pd.Series) else raw
            else:
                weights = nonzero.set_index("ticker")["signal"].apply(np.sign)
                w_sum = max(1.0, float(weights.abs().sum()))
                if w_sum > 0:
                    weights = weights / w_sum
                if str(self.config.position_sizing).lower() == "vol_scaled":
                    sigmas = {}
                    for tkr in weights.index:
                        f = self.price_data.get(tkr)
                        if f is not None and ts in f.index:
                            sigmas[tkr] = 1.0 / max(float(f.at[ts, "sigma"]), 1e-8)
                        else:
                            sigmas[tkr] = 1.0
                    inv = pd.Series(sigmas)
                    weights = weights * inv
                    w_sum2 = max(1e-12, float(weights.abs().sum()))
                    if w_sum2 > 0:
                        weights = weights / w_sum2
        nav = self._compute_nav(positions, positions.cash, self.price_data, ts)
        result = []
        for ticker in self.price_data:
            frame = self.price_data[ticker]
            if ts not in frame.index:
                continue
            close = float(frame.at[ts, "close"])
            if not np.isfinite(close) or close <= 0:
                continue
            target = float(weights.get(ticker, 0.0)) * nav
            cur_pos = positions.positions.get(ticker, Position(ticker))
            current = cur_pos.shares * close
            quantity = (target - current) / close
            if abs(quantity) <= 1e-10:
                continue
            side = "buy" if quantity > 0 else "sell"
            if quantity < 0 and self.config.margin_enabled and abs(quantity) > max(0.0, cur_pos.shares):
                side = "short"
            result.append(Order(ticker, abs(quantity), side, ts, float(weights.get(ticker, 0.0))))
        return result

    def _fill_orders(self, orders: List[Order], price_data: Dict[str, pd.DataFrame], current_date: date) -> List[Fill]:
        fills = []
        ts = pd.Timestamp(current_date)
        for order in orders:
            frame = price_data.get(order.ticker)
            if frame is None or ts not in frame.index:
                self._warnings.append(f"Order for {order.ticker} not filled: missing next-open price")
                continue
            row = frame.loc[ts]
            open_price = float(row.get("open", np.nan))
            if not np.isfinite(open_price) or open_price <= 0:
                open_price = float(row.get("close", np.nan))
            if not np.isfinite(open_price) or open_price <= 0:
                continue
            adv = float(row.get("adv", np.nan))
            quantity = order.quantity * partial_fill_ratio(order.quantity * open_price, adv, self.config.max_fill_pct)
            if quantity <= 0:
                continue
            signed = quantity if order.side == "buy" else -quantity
            if order.side == "short" and self._is_hard_to_borrow(order.ticker, ts):
                self._warnings.append(f"Short order for {order.ticker} rejected: hard-to-borrow constraint")
                continue
            sigma = max(float(row.get("sigma", 0.0)), 1e-4)
            if self.config.cost_model == "zero":
                impact_bps = 0.0
            elif self.config.cost_model == "flat_bps":
                impact_bps = max(0.0, float(self.config.cost_bps))
            else:
                lam = self._lambda_for_order(order.ticker, ts)
                impact_bps = almgren_chriss_impact(abs(signed * open_price), adv, sigma, lam)
            total_bps = impact_bps + max(0.0, float(self.config.fixed_cost_bps))
            fill_price = open_price * (1.0 + total_bps / 10000.0 * (1 if signed > 0 else -1))
            transaction_cost = abs(signed * fill_price) * total_bps / 10000.0
            self.portfolio.cash -= signed * fill_price + transaction_cost
            position = self.portfolio.positions.setdefault(order.ticker, Position(order.ticker))
            prior = position.shares
            new = prior + signed
            if prior == 0 or np.sign(prior) == np.sign(signed):
                position.average_price = (abs(prior) * position.average_price + abs(signed) * fill_price) / max(abs(new), 1e-12)
            elif abs(new) < 1e-12:
                position.average_price = 0.0
            position.shares, position.last_price = new, fill_price
            fills.append(Fill(order.ticker, signed, fill_price, order.side, order.signal_date, ts, transaction_cost, impact_bps))
        return fills

    def _is_hard_to_borrow(self, ticker: str, current_date: pd.Timestamp) -> bool:
        frame = self.price_data.get(ticker)
        if frame is None or current_date not in frame.index: return False
        borrow = float(frame.at[current_date, "borrow_rate"]) if "borrow_rate" in frame.columns else np.nan
        threshold = float(self.config.hard_to_borrow_threshold) if self.config else 0.05
        return bool(np.isfinite(borrow) and borrow > threshold)

    def _lambda_for_order(self, ticker: str, current_date: pd.Timestamp) -> float:
        configured = self.config.parameters.get("lambda_dict", {}) if self.config is not None else {}
        defaults = {"large": 4e-6, "mid": 2.4e-5, "small": 1.2e-4}
        defaults.update({str(key): float(value) for key, value in configured.items() if np.isfinite(value) and float(value) > 0})
        key = (current_date,)
        if not hasattr(self, '_lambda_cache'):
            self._lambda_cache = {}
        if key not in self._lambda_cache:
            adv_list = []
            adv_map = {}
            for symbol, frame in self.price_data.items():
                if current_date in frame.index:
                    adv_val = frame.at[current_date, "adv"]
                    if np.isfinite(adv_val) and adv_val > 0:
                        adv_list.append(adv_val)
                        adv_map[symbol] = adv_val
            if not adv_list:
                self._lambda_cache[key] = (defaults, {}, 0.0)
            else:
                adv_arr = np.asarray(adv_list, dtype=float)
                self._lambda_cache[key] = (defaults, adv_map, adv_arr)
        defaults, adv_map, adv_arr = self._lambda_cache[key]
        if len(adv_arr) == 0: return defaults["small"]
        adv = adv_map.get(ticker, 0.0)
        if adv <= 0: return defaults["small"]
        percentile = float(np.mean(adv_arr < adv))
        return defaults["large"] if percentile >= 0.90 else defaults["mid"] if percentile >= 0.50 else defaults["small"]

    def _apply_corporate_actions(self, positions: PortfolioState, current_date: date) -> None:
        events = self._corporate_actions
        ts = pd.Timestamp(current_date)
        if not events.empty:
            day_events = events.loc[events["date"] == ts]
            if not day_events.empty:
                for ticker, position in positions.positions.items():
                    ticker_rows = day_events.loc[day_events["ticker"] == ticker]
                    for action_type, ratio, amount, lp in zip(ticker_rows["action_type"], ticker_rows.get("ratio", pd.Series([1.0])), ticker_rows.get("amount", pd.Series([0.0])), ticker_rows.get("last_price", pd.Series([np.nan]))):
                        action = str(action_type).lower()
                        if action == "split":
                            r = float(ratio)
                            if np.isfinite(r) and r > 0:
                                position.shares *= r; position.average_price /= r
                        elif action == "dividend":
                            a = float(amount)
                            if np.isfinite(a): self.portfolio.cash += position.shares * a
                        elif action in {"delisting", "delist"}:
                            s = float(lp if np.isfinite(lp) else amount)
                            if np.isfinite(s): self.portfolio.cash += position.shares * s
                            position.shares = 0.0; position.average_price = 0.0; position.last_price = s
        for ticker, position in positions.positions.items():
            frame = self.price_data.get(ticker)
            if frame is not None:
                mask = frame.index <= ts
                close_vals = frame.loc[mask, "close"]
                if len(close_vals):
                    position.last_price = float(close_vals.iloc[-1])

    def _normalize_corporate_actions(self, actions: Any) -> pd.DataFrame:
        if actions is None: return pd.DataFrame(columns=["date", "ticker", "action_type", "ratio", "amount", "last_price"])
        frame = pd.DataFrame(actions).copy()
        if frame.empty: return pd.DataFrame(columns=["date", "ticker", "action_type", "ratio", "amount", "last_price"])
        frame = frame.rename(columns={"type": "action_type", "action": "action_type"})
        required = {"date", "ticker", "action_type"}
        missing = required - set(frame.columns)
        if missing: raise ValueError(f"Corporate actions missing columns: {sorted(missing)}")
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None); frame["ticker"] = frame["ticker"].astype(str).str.upper(); frame["ratio"] = pd.to_numeric(frame.get("ratio", 1.0), errors="coerce").fillna(1.0); frame["amount"] = pd.to_numeric(frame.get("amount", 0.0), errors="coerce").fillna(0.0); frame["last_price"] = pd.to_numeric(frame.get("last_price", np.nan), errors="coerce"); return frame.dropna(subset=["date"])

    def _compute_nav(self, positions: PortfolioState, cash: float, prices: Dict[str, pd.DataFrame], current_date: date) -> float:
        value = float(cash)
        ts = pd.Timestamp(current_date)
        for ticker, position in positions.positions.items():
            frame = prices.get(ticker)
            if frame is None:
                continue
            mask = frame.index <= ts
            close_vals = frame.loc[mask, "close"]
            if len(close_vals):
                position.last_price = float(close_vals.iloc[-1])
            value += position.shares * position.last_price
        return float(value)
