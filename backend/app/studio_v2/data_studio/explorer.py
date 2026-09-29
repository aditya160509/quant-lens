from __future__ import annotations

"""Data Explorer and Missing Data Heatmap (F6.7-F6.8)."""

from dataclasses import asdict, dataclass
from typing import Any, List

import numpy as np
import pandas as pd

from ..shared.data_loader import get_ohlcv, get_ohlcv_batch

try:
    import bottleneck as bn
    _HAS_BN = True
except ImportError:
    _HAS_BN = False


@dataclass
class AnomalyEvent:
    date: Any
    severity: str
    kind: str
    value: float
    suggested_action: str


@dataclass
class DistributionStats:
    mean: float
    std: float
    skewness: float
    excess_kurtosis: float
    p1: float
    p99: float
    jarque_bera_stat: float
    jarque_bera_p: float
    histogram_bins: List[float]
    qqplot_data: List[dict]


def garman_klass_vol(high: pd.Series, low: pd.Series, close: pd.Series, open: pd.Series, window: int = 21) -> pd.Series:
    frame = pd.concat([high, low, close, open], axis=1).apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    frame.columns = ["high", "low", "close", "open"]
    term = 0.5 * np.log(frame["high"] / frame["low"]) ** 2 - (2 * np.log(2) - 1) * np.log(frame["close"] / frame["open"]) ** 2
    w = max(1, int(window))
    move_window = min(w, max(1, len(term)))
    rolling_sum = bn.move_sum(term.to_numpy(dtype=float), window=move_window, min_count=1) if _HAS_BN else term.rolling(w, min_periods=1).sum().to_numpy()
    return pd.Series(np.sqrt((252.0 / w) * np.maximum(rolling_sum, 0.0)), index=frame.index)


def detect_5sigma_moves(returns: pd.Series, window: int = 63) -> List[AnomalyEvent]:
    values = pd.to_numeric(pd.Series(returns), errors="coerce").replace([np.inf, -np.inf], np.nan)
    w = max(2, int(window))
    if _HAS_BN:
        arr = values.to_numpy(dtype=float)
        move_window = min(w, max(1, len(arr)))
        mean = pd.Series(bn.move_mean(arr, window=move_window, min_count=2), index=values.index)
        std = pd.Series(bn.move_std(arr, window=move_window, min_count=2), index=values.index)
    else:
        mean = values.rolling(w, min_periods=2).mean(); std = values.rolling(w, min_periods=2).std()
    std = std.replace(0, np.nan)
    z = (values - mean) / std
    return [AnomalyEvent(index, "high", "5_sigma_move", float(values.loc[index]), "review price and corporate action data") for index in values.index[z.abs() > 5]]


