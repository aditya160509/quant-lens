"""Feature 2: Factor Exposure Decomposition."""

from typing import Any, Dict

import numpy as np
import pandas as pd

from app.services.factors_v2.core.analytics import DEFAULT_FACTORS, characteristic_panel, covariance_payload, factor_returns, ols_beta, price_sample, response
from app.services.factors_v2.core.performance import compute_mode, runtime_meta, stable_cache_key


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    mode = compute_mode(payload)
    factors = payload.get("factors", DEFAULT_FACTORS)
    requested_universe = int(payload.get("max_tickers", 120))
    char_payload = dict(payload)
    if mode == "realtime" and requested_universe > 1000:
        char_payload["max_tickers"] = max(100, min(1000, len(payload.get("holdings") or []) or 120))
    chars = characteristic_panel(char_payload)
    holdings = payload.get("holdings") or [{"ticker": t, "weight": 1 / min(len(chars), 30)} for t in chars["Ticker"].head(30)] if not chars.empty else []
    h = pd.DataFrame(holdings).rename(columns={"ticker": "Ticker"})
    if h.empty or chars.empty:
        return response("feature_02", "warning", meta={"warning": "No holdings or characteristic data available"})
    h["weight"] = pd.to_numeric(h.get("weight", 0), errors="coerce").fillna(0)
    h["weight"] = h["weight"] / h["weight"].abs().sum() if h["weight"].abs().sum() else h["weight"]
    merged = h.merge(chars, on="Ticker", how="left")
    char_rows = []
    for f in factors:
        zcol = f"{f}_z"
        if zcol not in merged:
            continue
        exp = float((merged["weight"] * merged[zcol].fillna(0)).sum())
        char_rows.append({"factor": f, "characteristic_exposure": exp, "tilt": _tilt(exp)})

    rets = factor_returns(payload).dropna().tail(int(payload.get("estimation_days", 252)))
    port_proxy = _portfolio_return_history(merged, int(payload.get("estimation_days", 252)))
    betas, se, _ = ols_beta(port_proxy, rets[[c for c in rets.columns if c != "RF"]]) if not rets.empty else (pd.Series(dtype=float), pd.Series(dtype=float), 0)
    ret_rows = [{"factor": k, "return_exposure": float(v), "standard_error": float(se.get(k, np.nan))} for k, v in betas.items()]
    ret_map = {r["factor"]: r["return_exposure"] for r in ret_rows}
    factor_proxy = {"value_pb": "HML", "momentum_12_1": "Mom", "quality_roe": "RMW", "investment": "CMA", "size": "SMB", "low_vol": "Mkt-RF"}
    divergence = []
    for r in char_rows:
        proxy = factor_proxy.get(r["factor"], r["factor"])
        d = r["characteristic_exposure"] - ret_map.get(proxy, 0.0)
        if abs(d) > 0.3:
            divergence.append({"factor": r["factor"], "divergence": d, "message": "Characteristic and return exposure estimates diverge"})
    mandate = set(str(x) for x in payload.get("mandate_factors", []))
    unintended = [
        {
            "factor": row["factor"],
            "active_exposure": row["characteristic_exposure"],
            "threshold": 0.4,
            "mandate_match": row["factor"] in mandate,
            "message": f"{row['factor']} exceeds the 0.4 sigma active exposure threshold and is not in mandate",
        }
        for row in char_rows
        if abs(row["characteristic_exposure"]) > 0.4 and (not mandate or row["factor"] not in mandate)
    ]
    stock_divergence = _stock_level_divergence(merged, factors, char_rows, ret_map, factor_proxy)
    tilt_summary = _plain_language_tilt_summary(char_rows, unintended)
    exposure_budget = _tracking_error_budget(char_rows, rets, factor_proxy)
    heatmap_cols = ["Ticker", "weight"] + [f"{f}_z" for f in factors if f"{f}_z" in merged]
    heatmap_frame = merged[heatmap_cols].copy()
    z_cols = [col for col in heatmap_frame.columns if col.endswith("_z")]
    if z_cols:
        heatmap_frame["missing_factor_values"] = heatmap_frame[z_cols].isna().sum(axis=1).astype(int)
        for col in z_cols:
            heatmap_frame[col] = pd.to_numeric(heatmap_frame[col], errors="coerce").fillna(0.0)
    else:
        heatmap_frame["missing_factor_values"] = 0
    heatmap = heatmap_frame.to_dict("records")
    research_exports = []
    if mode == "research":
        research_exports.append({"export": "animated_rolling_exposure_heatmap", "status": "available_on_demand", "cache_key": stable_cache_key("feature_02", payload, "animated_heatmap")})
    rolling_heatmap = _rolling_exposure_snapshots(payload.get("rebalancing_history"), chars, factors)
    multi_portfolio = _multi_portfolio_comparison(chars, char_rows, factors, payload)
    return response(
        "feature_02",
        "ok",
        summary_cards=char_rows + [{"label": "Tilt Summary", "value": tilt_summary}],
        charts={
            "exposure_bar": char_rows,
            "static_exposure_heatmap": heatmap,
            "rolling_exposure_snapshots": rolling_heatmap,
            "multi_portfolio_comparison": multi_portfolio,
        },
        tables={
            "characteristic_exposures": char_rows,
            "return_exposures": ret_rows,
            "divergence": divergence,
            "unintended_exposures": unintended,
            "multi_portfolio_comparison": multi_portfolio,
            "stock_level_exposure_surprises": stock_divergence,
            "factor_exposure_budget": exposure_budget,
            "tilt_summary": [{"summary": tilt_summary}],
            "research_exports": research_exports,
        },
        alerts=[{"level": "medium", **d} for d in divergence] + [{"level": "high", **u} for u in unintended],
        meta={
            **runtime_meta("feature_02", payload, ["realtime characteristic z-scores restricted to portfolio constituents/top sample above 1000 names"]),
            "methodologies": ["characteristic", "return_based_proxy"],
            "holdings_count": int(len(merged)),
            "requested_universe": requested_universe,
            "computed_universe": int(len(chars)),
            "precompute_policy": "full 5000-stock universe characteristic z-scores are expected from nightly cache",
            "heatmap_missing_values_imputed": int(heatmap_frame["missing_factor_values"].sum()),
            "chart_null_policy": "missing characteristic z-scores are rendered as neutral 0.0 and counted in missing_factor_values",
            "removed_io": ["historical rolling exposures are returned only when actual rebalancing_history snapshots are supplied"],
            "audit_closures": ["plain-language tilt summary", "unintended exposure detector", "stock-level surprise table", "factor tracking-error budget"],
        },
    )


