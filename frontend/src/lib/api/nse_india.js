/**
 * NSE India Stock Market API Client
 * Features:
 * - FREE API - No keys needed!
 * - Rate limiting aware
 * - Fallback to yfinance when NSE fails
 * - Earnings/Financial data
 * 
 * Usage: Run NSE server first: npx stock-nse-india serve --port 3001
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

// Rate limiting state (client-side tracking)
let lastRequestTime = 0;
const MIN_REQUEST_INTERVAL = 350; // ~3 req/sec

// Simple request queue for rate limiting
async function rateLimitedFetch(url, options = {}) {
    const now = Date.now();
    const elapsed = now - lastRequestTime;
    
    if (elapsed < MIN_REQUEST_INTERVAL) {
        await new Promise(resolve => setTimeout(resolve, MIN_REQUEST_INTERVAL - elapsed));
    }
    
    lastRequestTime = Date.now();
    return fetch(url, options);
}

// Helper for handling API responses with fallback
async function handleResponse(res, errorMsg, fallback = null) {
    if (!res.ok) {
        const error = await res.text();
        console.error(`[NSE] ${errorMsg}: ${error}`);
        if (fallback !== null) {
            console.log('[NSE] Using fallback value');
            return fallback;
        }
        throw new Error(`${errorMsg}: ${error}`);
    }
    return res.json();
}

// ===================== HEALTH CHECK =====================

/**
 * Check if NSE API is available
 */
export async function isNseApiHealthy() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/nse/health`);
        const data = await res.json();
        return data.status === 'healthy';
    } catch {
        return false;
    }
}

// ===================== CORE STOCK DATA =====================

/**
 * Get all NSE stock symbols
 */
export async function getNseSymbols() {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/symbols`);
    return handleResponse(res, "Failed to fetch NSE symbols", []);
}

/**
 * Get equity details for a stock
 * @param {string} symbol - Stock symbol (e.g., 'RELIANCE', 'TCS')
 */
export async function getNseEquity(symbol) {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/equity/${symbol.toUpperCase()}`);
    return handleResponse(res, `Failed to fetch equity details for ${symbol}`);
}

/**
 * Get historical data for a stock
 * @param {string} symbol - Stock symbol
 * @param {number} days - Number of days (default 30)
 */
export async function getNseHistorical(symbol, days = 30) {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/equity/${symbol.toUpperCase()}/historical?days=${days}`);
    return handleResponse(res, `Failed to fetch historical data for ${symbol}`, null);
}

/**
 * Get intraday data for a stock
 * @param {string} symbol - Stock symbol
 */
export async function getNseIntraday(symbol) {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/equity/${symbol.toUpperCase()}/intraday`);
    return handleResponse(res, `Failed to fetch intraday data for ${symbol}`, null);
}

/**
 * Get options chain for a stock
 * @param {string} symbol - Stock symbol
 */
export async function getNseOptionsChain(symbol) {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/equity/${symbol.toUpperCase()}/options`);
    return handleResponse(res, `Failed to fetch options chain for ${symbol}`);
}

/**
 * Get corporate info for a stock (includes earnings/financial data)
 * @param {string} symbol - Stock symbol
 */
export async function getNseCorporateInfo(symbol) {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/equity/${symbol.toUpperCase()}/corporate`);
    return handleResponse(res, `Failed to fetch corporate info for ${symbol}`);
}

/**
 * Get trade info for a stock
 * @param {string} symbol - Stock symbol
 */
export async function getNseTradeInfo(symbol) {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/equity/${symbol.toUpperCase()}/trade-info`);
    return handleResponse(res, `Failed to fetch trade info for ${symbol}`);
}

// ===================== EARNINGS DATA =====================

/**
 * Get comprehensive earnings data for a stock
 * Includes: financial_results, board_meetings, dividends, shareholding
 * @param {string} symbol - Stock symbol
 */
export async function getNseEarnings(symbol) {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/equity/${symbol.toUpperCase()}/earnings`);
    return handleResponse(res, `Failed to fetch earnings for ${symbol}`);
}

/**
 * Get upcoming earnings dates for Nifty 50 or specified stocks
 * @param {number} limit - Number of stocks to check (default 20)
 * @param {string[]} symbols - Optional array of symbols
 */
export async function getNseUpcomingEarnings(limit = 20, symbols = null) {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (symbols && symbols.length > 0) {
        params.append('symbols', symbols.join(','));
    }
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/earnings/upcoming?${params}`);
    return handleResponse(res, "Failed to fetch upcoming earnings", { upcoming_earnings: [] });
}

/**
 * Get earnings history for a stock
 * @param {string} symbol - Stock symbol
 * @param {number} quarters - Number of quarters (default 8)
 */
