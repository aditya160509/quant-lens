"""Screener V2 formula computations."""
from __future__ import annotations

import ast
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .common import number_like
from .data_loader import (
    AS_OF,
    as_of_context,
    close_matrix,
    load_factor_returns,
    ohlcv_for_symbols,
)
from .stats import _pick, _safe_div, rank_pct, zscore

RETURN_HORIZON_FIELDS = {
    "return_1d": 1,
    "r_1d": 1,
    "return_1w": 5,
    "r_5d": 5,
    "return_1m": 21,
    "r_21d": 21,
    "return_3m": 63,
    "r_63d": 63,
    "return_6m": 126,
    "r_126d": 126,
    "return_12m": 252,
    "r_252d": 252,
    "r_jt": 252,
    "momentum_jt": 252,
}


PIT_FUNDAMENTAL_FORMULA_FIELDS = {"roa", "roe", "current_ratio", "debt_equity", "gross_margin", "operating_margin", "mcap"}


HISTORICAL = {"lag", "change", "rolling_rank", "rolling_mean", "rolling_std", "rolling_max", "rolling_min"}
FUNCTIONS = ["rank", "zscore", "abs", "log", "sqrt", "min", "max", "if", "sector_rank", "sector_zscore", *sorted(HISTORICAL)]


class FormulaError(ValueError):
    pass


@dataclass
class FormulaResult:
    values: pd.Series
    diagnostics: list[dict[str, Any]]


