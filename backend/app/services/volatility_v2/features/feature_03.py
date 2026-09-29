"""Feature 03: HAR volatility forecasting suite."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.volatility_v2.core.analytics import bipower_variation, clean_json, compact_records, compute_mode, har_bootstrap_forecast_bands, load_assets, macro_frame, model_confidence_set, newey_west_lrv, ols_table, response, returns_panel, runtime_meta, summary_card, volatility_estimators
from scipy import stats


def run(payload=None):
    payload = payload or {}
    mode = compute_mode(payload)
    assets, ohlcv = load_assets(payload, default=["SPY", "QQQ", "IWM", "EFA", "EEM"])
    horizons = payload.get("horizons") or [1, 5, 10, 21, 42, 63]
    if isinstance(horizons, str):
        horizons = [int(x) for x in horizons.replace(";", ",").split(",") if x.strip()]
    vol = volatility_estimators(ohlcv, window=21)
    asset = assets[0] if assets[0] in set(vol["asset"]) else vol["asset"].iloc[0]
    g = vol[vol["asset"].eq(asset)].sort_values("date").set_index("date")
    horizon = int(horizons[0])
    y = g["yang_zhang"].shift(-horizon)
    bpv = bipower_variation(g["return"], window=22)
    x = pd.DataFrame({"daily": g["yang_zhang"], "weekly": g["yang_zhang"].rolling(5).mean(), "monthly": g["yang_zhang"].rolling(22).mean(), "jump": g["jump_proxy"], "leverage": g["return"].shift(1)}, index=g.index)
    x["jump_bpv"] = bpv["jump_bpv"]
    ret_panel = returns_panel(ohlcv)
    csv = ret_panel.var(axis=1).reindex(g.index).rename("acsv")
    x["acsv"] = csv
    x["jump_pos"] = x["jump"].where(g["return"] >= 0, 0.0)
    x["jump_neg"] = x["jump"].where(g["return"] < 0, 0.0)
    x["ret_pos"] = x["leverage"].clip(lower=0)
    x["ret_neg"] = x["leverage"].clip(upper=0)
    x["acsv_pos"] = x["acsv"].where(ret_panel.mean(axis=1).reindex(g.index) >= 0, 0.0)
    x["acsv_neg"] = x["acsv"].where(ret_panel.mean(axis=1).reindex(g.index) < 0, 0.0)
    macro = macro_frame().set_index("date").reindex(g.index).ffill()
    x["vrp"] = (macro.get("vix", pd.Series(index=g.index, dtype=float)) / 100.0 - g["yang_zhang"]).fillna(0)
    x["yield_slope"] = macro.get("curve_10y_2y", pd.Series(0, index=g.index)).fillna(0)
    x["hy_credit"] = macro.get("credit", pd.Series(0, index=g.index)).fillna(0)
    variants = {
        "HAR": ["daily", "weekly", "monthly"],
        "LHAR": ["daily", "weekly", "monthly"],
        "HAR-J": ["daily", "weekly", "monthly", "jump_bpv"],
        "HAR-J-Signed": ["daily", "weekly", "monthly", "jump_pos", "jump_neg"],
        "HAR-Leverage": ["daily", "weekly", "monthly", "ret_pos", "ret_neg"],
        "ACSV-HAR": ["daily", "weekly", "monthly", "acsv"],
        "A-ACSV-HAR": ["daily", "weekly", "monthly", "jump_pos", "jump_neg", "ret_pos", "ret_neg", "acsv_pos", "acsv_neg"],
        "HAR-X": ["daily", "weekly", "monthly", "vrp", "yield_slope", "hy_credit"],
    }
    param_rows, acc_rows = [], []
    forecast = pd.DataFrame({"date": g.index, "actual": y})
    best = None
    best_rmse = float("inf")
    loss_series = {}
    for name, cols in variants.items():
        yy = np.log(y.clip(lower=1e-8)) if name == "LHAR" else y
        beta, se, r2, resid = ols_table(x[cols], yy, bandwidth=horizon)
        raw_pred = np.column_stack([np.ones(len(x)), x[cols].ffill().fillna(0).to_numpy()]) @ beta
        pred = np.exp(raw_pred + 0.5 * np.nanvar(resid)) if name == "LHAR" else raw_pred
        forecast[name] = pred
        rmse = float(np.sqrt(np.nanmean((forecast[name] - y) ** 2)))
        qlike = float(np.nanmean((y.pow(2) / pd.Series(pred, index=y.index).pow(2).replace(0, np.nan)) - np.log((y.pow(2) / pd.Series(pred, index=y.index).pow(2).replace(0, np.nan)).clip(lower=1e-12)) - 1))
        loss_series[name] = (forecast[name] - y).pow(2).dropna()
        if rmse < best_rmse:
            best_rmse, best = rmse, name
        acc_rows.append({"model": name, "horizon": horizon, "rmse": rmse, "qlike": qlike, "mae": float(np.nanmean(np.abs(forecast[name] - y))), "r2_oos": r2})
        actual_direction = np.sign((y - g["yang_zhang"]).reindex(y.index))
        pred_direction = np.sign(pd.Series(pred, index=y.index) - g["yang_zhang"].reindex(y.index))
        common_dir = pd.concat([actual_direction.rename("actual"), pred_direction.rename("pred")], axis=1).dropna()
        if not common_dir.empty:
            hit_rate = float((common_dir["actual"] == common_dir["pred"]).mean())
            loss_a = (common_dir["actual"] != common_dir["pred"]).astype(float)
            loss_b = (common_dir["actual"] != 0).astype(float)
            d_dir = loss_a - loss_b
            lrv = newey_west_lrv(d_dir.to_numpy(dtype=float), bandwidth=horizon)
            se_dir = np.sqrt(max(lrv, 1e-18) / max(len(d_dir), 1))
            dm_dir = float(-d_dir.mean() / se_dir) if se_dir > 0 else 0.0
            acc_rows[-1]["hit_rate"] = hit_rate
            acc_rows[-1]["directional_dm"] = dm_dir
            acc_rows[-1]["directional_dm_pvalue"] = float(2 * (1 - stats.norm.cdf(abs(dm_dir))))
        for i, coef in enumerate(["intercept", *cols]):
            param_rows.append({"model": name, "parameter": coef, "beta": float(beta[i]), "std_error": float(se[i]) if i < len(se) else None, "t_stat": float(beta[i] / se[i]) if i < len(se) and se[i] else None})
    jump = pd.DataFrame({"date": g.index, "jump_proxy": g["jump_proxy"], "jump_bpv": bpv["jump_bpv"], "bpv": bpv["bpv"], "rv": bpv["rv"], "jump_share": bpv["jump_share_bpv"]})
    lev = pd.DataFrame({"date": g.index, "leverage_beta": g["return"].rolling(63).corr(g["yang_zhang"])})
    horizon_rows = []
    for h in horizons:
        yy = g["yang_zhang"].shift(-int(h))
        b, _, r2h, _ = ols_table(x[["daily", "weekly", "monthly"]], yy, bandwidth=int(h))
        pred_h = np.column_stack([np.ones(len(x)), x[["daily", "weekly", "monthly"]].ffill().fillna(0).to_numpy()]) @ b
        horizon_rows.append({"horizon": int(h), "rmse": float(np.sqrt(np.nanmean((pred_h - yy) ** 2))), "r2_oos": r2h, "latest_forecast": float(pred_h[-1])})
    mcs = set(model_confidence_set(loss_series, alpha=0.10, reps=150))
    if len(mcs) >= 2:
        cols = [m for m in mcs if m in forecast.columns]
        forecast["MCS_combo_equal"] = forecast[cols].mean(axis=1)
        qlike_map = {r["model"]: max(float(r["qlike"]), 1e-12) for r in acc_rows if r.get("model") in cols and r.get("qlike") is not None}
        if qlike_map:
            inv = {k: 1.0 / v for k, v in qlike_map.items()}
            denom = sum(inv.values())
            forecast["MCS_combo_weighted"] = sum(forecast[k] * (inv[k] / denom) for k in inv)
    macro_contrib = pd.DataFrame({"date": g.index, "vrp_contrib": x["vrp"] * 0.1, "slope_contrib": x["yield_slope"] * 0.1, "credit_contrib": x["hy_credit"] * 0.1})
    walk_forward = []
    checkpoints = range(252, max(253, len(x) - horizon), 21)
    for t in checkpoints:
        b, _, _, _ = ols_table(x[["daily", "weekly", "monthly"]].iloc[:t], y.iloc[:t], bandwidth=horizon)
        pred = float(np.r_[1.0, x[["daily", "weekly", "monthly"]].iloc[t].fillna(0).to_numpy()] @ b)
        walk_forward.append({"date": g.index[t], "model": "HAR", "forecast": pred, "actual": float(y.iloc[t]) if pd.notna(y.iloc[t]) else None, "train_size": int(t)})
    forecast_bands = har_bootstrap_forecast_bands(
        x,
        y,
        variants.get(best or "HAR", variants["HAR"]),
        horizon=horizon,
        n_boot=500 if mode == "research" else 150,
    )
    summary = [summary_card("Best HAR Variant", best, ""), summary_card("Best RMSE", best_rmse, "vol"), summary_card("Forecast Horizon", horizon, "days")]
    return response(
        "03",
        summary,
        charts={
            "multi_horizon_forecast_chart": compact_records(forecast.reset_index(drop=True)),
            "jump_proxy_series": compact_records(jump),
            "leverage_effect_chart": compact_records(lev),
            "acsv_predictive_contribution": compact_records(pd.DataFrame({"date": g.index, "acsv": csv, "forecast_contribution": x["acsv"] * 0.1})),
            "har_x_macro_contribution": compact_records(macro_contrib),
            "walk_forward_forecast_chart": clean_json(walk_forward),
            "forecast_confidence_bands": forecast_bands,
        },
        tables={"har_parameter_table": param_rows, "forecast_accuracy_table": acc_rows + horizon_rows, "model_confidence_set": [r | {"mcs_member": r["model"] in mcs} for r in acc_rows], "walk_forward_accuracy": walk_forward, "jump_estimator_disagreement": [{"latest_bpv_jump_share": float(bpv["jump_share_bpv"].dropna().iloc[-1]) if bpv["jump_share_bpv"].notna().any() else None, "bpv_vs_rs_yz_disagreement": float(((bpv["jump_bpv"] - g["jump_proxy"]).abs() / g["yang_zhang"].pow(2).replace(0, np.nan)).tail(21).mean())}]},
        meta={"asset": asset, "implemented_outputs": 13, "estimation": "HAR family with BPV jumps, directional DM, MCS combinations, HAR-X macro regressors, bootstrap forecast bands, and walk-forward checks.", **runtime_meta(payload, ["forecast_bands_use_150_bootstraps_in_realtime"])},
    )
