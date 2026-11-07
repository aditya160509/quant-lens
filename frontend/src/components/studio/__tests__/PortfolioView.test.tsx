import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import PortfolioView, { parseHoldingsCsv, parseReturnCsv } from "../PortfolioView";
import { studioRequest } from "@/lib/studioApi";

vi.mock("@/lib/studioApi", () => ({ studioRequest: vi.fn() }));
const request = studioRequest as ReturnType<typeof vi.fn>;
const fillAssumptions = () => {
  [[1, "SPY", "8", "20", "50"], [2, "TLT", "4", "10", "50"]].forEach(([index, ticker, expected, volatility, current]) => {
    fireEvent.change(screen.getByLabelText(`ticker ${index}`), { target: { value: ticker } });
    fireEvent.change(screen.getByLabelText(`expected ${index}`), { target: { value: expected } });
    fireEvent.change(screen.getByLabelText(`volatility ${index}`), { target: { value: volatility } });
    fireEvent.change(screen.getByLabelText(`current ${index}`), { target: { value: current } });
  });
};

describe("PortfolioView", () => {
  beforeEach(() => {
    request.mockReset();
  });
  it("submits explicit assumptions and renders a reconciled artifact", async () => {
    request.mockResolvedValue({ portfolio: {
      artifact_id: "portfolio_test", engine_version: "studio-portfolio-1.0", objective: "max_sharpe",
      assets: ["SPY", "TLT", "GLD"], weights: { SPY: 0.4, TLT: 0.35, GLD: 0.25 },
      trades: { SPY: -0.1, TLT: 0.05, GLD: 0.05 }, risk_contribution: { SPY: 0.5, TLT: 0.2, GLD: 0.3 },
      metrics: { expected_return: 0.06, volatility: 0.11, sharpe: 0.545, tracking_error: null, turnover: 0.2, estimated_cost_fraction: 0.0002, gross_leverage: 1, concentration_hhi: 0.345 },
      model: { expected_returns: "supplied", covariance: "supplied", observations: null, periods_per_year: 252, condition_number: 4, minimum_eigenvalue: 0.01, shrinkage: null },
      constraint_exposures: [], frontier: [{ return: 0.04, volatility: 0.08 }, { return: 0.08, volatility: 0.2 }], warnings: ["Unavailable fields are explicit."],
    }});
    render(<PortfolioView />);
    fillAssumptions();
    fireEvent.click(screen.getByRole("button", { name: "Optimize" }));

    await waitFor(() => expect(request).toHaveBeenCalledWith("/portfolio/optimize", expect.objectContaining({ method: "POST", retries: 0 })));
    const payload = request.mock.calls[0][1].body;
    expect(payload.assets).toEqual(["SPY", "TLT"]);
    expect(payload.covariance).toHaveLength(2);
    expect(screen.getByText("portfolio_test")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /efficient frontier/i })).toBeInTheDocument();
    expect(screen.getAllByText("20.00%").length).toBeGreaterThanOrEqual(1);
  });

  it("shows typed infeasibility without fabricating output", async () => {
    request.mockRejectedValue(new Error("position bounds cannot satisfy the required net weight of 1"));
    render(<PortfolioView />);
    fillAssumptions();
    fireEvent.click(screen.getByRole("button", { name: "Optimize" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("cannot satisfy");
    expect(screen.queryByText(/portfolio_/)).not.toBeInTheDocument();
  });

  it("parses aligned user return observations without supplying output values", () => {
    expect(parseReturnCsv("date,spy,tlt\n2025-01-01,0.01,-0.01\n2025-01-02,0.02,0\n2025-01-03,-0.01,0.01")).toEqual({
      assets: ["SPY", "TLT"], observations: [[0.01, -0.01], [0.02, 0], [-0.01, 0.01]],
    });
    expect(() => parseReturnCsv("SPY,TLT\n0.1,nope\n0.2,0.1\n0.0,0.0")).toThrow("Invalid return observation");
  });

  it("imports user holdings from weights or market values", () => {
    expect(parseHoldingsCsv("ticker,current_weight,expected_return,volatility\nSPY,60,8,20\nTLT,40,4,10")).toEqual([
      { ticker: "SPY", current: "60", expected: "8", volatility: "20" },
      { ticker: "TLT", current: "40", expected: "4", volatility: "10" },
    ]);
    const values = parseHoldingsCsv("symbol,market_value\nSPY,75000\nGLD,25000");
    expect(values.map((item) => Number(item.current))).toEqual([75, 25]);
  });
});
