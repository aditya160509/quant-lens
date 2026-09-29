export type StudioStatus = "idle" | "loading" | "success" | "error";

export type StudioRequestStatus = StudioStatus | "cancelled";

export interface StudioError {
  message: string;
  status?: number;
  code?: string;
  requestId?: string;
  retryable?: boolean;
  details?: unknown;
}

export interface StudioRequestState<T = unknown> {
  status: StudioRequestStatus;
  data: T | null;
  error: StudioError | null;
  startedAt?: number;
  completedAt?: number;
  requestId?: string;
}

export interface AlgorithmCell {
  id: string;
  title: string;
  code: string;
  language?: "python";
  dirty?: boolean;
  updatedAt?: string;
  cursor?: { line: number; column: number };
}

export interface KernelVariable {
  name: string;
  type: string;
  preview: string;
  value?: unknown;
  size?: number;
}

export interface LintDiagnostic {
  line: number;
  column?: number;
  severity: "error" | "warning" | "info";
  message: string;
  rule?: string;
}

export interface ExecutionResult {
  status?: string;
  output?: string;
  stdout?: string;
  stderr?: string;
  variables?: Record<string, unknown>;
  metrics?: Record<string, number>;
  error?: StudioError | string | null;
  run_id?: string;
  duration_ms?: number;
  execution_time_ms?: number;
  [key: string]: unknown;
}

export interface StudioRunRecord {
  id: string;
  label: string;
  status: "running" | "completed" | "failed";
  createdAt: string;
  durationMs?: number;
  metrics?: Record<string, number | string>;
  message?: string;
}

export interface PaperTradingStatus {
  name: string;
  status: string;
  nav?: number;
  positions?: Array<Record<string, unknown>>;
  updatedAt?: string;
  [key: string]: unknown;
}

export interface AlgorithmLabSnapshot {
  sessionId: string;
  activeCellId: string;
  cells: AlgorithmCell[];
  diagnostics: LintDiagnostic[];
  variables: Record<string, KernelVariable | unknown>;
  output: ExecutionResult | null;
  executionStatus: StudioRequestStatus;
  runHistory: StudioRunRecord[];
  paperStatus: PaperTradingStatus | null;
}
