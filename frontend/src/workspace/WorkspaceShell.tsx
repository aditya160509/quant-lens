"use client";

import { exportPrefs, importPrefs, pullPrefs, pushPrefs } from "./prefsSync";
import "./workspace.css";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, useSyncExternalStore, type KeyboardEvent as ReactKeyEvent, type ReactNode } from "react";
import {
  Activity, BrainCircuit, ChartNetwork, Command as CommandIcon, FlaskConical, Home, ListFilter, CloudDownload, CloudUpload, FileDown, FileUp, Moon, Orbit, PanelBottom, PanelLeft, PanelRight,
  PieChart, Search, ChevronDown, Settings2, SlidersHorizontal, Sun, type LucideIcon, CandlestickChart } from "lucide-react";
import * as Popover from "@radix-ui/react-popover";
import { QuickLook } from "@/kit/QuickLook";
import { SearchOverlay } from "@/modules/screener/search/SearchOverlay";
import { MODULES, type ModuleLink } from "./modules";
import { SHORTCUTS, useLayout, type Region } from "./layout";
import { prefClasses, usePrefs, type Accent, type Density, type LineWeight, type Palette } from "./prefs";
import { Segmented, Tooltip } from "./ui";

export type Theme = "dark" | "light";

/** One switcher for every module (JetBrains project widget): modules on the left, the hovered module's pages on the right. */
function ModuleSwitcher({ current, themeClass, className }: { current: ModuleLink | undefined; themeClass: string; className: string }) {
  const [open, setOpen] = useState(false);
  const [hot, setHot] = useState(current?.id ?? MODULES[0].id);
  const shown = MODULES.find((x) => x.id === hot) ?? MODULES[0];
  const Icon = current?.icon ?? Home;
  const nav = (e: ReactKeyEvent<HTMLDivElement>) => {
    if (!["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft"].includes(e.key)) return;
    e.preventDefault();
    const col = (document.activeElement as HTMLElement)?.closest("[data-col]")?.getAttribute("data-col") ?? "m";
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.currentTarget.querySelector<HTMLElement>(`[data-col="${e.key === "ArrowRight" ? "p" : "m"}"] a`)?.focus(); return; }
    const links = [...e.currentTarget.querySelectorAll<HTMLAnchorElement>(`[data-col="${col}"] a`)];
    const i = links.indexOf(document.activeElement as HTMLAnchorElement);
    links[(i + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length]?.focus();
  };
  return (
    <Popover.Root open={open} onOpenChange={(o) => { setOpen(o); if (o) setHot(current?.id ?? MODULES[0].id); }}>
      <Popover.Trigger asChild>
        <button type="button" className="ws-switch" aria-label="Switch module">
          <span className="tile"><Icon size={14} strokeWidth={1.8} /></span>{current?.label ?? "Home"}<ChevronDown size={13} strokeWidth={2} aria-hidden />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className={`pop ws-switch-pop ws-tokens${themeClass} ${className}`} align="start" sideOffset={8} onKeyDown={nav}>
          <div data-col="m" className="col">
            {MODULES.map((x) => {
              const I = x.icon;
              return (
                <Link key={x.id} href={x.href} className="mod" data-hot={x.id === hot || undefined} aria-current={x.id === current?.id ? "page" : undefined}
                  onMouseEnter={() => setHot(x.id)} onFocus={() => setHot(x.id)} onClick={() => setOpen(false)}>
                  <span className="tile"><I size={15} strokeWidth={1.8} /></span>
                  <span><b>{x.label}</b><small>{x.blurb}</small></span>
                </Link>
              );
            })}
          </div>
          <div data-col="p" className="col pages">
            <div className="hd">{shown.label}</div>
            {shown.pages?.map((p) => <Link key={p.href} href={p.href} className="item" onClick={() => setOpen(false)}>{p.label}</Link>)}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

/** The current module's pages as header tabs: pages change often, so they get the cheapest control. */
function PageTabs({ current }: { current: ModuleLink | undefined }) {
  const path = usePathname() ?? "";
  if (!current?.pages) return null;
  const on = current.pages.find((p) => path === p.href || path.startsWith(p.href + "/"))?.href;
  return (
    <nav className="ws-tabs" aria-label={`${current.label} pages`}>
      {current.pages.map((p) => <Link key={p.href} href={p.href} aria-current={p.href === on ? "page" : undefined}>{p.label}</Link>)}
    </nav>
  );
}

export type PaletteItem = { id: string; group: string; label: string; icon?: LucideIcon; meta?: string; keywords?: string[]; run: () => void };

type WorkspaceCtx = {
  theme: Theme;
  setCrumb: (crumb: string) => void;
  registerPalette: (source: string, items: PaletteItem[]) => void;
};

const Ctx = createContext<WorkspaceCtx | null>(null);

export function useWorkspace(): WorkspaceCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useWorkspace must be used inside WorkspaceShell");
  return ctx;
}

const THEME_KEY = "ws-theme";
const THEME_EVENT = "ws-theme-change";

/** Theme lives in localStorage; every workspace tab and window follows it. Server render is dark. */
const themeStore = {
  get(): Theme {
    try { return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark"; } catch { return "dark"; }
  },
  set(theme: Theme) {
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* storage unavailable */ }
    window.dispatchEvent(new Event(THEME_EVENT));
  },
  subscribe(onChange: () => void) {
    window.addEventListener(THEME_EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener(THEME_EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  },
};

const noopSubscribe = () => () => {};

const REGION_UI: { region: Region; label: string; icon: LucideIcon }[] = [
  { region: "left", label: "Feature list", icon: PanelLeft },
  { region: "bottom", label: "Runs and log", icon: PanelBottom },
  { region: "right", label: "Inspector", icon: PanelRight },
];

/** Region visibility rendered on the server and before hydration; a module constant so memo dependencies stay stable. */
const SERVER_OPEN = { left: true, right: true, bottom: false } as const;

export function WorkspaceShell({ module, className = "", children }: { module: string; className?: string; children: ReactNode }) {
  const router = useRouter();
  const theme = useSyncExternalStore(themeStore.subscribe, themeStore.get, () => "dark" as Theme);
  const [crumb, setCrumb] = useState("");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sources, setSources] = useState<Record<string, PaletteItem[]>>({});
  // Layout state comes from this device's storage; until hydration, render the server default so markup matches.
  const mounted = useSyncExternalStore(noopSubscribe, () => true, () => false);
  const stored = useLayout((s) => s.open);
  const open = mounted ? stored : SERVER_OPEN;
  const toggleRegion = useLayout((s) => s.toggle);

  const toggleTheme = useCallback(() => themeStore.set(themeStore.get() === "dark" ? "light" : "dark"), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey && !t?.closest("input, textarea, select, [contenteditable]")) { e.preventDefault(); setPaletteOpen(true); return; }
      if (!(e.metaKey || e.ctrlKey) || e.altKey) return;
      const key = e.key.toLowerCase();
      if (key === "k") { e.preventDefault(); setPaletteOpen((o) => !o); return; }
      const region = (Object.keys(SHORTCUTS) as Region[]).find((r) => SHORTCUTS[r].key === key);
      if (region) { e.preventDefault(); toggleRegion(region); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleRegion]);

  const registerPalette = useCallback((source: string, items: PaletteItem[]) => {
    setSources((cur) => ({ ...cur, [source]: items }));
  }, []);

  const ctx = useMemo<WorkspaceCtx>(() => ({ theme, setCrumb, registerPalette }), [theme, registerPalette]);

  const builtIn: PaletteItem[] = useMemo(() => [
    ...MODULES.map((m) => ({ id: `module-${m.id}`, group: "Modules", label: m.label, icon: m.icon, run: () => router.push(m.href) })),
    ...REGION_UI.map((r) => ({ id: `toggle-${r.region}`, group: "Layout", label: `${open[r.region] ? "Hide" : "Show"} ${r.label.toLowerCase()}`, icon: r.icon, meta: SHORTCUTS[r.region].label, run: () => toggleRegion(r.region) })),
    { id: "theme", group: "Layout", label: theme === "dark" ? "Switch to light theme" : "Switch to dark theme", icon: theme === "dark" ? Sun : Moon, run: toggleTheme },
    { id: "prefs-push", group: "Preferences", label: "Save preferences to the server", icon: CloudUpload, run: () => void pushPrefs() },
    { id: "prefs-pull", group: "Preferences", label: "Load preferences from the server", icon: CloudDownload, run: () => void pullPrefs() },
    { id: "prefs-export", group: "Preferences", label: "Export preferences as JSON", icon: FileDown, run: exportPrefs },
    { id: "prefs-import", group: "Preferences", label: "Import preferences from JSON", icon: FileUp, run: importPrefs },
  ], [router, theme, toggleTheme, open, toggleRegion]);

  const allItems = [...Object.values(sources).flat(), ...builtIn];
  const prefs = usePrefs();
  const themeClass = (theme === "light" ? " is-light" : "") + prefClasses(prefs);

  return (
    <Ctx.Provider value={ctx}>
      <div className={`ws ws-tokens${themeClass} ${className}`}>
        <header className="ws-top">
          <Link href="/" className="ws-brand" aria-label="ATLAS home">
            {/* The mark: a globe (the atlas) with a rising line drawn across it. */}
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden className="ws-mark">
              <defs>
                <linearGradient id="ws-mark-g" x1="0" y1="0" x2="0" y2="22" gradientUnits="userSpaceOnUse"><stop stopColor="oklch(0.72 0.15 235)" /><stop offset="1" stopColor="oklch(0.5 0.17 255)" /></linearGradient>
              </defs>
              <rect width="22" height="22" rx="6.5" fill="url(#ws-mark-g)" />
              <rect x="0.5" y="0.5" width="21" height="21" rx="6" stroke="white" strokeOpacity="0.22" />
              <circle cx="11" cy="11" r="6.2" stroke="white" strokeOpacity="0.55" strokeWidth="1.1" />
              <ellipse cx="11" cy="11" rx="2.6" ry="6.2" stroke="white" strokeOpacity="0.4" strokeWidth="1" />
              <path d="M4.2 14.2 8.4 10.6l2.4 2 6.8-6" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            ATLAS
          </Link>
          <span className="ws-div" aria-hidden />
          <ModuleSwitcher current={MODULES.find((x) => x.id === module)} themeClass={themeClass} className={className} />
          {MODULES.find((x) => x.id === module)?.pages ? <PageTabs current={MODULES.find((x) => x.id === module)} />
            : crumb ? <nav className="ws-crumb" aria-label="Breadcrumb"><span className="slash">/</span><b>{crumb}</b></nav> : null}
          {/* Pages put their own controls here (Studio Build: workspace, view, run), so there is one header, not two. */}
          <div id="ws-slot" className="ws-slot" />
          <button className="ws-search" onClick={() => setPaletteOpen(true)} aria-label="Open command palette">
            <Search size={14} strokeWidth={1.75} />
            <span className="label">Search names, screens, runs, actions</span>
            <span className="kbd">⌘K</span>
          </button>
          <div className="ws-layout-toggles" role="group" aria-label="Layout">
            {REGION_UI.map(({ region, label, icon: Icon }) => (
              <Tooltip key={region} label={<span>{open[region] ? "Hide" : "Show"} {label.toLowerCase()} <span className="kbd" style={{ marginLeft: 6 }}>{SHORTCUTS[region].label}</span></span>}>
                <button aria-pressed={open[region]} aria-label={`Toggle ${label.toLowerCase()}`} onClick={() => toggleRegion(region)}>
                  <Icon size={15} strokeWidth={1.6} />
                </button>
              </Tooltip>
            ))}
          </div>
          <SettingsPopover themeClass={themeClass} className={className} />
          <Tooltip label={theme === "dark" ? "Light theme" : "Dark theme"}>
            <button className="btn icon ghost" onClick={toggleTheme} aria-label="Toggle theme">
              {theme === "dark" ? <Sun size={15} strokeWidth={1.75} /> : <Moon size={15} strokeWidth={1.75} />}
            </button>
          </Tooltip>
        </header>

        <div className="ws-body">
          <nav className="ws-rail" aria-label="Modules">
            <Tooltip label="Home" side="right">
              <Link href="/" aria-label="Home"><Home size={18} strokeWidth={1.6} /></Link>
            </Tooltip>
            <span className="sep" />
            {MODULES.map((m) => {
              const Icon = m.icon;
              return (
                <Tooltip key={m.id} label={m.label} side="right">
                  <Link href={m.href} aria-label={m.label} aria-current={m.id === module ? "page" : undefined}>
                    <Icon size={18} strokeWidth={1.6} />
                  </Link>
                </Tooltip>
              );
            })}
            <span className="end" />
            <Tooltip label={<span>Command palette <span className="kbd" style={{ marginLeft: 6 }}>⌘K</span></span>} side="right">
              <button onClick={() => setPaletteOpen(true)} aria-label="Command palette"><CommandIcon size={17} strokeWidth={1.6} /></button>
            </Tooltip>
          </nav>
          <div className="ws-panels">{children}</div>
        </div>

        <SearchOverlay open={paletteOpen} onOpenChange={setPaletteOpen} items={allItems} themeClass={themeClass} className={className} />
        <QuickLook />
      </div>
    </Ctx.Provider>
  );
}

const ACCENTS: { id: Accent; color: string }[] = [
  { id: "blue", color: "oklch(0.7 0.15 255)" }, { id: "teal", color: "oklch(0.74 0.12 190)" },
  { id: "violet", color: "oklch(0.72 0.15 300)" }, { id: "amber", color: "oklch(0.8 0.14 80)" },
];

function SettingsPopover({ themeClass, className }: { themeClass: string; className: string }) {
  const p = usePrefs();
  return (
    <Popover.Root>
      <Tooltip label="Workspace settings">
        <Popover.Trigger asChild><button className="btn icon ghost" aria-label="Workspace settings"><Settings2 size={15} strokeWidth={1.75} /></button></Popover.Trigger>
      </Tooltip>
      <Popover.Portal>
        <Popover.Content className={`pop ws-tokens${themeClass} ${className}`} align="end" sideOffset={8} style={{ width: 260 }}>
          <div className="hd">Density</div>
          <div style={{ padding: "0 8px 6px" }}>
            <Segmented<Density> label="Density" value={p.density} onChange={(density) => p.set({ density })} options={[{ value: "compact", label: "Compact" }, { value: "comfortable", label: "Comfortable" }]} />
          </div>
          <div className="row">Invert up/down colours<button type="button" className="toggle" aria-pressed={p.invertColors} aria-label="Invert up and down colours" onClick={() => p.set({ invertColors: !p.invertColors })} /></div>
          <div className="row">Reduce motion<button type="button" className="toggle" aria-pressed={p.reducedMotion} aria-label="Reduce motion" onClick={() => p.set({ reducedMotion: !p.reducedMotion })} /></div>
          <div className="row">Accent
            <span style={{ display: "flex", gap: 8 }}>
              {ACCENTS.map((a) => <button key={a.id} type="button" className="sw" style={{ background: a.color }} aria-label={`${a.id} accent`} aria-pressed={p.accent === a.id} onClick={() => p.set({ accent: a.id })} />)}
            </span>
          </div>
          <div className="sep" />
          <div className="hd">Charts</div>
          <div style={{ padding: "0 8px 6px", display: "grid", gap: 6 }}>
            <Segmented<Palette> label="Series colours" value={p.palette} onChange={(palette) => p.set({ palette })} options={[{ value: "default", label: "Default" }, { value: "colorblind", label: "Safe" }, { value: "vivid", label: "Vivid" }, { value: "mono", label: "Mono" }]} />
            <Segmented<LineWeight> label="Line weight" value={p.lineWeight} onChange={(lineWeight) => p.set({ lineWeight })} options={[{ value: "thin", label: "Thin" }, { value: "regular", label: "Regular" }, { value: "bold", label: "Bold" }]} />
          </div>
          <div className="row">Gridlines<button type="button" className="toggle" aria-pressed={p.grid} aria-label="Gridlines" onClick={() => p.set({ grid: !p.grid })} /></div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
