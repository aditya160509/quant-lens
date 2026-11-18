"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Title } from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { Check, ChartLine, Filter, PanelRightOpen, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Monogram, openQuickLook, useQuickLook } from "@/kit/QuickLook";
import { fetchLookup, searchSymbols, usePopular, useSavedScreens, type SymbolHit } from "@/kit/QuickLookData";
import { useStudies } from "@/modules/research/store";
import { Chip, Tooltip } from "@/workspace/ui";
import type { PaletteItem } from "@/workspace/WorkspaceShell";
import { addToScreen, fuzzy, screenSector, useRecent } from "./state";
import "./search.css";

type Tab = "all" | "symbols" | "screens" | "runs" | "actions";
const TABS: { id: Tab; label: string }[] = [{ id: "all", label: "All" }, { id: "symbols", label: "Symbols" }, { id: "screens", label: "Screens" }, { id: "runs", label: "Runs" }, { id: "actions", label: "Actions" }];
const UNKNOWN = "Unknown";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => { const id = setTimeout(() => setV(value), ms); return () => clearTimeout(id); }, [value, ms]);
  return v;
}

/** One name: monogram, ticker, company, type, exchange. */
export function SymbolRow({ hit }: { hit: SymbolHit }) {
  return (
    <>
      <Monogram ticker={hit.ticker} />
      <b className="so-tk">{hit.ticker}</b>
      <span className="so-nm">{hit.company_name ?? UNKNOWN}</span>
      <Chip>{hit.type}</Chip>
      <span className="so-ex">{hit.exchange}</span>
    </>
  );
}