def _tilt(beta: float) -> str:
    mag = abs(beta)
    level = "strong" if mag > 0.7 else "moderate" if mag > 0.4 else "mild" if mag > 0.2 else "neutral"
    return f"{level} {'positive' if beta > 0 else 'negative' if beta < 0 else ''}".strip()


def _portfolio_return_history(merged: pd.DataFrame, estimation_days: int) -> pd.Series:
    prices = price_sample(max(120, len(merged) * 4))
    if prices.empty or not {"Date", "Ticker", "Close"}.issubset(prices):
        return pd.Series(dtype=float)
    close = prices.pivot_table(index="Date", columns="Ticker", values="Close", aggfunc="last").sort_index().tail(estimation_days + 1)
    weights = merged.groupby("Ticker")["weight"].sum().reindex(close.columns).fillna(0.0)
    available = weights[weights.ne(0)].index.intersection(close.columns)
    if not len(available):
        return pd.Series(dtype=float)
    weights = weights.reindex(available)
    weights = weights / weights.abs().sum()
    returns = close[available].pct_change(fill_method=None)
    return returns.mul(weights, axis=1).sum(axis=1, min_count=1).dropna()


def _rolling_exposure_snapshots(history: Any, chars: pd.DataFrame, factors) -> dict[str, Any]:
    if not isinstance(history, list) or not history or chars.empty:
        return {"snapshots": []}
    snapshots = []
    for snapshot in history:
        holdings = pd.DataFrame(snapshot.get("holdings") or []).rename(columns={"ticker": "Ticker"})
        if holdings.empty or "Ticker" not in holdings:
            continue
        holdings["weight"] = pd.to_numeric(holdings.get("weight", 0), errors="coerce").fillna(0.0)
        merged = holdings.merge(chars, on="Ticker", how="left")
        rows = []
        for factor in factors:
            zcol = f"{factor}_z"
            if zcol in merged:
                rows.append({"factor": factor, "exposure": float((merged["weight"] * pd.to_numeric(merged[zcol], errors="coerce").fillna(0)).sum())})
        snapshots.append({"date": snapshot.get("date"), "exposures": rows})
    return {"snapshots": snapshots}


