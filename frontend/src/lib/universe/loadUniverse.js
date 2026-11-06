/**
 * Universe Loader
 * Loads and provides access to the master universe.
 */

import universesData from '@/data/universes/universes.json';

// ===== Build Lookup Structures =====

const UNIVERSE = universesData;

// Flatten all symbols into a Set
export const ALLOWED_SYMBOLS = new Set();
export const GROUP_MAP = new Map();

for (const [group, symbols] of Object.entries(UNIVERSE)) {
    for (const symbol of symbols) {
        ALLOWED_SYMBOLS.add(symbol);
        GROUP_MAP.set(symbol, group);
    }
}

// ===== Group Constants =====

export const SECURITY_GROUPS = new Set(['india_nse', 'india_bse', 'us_equities']);
export const MARKET_GROUPS = new Set(['indices', 'etfs', 'commodities']);
export const MARKET_OPTIONAL_GROUPS = new Set(['fx', 'crypto']);

// Build group sets
export const SECURITY_SET = new Set();
export const MARKET_SET = new Set();
export const MARKET_OPTIONAL_SET = new Set();

for (const group of SECURITY_GROUPS) {
    (UNIVERSE[group] || []).forEach(s => SECURITY_SET.add(s));
}

for (const group of MARKET_GROUPS) {
    (UNIVERSE[group] || []).forEach(s => MARKET_SET.add(s));
}

for (const group of MARKET_OPTIONAL_GROUPS) {
    (UNIVERSE[group] || []).forEach(s => MARKET_OPTIONAL_SET.add(s));
}

// ===== Limits =====

export const LIMITS = {
    intraday_max: 10,
    correlation_max: 50,
    pca_max: 40,
    beta_max: 100,
    batch_max: 200,
    min_history_days: 365,
};

// ===== Access Functions =====

export function getUniverse(group = null) {
    if (group) {
        return UNIVERSE[group] || [];
    }
    return Array.from(ALLOWED_SYMBOLS);
}

export function getGroup(symbol) {
    return GROUP_MAP.get(symbol) || null;
}

export function isValidSymbol(symbol) {
    return ALLOWED_SYMBOLS.has(symbol);
}

export function isSecurityAllowed(symbol) {
    return SECURITY_SET.has(symbol);
}

export function isMarketAllowed(symbol, allowFxCrypto = false) {
    if (MARKET_SET.has(symbol)) return true;
    if (allowFxCrypto && MARKET_OPTIONAL_SET.has(symbol)) return true;
    return false;
}

export function getSecurityUniverse() {
    return Array.from(SECURITY_SET);
}

export function getMarketUniverse(includeFxCrypto = false) {
    const result = Array.from(MARKET_SET);
    if (includeFxCrypto) {
        result.push(...MARKET_OPTIONAL_SET);
    }
    return result;
}

export function getStats() {
    return {
        total: ALLOWED_SYMBOLS.size,
        security: SECURITY_SET.size,
        market: MARKET_SET.size,
        groups: Object.fromEntries(
            Object.entries(UNIVERSE).map(([k, v]) => [k, v.length])
        ),
    };
}

const universeLoader = {
    ALLOWED_SYMBOLS,
    GROUP_MAP,
    SECURITY_SET,
    MARKET_SET,
    LIMITS,
    getUniverse,
    getGroup,
    isValidSymbol,
    isSecurityAllowed,
    isMarketAllowed,
    getSecurityUniverse,
    getMarketUniverse,
    getStats,
};

export default universeLoader;
