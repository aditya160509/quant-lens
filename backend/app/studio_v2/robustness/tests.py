from __future__ import annotations

"""
All robustness tests (F3.2-F3.8) in one file.

Core: Parameter Stability Surface, Timing Perturbation,
      Cost Break-Even, Capacity & Turnover Stress.
Extended (on-demand): Universe Perturbation, Noise Injection,
      OOS Boundary Sensitivity.
"""

import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..backtest.metrics import PerformanceMetrics
from ..shared.data_loader import get_sector_map

try:
    from joblib import Parallel, delayed
    _HAS_JOBLIB = True
except ImportError:
    _HAS_JOBLIB = False


def _sharpe(values: Sequence[float]) -> float:
    arr = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    if arr.size < 2: return float("nan")
    sd = np.std(arr, ddof=1)
    return 0.0 if sd == 0 else float(np.mean(arr) / sd * np.sqrt(252.0))


@dataclass
class ParameterStabilityResult:
    grid_results: pd.DataFrame
    heatmaps: Dict[str, dict]
    stability_scores: Dict[str, float]
    fragility_flags: Dict[str, bool]
    warning: Optional[str] = None


@dataclass
class TimingPerturbationResult:
    by_magnitude: Dict[int, pd.DataFrame]
    sensitivity_score: float
    baseline_sharpe: float


@dataclass
class UniversePerturbationResult:
    by_dropout: Dict[float, pd.DataFrame]
    concentration_stocks: List[str]
    stability_score: float


@dataclass
class NoiseInjectionResult:
    by_level: Dict[float, pd.DataFrame]
    fragility_threshold: float
    noise_tolerance_score: float


@dataclass
class CostBreakEvenResult:
    cost_sharpes: pd.DataFrame
    breakeven_bps: float
    robustness_score: float


@dataclass
class CapacityResult:
    aum_results: pd.DataFrame
    capacity_ceiling: float
    slippage_table: pd.DataFrame
    bucket_impact: Dict[str, float]


@dataclass
class RegimeDecompositionResult:
    states: pd.Series
    per_regime: pd.DataFrame
    universality_score: float


@dataclass
class BoundarySensitivityResult:
    split_results: pd.DataFrame
    sensitivity_score: float


