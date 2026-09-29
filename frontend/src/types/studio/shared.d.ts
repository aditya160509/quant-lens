export interface StudioQuery {
  [key: string]: string | number | boolean | null | undefined;
}

export interface StudioRequestOptions extends RequestInit {
  key?: string;
  timeoutMs?: number;
  retries?: number;
  retryDelayMs?: number;
  cacheTtlMs?: number;
  query?: StudioQuery;
  signal?: AbortSignal;
}

export interface StudioApiState {
  status: import("./algorithm-lab").StudioRequestStatus;
  isLoading: boolean;
  error: import("./algorithm-lab").StudioError | null;
  errors: Record<string, import("./algorithm-lab").StudioError | null>;
}
