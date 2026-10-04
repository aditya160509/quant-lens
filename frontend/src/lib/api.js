import { API_BASE_URL } from "./apiBase";

export { API_BASE_URL };

async function handleResponse(res, errorContext) {
    if (!res.ok) {
        let errorMsg = "Unknown error";
        try {
            const errData = await res.json();
            errorMsg = errData.detail || JSON.stringify(errData);
        } catch (e) {
            errorMsg = res.statusText;
        }
        throw new Error(`${errorContext}: ${errorMsg}`);
    }
    return res.json();
}

// --- MONITOR ---
export async function fetchMonitorData(horizon = "3mo") {
    const res = await fetch(`${API_BASE_URL}/monitor?horizon=${horizon}`);
    return handleResponse(res, "Failed to fetch monitor data");
}

// --- MONITOR COMMAND CENTER ---
export async function fetchMonitorTickers() {
    const res = await fetch(`${API_BASE_URL}/monitor/tickers`);
    return handleResponse(res, "Failed to fetch monitor tickers");
}

export async function fetchMonitorBreadth(market = "IN") {
    const res = await fetch(`${API_BASE_URL}/monitor/breadth?market=${market}`);
    return handleResponse(res, "Failed to fetch monitor breadth");
}

export const fetchMonitorLeaders = async (market = "IN", k = 15) => {
    const res = await fetch(`${API_BASE_URL}/monitor/leaders?market=${market}&k=${k}`);
    return handleResponse(res, "Failed to fetch monitor leaders");
};

export const fetchNormalizedReturns = async (market = "IN", days = 30) => {
    const res = await fetch(`${API_BASE_URL}/monitor/normalized_returns?market=${market}&days=${days}`);
    return handleResponse(res, "Failed to fetch normalized returns");
};

export async function fetchMonitorFlows() {
    const res = await fetch(`${API_BASE_URL}/monitor/flows`);
    return handleResponse(res, "Failed to fetch monitor flows");
}

export async function fetchMonitorFXCrypto() {
    const res = await fetch(`${API_BASE_URL}/monitor/fxcrypto`);
    return handleResponse(res, "Failed to fetch monitor FX/crypto");
}

export async function fetchMonitorRegime(market = "IN", index = "^NSEI", window = "2y") {
    const params = new URLSearchParams({ market, index, window });
    const res = await fetch(`${API_BASE_URL}/monitor/regime?${params.toString()}`);
    return handleResponse(res, "Failed to fetch monitor regime");
}

export async function fetchMonitorOptions(nifty = true, window = "1y") {
    const res = await fetch(`${API_BASE_URL}/monitor/options?nifty=${nifty}&window=${window}`);
    return handleResponse(res, "Failed to fetch monitor options");
}

export async function fetchMonitorSchedule(market = "IN", date = null) {
    const params = new URLSearchParams({ market });
    if (date) params.set("date", date);
    const res = await fetch(`${API_BASE_URL}/monitor/schedule?${params.toString()}`);
    return handleResponse(res, "Failed to fetch monitor schedule");
}

export async function fetchMonitorNews(region = "IN", k = 20) {
    const res = await fetch(`${API_BASE_URL}/monitor/news?region=${region}&k=${k}`);
    return handleResponse(res, "Failed to fetch monitor news");
}

export async function fetchMonitorClock() {
    const res = await fetch(`${API_BASE_URL}/monitor/clock`);
    return handleResponse(res, "Failed to fetch monitor clock");
}

// --- MONITOR REFINEMENT (Ticker Strips, Heatmap, Breadth Charts) ---
export async function fetchEquityTickers() {
    const res = await fetch(`${API_BASE_URL}/monitor/equity_tickers`);
    return handleResponse(res, "Failed to fetch equity tickers");
}

export async function fetchMacroTickers() {
    const res = await fetch(`${API_BASE_URL}/monitor/macro_tickers`);
    return handleResponse(res, "Failed to fetch macro tickers");
}

export async function fetchMarketHeatmap(market = "IN") {
    const params = new URLSearchParams({ market });
    const res = await fetch(`${API_BASE_URL}/monitor/heatmap?${params.toString()}`);
    return handleResponse(res, `Failed to fetch ${market} heatmap`);
}

export async function fetchADL(days = 90) {
    const res = await fetch(`${API_BASE_URL}/monitor/adl?days=${days}`);
    return handleResponse(res, "Failed to fetch A/D line");
}

export async function fetchVolatilityRegime(days = 90) {
    const res = await fetch(`${API_BASE_URL}/monitor/volatility_regime?days=${days}`);
    return handleResponse(res, "Failed to fetch volatility regime");
}

export async function fetchMonitorSnapshot(market = "IN") {
    const res = await fetch(`${API_BASE_URL}/monitor/snapshot?market=${market}`);
    return handleResponse(res, "Failed to fetch monitor snapshot");
}

export async function fetchMonitorMasterSnapshot(market = "IN", horizon = "3mo") {
    const res = await fetch(`${API_BASE_URL}/monitor-v2/master-snapshot?market=${market}&horizon=${horizon}`);
    return handleResponse(res, "Failed to fetch master snapshot");
}

