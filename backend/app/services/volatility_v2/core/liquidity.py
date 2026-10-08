"""Exact-date USD ADV from explicitly declared source volume units."""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
from .currency import portfolio_prices
from .data_loader import resolve_symbols

SHARE_VOLUME_INSTRUMENTS = {"SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "USO"}


def observed_adv(ohlcv, payload, window=63):
    if window < 21:
        raise ValueError("ADV requires a window of at least 21 observations")
    usd, metadata = portfolio_prices(ohlcv, payload)
    native = ohlcv.pivot(index="Date", columns="Ticker", values="Close").reindex(
        usd.index
    )
    volume = ohlcv.pivot(index="Date", columns="Ticker", values="Volume").reindex(
        usd.index
    )
    declarations = payload.get("volume_units", {})
    if isinstance(declarations, str):
        declarations = json.loads(declarations)
    if not isinstance(declarations, dict):
        raise ValueError("volume_units must be a mapping")
    declared = {
        resolve_symbols([asset])[0]: unit for asset, unit in declarations.items()
    }
    if set(declared) - set(usd.columns) or len(declared) != len(declarations):
        raise ValueError("volume_units must contain unique requested assets")
    dollar = pd.DataFrame(index=usd.index)
    units = {}
    for asset in usd:
        unit = declared.get(
            asset, "shares" if asset in SHARE_VOLUME_INSTRUMENTS else None
        )
        if unit not in ("shares", "base_units", "quote_currency"):
            raise ValueError(
                f"Declare verified volume_units for {asset}; index/crypto volume units cannot be inferred"
            )
        units[asset] = unit
        dollar[asset] = (
            volume[asset] * usd[asset]
            if unit in ("shares", "base_units")
            else volume[asset] * (usd[asset] / native[asset])
        )
        dollar.loc[dollar[asset] <= 0, asset] = np.nan
    adv = dollar.rolling(window, min_periods=window).mean()
    return adv, {
        "window_observations": window,
        "volume_units": units,
        "instrument_currencies": metadata,
        "zero_or_missing_volume": "No ADV estimate; no substitute liquidity value",
        "temporary_impact_coefficient": "User assumption; execution/slippage calibration data are unavailable",
    }
