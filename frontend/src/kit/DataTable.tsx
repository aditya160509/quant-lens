"use client";

import toast from "react-hot-toast";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import * as Popover from "@radix-ui/react-popover";
import { ArrowDown, ArrowUp, ChevronRight, Columns3, Download, Link2, Pin, RotateCcw, Search, X } from "lucide-react";
import { Spark } from "@/charts/RankList";
import { downloadCsv, downloadXlsx } from "@/charts/export";
import { openQuickLook } from "./QuickLook";
import { EMPTY_VIEW, reduce, useSavedViews, useTableView, withPercentiles, type Fmt, type NumFmt, type TableView } from "./tableView";
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

/** Stable hue per name, so a ticker or sector keeps its colour everywhere. */
const hue = (s: string) => Array.from({ length: s.length }, (_, i) => s.charCodeAt(i)).reduce((h, c) => (h * 31 + c) % 360, 7);

const shortName = (c: string, head: string | null) => label(head && c.startsWith(`${head}_`) ? c.slice(head.length + 1) : c);

/** GitHub-style table text; pipes are escaped so a cell cannot add a column. */
export function toMarkdown(cols: string[], rows: Row[]): string {
  const cell = (v: unknown) => String(v ?? "").replace(/\|/g, "\\|").replace(/\s*\n\s*/g, " ");
  return [`| ${cols.map((c) => cell(label(c))).join(" | ")} |`, `|${cols.map(() => " --- ").join("|")}|`, ...rows.map((r) => `| ${cols.map((c) => cell(r[c])).join(" | ")} |`)].join("\n");
}

const FORMATS: { value: Fmt["mode"] | ""; label: string }[] = [{ value: "", label: "Plain" }, { value: "bar", label: "Bars" }, { value: "heat", label: "Heat" }, { value: "sign", label: "Signed" }, { value: "rule", label: "Rule" }, { value: "rank", label: "Top / bottom N" }];
const NUMS: { value: NumFmt["style"] | ""; label: string }[] = [{ value: "", label: "Auto" }, { value: "compact", label: "1.2B" }, { value: "percent", label: "%" }, { value: "fixed", label: "0.00" }, { value: "usd", label: "$" }];
const writeNum = (f: NumFmt, v: number) => f.style === "percent" ? `${(v * 100).toFixed(f.dp)}%`
  : new Intl.NumberFormat("en-US", f.style === "compact" ? { notation: "compact", maximumFractionDigits: f.dp } : f.style === "usd" ? { style: "currency", currency: "USD", notation: Math.abs(v) >= 1e6 ? "compact" : "standard", maximumFractionDigits: f.dp } : { minimumFractionDigits: f.dp, maximumFractionDigits: f.dp }).format(v);

