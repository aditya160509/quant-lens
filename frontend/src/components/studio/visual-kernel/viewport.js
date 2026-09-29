/**
 * Viewport math for financial canvases — pure functions.
 * offset: first visible candle index
 * scale: pixels per candle (bar width)
 */

export function clampViewport({ offset, scale, count, width, minScale = 2, maxScale = 40 }) {
    const clampedScale = Math.max(minScale, Math.min(maxScale, Number.isFinite(scale) ? scale : 6));
    const visibleCount = Math.max(1, Math.floor(width / clampedScale));
    const maxOffset = Math.max(0, count - visibleCount);
    const clampedOffset = Math.max(0, Math.min(maxOffset, Number.isFinite(offset) ? offset : 0));
    return { offset: clampedOffset, scale: clampedScale, visibleCount, maxOffset };
}

export function visibleRange({ offset, scale, width }) {
    const visibleCount = Math.max(1, Math.floor(width / scale));
    return { start: offset, end: offset + visibleCount - 1, count: visibleCount };
}

export function zoomAt({ offset, scale, width, count, factor, anchorX }) {
    const anchorIdx = offset + anchorX / scale;
    const nextScale = Math.max(2, Math.min(40, scale * factor));
    const nextOffset = anchorIdx - anchorX / nextScale;
    return clampViewport({ offset: nextOffset, scale: nextScale, count, width });
}

export function panBy({ offset, scale, width, count, deltaPixels }) {
    const deltaIdx = deltaPixels / scale;
    return clampViewport({ offset: offset - deltaIdx, scale, count, width });
}
