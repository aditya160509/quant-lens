import { describe, expect, it } from "vitest";
import { insertUse } from "../build/IndicatorPicker";

const rsi = { name: "RSI", inputs: { length: [14, 2, 100, 1] as [number, number, number, number] } };

describe("insertUse", () => {
  it("appends to an existing init and adds the import", () => {
    const code = "class Strategy:\n    def init(self, ctx):\n        self.n = 0\n\n    def on_bar(self, ctx):\n        pass\n";
    expect(insertUse(code, rsi)).toBe("from studio import ta\n\nclass Strategy:\n    def init(self, ctx):\n        self.n = 0\n        self.rsi = self.use(ta.RSI, length=14)\n\n    def on_bar(self, ctx):\n        pass\n");
  });
  it("creates init when missing, keeps an existing import, and picks a free name", () => {
    const code = "from studio import ta\n\nclass Strategy:\n    def on_bar(self, ctx):\n        x = self.rsi\n";
    expect(insertUse(code, rsi)).toBe("from studio import ta\n\nclass Strategy:\n    def init(self, ctx):\n        self.rsi_2 = self.use(ta.RSI, length=14)\n\n    def on_bar(self, ctx):\n        x = self.rsi\n");
  });
  it("snake-cases names and refuses code without a Strategy class", () => {
    expect(insertUse("class Strategy:\n    pass\n", { name: "RelativeStrength", inputs: {} })).toContain("self.relative_strength = self.use(ta.RelativeStrength)");
    expect(insertUse("x = 1\n", rsi)).toBeNull();
  });
});
