"""Contract, execution and no-look-ahead acceptance checks."""
import numpy as np
import pandas as pd
import pytest


def test_manifest_has_complete_feature_contracts():
    from app.services.ml_v2.registry import feature_manifest
    features = feature_manifest()
    assert len(features) == 12
    for feature in features:
        assert feature['inputs'] and feature['outputs']
        assert len({row['key'] for row in feature['inputs']}) == len(feature['inputs'])
        assert all({'key','type','label','group','default','help'} <= set(row) for row in feature['inputs'])
        assert all({'id','title','type','path','encoding','schema','primary'} <= set(row) for row in feature['outputs'])
        assert all('proxy' not in row.get('status','') for row in feature['outputs'])


def test_next_close_execution_and_actual_initial_purchase_cost():
    from app.services.ml_v2.core.portfolio import execute_portfolio
    dates = pd.date_range('2024-01-01',periods=4)
    returns = pd.DataFrame({'A':np.log([1.,1.1,1.2,1.])},index=dates)
    rows = execute_portfolio(returns,{dates[0]:{'A':1.}},100)
    assert rows[0]['equity'] == 1
    assert rows[1]['gross_return'] == 0
    assert rows[1]['equity'] == pytest.approx(1/1.01)
    assert rows[1]['turnover'] == pytest.approx(1/1.01)
    assert rows[2]['equity'] == pytest.approx(1.2/1.01)


def test_held_price_gap_is_not_filled():
    from app.services.ml_v2.core.portfolio import execute_portfolio
    dates = pd.date_range('2024-01-01',periods=3)
    returns = pd.DataFrame({'A':[0.,0.,np.nan]},index=dates)
    with pytest.raises(ValueError,match='Missing held-asset'):
        execute_portfolio(returns,{dates[0]:{'A':1.}})


def test_forward_filter_cannot_change_history_from_future_observations():
    from types import SimpleNamespace
    from app.services.ml_v2.core.regimes import forward_filter
    model = SimpleNamespace(n_components=2,startprob_=np.array([.5,.5]),
        transmat_=np.array([[.9,.1],[.2,.8]]),means_=np.array([[-1.],[1.]]),covars_=np.array([[[1.]],[[1.]]]))
    observations = np.array([[-1.],[0.],[1.],[-1.]])
    baseline = forward_filter(model,observations)
    altered = observations.copy(); altered[2:] = 100
    changed = forward_filter(model,altered)
    np.testing.assert_allclose(baseline[:2],changed[:2])
    np.testing.assert_allclose(baseline.sum(axis=1),1.)


def test_rolling_ivol_matches_ols_residual_standard_error():
    from app.services.ml_v2.core.microstructure import market_residual_ivol
    rng = np.random.default_rng(45)
    returns = pd.DataFrame(rng.normal(0,.01,(40,4)))
    actual = market_residual_ivol(returns,252).iloc[-1,0]
    window = returns.tail(21)
    design = np.column_stack([np.ones(21),window.mean(axis=1)])
    errors = window.iloc[:,0].to_numpy()-design@np.linalg.lstsq(design,window.iloc[:,0],rcond=None)[0]
    expected = np.sqrt((errors@errors)/19*252)
    assert actual == pytest.approx(expected,rel=1e-9)


@pytest.mark.parametrize('method',['static','rolling_ols','kalman'])
def test_pair_hedges_do_not_read_future_observations(method):
    from app.services.ml_v2.core.pairs import hedge_path
    rng = np.random.default_rng(25)
    x = np.cumsum(rng.normal(size=140))
    y = .8*x+rng.normal(scale=.2,size=140)
    original = hedge_path(y,x,80,method)
    perturbed = y.copy(); perturbed[110:] += 1000
    changed = hedge_path(perturbed,x,80,method)
    assert original[:30] == changed[:30]


def test_unsupported_input_is_rejected_before_execution():
    from app.services.ml_v2.features.feature_07 import run
    with pytest.raises(ValueError,match="Unsupported inputs"):
        run({"made_up_option":True})
