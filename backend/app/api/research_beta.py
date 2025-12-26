"""
Research Rolling Beta API
D1: Rolling factor exposure matrix for selected tickers.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import logging

from app.models.research_schemas import (
    RollingBetaRequest,
    RollingBetaDetailRequest,
    make_error_response,
)
from app.services.research_cache import research_cache
from app.services import research_data, research_math
from app.services.universe import validate_symbols

logger = logging.getLogger(__name__)

router = APIRouter()


def compute_rolling_betas(
    ticker_returns: Dict[str, pd.Series],
    factor_returns: pd.DataFrame,
    windows: List[int],
    winsor_p: float = 0.01,
    include_series: bool = False
) -> Dict[str, Any]:
    """
    Compute rolling betas for all ticker/factor/window combinations.
    
    Returns:
        Dict with 'matrix', 'quality', and optionally 'series' keys.
    """
    matrix = {}
    quality = {}
    series = {} if include_series else None
    
    for ticker, returns in ticker_returns.items():
        matrix[ticker] = {}
        quality[ticker] = {}
        if include_series:
            series[ticker] = {}
        
        for factor in factor_returns.columns:
            matrix[ticker][factor] = {}
            quality[ticker][factor] = {}
            if include_series:
                series[ticker][factor] = {}
            
            # Align returns with factor
            combined = pd.DataFrame({
                'y': returns,
                'x': factor_returns[factor]
            }).dropna()
            
            if len(combined) < 20:
                # Insufficient data
                for w in windows:
                    matrix[ticker][factor][str(w)] = None
                    quality[ticker][factor][str(w)] = {"r2": None, "n": 0}
                continue
            
            # Winsorize
            combined['y'] = research_math.winsorize(combined['y'], winsor_p)
            combined['x'] = research_math.winsorize(combined['x'], winsor_p)
            
            for window in windows:
                min_obs = max(15, int(window * 0.8))
                
                if len(combined) < window:
                    matrix[ticker][factor][str(window)] = None
                    quality[ticker][factor][str(window)] = {"r2": None, "n": len(combined)}
                    continue
                
                # Compute rolling betas
                rolling_results = []
                
                for i in range(window - 1, len(combined)):
                    y_window = combined['y'].iloc[i - window + 1:i + 1].values
                    x_window = combined['x'].iloc[i - window + 1:i + 1].values
                    
                    valid_mask = ~(np.isnan(y_window) | np.isnan(x_window))
                    if valid_mask.sum() >= min_obs:
                        beta, alpha, r2 = research_math.ols_single_factor(
                            y_window[valid_mask],
                            x_window[valid_mask]
                        )
                        rolling_results.append({
                            'date': combined.index[i],
                            'beta': beta,
                            'r2': r2,
                            'n': int(valid_mask.sum())
                        })
                
                if rolling_results:
                    # Last beta for matrix
                    last = rolling_results[-1]
                    matrix[ticker][factor][str(window)] = round(last['beta'], 4) if not np.isnan(last['beta']) else None
                    quality[ticker][factor][str(window)] = {
                        "r2": round(last['r2'], 4) if last['r2'] is not None and not np.isnan(last['r2']) else None,
                        "n": last['n']
                    }
                    
                    # Series if requested
                    if include_series:
                        # Downsample to max 300 points
                        if len(rolling_results) > 300:
                            step = len(rolling_results) // 300
                            rolling_results = rolling_results[::step]
                        
                        series[ticker][factor][str(window)] = [
                            {
                                "date": r['date'].strftime('%Y-%m-%d'),
                                "beta": round(r['beta'], 4) if not np.isnan(r['beta']) else None
                            }
                            for r in rolling_results
                        ]
                else:
                    matrix[ticker][factor][str(window)] = None
                    quality[ticker][factor][str(window)] = {"r2": None, "n": 0}
    
    return {
        "matrix": matrix,
        "quality": quality,
        "series": series
    }


@router.post("/rolling_beta")
async def rolling_beta(request: RollingBetaRequest):
    """
    Compute rolling factor betas for selected tickers.
    
    Returns a matrix of latest betas, quality metrics, and optionally time series.
    """
    try:
        # Check compute cache
        payload = request.model_dump()
        cached, cache_hit = research_cache.get_compute(payload)
        if cache_hit and cached is not None:
            cached['meta']['cache_hit'] = True
            return JSONResponse(content=cached)
        
        # Validate factors
        available_factors = research_data.get_available_factors()
        invalid_factors = [f for f in request.factors if f.upper() not in available_factors]
        if invalid_factors:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "INVALID_INPUT",
                    f"Unknown factors: {invalid_factors}",
                    {"available": available_factors}
                )
            )
        
        # Validate symbols using universe
        valid, invalid_symbols = validate_symbols(request.tickers, mode="security")
        if not valid:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "INVALID_SYMBOL",
                    f"Invalid symbols for this module: {invalid_symbols}",
                    {"invalid": invalid_symbols}
                )
            )
        
        # Load factor returns
        max_window = max(request.windows)
        buffer_days = max_window * 3
        total_lookback = request.lookback + buffer_days
        
        factor_returns = research_data.get_factor_returns(
            request.factors,
            total_lookback
        )
        
        if factor_returns.empty:
            return JSONResponse(
                status_code=500,
                content=make_error_response(
                    "DATA_ERROR",
                    "Failed to load factor data",
                    {}
                )
            )
        
        # Load ticker prices and compute returns
        ticker_returns = {}
        failed_tickers = []
        
        for ticker in request.tickers:
            prices = research_data.get_prices_daily(ticker, total_lookback)
            
            if prices.empty or 'close' not in prices.columns:
                failed_tickers.append(ticker)
                continue
            
            returns = research_math.returns_from_close(
                prices['close'],
                request.returns_type.value
            )
            
            if len(returns.dropna()) < max_window:
                failed_tickers.append(ticker)
                continue
            
            ticker_returns[ticker] = returns
        
        if not ticker_returns:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    "No valid ticker data found",
                    {"failed_tickers": failed_tickers}
                )
            )
        
        # Compute rolling betas
        results = compute_rolling_betas(
            ticker_returns,
            factor_returns,
            request.windows,
            request.regression.winsor_p,
            request.include_series
        )
        
        # Build response
        response = {
            "meta": {
                "lookback_days": request.lookback,
                "returns_type": request.returns_type.value,
                "windows": request.windows,
                "factors": list(factor_returns.columns),
                "tickers_requested": len(request.tickers),
                "tickers_computed": len(ticker_returns),
                "failed_tickers": failed_tickers if failed_tickers else None,
                "min_obs_ratio": 0.8,
                **research_cache.make_cache_meta(False)
            },
            "matrix": results["matrix"],
            "quality": results["quality"],
            "series": results["series"]
        }
        
        # Cache result
        research_cache.set_compute(payload, response)
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error in rolling_beta: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=make_error_response(
                "INTERNAL_ERROR",
                str(e),
                {}
            )
        )


@router.post("/rolling_beta_detail")
async def rolling_beta_detail(request: RollingBetaDetailRequest):
    """
    Get detailed rolling beta time series for a single ticker/factor combination.
    """
    try:
        # Load data
        max_window = request.window
        buffer_days = max_window * 3
        total_lookback = request.lookback + buffer_days
        
        # Factor returns
        factor_returns = research_data.get_factor_returns(
            [request.factor],
            total_lookback
        )
        
        if factor_returns.empty:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    f"Failed to load factor {request.factor}",
                    {}
                )
            )
        
        # Ticker prices
        prices = research_data.get_prices_daily(request.ticker, total_lookback)
        
        if prices.empty:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    f"Failed to load data for {request.ticker}",
                    {}
                )
            )
        
        returns = research_math.returns_from_close(prices['close'], "log")
        
        # Align
        factor_col = factor_returns.columns[0]
        combined = pd.DataFrame({
            'y': returns,
            'x': factor_returns[factor_col]
        }).dropna()
        
        if len(combined) < request.window:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    f"Insufficient data: {len(combined)} < {request.window}",
                    {}
                )
            )
        
        # Winsorize
        combined['y'] = research_math.winsorize(combined['y'], 0.01)
        combined['x'] = research_math.winsorize(combined['x'], 0.01)
        
        # Compute rolling
        min_obs = max(15, int(request.window * 0.8))
        series = []
        
        for i in range(request.window - 1, len(combined)):
            y_window = combined['y'].iloc[i - request.window + 1:i + 1].values
            x_window = combined['x'].iloc[i - request.window + 1:i + 1].values
            
            valid_mask = ~(np.isnan(y_window) | np.isnan(x_window))
            if valid_mask.sum() >= min_obs:
                beta, alpha, r2 = research_math.ols_single_factor(
                    y_window[valid_mask],
                    x_window[valid_mask]
                )
                series.append({
                    "date": combined.index[i].strftime('%Y-%m-%d'),
                    "beta": round(beta, 4) if not np.isnan(beta) else None,
                    "r2": round(r2, 4) if not np.isnan(r2) else None
                })
        
        return JSONResponse(content={
            "meta": {
                "ticker": request.ticker,
                "factor": request.factor,
                "window": request.window,
                "lookback": request.lookback,
                **research_cache.make_cache_meta(False)
            },
            "series": series
        })
        
    except Exception as e:
        logger.error(f"Error in rolling_beta_detail: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=make_error_response(
                "INTERNAL_ERROR",
                str(e),
                {}
            )
        )
