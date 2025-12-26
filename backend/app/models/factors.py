import pandas as pd
import statsmodels.api as sm
import logging
import app.factors

logger = logging.getLogger(__name__)

def run_factor_regression(asset_returns: pd.Series, model: str = "ff3") -> dict:
    """
    Runs a factor regression for a given asset return series.
    
    Args:
        asset_returns (pd.Series): Daily returns of the asset.
        model (str): "ff3", "ff5", or "momentum".
        
    Returns:
        dict: Regression results (alpha, betas, r_squared, etc.)
    """
    # Load factors
    try:
        # Load factors
        if model == "ff3":
            factors_df = app.factors.load_ff3_daily()
            cols = ['Mkt-RF', 'SMB', 'HML']
        elif model == "ff5":
            factors_df = app.factors.load_ff5_daily()
            cols = ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']
        elif model == "momentum":
            # The spec says "FF3 + Momentum"
            ff3 = app.factors.load_ff3_daily()
            mom = app.factors.load_mom_daily()
            factors_df = ff3.join(mom, how='inner')
            cols = ['Mkt-RF', 'SMB', 'HML', 'Mom']
        else:
            return {"error": "Unknown model"}
            
        if factors_df.empty:
            raise ValueError("Factor data not loaded")
            
        # Align dates
        # Ensure asset_returns is named for clarity in join
        returns = asset_returns.rename("Asset")
        
        # Calculate excess returns for asset_returns if RF is available in factors_df
        if 'RF' in factors_df.columns:
            # Align RF with asset_returns index before subtraction
            rf_series = factors_df['RF'].reindex(returns.index, method='ffill')
            returns_excess = returns - rf_series
            # Drop NaNs that might result from reindexing if returns index extends beyond factors
            returns_excess = returns_excess.dropna()
        else:
            returns_excess = returns # Fallback if RF missing
            
        # Align factors_df with returns_excess index
        factors_aligned = factors_df[cols].reindex(returns_excess.index, method='ffill').dropna()
        
        # Find common index after all alignments and drops
        common_index = returns_excess.index.intersection(factors_aligned.index)
        
        if len(common_index) < 30:
             # Not enough data for regression, return dummy/fallback
             logger.warning("Not enough data for factor regression, returning placeholder")
             # Use the last 30 available dates from returns_excess for the placeholder
             placeholder_dates = returns_excess.index[-min(30, len(returns_excess)):].strftime('%Y-%m-%d').tolist()
             return {
                "alpha": 0.0,
                "betas": {col: 0.0 for col in cols}, # Placeholder for betas
                "t_stats": {}, # Placeholder
                "r_squared": 0.0,
                "adj_r_squared": 0.0,
                "n_obs": 0,
                "dates": {
                    "start": placeholder_dates[0] if placeholder_dates else None,
                    "end": placeholder_dates[-1] if placeholder_dates else None
                }
             }
             
        y = returns_excess.loc[common_index]
        X = factors_aligned.loc[common_index]
        
        # Add constant for alpha
        X = sm.add_constant(X)
        
        model_fit = sm.OLS(y, X).fit()
        
        results = {
            "alpha": model_fit.params.get("const", 0),
            "betas": {col: model_fit.params.get(col, 0) for col in cols},
            "t_stats": model_fit.tvalues.to_dict(),
            "r_squared": model_fit.rsquared,
            "adj_r_squared": model_fit.rsquared_adj,
            "n_obs": int(model_fit.nobs),
            "dates": {
                "start": common_index[0].strftime('%Y-%m-%d'),
                "end": common_index[-1].strftime('%Y-%m-%d')
            }
        }
        return results
    except Exception as e:
        logger.error(f"Regression failed: {e}")
        return {"error": str(e)}

def get_rolling_betas(asset_returns: pd.Series, window: int = 252*3) -> pd.DataFrame:
    """
    Computes rolling betas against the market (CAPM) or FF3.
    For simplicity, let's do CAPM beta rolling.
    """
    factors = app.factors.load_ff3_daily()
    if factors.empty:
        return pd.DataFrame()
        
    data = factors.join(asset_returns.rename("Asset"), how='inner')
    if data.empty:
        return pd.DataFrame()
        
    # Rolling regression is expensive if done loop-wise in Python for many windows
    # We can use RollingOLS from statsmodels
    from statsmodels.regression.rolling import RollingOLS
    
    y = data['Asset'] - data['RF']
    X = sm.add_constant(data['Mkt-RF'])
    
    try:
        rols = RollingOLS(y, X, window=window)
        rres = rols.fit()
        params = rres.params.copy()
        params.columns = ['Alpha', 'Beta_Mkt']
        return params
    except Exception as e:
        logger.error(f"Rolling OLS failed: {e}")
        return pd.DataFrame()
