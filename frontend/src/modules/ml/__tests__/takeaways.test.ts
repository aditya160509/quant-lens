import { describe, it, expect } from "vitest";
import { takeaway } from "../takeaways";
import type { FeatureResult } from "@/modules/research/types";

/** Trimmed from real saved runs; only the fields the generators read. */
const res = (tables: Record<string, unknown[]>, extra: Record<string, unknown> = {}) => ({ tables, charts: {}, summary_cards: [], meta: {}, ...extra }) as unknown as FeatureResult;

describe("ML takeaways", () => {
  it("states the model against the best control, and says when the IC interval includes zero", () => {
    const r = res({ controls: [
      { model: "ensemble", primary: true, test_ic: 0.0595, ic_tstat: 0.89 },
      { model: "ic_composite", primary: false, test_ic: 0.099 },
      { model: "ridge", primary: false, test_ic: 0.027 },
    ] });
    expect(takeaway("ml02", "controls", undefined, r)).toBe("The ensemble trails the IC-weighted composite (0.059 vs 0.099) on held-out IC; its interval includes zero");
  });

  it("compares vol-targeting with unmanaged on Sharpe and drawdown", () => {
    const r = res({ position_sizing: [
      { strategy: "unmanaged", sharpe: 1.606, max_drawdown: -0.138 },
      { strategy: "vol_targeted", sharpe: 1.179, max_drawdown: -0.104 },
    ] });
    expect(takeaway("ml03", "position_sizing", undefined, r)).toBe("Vol-targeting lowered Sharpe to 1.18 from 1.61, drawdown -10% vs -14%");
  });

  it("judges VaR calibration from the Kupiec test", () => {
    const r = res({ var_es: [{ horizon: 1, level: 0.99, var: 0.0419, oos_breach_rate: 0, kupiec_p_value: 0.054 }] });
    expect(takeaway("ml03", "var_es", undefined, r)).toBe("One-day 99% VaR is 4.2%; breached 0.0% of held-out days vs 1% expected, calibration passes");
  });

  it("reads Validate sections", () => {
    const r = res({}, { sections: { controls: { strategy_sharpe: 0.99, best_control_sharpe: 1.56, best_control: "equal_weight" }, monte_carlo: { prob_sharpe_not_positive: 0.17 } } });
    expect(takeaway("mlvalidate", "controls", undefined, r)).toBe("Sharpe 0.99 trails the best simple alternative, equal weight (1.56)");
    expect(takeaway("mlvalidate", "monte_carlo", undefined, r)).toBe("17% of resampled histories have no positive Sharpe");
  });

  it("does not call a tiny purging gap an overstatement", () => {
    const r = res({ purged_vs_naive_cv_comparison: [{ method: "naive_cpcv", sharpe: 0.0148 }, { method: "purged_cpcv", sharpe: -0.0365 }] });
    expect(takeaway("ml01", "purged_vs_naive_cv_comparison", undefined, r)).toBe("Purging barely moves Sharpe (0.01 to -0.04): no leakage inflation");
  });

  it("returns null when the data cannot support a sentence, or for an unknown exhibit", () => {
    expect(takeaway("ml02", "controls", undefined, res({ controls: [] }))).toBeNull();
    expect(takeaway("ml02", "nope", undefined, res({}))).toBeNull();
  });
});
