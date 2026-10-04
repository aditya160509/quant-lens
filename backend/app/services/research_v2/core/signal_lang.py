"""Safe formula language for Research V2 signals.

Formulas are parsed with ``ast`` and walked against a strict whitelist (no eval,
no exec, no attribute access, no subscripts). They compile to vectorised pandas
operations over (month x ticker) frames. Time-series operators work along the
month axis; cross-sectional operators (rank, zscore, ...) work within each month.
Every field is point in time: prices up to the month end, fundamentals only after
the filing lag applied by ``point_in_time_fundamental``.
"""

from __future__ import annotations

import ast
import threading
from functools import lru_cache
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import data_loader as dl

MAX_EXPR_LEN = 2000
MAX_NODES = 250
MAX_WINDOW = 120

# Flow items below mix quarterly and annual rows; keep annual only (shared helper reads this set).
dl.FLOW_FIELDS.update({"Operating Cash Flow", "Free Cash Flow", "Capital Expenditure", "EBITDA", "Research And Development", "Selling General And Administration", "Interest Expense", "Cost Of Revenue", "Cash Dividends Paid", "Pretax Income"})


class SignalError(ValueError):
    def __init__(self, message: str, start: int = 0, end: int | None = None):
        super().__init__(message)
        self.message, self.start, self.end = message, start, start if end is None else end

    def as_dict(self) -> dict[str, Any]:
        return {"message": self.message, "start": self.start, "end": self.end}


class Groups:
    """Static per-ticker labels (sector, industry) used by group operators."""

    def __init__(self, labels: pd.Series):
        self.labels = labels


# ---------------------------------------------------------------------------
# fields

FUNDAMENTAL_FIELDS: dict[str, tuple[str, str]] = {
    "assets": ("Total Assets", "Total assets"),
    "equity": ("Stockholders Equity", "Book value of equity"),
    "debt": ("Total Debt", "Total debt"),
    "liabilities": ("Total Liabilities Net Minority Interest", "Total liabilities"),
    "revenue": ("Total Revenue", "Annual revenue"),
    "gross_profit": ("Gross Profit", "Annual gross profit"),
    "cost_of_revenue": ("Cost Of Revenue", "Annual cost of revenue"),
    "operating_income": ("Operating Income", "Annual operating income"),
    "ebitda": ("EBITDA", "Annual EBITDA"),
    "pretax_income": ("Pretax Income", "Annual pretax income"),
    "net_income": ("Net Income Common Stockholders", "Annual net income to common"),
    "op_cash_flow": ("Operating Cash Flow", "Annual operating cash flow"),
    "free_cash_flow": ("Free Cash Flow", "Annual free cash flow"),
    "capex": ("Capital Expenditure", "Annual capital expenditure (negative = spend)"),
    "dividends_paid": ("Cash Dividends Paid", "Annual cash dividends paid (negative = paid)"),
    "rd_expense": ("Research And Development", "Annual R&D expense"),
    "sga": ("Selling General And Administration", "Annual SG&A expense"),
    "interest_expense": ("Interest Expense", "Annual interest expense"),
    "shares": ("Ordinary Shares Number", "Shares outstanding"),
    "cash": ("Cash And Cash Equivalents", "Cash and equivalents"),
    "receivables": ("Receivables", "Receivables"),
    "inventory": ("Inventory", "Inventory"),
    "current_assets": ("Current Assets", "Current assets"),
    "current_liabilities": ("Current Liabilities", "Current liabilities"),
    "retained_earnings": ("Retained Earnings", "Retained earnings"),
    "ppe": ("Net PPE", "Net property, plant and equipment"),
    "tangible_book": ("Tangible Book Value", "Tangible book value"),
}
PRICE_FIELDS = {
    "close": "Month-end close",
    "open": "First open of the month",
    "high": "Highest daily high in the month",
    "low": "Lowest daily low in the month",
    "volume": "Shares traded in the month",
    "returns": "Monthly return",
    "dollar_volume": "Dollar volume traded in the month",
    "mcap": "Month-end market cap (price x point-in-time shares)",
}
DERIVED_FIELDS = {
    "rvol": "Monthly standard deviation of daily returns",
    "maxret": "Largest daily return in the month",
    "amihud_d": "Monthly mean of |daily return| / dollar volume (x1e6)",
    "ivol": "Idiosyncratic volatility vs Fama-French factors (rolling 36m)",
    "beta": "Market beta (rolling 36m)",
    "sector": "Sector label (group key for neutralize / group_rank)",
    "industry": "Industry label (group key for neutralize / group_rank)",
}
DERIVED_FIELDS_SET = set(DERIVED_FIELDS)


