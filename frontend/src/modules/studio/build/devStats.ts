/** Pure statistics for the Dev views: tearsheet, trade excursions, Monte Carlo. Equity is a list of { date, value } with value as growth of 1 (or any positive level). */
/** Smallest and largest of a list in one pass; spreading into Math.min/max overflows the stack past ~100k values. */
export function minMax(xs: readonly number[]): [number, number] {
  let lo = Infinity, hi = -Infinity;
  for (const x of xs) { if (x < lo) lo = x; if (x > hi) hi = x; }
  return [lo, hi];
}

export type Eq = { date: string; value: number };
export type Trade = { entry_date: string; exit_date: string; side: string; entry: number; exit: number; pnl: number; ret: number };
export type Ohlc = { time: string; high: number; low: number };

const mean = (a: number[]) => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0);
const sd = (a: number[]) => { const m = mean(a); return a.length > 1 ? Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1)) : 0; };
/** Period returns dated at their end; a step from a non-positive or non-finite level has no return and is left out. */
const datedReturns = (eq: Eq[]) => eq.slice(1).flatMap((p, i) => { const r = p.value / eq[i].value - 1; return eq[i].value > 0 && Number.isFinite(r) ? [{ date: p.date, r }] : []; });
export const returns = (eq: Eq[]) => datedReturns(eq).map((x) => x.r);
const days = (a: string, b: string) => (Date.parse(b) - Date.parse(a)) / 864e5;

/** Fall from the running peak; null until the peak is a positive level. */
export function drawdown(eq: Eq[]): { date: string; dd: number | null }[] {
  let peak = -Infinity;
  return eq.map((p) => { if (Number.isFinite(p.value)) peak = Math.max(peak, p.value); return { date: p.date, dd: peak > 0 && Number.isFinite(p.value) ? p.value / peak - 1 : null }; });
}

/** The deepest drawdowns, each with start, trough, recovery (null while open) and length in days. */
export function topDrawdowns(eq: Eq[], n = 5) {
  const out: { start: string; trough: string; end: string | null; depth: number; days: number }[] = [];
  const pts = eq.filter((p) => Number.isFinite(p.value));
  if (!pts.length) return out;
  let peak = pts[0], cur: (typeof out)[number] | null = null;
  for (const p of pts) {
    if (p.value >= peak.value || peak.value <= 0) { if (cur) { cur.end = p.date; cur.days = days(cur.start, p.date); out.push(cur); cur = null; } peak = p; continue; }
    const dd = p.value / peak.value - 1;
    if (!cur) cur = { start: peak.date, trough: p.date, end: null, depth: dd, days: 0 };
    else if (dd < cur.depth) { cur.depth = dd; cur.trough = p.date; }
  }
  if (cur) { cur.days = days(cur.start, pts.at(-1)!.date); out.push(cur); }
  return out.sort((a, b) => a.depth - b.depth).slice(0, n);
}

/** Conventions: 252 periods a year, zero risk-free rate. Null where a figure is undefined (no positive start, no variance, under two points). */
export function stats(eq: Eq[]) {
  const r = returns(eq), yrs = eq.length > 1 ? days(eq[0].date, eq.at(-1)!.date) / 365.25 : 0;
  const first = eq[0]?.value, last = eq.at(-1)?.value;
  const total = eq.length > 1 && first! > 0 && Number.isFinite(last) ? last! / first! - 1 : null;
  // A non-positive end is a total loss: -100% a year, not a fractional power of a negative number.
  const cagr = total === null || !(yrs > 0) ? null : total <= -1 ? -1 : (1 + total) ** (1 / yrs) - 1;
  const vol = sd(r) * Math.sqrt(252), down = Math.sqrt(mean(r.map((x) => Math.min(x, 0) ** 2))) * Math.sqrt(252);
  const maxdd = Math.min(0, minMax(drawdown(eq).flatMap((d) => (d.dd === null ? [] : [d.dd])))[0]);
  const [rlo, rhi] = minMax(r);
  return { total, cagr, vol, sharpe: vol ? (mean(r) * 252) / vol : null, sortino: down ? (mean(r) * 252) / down : null, maxdd, calmar: maxdd && cagr !== null ? cagr / -maxdd : null, best: Math.max(0, rhi), worst: Math.min(0, rlo), hit: r.length ? r.filter((x) => x > 0).length / r.length : null };
}