class FormulaEngine:
    def __init__(self, panel: pd.DataFrame):
        self.panel = panel
        self.names = {self._sanitize(c): c for c in panel.columns}
        self.diagnostics: list[dict[str, Any]] = []

    @staticmethod
    def _sanitize(name: str) -> str:
        return re.sub(r"[^0-9a-zA-Z_]", "_", str(name)).lower()

    def eval(self, expression: str) -> FormulaResult:
        expr = (expression or "core_quant_score").replace("^", "**")
        expr = re.sub(r"\bif\s*\(", "where(", expr)
        if len(expr) > 4000:
            raise FormulaError("Formula exceeds 4000 characters")
        try:
            tree = ast.parse(expr, mode="eval")
            if sum(1 for _ in ast.walk(tree)) > 256:
                raise FormulaError("Formula exceeds 256 syntax nodes")
            values = self._node(tree.body)
        except (SyntaxError, TypeError, ValueError, KeyError, IndexError, ZeroDivisionError, OverflowError) as exc:
            raise FormulaError(str(exc)) from exc
        if not isinstance(values, pd.Series):
            values = pd.Series(float(values), index=self.panel.index)
        values = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
        return FormulaResult(values=values, diagnostics=self.diagnostics)

    def _node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float, bool)):
                raise FormulaError("Only numeric constants are supported")
            return float(node.value)
        if isinstance(node, ast.Name):
            key = self._sanitize(node.id)
            if key not in self.names:
                raise FormulaError(f"Unknown field '{node.id}'")
            return pd.to_numeric(self.panel[self.names[key]], errors="coerce")
        if isinstance(node, ast.UnaryOp):
            val = self._node(node.operand)
            if isinstance(node.op, ast.USub):
                return -val
            if isinstance(node.op, ast.UAdd):
                return val
        if isinstance(node, ast.BinOp):
            left, right = self._node(node.left), self._node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                denominator = right.replace(0, np.nan) if isinstance(right, pd.Series) else right
                if not isinstance(denominator, pd.Series) and denominator == 0:
                    raise FormulaError("Division by zero")
                return left / denominator
            if isinstance(node.op, ast.Pow):
                if self._as_series(right).abs().gt(16).any():
                    raise FormulaError("Power exponents must be between -16 and 16")
                return left ** right
        if isinstance(node, ast.Compare):
            left = self._node(node.left)
            result = pd.Series(True, index=self.panel.index)
            known = pd.Series(True, index=self.panel.index)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._node(comparator)
                known &= self._as_series(left).notna() & self._as_series(right).notna()
                if isinstance(op, ast.Gt):
                    result &= left > right
                elif isinstance(op, ast.GtE):
                    result &= left >= right
                elif isinstance(op, ast.Lt):
                    result &= left < right
                elif isinstance(op, ast.LtE):
                    result &= left <= right
                elif isinstance(op, ast.Eq):
                    result &= left == right
                elif isinstance(op, ast.NotEq):
                    result &= left != right
                else:
                    raise FormulaError("Unsupported comparator")
                left = right
            return result.astype(float).where(known)
        if isinstance(node, ast.BoolOp):
            parts = [self._as_series(self._node(v)) for v in node.values]
            known = pd.concat([p.notna() for p in parts], axis=1).all(axis=1)
            vals = [p.fillna(0).astype(bool) for p in parts]
            result = vals[0]
            for val in vals[1:]:
                result = result & val if isinstance(node.op, ast.And) else result | val
            return result.astype(float).where(known)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id.lower()
            if name in HISTORICAL:
                field_name = node.args[0].id if node.args and isinstance(node.args[0], ast.Name) else None
                if field_name is None:
                    raise FormulaError(f"{name}() requires a field name as its first argument")
                if len(node.args) > 1 and not isinstance(node.args[1], ast.Constant):
                    raise FormulaError(f"{name}() period must be a numeric constant")
                if field_name and self._sanitize(field_name) not in self.names:
                    tickers = list(self.panel["ticker"]) if "ticker" in self.panel.columns else []
                    matrix = self._field_time_matrix(field_name, tickers, int(number_like(node.args[1].value) or 1) if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else 1)
                    current = matrix.iloc[-1].reindex(tickers).reset_index(drop=True).set_axis(self.panel.index) if matrix is not None and not matrix.empty else pd.Series(0.0, index=self.panel.index)
                    args = [current] + [self._node(a) for a in node.args[1:]]
                else:
                    args = [self._node(a) for a in node.args]
                return self._time_series_call(name, field_name, args)
            args = [self._node(a) for a in node.args]
            return self._call(name, args)
        raise FormulaError(f"Unsupported expression node {type(node).__name__}")

    def _call(self, name: str, args: list[Any]) -> Any:
        if name == "rank":
            return rank_pct(self._as_series(args[0])) / 100
        if name == "zscore":
            return zscore(args[0])
        if name == "abs":
            return args[0].abs() if isinstance(args[0], pd.Series) else abs(args[0])
        if name == "log":
            if isinstance(args[0], pd.Series):
                return np.log(args[0].where(args[0] > 0))
            value = number_like(args[0])
            if value is None or value <= 0:
                raise FormulaError("log() requires a positive numeric value")
            return math.log(value)
        if name == "sqrt":
            return np.sqrt(args[0])
        if name == "min":
            return pd.concat([self._as_series(a) for a in args], axis=1).min(axis=1, skipna=False)
        if name == "max":
            return pd.concat([self._as_series(a) for a in args], axis=1).max(axis=1, skipna=False)
        if name == "where":
            if len(args) != 3:
                raise FormulaError("where(condition, true_value, false_value) requires three arguments")
            condition = self._as_series(args[0])
            return pd.Series(np.where(condition.fillna(False).astype(bool), self._as_series(args[1]), self._as_series(args[2])), index=self.panel.index).where(condition.notna())
        if name == "sector_rank":
            series = self._as_series(args[0])
            return series.groupby(self.panel["sector"]).transform(lambda values: rank_pct(values) / 100)
        if name == "sector_zscore":
            series = self._as_series(args[0])
            return series.groupby(self.panel["sector"]).transform(lambda s: zscore(s))
        raise FormulaError(f"Unsupported function '{name}'")

    def _as_series(self, value: Any) -> pd.Series:
        if isinstance(value, pd.Series):
            return value.reindex(self.panel.index)
        return pd.Series(value, index=self.panel.index)

    def _field_time_matrix(self, field_key: str | None, tickers: list[str], periods: int) -> pd.DataFrame | None:
        if not field_key:
            return None
        lookback = max(periods * 3, 60)
        key = self._sanitize(field_key)
        if key in {"price", "close"}:
            return close_matrix(tickers, lookback_days=lookback)
        if key in {"open", "high", "low", "volume"}:
            raw = ohlcv_for_symbols(tickers)
            return raw.pivot_table(index="Date", columns="Ticker", values=key.title(), aggfunc="last").sort_index().tail(lookback)
        if key in {"mkt_rf", "smb", "hml", "rmw", "cma", "mom", "rf"}:
            factors = load_factor_returns()
            if key not in factors:
                return None
            factors = factors.set_index("date").sort_index()
            if AS_OF.get() is not None:
                factors = factors.loc[factors.index <= AS_OF.get()]
            series = factors[key].tail(lookback)
            return pd.DataFrame({ticker: series for ticker in tickers})
        horizon = RETURN_HORIZON_FIELDS.get(key)
        if horizon:
            prices = close_matrix(tickers, lookback_days=lookback + horizon + 5)
            if prices.empty:
                return prices
            if key in {"r_jt", "momentum_jt"}:
                return prices.shift(21) / prices.shift(252) - 1.0
            return prices.pct_change(periods=horizon, fill_method=None)
        return None

    def _fundamental_field_series(self, field_key: str, ticker: str) -> pd.Series:
        from .fundamentals import statement_snapshots
        hist = statement_snapshots([ticker])
        if hist.empty or "reportDate" not in hist.columns:
            return pd.Series(dtype=float)
        hist = hist.sort_values("reportDate").drop_duplicates("reportDate", keep="last")
        mapping: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
            "roa": lambda h: _safe_div(_pick(h, ["Net Income", "netIncomeToCommon"]), _pick(h, ["Total Assets", "totalAssets"])),
            "roe": lambda h: _safe_div(_pick(h, ["Net Income", "netIncomeToCommon"]), _pick(h, ["Stockholders Equity", "Total Equity", "totalStockholdersEquity"])),
            "current_ratio": lambda h: _safe_div(_pick(h, ["Current Assets", "totalCurrentAssets"]), _pick(h, ["Current Liabilities", "totalCurrentLiabilities"])),
            "debt_equity": lambda h: _safe_div(_pick(h, ["Total Debt", "totalDebt"]), _pick(h, ["Stockholders Equity", "Total Equity", "totalStockholdersEquity"])),
            "gross_margin": lambda h: _safe_div(_pick(h, ["Gross Profit", "grossProfit"]), _pick(h, ["Total Revenue", "totalRevenue", "revenue"])),
            "operating_margin": lambda h: _safe_div(_pick(h, ["EBIT", "Operating Income", "operatingIncome"]), _pick(h, ["Total Revenue", "totalRevenue", "revenue"])),
            "mcap": lambda h: pd.to_numeric(_pick(h, ["marketCap", "market_cap", "Market Cap"]), errors="coerce"),
        }
        fn = mapping.get(field_key)
        if fn is None:
            return pd.Series(dtype=float)
        series = pd.to_numeric(fn(hist), errors="coerce")
        available = pd.to_datetime(hist.reportDate) + pd.Timedelta(days=90)
        reports = pd.DataFrame({"available": available, "value": series}).sort_values("available").drop_duplicates("available", keep="last")
        prices = close_matrix([ticker], 2520)
        if prices.empty:
            return pd.Series(dtype=float)
        reports["available"] = reports.available.astype("datetime64[ns]")
        daily = pd.DataFrame({"date": prices.index.astype("datetime64[ns]")})
        merged = pd.merge_asof(daily, reports, left_on="date", right_on="available", direction="backward", tolerance=pd.Timedelta(days=550))
        if field_key == "mcap":
            shares = pd.to_numeric(_pick(hist, ["Ordinary Shares Number"]), errors="coerce")
            reports["value"] = shares.to_numpy()
            merged = pd.merge_asof(daily, reports, left_on="date", right_on="available", direction="backward", tolerance=pd.Timedelta(days=550))
            from .currency import instrument_specs, usd_price_matrix
            spec = instrument_specs([ticker])[ticker]
            units = spec.get('quoted_units_per_ordinary_share')
            usd = usd_price_matrix(prices, {ticker: spec})
            merged['value'] *= usd[ticker].to_numpy() * (units if units is not None else np.nan)
        return pd.Series(merged.value.to_numpy(), index=prices.index)

    def _time_series_call(self, name: str, field_name: str | None, args: list[Any]) -> pd.Series:
        requested = number_like(args[1]) if len(args) > 1 else 1
        if requested is None or requested < 1 or requested != int(requested):
            raise FormulaError("Historical period must be a positive integer")
        periods = int(requested)
        tickers = list(self.panel["ticker"]) if "ticker" in self.panel.columns else []
        key = self._sanitize(field_name or "")
        if key in PIT_FUNDAMENTAL_FORMULA_FIELDS:
            values: dict[str, float] = {}
            for ticker in tickers:
                series = self._fundamental_field_series(key, ticker)
                if series.empty:
                    values[ticker] = np.nan
                    continue
                values[ticker] = _history_value(series, name, periods)
            self.diagnostics.append({"level": "ok", "message": f"{name}() evaluated on true PIT fundamental history for '{field_name}' using trading sessions and a conservative 90-day availability lag."})
            return pd.Series(values).reindex(tickers).reset_index(drop=True).set_axis(self.panel.index)
        matrix = self._field_time_matrix(field_name, tickers, periods)
        if matrix is not None and not matrix.empty:
            if name == "lag":
                values = matrix.shift(periods).iloc[-1]
            elif name == "change":
                values = matrix.iloc[-1] / matrix.shift(periods).iloc[-1] - 1
            elif name == "rolling_rank":
                values = matrix.rolling(periods, min_periods=periods).rank(pct=True).iloc[-1]
            else:
                method = {"rolling_mean": "mean", "rolling_std": "std", "rolling_max": "max", "rolling_min": "min"}[name]
                values = getattr(matrix.rolling(periods, min_periods=periods), method)().iloc[-1]
            self.diagnostics.append({"level": "ok", "message": f"{name}() evaluated on true local time series for {field_name}."})
            return values.reindex(tickers).reset_index(drop=True).set_axis(self.panel.index)
        raise FormulaError(f"{name}() requires a true historical series; '{field_name}' is unsupported")


