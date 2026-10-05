import { fireEvent, render, screen } from "@testing-library/react";
import StudioActivityRail from "../shell/StudioActivityRail";
import ExecutionAssumptionsPanel from "../shell/ExecutionAssumptionsPanel";
import DataInspectorPanel from "../shell/DataInspectorPanel";
import { useStudioPreferenceStore } from "@/stores/studio/preferenceStore";
import { useStudioWorkspaceStore } from "@/stores/studio/workspaceStore";
import { useStudioResultStore } from "@/stores/studio/resultStore";

jest.mock("@/hooks/studio/useDataStudio", () => ({
  useDataStudio: () => ({
    loadCatalog: jest.fn().mockResolvedValue([{ name: "market_universe", source_type: "OHLCV", update_frequency: "daily" }]),
    loadFreshness: jest.fn().mockResolvedValue([{ source_name: "market_universe", status: "fresh", data_as_of: "2026-01-02", lag_trading_days: 0 }]),
    loadManifests: jest.fn().mockResolvedValue({ datasets: [{ id: "market_universe_daily", status: "valid", rows: 10, format: "parquet", path: "backend/data/market_universe.parquet", provenance: { source: "test", license_status: "review", transformation_version: "v1", point_in_time_policy: "not guaranteed", adjustment_policy: "proxy" } }] }),
    loadUploads: jest.fn().mockResolvedValue({ uploads: [] }),
    deleteUpload: jest.fn().mockResolvedValue({ status: "deleted" }),
    loadSeries: jest.fn().mockResolvedValue({ count: 0, total_count: 0, limit: 100, series: [] }),
    uploadDataset: jest.fn().mockResolvedValue({ source_name: "sample", validation_report: { rows: 1 } }),
    cancel: jest.fn(),
  }),
}));

describe("Studio shell controls", () => {
  beforeEach(() => {
    useStudioPreferenceStore.setState({ kernelCollapsed: false });
    useStudioWorkspaceStore.setState({ slippageBps: 1, commissionPct: 0.01 });
  });

  it("updates the editor rail through the preference store", () => {
    render(<StudioActivityRail settingsOpen={false} onToggleSettings={jest.fn()} dataOpen={false} onToggleData={jest.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Toggle strategy editor" }));

    expect(useStudioPreferenceStore.getState().kernelCollapsed).toBe(true);
  });

  it("updates execution assumptions and exposes a close action", () => {
    const onClose = jest.fn();
    render(<ExecutionAssumptionsPanel onClose={onClose} />);

    fireEvent.change(screen.getByRole("slider", { name: "Slippage basis points" }), { target: { value: "4.5" } });
    fireEvent.change(screen.getByRole("slider", { name: "Commission percent" }), { target: { value: "0.08" } });
    fireEvent.click(screen.getByRole("button", { name: "Close execution assumptions" }));

    expect(useStudioWorkspaceStore.getState().slippageBps).toBe(4.5);
    expect(useStudioWorkspaceStore.getState().commissionPct).toBe(0.08);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("opens the shared data inspector from the activity rail", () => {
    const onToggleData = jest.fn();
    render(<StudioActivityRail settingsOpen={false} onToggleSettings={jest.fn()} dataOpen={false} onToggleData={onToggleData} />);
    fireEvent.click(screen.getByRole("button", { name: "Toggle data inspector" }));
    expect(onToggleData).toHaveBeenCalledTimes(1);
  });

  it("renders governed inventory and reported data-quality fields", async () => {
    const onClose = jest.fn();
    useStudioResultStore.setState((state) => ({ data: { ...state.data, candles: [{ time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }], metadata: { data_quality: { status: "observed", source: "test-source", observations: 1, timezone: "UTC", currency: "USD", calendar: "XNYS", corporate_actions: "unknown", look_ahead_check: "not_verified" }, warnings: [] } } }));
    render(<DataInspectorPanel onClose={onClose} />);
    expect(screen.getAllByText("test-source")).toHaveLength(2);
    expect(screen.getByText("unknown")).toBeInTheDocument();
    expect(await screen.findByText("market_universe")).toBeInTheDocument();
    expect(screen.getByText("market_universe_daily · valid")).toBeInTheDocument();
    expect(screen.getByText(/daily · fresh/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("market_universe").closest("button")!);
    expect(await screen.findByRole("table", { name: "Virtualized dataset preview" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close data inspector" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