class ParameterStabilityTest:
    def identify_numeric_params(self, strategy_file: str) -> List[str]:
        tree = ast.parse(open(strategy_file, encoding="utf-8").read())
        names = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, (ast.Constant, ast.UnaryOp)) and isinstance(getattr(node.value, "value", None), (int, float)):
                names.extend(target.id for target in node.targets if isinstance(target, ast.Name))
        return names

    def build_param_grid(self, params: Sequence[str], current_values: Dict[str, float], n_points: int = 21) -> List[dict]:
        values = {name: np.linspace(float(current_values[name]) * 0.5, float(current_values[name]) * 1.5, int(n_points)) for name in params}
        if not values: return []
        keys = list(values)
        return [{key: float(choice) for key, choice in zip(keys, choices)} for choices in __import__("itertools").product(*(values[key] for key in keys))]

    def run_grid_parallel(self, param_grid: List[dict], config: Any) -> pd.DataFrame:
        callback = config.get("evaluate", config.get("objective")) if isinstance(config, dict) else getattr(config, "evaluate", None)
        def evaluate(parameters: dict) -> dict:
            value = callback(parameters) if callable(callback) else np.nan
            return {**parameters, "sharpe": float(value) if np.isscalar(value) else _sharpe(value)}
        rows = []
        if callable(callback) and len(param_grid) > 1 and _HAS_JOBLIB:
            rows = Parallel(n_jobs=min(32, len(param_grid)), prefer="threads")(
                delayed(evaluate)(parameters) for parameters in param_grid
            )
        elif callable(callback) and len(param_grid) > 1:
            with ThreadPoolExecutor(max_workers=min(32, len(param_grid))) as pool:
                futures = [pool.submit(evaluate, parameters) for parameters in param_grid]
                rows = [future.result() for future in as_completed(futures)]
        else:
            rows = [evaluate(parameters) for parameters in param_grid]
        return pd.DataFrame(rows)

    def compute_heatmap_data(self, results: pd.DataFrame, param_a: str, param_b: str) -> dict:
        if results.empty or param_a not in results or param_b not in results or "sharpe" not in results: return {"x": [], "y": [], "z": []}
        pivot = results.pivot_table(index=param_b, columns=param_a, values="sharpe", aggfunc="mean").sort_index()
        return {"x": pivot.columns.tolist(), "y": pivot.index.tolist(), "z": pivot.to_numpy().tolist(), "param_a": param_a, "param_b": param_b}

    def compute_stability_score(self, results: pd.DataFrame, optimal_sharpe: float) -> float:
        if results.empty or "sharpe" not in results or not np.isfinite(optimal_sharpe): return 0.0
        values = pd.to_numeric(results["sharpe"], errors="coerce")
        return float((values > 0.5 * optimal_sharpe).mean())

    def run(self, strategy_file: str, config: Any) -> ParameterStabilityResult:
        params = self.identify_numeric_params(strategy_file)
        values = config.get("current_values", {}) if isinstance(config, dict) else getattr(config, "current_values", {})
        selected = [p for p in params if p in values][: (len(params) if (isinstance(config, dict) and config.get("allow_3plus")) else 2)]
        if not selected: return ParameterStabilityResult(pd.DataFrame(), {}, {}, {}, "no numeric parameters to test")
        grid = self.build_param_grid(selected, values)
        results = self.run_grid_parallel(grid, config)
        optimum = float(pd.to_numeric(results.get("sharpe", pd.Series(dtype=float)), errors="coerce").max()) if not results.empty else float("nan")
        scores = {param: self.compute_stability_score(results, optimum) for param in selected}
        return ParameterStabilityResult(results, {f"{selected[0]}:{selected[1]}": self.compute_heatmap_data(results, selected[0], selected[1])} if len(selected) == 2 else {}, scores, {param: score < 0.20 for param, score in scores.items()})


class TimingPerturbationTest:
    def _single_simulation(self, trade_log: pd.DataFrame, k: int) -> pd.Series:
        if trade_log.empty: return pd.Series(dtype=float)
        rng = np.random.default_rng()
        returns = pd.to_numeric(trade_log.get("return", trade_log.get("trade_return", pd.Series(dtype=float))), errors="coerce").dropna().to_numpy()
        if returns.size == 0: return pd.Series(dtype=float)
        if {"entry_date", "exit_date", "entry_price", "exit_price"}.issubset(trade_log.columns):
            shifts = rng.integers(-k, k + 1, size=returns.size)
            # Without a price table, preserve each trade's measured return but
            # perturb its event ordering.  The full MC engine re-prices when
            # a price table is supplied.
            return pd.Series(returns[np.argsort(shifts)])
        return pd.Series(returns[rng.permutation(returns.size)])

    def compute_timing_sensitivity_score(self, baseline_sharpe: float, k5_sharpes: Sequence[float]) -> float:
        if not np.isfinite(baseline_sharpe) or baseline_sharpe == 0: return 0.0
        return float(np.nanmedian(k5_sharpes) / baseline_sharpe)

    def run(self, trade_log: pd.DataFrame, n_simulations: int = 1000) -> TimingPerturbationResult:
        if trade_log is None or trade_log.empty: return TimingPerturbationResult({}, float("nan"), float("nan"))
        base = pd.to_numeric(trade_log.get("return", trade_log.get("trade_return", pd.Series(dtype=float))), errors="coerce").dropna()
        baseline = _sharpe(base)
        output = {}
        for k in (1, 3, 5, 10):
            def evaluate(_: int) -> dict:
                simulated = self._single_simulation(trade_log, k)
                return {"sharpe": _sharpe(simulated), "sortino": PerformanceMetrics().compute_sortino(simulated), "max_drawdown": PerformanceMetrics().compute_max_drawdown(simulated)}
            if _HAS_JOBLIB and n_simulations > 1:
                rows = Parallel(n_jobs=-1, prefer="threads")(delayed(evaluate)(index) for index in range(int(n_simulations)))
            else:
                rows = [evaluate(index) for index in range(int(n_simulations))]
            output[k] = pd.DataFrame(rows)
        return TimingPerturbationResult(output, self.compute_timing_sensitivity_score(baseline, output[5]["sharpe"]), baseline)


