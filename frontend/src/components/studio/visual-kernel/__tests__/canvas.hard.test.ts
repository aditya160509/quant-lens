/**
 * @jest-environment jsdom
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
        const spy = jest.spyOn(global, 'ResizeObserver').mockImplementation(() => ({ observe: jest.fn(), disconnect: jest.fn(), unobserve: jest.fn() }));
        const cleanup = createResizeObserver(div, () => {});
        expect(typeof cleanup).toBe('function');
        cleanup();
        expect(spy.mock.results[0].value.disconnect).toHaveBeenCalled();
        spy.mockRestore();
    });
});
