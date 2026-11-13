"use client";

import { CandlestickSeries, ColorType, createChart, createSeriesMarkers, HistogramSeries, LineSeries, type IChartApi, type SeriesMarker, type Time } from "lightweight-charts";
import { useEffect, useRef } from "react";

export type Bar = { time: string; open: number; high: number; low: number; close: number; volume: number | null };
export type TradeMark = { time: string; side: "entry" | "exit"; label?: string };

// The chart library parses colours itself, so theme tokens (oklch) are resolved to rgba through a 1px canvas.
const probe = typeof document === "undefined" ? null : document.createElement("canvas").getContext("2d", { willReadFrequently: true });
function css(el: Element, name: string, fallback: string, alpha = 1) {
  const raw = getComputedStyle(el).getPropertyValue(name).trim() || fallback;
  if (!probe) return raw;
  probe.clearRect(0, 0, 1, 1);
  probe.fillStyle = raw;
  probe.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = probe.getImageData(0, 0, 1, 1).data;
  return `rgba(${r}, ${g}, ${b}, ${((a / 255) * alpha).toFixed(3)})`;
}
const AVERAGES = [50, 200];

/** Simple moving average of closes; undefined until the window fills. */
function sma(bars: Bar[], n: number) {
  let sum = 0;
  return bars.flatMap((b, i) => {
    sum += b.close - (i >= n ? bars[i - n].close : 0);
    return i >= n - 1 ? [{ time: b.time as Time, value: sum / n }] : [];
  });
}

/** Candles with a volume pane, SMA 50 and 200, and optional entry and exit marks, on Lightweight Charts v5 in the workspace theme. */
/** With `line` (e.g. trailing P/E per session) it draws that line instead of candles, keeping the marks. */
export function PriceChart({ bars, marks, height = 300, averages = AVERAGES, line }: { bars: Bar[]; marks?: TradeMark[]; height?: number; averages?: number[]; line?: { time: string; value: number }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || bars.length < 2) return;
    const up = css(el, "--up", "#26a69a"), down = css(el, "--down", "#ef5350"), text = css(el, "--text-3", "#888"), grid = css(el, "--grid", "rgba(128,128,128,.12)");
    const chart: IChartApi = createChart(el, {
      height, autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: text, fontSize: 11, attributionLogo: false, panes: { separatorColor: grid } },
      grid: { vertLines: { visible: false }, horzLines: { color: grid } },
      rightPriceScale: { borderVisible: false }, timeScale: { borderVisible: false },
      crosshair: { mode: 1 },
    });
    const candles = line
      ? chart.addSeries(LineSeries, { color: css(el, "--c1", "#6ea8fe"), lineWidth: 2, priceLineVisible: false })
      : chart.addSeries(CandlestickSeries, { upColor: up, downColor: down, wickUpColor: up, wickDownColor: down, borderVisible: false });
    if (line) candles.setData(line.map((p) => ({ time: p.time as Time, value: p.value })));
    else candles.setData(bars.map((b) => ({ time: b.time as Time, open: b.open, high: b.high, low: b.low, close: b.close })));
    if (!line) averages.forEach((n, i) => {
      const line = sma(bars, n);
      if (line.length) chart.addSeries(LineSeries, { color: css(el, `--c${i + 1}`, "#888"), lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: `SMA ${n}` }).setData(line);
    });
    if (bars.some((b) => b.volume)) {
      const upSoft = css(el, "--up", "#26a69a", 0.45), downSoft = css(el, "--down", "#ef5350", 0.45);
      const vol = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false }, 1);
      vol.setData(bars.map((b) => ({ time: b.time as Time, value: b.volume ?? 0, color: b.close >= b.open ? upSoft : downSoft })));
      chart.panes()[1]?.setHeight(Math.round(height * 0.22));
    }
    const shown = new Set(line ? line.map((p) => p.time) : bars.map((b) => b.time));
    const m: SeriesMarker<Time>[] = (marks ?? []).filter((x) => shown.has(x.time)).sort((a, b) => a.time.localeCompare(b.time))
      .map((x) => ({ time: x.time as Time, position: x.side === "entry" ? "belowBar" : "aboveBar", shape: x.side === "entry" ? "arrowUp" : "arrowDown", color: x.side === "entry" ? up : down, text: x.label ?? "" }));
    if (m.length) createSeriesMarkers(candles, m);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars, marks, height, averages, line]);
  return <div ref={ref} style={{ width: "100%", height }} role="img" aria-label={bars.length ? `Price from ${bars[0].time} to ${bars.at(-1)?.time}` : "No prices"} />;
}
