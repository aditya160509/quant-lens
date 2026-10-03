"use client";

import { Fragment, useEffect, useMemo, useState, type KeyboardEvent } from "react";
import * as Popover from "@radix-ui/react-popover";
import "./tables.css";
import { RegSettingsPopover } from "./table/RegSettingsPopover";
import { buildModel, notesText, regressionLatex, starsFor, statText } from "./table/regression";
import { useRegSettings } from "./table/settings";
import { ArrowDown, ArrowUp, Check, ChevronRight, Columns3, Copy, Download, FileDown, X } from "lucide-react";
import { downloadBase64, downloadCsv, downloadText } from "@/charts/export";
import { columns, fmtKey, isNum, isPKey, isTKey, label, num, pTone, pval, rowsOf, toneVar, tstat } from "../format";
import type { Row } from "../types";
import type { ViewProps } from "./types";

export function Empty({ text = "Nothing to show for this configuration." }: { text?: string }) {
  return <div style={{ padding: "22px 4px", color: "var(--text-3)", fontSize: 12.5 }}>{text}</div>;
}

const FLAG_KEYS = ["fragile", "disagreement", "material_disagreement", "imbalanced", "near_duplicate", "discontinuity", "still_significant", "significant", "flag", "concentrated", "manipulation_detected", "winner", "forbidden_comparison"];
const POSITIVE_FLAGS = new Set(["still_significant", "winner"]);

