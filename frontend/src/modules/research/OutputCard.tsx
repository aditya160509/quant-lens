"use client";

import { createElement, useState, useRef, type ReactNode } from "react";
import { BookOpen, Copy, Download, EyeOff, Maximize2, MoreHorizontal, Minimize2, Settings2, Table2, BarChart3, X } from "lucide-react";
import { downloadCsv, downloadPng, downloadSvg } from "@/charts/export";
import { useLayout } from "@/workspace/layout";
import { MenuItem, PopMenu, Tooltip, type MenuAt } from "@/workspace/ui";
import { label, out } from "./format";
import type { Item } from "./layouts";
import { CHART_VIEWS, viewFor } from "./outputs/registry";
import type { FeatureResult, FeatureSpec } from "./types";

export function OutputCard({ item, feature, result, maximized, onToggleMax, onHide, scope }: {
  item: Item;
  feature: FeatureSpec;
  result: FeatureResult;
  maximized: boolean;
  onToggleMax: () => void;
  onHide?: () => void;
  scope: string;
}) {
  const body = useRef<HTMLDivElement>(null);
  const key = item.keys[0];
  const spec = feature.outputs.find((o) => o.key === key);
  const viewName = item.view ?? spec?.render ?? "dataTable";
  const rows = out(result, key);
  const isChart = CHART_VIEWS.has(viewName);
  const [asTable, setAsTable] = useState(false);
  const [menu, setMenu] = useState<MenuAt | null>(null);
  const [about, setAbout] = useState(false);
  const title = item.title ?? spec?.title ?? label(key);
  const hint = item.hint ?? spec?.description;
  const name = `${feature.id}_${key}`;
  const svg = () => body.current?.querySelector("svg[role='img']") as SVGSVGElement | null;

  const canTable = isChart && rows.length > 0;
  const copy = () => {
    const cols = Object.keys(rows[0] ?? {});
    const tsv = [cols.join("\t"), ...rows.map((r) => cols.map((c) => String(r[c] ?? "")).join("\t"))].join("\n");
    void navigator.clipboard?.writeText(tsv);
  };
  const exportable = rows.length > 0 && !["latex", "csv", "pdf"].includes(viewName);
  const openSettings = () => { useLayout.getState().set("right", true, true); };

  return (
    <section className="card" id={`out-${key}`} aria-labelledby={`h-${key}`} style={maximized ? { minHeight: "100%" } : undefined}
      onContextMenu={(e) => { e.preventDefault(); setMenu({ x: e.clientX, y: e.clientY }); }}>
      <header className="card-h">
        <div style={{ minWidth: 0, display: "grid" }}>
          <h3 id={`h-${key}`}>{title}</h3>
          {hint ? <span className="sub">{hint}</span> : null}
        </div>
        <div className="tools">
          {canTable ? (
            <Tooltip label={asTable ? "Show chart" : "Show table"}>
              <button className="btn sm icon ghost" onClick={() => setAsTable((v) => !v)} aria-label={asTable ? "Show chart" : "Show table"} aria-pressed={asTable}>{asTable ? <BarChart3 size={13} /> : <Table2 size={13} />}</button>
            </Tooltip>
          ) : null}
          {isChart && !asTable ? (
            <>
              <ToolButton label="Download SVG" onClick={() => { const s = svg(); if (s) downloadSvg(s, name); }}>SVG</ToolButton>
              <ToolButton label="Download PNG" onClick={() => { const s = svg(); if (s) void downloadPng(s, name); }}>PNG</ToolButton>
            </>
          ) : null}
          {rows.length && !["latex", "csv", "pdf"].includes(viewName) ? <ToolButton label="Download CSV" onClick={() => downloadCsv(rows, name)}>CSV</ToolButton> : null}
          <Tooltip label="More">
            <button className="btn sm icon ghost" aria-haspopup="menu" aria-label="More actions" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setMenu({ x: r.right - 220, y: r.bottom + 4 }); }}><MoreHorizontal size={13} /></button>
          </Tooltip>
          <Tooltip label={maximized ? <span>Restore <span className="kbd">Esc</span></span> : "Expand"}>
            <button className="btn sm icon ghost" onClick={onToggleMax} aria-label={maximized ? "Restore" : "Expand"}>
              {maximized ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
            </button>
          </Tooltip>
        </div>
      </header>
      <div ref={body} className={`card-b${item.flush ? " flush" : ""}`}>
        {createElement(viewFor(asTable && isChart ? "dataTable" : viewName), { rows, result, feature, spec, keys: item.keys, opts: item.opts, scope })}
      </div>
      <PopMenu at={menu} onClose={() => setMenu(null)}>
        {rows.length ? <MenuItem icon={<Copy size={13} />} onClick={copy}>Copy data</MenuItem> : null}
        {onHide ? <MenuItem icon={<EyeOff size={13} />} onClick={onHide}>Hide</MenuItem> : null}
        <MenuItem icon={maximized ? <Minimize2 size={13} /> : <Maximize2 size={13} />} onClick={onToggleMax} hint={maximized ? "Esc" : undefined}>{maximized ? "Restore" : "Expand"}</MenuItem>
        {canTable ? <MenuItem icon={asTable ? <BarChart3 size={13} /> : <Table2 size={13} />} onClick={() => setAsTable((v) => !v)}>{asTable ? "Show chart" : "Show table"}</MenuItem> : null}
        {isChart && !asTable ? <><div className="sep" />
          <MenuItem icon={<Download size={13} />} onClick={() => { const sv = svg(); if (sv) downloadSvg(sv, name); }}>Export SVG</MenuItem>
          <MenuItem icon={<Download size={13} />} onClick={() => { const sv = svg(); if (sv) void downloadPng(sv, name); }}>Export PNG</MenuItem></> : null}
        {exportable ? <MenuItem icon={<Download size={13} />} onClick={() => downloadCsv(rows, name)}>Export CSV</MenuItem> : null}
        <div className="sep" />
        <MenuItem icon={<Settings2 size={13} />} onClick={openSettings}>Settings</MenuItem>
        <MenuItem icon={<BookOpen size={13} />} onClick={() => setAbout(true)}>About this method</MenuItem>
      </PopMenu>
      {about ? <MethodDrawer title={title} hint={hint} feature={feature} result={result} onClose={() => setAbout(false)} /> : null}
    </section>
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

function ToolButton({ label: l, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return <button className="btn sm ghost" style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--text-3)" }} onClick={onClick} aria-label={l} title={l}>{children}</button>;
}
