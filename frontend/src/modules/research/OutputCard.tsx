"use client";

import { createElement, useState, useRef } from "react";
import { ArrowDown, ArrowUp, BookOpen, RotateCcw, Pin, Check, ChevronDown, Copy, Download, EyeOff, Maximize2, MoreHorizontal, Minimize2, Settings2, Table2, BarChart3, X } from "lucide-react";
import { Exhibit } from "@/kit/Exhibit";
import { download, downloadCsv, downloadJson, downloadPng, downloadSvg, downloadTickers, downloadXlsx } from "@/charts/export";
import { Empty } from "@/kit/DataTable";
import { useLayout } from "@/workspace/layout";
import { MenuItem, PopMenu, Tooltip, type MenuAt } from "@/workspace/ui";
import { label, out } from "./format";
import type { Item } from "./layouts";
import { ALT_VIEWS, CHART_VIEWS, viewFor } from "./outputs/registry";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { Explore, ExploreControls, VIEW_LABEL, defaults, overlay, useExplore, viewsFor, type ViewKind } from "./outputs/explore";
import { useJob, useRuns } from "./api";
import { lab } from "./lab";
import { cardId, usePins } from "./cardPrefs";
import type { FeatureResult, FeatureSpec } from "./types";

/** Which designed lens a reader picked for a card, remembered on this device. */
const useLens = create<{ lens: Record<string, string>; set: (id: string, view: string | null) => void }>()(
  persist((set) => ({ lens: {}, set: (id, view) => set((s) => { const lens = { ...s.lens }; if (view) lens[id] = view; else delete lens[id]; return { lens }; }) }),
    { name: "lab-card-lens", storage: createJSONStorage(() => localStorage), version: 1 }),
);