function FlagChip({ k, v }: { k: string; v: unknown }) {
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

export function DataTable({ rows, opts }: Pick<ViewProps, "rows" | "opts">) {
  const hideOpt = opts?.hide as string[] | undefined;
  const order = opts?.columns as string[] | undefined;
  const groupKey = opts?.groupKey as string | undefined;
  const base = useMemo(() => {
    const all = columns(rows).filter((c) => !(hideOpt ?? []).includes(c));
    return order ? [...order.filter((c) => all.includes(c)), ...all.filter((c) => !order.includes(c))] : all;
  }, [rows, hideOpt, order]);
  const [colOrder, setColOrder] = useState<string[] | null>(null);
  const [hidden, setHidden] = useState<string[]>([]);
  const cols = useMemo(() => {
    const o = colOrder ? [...colOrder.filter((c) => base.includes(c)), ...base.filter((c) => !colOrder.includes(c))] : base;
    return o.filter((c) => !hidden.includes(c));
  }, [base, colOrder, hidden]);
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
  const order2 = useMemo(() => {
    const idx = rows.map((_, i) => i);
    if (!sort) return idx;
    return idx.sort((i, j) => {
      const x = rows[i][sort.key], y = rows[j][sort.key];
      if (isNum(x) && isNum(y)) return (x - y) * sort.dir;
      return String(x ?? "").localeCompare(String(y ?? "")) * sort.dir;
    });
  }, [rows, sort]);
  const max = (opts?.max as number | undefined) ?? 400;
  const shown = order2.slice(0, max);
  const numeric = new Set(cols.filter((c) => rows.some((r) => isNum(r[c]))));
  const bound = useMemo(() => {
    const m: Record<string, number> = {};
    cols.forEach((c) => { if (numeric.has(c) && !isPKey(c)) m[c] = Math.max(1e-12, ...rows.map((r) => (isNum(r[c]) ? Math.abs(r[c]) : 0))); });
    return m;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, cols]);
  if (!rows.length) return <Empty />;
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
  const render = (r: Row, i: number, c: string) => {
    const v = r[c];
    const d = flash[`${i}:${c}`];
    const content = FLAG_KEYS.includes(c) ? <FlagChip k={c} v={v} /> : isTKey(c) && isNum(v) ? <TBar t={v} /> : fmtKey(c, v);
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
    <th key={c} className={`sortable${numeric.has(c) ? " r" : ""}`} aria-sort={sort?.key === c ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
      onClick={() => setSort((s) => (s?.key === c ? (s.dir === 1 ? { key: c, dir: -1 } : null) : { key: c, dir: 1 }))}>
      {text}
      {sort?.key === c ? (sort.dir === 1 ? <ArrowUp size={10} style={{ marginLeft: 4, verticalAlign: -1 }} /> : <ArrowDown size={10} style={{ marginLeft: 4, verticalAlign: -1 }} />) : null}
    </th>
  );
  return (
    <div className="dt" data-density={density} onKeyDown={onKey}>
      <div className="dt-bar">
        <button className="btn sm ghost" aria-pressed={tint} onClick={() => setTint(!tint)}>Heat tint</button>
        <button className="btn sm ghost" onClick={() => setDensity(density === "compact" ? "comfortable" : "compact")}>{density === "compact" ? "Comfortable" : "Compact"}</button>
        <Popover.Root>
          <Popover.Trigger asChild><button className="btn sm ghost" aria-label="Columns"><Columns3 size={13} />Columns</button></Popover.Trigger>
          <Popover.Portal container={typeof document === "undefined" ? undefined : document.querySelector<HTMLElement>(".ws")}>
            <Popover.Content className="tbl-pop" align="end" sideOffset={6} collisionPadding={12}>
              <div className="tp-list">
                {[...cols, ...hidden].map((c) => (
                  <div key={c} className="tp-term">
                    <input type="checkbox" checked={!hidden.includes(c)} aria-label={`Show ${c}`} onChange={() => setHidden(hidden.includes(c) ? hidden.filter((x) => x !== c) : [...hidden, c])} />
                    <span style={{ flex: 1 }}>{label(c)}</span>
                    <button className="btn sm ghost" aria-label="Move left" onClick={() => move(c, -1)}><ArrowUp size={11} /></button>
                    <button className="btn sm ghost" aria-label="Move right" onClick={() => move(c, 1)}><ArrowDown size={11} /></button>
                  </div>
                ))}
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>
      <div className="tbl-wrap" style={{ maxHeight: (opts?.maxHeight as number | undefined) ?? 440 }}>
        <table className="tbl">
          <thead>
            {twoLevel ? <tr>{groups.map((g, k) => (g.head ? <th key={k} colSpan={g.span} className="grp">{label(g.head)}</th> : <th key={k} />))}</tr> : null}
            <tr>{groups.flatMap((g) => g.cols.map((c) => sortTh(c, shortName(c, g.head))))}</tr>
          </thead>
          <tbody>
            {items.map((it, k) => {
              if (it.kind === "group") {
                const closed = collapsed.includes(it.g);
                return (
                  <tr key={`g${k}`} className="gr" onClick={() => setCollapsed(closed ? collapsed.filter((x) => x !== it.g) : [...collapsed, it.g])} aria-expanded={!closed}>
                    <td colSpan={cols.length}><ChevronRight size={12} style={{ marginRight: 6, verticalAlign: -2, transform: closed ? "none" : "rotate(90deg)", transition: "transform .15s" }} />{it.g}<span className="stat-s" style={{ marginLeft: 8 }}>{it.n}</span></td>
                  </tr>
                );
              }
              const r = rows[it.i];
              return (
                <tr key={`r${it.i}`} className={`clickable${it.sub ? " sub" : ""}`} data-sel={sel === it.i} tabIndex={0} onClick={() => setSel(it.i)} onKeyDown={(e) => { if (e.key === "Enter") setSel(it.i); }}>
                  {cols.map((c, j) => (
                    <td key={c} className={`${numeric.has(c) ? "r num" : ""}${j === 0 ? " strong" : ""}${flash[`${it.i}:${c}`] !== undefined ? " flash" : ""}`} style={cellStyle(c, r[c])}>{render(r, it.i, c)}</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length > max ? <div className="stat-s" style={{ padding: "8px 12px" }}>Showing {max} of {rows.length} rows. The CSV export has all of them.</div> : null}
      </div>
      <div className="dt-cards">
        {shown.map((i) => (
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

// ---------------------------------------------------------------- facts

/** Key figures of a one-row output: headline numbers large, the rest as a compact grid, prose underneath. */
export function Facts({ rows, opts }: Pick<ViewProps, "rows" | "opts">) {
  const row = rowsOf(rows)[0];
  if (!row) return <Empty />;
  if (row.available === false) return <Empty text={String(row.reason ?? row.note ?? row.status ?? "Not available for this configuration.")} />;
  const hero = (opts?.hero as string[] | undefined) ?? [];
  const hide = new Set([...(opts?.hide as string[] | undefined) ?? [], "available"]);
  const entries = Object.entries(row).filter(([k, v]) => !hide.has(k) && v !== null && v !== undefined && !(Array.isArray(v) && !v.length));
  const prose = entries.filter(([, v]) => typeof v === "string" && v.length > 48);
  const heroEntries = entries.filter(([k]) => hero.includes(k));
  const rest = entries.filter((e) => !prose.includes(e) && !heroEntries.includes(e));
  return (
    <div style={{ display: "grid", gap: 16 }}>
      {heroEntries.length ? (
        <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
          {heroEntries.map(([k, v]) => (
            <div key={k}>
              <div className="stat-l">{label(k)}</div>
              <div className="stat-v" style={{ color: isPKey(k) ? toneVar(pTone(v)) : undefined }}>{fmtKey(k, v)}</div>
            </div>
          ))}
        </div>
      ) : null}
      {rest.length ? (
        <dl className="kv">
          {rest.map(([k, v]) => (
            <div key={k}>
              <dt>{label(k)}</dt>
              <dd className={isNum(v) ? "num" : undefined} style={{ color: isPKey(k) ? toneVar(pTone(v)) : undefined }}>
                {FLAG_KEYS.includes(k) ? <FlagChip k={k} v={v} /> : fmtKey(k, v)}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
      {prose.map(([k, v]) => <p key={k} className="prose">{String(v)}</p>)}
    </div>
  );
}

// ---------------------------------------------------------------- tests

const STAT_KEYS = ["statistic", "f_stat", "sup_f", "chi2_stat", "grs_stat", "mr_statistic", "t_stat", "observed_t", "observed", "fisher_stat", "jarque_bera", "j_stat", "treated_ratio", "post_pre_rmspe_ratio", "real_t_stat", "corrected_t", "condition_number", "alpha_t"];
const P_KEYS = ["p_value", "bootstrap_p_value", "placebo_p_value", "permutation_p_value", "p_value_robust", "fisher_p_value", "j_p_value", "alpha_p", "f_p_value", "one_sided_p_value"];
const NOTE_KEYS = ["verdict", "message", "interpretation", "note", "assessment", "fit_quality", "bias_direction", "description"];

export type TestRow = { name: string; stat: number | null; statName: string; p: number | null; note: string | null; flag: boolean | null; row: Row };

export function toTest(name: string, row: Row | undefined): TestRow | null {
  if (!row) return null;
  const statKey = STAT_KEYS.find((k) => isNum(row[k]));
  const pKey = P_KEYS.find((k) => isNum(row[k]));
  const note = NOTE_KEYS.map((k) => row[k]).find((v): v is string => typeof v === "string" && v.length > 0) ?? null;
  const flagVal = ["flag", "weak_identification_flag", "manipulation_detected", "concentrated"].map((k) => row[k]).find((v) => typeof v === "boolean");
  return {
    name: typeof row.test === "string" ? label(row.test) : name,
    stat: statKey ? (row[statKey] as number) : null,
    statName: typeof row.statistic === "string" ? row.statistic : statKey ? label(statKey) : "",
    p: pKey ? (row[pKey] as number) : null,
    note: row.available === false ? String(row.reason ?? row.note ?? "Not available") : note,
    flag: typeof flagVal === "boolean" ? flagVal : null,
    row,
  };
}

function Decision({ p, flag }: { p: number | null; flag: boolean | null }) {
  if (p === null) return flag === null ? <span style={{ color: "var(--text-4)" }}>–</span> : <span className={`chip ${flag ? "warn" : "up"}`}>{flag ? "Flagged" : "Clear"}</span>;
  const cls = p < 0.01 ? "up" : p < 0.05 ? "up" : p < 0.1 ? "warn" : "";
  return <span className={`chip ${cls}`}>{p < 0.01 ? "Reject 1%" : p < 0.05 ? "Reject 5%" : p < 0.1 ? "Reject 10%" : "Not rejected"}</span>;
}

/** Many hypothesis tests in one table: statistic, p-value, decision; click a row for every detail. */
export function TestsTable({ result, keys, feature }: ViewProps) {
  const [open, setOpen] = useState<number | null>(null);
  const tests = keys.flatMap((k) => {
    const title = feature.outputs.find((o) => o.key === k)?.title ?? label(k);
    const rows = rowsOf(result.tables?.[k] ?? result.charts?.[k]);
    if (rows.length > 1 && rows.every((r) => typeof r.test === "string")) return rows.map((r) => toTest(title, r));
    return [toTest(title, rows[0])];
  }).filter((t): t is TestRow => t !== null);
  if (!tests.length) return <Empty />;
  return (
    <table className="tbl">
      <thead><tr><th style={{ width: 22 }} /><th>Test</th><th className="r">Statistic</th><th className="r">p-value</th><th>Decision</th></tr></thead>
      <tbody>
        {tests.map((t, i) => (
          <Fragment key={i}>
            <tr onClick={() => setOpen(open === i ? null : i)} style={{ cursor: "pointer" }} aria-expanded={open === i}>
              <td style={{ paddingRight: 0 }}><ChevronRight size={13} style={{ color: "var(--text-3)", transform: open === i ? "rotate(90deg)" : "none", transition: "transform .15s" }} /></td>
              <td className="strong" style={{ whiteSpace: "normal" }}>
                {t.name}
                {t.statName && t.statName.length > 18 ? <div className="stat-s">{t.statName}</div> : null}
              </td>
              <td className="r num">{t.stat === null ? "–" : num(t.stat, 3)}</td>
              <td className="r num" style={{ color: toneVar(pTone(t.p)) }}>{pval(t.p)}</td>
              <td><Decision p={t.p} flag={t.flag} /></td>
            </tr>
            {open === i ? (
              <tr className="dim">
                <td />
                <td colSpan={4} style={{ whiteSpace: "normal", padding: "10px 12px 14px" }}>
                  {t.note ? <p className="prose" style={{ marginBottom: 10 }}>{t.note}</p> : null}
                  <Facts rows={[Object.fromEntries(Object.entries(t.row).filter(([k]) => !NOTE_KEYS.includes(k) && k !== "test"))]} />
                </td>
              </tr>
            ) : null}
          </Fragment>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------- regressions

/** Journal-style regression table driven by persisted publication settings (statistic, stars, terms, GOF, layout). */
export function RegressionTable({ rows, scope = "regression" }: Pick<ViewProps, "rows"> & { scope?: string }) {
  const s = useRegSettings(scope);
  const [copied, setCopied] = useState(false);
  if (!rows.length) return <Empty />;
  if (rows[0].available === false) return <Empty text={String(rows[0].reason ?? "Not available.")} />;
  const m = buildModel(rows, s);
  const stacked = s.layout === "stacked";
  const showStat = s.stat !== "none";
  const statHead = s.stat === "se" ? "SE" : s.stat === "t" ? "t-stat" : s.stat === "p" ? "p" : "95% CI";
  const tex = regressionLatex(m, s);
  return (
    <div className="dt rt">
      <div className="dt-bar">
        <button className="btn sm ghost" onClick={() => { void navigator.clipboard.writeText(tex); setCopied(true); setTimeout(() => setCopied(false), 1400); }}>
          {copied ? <Check size={12} /> : <Copy size={12} />}{copied ? "Copied" : "LaTeX"}
        </button>
        <button className="btn sm ghost" onClick={() => downloadText(tex, `${scope}.tex`, "application/x-tex")}><Download size={12} />.tex</button>
        <RegSettingsPopover scope={scope} rows={rows} />
      </div>
      {s.title ? <div style={{ fontWeight: 600, padding: "0 12px 6px" }}>{s.title}</div> : null}
      <table className="tbl">
        <thead>
          <tr><th>{label(m.labelKey)}</th><th className="r">Estimate</th>{showStat && !stacked ? <th className="r">{statHead}</th> : null}{m.extra.map((k) => <th key={k} className="r">{label(k)}</th>)}</tr>
        </thead>
        <tbody>
          {m.terms.map((x) => {
            const sig = x.p !== null && x.p < 0.05;
            const st = statText(x, s);
            return (
              <tr key={x.key}>
                <td className="strong">{x.name}</td>
                <td className="r num" style={{ color: sig && x.est !== null ? (x.est > 0 ? "var(--up)" : "var(--down)") : "var(--text)", fontWeight: 500 }}>
                  {num(x.est, 4)}<sup style={{ color: "var(--text-3)", marginLeft: 1 }}>{starsFor(x.p, s)}</sup>
                  {stacked && showStat ? <span className="rt-stat">{st}</span> : null}
                </td>
                {showStat && !stacked ? <td className="r num">{st || "–"}</td> : null}
                {m.extra.map((k) => <td key={k} className="r num">{fmtKey(k, rows[m.terms.indexOf(x)]?.[k])}</td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
      {m.gof.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 16px", padding: "10px 12px 2px", fontSize: 12, color: "var(--text-3)" }}>
          {m.gof.map((g) => <span key={g.k}>{g.name} <span className="num" style={{ color: "var(--text-2)" }}>{fmtKey(g.k, g.v)}</span></span>)}
        </div>
      ) : null}
      <div style={{ padding: "6px 12px 0", fontSize: 11.5, color: "var(--text-3)" }}>{notesText(s)}</div>
    </div>
  );
}

/** Rows compared on their t-statistics, e.g. placebo series or asset classes. */
export function TStatTable({ rows, opts }: Pick<ViewProps, "rows" | "opts">) {
  if (!rows.length) return <Empty />;
  const r0 = rows[0];
  const lab = (opts?.label as string | undefined) ?? ["series", "asset_class", "window", "placebo", "market", "portfolio", "covariate"].find((k) => k in r0) ?? Object.keys(r0)[0];
  const t = ["t_stat", "statistic", "post_ic_t"].find((k) => k in r0);
  const p = ["p_value", "p_value_robust"].find((k) => k in r0);
  const valueKeys = Object.keys(r0).filter((k) => ![lab, t, p].includes(k) && rows.some((r) => isNum(r[k]) || typeof r[k] === "boolean")).slice(0, 3);
  const notes = Object.keys(r0).filter((k) => ![lab].includes(k) && typeof r0[k] === "string" && (r0[k] as string).length > 20);
  return (
    <table className="tbl">
      <thead><tr><th>{label(lab)}</th>{valueKeys.map((k) => <th key={k} className="r">{label(k)}</th>)}{t ? <th>t-stat</th> : null}{p ? <th className="r">p</th> : null}</tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td className="strong" style={{ whiteSpace: "normal" }}>{fmtKey("", r[lab])}{notes.map((k) => r[k] ? <div key={k} className="stat-s">{String(r[k])}</div> : null)}</td>
            {valueKeys.map((k) => <td key={k} className="r num">{FLAG_KEYS.includes(k) ? <FlagChip k={k} v={r[k]} /> : fmtKey(k, r[k])}</td>)}
            {t ? <td>{isNum(r[t]) ? <TBar t={r[t] as number} /> : "–"}</td> : null}
            {p ? <td className="r num" style={{ color: toneVar(pTone(r[p])) }}>{pval(r[p])}</td> : null}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------- report cards

export function ReportCard({ rows }: Pick<ViewProps, "rows">) {
  const [open, setOpen] = useState<number | null>(null);
  if (!rows.length) return <Empty />;
  const red = rows.filter((r) => r.flag === "red").length;
  return (
    <div>
      <div style={{ display: "flex", gap: 8, padding: "0 2px 10px" }}>
        <span className={`chip ${red ? "down" : "up"}`}>{red} flagged</span>
        <span className="chip">{rows.length - red} clear</span>
      </div>
      <div style={{ display: "grid", gap: 6 }}>
        {[...rows].sort((a, b) => (a.flag === "red" ? -1 : 0) - (b.flag === "red" ? -1 : 0)).map((r, i) => {
          const bad = r.flag === "red";
          const amber = r.flag === "amber";
          const c = bad ? "var(--down)" : amber ? "var(--warn)" : "var(--up)";
          return (
            <button key={i} onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}
              style={{ textAlign: "left", display: "grid", gridTemplateColumns: "18px 1fr auto", gap: 12, alignItems: "start", padding: "10px 12px", borderRadius: 10, background: bad ? "var(--down-soft)" : "var(--panel-2)", boxShadow: "inset 0 0 0 1px var(--line)" }}>
              <span style={{ marginTop: 4, width: 10, height: 10, borderRadius: 3, background: c }} />
              <span>
                <span style={{ display: "block", fontWeight: 550, color: "var(--text)" }}>{String(r.test)}</span>
                <span style={{ display: "block", color: "var(--text-2)", fontSize: 12.5, marginTop: 2 }}>{String(r.explanation ?? "")}</span>
                {bad || open === i ? <span style={{ display: "block", marginTop: 6, color: bad ? "var(--text)" : "var(--text-3)", fontSize: 12.5 }}><b style={{ fontWeight: 600 }}>Fix: </b>{String(r.recommendation ?? "")}</span> : null}
              </span>
              <span style={{ textAlign: "right" }}>
                <span className="num" style={{ display: "block", color: "var(--text)" }}>{num(r.statistic, 3)}</span>
                <span className="num" style={{ display: "block", color: "var(--text-3)", fontSize: 11 }}>{isNum(r.p_value_or_threshold) ? `p ${pval(r.p_value_or_threshold)}` : String(r.p_value_or_threshold ?? "")}</span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function Scorecard({ rows }: Pick<ViewProps, "rows">) {
  if (!rows.length) return <Empty />;
  const passed = rows.filter((r) => r.pass === true).length;
  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <svg width={56} height={56} viewBox="0 0 56 56" aria-hidden>
          <circle cx={28} cy={28} r={23} fill="none" stroke="var(--grid)" strokeWidth={6} />
          <circle cx={28} cy={28} r={23} fill="none" stroke={passed === rows.length ? "var(--up)" : passed >= rows.length / 2 ? "var(--warn)" : "var(--down)"} strokeWidth={6}
            strokeDasharray={`${(passed / rows.length) * 144.5} 144.5`} strokeLinecap="round" transform="rotate(-90 28 28)" />
          <text x={28} y={28} dy="0.35em" textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--text)" style={{ fontFamily: "var(--mono)" }}>{passed}/{rows.length}</text>
        </svg>
        <div>
          <div style={{ fontWeight: 600 }}>{passed} of {rows.length} placebos passed</div>
          <div className="stat-s">A real effect should beat every fake version of itself.</div>
        </div>
      </div>
      <div style={{ display: "grid", gap: 6 }}>
        {rows.map((r, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "20px 1fr auto", gap: 10, alignItems: "center", padding: "9px 12px", borderRadius: 10, background: "var(--panel-2)", boxShadow: "inset 0 0 0 1px var(--line)" }}>
            <span style={{ display: "grid", placeItems: "center", width: 18, height: 18, borderRadius: 6, background: r.pass ? "var(--up-soft)" : "var(--down-soft)", color: r.pass ? "var(--up)" : "var(--down)", fontSize: 11, fontWeight: 700 }}>{r.pass ? "✓" : "✕"}</span>
            <span>
              <span style={{ display: "block", fontWeight: 550, color: "var(--text)" }}>{label(r.placebo)}</span>
              <span style={{ display: "block", color: "var(--text-3)", fontSize: 12 }}>{String(r.criterion ?? "")}</span>
            </span>
            <span style={{ textAlign: "right" }}>
              <span className="num" style={{ display: "block" }}>{tstat(r.statistic)}</span>
              {isNum(r.p_value) ? <span className="num" style={{ display: "block", fontSize: 11, color: "var(--text-3)" }}>p {pval(r.p_value)}</span> : null}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- publication table

export function PublicationTable({ rows, result }: Pick<ViewProps, "rows" | "result">) {
  if (!rows.length) return <Empty />;
  const cols = Object.keys(rows[0]).filter((k) => !["row", "kind"].includes(k));
  const title = typeof result.meta.table_title === "string" ? result.meta.table_title : "Cross-sectional return predictability";
  const firstStat = rows.findIndex((r) => r.kind === "stat");
  return (
    <div style={{ padding: "18px 22px 22px", borderRadius: 10, background: "var(--bg)", boxShadow: "inset 0 0 0 1px var(--line)" }}>
      <div style={{ textAlign: "center", fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 15, marginBottom: 2 }}>Table 1</div>
      <div style={{ textAlign: "center", fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 15, fontStyle: "italic", marginBottom: 14 }}>{title}</div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 14, fontVariantNumeric: "tabular-nums" }}>
        <thead>
          <tr style={{ borderTop: "1.5px solid var(--text)", borderBottom: "0.75px solid var(--text)" }}>
            <th />
            {cols.map((c) => <th key={c} style={{ padding: "7px 10px", fontWeight: 400, textAlign: "center" }}>{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderTop: i === firstStat ? "0.75px solid var(--text)" : undefined, borderBottom: i === rows.length - 1 ? "1.5px solid var(--text)" : undefined }}>
              <td style={{ padding: r.kind === "se" ? "0 10px 6px" : "6px 10px 1px", color: "var(--text)" }}>{String(r.row ?? "")}</td>
              {cols.map((c) => (
                <td key={c} style={{ padding: r.kind === "se" ? "0 10px 6px" : "6px 10px 1px", textAlign: "center", color: r.kind === "se" ? "var(--text-2)" : "var(--text)" }}>{String(r[c] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ marginTop: 10, fontFamily: "Georgia, serif", fontSize: 12, color: "var(--text-3)" }}>Standard errors in parentheses. *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.1.</p>
    </div>
  );
}

// ---------------------------------------------------------------- exports

export function Latex({ rows, spec }: Pick<ViewProps, "rows" | "spec">) {
  const [copied, setCopied] = useState<number | null>(null);
  const items = rows.filter((r) => typeof r.latex === "string");
  if (!items.length) return <Empty />;
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {items.map((r, i) => {
        const tex = String(r.latex);
        const name = String(r.table ?? spec?.key ?? `table_${i + 1}`);
        return (
          <div key={i} style={{ borderRadius: 10, overflow: "hidden", boxShadow: "inset 0 0 0 1px var(--line)", background: "var(--bg)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 6px 6px 12px", borderBottom: "1px solid var(--line)" }}>
              <span className="num" style={{ color: "var(--text-2)" }}>{name}.tex</span>
              <button className="btn sm ghost" style={{ marginLeft: "auto" }} onClick={() => { void navigator.clipboard.writeText(tex); setCopied(i); setTimeout(() => setCopied(null), 1400); }}>
                {copied === i ? <Check size={12} /> : <Copy size={12} />}{copied === i ? "Copied" : "Copy"}
              </button>
              <button className="btn sm ghost" onClick={() => downloadText(tex, `${name}.tex`, "application/x-tex")}><Download size={12} />Download</button>
            </div>
            <pre className="num" style={{ margin: 0, padding: 14, maxHeight: 300, overflow: "auto", fontSize: 11.5, lineHeight: 1.65, color: "var(--text-2)" }}>{tex}</pre>
          </div>
        );
      })}
    </div>
  );
}

export function CsvExport({ rows }: Pick<ViewProps, "rows">) {
  if (!rows.length) return <Empty />;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {rows.map((r, i) => {
        const name = String(r.name ?? r.table ?? `table_${i + 1}`);
        return (
          <button key={i} className="btn" onClick={() => (typeof r.csv === "string" ? downloadText(r.csv, `${name}.csv`, "text/csv") : downloadCsv(rows, name))}>
            <FileDown size={14} />{label(name)}<span className="num" style={{ color: "var(--text-3)" }}>.csv</span>
          </button>
        );
      })}
    </div>
  );
}

export function PdfExport({ rows, result }: Pick<ViewProps, "rows" | "result">) {
  const row = rows[0];
  const b64 = typeof result.meta.pdf_base64 === "string" ? result.meta.pdf_base64 : null;
  if (!b64) return <Empty text="The PDF is not available for this run." />;
  const name = String(row?.filename ?? "research_table.pdf");
  return (
    <button className="btn" onClick={() => downloadBase64(b64, name, "application/pdf")}>
      <FileDown size={14} />{name}{isNum(row?.bytes) ? <span className="num" style={{ color: "var(--text-3)" }}>{Math.round((row.bytes as number) / 1024)} KB</span> : null}
    </button>
  );
}

export function Prose({ rows }: Pick<ViewProps, "rows">) {
  const row = rows[0];
  if (!row) return <Empty />;
  const text = ["summary", "headline", "message", "verdict", "statement", "assessment", "explanation"].map((k) => row[k]).find((v): v is string => typeof v === "string");
  const rest = Object.fromEntries(Object.entries(row).filter(([, v]) => v !== text));
  return (
    <div style={{ display: "grid", gap: 14 }}>
      {text ? <p style={{ fontSize: 14, lineHeight: 1.6, color: "var(--text)", maxWidth: "70ch" }}>{text}</p> : null}
      {Object.keys(rest).length ? <Facts rows={[rest]} /> : null}
    </div>
  );
}
