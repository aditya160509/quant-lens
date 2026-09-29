"use client";

import { PcaV2Workbench, PCA_OUTPUT_BOOKS } from "@/components/pca-v2/customPagePrimitives";

export default function PcaFeature07Page() {
  return <PcaV2Workbench featureId="07" sections={PCA_OUTPUT_BOOKS["07"]} />;
}
