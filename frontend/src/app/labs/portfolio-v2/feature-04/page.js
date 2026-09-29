"use client";
import {
  PortfolioV2Workbench,
  PORTFOLIO_OUTPUT_BOOKS,
} from "@/components/portfolio-v2/customPagePrimitives";
export default function Page() {
  return (
    <PortfolioV2Workbench
      featureId="04"
      sections={PORTFOLIO_OUTPUT_BOOKS["04"]}
    />
  );
}
