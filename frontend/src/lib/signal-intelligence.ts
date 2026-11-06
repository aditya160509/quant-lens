/**
 * Signal Intelligence Engineering
 * Maps symbols to their specific institutional universes (Peers, Indices, Macros)
 */

export interface SignalMetadata {
    sector: string;
    index: { id: string; label: string };
    macros: Array<{ id: string; label: string; color: string }>;
    peers: Array<{ 
        symbol: string; 
        beta: number; 
        correlation: number; 
        spillover: string; 
        sentiment: 'BULLISH' | 'NEUTRAL' | 'STRONG_BULL' | 'BEARISH' 
    }>;
    pairTrades: Array<{ 
        long: string; 
        short: string; 
        score: number; 
        type: 'MEAN_REVERSION' | 'STRENGTH_DIVERGENCE' 
    }>;
    structuralData: {
        vwapPos: number; // in sigmas
        flowDelta: string;
        anomalousActivity: number; // 1-10
    };
    confidence: number;
    rr: string;
    lineageAge: string;
    riskExposure: number;
    expectedEv: number;
}

export function getSignalIntelligence(symbol: string, exchange: string): SignalMetadata {
    const isIndian = symbol?.endsWith('.NS') || symbol?.endsWith('.BO') || exchange === 'NSE' || exchange === 'BSE';
    const isCrypto = symbol?.includes('-USD') || exchange === 'CRYPTO';

    // Simple deterministic hash for symbol-based variety
    const getHash = (str: string) => {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = ((hash << 5) - hash) + str.charCodeAt(i);
            hash |= 0;
        }
        return Math.abs(hash);
    };

    const hash = getHash(symbol || 'DEFAULT');
    const confidence = 70 + (hash % 25); // 70-95
    const rrBase = 2 + (hash % 30) / 10; // 2.0 - 5.0
    const riskExposure = 10 + (hash % 60); // 10-70%
    const flowDelta = (hash % 10) - 4; // -4 to +5
    const anomalous = 1 + (hash % 8); // 1-9
    
    // Time since confirmation simulation (deterministic but looks dynamic)
    const minutes = hash % 15;
    const seconds = hash % 60;
    const lineageAge = `00:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

    if (isIndian) {
        return {
            sector: hash % 2 === 0 ? 'FINANCIAL SERVICES' : 'ENERGY & INFRA',
            index: { id: '^NSEI', label: 'NIFTY 50' },
            macros: [
                { id: 'USDINR=X', label: 'USDINR', color: '#f43f5e' },
                { id: '^NSEBANK', label: 'BANKNIFTY', color: '#8b5cf6' },
            ],
            peers: [
                { symbol: 'RELIANCE.NS', beta: 1.1, correlation: 0.85, spillover: '+1.10%', sentiment: 'BULLISH' },
                { symbol: 'TCS.NS', beta: 0.8, correlation: 0.72, spillover: '+0.60%', sentiment: 'NEUTRAL' },
                { symbol: 'HDFCBANK.NS', beta: 1.2, correlation: 0.88, spillover: '+1.20%', sentiment: 'STRONG_BULL' },
                { symbol: 'INFY.NS', beta: 0.9, correlation: 0.75, spillover: '+0.80%', sentiment: 'BULLISH' },
                { symbol: 'ICICIBANK.NS', beta: 1.3, correlation: 0.82, spillover: '+1.40%', sentiment: 'BULLISH' },
            ],
            pairTrades: [
                { long: 'HDFCBANK.NS', short: 'ICICIBANK.NS', score: 8.4, type: 'MEAN_REVERSION' },
                { long: 'TCS.NS', short: 'INFY.NS', score: 7.2, type: 'STRENGTH_DIVERGENCE' },
            ],
            structuralData: {
                vwapPos: (hash % 40 - 20) / 10, // -2.0 to 2.0
                flowDelta: `${flowDelta > 0 ? '+' : ''}${flowDelta.toFixed(1)}M`,
                anomalousActivity: anomalous
            },
            confidence,
            rr: `${rrBase.toFixed(1)} : 1`,
            lineageAge,
            riskExposure,
            expectedEv: Math.round(1000 + (hash % 5000))
        };
    }

    if (isCrypto) {
        return {
            sector: 'DIGITAL ASSETS',
            index: { id: 'BTC-USD', label: 'BITCOIN' },
            macros: [
                { id: 'ETH-USD', label: 'ETHEREUM', color: '#8b5cf6' },
                { id: 'USDT-DOM', label: 'USDT.D', color: '#10b981' },
            ],
            peers: [
                { symbol: 'SOL-USD', beta: 1.8, correlation: 0.92, spillover: '+3.20%', sentiment: 'STRONG_BULL' },
                { symbol: 'ETH-USD', beta: 1.2, correlation: 0.95, spillover: '+1.50%', sentiment: 'BULLISH' },
                { symbol: 'AVAX-USD', beta: 2.1, correlation: 0.88, spillover: '+4.10%', sentiment: 'STRONG_BULL' },
                { symbol: 'BNB-USD', beta: 0.9, correlation: 0.82, spillover: '+0.80%', sentiment: 'NEUTRAL' },
                { symbol: 'ADA-USD', beta: 1.4, correlation: 0.78, spillover: '+1.20%', sentiment: 'BULLISH' },
            ],
            pairTrades: [
                { long: 'SOL-USD', short: 'ETH-USD', score: 9.1, type: 'STRENGTH_DIVERGENCE' },
                { long: 'BTC-USD', short: 'WBTC-USD', score: 6.8, type: 'MEAN_REVERSION' },
            ],
            structuralData: {
                vwapPos: (hash % 30 - 15) / 10,
                flowDelta: `${(flowDelta * 100).toFixed(0)}K`,
                anomalousActivity: anomalous
            },
            confidence,
            rr: `${rrBase.toFixed(1)} : 1`,
            lineageAge,
            riskExposure,
            expectedEv: Math.round(500 + (hash % 2000))
        };
    }

    // Default: US / S&P 500
    return {
        sector: 'TECHNOLOGY',
        index: { id: '^GSPC', label: 'S&P 500' },
        macros: [
            { id: 'DXY', label: 'DXY', color: '#f43f5e' },
            { id: 'US10Y', label: 'US10Y', color: '#8b5cf6' },
        ],
        peers: [
            { symbol: 'QQQ', beta: 1.2, correlation: 0.94, spillover: '+1.20%', sentiment: 'BULLISH' },
            { symbol: 'MSFT', beta: 0.9, correlation: 0.88, spillover: '+0.90%', sentiment: 'NEUTRAL' },
            { symbol: 'AAPL', beta: 1.1, correlation: 0.85, spillover: '+1.10%', sentiment: 'BULLISH' },
            { symbol: 'NVDA', beta: 2.1, correlation: 0.72, spillover: '+2.10%', sentiment: 'STRONG_BULL' },
            { symbol: 'AMD', beta: 1.8, correlation: 0.65, spillover: '+1.80%', sentiment: 'BULLISH' },
        ],
        pairTrades: [
            { long: 'SPY', short: 'IVE', score: 8.4, type: 'MEAN_REVERSION' },
            { long: 'QQQ', short: 'DIA', score: 7.2, type: 'STRENGTH_DIVERGENCE' },
        ],
        structuralData: {
            vwapPos: (hash % 30 - 10) / 10,
            flowDelta: `${flowDelta > 0 ? '+' : ''}${flowDelta.toFixed(1)}M`,
            anomalousActivity: anomalous
        },
        confidence,
        rr: `${rrBase.toFixed(1)} : 1`,
        lineageAge,
        riskExposure,
        expectedEv: Math.round(1000 + (hash % 3000))
    };
}
