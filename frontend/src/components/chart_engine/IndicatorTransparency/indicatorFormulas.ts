/**
 * Indicator Math Transparency
 * 
 * Per tradefeature.md §19:
 * - Formula display on hover
 * - Input values tooltip  
 * - Lag warnings
 * - Misuse warnings
 */

// =============================================================================
// TYPES
// =============================================================================

export interface IndicatorFormula {
    id: string;
    name: string;
    formula: string;
    formulaLatex?: string;
    parameters: ParameterInfo[];
    lagBars: number;
    lagDescription: string;
    limitations: string[];
    recommendedTimeframes: string[];
    commonMisuses: string[];
}

export interface ParameterInfo {
    name: string;
    description: string;
    defaultValue: number | string;
    type: 'number' | 'string' | 'select';
    options?: string[];
}

export interface IndicatorValues {
    indicatorId: string;
    currentValue: number;
    inputValues: Record<string, number | number[]>;
    computationSteps?: string[];
}

// =============================================================================
// FORMULA DEFINITIONS
// =============================================================================

export const INDICATOR_FORMULAS: Record<string, IndicatorFormula> = {
    sma: {
        id: 'sma',
        name: 'Simple Moving Average',
        formula: 'SMA = (P₁ + P₂ + ... + Pₙ) / n',
        formulaLatex: '\\text{SMA} = \\frac{\\sum_{i=1}^{n} P_i}{n}',
        parameters: [
            { name: 'period', description: 'Number of periods to average', defaultValue: 20, type: 'number' }
        ],
        lagBars: 10, // half of default period
        lagDescription: 'SMA lags by approximately half its period (~10 bars for SMA 20)',
        limitations: [
            'Gives equal weight to all prices, may be slow to react',
            'Does not adapt to volatility changes',
            'May generate late signals in trending markets'
        ],
        recommendedTimeframes: ['1h', '4h', '1d'],
        commonMisuses: [
            'Using very short periods on low timeframes (too noisy)',
            'Using as sole entry/exit signal (prone to whipsaws)'
        ]
    },
    
    ema: {
        id: 'ema',
        name: 'Exponential Moving Average',
        formula: 'EMA = Price × k + EMA(prev) × (1-k), where k = 2/(n+1)',
        formulaLatex: '\\text{EMA}_t = P_t \\times k + \\text{EMA}_{t-1} \\times (1-k)',
        parameters: [
            { name: 'period', description: 'Smoothing period', defaultValue: 20, type: 'number' }
        ],
        lagBars: 7, // less than SMA
        lagDescription: 'EMA has less lag than SMA due to higher weight on recent prices',
        limitations: [
            'More sensitive to recent price spikes',
            'Can overshoot during volatile periods',
            'Still a lagging indicator'
        ],
        recommendedTimeframes: ['5m', '15m', '1h', '4h'],
        commonMisuses: [
            'Expecting EMA to predict price direction',
            'Ignoring that EMA is still based on past data'
        ]
    },
    
    rsi: {
        id: 'rsi',
        name: 'Relative Strength Index',
        formula: 'RSI = 100 - (100 / (1 + RS)), RS = Avg Gain / Avg Loss',
        formulaLatex: '\\text{RSI} = 100 - \\frac{100}{1 + \\frac{\\text{Avg Gain}}{\\text{Avg Loss}}}',
        parameters: [
            { name: 'period', description: 'Lookback period', defaultValue: 14, type: 'number' }
        ],
        lagBars: 7,
        lagDescription: 'RSI responds to price changes with approximately half-period lag',
        limitations: [
            'Can stay overbought/oversold for extended periods in strong trends',
            'Range-bound indicator (0-100) - cannot show trend strength',
            'Divergences can persist before reversals'
        ],
        recommendedTimeframes: ['15m', '1h', '4h', '1d'],
        commonMisuses: [
            'Blindly buying when RSI < 30 without trend context',
            'Ignoring that RSI > 70 can persist in bull markets',
            'Using 14 period on 1m charts (covers only 14 minutes)'
        ]
    },
    
    macd: {
        id: 'macd',
        name: 'MACD',
        formula: 'MACD = EMA(12) - EMA(26), Signal = EMA(9) of MACD',
        formulaLatex: '\\text{MACD} = \\text{EMA}_{12} - \\text{EMA}_{26}',
        parameters: [
            { name: 'fast', description: 'Fast EMA period', defaultValue: 12, type: 'number' },
            { name: 'slow', description: 'Slow EMA period', defaultValue: 26, type: 'number' },
            { name: 'signal', description: 'Signal line period', defaultValue: 9, type: 'number' }
        ],
        lagBars: 13, // half of slow period
        lagDescription: 'MACD inherits lag from its component EMAs (~13 bars with default settings)',
        limitations: [
            'Lagging indicator - signals come after price moves',
            'Crossovers can be late in fast-moving markets',
            'No defined overbought/oversold levels'
        ],
        recommendedTimeframes: ['1h', '4h', '1d'],
        commonMisuses: [
            'Using as primary entry signal without price action confirmation',
            'Ignoring the magnitude of crossovers',
            'Trading every crossover in choppy markets'
        ]
    },
    
    bollinger: {
        id: 'bollinger',
        name: 'Bollinger Bands',
        formula: 'Middle = SMA(n), Upper = SMA + k×σ, Lower = SMA - k×σ',
        formulaLatex: '\\text{Upper} = \\text{SMA} + k \\times \\sigma, \\text{Lower} = \\text{SMA} - k \\times \\sigma',
        parameters: [
            { name: 'period', description: 'SMA period', defaultValue: 20, type: 'number' },
            { name: 'stdDev', description: 'Standard deviation multiplier', defaultValue: 2, type: 'number' }
        ],
        lagBars: 10,
        lagDescription: 'Bands lag due to SMA calculation and backward-looking volatility',
        limitations: [
            'Bands widen after volatility, not before',
            'Touch of bands does not guarantee reversal',
            'Assumes normal distribution of returns'
        ],
        recommendedTimeframes: ['1h', '4h', '1d'],
        commonMisuses: [
            'Assuming price always reverts to middle band',
            'Selling at upper band in strong uptrends',
            'Using same settings across all markets'
        ]
    },
    
    atr: {
        id: 'atr',
        name: 'Average True Range',
        formula: 'TR = max(High-Low, |High-Close(prev)|, |Low-Close(prev)|), ATR = SMA(TR, n)',
        formulaLatex: '\\text{ATR} = \\frac{1}{n} \\sum_{i=1}^{n} \\text{TR}_i',
        parameters: [
            { name: 'period', description: 'Averaging period', defaultValue: 14, type: 'number' }
        ],
        lagBars: 7,
        lagDescription: 'ATR smooths volatility over the lookback period',
        limitations: [
            'Does not indicate direction, only magnitude',
            'Past volatility may not reflect future volatility',
            'Can spike during gaps'
        ],
        recommendedTimeframes: ['5m', '15m', '1h', '4h', '1d'],
        commonMisuses: [
            'Using ATR value from different timeframe without adjustment',
            'Setting stop-loss exactly 1 ATR without buffer'
        ]
    },
    
    vwap: {
        id: 'vwap',
        name: 'Volume Weighted Average Price',
        formula: 'VWAP = Σ(Typical Price × Volume) / Σ(Volume)',
        formulaLatex: '\\text{VWAP} = \\frac{\\sum (P_{typical} \\times V)}{\\sum V}',
        parameters: [],
        lagBars: 0,
        lagDescription: 'VWAP includes all data from session start (no lookback lag)',
        limitations: [
            'Only meaningful for intraday trading',
            'Resets each session - no overnight continuity',
            'Large prints can skew VWAP'
        ],
        recommendedTimeframes: ['1m', '5m', '15m', '1h'],
        commonMisuses: [
            'Using VWAP on daily charts (meaningless)',
            'Ignoring time of day - VWAP is more reliable later in session',
            'Trading against VWAP in strongly trending markets'
        ]
    },
    
    stochastic: {
        id: 'stochastic',
        name: 'Stochastic Oscillator',
        formula: '%K = (Close - Low(n)) / (High(n) - Low(n)) × 100, %D = SMA(%K, 3)',
        formulaLatex: '\\%K = \\frac{C - L_n}{H_n - L_n} \\times 100',
        parameters: [
            { name: 'kPeriod', description: '%K period', defaultValue: 14, type: 'number' },
            { name: 'dPeriod', description: '%D smoothing', defaultValue: 3, type: 'number' }
        ],
        lagBars: 7,
        lagDescription: 'Fast stochastic reacts quickly; slow stochastic has additional smoothing lag',
        limitations: [
            'Can stay overbought/oversold in trends',
            'Prone to whipsaws in ranging markets',
            'Only shows position within range, not trend'
        ],
        recommendedTimeframes: ['15m', '1h', '4h'],
        commonMisuses: [
            'Trading every crossover without trend filter',
            'Ignoring that >80 can stay >80 for extended periods'
        ]
    }
};

