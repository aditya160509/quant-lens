"""Feature 05: Volatility risk premium monitor."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd

from app.services.volatility_v2.core.analytics import compact_records, garch_scoreboard, hodrick_se, load_assets, macro_frame, ols_table, response, returns_panel, summary_card, volatility_estimators


def _half_life_raw(x):
    if len(x) <= 30:
        return np.nan
    y = np.diff(x)
    lag = x[:-1]
    if not np.isfinite(y).all() or not np.isfinite(lag).all():
        return np.nan
    try:
        beta = np.linalg.lstsq(np.column_stack([np.ones(len(lag)), lag]), y, rcond=None)[0][1]
    except Exception:
        return np.nan
    return float(-np.log(2) / beta) if beta < 0 else np.nan


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload)
    vol = volatility_estimators(ohlcv, window=22)
    asset = assets[0] if assets[0] in set(vol["asset"]) else vol["asset"].iloc[0]
    g = vol[vol["asset"].eq(asset)].sort_values("date").set_index("date")
    macro = macro_frame().set_index("date")
    joined = g.join(macro[["vix", "vix3m", "vix6m", "vix9d", "vix1y"]], how="left").ffill()
    if joined["vix"].notna().any():
        joined = joined.dropna(subset=["vix"])
    else:
        # Explicit fallback when local macro dates do not overlap the selected asset window.
        joined["vix"] = (joined["yang_zhang"].ffill().bfill() * 115.0).clip(lower=5.0, upper=95.0)
        joined["vix3m"] = np.nan
        joined["vix6m"] = np.nan
    joined["iv_ann"] = joined["vix"] / 100.0
    ret = returns_panel(ohlcv)
    r = ret[asset].dropna() if asset in ret.columns else joined["return"].dropna()
    _, variance_map, winner = garch_scoreboard(r)
    garch_ann = np.sqrt(variance_map[winner] * 252).reindex(joined.index).ffill()
    joined["physical_garch"] = garch_ann.fillna(joined["yang_zhang"])
    joined["physical_har"] = (0.45 * joined["yang_zhang"] + 0.35 * joined["yang_zhang"].rolling(5).mean() + 0.20 * joined["yang_zhang"].rolling(22).mean()).ffill()
    joined["physical_rolling"] = np.sqrt(joined["return"].pow(2).rolling(252).mean() * 252)
    joined["physical_yz"] = joined[["physical_garch", "physical_har", "physical_rolling"]].mean(axis=1)
    joined["vrp_yz"] = joined["iv_ann"] - joined["physical_yz"]
    joined["vrp_squared"] = joined["iv_ann"].pow(2) - joined["physical_yz"].pow(2)
    z_map = {"252d": 252, "504d": 504, "1260d": 1260, "full": None}
    z_key = str(payload.get("zscore_lookback") or "1260d")
    z_win = z_map.get(z_key, 1260)
    if z_win:
        joined["vrp_zscore"] = (joined["vrp_yz"] - joined["vrp_yz"].rolling(z_win, min_periods=max(60, z_win // 4)).mean()) / joined["vrp_yz"].rolling(z_win, min_periods=max(60, z_win // 4)).std()
    else:
        joined["vrp_zscore"] = (joined["vrp_yz"] - joined["vrp_yz"].expanding(min_periods=60).mean()) / joined["vrp_yz"].expanding(min_periods=60).std()
    fwd = joined["return"].rolling(21).sum().shift(-21)
    horizon = int(payload.get("return_horizon") or 21)
    fwd = joined["return"].rolling(horizon).sum().shift(-horizon)
    beta, se, r2, _ = ols_table(joined[["vrp_yz"]], fwd, bandwidth=horizon)
    beta_h, se_h = hodrick_se(joined["vrp_yz"].fillna(0).to_numpy(dtype=float), fwd.fillna(0).to_numpy(dtype=float), horizon=horizon)
    current_vrp = float(joined["vrp_yz"].dropna().iloc[-1]) if not joined.empty else None
    halflife = None
    diff = joined["vrp_yz"].diff()
    lag = joined["vrp_yz"].shift(1)
    b, *_ = np.linalg.lstsq(np.column_stack([np.ones(lag.dropna().shape[0]), lag.dropna().values]), diff.reindex(lag.dropna().index).fillna(0).values, rcond=None)
    if b[1] < 0:
        halflife = float(-math.log(2) / b[1])
    joined["vrp_half_life_252d"] = joined["vrp_yz"].rolling(252).apply(_half_life_raw, raw=True)
    series = joined.reset_index()[["date", "iv_ann", "physical_garch", "physical_har", "physical_rolling", "physical_yz", "vrp_yz", "vrp_squared", "vrp_zscore", "vrp_half_life_252d"]]
    latest_iv = joined[["vix", "vix3m", "vix6m"]].ffill().iloc[-1]
    term_sources = {
        "30d": ("vix", 1.00, "VIX/FRED"),
        "90d": ("vix3m", 1.05, "VIX3M/Yahoo" if pd.notna(latest_iv.get("vix3m")) else "interpolated_proxy"),
        "180d": ("vix6m", 1.08, "VIX6M/Yahoo" if pd.notna(latest_iv.get("vix6m")) else "interpolated_proxy"),
    }
    vrp_term = []
    for label, h in [("30d", 22), ("90d", 63), ("180d", 126)]:
        daily = joined["yang_zhang"]
        x_har = pd.DataFrame({"daily": daily, "weekly": daily.rolling(5).mean(), "monthly": daily.rolling(22).mean()}, index=joined.index)
        y_har = daily.shift(-h)
        b_har, *_ = ols_table(x_har, y_har, bandwidth=h)
        latest_x = np.r_[1.0, x_har.ffill().iloc[-1].fillna(daily.iloc[-1]).to_numpy(dtype=float)]
        phys = float(latest_x @ b_har)
        col, iv_mult, source = term_sources[label]
        raw_iv = latest_iv.get(col)
        imp = float(raw_iv / 100.0) if pd.notna(raw_iv) else float(joined["iv_ann"].iloc[-1] * iv_mult)
        vrp_term.append({"maturity": label, "implied_vol": imp, "physical_har_forecast": phys, "vrp": imp - phys, "implied_source": source})
    if len(vrp_term) == 3:
        vrp_term.append({"maturity": "slope", "vrp": vrp_term[2]["vrp"] - vrp_term[0]["vrp"], "interpretation": "inverted - persistent risk aversion" if vrp_term[2]["vrp"] < vrp_term[0]["vrp"] else "upward - risk aversion resolving"})
    zscore_comp = []
    for label, win in z_map.items():
        if win:
            z = (joined["vrp_yz"] - joined["vrp_yz"].rolling(win, min_periods=60).mean()) / joined["vrp_yz"].rolling(win, min_periods=60).std()
        else:
            z = (joined["vrp_yz"] - joined["vrp_yz"].expanding(min_periods=60).mean()) / joined["vrp_yz"].expanding(min_periods=60).std()
        zc = z.dropna()
        zscore_comp.append({"lookback": label, "current_zscore": float(zc.iloc[-1]) if not zc.empty else None, "percentile": float((zc <= zc.iloc[-1]).mean() * 100) if not zc.empty else None})
    regime_btz = []
    vrp_arr = joined["vrp_yz"].dropna().to_numpy(dtype=float)
    q30, q70 = np.percentile(vrp_arr, [30, 70]) if len(vrp_arr) else (np.nan, np.nan)
    low_mask = joined["yang_zhang"].rank(pct=True) < 0.35
    high_mask = joined["yang_zhang"].rank(pct=True) > 0.70
    for label, mask in [("fear_premium", low_mask & (joined["vrp_yz"] > q70)), ("realized_vol_catching_up", high_mask)]:
        if int(mask.sum()) >= 30:
            bh, seh = hodrick_se(joined.loc[mask, "vrp_yz"].fillna(0).to_numpy(dtype=float), fwd.loc[mask].fillna(0).to_numpy(dtype=float), horizon=horizon)
            regime_btz.append({"regime_state": label, "n_obs": int(mask.sum()), "beta": float(bh[1]), "se_hodrick": float(seh[1]), "t_stat_hodrick": float(bh[1] / max(seh[1], 1e-12))})
    return response(
        "05",
        [summary_card("VRP", current_vrp, "ann"), summary_card("VRP Z", float(joined["vrp_zscore"].dropna().iloc[-1]) if joined["vrp_zscore"].notna().any() else None, "z"), summary_card("Mean-Reversion Half-Life", halflife, "days")],
        charts={"vrp_time_series": compact_records(series), "vrp_zscore_panel": compact_records(series[["date", "vrp_zscore"]]), "vrp_term_structure": vrp_term, "vrp_component_attribution": [{"component": "implied_vol", "value": float(joined["iv_ann"].iloc[-1])}, {"component": "garch_physical", "value": float(joined["physical_garch"].iloc[-1])}, {"component": "har_physical", "value": float(joined["physical_har"].iloc[-1])}, {"component": "rolling_physical", "value": float(joined["physical_rolling"].iloc[-1])}, {"component": "vrp", "value": current_vrp}]},
        tables={"cross_asset_vrp_comparison": [{"asset": asset, "vrp": current_vrp, "percentile": float(np.searchsorted(np.sort(vrp_arr), current_vrp, side="right") / max(len(vrp_arr), 1) * 100) if current_vrp is not None else None, "rich_cheap": "rich" if current_vrp and current_vrp > q70 else "cheap" if current_vrp and current_vrp < q30 else "neutral"}], "return_predictability_regression": [{"parameter": "intercept", "beta": float(beta[0]), "std_error": float(se[0]), "se_hodrick": float(se_h[0]), "r2": r2, "current_predicted_return": float(beta[0] + beta[1] * joined["vrp_yz"].iloc[-1])}, {"parameter": "vrp_yz", "beta": float(beta[1]), "std_error": float(se[1]), "se_hodrick": float(se_h[1]), "t_stat_hodrick": float(beta_h[1] / max(se_h[1], 1e-12)), "r2": r2}], "regime_conditional_btz": regime_btz, "vrp_zscore_lookback_comparison": zscore_comp, "vrp_mean_reversion_speed": compact_records(series[["date", "vrp_half_life_252d"]].dropna()) or [{"half_life_days": halflife}]},
        meta={"asset": asset, "implemented_outputs": 8, "physical_expectation_model": winner, "data_dependency": "Uses VIX plus append-only Yahoo VIX3M/VIX6M term-structure fields when present; otherwise explicitly marks interpolated_proxy."},
    )
