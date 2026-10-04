"""ML V2 composite implementation."""
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
from .common import clean_json, compact_records, date_str, matrix_records, number_like, response, summary
from .estimators import ic_decay_ratio
from .panel import MLContext, load_context, make_feature_panel, numeric_xy


def pairwise_interaction_screen(
    x: pd.DataFrame,
    y: pd.Series,
    *,
    max_pairs: int = 30,
    min_abs_ic: float = 0.015,
) -> list[dict[str, Any]]:
    """Fast pairwise factor interaction screen using cross-sectional Spearman IC."""

    if x.empty or len(x.columns) < 2:
        return []
    cols = list(x.columns)
    rows: list[dict[str, Any]] = []
    yv = pd.to_numeric(y, errors="coerce").replace([np.inf, -np.inf], np.nan)
    for a, b in combinations(cols, 2):
        sa = pd.to_numeric(x[a], errors="coerce").replace([np.inf, -np.inf], np.nan)
        sb = pd.to_numeric(x[b], errors="coerce").replace([np.inf, -np.inf], np.nan)
        za = (sa - sa.mean()) / max(float(sa.std()), 1e-12)
        zb = (sb - sb.mean()) / max(float(sb.std()), 1e-12)
        inter = (za * zb).replace([np.inf, -np.inf], np.nan)
        valid = inter.notna() & yv.notna()
        if valid.sum() < 80:
            continue
        ic = fast_spearman_ic(inter[valid].to_numpy(dtype=float), yv[valid].to_numpy(dtype=float))
        if abs(ic) < min_abs_ic:
            continue
        rows.append(
            {
                "factor_a": a,
                "factor_b": b,
                "interaction": f"{a} x {b}",
                "interaction_ic": ic,
                "abs_ic": abs(ic),
                "direction": "positive" if ic >= 0 else "negative",
                "sample_rows": int(valid.sum()),
            }
        )
    rows.sort(key=lambda r: r["abs_ic"], reverse=True)
    return clean_json(rows[: max(0, int(max_pairs))])



