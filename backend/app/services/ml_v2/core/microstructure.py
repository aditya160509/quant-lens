"""ML V2 microstructure implementation."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable
import base64
import hashlib
import math
import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf, OAS
from sklearn.decomposition import PCA
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import ElasticNet, Lasso, Ridge, LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, roc_auc_score
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from .data_loader import annualization_factor, close_matrix, data_inventory, load_fama_french, load_macro, market_caps, ohlcv_for_symbols, parse_symbols, returns_matrix, sector_map, volume_matrix
from .performance import ThreadPoolExecutor, as_completed, cache_key, cached_ledoit_cov, data_inventory_cached, disk_get, disk_set, equity_from_returns, fast_spearman_ic, max_drawdown, normalize_payload, precompute_date_strings, ridge_fit_fast, sharpe, sortino, vectorized_ic_series, _CONTEXT_CACHE
from .validation import chronological_purged_split, purged_date_folds
from .common import clean_json, compact_records, matrix_records, response, summary
from .estimators import _ohlcv_lower, corwin_schultz_spread, high_low_amihud
from .panel import MLContext, load_context


def run_microstructure(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=12)
    rets, closes, vols = ctx.returns, ctx.closes.reindex(ctx.returns.index), ctx.volumes.reindex(ctx.returns.index)
    # S10 — Vectorized latest signal table: all (T×N) operations done at once
    dollar = (closes * vols).replace(0, np.nan)
    amihud_panel = (rets.abs() / dollar).rolling(21).mean() * 1e8
    logv = np.log(vols.replace(0, np.nan))
    vol_z_panel = (logv - logv.rolling(21).mean()) / logv.rolling(21).std().replace(0, np.nan)
    max_factor_panel = rets.rolling(21).max()
    high52_panel = closes / closes.rolling(252).max().replace(0, np.nan)
    mkt_ret = rets.mean(axis=1)
    ivol_panel = rets.sub(mkt_ret, axis=0).rolling(21).std() * math.sqrt(ctx.annualization)
    # Roll spread: 2*sqrt(max(0, -Cov(dr_t, dr_{t-1}))) per ticker
    roll_cov_panel = rets.rolling(22).cov(rets.shift(1))
    roll_spread_panel = 2.0 * np.sqrt((-roll_cov_panel).clip(lower=0))

    # Snapshot at latest date
    amihud_latest = amihud_panel.iloc[-1]
    vol_z_latest = vol_z_panel.iloc[-1]
    max_factor_latest = max_factor_panel.iloc[-1]
    high52_latest = high52_panel.iloc[-1]
    ivol_latest = ivol_panel.iloc[-1]
    roll_spread_latest = roll_spread_panel.iloc[-1]

    latest = []
    for t in rets.columns:
        # OHLCV-dependent signals still need per-ticker lookup — keep minimal
        ohlcv_t = ctx.ohlcv[ctx.ohlcv["Ticker"] == t] if "Ticker" in ctx.ohlcv.columns else pd.DataFrame()
        hl_amihud = np.nan
        cs_spread = np.nan
        dollar_vol_mom = np.nan
        turnover_rate = np.nan
        if not ohlcv_t.empty:
            ohlcv_t_idx = ohlcv_t.set_index("Date") if "Date" in ohlcv_t.columns else ohlcv_t
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                if col not in ohlcv_t_idx.columns:
                    ohlcv_t_idx[col] = np.nan
            try:
                hl_amihud = float(high_low_amihud(ohlcv_t_idx, window=21).iloc[-1])
            except Exception:
                pass
            try:
                cs_spread = float(corwin_schultz_spread(ohlcv_t_idx, window=21).iloc[-1])
            except Exception:
                pass
            try:
                ohlcv_l = _ohlcv_lower(ohlcv_t_idx)
                dv = (ohlcv_l["close"] * ohlcv_l["volume"]).replace(0, np.nan)
                dollar_vol_mom = float(np.log(dv.rolling(63).mean().iloc[-1] / dv.rolling(252).mean().iloc[-1]))
            except Exception:
                pass
            try:
                v = vols[t]
                turnover_rate = float(v.iloc[-1] / max(v.tail(21).mean(), 1e-8))
            except Exception:
                pass
        latest.append({
            "ticker": t,
            "amihud": float(amihud_latest.get(t, np.nan)),
            "hl_amihud": hl_amihud,
            "roll_spread": float(roll_spread_latest.get(t, np.nan)),
            "corwin_schultz_spread": cs_spread,
            "dollar_vol_momentum": dollar_vol_mom,
            "turnover_rate": turnover_rate,
            "max_factor": float(max_factor_latest.get(t, np.nan)),
            "high_52w_proximity": float(high52_latest.get(t, np.nan)),
            "ivol": float(ivol_latest.get(t, np.nan)),
            "volume_surprise": float(vol_z_latest.get(t, np.nan)),
            "sector": ctx.sectors.get(t, "Unknown"),
        })
    df = pd.DataFrame(latest).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    signals = ["amihud", "hl_amihud", "roll_spread", "corwin_schultz_spread", "max_factor", "high_52w_proximity", "ivol", "volume_surprise", "dollar_vol_momentum", "turnover_rate"]
    aliases = {"52w_high": "high_52w_proximity"}
    requested = (payload or {}).get("signal_families")
    if requested:
        requested = {aliases.get(str(s), str(s)) for s in requested}
        signals = [s for s in signals if s in requested]
    signals = [s for s in signals if s in df.columns]
    leaderboard = []
    fwd = rets.shift(-5).rolling(5).sum()
    try:
        stacked_fwd = fwd.tail(126).stack(future_stack=True).rename("forward_return").reset_index()
    except (TypeError, ValueError):
        stacked_fwd = fwd.tail(126).stack(dropna=False).rename("forward_return").reset_index()
    stacked_fwd.columns = ["date", "ticker", "forward_return"]
    stacked_fwd["date_code"] = pd.factorize(stacked_fwd["date"])[0]
    for sig in signals:
        sig_map = df.set_index("ticker")[sig]
        sig_vals = stacked_fwd["ticker"].map(sig_map).to_numpy(dtype=float)
        vals = vectorized_ic_series(sig_vals, stacked_fwd["forward_return"].to_numpy(dtype=float), stacked_fwd["date_code"].to_numpy())
        leaderboard.append({"signal": sig, "economic_mechanism": _signal_mechanism(sig), "rolling_21d_ic": float(np.nanmean(vals[-21:]) if vals else 0.0), "rolling_63d_ic": float(np.nanmean(vals[-63:]) if vals else 0.0), "ic_ir": float(np.nanmean(vals) / max(np.nanstd(vals), 1e-8)) if vals else 0.0, "ic_decay_ratio": float(abs(np.nanmean(vals[-21:])) / max(abs(np.nanmean(vals[-63:])), 1e-8)) if vals else 0.0})
    monitor = pd.DataFrame({"date": rets.index, "amihud": (rets.abs() / (closes * vols).replace(0, np.nan)).mean(axis=1).rolling(21).mean() * 1e8, "ivol": rets.sub(rets.mean(axis=1), axis=0).rolling(21).std().mean(axis=1)})
    amihud_surface = amihud_time_surface(rets, closes, vols, ctx.sectors)
    return response(
        "10",
        [summary("Signals", len(signals), "count"), summary("Top Signal", max(leaderboard, key=lambda r: abs(r["ic_ir"]))["signal"], "name"), summary("Universe", len(df), "assets")],
        charts={
            "microstructure_ic_leaderboard": leaderboard,
            "amihud_illiquidity_surface": compact_records(df.sort_values("amihud", ascending=False), limit=500),
            "roll_spread_cross_section": compact_records(df[["ticker", "roll_spread", "sector"]], limit=500),
            "max_factor_distribution": compact_records(df[["ticker", "max_factor", "sector"]], limit=500),
            "52_week_high_proximity_heatmap": [{"row": r["sector"], "col": r["ticker"], "value": r["high_52w_proximity"]} for r in latest[:500]],
            "ivol_cross_sectional_sort": _quintile_sort(df, "ivol"),
            "volume_surprise_signal": compact_records(df.sort_values("volume_surprise", ascending=False), limit=500),
            "microstructure_signal_correlation_matrix": matrix_records(df[signals].corr().fillna(0.0)),
            "liquidity_regime_monitor": compact_records(monitor.dropna(), limit=300),
            "signal_backtest": _micro_signal_backtest(df, ctx),
            "corwin_schultz_spread_cross_section": compact_records(df[["ticker", "corwin_schultz_spread", "sector"]].dropna(), limit=500),
            "hl_amihud_vs_standard_amihud": compact_records(df[["ticker", "amihud", "hl_amihud"]].dropna(), limit=500),
            "amihud_time_surface": amihud_surface,
        },
        tables={"microstructure_table": compact_records(df, limit=800), "ic_leaderboard": leaderboard, "amihud_time_surface": amihud_surface},
        meta={"implemented_outputs": 13, "no_tick_data": "Roll/Amihud/HL-Amihud/Corwin-Schultz daily estimators from OHLCV.", "new_signals": ["hl_amihud", "corwin_schultz_spread", "dollar_vol_momentum", "turnover_rate"]},
    )



def _signal_mechanism(sig: str) -> str:
    return {
        "amihud": "liquidity risk premium",
        "hl_amihud": "high-low liquidity risk premium",
        "roll_spread": "implicit transaction cost",
        "corwin_schultz_spread": "Corwin-Schultz bid-ask spread from high-low ratios",
        "max_factor": "lottery demand / retail speculation",
        "high_52w_proximity": "anchoring and momentum leadership",
        "ivol": "idiosyncratic volatility puzzle",
        "volume_surprise": "informed trading proxy",
        "dollar_vol_momentum": "institutional attention and liquidity growth",
        "turnover_rate": "investor attention and speculative activity",
    }.get(sig, "price-volume anomaly")



def amihud_time_surface(rets: pd.DataFrame, closes: pd.DataFrame, vols: pd.DataFrame, sectors: dict[str, str]) -> list[dict[str, Any]]:
    dollar = (closes * vols).replace(0, np.nan)
    amihud = (rets.abs() / dollar).replace([np.inf, -np.inf], np.nan) * 1e8
    rows = []
    for month, frame in amihud.tail(504).groupby(pd.to_datetime(amihud.tail(504).index).to_period("M")):
        vals = frame.mean(axis=0).dropna()
        if vals.empty:
            continue
        sector_vals: dict[str, list[float]] = {}
        for ticker, value in vals.items():
            sector_vals.setdefault(sectors.get(str(ticker), "Unknown"), []).append(float(value))
        for sector, values in sector_vals.items():
            rows.append({"month": str(month), "sector": sector, "amihud": float(np.nanmean(values)), "assets": int(len(values))})
    return rows[-240:]



def _quintile_sort(df: pd.DataFrame, col: str) -> list[dict[str, Any]]:
    out = df.copy()
    out["quintile"] = pd.qcut(out[col].rank(method="first"), 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
    return clean_json(out.groupby("quintile", observed=True)[col].agg(["mean", "count"]).reset_index().to_dict("records"))



def _micro_signal_backtest(df: pd.DataFrame, ctx: MLContext) -> list[dict[str, Any]]:
    rows = []
    signals = [c for c in ["amihud", "hl_amihud", "roll_spread", "corwin_schultz_spread", "max_factor", "high_52w_proximity", "ivol", "volume_surprise", "dollar_vol_momentum", "turnover_rate"] if c in df.columns]
    for sig in signals:
        valid_df = df[["ticker", sig]].replace([np.inf, -np.inf], np.nan).dropna()
        valid_df = valid_df[valid_df["ticker"].isin(ctx.returns.columns)]
        if len(valid_df) < 6:
            rows.append({"signal": sig, "annualized_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "turnover_proxy": 0.0, "valid_assets": int(len(valid_df))})
            continue
        n = max(1, len(valid_df) // 10)
        long = valid_df.nlargest(n, sig)["ticker"]
        short = valid_df.nsmallest(n, sig)["ticker"]
        spread = ctx.returns.reindex(columns=list(long)).mean(axis=1) - ctx.returns.reindex(columns=list(short)).mean(axis=1)
        spread = spread.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        rows.append({
            "signal": sig,
            "annualized_return": float(spread.mean() * ctx.annualization),
            "sharpe": sharpe(spread, ctx.annualization),
            "max_drawdown": max_drawdown(equity_from_returns(spread)),
            "turnover_proxy": 2 * n / max(len(valid_df), 1),
            "valid_assets": int(len(valid_df)),
        })
    return rows

