/**
 * Symbol Mapper
 * Maps TradingView symbols to universe symbols and provides normalization.
 */

import {
    ALLOWED_SYMBOLS,
    GROUP_MAP,
    isSecurityAllowed,
    isMarketAllowed
} from './loadUniverse';

// ===== Normalization =====

/**
 * Normalize a symbol to canonical form.
 * - Uppercase
 * - BRK.B -> BRK-B for US equities
 */
export function normalizeSymbol(symbol) {
    if (!symbol) return '';

    symbol = symbol.trim().toUpperCase();

    // Don't modify Indian or special symbols
    if (symbol.endsWith('.NS') || symbol.endsWith('.BO')) return symbol;
    if (symbol.startsWith('^')) return symbol;
    if (symbol.endsWith('=X') || symbol.includes('-USD')) return symbol;

    // For US equities, normalize class shares
    if (symbol.includes('.') && !symbol.endsWith('.NS') && !symbol.endsWith('.BO')) {
        const parts = symbol.split('.');
        if (parts.length === 2 && parts[1].length === 1) {
            const normalized = `${parts[0]}-${parts[1]}`;
            if (ALLOWED_SYMBOLS.has(normalized)) {
                return normalized;
            }
        }
    }

    return symbol;
}

// ===== TradingView Mapping =====

// Special index mappings
const INDEX_MAP = {
    'SPX': '^GSPC',
    'NIFTY': '^NSEI',
    'NIFTY50': '^NSEI',
    'SENSEX': '^BSESN',
    'VIX': '^VIX',
    'DJI': '^DJI',
    'IXIC': '^IXIC',
    'RUT': '^RUT',
};

/**
 * Map TradingView symbol to universe symbol.
 * 
 * @param {string} tvSymbol - Symbol from TradingView (e.g., "TCS", "AAPL")
 * @param {string} exchange - Exchange from TradingView (e.g., "NSE", "NASDAQ")
 * @returns {string|null} Universe symbol or null if not found
 */
export function mapTradingViewToUniverse(tvSymbol, exchange = '') {
    if (!tvSymbol) return null;

    tvSymbol = tvSymbol.trim().toUpperCase();
    exchange = exchange?.trim().toUpperCase() || '';

    // Parse "EXCHANGE:SYMBOL" format
    if (tvSymbol.includes(':')) {
        const [ex, sym] = tvSymbol.split(':');
        exchange = ex;
        tvSymbol = sym;
    }

    // Direct match first
    if (ALLOWED_SYMBOLS.has(tvSymbol)) {
        return tvSymbol;
    }

    // Exchange-based mapping
    if (exchange === 'NSE') {
        const candidate = `${tvSymbol}.NS`;
        if (ALLOWED_SYMBOLS.has(candidate)) return candidate;
    }

    if (exchange === 'BSE') {
        const candidate = `${tvSymbol}.BO`;
        if (ALLOWED_SYMBOLS.has(candidate)) return candidate;
    }

    // US exchanges
    if (['NASDAQ', 'NYSE', 'AMEX', 'ARCA'].includes(exchange)) {
        if (ALLOWED_SYMBOLS.has(tvSymbol)) return tvSymbol;
        const normalized = normalizeSymbol(tvSymbol);
        if (ALLOWED_SYMBOLS.has(normalized)) return normalized;
    }

    // Index mapping
    if (['INDEX', 'CBOE', 'SP', 'DJ'].includes(exchange)) {
        if (INDEX_MAP[tvSymbol]) return INDEX_MAP[tvSymbol];
        const candidate = `^${tvSymbol}`;
        if (ALLOWED_SYMBOLS.has(candidate)) return candidate;
    }

    // FX mapping
    if (['FX', 'OANDA', 'FOREX', 'FX_IDC'].includes(exchange)) {
        const candidate = `${tvSymbol}=X`;
        if (ALLOWED_SYMBOLS.has(candidate)) return candidate;
    }

    // Crypto mapping
    if (['BITSTAMP', 'COINBASE', 'BINANCE', 'CRYPTO'].includes(exchange)) {
        // Handle formats like BTCUSD -> BTC-USD
        if (!tvSymbol.includes('-') && tvSymbol.endsWith('USD')) {
            const base = tvSymbol.slice(0, -3);
            const candidate = `${base}-USD`;
            if (ALLOWED_SYMBOLS.has(candidate)) return candidate;
        }
        const candidate = `${tvSymbol}-USD`;
        if (ALLOWED_SYMBOLS.has(candidate)) return candidate;
    }

    // Fallback attempts
    const fallbacks = [
        `${tvSymbol}.NS`,
        `${tvSymbol}.BO`,
        `^${tvSymbol}`,
        `${tvSymbol}=X`,
        `${tvSymbol}-USD`,
        normalizeSymbol(tvSymbol),
    ];

    for (const candidate of fallbacks) {
        if (ALLOWED_SYMBOLS.has(candidate)) {
            return candidate;
        }
    }

    return null;
}

