"""
Research Style Map API
D3: Factor style map for cross-sectional factor positioning.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import logging

from app.models.research_schemas import (
    StyleMapRequest,
    make_error_response,
)
from app.services.research_cache import research_cache
from app.services import research_data, research_math
from app.services.universe import validate_symbols

logger = logging.getLogger(__name__)

router = APIRouter()


def compute_factor_exposure(
    returns: pd.Series,
    factor_returns: pd.Series
) -> Optional[float]:
    """
    Compute single-factor exposure (beta) for a ticker.
    
    Args:
        returns: Asset returns
        factor_returns: Factor returns
        
    Returns:
        Beta coefficient or None if insufficient data
    """
    # Align
    combined = pd.DataFrame({
        'y': returns,
        'x': factor_returns
    }).dropna()
    
    if len(combined) < 20:
        return None
    
    beta, alpha, r2 = research_math.ols_single_factor(
        combined['y'].values,
        combined['x'].values
    )
    
    return beta if not np.isnan(beta) else None


def compute_volatility_proxy(returns: pd.Series) -> Optional[float]:
    """
    Compute volatility proxy as annualized standard deviation.
    """
    if len(returns.dropna()) < 20:
        return None
    
    return float(returns.std() * np.sqrt(252))


def compute_quality_proxy(returns: pd.Series) -> Optional[float]:
    """
    Compute quality proxy as risk-adjusted returns (Sharpe-like).
    """
    returns_clean = returns.dropna()
    if len(returns_clean) < 20:
        return None
    
    mean_ret = returns_clean.mean() * 252
    vol = returns_clean.std() * np.sqrt(252)
    
    if vol < 1e-8:
        return None
    
    return float(mean_ret / vol)


@router.post("/style_map")
async def style_map(request: StyleMapRequest):
    """
    Compute factor style map positioning for selected tickers.
    
    Returns x, y, color, size coordinates based on factor exposures.
    """
    try:
        # Check compute cache
        payload = request.model_dump()
        cached, cache_hit = research_cache.get_compute(payload)
        if cache_hit and cached is not None:
            cached['meta']['cache_hit'] = True
            return JSONResponse(content=cached)
        
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
        
        # Determine required factors
        required_factors = set()
        factor_axis_map = {
            'x': request.x,
            'y': request.y,
            'color': request.color,
            'size': request.size
        }
        
        # Check which factors need to be loaded vs computed
        available = research_data.get_available_factors()
        computed_factors = {'VOL', 'VOLATILITY', 'QUALITY'}
        
        for axis, factor in factor_axis_map.items():
            factor_upper = factor.upper()
            if factor_upper not in computed_factors and factor_upper not in available:
                return JSONResponse(
                    status_code=400,
                    content=make_error_response(
                        "INVALID_INPUT",
                        f"Unknown factor for {axis}: {factor}",
                        {"available": available + list(computed_factors)}
                    )
                )
            if factor_upper not in computed_factors:
                required_factors.add(factor_upper)
        
        # Load factor returns
        factor_returns = pd.DataFrame()
        if required_factors:
            factor_returns = research_data.get_factor_returns(
                list(required_factors),
                request.lookback
            )
        
        # Load ticker data and compute exposures
        raw_exposures = {axis: {} for axis in ['x', 'y', 'color', 'size']}
        failed_tickers = []
        
        for ticker in request.tickers:
            prices = research_data.get_prices_daily(ticker, request.lookback)
            
            if prices.empty or 'close' not in prices.columns:
                failed_tickers.append(ticker)
                continue
            
            returns = research_math.returns_from_close(prices['close'], "log")
            
            if len(returns.dropna()) < 20:
                failed_tickers.append(ticker)
                continue
            
            # Compute exposure for each axis
            for axis, factor in factor_axis_map.items():
                factor_upper = factor.upper()
                
                if factor_upper in ('VOL', 'VOLATILITY'):
                    exposure = compute_volatility_proxy(returns)
                elif factor_upper == 'QUALITY':
                    exposure = compute_quality_proxy(returns)
                elif factor_upper in factor_returns.columns:
                    exposure = compute_factor_exposure(
                        returns,
                        factor_returns[factor_upper]
                    )
                else:
                    exposure = None
                
                raw_exposures[axis][ticker] = exposure
        
        if not any(raw_exposures['x'].values()):
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    "No valid exposures computed",
                    {"failed_tickers": failed_tickers}
                )
            )
        
        # Build DataFrame for standardization
        exposure_df = pd.DataFrame(raw_exposures)
        
        # Winsorize
        for col in exposure_df.columns:
            exposure_df[col] = research_math.winsorize(
                exposure_df[col].dropna(),
                request.winsor_p
            )
        
        # Standardize if requested
        if request.standardize == "cross_sectional_z":
            for col in exposure_df.columns:
                series = exposure_df[col].dropna()
                if len(series) > 1:
                    exposure_df[col] = research_math.standardize(series)
        
        # Build points
        points = []
        for ticker in exposure_df.index:
            point = {"ticker": ticker}
            for axis in ['x', 'y', 'color', 'size']:
                val = exposure_df.loc[ticker, axis]
                if pd.notna(val) and not np.isnan(val):
                    point[axis] = round(float(val), 4)
                else:
                    point[axis] = None
            points.append(point)
        
        # Build response
        response = {
            "meta": {
                "lookback_days": request.lookback,
                "x": request.x,
                "y": request.y,
                "color": request.color,
                "size": request.size,
                "standardize": request.standardize,
                "tickers_requested": len(request.tickers),
                "tickers_computed": len(points),
                "failed_tickers": failed_tickers if failed_tickers else None,
                **research_cache.make_cache_meta(False)
            },
            "points": points
        }
        
        # Cache result
        research_cache.set_compute(payload, response)
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error in style_map: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=make_error_response(
                "INTERNAL_ERROR",
                str(e),
                {}
            )
        )
