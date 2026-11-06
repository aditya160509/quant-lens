const unavailableMetric = Object.freeze({
    value: null,
    unit: 'unknown',
    status: 'unavailable',
    sample_size: 0,
    methodology: 'not reported by the execution artifact',
});

export function canonicalMetric(metrics, name) {
    const metric = metrics?.canonical?.[name];
    if (!metric || !['observed', 'estimated', 'unavailable'].includes(metric.status)) return unavailableMetric;
    return metric;
}

export function formatCanonicalMetric(metric, { signed = false, digits = 2 } = {}) {
    if (!metric || metric.status === 'unavailable' || !Number.isFinite(metric.value)) return 'Unavailable';
    if (metric.unit === 'decimal' || metric.unit === 'decimal_annualized') {
        const value = metric.value * 100;
        return `${signed && value > 0 ? '+' : ''}${value.toFixed(digits)}%`;
    }
    if (metric.unit === 'count') return String(Math.trunc(metric.value));
    if (metric.unit === 'bars') return `${metric.value.toFixed(digits)} bars`;
    return metric.value.toFixed(digits);
}

export function normalizeStudioExecutionResult(result, runId = null) {
    return {
        candles: result?.candles || [],
        signals: result?.signals || [],
        metrics: result?.metrics || {},
        trades: result?.trades || [],
        orders: Array.isArray(result?.orders) ? result.orders : deriveOrdersFromSignals(result?.signals),
        fills: Array.isArray(result?.fills) ? result.fills : null,
        fillsStatus: result?.fills_status || { status: 'unavailable', reason: 'The execution contract carries no governed fill records; fills are not synthesized.' },
        equityCurve: result?.equity_curve || [],
        series: result?.series || null,
        metadata: result?.metadata || null,
        runId,
        volumeProfile: [],
    };
}

export function deriveOrdersFromSignals(signals) {
    const orders = [];
    (signals || []).forEach((signal, position) => {
        const direction = Number(signal?.direction);
        if (direction !== 1 && direction !== -1) return;
        orders.push({
            order_id: `order-${position + 1}`,
            date: signal.date || null,
            timestamp: signal.timestamp ?? null,
            direction,
            price: Number.isFinite(signal.price) ? signal.price : null,
            bar_index: Number.isInteger(signal.idx) ? signal.idx : null,
            source: 'observed_signal',
        });
    });
    return orders;
}

export function replayFillLinkage(run) {
    const ordersAvailable = Array.isArray(run?.orders) && run.orders.length > 0;
    const fillsAvailable = Array.isArray(run?.fills) && run.fills.length > 0;
    return {
        ordersAvailable,
        fillsAvailable,
        fillsReason: run?.fillsStatus?.reason || 'The execution contract carries no governed fill records; fills are not synthesized from signals or trades.',
    };
}

export function studioComparisonCompatibility(left, right) {
    const dimensions = [
        ['currency', left?.metadata?.data_quality?.currency, right?.metadata?.data_quality?.currency],
        ['calendar', left?.metadata?.data_quality?.calendar, right?.metadata?.data_quality?.calendar],
        ['dataset', left?.metadata?.provenance?.dataset_id || left?.metadata?.data_quality?.source, right?.metadata?.provenance?.dataset_id || right?.metadata?.data_quality?.source],
        ['engine version', left?.metadata?.provenance?.engine_version, right?.metadata?.provenance?.engine_version],
        ['return convention', left?.metadata?.provenance?.parameters?.return_convention, right?.metadata?.provenance?.parameters?.return_convention],
    ];
    const missing = dimensions.filter(([, a, b]) => !a || !b).map(([name]) => name);
    const mismatched = dimensions.filter(([, a, b]) => a && b && a !== b).map(([name, a, b]) => `${name}: ${a} vs ${b}`);
    const leftTimes = left?.candles?.map((row) => row.time) || [];
    const rightTimes = right?.candles?.map((row) => row.time) || [];
    const aligned = leftTimes.length === rightTimes.length && leftTimes.every((value, index) => value === rightTimes[index]);
    if (!aligned) mismatched.push('observation calendar: timestamps are not aligned');
    const reasons = [...missing.map((name) => `${name}: not reported for both runs`), ...mismatched];
    return { compatible: reasons.length === 0, reasons };
}