export async function getNseEarningsHistory(symbol, quarters = 8) {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/earnings/history/${symbol.toUpperCase()}?quarters=${quarters}`);
    return handleResponse(res, `Failed to fetch earnings history for ${symbol}`);
}

// ===================== INDEX DATA =====================

/**
 * Get all market indices
 */
export async function getNseIndices() {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/indices`);
    return handleResponse(res, "Failed to fetch NSE indices", []);
}

/**
 * Get Nifty 50 data
 */
export async function getNifty50() {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/nifty50`);
    return handleResponse(res, "Failed to fetch Nifty 50 data");
}

/**
 * Get top gainers and losers
 * @param {string} index - Index name (default 'NIFTY 50')
 */
export async function getNseGainersLosers(index = 'NIFTY 50') {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/gainers-losers?index=${encodeURIComponent(index)}`);
    return handleResponse(res, "Failed to fetch gainers/losers", { gainers: [], losers: [] });
}

/**
 * Get most active stocks
 */
export async function getNseMostActive() {
    const res = await rateLimitedFetch(`${API_BASE_URL}/api/nse/most-active`);
    return handleResponse(res, "Failed to fetch most active stocks", []);
}

// ===================== BATCH OPERATIONS =====================

/**
 * Get multiple stocks data at once (with rate limiting)
 * @param {string[]} symbols - Array of stock symbols
 */
export async function getNseMultipleStocks(symbols) {
    const results = [];
    
    for (const symbol of symbols) {
        try {
            const data = await getNseEquity(symbol);
            results.push({ symbol, data, success: true });
        } catch (error) {
            results.push({ symbol, error: error.message, success: false });
        }
    }
    
    return results;
}

/**
 * Get earnings for multiple stocks (with rate limiting)
 * @param {string[]} symbols - Array of stock symbols
 */
export async function getNseMultipleEarnings(symbols) {
    const results = [];
    
    for (const symbol of symbols) {
        try {
            const data = await getNseEarnings(symbol);
            results.push({ symbol, data, success: true });
        } catch (error) {
            results.push({ symbol, error: error.message, success: false });
        }
    }
    
    return results;
}

/**
 * Get quick market overview (Nifty 50 + gainers/losers + most active)
 */
export async function getNseMarketOverview() {
    const [nifty, gainersLosers, mostActive] = await Promise.all([
        getNifty50().catch(() => null),
        getNseGainersLosers().catch(() => null),
        getNseMostActive().catch(() => null)
    ]);
    
    return {
        nifty50: nifty,
        gainersLosers: gainersLosers,
        mostActive: mostActive
    };
}

// ===================== HELPER FUNCTIONS =====================

/**
 * Check if a symbol is an Indian stock
 * @param {string} symbol - Stock symbol
 */
export function isIndianSymbol(symbol) {
    const upperSymbol = symbol.toUpperCase();
    const indianSuffixes = ['.NS', '.BO', '.NSE', '.BSE'];
    
    // Check for suffixes
    if (indianSuffixes.some(suffix => upperSymbol.endsWith(suffix))) {
        return true;
    }
    
    // Check for common Indian stocks
    return NIFTY_50_STOCKS.includes(upperSymbol.replace(/\.(NS|BO|NSE|BSE)$/i, ''));
}

/**
 * Clean symbol for NSE API (remove suffix)
 * @param {string} symbol - Stock symbol with optional suffix
 */
export function cleanNseSymbol(symbol) {
    return symbol.toUpperCase().replace(/\.(NS|BO|NSE|BSE)$/i, '');
}

/**
 * Format Indian currency
 * @param {number} value - Value in lakhs or crores
 * @param {string} unit - 'lakhs' or 'crores'
 */
export function formatIndianCurrency(value, unit = 'lakhs') {
    if (unit === 'crores') {
        return `₹${(value / 100).toFixed(2)} Cr`;
    }
    return `₹${value.toFixed(2)} L`;
}

// ===================== STOCK LISTS =====================

export const NIFTY_50_STOCKS = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'HINDUNILVR', 
    'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK', 'LT', 'BAJFINANCE',
    'AXISBANK', 'ASIANPAINT', 'MARUTI', 'TITAN', 'SUNPHARMA', 
    'ULTRACEMCO', 'WIPRO', 'NESTLEIND', 'HCLTECH', 'TECHM',
    'ONGC', 'NTPC', 'POWERGRID', 'TATAMOTORS', 'TATASTEEL', 
    'ADANIENT', 'ADANIPORTS', 'COALINDIA', 'JSWSTEEL', 'M&M',
    'BAJAJFINSV', 'HDFCLIFE', 'SBILIFE', 'DIVISLAB', 'DRREDDY',
    'CIPLA', 'APOLLOHOSP', 'EICHERMOT', 'HINDALCO', 'GRASIM',
    'BPCL', 'BRITANNIA', 'INDUSINDBK', 'TATACONSUM', 'HEROMOTOCO'
];