def field_names() -> list[str]:
    return [*PRICE_FIELDS, *DERIVED_FIELDS, *FUNDAMENTAL_FIELDS]


def _frame(ctx: dict[str, Any], daily_key: str, how: str) -> pd.DataFrame:
    d = ctx["daily"][daily_key]
    r = d.resample("ME")
    out = getattr(r, how)()
    return out.reindex(index=ctx["dates"], columns=ctx["symbols"])


def load_field(name: str, ctx: dict[str, Any], cache: dict[str, Any]):
    if name in cache:
        return cache[name]
    dates, symbols = ctx["dates"], ctx["symbols"]
    if name == "close":
        v = ctx["close_m"]
    elif name == "returns":
        v = ctx["returns"]
    elif name == "mcap":
        v = ctx["market_cap"]
    elif name == "open":
        v = _frame(ctx, "Open", "first")
    elif name == "high":
        v = _frame(ctx, "High", "max")
    elif name == "low":
        v = _frame(ctx, "Low", "min")
    elif name == "volume":
        v = _frame(ctx, "Volume", "sum")
    elif name == "dollar_volume":
        d = (ctx["daily"]["Close"] * ctx["daily"]["Volume"]).resample("ME").sum(min_count=1)
        v = d.reindex(index=dates, columns=symbols)
    elif name in {"rvol", "maxret"}:
        dr = ctx["daily"]["Close"].pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
        dr = dr.where(dr.abs() < 1)
        r = dr.resample("ME")
        v = (r.std() if name == "rvol" else r.max()).reindex(index=dates, columns=symbols)
    elif name == "amihud_d":
        dr = ctx["daily"]["Close"].pct_change(fill_method=None).abs()
        dv = (ctx["daily"]["Close"] * ctx["daily"]["Volume"]).where(lambda x: x > 0)
        v = ((dr / dv) * 1e6).replace([np.inf, -np.inf], np.nan).resample("ME").mean().reindex(index=dates, columns=symbols)
    elif name in {"ivol", "beta"}:
        from .panel import compute_control

        v = compute_control(name, ctx)
    elif name in {"sector", "industry"}:
        if name == "sector":
            lab = dl.static_sectors()
        else:
            df = dl._fundamentals_cols(["ticker", "industry", "reportDate"])
            lab = df.dropna(subset=["industry"]).sort_values("reportDate").groupby("ticker")["industry"].last() if "industry" in df.columns and not df.empty else pd.Series(dtype=object)
        v = Groups(lab.reindex(symbols))
    elif name in FUNDAMENTAL_FIELDS:
        v = dl.point_in_time_fundamental(FUNDAMENTAL_FIELDS[name][0], dates, symbols).reindex(index=dates, columns=symbols)
    else:
        raise KeyError(name)
    if isinstance(v, pd.DataFrame):
        v = v.reindex(index=dates, columns=symbols).replace([np.inf, -np.inf], np.nan)
    cache[name] = v
    return v


@lru_cache(maxsize=1)
def field_coverage() -> dict[str, float]:
    out = {k: 1.0 for k in [*PRICE_FIELDS, "rvol", "maxret", "amihud_d", "ivol", "beta"]}
    cols = [c for c, _ in FUNDAMENTAL_FIELDS.values()]
    df = dl._fundamentals_cols(["ticker", "sector", "industry", *cols])
    n = max(df["ticker"].nunique(), 1) if not df.empty else 1
    for k, (c, _) in FUNDAMENTAL_FIELDS.items():
        out[k] = round(float(df.loc[df[c].notna(), "ticker"].nunique() / n), 3) if c in df.columns else 0.0
    for k in ["sector", "industry"]:
        out[k] = round(float(df.loc[df[k].notna(), "ticker"].nunique() / n), 3) if k in df.columns else 0.0
    return out


# ---------------------------------------------------------------------------
# operators (frames are month x ticker)


def _is_frame(x: Any) -> bool:
    return isinstance(x, pd.DataFrame)


def _need(x: Any, op: str) -> pd.DataFrame:
    if not _is_frame(x):
        raise SignalError(f"{op}: expected a signal/field, got a number or group")
    return x


