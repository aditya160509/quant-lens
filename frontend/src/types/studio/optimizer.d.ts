export interface SearchParameter {
  name: string;
  current_value?: number;
  suggested_range?: [number, number];
  distribution?: string;
  step?: number;
}

export interface OptimizerRequest {
  mode?: "bayesian" | "walk_forward" | "cpcv";
  parameters?: SearchParameter[];
  trial_budget?: number;
  objective?: string;
  [key: string]: unknown;
}

export interface OptimizerResult {
  trials?: Array<Record<string, unknown>>;
  best_trial?: Record<string, unknown>;
  verdict?: Record<string, unknown>;
  trajectory?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface OptimizerState {
  request: OptimizerRequest;
  result: OptimizerResult | null;
  isRunning: boolean;
  error: import("./algorithm-lab").StudioError | null;
  updatedAt: number | null;
}
