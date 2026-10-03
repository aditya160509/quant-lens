import { render, screen } from "@testing-library/react";
import { verdictFor } from "../layouts";
import { specTitle } from "../format";
import { TestsTable } from "../outputs/tables";
import { toPayload, validate } from "../StudyForm";
import type { FeatureResult, FeatureSpec } from "../types";

const feature: FeatureSpec = {
  id: "01",
  name: "Canonical Test Engine",
  description: "",
  outputs: [],
  inputs: [
    { key: "max_symbols", type: "number", default: 400, min: 30, max: 2000, group: "Universe", label: "Size" },
    { key: "forward_months", type: "select", options: [1, 3, 6], default: 1, group: "Spec", label: "Horizon" },
    { key: "controls", type: "select", options: ["none", "full"], default: "none", group: "Spec", label: "Controls" },
    { key: "universe_filters", type: "multiselect", options: ["large_cap"], default: [], group: "Universe", label: "Filters" },
    { key: "table_columns", type: "json", default: "", group: "Table", label: "Columns" },
    { key: "signal_csv_path", type: "file", default: "", group: "Signal", label: "Upload" },
  ],
};

describe("study form payload", () => {
  it("coerces numbers and numeric selects, parses JSON and drops blanks", () => {
    const payload = toPayload(feature, { max_symbols: "250", forward_months: "3", controls: "full", universe_filters: [], table_columns: '[{"label":"(1)"}]', signal_csv_path: "" });
    expect(payload).toEqual({ max_symbols: 250, forward_months: 3, controls: "full", universe_filters: [], table_columns: [{ label: "(1)" }] });
  });

  it("flags out-of-range numbers and invalid JSON", () => {
    const errors = validate(feature, { max_symbols: "5", table_columns: "{not json" });
    expect(errors.max_symbols).toMatch(/Minimum 30/);
    expect(errors.table_columns).toMatch(/JSON/);
  });
});

describe("outputs", () => {
  it("shows a test's statistic, p-value decision and verdict", () => {
    const result: FeatureResult = { feature_id: "04", status: "ok", charts: {}, meta: {}, tables: { chow_test: [{ f_stat: 8.57, p_value: 0.0002, verdict: "coefficients differ across regimes", df1: 2 }] } };
    const f04: FeatureSpec = { ...feature, id: "04", outputs: [{ key: "chow_test", title: "Chow test", source: "tables", render: "testCard" }] };
    render(<TestsTable rows={[]} result={result} feature={f04} keys={["chow_test"]} scope="t" />);
    expect(screen.getByText("Chow test")).toBeInTheDocument();
    expect(screen.getByText("8.570")).toBeInTheDocument();
    expect(screen.getByText("Reject 1%")).toBeInTheDocument();
  });

  it("names specifications in plain language", () => {
    expect(specTitle("base")).toBe("Base specification");
    expect(specTitle("subsample=pre_2020; controls=size,value")).toBe("Subsample: Pre 2020 · Controls: Size + Value");
  });
});

describe("robustness verdict", () => {
  const result = (sig: number, total: number, p: number): FeatureResult => ({
    feature_id: "02", status: "ok", charts: {}, meta: {},
    tables: { robustness_summary_line: [{ significant_5pct: sig, specifications: total }], curve_level_joint_p_value: [{ p_value: p }] },
  });
  const f02: FeatureSpec = { ...feature, id: "02" };

  it("calls a signal robust only when most specifications and the whole curve pass", () => {
    expect(verdictFor(f02, result(20, 32, 0.01)).tone).toBe("up");
    expect(verdictFor(f02, result(20, 32, 0.2)).tone).toBe("down");
    expect(verdictFor(f02, result(10, 32, 0.07)).tone).toBe("warn");
    expect(verdictFor(f02, result(0, 32, 0.66)).headline).toMatch(/^Not robust\. Only 0 of 32/);
  });
});
