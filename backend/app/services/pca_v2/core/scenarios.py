"""PCA V2 scenarios primitives."""
from __future__ import annotations
import math
import base64
from io import BytesIO
from typing import Any
import numpy as np
import pandas as pd


def historical_worst_day_scenarios(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    n_worst: int = 5,
) -> list[dict]:
    """For each PC, find the n worst historical daily realizations and replay portfolio P&L."""
    from .analytics import factor_returns, portfolio_weights
    payload = payload or {}
    w = portfolio_weights(model["symbols"], payload).reindex(model["symbols"]).fillna(0.0).to_numpy(dtype=float)
    f = factor_returns(model)
    rows = []
    for j in range(model["k"]):
        worst_idx = f.iloc[:, j].nsmallest(n_worst).index
        for date in worst_idx:
            factor_shock = f.loc[date].to_numpy(dtype=float)
            asset_impacts = model["eigenvectors"][:, :model["k"]] @ factor_shock
            pnl = float(w @ asset_impacts)
            realized_port = float(model["returns"].loc[date].to_numpy(dtype=float) @ w)
            rows.append({
                "component": f"PC{j+1}",
                "date": str(pd.Timestamp(date).date()),
                "factor_return": float(factor_shock[j]),
                "estimated_pnl": pnl,
                "realized_portfolio_return": realized_port,
            })
    return sorted(rows, key=lambda r: r["estimated_pnl"])



