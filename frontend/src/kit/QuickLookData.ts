"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { API_BASE_URL } from "@/lib/apiBase";

const BASE = `${API_BASE_URL}/screener-v2`;

export type Point = { date: string; close: number };
export type Stat = { key: string; label: string; group: string; unit: "pct" | "x"; value: number | null; sector_percentile: number | null; sector_median: number | null; sector_n: number; own_history_percentile: number | null };
export type Note = { text: string; metric: string };
export type Lookup = {
  ticker: string; company_name: string | null; type: string; exchange: string; sector: string | null; industry: string | null; currency: string | null;
  price: number | null; market_cap: number | null; market_cap_currency: string | null; price_date: string; as_of: string;
  chart: Record<string, Point[]>; scores: { key: string; label: string; value: number | null }[]; thesis: string; stats: Stat[];
  piotroski: { score: number | null; available: number; complete: boolean; checks: { key: string; label: string; passed: boolean | null }[] };
  altman: { z: number | null; z_double_prime: number | null; zone: "Safe" | "Grey" | "Distress" | null; history: { available_date: string; altman_z_score: number | null }[] };
  peers: { scope: string; scope_n: number; columns: string[]; rows: Record<string, unknown>[]; median: Record<string, number | null> };
  statements: Statements; notes: { pros: Note[]; cons: Note[]; red_flags: Note[] }; limits: string[];
};
export type Statements = { periods: string[]; lines: { key: string; label: string; values: (number | null)[] }[] };
export type Compare = { as_of: string; columns: string[]; rows: ({ ticker: string; company_name: string | null; sector: string | null } & Record<string, unknown>)[] };

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(((await res.json().catch(() => null)) as { detail?: string } | null)?.detail ?? `Request failed (${res.status})`);
  return res.json() as Promise<T>;
}

export const fetchLookup = (ticker: string) => get<Lookup>(`/lookup/${encodeURIComponent(ticker)}`);
export const useLookup = (ticker: string | null) => useQuery({ queryKey: ["lookup", ticker], queryFn: () => fetchLookup(ticker!), enabled: !!ticker, staleTime: 300_000, retry: false });
export const useStatements = (ticker: string, period: string, all: boolean) =>
  useQuery({ queryKey: ["lookup-statements", ticker, period, all], queryFn: () => get<Statements>(`/lookup/${encodeURIComponent(ticker)}/statements?period=${period}&all_lines=${all}`), enabled: all, staleTime: 300_000, retry: false });
export const useCompare = (tickers: string[]) =>
  useQuery({ queryKey: ["lookup-compare", tickers], queryFn: () => get<Compare>(`/lookup/compare?tickers=${tickers.join(",")}`), enabled: tickers.length >= 2, staleTime: 300_000, retry: false });
export type Bars = { ticker: string; bars: { time: string; open: number; high: number; low: number; close: number; volume: number | null }[] };
const barsQuery = (ticker: string, days: number) => ({ queryKey: ["lookup-bars", ticker, days], queryFn: () => get<Bars>(`/lookup/${encodeURIComponent(ticker)}/ohlcv?days=${days}`), staleTime: 300_000, retry: false });
export const useBars = (ticker: string, days: number) => useQuery(barsQuery(ticker, days));
export const useBarsMany = (tickers: string[], days: number) => useQueries({ queries: tickers.map((t) => barsQuery(t, days)) });
export type PeHistory = { series: { date: string; valuation_metric: number | null; history_percentile: number | null }[] };
export const usePeHistory = (ticker: string, days: number, on: boolean) => useQuery({ queryKey: ["lookup-pe", ticker, days], queryFn: () => get<PeHistory>(`/lookup/${encodeURIComponent(ticker)}/pe-history?days=${days}`), enabled: on, staleTime: 300_000, retry: false });
export const pdfUrl = (ticker: string) => `${BASE}/lookup/${encodeURIComponent(ticker)}/pdf`;

export type SymbolHit = { ticker: string; company_name: string | null; type: string; exchange: string; sector?: string | null };
export const searchSymbols = (q: string, exchange: string | null, signal?: AbortSignal) =>
  fetch(`${BASE}/symbols?q=${encodeURIComponent(q)}&limit=40${exchange ? `&exchange=${encodeURIComponent(exchange)}` : ""}`, { signal }).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`Search failed (${r.status})`)))) as Promise<{ total: number; results: SymbolHit[] }>;
export type Popular = { results: SymbolHit[]; exchanges: { name: string; count: number }[]; types: { name: string; count: number }[] };
export const usePopular = () => useQuery({ queryKey: ["lookup-popular"], queryFn: () => get<Popular>("/lookup/popular"), staleTime: 600_000, retry: false });
export type SavedScreen = { screen_id: string; name: string; feature_id: string };
export const useSavedScreens = () => useQuery({ queryKey: ["screens"], queryFn: () => get<{ screens: SavedScreen[] }>("/screens"), staleTime: 60_000, retry: false });
