/**
 * HiDPI canvas helpers — single source for dpr + ResizeObserver.
 */

export function setupHiDPI(canvas, rect) {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, dpr, width: rect.width, height: rect.height };
}

export function createResizeObserver(container, onResize) {
    let frame = 0;
    const handle = () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
            const rect = container.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) onResize(rect);
        });
    };
    handle();
    const observer = new ResizeObserver(handle);
    observer.observe(container);
    return () => {
        cancelAnimationFrame(frame);
        observer.disconnect();
    };
}

export function exportCanvasToPNG(canvas, filename = 'studio-export.png') {
    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
}
