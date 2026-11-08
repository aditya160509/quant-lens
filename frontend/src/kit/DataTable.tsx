"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";
import { getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import * as Popover from "@radix-ui/react-popover";
import { ArrowDown, ArrowUp, ChevronRight, Columns3, Pin, X } from "lucide-react";
import { Spark } from "@/charts/RankList";
import { columns, fmtKey, isNum, isPKey, isTKey, label, pTone, toneVar } from "@/modules/research/format";
import type { Row } from "@/modules/research/types";
import "@/modules/research/outputs/tables.css";

export function Empty({ text = "Nothing to show for this configuration." }: { text?: string }) {
  return <div style={{ padding: "22px 4px", color: "var(--text-3)", fontSize: 12.5 }}>{text}</div>;
}

export const FLAG_KEYS = ["fragile", "disagreement", "material_disagreement", "imbalanced", "near_duplicate", "discontinuity", "still_significant", "significant", "flag", "concentrated", "manipulation_detected", "winner", "forbidden_comparison"];
const POSITIVE_FLAGS = new Set(["still_significant", "winner"]);

export function FlagChip({ k, v }: { k: string; v: unknown }) {
  if (typeof v === "string" && ["red", "amber", "green"].includes(v)) {
    const tone = v === "red" ? "down" : v === "amber" ? "warn" : "up";
    return <span className={`chip ${tone}`}>{v === "red" ? "Flag" : v === "amber" ? "Watch" : "OK"}</span>;
  }
  if (typeof v !== "boolean") return <>{fmtKey(k, v)}</>;
  if (!v) return <span style={{ color: "var(--text-4)" }}>No</span>;
  return <span className={`chip ${POSITIVE_FLAGS.has(k) ? "up" : "warn"}`}>Yes</span>;
}

/** t-statistic with a small diverging bar and the ±1.96 critical marks. */
export function TBar({ t, width = 92 }: { t: number; width?: number }) {
  const lim = Math.max(4, Math.abs(t));
  const x = (v: number) => width / 2 + (v / lim) * (width / 2);
  const sig = Math.abs(t) >= 1.96;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <svg width={width} height={12} aria-hidden style={{ flex: "none" }}>
        <rect x={0} y={5} width={width} height={2} rx={1} fill="var(--grid)" />
        <line x1={x(-1.96)} x2={x(-1.96)} y1={2} y2={10} stroke="var(--line-3)" />
        <line x1={x(1.96)} x2={x(1.96)} y1={2} y2={10} stroke="var(--line-3)" />
        <rect x={Math.min(x(0), x(t))} y={3} width={Math.max(1.5, Math.abs(x(t) - x(0)))} height={6} rx={2} fill={sig ? (t > 0 ? "var(--up)" : "var(--down)") : "var(--text-3)"} fillOpacity={sig ? 0.9 : 0.6} />
      </svg>
      <span className="num" style={{ minWidth: 38, textAlign: "right", color: sig ? "var(--text)" : "var(--text-2)" }}>{t.toFixed(2)}</span>
    </span>
  );
}

// ---------------------------------------------------------------- data table

type SortState = { key: string; dir: 1 | -1 } | null;

/** Column groups from shared prefixes ("income_revenue", "income_ebit" -> "Income"). */
function groupCols(cols: string[]): { head: string | null; span: number; cols: string[] }[] {
  const pre = (c: string) => (c.includes("_") ? c.split("_")[0] : null);
  const count = new Map<string, number>();
  cols.forEach((c) => { const p = pre(c); if (p) count.set(p, (count.get(p) ?? 0) + 1); });
  const out: { head: string | null; span: number; cols: string[] }[] = [];
  cols.forEach((c) => {
    const p = pre(c);
    const head = p && (count.get(p) ?? 0) > 1 ? p : null;
    const last = out[out.length - 1];
    if (last && head && last.head === head) { last.span++; last.cols.push(c); } else out.push({ head, span: 1, cols: [c] });
  });
  return out;
}

