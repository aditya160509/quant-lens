"use client";

import { ScreenerV2Workbench } from "@/components/screener-v2/customPagePrimitives";
import { SCREENER_OUTPUT_BOOKS } from "@/components/screener-v2/registry";

const SECTIONS = SCREENER_OUTPUT_BOOKS["05"];
const PAGE_SPEC = {
  eyebrow: "ATLAS // POINT-IN-TIME BACKTEST",
  headline: "Validate screens through performance, turnover and timing sensitivity.",
  description: "Equity curve, full statistics, rolling performance, holding period tests, weekday rebalance sensitivity, turnover and attribution.",
  intent: "PIT backtest · sensitivity",
};

export default function Page() {
  return <ScreenerV2Workbench featureId="05" sections={SECTIONS} pageSpec={PAGE_SPEC} />;
}
