"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { SERIES } from "@/charts/core";
import { TimeSeries } from "@/charts/TimeSeries";
import { DataTable } from "@/kit/DataTable";
import { studio } from "../api";

type Compared = {
  ids: string[]; dates: string[]; equity: Record<string, number[]>;
  metrics: { id: string; name: string; total_return: number; cagr: number; sharpe: number | null; max_drawdown: number; trades: number }[];
  correlation: { ids: string[]; matrix: number[][] }; diffs: { id: string; name: string; diff: string }[];
};

/** Two to six strategies side by side: growth of 1, the headline metrics, how their returns move together, and how each spec differs from the first. */
export function CompareDialog({ ids, onClose, onCombine }: { ids: string[]; onClose: () => void; onCombine: (ids: string[]) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const router = useRouter();
  useEffect(() => { ref.current?.showModal(); }, []);
  const q = useQuery({ queryKey: ["studio", "compare", ids], queryFn: () => studio<Compared>("POST", "/compare", { ids }), retry: false });
  const d = q.data;
  const name = (id: string) => d?.metrics.find((m) => m.id === id)?.name ?? id;
  const rows = d ? d.dates.map((date, i) => ({ date, ...Object.fromEntries(d.ids.map((id) => [id, d.equity[id][i]])) })) : [];

  return (
    <dialog ref={ref} className="sh-compare" aria-label="Compare strategies" onClose={onClose} onClick={(e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
      <div className="sh-compare-head">
        <b>Compare {ids.length} strategies</b>
        <button className="btn sm" onClick={() => { onCombine(ids); router.push("/studio/portfolio"); }}>Combine in Portfolio</button>
        <button className="btn sm ghost" onClick={() => ref.current?.close()}>Close</button>
      </div>
      {q.isLoading ? <p className="sh-trash-empty">Loading…</p> : q.error ? <p className="sh-find" role="alert"><b className="error">error</b>{(q.error as Error).message}</p> : d ? (
        <div className="sh-compare-body">
          <section><h3>Growth of 1</h3>
            <TimeSeries data={rows} series={d.ids.map((id, i) => ({ key: id, label: name(id), color: SERIES[i % SERIES.length] }))} height={260} refLines={[{ y: 1, label: "" }]} format={(v) => `${v.toFixed(2)}×`} directLabels />
          </section>
          <section><h3>Metrics</h3>
            <DataTable rows={d.metrics.map(({ id: _, ...m }) => ({ strategy: m.name, total_return: m.total_return, cagr: m.cagr, sharpe: m.sharpe, max_drawdown: m.max_drawdown, trades: m.trades }))} />
          </section>
          <section><h3>Correlation of returns</h3>
            <DataTable rows={d.correlation.ids.map((id, i) => ({ strategy: name(id), ...Object.fromEntries(d.correlation.ids.map((jd, j) => [`${name(jd)} correlation`, d.correlation.matrix[i][j]])) }))} />
          </section>
          {d.diffs.length ? <section><h3>Spec against {name(d.ids[0])}</h3>
            {d.diffs.map((x) => <details key={x.id}><summary>{x.name}</summary><pre className="bd-code">{x.diff || "No differences"}</pre></details>)}
          </section> : null}
        </div>
      ) : null}
    </dialog>
  );
}