def _history_value(series: pd.Series, name: str, periods: int) -> float:
    """One name's lag, change, rolling rank or rolling statistic at the latest session; NaN while the window is short."""
    if name in {"lag", "change"}:
        idx = len(series) - 1 - periods
        past = float(series.iloc[idx]) if 0 <= idx < len(series) else np.nan
        return past if name == "lag" else float(series.iloc[-1]) / past - 1
    window = series.tail(max(1, periods))
    if len(window) != periods or window.isna().any():
        return np.nan
    if name == "rolling_rank":
        return float((window <= window.iloc[-1]).mean())
    return float(getattr(window, {"rolling_mean": "mean", "rolling_std": "std", "rolling_max": "max", "rolling_min": "min"}[name])())


def expand_metrics(expression: str) -> str:
    """Named metrics are written into the formula as their own expressions, up to five levels deep."""
    from .state import list_metrics
    metrics = {m["name"]: m["expression"] for m in list_metrics()}
    for _ in range(5):
        hit = [n for n in metrics if re.search(rf"\b{n}\b", expression)]
        if not hit:
            return expression
        for n in hit:
            expression = re.sub(rf"\b{n}\b", f"({metrics[n]})", expression)
    raise FormulaError("Named metrics nest more than five levels or refer to themselves")


def evaluate_formula(panel: pd.DataFrame, expression: str) -> FormulaResult:
    return FormulaEngine(panel).eval(expand_metrics(expression or ""))


