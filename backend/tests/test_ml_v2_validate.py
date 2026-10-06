"""Validate verdicts, upload hardening and the leakage badge, on small synthetic data."""
import time

import numpy as np
import pandas as pd
import pytest

from app.services.ml_v2.core import uploads
from app.services.ml_v2.registry import run_feature


def _csv(frame):
    return frame.to_csv(index=False).encode()


def _predictions(signal_strength, seed=3, n_dates=700, n_tickers=12):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-04", periods=n_dates)
    latent = np.zeros((n_dates, n_tickers))
    for t in range(1, n_dates):
        latent[t] = 0.8 * latent[t - 1] + rng.normal(size=n_tickers)
    outcome = signal_strength * latent + rng.normal(scale=0.01, size=latent.shape)
    prediction = latent + rng.normal(scale=0.5, size=latent.shape) if signal_strength else rng.normal(size=latent.shape)
    tickers = [f"T{i}" for i in range(n_tickers)]
    return pd.DataFrame({"date": np.repeat(dates, n_tickers), "ticker": tickers * n_dates,
                         "prediction": prediction.ravel(), "outcome": outcome.ravel()})


def _validate(frame, **extra):
    stored = uploads.store_csv(_csv(frame), "predictions")
    return run_feature("validate", {"upload_id": stored["upload_id"], "n_seeds": 3, **extra})


def test_strong_signal_held_up_and_fast():
    start = time.monotonic()
    result = _validate(_predictions(0.002))
    assert time.monotonic() - start < 20
    assert result["verdict"]["label"] == "HELD UP", result["verdict"]["checks"]
    assert result["sections"]["leakage"]["badge"] == "pass"
    assert result["sections"]["controls"]["beats_best_control"]
    assert result["sections"]["improve"]["status"] == "ok"
    assert all("provenance" in block for block in result["sections"].values())


def test_noise_strategy_not_held_up():
    result = _validate(_predictions(0.0, seed=5))
    assert result["verdict"]["label"] in {"FAILED", "MIXED"}


def test_returns_upload_with_trial_matrix():
    rng = np.random.default_rng(1)
    dates = pd.bdate_range("2020-01-01", periods=500)
    trials = pd.DataFrame(rng.normal(0, 0.01, (500, 20)), columns=[f"trial_{i + 1}" for i in range(20)])
    trials.insert(0, "date", dates)
    t = uploads.store_csv(_csv(trials), "trial_matrix")
    result = run_feature("validate", {"upload_id": t["upload_id"], "trials_upload_id": t["upload_id"]})
    assert result["sections"]["pbo"]["status"] == "computed"
    assert result["sections"]["deflated_sharpe"]["trials"] == 20
    assert result["verdict"]["label"] != "HELD UP"


@pytest.mark.parametrize("mutate,message", [
    (lambda f: f.assign(prediction=f["prediction"].astype(object).where(f.index != 3, "=1+1")), "Formula"),
    (lambda f: f.assign(date=f["date"].where(f.index != 5, pd.Timestamp("2999-01-01"))), "Future"),
    (lambda f: pd.concat([f, f.iloc[:1]]), "Duplicate"),
])
def test_upload_rejections(mutate, message):
    frame = _predictions(0.001, n_dates=40, n_tickers=3)[["date", "ticker", "prediction", "outcome"]]
    with pytest.raises(uploads.UploadError, match=message):
        uploads.parse_csv(_csv(mutate(frame)), "predictions")


def test_upload_oversize_and_binary_rejected():
    with pytest.raises(uploads.UploadError) as exc:
        uploads.parse_csv(b"date,return\n" + b"x" * (uploads.MAX_BYTES + 1), "returns")
    assert exc.value.status == 413
    with pytest.raises(uploads.UploadError, match="plain-text"):
        uploads.parse_csv(b"PK\x03\x04junk", "returns")


def test_meta_label_feature_accepts_upload_id():
    stored = uploads.store_csv(_csv(_predictions(0.002, n_dates=300)), "predictions")
    result = run_feature("04", {"upload_id": stored["upload_id"]})
    assert [row["variant"] for row in result["tables"]["label_method_comparison"]][0] == "unfiltered"


