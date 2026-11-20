import { describe, expect, it } from "vitest";
import { excursions, monthly, shuffleTrades, stats, topDrawdowns } from "../build/devStats";

const eq = [100, 110, 99, 105, 120, 90, 95].map((value, i) => ({ date: `2024-0${i + 1}-01`, value }));

describe("dev stats", () => {
  it("finds the deepest drawdown and its trough", () => {
    const [d] = topDrawdowns(eq);
    expect(d.trough).toBe("2024-06-01");
    expect(d.depth).toBeCloseTo(90 / 120 - 1);
    expect(d.end).toBeNull();
    expect(stats(eq).maxdd).toBeCloseTo(-0.25);
  });
  it("compounds months", () => {
    const m = monthly(eq);
    expect(m.years).toEqual(["2024"]);
    expect(m.values[0][1]).toBeCloseTo(0.1);
  });
  it("measures excursions for a short against the high", () => {
    const e = excursions({ entry_date: "a", exit_date: "z", side: "short", entry: 100, exit: 95, pnl: 5, ret: 0.05 }, [{ time: "b", high: 108, low: 94 }]);
    expect(e.mae).toBeCloseTo(-0.08);
    expect(e.mfe).toBeCloseTo(0.06);
  });
  it("shuffling keeps the final return and is repeatable", () => {
    const r = [10, -5, 2, -8, 4], a = shuffleTrades(r, 100, 50, 7), b = shuffleTrades(r, 100, 50, 7);
    expect(a.final.every((x) => Math.abs(x - a.orig.ret) < 1e-9)).toBe(true);
    expect(a.dd).toEqual(b.dd);
  });
});
