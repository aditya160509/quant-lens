"use client";

import { Command } from "cmdk";
import { ExternalLink } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

const COMMANDS = [
  { group: "MODULES", id: "v01", label: "V01 · Estimators", sub: "Yang-Zhang, Parkinson, GK, RS, C2C", href: "/labs/volatility-v2/feature-01" },
  { group: "MODULES", id: "v02", label: "V02 · GARCH Suite", sub: "GARCH / EGARCH / GJR / FIGARCH", href: "/labs/volatility-v2/feature-02" },
  { group: "MODULES", id: "v03", label: "V03 · HAR Forecast", sub: "Multi-horizon walk-forward", href: "/labs/volatility-v2/feature-03" },
  { group: "MODULES", id: "v04", label: "V04 · Regime Detection", sub: "HMM / SJM probability stack", href: "/labs/volatility-v2/feature-04" },
  { group: "MODULES", id: "v05", label: "V05 · VRP Monitor", sub: "Implied versus physical premium", href: "/labs/volatility-v2/feature-05" },
  { group: "MODULES", id: "v06", label: "V06 · Spillover", sub: "Diebold-Yilmaz GFEVD network", href: "/labs/volatility-v2/feature-06" },
  { group: "MODULES", id: "v07", label: "V07 · DCC Engine", sub: "DCC-MLE / MIDAS correlation", href: "/labs/volatility-v2/feature-07" },
  { group: "MODULES", id: "v08", label: "V08 · Stress Engine", sub: "Scenario P&L and reverse stress", href: "/labs/volatility-v2/feature-08" },
  { group: "MODULES", id: "v09", label: "V09 · Vol Budget", sub: "Target-vol scaling and rebalance", href: "/labs/volatility-v2/feature-09" },
  { group: "CLUSTERS", id: "c1", label: "Estimation & Forecasting", sub: "V01 + V02 + V03", href: "#estimation-forecasting" },
  { group: "CLUSTERS", id: "c2", label: "Regimes & Risk Premium", sub: "V04 + V05", href: "#regime-premium" },
  { group: "CLUSTERS", id: "c3", label: "Connectedness & Stress", sub: "V06 + V07 + V08", href: "#systemic-covariance" },
  { group: "CLUSTERS", id: "c4", label: "Portfolio Control", sub: "V09", href: "#portfolio-control" },
  { group: "ACTIONS", id: "a1", label: "Open estimator shell", sub: "Start with realized volatility", href: "/labs/volatility-v2/feature-01" },
  { group: "ACTIONS", id: "a2", label: "Jump to DCC Engine", sub: "Multi-asset covariance", href: "/labs/volatility-v2/feature-07" },
];

export function VolCommandPalette() {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const router = useRouter();

  useEffect(() => {
    const down = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  useEffect(() => {
    const badge = document.querySelector(".vol-cmd-badge");
    if (!badge) return undefined;
    const click = () => setOpen(true);
    badge.addEventListener("click", click);
    return () => badge.removeEventListener("click", click);
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return COMMANDS;
    return COMMANDS.filter((command) => `${command.label} ${command.sub} ${command.group}`.toLowerCase().includes(q));
  }, [search]);

  const groups = useMemo(() => [...new Set(COMMANDS.map((command) => command.group))], []);

  function runCommand(href) {
    setOpen(false);
    if (href.startsWith("#")) {
      document.getElementById(href.slice(1))?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    router.push(href);
  }

  if (!open) return null;

  return (
    <>
      <div className="vol-cmdk-backdrop" onClick={() => setOpen(false)} />
      <div className="vol-cmdk-shell" role="dialog" aria-modal="true" aria-label="Volatility command palette">
        <Command label="Volatility command palette" shouldFilter={false}>
          <div className="vol-cmdk-input-wrap">
            <span className="vol-cmdk-input-icon">⌕</span>
            <Command.Input
              autoFocus
              className="vol-cmdk-input"
              onValueChange={setSearch}
              placeholder="Search modules, clusters, actions..."
              value={search}
            />
            <kbd className="vol-cmdk-esc">ESC</kbd>
          </div>
          <Command.List className="vol-cmdk-list">
            <Command.Empty className="vol-cmdk-empty">No command matched.</Command.Empty>
            {groups.map((group) => {
              const items = filtered.filter((command) => command.group === group);
              if (!items.length) return null;
              return (
                <Command.Group className="vol-cmdk-group" heading={group} key={group}>
                  {items.map((command) => (
                    <Command.Item className="vol-cmdk-item" key={command.id} onSelect={() => runCommand(command.href)}>
                      <span className="vol-cmdk-item-label">{command.label}</span>
                      <span className="vol-cmdk-item-sub">{command.sub}</span>
                      <ExternalLink className="vol-cmdk-item-arrow" size={11} />
                    </Command.Item>
                  ))}
                </Command.Group>
              );
            })}
          </Command.List>
          <div className="vol-cmdk-footer">
            <span><kbd>↑↓</kbd> navigate</span>
            <span><kbd>↵</kbd> open</span>
            <span><kbd>ESC</kbd> close</span>
            <b>ATLAS · VOL INTELLIGENCE</b>
          </div>
        </Command>
      </div>
    </>
  );
}
