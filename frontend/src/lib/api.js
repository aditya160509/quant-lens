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
export async function fetchMonitorNews(region = "IN", k = 20) {
    const res = await fetch(`${API_BASE_URL}/monitor/news?region=${region}&k=${k}`);
    return handleResponse(res, "Failed to fetch monitor news");
}

export async function fetchMarketIntraday(ticker = "SPY", interval = "5m") {
    const params = new URLSearchParams({ ticker, interval });
    const res = await fetch(`${API_BASE_URL}/markets/intraday?${params.toString()}`);
    return handleResponse(res, "Failed to fetch intraday data");
}

// --- EARNINGS ---
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
export async function runScenario({ scenarioId, shockSize, customShocks }) {
    const res = await fetch(`${API_BASE_URL}/portfolio/scenarios`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_id: scenarioId, shock_size: shockSize, custom_shocks: customShocks })
    });
    return handleResponse(res, "Failed to run scenario");
}

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

export async function fetchFundamentals(ticker, compact = false) {
    const params = new URLSearchParams({ compact: String(compact) });
    const res = await fetch(`${API_BASE_URL}/fundamentals/${ticker}?${params.toString()}`);
    return handleResponse(res, "Failed to fetch fundamentals");
}

export async function fetchDependencyMap(symbol) {
    const res = await fetch(`${API_BASE_URL}/research/e/dependency_map?symbol=${symbol}`);
    return handleResponse(res, "Failed to fetch dependency map");
}

// --- ML LABS GOD-MODE ---
// --- ML LABS GOD-MODE ---
