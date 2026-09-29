export interface FactorDefinition {
  id: string;
  name: string;
  expression?: string;
  category?: string;
  description?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface FactorEvaluation {
  factor?: FactorDefinition;
  ic?: number;
  rank_ic?: number;
  ic_ir?: number;
  turnover?: number;
  decay?: Array<{ lag: number; value: number }>;
  diagnostics?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface FactorLibraryResponse {
  factors?: FactorDefinition[];
  total?: number;
  [key: string]: unknown;
}

export interface FactorsState {
  request: Record<string, unknown>;
  result: FactorEvaluation | null;
  library: FactorLibraryResponse | null;
  isRunning: boolean;
  error: import("./algorithm-lab").StudioError | null;
  updatedAt: number | null;
}