const quantile = (sorted, probability) => {
    if (!sorted.length) return null;
    const position = (sorted.length - 1) * probability;
    const lower = Math.floor(position);
    const weight = position - lower;
    return sorted[lower + 1] === undefined ? sorted[lower] : sorted[lower] * (1 - weight) + sorted[lower + 1] * weight;
};

export function observedReturnDiagnostics(equity, rollingWindow = 21) {
    const returns = [];
    for (let index = 1; index < (equity || []).length; index += 1) {
        const previous = equity[index - 1];
        const current = equity[index];
        if (Number.isFinite(previous) && Number.isFinite(current) && previous > 0) returns.push(current / previous - 1);
    }
    if (returns.length < 2) return null;
    const sorted = [...returns].sort((a, b) => a - b);
    const window = Math.max(2, Math.min(Math.trunc(rollingWindow), returns.length));
    const rollingVolatility = [];
    for (let end = window; end <= returns.length; end += 1) {
        const sample = returns.slice(end - window, end);
        const mean = sample.reduce((sum, value) => sum + value, 0) / sample.length;
        const variance = sample.reduce((sum, value) => sum + (value - mean) ** 2, 0) / sample.length;
        rollingVolatility.push(Math.sqrt(variance * 252));
    }
    const p5 = quantile(sorted, 0.05);
    const tail = sorted.filter((value) => value <= p5);
    const min = sorted[0];
    const max = sorted.at(-1);
    const width = max - min;
    const histogram = Array.from({ length: 10 }, () => 0);
    returns.forEach((value) => { const index = width === 0 ? 0 : Math.min(9, Math.floor(((value - min) / width) * 10)); histogram[index] += 1; });
    return {
        observations: returns.length,
        quantiles: { p1: quantile(sorted, 0.01), p5, median: quantile(sorted, 0.5), p95: quantile(sorted, 0.95), p99: quantile(sorted, 0.99) },
        expectedShortfall5: tail.reduce((sum, value) => sum + value, 0) / tail.length,
        worst: min,
        best: max,
        histogram,
        rollingVolatility,
        rollingWindow: window,
    };
}

const csvCell = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;

export function buildStudioResultsCsv({ metrics, series, metadata, runId }) {
    const rows = [['section', 'name', 'index', 'value', 'unit', 'status', 'methodology']];
    Object.entries(metrics?.canonical || {}).forEach(([name, metric]) => {
        rows.push(['metric', name, '', metric.value, metric.unit, metric.status, metric.methodology]);
    });
    Object.entries(series || {}).forEach(([name, values]) => {
        if (!Array.isArray(values)) return;
        values.forEach((value, index) => rows.push(['series', name, index, value, '', Number.isFinite(value) ? 'observed' : 'unavailable', '']));
    });
    rows.push(['manifest', 'run_id', '', runId || '', '', '', '']);
    rows.push(['manifest', 'engine_version', '', metadata?.provenance?.engine_version || '', '', '', '']);
    rows.push(['manifest', 'code_hash', '', metadata?.provenance?.code_hash || '', '', '', '']);
    rows.push(['manifest', 'data_source', '', metadata?.data_quality?.source || '', '', '', '']);
    return rows.map((row) => row.map(csvCell).join(',')).join('\n');
}

