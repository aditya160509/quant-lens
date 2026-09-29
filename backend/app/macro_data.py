"""
Compatibility macro_data module.

This project previously imported `app.macro_data` from research services.
Some trimmed builds removed that file. This shim keeps API startup stable.
"""

from __future__ import annotations

import pandas as pd


def fetch_series(series_id: str, observation_start: str | None = None) -> pd.Series:
    """
    Best-effort macro series fetch.
    Returns an empty Series when data providers are unavailable.
    """
    try:
        # Late import to avoid hard dependency during app bootstrap.
        from app.services.macro.adapters import fetch_fred_series  # type: ignore

        out = fetch_fred_series(series_id, start=observation_start)
        if isinstance(out, pd.Series):
            return out
        if isinstance(out, pd.DataFrame) and not out.empty:
            return out.iloc[:, 0]
    except Exception:
        pass

    return pd.Series(dtype=float)

