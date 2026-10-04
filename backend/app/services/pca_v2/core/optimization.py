"""Constrained portfolio solvers with explicit failures and common constraints."""
from __future__ import annotations
import math
import numpy as np
from scipy.optimize import minimize
import cvxpy as cp


def expected_returns(model, payload):
    from .analytics import black_litterman_posterior, model_annualization
    annualization = model_annualization(model, payload)
    views = payload.get("bl_views") or []
    if views:
        translated = []
        for view in views:
            if view.get("pcs"):
                assets = np.zeros(len(model["symbols"]))
                for pc, coefficient in view["pcs"].items():
                    index = int(str(pc).replace("PC", "")) - 1
                    if not 0 <= index < model["k"]:
                        raise ValueError("Unknown Black-Litterman PC")
                    assets += float(coefficient) * model.get("orthonormal_eigenvectors",model["eigenvectors"])[:, index] / np.asarray(model.get("return_scales",np.ones(len(model["symbols"]))))
                view = {**view, "assets": dict(zip(model["symbols"], assets))}
            translated.append(view)
        weights = np.ones(len(model["symbols"])) / len(model["symbols"])
        return black_litterman_posterior(model["cleaned_cov"] * annualization, weights, translated, model["symbols"])
    return model["returns"].mean().to_numpy() * annualization


def constraints(model, payload, variable):
    from .analytics import model_annualization
    symbols = model["symbols"]
    n = len(symbols)
    maximum = float(payload.get("max_weight", .12))
    short = bool(payload.get("long_short", False))
    named = [("sum_to_one", cp.sum(variable) == 1)]
    if short:
        named += [("gross_limit", cp.norm1(variable) <= float(payload.get("gross_limit", 2)))]
    else:
        if maximum*n < 1 - 1e-10:
            raise ValueError("Infeasible max_weight: asset count times max_weight must be at least one")
        named += [("long_only", variable >= 0), ("max_weight", variable <= maximum)]
    previous = payload.get("previous_weights")
    if previous:
        old = np.array([float(previous.get(s, 0)) for s in symbols])
        named += [("turnover", cp.norm1(variable-old) <= 2*float(payload.get("turnover_max",1)))]
    for sector, bounds in (payload.get("sector_bounds") or {}).items():
        mask = np.array([model["sectors"].get(s)==sector for s in symbols],dtype=float)
        low,high = bounds
        named += [(f"sector_{sector}_min",mask@variable >= float(low)),(f"sector_{sector}_max",mask@variable <= float(high))]
    for component,bounds in (payload.get("factor_bounds") or {}).items():
        index=int(str(component).replace("PC", ""))-1
        if not 0 <= index < model["k"]:
            raise ValueError("Unknown factor exposure constraint")
        loading=model["eigenvectors"][:,index]
        low,high=bounds
        named += [(f"factor_{component}_min",loading@variable >= float(low)),(f"factor_{component}_max",loading@variable <= float(high))]
    if payload.get("tracking_error_max") is not None:
        benchmark=payload.get("benchmark_weights") or dict(zip(symbols,np.ones(n)/n))
        bw=np.array([float(benchmark.get(s,0)) for s in symbols])
        cov=model["cleaned_cov"]*model_annualization(model,payload)
        vals,vecs=np.linalg.eigh(cov)
        root=np.diag(np.sqrt(np.maximum(vals,0)))@vecs.T
        named += [("tracking_error",cp.norm(root@(variable-bw),2)<=float(payload["tracking_error_max"]))]
    if payload.get("cardinality_max") is not None:
        raise ValueError("Cardinality requires a mixed-integer quadratic solver; unavailable in the supported solver stack")
    return named