export function OutputCard({ item, feature, result, maximized, onToggleMax, onHide, onMove, onSpan, onDuplicate, scope, index }: {
  item: Item;
  feature: FeatureSpec;
  result: FeatureResult;
  maximized: boolean;
  onToggleMax: () => void;
  onHide?: () => void;
  onMove?: (d: -1 | 1) => void;
  onSpan?: (span: number) => void;
  onDuplicate?: () => void;
  scope: string;
  /** Exhibit number on the page, for labs that number them. */
  index?: number;
}) {
  const body = useRef<HTMLDivElement>(null);
  const key = item.keys[0];
  const spec = feature.outputs.find((o) => o.key === key);
  const designed = item.view ?? spec?.render ?? "dataTable";
  const dup = item.copy ? `#${item.copy}` : "";
  const lensId = `${feature.id}:${key}:${designed}${dup}`;
  const alts = ALT_VIEWS[designed] ?? [];
  const lens = useLens((st) => st.lens[lensId]);
  const setLens = useLens((st) => st.set);
  const viewName = lens && alts.some((a) => a.view === lens) ? lens : designed;
  const rows = out(result, key);
  const isChart = CHART_VIEWS.has(viewName);
  const cfgId = `${feature.id}:${key}:${item.view ?? ""}${dup}`;
  const own = useExplore((st) => st.configs[cfgId]);
  const typeDefault = useExplore((st) => st.configs[`type:${viewName}`]);
  // A reader's default for this kind of output applies until they choose something for this card.
  const custom = own ?? (typeDefault && rows.length && viewsFor(rows).includes(typeDefault.kind) ? defaults(rows, typeDefault.kind) : undefined);
  const setCustom = useExplore((st) => st.set);
  const asTable = custom?.kind === "table";
  const setAsTable = (f: (v: boolean) => boolean) => setCustom(cfgId, f(asTable) ? { kind: "table" } : null);
  const [viewMenu, setViewMenu] = useState<MenuAt | null>(null);
  const kinds: ViewKind[] = rows.length ? viewsFor(rows) : [];
  // Overlay: the same output from another finished run of this feature, drawn on one axis.
  const currentJob = scope.split(":")[1];
  const others = useRuns((st) => st.runs).filter((r) => r.featureId === feature.id && r.status === "completed" && r.jobId !== currentJob).slice(0, 6);
  const [overlayId, setOverlayId] = useState<string | null>(null);
  const other = useJob(overlayId);
  const otherRows = other.data?.result ? out(other.data.result, key) : [];
  const merged = overlayId && otherRows.length ? overlay(rows, otherRows) : null;
  const canOverlay = kinds.some((k) => k === "line");
  const pinned = usePins((st) => st.pins.some((p) => p.featureId === feature.id && p.card === cardId(item)));
  const togglePin = usePins((st) => st.toggle);
  const [menu, setMenu] = useState<MenuAt | null>(null);
  const [about, setAbout] = useState(false);
  const title = item.title ?? spec?.title ?? label(key);
  const hint = item.hint ?? spec?.description;
  const finding = custom || overlayId ? null : lab().takeaway?.(feature.id, key, item.view, result) ?? null;
  const name = `${feature.id}_${key}`;
  const svg = () => body.current?.querySelector("svg[role='img'], svg[role='group']") as SVGSVGElement | null;

  const canTable = isChart && rows.length > 0;
  const cols = Object.keys(rows[0] ?? {});
  const cell = (v: unknown) => (v === null || v === undefined ? "" : String(v));
  const tsv = () => [cols.join("\t"), ...rows.map((r) => cols.map((c) => cell(r[c]).replace(/[\t\n]/g, " ")).join("\t"))].join("\n");
  const markdown = () => [`| ${cols.join(" | ")} |`, `|${cols.map(() => " --- ").join("|")}|`, ...rows.map((r) => `| ${cols.map((c) => cell(r[c]).replace(/\|/g, "\\|")).join(" | ")} |`)].join("\n");
  const copy = () => void navigator.clipboard?.writeText(tsv());
  // An output the run returned as an empty list: say so instead of drawing an empty frame.
  const raw = result.tables?.[key] ?? result.charts?.[key] ?? result.sections?.[key];
  const empty = Array.isArray(raw) && raw.length === 0;
  const exportable = rows.length > 0 && !["latex", "csv", "pdf"].includes(viewName);
  const openSettings = () => { useLayout.getState().set("right", true, true); };
  const chartKind = kinds.find((k) => k !== "table");
  const [editing, setEditing] = useState(0);
  const editChart = () => { if (!custom && chartKind) setCustom(cfgId, defaults(rows, chartKind)); setEditing((n) => n + 1); };

  return (
    <Exhibit id={key} name={title} finding={finding} hint={hint} note={item.note} flush={item.flush} bodyRef={body}
      style={maximized ? { minHeight: "100%" } : undefined} onContextMenu={(e) => { e.preventDefault(); setMenu({ x: e.clientX, y: e.clientY }); }}
      tools={<>
          {item.toggle && alts.length && !custom ? (
            <div className="ub-seg card-toggle" role="radiogroup" aria-label="View">
              {[{ label: item.toggle, view: designed }, ...alts].map((a) => <button key={a.view} type="button" role="radio" aria-checked={viewName === a.view} onClick={() => setLens(lensId, a.view === designed ? null : a.view)}>{a.label}</button>)}
            </div>
          ) : (kinds.length > 1 || alts.length > 0) && viewName !== "latex" ? (
            <button className="btn sm ghost view-as" aria-haspopup="menu" aria-label="View as" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setViewMenu({ x: r.right - 200, y: r.bottom + 4 }); }}>
              {custom ? VIEW_LABEL[custom.kind] : "View"}<ChevronDown size={11} />
            </button>
          ) : null}
          <Tooltip label="More">
            <button className="btn sm icon ghost" aria-haspopup="menu" aria-label="More actions" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setMenu({ x: r.right - 220, y: r.bottom + 4 }); }}><MoreHorizontal size={13} /></button>
          </Tooltip>
          <Tooltip label={maximized ? <span>Restore <span className="kbd">Esc</span></span> : "Expand"}>
            <button className="btn sm icon ghost" onClick={onToggleMax} aria-label={maximized ? "Restore" : "Expand"}>
              {maximized ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
            </button>
          </Tooltip>
      </>}
      after={<>
      <PopMenu at={viewMenu} onClose={() => setViewMenu(null)} width={200}>
        <div className="hd">View as</div>
        <MenuItem icon={!custom && viewName === designed ? <Check size={13} /> : <span style={{ width: 13 }} />} onClick={() => { setCustom(cfgId, null); setLens(lensId, null); }}>Designed view</MenuItem>
        {alts.map((a) => (
          <MenuItem key={a.view} icon={!custom && viewName === a.view ? <Check size={13} /> : <span style={{ width: 13 }} />} onClick={() => { setCustom(cfgId, null); setLens(lensId, a.view); }}>{a.label}</MenuItem>
        ))}
        <div className="sep" />
        {kinds.map((k) => (
          <MenuItem key={k} icon={custom?.kind === k ? <Check size={13} /> : <span style={{ width: 13 }} />} onClick={() => setCustom(cfgId, defaults(rows, k))}>{VIEW_LABEL[k]}</MenuItem>
        ))}
        {custom ? <><div className="sep" /><MenuItem icon={<span style={{ width: 13 }} />} onClick={() => setCustom(`type:${viewName}`, { kind: custom.kind })}>Use {VIEW_LABEL[custom.kind]} for every output like this</MenuItem></> : null}
        {typeDefault ? <MenuItem icon={<span style={{ width: 13 }} />} onClick={() => setCustom(`type:${viewName}`, null)}>Forget the default for this output type</MenuItem> : null}
        {canOverlay && others.length ? <><div className="sep" /><div className="hd">Overlay another run</div>
          {others.map((r) => (
            <MenuItem key={r.jobId} icon={overlayId === r.jobId ? <Check size={13} /> : <span style={{ width: 13 }} />} onClick={() => setOverlayId(r.jobId)}>
              {new Date(r.startedAt).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}{r.sweep ? ` · ${label(r.sweep.key)} ${r.sweep.value}` : ""}
            </MenuItem>
          ))}</> : null}
      </PopMenu>
      <PopMenu at={menu} onClose={() => setMenu(null)}>
        {rows.length ? <MenuItem icon={<Copy size={13} />} onClick={copy}>Copy data</MenuItem> : null}
        {rows.length ? <MenuItem icon={<Copy size={13} />} onClick={() => void navigator.clipboard?.writeText(markdown())}>Copy as Markdown</MenuItem> : null}
        {currentJob && currentJob !== "draft" ? <MenuItem icon={<Pin size={13} />} onClick={() => togglePin({ featureId: feature.id, card: cardId(item), jobId: currentJob })}>{pinned ? "Unpin from board" : "Pin to board"}</MenuItem> : null}
        {onDuplicate ? <MenuItem icon={<Copy size={13} />} onClick={onDuplicate}>Duplicate</MenuItem> : null}
        {onHide ? <MenuItem icon={<EyeOff size={13} />} onClick={onHide}>{item.copy ? "Remove copy" : "Hide"}</MenuItem> : null}
        <MenuItem icon={maximized ? <Minimize2 size={13} /> : <Maximize2 size={13} />} onClick={onToggleMax} hint={maximized ? "Esc" : undefined}>{maximized ? "Restore" : "Expand"}</MenuItem>
        {canTable ? <MenuItem icon={asTable ? <BarChart3 size={13} /> : <Table2 size={13} />} onClick={() => setAsTable((v) => !v)}>{asTable ? "Show chart" : "Show table"}</MenuItem> : null}
        {isChart && !asTable ? <><div className="sep" />
          <MenuItem icon={<Download size={13} />} onClick={() => { const sv = svg(); if (sv) downloadSvg(sv, name); }}>Export SVG</MenuItem>
          <MenuItem icon={<Download size={13} />} onClick={() => { const sv = svg(); if (sv) void downloadPng(sv, name); }}>Export PNG</MenuItem></> : null}
        {exportable ? <MenuItem icon={<Download size={13} />} onClick={() => downloadCsv(rows, name)}>Export CSV</MenuItem> : null}
        {exportable ? <MenuItem icon={<Download size={13} />} onClick={() => download(`${name}.tsv`, new Blob([tsv()], { type: "text/tab-separated-values" }))}>Export TSV</MenuItem> : null}
        {exportable && lab().id === "screener" ? <MenuItem icon={<Download size={13} />} onClick={() => downloadJson(rows, name, (result.meta as { limitations?: string[] }).limitations)}>Export JSON</MenuItem> : null}
        {exportable && lab().id === "screener" ? <MenuItem icon={<Download size={13} />} onClick={() => void downloadXlsx(rows, name, `${lab().base}/export/xlsx`)}>Export Excel</MenuItem> : null}
        {exportable && lab().id === "screener" && "ticker" in rows[0] ? <MenuItem icon={<Download size={13} />} onClick={() => downloadTickers(rows, name)}>Export tickers</MenuItem> : null}
        {onSpan ? <><div className="sep" /><div className="hd">Width</div>
          <div className="menu-seg">{[[4, "⅓"], [6, "½"], [8, "⅔"], [12, "Full"]].map(([sp, t]) => (
            <button key={sp} type="button" aria-pressed={item.span === sp} onClick={() => { onSpan(sp as number); setMenu(null); }}>{t}</button>
          ))}</div></> : null}
        {onMove ? <>
          <MenuItem icon={<ArrowUp size={13} />} onClick={() => onMove(-1)}>Move earlier</MenuItem>
          <MenuItem icon={<ArrowDown size={13} />} onClick={() => onMove(1)}>Move later</MenuItem></> : null}
        <div className="sep" />
        {chartKind ? <MenuItem icon={<BarChart3 size={13} />} onClick={editChart}>Chart settings</MenuItem> : null}
        <MenuItem icon={<Settings2 size={13} />} onClick={openSettings}>Run settings</MenuItem>
        <MenuItem icon={<BookOpen size={13} />} onClick={() => setAbout(true)}>About this method</MenuItem>
        {custom || lens || overlayId ? <MenuItem icon={<RotateCcw size={13} />} onClick={() => { setCustom(cfgId, null); setLens(lensId, null); setOverlayId(null); }}>Reset this card</MenuItem> : null}
        <MenuItem icon={<RotateCcw size={13} />} onClick={() => { useExplore.setState({ configs: {} }); useLens.setState({ lens: {} }); }}>Reset every card to its designed view</MenuItem>
      </PopMenu>
      {about ? <MethodDrawer title={title} hint={hint} feature={feature} result={result} onClose={() => setAbout(false)} /> : null}
      </>}>
        {empty && !custom && !overlayId ? <Empty text={`No rows for ${title.toLowerCase()} with these settings.`} /> : overlayId ? (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: 12, color: "var(--text-3)" }}>
              <span>Overlay: <b style={{ color: "var(--text)", fontWeight: 500 }}>B</b> = run from {new Date(others.find((r) => r.jobId === overlayId)?.startedAt ?? 0).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
              <button className="btn sm ghost" style={{ marginLeft: "auto" }} onClick={() => setOverlayId(null)}><X size={12} />Remove overlay</button>
            </div>
            {merged ? <Explore rows={merged.rows} config={merged.config} /> : <div style={{ color: "var(--text-3)", fontSize: 12.5 }}>{other.isLoading ? "Loading run B…" : "That run is no longer on the server, or has no data for this output."}</div>}
          </div>
        ) : custom ? (
          <>
            <ExploreControls key={editing} rows={rows} config={custom} onChange={(c) => setCustom(cfgId, c)} startOpen={editing > 0} />
            <Explore rows={rows} config={custom} />
          </>
        ) : createElement(viewFor(viewName), { rows, result, feature, spec, keys: item.keys, opts: item.opts, scope })}
    </Exhibit>
  );
}