export async function fetchADThrust(days = 90) {
    const res = await fetch(`${API_BASE_URL}/monitor/ad_thrust?days=${days}`);
    return handleResponse(res, "Failed to fetch A/D thrust");
}

// --- MARKETS DAILY (Post-Close Cognition Screen - Rebuilt per Spec) ---
export async function fetchMarketDailyMatrix() {
    const res = await fetch(`${API_BASE_URL}/markets_daily/matrix`);
    return handleResponse(res, "Failed to fetch market matrix");
}

export async function fetchMarketDailySectorDispersion() {
    const res = await fetch(`${API_BASE_URL}/markets_daily/sector_dispersion`);
    return handleResponse(res, "Failed to fetch sector dispersion");
}

export async function fetchGraphIndexStructure() {
    const res = await fetch(`${API_BASE_URL}/markets_daily/graph_index_structure`);
    return handleResponse(res, "Failed to fetch index structure graph");
}

export async function fetchGraphMoveIntensity() {
    const res = await fetch(`${API_BASE_URL}/markets_daily/graph_move_intensity`);
    return handleResponse(res, "Failed to fetch move intensity graph");
}

export async function fetchGraphGapFollowthrough() {
    const res = await fetch(`${API_BASE_URL}/markets_daily/graph_gap_followthrough`);
    return handleResponse(res, "Failed to fetch gap followthrough graph");
}

export async function fetchMarketDailyStockMoveMap(k = 30) {
    const res = await fetch(`${API_BASE_URL}/markets_daily/stock_move_map?k=${k}`);
    return handleResponse(res, "Failed to fetch stock move map");
}

export async function fetchMarketDailySectorRelativeStrength() {
    const res = await fetch(`${API_BASE_URL}/markets_daily/sector_relative_strength`);
    return handleResponse(res, "Failed to fetch sector relative strength");
}

export async function fetchMarketDailyNews(category = "Market", k = 40) {
    const res = await fetch(`${API_BASE_URL}/markets_daily/news?category=${category}&k=${k}`);
    return handleResponse(res, "Failed to fetch news");
}

// --- MARKETS ---
export async function fetchMarketsData(window = "1y") {
    const res = await fetch(`${API_BASE_URL}/markets?window=${window}`);
    return handleResponse(res, "Failed to fetch markets data");
}

export async function fetchSectorRotation(period = "3mo") {
    const res = await fetch(`${API_BASE_URL}/markets/sector_rotation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period })
    });
    return handleResponse(res, "Failed to fetch sector rotation");
}

export async function fetchMarketIntraday(ticker = "SPY", interval = "5m") {
    const params = new URLSearchParams({ ticker, interval });
    const res = await fetch(`${API_BASE_URL}/markets/intraday?${params.toString()}`);
    return handleResponse(res, "Failed to fetch intraday data");
}

// --- EARNINGS ---
export async function fetchEarningsUpcoming(daysAhead = 30) {
    const res = await fetch(`${API_BASE_URL}/earnings/upcoming?days_ahead=${daysAhead}`);
    return handleResponse(res, "Failed to fetch upcoming earnings");
}

// --- SECURITY ---
export async function fetchSecurityDetail(symbol, period = "1y", interval = "1d") {
    const res = await fetch(`${API_BASE_URL}/security/detail?symbol=${symbol}&period=${period}&interval=${interval}`);
    return handleResponse(res, "Failed to fetch security detail");
}

export async function fetchSecurityIndicators(symbol, period = "1y", interval = "1d") {
    const res = await fetch(`${API_BASE_URL}/security/${symbol}/indicators?period=${period}&interval=${interval}`);
    return handleResponse(res, "Failed to fetch security indicators");
}

export async function fetchLiquidity(ticker) {
    const res = await fetch(`${API_BASE_URL}/liquidity/${ticker}`);
    return handleResponse(res, "Failed to fetch liquidity metrics");
}

// --- MACRO ---
export async function fetchMacroDashboard() {
    const res = await fetch(`${API_BASE_URL}/macro`);
    return handleResponse(res, "Failed to fetch macro dashboard");
}

// --- LABS ---
export async function runFactors(ticker, windowYears, model = "ff3") {
    const res = await fetch(`${API_BASE_URL}/labs/factors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears, model })
    });
    return handleResponse(res, "Failed to run factors analysis");
}

export async function runVolatility(ticker, windowYears) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run volatility analysis");
}

export async function runVolatilityIntelligence(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/intelligence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run volatility intelligence");
}

// Individual Volatility Feature APIs
export async function runVolRvSuite(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/rv_suite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run RV suite");
}

export async function runVolHeatmap(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/heatmap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run volatility heatmap");
}

export async function runVolCluster(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/cluster`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run cluster detector");
}

export async function runVolZscore(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/zscore`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run z-score");
}

export async function runVolRegime(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/regime`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run regime classifier");
}

export async function runVolMacro(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/macro`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run macro model");
}

export async function runVolForecast(ticker, horizon = 20) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/forecast`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, horizon })
    });
    return handleResponse(res, "Failed to run forecast cone");
}

export async function runVolGravity(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/gravity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run gravity well");
}

export async function runVolFracture(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/fracture`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run fracture map");
}

