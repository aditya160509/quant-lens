"""Twenty starter strategies, each a full spec with a one-line rule."""

from __future__ import annotations

import threading

from .compile import compile_spec
from .spec import Strategy


def _t(name: str, rule: str, **spec) -> dict:
    return {"name": name, "rule": rule, "spec": {"name": name, **spec}}


def _p(**values) -> dict:
    return {k: {"value": v, "min": lo, "max": hi, "step": step} for k, (v, lo, hi, step) in values.items()}


TEMPLATES = [
    _t("SMA cross", "Buy when the 50-day average crosses above the 200-day; sell on the cross back.", entry_long="crosses_above(sma(close, fast), sma(close, slow))",
       exit_long="crosses_below(sma(close, fast), sma(close, slow))", params=_p(fast=(50, 20, 100, 10), slow=(200, 100, 300, 20))),
    _t("EMA trend", "Hold while the 20-day EMA is above the 100-day EMA.", entry_long="ema(close, fast) > ema(close, slow)", exit_long="ema(close, fast) < ema(close, slow)",
       params=_p(fast=(20, 10, 50, 5), slow=(100, 50, 200, 10))),
    _t("Price above 200-day", "Own it above the 200-day average, cash below.", entry_long="close > sma(close, n)", exit_long="close < sma(close, n)", params=_p(n=(200, 100, 300, 20))),
    _t("Donchian breakout", "Buy a 55-day high; sell a 20-day low.", entry_long="close >= highest(high, entry_n)", exit_long="close <= lowest(low, exit_n)",
       params=_p(entry_n=(55, 20, 100, 5), exit_n=(20, 10, 50, 5)), exits={"stop_atr": 2.0}, sizing={"mode": "risk", "value": 0.01, "max_positions": 10}),
    _t("52-week high", "Buy a new 252-day high; trail an 8% stop.", entry_long="close >= highest(close, 252)", exits={"trail": 0.08}),
    _t("RSI(2) dip", "Buy a 2-day RSI under 10 in an uptrend; sell over 70.", entry_long="(rsi(close, 2) < low_level) & (close > sma(close, 200))", exit_long="rsi(close, 2) > 70",
       params=_p(low_level=(10, 5, 30, 5)), exits={"time_stop": 10}),
    _t("RSI(14) reversal", "Buy when the 14-day RSI climbs back over 30; sell over 60.", entry_long="crosses_above(rsi(close, 14), 30)", exit_long="rsi(close, 14) > 60", exits={"stop": 0.08}),
    _t("Bollinger bounce", "Buy below the lower band; sell at the middle.", entry_long="close < sma(close, 20) - width * std(close, 20)", exit_long="close > sma(close, 20)",
       params=_p(width=(2, 1, 3, 0.25)), exits={"stop": 0.1}),
    _t("Bollinger breakout", "Buy above the upper band; sell under the middle.", entry_long="close > sma(close, 20) + width * std(close, 20)", exit_long="close < sma(close, 20)",
       params=_p(width=(2, 1, 3, 0.25))),
    _t("12-month momentum", "Hold the ten strongest names over 12 months.", entry_long="rank(roc(close, 252)) > 0.9", exit_long="rank(roc(close, 252)) < 0.7", score="roc(close, 252)"),
    _t("6-month momentum, trend filter", "Top decile over 6 months, only above the 200-day.", entry_long="(rank(roc(close, 126)) > 0.9) & (close > sma(close, 200))",
       exit_long="(rank(roc(close, 126)) < 0.6) | (close < sma(close, 200))", score="roc(close, 126)"),
    _t("Short-term reversal", "Buy the week's worst decile; hold five days.", entry_long="rank(roc(close, 5)) < 0.1", exits={"time_stop": 5}, score="0 - roc(close, 5)"),
    _t("Low volatility", "Hold the calmest names of the last 60 days.", entry_long="rank(std(returns, 60)) < 0.1", exit_long="rank(std(returns, 60)) > 0.3", score="0 - std(returns, 60)"),
    _t("Volume breakout", "Buy a 20-day high on double the usual volume.", entry_long="(close >= highest(close, 20)) & (volume > 2 * sma(volume, 20))", exits={"stop": 0.07, "target": 0.15, "time_stop": 30}),
    _t("Gap down fade", "Buy a 3% gap down in an uptrend; out in three days.", entry_long="(open < delay(close, 1) * 0.97) & (close > sma(close, 200))", exits={"time_stop": 3, "stop": 0.05}),
    _t("Pullback in trend", "Buy three down days above the 100-day average.", entry_long="(close < delay(close, 1)) & (delay(close, 1) < delay(close, 2)) & (delay(close, 2) < delay(close, 3)) & (close > sma(close, 100))",
       exit_long="close > sma(close, 5)", exits={"stop": 0.06}),
    _t("ATR channel", "Buy above the 20-day average plus two ATR; trail three ATR.", entry_long="close > sma(close, 20) + 2 * atr(14)", exit_long="close < sma(close, 20)", exits={"stop_atr": 3.0}),
    _t("Weekly trend, daily entry", "Buy a daily 20-day high while last week closed above its 10-week average.", entry_long="(close >= highest(close, 20)) & (weekly(close) > weekly(sma(close, 50)))",
       exit_long="close < sma(close, 50)"),
    _t("Scale out winner", "Breakout; sell half at +10%, stop to entry at +5%.", entry_long="close >= highest(close, 50)", exit_long="close < sma(close, 50)",
       exits={"stop": 0.08, "breakeven": 0.05, "scale_at": 0.10, "scale_frac": 0.5}),
    _t("Long-short momentum", "Long the strongest decile, short the weakest.", entry_long="rank(roc(close, 126)) > 0.9", exit_long="rank(roc(close, 126)) < 0.7",
       entry_short="rank(roc(close, 126)) < 0.1", exit_short="rank(roc(close, 126)) > 0.3", sizing={"mode": "pct_equity", "value": 0.05, "max_positions": 20}),
]


