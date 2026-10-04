"""All feature envelopes against observed-data fixtures, plus estimator contracts."""
import importlib
import numpy as np
import pandas as pd
import pytest
from app.services.pca_v2.core import analytics as a
from app.services.pca_v2.core import cross_asset as cross
from app.services.pca_v2.registry import feature_manifest, run_feature


@pytest.fixture
def market(monkeypatch):
    rng=np.random.default_rng(44)
    dates=pd.date_range("2020-01-01",periods=300,freq="B")
    names=[f"A{i}" for i in range(12)]
    returns=pd.DataFrame(rng.normal(0,.01,(300,12))+rng.normal(0,.01,(300,1)),index=dates,columns=names)
    context={"symbols":names,"returns":returns,"lookback_days":300,"frequency":"daily","annualization_factor":252,"sectors":{s:"one" if i<6 else "two" for i,s in enumerate(names)},"market_caps":dict.fromkeys(names,1),"compute_mode":"realtime"}
    from app.services.pca_v2.core import model as model_module
    loader=lambda payload=None,**kw:{**context,"payload":payload or {}}
    monkeypatch.setattr(a,"load_context",loader)
    monkeypatch.setattr(model_module,"load_context",loader)
    monkeypatch.setattr(a,"latest_market_caps",lambda symbols:dict.fromkeys(symbols,1))
    monkeypatch.setattr(a,"dollar_volume_matrix",lambda symbols,lookback_days=504:pd.DataFrame(rng.uniform(1e7,1e8,(300,len(symbols))),index=dates,columns=symbols))
    blocks={"equity":returns.iloc[:,:6],"crypto":returns.iloc[:,6:]}
    monkeypatch.setattr(cross,"load_cross_asset_blocks",lambda payload:{"blocks":blocks,"symbols":{"equity":names[:6],"crypto":names[6:]},"coverage":[],"lookback_days":300})
    monkeypatch.setattr(cross,"load_hourly_ohlcv",lambda:pd.DataFrame())
    monkeypatch.setattr(cross,"_crypto_volume_filter",lambda *args:[])
    return returns


@pytest.mark.parametrize("feature_id",[f"{i:02}" for i in range(1,12)])
def test_every_feature_produces_declared_envelope(market,feature_id):
    payload={"symbols":list(market.columns),"k":2,"bootstrap_runs":8,"pca_window":63,"ou_window":63,"max_weight":.2,"frontier_points":10,"max_breaks":1,"loading_evolution_window":63}
    result=run_feature(feature_id,payload)
    assert result["status"]=="ok"
    manifest=next(f for f in feature_manifest() if f["id"]==feature_id)
    for output in manifest["outputs"]:
        assert output["key"] in result[output["source"]]


def test_correlation_pca_preserves_asset_risk_units(market):
    model=a.rmt_model({"matrix_type":"correlation","covariance_estimator":"sample","k":2})
    assert np.diag(model["pca_cov"])==pytest.approx(np.ones(12))
    assert np.diag(model["cov"])==pytest.approx(market.var().to_numpy())
    assert a.factor_returns(model).var().to_numpy()==pytest.approx(model["eigenvalues"][:2])


def test_constraints_fail_instead_of_silently_relaxing(market):
    from app.services.pca_v2.core.optimization import optimize
    model=a.rmt_model({"k":2})
    with pytest.raises(ValueError,match="Infeasible"):
        optimize(model,{"max_weight":.01},frontier=False)
    with pytest.raises(ValueError,match="Cardinality"):
        optimize(model,{"cardinality_max":3},frontier=False)
    result=optimize(model,{"max_weight":.2,"sector_bounds":{"one":[.3,.4]},"tracking_error_max":.1},frontier=False)
    group=sum(r["weight"] for r in result["weights"] if r["sector"]=="one")
    assert .3-1e-6<=group<=.4+1e-6
