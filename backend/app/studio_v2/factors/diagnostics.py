from __future__ import annotations

"""
Factor diagnostics (F4.5-F4.8).

Crowding monitor (contemporaneous only), factor half-life decay
tracking, Gram-Schmidt orthogonalization against 40-factor library,
interaction screener for pairwise IC improvement.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import numpy as np
import pandas as pd

from .evaluator import IcDecayCurve, InstantIcDiagnostics

try:
    import numba
    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False


if _HAS_NUMBA:
    @numba.njit(cache=True)
    def _ewma_corr_scan_numba(values: np.ndarray, max_lag: int) -> tuple:
        best_lag, best_corr = 1, -1.0
        n = len(values)
        for lag in range(1, max_lag + 1):
            alpha = 2.0 / (lag + 1.0)
            ewma = np.empty(n)
            ewma[0] = values[0]
            for i in range(1, n): ewma[i] = alpha * values[i] + (1.0 - alpha) * ewma[i - 1]
            x_mean, y_mean = np.mean(values), np.mean(ewma)
            numerator = np.sum((values - x_mean) * (ewma - y_mean)); denominator = np.sqrt(np.sum((values - x_mean) ** 2) * np.sum((ewma - y_mean) ** 2))
            corr = numerator / denominator if denominator > 0 else 0.0
            if corr > best_corr: best_lag, best_corr = lag, corr
        return best_lag, best_corr


@dataclass
class CrowdingResult:
    etf_ticker: str
    percentile: float
    traffic_light: str
    historical: pd.Series
    label: str = "Contemporaneous snapshot; not validated as a forward return predictor"


@dataclass
class DecayResult:
    vintages: pd.DataFrame
    slope: float
    p_value: float
    verdict: str


@dataclass
class OrthogonalizationResult:
    residual: Any
    raw_icir: float
    orthogonalized_icir: float
    novelty_fraction: float
    redundant_fraction: float
    warning: str = ""


@dataclass
class InteractionResult:
    interaction: Any
    ic: float
    icir: float
    parent_a_ic: float = np.nan
    parent_b_ic: float = np.nan
    trivial: bool = False


class CrowdingMonitor:
    mapping = {"momentum": "MTUM", "value": "VLUE", "low-vol": "USMV", "low_vol": "USMV", "quality": "QUAL", "size": "IJR"}

    def map_factor_to_etf(self, factor_returns: Any) -> str:
        name = str(getattr(factor_returns, "name", "")).lower()
        for key, etf in self.mapping.items():
            if key in name: return etf
        if isinstance(factor_returns, pd.DataFrame):
            correlations = factor_returns.corr(numeric_only=True).abs().mean().sort_values(ascending=False)
            return str(correlations.index[0]) if len(correlations) else "equal-weight"
        return "equal-weight"

    def __init__(self, aum_history: Optional[Dict[str, pd.Series]] = None) -> None:
        self._aum_history = {str(key).upper(): pd.Series(value, dtype=float).sort_index() for key, value in (aum_history or {}).items()}

    def register_aum_history(self, etf_ticker: str, series: pd.Series) -> None:
        cleaned = pd.Series(series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna().sort_index()
        if cleaned.empty:
            raise ValueError("AUM history must contain at least one finite observation")
        self._aum_history[str(etf_ticker).upper()] = cleaned

    def get_aum_growth_percentile(self, etf_ticker: str) -> float:
        history = self.get_historical_crowding_timeseries(etf_ticker)
        if history.empty: return float("nan")
        current = float(history.iloc[-1]); return float((history <= current).mean() * 100.0)

    def get_traffic_light(self, percentile: float) -> str:
        if not np.isfinite(percentile): return "unknown"
        return "red" if percentile > 80 else ("amber" if percentile >= 50 else "green")

    def get_historical_crowding_timeseries(self, etf_ticker: str) -> pd.Series:
        return self._aum_history.get(str(etf_ticker).upper(), pd.Series(dtype=float, name=etf_ticker))

    def compute_crowding_percentile(self, factor_returns: Any, factor_exposures: Any = None) -> CrowdingResult:
        etf = self.map_factor_to_etf(factor_returns)
        if factor_exposures is not None:
            exposures = pd.Series(factor_exposures, dtype=float).replace([np.inf, -np.inf], np.nan).dropna().abs()
            if not exposures.empty and exposures.sum() > 0:
                weights = exposures / exposures.sum(); concentration = float((weights ** 2).sum() * 100.0)
                history = pd.Series([concentration], name=etf)
                return CrowdingResult(etf, 100.0, "red" if concentration >= 10.0 else "amber" if concentration >= 5.0 else "green", history, "Cross-sectional concentration snapshot; not a forward-return validation")
        percentile = self.get_aum_growth_percentile(etf)
        return CrowdingResult(etf, percentile, self.get_traffic_light(percentile), self.get_historical_crowding_timeseries(etf))


class HalfLifeDecayTracker:
    def scan_ewma_half_life(self, values: Any, max_lag: int = 60) -> dict:
        """Find the EWMA lag most correlated with a finite return series."""
        clean = pd.to_numeric(pd.Series(values), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
        if len(clean) < 2: return {"lag": np.nan, "correlation": np.nan}
        limit = max(1, min(int(max_lag), len(clean) - 1))
        if _HAS_NUMBA:
            lag, correlation = _ewma_corr_scan_numba(clean, limit)
        else:
            scores = []
            for candidate in range(1, limit + 1):
                ewma = pd.Series(clean).ewm(halflife=candidate, adjust=False).mean(); scores.append(float(pd.Series(clean).corr(ewma)))
            lag = int(np.nanargmax(scores) + 1); correlation = float(scores[lag - 1])
        return {"lag": int(lag), "correlation": float(correlation)}

    def compute_half_life_for_window(self, scores: pd.DataFrame, forward_returns: pd.DataFrame, horizons: Sequence[int]) -> float:
        result = IcDecayCurve().compute_decay_curve(scores, forward_returns, horizons); return float(result.half_life)

    def fit_linear_regression(self, half_lives: Sequence[float], vintages: Sequence[Any]) -> dict:
        y = pd.Series(half_lives, dtype=float); x = pd.to_datetime(pd.Series(vintages), errors="coerce").map(lambda value: value.year if pd.notna(value) else np.nan).astype(float); valid = x.notna() & y.notna() & np.isfinite(y); 
        if valid.sum() < 2: return {"slope": 0.0, "intercept": float(y[valid].mean()) if valid.any() else np.nan, "p_value": np.nan}
        slope, intercept = np.polyfit(x[valid], y[valid], 1); residuals = y[valid] - (slope * x[valid] + intercept); se = np.sqrt(np.sum(residuals ** 2) / max(1, valid.sum() - 2)) / max(np.sqrt(np.sum((x[valid] - x[valid].mean()) ** 2)), 1e-12); t = slope / max(se, 1e-12)
        try:
            from scipy.stats import t as student_t
            p = float(2 * student_t.sf(abs(t), max(1, valid.sum() - 2)))
        except Exception: p = np.nan
        return {"slope": float(slope), "intercept": float(intercept), "p_value": p}

    def get_degradation_verdict(self, slope: float, p_value: float) -> str:
        if slope >= 0 or not np.isfinite(p_value) or p_value >= 0.10: return "green"
        return "red" if slope < -5 and p_value < 0.05 else "amber"

    def compute_half_life_over_vintage(self, expression: Any, start: Any, end: Any) -> DecayResult:
        if not isinstance(expression, dict): return DecayResult(pd.DataFrame(), 0.0, np.nan, "insufficient data")
        scores, forward = expression.get("scores", pd.DataFrame()), expression.get("forward_returns", pd.DataFrame())
        if scores.empty or forward.empty: return DecayResult(pd.DataFrame(), 0.0, np.nan, "insufficient data")
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end); rows = []; cursor = start_ts + pd.DateOffset(years=2)
        while cursor <= end_ts:
            window_start = cursor - pd.DateOffset(years=2); mask = (scores.index >= window_start) & (scores.index <= cursor); half = self.compute_half_life_for_window(scores.loc[mask], forward.loc[mask], (1, 5, 10, 21, 42, 63)); rows.append({"vintage": cursor, "half_life": half}); cursor += pd.DateOffset(months=6)
        frame = pd.DataFrame(rows); regression = self.fit_linear_regression(frame.get("half_life", []), frame.get("vintage", [])); return DecayResult(frame, regression["slope"], regression["p_value"], self.get_degradation_verdict(regression["slope"], regression["p_value"]))


class OrthogonalizationPanel:
    def _gram_schmidt_step(self, residual: Any, basis_factor: Any) -> Any:
        y, x = pd.Series(residual, dtype=float), pd.Series(basis_factor, dtype=float); frame = pd.concat([y.rename("y"), x.rename("x")], axis=1).replace([np.inf, -np.inf], np.nan).dropna();
        if frame.empty or frame["x"].var() == 0: return y
        beta = frame["y"].cov(frame["x"]) / frame["x"].var(); return y - beta * x

    def orthogonalize(self, factor_scores: Any, baseline_factors: Any) -> OrthogonalizationResult:
        residual = factor_scores.copy() if hasattr(factor_scores, "copy") else pd.Series(factor_scores, dtype=float)
        original = pd.Series(residual.to_numpy().ravel() if isinstance(residual, pd.DataFrame) else residual).astype(float)
        factors = baseline_factors.items() if isinstance(baseline_factors, dict) else enumerate(baseline_factors)
        for _, basis in factors:
            if isinstance(residual, pd.DataFrame) and isinstance(basis, pd.DataFrame):
                for column in residual.columns.intersection(basis.columns): residual[column] = self._gram_schmidt_step(residual[column], basis[column])
            else: residual = self._gram_schmidt_step(residual, basis)
        residual_values = pd.Series(residual.to_numpy().ravel() if isinstance(residual, pd.DataFrame) else residual).dropna()
        raw = InstantIcDiagnostics().compute_icir(original.dropna()); orth = InstantIcDiagnostics().compute_icir(residual_values); novelty = self.compute_novelty_fraction(raw, orth); warning = "fully redundant" if np.nanvar(np.asarray(residual_values)) < 1e-16 else ""; return OrthogonalizationResult(residual, raw, orth, novelty, 1 - novelty, warning)

    def compute_novelty_fraction(self, original_icir: float, orth_icir: float) -> float:
        if not np.isfinite(original_icir) or abs(original_icir) < 1e-12: return 0.0
        return float(np.clip(abs(orth_icir) / abs(original_icir), 0.0, 1.0))


class InteractionScreener:
    def cross_sectional_zscore(self, interaction: Any) -> Any:
        frame = pd.DataFrame(interaction); return frame.sub(frame.mean(axis=1), axis=0).div(frame.std(axis=1).replace(0, np.nan), axis=0) if isinstance(interaction, pd.DataFrame) else (pd.Series(interaction) - pd.Series(interaction).mean()) / pd.Series(interaction).std()

    def compute_interaction(self, factor_a: Any, factor_b: Any, forward_returns: Any = None) -> InteractionResult:
        a, b = pd.DataFrame(factor_a), pd.DataFrame(factor_b); interaction = self.cross_sectional_zscore(a * b); identical = a.equals(b)
        target = pd.DataFrame(forward_returns) if forward_returns is not None else b
        ic_values = InstantIcDiagnostics().compute_naive_ic(interaction, target)
        parent_a = InstantIcDiagnostics().compute_naive_ic(a, target); parent_b = InstantIcDiagnostics().compute_naive_ic(b, target)
        return InteractionResult(interaction, float(ic_values.mean()) if len(ic_values) else np.nan, InstantIcDiagnostics().compute_icir(ic_values), float(parent_a.mean()) if len(parent_a) else np.nan, float(parent_b.mean()) if len(parent_b) else np.nan, identical)