// =============================================================================
// LAG CALCULATION
// =============================================================================

export function calculateIndicatorLag(indicatorId: string, period: number): number {
    const formula = INDICATOR_FORMULAS[indicatorId];
    if (!formula) return Math.floor(period / 2);
    
    // Approximate lag based on indicator type
    switch (indicatorId) {
        case 'sma':
            return Math.floor(period / 2);
        case 'ema':
            return Math.floor(period / 3);
        case 'rsi':
        case 'stochastic':
            return Math.floor(period / 2);
        case 'macd':
            return 13; // Based on default settings
        case 'vwap':
            return 0;
        default:
            return Math.floor(period / 2);
    }
}

// =============================================================================
// WARNING GENERATOR
// =============================================================================

export interface IndicatorWarning {
    type: 'lag' | 'data' | 'misuse' | 'timeframe';
    severity: 'info' | 'warning' | 'caution';
    message: string;
}

export function generateWarnings(
    indicatorId: string,
    params: Record<string, number>,
    timeframe: string,
    availableBars: number
): IndicatorWarning[] {
    const warnings: IndicatorWarning[] = [];
    const formula = INDICATOR_FORMULAS[indicatorId];
    
    if (!formula) return warnings;
    
    const period = params.period || params.kPeriod || 14;
    
    // Data warning
    if (availableBars < period * 2) {
        warnings.push({
            type: 'data',
            severity: 'warning',
            message: `Insufficient data: ${availableBars} bars available, ${period * 2} recommended for ${formula.name}`
        });
    }
    
    // Lag warning
    const lag = calculateIndicatorLag(indicatorId, period);
    if (lag > 0) {
        warnings.push({
            type: 'lag',
            severity: 'info',
            message: `This indicator has ~${lag} bar lag`
        });
    }
    
    // Timeframe warnings
    const tfMinutes = parseTimeframeMinutes(timeframe);
    if (indicatorId === 'rsi' && period === 14 && tfMinutes === 1) {
        warnings.push({
            type: 'timeframe',
            severity: 'caution',
            message: 'RSI(14) on 1m timeframe only covers 14 minutes of data. Consider higher period or longer timeframe.'
        });
    }
    
    if (indicatorId === 'vwap' && tfMinutes >= 1440) {
        warnings.push({
            type: 'misuse',
            severity: 'warning',
            message: 'VWAP is designed for intraday trading and resets daily. Using on daily+ charts is not meaningful.'
        });
    }
    
    if (indicatorId === 'sma' && period === 200 && availableBars < 200) {
        warnings.push({
            type: 'data',
            severity: 'warning',
            message: `SMA(200) requires 200 bars. Only ${availableBars} bars available.`
        });
    }
    
    return warnings;
}

