"use client";

import { useCallback, useEffect } from "react";
import { usePanelRef, type PanelSize } from "react-resizable-panels";
import { useLayout, type Region } from "./layout";

/**
 * Binds a collapsible panel to a workspace region: the top-bar toggle and shortcut open or close it,
 * and dragging it shut updates the toggle.
 */
export function useRegionPanel(region: Region) {
  const panelRef = usePanelRef();
  const open = useLayout((s) => s.open[region]);
  const set = useLayout((s) => s.set);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    if (open && panel.isCollapsed()) panel.expand();
    else if (!open && !panel.isCollapsed()) panel.collapse();
  }, [open, panelRef]);

  // The first resize is the initial layout, not a user action, so it must not flip the toggle.
  const onResize = useCallback((size: PanelSize, _id: string | number | undefined, prev: PanelSize | undefined) => {
    if (prev === undefined) return;
    set(region, size.inPixels > 1);
  }, [region, set]);

  return { panelRef, onResize, defaultOpen: open };
}
