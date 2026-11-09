import numpy as np
import pandas as pd
import pytest

from app.services.ml_v2.core import stats as ml_stats
from app.services.screener_v2.core.backtest import cscv_pbo as screener_pbo
from app.services.shared.stats import cscv_pbo, deflated_sharpe_probability


@pytest.fixture
def returns():
    rng = np.random.default_rng(42)
    return pd.DataFrame(rng.normal(0.0005, 0.01, (480, 6)), columns=list("abcdef"))


def test_golden_pbo_matches_every_caller(returns):
    assert cscv_pbo(returns)["pbo"] == pytest.approx(32 / 70)
    assert screener_pbo(returns)["pbo"] == pytest.approx(32 / 70)
    assert ml_stats.cscv_pbo is cscv_pbo


def test_golden_deflated_sharpe(returns):
    assert deflated_sharpe_probability(returns.a, 6, 0.01) == pytest.approx(0.002942997059407358)
