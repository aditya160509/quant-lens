"""Studio v3 engine: the fill model on hand-built bars, and the vector engine against the event engine trade for trade."""

import time

import numpy as np
import pytest

from app.services.studio_v3.core import engine, fills
from app.services.studio_v3.core.engine import Params

FREE = {"commission_bps": 0.0, "slippage_bps": 0.0, "borrow_bps": 0.0}


def bars(o, h, l, c, v=None):
    f = lambda a: np.asarray(a, dtype=float).reshape(len(a), -1)
    return {"open": f(o), "high": f(h), "low": f(l), "close": f(c), "volume": f(v if v is not None else [1e9] * len(o))}


def sig(T, entries=(), exits=(), n=1):
    e, x = np.zeros((T, n), dtype=np.int8), np.zeros((T, n), dtype=np.int8)
    for t in entries:
        e[t, 0] = 1
    for t in exits:
        x[t, 0] = 1
    return e, x


def both(b, e, x, p, **kw):
    v, ev = engine.run(b, e, x, p, **kw), engine.run(b, e, x, p, engine="event", **kw)
    assert v.trades.shape == ev.trades.shape
    np.testing.assert_allclose(v.trades, ev.trades, rtol=1e-9, atol=1e-9, equal_nan=True)
    np.testing.assert_allclose(v.equity, ev.equity, rtol=1e-9)
    np.testing.assert_allclose(v.gross_equity, ev.gross_equity, rtol=1e-9)
    assert v.unfilled == ev.unfilled
    return v


def test_signal_fills_at_next_open_and_same_close_is_a_switch():
    b = bars([10, 11, 12, 13, 14], [10, 11, 12, 13, 14], [10, 11, 12, 13, 14], [10, 11, 12, 13, 14])
    e, x = sig(5, [0], [2])
    r = both(b, e, x, Params(size_mode=fills.SHARES, size=10, **FREE))
    assert r.trades[0, [engine.T_ENTRY_BAR, engine.T_EXIT_BAR, engine.T_ENTRY_PX, engine.T_EXIT_PX, engine.T_PNL]].tolist() == [1, 3, 11, 13, 20]
    r = both(b, e, x, Params(fill=1, size_mode=fills.SHARES, size=10, **FREE))
    assert r.trades[0, [engine.T_ENTRY_BAR, engine.T_EXIT_BAR, engine.T_ENTRY_PX, engine.T_EXIT_PX]].tolist() == [0, 2, 10, 12]


def test_gap_through_stop_fills_at_the_open_not_the_stop():  # K-3
    b = bars([100, 100, 80, 80], [100, 101, 82, 80], [100, 99, 78, 80], [100, 100, 80, 80])
    e, x = sig(4, [0])
    r = both(b, e, x, Params(stop=0.10, size_mode=fills.SHARES, size=1, **FREE))
    t = r.trades[0]
    assert (t[engine.T_EXIT_BAR], t[engine.T_EXIT_PX], t[engine.T_REASON]) == (2, 80.0, engine.R_STOP)  # stop was 90


def test_stop_and_target_in_one_bar_fills_the_stop_first():
    b = bars([100, 100, 100], [100, 100, 112], [100, 100, 88], [100, 100, 100])
    e, x = sig(3, [0])
    p = Params(stop=0.10, target=0.10, size_mode=fills.SHARES, size=1, **FREE)
    assert both(b, e, x, p).trades[0, engine.T_REASON] == engine.R_STOP


def test_time_stop_breakeven_and_scale_out_exact_trades():  # B-8
    flat = [100.0] * 8
    e, x = sig(8, [0])
    r = both(bars(flat, flat, flat, flat), e, x, Params(time_stop=3, size_mode=fills.SHARES, size=1, **FREE))
    assert r.trades[0, [engine.T_ENTRY_BAR, engine.T_EXIT_BAR, engine.T_REASON]].tolist() == [1, 4, engine.R_TIME]
    # breakeven: +5% on bar 2 moves the stop to 100; bar 3 trades down to 99
    b = bars([100, 100, 100, 101, 100], [100, 100, 106, 101, 100], [100, 100, 100, 99, 100], [100, 100, 105, 100, 100])
    e, x = sig(5, [0])
    r = both(b, e, x, Params(stop=0.10, breakeven=0.05, size_mode=fills.SHARES, size=1, **FREE))
    assert r.trades[0, [engine.T_EXIT_BAR, engine.T_EXIT_PX, engine.T_REASON, engine.T_PNL]].tolist() == [3, 100, engine.R_BREAKEVEN, 0]
    # scale out half at +10%, the rest leaves on the signal
    b = bars([100, 100, 100, 108, 108], [100, 100, 111, 108, 108], [100, 100, 100, 108, 108], [100, 100, 108, 108, 108])
    e, x = sig(5, [0], [3])
    r = both(b, e, x, Params(scale_at=0.10, scale_frac=0.5, size_mode=fills.SHARES, size=10, **FREE))
    np.testing.assert_allclose(r.trades[:, [engine.T_EXIT_BAR, engine.T_EXIT_PX, engine.T_SHARES, engine.T_REASON, engine.T_PNL]],
                               [[2, 110, 5, engine.R_SCALE, 50], [4, 108, 5, engine.R_SIGNAL, 40]])


