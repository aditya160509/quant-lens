"""PCA V2 allocation helpers."""
from __future__ import annotations
import math
from typing import Any
import numpy as np
import cvxpy as cp


def k_sensitivity_sweep(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
    oos_fraction: float = 0.3,
) -> list[dict]:
    """Out-of-sample Sharpe vs K sweep for sensitivity analysis."""
    from .analytics import covariance_estimator, eig_sorted, fit_mp_sigma2, model_annualization, mp_threshold
    from copy import deepcopy
    rets = model["returns"]
    n_obs = len(rets)
    split = int(n_obs * (1 - oos_fraction))
    embargo = int((payload or {}).get("oos_embargo", 21))
    rets_is = rets.iloc[:split]
    rets_oos = rets.iloc[split + embargo:]
    if len(rets_is)<30 or len(rets_oos)<10:
        raise ValueError("OOS split requires 30 train and 10 test observations after embargo")
    train_cov, _ = covariance_estimator(rets_is, "ledoit_wolf")
    train_vals, _ = eig_sorted(train_cov)
    train_mp = mp_threshold(train_vals, rets_is.shape[1], len(rets_is), fit_mp_sigma2(train_vals, rets_is.shape[1], len(rets_is)))
    k_max = max(1, int((train_vals>train_mp["lambda_max"]).sum()))
    model["oos_selection_disclosure"] = "Explicit/current coverage universe; historical membership unavailable. K candidates use training data only."
    k_range = range(1, min(k_max + 3, rets.shape[1] - 1))
    ann = model_annualization(model, payload)
    rows = []
    for k in k_range:
        try:
            m_is = deepcopy(model)
            m_is["returns"] = rets_is
            m_is["k"] = k
            cov_is, _ = covariance_estimator(rets_is, "ledoit_wolf")
            evals_is, evecs_is = eig_sorted(cov_is)
            idio_is = np.maximum(np.diag(cov_is) - np.sum(evecs_is[:, :k] ** 2 * evals_is[:k], axis=1), 1e-10)
            signal_is = (evecs_is[:, :k] * evals_is[:k]) @ evecs_is[:, :k].T
            m_is["cov"] = cov_is
            m_is["cleaned_cov"] = signal_is + np.diag(idio_is)
            m_is["eigenvalues"] = evals_is
            m_is["eigenvectors"] = evecs_is
            m_is["idio_var"] = idio_is
            from .optimization import optimize
            opt = optimize(m_is, payload or {}, frontier=False)
            w = np.array(
                [r["weight"] for r in sorted(opt["weights"], key=lambda x: model["symbols"].index(x["ticker"]) if x["ticker"] in model["symbols"] else 9999)],
                dtype=float,
            )
            if len(w) != len(model["symbols"]):
                continue
            oos_rets = rets_oos.reindex(columns=model["symbols"]).fillna(0.0).to_numpy(dtype=float)
            p_rets = oos_rets @ w
            sr = float(p_rets.mean() / max(p_rets.std(ddof=1), 1e-12) * math.sqrt(ann))
            rows.append({"k": k, "oos_sharpe": sr, "oos_vol": float(p_rets.std() * math.sqrt(ann)), "is_k_rmt": k == model["k_info"].get("rmt")})
        except (ValueError, RuntimeError) as exc:
            rows.append({"k":k,"error":str(exc),"oos_sharpe":None})
    return rows



def black_litterman_posterior(
    cov: np.ndarray,
    w_market: np.ndarray,
    views: list[dict],
    symbols: list[str],
    tau: float = 0.05,
    risk_aversion: float = 3.0,
) -> np.ndarray:
    """Black-Litterman posterior expected returns."""
    n = len(symbols)
    sym_idx = {s: i for i, s in enumerate(symbols)}
    mu_prior = risk_aversion * cov @ w_market

    if not views:
        return mu_prior

    Q_rows: list[np.ndarray] = []
    q_vals: list[float] = []
    omega_diag: list[float] = []
    for v in views:
        row = np.zeros(n)
        for ticker, loading in (v.get("assets") or {}).items():
            idx = sym_idx.get(ticker)
            if idx is not None:
                row[idx] = float(loading)
        if np.abs(row).sum() < 1e-12:
            continue
        Q_rows.append(row)
        q_vals.append(float(v.get("return", 0.0)))
        conf = float(np.clip(v.get("confidence", 0.5), 0.01, 0.99))
        omega_diag.append(tau * float(row @ cov @ row) / max(conf ** 2, 1e-6))

    if not Q_rows:
        return mu_prior

    P = np.array(Q_rows, dtype=float)
    q = np.array(q_vals, dtype=float)
    Omega = np.diag(omega_diag)

    tau_sigma_inv = np.linalg.pinv(tau * cov)
    omega_inv = np.diag(1.0 / np.maximum(np.diag(Omega), 1e-12))
    precision = tau_sigma_inv + P.T @ omega_inv @ P
    rhs = tau_sigma_inv @ mu_prior + P.T @ omega_inv @ q
    mu_post = np.linalg.pinv(precision) @ rhs
    return mu_post



def robust_frontier_ellipsoidal(
    model: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Bertsimas-Brown-style ellipsoidal uncertainty penalty frontier."""
    from .analytics import model_annualization, number_like

    payload = payload or {}
    symbols = model["symbols"]
    cov = model["cleaned_cov"]
    n = len(symbols)
    ann = model_annualization(model, payload)
    mu = model["returns"].mean().reindex(symbols).fillna(0.0).to_numpy(dtype=float) * ann
    gamma = float(number_like(payload.get("robust_gamma"), 1.0) or 1.0)
    max_w = float(number_like(payload.get("max_weight"), 0.12) or 0.12)
    diag_unc = np.diag(np.maximum(np.diag(cov), 1e-12)) * gamma
    rows = []
    if cp is not None:
        w = cp.Variable(n)
        u_sqrt = np.sqrt(np.diag(diag_unc))
        constraints = [cp.sum(w) == 1, w >= 0, w <= max_w]
        for lam in np.linspace(1.0, 20.0, 30):
            objective = cp.Maximize(mu @ w - float(lam) * cp.quad_form(w, cov) - cp.norm(cp.multiply(u_sqrt, w), 2))
            prob = cp.Problem(objective, constraints)
            try:
                prob.solve(solver=cp.CLARABEL, verbose=False)
            except Exception:
                try:
                    prob.solve(solver=cp.SCS, verbose=False)
                except Exception:
                    continue
            if w.value is None:
                continue
            ww = np.maximum(np.asarray(w.value, dtype=float), 0.0)
            ww = ww / max(ww.sum(), 1e-12)
            rows.append(
                {
                    "risk": float(math.sqrt(max(ww @ cov @ ww, 0.0)) * math.sqrt(ann)),
                    "return": float(ww @ mu),
                    "robust_penalty": float(np.linalg.norm(u_sqrt * ww)),
                    "lambda": float(lam),
                    "frontier": "robust_ellipsoidal",
                }
            )
    if rows:
        return rows
    raise ValueError("Ellipsoidal robust frontier optimization failed; no substitute frontier is produced")
