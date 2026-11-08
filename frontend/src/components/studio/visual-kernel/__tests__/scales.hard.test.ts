import { describe, it, expect } from "vitest";
import { createLinearScale, createPriceScale, createTimeScale } from '../scales';

describe('scales hardest invariants', () => {
    it('invert is inverse within 1e-10 over 100 random domains', () => {
        for (let i = 0; i < 100; i += 1) {
            const d0 = Math.random() * 200 - 100;
            const d1 = d0 + Math.random() * 100 + 1;
            const scale = createLinearScale([d0, d1], [0, 800]);
            const x = d0 + Math.random() * (d1 - d0);
            const px = scale(x);
            const inv = scale.invert(px);
            expect(Math.abs(inv - x)).toBeLessThan(1e-10);
        }
    });
    it('span zero returns center', () => {
        const s = createLinearScale([5, 5], [0, 100]);
        expect(s(5)).toBe(50);
        expect(s.ticks(5)).toEqual([5]);
    });
    it('non-finite domain returns r0', () => {
        const s = createLinearScale([NaN, 10], [0, 100]);
        expect(s(5)).toBe(0);
    });
    it('price scale clamps span zero to expanded domain', () => {
        const s = createPriceScale({ min: 100, max: 100, height: 200 });
        expect(s(100)).toBeGreaterThan(0);
        expect(s.invert(s(100))).toBeCloseTo(100, 5);
    });
    it('time scale with count 1 does not throw', () => {
        const s = createTimeScale({ count: 1, width: 800 });
        expect(() => s(0)).not.toThrow();
        expect(Number.isFinite(s(0))).toBe(true);
    });
    it('ticks monotonic and count+1', () => {
        const s = createLinearScale([0, 100], [0, 500]);
        const t = s.ticks(5);
        expect(t.length).toBe(6);
        for (let i = 1; i < t.length; i += 1) expect(t[i] > t[i - 1]).toBe(true);
    });
});
