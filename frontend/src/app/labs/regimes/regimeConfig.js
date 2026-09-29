// Fixed Regime Universes - Shared Configuration
// These universes NEVER mix tickers between US and India

export const REGIME_UNIVERSES = {
    US: {
        label: 'US Macro Regime',
        description: 'Global US-led macro state',
        color: '#3b82f6',  // Blue
        benchmark: 'SPY',
        nodes: ['QQQ', 'IWM', 'TLT', 'IEF', 'SHY', 'LQD', 'HYG', 'GLD', 'USO'],
        tickers: [
            'SPY', 'QQQ', 'IWM',           // Equity ETFs
            '^GSPC', '^IXIC',              // Major indices
            'TLT', 'IEF', 'SHY',           // Treasury ETFs
            'LQD', 'HYG',                  // Credit ETFs
            '^VIX',                        // Volatility
            'GLD', 'USO',                  // Commodities
            'EURUSD=X', 'JPY=X'            // FX
        ]
    },
    INDIA: {
        label: 'India Macro Regime',
        description: 'India domestic state with global spillovers',
        color: '#f97316',  // Orange
        benchmark: '^NSEI',
        // Using India-traded ETFs and key indices for proper regime detection
        nodes: ['NIFTYBEES.NS', 'BANKBEES.NS', 'GOLDBEES.NS', 'LIQUIDBEES.NS', '^BSESN'],
        tickers: [
            '^NSEI', '^BSESN',             // Major indices (NIFTY 50, SENSEX)
            'NIFTYBEES.NS', 'BANKBEES.NS', // Equity ETFs
            'GOLDBEES.NS',                 // Gold ETF
            'LIQUIDBEES.NS',               // Liquid fund (safe haven proxy)
            '^INDIAVIX',                   // India volatility
            'USDINR=X',                    // FX
            'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS' // Bellwether stocks
        ]
    }
};

export const THEME = {
    bg: '#0a0a0f',
    card: '#12121a',
    border: '#1e1e2e',
    text: '#e0e0e0',
    textMuted: '#888',
    accent: '#a855f7',
    danger: '#ef4444',
    warning: '#f59e0b',
    safe: '#10b981',
    us: '#3b82f6',
    india: '#f97316',
};

export const API_BASE = 'http://127.0.0.1:8000';
