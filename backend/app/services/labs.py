import pandas as pd
import numpy as np
import statsmodels.api as sm
from arch import arch_model
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from hmmlearn.hmm import GaussianHMM
import logging
import os

from app.factor_data import load_factors, get_combined_factors
from app.data_loader import get_universe
from app.services.portfolio import load_price_data

logger = logging.getLogger(__name__)

# Helper to load price data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "prices")
FACTOR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "factors_us")

def load_price_data(ticker):
    try:
        path = os.path.join(DATA_DIR, f"{ticker}.csv")
        if not os.path.exists(path):
            return pd.DataFrame()
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df
    except Exception as e:
        logger.error(f"Error loading {ticker}: {e}")
        return pd.DataFrame()

def load_factors():
    try:
        # Load Fama-French 3 factors + Momentum
        ff3_path = os.path.join(FACTOR_DIR, "ff3_daily.csv")
        mom_path = os.path.join(FACTOR_DIR, "momentum_daily.csv")
        
        # AUDIT FIX: Ken French files have 5-6 lines of metadata at the top
        # We need to find the actual header row
        def read_ff_csv(filepath):
            with open(filepath, 'r') as f:
                lines = f.readlines()
            
            # Find header row (contains comma-separated factor names)
            header_row = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if ',' in stripped and ('Mkt-RF' in stripped or 'Mom' in stripped or stripped.startswith(',')):
                    header_row = i
                    break
            
            df = pd.read_csv(filepath, skiprows=header_row)
            df.columns = [c.strip() for c in df.columns]
            
            # Handle date column
            first_col = df.columns[0]
            if first_col == '' or 'unnamed' in first_col.lower():
                df = df.rename(columns={first_col: 'Date'})
            if df.columns[0] != 'Date':
                df = df.rename(columns={df.columns[0]: 'Date'})
            
            # Parse dates (handle YYYYMMDD format)
            date_sample = str(df['Date'].iloc[0])
            if len(date_sample) == 8 and date_sample.isdigit():
                df['Date'] = pd.to_datetime(df['Date'].astype(str), format='%Y%m%d', errors='coerce')
            else:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            
            df = df.dropna(subset=['Date'])
            df = df.set_index('Date')
            
            # AUDIT FIX: Unconditionally divide by 100 (FF data is in percentage format)
            for col in df.columns:
                df[col] = df[col] / 100.0
            
            return df
        
        ff3 = read_ff_csv(ff3_path)
        mom = read_ff_csv(mom_path)
        
        # Join and clean
        factors = ff3.join(mom, how='inner').dropna()
        
        # Normalize names
        factors.columns = [c.strip() for c in factors.columns]
        
        return factors
    except Exception as e:
        logger.error(f"Error loading factors: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return pd.DataFrame()

# --- 1A Factors Lab ---
def run_factor_regression(ticker, window_years=3, model="ff3"):
    prices = load_price_data(ticker)
    if prices.empty:
        return {"error": f"No data for {ticker}"}
        
    factors = load_factors()
    if factors.empty:
        return {"error": "No factor data available"}
        
    # Calculate daily returns
    returns = prices['Close'].pct_change().dropna()
    returns.name = "Asset"
    
    # Align data
    data = pd.concat([returns, factors], axis=1).dropna()
    
    # Filter by window
    end_date = data.index.max()
    start_date = end_date - pd.DateOffset(years=window_years)
    data = data[data.index >= start_date]
    
    if len(data) < 252: # Require at least 1 year of data
        return {"error": "Insufficient data for regression"}
        
    # Excess returns: Asset - RF
    if 'RF' in data.columns:
        y = data['Asset'] - data['RF']
    else:
        y = data['Asset']
        
    # Select X variables based on model
    # Standard names in our CSVs (loaded in load_factors): 'Mkt-RF', 'SMB', 'HML', 'Mom'
    # Note: load_factors joins FF3 and Mom, so we have all columns.
    
    if model == "ff3":
        x_cols = ['Mkt-RF', 'SMB', 'HML']
    elif model == "ff5":
        # We only have FF3 + Mom loaded in load_factors currently. 
        # If FF5 is requested but we don't have RMW/CMA, fallback to FF3 or error?
        # For now, let's assume we might have them or just use what we have.
        # If the user provided ff5_daily.csv, we would have them.
        # Let's check available columns.
        possible_cols = ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']
        x_cols = [c for c in possible_cols if c in data.columns]
    elif model == "ff5_mom":
        possible_cols = ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA', 'Mom', 'MOM']
        x_cols = [c for c in possible_cols if c in data.columns]
    elif model == "momentum":
        # Just Market + Momentum? Or just Momentum? Usually Market + Mom.
        possible_cols = ['Mkt-RF', 'Mom', 'MOM']
        x_cols = [c for c in possible_cols if c in data.columns]
    else:
        # Default to FF3
        x_cols = ['Mkt-RF', 'SMB', 'HML']
        
    # Filter for columns that actually exist
    x_cols = [c for c in x_cols if c in data.columns]
    
    if not x_cols:
        return {"error": "Model factors not found in data"}

    X = data[x_cols]
    X = sm.add_constant(X)
    
    model_res = sm.OLS(y, X).fit()
    
    # Calculate cumulative returns for chart
    # Asset cumulative return
    asset_cum = (1 + returns[data.index]).cumprod()
    asset_cum = asset_cum / asset_cum.iloc[0]
    
    # Factor model fitted return (benchmark)
    # fitted values are excess returns, so add back RF if we subtracted it
    fitted_excess = model_res.fittedvalues
    if 'RF' in data.columns:
        fitted_ret = fitted_excess + data['RF']
    else:
        fitted_ret = fitted_excess
        
    model_cum = (1 + fitted_ret).cumprod()
    model_cum = model_cum / model_cum.iloc[0]
    
    return {
        "ticker": ticker,
        "window_years": window_years,
        "model": model,
        "betas": model_res.params.to_dict(),
        "t_stats": model_res.tvalues.to_dict(),
        "r_squared": model_res.rsquared,
        "alpha_annualized": model_res.params.get('const', 0) * 252,
        "dates": data.index.strftime('%Y-%m-%d').tolist(),
        "asset_cum_ret": asset_cum.tolist(),
        "model_cum_ret": model_cum.tolist()
    }

# --- 1B Volatility Lab ---
def run_volatility_analysis(ticker, window_years=1):
    prices = load_price_data(ticker)
    if prices.empty:
        return {"error": f"No data for {ticker}"}
        
    # Log returns
    returns = np.log(prices['Close'] / prices['Close'].shift(1)).dropna()
    
    # Filter window
    end_date = returns.index.max()
    start_date = end_date - pd.DateOffset(years=window_years)
    returns = returns[returns.index >= start_date]
    
    if len(returns) < 252:
        return {"error": "Insufficient data"}
        
    # 1. Realized Vol (21d rolling)
    realized_vol = returns.rolling(window=21).std() * np.sqrt(252)
    
    # 2. EWMA Vol (lambda=0.94)
    # RiskMetrics approach: sigma_t^2 = lambda * sigma_{t-1}^2 + (1-lambda) * r_{t-1}^2
    # Pandas ewm can approximate this
    ewma_vol = returns.ewm(alpha=0.06, adjust=False).std() * np.sqrt(252)
    
    # 3. GARCH(1,1)
    # Scale returns by 100 for better numerical stability in optimization
    am = arch_model(returns * 100, vol='Garch', p=1, o=0, q=1, dist='Normal')
    res = am.fit(disp='off')
    
    # Conditional vol (sigma)
    garch_vol = res.conditional_volatility / 100 * np.sqrt(252)
    
    # Forecast 21 days ahead
    forecast = res.forecast(horizon=21)
    # Get the annualized vol forecast for the next 21 days (mean of variances)
    # forecast.variance is variance per day
    next_21_vars = forecast.variance.iloc[-1].values
    garch_forecast_21d = np.sqrt(np.mean(next_21_vars)) * np.sqrt(252) / 100
    
    return {
        "ticker": ticker,
        "dates": returns.index.strftime('%Y-%m-%d').tolist(),
        "realized_vol": realized_vol.fillna(0).tolist(),
        "ewma_vol": ewma_vol.fillna(0).tolist(),
        "garch_vol": garch_vol.tolist(),
        "garch_forecast_21d": garch_forecast_21d,
        "garch_params": res.params.to_dict()
    }

# --- 1C Regimes Lab ---
def run_regime_detection(ticker, window_years=3):
    prices = load_price_data(ticker)
    if prices.empty:
        return {"error": f"No data for {ticker}"}
        
    returns = prices['Close'].pct_change().dropna()
    
    end_date = returns.index.max()
    start_date = end_date - pd.DateOffset(years=window_years)
    returns = returns[returns.index >= start_date]
    
    if len(returns) < 252:
        return {"error": "Insufficient data"}
        
    # Option 2: Volatility Threshold (Simpler, robust)
    vol = returns.rolling(window=21).std() * np.sqrt(252)
    threshold = vol.median()
    
    regimes = (vol > threshold).astype(int) # 0 = Low Vol, 1 = High Vol
    
    # Stats per regime
    stats = {}
    for r in [0, 1]:
        mask = regimes == r
        r_rets = returns[mask]
        stats[str(r)] = {
            "mean_return": r_rets.mean(),
            "volatility": r_rets.std() * np.sqrt(252),
            "probability": len(r_rets) / len(returns)
        }
        
    return {
        "ticker": ticker,
        "dates": returns.index.strftime('%Y-%m-%d').tolist(),
        "prices": prices.loc[returns.index]['Close'].tolist(),
        "regime_labels": regimes.fillna(0).tolist(),
        "regime_stats": stats
    }

# --- 1D PCA Lab ---
def run_pca_analysis(tickers=None):
    if not tickers:
        tickers = ["SPY", "QQQ", "DIA", "IWM", "XLK", "XLF", "XLY", "XLP", "XLE", "XLV", "XLRE", "XLU"]
        
    # Load all data
    data = {}
    for t in tickers:
        df = load_price_data(t)
        if not df.empty:
            data[t] = df['Close']
            
    if not data:
        return {"error": "No data found"}
        
    prices = pd.DataFrame(data)
    returns = prices.pct_change().dropna()
    
    # Last 3 years
    end_date = returns.index.max()
    start_date = end_date - pd.DateOffset(years=3)
    returns = returns[returns.index >= start_date]
    
    if returns.empty:
        return {"error": "Insufficient data"}
        
    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(returns)
    
    # PCA
    pca = PCA()
    pca.fit(X_scaled)
    
    # Components
    n_comps = min(10, len(tickers))
    explained_var = pca.explained_variance_ratio_[:n_comps]
    
    loadings = pd.DataFrame(
        pca.components_[:n_comps].T,
        columns=[f"PC{i+1}" for i in range(n_comps)],
        index=tickers
    )
    
    # Scores (Time series of PCs)
    scores = pca.transform(X_scaled)
    
    return {
        "tickers": tickers,
        "component_labels": [f"PC{i+1}" for i in range(n_comps)],
        "explained_variance": explained_var.tolist(),
        "loadings": loadings.to_dict(orient='index'), # {ticker: {PC1: x, PC2: y}}
        "dates": returns.index.strftime('%Y-%m-%d').tolist(),
        "pc1": scores[:, 0].tolist(),
        "pc2": scores[:, 1].tolist()
    }

# --- 1E Factor Screener ---
def get_factor_screen(universe="us"):
    tickers = get_universe(universe)
    if not tickers:
        return []
        
    results = []
    
    # Pre-fetch all data to avoid sequential delay? 
    # For now, sequential is fine for 40 tickers.
    
    for t in tickers:
        try:
            df = load_price_data(t)
            if df.empty or len(df) < 252:
                continue
                
            # Calculate Factors
            
            # 1. Momentum (12M return, skipping last 1M usually, but let's do simple 12M)
            # Ret_12m = P_t / P_{t-252} - 1
            current_price = df['Close'].iloc[-1]
            price_1y_ago = df['Close'].iloc[-252]
            momentum = (current_price / price_1y_ago) - 1
            
            # 2. Volatility (3M annualized)
            # 63 days
            recent_returns = df['Close'].pct_change().tail(63).dropna()
            volatility = recent_returns.std() * np.sqrt(252)
            
            # 3. Liquidity (Avg Volume 3M)
            if 'Volume' in df.columns:
                avg_volume = df['Volume'].tail(63).mean()
            else:
                avg_volume = 1000000.0 # Default mock volume
            
            # Score: High Mom, Low Vol
            # Simple Z-score like approach?
            # Let's just do a weighted score of raw values for simplicity in demo
            # But Vol is bad, Mom is good.
            # Score = Mom - Vol
            score = momentum - volatility
            
            results.append({
                "ticker": t,
                "momentum": momentum,
                "volatility": volatility,
                "liquidity": avg_volume,
                "score": score
            })
            
        except Exception as e:
            logger.error(f"Error screening {t}: {e}")
            continue
            
    # Sort by Score desc
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return results