export const BANK_NIFTY_STOCKS = [
    'HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'SBIN',
    'INDUSINDBK', 'BANDHANBNK', 'FEDERALBNK', 'IDFCFIRSTB', 'PNB'
];

export const IT_STOCKS = [
    'TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM',
    'LTIM', 'MPHASIS', 'COFORGE', 'PERSISTENT', 'LTTS'
];

export const PHARMA_STOCKS = [
    'SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'APOLLOHOSP',
    'BIOCON', 'AUROPHARMA', 'LUPIN', 'TORNTPHARM', 'ALKEM'
];

// ===================== EARNINGS DATA STRUCTURE =====================
/**
 * NSE Earnings Data Structure Reference:
 * 
 * getNseEarnings(symbol) returns:
 * {
 *   symbol: string,
 *   financial_results: [{
 *     period_end: string (e.g., "30 Sep 2025")
 *     income: number (in lakhs)
 *     profit_before_tax: number
 *     profit_after_tax: number
 *     eps_diluted: number
 *     audited: boolean
 *     consolidated: boolean
 *     broadcast_date: string
 *   }],
 *   upcoming_board_meetings: [{
 *     date: string (e.g., "09-Oct-2025")
 *     purpose: string
 *     is_earnings: boolean
 *   }],
 *   dividends: [{
 *     ex_date: string
 *     purpose: string (e.g., "Dividend - Rs 5.5 Per Share")
 *   }],
 *   latest_shareholding: {
 *     date: string,
 *     pattern: [{ "Promoter & Promoter Group": "50.11" }, ...]
 *   }
 * }
 * 
 * getNseUpcomingEarnings() returns:
 * {
 *   upcoming_earnings: [{
 *     symbol: string,
 *     date: string,
 *     date_iso: string (YYYY-MM-DD),
 *     purpose: string,
 *     days_until: number
 *   }],
 *   checked_count: number,
 *   errors_count: number
 * }
 */

// ===================== FALLBACK WRAPPERS =====================
// These functions try NSE first, then fall back to yfinance

/**
 * Get equity details with fallback to yfinance
 * @param {string} symbol - Stock symbol
 * @param {function} yfinanceFallback - Function to call for yfinance data (e.g., fetchSecurityDetail)
 */
export async function getEquityWithFallback(symbol, yfinanceFallback) {
    const cleanSymbol = cleanNseSymbol(symbol);
    
    // Try NSE first for Indian stocks
    if (isIndianSymbol(symbol)) {
        try {
            const nseData = await getNseEquity(cleanSymbol);
            if (nseData && !nseData.error) {
                console.log(`[NSE] Got equity data for ${cleanSymbol}`);
                return { source: 'nse', data: nseData };
            }
        } catch (e) {
            console.warn(`[NSE] Failed, falling back to yfinance: ${e.message}`);
        }
    }
    
    // Fallback to yfinance
    try {
        const yfData = await yfinanceFallback(symbol);
        return { source: 'yfinance', data: yfData };
    } catch (e) {
        console.error(`[Fallback] Both NSE and yfinance failed for ${symbol}`);
        return { source: 'error', data: null, error: e.message };
    }
}

/**
 * Get trade info with fallback to yfinance liquidity data
 * @param {string} symbol - Stock symbol
 * @param {function} yfinanceFallback - Function to call for yfinance data (e.g., fetchLiquidity)
 */
export async function getTradeInfoWithFallback(symbol, yfinanceFallback) {
    const cleanSymbol = cleanNseSymbol(symbol);
    
    if (isIndianSymbol(symbol)) {
        try {
            const nseData = await getNseTradeInfo(cleanSymbol);
            if (nseData && !nseData.error) {
                console.log(`[NSE] Got trade info for ${cleanSymbol}`);
                return { source: 'nse', data: nseData };
            }
        } catch (e) {
            console.warn(`[NSE] Trade info failed, falling back: ${e.message}`);
        }
    }
    
    try {
        const yfData = await yfinanceFallback(symbol);
        return { source: 'yfinance', data: yfData };
    } catch (e) {
        return { source: 'error', data: null, error: e.message };
    }
}

/**
 * Get options chain with fallback to yfinance
 * @param {string} symbol - Stock symbol
 * @param {function} yfinanceFallback - Function to call for yfinance options (e.g., fetchOptionsChain)
 */
