import { useState, useEffect, useMemo } from 'react';
import { getSeries } from '@/components/chart_engine/DataAdapter/intraday';
import { Timeframe } from '@/components/chart_engine/types';

export function useTacticalData(symbol: string, timeframe: string = '5m') {
    const [rawBars, setRawBars] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let isMounted = true;
        const fetchData = async () => {
            if (!symbol) return;
            setLoading(true);
            try {
                const series = await getSeries(symbol, timeframe as Timeframe); 
                if (isMounted) {
                    setRawBars(series.bars || []);
                    setLoading(false);
                }
            } catch (err) {
                console.error('[TacticalData] Error:', err);
                if (isMounted) setLoading(false);
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 60000);
        return () => {
            isMounted = false;
            clearInterval(interval);
        };
    }, [symbol, timeframe]);

    // Computed Intelligence Stack
    const intelligence = useMemo(() => {
        if (rawBars.length === 0) return null;

        // --- 1. OVERLAYS (EMA & LRC) ---
        const calculateEMA = (bars: any[], period: number) => {
            const k = 2 / (period + 1);
            let ema = bars[0].close;
            return bars.map((b, i) => {
                ema = (b.close - ema) * k + ema;
                return ema;
            });
        };

        const ema8 = calculateEMA(rawBars, 8);
        const ema21 = calculateEMA(rawBars, 21);

        // --- 2. ADAPTIVE LINEAR REGRESSION CHANNEL (LRC) ---
        // Calculate on the visible window (the 'warm' data)
        const lrcPeriod = 100;
        const lrcSeries = rawBars.map((_, i, arr) => {
            if (i < lrcPeriod) return null;
            
            // Rolling Linear Regression: y = mx + b
            const slice = arr.slice(i - lrcPeriod + 1, i + 1);
            const n = slice.length;
            let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
            
            for (let j = 0; j < n; j++) {
                const x = j;
                const y = slice[j].close;
                sumX += x;
                sumY += y;
                sumXY += x * y;
                sumX2 += x * x;
            }
            
            const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
            const intercept = (sumY - slope * sumX) / n;
            
            // Current center value
            const center = slope * (n - 1) + intercept;
            
            // Calculate Standard Deviation for Bands
            const dev = Math.sqrt(slice.reduce((acc, b, idx) => {
                const fitted = slope * idx + intercept;
                return acc + Math.pow(b.close - fitted, 2);
            }, 0) / n);

            return { center, upper: center + dev * 2, lower: center - dev * 2 };
        });

        // --- 3. BOLLINGER BANDS (20, 2SD) ---
        const bbPeriod = 20;
        const bollinger = rawBars.map((_, i, arr) => {
            if (i < bbPeriod) return null;
            const slice = arr.slice(i - bbPeriod + 1, i + 1);
            const basis = slice.reduce((a, b) => a + b.close, 0) / bbPeriod;
            const dev = Math.sqrt(slice.reduce((a, b) => a + Math.pow(b.close - basis, 2), 0) / bbPeriod);
            return {
                upper: basis + dev * 2,
                lower: basis - dev * 2,
                basis
            };
        });

        // --- 4. SESSION STATIC LEVELS ---
        const sessionHigh = Math.max(...rawBars.map(b => b.high));
        const sessionLow = Math.min(...rawBars.map(b => b.low));

        // --- 5. VOLUME PROFILE (POC Removed) ---
        const minPrice = Math.min(...rawBars.map(b => b.low));
        const maxPrice = Math.max(...rawBars.map(b => b.high));
        const priceRange = maxPrice - minPrice;
        const bucketCount = 50; 
        const buckets = new Array(bucketCount).fill(0).map(() => ({ buyVol: 0, sellVol: 0, total: 0 }));
        const bucketSize = priceRange / bucketCount;

        rawBars.forEach(b => {
            const idx = Math.min(bucketCount - 1, Math.floor((b.close - minPrice) / (bucketSize || 1)));
            if (b.close >= b.open) buckets[idx].buyVol += b.volume;
            else buckets[idx].sellVol += b.volume;
            buckets[idx].total += b.volume;
        });

        let maxV = 0;
        buckets.forEach((b) => { if (b.total > maxV) { maxV = b.total; } });

        // --- 6. VOLATILITY MOMENTUM ---
        const returns = rawBars.slice(1).map((b, i) => Math.abs(b.close / rawBars[i].close - 1));
        const hvPeriod = 20;
        const hvSeries = rawBars.map((_, i) => {
            if (i < hvPeriod) return 0;
            const slice = returns.slice(Math.max(0, i - hvPeriod), i);
            if (slice.length === 0) return 0;
            const mean = slice.reduce((a, b) => a + b, 0) / slice.length;
            const variance = slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / slice.length;
            return Math.sqrt(variance) * Math.sqrt(252);
        });

        // Proxy "Implied" Volatility based on range expansion vs distance to EMA21 (Replaced VWAP)
        const ivProxy = rawBars.map((b, i) => {
            const range = (b.high - b.low) / b.close;
            const distEma = Math.abs(b.close - ema21[i]) / b.close;
            return (range * 0.7 + distEma * 0.3) * 1.5;
        });

        // --- 7. DATA SLICING FOR UI ---
        const visibleSlice = 200;
        const sliceStart = Math.max(0, rawBars.length - visibleSlice);
        
        const slicedBars = rawBars.slice(sliceStart);
        const slicedIntelligence = {
            overlays: {
                lrc: lrcSeries.slice(sliceStart),
                ema8: ema8.slice(sliceStart),
                ema21: ema21.slice(sliceStart),
                bollinger: bollinger.slice(sliceStart)
            },
            levels: { sessionHigh, sessionLow },
            volumeProfile: {
                buckets,
                maxVol: maxV,
                minPrice,
                maxPrice
            },
            volatility: {
                hv: hvSeries.slice(sliceStart),
                iv: ivProxy.slice(sliceStart),
                regime: 'STABLE'
            }
        };
        
        return { 
            data: slicedBars, 
            intelligence: slicedIntelligence 
        };
    }, [rawBars]);

    return { 
        data: intelligence?.data || [], 
        intelligence: intelligence?.intelligence || null, 
        loading 
    };
}