def joint_scenario_pnl(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Simultaneously shock multiple PCs with independent magnitudes.

    payload["joint_shocks"] = {"PC1": 2.0, "PC3": -1.5}  (sigma multiples)
    """
    from .analytics import factor_returns, portfolio_weights
    payload = payload or {}
    w = portfolio_weights(model["symbols"], payload).reindex(model["symbols"]).fillna(0.0).to_numpy(dtype=float)
    f = factor_returns(model)
    stds = f.std().replace(0, np.nan).fillna(1e-6).to_numpy(dtype=float)
    joint_shocks_raw = payload.get("joint_shocks") or {}
    shock = np.zeros(model["k"])
    for label, sigma_mult in (joint_shocks_raw if isinstance(joint_shocks_raw, dict) else {}).items():
        try:
            pc_idx = int(str(label).upper().replace("PC", "")) - 1
            if 0 <= pc_idx < model["k"]:
                shock[pc_idx] = float(sigma_mult) * stds[pc_idx]
        except (ValueError, IndexError):
            continue
    asset_returns = model["eigenvectors"][:, :model["k"]] @ shock
    pnl = float(w @ asset_returns)
    ticker_contributions = [
        {"ticker": model["symbols"][i], "pnl_contribution": float(w[i] * asset_returns[i])}
        for i in range(len(w))
    ]
    return {
        "joint_shocks": joint_shocks_raw,
        "portfolio_pnl": pnl,
        "shock_vector": shock.tolist(),
        "ticker_contributions": sorted(ticker_contributions, key=lambda r: r["pnl_contribution"]),
    }



def stress_scenarios(model: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from .analytics import factor_returns, number_like, portfolio_weights
    payload = payload or {}
    w = portfolio_weights(model["symbols"], payload).reindex(model["symbols"]).fillna(0.0).to_numpy(dtype=float)
    f = factor_returns(model)
    stds = f.std().replace(0, np.nan).fillna(1e-6).to_numpy(dtype=float)
    magnitude = float(number_like(payload.get("shock_sigma"), 2.0) or 2.0)
    exposures = model["eigenvectors"][:, : model["k"]].T @ w
    rows = []
    waterfall = {}
    for j in range(model["k"]):
        for sign in (1, -1):
            shock = np.zeros(model["k"])
            shock[j] = sign * magnitude * stds[j]
            asset_impacts = model["eigenvectors"][:, : model["k"]] @ shock
            pnl = float(w @ asset_impacts)
            label = f"PC{j+1} {'+' if sign > 0 else '-'}{magnitude:g}sigma"
            rows.append({"scenario": label, "component": f"PC{j+1}", "direction": "positive" if sign > 0 else "negative", "portfolio_pnl_pct": pnl, "shock_sigma": sign * magnitude, "factor_exposure": float(exposures[j])})
            waterfall[label] = sorted([{"ticker": model["symbols"][i], "pnl_contribution": float(w[i] * asset_impacts[i])} for i in range(len(w))], key=lambda r: r["pnl_contribution"])[:80]
    scen = pd.DataFrame(rows).sort_values("portfolio_pnl_pct")
    worst = scen.iloc[0].to_dict() if not scen.empty else {}
    q_hist = f / f.std().replace(0, np.nan)
    analogs = []
    if not scen.empty:
        target = np.zeros(model["k"])
        pc_idx = int(str(worst.get("component", "PC1")).replace("PC", "")) - 1
        target[pc_idx] = float(worst.get("shock_sigma", -magnitude))
        q_arr = q_hist.fillna(0.0).to_numpy(dtype=float)
        factor_corr = np.corrcoef(q_arr, rowvar=False)
        inv_factor_corr = np.linalg.pinv(np.atleast_2d(factor_corr) + np.eye(model["k"]) * 1e-8)
        delta = q_arr - target
        dist = np.einsum("ij,jk,ik->i", delta, inv_factor_corr, delta)
        for idx in np.argsort(dist)[:5]:
            lo, hi = max(0, idx - 30), min(len(model["returns"]), idx + 31)
            window_returns = model["returns"].iloc[lo:hi].to_numpy(dtype=float) @ w
            analogs.append({"date": str(pd.Timestamp(q_hist.index[idx]).date()), "mahalanobis_distance": float(math.sqrt(max(dist[idx], 0.0))), "realized_portfolio_return": float(model["returns"].iloc[idx].to_numpy(dtype=float) @ w), "window_60d_cumulative_return": float(np.prod(1.0 + window_returns) - 1.0)})
    current_factor_z = q_hist.iloc[-1].fillna(0.0) if len(q_hist) else pd.Series(dtype=float)
    for row in rows:
        j = int(row["component"].replace("PC", "")) - 1
        shock = float(row["shock_sigma"])
        hist_col = q_hist.iloc[:, j].dropna() if j < q_hist.shape[1] else pd.Series(dtype=float)
        row["current_factor_zscore"] = float(current_factor_z.iloc[j]) if j < len(current_factor_z) else None
        row["shock_historical_percentile"] = float((hist_col <= shock).mean() * 100.0) if len(hist_col) else None
    # Augmented stress VaR: combine 2K parametric + 10K MC from K-dim Gaussian factor dist
    losses_param = -scen["portfolio_pnl_pct"].to_numpy(dtype=float) if not scen.empty else np.array([])
    rng = np.random.default_rng(42)
    mc_factor_draws = rng.multivariate_normal(np.zeros(model["k"]), np.atleast_2d(f.cov().to_numpy(dtype=float)), size=10_000)
    mc_asset_impacts = mc_factor_draws @ model["eigenvectors"][:, :model["k"]].T
    mc_pnls = mc_asset_impacts @ w
    losses_mc = -mc_pnls
    all_losses = np.concatenate([losses_param, losses_mc])
    stress_var = float(np.percentile(all_losses, 95)) if len(all_losses) else None
    stress_cvar = float(all_losses[all_losses >= stress_var].mean()) if stress_var is not None and np.any(all_losses >= stress_var) else stress_var
    # Historical worst-day scenarios
    hist_worst = historical_worst_day_scenarios(model, payload, n_worst=int(number_like(payload.get("n_worst_days"), 5) or 5))
    # Joint multi-PC shock
    joint_result = joint_scenario_pnl(model, payload) if payload.get("joint_shocks") else None
    return {"scenario_rows": rows, "worst_scenario": worst, "waterfall": waterfall, "analogs": analogs, "stress_var": stress_var, "stress_cvar": stress_cvar, "historical_worst_day_scenarios": hist_worst, "joint_scenario": joint_result}



def stress_pdf_report_base64(model: dict[str, Any], stress: dict[str, Any]) -> str | None:
    """Generate compact PDF report as base64 when reportlab is available."""

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception:
        return None
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 54
    c.setFont("Helvetica-Bold", 16)
    c.drawString(54, y, "PCA V2 Stress Scenario Report")
    y -= 28
    c.setFont("Helvetica", 10)
    c.drawString(54, y, f"Assets: {len(model['symbols'])} | Observations: {model['returns'].shape[0]} | K: {model['k']}")
    y -= 22
    worst = stress.get("worst_scenario") or {}
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, y, "Worst Scenario")
    y -= 16
    c.setFont("Helvetica", 9)
    c.drawString(54, y, f"{worst.get('scenario')} | P&L: {worst.get('portfolio_pnl_pct')}")
    y -= 22
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, y, "Stress VaR / CVaR")
    y -= 16
    c.setFont("Helvetica", 9)
    c.drawString(54, y, f"VaR: {stress.get('stress_var')} | CVaR: {stress.get('stress_cvar')}")
    y -= 24
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, y, "Top Historical Analogs")
    y -= 16
    c.setFont("Helvetica", 8)
    for row in (stress.get("analogs") or [])[:8]:
        c.drawString(54, y, f"{row.get('date')}  distance={row.get('distance')}  realized={row.get('realized_portfolio_return')}")
        y -= 12
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, y, "Scenario Table")
    y -= 14
    c.setFont("Helvetica", 8)
    for row in (stress.get("scenario_rows") or [])[:28]:
        c.drawString(54, y, f"{row.get('scenario')}: {row.get('portfolio_pnl_pct')}")
        y -= 10
        if y < 72:
            c.showPage()
            y = height - 54
            c.setFont("Helvetica", 8)
    c.save()
    return base64.b64encode(buffer.getvalue()).decode("ascii")

