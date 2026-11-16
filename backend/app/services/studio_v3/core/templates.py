"""Twenty starter strategies, each a full spec with a one-line rule."""

from __future__ import annotations

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
