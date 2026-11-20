/**
 * Alpha Engine Math Utilities
 * Precision statistical calculations for relative value analysis.
 */


/**
 * Calculates the Pearson Correlation Coefficient (R) between two datasets.
 */
export function calculateCorrelation(p: number[], g: number[]): number {
    const n = Math.min(p.length, g.length);
    if (n < 2) return 0;

    let sumP = 0, sumG = 0, sumPG = 0, sumP2 = 0, sumG2 = 0;
    
    for (let i = 0; i < n; i++) {
        sumP += p[i];
        sumG += g[i];
        sumPG += p[i] * g[i];
        sumP2 += p[i] * p[i];
        sumG2 += g[i] * g[i];
    }

    const numerator = n * sumPG - sumP * sumG;
    const denominator = Math.sqrt((n * sumP2 - sumP * sumP) * (n * sumG2 - sumG * sumG));

    if (denominator === 0) return 0;
    return numerator / denominator;
}

/**
 * Calculates Beta (sensitivity) of G relative to P.
 */
export function calculateBeta(p: number[], g: number[]): number {
    const n = Math.min(p.length, g.length);
    if (n < 2) return 1;

    // Calculate returns instead of raw prices for beta
    const pReturns = [];
    const gReturns = [];
    for (let i = 1; i < n; i++) {
        pReturns.push((p[i] - p[i-1]) / p[i-1]);
        gReturns.push((g[i] - g[i-1]) / g[i-1]);
    }

    const avgP = pReturns.reduce((a, b) => a + b, 0) / pReturns.length;
    const avgG = gReturns.reduce((a, b) => a + b, 0) / gReturns.length;

    let covariance = 0;
    let varianceP = 0;

    for (let i = 0; i < pReturns.length; i++) {
        covariance += (pReturns[i] - avgP) * (gReturns[i] - avgG);
        varianceP += (pReturns[i] - avgP) ** 2;
    }

    if (varianceP === 0) return 1;
    return covariance / varianceP;
}

/**
 * Normalizes a price series to start at 0% from a specific anchor index.
 */
export function normalizeSeries(data: number[], anchorIdx: number): number[] {
    const base = data[anchorIdx] || data[0] || 1;
    return data.map(val => (val / base - 1) * 100);
}

/**
 * Calculates Alpha Velocity (lead/lag) over N bars.
 */
export function calculateAlphaVelocity(p: number[], g: number[]): number {
    if (p.length < 2 || g.length < 2) return 0;
    
    const pStart = p[0];
    const gStart = g[0];
    const pEnd = p[p.length - 1];
    const gEnd = g[g.length - 1];

    const pPerf = (pEnd / pStart - 1);
    const gPerf = (gEnd / gStart - 1);

    return (gPerf - pPerf) * 100;
}

/**
 * Calculates Z-Score normalization for a series.
 */
export function calculateZScore(data: number[]): number[] {
    if (data.length === 0) return [];
    const avg = data.reduce((a, b) => a + b, 0) / data.length;
    const stdDev = Math.sqrt(data.reduce((a, b) => a + (b - avg) ** 2, 0) / data.length);
    if (stdDev === 0) return data.map(() => 0);
    return data.map(val => (val - avg) / stdDev);
}

/**
 * Calculates Ratio of G / P.
 */
export function calculateRatio(p: number[], g: number[]): number[] {
    const n = Math.min(p.length, g.length);
    const ratio = [];
    for (let i = 0; i < n; i++) {
        ratio.push(g[i] / p[i]);
    }
    return ratio;
}
