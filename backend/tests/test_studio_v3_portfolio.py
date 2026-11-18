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
