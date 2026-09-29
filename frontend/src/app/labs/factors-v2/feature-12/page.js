"use client";

import { CustomFeaturePage } from "@/components/factors-v2/customPagePrimitives";

const sections = [
  {
    "id": "dna-radar",
    "title": "Eight-Dimensional DNA Radar",
    "source": "charts",
    "dataKey": "dna_radar",
    "fallbackKeys": [
      "dna_vector"
    ],
    "chartType": "radar",
    "config": {
      "outerRadius": "72%",
      "stroke": "#2F81F7",
      "fill": "#2F81F7",
      "fillOpacity": 0.18
    }
  },
  {
    "id": "sector-dna",
    "title": "Sector DNA Long Short Tilt",
    "source": "charts",
    "dataKey": "sector_dna",
    "chartType": "groupedHorizontalBar",
    "config": {
      "seriesColors": [
        "#3FB950",
        "#F85149"
      ]
    }
  },
  {
    "id": "regime-dna",
    "title": "Regime DNA",
    "source": "charts",
    "dataKey": "regime_dna",
    "chartType": "bar",
    "config": {
      "seriesColors": [
        "#3FB950",
        "#D29922",
        "#F85149",
        "#A371F7",
        "#58A6FF",
        "#8B949E"
      ]
    }
  },
  {
    "id": "correlation-dna",
    "title": "Latest Correlation DNA",
    "source": "charts",
    "dataKey": "correlation_dna",
    "chartType": "horizontalBar",
    "config": {
      "colorBySign": true,
      "positiveColor": "#3FB950",
      "negativeColor": "#F85149"
    }
  },
  {
    "id": "return-anatomy",
    "title": "Return Anatomy",
    "source": "tables",
    "dataKey": "return_anatomy",
    "chartType": "donut"
  },
  {
    "id": "purity-score",
    "title": "Purity Score",
    "source": "summary",
    "dataKey": "summary_cards",
    "chartType": "summaryGauges"
  },
  {
    "id": "classifier-output",
    "title": "CART Classifier Output",
    "source": "charts",
    "dataKey": "classifier_output",
    "fallbackKeys": [
      "classifier_probabilities",
      "classifier_probability"
    ],
    "chartType": "classifier",
    "config": {
      "seriesColors": [
        "#3FB950",
        "#2F81F7",
        "#D29922",
        "#F85149"
      ]
    }
  }
];

export default function Feature12Page() {
  return <CustomFeaturePage featureId="12" sections={sections} />;
}
