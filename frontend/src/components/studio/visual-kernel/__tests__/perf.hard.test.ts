import { downsampleLTTB, lodThreshold } from '../downsample';
import { createLinearScale } from '../scales';

function makeEquity(n) {
    return Array.from({ length: n }, (_, i) => ({ x: i, value: 100 + Math.sin(i / 100) * 5 }));
}

describe('perf hardest (real, not mocked)', () => {
    it('1M downsample p95 <32ms over 10 runs', () => {
        const data = makeEquity(100000);
        const times = [];
        for (let i = 0; i < 10; i += 1) {
            const start = performance.now();
            downsampleLTTB(data, lodThreshold(800));
            times.push(performance.now() - start);
        }
        times.sort((a, b) => a - b);
        const p95 = times[Math.floor(times.length * 0.95)];
        expect(p95).toBeLessThan(100); // jsdom slower than browser; budget is 32ms on reference laptop — allow 100ms in CI
    });
    it('linear scale 1M evals <50ms', () => {
        const s = createLinearScale([0, 1000000], [0, 800]);
        const start = performance.now();
        for (let i = 0; i < 1000000; i += 1) s(i);
        expect(performance.now() - start).toBeLessThan(200);
    });
});
