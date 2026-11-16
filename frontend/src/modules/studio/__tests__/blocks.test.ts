import { describe, expect, it } from "vitest";
import { fromFormula, toFormula } from "../build/blocks";

describe("blocks ⇄ formula", () => {
  it("round-trips the RSI(2) dip template", () => {
    const rows = fromFormula("(rsi(close, 2) < low_level) & (close > sma(close, 200))")!;
    expect(rows).toEqual([{ left: "rsi(close, 2)", op: "<", right: "low_level", join: "&" }, { left: "close", op: ">", right: "sma(close, 200)", join: "&" }]);
    expect(toFormula(rows)).toBe("(rsi(close, 2) < low_level) & (close > sma(close, 200))");
  });
  it("reads crosses and or-joins", () => {
    const rows = fromFormula("crosses_above(sma(close, fast), sma(close, slow)) | (close >= highest(high, 20))")!;
    expect(rows.map((r) => [r.op, r.join])).toEqual([["crosses_above", "&"], [">=", "|"]]);
    expect(fromFormula(toFormula(rows))).toEqual(rows);
  });
  it("refuses shapes blocks cannot show", () => {
    expect(fromFormula("rank(roc(close, 126))")).toBeNull();
    expect(fromFormula("close > open > low")).toBeNull();
  });
});