const shortName = (c: string, head: string | null) => label(head && c.startsWith(`${head}_`) ? c.slice(head.length + 1) : c);

/** GitHub-style table text; pipes are escaped so a cell cannot add a column. */
export function toMarkdown(cols: string[], rows: Row[]): string {
  const cell = (v: unknown) => String(v ?? "").replace(/\|/g, "\\|").replace(/\s*\n\s*/g, " ");
  return [`| ${cols.map((c) => cell(label(c))).join(" | ")} |`, `|${cols.map(() => " --- ").join("|")}|`, ...rows.map((r) => `| ${cols.map((c) => cell(r[c])).join(" | ")} |`)].join("\n");
}

export function DataTable({ rows, opts }: { rows: Row[]; opts?: Record<string, unknown> }) {
  const hideOpt = opts?.hide as string[] | undefined;
  const order = opts?.columns as string[] | undefined;
  const groupKey = opts?.groupKey as string | undefined;
  const bars = opts?.bars as string[] | undefined;
  const base = useMemo(() => {
    const all = columns(rows).filter((c) => !(hideOpt ?? []).includes(c));
    return order ? [...order.filter((c) => all.includes(c)), ...all.filter((c) => !order.includes(c))] : all;
  }, [rows, hideOpt, order]);
  const [colOrder, setColOrder] = useState<string[] | null>(null);
  const [hidden, setHidden] = useState<string[]>([]);
  const [pinned, setPinned] = useState<string[]>([]);
  const [widths, setWidths] = useState<Record<string, number>>({});
  const [lefts, setLefts] = useState<Record<string, number>>({});
  const cols = useMemo(() => {
    const o = colOrder ? [...colOrder.filter((c) => base.includes(c)), ...base.filter((c) => !colOrder.includes(c))] : base;
    const shown = o.filter((c) => !hidden.includes(c));
    return [...shown.filter((c) => pinned.includes(c)), ...shown.filter((c) => !pinned.includes(c))];
  }, [base, colOrder, hidden, pinned]);
  const [sort, setSort] = useState<SortState>(null);
  const [tint, setTint] = useState(opts?.tint === true);
  const [density, setDensity] = useState<"compact" | "comfortable">("comfortable");
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [prev, setPrev] = useState<Row[]>(rows);
  const [flash, setFlash] = useState<Record<string, number>>({});
  if (prev !== rows) {
    const f: Record<string, number> = {};
    rows.forEach((r, i) => base.forEach((c) => { const a = prev[i]?.[c], b = r[c]; if (prev[i] && a !== b && isNum(b)) f[`${i}:${c}`] = isNum(a) ? b - a : 0; }));
    setPrev(rows);
    setFlash(f);
  }
  useEffect(() => {
    if (!Object.keys(flash).length) return;
    const id = setTimeout(() => setFlash({}), 600);
    return () => clearTimeout(id);
  }, [flash]);
  const definitions = useMemo<ColumnDef<Row>[]>(() => base.map((key) => ({
    id: key, accessorFn: (row) => row[key],
    sortingFn: (a, b) => {
      const x = a.original[key], y = b.original[key];
      return isNum(x) && isNum(y) ? x - y : String(x ?? "").localeCompare(String(y ?? ""));
    },
  })), [base]);
  const sorting = useMemo(() => sort ? [{ id: sort.key, desc: sort.dir === -1 }] : [], [sort]);
  const table = useReactTable({ data: rows, columns: definitions, autoResetPageIndex: false,
    state: { sorting },
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(),
  });
  const order2 = table.getRowModel().rows.map((row) => row.index);
  const max = Math.max(1, Math.floor(Number(opts?.max) || 400));
  const [page, setPage] = useState(0);
  const currentPage = Math.min(page, Math.max(0, Math.ceil(rows.length / max) - 1));
  const shown = order2.slice(currentPage * max, (currentPage + 1) * max);
  const scrollRef = useRef<HTMLDivElement>(null);
  const numeric = new Set(cols.filter((c) => rows.some((r) => isNum(r[c]))));
  const bound = useMemo(() => {
    const m: Record<string, number> = {};
    cols.forEach((c) => { if (numeric.has(c) && !isPKey(c)) m[c] = Math.max(1e-12, ...rows.map((r) => (isNum(r[c]) ? Math.abs(r[c]) : 0))); });
    return m;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, cols]);
  const headRow = useRef<HTMLTableRowElement>(null);
  // A pinned column sticks at the summed width of the pinned columns before it.
  useLayoutEffect(() => {
    const next: Record<string, number> = {};
    let x = 0;
    headRow.current?.querySelectorAll<HTMLElement>("th[data-col]").forEach((th) => {
      const c = th.dataset.col as string;
      if (!pinned.includes(c)) return;
      next[c] = x;
      x += th.getBoundingClientRect().width;
    });
    setLefts((prev) => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next));
  }, [pinned, widths, cols, rows]);
  const colStyle = (c: string, head = false): CSSProperties | undefined => {
    const style: CSSProperties = {};
    if (widths[c]) { style.width = widths[c]; style.minWidth = widths[c]; style.maxWidth = widths[c]; }
    if (pinned.includes(c)) { style.position = "sticky"; style.left = lefts[c] ?? 0; style.zIndex = head ? 4 : 2; style.background = "var(--panel)"; }
    return Object.keys(style).length ? style : undefined;
  };
  const startResize = (c: string, e: PointerEvent<HTMLSpanElement>) => {
    e.preventDefault();
    const th = e.currentTarget.parentElement as HTMLElement;
    const x0 = e.clientX, w0 = th.getBoundingClientRect().width;
    const move = (m: globalThis.PointerEvent) => setWidths((w) => ({ ...w, [c]: Math.max(48, Math.round(w0 + m.clientX - x0)) }));
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const groups = groupCols(cols);
  const twoLevel = groups.some((g) => g.head);
  const move = (c: string, d: number) => {
    const o = [...cols]; const i = o.indexOf(c); const j = i + d;
    if (j < 0 || j >= o.length) return;
    [o[i], o[j]] = [o[j], o[i]];
    setColOrder([...o, ...hidden]);
  };
  const cellStyle = (c: string, v: unknown) => {
    if (isPKey(c)) return { color: toneVar(pTone(v)) };
    if (tint && isNum(v) && bound[c]) {
      const a = Math.min(1, Math.abs(v) / bound[c]) * 0.28;
      return { background: `color-mix(in oklch, ${v >= 0 ? "var(--up)" : "var(--down)"} ${(a * 100).toFixed(0)}%, transparent)` };
    }
    return undefined;
  };
  const items: ({ kind: "group"; g: string; n: number } | { kind: "row"; i: number; sub: boolean })[] = [];
  if (groupKey) {
    const seen = new Map<string, number[]>();
    shown.forEach((i) => { const g = String(rows[i][groupKey] ?? "Other"); seen.set(g, [...(seen.get(g) ?? []), i]); });
    seen.forEach((ix, g) => { items.push({ kind: "group", g, n: ix.length }); if (!collapsed.includes(g)) ix.forEach((i) => items.push({ kind: "row", i, sub: true })); });
  } else shown.forEach((i) => items.push({ kind: "row", i, sub: false }));
  const virtual = items.length > 200;
  const virtualizer = useVirtualizer({ count: virtual ? items.length : 0,
    getScrollElement: () => scrollRef.current, estimateSize: () => density === "compact" ? 24 : 32,
    overscan: 8, initialRect: { width: 800, height: 440 },
  });
  const windowRows = virtual ? virtualizer.getVirtualItems() : [];
  const visibleItems = virtual ? windowRows.map((row) => ({ item: items[row.index], index: row.index })) : items.map((item, index) => ({ item, index }));
  const changePage = (next: number) => { setPage(next); setSel(null); if (scrollRef.current) scrollRef.current.scrollTop = 0; };
  if (!rows.length) return <Empty />;
  const render = (r: Row, i: number, c: string) => {
    const v = r[c];
    const d = flash[`${i}:${c}`];
    const content = bars?.includes(c) && isNum(v) ? <span className="pbar"><i style={{ width: `${Math.max(0, Math.min(100, v))}%` }} />{fmtKey(c, v)}</span> : Array.isArray(v) && v.length > 1 && v.every(isNum) ? <Spark values={v} /> : FLAG_KEYS.includes(c) ? <FlagChip k={c} v={v} /> : isTKey(c) && isNum(v) ? <TBar t={v} /> : fmtKey(c, v);
    return <>{content}{d ? <span className={`dl ${d > 0 ? "up" : "down"}`} aria-label={d > 0 ? "up" : "down"}>{d > 0 ? "▲" : "▼"}</span> : null}</>;
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (sel === null) return;
    if (e.key === "Escape") { setSel(null); return; }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const p = shown.indexOf(sel);
      const n = shown[Math.max(0, Math.min(shown.length - 1, p + (e.key === "ArrowDown" ? 1 : -1)))];
      if (n !== undefined) setSel(n);
    }
  };
  const sortTh = (c: string, text: string) => (
    <th key={c} data-col={c} style={colStyle(c, true)} className={`sortable${numeric.has(c) ? " r" : ""}`} aria-sort={sort?.key === c ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
      >
      <button className="dt-sort" onClick={() => { setPage(0); setSort((s) => (s?.key === c ? (s.dir === 1 ? { key: c, dir: -1 } : null) : { key: c, dir: 1 })); }}>
      {text}
      {sort?.key === c ? (sort.dir === 1 ? <ArrowUp size={10} style={{ marginLeft: 4, verticalAlign: -1 }} /> : <ArrowDown size={10} style={{ marginLeft: 4, verticalAlign: -1 }} />) : null}
      </button>
      <span className="dt-grip" role="separator" aria-label={`Resize ${text}`} onPointerDown={(e) => startResize(c, e)} />
    </th>
  );
  return (
    <div className="dt" data-virtual={virtual} data-density={density} onKeyDown={onKey}>
      <div className="dt-bar">
        <Popover.Root>
          <Popover.Trigger asChild><button className="btn sm ghost" aria-label="Table options"><Columns3 size={13} />Table</button></Popover.Trigger>
          <Popover.Portal container={typeof document === "undefined" ? undefined : document.querySelector<HTMLElement>(".ws")}>
            <Popover.Content className="tbl-pop" align="end" sideOffset={6} collisionPadding={12}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 2, paddingBottom: 6 }}>
        <button className="btn sm ghost" aria-pressed={tint} onClick={() => setTint(!tint)}>Heat tint</button>
                <button className="btn sm ghost" onClick={() => setDensity(density === "compact" ? "comfortable" : "compact")}>{density === "compact" ? "Comfortable" : "Compact"}</button>
                <button className="btn sm ghost" onClick={() => void navigator.clipboard?.writeText(toMarkdown(cols, order2.map((i) => rows[i])))}>Copy as Markdown</button>
              </div>
              <div className="tp-list">
                {[...cols, ...hidden].map((c) => (
                  <div key={c} className="tp-term">
                    <input type="checkbox" checked={!hidden.includes(c)} aria-label={`Show ${c}`} onChange={() => setHidden(hidden.includes(c) ? hidden.filter((x) => x !== c) : [...hidden, c])} />
                    <span style={{ flex: 1 }}>{label(c)}</span>
                    <button className="btn sm ghost" aria-pressed={pinned.includes(c)} aria-label={`Pin ${label(c)}`} onClick={() => setPinned(pinned.includes(c) ? pinned.filter((x) => x !== c) : [...pinned, c])}><Pin size={11} /></button>
                    <button className="btn sm ghost" aria-label="Move left" onClick={() => move(c, -1)}><ArrowUp size={11} /></button>
                    <button className="btn sm ghost" aria-label="Move right" onClick={() => move(c, 1)}><ArrowDown size={11} /></button>
                  </div>
                ))}
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>
      <div ref={scrollRef} className="tbl-wrap" style={{ maxHeight: (opts?.maxHeight as number | undefined) ?? 440 }}>
        <table className="tbl">
          <thead>
            {twoLevel ? <tr>{groups.map((g, k) => (g.head ? <th key={k} colSpan={g.span} className="grp">{label(g.head)}</th> : <th key={k} />))}</tr> : null}
            <tr ref={headRow}>{groups.flatMap((g) => g.cols.map((c) => sortTh(c, shortName(c, g.head))))}</tr>
          </thead>
          <tbody>
            {virtual && windowRows[0]?.start > 0 ? <tr aria-hidden="true"><td colSpan={cols.length} style={{ height: windowRows[0].start, padding: 0, border: 0 }} /></tr> : null}
            {visibleItems.map(({ item: it, index: k }) => {
              if (it.kind === "group") {
                const closed = collapsed.includes(it.g);
                return (
                  <tr key={`g${k}`} className="gr">
                    <td colSpan={cols.length}><button className="dt-sort" aria-expanded={!closed} onClick={() => setCollapsed(closed ? collapsed.filter((x) => x !== it.g) : [...collapsed, it.g])}><ChevronRight size={12} style={{ marginRight: 6, verticalAlign: -2, transform: closed ? "none" : "rotate(90deg)", transition: "transform .15s" }} />{it.g}<span className="stat-s" style={{ marginLeft: 8 }}>{it.n}</span></button></td>
                  </tr>
                );
              }
              const r = rows[it.i];
              return (
                <tr key={`r${it.i}`} className={`clickable${it.sub ? " sub" : ""}`} data-sel={sel === it.i} tabIndex={0} onClick={() => setSel(it.i)} onKeyDown={(e) => { if (e.key === "Enter") setSel(it.i); }}>
                  {cols.map((c, j) => (
                    <td key={c} className={`${numeric.has(c) ? "r num" : ""}${j === 0 ? " strong" : ""}${flash[`${it.i}:${c}`] !== undefined ? " flash" : ""}`} style={{ ...cellStyle(c, r[c]), ...colStyle(c) }}>{render(r, it.i, c)}</td>
                  ))}
                </tr>
              );
            })}
            {virtual && windowRows.length ? <tr aria-hidden="true"><td colSpan={cols.length} style={{ height: Math.max(0, virtualizer.getTotalSize() - windowRows[windowRows.length - 1].end), padding: 0, border: 0 }} /></tr> : null}
          </tbody>
        </table>
      </div>
      {rows.length > max ? <nav className="dt-pages" aria-label="Table pages"><span role="status">Rows {currentPage * max + 1}–{Math.min((currentPage + 1) * max, rows.length)} of {rows.length}</span><button className="btn sm ghost" disabled={currentPage === 0} onClick={() => changePage(currentPage - 1)}>Previous</button><button className="btn sm ghost" disabled={(currentPage + 1) * max >= rows.length} onClick={() => changePage(currentPage + 1)}>Next</button></nav> : null}
      <div className="dt-cards">
        {!virtual && shown.map((i) => (
          <div key={i} className="dt-card" onClick={() => setSel(i)}>
            {cols.map((c) => <div key={c}><span>{label(c)}</span><span>{render(rows[i], i, c)}</span></div>)}
          </div>
        ))}
      </div>
      {sel !== null && rows[sel] ? (
        <aside className="dt-drawer" aria-label="Row details">
          <h4><span>Row {sel + 1}</span><button className="btn sm ghost" aria-label="Close" onClick={() => setSel(null)}><X size={13} /></button></h4>
          <dl className="kv">{base.map((c) => <div key={c}><dt>{label(c)}</dt><dd className={isNum(rows[sel][c]) ? "num" : undefined}>{fmtKey(c, rows[sel][c])}</dd></div>)}</dl>
        </aside>
      ) : null}
    </div>
  );
}
