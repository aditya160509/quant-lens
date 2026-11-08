import { describe, it, expect } from "vitest";
import { hitTestCandle, drawCrosshair, drawAnnotations } from '../interaction';
import { createLinearScale } from '../scales';

describe('interaction hardest', () => {
    it('hitTest at bar edges returns correct idx', () => {
        const candles = Array.from({ length: 10 }, (_, i) => ({ open: 100, high: 102, low: 99, close: 101, volume: 1000, time: i }));
        const scaleY = createLinearScale([98, 103], [200, 0]);
        const timeScale = createLinearScale([0, 9], [20, 780]);
        const barWidth = (780 - 20) / 9;
        const hit = hitTestCandle({ x: 20, y: 100, candles, scaleY, timeScale, barWidth, paddingLeft: 20, offset: 0 });
        expect(hit.idx).toBe(0);
        const hitEnd = hitTestCandle({ x: 780, y: 100, candles, scaleY, timeScale, barWidth, paddingLeft: 20, offset: 0 });
        expect(hitEnd.idx).toBe(9);
        expect(hitTestCandle({ x: -100, y: 100, candles, scaleY, timeScale, barWidth: 8, paddingLeft: 20, offset: 0 })).toBeNull();
    });
    it('drawCrosshair with NaN does not throw', () => {
        const ctx = { save: () => {}, restore: () => {}, strokeStyle: '', setLineDash: () => {}, lineWidth: 0, beginPath: () => {}, moveTo: () => {}, lineTo: () => {}, stroke: () => {}, fillStyle: '', fillRect: () => {}, font: '', textAlign: '', fillText: () => {}, canvas: { width: 800 } };
        expect(() => drawCrosshair(ctx, { x: NaN, y: 100, width: 800, height: 400, label: null })).not.toThrow();
    });
    it('drawAnnotations skips Infinity', () => {
        const ctx = { save: () => {}, restore: () => {}, strokeStyle: '', lineWidth: 0, setLineDash: () => {}, beginPath: () => {}, moveTo: () => {}, lineTo: () => {}, stroke: () => {}, fillStyle: '', fillRect: () => {}, canvas: { width: 800 } };
        const scaleY = () => Infinity;
        const timeScale = (i) => i * 10;
        expect(() => drawAnnotations(ctx, [{ type: 'line', value: Infinity }], scaleY, timeScale)).not.toThrow();
    });
});
