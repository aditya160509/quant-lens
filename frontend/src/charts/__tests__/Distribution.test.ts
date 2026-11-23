import { describe, expect, it } from "vitest";
import { winsorise } from "../Distribution";

describe("winsorise", () => {
  it("clips outliers into end bins", () => {
    const v = [...Array.from({ length: 100 }, (_, i) => i / 100), 50].sort((a, b) => a - b);
    const w = winsorise(v)!;
    expect(w.over).toBe(1);
    expect(Math.max(...w.vals)).toBeLessThan(2);
  });
  it("leaves small, equal or tight data alone", () => {
    expect(winsorise([1, 2, 3])).toBeNull();
    expect(winsorise(Array(30).fill(5))).toBeNull();
    expect(winsorise(Array.from({ length: 50 }, (_, i) => i))).toBeNull();
  });
});