export async function runVolReservoir(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/reservoir`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run reservoir");
}

export async function runVolSymmetry(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/symmetry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run symmetry break");
}

export async function runVolTransmission(tickers = null) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/transmission`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers })
    });
    return handleResponse(res, "Failed to run transmission engine");
}

export async function runVolIvRvSpread(ticker, windowYears = 2) {
    const res = await fetch(`${API_BASE_URL}/labs/volatility/iv_rv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run IV-RV spread");
}

export async function runRegimes(ticker, windowYears) {
    const res = await fetch(`${API_BASE_URL}/labs/regimes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run regime detection");
}

export async function runPCA(tickers = null) {
    const res = await fetch(`${API_BASE_URL}/labs/pca`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers })
    });
    return handleResponse(res, "Failed to fetch PCA");
}

// --- PCA EIGENPHYSICS (Advanced PCA Analysis) ---

export async function runPCAEigenphysics({
    universeKey = "MACRO",
    lookbackDays = 252,
    windows = [60],
    features = null,
    includeTimeline = false,
    forceRebuild = false
} = {}) {
    const res = await fetch(`${API_BASE_URL}/pca/eigenphysics/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            universe_key: universeKey,
            lookback_days: lookbackDays,
            windows,
            features,
            include_timeline: includeTimeline,
            force_rebuild: forceRebuild
        })
    });
    return handleResponse(res, "Failed to run PCA Eigenphysics");
}

export async function getPCAState(universeKey = "MACRO", window = 60, lookbackDays = 252) {
    const params = new URLSearchParams({
        universe_key: universeKey,
        window: window.toString(),
        lookback_days: lookbackDays.toString()
    });
    const res = await fetch(`${API_BASE_URL}/pca/eigenphysics/state?${params.toString()}`);
    return handleResponse(res, "Failed to get PCA state");
}

export async function getPCAFeature(featureName, universeKey = "MACRO", window = 60, lookbackDays = 252) {
    const params = new URLSearchParams({
        universe_key: universeKey,
        window: window.toString(),
        lookback_days: lookbackDays.toString()
    });
    const res = await fetch(`${API_BASE_URL}/pca/eigenphysics/feature/${featureName}?${params.toString()}`);
    return handleResponse(res, `Failed to get PCA feature: ${featureName}`);
}

export async function runPCAShock(universeKey = "MACRO", window = 60, shocks = {}) {
    const res = await fetch(`${API_BASE_URL}/pca/eigenphysics/shock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            universe_key: universeKey,
            window,
            shocks
        })
    });
    return handleResponse(res, "Failed to run PCA shock simulation");
}

export async function getPCACacheStatus() {
    const res = await fetch(`${API_BASE_URL}/pca/eigenphysics/cache-status`);
    return handleResponse(res, "Failed to get PCA cache status");
}

// --- PCA GOD MODE OMEGA (Institutional-Grade PCA System) ---

export async function getPCAGodModeUniverses() {
    const res = await fetch(`${API_BASE_URL}/pca/godmode/universes`);
    return handleResponse(res, "Failed to get PCA universes");
}

export async function runPCAGodMode({
    universeKey = "US_SP500_TOP50",
    customTickers = null,
    lookbackDays = 252,
    minHistoryDays = 100,  // Lowered for international market support
    maxMissingPct = 0.10,  // Increased tolerance
    returnType = "log",
    normalization = "zscore",
    matrixType = "correlation",
    rollingEnabled = false,  // Disabled by default for faster initial load
    rollingWindow = 126,
    rollingStep = 42
} = {}) {
    const res = await fetch(`${API_BASE_URL}/pca/godmode/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            universe_key: universeKey,
            custom_tickers: customTickers,
            lookback_days: lookbackDays,
            min_history_days: minHistoryDays,
            max_missing_pct: maxMissingPct,
            return_type: returnType,
            normalization,
            matrix_type: matrixType,
            rolling_enabled: rollingEnabled,
            rolling_window: rollingWindow,
            rolling_step: rollingStep
        })
    });
    return handleResponse(res, "Failed to run PCA God Mode");
}

export async function getPCAGodModeStructure(universeKey = "US_SP500_TOP50", lookbackDays = 252) {
    const params = new URLSearchParams({ universe_key: universeKey, lookback_days: lookbackDays.toString() });
    const res = await fetch(`${API_BASE_URL}/pca/godmode/structure?${params.toString()}`);
    return handleResponse(res, "Failed to get PCA structure");
}

export async function getPCAGodModeFactors(universeKey = "US_SP500_TOP50", lookbackDays = 252, numPcs = 10) {
    const params = new URLSearchParams({ universe_key: universeKey, lookback_days: lookbackDays.toString(), num_pcs: numPcs.toString() });
    const res = await fetch(`${API_BASE_URL}/pca/godmode/factors?${params.toString()}`);
    return handleResponse(res, "Failed to get PCA factors");
}

export async function getPCAGodModeLoadings(universeKey, pcIndex, lookbackDays = 252) {
    const params = new URLSearchParams({ universe_key: universeKey, lookback_days: lookbackDays.toString() });
    const res = await fetch(`${API_BASE_URL}/pca/godmode/factors/${pcIndex}/loadings?${params.toString()}`);
    return handleResponse(res, "Failed to get PCA loadings");
}

export async function getPCAGodModeStability(universeKey = "US_SP500_TOP50", lookbackDays = 252, numPcs = 5) {
    const params = new URLSearchParams({ universe_key: universeKey, lookback_days: lookbackDays.toString(), num_pcs: numPcs.toString() });
    const res = await fetch(`${API_BASE_URL}/pca/godmode/stability?${params.toString()}`);
    return handleResponse(res, "Failed to get PCA stability");
}

export async function getPCAGodModeRedundancy(universeKey = "US_SP500_TOP50", lookbackDays = 252, kComponents = 5, threshold = 0.85) {
    const params = new URLSearchParams({ 
        universe_key: universeKey, 
        lookback_days: lookbackDays.toString(), 
        k_components: kComponents.toString(),
        similarity_threshold: threshold.toString()
    });
    const res = await fetch(`${API_BASE_URL}/pca/godmode/redundancy?${params.toString()}`);
    return handleResponse(res, "Failed to get PCA redundancy");
}

export async function simulatePCAGodModeShock(universeKey = "US_SP500_TOP50", lookbackDays = 252, shockConfig = { 1: 2.0 }) {
    const res = await fetch(`${API_BASE_URL}/pca/godmode/shock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            universe_key: universeKey,
            lookback_days: lookbackDays,
            shock_config: shockConfig
        })
    });
    return handleResponse(res, "Failed to simulate PCA shock");
}