def add_metric_columns(panel: pd.DataFrame) -> pd.DataFrame:
    """Every saved metric marked as a column becomes one, so it can be filtered, sorted, ranked and charted like any other."""
    from .state import list_metrics
    shown = [m for m in list_metrics() if m["show"] and m["name"] not in panel.columns]
    for m in shown:
        panel[m["name"]] = evaluate_formula(panel, m["expression"]).values
    panel.attrs["metric_columns"] = [m["name"] for m in shown]
    return panel


def catalogue(panel: pd.DataFrame) -> dict[str, Any]:
    from .state import list_metrics
    return {"fields": sorted(c for c in panel.select_dtypes("number").columns), "functions": FUNCTIONS, "metrics": list_metrics(), "templates": formula_templates()}


def preview(panel: pd.DataFrame, expression: str, sample: int = 300) -> dict[str, Any]:
    """The formula on every name, or on the largest `sample` when it reads price history, with the count stated."""
    sized = panel.sort_values("market_cap", ascending=False).head(sample).reset_index(drop=True) if "market_cap" in panel and HISTORICAL_RE.search(expression) else panel.reset_index(drop=True)
    values = evaluate_formula(sized, expression).values
    known = values.dropna()
    top = sized.assign(value=values).dropna(subset=["value"]).nlargest(5, "value")
    return {"names": len(sized), "of": len(panel), "known": len(known), "min": _num(known.min()), "median": _num(known.median()), "max": _num(known.max()),
            "top": [{"ticker": t, "value": float(v)} for t, v in zip(top["ticker"], top["value"])]}