export async function getOptionsWithFallback(symbol, yfinanceFallback) {
    const cleanSymbol = cleanNseSymbol(symbol);
    
    if (isIndianSymbol(symbol)) {
        try {
            const nseData = await getNseOptionsChain(cleanSymbol);
            if (nseData && !nseData.error && nseData.records) {
                console.log(`[NSE] Got options chain for ${cleanSymbol}`);
                return { source: 'nse', data: nseData };
            }
        } catch (e) {
            console.warn(`[NSE] Options failed, falling back: ${e.message}`);
        }
    }
    
    try {
        const yfData = await yfinanceFallback(symbol);
        return { source: 'yfinance', data: yfData };
    } catch (e) {
        return { source: 'error', data: null, error: e.message };
    }
}

/**
 * Get earnings with fallback to yfinance
 * @param {string} symbol - Stock symbol 
 * @param {function} yfinanceFallback - Function to call for yfinance earnings (e.g., fetchEarningsHistory)
 */
export async function getEarningsWithFallback(symbol, yfinanceFallback) {
    const cleanSymbol = cleanNseSymbol(symbol);
    
    if (isIndianSymbol(symbol)) {
        try {
            const nseData = await getNseEarnings(cleanSymbol);
            if (nseData && !nseData.error) {
                console.log(`[NSE] Got earnings for ${cleanSymbol}`);
                return { source: 'nse', data: nseData };
            }
        } catch (e) {
            console.warn(`[NSE] Earnings failed, falling back: ${e.message}`);
        }
    }
    
    // Fallback to yfinance
    try {
        const yfData = await yfinanceFallback(symbol);
        // Transform yfinance earnings to match NSE format
        const transformed = {
            symbol: symbol,
            financial_results: yfData?.earnings?.map(e => ({
                period_end: e.date,
                income: e.revenue || 0,
                profit_after_tax: e.earnings || 0,
                eps_diluted: e.eps || 0,
                audited: true,
                eps_estimate: e.eps_estimate,
                eps_surprise: e.eps_surprise
            })) || [],
            upcoming_board_meetings: [],
            dividends: yfData?.dividends || [],
            latest_shareholding: null
        };
        return { source: 'yfinance', data: transformed };
    } catch (e) {
        return { source: 'error', data: null, error: e.message };
    }
}

/**
 * Get all stock data with automatic NSE/yfinance fallback
 * This is the main function to use for fetching comprehensive stock data
 * @param {string} symbol - Stock symbol
 * @param {object} yfinanceApis - Object with yfinance API functions
 * @param {function} yfinanceApis.fetchSecurityDetail
 * @param {function} yfinanceApis.fetchLiquidity  
 * @param {function} yfinanceApis.fetchOptionsChain
 * @param {function} yfinanceApis.fetchEarningsHistory
 */
export async function getStockDataWithFallback(symbol, yfinanceApis) {
    const isIndian = isIndianSymbol(symbol);
    const cleanSymbol = cleanNseSymbol(symbol);
    
    const results = {
        symbol: symbol,
        isIndian: isIndian,
        source: isIndian ? 'nse' : 'yfinance',
        nseAvailable: false,
        equity: null,
        tradeInfo: null,
        options: null,
        earnings: null,
        errors: []
    };
    
    // Check NSE health first for Indian stocks
    if (isIndian) {
        results.nseAvailable = await isNseApiHealthy();
    }
    
    // Fetch all data with fallbacks
    const [equityResult, tradeResult, optionsResult, earningsResult] = await Promise.allSettled([
        getEquityWithFallback(symbol, yfinanceApis.fetchSecurityDetail),
        getTradeInfoWithFallback(symbol, yfinanceApis.fetchLiquidity),
        getOptionsWithFallback(symbol, yfinanceApis.fetchOptionsChain),
        getEarningsWithFallback(symbol, yfinanceApis.fetchEarningsHistory)
    ]);
    
    if (equityResult.status === 'fulfilled') {
        results.equity = equityResult.value;
    } else {
        results.errors.push(`Equity: ${equityResult.reason}`);
    }
    
    if (tradeResult.status === 'fulfilled') {
        results.tradeInfo = tradeResult.value;
    } else {
        results.errors.push(`Trade: ${tradeResult.reason}`);
    }
    
    if (optionsResult.status === 'fulfilled') {
        results.options = optionsResult.value;
    } else {
        results.errors.push(`Options: ${optionsResult.reason}`);
    }
    
    if (earningsResult.status === 'fulfilled') {
        results.earnings = earningsResult.value;
    } else {
        results.errors.push(`Earnings: ${earningsResult.reason}`);
    }
    
    // Update source based on what was actually used
    if (results.equity?.source === 'yfinance' || !isIndian) {
        results.source = 'yfinance';
    }
    
    return results;
}