export async function getPCAGodModeBreaks(universeKey = "US_SP500_TOP50", lookbackDays = 504) {
    const params = new URLSearchParams({ universe_key: universeKey, lookback_days: lookbackDays.toString() });
    const res = await fetch(`${API_BASE_URL}/pca/godmode/breaks?${params.toString()}`);
    return handleResponse(res, "Failed to get PCA breaks");
}

export async function getPCAGodModeGovernance(universeKey = "US_SP500_TOP50", lookbackDays = 252) {
    const params = new URLSearchParams({ universe_key: universeKey, lookback_days: lookbackDays.toString() });
    const res = await fetch(`${API_BASE_URL}/pca/godmode/governance?${params.toString()}`);
    return handleResponse(res, "Failed to get PCA governance");
}

export async function exportPCAGodModeData(universeKey = "US_SP500_TOP50", lookbackDays = 252, formats = ["eigenvalues", "loadings"]) {
    const params = new URLSearchParams({ universe_key: universeKey, lookback_days: lookbackDays.toString() });
    formats.forEach(f => params.append('formats', f));
    const res = await fetch(`${API_BASE_URL}/pca/godmode/export?${params.toString()}`, { method: 'POST' });
    return handleResponse(res, "Failed to export PCA data");
}


export async function getFactorScreen(universe = "us") {
    const res = await fetch(`${API_BASE_URL}/labs/factors/screener`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ universe })
    });
    return handleResponse(res, "Failed to fetch factor screen");
}

export async function fetchScreener(params = {}) {
    const queryParams = new URLSearchParams();
    if (params.sector) queryParams.set('sector', params.sector);
    if (params.industry) queryParams.set('industry', params.industry);
    if (params.liquidity) queryParams.set('liquidity', params.liquidity);
    if (params.vol_bucket) queryParams.set('vol_bucket', params.vol_bucket);
    if (params.marketcap_min) queryParams.set('marketcap_min', params.marketcap_min);
    if (params.marketcap_max) queryParams.set('marketcap_max', params.marketcap_max);
    if (params.sort_by) queryParams.set('sort_by', params.sort_by);
    if (params.sort_dir) queryParams.set('sort_dir', params.sort_dir);
    if (params.limit) queryParams.set('limit', params.limit);
    if (params.offset) queryParams.set('offset', params.offset);

    const res = await fetch(`${API_BASE_URL}/labs/screener?${queryParams.toString()}`);
    return handleResponse(res, "Failed to fetch screener data");
}

// --- PORTFOLIO ---
export async function fetchPortfolioState() {
    const res = await fetch(`${API_BASE_URL}/portfolio/state`);
    return handleResponse(res, "Failed to fetch portfolio state");
}

export async function fetchPortfolioHistory() {
    const res = await fetch(`${API_BASE_URL}/portfolio/history`);
    return handleResponse(res, "Failed to fetch portfolio history");
}

export async function fetchPortfolioAllocations() {
    const res = await fetch(`${API_BASE_URL}/portfolio/allocations`);
    return handleResponse(res, "Failed to fetch portfolio allocations");
}

export async function fetchPortfolioSummary() {
    const res = await fetch(`${API_BASE_URL}/portfolio/summary`);
    return handleResponse(res, "Failed to fetch portfolio summary");
}

export async function executeTrade({ side, ticker, quantity }) {
    const res = await fetch(`${API_BASE_URL}/portfolio/trade`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ side, ticker, quantity })
    });
    return handleResponse(res, "Failed to execute trade");
}

