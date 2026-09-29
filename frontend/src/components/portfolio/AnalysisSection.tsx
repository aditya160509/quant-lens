'use client';

import React, { useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import type { PlotParams } from 'react-plotly.js';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false }) as React.ComponentType<PlotParams>;
const API_BASE = 'http://127.0.0.1:8000/api';


// =============================================================================
// ANALYSIS TAB - Features 41-43: Holdings Overlap, Dividend Tracker, Tax Lots
// =============================================================================

const KPICard = ({ label, value, subtitle = '', color = 'default' }: { label: string; value: any; subtitle?: string; color?: string }) => {
  const colorClasses = {
    emerald: 'text-[var(--terminal-green)]',
    red: 'text-[var(--terminal-red)]',
    amber: 'text-[var(--terminal-orange)]',
    default: 'text-[var(--terminal-cyan)]',
    low: 'text-[var(--terminal-green)]',
    medium: 'text-[var(--terminal-orange)]',
    high: 'text-[var(--terminal-red)]'
  };
  return (
    <div className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded-lg p-4">
      <div className="text-xs text-[var(--terminal-dim)] uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-2xl font-bold ${colorClasses[color] || colorClasses.default}`}>{value}</div>
      {subtitle && <div className="text-xs text-[var(--terminal-dim)] mt-1 opacity-70">{subtitle}</div>}
    </div>
  );
};

const LoadingSpinner = () => (
  <div className="flex items-center justify-center p-8">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--terminal-cyan)]"></div>
  </div>
);