def optimize(model,payload,frontier=True,duals=False):
    from .analytics import model_annualization
    payload=payload or {}
    n=len(model["symbols"])
    cov=model["cleaned_cov"]*model_annualization(model,payload)
    mu=expected_returns(model,payload)
    objective=payload.get("objective","mean_variance")
    w=cp.Variable(n)
    named=constraints(model,payload,w)
    if objective=="mean_variance":
        problem=cp.Problem(cp.Minimize(float(payload.get("risk_aversion",5))*cp.quad_form(w,cp.psd_wrap(cov))-mu@w),[c for _,c in named])
        problem.solve(solver=cp.CLARABEL)
        if w.value is None or problem.status not in {"optimal","optimal_inaccurate"}:
            raise ValueError(f"Optimization failed: {problem.status}")
        weights=np.asarray(w.value).reshape(-1)
        shadows=[{"constraint":name,"dual_value": np.asarray(c.dual_value).tolist()} for name,c in named]
        status=problem.status
    else:
        # Feasible start and exact constraint verification for nonlinear objectives.
        feasible=cp.Problem(cp.Minimize(cp.sum_squares(w)),[c for _,c in named]);feasible.solve(solver=cp.CLARABEL)
        if w.value is None:
            raise ValueError("Infeasible portfolio constraints")
        start=np.asarray(w.value).reshape(-1)
        if objective in {"erc","risk_parity","equal_risk_contribution"}:
            budgets=payload.get("risk_budgets") or {}
            targets=np.array([float(budgets.get(s,1/n)) for s in model["symbols"]]);targets/=targets.sum()
            def loss(x):
                total=max(x@cov@x,1e-15)
                return np.sum((x*(cov@x)/total-targets)**2)
        elif objective in {"max_sharpe","msp","maximum_sharpe"}:
            def loss(x):
                return -(x@mu-float(payload.get("risk_free_rate",0)))/np.sqrt(max(x@cov@x,1e-15))
        elif objective in {"pc_factor_risk_parity","pc_risk_parity"}:
            def loss(x):
                components=model["eigenvalues"][:model["k"]]*(model["eigenvectors"][:,:model["k"]].T@x)**2
                return np.sum((components/max(components.sum(),1e-15)-1/model["k"])**2)
        else:
            raise ValueError(f"Unknown portfolio objective: {objective}")
        def residual(x, constraint):
            w.value=x
            return np.asarray(-constraint.expr.value).reshape(-1)
        scipy_constraints=[{"type":"eq" if isinstance(c,cp.constraints.zero.Equality) else "ineq","fun":lambda x,c=c:residual(x,c)} for _,c in named]
        result=minimize(loss,start,method="SLSQP",constraints=scipy_constraints,options={"maxiter":1000,"ftol":1e-10})
        if not result.success:
            raise ValueError(f"Nonlinear optimizer failed: {result.message}")
        weights=result.x;w.value=weights
        if any(np.max(c.violation())>1e-5 for _,c in named):
            raise ValueError("Solver returned a portfolio violating constraints")
        shadows=[];status="slsqp"
    frontier_rows=[]
    if frontier:
        aversion=cp.Parameter(nonneg=True)
        efficient=cp.Problem(cp.Maximize(mu@w-aversion*cp.quad_form(w,cp.psd_wrap(cov))),[c for _,c in named])
        for value in np.logspace(-3,4,int(payload.get("frontier_points",100))):
            aversion.value=value;efficient.solve(solver=cp.CLARABEL)
            if w.value is None:
                raise ValueError(f"Frontier failed: {efficient.status}")
            x=np.asarray(w.value).reshape(-1)
            frontier_rows.append({"risk":float(np.sqrt(max(x@cov@x,0))),"return":float(x@mu),"lambda":float(value),"status":efficient.status})
    return {"status":status,"weights":[{"ticker":s,"weight":float(weights[i]),"sector":model["sectors"].get(s,"Unknown")} for i,s in enumerate(model["symbols"])],"expected_return":float(weights@mu),"annualized_vol":float(np.sqrt(max(weights@cov@weights,0))),"objective":objective,"frontier":frontier_rows,"shadow_prices":shadows,"posterior_returns":[{"ticker":s,"expected_return":float(mu[i])} for i,s in enumerate(model["symbols"])]}


def rolling_backtest(model,payload):
    from .analytics import covariance_estimator,eig_sorted
    rets=model.get("original_returns",model["returns"])
    window=int(payload.get("rebalance_window",126));step=int(payload.get("rebalance_step",21))
    records=[];equity=1.;previous=np.zeros(rets.shape[1])
    for end in range(window,len(rets),step):
        train=rets.iloc[end-window:end]
        cov,_=covariance_estimator(train,payload.get("covariance_estimator","ledoit_wolf"))
        vals,vecs=eig_sorted(cov)
        local={**model,"returns":train,"cleaned_cov":cov,"eigenvalues":vals,"eigenvectors":vecs}
        result=optimize(local,payload,frontier=False)
        weights=np.array([r["weight"] for r in result["weights"]])
        turnover=float(np.abs(weights-previous).sum());previous=weights
        for offset,(date,row) in enumerate(rets.iloc[end:end+step].iterrows()):
            gross=float(row.to_numpy()@weights)
            cost=turnover*float(payload.get("cost_bps",2))/10000 if offset==0 else 0.
            net=gross-cost;equity*=1+net
            records.append({"date":date,"gross_return":gross,"net_return":net,"equity":equity,"turnover":turnover if offset==0 else 0})
    return records
