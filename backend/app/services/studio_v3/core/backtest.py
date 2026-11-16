"""st01 Backtest: one run of the compiled strategy on the development period, and everything the page shows about it."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from app.services.screener_v2.core import data_loader
from app.services.shared import metrics as M

from . import compile as C
from . import data, engine, limits
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
    hourly: tuple | None
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
    if not len(p.dates):
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
    bench = None
    if settings.benchmark:
        b = data.panel([settings.benchmark], None, None)
        if len(b.dates):
            bench = pd.Series(b.close[:, 0], index=b.dates).reindex(p.dates, method="ffill").to_numpy()
            if not np.isfinite(bench).any():
                bench = None
    return Prepared(p, sig_bars, bench, data.magnifier(p) if settings.magnifier else None, holdout_from, len(symbols), all_dates)


def simulate(spec: Strategy, prep: Prepared, settings: Settings, *, sig: C.Signals | None = None, cost_multiple: float = 1.0, lo: int = 0, magnifier: bool = True,
             mask: np.ndarray | None = None, params: dict[str, float] | None = None, exits_override: dict | None = None) -> engine.Result:
    sig = sig or C.signals(spec, prep.sig_bars, prep.panel.dates, params)
    traded = np.isfinite(prep.panel.close)
    entries = np.where(traded if mask is None else traded & mask[None, :], sig.entries, 0).astype(np.int8)
    p = engine_params(spec, settings, cost_multiple)
    if exits_override:
        p = replace(p, **exits_override)
    hourly = prep.hourly if magnifier else None
    if lo:
        hourly = (hourly[0], hourly[1], hourly[2][lo:]) if hourly else None
        bars = {k: v[lo:] for k, v in prep.panel.bars().items()}
        return engine.run(bars, entries[lo:], sig.exits[lo:], p, score=None if sig.score is None else sig.score[lo:], stop_dist=None if sig.stop_dist is None else sig.stop_dist[lo:], hourly=hourly)
    return engine.run(prep.panel.bars(), entries, sig.exits, p, score=sig.score, stop_dist=sig.stop_dist, hourly=hourly)


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


def start_dates(spec: Strategy, prep: Prepared, settings: Settings, sig: C.Signals, starts: list[int]) -> list[dict]:
    """The same strategy begun on other dates, each run to the end of the development period (K-5)."""
    out, lim = [], spec.limits.max_drawdown
    for lo in starts:
        r = simulate(spec, prep, settings, sig=sig, lo=lo)
        dd = M.max_drawdown(r.equity)
        out.append({"start": str(prep.panel.dates[lo].date()), "cagr": _cagr(r.equity, settings.capital), "total_return": float(r.equity[-1] / settings.capital - 1), "max_drawdown": dd,
                    "trades": len(r.trades), "passes": None if lim is None else bool(abs(dd) <= lim)})
    return out


def _rolling(eq: np.ndarray, bench: np.ndarray | None, dates: pd.DatetimeIndex) -> list[dict]:
    r = pd.Series(eq, index=dates).pct_change()
    out = pd.DataFrame({"sharpe_6m": r.rolling(126).mean() / r.rolling(126).std() * math.sqrt(M.ANN), "sharpe_12m": r.rolling(252).mean() / r.rolling(252).std() * math.sqrt(M.ANN),
                        "vol_6m": r.rolling(126).std() * math.sqrt(M.ANN)})
    if bench is not None:
        b = pd.Series(bench, index=dates).pct_change()
        out["beta_12m"], out["correlation_12m"] = r.rolling(252).cov(b) / b.rolling(252).var(), r.rolling(252).corr(b)
    out = out.dropna(how="all").iloc[:: max(1, len(out) // 500)]
    return [{"date": str(i.date()), **{k: (float(v) if math.isfinite(v) else None) for k, v in row.items()}} for i, row in out.iterrows()]


def run_backtest(spec: Strategy, settings: Settings, progress=None) -> dict:
    """The st01 result in the labs' FeatureResult shape. Raises Refusal instead of returning an empty report."""
    stage = progress or (lambda *_: None)
    found = C.compile_spec(spec)
    if not found["ok"]:
        first = next(f for f in found["findings"] if f["severity"] == "error")
        raise Refusal(f"The strategy does not compile: {first['message']}" + (f" (line {first['line']}, '{first['token']}')" if first["token"] else "") + ".",
                      ["a rule has a typo", "a rule reads a future bar", "a setting is missing"])
    if spec.code.strip() and not (spec.entry_long.strip() or spec.entry_short.strip()):
        raise Refusal("Python strategies cannot run yet.", ["the sandbox is not built", "write the rule as a formula", "or as blocks"])
    stage("load", 10)
    prep = prepare(settings)
    p, cap = prep.panel, settings.capital
    stage("signals", 30)
    sig = C.signals(spec, prep.sig_bars, p.dates)
    n_entries = int(np.count_nonzero(sig.entries[np.isfinite(p.close)]))
    if n_entries == 0:
        raise Refusal("0 entries: the rule is never true on this universe.",
                      ["a threshold is never reached on these names", f"the period is too short for the longest window ({len(p.dates)} bars)", "an entry needs data these names do not have"])
    stage("simulate", 50)
    r = simulate(spec, prep, settings, sig=sig)
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
    costs_total = float(r.gross_equity[-1] - r.equity[-1])
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

    stage("fill check", 84)
    e = spec.exits
    hourly_held = int((prep.hourly[2][:, :, 0] >= 0).any(axis=0).sum()) if prep.hourly else 0
    fill = {"status": "skipped", "reason": "worst-case same-bar rule applied: no hourly bars for these names" if not hourly_held else "needs a stop and a target: only then can both fall inside one bar"}
    if hourly_held and (e.stop or e.stop_atr) and (e.target or e.scale_at):
        rb = simulate(spec, prep, settings, sig=sig, magnifier=False)
        fill = {"status": "ok", "hourly_names": hourly_held, "with_hourly": float(r.equity[-1] / cap - 1), "daily_only": float(rb.equity[-1] / cap - 1), "daily_equity": rb.equity}

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
    lim_rows = check_limits(spec, ret, tr, bm, cost_share, sd_pass)
    judged = [x for x in lim_rows if x["pass"] is not None]
    closest = min((x for x in judged if x["room"] is not None), key=lambda x: x["room"], default=None)

    step = max(1, len(dates) // 2000)
    idx = sorted(set(range(0, len(dates), step)) | {len(dates) - 1})
    curve = [{"date": str(dates[i].date()), "strategy": r.equity[i], "gross": r.gross_equity[i], "benchmark": bench_eq[i] if bench_eq is not None else None,
              "survivors_only": surv["equity"][i] if surv else None, "daily_fills": fill["daily_equity"][i] if fill["status"] == "ok" else None} for i in idx]
    if surv:
        surv.pop("equity")
    if fill["status"] == "ok":
        fill.pop("daily_equity")
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
        "charts": {"equity_curve": curve, "cost_ladder": ladder, "start_dates": sd, "exposure": exposure, "rolling": _rolling(r.equity, bench_eq, dates)},
        "tables": {"trades": trades, "carried_by": carried, "crises": crises, "drawdowns": dd_rows, "per_name": per_name, "my_limits": lim_rows,
                   "limits": limits.run_limits(start=str(dates[0].date()), end=str(dates[-1].date()), requested=prep.requested, held=held, delisted=int(dead.sum()), fill=settings.fill,
                                               costs=settings.costs.model_dump(), haircut=settings.delist_haircut, hourly_held=hourly_held, magnifier=settings.magnifier,
                                               holdout_from=prep.holdout_from, top_n=None if settings.symbols else settings.top_n),
                   "statistics": [{"metric": k, "value": v} for k, v in {**ret, **tr, **bm}.items()]},
        "meta": {
            "headline": headline, "verdict_chip": "not validated", "metrics": {**ret, **tr, **bm}, "total_return": total, "years": years, "benchmark": settings.benchmark if bm else None,
            "costs_off": settings.costs.off(), "few_trades": few, "open_trades": len(r.trades) - len(closed), "unfilled": r.unfilled, "entry_signals": n_entries,
            "costs": {"total": costs_total, "share_of_gross": cost_share, "gross_return": float(r.gross_equity[-1] / cap - 1), "net_return": total, "turnover_per_year": turnover},
            "exposure": {"time_in_market": float((r.positions > 0).mean()), "avg_gross": float(r.gross_exposure.mean()), "avg_net": float(r.net_exposure.mean())},
            "start_dates": {"positive": int(sum(c > 0 for c in cagrs)), "of": len(cagrs), "cagr_low": min(cagrs) if cagrs else None, "cagr_high": max(cagrs) if cagrs else None, "pass_share": sd_pass},
            "survivorship": surv or {"status": "skipped", "reason": "no name in this universe stops trading inside the period"},
            "fill_check": fill, "without_best_months": without_best, "thirds_sharpe": thirds, "capacity": capacity,
            "my_limits": {"passed": sum(x["pass"] for x in judged), "of": len(judged), "closest": closest},
            "holdout_from": prep.holdout_from, "period": [str(dates[0].date()), str(dates[-1].date())], "universe": {"requested": prep.requested, "held": held, "delisted": int(dead.sum())},
            "fill_model": settings.fill, "data_version": data.data_version(), "freshness": limits.freshness(), "run_hash": run_hash, "result_hash": result_hash,
            "spec": spec.model_dump(), "settings": settings.model_dump(), "description": found["description"], "findings": found["findings"],
            "limitations": [x["detail"] for x in []],
        },
    }
    out["_trial"] = {"returns": monthly.to_numpy(), "sharpe": ret.get("sharpe")}  # for the ledger; removed before the result is stored
    return _clean(out) | {"_trial": out["_trial"]}
