"use client";

import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { API_BASE_URL } from "@/lib/apiBase";
import { lab, owns } from "./lab";

/** Universe and symbol lookups read the shared market data, served by the Research API for every lab. */
const DATA_BASE = `${API_BASE_URL}/labs/research/v2`;
import type { FeatureResult, FeatureSpec, Job, RunLogEntry, RunRecord } from "./types";


export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit, base = lab().base): Promise<T> {
  const res = await fetch(`${base}${path}`, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (body as { detail?: unknown }).detail;
    throw new ApiError(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return body as T;
}

export function useManifest() {
  return useQuery({
    queryKey: [lab().id, "manifest"],
    queryFn: () => request<unknown>("/features").then((d) => lab().manifest(d)),
    staleTime: Infinity,
  });
}

export function searchSymbols(q: string) {
  return request<{ results: { ticker: string; sector?: string | null }[] }>(`/symbols?q=${encodeURIComponent(q)}&limit=12`, undefined, DATA_BASE).then((d) => d.results);
}

export type UniverseSymbol = { ticker: string; sector: string | null; rank: number };

/** Every US common equity with its sector, in data-coverage order. Fetched once per session. */
export function useUniverse(enabled = true) {
  return useQuery({
    queryKey: ["research", "universe"],
    queryFn: () => request<{ symbols: UniverseSymbol[] }>("/universe", undefined, DATA_BASE).then((d) => d.symbols),
    staleTime: Infinity,
    enabled,
  });
}

export type UploadInfo = { upload_id: string; rows: number; columns: string[]; date_range?: [string, string]; warnings?: string[]; nan_share?: Record<string, number> };

export function uploadFile(kind: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<UploadInfo>(`/uploads?kind=${kind}`, { method: "POST", body: form });
}

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

/** Headline numbers of a finished run, by summary-card label. */
export const metricsOf = (result: FeatureResult): Record<string, number> =>
  Object.fromEntries((result.summary_cards ?? []).filter((c) => typeof c.value === "number" && Number.isFinite(c.value)).map((c) => [c.label, c.value as number]));

/** Polls every unfinished run except the one on screen, so sweeps and background jobs complete in the dock. */
export function useBackgroundRuns(features: FeatureSpec[] | undefined, activeJob: string | null, verdict: (f: FeatureSpec, r: FeatureResult) => { headline: string | null; tone: RunRecord["tone"] | null }) {
  const pending = useRuns((s) => s.runs.filter((r) => (r.status === "queued" || r.status === "running") && r.jobId !== activeJob && owns(r.featureId)).map((r) => r.jobId).join(","));
  const ids = pending ? pending.split(",") : [];
  const queries = useQueries({
    queries: ids.map((id) => ({ queryKey: [lab().id, "job", id], queryFn: () => request<Job>(`/jobs/${id}`), refetchInterval: 1500, refetchIntervalInBackground: true, retry: 1 })),
  });
  const key = queries.map((q) => q.data?.status ?? "").join(",");
  useEffect(() => {
    const { runs, update, log } = useRuns.getState();
    queries.forEach((q, i) => {
      const data = q.data, rec = runs.find((r) => r.jobId === ids[i]);
      if (!data || !rec || data.status === rec.status) return;
      if (data.status === "completed" && data.result) {
        const f = features?.find((x) => x.id === rec.featureId);
        const v = f ? verdict(f, data.result) : { headline: null, tone: null };
        update(rec.jobId, { status: "completed", headline: v.headline ?? undefined, tone: v.tone ?? undefined, metrics: metricsOf(data.result) });
        log(rec.jobId, "Completed in the background", "up");
      } else {
        update(rec.jobId, { status: data.status });
        if (data.status === "failed") log(rec.jobId, `Failed: ${data.error ?? "unknown error"}`, "down");
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: [lab().id, "job", jobId],
    queryFn: () => request<Job>(`/jobs/${jobId}`),
    enabled: Boolean(jobId),
    staleTime: (q) => (TERMINAL.has(q.state.data?.status ?? "") ? Infinity : 0),
    refetchInterval: (q) => (TERMINAL.has(q.state.data?.status ?? "") ? false : 1000),
    // Keep polling in a background tab so a long study finishes while the reader is elsewhere.
    refetchIntervalInBackground: true,
    retry: (count, err) => !(err instanceof ApiError) && count < 2,
  });
}

export function useSubmitJob(featureId: string) {
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) => {
      const { path, body } = lab().submit(featureId, payload);
      return request<{ job_id: string; status: Job["status"] }>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    },
  });
}

export function cancelJob(jobId: string) {
  return request<{ status: string }>(`/jobs/${jobId}/cancel`, { method: "POST" });
}

type RunStore = {
  runs: RunRecord[];
  add: (run: RunRecord) => void;
  update: (jobId: string, patch: Partial<RunRecord>) => void;
  remove: (jobId: string) => void;
  log: (jobId: string, text: string, tone?: RunLogEntry["tone"]) => void;
};

/** Local run history: the dock lists it and the feature nav shows each feature's latest verdict. */
export const useRuns = create<RunStore>()(
  persist(
    (set) => ({
      runs: [],
      add: (run) => set((s) => ({ runs: [run, ...s.runs.filter((r) => r.jobId !== run.jobId)].slice(0, 60) })),
      update: (jobId, patch) => set((s) => ({ runs: s.runs.map((r) => (r.jobId === jobId ? { ...r, ...patch } : r)) })),
      remove: (jobId) => set((s) => ({ runs: s.runs.filter((r) => r.jobId !== jobId) })),
      log: (jobId, text, tone) => set((s) => ({ runs: s.runs.map((r) => (r.jobId === jobId ? { ...r, log: [...(r.log ?? []), { t: Date.now(), text, tone }].slice(-40) } : r)) })),
    }),
    { name: "research-runs", storage: createJSONStorage(() => localStorage), version: 1 },
  ),
);

export function latestRun(runs: RunRecord[], featureId: string) {
  return runs.find((r) => r.featureId === featureId && r.status === "completed");
}

// ---------------------------------------------------------------- signals, projects, reports (docs/RESEARCH_V3_CONTRACTS.md)

export type Operator = { name: string; args: string[]; doc: string; example: string; category: string };
export type Field = { name: string; source: string; doc: string; coverage: number };
export type LibrarySignal = { id: string; name: string; category: string; formula: string; citation: string; year?: number; expected_sign: 1 | -1 };
export type Preview = { n_names: number; months: number; histogram: { x0: number; x1: number; count: number }[]; coverage: { month: string; share: number }[]; corr_known: { name: string; corr: number }[] };
export type Validation = { ok: true; preview: Preview } | { ok: false; error: { message: string; start?: number; end?: number } };

const get = <T,>(path: string) => request<T>(path);
/** Lists arrive bare or wrapped ({ projects: [...] }, { matches: [...] }); accept both. */
const getList = <T,>(path: string) => request<unknown>(path).then((d) => (Array.isArray(d) ? d : Object.values((d ?? {}) as Record<string, unknown>).find(Array.isArray) ?? []) as T[]);
const post = <T,>(path: string, body: unknown) => request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const useOperators = () => useQuery({ queryKey: ["research", "ops"], queryFn: () => getList<Operator>("/signals/operators"), staleTime: Infinity, retry: false });
export const useFields = () => useQuery({ queryKey: ["research", "fields"], queryFn: () => getList<Field>("/signals/fields"), staleTime: Infinity, retry: false });
export const useLibrary = (enabled = true) => useQuery({ queryKey: ["research", "library"], queryFn: () => getList<LibrarySignal>("/signals/library"), staleTime: Infinity, retry: false, enabled });
export const validateExpr = (expr: string) => post<Validation>("/signals/validate", { expr });
export const combineExprs = (exprs: string[], method: string) => post<{ expr: string }>("/signals/combine", { exprs, method });
export const saveSignal = (name: string, expr: string, project_id?: string) => post<{ id: string; version: number }>("/signals/saved", { name, expr, project_id });
export const useSavedSignals = () => useQuery({ queryKey: ["research", "saved"], queryFn: () => getList<{ id: string; name: string; latest_version: number; updated_at: string }>("/signals/saved"), retry: false });
export const useSavedSignal = (id: string | null) => useQuery({ queryKey: ["research", "saved", id], queryFn: () => get<{ id: string; name: string; versions: { version: number; expr: string; created_at: string }[] }>(`/signals/saved/${id}`), enabled: Boolean(id), retry: false });
export const useLiterature = (expr: string | null) => useQuery({ queryKey: ["research", "lit", expr], queryFn: () => getList<{ library_id: string; name: string; corr: number }>(`/literature/match?expr=${encodeURIComponent(expr ?? "")}`), enabled: Boolean(expr), retry: false, staleTime: 60_000 });

export type Project = { id: string; name: string; description?: string; created_at: string };
export type Ledger = { trials: number; distinct_signals: number; deflated_sharpe_hurdle: number | null; haircut_sharpe?: { observed: number; haircut: number } | null; pbo?: number | null; entries: { job_id: string; feature_id: string; signal: string; t_stat: number | null; sharpe?: number | null; created_at: string }[] };
export const useProjects = () => useQuery({ queryKey: ["research", "projects"], queryFn: () => getList<Project>("/projects"), retry: false });
export const createProject = (name: string, description?: string) => post<Project>("/projects", { name, description });
export const useLedger = (projectId: string | null) => useQuery({ queryKey: ["research", "ledger", projectId], queryFn: () => get<Ledger>(`/projects/${projectId}/ledger`), enabled: Boolean(projectId), retry: false, refetchInterval: 15_000 });
export const useHoldout = (projectId: string | null) => useQuery({ queryKey: ["research", "holdout", projectId], queryFn: () => get<{ sealed_after: string | null; unsealed: boolean }>(`/projects/${projectId}/holdout`), enabled: Boolean(projectId), retry: false });
export const setHoldout = (projectId: string, body: { sealed_after?: string; unseal?: boolean }) => post<unknown>(`/projects/${projectId}/holdout`, body);
export const preregister = (body: { project_id: string; hypothesis: string; expected_sign: number; primary_test: string; signal: string }) => post<{ id: string }>("/preregistrations", body);
export const shareJob = (job_id: string) => post<{ token: string }>("/share", { job_id });

export type Universe = { id: string; label: string; region: string; asset_type: string; count: number };
export const useUniverses = () => useQuery({ queryKey: ["research", "universes"], queryFn: () => request<unknown>("/universes", undefined, DATA_BASE).then((d) => (Array.isArray(d) ? d : Object.values((d ?? {}) as Record<string, unknown>).find(Array.isArray) ?? []) as Universe[]), staleTime: 300_000, retry: false });

export type Grade = { dimension: string; grade: string; score: number; summary: string; metric?: { label: string; value: number | string } };
export type ReportCard = { grades: Grade[]; overall: { grade: string; score: number; verdict: string }; checklist: { id: string; question: string; pass: boolean | null; detail: string }[]; protocol: { name: string; steps: { id: string; label: string; pass: boolean | null; detail: string }[] }; explain: string[] };
export const submitReportCard = (payload: Record<string, unknown>) => post<{ job_id: string; status: Job["status"] }>("/report-card/jobs", { payload });
export const submitBatch = (signals: string[], payload: Record<string, unknown>) => post<{ job_id: string; status: Job["status"] }>("/batch/jobs", { signals, payload });
export const submitValidation = (payload: Record<string, unknown>, method: string, folds: number, embargo_days: number) => post<{ job_id: string; status: Job["status"] }>("/validation/jobs", { payload, method, folds, embargo_days });
export const reportUrl = (jobId: string, ext: "tex" | "pdf") => `${lab().base}/report/${jobId}.${ext}`;

/** The signal every study uses when set: a formula from the Signal page, applied as `signal_expr`. */
type ActiveSignal = { expr: string | null; name: string | null; projectId: string | null; set: (p: Partial<Omit<ActiveSignal, "set">>) => void };
export const useActiveSignal = create<ActiveSignal>()(persist((set) => ({ expr: null, name: null, projectId: null, set: (p) => set(p) }), { name: "research-active-signal", storage: createJSONStorage(() => localStorage) }));

/** A run's payload without the workspace-wide context (signal formula, project), for "settings changed" checks. */
export const studyPart = (p: Record<string, unknown> | undefined) => {
  if (!p) return p;
  const { signal_expr: _a, project_id: _b, ...rest } = p;
  void _a; void _b;
  // "12" and 12 are the same setting: compare numbers as numbers, keys in a fixed order.
  const norm = (v: unknown): unknown => (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v)) ? Number(v) : Array.isArray(v) ? v.map(norm) : v);
  return Object.fromEntries(Object.keys(rest).sort().map((k) => [k, norm(rest[k])]));
};
