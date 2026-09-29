/**
 * Intraday Data Adapter
 * Fetches and transforms intraday OHLCV data
 */

import type { OHLCVBar, SeriesData, SessionConfig, Timeframe } from '../types';

// =============================================================================
// DEFAULT SESSION CONFIGS
// =============================================================================

export const US_EQUITY_SESSION: SessionConfig = {
    timezone: 'America/New_York',
    preMarketStart: '04:00',
    regularStart: '09:30',
    regularEnd: '16:00',
    extendedEnd: '20:00',
};

export const INDIA_EQUITY_SESSION: SessionConfig = {
    timezone: 'Asia/Kolkata',
    regularStart: '09:15',
    regularEnd: '15:30',
};

// =============================================================================
// DATA ADAPTER
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE || '';

// Daily timeframes that need different API endpoint
const DAILY_TIMEFRAMES = ['1d', '3mo', '6mo', '1y', '2y', '5y'];

export function isDailyTimeframe(timeframe: string): boolean {
    return DAILY_TIMEFRAMES.includes(timeframe.toLowerCase());
}

// Map period to API period parameter
function getPeriodForTimeframe(timeframe: string): string {
    const tf = timeframe.toLowerCase();
    switch(tf) {
        case '3mo': return '3mo';
        case '6mo': return '6mo';
        case '1y': return '1y';
        case '2y': return '2y';
        case '5y': return '5y';
        default: return '1y';
    }
}

export async function getSeries(
    symbol: string,
    timeframe: Timeframe,
    sessionConfig: SessionConfig = US_EQUITY_SESSION
): Promise<SeriesData> {
    try {
        // Determine the appropriate period and interval for the API
        let interval = timeframe;
        let period: string;
        
        // Map timeframe to appropriate period
        switch(timeframe) {
            case '1m':
                period = '7d';
                break;
            case '5m':
            case '15m':
            case '30m':
            case '1h':
                period = '60d';
                break;
            case '3mo':
                period = '3mo';
                interval = '1d';
                break;
            case '6mo':
                period = '6mo';
                interval = '1d';
                break;
            case '1y':
                period = '2y'; // Fetch extra context for indicators (SMA200 etc)
                interval = '1d';
                break;
            case '2y':
                period = '5y';
                interval = '1d';
                break;
            case '5y':
                period = 'max';
                interval = '1d';
                break;
            default:
                period = '1y';
                interval = '1d';
        }
        
        // Normalize symbol (e.g., BTC/USD -> BTC-USD for Yahoo compatibility)
        const normalizedSymbol = symbol.replace('/', '-');
        
        // Use the /api/prices endpoint which works for all intervals and Indian stocks
        const url = `${API_BASE}/api/prices/${encodeURIComponent(normalizedSymbol)}?interval=${interval}&period=${period}`;
        console.log(`[DataAdapter] Fetching: ${url}`);
        
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Failed to fetch data: ${response.statusText}`);
        }

        const data = await response.json();
        
        // Transform API response (candles format: {t, o, h, l, c, v})
        const bars: OHLCVBar[] = (data.candles || []).map((candle: any) => ({
            timestamp: new Date(candle.t).getTime(),
            open: candle.o,
            high: candle.h,
            low: candle.l,
            close: candle.c,
            volume: candle.v || 0,
        }));

        // Detect Indian session
        const isIndian = symbol.endsWith('.NS') || symbol.endsWith('.BO');
        const session = isIndian ? INDIA_EQUITY_SESSION : sessionConfig;

        return {
            symbol,
            timeframe,
            bars,
            session,
            previousClose: bars.length > 1 ? bars[bars.length - 2].close : undefined,
        };
    } catch (error) {
        console.error('Data adapter error:', error);
        throw error;
    }
}

// Daily data fetcher - uses security/detail endpoint
export async function getSeriesDaily(
    symbol: string,
    timeframe: Timeframe,
    sessionConfig: SessionConfig = US_EQUITY_SESSION
): Promise<SeriesData> {
    try {
        const period = getPeriodForTimeframe(timeframe);
        // Normalize symbol
        const normalizedSymbol = symbol.replace('/', '-');
        
        // Note: Backend expects 'symbol' not 'ticker'
        const url = `${API_BASE}/api/security/detail?symbol=${encodeURIComponent(normalizedSymbol)}&period=${period}&interval=1d`;
        console.log(`[DataAdapter] Fetching daily: ${url}`);
        
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Failed to fetch daily data: ${response.statusText}`);
        }

        const data = await response.json();

        // Transform daily response - backend returns price.dates[], price.open[], etc.
        const priceData = data.price || {};
        const dates = priceData.dates || [];
        
        const bars: OHLCVBar[] = dates.map((date: string, i: number) => ({
            timestamp: new Date(date).getTime(),
            open: priceData.open?.[i] ?? priceData.close?.[i] ?? 0,
            high: priceData.high?.[i] ?? priceData.close?.[i] ?? 0,
            low: priceData.low?.[i] ?? priceData.close?.[i] ?? 0,
            close: priceData.close?.[i] ?? 0,
            volume: priceData.volume?.[i] ?? 0,
        }));

        return {
            symbol,
            timeframe,
            bars,
            session: sessionConfig,
            previousClose: data.previousClose || data.previous_close,
        };
    } catch (error) {
        console.error('Daily data adapter error:', error);
        throw error;
    }
}