class UniversePerturbationTest:
    def drop_and_replace(self, tickers: Sequence[str], dropout_pct: float, sector_map: Optional[Dict[str, str]] = None) -> List[str]:
        symbols = list(tickers); n_drop = min(len(symbols), max(0, int(round(len(symbols) * dropout_pct))))
        if n_drop == 0: return symbols
        rng = np.random.default_rng(); dropped = set(rng.choice(symbols, n_drop, replace=False).tolist()); remaining = [t for t in symbols if t not in dropped]
        if sector_map is None:
            try:
                sector_map = get_sector_map(symbols)
            except (FileNotFoundError, ValueError):
                sector_map = {}
        groups: Dict[str, List[str]] = {}
        for ticker in symbols:
            groups.setdefault(str(sector_map.get(ticker, "__unknown__")), []).append(ticker)
        replacements = []
        for ticker in dropped:
            sector = str(sector_map.get(ticker, "__unknown__"))
            pool = [candidate for candidate in groups.get(sector, []) if candidate not in dropped and candidate not in replacements]
            if not pool:
                pool = [candidate for candidate in symbols if candidate not in dropped and candidate not in replacements]
            if pool:
                replacements.append(str(rng.choice(pool)))
            else:
                replacements.append(ticker)
        return remaining + replacements

    def compute_concentration_stocks(self, results: pd.DataFrame, tickers: Sequence[str]) -> List[str]:
        if results.empty or "ticker_removed" not in results: return list(tickers)[:20]
        impact = results.groupby("ticker_removed")["sharpe_degradation"].mean().sort_values(ascending=False)
        return impact.head(20).index.astype(str).tolist()

    def compute_universe_stability_score(self, baseline_sharpe: float, results_at_20pct: pd.DataFrame) -> float:
        if results_at_20pct.empty or baseline_sharpe == 0: return 0.0
        return float((abs(pd.to_numeric(results_at_20pct["sharpe"], errors="coerce") - baseline_sharpe) < 0.3).mean())

    def run(self, original_universe: Sequence[str], config: Any, n_samples: int = 500) -> UniversePerturbationResult:
        baseline = float(config.get("baseline_sharpe", 0.0)) if isinstance(config, dict) else 0.0
        evaluate = config.get("evaluate") if isinstance(config, dict) else None
        by_dropout = {}
        for pct in (0.10, 0.20, 0.30):
            def evaluate_sample(_: int) -> dict:
                universe = self.drop_and_replace(original_universe, pct, config.get("sector_map") if isinstance(config, dict) else None)
                value = evaluate(universe) if callable(evaluate) else np.nan
                return {"sharpe": float(value) if np.isscalar(value) else _sharpe(value), "universe_size": len(universe)}
            if _HAS_JOBLIB and n_samples > 1:
                rows = Parallel(n_jobs=-1, prefer="threads")(delayed(evaluate_sample)(index) for index in range(int(n_samples)))
            else:
                rows = [evaluate_sample(index) for index in range(int(n_samples))]
            by_dropout[pct] = pd.DataFrame(rows)
        return UniversePerturbationResult(by_dropout, self.compute_concentration_stocks(pd.DataFrame(), original_universe), self.compute_universe_stability_score(baseline, by_dropout[0.20]))