def _like(v: Any, ref: pd.DataFrame) -> pd.DataFrame:
    return v if _is_frame(v) else pd.DataFrame(float(v), index=ref.index, columns=ref.columns)


def _clean(x: pd.DataFrame) -> pd.DataFrame:
    return x.replace([np.inf, -np.inf], np.nan)


def _win(w: Any, op: str) -> int:
    if isinstance(w, bool) or not isinstance(w, (int, float)) or int(w) != w:
        raise SignalError(f"{op}: window must be an integer constant")
    w = int(w)
    if w < 1:
        raise SignalError(f"{op}: window must be >= 1 (negative windows reference forward data)")
    if w > MAX_WINDOW:
        raise SignalError(f"{op}: window {w} exceeds the maximum of {MAX_WINDOW} months")
    return w


def _ts_rank(x, w):
    def last_rank(a):
        v = a[-1]
        return np.nan if np.isnan(v) else float((a <= v).sum()) / len(a)

    return _need(x, "ts_rank").rolling(w, min_periods=w).apply(last_rank, raw=True)


def _row_q(x, q):
    return _need(x, "quantile").quantile(q, axis=1)


def _bcast(s: pd.Series, x: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(np.repeat(s.to_numpy()[:, None], x.shape[1], axis=1), index=x.index, columns=x.columns)


def _winsorize(x, p=0.01):
    x = _need(x, "winsorize")
    if not isinstance(p, (int, float)) or not 0 <= p < 0.5:
        raise SignalError("winsorize: p must be a constant in [0, 0.5)")
    return x.clip(lower=_bcast(x.quantile(p, axis=1), x), upper=_bcast(x.quantile(1 - p, axis=1), x), axis=None)


def _zscore(x):
    x = _need(x, "zscore")
    return _clean(x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1).replace(0, np.nan), axis=0))


def _grp(g, op):
    if not isinstance(g, Groups):
        raise SignalError(f"{op}: second argument must be a group field such as sector or industry")
    return g.labels


def _neutralize(x, g):
    x = _need(x, "neutralize")
    lab = _grp(g, "neutralize")
    out = x.copy()
    for _, cols in lab.dropna().groupby(lab.dropna()).groups.items():
        cols = [c for c in cols if c in x.columns]
        if cols:
            out[cols] = x[cols].sub(x[cols].mean(axis=1), axis=0)
    out.loc[:, ~x.columns.isin(lab.dropna().index)] = np.nan
    return out


def _group_rank(x, g):
    x = _need(x, "group_rank")
    lab = _grp(g, "group_rank")
    out = pd.DataFrame(np.nan, index=x.index, columns=x.columns)
    for _, cols in lab.dropna().groupby(lab.dropna()).groups.items():
        cols = [c for c in cols if c in x.columns]
        if cols:
            out[cols] = x[cols].rank(axis=1, pct=True)
    return out


def _if_else(c, a, b):
    c = _need(c, "if_else")
    a, b = _like(a, c), _like(b, c)
    return pd.DataFrame(np.where(c.to_numpy() > 0, a.to_numpy(), b.to_numpy()), index=c.index, columns=c.columns).where(c.notna())


def _nanop(fn):
    def run(a, b):
        ref = a if _is_frame(a) else _need(b, "min/max")
        a, b = _like(a, ref), _like(b, ref)
        return fn(a, b)

    return run


def _log(x):
    x = _need(x, "log")
    return np.log(x.where(x > 0))


def _sqrt(x):
    x = _need(x, "sqrt")
    return np.sqrt(x.where(x >= 0))


def _ts(op, fn):
    return lambda x, w: fn(_need(x, op).rolling(_win(w, op), min_periods=_win(w, op)))


def _delay(x, n):
    n = _win(n, "delay") if n != 0 else 0
    return _need(x, "delay").shift(n)


def _delta(x, n):
    return _need(x, "delta") - _delay(x, n)


def _ts_return(x, n):
    x = _need(x, "ts_return")
    return _clean(x / _delay(x, _win(n, "ts_return")) - 1)


def _ts_corr(x, y, w):
    w = _win(w, "ts_corr")
    return _clean(_need(x, "ts_corr").rolling(w, min_periods=w).corr(_need(y, "ts_corr")))


