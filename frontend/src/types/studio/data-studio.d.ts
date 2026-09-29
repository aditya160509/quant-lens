export interface UniverseFilter {
  field: string;
  operator: string;
  value: string | number | boolean;
}

export interface DataSeriesPoint {
  date: string;
  value: number;
  [key: string]: unknown;
}

export interface DataCatalogItem {
  id: string;
  name: string;
  source?: string;
  updatedAt?: string;
  rows?: number;
  status?: string;
  [key: string]: unknown;
}

export interface DataSeriesResponse {
  ticker?: string;
  series?: DataSeriesPoint[];
  data?: DataSeriesPoint[];
  [key: string]: unknown;
}

export interface DataStudioState {
  ticker: string;
  request: Record<string, unknown>;
  series: DataSeriesResponse | null;
  universe: Record<string, unknown> | null;
  catalog: DataCatalogItem[] | Record<string, unknown> | null;
  error: import("./algorithm-lab").StudioError | null;
  updatedAt: number | null;
}
