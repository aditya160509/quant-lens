import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from app.services.research_v2.core.ledger_math import deflated_sharpe_hurdle, haircut_t, pbo_cscv
from app.services.research_v2.store import Store, apply_seal


def test_persistence_across_fresh_store(tmp_path):
    db = tmp_path / "r.sqlite"
    s = Store(db)
    p = s.create_project("p")
    s.save_job("j1", "01", {"signal": "mom"}, "completed", 1.0, {"summary_cards": [], "meta": {}}, project_id=p["id"])
    s2 = Store(db)
    assert s2.get_job("j1")["result"]["meta"] == {}
    assert s2.get_project(p["id"])["name"] == "p"


def test_dsr_hurdle_known_value():
    g = 0.5772156649015329
    expect = 0.1 ** 0.5 * ((1 - g) * norm.ppf(1 - 1 / 10) + g * norm.ppf(1 - 1 / (10 * np.e)))
    assert deflated_sharpe_hurdle(10, 0.1) == pytest.approx(expect)
    assert deflated_sharpe_hurdle(1, 0.1) is None


def test_haircut_bonferroni():
    h = haircut_t(3.0, 10)
    p_adj = 10 * 2 * (1 - norm.cdf(3.0))
    assert h["adjusted"] == pytest.approx(norm.ppf(1 - p_adj / 2))
    assert 0 < h["haircut"] < 1
    assert haircut_t(3.0, 1)["haircut"] == pytest.approx(0, abs=1e-9)


def test_pbo_noise_high_and_signal_low():
    rng = np.random.default_rng(1)
    noise = rng.normal(size=(400, 16))
    assert pbo_cscv(noise) > 0.3
    sig = rng.normal(size=(400, 16)) + np.linspace(0, 0.3, 16)
    assert pbo_cscv(sig) < pbo_cscv(noise)
    assert pbo_cscv(noise[:, :5]) is None


def test_ledger_and_share_roundtrip(tmp_path):
    s = Store(tmp_path / "r.sqlite")
    pid = s.create_project("p")["id"]
    for i, t in enumerate([2.0, 3.1, 1.2]):
        s.save_job(f"j{i}", "01", {"signal": f"s{i}"}, "completed", 1.0, {"summary_cards": [{"label": "L/S t-stat", "value": t}, {"label": "Sharpe", "value": t / 4}]}, project_id=pid)
    led = s.ledger(pid)
    assert led["trials"] == 3 and led["distinct_signals"] == 3 and "pbo" not in led
    assert led["deflated_sharpe_hurdle"] is not None and led["haircut_sharpe"]["haircut"] is not None
    tok = s.create_share("j1")
    got = Store(tmp_path / "r.sqlite").get_share(tok)
    assert got["feature_id"] == "01" and got["result"]["summary_cards"][0]["value"] == 3.1
    assert s.get_share("nope") is None
    s.create_prereg(pid, "h", "+", "t", "s1")
    assert s.is_preregistered(pid, {"signal": "s1"}) and not s.is_preregistered(pid, {"signal": "x"})


def test_holdout_filters_dates(tmp_path):
    s = Store(tmp_path / "r.sqlite")
    pid = s.create_project("p")["id"]
    s.set_holdout(pid, "2020-12-31")
    assert s.holdout(pid) == {"sealed_after": "2020-12-31", "unsealed": False}
    idx = pd.date_range("2020-01-31", "2021-12-31", freq="ME")
    kept = apply_seal(idx, s.sealed_after(pid), 3)
    assert kept.max() == pd.Timestamp("2020-09-30")
    s.set_holdout(pid, None)
    assert len(apply_seal(idx, s.sealed_after(pid), 3)) == len(idx)