# name -> (callable, arg names, doc, example, category)
OPERATORS: dict[str, tuple[Callable, list[str], str, str, str]] = {
    "ts_mean": (_ts("ts_mean", lambda r: r.mean()), ["x", "window"], "Trailing mean over `window` months", "ts_mean(returns, 12)", "time-series"),
    "ts_std": (_ts("ts_std", lambda r: r.std()), ["x", "window"], "Trailing standard deviation", "ts_std(returns, 12)", "time-series"),
    "ts_sum": (_ts("ts_sum", lambda r: r.sum()), ["x", "window"], "Trailing sum", "ts_sum(returns, 6)", "time-series"),
    "ts_min": (_ts("ts_min", lambda r: r.min()), ["x", "window"], "Trailing minimum", "ts_min(close, 12)", "time-series"),
    "ts_max": (_ts("ts_max", lambda r: r.max()), ["x", "window"], "Trailing maximum", "ts_max(close, 12)", "time-series"),
    "ts_rank": (lambda x, w: _ts_rank(x, _win(w, "ts_rank")), ["x", "window"], "Percentile of today's value within the trailing window", "ts_rank(close, 12)", "time-series"),
    "delay": (_delay, ["x", "n"], "Value n months ago (n >= 0; negative n is rejected as look-ahead)", "delay(close, 1)", "time-series"),
    "delta": (_delta, ["x", "n"], "x minus its value n months ago", "delta(assets, 12)", "time-series"),
    "ts_return": (_ts_return, ["x", "n"], "x / x(n months ago) - 1", "ts_return(close, 12)", "time-series"),
    "ts_corr": (_ts_corr, ["x", "y", "window"], "Trailing correlation of x and y", "ts_corr(returns, volume, 12)", "time-series"),
    "rank": (lambda x: _need(x, "rank").rank(axis=1, pct=True), ["x"], "Cross-sectional percentile rank within each month", "rank(mcap)", "cross-section"),
    "zscore": (_zscore, ["x"], "Cross-sectional z-score within each month", "zscore(equity / mcap)", "cross-section"),
    "winsorize": (_winsorize, ["x", "p"], "Clip each month's cross-section at the p and 1-p quantiles (default p=0.01)", "winsorize(returns, 0.02)", "cross-section"),
    "demean": (lambda x: _need(x, "demean").sub(x.mean(axis=1), axis=0), ["x"], "Subtract the monthly cross-sectional mean", "demean(returns)", "cross-section"),
    "neutralize": (_neutralize, ["x", "group"], "Demean x within each group (e.g. sector) every month", "neutralize(equity / mcap, sector)", "cross-section"),
    "group_rank": (_group_rank, ["x", "group"], "Percentile rank within each group every month", "group_rank(returns, sector)", "cross-section"),
    "q20": (lambda x: _bcast(_row_q(x, 0.2), x), ["x"], "Monthly 20th percentile of x (broadcast)", "x < q20(x)", "cross-section"),
    "q80": (lambda x: _bcast(_row_q(x, 0.8), x), ["x"], "Monthly 80th percentile of x (broadcast)", "x > q80(x)", "cross-section"),
    "abs": (lambda x: _need(x, "abs").abs(), ["x"], "Absolute value", "abs(returns)", "math"),
    "log": (_log, ["x"], "Natural log (non-positive values become missing)", "log(mcap)", "math"),
    "sign": (lambda x: np.sign(_need(x, "sign")), ["x"], "Sign: -1, 0 or 1", "sign(returns)", "math"),
    "sqrt": (_sqrt, ["x"], "Square root (negative values become missing)", "sqrt(volume)", "math"),
    "if_else": (_if_else, ["cond", "a", "b"], "a where cond is true, else b", "if_else(returns > 0, 1, -1)", "logic"),
    "min": (_nanop(lambda a, b: a.where(a <= b, b).where(a.notna() & b.notna())), ["a", "b"], "Elementwise minimum", "min(returns, 0)", "math"),
    "max": (_nanop(lambda a, b: a.where(a >= b, b).where(a.notna() & b.notna())), ["a", "b"], "Elementwise maximum", "max(returns, 0)", "math"),
}
ARITY = {k: (len(v[1]) - (1 if k == "winsorize" else 0), len(v[1])) for k, v in OPERATORS.items()}

_BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a**b}
_CMPOPS = {ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b, ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b, ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}


# ---------------------------------------------------------------------------
# parsing and evaluation