def test_costs_borrow_and_delisting_settle():
    b = bars([100, 100, 100, np.nan], [100, 100, 100, np.nan], [100, 100, 100, np.nan], [100, 100, 90, np.nan])
    e, x = sig(4, [0])
    r = both(b, e, x, Params(size_mode=fills.SHARES, size=10, commission_bps=10, slippage_bps=0, borrow_bps=0, delist_haircut=0.5))
    t = r.trades[0]
    assert (t[engine.T_REASON], t[engine.T_EXIT_PX]) == (engine.R_DELISTED, 45.0)
    assert t[engine.T_PNL] == pytest.approx(10 * (45 - 100) - 1.0 - 0.45)
    assert r.gross_equity[-1] - r.equity[-1] == pytest.approx(1.45)


def random_market(T=400, N=12, seed=0):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.02, (T, N)), axis=0))
    o = np.vstack([c[:1], c[:-1]]) * (1 + rng.normal(0, 0.006, (T, N)))
    h, l = np.maximum(o, c) * (1 + rng.uniform(0, 0.02, (T, N))), np.minimum(o, c) * (1 - rng.uniform(0, 0.02, (T, N)))
    v = rng.uniform(1e4, 1e6, (T, N))
    c[300:, 3] = np.nan  # one name delists
    c[50:60, 5] = np.nan  # one has a gap in its history
    for a in (o, h, l, v):
        a[np.isnan(c)] = np.nan
    e = (rng.random((T, N)) < 0.05).astype(np.int8) * rng.choice(np.array([1, 1, -1], dtype=np.int8), (T, N))
    x = (rng.random((T, N)) < 0.08).astype(np.int8) * rng.integers(1, 4, (T, N), dtype=np.int8)
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}, e, x, rng.normal(size=(T, N)), c * 0.03


@pytest.mark.parametrize("p", [
    Params(),
    Params(stop=0.05, target=0.08, max_positions=4, size_mode=fills.EQUAL),
    Params(trail=0.06, time_stop=15, size_mode=fills.PCT_EQUITY, size=0.2, volume_cap=0.001),
    Params(stop=0.04, breakeven=0.03, scale_at=0.05, scale_frac=0.5, target=0.12, size_mode=fills.RISK, size=0.01, max_positions=5),
    Params(fill=1, stop=0.05, target=0.05, max_positions=3, size_mode=fills.CASH, size=20_000, leverage=2.0, slippage_range=0.05),
    Params(stop=0.05, max_positions=4, size_mode=fills.SCORE),
    Params(stop=0.05, target=0.08, max_positions=4, size_mode=fills.KELLY, size=0.25),
], ids=["defaults", "bracket", "trail_time_volcap", "risk_breakeven_scale", "same_close_leverage", "score_weight", "kelly"])
def test_vector_engine_matches_event_engine_trade_for_trade(p):
    b, e, x, score, dist = random_market()
    r = both(b, e, x, p, score=score)
    assert len(r.trades) > 20
    both(b, e, x, p, score=score, stop_dist=dist)
    again = engine.run(b, e, x, p, score=score)  # K-2: same run twice, identical bytes
    assert again.trades.tobytes() == r.trades.tobytes() and again.equity.tobytes() == r.equity.tobytes()


