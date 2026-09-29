"use client";

import { ScreenerV2Workbench } from "@/components/screener-v2/customPagePrimitives";
import { SCREENER_OUTPUT_BOOKS } from "@/components/screener-v2/registry";

const SECTIONS = SCREENER_OUTPUT_BOOKS["02"];
const PAGE_SPEC = {
  eyebrow: "ATLAS // FORMULA BUILDER",
  headline: "Write custom expressions and immediately inspect ranked output.",
  description: "Formula validation, result tables, historical formula backtest and factor-zoo comparison for fast custom screen research.",
  intent: "formula · validate · rank",
};

export default function Page() {
  return <ScreenerV2Workbench featureId="02" sections={SECTIONS} pageSpec={PAGE_SPEC} />;
}
