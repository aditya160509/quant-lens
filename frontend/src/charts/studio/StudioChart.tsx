"use client";

import { CandlestickSeries, ColorType, createChart, createSeriesMarkers, HistogramSeries, LineSeries, type IChartApi, type ISeriesApi, type SeriesMarker, type Time } from "lightweight-charts";
import { useEffect, useRef } from "react";
import { getIndicator } from "@/components/chart_engine/IndicatorEngine/registry";
import type { OHLCVBar } from "@/components/chart_engine/types";

export type ChartBar = { time: string; open: number; high: number; low: number; close: number; volume: number };
export type ChartTrade = { entry_date: string; exit_date: string; side: string; pnl: number; exit_reason?: string };
export type ChartIndicator = { id: string; params: Record<string, unknown> };

const probe = typeof document === "undefined" ? null : document.createElement("canvas").getContext("2d", { willReadFrequently: true });
/** Lightweight Charts parses colours itself: theme tokens (oklch) resolve to rgba through a 1px canvas. */
function css(el: Element, name: string, fallback: string, alpha = 1) {
  const raw = getComputedStyle(el).getPropertyValue(name).trim() || fallback;
  if (!probe) return raw;
  probe.clearRect(0, 0, 1, 1);
  probe.fillStyle = raw;
  probe.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = probe.getImageData(0, 0, 1, 1).data;
  return `rgba(${r}, ${g}, ${b}, ${((a / 255) * alpha).toFixed(3)})`;
}
const toTime = (s: string) => (s.length > 10 ? Math.floor(Date.parse(s) / 1000) : s) as Time;
const PALETTE = ["--c1", "--c2", "--c3", "--c4", "--c5", "--c6"];

/** Candles, volume, any registered indicator (overlay or own pane), and a strategy's trades as markers with the held span shaded.
 *  `upto` draws only the first n bars (replay); `focus` zooms to a trade. */
export function StudioChart({ bars, indicators, trades, upto, focus, height = 520 }: {
  bars: ChartBar[]; indicators: ChartIndicator[]; trades: ChartTrade[]; upto?: number; focus?: ChartTrade | null; height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const api = useRef<{ chart: IChartApi; candles: ISeriesApi<"Candlestick"> } | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || bars.length < 2) return;
    const shown = upto ? bars.slice(0, upto) : bars;
    const up = css(el, "--up", "#26a69a"), down = css(el, "--down", "#ef5350"), text = css(el, "--text-3", "#888"), grid = css(el, "--grid", "rgba(128,128,128,.12)");
    const chart = createChart(el, {
      height, autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: text, fontSize: 11, attributionLogo: false, panes: { separatorColor: grid } },
      grid: { vertLines: { visible: false }, horzLines: { color: grid } },
      rightPriceScale: { borderVisible: false }, timeScale: { borderVisible: false, timeVisible: bars[0].time.length > 10 }, crosshair: { mode: 0 },
    });
    const candles = chart.addSeries(CandlestickSeries, { upColor: up, downColor: down, wickUpColor: up, wickDownColor: down, borderVisible: false });
    candles.setData(shown.map((b) => ({ time: toTime(b.time), open: b.open, high: b.high, low: b.low, close: b.close })));
    const vol = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false }, 1);
    const upSoft = css(el, "--up", "#26a69a", 0.4), downSoft = css(el, "--down", "#ef5350", 0.4);
    vol.setData(shown.map((b) => ({ time: toTime(b.time), value: b.volume, color: b.close >= b.open ? upSoft : downSoft })));
    chart.panes()[1]?.setHeight(Math.round(height * 0.14));

    const ohlcv: OHLCVBar[] = shown.map((b) => ({ timestamp: Date.parse(b.time), open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume }));
    let pane = 2;
    indicators.forEach((ind, k) => {
      const def = getIndicator(ind.id);
      if (!def) return;
      const out = def.compute(ohlcv, { ...def.defaultParams, ...ind.params });
      const color = css(el, PALETTE[k % PALETTE.length], "#888");
      const at = def.placement === "overlay" ? 0 : pane++;
      const line = (values: number[], c: string, title: string) => chart.addSeries(LineSeries, { color: c, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title }, at)
        .setData(values.flatMap((v, i) => (Number.isFinite(v) ? [{ time: toTime(shown[i].time), value: v }] : [])));
      const label = `${def.shortName} ${Object.values({ ...def.defaultParams, ...ind.params }).join(",")}`;
      if (out.bands) {
        line(out.bands.upper, color, `${label} upper`);
        line(out.bands.middle, color, label);
        line(out.bands.lower, color, `${label} lower`);
      } else line(out.series.map((p) => p.value), color, label);
      if (at > 1) chart.panes()[at]?.setHeight(Math.round(height * 0.16));
    });

    const last = shown.at(-1)!.time;
    const marks: SeriesMarker<Time>[] = trades.flatMap((t) => {
      const long = t.side === "long";
      const m: SeriesMarker<Time>[] = [];
      if (t.entry_date <= last) m.push({ time: toTime(t.entry_date), position: long ? "belowBar" : "aboveBar", shape: long ? "arrowUp" : "arrowDown", color: long ? up : down, text: long ? "B" : "S" });
      if (t.exit_date <= last) m.push({ time: toTime(t.exit_date), position: long ? "aboveBar" : "belowBar", shape: "circle", color: t.pnl >= 0 ? up : down, text: `${t.pnl >= 0 ? "+" : ""}${Math.round(t.pnl)}` });
      return m;
    }).sort((a, b) => String(a.time).localeCompare(String(b.time)));
    if (marks.length) createSeriesMarkers(candles, marks);
    chart.timeScale().fitContent();
    api.current = { chart, candles };
    return () => { chart.remove(); api.current = null; };
  }, [bars, indicators, trades, upto, height]);

  useEffect(() => {
    if (!focus || !api.current) return;
    const i = bars.findIndex((b) => b.time >= focus.entry_date), j = bars.findIndex((b) => b.time >= focus.exit_date);
    if (i < 0) return;
    api.current.chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, i - 20), to: (j < 0 ? bars.length - 1 : j) + 20 });
  }, [focus, bars]);

  return <div ref={ref} style={{ width: "100%", height }} role="img" aria-label={bars.length ? `Price from ${bars[0].time} to ${bars.at(-1)?.time}` : "No prices"} />;
}
