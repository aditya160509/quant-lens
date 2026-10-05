"""Training-selected pairs with causal hedge ratios and observed portfolio returns."""
from __future__ import annotations
from itertools import combinations
from typing import Any
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
from .common import compact_records, date_str, response, summary
from .panel import load_context
from .portfolio import execute_portfolio


def hedge_path(y, x, cut, method):
    """Initial hedge fit on formation history; subsequent updates use past observations."""
    initial = np.column_stack([np.ones(cut),x[:cut]])
    beta = np.linalg.lstsq(initial,y[:cut],rcond=None)[0]
    variance = max(float(np.var(y[:cut]-initial@beta)),1e-10)
    covariance = np.eye(2)*variance
    history = list(y[:cut]-initial@beta)
    rows = []
    for position in range(cut,len(y)):
        if method == "rolling_ols":
            start = max(0,position-126)
            beta = np.linalg.lstsq(np.column_stack([np.ones(position-start),x[start:position]]),y[start:position],rcond=None)[0]
            reference = y[start:position] - beta[0] - beta[1]*x[start:position]
        else:
            reference = np.asarray(history[-63:])
        design = np.array([1.,x[position]])
        residual = float(y[position]-design@beta)
        deviation = float(reference.std(ddof=1))
        zscore = (residual-float(reference.mean()))/deviation if deviation>1e-10 else None
        rows.append({"position":position,"hedge_ratio":float(beta[1]),"intercept":float(beta[0]),"spread":residual,"zscore":zscore})
        history.append(residual)
        if method == "kalman":
            # Fixed Q/R from the training residual scale, never fitted on the test path.
            predicted_cov = covariance+np.eye(2)*variance*1e-4
            gain = predicted_cov@design/(design@predicted_cov@design+variance)
            beta = beta+gain*residual
            covariance = (np.eye(2)-np.outer(gain,design))@predicted_cov
    return rows


def run_pairs_engine(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload,min_symbols=10)
    closes = ctx.closes.where(ctx.closes>0)
    if len(closes)<160:
        raise ValueError("Pairs require at least 160 observed formation and evaluation sessions")
    if len(ctx.symbols)>120:
        raise ValueError("Pairwise research is limited to 120 explicitly selected assets")
    cut = int(len(closes)*.6)
    selection = str(ctx.payload.get("pair_selection","engle_granger"))
    if selection not in {"engle_granger","sector_neutral"}:
        raise ValueError("Unsupported pair_selection")
    method = str(ctx.payload.get("hedge_ratio_method","kalman"))
    if method not in {"static","rolling_ols","kalman"}:
        raise ValueError("Unsupported hedge_ratio_method")
    minimum = float(ctx.payload.get("min_correlation",.45))
    entry = float(ctx.payload.get("entry_z",2)); exit = float(ctx.payload.get("exit_z",.5))
    if not 0<=minimum<=1 or not 0<=exit<entry:
        raise ValueError("Require 0 <= min_correlation <= 1 and 0 <= exit_z < entry_z")
    formation_returns = ctx.returns.iloc[:cut]
    candidates = []
    for a,b in combinations(closes.columns,2):
        if selection == "sector_neutral":
            if ctx.sectors.get(a,"Unknown") == "Unknown" or ctx.sectors.get(a) != ctx.sectors.get(b):
                continue
        history = np.log(closes.iloc[:cut][[a,b]]).dropna()
        correlation = formation_returns[a].corr(formation_returns[b])
        if len(history)<80 or pd.isna(correlation) or abs(correlation)<minimum:
            continue
        statistic,pvalue,_ = coint(history[a],history[b],trend="c",autolag="aic")
        candidates.append({"asset_a":a,"asset_b":b,"formation_correlation":float(correlation),
            "engle_granger_statistic":float(statistic),"engle_granger_pvalue":float(pvalue),"cointegrated":bool(pvalue<.05),
            "formation_observations":len(history)})
    candidates.sort(key=lambda row:row["engle_granger_pvalue"])
    accepted = [row for row in candidates if row["cointegrated"]]
    rows, signals, targets = [], [], {}
    if accepted:
        pair = accepted[0]
        prices = np.log(closes[[pair["asset_a"],pair["asset_b"]]])
        # Trading history must be complete: do not compress missing sessions into contiguous returns.
        if prices.isna().any().any():
            raise ValueError("Selected pair has missing prices; cannot run a continuous observed backtest")
        rows = hedge_path(prices.iloc[:,0].to_numpy(),prices.iloc[:,1].to_numpy(),cut,method)
        direction = 0
        for row in rows:
            date = closes.index[row.pop("position")]
            row["date"] = date_str(date)
            zscore = row["zscore"]
            if zscore is not None:
                if direction and abs(zscore)<=exit:
                    direction = 0
                elif not direction and abs(zscore)>=entry:
                    direction = -1 if zscore>0 else 1
            hedge = row["hedge_ratio"]
            norm = 1+abs(hedge)
            targets[date] = {pair["asset_a"]:direction/norm,pair["asset_b"]:-direction*hedge/norm}
            signals.append({"date":date_str(date),"direction":direction,"zscore":zscore})
    equity = execute_portfolio(ctx.returns,targets,float(ctx.payload.get("cost_bps",10)))
    return response("09",[summary("Formation candidates",len(candidates),"pairs"),summary("Cointegrated",len(accepted),"p<0.05")],
        charts={"pair_candidate_leaderboard":candidates,"spread_zscore_timeseries":rows,
            "cointegration_network":[{"source":row["asset_a"],"target":row["asset_b"],"pvalue":row["engle_granger_pvalue"]} for row in accepted],
            "hedge_ratio_path":rows,"entry_exit_signal_timeline":signals,"pair_backtest_equity":equity},
        tables={"pair_candidates":candidates,"spread_timeseries":rows,"hedge_ratio":rows,
            "training_audit":[{"formation_end":date_str(closes.index[cut-1]),"formation_sessions":cut,"selected_pair":accepted[0] if accepted else None}]},
        meta={"selection":"initial_60_percent_formation_only; fixed_pair_OOS","cointegration":"statsmodels_Engle_Granger_with_intercept",
            "hedge_ratio_method":method,"execution":"next_close_with_actual_turnover_costs","kalman":"training_scale_fixed_Q_R",
            "empty_selection":"cash; no pair met the formation test","return_currency":"native currencies; FX and borrow costs excluded",
            "sector_metadata":"current snapshot; sector_neutral is not historical membership"})