class DataExplorer:
    def get_primary_series(
        self,
        ticker: str,
        start: Any,
        end: Any,
        *,
        limit: int | None = None,
    ) -> pd.DataFrame:
        frame = get_ohlcv(ticker, start, end)
        if frame.empty:
            return frame
        frame["returns"] = frame["adjusted_close"].pct_change(fill_method=None)
        frame["realized_vol_gk"] = garman_klass_vol(frame["high"], frame["low"], frame["close"], frame["open"])
        w = 252; values = pd.to_numeric(frame["returns"], errors="coerce").to_numpy(dtype=float)
        if _HAS_BN:
            move_window = min(w, max(1, len(values)))
            mean = bn.move_mean(values, window=move_window, min_count=2); std = bn.move_std(values, window=move_window, min_count=2)
            frame["rolling_sharpe"] = mean / np.where(std == 0, np.nan, std) * np.sqrt(252.0)
        else:
            frame["rolling_sharpe"] = frame["returns"].rolling(w, min_periods=2).mean().div(frame["returns"].rolling(w, min_periods=2).std().replace(0, np.nan)) * np.sqrt(252.0)
        if limit is not None:
            frame = frame.tail(max(1, min(int(limit), 500))).reset_index(drop=True)
        return frame

    def get_derived_series(self, ticker: str, series_type: str, start: Any, end: Any) -> pd.Series:
        frame = self.get_primary_series(ticker, start, end)
        if frame.empty:
            return pd.Series(dtype=float)
        key = str(series_type).lower()
        if key in frame:
            return frame.set_index("date")[key]
        if key in {"garman_klass", "realized_vol"}:
            return frame.set_index("date")["realized_vol_gk"]
        return frame.set_index("date")["returns"] if key in {"returns", "return"} else frame.set_index("date")["rolling_sharpe"] if key in {"rolling_sharpe", "sharpe"} else pd.Series(dtype=float)

    def get_secondary_overlay(self, primary: Any, secondary: Any, start: Any, end: Any) -> pd.DataFrame:
        frame = pd.concat([pd.Series(primary, name="primary"), pd.Series(secondary, name="secondary")], axis=1)
        frame.index = pd.to_datetime(frame.index, errors="coerce")
        return frame.loc[(frame.index >= pd.Timestamp(start)) & (frame.index <= pd.Timestamp(end))].sort_index()

    def get_distribution(self, returns: Any) -> DistributionStats:
        values = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
        n = len(values); skew = float(values.skew()) if n >= 3 else 0.0; kurt = float(values.kurt()) if n >= 4 else 0.0
        jb = n / 6.0 * (skew ** 2 + kurt ** 2 / 4.0) if n else np.nan
        try:
            from scipy.stats import chi2, norm
            p, expected = float(chi2.sf(jb, 2)), norm.ppf(np.linspace(0.5 / max(1, n), 1 - 0.5 / max(1, n), n)) if n else np.array([])
        except Exception:
            p, expected = (float(np.exp(-jb / 2.0)) if n else np.nan), np.linspace(-2, 2, n)
        counts, bins = np.histogram(values, bins=min(30, max(1, n))) if n else (np.array([]), np.array([]))
        ordered = np.sort(values.to_numpy())
        return DistributionStats(float(values.mean()) if n else np.nan, float(values.std(ddof=1)) if n > 1 else 0.0, skew, kurt, float(values.quantile(0.01)) if n else np.nan, float(values.quantile(0.99)) if n else np.nan, float(jb), p, bins.tolist(), [{"theoretical": float(x), "sample": float(y)} for x, y in zip(expected, ordered)])

    def get_anomalies(self, ticker: str, start: Any, end: Any) -> pd.DataFrame:
        frame = self.get_primary_series(ticker, start, end)
        if frame.empty:
            return pd.DataFrame(columns=["date", "severity", "kind", "value", "suggested_action"])
        events = [asdict(event) for event in detect_5sigma_moves(frame.set_index("date")["returns"])]
        zero_volume = frame.loc[pd.to_numeric(frame["volume"], errors="coerce") <= 0, ["date", "volume"]]
        events.extend({"date": row.date, "severity": "medium", "kind": "zero_volume", "value": float(row.volume), "suggested_action": "exclude date from factor computation"} for row in zero_volume.itertuples())
        return pd.DataFrame(events)


class MissingDataHeatmap:
    def __init__(self) -> None:
        self._last = {}

    def classify_cell_status(self, has_data: bool, is_anomalous: bool) -> str:
        return "yellow" if has_data and is_anomalous else ("green" if has_data else "red")

    def get_heatmap_data(self, tickers: List[str], start: Any, end: Any) -> dict:
        symbols, dates = list(tickers or [])[:500], pd.date_range(start, end, freq="B"); matrix = []; batch = get_ohlcv_batch(symbols, start, end)
        for ticker in symbols:
            raw = batch.get(str(ticker).upper(), pd.DataFrame()); frame = raw.set_index("date") if not raw.empty else pd.DataFrame(); row = []
            for value in dates:
                exists = value in frame.index and pd.notna(frame.loc[value].get("close", np.nan)) if not frame.empty else False
                anomaly = exists and float(frame.loc[value].get("volume", 0)) <= 0
                row.append(self.classify_cell_status(exists, anomaly))
            matrix.append(row)
        output = {"tickers": symbols, "dates": [str(value.date()) for value in dates], "status": matrix, "warning": "truncated to 500 tickers" if len(tickers or []) > 500 else None}; self._last = output; return output

    def get_systematic_exclusion_dates(self, threshold: float = 0.8) -> List[Any]:
        if not self._last:
            return []
        matrix = np.asarray(self._last["status"], dtype=object)
        return [self._last["dates"][index] for index, value in enumerate((matrix == "red").mean(axis=0)) if value >= threshold]

    def get_ticker_exclusion_dates(self, ticker: str) -> List[Any]:
        if not self._last or ticker not in self._last["tickers"]:
            return []
        row = self._last["status"][self._last["tickers"].index(ticker)]
        return [date for date, status in zip(self._last["dates"], row) if status == "red"]
