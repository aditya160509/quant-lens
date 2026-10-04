"""PCA V2 regimes primitives."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd


def rolling_pca_metrics(payload: dict[str, Any] | None = None, windows: tuple[int, ...] = (21, 63, 126, 252)) -> pd.DataFrame:
    from .analytics import covariance_estimator, eig_sorted, load_context, subspace_principal_angles
    ctx = load_context(payload)
    rets = ctx["returns"]
    rows: list[dict[str, Any]] = []
    for w in windows:
        if len(rets) < w + 5:
            continue
        step = max(1, int(w // 8))
        prior_vec = None
        prior_loading_matrix = None
        series: list[float] = []
        k_used = int(ctx.get("payload", {}).get("k") or 3)
        for end in range(w, len(rets) + 1, step):
            sample = rets.iloc[end - w: end]
            cov, _ = covariance_estimator(sample, (payload or {}).get("covariance_estimator", "ledoit_wolf"))
            vals, vecs = eig_sorted(cov)
            pc1 = float(vals[0] / max(vals.sum(), 1e-12))
            cos = abs(float(vecs[:, 0] @ prior_vec)) if prior_vec is not None else 1.0
            # Principal angles between consecutive loading subspaces
            if prior_loading_matrix is not None and prior_loading_matrix.shape == vecs[:, :k_used].shape:
                angles = subspace_principal_angles(prior_loading_matrix, vecs[:, :k_used])
                max_principal_angle = float(np.degrees(angles[-1]))
            else:
                max_principal_angle = 0.0
            series.append(pc1)
            row = {"date": sample.index[-1], "window": w, "pc1_share": pc1, "pc1_cosine_stability": cos, "effective_dimensions": float((vals.sum() ** 2) / max(np.sum(vals ** 2), 1e-12)), "eigen_ratio_k": int(np.argmax(vals[:-1] / np.maximum(vals[1:], 1e-12)) + 1) if len(vals) > 2 else 1, "max_principal_angle_deg": max_principal_angle}
            for pc_idx in range(min(5, len(vals))):
                row[f"eigenvalue_pc{pc_idx + 1}"] = float(vals[pc_idx])
                if prior_loading_matrix is not None and pc_idx < prior_loading_matrix.shape[1]:
                    row[f"cosine_pc{pc_idx + 1}"] = abs(float(vecs[:, pc_idx] @ prior_loading_matrix[:, pc_idx]))
                else:
                    row[f"cosine_pc{pc_idx + 1}"] = 1.0
            rows.append(row)
            prior_vec = vecs[:, 0]
            prior_loading_matrix = vecs[:, :k_used]
        if series:
            arr = np.asarray(series)
            mean = float(arr.mean())
            std = float(arr.std(ddof=1) or 1.0)
            for r in rows:
                if r["window"] == w:
                    r["pc1_zscore"] = float((r["pc1_share"] - mean) / std)
    return pd.DataFrame(rows)



def cusum_table(series: pd.Series) -> list[dict[str, Any]]:
    x = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if len(x) < 5:
        return []
    centered = x - x.mean()
    s = x.std(ddof=1) or 1.0
    vals = np.abs(np.cumsum(centered)) / (s * math.sqrt(len(x)))
    from statsmodels.stats.diagnostic import breaks_cusumolsresid
    statistic, pvalue, critical = breaks_cusumolsresid(centered.to_numpy() if isinstance(centered,pd.Series) else centered, ddof=1)
    return [{"global_statistic":float(statistic), "global_pvalue":float(pvalue), "index": i, "cusum": float(v), "critical_90": 1.224, "critical_95": 1.358, "critical_99": 1.628, "break": bool(v > 1.358)} for i, v in enumerate(vals)]



def bai_perron_breakpoints(
    series: pd.Series,
    max_breaks: int = 3,
    min_segment: int = 20,
) -> list[dict[str, Any]]:
    """Dynamic-programming multiple mean-break search with BIC selection."""

    x = pd.to_numeric(series, errors="coerce").dropna()
    n = len(x)
    if n < min_segment * 2:
        return []
    values = x.to_numpy(dtype=float)

    if min_segment < 2 or max_breaks < 0:
        raise ValueError("Break selection requires min_segment >= 2 and max_breaks >= 0")
    prefix = np.r_[0., np.cumsum(values)]
    squares = np.r_[0., np.cumsum(values**2)]
    def sse(i, j):
        return max(float(squares[j]-squares[i]-(prefix[j]-prefix[i])**2/(j-i)),0.)
    max_segments = min(max_breaks+1,n//min_segment)
    costs = np.full((max_segments+1,n+1), np.inf)
    prior = np.full((max_segments+1,n+1), -1, dtype=int)
    costs[0,0] = 0.
    for segments in range(1,max_segments+1):
        for end in range(segments*min_segment,n+1):
            for start in range((segments-1)*min_segment,end-min_segment+1):
                value = costs[segments-1,start]+sse(start,end)
                if value<costs[segments,end]:
                    costs[segments,end]=value;prior[segments,end]=start
    candidates=[]
    for segments in range(1,max_segments+1):
        end=n;points=[]
        for current in range(segments,0,-1):
            start=prior[current,end]
            if start>0:points.append(int(start))
            end=start
        candidates.append((segments-1,sorted(points),float(costs[segments,n])))
    scored = []
    for k, points, loss in candidates:
        bic = n * math.log(max(loss / n, 1e-12)) + (k + 1) * math.log(n)
        scored.append((bic, k, points, loss))
    bic, k, points, loss = min(scored, key=lambda item: item[0])
    rows = []
    all_points = [0] + points + [n]
    for idx, bp in enumerate(points):
        before = values[all_points[idx] : bp]
        after = values[bp : all_points[idx + 2]]
        rows.append(
            {
                "break_index": int(bp),
                "break_date": str(pd.Timestamp(x.index[bp]).date()) if hasattr(x.index[bp], "date") else str(x.index[bp]),
                "mean_before": float(before.mean()) if len(before) else None,
                "mean_after": float(after.mean()) if len(after) else None,
                "selected_break_count": int(k),
                "bic": float(bic),
                "segment_sse": float(loss),
            }
        )
    return rows



def tensor_hosvd(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    windows: tuple[int, ...] = (21, 63, 126, 252),
) -> dict[str, Any]:
    """HOSVD/Tucker decomposition of eigenvalue-share tensor K x W x T."""
    from .analytics import covariance_estimator, eig_sorted

    payload = payload or {}
    rets = model.get("original_returns",model["returns"])
    k = min(int(payload.get("tensor_k") or model["k"] or 3), 8, rets.shape[1])
    step = int(payload.get("tensor_step") or 21)
    time_points = []
    tensors = []
    max_w = max(windows)
    for end in range(max_w, len(rets) + 1, step):
        date = rets.index[end - 1]
        slice_kw = np.zeros((k, len(windows)))
        for wi, w in enumerate(windows):
            sample = rets.iloc[end - w : end]
            cov, _ = covariance_estimator(sample, (payload or {}).get("covariance_estimator", "ledoit_wolf"))
            vals, _ = eig_sorted(cov)
            total = max(float(vals.sum()), 1e-12)
            slice_kw[:, wi] = vals[:k] / total
        tensors.append(slice_kw)
        time_points.append(date)
    if not tensors:
        return {"core_records": [], "factor_singular_values": [], "window_singular_values": [], "time_singular_values": []}
    arr = np.stack(tensors, axis=2)  # K x W x T
    unfold_factor = arr.reshape(k, -1)
    unfold_window = np.moveaxis(arr, 1, 0).reshape(len(windows), -1)
    unfold_time = np.moveaxis(arr, 2, 0).reshape(len(time_points), -1)
    uf, sf, _ = np.linalg.svd(unfold_factor, full_matrices=False)
    uw, sw, _ = np.linalg.svd(unfold_window, full_matrices=False)
    ut, st, _ = np.linalg.svd(unfold_time, full_matrices=False)
    rf = min(3, uf.shape[1])
    rw = min(3, uw.shape[1])
    rt = min(4, ut.shape[1])
    core = np.einsum("ia,jb,kc,ijk->abc", uf[:, :rf], uw[:, :rw], ut[:, :rt], arr)
    core_records = []
    for a in range(core.shape[0]):
        for b in range(core.shape[1]):
            for c in range(core.shape[2]):
                core_records.append({"factor_mode": a + 1, "window_mode": b + 1, "time_mode": c + 1, "value": float(core[a, b, c])})
    return {
        "core_records": core_records,
        "factor_singular_values": [{"mode": i + 1, "singular_value": float(v)} for i, v in enumerate(sf[:8])],
        "window_singular_values": [{"mode": i + 1, "singular_value": float(v)} for i, v in enumerate(sw[: len(windows)])],
        "time_singular_values": [{"mode": i + 1, "singular_value": float(v)} for i, v in enumerate(st[:10])],
        "dates": [str(pd.Timestamp(d).date()) for d in time_points],
    }



def rolling_loading_evolution(
    payload: dict[str, Any] | None = None,
    window: int = 126,
    step: int = 21,
    pc_idx: int = 0,
    max_dates: int = 100,
) -> list[dict[str, Any]]:
    """Compute PC loading vector at each rolling date for heatmap / animation.

    Returns (date, ticker, loading) triples, downsampled to max_dates windows.

    Args:
        payload: Standard payload dict.
        window: Rolling window in trading days.
        step: Step between windows (controls resolution vs payload size).
        pc_idx: Which PC to track (0 = PC1, 1 = PC2, ...).
        max_dates: Hard cap on number of time slices returned.
    """
    from .analytics import covariance_estimator, eig_sorted, load_context
    ctx = load_context(payload)
    rets = ctx["returns"]
    estimator = (payload or {}).get("covariance_estimator", "ledoit_wolf")
    rows: list[dict[str, Any]] = []
    dates_seen = 0
    prior_loading = None
    for end in range(window, len(rets) + 1, step):
        if dates_seen >= max_dates:
            break
        sample = rets.iloc[end - window: end]
        cov, _ = covariance_estimator(sample, estimator)
        _, vecs = eig_sorted(cov)
        loading_vec = vecs[:, pc_idx]
        if prior_loading is not None and loading_vec @ prior_loading < 0:
            loading_vec = -loading_vec
        prior_loading = loading_vec.copy()
        date_str = str(pd.Timestamp(sample.index[-1]).date())
        for i, ticker in enumerate(rets.columns):
            rows.append({"date": date_str, "ticker": ticker, "loading": float(loading_vec[i])})
        dates_seen += 1
    return rows



def pc1_percentile_rank(
    rolling_df: pd.DataFrame,
    history_window: int = 252,
) -> dict[str, Any]:
    """Given the output of rolling_pca_metrics(), compute current PC1 share
    as a percentile of its recent history, per rolling window length.

    Args:
        rolling_df: DataFrame from rolling_pca_metrics().
        history_window: Number of most-recent observations for percentile.

    Returns:
        Dict mapping window_days -> {current_pc1_share, percentile_rank, alert}.
        alert is "HIGH" (>=80th pct), "LOW" (<=20th pct), or "NORMAL".
    """
    result: dict[str, Any] = {}
    if rolling_df.empty or "pc1_share" not in rolling_df.columns:
        return result
    for w in rolling_df["window"].unique():
        sub = rolling_df[rolling_df["window"] == w].sort_values("date")
        if sub.empty:
            continue
        series = sub["pc1_share"].to_numpy(dtype=float)
        current = float(series[-1])
        history = series[-history_window:]
        pct_rank = float(np.mean(history <= current) * 100)
        result[int(w)] = {
            "current_pc1_share": current,
            "percentile_rank": pct_rank,
            "history_window": int(len(history)),
            "alert": "HIGH" if pct_rank >= 80 else "LOW" if pct_rank <= 20 else "NORMAL",
        }
    return result

