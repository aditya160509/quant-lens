"""Studio Library: versioned, immutable items (cost presets, universes, benchmarks, regimes, crises, metrics, profiles) in one JSON file."""

from __future__ import annotations

import ast
import datetime as dt
import itertools
import json
import math
import threading
import time
import uuid
from functools import lru_cache
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.services.screener_v2.core.data_loader import BACKEND_DATA, normalize_symbol

from . import backtest, data, formula, limits
from .spec import Costs, Settings, Sizing

LIB_PATH = BACKEND_DATA / "studio_v3" / "library.json"
_LOCK = threading.Lock()
FIRST_BARS = "2015-01-01"  # DECISIONS: no stock bars before 2015


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _date(v: str) -> str:
    try:
        return str(dt.date.fromisoformat(v))
    except (TypeError, ValueError) as e:
        raise ValueError(f"'{v}' is not a date (YYYY-MM-DD)") from e


# --- item bodies ---------------------------------------------------------------


class CostPreset(_M):
    commission_bps: float = Field(0.0, ge=0)
    commission_share: float = Field(0.0, ge=0)
    commission_min: float = Field(0.0, ge=0)
    slippage_bps: float = Field(0.0, ge=0)
    borrow_bps: float = Field(0.0, ge=0)
    effective_from: str = "2015-01-01"
    note: str = ""

    _d = field_validator("effective_from")(lambda v: _date(v))

    def costs(self, profile: str) -> Costs:
        return Costs(profile=profile, **self.model_dump(exclude={"effective_from", "note"}))


class UniverseBody(_M):
    kind: Literal["static", "top_dollar_volume", "screen"]
    symbols: list[str] = Field(default_factory=list, max_length=5000)  # static list, or the candidate pool for the other kinds
    n: int = Field(50, ge=1, le=5000)  # top_dollar_volume: names kept
    lookback: int = Field(60, ge=1, le=1000)  # bars of dollar volume averaged
    rule: str = ""  # screen: formula true for a name on the rebalance bar
    rebalance: Literal["W", "M", "Q"] = "M"
    min_price: float = Field(0.0, ge=0)
    pool: int = Field(300, ge=1, le=5000)  # candidate names by today's liquidity when `symbols` is empty

    @model_validator(mode="after")
    def _check(self):
        self.symbols = [normalize_symbol(s) for s in self.symbols]
        if self.kind == "static" and not self.symbols:
            raise ValueError("A static universe needs symbols")
        if self.kind == "screen":
            formula.parse(self.rule)  # refuses typos and look-ahead
        return self


class BenchmarkBody(_M):
    weights: dict[str, float]

    @model_validator(mode="after")
    def _check(self):
        w = {normalize_symbol(k): float(v) for k, v in self.weights.items()}
        if not w or any(not math.isfinite(v) or v <= 0 for v in w.values()):
            raise ValueError("Weights must be positive numbers")
        total = sum(w.values())
        self.weights = {k: v / total for k, v in w.items()}
        return self


class RegimeBody(_M):
    benchmark: str = "SPY"
    rule: str  # formula on the benchmark's bars, e.g. close > sma(close, 200)

    @model_validator(mode="after")
    def _check(self):
        self.benchmark = normalize_symbol(self.benchmark)
        formula.parse(self.rule)
        return self


class CrisisBody(_M):
    start: str
    end: str

    @model_validator(mode="after")
    def _check(self):
        a, z = _date(self.start), _date(self.end)
        if a < FIRST_BARS:
            raise ValueError(f"No stock bars before 2015, so a window starting {a} cannot be measured (docs/studio/plan/DECISIONS.md: real history is 2015 onward)")
        if z < a:
            raise ValueError("The window ends before it starts")
        return self


# --- safe metric formulas ------------------------------------------------------

METRIC_NAMES = {"cagr": "cagr", "sharpe": "sharpe", "sortino": "sortino", "calmar": "calmar", "max_drawdown": "max_drawdown", "ulcer": "ulcer", "volatility": "annual_vol",
                "win_rate": "win_rate", "trades": "trades", "profit_factor": "profit_factor", "total_return": "total_return", "years": "years", "exposure": "time_in_market",
                "expectancy": "expectancy", "beta": "beta", "alpha": "alpha"}