def parse(expr: str) -> ast.Expression:
    """Parse and statically validate a formula. Raises SignalError with a character span."""

    if not isinstance(expr, str) or not expr.strip():
        raise SignalError("Formula is empty")
    if len(expr) > MAX_EXPR_LEN:
        raise SignalError(f"Formula is longer than {MAX_EXPR_LEN} characters", 0, len(expr))
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        off = max((e.offset or 1) - 1, 0)
        raise SignalError(f"Syntax error: {e.msg}", off, off + 1) from None
    lead = len(expr) - len(expr.lstrip())
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise SignalError("Formula is too complex", 0, len(expr))
    names = set(field_names())
    for n in nodes:
        span = (getattr(n, "col_offset", 0) + lead, getattr(n, "end_col_offset", 0) + lead)
        if isinstance(n, (ast.Expression, ast.Load, ast.operator, ast.unaryop, ast.cmpop)):
            if isinstance(n, ast.operator) and type(n) not in _BINOPS and not isinstance(n, (ast.BitAnd, ast.BitOr)):
                raise SignalError(f"Operator {type(n).__name__} is not allowed", *span)
            continue
        if isinstance(n, ast.Constant):
            if isinstance(n.value, bool) or not isinstance(n.value, (int, float)):
                raise SignalError("Only numeric constants are allowed", *span)
        elif isinstance(n, ast.Name):
            if n.id not in names and n.id not in OPERATORS:
                raise SignalError(f"Unknown name '{n.id}'", *span)
        elif isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name):
                raise SignalError("Only calls to named operators are allowed", *span)
            if n.func.id not in OPERATORS:
                raise SignalError(f"Unknown operator '{n.func.id}'", *span)
            if n.keywords:
                raise SignalError("Keyword arguments are not supported", *span)
            lo, hi = ARITY[n.func.id]
            if not lo <= len(n.args) <= hi:
                raise SignalError(f"{n.func.id} takes {lo if lo == hi else f'{lo}-{hi}'} arguments, got {len(n.args)}", *span)
        elif isinstance(n, ast.BinOp):
            if type(n.op) not in _BINOPS and not isinstance(n.op, (ast.BitAnd, ast.BitOr)):
                raise SignalError("Operator not allowed", *span)
        elif isinstance(n, ast.UnaryOp):
            if not isinstance(n.op, (ast.USub, ast.UAdd)):
                raise SignalError("Only unary + and - are allowed", *span)
        elif isinstance(n, ast.Compare):
            if len(n.ops) != 1 or type(n.ops[0]) not in _CMPOPS:
                raise SignalError("Use a single comparison (>, >=, <, <=, ==, !=)", *span)
        else:
            raise SignalError(f"'{type(n).__name__}' is not allowed in formulas (no attribute access, subscripts, lambdas or strings)", *span)
    # bare operator names (not called) are not values
    called = {id(n.func) for n in nodes if isinstance(n, ast.Call)}
    for n in nodes:
        if isinstance(n, ast.Name) and n.id in OPERATORS and n.id not in names and id(n) not in called:
            raise SignalError(f"'{n.id}' is an operator; call it like {n.id}(...)", n.col_offset + lead, n.end_col_offset + lead)
    return tree


def references_forward(tree: ast.Expression) -> str | None:
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"delay", "delta", "ts_return"} and len(n.args) >= 2:
            a = n.args[1]
            if isinstance(a, ast.UnaryOp) and isinstance(a.op, ast.USub):
                return f"{n.func.id} with a negative lag reads future data"
    return None