def test_vol_target_sizing_matches_across_engines_and_shrinks_volatile_names():
    b, e, x, score, _ = random_market()
    vol = np.full(b["close"].shape, 0.2)
    vol[:, 0] = 0.8  # one name four times as volatile
    p = Params(size_mode=fills.VOL, size=0.15, max_positions=5)
    r = both(b, e, x, p, score=score, size_vol=vol)
    value = r.trades[:, engine.T_SHARES] * r.trades[:, engine.T_ENTRY_PX]
    calm, wild = value[r.trades[:, engine.T_SYM] != 0], value[r.trades[:, engine.T_SYM] == 0]
    assert len(wild) and np.median(wild) < np.median(calm) / 3


def test_equity_is_cash_plus_marked_positions_and_reconciles_with_trades():
    b, e, x, _, _ = random_market()
    p = Params(stop=0.05, target=0.08, max_positions=4)
    r = engine.run(b, e, x, p)
    assert r.equity[-1] - p.capital == pytest.approx(r.trades[:, engine.T_PNL].sum(), rel=1e-9)


def test_sma_cross_500_names_10_years_speed():  # K-9: measured, budget 5 s cold
    from app.services.screener_v2.core import data_loader
    from app.services.studio_v3.core import data

    if not data_loader.MARKET_UNIVERSE.exists():
        pytest.skip("market parquet not present")
    symbols = data_loader.parse_symbols({"max_symbols": 500}, default_limit=500)
    t0 = time.perf_counter()
    p = data.panel(symbols, "2016-01-01", "2026-01-01")
    c = p.close
    csum = np.nancumsum(c, axis=0)
    sma = lambda w: (csum - np.vstack([np.zeros((w, c.shape[1])), csum[:-w]])) / w
    fast, slow = sma(50), sma(200)
    up = fast > slow
    e = np.zeros(c.shape, dtype=np.int8)
    e[1:][up[1:] & ~up[:-1]] = 1
    e[:200] = 0
    x = np.zeros(c.shape, dtype=np.int8)
    x[1:][~up[1:] & up[:-1]] = 1
    load = time.perf_counter() - t0
    params = Params(max_positions=50)
    t1 = time.perf_counter()
    r = engine.run(p.bars(), e, x, params)
    run = time.perf_counter() - t1
    print(f"\nK-9 {len(p.symbols)} names x {len(p.dates)} bars: load+signals {load:.2f}s, engine {run:.3f}s (incl. JIT if cold), {len(r.trades)} trades")
    assert len(p.symbols) >= 400 and len(r.trades) > 100
    assert load + run < 5.0


def test_on_fill_delivers_executed_orders_before_the_bar_callback():
    b = bars([100, 101, 101], [100, 101, 114], [100, 101, 88], [100, 101, 101])
    entries, exits = sig(3, [0])
    events = []

    class Strategy(engine.SignalStrategy):
        def on_fill(self, ctx, fill):
            events.append(("fill", ctx.t, fill))

        def on_bar(self, ctx):
            events.append(("bar", ctx.t))
            super().on_bar(ctx)

    params = Params(stop=0.10, target=0.10, size_mode=fills.SHARES, size=2, commission_share=0.25,
                    volume_cap=1e-9, **FREE)
    result = engine.run(b, entries, exits, params, strategy=Strategy(entries, exits))
    assert events == [
        ("bar", 0),
        ("fill", 1, engine.Fill(0, 1, "buy", 1, 101, 0.25)),
        ("bar", 1),
        ("fill", 2, engine.Fill(0, 2, "sell", 1, 90.9, 0.25)),
        ("bar", 2),
    ]
    assert result.trades[0, engine.T_REASON] == engine.R_STOP
    assert result.unfilled == 1


def test_on_fill_delivers_same_close_entry_and_delisting():
    b = bars([10, 11, np.nan], [10, 11, np.nan], [10, 11, np.nan], [10, 11, np.nan])
    entries, exits = sig(3, [0])
    events = []

    class Strategy(engine.SignalStrategy):
        def on_fill(self, ctx, fill):
            events.append(("fill", ctx.t, fill))

        def on_bar(self, ctx):
            events.append(("bar", ctx.t))
            super().on_bar(ctx)

    p = Params(fill=1, size_mode=fills.SHARES, size=2, **FREE)
    engine.run(b, entries, exits, p, strategy=Strategy(entries, exits))
    assert events == [
        ("bar", 0),
        ("fill", 0, engine.Fill(0, 0, "buy", 2, 10, 0)),
        ("bar", 1),
        ("fill", 1, engine.Fill(0, 1, "sell", 2, 11, 0)),
        ("bar", 2),
    ]
