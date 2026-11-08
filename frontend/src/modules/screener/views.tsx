"use client";

import { Treemap } from "@/charts/Treemap";
import { isNum, label, out, pct } from "@/modules/research/format";
import type { ViewProps } from "@/modules/research/outputs/types";

/** Every passing name as a rectangle: area is market cap, colour is the 1-month return, grouped by sector. */
export function ScreenTreemap({ result }: ViewProps) {
  const items = out(result, "ranked_screener_table").filter((r) => isNum(r.market_cap) && r.market_cap > 0).map((r) => ({
    label: String(r.ticker), group: typeof r.sector === "string" && r.sector ? r.sector : "Unknown sector",
    size: r.market_cap as number, colorValue: isNum(r.return_1m) ? r.return_1m : undefined,
  }));
  return <Treemap title="Passing names by sector" sizeLabel="Market cap" colorLabel={`Mean ${label("return_1m").toLowerCase()}`} colorAggregate="mean" format={(v) => `$${(v / 1e9).toLocaleString("en-US", { maximumFractionDigits: 0 })}B`} colorFormat={(v) => pct(v, 1)} items={items} />;
}
