"""Factors V2 factor data helpers."""

from __future__ import annotations
from typing import Any, Dict
import numpy as np
import pandas as pd
from .data_loader import load_aqr_factor_returns, load_factor_returns
from .common import normalize_factor_name


def factor_returns(payload: Dict[str, Any] | None = None) -> pd.DataFrame:
    model = (
        (payload or {}).get("factor_model")
        or (payload or {}).get("factor_set_id")
        or "ff5_mom"
    )
    include_aqr = bool((payload or {}).get("include_aqr", False))
    aqr_region = str((payload or {}).get("aqr_region", "USA"))
    df = load_factor_returns(model).copy()
    if include_aqr:
        aqr = load_aqr_factor_returns(aqr_region)
        if aqr.empty:
            raise ValueError("Requested AQR region has no observed local factor series")
        df = df.join(aqr, how="outer")
    df = df.drop(columns=[c for c in ["RF"] if c in df.columns]).dropna(how="all")
    if not df.empty:
        df = pd.DataFrame(
            np.ascontiguousarray(df.to_numpy(dtype=np.float64)),
            index=df.index,
            columns=df.columns,
        )
    if payload and payload.get("as_of_date"):
        df = df.loc[: pd.Timestamp(payload["as_of_date"])]
    if payload and payload.get("return_factors"):
        names = payload["return_factors"]
        if not isinstance(names, list) or not names or set(names) - set(df):
            raise ValueError("return_factors must name observed factor columns")
        df = df.loc[:, names]
    if payload and payload.get("start_date"):
        df = df.loc[pd.Timestamp(payload["start_date"]) :]
    return df


def backtest_series(payload=None):
    payload = payload or {}
    factor = normalize_factor_name(payload.get("factor", "momentum_12_1"))
    columns = {
        "value_pb": "HML",
        "value_ep": "HML",
        "quality_roe": "RMW",
        "profitability": "RMW",
        "investment": "CMA",
        "size": "SMB",
        "momentum_12_1": "Mom",
        "momentum_6_1": "Mom",
        "low_vol": "BAB",
    }
    rets = factor_returns(payload)
    col = columns.get(factor, factor)
    if col not in rets:
        raise ValueError(f"No observed factor return column for {factor}: {col}")
    r = rets[col].dropna().tail(int(payload.get("window_days", 756)))
    return {
        "factor": factor,
        "column": col,
        "gross": r,
        "net": r,
        "equity_gross": (1 + r).cumprod(),
        "equity_net": (1 + r).cumprod(),
        "cost_model": {},
        "basis": "published_factor_returns_not_a_stock_backtest",
    }


def run_feature_module(num, payload=None):
    from ..registry import run_feature
    from ..features.inputs import inputs

    fid = str(num).zfill(2)
    allowed = {i["key"] for i in inputs(fid)}
    return run_feature(fid, {k: v for k, v in (payload or {}).items() if k in allowed})
