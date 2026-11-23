"""Twenty starter strategies, each a full spec with a one-line rule."""

from __future__ import annotations

import re
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
    _t("Python Supertrend", "Ride the Supertrend while RSI is not stretched; the chart draws both from the same numbers.", code='''from studio import ta


class Strategy:
    def init(self, ctx):
        self.trend = self.use(ta.Supertrend, factor=3.0, atr_period=10)
        self.rsi = self.use(ta.RSI, length=14)

    def on_bar(self, ctx):
        if not self.trend.ready:
            return
        if ctx.position == 0 and self.trend["direction"] < 0 and self.rsi.value < 70:
            ctx.buy()
        elif ctx.position > 0 and self.trend["direction"] > 0:
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


def _classic(name: str, rule: str, inputs: str, chart: str, body: str, plots: str = "") -> dict:
    """A strategy ported from the old chart engine's list (TradingView's built-in strategies), long or flat: one indicator class computes
    the buy and sell signals with studio.ta over the whole history, and the strategy acts on them bar by bar."""
    lines = "\n".join(f"        {line}" for line in body.strip().splitlines())
    reads = "        p = self.inputs\n" if re.search(r"\bp\[", body) else ""
    imports = ("import numpy as np\n" if "np." in body else "") + ("from studio import ta\n" if "ta." in body else "")
    code = f'''{imports}


class Signals:
    inputs = {inputs}
    chart = "{chart}"
    plots = {{"buy": {{"display": "none"}}, "sell": {{"display": "none"}}{plots}}}

    def compute(self, bars):
{reads}{lines}


class Strategy:
    def init(self, ctx):
        self.signals = self.use(Signals)

    def on_bar(self, ctx):
        if ctx.position == 0 and self.signals["buy"]:
            ctx.buy()
        elif ctx.position > 0 and self.signals["sell"]:
            ctx.sell()
'''
    return _t(name, rule, code=code)


C, H, L, O = 'bars["close"]', 'bars["high"]', 'bars["low"]', 'bars["open"]'
CLASSICS = [
    _classic("Classic: MA cross", "Buy when the 10-bar average crosses above the 20-bar one; sell on the cross back.", '{"fast": (10, 2, 50, 1), "slow": (20, 5, 200, 1)}', "main", f"""
fast, slow = ta.sma({C}, p["fast"]), ta.sma({C}, p["slow"])
return {{"buy": ta.crossover(fast, slow), "sell": ta.crossunder(fast, slow), "fast": fast, "slow": slow}}"""),
    _classic("Classic: three MA stack", "Buy when the 5, 10 and 20-bar averages stack upward; sell when they stack downward.", '{"short": (5, 2, 20, 1), "medium": (10, 5, 50, 1), "long": (20, 10, 100, 1)}', "main", f"""
a, m, z = ta.sma({C}, p["short"]), ta.sma({C}, p["medium"]), ta.sma({C}, p["long"])
up, down = (a > m) & (m > z), (a < m) & (m < z)
return {{"buy": up & ~np.r_[False, up[:-1]], "sell": down & ~np.r_[False, down[:-1]], "short": a, "medium": m, "long": z}}"""),
    _classic("Classic: RSI", "Buy when RSI(14) climbs back over 30; sell when it falls back under 70.", '{"length": (14, 2, 50, 1), "oversold": (30, 10, 40, 1), "overbought": (70, 60, 90, 1)}', "own", f"""
r = ta.rsi({C}, p["length"])
return {{"buy": ta.crossover(r, p["oversold"]), "sell": ta.crossunder(r, p["overbought"]), "rsi": r}}"""),
    _classic("Classic: MACD", "Buy when MACD crosses above its signal line; sell on the cross below.", '{"fast": (12, 5, 30, 1), "slow": (26, 10, 50, 1), "signal": (9, 3, 20, 1)}', "own", f"""
line, signal, hist = ta.macd({C}, p["fast"], p["slow"], p["signal"])
return {{"buy": ta.crossover(line, signal), "sell": ta.crossunder(line, signal), "macd": line, "signal": signal, "hist": hist}}""", ', "hist": {"style": "histogram"}'),
    _classic("Classic: Bollinger Bands", "Buy when the low first touches the lower band; sell when the high first touches the upper band.", '{"length": (20, 5, 50, 1), "mult": (2.0, 1.0, 4.0, 0.5)}', "main", f"""
basis, upper, lower = ta.bb({C}, p["length"], p["mult"])
return {{"buy": ta.crossunder({L}, lower), "sell": ta.crossover({H}, upper), "upper": upper, "basis": basis, "lower": lower}}"""),
    _classic("Classic: stochastic slow", "Buy when %K crosses above %D near oversold; sell when it crosses below near overbought.", '{"k": (14, 5, 30, 1), "d": (3, 1, 10, 1), "smooth": (3, 1, 10, 1), "oversold": (20, 5, 30, 1), "overbought": (80, 70, 95, 1)}', "own", f"""
k = ta.sma(ta.stoch({C}, {H}, {L}, p["k"]), p["smooth"])
d = ta.sma(k, p["d"])
return {{"buy": ta.crossover(k, d) & (k < p["oversold"] + 10), "sell": ta.crossunder(k, d) & (k > p["overbought"] - 10), "k": k, "d": d}}"""),
    _classic("Classic: momentum", "Buy when 10-bar momentum turns positive; sell when it turns negative.", '{"length": (10, 3, 50, 1)}', "own", f"""
m = ta.mom({C}, p["length"])
return {{"buy": ta.crossover(m, 0), "sell": ta.crossunder(m, 0), "momentum": m}}"""),
    _classic("Classic: consecutive up/down", "Buy after three down bars in a row; sell after three up bars.", '{"bars": (3, 2, 7, 1)}', "main", f"""
return {{"buy": ta.sma({C} < {O}, p["bars"]) == 1, "sell": ta.sma({C} > {O}, p["bars"]) == 1}}"""),
    _classic("Classic: bar up/down", "Buy on an up bar after a down bar; sell on a down bar after an up bar.", "{}", "main", f"""
up, down = {C} > {O}, {C} < {O}
return {{"buy": up & np.r_[False, ~up[:-1]], "sell": down & np.r_[False, ~down[:-1]]}}"""),
    _classic("Classic: inside bar", "After an inside bar, buy a close above the mother bar's high; sell a close below its low.", "{}", "main", f"""
mother_high, mother_low = ta.shift({H}, 2), ta.shift({L}, 2)
inside = (ta.shift({H}) < mother_high) & (ta.shift({L}) > mother_low)
return {{"buy": inside & ({C} > mother_high), "sell": inside & ({C} < mother_low)}}"""),
    _classic("Classic: outside bar", "Buy an up bar that engulfs the last bar's range; sell a down one.", "{}", "main", f"""
outside = ({H} > ta.shift({H})) & ({L} < ta.shift({L}))
return {{"buy": outside & ({C} > {O}), "sell": outside & ({C} < {O})}}"""),
    _classic("Classic: greedy trend", "Buy a rising close above its 10-bar average; sell a falling close below it.", '{"length": (10, 3, 30, 1)}', "main", f"""
ma, prev = ta.sma({C}, p["length"]), ta.shift({C})
return {{"buy": ({C} > ma) & ({C} > prev), "sell": ({C} < ma) & ({C} < prev), "average": ma}}"""),
    _classic("Classic: channel breakout", "Buy a close through the prior 20-bar high; sell a close through the prior 20-bar low.", '{"length": (20, 5, 50, 1)}', "main", f"""
upper, lower = ta.shift(ta.highest({H}, p["length"])), ta.shift(ta.lowest({L}, p["length"]))
return {{"buy": ta.crossover({C}, upper), "sell": ta.crossunder({C}, lower), "upper": upper, "lower": lower}}"""),
    _classic("Classic: Parabolic SAR", "Buy when price closes above the SAR; sell when it closes below.", '{"start": (0.02, 0.01, 0.1, 0.01), "maximum": (0.2, 0.1, 0.5, 0.05)}', "main", f"""
s = ta.sar({H}, {L}, {C}, p["start"], p["start"], p["maximum"])
return {{"buy": ta.crossover({C}, s), "sell": ta.crossunder({C}, s), "sar": s}}""", ', "sar": {"style": "dots"}'),
    _classic("Classic: Keltner breakout", "Buy a close above the upper Keltner band; sell a close below the lower band.", '{"ema": (20, 5, 50, 1), "atr": (10, 5, 30, 1), "mult": (2.0, 1.0, 4.0, 0.5)}', "main", f"""
basis = ta.ema({C}, p["ema"])
width = p["mult"] * ta.atr({H}, {L}, {C}, p["atr"])
return {{"buy": ta.crossover({C}, basis + width), "sell": ta.crossunder({C}, basis - width), "upper": basis + width, "basis": basis, "lower": basis - width}}"""),
    _classic("Classic: ADX breakout", "When ADX rises through 25, buy if price is above its level 5 bars ago, sell if below.", '{"length": (14, 5, 30, 1), "threshold": (25, 15, 40, 1)}', "own", f"""
adx = ta.dmi({H}, {L}, {C}, p["length"], p["length"])[2]
fired, rising = ta.crossover(adx, p["threshold"]), {C} > ta.shift({C}, 5)
return {{"buy": fired & rising, "sell": fired & ~rising, "adx": adx}}"""),
    _classic("Classic: price channel", "Buy a high above the prior 20-bar high; sell a low under the prior 20-bar low.", '{"length": (20, 5, 55, 1)}', "main", f"""
upper, lower = ta.shift(ta.highest({H}, p["length"])), ta.shift(ta.lowest({L}, p["length"]))
return {{"buy": {H} > upper, "sell": {L} < lower, "upper": upper, "lower": lower}}"""),
    _classic("Classic: volatility expansion", "Buy a one-bar rise larger than twice the 5-bar ATR; sell a fall that large.", '{"length": (5, 2, 20, 1), "mult": (2.0, 1.0, 4.0, 0.5)}', "own", f"""
move, band = ta.change({C}), p["mult"] * ta.atr({H}, {L}, {C}, p["length"])
return {{"buy": move > band, "sell": -move > band, "band": band}}"""),
    _classic("Classic: pivot reversal", "Buy when a pivot low is confirmed (4 bars left, 2 right); sell on a confirmed pivot high.", '{"left": (4, 2, 10, 1), "right": (2, 1, 5, 1)}', "main", f"""
low_pivot, high_pivot = ta.pivotlow({L}, p["left"], p["right"]), ta.pivothigh({H}, p["left"], p["right"])
return {{"buy": np.isfinite(low_pivot), "sell": np.isfinite(high_pivot)}}"""),
]


def list_python_templates() -> list[dict]:
    return [{"name": template["name"], "rule": template["rule"], "spec": template["spec"],
             "symbols": _universe(template["spec"]["code"]) or (["SPY", "QQQ"] if template["name"] == "Python pairs" else ["SPY", "QQQ", "IWM"])}
            for template in PYTHON_TEMPLATES + CLASSICS]


def _universe(code: str) -> list[str] | None:
    from . import pycode
    found = pycode.universe_attribute(code)
    return found if isinstance(found, list) else None


# --- gallery stats (B-97): each starter's backtest on its default universe, computed once per data version off the request path ---

_stats_running = threading.Event()


def stats() -> dict:
    from . import data, store
    key = f"template_stats:v2:{data.data_version()}"  # v2 adds the equity spark
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
                             "start": str(prep.panel.dates[0].date()), "end": str(prep.panel.dates[-1].date()), "symbols": len(prep.panel.symbols),
                             "spark": [round(float(x), 4) for x in (eq / eq[0])[:: max(1, len(eq) // 60)]]}
            except Exception as exc:  # noqa: BLE001 one broken starter must not hide the others
                out[name] = {"error": str(exc)[:200]}
        store.kv_set(key, out)
    finally:
        _stats_running.clear()
