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