// --- Holdings Overlap Component ---
export const HoldingsOverlap = () => {
  const [portfolios, setPortfolios] = useState([
    { name: 'Portfolio 1', holdings: 'AAPL:0.3,MSFT:0.25,GOOGL:0.2,AMZN:0.15,NVDA:0.1' },
    { name: 'Portfolio 2', holdings: 'AAPL:0.25,MSFT:0.20,META:0.2,TSLA:0.2,NVDA:0.15' }
  ]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const parsePortfolios = useCallback(() => {
    return portfolios.map(p => ({
      name: p.name,
      holdings: p.holdings.split(',').map(h => {
        const [ticker, weight] = h.trim().split(':');
        return { ticker: ticker.trim().toUpperCase(), weight: parseFloat(weight) || 0 };
      })
    }));
  }, [portfolios]);

  const runAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/portfolio/overlap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolios: parsePortfolios() })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }, [parsePortfolios]);

  const updatePortfolio = (index, field, value) => {
    const updated = [...portfolios];
    updated[index][field] = value;
    setPortfolios(updated);
  };

  const addPortfolio = () => {
    setPortfolios([...portfolios, { name: `Portfolio ${portfolios.length + 1}`, holdings: '' }]);
  };

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">Holdings Overlap Analysis</h3>
        {portfolios.map((port, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-2">
            <input type="text" value={port.name} onChange={(e) => updatePortfolio(i, 'name', e.target.value)}
              placeholder="Portfolio Name"
              className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
            <input type="text" value={port.holdings} onChange={(e) => updatePortfolio(i, 'holdings', e.target.value)}
              placeholder="TICKER:WEIGHT,..."
              className="md:col-span-3 bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
          </div>
        ))}
        <div className="flex gap-2 mt-3">
          <button onClick={addPortfolio}
            className="bg-[var(--terminal-darker)] hover:bg-[var(--terminal-dark)] text-[var(--foreground)] border border-[var(--border)] px-3 py-2 rounded text-sm font-mono transition-colors">+ ADD PORTFOLIO</button>
          <button onClick={runAnalysis} disabled={loading}
            className="bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-4 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono uppercase">
            {loading ? 'ANALYZING...' : 'ANALYZE OVERLAP'}
          </button>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}
      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard label="Redundancy Score" value={`${result.metrics?.redundancy_score?.toFixed(0)}%`}
              color={result.metrics?.redundancy_score > 50 ? 'red' : result.metrics?.redundancy_score > 25 ? 'amber' : 'emerald'} />
            <KPICard label="Unique Holdings" value={result.metrics?.unique_holdings} />
            <KPICard label="Avg Overlap" value={`${result.metrics?.avg_pairwise_overlap?.toFixed(1)}%`} />
            <KPICard label="Mega-Cap Exp" value={`${(result.metrics?.mega_cap_exposure * 100)?.toFixed(1)}%`}
              color={result.metrics?.mega_cap_exposure > 0.3 ? 'amber' : 'default'} />
          </div>

          {/* Overlap Matrix */}
          {result.overlap_matrix && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3">Overlap Matrix (%)</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm font-mono">
                  <thead>
                    <tr>
                      <th className="text-left py-2 px-2 text-[var(--terminal-dim)]"></th>
                      {Object.keys(result.overlap_matrix).map(name => (
                        <th key={name} className="text-center py-2 px-2 text-[var(--terminal-dim)] uppercase text-xs">{name}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(result.overlap_matrix).map(([row, cols]) => (
                      <tr key={row} className="border-b border-[var(--border)]/10">
                        <td className="py-2 px-2 text-[var(--foreground)] font-bold">{row}</td>
                        {Object.values(cols as Record<string, number>).map((val, i) => (
                          <td key={i} className="text-center py-2 px-2">
                            <span className={`px-2 py-1 rounded text-xs font-bold ${
                              val >= 80 ? 'bg-[var(--terminal-red)]/20 text-[var(--terminal-red)]' :
                              val >= 50 ? 'bg-[var(--terminal-orange)]/20 text-[var(--terminal-orange)]' :
                              val >= 20 ? 'bg-[var(--terminal-cyan)]/20 text-[var(--terminal-cyan)]' :
                              'bg-[var(--terminal-darker)] text-[var(--terminal-dim)]'
                            }`}>{val?.toFixed(0)}%</span>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Overlapping Holdings */}
          {result.overlapping_holdings?.length > 0 && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3">Top Overlapping Holdings</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {result.overlapping_holdings.slice(0, 8).map((h, i) => (
                  <div key={i} className="bg-[var(--terminal-darker)] rounded p-2 border border-[var(--border)]/30">
                    <div className="flex justify-between items-center">
                      <span className="text-[var(--foreground)] font-bold font-mono">{h.ticker}</span>
                      <span className="text-[10px] uppercase font-bold bg-[var(--terminal-orange)]/20 text-[var(--terminal-orange)] px-2 py-0.5 rounded">
                        {h.count} portfolios
                      </span>
                    </div>
                    <div className="text-[10px] text-[var(--terminal-dim)] mt-1 uppercase font-mono">
                      Exposure: {(h.total_exposure * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// --- Dividend Tracker Component ---
export const DividendTracker = () => {
  const [positions, setPositions] = useState([
    { ticker: 'JNJ', shares: 50, cost_basis: 140 },
    { ticker: 'PG', shares: 40, cost_basis: 130 },
    { ticker: 'KO', shares: 100, cost_basis: 55 },
    { ticker: 'VZ', shares: 80, cost_basis: 40 }
  ]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/portfolio/dividends`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          positions: positions.map(p => ({ ticker: p.ticker, shares: p.shares, cost_basis: p.cost_basis })),
          reinvest: false,
          growth_rate: 0.03,
          horizon_years: 5
        })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }, [positions]);

  const updatePosition = (index, field, value) => {
    const updated = [...positions];
    updated[index][field] = field === 'shares' || field === 'cost_basis' ? Number(value) : value;
    setPositions(updated);
  };

  const addPosition = () => {
    setPositions([...positions, { ticker: '', shares: 0, cost_basis: 0 }]);
  };

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">Dividend Income Tracker</h3>
        {positions.map((pos, i) => (
          <div key={i} className="grid grid-cols-3 gap-2 mb-2">
            <input type="text" value={pos.ticker} onChange={(e) => updatePosition(i, 'ticker', e.target.value.toUpperCase())}
              placeholder="Ticker" className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
            <input type="number" value={pos.shares} onChange={(e) => updatePosition(i, 'shares', e.target.value)}
              placeholder="Shares" className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
            <input type="number" value={pos.cost_basis} onChange={(e) => updatePosition(i, 'cost_basis', e.target.value)}
              placeholder="Cost Basis" className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
          </div>
        ))}
        <div className="flex gap-2 mt-3">
          <button onClick={addPosition} className="bg-[var(--terminal-darker)] hover:bg-[var(--terminal-dark)] text-[var(--foreground)] border border-[var(--border)] px-3 py-2 rounded text-sm font-mono">+ ADD</button>
          <button onClick={runAnalysis} disabled={loading}
            className="bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-4 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono uppercase">
            {loading ? 'FETCHING...' : 'TRACK DIVIDENDS'}
          </button>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}
      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard label="Annual Income" value={`$${result.income_metrics?.annual_income?.toLocaleString(undefined, {maximumFractionDigits: 0})}`} color="emerald" />
            <KPICard label="Monthly Income" value={`$${result.income_metrics?.monthly_income?.toFixed(0)}`} />
            <KPICard label="Current Yield" value={`${(result.income_metrics?.current_yield * 100)?.toFixed(2)}%`} />
            <KPICard label="Yield on Cost" value={`${(result.income_metrics?.yield_on_cost * 100)?.toFixed(2)}%`} color="amber" />
          </div>

          {/* Holdings Table */}
          <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
            <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Dividends Ledger</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm font-mono">
                <thead>
                  <tr className="text-left text-[var(--terminal-dim)] border-b border-[var(--border)]/50 uppercase text-xs">
                    <th className="py-3 px-2">Ticker</th>
                    <th className="py-3 px-2 text-right">Shares</th>
                    <th className="py-3 px-2 text-right">Div Rate</th>
                    <th className="py-3 px-2 text-right">Annual</th>
                    <th className="py-3 px-2 text-right">Yield</th>
                    <th className="py-3 px-2 text-center">Trend</th>
                    <th className="py-3 px-2 text-center">Cut Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {result.holdings?.filter(h => !h.error).map((h, i) => (
                    <tr key={i} className="border-b border-[var(--border)]/10 hover:bg-[var(--terminal-darker)] transition-colors">
                      <td className="py-3 px-2 text-[var(--foreground)] font-bold">{h.ticker}</td>
                      <td className="py-3 px-2 text-right text-[var(--terminal-dim)]">{h.shares}</td>
                      <td className="py-3 px-2 text-right text-[var(--terminal-cyan)] font-bold">${h.dividend_rate?.toFixed(2)}</td>
                      <td className="py-3 px-2 text-right text-[var(--terminal-green)] font-bold">${h.annual_income?.toFixed(0)}</td>
                      <td className="py-3 px-2 text-right text-[var(--terminal-dim)]">{(h.dividend_yield * 100)?.toFixed(2)}%</td>
                      <td className="py-3 px-2 text-center">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                          h.dividend_trend === 'growing' ? 'bg-[var(--terminal-green)]/20 text-[var(--terminal-green)]' :
                          h.dividend_trend === 'declining' ? 'bg-[var(--terminal-red)]/20 text-[var(--terminal-red)]' :
                          'bg-[var(--terminal-darker)] text-[var(--terminal-dim)]'
                        }`}>{h.dividend_trend}</span>
                      </td>
                      <td className="py-3 px-2 text-center">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                          h.cut_risk === 'high' ? 'bg-[var(--terminal-red)]/20 text-[var(--terminal-red)]' :
                          h.cut_risk === 'medium' ? 'bg-[var(--terminal-orange)]/20 text-[var(--terminal-orange)]' :
                          'bg-[var(--terminal-green)]/20 text-[var(--terminal-green)]'
                        }`}>{h.cut_risk}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Income Forecast */}
          {result.forecast?.length > 0 && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">5-Year Income Forecast</h4>
              <Plot
                data={[{
                  type: 'bar',
                  x: result.forecast.map(f => `Year ${f.year}`),
                  y: result.forecast.map(f => f.annual_income),
                  marker: { color: 'var(--terminal-green)' }
                }]}
                layout={{
                  paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
                  font: { color: 'var(--terminal-dim)', family: 'monospace' },
                  xaxis: { gridcolor: 'var(--border)', zerolinecolor: 'var(--border)' },
                  yaxis: { title: 'Annual Income ($)', gridcolor: 'var(--border)', tickformat: ',.0f', zerolinecolor: 'var(--border)' },
                  margin: { t: 20, b: 40, l: 60, r: 20 }, height: 200
                }}
                config={{ displayModeBar: false }}
                style={{ width: '100%' }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// --- Tax Lot Optimizer Component ---
export const TaxLotOptimizer = () => {
  const [taxLots, setTaxLots] = useState([
    { purchase_date: '2022-01-15', quantity: 50, cost_basis: 150 },
    { purchase_date: '2023-03-20', quantity: 30, cost_basis: 180 },
    { purchase_date: '2024-06-10', quantity: 20, cost_basis: 200 }
  ]);
  const [sellQty, setSellQty] = useState(40);
  const [currentPrice, setCurrentPrice] = useState(195);
  const [preference, setPreference] = useState('minimize_tax');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runOptimization = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/portfolio/tax-lots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tax_lots: taxLots,
          sell_quantity: sellQty,
          current_price: currentPrice,
          preference
        })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }, [taxLots, sellQty, currentPrice, preference]);

  const updateLot = (index, field, value) => {
    const updated = [...taxLots];
    updated[index][field] = field === 'quantity' || field === 'cost_basis' ? Number(value) : value;
    setTaxLots(updated);
  };

  return (
    <div className="space-y-4">
      <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
        <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">Tax Lot Optimizer</h3>
        <div className="space-y-2 mb-4">
          {taxLots.map((lot, i) => (
            <div key={i} className="grid grid-cols-3 gap-2">
              <input type="date" value={lot.purchase_date} onChange={(e) => updateLot(i, 'purchase_date', e.target.value)}
                className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
              <input type="number" value={lot.quantity} onChange={(e) => updateLot(i, 'quantity', e.target.value)}
                placeholder="Qty" className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
              <input type="number" value={lot.cost_basis} onChange={(e) => updateLot(i, 'cost_basis', e.target.value)}
                placeholder="Cost" className="bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Sell Quantity</label>
            <input type="number" value={sellQty} onChange={(e) => setSellQty(Number(e.target.value))}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
          </div>
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Current Price</label>
            <input type="number" value={currentPrice} onChange={(e) => setCurrentPrice(Number(e.target.value))}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none" />
          </div>
          <div>
            <label className="text-xs text-[var(--terminal-dim)]">Strategy</label>
            <select value={preference} onChange={(e) => setPreference(e.target.value)}
              className="w-full bg-[var(--terminal-darker)] border border-[var(--border)] rounded px-3 py-2 text-[var(--foreground)] text-sm focus:border-[var(--terminal-yellow)] outline-none">
              <option value="minimize_tax">Minimize Tax</option>
              <option value="harvest_losses">Harvest Losses</option>
              <option value="fifo">FIFO</option>
              <option value="lifo">LIFO</option>
              <option value="hifo">HIFO</option>
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={runOptimization} disabled={loading}
              className="w-full bg-[var(--terminal-cyan)] hover:opacity-90 text-[var(--terminal-black)] px-4 py-2 rounded text-sm font-bold disabled:opacity-50 transition-all font-mono uppercase">
              {loading ? 'CALCULATING...' : 'OPTIMIZE'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="bg-[var(--terminal-red)]/10 border border-[var(--terminal-red)]/30 rounded p-3 text-[var(--terminal-red)] text-sm font-mono">{error}</div>}
      {loading && <LoadingSpinner />}

      {result && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPICard label="Total Proceeds" value={`$${result.tax_impact?.total_proceeds?.toLocaleString(undefined, {maximumFractionDigits: 0})}`} />
            <KPICard label="Capital Gain" value={`$${result.tax_impact?.total_gain?.toFixed(0)}`}
              color={result.tax_impact?.total_gain > 0 ? 'amber' : 'emerald'} />
            <KPICard label="Est. Tax" value={`$${result.tax_impact?.total_tax?.toFixed(0)}`} color="red" />
            <KPICard label="After-Tax" value={`$${result.tax_impact?.after_tax_proceeds?.toFixed(0)}`} color="emerald" />
          </div>

          {/* Recommended Lots */}
          <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
            <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3">Recommended Lot Selection ({preference})</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm font-mono">
                <thead>
                  <tr className="text-left text-[var(--terminal-dim)] border-b border-[var(--border)]/50 uppercase text-xs">
                    <th className="py-2 px-2">Purchase Date</th>
                    <th className="py-2 px-2">Holding</th>
                    <th className="py-2 px-2 text-right">Cost Basis</th>
                    <th className="py-2 px-2 text-right">Sell Qty</th>
                    <th className="py-2 px-2 text-right">Gain/Loss</th>
                    <th className="py-2 px-2 text-right">Est. Tax</th>
                  </tr>
                </thead>
                <tbody>
                  {result.recommended_lots?.map((lot, i) => (
                    <tr key={i} className="border-b border-[var(--border)]/10 hover:bg-[var(--terminal-darker)] transition-colors">
                      <td className="py-2 px-2 text-[var(--foreground)] font-bold">{lot.purchase_date}</td>
                      <td className="py-2 px-2">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                          lot.is_long_term ? 'bg-[var(--terminal-green)]/20 text-[var(--terminal-green)]' : 'bg-[var(--terminal-orange)]/20 text-[var(--terminal-orange)]'
                        }`}>{lot.holding_period}</span>
                      </td>
                      <td className="py-2 px-2 text-right text-[var(--terminal-dim)]">${lot.cost_basis?.toFixed(2)}</td>
                      <td className="py-2 px-2 text-right text-[var(--terminal-cyan)] font-bold">{lot.sell_quantity}</td>
                      <td className={`py-2 px-2 text-right font-bold ${lot.lot_gain >= 0 ? 'text-[var(--terminal-orange)]' : 'text-[var(--terminal-green)]'}`}>
                        {lot.lot_gain >= 0 ? '+' : ''}${lot.lot_gain?.toFixed(0)}
                      </td>
                      <td className="py-2 px-2 text-right text-[var(--terminal-red)] font-bold">${lot.lot_tax?.toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Strategy Comparison */}
          {result.comparison && (
            <div className="bg-[var(--terminal-dark)] border border-[var(--border)] rounded-lg p-4">
              <h4 className="text-sm font-medium text-[var(--terminal-dim)] mb-3 uppercase tracking-wider">Strategy Comparison</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(result.comparison).map(([strategy, data]: [string, any]) => (
                  <div key={strategy} className={`p-3 rounded border transition-all ${data.selected ? 'bg-[var(--terminal-cyan)]/10 border-[var(--terminal-cyan)] shadow-[0_0_10px_rgba(6,182,212,0.1)]' : 'bg-[var(--terminal-darker)] border-[var(--border)]/30'}`}>
                    <div className="text-[10px] text-[var(--terminal-dim)] uppercase font-mono font-bold">{strategy.replace('_', ' ')}</div>
                    <div className="text-[var(--foreground)] font-bold font-mono mt-1">Tax: ${data.total_tax?.toFixed(0)}</div>
                    <div className="text-xs text-[var(--terminal-green)] font-mono font-bold mt-0.5">After: ${data.after_tax_proceeds?.toFixed(0)}</div>
                    {data.selected && <div className="text-[10px] text-[var(--terminal-cyan)] mt-2 font-mono font-bold tracking-widest text-center border-t border-[var(--terminal-cyan)]/20 pt-1">SELECTED</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const AnalysisSectionExports = { HoldingsOverlap, DividendTracker, TaxLotOptimizer };
export default AnalysisSectionExports;
