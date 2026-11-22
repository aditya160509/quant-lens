"""Live acceptance (PAGES L-4, L-5, L-6, L-7)."""

import numpy as np
import pytest

from app.services.studio_v3.core import live as L
from app.services.studio_v3.core import store


def test_reconcile_matches_within_two_days():  # L-5
    model = [{"symbol": "AAPL", "entry_date": "2024-01-02", "entry": 100.0, "side": "long"}, {"symbol": "MSFT", "entry_date": "2024-01-05", "entry": 50.0, "side": "long"}]
    real = [{"date": "2024-01-03", "symbol": "aapl", "price": 101.0}, {"date": "2024-02-01", "symbol": "NVDA", "price": 10.0}]
    r = L.reconcile(model, real)
    assert r["matched"] == 1 and r["skipped"] == 1 and r["extra"] == 1 and round(r["avg_fill_bps"]) == 100


def test_band_brackets_the_median():  # L-4
    p5, p50, p95 = L.band(np.random.default_rng(0).normal(0.0005, 0.01, 1000), 60, 7)
    assert (p5 <= p50).all() and (p50 <= p95).all() and len(p50) == 60


def test_freeze_segments_and_broken_channel_is_recorded(tmp_path, monkeypatch):  # L-6, L-7
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "s.db")
    L.freeze("x", 1, "2025-01-01", "human")
    L.freeze("x", 2, None, "human")
    assert [s["version"] for s in L.segments("x")] == [1, 2] and L.segments("x")[0]["backdated"]
    assert L.stop("x", 2, "human")["to"] and L.segments("x")[1]["to"]
    with pytest.raises(KeyError):
        L.stop("x", 2, "human")  # already stopped
    L.set_channels("x", ["notascheme://nothing"])
    out = L.deliver("x", "t", "b")
    assert out[0]["ok"] is False and out[0]["error"]