export async function optimizePortfolio({ tickers, mode }) {
    const res = await fetch(`${API_BASE_URL}/portfolio/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers, mode })
    });
    return handleResponse(res, "Failed to optimize portfolio");
}

export async function runBacktest({ strategy, startDate, endDate }) {
    const res = await fetch(`${API_BASE_URL}/portfolio/backtest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_id: strategy, start_date: startDate, end_date: endDate })
    });
    return handleResponse(res, "Failed to run backtest");
}

export async function runScenario({ scenarioId, shockSize, customShocks }) {
    const res = await fetch(`${API_BASE_URL}/portfolio/scenarios`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_id: scenarioId, shock_size: shockSize, custom_shocks: customShocks })
    });
    return handleResponse(res, "Failed to run scenario");
}

export async function runPortfolioComparison({ benchmarkId, alternativeWeights }) {
    const res = await fetch(`${API_BASE_URL}/portfolio/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ benchmark_id: benchmarkId, alternative_weights: alternativeWeights })
    });
    return handleResponse(res, "Failed to run comparison");
}

export async function fetchSuggestions() {
    const res = await fetch(`${API_BASE_URL}/portfolio/suggestions`);
    return handleResponse(res, "Failed to fetch suggestions");
}

export async function fetchRegistryStatus() {
    const res = await fetch(`${API_BASE_URL}/registry/status`);
    return handleResponse(res, "Failed to fetch registry status");
}

// --- CLUSTER B ---

// Watchlists
export async function getWatchlists() {
    const res = await fetch(`${API_BASE_URL}/watchlists`);
    return handleResponse(res, "Failed to fetch watchlists");
}

export async function createWatchlist(name, tickers) {
    const res = await fetch(`${API_BASE_URL}/watchlists`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, tickers })
    });
    return handleResponse(res, "Failed to create watchlist");
}

export async function deleteWatchlist(id) {
    const res = await fetch(`${API_BASE_URL}/watchlists/${id}`, {
        method: "DELETE"
    });
    return handleResponse(res, "Failed to delete watchlist");
}

// Options
export async function getOptions(ticker) {
    const res = await fetch(`${API_BASE_URL}/options/${ticker}`);
    return handleResponse(res, "Failed to fetch options");
}

// Alerts
export async function getAlerts() {
    const res = await fetch(`${API_BASE_URL}/alerts`);
    return handleResponse(res, "Failed to fetch alerts");
}

export async function createAlert(ticker, condition, threshold) {
    const res = await fetch(`${API_BASE_URL}/alerts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, condition, threshold })
    });
    return handleResponse(res, "Failed to create alert");
}

// Workspaces
export async function getWorkspaces() {
    const res = await fetch(`${API_BASE_URL}/workspaces`);
    return handleResponse(res, "Failed to fetch workspaces");
}

export async function saveWorkspace(name, config) {
    const res = await fetch(`${API_BASE_URL}/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, config })
    });
    return handleResponse(res, "Failed to save workspace");
}

// Gamification
export async function getGameStatus() {
    const res = await fetch(`${API_BASE_URL}/game/status`);
    return handleResponse(res, "Failed to fetch game status");
}

export async function recordGameEvent(type, data = {}) {
    const res = await fetch(`${API_BASE_URL}/game/event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, data })
    });
    return handleResponse(res, "Failed to record game event");
}

// Factor Screener

// Intraday
export async function getIntraday(ticker, interval = "5m") {
    const res = await fetch(`${API_BASE_URL}/security/${ticker}/intraday?interval=${interval}`);
    return handleResponse(res, "Failed to fetch intraday data");
}

// Macro Impact
export async function getMacroImpact(ticker) {
    const res = await fetch(`${API_BASE_URL}/macro/impact?ticker=${ticker}`);
    return handleResponse(res, "Failed to fetch macro impact");
}

// Intraday Markets
export async function fetchIntradayMarketData(tickers, interval = "5m") {
    const res = await fetch(`${API_BASE_URL}/markets/intraday?tickers=${tickers}&interval=${interval}`);
    return handleResponse(res, "Failed to fetch intraday market data");
}

// Options Chain
export async function fetchOptionsChain(ticker) {
    const res = await fetch(`${API_BASE_URL}/options/${ticker}`);
    return handleResponse(res, "Failed to fetch options chain");
}

// --- PRICES API ---

export async function fetchPrices(symbol, interval = "1d", lookbackDays = 365) {
    const params = new URLSearchParams({
        interval,
        lookback_days: lookbackDays.toString()
    });
    const res = await fetch(`${API_BASE_URL}/prices/${symbol}?${params.toString()}`);
    return handleResponse(res, "Failed to fetch prices");
}

