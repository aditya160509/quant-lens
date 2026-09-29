from __future__ import annotations

"""
Universe Builder (F6.1, F6.3).

Filter stack interface (market cap, ADV, price, sector, exchange filters).
Time-varying universe viewer with Jaccard overlap analysis.
"""

import uuid
import weakref
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..shared.data_loader import (
    _load_canonical,
    get_all_tickers,
    get_market_cap,
    get_metadata,
    get_ohlcv_batch,
)


_BUILDERS: "weakref.WeakValueDictionary[str, UniverseBuilder]" = weakref.WeakValueDictionary()


@dataclass
class FilterCard:
    filter_type: str
    enabled: bool = True
    parameters: dict = None
    def __post_init__(self) -> None:
        if self.parameters is None: self.parameters = {}


class UniverseBuilder:
    def __init__(self) -> None:
        self.definitions = {}
        self._sector_map: Dict[str, str] = {}
        self._exchange_map: Dict[str, str] = {}
        self._active_asset_class = "equity"

    def _snapshot(self, tickers: Sequence[str], when: Any) -> pd.DataFrame:
        rows = []
        symbols = [str(t).upper() for t in tickers]
        if self._active_asset_class in {"equity", "etf"}:
            batch = get_ohlcv_batch(symbols, when, when)
        else:
            canonical = _load_canonical(self._active_asset_class)
            target = pd.Timestamp(when)
            selected = canonical.loc[
                canonical["ticker"].isin(symbols) & (canonical["date"] <= target)
            ].groupby("ticker", observed=True, sort=False).tail(63)
            batch = {
                str(ticker): group.assign(
                    adjusted_close=group["close"],
                    dollar_volume=pd.to_numeric(group["close"], errors="coerce")
                    * pd.to_numeric(group["volume"], errors="coerce"),
                )
                for ticker, group in selected.groupby("ticker", observed=True)
            }
        cap_map = {}
        try:
            metadata = get_metadata(symbols)
            sector_col = next((c for c in ("gics_sector", "sector") if c in metadata.columns), None)
            exchange_col = next((c for c in ("exchange", "exchange_code", "market") if c in metadata.columns), None)
            self._sector_map = dict(zip(metadata["ticker"], metadata[sector_col])) if sector_col else {}
            self._exchange_map = dict(zip(metadata["ticker"], metadata[exchange_col])) if exchange_col else {}
            cap_map = dict(zip(metadata["ticker"], pd.to_numeric(metadata["marketcap"], errors="coerce"))) if "marketcap" in metadata.columns else {}
        except (FileNotFoundError, ValueError):
            self._sector_map, self._exchange_map = {}, {}
        for ticker in symbols:
            frame = batch.get(ticker, pd.DataFrame())
            if frame.empty: continue
            market_cap = cap_map.get(ticker, np.nan)
            if not np.isfinite(market_cap) and self._active_asset_class in {"equity", "etf"}:
                market_cap = get_market_cap(ticker, when)
            row = frame.iloc[-1].to_dict(); row["ticker"] = ticker; row["market_cap"] = float(market_cap); row["float_market_cap"] = row["market_cap"]; row["adv"] = float(pd.to_numeric(frame["dollar_volume"], errors="coerce").tail(63).mean()); row["sector"] = self._sector_map.get(ticker); row["exchange"] = self._exchange_map.get(ticker); rows.append(row)
        return pd.DataFrame(rows)

    def apply_market_cap_filter(self, tickers: Sequence[str], min_cap: Optional[float], max_cap: Optional[float], date: Any) -> pd.DataFrame:
        frame = self._snapshot(tickers, date); mask = pd.Series(True, index=frame.index)
        if min_cap is not None: mask &= frame["market_cap"] >= float(min_cap)
        if max_cap is not None: mask &= frame["market_cap"] <= float(max_cap)
        return frame.loc[mask.fillna(False)]

    def apply_adv_filter(self, tickers: Sequence[str], min_adv: Optional[float], date: Any) -> pd.DataFrame:
        frame = self._snapshot(tickers, date)
        return frame.loc[frame.get("adv", pd.Series(dtype=float)) >= float(min_adv)] if min_adv is not None else frame

    def apply_price_filter(self, tickers: Sequence[str], min_price: Optional[float], date: Any) -> pd.DataFrame:
        frame = self._snapshot(tickers, date)
        return frame.loc[pd.to_numeric(frame.get("close", pd.Series(dtype=float)), errors="coerce") >= float(min_price)] if min_price is not None else frame

    def apply_sector_filter(self, tickers: Sequence[str], include: Optional[Sequence[str]], exclude: Optional[Sequence[str]]) -> pd.DataFrame:
        symbols = [str(t).upper() for t in tickers]; frame = pd.DataFrame({"ticker": symbols, "sector": [self._sector_map.get(t) for t in symbols]}); sector = frame["sector"]; mask = sector.notna()
        if include: mask &= sector.isin(include)
        if exclude: mask &= ~sector.isin(exclude)
        return frame.loc[mask]

    def apply_exchange_filter(self, tickers: Sequence[str], exchanges: Optional[Sequence[str]]) -> pd.DataFrame:
        symbols = [str(t).upper() for t in tickers]; frame = pd.DataFrame({"ticker": symbols, "exchange": [self._exchange_map.get(t) for t in symbols]})
        if exchanges in (None, [], ["ALL"]): return frame
        allowed = {str(value).upper() for value in exchanges}; return frame.loc[frame["exchange"].astype(str).str.upper().isin(allowed)]

    def apply_float_filter(self, tickers: Sequence[str], percentile_min: Optional[float], percentile_max: Optional[float], date: Any) -> pd.DataFrame:
        frame = self._snapshot(tickers, date); values = pd.to_numeric(frame.get("float_market_cap", pd.Series(dtype=float)), errors="coerce")
        lower = values.quantile(float(percentile_min) / 100.0) if percentile_min is not None else -np.inf; upper = values.quantile(float(percentile_max) / 100.0) if percentile_max is not None else np.inf
        return frame.loc[values.between(lower, upper)]

    def apply_custom_expression(self, tickers: Sequence[str], expression: str, date: Any) -> pd.DataFrame:
        frame = self._snapshot(tickers, date)
        if frame.empty or not expression: return frame
        try: return frame.loc[frame.eval(expression, engine="python")]
        except (ValueError, SyntaxError, NameError): return frame.iloc[0:0]

    def apply_filter_stack(self, filters: List[Any], date: Any) -> pd.DataFrame:
        self._active_asset_class = "equity"
        current = get_all_tickers()
        for raw in filters or []:
            card = raw if isinstance(raw, FilterCard) else FilterCard(raw.get("filter_type", raw.get("type", "")), raw.get("enabled", True), raw.get("parameters", raw))
            if not card.enabled: continue
            p, kind = card.parameters, card.filter_type.lower()
            if kind in {"asset_class", "asset"}:
                self._active_asset_class = str(p.get("asset_class", p.get("value", "equity"))).lower()
                if self._active_asset_class in {"equity", "etf"}:
                    result = pd.DataFrame({"ticker": get_all_tickers()})
                else:
                    result = pd.DataFrame({"ticker": sorted(_load_canonical(self._active_asset_class)["ticker"].unique())})
            elif kind in {"market_cap", "market_cap_bounds"}: result = self.apply_market_cap_filter(current, p.get("min_cap", p.get("min")), p.get("max_cap", p.get("max")), date)
            elif kind in {"adv", "avg_daily_dollar_volume"}: result = self.apply_adv_filter(current, p.get("min_adv", p.get("min")), date)
            elif kind in {"price", "min_price"}: result = self.apply_price_filter(current, p.get("min_price", p.get("min", 0)), date)
            elif kind == "sector": result = self.apply_sector_filter(current, p.get("include"), p.get("exclude"))
            elif kind == "exchange": result = self.apply_exchange_filter(current, p.get("exchanges"))
            elif kind in {"float", "float_market_cap"}: result = self.apply_float_filter(current, p.get("percentile_min"), p.get("percentile_max"), date)
            elif kind in {"custom", "expression"}: result = self.apply_custom_expression(current, p.get("expression", ""), date)
            else: result = pd.DataFrame({"ticker": current})
            current = result["ticker"].astype(str).tolist() if "ticker" in result else []
        return pd.DataFrame({"ticker": current})

    def count_by_filter(self, filters: List[Any], date: Any) -> List[int]:
        current = get_all_tickers(); counts = [len(current)]
        for index in range(len(filters or [])): counts.append(len(self.apply_filter_stack((filters or [])[: index + 1], date)))
        return counts

    def save_universe_definition(self, name: str, filters: List[Any]) -> str:
        identifier = str(uuid.uuid4()); self.definitions[identifier] = {"name": name, "filters": [asdict(item) if isinstance(item, FilterCard) else dict(item) for item in filters or []]}; _BUILDERS[identifier] = self; return identifier


