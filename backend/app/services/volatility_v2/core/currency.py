"""Observed USD portfolio returns; currency declarations never come from suffix guesses."""

from __future__ import annotations
import json
from functools import lru_cache
import numpy as np
import pandas as pd
from . import data_loader

# Explicit quote denominations for the shipped default instruments.
USD_INSTRUMENTS = {
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "TLT",
    "GLD",
    "USO",
    "BTC_USD",
    "ETH_USD",
    "^GSPC",
}
FX_DAILY = data_loader.BACKEND_DATA / "canonical/fx_daily.parquet"


@lru_cache(maxsize=2)
def _fx(version):
    frame = pd.read_parquet(version[0], columns=["Ticker", "Date", "Close"])
    frame["Date"] = pd.to_datetime(frame.Date, errors="raise")
    if frame.duplicated(["Ticker", "Date"]).any() or not frame.Close.gt(0).all():
        raise ValueError("FX observations must be unique and positive")
    return frame.pivot(index="Date", columns="Ticker", values="Close").sort_index()


def quote_currencies(assets, payload):
    raw = payload.get("quote_currencies", {})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("quote_currencies must be a JSON object") from exc
    if not isinstance(raw, dict):
        raise ValueError("quote_currencies must be a mapping")
    declared = {
        data_loader.resolve_symbols([key])[0]: value for key, value in raw.items()
    }
    currencies = {
        asset: declared.get(asset, "USD" if asset in USD_INSTRUMENTS else None)
        for asset in assets
    }
    missing = [asset for asset, currency in currencies.items() if currency is None]
    if missing:
        raise ValueError(
            "Declare observed quote_currencies for: "
            + ", ".join(missing)
            + "; suffix/financial-currency inference is prohibited"
        )
    for asset, value in currencies.items():
        if not isinstance(value, str) or not (
            value in ("GBp", "ZAc", "ILA")
            or len(value) == 3
            and value.isalpha()
            and value.isupper()
        ):
            raise ValueError(f"Invalid quote currency for {asset}")
    if set(declared) - set(assets):
        raise ValueError(
            "quote_currencies contains symbols outside the requested portfolio"
        )
    return currencies


def portfolio_prices(ohlcv, payload):
    if payload.get("base_currency", "USD") != "USD":
        raise ValueError("Portfolio analytics currently support USD base currency only")
    prices = ohlcv.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    assets = list(prices.columns)
    currencies = quote_currencies(assets, payload)
    fx = None
    meta = []
    for asset, currency in currencies.items():
        major, unit = {
            "GBp": ("GBP", 0.01),
            "ZAc": ("ZAR", 0.01),
            "ILA": ("ILS", 0.01),
        }.get(currency, (currency, 1.0))
        if major == "USD":
            rate = pd.Series(unit, index=prices.index)
            ticker = None
        else:
            if fx is None:
                fx = _fx(data_loader.file_version(FX_DAILY))
                end = data_loader.cutoff()
                if end is not None:
                    fx = fx.loc[:end]
            direct, inverse = f"{major}USD=X", f"USD{major}=X"
            ticker = direct if direct in fx else inverse if inverse in fx else None
            if ticker is None:
                raise ValueError(f"No observed USD exchange rate for {currency}")
            rate = (
                fx[ticker].reindex(prices.index) * unit
                if ticker == direct
                else unit / fx[ticker].reindex(prices.index)
            )
            if (prices[asset].notna() & rate.isna()).any():
                missing = int((prices[asset].notna() & rate.isna()).sum())
                raise ValueError(
                    f"Missing exact-date {currency}/USD observations for {asset} ({missing} price dates); no stale fill is allowed"
                )
        prices[asset] = prices[asset] * rate
        meta.append(
            {
                "asset": asset,
                "quote_currency": currency,
                "base_currency": "USD",
                "observed_fx_ticker": ticker,
                "quote_unit_scale": unit,
            }
        )
    return prices, meta


def portfolio_returns(ohlcv, payload, log_returns=True):
    prices, metadata = portfolio_prices(ohlcv, payload)
    returns = (
        np.log(prices / prices.shift(1))
        if log_returns
        else prices.pct_change(fill_method=None)
    )
    returns = returns.replace([np.inf, -np.inf], np.nan)
    complete = returns.dropna(how="any")
    if complete.empty:
        raise ValueError("No complete aligned USD returns for the requested portfolio")
    return complete, {
        "base_currency": "USD",
        "instrument_currencies": metadata,
        "return_convention": "log" if log_returns else "simple",
        "excluded_incomplete_return_dates": len(returns) - len(complete),
        "price_adjustment": "Observed Close field; total-return/corporate-action adjustment not guaranteed by source metadata",
    }
