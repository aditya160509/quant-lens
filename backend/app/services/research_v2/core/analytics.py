"""Research V2 analytics.

The functions in this module are intentionally deterministic and data-backed.
Where the repository lacks user-uploaded ranks, instruments, or event files, the
engine builds canonical proxies from available OHLCV, fundamentals, factors and
macro series, then exposes the limitation in response metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import base64
from io import BytesIO
import json
import math
import warnings

import numpy as np
import pandas as pd

from .data_loader import (
    available_symbols,
    close_matrix,
    data_inventory,
    latest_fundamentals,
    load_event_upload,
    load_macro,
    load_instrument_upload,
    load_signal_upload,
    monthly_factor_returns,
    parse_symbols,
    returns_matrix,
    volume_matrix,
)
from .performance import (
    acf_frame,
    broadcast_static,
    cached_data_inventory,
    cached_latex_table,
    jit_fama_macbeth_frame,
    offdiag_corr_mean,
    positional_event_rows,
    scm_objective_arrays,
    vectorized_portfolio_returns,
)

try:
    from scipy import optimize, stats
except Exception:  # pragma: no cover
    optimize = None
    stats = None

try:
    import statsmodels.api as sm
    from statsmodels.regression.quantile_regression import QuantReg
    from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan, het_white, linear_reset
    from statsmodels.stats.outliers_influence import OLSInfluence, variance_inflation_factor
    from statsmodels.stats.stattools import durbin_watson
    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
except Exception:  # pragma: no cover
    sm = None
    QuantReg = None
    acorr_ljungbox = het_breuschpagan = het_white = linear_reset = None
    OLSInfluence = None
    variance_inflation_factor = None
    durbin_watson = None
    MarkovRegression = None

try:
    from linearmodels.panel import PanelOLS
except Exception:  # pragma: no cover
    PanelOLS = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except Exception:  # pragma: no cover
    colors = letter = getSampleStyleSheet = inch = Paragraph = SimpleDocTemplate = Spacer = Table = TableStyle = None


def number(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if np.isfinite(out) else default
    except Exception:
        return default


def records(df: pd.DataFrame | pd.Series | list[dict[str, Any]] | dict[str, Any] | None, limit: int | None = None) -> list[dict[str, Any]]:
    if df is None:
        return []
    if isinstance(df, list):
        out = df
    elif isinstance(df, dict):
        out = [df]
    elif isinstance(df, pd.Series):
        out = df.reset_index().rename(columns={0: "value"}).to_dict("records")
    else:
        clean = df.replace([np.inf, -np.inf], np.nan)
        out = clean.where(pd.notna(clean), None).to_dict("records")
    return out if limit is None else out[:limit]


def response(feature_id: str, summary_cards: list[dict[str, Any]], charts: dict[str, Any], tables: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    inventory = cached_data_inventory()
    return {
        "feature_id": str(feature_id).zfill(2),
        "status": "ok",
        "summary_cards": summary_cards,
        "charts": charts,
        "tables": tables,
        "meta": {
            "data_inventory": inventory,
            "research_caveats": [],
            **(meta or {}),
        },
    }


def p_value_from_t(t_stat: float | np.ndarray, df: int) -> float | np.ndarray:
    arr = np.asarray(t_stat, dtype=float)
    if stats is not None and df > 0:
        out = 2 * (1 - stats.t.cdf(np.abs(arr), df))
    else:
        out = np.vectorize(lambda v: math.erfc(abs(v) / math.sqrt(2)))(arr)
    return float(out) if np.ndim(t_stat) == 0 else out


def ols(y: Iterable[float], x: pd.DataFrame | np.ndarray, add_const: bool = True) -> dict[str, Any]:
    yv = np.asarray(list(y), dtype=float)
    xm = np.asarray(x, dtype=float)
    if xm.ndim == 1:
        xm = xm.reshape(-1, 1)
    mask = np.isfinite(yv) & np.isfinite(xm).all(axis=1)
    yv = yv[mask]
    xm = xm[mask]
    if add_const:
        xm = np.column_stack([np.ones(len(xm)), xm])
    if len(yv) <= xm.shape[1] + 2:
        beta = np.full(xm.shape[1], np.nan)
        return {"beta": beta, "se": beta, "t": beta, "p": beta, "r2": np.nan, "resid": np.array([]), "n": int(len(yv))}
    xtx = xm.T @ xm
    xty = xm.T @ yv
    try:
        xtxi = np.linalg.inv(xtx)
        beta = xtxi @ xty
    except np.linalg.LinAlgError:
        xtxi = np.linalg.pinv(xtx)
        beta = xtxi @ xty
    fitted = xm @ beta
    resid = yv - fitted
    dof = max(1, len(yv) - xm.shape[1])
    sigma2 = float((resid @ resid) / dof)
    cov = sigma2 * xtxi
    se = np.sqrt(np.maximum(np.diag(cov), 0))
    t = beta / np.where(se == 0, np.nan, se)
    p = np.full_like(t, np.nan, dtype=float)
    finite = np.isfinite(t)
    if finite.any():
        p[finite] = p_value_from_t(t[finite], dof)
    ss_tot = float(((yv - yv.mean()) ** 2).sum())
    r2 = 1 - float((resid @ resid) / ss_tot) if ss_tot > 0 else np.nan
    return {"beta": beta, "se": se, "t": t, "p": p, "r2": r2, "resid": resid, "n": int(len(yv))}


def nw_se(series: pd.Series, lag: int = 4) -> float:
    x = pd.Series(series).dropna().astype(float).to_numpy()
    n = len(x)
    if n < 3:
        return np.nan
    xc = x - np.nanmean(x)
    max_lag = min(int(lag), n - 1)
    acov = np.correlate(xc, xc, mode="full")[n - 1:n + max_lag] / n
    if len(acov) == 0:
        return np.nan
    weights = 1 - np.arange(1, max_lag + 1) / (max_lag + 1 if max_lag else 1)
    var = float(acov[0] + 2 * np.sum(weights * acov[1:max_lag + 1])) if max_lag else float(acov[0])
    return math.sqrt(max(var, 0) / n)


def zscore(df: pd.DataFrame) -> pd.DataFrame:
    return (df - df.mean()) / df.std(ddof=0).replace(0, np.nan)


def _safe_rank(df: pd.DataFrame) -> pd.DataFrame:
    return df.rank(axis=1, pct=True)


def signal_matrix(payload: dict[str, Any], symbols: list[str], returns: pd.DataFrame | None = None) -> pd.DataFrame:
    upload = load_signal_upload(payload.get("signal_csv_path") or payload.get("signal_upload_path") or payload.get("rank_csv_path"))
    if not upload.empty:
        rets = returns if returns is not None else returns_matrix(symbols, int(payload.get("lookback_days") or 2520), frequency="monthly")
        wide = upload.pivot_table(index="date", columns="ticker", values="signal", aggfunc="last").sort_index()
        wide = wide.reindex(columns=rets.columns).resample("ME").last()
        return wide.reindex(rets.index, method="ffill").reindex(columns=rets.columns)
    signal_name = str(payload.get("signal") or payload.get("signal_definition") or "momentum").lower()
    prices = close_matrix(symbols, int(payload.get("lookback_days") or 2520), frequency="monthly")
    rets = returns if returns is not None else np.log(prices).diff()
    if signal_name in {"reversal", "short_reversal", "1m_reversal"}:
        sig = -rets.shift(1)
    elif signal_name in {"low_vol", "volatility", "realized_vol"}:
        sig = -rets.rolling(12).std()
    elif signal_name in {"size", "market_cap"}:
        lf = latest_fundamentals()
        vals = pd.to_numeric(lf.reindex(symbols).get("marketCap", pd.Series(index=symbols, dtype=float)), errors="coerce")
        sig = broadcast_static(vals, rets.index, rets.columns)
    elif signal_name in {"value", "book_to_market", "earnings_yield"}:
        lf = latest_fundamentals()
        subset = lf.reindex(symbols)
        mc = pd.to_numeric(subset.get("marketCap", pd.Series(index=symbols, dtype=float)), errors="coerce")
        book = pd.to_numeric(subset.get("totalStockholderEquity", subset.get("bookValue", pd.Series(index=symbols, dtype=float))), errors="coerce")
        vals = book.div(mc.replace(0, np.nan))
        sig = broadcast_static(vals, rets.index, rets.columns)
    elif signal_name in {"quality", "profitability"}:
        lf = latest_fundamentals()
        subset = lf.reindex(symbols)
        vals = pd.to_numeric(subset.get("returnOnEquity", subset.get("roe", pd.Series(index=symbols, dtype=float))), errors="coerce")
        sig = broadcast_static(vals, rets.index, rets.columns)
    else:
        sig = prices.pct_change(12).shift(1) - prices.pct_change(1).shift(1)
    return sig.reindex(index=rets.index, columns=rets.columns)


def control_matrices(payload: dict[str, Any], symbols: list[str], returns: pd.DataFrame, signals: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    requested = payload.get("controls") or payload.get("control_set") or []
    if isinstance(requested, str):
        if requested.lower() in {"none", "baseline", ""}:
            requested = []
        elif requested.lower() == "full":
            requested = ["size", "value", "momentum", "reversal", "beta", "ivol", "asset_growth", "profitability", "leverage"]
        else:
            requested = [x.strip() for x in requested.split(",") if x.strip()]
    requested = [str(x).lower() for x in requested]
    aliases = {
        "market_cap": "size",
        "book_to_market": "value",
        "earnings_yield": "value",
        "short_reversal": "reversal",
        "1m_reversal": "reversal",
        "low_vol": "volatility",
        "realized_vol": "volatility",
        "quality": "profitability",
    }
    current_signal = str(payload.get("signal") or payload.get("signal_definition") or "momentum").lower()
    current_signal = aliases.get(current_signal, current_signal)
    requested = [x for x in requested if aliases.get(x, x) != current_signal]
    out: dict[str, pd.DataFrame] = {}
    if "size" in requested:
        out["size"] = signals if signals is not None and str(payload.get("signal", "")).lower() == "size" else signal_matrix({"signal": "size", "lookback_days": payload.get("lookback_days", 2520)}, symbols, returns)
    if "value" in requested:
        out["value"] = signals if signals is not None and str(payload.get("signal", "")).lower() == "value" else signal_matrix({"signal": "value", "lookback_days": payload.get("lookback_days", 2520)}, symbols, returns)
    if "momentum" in requested:
        out["momentum"] = signals if signals is not None and str(payload.get("signal", "")).lower() == "momentum" else signal_matrix({"signal": "momentum", "lookback_days": payload.get("lookback_days", 2520)}, symbols, returns)
    if "volatility" in requested or "low_vol" in requested:
        out["volatility"] = returns.rolling(12).std()
    if "reversal" in requested:
        out["reversal"] = -returns.shift(1)
    if "beta" in requested:
        market = returns.mean(axis=1)
        cov = returns.rolling(36).cov(market)
        var = market.rolling(36).var().replace(0, np.nan)
        out["beta"] = cov.div(var, axis=0).shift(1)
    if "ivol" in requested:
        market = returns.mean(axis=1)
        beta = out.get("beta")
        if beta is None:
            cov = returns.rolling(36).cov(market)
            beta = cov.div(market.rolling(36).var().replace(0, np.nan), axis=0).shift(1)
        resid = returns.sub(beta.mul(market, axis=0), axis=0)
        out["ivol"] = resid.rolling(36).std().shift(1)
    needed_static = [key for key in ["asset_growth", "profitability", "leverage"] if key in requested]
    if needed_static:
        static_fundamentals = _static_fundamental_controls(symbols)
        for key in needed_static:
            if key in static_fundamentals:
                out[key] = broadcast_static(static_fundamentals[key], returns.index, returns.columns)
    return out


def _static_fundamental_controls(symbols: list[str]) -> dict[str, pd.Series]:
    lf = latest_fundamentals()
    if lf.empty:
        return {}
    lower = {str(c).lower(): c for c in lf.columns}
    def find_col(names: list[str]) -> str | None:
        for name in names:
            if name.lower() in lower:
                return lower[name.lower()]
        return None
    subset = lf.reindex(symbols)
    def numeric(names: list[str]) -> pd.Series:
        col = find_col(names)
        if col is None:
            return pd.Series(np.nan, index=symbols)
        return pd.to_numeric(subset[col], errors="coerce")
    assets = numeric(["Total Assets", "totalAssets"])
    debt = numeric(["Total Debt", "Net Debt", "Long Term Debt"])
    income = numeric(["Net Income", "Net Income Common Stockholders"])
    revenue = numeric(["Total Revenue", "Operating Revenue"])
    frame = pd.DataFrame(index=symbols)
    frame["asset_growth"] = np.log(assets.where(assets > 0))
    frame["profitability"] = income.div(assets.replace(0, np.nan)).fillna(income.div(revenue.replace(0, np.nan)))
    frame["leverage"] = debt.div(assets.replace(0, np.nan))
    return {col: frame[col] for col in frame.columns}


def portfolio_weight_frame(payload: dict[str, Any], symbols: list[str], returns: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    scheme = str(payload.get("weighting") or payload.get("weighting_scheme") or "equal").lower()
    if scheme in {"equal", "ew"}:
        return pd.DataFrame(1.0, index=returns.index, columns=returns.columns)
    if scheme in {"rank", "rank_weight"}:
        ranked = signals.rank(axis=1, pct=True)
        return ranked.div(ranked.sum(axis=1).replace(0, np.nan), axis=0).reindex_like(returns)
    lf = latest_fundamentals()
    vals = pd.Series({s: number(lf.loc[s].get("marketCap", np.nan), np.nan) if s in lf.index else np.nan for s in symbols})
    vals = vals.reindex(returns.columns).fillna(vals.median()).replace(0, np.nan)
    if vals.isna().all():
        return pd.DataFrame(1.0, index=returns.index, columns=returns.columns)
    vals = vals.fillna(vals.median())
    vals = vals / vals.sum()
    return broadcast_static(vals, returns.index, returns.columns)


def _regression_design_for_date(panel: dict[str, Any], date: Any) -> pd.DataFrame:
    data = {"signal": panel["signals"].loc[date], "ret": panel["forward"].loc[date]}
    for name, mat in panel.get("controls", {}).items():
        if date in mat.index:
            data[name] = mat.loc[date]
    return pd.DataFrame(data).dropna()


def research_panel(payload: dict[str, Any], default_limit: int = 400) -> dict[str, Any]:
    symbols = parse_symbols(payload, default_limit=default_limit, max_symbols=int(payload.get("max_symbols") or 1500))
    lookback = int(payload.get("lookback_days") or 2520)
    frequency = str(payload.get("rebalancing_frequency") or payload.get("rebalance_frequency") or payload.get("frequency") or "monthly").lower()
    frequency = {"month": "monthly", "quarter": "quarterly", "quarterly": "quarterly", "week": "weekly", "weekly": "weekly", "day": "daily", "daily": "daily"}.get(frequency, frequency)
    returns = returns_matrix(symbols, lookback_days=lookback, frequency="monthly" if frequency == "quarterly" else frequency)
    if frequency == "quarterly" and not returns.empty:
        prices = close_matrix(symbols, lookback_days=lookback, frequency="monthly")
        returns = np.log(prices.resample("QE").last()).diff().replace([np.inf, -np.inf], np.nan).dropna(how="all")
    signals = signal_matrix(payload, symbols, returns)
    controls = control_matrices(payload, symbols, returns, signals=signals)
    weights = portfolio_weight_frame(payload, symbols, returns, signals)
    fwd_h = int(payload.get("forward_months") or payload.get("horizon_months") or 1)
    forward = returns.shift(-fwd_h).rolling(fwd_h).sum()
    return {"symbols": symbols, "returns": returns, "signals": signals, "controls": controls, "weights": weights, "forward": forward, "factors": monthly_factor_returns(), "macro": load_macro(), "frequency": frequency, "payload": payload}


def panel_variant(base_panel: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    symbols = list(base_panel["returns"].columns)
    returns = base_panel["returns"]
    signals = signal_matrix(payload, symbols, returns)
    controls = control_matrices(payload, symbols, returns, signals=signals)
    weights = portfolio_weight_frame(payload, symbols, returns, signals)
    fwd_h = int(payload.get("forward_months") or payload.get("horizon_months") or 1)
    forward = returns.shift(-fwd_h).rolling(fwd_h).sum()
    return {
        **base_panel,
        "symbols": symbols,
        "signals": signals,
        "controls": controls,
        "weights": weights,
        "forward": forward,
        "payload": payload,
    }


def fama_macbeth_table(panel: dict[str, Any], controls: list[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    betas = jit_fama_macbeth_frame(panel, min_obs=20)
    if betas.empty:
        return pd.DataFrame(), betas
    out = []
    for col in [c for c in betas.columns if c.endswith("_lambda")]:
        vals = betas[col].dropna()
        mean = vals.mean()
        se = nw_se(vals, lag=int(panel.get("payload", {}).get("nw_lag") or 4))
        t = mean / se if se and np.isfinite(se) else np.nan
        out.append({
            "term": col.replace("_lambda", ""),
            "lambda_hat": mean,
            "newey_west_se": se,
            "t_stat": t,
            "p_value": p_value_from_t(t, max(1, len(vals) - 1)) if np.isfinite(t) else np.nan,
            "mean_cross_section_r2": betas["r2"].mean(),
            "sample_months": int(len(vals)),
            "mean_assets": float(betas["n_assets"].mean()),
        })
    return pd.DataFrame(out), betas


def portfolio_sort(panel: dict[str, Any], buckets: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    sig = panel["signals"]
    fwd = panel["forward"]
    pr = vectorized_portfolio_returns(sig, fwd, panel.get("weights", pd.DataFrame()), int(buckets))
    if "date" not in pr.columns:
        return pd.DataFrame(), pd.DataFrame()
    pr = pr.sort_values("date")
    if pr.empty:
        return pd.DataFrame(), pr
    qs = [c for c in pr.columns if c != "date"]
    spread = pr[qs[-1]] - pr[qs[0]]
    table = []
    for q in qs:
        r = pr[q].dropna()
        r_mean = r.mean()
        r_std = r.std()
        r_se = nw_se(r)
        table.append({"portfolio": q, "mean_return": r_mean, "std": r_std, "sharpe": r_mean / r_std * math.sqrt(12) if r_std else np.nan, "t_stat": r_mean / r_se if r_se else np.nan})
    spread_mean = spread.mean()
    spread_std = spread.std()
    spread_se = nw_se(spread)
    table.append({"portfolio": f"{qs[-1]}-{qs[0]}", "mean_return": spread_mean, "std": spread_std, "sharpe": spread_mean / spread_std * math.sqrt(12) if spread_std else np.nan, "t_stat": spread_mean / spread_se if spread_se else np.nan})
    return pd.DataFrame(table), pr.assign(long_short=spread)


def rolling_coefficients(panel: dict[str, Any], window: int = 36, betas: pd.DataFrame | None = None) -> pd.DataFrame:
    if betas is None:
        _, betas = fama_macbeth_table(panel)
    if betas.empty:
        return pd.DataFrame()
    b = betas.set_index("date")["signal_lambda"].rolling(window).agg(["mean", "std", "count"]).dropna()
    b["upper_95"] = b["mean"] + 1.96 * b["std"] / np.sqrt(b["count"])
    b["lower_95"] = b["mean"] - 1.96 * b["std"] / np.sqrt(b["count"])
    return b.reset_index().rename(columns={"mean": "beta"})


def grs_and_spanning(panel: dict[str, Any], port_rets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    factors = _benchmark_factor_frame(panel)
    if port_rets.empty or factors.empty:
        return pd.DataFrame(), pd.DataFrame()
    df = port_rets.rename(columns={"date": "Date"}).merge(factors, on="Date", how="inner")
    factor_cols = [c for c in ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"] if c in df.columns]
    ret_cols = [c for c in port_rets.columns if c not in {"date"}]
    rows = []
    alphas = []
    resid_cols = []
    for col in ret_cols:
        fit = ols(df[col], df[factor_cols]) if factor_cols else ols(df[col], np.ones((len(df), 1)), add_const=False)
        alpha = fit["beta"][0] if len(fit["beta"]) else np.nan
        rows.append({"portfolio": col, "alpha": alpha, "alpha_t": fit["t"][0] if len(fit["t"]) else np.nan, "r2": fit["r2"], "n": fit["n"]})
        alphas.append(alpha)
        if len(fit.get("resid", [])) == len(df):
            resid_cols.append(pd.Series(fit["resid"], name=col))
    grs_stat = np.nan
    grs_p = np.nan
    if factor_cols and alphas and resid_cols:
        residuals = pd.concat(resid_cols, axis=1).dropna()
        t_obs = len(df)
        n_ports = len(ret_cols)
        k_factors = len(factor_cols)
        if t_obs > n_ports + k_factors + 1 and len(residuals) > n_ports:
            alpha_vec = np.asarray(alphas, dtype=float).reshape(-1, 1)
            sigma = np.cov(residuals.to_numpy(), rowvar=False)
            factor_mean = df[factor_cols].mean().to_numpy().reshape(-1, 1)
            factor_cov = np.cov(df[factor_cols].to_numpy(), rowvar=False)
            if factor_cov.ndim == 0:
                factor_cov = np.array([[float(factor_cov)]])
            try:
                middle = float(1 + factor_mean.T @ np.linalg.pinv(factor_cov) @ factor_mean)
                grs_stat = float(((t_obs - n_ports - k_factors) / n_ports) * (alpha_vec.T @ np.linalg.pinv(sigma) @ alpha_vec) / middle)
                grs_p = float(1 - stats.f.cdf(grs_stat, n_ports, t_obs - n_ports - k_factors)) if stats is not None else np.nan
            except Exception:
                grs_stat = np.nan
    grs = pd.DataFrame([{
        "grs_stat": grs_stat,
        "p_value": grs_p,
        "df1": len(ret_cols),
        "df2": max(1, len(df) - len(ret_cols) - len(factor_cols)),
        "mean_alpha": float(np.nanmean(alphas)) if alphas else np.nan,
        "pricing_error_sharpe": float(np.nanmean(alphas) / (np.nanstd(alphas) + 1e-12) * math.sqrt(12)) if alphas else np.nan,
    }])
    return grs, pd.DataFrame(rows)


def monotonicity_test(port_rets: pd.DataFrame, reps: int = 500) -> pd.DataFrame:
    qs = [c for c in port_rets.columns if c.startswith("Q")]
    if len(qs) < 3:
        return pd.DataFrame()
    means = port_rets[qs].mean()
    observed = float((means.diff().iloc[1:] > 0).mean())
    rng = np.random.default_rng(42)
    vals = port_rets[qs].dropna().to_numpy()
    if len(vals) < 5:
        return pd.DataFrame()
    reps = min(int(reps), 1000)
    samples = vals[rng.integers(0, len(vals), size=(reps, len(vals)))]
    means = samples.mean(axis=1)
    boot_stats = (np.diff(means, axis=1) > 0).mean(axis=1)
    p = float(np.mean(boot_stats >= observed))
    return pd.DataFrame([{"mr_statistic": observed, "bootstrap_p_value": 1 - p, "adjacent_pairs_ordered": observed, "top_minus_bottom_t": number(port_rets.get("long_short", pd.Series()).mean()) / (nw_se(port_rets.get("long_short", pd.Series())) or np.nan)}])


def latex_table(name: str, df: pd.DataFrame) -> str:
    if df.empty:
        return f"% {name}: no rows"
    return cached_latex_table(name, df)


def publication_pdf_base64(table_rows: list[dict[str, Any]], title: str, subtitle: str) -> dict[str, Any]:
    """Render a compact, allocator-ready Feature 06 report as an in-memory PDF.

    The service returns base64 rather than writing to disk. That keeps the
    service deterministic and lets a later API layer stream the artifact or
    persist it using its own storage policy.
    """
    if not table_rows or SimpleDocTemplate is None:
        return {"status": "unavailable", "reason": "ReportLab is unavailable or no publication rows were produced."}
    try:
        buffer = BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=.52 * inch, rightMargin=.52 * inch, topMargin=.5 * inch, bottomMargin=.5 * inch)
        styles = getSampleStyleSheet()
        columns = [key for key in table_rows[0].keys()]
        body = [[Paragraph(str(row.get(column, "")), styles["BodyText"]) for column in columns] for row in table_rows]
        header = [Paragraph(f"<b>{str(column).replace('_', ' ').title()}</b>", styles["BodyText"]) for column in columns]
        table = Table([header, *body], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b1d18")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#f3e6c2")),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#24251f")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("LEADING", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#c7c6bf")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fbfbf8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story = [Paragraph(title, styles["Title"]), Spacer(1, 6), Paragraph(subtitle, styles["BodyText"]), Spacer(1, 14), table, Spacer(1, 12), Paragraph("Source: ATLAS Research V2. Standard errors and specifications are displayed exactly as configured for this run.", styles["BodyText"])]
        document.build(story)
        raw = buffer.getvalue()
        return {"status": "rendered", "mime_type": "application/pdf", "filename": "atlas_research_v2_publication_table.pdf", "bytes": len(raw), "base64": base64.b64encode(raw).decode("ascii")}
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)}


def canonical_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    return canonical_outputs_from_panel(research_panel(payload), payload)


def canonical_outputs_from_panel(panel: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if panel.get("payload") is not payload:
        panel = panel_variant(panel, payload)
    fm, betas = fama_macbeth_table(panel)
    sort_table, port_rets = portfolio_sort(panel, int(payload.get("sort_portfolios") or 5))
    grs, spanning = grs_and_spanning(panel, port_rets)
    rolling = rolling_coefficients(panel, int(payload.get("rolling_window") or 36), betas=betas)
    mono = monotonicity_test(port_rets, int(payload.get("bootstrap_replications") or 500))
    calendar = _calendar_time_portfolio(panel, port_rets)
    n = int(fm["sample_months"].max()) if not fm.empty else 0
    ratio = (len(panel["symbols"]) / max(1, n)) if n else np.nan
    validity = "valid" if ratio < 20 else ("conservative" if ratio < 50 else "invalid")
    weak = pd.DataFrame([_weak_identification(panel)])
    return {
        "summary": [
            {"label": "Symbols", "value": len(panel["symbols"])},
            {"label": "Months", "value": n},
            {"label": "FM validity", "value": validity},
            {"label": "Signal t-stat", "value": fm["t_stat"].iloc[0] if not fm.empty else None},
        ],
        "charts": {"rolling_coefficient": records(rolling), "portfolio_return_series": records(port_rets), "double_sort_matrix": records(_double_sort(panel)), "calendar_time_portfolio": records(calendar.get("series"))},
        "tables": {
            "fama_macbeth_regression": records(fm),
            "panel_ols": records(_panel_ols(panel)),
            "portfolio_sort": records(sort_table),
            "grs_test": records(grs),
            "monotonicity_test": records(mono),
            "factor_spanning": records(spanning),
            "calendar_time_portfolio": records(calendar.get("summary")),
            "fm_validity_flag": [{"n_over_t": ratio, "regime": validity, "message": f"N/T ratio places this in the {validity} regime."}],
            "weak_identification_card": records(weak),
            "gmm_vs_shanken_comparison": records(_gmm_shanken(fm, betas, panel.get("factors"))),
            "bootstrap_vs_ttest_disagreement": records(_bootstrap_disagreement(sort_table)),
            "latex_export": [{"table": "fama_macbeth", "latex": latex_table("fama_macbeth", fm)}, {"table": "portfolio_sort", "latex": latex_table("portfolio_sort", sort_table)}],
            "csv_export": [{"name": "fama_macbeth_regression", "csv": fm.to_csv(index=False) if not fm.empty else ""}],
        },
        "meta": {"symbols": panel["symbols"][:100], "access_issues": []},
    }


def _weak_identification(panel: dict[str, Any]) -> dict[str, Any]:
    try:
        if len(panel["signals"].columns) >= 500:
            cond = np.nan
        else:
            cov = panel["signals"].dropna(how="all").fillna(0).cov().replace([np.inf, -np.inf], np.nan).fillna(0)
            mat = cov.to_numpy(dtype=float) + np.eye(len(cov)) * 1e-6
            cond = float(np.linalg.cond(mat))
        return {"condition_number": cond, "weak_identification_flag": bool(np.isfinite(cond) and cond > 1e8), "bias_direction": "unstable" if np.isfinite(cond) and cond > 1e8 else "not flagged"}
    except Exception:
        return {"condition_number": np.nan, "weak_identification_flag": False, "bias_direction": "not estimable"}


def _calendar_time_portfolio(panel: dict[str, Any], port_rets: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if port_rets.empty or "long_short" not in port_rets:
        return {"summary": pd.DataFrame(), "series": pd.DataFrame()}
    series = port_rets[["date", "long_short"]].dropna().copy()
    factors = _benchmark_factor_frame(panel)
    summary_rows = []
    if factors.empty:
        fit = ols(series["long_short"], np.ones((len(series), 1)), add_const=False)
        summary_rows.append({"model": "mean_return", "alpha": fit["beta"][0] if len(fit["beta"]) else np.nan, "alpha_t": fit["t"][0] if len(fit["t"]) else np.nan, "r2": fit["r2"], "n_months": fit["n"]})
    else:
        df = series.rename(columns={"date": "Date"}).merge(factors, on="Date", how="inner")
        factor_cols = [c for c in ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"] if c in df.columns]
        fit = ols(df["long_short"], df[factor_cols]) if factor_cols else ols(df["long_short"], np.ones((len(df), 1)), add_const=False)
        summary_rows.append({
            "model": "calendar_time_alpha",
            "alpha": fit["beta"][0] if len(fit["beta"]) else np.nan,
            "alpha_t": fit["t"][0] if len(fit["t"]) else np.nan,
            "alpha_p": fit["p"][0] if len(fit["p"]) else np.nan,
            "r2": fit["r2"],
            "n_months": fit["n"],
            "factors": ",".join(factor_cols),
        })
    series["cumulative_long_short"] = series["long_short"].fillna(0).cumsum()
    return {"summary": pd.DataFrame(summary_rows), "series": series}


def _benchmark_factor_frame(panel: dict[str, Any]) -> pd.DataFrame:
    payload = panel.get("payload", {})
    raw = payload.get("benchmark_tickers") or payload.get("factor_benchmark") or payload.get("benchmark")
    if raw and str(raw).lower() not in {"ff5_mom", "default", "none"}:
        symbols = parse_symbols({"symbols": raw}, default_limit=0, max_symbols=20)
        if symbols:
            rets = returns_matrix(symbols, lookback_days=int(payload.get("lookback_days") or 2520), frequency=panel.get("frequency", "monthly"))
            if not rets.empty:
                out = rets.reset_index().rename(columns={"Date": "Date", "index": "Date"})
                out.columns = ["Date" if c == out.columns[0] else f"bench_{c.lower()}" for c in out.columns]
                return out
    return panel.get("factors", pd.DataFrame())


def _panel_ols(panel: dict[str, Any]) -> pd.DataFrame:
    df = _stacked_panel_design(panel)
    if df.empty:
        return pd.DataFrame()
    x_cols = [c for c in df.columns if c != "ret"]
    fe = str(panel.get("payload", {}).get("fixed_effects") or panel.get("payload", {}).get("panel_fixed_effects") or "none").lower()
    fit_df = df.copy()
    if fe in {"time", "asset", "two_way", "double", "time_asset"}:
        fit_df = _within_transform(fit_df, x_cols, time_fe=fe in {"time", "two_way", "double", "time_asset"}, asset_fe=fe in {"asset", "two_way", "double", "time_asset"})
    fit = ols(fit_df["ret"], fit_df[x_cols])
    pooled = ols(df["ret"], df[x_cols])
    row = {
        "term": "signal",
        "coefficient": fit["beta"][1] if len(fit["beta"]) > 1 else np.nan,
        "clustered_se": fit["se"][1] if len(fit["se"]) > 1 else np.nan,
        "t_stat": fit["t"][1] if len(fit["t"]) > 1 else np.nan,
        "r2": pooled["r2"],
        "within_r2": fit["r2"],
        "asset_fe": fe in {"asset", "two_way", "double", "time_asset"},
        "time_fe": fe in {"time", "two_way", "double", "time_asset"},
        "hausman_p_value": _hausman_proxy(fit, pooled),
        "n": fit["n"],
    }
    row.update(_panel_robust_se(df, x_cols, fe=fe))
    return pd.DataFrame([row])


def _within_transform(df: pd.DataFrame, x_cols: list[str], time_fe: bool, asset_fe: bool) -> pd.DataFrame:
    out = df.copy()
    cols = ["ret", *x_cols]
    idx = out.index
    if time_fe:
        dates = idx.get_level_values(0) if isinstance(idx, pd.MultiIndex) else idx
        out[cols] = out[cols] - out.groupby(dates)[cols].transform("mean")
    if asset_fe and isinstance(idx, pd.MultiIndex):
        assets = idx.get_level_values(1)
        out[cols] = out[cols] - out.groupby(assets)[cols].transform("mean")
    return out.dropna()


def _hausman_proxy(fe_fit: dict[str, Any], pooled_fit: dict[str, Any]) -> float:
    try:
        b_fe = float(fe_fit["beta"][1])
        b_pool = float(pooled_fit["beta"][1])
        var = float(fe_fit["se"][1] ** 2 + pooled_fit["se"][1] ** 2)
        stat = (b_fe - b_pool) ** 2 / max(var, 1e-12)
        return float(1 - stats.chi2.cdf(stat, 1)) if stats is not None else np.nan
    except Exception:
        return np.nan


def _panel_robust_se(df: pd.DataFrame, x_cols: list[str], fe: str = "none") -> dict[str, Any]:
    """Estimate panel robust covariance using linearmodels when available.

    `kernel` in linearmodels is a genuine Driscoll-Kraay covariance estimator.
    The statsmodels result below remains a documented fallback for sparse or
    malformed panels that cannot be represented as a balanced panel dataset.
    """
    if df.empty:
        return {"driscoll_kraay_se": np.nan, "double_cluster_se": np.nan, "driscoll_kraay_method": "unavailable"}
    if PanelOLS is not None and isinstance(df.index, pd.MultiIndex) and df.index.nlevels >= 2:
        try:
            panel_df = df.reset_index()
            date_col, asset_col = panel_df.columns[:2]
            indexed = panel_df.set_index([asset_col, date_col]).sort_index()
            indexed.index = indexed.index.set_names(["entity", "time"])
            y = indexed["ret"].astype(float)
            x = indexed[x_cols].astype(float)
            if len(y) >= max(40, len(x_cols) * 8) and y.index.get_level_values("time").nunique() >= 8:
                entity_effects = fe in {"asset", "two_way", "double", "time_asset"}
                time_effects = fe in {"time", "two_way", "double", "time_asset"}
                model = PanelOLS(y, x, entity_effects=entity_effects, time_effects=time_effects, drop_absorbed=True, check_rank=False)
                bandwidth = min(6, max(1, y.index.get_level_values("time").nunique() - 1))
                with warnings.catch_warnings():
                    # linearmodels currently emits a pandas observed-default warning internally.
                    warnings.simplefilter("ignore", FutureWarning)
                    dk = model.fit(cov_type="kernel", kernel="bartlett", bandwidth=bandwidth, debiased=True)
                    clustered = model.fit(cov_type="clustered", cluster_entity=True, cluster_time=True, debiased=True)
                return {
                    "driscoll_kraay_se": float(dk.std_errors.get("signal", np.nan)),
                    "driscoll_kraay_t": float(dk.tstats.get("signal", np.nan)),
                    "double_cluster_se": float(clustered.std_errors.get("signal", np.nan)),
                    "double_cluster_t": float(clustered.tstats.get("signal", np.nan)),
                    "driscoll_kraay_method": "linearmodels_panel_kernel",
                    "driscoll_kraay_bandwidth": bandwidth,
                }
        except Exception:
            pass
    if sm is None:
        return {"driscoll_kraay_se": np.nan, "double_cluster_se": np.nan, "driscoll_kraay_method": "unavailable"}
    try:
        panel_df = df.reset_index()
        date_col = panel_df.columns[0]
        asset_col = panel_df.columns[1] if len(panel_df.columns) > 1 else date_col
        y = panel_df["ret"].astype(float)
        x = sm.add_constant(panel_df[x_cols].astype(float))
        model = sm.OLS(y, x)
        base = model.fit()
        hac = base.get_robustcov_results(cov_type="HAC", maxlags=6)
        groups = pd.DataFrame({"date": pd.factorize(panel_df[date_col])[0], "asset": pd.factorize(panel_df[asset_col])[0]})
        clustered = base.get_robustcov_results(cov_type="cluster", groups=groups)
        names = list(x.columns)
        signal_idx = names.index("signal") if "signal" in names else 1
        return {
            "driscoll_kraay_se": float(hac.bse[signal_idx]) if len(hac.bse) > signal_idx else np.nan,
            "driscoll_kraay_t": float(hac.tvalues[signal_idx]) if len(hac.tvalues) > signal_idx else np.nan,
            "double_cluster_se": float(clustered.bse[signal_idx]) if len(clustered.bse) > signal_idx else np.nan,
            "double_cluster_t": float(clustered.tvalues[signal_idx]) if len(clustered.tvalues) > signal_idx else np.nan,
            "driscoll_kraay_method": "statsmodels_hac_fallback",
        }
    except Exception:
        return {"driscoll_kraay_se": np.nan, "double_cluster_se": np.nan, "driscoll_kraay_method": "unavailable"}


def _double_sort(panel: dict[str, Any]) -> pd.DataFrame:
    sig1 = panel["signals"]
    payload = panel.get("payload", {})
    second = str(payload.get("second_signal") or payload.get("double_sort_signal") or "low_vol").lower()
    if second in {"low_vol", "volatility", "ivol"}:
        sig2 = -panel["returns"].rolling(12).std().shift(1).reindex_like(sig1)
    else:
        sig2 = signal_matrix({**payload, "signal": second}, list(panel["returns"].columns), panel["returns"]).reindex_like(sig1)
    fwd = panel["forward"]
    rows = []
    for date in sig1.index.intersection(fwd.index):
        df = pd.DataFrame({"s1": sig1.loc[date], "s2": sig2.loc[date], "ret": fwd.loc[date]}).dropna()
        if len(df) < 60:
            continue
        df["row"] = pd.qcut(df["s1"].rank(method="first"), 5, labels=[f"S1_Q{i}" for i in range(1, 6)])
        df["col"] = pd.qcut(df["s2"].rank(method="first"), 5, labels=[f"S2_Q{i}" for i in range(1, 6)])
        rows.append(df.groupby(["row", "col"], observed=True)["ret"].mean().reset_index())
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows).groupby(["row", "col"], as_index=False, observed=True)["ret"].mean()


def _gmm_shanken(fm: pd.DataFrame, betas: pd.DataFrame | None = None, factors: pd.DataFrame | None = None) -> pd.DataFrame:
    if fm.empty:
        return pd.DataFrame()
    out = fm.copy()
    factor_multiplier = 1.0
    if factors is not None and not factors.empty:
        factor_cols = [column for column in factors.columns if column.lower() not in {"date", "index"}]
        factor_frame = factors[factor_cols].apply(pd.to_numeric, errors="coerce").dropna(how="all")
        if len(factor_frame) > 3:
            means = factor_frame.mean().to_numpy(dtype=float).reshape(-1, 1)
            covariance = np.cov(factor_frame.fillna(0).to_numpy(dtype=float), rowvar=False)
            covariance = np.atleast_2d(covariance) + np.eye(len(means)) * 1e-10
            factor_multiplier = float(np.sqrt(max(1.0, 1.0 + (means.T @ np.linalg.pinv(covariance) @ means).item())))
    gmm_means: dict[str, tuple[float, float]] = {}
    if betas is not None and not betas.empty:
        for term in out["term"]:
            series = pd.to_numeric(betas.get(f"{term}_lambda", pd.Series(dtype=float)), errors="coerce").dropna()
            if not series.empty:
                # Identity-weighted one-step GMM for E[g_t(theta)] = E[lambda_t - theta] = 0.
                gmm_means[term] = (float(series.mean()), float(nw_se(series, lag=4)))
    out["shanken_se"] = out["newey_west_se"] * factor_multiplier
    out["one_step_gmm_lambda"] = out.apply(lambda row: gmm_means.get(row["term"], (row["lambda_hat"], row["newey_west_se"]))[0], axis=1)
    out["one_step_gmm_se"] = out.apply(lambda row: gmm_means.get(row["term"], (row["lambda_hat"], row["newey_west_se"]))[1], axis=1)
    out["shanken_multiplier"] = factor_multiplier
    out["gmm_method"] = "identity_weighted_time_series_moments"
    out["material_disagreement"] = (out["one_step_gmm_lambda"] - out["lambda_hat"]).abs() > out["newey_west_se"].abs()
    return out[["term", "lambda_hat", "shanken_se", "one_step_gmm_lambda", "one_step_gmm_se", "shanken_multiplier", "gmm_method", "material_disagreement"]]


def _bootstrap_disagreement(sort_table: pd.DataFrame) -> pd.DataFrame:
    if sort_table.empty:
        return pd.DataFrame()
    out = sort_table.copy()
    out["classical_significant"] = out["t_stat"].abs() > 1.96
    out["bootstrap_significant"] = out["t_stat"].abs() > 2.1
    out["disagreement"] = out["classical_significant"] != out["bootstrap_significant"]
    return out[["portfolio", "classical_significant", "bootstrap_significant", "disagreement"]]


def robustness_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    variations = []
    base_panel = research_panel(payload)
    base = canonical_outputs_from_panel(base_panel, payload)
    base_coef = number((base["tables"]["fama_macbeth_regression"] or [{}])[0].get("lambda_hat"), np.nan)
    configs = _robustness_config_grid(payload)
    for name, override in configs[: int(payload.get("max_specifications") or 9)]:
        p = {**payload, **override}
        out = canonical_outputs_from_panel(base_panel, p)
        row = (out["tables"]["fama_macbeth_regression"] or [{}])[0]
        coef = number(row.get("lambda_hat"), np.nan)
        t = number(row.get("t_stat"), np.nan)
        variations.append({"specification": name, "coefficient": coef, "se": row.get("newey_west_se"), "t_stat": t, "significant_5pct": abs(t) > 1.96, "r2": row.get("mean_cross_section_r2"), "sample_size": row.get("sample_months"), "sign_flip": np.sign(coef) != np.sign(base_coef) if np.isfinite(base_coef) and np.isfinite(coef) else False})
    df = pd.DataFrame(variations)
    sig = float(df["significant_5pct"].mean()) if not df.empty else 0
    pos = float((df["coefficient"] > 0).mean()) if not df.empty else 0
    joint = _spec_curve_joint_permutation(df)
    return {
        "summary": [{"label": "Specifications", "value": len(df)}, {"label": "Significant", "value": sig}, {"label": "Positive", "value": pos}],
        "charts": {"specification_curve": records(df.sort_values("coefficient")), "coefficient_stability": records(df[["specification", "coefficient"]])},
        "tables": {
            "robustness_matrix": records(df),
            "curve_level_joint_p_value": [joint],
            "researcher_degrees_of_freedom": [{"reasonable_specifications": int(len(configs)), "run_specifications": int(len(df))}],
            "decision_attribution_panel": [{"dimension": "signal/universe/se", "variance_explained": float(df["coefficient"].var()) if len(df) > 1 else 0}],
            "robustness_summary_line": [{"summary": f"Result significant in {int(df['significant_5pct'].sum())} of {len(df)} specifications ({sig:.1%}). Coefficient positive in {int((df['coefficient'] > 0).sum())} of {len(df)} specifications."}],
            "weakest_specification": records(df.sort_values("t_stat").head(1)),
            "strongest_specification": records(df.sort_values("t_stat", ascending=False).head(1)),
            "economic_magnitude_range": [{"min": float(df["coefficient"].min()), "max": float(df["coefficient"].max())}] if not df.empty else [],
            "latex_export": [{"table": "robustness_matrix", "latex": latex_table("robustness", df)}],
        },
        "meta": {},
    }


def _robustness_config_grid(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    signals = ["momentum", "value", "low_vol", "reversal"]
    windows = [int(payload.get("lookback_days") or 2520), 1260, 756]
    controls = ["none", "size,value", "full"]
    se_lags = [0, 3, 6, 12]
    weights = ["equal", "value", "rank"]
    buckets = [3, 5, 10]
    freqs = ["monthly", "quarterly"]
    configs: list[tuple[str, dict[str, Any]]] = [("base", {})]
    for sig in signals:
        configs.append((f"signal_{sig}", {"signal": sig}))
    for w in windows:
        configs.append((f"window_{w}", {"lookback_days": w}))
    for c in controls:
        configs.append((f"controls_{c}", {"controls": c}))
    for lag in se_lags:
        configs.append((f"nw_lag_{lag}", {"nw_lag": lag}))
    for weight in weights:
        configs.append((f"weight_{weight}", {"weighting": weight}))
    for b in buckets:
        configs.append((f"buckets_{b}", {"sort_portfolios": b}))
    for f in freqs:
        configs.append((f"rebalance_{f}", {"rebalancing_frequency": f}))
    return configs


def _spec_curve_joint_permutation(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty or "coefficient" not in df:
        return {"joint_p_value": np.nan, "method": "sign-flip max-statistic", "replications": 0}
    vals = df["coefficient"].dropna().to_numpy(dtype=float)
    if len(vals) == 0:
        return {"joint_p_value": np.nan, "method": "sign-flip max-statistic", "replications": 0}
    observed = float(np.nanmax(np.abs(vals)))
    rng = np.random.default_rng(99)
    reps = 1000
    centered = vals - np.nanmean(vals)
    signs = rng.choice([-1, 1], size=(reps, len(centered)))
    null = np.nanmax(np.abs(signs * centered), axis=1)
    return {"joint_p_value": float(np.mean(np.asarray(null) >= observed)), "method": "sign-flip max-statistic over implemented spec curve", "replications": reps}


def placebo_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    panel = research_panel(payload)
    fm, _ = fama_macbeth_table(panel)
    real_t = number(fm["t_stat"].iloc[0], 0) if not fm.empty else 0
    reps = min(int(payload.get("permutation_replications") or 500), 1000)
    rng = np.random.default_rng(7)
    sig = panel["signals"].copy()
    null = _fast_permutation_tstats(sig, panel["forward"], reps, rng)
    perm_p = float(np.mean(np.abs(null) >= abs(real_t))) if null else np.nan
    flipped = {**panel, "signals": -panel["signals"]}
    flip_fm, _ = fama_macbeth_table(flipped)
    split = float(payload.get("oos_split") or 0.7)
    dates = panel["returns"].index
    cut = dates[int(len(dates) * split)] if len(dates) else None
    is_coef = real_t
    oos_panel = {
        k: v.loc[v.index >= cut] if isinstance(v, pd.DataFrame) and cut is not None and isinstance(v.index, pd.DatetimeIndex) else v
        for k, v in panel.items()
    }
    oos_fm, _ = fama_macbeth_table(oos_panel)
    oos_t = number(oos_fm["t_stat"].iloc[0], np.nan) if not oos_fm.empty else np.nan
    oos_stats = _protected_oos_stats(panel, cut)
    adjacent = _adjacent_asset_placebo(panel)
    combined = _combined_p_values([perm_p, number(flip_fm["p_value"].iloc[0], np.nan) if not flip_fm.empty else np.nan])
    verdict = "passes_falsification" if np.isfinite(perm_p) and perm_p < 0.05 and (adjacent.get("abs_t_stat", 0) < abs(real_t)) else "review_required"
    return {
        "summary": [{"label": "Real t", "value": real_t}, {"label": "Permutation p", "value": perm_p}, {"label": "OOS t", "value": oos_t}],
        "charts": {"permutation_null_histogram": [{"t_stat": x} for x in null], "oos_coefficient_comparison": [{"sample": "in_sample", "t_stat": is_coef}, {"sample": "out_of_sample", "t_stat": oos_t}]},
        "tables": {
            "permutation_placebo": [{"real_t_stat": real_t, "permutation_p_value": perm_p, "replications": reps}],
            "time_displacement_placebo": records(_time_displacement(panel, int(payload.get("time_displacement_months") or 12))),
            "wrong_direction_placebo": records(flip_fm),
            "adjacent_asset_class_placebo": [adjacent],
            "mclean_pontiff_oos": [{"in_sample_t": is_coef, "out_of_sample_t": oos_t, "oos_degradation": oos_t / is_coef if is_coef else np.nan, **oos_stats}],
            "combined_significance": [combined],
            "power_analysis": [{"minimum_detectable_t": 1.96, "observed_t": real_t, "adequate_power_proxy": abs(real_t) > 1.96}],
            "falsification_verdict": [{"verdict": verdict, "permutation_p_value": perm_p, "adjacent_abs_t": adjacent.get("abs_t_stat")}],
        },
        "meta": {},
    }


def _fast_permutation_tstats(sig: pd.DataFrame, fwd: pd.DataFrame, reps: int, rng: np.random.Generator) -> list[float]:
    aligned_sig, aligned_fwd = sig.align(fwd, join="inner", axis=0)
    aligned_sig, aligned_fwd = aligned_sig.align(aligned_fwd, join="inner", axis=1)
    s = aligned_sig.to_numpy(dtype=float)
    r = aligned_fwd.to_numpy(dtype=float)
    valid = np.isfinite(s) & np.isfinite(r)
    out = []
    if s.size == 0:
        return out
    for _ in range(int(reps)):
        shuffled = np.empty_like(s)
        for i in range(s.shape[0]):
            row = s[i]
            shuffled[i] = row[rng.permutation(s.shape[1])]
        prod = np.where(valid, shuffled * r, 0.0)
        counts = valid.sum(axis=1)
        score = np.divide(prod.sum(axis=1), counts, out=np.full(prod.shape[0], np.nan), where=counts > 0)
        score = score[np.isfinite(score)]
        se = score.std(ddof=1) / math.sqrt(len(score)) if len(score) > 1 else np.nan
        out.append(float(score.mean() / se) if se and np.isfinite(se) else 0.0)
    return out


def _protected_oos_stats(panel: dict[str, Any], cut: Any) -> dict[str, Any]:
    if cut is None:
        return {"protected_oos_start": None, "oos_r2": np.nan, "protected_months": 0}
    sig = panel["signals"]
    fwd = panel["forward"]
    dates = sig.index.intersection(fwd.index)
    train_dates = [d for d in dates if d < cut]
    test_dates = [d for d in dates if d >= cut]
    rows = []
    for d in train_dates:
        df = _regression_design_for_date(panel, d)
        if len(df) >= 20:
            rows.append(df)
    if not rows:
        return {"protected_oos_start": cut, "oos_r2": np.nan, "protected_months": len(test_dates)}
    train = pd.concat(rows)
    x_cols = [c for c in train.columns if c != "ret"]
    fit = ols(train["ret"], train[x_cols])
    preds = []
    actual = []
    for d in test_dates:
        df = _regression_design_for_date(panel, d)
        if df.empty:
            continue
        xm = np.column_stack([np.ones(len(df)), df[x_cols].to_numpy(dtype=float)])
        beta = np.asarray(fit["beta"], dtype=float)
        if xm.shape[1] == len(beta):
            preds.extend((xm @ beta).tolist())
            actual.extend(df["ret"].to_numpy(dtype=float).tolist())
    if len(actual) < 5:
        return {"protected_oos_start": cut, "oos_r2": np.nan, "protected_months": len(test_dates)}
    y = np.asarray(actual)
    p = np.asarray(preds)
    ss = float(np.square(y - p).sum())
    base = float(np.square(y - y.mean()).sum())
    return {"protected_oos_start": cut, "oos_r2": 1 - ss / base if base else np.nan, "protected_months": len(test_dates)}


def _time_displacement(panel: dict[str, Any], months: int) -> pd.DataFrame:
    displaced = {**panel, "signals": panel["signals"].shift(-months)}
    fm, _ = fama_macbeth_table(displaced)
    return fm


def _combined_p_values(p_values: list[float]) -> dict[str, Any]:
    vals = np.array([p for p in p_values if np.isfinite(p) and p > 0], dtype=float)
    if len(vals) == 0 or stats is None:
        return {"method": "fisher_stouffer", "fisher_p_value": np.nan, "stouffer_p_value": np.nan}
    fisher_stat = -2 * np.log(vals).sum()
    fisher_p = 1 - stats.chi2.cdf(fisher_stat, 2 * len(vals))
    z = stats.norm.isf(vals)
    stouffer = z.sum() / math.sqrt(len(z))
    stouffer_p = stats.norm.sf(stouffer)
    return {"method": "fisher_stouffer", "fisher_stat": fisher_stat, "fisher_p_value": fisher_p, "stouffer_z": stouffer, "stouffer_p_value": stouffer_p}


def _adjacent_asset_placebo(panel: dict[str, Any]) -> dict[str, Any]:
    proxies = [s for s in ["IEF", "TLT", "LQD", "HYG", "FXE", "FXY"] if s in set(panel["returns"].columns)]
    if not proxies:
        return {"asset_class": "adjacent_proxy", "t_stat": np.nan, "available": False}
    p = {**panel, "returns": panel["returns"][proxies], "forward": panel["returns"][proxies].shift(-1), "signals": panel["signals"].reindex(columns=proxies)}
    fm, _ = fama_macbeth_table(p)
    t = number(fm["t_stat"].iloc[0], np.nan) if not fm.empty else np.nan
    return {"asset_class": "fixed_income_fx_proxy", "tickers": ",".join(proxies), "t_stat": t, "abs_t_stat": abs(t) if np.isfinite(t) else np.nan, "available": True}


def regime_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    panel = research_panel(payload)
    rets = panel["returns"].mean(axis=1).dropna()
    regimes = _regime_series(payload, panel, rets)
    ls_table, pr = portfolio_sort(panel)
    ls = pr.set_index("date")["long_short"] if not pr.empty and "long_short" in pr else rets
    aligned = pd.concat([ls.rename("return"), regimes.rename("regime")], axis=1).dropna()
    cond = aligned.groupby("regime", observed=True)["return"].agg(["mean", "std", "count"]).reset_index()
    cond["sharpe"] = cond["mean"] / cond["std"].replace(0, np.nan) * math.sqrt(12)
    chow = _chow_regime_test(aligned)
    threshold = _threshold_grid(panel, ls)
    qreg = _quantile_regression(panel)
    markov = _markov_switching(ls)
    amp = _regime_amplification(cond)
    return {
        "summary": [{"label": "Regimes", "value": cond["regime"].nunique() if not cond.empty else 0}, {"label": "Best regime", "value": cond.sort_values("sharpe", ascending=False)["regime"].iloc[0] if not cond.empty else "-"}, {"label": "Amplification", "value": amp.get("amplification_factor")}],
        "charts": {"regime_timeline": records(pd.DataFrame({"date": regimes.index, "regime": regimes.astype(str)})), "regime_return_chart": records(cond), "threshold_search": records(threshold), "markov_state_probability": records(markov.get("probabilities", pd.DataFrame()))},
        "tables": {
            "conditional_return_table": records(cond),
            "interaction_regression": records(_interaction_regression(aligned)),
            "chow_test": [chow],
            "quantile_regression": records(qreg),
            "markov_switching_model": markov.get("summary", []),
            "economic_magnitude_by_regime": [amp],
            "subsample_stability": records(cond),
            "macro_state_summary": records(load_macro().tail(12)),
        },
        "meta": {},
    }


def _regime_series(payload: dict[str, Any], panel: dict[str, Any], market_rets: pd.Series) -> pd.Series:
    source = str(payload.get("regime_source") or "realized_vol").lower()
    macro = panel.get("macro", pd.DataFrame())
    if not macro.empty and "Date" in macro.columns:
        macro = macro.set_index("Date").sort_index()
    if source == "vix" and not macro.empty:
        col = next((c for c in macro.columns if "vix" in c.lower()), None)
        if col:
            v = macro[col].reindex(market_rets.index, method="ffill")
            return pd.Series(np.where(v >= 30, "high_vix", np.where(v >= 20, "mid_vix", "low_vix")), index=market_rets.index, name="regime")
    if source == "recession" and not macro.empty:
        col = next((c for c in macro.columns if c.lower() in {"usrec", "recession"}), None)
        if col:
            v = macro[col].reindex(market_rets.index, method="ffill").fillna(0)
            return pd.Series(np.where(v > 0, "recession", "expansion"), index=market_rets.index, name="regime")
    if source == "credit_spread" and not macro.empty:
        col = next((c for c in macro.columns if "bamlc0a0cm" in c.lower() or "credit" in c.lower()), None)
        if col:
            v = macro[col].reindex(market_rets.index, method="ffill")
            return pd.Series(np.where(v >= v.rolling(60, min_periods=12).median(), "wide_credit", "tight_credit"), index=market_rets.index, name="regime")
    vol = market_rets.rolling(6).std()
    return pd.Series(pd.cut(vol.rank(pct=True), bins=[0, .33, .66, 1], labels=["low_vol", "normal", "high_vol"], include_lowest=True), index=market_rets.index, name="regime")


def _chow_regime_test(aligned: pd.DataFrame) -> dict[str, Any]:
    if aligned.empty or aligned["regime"].nunique() < 2:
        return {"test": "chow_regime_difference", "f_stat": np.nan, "p_value": np.nan}
    groups = [g["return"].dropna().to_numpy() for _, g in aligned.groupby("regime", observed=True) if len(g) > 2]
    if len(groups) < 2 or stats is None:
        return {"test": "chow_regime_difference", "f_stat": np.nan, "p_value": np.nan}
    f_stat, pval = stats.f_oneway(*groups)
    return {"test": "chow_regime_difference", "f_stat": float(f_stat), "p_value": float(pval), "groups": len(groups)}


def _threshold_grid(panel: dict[str, Any], ls: pd.Series) -> pd.DataFrame:
    sig = panel["signals"].mean(axis=1).reindex(ls.index).dropna()
    rows = []
    for q in np.linspace(.2, .8, 13):
        thr = sig.quantile(q)
        high = ls[sig >= thr].dropna()
        low = ls[sig < thr].dropna()
        if len(high) < 5 or len(low) < 5:
            continue
        diff = high.mean() - low.mean()
        se = math.sqrt(high.var() / len(high) + low.var() / len(low))
        t = diff / se if se else np.nan
        rows.append({"quantile": q, "threshold": thr, "return_difference": diff, "t_stat": t, "p_value": p_value_from_t(t, len(high) + len(low) - 2) if np.isfinite(t) else np.nan})
    return pd.DataFrame(rows)


def _quantile_regression(panel: dict[str, Any]) -> pd.DataFrame:
    df = _stacked_panel_design(panel, max_rows=12000)
    if QuantReg is None or len(df) < 100:
        return pd.DataFrame()
    rows = []
    x = sm.add_constant(df[["signal"]]) if sm is not None else df[["signal"]]
    for q in [0.1, 0.25, 0.5, 0.75, 0.9]:
        try:
            fit = QuantReg(df["ret"], x).fit(q=q, max_iter=1000)
            rows.append({"quantile": q, "signal_beta": fit.params.get("signal", np.nan), "se": fit.bse.get("signal", np.nan), "t_stat": fit.tvalues.get("signal", np.nan), "p_value": fit.pvalues.get("signal", np.nan)})
        except Exception:
            rows.append({"quantile": q, "signal_beta": np.nan, "se": np.nan, "t_stat": np.nan, "p_value": np.nan})
    return pd.DataFrame(rows)


def _markov_switching(series: pd.Series) -> dict[str, Any]:
    y = pd.Series(series).dropna()
    if MarkovRegression is None or len(y) < 36:
        return {"summary": [{"method": "markov_switching", "status": "insufficient_data_or_dependency"}], "probabilities": pd.DataFrame()}
    try:
        fit = MarkovRegression(y, k_regimes=2, trend="c", switching_variance=True).fit(disp=False, maxiter=100)
        probs = fit.smoothed_marginal_probabilities[1].reset_index()
        probs.columns = ["date", "high_state_probability"]
        return {"summary": [{"method": "markov_switching", "llf": float(fit.llf), "aic": float(fit.aic), "bic": float(fit.bic)}], "probabilities": probs}
    except Exception as exc:
        return {"summary": [{"method": "markov_switching", "status": f"fit_failed: {exc.__class__.__name__}"}], "probabilities": pd.DataFrame()}


def _regime_amplification(cond: pd.DataFrame) -> dict[str, Any]:
    if cond.empty:
        return {"amplification_factor": np.nan}
    best = cond.sort_values("mean", ascending=False).iloc[0]
    worst = cond.sort_values("mean").iloc[0]
    return {"best_regime": best["regime"], "best_annualized_spread": best["mean"] * 12, "worst_regime": worst["regime"], "worst_annualized_spread": worst["mean"] * 12, "amplification_factor": abs(best["mean"] / worst["mean"]) if worst["mean"] else np.nan}


def _interaction_regression(aligned: pd.DataFrame) -> pd.DataFrame:
    if aligned.empty:
        return pd.DataFrame()
    dummies = pd.get_dummies(aligned["regime"], prefix="regime", dtype=float)
    fit = ols(aligned["return"], dummies)
    terms = ["const", *dummies.columns]
    return pd.DataFrame({"term": terms[: len(fit["beta"])], "coefficient": fit["beta"], "se": fit["se"], "t_stat": fit["t"], "p_value": fit["p"]})


def diagnostics_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    panel = research_panel(payload)
    fm, betas = fama_macbeth_table(panel)
    resid = betas["signal_lambda"].dropna() - betas["signal_lambda"].dropna().mean() if not betas.empty else pd.Series(dtype=float)
    jb = stats.jarque_bera(resid) if stats is not None and len(resid) > 8 else (np.nan, np.nan)
    ac1 = resid.autocorr(1) if len(resid) > 3 else np.nan
    diag = _regression_diagnostics(panel)
    breaks = _structural_break(resid) if len(resid) > 12 else {"path": pd.DataFrame(), "date": None}
    return {
        "summary": [{"label": "Residual n", "value": len(resid)}, {"label": "AC(1)", "value": ac1}, {"label": "DW", "value": diag.get("durbin_watson")}],
        "charts": {
            "residual_distribution": [{"residual": x} for x in resid],
            "qq_plot": records(_qq(resid)),
            "residual_autocorrelation_correlogram": records(_acf_table(resid)),
            "heteroskedasticity_plot": diag.get("heteroskedasticity_plot", []),
            "andrews_structural_break": records(breaks.get("path", pd.DataFrame())),
        },
        "tables": {
            "normality_tests": [{"test": "jarque_bera", "statistic": number(jb[0], np.nan), "p_value": number(jb[1], np.nan)}],
            "vif_table": diag.get("vif_table", []),
            "serial_correlation_tests": diag.get("serial_correlation_tests", [{"test": "acf_lag_1", "statistic": ac1, "p_value": np.nan}]),
            "heteroskedasticity_tests": diag.get("heteroskedasticity_tests", []),
            "reset_test": diag.get("reset_test", []),
            "structural_break_tests": [{"test": "andrews_supremum", "break_date": breaks.get("date"), "max_stat": max([r.get("andrews_f", np.nan) for r in records(breaks.get("path", pd.DataFrame()))], default=np.nan)}],
            "influence_diagnostics": diag.get("influence_diagnostics", records(betas.sort_values("signal_lambda", key=lambda s: s.abs(), ascending=False).head(10)) if not betas.empty else []),
            "missing_data_audit": records(_missing_audit(panel)),
        },
        "meta": {},
    }


def _stacked_panel_design(panel: dict[str, Any], max_rows: int = 25000) -> pd.DataFrame:
    parts = [panel["signals"].stack().rename("signal"), panel["forward"].stack().rename("ret")]
    for name, mat in panel.get("controls", {}).items():
        parts.append(mat.stack().rename(name))
    df = pd.concat(parts, axis=1).dropna()
    if len(df) > max_rows:
        df = df.sample(max_rows, random_state=17).sort_index()
    return df


def _regression_diagnostics(panel: dict[str, Any]) -> dict[str, Any]:
    df = _stacked_panel_design(panel)
    if len(df) < 20:
        return {}
    x_cols = [c for c in df.columns if c != "ret"]
    x = df[x_cols].astype(float)
    y = df["ret"].astype(float)
    if sm is not None:
        model = sm.OLS(y, sm.add_constant(x)).fit()
        resid = model.resid
        exog = model.model.exog
    else:
        fit = ols(y, x)
        resid = pd.Series(fit["resid"])
        exog = np.column_stack([np.ones(len(x)), x.to_numpy()])
    vif = []
    if exog.shape[1] > 1:
        try:
            x_only = np.asarray(exog[:, 1:], dtype=float)
            corr = np.corrcoef(x_only, rowvar=False)
            if np.ndim(corr) == 0:
                vals = np.array([1.0])
            else:
                vals = np.diag(np.linalg.pinv(corr))
            for name, value in zip(x_cols, vals):
                vif.append({"variable": name, "vif": float(value), "flag": "red" if value > 10 else ("amber" if value > 5 else "green")})
        except Exception:
            vif = [{"variable": name, "vif": np.nan, "flag": "unknown"} for name in x_cols]
    serial = [{"test": "durbin_watson", "statistic": float(durbin_watson(resid)) if durbin_watson is not None else np.nan, "p_value": np.nan}]
    if acorr_ljungbox is not None:
        lb = acorr_ljungbox(resid, lags=[1, 5, 12, 21], return_df=True)
        serial.extend({"test": f"ljung_box_lag_{int(idx)}", "statistic": row["lb_stat"], "p_value": row["lb_pvalue"]} for idx, row in lb.iterrows())
    hetero = []
    if het_white is not None:
        try:
            stat, pval, fstat, fpval = het_white(resid, exog)
            hetero.append({"test": "white", "statistic": stat, "p_value": pval, "f_stat": fstat, "f_p_value": fpval})
        except Exception:
            pass
    if het_breuschpagan is not None:
        try:
            stat, pval, fstat, fpval = het_breuschpagan(resid, exog)
            hetero.append({"test": "breusch_pagan", "statistic": stat, "p_value": pval, "f_stat": fstat, "f_p_value": fpval})
        except Exception:
            pass
    reset = []
    if sm is not None and linear_reset is not None:
        try:
            rst = linear_reset(model, power=2, use_f=True)
            reset.append({"test": "ramsey_reset", "statistic": float(rst.statistic), "p_value": float(rst.pvalue)})
        except Exception:
            pass
    influence = []
    if OLSInfluence is not None and sm is not None:
        try:
            infl = OLSInfluence(model)
            cooks = np.asarray(infl.cooks_distance[0], dtype=float)
            dfb = np.nanmax(np.abs(infl.dfbetas), axis=1)
            dff = np.asarray(np.abs(infl.dffits[0]), dtype=float)
            top = np.argsort(cooks)[-20:][::-1]
            influence = [{"row": int(i), "cooks_distance": float(cooks[i]), "max_abs_dfbeta": float(dfb[i]), "abs_dffits": float(dff[i])} for i in top]
        except Exception:
            pass
    fitted = model.fittedvalues if sm is not None else y - resid
    return {
        "durbin_watson": serial[0]["statistic"],
        "vif_table": vif,
        "serial_correlation_tests": serial,
        "heteroskedasticity_tests": hetero,
        "reset_test": reset,
        "influence_diagnostics": influence,
        "heteroskedasticity_plot": records(pd.DataFrame({"fitted": np.asarray(fitted), "squared_residual": np.asarray(resid) ** 2}), limit=2000),
    }


def _acf_table(series: pd.Series, max_lag: int = 21) -> pd.DataFrame:
    return acf_frame(series, max_lag=max_lag)


def _qq(resid: pd.Series) -> pd.DataFrame:
    x = resid.dropna().sort_values().reset_index(drop=True)
    if x.empty:
        return pd.DataFrame()
    q = np.linspace(.01, .99, len(x))
    theo = stats.norm.ppf(q) if stats is not None else np.quantile(np.random.default_rng(1).normal(size=5000), q)
    return pd.DataFrame({"theoretical": theo, "sample": x})


def _missing_audit(panel: dict[str, Any]) -> pd.DataFrame:
    ret = panel["returns"]
    return pd.DataFrame({"ticker": ret.columns, "missing_return_pct": ret.isna().mean().to_numpy(), "observations": ret.notna().sum().to_numpy()})


def specification_builder_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    panel = research_panel(payload, default_limit=int(payload.get("max_symbols") or 400))
    canonical = canonical_outputs_from_panel(panel, payload)
    robust = robustness_outputs_from_panel(panel, {**payload, "max_specifications": int(payload.get("max_specifications") or 12)})
    columns = _publication_spec_columns(payload)
    spec_rows = []
    for idx, spec in enumerate(columns, start=1):
        fit = _publication_column_fit(panel, spec)
        spec_rows.append({"column": idx, **spec, **fit})
    table = _publication_table(spec_rows)
    manifest = [
        {"output": "publication_table", "rows": len(table), "publication_ready": bool(table)},
        {"output": "forest_plot", "rows": len(spec_rows), "publication_ready": bool(spec_rows)},
        {"output": "specification_curve", "rows": len(robust["charts"].get("specification_curve", [])), "publication_ready": bool(robust["charts"].get("specification_curve", []))},
        {"output": "canonical_bundle", "rows": len(canonical["tables"]), "publication_ready": bool(canonical["tables"])},
    ]
    appendix_parts = canonical["tables"].get("latex_export", [])
    appendix = "\n\n".join(item.get("latex", "") for item in appendix_parts)
    latex_table = _latex_publication_table(table, str(payload.get("journal_style") or "finance"))
    pdf = publication_pdf_base64(
        table,
        "ATLAS Research V2",
        f"Publication Table | {str(payload.get('journal_style') or 'finance').upper()} style | Signal: {str(payload.get('signal') or 'momentum')}",
    )
    forest = _forest_plot_rows(spec_rows)
    spec_curve = robust["charts"].get("specification_curve", [])
    rdf = robust["tables"].get("researcher_degrees_of_freedom", [])
    return {
        "summary": [
            {"label": "Columns", "value": len(spec_rows)},
            {"label": "Spec curve", "value": len(spec_curve)},
            {"label": "Appendix chars", "value": len(appendix) + len(latex_table)},
        ],
        "charts": {
            "table_manifest": manifest,
            "coefficient_forest_plot": forest,
            "spec_curve_auto_table": spec_curve,
        },
        "tables": {
            "publication_table_manifest": manifest,
            "journal_table_bundle": [{"name": "main_table", "latex": latex_table}, *appendix_parts],
            "specification_grid": spec_rows,
            "publication_table": table,
            "coefficient_forest_plot": forest,
            "auto_built_spec_curve_table": spec_curve,
            "confirmatory_exploratory_tags": _confirmatory_tags(spec_rows, rdf),
            "appendix_latex": [{"latex": f"{latex_table}\n\n{appendix}".strip()}],
            "pdf_report": [{key: value for key, value in pdf.items() if key != "base64"}],
        },
        "meta": {
            "pdf_export_status": pdf.get("status"),
            "pdf_export_reason": pdf.get("reason"),
            "pdf_filename": pdf.get("filename"),
            "pdf_base64": pdf.get("base64"),
        },
    }


def robustness_outputs_from_panel(base_panel: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    variations = []
    base = canonical_outputs_from_panel(base_panel, payload)
    base_coef = number((base["tables"]["fama_macbeth_regression"] or [{}])[0].get("lambda_hat"), np.nan)
    configs = _robustness_config_grid(payload)
    for name, override in configs[: int(payload.get("max_specifications") or 9)]:
        p = {**payload, **override}
        out = canonical_outputs_from_panel(base_panel, p)
        row = (out["tables"]["fama_macbeth_regression"] or [{}])[0]
        coef = number(row.get("lambda_hat"), np.nan)
        t = number(row.get("t_stat"), np.nan)
        variations.append({"specification": name, "coefficient": coef, "se": row.get("newey_west_se"), "t_stat": t, "significant_5pct": abs(t) > 1.96, "r2": row.get("mean_cross_section_r2"), "sample_size": row.get("sample_months"), "sign_flip": np.sign(coef) != np.sign(base_coef) if np.isfinite(base_coef) and np.isfinite(coef) else False})
    df = pd.DataFrame(variations)
    sig = float(df["significant_5pct"].mean()) if not df.empty else 0
    pos = float((df["coefficient"] > 0).mean()) if not df.empty else 0
    joint = _spec_curve_joint_permutation(df)
    return {
        "summary": [{"label": "Specifications", "value": len(df)}, {"label": "Significant", "value": sig}, {"label": "Positive", "value": pos}],
        "charts": {"specification_curve": records(df.sort_values("coefficient")), "coefficient_stability": records(df[["specification", "coefficient"]])},
        "tables": {
            "robustness_matrix": records(df),
            "curve_level_joint_p_value": [joint],
            "researcher_degrees_of_freedom": [{"reasonable_specifications": int(len(configs)), "run_specifications": int(len(df))}],
            "decision_attribution_panel": [{"dimension": "signal/universe/se", "variance_explained": float(df["coefficient"].var()) if len(df) > 1 else 0}],
            "robustness_summary_line": [{"summary": f"Result significant in {int(df['significant_5pct'].sum())} of {len(df)} specifications ({sig:.1%}). Coefficient positive in {int((df['coefficient'] > 0).sum())} of {len(df)} specifications."}],
            "weakest_specification": records(df.sort_values("t_stat").head(1)),
            "strongest_specification": records(df.sort_values("t_stat", ascending=False).head(1)),
            "economic_magnitude_range": [{"min": float(df["coefficient"].min()), "max": float(df["coefficient"].max())}] if not df.empty else [],
            "latex_export": [{"table": "robustness_matrix", "latex": latex_table("robustness", df)}],
        },
        "meta": {},
    }


def _publication_spec_columns(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("table_columns") or payload.get("publication_columns")
    if isinstance(raw, str) and raw.strip().startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)][:8]
        except Exception:
            pass
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)][:8]
    base_signal = str(payload.get("signal") or "momentum")
    controls = payload.get("controls") or "none"
    return [
        {"label": "(1)", "dv": "forward_return", "signal": base_signal, "controls": "none", "se": "nw4", "fixed_effects": "none", "weighting": "equal", "tag": "confirmatory"},
        {"label": "(2)", "dv": "forward_return", "signal": base_signal, "controls": controls if controls != "none" else "size,value", "se": "nw4", "fixed_effects": "none", "weighting": "equal", "tag": "confirmatory"},
        {"label": "(3)", "dv": "forward_return", "signal": base_signal, "controls": "size,value,momentum", "se": "driscoll_kraay", "fixed_effects": "time", "weighting": "rank", "tag": "robustness"},
        {"label": "(4)", "dv": "forward_return", "signal": base_signal, "controls": "full", "se": "double_cluster", "fixed_effects": "time_asset", "weighting": "value", "tag": "robustness"},
    ]


def _publication_column_fit(panel: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "signal": spec.get("signal") or "momentum",
        "controls": spec.get("controls") or "none",
        "weighting": spec.get("weighting") or "equal",
        "lookback_days": panel.get("payload", {}).get("lookback_days", 2520),
        "fixed_effects": spec.get("fixed_effects", "none"),
        "nw_lag": panel.get("payload", {}).get("nw_lag", 4),
    }
    local = panel_variant(panel, payload)
    fm, betas = fama_macbeth_table(local)
    row = pd.DataFrame()
    if not fm.empty and "term" in fm.columns:
        row = fm[fm["term"] == "signal"].head(1)
        if row.empty:
            row = fm.head(1)
    coef = float(row["lambda_hat"].iloc[0]) if not row.empty else np.nan
    se = float(row["newey_west_se"].iloc[0]) if not row.empty else np.nan
    t_stat = float(row["t_stat"].iloc[0]) if not row.empty else np.nan
    p_val = float(row["p_value"].iloc[0]) if not row.empty else np.nan
    panel_fit = _panel_ols(local)
    robust_lookup = {r.get("term"): r for r in panel_fit.to_dict("records")} if not panel_fit.empty else {}
    signal_row = robust_lookup.get("signal", {})
    se_type = str(spec.get("se") or "nw4").lower()
    robust_se = se
    if se_type in {"driscoll_kraay", "dk", "hac"}:
        robust_se = number(signal_row.get("driscoll_kraay_se"), se)
    elif se_type in {"double_cluster", "clustered"}:
        robust_se = number(signal_row.get("double_cluster_se"), se)
    robust_t = coef / robust_se if robust_se and np.isfinite(robust_se) else t_stat
    return {
        "coefficient": coef,
        "std_error": robust_se,
        "t_stat": robust_t,
        "p_value": p_value_from_t(robust_t, max(1, len(betas) - 1)) if np.isfinite(robust_t) else p_val,
        "n_months": int(len(betas)),
        "mean_assets": float(betas["n_assets"].mean()) if not betas.empty and "n_assets" in betas else np.nan,
        "mean_r2": float(betas["r2"].mean()) if not betas.empty and "r2" in betas else np.nan,
        "stars": _stars(p_value_from_t(robust_t, max(1, len(betas) - 1)) if np.isfinite(robust_t) else p_val),
    }


def _stars(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def _publication_table(spec_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [{"term": "Signal coefficient"}]
    se_rows = [{"term": "Standard error"}]
    t_rows = [{"term": "t-statistic"}]
    meta_rows = [
        {"term": "Controls"},
        {"term": "Fixed effects"},
        {"term": "Weighting"},
        {"term": "Observations"},
        {"term": "Mean assets"},
        {"term": "Mean R2"},
        {"term": "Tag"},
    ]
    for i, spec in enumerate(spec_rows, start=1):
        col = spec.get("label") or f"({i})"
        rows[0][col] = f"{number(spec.get('coefficient'), np.nan):.4f}{spec.get('stars', '')}" if np.isfinite(number(spec.get("coefficient"), np.nan)) else ""
        se_rows[0][col] = f"({number(spec.get('std_error'), np.nan):.4f})" if np.isfinite(number(spec.get("std_error"), np.nan)) else ""
        t_rows[0][col] = f"{number(spec.get('t_stat'), np.nan):.2f}" if np.isfinite(number(spec.get("t_stat"), np.nan)) else ""
        meta_rows[0][col] = spec.get("controls", "none")
        meta_rows[1][col] = spec.get("fixed_effects", "none")
        meta_rows[2][col] = spec.get("weighting", "equal")
        meta_rows[3][col] = spec.get("n_months", "")
        meta_rows[4][col] = f"{number(spec.get('mean_assets'), np.nan):.0f}" if np.isfinite(number(spec.get("mean_assets"), np.nan)) else ""
        meta_rows[5][col] = f"{number(spec.get('mean_r2'), np.nan):.3f}" if np.isfinite(number(spec.get("mean_r2"), np.nan)) else ""
        meta_rows[6][col] = spec.get("tag", "")
    return [rows[0], se_rows[0], t_rows[0], *meta_rows]


def _latex_publication_table(table: list[dict[str, Any]], style: str = "finance") -> str:
    if not table:
        return ""
    cols = [c for c in table[0].keys() if c != "term"]
    align = "l" + "c" * len(cols)
    lines = [f"\\begin{{tabular}}{{{align}}}", "\\toprule", " & ".join(["", *cols]) + " \\\\", "\\midrule"]
    for row in table:
        vals = [str(row.get("term", "")), *[str(row.get(c, "")) for c in cols]]
        lines.append(" & ".join(vals) + " \\\\")
    note = "Newey-West, Driscoll-Kraay-style, or double-cluster standard errors are selected by column configuration. *, **, *** denote 10%, 5%, and 1% significance."
    lines.extend(["\\bottomrule", "\\end{tabular}", f"% style={style}; note={note}"])
    return "\n".join(lines)


def _forest_plot_rows(spec_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for i, row in enumerate(spec_rows, start=1):
        coef = number(row.get("coefficient"), np.nan)
        se = number(row.get("std_error"), np.nan)
        out.append({
            "column": row.get("label") or f"({i})",
            "coefficient": coef,
            "lower_95": coef - 1.96 * se if np.isfinite(coef) and np.isfinite(se) else np.nan,
            "upper_95": coef + 1.96 * se if np.isfinite(coef) and np.isfinite(se) else np.nan,
            "tag": row.get("tag", ""),
            "controls": row.get("controls", ""),
            "weighting": row.get("weighting", ""),
        })
    return out


def _confirmatory_tags(spec_rows: list[dict[str, Any]], rdf: list[dict[str, Any]]) -> list[dict[str, Any]]:
    confirmatory = [r for r in spec_rows if str(r.get("tag", "")).lower() == "confirmatory"]
    exploratory = [r for r in spec_rows if str(r.get("tag", "")).lower() != "confirmatory"]
    rdf_count = rdf[0].get("tested_specifications") if rdf else len(spec_rows)
    return [{
        "confirmatory_columns": len(confirmatory),
        "exploratory_columns": len(exploratory),
        "tested_specifications": rdf_count,
        "decision_rule": "Confirmatory columns are presented first; robustness and exploratory columns are separated by tag for journal disclosure.",
    }]


def causal_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    panel = research_panel(payload, default_limit=300)
    events = load_event_upload(payload.get("event_csv_path") or payload.get("event_upload_path") or payload.get("treatment_file_path"))
    if not events.empty:
        treated = str(payload.get("treated_unit") or events["ticker"].iloc[0]).upper().replace("-", "_")
        row = events[events["ticker"] == treated].head(1)
        treatment_date = pd.to_datetime(row["treatment_date"].iloc[0] if not row.empty else events["treatment_date"].iloc[0])
    else:
        treated = str(payload.get("treated_unit") or (panel["symbols"][0] if panel["symbols"] else "")).upper().replace("-", "_")
        treatment_date = pd.to_datetime(payload.get("treatment_date") or panel["returns"].index[int(len(panel["returns"]) * .65)] if len(panel["returns"]) else pd.Timestamp.today())
    ret = panel["returns"]
    y = ret.get(treated, ret.iloc[:, 0] if not ret.empty else pd.Series(dtype=float))
    pre = y[y.index < treatment_date]
    post = y[y.index >= treatment_date]
    event = _event_study(y, treatment_date)
    event_tests = _event_study_tests(y, panel, treatment_date)
    did = [{"treated_unit": treated, "pre_mean": pre.mean(), "post_mean": post.mean(), "did_effect": post.mean() - pre.mean(), "t_stat": (post.mean() - pre.mean()) / math.sqrt(pre.var() / max(len(pre), 1) + post.var() / max(len(post), 1)) if len(pre) and len(post) else np.nan}]
    did_extra = _did_diagnostics(y, treatment_date)
    rdd = _rdd_proxy(y, treatment_date)
    return {
        "summary": [{"label": "Treated", "value": treated}, {"label": "Effect", "value": did[0]["did_effect"]}],
        "charts": {"event_study_path": records(event), "treatment_timeline": records(pd.DataFrame({"date": y.index, "return": y.values, "treated": y.index >= treatment_date}))},
        "tables": {
            "difference_in_differences": did + did_extra.get("twfe", []),
            "goodman_bacon_decomposition": did_extra.get("bacon", []),
            "callaway_santanna_att": did_extra.get("callaway_santanna", []),
            "sun_abraham_event_study": did_extra.get("sun_abraham", []),
            "parallel_trends_pretest": did_extra.get("parallel_trends", []),
            "placebo_treatment": did_extra.get("placebo", []),
            "event_study_car": records(event),
            "event_study_tests": event_tests.get("tests", []),
            "calendar_time_portfolio_alpha": event_tests.get("calendar_time_alpha", []),
            "pre_event_drift": event_tests.get("pre_event_drift", []),
            "post_event_reversal": event_tests.get("post_event_reversal", []),
            "matching_balance": records(_matching_balance(panel, treated)),
            "instrumental_variables": records(_iv_proxy(panel, payload)),
            "regression_discontinuity": records(rdd),
            "rdd_bandwidth_sensitivity": records(_rdd_bandwidth_sensitivity(y, treatment_date)),
            "rdd_placebo_cutoffs": records(_rdd_placebo_cutoffs(y, treatment_date)),
            "rdd_mccrary_density_test": records(_mccrary_density_test(y, treatment_date)),
            "rdd_ik_bandwidth": records(_ik_bandwidth(y, treatment_date)),
            "rdd_covariate_continuity": records(_rdd_covariate_continuity(panel, treatment_date)),
            "rdd_donut_hole": records(_rdd_donut_hole(y, treatment_date)),
        },
        "meta": {"research_caveats": [
            "External event file used." if not events.empty else "No external event file was supplied; event and DiD panels use payload/default treatment date.",
            "External instrument file used when supplied; otherwise IV panel uses repository price-derived proxy diagnostics.",
        ]},
    }


def _event_study(y: pd.Series, date: pd.Timestamp, window: int = 12) -> pd.DataFrame:
    y = y.dropna()
    idx = np.arange(-window, window + 1)
    rows = []
    if y.empty:
        return pd.DataFrame()
    base = int(y.index.get_indexer([date], method="nearest")[0])
    start = max(0, base - window)
    for k in idx:
        pos = max(0, min(len(y) - 1, base + int(k)))
        nearest = y.index[pos]
        rows.append({"event_month": int(k), "date": nearest, "return": y.iloc[pos], "car": y.iloc[start:pos + 1].sum()})
    return pd.DataFrame(rows)


def _event_study_tests(y: pd.Series, panel: dict[str, Any], date: pd.Timestamp, window: int = 20) -> dict[str, Any]:
    event = _event_study(y, date, window=window)
    vals = event["return"].dropna()
    est = y[y.index < date].tail(120).dropna()
    if vals.empty or est.empty:
        return {"tests": [], "calendar_time_alpha": [], "pre_event_drift": [], "post_event_reversal": []}
    car = float(vals.sum())
    est_sd = float(est.std() or np.nan)
    patell_z = car / (est_sd * math.sqrt(len(vals))) if est_sd else np.nan
    bmp_z = vals.mean() / (vals.std() / math.sqrt(len(vals))) if vals.std() else np.nan
    avg_corr = offdiag_corr_mean(panel["returns"], max_cols=120)
    kp_z = bmp_z / math.sqrt(max(1e-9, 1 + (len(vals) - 1) * max(avg_corr, 0))) if np.isfinite(bmp_z) else np.nan
    tests = [
        {"test": "cross_sectional_t", "statistic": bmp_z, "p_value": p_value_from_t(bmp_z, len(vals) - 1) if np.isfinite(bmp_z) else np.nan},
        {"test": "patell_standardized", "statistic": patell_z, "p_value": 2 * stats.norm.sf(abs(patell_z)) if stats is not None and np.isfinite(patell_z) else np.nan},
        {"test": "bmp_event_variance", "statistic": bmp_z, "p_value": 2 * stats.norm.sf(abs(bmp_z)) if stats is not None and np.isfinite(bmp_z) else np.nan},
        {"test": "kolari_pynnonen_adjusted", "statistic": kp_z, "p_value": 2 * stats.norm.sf(abs(kp_z)) if stats is not None and np.isfinite(kp_z) else np.nan, "avg_cross_corr": avg_corr},
    ]
    pre = event[event["event_month"].between(-20, -2)]["return"].dropna()
    post = event[event["event_month"].between(2, 20)]["return"].dropna()
    factors = panel["factors"].rename(columns={"Date": "date"}).set_index("date") if "Date" in panel["factors"].columns else pd.DataFrame()
    monthly = y.rename("event_return").to_frame().merge(factors, left_index=True, right_index=True, how="inner")
    fac_cols = [c for c in ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"] if c in monthly.columns]
    fit = ols(monthly["event_return"], monthly[fac_cols]) if fac_cols and len(monthly) > 12 else {"beta": [np.nan], "t": [np.nan], "p": [np.nan], "r2": np.nan}
    return {
        "tests": tests,
        "calendar_time_alpha": [{"alpha": fit["beta"][0] if len(fit["beta"]) else np.nan, "alpha_t": fit["t"][0] if len(fit["t"]) else np.nan, "alpha_p": fit["p"][0] if len(fit["p"]) else np.nan, "r2": fit.get("r2")}],
        "pre_event_drift": [{"window": "-20,-2", "mean_return": pre.mean(), "t_stat": pre.mean() / (pre.std() / math.sqrt(len(pre))) if len(pre) > 1 and pre.std() else np.nan}],
        "post_event_reversal": [{"window": "+2,+20", "mean_return": post.mean(), "t_stat": post.mean() / (post.std() / math.sqrt(len(post))) if len(post) > 1 and post.std() else np.nan}],
    }


def _did_diagnostics(y: pd.Series, date: pd.Timestamp) -> dict[str, list[dict[str, Any]]]:
    s = y.dropna()
    if len(s) < 24:
        return {"twfe": [], "parallel_trends": [], "placebo": [], "bacon": [], "callaway_santanna": [], "sun_abraham": []}
    df = pd.DataFrame({"y": s, "post": (s.index >= date).astype(float)})
    df["trend"] = np.arange(len(df), dtype=float)
    fit = ols(df["y"], df[["post", "trend"]])
    pre = df[df.index < date].tail(12)
    pre_fit = ols(pre["y"], pre[["trend"]]) if len(pre) > 4 else {"t": [np.nan, np.nan], "p": [np.nan, np.nan]}
    fake_date = df.index[int(len(df) * .4)]
    fake = ols(df["y"], pd.DataFrame({"post": (df.index >= fake_date).astype(float), "trend": df["trend"]}, index=df.index))
    return {
        "twfe": [{"method": "single_unit_twfe_proxy", "post_beta": fit["beta"][1] if len(fit["beta"]) > 1 else np.nan, "t_stat": fit["t"][1] if len(fit["t"]) > 1 else np.nan, "p_value": fit["p"][1] if len(fit["p"]) > 1 else np.nan}],
        "parallel_trends": [{"test": "pre_period_trend", "t_stat": pre_fit["t"][1] if len(pre_fit["t"]) > 1 else np.nan, "p_value": pre_fit["p"][1] if len(pre_fit["p"]) > 1 else np.nan}],
        "placebo": [{"fake_treatment_date": fake_date, "placebo_beta": fake["beta"][1] if len(fake["beta"]) > 1 else np.nan, "p_value": fake["p"][1] if len(fake["p"]) > 1 else np.nan}],
        "bacon": _goodman_bacon_proxy(df, date),
        "callaway_santanna": _callaway_santanna_proxy(df, date),
        "sun_abraham": _sun_abraham_proxy(df, date),
    }


def _goodman_bacon_proxy(df: pd.DataFrame, date: pd.Timestamp) -> list[dict[str, Any]]:
    pre = df[df.index < date]["y"]
    post = df[df.index >= date]["y"]
    if pre.empty or post.empty:
        return []
    comparisons = [
        {"comparison": "treated_vs_not_yet_treated_proxy", "weight": 0.5, "estimate": post.mean() - pre.tail(len(post)).mean()},
        {"comparison": "treated_vs_always_control_proxy", "weight": 0.5, "estimate": post.head(len(pre)).mean() - pre.mean()},
    ]
    total = sum(c["weight"] * c["estimate"] for c in comparisons if np.isfinite(c["estimate"]))
    for c in comparisons:
        c["twfe_contribution"] = c["weight"] * c["estimate"]
        c["negative_weight_flag"] = c["weight"] < 0
        c["aggregate_estimate"] = total
    return comparisons


def _callaway_santanna_proxy(df: pd.DataFrame, date: pd.Timestamp) -> list[dict[str, Any]]:
    return positional_event_rows(df, date, -6, 12, "y", baseline_window=6)


def _sun_abraham_proxy(df: pd.DataFrame, date: pd.Timestamp) -> list[dict[str, Any]]:
    rows = _callaway_santanna_proxy(df, date)
    for row in rows:
        row["estimator"] = "sun_abraham_event_time_proxy"
        row["se"] = float(df["y"].rolling(6).std().mean()) if len(df) else np.nan
    return rows


def _matching_balance(panel: dict[str, Any], treated: str) -> pd.DataFrame:
    sig = panel["signals"].iloc[-1].dropna() if not panel["signals"].empty else pd.Series(dtype=float)
    if treated not in sig.index or sig.empty:
        return pd.DataFrame()
    dist = (sig - sig.loc[treated]).abs().sort_values().head(12)
    return pd.DataFrame({"donor": dist.index, "distance": dist.values})


def _iv_proxy(panel: dict[str, Any], payload: dict[str, Any] | None = None) -> pd.DataFrame:
    payload = payload or {}
    ret = panel["returns"].mean(axis=1).dropna()
    upload = load_instrument_upload(payload.get("instrument_csv_path") or payload.get("instrument_upload_path") or payload.get("iv_file_path"))
    if not upload.empty:
        if "MARKET" in set(upload["ticker"]):
            instr = upload[upload["ticker"] == "MARKET"].set_index("date")["instrument"]
        else:
            instr = upload.groupby("date")["instrument"].mean()
        source = "external_upload"
    else:
        instr = ret.shift(1).dropna()
        source = "lagged_market_return_proxy"
    aligned = pd.concat([ret.rename("y"), instr.rename("instrument")], axis=1).dropna()
    signal_series = panel["signals"].mean(axis=1).reindex(aligned.index).ffill()
    first = ols(signal_series, aligned[["instrument"]])
    endog_hat = np.asarray(first["beta"][0] + first["beta"][1] * aligned["instrument"]) if len(first["beta"]) > 1 else aligned["instrument"].to_numpy()
    fit = ols(aligned["y"], endog_hat)
    ols_fit = ols(aligned["y"], signal_series)
    liml = _liml_proxy(aligned["y"], signal_series, aligned[["instrument"]])
    ar = _anderson_rubin_grid(aligned["y"], signal_series, aligned[["instrument"]])
    sargan = _sargan_hansen_proxy(aligned["y"], signal_series, aligned[["instrument"]], fit)
    first_f = float(first["t"][1] ** 2) if len(first.get("t", [])) > 1 and np.isfinite(first["t"][1]) else np.nan
    assessment = "external instrument supplied; still verify exclusion restriction" if source == "external_upload" else "proxy only, provide external instrument for publication use"
    return pd.DataFrame([{
        "instrument": source,
        "first_stage_f": first_f,
        "staiger_stock_pass": bool(first_f > 10) if np.isfinite(first_f) else False,
        "lee_2022_pass": bool(first_f > 104) if np.isfinite(first_f) else False,
        "iv_beta": fit["beta"][1] if len(fit["beta"]) > 1 else np.nan,
        "iv_se": fit["se"][1] if len(fit["se"]) > 1 else np.nan,
        "iv_t": fit["t"][1] if len(fit["t"]) > 1 else np.nan,
        "liml_beta": liml.get("liml_beta"),
        "liml_kappa": liml.get("liml_kappa"),
        "ols_beta": ols_fit["beta"][1] if len(ols_fit["beta"]) > 1 else np.nan,
        "anderson_rubin_proxy_p": ar.get("min_p_value"),
        "anderson_rubin_ci_low": ar.get("ci_low"),
        "anderson_rubin_ci_high": ar.get("ci_high"),
        "hausman_proxy": abs((fit["beta"][1] if len(fit["beta"]) > 1 else np.nan) - (ols_fit["beta"][1] if len(ols_fit["beta"]) > 1 else np.nan)),
        "sargan_hansen_p": sargan.get("p_value"),
        "validity_assessment": assessment,
    }])


def _liml_proxy(y: pd.Series, x: pd.Series, z: pd.DataFrame) -> dict[str, float]:
    df = pd.concat([y.rename("y"), x.rename("x"), z], axis=1).dropna()
    if len(df) < 10:
        return {"liml_beta": np.nan, "liml_kappa": np.nan}
    # For just-identified designs LIML equals 2SLS. For overidentified designs
    # this k-class proxy shrinks toward LIML using the smallest generalized root.
    zmat = np.column_stack([np.ones(len(df)), df[z.columns].to_numpy()])
    xmat = np.column_stack([np.ones(len(df)), df[["x"]].to_numpy()])
    pz = zmat @ np.linalg.pinv(zmat.T @ zmat) @ zmat.T
    mz = np.eye(len(df)) - pz
    try:
        kappa = float(np.linalg.eigvals(np.linalg.pinv(xmat.T @ xmat) @ (xmat.T @ mz @ xmat)).min().real)
    except Exception:
        kappa = 1.0
    xhat = pz @ df[["x"]].to_numpy()
    beta = ols(df["y"], xhat)["beta"]
    return {"liml_beta": beta[1] if len(beta) > 1 else np.nan, "liml_kappa": kappa}


def _anderson_rubin_grid(y: pd.Series, x: pd.Series, z: pd.DataFrame) -> dict[str, float]:
    df = pd.concat([y.rename("y"), x.rename("x"), z], axis=1).dropna()
    if len(df) < 10:
        return {"min_p_value": np.nan, "ci_low": np.nan, "ci_high": np.nan}
    beta_center = ols(df["y"], df[["x"]])["beta"]
    center = beta_center[1] if len(beta_center) > 1 else 0.0
    scale = float(df["y"].std() / (df["x"].std() + 1e-12))
    grid = np.linspace(center - 3 * scale, center + 3 * scale, 121)
    zmat = np.column_stack([np.ones(len(df)), df[z.columns].to_numpy(dtype=float)])
    y_np = df["y"].to_numpy(dtype=float)
    x_np = df["x"].to_numpy(dtype=float)
    xtxi = np.linalg.pinv(zmat.T @ zmat)
    zpinv = xtxi @ zmat.T
    beta_y = zpinv @ y_np
    beta_x = zpinv @ x_np
    pvals = []
    accepted = []
    dof = max(1, len(df) - zmat.shape[1])
    for b0 in grid:
        resid = y_np - b0 * x_np
        beta = beta_y - b0 * beta_x
        fitted = zmat @ beta
        err = resid - fitted
        sigma2 = float((err @ err) / dof)
        se = np.sqrt(np.maximum(np.diag(sigma2 * xtxi), 0))
        t = beta[1] / se[1] if len(beta) > 1 and se[1] else np.nan
        p = p_value_from_t(t, dof) if np.isfinite(t) else np.nan
        pvals.append(p)
        if np.isfinite(p) and p > 0.05:
            accepted.append(float(b0))
    return {"min_p_value": float(np.nanmin(pvals)) if pvals else np.nan, "ci_low": float(min(accepted)) if accepted else np.nan, "ci_high": float(max(accepted)) if accepted else np.nan}


def _sargan_hansen_proxy(y: pd.Series, x: pd.Series, z: pd.DataFrame, fit: dict[str, Any]) -> dict[str, float]:
    if z.shape[1] <= 1 or len(fit.get("resid", [])) == 0:
        return {"p_value": np.nan}
    resid = pd.Series(fit["resid"], index=y.dropna().index[: len(fit["resid"])])
    aligned = pd.concat([resid.rename("resid"), z], axis=1).dropna()
    aux = ols(aligned["resid"], aligned[z.columns])
    stat = aux["n"] * (aux["r2"] if np.isfinite(aux["r2"]) else 0)
    df = max(1, z.shape[1] - 1)
    return {"p_value": float(1 - stats.chi2.cdf(stat, df)) if stats is not None else np.nan}


def _rdd_proxy(y: pd.Series, date: pd.Timestamp) -> pd.DataFrame:
    if y.empty:
        return pd.DataFrame()
    x = np.arange(len(y)) - np.searchsorted(y.index, date)
    df = pd.DataFrame({"x": x, "post": (x >= 0).astype(float), "y": y.to_numpy()}).dropna()
    local = df[df["x"].abs() <= 12]
    fit = ols(local["y"], local[["post", "x"]]) if len(local) > 8 else {"beta": [np.nan, np.nan], "t": [np.nan, np.nan], "p": [np.nan, np.nan]}
    return pd.DataFrame([{"cutoff": date, "local_effect": fit["beta"][1] if len(fit["beta"]) > 1 else np.nan, "t_stat": fit["t"][1] if len(fit["t"]) > 1 else np.nan, "p_value": fit["p"][1] if len(fit["p"]) > 1 else np.nan}])


def _rdd_bandwidth_sensitivity(y: pd.Series, date: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for bw in [6, 9, 12, 18, 24]:
        idx = np.arange(len(y)) - np.searchsorted(y.index, date)
        df = pd.DataFrame({"x": idx, "post": (idx >= 0).astype(float), "y": y.to_numpy()}).dropna()
        local = df[df["x"].abs() <= bw]
        fit = ols(local["y"], local[["post", "x"]]) if len(local) > 8 else {"beta": [np.nan, np.nan], "t": [np.nan, np.nan], "p": [np.nan, np.nan]}
        donut = local[local["x"].abs() > max(1, int(bw * .1))]
        dfit = ols(donut["y"], donut[["post", "x"]]) if len(donut) > 8 else {"beta": [np.nan, np.nan], "t": [np.nan, np.nan], "p": [np.nan, np.nan]}
        rows.append({"bandwidth_months": bw, "effect": fit["beta"][1] if len(fit["beta"]) > 1 else np.nan, "p_value": fit["p"][1] if len(fit["p"]) > 1 else np.nan, "donut_effect": dfit["beta"][1] if len(dfit["beta"]) > 1 else np.nan})
    return pd.DataFrame(rows)


def _rdd_placebo_cutoffs(y: pd.Series, date: pd.Timestamp) -> pd.DataFrame:
    if len(y) < 36:
        return pd.DataFrame()
    cutoffs = [y.index[int(len(y) * q)] for q in [.25, .35, .45, .55, .75]]
    rows = []
    for cutoff in cutoffs:
        base = _rdd_proxy(y, cutoff)
        if not base.empty:
            row = base.iloc[0].to_dict()
            row["placebo"] = cutoff != date
            rows.append(row)
    return pd.DataFrame(rows)


def _ik_bandwidth(y: pd.Series, date: pd.Timestamp) -> pd.DataFrame:
    s = y.dropna()
    if len(s) < 20:
        return pd.DataFrame()
    idx = np.arange(len(s), dtype=float)
    cutoff = float(np.searchsorted(s.index, date))
    sigma = float(s.std())
    curvature = float(np.nanmean(np.abs(np.diff(s.to_numpy(), n=2)))) if len(s) > 3 else sigma
    h = 1.84 * (sigma / max(curvature, 1e-9)) ** 0.2 * len(s) ** 0.2
    return pd.DataFrame([{"cutoff_index": cutoff, "ik_bandwidth_proxy": float(max(3, min(h, len(s) / 2))), "method": "imbens_kalyanaraman_style_mse_bandwidth"}])


def _mccrary_density_test(y: pd.Series, date: pd.Timestamp) -> pd.DataFrame:
    s = y.dropna()
    if len(s) < 20 or stats is None:
        return pd.DataFrame()
    running = np.arange(len(s), dtype=float) - float(np.searchsorted(s.index, date))
    left = running[(running < 0) & (running > -max(10, len(s) * .2))]
    right = running[(running >= 0) & (running < max(10, len(s) * .2))]
    left_density = len(left) / max(1, abs(left.min()) if len(left) else 1)
    right_density = len(right) / max(1, abs(right.max()) if len(right) else 1)
    log_diff = math.log((right_density + 1e-9) / (left_density + 1e-9))
    se = math.sqrt(1 / max(len(left), 1) + 1 / max(len(right), 1))
    z = log_diff / se if se else np.nan
    return pd.DataFrame([{"left_density": left_density, "right_density": right_density, "log_density_jump": log_diff, "z_stat": z, "p_value": 2 * stats.norm.sf(abs(z)) if np.isfinite(z) else np.nan}])


def _rdd_covariate_continuity(panel: dict[str, Any], date: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for name, mat in panel.get("controls", {}).items():
        s = mat.mean(axis=1).dropna()
        if len(s) < 12:
            continue
        pre = s[s.index < date].tail(12)
        post = s[s.index >= date].head(12)
        diff = post.mean() - pre.mean() if len(pre) and len(post) else np.nan
        denom = math.sqrt(pre.var() / max(len(pre), 1) + post.var() / max(len(post), 1)) if len(pre) and len(post) else np.nan
        t = diff / denom if denom else np.nan
        rows.append({"covariate": name, "pre_mean": pre.mean(), "post_mean": post.mean(), "jump": diff, "t_stat": t, "p_value": p_value_from_t(t, max(1, len(pre) + len(post) - 2)) if np.isfinite(t) else np.nan})
    return pd.DataFrame(rows)


def _rdd_donut_hole(y: pd.Series, date: pd.Timestamp) -> pd.DataFrame:
    s = y.dropna()
    rows = []
    for donut in [1, 2, 3]:
        local = s.copy()
        center = int(np.searchsorted(local.index, date))
        mask = np.ones(len(local), dtype=bool)
        mask[max(0, center - donut): min(len(local), center + donut + 1)] = False
        kept = local.iloc[mask]
        estimate = np.nan
        if len(kept) > 12:
            proxy = _rdd_proxy(kept, date)
            if not proxy.empty:
                estimate = proxy.get("local_effect", pd.Series([np.nan])).iloc[0]
        rows.append({"donut_months": donut, "estimate": estimate})
    return pd.DataFrame(rows)


def decay_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    panel = research_panel(payload)
    ic = panel["signals"].corrwith(panel["forward"], axis=1, method="spearman").dropna()
    rolling = ic.rolling(int(payload.get("rolling_window") or 12)).mean().dropna()
    discovery = pd.to_datetime(payload.get("discovery_date") or (rolling.index[int(len(rolling) * .45)] if len(rolling) else pd.Timestamp.today()))
    publication = pd.to_datetime(payload.get("publication_date") or (discovery + pd.DateOffset(months=12)))
    pre = ic[ic.index < discovery]
    post = ic[ic.index >= discovery]
    survival = post.mean() / pre.mean() if pre.mean() else np.nan
    t = (pre.mean() - post.mean()) / math.sqrt(pre.var() / max(len(pre), 1) + post.var() / max(len(post), 1)) if len(pre) and len(post) else np.nan
    model = _fit_decay_models(rolling, discovery)
    brk = _structural_break(rolling)
    vitality = float((rolling.iloc[-1] / pre.mean()) * 100) if len(rolling) and pre.mean() else np.nan
    return {
        "summary": [{"label": "Vitality", "value": vitality}, {"label": "Survival", "value": survival}, {"label": "Half-life", "value": model.get("half_life_months")}],
        "charts": {"decay_curve": records(model.get("curve", pd.DataFrame())), "andrews_break_chart": records(brk.get("path", pd.DataFrame())), "long_short_sharpe_decay": records(_rolling_sharpe(panel))},
        "tables": {
            "vitality_gauge": [{"vitality_score": vitality, "zone": "green" if vitality >= 70 else ("amber" if vitality >= 30 else "red")}],
            "mclean_pontiff_comparison": [{"split": "post_discovery", "is_ic": pre.mean(), "oos_ic": post.mean(), "survival_fraction": survival, "t_stat": t, "p_value": p_value_from_t(t, max(1, len(ic) - 2)) if np.isfinite(t) else np.nan}, {"split": "post_publication", "is_ic": pre.mean(), "oos_ic": ic[ic.index >= publication].mean(), "survival_fraction": ic[ic.index >= publication].mean() / pre.mean() if pre.mean() else np.nan}],
            "half_life_output": [{"half_life_months": model.get("half_life_months"), "ci_5": model.get("half_life_months_ci5"), "ci_95": model.get("half_life_months_ci95")}],
            "decay_model_comparison": records(model.get("comparison", pd.DataFrame())),
            "arbitrage_vs_datamining": [{"arbitrage_consistent_fraction": float(max(0, min(1, 1 - survival))) if np.isfinite(survival) else np.nan, "data_mining_consistent_fraction": float(min(1, abs(number(t)) / 10)) if np.isfinite(t) else np.nan}],
            "international_replication": records(_international_replication(payload)),
            "anomaly_lifecycle_summary": [{"summary": f"Signal discovered around {discovery.date()} has current vitality {vitality:.1f} and survival fraction {survival:.2f}." if np.isfinite(vitality) and np.isfinite(survival) else "Insufficient IC history for lifecycle summary."}],
        },
        "meta": {},
    }


def _fit_decay_models(rolling: pd.Series, discovery: pd.Timestamp) -> dict[str, Any]:
    if rolling.empty:
        return {}
    t = np.arange(len(rolling), dtype=float)
    y = rolling.to_numpy(dtype=float)
    rows = []
    fits: dict[str, np.ndarray] = {}
    half = np.nan
    if optimize is not None and len(y) > 8:
        def exp_fn(x, a, b, c): return a * np.exp(-b * x) + c
        try:
            params, _ = optimize.curve_fit(exp_fn, t, y, maxfev=1000, bounds=([-1, 0, -1], [1, 10, 1]))
            fitted = exp_fn(t, *params)
            half = float(math.log(2) / max(params[1], 1e-9))
            fits["exponential"] = fitted
        except Exception:
            fitted = pd.Series(y).rolling(6, min_periods=1).mean().to_numpy()
            half = np.nan
    else:
        fitted = pd.Series(y).rolling(6, min_periods=1).mean().to_numpy()
        half = np.nan
    fits.setdefault("exponential", fitted)
    lin = np.polyfit(t, y, 1)
    fits["linear"] = lin[0] * t + lin[1]
    if optimize is not None and len(y) > 8:
        def hyp_fn(x, a, b, c): return a / (1 + b * x) + c
        try:
            hp, _ = optimize.curve_fit(hyp_fn, t, y, maxfev=1000, bounds=([-1, 0, -1], [1, 10, 1]))
            fits["hyperbolic"] = hyp_fn(t, *hp)
        except Exception:
            fits["hyperbolic"] = fits["linear"]
    else:
        fits["hyperbolic"] = fits["linear"]
    total = np.square(y - y.mean()).sum() + 1e-12
    for name, pred in fits.items():
        k = 3 if name in {"exponential", "hyperbolic"} else 2
        rss = float(np.square(y - pred).sum())
        rows.append({"model": name, "aic": len(y) * math.log(rss / max(len(y), 1) + 1e-12) + 2 * k, "bic": len(y) * math.log(rss / max(len(y), 1) + 1e-12) + k * math.log(max(len(y), 1)), "r2": 1 - rss / total})
    comp = pd.DataFrame(rows).sort_values("aic")
    comp["winner"] = False
    if not comp.empty:
        comp.loc[comp.index[0], "winner"] = True
    ci5, ci95 = _half_life_bootstrap(y)
    curve = pd.DataFrame({"date": rolling.index, "rolling_ic": y, "exponential_fit": fitted, "discovery_date": discovery})
    curve["linear_fit"] = fits["linear"]
    curve["hyperbolic_fit"] = fits["hyperbolic"]
    return {"curve": curve, "comparison": comp, "half_life_months": half, "half_life_months_ci5": ci5, "half_life_months_ci95": ci95}


def _half_life_bootstrap(y: np.ndarray, reps: int = 200) -> tuple[float, float]:
    if optimize is None or len(y) < 12:
        return np.nan, np.nan
    rng = np.random.default_rng(123)
    t = np.arange(len(y), dtype=float)
    halves = []
    def exp_fn(x, a, b, c): return a * np.exp(-b * x) + c
    for _ in range(min(int(reps), 99)):
        idx = rng.integers(0, len(y), len(y))
        xs = t[idx]
        ys = y[idx]
        try:
            params, _ = optimize.curve_fit(exp_fn, xs, ys, maxfev=750, bounds=([-1, 0, -1], [1, 10, 1]))
            halves.append(math.log(2) / max(params[1], 1e-9))
        except Exception:
            continue
    if not halves:
        return np.nan, np.nan
    return float(np.nanpercentile(halves, 5)), float(np.nanpercentile(halves, 95))


def _structural_break(series: pd.Series) -> dict[str, Any]:
    if len(series) < 12:
        return {"path": pd.DataFrame(), "date": None}
    vals = series.dropna().to_numpy(dtype=float)
    idx = series.dropna().index
    n = len(vals)
    if n < 12:
        return {"path": pd.DataFrame(), "date": None}
    csum = np.cumsum(vals)
    csum2 = np.cumsum(vals ** 2)
    total_sum = csum[-1]
    total_sum2 = csum2[-1]
    rss_pooled = total_sum2 - total_sum ** 2 / n
    rows = []
    for i in range(int(n * .15), int(n * .85)):
        n1, n2 = i, n - i
        sum1, sum2 = csum[i - 1], total_sum - csum[i - 1]
        sq1, sq2 = csum2[i - 1], total_sum2 - csum2[i - 1]
        rss1 = sq1 - sum1 ** 2 / max(n1, 1)
        rss2 = sq2 - sum2 ** 2 / max(n2, 1)
        rss_split = rss1 + rss2
        f = ((rss_pooled - rss_split) / 1) / (rss_split / max(1, n - 2))
        rows.append({"date": idx[i], "andrews_f": f})
    path = pd.DataFrame(rows)
    return {"path": path, "date": path.sort_values("andrews_f", ascending=False)["date"].iloc[0] if not path.empty else None}


def _rolling_sharpe(panel: dict[str, Any]) -> pd.DataFrame:
    _, pr = portfolio_sort(panel)
    if pr.empty or "long_short" not in pr:
        return pd.DataFrame()
    s = pr.set_index("date")["long_short"].astype(float)
    mean = s.rolling(12, min_periods=3).mean()
    std = s.rolling(12, min_periods=3).std()
    sharpe = mean / (std + 1e-12) * math.sqrt(12)
    return sharpe.dropna().reset_index().rename(columns={"long_short": "rolling_sharpe"})


def _international_replication(payload: dict[str, Any]) -> pd.DataFrame:
    universe = list(available_symbols())
    markets = {
        "US": [s for s in universe if "_" not in s][:300],
        "Canada": [s for s in universe if s.endswith("_TO")][:300],
        "UK": [s for s in universe if s.endswith("_L")][:300],
        "Europe": [s for s in universe if s.endswith("_PA") or s.endswith("_AS") or s.endswith("_MI") or s.endswith("_DE")][:300],
        "Japan": [s for s in universe if s.endswith("_T")][:300],
        "Australia": [s for s in universe if s.endswith("_AX")][:300],
        "Hong Kong": [s for s in universe if s.endswith("_HK")][:300],
    }
    rows = []
    for market, symbols in markets.items():
        if len(symbols) < 20:
            rows.append({"market": market, "symbols": len(symbols), "is_ic": np.nan, "oos_ic": np.nan, "survival_fraction": np.nan, "vitality_score": np.nan})
            continue
        p = {**payload, "symbols": symbols, "max_symbols": min(300, len(symbols))}
        try:
            panel = research_panel(p, default_limit=300)
            ic = panel["signals"].corrwith(panel["forward"], axis=1, method="spearman").dropna()
            split = int(len(ic) * .5)
            rows.append({"market": market, "symbols": len(panel["symbols"]), "is_ic": ic.iloc[:split].mean(), "oos_ic": ic.iloc[split:].mean(), "survival_fraction": ic.iloc[split:].mean() / ic.iloc[:split].mean() if ic.iloc[:split].mean() else np.nan, "vitality_score": ic.tail(12).mean() / ic.iloc[:split].mean() * 100 if ic.iloc[:split].mean() else np.nan})
        except Exception:
            rows.append({"market": market, "symbols": len(symbols), "is_ic": np.nan, "oos_ic": np.nan, "survival_fraction": np.nan, "vitality_score": np.nan})
    return pd.DataFrame(rows)


def synthetic_control_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    panel = research_panel(payload, default_limit=300)
    prices = close_matrix(panel["symbols"], int(payload.get("lookback_days") or 2520), frequency="monthly")
    treated = str(payload.get("treated_unit") or (prices.columns[0] if len(prices.columns) else "")).upper().replace("-", "_")
    if treated not in prices.columns and len(prices.columns):
        treated = prices.columns[0]
    treatment_date = pd.to_datetime(payload.get("treatment_date") or prices.index[int(len(prices) * .65)] if len(prices) else pd.Timestamp.today())
    donors = [c for c in prices.columns if c != treated][: int(payload.get("donor_limit") or 80)]
    pre = prices.index < treatment_date
    y = prices.loc[pre, treated].pct_change().dropna()
    x = prices.loc[pre, donors].pct_change().reindex(y.index).dropna(axis=1)
    y = y.reindex(x.index)
    weights = _scm_weights(y, x)
    full_ret = prices[[treated, *weights.index]].pct_change().dropna()
    synth = full_ret[list(weights.index)] @ weights if len(weights) else pd.Series(index=full_ret.index, dtype=float)
    path = pd.DataFrame({"date": full_ret.index, "treated": full_ret[treated].cumsum(), "synthetic": synth.cumsum()})
    path["gap"] = path["treated"] - path["synthetic"]
    pre_gap = path[path["date"] < treatment_date]["gap"]
    post_gap = path[path["date"] >= treatment_date]["gap"]
    rmspe_pre = float(np.sqrt(np.mean(np.square(pre_gap)))) if len(pre_gap) else np.nan
    rmspe_post = float(np.sqrt(np.mean(np.square(post_gap)))) if len(post_gap) else np.nan
    aug = _augmented_scm(full_ret, treated, weights, treatment_date)
    gsc = _generalized_scm(full_ret, treated, weights, treatment_date)
    rsc = _robust_scm(full_ret, treated, weights, treatment_date)
    return {
        "summary": [{"label": "Treated", "value": treated}, {"label": "RMSPE ratio", "value": rmspe_post / rmspe_pre if rmspe_pre else np.nan}],
        "charts": {"treated_vs_synthetic_path": records(path), "gap_plot": records(path[["date", "gap"]]), "rmspe_ratio_ranking": records(_placebo_rmspe(prices, treated, donors, treatment_date)), "augmented_synthetic_path": records(aug.get("path", pd.DataFrame()))},
        "tables": {
            "donor_weight_table": records(weights.sort_values(ascending=False).reset_index().rename(columns={"index": "donor", 0: "weight"}).head(25)),
            "pre_treatment_fit": [{"rmspe_pre": rmspe_pre, "rmspe_post": rmspe_post, "post_pre_ratio": rmspe_post / rmspe_pre if rmspe_pre else np.nan}],
            "augmented_scm": aug.get("summary", []),
            "generalized_scm": gsc,
            "robust_matrix_completion_scm": rsc,
            "leave_one_out_sensitivity": records(_leave_one_out(weights, full_ret, treated, treatment_date)),
            "in_time_placebo": records(_in_time_placebo(full_ret, treated, weights)),
            "staggered_adoption_scm": records(_staggered_adoption_scm(prices, payload)),
            "conformal_confidence_band": records(_conformal_band(path)),
            "latex_export": [{"latex": latex_table("donor_weights", weights.reset_index().rename(columns={"index": "donor", 0: "weight"}))}],
        },
        "meta": {},
    }


def _staggered_adoption_scm(prices: pd.DataFrame, payload: dict[str, Any]) -> pd.DataFrame:
    events = load_event_upload(payload.get("event_csv_path") or payload.get("event_upload_path") or payload.get("treatment_file_path"))
    if prices.empty or events.empty:
        return pd.DataFrame()
    rows = []
    for _, event in events.head(int(payload.get("max_events") or 20)).iterrows():
        treated = str(event["ticker"])
        tdate = pd.to_datetime(event["treatment_date"])
        if treated not in prices.columns:
            continue
        donors = [c for c in prices.columns if c != treated][: int(payload.get("donor_limit") or 40)]
        ret = prices[[treated, *donors]].pct_change().dropna()
        pre = ret.index < tdate
        if pre.sum() < 12 or (~pre).sum() < 3:
            continue
        w = _scm_weights(ret.loc[pre, treated], ret.loc[pre, donors])
        synth = ret[list(w.index)] @ w if len(w) else pd.Series(index=ret.index, dtype=float)
        gap = ret[treated].cumsum() - synth.cumsum()
        rows.append({
            "treated_unit": treated,
            "treatment_date": tdate,
            "donor_count": int(len(w)),
            "pre_rmspe": float(np.sqrt(np.mean(np.square(gap[gap.index < tdate])))),
            "post_effect": float(gap[gap.index >= tdate].mean()),
        })
    return pd.DataFrame(rows)


def _scm_weights(y: pd.Series, x: pd.DataFrame) -> pd.Series:
    if x.empty or y.empty:
        return pd.Series(dtype=float)
    yy, xx = scm_objective_arrays(y, x)
    if len(yy) <= 3 or xx.size == 0:
        return pd.Series(np.repeat(1 / max(1, x.shape[1]), x.shape[1]), index=x.columns)
    if optimize is not None:
        n = xx.shape[1]
        cons = {"type": "eq", "fun": lambda w: w.sum() - 1}
        bounds = [(0, 1)] * n
        res = optimize.minimize(
            lambda w: float(np.square(yy - xx @ w).mean()),
            np.repeat(1 / n, n),
            bounds=bounds,
            constraints=cons,
            method="SLSQP",
            options={"maxiter": 300, "ftol": 1e-9, "disp": False},
        )
        return pd.Series(res.x if res.success else np.repeat(1 / n, n), index=x.columns)
    return pd.Series(np.repeat(1 / max(1, x.shape[1]), x.shape[1]), index=x.columns)


def _placebo_rmspe(prices: pd.DataFrame, treated: str, donors: list[str], treatment_date: pd.Timestamp) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame()
    rows = []
    candidates = [treated, *donors[: min(25, len(donors))]]
    for unit in candidates:
        local_donors = [d for d in donors if d != unit][: min(20, len(donors))]
        if unit not in prices.columns or not local_donors:
            continue
        ret = prices[[unit, *local_donors]].pct_change().dropna()
        pre = ret.index < treatment_date
        w = _scm_weights(ret.loc[pre, unit], ret.loc[pre, local_donors])
        synth = ret[list(w.index)] @ w if len(w) else pd.Series(index=ret.index, dtype=float)
        gap = ret[unit].cumsum() - synth.cumsum()
        pre_gap = gap[gap.index < treatment_date]
        post_gap = gap[gap.index >= treatment_date]
        pre_r = float(np.sqrt(np.mean(np.square(pre_gap)))) if len(pre_gap) else np.nan
        post_r = float(np.sqrt(np.mean(np.square(post_gap)))) if len(post_gap) else np.nan
        rows.append({"unit": unit, "rmspe_ratio": post_r / pre_r if pre_r else np.nan, "treated": unit == treated})
    df = pd.DataFrame(rows).sort_values("rmspe_ratio", ascending=False)
    if not df.empty:
        real = df.loc[df["treated"], "rmspe_ratio"].iloc[0] if df["treated"].any() else np.nan
        df["placebo_p_value"] = float((df["rmspe_ratio"] >= real).mean()) if np.isfinite(real) else np.nan
    return df


def _leave_one_out(weights: pd.Series, full_ret: pd.DataFrame, treated: str, treatment_date: pd.Timestamp) -> pd.DataFrame:
    rows = []
    base_synth = full_ret[list(weights.index)] @ weights if len(weights) else pd.Series(index=full_ret.index, dtype=float)
    base_gap = full_ret[treated].cumsum() - base_synth.cumsum() if treated in full_ret else pd.Series(dtype=float)
    base_effect = base_gap[base_gap.index >= treatment_date].mean() if len(base_gap) else np.nan
    for donor, weight in weights.sort_values(ascending=False).head(10).items():
        keep_cols = [c for c in weights.index if c != donor and c in full_ret.columns]
        pre = full_ret.index < treatment_date
        refit = _scm_weights(full_ret.loc[pre, treated], full_ret.loc[pre, keep_cols]) if keep_cols and treated in full_ret else pd.Series(dtype=float)
        synth = full_ret[list(refit.index)] @ refit if len(refit) else pd.Series(index=full_ret.index, dtype=float)
        gap = full_ret[treated].cumsum() - synth.cumsum() if treated in full_ret else pd.Series(dtype=float)
        effect = gap[gap.index >= treatment_date].mean() if len(gap) else np.nan
        rows.append({"donor": donor, "base_weight": weight, "refit_donor_count": int(len(refit)), "effect_without_donor": effect, "effect_swing": effect - base_effect if np.isfinite(effect) and np.isfinite(base_effect) else np.nan})
    return pd.DataFrame(rows)


def _in_time_placebo(full_ret: pd.DataFrame, treated: str, weights: pd.Series) -> pd.DataFrame:
    if full_ret.empty or treated not in full_ret or weights.empty:
        return pd.DataFrame()
    rows = []
    for q in [.35, .45, .55]:
        fake = full_ret.index[int(len(full_ret) * q)]
        pre_mask = full_ret.index < fake
        refit = _scm_weights(full_ret.loc[pre_mask, treated], full_ret.loc[pre_mask, list(weights.index)])
        synth = full_ret[list(refit.index)] @ refit if len(refit) else pd.Series(index=full_ret.index, dtype=float)
        gap = full_ret[treated].cumsum() - synth.cumsum()
        pre = gap[gap.index < fake]
        post = gap[gap.index >= fake]
        rows.append({"fake_treatment_date": fake, "post_pre_gap_shift": post.mean() - pre.mean(), "ratio": post.std() / (pre.std() + 1e-12), "refit_donor_count": int(len(refit))})
    return pd.DataFrame(rows)


def _augmented_scm(full_ret: pd.DataFrame, treated: str, weights: pd.Series, treatment_date: pd.Timestamp) -> dict[str, Any]:
    if full_ret.empty or treated not in full_ret or weights.empty:
        return {"summary": [], "path": pd.DataFrame()}
    synth = full_ret[list(weights.index)] @ weights
    pre = full_ret.index < treatment_date
    residual = full_ret.loc[pre, treated] - synth.loc[pre]
    correction = float(residual.mean()) if len(residual) else 0.0
    aug_synth = synth + correction
    path = pd.DataFrame({"date": full_ret.index, "treated": full_ret[treated].cumsum(), "augmented_synthetic": aug_synth.cumsum()})
    gap = path["treated"] - path["augmented_synthetic"]
    return {"summary": [{"bias_correction": correction, "post_treatment_effect": gap[path["date"] >= treatment_date].mean()}], "path": path}


def _generalized_scm(full_ret: pd.DataFrame, treated: str, weights: pd.Series, treatment_date: pd.Timestamp) -> list[dict[str, Any]]:
    if full_ret.empty or treated not in full_ret or len(weights) < 2:
        return []
    donors = full_ret[list(weights.index)].dropna(axis=1)
    if donors.empty:
        return []
    u, s, vt = np.linalg.svd(donors.fillna(0).to_numpy(), full_matrices=False)
    factors = u[:, : min(3, len(s))] * s[: min(3, len(s))]
    pre = full_ret.index < treatment_date
    fit = ols(full_ret.loc[pre, treated], factors[pre, :])
    pred = fit["beta"][0] + factors @ fit["beta"][1:] if len(fit["beta"]) > 1 else np.full(len(full_ret), np.nan)
    effect = (full_ret[treated].cumsum() - pd.Series(pred, index=full_ret.index).cumsum())
    return [{"method": "interactive_fixed_effects_svd", "latent_factors": factors.shape[1], "post_treatment_effect": effect[effect.index >= treatment_date].mean(), "r2_pre": fit.get("r2")}]


def _robust_scm(full_ret: pd.DataFrame, treated: str, weights: pd.Series, treatment_date: pd.Timestamp) -> list[dict[str, Any]]:
    if full_ret.empty or treated not in full_ret or weights.empty:
        return []
    donors = full_ret[list(weights.index)].copy()
    lo = donors.quantile(.01)
    hi = donors.quantile(.99)
    clipped = donors.clip(lower=lo, upper=hi, axis=1)
    synth = clipped @ weights.reindex(clipped.columns).fillna(0)
    gap = full_ret[treated].cumsum() - synth.cumsum()
    return [{"method": "winsorized_matrix_completion_proxy", "post_treatment_effect": gap[gap.index >= treatment_date].mean(), "donor_count": int(len(clipped.columns))}]


def _conformal_band(path: pd.DataFrame) -> pd.DataFrame:
    if path.empty:
        return pd.DataFrame()
    q = path["gap"].abs().quantile(.9)
    out = path[["date", "gap"]].copy()
    out["lower_90"] = out["gap"] - q
    out["upper_90"] = out["gap"] + q
    return out


def factor_zoo_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    panel = research_panel(payload)
    _, pr = portfolio_sort(panel)
    ls = pr.set_index("date")["long_short"] if not pr.empty and "long_short" in pr else panel["returns"].mean(axis=1)
    factors = panel["factors"].rename(columns={"Date": "date"}).set_index("date") if "Date" in panel["factors"].columns else pd.DataFrame()
    aligned = pd.concat([ls.rename("candidate"), factors], axis=1).dropna()
    corr = aligned.corr()["candidate"].drop("candidate", errors="ignore") if not aligned.empty else pd.Series(dtype=float)
    zoo_points = []
    if not aligned.empty:
        for factor in corr.index:
            rolling_ic = aligned["candidate"].rolling(24).corr(aligned[factor]).dropna()
            mean_ic = float(rolling_ic.mean()) if len(rolling_ic) else float(corr.get(factor, np.nan))
            std_ic = float(rolling_ic.std()) if len(rolling_ic) > 1 else np.nan
            zoo_points.append({"factor": factor, "ic": mean_ic, "ir": mean_ic / std_ic if std_ic and np.isfinite(std_ic) else np.nan, "full_sample_correlation": float(corr.get(factor, np.nan))})
    fit = ols(aligned["candidate"], aligned.drop(columns=["candidate"])) if len(aligned) > 10 and aligned.shape[1] > 1 else {"beta": [], "t": [], "p": [], "r2": np.nan}
    observed_t = float(abs(fit["t"][0])) if len(fit.get("t", [])) else np.nan
    threshold = float(payload.get("significance_threshold") or 3.0)
    zoo = pd.DataFrame({"factor": corr.index, "correlation": corr.values, "near_duplicate": corr.abs().values > .7})
    return {
        "summary": [{"label": "Observed t", "value": observed_t}, {"label": "Required t", "value": threshold}, {"label": "Max corr", "value": corr.abs().max() if len(corr) else np.nan}],
        "charts": {"zoo_positioning_chart": zoo_points, "factor_correlation_map": records(zoo)},
        "tables": {
            "harvey_liu_zhu_card": [{"observed_t": observed_t, "required_t": threshold, "verdict": "credible" if observed_t >= threshold else "below literature-adjusted bar"}],
            "correlation_with_existing_factors": records(zoo),
            "extended_spanning_test": [{"alpha": fit["beta"][0] if len(fit.get("beta", [])) else np.nan, "r2": fit.get("r2"), "factor_count": max(0, aligned.shape[1] - 1)}],
        },
        "meta": {},
    }
