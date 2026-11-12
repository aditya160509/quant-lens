"use client";

import toast from "react-hot-toast";
import { API_BASE_URL } from "@/lib/apiBase";
import { download } from "@/charts/export";

// Device-kept preferences that travel together. Run history and chart notes stay on the device.
const KEYS = ["ws-prefs", "ws-layout", "ws-views", "table-views", "research-table-settings", "research-card-prefs", "lab-card-lens", "research-explore", "research-presets",
  "research-user-defaults", "research-form-level", "research-pins", "screener-watchlists", "screener-filter-picks", "screener-auto-run", "screener-filters-hidden", "screener-spark-days", "quicklook-ratios-hidden"];
const URL = `${API_BASE_URL}/screener-v2/preferences`;

function collect(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const k of KEYS) { try { const v = localStorage.getItem(k); if (v !== null) out[k] = v; } catch { /* storage blocked */ } }
  return out;
}

// Applying needs a reload: every store reads its saved state once at start.
function apply(blob: Record<string, unknown>) {
  const keys = Object.keys(blob).filter((k) => KEYS.includes(k) && typeof blob[k] === "string");
  if (!keys.length) { toast.error("No preferences in that file"); return; }
  try { keys.forEach((k) => localStorage.setItem(k, blob[k] as string)); } catch { toast.error("This browser blocks storage"); return; }
  window.location.reload();
}

export const exportPrefs = () => download("atlas-preferences.json", new Blob([JSON.stringify(collect(), null, 2)], { type: "application/json" }));

export function importPrefs() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "application/json,.json";
  input.onchange = () => { void input.files?.[0]?.text().then((t) => apply(JSON.parse(t) as Record<string, unknown>)).catch(() => toast.error("That file is not a preferences export")); };
  input.click();
}

export async function pushPrefs() {
  const res = await fetch(URL, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collect()) });
  if (res.ok) toast.success("Preferences saved to the server");
  else toast.error(`Could not save preferences (${res.status})`);
}

export async function pullPrefs() {
  const res = await fetch(URL);
  const body = res.ok ? ((await res.json()) as { preferences: Record<string, unknown>; saved: number | null }) : null;
  if (!body?.saved) { toast.error(res.ok ? "No preferences saved on the server yet" : `Could not load preferences (${res.status})`); return; }
  apply(body.preferences);
}