/** Compounded return per calendar month: rows are years, columns are Jan..Dec. */
export function monthly(eq: Eq[]) {
  const last = new Map<string, number>();
  let prevKey = "", prevVal = eq[0]?.value ?? 1;
  const res = new Map<string, number | null>();
  for (const p of eq) {
    const k = p.date.slice(0, 7);
    if (k !== prevKey) { if (prevKey) last.set(prevKey, prevVal); prevKey = k; }
    prevVal = p.value; last.set(k, p.value);
  }
  let before = eq[0]?.value ?? 1;
  for (const k of [...last.keys()].sort()) { const v = last.get(k)!; res.set(k, before > 0 && Number.isFinite(v) ? v / before - 1 : null); before = v; }
  const years = [...new Set([...res.keys()].map((k) => k.slice(0, 4)))].sort();
  return { years, values: years.map((y) => Array.from({ length: 12 }, (_, m) => res.get(`${y}-${String(m + 1).padStart(2, "0")}`) ?? null)) };
}

export function rollingSharpe(eq: Eq[], window = 63) {
  const d = datedReturns(eq), r = d.map((x) => x.r);
  return r.flatMap((_, i) => { if (i + 1 < window) return []; const w = r.slice(i + 1 - window, i + 1), s = sd(w); return [{ date: d[i].date, sharpe: s ? (mean(w) / s) * Math.sqrt(252) : null }]; });
}

/** Worst move against and best move for each trade while it was open, as a fraction of the entry price. */
export function excursions(t: Trade, bars: Ohlc[]) {
  const held = bars.filter((b) => b.time >= t.entry_date && b.time <= t.exit_date);
  if (!held.length || !t.entry) return { mae: null, mfe: null };
  const hi = minMax(held.map((b) => b.high))[1], lo = minMax(held.map((b) => b.low))[0];
  const long = t.side !== "short";
  const up = hi / t.entry - 1, down = lo / t.entry - 1;
  return long ? { mae: Math.min(0, down), mfe: Math.max(0, up) } : { mae: Math.min(0, -up), mfe: Math.max(0, -down) };
}

const rng = (seed: number) => () => { seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };

/** Equity path from a start capital and a list of trade profits (additive: positions are sized from capital, so trade returns do not compound). */
const path = (capital: number, pnl: number[]) => { let v = capital, peak = capital, worst = 0; for (const x of pnl) { v += x; peak = Math.max(peak, v); worst = Math.min(worst, v / peak - 1); } return { ret: v / capital - 1, dd: worst }; };

/** Trade-order shuffling: same trades, random order. Returns final return and max drawdown per run, plus the original; null without positive capital or trades. */
export function shuffleTrades(pnl: number[], capital: number, runs: number, seed = 1) {
  if (!(capital > 0) || !pnl.length) return null;
  const rand = rng(seed), final: number[] = [], dd: number[] = [];
  for (let k = 0; k < runs; k++) {
    const a = pnl.slice();
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    const p = path(capital, a); final.push(p.ret); dd.push(p.dd);
  }
  return { orig: path(capital, pnl), final, dd };
}

/** Same sampling with replacement: the sample of trades, not just their order, changes. */
export function bootstrapTrades(pnl: number[], capital: number, runs: number, seed = 1) {
  if (!(capital > 0) || !pnl.length) return null;
  const rand = rng(seed), final: number[] = [], dd: number[] = [];
  for (let k = 0; k < runs; k++) {
    const p = path(capital, pnl.map(() => pnl[Math.floor(rand() * pnl.length)])); final.push(p.ret); dd.push(p.dd);
  }
  return { orig: path(capital, pnl), final, dd };
}

export const percentile = (xs: number[], v: number) => (xs.filter((x) => x <= v).length / (xs.length || 1)) * 100;

/** Strategy Tester summary from closed trades: net P&L, win rate, profit factor and the worst fall in cumulative P&L, in currency. */
export function tradeSummary(unsorted: { pnl?: unknown; exit_date?: unknown; date?: unknown }[]) {
  // Equity and drawdown accrue in exit order; trades often arrive in entry order.
  const at = (t: { exit_date?: unknown; date?: unknown }) => String(t.exit_date ?? t.date ?? "");
  const trades = [...unsorted].sort((a, b) => (at(a) < at(b) ? -1 : at(a) > at(b) ? 1 : 0));
  const pnl = trades.map((t) => Number(t.pnl)).filter(Number.isFinite);
  const gain = pnl.filter((x) => x > 0).reduce((s, x) => s + x, 0), loss = -pnl.filter((x) => x < 0).reduce((s, x) => s + x, 0);
  let cum = 0, peak = 0, maxdd = 0;
  const curve = trades.flatMap((t, i) => {
    const x = Number(t.pnl); if (!Number.isFinite(x)) return [];
    cum += x; peak = Math.max(peak, cum); maxdd = Math.min(maxdd, cum - peak);
    return [{ date: String(t.exit_date ?? t.date ?? i), net: cum, dd: cum - peak }];
  });
  return { net: cum, trades: pnl.length, win: pnl.length ? pnl.filter((x) => x > 0).length / pnl.length : null, pf: loss ? gain / loss : null, avg: pnl.length ? cum / pnl.length : null, maxdd, curve };
}
