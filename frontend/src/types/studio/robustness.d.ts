export interface RobustnessRequest {
  test?: string;
  mode?: string;
  strategy_file?: string;
  trade_log?: Array<Record<string, unknown>>;
  tickers?: string[];
  n_simulations?: number;
  [key: string]: unknown;
}

export interface RobustnessResult {
  status?: string;
  warning?: string;
  sensitivity_score?: number;
  stability_score?: number;
  baseline_sharpe?: number;
  by_magnitude?: Record<string, Array<Record<string, unknown>>>;
  by_dropout?: Record<string, Array<Record<string, unknown>>>;
  [key: string]: unknown;
}

export interface RobustnessState {
  request: RobustnessRequest;
  result: RobustnessResult | null;
  isRunning: boolean;
  error: import("./algorithm-lab").StudioError | null;
  updatedAt: number | null;
}
