"""st01 Backtest: one run of the compiled strategy on the development period, and everything the page shows about it."""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from app.services.screener_v2.core import data_loader
from app.services.shared import metrics as M

from . import compile as C
from . import data, engine, formula, limits, paths, pycode
from .spec import Settings, Strategy, engine_params

FEW_TRADES = 30
CRISES = [("Dot-com bust", "2000-03-24", "2002-10-09"), ("Financial crisis", "2007-10-09", "2009-03-09"), ("Euro debt", "2011-04-29", "2011-10-03"),
          ("China and oil", "2015-05-21", "2016-02-11"), ("Q4 2018", "2018-09-20", "2018-12-24"), ("Covid crash", "2020-02-19", "2020-03-23"),
          ("2022 bear", "2022-01-03", "2022-10-12"), ("2025 tariffs", "2025-02-19", "2025-04-08")]


class Refusal(ValueError):
    """A run that must not produce a report (K-7): the reason and the most likely causes."""

    def __init__(self, reason: str, causes: list[str]):
        super().__init__(reason + " Likely causes: " + "; ".join(causes) + ".")
        self.reason, self.causes = reason, causes


@dataclass
class Prepared:
    panel: data.Panel  # development period only
    sig_bars: dict[str, np.ndarray]  # bars with gaps inside a name's life filled, for indicators
    benchmark: np.ndarray | None
    holdout_from: str | None  # first sealed date
    requested: int
    all_dates: pd.DatetimeIndex  # development + hold-out (dates only; hold-out bars never leave this module)


def _universe(settings: Settings) -> list[str]:
    if settings.symbols:
        return [data_loader.normalize_symbol(s) for s in settings.symbols]
    return list(data_loader.parse_symbols({"universe": "master", "primary_only": True, "max_symbols": settings.top_n}, max_symbols=5000))


def _fill_gaps(a: np.ndarray, alive: np.ndarray) -> np.ndarray:
    out = pd.DataFrame(a).ffill().to_numpy(copy=True)
    out[~alive] = np.nan
    return out


def prepare(settings: Settings, *, include_holdout: bool = False) -> Prepared:
    symbols = _universe(settings)
    p = data.panel(symbols, settings.start, settings.end)
    if not len(p.dates) or not p.close.shape[1]:
        raise Refusal("No bars for this universe in the chosen period.", ["the period is outside the data we hold", "the symbols are not in the file", "the universe is empty"])
    ok = np.isfinite(p.close)
    # keep sessions where at least half the live names trade: drops other markets' holidays from a shared calendar
    first, last = np.argmax(ok, axis=0), ok.shape[0] - 1 - np.argmax(ok[::-1], axis=0)
    t = np.arange(ok.shape[0])[:, None]
    alive = (t >= first) & (t <= last) & ok.any(axis=0)
    keep = ok.sum(axis=1) >= np.maximum(1, 0.5 * alive.sum(axis=1))
    p = data.Panel(p.dates[keep], p.symbols, *(getattr(p, f)[keep] for f in data.FIELDS))
    alive, all_dates = alive[keep], p.dates
    cut = len(p.dates) if include_holdout or not settings.holdout else max(int(len(p.dates) * (1 - settings.holdout)), 1)
    holdout_from = str(p.dates[cut].date()) if cut < len(p.dates) else None
    p, alive = p.window(0, cut), alive[:cut]
    sig_bars = {f: _fill_gaps(getattr(p, f), alive) for f in ("open", "high", "low", "close")} | {"volume": np.where(alive, np.nan_to_num(p.volume), np.nan)}
    m = data.panel(["SPY"], None, None)
    mkt = pd.Series(m.close[:, 0], index=m.dates).reindex(p.dates, method="ffill").to_numpy() if len(m.dates) else np.full(len(p.dates), np.nan)
    sig_bars["market"] = np.repeat(mkt[:, None], p.close.shape[1], axis=1)  # SPY close on every column, for market rules
    bench = None
    if settings.benchmark:
        b = data.panel([settings.benchmark], None, None)
        if len(b.dates):
            bench = pd.Series(b.close[:, 0], index=b.dates).reindex(p.dates, method="ffill").to_numpy()
            if not np.isfinite(bench).any():
                bench = None
    return Prepared(p, sig_bars, bench, holdout_from, len(symbols), all_dates)


COST_OVERRIDES = ("commission_bps", "commission_share", "commission_min", "slippage_bps", "slippage_range", "borrow_bps")


def _override_params(values: dict, cost_multiple: float = 1.0) -> dict:
    """Class attributes from the code as engine parameters (B-63); cost values still climb the ladder."""
    out = {k: (v * cost_multiple if k in COST_OVERRIDES else v) for k, v in values.items() if k != "fill"}
    if "fill" in values:
        out["fill"] = float(values["fill"] == "same_close")
    return out


def _effective(spec: Strategy, settings: Settings, cost_multiple: float = 1.0) -> engine.Params:
    """The engine parameters the run actually uses: the card, then the code's class attributes."""
    params = engine_params(spec, settings, cost_multiple)
    overrides = pycode.engine_overrides(spec.code) if spec.code.strip() else {}
    return replace(params, **_override_params(overrides, cost_multiple)) if overrides else params


