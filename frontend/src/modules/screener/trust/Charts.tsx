"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { XYPlot, type XYPoint } from "@/charts/XYPlot";
import { Empty } from "@/kit/DataTable";
import { isNum, label, num } from "@/modules/research/format";
import { useStudies } from "@/modules/research/store";
import { defaultsFor } from "@/modules/research/StudyForm";
import type { FeatureResult, FeatureSpec, Row } from "@/modules/research/types";
import { send } from "../api";
import { runOf } from "./Explain";

/** Two metrics of the passing names; draw around a cluster and its bounds become filters. */
export function ScreenScatter({ rows, feature }: { rows: Row[]; feature: FeatureSpec }) {
  const keys = useQuery({ queryKey: ["screener", "filter-keys"], queryFn: () => send<Record<string, [string, string]>>("GET", "/filters/keys"), staleTime: Infinity });
  const usable = useMemo(() => Object.keys(keys.data ?? {}).filter((c) => rows.some((r) => isNum(r[c]))), [keys.data, rows]);
  const [x, setX] = useState("trailing_pe");
  const [y, setY] = useState("roe");
  const [picked, setPicked] = useState<XYPoint[]>([]);
  const xc = usable.includes(x) ? x : usable[0];
  const yc = usable.includes(y) ? y : usable[1] ?? usable[0];
  const points = useMemo(() => (xc && yc ? rows.filter((r) => isNum(r[xc]) && isNum(r[yc])).map((r) => ({ x: r[xc] as number, y: r[yc] as number, label: String(r.ticker ?? "") })) : []), [rows, xc, yc]);
  if (!xc || !yc) return <Empty text="No metric to plot." />;
  const apply = () => {
    const set: Record<string, string> = {};
    for (const [col, pick] of [[xc, (p: XYPoint) => p.x], [yc, (p: XYPoint) => p.y]] as const) {
      const [lo, hi] = keys.data![col];
      const v = picked.map(pick);
      set[lo] = String(Number(Math.min(...v).toPrecision(4)));
      set[hi] = String(Number(Math.max(...v).toPrecision(4)));
    }
    useStudies.setState((s) => ({ forms: { ...s.forms, [feature.id]: { ...defaultsFor(feature), ...s.forms[feature.id], ...set } } }));
  };
  const select = (value: string, set: (v: string) => void, name: string) => (
    <label className="xc"><span>{name}</span><select value={value} onChange={(e) => { set(e.target.value); setPicked([]); }}>{usable.map((c) => <option key={c} value={c}>{label(c)}</option>)}</select></label>
  );
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "end", flexWrap: "wrap" }}>
        {select(xc, setX, "X")}{select(yc, setY, "Y")}
        <button type="button" className="btn sm" disabled={!picked.length} onClick={apply}>Filter to {picked.length.toLocaleString()} selected</button>
      </div>
      <XYPlot points={points} xLabel={label(xc)} yLabel={label(yc)} height={320} robust onSelection={setPicked} />
    </div>
  );
}

type Sensitivity = { count: number; shifts: number[]; filters: { filter: string; label: string; side: "min" | "max"; threshold: number; counts: number[] }[] };

/** Names passing when each threshold moves, the others held; the filter that moves the count most is marked. */
export function SensitivityStrip({ result }: { result: FeatureResult }) {
  const runId = runOf(result)?.id;
  const res = useQuery({ queryKey: ["explain", "sensitivity", runId], queryFn: () => send<Sensitivity>("POST", "/explain/sensitivity", { run_id: runId }), enabled: Boolean(runId), retry: false });
  if (!runId) return <Empty text="No run record." />;
  if (res.error) return <div role="alert" style={{ color: "var(--down)", fontSize: 12 }}>{res.error.message}</div>;
  const d = res.data;
  if (!d) return <div aria-busy="true">Loading</div>;
  if (!d.filters.length) return <Empty text="No range filter set." />;
  const spread = (f: Sensitivity["filters"][number]) => Math.max(...f.counts, d.count) - Math.min(...f.counts, d.count);
  const worst = Math.max(...d.filters.map(spread));
  const half = d.shifts.findIndex((s) => s > 0);
  const cell = (n: number, i: number) => <td key={i} className="r num" style={{ color: n > d.count ? "var(--up)" : n < d.count ? "var(--down)" : undefined }}>{n.toLocaleString()}</td>;
  return (
    <table className="tbl">
      <thead><tr><th>Filter</th>{d.shifts.slice(0, half).map((s) => <th key={s} className="r">{Math.round(s * 100)}%</th>)}<th className="r">Now</th>{d.shifts.slice(half).map((s) => <th key={s} className="r">+{Math.round(s * 100)}%</th>)}<th /></tr></thead>
      <tbody>
        {d.filters.map((f) => (
          <tr key={f.filter}>
            <td className="strong">{f.label} {f.side === "min" ? "≥" : "≤"} {num(f.threshold, 3)}</td>
            {f.counts.slice(0, half).map(cell)}
            <td className="r num strong">{d.count.toLocaleString()}</td>
            {f.counts.slice(half).map(cell)}
            <td>{worst > 0 && spread(f) === worst ? <span className="chip warn">Most sensitive</span> : null}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
