"use client";

import { Search, Star } from "lucide-react";
import { useMemo, useState } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { InputSpec } from "@/modules/research/types";

/** Metric prefix to the group it is listed under, in the order screeners show them. */
const GROUPS: [string, RegExp][] = [
  ["Market", /^(market_cap|price|dollar_volume|shares_outstanding|float_percent|amihud|enterprise_value)/],
  ["Valuation", /^(pe|forward_pe|pb|ps|p_cf|ev_|earnings_yield|fcf_yield|valuation)/],
  ["Profitability", /^(roe|roa|roic|gpa|gross_margin|operating_margin|net_margin|ebitda_margin|asset_turnover|quality)/],
  ["Growth", /^(revenue_growth|eps_growth|qtr_)/],
  ["Health", /^(interest_coverage|debt_|current_ratio|quick_ratio|cash_debt|accruals|ocf_net_income|altman|piotroski)/],
  ["Dividends", /^(dividend|payout)/],
  ["Performance", /^(return_|momentum|drawdown|high_proximity|prox52|max_factor|rel_return|worst_day|gap|up_days|down_days|above_52w_low)/],
  ["Technical", /^(rsi|macd|bollinger|adx|atr|stochastic|williams|obv|dist_sma|dist_ema|vratio|relative_volume|beta|ivol|realized_vol|yang_zhang)/],
  ["Score", /^(score|sector_score|.*_percentile)/],
];
const groupOf = (m: string) => GROUPS.find(([, re]) => re.test(m))?.[0] ?? "Other";

/** Recently used and starred filters, kept on this device. */
const usePicks = create<{ recent: string[]; stars: string[]; remember: (m: string) => void; star: (m: string) => void }>()(persist((set) => ({
  recent: [], stars: [],
  remember: (m) => set((s) => ({ recent: [m, ...s.recent.filter((x) => x !== m)].slice(0, 6) })),
  star: (m) => set((s) => ({ stars: s.stars.includes(m) ? s.stars.filter((x) => x !== m) : [...s.stars, m] })),
}), { name: "screener-filter-picks", storage: createJSONStorage(() => localStorage), version: 1 }));

/** Every range filter, searchable and grouped, with recent and starred at the top; picking one opens its editor. */
export function AddFilter({ fields, active, name, onPick }: { fields: InputSpec[]; active: Set<string>; name: (m: string) => string; onPick: (m: string) => void }) {
  const [q, setQ] = useState("");
  const { recent, stars, remember, star } = usePicks();
  const metrics = useMemo(() => [...new Set(fields.map((f) => f.key.replace(/_(min|max|top)$/, "")))], [fields]);
  const hit = (m: string) => !q || `${m} ${name(m)}`.toLowerCase().includes(q.toLowerCase());
  const pick = (m: string) => { remember(m); onPick(m); };
  const item = (m: string) => (
    <div key={m} className="af-item" data-on={active.has(m)}>
      <button type="button" className="af-name" onClick={() => pick(m)}>{name(m)}</button>
      <button type="button" className="af-star" aria-pressed={stars.includes(m)} aria-label={`Star ${name(m)}`} onClick={() => star(m)}><Star size={11} fill={stars.includes(m) ? "currentColor" : "none"} /></button>
    </div>
  );
  const groups = [["Starred", stars.filter((m) => metrics.includes(m))], ["Recent", recent.filter((m) => metrics.includes(m))], ...GROUPS.map(([g]) => [g, metrics.filter((m) => groupOf(m) === g)]), ["Other", metrics.filter((m) => groupOf(m) === "Other")]] as [string, string[]][];
  return (
    <div className="af">
      <label className="af-q"><Search size={13} aria-hidden /><input autoFocus placeholder="Search filters" aria-label="Search filters" value={q} onChange={(e) => setQ(e.target.value)} /></label>
      <div className="af-groups">
        {groups.map(([g, ms]) => { const shown = ms.filter(hit); return shown.length && !(q && (g === "Starred" || g === "Recent")) ? <section key={g}><h5>{g}</h5><div className="af-grid">{shown.map(item)}</div></section> : null; })}
      </div>
    </div>
  );
}
