/**
 * Portfolio God Mode - Zustand Store
 * Central state management for portfolio data, risk, alerts, and feature outputs
 */
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

// =============================================================================
// TYPES
// =============================================================================

interface TimeSeriesPoint {
    t: string;
    v: number;
}

interface TimeSeries {
    id: string;
    name: string;
    freq: string;
    unit: string;
    points: TimeSeriesPoint[];
    meta: Record<string, string>;
    quality: Quality;
}

interface Quality {
    stalenessSec: number;
    missingPct: number;
    revisionFlag: boolean;
    warnings: string[];
}

interface Position {
    ticker: string;
    name: string;
    qty: number;
    px: number;
    mv: number;
    weight: number;
    sector: string;
    region: string;
    beta: number;
    pnl: number;
}

interface Benchmark {
    id: string;
    name: string;
}

interface PortfolioSnapshot {
    asOf: string;
    baseCcy: string;
    nav: number;
    cash: number;
    positions: Position[];
    benchmarks: Benchmark[];
    quality: Quality;
}

interface RiskMetrics {
    asOf: string;
    volAnn: number;
    var95: number;
    cvar95: number;
    maxDd: number;
    beta: number;
    corrAvg: number;
    liqScore: number;
    quality: Quality;
    explain: string[];
}

interface Alert {
    id: string;
    severity: 'Low' | 'Med' | 'High';
    message: string;
    evidence: string[];
    timestamp: string;
}

interface HealthMeter {
    score: number;
    label: string;
    components: Record<string, number>;
    drivers: { rows: Driver[] };
}

interface Driver {
    name: string;
    direction: 'Up' | 'Down' | 'Flat';
    magnitude: number;
    contribution: number;
    confidence: number;
    explain: string;
    evidence: string[];
}

interface PortfolioState {
    stateId: string;
    name: string;
    createdAt: string;
    notes: string;
}

type Window = '1W' | '1M' | '3M' | '6M' | '1Y' | '3Y' | '5Y' | 'MAX';
type FeatureId = string;

// =============================================================================
// STORE STATE
// =============================================================================

interface PortfolioStoreState {
    // Core data
    snapshot: PortfolioSnapshot | null;
    timeseries: {
        nav: TimeSeries | null;
        bench: TimeSeries[];
        factors: TimeSeries[];
    };
    risk: RiskMetrics | null;
    alerts: Alert[];
    health: HealthMeter | null;
    
    // State management
    states: PortfolioState[];
    activeStateId: string;
    
    // Global controls
    window: Window;
    benchmarkIds: string[];
    
    // Feature outputs (cached by feature ID)
    featureOutputs: Record<FeatureId, any>;
    
    // Active feature
    activeFeature: FeatureId;
    
    // UI state
    loading: boolean;
    error: string | null;
    drawerOpen: boolean;
    drawerTab: 'evidence' | 'audit' | 'inputs' | 'assumptions' | 'export';
    
    // Actions
    setWindow: (window: Window) => void;
    setBenchmarkIds: (ids: string[]) => void;
    setActiveFeature: (featureId: FeatureId) => void;
    setActiveStateId: (stateId: string) => void;
    setDrawerOpen: (open: boolean) => void;
    setDrawerTab: (tab: 'evidence' | 'audit' | 'inputs' | 'assumptions' | 'export') => void;
    
    // Data fetching
    fetchSnapshot: () => Promise<void>;
    fetchTimeseries: () => Promise<void>;
    fetchRisk: () => Promise<void>;
    fetchAlerts: () => Promise<void>;
    fetchHealth: () => Promise<void>;
    fetchStates: () => Promise<void>;
    saveState: (name: string, notes?: string) => Promise<void>;
    setFeatureOutput: (featureId: FeatureId, output: any) => void;
    
    // Refresh all
    refreshAll: () => Promise<void>;
}

const API_BASE = 'http://127.0.0.1:8000/api/portfolio';

// =============================================================================
// STORE IMPLEMENTATION
// =============================================================================

