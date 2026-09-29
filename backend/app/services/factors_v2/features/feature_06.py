"""Feature 6: Factor Crowding Monitor."""

from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy import stats

from app.services.factors_v2.core.analytics import backtest_series, characteristic_panel, empirical_percentile, price_sample, response, valuation_spread
from app.services.factors_v2.core.performance import hhi_fast, rolling_autocorr_1, rolling_std_percentile_kernel, runtime_meta


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    val = valuation_spread(payload)
    bt = backtest_series(payload)
    chars = characteristic_panel(payload)
    r = bt["gross"].dropna()
    r_arr = r.to_numpy(dtype=float)
    ac_path = rolling_autocorr_1(r_arr, 63) if len(r_arr) > 63 else np.asarray([])
    ac_series = np.asarray(ac_path, dtype=float)
    ac1 = float(ac_series[np.isfinite(ac_series)][-1]) if np.isfinite(ac_series).any() else 0.0
    ac_score = empirical_percentile(-pd.Series(ac_series[np.isfinite(ac_series)]), -ac1)
    factor = bt["factor"]
    hhi = None
    sector_hhi = None
    if not chars.empty and factor in chars:
        q = chars[factor].rank(pct=True)
        top = chars[q >= 0.8].copy()
        w = top.get("market_cap", 1).fillna(1)
        hhi = hhi_fast(w.to_numpy(dtype=float))
        if "sector" in top:
            sw = top.groupby("sector")["market_cap"].sum().fillna(0)
            sector_hhi = hhi_fast(sw.to_numpy(dtype=float))
    val_pct = val["rows"][0].get("percentile") if val["rows"] else 50
    crowd_val = 100 - val_pct if factor in {"value_pb", "quality_roe", "profitability"} else val_pct
    hhi_score = min(100.0, (hhi or 0) * 1000)
    spread_proxy = _bid_ask_spread_proxy(chars, price_sample(int(payload.get("max_tickers", 240))), factor)
    spread_score = float(spread_proxy.get("differential_percentile", np.nan))
    metric_values = np.asarray([crowd_val, ac_score, hhi_score, spread_score], dtype=float)
    valid = np.isfinite(metric_values)
    method = str(payload.get("composite_method", "equal_weight")).lower()
    configured_weights = np.asarray(payload.get("composite_weights", [1, 1, 1, 1]), dtype=float)
    if configured_weights.shape != metric_values.shape:
        configured_weights = np.ones_like(metric_values)
    weights = configured_weights * valid
    weights = weights / weights.sum() if weights.sum() else np.ones_like(metric_values) / len(metric_values)
    composite = float(np.nansum(metric_values * weights)) if valid.any() else 50.0
    crash_rows = _bayesian_crash_table(r, composite)
    crash = crash_rows[0]["posterior_mean"] if crash_rows else float((r.rolling(21).sum().shift(-21) < r.rolling(21).sum().quantile(0.1)).mean())
    rows = [
        {"metric": "valuation", "score": crowd_val},
        {"metric": "autocorrelation", "score": ac_score, "raw": ac1},
        {"metric": "concentration_hhi", "score": hhi_score, "raw": hhi},
        {"metric": "bid_ask_spread_proxy", "score": spread_score, "raw": spread_proxy.get("long_short_spread_differential"), "included_in_composite": True, "method": spread_proxy.get("method")},
    ]
    crowd_series = pd.Series(rolling_std_percentile_kernel(r_arr, 63), index=r.index)
    scatter_rows, scatter_meta = _crowding_forward_scatter(r, crowd_series)
    overlay_rows, crash_annotations = _crowding_return_overlay(r, crowd_series)
    league = _crowding_league(payload)
    deleveraging_risk = hhi_score * (spread_score if np.isfinite(spread_score) else 50) / 100
    return response(
        "feature_06",
        "ok",
        summary_cards=[{"label": "Composite Crowding", "value": composite, "unit": "0-100"}, {"label": "1M Crash Probability", "value": crash}],
        charts={
            "metric_breakdown": rows,
            "crowding_timeseries": [{"date": k, "value": v} for k, v in crowd_series.tail(260).items()],
            "crowding_forward_scatter": scatter_rows,
            "crowding_return_overlay": overlay_rows,
            "crash_annotations": crash_annotations,
        },
        tables={
            "crowding_metrics": rows,
            "liquidity_long_short": [
                {"book": "long", **spread_proxy.get("long_book", {})},
                {"book": "short", **spread_proxy.get("short_book", {})},
            ],
            "bid_ask_detail": [spread_proxy],
            "crowding_league": league,
            "crowding_scatter_regression": [scatter_meta],
            "crash_annotations": crash_annotations,
            "crash_probability": crash_rows,
            "deleveraging_risk": [
                {
                    "measure": "deleveraging_risk_proxy",
                    "value": deleveraging_risk,
                    "hhi_score": hhi_score,
                    "bid_ask_spread_score": spread_score if np.isfinite(spread_score) else None,
                    "method": "HHI concentration multiplied by local Roll/Amihud spread percentile",
                }
            ],
        },
        alerts=[{"level": "high", "message": "Crowding composite above threshold", "score": composite}] if composite > float(payload.get("alert_threshold", 70)) else [],
        meta={
            **runtime_meta("feature_06", payload, ["realtime composite uses valuation spread, return autocorrelation, HHI, and local Roll/Amihud spread proxy"]),
            "factor": factor,
            "deleveraging_risk_proxy": deleveraging_risk,
            "composite_metrics": ["valuation", "autocorrelation", "concentration_hhi", "bid_ask_spread_proxy"],
            "alternative_data_removed": "short interest and institutional ownership rows are removed because those feeds are not present locally",
            "bid_ask_method": "Roll 1984 implied spread plus Amihud 2002 illiquidity proxy from local OHLCV/volume data; no external quote fetch",
            "audit_closures": ["bid-ask proxy from local data", "crowding forward-return scatter", "cross-factor crowding league"],
        },
    )