_FUNCS = {"abs": abs, "min": min, "max": max, "sqrt": math.sqrt, "log": math.log}
_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}
_CMP = {ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b, ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b}


def _metric_tree(expr: str) -> ast.Expression:
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError("The metric formula does not parse") from e
    for n in ast.walk(tree):
        ok = (isinstance(n, (ast.Expression, ast.Load, ast.BinOp, ast.UnaryOp, ast.USub, ast.Compare, ast.IfExp))
              or (isinstance(n, ast.operator) and type(n) in _BIN) or (isinstance(n, ast.cmpop) and type(n) in _CMP)
              or (isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool))
              or (isinstance(n, ast.Name) and (n.id in METRIC_NAMES or n.id in _FUNCS))
              or (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords))
        if not ok:
            raise ValueError(f"'{type(n).__name__}' is not allowed in a metric formula; use numbers, + - * /, comparisons, {', '.join(_FUNCS)} and {', '.join(METRIC_NAMES)}")
    return tree


class MetricBody(_M):
    formula: str

    @field_validator("formula")
    @classmethod
    def _f(cls, v):
        _metric_tree(v)
        return v


def eval_metric(expr: str, metrics: dict[str, Any]) -> float | bool | None:
    """Evaluate a validated metric formula against a backtest's metrics dict; None when a needed metric is missing."""
    env = {k: metrics.get(src) for k, src in METRIC_NAMES.items()}

    def go(n):
        if isinstance(n, ast.Expression):
            return go(n.body)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            v = env[n.id]
            if v is None:
                raise ArithmeticError
            return float(v)
        if isinstance(n, ast.UnaryOp):
            return -go(n.operand)
        if isinstance(n, ast.BinOp):
            return _BIN[type(n.op)](go(n.left), go(n.right))
        if isinstance(n, ast.Compare):
            return _CMP[type(n.ops[0])](go(n.left), go(n.comparators[0]))
        if isinstance(n, ast.IfExp):
            return go(n.body) if go(n.test) else go(n.orelse)
        return _FUNCS[n.func.id](*[go(a) for a in n.args])

    try:
        out = go(_metric_tree(expr))
    except (ArithmeticError, ValueError):  # missing metric, divide by zero, log of a negative
        return None
    return out if isinstance(out, bool) else (float(out) if math.isfinite(out) else None)


class ProfileBody(_M):
    validation: dict[str, Any] = Field(default_factory=dict)
    report_order: list[str] = Field(default_factory=list)
    sizing: Sizing = Field(default_factory=Sizing)


BODIES: dict[str, type[BaseModel]] = {"cost_preset": CostPreset, "universe": UniverseBody, "benchmark": BenchmarkBody, "regime": RegimeBody, "crisis": CrisisBody,
                                      "metric": MetricBody, "profile": ProfileBody}
ItemType = Literal["cost_preset", "universe", "benchmark", "regime", "crisis", "metric", "profile"]

SEED = [("US retail", {"commission_bps": 1.0, "slippage_bps": 2.0, "borrow_bps": 50.0, "note": "Current defaults"}),
        ("IBKR fixed", {"commission_share": 0.005, "commission_min": 1.0, "slippage_bps": 2.0, "borrow_bps": 50.0, "note": "$0.005 a share, $1 minimum; the 1% of trade value cap is not modelled"}),
        ("IBKR tiered", {"commission_share": 0.0035, "commission_min": 0.35, "slippage_bps": 2.0, "borrow_bps": 50.0, "note": "$0.0035 a share, $0.35 minimum; exchange and clearing fees not included"}),
        ("Zero commission + spread", {"slippage_bps": 5.0, "borrow_bps": 50.0, "note": "No commission; the spread is the cost"}),
        ("Custom", {"note": "Set your own"})]


# --- the store -----------------------------------------------------------------


