"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { FeatureSpec } from "@/modules/research/types";
import { studio } from "../api";

type Row = { symbol: string; first: string | null; last: string | null; bars: number; gaps: number; missing: number; bad: number; dups: number; jumps: number; stale: number; strip: number[] };
type Listing = { symbols: Row[]; total: number; start: string | null; end: string | null };
type Issue = { kind: string; date: string; detail: string };
type Detail = Row & { issues: Issue[]; issues_total: number };
const PAGE = 100;
const FLAGS: [keyof Row, string][] = [["gaps", "Gaps"], ["bad", "Bad price"], ["dups", "Duplicates"], ["jumps", "Jumps"], ["stale", "Stale"]];

/** Data browser: coverage strip and quality flags per symbol in the market file. */
export default function DataPage(_: { features: FeatureSpec[] }) {
  const [q, setQ] = useState("");
  const [flagged, setFlagged] = useState(false);
  const [page, setPage] = useState(0);
  const [sel, setSel] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["studio", "data", q, flagged, page], queryFn: () => studio<Listing>("GET", `/data/symbols?q=${encodeURIComponent(q)}&flagged=${flagged}&offset=${page * PAGE}&limit=${PAGE}`), placeholderData: (p) => p, retry: 1 });
  const one = useQuery({ queryKey: ["studio", "data", "one", sel], enabled: !!sel, queryFn: () => studio<Detail>("GET", `/data/symbols/${sel}`) });
  const d = list.data;
  return (
    <div className="db">
      <header className="db-hd">
        <h1>Data</h1>
        <input aria-label="Search symbols" placeholder="Search" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
        <label><input type="checkbox" checked={flagged} onChange={(e) => { setFlagged(e.target.checked); setPage(0); }} />Flagged only</label>
        <span className="db-n">{d ? `${d.total.toLocaleString()} symbols${d.start ? ` · ${d.start} to ${d.end}` : ""}` : ""}</span>
      </header>
      {list.error ? <p className="dv-empty">{(list.error as Error).message}</p> : !d ? <p className="dv-empty">Loading</p> : !d.symbols.length ? <p className="dv-empty">No symbols</p> : (
        <div className="db-grid">
          <table className="db-tbl">
            <thead><tr><th>Symbol</th><th>Coverage</th><th>First</th><th>Last</th><th>Bars</th>{FLAGS.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead>
            <tbody>{d.symbols.map((r) => (
              <tr key={r.symbol} aria-selected={sel === r.symbol} onClick={() => setSel(r.symbol)}>
                <td><b>{r.symbol}</b></td>
                <td><Strip v={r.strip} /></td>
                <td>{r.first}</td><td>{r.last}</td><td>{r.bars.toLocaleString()}</td>
                {FLAGS.map(([k]) => <td key={k} className={r[k] ? "db-flag" : "db-zero"}>{r[k] as number}</td>)}
              </tr>
            ))}</tbody>
          </table>
          {sel ? (
            <aside className="db-side">
              <h2>{sel}<button className="btn sm ghost" onClick={() => setSel(null)}>Close</button></h2>
              {one.isLoading ? <p className="dv-empty">Loading</p> : one.data ? (
                one.data.issues.length ? <ul>{one.data.issues.map((i, n) => <li key={n}><b>{i.kind}</b><time>{i.date}</time><span>{i.detail}</span></li>)}</ul> : <p className="dv-empty">No issues</p>
              ) : <p className="dv-empty">{(one.error as Error | null)?.message}</p>}
              {one.data && one.data.issues_total > one.data.issues.length ? <p className="db-n">Showing {one.data.issues.length} of {one.data.issues_total}</p> : null}
            </aside>
          ) : null}
        </div>
      )}
      {d && d.total > PAGE ? (
        <footer className="db-pg">
          <button className="btn sm ghost" disabled={!page} onClick={() => setPage(page - 1)}>Prev</button>
          <span>{page * PAGE + 1} to {Math.min(d.total, (page + 1) * PAGE)}</span>
          <button className="btn sm ghost" disabled={(page + 1) * PAGE >= d.total} onClick={() => setPage(page + 1)}>Next</button>
        </footer>
      ) : null}
    </div>
  );
}

function Strip({ v }: { v: number[] }) {
  return <span className="db-strip" role="img" aria-label="Coverage over time">{v.map((x, i) => <i key={i} style={{ opacity: 0.08 + 0.72 * x }} className={x < 0.5 ? "db-low" : undefined} />)}</span>;
}
