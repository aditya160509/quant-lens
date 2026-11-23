import { describe, expect, it } from "vitest";
import { minMax, tradeSummary } from "../build/devStats";

describe("devStats", () => {
  it("measures drawdown in exit order, not array order", () => {
    // In entry order the loss comes last; by exit date it lands between the two wins.
    const s = tradeSummary([
      { pnl: 100, exit_date: "2024-01-10" },
      { pnl: 50, exit_date: "2024-03-01" },
      { pnl: -80, exit_date: "2024-02-01" },
    ]);
    expect(s.curve.map((p) => p.net)).toEqual([100, 20, 70]);
    expect(s.maxdd).toBe(-80);
  });

  it("handles arrays too large to spread", () => {
    const xs = Array.from({ length: 300_000 }, (_, i) => i - 1000);
    expect(minMax(xs)).toEqual([-1000, 298_999]);
  });
});
