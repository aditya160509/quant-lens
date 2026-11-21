import { describe, expect, it } from "vitest";
import { runArgs, words } from "../build/Terminal";

describe("terminal", () => {
  it("splits quoted words", () => expect(words('atlas run --costs "US retail" --top 20')).toEqual(["atlas", "run", "--costs", "US retail", "--top", "20"]));
  it("maps run flags to run settings", () => {
    expect(runArgs(["full", "--symbols", "aapl,msft", "--from", "2020-01-01", "--top", "20"])).toEqual({ level: "full", settings: { symbols: "AAPL MSFT", start: "2020-01-01", top_n: 20 } });
    expect(() => runArgs(["--nope"])).toThrow(/Unknown flag/);
  });
});
