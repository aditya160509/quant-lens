I need to read both documents carefully before giving you the gap analysis.

Let me go through this systematically — spec (doc 2) vs implementation (docs 1 + 3), feature by feature.

---

## FEATURE 1 — RMT Covariance Engine

**Not done:**

1. σ² fitting is wrong. Spec requires MLE fit of the MP density to the empirical spectrum. You have:

```python
# CURRENT — wrong, just median
sigma = float(np.nanmedian(vals) if len(vals) else 1.0)
```

```python
# CORRECT — moment matching on noise bulk
def fit_mp_sigma2(eigenvalues: np.ndarray, q: float) -> float:
    """Fit σ² by matching the theoretical MP mean to the empirical bulk mean."""
    vals = np.asarray(eigenvalues, dtype=float)
    # Iterative: restrict to bulk, refit, repeat until convergence
    sigma2 = float(np.median(vals))
    for _ in range(50):
        lam_max = sigma2 * (1 + np.sqrt(q)) ** 2
        bulk = vals[vals <= lam_max * 1.05]  # slight tolerance
        if len(bulk) == 0:
            break
        new_sigma2 = float(np.mean(bulk))  # E[λ] under MP = σ²
        if abs(new_sigma2 - sigma2) < 1e-8:
            break
        sigma2 = new_sigma2
    return max(sigma2, 1e-12)
```

Then in `mp_threshold`:

```python
def mp_threshold(eigenvalues, n_assets, n_obs, sigma2=None):
    q = max(float(n_assets) / max(float(n_obs), 1.0), 1e-9)
    vals = np.asarray(eigenvalues, dtype=float)
    sigma = float(sigma2) if sigma2 is not None else fit_mp_sigma2(vals, q)
    root = math.sqrt(q)
    return {
        "q_ratio": q,
        "sigma2": sigma,
        "lambda_min": sigma * (1 - root) ** 2,
        "lambda_max": sigma * (1 + root) ** 2,
    }
```

2. Outlier pre-processing not implemented at all. Spec requires winsorize / Huber M-estimation / trimming before the covariance estimator runs.

```python
def preprocess_returns(
    returns: pd.DataFrame,
    method: str = "none",
    winsor_lower: float = 0.01,
    winsor_upper: float = 0.99,
) -> pd.DataFrame:
    """Apply outlier pre-processing before covariance estimation."""
    x = returns.copy()
    method = str(method or "none").lower()
    if method == "none":
        return x
    if method.startswith("winsor"):
        lo = x.quantile(winsor_lower)
        hi = x.quantile(winsor_upper)
        x = x.clip(lower=lo, upper=hi, axis=1)
        return x
    if method == "huber":
        from scipy.stats import median_abs_deviation
        for col in x.columns:
            s = x[col].to_numpy(dtype=float)
            med = np.median(s)
            mad = max(float(median_abs_deviation(s, nan_policy="omit")), 1e-12)
            k = 1.345  # standard Huber tuning constant
            weights = np.where(np.abs(s - med) / mad <= k, 1.0,
                               k / (np.abs(s - med) / mad + 1e-12))
            x[col] = med + weights * (s - med)
        return x
    if method == "trim":
        lo_val = x.quantile(winsor_lower)
        hi_val = x.quantile(winsor_upper)
        mask = (x >= lo_val) & (x <= hi_val)
        return x.where(mask).fillna(0.0)
    return x
```

Then wire it into `rmt_model`:

```python
# In rmt_model(), before covariance_estimator call:
outlier_method = payload.get("outlier_method") or "none"
winsor_lower = float(number_like(payload.get("winsor_lower"), 0.01) or 0.01)
winsor_upper = float(number_like(payload.get("winsor_upper"), 0.99) or 0.99)
returns_clean = preprocess_returns(
    returns, method=outlier_method,
    winsor_lower=winsor_lower, winsor_upper=winsor_upper
)
cov, cov_meta = covariance_estimator(
    returns_clean, method, ewma_lambda=...
)
```

3. Shrinkage blend reconstruction mode not implemented. Spec requires a slider between raw and cleaned.

```python
def reconstruct_covariance(
    cov_raw: np.ndarray,
    eigenvalues: np.ndarray,
    eigenvectors: np.ndarray,
    idio_var: np.ndarray,
    k: int,
    blend_gamma: float = 0.0,  # 0 = pure RMT, 1 = pure sample
) -> np.ndarray:
    signal = (eigenvectors[:, :k] * eigenvalues[:k]) @ eigenvectors[:, :k].T
    sigma_k = signal + np.diag(idio_var)
    if blend_gamma <= 0.0:
        return sigma_k
    return (1 - blend_gamma) * sigma_k + blend_gamma * cov_raw
```

Wire into `rmt_model`:

```python
blend_gamma = float(number_like(payload.get("blend_gamma") or payload.get("shrinkage_blend"), 0.0) or 0.0)
blend_gamma = float(np.clip(blend_gamma, 0.0, 1.0))
cleaned = reconstruct_covariance(cov, evals, evecs, idio, k, blend_gamma)
```

---

## FEATURE 2 — Loading Matrix

**Not done:**

1. Promax rotation entirely missing.

```python
def promax(loadings: np.ndarray, power: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Oblique Promax rotation. Returns (rotated_loadings, factor_correlation_matrix)."""
    # Start from varimax solution
    rot = varimax(loadings)
    # Raise to power to concentrate, then solve for non-orthogonal rotation
    target = np.sign(rot) * np.abs(rot) ** power
    A = np.linalg.lstsq(rot, target, rcond=None)[0]
    # Normalize columns of A
    D = np.diag(1.0 / np.sqrt(np.diag(A.T @ A) + 1e-12))
    A = A @ D
    rotated = rot @ A
    # Factor correlation matrix
    phi = np.linalg.inv(A.T @ A + 1e-10 * np.eye(A.shape[0]))
    return rotated, phi
```

Wire into feature_02:

