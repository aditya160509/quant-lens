"use client";

import { Suspense, useEffect, useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import StudioLayout from "./StudioLayout";
import { StudioProvider } from "./StudioStore";
import { useStudioWorkspaceStore } from "@/stores/studio/workspaceStore";

const MODE_TO_TAB = Object.freeze({
  develop: "develop",
  results: "tearsheet",
  portfolio: "portfolio",
  paper: "paper",
  compose: "composer",
  stress: "validate",
  validate: "validate",
  replay: "replay",
});
const TAB_TO_MODE = Object.freeze(
  Object.fromEntries(Object.entries(MODE_TO_TAB).map(([mode, tab]) => [tab, mode])),
);

function StudioModeSync() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeTab = useStudioWorkspaceStore((state) => state.activeTab);
  const setActiveTab = useStudioWorkspaceStore((state) => state.setActiveTab);
  const requestedMode = searchParams.get("mode") || "develop";
  const targetTab = MODE_TO_TAB[requestedMode];
  const requestedTabRef = useRef(null);
  const applyingUrlRef = useRef(false);
  const activeTabRef = useRef(activeTab);
  const serializedSearch = searchParams.toString();

  useEffect(() => {
    activeTabRef.current = activeTab;
  }, [activeTab]);

  useEffect(() => {
    if (!targetTab) {
      requestedTabRef.current = "develop";
      applyingUrlRef.current = activeTabRef.current !== "develop";
      const normalized = new URLSearchParams(serializedSearch);
      normalized.set("mode", "develop");
      router.replace(`${pathname}?${normalized.toString()}`, { scroll: false });
      if (applyingUrlRef.current) {
        setActiveTab("develop");
      }
      return;
    }

    requestedTabRef.current = targetTab;
    applyingUrlRef.current = activeTabRef.current !== targetTab;
    if (applyingUrlRef.current) {
      setActiveTab(targetTab);
    }
  }, [pathname, requestedMode, router, serializedSearch, setActiveTab, targetTab]);

  useEffect(() => {
    if (applyingUrlRef.current) {
      if (requestedTabRef.current === activeTab) {
        applyingUrlRef.current = false;
      }
      return;
    }

    const activeMode = TAB_TO_MODE[activeTab];
    if (!activeMode || requestedMode === activeMode) {
      return;
    }

    requestedTabRef.current = activeTab;
    const updated = new URLSearchParams(serializedSearch);
    updated.set("mode", activeMode);
    router.replace(`${pathname}?${updated.toString()}`, { scroll: false });
  }, [activeTab, pathname, requestedMode, router, serializedSearch]);

  return null;
}

export default function OriginalStudioPage() {
  return (
    <StudioProvider>
      <Suspense fallback={null}>
        <StudioModeSync />
      </Suspense>
      <StudioLayout />
    </StudioProvider>
  );
}
