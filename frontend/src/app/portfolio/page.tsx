'use client';

import React, { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import type { PlotParams } from 'react-plotly.js';

// Dynamic import for Plotly to avoid SSR issues
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false }) as React.ComponentType<PlotParams>;

// Import new portfolio feature components
import { MarkowitzOptimizer, RiskParityAllocator, FactorTiltOptimizer } from '@/components/portfolio/OptimizeSection';
import { RatiosDashboard, DrawdownAnalysis, BenchmarkComparison } from '@/components/portfolio/PerformanceSection';
import { MonteCarloSimulation, VaRCalculator } from '@/components/portfolio/RiskSection';
import { HoldingsOverlap, DividendTracker, TaxLotOptimizer } from '@/components/portfolio/AnalysisSection';


const API_BASE = 'http://127.0.0.1:8000/api';

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

async function fetchAPI(endpoint: string, options: RequestInit = {}) {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const json = await res.json();
    return json.data || json;
  } catch (e) {
    console.error(`API Error ${endpoint}:`, e);
    return null;
  }
}

// =============================================================================
// SUB-TAB CONFIGURATION - Maps to 29 Features
// =============================================================================

const subTabs = [
  { id: 'overview', label: 'OVERVIEW' },     // F1-4: Core portfolio overview
  { id: 'optimize', label: 'OPTIMIZE' },     // NEW: Markowitz, Risk Parity, Black-Litterman, Factor Tilt
  { id: 'performance', label: 'PERFORMANCE' }, // NEW: Ratios, Drawdowns, Benchmark
  { id: 'simulation', label: 'SIMULATION' }, // NEW: Monte Carlo, VaR/CVaR
  { id: 'analysis', label: 'ANALYSIS' },     // NEW: Overlap, Dividends, Tax Lots
  { id: 'trades', label: 'TRADES' },         // NEW: Trade Log & Snapshots
  // REMOVED: risk, regimes, strategy, hedge, audit tabs per user request (code retained)
];

// =============================================================================
// LOADING STATE
// =============================================================================

function LoadingState() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-pulse text-terminal-dim font-mono">INITIALIZING PORTFOLIO ENGINE...</div>
    </div>
  );
}

// =============================================================================
// KPI CARD
// =============================================================================

function KPICard({ label, value, color = 'default', subtitle }: { 
  label: string; 
  value: string | number; 
  color?: 'emerald' | 'red' | 'amber' | 'default';
  subtitle?: string;
}) {
  const colorClasses = {
    emerald: 'text-terminal-green',
    red: 'text-terminal-red',
    amber: 'text-terminal-yellow',
    default: 'text-terminal-text'
  };

  return (
    <div className="bg-terminal-dark/50 border border-terminal-gray rounded px-4 py-3 shadow-panel">
      <p className="text-[10px] text-terminal-dim uppercase font-black tracking-widest">{label}</p>
      <p className={`text-xl font-bold mt-1 ${colorClasses[color]}`}>{value}</p>
      {subtitle && <p className="text-[10px] text-terminal-dim mt-1 font-mono">{subtitle}</p>}
    </div>
  );
}

// =============================================================================
// OVERVIEW TAB - Institutional Portfolio Intelligence Dashboard (READ-ONLY)
// 7 Sections per spec: Growth, Summary, Sector/Contribution, Holdings, 
// Calendar Heatmap, Risk Snapshot, What Changed
// =============================================================================

// Currency conversion rate (INR to USD) - approximate
const INR_TO_USD = 0.012;

// Sector color mapping
const SECTOR_COLORS: Record<string, string> = {
  'Technology': '#3B82F6',
  'Healthcare': '#EF4444',
  'Finance': '#10B981',
  'Energy': '#F59E0B',
  'Consumer': '#8B5CF6',
  'Industrial': '#6B7280',
  'Materials': '#92400E',
  'Utilities': '#06B6D4',
  'Other': '#64748B'
};

// Ticker to sector mapping
const TICKER_SECTORS: Record<string, string> = {
  'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 'NVDA': 'Technology',
  'META': 'Technology', 'AMZN': 'Consumer', 'TSLA': 'Consumer',
  'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'PFE': 'Healthcare',
  'JPM': 'Finance', 'BAC': 'Finance', 'GS': 'Finance',
  'XOM': 'Energy', 'CVX': 'Energy',
  'RELIANCE.NS': 'Energy', 'TCS.NS': 'Technology', 'HDFCBANK.NS': 'Finance',
  'INFY.NS': 'Technology', 'BHARTIARTL.NS': 'Technology'
};

// Check if ticker is Indian stock
const isIndianStock = (ticker: string) => ticker.endsWith('.NS') || ticker.endsWith('.BO');

// Convert price to USD if needed
const toUSD = (price: number, ticker: string) => isIndianStock(ticker) ? price * INR_TO_USD : price;

