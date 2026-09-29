"use client";

import { ScreenerV2Workbench } from "@/components/screener-v2/customPagePrimitives";
import { SCREENER_OUTPUT_BOOKS } from "@/components/screener-v2/registry";

const SECTIONS = SCREENER_OUTPUT_BOOKS["06"];
const PAGE_SPEC = {
  eyebrow: "ATLAS // ALERT MONITOR",
  headline: "Turn screens into a live watchlist and alert tape.",
  description: "Alert feed, alert precision tracker, historical precision replay and entry-exit log for monitored screen changes.",
  intent: "watchlist · alerts · replay",
};

export default function Page() {
  return <ScreenerV2Workbench featureId="06" sections={SECTIONS} pageSpec={PAGE_SPEC} />;
}
