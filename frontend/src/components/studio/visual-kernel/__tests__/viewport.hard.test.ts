import { clampViewport, zoomAt, panBy, visibleRange } from '../viewport';

describe('viewport hardest', () => {
    it('clamp is idempotent', () => {
        const v1 = clampViewport({ offset: 10, scale: 5, count: 1000, width: 800 });
        const v2 = clampViewport({ offset: v1.offset, scale: v1.scale, count: 1000, width: 800 });
        expect(v2).toEqual(v1);
    });
    it('zoomAt preserves anchor index', () => {
        const anchorX = 200;
        const orig = { offset: 50, scale: 6, count: 500, width: 800 };
        const anchorIdx = orig.offset + anchorX / orig.scale;
        const next = zoomAt({ ...orig, factor: 1.5, anchorX });
        const nextAnchorIdx = next.offset + anchorX / next.scale;
        expect(Math.abs(nextAnchorIdx - anchorIdx)).toBeLessThan(0.01);
    });
    it('pan never exceeds maxOffset', () => {
        for (let i = 0; i < 100; i += 1) {
            const v = panBy({ offset: 0, scale: 6, width: 800, count: 100, deltaPixels: -10000 });
            expect(v.offset).toBeLessThanOrEqual(v.maxOffset);
            expect(v.offset).toBeGreaterThanOrEqual(0);
        }
    });
    it('visibleRange count matches floor(width/scale)', () => {
        const v = clampViewport({ offset: 10, scale: 8, count: 200, width: 800 });
        const r = visibleRange({ offset: v.offset, scale: v.scale, width: 800 });
        expect(r.count).toBe(Math.floor(800 / v.scale));
    });
    it('fuzz 10k random inputs never throw and stay bounded', () => {
        for (let i = 0; i < 10000; i += 1) {
            const c = clampViewport({ offset: Math.random() * 200 - 50, scale: Math.random() * 100, count: Math.floor(Math.random() * 1000), width: 600 + Math.random() * 600 });
            expect(Number.isFinite(c.offset) && Number.isFinite(c.scale)).toBe(true);
        }
    });
});
