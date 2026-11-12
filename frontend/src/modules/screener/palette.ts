"use client";

import { useQuery } from "@tanstack/react-query";
import { BookmarkCheck, Building2, Filter, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { openQuickLook } from "@/kit/QuickLook";
import { usePopular } from "@/kit/QuickLookData";
import { get } from "@/modules/research/api";
import { featureHref } from "@/modules/research/catalog";
import { useStudies } from "@/modules/research/store";
import { useWorkspace } from "@/workspace/WorkspaceShell";

type Screen = { screen_id: string; name: string; feature_id: string; payload: Record<string, unknown> };
type Template = { key: string; formula: string };
// Stable empties: a fresh [] each render would re-register the palette in a loop.
const NO_HITS: never[] = [];

/** Command palette entries for the Screener: add a filter, open any saved screen or template, open a stock. */
export function useScreenerPalette() {
  const { registerPalette } = useWorkspace();
  const router = useRouter();
  const popular = usePopular().data?.results ?? NO_HITS;
  const screens = useQuery({ queryKey: ["screener", "screens"], queryFn: () => get<{ screens: Screen[] }>("/screens"), retry: false }).data?.screens ?? NO_HITS;
  const templates = useQuery({ queryKey: ["screener", "templates"], queryFn: () => get<{ templates: Template[] }>("/templates"), staleTime: Infinity, retry: false }).data?.templates ?? NO_HITS;
  useEffect(() => {
    const open = (id: string, patch: Record<string, unknown>) => {
      useStudies.setState((s) => ({ forms: { ...s.forms, [id]: { ...s.forms[id], ...patch } } }));
      router.push(`${featureHref(id)}?go=1`);
    };
    registerPalette("screener", [
      { id: "scr-filter", group: "Screener", icon: Filter, label: "Add filter", meta: "⇧F", run: () => { const b = document.querySelector<HTMLButtonElement>("[data-hotkey='f']"); if (b) b.click(); else router.push(featureHref("sc01")); } },
      ...screens.map((x) => ({ id: `scr-saved-${x.screen_id}`, group: "Saved screens", icon: BookmarkCheck, label: x.name, run: () => open(`sc${x.feature_id}`, x.payload) })),
      ...templates.map((t) => ({ id: `scr-tpl-${t.key}`, group: "Screen templates", icon: Sparkles, label: t.key.replace(/_/g, " "), keywords: [t.formula], run: () => open("sc02", { formula: t.formula }) })),
      ...popular.map((h) => ({ id: `scr-stock-${h.ticker}`, group: "Stocks", icon: Building2, label: h.ticker, meta: h.company_name ?? undefined, keywords: [h.company_name ?? "", h.sector ?? ""], run: () => openQuickLook(h.ticker) })),
    ]);
    return () => registerPalette("screener", []);
  }, [registerPalette, router, screens, templates, popular]);
}
