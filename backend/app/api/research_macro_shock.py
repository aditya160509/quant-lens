"""
Research Macro Shock API
D2: Macro shock propagation analysis for selected tickers.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import pandas as pd
import numpy as np
from typing import Dict, List, Any
import logging

from app.models.research_schemas import (
    MacroShockRequest,
    make_error_response,
)
from app.services.research_cache import research_cache
from app.services import research_data, research_math

logger = logging.getLogger(__name__)

router = APIRouter()


def compute_macro_shocks(
    ticker_returns: Dict[str, pd.Series],
    macro_changes: pd.DataFrame,
    shocks: Dict[str, float],
    shock_mode: str,
    winsor_p: float = 0.01,
    ridge: float = 1e-6
) -> Dict[str, Any]:
    """
    Compute macro shock impacts for all tickers.
    
    Args:
        ticker_returns: Dict of ticker -> returns series
        macro_changes: DataFrame of macro driver daily changes
        shocks: Dict of driver -> shock magnitude
        shock_mode: "sigma" or "raw"
        winsor_p: Winsorization percentile
        ridge: Ridge regularization for OLS
        
    Returns:
        Dict with 'impacts' and 'rankings'
    """
    impacts = {}
    
    # Standardize macro changes if sigma mode
    if shock_mode == "sigma":
        macro_z = research_math.standardize_cross_sectional(macro_changes)
    else:
        macro_z = macro_changes.copy()
    
    drivers = list(macro_z.columns)
    
    for ticker, returns in ticker_returns.items():
        # Align returns with macro
        combined = pd.DataFrame({'y': returns})
        for driver in drivers:
            combined[driver] = macro_z[driver]
        
        combined = combined.dropna()
        
        if len(combined) < 30:
            impacts[ticker] = {
                "total": None,
                "components": {d: None for d in drivers},
                "fit": {"r2": None, "n": len(combined), "error": "Insufficient data"}
            }
            continue
        
        # Winsorize
        combined['y'] = research_math.winsorize(combined['y'], winsor_p)
        for d in drivers:
            combined[d] = research_math.winsorize(combined[d], winsor_p)
        
        # Multi-factor regression
        y = combined['y'].values
        X = combined[drivers].values
        
        betas, stats, r2 = research_math.ols_multi_factor(
            y, X, ridge=ridge, add_intercept=True
        )
        
        resid_std = stats.get("residual_std")
        
        if np.any(np.isnan(betas)):
            impacts[ticker] = {
                "total": None,
                "components": {d: None for d in drivers},
                "fit": {"r2": None, "n": len(combined), "error": "Regression failed"}
            }
            continue
        
        # betas[0] is intercept, betas[1:] are driver betas
        driver_betas = betas[1:]
        
        # Compute impact
        components = {}
        total = 0.0
        
        for i, driver in enumerate(drivers):
            shock_val = shocks.get(driver, 0.0)
            contrib = driver_betas[i] * shock_val
            components[driver] = round(float(contrib), 6)
            total += contrib
        
        impacts[ticker] = {
            "total": round(float(total), 6),
            "components": components,
            "fit": {
                "r2": round(float(r2), 4) if not np.isnan(r2) else None,
                "n": len(combined),
                "resid_std": round(float(resid_std), 6) if not np.isnan(resid_std) else None
            }
        }
    
    # Compute rankings
    valid_impacts = [(t, d["total"]) for t, d in impacts.items() if d["total"] is not None]
    
    sorted_positive = sorted(
        [(t, v) for t, v in valid_impacts if v > 0],
        key=lambda x: -x[1]
    )[:10]
    
    sorted_negative = sorted(
        [(t, v) for t, v in valid_impacts if v < 0],
        key=lambda x: x[1]
    )[:10]
    
    rankings = {
        "top_positive": [{"ticker": t, "impact": v} for t, v in sorted_positive],
        "top_negative": [{"ticker": t, "impact": v} for t, v in sorted_negative]
    }
    
    return {
        "impacts": impacts,
        "rankings": rankings
    }


@router.post("/macro_shock")
async def macro_shock(request: MacroShockRequest):
    """
    Compute macro shock propagation impacts for selected tickers.
    
    Estimates how macro driver shocks affect asset returns using multivariate OLS.
    """
    try:
        # Check compute cache
        payload = request.model_dump()
        cached, cache_hit = research_cache.get_compute(payload)
        if cache_hit and cached is not None:
            cached['meta']['cache_hit'] = True
            return JSONResponse(content=cached)
        
        # Validate drivers
        available_macro = research_data.get_available_macro()
        invalid_drivers = [d for d in request.drivers if d.upper() not in available_macro]
        if invalid_drivers:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "INVALID_INPUT",
                    f"Unknown macro drivers: {invalid_drivers}",
                    {"available": available_macro}
                )
            )
        
        # Validate shocks match drivers
        shock_drivers = set(request.shocks.keys())
        requested_drivers = set(d.upper() for d in request.drivers)
        missing_shocks = requested_drivers - set(k.upper() for k in shock_drivers)
        if missing_shocks:
            # Default missing shocks to 0
            for d in missing_shocks:
                request.shocks[d] = 0.0
        
        # Load macro data
        macro_data_df = research_data.get_macro_series(request.drivers, request.lookback)
        
        if macro_data_df.empty:
            return JSONResponse(
                status_code=500,
                content=make_error_response(
                    "DATA_ERROR",
                    "Failed to load macro data. Ensure FRED_API_KEY is set.",
                    {}
                )
            )
        
        # Compute daily changes
        macro_changes = macro_data_df.diff()
        macro_changes = macro_changes.dropna()
        
        if len(macro_changes) < 30:
            return JSONResponse(
                status_code=400,
                content=make_error_response(
                    "DATA_ERROR",
                    f"Insufficient macro data: {len(macro_changes)} days",
                    {}
                )
            )
        
        # Load ticker returns
        ticker_returns = {}
        failed_tickers = []
        
        for ticker in request.tickers:
            prices = research_data.get_prices_daily(ticker, request.lookback)
            
            if prices.empty or 'close' not in prices.columns:
                failed_tickers.append(ticker)
                continue
            
            returns = research_math.returns_from_close(
                prices['close'],
                request.returns_type.value
            )
            
            if len(returns.dropna()) < 30:
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
        
        # Normalize shock keys to uppercase
        normalized_shocks = {k.upper(): v for k, v in request.shocks.items()}
        
        # Compute impacts
        results = compute_macro_shocks(
            ticker_returns,
            macro_changes,
            normalized_shocks,
            request.shock_mode.value,
            request.model.winsor_p,
            request.model.ridge
        )
        
        # Build response
        response = {
            "meta": {
                "drivers": list(macro_changes.columns),
                "shock_mode": request.shock_mode.value,
                "shocks_applied": normalized_shocks,
                "lookback_days": request.lookback,
                "tickers_requested": len(request.tickers),
                "tickers_computed": len(ticker_returns),
                "failed_tickers": failed_tickers if failed_tickers else None,
                **research_cache.make_cache_meta(False)
            },
            "impacts": results["impacts"],
            "rankings": results["rankings"]
        }
        
        # Cache result
        research_cache.set_compute(payload, response)
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error in macro_shock: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=make_error_response(
                "INTERNAL_ERROR",
                str(e),
                {}
            )
        )
