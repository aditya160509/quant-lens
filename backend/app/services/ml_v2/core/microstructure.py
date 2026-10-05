"""Historical daily OHLCV estimators and causal cross-sectional portfolios."""
from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from .common import compact_records, matrix_records, response, summary
from .estimators import corwin_schultz_spread, high_low_amihud
from .panel import load_context
from .portfolio import execute_portfolio
from .performance import fast_spearman_ic


def market_residual_ivol(returns, annualization, window=21):
    """Rolling OLS with intercept and equal-weight market, residual df = n-2."""
    market = returns.mean(axis=1,skipna=False)
    market_var = market.rolling(window).var(ddof=1)
    covariance = returns.rolling(window).cov(market)
    residual_variance = returns.rolling(window).var(ddof=1) - covariance.pow(2).div(market_var,axis=0)
    return np.sqrt(residual_variance.clip(lower=0)*(window-1)/(window-2)*annualization)


def run_microstructure(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = load_context(payload,min_symbols=12)
    logs = ctx.returns
    returns = np.expm1(logs)
    close = ctx.closes.reindex(logs.index); volume = ctx.volumes.reindex(logs.index)
    window = int(ctx.payload.get("amihud_window",21))
    if str(ctx.payload.get("ic_protocol","daily_forward_ic")) != "daily_forward_ic":
        raise ValueError("Only historical daily_forward_ic is supported")
    if str(ctx.payload.get("ivol_model","market_residual")) != "market_residual":
        raise ValueError("Only rolling market OLS residual IVOL is supported")
    notional = (close*volume).where((close>0)&(volume>0))
    logvolume = np.log(volume.where(volume>0))
    price_changes = close.diff()
    roll_covariance = price_changes.rolling(21).cov(price_changes.shift(1))
    panels = {"amihud":(returns.abs()/notional).rolling(window).mean()*1e8,
        "roll_spread":2*np.sqrt((-roll_covariance).clip(lower=0)),
        "max_factor":returns.rolling(21).max(),"high_52w_proximity":close/close.rolling(252).max(),
        "ivol":market_residual_ivol(returns,ctx.annualization),
        "volume_surprise":(logvolume-logvolume.rolling(21).mean())/logvolume.rolling(21).std().replace(0,np.nan),
        "dollar_vol_momentum":np.log(notional.rolling(63).mean()/notional.rolling(252).mean()),
        "turnover_rate":volume/volume.rolling(21).mean().replace(0,np.nan)}
    for key, estimator in [("hl_amihud",high_low_amihud),("corwin_schultz_spread",corwin_schultz_spread)]:
        columns = {}
        for ticker, group in ctx.ohlcv.groupby("Ticker",sort=False):
            columns[ticker] = estimator(group.set_index("Date"),window=window).reindex(logs.index)
        panels[key] = pd.DataFrame(columns,index=logs.index).reindex(columns=logs.columns)
    aliases = {"52w_high":"high_52w_proximity"}
    requested = ctx.payload.get("signal_families",list(panels))
    signals = [aliases.get(str(key),str(key)) for key in requested]
    if not signals or set(signals)-set(panels):
        raise ValueError("Select supported signal families")
    forward = np.expm1(logs.shift(-5).rolling(5).sum())
    leaderboard, backtests = [], []
    snapshots = pd.DataFrame({key:values.iloc[-1] for key,values in panels.items()})
    snapshots["ticker"] = snapshots.index
    snapshots["sector"] = snapshots.ticker.map(ctx.sectors).fillna("Unknown")
    for key in signals:
        values = panels[key].replace([np.inf,-np.inf],np.nan)
        daily = []
        targets = {}
        for date, row in values.iterrows():
            valid = pd.concat([row.rename("signal"),forward.loc[date].rename("forward")],axis=1).dropna()
            if len(valid)>=4 and valid.signal.nunique()>1 and valid.forward.nunique()>1:
                daily.append(fast_spearman_ic(valid.signal.to_numpy(),valid.forward.to_numpy()))
            observed = row.dropna().sort_values(kind="stable")
            if len(observed)>=4:
                n = max(1,len(observed)//5)
                targets[date] = {**{ticker:-.5/n for ticker in observed.index[:n]},
                                 **{ticker:.5/n for ticker in observed.index[-n:]}}
        ic = np.array(daily)
        leaderboard.append({"signal":key,"mean_daily_ic":float(ic.mean()) if len(ic) else None,
            "ic_ir":float(ic.mean()/ic.std(ddof=1)) if len(ic)>1 and ic.std(ddof=1)>0 else None,
            "observations_dates":len(ic)})
        accounting = execute_portfolio(logs,targets,float(ctx.payload.get("cost_bps",10)))
        backtests.extend({"signal":key,**row} for row in accounting)
    surface = compact_records(panels["amihud"].rename_axis("date").reset_index(),limit=1000)
    snapshot_rows = compact_records(snapshots.reset_index(drop=True),limit=1000)
    return response("10",[summary("Signals",len(signals),"count"),summary("Universe",len(snapshots),"assets")],
        charts={"microstructure_ic_leaderboard":leaderboard,"amihud_illiquidity_surface":snapshot_rows,
            "roll_spread_cross_section":compact_records(snapshots[["ticker","roll_spread"]]),
            "max_factor_distribution":compact_records(snapshots[["ticker","max_factor"]]),
            "52_week_high_proximity_heatmap":compact_records(snapshots[["ticker","high_52w_proximity"]]),
            "ivol_cross_sectional_sort":compact_records(snapshots[["ticker","ivol"]].sort_values("ivol")),
            "volume_surprise_signal":compact_records(snapshots[["ticker","volume_surprise"]]),
            "microstructure_signal_correlation_matrix":matrix_records(snapshots[signals].corr()),
            "liquidity_regime_monitor":compact_records(pd.DataFrame({"date":logs.index,"mean_amihud":panels["amihud"].mean(axis=1)})),
            "signal_backtest":backtests,"corwin_schultz_spread_cross_section":compact_records(snapshots[["ticker","corwin_schultz_spread"]]),
            "hl_amihud_vs_standard_amihud":compact_records(snapshots[["ticker","amihud","hl_amihud"]]),"amihud_time_surface":surface},
        tables={"microstructure_table":snapshot_rows,"ic_leaderboard":leaderboard,"amihud_time_surface":surface},
        meta={"ic_protocol":"same_date_signals_vs_next_5_session_returns","backtest":"daily_reselection_next_close_execution_actual_turnover",
            "ivol":"rolling_OLS_intercept_and_equal_weight_market","roll_spread_units":"native_quote_price; daily estimator, not observed quotes",
            "notional_units":"native quote currency times shares; not USD", "volume_ratio":"relative to rolling mean, not shares-outstanding turnover",
            "return_currency":"native currencies; FX and borrow costs excluded"})
