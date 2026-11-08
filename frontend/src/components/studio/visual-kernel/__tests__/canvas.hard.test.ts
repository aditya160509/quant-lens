import { vi, describe, it, expect } from "vitest";
/**
 */
import { setupHiDPI, createResizeObserver } from '../canvas';

describe('canvas HiDPI hardest', () => {
    it('sets width === rect.width*dpr', () => {
        const canvas = document.createElement('canvas');
        const rect = { width: 400, height: 200 };
        Object.defineProperty(window, 'devicePixelRatio', { value: 2, writable: true });
        const { ctx, width, height, dpr } = setupHiDPI(canvas, rect);
        expect(canvas.width).toBe(800);
        expect(canvas.height).toBe(400);
        expect(width).toBe(400);
        expect(height).toBe(200);
        expect(dpr).toBe(2);
        expect(ctx).toBeTruthy();
    });
    it('ResizeObserver cleanup disconnects', () => {
        const div = document.createElement('div');
        const disconnect = vi.fn();
        const original = global.ResizeObserver;
        global.ResizeObserver = class { observe = vi.fn(); unobserve = vi.fn(); disconnect = disconnect; } as unknown as typeof ResizeObserver;
        const cleanup = createResizeObserver(div, () => {});
        expect(typeof cleanup).toBe('function');
        cleanup();
        expect(disconnect).toHaveBeenCalled();
        global.ResizeObserver = original;
    });
});