// =============================================================================
// MOCK DATA FOR DEVELOPMENT
// =============================================================================

export function generateMockBars(count: number = 100): OHLCVBar[] {
    const bars: OHLCVBar[] = [];
    const now = Date.now();
    const interval = 5 * 60 * 1000; // 5 minutes
    let price = 450 + Math.random() * 50;

    for (let i = count - 1; i >= 0; i--) {
        const timestamp = now - i * interval;
        const change = (Math.random() - 0.5) * 2;
        const open = price;
        const close = price + change;
        const high = Math.max(open, close) + Math.random() * 0.5;
        const low = Math.min(open, close) - Math.random() * 0.5;
        const volume = Math.floor(100000 + Math.random() * 500000);

        bars.push({
            timestamp,
            open,
            high,
            low,
            close,
            volume,
        });

        price = close;
    }

    return bars;
}

export function getMockSeries(
    symbol: string,
    timeframe: Timeframe
): SeriesData {
    return {
        symbol,
        timeframe,
        bars: generateMockBars(200),
        session: US_EQUITY_SESSION,
        previousClose: 448.5,
    };
}

// =============================================================================
// DATA TRANSFORMERS
// =============================================================================

/**
 * Convert regular OHLCV to Heikin Ashi
 */
export function toHeikinAshi(bars: OHLCVBar[]): OHLCVBar[] {
    if (bars.length === 0) return [];

    const result: OHLCVBar[] = [];

    for (let i = 0; i < bars.length; i++) {
        const bar = bars[i];
        const prevHA = result[i - 1];

        const haClose = (bar.open + bar.high + bar.low + bar.close) / 4;
        const haOpen = prevHA
            ? (prevHA.open + prevHA.close) / 2
            : (bar.open + bar.close) / 2;
        const haHigh = Math.max(bar.high, haOpen, haClose);
        const haLow = Math.min(bar.low, haOpen, haClose);

        result.push({
            timestamp: bar.timestamp,
            open: haOpen,
            high: haHigh,
            low: haLow,
            close: haClose,
            volume: bar.volume,
        });
    }

    return result;
}

/**
 * Convert to Renko bricks
 */
export function toRenko(bars: OHLCVBar[], boxSize: number): OHLCVBar[] {
    if (bars.length === 0 || boxSize <= 0) return [];

    const bricks: OHLCVBar[] = [];
    let currentPrice = Math.floor(bars[0].close / boxSize) * boxSize;

    for (const bar of bars) {
        const close = bar.close;

        while (close >= currentPrice + boxSize) {
            // Bullish brick
            bricks.push({
                timestamp: bar.timestamp,
                open: currentPrice,
                high: currentPrice + boxSize,
                low: currentPrice,
                close: currentPrice + boxSize,
                volume: bar.volume,
            });
            currentPrice += boxSize;
        }

        while (close <= currentPrice - boxSize) {
            // Bearish brick
            bricks.push({
                timestamp: bar.timestamp,
                open: currentPrice,
                high: currentPrice,
                low: currentPrice - boxSize,
                close: currentPrice - boxSize,
                volume: bar.volume,
            });
            currentPrice -= boxSize;
        }
    }

    return bricks;
}

