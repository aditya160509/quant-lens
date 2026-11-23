import { describe, expect, it } from "vitest";
import { transformBars } from "../build/DevChart";

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
    expect(out.every((b) => Math.abs(Math.abs(b.close - b.open) - Math.abs(out[0]!.close - out[0]!.open)) < 1e-9)).toBe(true);
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
});
