import { toHeikinAshi, toRenko, resampleCandles, createPriceScale } from '../scales';

describe('chart types hardest', () => {
    const candles = [
        { time: 1, open: 100, high: 105, low: 98, close: 103, volume: 1000 },
        { time: 2, open: 103, high: 107, low: 102, close: 106, volume: 1200 },
        { time: 3, open: 106, high: 108, low: 104, close: 105, volume: 800 },
    ];
    it('Heikin Ashi preserves count and transforms correctly', () => {
        const ha = toHeikinAshi(candles);
        expect(ha.length).toBe(3);
        expect(ha[0].close).toBeCloseTo((100+105+98+103)/4, 5);
        expect(ha[1].open).toBeCloseTo((ha[0].open + ha[0].close)/2, 5);
        expect(Number.isFinite(ha[1].high) && Number.isFinite(ha[1].low)).toBe(true);
    });
    it('Renko bricks with size', () => {
        const renko = toRenko(candles, 2);
        expect(Array.isArray(renko)).toBe(true);
        expect(renko.length).toBeGreaterThan(0);
    });
    it('resample 1W aggregates 5 daily', () => {
        const daily = Array.from({ length: 10 }, (_, i) => ({ time: i, open: 100+i, high: 105+i, low: 98+i, close: 103+i, volume: 1000 }));
        const weekly = resampleCandles(daily, '1W');
        expect(weekly.length).toBe(2);
        expect(weekly[0].high).toBe(109); // 105+4
        expect(weekly[0].volume).toBe(5000);
    });
    it('price scale log mode invert roundtrip', () => {
        const s = createPriceScale({ min: 100, max: 200, height: 400, mode: 'log', base: 100 });
        const v = 150;
        const px = s(v);
        const inv = s.invert(px);
        expect(Math.abs(inv - v)).toBeLessThan(0.5);
    });
    it('price scale percent mode', () => {
        const s = createPriceScale({ min: 90, max: 110, height: 400, mode: 'percent', base: 100 });
        expect(s.invert(s(100))).toBeCloseTo(100, 5);
    });
});