/**
 * Convert to Range Bars
 */
export function toRangeBars(bars: OHLCVBar[], rangeSize: number): OHLCVBar[] {
    if (bars.length === 0 || rangeSize <= 0) return [];

    const result: OHLCVBar[] = [];
    let current: OHLCVBar | null = null;

    for (const bar of bars) {
        if (!current) {
            current = { ...bar };
            continue;
        }

        // Check if current bar exceeds range
        const range = current.high - current.low;

        if (range >= rangeSize) {
            // Close current bar and start new one
            result.push(current);
            current = { ...bar };
        } else {
            // Update current bar
            current.high = Math.max(current.high, bar.high);
            current.low = Math.min(current.low, bar.low);
            current.close = bar.close;
            current.volume += bar.volume;
        }
    }

    if (current) {
        result.push(current);
    }

    return result;
}

/**
 * Convert to Kagi chart
 * Kagi charts show trend reversals based on a reversal amount
 */
export function toKagi(bars: OHLCVBar[], reversalAmount: number): OHLCVBar[] {
    if (bars.length === 0 || reversalAmount <= 0) return [];

    const result: OHLCVBar[] = [];
    let direction: 'up' | 'down' = 'up';
    let lastTurn = bars[0].close;
    let lineStart = bars[0].close;

    for (const bar of bars) {
        const close = bar.close;
        
        if (direction === 'up') {
            if (close >= lastTurn) {
                // Continue up
                lastTurn = close;
            } else if (lastTurn - close >= reversalAmount) {
                // Reversal down
                result.push({
                    timestamp: bar.timestamp,
                    open: lineStart,
                    high: lastTurn,
                    low: lineStart,
                    close: lastTurn,
                    volume: bar.volume,
                });
                direction = 'down';
                lineStart = lastTurn;
                lastTurn = close;
            }
        } else {
            if (close <= lastTurn) {
                // Continue down
                lastTurn = close;
            } else if (close - lastTurn >= reversalAmount) {
                // Reversal up
                result.push({
                    timestamp: bar.timestamp,
                    open: lineStart,
                    high: lineStart,
                    low: lastTurn,
                    close: lastTurn,
                    volume: bar.volume,
                });
                direction = 'up';
                lineStart = lastTurn;
                lastTurn = close;
            }
        }
    }

    // Push final segment
    if (bars.length > 0) {
        const lastBar = bars[bars.length - 1];
        result.push({
            timestamp: lastBar.timestamp,
            open: lineStart,
            high: direction === 'up' ? lastTurn : lineStart,
            low: direction === 'down' ? lastTurn : lineStart,
            close: lastTurn,
            volume: lastBar.volume,
        });
    }

    return result;
}

/**
 * Convert to Point & Figure chart
 * X columns represent rising prices, O columns represent falling prices
 */