def _bayesian_crash_table(r, current_score):
    rows = []
    crowd_proxy = pd.Series(rolling_std_percentile_kernel(r.to_numpy(dtype=float), 63), index=r.index).dropna()
    for horizon in [21, 63, 126]:
        fwd = r.rolling(horizon).sum().shift(-horizon)
        aligned = crowd_proxy.to_frame("crowd").join(fwd.rename("fwd")).dropna()
        if aligned.empty:
            continue
        lower = max(0, current_score - 15)
        bucket = aligned[aligned["crowd"] >= lower]
        if len(bucket) < 20:
            bucket = aligned[aligned["crowd"] >= max(0, current_score - 30)]
        crash_cut = aligned["fwd"].quantile(0.1)
        crashes = int((bucket["fwd"] <= crash_cut).sum())
        n = int(len(bucket))
        alpha = 1 + crashes
        beta = 9 + max(n - crashes, 0)
        rows.append(
            {
                "horizon_days": horizon,
                "observations": n,
                "crashes": crashes,
                "posterior_mean": float(alpha / (alpha + beta)),
                "credible_low_90": float(stats.beta.ppf(0.05, alpha, beta)),
                "credible_high_90": float(stats.beta.ppf(0.95, alpha, beta)),
                "reliability": "Reliable" if n > 50 else "Marginal" if n >= 20 else "Insufficient Sample Size",
            }
        )
    return rows


def _roll_spread(prices: pd.Series, window: int = 63) -> pd.Series:
    delta = prices.pct_change(fill_method=None)
    cov_series = delta.rolling(window).cov(delta.shift(1))
    return 2 * np.sqrt(np.maximum(0, -cov_series))


def _amihud_illiquidity(returns: pd.Series, volume_usd: pd.Series, window: int = 63) -> pd.Series:
    return (returns.abs() / volume_usd.clip(lower=1.0)).rolling(window).mean() * 1e6