/** Table of rows. With `opts.viewKey` the arrangement (columns, sort, formats, grouping) is shared with the URL and can be saved; `opts.detail` fills the row drawer. */
export function DataTable({ rows: source, opts }: { rows: Row[]; opts?: Record<string, unknown> }) {
  const viewKey = opts?.viewKey as string | undefined;
  // Lead columns (ticker, company) start frozen.
  const [view, update] = useTableView(viewKey, { tint: opts?.tint === true, pinned: (opts?.freeze as string[] | undefined) ?? (opts?.lead as string[] | undefined) ?? [] });
  const { order: colOrder, hidden, pinned, widths, sort, density, tint } = view;
  const patch = (p: Partial<TableView>) => update((v) => ({ ...v, ...p }));
  const [query, setQuery] = useState("");
  const [colQ, setColQ] = useState("");
  const rows = useMemo(() => {
    const all = withPercentiles(source, view.pct);
    const q = query.trim().toLowerCase();
    return q ? all.filter((r) => Object.values(r).some((v) => typeof v === "string" && v.toLowerCase().includes(q))) : all;
  }, [source, view.pct, query]);
  const sets = opts?.sets as Record<string, string[]> | undefined;
  const lead = (opts?.lead as string[] | undefined) ?? [];
  const activeSet = sets && view.set && sets[view.set] ? sets[view.set] : null;
  const saved = useSavedViews();
  const [viewName, setViewName] = useState("");
  const [everywhere, setEverywhere] = useState(false);
  const hideOpt = opts?.hide as string[] | undefined;
  const order = opts?.columns as string[] | undefined;
  const groupKey = view.groupBy ?? (opts?.groupKey as string | undefined);
  const bars = opts?.bars as string[] | undefined;
  const rowActions = opts?.rowActions as ((row: Row) => ReactNode) | undefined;
  const hatch = opts?.hatch === true;
  const bulk = opts?.bulk as ((rows: Row[], clear: () => void) => ReactNode) | undefined;
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [pickedFor, setPickedFor] = useState<Row[]>(rows);
  if (pickedFor !== rows) { setPickedFor(rows); setPicked(new Set()); }
  const base = useMemo(() => {
    const all = columns(source).filter((c) => !(hideOpt ?? []).includes(c) && source.some((r) => r[c] !== null && r[c] !== undefined && r[c] !== ""))
      .filter((c) => !activeSet || lead.includes(c) || activeSet.includes(c));
    return order ? [...order.filter((c) => all.includes(c)), ...all.filter((c) => !order.includes(c))] : all;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, hideOpt, order, activeSet]);
  const [lefts, setLefts] = useState<Record<string, number>>({});
  const cols = useMemo(() => {
    const o = colOrder ? [...colOrder.filter((c) => base.includes(c)), ...base.filter((c) => !colOrder.includes(c))] : base;
    const shown = o.filter((c) => !hidden.includes(c));
    return [...shown.filter((c) => pinned.includes(c)), ...shown.filter((c) => !pinned.includes(c))];
  }, [base, colOrder, hidden, pinned]);
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
  const sort2 = view.sort2;
  const sorting = useMemo(() => [sort, sort2].filter((x): x is { key: string; dir: 1 | -1 } => !!x).map((x) => ({ id: x.key, desc: x.dir === -1 })), [sort, sort2]);
  const table = useReactTable({ data: rows, columns: definitions, autoResetPageIndex: false,
    state: { sorting },
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), enableMultiSort: true, isMultiSortEvent: () => true,
  });
  const order2 = table.getRowModel().rows.map((row) => row.index);
  const shownRows = () => order2.map((i) => Object.fromEntries(cols.map((c) => [c, rows[i][c]])));
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
    const move = (m: globalThis.PointerEvent) => update((v) => ({ ...v, widths: { ...v.widths, [c]: Math.max(48, Math.round(w0 + m.clientX - x0)) } }));
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
    patch({ order: [...o, ...hidden] });
  };
  const range = useMemo(() => {
    const m: Record<string, [number, number]> = {};
    Object.keys(view.fmt).forEach((c) => { const v = rows.map((r) => r[c]).filter(isNum); if (v.length) m[c] = [Math.min(...v), Math.max(...v)]; });
    return m;
  }, [rows, view.fmt]);
  // Top / bottom N: the Nth best (or worst) value is the cut.
  const cut = useMemo(() => {
    const m: Record<string, number> = {};
    Object.entries(view.fmt).forEach(([c, f]) => {
      if (f.mode !== "rank") return;
      const v = rows.map((r) => r[c]).filter(isNum).sort((a, b) => (f.op === "<" ? a - b : b - a));
      const n = Math.max(1, Math.round(f.value ?? 10));
      if (v.length) m[c] = v[Math.min(n, v.length) - 1];
    });
    return m;
  }, [rows, view.fmt]);
  const numText = (c: string, v: unknown) => (view.num?.[c] && isNum(v) ? writeNum(view.num[c], v) : fmtKey(c, v));
  const [dragCol, setDragCol] = useState<string | null>(null);
  const cellStyle = (c: string, v: unknown) => {
    const f = view.fmt[c];
    if (f && isNum(v) && range[c]) {
      if (f.mode === "heat") return { background: `color-mix(in oklch, var(--accent) ${(range[c][1] > range[c][0] ? ((v - range[c][0]) / (range[c][1] - range[c][0])) * 40 : 20).toFixed(0)}%, transparent)` };
      if (f.mode === "sign") return { color: v > 0 ? "var(--up)" : v < 0 ? "var(--down)" : undefined };
      if (f.mode === "rule" && f.value !== undefined && (f.op === "<" ? v < f.value : v > f.value)) return { background: "color-mix(in oklch, var(--warn) 24%, transparent)" };
      if (f.mode === "rank" && cut[c] !== undefined && (f.op === "<" ? v <= cut[c] : v >= cut[c])) return { background: `color-mix(in oklch, ${f.op === "<" ? "var(--down)" : "var(--up)"} 22%, transparent)` };
    }
    if (isPKey(c)) return { color: toneVar(pTone(v)) };
    if (tint && isNum(v) && bound[c]) {
      const a = Math.min(1, Math.abs(v) / bound[c]) * 0.28;
      return { background: `color-mix(in oklch, ${v >= 0 ? "var(--up)" : "var(--down)"} ${(a * 100).toFixed(0)}%, transparent)` };
    }
    return undefined;
  };
  const items: ({ kind: "group"; g: string; n: number; ix: number[] } | { kind: "row"; i: number; sub: boolean })[] = [];
  if (groupKey) {
    const seen = new Map<string, number[]>();
    // A numeric column groups into quintiles of the shown rows.
    const qs = numeric.has(groupKey) ? rows.map((r) => r[groupKey]).filter(isNum).sort((a, b) => a - b) : null;
    const bucket = (v: unknown) => !qs ? String(v ?? "Other") : !isNum(v) ? "No value" : `Q${Math.min(5, 1 + Math.floor((qs.findIndex((x) => x >= v) / qs.length) * 5))} ${label(groupKey)}`;
    shown.forEach((i) => { const g = bucket(rows[i][groupKey]); seen.set(g, [...(seen.get(g) ?? []), i]); });
    seen.forEach((ix, g) => { items.push({ kind: "group", g, n: ix.length, ix }); if (!collapsed.includes(g)) ix.forEach((i) => items.push({ kind: "row", i, sub: true })); });
  } else shown.forEach((i) => items.push({ kind: "row", i, sub: false }));
  const virtual = items.length > 200;
  const virtualizer = useVirtualizer({ count: virtual ? items.length : 0,
    getScrollElement: () => scrollRef.current, estimateSize: () => density === "compact" ? 24 : 32,
    overscan: 8, initialRect: { width: 800, height: 440 },
  });
  const windowRows = virtual ? virtualizer.getVirtualItems() : [];
  const visibleItems = virtual ? windowRows.map((row) => ({ item: items[row.index], index: row.index })) : items.map((item, index) => ({ item, index }));
  const changePage = (next: number) => { setPage(next); setSel(null); if (scrollRef.current) scrollRef.current.scrollTop = 0; };
  if (!source.length) return <Empty />;
  const render = (r: Row, i: number, c: string) => {
    const v = r[c];
    const d = flash[`${i}:${c}`];
    const f = view.fmt[c];
    const width = f?.mode === "bar" && isNum(v) && range[c] ? (range[c][1] > range[c][0] ? ((v - range[c][0]) / (range[c][1] - range[c][0])) * 100 : 50) : (view.pct[c] || bars?.includes(c)) && isNum(v) ? v : null;
    const content = width !== null && isNum(v) ? <span className="pbar"><i style={{ width: `${Math.max(0, Math.min(100, width))}%` }} />{view.pct[c] ? Math.round(v) : numText(c, v)}</span> : Array.isArray(v) && v.length > 1 && v.every(isNum) ? <Spark values={v} /> : FLAG_KEYS.includes(c) ? <FlagChip k={c} v={v} /> : isTKey(c) && isNum(v) ? <TBar t={v} /> : v === null || v === undefined || v === "" ? <span className="miss">—</span> : numText(c, v);
    if (c === "sector" && typeof v === "string" && v) return <span className="sec-pill" style={{ "--h": hue(v) } as CSSProperties}>{v}</span>;
    if (c === "company_name" && typeof v === "string") return <span className="co-name" title={v}>{v}</span>;
    return <>{c === "ticker" && typeof v === "string" ? <button type="button" className="tk-link" onClick={(e) => { e.stopPropagation(); openQuickLook(v); }}><span className="mono-tile" aria-hidden style={{ "--h": hue(v) } as CSSProperties}>{v.replace(/[^A-Z0-9]/gi, "").slice(0, 2)}</span>{content}</button> : content}{d ? <span className={`dl ${d > 0 ? "up" : "down"}`} aria-label={d > 0 ? "up" : "down"}>{d > 0 ? "▲" : "▼"}</span> : null}</>;
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
    <th key={c} data-col={c} style={colStyle(c, true)} className={`sortable${numeric.has(c) ? " r" : ""}${dragCol && dragCol !== c ? " drop" : ""}`} aria-sort={sort?.key === c ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
      draggable onDragStart={(e) => { setDragCol(c); e.dataTransfer.effectAllowed = "move"; }} onDragEnd={() => setDragCol(null)}
      onDragOver={(e) => { if (dragCol && dragCol !== c) e.preventDefault(); }}
      onDrop={(e) => { e.preventDefault(); if (!dragCol || dragCol === c) return; const o = cols.filter((x) => x !== dragCol); o.splice(o.indexOf(c), 0, dragCol); patch({ order: [...o, ...hidden] }); setDragCol(null); }}
      >
      <button className="dt-sort" title="Shift-click to sort by a second column" onClick={(e) => {
        setPage(0);
        const next = (cur: { key: string; dir: 1 | -1 } | null | undefined) => (cur?.key === c ? (cur.dir === 1 ? { key: c, dir: -1 as const } : null) : { key: c, dir: 1 as const });
        if (e.shiftKey && sort && sort.key !== c) patch({ sort2: next(sort2) });
        else patch({ sort: next(sort), sort2: sort?.key === c ? sort2 : null });
      }}>
      {text}{view.pct[c] ? (view.pct[c] === "sector" ? " %ile of sector" : " %ile of shown") : ""}
      {sort?.key === c ? (sort.dir === 1 ? <ArrowUp size={10} style={{ marginLeft: 4, verticalAlign: -1 }} /> : <ArrowDown size={10} style={{ marginLeft: 4, verticalAlign: -1 }} />) : null}
      {sort2?.key === c ? <span className="sort2">{sort2.dir === 1 ? "↑" : "↓"}2</span> : null}
      </button>
      <span className="dt-grip" role="separator" aria-label={`Resize ${text}`} title="Drag to resize, double-click to fit" onPointerDown={(e) => startResize(c, e)} onDoubleClick={() => { const { [c]: _, ...rest } = widths; void _; patch({ widths: rest }); }} />
    </th>
  );
  return (
    <div className="dt" data-virtual={virtual} data-density={density} data-bulk={!!bulk} onKeyDown={onKey}>
      <div className="dt-bar">
        {sets ? (
          <div className="dt-sets" role="tablist" aria-label="Column sets">
            {[null, ...Object.keys(sets)].map((k) => <button key={k ?? "all"} role="tab" aria-selected={(view.set ?? null) === k} onClick={() => patch({ set: k })}>{k ?? "All"}</button>)}
          </div>
        ) : null}
        <label className="dt-q"><Search size={12} aria-hidden /><input type="search" placeholder="Search" aria-label="Search rows" value={query} onChange={(e) => { setQuery(e.target.value); setPage(0); }} /></label>
        <span className="dt-n num">{rows.length === source.length ? rows.length : `${rows.length} of ${source.length}`}</span>
        <Popover.Root>
          <Popover.Trigger asChild><button className="btn sm ghost" aria-label="Table options" data-hotkey="col" aria-keyshortcuts="F"><Columns3 size={13} />Table</button></Popover.Trigger>
          <Popover.Portal container={typeof document === "undefined" ? undefined : document.querySelector<HTMLElement>(".ws")}>
            <Popover.Content className="tbl-pop" align="end" sideOffset={6} collisionPadding={12}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 2, paddingBottom: 6 }}>
                <button className="btn sm ghost" aria-pressed={tint} onClick={() => patch({ tint: !tint })}>Heat tint</button>
                <button className="btn sm ghost" onClick={() => patch({ density: density === "compact" ? "comfortable" : "compact" })}>{density === "compact" ? "Comfortable" : "Compact"}</button>
                <button className="btn sm ghost" onClick={() => void navigator.clipboard?.writeText(toMarkdown(cols, order2.map((i) => rows[i]))).then(() => toast.success("Table copied as Markdown"))}>Markdown</button>
                <button className="btn sm ghost" onClick={() => downloadCsv(shownRows(), "table")}><Download size={11} />CSV</button>
                {opts?.xlsx ? <button className="btn sm ghost" onClick={() => void downloadXlsx(shownRows(), "table", opts.xlsx as string)}><Download size={11} />Excel</button> : null}
                <button className="btn sm ghost" onClick={() => void navigator.clipboard?.writeText(window.location.href).then(() => toast.success("Link copied"))}><Link2 size={11} />Link</button>
                <button className="btn sm ghost" onClick={() => update(() => ({ ...EMPTY_VIEW, tint: opts?.tint === true }))}><RotateCcw size={11} />Reset</button>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, paddingBottom: 6 }}>
                <label className="xc"><span>Group by</span>
                  <select value={view.groupBy ?? ""} onChange={(e) => patch({ groupBy: e.target.value || null })}>
                    <option value="">None</option>
                    {base.map((c) => <option key={c} value={c}>{label(c)}{numeric.has(c) ? " (quintiles)" : ""}</option>)}
                  </select>
                </label>
                {view.groupBy ? <label className="xc"><span>Summary</span>
                  <select value={view.summary} onChange={(e) => patch({ summary: e.target.value as TableView["summary"] })}>{["median", "mean", "sum"].map((f) => <option key={f} value={f}>{label(f)}</option>)}</select>
                </label> : null}
              </div>
              <label className="dt-q" style={{ marginBottom: 6 }}><Search size={12} aria-hidden /><input type="search" placeholder="Find column" aria-label="Find column" value={colQ} onChange={(e) => setColQ(e.target.value)} /></label>
              <div className="tp-list">
                {[...cols, ...hidden].filter((c) => !colQ || `${c} ${label(c)}`.toLowerCase().includes(colQ.toLowerCase())).map((c) => (
                  <div key={c} className="tp-term">
                    <input type="checkbox" checked={!hidden.includes(c)} aria-label={`Show ${c}`} onChange={() => patch({ hidden: hidden.includes(c) ? hidden.filter((x) => x !== c) : [...hidden, c] })} />
                    <span style={{ flex: 1 }}>{label(c)}</span>
                    {numeric.has(c) ? (
                      <>
                        <select aria-label={`${label(c)} scale`} value={view.pct[c] ?? ""} onChange={(e) => { const { [c]: _, ...rest } = view.pct; void _; patch({ pct: e.target.value ? { ...rest, [c]: e.target.value as "all" | "sector" } : rest }); }}>
                          <option value="">Value</option><option value="all">%ile of shown</option>{base.includes("sector") ? <option value="sector">%ile of sector</option> : null}
                        </select>
                        <select aria-label={`${label(c)} number format`} value={view.num?.[c]?.style ?? ""} onChange={(e) => { const { [c]: _, ...rest } = view.num ?? {}; void _; patch({ num: e.target.value ? { ...rest, [c]: { style: e.target.value as NumFmt["style"], dp: e.target.value === "compact" ? 1 : 2 } } : rest }); }}>
                          {NUMS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
                        </select>
                        {view.num?.[c] ? <input className="input num" style={{ width: 40, height: 24 }} type="number" min={0} max={6} aria-label={`${label(c)} decimals`} value={view.num[c].dp} onChange={(e) => patch({ num: { ...view.num, [c]: { ...view.num![c], dp: Math.max(0, Math.min(6, Number(e.target.value))) } } })} /> : null}
                        <select aria-label={`${label(c)} format`} value={view.fmt[c]?.mode ?? ""} onChange={(e) => { const { [c]: _, ...rest } = view.fmt; void _; patch({ fmt: e.target.value ? { ...rest, [c]: { mode: e.target.value as Fmt["mode"], op: ">", value: view.fmt[c]?.value ?? 0 } } : rest }); }}>
                          {FORMATS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
                        </select>
                        {view.fmt[c]?.mode === "rank" ? (
                          <>
                            <select aria-label="Top or bottom" value={view.fmt[c].op} onChange={(e) => patch({ fmt: { ...view.fmt, [c]: { ...view.fmt[c], op: e.target.value as ">" | "<" } } })}><option value=">">Top</option><option value="<">Bottom</option></select>
                            <input className="input num" style={{ width: 52, height: 24 }} type="number" min={1} aria-label="N" value={view.fmt[c].value || 10} onChange={(e) => patch({ fmt: { ...view.fmt, [c]: { ...view.fmt[c], value: Number(e.target.value) } } })} />
                          </>
                        ) : view.fmt[c]?.mode === "rule" ? (
                          <>
                            <select aria-label="Rule" value={view.fmt[c].op} onChange={(e) => patch({ fmt: { ...view.fmt, [c]: { ...view.fmt[c], op: e.target.value as ">" | "<" } } })}><option value=">">&gt;</option><option value="<">&lt;</option></select>
                            <input className="input num" style={{ width: 64, height: 24 }} type="number" aria-label="Rule value" value={view.fmt[c].value ?? 0} onChange={(e) => patch({ fmt: { ...view.fmt, [c]: { ...view.fmt[c], value: Number(e.target.value) } } })} />
                          </>
                        ) : null}
                      </>
                    ) : null}
                    <button className="btn sm ghost" aria-pressed={pinned.includes(c)} aria-label={`Pin ${label(c)}`} onClick={() => patch({ pinned: pinned.includes(c) ? pinned.filter((x) => x !== c) : [...pinned, c] })}><Pin size={11} /></button>
                    <button className="btn sm ghost" aria-label="Move left" onClick={() => move(c, -1)}><ArrowUp size={11} /></button>
                    <button className="btn sm ghost" aria-label="Move right" onClick={() => move(c, 1)}><ArrowDown size={11} /></button>
                  </div>
                ))}
              </div>
              {viewKey ? (
                <div style={{ display: "grid", gap: 4, paddingTop: 8 }}>
                  <div style={{ display: "flex", gap: 4 }}>
                    <input className="input" style={{ flex: 1, height: 26 }} placeholder="View name" aria-label="View name" value={viewName} onChange={(e) => setViewName(e.target.value)} />
                    <button type="button" className="pill" aria-pressed={everywhere} onClick={() => setEverywhere(!everywhere)}>All tables</button>
                    <button type="button" className="btn sm" disabled={!viewName.trim()} onClick={() => { saved.save({ name: viewName.trim(), scope: everywhere ? "all" : "here", key: viewKey, view }); toast.success(`View "${viewName.trim()}" saved`); setViewName(""); }}>Save</button>
                  </div>
                  {saved.views.filter((v) => v.scope === "all" || v.key === viewKey).map((v) => (
                    <div key={v.id} style={{ display: "flex", gap: 4, alignItems: "center" }}>
                      <button type="button" className="btn sm ghost" style={{ flex: 1, justifyContent: "flex-start" }} onClick={() => update(() => ({ ...EMPTY_VIEW, ...v.view }))}>{v.name}{v.scope === "all" ? " · all tables" : ""}</button>
                      <button type="button" className="btn sm ghost" aria-label={`Delete ${v.name}`} onClick={() => saved.remove(v.id)}><X size={11} /></button>
                    </div>
                  ))}
                </div>
              ) : null}
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>
      {bulk && picked.size ? (
        <div className="dt-bulk" role="toolbar" aria-label="Selected rows">
          <strong className="num">{picked.size}</strong> selected
          {bulk([...picked].map((i) => rows[i]).filter(Boolean), () => setPicked(new Set()))}
          <button className="btn sm ghost" onClick={() => setPicked(new Set())}><X size={11} />Clear</button>
        </div>
      ) : null}
      <div ref={scrollRef} className="tbl-wrap" style={{ maxHeight: (opts?.maxHeight as number | undefined) ?? 440 }}>
        <table className="tbl">
          <thead>
            {twoLevel ? <tr>{groups.map((g, k) => (g.head ? <th key={k} colSpan={g.span} className="grp">{label(g.head)}</th> : <th key={k} />))}</tr> : null}
            <tr ref={headRow}>{bulk ? <th className="dt-chk"><input type="checkbox" aria-label="Select all shown" checked={shown.length > 0 && shown.every((i) => picked.has(i))} onChange={(e) => setPicked(e.target.checked ? new Set(shown) : new Set())} /></th> : null}{groups.flatMap((g) => g.cols.map((c) => sortTh(c, shortName(c, g.head))))}{rowActions ? <th aria-label="Actions" /> : null}</tr>
          </thead>
          <tbody>
            {virtual && windowRows[0]?.start > 0 ? <tr aria-hidden="true"><td colSpan={cols.length + (rowActions ? 1 : 0) + (bulk ? 1 : 0)} style={{ height: windowRows[0].start, padding: 0, border: 0 }} /></tr> : null}
            {visibleItems.map(({ item: it, index: k }) => {
              if (it.kind === "group") {
                const closed = collapsed.includes(it.g);
                return (
                  <tr key={`g${k}`} className="gr">
                    {bulk ? <td /> : null}
                    {cols.map((c, j) => j === 0 ? (
                      <td key={c}><button className="dt-sort" aria-expanded={!closed} onClick={() => setCollapsed(closed ? collapsed.filter((x) => x !== it.g) : [...collapsed, it.g])}><ChevronRight size={12} style={{ marginRight: 6, verticalAlign: -2, transform: closed ? "none" : "rotate(90deg)", transition: "transform .15s" }} />{it.g}<span className="stat-s" style={{ marginLeft: 8 }}>{it.n}</span></button></td>
                    ) : <td key={c} className={numeric.has(c) ? "r num" : undefined}>{numeric.has(c) ? fmtKey(c, reduce(it.ix.map((i) => rows[i][c]).filter(isNum), view.summary)) : ""}</td>)}
                    {rowActions ? <td /> : null}
                  </tr>
                );
              }
              const r = rows[it.i];
              return (
                <tr key={`r${it.i}`} className={`clickable${it.sub ? " sub" : ""}`} data-sel={sel === it.i} tabIndex={0} onClick={() => setSel(it.i)} onKeyDown={(e) => { if (e.key === "Enter") setSel(it.i); }}>
                  {bulk ? <td className="dt-chk" onClick={(e) => e.stopPropagation()}><input type="checkbox" aria-label={`Select ${String(r.ticker ?? it.i + 1)}`} checked={picked.has(it.i)} onChange={() => setPicked((p) => { const n = new Set(p); if (n.has(it.i)) n.delete(it.i); else n.add(it.i); return n; })} /></td> : null}
                  {cols.map((c, j) => (
                    <td key={c} className={`${numeric.has(c) ? "r num" : ""}${j === 0 ? " strong" : ""}${flash[`${it.i}:${c}`] !== undefined ? " flash" : ""}${hatch && (r[c] === null || r[c] === undefined || r[c] === "Unknown") ? " unk" : ""}`} style={{ ...cellStyle(c, r[c]), ...colStyle(c) }}>{render(r, it.i, c)}</td>
                  ))}
                  {rowActions ? <td className="ra" onClick={(e) => e.stopPropagation()}>{rowActions(r)}</td> : null}
                </tr>
              );
            })}
            {virtual && windowRows.length ? <tr aria-hidden="true"><td colSpan={cols.length + (rowActions ? 1 : 0) + (bulk ? 1 : 0)} style={{ height: Math.max(0, virtualizer.getTotalSize() - windowRows[windowRows.length - 1].end), padding: 0, border: 0 }} /></tr> : null}
          </tbody>
          {rows.length > 3 && numeric.size ? (
            <tfoot>
              <tr className="dt-foot">
                {bulk ? <td /> : null}
                {cols.map((c, j) => <td key={c} className={numeric.has(c) ? "r num" : undefined} style={colStyle(c)}>{j === 0 ? "Median" : numeric.has(c) && !isPKey(c) ? numText(c, reduce(rows.map((r) => r[c]).filter(isNum), "median")) : ""}</td>)}
                {rowActions ? <td /> : null}
              </tr>
            </tfoot>
          ) : null}
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
          {typeof opts?.detail === "function" ? (opts.detail as (row: Row) => ReactNode)(rows[sel]) : null}
        </aside>
      ) : null}
    </div>
  );
}