export const usePortfolioStore = create<PortfolioStoreState>()(
    devtools(
        (set, get) => ({
            // Initial state
            snapshot: null,
            timeseries: { nav: null, bench: [], factors: [] },
            risk: null,
            alerts: [],
            health: null,
            states: [],
            activeStateId: '',
            window: '1Y',
            benchmarkIds: ['SPY'],
            featureOutputs: {},
            activeFeature: 'brain',
            loading: false,
            error: null,
            drawerOpen: true,
            drawerTab: 'evidence',
            
            // Setters
            setWindow: (window) => {
                set({ window });
                // Refresh data with new window
                get().refreshAll();
            },
            
            setBenchmarkIds: (ids) => {
                set({ benchmarkIds: ids });
                get().fetchTimeseries();
            },
            
            setActiveFeature: (featureId) => {
                set({ activeFeature: featureId });
            },
            
            setActiveStateId: (stateId) => {
                set({ activeStateId: stateId });
            },
            
            setDrawerOpen: (open) => set({ drawerOpen: open }),
            setDrawerTab: (tab) => set({ drawerTab: tab }),
            
            // Data fetching
            fetchSnapshot: async () => {
                try {
                    set({ loading: true, error: null });
                    const res = await fetch(`${API_BASE}/snapshot`);
                    if (!res.ok) throw new Error('Failed to fetch snapshot');
                    const data = await res.json();
                    set({ snapshot: data, loading: false });
                } catch (e: any) {
                    set({ error: e.message, loading: false });
                }
            },
            
            fetchTimeseries: async () => {
                try {
                    const { window, benchmarkIds } = get();
                    const res = await fetch(
                        `${API_BASE}/timeseries?window=${window}&benchmarkIds=${benchmarkIds.join(',')}`
                    );
                    if (!res.ok) throw new Error('Failed to fetch timeseries');
                    const data = await res.json();
                    set({ timeseries: { nav: data.nav, bench: data.bench, factors: data.factors } });
                } catch (e: any) {
                    set({ error: e.message });
                }
            },
            
            fetchRisk: async () => {
                try {
                    const { window } = get();
                    const res = await fetch(`${API_BASE}/risk?window=${window}`);
                    if (!res.ok) throw new Error('Failed to fetch risk');
                    const data = await res.json();
                    set({ risk: data });
                } catch (e: any) {
                    set({ error: e.message });
                }
            },
            
            fetchAlerts: async () => {
                try {
                    const res = await fetch(`${API_BASE}/alerts`);
                    if (!res.ok) throw new Error('Failed to fetch alerts');
                    const data = await res.json();
                    set({ alerts: data.alerts || [] });
                } catch (e: any) {
                    set({ error: e.message });
                }
            },
            
            fetchHealth: async () => {
                try {
                    const res = await fetch(`${API_BASE}/health`);
                    if (!res.ok) throw new Error('Failed to fetch health');
                    const data = await res.json();
                    set({ health: data });
                } catch (e: any) {
                    set({ error: e.message });
                }
            },
            
            fetchStates: async () => {
                try {
                    const res = await fetch(`${API_BASE}/state/list`);
                    if (!res.ok) throw new Error('Failed to fetch states');
                    const data = await res.json();
                    set({ states: data.states || [] });
                } catch (e: any) {
                    set({ error: e.message });
                }
            },
            
            saveState: async (name, notes = '') => {
                try {
                    const res = await fetch(`${API_BASE}/state/save`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name, notes, overrides: {} })
                    });
                    if (!res.ok) throw new Error('Failed to save state');
                    const data = await res.json();
                    if (data.ok) {
                        get().fetchStates();
                        set({ activeStateId: data.stateId });
                    }
                } catch (e: any) {
                    set({ error: e.message });
                }
            },
            
            setFeatureOutput: (featureId, output) => {
                set((state) => ({
                    featureOutputs: { ...state.featureOutputs, [featureId]: output }
                }));
            },
            
            refreshAll: async () => {
                const store = get();
                set({ loading: true });
                await Promise.all([
                    store.fetchSnapshot(),
                    store.fetchTimeseries(),
                    store.fetchRisk(),
                    store.fetchAlerts(),
                    store.fetchHealth(),
                    store.fetchStates()
                ]);
                set({ loading: false });
            }
        }),
        { name: 'portfolio-godmode' }
    )
);

// =============================================================================
// FEATURE DATA FETCHING HELPERS
// =============================================================================