def _simulate_python(spec, prep, settings, *, cost_multiple=1.0, lo=0, mask=None, params=None, exits_override=None,
                     output=None, repaint_from=None, debug_symbol=None, debug_after=None, debug_event=None, debug_breakpoint=None, debug_loss=None):
    params = {**spec.values(), **(params or {})}
    panel = prep.panel
    symbols = panel.symbols
    dates = panel.dates[lo:]
    bars = {k: v[lo:] for k, v in panel.bars().items()}
    signal_bars = prep.sig_bars
    if mask is not None:
        symbols = tuple(s for s, keep in zip(symbols, mask, strict=True) if keep)
        bars = {k: v[:, mask] for k, v in bars.items()}
        signal_bars = {k: v[:, mask] for k, v in signal_bars.items()}
    cache: dict = {}
    args = (signal_bars, panel.dates, params, cache)
    stop_dist = spec.exits.stop_atr * formula.evaluate("atr(14)", *args) if spec.exits.stop_atr else None
    market_filter = C._bool(spec.market_filter, *args) if spec.market_filter.strip() else None
    size_vol = C._vol(spec, *args)
    overrides = pycode.engine_overrides(spec.code)
    engine_settings = _effective(spec, settings, cost_multiple)
    if overrides and output is not None:
        output["settings_overrides"] = overrides
    if exits_override:
        engine_settings = replace(engine_settings, **exits_override)
    repaint_bars = None
    if repaint_from is not None:
        last = len(dates) - 1
        repaint_bars = np.unique(np.linspace(min(max(repaint_from, 1), last), last, 50).astype(int)).tolist()
    return pycode.run_event(
        spec.code, bars, dates, params, list(symbols), engine_settings, output=output, repaint_bars=repaint_bars,
        signal_bars={k: v[lo:] for k, v in signal_bars.items()},
        stop_dist=None if stop_dist is None else np.nan_to_num(stop_dist[lo:]),
        size_vol=None if size_vol is None else size_vol[lo:],
        market_filter=None if market_filter is None else market_filter[lo:],
        benchmark=None if prep.benchmark is None else prep.benchmark[lo:],
        files=spec.files, debug_symbol=debug_symbol, debug_after=debug_after, debug_event=debug_event, debug_breakpoint=debug_breakpoint, debug_loss=debug_loss,
    )


def simulate(spec: Strategy, prep: Prepared, settings: Settings, *, sig: C.Signals | None = None, cost_multiple: float = 1.0, lo: int = 0,
             mask: np.ndarray | None = None, params: dict[str, float] | None = None, exits_override: dict | None = None) -> engine.Result:
    if spec.code.strip() and sig is None:
        return _simulate_python(spec, prep, settings, cost_multiple=cost_multiple, lo=lo, mask=mask, params=params, exits_override=exits_override)
    sig = sig or C.signals(spec, prep.sig_bars, prep.panel.dates, params)
    traded = np.isfinite(prep.panel.close)
    entries = np.where(traded if mask is None else traded & mask[None, :], sig.entries, 0).astype(np.int8)
    exits = sig.exits
    if spec.defensive.strip() and spec.market_filter.strip():
        # B-122 allocate if/else: while the market rule is false, hold the defensive name; sell it when the rule turns true
        name = spec.defensive.strip().upper()
        if name not in prep.panel.symbols:
            raise Refusal(f"The defensive symbol {name} is not in the universe.", [f"add {name} to the universe", "or clear the defensive symbol to sit in cash"])
        j = prep.panel.symbols.index(name)
        on = C.market_on(spec, prep.sig_bars, prep.panel.dates, params)[:, j]
        entries[:, j] = np.where(on | ~traded[:, j], 0, 1)
        exits = exits.copy()
        exits[:, j] = np.where(on, 1, 0)
    p = _effective(spec, settings, cost_multiple)
    if exits_override:
        p = replace(p, **exits_override)
    if spec.scale_in.strip():
        adds = C.market_on(spec.model_copy(update={"market_filter": spec.scale_in}), prep.sig_bars, prep.panel.dates, params) & traded
        bars = {k: v[lo:] for k, v in prep.panel.bars().items()}
        return engine.run(bars, entries[lo:], exits[lo:], p, score=None if sig.score is None else sig.score[lo:], stop_dist=None if sig.stop_dist is None else sig.stop_dist[lo:],
                          size_vol=None if sig.size_vol is None else sig.size_vol[lo:], strategy=engine.ScaleInStrategy(entries[lo:], exits[lo:], adds[lo:], spec.max_entries))
    if lo:
        bars = {k: v[lo:] for k, v in prep.panel.bars().items()}
        return engine.run(bars, entries[lo:], exits[lo:], p, score=None if sig.score is None else sig.score[lo:], stop_dist=None if sig.stop_dist is None else sig.stop_dist[lo:],
                          size_vol=None if sig.size_vol is None else sig.size_vol[lo:])
    return engine.run(prep.panel.bars(), entries, exits, p, score=sig.score, stop_dist=sig.stop_dist, size_vol=sig.size_vol)


def _cagr(eq: np.ndarray, capital: float) -> float | None:
    if len(eq) < 2 or eq[-1] <= 0:
        return None
    return float((eq[-1] / capital) ** (M.ANN / len(eq)) - 1)


