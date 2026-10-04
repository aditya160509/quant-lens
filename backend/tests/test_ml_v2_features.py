"""Feature-level numerical and execution regressions."""
import numpy as np
import pandas as pd
import pytest

def test_sequence_models_train_real_architectures(monkeypatch):
    pytest.importorskip("torch")
    from types import SimpleNamespace
    from app.services.ml_v2.core import panel as panel_module
    from app.services.ml_v2.features.feature_12 import run
    rng = np.random.default_rng(18)
    dates = pd.date_range("2022-01-01", periods=180)
    panel = pd.DataFrame({"date": np.tile(dates, 2), "ticker": np.repeat(["AAA", "BBB"], len(dates)),
        "mom_21": rng.normal(size=360), "ret_1d": rng.normal(scale=.01, size=360),
        "vol_21": rng.uniform(.1, .3, 360)})
    panel = panel.sort_values(["date", "ticker"]).reset_index(drop=True)
    panel["target_return"] = .01 * panel["mom_21"] + rng.normal(scale=.005, size=360)
    ctx = SimpleNamespace(returns=pd.DataFrame(index=dates), closes=pd.DataFrame(index=dates))
    monkeypatch.setattr(panel_module, "load_context", lambda *a, **kw: ctx)
    monkeypatch.setattr(panel_module, "make_feature_panel", lambda *a, **kw: (panel, panel.target_return))
    result = run({"architectures": ["patchtst", "itransformer", "lstm", "mlp"],
                  "epochs": 1, "sequence_length": 21, "transformer_depth": 1})
    rows = result["tables"]["architecture_comparison"]
    assert len(rows) == 4
    assert all(row["training_time_seconds"] > 0 for row in rows)
    assert all(np.isfinite(row["mae"]) for row in rows)
    assert result["meta"]["training"] == "actual_pytorch_cpu"
