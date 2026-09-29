"""Feature 06: Cross-asset volatility connectedness."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.volatility_v2.core.analytics import DEFAULT_ASSETS, barunik_krehlik_connectedness, compact_records, connectedness_at_risk, fit_var, fit_var_ew, generalized_fevd, load_assets, macro_frame, matrix_records, response, summary_card, volatility_estimators, var_ma_matrices


def run(payload=None):
    payload = payload or {}
    assets, ohlcv = load_assets(payload, default=payload.get("assets") or DEFAULT_ASSETS)
    vol = volatility_estimators(ohlcv, window=21)
    try:
        panel = vol.pivot(index="date", columns="asset", values="yang_zhang").dropna(axis=1, thresh=120).ffill().dropna()
    except ValueError:
        panel = vol.pivot_table(index="date", columns="asset", values="yang_zhang", aggfunc="last").dropna(axis=1, thresh=120).ffill().dropna()
    if panel.shape[1] < 2:
        try:
            panel = vol.pivot(index="date", columns="asset", values="cc").ffill().dropna()
        except ValueError:
            panel = vol.pivot_table(index="date", columns="asset", values="cc", aggfunc="last").ffill().dropna()
    logv = np.log(panel.replace(0, np.nan)).dropna()
    if payload.get("ew_var") or payload.get("var_weighting") == "ew":
        coefs, sigma, lag_order, bic = fit_var_ew(logv, max_lag=int(payload.get("max_lag") or 5), delta=float(payload.get("ew_delta") or 0.99))
        var_method = "ew_var"
    else:
        coefs, sigma, lag_order, bic = fit_var(logv, max_lag=int(payload.get("max_lag") or 5))
        var_method = "ols_var"
    theta = generalized_fevd(coefs, sigma, horizon=int(payload.get("fevd_horizon") or 10))
    theta.index = logv.columns
    theta.columns = logv.columns
    rolling_conn = []
    window = min(252, max(60, len(logv) // 3))
    for i in range(window, len(logv), max(1, len(logv) // 300)):
        try:
            cfs, sig, _, _ = fit_var(logv.iloc[i - window : i], max_lag=min(3, int(payload.get("max_lag") or 5)))
            th = generalized_fevd(cfs, sig, horizon=int(payload.get("fevd_horizon") or 10))
            val = float((th.to_numpy().sum() - np.trace(th.to_numpy())) / len(th) * 100)
        except Exception:
            val = np.nan
        rolling_conn.append({"date": logv.index[i], "connectedness": val, "percentile": None})
    conn_df = pd.DataFrame(rolling_conn)
    if not conn_df.empty:
        conn_df["percentile"] = conn_df["connectedness"].rank(pct=True) * 100
    to = theta.sum(axis=0)
    frm = theta.sum(axis=1)
    spill = pd.DataFrame({"asset": theta.index, "from_spillover": frm.values, "to_spillover": to.reindex(theta.index).values})
    spill["net_spillover"] = spill["to_spillover"] - spill["from_spillover"]
    edges = []
    for r in theta.index:
        for c in theta.columns:
            v = float(theta.loc[r, c])
            if r != c and v >= float(theta.to_numpy().mean()):
                edges.append({"source": c, "target": r, "weight": v})
    nodes = [{"id": a, "net_spillover": float(spill.set_index("asset").loc[a, "net_spillover"]), "size": float(spill.set_index("asset").loc[a, "from_spillover"])} for a in spill["asset"]]
    current = float(conn_df["connectedness"].iloc[-1]) if not conn_df.empty else 0.0
    try:
        bk = barunik_krehlik_connectedness(coefs, sigma)
        freq = [{"band": k, "connectedness": v["connectedness"]} for k, v in bk.items()]
    except Exception:
        freq = []
    cor = connectedness_at_risk(conn_df, macro_frame(), current) or {}
    drivers = sorted(edges, key=lambda e: e["weight"], reverse=True)[:5]
    conn_vals = conn_df["connectedness"].dropna().to_numpy(dtype=float) if not conn_df.empty else np.array([])
    conn_q75 = float(np.percentile(conn_vals, 75)) if len(conn_vals) else np.inf
    alerts = [{"level": "warning", "message": "Connectedness above historical top quartile.", "drivers": drivers}] if not conn_df.empty and current >= conn_q75 else []
    phis = var_ma_matrices(coefs, 22)
    irf = [{"horizon": h, "source": str(logv.columns[j]), "target": str(logv.columns[i]), "response": float(phis[h][i, j])} for h in [1, 5, 10, 21] for i in range(len(logv.columns)) for j in range(len(logv.columns))]
    return response(
        "06",
        [summary_card("Connectedness", current, "pct"), summary_card("Top Transmitter", spill.sort_values("net_spillover", ascending=False)["asset"].iloc[0], ""), summary_card("Asset Count", panel.shape[1], "")],
        charts={"connectedness_index": compact_records(conn_df), "frequency_decomposed_connectedness": freq, "connectedness_at_risk": cor, "spillover_network_graph": {"nodes": nodes, "edges": edges}, "pairwise_fevd_heatmap": matrix_records(theta), "rolling_to_from_decomposition": compact_records(spill), "var_impulse_response": irf},
        tables={"net_spillover_ranking": compact_records(spill.sort_values("net_spillover", ascending=False), limit=200), "connectedness_at_risk": [cor] if cor else [], "connectedness_regime_alert": alerts},
        alerts=alerts,
        meta={"assets": list(panel.columns), "implemented_outputs": 9, "var_lag_order": lag_order, "var_bic": bic, "var_method": var_method, "estimation": "VAR(p)/EW-VAR with BIC lag selection, Pesaran-Shin generalized FEVD, Barunik-Krehlik frequency connectedness, and macro Connectedness-at-Risk."},
    )
