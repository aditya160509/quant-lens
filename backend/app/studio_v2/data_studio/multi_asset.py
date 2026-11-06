"""Multi-asset catalog with normalized contract metadata."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..shared.data_loader import _load_canonical

class MultiAssetCatalog:
    _CLASSES = {
        "equity": {"price_multiplier": 1.0, "calendar": "exchange", "fields": ["open", "high", "low", "close", "volume"]},
        "etf": {"price_multiplier": 1.0, "calendar": "exchange", "fields": ["open", "high", "low", "close", "volume"]},
        "future": {"price_multiplier": "contract_multiplier", "calendar": "exchange", "fields": ["open", "high", "low", "close", "volume", "open_interest", "expiry"]},
        "fx": {"price_multiplier": 1.0, "calendar": "24x5", "fields": ["open", "high", "low", "close", "base_currency", "quote_currency"]},
        "crypto": {"price_multiplier": 1.0, "calendar": "24x7", "fields": ["open", "high", "low", "close", "volume"]},
        "fixed_income": {"price_multiplier": 1.0, "calendar": "business_day", "fields": ["price", "yield", "duration", "spread"]},
        "commodity": {"price_multiplier": "contract_multiplier", "calendar": "exchange", "fields": ["open", "high", "low", "close", "volume", "expiry"]},
    }

    def list_asset_classes(self) -> list[dict[str, Any]]:
        return [{"id": name, **metadata} for name, metadata in self._CLASSES.items()]

    def validate_instrument(self, instrument: dict[str, Any]) -> dict[str, Any]:
        asset_class = str(instrument.get("asset_class", "")).lower()
        if asset_class not in self._CLASSES:
            raise ValueError(f"unsupported asset class '{asset_class}'")
        required = {"symbol", "currency"}
        if asset_class in {"future", "commodity"}:
            required |= {"contract_multiplier", "expiry"}
        missing = required.difference(instrument)
        if missing:
            raise ValueError(f"instrument missing fields: {sorted(missing)}")
        return {**instrument, "asset_class": asset_class, "schema": self._CLASSES[asset_class]}

    def build_futures_universe(self, contracts: Any | None = None,
                               roll_method: str = "active_front_month",
                               target_days: int = 30) -> dict[str, Any]:
        frame = pd.DataFrame(contracts) if contracts is not None else _load_canonical("futures").copy()
        frame = frame.rename(columns={column: str(column).lower() for column in frame.columns})
        method = str(roll_method).lower()
        if method not in {"active_front_month", "ratio_adjusted", "constant_maturity"}:
            raise ValueError("unsupported futures roll method")
        if not 1 <= int(target_days) <= 365:
            raise ValueError("target_days must be between 1 and 365")
        if frame.empty:
            return {"asset_class": "future", "roll_method": method, "instruments": [],
                    "continuous": [], "roll_audit": [],
                    "data_quality": {"input_rows": 0, "usable_rows": 0}}
        required = {"ticker", "date"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(f"futures contracts missing required columns: {missing}")
        settlement_column = next(
            (column for column in ("settlement", "settle") if column in frame.columns),
            None,
        )
        if settlement_column is None and "close" not in frame.columns:
            raise ValueError("futures contracts require settlement, settle, or close prices")
        input_rows = len(frame)
        warnings: list[str] = []
        if settlement_column is not None:
            settlement = pd.to_numeric(frame[settlement_column], errors="coerce")
            close_fallback = (
                pd.to_numeric(frame["close"], errors="coerce")
                if "close" in frame.columns
                else pd.Series(np.nan, index=frame.index)
            )
            missing_settlement = int(settlement.isna().sum())
            frame["close"] = settlement.combine_first(close_fallback)
            price_source = (
                "settlement_with_close_fallback" if missing_settlement else "settlement"
            )
            if missing_settlement:
                warnings.append(
                    f"{missing_settlement} rows lacked settlement and used close when available."
                )
        else:
            frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
            missing_settlement = input_rows
            price_source = "close_fallback"
            warnings.append("Settlement is unavailable; close is used as the roll price.")
        frame["date"] = pd.to_datetime(
            frame["date"], errors="coerce", utc=True
        ).dt.tz_convert(None)
        frame["ticker"] = frame["ticker"].astype(str).str.strip()
        invalid_base = frame["date"].isna() | frame["close"].isna() | frame["ticker"].eq("")
        invalid_base_rows = int(invalid_base.sum())
        frame = frame.loc[~invalid_base].copy()
        before_deduplication = len(frame)
        frame = frame.sort_values(["date", "ticker"], kind="mergesort").drop_duplicates(
            ["date", "ticker"], keep="last"
        )
        duplicate_rows_dropped = before_deduplication - len(frame)
        negative_price_rows = int(frame["close"].lt(0).sum())
        if "expiry" not in frame:
            instruments = sorted(frame["ticker"].astype(str).unique())
            return {
                "asset_class": "future", "roll_method": method,
                "instruments": instruments,
                "continuous": frame.sort_values(["date", "ticker"]).to_dict(orient="records"),
                "roll_audit": [],
                "price_source": price_source,
                "data_quality": {
                    "input_rows": input_rows, "usable_rows": len(frame),
                    "invalid_rows_dropped": invalid_base_rows,
                    "duplicate_rows_dropped": duplicate_rows_dropped,
                    "missing_settlement_rows": missing_settlement,
                    "missing_expiry_rows": input_rows,
                    "expired_rows_dropped": 0,
                    "negative_price_rows": negative_price_rows,
                    "insufficient_contract_dates": 0,
                    "calendar_gap_dates": [],
                },
                "warning": " ".join([
                    "Canonical series are provider-continuous; contract expiry history is unavailable.",
                    *warnings,
                ]),
            }
        frame["expiry"] = pd.to_datetime(
            frame["expiry"], errors="coerce", utc=True
        ).dt.tz_convert(None)
        missing_expiry_rows = int(frame["expiry"].isna().sum())
        if missing_expiry_rows:
            warnings.append(f"{missing_expiry_rows} rows with missing expiry were excluded.")
        frame = frame.dropna(subset=["expiry"])
        frame["days_to_expiry"] = (frame["expiry"] - frame["date"]).dt.days
        expired_rows = int(frame["days_to_expiry"].lt(0).sum())
        frame = frame.loc[frame["days_to_expiry"] >= 0].copy()
        rows, audit = [], []
        insufficient_contract_dates = 0
        for date, daily in frame.groupby("date", sort=True):
            daily = daily.sort_values(["expiry", "ticker"], kind="mergesort")
            if method == "constant_maturity" and len(daily) >= 2:
                left, right = daily.iloc[0], daily.iloc[1]
                span = max(1, int(right.days_to_expiry - left.days_to_expiry))
                right_weight = float(np.clip((target_days - left.days_to_expiry) / span, 0, 1))
                row = left.copy()
                row["close"] = (1 - right_weight) * float(left.close) + right_weight * float(right.close)
                row["contract_weights"] = {str(left.ticker): 1 - right_weight, str(right.ticker): right_weight}
            else:
                if method == "constant_maturity":
                    insufficient_contract_dates += 1
                row = daily.iloc[0].copy()
            rows.append(row.to_dict())
        continuous = pd.DataFrame(rows)
        if continuous.empty:
            warnings.append("No unexpired contracts remained after validation.")
            return {
                "asset_class": "future", "roll_method": method,
                "instruments": [], "continuous": [], "roll_audit": [],
                "price_source": price_source,
                "data_quality": {
                    "input_rows": input_rows, "usable_rows": 0,
                    "invalid_rows_dropped": invalid_base_rows,
                    "duplicate_rows_dropped": duplicate_rows_dropped,
                    "missing_settlement_rows": missing_settlement,
                    "missing_expiry_rows": missing_expiry_rows,
                    "expired_rows_dropped": expired_rows,
                    "negative_price_rows": negative_price_rows,
                    "insufficient_contract_dates": insufficient_contract_dates,
                    "calendar_gap_dates": [],
                },
                "warning": " ".join(warnings),
            }
        continuous = continuous.sort_values("date").reset_index(drop=True)
        calendar_gaps = continuous["date"].diff().dt.days.gt(7)
        calendar_gap_dates = [
            str(pd.Timestamp(value).date())
            for value in continuous.loc[calendar_gaps, "date"].tolist()
        ]
        if calendar_gap_dates:
            warnings.append(
                f"{len(calendar_gap_dates)} calendar gaps longer than seven days were retained."
            )
        if method == "ratio_adjusted" and len(continuous):
            adjusted = pd.to_numeric(continuous["close"], errors="coerce").to_numpy(dtype=float, copy=True)
            roll_locations = np.flatnonzero(
                continuous["ticker"].ne(continuous["ticker"].shift()).to_numpy()
            )[1:]
            for location in reversed(roll_locations.tolist()):
                previous = continuous.iloc[location - 1]
                current = continuous.iloc[location]
                previous_price, current_price = float(previous.close), float(current.close)
                event = {
                    "date": str(pd.Timestamp(current.date).date()),
                    "from": str(previous.ticker), "to": str(current.ticker),
                    "previous_price": previous_price, "current_price": current_price,
                }
                if previous_price > 0 and current_price > 0:
                    adjustment = current_price / previous_price
                    adjusted[:location] *= adjustment
                    event.update({"method": "ratio_back_adjustment", "ratio": adjustment})
                else:
                    adjustment = current_price - previous_price
                    adjusted[:location] += adjustment
                    event.update({"method": "additive_back_adjustment", "amount": adjustment})
                    warnings.append(
                        "A non-positive roll boundary used additive back-adjustment instead of a ratio."
                    )
                audit.append(event)
            continuous["close"] = adjusted
            audit.sort(key=lambda event: event["date"])
        if insufficient_contract_dates:
            warnings.append(
                f"{insufficient_contract_dates} dates had fewer than two contracts; "
                "front-month fallback was used."
            )
        return {"asset_class": "future", "roll_method": method,
                "instruments": sorted(frame["ticker"].astype(str).unique()),
                "continuous": continuous.to_dict(orient="records"), "roll_audit": audit,
                "price_source": price_source,
                "data_quality": {
                    "input_rows": input_rows, "usable_rows": len(frame),
                    "invalid_rows_dropped": invalid_base_rows,
                    "duplicate_rows_dropped": duplicate_rows_dropped,
                    "missing_settlement_rows": missing_settlement,
                    "missing_expiry_rows": missing_expiry_rows,
                    "expired_rows_dropped": expired_rows,
                    "negative_price_rows": negative_price_rows,
                    "insufficient_contract_dates": insufficient_contract_dates,
                    "calendar_gap_dates": calendar_gap_dates,
                },
                "warning": " ".join(dict.fromkeys(warnings)) or None}

    def build_crypto_universe(self, exchange: str | None = None,
                              quote_currency: str | None = None) -> dict[str, Any]:
        frame = _load_canonical("crypto").copy()
        tickers = frame["ticker"].astype(str)
        quote = tickers.str.rsplit("_", n=1).str[-1]
        if quote_currency:
            frame = frame.loc[quote.str.upper() == str(quote_currency).upper()]
        if exchange and "exchange" in frame:
            frame = frame.loc[frame["exchange"].astype(str).str.lower() == str(exchange).lower()]
        return {"asset_class": "crypto", "exchange": exchange, "quote_currency": quote_currency,
                "instruments": sorted(frame["ticker"].astype(str).unique()),
                "observations": int(len(frame))}

    def build_fx_universe(self, settlement_type: str | None = None) -> dict[str, Any]:
        frame = _load_canonical("fx").copy()
        tickers = frame["ticker"].astype(str)
        inferred = np.where(tickers.str.contains("=X", regex=False), "deliverable_spot", "non_deliverable")
        frame["settlement_type"] = inferred
        if settlement_type:
            frame = frame.loc[frame["settlement_type"] == settlement_type]
        return {"asset_class": "fx", "settlement_type": settlement_type,
                "instruments": sorted(frame["ticker"].astype(str).unique()),
                "observations": int(len(frame))}
