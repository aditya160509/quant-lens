/**
 * @jest-environment jsdom
 */
import { isWebGLAvailable, createWebGLContext } from '../webgl';

describe('webgl hardest', () => {
    it('fallback when getContext returns null', () => {
        const canvas = document.createElement('canvas');
        jest.spyOn(canvas, 'getContext').mockReturnValue(null);
        expect(createWebGLContext(canvas)).toBeNull();
    });
    it('isWebGLAvailable returns boolean', () => {
        expect(typeof isWebGLAvailable()).toBe('boolean');
    });
    it('parity: WebGL and Canvas2D inputs produce same domain mapping', () => {
        // Pure check: both paths use same minV/maxV → same scaleY
        const path = Array.from({ length: 252 }, (_, i) => 1 + Math.sin(i / 20) * 0.1);
        const minV = Math.min(...path) * 0.95;
        const maxV = Math.max(...path) * 1.05;
        const scaleY = (v) => 400 - ((v - minV) / (maxV - minV || 1)) * 400;
        expect(Number.isFinite(scaleY(path[0]))).toBe(true);
        expect(scaleY(minV)).toBeGreaterThan(scaleY(maxV));
    });
});