class TimeVaryingUniverse:
    def __init__(self, builder: Optional[UniverseBuilder] = None) -> None: self.builder = builder or UniverseBuilder()
    def get_heatmap_data(self, universe_id: str, start: Any, end: Any) -> dict:
        definition = self.builder.definitions.get(universe_id, {}); dates = pd.date_range(start, end, freq="B"); included = {str(value.date()): self.builder.apply_filter_stack(definition.get("filters", []), value)["ticker"].tolist() for value in dates}; return {"dates": list(included), "tickers": sorted(set().union(*[set(values) for values in included.values()])) if included else [], "included": included}
    def get_entry_exit_events(self, universe_id: str, start: Any, end: Any) -> pd.DataFrame:
        heat = self.get_heatmap_data(universe_id, start, end); previous, rows = set(), []
        for date_key in heat["dates"]:
            current = set(heat["included"].get(date_key, [])); rows.extend({"date": date_key, "ticker": ticker, "event": "entry"} for ticker in current - previous); rows.extend({"date": date_key, "ticker": ticker, "event": "exit"} for ticker in previous - current); previous = current
        return pd.DataFrame(rows)
    def compute_jaccard_similarity(self, universe_a: Any, universe_b: Any, frequency: str = "M") -> pd.Series:
        if isinstance(universe_a, dict) and isinstance(universe_b, dict):
            keys = sorted(set(universe_a) & set(universe_b)); return pd.Series({key: len(set(universe_a[key]) & set(universe_b[key])) / len(set(universe_a[key]) | set(universe_b[key])) if set(universe_a[key]) | set(universe_b[key]) else 1.0 for key in keys})
        a, b = set(universe_a or []), set(universe_b or []); return pd.Series([len(a & b) / len(a | b) if a | b else 1.0])
    def get_stock_sorted_by_market_cap(self, tickers: Sequence[str], date: Any) -> List[str]: return self.builder._snapshot(tickers, date).sort_values("market_cap", ascending=False)["ticker"].tolist()


def get_current_count(universe_id: str, date: Any) -> int:
    builder = _BUILDERS.get(str(universe_id))
    if builder is None: raise KeyError(f"Universe definition '{universe_id}' is not available")
    return len(builder.apply_filter_stack(builder.definitions.get(str(universe_id), {}).get("filters", []), date))
