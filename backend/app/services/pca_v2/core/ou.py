"""PCA V2 ou primitives."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd
from .data_loader import dollar_volume_matrix


def volume_time_residuals(
    resid: pd.DataFrame,
    dv: pd.DataFrame,
) -> pd.DataFrame:
    """Re-express residuals in volume time per Avellaneda-Lee (2010)."""
    vol_mean = dv.rolling(30, min_periods=5).mean().replace(0, np.nan)
    vol_ratio = (dv / vol_mean).clip(lower=0.01)
    scaled = resid / np.sqrt(vol_ratio.reindex(index=resid.index, columns=resid.columns))
    scaled = scaled.replace([np.inf,-np.inf],np.nan).dropna(how="any")
    if len(scaled)<30:
        raise ValueError("Volume-time requires 30 complete observed residual/volume rows")
    return scaled



def residual_matrix(model: dict[str, Any], k: int | None = None) -> pd.DataFrame:
    from .analytics import factor_returns
    k = int(k or model["k"])
    if model.get("payload", {}).get("rolling_refit"):
        from .causal import rolling_residuals
        return rolling_residuals(model.get("original_returns", model["returns"]), int(model["payload"].get("pca_window",126)), k, model["payload"].get("covariance_estimator","ledoit_wolf"))
    rets = model["returns"].copy()
    f = factor_returns(model, k)
    x = np.column_stack([np.ones(len(f)), f.to_numpy(dtype=float)])
    y = rets.to_numpy(dtype=float)
    beta = np.linalg.pinv(x.T @ x) @ x.T @ y
    resid = y - x @ beta
    return pd.DataFrame(resid, index=rets.index, columns=rets.columns)



def ou_signal_table(model: dict[str, Any], payload: dict[str, Any] | None = None) -> pd.DataFrame:
    from .analytics import number_like
    payload = payload or {}
    resid = residual_matrix(model)
    # Volume-time adjustment (Avellaneda-Lee 2010)
    use_volume_time = bool(payload.get("volume_time", False))
    if use_volume_time:
        dv = dollar_volume_matrix(model["symbols"], lookback_days=model["lookback_days"]).reindex(resid.index)
        if dv.empty or dv.isna().all().any():
            raise ValueError("Volume-time requested but dollar-volume data is unavailable")
        resid = volume_time_residuals(resid, dv)
    window = int(number_like(payload.get("ou_window"), 126) or 126)
    entry = float(number_like(payload.get("entry_z"), 2.0) or 2.0)
    max_half_life = float(number_like(payload.get("max_half_life"), 60.0) or 60.0)
    sectors = model["sectors"]
    rows = []
    for ticker in resid.columns:
        x = resid[ticker].tail(window).cumsum().dropna().to_numpy(dtype=float)
        if len(x) < 25 or np.nanstd(x) <= 0:
            continue
        y = x[1:]
        lag = x[:-1]
        design = np.column_stack([np.ones(len(lag)), lag])
        a, b = np.linalg.lstsq(design, y, rcond=None)[0]
        if not 0 < b < 1:
            rows.append({"ticker":ticker,"sector":sectors.get(ticker,"Unknown"),"direction":"No Signal","economically_viable":False,"residual_z":None,"ou_half_life_days":None,"stationarity":"AR1 outside (0,1)"})
            continue
        b = float(b)
        kappa = -math.log(b)
        mu = float(a / (1 - b)) if abs(1 - b) > 1e-8 else float(np.mean(x))
        err = y - (a + b * lag)
        zeta = float(np.std(err, ddof=1))
        sigma = zeta * math.sqrt(max(2 * kappa / max(1 - math.exp(-2 * kappa), 1e-9), 1e-9))
        sigma_eq = sigma / math.sqrt(max(2 * kappa, 1e-9))
        zscore = float((x[-1] - mu) / max(sigma_eq, 1e-9))
        half_life = float(math.log(2) / max(kappa, 1e-9))
        # Standard errors on OU parameters (OLS SE from AR(1) regression)
        n_obs = len(y)
        resid_ols = err
        xtx_inv = np.linalg.pinv(design.T @ design)
        var_resid = float(np.var(resid_ols, ddof=2))
        se_b = float(math.sqrt(max(var_resid * xtx_inv[1, 1], 1e-12)))
        se_kappa = se_b / max(b, 1e-12)  # delta method: SE(kappa) ≈ SE(b) / b
        # Break-even Z: smallest |z| at which expected half-reversion PnL covers 1bp cost
        breakeven_z = float(1.0 / max(sigma_eq * math.sqrt(max(half_life, 0.5)), 1e-9) * 1e-4)
        direction = "Long" if zscore < -entry else "Short" if zscore > entry else "No Signal"
        viable = direction != "No Signal" and half_life <= max_half_life
        z_path = (x - mu) / max(sigma_eq, 1e-9)
        active_path = np.abs(z_path) >= entry
        days_since_trigger = 0
        for is_active in active_path[::-1]:
            if not is_active:
                break
            days_since_trigger += 1
        rows.append({"ticker": ticker, "sector": sectors.get(ticker, "Unknown"), "residual_z": zscore, "ou_half_life_days": half_life, "kappa": kappa, "mu": mu, "sigma_eq": sigma_eq, "se_kappa": se_kappa, "se_b": se_b, "breakeven_z": breakeven_z, "direction": direction, "economically_viable": bool(viable), "estimated_days_to_half_reversion": half_life, "days_since_signal_trigger": days_since_trigger if direction != "No Signal" else 0, "volume_time_adjusted": use_volume_time})
    return pd.DataFrame(rows, columns=["ticker", "sector", "residual_z", "ou_half_life_days", "kappa", "mu", "sigma_eq", "se_kappa", "se_b", "breakeven_z", "direction", "economically_viable", "estimated_days_to_half_reversion", "days_since_signal_trigger", "volume_time_adjusted"]).sort_values("residual_z", key=lambda s: s.abs(), ascending=False)



def signal_decay_analysis(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    horizons: tuple[int, ...] = (1, 5, 10, 21, 42, 63),
) -> list[dict[str, Any]]:
    """For every ticker that ever had an active signal, compute the average
    residual Z-score at T+h days after signal generation (forward Z-score).

    Empirically validates whether the OU mean-reversion assumption holds.
    A truly mean-reverting residual should show Z decaying toward 0 as h grows.
    """
    from .analytics import number_like
    payload = payload or {}
    from .causal import rolling_residuals
    resid = rolling_residuals(model.get("original_returns", model["returns"]), int(payload.get("pca_window", 126)), payload.get("k") or payload.get("component_count"), payload.get("covariance_estimator", "ledoit_wolf"))
    entry_z = float(number_like(payload.get("entry_z"), 2.0) or 2.0)
    window = int(number_like(payload.get("ou_window"), 126) or 126)
    rows: list[dict[str, Any]] = []
    for ticker in resid.columns:
        z_series = resid[ticker].dropna()
        if len(z_series) < max(horizons) + window + 5:
            continue
        mu_r = z_series.rolling(window, min_periods=30).mean()
        sig_r = z_series.rolling(window, min_periods=30).std().replace(0, np.nan)
        zscores = ((z_series - mu_r) / sig_r).dropna()
        for direction, mask_fn in (
            ("Long", lambda z: z < -entry_z),
            ("Short", lambda z: z > entry_z),
        ):
            signal_dates = zscores.index[mask_fn(zscores)]
            if len(signal_dates) == 0:
                continue
            init_z_mean = float(zscores[signal_dates].mean())
            for h in horizons:
                fwd_z_vals = []
                for dt in signal_dates:
                    try:
                        pos = zscores.index.get_loc(dt)
                        if pos + h < len(zscores):
                            fwd_z_vals.append(float(zscores.iloc[pos + h]))
                    except Exception:
                        continue
                if fwd_z_vals:
                    avg_fwd = float(np.mean(fwd_z_vals))
                    rows.append({
                        "ticker": ticker,
                        "sector": model["sectors"].get(ticker, "Unknown"),
                        "signal_direction": direction,
                        "horizon_days": h,
                        "avg_z_at_horizon": avg_fwd,
                        "n_signals": len(signal_dates),
                        "mean_reverting": bool(
                            direction == "Long" and avg_fwd > init_z_mean
                            or direction == "Short" and avg_fwd < init_z_mean
                        ),
                    })
    return rows



def residual_ou_backtest(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Vectorized residual OU signal backtest with entry/exit thresholds and costs."""
    from .analytics import model_annualization, number_like

    payload = payload or {}
    from .causal import rolling_residuals
    resid = rolling_residuals(model.get("original_returns", model["returns"]), window=int(payload.get("pca_window", 126)), k=payload.get("k") or payload.get("component_count"), estimator=payload.get("covariance_estimator", "ledoit_wolf")).cumsum()
    window = int(number_like(payload.get("ou_window"), 126) or 126)
    entry_z = float(number_like(payload.get("entry_z"), 2.0) or 2.0)
    exit_z = float(number_like(payload.get("exit_z"), 0.25) or 0.25)
    cost_bps = float(number_like(payload.get("cost_bps"), 2.0) or 2.0)
    max_positions = int(number_like(payload.get("max_positions"), 20) or 20)
    returns = model.get("original_returns",model["returns"]).reindex(index=resid.index, columns=resid.columns)
    z = resid.sub(resid.rolling(window, min_periods=max(20, window // 4)).mean()).div(
        resid.rolling(window, min_periods=max(20, window // 4)).std().replace(0, np.nan)
    )
    signal = pd.DataFrame(0.0, index=z.index, columns=z.columns)
    state = np.zeros(z.shape[1])
    for i in range(len(z)):
        current = z.iloc[i].to_numpy(dtype=float)
        state[np.abs(current) < exit_z] = 0.0
        state[current < -entry_z] = 1.0
        state[current > entry_z] = -1.0
        signal.iloc[i] = state
    # Keep only strongest names each day.
    ranks = z.abs().rank(axis=1, ascending=False, method="first")
    signal = signal.where(ranks <= max_positions, 0.0)
    gross_exposure = signal.abs().sum(axis=1).replace(0, np.nan)
    weights = signal.div(gross_exposure, axis=0).fillna(0.0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    gross = (weights.shift(1).fillna(0.0) * returns).sum(axis=1)
    costs = turnover.shift(1, fill_value=0.0) * cost_bps / 10000.0
    net = gross - costs
    equity = (1.0 + net).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    ann_factor = model_annualization(model, payload)
    ann = math.sqrt(ann_factor)
    sharpe = float(net.mean() / max(net.std(ddof=1), 1e-12) * ann)
    gross_sharpe = float(gross.mean() / max(gross.std(ddof=1), 1e-12) * ann)
    rows = pd.DataFrame(
        {
            "date": net.index,
            "gross_return": gross,
            "net_return": net,
            "turnover": turnover,
            "cost": costs,
            "equity": equity,
            "drawdown": drawdown,
            "active_positions": weights.abs().gt(0).sum(axis=1),
        }
    )
    stats_row = {
        "pca_fit": "rolling_past_only; signal_at_t_trade_at_t_plus_1",
        "gross_sharpe": gross_sharpe,
        "net_sharpe": sharpe,
        "annualized_return": float(net.mean() * ann_factor),
        "annualized_vol": float(net.std(ddof=1) * ann),
        "max_drawdown": float(drawdown.min()),
        "hit_rate": float((net > 0).mean()),
        "avg_daily_turnover": float(turnover.mean()),
        "total_cost": float(costs.sum()),
        "average_holding_period_days": _average_signal_holding_period(signal),
        "entry_z": entry_z,
        "exit_z": exit_z,
        "cost_bps": cost_bps,
    }
    return {"equity_curve": rows, "stats": stats_row}



def _average_signal_holding_period(signal: pd.DataFrame) -> float | None:
    durations = []
    for column in signal:
        active = signal[column].ne(0).to_numpy()
        start = None
        for idx, value in enumerate(active):
            if value and start is None:
                start = idx
            elif not value and start is not None:
                durations.append(idx - start)
                start = None
        if start is not None:
            durations.append(len(active) - start)
    return float(np.mean(durations)) if durations else None



def ou_mle(x: np.ndarray, dt: float = 1.0 / 252) -> dict[str, float]:
    """Estimate OU parameters {kappa, mu, sigma} by exact discrete-time MLE.

    The discrete-time OU transition density is Gaussian:
        mean_t = mu + (x_{t-1} - mu) * exp(-kappa * dt)
        var_t  = sigma^2 * (1 - exp(-2*kappa*dt)) / (2*kappa)

    Warm-started from the OLS AR(1) solution. Uses scipy L-BFGS-B.
    """
    from scipy.optimize import minimize as _minimize

    x = np.asarray(x, dtype=float)
    if len(x) < 10:
        return {"kappa": float("nan"), "mu": float("nan"), "sigma": float("nan"),
                "half_life_days": float("nan"), "log_likelihood": float("nan")}

    y, lag = x[1:], x[:-1]

    def neg_loglik(params: np.ndarray) -> float:
        kappa_, mu_, log_sigma_ = params
        kappa_ = max(kappa_, 1e-6)
        sigma_ = math.exp(log_sigma_)
        e_kdt = math.exp(-kappa_ * dt)
        cond_mean = mu_ + (lag - mu_) * e_kdt
        cond_var = max(sigma_ ** 2 * (1.0 - math.exp(-2.0 * kappa_ * dt)) / (2.0 * kappa_), 1e-12)
        residuals = y - cond_mean
        n = len(residuals)
        return 0.5 * n * math.log(2 * math.pi * cond_var) + 0.5 * float(np.sum(residuals ** 2)) / cond_var

    # OLS warm start
    design = np.column_stack([np.ones(len(lag)), lag])
    a_ols, b_ols = np.linalg.lstsq(design, y, rcond=None)[0]
    b_ols = float(np.clip(b_ols, 1e-6, 0.999999))
    kappa0 = max(-math.log(b_ols) / dt, 1e-4)
    mu0 = float(a_ols / (1 - b_ols)) if abs(1 - b_ols) > 1e-8 else float(np.mean(x))
    sigma0 = float(np.std(y - (a_ols + b_ols * lag), ddof=1))

    try:
        res = _minimize(
            neg_loglik,
            x0=[kappa0, mu0, math.log(max(sigma0, 1e-8))],
            method="L-BFGS-B",
            bounds=[(1e-6, 500.0), (None, None), (-20.0, 10.0)],
            options={"maxiter": 500, "ftol": 1e-10},
        )
        kappa, mu, log_sigma = res.x
        sigma = math.exp(log_sigma)
        ll = float(-res.fun)
    except (ValueError, RuntimeError) as exc:
        raise ValueError("OU MLE optimization failed") from exc
    if not res.success:
        raise ValueError(f"OU MLE optimization failed: {res.message}")

    return {
        "kappa": float(kappa),
        "mu": float(mu),
        "sigma": float(sigma),
        "half_life_days": float(math.log(2) / max(kappa, 1e-9) / max(dt, 1e-12)),
        "log_likelihood": ll,
    }