export function toPointAndFigure(bars: OHLCVBar[], boxSize: number, reversalBoxes: number = 3): OHLCVBar[] {
    if (bars.length === 0 || boxSize <= 0) return [];

    const result: OHLCVBar[] = [];
    let column: 'X' | 'O' = 'X';  // X = up, O = down
    let columnLow = Math.floor(bars[0].low / boxSize) * boxSize;
    let columnHigh = columnLow + boxSize;

    for (const bar of bars) {
        const high = bar.high;
        const low = bar.low;

        if (column === 'X') {
            // In uptrend column
            if (high >= columnHigh + boxSize) {
                // Extend column up
                columnHigh = Math.floor(high / boxSize) * boxSize;
            } else if (low <= columnHigh - (reversalBoxes * boxSize)) {
                // Reversal: create new O column
                result.push({
                    timestamp: bar.timestamp,
                    open: columnLow,
                    high: columnHigh,
                    low: columnLow,
                    close: columnHigh,
                    volume: bar.volume,
                });
                column = 'O';
                columnLow = Math.floor(low / boxSize) * boxSize;
                columnHigh = columnHigh - boxSize;
            }
        } else {
            // In downtrend column
            if (low <= columnLow - boxSize) {
                // Extend column down
                columnLow = Math.floor(low / boxSize) * boxSize;
            } else if (high >= columnLow + (reversalBoxes * boxSize)) {
                // Reversal: create new X column
                result.push({
                    timestamp: bar.timestamp,
                    open: columnHigh,
                    high: columnHigh,
                    low: columnLow,
                    close: columnLow,
                    volume: bar.volume,
                });
                column = 'X';
                columnHigh = Math.floor(high / boxSize) * boxSize;
                columnLow = columnLow + boxSize;
            }
        }
    }

    // Push final column
    if (bars.length > 0) {
        const lastBar = bars[bars.length - 1];
        result.push({
            timestamp: lastBar.timestamp,
            open: column === 'X' ? columnLow : columnHigh,
            high: columnHigh,
            low: columnLow,
            close: column === 'X' ? columnHigh : columnLow,
            volume: lastBar.volume,
        });
    }

    return result;
}

/**
 * Convert to Line Break chart
 * New lines are drawn when price breaks the previous line's high or low
 */
export function toLineBreak(bars: OHLCVBar[], lineCount: number = 3): OHLCVBar[] {
    if (bars.length === 0 || lineCount <= 0) return [];

    const lines: OHLCVBar[] = [];
    
    // First bar starts the first line
    lines.push({
        timestamp: bars[0].timestamp,
        open: bars[0].open,
        high: bars[0].close,
        low: bars[0].open,
        close: bars[0].close,
        volume: bars[0].volume,
    });

    for (let i = 1; i < bars.length; i++) {
        const bar = bars[i];
        const lastLine = lines[lines.length - 1];
        const isLastLineUp = lastLine.close > lastLine.open;

        // Get lookback lines for reversal check
        const lookbackStart = Math.max(0, lines.length - lineCount);
        const lookbackLines = lines.slice(lookbackStart);
        const lookbackHigh = Math.max(...lookbackLines.map(l => Math.max(l.open, l.close)));
        const lookbackLow = Math.min(...lookbackLines.map(l => Math.min(l.open, l.close)));

        if (isLastLineUp) {
            // Last line was bullish
            if (bar.close > lookbackHigh) {
                // Continue up - new bullish line
                lines.push({
                    timestamp: bar.timestamp,
                    open: lastLine.close,
                    high: bar.close,
                    low: lastLine.close,
                    close: bar.close,
                    volume: bar.volume,
                });
            } else if (bar.close < lookbackLow) {
                // Reversal - new bearish line
                lines.push({
                    timestamp: bar.timestamp,
                    open: lastLine.close,
                    high: lastLine.close,
                    low: bar.close,
                    close: bar.close,
                    volume: bar.volume,
                });
            }
        } else {
            // Last line was bearish
            if (bar.close < lookbackLow) {
                // Continue down - new bearish line
                lines.push({
                    timestamp: bar.timestamp,
                    open: lastLine.close,
                    high: lastLine.close,
                    low: bar.close,
                    close: bar.close,
                    volume: bar.volume,
                });
            } else if (bar.close > lookbackHigh) {
                // Reversal - new bullish line
                lines.push({
                    timestamp: bar.timestamp,
                    open: lastLine.close,
                    high: bar.close,
                    low: lastLine.close,
                    close: bar.close,
                    volume: bar.volume,
                });
            }
        }
    }

    return lines;
}

/**
 * Get baseline price (typically VWAP or SMA)
 */
export function calculateBaseline(bars: OHLCVBar[]): number {
    if (bars.length === 0) return 0;
    
    // Use VWAP as baseline
    let cumTypicalPriceVolume = 0;
    let cumVolume = 0;
    
    for (const bar of bars) {
        const typicalPrice = (bar.high + bar.low + bar.close) / 3;
        cumTypicalPriceVolume += typicalPrice * bar.volume;
        cumVolume += bar.volume;
    }
    
    return cumVolume > 0 ? cumTypicalPriceVolume / cumVolume : bars[bars.length - 1].close;
}