function OverviewTab() {
  const [summary, setSummary] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [timePeriod, setTimePeriod] = useState<'1W' | '1M' | '3M' | 'YTD' | '1Y' | 'ALL'>('1M');
  const [sortColumn, setSortColumn] = useState<string>('contribution');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const [showBenchmark, setShowBenchmark] = useState(false);
  const [hoveredSector, setHoveredSector] = useState<string | null>(null);
  const [contributionView, setContributionView] = useState<'assets' | 'sectors'>('assets');
  const [whatChangedPeriod, setWhatChangedPeriod] = useState<'yesterday' | 'week' | 'month'>('week');

  useEffect(() => {
    Promise.all([
      fetchAPI('/portfolio/summary'),
      fetchAPI('/portfolio/holdings')
    ]).then(([sum, hold]) => {
      setSummary(sum);
      const rawPositions = Array.isArray(hold) ? hold : (hold?.positions || []);
      const processed = rawPositions.map((p: any) => {
        const ticker = p.ticker || p.symbol || '';
        const quantity = p.shares || p.quantity || 0;
        const avgCost = p.cost_basis ? p.cost_basis / (quantity || 1) : p.avg_cost || 0;
        const price = p.price || p.current_price || 0;
        
        // Convert to USD for Indian stocks
        const avgCostUSD = toUSD(avgCost, ticker);
        const priceUSD = toUSD(price, ticker);
        const value = quantity * priceUSD;
        const pnl = (priceUSD - avgCostUSD) * quantity;
        const pnlPct = avgCostUSD > 0 ? ((priceUSD - avgCostUSD) / avgCostUSD) * 100 : 0;
        
        return {
          symbol: ticker,
          quantity,
          avgCost: avgCostUSD,
          price: priceUSD,
          value,
          pnl,
          pnlPct,
          sector: TICKER_SECTORS[ticker] || 'Other',
          isIndian: isIndianStock(ticker)
        };
      });
      setPositions(processed);
      setLoading(false);
    });
  }, []);

  if (loading) return <LoadingState />;

  // Calculate derived metrics
  const totalValue = positions.reduce((sum, p) => sum + p.value, 0);
  const totalPnL = positions.reduce((sum, p) => sum + p.pnl, 0);
  const totalCost = positions.reduce((sum, p) => sum + (p.avgCost * p.quantity), 0);
  const totalReturnPct = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0;
  const cash = summary?.cash || 0;
  const totalEquity = totalValue + cash;
  
  // Calculate contribution for each position
  const positionsWithContribution = positions.map(p => ({
    ...p,
    contribution: totalPnL !== 0 ? (p.pnl / Math.abs(totalPnL)) * 100 : 0,
    weight: totalEquity > 0 ? (p.value / totalEquity) * 100 : 0
  }));

  // Sector aggregation
  const sectorData = positionsWithContribution.reduce((acc, p) => {
    if (!acc[p.sector]) {
      acc[p.sector] = { value: 0, pnl: 0, contribution: 0 };
    }
    acc[p.sector].value += p.value;
    acc[p.sector].pnl += p.pnl;
    acc[p.sector].contribution += p.contribution;
    return acc;
  }, {} as Record<string, { value: number; pnl: number; contribution: number }>);

  const sectorArray = Object.entries(sectorData).map(([name, data]: [string, { value: number; pnl: number; contribution: number }]) => ({
    name,
    value: data.value,
    pnl: data.pnl,
    contribution: data.contribution,
    weight: totalEquity > 0 ? (data.value / totalEquity) * 100 : 0,
    color: SECTOR_COLORS[name] || SECTOR_COLORS['Other']
  })).sort((a, b) => b.value - a.value);

  // Sort positions
  const sortedPositions = [...positionsWithContribution]
    .filter(p => !selectedSector || p.sector === selectedSector)
    .filter(p => !searchTerm || p.symbol.toLowerCase().includes(searchTerm.toLowerCase()))
    .sort((a, b) => {
      const aVal = a[sortColumn as keyof typeof a] || 0;
      const bVal = b[sortColumn as keyof typeof b] || 0;
      return sortDirection === 'desc' ? (bVal as number) - (aVal as number) : (aVal as number) - (bVal as number);
    });

  // Top contributors
  const topContributors = [...positionsWithContribution]
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, 8);

  // Risk metrics (simplified)
  const maxWeight = Math.max(...positionsWithContribution.map(p => p.weight));
  const top3Weight = positionsWithContribution
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 3)
    .reduce((sum, p) => sum + p.weight, 0);
  const topSector = sectorArray[0];

  // Max drawdown (simulated - would come from API with historical data)
  const maxDrawdown = -8.4; // Example value

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'desc' ? 'asc' : 'desc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  const formatCurrency = (val: number) => 
    val >= 0 ? `$${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : `-$${Math.abs(val).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">
      
      {/* ============================================================= */}
      {/* SECTION 1: PORTFOLIO GROWTH CHART (HERO) */}
      {/* ============================================================= */}
      <div className="bg-terminal-dark/40 border border-terminal-gray rounded-xl p-6 shadow-panel">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-xl font-black text-terminal-yellow uppercase tracking-tight">Portfolio Performance</h2>
            <p className="text-[10px] text-terminal-dim font-black uppercase tracking-widest">Total equity over time</p>
          </div>
          <div className="flex items-center gap-4">
            {/* Benchmark Toggle */}
            <label className="flex items-center gap-2 text-xs text-terminal-dim cursor-pointer font-mono">
              <input 
                type="checkbox" 
                checked={showBenchmark} 
                onChange={() => setShowBenchmark(!showBenchmark)}
                className="rounded border-terminal-gray bg-terminal-black accent-terminal-yellow"
              />
              Show S&P 500
            </label>
            {/* Time Period Selector */}
            <div className="flex gap-1 bg-terminal-black/50 border border-terminal-gray rounded p-1">
              {(['1W', '1M', '3M', 'YTD', '1Y', 'ALL'] as const).map(period => (
                <button
                  key={period}
                  onClick={() => setTimePeriod(period)}
                  className={`px-3 py-1.5 text-[10px] font-black rounded transition-all uppercase tracking-tighter ${
                    timePeriod === period 
                      ? 'bg-terminal-yellow text-terminal-black' 
                      : 'text-terminal-dim hover:text-terminal-text hover:bg-terminal-gray/30'
                  }`}
                >
                  {period}
                </button>
              ))}
            </div>
          </div>
        </div>
        
        {/* Chart Area */}
        <div className="h-[320px] bg-terminal-black/30 rounded-lg flex items-center justify-center border border-terminal-gray/30">
          <div className="text-center">
            <div className="text-5xl font-black text-terminal-yellow mb-2 tracking-tighter">
              {formatCurrency(totalEquity)}
            </div>
            <div className={`text-lg font-black ${totalPnL >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
              {totalPnL >= 0 ? '▲' : '▼'} {formatCurrency(totalPnL)} ({totalReturnPct.toFixed(2)}%)
            </div>
            <p className="text-[10px] text-terminal-dim mt-2 font-mono uppercase">Historical chart requires equity_history data</p>
          </div>
        </div>
      </div>

      {/* ============================================================= */}
      {/* SECTION 2: SUMMARY STATE CARDS (5 Cards) */}
      {/* ============================================================= */}
      <div className="grid grid-cols-5 gap-4">
        {/* Card 1: Total Value */}
        <div className="bg-terminal-dark/40 border border-terminal-gray rounded-xl p-5 shadow-panel">
          <p className="text-[10px] text-terminal-dim uppercase font-black tracking-widest mb-1">Total Value</p>
          <p className="text-2xl font-black text-terminal-text tracking-tight">{formatCurrency(totalEquity)}</p>
          <p className="text-[10px] text-terminal-dim mt-1 font-mono uppercase">Current Liquidity</p>
        </div>
        
        {/* Card 2: Total Gain/Loss */}
        <div className="bg-terminal-dark/40 border border-terminal-gray rounded-xl p-5 shadow-panel">
          <p className="text-[10px] text-terminal-dim uppercase font-black tracking-widest mb-1">Total Gain/Loss</p>
          <p className={`text-2xl font-black tracking-tight ${totalPnL >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
            {totalPnL >= 0 ? '▲' : '▼'} {formatCurrency(totalPnL)}
          </p>
          <p className="text-[10px] text-terminal-dim mt-1 font-mono uppercase">Since Genesis</p>
        </div>
        
        {/* Card 3: Total Return % */}
        <div className="bg-terminal-dark/40 border border-terminal-gray rounded-xl p-5 shadow-panel">
          <p className="text-[10px] text-terminal-dim uppercase font-black tracking-widest mb-1">Total Return</p>
          <p className={`text-2xl font-black tracking-tight ${totalReturnPct >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
            {totalReturnPct >= 0 ? '▲' : '▼'} {totalReturnPct.toFixed(2)}%
          </p>
          <p className="text-[10px] text-terminal-dim mt-1 font-mono uppercase">Portfolio Alpha</p>
        </div>
        
        {/* Card 4: Today's Change */}
        <div className="bg-terminal-dark/40 border border-terminal-gray rounded-xl p-5 shadow-panel">
          <p className="text-[10px] text-terminal-dim uppercase font-black tracking-widest mb-1">Today&apos;s Delta</p>
          <p className={`text-2xl font-black tracking-tight ${totalPnL >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
            ▲ $0 <span className="text-sm">(0.00%)</span>
          </p>
          <p className="text-[10px] text-terminal-dim mt-1 font-mono uppercase">Session Performance</p>
        </div>
        
        {/* Card 5: Max Drawdown */}
        <div className="bg-terminal-dark/40 border border-terminal-gray rounded-xl p-5 shadow-panel">
          <p className="text-[10px] text-terminal-dim uppercase font-black tracking-widest mb-1">Max Drawdown</p>
          <p className="text-2xl font-black text-terminal-orange tracking-tight">▼ {maxDrawdown.toFixed(1)}%</p>
          <p className="text-[10px] text-terminal-dim mt-1 font-mono uppercase">Risk Constraint</p>
        </div>
      </div>

      {/* ============================================================= */}
      {/* SECTION 3: STRUCTURE + DRIVERS (Two Column) */}
      {/* ============================================================= */}
      <div className="grid grid-cols-2 gap-6">
        {/* LEFT: Sector Allocation */}
        <div className="bg-terminal-dark/40 border border-terminal-gray rounded-xl p-5 shadow-panel">
          <h3 className="text-[10px] font-black text-terminal-dim uppercase tracking-widest mb-4">Sector Allocation</h3>
          <div className="flex items-center gap-6">
            {/* Donut Chart Placeholder */}
            <div className="relative w-48 h-48">
              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                {sectorArray.reduce((acc, sector, i) => {
                  const startAngle = acc.angle;
                  const sliceAngle = (sector.weight / 100) * 360;
                  const endAngle = startAngle + sliceAngle;
                  const largeArc = sliceAngle > 180 ? 1 : 0;
                  
                  const x1 = 50 + 35 * Math.cos((startAngle * Math.PI) / 180);
                  const y1 = 50 + 35 * Math.sin((startAngle * Math.PI) / 180);
                  const x2 = 50 + 35 * Math.cos((endAngle * Math.PI) / 180);
                  const y2 = 50 + 35 * Math.sin((endAngle * Math.PI) / 180);
                  
                  acc.paths.push(
                    <path
                      key={sector.name}
                      d={`M 50 50 L ${x1} ${y1} A 35 35 0 ${largeArc} 1 ${x2} ${y2} Z`}
                    fill={sector.color}
                    stroke="var(--terminal-black)"
                    strokeWidth="1"
                    className={`cursor-pointer transition-all ${
                      hoveredSector === sector.name ? 'opacity-100' : 'opacity-70'
                    } ${selectedSector === sector.name ? 'opacity-100' : ''}`}
                    onMouseEnter={() => setHoveredSector(sector.name)}
                    onMouseLeave={() => setHoveredSector(null)}
                    onClick={() => setSelectedSector(selectedSector === sector.name ? null : sector.name)}
                  />
                );
                acc.angle = endAngle;
                return acc;
              }, { paths: [] as React.ReactNode[], angle: 0 }).paths}
              {/* Center Circle */}
              <circle cx="50" cy="50" r="22" fill="var(--terminal-black)" />
            </svg>
            {/* Center Text */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <p className="text-[8px] text-terminal-dim font-black uppercase tracking-widest">{hoveredSector || 'Total'}</p>
              <p className="text-lg font-black text-terminal-text tracking-tight">
                {hoveredSector 
                  ? `${sectorArray.find(s => s.name === hoveredSector)?.weight.toFixed(1)}%`
                  : '100%'}
              </p>
            </div>
            </div>
            
            {/* Legend */}
            <div className="flex-1 space-y-2">
              {sectorArray.map(sector => (
                <div 
                  key={sector.name}
                  className={`flex items-center justify-between px-2 py-1 rounded cursor-pointer transition-all ${
                    selectedSector === sector.name ? 'bg-zinc-800' : 'hover:bg-zinc-800/50'
                  }`}
                  onClick={() => setSelectedSector(selectedSector === sector.name ? null : sector.name)}
                >
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: sector.color }} />
                    <span className="text-[10px] text-terminal-dim font-black uppercase">{sector.name}</span>
                  </div>
                  <span className="text-[10px] font-mono font-bold text-terminal-text">{sector.weight.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT: Contribution Breakdown */}
        <div className="bg-terminal-dark/40 border border-terminal-gray rounded-xl p-5 shadow-panel">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-[10px] font-black text-terminal-dim uppercase tracking-widest">Performance Contribution</h3>
            <div className="flex gap-1 bg-terminal-black/50 border border-terminal-gray rounded p-0.5">
              <button
                onClick={() => setContributionView('assets')}
                className={`px-2 py-1 text-[9px] font-black rounded transition-all uppercase ${
                  contributionView === 'assets' ? 'bg-terminal-gray text-terminal-text' : 'text-terminal-dim hover:text-terminal-text'
                }`}
              >
                Assets
              </button>
              <button
                onClick={() => setContributionView('sectors')}
                className={`px-2 py-1 text-[9px] font-black rounded transition-all uppercase ${
                  contributionView === 'sectors' ? 'bg-terminal-gray text-terminal-text' : 'text-terminal-dim hover:text-terminal-text'
                }`}
              >
                Sectors
              </button>
            </div>
          </div>
          <div className="space-y-2">
            {contributionView === 'assets' ? (
              topContributors.map(pos => (
                <div key={pos.symbol} className="flex items-center gap-3">
                  <span className="w-20 text-sm font-mono text-zinc-300 truncate">{pos.symbol}</span>
                  <div className="flex-1 h-6 bg-terminal-black/40 border border-terminal-gray/20 rounded relative overflow-hidden">
                    {pos.contribution >= 0 ? (
                      <div 
                        className="absolute left-1/2 h-full bg-terminal-green/40 rounded-r"
                        style={{ width: `${Math.min(Math.abs(pos.contribution), 50)}%` }}
                      />
                    ) : (
                      <div 
                        className="absolute right-1/2 h-full bg-terminal-red/40 rounded-l"
                        style={{ width: `${Math.min(Math.abs(pos.contribution), 50)}%` }}
                      />
                    )}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-[10px] text-terminal-text font-mono font-bold">
                        {pos.contribution >= 0 ? '+' : ''}{pos.contribution.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <span className={`w-20 text-right text-xs font-mono font-bold ${pos.pnl >= 0 ? 'text-terminal-green' : 'text-terminal-red'}`}>
                    {formatCurrency(pos.pnl)}
                  </span>
                </div>
              ))
            ) : (
              sectorArray.map(sector => (
                <div key={sector.name} className="flex items-center gap-3">
                  <span className="w-20 text-sm text-zinc-300 truncate">{sector.name}</span>
                  <div className="flex-1 h-6 bg-zinc-800 rounded relative overflow-hidden">
                    {sector.contribution >= 0 ? (
                      <div 
                        className="absolute left-1/2 h-full rounded-r"
                        style={{ width: `${Math.min(Math.abs(sector.contribution), 50)}%`, backgroundColor: sector.color }}
                      />
                    ) : (
                      <div 
                        className="absolute right-1/2 h-full rounded-l"
                        style={{ width: `${Math.min(Math.abs(sector.contribution), 50)}%`, backgroundColor: '#ef4444' }}
                      />
                    )}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xs text-zinc-300 font-mono">
                        {sector.contribution >= 0 ? '+' : ''}{sector.contribution.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <span className={`w-20 text-right text-sm font-mono ${sector.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {formatCurrency(sector.pnl)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ============================================================= */}
      {/* SECTION 4: HOLDINGS TABLE */}
      {/* ============================================================= */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl">
        <div className="px-5 py-4 border-b border-zinc-800 flex justify-between items-center">
          <div>
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">Holdings Details</h3>
            <p className="text-xs text-zinc-500 mt-0.5">
              {sortedPositions.length} position{sortedPositions.length !== 1 ? 's' : ''} 
              {selectedSector && ` in ${selectedSector}`}
              {searchTerm && ` matching "${searchTerm}"`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {selectedSector && (
              <button 
                onClick={() => setSelectedSector(null)}
                className="text-xs text-cyan-400 hover:text-cyan-300"
              >
                Clear filter
              </button>
            )}
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search symbol..."
              className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-600 w-40"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-800/50 sticky top-0">
              <tr className="text-left text-zinc-500 uppercase text-xs">
                <th className="px-4 py-3 cursor-pointer hover:text-zinc-300" onClick={() => handleSort('symbol')}>
                  Symbol {sortColumn === 'symbol' && (sortDirection === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 text-right cursor-pointer hover:text-zinc-300" onClick={() => handleSort('quantity')}>
                  Qty {sortColumn === 'quantity' && (sortDirection === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 text-right cursor-pointer hover:text-zinc-300" onClick={() => handleSort('avgCost')}>
                  Avg Cost {sortColumn === 'avgCost' && (sortDirection === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 text-right cursor-pointer hover:text-zinc-300" onClick={() => handleSort('price')}>
                  Price {sortColumn === 'price' && (sortDirection === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 text-right cursor-pointer hover:text-zinc-300" onClick={() => handleSort('value')}>
                  Value {sortColumn === 'value' && (sortDirection === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 text-right cursor-pointer hover:text-zinc-300" onClick={() => handleSort('pnl')}>
                  P&L $ {sortColumn === 'pnl' && (sortDirection === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 text-right cursor-pointer hover:text-zinc-300" onClick={() => handleSort('pnlPct')}>
                  P&L % {sortColumn === 'pnlPct' && (sortDirection === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 text-right cursor-pointer hover:text-zinc-300" onClick={() => handleSort('weight')}>
                  Weight {sortColumn === 'weight' && (sortDirection === 'desc' ? '↓' : '↑')}
                </th>
                <th className="px-4 py-3 text-right cursor-pointer hover:text-zinc-300" onClick={() => handleSort('contribution')}>
                  Contrib {sortColumn === 'contribution' && (sortDirection === 'desc' ? '↓' : '↑')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedPositions.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-zinc-500">No positions</td></tr>
              ) : sortedPositions.map((pos, i) => (
                <tr key={pos.symbol} className={`border-t border-zinc-800/50 ${i % 2 === 0 ? 'bg-zinc-900/30' : ''} hover:bg-zinc-800/30`}>
                  <td className="px-4 py-3">
                    <span className="font-mono font-semibold text-cyan-400">{pos.symbol}</span>
                    {pos.isIndian && <span className="ml-2 text-xs text-zinc-500">₹→$</span>}
                  </td>
                  <td className="px-4 py-3 text-right text-zinc-300">{pos.quantity.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-zinc-500">${pos.avgCost.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right text-zinc-200">${pos.price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right font-semibold text-zinc-100">${pos.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                  <td className={`px-4 py-3 text-right font-semibold ${pos.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {pos.pnl >= 0 ? '+' : ''}{formatCurrency(pos.pnl)}
                  </td>
                  <td className={`px-4 py-3 text-right ${pos.pnlPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {pos.pnlPct >= 0 ? '+' : ''}{pos.pnlPct.toFixed(2)}%
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 h-2 bg-zinc-800 rounded-full overflow-hidden">
                        <div className="h-full bg-zinc-500" style={{ width: `${Math.min(pos.weight, 100)}%` }} />
                      </div>
                      <span className="text-zinc-400 w-12 text-right">{pos.weight.toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className={`px-4 py-3 text-right font-semibold ${pos.contribution >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {pos.contribution >= 0 ? '+' : ''}{pos.contribution.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ============================================================= */}
      {/* SECTION 5: PERFORMANCE BEHAVIOR (CALENDAR HEATMAP) */}
      {/* ============================================================= */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">Performance Behavior</h3>
            <p className="text-xs text-zinc-500 mt-0.5">Daily return patterns (last 12 months)</p>
          </div>
          <div className="flex items-center gap-4">
            {/* Legend */}
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span>Loss</span>
              <div className="flex gap-0.5">
                <div className="w-3 h-3 rounded-sm bg-red-600" />
                <div className="w-3 h-3 rounded-sm bg-red-400" />
                <div className="w-3 h-3 rounded-sm bg-zinc-700" />
                <div className="w-3 h-3 rounded-sm bg-emerald-400" />
                <div className="w-3 h-3 rounded-sm bg-emerald-600" />
              </div>
              <span>Gain</span>
            </div>
          </div>
        </div>
        {/* Calendar Heatmap Grid (52 weeks x 7 days) */}
        <div className="overflow-x-auto">
          <div className="flex gap-0.5 min-w-[750px]">
            {Array.from({ length: 52 }, (_, weekIdx) => (
              <div key={weekIdx} className="flex flex-col gap-0.5">
                {Array.from({ length: 7 }, (_, dayIdx) => {
                  // Generate a random-ish return for visualization
                  const seed = (weekIdx * 7 + dayIdx) % 11;
                  const returnVal = [-2.5, -1.5, -0.8, -0.3, 0, 0.2, 0.5, 0.8, 1.2, 1.8, 2.5][seed];
                  let bgColor = 'bg-zinc-700';
                  if (returnVal < -1.5) bgColor = 'bg-red-600';
                  else if (returnVal < -0.5) bgColor = 'bg-red-400';
                  else if (returnVal > 1.5) bgColor = 'bg-emerald-600';
                  else if (returnVal > 0.5) bgColor = 'bg-emerald-400';
                  return (
                    <div 
                      key={dayIdx} 
                      className={`w-3 h-3 rounded-sm ${bgColor} hover:ring-1 hover:ring-zinc-400`}
                      title={`Week ${weekIdx + 1}, Day ${dayIdx + 1}: ${returnVal >= 0 ? '+' : ''}${returnVal.toFixed(1)}%`}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
        <div className="flex justify-between mt-3 text-xs text-zinc-500">
          <span>Jan</span><span>Feb</span><span>Mar</span><span>Apr</span><span>May</span><span>Jun</span>
          <span>Jul</span><span>Aug</span><span>Sep</span><span>Oct</span><span>Nov</span><span>Dec</span>
        </div>
      </div>

      {/* ============================================================= */}
      {/* SECTION 6: RISK SNAPSHOT */}
      {/* ============================================================= */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
          <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Portfolio Volatility</p>
          <p className="text-2xl font-bold text-amber-400">~15.2%</p>
          <p className="text-xs text-zinc-500 mt-1">Moderate • Annualized</p>
        </div>
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
          <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Current Drawdown</p>
          <p className="text-2xl font-bold text-zinc-300">{maxDrawdown.toFixed(1)}%</p>
          <p className="text-xs text-zinc-500 mt-1">From peak value</p>
        </div>
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
          <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Top Risk Contributor</p>
          <p className="text-2xl font-bold" style={{ color: topSector?.color }}>{topSector?.name}</p>
          <p className="text-xs text-zinc-500 mt-1">{topSector?.weight.toFixed(1)}% concentration</p>
        </div>
      </div>

      {/* ============================================================= */}
      {/* SECTION 7: WHAT CHANGED */}
      {/* ============================================================= */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">What Changed</h3>
          <select 
            value={whatChangedPeriod}
            onChange={(e) => setWhatChangedPeriod(e.target.value as 'yesterday' | 'week' | 'month')}
            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-300"
          >
            <option value="yesterday">Since Yesterday</option>
            <option value="week">Since Last Week</option>
            <option value="month">Since Last Month</option>
          </select>
        </div>
        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <span className="text-cyan-400">📊</span>
            <p className="text-sm text-zinc-300">
              <span className="font-semibold text-zinc-100">{topSector?.name}</span> remains your largest sector at {topSector?.weight.toFixed(1)}%
            </p>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-emerald-400">↑</span>
            <p className="text-sm text-zinc-300">
              Top performer: <span className="font-semibold text-emerald-400">{positionsWithContribution[0]?.symbol}</span> contributing {positionsWithContribution[0]?.contribution.toFixed(1)}% of gains
            </p>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-amber-400">⚠</span>
            <p className="text-sm text-zinc-300">
              Concentration: Top position is <span className="font-semibold">{maxWeight.toFixed(1)}%</span> of portfolio
            </p>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-zinc-400">💵</span>
            <p className="text-sm text-zinc-300">
              Cash reserve: <span className="font-semibold">{formatCurrency(cash)}</span> ({((cash / totalEquity) * 100).toFixed(1)}% uninvested)
            </p>
          </div>
        </div>
      </div>

    </div>
  );
}

// =============================================================================
// RISK TAB - VaR-ONLY Dashboard with 9 VaR Models
// =============================================================================

function RiskTab() {
  const [varData, setVarData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [portfolioValue, setPortfolioValue] = useState(1000000);
  const [confidence, setConfidence] = useState(0.99);

  const fetchVarData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/portfolio-risk/dashboard?portfolio_value=${portfolioValue}&confidence=${confidence}`);
      if (res.ok) {
        const data = await res.json();
        setVarData(data);
      }
    } catch (err) {
      console.error('VaR fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [portfolioValue, confidence]);

  useEffect(() => { fetchVarData(); }, [fetchVarData]);

  if (loading && !varData) return <LoadingState />;

  const riskScore = varData?.risk_score?.overall_score || 0;
  const scoreColor = riskScore >= 70 ? 'text-emerald-400' : riskScore >= 50 ? 'text-amber-400' : 'text-red-400';
  const scoreBg = riskScore >= 70 ? 'bg-emerald-500/10 border-emerald-500/30' : riskScore >= 50 ? 'bg-amber-500/10 border-amber-500/30' : 'bg-red-500/10 border-red-500/30';
  const fmt = (v: number) => v ? `$${v.toLocaleString(undefined, {maximumFractionDigits: 0})}` : '--';
  const pct = (v: number) => v ? `${(v * 100).toFixed(2)}%` : '--';

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-4 justify-end">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500">NAV:</span>
          <input 
            type="number" 
            value={portfolioValue} 
            onChange={(e) => setPortfolioValue(Number(e.target.value))}
            className="w-28 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm"
          />
        </div>
        <select 
          value={confidence} 
          onChange={(e) => setConfidence(Number(e.target.value))}
          className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm"
        >
          <option value={0.99}>99% CI</option>
          <option value={0.95}>95% CI</option>
        </select>
        <button onClick={fetchVarData} className="px-3 py-1 bg-blue-500 hover:bg-blue-600 rounded text-sm">
          Refresh
        </button>
      </div>

      {/* Master Risk Panel */}
      <div className={`p-6 rounded-xl border ${scoreBg}`}>
        <div className="grid grid-cols-5 gap-6">
          <div className="text-center">
            <div className={`text-5xl font-black ${scoreColor}`}>{riskScore.toFixed(0)}</div>
            <div className="text-sm text-zinc-400 mt-1">Risk Score</div>
            <div className={`text-xs font-bold ${scoreColor} mt-1`}>
              {riskScore >= 80 ? 'HEALTHY' : riskScore >= 60 ? 'MODERATE' : 'AT RISK'}
            </div>
          </div>
          <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-700">
            <div className="text-xs text-amber-400 mb-1">⭐ Cornish-Fisher VaR</div>
            <div className="text-2xl font-bold text-red-400">{fmt(varData?.cornish_fisher_var?.cf_var_dollar)}</div>
            <div className="text-xs text-zinc-500">{pct(varData?.cornish_fisher_var?.cf_var_percent)} of NAV</div>
          </div>
          <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-700">
            <div className="text-xs text-zinc-400 mb-1">Expected Tail Loss</div>
            <div className="text-2xl font-bold text-purple-400">{fmt(varData?.expected_tail_loss?.etl_dollar)}</div>
            <div className="text-xs text-zinc-500">ETL/VaR: {varData?.expected_tail_loss?.etl_var_ratio?.toFixed(2) || '--'}x</div>
          </div>
          <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-700">
            <div className="text-xs text-zinc-400 mb-1">Stressed VaR</div>
            <div className="text-2xl font-bold text-amber-400">{fmt(varData?.stressed_var?.stressed_var_dollar)}</div>
            <div className="text-xs text-zinc-500">{varData?.stressed_var?.stress_multiple?.toFixed(1) || '--'}x Normal</div>
          </div>
          <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-700">
            <div className="text-xs text-zinc-400 mb-1">Portfolio Volatility</div>
            <div className="text-2xl font-bold text-blue-400">{pct(varData?.parametric_var?.portfolio_volatility)}</div>
            <div className="text-xs text-zinc-500">Annualized</div>
          </div>
        </div>
      </div>

      {/* VaR Models Grid */}
      <div className="grid grid-cols-3 gap-4">
        {/* Parametric VaR */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-zinc-300 mb-3">📊 Parametric VaR</h4>
          <div className="text-2xl font-bold text-blue-400">{fmt(varData?.parametric_var?.var_dollar)}</div>
          <div className="text-xs text-zinc-500 mt-1">Variance-Covariance Method</div>
          <div className="mt-3 text-xs text-zinc-400">
            Assumes normal distribution. May underestimate tail risk.
          </div>
        </div>

        {/* Cornish-Fisher VaR (Primary) */}
        <div className="bg-zinc-900/80 border border-amber-500/30 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-amber-400 mb-3">⭐ Cornish-Fisher VaR <span className="text-[10px] bg-amber-500/20 px-1 rounded">PRIMARY</span></h4>
          <div className="text-2xl font-bold text-amber-400">{fmt(varData?.cornish_fisher_var?.cf_var_dollar)}</div>
          <div className="text-xs text-zinc-500 mt-1">Tail Inflation: {varData?.cornish_fisher_var?.tail_inflation?.toFixed(2)}x</div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            <div className="bg-zinc-800 rounded p-2 text-center">
              <div className="text-zinc-500">Skewness</div>
              <div>{varData?.cornish_fisher_var?.skewness?.toFixed(3) || '--'}</div>
            </div>
            <div className="bg-zinc-800 rounded p-2 text-center">
              <div className="text-zinc-500">Kurtosis</div>
              <div>{varData?.cornish_fisher_var?.kurtosis?.toFixed(3) || '--'}</div>
            </div>
          </div>
        </div>

        {/* Expected Tail Loss */}
        <div className="bg-zinc-900/80 border border-purple-500/30 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-purple-400 mb-3">📉 Expected Tail Loss (CVaR)</h4>
          <div className="text-2xl font-bold text-purple-400">{fmt(varData?.expected_tail_loss?.etl_dollar)}</div>
          <div className="text-xs text-zinc-500 mt-1">Average loss beyond VaR</div>
          <div className="mt-3 text-xs text-zinc-400">
            ETL/VaR Ratio: {varData?.expected_tail_loss?.etl_var_ratio?.toFixed(2) || '--'}x
          </div>
        </div>

        {/* Stressed VaR */}
        <div className="bg-zinc-900/80 border border-red-500/30 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-red-400 mb-3">⚡ Stressed VaR</h4>
          <div className="text-2xl font-bold text-red-400">{fmt(varData?.stressed_var?.stressed_var_dollar)}</div>
          <div className="text-xs text-zinc-500 mt-1">{varData?.stressed_var?.stress_multiple?.toFixed(1)}x Normal VaR</div>
          <div className="mt-3 text-xs text-zinc-400">
            Max Safe Leverage: {varData?.stressed_var?.max_safe_leverage?.toFixed(1)}x
          </div>
        </div>

        {/* Correlation Stress */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-zinc-300 mb-3">🔗 Correlation Stress</h4>
          <div className="text-2xl font-bold text-cyan-400">{varData?.correlation_stress?.var_increase_ratio?.toFixed(1) || '--'}x</div>
          <div className="text-xs text-zinc-500 mt-1">VaR Increase Under Stress</div>
          <div className="mt-3 flex justify-between text-xs">
            <span className="text-zinc-500">Diversification:</span>
            <span className="text-emerald-400">{pct(varData?.correlation_stress?.diversification_benefit)}</span>
          </div>
          {varData?.correlation_stress?.false_diversification_warning && (
            <div className="mt-2 text-xs text-red-400">⚠️ False diversification risk</div>
          )}
        </div>

        {/* Component VaR */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-zinc-300 mb-3">🎯 Component VaR</h4>
          <div className="text-2xl font-bold text-zinc-100">{fmt(varData?.component_var?.total_var)}</div>
          <div className="text-xs text-zinc-500 mt-1">{varData?.component_var?.count || 0} positions analyzed</div>
          {varData?.component_var?.risk_hogs?.length > 0 && (
            <div className="mt-3 text-xs">
              <span className="text-red-400">Risk Hogs:</span> {varData.component_var.risk_hogs.slice(0, 3).join(', ')}
            </div>
          )}
        </div>
      </div>

      {/* Risk Score Components */}
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-zinc-300 mb-4">📊 Risk Score Breakdown</h4>
        <div className="grid grid-cols-5 gap-4">
          {varData?.risk_score?.components && Object.entries(varData.risk_score.components).map(([key, value]: [string, any]) => (
            <div key={key}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-zinc-400 capitalize">{key.replace(/_/g, ' ')}</span>
                <span className={value >= 70 ? 'text-emerald-400' : value >= 50 ? 'text-amber-400' : 'text-red-400'}>
                  {value?.toFixed(0)}
                </span>
              </div>
              <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div 
                  className="h-full rounded-full transition-all"
                  style={{ 
                    width: `${value}%`,
                    backgroundColor: value >= 70 ? '#10b981' : value >= 50 ? '#f59e0b' : '#ef4444'
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Link to Full Dashboard */}
      <div className="text-center">
        <a href="/portfolio/risk" className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 rounded-lg font-medium transition-all">
          📉 Open Full VaR Dashboard with Backtesting & Position Sizing →
        </a>
      </div>
    </div>
  );
}


// =============================================================================
// STRATEGY TAB - F13-F17: Strategy Slots, Backtest, Divergence
// =============================================================================

function StrategyTab() {
  const [strategies, setStrategies] = useState<any>(null);
  const [activeSlots, setActiveSlots] = useState<any[]>([]);
  const [divergence, setDivergence] = useState<any>(null);
  const [backtestResult, setBacktestResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedStrategy, setSelectedStrategy] = useState('momentum');

  useEffect(() => {
    Promise.all([
      fetchAPI('/portfolio/strategies'),
      fetchAPI('/portfolio/strategies/active'),
      fetchAPI('/portfolio/strategies/divergence')
    ]).then(([str, active, div]) => {
      setStrategies(str);
      setActiveSlots(active?.slots || []);
      setDivergence(div);
      setLoading(false);
    });
  }, []);

  const runBacktest = async () => {
    const result = await fetchAPI(`/portfolio/strategies/backtest?strategy_id=${selectedStrategy}`, { method: 'POST' });
    setBacktestResult(result);
  };

  if (loading) return <LoadingState />;

  const availableStrategies = strategies?.strategies || [];

  return (
    <div className="space-y-4">
      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4">
        <KPICard label="ACTIVE STRATEGIES" value={activeSlots.length} />
        <KPICard label="AVAILABLE TEMPLATES" value={availableStrategies.length} />
        <KPICard 
          label="DIVERGENCE SCORE" 
          value={`${((divergence?.weight_divergence || 0) * 100).toFixed(1)}%`}
          color={(divergence?.weight_divergence || 0) > 0.1 ? 'red' : 'emerald'}
        />
        <KPICard label="REBALANCE URGENCY" value={divergence?.rebalance_urgency || 'LOW'} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Backtest Panel */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">STRATEGY BACKTEST</h3>
          </div>
          <div className="p-4 space-y-4">
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-100"
            >
              {availableStrategies.map((s: any) => (
                <option key={s.id || s} value={s.id || s}>{s.name || s}</option>
              ))}
            </select>
            <button
              onClick={runBacktest}
              className="w-full bg-emerald-500 hover:bg-emerald-600 text-white py-2 rounded font-semibold"
            >
              RUN BACKTEST
            </button>
            {backtestResult && (
              <div className="bg-zinc-800/50 rounded p-3 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-400">Total Return</span>
                  <span className={backtestResult.total_return >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                    {(backtestResult.total_return * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Sharpe Ratio</span>
                  <span className="text-zinc-100">{backtestResult.sharpe?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Max Drawdown</span>
                  <span className="text-red-400">{(backtestResult.max_drawdown * 100).toFixed(2)}%</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Active Strategies */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">ACTIVE SLOTS</h3>
          </div>
          <div className="p-4">
            {activeSlots.length === 0 ? (
              <div className="text-zinc-500 text-center py-4">No active strategy slots</div>
            ) : activeSlots.map((slot: any, i: number) => (
              <div key={i} className="flex justify-between items-center py-2 border-b border-zinc-800 last:border-0">
                <span className="text-zinc-300">{slot.name || slot.strategy_id}</span>
                <span className={`text-xs px-2 py-1 rounded ${slot.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-700 text-zinc-400'}`}>
                  {slot.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// TRADE TAB - F18-F21: Trade Preview, Basket, Opportunities
// =============================================================================

function TradeTab() {
  const [tradeHistory, setTradeHistory] = useState<any[]>([]);
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [preview, setPreview] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [ticker, setTicker] = useState('');
  const [shares, setShares] = useState('');
  const [action, setAction] = useState<'BUY' | 'SELL'>('BUY');

  useEffect(() => {
    Promise.all([
      fetchAPI('/portfolio/trade/history'),
      fetchAPI('/portfolio/opportunities')
    ]).then(([hist, opp]) => {
      setTradeHistory(hist?.trades || []);
      setOpportunities(opp?.opportunities || []);
      setLoading(false);
    });
  }, []);

  const handlePreview = async () => {
    if (!ticker || !shares) return;
    const result = await fetchAPI(`/portfolio/trade/preview?action=${action}&ticker=${ticker}&quantity=${shares}`, { method: 'POST' });
    setPreview(result);
  };

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-4">
      {/* Trade Preview */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-zinc-900/80 border border-zinc-800 rounded">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">TRADE INTENT SIMULATOR</h3>
          </div>
          <div className="p-4 space-y-4">
            <div className="flex gap-2">
              <button
                onClick={() => setAction('BUY')}
                className={`flex-1 py-2 rounded font-semibold ${action === 'BUY' ? 'bg-emerald-500 text-white' : 'bg-zinc-800 text-zinc-400'}`}
              >
                BUY
              </button>
              <button
                onClick={() => setAction('SELL')}
                className={`flex-1 py-2 rounded font-semibold ${action === 'SELL' ? 'bg-red-500 text-white' : 'bg-zinc-800 text-zinc-400'}`}
              >
                SELL
              </button>
            </div>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="SYMBOL"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-100"
            />
            <input
              type="number"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              placeholder="SHARES"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-100"
            />
            <button onClick={handlePreview} className="w-full bg-zinc-700 hover:bg-zinc-600 text-white py-2 rounded font-semibold">
              PREVIEW IMPACT
            </button>
            {preview && (
              <div className="bg-zinc-800/50 rounded p-3 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-400">New Weight</span>
                  <span className="text-zinc-100">{(preview.new_weight * 100).toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Est. Cost</span>
                  <span className="text-zinc-100">${preview.estimated_cost?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Approved</span>
                  <span className={preview.approved ? 'text-emerald-400' : 'text-red-400'}>
                    {preview.approved ? 'YES' : 'NO'}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Alpha Radar */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">ALPHA RADAR</h3>
          </div>
          <div className="p-4 max-h-[300px] overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-zinc-500 text-xs uppercase">
                  <th className="pb-2">Symbol</th>
                  <th className="pb-2 text-right">Fit Score</th>
                  <th className="pb-2 text-right">Alpha Est.</th>
                </tr>
              </thead>
              <tbody>
                {opportunities.map((opp: any, i: number) => (
                  <tr key={i} className="border-t border-zinc-800">
                    <td className="py-2 font-mono text-emerald-400">{opp.ticker}</td>
                    <td className="py-2 text-right text-zinc-300">{(opp.fit_score * 100).toFixed(0)}%</td>
                    <td className={`py-2 text-right ${opp.alpha_estimate >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {opp.alpha_estimate >= 0 ? '+' : ''}{(opp.alpha_estimate * 100).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Trade History */}
      <div className="bg-zinc-900/80 border border-zinc-800 rounded">
        <div className="px-4 py-3 border-b border-zinc-800">
          <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">TRADE HISTORY</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-800/50">
              <tr className="text-left text-zinc-500 uppercase text-xs">
                <th className="px-4 py-2">Time</th>
                <th className="px-4 py-2">Action</th>
                <th className="px-4 py-2">Symbol</th>
                <th className="px-4 py-2 text-right">Qty</th>
                <th className="px-4 py-2 text-right">Price</th>
                <th className="px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {tradeHistory.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-4 text-center text-zinc-500">No trades yet</td></tr>
              ) : tradeHistory.map((t: any, i: number) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-zinc-900/30' : ''}>
                  <td className="px-4 py-2 text-zinc-400">{t.fill_time || t.timestamp}</td>
                  <td className={`px-4 py-2 ${t.action === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>{t.action}</td>
                  <td className="px-4 py-2 font-mono text-zinc-100">{t.ticker}</td>
                  <td className="px-4 py-2 text-right text-zinc-300">{t.quantity}</td>
                  <td className="px-4 py-2 text-right text-zinc-300">${t.fill_price?.toFixed(2)}</td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${t.status === 'FILLED' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-700 text-zinc-400'}`}>
                      {t.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// HEDGE TAB - F22-F24: Hedge Response, Clock, PnL
// =============================================================================

function HedgeTab() {
  const [hedgeResponse, setHedgeResponse] = useState<any>(null);
  const [hedgeClock, setHedgeClock] = useState<any>(null);
  const [hedgePnl, setHedgePnl] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchAPI('/portfolio/hedge/response'),
      fetchAPI('/portfolio/hedge/clock'),
      fetchAPI('/portfolio/hedge/pnl')
    ]).then(([resp, clock, pnl]) => {
      setHedgeResponse(resp);
      setHedgeClock(clock);
      setHedgePnl(pnl);
      setLoading(false);
    });
  }, []);

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-4">
      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4">
        <KPICard label="PORTFOLIO BETA" value={hedgeResponse?.portfolio_beta?.toFixed(2) || 0} />
        <KPICard label="HEDGE RATIO" value={`${((hedgeResponse?.current_hedge_ratio || 0) * 100).toFixed(0)}%`} />
        <KPICard 
          label="HEDGE P&L" 
          value={`$${(hedgePnl?.total_hedge_pnl || 0).toLocaleString()}`}
          color={(hedgePnl?.total_hedge_pnl || 0) >= 0 ? 'emerald' : 'red'}
        />
        <KPICard 
          label="REBALANCE URGENCY" 
          value={hedgeClock?.rebalance_urgency || 'LOW'}
          color={hedgeClock?.rebalance_urgency === 'HIGH' ? 'red' : hedgeClock?.rebalance_urgency === 'MEDIUM' ? 'amber' : 'emerald'}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Hedge Response */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">HEDGE RECOMMENDATIONS</h3>
          </div>
          <div className="p-4">
            {hedgeResponse?.recommendations?.length === 0 ? (
              <div className="text-zinc-500 text-center py-4">No hedge recommendations</div>
            ) : (hedgeResponse?.recommendations || []).map((rec: any, i: number) => (
              <div key={i} className="border-b border-zinc-800 py-3 last:border-0">
                <div className="flex justify-between items-center">
                  <span className="text-zinc-300 font-medium">{rec.strategy}</span>
                  <span className="text-emerald-400 text-sm">{(rec.expected_protection * 100).toFixed(0)}% protection</span>
                </div>
                <p className="text-zinc-500 text-sm mt-1">Cost: ${rec.estimated_cost?.toFixed(2)}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Hedge Clock */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">HEDGE REBALANCING CLOCK</h3>
          </div>
          <div className="p-4 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Current Effectiveness</span>
              <span className="text-zinc-100">{((hedgeClock?.current_effectiveness || 0) * 100).toFixed(0)}%</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Target Effectiveness</span>
              <span className="text-zinc-100">{((hedgeClock?.target_effectiveness || 0) * 100).toFixed(0)}%</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Days to Threshold</span>
              <span className="text-zinc-100">{hedgeClock?.days_to_threshold || 0}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Recommended Action</span>
              <span className="text-emerald-400">{hedgeClock?.recommended_action || 'HOLD'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// AUDIT TAB - F25-F29: Counterfactual, Contribution, Return Path, Audit
// =============================================================================

function AuditTab() {
  const [counterfactual, setCounterfactual] = useState<any>(null);
  const [contribution, setContribution] = useState<any>(null);
  const [returnPath, setReturnPath] = useState<any>(null);
  const [auditLog, setAuditLog] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchAPI('/portfolio/counterfactual'),
      fetchAPI('/portfolio/contribution'),
      fetchAPI('/portfolio/return-path'),
      fetchAPI('/portfolio/audit')
    ]).then(([cf, cont, rp, audit]) => {
      setCounterfactual(cf);
      setContribution(cont);
      setReturnPath(rp);
      setAuditLog(audit);
      setLoading(false);
    });
  }, []);

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-4">
      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4">
        <KPICard 
          label="COUNTERFACTUAL DELTA" 
          value={`${((counterfactual?.return_delta || 0) * 100).toFixed(2)}%`}
          color={(counterfactual?.return_delta || 0) >= 0 ? 'emerald' : 'red'}
        />
        <KPICard label="SKILL COMPONENT" value={`${((returnPath?.skill_component || 0) * 100).toFixed(1)}%`} color="emerald" />
        <KPICard label="LUCK COMPONENT" value={`${((returnPath?.luck_component || 0) * 100).toFixed(1)}%`} />
        <KPICard label="AUDIT ENTRIES" value={auditLog?.log?.length || 0} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Counterfactual */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">COUNTERFACTUAL ANALYSIS</h3>
          </div>
          <div className="p-4 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Scenario</span>
              <span className="text-zinc-100">{counterfactual?.scenario_type || 'N/A'}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Actual Return</span>
              <span className="text-zinc-100">{((counterfactual?.actual_return || 0) * 100).toFixed(2)}%</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Hypothetical Return</span>
              <span className={counterfactual?.hypothetical_return >= counterfactual?.actual_return ? 'text-emerald-400' : 'text-red-400'}>
                {((counterfactual?.hypothetical_return || 0) * 100).toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-400">Confidence</span>
              <span className="text-zinc-100">{((counterfactual?.confidence || 0) * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {/* Return Path Decomposition */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">RETURN DECOMPOSITION</h3>
          </div>
          <div className="p-4 space-y-3">
            {['skill', 'luck', 'risk', 'cost', 'market'].map(comp => (
              <div key={comp} className="flex justify-between text-sm">
                <span className="text-zinc-400 capitalize">{comp} Component</span>
                <span className={returnPath?.[`${comp}_component`] >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                  {((returnPath?.[`${comp}_component`] || 0) * 100).toFixed(2)}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Contribution */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">TOP CONTRIBUTORS</h3>
          </div>
          <div className="p-4">
            {(contribution?.top_contributors || []).map((c: string, i: number) => (
              <div key={i} className="flex justify-between py-2 border-b border-zinc-800 last:border-0">
                <span className="font-mono text-emerald-400">{c}</span>
                <span className="text-zinc-300">#{i + 1}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Audit Log */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">AUDIT LOG</h3>
          </div>
          <div className="p-4 max-h-[200px] overflow-auto">
            {(auditLog?.log || []).slice(0, 10).map((entry: any, i: number) => (
              <div key={i} className="border-b border-zinc-800 py-2 last:border-0 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-400">{entry.action}</span>
                  <span className="text-zinc-500 text-xs">{entry.timestamp}</span>
                </div>
                <p className="text-zinc-300 text-xs mt-1">{entry.entity_type}: {entry.entity_id}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// OPTIMIZE TAB - NEW: Markowitz, Risk Parity, Black-Litterman, Factor Tilt
// =============================================================================

function OptimizeTab() {
  const [activeOptimizer, setActiveOptimizer] = useState('markowitz');

  return (
    <div className="space-y-4">
      {/* Sub-nav */}
      <div className="flex gap-2 bg-zinc-900/50 rounded p-2">
        {[
          { id: 'markowitz', label: 'Markowitz MVO' },
          { id: 'risk-parity', label: 'Risk Parity' },
          { id: 'factor-tilt', label: 'Factor Tilt' }
        ].map(opt => (
          <button
            key={opt.id}
            onClick={() => setActiveOptimizer(opt.id)}
            className={`px-4 py-2 text-sm font-medium rounded transition ${
              activeOptimizer === opt.id
                ? 'bg-cyan-600 text-white'
                : 'text-zinc-400 hover:bg-zinc-800'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {activeOptimizer === 'markowitz' && <MarkowitzOptimizer />}
      {activeOptimizer === 'risk-parity' && <RiskParityAllocator />}
      {activeOptimizer === 'factor-tilt' && <FactorTiltOptimizer />}
    </div>
  );
}

// =============================================================================
// PERFORMANCE TAB - NEW: Ratios, Drawdowns, Benchmark, Attribution
// =============================================================================

function PerformanceTab() {
  const [activeView, setActiveView] = useState('ratios');

  return (
    <div className="space-y-4">
      <div className="flex gap-2 bg-zinc-900/50 rounded p-2">
        {[
          { id: 'ratios', label: 'Sharpe/Sortino/Calmar' },
          { id: 'drawdowns', label: 'Drawdown Analysis' },
          { id: 'benchmark', label: 'Benchmark Comparison' }
        ].map(opt => (
          <button
            key={opt.id}
            onClick={() => setActiveView(opt.id)}
            className={`px-4 py-2 text-sm font-medium rounded transition ${
              activeView === opt.id ? 'bg-emerald-600 text-white' : 'text-zinc-400 hover:bg-zinc-800'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {activeView === 'ratios' && <RatiosDashboard />}
      {activeView === 'drawdowns' && <DrawdownAnalysis />}
      {activeView === 'benchmark' && <BenchmarkComparison />}
    </div>
  );
}

// =============================================================================
// SIMULATION TAB - NEW: Monte Carlo, VaR/CVaR
// =============================================================================

function SimulationTab() {
  const [activeView, setActiveView] = useState('montecarlo');

  return (
    <div className="space-y-4">
      <div className="flex gap-2 bg-zinc-900/50 rounded p-2">
        {[
          { id: 'montecarlo', label: 'Monte Carlo Simulation' },
          { id: 'var', label: 'VaR & CVaR' }
        ].map(opt => (
          <button
            key={opt.id}
            onClick={() => setActiveView(opt.id)}
            className={`px-4 py-2 text-sm font-medium rounded transition ${
              activeView === opt.id ? 'bg-amber-600 text-white' : 'text-zinc-400 hover:bg-zinc-800'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {activeView === 'montecarlo' && <MonteCarloSimulation />}
      {activeView === 'var' && <VaRCalculator />}
    </div>
  );
}

// =============================================================================
// ANALYSIS TAB - NEW: Holdings Overlap, Dividends, Tax Lots
// =============================================================================

function TradesTab() {
  const [trades, setTrades] = useState<any[]>([]);
  const [selectedTrade, setSelectedTrade] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadTrades = () => {
      const historyKey = 'quant360_trade_history';
      const history = JSON.parse(localStorage.getItem(historyKey) || '[]');
      setTrades(history);
      setLoading(false);
    };
    loadTrades();
  }, []);

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-black text-terminal-yellow uppercase tracking-tight">Institutional Trade Ledger</h2>
          <p className="text-[10px] text-terminal-dim font-black uppercase tracking-widest">Post-Trade Analysis & Forensic Logs</p>
        </div>
        <div className="bg-terminal-dark/40 border border-terminal-gray rounded px-3 py-1.5 flex gap-4 text-[10px] font-mono">
           <div className="flex items-center gap-1.5">
             <span className="text-terminal-dim truncate">TOTAL EXECUTED:</span>
             <span className="text-terminal-yellow font-bold">{trades.length}</span>
           </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Trade List Container */}
        <div className={`${selectedTrade ? 'col-span-8' : 'col-span-12'} transition-all duration-300`}>
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl overflow-hidden shadow-panel">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/80">
                <tr className="text-left text-terminal-dim uppercase text-[10px] font-black tracking-widest">
                  <th className="px-5 py-3">Timestamp</th>
                  <th className="px-5 py-3">Ticker</th>
                  <th className="px-5 py-3">Side</th>
                  <th className="px-5 py-3 text-right">Size</th>
                  <th className="px-5 py-3 text-right">Fill Price</th>
                  <th className="px-5 py-3 text-right">Notional</th>
                  <th className="px-5 py-3 text-center">Snapshot</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {trades.length === 0 ? (
                  <tr><td colSpan={7} className="px-5 py-12 text-center text-terminal-dim font-mono italic">No trade records found in persistence store.</td></tr>
                ) : trades.map((trade, i) => (
                  <tr 
                    key={trade.id || i} 
                    className={`hover:bg-zinc-800/30 transition-colors cursor-pointer ${selectedTrade?.id === trade.id ? 'bg-zinc-800/50' : ''}`}
                    onClick={() => setSelectedTrade(trade)}
                  >
                    <td className="px-5 py-3 font-mono text-xs text-zinc-400">
                      {new Date(trade.timestamp).toLocaleString(undefined, { 
                        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' 
                      })}
                    </td>
                    <td className="px-5 py-3">
                      <span className="font-black text-terminal-yellow">{trade.symbol}</span>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                        trade.side === 'BUY' ? 'bg-terminal-green/20 text-terminal-green' : 'bg-terminal-red/20 text-terminal-red'
                      }`}>
                        {trade.side}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right font-mono text-xs">
                      {trade.quantity.toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-right font-mono text-xs font-bold text-zinc-200">
                      ${trade.fillPrice?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-5 py-3 text-right font-mono text-xs text-zinc-400">
                      ${(trade.fillPrice * trade.quantity).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </td>
                    <td className="px-5 py-3 text-center">
                      <button className="text-terminal-cyan hover:text-terminal-cyan/80 transition-colors">
                        <svg className="w-4 h-4 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Forensic Detail Panel */}
        {selectedTrade && (
          <div className="col-span-4 space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
            <div className="bg-terminal-dark/60 border border-terminal-gray rounded-xl p-5 shadow-panel h-full">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h3 className="text-sm font-black text-terminal-text uppercase tracking-wider">Forensic Snapshot</h3>
                  <p className="text-[10px] text-terminal-dim font-mono">ID: {selectedTrade.id}</p>
                </div>
                <button 
                  onClick={() => setSelectedTrade(null)}
                  className="text-terminal-dim hover:text-terminal-text transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Journal Entry section if available */}
              <div className="space-y-4">
                <div className="bg-terminal-black/50 border border-terminal-gray/30 rounded-lg p-3">
                  <span className="text-[9px] font-black text-terminal-green uppercase tracking-widest block mb-2">Trade Journal</span>
                  <p className="text-xs text-zinc-300 italic mb-2 leading-relaxed">
                    &quot;{selectedTrade.journal?.thesis || 'No thesis provided for this execution.'}&quot;
                  </p>
                  <div className="flex gap-2">
                    <span className="px-2 py-0.5 bg-zinc-800 rounded text-[9px] text-zinc-400 font-mono">
                      {selectedTrade.journal?.setupName || 'Unmapped Setup'}
                    </span>
                    <span className="px-2 py-0.5 bg-zinc-800 rounded text-[9px] text-terminal-yellow font-mono">
                      {selectedTrade.journal?.reasonTag || 'Other'}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-terminal-black/50 border border-terminal-gray/30 rounded-lg p-3">
                    <span className="text-[9px] font-black text-terminal-dim uppercase tracking-widest block mb-1">Execution Score</span>
                    <div className="text-xl font-black text-terminal-green">94.2</div>
                    <span className="text-[8px] font-mono text-terminal-dim">Institutional Grade</span>
                  </div>
                  <div className="bg-terminal-black/50 border border-terminal-gray/30 rounded-lg p-3">
                    <span className="text-[9px] font-black text-terminal-dim uppercase tracking-widest block mb-1">Fill Quality</span>
                    <div className="text-xl font-black text-terminal-yellow">+0.02%</div>
                    <span className="text-[8px] font-mono text-terminal-dim">vs Mid-Price</span>
                  </div>
                </div>

                <div className="bg-terminal-black/50 border border-terminal-gray/30 rounded-lg p-4">
                  <span className="text-[9px] font-black text-terminal-cyan uppercase tracking-widest block mb-3">Signal State at Execution</span>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center text-[10px] font-mono">
                      <span className="text-terminal-dim uppercase">Confidence Score</span>
                      <span className="text-terminal-text font-bold">{selectedTrade.journal?.forensic?.confidence || 75}%</span>
                    </div>
                    <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
                      <div className="h-full bg-terminal-cyan" style={{ width: `${selectedTrade.journal?.forensic?.confidence || 75}%` }} />
                    </div>
                    <div className="flex justify-between items-center text-[10px] font-mono pt-2">
                      <span className="text-terminal-dim uppercase">Volatility Regime</span>
                      <span className="text-terminal-text">LOW_COMPRESSED</span>
                    </div>
                    <div className="flex justify-between items-center text-[10px] font-mono">
                      <span className="text-terminal-dim uppercase">LRC Position</span>
                      <span className="text-terminal-green">MEAN_REVERSION</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-terminal-gray/30">
                <button className="w-full py-2 bg-terminal-dim/10 border border-terminal-gray rounded font-black text-[10px] text-terminal-dim hover:text-terminal-text hover:bg-terminal-dim/20 transition-all uppercase tracking-widest">
                  Export Forensic Audit Report
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function AnalysisTab() {
  const [activeView, setActiveView] = useState('overlap');

  return (
    <div className="space-y-4">
      <div className="flex gap-2 bg-zinc-900/50 rounded p-2">
        {[
          { id: 'overlap', label: 'Holdings Overlap' },
          { id: 'dividends', label: 'Dividend Tracker' },
          { id: 'tax', label: 'Tax Lot Optimizer' }
        ].map(opt => (
          <button
            key={opt.id}
            onClick={() => setActiveView(opt.id)}
            className={`px-4 py-2 text-sm font-medium rounded transition ${
              activeView === opt.id ? 'bg-violet-600 text-white' : 'text-zinc-400 hover:bg-zinc-800'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {activeView === 'overlap' && <HoldingsOverlap />}
      {activeView === 'dividends' && <DividendTracker />}
      {activeView === 'tax' && <TaxLotOptimizer />}
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function PortfolioPage() {
  const [activeTab, setActiveTab] = useState('overview');

  const renderTab = () => {
    switch (activeTab) {
      case 'overview': return <OverviewTab />;
      case 'optimize': return <OptimizeTab />;
      case 'performance': return <PerformanceTab />;
      case 'simulation': return <SimulationTab />;
      case 'analysis': return <AnalysisTab />;
      case 'trades': return <TradesTab />;
      // REMOVED: regimes, strategy, hedge, audit cases per user request (components retained)
      default: return <OverviewTab />;
    }
  };

  return (
    <div className="min-h-screen bg-black text-zinc-100">
      {/* Sub-Tabs */}
      <div className="border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex gap-1 px-4 py-2">
          {subTabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors rounded ${
                activeTab === tab.id
                  ? 'bg-zinc-800 text-emerald-400'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="p-4">
        {renderTab()}
      </div>
    </div>
  );
}