function parseTimeframeMinutes(timeframe: string): number {
    const match = timeframe.match(/(\d+)([mhdwMy])/);
    if (!match) return 1;
    
    const value = parseInt(match[1]);
    const unit = match[2];
    
    switch (unit) {
        case 'm': return value;
        case 'h': return value * 60;
        case 'd': return value * 1440;
        case 'w': return value * 10080;
        case 'M': return value * 43200;
        case 'y': return value * 525600;
        default: return value;
    }
}

// =============================================================================
// TOOLTIP CONTENT GENERATOR
// =============================================================================

export function generateTooltipContent(
    indicatorId: string,
    currentValue: number,
    params: Record<string, number>
): string {
    const formula = INDICATOR_FORMULAS[indicatorId];
    if (!formula) return `${indicatorId}: ${currentValue.toFixed(2)}`;
    
    let content = `**${formula.name}**\n\n`;
    content += `**Formula:**\n${formula.formula}\n\n`;
    content += `**Current Value:** ${currentValue.toFixed(4)}\n\n`;
    
    if (Object.keys(params).length > 0) {
        content += `**Parameters:**\n`;
        for (const [key, value] of Object.entries(params)) {
            content += `- ${key}: ${value}\n`;
        }
        content += '\n';
    }
    
    content += `**Lag:** ${formula.lagDescription}\n\n`;
    
    if (formula.limitations.length > 0) {
        content += `**Limitations:**\n`;
        formula.limitations.forEach(l => {
            content += `- ${l}\n`;
        });
    }
    
    return content;
}
