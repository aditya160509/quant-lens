"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { API_BASE_URL } from "@/lib/api";

const BASE = `${API_BASE_URL}/labs/research/v2`;

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.detail || `Request failed (${res.status})`);
  return body;
}

export function useResearchManifest() {
  return useQuery({
    queryKey: ["research-v2", "manifest"],
    queryFn: () => request("/features"),
    staleTime: Infinity,
    select: (data) => data.features,
  });
}

export function useFeature(featureId) {
  const manifest = useResearchManifest();
  const id = String(featureId).padStart(2, "0");
  return { ...manifest, data: manifest.data?.find((f) => f.id === id) };
}

export function searchSymbols(q) {
  return request(`/symbols?q=${encodeURIComponent(q)}&limit=12`).then((d) => d.results);
}

export function uploadFile(kind, file) {
  const form = new FormData();
  form.append("file", file);
  return request(`/uploads?kind=${kind}`, { method: "POST", body: form });
}

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

/** Submit a study as a background job and poll it until it finishes. */
export function useResearchJob(featureId) {
  const [jobId, setJobId] = useState(null);
  const [startedAt, setStartedAt] = useState(null);
  const submit = useMutation({
    mutationFn: (payload) => request(`/feature/${featureId}/jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ payload }) }),
    onSuccess: (job) => { setJobId(job.job_id); setStartedAt(Date.now()); },
  });
  const job = useQuery({
    queryKey: ["research-v2", "job", jobId],
    queryFn: () => request(`/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => (TERMINAL.has(query.state.data?.status) ? false : 1200),
  });
  const cancel = useMutation({ mutationFn: () => request(`/jobs/${jobId}/cancel`, { method: "POST" }), onSuccess: () => job.refetch() });
  const status = submit.isPending ? "submitting" : job.data?.status ?? (submit.isError ? "failed" : "idle");
  return {
    run: (payload) => submit.mutate(payload),
    cancel: () => cancel.mutate(),
    status,
    startedAt,
    result: job.data?.status === "completed" ? job.data.result : null,
    error: submit.error?.message || job.error?.message || job.data?.error || null,
  };
}