const FEATURE_ENDPOINTS: Record<string, string> = {
    longevity: '/longevity',
    crowding: '/crowding',
    fingerprint: '/fingerprint',
    entropy: '/entropy',
    efficiency: '/efficiency',
    return_path: '/returns',
    hedge_clock: '/hedge-clock',
    dd_sensitivity: '/dd-sensitivity',
    alpha_radar: '/alpha-signals',
    style_box: '/style-box',
    contribution: '/contribution',
    walk_forward: '/walk-forward',
    regime_report: '/regimes',
    scenario_library: '/scenario-library',
    multi_bench: '/multi-bench',
    consistency: '/consistency',
    ranking: '/ranking',
    hedge_library: '/hedge-library',
    hedge_pnl: '/hedge-pnl',
    guardrails: '/guardrails',
    sanity_check: '/sanity'
};

const API_BASE_FETCHER = 'http://127.0.0.1:8000/api/portfolio';

export async function fetchFeatureData(featureId: string): Promise<any> {
    const endpoint = FEATURE_ENDPOINTS[featureId];
    if (!endpoint) return null;
    
    try {
        const res = await fetch(`${API_BASE_FETCHER}${endpoint}`);
        if (!res.ok) throw new Error(`Failed to fetch ${featureId}`);
        return await res.json();
    } catch (e) {
        console.error(`Error fetching ${featureId}:`, e);
        return null;
    }
}

export async function runScenario(scenarioIds: string[], stackMode: string = 'add', horizon: string = '1M'): Promise<any> {
    try {
        const res = await fetch(`${API_BASE_FETCHER}/scenario/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scenarioIds, stackMode, horizon })
        });
        if (!res.ok) throw new Error('Failed to run scenario');
        return await res.json();
    } catch (e) {
        console.error('Error running scenario:', e);
        return null;
    }
}

export async function applyHedge(hedgeId: string, budgetPct: number = 0.05): Promise<any> {
    try {
        const res = await fetch(`${API_BASE_FETCHER}/hedge/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hedgeId, budgetPct })
        });
        if (!res.ok) throw new Error('Failed to apply hedge');
        return await res.json();
    } catch (e) {
        console.error('Error applying hedge:', e);
        return null;
    }
}

export async function createTradeBasket(allocations: {ticker: string, weight: number}[], cashGuard: number = 0.05): Promise<any> {
    try {
        const res = await fetch(`${API_BASE_FETCHER}/trade/basket`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ allocations, cashGuard })
        });
        if (!res.ok) throw new Error('Failed to create trade basket');
        return await res.json();
    } catch (e) {
        console.error('Error creating trade basket:', e);
        return null;
    }
}

