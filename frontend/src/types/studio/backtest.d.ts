export interface BacktestConfig {
  strategy_source?: string;
  strategy_file?: string;
  universe_id?: string | string[];
  date_start?: string;
  date_end?: string;
  benchmark?: string;
  rebalance_freq?: string;
  position_sizing?: string;
  cost_model?: string;
  cost_bps?: number;
  initial_cash?: number;
  max_leverage?: number;
  max_fill_pct?: number;
  parameters?: Record<string, unknown>;
  fixed_cost_bps?: number;
  survivorship_bias?: boolean;
  margin_enabled?: boolean;
  hard_to_borrow_threshold?: number;
  corporate_actions?: Array<Record<string, unknown>>;
}

export interface BacktestResult {
  run_id?: string;
  result?: {
    daily_nav?: Record<string, number>;
    daily_returns?: Record<string, number>;
    trade_log?: Array<Record<string, unknown>>;
    positions_log?: Array<Record<string, unknown>>;
    orders_log?: Array<Record<string, unknown>>;
    warnings?: string[];
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface BacktestMetricSet {
  sharpe?: number;
  sortino?: number;
  max_drawdown?: number;
  annual_return?: number;
  calmar?: number;
  win_rate?: number;
  [key: string]: number | string | undefined;
}

export interface BacktestState {
  config: BacktestConfig;
  result: BacktestResult | null;
  metrics: BacktestMetricSet | null;
  isRunning: boolean;
  lastRunId: string | null;
  error: import("./algorithm-lab").StudioError | null;
  updatedAt: number | null;
}