def list_templates() -> list[dict]:
    return [{**t, "description": compile_spec(Strategy(**t["spec"]))["description"]} for t in TEMPLATES]


PYTHON_TEMPLATES = [
    _t("Python trend", "Buy above the 100-session average and exit below it.", code='''class Strategy:
    warmup = 99

    def on_bar(self, ctx):
        if ctx.rule("close > sma(close, 100)"):
            ctx.buy()
        else:
            ctx.sell()
'''),
    _t("Python mean reversion", "Buy an oversold RSI and exit when it recovers.", code='''class Strategy:
    def on_bar(self, ctx):
        if ctx.rule("rsi(close, 14) < 35"):
            ctx.buy()
        elif ctx.rule("rsi(close, 14) > 55"):
            ctx.sell()
'''),
    _t("Python momentum rotation", "At month start, hold the strongest name by 63-session return.", code='''class Strategy:
    warmup = 63
    rebalance_schedule = "month_start"

    def on_data(self, ctx):
        if not ctx.rebalancing:
            return
        ranked = ctx.rank("roc(close, 63)", top=1)
        if ranked:
            leader = ranked[0][0]
            ctx.target_weights({symbol: 0.9 if symbol == leader else 0 for symbol in ctx.symbols})
'''),
    _t("Python pairs", "Trade the spread between SPY and QQQ after normalising each by its recent average.", code='''class Strategy:
    warmup = 30

    def on_data(self, ctx):
        if "SPY" not in ctx.symbols or "QQQ" not in ctx.symbols:
            return
        spy = ctx.value("close / sma(close, 30)", "SPY")
        qqq = ctx.value("close / sma(close, 30)", "QQQ")
        spread = spy - qqq
        if abs(spread) < 0.005:
            ctx.liquidate()
        elif spread > 0.025:
            ctx.target_weights({"SPY": -0.25, "QQQ": 0.25})
        elif spread < -0.025:
            ctx.target_weights({"SPY": 0.25, "QQQ": -0.25})
'''),
    _t("Python volatility target", "Scale exposure to a 12% annualised volatility target each month.", code='''class Strategy:
    warmup = 21
    rebalance_schedule = "month_start"

    def on_data(self, ctx):
        if not ctx.rebalancing:
            return
        for symbol in ctx.symbols:
            volatility = ctx.value("std(returns, 20)", symbol) * math.sqrt(252)
            if volatility > 0:
                ctx.set_holdings(symbol, min(0.9, 0.12 / volatility) / len(ctx.symbols))
'''),
    _t("Python breakout", "Enter on a new 30-session closing high and exit below the 15-session average.", code='''class Strategy:
    def on_bar(self, ctx):
        if ctx.rule("close > delay(highest(close, 30), 1)"):
            ctx.buy()
        elif ctx.rule("close < sma(close, 15)"):
            ctx.sell()
'''),
    _t("Python seasonality", "Enter at the start of each month and exit after five observed sessions.", code='''class Strategy:
    def init(self, ctx):
        self.exit_at = 0

    def on_data(self, ctx):
        if ctx.is_month_start:
            ctx.target_weights({symbol: 0.9 / len(ctx.symbols) for symbol in ctx.symbols})
            self.exit_at = ctx.bar_index + 5
        elif ctx.bar_index == self.exit_at:
            ctx.liquidate()
'''),
    _t("Python ML score", "Fit a one-feature streaming regression to completed daily returns.", code='''class Strategy:
    warmup = 30

    def init(self, ctx):
        self.cross_product = 0.0
        self.feature_power = 0.0

    def on_bar(self, ctx):
        x = ctx.value("delay(returns, 1)")
        y = ctx.value("returns")
        if math.isfinite(x) and math.isfinite(y):
            self.cross_product = 0.98 * self.cross_product + x * y
            self.feature_power = 0.98 * self.feature_power + x * x
            if self.feature_power > 0:
                score = self.cross_product / self.feature_power * y
                if score > 0:
                    ctx.buy()
                elif score < 0:
                    ctx.sell()
'''),
    _t("Python dual momentum", "Each month hold US or international stocks, whichever rose more over 12 months, and bonds when neither beat cash.", code='''class Strategy:
    universe = ["SPY", "EFA", "IEF", "BIL"]
    warmup = 252
    rebalance_schedule = "month_start"

    def on_data(self, ctx):
        if not ctx.rebalancing:
            return
        ret = {symbol: ctx.value("roc(close, 252)", symbol) for symbol in ("SPY", "EFA", "BIL")}
        best = "SPY" if ret["SPY"] >= ret["EFA"] else "EFA"
        hold = best if ret[best] > ret["BIL"] else "IEF"
        ctx.target_weights({symbol: 0.95 if symbol == hold else 0 for symbol in ctx.symbols})
'''),
    _t("Python sector rotation", "Each month hold the three sectors with the best 6-month return.", code='''class Strategy:
    universe = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
    warmup = 126
    rebalance_schedule = "month_start"

    def on_data(self, ctx):
        if not ctx.rebalancing:
            return
        top = [symbol for symbol, _ in ctx.rank("roc(close, 126)", top=3)]
        ctx.target_weights({symbol: 0.32 if symbol in top else 0 for symbol in ctx.symbols}, corridor=0.03)
'''),
    _t("Python risk parity", "Each month weight stocks, bonds and gold by inverse 3-month volatility.", code='''class Strategy:
    universe = ["SPY", "TLT", "GLD"]
    warmup = 63
    rebalance_schedule = "month_start"

    def on_data(self, ctx):
        if not ctx.rebalancing:
            return
        vol = {symbol: ctx.value("std(returns, 63)", symbol) for symbol in ctx.symbols}
        inverse = {symbol: 1 / v for symbol, v in vol.items() if math.isfinite(v) and v > 0}
        total = sum(inverse.values())
        if not total:
            return
        ctx.target_weights({symbol: 0.95 * value / total for symbol, value in inverse.items()}, corridor=0.02)
'''),
]


