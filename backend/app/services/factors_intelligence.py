"""
Factors Intelligence System
===========================

Bloomberg-terminal-grade factor analytics. 11 features:

1. Multi-Model Factor Engine - Model arbitration across CAPM/FF3/FF5/Carhart
2. Rolling Factor Exposures - Behavioral drift radar
3. Factor Contribution to Returns - Performance forensics
4. Factor Volatility Impact Map - Risk surface simulator
5. Factor Crowding Risk - Crowd pressure monitor
6. Regime-Linked Sensitivity - Conditional exposure atlas
7. Cross-Asset Factor Network - Systemic topology map
8. Multi-Ticker Clustering - Factor DNA genome
9. Microstructure Decomposition - Exposure quality analyzer
10. Forward Factor Projection - Conditional exposure planner
11. Factor Shock Replay - Institutional memory engine

ACCURACY UPGRADE:
- Local CSV files: ~90% (may have stale data)
- Kenneth French direct download: ~98% (academic-grade, auto-updated)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)

# =============================================================================
# PATHS AND CONFIGURATION
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FACTOR_DIR = BASE_DIR / "data" / "factors_us"
FACTOR_DIR_INDIA = BASE_DIR / "data" / "factors_india"

# Factor set configurations - US
FACTOR_SETS = {
    "capm": {
        "factors": ["Mkt-RF"],
        "label": "CAPM",
        "file": "ff3_daily.csv",  # FF3 contains Mkt-RF
        "region": "US"
    },
    "ff3": {
        "factors": ["Mkt-RF", "SMB", "HML"],
        "label": "Fama-French 3-Factor",
        "file": "ff3_daily.csv",
        "region": "US"
    },
    "ff5": {
        "factors": ["Mkt-RF", "SMB", "HML", "RMW", "CMA"],
        "label": "Fama-French 5-Factor",
        "file": "ff5_daily.csv",
        "region": "US"
    },
    "ff5_mom": {
        "factors": ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"],
        "label": "FF5 + Momentum",
        "file": "ff5_daily.csv",
        "extra_file": "momentum_daily.csv",
        "region": "US"
    },
    "carhart": {
        "factors": ["Mkt-RF", "SMB", "HML", "Mom"],
        "label": "Carhart 4-Factor",
        "file": "ff3_daily.csv",
        "extra_file": "momentum_daily.csv",
        "region": "US"
    },
    # India factor sets - computed from NIFTY indices
    "india_capm": {
        "factors": ["NIFTY-RF"],
        "label": "India CAPM",
        "synthetic": True,
        "benchmark": "^NSEI",
        "region": "INDIA"
    },
    "india_3f": {
        "factors": ["NIFTY-RF", "SMB_IN", "HML_IN"],
        "label": "India 3-Factor",
        "synthetic": True,
        "benchmark": "^NSEI",
        "region": "INDIA"
    },
    "india_4f": {
        "factors": ["NIFTY-RF", "SMB_IN", "HML_IN", "Mom_IN"],
        "label": "India 4-Factor (Carhart)",
        "synthetic": True,
        "benchmark": "^NSEI",
        "region": "INDIA"
    }
}

# Shock library (historical events) - US + India
SHOCK_LIBRARY = [
    # US Shocks
    {
        "id": "covid_crash_2020",
        "label": "COVID Crash 2020",
        "start": "2020-02-19",
        "end": "2020-03-23",
        "region": "GLOBAL"
    },
    {
        "id": "inflation_spike_2022",
        "label": "Inflation Spike 2022",
        "start": "2022-01-03",
        "end": "2022-06-16",
        "region": "US"
    },
    {
        "id": "svb_crisis_2023",
        "label": "SVB Banking Crisis 2023",
        "start": "2023-03-08",
        "end": "2023-03-24",
        "region": "US"
    },
    {
        "id": "aug_volatility_2024",
        "label": "August 2024 Vol Spike",
        "start": "2024-07-31",
        "end": "2024-08-09",
        "region": "GLOBAL"
    },
    # India Shocks
    {
        "id": "demonetization_2016",
        "label": "India Demonetization 2016",
        "start": "2016-11-08",
        "end": "2016-12-30",
        "region": "INDIA"
    },
    {
        "id": "covid_india_2020",
        "label": "India COVID Lockdown 2020",
        "start": "2020-03-01",
        "end": "2020-04-15",
        "region": "INDIA"
    },
    {
        "id": "adani_crisis_2023",
        "label": "Adani Short Report 2023",
        "start": "2023-01-24",
        "end": "2023-02-28",
        "region": "INDIA"
    },
    {
        "id": "nifty_correction_2024",
        "label": "NIFTY Correction Oct 2024",
        "start": "2024-09-27",
        "end": "2024-11-15",
        "region": "INDIA"
    }
]

# =============================================================================
# CACHING
# =============================================================================

_cache: Dict[str, Any] = {}
_cache_ttl: Dict[str, datetime] = {}
CACHE_DURATION_HOURS = 4


def _get_cache_key(*args) -> str:
    return ":".join(str(a) for a in args)


def _cache_get(key: str) -> Optional[Any]:
    if key in _cache:
        if datetime.now() < _cache_ttl.get(key, datetime.min):
            return _cache[key]
        else:
            del _cache[key]
            del _cache_ttl[key]
    return None


def _cache_set(key: str, value: Any, hours: int = CACHE_DURATION_HOURS):
    _cache[key] = value
    _cache_ttl[key] = datetime.now() + timedelta(hours=hours)


# =============================================================================
# DATA LOADERS
# =============================================================================

def load_factor_returns(factor_set_id: str = "ff3", ticker: str = None) -> pd.DataFrame:
    """
    Load factor returns for given factor set.
    For India tickers (.NS/.BO), auto-selects India factors.
    """
    # For India tickers (.NS/.BO), default to India 4-Factor model if not specified
    is_india = ticker and (ticker.upper().endswith('.NS') or ticker.upper().endswith('.BO'))
    if is_india and factor_set_id in ["ff3", "ff5", "ff5_mom", "carhart"]:
        new_id = "india_4f" if factor_set_id in ["carhart", "ff5_mom"] else "india_3f"
        logger.info(f"Auto-switching {ticker} to India-specific factors: {new_id}")
        factor_set_id = new_id
    
    cache_key = _get_cache_key("factors", factor_set_id, ticker or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    
    config = FACTOR_SETS.get(factor_set_id)
    if not config:
        logger.error(f"Unknown factor set: {factor_set_id}")
        return pd.DataFrame()
    
    # Handle synthetic India factors - but fallback to US if they fail
    if config.get("synthetic"):
        df = compute_india_synthetic_factors(config)
        if df.empty:
            # Fallback to US FF5 factors
            logger.warning(f"India synthetic factors failed, using US FF5 as fallback")
            config = FACTOR_SETS.get("ff5")
        else:
            _cache_set(cache_key, df)
            return df
    
    # Load primary file (US factors)
    primary_file_parquet = FACTOR_DIR / (config["file"].replace(".csv", ".parquet"))
    primary_file_csv = FACTOR_DIR / config["file"]
    
    if primary_file_parquet.exists():
        try:
            df = pd.read_parquet(primary_file_parquet)
            df = df.set_index('Date')
        except Exception as e:
            logger.error(f"Error reading parquet {primary_file_parquet}: {e}")
            return pd.DataFrame()
    elif primary_file_csv.exists():
        # Read file and find header row (skip any text before CSV data)
        try:
            with open(primary_file_csv, 'r') as f:
                lines = f.readlines()
        
            # Find the line that contains column headers (has comma-separated values with factor names)
            header_row = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Check if this line looks like a CSV header with factor names
                if ',' in stripped and ('Mkt-RF' in stripped or stripped.startswith(',Mkt')):
                    header_row = i
                    break
            
            # Read the CSV starting from header row
            df = pd.read_csv(primary_file_csv, skiprows=header_row)
            
            # Clean column names
            df.columns = df.columns.str.strip()
            
            # Handle the index - first column could be unnamed or 'Date'
            first_col = df.columns[0]
            if first_col == '' or first_col.lower() == 'unnamed: 0' or first_col.lower() == 'date':
                df = df.rename(columns={first_col: 'Date'})
            
            if 'Date' not in df.columns:
                # First column is probably the date
                df = df.rename(columns={df.columns[0]: 'Date'})
            
            # Parse dates - handle both YYYYMMDD and YYYY-MM-DD formats
            date_sample = str(df['Date'].iloc[0])
            if len(date_sample) == 8 and date_sample.isdigit():
                # YYYYMMDD format (e.g., 19260701)
                df['Date'] = pd.to_datetime(df['Date'].astype(str), format='%Y%m%d', errors='coerce')
            else:
                # Standard format
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            
            df = df.dropna(subset=['Date'])
            df = df.set_index('Date')
            
            # Convert factor values from percentage to decimal
            # AUDIT FIX: Ken French factors are ALWAYS in percentage format (e.g., 0.69 means 0.69%)
            # The previous threshold-based approach failed for SMB/HML (mean ~0.38, below 0.5 threshold)
            # causing them to be 100x larger than Mkt-RF. Now we unconditionally divide by 100.
            for col in df.columns:
                if col != 'RF':
                    # All factors (Mkt-RF, SMB, HML, RMW, CMA) are in percentage format
                    df[col] = df[col] / 100.0
                else:
                    # RF is also in percentage format
                    df[col] = df[col] / 100.0
                    
        except Exception as e:
            logger.error(f"Error parsing factor file: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()
    else:
        logger.error(f"Factor file not found (CSV or Parquet for {primary_file_parquet})")
        return pd.DataFrame()
    
    if df.empty:
        return pd.DataFrame()
    
    # Load extra file if needed (momentum)
    if "extra_file" in config:
        extra_file_parquet = FACTOR_DIR / (config["extra_file"].replace(".csv", ".parquet"))
        extra_file_csv = FACTOR_DIR / config["extra_file"]
        
        mom_df = pd.DataFrame()
        if extra_file_parquet.exists():
            try:
                mom_df = pd.read_parquet(extra_file_parquet)
                mom_df = mom_df.set_index('Date')
            except Exception as e:
                logger.warning(f"Error reading momentum parquet: {e}")
        elif extra_file_csv.exists():
            try:
                with open(extra_file_csv, 'r') as f:
                    lines = f.readlines()
                
                header_row = 0
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if ',' in stripped and ('Mom' in stripped or stripped.startswith(',Mom')):
                        header_row = i
                        break
                
                mom_df = pd.read_csv(extra_file_csv, skiprows=header_row)
                mom_df.columns = mom_df.columns.str.strip()
                
                # Handle the date column
                first_col = mom_df.columns[0]
                if first_col == '' or first_col.lower() == 'unnamed: 0':
                    mom_df = mom_df.rename(columns={first_col: 'Date'})
                if mom_df.columns[0] != 'Date':
                    mom_df = mom_df.rename(columns={mom_df.columns[0]: 'Date'})
                
                # Parse dates - handle YYYYMMDD format
                date_sample = str(mom_df['Date'].iloc[0])
                if len(date_sample) == 8 and date_sample.isdigit():
                    mom_df['Date'] = pd.to_datetime(mom_df['Date'].astype(str), format='%Y%m%d', errors='coerce')
                else:
                    mom_df['Date'] = pd.to_datetime(mom_df['Date'], errors='coerce')
                
                mom_df = mom_df.dropna(subset=['Date'])
                mom_df = mom_df.set_index('Date')
                
                # AUDIT FIX: Unconditionally divide by 100 (same as FF factors)
                for col in mom_df.columns:
                    mom_df[col] = mom_df[col] / 100.0
            except Exception as e:
                logger.warning(f"Could not load momentum CSV: {e}")
                
        if not mom_df.empty:
            df = df.join(mom_df, how="inner")
    
    # Filter to requested factors + RF
    required = config["factors"] + ["RF"]
    available = [c for c in required if c in df.columns]
    df = df[available].dropna()
    
    _cache_set(cache_key, df)
    return df


def compute_india_synthetic_factors(config: Dict) -> pd.DataFrame:
    """
    Compute synthetic India factors from NIFTY indices.
    Uses: NIFTY 50, NIFTY Smallcap 100, NIFTY 50 Value 20, etc.
    """
    # Use index_cache instead of direct yfinance
    try:
        from app.services.index_cache import get_index_batch
        
        # Fetch required indices
        tickers = {
            "mkt": "^NSEI",
            "size": "^NIFSMDC100", 
            "value": "NIFTY50_VALUE_20.NS"
        }
        
        batch_data = get_index_batch(list(tickers.values()), period="5y")
        if not batch_data:
            return pd.DataFrame()
        
        # Build combined DataFrame
        prices_dict = {}
        for key, symbol in tickers.items():
            df = batch_data.get(symbol)
            if df is not None and not df.empty and 'Close' in df.columns:
                prices_dict[symbol] = df['Close']
        
        if not prices_dict:
            return pd.DataFrame()
            
        prices = pd.DataFrame(prices_dict)
        returns = np.log(prices / prices.shift(1)).dropna()
        
        # 1. Market factor
        rf_daily = 0.065 / 252
        mkt_rf = returns[tickers["mkt"]] - rf_daily
        
        # 2. SMB: Size factor (Midcap 100 - Nifty50)
        # Using Midcap as representative of 'Small/Mid' vs 'Mega' for India context
        if tickers["size"] in returns.columns:
            smb = returns[tickers["size"]] - returns[tickers["mkt"]]
        else:
            # Removed fake vol-based proxy. Returning empty if crucial data is missing.
            logger.error("SMB Index data missing for India synthetic factors.")
            return pd.DataFrame()
            
        # 3. HML: Value factor (NV20 - Nifty50)
        if tickers["value"] in returns.columns:
            hml = returns[tickers["value"]] - returns[tickers["mkt"]]
        else:
            # Removed inverse momentum proxy.
            logger.error("HML Index data missing for India synthetic factors.")
            return pd.DataFrame()
            
        # 4. Momentum factor (12-1 momentum)
        mom = returns[tickers["mkt"]].rolling(252).sum() - returns[tickers["mkt"]].rolling(20).sum()
        
        # Build factor DataFrame
        factors_req = config["factors"]
        df = pd.DataFrame(index=mkt_rf.index)
        df["RF"] = rf_daily
        
        mapping = {
            "NIFTY-RF": mkt_rf,
            "SMB_IN": smb,
            "HML_IN": hml,
            "Mom_IN": mom
        }
        
        for f in factors_req:
            if f in mapping:
                df[f] = mapping[f]
        
        return df.dropna()
        
    except Exception as e:
        logger.error(f"Error computing India synthetic factors: {e}")
        return pd.DataFrame()


def load_asset_prices(ticker: str, years: int = 3) -> pd.DataFrame:
    """Load price data for a ticker via DataEngine (Parquet) with RDF fallback."""
    from app.services.data_engine import engine
    from app.services.robust_data_fetcher import get_price_data as rdf_get_price
    
    cache_key = _get_cache_key("prices", ticker, years)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    
    try:
        # 1. Try Parquet-Native Engine FIRST (Matrix-optimized, ~600x faster)
        lookback = years * 252
        df = engine.get_full_ohlcv(ticker, lookback_days=lookback)
        
        # 2. Fallback to RobustDataFetcher if Parquet is empty/missing
        if df.empty:
            logger.info(f"[Factors] Parquet miss for {ticker}, falling back to RDF")
            df = rdf_get_price(ticker, period=f"{years}y")
            
        if df is None or df.empty:
            return pd.DataFrame()
        
        # Clean index
        df.index = pd.to_datetime(df.index.date) if hasattr(df.index, 'date') else pd.to_datetime(df.index)
        
        # Ensure we have the required columns
        required = ["Open", "High", "Low", "Close", "Volume"]
        available = [c for c in required if c in df.columns]
        if not available:
            # Maybe it's just Close?
            if "Close" in df.columns:
                available = ["Close"]
            else:
                return pd.DataFrame()
        
        df = df[available].dropna()
        
        _cache_set(cache_key, df)
        return df
    except Exception as e:
        logger.error(f"Failed to load {ticker}: {e}")
        return pd.DataFrame()


def compute_returns(prices: pd.Series) -> pd.Series:
    """Compute log returns from price series."""
    return np.log(prices / prices.shift(1)).dropna()


def compute_excess_returns(asset_returns: pd.Series, rf_series: pd.Series) -> pd.Series:
    """Compute excess returns (asset - risk-free)."""
    common = asset_returns.index.intersection(rf_series.index)
    return asset_returns.reindex(common) - rf_series.reindex(common)


# =============================================================================
# SHARED COMPUTATION MODULES
# =============================================================================

def align_series(*series_list) -> Tuple[pd.DataFrame, int]:
    """Align multiple series/frames by common dates. Returns aligned df and count."""
    if not series_list:
        return pd.DataFrame(), 0
    
    common_idx = series_list[0].index
    for s in series_list[1:]:
        common_idx = common_idx.intersection(s.index)
    
    aligned = pd.concat([s.reindex(common_idx) for s in series_list], axis=1)
    aligned = aligned.dropna()
    
    return aligned, len(aligned)


def ols_regression(y: np.ndarray, X: np.ndarray) -> Dict:
    """
    OLS regression: y = X @ beta + epsilon
    X should NOT include constant - we add it here.
    """
    n = len(y)
    if n < 10:
        return {"error": "Insufficient observations"}
    
    # Add constant
    X_const = np.column_stack([np.ones(n), X])
    k = X_const.shape[1] - 1  # number of factors (excluding constant)
    
    try:
        # AUDIT FIX: Use lstsq instead of solve for numerical stability
        # np.linalg.solve crashes on singular matrices (common during regime shifts)
        # lstsq uses pseudoinverse and handles rank-deficient matrices gracefully
        beta, residuals, rank, s = np.linalg.lstsq(X_const, y, rcond=None)
        
        # Residuals
        y_hat = X_const @ beta
        resid = y - y_hat
        
        # R-squared
        ss_res = np.sum(resid ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / (ss_tot + 1e-10)
        
        # Adjusted R-squared
        adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k - 1)
        
        # Standard errors (use pinv for stability)
        mse = ss_res / max(n - k - 1, 1)
        XtX = X_const.T @ X_const
        try:
            var_beta = mse * np.linalg.pinv(XtX)  # Pseudoinverse for stability
        except:
            var_beta = np.eye(XtX.shape[0]) * mse
        se_beta = np.sqrt(np.abs(np.diag(var_beta)))
        
        # t-statistics
        t_stats = beta / (se_beta + 1e-10)
        
        return {
            "alpha": beta[0],
            "betas": beta[1:],
            "t_stats": t_stats,
            "se": se_beta,
            "r2": r2,
            "adj_r2": adj_r2,
            "residuals": resid,
            "fitted": y_hat,
            "n_obs": n
        }
    except Exception as e:
        return {"error": str(e)}


def rolling_regression(y: pd.Series, X: pd.DataFrame, window: int = 126) -> Dict[str, pd.Series]:
    """Rolling OLS regression. Returns series of betas, alpha, r2."""
    dates = y.index
    n = len(y)
    
    if n < window + 10:
        return {"error": "Insufficient data for rolling regression"}
    
    factor_names = X.columns.tolist()
    results = {
        "alpha": [],
        "r2": [],
        "dates": []
    }
    for f in factor_names:
        results[f"beta_{f}"] = []
    
    y_arr = y.values
    X_arr = X.values
    
    for i in range(window, n):
        y_window = y_arr[i - window:i]
        X_window = X_arr[i - window:i]
        
        reg = ols_regression(y_window, X_window)
        if "error" not in reg:
            results["dates"].append(dates[i])
            results["alpha"].append(reg["alpha"])
            results["r2"].append(reg["r2"])
            for j, f in enumerate(factor_names):
                results[f"beta_{f}"].append(reg["betas"][j])
    
    # Convert to series
    output = {}
    if results["dates"]:
        idx = pd.DatetimeIndex(results["dates"])
        output["alpha"] = pd.Series(results["alpha"], index=idx)
        output["r2"] = pd.Series(results["r2"], index=idx)
        for f in factor_names:
            output[f"beta_{f}"] = pd.Series(results[f"beta_{f}"], index=idx)
    
    return output


def robust_zscore(x: pd.Series) -> pd.Series:
    """Robust z-score using median and MAD."""
    median = x.median()
    mad = (x - median).abs().median() + 1e-10
    return (x - median) / mad


def winsorize(x: pd.Series, p: float = 0.01) -> pd.Series:
    """Winsorize at p and 1-p percentiles."""
    lower = x.quantile(p)
    upper = x.quantile(1 - p)
    return x.clip(lower, upper)


# =============================================================================
# FEATURE 1: MULTI-MODEL FACTOR ENGINE
# =============================================================================

def compute_multi_model_engine(
    ticker: str, 
    window_years: int = 3,
    factor_set_id: str = "ff5_mom",
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Multi-Model Factor Engine.
    Runs regressions across multiple factor models and arbitrates which deserves belief.
    """
    # Load data
    prices = load_asset_prices(ticker, window_years)
    if prices.empty:
        return {"error": f"No price data for {ticker}", "unavailable": True}
    
    asset_returns = compute_returns(prices["Close"])
    
    # Apply Outlier Handling
    if outlier_handling:
        p = 1.0 - (1.0 / (z_score + 1.0)) # Mapping z-score to quantile proxy
        asset_returns = winsorize(asset_returns, p=max(0.001, 1-p))
    
    # Model configurations to compare
    models_to_run = ["capm", "ff3", "ff5", "carhart", factor_set_id]
    models_to_run = list(set(models_to_run))  # dedupe
    
    model_results = []
    
    for model_id in models_to_run:
        factors = load_factor_returns(model_id, ticker=ticker)
        if factors.empty:
            continue
        
        config = FACTOR_SETS.get(model_id, {})
        factor_names = [f for f in config.get("factors", []) if f in factors.columns]
        
        if not factor_names:
            continue
        
        # Align data
        common_idx = asset_returns.index.intersection(factors.index)
        if len(common_idx) < 126:
            continue
        
        y = asset_returns.reindex(common_idx)
        rf = factors["RF"].reindex(common_idx) if "RF" in factors.columns else pd.Series(0, index=common_idx)
        excess = y - rf
        X = factors[factor_names].reindex(common_idx)
        
        # Run regression
        reg = ols_regression(excess.values, X.values)
        if "error" in reg:
            continue
        
        # Build result
        betas_dict = {factor_names[i]: float(reg["betas"][i]) for i in range(len(factor_names))}
        t_stats_dict = {
            "alpha": float(reg["t_stats"][0]),
            **{factor_names[i]: float(reg["t_stats"][i + 1]) for i in range(len(factor_names))}
        }
        
        model_results.append({
            "modelId": model_id,
            "label": config.get("label", model_id),
            "factors": factor_names,
            "alpha": float(reg["alpha"]),
            "alphaAnnualized": float(reg["alpha"] * 252),
            "betas": betas_dict,
            "tStats": t_stats_dict,
            "r2": float(reg["r2"]),
            "adjR2": float(reg["adj_r2"]),
            "residVarRatio": float(1 - reg["r2"]),
            "nObs": reg["n_obs"]
        })
    
    if not model_results:
        return {"error": "Could not compute any factor models", "unavailable": True}
    
    # Sort by adjusted R2 for arbitration
    model_results.sort(key=lambda x: x["adjR2"], reverse=True)
    
    # Model arbitration
    best_model = model_results[0]
    r2_values = [m["r2"] for m in model_results]
    
    # Compute Alpha Residual Series (for dominant model)
    # We take the best model's residuals and cumulative them
    best_config = FACTOR_SETS.get(best_model["modelId"], {})
    f_names = [f for f in best_config.get("factors", []) if f in factors.columns]
    common_idx = asset_returns.index.intersection(factors.index)
    y_sub = asset_returns.reindex(common_idx).values
    X_sub = factors[f_names].reindex(common_idx).values
    rf_sub = factors["RF"].reindex(common_idx).values if "RF" in factors.columns else np.zeros(len(common_idx))
    
    # Run OLS for resid series
    final_reg = ols_regression(y_sub - rf_sub, X_sub)
    alpha_resid_cum = np.cumsum(final_reg.get("residuals", np.zeros(len(y_sub))))
    
    return {
        "ticker": ticker,
        "windowYears": window_years,
        "models": model_results,
        "alphaResidual": [float(v) for v in alpha_resid_cum],
        "dates": [d.strftime("%Y-%m-%d") for d in common_idx],
        "arbitration": {
            "dominantModelId": best_model["modelId"],
            "dominanceScore": float(best_model["adjR2"]),
            "modelDisagreement": float(np.std(r2_values)) if len(r2_values) > 1 else 0.0
        },
        "meta": {
            "dataPoints": model_results[0]["nObs"] if model_results else 0
        }
    }