```python
rotation = str(payload.get("rotation", "none")).lower()
if rotation == "varimax":
    rot = varimax(model["eigenvectors"][:, :k])
    rotated = _build_rotated_records(rot, model)
elif rotation == "promax":
    rot, phi = promax(model["eigenvectors"][:, :k])
    rotated = _build_rotated_records(rot, model)
    # also return phi as factor_correlation_matrix in tables
```

2. Per-asset R² of the factor model not computed or returned anywhere.

```python
def asset_r2(model: dict) -> list[dict]:
    """Fraction of each asset's variance explained by the K-PC factor model."""
    k = model["k"]
    evals = model["eigenvalues"][:k]
    vecs = model["eigenvectors"][:, :k]
    diag_cov = np.diag(model["cov"])
    r2_vals = np.sum(vecs ** 2 * evals, axis=1) / np.maximum(diag_cov, 1e-12)
    return [
        {
            "ticker": model["symbols"][i],
            "sector": model["sectors"].get(model["symbols"][i], "Unknown"),
            "r2": float(np.clip(r2_vals[i], 0.0, 1.0)),
            "idiosyncratic_share": float(np.clip(1 - r2_vals[i], 0.0, 1.0)),
        }
        for i in range(len(model["symbols"]))
    ]
```

Add to feature_02 tables: `"asset_r2_table": asset_r2(model)`

3. Hoyer sparsity score per loading column not computed.

```python
def hoyer_sparsity(loadings: np.ndarray) -> list[dict]:
    """Hoyer sparsity score per PC column. Higher = more concentrated = more interpretable."""
    n, k = loadings.shape
    rows = []
    for j in range(k):
        col = loadings[:, j]
        l1 = float(np.sum(np.abs(col)))
        l2 = float(np.sqrt(np.sum(col ** 2)))
        # Hoyer: (sqrt(n) - l1/l2) / (sqrt(n) - 1), in [0,1]
        sparsity = (math.sqrt(n) - l1 / max(l2, 1e-12)) / max(math.sqrt(n) - 1, 1e-12)
        rows.append({"component": f"PC{j+1}", "hoyer_sparsity": float(np.clip(sparsity, 0, 1))})
    return rows
```

4. Two-level Hierarchical PCA is fully absent. This is large. Wire it as an optional toggle:

```python
def hierarchical_pca(
    returns: pd.DataFrame,
    sectors: dict[str, str],
    k_intra: int = 2,
    k_cross: int = 3,
    estimator: str = "ledoit_wolf",
) -> dict:
    """Two-level Hierarchical PCA: intra-cluster then cross-cluster."""
    from collections import defaultdict
    cluster_map: dict[str, list[str]] = defaultdict(list)
    for ticker, sector in sectors.items():
        if ticker in returns.columns:
            cluster_map[sector].append(ticker)

    cluster_factors = {}
    cluster_loadings = {}
    for sector, tickers in cluster_map.items():
        if len(tickers) < 2:
            continue
        sub_rets = returns[tickers].fillna(0.0)
        cov, _ = covariance_estimator(sub_rets, estimator)
        vals, vecs = eig_sorted(cov)
        kk = min(k_intra, len(tickers) - 1, len(vals))
        # Intra-cluster factor returns
        f = sub_rets.to_numpy(dtype=float) @ vecs[:, :kk]
        cluster_factors[sector] = pd.DataFrame(
            f, index=returns.index,
            columns=[f"{sector}_PC{i+1}" for i in range(kk)]
        )
        cluster_loadings[sector] = {
            "tickers": tickers,
            "loadings": vecs[:, :kk],
            "eigenvalues": vals[:kk],
        }

    if len(cluster_factors) < 2:
        return {"cluster_factors": cluster_factors, "cross_loadings": None}

    # Level-2: PCA across cluster factor returns
    cross_rets = pd.concat(list(cluster_factors.values()), axis=1).fillna(0.0)
    cov2, _ = covariance_estimator(cross_rets, estimator)
    vals2, vecs2 = eig_sorted(cov2)
    kk2 = min(k_cross, cross_rets.shape[1] - 1)
    cross_factor_rets = pd.DataFrame(
        cross_rets.to_numpy(dtype=float) @ vecs2[:, :kk2],
        index=returns.index,
        columns=[f"Cross_PC{i+1}" for i in range(kk2)]
    )
    return {
        "cluster_factors": cluster_factors,
        "cluster_loadings": cluster_loadings,
        "cross_factor_returns": cross_factor_rets,
        "cross_eigenvectors": vecs2[:, :kk2],
        "cross_eigenvalues": vals2[:kk2],
        "cross_column_names": list(cross_rets.columns),
    }
```

---

## FEATURE 3 — Risk Decomposition

**Not done:**

1. Benchmark-relative active risk attribution entirely absent. The `risk_decomposition` function has no benchmark parameter.

```python
def active_risk_attribution(
    model: dict,
    payload: dict | None = None,
) -> dict:
    """Tracking error decomposition against a benchmark weight vector."""
    payload = payload or {}
    symbols = model["symbols"]
    w = portfolio_weights(symbols, payload).reindex(symbols).fillna(0.0).to_numpy(dtype=float)
    # benchmark weights: equal-weight default or user-supplied
    w_bench_raw = payload.get("benchmark_weights") or {}
    if isinstance(w_bench_raw, dict) and w_bench_raw:
        w_bench = pd.Series({s: float(w_bench_raw.get(s, 0.0)) for s in symbols}, dtype=float)
        w_bench = (w_bench / w_bench.abs().sum()).to_numpy(dtype=float)
    else:
        # equal-weight SPY proxy: just equal-weight the universe
        w_bench = np.ones(len(symbols)) / len(symbols)

    wa = w - w_bench  # active weight
    cov = model["cleaned_cov"]
    evals = model["eigenvalues"]
    vecs = model["eigenvectors"]
    k = model["k"]

    active_var = float(wa @ cov @ wa)
    te = float(math.sqrt(max(active_var * 252, 0)))

    factor_active_vars = []
    for i in range(k):
        exposure = float(wa @ vecs[:, i])
        fav = float(evals[i] * exposure ** 2)
        factor_active_vars.append({
            "component": f"PC{i+1}",
            "active_exposure": exposure,
            "active_variance": fav,
            "pct_active_variance": fav / max(active_var, 1e-12) * 100,
            "annualized_te_contribution_bps": float(math.sqrt(max(fav * 252, 0)) * 10000),
        })

    idio_active_var = float(np.sum(model["idio_var"] * wa ** 2))
    factor_active_vars.append({
        "component": "Idiosyncratic",
        "active_exposure": None,
        "active_variance": idio_active_var,
        "pct_active_variance": idio_active_var / max(active_var, 1e-12) * 100,
        "annualized_te_contribution_bps": float(math.sqrt(max(idio_active_var * 252, 0)) * 10000),
    })

    return {
        "active_variance": active_var,
        "tracking_error_annualized": te,
        "factor_tilt_share": sum(r["pct_active_variance"] for r in factor_active_vars if r["component"] != "Idiosyncratic"),
        "selection_share": idio_active_var / max(active_var, 1e-12) * 100,
        "attribution_rows": factor_active_vars,
    }
```

