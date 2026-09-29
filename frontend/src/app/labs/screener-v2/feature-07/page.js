"use client";

import { ScreenerV2Workbench } from "@/components/screener-v2/customPagePrimitives";
import { SCREENER_OUTPUT_BOOKS } from "@/components/screener-v2/registry";

const SECTIONS = SCREENER_OUTPUT_BOOKS["07"];
const PAGE_SPEC = {
  eyebrow: "ATLAS // RELATIVE VALUE",
  headline: "Inspect valuation through peers, sectors, history and momentum.",
  description: "Four-dimensional valuation card, sector landscape heatmap, own-history percentile series, peer table and universe percentile table.",
  intent: "valuation · peers · history",
};

export default function Page() {
  return <ScreenerV2Workbench featureId="07" sections={SECTIONS} pageSpec={PAGE_SPEC} />;
}
