"use client";

import { useQuery } from "@tanstack/react-query";
import { STUDIO_BASE } from "./base";

/** A request to the Studio API; a failed one throws the server's own message. */
export async function studio<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${STUDIO_BASE}${path}`, { method, signal, headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const json = (await res.json().catch(() => ({}))) as { detail?: unknown };
  if (!res.ok) { const d = json.detail as { reason?: string; message?: string } | undefined; throw Object.assign(new Error(typeof json.detail === "string" ? json.detail : d?.reason ?? d?.message ?? `Request failed (${res.status})`), { status: res.status, detail: json.detail }); }
  return json as T;
}

export type Ledger = { raw: number; effective: number; by_actor: Record<string, number>; unsaved?: boolean };
export type LastRun = { job_id: string; at: number; version: number; headline: string; total_return: number; sharpe: number | null; trades: number; spark: number[] };
export type StrategyCard = { id: string; name: string; folder: string; tags: string[]; archived: boolean; created: number; updated: number; version: number; has_draft: boolean; last_run: LastRun | null; trials: Ledger;
  status?: "Draft" | "Backtested" | "Validated" | "Paper" | "Live"; validation_expired?: boolean; trashed?: boolean; purge_at?: number; pinned?: boolean };
export type Freshness = { date: string; age_days: number; tone: "ok" | "amber" | "red"; label: string };
export type Attention = { kind: string; tone: string; text: string; strategy_id?: string; action: { label: string; href: string } };
export type RecentRun = { job_id: string; strategy_id: string | null; strategy: string | null; version: number | null; feature: string; at: number; headline: string; settings_changed?: boolean };
export type LiveRow = { id: string; name: string; status: string; paper_return: number | null; today_pnl: number | null; last_step: string | null };
export type Home = { strategies: StrategyCard[]; attention: Attention[]; recent_runs: RecentRun[]; freshness: Freshness; live?: { strategies: LiveRow[]; alerts: number; heartbeat: number | null };
  prefs?: { layout: "cards" | "table"; sort: string; columns: string[]; density: "comfortable" | "compact"; group_by: string; card_fields: string[]; pinned: string[] } };
export type Template = { name: string; rule: string; description: string; spec: Record<string, unknown> };
export type Finding = { severity: "error" | "warning"; role: string; line: number; start: number; end: number; token: string; message: string; lookahead?: boolean };
export type Compiled = { ok: boolean; findings: Finding[]; hash: string; description: string; ms?: number; complexity?: { parameter_count: number; formula_rule_count: number; degrees_of_freedom: number }; parameters?: Record<string, { value: number; min?: number | null; max?: number | null; step?: number | null }> };

export const useHome = () => useQuery({ queryKey: ["studio", "home"], queryFn: () => studio<Home>("GET", "/home"), retry: 1 });
const templatesQuery = { queryKey: ["studio", "templates"], queryFn: () => studio<{ templates: Template[]; python_templates: Template[] }>("GET", "/templates"), staleTime: Infinity };
export const useTemplates = () => useQuery({ ...templatesQuery, select: (d) => d.templates });
export const usePyTemplates = () => useQuery({ ...templatesQuery, select: (d) => d.python_templates });
export const useLimits = () => useQuery({ queryKey: ["studio", "limits"], queryFn: () => studio<{ freshness: Freshness; data: Record<string, unknown> }>("GET", "/limits"), staleTime: 300_000 });