export async function fetchPricesBatch(tickers, interval = "1d", lookbackDays = 365) {
    const res = await fetch(`${API_BASE_URL}/prices/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            tickers,
            interval,
            lookback_days: lookbackDays
        })
    });
    const result = await handleResponse(res, "Failed to fetch batch prices");
    
    // Transform candle format {t, o, h, l, c, v} to {closes: [], dates: []} for stats functions
    const transformed = {};
    if (result?.data) {
        for (const [ticker, candles] of Object.entries(result.data)) {
            if (Array.isArray(candles) && candles.length > 0) {
                transformed[ticker] = {
                    closes: candles.map(c => c.c),
                    opens: candles.map(c => c.o),
                    highs: candles.map(c => c.h),
                    lows: candles.map(c => c.l),
                    volumes: candles.map(c => c.v),
                    dates: candles.map(c => c.t),
                    candles: candles
                };
            } else {
                transformed[ticker] = { closes: [], dates: [], candles: [] };
            }
        }
    }
    return transformed;
}

// --- QUOTES API ---

export async function fetchQuote(symbol, interval = "1d") {
    const params = new URLSearchParams({ interval });
    const res = await fetch(`${API_BASE_URL}/quotes/${symbol}?${params.toString()}`);
    return handleResponse(res, "Failed to fetch quote");
}

export async function fetchQuotesBatch(symbols, interval = "1d") {
    const res = await fetch(`${API_BASE_URL}/quotes/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols, interval })
    });
    return handleResponse(res, "Failed to fetch batch quotes");
}

// --- CLUSTER E: RESEARCH APIs ---

export async function fetchNarrative(marketProxy = "SPY", lookbackDays = 60) {
    const res = await fetch(`${API_BASE_URL}/research/e/narrative`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ market_proxy: marketProxy, lookback_days: lookbackDays })
    });
    return handleResponse(res, "Failed to fetch narrative");
}

export async function fetchRiskScore(lookbackDays = 252) {
    const res = await fetch(`${API_BASE_URL}/research/e/risk_score`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lookback_days: lookbackDays })
    });
    return handleResponse(res, "Failed to fetch risk score");
}

export async function fetchReplay(preset = "covid", assets = ["SPY"]) {
    const res = await fetch(`${API_BASE_URL}/research/e/replay`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "preset", preset, assets })
    });
    return handleResponse(res, "Failed to fetch replay data");
}

export async function fetchScan(pattern = "golden_cross", tickers = ["ALL"], limit = 50) {
    const res = await fetch(`${API_BASE_URL}/research/e/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pattern, tickers, limit })
    });
    return handleResponse(res, "Failed to scan patterns");
}

export async function fetchSharpeRadar(tickers = ["SPY", "QQQ"], horizons = [21, 63, 126, 252]) {
    const res = await fetch(`${API_BASE_URL}/research/e/sharpe_radar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers, horizons })
    });
    return handleResponse(res, "Failed to fetch Sharpe radar");
}

export async function fetchSpider(ref = "SPY", tickers = ["QQQ", "GLD"], window = 60) {
    const res = await fetch(`${API_BASE_URL}/research/e/spider`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ref, tickers: [ref, ...tickers], window })
    });
    return handleResponse(res, "Failed to fetch spider data");
}

export async function fetchFundamentals(ticker, compact = false) {
    const params = new URLSearchParams({ compact: String(compact) });
    const res = await fetch(`${API_BASE_URL}/fundamentals/${ticker}?${params.toString()}`);
    return handleResponse(res, "Failed to fetch fundamentals");
}

export async function fetchSentimentMarket(tickers = "SPY,QQQ,IWM", lookback = 30) {
    const params = new URLSearchParams({ tickers, lookback: String(lookback) });
    const res = await fetch(`${API_BASE_URL}/sentiment/market?${params.toString()}`);
    return handleResponse(res, "Failed to fetch market sentiment");
}

export async function fetchSentimentAsset(ticker, lookback = 90) {
    const params = new URLSearchParams({ ticker, lookback: String(lookback) });
    const res = await fetch(`${API_BASE_URL}/sentiment/asset?${params.toString()}`);
    return handleResponse(res, "Failed to fetch asset sentiment");
}

// =============================================================================
// FACTORS INTELLIGENCE
// =============================================================================

export async function fetchFactorsUniverse() {
    const res = await fetch(`${API_BASE_URL}/labs/factors/universe`);
    return handleResponse(res, "Failed to fetch factors universe");
}

export async function runFactorsIntelligence(ticker, factorSetId = "ff5", windowYears = 3, universeTickers = null) {
    const res = await fetch(`${API_BASE_URL}/labs/factors/intelligence/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ticker,
            factor_set_id: factorSetId,
            window_years: windowYears,
            universe_tickers: universeTickers
        })
    });
    return handleResponse(res, "Failed to run factors intelligence");
}

export async function runFactorMultiModel(ticker, factorSetId = "ff5_mom", windowYears = 3, zScore = 2.0, outlierHandling = true) {
    const res = await fetch(`${API_BASE_URL}/labs/factors/multi_model`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, factor_set_id: factorSetId, window_years: windowYears, z_score: zScore, outlier_handling: outlierHandling })
    });
    return handleResponse(res, "Failed to run factor multi-model");
}

export async function runFactorRollingExposures(ticker, factorSetId = "ff5", windowYears = 3, zScore = 2.0, outlierHandling = true) {
    const res = await fetch(`${API_BASE_URL}/labs/factors/rolling_exposures`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, factor_set_id: factorSetId, window_years: windowYears, z_score: zScore, outlier_handling: outlierHandling })
    });
    return handleResponse(res, "Failed to fetch rolling exposures");
}

export async function runFactorContribution(ticker, factorSetId = "ff5", windowYears = 3, zScore = 2.0, outlierHandling = true) {
    const res = await fetch(`${API_BASE_URL}/labs/factors/contribution`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, factor_set_id: factorSetId, window_years: windowYears, z_score: zScore, outlier_handling: outlierHandling })
    });
    return handleResponse(res, "Failed to run contribution analysis");
}

export async function runFactorShockReplay(ticker, factorSetId = "ff5", windowYears = 3) {
    const res = await fetch(`${API_BASE_URL}/labs/factors/shock_replay`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, factor_set_id: factorSetId, window_years: windowYears })
    });
    return handleResponse(res, "Failed to run shock replay");
}

export async function runFactorBacktest(universe, factor, windowYears = 5, rebalanceFreq = "M", zScore = 2.0, outlierHandling = true) {
    const res = await fetch(`${API_BASE_URL}/labs/factors/backtest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, factor, window_years: windowYears, rebalance_freq: rebalanceFreq, z_score: zScore, outlier_handling: outlierHandling })
    });
    return handleResponse(res, "Failed to run factor backtest");
}

