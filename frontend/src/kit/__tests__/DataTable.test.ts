import { describe, expect, it } from "vitest";
import { fixedFmt, groupCols } from "../DataTable";

describe("DataTable columns", () => {
  it("groups only adjacent columns sharing a prefix", () => {
    const g = groupCols(["symbol", "entry_date", "entry_price", "exit_date", "pnl", "exit_reason"]);
    expect(g.map((x) => x.head)).toEqual([null, "entry", null, null, null]);
    expect(g[1].span).toBe(2);
  });
  it("uses fixed decimals per column kind", () => {
    expect(fixedFmt("pnl", [1])!(-1290.1)).toBe("-1,290.10");
    expect(fixedFmt("mae", [0.1])!(-0.0312)).toBe("-3.1%");
    expect(fixedFmt("bars", [3])!(12)).toBe("12");
    expect(fixedFmt("shares", [1.5])!(1.5)).toBe("1.500");
    expect(fixedFmt("symbol", ["A"])).toBeNull();
  });
});
