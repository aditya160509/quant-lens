"""Golden-number and look-ahead tests for the Research V2 estimators."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from app.services.research_v2.core import stats as S
from app.services.research_v2.core.estimators import fm_slopes, grs_test, two_pass
from app.services.research_v2.core.panel import compute_dependent, compute_signal


def test_nw_se_matches_statsmodels_hac() -> None:
    rng = np.random.default_rng(0)
    x = pd.Series(np.convolve(rng.normal(size=400), [1, 0.6, 0.3], mode="same"))
    ours = S.nw_se(x, lag=5)
    ref = sm.OLS(x, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": 5, "use_correction": False}).bse.iloc[0]
    assert ours == pytest.approx(ref, rel=1e-10)


def test_andrews_null_matches_published_critical_values() -> None:
    # Andrews (1993) Table 1, one parameter, 15% trimming: 10% 7.12, 5% 8.68, 1% 12.16
    q = np.quantile(S._supf_null(1, 0.15), [0.90, 0.95, 0.99])
    assert q == pytest.approx([7.12, 8.68, 12.16], abs=0.45)


def test_andrews_finds_planted_break_inside_interval() -> None:
    rng = np.random.default_rng(1)
    idx = pd.date_range("2000-01-31", periods=200, freq="ME")
    y = pd.Series(np.r_[rng.normal(0, 1, 120), rng.normal(1.2, 1, 80)], index=idx)
    res = S.andrews_sup_f(y)
    assert res["p_value"] < 0.01
    assert res["break_ci90_low"] <= idx[120] <= res["break_ci90_high"]


def test_mr_test_power_and_size() -> None:
    rng = np.random.default_rng(2)
    cols = [f"Q{i}" for i in range(1, 6)]
    rising = pd.DataFrame(rng.normal(0, 0.02, (360, 5)) + np.linspace(0, 0.02, 5), columns=cols)
    flat = pd.DataFrame(rng.normal(0, 0.02, (360, 5)), columns=cols)
    assert S.monotonic_relation_test(rising, 300)["bootstrap_p_value"] < 0.05
    assert S.monotonic_relation_test(flat, 300)["bootstrap_p_value"] > 0.10


def test_chow_test_matches_manual_formula() -> None:
    rng = np.random.default_rng(3)
    x = pd.DataFrame({"x": rng.normal(size=300)})
    g = pd.Series((np.arange(300) >= 150).astype(float))
    y = pd.Series(1 + 0.5 * x["x"] + g * 0.8 * x["x"] + rng.normal(size=300))
    res = S.chow_test(y, x, g)
    rss = lambda yy, xx: sm.OLS(yy, sm.add_constant(xx)).fit().ssr  # noqa: E731
    k = 2
    manual = ((rss(y, x) - rss(y[g == 1], x[g == 1]) - rss(y[g == 0], x[g == 0])) / k) / ((rss(y[g == 1], x[g == 1]) + rss(y[g == 0], x[g == 0])) / (300 - 2 * k))
    assert res["f_stat"] == pytest.approx(manual)
    assert res["p_value"] < 0.01


def test_grs_is_correctly_sized_under_the_null() -> None:
    rng = np.random.default_rng(4)
    rejections = 0
    for _ in range(300):
        f = pd.DataFrame({"mkt": rng.normal(0.005, 0.04, 120)})
        port = pd.DataFrame({f"Q{i}": f["mkt"] * (0.8 + 0.1 * i) + rng.normal(0, 0.02, 120) for i in range(5)})
        rejections += grs_test(port, f)["p_value"] < 0.05
    assert 0.02 <= rejections / 300 <= 0.09


def test_two_pass_shanken_multiplier_formula() -> None:
    rng = np.random.default_rng(5)
    f = pd.DataFrame({"f1": rng.normal(0.01, 0.05, 240), "f2": rng.normal(0.004, 0.03, 240)})
    betas = rng.normal(1, 0.4, (2, 12))
    assets = pd.DataFrame(f.to_numpy() @ betas + rng.normal(0, 0.02, (240, 12)), columns=[f"a{i}" for i in range(12)])
    res = two_pass(assets, f)
    lam = res["table"]["lambda_ols"].to_numpy()
    sigma_f = np.cov(f.to_numpy(), rowvar=False)
    assert res["shanken_multiplier"] == pytest.approx(np.sqrt(1 + lam @ np.linalg.inv(sigma_f) @ lam))
    assert (res["table"]["se_shanken"] > res["table"]["se_uncorrected"]).all()


def test_fm_slopes_recover_planted_premium_and_skip_nan_rows() -> None:
    rng = np.random.default_rng(6)
    dates = pd.date_range("2010-01-31", periods=60, freq="ME")
    cols = [f"S{i}" for i in range(80)]
    sig = pd.DataFrame(rng.normal(size=(60, 80)), index=dates, columns=cols)
    y = 0.02 * sig + pd.DataFrame(rng.normal(0, 0.05, (60, 80)), index=dates, columns=cols)
    sig.iloc[:10] = np.nan  # regression guard: NaN rows must be dropped, not treated as data
    slopes = fm_slopes(y, {"signal": sig})
    assert len(slopes) == 50
    assert slopes["signal"].mean() == pytest.approx(0.02, abs=0.004)


def _ctx(close: pd.DataFrame) -> dict:
    rets = close.pct_change(fill_method=None)
    return {"close_m": close, "returns": rets, "daily": {}, "market_cap": close * np.nan, "factors": pd.DataFrame(index=close.index), "symbols": list(close.columns), "dates": close.index}


def test_signals_do_not_look_ahead() -> None:
    rng = np.random.default_rng(7)
    dates = pd.date_range("2015-01-31", periods=40, freq="ME")
    close = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.05, (40, 5)), axis=0)), index=dates, columns=list("ABCDE"))
    shocked = close.copy()
    shocked.iloc[30:] *= 3.0  # change only the future
    for name in ["momentum", "reversal", "low_vol"]:
        a = compute_signal(name, _ctx(close)).iloc[:30]
        b = compute_signal(name, _ctx(shocked)).iloc[:30]
        pd.testing.assert_frame_equal(a, b)


def test_dependent_variable_is_the_next_holding_period() -> None:
    dates = pd.date_range("2015-01-31", periods=12, freq="ME")
    close = pd.DataFrame({"A": np.arange(1, 13, dtype=float)}, index=dates)
    fwd = compute_dependent("forward_return", 3, _ctx(close))
    assert fwd.loc[dates[2], "A"] == pytest.approx(close.loc[dates[5], "A"] / close.loc[dates[2], "A"] - 1)