def test_cost_ranks_first_when_gross_positive_net_negative():
    rng = np.random.default_rng(9)
    dates = pd.bdate_range("2021-01-04", periods=600)
    n = 12
    pred = rng.normal(size=(600, n))
    out = 0.004 * pred + rng.normal(scale=0.01, size=pred.shape)
    frame = pd.DataFrame({"date": np.repeat(dates, n), "ticker": [f"T{i}" for i in range(n)] * 600,
                          "prediction": pred.ravel(), "outcome": out.ravel()})
    result = _validate(frame, cost_bps=60.0)
    autopsy = result["sections"]["autopsy"]
    assert autopsy["ranked_causes"][0]["cause"] == "cost_sensitivity"
    assert result["verdict"]["label"] == "FAILED"
    assert autopsy["sentence"].startswith("Fails because Gross Sharpe")
    assert result["sections"]["min_backtest_length"]["trials"] == result["sections"]["deflated_sharpe"]["trials"]


def test_manifest_has_no_market_inputs_and_requires_input():
    from app.services.ml_v2.registry import feature_manifest
    keys = {row["key"] for f in feature_manifest() if f["id"] == "validate" for row in f["inputs"]}
    assert not keys & {"symbols", "universe", "frequency", "lookback_days", "max_symbols", "as_of_date"}
    with pytest.raises(ValueError, match="Upload your returns"):
        run_feature("validate", {})


def test_validate_and_meta_label_accept_alpha_artifact():
    from app.services.ml_v2.core.common import put_artifact
    frame = _predictions(0.002, n_dates=300)
    art = put_artifact("alpha_predictions", {"horizon": 1, "heldout": {
        "date": frame["date"].dt.strftime("%Y-%m-%d").tolist(), "ticker": frame["ticker"].tolist(),
        "score": frame["prediction"].tolist(), "forward_return": frame["outcome"].tolist()}})
    result = run_feature("validate", {"artifact_id": art})
    assert result["verdict"]["label"] in {"HELD UP", "MIXED", "FAILED"} and result["meta"]["input"].startswith("artifact:")
    assert run_feature("04", {"artifact_id": art})["tables"]["label_method_comparison"][0]["variant"] == "unfiltered"
    with pytest.raises(ValueError, match="Unknown or expired"):
        run_feature("validate", {"artifact_id": "0" * 16})


def test_autopsy_wording_short_sample_over_100_percent():
    from app.services.ml_v2.core.validate_engine import _span
    assert _span(pd.Timestamp("2025-04-01"), pd.Timestamp("2025-06-30"), pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")) == "Apr–Jun 2025"
    rng = np.random.default_rng(4)
    dates = pd.bdate_range("2025-01-06", periods=240)
    n = 8
    pred = rng.normal(size=(240, n))
    out = rng.normal(scale=0.01, size=pred.shape)
    out[60:120] += 0.012 * pred[60:120]       # profit only in one stretch
    out[:60] -= 0.004 * pred[:60]
    out[120:] -= 0.004 * pred[120:]
    frame = pd.DataFrame({"date": np.repeat(dates, n), "ticker": [f"T{i}" for i in range(n)] * 240,
                          "prediction": pred.ravel(), "outcome": out.ravel()})
    autopsy = _validate(frame, cost_bps=0.0)["sections"]["autopsy"]
    text = " ".join(c["phrase"] for c in autopsy["ranked_causes"])
    assert "2025-2025" not in text and "%  of profit" not in text
    assert "short_history" in {c["cause"] for c in autopsy["ranked_causes"]}
    assert "too little out-of-sample history" in text
    regime = next(c for c in autopsy["ranked_causes"] if c["cause"] == "regime_dependence")
    if "supplies 1" in regime["evidence"] and "% of total" in regime["evidence"] and int(regime["evidence"].split("supplies ")[1].split("%")[0]) > 100:
        assert "earned more than the whole period's profit" in regime["phrase"]
