/** Docs recipes (B-36); each one runs on the engine as written. */
export const RECIPES: [string, string][] = [
  [
    "Rotate monthly into the top 2 by 6-month return",
    "class Strategy:\n    universe = [\"SPY\", \"QQQ\", \"IWM\", \"EFA\", \"TLT\"]\n    warmup = 126\n    rebalance_schedule = \"month_start\"\n\n    def on_data(self, ctx):\n        if not ctx.rebalancing:\n            return\n        top = [symbol for symbol, _ in ctx.rank(\"roc(close, 126)\", top=2)]\n        ctx.target_weights({symbol: 0.5 if symbol in top else 0 for symbol in ctx.symbols}, corridor=0.05)\n"
  ],
  [
    "Bracket entry: 5% stop, 15% target, 8% trail",
    "class Strategy:\n    universe = [\"SPY\"]\n\n    def on_data(self, ctx):\n        if ctx.value(\"crosses_above(sma(close, 50), sma(close, 200))\", \"SPY\"):\n            ctx.bracket(\"SPY\", 100, stop=0.05, target=0.15, trail=0.08)\n"
  ],
  [
    "Plot an indicator under the price",
    "class Strategy:\n    def on_bar(self, ctx):\n        ctx.plot(\"rsi\", ctx.value(\"rsi(close, 14)\"))\n        ctx.plot(\"sma 50\", ctx.value(\"sma(close, 50)\"), chart=\"main\")\n"
  ],
  [
    "Guard: assert no short position",
    "class Strategy:\n    def on_bar(self, ctx):\n        if ctx.position == 0 and ctx.value(\"close > sma(close, 200)\"):\n            ctx.buy()\n        elif ctx.position > 0 and ctx.value(\"close < sma(close, 200)\"):\n            ctx.sell()\n        ctx.assert_invariant(ctx.position >= 0, \"no short position\")\n"
  ],
  [
    "Log the reason for each trade",
    "class Strategy:\n    def on_bar(self, ctx):\n        rsi = ctx.value(\"rsi(close, 2)\")\n        if ctx.position == 0 and rsi < 10:\n            ctx.log(f\"buy: RSI(2) {rsi:.1f}\")\n            ctx.buy()\n        elif ctx.position > 0 and rsi > 70:\n            ctx.log(f\"sell: RSI(2) {rsi:.1f}\")\n            ctx.sell()\n"
  ]
];