Wire into feature_03:

```python
active = active_risk_attribution(model, payload)
# add to tables: "active_risk_attribution_table": active["attribution_rows"]
# add to charts: "tracking_error_annualized": active["tracking_error_annualized"]
```

2. Rolling per-factor decomposition is missing. Currently `rolling` in feature_03 is just rolling portfolio vol, not a rolling attribution stack.

```python
def rolling_risk_decomposition(
    model: dict,
    payload: dict | None = None,
    window: int = 21,
) -> pd.DataFrame:
    symbols = model["symbols"]
    w = portfolio_weights(symbols, payload).reindex(symbols).fillna(0.0).to_numpy(dtype=float)
    rets = model["returns"].reindex(columns=symbols).fillna(0.0)
    k = model["k"]
    rows = []
    for end in range(window, len(rets) + 1):
        sub = rets.iloc[end - window: end]
        cov_sub = np.cov(sub.to_numpy(dtype=float), rowvar=False)
        port_var = max(float(w @ cov_sub @ w), 1e-12)
        evals_sub, evecs_sub = eig_sorted(cov_sub)
        row = {"date": rets.index[end - 1]}
        for i in range(min(k, len(evals_sub))):
            exp = float(w @ evecs_sub[:, i])
            row[f"PC{i+1}_pct"] = float(evals_sub[i] * exp ** 2 / port_var * 100)
        idio = max(0.0, 100.0 - sum(row.get(f"PC{i+1}_pct", 0.0) for i in range(k)))
        row["Idiosyncratic_pct"] = idio
        rows.append(row)
    return pd.DataFrame(rows)
```

---

## FEATURE 4 — OU Stat Arb

**Not done:**

1. Volume-time adjustment — the entire Avellaneda improvement is absent, noted in meta only.

```python
def volume_time_residuals(
    resid: pd.DataFrame,
    dv: pd.DataFrame,
) -> pd.DataFrame:
    """Re-express residuals in volume time per Avellaneda-Lee (2010)."""
    # Volume clock: normalize volume by 30-day rolling mean
    vol_mean = dv.rolling(30, min_periods=5).mean().replace(0, np.nan)
    vol_ratio = (dv / vol_mean).fillna(1.0).clip(lower=0.01)
    # Scale residuals: divide by sqrt of relative volume
    # Low volume → weight up (more credible signal), high volume → weight down
    scaled = resid / np.sqrt(vol_ratio.reindex(resid.index, method="ffill").reindex(columns=resid.columns).fillna(1.0))
    return scaled
```

Wire into `ou_signal_table`:

```python
use_volume_time = bool(payload.get("volume_time", False))
if use_volume_time:
    from .data_loader import dollar_volume_matrix
    dv = dollar_volume_matrix(list(resid.columns), lookback_days=window + 60)
    resid = volume_time_residuals(resid, dv)
```

2. Break-even Z-score (transaction cost filter) not computed:

```python
def breakeven_zscore(
    sigma_eq: float,
    cost_bps: float,
    s_exit: float = 0.0,
) -> float:
    """Minimum Z-score for the signal to be economically viable after costs."""
    # gross P&L per unit ≈ sigma_eq * (|z| - s_exit)
    # net P&L > 0 requires: sigma_eq * (|z| - s_exit) > 2 * cost_bps / 10000
    if sigma_eq <= 0:
        return float("inf")
    return s_exit + (2 * cost_bps / 10000) / sigma_eq
```

Add to each row in `ou_signal_table`:

```python
cost_bps = float(number_like(payload.get("cost_bps"), 5.0) or 5.0)
s_exit = float(number_like(payload.get("exit_z"), 0.0) or 0.0)
rows[-1]["breakeven_z"] = breakeven_zscore(sigma_eq, cost_bps, s_exit)
rows[-1]["net_viable"] = bool(abs(zscore) > breakeven_zscore(sigma_eq, cost_bps, s_exit))
```

3. OU parameter standard errors (delta method) not computed anywhere:

```python
def ou_parameter_stderr(
    x: np.ndarray,
    a: float, b: float, zeta2: float
) -> dict:
    """Standard errors on OU parameters via OLS residual variance."""
    n = len(x) - 1
    y = x[1:]
    lag = x[:-1]
    X = np.column_stack([np.ones(n), lag])
    XtX_inv = np.linalg.pinv(X.T @ X)
    # SE on b (mean-reversion parameter) — most critical
    se_b = float(math.sqrt(max(zeta2 * XtX_inv[1, 1], 0)))
    # SE on half-life via delta method: HL = ln(2)/(-ln(b))
    # dHL/db = ln(2) / (b * ln(b)^2)  [using b = e^{-kappa}]
    if 1e-6 < b < 1 - 1e-6:
        dhl_db = math.log(2) / (b * math.log(b) ** 2 + 1e-12)
        se_hl = float(abs(dhl_db) * se_b)
    else:
        se_hl = float("inf")
    return {"se_b": se_b, "se_half_life": se_hl}
```

