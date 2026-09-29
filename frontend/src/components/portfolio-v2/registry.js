export const PORTFOLIO_V2_FEATURES = [
  f(
    "01",
    "Portfolio Construction Engine",
    "Optimize allocation across Sharpe, minimum variance, CVaR, Black-Litterman and risk-budget objectives.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM,TLT,GLD",
      objective: "max_sharpe",
      covariance_estimator: "ledoit_wolf",
      lookback_days: 1260,
    },
  ),
  f(
    "02",
    "Honest Backtesting Engine",
    "Audit performance with walk-forward validation, costs, PBO, DSR, drawdowns and risk-method comparisons.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM",
      rebalance_frequency: "monthly",
      lookback_days: 2520,
      transaction_cost_bps: 5,
      var_confidence: 0.95,
    },
  ),
  f(
    "03",
    "Performance Attribution Engine",
    "Explain active return, factor risk, drawdowns, Brinson effects and skill-versus-luck evidence.",
    { assets: "SPY,QQQ,IWM,EFA,EEM", benchmark: "SPY", lookback_days: 1260 },
  ),
  f(
    "04",
    "Portfolio Stress Testing Engine",
    "Run historical, parametric, reverse and Monte Carlo stress scenarios with correlation breakdown.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM,TLT,GLD",
      loss_threshold: 0.15,
      simulations: 20000,
      lookback_days: 1260,
    },
  ),
  f(
    "05",
    "Market-Implied Macro Factor Model",
    "Measure macro betas, unintended exposures, factor crowding and marginal contribution to tracking error.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM,TLT,GLD",
      lookback_days: 1260,
      rolling_window: 252,
    },
  ),
  f(
    "06",
    "Regime-Aware Allocation Engine",
    "Detect market regimes and translate transition probabilities into conditional allocation and risk controls.",
    { assets: "SPY,QQQ,IWM,EFA,EEM", regimes: 4, lookback_days: 1260 },
  ),
  f(
    "07",
    "Liquidity Analytics Engine",
    "Estimate days-to-liquidate, liquidity VaR, crisis costs and executable liquidation schedules.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM",
      aum: 100000000,
      participation_rate: 0.1,
      lookback_days: 756,
    },
  ),
  f(
    "08",
    "Diversification and Contagion Engine",
    "Map correlation structure, effective bets, crisis deltas, minimum spanning trees and contagion networks.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM,TLT,GLD",
      lookback_days: 1260,
      correlation_threshold: 0.6,
    },
  ),
  f(
    "09",
    "Alpha Decay and Half-Life Engine",
    "Estimate IC decay, factor half-life, crowding, capacity and optimal rebalance frequency.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM",
      factor_taxonomy: "mechanical",
      lookback_days: 1260,
    },
  ),
  f(
    "10",
    "Growth-Optimal Capital Allocation",
    "Compare constrained Kelly, Markowitz and turnover-aware sizing under ruin and drawdown limits.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM",
      kelly_fraction: 0.5,
      drawdown_limit: 0.2,
      lookback_days: 1260,
    },
  ),
  f(
    "11",
    "Optimal Execution and Transaction Cost Engine",
    "Design multi-asset schedules with implementation shortfall, Almgren-Chriss and signal-decay urgency.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM",
      aum: 100000000,
      time_horizon: 5,
      participation_rate: 0.1,
    },
  ),
  f(
    "12",
    "Systemic Risk and Fire-Sale Contagion",
    "Measure portfolio overlap, DebtRank, liquidation spirals and overlap-reducing reallocations.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM",
      liquidation_fraction: 0.2,
      leverage: 2,
      lookback_days: 1260,
    },
  ),
  f(
    "13",
    "Multi-Strategy Allocation and Risk Budgeting",
    "Allocate across strategy sleeves with Kelly, Sharpe momentum, capacity, netting and kill switches.",
    {
      assets: "SPY,QQQ,IWM,EFA,EEM",
      kill_switch_drawdown: 0.15,
      lookback_days: 1260,
    },
  ),
];

function f(id, title, description, defaults) {
  return {
    id,
    slug: `feature-${id}`,
    title,
    shortTitle: title.replace(" Engine", ""),
    description,
    defaults,
    fields: Object.entries(defaults).map(([key, value]) => ({
      key,
      label: titleize(key),
      type:
        typeof value === "number"
          ? "number"
          : key === "assets"
            ? "tickers"
            : "text",
    })),
  };
}

export function titleize(value) {
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
}
export function getPortfolioV2Feature(id) {
  const key = String(id)
    .replace(/feature[-_]?/i, "")
    .padStart(2, "0");
  const hit = PORTFOLIO_V2_FEATURES.find((x) => x.id === key);
  if (!hit) throw new Error(`Unknown Portfolio V2 feature ${id}`);
  return hit;
}
