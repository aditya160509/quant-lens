import { describe, expect, it } from "vitest";
import { bootstrapTrades, drawdown, excursions, minMax, monthly, returns, rollingSharpe, shuffleTrades, stats, topDrawdowns, tradeSummary } from "../build/devStats";

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
  it("summarises trades for the tester drawer", () => {
    const s = tradeSummary([{ pnl: 100 }, { pnl: -50 }, { pnl: -30 }, { pnl: 80 }, { pnl: "x" }]);
    expect(s.net).toBe(100);
    expect(s.trades).toBe(4);
    expect(s.win).toBe(0.5);
    expect(s.pf).toBeCloseTo(180 / 80);
    expect(s.maxdd).toBe(-80);
    expect(tradeSummary([]).pf).toBeNull();
  });
  it("measures trade drawdown in exit order, not array order", () => {
    // In entry order the loss comes last; by exit date it lands between the two wins.
    const s = tradeSummary([{ pnl: 100, exit_date: "2024-01-10" }, { pnl: 50, exit_date: "2024-03-01" }, { pnl: -80, exit_date: "2024-02-01" }]);
    expect(s.curve.map((p) => p.net)).toEqual([100, 20, 70]);
    expect(s.maxdd).toBe(-80);
  });
  it("finds min and max of arrays too large to spread", () => {
    expect(minMax(Array.from({ length: 300_000 }, (_, i) => i - 1000))).toEqual([-1000, 298_999]);
  });
  it("handles empty and one-row equity without throwing or inventing figures", () => {
    expect(topDrawdowns([])).toEqual([]);
    expect(drawdown([])).toEqual([]);
    const one = [{ date: "2024-01-01", value: 100 }];
    expect(topDrawdowns(one)).toEqual([]);
    const s = stats(one);
    expect(s.total).toBeNull();
    expect(s.cagr).toBeNull();
    expect(s.sharpe).toBeNull();
    expect(s.hit).toBeNull();
    expect(stats([{ date: "2024-01-01", value: 1 }, { date: "2025-01-01", value: 1 }]).sharpe).toBeNull();
  });
  it("never divides by a zero or negative level", () => {
    const zero = [0, 0, 10, 12].map((value, i) => ({ date: `2024-0${i + 1}-01`, value }));
    expect(returns(zero)).toHaveLength(1);
    expect(returns(zero)[0]).toBeCloseTo(0.2);
    expect(drawdown(zero).map((d) => d.dd)).toEqual([null, null, 0, 0]);
    expect(stats(zero).total).toBeNull();
    expect(stats(zero).cagr).toBeNull();
    expect(monthly(zero).values[0].slice(0, 3)).toEqual([null, null, null]);
    expect(rollingSharpe(zero, 1).map((r) => r.date)).toEqual(["2024-04-01"]);
  });
  it("reports bankruptcy as a total loss, all values finite", () => {
    const bust = [100, 120, 50, 0, -20].map((value, i) => ({ date: `202${i}-01-01`, value }));
    const s = stats(bust);
    expect(s.total).toBeCloseTo(-1.2);
    expect(s.cagr).toBe(-1);
    expect(Object.values(s).every((v) => v === null || Number.isFinite(v))).toBe(true);
    expect(topDrawdowns(bust)[0].depth).toBeCloseTo(-20 / 120 - 1);
    expect(returns(bust).every(Number.isFinite)).toBe(true);
  });
  it("trade paths need positive capital and trades", () => {
    expect(shuffleTrades([1, 2, 3], 0, 10)).toBeNull();
    expect(bootstrapTrades([1, 2, 3], -5, 10)).toBeNull();
    expect(bootstrapTrades([], 100, 10)).toBeNull();
    const bust = shuffleTrades([-150, 10, 20], 100, 20, 3)!;
    expect(bust.final.every(Number.isFinite) && bust.dd.every(Number.isFinite)).toBe(true);
  });
});
