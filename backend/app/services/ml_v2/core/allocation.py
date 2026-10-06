"""Constrained allocation with historical monthly refits and actual turnover."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf, OAS
from sklearn.cluster import KMeans
from .common import build_provenance, get_artifact, put_artifact, response, summary, matrix_records
from .data_loader import normalize_symbol, universe_label
from .panel import load_context
from .performance import fast_spearman_ic, max_drawdown, sharpe
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


def optimize(cov, seed, request, sectors, objective=None, gradient=None):
    names = list(cov.index)
    low, high = float(request.get("min_weight",0.)), float(request.get("max_weight",.25))
    cap = float(request.get("max_sector_weight",.4))
    if not 0<=low<=high<=1 or not 0<cap<=1 or low*len(names)>1 or high*len(names)<1:
        raise ValueError("Infeasible allocation bounds")
    constraints=[{"type":"eq","fun":lambda w: float(w.sum()-1),"jac":lambda w: np.ones(len(w))}]
    # Names without sector metadata are exempt from the sector cap (reported by the caller).
    for sector in sorted({sectors.get(name,"Unknown") for name in names}-{"Unknown"}):
        mask=np.array([sectors.get(name,"Unknown")==sector for name in names])
        constraints.append({"type":"ineq","fun":lambda w,mask=mask: float(cap-w[mask].sum()),"jac":lambda w,mask=mask: -mask.astype(float)})
    objective=objective or (lambda w: float(np.sum((w-seed)**2)))
    gradient=gradient or (lambda w: 2*(w-seed))
    fit=minimize(objective,seed,jac=gradient,method="SLSQP",bounds=[(low,high)]*len(names),constraints=constraints,
                 options={"maxiter":500,"ftol":1e-11})
    if not fit.success or any(c["fun"](fit.x)<-1e-7 for c in constraints[1:]):
        raise ValueError(f"Allocation optimization failed: {fit.message}")
    return pd.Series(fit.x,index=names)


def relax_infeasible_bounds(request,names,sectors):
    """Loosen max_weight and max_sector_weight just enough to be feasible (few names or one sector); returns the request and notes."""
    high,cap=float(request.get("max_weight",.25)),float(request.get("max_sector_weight",.4))
    labels=pd.Series([sectors.get(n,"Unknown") for n in names]);unknown=int((labels=="Unknown").sum());counts=labels[labels!="Unknown"].value_counts()
    notes=[f"{unknown} name(s) without sector metadata are exempt from the sector cap"] if unknown else []
    if high*len(names)<1:
        high=min(1.,1.25/len(names));notes.append(f"max_weight raised to {high:.3f} so {len(names)} names can sum to 100%")
    if cap<1 and float(np.minimum(cap,high*counts).sum())+high*unknown<1-1e-9:
        low_cap,high_cap=cap,1.
        for _ in range(40):
            mid=(low_cap+high_cap)/2
            low_cap,high_cap=(mid,high_cap) if float(np.minimum(mid,high*counts).sum())+high*unknown<1-1e-9 else (low_cap,mid)
        cap=min(1.,high_cap+.01);notes.append(f"max_sector_weight raised to {cap:.3f}; the requested names are concentrated in few sectors")
    return {**request,"max_weight":high,"max_sector_weight":cap},notes


def minimum_variance(cov):
    seed=np.full(len(cov),1/len(cov));array=cov.to_numpy()
    fit=minimize(lambda w: float(w@array@w),seed,jac=lambda w: 2*array@w,method="SLSQP",bounds=[(0,1)]*len(cov),
                 constraints=[{"type":"eq","fun":lambda w: float(w.sum()-1),"jac":lambda w: np.ones(len(w))}],options={"ftol":1e-12,"maxiter":500})
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
    variant=request.get("optimization_variant","min_variance")
    hrp,order,tree=hrp_weights(cov,request.get("clustering_linkage","ward"))
    inverse=pd.Series(1/np.diag(cov),index=cov.index)/np.sum(1/np.diag(cov))
    if variant=="standard_hrp":
        weights=optimize(cov,hrp.to_numpy(),request,sectors)
    elif variant=="nco":
        weights=optimize(cov,nco_weights(returns.dropna()).to_numpy(),request,sectors)
    elif variant=="min_variance":
        weights=optimize(cov,hrp.to_numpy(),request,sectors,lambda w: float(w@cov.to_numpy()@w),lambda w: 2*cov.to_numpy()@w)
    elif variant=="inverse_variance":
        weights=optimize(cov,inverse.to_numpy(),request,sectors)
    elif variant=="equal_weight":
        weights=optimize(cov,np.full(len(cov),1/len(cov)),request,sectors)
    else:
        raise ValueError("Supported variants: min_variance, standard_hrp, nco, inverse_variance, equal_weight")
    return weights,cov,order,tree


def control_weights(cov,variant,linkage):
    """Unconstrained long-only references shown beside the chosen allocation."""
    if variant=="standard_hrp":
        return hrp_weights(cov,linkage)[0]
    if variant=="inverse_variance":
        return pd.Series(1/np.diag(cov),index=cov.index)/np.sum(1/np.diag(cov))
    if variant=="equal_weight":
        return pd.Series(1/len(cov),index=cov.index)
    return minimum_variance(cov)


def drift(weights,returns):
    """Buy-and-hold weights after the given log returns."""
    held=weights.copy()
    for _,row in returns.iterrows():
        held=held*np.exp(row.fillna(0.))
        held=held/held.sum()
    return held


def rebalance_gain(current,target,cov,ann,aversion,cost_bps,period=21):
    """Quadratic-utility gain from moving to target (return per period) against the proportional cost of the trade."""
    sigma=cov.to_numpy()*ann
    c,t=current.to_numpy(),target.to_numpy()
    gain=.5*aversion*(c@sigma@c-t@sigma@t)*period/ann
    turnover=float(np.abs(t-c).sum())
    return float(gain),turnover,float(cost_bps/1e4*turnover)


def strategy_summary(rows,ann,turnovers):
    net=pd.Series([r["net_return"] for r in rows]);gross=pd.Series([r["gross_return"] for r in rows])
    return {"annual_return":float(net.mean()*ann),"annual_volatility":float(net.std()*np.sqrt(ann)),"sharpe":sharpe(net.to_numpy(),ann),
            "max_drawdown":max_drawdown(np.array([r["equity"] for r in rows])),"final_equity":float(rows[-1]["equity"]),
            "average_turnover":float(np.mean(turnovers)) if len(turnovers) else None,"cost_drag_annual":float((gross-net).mean()*ann)}


def block_bootstrap(frame,rng,block=10):
    n=len(frame);starts=rng.integers(0,n-block+1,size=int(np.ceil(n/block)))
    index=np.concatenate([np.arange(s,s+block) for s in starts])[:n]
    return frame.iloc[index].reset_index(drop=True)


def alpha_views(artifact_id,cov,ann):
    """Grinold views from stored Alpha scores: annual return = IC x annual volatility x standardised score, IC from the held-out rows."""
    stored=get_artifact(str(artifact_id))
    if not stored or stored.get("kind")!="alpha_predictions":
        raise ValueError("alpha_artifact_id is unknown or expired; rerun Alpha and pass the new id")
    held=pd.DataFrame(stored["heldout"])
    ics=[fast_spearman_ic(g["score"].to_numpy(float),g["forward_return"].to_numpy(float)) for _,g in held.groupby("date") if len(g)>=6]
    ics=[v for v in ics if np.isfinite(v)]
    ic=float(np.mean(ics)) if ics else float("nan")
    scores=pd.Series({t:v["score"] for t,v in stored["predictions"].items()}).reindex(cov.index).dropna()
    info={"artifact_id":artifact_id,"held_out_ic":ic,"names_with_scores":int(len(scores)),"alpha_as_of":stored.get("as_of"),"alpha_horizon":stored.get("horizon")}
    if len(scores)<4 or not np.isfinite(ic) or ic<=0:
        return {},{**info,"used":False,"reason":"held-out IC is not positive or fewer than four scored names"}
    z=(scores-scores.mean())/scores.std(ddof=1)
    vol=np.sqrt(np.diag(cov)*ann);vol=pd.Series(vol,index=cov.index).reindex(scores.index)
    views=(min(ic,.25)*vol*z)
    return {t:float(v) for t,v in views.items()},{**info,"used":True,"ic_used":min(ic,.25)}


def parse_holdings(request,close):
    """Current weights from {ticker: weight} or {ticker: shares}; returns (weights, portfolio value, shares or None)."""
    holdings=request.get("holdings")
    if not isinstance(holdings,dict) or not holdings:
        return None,None,None
    values=pd.Series({normalize_symbol(k):float(v) for k,v in holdings.items()})
    if not np.isfinite(values).all() or (values<0).any() or values.sum()<=0:
        raise ValueError("holdings must be finite, nonnegative and not all zero")
    if str(request.get("holdings_unit","weights"))=="shares":
        missing=[t for t in values.index if t not in close or not np.isfinite(close[t])]
        if missing:
            raise ValueError("No latest price for holdings: "+", ".join(missing))
        dollars=values*close.reindex(values.index)
        return dollars/dollars.sum(),float(dollars.sum()),values
    return values/values.sum(),float(request.get("portfolio_value") or 100000.),None


def run_hrp_optimizer(payload=None):
    request=dict(payload or {})
    holdings=request.get("holdings")
    if holdings and not (request.get("symbols") or request.get("tickers")):
        request["symbols"]=[normalize_symbol(k) for k in holdings]
    ctx=load_context(request);request=ctx.payload
    if ctx.returns.shape[1]>200:
        raise ValueError("Allocation supports up to 200 explicitly requested assets")
    request,bound_notes=relax_infeasible_bounds(request,list(ctx.returns.columns),ctx.sectors)
    variant=request.get("optimization_variant","min_variance");linkage=request.get("clustering_linkage","ward")
    cost_bps=float(request.get("cost_bps",5));ann=ctx.annualization
    weights,cov,order,tree=allocation(ctx.returns,request,ctx.sectors)
    reference=np.full(len(weights),1/len(weights))
    tau=float(request.get("black_litterman_tau",.05))
    aversion=float(request.get("risk_aversion",2.5))
    if not 0<tau<=1 or aversion<=0:
        raise ValueError("BL tau must be (0,1] and risk_aversion must be positive")
    sigma=cov.to_numpy();prior=aversion*sigma@reference
    views=dict(request.get("views") or {})
    if not isinstance(views,dict) or set(views)-set(weights.index):
        raise ValueError("BL views must map requested assets to annual expected returns")
    alpha_info=None
    if request.get("alpha_artifact_id"):
        generated,alpha_info=alpha_views(request["alpha_artifact_id"],cov,ann)
        views={**generated,**views}
    posterior=prior.copy()
    if views:
        selected=[list(weights.index).index(name) for name in views]
        P=np.eye(len(weights))[selected]
        Q=np.array([float(views[name])/ann for name in views])
        if not np.isfinite(Q).all(): raise ValueError("BL views must be finite")
        omega=np.diag(np.diag(P@(tau*sigma)@P.T))
        posterior=prior+tau*sigma@P.T@np.linalg.solve(P@(tau*sigma)@P.T+omega,Q-P@prior)
    bl=optimize(cov,weights.to_numpy(),request,ctx.sectors,
                lambda w: float(.5*aversion*w@sigma@w-posterior@w),lambda w: aversion*sigma@w-posterior)
    window=int(request.get("allocation_window",252))
    controls=[v for v in ("min_variance","standard_hrp","inverse_variance","equal_weight") if v!=variant]
    targets={variant:{},"turnover_aware":{},**{c:{} for c in controls}};audit,log=[],[]
    held=None;last_executed=None
    for i in range(window,len(ctx.returns),21):
        history=ctx.returns.iloc[i-window:i]
        chosen,hist_cov,_,_=allocation(history,request,ctx.sectors)
        date=ctx.returns.index[i]
        targets[variant][date]=chosen.to_dict()
        for name in controls:
            targets[name][date]=control_weights(hist_cov,name,linkage).to_dict()
        if held is None:
            trade,gain,cost,turnover=True,None,None,float(chosen.abs().sum())
        else:
            held=drift(held,ctx.returns.iloc[last_executed:i])
            gain,turnover,cost=rebalance_gain(held,chosen,hist_cov,ann,float(request.get("risk_aversion",2.5)),cost_bps)
            trade=gain>cost
        if trade:
            targets["turnover_aware"][date]=chosen.to_dict();held=chosen.copy();last_executed=i
        log.append({"date":str(date.date()),"traded":bool(trade),"expected_gain":gain,"trade_cost":cost,"turnover":turnover})
        audit.append({"formation_date":str(date.date()),"training_end":str(history.index[-1].date()),"assets":len(chosen)})
    if not audit:
        raise ValueError("Insufficient dates for historical allocation window")
    rows,summaries,curve={},[],[]
    kinds={variant:"chosen","turnover_aware":"chosen with no-trade rule"}
    for name,target in targets.items():
        rows[name]=execute_portfolio(ctx.returns,target,cost_bps)
        turnovers=[r["turnover"] for r in rows[name] if r["turnover"]>0][1:]
        summaries.append({"strategy":name,"kind":kinds.get(name,"control"),**strategy_summary(rows[name],ann,turnovers),"rebalances_executed":len(target)})
        curve.extend({"strategy":name,"date":r["date"],"equity":r["equity"],"net_return":r["net_return"]} for r in rows[name])
    backtest=rows[variant]
    # Bootstrap weight stability: block-resample the last window and re-solve the chosen allocation.
    draws=int(request.get("bootstrap_samples",40));stability=[]
    if draws:
        rng=np.random.default_rng(7);sample=ctx.returns.iloc[-window:];samples=[]
        for _ in range(draws):
            try:
                samples.append(allocation(block_bootstrap(sample,rng),request,ctx.sectors)[0].reindex(weights.index))
            except ValueError:
                continue
        if samples:
            table=pd.DataFrame(samples)
            stability=[{"asset":name,"weight":float(weights[name]),"p05":float(table[name].quantile(.05)),"p95":float(table[name].quantile(.95)),
                        "std":float(table[name].std()),"selected_share":float((table[name]>.01).mean()),"draws":len(table)} for name in weights.index]
    contributions=weights*(cov@weights)/float(weights@cov@weights)
    weight_rows=[{"asset":name,"weight":float(weights[name]),"sector":ctx.sectors.get(name,"Unknown")} for name in weights.index]
    bl_rows=[{"asset":name,"reference_prior_return":float(prior[i]*ann),"posterior_return":float(posterior[i]*ann),
              "posterior_weight":float(bl[name])} for i,name in enumerate(weights.index)]
    tree_rows=[{"left":int(a),"right":int(b),"distance":float(c),"count":int(d)} for a,b,c,d in tree]
    current,value,shares=parse_holdings(request,ctx.closes.iloc[-1])
    trades,trade_summary,holding_risk=[],[],[]
    if current is not None:
        current=current.reindex(weights.index).fillna(0.)
        gain,turnover,cost=rebalance_gain(current,weights,cov,ann,aversion,cost_bps)
        price=ctx.closes.iloc[-1].reindex(weights.index)
        for name in weights.index:
            delta=float(weights[name]-current[name])
            trades.append({"asset":name,"current_weight":float(current[name]),"target_weight":float(weights[name]),"trade_weight":delta,
                           "side":"buy" if delta>1e-6 else "sell" if delta<-1e-6 else "hold","trade_value":delta*value,
                           "shares":float(delta*value/price[name]) if price[name]>0 else None,"cost":abs(delta)*value*cost_bps/1e4})
        vol_now,vol_new=float(np.sqrt(current@cov@current*ann)),float(np.sqrt(weights@cov@weights*ann))
        trade_summary=[{"portfolio_value":value,"turnover":turnover,"total_cost":turnover*value*cost_bps/1e4,"cost_bps":cost_bps,
            "volatility_before":vol_now,"volatility_after":vol_new,"volatility_change":vol_new-vol_now,"expected_gain_per_month":gain,
            "expected_cost":cost,"trade_recommended":bool(gain>cost)}]
        now_risk=current*(cov@current)/max(float(current@cov@current),1e-18)
        holding_risk=[{"asset":n,"current_weight":float(current[n]),"current_risk_contribution":float(now_risk[n]),
                       "target_weight":float(weights[n]),"target_risk_contribution":float(contributions[n])} for n in weights.index if current[n]>0 or weights[n]>1e-6]
    artifact_id=put_artifact("allocation_returns",{"variant":variant,"cost_bps":cost_bps,"universe":list(weights.index),
        "dates":[r["date"] for r in backtest],"net_returns":{n:[r["net_return"] for r in r_] for n,r_ in rows.items()}})
    provenance=build_provenance(ctx.closes,calendar=ctx.calendar,train_window=(ctx.returns.index[0],ctx.returns.index[window-1]),
        test_window=(ctx.returns.index[window],ctx.returns.index[-1]),purge=0,embargo=0,universe=universe_label(ctx.payload,ctx.symbols),
        extra={"allocation_window":window,"refits":len(audit)})
    best=max(summaries,key=lambda r:-np.inf if r["sharpe"] is None or not np.isfinite(r["sharpe"]) else r["sharpe"])
    alerts=[{"level":"info","message":f"{best['strategy']} has the highest walk-forward Sharpe; compare it with the controls before relying on {variant}."}] if best["strategy"]!=variant else []
    alerts.extend({"level":"warning","message":note} for note in bound_notes)
    if alpha_info and not alpha_info["used"]:
        alerts.append({"level":"warning","message":"Alpha views ignored: "+alpha_info["reason"]})
    return response("05",[summary("Assets",len(weights)),summary("Refits",len(audit)),summary("Allocation",variant)],
        charts={"hrp_weight_vector":weight_rows,"cluster_dendrograms":tree_rows,
                "quasi_diagonalized_covariance_heatmap":matrix_records(cov.loc[order,order],limit=200),
                "risk_contribution_decomposition":[{"asset":name,"risk_contribution":float(value_)} for name,value_ in contributions.items()],
                "walk_forward_allocation":backtest,"controls_equity":curve,"weight_stability":stability,
                "black_litterman_posterior_return_vector":bl_rows,
                "bl_vs_pure_hrp_weight_comparison":[{"asset":name,"allocation_weight":float(weights[name]),"black_litterman":float(bl[name])} for name in weights.index]},
        tables={"hrp_weights":weight_rows,"controls_summary":summaries,"weight_stability":stability,"rebalance_log":log,"trade_list":trades,
                "rebalance_summary":trade_summary,"holding_risk":holding_risk,"alpha_views":[{**alpha_info,"asset":a,"view_annual_return":v} for a,v in (views.items() if alpha_info and alpha_info["used"] else [])],
                "allocation_training_audit":audit,"black_litterman":bl_rows},
        alerts=alerts,provenance=provenance,
        meta={"artifact_id":artifact_id,"estimator":request.get("covariance_estimator","ledoit_wolf"),"variant":variant,
              "controls":"min-variance (Ledoit-Wolf), HRP, inverse-variance and 1/N shown beside the chosen allocation, walk-forward, net of costs; the chosen allocation uses the weight and sector bounds, controls do not",
              "no_trade_rule":"rebalance only when the quadratic-utility gain (risk aversion x variance reduction x 21/252) exceeds the proportional cost of the trade",
              "bootstrap":f"{draws} block-bootstrap resamples (block 10) of the last {window} sessions; bands are the 5th and 95th percentile weights",
              "alpha_views":alpha_info,"sector_basis":"time_invariant_current_snapshot","bl_prior":"equal_weight_reference_not_market_cap_equilibrium",
              "views_units":"annual_return","as_of_date":str(ctx.returns.index.max().date()),
              "execution":"next_close","costs":"actual_drifted_turnover","return_currency":"native; FX and borrow costs excluded"})
