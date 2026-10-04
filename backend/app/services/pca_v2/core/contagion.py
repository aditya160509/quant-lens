"""PCA V2 contagion primitives."""
from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd


def rolling_group_residual_corr(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    window: int = 63,
) -> list[dict]:
    """Rolling daily time series of average pairwise residual correlation per sector."""
    from .analytics import number_like, residual_matrix
    payload = payload or {}
    window = int(number_like((payload or {}).get("residual_window"), window) or window)
    resid = residual_matrix(model)
    sectors = model["sectors"]
    sector_cols: dict[str, list[str]] = {}
    for col in resid.columns:
        s = sectors.get(col, "Unknown")
        sector_cols.setdefault(s, []).append(col)

    rows = []
    for end in range(window, len(resid) + 1):
        sub = resid.iloc[end - window: end]
        date = resid.index[end - 1]
        for sector, cols in sector_cols.items():
            if len(cols) < 2:
                continue
            c = sub[cols].corr().fillna(0.0).to_numpy(dtype=float)
            upper = c[np.triu_indices_from(c, 1)]
            rows.append({
                "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                "sector": sector,
                "avg_residual_corr": float(np.mean(upper)),
            })
    return rows



def residual_contagion(model: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .analytics import eig_sorted, number_like, residual_matrix
    payload = payload or {}
    resid = residual_matrix(model)
    window = int(number_like(payload.get("residual_window"), 63) or 63)
    r = resid.tail(window)
    corr = r.corr().fillna(0.0)
    vals, _ = eig_sorted(corr.to_numpy(dtype=float))
    sectors = model["sectors"]
    group_rows = []
    for sector in sorted(set(sectors.values())):
        cols = [s for s in corr.columns if sectors.get(s) == sector]
        if len(cols) < 2:
            continue
        c = corr.loc[cols, cols].to_numpy(dtype=float)
        group_rows.append({"group": sector, "avg_pairwise_residual_corr": float(c[np.triu_indices_from(c, 1)].mean()), "asset_count": len(cols)})
    pairs = []
    arr = corr.to_numpy(dtype=float)
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pairs.append({"pair": f"{cols[i]} / {cols[j]}", "ticker_a": cols[i], "ticker_b": cols[j], "sector_a": sectors.get(cols[i], "Unknown"), "sector_b": sectors.get(cols[j], "Unknown"), "residual_corr": float(arr[i, j]), "same_sector": sectors.get(cols[i]) == sectors.get(cols[j])})
    pairs = sorted(pairs, key=lambda x: abs(x["residual_corr"]), reverse=True)[:80]
    under = []
    for kk in range(1, min(12, model["returns"].shape[1] - 1, len(model["eigenvalues"])) + 1):
        rr = residual_matrix(model, kk).tail(window).corr().fillna(0.0).to_numpy(dtype=float)
        upper = rr[np.triu_indices_from(rr, 1)]
        ev, _ = eig_sorted(rr)
        under.append({"k": kk, "avg_abs_residual_corr": float(np.mean(np.abs(upper))), "lambda1_residual": float(ev[0])})
    return {"residual_corr": corr, "lambda1_residual": float(vals[0]), "group_rows": group_rows, "pairs": pairs, "under_specification": under}



def residual_tensor_hosvd(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    windows: tuple[int, ...] = (21, 63, 126, 252),
) -> dict[str, Any]:
    """HOSVD/Tucker decomposition of residual-correlation tensors.

    Tensor dimensions are residual group x window length x time. Each cell is
    the average pairwise residual correlation for one sector/group at a rolling
    date. This is the Feature 08 tensor monitor, using actual residual
    correlations rather than the previous K-diagnostic proxy.
    """
    from .analytics import number_like, residual_matrix

    payload = payload or {}
    resid = residual_matrix(model)
    groups: dict[str, list[str]] = {}
    for ticker in resid.columns:
        groups.setdefault(model["sectors"].get(ticker, "Unknown"), []).append(ticker)
    groups = {name: cols for name, cols in groups.items() if len(cols) >= 2}
    if not groups:
        return {"core_records": [], "group_singular_values": [], "window_singular_values": [], "time_singular_values": [], "summary": []}

    max_steps = int(number_like(payload.get("residual_tensor_max_dates"), 80) or 80)
    min_window = min(windows)
    if len(resid) < min_window + 5:
        return {"core_records": [], "group_singular_values": [], "window_singular_values": [], "time_singular_values": [], "summary": []}
    step = max(1, int((len(resid) - min_window) / max(max_steps, 1)))
    date_ends = list(range(min_window, len(resid) + 1, step))[:max_steps]
    group_names = sorted(groups)
    tensor = np.zeros((len(group_names), len(windows), len(date_ends)), dtype=float)

    for t_idx, end in enumerate(date_ends):
        for w_idx, window in enumerate(windows):
            if end < window:
                continue
            sub = resid.iloc[end - window : end]
            for g_idx, group in enumerate(group_names):
                corr = sub[groups[group]].corr().fillna(0.0).to_numpy(dtype=float)
                upper = corr[np.triu_indices_from(corr, 1)]
                tensor[g_idx, w_idx, t_idx] = float(np.mean(upper)) if len(upper) else 0.0

    centered = tensor - tensor.mean(axis=2, keepdims=True)
    ug, sg, _ = np.linalg.svd(centered.reshape(len(group_names), -1), full_matrices=False)
    uw, sw, _ = np.linalg.svd(np.moveaxis(centered, 1, 0).reshape(len(windows), -1), full_matrices=False)
    ut, st, _ = np.linalg.svd(np.moveaxis(centered, 2, 0).reshape(len(date_ends), -1), full_matrices=False)
    rg = min(4, ug.shape[1])
    rw = min(4, uw.shape[1])
    rt = min(6, ut.shape[1])
    core = np.einsum("ia,jb,kc,ijk->abc", ug[:, :rg], uw[:, :rw], ut[:, :rt], centered)

    core_records = []
    for a in range(core.shape[0]):
        for b in range(core.shape[1]):
            for c in range(core.shape[2]):
                core_records.append({"group_mode": a + 1, "window_mode": b + 1, "time_mode": c + 1, "value": float(core[a, b, c])})

    summary = []
    for g_idx, group in enumerate(group_names):
        current = float(tensor[g_idx, :, -1].mean()) if tensor.shape[2] else 0.0
        history = tensor[g_idx].reshape(-1)
        pct = float(np.mean(history <= current) * 100) if len(history) else 0.0
        summary.append({"group": group, "current_avg_residual_corr": current, "percentile": pct})

    return {
        "core_records": core_records,
        "group_singular_values": [{"group": group_names[i], "singular_value": float(v)} for i, v in enumerate(sg[: len(group_names)])],
        "window_singular_values": [{"window": int(windows[i]), "singular_value": float(v)} for i, v in enumerate(sw[: len(windows)])],
        "time_singular_values": [{"mode": i + 1, "singular_value": float(v)} for i, v in enumerate(st[:10])],
        "dates": [str(pd.Timestamp(resid.index[end - 1]).date()) for end in date_ends],
        "summary": sorted(summary, key=lambda r: abs(r["current_avg_residual_corr"]), reverse=True),
    }