def _bid_ask_spread_proxy(chars: pd.DataFrame, prices: pd.DataFrame, factor: str, window: int = 63) -> Dict[str, Any]:
    if prices.empty or chars.empty or factor not in chars:
        return {"method": "roll_1984_implied_spread_plus_amihud_2002", "status": "insufficient_data"}
    q = chars[factor].rank(pct=True)
    books = {"long": set(chars.loc[q >= 0.8, "Ticker"]), "short": set(chars.loc[q <= 0.2, "Ticker"])}
    close = prices.set_index(["Date", "Ticker"])["Close"].unstack("Ticker").sort_index()
    volume = prices.set_index(["Date", "Ticker"])["Volume"].unstack("Ticker").sort_index()
    results = {}
    for book_name, tickers in books.items():
        book_tickers = [ticker for ticker in tickers if ticker in close.columns][:100]
        if not book_tickers:
            continue
        roll_df = pd.DataFrame({ticker: _roll_spread(close[ticker].dropna(), window) for ticker in book_tickers}).mean(axis=1).dropna()
        vol_usd = close[book_tickers] * volume[book_tickers].fillna(0)
        rets = close[book_tickers].pct_change(fill_method=None)
        amihud = pd.DataFrame({ticker: _amihud_illiquidity(rets[ticker], vol_usd[ticker], window) for ticker in book_tickers}).mean(axis=1).dropna()
        current = float(roll_df.iloc[-1]) if len(roll_df) else None
        results[book_name] = {
            "roll_spread_current": current,
            "roll_spread_percentile": empirical_percentile(roll_df, current) if current is not None else None,
            "roll_spread_velocity_21d": float(roll_df.diff(21).iloc[-1]) if len(roll_df) > 21 else None,
            "amihud_current": float(amihud.iloc[-1]) if len(amihud) else None,
            "amihud_percentile": empirical_percentile(amihud, float(amihud.iloc[-1])) if len(amihud) else None,
            "tickers": len(book_tickers),
        }
    long_spread = results.get("long", {}).get("roll_spread_current")
    short_spread = results.get("short", {}).get("roll_spread_current")
    diff = float((long_spread or 0) - (short_spread or 0))
    pct = 50.0
    if "long" in results and "short" in results:
        long_series = pd.DataFrame({ticker: _roll_spread(close[ticker].dropna(), window) for ticker in [t for t in books["long"] if t in close.columns][:100]}).mean(axis=1)
        short_series = pd.DataFrame({ticker: _roll_spread(close[ticker].dropna(), window) for ticker in [t for t in books["short"] if t in close.columns][:100]}).mean(axis=1)
        differential = (long_series - short_series).dropna()
        if len(differential):
            pct = empirical_percentile(differential, float(differential.iloc[-1]))
    return {"long_book": results.get("long", {}), "short_book": results.get("short", {}), "long_short_spread_differential": diff, "differential_percentile": pct, "crowding_signal": diff > 0, "method": "roll_1984_implied_spread_plus_amihud_2002"}


def _crowding_forward_scatter(r: pd.Series, crowd_series: pd.Series):
    fwd = r.rolling(63).sum().shift(-63)
    aligned = pd.concat([crowd_series.rename("crowding"), fwd.rename("forward_63d_return")], axis=1).dropna()
    if len(aligned) < 30:
        return [], {"status": "insufficient_data", "observations": int(len(aligned))}
    x = aligned["crowding"].to_numpy(dtype=float)
    y = aligned["forward_63d_return"].to_numpy(dtype=float)
    X = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ coef
    r2 = float(1 - np.sum((y - yhat) ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-12))
    rows = aligned.tail(500).reset_index().rename(columns={"index": "date"}).to_dict("records")
    return rows, {"slope": float(coef[1]), "intercept": float(coef[0]), "r_squared": r2, "observations": int(len(aligned))}


def _crowding_return_overlay(r: pd.Series, crowd_series: pd.Series):
    fwd = r.rolling(63).sum().shift(-63)
    aligned = pd.concat([crowd_series.rename("crowding"), fwd.rename("forward_63d_return"), r.rolling(21).sum().rename("trailing_21d_return")], axis=1).dropna()
    if aligned.empty:
        return [], []
    crash_cut = float(aligned["forward_63d_return"].quantile(0.1))
    event_rows = []
    out = []
    for idx, row in aligned.tail(520).iterrows():
        crowding = float(row["crowding"])
        forward = float(row["forward_63d_return"])
        crash_flag = bool(crowding >= 70 and forward <= crash_cut)
        event = "HIGH CROWDING / WEAK FORWARD RETURN" if crash_flag else None
        item = {
            "date": str(pd.Timestamp(idx).date()),
            "crowding": crowding,
            "forward_63d_return": forward,
            "trailing_21d_return": float(row["trailing_21d_return"]),
            "crash_flag": crash_flag,
            "event": event,
        }
        out.append(item)
        if crash_flag:
            event_rows.append({**item, "threshold": crash_cut})
    return out, event_rows[-20:]


def _crowding_league(payload: Dict[str, Any]) -> list[dict[str, Any]]:
    factors = payload.get("factors") or ["value_pb", "momentum_12_1", "quality_roe", "low_vol", "size"]
    rows = []
    for factor in factors[:12]:
        sub = {**payload, "factor": factor}
        val = valuation_spread(sub)
        bt = backtest_series(sub)
        r = bt["gross"].dropna()
        if r.empty:
            continue
        crowd_path = pd.Series(rolling_std_percentile_kernel(r.to_numpy(dtype=float), 63), index=r.index).dropna()
        score = float(crowd_path.iloc[-1]) if len(crowd_path) else None
        rows.append({"factor": factor, "crowding_score": score, "change_1m": float(crowd_path.diff(21).iloc[-1]) if len(crowd_path) > 21 else None, "change_3m": float(crowd_path.diff(63).iloc[-1]) if len(crowd_path) > 63 else None, "valuation_percentile": val["rows"][0].get("percentile") if val.get("rows") else None})
    return sorted(rows, key=lambda row: row.get("crowding_score") if row.get("crowding_score") is not None else -1, reverse=True)