def list_python_templates() -> list[dict]:
    return [{"name": template["name"], "rule": template["rule"], "spec": template["spec"],
             "symbols": _universe(template["spec"]["code"]) or (["SPY", "QQQ"] if template["name"] == "Python pairs" else ["SPY", "QQQ", "IWM"])}
            for template in PYTHON_TEMPLATES]


def _universe(code: str) -> list[str] | None:
    from . import pycode
    found = pycode.universe_attribute(code)
    return found if isinstance(found, list) else None


# --- gallery stats (B-97): each starter's backtest on its default universe, computed once per data version off the request path ---

_stats_running = threading.Event()


def stats() -> dict:
    from . import data, store
    key = f"template_stats:{data.data_version()}"
    done = store.kv_get(key)
    if done is not None:
        return {"status": "ready", "stats": done}
    if not _stats_running.is_set():
        _stats_running.set()
        threading.Thread(target=_compute_stats, args=(key,), daemon=True).start()
    return {"status": "computing", "stats": {}}


def _compute_stats(key: str) -> None:
    import numpy as np

    from . import backtest, store
    from .spec import Settings, Strategy
    out = {}
    try:
        items = [(t["name"], t["spec"], None) for t in list_templates()] + [(t["name"], t["spec"], t["symbols"]) for t in list_python_templates()]
        for name, spec, symbols in items:
            try:
                settings = Settings(symbols=symbols, benchmark="") if symbols else Settings()
                prep = backtest.prepare(settings)
                r = backtest.simulate(Strategy(**spec), prep, settings)
                eq = np.asarray(r.equity, dtype=float)
                rets = np.diff(eq) / eq[:-1]
                sd = float(np.std(rets))
                out[name] = {"total_return": float(eq[-1] / eq[0] - 1), "sharpe": float(np.mean(rets) / sd * np.sqrt(252)) if sd > 0 else None,
                             "max_drawdown": float((eq / np.maximum.accumulate(eq) - 1).min()), "trades": len(r.trades),
                             "start": str(prep.panel.dates[0].date()), "end": str(prep.panel.dates[-1].date()), "symbols": len(prep.panel.symbols)}
            except Exception as exc:  # noqa: BLE001 one broken starter must not hide the others
                out[name] = {"error": str(exc)[:200]}
        store.kv_set(key, out)
    finally:
        _stats_running.clear()
