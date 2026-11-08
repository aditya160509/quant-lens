import { describe, it, expect } from "vitest";
import { CalendarHeatmap } from "@/charts/CalendarHeatmap";
import { Dumbbell } from "@/charts/Dumbbell";
import { Heatmap } from "@/charts/Heatmap";
import { RankList, Spark } from "@/charts/RankList";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { verdictFor } from "../layouts";
import { specTitle } from "../format";
import { clusterIds, leafOrder, validLinkage } from "@/charts/clustering";
import { DataTable, TestsTable } from "../outputs/tables";
import { toMarkdown } from "@/kit/DataTable";
import { StudyForm, toPayload, validate } from "../StudyForm";
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

describe("monthly calendar semantics", () => {
  it("averages repeated months and distinguishes zero from missing observations", () => {
    render(<CalendarHeatmap title="Monthly IC" data={[
      { date: "2026-01-01", value: 0.2 }, { date: "2026-01-31", value: 0.4 },
      { date: "2026-02-01", value: 0 }, { date: "invalid", value: 1 },
      { date: "2026-03-01", value: Number.NaN },
    ]} />);
    expect(screen.getByRole("table", { name: "Monthly IC" })).toBeInTheDocument();
    expect(within(screen.getByRole("table", { name: "Monthly IC" })).getByTitle("Jan 2026: 0.300")).toHaveTextContent("0.300");
    expect(within(screen.getByRole("table", { name: "Monthly IC" })).getByTitle("Feb 2026: 0.000")).toHaveTextContent("0.000");
    expect(within(screen.getByRole("table", { name: "Monthly IC" })).getByTitle("Mar 2026: No observation")).toHaveTextContent("–");
  });

  it("sums counts only when explicitly requested", () => {
    render(<CalendarHeatmap title="Runs" signed={false} aggregate="sum" data={[
      { date: "2026-01-01", value: 2 }, { date: "2026-01-02", value: 3 },
    ]} format={String} />);
    expect(within(screen.getByRole("table", { name: "Runs" })).getByTitle("Jan 2026: 5")).toHaveTextContent("5");
  });
});


describe("table markdown", () => {
  it("keeps every row in one column per field when cells hold pipes or newlines", () => {
    expect(toMarkdown(["ticker", "note"], [{ ticker: "A|B", note: "one\ntwo" }, { ticker: "C", note: null }])).toBe(
      "| Ticker | Note |\n| --- | --- |\n| A\\|B | one two |\n| C |  |",
    );
  });
});

