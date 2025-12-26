import pandas as pd
import numpy as np
import logging
from app import data_loader

logger = logging.getLogger(__name__)

def run_backtest(strategy: str, tickers: list[str], start_date: str = "2020-01-01", end_date: str = None) -> dict:
    """
    Runs a backtest for a given strategy.
    
    Args:
        strategy (str): "equal_weight", "60_40", "momentum", "low_vol".
        tickers (list): Universe of assets.
        start_date (str): Start date.
        
    Returns:
        dict: Backtest results.
    """
    # Fetch data
    # We need a longer period for momentum (lookback)
    try:
        # Fetch data
        df = data_loader.get_price_history(tickers, start=start_date, end=end_date)
        
        if df.empty:
            return {"error": "No data"}
            
        # If MultiIndex, extract Close
        if isinstance(df.columns, pd.MultiIndex):
            if 'Close' in df.columns.get_level_values(0):
                df = df.xs('Close', axis=1, level=0)
            else:
                pass
        
        returns = df.pct_change()
        
        # Strategy Logic
        if strategy == "equal_weight":
            # Rebalance daily or monthly? Let's do daily rebalance for simplicity (1/N)
            # Or just average returns (implies daily rebalancing)
            port_returns = returns.mean(axis=1)
            
        elif strategy == "60_40":
            # Assumes first ticker is Stock, second is Bond
            if len(tickers) < 2:
                return {"error": "Need at least 2 assets for 60/40"}
            w = np.array([0.6, 0.4] + [0]*(len(tickers)-2))
            # Normalize if more than 2 passed but we only use first 2? 
            # Or just assume user passed SPY, TLT
            port_returns = returns.dot(w[:len(returns.columns)])
            
        elif strategy == "momentum":
            # Monthly rebalance, top decile
            # Resample to monthly
            monthly_prices = df.resample('M').last()
            monthly_ret = monthly_prices.pct_change()
            
            # 12-1 momentum (skip most recent month)
            mom_signal = monthly_prices.shift(1).pct_change(periods=11)
            
            # Generate weights
            weights = pd.DataFrame(0, index=mom_signal.index, columns=mom_signal.columns)
            
            for date, row in mom_signal.iterrows():
                # Select top N (e.g., top 30%)
                # If universe is small, select top 1 or 2
                n_select = max(1, int(len(tickers) * 0.3))
                top_assets = row.nlargest(n_select).index
                weights.loc[date, top_assets] = 1.0 / n_select
                
            # Shift weights by 1 month to avoid lookahead
            weights = weights.shift(1).dropna()
            
            # Daily returns * weights (forward fill weights to daily)
            daily_weights = weights.reindex(returns.index).ffill()
            port_returns = (returns * daily_weights).sum(axis=1)
            
        elif strategy == "low_vol":
            # Inverse volatility weighting
            # Rolling vol
            vol = returns.rolling(63).std()
            inv_vol = 1.0 / vol
            weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
            
            # Shift weights
            weights = weights.shift(1)
            port_returns = (returns * weights).sum(axis=1)
            
        else:
            return {"error": "Unknown strategy"}
            
        # Metrics
        port_returns = port_returns.dropna()
        cum_ret = (1 + port_returns).cumprod() - 1
        
        total_ret = cum_ret.iloc[-1] if not cum_ret.empty else 0
        ann_ret = (1 + total_ret) ** (252 / len(port_returns)) - 1 if len(port_returns) > 0 else 0
        ann_vol = port_returns.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        dd = (cum_ret - cum_ret.cummax()).min()
        
        return {
            "metrics": {
                "total_return": total_ret,
                "annualized_return": ann_ret,
                "annualized_volatility": ann_vol,
                "sharpe_ratio": sharpe,
                "max_drawdown": dd
            },
            "equity_curve": {
                "dates": cum_ret.index.strftime('%Y-%m-%d').tolist(),
                "values": cum_ret.tolist()
            }
        }
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return {"error": str(e)}
