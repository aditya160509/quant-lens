"use client";

import { ScreenerV2Workbench } from "@/components/screener-v2/customPagePrimitives";
import { SCREENER_OUTPUT_BOOKS } from "@/components/screener-v2/registry";

const SECTIONS = SCREENER_OUTPUT_BOOKS["01"];
const PAGE_SPEC = {
  eyebrow: "ATLAS // CORE SCREEN",
  headline: "Rank the full universe with institutional factor context.",
  description: "Multi-factor score table, filter funnel, percentile context, sector heatmap, quick-look chart and bucket distribution in one screening workspace.",
  intent: "rank · filter · inspect",
};

export default function Page() {
  return <ScreenerV2Workbench featureId="01" sections={SECTIONS} pageSpec={PAGE_SPEC} />;
}
