"""FIFO tax-lot accounting with short/long-term classification and wash sales."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TaxConfig:
    st_rate: float = 0.35
    lt_rate: float = 0.20
    wash_sale_detection: bool = True

    def validate(self) -> None:
        if not 0 <= self.st_rate <= 1 or not 0 <= self.lt_rate <= 1:
            raise ValueError("tax rates must be between 0 and 1")


class TaxEngine:
    @staticmethod
    def _normalize_trades(trade_log: Any) -> pd.DataFrame:
        trades = pd.DataFrame(trade_log).copy()
        required = {"ticker", "quantity", "price"}
        missing = required - set(trades.columns)
        if missing:
            raise ValueError(f"trade log missing columns: {sorted(missing)}")
        date_column = "fill_date" if "fill_date" in trades.columns else "date"
        if date_column not in trades:
            raise ValueError("trade log requires fill_date or date")
        trades["date"] = pd.to_datetime(trades[date_column], utc=True)
        trades["quantity"] = pd.to_numeric(trades["quantity"], errors="raise")
        trades["price"] = pd.to_numeric(trades["price"], errors="raise")
        return trades.sort_values(["date"]).reset_index(drop=True)

    @staticmethod
    def _classify_st_lt(entry_date: pd.Timestamp, exit_date: pd.Timestamp) -> str:
        return "LT" if (exit_date - entry_date).days >= 365 else "ST"

    def apply_tax(
        self,
        trade_log: Any,
        config: TaxConfig | dict[str, Any],
        pre_tax_equity_curve: Optional[Any] = None,
    ) -> dict[str, Any]:
        cfg = config if isinstance(config, TaxConfig) else TaxConfig(**config)
        cfg.validate()
        trades = self._normalize_trades(trade_log)
        lots: dict[str, list[dict[str, Any]]] = {}
        realized: list[dict[str, Any]] = []

        for trade_index, trade in trades.iterrows():
            ticker = str(trade["ticker"]).upper()
            quantity = float(trade["quantity"])
            price = float(trade["price"])
            date = trade["date"]
            ticker_lots = lots.setdefault(ticker, [])
            if abs(quantity) <= 1e-12:
                continue
            # A trade in the same direction extends inventory. A trade in the
            # opposite direction closes FIFO lots first, then opens any excess.
            if not ticker_lots or np.sign(ticker_lots[0]["quantity"]) == np.sign(quantity):
                ticker_lots.append(
                    {"quantity": quantity, "price": price, "date": date, "trade_index": int(trade_index)}
                )
                continue
            remaining = abs(quantity)
            trade_sign = np.sign(quantity)
            while remaining > 1e-12 and ticker_lots and np.sign(ticker_lots[0]["quantity"]) != trade_sign:
                lot = ticker_lots[0]
                matched = min(remaining, abs(float(lot["quantity"])))
                lot_sign = np.sign(lot["quantity"])
                gain = matched * (price - float(lot["price"])) * lot_sign
                term = self._classify_st_lt(lot["date"], date)
                realized.append(
                    {
                        "trade_id": str(trade.get("trade_id", f"T-{trade_index:06d}")),
                        "ticker": ticker,
                        "entry_date": lot["date"].isoformat(),
                        "sale_date": date.isoformat(),
                        "quantity": matched * lot_sign,
                        "position_type": "long" if lot_sign > 0 else "short",
                        "cost_basis": matched * float(lot["price"]),
                        "proceeds": matched * price,
                        "gain": gain,
                        "term": term,
                        "tax_rate": cfg.lt_rate if term == "LT" else cfg.st_rate,
                        "tax": max(0.0, gain) * (cfg.lt_rate if term == "LT" else cfg.st_rate),
                    }
                )
                lot["quantity"] -= matched * lot_sign
                remaining -= matched
                if abs(lot["quantity"]) <= 1e-12:
                    ticker_lots.pop(0)
            if remaining > 1e-12:
                ticker_lots.append(
                    {"quantity": remaining * trade_sign, "price": price, "date": date, "trade_index": int(trade_index)},
                )

        wash_sales: list[dict[str, Any]] = []
        if cfg.wash_sale_detection:
            purchases = trades.loc[trades["quantity"] > 0]
            for item in realized:
                if item["gain"] >= 0:
                    continue
                sale_date = pd.Timestamp(item["sale_date"])
                matches = purchases.loc[
                    (purchases["ticker"].astype(str).str.upper() == item["ticker"])
                    & (purchases["date"] >= sale_date - timedelta(days=30))
                    & (purchases["date"] <= sale_date + timedelta(days=30))
                    & (purchases["date"] != sale_date)
                ]
                if matches.empty:
                    continue
                replacement = matches.iloc[0]
                disallowed = min(
                    abs(float(item["gain"])),
                    abs(float(item["gain"])) * min(1.0, float(replacement["quantity"]) / item["quantity"]),
                )
                item["wash_sale_disallowed"] = disallowed
                wash_sales.append(
                    {
                        "trade_id": item["trade_id"],
                        "ticker": item["ticker"],
                        "sale_date": sale_date.isoformat(),
                        "repurchase_date": replacement["date"].isoformat(),
                        "loss_disallowed": disallowed,
                    }
                )

        st_gains = sum(max(0.0, item["gain"]) for item in realized if item["term"] == "ST")
        lt_gains = sum(max(0.0, item["gain"]) for item in realized if item["term"] == "LT")
        total_tax = sum(item["tax"] for item in realized)
        total_positive_gains = st_gains + lt_gains
        tax_by_date = pd.Series(
            [item["tax"] for item in realized],
            index=pd.to_datetime([item["sale_date"] for item in realized], utc=True),
            dtype=float,
        ).groupby(level=0).sum() if realized else pd.Series(dtype=float)

        post_tax_curve: dict[str, float] = {}
        if pre_tax_equity_curve is not None:
            pre_tax = pd.Series(pre_tax_equity_curve, dtype=float)
            pre_tax.index = pd.to_datetime(pre_tax.index, utc=True)
            liabilities = tax_by_date.reindex(pre_tax.index, fill_value=0.0).cumsum()
            post_tax = pre_tax - liabilities
            post_tax_curve = {index.isoformat(): float(value) for index, value in post_tax.items()}

        return {
            "config": asdict(cfg),
            "realized_lots": realized,
            "wash_sales": wash_sales,
            "wash_sale_count": len(wash_sales),
            "post_tax_equity_curve": post_tax_curve,
            "summary": {
                "st_gains": st_gains,
                "lt_gains": lt_gains,
                "total_tax_paid": total_tax,
                "effective_tax_rate": total_tax / total_positive_gains if total_positive_gains else 0.0,
            },
        }