def _clean(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, (np.floating, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


def trades_table(r: engine.Result, p: data.Panel) -> list[dict]:
    t, d = r.trades, [str(x.date()) for x in p.dates]
    cols = engine
    return [{
        "symbol": p.symbols[int(x[cols.T_SYM])], "side": "long" if x[cols.T_DIR] > 0 else "short", "entry_date": d[int(x[cols.T_ENTRY_BAR])], "exit_date": d[int(x[cols.T_EXIT_BAR])],
        "entry": x[cols.T_ENTRY_PX], "exit": x[cols.T_EXIT_PX], "shares": x[cols.T_SHARES], "pnl": x[cols.T_PNL], "return": x[cols.T_RET],
        "bars": int(x[cols.T_EXIT_BAR] - x[cols.T_ENTRY_BAR]), "mae": x[cols.T_MAE], "mfe": x[cols.T_MFE], "exit_reason": engine.REASONS[int(x[cols.T_REASON])],
        "costs": x[cols.T_COSTS], "signal_date": d[int(x[cols.T_SIGNAL_BAR])], "risk": x[cols.T_RISK],
    } for x in t]


def check_limits(spec: Strategy, ret: dict, trade: dict, bench: dict, cost_share: float | None, start_pass: float | None) -> list[dict]:
    """My limits strip: each walk-away condition with pass or fail and the room left."""
    lim, rows = spec.limits, []

    def add(name: str, value: float | None, limit: float | None, lower_is_better: bool, fmt: str):
        if limit is None:
            return
        if value is None:
            rows.append({"limit": name, "value": None, "bound": limit, "pass": None, "room": None, "format": fmt})
            return
        ok = value <= limit if lower_is_better else value >= limit
        room = (limit - value) / limit if lower_is_better and limit else (value - limit) / limit if limit else None
        rows.append({"limit": name, "value": value, "bound": limit, "pass": bool(ok), "room": room, "format": fmt})

    add("Drawdown", abs(ret.get("max_drawdown", 0.0)) if ret else None, lim.max_drawdown, True, "pct")
    add("Drawdown length (months)", ret.get("max_drawdown_bars", 0) / 21 if ret else None, lim.max_drawdown_months, True, "num")
    add("Trades", trade.get("trades"), lim.min_trades, False, "int")
    add("Years", ret.get("years") if ret else None, lim.min_years, False, "num")
    add("Beta", bench.get("beta") if bench else None, lim.max_beta, True, "num")
    add("Cost share of gross", cost_share, lim.max_cost_share, True, "pct")
    add("Start dates passing", start_pass, lim.min_start_pass, False, "pct")
    return rows


def start_dates(spec: Strategy, prep: Prepared, settings: Settings, sig: C.Signals | None, starts: list[int]) -> list[dict]:
    """The same strategy begun on other dates, each run to the end of the development period (K-5)."""
    out, lim = [], spec.limits.max_drawdown
    for lo in starts:
        r = simulate(spec, prep, settings, sig=sig, lo=lo)
        dd = M.max_drawdown(r.equity)
        out.append({"start": str(prep.panel.dates[lo].date()), "cagr": _cagr(r.equity, settings.capital), "total_return": float(r.equity[-1] / settings.capital - 1), "max_drawdown": dd,
                    "trades": len(r.trades), "passes": None if lim is None else bool(abs(dd) <= lim)})
    return out


def _rolling(eq: np.ndarray, bench: np.ndarray | None, dates: pd.DatetimeIndex) -> list[dict]:
    e = pd.Series(eq, index=dates)
    r = e.pct_change()
    cols = {}
    for w, k in ((126, "6m"), (252, "12m"), (756, "36m")):
        cols[f"return_{k}"], cols[f"vol_{k}"] = e / e.shift(w) - 1, r.rolling(w).std() * math.sqrt(M.ANN)
        cols[f"sharpe_{k}"] = r.rolling(w).mean() / r.rolling(w).std() * math.sqrt(M.ANN)
    if bench is not None:
        b = pd.Series(bench, index=dates).pct_change()
        for w, k in ((126, "6m"), (252, "12m"), (756, "36m")):
            cols[f"beta_{k}"] = r.rolling(w).cov(b) / b.rolling(w).var()
        cols["correlation_12m"] = r.rolling(252).corr(b)
    out = pd.DataFrame(cols).replace([np.inf, -np.inf], np.nan).dropna(how="all")
    out = out.iloc[:: max(1, len(out) // 500)]
    return [{"date": str(i.date()), **{k: (float(v) if math.isfinite(v) else None) for k, v in row.items()}} for i, row in out.iterrows()]


def run_backtest(spec: Strategy, settings: Settings, progress=None) -> dict:
    """The st01 result in the labs' FeatureResult shape. Raises Refusal instead of returning an empty report."""
    started = time.perf_counter()
    info: dict = {"budget_seconds": pycode.TIMEOUT_S}

    def stage(name: str, percent: float) -> None:
        """Progress with what the run is working on and how long it has taken; a cancelled job stops at the next stage (B-85, B-86)."""
        if progress is None:
            return
        if getattr(progress, "cancelled", lambda: False)():
            raise Refusal("The run was cancelled.", ["start it again when ready"])
        progress(name, percent, {**info, "elapsed_seconds": round(time.perf_counter() - started, 2)})

    found = C.compile_spec(spec)
    if not found["ok"]:
        first = next(f for f in found["findings"] if f["severity"] == "error")
        raise Refusal(f"The strategy does not compile: {first['message']}" + (f" (line {first['line']}, '{first['token']}')" if first["token"] else "") + ".",
                      ["a rule has a typo", "a rule reads a future bar", "a setting is missing"])
    stage("load", 10)
    prep = prepare(settings)
    p, cap = prep.panel, settings.capital
    info.update(symbols=len(p.symbols), bars=len(p.dates))
    stage("signals", 30)
    sig = None if spec.code.strip() else C.signals(spec, prep.sig_bars, p.dates)
    stage("simulate", 50)
    output: dict = {}
    effective = _effective(spec, settings)
    if sig is None:
        try:
            r = _simulate_python(spec, prep, settings, output=output)
        except pycode.CodeError as exc:
            location = f" on line {exc.line}" if exc.line else ""
            raise Refusal(f"Python strategy failed{location}: {exc.message}", ["check the failing line in the Build preview"]) from exc
        n_entries = output.pop("entry_signals")
    else:
        n_entries = int(np.count_nonzero(sig.entries[np.isfinite(p.close)]))
        r = simulate(spec, prep, settings, sig=sig)
    if n_entries == 0:
        raise Refusal("0 entries: the rule is never true on this universe.",
                      ["a threshold is never reached on these names", f"the period is too short for the longest window ({len(p.dates)} bars)", "an entry needs data these names do not have"])
    closed = r.trades[r.trades[:, engine.T_REASON] != engine.R_OPEN]
    if len(r.trades) == 0:
        raise Refusal(f"{n_entries} entry signals but 0 fills.", ["the position size rounds to nothing", "the volume cap leaves no room", "signals fall on a name's last bar"])
    dates = p.dates
    ret = M.return_metrics(r.equity, dates)
    years = ret.get("years") or len(dates) / M.ANN
    tr = M.trade_metrics(r.trades[:, engine.T_PNL], r.trades[:, engine.T_RET], r.trades[:, engine.T_EXIT_BAR] - r.trades[:, engine.T_ENTRY_BAR], r.trades[:, engine.T_MAE],
                         r.trades[:, engine.T_MFE], r.trades[:, engine.T_RISK], years)
    bench_eq = None
    if prep.benchmark is not None:
        b = pd.Series(prep.benchmark).bfill().to_numpy()
        bench_eq = b / b[0] * cap
    bm = M.benchmark_metrics(r.equity, bench_eq) if bench_eq is not None else {}
    ext = M.extra_metrics(r.equity, bench_eq, dates)
    ext["psr_benchmark_sharpe"] = 1.0
    costs_total = float(r.gross_equity[-1] - r.equity[-1])
    base = cap + np.concatenate(([0.0], np.cumsum(closed[:, engine.T_PNL])[:-1]))
    side = closed[:, engine.T_DIR]
    trade_split = {k: M.lean_trade_stats(closed[m, engine.T_PNL], base[m]) for k, m in (("all", side != 0), ("long", side > 0), ("short", side < 0))}
    ext.update(profit_loss_ratio=trade_split["all"].get("profit_loss_ratio"), lean_expectancy=trade_split["all"].get("expectancy"), fees_total=costs_total, volume_traded=float(r.traded.sum()))
    gross_profit = float(r.gross_equity[-1] - cap)
    cost_share = costs_total / gross_profit if gross_profit > 0 else None
    turnover = float(r.traded.sum() / r.equity.mean() / years)

    stage("cost ladder", 60)
    ladder = []
    for m in (1, 2, 4):
        rr = r if m == 1 else simulate(spec, prep, settings, sig=sig, cost_multiple=m)
        ladder.append({"multiple": m, "cagr": _cagr(rr.equity, cap), "sharpe": M.return_metrics(rr.equity).get("sharpe"), "total_return": float(rr.equity[-1] / cap - 1)})

    stage("start dates", 70)
    n_starts = 12
    starts = sorted({int(i) for i in np.linspace(0, len(dates) // 2, n_starts)}) if len(dates) > 4 * n_starts else [0]
    sd = start_dates(spec, prep, settings, sig, starts)
    sd_pass = float(np.mean([s["passes"] for s in sd])) if sd and sd[0]["passes"] is not None else None
    cagrs = [s["cagr"] for s in sd if s["cagr"] is not None]

    stage("survivorship", 78)
    last_bar = engine._last_bar(p.close)
    dead = (last_bar < len(dates)) & (last_bar >= 0)
    held = int((last_bar >= 0).sum())
    surv = None
    if dead.any() and (~dead).any():
        rs = simulate(spec, prep, settings, sig=sig, mask=~dead)
        surv = {"status": "ok", "with_delisted": ret.get("cagr"), "survivors_only": _cagr(rs.equity, cap), "delisted": int(dead.sum()), "equity": rs.equity}

    stage("report", 90)
    trades = trades_table(r, p)
    pnl = r.trades[:, engine.T_PNL]
    order = np.argsort(-pnl)
    net_profit = float(pnl.sum())
    carried = [{"top": k, "share": float(pnl[order[:k]].sum() / net_profit) if net_profit > 0 else None,
                "cagr_without": _cagr(np.array([cap, r.equity[-1] - pnl[order[:k]].sum()]).repeat([1, len(dates) - 1]), cap) if r.equity[-1] - pnl[order[:k]].sum() > 0 else None}
               for k in (1, 5, 10) if len(pnl) >= k]
    s = pd.Series(r.equity, index=dates)
    monthly = s.resample("ME").last().pct_change().dropna()
    without_best = float((1 + monthly.sort_values().iloc[:-3]).prod() ** (12 / max(len(monthly) - 3, 1)) - 1) if len(monthly) > 6 else None
    crises = []
    for name, a, z in CRISES:
        a, z = pd.Timestamp(a), pd.Timestamp(z)
        if a >= dates[0] and z <= dates[-1]:
            i, j = dates.searchsorted(a), dates.searchsorted(z, side="right") - 1
            crises.append({"period": name, "from": str(dates[i].date()), "to": str(dates[j].date()), "strategy": float(r.equity[j] / r.equity[i] - 1),
                           "benchmark": float(bench_eq[j] / bench_eq[i] - 1) if bench_eq is not None else None})
    episodes = sorted(M.drawdowns(r.equity), key=lambda d: d["depth"])[:5]
    dd_rows = [{"depth": d["depth"], "peak": str(dates[max(d["peak"], 0)].date()), "trough": str(dates[d["trough"]].date()),
                "recovered": str(dates[d["recovery"]].date()) if d["recovery"] is not None else None, "months": d["bars"] / 21} for d in episodes]
    third = len(dates) // 3
    thirds = [M.sharpe(np.diff(r.equity[i * third:(i + 1) * third + 1]) / r.equity[i * third:(i + 1) * third]) for i in range(3)] if third > 20 else []
    # capacity: the capital at which the 10th-percentile trade would be 1% of its entry bar's dollar volume
    eb, sy = r.trades[:, engine.T_ENTRY_BAR].astype(int), r.trades[:, engine.T_SYM].astype(int)
    dollar_volume = p.volume[eb, sy] * p.close[eb, sy]
    notional = r.trades[:, engine.T_SHARES] * r.trades[:, engine.T_ENTRY_PX]
    room = 0.01 * dollar_volume / notional
    room = room[np.isfinite(room) & (room > 0)]
    capacity = float(cap * np.quantile(room, 0.10)) if len(room) else None
    by_name: dict[str, list[float]] = {}
    for t in trades:
        by_name.setdefault(t["symbol"], []).append(t["pnl"])
    per_name = sorted(({"symbol": k, "trades": len(v), "pnl": float(sum(v)), "win_rate": float(np.mean([x > 0 for x in v])), "share": float(sum(v) / net_profit) if net_profit > 0 else None,
                        "best": max(v), "worst": min(v)} for k, v in by_name.items()), key=lambda x: -x["pnl"])
    labels = paths.regimes(bench_eq, dates) if bench_eq is not None else None
    market = prep.sig_bars["market"][:, 0] if "market" in prep.sig_bars else None
    regime_rows = paths.by_regime(labels, r.trades[:, engine.T_ENTRY_BAR].astype(int), pnl, r.trades[:, engine.T_RET]) if bench_eq is not None else []
    mc = paths.trade_monte_carlo(closed[:, engine.T_PNL], cap, seed=settings.seed)
    lim_rows = check_limits(spec, ret, tr, bm, cost_share, sd_pass)
    judged = [x for x in lim_rows if x["pass"] is not None]
    closest = min((x for x in judged if x["room"] is not None), key=lambda x: x["room"], default=None)

    step = max(1, len(dates) // 2000)
    idx = sorted(set(range(0, len(dates), step)) | {len(dates) - 1})
    curve = [{"date": str(dates[i].date()), "strategy": r.equity[i], "gross": r.gross_equity[i], "benchmark": bench_eq[i] if bench_eq is not None else None,
              "survivors_only": surv["equity"][i] if surv else None,
              "regime": labels[i] if labels is not None else None} for i in idx]
    rules = paths.rule_check(r.equity, dates, settings.rule_target, settings.rule_daily_loss, settings.rule_max_dd, settings.rule_min_days)
    if surv:
        surv.pop("equity")
    exposure = [{"date": str(dates[i].date()), "gross": r.gross_exposure[i], "net": r.net_exposure[i], "positions": r.positions[i]} for i in idx]

    sign = lambda v: f"{'+' if v > 0 else ''}{v * 100:.0f}%"
    total = float(r.equity[-1] / cap - 1)
    headline = ", ".join(x for x in [
        f"{sign(total)}" + (f" vs {settings.benchmark} {sign(bm['benchmark_total_return'])}" if bm else ""), f"{years:.1f} years",
        f"Sharpe {ret['sharpe']:.2f}" if ret.get("sharpe") is not None else "", f"worst drawdown {ret['max_drawdown'] * 100:.0f}%" if ret else "", f"{len(r.trades)} trades"] if x)
    result_hash = hashlib.sha256(r.trades.tobytes() + r.equity.tobytes()).hexdigest()[:16]
    run_hash = hashlib.sha256(f"{spec.hash()}:{settings.hash()}:{data.data_version()}".encode()).hexdigest()[:16]
    few = len(r.trades) < FEW_TRADES
    cards = [("Sharpe", ret.get("sharpe"), None), ("CAGR", ret.get("cagr"), "%"), ("Max drawdown", ret.get("max_drawdown"), "%"), ("Trades", len(r.trades), None),
             ("Win rate", tr.get("win_rate"), "%"), ("Profit factor", tr.get("profit_factor"), "×")]
    out = {
        "feature_id": "st01", "status": "ok",
        "summary_cards": [{"label": k, "value": v, **({"unit": u} if u else {})} for k, v, u in cards],
        "charts": {"trade_mc": mc["fan"] if mc else [], "equity_curve": curve, "cost_ladder": ladder, "start_dates": sd, "exposure": exposure, "rolling": _rolling(r.equity, bench_eq, dates)},
        "tables": {"by_regime": regime_rows, "conditions": paths.conditions(r.equity, market, dates) if market is not None and np.isfinite(market).any() else [],
                   "rule_check": rules.pop("rows"), "holdings": [{"date": x["date"], "names": x["positions"]} for x in exposure], "seasonality": paths.seasonality(r.equity, dates), "ruin": mc["ruin"] if mc else [], "streaks": mc["streaks"] if mc else [],
                   "trades": trades, "carried_by": carried, "crises": crises, "drawdowns": dd_rows, "per_name": per_name, "my_limits": lim_rows,
                   "limits": limits.run_limits(start=str(dates[0].date()), end=str(dates[-1].date()), requested=prep.requested, held=held, delisted=int(dead.sum()), fill=settings.fill,
                                               costs=settings.costs.model_dump(), haircut=settings.delist_haircut,
                                               holdout_from=prep.holdout_from, top_n=None if settings.symbols else settings.top_n),
                   "statistics": [{"metric": k, "value": v} for k, v in {**ret, **tr, **bm, **ext}.items()]},
        "meta": {
            **output,
            "headline": headline, "verdict_chip": "not validated", "metrics": {**ret, **tr, **bm, **ext}, "total_return": total, "years": years, "benchmark": settings.benchmark if bm else None,
            "rule_check": {**rules, "target": settings.rule_target, "daily_loss": settings.rule_daily_loss, "max_dd": settings.rule_max_dd, "min_days": settings.rule_min_days},
            "costs_off": not (effective.commission_bps or effective.commission_share or effective.commission_min or effective.slippage_bps or effective.slippage_range),
            "few_trades": few, "open_trades": len(r.trades) - len(closed), "unfilled": r.unfilled, "entry_signals": n_entries,
            "trade_split": trade_split, "distribution": M.return_distribution(r.equity, dates),
            "costs": {"total": costs_total, "share_of_gross": cost_share, "gross_return": float(r.gross_equity[-1] / cap - 1), "net_return": total, "turnover_per_year": turnover},
            "exposure": {"time_in_market": float((r.positions > 0).mean()), "avg_gross": float(r.gross_exposure.mean()), "avg_net": float(r.net_exposure.mean())},
            "start_dates": {"positive": int(sum(c > 0 for c in cagrs)), "of": len(cagrs), "cagr_low": min(cagrs) if cagrs else None, "cagr_high": max(cagrs) if cagrs else None, "pass_share": sd_pass},
            "survivorship": surv or {"status": "skipped", "reason": "no name in this universe stops trading inside the period"},
            "paths": {k: v for k, v in mc.items() if k not in ("fan", "ruin", "streaks")} if mc else {"status": "skipped", "reason": "fewer than 10 closed trades"},
            "without_best_months": without_best, "thirds_sharpe": thirds, "capacity": capacity,
            "my_limits": {"passed": sum(x["pass"] for x in judged), "of": len(judged), "closest": closest},
            "holdout_from": prep.holdout_from, "period": [str(dates[0].date()), str(dates[-1].date())], "universe": {"requested": prep.requested, "held": held, "delisted": int(dead.sum())},
            "fill_model": "same_close" if effective.fill else "next_open", "data_version": data.data_version(), "freshness": limits.freshness(), "run_hash": run_hash, "result_hash": result_hash,
            "risk_events": [{"bar": e["bar"], "date": str(dates[e["bar"]].date()), "kind": e["kind"], "value": e["value"], "limit": e["limit"]} for e in r.risk_events],
            "spec": spec.model_dump(), "settings": settings.model_dump(), "description": found["description"], "findings": found["findings"],
            "limitations": [x["detail"] for x in []],
        },
    }
    out["_trial"] = {"returns": monthly.to_numpy(), "sharpe": ret.get("sharpe")}  # for the ledger; removed before the result is stored
    return _clean(out) | {"_trial": out["_trial"]}



def checks(spec: Strategy, settings: Settings) -> dict:
    """Build checks card rows (B-119): warm-up, data each rule reads and survivorship exposure."""
    prep = prepare(settings)
    p = prep.panel
    last_bar = engine._last_bar(p.close)
    dead = (last_bar < len(p.dates)) & (last_bar >= 0)
    names = [p.symbols[i] for i in np.flatnonzero(dead)]
    warmup = C.warmup_bars(spec)
    warnings = []
    if warmup and len(p.dates) and warmup >= len(p.dates):
        warnings.append(f"Warm-up needs {warmup} bars and the period holds {len(p.dates)}; no bar is eligible.")
    elif warmup and len(p.dates) and warmup > len(p.dates) / 2:
        warnings.append(f"Warm-up uses {warmup} of the {len(p.dates)} bars in the period.")
    return {
        "warmup_bars": warmup,
        "warmup_share": warmup / len(p.dates) if len(p.dates) else None,
        "warnings": warnings,
        "first_eligible_date": str(p.dates[min(warmup, len(p.dates) - 1)].date()) if len(p.dates) else None,
        "data_used": C.data_used(spec),
        "period": [str(p.dates[0].date()), str(p.dates[-1].date())] if len(p.dates) else [],
        "universe": {"symbols": len(p.symbols), "held": int((last_bar >= 0).sum()), "delisted": len(names),
                     "delisted_names": names[:10]},
        "survivorship": (
            {"status": "ok", "delisted": len(names),
             "note": "Names that stop trading inside the period are settled at their last close. Names missing from the data are not represented."}
            if names else {"status": "skipped", "reason": "no name in this universe stops trading inside the period"}
        ),
        "parameters": spec.values(),
    }


def debug_bar(spec: Strategy, settings: Settings, symbol: str, date: str, step: int, event: str | None = None, breakpoint: dict | None = None, loss_fraction: float | None = None) -> dict:
    if not spec.code.strip():
        raise Refusal("The debugger needs Python source.", ["Switch to Python or generate Python from the formula."])
    prep = prepare(settings)
    panel = prep.panel
    if symbol not in panel.symbols:
        raise Refusal(f"{symbol} is outside the run universe.", ["Select one of the strategy symbols."])
    available = np.flatnonzero(np.isfinite(panel.close[:, panel.symbols.index(symbol)]))
    dates = panel.dates[available]
    target = int(dates.searchsorted(pd.Timestamp(date)))
    if target >= len(dates) or dates[target] != pd.Timestamp(date) or not 0 <= target + step < len(dates):
        raise Refusal(f"No selected bar for {symbol} on {date} with step {step}. Valid dates run from {dates[0].date()} to {dates[-1].date()}.", ["Select an observed session within the development window."])
    target += step
    bar = int(available[target])
    output: dict = {}
    if event is not None:
        _simulate_python(spec, prep, settings, output=output, debug_symbol=symbol, debug_after=bar, debug_event=event,
                         debug_breakpoint=breakpoint, debug_loss=loss_fraction)
        if "debug" not in output:
            label = "equity loss at the requested threshold" if event == "equity" else event
            raise Refusal(f"No later {label} for {symbol}.", ["Try an earlier session or choose a different symbol."])
        target = int(available.searchsorted(output["debug"]["bar_index"]))
    else:
        end = bar + 1
        prefix = replace(prep, panel=panel.window(0, end), sig_bars={k: v[:end] for k, v in prep.sig_bars.items()},
                         benchmark=None if prep.benchmark is None else prep.benchmark[:end])
        _simulate_python(spec, prefix, settings, output=output, debug_symbol=symbol)
    return {**output["debug"], "previous_date": str(dates[target - 1].date()) if target else None,
            "next_date": str(dates[target + 1].date()) if target + 1 < len(dates) else None}

def watch(spec: Strategy, symbol: str, date: str, expressions: list[str], history: int = 20) -> list[dict]:
    """Watch expressions at a paused bar (B-71): each formula's value on `date` and over the `history` bars up to it. Formulas only read bars up to
    their own date, so a watch never shows the future, and nothing the strategy owns is touched."""
    settings = Settings(symbols=[symbol], benchmark="")
    prep = prepare(settings)
    dates = prep.panel.dates
    at = int(dates.searchsorted(pd.Timestamp(date)))
    if at >= len(dates) or dates[at] != pd.Timestamp(date):
        raise Refusal(f"No bar for {symbol} on {date}. Valid dates run from {dates[0].date()} to {dates[-1].date()}.", ["Select an observed session within the development window."])
    params = spec.values()
    rows = []
    for expression in expressions:
        try:
            series = formula.evaluate(expression, prep.sig_bars, dates, params)[:, 0]
        except Exception as exc:  # noqa: BLE001 a bad watch is reported on its own row
            rows.append({"expression": expression, "error": getattr(exc, "message", str(exc)), "value": None, "history": []})
            continue
        window = series[max(0, at + 1 - history):at + 1]
        clean = [None if not np.isfinite(v) else float(v) for v in window.astype(float)]
        rows.append({"expression": expression, "error": None, "value": clean[-1], "history": [{"date": str(d.date()), "value": v} for d, v in zip(dates[at + 1 - len(clean):at + 1], clean, strict=True)]})
    return rows


def resolve_universe(attribute: list[str] | str | None, fallback: list[str], limit: int = 50) -> list[str]:
    """Strategy.universe: a list, a library universe id, or an index name such as "master" (B-43)."""
    if attribute is None:
        return fallback
    if isinstance(attribute, list):
        return [data_loader.normalize_symbol(s) for s in attribute]
    from . import library  # lazy: library imports this module

    try:
        item = library.get(attribute)
    except KeyError:
        item = None
    if item and item.get("kind") == "universe":
        return library._pool(library.UniverseBody(**item["body"]))[:limit]
    try:
        return list(data_loader.parse_symbols({"universe": attribute, "primary_only": True}, max_symbols=limit))[:limit]
    except ValueError as exc:
        raise Refusal(f"Strategy.universe {attribute!r} is not a symbol list, library universe or index name.", [str(exc)]) from exc


def preview(spec: Strategy, symbol: str, years: float = 2.0, symbols: list[str] | None = None, *, profile: bool = False, repaint: bool = True, logpoints: list[dict] | None = None) -> dict:
    """Build's preview: one name, the last `years` of development bars, closes plus the trades the rule takes there (B-5).
    repaint=False skips the look-ahead replay (most of the time on Python code) so a typing preview stays fast; Build asks for it once typing stops."""
    found = C.compile_spec(spec)
    if not found["ok"]:
        return {"status": "skipped", "reason": "the rule does not compile", "bars": [], "trades": []}
    # load extra history so long windows are warm before the visible span
    chosen = symbols or resolve_universe(pycode.universe_attribute(spec.code) if spec.code.strip() else None, [symbol])
    settings = Settings(symbols=chosen, benchmark="")
    prep = prepare(settings)
    p = prep.panel
    lo = max(0, int(p.dates.searchsorted(p.dates[-1] - pd.DateOffset(days=int(365 * years)))))
    output: dict = {"order_lines": True, "profile": profile, **({"logpoints": logpoints} if logpoints else {})}
    if spec.code.strip():
        # Start a year before the window so history-based code is warm, then shift the bar indexes back to the full panel.
        run_from = max(0, lo - 252)
        r = _simulate_python(spec, prep, settings, lo=run_from, output=output, repaint_from=None if profile or not repaint else lo - run_from)
        output.pop("entry_signals")
        for col in (engine.T_ENTRY_BAR, engine.T_EXIT_BAR, engine.T_SIGNAL_BAR):
            r.trades[:, col] += run_from
        for event in r.risk_events:
            event["bar"] += run_from
    else:
        sig = C.signals(spec, prep.sig_bars, p.dates)
        r = simulate(spec, prep, settings, sig=sig)
        if repaint:
            output["repaint"] = repaint_check(spec, prep, lo, full=sig)
    start = str(p.dates[lo].date())
    trades = [t for t in trades_table(r, p) if t["entry_date"] >= start]
    by_symbol = {name: [{"date": str(d.date()), "close": float(c)} for d, c in zip(p.dates[lo:], p.close[lo:, i], strict=True) if np.isfinite(c)]
                 for i, name in enumerate(p.symbols)}
    bars = by_symbol[p.symbols[0]]
    if len(p.symbols) > 1:  # a book: the return is the account's, not a product of trade returns
        total = float(r.equity[-1] / r.equity[lo - run_from if spec.code.strip() else lo] - 1)
    else:
        total = float(np.prod([1 + t["return"] for t in trades]) - 1) if trades else 0.0
    risk = [{"date": str(p.dates[e["bar"]].date()), "kind": e["kind"], "value": e["value"], "limit": e["limit"]} for e in r.risk_events]
    output.pop("risk_events", None)
    if isinstance(output.get("warmup"), dict):  # B-53: the longest window any rule needs, when the code sets no warmup of its own
        needed = C.warmup_bars(spec)
        output["warmup"] = {**output["warmup"], "inferred_bars": needed, "inferred_start_date": str(p.dates[needed].date()) if needed < len(p.dates) else None}
    if output.get("profile") in (False, None):
        output.pop("profile", None)
    if output.get("order_lines") is True:  # formula strategies place no Python orders
        output["order_lines"] = []
    return {"status": "ok", "symbol": p.symbols[0], "symbols": list(p.symbols), "bars_by_symbol": by_symbol, "window": {"start": start, "end": str(p.dates[-1].date())}, "bars": bars, "trades": trades, "total_return": total, **output, "risk_events": risk}


def repaint_check(spec: Strategy, prep: Prepared, lo: int = 0, cuts: int = 50, *, full: C.Signals | None = None) -> dict:
    """Recompute the rule on history cut at `cuts` bars; the signal on each cut bar must equal the full-history signal. Any mismatch reads the future."""
    dates = prep.panel.dates
    symbols = list(prep.panel.symbols)
    full = full if full is not None else C.signals(spec, prep.sig_bars, dates, symbols=symbols)
    at = np.unique(np.linspace(max(lo, 1), len(dates) - 1, cuts).astype(int))
    bad = []
    for t in at:
        cut = C.signals(spec, {k: v[:t + 1] for k, v in prep.sig_bars.items()}, dates[:t + 1], symbols=symbols)
        same = np.array_equal(cut.entries[t], full.entries[t]) and np.array_equal(cut.exits[t], full.exits[t])
        if not same:
            bad.append(str(dates[t].date()))
    return {"cuts": len(at), "changed": len(bad), "dates": bad[:5]}
