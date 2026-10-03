"use client";

import "./workspace.css";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import {
  Activity, BrainCircuit, ChartNetwork, Command as CommandIcon, FlaskConical, Home, Moon, Orbit, PanelBottom, PanelLeft, PanelRight,
  PieChart, Search, Settings2, SlidersHorizontal, Sun, type LucideIcon,
} from "lucide-react";
import * as Popover from "@radix-ui/react-popover";
import { SHORTCUTS, useLayout, type Region } from "./layout";
import { prefClasses, usePrefs, type Accent, type Density, type LineWeight, type Palette } from "./prefs";
import { Segmented, Tooltip } from "./ui";

export type Theme = "dark" | "light";

type ModuleLink = { id: string; label: string; href: string; icon: LucideIcon };

/** Modules shown in the rail. Research lives in the workspace; the others move in as they are rebuilt. */
export const MODULES: ModuleLink[] = [
  { id: "research", label: "Research", href: "/research", icon: FlaskConical },
  { id: "screener", label: "Screener", href: "/labs/screener-v2", icon: SlidersHorizontal },
  { id: "factors", label: "Factors", href: "/labs/factors-v2", icon: ChartNetwork },
  { id: "ml", label: "Machine learning", href: "/labs/ml-v2", icon: BrainCircuit },
  { id: "pca", label: "PCA", href: "/labs/pca-v2", icon: Orbit },
  { id: "volatility", label: "Volatility", href: "/labs/volatility-v2", icon: Activity },
  { id: "portfolio", label: "Portfolio", href: "/labs/portfolio-v2", icon: PieChart },
];

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

export function WorkspaceShell({ module, className = "", children }: { module: string; className?: string; children: ReactNode }) {
  const router = useRouter();
  const theme = useSyncExternalStore(themeStore.subscribe, themeStore.get, () => "dark" as Theme);
  const [crumb, setCrumb] = useState("");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sources, setSources] = useState<Record<string, PaletteItem[]>>({});
  // Layout state comes from this device's storage; until hydration, render the server default so markup matches.
  const mounted = useSyncExternalStore(noopSubscribe, () => true, () => false);
  const stored = useLayout((s) => s.open);
  const open = mounted ? stored : { left: true, right: true, bottom: false };
  const toggleRegion = useLayout((s) => s.toggle);

  const toggleTheme = useCallback(() => themeStore.set(themeStore.get() === "dark" ? "light" : "dark"), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
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
  const current = MODULES.find((m) => m.id === module);

  const builtIn: PaletteItem[] = useMemo(() => [
    ...MODULES.map((m) => ({ id: `module-${m.id}`, group: "Modules", label: m.label, icon: m.icon, run: () => router.push(m.href) })),
    ...REGION_UI.map((r) => ({ id: `toggle-${r.region}`, group: "Layout", label: `${open[r.region] ? "Hide" : "Show"} ${r.label.toLowerCase()}`, icon: r.icon, meta: SHORTCUTS[r.region].label, run: () => toggleRegion(r.region) })),
    { id: "theme", group: "Layout", label: theme === "dark" ? "Switch to light theme" : "Switch to dark theme", icon: theme === "dark" ? Sun : Moon, run: toggleTheme },
  ], [router, theme, toggleTheme, open, toggleRegion]);

  const allItems = [...Object.values(sources).flat(), ...builtIn];
  const groups = allItems.reduce<Record<string, PaletteItem[]>>((acc, it) => ({ ...acc, [it.group]: [...(acc[it.group] ?? []), it] }), {});
  const prefs = usePrefs();
  const themeClass = (theme === "light" ? " is-light" : "") + prefClasses(prefs);

  return (
    <Ctx.Provider value={ctx}>
      <div className={`ws ws-tokens${themeClass} ${className}`}>
        <header className="ws-top">
          <Link href="/" className="ws-brand" aria-label="ATLAS home">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
              <rect width="20" height="20" rx="6" fill="var(--text)" />
              <path d="M5 13.5 8.2 9l2.6 2.6L15 6" stroke="var(--bg)" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            ATLAS
          </Link>
          <nav className="ws-crumb" aria-label="Breadcrumb">
            <span className="slash">/</span>
            <span>{current?.label}</span>
            {crumb ? <><span className="slash">/</span><b>{crumb}</b></> : null}
          </nav>
          <button className="ws-search" onClick={() => setPaletteOpen(true)} aria-label="Open command palette">
            <Search size={14} strokeWidth={1.75} />
            <span className="label">Search features, runs, actions</span>
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

        <Command.Dialog
          open={paletteOpen}
          onOpenChange={setPaletteOpen}
          label="Command palette"
          overlayClassName={`cmdk-overlay${themeClass}`}
          contentClassName={`cmdk ws-tokens${themeClass} ${className}`}
        >
          <Command.Input placeholder="Jump to a feature, a past run, or an action" />
          <Command.List>
            <Command.Empty>No matches</Command.Empty>
            {Object.entries(groups).map(([group, items]) => (
              <Command.Group key={group} heading={group}>
                {items.map((it) => {
                  const Icon = it.icon;
                  return (
                    <Command.Item key={it.id} value={`${it.label} ${(it.keywords ?? []).join(" ")} ${it.id}`} onSelect={() => { setPaletteOpen(false); it.run(); }}>
                      {Icon ? <Icon size={15} strokeWidth={1.6} /> : null}
                      {it.label}
                      {it.meta ? <span className="meta">{it.meta}</span> : null}
                    </Command.Item>
                  );
                })}
              </Command.Group>
            ))}
          </Command.List>
        </Command.Dialog>
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