HISTORICAL_RE = re.compile(rf"\b({'|'.join(sorted(HISTORICAL))})\s*\(")


def _num(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def formula_templates() -> list[dict[str, str]]:
    return [
        {"name": "Value Momentum Quality", "expression": "0.35*rank(earnings_yield)+0.35*rank(momentum_jt)+0.30*rank(roe)"},
        {"name": "Sector Neutral Value", "expression": "sector_rank(earnings_yield)+0.5*sector_rank(fcf_yield)"},
        {"name": "Low Vol Momentum", "expression": "0.55*rank(momentum_jt)+0.45*rank(-realized_vol_63d)"},
        {"name": "Technical Breakout", "expression": "rank(dist_sma_200)+rank(macd_histogram)+rank(bollinger_pct_b)"},
        {"name": "Quality Balance Sheet", "expression": "rank(roe)+rank(gpa)+rank(interest_coverage)-rank(debt_ebitda)"},
        {"name": "Four Profitability and Liquidity Conditions", "expression": "if(roa>0,1,0)+if(ocf_net_income>1,1,0)+if(current_ratio>1,1,0)+if(gross_margin>0,1,0)"},
        {"name": "Altman Z Score", "expression": "1.2*working_capital_assets+1.4*retained_earnings_assets+3.3*ebit_assets+0.6*market_value_liabilities+sales_assets"},
        {"name": "EBIT Yield and Accounting ROIC Blend", "expression": "rank(earnings_yield)+rank(roic)"},
        {"name": "Acquirers Multiple", "expression": "rank(-ev_ebit)"},
        {"name": "Net Payout Yield", "expression": "rank(net_payout_yield)"},
        {"name": "Quality, Leverage and Volatility Blend", "expression": "rank(gpa)+rank(roe)+rank(interest_coverage)-rank(debt_ebitda)-rank(realized_vol_63d)"},
        {"name": "Trending Value", "expression": "rank(earnings_yield)+rank(fcf_yield)+rank(momentum_jt)"},
        {"name": "Low Volatility, Momentum and Payout Blend", "expression": "rank(-realized_vol_63d)+rank(momentum_jt)+rank(net_payout_yield)"},
        {"name": "Book Value, Liquidity and Coverage Blend", "expression": "rank(-pb_ratio)+rank(current_ratio)+rank(interest_coverage)"},
    ]



def historical_ic_comparison(symbols, payload, provider):
    """Cross-sectional Spearman IC over disjoint, matured forward-return intervals."""
    prices = close_matrix(symbols, int(payload.get('lookback_days', 756)) + 252)
    fields = ['formula_score', 'valuation_percentile', 'quality_percentile', 'momentum_percentile', 'low_vol_percentile', 'liquidity_percentile', 'core_quant_score']
    results = []
    for horizon in [1, 5, 21, 63, 126, 252]:
        estimates = {field: [] for field in fields}
        last_label = None
        for index in range(251, len(prices) - horizon - 1, max(21, horizon + 1)):
            date = prices.index[index]
            with as_of_context(date):
                panel = provider.panel_at(date)
                panel['formula_score'] = provider(date).reindex(panel.ticker).to_numpy()
            forward = prices.iloc[index + 1 + horizon] / prices.iloc[index + 1] - 1
            for field in fields:
                frame = pd.DataFrame({'signal': panel.set_index('ticker')[field], 'forward': forward}).replace([np.inf, -np.inf], np.nan).dropna()
                if len(frame) >= 3 and frame.signal.nunique() > 1 and frame.forward.nunique() > 1:
                    estimates[field].append(float(frame.signal.corr(frame.forward, method='spearman')))
                    last_label = prices.index[index + 1 + horizon]
        for field, values in estimates.items():
            deviation = np.std(values, ddof=1) if len(values) > 1 else np.nan
            results.append({'factor': field, 'forward_horizon_sessions': horizon, 'formation_count': len(values),
                            'mean_ic': float(np.mean(values)) if values else None,
                            'ic_ir': float(np.mean(values) / deviation) if np.isfinite(deviation) and deviation > 0 else None,
                            'last_label_end': str(last_label.date()) if values and last_label is not None else None,
                            'method': 'walk-forward Spearman; disjoint forward-label intervals; close t+1 execution'})
    return results
