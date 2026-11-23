import { describe, expect, it } from "vitest";
import { fuzzy, py, runArgs, words } from "../build/Terminal";

describe("terminal", () => {
  it("writes preview data as Python literals", () => expect(py({ a: [1, null, true, NaN], "b\"": 'x"y' })).toBe('{"a": [1, None, True, None], "b\\"": "x\\"y"}'));
  it("fuzzy-matches history", () => { expect(fuzzy("arq", "atlas run quick")).toBe(true); expect(fuzzy("qra", "atlas run quick")).toBe(false); });
  it("splits quoted words", () => expect(words('atlas run --costs "US retail" --top 20')).toEqual(["atlas", "run", "--costs", "US retail", "--top", "20"]));
  it("maps run flags to run settings", () => {
    expect(runArgs(["full", "--symbols", "aapl,msft", "--from", "2020-01-01", "--top", "20"])).toEqual({ level: "full", settings: { symbols: "AAPL MSFT", start: "2020-01-01", top_n: 20 } });
    expect(() => runArgs(["--nope"])).toThrow(/Unknown flag/);
  });
});