4. Signal decay analysis not implemented:

```python
def signal_decay_analysis(
    model: dict,
    payload: dict | None = None,
    horizons: tuple = (1, 5, 10, 21, 42, 63),
) -> list[dict]:
    """
    For each signal-active ticker, track the average Z-score
    at T+h days after signal generation.
    Empirically validates whether mean-reversion is holding.
    """
    payload = payload or {}
    signals = ou_signal_table(model, payload)
    resid = residual_matrix(model)
    entry = float(number_like(payload.get("entry_z"), 2.0) or 2.0)
    rows = []
    for _, sig in signals.iterrows():
        ticker = sig["ticker"]
        if ticker not in resid.columns:
            continue
        mu = sig["mu"]
        sigma_eq = max(sig["sigma_eq"], 1e-9)
        x = resid[ticker].cumsum().to_numpy(dtype=float)
        # find all entry dates
        zscores = (x - mu) / sigma_eq
        for t in range(len(zscores) - max(horizons)):
            if abs(zscores[t]) >= entry:
                direction = -1 if zscores[t] > 0 else 1  # fade the extreme
                for h in horizons:
                    z_h = float(zscores[t + h])
                    rows.append({
                        "ticker": ticker,
                        "horizon": h,
                        "initial_z": float(zscores[t]),
                        "z_at_horizon": z_h,
                        "reversion": float(direction * (zscores[t] - z_h)),
                    })
    if not rows:
        return []
    df = pd.DataFrame(rows)
    summary = df.groupby("horizon").agg(
        avg_reversion=("reversion", "mean"),
        hit_rate=("reversion", lambda s: (s > 0).mean()),
        n_signals=("reversion", "count"),
    ).reset_index()
    return clean_json(summary.to_dict("records"))
```

---

## FEATURE 5 — Regime Monitor

**Not done:**

1. Current percentile ranking of φ₁(t) not computed — spec requires 252-day historical percentile in the alert panel.

```python
def compute_percentile_rank(series: pd.Series, current_val: float, window: int = 252) -> float:
    hist = series.dropna().tail(window).to_numpy(dtype=float)
    if len(hist) == 0:
        return 50.0
    return float(np.mean(hist <= current_val) * 100)
```

Add into feature_05 alert panel:

```python
# In feature_05.run():
pc1_series = roll[roll["window"] == 63]["pc1_share"] if not roll.empty else pd.Series(dtype=float)
current_pc1 = float(pc1_series.iloc[-1]) if len(pc1_series) else None
pc1_percentile = compute_percentile_rank(pc1_series, current_pc1) if current_pc1 else None
# include in summary_cards
```

2. PC1 loading evolution heatmap (N × T matrix of loading vectors over time) — not computed at all. Rolling PCA only tracks scalar metrics.

```python
def rolling_loading_evolution(
    payload: dict | None = None,
    window: int = 63,
    step: int = 5,
    top_n: int = 20,
) -> list[dict]:
    """Track how PC1 loadings evolve across rolling windows."""
    ctx = load_context(payload)
    rets = ctx["returns"]
    symbols = ctx["symbols"]
    rows = []
    for end in range(window, len(rets) + 1, step):
        sample = rets.iloc[end - window: end]
        cov, _ = covariance_estimator(sample, "ledoit_wolf")
        _, vecs = eig_sorted(cov)
        date_str = str(pd.Timestamp(sample.index[-1]).date())
        for i, ticker in enumerate(symbols[:top_n]):
            rows.append({
                "date": date_str,
                "ticker": ticker,
                "pc1_loading": float(vecs[i, 0]),
            })
    return rows
```

3. Principal angles between subspaces — the spec is explicit about K-dimensional subspace angles, not just scalar cosine similarity. The `rolling_pca_metrics` function only tracks `pc1_cosine_stability` (scalar, PC1 only).

```python
def subspace_principal_angles(
    P1: np.ndarray,  # N x K
    P2: np.ndarray,  # N x K
) -> np.ndarray:
    """Principal angles between two K-dimensional subspaces via SVD of P1^T P2."""
    M = P1.T @ P2  # K x K
    sv = np.linalg.svd(M, compute_uv=False)
    sv = np.clip(sv, -1.0, 1.0)
    return np.arccos(sv)  # principal angles in radians
```

Wire into `rolling_pca_metrics` alongside the existing cosine:

```python
if prior_vec is not None and prior_loading_matrix is not None:
    angles = subspace_principal_angles(prior_loading_matrix, vecs[:, :k_used])
    max_principal_angle = float(np.degrees(angles[-1]))  # largest angle = most sensitive
else:
    max_principal_angle = 0.0
rows[-1]["max_principal_angle_deg"] = max_principal_angle
prior_loading_matrix = vecs[:, :k_used]
```

---

## FEATURE 6 — Optimization

**Not done — this feature has the largest gaps:**

1. ERC / Risk Parity (Spinu algorithm) entirely absent:

```python
def erc_portfolio(
    cov: np.ndarray,
    symbols: list[str],
    risk_budgets: np.ndarray | None = None,
) -> np.ndarray:
    """
    Equal Risk Contribution portfolio via Spinu (2013) convex reformulation.
    Minimizes f(w) = 0.5 * w^T Sigma w - sum(c_i * log(w_i))
    where c_i = risk budget (equal by default = 1/N).
    """
    n = cov.shape[0]
    c = risk_budgets if risk_budgets is not None else np.ones(n) / n

    def objective(w):
        return 0.5 * w @ cov @ w - float(np.sum(c * np.log(np.maximum(w, 1e-12))))

    def gradient(w):
        return cov @ w - c / np.maximum(w, 1e-12)

    w0 = np.ones(n) / n
    bounds = [(1e-6, None)] * n
    result = minimize(
        objective, w0, jac=gradient,
        method="L-BFGS-B", bounds=bounds,
        options={"maxiter": 1000, "ftol": 1e-12},
    )
    w = np.array(result.x, dtype=float)
    w = np.maximum(w, 0)
    return w / w.sum()
```