def _plain_language_tilt_summary(rows, unintended) -> str:
    if not rows:
        return "No reliable factor exposures were available from the supplied holdings."
    ranked = sorted(rows, key=lambda row: abs(row.get("characteristic_exposure") or 0), reverse=True)
    lead = ranked[:3]
    parts = [f"{row['factor']} {row['characteristic_exposure']:+.2f} sigma ({row['tilt']})" for row in lead]
    sentence = "Portfolio factor profile: " + ", ".join(parts) + "."
    if unintended:
        sentence += " Dominant unintended exposure: " + f"{unintended[0]['factor']} {unintended[0]['active_exposure']:+.2f} sigma."
    else:
        sentence += " No non-mandate exposure exceeds the 0.4 sigma realtime threshold."
    return sentence


def _stock_level_divergence(merged: pd.DataFrame, factors, char_rows, ret_map, factor_proxy) -> list[dict[str, Any]]:
    if merged.empty:
        return []
    rows = []
    char_map = {row["factor"]: row["characteristic_exposure"] for row in char_rows}
    for factor in factors:
        zcol = f"{factor}_z"
        proxy = factor_proxy.get(factor, factor)
        if zcol not in merged:
            continue
        ret_exp = float(ret_map.get(proxy, 0.0))
        port_exp = float(char_map.get(factor, 0.0))
        subset = merged[["Ticker", "weight", zcol]].dropna()
        if subset.empty:
            continue
        tickers = subset["Ticker"].astype(str).to_numpy()
        weights = subset["weight"].astype(float).to_numpy()
        char_z = subset[zcol].astype(float).to_numpy()
        surprise = char_z - ret_exp
        signals = np.where(surprise > 0.5, "review_long_tilt", np.where(surprise < -0.5, "review_short_tilt", "neutral"))
        rows.extend(
            {
                "ticker": tickers[i],
                "factor": factor,
                "weight": float(weights[i]),
                "characteristic_z": float(char_z[i]),
                "portfolio_factor_exposure": port_exp,
                "return_proxy_exposure": ret_exp,
                "divergence": float(surprise[i]),
                "trade_signal": str(signals[i]),
            }
            for i in range(len(tickers))
        )
    return sorted(rows, key=lambda row: abs(row["divergence"]), reverse=True)[:50]


def _tracking_error_budget(char_rows, rets: pd.DataFrame, factor_proxy) -> list[dict[str, Any]]:
    if not char_rows or rets.empty:
        return []
    cols, exposures, names = [], [], []
    for row in char_rows:
        col = factor_proxy.get(row["factor"], row["factor"])
        if col in rets.columns:
            cols.append(col)
            names.append(row["factor"])
            exposures.append(float(row["characteristic_exposure"]))
    if not cols:
        return []
    cov = covariance_payload(rets[cols], "ledoit_wolf").get("covariance")
    if cov is None or cov.empty:
        return []
    b = np.asarray(exposures, dtype=float)
    cov_arr = cov.values
    marginal = cov_arr @ b
    contrib = b * marginal
    total = float(abs(contrib).sum()) or 1.0
    return [{"factor": name, "tracking_error_contribution": float(contrib[i]), "budget_pct": float(abs(contrib[i]) / total)} for i, name in enumerate(names)]


def _multi_portfolio_comparison(chars: pd.DataFrame, current_rows, factors, payload: Dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {"portfolio": "CURRENT", "factor": row["factor"], "exposure": float(row.get("characteristic_exposure") or 0.0), "source": "configured_holdings"}
        for row in current_rows
    ]
    raw = payload.get("comparison_portfolios") or payload.get("comparison_tickers") or payload.get("benchmarks") or []
    if isinstance(raw, str):
        candidates = [x.strip().upper() for x in raw.replace(";", ",").split(",") if x.strip()]
    elif isinstance(raw, list):
        candidates = [str(x.get("ticker", x)).strip().upper() for x in raw if str(x.get("ticker", x)).strip()]
    else:
        candidates = []
    if not candidates:
        candidates = [str(payload.get("benchmark", "SPY")).upper(), "QQQ", "IWM"]
    by_ticker = chars.set_index("Ticker") if not chars.empty and "Ticker" in chars else pd.DataFrame()
    for ticker in candidates[:5]:
        if ticker in by_ticker.index:
            source_row = by_ticker.loc[ticker]
            if isinstance(source_row, pd.DataFrame):
                source_row = source_row.iloc[0]
            for factor in factors:
                zcol = f"{factor}_z"
                if zcol in source_row:
                    value = pd.to_numeric(source_row[zcol], errors="coerce")
                    rows.append({"portfolio": ticker, "factor": factor, "exposure": float(value) if pd.notna(value) else 0.0, "source": "master_universe_single_name"})
        else:
            rows.append({"portfolio": ticker, "factor": None, "exposure": None, "source": "unavailable_missing_characteristics"})
    return rows