export async function runFactorRotation(factorSetId = "ff5_mom") {
    const res = await fetch(`${API_BASE_URL}/labs/factors/rotation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ factor_set_id: factorSetId })
    });
    return handleResponse(res, "Failed to run factor rotation");
}

export async function runFactorRegimes(factorSetId = "ff5_mom") {
    const res = await fetch(`${API_BASE_URL}/labs/factors/regimes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ factor_set_id: factorSetId })
    });
    return handleResponse(res, "Failed to run factor regimes");
}

export async function runFactorOptimizer(factorSetId = "ff5_mom", targetVol = 0.15, zScore = 2.0, outlierHandling = true) {
    const res = await fetch(`${API_BASE_URL}/labs/factors/optimizer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ factor_set_id: factorSetId, target_vol: targetVol, z_score: zScore, outlier_handling: outlierHandling })
    });
    return handleResponse(res, "Failed to run factor optimizer");
}

// =============================================================================
// FACTORS V2 - Dormant until backend/app/api/factors_v2.py is wired in main.py
// =============================================================================

export async function fetchFactorsV2Features() {
    const res = await fetch(`${API_BASE_URL}/labs/factors/v2/features`);
    return handleResponse(res, "Failed to fetch Factors V2 feature metadata");
}

export async function searchFactorsV2Symbols(query = "", options = {}) {
    const params = new URLSearchParams({
        q: query,
        limit: String(options.limit || 25),
    });
    if (options.assetType) params.set("asset_type", options.assetType);
    const res = await fetch(`${API_BASE_URL}/labs/factors/v2/symbols?${params.toString()}`);
    return handleResponse(res, "Failed to search Factors V2 symbols");
}

export async function runFactorsV2Feature(featureId, payload = {}) {
    const normalized = String(featureId).replace("feature_", "").replace("feature-", "").padStart(2, "0");
    const res = await fetch(`${API_BASE_URL}/labs/factors/v2/feature/${normalized}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    return handleResponse(res, `Failed to run Factors V2 feature ${normalized}`);
}

export async function runFactorsV2All(payload = {}, featurePayloads = {}) {
    const res = await fetch(`${API_BASE_URL}/labs/factors/v2/run-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload, feature_payloads: featurePayloads })
    });
    return handleResponse(res, "Failed to run all Factors V2 features");
}

export async function runMlV2Feature(featureId, payload = {}) {
    const normalized = String(featureId).replace("feature_", "").replace("feature-", "").padStart(2, "0");
    const res = await fetch(`${API_BASE_URL}/ml/v2/features/${normalized}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    return handleResponse(res, `Failed to run ML V2 feature ${normalized}`);
}

export async function searchMlV2Symbols(query = "", options = {}) {
    const params = new URLSearchParams({ q: query, limit: String(options.limit || 25) });
    const res = await fetch(`${API_BASE_URL}/ml/v2/symbols?${params}`);
    return handleResponse(res, "Failed to search ML V2 symbols");
}

export async function runScreenerV2Feature(featureId, payload = {}) {
    const normalized = String(featureId).replace("feature_", "").replace("feature-", "").padStart(2, "0");
    const res = await fetch(`${API_BASE_URL}/screener-v2/run/${normalized}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload })
    });
    return handleResponse(res, `Failed to run Screener V2 feature ${normalized}`);
}

export async function searchScreenerV2Symbols(query = "", options = {}) {
    const params = new URLSearchParams({ q: query, limit: String(options.limit || 25) });
    return handleResponse(await fetch(`${API_BASE_URL}/screener-v2/symbols?${params}`), "Failed to search Screener V2 symbols");
}

// =============================================================================
// ALPHA MODELS - Momentum & Mean Reversion Intelligence
// =============================================================================

export async function fetchMomentum(symbols, benchmark = "SPY") {
    const params = new URLSearchParams({ symbols, benchmark });
    const res = await fetch(`${API_BASE_URL}/alpha/momentum?${params.toString()}`);
    return handleResponse(res, "Failed to fetch momentum scores");
}

export async function fetchMeanReversion(symbols, sensitivity = "conservative") {
    const params = new URLSearchParams({ symbols, sensitivity });
    const res = await fetch(`${API_BASE_URL}/alpha/mean_reversion?${params.toString()}`);
    return handleResponse(res, "Failed to fetch mean reversion scores");
}

export async function fetchAlertPreview(symbol) {
    const params = new URLSearchParams({ symbol });
    const res = await fetch(`${API_BASE_URL}/alpha/alerts/preview?${params.toString()}`);
    return handleResponse(res, "Failed to fetch alert preview");
}

// =============================================================================
// OPTIONS CALCULATOR - Multi-leg Strategy Analysis
// =============================================================================

/**
 * Calculate multi-leg options strategy payoff
 * @param {Array} legs - Array of leg objects with type, strike, quantity, iv, expiry_days
 * @param {number} spot - Current underlying price
 * @param {number} rate - Risk-free rate (default 0.05)
 * @returns {Object} Payoff curve, break-evens, max profit/loss, Greeks
 * 
 * Example:
 * calculateOptionsPayoff([
 *   { type: 'call', strike: 100, quantity: 1, iv: 0.25, expiry_days: 30 },
 *   { type: 'put', strike: 100, quantity: -1, iv: 0.25, expiry_days: 30 }
 * ], 100)
 */
export async function calculateOptionsPayoff(legs, spot, rate = 0.05) {
    const res = await fetch(`${API_BASE_URL}/options/calculator`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ legs, spot, rate })
    });
    return handleResponse(res, "Failed to calculate options payoff");
}
// --- RESEARCH E ---
export async function fetchDependencyMap(symbol) {
    const res = await fetch(`${API_BASE_URL}/research/e/dependency_map?symbol=${symbol}`);
    return handleResponse(res, "Failed to fetch dependency map");
}

// --- ML LABS GOD-MODE ---
// --- ML LABS GOD-MODE ---
export async function fetchMLStructural(universe = "sp500", lookback = 252, options = {}) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/structural`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, lookback, timeframe: options.timeframe || "1D" }),
        signal: options.signal
    });
    return handleResponse(res, "Failed to fetch ML structural DNA");
}