2. Maximum Sharpe Portfolio not explicitly solved — you only do mean-variance sweep, not the explicit MSP:

```python
def max_sharpe_portfolio(
    cov: np.ndarray,
    mu: np.ndarray,
    rf: float = 0.0,
    max_weight: float = 0.12,
) -> np.ndarray:
    """
    Explicit max-Sharpe via the Tobin separation trick:
    minimize w^T Sigma w  s.t. w^T (mu - rf) = 1, w >= 0
    then renormalize.
    """
    n = len(mu)
    excess_mu = mu - rf
    if cp is not None:
        w = cp.Variable(n)
        constraints = [
            cp.sum(cp.multiply(excess_mu, w)) == 1,
            w >= 0,
            w <= max_weight * cp.sum(cp.abs(w)),
        ]
        prob = cp.Problem(cp.Minimize(cp.quad_form(w, cov)), constraints)
        try:
            prob.solve(solver=cp.OSQP, verbose=False)
            raw = np.array(w.value, dtype=float)
        except Exception:
            raw = np.linalg.pinv(cov) @ excess_mu
    else:
        raw = np.linalg.pinv(cov) @ excess_mu
    raw = np.maximum(raw, 0)
    total = raw.sum()
    return raw / total if total > 1e-12 else np.ones(n) / n
```

3. K-sensitivity chart (out-of-sample Sharpe vs K) — not implemented at all:

```python
def k_sensitivity_sweep(
    model: dict,
    payload: dict | None = None,
    k_range: tuple | None = None,
    oos_fraction: float = 0.3,
) -> list[dict]:
    """
    For each K from 1 to K_max, build the max-Sharpe portfolio using
    in-sample data, evaluate realized Sharpe on held-out OOS period.
    """
    rets = model["returns"]
    n_obs = len(rets)
    split = int(n_obs * (1 - oos_fraction))
    rets_is = rets.iloc[:split]
    rets_oos = rets.iloc[split:]
    k_max = int(model["k_info"].get("rmt", 10))
    k_range = k_range or range(1, min(k_max + 3, rets.shape[1] - 1))
    rows = []
    for k in k_range:
        # Fit on in-sample
        from copy import deepcopy
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
        # Optimize on IS
        opt = optimize_portfolio(m_is, payload)
        w = np.array([r["weight"] for r in sorted(opt["weights"], key=lambda x: model["symbols"].index(x["ticker"]) if x["ticker"] in model["symbols"] else 9999)], dtype=float)
        if len(w) != len(model["symbols"]):
            continue
        # Evaluate on OOS
        oos_rets = rets_oos.reindex(columns=model["symbols"]).fillna(0.0).to_numpy(dtype=float)
        p_rets = oos_rets @ w
        sr = float(p_rets.mean() / max(p_rets.std(ddof=1), 1e-12) * math.sqrt(252))
        rows.append({"k": k, "oos_sharpe": sr, "oos_vol": float(p_rets.std() * math.sqrt(252)), "is_k_rmt": k == model["k_info"].get("rmt")})
    return rows
```

4. Turnover constraint — not implemented:

```python
# In optimize_portfolio(), add:
w_prev_raw = payload.get("previous_weights") or {}
to_max = float(number_like(payload.get("turnover_max"), 1.0) or 1.0)  # default: unconstrained

if cp is not None and isinstance(w_prev_raw, dict) and w_prev_raw:
    w_prev = np.array([float(w_prev_raw.get(s, 0.0)) for s in symbols], dtype=float)
    w_prev = w_prev / max(w_prev.sum(), 1e-12)
    # Add turnover constraint: sum |w - w_prev| <= 2 * to_max
    constraints.append(cp.norm1(w_var - w_prev) <= 2 * to_max)
```

5. Black-Litterman posterior not implemented. This is large, here is the core math:

```python
def black_litterman_posterior(
    cov: np.ndarray,
    w_market: np.ndarray,
    views: list[dict],  # [{"assets": {"AAPL": 0.5, "MSFT": -0.5}, "return": 0.05, "confidence": 0.7}]
    symbols: list[str],
    tau: float = 0.05,
    risk_aversion: float = 3.0,
) -> np.ndarray:
    """
    Black-Litterman posterior expected returns.
    Returns N x 1 posterior mu vector.
    """
    n = len(symbols)
    sym_idx = {s: i for i, s in enumerate(symbols)}
    # Prior: reverse-optimization from market weights
    mu_prior = risk_aversion * cov @ w_market

    if not views:
        return mu_prior

    Q_rows, q_vals, omega_diag = [], [], []
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
        # Omega_ii = tau * P_i Sigma P_i^T / confidence^2 (scales view uncertainty by confidence)
        omega_diag.append(tau * float(row @ cov @ row) / max(conf ** 2, 1e-6))

    P = np.array(Q_rows, dtype=float)   # Q x N
    q = np.array(q_vals, dtype=float)   # Q
    Omega = np.diag(omega_diag)          # Q x Q

    # BL posterior formula:
    # mu_post = [(tau*Sigma)^{-1} + P^T Omega^{-1} P]^{-1}
    #           * [(tau*Sigma)^{-1} mu_prior + P^T Omega^{-1} q]
    tau_sigma_inv = np.linalg.pinv(tau * cov)
    omega_inv = np.diag(1.0 / np.diag(Omega))
    precision = tau_sigma_inv + P.T @ omega_inv @ P
    rhs = tau_sigma_inv @ mu_prior + P.T @ omega_inv @ q
    mu_post = np.linalg.pinv(precision) @ rhs
    return mu_post
```

Wire into `optimize_portfolio`:

