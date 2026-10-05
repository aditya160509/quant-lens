"""Constrained allocation with historical monthly refits and actual turnover."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf, OAS
from sklearn.cluster import KMeans
from .panel import load_context
from .common import response, summary, matrix_records
from .portfolio import execute_portfolio


def covariance_matrix(returns, estimator):
    clean = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 30 or (clean.std() <= 1e-12).any():
        raise ValueError("Allocation requires 30 complete nonconstant simultaneous returns")
    if estimator == "sample":
        array = clean.cov().to_numpy()
    elif estimator == "ledoit_wolf":
        array = LedoitWolf().fit(clean).covariance_
    elif estimator == "oas":
        array = OAS().fit(clean).covariance_
    elif estimator == "ewma":
        weights = .5 ** (np.arange(len(clean)-1, -1, -1) / 63.)
        weights /= weights.sum()
        centered = clean.to_numpy() - weights @ clean.to_numpy()
        array = (centered * weights[:, None]).T @ centered
    elif estimator == "rmt_cleaned":
        sample = clean.cov().to_numpy()
        standard = np.sqrt(np.diag(sample))
        correlation = sample / np.outer(standard, standard)
        values, vectors = np.linalg.eigh(correlation)
        noise = values <= (1 + np.sqrt(clean.shape[1] / len(clean)))**2
        if noise.any():
            values[noise] = values[noise].mean()
        correlation = vectors @ np.diag(values) @ vectors.T
        scale = np.sqrt(np.diag(correlation))
        correlation /= np.outer(scale, scale)
        array = correlation * np.outer(standard, standard)
    else:
        raise ValueError(f"Unsupported covariance estimator {estimator}")
    return pd.DataFrame(array, index=clean.columns, columns=clean.columns)


def hrp_weights(cov, linkage_method="ward"):
    standard = np.sqrt(np.diag(cov))
    correlation = np.clip(cov.to_numpy() / np.outer(standard, standard), -1, 1)
    distance = np.sqrt(np.maximum(0., (1-correlation)/2))
    np.fill_diagonal(distance, 0.)
    tree = linkage(squareform(distance, checks=False), method=linkage_method) if len(cov)>1 else np.empty((0,4))
    order = list(cov.index[leaves_list(tree)]) if len(tree) else list(cov.index)
    weights = pd.Series(1., index=order)
    def variance(assets):
        sub = cov.loc[assets, assets].to_numpy()
        inverse = 1/np.diag(sub)
        inverse /= inverse.sum()
        return inverse @ sub @ inverse
    clusters = [order]
    while clusters:
        cluster = clusters.pop(0)
        if len(cluster)<2:
            continue
        left, right = cluster[:len(cluster)//2], cluster[len(cluster)//2:]
        vl, vr = variance(left), variance(right)
        allocation = vr/(vl+vr)
        weights.loc[left] *= allocation
        weights.loc[right] *= 1-allocation
        clusters.extend([left,right])
    return weights.reindex(cov.index), order, tree


def optimize(cov, seed, request, sectors, objective=None):
    names = list(cov.index)
    low, high = float(request.get("min_weight",0.)), float(request.get("max_weight",.25))
    cap = float(request.get("max_sector_weight",.4))
    if not 0<=low<=high<=1 or not 0<cap<=1 or low*len(names)>1 or high*len(names)<1:
        raise ValueError("Infeasible allocation bounds")
    unknown = [name for name in names if sectors.get(name,"Unknown")=="Unknown"]
    if unknown and cap < 1:
        raise ValueError("Cannot enforce sector cap without sector metadata for: "+", ".join(unknown))
    constraints=[{"type":"eq","fun":lambda w: float(w.sum()-1)}]
    for sector in sorted({sectors.get(name,"Unknown") for name in names}):
        mask=np.array([sectors.get(name,"Unknown")==sector for name in names])
        constraints.append({"type":"ineq","fun":lambda w,mask=mask: float(cap-w[mask].sum())})
    objective=objective or (lambda w: float(np.sum((w-seed)**2)))
    fit=minimize(objective,seed,method="SLSQP",bounds=[(low,high)]*len(names),constraints=constraints,
                 options={"maxiter":500,"ftol":1e-11})
    if not fit.success or any(c["fun"](fit.x)<-1e-7 for c in constraints[1:]):
        raise ValueError(f"Allocation optimization failed: {fit.message}")
    return pd.Series(fit.x,index=names)


def minimum_variance(cov):
    seed=np.full(len(cov),1/len(cov));array=cov.to_numpy()
    fit=minimize(lambda w: float(w@array@w),seed,method="SLSQP",bounds=[(0,1)]*len(cov),
                 constraints=[{"type":"eq","fun":lambda w: float(w.sum()-1)}],options={"ftol":1e-12,"maxiter":500})
    if not fit.success:
        raise ValueError("Nested minimum-variance optimization failed")
    return pd.Series(fit.x,index=cov.index)


def nco_weights(returns):
    cov=covariance_matrix(returns,"ledoit_wolf")
    scale=np.sqrt(np.diag(cov));corr=cov.to_numpy()/np.outer(scale,scale)
    labels=KMeans(n_clusters=max(1,int(np.sqrt(len(cov)))),random_state=7,n_init=10).fit_predict(corr)
    within={};series={}
    for label in np.unique(labels):
        names=list(cov.index[labels==label]);within[label]=minimum_variance(cov.loc[names,names])
        series[label]=returns[names]@within[label]
    nested=pd.DataFrame(series).dropna()
    across=minimum_variance(covariance_matrix(nested,"ledoit_wolf"))
    weights=pd.Series(0.,index=cov.index)
    for label,cluster_weight in across.items():
        weights.loc[within[label].index]=within[label]*cluster_weight
    return weights


def allocation(returns,request,sectors):
    cov=covariance_matrix(returns,request.get("covariance_estimator","ledoit_wolf"))
    variant=request.get("optimization_variant","standard_hrp")
    hrp,order,tree=hrp_weights(cov,request.get("clustering_linkage","ward"))
    if variant=="standard_hrp":
        weights=optimize(cov,hrp.to_numpy(),request,sectors)
    elif variant=="nco":
        weights=optimize(cov,nco_weights(returns.dropna()).to_numpy(),request,sectors)
    elif variant=="min_variance":
        weights=optimize(cov,hrp.to_numpy(),request,sectors,lambda w: float(w@cov.to_numpy()@w))
    else:
        raise ValueError("Supported variants: standard_hrp, nco, min_variance")
    return weights,cov,order,tree


def run_hrp_optimizer(payload=None):
    request=payload or {};ctx=load_context(request)
    if ctx.returns.shape[1]>200:
        raise ValueError("Allocation supports up to 200 explicitly requested assets")
    weights,cov,order,tree=allocation(ctx.returns,request,ctx.sectors)
    ann=ctx.annualization
    reference=np.full(len(weights),1/len(weights))
    tau=float(request.get("black_litterman_tau",.05))
    aversion=float(request.get("risk_aversion",2.5))
    if not 0<tau<=1 or aversion<=0:
        raise ValueError("BL tau must be (0,1] and risk_aversion must be positive")
    sigma=cov.to_numpy();prior=aversion*sigma@reference
    views=request.get("views") or {}
    if not isinstance(views,dict) or set(views)-set(weights.index):
        raise ValueError("BL views must map requested assets to annual expected returns")
    posterior=prior.copy()
    if views:
        selected=[list(weights.index).index(name) for name in views]
        P=np.eye(len(weights))[selected]
        Q=np.array([float(views[name])/ann for name in views])
        if not np.isfinite(Q).all(): raise ValueError("BL views must be finite")
        omega=np.diag(np.diag(P@(tau*sigma)@P.T))
        posterior=prior+tau*sigma@P.T@np.linalg.solve(P@(tau*sigma)@P.T+omega,Q-P@prior)
    bl=optimize(cov,weights.to_numpy(),request,ctx.sectors,
                lambda w: float(.5*aversion*w@sigma@w-posterior@w))
    targets={};audit=[];window=int(request.get("allocation_window",126))
    for i in range(window,len(ctx.returns),21):
        history=ctx.returns.iloc[i-window:i]
        chosen,_,_,_=allocation(history,request,ctx.sectors)
        date=ctx.returns.index[i]
        targets[date]=chosen.to_dict()
        audit.append({"formation_date":str(date.date()),"training_end":str(history.index[-1].date()),"assets":len(chosen)})
    if not targets:
        raise ValueError("Insufficient dates for historical allocation window")
    backtest=execute_portfolio(ctx.returns,targets,float(request.get("cost_bps",5)))
    contributions=weights*(cov@weights)/float(weights@cov@weights)
    weight_rows=[{"asset":name,"weight":float(weights[name]),"sector":ctx.sectors.get(name,"Unknown")}
                 for name in weights.index]
    bl_rows=[{"asset":name,"reference_prior_return":float(prior[i]*ann),"posterior_return":float(posterior[i]*ann),
              "posterior_weight":float(bl[name])} for i,name in enumerate(weights.index)]
    tree_rows=[{"left":int(a),"right":int(b),"distance":float(c),"count":int(d)} for a,b,c,d in tree]
    return response("05",[summary("Assets",len(weights)),summary("Refits",len(audit))],
        charts={"hrp_weight_vector":weight_rows,"cluster_dendrograms":tree_rows,
                "quasi_diagonalized_covariance_heatmap":matrix_records(cov.loc[order,order],limit=200),
                "risk_contribution_decomposition":[{"asset":name,"risk_contribution":float(value)} for name,value in contributions.items()],
                "walk_forward_allocation":backtest,"black_litterman_posterior_return_vector":bl_rows,
                "bl_vs_pure_hrp_weight_comparison":[{"asset":name,"allocation_weight":float(weights[name]),"black_litterman":float(bl[name])} for name in weights.index]},
        tables={"hrp_weights":weight_rows,"allocation_training_audit":audit,"black_litterman":bl_rows},
        meta={"estimator":request.get("covariance_estimator","ledoit_wolf"),"variant":request.get("optimization_variant","standard_hrp"),
              "sector_basis":"time_invariant_current_snapshot","bl_prior":"equal_weight_reference_not_market_cap_equilibrium",
              "views_units":"annual_return","as_of_date":str(ctx.returns.index.max().date()),
              "execution":"next_close","costs":"actual_drifted_turnover","return_currency":"native; FX and borrow costs excluded"})