def forward_selection_fama_macbeth(panel: pd.DataFrame, x: pd.DataFrame, y: pd.Series, *, max_factors: int = 8) -> list[dict[str, Any]]:
    """Lightweight forward factor inclusion screen using date-wise cross-sectional slopes."""

    if panel.empty or x.empty or "date" not in panel:
        return []
    selected: list[str] = []
    remaining = list(x.columns)
    rows: list[dict[str, Any]] = []
    dates = pd.to_datetime(panel["date"])
    yv = pd.to_numeric(y, errors="coerce").replace([np.inf, -np.inf], np.nan)
    for step in range(min(max_factors, len(remaining))):
        best: dict[str, Any] | None = None
        for factor in remaining:
            cols = selected + [factor]
            slopes = []
            for _, idx in pd.Series(np.arange(len(panel)), index=dates).groupby(level=0):
                idx_arr = idx.to_numpy(dtype=int)
                if len(idx_arr) < len(cols) + 8:
                    continue
                xx = x.iloc[idx_arr][cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
                yy = yv.iloc[idx_arr].to_numpy(dtype=float)
                valid = np.isfinite(yy)
                if valid.sum() < len(cols) + 8:
                    continue
                xx = xx[valid]
                yy = yy[valid]
                xx = np.column_stack([np.ones(len(xx)), xx])
                try:
                    coef = np.linalg.lstsq(xx, yy, rcond=None)[0][-1]
                    slopes.append(float(coef))
                except Exception:
                    continue
            if len(slopes) < 10:
                continue
            mean_slope = float(np.mean(slopes))
            se = float(np.std(slopes, ddof=1) / math.sqrt(max(len(slopes), 1)))
            t_stat = mean_slope / max(se, 1e-12)
            candidate = {"step": step + 1, "factor": factor, "mean_cross_sectional_slope": mean_slope, "fama_macbeth_t": t_stat, "periods": len(slopes), "selected": abs(t_stat) >= 1.5}
            if best is None or abs(candidate["fama_macbeth_t"]) > abs(best["fama_macbeth_t"]):
                best = candidate
        if best is None:
            break
        rows.append(best)
        selected.append(str(best["factor"]))
        remaining = [f for f in remaining if f != best["factor"]]
        if not bool(best["selected"]):
            break
    return clean_json(rows)



def run_composite_optimizer(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload, min_symbols=12)
    panel, y = make_feature_panel(ctx, horizon=int(number_like((payload or {}).get("prediction_horizon"), 5) or 5))
    x, y = numeric_xy(panel, y)
    factor_cols = list(x.columns)
    if ctx.sectors and "ticker" in panel.columns:
        x_neutralized = x.copy()
        sector_map_for_rows = pd.Series(panel["ticker"].map(lambda t: ctx.sectors.get(str(t), "Unknown")).values, index=x.index)
        for col in factor_cols:
            medians = x[col].groupby(sector_map_for_rows).transform("median")
            x_neutralized[col] = x[col] - medians
    else:
        x_neutralized = x.copy()
    ic_rows = []
    for col in factor_cols:
        ic = fast_spearman_ic(x_neutralized[col].to_numpy(dtype=float), y.to_numpy(dtype=float))
        rolling_ics = []
        for end in range(63, len(y) + 1, 21):
            rolling_ics.append(fast_spearman_ic(x_neutralized[col].iloc[end-63:end].to_numpy(), y.iloc[end-63:end].to_numpy()))
        ic_std = float(np.std(rolling_ics, ddof=1)) if len(rolling_ics) > 1 else 0.0
        ic_rows.append({"factor": col, "ic": ic, "ic_ir": float(np.mean(rolling_ics) / ic_std) if ic_std > 1e-12 else 0.0, "weight_raw": max(ic, 0.0), "ic_decay_ratio": ic_decay_ratio(x_neutralized[col], y)})
    total = sum(r["weight_raw"] for r in ic_rows) or len(ic_rows)
    for r in ic_rows:
        r["composite_weight"] = float((r["weight_raw"] or 1 / len(ic_rows)) / total)
    corr = x_neutralized.corr().fillna(0.0)
    # Gram-Schmidt residualization summary.
    ortho = []
    q = np.empty((len(x), 0))
    for col in factor_cols:
        v = x_neutralized[col].to_numpy(dtype=float)
        for i in range(q.shape[1]):
            v = v - np.dot(v, q[:, i]) * q[:, i]
        norm = np.linalg.norm(v)
        if norm > 1e-12:
            q = np.column_stack([q, v / norm])
        ortho.append({"factor": col, "residual_norm": float(norm), "orthogonal_rank": len(ortho) + 1})
    wf_weights = walkforward_ic_weights(panel, y, factor_cols, window=int(number_like((payload or {}).get("walk_forward_window"), 252) or 252))
    use_interactions = str((payload or {}).get("higher_order_interactions", "true")).lower() not in {"0", "false", "no", "off"}
    interactions = pairwise_interaction_screen(
        x_neutralized,
        y,
        max_pairs=int(number_like((payload or {}).get("max_interactions"), 30) or 30),
        min_abs_ic=float(number_like((payload or {}).get("interaction_min_ic"), 0.015) or 0.015),
    ) if use_interactions else []
    fmb_selection = forward_selection_fama_macbeth(
        panel,
        x_neutralized,
        y,
        max_factors=int(number_like((payload or {}).get("forward_selection_max_factors"), 8) or 8),
    )
    elasso_rows = elastic_lasso_selection(x_neutralized, y)
    dynamic_rows = alphaforge_dynamic_weights(panel, x_neutralized, y, factor_cols)
    decay_alerts = ic_decay_alerts(ic_rows)
    rolling_composite = rolling_composite_ic(panel, x_neutralized, y, ic_rows)
    score = sum(x_neutralized[r["factor"]] * r["composite_weight"] for r in ic_rows)
    panel2 = panel[["date", "ticker", "sector"]].copy()
    panel2["composite_score"] = score
    latest = panel2.groupby("ticker").tail(1).sort_values("composite_score", ascending=False)
    return response(
        "08",
        [summary("Factors", len(factor_cols), "count"), summary("Top IC", max(r["ic"] for r in ic_rows), "spearman"), summary("Signals", len(latest), "assets")],
        charts={
            "ic_weighted_composite_weights": ic_rows,
            "factor_correlation_heatmap": matrix_records(corr),
            "orthogonalization_impact": ortho,
            "walk_forward_weight_stability": wf_weights,
            "composite_signal_distribution": compact_records(latest[["ticker", "sector", "composite_score"]], limit=500),
            "long_short_backtest": _long_short_backtest(panel2, ctx),
            "factor_turnover_table": [{"factor": r["factor"], "turnover_proxy": float(abs(r["composite_weight"] - 1 / len(ic_rows)))} for r in ic_rows],
            "higher_order_interaction_table": interactions,
            "interaction_table": interactions,
            "forward_selection_fama_macbeth": fmb_selection,
            "elastic_lasso_factor_selection": elasso_rows,
            "alphaforge_dynamic_weights": dynamic_rows,
            "ic_decay_alerts": decay_alerts,
            "rolling_composite_ic": rolling_composite,
        },
        tables={"factor_ic_table": ic_rows, "latest_composite_scores": compact_records(latest, limit=500), "orthogonalization_table": ortho, "higher_order_interaction_table": interactions, "forward_selection_fama_macbeth": fmb_selection, "elastic_lasso_factor_selection": elasso_rows, "ic_decay_alerts": decay_alerts},
        meta={"implemented_outputs": 15, "sector_neutralization": "applied", "walk_forward": "rolling_ic_weights", "higher_order_interactions": use_interactions, "dml_ape_integration": "Feature 11 can replace IC weights after API persistence is wired."},
    )



def _long_short_backtest(panel: pd.DataFrame, ctx: MLContext) -> list[dict[str, Any]]:
    rows = []
    for d, g in panel.groupby("date"):
        if len(g) < 10:
            continue
        n = max(1, len(g) // 10)
        long = g.nlargest(n, "composite_score")["ticker"]
        short = g.nsmallest(n, "composite_score")["ticker"]
        if d in ctx.returns.index:
            ret = float(ctx.returns.loc[d, long].mean() - ctx.returns.loc[d, short].mean())
            rows.append({"date": date_str(d), "long_short_return": ret, "equity": None})
    eq = equity_from_returns([r["long_short_return"] for r in rows])
    for r, e in zip(rows, eq):
        r["equity"] = float(e)
    return rows[-300:]



def elastic_lasso_selection(x: pd.DataFrame, y: pd.Series) -> list[dict[str, Any]]:
    if x.empty:
        return []
    model = ElasticNet(alpha=1e-4, l1_ratio=0.65, max_iter=5000).fit(x.fillna(0.0), y.fillna(0.0))
    coefs = np.asarray(model.coef_, dtype=float)
    rows = [{"factor": c, "elastic_lasso_coef": float(v), "selected": bool(abs(v) > 1e-8)} for c, v in zip(x.columns, coefs)]
    rows.sort(key=lambda r: abs(r["elastic_lasso_coef"]), reverse=True)
    return rows



def alphaforge_dynamic_weights(panel: pd.DataFrame, x: pd.DataFrame, y: pd.Series, factor_cols: list[str]) -> list[dict[str, Any]]:
    dates = pd.to_datetime(panel["date"]).drop_duplicates().sort_values().reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for i in range(126, len(dates), max(21, len(dates) // 24 if len(dates) else 21)):
        train_dates = dates.iloc[max(0, i - 126):i]
        mask = pd.to_datetime(panel["date"]).isin(train_dates)
        scores = []
        for col in factor_cols:
            scores.append(max(0.0, fast_spearman_ic(x.loc[mask, col].to_numpy(dtype=float), y.loc[mask].to_numpy(dtype=float))))
        total = sum(scores) or 1.0
        row = {"date": date_str(dates.iloc[i])}
        row.update({col: float(score / total) for col, score in zip(factor_cols, scores)})
        rows.append(row)
    return rows



def ic_decay_alerts(ic_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alerts = []
    for row in ic_rows:
        ratio = float(row.get("ic_decay_ratio") or 0.0)
        if ratio < 0.4:
            alerts.append({"factor": row["factor"], "severity": "high", "message": "short-window IC has decayed materially", "ic_decay_ratio": ratio})
        elif ratio < 0.75:
            alerts.append({"factor": row["factor"], "severity": "watch", "message": "short-window IC is weakening", "ic_decay_ratio": ratio})
    return alerts



def rolling_composite_ic(panel: pd.DataFrame, x: pd.DataFrame, y: pd.Series, ic_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weights = {r["factor"]: float(r.get("composite_weight") or 0.0) for r in ic_rows}
    score = sum(x[c] * weights.get(c, 0.0) for c in x.columns)
    dates = pd.to_datetime(panel["date"])
    df = pd.DataFrame({"date": dates, "score": score, "target": y}).dropna()
    rows = []
    for d, g in df.groupby("date"):
        if len(g) < 8:
            continue
        rows.append({"date": date_str(d), "composite_ic": fast_spearman_ic(g["score"].to_numpy(dtype=float), g["target"].to_numpy(dtype=float)), "observations": int(len(g))})
    return rows[-252:]



def walkforward_ic_weights(panel: pd.DataFrame, y: pd.Series, factor_cols: list[str], window: int = 252, step: int = 21) -> list[dict[str, Any]]:
    """Walk-forward IC weight estimation with rolling refit."""
    rows = []
    dates = panel["date"].drop_duplicates().sort_values().reset_index(drop=True)
    for i in range(window, len(dates), step):
        train_dates = dates.iloc[i - window:i]
        mask = panel["date"].isin(train_dates)
        x_w = panel.loc[mask, factor_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        y_w = y.loc[mask]
        weights = {}
        for col in factor_cols:
            ic = float(stats.spearmanr(x_w[col], y_w).correlation or 0.0)
            weights[col] = max(ic, 0.0)
        total = sum(weights.values()) or 1.0
        row = {"date": date_str(dates.iloc[i])}
        row.update({col: float(v / total) for col, v in weights.items()})
        rows.append(row)
    return rows