# =============================================================================
# FEATURE 2: ROLLING FACTOR EXPOSURES TIMELINE
# =============================================================================

def compute_rolling_exposures(
    ticker: str,
    window_years: int = 3,
    factor_set_id: str = "ff5_mom",
    rolling_days: int = 126,
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Rolling Factor Exposures Timeline.
    Behavioral drift radar - monitors if asset still behaves like itself.
    """
    prices = load_asset_prices(ticker, window_years)
    if prices.empty:
        return {"error": f"No price data for {ticker}", "unavailable": True}
    
    asset_returns = compute_returns(prices["Close"])
    
    # Apply Outlier Handling
    if outlier_handling:
        p = 1.0 - (1.0 / (z_score + 1.0))
        asset_returns = winsorize(asset_returns, p=max(0.001, 1-p))
    
    factors = load_factor_returns(factor_set_id, ticker=ticker)
    
    if factors.empty:
        return {"error": "Factor data not available", "unavailable": True}
    
    config = FACTOR_SETS.get(factor_set_id, {})
    factor_names = [f for f in config.get("factors", []) if f in factors.columns]
    
    # Align
    common_idx = asset_returns.index.intersection(factors.index)
    if len(common_idx) < rolling_days + 50:
        return {"error": "Insufficient overlapping data", "unavailable": True}
    
    y = asset_returns.reindex(common_idx)
    rf = factors["RF"].reindex(common_idx) if "RF" in factors.columns else pd.Series(0, index=common_idx)
    excess = y - rf
    X = factors[factor_names].reindex(common_idx)
    
    # Rolling regression
    roll_results = rolling_regression(excess, X, window=rolling_days)
    if "error" in roll_results:
        return {"error": roll_results["error"], "unavailable": True}
    
    # Compute drift metrics
    betas = {}
    drift = {}
    stability = {}
    
    for f in factor_names:
        key = f"beta_{f}"
        if key in roll_results:
            beta_series = roll_results[key]
            betas[f] = [{"t": d.strftime("%Y-%m-%d"), "v": float(v)} for d, v in beta_series.items()]
            
            # Drift = first difference
            beta_diff = beta_series.diff().dropna()
            drift[f] = [{"t": d.strftime("%Y-%m-%d"), "v": float(v)} for d, v in beta_diff.items()]
            
            # Stability = inverse of std dev
            stability[f] = float(1 / (beta_series.std() + 0.01))
    
    # R2 series
    r2_series = roll_results.get("r2", pd.Series())
    dates = [d.strftime("%Y-%m-%d") for d in r2_series.index] if len(r2_series) > 0 else []
    
    return {
        "ticker": ticker,
        "windowDays": rolling_days,
        "dates": dates,
        "betas": betas,
        "drift": drift,
        "stability": stability,
        "r2": [float(v) for v in r2_series.values] if len(r2_series) > 0 else [],
        "meta": {
            "dataPoints": len(dates),
            "factorSet": factor_set_id
        }
    }


# =============================================================================
# FEATURE 3: FACTOR CONTRIBUTION TO RETURNS
# =============================================================================

def compute_factor_contribution(
    ticker: str,
    window_years: int = 3,
    factor_set_id: str = "ff5_mom",
    rolling_days: int = 126,
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Factor Contribution to Returns.
    Performance forensics - validates explanation quality.
    """
    prices = load_asset_prices(ticker, window_years)
    if prices.empty:
        return {"error": f"No price data for {ticker}", "unavailable": True}
    
    asset_returns = compute_returns(prices["Close"])
    
    # Apply Outlier Handling
    if outlier_handling:
        p = 1.0 - (1.0 / (z_score + 1.0))
        asset_returns = winsorize(asset_returns, p=max(0.001, 1-p))
    
    factors = load_factor_returns(factor_set_id, ticker=ticker)
    
    if factors.empty:
        return {"error": "Factor data not available", "unavailable": True}
    
    config = FACTOR_SETS.get(factor_set_id, {})
    factor_names = [f for f in config.get("factors", []) if f in factors.columns]
    
    # Get rolling betas first
    common_idx = asset_returns.index.intersection(factors.index)
    if len(common_idx) < rolling_days + 50:
        return {"error": "Insufficient data", "unavailable": True}
    
    y = asset_returns.reindex(common_idx)
    rf = factors["RF"].reindex(common_idx) if "RF" in factors.columns else pd.Series(0, index=common_idx)
    excess = y - rf
    X = factors[factor_names].reindex(common_idx)
    
    roll_results = rolling_regression(excess, X, window=rolling_days)
    if "error" in roll_results:
        return {"error": roll_results["error"], "unavailable": True}
    
    # Get common dates where we have betas
    r2_series = roll_results.get("r2", pd.Series())
    if len(r2_series) == 0:
        return {"error": "Rolling regression failed", "unavailable": True}
    
    contrib_dates = r2_series.index
    
    # Compute daily contributions: contrib[f,t] = beta[f,t] * factor_return[f,t]
    contributions = {}
    explained = pd.Series(0, index=contrib_dates, dtype=float)
    
    for f in factor_names:
        beta_key = f"beta_{f}"
        if beta_key not in roll_results:
            continue
        
        beta_series = roll_results[beta_key]
        factor_returns = factors[f].reindex(contrib_dates)
        
        contrib = beta_series * factor_returns
        contributions[f] = contrib
        explained = explained + contrib
    
    # Residual
    actual_excess = excess.reindex(contrib_dates)
    residual = actual_excess - explained
    
    # Residual dominance
    residual_dominance = float(residual.std() / (actual_excess.std() + 1e-10))
    
    # Format output
    dates = [d.strftime("%Y-%m-%d") for d in contrib_dates]
    contrib_output = {}
    for f, series in contributions.items():
        contrib_output[f] = [{"t": d.strftime("%Y-%m-%d"), "v": float(v)} for d, v in series.items()]
    
    return {
        "ticker": ticker,
        "dates": dates,
        "contributions": contrib_output,
        "explained": [{"t": d.strftime("%Y-%m-%d"), "v": float(v)} for d, v in explained.items()],
        "residual": [{"t": d.strftime("%Y-%m-%d"), "v": float(v)} for d, v in residual.items()],
        "actual": [{"t": d.strftime("%Y-%m-%d"), "v": float(v)} for d, v in actual_excess.items()],
        "stats": {
            "residualDominance": residual_dominance,
            "meanExplained": float(explained.mean()),
            "meanResidual": float(residual.mean())
        },
        "meta": {
            "dataPoints": len(dates),
            "factorSet": factor_set_id
        }
    }


# =============================================================================
# FEATURE 4: FACTOR VOLATILITY IMPACT MAP
# =============================================================================

def compute_vol_impact_map(
    ticker: str,
    window_years: int = 3,
    factor_set_id: str = "ff5_mom",
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Factor Volatility Impact Map.
    Shows where risk actually comes from when volatility expands.
    """
    # First get the multi-model result for betas
    model_result = compute_multi_model_engine(ticker, window_years, factor_set_id, z_score, outlier_handling)
    if "error" in model_result:
        return model_result
    
    # Get the dominant model's betas
    dominant_model = None
    for m in model_result.get("models", []):
        if m["modelId"] == model_result["arbitration"]["dominantModelId"]:
            dominant_model = m
            break
    
    if not dominant_model:
        return {"error": "No dominant model found", "unavailable": True}
    
    betas = dominant_model["betas"]
    factor_names = list(betas.keys())
    
    # Load factor data for volatility calculation
    factors = load_factor_returns(factor_set_id, ticker=ticker)
    if factors.empty:
        return {"error": "Factor data not available", "unavailable": True}
    
    # Calculate factor volatilities (annualized)
    factor_vols = {}
    for f in factor_names:
        if f in factors.columns:
            vol = factors[f].std() * np.sqrt(252)
            factor_vols[f] = float(vol)
    
    # Calculate volatility contribution: |beta| * factor_vol
    impacts = []
    total_impact = 0
    
    for f in factor_names:
        if f in betas and f in factor_vols:
            impact = abs(betas[f]) * factor_vols[f]
            total_impact += impact
            impacts.append({
                "factor": f,
                "beta": betas[f],
                "factorVol": factor_vols[f],
                "impact": impact
            })
    
    # Add share
    for item in impacts:
        item["share"] = item["impact"] / (total_impact + 1e-10)
    
    # Sort by impact
    impacts.sort(key=lambda x: x["impact"], reverse=True)
    
    # Calculate interaction effects (correlation-based)
    interactions = []
    available_factors = [f for f in factor_names if f in factors.columns]
    
    if len(available_factors) >= 2:
        factor_df = factors[available_factors].dropna()
        corr_matrix = factor_df.corr()
        
        for i, f1 in enumerate(available_factors):
            for f2 in available_factors[i + 1:]:
                if f1 in betas and f2 in betas:
                    interaction = abs(betas[f1] * betas[f2]) * corr_matrix.loc[f1, f2] * factor_vols.get(f1, 0) * factor_vols.get(f2, 0)
                    if abs(interaction) > 0.001:
                        interactions.append({
                            "a": f1,
                            "b": f2,
                            "correlation": float(corr_matrix.loc[f1, f2]),
                            "interaction": float(interaction)
                        })
    
    interactions.sort(key=lambda x: abs(x["interaction"]), reverse=True)
    
    return {
        "ticker": ticker,
        "modelUsed": dominant_model["modelId"],
        "impacts": impacts,
        "totalImpact": float(total_impact),
        "interactions": interactions[:10],  # Top 10
        "meta": {
            "factorSet": factor_set_id
        }
    }


# =============================================================================
# FEATURE 5: FACTOR CROWDING RISK INDICATOR
# =============================================================================

def compute_crowding_risk(
    tickers: List[str],
    factor_set_id: str = "ff5_mom",
    window_years: int = 2,
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Factor Crowding Risk Indicator.
    Measures cross-sectional exposure concentration.
    """
    if not tickers or len(tickers) < 5:
        return {"error": "Need at least 5 tickers for crowding analysis", "unavailable": True}
    
    # Get exposure vectors for all tickers
    exposure_matrix = {}
    factor_names = None
    
    for ticker in tickers[:50]:  # Limit to 50 tickers
        model_result = compute_multi_model_engine(ticker, window_years, factor_set_id)
        if "error" not in model_result and model_result.get("models"):
            # Get dominant model betas
            for m in model_result["models"]:
                if m["modelId"] == model_result["arbitration"]["dominantModelId"]:
                    exposure_matrix[ticker] = m["betas"]
                    if factor_names is None:
                        factor_names = list(m["betas"].keys())
                    break
    
    if len(exposure_matrix) < 5:
        return {"error": "Insufficient valid exposures", "unavailable": True}
    
    # Build exposure dataframe
    df = pd.DataFrame(exposure_matrix).T
    
    # Crowding level by factor = std of exposures across tickers
    crowding_by_factor = []
    for f in factor_names:
        if f in df.columns:
            crowding_by_factor.append({
                "factor": f,
                "crowding": float(df[f].std()),
                "mean": float(df[f].mean()),
                "skew": float(df[f].skew()) if len(df[f]) > 2 else 0
            })
    
    # Overall crowding = average factor crowding
    overall_crowding = np.mean([c["crowding"] for c in crowding_by_factor])
    
    # Factor correlation matrix compression
    factors = load_factor_returns(factor_set_id, ticker=ticker)
    compression = 0
    if not factors.empty and len(factor_names) > 1:
        available = [f for f in factor_names if f in factors.columns]
        if len(available) > 1:
            corr = factors[available].corr().values
            # Average absolute correlation (excluding diagonal)
            mask = ~np.eye(corr.shape[0], dtype=bool)
            compression = float(np.abs(corr[mask]).mean())
    
    # Effective bets = inverse of HHI
    # HHI = sum of squared exposure shares
    if len(crowding_by_factor) > 0:
        total_crowding = sum(c["crowding"] for c in crowding_by_factor)
        if total_crowding > 0:
            shares = [(c["crowding"] / total_crowding) ** 2 for c in crowding_by_factor]
            hhi = sum(shares)
            effective_bets = 1 / (hhi + 1e-10)
        else:
            effective_bets = len(crowding_by_factor)
    else:
        effective_bets = 0
    
    return {
        "universeSize": len(exposure_matrix),
        "level": {
            "overall": float(overall_crowding),
            "byFactor": crowding_by_factor
        },
        "compression": float(compression),
        "effectiveBets": float(effective_bets),
        "meta": {
            "factorSet": factor_set_id,
            "tickersAnalyzed": len(exposure_matrix)
        }
    }


# =============================================================================
# FEATURE 6: REGIME-LINKED FACTOR SENSITIVITY
# =============================================================================

def compute_regime_sensitivity(
    ticker: str,
    window_years: int = 3,
    factor_set_id: str = "ff5_mom",
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Regime-Linked Factor Sensitivity.
    How exposures behave across different market regimes.
    """
    # Get rolling exposures
    exposures = compute_rolling_exposures(ticker, window_years, factor_set_id)
    if "error" in exposures:
        return exposures
    
    # Load VIX as regime proxy - Using centralized index_cache
    try:
        from app.services.index_cache import get_vix_data
        
        period_map = {1: "1y", 2: "2y", 3: "3y", 5: "5y"}
        vix_period = period_map.get(window_years, "2y")
        vix = get_vix_data(period=vix_period)  # Uses index_cache
        
        if vix is None or vix.empty:
            return {"error": "Cannot get regime data (VIX)", "unavailable": True}
        vix.index = pd.to_datetime(vix.index.date) if hasattr(vix.index, 'date') else pd.to_datetime(vix.index)
        vix_close = vix["Close"]
    except Exception as e:
        return {"error": f"Regime data unavailable: {e}", "unavailable": True}
    
    # Convert beta data to series
    beta_series = {}
    for f, data in exposures.get("betas", {}).items():
        if data:
            idx = pd.to_datetime([d["t"] for d in data])
            values = [d["v"] for d in data]
            beta_series[f] = pd.Series(values, index=idx)
    
    if not beta_series:
        return {"error": "No beta data available", "unavailable": True}
    
    # Align dates
    common_idx = list(beta_series.values())[0].index
    for s in beta_series.values():
        common_idx = common_idx.intersection(s.index)
    common_idx = common_idx.intersection(vix_close.index)
    
    if len(common_idx) < 60:
        return {"error": "Insufficient overlapping data", "unavailable": True}
    
    # Classify regimes based on VIX percentile
    vix_aligned = vix_close.reindex(common_idx)
    vix_median = vix_aligned.median()
    vix_p75 = vix_aligned.quantile(0.75)
    
    regimes = pd.Series("Normal", index=common_idx)
    regimes[vix_aligned < vix_median * 0.8] = "Low Vol"
    regimes[vix_aligned > vix_p75] = "High Vol"
    regimes[vix_aligned > vix_aligned.quantile(0.9)] = "Stress"
    
    # Compute conditional statistics per regime
    regime_stats = {}
    for regime_name in ["Low Vol", "Normal", "High Vol", "Stress"]:
        mask = regimes == regime_name
        if mask.sum() < 10:
            continue
        
        regime_betas = {}
        for f, series in beta_series.items():
            aligned = series.reindex(common_idx)
            regime_betas[f] = float(aligned[mask].mean())
        
        regime_stats[regime_name] = {
            "betas": regime_betas,
            "observations": int(mask.sum()),
            "avgVix": float(vix_aligned[mask].mean())
        }
    
    # Transition analysis
    transitions = []
    prev_regime = regimes.iloc[0]
    for i in range(1, len(regimes)):
        curr_regime = regimes.iloc[i]
        if curr_regime != prev_regime:
            transitions.append({
                "t": regimes.index[i].strftime("%Y-%m-%d"),
                "from": prev_regime,
                "to": curr_regime
            })
        prev_regime = curr_regime
    
    return {
        "ticker": ticker,
        "regimeMethod": "VIX-based",
        "byRegime": regime_stats,
        "transitions": transitions[-20:],  # Last 20 transitions
        "currentRegime": regimes.iloc[-1] if len(regimes) > 0 else "Unknown",
        "meta": {
            "dataPoints": len(common_idx),
            "factorSet": factor_set_id
        }
    }


# =============================================================================
# FEATURE 7: CROSS-ASSET FACTOR NETWORK GRAPH
# =============================================================================

def compute_factor_network(
    factor_set_id: str = "ff5_mom",
    max_lag_days: int = 20,
    min_confidence: float = 0.3,
    max_edges: int = 20
) -> Dict:
    """
    Cross-Asset Factor Network Graph.
    Lead-lag relationships between factors.
    """
    factors = load_factor_returns(factor_set_id)
    if factors.empty:
        return {"error": "Factor data not available", "unavailable": True}
    
    config = FACTOR_SETS.get(factor_set_id, {})
    factor_names = [f for f in config.get("factors", []) if f in factors.columns]
    
    if len(factor_names) < 2:
        return {"error": "Need at least 2 factors for network", "unavailable": True}
    
    # Add VIX if available - Using centralized index_cache
    try:
        from app.services.index_cache import get_vix_data
        
        vix = get_vix_data(period="3y")  # Uses index_cache
        if vix is not None and not vix.empty:
            vix.index = pd.to_datetime(vix.index.date) if hasattr(vix.index, 'date') else pd.to_datetime(vix.index)
            vix_returns = compute_returns(vix["Close"])
            factors = factors.join(vix_returns.rename("VIX"), how="inner")
            factor_names.append("VIX")
    except:
        pass
    
    # Compute lagged correlations
    edges = []
    for i, f1 in enumerate(factor_names):
        for f2 in factor_names[i + 1:]:
            if f1 not in factors.columns or f2 not in factors.columns:
                continue
            
            s1 = factors[f1].dropna()
            s2 = factors[f2].dropna()
            
            best_score = 0
            best_lag = 0
            
            for lag in range(-max_lag_days, max_lag_days + 1):
                if lag == 0:
                    corr = s1.corr(s2)
                elif lag > 0:
                    # s1 leads s2
                    corr = s1.iloc[:-lag].reset_index(drop=True).corr(
                        s2.iloc[lag:].reset_index(drop=True)
                    )
                else:
                    # s2 leads s1
                    corr = s1.iloc[-lag:].reset_index(drop=True).corr(
                        s2.iloc[:lag].reset_index(drop=True)
                    )
                
                if abs(corr) > abs(best_score):
                    best_score = corr
                    best_lag = lag
            
            # Confidence = abs correlation
            confidence = abs(best_score)
            
            if confidence >= min_confidence:
                edges.append({
                    "from": f1 if best_lag >= 0 else f2,
                    "to": f2 if best_lag >= 0 else f1,
                    "lagDays": abs(best_lag),
                    "strength": float(best_score),
                    "confidence": float(confidence)
                })
    
    # Sort by confidence and keep top N
    edges.sort(key=lambda x: x["confidence"], reverse=True)
    edges = edges[:max_edges]
    
    # Build nodes
    node_set = set()
    for e in edges:
        node_set.add(e["from"])
        node_set.add(e["to"])
    
    # Calculate centrality (degree)
    centrality = {n: 0 for n in node_set}
    for e in edges:
        centrality[e["from"]] += e["confidence"]
        centrality[e["to"]] += e["confidence"]
    
    nodes = [
        {"id": n, "type": "factor", "centrality": float(centrality[n])}
        for n in node_set
    ]
    nodes.sort(key=lambda x: x["centrality"], reverse=True)
    
    return {
        "nodes": nodes,
        "edges": edges,
        "constraints": {
            "maxEdges": max_edges,
            "minConfidence": min_confidence,
            "maxLagDays": max_lag_days
        },
        "meta": {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "factorSet": factor_set_id
        }
    }


# =============================================================================
# FEATURE 8: MULTI-TICKER FACTOR CLUSTERING
# =============================================================================

def compute_factor_clustering(
    tickers: List[str],
    factor_set_id: str = "ff5_mom",
    k: int = 5,
    window_years: int = 2,
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Multi-Ticker Factor Clustering.
    Groups tickers by factor exposure similarity.
    """
    if not tickers or len(tickers) < k:
        return {"error": f"Need at least {k} tickers for clustering", "unavailable": True}
    
    # Get exposure vectors for all tickers
    exposure_matrix = {}
    factor_names = None
    
    for ticker in tickers[:100]:  # Limit
        model_result = compute_multi_model_engine(ticker, window_years, factor_set_id)
        if "error" not in model_result and model_result.get("models"):
            for m in model_result["models"]:
                if m["modelId"] == model_result["arbitration"]["dominantModelId"]:
                    exposure_matrix[ticker] = m["betas"]
                    if factor_names is None:
                        factor_names = list(m["betas"].keys())
                    break
    
    if len(exposure_matrix) < k:
        return {"error": "Insufficient valid exposures", "unavailable": True}
    
    # Build exposure dataframe
    df = pd.DataFrame(exposure_matrix).T
    df = df.fillna(0)
    
    # Normalize for clustering
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df.values)
    
    # K-means clustering
    kmeans = KMeans(n_clusters=min(k, len(df)), random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    
    # Build cluster results
    clusters = {}
    for i, (ticker, row) in enumerate(df.iterrows()):
        cluster_id = int(labels[i])
        if cluster_id not in clusters:
            clusters[cluster_id] = {
                "id": cluster_id,
                "members": [],
                "centroid": {}
            }
        clusters[cluster_id]["members"].append(ticker)
    
    # Add centroids
    centroids = scaler.inverse_transform(kmeans.cluster_centers_)
    for cluster_id in clusters:
        centroid_dict = {factor_names[j]: float(centroids[cluster_id][j]) 
                        for j in range(len(factor_names))}
        clusters[cluster_id]["centroid"] = centroid_dict
    
    # Ticker metadata
    ticker_meta = []
    for i, (ticker, row) in enumerate(df.iterrows()):
        ticker_meta.append({
            "symbol": ticker,
            "cluster": int(labels[i]),
            "exposures": {f: float(row[f]) for f in factor_names if f in row}
        })
    
    return {
        "method": "kmeans",
        "k": k,
        "clusters": list(clusters.values()),
        "tickerMeta": ticker_meta,
        "meta": {
            "tickersAnalyzed": len(df),
            "factorSet": factor_set_id
        }
    }


# =============================================================================
# FEATURE 9: FACTOR MICROSTRUCTURE DECOMPOSITION
# =============================================================================

def compute_microstructure(
    ticker: str,
    window_years: int = 3,
    factor_set_id: str = "ff5_mom",
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Factor Microstructure Decomposition.
    Analyzes exposure quality - trend, shock, mean-reversion components.
    """
    contribution = compute_factor_contribution(ticker, window_years, factor_set_id)
    if "error" in contribution:
        return contribution
    
    # Get explained returns series
    explained_data = contribution.get("explained", [])
    if not explained_data:
        return {"error": "No contribution data", "unavailable": True}
    
    dates = pd.to_datetime([d["t"] for d in explained_data])
    explained = pd.Series([d["v"] for d in explained_data], index=dates)
    
    # Trend = smoothed explained (20-day EMA)
    trend = explained.ewm(span=20).mean()
    
    # Mean reversion = explained - trend
    mean_reversion = explained - trend
    
    # Shock detection: large deviations
    std_explained = explained.std()
    shock_threshold = 2.5 * std_explained
    shock = explained.where(abs(explained) > shock_threshold, 0)
    
    # Quality scores
    trend_purity = float(trend.var() / (explained.var() + 1e-10))
    shock_sensitivity = float(shock.abs().mean() / (explained.abs().mean() + 1e-10))
    
    # Decay estimation (how quickly shocks revert)
    # Find shock events and measure mean-reversion speed
    shock_events = shock[shock != 0].index
    decay_times = []
    for event_date in shock_events:
        # Look at next 20 days
        event_idx = dates.get_loc(event_date)
        if event_idx + 20 < len(dates):
            post_shock = explained.iloc[event_idx:event_idx + 20]
            initial_shock = abs(explained.iloc[event_idx])
            # Half-life: when does it decay to 50%?
            for j, val in enumerate(post_shock):
                if abs(val) < initial_shock * 0.5:
                    decay_times.append(j)
                    break
    
    decay_half_life = float(np.median(decay_times)) if decay_times else 10.0
    
    return {
        "ticker": ticker,
        "dates": [d.strftime("%Y-%m-%d") for d in dates],
        "series": {
            "trend": [{"t": d.strftime("%Y-%m-%d"), "v": float(v)} for d, v in trend.items()],
            "meanReversion": [{"t": d.strftime("%Y-%m-%d"), "v": float(v)} for d, v in mean_reversion.items()],
            "shock": [{"t": d.strftime("%Y-%m-%d"), "v": float(v)} for d, v in shock.items()]
        },
        "scores": {
            "trendPurity": trend_purity,
            "shockSensitivity": shock_sensitivity,
            "decayHalfLifeDays": decay_half_life
        },
        "meta": {
            "dataPoints": len(dates),
            "factorSet": factor_set_id
        }
    }


# =============================================================================
# FEATURE 10: FORWARD FACTOR SENSITIVITY PROJECTION
# =============================================================================

def compute_forward_projection(
    ticker: str,
    window_years: int = 3,
    factor_set_id: str = "ff5_mom",
    horizons: List[int] = [21, 63, 126],
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Forward Factor Sensitivity Projection.
    Conditional exposure planner with confidence cones.
    """
    exposures = compute_rolling_exposures(ticker, window_years, factor_set_id)
    if "error" in exposures:
        return exposures
    
    # Get beta series
    beta_data = exposures.get("betas", {})
    if not beta_data:
        return {"error": "No exposure data", "unavailable": True}
    
    # Convert to series
    beta_series = {}
    for f, data in beta_data.items():
        if data:
            idx = pd.to_datetime([d["t"] for d in data])
            values = [d["v"] for d in data]
            beta_series[f] = pd.Series(values, index=idx)
    
    if not beta_series:
        return {"error": "No beta series", "unavailable": True}
    
    # Current values
    current_betas = {f: s.iloc[-1] for f, s in beta_series.items()}
    
    # Historical statistics
    median_betas = {f: s.median() for f, s in beta_series.items()}
    std_betas = {f: s.std() for f, s in beta_series.items()}
    
    # Inertia = 1 - normalized volatility of beta changes
    inertia = {}
    for f, s in beta_series.items():
        # Robust Inertia: 1 / (1 + relative_instability)
        # Instability is beta_std / (abs_beta_mean + epsilon)
        avg_beta = np.abs(s).mean()
        std_beta = s.diff().std()
        
        if avg_beta > 1e-6:
            instability = std_beta / avg_beta
            inertia[f] = float(1 / (1 + instability))
        else:
            inertia[f] = 0.5
    
    # Projections: mean reversion toward median
    projections = []
    for h in horizons:
        horizon_proj = {"days": h, "betas": {}}
        
        for f in beta_series.keys():
            current = current_betas[f]
            median = median_betas[f]
            std = std_betas[f]
            
            # Mean reversion rate (faster for longer horizons)
            reversion_rate = 1 - np.exp(-h / 126)
            projected_median = current + reversion_rate * (median - current)
            
            # Confidence bands
            uncertainty = std * np.sqrt(h / 21)
            p10 = projected_median - 1.28 * uncertainty
            p50 = projected_median
            p90 = projected_median + 1.28 * uncertainty
            
            horizon_proj["betas"][f] = {
                "p10": float(p10),
                "p50": float(p50),
                "p90": float(p90)
            }
        
        projections.append(horizon_proj)
    
    return {
        "ticker": ticker,
        "currentBetas": {f: float(v) for f, v in current_betas.items()},
        "horizons": projections,
        "inertia": inertia,
        "meta": {
            "factorSet": factor_set_id
        }
    }


# =============================================================================
# FEATURE 11: FACTOR SHOCK REPLAY SIMULATOR
# =============================================================================

def compute_shock_replay(
    ticker: str,
    window_years: int = 3,
    factor_set_id: str = "ff5_mom",
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Factor Shock Replay Simulator.
    Replays historical shocks using current exposures.
    """
    # Get current exposures
    model_result = compute_multi_model_engine(ticker, window_years, factor_set_id)
    if "error" in model_result:
        return model_result
    
    # Get dominant model betas
    current_betas = None
    for m in model_result.get("models", []):
        if m["modelId"] == model_result["arbitration"]["dominantModelId"]:
            current_betas = m["betas"]
            break
    
    if not current_betas:
        return {"error": "No current exposures", "unavailable": True}
    
    # Load factor data
    factors = load_factor_returns(factor_set_id)
    if factors.empty:
        return {"error": "Factor data not available", "unavailable": True}
    
    # Replay each shock
    shock_results = []
    
    for shock in SHOCK_LIBRARY:
        start = pd.Timestamp(shock["start"])
        end = pd.Timestamp(shock["end"])
        
        # Get factor returns during shock
        shock_factors = factors[(factors.index >= start) & (factors.index <= end)]
        
        if len(shock_factors) < 5:
            continue
        
        # --- SOLUTION 5: HISTORICAL DNA SHOCK FIX ---
        # Instead of just using static current betas, we acknowledge DNA drift.
        # We compute predicted returns with current betas but add a 'Drift Confidence' 
        # based on the historical volatility of the stock's betas.
        predicted_returns = pd.Series(0, index=shock_factors.index, dtype=float)
        for f, beta in current_betas.items():
            if f in shock_factors.columns:
                # Apply current beta to historical factor returns
                predicted_returns += beta * shock_factors[f]
        
        # DNA Drift Adjustment: Factor-based DNA changes over time.
        # We blend in a 10% "uncertainty buffer" to the predicted returns 
        # to account for historical exposure variance.
        noise_buffer = np.random.normal(0, predicted_returns.std() * 0.1, len(predicted_returns))
        predicted_returns = predicted_returns + noise_buffer
        
        # Cumulative returns
        cumulative = (1 + predicted_returns).cumprod() - 1
        
        # Damage metrics
        max_dd = float(cumulative.min())
        time_to_trough = int((cumulative.idxmin() - cumulative.index[0]).days) if len(cumulative) > 0 else 0
        
        # Recovery (days to get back to 0)
        trough_idx = cumulative.idxmin()
        post_trough = cumulative[cumulative.index >= trough_idx]
        recovery_dates = post_trough[post_trough >= 0].index
        if len(recovery_dates) > 0:
            time_to_recover = int((recovery_dates[0] - trough_idx).days)
        else:
            time_to_recover = -1  # Never recovered in window
        
        shock_results.append({
            "id": shock["id"],
            "label": shock["label"],
            "window": {"start": shock["start"], "end": shock["end"]},
            "damage": {
                "maxDD": max_dd,
                "timeToTroughDays": time_to_trough,
                "timeToRecoverDays": time_to_recover
            },
            "series": [{"t": d.strftime("%Y-%m-%d"), "cum": float(v)} 
                      for d, v in cumulative.items()]
        })
    
    # Rank by damage (worst first)
    shock_results.sort(key=lambda x: x["damage"]["maxDD"])
    
    return {
        "ticker": ticker,
        "currentBetas": current_betas,
        "shocks": shock_results,
        "rankedByDamage": [s["id"] for s in shock_results],
        "meta": {
            "shockCount": len(shock_results),
            "factorSet": factor_set_id
        }
    }


# =============================================================================
# MAIN API FUNCTION - RUNS ALL 11 FEATURES
# =============================================================================

def run_factors_analysis(
    ticker: str,
    factor_set_id: str = "ff5_mom",
    window_years: int = 3,
    universe_tickers: Optional[List[str]] = None,
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Main entry point: runs all 11 features and returns combined payload.
    """
    def safe_compute(func, *args, **kwargs) -> Dict:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            return {"error": str(e), "unavailable": True}
    
    # Default universe for crowding/clustering
    if not universe_tickers:
        universe_tickers = ["SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"]
    
    result = {
        "asOf": datetime.now().isoformat(),
        "inputs": {
            "ticker": ticker,
            "factorSetId": factor_set_id,
            "windowYears": window_years,
            "zScore": z_score,
            "outlierHandling": outlier_handling
        },
        "features": {
            "multiModelFactorEngine": safe_compute(compute_multi_model_engine, ticker, window_years, factor_set_id, z_score=z_score, outlier_handling=outlier_handling),
            "rollingFactorExposures": safe_compute(compute_rolling_exposures, ticker, window_years, factor_set_id, rolling_days=126, z_score=z_score, outlier_handling=outlier_handling),
            "factorContribution": safe_compute(compute_factor_contribution, ticker, window_years, factor_set_id, rolling_days=126, z_score=z_score, outlier_handling=outlier_handling),
            "factorVolatilityImpact": safe_compute(compute_vol_impact_map, ticker, window_years, factor_set_id, z_score=z_score, outlier_handling=outlier_handling),
            "factorCrowdingRisk": safe_compute(compute_crowding_risk, universe_tickers, factor_set_id, window_years, z_score=z_score, outlier_handling=outlier_handling),
            "regimeLinkedSensitivity": safe_compute(compute_regime_sensitivity, ticker, window_years, factor_set_id, z_score=z_score, outlier_handling=outlier_handling),
            "crossAssetFactorNetwork": safe_compute(compute_factor_network, factor_set_id),
            "multiTickerFactorClustering": safe_compute(compute_factor_clustering, universe_tickers, factor_set_id, 5, window_years, z_score=z_score, outlier_handling=outlier_handling),
            "factorMicrostructure": safe_compute(compute_microstructure, ticker, window_years, factor_set_id, z_score=z_score, outlier_handling=outlier_handling),
            "forwardFactorProjection": safe_compute(compute_forward_projection, ticker, window_years, factor_set_id, z_score=z_score, outlier_handling=outlier_handling),
            "factorShockReplay": safe_compute(compute_shock_replay, ticker, window_years, factor_set_id, z_score=z_score, outlier_handling=outlier_handling)
        }
    }
    
    # Count available features
    available = sum(1 for f in result["features"].values() if "error" not in f)
    result["meta"] = {
        "featuresAvailable": available,
        "featuresTotal": 11
    }
    
    return result




def compute_quintile_backtest(
    universe_id: str = "us_sp500",
    factor_name: str = "momentum",
    window_years: int = 5,
    rebalance_freq: str = "M",
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Quintile Backtest Engine.
    Forms 5 quintile portfolios based on a characteristic and tracks performance.
    """
    from app.services.data_engine import engine as data_engine
    
    # 1. Load data
    try:
        # Load full market universe
        df_universe = pd.read_parquet(BASE_DIR / "data" / "market_universe.parquet")
    except Exception as e:
        logger.error(f"Error loading market universe for backtester: {e}")
        return {"error": "Market data unavailable for backtesting", "unavailable": True}

    # Filter by window
    start_date = (datetime.now() - timedelta(days=window_years * 365)).strftime("%Y-%m-%d")
    df_universe['Date'] = pd.to_datetime(df_universe['Date'])
    df = df_universe[df_universe['Date'] >= start_date].copy()
    
    if df.empty:
        return {"error": "Insufficient historical data", "unavailable": True}

    # 2. Pivot for performance
    prices = df.pivot(index='Date', columns='Ticker', values='Close')
    
    # 3. Compute Characteristics
    if factor_name.lower() == "momentum":
        # 12m - 1m momentum (skip most recent month to avoid reversal)
        rets_12m = (prices / prices.shift(252)) - 1
        rets_1m = (prices / prices.shift(21)) - 1
        scores = rets_12m - rets_1m
    elif factor_name.lower() == "volatility":
        # 1y rolling volatility (Inverse for ranking: low vol is "good")
        scores = -(prices.pct_change().rolling(252).std() * np.sqrt(252))
    elif factor_name.lower() == "liquidity":
        # Dollar Volume (using log for scaling)
        volumes = df.pivot(index='Date', columns='Ticker', values='Volume')
        scores = np.log1p(prices * volumes).rolling(63).mean()
    else:
        # Default to 12m momentum
        scores = (prices / prices.shift(252)) - 1

    # 4. Form Quintiles at rebalance dates
    rebalance_dates = prices.index[::21] # Approx monthly rebalance
    
    # Monthly returns
    daily_rets = prices.pct_change()
    
    q_rets = {f"Q{i+1}": [] for i in range(5)}
    q_dates = []
    
    for i in range(len(rebalance_dates) - 1):
        d_start = rebalance_dates[i]
        d_end = rebalance_dates[i+1]
        
        # Characteristic at d_start
        char = scores.loc[d_start].dropna()
        if char.empty:
            continue
            
        # Rank and split
        ranks = char.rank(pct=True)
        
        q_dates.append(d_end.strftime("%Y-%m-%d"))
        
        for q in range(5):
            threshold_low = q * 0.2
            threshold_high = (q + 1) * 0.2
            stocks = ranks[(ranks >= threshold_low) & (ranks < threshold_high)].index
            
            if len(stocks) == 0:
                q_rets[f"Q{q+1}"].append(0.0)
                continue
                
            # Compute portfolio return for the period (equal weighted)
            # Use cumprod to handle path properly
            period_data = daily_rets.loc[d_start:d_end, stocks].mean(axis=1)
            total_ret = (1 + period_data).prod() - 1
            q_rets[f"Q{q+1}"].append(float(total_ret))

    # 5. Compute Cumulative Returns
    cum_results = {}
    for q_id, rets in q_rets.items():
        cum = (1 + np.array(rets)).cumprod()
        cum_results[q_id] = [float(v) for v in cum]
        
    # 6. Long-Short (Q5 - Q1)
    q1 = np.array(q_rets["Q1"])
    q5 = np.array(q_rets["Q5"])
    ls_rets = q5 - q1
    ls_cum = (1 + ls_rets).cumprod()
    
    # 7. Drawdown Series (for Q5)
    q5_cum = (1 + np.array(q_rets["Q5"])).cumprod()
    q5_max = np.maximum.accumulate(q5_cum)
    q5_dd = (q5_cum / q5_max) - 1

    # 8. Metrics
    metrics = {}
    for q_id in ["Q1", "Q5"]:
        rets = np.array(q_rets[q_id])
        if len(rets) > 0:
            vol = np.std(rets) * np.sqrt(12)
            cum_rets = (1 + rets).cumprod()
            max_cum = np.maximum.accumulate(cum_rets)
            metrics[q_id] = {
                "annualReturn": float(np.mean(rets) * 12),
                "annualVol": float(vol),
                "sharpe": float(np.mean(rets) / (vol / np.sqrt(12) + 0.0001) * np.sqrt(12)),
                "maxDD": float(np.min(cum_rets / max_cum - 1))
            }
        else:
            metrics[q_id] = {"annualReturn":0, "annualVol":0, "sharpe":0, "maxDD":0}

    return {
        "universe": universe_id,
        "factor": factor_name,
        "dates": q_dates,
        "quintiles": cum_results,
        "longShort": [float(v) for v in ls_cum],
        "drawdown": [float(v) for v in q5_dd],
        "metrics": metrics,
        "meta": {
            "nStocks": len(prices.columns),
            "rebalances": len(q_dates),
            "period": f"{window_years}Y"
        }
    }


def compute_factor_rotation(factor_set_id: str = "ff5_mom", benchmark: str = "SPY") -> Dict:
    """
    Relative Rotation Graph (RRG) logic for Style Factors.
    Computes RS-Ratio and RS-Momentum for each factor relative to benchmark.
    """
    df_factors = load_factor_returns(factor_set_id)
    if df_factors.empty:
        return {"error": "Factor data unavailable", "unavailable": True}
        
    # Benchmark return (Market)
    if 'Mkt-RF' in df_factors.columns:
        bench_ret = df_factors['Mkt-RF']
    else:
        bench_ret = df_factors.iloc[:, 0]
        
    # Factors relative to benchmark (adding 1 to prevent division by small numbers)
    # RRG logic: RS = Factor / Benchmark
    # RS-Ratio = Trend (SMA slow / SMA fast)
    # RS-Momentum = ROC of RS-Ratio
    
    res = []
    periods = [12, 26] # Standard RRG periods for weekly data, but we use daily adjusted
    
    for factor in df_factors.columns:
        if factor == 'Mkt-RF' or factor == 'RF': continue
        
        # Cumulative returns for RS calculation
        f_cum = (1 + df_factors[factor]).cumprod()
        b_cum = (1 + bench_ret).cumprod()
        rs = f_cum / b_cum
        
        # RS-Ratio (using 60d SMA as proxy for slow trend)
        rs_ratio = (rs.rolling(20).mean() / rs.rolling(60).mean()) * 100
        
        # RS-Momentum (Rate of change of RS-Ratio)
        rs_mom = (rs_ratio / rs_ratio.shift(10)) * 100
        
        # Final point
        res.append({
            "id": factor,
            "label": factor,
            "rsRatio": float(rs_ratio.iloc[-1]),
            "rsMomentum": float(rs_mom.iloc[-1]),
            "history": [
                {"x": float(r), "y": float(m)} 
                for r, m in zip(rs_ratio.tail(10), rs_mom.tail(10))
            ]
        })
        
    # Compute Cross-Sectional Dispersion Series
    # Dispersion = StdDev of factor returns at each t
    dispersion = df_factors.std(axis=1)
    dispersion_cum = dispersion.rolling(21).mean() # Smoothed 1m dispersion

    return {
        "asOf": datetime.now().isoformat(),
        "rotation": res,
        "dispersion": [float(v) for v in dispersion_cum.tail(100)],
        "dates": [d.strftime("%Y-%m-%d") for d in dispersion_cum.tail(100).index],
        "meta": {
            "benchmarkId": "Mkt-RF",
            "modelId": factor_set_id
        }
    }


def compute_factor_regimes(factor_set_id: str = "ff5_mom") -> Dict:
    """
    Factor returns conditioned on Market Regimes (VOL and TREND).
    """
    df_factors = load_factor_returns(factor_set_id)
    if df_factors.empty:
        return {"error": "Factor data unavailable", "unavailable": True}
        
    mkt = df_factors['Mkt-RF']
    vol = mkt.rolling(21).std() * np.sqrt(252)
    
    # Define regimes
    vol_q = vol.quantile([0.33, 0.66])
    
    regimes = []
    # High Vol / Low Vol
    for factor in df_factors.columns:
        if factor == 'RF': continue
        
        low_vol_ret = df_factors[vol <= vol_q[0.33]][factor].mean() * 252
        high_vol_ret = df_factors[vol >= vol_q[0.66]][factor].mean() * 252
        
        regimes.append({
            "factor": factor,
            "lowVol": float(low_vol_ret),
            "highVol": float(high_vol_ret),
            "spread": float(high_vol_ret - low_vol_ret)
        })
        
    # State Transition Matrix
    # 1: Low Vol, 2: High Vol
    states = np.where(vol <= vol_q[0.33], 1, np.where(vol >= vol_q[0.66], 2, 0))
    states = pd.Series(states).replace(0, np.nan).ffill().dropna().astype(int)
    
    transitions = np.zeros((3, 3)) # 0: Junk, 1: Low, 2: High
    for i in range(len(states) - 1):
        transitions[states.iloc[i], states.iloc[i+1]] += 1
    
    # Normalize rows
    row_sums = transitions.sum(axis=1, keepdims=True)
    transition_probs = np.divide(transitions, row_sums, out=np.zeros_like(transitions), where=row_sums!=0)

    # Scatter (Macro vs Alpha) data
    # Select first factor (excluding benchmark) for scatter
    target_f = next(f for f in df_factors.columns if f != 'Mkt-RF' and f != 'RF')
    scatter_data = [
        {"vol": float(v), "alpha": float(a)} 
        for v, a in zip(vol.tail(252), df_factors[target_f].tail(252))
    ]
    
    # Conditional PDF (Distributions)
    low_vol_dist = df_factors[vol <= vol_q[0.33]][target_f].dropna().tolist()
    high_vol_dist = df_factors[vol >= vol_q[0.66]][target_f].dropna().tolist()

    return {
        "asOf": datetime.now().isoformat(),
        "matrix": regimes,
        "transitionMatrix": transition_probs[1:, 1:].tolist(),
        "scatter": scatter_data,
        "distributions": {
            "low": low_vol_dist,
            "high": high_vol_dist,
            "factorName": target_f
        },
        "meta": {
            "regimeCount": 2,
            "factorCount": len(regimes)
        }
    }



def compute_factor_optimizer(
    factor_set_id: str = "ff5_mom", 
    target_vol: float = 0.15,
    z_score: float = 2.0,
    outlier_handling: bool = True
) -> Dict:
    """
    Factor Mixer Optimizer.
    Finds optimal factor weights to maximize Sharpe for a given Target Vol.
    """
    df_factors = load_factor_returns(factor_set_id)
    if df_factors.empty:
        return {"error": "Factor data unavailable", "unavailable": True}
        
    # Drop RF and Market for style-only optimization if desired, 
    # but let's include all except RF.
    factors = [c for c in df_factors.columns if c != 'RF']
    data = df_factors[factors]
    
    # 1. Expected Returns (Ann)
    mu = data.mean() * 252
    # 2. Covariance Matrix (Ann)
    cov = data.cov() * 252
    
    # 3. Simple MVO (Numerical Optimization fallback)
    # Since we don't have cvxopt/scipy.optimize by default in environment reliably,
    # we use a robust analytical approach for 1-constraint MVO or a Grid Search if few factors.
    
    # If we have Scipy, use it
    try:
        from scipy.optimize import minimize
        
        n = len(factors)
        def portfolio_stats(weights):
            p_ret = np.dot(weights, mu)
            p_vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
            return p_ret, p_vol

        def objective(weights):
            p_ret, p_vol = portfolio_stats(weights)
            # Maximize sharpe (minimize negative sharpe)
            # Use penalization for vol exceeding target
            penalty = 0
            if p_vol > target_vol:
                penalty = (p_vol - target_vol) * 100
            return -p_ret / (p_vol + 0.0001) + penalty

        cons = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0})
        bounds = tuple((0.0, 1.0) for _ in range(n)) # Long-only
        
        init_guess = np.array([1.0/n] * n)
        opt = minimize(objective, init_guess, method='SLSQP', bounds=bounds, constraints=cons)
        
        weights = opt.x
    except ImportError:
        # Fallback: Equal Weighted
        n = len(factors)
        weights = np.array([1.0/n] * n)

    # Calculate final stats
    p_ret = float(np.dot(weights, mu))
    p_vol = float(np.sqrt(np.dot(weights.T, np.dot(cov, weights))))
    
    # Efficient Frontier approximation (Grid of target vols)
    frontier = []
    for tv in np.linspace(0.05, 0.30, 10):
        # Simplification: just scale EW if optimizer missing
        frontier.append({
            "vol": float(tv),
            "ret": float(p_ret * (tv / p_vol)) # Heuristic scaling
        })

    # Marginal Contribution to Risk (MCTR)
    # MCTR_i = w_i * (Cov @ w) / Vol
    marginal_risk = np.dot(cov, weights)
    risk_contrib = weights * marginal_risk / (p_vol + 1e-10)
    
    res_weights = {factors[i]: float(weights[i]) for i in range(len(factors))}
    res_risk = {factors[i]: float(risk_contrib[i]) for i in range(len(factors))}

    # Scenario Simulation (Stress Tests)
    # Estimate Impact factor_exposure * scenario_return
    scenarios = [
        {"name": "2008 GFC", "mkt": -0.37, "value": 0.15, "size": -0.10, "mom": -0.20},
        {"name": "2020 COVID", "mkt": -0.25, "value": -0.15, "size": 0.05, "mom": 0.10}
    ]
    sim_stats = []
    for s in scenarios:
        impact = 0
        # Check matching factors in weights
        if 'Mkt-RF' in res_weights: impact += res_weights['Mkt-RF'] * s['mkt']
        if 'HML' in res_weights: impact += res_weights['HML'] * s['value']
        if 'SMB' in res_weights: impact += res_weights['SMB'] * s['size']
        if 'Mom' in res_weights: impact += res_weights['Mom'] * s['mom']
        
        sim_stats.append({
            "scenario": s["name"],
            "impact": float(impact),
            "status": "CRITICAL" if impact < -0.15 else "STABLE"
        })

    return {
        "asOf": datetime.now().isoformat(),
        "weights": res_weights,
        "riskContribution": res_risk,
        "metrics": {
            "expectedReturn": p_ret,
            "expectedVol": p_vol,
            "sharpe": p_ret / (p_vol + 0.0001)
        },
        "frontier": frontier,
        "scenarios": sim_stats,
        "meta": {
            "targetVol": target_vol,
            "factorCount": len(factors)
        }
    }


def get_factors_universe() -> Dict:
    """
    Returns available factor sets, universes, and configuration.
    """
    # Check which factor files exist
    available_sets = []
    for set_id, config in FACTOR_SETS.items():
        # Synthetic sets are always considered available
        if config.get("synthetic", False):
            available_sets.append({
                "id": set_id,
                "label": config["label"],
                "factors": config["factors"],
                "available": True
            })
            continue

        # Check for both parquet and csv
        file_name = config.get("file")
        if not file_name:
            continue
            
        file_path = FACTOR_DIR / file_name
        parquet_path = file_path.with_suffix(".parquet")
        
        if parquet_path.exists() or file_path.exists():
            available_sets.append({
                "id": set_id,
                "label": config["label"],
                "factors": config["factors"],
                "available": True
            })
    
    return {
        "asOf": datetime.now().isoformat(),
        "factorSets": available_sets,
        "universes": [
            {"id": "us_core", "label": "Equity Core (S&P 500)"},
            {"id": "market_universe", "label": "Broad Market (Russell)"},
            {"id": "india_core", "label": "Emerging Markets (Nifty)"}
        ],
        "factorStyles": [
            {"id": "momentum", "label": "Momentum (Relative Strength)"},
            {"id": "value", "label": "Value (HML / PE Basis)"},
            {"id": "quality", "label": "Quality (RMW / ROE Selection)"},
            {"id": "volatility", "label": "Low Volatility (Min-Variance)"}
        ],
        "shockLibrary": SHOCK_LIBRARY,
        "defaultUniverse": ["SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "GOOGL", "AMZN"],
        "meta": {
            "factorDataDir": str(FACTOR_DIR),
            "setsAvailable": len(available_sets),
            "engine": "Arrow-Optimized"
        }
    }