function MethodDrawer({ title, hint, feature, result, onClose }: { title: string; hint?: string; feature: FeatureSpec; result: FeatureResult; onClose: () => void }) {
  const assumptions = feature.inputs.filter((i) => i.help).slice(0, 12);
  return (
    <aside className="drawer" role="dialog" aria-label="About this method">
      <div style={{ display: "flex", alignItems: "center", marginBottom: 10 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--text)", flex: 1 }}>{title}</h3>
        <button className="btn sm icon ghost" onClick={onClose} aria-label="Close"><X size={13} /></button>
      </div>
      {hint ? <p style={{ marginBottom: 12 }}>{hint}</p> : null}
      <h4 className="insp-h">{feature.name}</h4>
      <p style={{ marginBottom: 14 }}>{feature.description}</p>
      {assumptions.length ? <><h4 className="insp-h">Inputs and assumptions</h4>
        <dl style={{ margin: "0 0 14px" }}>{assumptions.map((i) => <div key={i.key} style={{ marginBottom: 8 }}><dt style={{ color: "var(--text)", fontWeight: 500 }}>{i.label}</dt><dd style={{ margin: 0 }}>{i.help}</dd></div>)}</dl></> : null}
      {result.meta.research_caveats?.length ? <><h4 className="insp-h">Caveats</h4><ul style={{ paddingLeft: 18 }}>{result.meta.research_caveats.map((c) => <li key={c}>{c}</li>)}</ul></> : null}
    </aside>
  );
}
