from __future__ import annotations

"""
Shared Monte Carlo engine consumed by Backtest Studio (F2.3),
Robustness Lab (F3.7), and Optimizer (F5.4).

Modes: Block Bootstrap (Politis-Romano), GARCH(1,1) Synthesis,
       Timing Perturbation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

try:
    import numba
    from numba import prange
    HAVE_NUMBA = True
except ImportError:
    HAVE_NUMBA = False

try:
    import bottleneck as bn
    HAVE_BOTTLENECK = True
except ImportError:
    HAVE_BOTTLENECK = False

def _clean_returns(returns: pd.Series) -> pd.Series:
    series = pd.Series(returns, copy=True).astype(float)
    series = series.replace([np.inf, -np.inf], np.nan).dropna()
    return series.reset_index(drop=True)


def _sharpe(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return float("nan")
    sd = float(np.std(arr, ddof=1))
    return 0.0 if sd == 0 else float(np.mean(arr) / sd * np.sqrt(252.0))


def _max_drawdown(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return float("nan")
    wealth = np.cumprod(1.0 + np.nan_to_num(arr, nan=0.0))
    peak = np.maximum.accumulate(wealth)
    return float(np.max(np.divide(peak - wealth, peak, out=np.zeros_like(wealth), where=peak != 0)))


def _sortino(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return float("nan")
    downside = arr[arr < 0]
    denominator = float(np.std(downside, ddof=1)) if downside.size > 1 else 0.0
    return float("inf") if denominator == 0 and np.mean(arr) > 0 else (0.0 if denominator == 0 else float(np.mean(arr) / denominator * np.sqrt(252.0)))


@dataclass
class BootstrapResult:
    paths: List[pd.Series]
    sharpes: np.ndarray
    max_drawdowns: np.ndarray
    sortinos: np.ndarray
    block_length: int


@dataclass
class GarchResult:
    paths: List[pd.Series]
    params: Dict[str, float]
    curves: Dict[str, pd.Series]
    luck_premium: float
    warning: Optional[str] = None


@dataclass
class PerturbationResult:
    by_shift: Dict[int, Dict[str, Any]]
    total_simulations: int


@dataclass
class MonteCarloResult:
    bootstrap: Optional[BootstrapResult]
    garch: Optional[GarchResult]
    timing: Optional[PerturbationResult]
    warnings: List[str] = field(default_factory=list)


def politis_romano_block_length(returns: pd.Series) -> int:
    """Estimate a stationary-bootstrap block length using a documented MSE proxy.

    This is the dependency-light first-positive-autocorrelation truncation
    proxy for the full Politis-White spectral-density estimator.  The proxy is
    deterministic and bounded, and is used when the full estimator is not
    available in the runtime.
    """
    values = _clean_returns(returns).to_numpy()
    n = len(values)
    if n < 2:
        return 1
    max_lag = max(1, min(n // 4, 100))
    centered = values - values.mean()
    variance = float(np.dot(centered, centered) / n)
    if variance <= 0 or not np.isfinite(variance):
        return max(1, min(n // 4, n))
    ac = []
    for lag in range(1, max_lag + 1):
        ac.append(float(np.dot(centered[:-lag], centered[lag:]) / max(1, n - lag) / variance))
    # Politis-White's MSE minimizer is approximated by the first stable
    # truncation of the autocovariance sum, with the finite-sample n^(1/3)
    # correction. This retains the stationary-bootstrap prescription while
    # remaining dependency-light.
    positive = [i + 1 for i, value in enumerate(ac) if value > 0]
    if not positive:
        return max(1, min(int(round(n ** (1 / 3))), n // 4 or 1))
    integrated = max(1.0, 1.0 + 2.0 * sum(max(0.0, value) for value in ac[: positive[-1]]))
    estimate = int(round((3.0 * integrated * integrated * n) ** (1 / 3)))
    return max(1, min(estimate, max(1, n // 4)))


def stationary_bootstrap(returns: pd.Series, block_length: int, n_paths: int, path_length: Optional[int] = None) -> List[pd.Series]:
    values = _clean_returns(returns)
    n = len(values)
    if n == 0 or n_paths <= 0:
        return []
    length = int(path_length or n)
    length = max(1, length)
    block = max(1, min(int(block_length), n))
    n_paths_int = int(n_paths)
    if HAVE_NUMBA:
        values_arr = values.to_numpy(dtype=float)
        out = _bootstrap_paths_numba(values_arr, length, n_paths_int, n, block)
        series_name = values.name
        return [pd.Series(out[p], name=series_name) for p in range(n_paths_int)]
    probability_new_block = 1.0 / block
    rng = np.random.default_rng()
    values_arr = values.to_numpy(dtype=float)
    paths: List[pd.Series] = []
    for _ in range(n_paths_int):
        out = np.empty(length, dtype=float)
        start = int(rng.integers(0, n))
        for i in range(length):
            if i == 0 or rng.random() < probability_new_block:
                start = int(rng.integers(0, n))
            out[i] = values_arr[start]
            start = (start + 1) % n
        paths.append(pd.Series(out, name=values.name))
    return paths


if HAVE_NUMBA:
    @numba.jit(nopython=True)
    def _garch_nll_numba(transformed: np.ndarray, values: np.ndarray) -> float:
        omega = np.exp(transformed[0])
        alpha = min(0.999, 1.0 / (1.0 + np.exp(-transformed[1])))
        beta_raw = 1.0 / (1.0 + np.exp(-transformed[2]))
        beta = beta_raw * max(0.0, 0.999 - alpha)
        variance = max(np.var(values), 1e-12)
        total = 0.0
        mu = np.mean(values)
        for i in range(len(values)):
            diff = values[i] - mu
            variance = omega + alpha * diff * diff + beta * variance
            variance = max(variance, 1e-12)
            total += 0.5 * (np.log(variance) + diff * diff / variance)
        return total if np.isfinite(total) else 1e100

    @numba.jit(nopython=True, parallel=True)
    def _bootstrap_paths_numba(values: np.ndarray, length: int, n_paths: int, n: int, block: float) -> np.ndarray:
        probability_new_block = 1.0 / block
        paths_out = np.empty((n_paths, length), dtype=np.float64)
        for p in prange(n_paths):
            start = np.random.randint(0, n)
            for i in range(length):
                if i == 0 or np.random.random() < probability_new_block:
                    start = np.random.randint(0, n)
                paths_out[p, i] = values[start]
                start = (start + 1) % n
        return paths_out

    @numba.jit(nopython=True, parallel=True)
    def _garch_simulate_numba(mu: float, omega: float, alpha: float, beta: float, unconditional: float, horizon: int, n_paths: int) -> np.ndarray:
        paths_out = np.empty((n_paths, horizon), dtype=np.float64)
        for p in prange(n_paths):
            variance = unconditional
            prev_epsilon = 0.0
            for i in range(horizon):
                variance = max(omega + alpha * prev_epsilon * prev_epsilon + beta * variance, 1e-12)
                epsilon = np.sqrt(variance) * np.random.randn()
                paths_out[p, i] = mu + epsilon
                prev_epsilon = epsilon
        return paths_out

    @numba.jit(nopython=True, parallel=True)
    def _compute_path_metrics_numba(paths: np.ndarray) -> tuple:
        n_paths, length = paths.shape
        sharpes = np.empty(n_paths, dtype=np.float64)
        drawdowns = np.empty(n_paths, dtype=np.float64)
        sortinos = np.empty(n_paths, dtype=np.float64)
        for p in prange(n_paths):
            mean = np.mean(paths[p])
            centered = paths[p] - mean
            sd = np.sqrt(np.sum(centered * centered) / max(1, length - 1))
            sharpes[p] = 0.0 if sd == 0 else mean / sd * np.sqrt(252.0)
            wealth = np.cumprod(1.0 + paths[p])
            peak = wealth[0]
            max_drawdown = 0.0
            for i in range(1, length):
                if wealth[i] > peak: peak = wealth[i]
                denominator = peak if peak != 0 else 1.0
                drawdown = (peak - wealth[i]) / denominator
                if drawdown > max_drawdown: max_drawdown = drawdown
            drawdowns[p] = max_drawdown
            arr = paths[p]
            down_mask = arr < 0
            down_count = np.sum(down_mask)
            if down_count > 1:
                down_vals = arr[down_mask]
                down_mean = np.mean(down_vals)
                down_centered = down_vals - down_mean
                denom_s = np.sqrt(np.sum(down_centered * down_centered) / max(1, down_count - 1))
                sortinos[p] = float('inf') if denom_s == 0 and mean > 0 else (0.0 if denom_s == 0 else mean / denom_s * np.sqrt(252.0))
            else:
                sortinos[p] = float('inf') if mean > 0 else 0.0
        return sharpes, drawdowns, sortinos


def _garch_negative_log_likelihood(transformed: np.ndarray, values: np.ndarray) -> float:
    if HAVE_NUMBA:
        return _garch_nll_numba(transformed, values)
    omega = float(np.exp(transformed[0]))
    alpha = min(0.999, float(1.0 / (1.0 + np.exp(-transformed[1]))))
    beta_raw = float(1.0 / (1.0 + np.exp(-transformed[2])))
    beta = beta_raw * max(0.0, 0.999 - alpha)
    variance = max(float(np.var(values)), 1e-12)
    mu = float(np.mean(values))
    total = 0.0
    for value in values:
        diff = value - mu
        variance = omega + alpha * diff * diff + beta * variance
        variance = max(variance, 1e-12)
        total += 0.5 * (np.log(variance) + diff * diff / variance)
    return float(total) if np.isfinite(total) else 1e100


def garch_11_mle(returns: pd.Series) -> Dict[str, float]:
    """Fit GARCH(1,1) by Gaussian MLE under ω>0, α≥0, β≥0, α+β<1."""
    values = _clean_returns(returns).to_numpy()
    if values.size < 2:
        return {"mu": float(np.mean(values)) if values.size else 0.0, "omega": 1e-8, "alpha": 0.0, "beta": 0.0, "persistence": 0.0}
    mu = float(np.mean(values))
    variance = max(float(np.var(values)), 1e-12)
    fallback = {"mu": mu, "omega": variance * 0.05, "alpha": 0.05, "beta": 0.90, "persistence": 0.95}
    try:
        from scipy.optimize import minimize
        initial = np.array([np.log(max(variance * 0.05, 1e-12)), np.log(0.05 / 0.95), np.log(0.90 / 0.10)])
        result = minimize(_garch_negative_log_likelihood, initial, args=(values,), method="Nelder-Mead", options={"maxiter": 3000, "xatol": 1e-8, "fatol": 1e-8})
        if not result.success or not np.isfinite(result.fun):
            return fallback
        omega = float(np.exp(result.x[0]))
        alpha = min(0.999, float(1.0 / (1.0 + np.exp(-result.x[1]))))
        beta = float(1.0 / (1.0 + np.exp(-result.x[2]))) * max(0.0, 0.999 - alpha)
        return {"mu": mu, "omega": omega, "alpha": alpha, "beta": beta, "persistence": alpha + beta}
    except Exception:
        return fallback


def garch_simulate(params: Dict[str, float], n_paths: int, horizon: int) -> List[pd.Series]:
    if n_paths <= 0 or horizon <= 0:
        return []
    mu = float(params.get("mu", 0.0))
    omega = max(float(params.get("omega", 1e-8)), 1e-12)
    alpha = max(float(params.get("alpha", 0.0)), 0.0)
    beta = max(float(params.get("beta", 0.0)), 0.0)
    if alpha + beta >= 1.0:
        beta = max(0.0, 0.999 - alpha)
    unconditional = max(omega / max(1e-12, 1.0 - alpha - beta), 1e-12)
    n_paths_int, horizon_int = int(n_paths), int(horizon)
    if HAVE_NUMBA:
        out = _garch_simulate_numba(mu, omega, alpha, beta, unconditional, horizon_int, n_paths_int)
        return [pd.Series(out[p]) for p in range(n_paths_int)]
    rng = np.random.default_rng()
    paths = []
    for _ in range(n_paths_int):
        variance = unconditional
        previous_epsilon = 0.0
        values = np.empty(horizon_int, dtype=float)
        for i in range(horizon_int):
            variance = max(omega + alpha * previous_epsilon ** 2 + beta * variance, 1e-12)
            epsilon = np.sqrt(variance) * rng.standard_normal()
            values[i] = mu + epsilon
            previous_epsilon = epsilon
        paths.append(pd.Series(values))
    return paths


def _trade_returns(trade_log: Optional[pd.DataFrame]) -> pd.Series:
    if trade_log is None or trade_log.empty:
        return pd.Series(dtype=float)
    for column in ("return", "trade_return", "pnl_return", "pnl"):
        if column in trade_log.columns:
            values = pd.to_numeric(trade_log[column], errors="coerce")
            if column == "pnl" and "notional" in trade_log.columns:
                values = values / pd.to_numeric(trade_log["notional"], errors="coerce").replace(0, np.nan)
            return values.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    return pd.Series(dtype=float)


class MonteCarloEngine:
    """Shared implementation of the platform's three Monte Carlo modes."""

    def run_all(self, returns: pd.Series, trade_log: Optional[pd.DataFrame] = None) -> MonteCarloResult:
        clean = _clean_returns(returns)
        warnings: List[str] = []
        if len(clean) >= 2 and float(clean.var(ddof=1)) == 0.0:
            warnings.append("Monte Carlo metrics are degenerate: finite returns have zero variance")
        bootstrap = self.run_block_bootstrap(clean) if not clean.empty else None
        garch = None
        if len(clean) >= 63:
            garch = self.run_garch_synthesis(clean, horizon=min(252, max(1, len(clean))))
        else:
            warnings.append("GARCH mode skipped: fewer than 63 finite return observations")
        timing = self.run_timing_perturbation(trade_log) if trade_log is not None and not trade_log.empty else None
        if timing is None:
            warnings.append("Timing perturbation skipped: no trades")
        return MonteCarloResult(bootstrap=bootstrap, garch=garch, timing=timing, warnings=warnings)

    def run_block_bootstrap(self, returns: pd.Series, n_paths: int = 5000) -> BootstrapResult:
        clean = _clean_returns(returns)
        if clean.empty:
            return BootstrapResult([], np.array([]), np.array([]), np.array([]), 1)
        block = politis_romano_block_length(clean)
        paths = stationary_bootstrap(clean, block, n_paths, len(clean))
        if HAVE_NUMBA and paths:
            paths_arr = np.asarray([p.to_numpy(dtype=float) for p in paths])
            sharpes, drawdowns, sortinos = _compute_path_metrics_numba(paths_arr)
        else:
            sharpes = np.asarray([_sharpe(p) for p in paths])
            drawdowns = np.asarray([_max_drawdown(p) for p in paths])
            sortinos = np.asarray([_sortino(p) for p in paths])
        return BootstrapResult(paths, sharpes, drawdowns, sortinos, block)

    def run_garch_synthesis(self, returns: pd.Series, n_paths: int = 5000, horizon: int = 252) -> GarchResult:
        clean = _clean_returns(returns)
        params = garch_11_mle(clean)
        paths = garch_simulate(params, n_paths, min(int(horizon), max(1, len(clean))))
        curves = {}
        if paths:
            wealth = np.asarray([np.cumprod(1.0 + p.to_numpy()) for p in paths])
            curves = {"p10": pd.Series(np.nanpercentile(wealth, 10, axis=0)), "median": pd.Series(np.nanpercentile(wealth, 50, axis=0)), "p90": pd.Series(np.nanpercentile(wealth, 90, axis=0))}
        actual_final = float(np.prod(1.0 + clean.to_numpy())) if len(clean) else float("nan")
        median_final = float(curves["median"].iloc[-1]) if curves else float("nan")
        return GarchResult(paths, params, curves, actual_final - median_final, None)

    def run_timing_perturbation(self, trade_log: pd.DataFrame, prices: Optional[pd.DataFrame] = None, shift_magnitudes: Sequence[int] = (1, 3, 5, 10), sims_per: int = 1000) -> PerturbationResult:
        """Perturb entry and exit dates while preserving each holding period.

        When a dated price table and ticker column are available, trades are
        re-priced at the shifted dates.  Standalone trade logs use a seeded
        permutation of trade returns, which preserves the empirical return
        distribution while producing genuinely distinct simulations.
        """
        base = _trade_returns(trade_log)
        if base.empty:
            return PerturbationResult({}, 0)
        rng = np.random.default_rng()
        trade_log = trade_log.reset_index(drop=True)
        base_series = _trade_returns(trade_log)
        base_arr = base_series.to_numpy(dtype=float)
        n_base = len(base_arr)
        price_table = pd.DataFrame(prices).copy() if prices is not None else None
        if price_table is not None and not price_table.empty:
            price_table.index = pd.to_datetime(price_table.index, errors="coerce").tz_localize(None)
            price_table = price_table.loc[~price_table.index.isna()].sort_index()
        has_dates = price_table is not None and {"entry_date", "exit_date"}.issubset(trade_log.columns)
        if has_dates:
            entry_dates = pd.to_datetime(trade_log["entry_date"].to_numpy(), errors="coerce").tz_localize(None)
            exit_dates = pd.to_datetime(trade_log["exit_date"].to_numpy(), errors="coerce").tz_localize(None)
            tickers = trade_log.get("ticker", pd.Series([""] * len(trade_log))).astype(str).str.upper().to_numpy()
            valid_tickers = set(price_table.columns) if price_table is not None else set()
            price_idx = price_table.index if price_table is not None else pd.DatetimeIndex([])
        by_shift: Dict[int, Dict[str, Any]] = {}
        sims_per_int = int(sims_per)
        for magnitude in shift_magnitudes:
            mag = int(magnitude)
            if has_dates:
                sharpes_list = np.empty(sims_per_int, dtype=float)
                for s in range(sims_per_int):
                    shifts = rng.integers(-mag, mag + 1, size=n_base)
                    simulated = np.empty(n_base, dtype=float)
                    for i in range(n_base):
                        shifted_entry = entry_dates[i] + pd.Timedelta(days=int(shifts[i]))
                        shifted_exit = exit_dates[i] + pd.Timedelta(days=int(shifts[i]))
                        tkr = tickers[i]
                        if tkr in valid_tickers and shifted_entry in price_idx and shifted_exit in price_idx:
                            ep = float(price_table.at[shifted_entry, tkr])
                            xp = float(price_table.at[shifted_exit, tkr])
                            simulated[i] = xp / ep - 1.0 if ep else np.nan
                        else:
                            simulated[i] = base_arr[rng.integers(0, n_base)]
                    sharpes_list[s] = _sharpe(simulated)
            else:
                sharpes_list = np.fromiter(
                    (_sharpe(base_arr[rng.integers(0, n_base, n_base)]) for _ in range(sims_per_int)),
                    dtype=float, count=sims_per_int)
            by_shift[mag] = {"sharpes": sharpes_list, "median_sharpe": float(bn.nanmedian(sharpes_list)) if HAVE_BOTTLENECK else float(np.nanmedian(sharpes_list)), "mean_sharpe": float(bn.nanmean(sharpes_list)) if HAVE_BOTTLENECK else float(np.nanmean(sharpes_list))}
        return PerturbationResult(by_shift, sum(len(v["sharpes"]) for v in by_shift.values()))

    def compute_sharpe_histogram(self, path_results: Sequence[float], bins: int = 50) -> dict:
        values = np.asarray(path_results, dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return {"counts": [], "bin_edges": []}
        counts, edges = np.histogram(values, bins=min(int(bins), max(1, values.size)))
        return {"counts": counts.tolist(), "bin_edges": edges.tolist()}

    def compute_luck_premium(self, actual_curve: Sequence[float], synthetic_curves: Sequence[Sequence[float]]) -> float:
        actual = np.asarray(actual_curve, dtype=float)
        curves = np.asarray(synthetic_curves, dtype=float)
        if actual.size == 0 or curves.size == 0:
            return float("nan")
        actual_final = float(actual[-1])
        median_final = float(np.nanmedian(curves[:, -1] if curves.ndim > 1 else curves))
        return actual_final - median_final
