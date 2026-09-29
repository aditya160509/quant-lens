export type StudioContractVersion = "1.0";
export type StudioJobStatus = "queued" | "running" | "cancelling" | "cancelled" | "succeeded" | "failed";
export type StudioValueStatus = "observed" | "estimated" | "unavailable";

export interface StudioWarning {
  code: string;
  message: string;
  field?: string | null;
}

export interface StudioDataQuality {
  status: "observed" | "partial" | "unavailable" | "synthetic";
  observations: number;
  missing_observations: number;
  source?: string | null;
  as_of?: string | null;
}

export interface StudioProvenance {
  engine_version: string;
  generated_at: string;
  code_hash?: string | null;
  dataset_id?: string | null;
  parameters: Record<string, unknown>;
}

export interface StudioMetricValue {
  value: number | null;
  unit: string;
  status: StudioValueStatus;
  sample_size: number;
  methodology: string;
}

export interface StudioResultMetadata {
  contract_version: StudioContractVersion;
  data_quality: StudioDataQuality;
  provenance: StudioProvenance;
  warnings: StudioWarning[];
  partial: boolean;
  synthetic: boolean;
}

export interface StudioErrorEnvelope {
  contract_version: StudioContractVersion;
  code: string;
  message: string;
  field_errors: Record<string, string>;
  retryable: boolean;
  request_id?: string | null;
  documentation_hint?: string | null;
  details: Record<string, unknown>;
}

export interface StudioArtifactRef {
  artifact_id: string;
  schema_version: string;
  content_hash: string;
  media_type: string;
}

export interface StudioArtifactManifest {
  contract_version: StudioContractVersion;
  manifest_id: string;
  owner_id: string;
  artifacts: StudioArtifactRef[];
  provenance: StudioProvenance;
  created_at: string;
}

export interface StudioRunRequest {
  contract_version: StudioContractVersion;
  project_id: string;
  dataset_id: string;
  strategy_version_id: string;
  parameters: Record<string, unknown>;
  idempotency_key: string;
}

export interface StudioRunResponse {
  contract_version: StudioContractVersion;
  run_id: string;
  status: StudioJobStatus;
  created_at: string;
  updated_at: string;
}

export interface StudioResultResponse {
  contract_version: StudioContractVersion;
  run_id: string;
  metrics: Record<string, StudioMetricValue>;
  artifacts: StudioArtifactRef[];
  metadata: StudioResultMetadata;
}
