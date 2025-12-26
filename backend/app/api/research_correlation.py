"""
Research Correlation API
D5: Cross-asset correlation matrix analysis.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from typing import Dict, List, Any
import logging

from app.models.research_schemas import (
    CorrelationMatrixRequest,
    CorrelationPairRequest,
    make_error_response,
)
from app.services.research_cache import research_cache
from app.services import research_data, research_math
from app.services.universe import validate_symbols

logger = logging.getLogger(__name__)

router = APIRouter()


def compute_correlation_matrices(
    returns_df: pd.DataFrame,
    windows: List[int],
    method: str = "pearson"
) -> Dict[str, Any]:
    """
    Compute correlation matrices for multiple windows.
    
    Args:
        returns_df: DataFrame with ticker columns
        windows: List of window sizes
        method: Correlation method
        
    Returns:
        Dict with matrices, delta, and order
    """
    tickers = list(returns_df.columns)
    matrices = {}
    
    max_window = max(windows)
    if len(returns_df) < max_window:
        return {"error": f"Insufficient data: {len(returns_df)} < {max_window}"}
    
    for window in windows:
        # Use last 'window' days
        window_data = returns_df.iloc[-window:]
        
        corr = window_data.corr(method=method)
        
        # Convert to nested dict
        matrices[str(window)] = {}
        for t1 in tickers:
            matrices[str(window)][t1] = {}
            for t2 in tickers:
                val = corr.loc[t1, t2]
                if pd.notna(val) and not np.isnan(val):
                    matrices[str(window)][t1][t2] = round(float(val), 4)
                else:
                    matrices[str(window)][t1][t2] = None
    
    # Compute delta (recent - previous)
    delta = None
    if len(windows) >= 2:
        sorted_windows = sorted(windows)
        recent_window = sorted_windows[0]
        prev_window = sorted_windows[1]
        
        delta = {}
        for t1 in tickers:
            delta[t1] = {}
            for t2 in tickers:
                recent_val = matrices[str(recent_window)][t1][t2]
                prev_val = matrices[str(prev_window)][t1][t2]
                
                if recent_val is not None and prev_val is not None:
                    delta[t1][t2] = round(recent_val - prev_val, 4)
                else:
                    delta[t1][t2] = None
    
    # Compute hierarchical ordering using most recent window
    recent_window = str(min(windows))
    recent_corr = pd.DataFrame(matrices[recent_window])
    recent_corr = recent_corr.astype(float)
    
    # Handle NaNs for clustering
    recent_corr = recent_corr.fillna(0)
    
    try:
        order = research_math.hierarchical_order(recent_corr)
    except Exception as e:
        logger.warning(f"Hierarchical ordering failed: {e}")
        order = tickers
    
    return {
        "matrices": matrices,
        "delta": delta,
        "order": order
    }


@router.post("/correlation_matrix")
async def correlation_matrix(request: CorrelationMatrixRequest):
    """
    Compute correlation matrices for selected tickers across multiple windows.
    
    Returns correlation values, delta between windows, and optimal ordering.
    """
    try:
        # Check compute cache
        payload = request.model_dump()
        cached, cache_hit = research_cache.get_compute(payload)
        if cache_hit and cached is not None:
            cached['meta']['cache_hit'] = True
            return JSONResponse(content=cached)
        
        if len(request.tickers) < 2:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "INVALID_INPUT",
                    "At least 2 tickers required for correlation",
                    {}
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
        
        # Load returns for all tickers
        max_window = max(request.windows)
        buffer_days = max_window * 2
        total_lookback = request.lookback + buffer_days
        
        returns_dict = {}
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
            
            returns_dict[ticker] = returns
        
        if len(returns_dict) < 2:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    "Insufficient valid tickers for correlation",
                    {"failed_tickers": failed_tickers}
                )
            )
        
        # Build aligned returns DataFrame
        returns_df = pd.DataFrame(returns_dict)
        returns_df = returns_df.dropna(how='all')
        
        # Ensure enough overlap
        overlap = returns_df.dropna()
        if len(overlap) < max_window:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    f"Insufficient overlap: {len(overlap)} < {max_window}",
                    {}
                )
            )
        
        # Compute correlations
        results = compute_correlation_matrices(
            returns_df,
            request.windows,
            request.method.value
        )
        
        if "error" in results:
            return JSONResponse(
                status_code=500,
                content=make_error_response(
                    "COMPUTE_ERROR",
                    results["error"],
                    {}
                )
            )
        
        # Build response
        response = {
            "meta": {
                "windows": request.windows,
                "method": request.method.value,
                "lookback_days": request.lookback,
                "tickers_requested": len(request.tickers),
                "tickers_computed": len(returns_dict),
                "failed_tickers": failed_tickers if failed_tickers else None,
                "overlap_days": len(overlap),
                **research_cache.make_cache_meta(False)
            },
            "tickers": list(returns_dict.keys()),
            "matrices": results["matrices"],
            "delta": results["delta"],
            "order": results["order"]
        }
        
        # Cache result
        research_cache.set_compute(payload, response)
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error in correlation_matrix: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=make_error_response(
                "INTERNAL_ERROR",
                str(e),
                {}
            )
        )


@router.post("/correlation_pair")
async def correlation_pair(request: CorrelationPairRequest):
    """
    Get rolling correlation time series for a pair of tickers.
    """
    try:
        # Load returns for both tickers
        buffer_days = request.window * 2
        total_lookback = request.lookback + buffer_days
        
        prices_a = research_data.get_prices_daily(request.a, total_lookback)
        prices_b = research_data.get_prices_daily(request.b, total_lookback)
        
        if prices_a.empty:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    f"Failed to load data for {request.a}",
                    {}
                )
            )
        
        if prices_b.empty:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    f"Failed to load data for {request.b}",
                    {}
                )
            )
        
        returns_a = research_math.returns_from_close(prices_a['close'], "log")
        returns_b = research_math.returns_from_close(prices_b['close'], "log")
        
        # Align
        combined = pd.DataFrame({
            'a': returns_a,
            'b': returns_b
        }).dropna()
        
        if len(combined) < request.window:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    f"Insufficient overlap: {len(combined)} < {request.window}",
                    {}
                )
            )
        
        # Compute rolling correlation
        rolling_corr = research_math.compute_rolling_correlation(
            combined['a'],
            combined['b'],
            request.window
        )
        
        # Build series
        series = []
        for idx, val in rolling_corr.dropna().items():
            series.append({
                "date": idx.strftime('%Y-%m-%d'),
                "corr": round(float(val), 4) if not np.isnan(val) else None
            })
        
        # Downsample if too long
        if len(series) > 500:
            step = len(series) // 500
            series = series[::step]
        
        return JSONResponse(content={
            "meta": {
                "a": request.a,
                "b": request.b,
                "window": request.window,
                "lookback": request.lookback,
                "data_points": len(series),
                **research_cache.make_cache_meta(False)
            },
            "series": series
        })
        
    except Exception as e:
        logger.error(f"Error in correlation_pair: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=make_error_response(
                "INTERNAL_ERROR",
                str(e),
                {}
            )
        )
