/** Shapes of the Research V2 API (backend/app/api/research_v2.py). */

export type Row = Record<string, unknown>;

export type InputType = "select" | "multiselect" | "boolean" | "number" | "date" | "json" | "file" | "ticker" | "ticker_list" | "text" | "text_list";

export type InputSpec = {
  key: string;
  label: string;
  type: InputType;
  default?: unknown;
  group: string;
  help?: string;
  options?: (string | number)[];
  min?: number;
  max?: number;
  /** Rules from the API (docs/RESEARCH_V3_CONTRACTS.md §3); the form falls back to its own maps when absent. */
  required?: boolean;
  depends_on?: { field: string; values?: (string | number | boolean)[]; present?: boolean } | null;
  conflicts_with?: string[];
  unit?: string;
  level?: "quick" | "standard" | "expert";
  citation?: string;
};

export type OutputSpec = {
  key: string;
  title: string;
  source: "tables" | "charts" | "sections";
  render: string;
  description?: string;
  primary?: boolean;
  /** ML contract: column roles (x, y, series, value, bin) and availability. */
  encoding?: Record<string, unknown>;
  type?: string;
  status?: string;
};

export type FeatureSpec = {
  id: string;
  name: string;
  description: string;
  inputs: InputSpec[];
  outputs: OutputSpec[];
};

export type SummaryCard = { label: string; value: unknown };

export type FeatureResult = {
  feature_id: string;
  status: string;
  summary_cards?: SummaryCard[];
  charts: Record<string, unknown>;
  tables: Record<string, unknown>;
  /** Report blocks keyed by output (ML Validate). */
  sections?: Record<string, unknown>;
  meta: {
    research_caveats?: string[];
    config?: Record<string, unknown>;
    headline?: string;
    verdict?: "pass" | "fail" | "mixed";
    [key: string]: unknown;
  };
};

export type JobStatus = "idle" | "submitting" | "queued" | "running" | "completed" | "failed" | "cancelled";

export type Job = {
  job_id: string;
  type?: string;
  status: Exclude<JobStatus, "idle" | "submitting">;
  created_at?: string;
  updated_at?: string;
  progress?: number | string | { percent?: number; message?: string } | null;
  error?: string | null;
  result?: FeatureResult;
};

/** A run kept in local history so the dock and nav can show the latest verdict per feature. */
export type RunRecord = {
  jobId: string;
  featureId: string;
  featureName: string;
  startedAt: number;
  status: Job["status"];
  headline?: string;
  tone?: "up" | "down" | "warn";
  signal?: string;
  /** The exact settings submitted, so a past run can be restored into the form. */
  payload?: Record<string, unknown>;
  log?: RunLogEntry[];
  /** Set when the run is one value of a parameter sweep. */
  sweep?: { key: string; value: number; group: string };
  /** Numeric headline figures, kept so sweep runs can be compared without refetching. */
  metrics?: Record<string, number>;
};

export type RunLogEntry = { t: number; text: string; tone?: "up" | "down" | "warn" };
