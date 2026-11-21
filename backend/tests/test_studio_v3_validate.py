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


def test_trade_mc_is_deterministic_and_tells_edge_from_noise():  # V-22, V-36, V-37
    rng = np.random.default_rng(5)
    edge, zero = rng.standard_normal(200) * 100 + 40, rng.standard_normal(200) * 100
    costs = np.full(200, 5.0)
    a = V.trade_mc(edge, costs, 100_000, "skip", 500, 7, 5.0)
    b = V.trade_mc(edge, costs, 100_000, "skip", 500, 7, 5.0)
    assert np.array_equal(a["sharpe"], b["sharpe"]) and len(a["ret"]) == 500
    assert np.percentile(a["sharpe"], 5) > 0 > np.percentile(V.trade_mc(zero - 60, costs, 100_000, "slip", 500, 7, 5.0)["sharpe"], 5)
    sh, rs = V.trade_mc(edge, costs, 100_000, "shuffle", 300, 7, 5.0), V.trade_mc(edge, costs, 100_000, "resample", 300, 7, 5.0)
    assert np.allclose(sh["ret"], edge.sum() / 100_000) and rs["ret"].std() > 0 and (rs["dd"] >= 0).all()
    assert len(V.trade_mc(edge, costs, 100_000, "resample", 50, 7, 5.0)["ret"]) == 50
    assert not np.isnan(V.trade_mc(np.zeros(20), np.zeros(20), 1e5, "skip", 10, 1, 1.0)["sharpe"]).any()  # flat trades: no division by zero


def test_regime_and_year_tables_need_60_bars_to_judge():  # V-28, V-29
    import pandas as pd
    dates = pd.bdate_range("2020-01-01", periods=301)
    daily = np.full(300, 0.001)
    labels = np.array(["up"] * 100 + ["down"] * 30 + ["up"] * 171, dtype=object)
    reg, yrs = V.regime_tables(daily, labels, dates)
    assert {r["regime"]: r["judged"] for r in reg} == {"up": True, "down": False}
    assert [y["year"] for y in yrs] == [2020, 2021] and sum(y["days"] for y in yrs) == 300


def test_lookahead_check_passes_a_causal_rule():  # V-30
    from app.services.studio_v3.core import compile as C
    n = 400
    close = 100 + np.cumsum(np.random.default_rng(2).standard_normal((n, 3)), axis=0)
    bars = {"open": close, "high": close, "low": close, "close": close, "volume": np.ones_like(close)}
    import pandas as pd
    dates = pd.bdate_range("2020-01-01", periods=n)
    spec = V.Strategy(entry_long="crosses_above(sma(close, 10), sma(close, 30))", exit_long="crosses_below(sma(close, 10), sma(close, 30))")
    rows = V.lookahead(spec, bars, dates, C.signals(spec, bars, dates), 7)
    assert len(rows) == 5 and all(r["ok"] for r in rows)


def test_run_validate_new_tests_echo_sims_and_seed():
    from app.services.studio_v3.core.spec import Settings, Strategy
    spec = Strategy(entry_long="crosses_above(sma(close, 20), sma(close, 100))", exit_long="crosses_below(sma(close, 20), sma(close, 100))")
    o = V.run_validate(spec, Settings(top_n=30, seed=11), sims=10**9)
    assert o["meta"]["sims"] == V.MAX_SIMS == 100000
    assert o["meta"]["seed"] == 11
    by = {t["test"]: t for t in o["meta"]["tiles"]}
    assert {"mc_trades", "skip_trades", "regimes", "sanity", "unseen"} <= set(by)
    assert by["unseen"]["status"] in ("pass", "fail") and "cost_sweep" in o["tables"] and len(o["tables"]["cost_sweep"]) == 7
    assert o["meta"]["stress"]["runs"] == V.PROFILES["quick"]["noise"] and {"p5", "p50", "p95", "original"} <= set(o["charts"]["stress"][0])
    assert {"param_" + k for k in ()} <= set(o["tables"].get("windows", [{}])[0]) and "wfe" in o["meta"]["walk_forward"]
    few = V.run_validate(spec, Settings(symbols=["SPY", "QQQ", "IWM"]), sims=20)
    assert {t["test"]: t["status"] for t in few["meta"]["tiles"]}["unseen"] == "skipped"