export function downloadStudioResultsCsv(result, filename = 'studio-results.csv') {
    const blob = new Blob([buildStudioResultsCsv(result)], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
}

export function buildStudioResultsJson({ metrics, series, metadata, runId, orders, fillsStatus }) {
    return JSON.stringify({
        run_id: runId || null,
        engine_version: metadata?.provenance?.engine_version || null,
        code_hash: metadata?.provenance?.code_hash || null,
        data_source: metadata?.data_quality?.source || null,
        warnings: metadata?.warnings || [],
        metrics: metrics?.canonical || {},
        series: series || null,
        orders: orders || [],
        fills: null,
        fills_status: fillsStatus || { status: 'unavailable' },
        arrow_export: { status: 'deferred', reason: 'Arrow export is deferred until a governed columnar schema is approved; CSV and JSON carry the same canonical values.' },
    }, null, 2);
}

export function downloadStudioResultsJson(result, filename = 'studio-results.json') {
    const blob = new Blob([buildStudioResultsJson(result)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
}

const escapeHtml = (value) => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

export function buildStudioResultsHtml({ metrics, series, metadata, runId, orders, fillsStatus }) {
    const engine = escapeHtml(metadata?.provenance?.engine_version || 'Unavailable');
    const codeHash = escapeHtml(metadata?.provenance?.code_hash || 'Unavailable');
    const source = escapeHtml(metadata?.data_quality?.source || 'Unavailable');
    const runLabel = escapeHtml(runId || 'unpersisted');
    const metricRows = Object.entries(metrics?.canonical || {}).map(([name, metric]) => {
        const cells = [name, metric.value, metric.unit, metric.status, metric.methodology].map(escapeHtml);
        return '<tr><td>' + cells.join('</td><td>') + '</td></tr>';
    }).join('');
    const orderRows = (orders || []).map((order) => {
        const cells = [order.order_id, order.date, order.direction, order.price].map(escapeHtml);
        return '<tr><td>' + cells.join('</td><td>') + '</td></tr>';
    }).join('') || '<tr><td colspan="4">No observed orders.</td></tr>';
    const warningItems = (metadata?.warnings || []).map((warning) => {
        const text = warning.code || warning.message || JSON.stringify(warning);
        return '<li>' + escapeHtml(text) + '</li>';
    }).join('');
    const seriesSummary = Object.entries(series || {}).map(([name, values]) => {
        const count = Array.isArray(values) ? values.length : 0;
        return name + '=' + count;
    }).join(', ') || 'none';
    const fillsNote = escapeHtml(fillsStatus?.reason || 'Fills are not synthesized.');
    const parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<title>Studio results ' + runLabel + '</title>',
        '<style>body{font-family:monospace;max-width:900px;margin:24px auto;padding:0 16px;color:#111}',
        'table{border-collapse:collapse;width:100%;font-size:12px}',
        'th,td{border:1px solid #999;padding:4px 8px;text-align:left}',
        '.note{font-size:11px;color:#444}</style></head><body>',
        '<div><button onclick="window.print()">Save as PDF via print</button>',
        '<p class="note">Print-friendly report. Use the browser print dialog to save as PDF. ',
        'Arrow export deferred: no governed columnar schema exists yet; CSV and JSON carry the same canonical values.</p></div>',
        '<h1>Studio results ' + runLabel + '</h1>',
        '<p>Engine ' + engine + ' | Code ' + codeHash + ' | Source ' + source + '</p>',
        '<h2>Warnings</h2><ul>' + (warningItems || '<li>None</li>') + '</ul>',
        '<h2>Canonical metrics</h2><table><thead><tr><th>Name</th><th>Value</th><th>Unit</th><th>Status</th><th>Methodology</th></tr></thead>',
        '<tbody>' + metricRows + '</tbody></table>',
        '<h2>Observed orders (fills unavailable)</h2><p class="note">' + fillsNote + '</p>',
        '<table><thead><tr><th>Order</th><th>Date</th><th>Direction</th><th>Price</th></tr></thead>',
        '<tbody>' + orderRows + '</tbody></table>',
        '<h2>Provenance</h2><p class="note">Deterministic export of visible canonical values. ',
        'Series row counts: ' + escapeHtml(seriesSummary) + '.</p></body></html>',
    ];
    return parts.join('');
}

export function downloadStudioResultsHtml(result, filename = 'studio-results.html') {
    const blob = new Blob([buildStudioResultsHtml(result)], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
}
