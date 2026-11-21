"use client";

import * as Popover from "@radix-ui/react-popover";
import { ChevronDown, Home, LayoutGrid } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type KeyboardEvent as ReactKeyEvent } from "react";
import { MODULES, type ModuleLink } from "./modules";

/** One switcher for every module (JetBrains project widget): modules on the left, the hovered module's pages on the right. */
export function ModuleSwitcher({ current, themeClass = "", className = "", label }: { current: ModuleLink | undefined; themeClass?: string; className?: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const [hot, setHot] = useState(current?.id ?? MODULES[0].id);
  const shown = MODULES.find((x) => x.id === hot) ?? MODULES[0];
  const Icon = current?.icon ?? (label ? LayoutGrid : Home);
  const page = activePage(current, usePathname() ?? "");
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
          <span className="tile"><Icon size={14} strokeWidth={1.8} /></span>{label ?? current?.label ?? "Home"}{page && page.href !== current?.href ? <><span className="slash">/</span><b>{page.label}</b></> : null}<ChevronDown size={13} strokeWidth={2} aria-hidden />
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
            {shown.pages?.map((p) => <Link key={p.href} href={p.href} className="item" aria-current={p.href === page?.href ? "page" : undefined} onClick={() => setOpen(false)}>{p.label}</Link>)}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

/** The page of a module the path is on; longest match wins, so the module root is active only on the root itself. */
const activePage = (m: ModuleLink | undefined, path: string) =>
  m?.pages?.filter((p) => path === p.href || path.startsWith(p.href + "/")).sort((x, y) => y.href.length - x.href.length)[0];
