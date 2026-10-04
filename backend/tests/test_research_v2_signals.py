"""Signal formula language: parser safety, operators vs pandas, library, endpoints, saved signals."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import research_v2_signals as api
from app.services.research_v2.core import signal_lang as sl
from app.services.research_v2.core import signal_service as svc
from app.services.research_v2.core import signal_store as store
from app.services.research_v2.core.signal_library import LIBRARY

client = TestClient(FastAPI())
client.app.include_router(api.router, prefix="/api")
BASE = "/api/labs/research/v2/signals"


@pytest.fixture(scope="module")
def synth():
    rng = np.random.default_rng(0)
    dates = pd.date_range("2015-01-31", periods=60, freq="ME")
    syms = [f"S{i}" for i in range(25)]
    close = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0.01, 0.05, (60, 25)), axis=0), index=dates, columns=syms)
    ret = close.pct_change(fill_method=None)
    return {"close_m": close, "returns": ret, "dates": dates, "symbols": syms, "market_cap": close * 1e6, "daily": {}}


@pytest.mark.parametrize("bad", ["__import__('os').system('ls')", "close.__class__", "close[0]", "(lambda: 1)()", "open('x')", "eval('1')", "close if 1 else 2", "'abc'", "[1,2]", "ts_mean(close, w=3)", "ts_mean", "unknown_field + 1", "x := 1", "close ** close ** close and 1"])
def test_parser_rejects_unsafe_or_unknown_input(bad):
    with pytest.raises(sl.SignalError):
        sl.parse(bad)


def test_error_carries_character_span():
    with pytest.raises(sl.SignalError) as e:
        sl.parse("rank(close) + foo")
    assert (e.value.start, e.value.end) == (14, 17)


def test_operators_match_pandas_reference(synth):
    c, r = synth["close_m"], synth["returns"]
    pd.testing.assert_frame_equal(sl.evaluate("ts_mean(returns, 6)", synth), r.rolling(6, min_periods=6).mean())
    pd.testing.assert_frame_equal(sl.evaluate("delay(close, 1) / delay(close, 12) - 1", synth), c.shift(1) / c.shift(12) - 1)
    pd.testing.assert_frame_equal(sl.evaluate("rank(close)", synth), c.rank(axis=1, pct=True))
    z = sl.evaluate("zscore(close)", synth)
    assert np.allclose(z.mean(axis=1), 0, atol=1e-9) and np.allclose(z.std(axis=1), 1, atol=1e-9)
    pd.testing.assert_frame_equal(sl.evaluate("ts_corr(close, returns, 12)", synth), c.rolling(12, min_periods=12).corr(r))
    cond = sl.evaluate("if_else(returns > 0, 1, -1)", synth)
    assert set(np.unique(cond.dropna().to_numpy())) <= {-1.0, 1.0}
    w = sl.evaluate("winsorize(returns, 0.1)", synth).dropna(how="all")
    assert (w.max(axis=1) <= r.loc[w.index].quantile(0.9, axis=1) + 1e-12).all()


def test_forward_references_are_rejected(synth):
    with pytest.raises(sl.SignalError):
        sl.evaluate("delay(close, -1)", synth)
    with pytest.raises(sl.SignalError):
        sl.evaluate("ts_mean(close, 0)", synth)


def test_orthogonalized_signal_is_uncorrelated_with_regressor(synth):
    a, b = sl.evaluate("returns", synth), sl.evaluate("log(close)", synth)
    res = sl.orthogonalize(a + 0.5 * b, [b]).dropna(how="all")
    assert abs(res.corrwith(b.loc[res.index], axis=1).dropna()).max() < 1e-8


def test_lookahead_guard_flags_future_returns(synth):
    flagged = sl.lookahead_check(None, synth["returns"].shift(-1), synth["returns"])
    assert flagged["flagged"]
    assert not sl.lookahead_check("returns", synth["returns"], synth["returns"])["flagged"]


def test_library_has_40_formulas_that_all_compile_on_real_data():
    assert len(LIBRARY) >= 40 and len({x["id"] for x in LIBRARY}) == len(LIBRARY)
    ctx = svc.preview_ctx(40, 2520)
    cache: dict = {}
    for item in LIBRARY:
        out = sl.evaluate(item["formula"], ctx, cache)
        assert out.shape == (len(ctx["dates"]), len(ctx["symbols"])), item["id"]
        assert item["citation"] and item["expected_sign"] in (1, -1)
    assert sl.evaluate("delay(close, 1) / delay(close, 12) - 1", ctx).notna().any().any()


def test_validate_endpoint():
    ok = client.post(f"{BASE}/validate", json={"expr": "zscore(delay(close, 1) / delay(close, 12) - 1)"}).json()
    assert ok["ok"] and ok["preview"]["n_names"] > 10 and len(ok["preview"]["histogram"]) == 20 and ok["preview"]["corr_known"]
    bad = client.post(f"{BASE}/validate", json={"expr": "__import__('os')"}).json()
    assert bad["ok"] is False and {"message", "start", "end"} <= set(bad["error"])
    assert client.get(f"{BASE}/operators").json()[0]["name"]
    assert any(f["name"] == "close" for f in client.get(f"{BASE}/fields").json())
    assert len(client.get(f"{BASE}/library").json()) >= 40


def test_saved_signals_are_versioned_and_combine(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "s.sqlite")
    a = client.post(f"{BASE}/saved", json={"name": "mom", "expr": "ts_return(close, 12)"}).json()
    b = client.post(f"{BASE}/saved", json={"name": "mom", "expr": "ts_return(close, 6)"}).json()
    assert b == {"id": a["id"], "version": 2}
    assert client.post(f"{BASE}/saved", json={"name": "bad", "expr": "os.system"}).status_code == 422
    assert client.get(f"{BASE}/saved").json()[0]["latest_version"] == 2
    assert [v["version"] for v in client.get(f"{BASE}/saved/{a['id']}").json()["versions"]] == [1, 2]
    assert store.resolve_ref(f"{a['id']}@1") == "ts_return(close, 12)"
    e = client.post(f"{BASE}/combine", json={"exprs": ["ts_return(close, 12)", "-returns"], "method": "equal"}).json()["expr"]
    sl.parse(e)
    assert "zscore" in e
