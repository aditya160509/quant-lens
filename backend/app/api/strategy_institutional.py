from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import polars as pl
import numpy as np
from app.services.polars_strategy_engine import PolarsStrategyEngine
from app.services.historical_price_service import _load_csv, PRICES_DIR
from datetime import datetime
import os

router = APIRouter()

class MCRequest(BaseModel):
    ticker: str
    paths: int = 10000
    horizon: int = 252

class WealthRequest(BaseModel):
    ticker: str
    monthly_contribution: float = 1000.0
    horizon_years: int = 10

@router.post("/polars/monte_carlo")
async def run_polars_mc(req: MCRequest):
    """Vectorsied Monte Carlo using Polars"""
    try:
        # Load data
        df_pd = _load_csv(req.ticker)
        if df_pd is None or df_pd.empty:
            raise HTTPException(status_code=404, detail=f"Data for {req.ticker} not found")
        
        if df_pd.index.tz is not None:
            df_pd.index = df_pd.index.tz_localize(None)
        
        # Convert to Polars
        df = pl.from_pandas(df_pd.reset_index())
        
        # Calculate daily returns
        returns = df["Close"].log().diff().drop_nulls()
        
        # Run MC
        results = PolarsStrategyEngine.run_monte_carlo(returns, n_paths=req.paths, horizon=req.horizon)
        
        return results
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/polars/prosperity_cone")
async def prosperity_cone(req: WealthRequest):
    """Wealth projection with contribution and MC results"""
    try:
        df_pd = _load_csv(req.ticker)
        if df_pd is None or df_pd.empty:
            raise HTTPException(status_code=404, detail=f"Data for {req.ticker} not found")
        
        if df_pd.index.tz is not None:
            df_pd.index = df_pd.index.tz_localize(None)
            
        df = pl.from_pandas(df_pd.reset_index())
        returns = df["Close"].log().diff().drop_nulls()
        
        # Simulation parameters
        n_paths = 5000
        horizon_days = req.horizon_years * 252
        monthly_cont = req.monthly_contribution
        
        # Vectorized MC
        returns_np = returns.to_numpy()
        indices = np.random.choice(len(returns_np), size=(horizon_days, n_paths))
        sampled_returns = returns_np[indices]
        
        # Wealth calculation with monthly contributions
        # Every 21 bars (approx 1 month), we add the contribution
        wealth_matrix = np.zeros((horizon_days, n_paths))
        current_wealth = np.zeros(n_paths) + 10000  # Initial 10k
        
        for i in range(horizon_days):
            current_wealth = current_wealth * (1 + sampled_returns[i])
            if (i + 1) % 21 == 0:
                current_wealth += monthly_cont
            wealth_matrix[i, :] = current_wealth
            
        final_wealth = wealth_matrix[-1, :]
        
        return {
            "median_wealth": float(np.median(final_wealth)),
            "p5": float(np.percentile(final_wealth, 5)),
            "p95": float(np.percentile(final_wealth, 95)),
            "horizon_years": req.horizon_years,
            "paths": [wealth_matrix[:, i].tolist() for i in range(20)] # Sample
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
