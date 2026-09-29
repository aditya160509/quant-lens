import { render, screen } from "@testing-library/react";
import { toPayload, validate } from "../StudyForm";
import { PublicationTable, RenderOutput, ReportCard, TestCard } from "../renderers";

const feature = {
  id: "01",
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

describe("renderers", () => {
  it("renders a journal table with coefficient, standard-error and statistics rows", () => {
    render(<PublicationTable value={[
      { row: "Momentum", kind: "coefficient", "(1)": "0.011*" },
      { row: "", kind: "se", "(1)": "(0.006)" },
      { row: "Observations", kind: "stat", "(1)": "7,860" },
    ]} />);
    expect(screen.getByText("0.011*")).toBeInTheDocument();
    expect(screen.getByText("(0.006)")).toBeInTheDocument();
    expect(screen.getByText("Observations")).toBeInTheDocument();
  });

  it("shows the headline statistic, p-value and verdict of a test", () => {
    render(<TestCard value={[{ f_stat: 8.57, p_value: 0.0002, verdict: "coefficients differ across regimes", df1: 2 }]} />);
    expect(screen.getByText("8.570")).toBeInTheDocument();
    expect(screen.getByText("coefficients differ across regimes")).toBeInTheDocument();
  });

  it("marks red diagnostics with their recommended fix", () => {
    render(<ReportCard value={[{ test: "Breusch-Pagan", statistic: 37.2, p_value_or_threshold: 0.00001, flag: "red", explanation: "x", recommendation: "Use robust SEs." }]} />);
    expect(screen.getByText("Use robust SEs.")).toBeInTheDocument();
  });

  it("explains a missing output instead of rendering an empty card", () => {
    render(<RenderOutput output={{ key: "grs_test", source: "tables", render: "testCard" }} response={{ tables: {} }} />);
    expect(screen.getByText(/Not produced/)).toBeInTheDocument();
  });
});