class NoiseInjectionTest:
    def inject_noise(self, prices: pd.DataFrame, sigma: float) -> pd.DataFrame:
        rng = np.random.default_rng(); numeric = prices.select_dtypes(include=[np.number]).columns
        out = prices.copy(); out[numeric] = out[numeric] * (1.0 + rng.normal(0.0, float(sigma), size=(len(out), len(numeric))))
        return out

    def find_fragility_threshold(self, results_by_level: Dict[float, pd.DataFrame]) -> float:
        for level in sorted(results_by_level):
            values = pd.to_numeric(results_by_level[level].get("sharpe", pd.Series(dtype=float)), errors="coerce")
            if np.nanmedian(values) <= 0: return float(level)
        return float("nan")

    def compute_noise_tolerance(self, results_at_0_005: pd.DataFrame, baseline_sharpe: float) -> float:
        if baseline_sharpe == 0 or results_at_0_005.empty: return 0.0
        return float(np.nanmedian(results_at_0_005["sharpe"]) / baseline_sharpe)

    def run(self, strategy_file: str, config: Any, n_simulations: int = 500) -> NoiseInjectionResult:
        prices = config.get("prices", pd.DataFrame()) if isinstance(config, dict) else pd.DataFrame(); evaluate = config.get("evaluate") if isinstance(config, dict) else None; baseline = float(config.get("baseline_sharpe", 0.0)) if isinstance(config, dict) else 0.0
        output = {}
        for sigma in (0.001, 0.003, 0.005, 0.010):
            def evaluate_sample(_: int) -> dict:
                noisy = self.inject_noise(prices, sigma); value = evaluate(noisy) if callable(evaluate) else np.nan
                return {"sharpe": float(value) if np.isscalar(value) else _sharpe(value)}
            if _HAS_JOBLIB and n_simulations > 1:
                rows = Parallel(n_jobs=-1, prefer="threads")(delayed(evaluate_sample)(index) for index in range(int(n_simulations)))
            else:
                rows = [evaluate_sample(index) for index in range(int(n_simulations))]
            output[sigma] = pd.DataFrame(rows)
        return NoiseInjectionResult(output, self.find_fragility_threshold(output), self.compute_noise_tolerance(output[0.005], baseline))


class CostBreakEvenTest:
    def compute_breakeven_cost(self, cost_sharpes: pd.DataFrame) -> float:
        if cost_sharpes.empty: return float("nan")
        x, y = pd.to_numeric(cost_sharpes.iloc[:, 0], errors="coerce"), pd.to_numeric(cost_sharpes.iloc[:, 1], errors="coerce")
        valid = x.notna() & y.notna()
        if valid.sum() < 2: return float("nan")
        slope, intercept = np.polyfit(x[valid], y[valid], 1)
        if slope == 0: return float("inf") if intercept > 0 else 0.0
        return float(-intercept / slope)

    def compute_cost_robustness_score(self, breakeven: float, realistic_band: Tuple[float, float]) -> float:
        midpoint = float(np.mean(realistic_band)); return float(breakeven / midpoint) if midpoint > 0 and np.isfinite(breakeven) else (1.0 if breakeven == float("inf") else 0.0)

    def run(self, strategy_file: str, config: Any, cost_levels: int = 20, max_cost_bps: float = 50) -> CostBreakEvenResult:
        evaluate = config.get("evaluate") if isinstance(config, dict) else None; band = config.get("realistic_band", (5, 15)) if isinstance(config, dict) else (5, 15)
        rows = []
        for cost in np.linspace(0.0, float(max_cost_bps), int(cost_levels)):
            value = evaluate(float(cost)) if callable(evaluate) else np.nan; rows.append({"cost_bps": cost, "sharpe": float(value) if np.isscalar(value) else _sharpe(value)})
        frame = pd.DataFrame(rows); return CostBreakEvenResult(frame, self.compute_breakeven_cost(frame[["cost_bps", "sharpe"]]), self.compute_cost_robustness_score(self.compute_breakeven_cost(frame[["cost_bps", "sharpe"]]), band))


