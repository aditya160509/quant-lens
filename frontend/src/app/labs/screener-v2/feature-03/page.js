"use client";

import { ScreenerV2Workbench } from "@/components/screener-v2/customPagePrimitives";
import { SCREENER_OUTPUT_BOOKS } from "@/components/screener-v2/registry";

const SECTIONS = SCREENER_OUTPUT_BOOKS["03"];
const PAGE_SPEC = {
  eyebrow: "ATLAS // COMPOSITE ENGINE",
  headline: "Build composite scores with transparent component attribution.",
  description: "Composite ranks, decomposition, component IC/IR, correlation heatmaps, factor backtests and regime conditional diagnostics.",
  intent: "weights · transparency · IC",
};

export default function Page() {
  return <ScreenerV2Workbench featureId="03" sections={SECTIONS} pageSpec={PAGE_SPEC} />;
}
