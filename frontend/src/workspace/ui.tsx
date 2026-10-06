"use client";

import * as RT from "@radix-ui/react-tooltip";
import { useEffect, useRef, type ReactElement, type ReactNode } from "react";

export type Tone = "up" | "down" | "warn" | "accent" | "neutral";

/** Tooltip rendered inside the workspace tree so it inherits the theme tokens. */
export function Tooltip({ label, side = "bottom", children }: { label: ReactNode; side?: "top" | "right" | "bottom" | "left"; children: ReactElement }) {
  return (
    <RT.Provider delayDuration={350} skipDelayDuration={150}>
      <RT.Root>
        <RT.Trigger asChild>{children}</RT.Trigger>
        <RT.Content className="tip" side={side} sideOffset={6} collisionPadding={8}>{label}</RT.Content>
      </RT.Root>
    </RT.Provider>
  );
}

export function Chip({ tone = "neutral", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return <span className={`chip${tone === "neutral" ? "" : ` ${tone}`}`} title={title}>{children}</span>;
}

export function Dot({ tone, live = false }: { tone?: Tone | null; live?: boolean }) {
  return <span className={`dot${live ? " live" : tone && tone !== "neutral" && tone !== "accent" ? ` ${tone}` : ""}`} aria-hidden />;
}

export function Segmented<T extends string | number>({ value, options, onChange, label }: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={String(o.value)} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

/** Pill tabs that keep the selected tab scrolled into view and move with the arrow keys (WAI-ARIA tabs pattern). */
export function Tabs<T extends string>({ value, tabs, onChange }: { value: T; tabs: { id: T; label: string; count?: number }[]; onChange: (id: T) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const strip = ref.current;
    const sel = strip?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!strip || !sel) return;
    const left = sel.offsetLeft - strip.offsetLeft, right = left + sel.offsetWidth;
    if (left < strip.scrollLeft) strip.scrollTo({ left: left - 16, behavior: "smooth" });
    else if (right > strip.scrollLeft + strip.clientWidth) strip.scrollTo({ left: right - strip.clientWidth + 16, behavior: "smooth" });
  }, [value, tabs.length]);
  const onKey = (e: React.KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === value);
    const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : null;
    if (next === null || !tabs.length) return;
    e.preventDefault();
    const t = tabs[(next + tabs.length) % tabs.length];
    onChange(t.id);
    ref.current?.querySelector<HTMLElement>(`[data-tab="${CSS.escape(t.id)}"]`)?.focus();
  };
  return (
    <div className="tabs" role="tablist" ref={ref} onKeyDown={onKey}>
      {tabs.map((t) => (
        <button key={t.id} role="tab" type="button" data-tab={t.id} aria-selected={t.id === value} tabIndex={t.id === value ? 0 : -1} onClick={() => onChange(t.id)}>
          {t.label}
          {t.count !== undefined ? <span className="count">{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

export function Skeleton({ w = "100%", h = 12, style }: { w?: number | string; h?: number | string; style?: React.CSSProperties }) {
  return <div className="skel" style={{ width: w, height: h, ...style }} />;
}

export type MenuAt = { x: number; y: number };

/** A small positioned menu (right-click or button anchored). Closes on outside click, Escape and scroll. */
export function PopMenu({ at, onClose, children, width = 220, sticky = false }: { at: MenuAt | null; onClose: () => void; children: ReactNode; width?: number; sticky?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!at) return;
    const down = (e: Event) => { if (!ref.current?.contains(e.target as Node)) onClose(); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("mousedown", down);
    window.addEventListener("keydown", key);
    window.addEventListener("resize", onClose);
    return () => { window.removeEventListener("mousedown", down); window.removeEventListener("keydown", key); window.removeEventListener("resize", onClose); };
  }, [at, onClose]);
  if (!at) return null;
  const x = Math.min(at.x, window.innerWidth - width - 8);
  const y = Math.min(at.y, window.innerHeight - 340);
  return <div ref={ref} className="pop" role="menu" style={{ position: "fixed", left: x, top: Math.max(8, y), width }} onClick={sticky ? undefined : onClose}>{children}</div>;
}

export function MenuItem({ icon, onClick, danger, children, hint }: { icon?: ReactNode; onClick: () => void; danger?: boolean; children: ReactNode; hint?: string }) {
  return <button type="button" role="menuitem" className={`item${danger ? " danger" : ""}`} onClick={onClick}>{icon}<span style={{ flex: 1 }}>{children}</span>{hint ? <span className="kbd">{hint}</span> : null}</button>;
}