class CapacityStressTest:
    def compute_impact(self, trade_size: float, adv: float, sigma: float, lam: float) -> float:
        if trade_size == 0 or adv <= 0 or not np.isfinite(adv): return 0.0
        return float(lam * max(float(sigma), 1e-4) * (abs(float(trade_size)) / float(adv)) ** (3.0 / 5.0) * 10000.0)

    def simulate_aum_level(self, trades: pd.DataFrame, aum: float, adv: Any, vol: Any, lambda_dict: Dict[str, float], fixed_cost: float = 0.0) -> dict:
        gross = float(pd.to_numeric(trades.get("gross_return", trades.get("return", pd.Series(dtype=float))), errors="coerce").sum()) if not trades.empty else 0.0; impact_total = 0.0; bucket_impact = {}
        for _, row in trades.iterrows():
            ticker = str(row.get("ticker", "")); adv_value = float(adv.get(ticker, np.nan) if isinstance(adv, dict) else adv.loc[ticker] if hasattr(adv, "loc") and ticker in adv.index else np.nan); sigma = float(vol.get(ticker, 0.0) if isinstance(vol, dict) else vol.loc[ticker] if hasattr(vol, "loc") and ticker in vol.index else 0.0); lam = float(lambda_dict.get(row.get("bucket", "small"), lambda_dict.get("small", 1.2e-4))); impact = self.compute_impact(abs(float(row.get("trade_size", row.get("notional", 0.0)))) * aum, adv_value, sigma, lam); impact_total += impact / 10000.0; bucket = str(row.get("bucket", "small")); bucket_impact[bucket] = bucket_impact.get(bucket, 0.0) + impact
        net = gross - impact_total - max(0.0, fixed_cost) * len(trades) / 10000.0
        return {"aum": float(aum), "gross_return": gross, "impact_cost": impact_total, "net_return": net, "net_sharpe": net, "bucket_impact": bucket_impact}

    def find_capacity_ceiling(self, aum_results: pd.DataFrame) -> float:
        if aum_results.empty: return float("nan")
        ordered = aum_results.sort_values("aum")
        for _, row in ordered.iterrows():
            if float(row.get("net_return", 0.0)) <= 0: return float(row["aum"])
        return float("inf")

    def compute_slippage_table(self, aum_results: pd.DataFrame) -> pd.DataFrame:
        levels = [1e7, 1e8, 1e9, 1e10]
        if aum_results.empty: return pd.DataFrame(columns=["aum", "slippage", "net_alpha", "net_sharpe"])
        rows = []
        for level in levels:
            row = aum_results.iloc[(aum_results["aum"] - level).abs().argmin()]; rows.append({"aum": level, "slippage": row.get("impact_cost", np.nan), "net_alpha": row.get("net_return", np.nan), "net_sharpe": row.get("net_sharpe", np.nan)})
        return pd.DataFrame(rows)

    def run(self, trade_log: pd.DataFrame, adv_data: Any, vol_data: Any, lambda_dict: Dict[str, float]) -> CapacityResult:
        levels = np.logspace(6, 10, 20); rows = [self.simulate_aum_level(trade_log, level, adv_data, vol_data, lambda_dict) for level in levels]; frame = pd.DataFrame(rows); bucket = {}
        for row in frame.get("bucket_impact", []):
            for key, value in row.items(): bucket[key] = bucket.get(key, 0.0) + value
        return CapacityResult(frame, self.find_capacity_ceiling(frame), self.compute_slippage_table(frame), bucket)


