/**
 * Level-of-detail downsampling — deterministic, pure.
 * Uses Largest-Triangle-Three-Buckets for equity curves, preserves extremes.
 */

export function downsampleLTTB(data, threshold) {
    if (!Array.isArray(data)) return [];
    if (data.length <= threshold || threshold <= 2) return data.slice();
    const bucketSize = (data.length - 2) / (threshold - 2);
    const sampled = [data[0]];
    let a = 0;
    for (let i = 0; i < threshold - 2; i += 1) {
        const rangeStart = Math.floor((i + 1) * bucketSize) + 1;
        const rangeEnd = Math.floor((i + 2) * bucketSize) + 1;
        const avgRange = data.slice(rangeStart, Math.min(rangeEnd, data.length));
        const avgX = avgRange.reduce((s, p) => s + (p.x ?? 0), 0) / (avgRange.length || 1);
        const avgY = avgRange.reduce((s, p) => s + (p.value ?? p), 0) / (avgRange.length || 1);
        const bucketStart = Math.floor(i * bucketSize) + 1;
        const bucketEnd = Math.floor((i + 1) * bucketSize) + 1;
        let maxArea = -1;
        let maxIdx = bucketStart;
        for (let j = bucketStart; j < bucketEnd; j += 1) {
            const area = Math.abs((data[a].x - avgX) * (data[j].value - data[a].value) - (data[a].x - data[j].x) * (avgY - data[a].value)) * 0.5;
            if (area > maxArea) { maxArea = area; maxIdx = j; }
        }
        sampled.push(data[maxIdx]);
        a = maxIdx;
    }
    sampled.push(data[data.length - 1]);
    return sampled;
}

export function lodThreshold(width) {
    // Visible pixels determine max points — not arbitrary caps
    if (!Number.isFinite(width) || width <= 0) return 1000;
    return Math.max(500, Math.min(2000, Math.floor(width * 1.5)));
}