export async function exportData(moduleId: string, type: 'json' | 'csv' | 'png', payload: any): Promise<any> {
    try {
        const res = await fetch(`${API_BASE_FETCHER}/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ moduleId, type, payload })
        });
        if (!res.ok) throw new Error('Failed to export');
        return await res.json();
    } catch (e) {
        console.error('Error exporting:', e);
        return null;
    }
}

// =============================================================================
// FEATURE DEFINITIONS
// =============================================================================

export const FEATURES = {
    // God Layer (1-17)
    brain: { id: 'brain', name: 'Portfolio Brain', group: 'core', order: 1 },
    shock_propagation: { id: 'shock_propagation', name: 'Shock Propagation', group: 'risk', order: 2 },
    cross_impact: { id: 'cross_impact', name: 'Cross Impact Matrix', group: 'risk', order: 3 },
    weather: { id: 'weather', name: 'Weather Station', group: 'risk', order: 4 },
    position: { id: 'position', name: 'Position Analyzer', group: 'core', order: 5 },
    liquidity: { id: 'liquidity', name: 'Liquidity Map', group: 'risk', order: 6 },
    longevity: { id: 'longevity', name: 'Longevity Score', group: 'risk', order: 7 },
    crowding: { id: 'crowding', name: 'Crowding Scanner', group: 'risk', order: 8 },
    trade_intent: { id: 'trade_intent', name: 'Trade Intent', group: 'trade', order: 9 },
    fingerprint: { id: 'fingerprint', name: 'Fingerprint', group: 'core', order: 10 },
    entropy: { id: 'entropy', name: 'Entropy Meter', group: 'risk', order: 11 },
    efficiency: { id: 'efficiency', name: 'Capital Efficiency', group: 'core', order: 12 },
    return_path: { id: 'return_path', name: 'Return Path', group: 'core', order: 13 },
    hedge_clock: { id: 'hedge_clock', name: 'Hedge Clock', group: 'hedge', order: 14 },
    dd_sensitivity: { id: 'dd_sensitivity', name: 'DD Sensitivity', group: 'risk', order: 15 },
    sculptor: { id: 'sculptor', name: 'Target Sculptor', group: 'trade', order: 16 },
    alpha_radar: { id: 'alpha_radar', name: 'Alpha Radar', group: 'core', order: 17 },
    
    // Extras (18-38)
    time_scrubber: { id: 'time_scrubber', name: 'Time Scrubber', group: 'control', order: 18 },
    states: { id: 'states', name: 'States', group: 'control', order: 19 },
    alerts_rule: { id: 'alerts_rule', name: 'Alert Rules', group: 'control', order: 20 },
    health: { id: 'health', name: 'Health Meter', group: 'core', order: 21 },
    style_box: { id: 'style_box', name: 'Style Box', group: 'core', order: 22 },
    contribution: { id: 'contribution', name: 'Contribution Replay', group: 'core', order: 23 },
    walk_forward: { id: 'walk_forward', name: 'Walk Forward', group: 'backtest', order: 24 },
    grid_explorer: { id: 'grid_explorer', name: 'Grid Explorer', group: 'backtest', order: 25 },
    regime_report: { id: 'regime_report', name: 'Regime Report', group: 'backtest', order: 26 },
    scenario_library: { id: 'scenario_library', name: 'Scenario Library', group: 'scenario', order: 27 },
    scenario_stack: { id: 'scenario_stack', name: 'Scenario Stack', group: 'scenario', order: 28 },
    hedge_response: { id: 'hedge_response', name: 'Hedge Response', group: 'hedge', order: 29 },
    multi_bench: { id: 'multi_bench', name: 'Multi Benchmark', group: 'compare', order: 30 },
    consistency: { id: 'consistency', name: 'Consistency', group: 'compare', order: 31 },
    ranking: { id: 'ranking', name: 'Strategy Ranking', group: 'compare', order: 32 },
    hedge_library: { id: 'hedge_library', name: 'Hedge Library', group: 'hedge', order: 33 },
    hedge_pnl: { id: 'hedge_pnl', name: 'Hedge PnL', group: 'hedge', order: 34 },
    one_tap_hedge: { id: 'one_tap_hedge', name: 'One Tap Hedge', group: 'hedge', order: 35 },
    basket_trades: { id: 'basket_trades', name: 'Basket Trades', group: 'trade', order: 36 },
    guardrails: { id: 'guardrails', name: 'Guardrails', group: 'trade', order: 37 },
    sanity_check: { id: 'sanity_check', name: 'Sanity Check', group: 'trade', order: 38 },
    trading: { id: 'trading', name: '💹 Trading Center', group: 'trade', order: 39 }
} as const;

export const FEATURE_GROUPS = [
    { id: 'core', name: 'Core', features: ['brain', 'health', 'position', 'fingerprint', 'efficiency', 'return_path', 'style_box', 'contribution', 'alpha_radar'] },
    { id: 'risk', name: 'Risk', features: ['shock_propagation', 'cross_impact', 'weather', 'liquidity', 'longevity', 'crowding', 'entropy', 'dd_sensitivity'] },
    { id: 'hedge', name: 'Hedge', features: ['hedge_clock', 'hedge_response', 'hedge_library', 'hedge_pnl', 'one_tap_hedge'] },
    { id: 'scenario', name: 'Scenario', features: ['scenario_library', 'scenario_stack'] },
    { id: 'backtest', name: 'Backtest', features: ['walk_forward', 'grid_explorer', 'regime_report'] },
    { id: 'compare', name: 'Compare', features: ['multi_bench', 'consistency', 'ranking'] },
    { id: 'trade', name: 'Trade', features: ['trading', 'trade_intent', 'sculptor', 'basket_trades', 'guardrails', 'sanity_check'] },
    { id: 'control', name: 'Control', features: ['time_scrubber', 'states', 'alerts_rule'] }
];

export type FeatureKey = keyof typeof FEATURES;