// ===== Symbol Info =====

/**
 * Get display info for a symbol.
 */
export function getSymbolInfo(symbol) {
    const group = GROUP_MAP.get(symbol) || 'other';

    let exchange, base;

    if (symbol.endsWith('.NS')) {
        exchange = 'NSE';
        base = symbol.slice(0, -3);
    } else if (symbol.endsWith('.BO')) {
        exchange = 'BSE';
        base = symbol.slice(0, -3);
    } else if (symbol.startsWith('^')) {
        exchange = 'INDEX';
        base = symbol.slice(1);
    } else if (symbol.endsWith('=F')) {
        exchange = 'COMMODITIES';
        base = symbol.slice(0, -2);
    } else if (symbol.endsWith('=X')) {
        exchange = 'FX';
        base = symbol.slice(0, -2);
    } else if (symbol.includes('-USD')) {
        exchange = 'CRYPTO';
        base = symbol.replace('-USD', '');
    } else {
        exchange = 'US';
        base = symbol;
    }

    return {
        symbol,
        base,
        exchange,
        group,
        display: `${base} • ${exchange}`,
        isUnknown: !ALLOWED_SYMBOLS.has(symbol)
    };
}


// ===== Mode Validation =====

/**
 * Validate symbol for a specific mode.
 * 
 * @param {string} symbol - Symbol to validate
 * @param {string} mode - "market" | "security" | "any"
 * @param {Object} options - { allowFxCrypto: boolean }
 * @returns {{ valid: boolean, error: string|null }}
 */
export function validateForMode(symbol, mode = 'any', options = {}) {
    // If it's a known symbol, do normal checks
    if (!ALLOWED_SYMBOLS.has(symbol)) {
        // For workspace mode, we allow anything as long as it's a string
        if (typeof symbol === 'string' && symbol.length > 0) {
           return { valid: true, error: null };
        }
        return { valid: false, error: 'Symbol not supported' };
    }


    if (mode === 'security') {
        if (!isSecurityAllowed(symbol)) {
            return {
                valid: false,
                error: 'This instrument is available only in the Markets page'
            };
        }
    } else if (mode === 'market') {
        if (!isMarketAllowed(symbol, options.allowFxCrypto)) {
            return {
                valid: false,
                error: 'This instrument is available only in the Security page'
            };
        }
    }

    return { valid: true, error: null };
}

// ===== Exchange Tag Color =====

export function getExchangeColor(exchange) {
    const colors = {
        NSE: '#4ade80',      // green
        BSE: '#f472b6',      // pink
        US: '#60a5fa',       // blue
        NASDAQ: '#60a5fa',
        NYSE: '#60a5fa',
        INDEX: '#fbbf24',    // yellow
        COMMODITIES: '#f59e0b', // amber
        FX: '#a78bfa',       // purple
        CRYPTO: '#f97316',   // orange
    };
    return colors[exchange] || '#9ca3af';
}

const symbolMapper = {
    normalizeSymbol,
    mapTradingViewToUniverse,
    getSymbolInfo,
    validateForMode,
    getExchangeColor,
};

export default symbolMapper;

