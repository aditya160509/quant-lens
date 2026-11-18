"""Portfolio acceptance (PAGES P-1, P-2)."""

import numpy as np
import pandas as pd

from app.services.studio_v3.core import portfolio as P


def test_equal_weight_is_the_mean_of_daily_returns():  # P-1
    r = pd.DataFrame({"a": [0.01, -0.02, 0.03], "b": [0.0, 0.01, -0.01]})
    w = P._weights(r, "equal")
    assert np.allclose(w, [0.5, 0.5]) and np.allclose(r.to_numpy() @ w, [0.005, -0.005, 0.01])


def test_switch_acts_on_the_next_bar():  # P-2: no look-ahead
    dates = pd.bdate_range("2020-01-01", periods=300)
    close = np.r_[np.linspace(100, 200, 250), np.linspace(200, 120, 50)]
    on = P.switch_series("close > sma(close, 200)", close, dates)
    raw = close > pd.Series(close).rolling(200).mean().to_numpy()
    assert not on[0] and np.array_equal(on[1:], raw[:-1])


def test_min_variance_is_long_only_and_sums_to_one():
    rng = np.random.default_rng(0)
    r = pd.DataFrame(rng.standard_normal((500, 4)) * [0.01, 0.02, 0.03, 0.01])
    w = P._weights(r, "min_variance")
    assert (w >= 0).all() and abs(w.sum() - 1) < 1e-9


def test_risk_parity_hrp_and_rolling_weights():
    import numpy as np
    import pandas as pd

    from app.services.studio_v3.core import portfolio as P
    rng = np.random.default_rng(0)
    r = pd.DataFrame(rng.standard_normal((600, 4)) * [0.005, 0.01, 0.02, 0.01], columns=list("abcd"), index=pd.bdate_range("2020-01-01", periods=600))
    w = P._weights(r, "risk_parity")
    rc = w * (r.cov().to_numpy() @ w)
    assert abs(w.sum() - 1) < 1e-9 and rc.max() / rc.min() < 1.05  # equal risk contributions
    h = P._weights(r, "hrp")
    assert abs(h.sum() - 1) < 1e-9 and h[0] > h[2]  # the quiet name gets more
    out, hist = P.rolling(r, "inverse_vol")
    assert np.allclose(out[:253], r.iloc[:253].mean(1))  # equal weight until a year of history: no look-ahead
    assert hist[0]["date"] == str(r.index[253].date())


def test_cap_redistributes_and_frontier_dominates_members():
    w = P._cap(np.array([0.7, 0.2, 0.1]), 0.4)
    assert abs(w.sum() - 1) < 1e-9 and w.max() <= 0.4 + 1e-9 and w[1] > w[2]  # excess goes in proportion
    rng = np.random.default_rng(1)
    r = pd.DataFrame(rng.standard_normal((800, 3)) * 0.01 + [0.0004, 0.0002, 0.0003], columns=list("abc"))
    md = P._weights(r, "max_diversification")
    assert (md >= 0).all() and abs(md.sum() - 1) < 1e-9
    f = P.frontier(r)
    assert len(f) > 5 and max(p["ret"] for p in f) >= r.mean().max() * 252 * 0.95  # frontier reaches the best member's return


def test_analytics_netting_dropout_and_grade():
    from types import SimpleNamespace as NS
    dates = pd.bdate_range("2018-01-01", periods=700)
    rng = np.random.default_rng(2)
    r = pd.DataFrame(rng.standard_normal((700, 3)) * 0.01 + 0.0005, columns=["a", "b", "c"], index=dates)
    pos = np.zeros((700, 1)); pos[100:200] = 10  # a and b hold opposite sides: netting removes all of it
    res = {"a": NS(traded=np.ones(700), positions=pos), "b": NS(traded=np.ones(700), positions=-pos), "c": NS(traded=np.ones(700), positions=np.zeros((700, 1)))}
    w = np.ones(3) / 3
    eq = 1e5 * np.cumprod(1 + r.to_numpy() @ w)
    out = P.analytics(r, w, eq, dates, 1e5, None, res, {}, list(r.columns), "equal", "", 7)
    assert out["stats"]["netting"]["saved"] == 1.0
    assert abs(out["stats"]["effective_bets"] - 3) < 1e-9 and len(out["tables"]["dropout"]) == 3
    assert out["grade"]["grade"] in "ABCDF" and {t["test"] for t in out["tiles"]} >= {"dsr", "walk_forward"}


def _r(n=300, seed=3, k=3):
    return pd.DataFrame(np.random.default_rng(seed).standard_normal((n, k)) * 0.01 + 0.0003, columns=list("abcd")[:k], index=pd.bdate_range("2020-01-01", periods=n))


def test_new_methods_are_long_only_and_sum_to_one():  # P-6
    r = _r(400)
    for m in ("min_variance_shrunk", "capped_kelly", "member_momentum", "drawdown_throttle"):
        w = P._weights(r, m)
        assert (w >= 0).all() and abs(w.sum() - 1) < 1e-9, m
    assert P._weights(_r(400, k=4), "capped_kelly").max() <= 0.25 + 1e-9
    r["a"] = -0.001
    assert P._weights(r, "member_momentum")[0] == 0  # negative trailing return gets nothing


