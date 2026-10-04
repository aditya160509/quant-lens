"""Numerical reference checks and temporal acceptance guards."""
import numpy as np
import pandas as pd
import pytest
from sklearn.decomposition import PCA
from app.services.pca_v2.core import analytics as a
from app.services.pca_v2.core.causal import rolling_residuals


def test_eigh_matches_sklearn_and_mp_closed_form():
    x = np.random.default_rng(4).normal(size=(1000, 8))
    vals, vecs = a.eig_sorted(np.cov(x, rowvar=False))
    reference = PCA().fit(x)
    np.testing.assert_allclose(vals, reference.explained_variance_, rtol=1e-12)
    edge = a.mp_threshold(vals, 8, 1000, sigma2=1)
    assert edge["lambda_max"] == pytest.approx((1+np.sqrt(.008))**2)


def test_correlation_kaiser_and_covariance_rejection():
    assert a.choose_k(np.array([2., .8, .2]), {"lambda_max":1.5}, {"matrix_type":"correlation", "k_method":"kaiser"})["selected"] == 1
    assert a.choose_k(np.array([.02,.008,.002]), {"lambda_max":.015})["kaiser"] is None
    with pytest.raises(ValueError, match="Kaiser"):
        a.choose_k(np.ones(3), {"lambda_max":2}, {"k_method":"kaiser"})


def test_future_data_cannot_change_past_residuals_or_backtest():
    rets = pd.DataFrame(np.random.default_rng(9).normal(0,.02,size=(140,5)), index=pd.date_range("2020-01-01",periods=140), columns=list("ABCDE"))
    changed = rets.copy()
    changed.iloc[100:] *= 100
    one = rolling_residuals(rets, window=30, k=1)
    two = rolling_residuals(changed, window=30, k=1)
    pd.testing.assert_frame_equal(one.loc[:rets.index[99]],two.loc[:rets.index[99]])
    model = {"returns":rets, "annualization_factor":252}
    out1 = a.residual_ou_backtest(model, {"pca_window":30,"ou_window":30,"k":1})["equity_curve"]
    out2 = a.residual_ou_backtest({**model,"returns":changed}, {"pca_window":30,"ou_window":30,"k":1})["equity_curve"]
    pd.testing.assert_frame_equal(out1.loc[out1.date < rets.index[100]],out2.loc[out2.date < rets.index[100]])


def test_hac_matches_statsmodels():
    import statsmodels.api as sm
    from statsmodels.stats.sandwich_covariance import cov_hac
    rng=np.random.default_rng(7)
    x=sm.add_constant(rng.normal(size=(200,2)))
    fit=sm.OLS(x@np.array([1,2,3])+rng.normal(size=200),x).fit()
    assert a.newey_west_se(x,fit.resid,1,3) == pytest.approx(np.sqrt(cov_hac(fit,nlags=3)[1,1]),rel=1e-12)


def test_missing_returns_rejected_by_estimator():
    with pytest.raises(ValueError, match="finite"):
        a.covariance_estimator(pd.DataFrame([[1,2],[np.nan,3]]))


def test_planted_spike_recovered_and_condition_improves(monkeypatch):
    from app.services.pca_v2.core import model as m
    rng=np.random.default_rng(31)
    x=rng.normal(size=(160,40))*.01+rng.normal(size=(160,1))*.03
    rets=pd.DataFrame(x,columns=[str(i) for i in range(40)])
    monkeypatch.setattr(m,"load_context",lambda payload:{"payload":payload,"returns":rets,"symbols":list(rets),"sectors":{},"market_caps":{},"frequency":"daily"})
    result=m.rmt_model({"covariance_estimator":"sample"})
    assert result["k_info"]["rmt"]==1
    before=np.linalg.cond(result["raw_cov"])
    after=np.linalg.cond(result["cleaned_cov"])
    assert after < before


def test_rolling_sign_flips_are_aligned(monkeypatch):
    from app.services.pca_v2.core import regimes
    from app.services.pca_v2.core import analytics
    rng=np.random.default_rng(81)
    returns=pd.DataFrame(rng.normal(size=(100,3)),index=pd.date_range("2020-01-01",periods=100),columns=list("ABC"))
    monkeypatch.setattr(analytics,"load_context",lambda payload:{"returns":returns})
    calls=[0]
    def alternating(cov):
        calls[0]+=1
        return np.ones(3),np.eye(3)*(-1 if calls[0]%2 else 1)
    monkeypatch.setattr(analytics,"eig_sorted",alternating)
    rows=regimes.rolling_loading_evolution({},window=30,step=10)
    assert len(set(row["loading"] for row in rows if row["ticker"]=="A"))==1
