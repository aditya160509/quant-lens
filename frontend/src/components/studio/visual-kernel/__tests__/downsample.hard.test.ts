import { downsampleLTTB, lodThreshold } from '../downsample';

function makeEquity(n) {
    return Array.from({ length: n }, (_, i) => ({ x: i, value: 100 + Math.sin(i / 50) * 10 + i * 0.01 }));
}

describe('downsample hardest', () => {
    it('preserves start/end and length==threshold', () => {
        const data = makeEquity(10000);
        const out = downsampleLTTB(data, 500);
        expect(out.length).toBe(500);
        expect(out[0]).toEqual(data[0]);
        expect(out[out.length - 1]).toEqual(data[data.length - 1]);
    });
    it('max drawdown error <0.5% after downsample', () => {
        const data = makeEquity(10000);
        const calcDD = (arr) => { let peak = -Infinity; let maxDD = 0; arr.forEach(p => { const v = p.value; if (v > peak) peak = v; const dd = (peak - v) / peak; if (dd > maxDD) maxDD = dd; }); return maxDD; };
        const orig = calcDD(data);
        const down = calcDD(downsampleLTTB(data, 1500));
        expect(Math.abs(orig - down) / (orig || 1)).toBeLessThan(0.005);
    });
    it('lodThreshold monotonic in width', () => {
        expect(lodThreshold(400) < lodThreshold(800)).toBe(true);
        expect(lodThreshold(800) < lodThreshold(1600)).toBe(true);
        expect(lodThreshold(NaN)).toBe(1000);
    });
    it('empty/null returns []', () => {
        expect(downsampleLTTB([], 100)).toEqual([]);
        expect(downsampleLTTB(null, 100)).toEqual([]);
    });
});
