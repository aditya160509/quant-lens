"""Observed dollar-volume liquidity factors and regression diagnostics."""
import numpy as np
import pandas as pd


def outputs(model,payload):
    from .analytics import dollar_volume_matrix,pastor_stambaugh_gamma,eig_sorted,fit_mp_sigma2,mp_threshold,factor_returns,newey_west_se,portfolio_weights,risk_decomposition
    symbols=model["symbols"];rets=model["returns"]
    dv=dollar_volume_matrix(symbols,model["lookback_days"]).reindex(index=rets.index,columns=symbols)
    if dv.empty or dv.isna().all().any() or (dv<=0).all().any():
        raise ValueError("Liquidity requires observed positive dollar volume for every requested asset")
    measure=payload.get("illiquidity_measure","amihud");window=int(payload.get("illiquidity_window",21))
    if measure=="amihud":
        panel=(rets.abs()/dv.where(dv>0)).rolling(window,min_periods=window).mean()
    elif measure=="pastor_stambaugh":
        panel=pastor_stambaugh_gamma(rets,dv,rets.mean(axis=1),window=window)
    else:
        raise ValueError("True Kyle lambda needs signed intraday order flow; turnover needs historical shares. Supported measures: amihud, pastor_stambaugh")
    normalization=payload.get("illiquidity_normalization","standardize")
    if normalization=="rank":
        z=panel.rank(axis=1,pct=True)-.5
    elif normalization=="log":
        z=np.sign(panel)*np.log1p(panel.abs())
    elif normalization=="standardize":
        z=panel.sub(panel.mean(axis=1),axis=0).div(panel.std(axis=1).replace(0,np.nan),axis=0)
    else:
        raise ValueError("Unknown illiquidity normalization")
    z=z.replace([np.inf,-np.inf],np.nan).dropna(how="any")
    if len(z)<30:
        raise ValueError("Liquidity requires 30 complete normalized observations")
    vals,vecs=eig_sorted(z.cov().to_numpy())
    threshold=mp_threshold(vals,len(symbols),len(z),fit_mp_sigma2(vals,len(symbols),len(z)))
    k=max(1,int((vals>threshold["lambda_max"]).sum()))
    liquidity_factors = pd.DataFrame(z.to_numpy()@vecs[:,:k], index=z.index, columns=[f"Liquidity_PC{i+1}" for i in range(k)])
    if payload.get("liquidity_factor_method","pca")=="iml":
        ranks=panel.loc[z.index].rank(axis=1,pct=True)
        high=ranks.ge(.7);low=ranks.le(.3)
        factor=(rets.loc[z.index].where(high).mean(axis=1)-rets.loc[z.index].where(low).mean(axis=1)).rename("latent_liquidity")
    else:
        factor=pd.Series(z.to_numpy()@vecs[:,0],index=z.index,name="latent_liquidity")
    delta=factor.diff().dropna()
    factors=factor_returns(model).loc[delta.index]
    design=np.column_stack([np.ones(len(delta)),factors.to_numpy(),delta.to_numpy()])
    y=rets.loc[delta.index].to_numpy();coef=np.linalg.lstsq(design,y,rcond=None)[0];residual=y-design@coef
    rows=[]
    for i,ticker in enumerate(symbols):
        se=newey_west_se(design,residual[:,i],design.shape[1]-1,3)
        current=float(panel[ticker].dropna().iloc[-1]);history=panel[ticker].dropna()
        rows.append({"ticker":ticker,"sector":model["sectors"].get(ticker,"Unknown"),"current_amihud":current,"amihud_percentile":float((history<=current).mean()*100),"liquidity_beta":float(coef[-1,i]),"beta_se":se,"t_stat":float(coef[-1,i]/se) if se>0 else None,"illiquidity_measure":measure})
    weights=portfolio_weights(symbols,payload).to_numpy();beta=coef[-1];port_beta=float(weights@beta)
    factor_design=np.column_stack([np.ones(len(delta)),factors.to_numpy()]);orthogonal_delta=delta.to_numpy()-factor_design@np.linalg.lstsq(factor_design,delta.to_numpy(),rcond=None)[0]
    liqvar=float(np.var(orthogonal_delta,ddof=1));contribution=port_beta**2*liqvar
    stdrisk=risk_decomposition(model,payload)
    assetvar=rets.loc[delta.index].var().to_numpy();corr=np.outer(beta,beta)*liqvar/np.sqrt(np.outer(assetvar,assetvar))
    corr=pd.DataFrame(corr,index=symbols,columns=symbols)
    # Orthogonal regression separates liquidity from existing PCs without counting it twice.
    fitted_pc=design@coef-np.outer(orthogonal_delta,beta);pcport=fitted_pc@weights
    idioport=residual@weights
    augmented=[{"component":"PC regression","variance_contribution":float(np.var(pcport,ddof=1))},{"component":"Orthogonal liquidity","variance_contribution":contribution},{"component":"Idiosyncratic","variance_contribution":float(np.var(idioport,ddof=1))}]
    value=float(payload.get("portfolio_value",1e6));participation=float(payload.get("adv_participation_rate",.15))
    if not 0<participation<=1:
        raise ValueError("adv_participation_rate must be in (0,1]")
    liquidation=[]
    for i,ticker in enumerate(symbols):
        adv=float(dv[ticker].tail(21).dropna().median());vol=float(rets[ticker].tail(63).std())
        if not np.isfinite(adv) or adv<=0:
            raise ValueError("Insufficient observed ADV for "+ticker)
        position=abs(weights[i])*value;days=max(1.,position/(participation*adv));cost=vol*np.sqrt(position/(days*adv))*10000
        liquidation.append({"ticker":ticker,"position_value":position,"adv":adv,"position_pct_adv":position/adv,"adv_participation_rate":participation,"days_to_liquidate":days,"estimated_cost_bps":float(cost),"rating":"Red" if days>5 or cost>20 else "Amber" if days>1 or cost>5 else "Green"})
    percentile=float((factor<=factor.iloc[-1]).mean()*100);top=np.argsort(np.abs(weights))[-min(20,len(symbols)):];topcorr=corr.to_numpy()[np.ix_(top,top)];average=float(topcorr[np.triu_indices_from(topcorr,1)].mean())
    signals={"liquidity_factor_above_p90":percentile>=90,"top20_liquidity_corr_above_030":average>=.30,"portfolio_beta_above_threshold":abs(port_beta)>=float(payload.get("liquidity_beta_threshold",.5))}
    score=contribution/max(stdrisk["portfolio_vol_daily"]**2,1e-15)
    return {"liquidity_factors":liquidity_factors,"amihud_panel":z,"latent_liquidity":factor,"liquidity_betas":rows,"portfolio_liquidity_beta":port_beta,"liquidity_variance_contribution":contribution,"augmented_risk_decomposition":augmented,"liquidity_driven_corr":corr,"unwind_signals":signals,"unwind_signal_count":sum(signals.values()),"liquidity_factor_percentile":percentile,"top20_liquidity_corr":average,"liquidation":liquidation,"lavar":stdrisk["var"]["gaussian_var"]+sum(abs(weights[i])*row["estimated_cost_bps"]/10000 for i,row in enumerate(liquidation)),"quant_unwind_score":score,"quant_unwind_threshold":float(payload.get("quant_unwind_threshold",.15)),"illiquidity_measure":measure,"illiquidity_normalization":normalization,"liquidity_mp":threshold,"liquidity_k":k,"liquidity_factor_method":payload.get("liquidity_factor_method","pca")}