class _Eval:
    def __init__(self, ctx: dict[str, Any], cache: dict[str, Any]):
        self.ctx, self.cache = ctx, cache

    def go(self, n: ast.AST) -> Any:
        try:
            return self._go(n)
        except SignalError as e:
            if e.start == 0 and e.end == 0 and hasattr(n, "col_offset"):
                e.start, e.end = n.col_offset, n.end_col_offset
            raise

    def _go(self, n: ast.AST) -> Any:
        if isinstance(n, ast.Expression):
            return self.go(n.body)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            return load_field(n.id, self.ctx, self.cache)
        if isinstance(n, ast.UnaryOp):
            v = self.go(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            a, b = self.go(n.left), self.go(n.right)
            if isinstance(n.op, ast.BitAnd):
                a, b = _need(a, "&"), _like(b, a)
                return ((a > 0) & (b > 0)).astype(float).where(a.notna() & b.notna())
            if isinstance(n.op, ast.BitOr):
                a, b = _need(a, "|"), _like(b, a)
                return ((a > 0) | (b > 0)).astype(float).where(a.notna() & b.notna())
            for v in (a, b):
                if isinstance(v, Groups):
                    raise SignalError("Group fields can only be used inside neutralize / group_rank", n.col_offset, n.end_col_offset)
            r = _BINOPS[type(n.op)](a, b)
            return _clean(r) if _is_frame(r) else r
        if isinstance(n, ast.Compare):
            a, b = self.go(n.left), self.go(n.comparators[0])
            ref = a if _is_frame(a) else _need(b, "comparison")
            a, b = _like(a, ref), _like(b, ref)
            return _CMPOPS[type(n.ops[0])](a, b).astype(float).where(a.notna() & b.notna())
        if isinstance(n, ast.Call):
            fn = OPERATORS[n.func.id][0]
            args = [self.go(a) for a in n.args]
            r = fn(*args)
            return _clean(r) if _is_frame(r) else r
        raise SignalError("Unsupported expression", getattr(n, "col_offset", 0), getattr(n, "end_col_offset", 0))


def evaluate(expr: str, ctx: dict[str, Any], cache: dict[str, Any] | None = None) -> pd.DataFrame:
    tree = parse(expr)
    msg = references_forward(tree)
    if msg:
        raise SignalError(msg, 0, len(expr))
    out = _Eval(ctx, {} if cache is None else cache).go(tree)
    if not _is_frame(out):
        raise SignalError("Formula must produce a signal (month x ticker), not a constant", 0, len(expr))
    return out.reindex(index=ctx["dates"], columns=ctx["symbols"])


# ---------------------------------------------------------------------------
# look-ahead guard, orthogonalisation, combination

_GUARD = threading.local()


def rank_ic(sig: pd.DataFrame, ret_next: pd.DataFrame) -> pd.Series:
    return sig.rank(axis=1).corrwith(ret_next.rank(axis=1), axis=1)


def lookahead_check(expr: str | None, sig: pd.DataFrame, returns: pd.DataFrame, tree: ast.Expression | None = None) -> dict[str, Any]:
    """Flag formulas that read forward data or correlate implausibly with the *next* month's return."""

    if expr:
        msg = references_forward(tree or parse(expr))
        if msg:
            return {"flagged": True, "reason": msg}
    fwd = rank_ic(sig, returns.shift(-1)).dropna()
    same = rank_ic(sig, returns).dropna()
    info = {"mean_corr_future_month": round(float(fwd.mean()), 4) if len(fwd) else None, "mean_corr_same_month": round(float(same.mean()), 4) if len(same) else None}
    if len(fwd) >= 12 and abs(fwd.mean()) > 0.25:
        return {"flagged": True, "reason": f"Signal has a mean cross-sectional rank correlation of {fwd.mean():.2f} with next month's return; real anomalies sit near 0.01 to 0.05. Check for look-ahead.", **info}
    return {"flagged": False, **info}


def set_lookahead(v: dict[str, Any] | None) -> None:
    _GUARD.value = v


def get_lookahead() -> dict[str, Any]:
    return getattr(_GUARD, "value", None) or {"flagged": False}


def orthogonalize(sig: pd.DataFrame, others: list[pd.DataFrame]) -> pd.DataFrame:
    """Per-month cross-sectional OLS residual of ``sig`` on ``others`` (with intercept)."""

    out = pd.DataFrame(np.nan, index=sig.index, columns=sig.columns)
    arrs = [o.reindex_like(sig).to_numpy(float) for o in others]
    s = sig.to_numpy(float)
    for i in range(s.shape[0]):
        cols = [a[i] for a in arrs]
        ok = np.isfinite(s[i])
        for c in cols:
            ok &= np.isfinite(c)
        if ok.sum() < len(cols) + 5:
            continue
        X = np.column_stack([np.ones(ok.sum()), *[c[ok] for c in cols]])
        beta, *_ = np.linalg.lstsq(X, s[i][ok], rcond=None)
        res = np.full(s.shape[1], np.nan)
        res[ok] = s[i][ok] - X @ beta
        out.iloc[i] = res
    return out


def combine_expr(exprs: list[str], method: str, weights: list[float] | None = None) -> str:
    if not exprs:
        raise SignalError("Provide at least one formula")
    for e in exprs:
        parse(e)
    base = "rank" if method == "rank_average" else "zscore"
    w = weights or [1.0 / len(exprs)] * len(exprs)
    terms = [f"{wi:.4f} * {base}({e})" for wi, e in zip(w, exprs)]
    return " + ".join(terms)
