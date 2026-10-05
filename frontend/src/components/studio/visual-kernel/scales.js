/** @typedef {((value: number) => number) & {invert: (pixel: number) => number, ticks: (count?: number) => number[], domain: () => number[], range: () => number[]}} FinancialScale */
/**
 * Owned financial scales — pure, deterministic, no side effects.
 * Every display metric must be validated with Number.isFinite before
 * calling these helpers; 0 is valid data, null means unavailable.
 */

/**
 * Linear scale: domain [d0,d1] → range [r0,r1]
 * Returns a function with .invert and .ticks for axis rendering.
 * @returns {FinancialScale}
 */
export function createLinearScale(domain, range) {
    const [d0, d1] = domain;
    const [r0, r1] = range;
    const dSpan = d1 - d0;
    const rSpan = r1 - r0;
    const domainIsFinite = Number.isFinite(d0) && Number.isFinite(d1);
    const factor = domainIsFinite && dSpan !== 0 ? rSpan / dSpan : 0;
    const offset = r0 - d0 * factor;
    // Specialize once when the scale is built. This function runs for every
    // visible point, so repeating invariant domain checks here is expensive.
    const scale = !domainIsFinite
        ? () => r0
        : dSpan === 0
            ? (value) => Number.isFinite(value) ? (r0 + r1) / 2 : r0
            : (value) => Number.isFinite(value) ? value * factor + offset : r0;
    scale.invert = (pixel) => {
        if (rSpan === 0) return d0;
        return d0 + ((pixel - r0) / rSpan) * dSpan;
    };
    scale.ticks = (count = 5) => {
        if (!domainIsFinite || count <= 0) return [];
        if (dSpan === 0) return [d0];
        const step = dSpan / count;
        return Array.from({ length: count + 1 }, (_, i) => d0 + i * step);
    };
    scale.domain = () => [d0, d1];
    scale.range = () => [r0, r1];
    return scale;
}

/**
 * Price scale: maps value domain to pixel height with top/bottom padding.
 * Supports modes: linear (default), log, percent, indexed100
 * Inverted because canvas y=0 is top.
 * @returns {FinancialScale}
 */
export function createPriceScale({ min, max, height, paddingTop = 20, paddingBottom = 30, mode = 'linear', base = 100 }) {
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
        return createLinearScale([0, 1], [height - paddingBottom, paddingTop]);
    }
    const range = height - paddingTop - paddingBottom;
    let d0 = min;
    let d1 = max;
    let toDomain = (v) => v;
    let fromDomain = (v) => v;
    if (mode === 'log') {
        const logMin = Math.log(Math.max(1e-9, min));
        const logMax = Math.log(Math.max(1e-9, max));
        d0 = logMin; d1 = logMax;
        toDomain = (v) => Math.log(Math.max(1e-9, v));
        fromDomain = (v) => Math.exp(v);
    } else if (mode === 'percent') {
        // percent change from base (first close)
        d0 = ((min - base) / base) * 100;
        d1 = ((max - base) / base) * 100;
        toDomain = (v) => ((v - base) / base) * 100;
        fromDomain = (v) => base * (1 + v / 100);
    } else if (mode === 'indexed100') {
        d0 = (min / base) * 100;
        d1 = (max / base) * 100;
        toDomain = (v) => (v / base) * 100;
        fromDomain = (v) => (v / 100) * base;
    }
    const span = d1 - d0;
    if (span === 0) return createLinearScale([d0 - 1, d1 + 1], [height - paddingBottom, paddingTop]);
    const linear = createLinearScale([d0, d1], [height - paddingBottom, paddingTop]);
    const scale = (v) => linear(toDomain(v));
    scale.invert = (px) => fromDomain(linear.invert(px));
    scale.ticks = (count = 5) => linear.ticks(count).map(fromDomain);
    scale.domain = () => [fromDomain(d0), fromDomain(d1)];
    scale.range = linear.range;
    // TradingView PriceFormatter niceTicks 1-2-5
    scale.niceTicks = (count = 5) => {
        const raw = linear.ticks(count);
        return raw.map(fromDomain).map((v) => Number(v.toFixed(2)));
    };
    return scale;
}