```python
bl_views = payload.get("bl_views") or []
w_market = np.array([model["market_caps"].get(s, 1.0) for s in symbols], dtype=float)
w_market /= max(w_market.sum(), 1e-12)
if bl_views:
    mu = black_litterman_posterior(cov, w_market, bl_views, symbols)
else:
    mu = model["returns"].mean().reindex(symbols).fillna(0.0).to_numpy(dtype=float) * 252
```

---

## FEATURE 7 — Bootstrap Validation

**Not done:**

1. Bai-Ng IC2 and IC3 formulas are wrong — currently hardcoded as IC1 × 1.15 and IC1 × 0.85 which is nonsense:

```python
def bai_ng_criteria(
    returns: pd.DataFrame,
    k_max: int = 15,
) -> list[dict]:
    """
    Bai and Ng (2002) IC1, IC2, IC3 criteria.
    Correct formulas from the paper.
    """
    x = returns.fillna(0.0).to_numpy(dtype=float)
    T, N = x.shape
    rows = []
    for r in range(0, min(k_max + 1, min(N, T) - 1)):
        if r == 0:
            ssr = float(np.sum(x ** 2))
        else:
            # Factor model residual sum of squares
            cov = np.cov(x, rowvar=False)
            vals, vecs = eig_sorted(cov)
            f = x @ vecs[:, :r]           # T x r factors
            b = vecs[:, :r]               # N x r loadings
            resid = x - f @ b.T
            ssr = float(np.sum(resid ** 2))
        nssr = ssr / max(N * T, 1)
        log_nssr = math.log(max(nssr, 1e-300))
        mn = min(N, T)
        nt = N * T
        # IC1: penalty = r * (N+T)/(NT) * ln(NT/(N+T))
        p1 = r * ((N + T) / max(nt, 1)) * math.log(max(nt / max(N + T, 1), 2))
        # IC2: penalty = r * (N+T)/(NT) * ln(min(N,T))
        p2 = r * ((N + T) / max(nt, 1)) * math.log(max(mn, 2))
        # IC3: penalty = r * ln(min(N,T)) / min(N,T)
        p3 = r * math.log(max(mn, 2)) / max(mn, 1)
        rows.append({
            "k": r,
            "IC1": log_nssr + p1,
            "IC2": log_nssr + p2,
            "IC3": log_nssr + p3,
        })
    # Mark recommended K for each criterion
    if rows:
        best_ic1 = min(rows, key=lambda x: x["IC1"])["k"]
        best_ic2 = min(rows, key=lambda x: x["IC2"])["k"]
        best_ic3 = min(rows, key=lambda x: x["IC3"])["k"]
        for row in rows:
            row["ic1_recommended"] = row["k"] == best_ic1
            row["ic2_recommended"] = row["k"] == best_ic2
            row["ic3_recommended"] = row["k"] == best_ic3
    return rows
```

Replace `_bai_ng_proxy` in feature_07 with a real call to this.

2. Block bootstrap not implemented — currently only case bootstrap:

```python
def block_bootstrap_sample(
    x: np.ndarray,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Circular block bootstrap: sample T/L blocks of length L with replacement."""
    T = x.shape[0]
    n_blocks = math.ceil(T / block_length)
    starts = rng.integers(0, T, size=n_blocks)
    indices = []
    for s in starts:
        idx = np.arange(s, s + block_length) % T  # circular wrap
        indices.extend(idx.tolist())
    return x[indices[:T]]
```

Wire into `bootstrap_validation`:

```python
bootstrap_type = str(payload.get("bootstrap_type") or "case").lower()
block_length = int(number_like(payload.get("block_length"), 10) or 10)
rng = np.random.default_rng(7)
for _ in range(b):
    if bootstrap_type == "block":
        sample_x = block_bootstrap_sample(x, block_length, rng)
    else:
        idx = rng.integers(0, len(x), len(x))
        sample_x = x[idx]
    sample = pd.DataFrame(sample_x, columns=rets.columns)
    # ... rest of loop unchanged
```

3. Real principal angles using SVD — `_principal_angle_proxy` is fake:

```python
def _principal_angles_from_scorecard(
    model: dict,
    cosines: list[list[float]],
    k: int,
) -> list[dict]:
    """
    Approximation of principal angles from bootstrap cosine distributions.
    For exact angles you need the bootstrap eigenvector matrices themselves.
    """
    rows = []
    for j in range(k):
        mean_cos = float(np.mean(cosines[j]))
        # largest principal angle in the bundle approximated as arccos of min cosine
        p05_cos = float(np.percentile(cosines[j], 5))
        rows.append({
            "component": f"PC{j+1}",
            "mean_cosine": mean_cos,
            "p05_cosine": p05_cos,
            "approx_max_principal_angle_deg": float(np.degrees(np.arccos(np.clip(p05_cos, -1, 1)))),
        })
    return rows
```

---

## FEATURE 8 — Contagion Monitor

**Not done:**

1. Rolling group correlation time series — `group_rows` is only a current snapshot, not a time series. The spec shows rolling line charts per sector.

```python
def rolling_group_residual_corr(
    model: dict,
    payload: dict | None = None,
    window: int = 63,
    step: int = 5,
) -> list[dict]:
    payload = payload or {}
    resid = residual_matrix(model)
    sectors = model["sectors"]
    rows = []
    for end in range(window, len(resid) + 1, step):
        sub = resid.iloc[end - window: end]
        corr = sub.corr().fillna(0.0)
        date_str = str(pd.Timestamp(resid.index[end - 1]).date())
        for sector in sorted(set(sectors.values())):
            cols = [s for s in corr.columns if sectors.get(s) == sector]
            if len(cols) < 2:
                continue
            c = corr.loc[cols, cols].to_numpy(dtype=float)
            upper = c[np.triu_indices_from(c, 1)]
            rows.append({
                "date": date_str,
                "group": sector,
                "avg_residual_corr": float(upper.mean()),
                "asset_count": len(cols),
            })
    return rows
```

---

## FEATURE 9 — Stress Scenarios

**Not done:**

1. Historical worst-day scenarios (5 worst single-day PC realizations) not implemented — only parametric:

