"use client";

import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { API_BASE_URL } from "@/lib/apiBase";
import type { FeatureResult, FeatureSpec, Job, RunLogEntry, RunRecord } from "./types";

const BASE = `${API_BASE_URL}/labs/research/v2`;

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (body as { detail?: unknown }).detail;
    throw new ApiError(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return body as T;
}

export function useManifest() {
  return useQuery({
    queryKey: ["research", "manifest"],
    queryFn: () => request<{ features: FeatureSpec[] }>("/features").then((d) => d.features),
    staleTime: Infinity,
  });
}

export function searchSymbols(q: string) {
  return request<{ results: { ticker: string; sector?: string | null }[] }>(`/symbols?q=${encodeURIComponent(q)}&limit=12`).then((d) => d.results);
}

export type UniverseSymbol = { ticker: string; sector: string | null; rank: number };

/** Every US common equity with its sector, in data-coverage order. Fetched once per session. */
export function useUniverse(enabled = true) {
  return useQuery({
    queryKey: ["research", "universe"],
    queryFn: () => request<{ symbols: UniverseSymbol[] }>("/universe").then((d) => d.symbols),
    staleTime: Infinity,
    enabled,
  });
}

export function uploadFile(kind: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ upload_id: string; rows: number; columns: string[] }>(`/uploads?kind=${kind}`, { method: "POST", body: form });
}

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

/** Headline numbers of a finished run, by summary-card label. */
export const metricsOf = (result: FeatureResult): Record<string, number> =>
  Object.fromEntries((result.summary_cards ?? []).filter((c) => typeof c.value === "number" && Number.isFinite(c.value)).map((c) => [c.label, c.value as number]));

/** Polls every unfinished run except the one on screen, so sweeps and background jobs complete in the dock. */
export function useBackgroundRuns(features: FeatureSpec[] | undefined, activeJob: string | null, verdict: (f: FeatureSpec, r: FeatureResult) => { headline: string | null; tone: RunRecord["tone"] | null }) {
  const pending = useRuns((s) => s.runs.filter((r) => (r.status === "queued" || r.status === "running") && r.jobId !== activeJob).map((r) => r.jobId).join(","));
  const ids = pending ? pending.split(",") : [];
  const queries = useQueries({
    queries: ids.map((id) => ({ queryKey: ["research", "job", id], queryFn: () => request<Job>(`/jobs/${id}`), refetchInterval: 1500, retry: 1 })),
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
    queryKey: ["research", "job", jobId],
    queryFn: () => request<Job>(`/jobs/${jobId}`),
    enabled: Boolean(jobId),
    staleTime: (q) => (TERMINAL.has(q.state.data?.status ?? "") ? Infinity : 0),
    refetchInterval: (q) => (TERMINAL.has(q.state.data?.status ?? "") ? false : 1000),
    retry: (count, err) => !(err instanceof ApiError) && count < 2,
  });
}

export function useSubmitJob(featureId: string) {
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      request<{ job_id: string; status: Job["status"] }>(`/feature/${featureId}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload }),
      }),
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
