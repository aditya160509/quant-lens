import { describe, expect, it } from "vitest";
import { causalBox, csvCell, MAX_BRICKS, toCsv, transformBars } from "../build/DevChart";

const bar = (i: number, close: number) => ({ time: i * 864e5, open: close, high: close + 1, low: close - 1, close, volume: 100 });

describe("transformBars", () => {
  it("leaves time-based styles alone", () => {
    const src = [bar(0, 10), bar(1, 11)];
    expect(transformBars(src, "candles")).toBe(src);
  });
  it("renko adds one brick per box crossed, with unique times", () => {
    const src = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 30].map((c, i) => bar(i, 100 + c));
    const out = transformBars(src, "renko");
    expect(out.length).toBeGreaterThan(1);
    expect(new Set(out.map((b) => b.time)).size).toBe(out.length);
    // Each brick is one box as of the bar that completed it (bricks from one bar sit 1 ms apart).
    const box = causalBox(src);
    expect(out.every((b) => Math.abs(Math.abs(b.close - b.open) - box[Math.floor(b.time / 864e5)]!) < 1e-9)).toBe(true);
  });
  it("line break only adds a line when the close breaks the last line", () => {
    const out = transformBars([bar(0, 10), bar(1, 12), bar(2, 11), bar(3, 13)], "linebreak");
    expect(out.map((b) => b.close)).toEqual([10, 12, 13]);
  });
  it("range bars close once the span reaches a box; kagi and point and figure reverse after their threshold", () => {
    const src = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 20, 26, 14, 8, 2].map((c, i) => bar(i, 100 + c));
    for (const style of ["range", "kagi", "pnf"]) {
      const out = transformBars(src, style);
      expect(out.length).toBeGreaterThan(1);
      expect(out.every((b, i) => !i || b.time > out[i - 1]!.time)).toBe(true);
    }
    const kagi = transformBars(src, "kagi");
    expect(kagi.at(-1)!.close).toBeLessThan(kagi.at(-1)!.open);
  });
  it("is causal: appending future bars never changes a synthetic bar built from the prefix", () => {
    const closes = [100, 103, 99, 106, 110, 104, 98, 92, 97, 105, 115, 108, 101, 96, 103, 112, 120, 111, 104, 99, 95, 102, 109, 118, 125];
    const all = closes.map((c, i) => ({ ...bar(i, c), high: c + 1 + (i % 3), low: c - 1 - (i % 2) }));
    // A huge late swing would have widened a window-end ATR box for all history.
    all.push(...[400, 30, 420, 25].map((c, i) => bar(closes.length + i, c)));
    let compared = 0;
    for (const style of ["renko", "range", "kagi", "pnf", "linebreak"]) {
      for (const cut of [8, 15, 25]) {
        const head = transformBars(all.slice(0, cut), style), full = transformBars(all, style);
        // Kagi and point and figure end on the swing still in progress, which later bars may extend.
        const done = style === "kagi" || style === "pnf" ? head.slice(0, -1) : head;
        expect(full.slice(0, done.length)).toEqual([...done]);
        compared += done.length;
      }
    }
    expect(compared).toBeGreaterThan(30);
  });
  it("rejects non-positive or NaN prices and caps bricks instead of hanging", () => {
    const good = [bar(0, 10), bar(1, 11), bar(2, 12)];
    for (const bad of [bar(1, 0), bar(1, -5), { ...bar(1, 11), close: NaN }, { ...bar(1, 11), high: 5 }]) {
      const src = [good[0]!, bad, good[2]!];
      for (const style of ["renko", "range", "kagi", "pnf"]) {
        const out = transformBars(src, style);
        expect(out.invalid).toMatch(/showing candles/);
        expect([...out]).toEqual(src);
      }
    }
    // A large gap is bounded by the box, which includes the gapping bar's own true range.
    const gap = [...Array.from({ length: 20 }, (_, i) => ({ ...bar(i, 1), high: 1.0001, low: 0.9999 })), bar(20, 1e6)];
    expect(transformBars(gap, "renko").length).toBeLessThan(100);
    // A long quiet trend makes one brick per bar: past the cap it is flagged, not drawn.
    const trend = Array.from({ length: MAX_BRICKS + 5000 }, (_, i) => { const c = 1 + i * 0.001; return { time: i * 864e5, open: c, high: c, low: c, close: c, volume: 1 }; });
    const t = performance.now(), out = transformBars(trend, "renko");
    expect(out.invalid).toContain(MAX_BRICKS.toLocaleString());
    expect(out.length).toBe(trend.length);
    expect(performance.now() - t).toBeLessThan(1000);
  });
});

describe("toCsv", () => {
  it("quotes per RFC 4180, neutralises formula text and keeps numbers numeric", () => {
    expect(toCsv([["date", 'a,"b"', "line\nbreak"], ["2024-01-02", -1.5, null], ["=HYPERLINK(1)", "+x", "@y"]])).toBe(
      `date,"a,""b""","line\nbreak"\r\n2024-01-02,-1.5,\r\n'=HYPERLINK(1),'+x,'@y`);
    expect(csvCell("-2")).toBe("'-2");
    expect(csvCell(-2)).toBe("-2");
    expect(csvCell(NaN)).toBe("");
  });
});