```python
def historical_worst_day_scenarios(
    model: dict,
    payload: dict | None = None,
    n_worst: int = 5,
) -> list[dict]:
    """For each PC, find the n_worst historical daily realizations and replay portfolio P&L."""
    w = portfolio_weights(model["symbols"], payload).reindex(model["symbols"]).fillna(0.0).to_numpy(dtype=float)
    f = factor_returns(model)
    rows = []
    for j, col in enumerate(f.columns):
        worst_idx = f[col].nsmallest(n_worst).index
        for date in worst_idx:
            shock = f.loc[date].to_numpy(dtype=float)
            asset_impacts = model["eigenvectors"][:, :model["k"]] @ shock
            pnl = float(w @ asset_impacts)
            rows.append({
                "scenario_type": "historical_worst_day",
                "component": col,
                "date": str(pd.Timestamp(date).date()),
                "realized_factor_return": float(f.loc[date, col]),
                "portfolio_pnl_pct": pnl,
            })
    return sorted(rows, key=lambda r: r["portfolio_pnl_pct"])
```

2. Joint multi-PC shock not implemented:

```python
def joint_scenario_pnl(
    model: dict,
    shocks: dict,  # {"PC1": 2.0, "PC3": -1.5} — signed sigma multiples
    payload: dict | None = None,
) -> dict:
    """User-specified compound scenario: shock multiple PCs simultaneously."""
    w = portfolio_weights(model["symbols"], payload).reindex(model["symbols"]).fillna(0.0).to_numpy(dtype=float)
    f = factor_returns(model)
    stds = f.std().replace(0, np.nan).fillna(1e-6).to_numpy(dtype=float)
    k = model["k"]
    shock_vec = np.zeros(k)
    for label, mult in shocks.items():
        idx = int(str(label).replace("PC", "")) - 1
        if 0 <= idx < k:
            shock_vec[idx] = float(mult) * stds[idx]
    asset_impacts = model["eigenvectors"][:, :k] @ shock_vec
    pnl = float(w @ asset_impacts)
    contributions = [
        {"ticker": model["symbols"][i], "pnl_contribution": float(w[i] * asset_impacts[i])}
        for i in range(len(w))
    ]
    return {
        "shocks": shocks,
        "portfolio_pnl_pct": pnl,
        "interaction_note": "Interaction effects present when portfolio has joint exposure to multiple shocked PCs",
        "contributions": sorted(contributions, key=lambda r: r["pnl_contribution"]),
    }
```

---

## FEATURE 10 — Cross-Asset

This is essentially a stub. The entire implementation is a simple equity-only block classifier with a `status: "partial"` flag. Everything in the spec for Feature 10 is missing:

- DCC-GARCH cross-block estimation
- Asset-class-specific estimators per block (FX=EWMA, commodities=OAS, crypto=MCD)
- Calendar alignment (equity-day-only vs 7-day)
- Cornish-Fisher adjusted MP threshold for crypto
- FX hedging at the covariance level
- Block correlation regime monitor (CASCI)
- Crypto volume filter / wash trading detection
- Student-t EM for crypto block

This is a full standalone build. The skeleton to wire in:

```python
# In feature_10.py / core/cross_asset.py

def detect_asset_class(symbol: str) -> str:
    s = symbol.upper()
    if any(c in s for c in ["BTC", "ETH", "SOL", "BNB", "XRP", "AVAX"]):
        return "crypto"
    if s.endswith("=X") or s in {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD"}:
        return "fx"
    if s in {"GC_F", "SI_F", "CL_F", "NG_F", "HG_F", "ZC_F", "ZW_F", "ZS_F"}:
        return "commodity"
    if s in {"SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "USO"}:
        return "index_etf"
    return "equity"


def block_covariance(
    returns_block: pd.DataFrame,
    asset_class: str,
    ewma_lambda: float = 0.94,
) -> tuple[np.ndarray, dict]:
    """Apply the per-block estimator as specified."""
    if asset_class == "fx":
        return covariance_estimator(returns_block, "ewma", ewma_lambda=ewma_lambda)
    elif asset_class == "commodity":
        return covariance_estimator(returns_block, "oas")
    elif asset_class == "crypto":
        return covariance_estimator(returns_block, "mcd")
    else:
        return covariance_estimator(returns_block, "ledoit_wolf")


def assemble_block_covariance(
    returns: pd.DataFrame,
    symbols: list[str],
    cross_shrinkage: float = 0.6,
) -> tuple[np.ndarray, dict]:
    """
    Assemble the unified N x N covariance matrix:
    - diagonal blocks: per-class dedicated estimator
    - off-diagonal blocks: shrunk toward zero (simple approach before DCC)
    """
    classes = {s: detect_asset_class(s) for s in symbols}
    unique_classes = sorted(set(classes.values()))
    n = len(symbols)
    unified = np.zeros((n, n))
    sym_idx = {s: i for i, s in enumerate(symbols)}

    for cls in unique_classes:
        block_syms = [s for s in symbols if classes[s] == cls]
        if not block_syms:
            continue
        idx = [sym_idx[s] for s in block_syms]
        block_rets = returns[block_syms].fillna(0.0)
        cov_block, _ = block_covariance(block_rets, cls)
        for ii, i in enumerate(idx):
            for jj, j in enumerate(idx):
                unified[i, j] = cov_block[ii, jj]

    # Cross-block: sample covariance shrunk toward 0
    full_cov = np.cov(returns[symbols].fillna(0.0).to_numpy(dtype=float), rowvar=False)
    for ci, cls_a in enumerate(unique_classes):
        for cj, cls_b in enumerate(unique_classes):
            if cls_a >= cls_b:
                continue
            syms_a = [s for s in symbols if classes[s] == cls_a]
            syms_b = [s for s in symbols if classes[s] == cls_b]
            for sa in syms_a:
                for sb in syms_b:
                    ia, ib = sym_idx[sa], sym_idx[sb]
                    # Shrink cross-block entries toward 0
                    unified[ia, ib] = (1 - cross_shrinkage) * full_cov[ia, ib]
                    unified[ib, ia] = unified[ia, ib]

    return unified, {"estimator": "block_aware", "cross_shrinkage": cross_shrinkage}
```