def test_drawdown_throttle_is_causal_and_cuts_exposure():  # P-6
    r = pd.DataFrame({"a": [0.0, -0.5, 0.0, 0.0], "b": [0.0, 0.0, 0.0, 0.0]})
    out, _ = P.rolling(r, "drawdown_throttle")
    # bar 1 uses the weights known after bar 0 (full); bar 2 sees a at -50% and holds half of 1/2
    assert np.allclose(out, [0.0, -0.25, 0.0, 0.0]) and np.allclose(P._weights(r, "drawdown_throttle"), [1 / 3, 2 / 3])


def test_threshold_never_trades_inside_the_corridor():  # P-7
    r = pd.DataFrame({"a": [0.001] * 20, "b": [0.0] * 20})
    out, n, turn = P.threshold(r, np.array([0.5, 0.5]))
    assert n == 0 and turn == 0 and out[0] == 0.0005
    big = pd.DataFrame({"a": [0.2] * 5, "b": [0.0] * 5})
    _, n, turn = P.threshold(big, np.array([0.5, 0.5]))
    assert n >= 1 and turn > 0
    _, n, _ = P.threshold(big, np.array([0.5, 0.5]), min_trade=0.9)
    assert n == 0  # every trade is below the minimum


def test_sleeves_disable_start_and_scale():  # P-5
    r = _r(200, k=2)
    out = P.apply_sleeves(r, {"a": "x", "b": "y"}, {"x": {"enabled": False}, "y": {"start": str(r.index[100].date())}})
    assert (out["a"] == 0).all() and (out["b"][:100] == 0).all() and np.allclose(out["b"][100:], r["b"][100:])
    sc = P.apply_sleeves(r, {"a": "x", "b": "y"}, {"x": {"vol_target": 0.05}})
    assert np.allclose(sc["a"][:63], r["a"][:63]) and not np.allclose(sc["a"], r["a"]) and np.allclose(sc["b"], r["b"])


def test_sleeve_bad_date_is_refused():
    import pytest

    from app.services.studio_v3.core.backtest import Refusal
    with pytest.raises(Refusal):
        P.apply_sleeves(_r(50, k=2), {"a": "x"}, {"x": {"start": "not a date"}})


def test_run_exposes_member_ids_for_deploy():
    from app.services.studio_v3.features import feature_04 as F
    m = F.run({"strategy_ids": "6a211f9e020a 3713c9254031"})["meta"]
    assert [d["name"] for d in m["member_ids"]] == m["names"] and abs(sum(d["weight"] for d in m["member_ids"]) - 1) < 1e-9


def test_mean_variance_shrunk_long_only_and_capped():  # P-6
    r = _r(400, k=4)
    w = P._weights(r, "mean_variance_shrunk")
    assert (w >= 0).all() and abs(w.sum() - 1) < 1e-9 and P._cap(w.copy(), 0.4).max() <= 0.4 + 1e-9


def test_sleeve_capital_scales_and_is_bounded():  # P-5
    import pytest

    from app.services.studio_v3.core.backtest import Refusal
    r = _r(100, k=2)
    out = P.apply_sleeves(r, {"a": "x", "b": "y"}, {"x": {"capital": 0.5}})
    assert np.allclose(out["a"], r["a"] * 0.5) and np.allclose(out["b"], r["b"])
    with pytest.raises(Refusal):
        P.apply_sleeves(r, {"a": "x"}, {"x": {"capital": 2}})


def _panel_and_result():
    from types import SimpleNamespace as NS
    T = 40
    close = np.full((T, 3), 100.0)
    tr = np.zeros((1, 15)); tr[0, [0, 1, 2, 3, 4, 6]] = [1, 1, 5, T - 1, 100, 10]  # symbol 1, long, 10 sh, bars 5..end
    tr[0, 11] = 7  # open at end
    return NS(close=close, volume=np.full((T, 3), 1e5), symbols=("A", "B", "C"), dates=pd.bdate_range("2020-01-01", periods=T)), NS(trades=tr, equity=np.full(T, 1e4))


def test_capacity_book_and_overlay():  # P-9, P-11, P-23
    panel, res = _panel_and_result()
    c = P.capacity(res, panel, 1e4)
    assert c["avg_trade"] == 1000 and abs(c["capacity"] - 1e4 * 0.01 * 1e7 / 1000) < 1e-6  # 1% of 1e7 dollar volume
    assert P.capacity(type(res)(trades=res.trades[:0], equity=res.equity), panel, 1e4) is None
    E = P._book(res, panel)
    assert E[4, 1] == 0 and np.allclose(E[5:, 1], 0.1) and np.allclose(P._book(res, panel, 39), E[-1:])
    r, info = P.overlay(np.full(40, 0.01), E, panel.symbols, {"max_symbol": 0.05})
    assert np.allclose(r[7:], 0.005) and r[5] == 0.01 and info["bars_cut"] > 0  # cut from the bar after the breach
    stats, _ = P.book_view(E[-1], panel, None)
    assert abs(stats["book_gross"] - 0.1) < 1e-9 and stats["book_beta"] is None


def test_run_with_limits_ban_and_bad_input():  # P-5, P-11
    import pytest

    from app.services.studio_v3.core.backtest import Refusal
    from app.services.studio_v3.features import feature_04 as F
    ids = "6a211f9e020a 3713c9254031"
    with pytest.raises(Refusal):
        F.run({"strategy_ids": ids, "max_gross": -1})
    out = F.run({"strategy_ids": ids, "max_gross": 0.5, "ban": "AAPL", "method": "mean_variance_shrunk"})
    assert out["meta"]["constraints"]["limits"] == {"max_gross": 0.5} and out["meta"]["banned"] == ["AAPL"] and len(out["tables"]["capacity"]) == 2