export async function fetchMLAlpha(universe = "sp500", lookback = 252, options = {}) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/alpha`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, lookback, timeframe: options.timeframe || "1D" }),
        signal: options.signal
    });
    return handleResponse(res, "Failed to fetch ML alpha ribbon");
}

export async function fetchMLRegime(universe = "sp500", options = {}) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/regime`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, timeframe: options.timeframe || "1D" }),
        signal: options.signal
    });
    return handleResponse(res, "Failed to fetch ML regime entropy");
}

export async function fetchMLStress(universe = "sp500", shock_pct = -0.03, options = {}) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/stress`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, shock_pct, timeframe: options.timeframe || "1D" }),
        signal: options.signal
    });
    return handleResponse(res, "Failed to fetch ML stress contagion");
}

export async function fetchMLPeak(universe = "sp500", options = {}) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/peak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, timeframe: options.timeframe || "1D" }),
        signal: options.signal
    });
    return handleResponse(res, "Failed to fetch Peak ML Intelligence");
}

export async function fetchMLMacro() {
    const res = await fetch(`${API_BASE_URL}/labs/ml/macro`);
    return handleResponse(res, "Failed to fetch ML Macro Pulse");
}
// --- ML V2 INTELLIGENCE (Merged) ---
export async function fetchML2Regime(universe, ticker = null, timeframe = "1D", lookback = 252) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/v2/regime`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, ticker, timeframe, lookback })
    });
    return handleResponse(res, "Failed to fetch ML v2 regime");
}

export async function fetchML2Anomalies(universe, ticker = null, timeframe = "1D", lookback = 252) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/v2/anomalies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, ticker, timeframe, lookback })
    });
    return handleResponse(res, "Failed to fetch ML v2 anomalies");
}

export async function fetchML2MonteCarlo(universe, ticker = null, timeframe = "1D", lookback = 252) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/v2/montecarlo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, ticker, timeframe, lookback })
    });
    return handleResponse(res, "Failed to fetch ML v2 monte carlo");
}

export async function fetchML2Liquidity(universe, ticker = null, timeframe = "1D", lookback = 252) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/v2/liquidity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, ticker, timeframe, lookback })
    });
    return handleResponse(res, "Failed to fetch ML v2 liquidity");
}

export async function fetchML2Valuation(universe, ticker = null, timeframe = "1D", lookback = 252) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/v2/valuation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, ticker, timeframe, lookback })
    });
    return handleResponse(res, "Failed to fetch ML v2 valuation");
}

export async function fetchML2GalaxyUniverse(universe, timeframe = "1D", lookback = 252) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/v2/galaxy/universe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, timeframe, lookback })
    });
    return handleResponse(res, "Failed to fetch ML v2 galaxy universe");
}

export async function fetchML2GalaxySimilar(universe, ticker = null, timeframe = "1D", lookback = 252) {
    const res = await fetch(`${API_BASE_URL}/labs/ml/v2/galaxy/similar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ universe, ticker, timeframe, lookback })
    });
    return handleResponse(res, "Failed to fetch ML v2 galaxy similar");
}