---

## FEATURE 11 — Latent Liquidity

Partially implemented but several gaps:

1. Pastor-Stambaugh gamma not implemented (only Amihud):

```python
def pastor_stambaugh_gamma(
    returns: pd.DataFrame,
    dollar_volume: pd.DataFrame,
    market_returns: pd.Series,
    window: int = 21,
) -> pd.DataFrame:
    """
    Pastor-Stambaugh (2003) liquidity measure.
    gamma_i = coefficient on sign(R_excess) * DollarVolume in:
    R_{i,t+1}^e = theta + phi*R_{i,t} + gamma * sign(R_{i,t}^e) * DollarVol_{i,t} + eps
    """
    gammas = {}
    for ticker in returns.columns:
        r = returns[ticker].dropna()
        dv = dollar_volume[ticker].reindex(r.index).fillna(method="ffill")
        rm = market_returns.reindex(r.index).fillna(0.0)
        r_excess = r - rm
        if len(r_excess) < window + 5:
            continue
        rolling_gammas = []
        for end in range(window, len(r_excess)):
            sub_re = r_excess.iloc[end - window: end]
            sub_r = r.iloc[end - window: end]
            sub_dv = dv.iloc[end - window: end]
            y = sub_re.shift(-1).iloc[:-1].to_numpy(dtype=float)
            x1 = sub_r.iloc[:-1].to_numpy(dtype=float)
            signed_vol = (np.sign(sub_re.iloc[:-1]) * sub_dv.iloc[:-1]).to_numpy(dtype=float)
            X = np.column_stack([np.ones(len(y)), x1, signed_vol])
            valid = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
            if valid.sum() < 5:
                rolling_gammas.append(np.nan)
                continue
            coef = np.linalg.lstsq(X[valid], y[valid], rcond=None)[0]
            rolling_gammas.append(float(coef[2]))
        gammas[ticker] = pd.Series(rolling_gammas, index=r_excess.index[window:])
    return pd.DataFrame(gammas)
```

2. Kyle's lambda daily approximation not implemented:

```python
def kyle_lambda_daily(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """
    Daily approximation of Kyle's lambda from OHLCV.
    lambda_i = (High - Low) / (2 * Volume * sqrt(2/pi))
    Hasbrouck (2009) daily proxy.
    """
    from .data_loader import load_market_ohlcv
    df = load_market_ohlcv()
    results = {}
    for ticker in ohlcv.columns if hasattr(ohlcv, 'columns') else []:
        sub = df[df["Ticker"] == ticker][["Date", "High", "Low", "Volume"]].set_index("Date")
        if sub.empty:
            continue
        high = pd.to_numeric(sub["High"], errors="coerce")
        low = pd.to_numeric(sub["Low"], errors="coerce")
        vol = pd.to_numeric(sub["Volume"], errors="coerce").replace(0, np.nan)
        lam = (high - low) / (2 * vol * math.sqrt(2 / math.pi))
        results[ticker] = lam
    return pd.DataFrame(results)
```

3. Newey-West standard errors on liquidity beta not implemented — currently plain OLS SE:

```python
def newey_west_se(
    X: np.ndarray,
    residuals: np.ndarray,
    coef_idx: int = 1,
    n_lags: int = 3,
) -> float:
    """Newey-West HAC standard error for coefficient at coef_idx."""
    n = X.shape[0]
    XtX_inv = np.linalg.pinv(X.T @ X)
    # Long-run variance matrix S
    S = np.zeros((X.shape[1], X.shape[1]))
    # Lag 0
    for t in range(n):
        S += (residuals[t] ** 2) * np.outer(X[t], X[t])
    S /= n
    # Lags 1 to L (Bartlett kernel)
    for lag in range(1, n_lags + 1):
        w = 1.0 - lag / (n_lags + 1)
        gamma = np.zeros((X.shape[1], X.shape[1]))
        for t in range(lag, n):
            gamma += residuals[t] * residuals[t - lag] * np.outer(X[t], X[t - lag])
        gamma /= n
        S += w * (gamma + gamma.T)
    V = XtX_inv @ S @ XtX_inv / n
    return float(math.sqrt(max(V[coef_idx, coef_idx], 0)))
```

Replace the plain SE in `liquidity_outputs` with this.

---

## Summary Table

| Feature | Status | Priority gaps                                                                                     |
| ------- | ------ | ------------------------------------------------------------------------------------------------- |
| F1      | ~70%   | σ² fitting wrong, outlier preprocessing missing, blend reconstruction missing                     |
| F2      | ~60%   | Promax missing, HPCA missing, R² missing, Hoyer missing                                           |
| F3      | ~65%   | Active risk attribution missing, rolling per-factor decomposition missing                         |
| F4      | ~50%   | Volume-time missing, break-even Z missing, SE on OU params missing, signal decay missing          |
| F5      | ~60%   | Percentile ranks missing, loading evolution heatmap missing, principal angles missing             |
| F6      | ~40%   | ERC missing, MSP explicit missing, K-sensitivity missing, BL missing, turnover constraint missing |
| F7      | ~55%   | IC2/IC3 formulas wrong, block bootstrap missing, subsampling missing                              |
| F8      | ~65%   | Rolling group time series missing                                                                 |
| F9      | ~60%   | Historical worst-day missing, joint multi-PC shock missing                                        |
| F10     | ~15%   | Almost everything missing — treat as greenfield                                                   |
| F11     | ~65%   | PS gamma missing, Kyle's lambda missing, NW standard errors missing                               |

**Highest priority order to fix:** F6 (optimization, most user-facing) → F1 (σ² fitting, everything downstream depends on it) → F7 (IC criteria are factually wrong) → F4 (volume-time is the main Avellaneda improvement) → F10 (stub, needs proper block architecture).