/** Large search from anywhere: symbols, saved screens, runs and actions in one overlay. */
export function SearchOverlay({ open, onOpenChange, items, themeClass, className }: {
  open: boolean; onOpenChange: (o: boolean) => void; items: PaletteItem[]; themeClass: string; className: string;
}) {
  const router = useRouter();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("all");
  const [text, setText] = useState("");
  const [exchange, setExchange] = useState<string | null>(null);
  const [value, setValue] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const q = useDebounced(text.trim(), 120);
  const recent = useRecent((s) => s.tickers);
  const popular = usePopular();
  const screens = useSavedScreens();
  const wantSymbols = tab === "all" || tab === "symbols";
  const found = useQuery({ queryKey: ["symbol-search", q, exchange], queryFn: ({ signal }) => searchSymbols(q, exchange, signal), enabled: open && wantSymbols && (q.length > 0 || exchange !== null), placeholderData: keepPreviousData, retry: false });

  useEffect(() => { if (open) { setText(""); setExchange(null); setTab("all"); setValue(""); } }, [open]);

  const typing = q.length > 0 || exchange !== null;
  const symbols: SymbolHit[] = useMemo(() => {
    if (typing) return found.data?.results ?? [];
    const pop = popular.data?.results ?? [];
    const byTicker = new Map(pop.map((p) => [p.ticker, p]));
    return [...recent.map((t) => byTicker.get(t) ?? { ticker: t, company_name: null, type: "Stock", exchange: UNKNOWN }), ...pop.filter((p) => !recent.includes(p.ticker))];
  }, [typing, found.data, popular.data, recent]);
  const groupOf = (it: PaletteItem) => (it.group === "Recent runs" ? "runs" : "actions");
  const savedScreens = useMemo(() => fuzzy(screens.data?.screens ?? [], (s) => s.name, text), [screens.data, text]);
  const runs = useMemo(() => fuzzy(items.filter((i) => groupOf(i) === "runs"), (i) => `${i.label} ${i.meta ?? ""}`, text), [items, text]);
  const actions = useMemo(() => fuzzy(items.filter((i) => groupOf(i) === "actions"), (i) => `${i.label} ${(i.keywords ?? []).join(" ")}`, text), [items, text]);

  const close = () => onOpenChange(false);
  const loadScreen = (id: string) => {
    const s = screens.data?.screens.find((x) => x.screen_id === id);
    if (!s) return;
    useStudies.setState((st) => ({ forms: { ...st.forms, [`sc${s.feature_id}`]: (s as unknown as { payload: Record<string, unknown> }).payload } }));
    close();
    router.push("/screener/screen");
  };
  const mark = (id: string) => { setDone(id); setTimeout(() => setDone((d) => (d === id ? null : d)), 1400); };

  const act = {
    overview: (t: string) => { close(); openQuickLook(t, "overview"); useQuickLook.getState().setRange("1Y"); },
    chart: (t: string) => { close(); openQuickLook(t, "overview"); useQuickLook.getState().setRange("10Y"); },
    add: (t: string) => { addToScreen(t); mark(`add:${t}`); },
    sector: async (t: string) => {
      const sector = (await qc.ensureQueryData({ queryKey: ["lookup", t], queryFn: () => fetchLookup(t), staleTime: 300_000 }).catch(() => null))?.sector;
      if (!sector) { mark(`sec-fail:${t}`); return; }
      screenSector(sector); close(); router.push("/screener/screen");
    },
  };

  const selected = value.startsWith("sym:") ? value.slice(4) : null;
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Tab") { e.preventDefault(); const i = TABS.findIndex((t) => t.id === tab); setTab(TABS[(i + (e.shiftKey ? TABS.length - 1 : 1)) % TABS.length].id); return; }
    if (e.key !== "Enter" || !selected) return;
    if (e.metaKey || e.ctrlKey) { e.preventDefault(); act.chart(selected); }
    else if (e.shiftKey) { e.preventDefault(); act.add(selected); }
    else if (e.altKey) { e.preventDefault(); void act.sector(selected); }
  };

  const showSymbols = wantSymbols && symbols.length > 0;
  const shownSymbols = tab === "all" ? symbols.slice(0, 8) : symbols;
  const empty = !(showSymbols || (["all", "screens"].includes(tab) && savedScreens.length) || (["all", "runs"].includes(tab) && runs.length) || (["all", "actions"].includes(tab) && actions.length));
  const loading = wantSymbols && (typing ? found.isFetching && !found.data : popular.isLoading);

  return (
    <Command.Dialog open={open} onOpenChange={onOpenChange} label="Search" shouldFilter={false} value={value} onValueChange={setValue} onKeyDown={onKeyDown}
      overlayClassName={`cmdk-overlay${themeClass}`} contentClassName={`cmdk so ws-tokens${themeClass} ${className}`}>
      <Title className="sr-only">Search</Title>
      <div className="so-input">
        <Search size={16} strokeWidth={1.75} aria-hidden />
        <Command.Input value={text} onValueChange={setText} placeholder="Search names, screens, runs, actions" />
        <span className="kbd">esc</span>
      </div>
      <div className="so-tabs" role="tablist" aria-label="Result type">
        {TABS.map((t) => <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>{t.label}</button>)}
      </div>
      {wantSymbols && (popular.data?.exchanges.length ?? 0) > 1 ? (
        <div className="so-chips" role="group" aria-label="Exchange">
          {popular.data!.exchanges.map((x) => <button key={x.name} className="pill" aria-pressed={exchange === x.name} onClick={() => setExchange(exchange === x.name ? null : x.name)}>{x.name}<span className="num">{x.count.toLocaleString()}</span></button>)}
        </div>
      ) : null}
      <Command.List>
        {loading ? <div className="so-state" role="status">Searching</div> : null}
        {found.error && typing ? <div className="so-state err" role="alert">{(found.error as Error).message}</div> : null}
        {!loading && empty ? <Command.Empty>{typing ? "No matches" : "Nothing yet"}</Command.Empty> : null}
        {showSymbols ? (
          <Command.Group heading={typing ? `Symbols${found.data && found.data.total > shownSymbols.length ? ` · ${shownSymbols.length} of ${found.data.total.toLocaleString()}` : ""}` : recent.length ? "Recent and popular" : "Popular"}>
            {shownSymbols.map((h) => (
              <Command.Item key={h.ticker} value={`sym:${h.ticker}`} onSelect={() => act.overview(h.ticker)} className="so-item">
                <SymbolRow hit={h} />
                <span className="so-acts" onClick={(e) => e.stopPropagation()} onPointerDown={(e) => e.preventDefault()}>
                  <Tooltip label={<span>Chart <span className="kbd">⌘↵</span></span>}><button aria-label={`${h.ticker} chart`} onClick={() => act.chart(h.ticker)}><ChartLine size={14} /></button></Tooltip>
                  <Tooltip label={<span>Overview <span className="kbd">↵</span></span>}><button aria-label={`${h.ticker} overview`} onClick={() => act.overview(h.ticker)}><PanelRightOpen size={14} /></button></Tooltip>
                  <Tooltip label={<span>Add to screen <span className="kbd">⇧↵</span></span>}><button aria-label={`Add ${h.ticker} to screen`} onClick={() => act.add(h.ticker)}>{done === `add:${h.ticker}` ? <Check size={14} /> : <Filter size={14} />}</button></Tooltip>
                  <Tooltip label={<span>Screen its sector <span className="kbd">⌥↵</span></span>}><button aria-label={`Screen ${h.ticker}'s sector`} onClick={() => void act.sector(h.ticker)}>{done === `sec-fail:${h.ticker}` ? UNKNOWN : "Sector"}</button></Tooltip>
                </span>
              </Command.Item>
            ))}
          </Command.Group>
        ) : null}
        {["all", "screens"].includes(tab) && savedScreens.length ? (
          <Command.Group heading="Screens">
            {savedScreens.map((s) => <Command.Item key={s.screen_id} value={`screen:${s.screen_id}`} onSelect={() => loadScreen(s.screen_id)} className="so-item"><span className="so-nm">{s.name}</span></Command.Item>)}
          </Command.Group>
        ) : null}
        {["all", "runs"].includes(tab) && runs.length ? (
          <Command.Group heading="Runs">
            {runs.map((i) => <Command.Item key={i.id} value={`run:${i.id}`} onSelect={() => { close(); i.run(); }} className="so-item"><span className="so-nm">{i.label}</span>{i.meta ? <span className="so-ex">{i.meta}</span> : null}</Command.Item>)}
          </Command.Group>
        ) : null}
        {["all", "actions"].includes(tab) && actions.length ? (
          <Command.Group heading="Actions">
            {actions.map((i) => {
              const Icon = i.icon;
              return <Command.Item key={i.id} value={`act:${i.id}`} onSelect={() => { close(); i.run(); }} className="so-item">{Icon ? <Icon size={15} strokeWidth={1.6} /> : null}<span className="so-nm">{i.label}</span>{i.meta ? <span className="so-ex">{i.meta}</span> : null}</Command.Item>;
            })}
          </Command.Group>
        ) : null}
      </Command.List>
    </Command.Dialog>
  );
}
