"""Validate acceptance (PAGES V-1, V-4, V-5, V-7, V-8)."""

import numpy as np
import pytest

from app.services.studio_v3.core import store
from app.services.studio_v3.core import validate as V
from app.services.studio_v3.core.backtest import Refusal


def _tiles(**status):
    return [V._tile(k, s, finding=f"{k} finding") for k, s in status.items()]


def test_lucky_strategy_is_graded_down_with_luck_named():  # V-1
    rng = np.random.default_rng(3)
    daily = rng.standard_normal(1260) * 0.01 + 0.0004  # Sharpe about 0.6 over 5 years
    lk = V.luck(daily, 5.0, {"raw": 2000, "effective": 400.0}, list(rng.standard_normal(400) * 0.4), 7)
    assert lk["lottery_p95"] > lk["sharpe"] and lk["dsr"] < 0.95
    g = V.grade(_tiles(walk_forward="fail", vs_random="fail", noise="pass", dsr="fail", pbo="fail"), few=False)
    assert g["grade"] in ("D", "F") and g["reason"].startswith("luck")


def test_robust_strategy_passes():  # V-1
    g = V.grade(_tiles(walk_forward="pass", vs_random="pass", noise="pass", mcpt="pass", delay="pass", costs="pass", parameters="pass", dsr="pass", pbo="pass"), few=False)
    assert g["grade"] == "A"


def test_few_trades_cap_the_grade():  # V-8
    g = V.grade(_tiles(walk_forward="skipped", noise="pass", costs="pass", dsr="pass"), few=True)
    assert g["grade"] == "C" and g["cap"] == "C"


def test_weights_change_the_grade_without_a_run():  # V-7
    tiles = _tiles(walk_forward="pass", noise="fail", costs="fail")
    before = V.grade(tiles, few=False)["grade"]
    for t in tiles:
        t["weight"] = 10 if t["test"] == "walk_forward" else 1
    assert V.grade(tiles, few=False)["grade"] < before  # A sorts before F


def test_holdout_looks_are_logged_and_agents_have_a_budget(tmp_path, monkeypatch):  # V-4, V-5
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "studio.sqlite")
    sid = store.create(V.Strategy(entry_long="close > sma(close, 50)"))["id"]
    for _ in range(3):
        V.open_holdout(sid, 1, "agent:test")
    with pytest.raises(Refusal):
        V.open_holdout(sid, 1, "agent:test")
    V.open_holdout(sid, 1, "human")
    looks = V.holdout_looks(sid)
    assert [x["actor"] for x in looks] == ["agent:test"] * 3 + ["human"]


def test_pbo_flags_noise_and_clears_a_real_edge():
    rng = np.random.default_rng(0)
    noise = rng.standard_normal((800, 16)) * 0.01
    assert V.pbo_cscv(noise) > 0.3
    edge = noise + np.linspace(0, 0.002, 16)  # higher index, steadily better everywhere
    assert V.pbo_cscv(edge) < 0.1


def test_cpcv_and_anchored_walk_forward_pick_the_real_edge():
    import pandas as pd
    rng = np.random.default_rng(1)
    rets = rng.standard_normal((1000, 8)) * 0.01 + np.linspace(0, 0.001, 8)
    curves = [({"k": j}, np.concatenate([[1.0], np.cumprod(1 + rets[:, j])])) for j in range(8)]
    dates = pd.bdate_range("2015-01-01", periods=1001)
    cp = V.cpcv(curves, dates)
    assert cp["splits"] == 15 and cp["paths"] == 5 and cp["share_positive"] == 1.0
    s, rows, _ = V.walk_forward(curves, dates, 4, anchored=True, purge=5)
    assert len(rows) == 4 and s["oos_sharpe"] > 0


def test_validation_is_reproducible():  # V-3: same spec, settings and data give the same tile hash
    from app.services.studio_v3.core.spec import Settings, Strategy
    spec = Strategy(entry_long="crosses_above(sma(close, f), sma(close, 100))", exit_long="crosses_below(sma(close, f), sma(close, 100))",
                    params={"f": {"value": 20, "min": 10, "max": 50, "step": 10}})
    a = V.run_validate(spec, Settings(symbols=["SPY", "QQQ", "IWM"]))
    b = V.run_validate(spec, Settings(symbols=["SPY", "QQQ", "IWM"]))
    assert a["meta"]["result_hash"] == b["meta"]["result_hash"]
