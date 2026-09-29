"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "report-sections",
    "title": "Allocator Report Sections",
    "source": "tables",
    "dataKey": "sections",
    "fallbackKeys": [
      "sections",
      "report_preview"
    ],
    "chartType": "table"
  },
  {
    "id": "audit-trail",
    "title": "Report Audit Trail",
    "source": "meta",
    "dataKey": "audit_trail",
    "fallbackKeys": [
      "audit"
    ],
    "chartType": "table"
  },
  {
    "id": "pdf-download",
    "title": "PDF Export",
    "source": "meta",
    "dataKey": "pdf_base64",
    "chartType": "pdfDownload"
  }
];

export default function Feature14Page() {
  return <CustomFeaturePage featureId="14" sections={sections} />;
}