describe("ranked contributions", () => {
  it("sorts by magnitude and lets readers reveal every finite contribution", () => {
    render(<RankList title="Drivers" top={2} format={String} items={[
      { label: "family/small", value: 1 }, { label: "family/negative", value: -5 },
      { label: "family/large", value: 4 }, { label: "invalid", value: Number.NaN },
    ]} />);
    expect(screen.getAllByRole("listitem")[0]).toHaveTextContent("negative");
    expect(screen.queryByText("small")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show all 3" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByText("small")).toBeInTheDocument();
    expect(screen.queryByText("invalid")).not.toBeInTheDocument();
  });

  it("draws a trend from finite samples and survives gaps", () => {
    const { container } = render(<Spark values={[1, Number.NaN, 2, Number.POSITIVE_INFINITY, 3]} />);
    const line = container.querySelector("polyline");
    expect(line).not.toBeNull();
    expect(line?.getAttribute("points")).not.toMatch(/NaN|Infinity/);
    expect(line?.getAttribute("points")?.split(" ")).toHaveLength(3);
  });
});


describe("cinema interaction regressions", () => {
  it("keeps every table row reachable and sorts across pages", () => {
    render(<DataTable rows={Array.from({ length: 5 }, (_, i) => ({ ticker: `Name${i}`, score: i }))} opts={{ max: 2 }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Rows 1–2 of 5");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("status")).toHaveTextContent("Rows 3–4 of 5");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("status")).toHaveTextContent("Rows 5–5 of 5");
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Score" }));
    fireEvent.click(screen.getByRole("button", { name: "Score" }));
    expect(screen.getByRole("status")).toHaveTextContent("Rows 1–2 of 5");
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Name4");
  });

  it("draws percentile bars and pins a chosen column first", () => {
    const { container } = render(<DataTable rows={[{ ticker: "AAA", sector_relative_score: 80, price: 3 }]} opts={{ bars: ["sector_relative_score"] }} />);
    expect(container.querySelector(".pbar > i")).toHaveStyle({ width: "80%" });
    fireEvent.click(screen.getByRole("button", { name: "Table options" }));
    fireEvent.click(screen.getByRole("button", { name: "Pin Price" }));
    expect(container.querySelector("th[data-col='price']")?.getAttribute("style")).toContain("sticky");
  });

  it("keeps cluster identity consistent below the cut and rejects cyclic linkage", () => {
    const merges = [{ left: 0, right: 1, distance: 1 }, { left: 2, right: 3, distance: 2 }, { left: 4, right: 5, distance: 5 }];
    expect(leafOrder(merges, 4)).toEqual([0, 1, 2, 3]);
    expect(clusterIds(merges, 4, 3)).toEqual([0, 0, 1, 1]);
    expect(clusterIds(merges, 4, 5)).toEqual([0, 0, 0, 0]);
    expect(clusterIds(merges, 4, 0)).toEqual([0, 1, 2, 3]);
    expect(validLinkage([{ left: 0, right: 2, distance: 1 }], 2)).toBe(false);
    expect(validLinkage([{ left: 0, right: 0, distance: 1 }], 2)).toBe(false);
  });


});


describe("heat table ordering", () => {
  it("sorts rows and columns while preserving labels, missing cells and totals", () => {
    render(<Heatmap rows={["A", "B"]} cols={["X", "Y"]} values={[[1, 4], [3, null]]} totals format={String} />);
    fireEvent.click(screen.getByRole("button", { name: "X" }));
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("B3–");
    fireEvent.click(screen.getByRole("button", { name: "A" }));
    expect(screen.getAllByRole("columnheader")[1]).toHaveTextContent("Y");
    expect(screen.getAllByRole("row").at(-1)).toHaveTextContent("Total44");
    expect(screen.getByTitle("B · Y: No observation")).toHaveTextContent("–");
    fireEvent.click(screen.getByRole("button", { name: "Reset order" }));
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("A14");
  });
});


describe("study feedback", () => {
  it("validates edits before submission and clears corrected errors", () => {
    const spec = { ...feature, inputs: [{ key: "horizon", type: "number" as const, default: 21, min: 1, max: 63, group: "Model", label: "Horizon", help: "Number of sessions ahead to predict." }] };
    const { rerender } = render(<StudyForm feature={spec} form={{ horizon: 0 }} setForm={() => {}} errors={{}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Minimum 1");
    expect(screen.getByRole("button", { name: /Explain this setting/ })).toBeInTheDocument();
    rerender(<StudyForm feature={spec} form={{ horizon: 21 }} setForm={() => {}} errors={{ horizon: "Minimum 1" }} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});


it("aggregates activity by UTC weekday and hour without filling missing hours", () => {
  render(<CalendarHeatmap hourly title="Activity" aggregate="sum" signed={false} format={String} data={[
    { date: "2026-10-19T10:15:00Z", value: 1 }, { date: "2026-10-26T10:30:00Z", value: 1 },
  ]} />);
  fireEvent.click(screen.getByRole("button", { name: "Weekday × hour (UTC)" }));
  const table = within(screen.getByRole("table", { name: "Activity" }));
  expect(table.getByTitle("Mon 10:00 UTC: 2")).toHaveTextContent("2");
  expect(table.getByTitle("Mon 11:00 UTC: No observation")).toHaveTextContent("–");
});


it("requires a validation source before submitting a job", () => {
  const spec: FeatureSpec = { ...feature, id: "mlvalidate", inputs: [{ key: "upload_id", label: "Data", type: "text", group: "Data" }] };
  expect(validate(spec, {}).upload_id).toMatch(/Upload data/);
  expect(validate(spec, { artifact_id: "allocation-result" })).toEqual({});
  expect(validate(spec, { upload_id: "uploaded-returns" })).toEqual({});
});


it("keeps zero-change dumbbells finite on a shared scale", () => {
  const { container } = render(<Dumbbell shared aLabel="Before" bLabel="After" rows={[{ label: "Cost", a: 0, b: 0, format: String }]} />);
  expect(container.querySelector(".db-dot.a[title]")).toHaveStyle({ left: "50%" });
  expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
});