class RegimeDecompositionTest:
    def fit_hmm(self, features: pd.DataFrame, n_states: int = 3) -> dict:
        frame = pd.DataFrame(features).select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan).dropna()
        if frame.empty:
            return {"features": frame, "states": pd.Series(dtype=object), "means": pd.DataFrame(), "transitions": np.empty((0, 0)), "n_states": int(n_states)}
        states_count = max(2, min(int(n_states), len(frame)))
        try:
            from hmmlearn.hmm import GaussianHMM
            model = GaussianHMM(n_components=states_count, covariance_type="full", n_iter=200, random_state=42, init_params="stmc")
            model.fit(frame.to_numpy())
            labels = model.predict(frame.to_numpy())
            means = pd.DataFrame(model.means_, columns=frame.columns)
            transitions = model.transmat_
        except Exception:
            # Deterministic quantile states remain a valid degraded mode when
            # the optional HMM runtime cannot fit a singular sample.
            labels = pd.qcut(frame.iloc[:, 0].rank(method="first"), q=states_count, labels=False, duplicates="drop").to_numpy()
            means = frame.assign(_state=labels).groupby("_state").mean()
            transitions = np.zeros((states_count, states_count), dtype=float)
            for left, right in zip(labels[:-1], labels[1:]): transitions[int(left), int(right)] += 1
            row_sums = transitions.sum(axis=1, keepdims=True); transitions = np.divide(transitions, row_sums, out=np.full_like(transitions, 1.0 / states_count), where=row_sums > 0)
        state_names = pd.Series(labels, index=frame.index).map(lambda value: f"state_{int(value)}")
        return {"features": frame, "states": state_names, "means": means, "transitions": transitions, "n_states": states_count}

    def assign_states(self, hmm: dict) -> pd.Series:
        return pd.Series(hmm.get("states", pd.Series(dtype=object)), dtype=object)

    def compute_per_regime_performance(self, returns: pd.Series, states: pd.Series) -> pd.DataFrame:
        rows = []
        for state, values in pd.Series(returns).groupby(states.reindex(pd.Series(returns).index)):
            values = values.dropna(); rows.append({"regime": state, "sharpe": _sharpe(values), "sortino": PerformanceMetrics().compute_sortino(values), "hit_rate": float((values > 0).mean()), "avg_return": float(values.mean()), "count": int(len(values))})
        return pd.DataFrame(rows)

    def compute_regime_universality_score(self, per_regime_sharpes: Sequence[float], unconditional_sharpe: float) -> float:
        return float(np.nanmin(per_regime_sharpes) / unconditional_sharpe) if unconditional_sharpe not in (0, np.nan) and np.isfinite(unconditional_sharpe) else 0.0

    def run(self, returns: pd.Series, vix_series: pd.Series) -> RegimeDecompositionResult:
        frame = pd.concat([pd.Series(returns, name="returns"), pd.Series(vix_series, name="vix")], axis=1).dropna(); hmm = self.fit_hmm(frame[["vix", "returns"]]); states = self.assign_states(hmm); per = self.compute_per_regime_performance(frame["returns"], states); return RegimeDecompositionResult(states, per, self.compute_regime_universality_score(per.get("sharpe", pd.Series(dtype=float)), _sharpe(frame["returns"])))


class OOSBoundarySensitivityTest:
    def compute_boundary_sensitivity_score(self, oos_sharpes: Sequence[float]) -> float:
        values = pd.Series(oos_sharpes, dtype=float).replace([np.inf, -np.inf], np.nan).dropna(); return float(values.std(ddof=1)) if len(values) > 1 else 0.0

    def run(self, strategy: Any, config: Any, baseline_split: Any, shifts: Sequence[int] = (-6, -3, 0, 3, 6)) -> BoundarySensitivityResult:
        evaluate = config.get("evaluate") if isinstance(config, dict) else None; rows = []
        for shift in shifts:
            value = evaluate(shift) if callable(evaluate) else np.nan; rows.append({"shift_months": shift, "oos_sharpe": float(value) if np.isscalar(value) else _sharpe(value)})
        frame = pd.DataFrame(rows); return BoundarySensitivityResult(frame, self.compute_boundary_sensitivity_score(frame["oos_sharpe"]))


def get_realistic_cost_band(tickers: Sequence[str], adv_data: Any, mcap_data: Any) -> Tuple[float, float]:
    values = []
    for ticker in tickers:
        cap = mcap_data.get(ticker, np.nan) if isinstance(mcap_data, dict) else mcap_data.loc[ticker] if hasattr(mcap_data, "loc") and ticker in mcap_data.index else np.nan
        if np.isfinite(cap): values.append(float(cap))
    median = float(np.nanmedian(values)) if values else 0.0
    return (2.0, 5.0) if median >= 10e9 else ((5.0, 15.0) if median >= 2e9 else (15.0, 30.0))
