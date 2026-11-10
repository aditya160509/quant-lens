# Open-source check, all labs (2026-11-10)

Results from TinyFish searches of quant platforms like this one. None of these projects covers all seven labs, so the useful parts are per-lab ideas.

| Lab | Best reference | What to take |
|---|---|---|
| Factors | Alphalens (reloaded) | Factor tear sheet: IC by horizon, IC decay, quantile return spread, turnover, sector-neutral IC |
| ML | Qlib | Report pages: cumulative return by score group, rank IC over time, risk-analysis block, model-vs-benchmark |
| PCA | Qlib risk model, skfolio | Eigenvalue scree with Marchenko–Pastur edge, loading heatmap, factor-return lines |
| Portfolio | Riskfolio-Lib, skfolio, PyPortfolioOpt | Efficient frontier with chosen point, risk-contribution bars, HRP dendrogram, weights-over-time area |
| Volatility | Open vol-surface tools | 3D IV surface (moneyness × expiry), skew slices, term structure |
| Research / backtests | QuantStats, OpenStatz | Tear-sheet sections: rolling Sharpe and beta, worst drawdowns table, monthly heatmap, EOY bars |
| Studio / platform | QuantDinger (13k stars) | Separate API vs worker processes, durable jobs, strategy evolution with walk-forward, PBO, Deflated Sharpe, block-bootstrap Monte Carlo, cost-stress tests, MCP agent gateway |
| Shared UI | FINOS Perspective, Lightweight Charts v5 | Pivot grid for any result table; fast price/equity charts |

## Already done here
- Monthly heatmap, drawdown, distribution, attribution, and holdings timeline run on the shared `charts/` components.
- PBO, Deflated Sharpe, and walk-forward already exist on the backend.

## Gaps worth building
1. Alphalens-style IC decay and quantile-spread panels in Factors.
2. Risk-contribution bars and an HRP dendrogram in Portfolio.
3. A 3D IV surface in Volatility.
4. Rolling Sharpe and a worst-drawdowns table in every backtest tear sheet.
5. Block-bootstrap Monte Carlo and cost-stress panels, taken from the QuantDinger pattern.