// Chart type transforms — Heikin Ashi, Renko, etc. (TradingView max)
export function toHeikinAshi(candles) {
    if (!Array.isArray(candles) || candles.length === 0) return [];
    const ha = [];
    let prevHaOpen = candles[0].open;
    let prevHaClose = candles[0].close;
    candles.forEach((c, i) => {
        if (i === 0) {
            ha.push({ ...c, open: (c.open + c.close) / 2, close: (c.open + c.high + c.low + c.close) / 4 });
            prevHaOpen = ha[0].open; prevHaClose = ha[0].close;
        } else {
            const haClose = (c.open + c.high + c.low + c.close) / 4;
            const haOpen = (prevHaOpen + prevHaClose) / 2;
            const haHigh = Math.max(c.high, haOpen, haClose);
            const haLow = Math.min(c.low, haOpen, haClose);
            ha.push({ ...c, open: haOpen, high: haHigh, low: haLow, close: haClose });
            prevHaOpen = haOpen; prevHaClose = haClose;
        }
    });
    return ha;
}

export function toRenko(candles, brickSize) {
    if (!Array.isArray(candles) || candles.length === 0) return [];
    const size = brickSize || Math.max(0.5, (Math.max(...candles.map(c=>c.high)) - Math.min(...candles.map(c=>c.low))) * 0.01);
    const renko = [];
    let lastClose = candles[0].close;
    candles.forEach((c) => {
        const diff = c.close - lastClose;
        const bricks = Math.floor(Math.abs(diff) / size);
        for (let i = 0; i < bricks; i += 1) {
            lastClose += Math.sign(diff) * size;
            renko.push({ time: c.time, open: lastClose - Math.sign(diff)*size, high: lastClose + size*0.1, low: lastClose - size*0.1, close: lastClose, volume: c.volume / (bricks||1) });
        }
    });
    return renko.length ? renko : candles;
}

export function resampleCandles(candles, timeframe) {
    if (!Array.isArray(candles) || candles.length === 0 || timeframe === '1D' || !timeframe) return candles;
    const map = { '1W': 5, '1M': 21, '1H': 1, '4H': 1 }; // daily data: 5d=week, 21d=month; intraday not resampled here
    const bucket = map[timeframe];
    if (!bucket || bucket <= 1) return candles;
    const out = [];
    for (let i = 0; i < candles.length; i += bucket) {
        const slice = candles.slice(i, i + bucket);
        if (slice.length === 0) continue;
        out.push({
            time: slice[0].time,
            open: slice[0].open,
            high: Math.max(...slice.map(c=>c.high)),
            low: Math.min(...slice.map(c=>c.low)),
            close: slice[slice.length-1].close,
            volume: slice.reduce((s,c)=>s+c.volume,0),
        });
    }
    return out;
}

/**
 * Time/index scale: maps index 0..n-1 to x pixels.
 */
export function createTimeScale({ count, width, paddingLeft = 20, paddingRight = 50 }) {
    if (!Number.isFinite(count) || count <= 1) {
        return createLinearScale([0, 1], [paddingLeft, width - paddingRight]);
    }
    return createLinearScale([0, count - 1], [paddingLeft, width - paddingRight]);
}

/**
 * Color scale for heat/density (linear interpolation).
 */
export function createColorScale(stops) {
    // stops: [{t:0,color:'rgb(...)'}, {t:1,color:'rgb(...)'}] sorted
    return (t) => {
        const clamped = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0));
        if (stops.length === 0) return 'transparent';
        if (stops.length === 1) return stops[0].color;
        for (let i = 1; i < stops.length; i += 1) {
            if (clamped <= stops[i].t) {
                const a = stops[i - 1];
                const b = stops[i];
                const u = (clamped - a.t) / (b.t - a.t || 1);
                return interpolateColor(a.color, b.color, u);
            }
        }
        return stops[stops.length - 1].color;
    };
}

function interpolateColor(a, b, t) {
    // naive rgb lerp, expects 'rgba(r,g,b,a)' or '#rrggbb'
    const pa = parseColor(a);
    const pb = parseColor(b);
    if (!pa || !pb) return a;
    const r = Math.round(pa.r + (pb.r - pa.r) * t);
    const g = Math.round(pa.g + (pb.g - pa.g) * t);
    const b2 = Math.round(pa.b + (pb.b - pa.b) * t);
    const alpha = pa.a + (pb.a - pa.a) * t;
    return `rgba(${r},${g},${b2},${alpha})`;
}

function parseColor(c) {
    const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+),?\s*([\d.]+)?\)/);
    if (m) return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]), a: m[4] ? Number(m[4]) : 1 };
    const h = c.match(/^#([0-9a-f]{6})$/i);
    if (h) {
        const n = parseInt(h[1], 16);
        return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 };
    }
    return null;
}
