"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";

const KEY = "research-onboarding-v1";
const STEPS = [
  { label: "Load momentum on the Signal page", href: "/research/signal" },
  { label: "Run the report card", href: "/research/report" },
  { label: "Open Robustness", href: "/research/signal" },
];
type State = { done: number[]; dismissed: boolean };

function load(): State {
  try { const v = JSON.parse(localStorage.getItem(KEY) ?? ""); if (v && Array.isArray(v.done)) return v; } catch { /* unavailable */ }
  return { done: [], dismissed: false };
}

/** Dismissible 60-second first run; progress persists on this device. */
export function Onboarding() {
  const [st, setSt] = useState<State | null>(null);
  useEffect(() => { setSt(load()); }, []);
  const save = (n: State) => { setSt(n); try { localStorage.setItem(KEY, JSON.stringify(n)); } catch { /* ignore */ } };
  if (!st || st.dismissed || st.done.length >= STEPS.length) return null;
  const toggle = (i: number) => save({ ...st, done: st.done.includes(i) ? st.done.filter((d) => d !== i) : [...st.done, i] });
  return (
    <div className="card" style={{ padding: 14, position: "relative" }} role="region" aria-label="Quick start">
      <button aria-label="Dismiss quick start" onClick={() => save({ ...st, dismissed: true })} style={{ position: "absolute", top: 10, right: 10 }}><X size={14} /></button>
      <div style={{ fontWeight: 600, marginBottom: 2 }}>Your first report in 60 seconds</div>
      <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 8 }}>{st.done.length} of {STEPS.length} done</div>
      <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
        {STEPS.map((s, i) => (
          <li key={s.label} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            <button aria-label={`Mark step ${i + 1} ${st.done.includes(i) ? "not done" : "done"}`} onClick={() => toggle(i)}
              style={{ width: 18, height: 18, borderRadius: 9, border: "1px solid var(--accent-line)", display: "grid", placeItems: "center", background: st.done.includes(i) ? "var(--accent)" : "transparent" }}>
              {st.done.includes(i) ? <Check size={11} /> : null}
            </button>
            <Link href={s.href} onClick={() => !st.done.includes(i) && toggle(i)} style={{ color: "var(--text)", textDecoration: st.done.includes(i) ? "line-through" : "none" }}>{i + 1}. {s.label}</Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