def _load() -> dict:
    try:
        lib = json.loads(LIB_PATH.read_text())
    except (OSError, ValueError):
        lib = {"items": {}}
    if not any(i["type"] == "cost_preset" for i in lib["items"].values()):
        for name, body in SEED:
            iid = "cost-" + name.lower().replace(" + ", "-").replace(" ", "-")
            lib["items"][iid] = {"id": iid, "type": "cost_preset", "name": name, "archived": False, "created": time.time(), "versions": [{"version": 1, "body": CostPreset(**body).model_dump(), "created": time.time()}]}
    return lib


def _save(lib: dict) -> None:
    LIB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LIB_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(lib))
    tmp.replace(LIB_PATH)


def _validate(kind: str, body: dict) -> dict:
    if kind not in BODIES:
        raise ValueError(f"Unknown item type {kind}")
    try:
        return BODIES[kind](**body).model_dump()
    except ValidationError as e:
        raise ValueError("; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())) from e


def _view(item: dict, version: int | None = None) -> dict:
    v = next((x for x in item["versions"] if x["version"] == (version or item["versions"][-1]["version"])), None)
    if v is None:
        raise KeyError(f"{item['id']} has no version {version}")
    return {"id": item["id"], "type": item["type"], "name": item["name"], "archived": item["archived"], "latest": item["versions"][-1]["version"],
            "version": v["version"], "body": v["body"], "created": v["created"]}


def list_items(kind: str | None = None, include_archived: bool = False) -> list[dict]:
    with _LOCK:
        lib = _load()
    return [_view(i) for i in lib["items"].values() if (kind is None or i["type"] == kind) and (include_archived or not i["archived"])]


def get(item_id: str, version: int | None = None) -> dict:
    with _LOCK:
        item = _load()["items"].get(item_id)
    if not item:
        raise KeyError(f"Unknown library item {item_id}")
    return {**_view(item, version), "versions": [{"version": v["version"], "created": v["created"]} for v in item["versions"]]}


def create(kind: str, name: str, body: dict) -> dict:
    body = _validate(kind, body)
    with _LOCK:
        lib = _load()
        iid = f"{kind[:4]}-{uuid.uuid4().hex[:8]}"
        lib["items"][iid] = {"id": iid, "type": kind, "name": name.strip() or "Untitled", "archived": False, "created": time.time(), "versions": [{"version": 1, "body": body, "created": time.time()}]}
        _save(lib)
    return get(iid)


def add_version(item_id: str, body: dict, name: str | None = None) -> dict:
    """A new immutable version; an unchanged body returns the latest instead of adding a copy."""
    with _LOCK:
        lib = _load()
        item = lib["items"].get(item_id)
        if not item:
            raise KeyError(f"Unknown library item {item_id}")
        body = _validate(item["type"], body)
        if body != item["versions"][-1]["body"]:
            item["versions"].append({"version": item["versions"][-1]["version"] + 1, "body": body, "created": time.time()})
        if name and name.strip():
            item["name"] = name.strip()
        _save(lib)
    return get(item_id)


def archive(item_id: str) -> dict:
    """Delete-to-archive: the item and its versions stay, so a run that pinned one still resolves."""
    with _LOCK:
        lib = _load()
        if item_id not in lib["items"]:
            raise KeyError(f"Unknown library item {item_id}")
        lib["items"][item_id]["archived"] = True
        _save(lib)
    return get(item_id)


# --- Y-10 cost comparison --------------------------------------------------------


def _preset_costs(ref: dict) -> Costs:
    it = get(ref["item_id"], ref.get("version"))
    if it["type"] != "cost_preset":
        raise ValueError(f"{ref['item_id']} is not a cost preset")
    return CostPreset(**it["body"]).costs(it["name"])


def compare_costs(spec, settings: Settings, a: dict, b: dict) -> dict:
    """One strategy under two cost presets ({item_id, version?}); deltas are b minus a."""
    rows = {}
    for k, ref in (("a", a), ("b", b)):
        costs = _preset_costs(ref)
        out = backtest.run_backtest(spec, settings.model_copy(update={"costs": costs}))["meta"]
        rows[k] = {"profile": costs.profile, "total_return": out["total_return"], "sharpe": out["metrics"].get("sharpe"), "cost_share": out["costs"]["share_of_gross"], "costs_total": out["costs"]["total"]}
    d = {m: None if rows["a"][m] is None or rows["b"][m] is None else rows["b"][m] - rows["a"][m] for m in ("total_return", "sharpe", "cost_share", "costs_total")}
    return {"a": rows["a"], "b": rows["b"], "delta": d}


# --- Y-5/6/7 universes -----------------------------------------------------------


def _pool(b: UniverseBody) -> list[str]:
    return b.symbols or backtest._universe(Settings(top_n=b.pool))


def membership(b: UniverseBody, start: str | None = None, end: str | None = None) -> tuple[pd.DatetimeIndex, tuple[str, ...], np.ndarray]:
    """(dates, symbols, bool matrix): who is in the universe on each bar. Chosen on a rebalance bar's close, applied from the next bar, so never with later data."""
    p = data.panel(_pool(b), start, end)
    if not len(p.dates):
        return p.dates, p.symbols, np.zeros((0, 0), bool)
    live = np.isfinite(p.close)
    if b.kind == "static":
        return p.dates, p.symbols, live
    chosen = np.zeros(live.shape, bool)
    reb = p.dates.to_series().groupby(p.dates.to_period(b.rebalance if b.rebalance != "W" else "W-FRI")).idxmax()
    idx = np.searchsorted(p.dates, pd.DatetimeIndex(reb.to_numpy()))
    if b.kind == "top_dollar_volume":
        dv = pd.DataFrame(p.close * p.volume).rolling(b.lookback, min_periods=max(1, b.lookback // 2)).mean().to_numpy()
    else:
        bars = {f: getattr(p, f) for f in data.FIELDS} | {"market": np.full(p.close.shape, np.nan)}
        try:
            ok = formula.evaluate(b.rule, bars, p.dates).astype(bool)
        except (KeyError, formula.SignalError) as e:
            raise ValueError(f"The screen rule cannot be evaluated: {e}") from e
    for i in idx:
        eligible = live[i] & (p.close[i] >= b.min_price)
        if b.kind == "top_dollar_volume":
            score = np.where(eligible & np.isfinite(dv[i]), dv[i], -np.inf)
            pick = np.argsort(-score)[: b.n]
            row = np.zeros(live.shape[1], bool)
            row[pick[np.isfinite(score[pick])]] = True
        else:
            row = eligible & ok[i]
        chosen[i + 1 :] = row  # held until the next rebalance overwrites it
    chosen[: idx[0] + 1] = False
    return p.dates, p.symbols, chosen


def universe_preview(b: UniverseBody, start: str | None = None, end: str | None = None) -> dict:
    dates, syms, m = membership(b, start, end)
    if not m.size:
        return {"count": [], "turnover": None, "coverage": None, "members": [], "note": "No bars for this universe in the period."}
    n = m.sum(axis=1)
    step = max(1, len(dates) // 120)
    changes = [(m[i] ^ m[i - 1]).sum() / max(m[i].sum(), m[i - 1].sum(), 1) for i in range(1, len(m)) if (m[i] != m[i - 1]).any()]
    live = np.isfinite(data.panel(list(syms), start, end).close) if b.kind != "static" else m
    cov = float((m & live).sum() / max(m.sum(), 1))
    dead = limits.audit()["ended_early_share"] if b.kind != "static" else None
    note = ("Candidates are today's symbol file: names that were delisted before it was built may be missing, so past winners are over-represented"
            + (f" ({dead:.0%} of the file's names stop trading early)." if dead is not None else ".") if b.kind != "static" else "A fixed list chosen today carries hindsight if it came from today's winners.")
    return {"count": [{"date": str(dates[i].date()), "count": int(n[i])} for i in range(0, len(dates), step)], "turnover": float(np.mean(changes)) if changes else 0.0,
            "coverage": cov, "members": [syms[j] for j in np.flatnonzero(m[-1])][:200], "as_of": str(dates[-1].date()), "point_in_time": b.kind != "static", "note": note}


# --- Y-12 benchmarks, Y-16 regimes -----------------------------------------------


def benchmark_series(weights: dict[str, float], start: str | None = None, end: str | None = None) -> dict:
    w = BenchmarkBody(weights=weights).weights
    p = data.panel(list(w), start, end)
    missing = [s for s in w if s not in p.symbols]
    if missing:
        raise ValueError(f"Not in the data: {', '.join(missing)}")
    close = pd.DataFrame(p.close, index=p.dates, columns=p.symbols)[list(w)].ffill()
    close = close.dropna()
    if len(close) < 2:
        raise ValueError("These symbols share no dates in the period")
    ret = close.pct_change().fillna(0.0) @ pd.Series(w)  # daily rebalanced to the weights
    return {"weights": w, "series": [{"date": str(d.date()), "value": float(v)} for d, v in (100 * (1 + ret).cumprod()).items()]}


def regime_spans(b: RegimeBody, start: str | None = None, end: str | None = None) -> dict:
    p = data.panel([b.benchmark], start, end)
    if not len(p.dates):
        raise ValueError(f"Not in the data: {b.benchmark}")
    bars = {f: getattr(p, f) for f in data.FIELDS} | {"market": p.close}
    try:
        on = formula.evaluate(b.rule, bars, p.dates)[:, 0].astype(bool)
    except (KeyError, formula.SignalError) as e:
        raise ValueError(f"The regime rule cannot be evaluated: {e}") from e
    cut = np.flatnonzero(np.diff(on.astype(np.int8), prepend=-1, append=-1))
    spans = [{"regime": bool(on[a]), "from": str(p.dates[a].date()), "to": str(p.dates[z - 1].date()), "bars": int(z - a)} for a, z in itertools.pairwise(cut)]
    return {"benchmark": b.benchmark, "share_on": float(on.mean()), "spans": spans}


# --- Y-36/Y-18 data -----------------------------------------------------------------


@lru_cache(maxsize=2)
def _per_symbol(version: str) -> list[dict]:
    import polars as pl

    from app.services.screener_v2.core import data_loader

    frame = data_loader.load_market_frame().lazy()
    per = frame.group_by(data_loader.NORMALIZED_TICKER.alias("symbol")).agg(pl.col("Date").min().alias("first"), pl.col("Date").max().alias("last"), pl.len().alias("bars"), ).sort("symbol").collect()
    cal = np.sort(frame.select(pl.col("Date").unique()).collect()["Date"].to_numpy())
    rows = []
    for s, a, z, n in per.iter_rows():
        span = int(np.searchsorted(cal, np.datetime64(z), side="right") - np.searchsorted(cal, np.datetime64(a)))
        rows.append({"symbol": s, "first": str(a.date()), "last": str(z.date()), "bars": n, "gaps": max(span - n, 0)})
    return rows


def catalog(offset: int = 0, limit: int = 100, q: str = "") -> dict:
    rows = _per_symbol(data.data_version())
    if q:
        rows = [r for r in rows if r["symbol"].startswith(q.strip().upper())]
    return {"total": len(rows), "offset": offset, "rows": rows[offset : offset + limit], "adjustment": limits.ADJUSTMENT}


# --- Y-35 profiles ---------------------------------------------------------------------


def export_profile(item_id: str, version: int | None = None) -> dict:
    it = get(item_id, version)
    if it["type"] != "profile":
        raise ValueError(f"{item_id} is not a profile")
    return {"kind": "studio-profile", "format": 1, "name": it["name"], "body": it["body"]}


def import_profile(doc: dict) -> dict:
    if doc.get("kind") != "studio-profile" or doc.get("format") != 1:
        raise ValueError("Not a Studio profile export")
    return create("profile", str(doc.get("name") or "Imported profile"), doc.get("body") or {})
